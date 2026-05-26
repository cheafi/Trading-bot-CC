# CC Upgrade Blueprint v1
## 「一眼可決策」Product Surface Roadmap

> **Core Principle:** Keep CC's advanced backend — ship simpler, clearer, single-purpose surfaces.
>
> Generated: 2026-04-01 | Based on: Backend capability audit + Trading_Project-main analysis + screenshot reference

---

## Architecture Overview

```
Current Stack:
├── Backend:  FastAPI (51 endpoints, full quant engine)
├── Frontend: Alpine.js + Tailwind CSS (CDN, no build step)
├── Charts:   ⚠️ NONE currently (Chart.js cached in SW but unused)
├── Bot:      Discord.py (65+ commands)
└── PWA:      Full manifest + service worker

Upgrade Strategy:
├── Add Chart.js (already cached in SW) for all chart surfaces
├── Each new page = 1 new HTML template + 1-3 new API endpoints
├── Keep Alpine.js + Tailwind — zero build step
├── All pages follow: dark theme, mobile-first, glassmorphism cards
└── Research artifacts saved to data/reports/ (json + md + png)
```

### Charting Decision

| Library | Verdict | Why |
|---------|---------|-----|
| **Chart.js** | ✅ Use | Already cached in SW, lightweight, good for bar/line/scatter/heatmap |
| Plotly | ❌ Skip | Too heavy for mobile PWA, overkill for dashboard charts |
| Lightweight Charts | ❌ Skip | Great for candlestick but CC doesn't need real-time tick charts |
| D3 | ❌ Skip | Too low-level, unnecessary complexity |

### Shared Component Pattern

Every new page follows this template:

```html
<!-- Template: src/api/templates/{page_name}.html -->
<!-- CSS: Tailwind CDN + shared dark tokens (copy from index.html) -->
<!-- JS: Alpine.js + Chart.js CDN -->
<!-- Data: fetch('/api/v7/{endpoint}') every N seconds -->
<!-- Nav: Back to Dashboard link + page title -->
<!-- Layout: 2-4 fixed zones, no scroll-to-find -->
```

---

## P0: Highest Priority (Ship First)

---

### Page 1: Regime Screener

> **One screen = one decision.** Answer: "What should I trade today and why?"

#### User Goal
Open this page → immediately know: regime, which strategies are ON, ranked candidates, pick one → see entry/SL/TP/chart → decide.

#### Data Sources (Already Built)

| Data | Source | File | Lines |
|------|--------|------|-------|
| Regime state | `get_regime_data()` | `src/api/main.py` | 219-260 |
| Scoreboard | `/api/v6/scoreboard` | `src/api/main.py` | 1919-2029 |
| Risk budget | `PortfolioRiskBudget` | `src/engines/portfolio_risk_budget.py` | 1-392 |
| Strategy status | `StrategyLeaderboard` | `src/engines/strategy_leaderboard.py` | 1-371 |
| Signal validation | `GPTSignalValidator` | `src/engines/gpt_validator.py` | 1-500 |
| Price data | `/api/data/prices` | `src/api/main.py` | ~800 |

#### New API Endpoints

```
GET /api/v7/regime-screener
Response:
{
  "regime": {
    "risk":  "RISK_ON" | "RISK_OFF" | "NEUTRAL",
    "trend": "UPTREND" | "DOWNTREND" | "NEUTRAL",
    "vol":   "HIGH_VOL" | "LOW_VOL" | "NORMAL",
    "label": "Bullish Momentum",        // human-readable
    "active_engine": "trend_following",  // primary engine for this regime
    "risk_budget": { "max_gross": 0.80, "max_single": 0.05 }
  },
  "candidates": [
    {
      "rank": 1,
      "ticker": "NVDA",
      "engine": "momentum",
      "score": 0.87,
      "direction": "LONG",
      "entry": 142.50,
      "stop": 136.80,
      "tp1": 152.00,
      "tp2": 165.00,
      "rr": 2.4,
      "confidence": 0.82,
      "ev": 0.38,
      "why": "Breakout above 50d MA on 2x volume, RSI 62",
      "risks": ["Earnings in 12 days", "Sector rotation risk"]
    }
  ],
  "universe_size": 500,
  "candidate_count": 12,
  "generated_at": "2026-04-01T09:30:00Z"
}

GET /api/v7/regime-screener/detail/{ticker}
Response:
{
  "ticker": "NVDA",
  "price_data": { /* OHLCV last 200 bars */ },
  "indicators": {
    "rsi": 62, "sma20": 138.5, "sma50": 132.1, "sma200": 118.4,
    "volume_ratio": 2.1, "atr": 4.2, "beta": 1.45
  },
  "signal": { /* full signal card from v6 */ },
  "sector": "Technology",
  "market_cap": "3.2T",
  "regime_at_signal": "RISK_ON + UPTREND + NORMAL"
}

GET /api/v7/regime-screener/history
Response:
{
  "dates": ["2026-03-31", "2026-03-28", ...],
  "regimes": [
    {"date": "2026-03-31", "risk": "RISK_ON", "trend": "UPTREND", ...}
  ]
}
```

#### UI Layout (4 Fixed Zones)

