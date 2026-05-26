# Strategy Guide

> How CC's trading strategies work, when they apply, and what their limitations are.
>
> **Important:** All strategies produce *signals for research and education*. They are not financial advice. Every signal must be validated with your own analysis.

---

## Strategy Families

CC currently implements 4 active strategy families with additional styles planned.

### Active Strategies

| Strategy | Holding Period | Best Regime | Score Range | Status |
|----------|---------------|-------------|-------------|--------|
| **Swing** | 3–15 days | Bull trending, bull volatile | 0–100 | ✅ Active |
| **Breakout** | 1–10 days | Bull trending, neutral consolidation | 0–100 | ✅ Active |
| **Momentum** | 2–20 days | Bull trending, bull volatile | 0–100 | ✅ Active |
| **Mean Reversion** | 1–5 days | Sideways, neutral consolidation | 0–100 | ✅ Active |

### Planned Strategies

| Strategy | Status | Notes |
|----------|--------|-------|
| **VCP (Volatility Contraction)** | 🔄 In development | Minervini SEPA pattern, code exists but needs validation |
| **Trend Following** | 📋 Planned | Longer-horizon trend persistence entries |
| **Event-Driven** | 📋 Planned | Earnings, macro releases, catalyst-aware |
| **Sector Rotation** | 📋 Planned | Money flow between sectors |
| **Relative Strength Leaders** | 📋 Planned | Top names in top sectors |

---

## Strategy Details

### 🔄 Swing Trading

**What it does:** Identifies pullback entries in established uptrends. Looks for stocks pulling back to key moving averages (10/21 EMA, 50 SMA) on declining volume, then entering when the pullback shows signs of exhaustion.

**When it works well:**
- Market in bull trending or bull volatile regime
- Individual stock in confirmed Stage 2 uptrend (above rising 50/200 MA)
- Volume contracts during pullback, then expands on reversal

**When it fails:**
- Bear markets — pullbacks become breakdowns
- Late-stage rallies with deteriorating breadth
- High-volatility environments where stops get hit frequently

**Key filters:**
- Trend template (above 50/200 MA, both rising)
- Volume dry-up during pullback
- RSI not already overbought (< 70)
- ATR-based stop placement

**Invalidation:** Close below the pullback low or key support level on increased volume.

**What's honest:** Swing signals work best in clearly trending markets. In choppy or transitional regimes, win rates drop significantly. CC throttles swing signals when the regime is hostile.

---

### 🚀 Breakout Trading

**What it does:** Identifies stocks breaking out of consolidation patterns (bases, ranges, triangles) with volume expansion.

**When it works well:**
- After tight consolidation (low volatility compression)
- Volume expands 1.5x+ above 20-day average on breakout day
- Market regime is supportive (bull trending, neutral)
- Sector/industry group is showing relative strength

