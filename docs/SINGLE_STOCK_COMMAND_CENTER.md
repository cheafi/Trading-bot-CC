# Single-Stock Command Center — Engineering Spec

**Product:** Clarity Console · Dossier tab (`index.html` → `tab==='dossier'`)  
**Goal:** Upgrade from “data viewer” to **investment decision console** — decision, comparison, tracking, action.  
**Principle:** Every module must answer: *So what? · Why now? · What to do? · What to avoid? · What invalidates?*

**Status vs today (observed in repo):**

| Layer | Today | Target |
|-------|-------|--------|
| A Decision summary | Partial (Verdict + conviction split) | **Unified sticky card** |
| B Fundamentals | ~9 KPIs via v9 | Trends + peers + drivers |
| C Technicals | Strong grid + chart | Multi-TF + scores + patterns |
| D Peers | 3M momentum rank only | Full comparison table |
| E Ownership | Conviction summary | Tables + lag labels |
| F Options | Grade only; UI disabled | Full flow panel |
| G Catalysts | Earnings + blackout | 7/30/90 map |
| H Monitoring | Trade advisor only | Thesis + delta trackers |

---

## 1. Page architecture (8 layers → UI)

```
┌──────────────────────────────────────────────────────────────────────────┐
│ STICKY: Layer A — Decision Summary (always visible)                       │
├──────────────────────────────────────────────────────────────────────────┤
│ TABS: [Decision] [Fundamentals] [Technicals] [Peers] [Ownership]         │
│       [Options] [Catalysts] [Risk] [Monitor] [Execute]                    │
├──────────────────────────────────────────────────────────────────────────┤
│ Tab content (scroll within tab) + right rail optional (desktop)         │
└──────────────────────────────────────────────────────────────────────────┘
```

**Route:** Keep `tab==='dossier'`.  
**Primary API (new):** `GET /api/v7/stock-intel/{ticker}` — aggregated payload (reduces 6+ parallel fetches → 503).  
**Legacy (keep during migration):** `/api/live/dossier/{t}`, `/api/v1/conviction/{t}`, `/api/dossier/{t}/peers`, `/api/v9/*`.

---

## 2. Layer A — Above-the-fold decision summary

### 2.1 Visible fields (always sticky)

| Field | Type | Source (existing → new) | So what? |
|-------|------|-------------------------|----------|
| `symbol` | string | live_dossier | Identity |
| `company_name` | string | yfinance info / new | Context |
| `exchange` | string | new | Listing |
| `sector` | string | signal.sector / v9 | Sleeve fit |
| `industry` | string | new | Peer set |
| `price` | number | live_dossier | Mark |
| `change_pct` | number | live_dossier | Day move |
| `market_cap` | number | v9 fundamentals | Size bucket |
| `verdict` | enum | **unified** BUY/WATCH/WAIT/AVOID | **Primary action** |
| `conviction_score` | 0–100 | merge confidence.final + conviction | Strength |
| `timing_score` | 0–100 | confidence.timing + structure | Entry quality |
| `risk_reward_score` | 0–100 | trade_plan.rr_ratio mapped | R:R quality |
| `entry_zone` | [low, high] | trade_plan | Where to bid |
| `stop` | number | trade_plan / 1.5 ATR | Invalidation |
| `target_zone` | [t1, t2] | trade_plan 1R/2R | Reward |
| `next_catalyst` | {date, label, days} | v9 earnings + events | Why now |
| `bull_one_liner` | string | why_buy[0] or AI | Quick bull |
| `bear_one_liner` | string | why_stop[0] or AI | Quick bear |
| `regime_gate` | PASS/BLOCK | regime.should_trade | Trade allowed? |
| `data_trust` | LIVE/DELAYED | trust strip | Can I trust this? |

### 2.2 UI block order (top → bottom, ~120px sticky header)

1. Row 1: Ticker · name · sector/industry · price · Δ% · cap  
2. Row 2: **VERDICT pill** · conviction · timing · R:R · regime gate  
3. Row 3: Entry zone · Stop · Target · **Next catalyst (D-12)**  
4. Row 4: Bull line · Bear line · [Research] [Replay] [★][❤][👁]

### 2.3 Unification rule (engineering)

```text
verdict = f(
  conviction.action,      // BUY|WATCH|WAIT|AVOID|NO_TOUCH
  dosVerdict().label,     // client-side heuristic
  regime.should_trade,
  earnings.in_blackout
)
// Single source returned by stock-intel.decision — UI must NOT compute 3 different actions
```