```
┌─────────────────────────────────────────────────────────┐
│  ZONE 1: Regime Banner                                  │
│  ┌──────────┐ ┌──────────┐ ┌───────────┐ ┌───────────┐ │
│  │ Regime:  │ │ Engine:  │ │ Universe: │ │Candidates:│ │
│  │ RISK_ON  │ │ Momentum │ │    500    │ │    12     │ │
│  │ 🟢       │ │ 🟢 Active│ │           │ │           │ │
│  └──────────┘ └──────────┘ └───────────┘ └───────────┘ │
│  Risk Budget: ████████░░ 80% gross | Max single: 5%    │
├─────────────────────────────────────────────────────────┤
│  ZONE 2: Ranked Candidates Table                        │
│  ┌────┬───────┬────────┬───────┬──────┬────┬────┬─────┐ │
│  │Rank│Ticker │Engine  │ Score │Entry │ SL │ TP │ R:R │ │
│  ├────┼───────┼────────┼───────┼──────┼────┼────┼─────┤ │
│  │ 1  │ NVDA  │momentum│ 0.87  │142.5 │136 │152 │ 2.4 │ │
│  │ 2  │ AAPL  │trend   │ 0.81  │178.2 │171 │190 │ 2.1 │ │
│  │ 3  │ META  │breakout│ 0.76  │515.0 │498 │545 │ 1.8 │ │
│  └────┴───────┴────────┴───────┴──────┴────┴────┴─────┘ │
│  (click row to load detail →)                           │
├──────────────────────────┬──────────────────────────────┤
│  ZONE 3: Ticker Detail   │  ZONE 4: Chart              │
│  NVDA                    │  ┌────────────────────────┐  │
│  Price: $142.50 (+2.3%)  │  │  📈 Price + SMA20/50   │  │
│  RSI: 62                 │  │     + Volume bars       │  │
│  Volume: 2.1x avg        │  │     + Entry/SL/TP      │  │
│  Beta: 1.45              │  │     horizontal lines    │  │
│  Sector: Technology      │  │                        │  │
│  ──────────────────      │  │                        │  │
│  Why: Breakout above     │  │                        │  │
│  50d MA on 2x volume     │  └────────────────────────┘  │
│  ──────────────────      │                              │
│  Risks:                  │  [Screener] [Background]     │
│  • Earnings in 12 days   │  [Historical Regimes]        │
│  • Sector rotation       │                              │
└──────────────────────────┴──────────────────────────────┘

Tabs at bottom: [Screener Result] [Background] [Historical Regimes]
```

#### Route & Template

```python
# src/api/main.py — new route
@app.get("/regime-screener", response_class=HTMLResponse)
async def regime_screener_page(request: Request):
    return templates.TemplateResponse("regime_screener.html", {"request": request})

# Template: src/api/templates/regime_screener.html
# Alpine.js x-data component fetches /api/v7/regime-screener every 60s
# Chart.js line chart for Zone 4, updated on ticker click
```

#### Backend Implementation

```python
# src/api/main.py — new endpoint
@app.get("/api/v7/regime-screener")
async def regime_screener():
    # 1. Get regime from existing scoreboard logic (lines 1919-2029)
    regime = get_regime_data()  # existing function
    
    # 2. Get active strategies from leaderboard
    active = strategy_leaderboard.active_strategies()
    
    # 3. Get latest signals filtered by active strategies
    signals = [s for s in recent_signals if s.strategy in active]
    
    # 4. Rank by composite score (confidence * EV * regime_alignment)
    ranked = sorted(signals, key=lambda s: s.composite_score, reverse=True)
    
    # 5. Get risk budget
    budget = portfolio_risk_budget.current_exposure()
    
    return {
        "regime": regime,
        "candidates": [format_candidate(s) for s in ranked[:20]],
        "universe_size": len(universe),
        "candidate_count": len(ranked),
        "generated_at": datetime.utcnow().isoformat()
    }
```

#### Priority & Effort

| Aspect | Estimate |
|--------|----------|
| New code | ~400 lines (template) + ~150 lines (API) |
| Backend work | Minimal — compose existing functions |
| Chart.js integration | First chart page — establish pattern |
| Mobile layout | 4 zones stack vertically |
| **Effort** | **2-3 days** |

---

### Page 2: Portfolio Brief

> **Aggregated intelligence, not just alerts.** Answer: "What's happening in my portfolio right now?"

#### User Goal
Daily morning → open brief → know: which holdings moved, why, what to watch, sector story, no-change summary, follow-up questions.

#### Data Sources (Already Built)

| Data | Source | File |
|------|--------|------|
| Trade brief narrative | `generate_trade_brief()` | `src/engines/gpt_validator.py:986-1044` |
| Deterministic memo | `_build_deterministic_memo()` | `src/engines/gpt_validator.py:1046-1065` |
| Portfolio positions | `/api/broker/positions` | `src/api/main.py` |
| Price changes | `/api/data/prices` | `src/api/main.py` |
| Signal history | `/api/signals` | `src/api/main.py` |
| Sector scanner | `/api/scan/sectors` | `src/api/main.py` |

#### New API Endpoints

```
GET /api/v7/portfolio-brief
Query: ?date=2026-04-01 (optional, default=today)
Response:
{
  "date": "2026-04-01",
  "headline": "5 個持倉有訊號觸發",
  "portfolio_story": "半導體板塊群起...",
  
  "holdings_with_signals": [
    {
      "ticker": "NVDA",
      "change_pct": 6.9,
      "signal_type": "momentum_breakout",
      "note": "大幅波動",
      "indicators": { "rsi": 72, "above_ma20": true, "above_ma50": true }
    }
  ],
  
  "holdings_no_signal": [
    {
      "ticker": "SOFI",
      "change_pct": 0.3,
      "note": "RSI 34 進入低值 — 看看多頭反轉條件",
      "watch_reason": "near_oversold"
    }
  ],
  
  "sector_clustering": {
    "semiconductor": {
      "tickers": ["NVDA", "MU", "CRDO"],
      "avg_change": 5.7,
      "narrative": "同時大漲 5-7%，疑似 AI 次主題"
    }
  },
  
  "top_catalysts": [
    "GTC 大會本週開始 — 記憶體+AI 基礎設施直接受益",
    "Q2 earnings 3/18 — 市場提前反應"
  ],
  
  "no_change_summary": "其餘 28 隻 watchlist 無重大變化",
  
  "follow_up_prompts": [
    "SOFI RSI 低值代表什麼？",
    "半導體群起是否 sector rotation？",
    "NVDA 大漲後應否加倉？"
  ],
  
  "generated_at": "2026-04-01T04:30:00Z"
}

GET /api/v7/watchlist-brief
# Same structure but for watchlist instead of holdings

GET /api/v7/why-moved/{ticker}
Response:
{
  "ticker": "MU",
  "change_pct": 5.1,
  "reasons": [
    { "source": "news", "text": "Top Analysts Raise Price Targets to $500" },
    { "source": "event", "text": "GTC 大會本週" },
    { "source": "technical", "text": "突破 MA20 + MA50 阻力" },
    { "source": "flow", "text": "Stock Titan: Micron buys Taiwan chip" }
  ],
  "signal_status": "LONG active since 2026-03-14",
  "confidence": 0.78
}
```

