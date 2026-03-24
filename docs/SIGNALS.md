# Signals Reference

> How trading signals are generated, scored, and explained in TradingAI Bot v6.

---

## Signal Lifecycle

```
Raw Price Data (yfinance)
       │
       ▼
Indicator Calculation (indicators.py)
  SMA · EMA · VWAP · RSI · MACD · Bollinger · ATR · ADX · Volume
       │
       ▼
Strategy Pattern Detection (signal_engine.py)
  Swing · Breakout · Momentum · Mean-Reversion
       │
       ▼
Scoring (0–100)
  Trend + Momentum + Volume + Risk/Reward
       │
       ▼
Thesis Builder
  WHY BUY narrative + WHY THIS STOP logic
       │
       ▼
ML Regime Check (strategy_optimizer.py)
  Regime fit · Backtest score · Score correction multiplier
       │
       ▼
Optional: GPT Validation (gpt_validator.py)
       │
       ▼
Discord Signal Card
  All fields · 3 interactive buttons
```

---

## 4 Strategy Families

### 🔄 SWING — Pullback to Support

**Thesis:** Buy quality stocks during healthy pullbacks within an uptrend.

| Condition | Value |
|-----------|-------|
| Trend | Price > SMA50 (uptrend intact) |
| Pullback | Price at or near SMA20 (−2% to +2%) |
| RSI | 40–55 (not oversold, controlled pullback) |
| Volume | Declining volume on pullback (distribution absent) |
| Stop | Below SMA20 or recent swing low |
| Target | Prior swing high or R1 pivot |
| Hold | 5–15 trading days |

**Best regime:** `bull_trending`, `bull_choppy`

**Worst regime:** `bear_trending`, `high_volatility`

---

### 🚀 BREAKOUT — Range Expansion

**Thesis:** Buy stocks breaking above consolidation with volume confirmation.

| Condition | Value |
|-----------|-------|
| Trend | Price crosses above SMA50 or multi-week range high |
| Volume | Spike > 1.5× 20-day average (institutional demand) |
| RSI | 55–75 (strong but not climactic) |
| Base | 3+ weeks of tight consolidation before breakout |
| Stop | Base low (below consolidation) |
| Target | Measured move = base height × 2–3 |
| Hold | 2–6 weeks |

**Best regime:** `bull_trending`, `breakout_environment`

**Worst regime:** `sideways`, `bear_trending`

---

### ⚡ MOMENTUM — Relative Strength Leaders

**Thesis:** Own the strongest stocks in the strongest sectors. Hold as long as trend continues.

| Condition | Value |
|-----------|-------|
| Relative strength | Top quartile vs SPY (20-day RS rank) |
| EMA alignment | EMA9 > EMA21 > SMA50 (bullish stack) |
| ADX | > 25 (confirmed trending) |
| Volume | > 1.2× average |
| RSI | > 50 (bullish territory) |
| Stop | EMA21 or recent 10-day low |
| Target | Trailing — exit on EMA9 cross below EMA21 |
| Hold | 1–8 weeks (trail the trend) |

**Best regime:** `bull_trending`, `high_volatility` (up moves)

**Worst regime:** `mean_reversion_environment`, `sideways`

---

### ↩️ MEAN_REVERSION — Extreme Bounce

**Thesis:** Short-term overextension snaps back. Buy extreme oversold with intact long-term trend.

| Condition | Value |
|-----------|-------|
| Long trend | Price > SMA200 (long-term uptrend intact) |
| Short-term drop | −5% to −15% from 20-day high |
| RSI | < 35 (oversold) |
| Bollinger Band | Price touching or below lower band (−2σ) |
| Stop | Below recent low (give up on the bounce) |
| Target | SMA20 or Bollinger midline |
| Hold | 2–7 trading days |

**Best regime:** `mean_reversion_environment`, `sideways`

**Worst regime:** `bear_trending` (bounces fail in downtrends)

---

## Scoring Formula

Every signal receives a composite score (0–100):

$$\text{Score} = w_1 \cdot T + w_2 \cdot M + w_3 \cdot V + w_4 \cdot RR$$

| Component | Weight | Inputs |
|-----------|--------|--------|
| Trend ($T$) | 25% | SMA alignment, ADX, price vs key MAs |
| Momentum ($M$) | 25% | RSI, MACD histogram, EMA cross |
| Volume ($V$) | 25% | Relative volume, OBV direction, accumulation |
| Risk/Reward ($RR$) | 25% | R:R ratio, ATR-calibrated stop, liquidity |

**Score labels:**

| Score | Label | Action |
|-------|-------|--------|
| 80–100 | 🟢 STRONG BUY | High conviction entry |
| 65–79 | 🟢 BUY | Standard entry |
| 45–64 | ⚪ NEUTRAL | Watch and wait |
| 30–44 | 🔴 WEAK | Avoid or reduce |
| 0–29 | 🔴 AVOID | Do not enter |

---

