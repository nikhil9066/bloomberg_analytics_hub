# Quick Testing Guide - CFO Dashboard Fixes (Mar 9, 2026)

## 🚀 Start the Dashboard

```bash
cd /Users/nikhil/.openclaw/workspace/bloomberg_analytics_hub
git checkout feature/dashboard-fixes-mar-9
python app.py
```

Open: http://localhost:8050

---

## ✅ Test Sequence

### 1. First Load (Fix #5)
**Expected:** Dashboard loads IMMEDIATELY with demo data
- No "Welcome to CFO Pulse" screen
- Test Company shown
- 5 competitors pre-loaded: META, GOOGL, AAPL, MSFT, AMZN

❌ **If you see onboarding screen** → Fix #5 failed

---

### 2. Margin Bridge Analysis (Fix #1)
**Location:** Scroll to "Margin Bridge Analysis" section

**Expected:**
- Waterfall chart starts at positive Revenue
- Flows downward through deductions (COGS, OpEx, D&A, Interest & Tax)
- Ends at Net Income
- All "total" bars (Revenue, Gross Profit, EBITDA, EBIT, Net Income) are positive
- All "relative" bars (COGS, OpEx, D&A, Interest & Tax) are negative (pulling down)

❌ **If Revenue or totals show negative** → Fix #1 failed

---

### 3. Ratio Analyzer (Fix #2)
**Location:** Navigate to "Ratio Analyzer" tab

**Expected:** 6 ratio cards show:
1. Gross Margin: XX%
2. EBITDA Margin: XX%
3. Current Ratio: X.X:1
4. Quick Ratio: X.X:1
5. Debt to Asset: XX%
6. Interest Coverage: X.Xx

**Also check:**
- Chart below ratios renders properly
- No "none" or "N/A" values

❌ **If any ratio shows "none"** → Fix #2 failed

---

### 4. Forecast & Trends (Fix #4)
**Location:** Navigate to "Forecast & Trends" tab

**Test 4a - All Companies Shown:**
- Count the forecast cards at top
- Should show 5 cards (META, GOOGL, AAPL, MSFT, AMZN)

❌ **If only 4 cards shown** → Fix #4a failed

**Test 4b - Different Values:**
- Check "Projected Growth" value on each card
- Values should be DIFFERENT for each company
- Example: META: 8.3%, GOOGL: 6.5%, AAPL: 5.2%, etc.

❌ **If all show same value (like 5.0%)** → Fix #4b failed

**Test 4d - Dotted Forecast Lines:**
- Look at the area chart
- Historical years (2023, 2024) → solid lines
- Forecast years (2025 (F), 2026 (F)) → dotted lines

❌ **If all lines solid** → Fix #4d failed

**Test 4e - Actual vs Forecast EBITDA Chart:**
- Scroll down
- Should see new full-width chart titled "Actual vs Forecast EBITDA"
- Shows all 5 companies
- Historical (2023-2024): solid
- Forecast (2025-2026 (F)): dotted

❌ **If chart missing** → Fix #4e failed

---

### 5. Scenario Simulator (Fix #3)
**Location:** Navigate to "Scenario Simulator" tab

**Expected Layout:**
- **Left panel (4 columns):**
  - Revenue Growth slider (-10% to 30%, default 5%)
  - Cost Reduction slider (0% to 20%, default 0%)
  - Margin Improvement slider (0 to 10 pts, default 0)
  - "Reset to Baseline" button

- **Right panel (8 columns):**
  - Dual-line chart showing 2024-2027 (F)
  - Comparison metrics for 2027 (Revenue, EBITDA, Net Income)

**Test Interactivity:**
1. Move "Revenue Growth" slider to 15%
   - Chart should update immediately
   - Dashed lines (user scenario) should diverge upward from solid lines
   - 2027 metrics should show positive delta

2. Move "Cost Reduction" to 10%
   - EBITDA lines should diverge more

3. Click "Reset to Baseline"
   - All sliders return to: 5%, 0%, 0
   - Chart resets to baseline comparison

**Visual Check:**
- Baseline: Solid lines (blue Revenue, green EBITDA)
- User Scenario: Dashed lines with diamond markers
- Legend shows all 4 traces

❌ **If chart doesn't update on slider change** → Fix #3 callback failed
❌ **If only 1 scenario shown (not 2)** → Fix #3 failed
❌ **If reset button doesn't work** → Reset callback failed

---

## 🎨 Bonus: Dark Mode Test

Click the dark mode toggle (top right)

**Expected:**
- All sections switch to dark theme
- Charts update colors
- Text remains readable
- No visual glitches

❌ **If any section looks broken in dark mode** → Theme issue

---

## 📊 Quick Visual Summary

| Section | What to Check | Pass ✅ / Fail ❌ |
|---------|---------------|-------------------|
| First Load | No onboarding, demo data loaded | |
| Margin Bridge | Positive waterfall flow | |
| Ratio Analyzer | 6 ratios showing values | |
| Forecast Cards | 5 companies (not 4) | |
| Forecast Values | Different per company | |
| Forecast Lines | Dotted for future years | |
| EBITDA Chart | New chart exists | |
| Scenario Layout | Left controls, right results | |
| Scenario Sliders | Chart updates dynamically | |
| Scenario Lines | 2 scenarios (solid + dashed) | |
| Reset Button | Returns to 5%, 0%, 0 | |

---

## 🐛 If Something Fails

1. Check browser console for errors (F12 → Console tab)
2. Check terminal where `python app.py` is running for Python errors
3. Take screenshot of the issue
4. Note which test failed
5. Let Nikhil know!

---

## ✅ All Tests Pass?

If everything looks good:

```bash
# Push the branch
git push origin feature/dashboard-fixes-mar-9

# Then create PR on GitHub:
# - Title: "CFO Dashboard Fixes (Mar 9)"
# - Compare: feature/dashboard-fixes-mar-9 → main
# - Add description linking to FIXES_SUMMARY_MAR_9.md
# - Request review
```

**DO NOT MERGE** until reviewed! 🚨

---

## Quick Commands

```bash
# Start dashboard
python app.py

# Check current branch
git branch

# View changes
git diff main

# Uncommit if needed (keeps changes)
git reset --soft HEAD~1

# Discard all changes (nuclear option)
git checkout main && git branch -D feature/dashboard-fixes-mar-9
```

---

Happy testing! 🎯