#### Artifact Output

```
data/brief-YYYY-MM-DD.md        — daily brief in markdown
data/brief-YYYY-MM-DD.json      — structured data
data/brief-YYYY-MM-DD-card.png  — shareable card (future P2)
```

#### Auto-generation

```python
# Add to scheduler / daily job
async def generate_daily_brief():
    """Run at 04:30 UTC (before US pre-market)"""
    brief = await build_portfolio_brief()
    
    # Save artifacts
    date_str = datetime.utcnow().strftime('%Y-%m-%d')
    save_json(f"data/brief-{date_str}.json", brief)
    save_markdown(f"data/brief-{date_str}.md", format_brief_md(brief))
    
    # Push to Discord
    await discord_bot.send_daily_brief(brief)
```

#### UI Layout

```
┌─────────────────────────────────────────────────────────┐
│  Portfolio 速報 2026-04-01                  [📅 Date ▼] │
│  "5 個持倉有訊號觸發"                                    │
├─────────────────────────────────────────────────────────┤
│  📈 Holdings with Signals                               │
│  ┌─────────────────────────────────────────────────────┐ │
│  │ ✦ NVDA +6.9% — 大幅波動  │ above MA20/MA50        │ │
│  │ ✦ MU  +5.1% — MA20突破   │ above MA20/MA50        │ │
│  │ ✦ CRDO+4.5% — 大幅波動   │ above MA20/MA50        │ │
│  └─────────────────────────────────────────────────────┘ │
├─────────────────────────────────────────────────────────┤
│  🏭 Sector Clustering                                   │
│  半導體: NVDA MU CRDO 同時大漲 5-7%                       │
│  疑似 AI 基礎設施主題驅動                                  │
├─────────────────────────────────────────────────────────┤
│  🔥 Top Catalysts                                       │
│  • GTC 大會本週 — 記憶體+AI 直接受益                       │
│  • Q2 earnings approaching                              │
├─────────────────────────────────────────────────────────┤
│  👁 Watch (no signal but notable)                        │
│  ✦ SOFI +0.3% — RSI 34 低值，看看反轉條件                 │
├─────────────────────────────────────────────────────────┤
│  ✅ No Change: 其餘 28 隻無重大變化                        │
├─────────────────────────────────────────────────────────┤
│  ❓ Follow-up Questions                                  │
│  [SOFI RSI 代表什麼？] [半導體是否 rotation？] [加倉？]     │
│  → Click any → calls /api/v7/why-moved/{ticker}          │
└─────────────────────────────────────────────────────────┘
```

#### Priority & Effort

| Aspect | Estimate |
|--------|----------|
| New code | ~350 lines (template) + ~200 lines (API + brief builder) |
| GPT integration | Reuse `MorningMemoComposer` with new aggregation prompt |
| Artifact output | ~50 lines (json/md writer) |
| Daily scheduler | ~30 lines |
| **Effort** | **2-3 days** |

---

### Page 3: Compare Overlay

> **Chart-based comparison, not just numbers.** Answer: "How does A compare to B visually?"

#### User Goal
Pick 2+ tickers → see normalized return chart (base=100) + relative strength + correlation. Replace current text-only `/compare`.

#### Data Sources (Already Built)

| Data | Source |
|------|--------|
| Price history | `/api/data/prices/{ticker}` |
| Performance analytics | `PerformanceAnalytics.compare_strategies()` |
| Correlation | `PerformanceAnalytics` — rolling window |

#### New API Endpoint

```
GET /api/v7/compare-overlay
Query: ?tickers=NVDA,AMD,SPY&period=6m&mode=normalized
Response:
{
  "mode": "normalized",  // normalized | relative_strength | correlation
  "base_date": "2025-10-01",
  "series": {
    "NVDA": [100, 101.2, 99.8, ...],  // daily normalized values
    "AMD":  [100, 98.5, 102.3, ...],
    "SPY":  [100, 100.3, 100.1, ...]
  },
  "dates": ["2025-10-01", "2025-10-02", ...],
  "stats": {
    "NVDA": { "total_return": 42.3, "sharpe": 1.8, "max_dd": -15.2, "beta_vs_spy": 1.45, "corr_vs_spy": 0.72 },
    "AMD":  { "total_return": 28.1, "sharpe": 1.2, "max_dd": -22.1, "beta_vs_spy": 1.62, "corr_vs_spy": 0.68 }
  },
  "correlation_matrix": {
    "NVDA-AMD": 0.81,
    "NVDA-SPY": 0.72,
    "AMD-SPY":  0.68
  }
}
```

#### 3 Modes

| Mode | Chart Type | X-axis | Y-axis |
|------|-----------|--------|--------|
| **Normalized Return** | Multi-line | Date | Base=100 |
| **Relative Strength** | Line | Date | A/B ratio |
| **Correlation/Beta** | Scatter + stats | A returns | B returns |

