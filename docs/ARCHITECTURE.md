# Architecture

> Full technical architecture of TradingAI Bot v6 Pro Desk.

---

## System Overview

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                           DISCORD INTERFACE                                  │
│              54 slash commands  ·  rich embeds  ·  interactive buttons       │
└──────────────────────────────────┬──────────────────────────────────────────┘
                                   │
┌──────────────────────────────────▼──────────────────────────────────────────┐
│                    src/discord_bot.py  (5,596 lines)                         │
│                                                                               │
│  ┌──────────────────────────────────────────────────────────────────────┐   │
│  │  Command Layer (54 slash commands)                                    │   │
│  │  advise · ai · alert · analyze · announce · asia · backtest          │   │
│  │  best_strategy · breakout · btc · buy · clear_alerts · compare       │   │
│  │  crypto · daily · daily_update · dashboard · dip · help · hk         │   │
│  │  japan · levels · macro · market · market_now · momentum · movers    │   │
│  │  my_alerts · news · pin · pnl · portfolio · positions · premarket    │   │
│  │  price · purge · quote · report · risk · scan · score · sector       │   │
│  │  sell · setup · signals · slowmode · squeeze · stats · status        │   │
│  │  strategy_report · swing · watchlist · whale · why                   │   │
│  └──────────────────────────────────────────────────────────────────────┘   │
│                                                                               │
│  ┌────────────────────────────────────────────────────────────────────┐     │
│  │  Task Layer (23 background tasks)                                   │     │
│  │  update_presence(1m) · market_pulse(15m) · auto_movers(30m)        │     │
│  │  auto_sector_macro(60m) · auto_crypto(30m) · global_market_update  │     │
│  │  auto_swing_scan(6h) · auto_breakout_scan(4h) · auto_momentum(2h)  │     │
│  │  auto_signal_scan(3h) · morning_brief · eod_report · asia_preview  │     │
│  │  auto_whale_scan(45m) · weekly_recap · realtime_price_alerts(3m)   │     │
│  │  auto_news_feed(30m) · auto_ticker_news(15m) · auto_strategy_learn │     │
│  │  smart_morning_update · opportunity_scanner(30m) · vix_monitor(5m) │     │
│  │  health_check(30m)                                                  │     │
│  └────────────────────────────────────────────────────────────────────┘     │
│                                                                               │
│  ┌─────────────────────────────────┐  ┌────────────────────────────────┐   │
│  │  Signal Card Builder            │  │  Price Alert Engine            │   │
│  │  _build_signal_card()           │  │  _store_alert() / _check()     │   │
│  │  ├── WHY BUY narrative          │  │  3-min polling · 50 tickers    │   │
│  │  ├── WHY THIS STOP logic        │  │  news auto-attached to spikes  │   │
│  │  └── ML Regime Check            │  │  User + auto-set alerts        │   │
│  └─────────────────────────────────┘  └────────────────────────────────┘   │
└──────┬─────────────────────┬───────────────────────┬─────────────────────────┘
       │                     │                       │
┌──────▼───────────┐  ┌──────▼──────────────┐  ┌───▼─────────────────────────┐
│ Strategy         │  │ Signal Engine        │  │ Data Layer                  │
│ Optimizer        │  │ signal_engine.py     │  │                             │
│ (936 lines)      │  │ (1,244 lines)        │  │ yfinance — OHLCV + news     │
│                  │  │                      │  │ 50 US stocks                │
│ 4 strategies     │  │ generate_signals()   │  │ 10 crypto                   │
│ 9 regimes        │  │ score_signal()       │  │ 3 Asia indices              │
│ Walk-forward     │  │ validate_signal()    │  │ 11 S&P sectors              │
│ Param sweep      │  │ build_thesis()       │  │                             │
│ Monte Carlo      │  │ build_stop_reason()  │  │ Optional: OpenAI GPT        │
│ Self-correction  │  └──────────────────────┘  └─────────────────────────────┘
└──────────────────┘
       │
       └──────────────────────────────────────────────────────────┐
                                                                   │
