# Bot Guide — All 64 Commands

> Complete reference for every slash command in CC v9.0.

---

## Quick Navigation

- [📊 Market Intelligence](#-market-intelligence)
- [🤖 AI Analysis](#-ai-analysis)
- [🎯 Signals & Scanners](#-signals--scanners)
- [📈 Backtest & Strategy AI](#-backtest--strategy-ai)
- [💼 Portfolio & P&L](#-portfolio--pnl)
- [📋 Reports & Dashboard](#-reports--dashboard)
- [🔔 Alerts & Watchlist](#-alerts--watchlist)
- [⚙️ Admin & Utilities](#️-admin--utilities)
- [Signal Card Anatomy](#signal-card-anatomy)
- [4 Workflow Guides](#workflow-guides)

---

## 📊 Market Intelligence

### `/market`
Full market dashboard. Posts a rich embed with:
- US indices: SPY, QQQ, DIA, IWM + day change
- VIX reading with fear/greed label
- Breadth indicators (% above SMA50)
- Futures pre-market if available
- Sector performance heatmap summary

### `/market_now`
Instant compact snapshot — SPY, QQQ, DIA, IWM, VIX. Best for quick checks during trading hours.

### `/premarket`
Pre-market movers (4am–9:30am ET). Shows top 5 gainers/losers from watchlist with volume context and overnight futures.

### `/sector`
11-sector heatmap with performance bars:
`XLK · XLV · XLF · XLE · XLY · XLP · XLI · XLRE · XLB · XLU · XLC`
Includes YTD comparison and relative strength.

### `/macro`
Macro indicators: Gold (GLD), Oil (USO), Bonds (TLT), Dollar (DXY), Bitcoin (BTC-USD). Shows correlations and risk-off/risk-on signal.

### `/movers`
Top 5 gainers and top 5 losers from the 50-stock watchlist with volume ratio and short note.

### `/crypto`
Top 6 crypto (BTC, ETH, SOL, DOGE, ADA, AVAX) with price, 24h change, and sentiment gauge (🐂/🐻/😐).

### `/asia`
Asia session — Nikkei 225, Hang Seng Index, Shanghai Composite with change and trend note.

### `/japan`
Nikkei 225 deep dive — price, change, volume, trend, key support/resistance.

### `/hk`
Hang Seng Index detail — price, change, Hang Seng Tech, southbound flow note.

### `/btc`
Bitcoin deep dive — price, 24h/7d change, dominance, fear & greed index, on-chain note.

### `/daily`
Comprehensive daily summary — combines market, macro, sectors, movers, and top 3 signals in one scrollable embed.

### `/daily_update`
Triggers a fresh market update immediately (same as what `auto_movers` posts automatically).

### `/risk`
Risk regime assessment:
- VIX level → risk-on / risk-off / elevated / extreme
- Suggested allocation (equities vs cash/bonds)
- Sector rotation guidance for current regime

### `/whale`
Unusual volume scan — identifies stocks from the 50-stock universe with volume > 3× average in the last session. Flags potential institutional activity.

---

## 🤖 AI Analysis

### `/ai TICKER`
GPT-powered comprehensive analysis. Requires `OPENAI_API_KEY`. Returns:
- Current trend assessment
- Sentiment from recent news
- Key catalysts
- Actionable thesis (bull/bear case)

Falls back to rule-based analysis if no API key.

### `/analyze TICKER`
Deep technical analysis:
- Price + all moving averages (SMA20/50/200, EMA9/21)
- RSI, MACD, Bollinger Bands, ATR, ADX
- Volume analysis (relative volume, OBV trend)
- Trend direction and strength
- Key support and resistance levels

### `/advise TICKER`
Actionable recommendation:
- Clear **BUY / HOLD / SELL / WATCH** verdict
- Confidence level (%)
- Entry range, target, stop
- Risk/reward ratio
- One-paragraph plain-English reasoning

### `/score TICKER`
Signal quality score (0–100) with full breakdown:
- Trend component (0–25)
- Momentum component (0–25)
- Volume component (0–25)
- Risk/reward component (0–25)
- Label: STRONG BUY / BUY / NEUTRAL / SELL / AVOID

### `/compare TICKER_A TICKER_B`
Side-by-side comparison:
- Price performance (1d, 5d, 1m, 3m)
- Technical scores
- Relative strength
- Which is currently stronger and why

### `/levels TICKER`
Key price levels:
- Daily support (S1, S2) and resistance (R1, R2)
- Weekly pivot
- SMA20 / SMA50 / SMA200 as dynamic levels
- Recent high/low
- ATR-based stop distance

### `/why TICKER` ⭐ Conviction Engine
The deepest single-stock analysis command. Posts a full conviction scorecard:

```
CONVICTION SCORE: +72 / 100
  Technical      +35 / 40
  Fundamental    +18 / 25
  Momentum       +12 / 20
  News/Sentiment +7  / 15

  🟢 WHY BUY  (specific edge narrative)
  🛑 WHY THIS STOP  (exact placement + risk%)
  📰 Recent headlines (last 3 relevant)
  🎯 Analyst consensus + price target
  ⚖️  Bull case vs Bear case
```

Score interpretation:
- `+60 to +100` — Strong conviction to buy
- `+20 to +59` — Moderate conviction
- `-19 to +19` — Neutral / wait
- `-60 to -20` — Caution / avoid
- `-100 to -61` — Strong conviction to sell / short

### `/price TICKER`
Real-time quote with extended-hours price. Shows regular + pre/post-market price if available.

### `/quote TICKER`
Compact one-line price quote.

---

## 🎯 Signals & Scanners

### `/signals`
Latest trading signals overview — shows the most recent signal for each active scan type (swing, breakout, momentum, mean-reversion).

### `/scan STRATEGY`
Run a named scanner immediately:
- `vcp` — Volatility Contraction Pattern
- `breakout` — Price breakout above resistance
- `dip` — Mean-reversion dip buy
- `momentum` — High relative strength momentum
- `swing` — Multi-day swing pullback

### `/breakout`
Consolidation breakout scanner — finds stocks from the 50-stock universe that are:
- Trading above SMA50 with volume spike (> 1.5× avg)
- Breaking above a prior resistance level
- RSI 55–75 (trending, not overbought)
Returns top 5 setups with entry, target, stop.

### `/dip`
Dip-buying scanner — mean-reversion setups:
- Recent sharp pullback (−5% to −15% from high)
- RSI oversold (< 35)
- Still above SMA200 (long-term trend intact)
Returns top 5 dip setups.

### `/momentum`
High-momentum scanner:
- 20-day relative strength rank
- Volume > 1.2× average
- ADX > 25 (trending)
- Dual EMA bullish alignment (EMA9 > EMA21)
Returns top 5 momentum leaders.

### `/swing`
Swing pullback scanner:
- Pulled back to SMA20 support
- RSI 40–55 (not oversold, not overbought)
- Volume declining on pullback (healthy)
Returns top 5 swing entries.

### `/squeeze`
Bollinger Band squeeze — finds stocks where:
- Bollinger Band width at 6-month low
- Keltner Channel inside Bollinger Band
- Volume building
Squeeze + volume = impending breakout.

### `/setup TICKER`
Full setup analysis for one stock — combines technical, risk/reward, entry, target, stop, and scores it against all 4 strategy types.

### `/news TICKER`
Latest news headlines for a ticker (via yfinance) with:
- Headline + source + time
- Sentiment classification (positive / negative / neutral)
- Aggregated sentiment score

---

## 📈 Backtest & Strategy AI

### `/backtest TICKER [PERIOD]` ⭐ Full AI Backtest Engine
The most comprehensive backtest command. Period defaults to `1y`. Options: `6mo`, `1y`, `2y`.

**What it runs:**
1. **4-strategy comparison** — SWING, BREAKOUT, MEAN_REVERSION, MOMENTUM each fully simulated
2. **Walk-forward validation** — 4 folds (70% train / 30% test), shows OOS degradation
3. **Parameter sweep** — 81 combinations of RSI period, SMA period, volume multiplier
4. **Cross-check** — do multiple strategies agree? Boosts conviction
5. **Monte Carlo** — 500 simulations → 5th/50th/95th percentile return range
6. **Regime diagnosis** — which of 9 regimes is the stock currently in?
7. **Self-correction** — live signal accuracy feeds back as a score multiplier (×0.6–1.4)

**Output format:**
```
🤖 AI BACKTEST — NVDA (1y)
  
  STRATEGY RANKING
  1. BREAKOUT    Score 78  Win 64%  Avg +8.2%  OOS −4%
  2. MOMENTUM    Score 71  Win 58%  Avg +6.1%  OOS −7%
  3. SWING       Score 64  Win 52%  Avg +4.8%  OOS −5%
  4. MEAN_REV    Score 41  Win 45%  Avg +2.1%  OOS −18%
  
  REGIME: bull_trending (confidence 82%)
  RECOMMENDATION: BREAKOUT in bull_trending regime
  
  WALK-FORWARD: Train 64% → OOS 60% (−4% degradation) ✅
  MONTE CARLO (500 runs): 5th: −12% | 50th: +31% | 95th: +68%
  BEST PARAMS: RSI(14) SMA(50) VolMult(1.5)
  PARAM STABILITY: 73/100
```

### `/best_strategy TICKER`
Fast regime-aware strategy selection. Uses 6-month data and runs a quick version of the optimizer. Returns the single best-fit strategy for the current market regime. Best used before entering a trade.

### `/strategy_report`
Self-learning accuracy report for all tracked strategies:
- Live signal accuracy (signals posted vs actual outcomes)
- Backtest win rate vs actual win rate gap
- Score correction multiplier currently applied (×0.6–1.4)
- Correction log (last 10 adjustments with reason)
- Overall optimizer confidence by strategy

---

## 💼 Portfolio & P&L

### `/portfolio`
Full portfolio view:
- All open positions with current price, entry, P&L
- Sector allocation breakdown
- Total portfolio value
- Beta-adjusted exposure

### `/positions`
Open positions with live P&L:
- Each position: ticker, shares, entry, current, P&L $, P&L %
- Color-coded (green = profit, red = loss)

### `/pnl`
Profit & loss summary:
- Today, this week, this month, all-time
- Best/worst single trade
- Win rate and average return

### `/buy TICKER [SHARES]`
Paper trade buy:
- Validates signal quality (shows score)
- Suggests position size based on account % risk
- Sets initial stop based on ATR
- Confirms entry at current price

### `/sell TICKER [SHARES]`
Paper trade sell:
- Shows realized P&L
- Compares exit to target and stop
- Logs the trade outcome (feeds strategy self-learning)

---

## 📋 Reports & Dashboard

### `/dashboard`
Full interactive dashboard with navigation buttons to cycle between:
- Market overview
- Sector heatmap
- Signal summary
- Portfolio snapshot

### `/report`
Comprehensive formatted report — combines market, signals, portfolio, and top opportunities in a single printable embed.

### `/stats`
Bot statistics:
- Total signals generated (session + all-time)
- Win rate by strategy type
- Uptime since last restart
- Number of active alerts
- Background task health summary

### `/status`
Status check for all 23 background tasks:
- Active ✅ or Inactive ⚠️
- Time until next run
- Last run timestamp
- Error count (if any)

---

## 🔔 Alerts & Watchlist

### `/alert TICKER above/below PRICE`
Set a personal price alert. Fires once when the condition is met, then auto-removes.
```
/alert NVDA above 150
/alert TSLA below 200
```

### `/my_alerts`
View all your active price alerts with current price vs target.

### `/clear_alerts`
Remove all your active alerts.

### `/watchlist [add/remove/clear/show] [TICKER]`
Manage your personal watchlist (up to 20 tickers):
```
/watchlist add NVDA
/watchlist remove NVDA
/watchlist show
/watchlist clear
```
Your watchlist is separate from the 50-stock system universe.

---

## ⚙️ Admin & Utilities

### `/help`
Interactive help embed with navigation buttons to browse each command category.

### `/announce MESSAGE`
Post a formatted announcement embed. Admin only.

### `/pin MESSAGE`
Pin a short message as an embed in the channel. Admin only.

### `/purge N`
Delete the last N messages (max 100). Admin only.

### `/slowmode SECONDS`
Set channel slowmode. `0` to disable. Admin only.

---

## Signal Card Anatomy

Every signal generated by a scanner (`/signals`, `/scan`, `/breakout`, `/momentum`, `/swing`, auto-tasks) follows this layout:

```
┌──────────────────────────────────────────────────────────────────┐
│  🟢 LONG  NVDA  —  $142.50                                       │
│  Strategy: BREAKOUT  ·  Score: 87/100  ████████░░                │
│                                                                   │
│  📋 Signal Conditions                                            │
│  • 🚀 BREAKING OUT above $141.00 resistance                      │
│  • 🔥 Volume 2.3× average — institutional demand                 │
│  • ✅ Above SMA50 — trend intact                                  │
│                                                                   │
│  🎯 Target: $162.00                                              │
│  🛑 Stop: $132.00                                                │
│  ⚖️  R:R: 2.4:1                                                  │
│  ⏱️  Holding: 1–4 weeks                                          │
│                                                                   │
│  RSI: ⚪ 58      RelVol: 🔥 2.3×    ADX: 32                     │
│                                                                   │
│  🛑 Invalidation: Close below $132.00 (base of consolidation)   │
│                                                                   │
│  ── NEW IN V6 ───────────────────────────────────────────────── │
│  🟢 WHY BUY                                                      │
│     NVDA broke out of a 3-week tight range on 2.3× volume.      │
│     EMA9/21 bullish cross confirmed. Sector momentum positive.   │
│                                                                   │
│  🛑 WHY THIS STOP @ $132.00                                      │
│     $132.00 = base of consolidation box. A close below this      │
│     invalidates the base. Distance = 7.4% = 1.5× ATR(14).       │
│                                                                   │
│  🧠 ML REGIME CHECK                                              │
│     Backtest score: 78 · Regime: bull_trending · BREAKOUT fits  │
│     OOS win rate: 60% · Score multiplier: ×1.2 (good accuracy) │
│  ─────────────────────────────────────────────────────────────── │
│  💰 Liquidity: ✅ $42.1M avg vol/day                             │
│  Stop/ATR: 1.5×                                                  │
│                                                                   │
│  [🔍 Deep Analysis]  [📐 Position Sizer]  [🔔 Set Alert]        │
└──────────────────────────────────────────────────────────────────┘
```

---

## Workflow Guides

### Workflow 1 — Morning Research
```
1. /market_now          → quick index snapshot
2. /premarket           → any overnight moves
3. /sector              → where is money flowing?
4. /signals             → what did the bot flag overnight?
5. /why TICKER          → deep conviction check on best setup
```

### Workflow 2 — Deep Dive Before Entering a Trade
```
1. /analyze TICKER      → full technical picture
2. /backtest TICKER     → which strategy fits? what's OOS accuracy?
3. /best_strategy TICKER → regime-aware recommendation
4. /why TICKER          → conviction score −100→+100
5. /levels TICKER       → exact entry, target, stop
6. /buy TICKER          → paper trade entry
```

### Workflow 3 — Risk Check
```
1. /risk                → VIX regime + allocation guidance
2. /positions           → current exposure
3. /pnl                 → how am I doing?
4. /portfolio           → sector concentration check
```

### Workflow 4 — Monitoring Active Trades
```
1. /alert TICKER below STOP_PRICE   → set stop alert
2. /my_alerts                        → review all alerts
3. /price TICKER                     → real-time check
4. /strategy_report                  → is the model still accurate?
```

---

Back to [README.md](../README.md)