#### UI Layout

```
┌─────────────────────────────────────────────────────────┐
│  Compare Overlay                                        │
│  Tickers: [NVDA] [AMD] [SPY] [+ Add]  Period: [6M ▼]  │
│  Mode: [Normalized ●] [Relative Strength] [Correlation] │
├─────────────────────────────────────────────────────────┤
│  ┌─────────────────────────────────────────────────────┐ │
│  │                                                     │ │
│  │   📈 Chart.js multi-line chart                      │ │
│  │      NVDA ━━ green                                  │ │
│  │      AMD  ━━ blue                                   │ │
│  │      SPY  ━━ gray (benchmark)                       │ │
│  │                                                     │ │
│  │   Y: 80  90  100  110  120  130  140                │ │
│  │   X: Oct  Nov  Dec  Jan  Feb  Mar  Apr              │ │
│  │                                                     │ │
│  └─────────────────────────────────────────────────────┘ │
├─────────────────────────────────────────────────────────┤
│  Stats Comparison                                       │
│  ┌──────────┬────────┬────────┬────────┐                │
│  │          │  NVDA  │  AMD   │  SPY   │                │
│  ├──────────┼────────┼────────┼────────┤                │
│  │ Return   │ +42.3% │ +28.1% │ +12.5% │                │
│  │ Sharpe   │  1.80  │  1.20  │  0.95  │                │
│  │ Max DD   │ -15.2% │ -22.1% │ -8.3%  │                │
│  │ Beta     │  1.45  │  1.62  │  1.00  │                │
│  │ Corr/SPY │  0.72  │  0.68  │  1.00  │                │
│  └──────────┴────────┴────────┴────────┘                │
└─────────────────────────────────────────────────────────┘
```

#### Discord Upgrade

```python
# Upgrade /compare in discord_bot.py (line ~4491)
# After building text embed, also:
# 1. Call /api/v7/compare-overlay
# 2. Generate Chart.js chart server-side → save PNG
# 3. Attach PNG to Discord embed
```

#### Priority & Effort

| Aspect | Estimate |
|--------|----------|
| New code | ~300 lines (template) + ~120 lines (API) |
| Chart.js | Multi-line chart with legend, tooltips |
| Server-side chart | Optional — matplotlib/plotly for Discord PNG |
| **Effort** | **1-2 days** |

---

## P1: Medium-High ROI

---

### Page 4: Options Lab

> **Research-grade options surface.** Answer: "What's the best options expression for this idea?"

#### User Goal
Enter ticker + view → see ranked contracts, EV/liquidity scatter, IV term structure, skew warnings, earnings proximity.

#### Data Sources (Already Built)

| Data | Source | File |
|------|--------|------|
| Expression decision | `ExpressionEngine.evaluate()` | `src/engines/expression_engine.py:72-180` |
| IV thresholds | `CHEAP_IV_THRESHOLD`, etc. | `src/engines/expression_engine.py:18-24` |
| Options gates | 4-gate check | `src/engines/expression_engine.py:85-115` |

#### New API Endpoints

```
GET /api/v7/options-screen
Query: ?ticker=MSFT&strategy=long_call
Response:
{
  "ticker": "MSFT",
  "spot_price": 405.54,
  "expression_decision": "long_call",
  "expression_reason": "IV percentile 37% < 40% threshold, confidence 0.82",
  
  "market_context": {
    "iv_rank": 37,
    "iv_percentile": 37,
    "skew": 0.009,  // positive = call-favored
    "days_to_earnings": 52,
    "ex_dividend_days": 73,
    "high_iv_warning": false,
    "earnings_proximity_warning": false
  },
  
  "contracts": [
    {
      "rank": 1,
      "strike": 490,
      "expiry": "2027-03-19",
      "dte": 718,
      "delta": 0.38,
      "mid": 25.15,
      "oi": 752,
      "spread_pct": 1.2,
      "ev": 0.94,
      "breakeven": 515.15,
      "breakeven_pct": 27.0,
      "max_loss": 2515
    }
  ],
  
  "why_this_expression": {
    "chosen": "Long Call",
    "not_stock": "Leverage ratio 3.2x more capital efficient",
    "not_spread": "IV is cheap — no need to sell premium",
    "no_trade_conditions": ["OI < 500", "Spread > 5%", "DTE < 30"]
  },
  
  "generated_at": "2026-04-01T14:30:00Z"
}

GET /api/v7/options-screen/iv-term
Query: ?ticker=MSFT
Response:
{
  "ticker": "MSFT",
  "term_structure": [
    { "dte": 30, "iv": 0.22 },
    { "dte": 60, "iv": 0.24 },
    { "dte": 90, "iv": 0.26 },
    { "dte": 180, "iv": 0.28 },
    { "dte": 365, "iv": 0.31 }
  ]
}

GET /api/v7/leaps
Query: ?ticker=MSFT
# Returns LEAPS-specific contracts (DTE >= 365)
```

#### UI Layout (4 Zones)

