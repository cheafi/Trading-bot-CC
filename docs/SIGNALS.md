# 🎯 Signal Engine — TradingAI Bot v6

How trading signals are generated, scored, validated, and delivered.

---

## Signal Pipeline

```
┌──────────────────────────────────────────────────────────────────────┐
│                        SIGNAL GENERATION PIPELINE                     │
├──────────────────────────────────────────────────────────────────────┤
│                                                                       │
│   ┌────────────┐     ┌────────────┐     ┌────────────┐              │
│   │  Universe  │────▶│  Indicator │────▶│  Strategy  │              │
│   │  Selection │     │  Engine    │     │  Rules     │              │
│   │  30 stocks │     │  SMA, RSI  │     │  Per-type  │              │
│   │  10 crypto │     │  MACD, ATR │     │  scoring   │              │
│   │  3 indices │     │  Vol, OBV  │     │            │              │
│   └────────────┘     └────────────┘     └─────┬──────┘              │
│                                                │                      │
│                                                ▼                      │
│   ┌────────────┐     ┌────────────┐     ┌────────────┐              │
│   │  Discord   │◀────│   Risk     │◀────│  Scoring   │              │
│   │  Delivery  │     │  Context   │     │  & Ranking │              │
│   │  Embeds +  │     │  Regime,   │     │  0 – 100   │              │
│   │  Buttons   │     │  VIX, Size │     │  Top 5     │              │
│   └────────────┘     └────────────┘     └────────────┘              │
│         │                                                             │
│         ▼                                                             │
│   Optional: GPT Validator → narrative + approval + reasoning          │
│                                                                       │
└──────────────────────────────────────────────────────────────────────┘
```

---

## Strategy Families

### ⚡ Momentum

**When it activates:** RISK_ON regime, trending market, ADX > 25

| Criteria | Threshold |
|----------|-----------|
| Price above SMA(50) above SMA(200) | Uptrend confirmed |
| 21-day return | Top quintile of universe |
| RSI(14) | 50–70 (not overbought) |
| Relative volume | > 1.0x |
| ADX(14) | > 25 |

**Exit rules:**
- Trailing stop: 2× ATR(14)
- Close below SMA(50)
- RSI > 80

**Hold window:** Days to 2 weeks
**Auto-scan:** `auto_momentum_scan` every 2 hr → `#momentum-alerts`

---

### 🔄 Swing

**When it activates:** Healthy pullbacks in established uptrends

| Criteria | Threshold |
|----------|-----------|
| SMA(50) slope | Positive (uptrend intact) |
| Pullback depth | 3–8% from recent high |
| RSI(14) | 35–50 (oversold but not broken) |
| Volume on pullback | Declining (no distribution) |
| Support level | Near SMA(20) or SMA(50) |

**Exit rules:**
- Target: prior swing high or 1.5–2× risk
- Stop: below pullback low or 1.5× ATR below entry
- Time stop: 10 days without progress

**Hold window:** 2–8 weeks
**Auto-scan:** `auto_swing_scan` every 6 hr → `#swing-trades`

---

### 🚀 Breakout / VCP

**When it activates:** Volatility contraction with volume expansion

| Criteria | Threshold |
|----------|-----------|
| Consolidation | 3+ weeks of tightening range |
| Bollinger Band width | Contracting (squeeze) |
| Volume at breakout | > 1.5× average |
| Price vs resistance | Within 2% of breakout level |
| ATR(14) | Declining during base |

**Exit rules:**
- Stop: just below breakout level
- Target: measured move (range height projected up)
- Trailing: 2× ATR once in profit

**Hold window:** 1–4 weeks
**Auto-scan:** `auto_breakout_scan` every 4 hr → `#breakout-setups`

---

### 📉 Mean Reversion

**When it activates:** NEUTRAL or ranging markets, non-trending conditions

| Criteria | Threshold |
|----------|-----------|
| RSI(14) | < 30 (oversold) |
| Distance from SMA(20) | > 2 standard deviations below |
| Z-score of returns | < -2.0 |
| Volume spike | Present (capitulation-like) |

**Exit rules:**
- Target: SMA(20) regression
- Stop: -3% below entry or new low
- Time: 5 days without bounce

**Hold window:** 2–7 days

---

### 📅 Earnings / Event-Driven

**When it activates:** Pre-earnings positioning or post-earnings reaction

| Criteria | Threshold |
|----------|-----------|
| Days to earnings | 5–15 (pre) or 0–2 (post) |
| Implied vol rank | Context-dependent |
| Historical earnings beat rate | > 60% |
| Technical alignment | Trend + volume confirmation |

