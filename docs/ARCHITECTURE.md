# 🏗️ System Architecture — TradingAI Bot v6

A deep dive into how the system is designed, how data flows, and how 21 background tasks orchestrate 24/7 market intelligence.

---

## High-Level Architecture

```
┌─────────────────────────────────────────────────────────────────────────┐
│                        TradingAI Bot v6 Pro Desk                        │
├─────────────────────────────────────────────────────────────────────────┤
│                                                                         │
│   DATA SOURCES                                                          │
│   ┌──────────┐  ┌──────────┐  ┌──────────┐  ┌──────────┐              │
│   │ Yahoo    │  │  News    │  │  Broker  │  │  OpenAI  │              │
│   │ Finance  │  │  Feeds   │  │  APIs    │  │  GPT     │              │
│   └────┬─────┘  └────┬─────┘  └────┬─────┘  └────┬─────┘              │
│        └──────────────┼──────────────┼──────────────┘                   │
│                       ▼              ▼                                   │
│   ┌─────────────────────────────────────────────────────────────────┐   │
│   │                    INTELLIGENCE LAYER                            │   │
│   │  ┌────────────┐ ┌────────────┐ ┌────────────┐ ┌──────────────┐ │   │
│   │  │  Feature   │ │   Signal   │ │    GPT     │ │    Data      │ │   │
│   │  │  Engine    │ │   Engine   │ │  Validator │ │   Quality    │ │   │
│   │  └────────────┘ └────────────┘ └────────────┘ └──────────────┘ │   │
│   │  ┌────────────┐ ┌────────────┐ ┌────────────┐ ┌──────────────┐ │   │
│   │  │  Momentum  │ │   Swing    │ │  Breakout  │ │ Mean-Revert  │ │   │
│   │  │  Strategy  │ │  Strategy  │ │  / VCP     │ │  Strategy    │ │   │
│   │  └────────────┘ └────────────┘ └────────────┘ └──────────────┘ │   │
│   └─────────────────────────────────────────────────────────────────┘   │
│                       │              │                                   │
│                       ▼              ▼                                   │
│   ┌──────────────────────┐  ┌─────────────────────────────────────┐    │
│   │   DISCORD BOT        │  │       WEB API (FastAPI)             │    │
│   │   52 commands         │  │   /api/v6/scoreboard               │    │
│   │   21 background tasks │  │   /api/v6/signals                  │    │
│   │   Real-time alerts    │  │   /api/v6/regime-snapshot          │    │
│   │   Report embeds       │  │   /dashboard                       │    │
│   └──────────────────────┘  └─────────────────────────────────────┘    │
│                       │              │                                   │
│                       ▼              ▼                                   │
│   ┌─────────────────────────────────────────────────────────────────┐   │
│   │                     BROKER LAYER                                 │   │
│   │   Alpaca · Interactive Brokers · Futu · MT5 · Paper Broker      │   │
│   └─────────────────────────────────────────────────────────────────┘   │
│                                                                         │
└─────────────────────────────────────────────────────────────────────────┘
```

---

## Layer Breakdown

### Layer 1 — Interface

| Component | File | Lines | Role |
|-----------|------|------:|------|
| Discord Bot | `src/discord_bot.py` | ~4,800 | Primary interface — 52 commands, 21 tasks |
| Bot Copy | `src/notifications/discord_bot.py` | ~4,800 | Runtime import target |
| FastAPI | `src/api/main.py` | ~2,200 | REST API + web dashboard |
| Bot Launcher | `run_discord_bot.py` | ~80 | Entry point |
| Dashboard Launcher | `run_dashboard.py` | ~70 | Entry point |
| Report Generator | `src/notifications/report_generator.py` | ~400 | Format-agnostic report builders |

### Layer 2 — Strategy