### 2.4 Drill-down from A

- Scenario table (bull/base/bear)  
- Full “why now / why not” lists  
- Agent debate summary (from Command Board API)

---

## 3. Layer B — Fundamental intelligence

### 3.1 Tab default (summary row)

| Field | Periods | Source |
|-------|---------|--------|
| Revenue growth | YoY, 3Y CAGR | v9 / yfinance |
| EPS growth | YoY | v9 |
| Gross / op / net margin | trend spark | v9 |
| FCF | trend + yield | v9 |
| Cash / debt / D/E | point | v9 |
| ROE / ROIC | point | v9 |
| P/E, Fwd P/E, EV/EBITDA, P/FCF | vs peer median | v9 + peers API |
| Valuation percentile | 5Y band | **new calc** |
| Estimate revision | 30d direction | **new** (or stub) |
| Analyst target range | low/mid/high | **new** |

### 3.2 Drill-down

| Section | Fields |
|---------|--------|
| Business model | `summary_plain`, `revenue_model`, `key_customers` |
| Segments | `segments[]: {name, pct_revenue}` |
| Geo | `geo[]: {region, pct}` |
| Key driver | `primary_driver` enum: rates/ai/commodity/ad/consumer/… |
| 10Y financials table | annual revenue, EPS, FCF, margins |
| Quality flags | dilution, buyback, accruals warning |

### 3.3 Remove / demote from default

- Raw factor chips wall → merge into `evidence.bull[]` / `evidence.bear[]`

---

## 4. Layer C — Technical / timing

### 4.1 Tab default

| Field | Source |
|-------|--------|
| Multi-TF trend | 1D/1W/1M: UP/DOWN/RANGE | **new** from chart |
| vs MA 20/50/100/200 | live_dossier.technicals | exists |
| RSI, MACD, ATR, vol ratio | exists |
| Support / resistance | exists |
| RS vs SPY % | conviction | exists |
| RS vs sector ETF | **new** |
| Pattern tag | structure.trend + VCP/base/squeeze | v9 structure + **new classifier** |
| `entry_quality_score` | 0–100 | **new** composite |
| `trend_health_score` | 0–100 | **new** |
| `technical_invalidation` | price level | trade_plan.invalidation |
| `next_trigger` | breakout level | structure |

### 4.2 Drill-down

- Full chart (existing LightweightCharts)  
- Pattern signals toggle  
- Historical analogs (with **n** and disclaimer)  
- Performance vs SPY (keep — high value)

### 4.3 Chart timeframes (add)

Default chart: 6M. Buttons: 1M · 3M · 6M · 1Y · 2Y (existing + 1M).

---

## 5. Layer D — Peer / sector comparison

### 5.1 Tab default — comparison table

**Columns:** Ticker · 1M% · 3M% · 6M% · YTD% · P/E · Rev growth · Net margin · RS vs SPY · Rev revision (arrow)

**Rows:** Subject + top 5 peers + sector ETF + SPY (benchmark)

| Field | Source |
|-------|--------|
| `peer_set` | GICS / manual map / dossier peers | extend `/api/dossier/{t}/peers` |
| `ticker_rank` | composite rank | exists (momentum only → expand) |
| `verdict` | best name / laggard / catch-up | **new rules** |

### 5.2 Drill-down

- Radar chart (valuation, growth, momentum, quality, RS)  
- “Why not peer X?” one-liner (AI optional)

### 5.3 Ranking strip (above table)

`#1 NVDA · #2 AMD · #3 INTC` — click switches dossier ticker

---

## 6. Layer E — Smart Money Intelligence

**Full spec:** [SMART_MONEY_INTELLIGENCE.md](./SMART_MONEY_INTELLIGENCE.md) — signal tiers T1–T4, 6 source types, Leader Consensus Matrix, verdict engine.

**Tab name:** `Smart Money` (5 sub-tabs + matrix + theme map)

| Sub-tab | Above fold | Drill-down |
|---------|------------|------------|
| Great Investors | tier, direction, lag, capital | 13F history |
| Insider | cluster, buy/sell ratio | Form 4 table |
| Political | warning + last disclosure | history |
| Options | LEAPS, flow grade | chain |
| Thesis Radar | T3 commentators only | sources |

**Stock verdict:** `confirmed_accumulation` \| `possible_accumulation` \| `mixed` \| `distribution` \| `no_meaningful_signal`

---

## 7. Layer F — Options / flow