**When it fails:**
- False breakouts (the #1 risk) — price breaks out then reverses
- Low-volume breakouts that lack conviction
- Breakouts into resistance (prior highs, round numbers) without catalyst
- Bear or high-volatility regimes where breakouts get sold into

**Key filters:**
- Base quality (minimum 3+ weeks of consolidation)
- Volume expansion confirmation (breakout day volume vs average)
- Relative strength vs market
- Prior-high resistance distance

**Invalidation:** Close back inside the base on high volume. The breakout has failed.

**What's honest:** Even well-filtered breakouts have a ~40–60% win rate. The edge comes from risk:reward (cutting losers fast, letting winners run), not from high hit rates. CC's breakout score reflects base quality and volume confirmation, but false breakouts are inherent to the style.

---

### ⚡ Momentum Trading

**What it does:** Identifies stocks with strong price acceleration and relative strength. Focuses on names making new highs with increasing volume and outperforming their sector.

**When it works well:**
- Strong bull markets with broad participation
- Sector rotation accelerating (money flowing into growth, tech, etc.)
- Individual stock showing persistent relative strength (RS > 80)

**When it fails:**
- Market regime shifts to risk-off — momentum leaders crash hardest
- Crowded trades (everyone owns the same names)
- Late-cycle momentum where leaders are extended

**Key filters:**
- Relative strength ranking (top 20% of universe)
- Price making 20/50-day highs
- Volume trend (increasing on up days)
- Regime filter — suppressed in bear/crisis

**Invalidation:** Loss of relative strength (drops below RS 50), close below 50-day MA.

**What's honest:** Momentum works in waves. When it works, returns are outsized. When it reverses, drawdowns are fast and severe. CC's regime awareness helps but cannot perfectly time regime shifts.

---

### 📉 Mean Reversion

**What it does:** Identifies stocks that have moved too far from their mean (moving average, Bollinger Band) and are likely to revert. Buys oversold conditions in suitable environments.

**When it works well:**
- Sideways, range-bound markets
- Stocks that are fundamentally stable but temporarily oversold
- Low-volatility environments where extremes tend to revert

**When it fails:**
- Trending markets — "oversold" gets more oversold in downtrends
- During market regime transitions (bull → bear)
- Around earnings or major catalysts (gap risk)
- In crisis/panic environments (mean reversion is extremely dangerous)

**Key filters:**
- **Regime filter:** Only active in `sideways` and `neutral_consolidation` regimes
- RSI below 30 (oversold) with volume capitulation
- Price at/below lower Bollinger Band
- Fundamental stability (not a stock in structural decline)

**Invalidation:** New 52-week low on heavy volume. The "mean" itself is moving down.

**What's honest:** Mean reversion is the most dangerous strategy to use incorrectly. "Buy the dip" in a bear market destroys capital. CC restricts mean reversion to appropriate regimes, but no filter is perfect. This strategy should never be the core approach — it's a supplement for specific conditions.

---

### 🔍 VCP (Volatility Contraction Pattern) — In Development

**What it does:** Implements Mark Minervini's SEPA (Specific Entry Point Analysis) methodology. Looks for stocks in Stage 2 uptrends that form a series of tighter and tighter price contractions with declining volume, leading to a breakout at the pivot point.

**VCP characteristics:**
1. Stock in Stage 2 uptrend (above rising 50/200-day MA)
2. Price corrects in successively tighter consolidations (e.g., 25% → 15% → 8%)
3. At least 2–3 contractions visible
4. Volume dries up during consolidation
5. Breakout occurs at the pivot on expanding volume

**Current status:** Code exists in `src/algo/vcp_strategy.py` (415 lines) with Minervini trend template, contraction detection, and volume analysis. However, it has **not been validated** through walk-forward backtesting and is not yet connected to the live signal engine.

**Limitations we're honest about:**
- VCP detection is subjective — code approximates but cannot perfectly replicate expert pattern recognition
- False positives are common in automated VCP scanning
- The strategy requires post-scan human review to confirm pattern quality
- Backtest results are pending

---

## How Scores Work

Every signal gets a score from 0–100:

| Score Range | Grade | Meaning | Alert Action |
|-------------|-------|---------|-------------|
| 80–100 | A / A+ | Strong setup, multiple confirmations | Signal alert + top priority |
| 65–79 | B / B+ | Good setup, most factors aligned | Signal alert |
| 50–64 | C / C+ | Marginal setup, watch only | Watchlist only |
| Below 50 | D / F | Weak or conflicting signals | Not alerted |

**What scores include:**
- Technical setup quality (trend, momentum, volume)
- Regime alignment (does the market environment support this strategy?)
- Risk:reward ratio
- Relative strength vs market/sector
- Event risk proximity (earnings, macro)
- Liquidity quality (volume, spread)

**What scores do NOT guarantee:**
- Scores are not win probabilities (a score of 75 does not mean 75% chance of profit)
- Scores are based on historical pattern matching, which may not repeat
- Scores can change rapidly as new data arrives
- High scores can still lose money — always use stops

---

## Regime Impact on Strategies

CC classifies the market into 9 regimes. Each regime affects which strategies are active and how aggressively they generate signals:

| Regime | Swing | Breakout | Momentum | Mean Reversion |
|--------|-------|----------|----------|----------------|
| Bull Trending | ✅ Full | ✅ Full | ✅ Full | ❌ Off |
| Bull Volatile | ✅ Full | 🟡 Cautious | ✅ Full | ❌ Off |
| Bull Exhaustion | 🟡 Cautious | 🟡 Cautious | 🟡 Cautious | ❌ Off |
| Neutral Consolidation | ✅ Full | ✅ Full | 🟡 Cautious | ✅ Full |
| Sideways | 🟡 Cautious | 🟡 Cautious | ❌ Off | ✅ Full |
| Bear Rally | 🟡 Cautious | ❌ Off | ❌ Off | ✅ Full |
| Bear Trending | ❌ Off | ❌ Off | ❌ Off | ❌ Off |
| Bear Volatile | ❌ Off | ❌ Off | ❌ Off | ❌ Off |
| Crisis | ❌ Off | ❌ Off | ❌ Off | ❌ Off |

> In bear trending, bear volatile, and crisis regimes, CC significantly reduces or eliminates long signals. **The best trade is often no trade.**

---

## Understanding Signal Invalidation

Every signal includes an invalidation condition — the specific price/event that proves the trade idea wrong.

**Why this matters:**
- Invalidation defines your risk before you enter
- If invalidation triggers, exit — don't hope
- The stop price is based on the invalidation level, not an arbitrary percentage

**Types of invalidation:**
| Type | Example |
|------|---------|
| **Price** | Close below $181.50 |
| **Volume** | Break below support on 2x average volume |
| **Time** | If no move within 10 trading days |
| **Event** | Earnings miss or negative guidance |
| **Regime** | Market shifts from bull to bear |

---

## When NOT to Trade

CC tries to help you avoid bad trades, not just find good ones. Signals are suppressed or scored lower when:

- **Regime is hostile** — Bear trending, bear volatile, or crisis
- **Earnings within 2 days** — Event risk too high for technical signals
- **Liquidity is poor** — Dollar volume below $5M/day
- **Breadth is deteriorating** — Market participation narrowing
- **Signal contradicts regime** — Long signals in bear markets are penalized
- **Multiple strong contradictions** — "Why Not" outweighs "Why Buy"

**The goal is fewer, higher-quality signals — not more signals.**

---

## Improving Over Time

CC is designed for continuous improvement:

1. **Every signal is logged** — for post-trade review
2. **Performance Lab tracks outcomes** — win rate, drawdown, Sharpe
3. **Strategy Leaderboard** — compares strategy family performance
4. **Edge calibration** — adjusts expected win rates based on historical outcomes
5. **Walk-forward backtesting** — validates strategies on out-of-sample data

**What's not yet built:**
- Automated post-trade reflection prompts
- Signal history browser with outcome tagging
- Strategy-specific learning dashboards
- Reinforcement-based score adjustment

---

## Disclaimer

All strategies are algorithmic pattern detection tools. They identify setups that have historically preceded favorable price moves, but **past patterns do not guarantee future results**.

- No strategy works all the time
- Losses are a normal part of trading
- Position sizing and risk management matter more than entry signals
- Always apply your own judgment before acting on any signal
- CC is a research tool, not a recommendation engine