┌──────────────────────────────────────────────────────────────────▼──────────┐
│  Supporting Engines                                                           │
│  gpt_validator.py (1,058)  ·  indicators.py (1,272)  ·  models.py (766)     │
│  feature_engine.py  ·  ai_advisor.py  ·  insight_engine.py                  │
└─────────────────────────────────────────────────────────────────────────────┘
```

---

## Layer Breakdown

### Layer 1 — Discord Interface
`src/discord_bot.py` is the single entry point for all user-facing functionality.

- All 54 slash commands defined as `@bot.tree.command` decorators
- All 23 background tasks defined as `@tasks.loop` decorators
- Commands call engines directly; no REST intermediary
- Responses are Discord embeds (`discord.Embed`) with inline fields and buttons

### Layer 2 — Signal & Analysis Engines

| File | Lines | Role |
|------|------:|------|
| `src/engines/signal_engine.py` | 1,244 | Swing / breakout / momentum / mean-reversion scans |
| `src/engines/gpt_validator.py` | 1,058 | OpenAI GPT narrative generation + validation |
| `src/engines/strategy_optimizer.py` | 936 | AI self-learning backtest engine (new) |
| `src/engines/feature_engine.py` | — | Feature extraction for ML |
| `src/engines/ai_advisor.py` | — | Integrated AI trade advice |
| `src/engines/insight_engine.py` | — | Market insight aggregation |

### Layer 3 — Technical Indicators
`src/algo/indicators.py` (1,272 lines) — pure calculation functions:
- SMA, EMA, VWAP, Bollinger Bands, ATR, RSI, MACD, ADX
- Volume spike detection, VCP pattern recognition
- Regime classifier (9 states: bull_trending, bear_trending, high_volatility, sideways, etc.)
- All functions return typed dicts; no side effects

### Layer 4 — Models
`src/core/models.py` (766 lines) — Pydantic v2 type system:
- `SignalCard`, `TradeSetup`, `BrokerPosition`, `WatchlistItem`
- `BacktestResult`, `StrategyResult`, `RegimeState`
- Runtime state singletons (signal cache, alert registry)

### Layer 5 — Data
All market data sourced from `yfinance`:
- OHLCV history (1d, 5m, 1m periods)
- Earnings dates, analyst targets, P/E ratios
- News headlines per ticker
- No paid data API required

---

## 23 Background Tasks — Full Map

| Task | Interval | Active Hours (UTC) | Channel | What It Posts |
|------|----------|-------------------|---------|---------------|
| `update_presence` | 1 min | always | — | Bot status line |
| `market_pulse` | 15 min | always | #general | SPY/QQQ/BTC pulse |
| `auto_movers` | 30 min | 8–22 UTC | #general | Top 5 gainers + losers |
| `auto_sector_macro` | 60 min | 8–22 UTC | #general | Sector heatmap |
| `auto_crypto` | 30 min | always | #crypto | Top 6 crypto |
| `global_market_update` | 60 min | always | #general | World indices |
| `auto_swing_scan` | 6 h | weekdays | #signals | Swing pullback setups |
| `auto_breakout_scan` | 4 h | weekdays | #signals | Breakout setups |
| `auto_momentum_scan` | 2 h | weekdays | #signals | Momentum setups |
| `auto_signal_scan` | 3 h | 13–21 UTC | #signals | Combined AI scan |
| `morning_brief` | daily | 01:00 UTC | #daily-reports | Asia morning |
| `eod_report` | daily | 20:10 UTC | #daily-reports | EOD scorecard |
| `asia_preview` | daily | 01:00 UTC | #daily-reports | Asia session preview |
| `auto_whale_scan` | 45 min | 8–22 UTC | #signals | Unusual volume |
| `weekly_recap` | weekly | Sun 21 UTC | #daily-reports | Weekly wrap-up |
| `realtime_price_alerts` | 3 min | always | #alerts | User + auto alerts |
| `auto_news_feed` | 30 min | always | #news | 25-source news feed |
| `auto_ticker_news` | 15 min | always | #news | Rolling 50-stock news |
| `auto_strategy_learn` | 6 h | weekdays | #ai-signals | ML backtest self-learning |
| `smart_morning_update` | daily | 13:30 UTC | #daily-reports | US pre-market memo |
| `opportunity_scanner` | 30 min | 13–21 UTC | #signals | Best setups now |
| `vix_fear_monitor` | 5 min | always | #alerts | VIX spike warnings |
| `health_check` | 30 min | always | — | Internal diagnostics |

---

## Strategy Optimizer Architecture

`src/engines/strategy_optimizer.py` (936 lines) — singleton `get_optimizer()`

```
StrategyOptimizer
├── _detect_regime(prices)          → 9-state classification
│     bull_trending · bull_choppy · bear_trending · bear_choppy
│     high_volatility · low_volatility · sideways
│     breakout_environment · mean_reversion_environment
│
├── _simulate_strategy(prices, params, strategy_type)
│     SWING        — pullback to SMA20 + RSI oversold + volume
│     BREAKOUT     — price above SMA50 + volume spike + high of range
│     MEAN_REVERSION — Bollinger Band touch + RSI extremes
│     MOMENTUM     — dual EMA crossover + ADX > 25
│
├── _walk_forward_backtest(prices, strategy_type)
│     4 folds: 70% train / 30% test
│     → train win rate, test win rate, OOS degradation %
│
├── _parameter_sweep(prices, strategy_type)
│     81 parameter combinations (rsi_period, sma_period, vol_mult)
│     → best_params, param_stability score
│
├── _cross_check(prices, strategy_type)
│     SWING → supports BREAKOUT?
│     BREAKOUT → momentum confirmation?
│     → cross_check_score
│
├── _monte_carlo(prices, trades, n=500)
│     500 simulation runs with randomised entry sequencing
│     → monte_carlo_mean_return, monte_carlo_5th_pct, monte_carlo_95th_pct
│
├── _get_correction_multiplier(strategy_type)
│     Live signal accuracy vs backtest win rate
│     Poor accuracy (< 40%) → ×0.6
│     Good accuracy (> 60%) → ×1.4
│
└── run_full_backtest(ticker, period)
      Runs all 4 strategies → sorts by corrected_final_score
      Caches result for 6 hours