### 7.1 Tab default

| Field | Source |
|-------|--------|
| `flow_quality_score` | 0–100 | radar + rules |
| `iv_rank` / `iv_percentile` | options API | Polygon or mock |
| `put_call_skew` | ratio | live/options |
| `unusual_activity` | bool + grade | conviction.options |
| `leaps_activity` | bool | **new** |
| `oi_change_5d` | % | **new** |
| `confirms_thesis` | yes/no/neutral | rules |
| Disclaimer | always visible | mock vs live provider |

### 7.2 Drill-down

- Strike/expiry heatmap  
- Block/sweep list (if Polygon)  
- Gamma zones (approx)  
- Connect existing `/api/live/options/{ticker}` — **remove disabled “Options (soon)” button**

---

## 8. Layer G — Catalyst / schedule

### 8.1 Tab default — timeline strip

| Horizon | Events |
|---------|--------|
| 7d | earnings, ex-div, macro |
| 30d | investor day, product, legal |
| 90d | guidance, regulatory |

| Field | Source |
|-------|--------|
| `next_earnings` | v9 earnings | exists |
| `eps_consensus` / `rev_consensus` | **new** |
| `in_blackout` | v9 | exists |
| `pre_event_playbook` | 1–2 bullets | rules |
| `post_event_playbook` | 1–2 bullets | rules |

### 8.2 Drill-down

- Full calendar export  
- Historical earnings surprise chart

---

## 9. Layer H — Monitoring / post-entry

**Show tab only if:** `pf.positions[ticker]` exists OR user clicks “Track thesis”.

| Tracker | Default widget | Alert examples |
|---------|----------------|----------------|
| Thesis | original bull/bear saved | thesis score drop |
| Technical health | trend_health_score | below stop, break SMA50 |
| Insider | net 30d direction | cluster sell |
| 13F | QoQ change | major trim |
| Options | skew flip | unusual put |
| Estimates | revision arrow | downgrade cluster |
| Peers | RS rank vs group | lost #1 to peer |
| Catalyst | days to earnings |进入 blackout |
| What changed | diff since `entry_date` | **new** |

### 9.1 Drill-down

- Alert rule builder  
- Journal link (decision persistence)

---

## 10. Advanced modules (phase gates)

| Module | Phase | Placement |
|--------|-------|-----------|
| Influencer / leader tracking | 2 | Ownership drill-down |
| Macro / curve linkage | 2 | Catalyst + Risk tabs |
| Sleeve / fund-fit view | 2 | Decision tab sidebar |
| IBKR execution | **1** | Execute tab |
| News clustering | 3 | Drill-down |
| Transcript AI | 3 | Drill-down |
| Social sentiment | 3 | hidden by default |

### 10.1 Sleeve fit (fields)

| Sleeve | fit_score 0–100 |
|--------|-----------------|
| growth, momentum, recovery, defensive, quality, event_driven | rules from sector + technicals + catalyst |

### 10.2 Macro linkage (fields)

`macro_drivers[]: {factor: "10Y yield", beta_hint, current_direction, supports_thesis}`

---

## 11. Layer I — Execute (IBKR) — Phase 1

| Action | API | UI |
|--------|-----|-----|
| Add watchlist | ibkr / internal | button |
| Price alert | ibkr | modal |
| Bracket draft | ibkr | pre-fill entry/stop/target from Layer A |
| Size from 1% risk | client calc | show qty |
| Paper order handoff | ibkr | **no fake fill** — staging only |

---

## 12. API design — `GET /api/v7/stock-intel/{ticker}`

### 12.1 Response shape (top-level)

```json
{
  "as_of": "ISO8601",
  "trust": { "mode": "PAPER", "data": "LIVE", "sources": [] },
  "decision": { },
  "snapshot": { },
  "fundamentals": { },
  "technicals": { },
  "peers": { },
  "ownership": { },
  "options": { },
  "catalysts": { },
  "risk": { },
  "monitor": { },
  "macro_linkage": { },
  "sleeve_fit": { },
  "execution": { "ibkr_ready": true, "suggested_qty": 0 }
}
```

### 12.2 Backend composition

| Section | Compose from |
|---------|----------------|
| decision | live_dossier + conviction + unified verdict service |
| fundamentals | v9/fundamentals + yfinance |
| technicals | live_dossier + v9/structure + live/chart summary |
| peers | dossier/peers (extended) |
| ownership | conviction + edgar |
| options | conviction + live/options |
| catalysts | v9/earnings + event_data |
| risk | live_dossier trade_plan + scenarios |
| monitor | positions store + diff engine |
| macro_linkage | regime + sector macro map |
| sleeve_fit | classifier rules |