```
┌─────────────────────────────────────────────────────────┐
│  Options Lab: MSFT          [Search: ________] [Go]     │
│  Strategy: [Long Call ▼]    Spot: $405.54               │
├──────────────────────────┬──────────────────────────────┤
│  ZONE 1: Market Context  │  ZONE 2: Contract Ranking   │
│  IV Rank: 37% (cheap)    │  ┌────┬──────┬─────┬──────┐ │
│  Skew: +0.009 (neutral)  │  │Rank│Strike│Delta│  EV  │ │
│  Earnings: 52 days       │  │ 1  │ $490 │ 0.38│ 0.94 │ │
│  Ex-Div: 73 days         │  │ 2  │ $500 │ 0.36│ 0.88 │ │
│  ⚠️ None                 │  │ 3  │ $480 │ 0.42│ 0.82 │ │
│                          │  └────┴──────┴─────┴──────┘ │
│  Expression: LONG CALL   │                              │
│  Why: IV cheap, high conf│                              │
├──────────────────────────┼──────────────────────────────┤
│  ZONE 3: EV vs Liquidity │  ZONE 4: IV Term Structure  │
│  ┌──────────────────┐    │  ┌──────────────────────┐    │
│  │  Scatter chart    │    │  │  Line chart           │    │
│  │  X: Liquidity     │    │  │  X: DTE               │    │
│  │  Y: Expected Value│    │  │  Y: Implied Vol       │    │
│  │  Color: Delta     │    │  │                      │    │
│  │  Size: OI         │    │  │  Normal / Inverted   │    │
│  └──────────────────┘    │  │  / Humped indicator   │    │
│                          │  └──────────────────────┘    │
├──────────────────────────┴──────────────────────────────┤
│  Explainability Panel                                   │
│  ✅ Why Long Call: IV cheap (37% < 40%), confidence 82% │
│  ❌ Why not Stock: Leverage 3.2x more efficient         │
│  ❌ Why not Spread: No need to sell premium (IV cheap)   │
│  ⛔ No-trade if: OI<500, Spread>5%, DTE<30              │
└─────────────────────────────────────────────────────────┘
```

#### Priority & Effort

| Aspect | Estimate |
|--------|----------|
| New code | ~450 lines (template) + ~250 lines (API + options data) |
| External data | Need options chain data source (yfinance/CBOE/broker) |
| Chart.js | Scatter + Line charts |
| **Effort** | **3-4 days** |
| **Dependency** | Options chain data feed |

---

### Page 5: Performance Lab

> **FinLab-style KPI presentation.** Answer: "How well is the system actually performing?"

#### User Goal
See track record: equity curve, monthly heatmap, drawdown history, alpha/beta, risk metrics — distinguish backtest vs paper vs live.

#### Data Sources (Already Built)

| Data | Source | File |
|------|--------|------|
| KPIs | `ProfessionalKPIDashboard` | `src/engines/professional_kpi.py:1-315` |
| Backtester | `EnhancedBacktester` | `src/backtest/enhanced_backtester.py:1-1366` |
| Analytics | `PerformanceAnalytics` | `src/performance/analytics.py:1-402` |
| Drawdowns | `DrawdownPeriod` | `src/performance/analytics.py` |

#### New API Endpoint

```
GET /api/v7/performance-lab
Query: ?strategy=all&source=live&period=1y
Response:
{
  "summary": {
    "annual_return": 41.5,
    "alpha": 35.8,
    "beta": 0.36,
    "sharpe": 2.1,
    "sortino": 3.4,
    "calmar": 2.8,
    "max_drawdown": -14.2,
    "win_rate": 0.64,
    "profit_factor": 2.3,
    "var_95": -2.1,
    "cvar_95": -3.4,
    "source": "live",  // backtest | paper | live
    "gross_or_net": "net"
  },
  
  "equity_curve": {
    "dates": ["2025-04-01", ...],
    "values": [100, 101.2, ...],
    "benchmark": [100, 100.3, ...]  // SPY
  },
  
  "monthly_returns": {
    "2025": { "Jan": 3.2, "Feb": -1.1, "Mar": 5.4, ... },
    "2026": { "Jan": 2.8, "Feb": 4.1, "Mar": 3.9 }
  },
  
  "annual_returns": [
    { "year": 2025, "return": 38.2, "benchmark": 12.1, "alpha": 26.1 }
  ],
  
  "drawdowns": [
    { "start": "2025-08-01", "trough": "2025-08-15", 
      "recovery": "2025-09-02", "depth": -14.2, "days": 32 }
  ],
  
  "win_loss_distribution": {
    "bins": [-10, -8, -6, -4, -2, 0, 2, 4, 6, 8, 10, 12, 14],
    "counts": [1, 2, 5, 8, 12, 0, 15, 10, 7, 4, 2, 1]
  },
  
  "holding_period": {
    "avg_hours": 72,
    "median_hours": 48,
    "distribution": { "< 1d": 15, "1-3d": 35, "3-7d": 30, "7-14d": 15, "> 14d": 5 }
  }
}
```

#### UI Layout (Tabbed)

```
┌─────────────────────────────────────────────────────────┐
│  Performance Lab                                        │
│  Source: [Live ●] [Paper] [Backtest]                    │
│  Strategy: [All ▼]   Period: [1Y ▼]                    │
├─────────────────────────────────────────────────────────┤
│  KPI Banner                                             │
│  ┌────────┐ ┌────────┐ ┌────────┐ ┌────────┐ ┌───────┐ │
│  │Annual  │ │ Alpha  │ │ Beta   │ │Sharpe  │ │ MDD   │ │
│  │+41.5%  │ │+35.8%  │ │ 0.36  │ │ 2.10   │ │-14.2% │ │
│  └────────┘ └────────┘ └────────┘ └────────┘ └───────┘ │
├─────────────────────────────────────────────────────────┤
│  Tabs: [Equity] [Monthly] [Annual] [Drawdowns]          │
│        [Risk] [Distribution] [Holdings]                 │
│                                                         │
│  [Equity Tab — Default]                                 │
│  ┌─────────────────────────────────────────────────────┐ │
│  │   📈 Equity curve (blue) vs SPY (gray)              │ │
│  │   Cumulative return, log or linear scale toggle     │ │
│  │   Shaded drawdown regions                           │ │
│  └─────────────────────────────────────────────────────┘ │
│                                                         │
│  [Monthly Tab]                                          │
│  ┌─────────────────────────────────────────────────────┐ │
│  │   Heatmap: rows=years, cols=months                  │ │
│  │   Green=positive, Red=negative                      │ │
│  │   Color intensity = magnitude                       │ │
│  └─────────────────────────────────────────────────────┘ │
│                                                         │
│  [Risk Tab]                                             │
│  VaR-95: -2.1%  |  CVaR-95: -3.4%  |  Vol: 12.3%      │
│  Sortino: 3.4   |  Calmar: 2.8     |  Info Ratio: 2.1  │
└─────────────────────────────────────────────────────────┘
```

