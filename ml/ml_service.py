"""
ML Service - Load and use trained ML models from HANA
Provides interface for dashboard to get ML predictions and insights
"""

import logging
import json
import io
import joblib
import numpy as np
import pandas as pd
from typing import Dict, List, Any, Optional, Tuple
from datetime import datetime

logger = logging.getLogger(__name__)


class MLService:
    """Service for loading and using ML models from HANA"""
    
    def __init__(self, hana_client, ml_schema: str = None, data_schema: str = None):
        """
        Initialize ML service with HANA client
        
        Args:
            hana_client: HANA connection client
            ml_schema: Schema for ML models (defaults to BLOOMBERG_DATA)
            data_schema: Schema for financial data (defaults to BLOOMBERG_DATA)
        """
        self.hana_client = hana_client
        # Use provided schemas or default to BLOOMBERG_DATA for both
        self.schema = ml_schema or "BLOOMBERG_DATA"
        self.data_schema = data_schema or "BLOOMBERG_DATA"
        self._model_cache = {}
        logger.info(f"MLService initialized with ML schema: {self.schema}, Data schema: {self.data_schema}")
        
    def get_active_models(self) -> List[Dict]:
        """Get list of all active ML models"""
        try:
            cursor = self.hana_client.connection.cursor()
            cursor.execute(f"""
                SELECT "MODEL_ID", "MODEL_NAME", "MODEL_TYPE", "VERSION", 
                       "TRAINING_ROWS", "CREATED_AT"
                FROM "{self.schema}"."ML_MODELS"
                WHERE "IS_ACTIVE" = 1
                ORDER BY "MODEL_NAME"
            """)
            
            columns = [desc[0] for desc in cursor.description]
            rows = cursor.fetchall()
            
            models = []
            for row in rows:
                models.append({
                    "model_id": row[0],
                    "name": row[1],
                    "type": row[2],
                    "version": row[3],
                    "training_rows": row[4],
                    "trained_at": row[5].strftime("%Y-%m-%d %H:%M") if row[5] else None
                })
            logger.info(f"Found {len(models)} active ML models")
            return models
            
        except Exception as e:
            logger.error(f"Error getting active models: {e}")
            return []
    
    def load_model(self, model_name: str) -> Tuple[Any, Any, List[str], Dict]:
        """
        Load a model from HANA.
        Returns: (model, scaler, feature_columns, metrics)
        """
        # Check cache first
        if model_name in self._model_cache:
            logger.debug(f"Model {model_name} loaded from cache")
            return self._model_cache[model_name]
            
        try:
            cursor = self.hana_client.connection.cursor()
            cursor.execute(f"""
                SELECT "MODEL_BLOB", "SCALER_BLOB", "FEATURE_COLUMNS", "METRICS"
                FROM "{self.schema}"."ML_MODELS"
                WHERE "MODEL_NAME" = ? AND "IS_ACTIVE" = 1
            """, (model_name,))
            
            row = cursor.fetchone()
            if not row:
                logger.warning(f"No active model found: {model_name} in schema {self.schema}")
                return None, None, [], {}
            
            model_bytes, scaler_bytes, features_json, metrics_json = row
            
            # Deserialize model
            model_buffer = io.BytesIO(model_bytes)
            model = joblib.load(model_buffer)
            
            # Deserialize scaler if present
            scaler = None
            if scaler_bytes:
                scaler_buffer = io.BytesIO(scaler_bytes)
                scaler = joblib.load(scaler_buffer)
            
            feature_columns = json.loads(features_json) if features_json else []
            metrics = json.loads(metrics_json) if metrics_json else {}
            
            # Cache the loaded model
            self._model_cache[model_name] = (model, scaler, feature_columns, metrics)
            
            logger.info(f"Loaded model: {model_name} with {len(feature_columns)} features")
            return model, scaler, feature_columns, metrics
            
        except Exception as e:
            logger.error(f"Error loading model {model_name}: {e}")
            return None, None, [], {}
    
    def get_cluster_labels(self, model_name: str) -> List[Dict]:
        """Get cluster labels for a clustering model"""
        try:
            cursor = self.hana_client.connection.cursor()
            cursor.execute(f"""
                SELECT cl."CLUSTER_ID", cl."CLUSTER_LABEL", cl."SAMPLE_COUNT", cl."AVG_HEALTH_SCORE"
                FROM "{self.schema}"."ML_CLUSTER_LABELS" cl
                JOIN "{self.schema}"."ML_MODELS" m ON cl."MODEL_ID" = m."MODEL_ID"
                WHERE m."MODEL_NAME" = ? AND m."IS_ACTIVE" = 1
                ORDER BY cl."CLUSTER_ID"
            """, (model_name,))
            
            rows = cursor.fetchall()
            return [
                {
                    "cluster_id": row[0],
                    "label": row[1],
                    "sample_count": row[2],
                    "avg_health_score": float(row[3]) if row[3] else 0
                }
                for row in rows
            ]
            
        except Exception as e:
            logger.error(f"Error getting cluster labels: {e}")
            return []
    
    def get_company_data(self, tickers: List[str] = None) -> pd.DataFrame:
        """Get latest financial data for specified companies"""
        try:
            cursor = self.hana_client.connection.cursor()
            
            # First get all data from latest date
            query = f"""
                SELECT * FROM "{self.data_schema}"."FINANCIAL_RATIOS"
                WHERE "DATA_DATE" = (SELECT MAX("DATA_DATE") FROM "{self.data_schema}"."FINANCIAL_RATIOS")
            """
            cursor.execute(query)
            
            columns = [desc[0] for desc in cursor.description]
            rows = cursor.fetchall()
            
            df = pd.DataFrame(rows, columns=columns)
            logger.info(f"Loaded {len(df)} rows from FINANCIAL_RATIOS")
            
            # Convert Decimal to float
            for col in df.columns:
                if df[col].dtype == object:
                    try:
                        df[col] = pd.to_numeric(df[col], errors='ignore')
                    except:
                        pass
            
            # Normalize ticker column - remove " US Equity" suffix if present
            if 'TICKER' in df.columns:
                df['TICKER'] = df['TICKER'].str.replace(' US Equity', '', regex=False)
                logger.debug(f"Available tickers: {df['TICKER'].unique().tolist()[:10]}")
            
            # Deduplicate by TICKER - keep first row per ticker
            if 'TICKER' in df.columns:
                df = df.drop_duplicates(subset=['TICKER'], keep='first')
                logger.info(f"After deduplication: {len(df)} unique tickers")
            
            # Filter by tickers if provided
            if tickers and 'TICKER' in df.columns:
                # Normalize input tickers - filter out non-ticker values (like company names)
                normalized_tickers = []
                for t in tickers:
                    t_clean = t.replace(' US Equity', '')
                    # Only include if it looks like a valid ticker (all caps, reasonable length)
                    if t_clean.isupper() and len(t_clean) <= 5:
                        normalized_tickers.append(t_clean)
                
                if not normalized_tickers:
                    logger.warning(f"No valid tickers in input: {tickers}")
                    return df  # Return all data if no valid tickers
                
                df_filtered = df[df['TICKER'].isin(normalized_tickers)]
                logger.info(f"Filtered to {len(df_filtered)} rows for tickers: {normalized_tickers[:5]}")
                
                # Log which tickers weren't found
                found_tickers = df_filtered['TICKER'].unique().tolist()
                missing = [t for t in normalized_tickers if t not in found_tickers]
                if missing:
                    logger.warning(f"Tickers not found in data: {missing}")
                
                return df_filtered
            
            return df
            
        except Exception as e:
            logger.error(f"Error getting company data: {e}")
            return pd.DataFrame()
    
    def get_advanced_data(self, tickers: List[str] = None) -> pd.DataFrame:
        """Get advanced financial data"""
        try:
            cursor = self.hana_client.connection.cursor()
            
            query = f"""
                SELECT * FROM "{self.data_schema}"."FINANCIAL_DATA_ADVANCED"
                ORDER BY "DATA_DATE" DESC
            """
            cursor.execute(query)
            
            columns = [desc[0] for desc in cursor.description]
            rows = cursor.fetchall()
            
            df = pd.DataFrame(rows, columns=columns)
            logger.info(f"Loaded {len(df)} rows from FINANCIAL_DATA_ADVANCED")
            
            if tickers and 'TICKER' in df.columns:
                df = df[df['TICKER'].isin(tickers)]
                logger.info(f"Filtered to {len(df)} rows for tickers")
            
            # Convert Decimal to float
            for col in df.columns:
                if df[col].dtype == object:
                    try:
                        df[col] = pd.to_numeric(df[col], errors='ignore')
                    except:
                        pass
            
            return df
            
        except Exception as e:
            logger.error(f"Error getting advanced data: {e}")
            return pd.DataFrame()
    
    def _analyze_ratios_without_model(self, df: pd.DataFrame) -> Dict:
        """Fallback ratio analysis without ML model - uses data directly"""
        ratio_metrics = ['CUR_RATIO', 'QUICK_RATIO', 'GROSS_MARGIN', 'EBITDA_MARGIN', 
                        'TOT_DEBT_TO_TOT_ASSET', 'INTEREST_COVERAGE_RATIO']
        available = [m for m in ratio_metrics if m in df.columns]
        
        if not available:
            logger.warning("No ratio metrics available in data")
            return {"error": "No metrics", "companies": []}
        
        results = []
        for _, row in df.iterrows():
            ticker = row.get('TICKER', 'Unknown')
            
            ratio_scores = {}
            total_score = 0
            count = 0
            
            for feat in available:
                val = float(row[feat]) if pd.notna(row[feat]) else 0
                # Normalize to 0-100 scale
                if feat in ['CUR_RATIO', 'QUICK_RATIO']:
                    score = min(100, val * 40)  # Target ~2.5
                elif feat in ['GROSS_MARGIN', 'EBITDA_MARGIN']:
                    score = min(100, val * 2)  # Target ~50%
                elif feat == 'TOT_DEBT_TO_TOT_ASSET':
                    score = max(0, 100 - val * 2)  # Lower is better
                else:
                    score = min(100, max(0, val * 5))
                
                ratio_scores[feat] = score
                total_score += score
                count += 1
            
            avg_score = total_score / count if count > 0 else 50
            health_label = 'Excellent' if avg_score >= 80 else ('Good' if avg_score >= 60 else ('Fair' if avg_score >= 40 else 'Weak'))
            
            results.append({
                'ticker': ticker,
                'cluster': 0,
                'health_label': health_label,
                'ratio_scores': ratio_scores,
                'overall_score': avg_score
            })
        
        logger.info(f"Analyzed {len(results)} companies using data-only mode")
        
        return {
            "companies": results,
            "cluster_labels": [
                {"cluster_id": 0, "label": "Excellent", "sample_count": len([r for r in results if r['health_label'] == 'Excellent']), "avg_health_score": 85},
                {"cluster_id": 1, "label": "Good", "sample_count": len([r for r in results if r['health_label'] == 'Good']), "avg_health_score": 70},
                {"cluster_id": 2, "label": "Fair", "sample_count": len([r for r in results if r['health_label'] == 'Fair']), "avg_health_score": 50},
                {"cluster_id": 3, "label": "Weak", "sample_count": len([r for r in results if r['health_label'] == 'Weak']), "avg_health_score": 30},
            ],
            "features": available,
            "model_metrics": {"mode": "data-only"}
        }

    # ==================== RATIO ANALYZER ====================
    def analyze_ratios(self, tickers: List[str]) -> Dict:
        """
        Analyze financial ratios for given companies.
        Returns cluster assignments and health scores.
        """
        logger.info(f"analyze_ratios called with tickers: {tickers}")
        
        # Get data first
        df = self.get_company_data(tickers)
        if df.empty:
            logger.warning(f"No data found for tickers: {tickers}")
            return {"error": "No data", "companies": []}
        
        # Try to load model
        model, scaler, features, metrics = self.load_model('ratio_analyzer')
        
        # If no model, use data-only analysis
        if model is None:
            logger.info("Ratio analyzer model not loaded, using data-only mode")
            return self._analyze_ratios_without_model(df)
        
        # Get cluster labels
        cluster_labels = self.get_cluster_labels('ratio_analyzer')
        label_map = {c['cluster_id']: c['label'] for c in cluster_labels}
        
        results = []
        available_features = [f for f in features if f in df.columns]
        
        if not available_features:
            logger.warning("No matching features in data, falling back to data-only mode")
            return self._analyze_ratios_without_model(df)
        
        for _, row in df.iterrows():
            ticker = row.get('TICKER', 'Unknown')
            
            # Prepare features
            X = row[available_features].fillna(0).values.reshape(1, -1)
            X = np.array([[float(x) for x in X[0]]])
            
            try:
                if scaler:
                    X_scaled = scaler.transform(X)
                else:
                    X_scaled = X
                
                # Get cluster and health score
                if hasattr(model, 'kmeans'):
                    cluster = model.kmeans.predict(X_scaled)[0]
                    health_label = label_map.get(cluster, 'Unknown')
                else:
                    cluster = 0
                    health_label = 'N/A'
                
                # Calculate individual ratio scores
                ratio_scores = {}
                for feat in available_features:
                    val = float(row[feat]) if pd.notna(row[feat]) else 0
                    # Normalize to 0-100 scale (simplified)
                    ratio_scores[feat] = min(100, max(0, val * 10)) if val > 0 else 50
                
                results.append({
                    'ticker': ticker,
                    'cluster': int(cluster),
                    'health_label': health_label,
                    'ratio_scores': ratio_scores,
                    'overall_score': np.mean(list(ratio_scores.values()))
                })
                
            except Exception as e:
                logger.error(f"Error analyzing {ticker}: {e}")
                results.append({
                    'ticker': ticker,
                    'cluster': -1,
                    'health_label': 'Error',
                    'ratio_scores': {},
                    'overall_score': 0
                })
        
        logger.info(f"Analyzed {len(results)} companies with ML model")
        return {
            "companies": results,
            "cluster_labels": cluster_labels,
            "features": available_features,
            "model_metrics": metrics
        }
    
    # ==================== ANOMALY DETECTOR ====================
    def detect_anomalies(self, tickers: List[str]) -> Dict:
        """
        Detect anomalies in financial metrics.
        Returns anomaly scores for each company/metric.
        """
        logger.info(f"detect_anomalies called with tickers: {tickers}")
        
        df = self.get_company_data(tickers)
        if df.empty:
            return {"error": "No data", "companies": []}
        
        model, scaler, features, metrics = self.load_model('anomaly_detector')
        
        # If model not loaded, use statistical fallback
        if model is None:
            logger.info("Anomaly detector model not loaded, using statistical fallback")
            return self._detect_anomalies_fallback(df)
        
        results = []
        available_features = [f for f in features if f in df.columns]
        
        if not available_features:
            return self._detect_anomalies_fallback(df)
        
        for _, row in df.iterrows():
            ticker = row.get('TICKER', 'Unknown')
            
            X = row[available_features].fillna(0).values.reshape(1, -1)
            X = np.array([[float(x) for x in X[0]]])
            
            try:
                if scaler:
                    X_scaled = scaler.transform(X)
                else:
                    X_scaled = X
                
                # Get anomaly score from isolation forest
                if hasattr(model, 'iso_forest'):
                    anomaly_score = -model.iso_forest.decision_function(X_scaled)[0]
                    is_anomaly = model.iso_forest.predict(X_scaled)[0] == -1
                else:
                    anomaly_score = 0
                    is_anomaly = False
                
                # Per-metric anomaly scores
                metric_scores = {}
                for i, feat in enumerate(available_features):
                    val = X[0][i]
                    metric_scores[feat] = {
                        'value': float(val),
                        'score': min(5, abs(anomaly_score))
                    }
                
                results.append({
                    'ticker': ticker,
                    'anomaly_score': float(anomaly_score),
                    'is_anomaly': bool(is_anomaly),
                    'metric_scores': metric_scores
                })
                
            except Exception as e:
                logger.error(f"Error detecting anomalies for {ticker}: {e}")
        
        logger.info(f"Detected anomalies for {len(results)} companies")
        return {
            "companies": results,
            "features": available_features,
            "threshold": metrics.get('threshold', 0)
        }
    
    def _detect_anomalies_fallback(self, df: pd.DataFrame) -> Dict:
        """Statistical fallback for anomaly detection"""
        numeric_cols = df.select_dtypes(include=[np.number]).columns.tolist()
        features = [c for c in numeric_cols if c not in ['ID', 'DATA_DATE']][:8]
        
        results = []
        for _, row in df.iterrows():
            ticker = row.get('TICKER', 'Unknown')
            metric_scores = {}
            total_score = 0
            
            for feat in features:
                val = float(row[feat]) if pd.notna(row[feat]) else 0
                col_mean = df[feat].mean()
                col_std = df[feat].std()
                if col_std > 0:
                    z_score = abs(val - col_mean) / col_std
                    score = min(5, z_score)
                else:
                    score = 0
                metric_scores[feat] = {'value': val, 'score': score}
                total_score += score
            
            avg_score = total_score / len(features) if features else 0
            results.append({
                'ticker': ticker,
                'anomaly_score': avg_score,
                'is_anomaly': avg_score > 2.5,
                'metric_scores': metric_scores
            })
        
        return {"companies": results, "features": features, "threshold": 2.5}
    
    # ==================== COMPETITOR BENCHMARK ====================
    def benchmark_competitors(self, tickers: List[str], target_ticker: str = None) -> Dict:
        """
        Benchmark companies against each other.
        Returns similarity scores and rankings.
        """
        logger.info(f"benchmark_competitors called with tickers: {tickers}, target: {target_ticker}")
        
        df = self.get_company_data(tickers)
        if df.empty:
            return {"error": "No data", "companies": []}
        
        if target_ticker is None and tickers:
            target_ticker = tickers[0]
        
        model, scaler, features, metrics = self.load_model('competitor_benchmark')
        
        # Use data-driven approach if no model
        if model is None:
            logger.info("Competitor benchmark model not loaded, using data-driven approach")
        
        # Get available features
        numeric_cols = df.select_dtypes(include=[np.number]).columns.tolist()
        available_features = [c for c in numeric_cols if c not in ['ID', 'DATA_DATE']][:10]
        
        if features:
            available_features = [f for f in features if f in df.columns] or available_features
        
        results = []
        
        # Get target company data
        target_row = df[df['TICKER'] == target_ticker]
        if target_row.empty:
            logger.warning(f"Target company {target_ticker} not found")
            return {"error": f"Target company {target_ticker} not found", "companies": []}
        
        target_data = target_row[available_features].fillna(0).values[0]
        target_data = np.array([float(x) for x in target_data])
        
        for _, row in df.iterrows():
            ticker = row.get('TICKER', 'Unknown')
            
            X = row[available_features].fillna(0).values
            X = np.array([float(x) for x in X])
            
            try:
                # Calculate similarity (cosine similarity)
                if np.linalg.norm(X) > 0 and np.linalg.norm(target_data) > 0:
                    similarity = np.dot(X, target_data) / (np.linalg.norm(X) * np.linalg.norm(target_data))
                else:
                    similarity = 0
                
                # Per-metric comparison
                metric_comparison = {}
                for i, feat in enumerate(available_features):
                    target_val = target_data[i]
                    company_val = X[i]
                    if target_val != 0:
                        pct_diff = ((company_val - target_val) / abs(target_val)) * 100
                    else:
                        pct_diff = 0
                    
                    metric_comparison[feat] = {
                        'value': float(company_val),
                        'target_value': float(target_val),
                        'pct_diff': float(pct_diff),
                        'status': 'above' if pct_diff > 5 else ('below' if pct_diff < -5 else 'similar')
                    }
                
                results.append({
                    'ticker': ticker,
                    'similarity': float(similarity),
                    'is_target': ticker == target_ticker,
                    'metric_comparison': metric_comparison
                })
                
            except Exception as e:
                logger.error(f"Error benchmarking {ticker}: {e}")
        
        # Sort by similarity
        results.sort(key=lambda x: x['similarity'], reverse=True)
        
        logger.info(f"Benchmarked {len(results)} companies")
        return {
            "target": target_ticker,
            "companies": results,
            "features": available_features
        }
    
    # ==================== FORECASTER ====================
    def get_forecasts(self, tickers: List[str]) -> Dict:
        """
        Get financial forecasts for companies.
        """
        logger.info(f"get_forecasts called with tickers: {tickers}")
        
        df = self.get_advanced_data(tickers)
        if df.empty:
            # Try regular company data as fallback
            df = self.get_company_data(tickers)
            if df.empty:
                return {"error": "No data", "companies": []}
        
        model, scaler, features, metrics = self.load_model('forecaster')
        
        # Get available forecast metrics
        forecast_metrics = ['SALES_REV_TURN', 'NET_INCOME', 'EBITDA', 'CF_FREE_CASH_FLOW', 
                          'EBITDA_MARGIN', 'GROSS_MARGIN']
        available_metrics = [m for m in forecast_metrics if m in df.columns]
        
        if not available_metrics:
            logger.warning("No forecast metrics found in data")
            return {"error": "No forecast metrics", "companies": []}
        
        results = []
        for ticker in tickers:
            ticker_data = df[df['TICKER'] == ticker].head(1)
            if ticker_data.empty:
                logger.warning(f"No data for ticker {ticker}")
                continue
            
            ticker_forecasts = {}
            for metric in available_metrics:
                current_val = float(ticker_data[metric].iloc[0]) if pd.notna(ticker_data[metric].iloc[0]) else 0
                # Simple growth forecast
                growth_rate = 0.05  # 5% default growth
                if metrics and metric in metrics:
                    growth_rate = metrics[metric].get('avg_growth', 0.05)
                
                forecast_1y = current_val * (1 + growth_rate)
                forecast_2y = current_val * (1 + growth_rate) ** 2
                
                ticker_forecasts[metric] = {
                    'current': current_val,
                    'forecast_1y': forecast_1y,
                    'forecast_2y': forecast_2y,
                    'growth_rate': growth_rate
                }
            
            results.append({
                'ticker': ticker,
                'forecasts': ticker_forecasts
            })
        
        logger.info(f"Generated forecasts for {len(results)} companies")
        return {
            "companies": results,
            "metrics": available_metrics
        }
    
    # ==================== SCENARIO SIMULATOR ====================
    def simulate_scenarios(self, ticker: str, scenarios: List[Dict] = None) -> Dict:
        """
        Run scenario simulations for a company.
        """
        logger.info(f"simulate_scenarios called for ticker: {ticker}")
        
        df = self.get_company_data([ticker])
        if df.empty:
            return {"error": "No data", "scenarios": []}
        
        company_data = df.iloc[0]
        
        # Default scenarios if none provided
        if scenarios is None:
            scenarios = [
                {"name": "Base Case", "revenue_change": 0, "cost_change": 0},
                {"name": "Optimistic", "revenue_change": 0.15, "cost_change": -0.05},
                {"name": "Pessimistic", "revenue_change": -0.10, "cost_change": 0.10},
                {"name": "Cost Reduction", "revenue_change": 0, "cost_change": -0.15},
                {"name": "Growth Investment", "revenue_change": 0.20, "cost_change": 0.10},
            ]
        
        results = []
        base_revenue = float(company_data.get('SALES_REV_TURN', 0)) if 'SALES_REV_TURN' in company_data.index else 0
        if base_revenue == 0:
            base_revenue = float(company_data.get('TOT_LIAB_AND_EQY', 1000)) if 'TOT_LIAB_AND_EQY' in company_data.index else 1000
        
        base_margin = float(company_data.get('GROSS_MARGIN', 0)) if 'GROSS_MARGIN' in company_data.index else 0
        if base_margin == 0:
            base_margin = float(company_data.get('EBITDA_MARGIN', 30)) if 'EBITDA_MARGIN' in company_data.index else 30
        
        for scenario in scenarios:
            new_revenue = base_revenue * (1 + scenario.get('revenue_change', 0))
            margin_impact = scenario.get('cost_change', 0) * -50
            new_margin = base_margin + margin_impact
            new_profit = new_revenue * (new_margin / 100)
            
            results.append({
                'name': scenario['name'],
                'revenue': new_revenue,
                'margin': new_margin,
                'profit': new_profit,
                'revenue_change': scenario.get('revenue_change', 0) * 100,
                'margin_change': margin_impact
            })
        
        logger.info(f"Simulated {len(results)} scenarios for {ticker}")
        return {
            "ticker": ticker,
            "base_revenue": base_revenue,
            "base_margin": base_margin,
            "scenarios": results
        }
    
    # ==================== GOAL TRACKER ====================
    def track_goals(self, tickers: List[str], goals: List[Dict] = None) -> Dict:
        """
        Track progress towards financial goals.
        """
        logger.info(f"track_goals called with tickers: {tickers}")
        
        df = self.get_company_data(tickers)
        if df.empty:
            return {"error": "No data", "companies": []}
        
        # Default goals if none provided
        if goals is None:
            goals = [
                {"metric": "GROSS_MARGIN", "target": 40, "label": "Gross Margin > 40%"},
                {"metric": "CUR_RATIO", "target": 1.5, "label": "Current Ratio > 1.5"},
                {"metric": "EBITDA_MARGIN", "target": 20, "label": "EBITDA Margin > 20%"},
                {"metric": "TOT_DEBT_TO_TOT_ASSET", "target": 50, "label": "Debt/Asset < 50%", "inverse": True},
            ]
        
        results = []
        for _, row in df.iterrows():
            ticker = row.get('TICKER', 'Unknown')
            
            goal_progress = []
            for goal in goals:
                metric = goal['metric']
                target = goal['target']
                inverse = goal.get('inverse', False)
                
                current_val = float(row.get(metric, 0)) if pd.notna(row.get(metric)) else 0
                
                if inverse:
                    # Lower is better (e.g., debt ratio)
                    progress = min(100, max(0, (target - current_val + target) / target * 50)) if target > 0 else 50
                    on_track = current_val <= target
                else:
                    # Higher is better
                    progress = min(100, (current_val / target * 100)) if target > 0 else 0
                    on_track = current_val >= target
                
                goal_progress.append({
                    'label': goal['label'],
                    'metric': metric,
                    'current': current_val,
                    'target': target,
                    'progress': progress,
                    'on_track': on_track
                })
            
            results.append({
                'ticker': ticker,
                'goals': goal_progress
            })
        
        logger.info(f"Tracked goals for {len(results)} companies")
        return {
            "companies": results,
            "goal_definitions": goals
        }