## ML Score Correction

The strategy optimizer tracks live accuracy and applies a multiplier to all signal scores:

| Live accuracy vs backtest | Correction multiplier |
|--------------------------|----------------------|
| Accuracy > 60% | ×1.4 (model over-performing) |
| Accuracy 50–60% | ×1.2 |
| Accuracy 40–50% | ×1.0 (no change) |
| Accuracy 30–40% | ×0.8 |
| Accuracy < 30% | ×0.6 (model under-performing) |

Use `/strategy_report` to see the current multiplier for each strategy.

---

## 9 Market Regimes

The regime detector classifies current market conditions using:
- 20-day volatility (ATR/price)
- Directional bias (returns vs SMA)
- ADX (trend strength)
- Bollinger Band width (squeeze vs expansion)

| Regime | Characteristics | Best Strategies |
|--------|-----------------|-----------------|
| `bull_trending` | Steady uptrend, moderate vol | BREAKOUT, MOMENTUM |
| `bull_choppy` | Upward bias but whippy | SWING |
| `bear_trending` | Steady downtrend | MEAN_REVERSION (short-term), cash |
| `bear_choppy` | Downward bias + noise | Avoid / reduce |
| `high_volatility` | Large daily swings | Reduce size · tight stops |
| `low_volatility` | Tight range, low ADX | BREAKOUT (pre-squeeze) |
| `sideways` | No directional bias | MEAN_REVERSION |
| `breakout_environment` | Multiple stocks breaking out | BREAKOUT, MOMENTUM |
| `mean_reversion_env` | Repeated reversals | MEAN_REVERSION |

---

## WHY BUY / WHY THIS STOP

Every signal card includes plain-English explanations:

**WHY BUY** — Explains the specific edge for this trade:
- Which pattern triggered (e.g., "broke 3-week base on 2×vol")
- Sector and macro context ("semis rotating in, institutional buying visible")
- What would make this a great trade

**WHY THIS STOP** — Explains exactly why the stop is placed where it is:
- Structural level (base low, swing low, SMA)
- Distance in % and ATR multiples
- What it means if the stop triggers ("invalidates the base — thesis wrong")

---

## 50-Stock Universe

All scanners search within this universe. Stocks selected for liquidity (>$10M avg daily vol), sector diversity, and retail trading interest.

```
Mega-cap Tech   AAPL · MSFT · GOOGL · AMZN · NVDA · META · TSLA
Semiconductors  AMD · INTC · AVGO · MU · ARM · SMCI · QCOM
Software/Cloud  CRM · ADBE · NOW · SNOW · PLTR · NET · CRWD · PANW
Finance/Fintech JPM · BAC · GS · V · MA · COIN · SOFI · HOOD
Consumer/Media  NFLX · DIS · UBER · ABNB · SHOP · ROKU · SNAP · BABA
Healthcare      LLY · JNJ · MRNA · ABBV
Speculative     RIVN · NIO · MARA · GME · DKNG · PYPL · LULU
```

Plus system symbols (not scanned, used for context):
- Market ETFs: SPY, QQQ, DIA, IWM
- Volatility: ^VIX
- Macro: GLD, USO, TLT, DXY
- Crypto: BTC-USD, ETH-USD, SOL-USD, DOGE-USD, ADA-USD, AVAX-USD
- Asia: ^N225 (Nikkei), ^HSI (Hang Seng), 000001.SS (Shanghai)
- Sectors: XLK, XLV, XLF, XLE, XLY, XLP, XLI, XLRE, XLB, XLU, XLC

---

## Auto-Scanner Schedule

| Scanner | Task | Interval | Active Hours |
|---------|------|----------|-------------|
| Swing setups | `auto_swing_scan` | 6 hours | Weekdays |
| Breakout setups | `auto_breakout_scan` | 4 hours | Weekdays |
| Momentum setups | `auto_momentum_scan` | 2 hours | Weekdays |
| Combined AI scan | `auto_signal_scan` | 3 hours | 13–21 UTC |
| Opportunity spots | `opportunity_scanner` | 30 min | 13–21 UTC |
| Unusual volume | `auto_whale_scan` | 45 min | 8–22 UTC |
| Price alerts | `realtime_price_alerts` | 3 min | Always |
| Ticker news | `auto_ticker_news` | 15 min | Always |

---

## News Integration

### Auto Ticker News (`auto_ticker_news` — every 15 min)
Rotates through all 50 stocks checking for news. Posts to `#news` channel when a new headline is found. Includes:
- Headline + source + time
- Sentiment classification
- Ticker + current price

### News Auto-Attach on Price Spikes
When `realtime_price_alerts` detects a price spike (> 2% in 3 min), it automatically fetches the most recent news for that ticker and attaches it to the alert. This answers "why is it moving?" in real time.

### `/news TICKER` — On-demand
Pull the latest 5 headlines for any ticker with sentiment analysis.

---

Back to [README.md](../README.md)