#### Priority & Effort

| Aspect | Estimate |
|--------|----------|
| New code | ~600 lines (template, most complex page) + ~200 lines (API) |
| Chart.js | Line (equity), heatmap (monthly), bar (annual/distribution) |
| Data source distinction | Must clearly label backtest vs paper vs live |
| **Effort** | **3-4 days** |

---

### Page 6: Strategy Portfolio Lab

> **Multi-strategy allocation optimizer.** Answer: "How should I combine my strategies?"

#### User Goal
See all strategies side-by-side → correlation matrix → optimal weights → regime-specific allocation → combined equity curve.

#### Data Sources (Already Built)

| Data | Source | File |
|------|--------|------|
| Strategy metrics | `StrategyLeaderboard` | `src/engines/strategy_leaderboard.py` |
| Analytics | `PerformanceAnalytics.compare_strategies()` | `src/performance/analytics.py` |
| Risk budget | `PortfolioRiskBudget` | `src/engines/portfolio_risk_budget.py` |
| Regime state | Scoreboard | `src/api/main.py:1919-2029` |

#### New API Endpoints

```
GET /api/v7/strategy-portfolio
Response:
{
  "strategies": [
    {
      "name": "Momentum v1.0",
      "sharpe": 2.85,
      "cagr": 42.2,
      "mdd": -13.0,
      "turnover": 1.2,
      "style": "動量突破 + 大盤趨勢",
      "status": "ACTIVE"
    },
    // ... 6 strategies
  ],
  
  "correlation_matrix": {
    "labels": ["Momentum", "Dual-Factor", "High Yield", "Sector Focus", "Small Cap", "Event"],
    "values": [
      [1.00, 0.45, 0.32, 0.28, 0.51, 0.15],
      [0.45, 1.00, 0.38, 0.42, 0.33, 0.22],
      // ...
    ]
  },
  
  "optimizations": {
    "equal_weight":    { "weights": [0.167, 0.167, 0.167, 0.167, 0.167, 0.167], "sharpe": 1.91, "cagr": 37.4, "mdd": -13.0 },
    "max_sharpe":      { "weights": [0.30, 0.25, 0.20, 0.10, 0.10, 0.05], "sharpe": 2.45, "cagr": 41.5, "mdd": -11.2 },
    "risk_parity":     { "weights": [0.18, 0.22, 0.15, 0.12, 0.18, 0.15], "sharpe": 2.12, "cagr": 38.8, "mdd": -10.5 },
    "min_variance":    { "weights": [0.15, 0.20, 0.25, 0.15, 0.10, 0.15], "sharpe": 1.85, "cagr": 34.2, "mdd": -9.1 },
    "min_mdd":         { "weights": [0.20, 0.15, 0.20, 0.20, 0.10, 0.15], "sharpe": 1.95, "cagr": 35.5, "mdd": -8.8 }
  },
  
  "regime_weights": {
    "RISK_ON + UPTREND": { "weights": [0.35, 0.25, 0.15, 0.10, 0.10, 0.05] },
    "RISK_OFF + DOWNTREND": { "weights": [0.05, 0.10, 0.30, 0.20, 0.05, 0.30] }
  },
  
  "portfolio_equity_curve": {
    "dates": ["2024-01-01", ...],
    "strategies": { "Momentum": [100, ...], "Dual-Factor": [100, ...] },
    "combined": [100, 103.2, ...]
  }
}
```

#### UI Layout

```
┌─────────────────────────────────────────────────────────┐
│  Strategy Portfolio Lab                                 │
│  Optimization: [Max Sharpe ▼]  Regime: [Current ▼]     │
├─────────────────────────────────────────────────────────┤
│  Strategy Overview Table                                │
│  ┌────┬──────────────┬───────┬──────┬──────┬──────────┐ │
│  │ #  │ Strategy     │Sharpe │ CAGR │ MDD  │ Style    │ │
│  │ 1  │ Momentum 1.0 │ 2.85  │42.2% │-13.0%│ 動量突破 │ │
│  │ 2  │ Dual-Factor  │ 2.31  │56.7% │-13.5%│ 多因子  │ │
│  │ 3  │ High Yield   │ 2.49  │39.8% │-14.8%│ 價值+   │ │
│  └────┴──────────────┴───────┴──────┴──────┴──────────┘ │
├──────────────────────────┬──────────────────────────────┤
│  Correlation Heatmap     │  Optimal Weights Pie/Bar     │
│  ┌──────────────────┐    │  ┌──────────────────────┐    │
│  │  6×6 heatmap     │    │  │  Doughnut chart       │    │
│  │  green=low corr  │    │  │  Momentum: 30%       │    │
│  │  red=high corr   │    │  │  Dual-Factor: 25%    │    │
│  └──────────────────┘    │  │  High Yield: 20%     │    │
│                          │  └──────────────────────┘    │
├──────────────────────────┴──────────────────────────────┤
│  Combined Equity Curve                                  │
│  ┌─────────────────────────────────────────────────────┐ │
│  │  Individual strategies (thin) + Combined (thick)    │ │
│  │  Toggle strategies on/off                           │ │
│  └─────────────────────────────────────────────────────┘ │
├─────────────────────────────────────────────────────────┤
│  Optimization Comparison                                │
│  ┌────────────┬───────┬──────┬──────┐                   │
│  │ Method     │Sharpe │ CAGR │ MDD  │                   │
│  │ Equal Wt   │ 1.91  │37.4% │-13.0%│                   │
│  │ Max Sharpe │ 2.45  │41.5% │-11.2%│ ← recommended    │
│  │ Risk Parity│ 2.12  │38.8% │-10.5%│                   │
│  │ Min Var    │ 1.85  │34.2% │ -9.1%│                   │
│  │ Min MDD    │ 1.95  │35.5% │ -8.8%│                   │
│  └────────────┴───────┴──────┴──────┘                   │
└─────────────────────────────────────────────────────────┘
```