---

## Signal Scoring (0–100)

Each signal receives a composite score:

| Component | Weight | Inputs |
|-----------|-------:|--------|
| **Technical alignment** | 30% | SMA position, trend state, RSI zone |
| **Momentum strength** | 20% | Return rank, MACD histogram, ADX |
| **Volume confirmation** | 15% | Relative volume, OBV trend |
| **Risk/reward ratio** | 15% | Target vs stop distance |
| **Pattern quality** | 10% | Consolidation shape, clean levels |
| **Regime fit** | 10% | Strategy matches current market regime |

### Score tiers

| Score | Label | Auto-posted? |
|------:|-------|:------------:|
| 85–100 | 🔥 HIGH CONVICTION | ✅ + cross-posted to `#daily-brief` |
| 75–84 | ⭐ GOOD SETUP | ✅ via `opportunity_scanner` |
| 60–74 | Moderate | Only in scheduled scans |
| < 60 | Weak | Filtered out |

---

## Signal Card Format

Every signal delivered to Discord follows this structure:

```
┌─────────────────────────────────────────────────────┐
│  🎯 SWING LONG — NVDA $142.50                       │
│  Score: 82/100                                       │
├─────────────────────────────────────────────────────┤
│  🎯 Target: $155.00    │  🛑 Stop: $135.00          │
│  ⚖️ R:R: 2.4:1        │  RSI: 55                   │
│  📊 Rel Vol: 1.8x     │  ATR: $4.20                │
│  💰 Liquidity: ✅ $42M/day                          │
├─────────────────────────────────────────────────────┤
│  Reasons:                                            │
│  • Price above rising 50-SMA                         │
│  • Volume confirming breakout                        │
│  • Tech sector in relative strength                  │
├─────────────────────────────────────────────────────┤
│  [Deep Analysis] [Position Sizer] [Set Alert]        │
└─────────────────────────────────────────────────────┘
```

---

## GPT Validation Layer

When enabled (requires `OPENAI_API_KEY`), GPT adds:

| Function | Input | Output |
|----------|-------|--------|
| Signal validation | Signal + context | APPROVED / NEEDS_REVIEW / REJECTED |
| Narrative reasoning | Signal data | "Why this trade, why now" explanation |
| Conflict detection | Multiple signals | Contradiction warnings |
| Report generation | Structured data | Natural language summaries |

GPT is never used to predict prices. It's used to reason about evidence quality.

---

## Universe Watched

### 🇺🇸 US Equities (30 stocks)

```
AAPL  MSFT  GOOGL  AMZN  NVDA  META  TSLA  AMD  NFLX  CRM
COIN  PLTR  SOFI   NIO   RIVN  MARA  XYZ   SHOP ROKU  SNAP
UBER  ABNB  NET    CRWD  DKNG  SMCI  ARM   AVGO MU    INTC
```

### ₿ Crypto (10 assets)

```
BTC-USD  ETH-USD  SOL-USD  DOGE-USD  ADA-USD
XRP-USD  AVAX-USD DOT-USD  MATIC-USD LINK-USD
```

### 🌏 Asia Indices (3)

```
^N225 (Nikkei)  ·  ^HSI (Hang Seng)  ·  000001.SS (Shanghai)
```

### 📊 Indices & Macro

```
SPY  QQQ  DIA  IWM  ^VIX
GLD  USO  TLT  UUP  BTC-USD
XLK  XLF  XLV  XLE  XLI  XLY  XLP  XLU  XLRE  XLC  XLB
```

---

## Relevant Source Files

| File | Lines | Role |
|------|------:|------|
| `src/engines/signal_engine.py` | 1,244 | Core signal generation + ranking |
| `src/engines/gpt_validator.py` | 1,058 | GPT reasoning + approval |
| `src/algo/indicators.py` | 1,272 | Technical indicator calculations |
| `src/algo/swing_strategies.py` | 863 | Swing strategy implementation |
| `src/algo/momentum_strategy.py` | 203 | Momentum strategy |
| `src/algo/mean_reversion_strategy.py` | 215 | Mean reversion strategy |
| `src/algo/vcp_strategy.py` | 415 | VCP / breakout strategy |
| `src/algo/earnings_strategies.py` | 683 | Event-driven strategies |
| `src/algo/position_manager.py` | 752 | Position sizing + stop management |
| `src/algo/strategy_manager.py` | 416 | Multi-strategy orchestration |

---

_Last updated: March 2026 · v6 Pro Desk Edition_