```

---

## Signal Card Build Flow

```
_build_signal_card(ticker, signal_type)
  │
  ├── 1. Fetch OHLCV (yfinance)
  ├── 2. Calculate all indicators (indicators.py)
  ├── 3. Score 0–100 (signal_engine.score_signal)
  ├── 4. Build WHY BUY thesis (signal_engine.build_thesis)
  ├── 5. Build WHY THIS STOP logic (signal_engine.build_stop_reason)
  ├── 6. Attach ML Regime Check (_attach_ml_rank → strategy_optimizer)
  ├── 7. Fetch latest news (yfinance ticker.news)
  ├── 8. Optional: GPT validate (gpt_validator — if OPENAI_API_KEY set)
  └── 9. Build Discord Embed with all fields + 3 buttons
```

---

## File Structure

```
TradingAI_Bot-main/
├── run_discord_bot.py          ← entry point
├── src/
│   ├── discord_bot.py          ← canonical source (5,596 lines)
│   ├── notifications/
│   │   └── discord_bot.py      ← symlinked copy (auto-synced)
│   ├── engines/
│   │   ├── strategy_optimizer.py   (936 lines) ← NEW
│   │   ├── signal_engine.py        (1,244)
│   │   ├── gpt_validator.py        (1,058)
│   │   ├── feature_engine.py
│   │   ├── ai_advisor.py
│   │   └── insight_engine.py
│   ├── algo/
│   │   ├── indicators.py           (1,272)
│   │   ├── base_strategy.py
│   │   ├── momentum_strategy.py
│   │   ├── swing_strategies.py
│   │   └── ...
│   ├── core/
│   │   ├── models.py               (766)
│   │   ├── config.py
│   │   └── database.py
│   ├── brokers/
│   │   ├── paper_broker.py
│   │   ├── alpaca_broker.py
│   │   └── ...
│   └── ml/
│       ├── feature_pipeline.py
│       ├── trade_learner.py
│       └── rl_agents.py
├── docs/
├── requirements/
└── docker/
```

---

Back to [README.md](../README.md)