#### New Backend Module

```python
# src/engines/strategy_portfolio_optimizer.py (NEW)
class StrategyPortfolioOptimizer:
    """Multi-strategy portfolio optimization using existing analytics."""
    
    def optimize(self, strategies: list, method: str) -> dict:
        """
        Methods: equal_weight, max_sharpe, risk_parity, 
                 min_variance, min_mdd, regime_based
        
        Uses:
        - PerformanceAnalytics for return series + correlation
        - scipy.optimize.minimize for weight optimization
        - StrategyLeaderboard for strategy health gating
        """
    
    def regime_mix(self, regime: str) -> dict:
        """Adjust weights based on current regime state."""
    
    def attribution(self, weights: list) -> dict:
        """Return-attribution by strategy sleeve."""
```

#### Priority & Effort

| Aspect | Estimate |
|--------|----------|
| New code | ~400 lines (template) + ~300 lines (optimizer) + ~100 lines (API) |
| Math | scipy for optimization (already likely in env) |
| Chart.js | Heatmap, doughnut, multi-line |
| **Effort** | **3-5 days** |

---

## P2: Productization & Branding

---

### Page 7: Shareable Cards

> **Every insight → one image.** For Discord, social media, audit trail.

#### Card Types

| Card | Content | Size |
|------|---------|------|
| Daily Brief Card | Regime + top 3 signals + portfolio summary | 1200×630 |
| Regime Screener Card | Regime + candidates table + top pick | 1200×630 |
| Options Idea Card | Ticker + expression + top 3 contracts | 1200×630 |
| Performance Card | Equity curve + KPI row + monthly mini-heatmap | 1200×630 |
| Signal Card | Single signal with entry/SL/TP + chart mini | 800×418 |
| Drawdown Card | MDD history + current drawdown | 1200×630 |

#### Implementation

```python
# src/reports/card_generator.py (NEW)
# Uses matplotlib or Pillow for server-side rendering
# Template: dark background, CC branding, fixed layout

class CardGenerator:
    def daily_brief_card(self, brief: dict) -> bytes:  # PNG
    def regime_card(self, screener: dict) -> bytes:
    def options_card(self, screen: dict) -> bytes:
    def performance_card(self, perf: dict) -> bytes:
    def signal_card(self, signal: dict) -> bytes:
    
    def save(self, card: bytes, path: str):
        """Save to data/cards/YYYY-MM-DD/{type}.png"""
```

#### Effort: 2-3 days

---

### Page 8: Artifact Archive

> **Every research output → saved, searchable, replayable, auditable.**

#### Directory Structure

```
data/
├── reports/
│   ├── daily/
│   │   ├── 2026-04-01/
│   │   │   ├── brief.json
│   │   │   ├── brief.md
│   │   │   ├── brief-card.png
│   │   │   ├── regime.json
│   │   │   └── signals.json
│   │   └── 2026-03-31/
│   ├── options/
│   │   ├── msft-2026-04-01/
│   │   │   ├── screen.json
│   │   │   ├── screen.csv
│   │   │   ├── ev-scatter.png
│   │   │   ├── iv-term.png
│   │   │   └── summary.md
│   ├── performance/
│   │   ├── monthly/
│   │   │   ├── 2026-03.json
│   │   │   ├── 2026-03-equity.png
│   │   │   └── 2026-03-heatmap.png
│   │   └── quarterly/
│   └── compare/
│       └── nvda-vs-amd-2026-04-01/
├── cards/
│   ├── 2026-04-01/
│   │   ├── daily-brief.png
│   │   ├── regime-screener.png
│   │   └── performance.png
```

#### API

```
GET /api/v7/artifacts
Query: ?type=daily&date=2026-04-01
Response: { "files": [...], "download_url": "..." }

GET /api/v7/artifacts/compare
Query: ?date1=2026-04-01&date2=2026-03-31&type=daily
Response: { "diff": {...} }
```

#### Implementation

```python
# src/reports/artifact_manager.py (NEW)
class ArtifactManager:
    base_dir = "data/reports"
    
    def save(self, category: str, name: str, data: dict, formats: list):
        """Save artifact in multiple formats: json, csv, md, png"""
    
    def load(self, category: str, name: str, format: str):
        """Load a saved artifact"""
    
    def list(self, category: str, date_range: tuple):
        """List available artifacts"""
    
    def compare(self, artifact_a: str, artifact_b: str):
        """Diff two artifacts"""
```

#### Effort: 2 days

---

## Signal Explorer Upgrade (Bonus)

> Current signal_explorer.html uses **hardcoded sample data**. Upgrade to real API integration + lifecycle tracking.

#### Enhanced Signal Fields

```json
{
  "id": "sig_20260401_001",
  "ticker": "NVDA",
  "status": "ACTIVE",           // Triggered → Approved/Conditional/Rejected → Active → TP/SL/TimeStop/Expired/Cancelled
  "days_open": 3,
  "current_pl_pct": 4.2,
  "current_pl_r": 1.1,
  "exit_reason": null,          // tp_hit | sl_hit | time_stop | expired | cancelled
  "regime_at_entry": "RISK_ON + UPTREND",
  "confidence_at_entry": 0.82,
  "realized_vs_expected_r": null,  // filled on close
  "entry_price": 142.50,
  "current_price": 148.48,
  "stop": 136.80,
  "tp1": 152.00,
  "tp2": 165.00
}
```