| Module | Purpose |
|--------|---------|
| `src/algo/momentum_strategy.py` | Trend continuation, relative strength |
| `src/algo/mean_reversion_strategy.py` | Oversold bounces, z-score entries |
| `src/algo/swing_strategies.py` | Multi-day pullback entries |
| `src/algo/vcp_strategy.py` | Volatility contraction patterns |
| `src/algo/trend_following_strategy.py` | SMA crossovers, ADX trending |
| `src/algo/earnings_strategies.py` | Event-driven catalyst plays |
| `src/algo/indicators.py` | 1,272 lines of TA calculations |
| `src/algo/position_manager.py` | Sizing, stop management |
| `src/algo/strategy_manager.py` | Multi-strategy orchestration |

### Layer 3 — Engines

| Module | Purpose |
|--------|---------|
| `src/engines/signal_engine.py` | Signal generation and ranking |
| `src/engines/gpt_validator.py` | GPT reasoning, approval, and narrative |
| `src/engines/feature_engine.py` | Derived technical features |
| `src/engines/insight_engine.py` | Insight composition |
| `src/engines/ai_advisor.py` | User-facing AI analysis |
| `src/engines/auto_trading_engine.py` | Execution engine logic |
| `src/engines/data_quality.py` | Feed health / staleness checks |
| `src/engines/delta_scoreboard.py` | Regime change tracking |

### Layer 4 — Broker

| Module | Markets |
|--------|---------|
| `src/brokers/paper_broker.py` | Simulated (default) |
| Alpaca via `broker_manager.py` | US equities |
| `src/brokers/ib_broker.py` | US, global equities + options |
| `src/brokers/futu_broker.py` | HK, CN markets |
| `src/brokers/mt5_broker.py` | Forex, CFDs |

### Layer 5 — Models

`src/core/models.py` (767 lines) defines all shared Pydantic models:
- Market: `OHLCV`, `Quote`, `MarketSnapshot`
- Features: `TechnicalFeatures`, `MarketBreadth`, `MarketRegime`
- Signals: `Signal`, `Target`, `Invalidation`
- v6 Pro: `RegimeScoreboard`, `ScenarioPlan`, `DeltaSnapshot`, `DataQualityReport`

---

## Data Flow Diagrams

### 📊 Market Data Path

```
Yahoo Finance API
      │
      ▼
_sync_fetch_stock(ticker)     ← runs in thread pool
      │
      ▼
_fetch_stock(ticker)          ← async wrapper
      │
      ▼
Normalized dict: {ticker, price, change_pct, volume, high, low, ...}
      │
      ├──→ Discord embed builder → channel post
      ├──→ Signal scoring pipeline
      ├──→ Report generator
      └──→ API endpoint response
```

### 🎯 Signal Generation Path

```
Scheduler triggers scan (e.g., auto_swing_scan)
      │
      ▼
_sync_swing_scan(_WATCH_US)    ← 30 tickers
      │
      ▼
Per ticker:
  ├── Fetch 1mo history via yfinance
  ├── Compute SMA, RSI, ATR, MACD, volume metrics
  ├── Apply strategy-specific entry rules
  └── Score (0-100) based on signal quality
      │
      ▼
Sort by score, take top 5
      │
      ▼
_build_signal_card() → embed with entry/stop/target/R:R
      │
      ├──→ Post to #swing-trades (with action buttons)
      └──→ Audit log
```

### 🚨 Real-Time Alert Path

```
realtime_price_alerts (every 3 min)
      │
      ▼
For each category: US stocks, indices, crypto, Asia
  ├── Fetch current price
  ├── Check: |change_pct| ≥ threshold?
  │     Stocks ≥ 3%  ·  Indices ≥ 1.2%  ·  Crypto ≥ 5%
  ├── Check: cooldown expired? (30 min per ticker)
  └── If triggered → post alert embed
      │
      ▼
Also check _user_alerts dict
  ├── User set: /alert AAPL above 200
  ├── Current price ≥ 200? → mark triggered
  ├── DM the user
  └── Post to #signals
```

