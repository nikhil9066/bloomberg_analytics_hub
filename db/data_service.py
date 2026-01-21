"""
Data service layer for retrieving financial data from SAP HANA
Provides clean interface for dashboard queries
"""

import logging
import pandas as pd
from datetime import datetime, timedelta
from db.hana_client import HanaClient


class FinancialDataService:
    """Service for retrieving and processing financial data for dashboard"""

    def __init__(self, config):
        """Initialize data service with HANA client"""
        self.logger = logging.getLogger(__name__)
        self.hana_client = HanaClient(config)
        self.schema = config['hana']['schema']
        self.connected = False

        # Simple in-memory cache with TTL
        self._cache = {}
        self._cache_ttl = timedelta(minutes=5)  # Cache for 5 minutes

    def connect(self):
        """Establish connection to HANA"""
        self.connected = self.hana_client.connect()
        return self.connected

    def close(self):
        """Close HANA connection"""
        if self.hana_client:
            self.hana_client.close()
            self.connected = False

    def _get_cached(self, key):
        """Get data from cache if not expired"""
        if key in self._cache:
            data, timestamp = self._cache[key]
            if datetime.now() - timestamp < self._cache_ttl:
                self.logger.debug(f"Cache hit for key: {key}")
                return data
            else:
                # Cache expired, remove it
                del self._cache[key]
                self.logger.debug(f"Cache expired for key: {key}")
        return None

    def _set_cached(self, key, data):
        """Store data in cache with timestamp"""
        self._cache[key] = (data, datetime.now())
        self.logger.debug(f"Cache set for key: {key}")

    def get_financial_ratios(self, limit=50):
        """
        Retrieve financial ratios data - latest records only

        Args:
            limit (int): Maximum number of records to retrieve (default 50, latest by timestamp)

        Returns:
            pd.DataFrame: Financial ratios data (most recent records)
        """
        if not self.connected:
            self.logger.error("Not connected to HANA")
            return pd.DataFrame()

        # Check cache first
        cache_key = f"financial_ratios_{limit}"
        cached_data = self._get_cached(cache_key)
        if cached_data is not None:
            return cached_data

        cursor = None
        try:
            query = f"""
            SELECT
                "TICKER",
                "IDENTIFIER_TYPE",
                "IDENTIFIER_VALUE",
                "TOT_DEBT_TO_TOT_ASSET",
                "CASH_DVD_COVERAGE",
                "TOT_DEBT_TO_EBITDA",
                "CUR_RATIO",
                "QUICK_RATIO",
                "GROSS_MARGIN",
                "INTEREST_COVERAGE_RATIO",
                "EBITDA_MARGIN",
                "TOT_LIAB_AND_EQY",
                "NET_DEBT_TO_SHRHLDR_EQTY",
                "TIMESTAMP"
            FROM "{self.schema}"."FINANCIAL_RATIOS"
            ORDER BY "TIMESTAMP" DESC
            LIMIT {limit}
            """

            cursor = self.hana_client.connection.cursor()
            cursor.execute(query)

            columns = [desc[0] for desc in cursor.description]
            data = cursor.fetchall()

            df = pd.DataFrame(data, columns=columns)
            self.logger.info(f"Retrieved {len(df)} financial ratio records")

            # Cache the result
            self._set_cached(cache_key, df)

            return df

        except Exception as e:
            self.logger.error(f"Error retrieving financial ratios: {str(e)}")
            return pd.DataFrame()
        finally:
            if cursor:
                cursor.close()

    def get_advanced_financials(self, limit=100):
        """
        Retrieve advanced financial data
        Note: This returns empty DataFrame as FINANCIAL_ADVANCED table doesn't exist
        Kept for backward compatibility with dashboard code

        Args:
            limit (int): Maximum number of records to retrieve

        Returns:
            pd.DataFrame: Empty DataFrame (table doesn't exist)
        """
        self.logger.debug("get_advanced_financials called but FINANCIAL_ADVANCED table doesn't exist")
        return pd.DataFrame()

    def get_ticker_list(self):
        """
        Get unique list of tickers from FINANCIAL_RATIOS table

        Returns:
            list: Unique ticker symbols
        """
        if not self.connected:
            return []

        cursor = None
        try:
            query = f"""
            SELECT DISTINCT "TICKER"
            FROM "{self.schema}"."FINANCIAL_RATIOS"
            WHERE "TICKER" IS NOT NULL
            ORDER BY "TICKER"
            """

            cursor = self.hana_client.connection.cursor()
            cursor.execute(query)
            tickers = [row[0] for row in cursor.fetchall()]

            return tickers

        except Exception as e:
            self.logger.error(f"Error retrieving ticker list: {str(e)}")
            return []
        finally:
            if cursor:
                cursor.close()

    def get_ticker_data(self, ticker):
        """
        Get all data for a specific ticker from FINANCIAL_RATIOS table

        Args:
            ticker (str): Stock ticker symbol

        Returns:
            dict: Dictionary with 'ratios' DataFrame (advanced is empty)
        """
        if not self.connected:
            return {'ratios': pd.DataFrame(), 'advanced': pd.DataFrame()}

        cursor = None
        try:
            cursor = self.hana_client.connection.cursor()

            # Get ratios data
            ratios_query = f"""
            SELECT * FROM "{self.schema}"."FINANCIAL_RATIOS"
            WHERE "TICKER" = ?
            ORDER BY "TIMESTAMP" DESC
            """

            cursor.execute(ratios_query, [ticker])
            columns = [desc[0] for desc in cursor.description]
            ratios_data = cursor.fetchall()
            ratios_df = pd.DataFrame(ratios_data, columns=columns)

            return {
                'ratios': ratios_df,
                'advanced': pd.DataFrame()  # No advanced table
            }

        except Exception as e:
            self.logger.error(f"Error retrieving ticker data: {str(e)}")
            return {'ratios': pd.DataFrame(), 'advanced': pd.DataFrame()}
        finally:
            if cursor:
                cursor.close()

    def get_summary_stats(self):
        """
        Get summary statistics for dashboard

        Returns:
            dict: Summary statistics
        """
        if not self.connected:
            return {}

        cursor = None
        try:
            cursor = self.hana_client.connection.cursor()

            # Count records in FINANCIAL_RATIOS table
            cursor.execute(f'SELECT COUNT(*) FROM "{self.schema}"."FINANCIAL_RATIOS"')
            ratios_count = cursor.fetchone()[0]

            # Get unique tickers
            cursor.execute(f'SELECT COUNT(DISTINCT "TICKER") FROM "{self.schema}"."FINANCIAL_RATIOS"')
            unique_tickers = cursor.fetchone()[0]

            # Get last update time
            cursor.execute(f'SELECT MAX("TIMESTAMP") FROM "{self.schema}"."FINANCIAL_RATIOS"')
            last_update = cursor.fetchone()[0]

            return {
                'ratios_count': ratios_count,
                'advanced_count': 0,  # No advanced table
                'unique_tickers': unique_tickers,
                'last_update': last_update
            }

        except Exception as e:
            self.logger.error(f"Error retrieving summary stats: {str(e)}")
            return {}
        finally:
            if cursor:
                cursor.close()

    def get_dashboard_stats(self):
        """
        Get comprehensive dashboard statistics for sidebar display

        Returns:
            dict: Dashboard statistics including counts, data quality, timestamps
        """
        if not self.connected:
            return {
                'total_records': 0,
                'annual_records': 0,
                'unique_tickers': 0,
                'last_sync': None,
                'data_quality': 0.0,
                'connection_status': 'Disconnected'
            }

        cursor = None
        try:
            cursor = self.hana_client.connection.cursor()

            # Count records in FINANCIAL_RATIOS table
            cursor.execute(f'SELECT COUNT(*) FROM "{self.schema}"."FINANCIAL_RATIOS"')
            ratios_count = cursor.fetchone()[0]

            # Count records in ANNUAL_FINANCIALS table
            try:
                cursor.execute(f'SELECT COUNT(*) FROM "{self.schema}"."ANNUAL_FINANCIALS"')
                annual_count = cursor.fetchone()[0]
            except Exception:
                annual_count = 0

            # Get unique tickers
            cursor.execute(f'SELECT COUNT(DISTINCT "TICKER") FROM "{self.schema}"."FINANCIAL_RATIOS"')
            unique_tickers = cursor.fetchone()[0]

            # Get last update time (most recent timestamp)
            cursor.execute(f'SELECT MAX("TIMESTAMP") FROM "{self.schema}"."FINANCIAL_RATIOS"')
            last_sync = cursor.fetchone()[0]

            # Calculate data quality (percentage of non-null values in key columns)
            cursor.execute(f'''
                SELECT
                    COUNT(*) as total,
                    COUNT("TICKER") as ticker_count,
                    COUNT("GROSS_MARGIN") as gross_margin_count,
                    COUNT("EBITDA_MARGIN") as ebitda_margin_count,
                    COUNT("CUR_RATIO") as cur_ratio_count,
                    COUNT("QUICK_RATIO") as quick_ratio_count
                FROM "{self.schema}"."FINANCIAL_RATIOS"
            ''')
            quality_row = cursor.fetchone()
            if quality_row and quality_row[0] > 0:
                total = quality_row[0]
                filled_count = sum(quality_row[1:])
                total_possible = total * 5  # 5 key columns
                data_quality = (filled_count / total_possible) * 100 if total_possible > 0 else 0
            else:
                data_quality = 0.0

            return {
                'total_records': ratios_count,
                'annual_records': annual_count,
                'unique_tickers': unique_tickers,
                'last_sync': last_sync,
                'data_quality': round(data_quality, 1),
                'connection_status': 'Connected'
            }

        except Exception as e:
            self.logger.error(f"Error retrieving dashboard stats: {str(e)}")
            return {
                'total_records': 0,
                'annual_records': 0,
                'unique_tickers': 0,
                'last_sync': None,
                'data_quality': 0.0,
                'connection_status': 'Error'
            }
        finally:
            if cursor:
                cursor.close()

    def get_annual_financials(self, tickers=None):
        """
        Retrieve annual financial data from ANNUAL_FINANCIALS table

        Args:
            tickers (list): Optional list of tickers to filter by

        Returns:
            pd.DataFrame: Annual financials data (all records, no limit)
        """
        if not self.connected:
            self.logger.error("Not connected to HANA")
            return pd.DataFrame()

        # Check cache first
        cache_key = f"annual_financials_{','.join(tickers) if tickers else 'all'}"
        cached_data = self._get_cached(cache_key)
        if cached_data is not None:
            return cached_data

        cursor = None
        try:
            # Build query based on whether tickers are provided
            if tickers:
                placeholders = ', '.join(['?' for _ in tickers])
                query = f"""
                SELECT *
                FROM "{self.schema}"."ANNUAL_FINANCIALS"
                WHERE "TICKER" IN ({placeholders})
                ORDER BY "TICKER", "FISCAL_YEAR" DESC
                """
                cursor = self.hana_client.connection.cursor()
                cursor.execute(query, tickers)
            else:
                query = f"""
                SELECT *
                FROM "{self.schema}"."ANNUAL_FINANCIALS"
                ORDER BY "TICKER", "FISCAL_YEAR" DESC
                """
                cursor = self.hana_client.connection.cursor()
                cursor.execute(query)

            columns = [desc[0] for desc in cursor.description]
            data = cursor.fetchall()

            df = pd.DataFrame(data, columns=columns)
            self.logger.info(f"Retrieved {len(df)} annual financials records")

            # Cache the result
            self._set_cached(cache_key, df)

            return df

        except Exception as e:
            self.logger.error(f"Error retrieving annual financials: {str(e)}")
            return pd.DataFrame()
        finally:
            if cursor:
                cursor.close()

    def get_comparison_data(self, tickers, metrics):
        """
        Get comparison data for multiple tickers and metrics

        Args:
            tickers (list): List of ticker symbols
            metrics (list): List of metric names

        Returns:
            pd.DataFrame: Comparison data
        """
        if not self.connected or not tickers or not metrics:
            return pd.DataFrame()

        cursor = None
        try:
            # Validate metrics against allowed columns to prevent SQL injection
            allowed_metrics = {
                'GROSS_MARGIN', 'EBITDA_MARGIN', 'CUR_RATIO', 'QUICK_RATIO',
                'TOT_DEBT_TO_TOT_ASSET', 'INTEREST_COVERAGE_RATIO', 'CASH_DVD_COVERAGE',
                'TOT_DEBT_TO_EBITDA', 'NET_DEBT_TO_SHRHLDR_EQTY', 'TOT_LIAB_AND_EQY'
            }

            # Filter metrics to only allowed ones
            safe_metrics = [m for m in metrics if m in allowed_metrics]
            if not safe_metrics:
                self.logger.warning("No valid metrics provided for comparison")
                return pd.DataFrame()

            # Build column list with proper quoting
            column_list = ', '.join([f'"{metric}"' for metric in safe_metrics])

            # Build parameterized query for tickers
            placeholders = ', '.join(['?' for _ in tickers])

            query = f"""
            SELECT
                "TICKER",
                {column_list}
            FROM "{self.schema}"."FINANCIAL_RATIOS"
            WHERE "TICKER" IN ({placeholders})
            """

            cursor = self.hana_client.connection.cursor()
            cursor.execute(query, tickers)

            columns = [desc[0] for desc in cursor.description]
            data = cursor.fetchall()

            df = pd.DataFrame(data, columns=columns)
            return df

        except Exception as e:
            self.logger.error(f"Error retrieving comparison data: {str(e)}")
            return pd.DataFrame()
        finally:
            if cursor:
                cursor.close()