---

## Implementation Roadmap

```
Week 1: Foundation + Regime Screener
├── Day 1: Add Chart.js to template base, establish shared CSS tokens
├── Day 2: /api/v7/regime-screener endpoint + regime_screener.html
├── Day 3: Regime Screener: detail endpoint + Chart.js line chart
├── Day 4: Connect Signal Explorer to real API (replace hardcoded data)
└── Day 5: Polish + mobile responsive testing

Week 2: Portfolio Brief + Compare
├── Day 1: Brief builder logic + /api/v7/portfolio-brief
├── Day 2: portfolio_brief.html template
├── Day 3: Artifact output (json/md) + daily scheduler hook
├── Day 4: Compare Overlay /api/v7/compare-overlay + chart
├── Day 5: compare.html template + Discord /compare upgrade

Week 3: Options Lab + Performance Lab
├── Day 1: Options data integration (yfinance/broker)
├── Day 2: /api/v7/options-screen + options_lab.html
├── Day 3: IV term chart + EV scatter
├── Day 4: /api/v7/performance-lab + performance_lab.html
├── Day 5: Monthly heatmap + equity curve + drawdown chart

Week 4: Strategy Portfolio Lab + Cards
├── Day 1: StrategyPortfolioOptimizer backend
├── Day 2: /api/v7/strategy-portfolio + template
├── Day 3: Correlation heatmap + weight optimization
├── Day 4: CardGenerator for shareable PNGs
├── Day 5: ArtifactManager + final integration testing
```

---

## Navigation Structure

```
Dashboard (/)
├── 📊 Home (existing)
├── 🔬 Backtest (existing)
├── 🔍 Quote (existing)
├── 💬 Commands (existing)
│
├── 🎯 Regime Screener (/regime-screener)     ← P0 NEW
├── 📋 Portfolio Brief (/portfolio-brief)      ← P0 NEW
├── 📈 Compare Overlay (/compare)              ← P0 NEW
├── 🔮 Options Lab (/options-lab)              ← P1 NEW
├── 📊 Performance Lab (/performance-lab)      ← P1 NEW
├── ⚖️ Strategy Portfolio (/strategy-lab)      ← P1 NEW
└── 📡 Signal Explorer (/signals/explorer)     ← UPGRADE
```

#### Nav Bar Update

```html
<!-- Add to all templates — bottom nav or sidebar -->
<nav class="fixed bottom-0 w-full bg-gray-900 border-t border-gray-700 px-2 py-1">
  <div class="flex justify-around text-xs">
    <a href="/" class="text-center">📊<br>Home</a>
    <a href="/regime-screener" class="text-center">🎯<br>Regime</a>
    <a href="/portfolio-brief" class="text-center">📋<br>Brief</a>
    <a href="/compare" class="text-center">📈<br>Compare</a>
    <a href="/options-lab" class="text-center">🔮<br>Options</a>
    <a href="/performance-lab" class="text-center">📊<br>Perf</a>
    <a href="/strategy-lab" class="text-center">⚖️<br>Strategy</a>
    <a href="/signals/explorer" class="text-center">📡<br>Signals</a>
  </div>
</nav>
```

---

## Time Policy (From Your Analysis)

All timestamps follow this canonical policy:

| Layer | Timezone | Format |
|-------|----------|--------|
| **Storage** | UTC always | ISO 8601 |
| **API Response** | UTC always | ISO 8601 with Z suffix |
| **Display** | User-configurable | HKT / ET / UTC toggle |
| **Cards / Reports** | Show both | `generated_at` + user-local |
| **Discord** | HKT default | Configurable via user pref |

---

## Summary Metrics

| Item | Backend Lines | Template Lines | New Endpoints | Charts | Effort |
|------|--------------|----------------|---------------|--------|--------|
| Regime Screener | ~150 | ~400 | 3 | 1 line | 2-3d |
| Portfolio Brief | ~200 | ~350 | 3 | 0 | 2-3d |
| Compare Overlay | ~120 | ~300 | 1 | 1 multi-line | 1-2d |
| Options Lab | ~250 | ~450 | 3 | 2 (scatter+line) | 3-4d |
| Performance Lab | ~200 | ~600 | 1 | 4 (line+heatmap+bar+area) | 3-4d |
| Strategy Portfolio | ~300 | ~400 | 1 | 3 (heatmap+pie+line) | 3-5d |
| Shareable Cards | ~300 | — | 1 | matplotlib | 2-3d |
| Artifact Archive | ~150 | — | 2 | — | 2d |
| **Total** | **~1,670** | **~2,500** | **15** | **11** | **~20d** |

---

## Key Principles (Do's and Don'ts)

### ✅ DO
- Single-purpose pages — one screen, one decision
- Decision compression — all info needed on one view
- Research artifact pipeline — json/md/png for every output
- Portfolio-level explanation — story, not just numbers
- Mobile-first dark card design — PWA ready
- Source labels — always show backtest / paper / live
- Components over scores — show confidence, risk, regime, not just a number

### ❌ DON'T
- Don't simplify CC's regime to just bull/weak — keep 3-axis (risk/trend/vol)
- Don't use single composite score — always show components
- Don't mix backtest/paper/live returns — clearly separate
- Don't use fixed 10%/20% stops for all assets — keep dynamic
- Don't turn notebooks into production — keep labs/ separate
- Don't overload any single page — if it scrolls too much, split it

---

> **Final word:** CC 已有 quant math，缺嘅係 presentation layer。
> Ship the surface, not more math.
