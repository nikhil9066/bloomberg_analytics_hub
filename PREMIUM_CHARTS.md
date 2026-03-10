# Premium Charts Design - CFO Dashboard

## 🔒 Premium Features (Blurred until payment)

These 4 charts use real Bloomberg data (450+ companies, 10k+ rows) to provide insights that typical dashboards don't offer.

---

### Chart 1: **Cash Conversion Cycle Bubble Chart** 💰
**Why CFOs love this:** Shows who's managing working capital most efficiently

**Data:**
- X-axis: Days Sales Outstanding (DSO) - how fast you collect cash
- Y-axis: Days Inventory Outstanding (DIO) - how fast you move inventory
- Bubble Size: Revenue ($M)
- Color: Days Payable Outstanding (DPO) - how long you delay paying suppliers
- Lower-left quadrant = Most efficient (collect fast, move inventory fast)

**Calculation:**
```
DSO = (Accounts Receivable / Revenue) × 365
DIO = (Inventory / COGS) × 365
DPO = (Accounts Payable / COGS) × 365
CCC = DSO + DIO - DPO (lower is better)
```

**Fields:** `ACCOUNTS_RECEIVABLE`, `SALES_REV_TURN`, `INVENTORY`, `IS_COGS`, `ACCOUNTS_PAYABLE`

---

### Chart 2: **Margin Decomposition Waterfall** 📊
**Why CFOs love this:** Pinpoints EXACTLY where margins are lost vs industry

**Data:**
- Start: Revenue (100%)
- Deductions:
  - COGS %
  - R&D %
  - SG&A %
  - D&A %
  - Interest %
  - Tax %
- End: Net Margin %

**Comparison:** YOUR company vs TOP 10 COMPETITOR AVERAGE

**Visualization:** Dual waterfall (side-by-side)
- Green bars = You're better than average
- Red bars = You're worse than average

**Fields:** `SALES_REV_TURN`, `IS_COGS`, `IS_RESEARCH_AND_DEVELOPMENT`, `IS_SGA_EXPENSE`, `IS_DEPRECIATION_AND_AMORTIZATION`, `IS_INT_EXPENSE`, `IS_INC_TAX_EXP`, `NET_INCOME`

---

### Chart 3: **DuPont ROE Decomposition Sunburst** 🎯
**Why CFOs love this:** Shows which lever is driving/dragging ROE

**Formula:**
```
ROE = Net Margin × Asset Turnover × Equity Multiplier
    = (Net Income / Revenue) × (Revenue / Assets) × (Assets / Equity)
```

**Visualization:** Sunburst chart with 3 rings
- Inner ring: Your company ROE
- Middle ring: 3 components (Net Margin, Asset Turnover, Leverage)
- Outer ring: Your value vs Industry Average for each component

**Color coding:**
- Green = You're beating industry average
- Red = You're lagging industry average
- Gray = Neutral

**Fields:** `NET_INCOME`, `SALES_REV_TURN`, `TOT_LIAB_AND_EQY`, `SHRHLDR_EQY`

---

### Chart 4: **Working Capital Efficiency Matrix** 📈
**Why CFOs love this:** 2×2 matrix showing who's winning on efficiency + profitability

**Axes:**
- X-axis: Cash Conversion Cycle (days) - lower is better
- Y-axis: ROIC (Return on Invested Capital) % - higher is better

**Quadrants:**
- **Top-left:** Efficient + Profitable ⭐ (Best companies)
- **Top-right:** Inefficient but Profitable 💰
- **Bottom-left:** Efficient but Unprofitable 🔧
- **Bottom-right:** Inefficient + Unprofitable ⚠️ (Worst)

**Your company:** Highlighted with ⭐ marker + label
**All 50 competitors:** Plotted as dots (color-coded by industry)

**Calculations:**
```
CCC = DSO + DIO - DPO
ROIC = NOPAT / Invested Capital
     = (EBIT × (1 - Tax Rate)) / (Equity + Debt)
```

**Fields:** Same as Chart 1 + `EBIT`, `IS_INC_TAX_EXP`, `SHRHLDR_EQY`, `TOT_DEBT`

---

## 🎨 Payment Page Design

**Blur effect:** 
- Premium section blurred with `filter: blur(8px)`
- Overlay with gradient background
- CTA: "🔒 Unlock Pro Analytics - $49/month"
- Payment form: Card number, Expiry, CVV (animated inputs)
- Demo mode: Any card number unlocks (for client demo)

**Animation:**
- Shake effect on hover
- Pulse glow on CTA button
- Smooth slide-in from bottom when payment succeeds
- Confetti explosion on unlock ✨

---

## Implementation Notes

- All calculations done server-side in ml_service.py
- Data cached (5-min expiry) for performance
- Dark mode compatible
- Mobile responsive (charts stack vertically)
- Export to PDF feature (premium only)