---

## Automation Orchestration

### Task Registration Pattern

Every background task follows this lifecycle:

```python
# 1. Define the task
@tasks.loop(minutes=3)
async def realtime_price_alerts():
    ...

# 2. Add before_loop waiter
@realtime_price_alerts.before_loop
async def _w13():
    await bot.wait_until_ready()

# 3. Register in on_ready
all_tasks = [..., realtime_price_alerts, ...]
for t in all_tasks:
    if not t.is_running():
        t.start()

# 4. Monitor in health_check
f"{'✅' if realtime_price_alerts.is_running() else '❌'} Price Alerts"
```

### Full Task Map

| # | Task | Interval | Hours (UTC) | Coverage |
|---|------|----------|-------------|----------|
| 1 | `update_presence` | 5 min | 24/7 | Status bar |
| 2 | `market_pulse` | 15 min | 08–22 weekday | `#daily-brief` |
| 3 | `auto_movers` | 30 min | 08–22 weekday | `#signals` |
| 4 | `auto_sector_macro` | 60 min | 08–22 weekday | `#daily-brief` |
| 5 | `auto_crypto` | 2 hr | 24/7 | `#daily-brief` |
| 6 | `global_market_update` | 4 hr | 24/7 | `#daily-brief` |
| 7 | `auto_swing_scan` | 6 hr | Weekday | `#swing-trades` |
| 8 | `auto_breakout_scan` | 4 hr | 13–21 weekday | `#breakout-setups` |
| 9 | `auto_momentum_scan` | 2 hr | 13–21 weekday | `#momentum-alerts` |
| 10 | `auto_signal_scan` | 3 hr | 13–21 weekday | `#ai-signals` |
| 11 | `morning_brief` | 10 min check | 13:20–13:40 weekday | `#daily-brief` |
| 12 | `eod_report` | 10 min check | 20:05–20:20 weekday | `#daily-brief` |
| 13 | `asia_preview` | 10 min check | 01:00–01:15 | `#daily-brief` |
| 14 | `auto_whale_scan` | 45 min | 08–22 weekday | `#signals` |
| 15 | `weekly_recap` | 30 min check | Sunday 21–22 | `#daily-brief` |
| 16 | `realtime_price_alerts` | 3 min | 24/7 | `#momentum-alerts` |
| 17 | `auto_news_feed` | 30 min | 24/7 | `#daily-brief` |
| 18 | `smart_morning_update` | 5 min check | Timed windows | `#daily-brief` |
| 19 | `opportunity_scanner` | 30 min | Weekday | `#momentum-alerts` |
| 20 | `vix_fear_monitor` | 5 min | 24/7 | `#daily-brief` |
| 21 | `health_check` | 30 min | 24/7 | `#admin-log` |

---

## Channel Architecture

```
📊 TRADING
├── #daily-brief      ← morning briefs, EOD, macro, news, VIX alerts
├── #signals          ← whale alerts, user price alerts
├── #swing-trades     ← auto swing scan results
└── #breakout-setups  ← auto breakout scan results

📈 MARKETS
├── #momentum-alerts  ← price spikes, momentum scan, opportunities
├── #ai-signals       ← combined AI-ranked signals
├── #bot-commands     ← user interactions
└── #trading-chat     ← discussion

🔧 ADMIN
└── #admin-log        ← health checks, audit trail
```

---

## Design Principles

1. **Discord-first** — Everything works without the web dashboard
2. **Always-on** — 24/7 tasks cover all global sessions
3. **Multi-horizon** — Short (minutes/days), medium (weeks), longer (regime)
4. **Risk-aware** — Regime detection drives strategy selection and sizing
5. **Modular** — Strategies, brokers, and engines are independently replaceable
6. **Fail-soft** — Each task has try/except; one failure doesn't crash the bot

---

_Last updated: March 2026 · v6 Pro Desk Edition_