**Cache:** 60s per ticker in `app.state.stock_intel_cache`.

---

## 13. Dashboard integration

| Surface | Integration |
|---------|-------------|
| Today / Ranked | Click ticker → `openDossier(t)` with **decision pre-loaded** |
| Command Board | Right rail peers/debate → **same** stock-intel decision |
| Positions | “Monitor” opens dossier tab H |
| Header pills | Unaffected |

---

## 14. AI usage (strict)

| Use | Output schema |
|-----|----------------|
| Bull/bear one-liner | max 120 chars each |
| Contradictions | `{claims[], conflicts[]}` |
| Why not peer X | one sentence |
| Catalyst priority | ordered list |
| **Do NOT** | price target invention, fake flow narrative |

**Endpoint:** `POST /api/v7/stock-intel/{ticker}/narrative` (optional, async, cache 1h)

---

## 15. Implementation phases

### Phase 1 — MVP (2–3 sprints) **ship decision console**

- [ ] `stock-intel` aggregator endpoint  
- [ ] Sticky Layer A (unified verdict)  
- [ ] Tab shell (9 tabs)  
- [ ] Peers table (extended API)  
- [ ] Catalyst strip (7/30/90)  
- [ ] Options tab wired (remove “soon”)  
- [ ] Execute tab (IBKR watchlist + bracket draft)  
- [ ] Remove: disabled buttons, demote factor chips  

### Phase 2 — Institutional depth

- [ ] Ownership tables + lag labels  
- [ ] Fundamentals trends + valuation band  
- [ ] Multi-TF + entry/trend scores  
- [ ] Monitor tab + thesis save  
- [ ] Sleeve fit + macro linkage  
- [ ] Leader board (curated)  

### Phase 3 — Advanced

- [ ] Influencer cluster (curated only)  
- [ ] Accumulation proxy  
- [ ] News/transcript drill-down  
- [ ] Radar charts  

---

## 16. Top 20 highest-impact additions (ordered)

1. Unified sticky decision card  
2. `stock-intel` aggregate API  
3. Peer comparison table (6 metrics × 7 rows)  
4. Catalyst 7/30/90 strip  
5. Options tab live wiring  
6. IBKR execute handoff  
7. Multi-TF trend row  
8. Entry + trend health scores  
9. Insider transaction table  
10. 13F QoQ summary  
11. Valuation vs 5Y band  
12. Business model + driver line  
13. Monitor / thesis tracker  
14. “What changed since entry”  
15. Flow quality score + disclaimer  
16. Sleeve fit chips  
17. Macro driver tags  
18. Agent debate import  
19. Structured AI bull/bear (not wall of text)  
20. Pattern tags (VCP/base/squeeze)

---

## 17. Top 10 remove or demote

1. Duplicate verdict systems  
2. Factor chips as primary UI  
3. Disabled Backtest/Options placeholders  
4. Unstructured AI essay block  
5. Analogs in default view  
6. 3M-only peer rank headline  
7. Mock options without badge  
8. Repeated S/R blocks  
9. Uncalibrated confidence without tooltip  
10. Infinite scroll without tabs  

---

## 18. File touch list (engineering)

| File | Change |
|------|--------|
| `src/api/routers/stock_intel.py` | **NEW** aggregator |
| `src/api/routers/dossier.py` | extend peers |
| `src/api/templates/index.html` | dossier tab redesign |
| `src/api/routers/conviction.py` | expose tables |
| `src/api/main.py` | include_router stock_intel |
| `tests/test_stock_intel.py` | **NEW** |

---

## 19. Acceptance criteria (PM sign-off)

- [ ] Above fold answers: action, entry, stop, catalyst, bull/bear in **<3s** scan  
- [ ] One verdict only — no conflicting BUY vs WATCH labels  
- [ ] Peer tab answers: “is this the best name in group?”  
- [ ] Options tab states mock vs live  
- [ ] Ownership shows SEC/13F lag  
- [ ] Position holders see Monitor tab with ≥3 trackers  
- [ ] IBKR handoff pre-fills bracket from decision card  
- [ ] Page load ≤2 aggregate calls (not 8+)  
- [ ] Every module has “So what” line or action implication  

---

*Document version: 1.0 · For Clarity Console Dossier upgrade · Hand to engineering.*
