# CFO Dashboard Fixes - March 9, 2026

## Overview
Working on branch: `feature/dashboard-fixes-mar-9`
**DO NOT MERGE TO MAIN** - Wait for review

## Issues to Fix

### 1. Margin Bridge Analysis - Negative Values ❌
**Location:** app.py line ~3655-3798
**Problem:** Waterfall chart showing negative/incorrect values
**Root Cause:** Incorrect abs() usage in COGS and other calculations
**Fix:** 
- Recalculate COGS, OpEx, D&A, Interest & Taxes properly
- Ensure waterfall flows correctly: Revenue → COGS → Gross Profit → OpEx → EBITDA → D&A → EBIT → Interest/Tax → Net Income

### 2. Ratio Analyzer - Showing "None" ❌
**Location:** app.py line ~4087-4287
**Problem:** All ratio values showing as "none" including charts
**Root Cause:** Field name mismatch between ratio_mapping keys and actual ratio_scores keys from ml_service
**Data Structure from ml_service.analyze_ratios():**
```python
{
    "companies": [{
        'ticker': str,
        'ratio_scores': {
            'EBITDA_MARGIN': float,
            'GROSS_MARGIN': float,
            'CUR_RATIO': float,
            etc...
        }
    }]
}
```
**Fix:** Update ratio_mapping to match actual field names from dataset

### 3. Scenario Simulator - Major Redesign 🔄
**Location:** app.py line ~4302-4502
**Requirements:**
a. Use META company values (since we have ACDOCA data)
b. Show 2 scenarios:
   - **Scenario 1:** Current trend (baseline projection)
   - **Scenario 2:** User tweaked values (interactive sliders)
c. Dynamic graph with 2 lines:
   - Current trend line (solid)
   - User tweaked line (dashed)
d. Analyze image provided by user for design reference
   
**Implementation Plan:**
- Add input sliders for: Revenue Growth %, Cost Reduction %, Margin Improvement %
- Calculate baseline projection (5% default growth)
- Calculate user scenario with slider values
- Plot both on same graph with distinct styling
- Show comparison metrics (Revenue, EBITDA, Net Income for both scenarios)

### 4. Forecast & Trends - Multiple Bugs 🐛
**Location:** app.py line ~4529-4779

**Bug 4a:** Companies cut off at 4
**Current:** `selected_competitors[:5]` in forecast call, but cards use `[:4]`
**Fix:** Remove arbitrary limits, show all selected competitors

**Bug 4b:** All companies showing same values
**Root Cause:** Need to investigate - likely growth_rate is same for all (0.05 default)
**Fix:** Use company-specific historical growth rates from data

**Bug 4c:** Verify values correctness
**Action:** Add validation checks and logging to ensure forecast calculations are accurate

**Bug 4d:** Future values should be dotted
**Fix:** Add `dash='dot'` to forecast trace lines for years 2025 (F), 2026 (F)

**Bug 4e:** Add Actual vs Forecast EBITDA chart
**New Chart:** Side-by-side comparison of:
- Historical EBITDA (actual values)
- Forecasted EBITDA (dotted line continuation)
- Similar for Revenue, Net Income

### 5. Remove Onboarding - Load Demo Data 🚀
**Location:** app.py line ~960+ (create_onboarding_screen)
**Current:** Shows "Welcome to CFO Pulse" form on first load
**Requirement:** Skip onboarding, load demo data immediately
**Fix:**
- Modify app initialization to pre-load demo companies
- Skip onboarding screen entirely
- Use META, GOOGL, AAPL, MSFT, AMZN as default competitors
- Set Test Company data from ACDOCA (if available)

---

## Implementation Order

1. ✅ Create branch `feature/dashboard-fixes-mar-9`
2. Fix #5 (Remove onboarding) - Gets us working dashboard immediately
3. Fix #1 (Margin Bridge)
4. Fix #2 (Ratio Analyzer)
5. Fix #4 (Forecast & Trends bugs)
6. Fix #3 (Scenario Simulator) - Most complex, save for last

---

## Testing Checklist

- [ ] Margin Bridge shows positive waterfall flow
- [ ] Ratio Analyzer displays all values correctly
- [ ] Ratio Analyzer chart renders properly
- [ ] Scenario Simulator shows 2 scenarios clearly
- [ ] Scenario Simulator graph has 2 lines (current + user)
- [ ] Forecast shows all selected competitors (not cut at 4)
- [ ] Forecast values differ per company
- [ ] Forecast future values are dotted lines
- [ ] Actual vs Forecast EBITDA chart displays
- [ ] Dashboard loads with demo data immediately (no onboarding)
- [ ] All sections work in both light and dark mode

---

## Notes
- Test Company = "Test Company" (from ACDOCA integration)
- META = Primary competitor for Scenario Simulator baseline
- All changes on `feature/dashboard-fixes-mar-9` branch
- **DO NOT MERGE** until Nikhil reviews
