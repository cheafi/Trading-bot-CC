# TradingAI Bot 🤖📈

> **An elite algorithmic trading platform** — regime-aware signal generation, multi-expert council decisions, portfolio risk management, and a live Alpine.js dashboard. Built for professionals.

[![Python](https://img.shields.io/badge/Python-3.13-blue?style=flat&logo=python&logoColor=white)](https://python.org)
[![FastAPI](https://img.shields.io/badge/FastAPI-0.136-009688?style=flat&logo=fastapi&logoColor=white)](https://fastapi.tiangolo.com)
[![Docker](https://img.shields.io/badge/Docker-ready-2496ED?style=flat&logo=docker&logoColor=white)](https://docker.com)
[![License](https://img.shields.io/badge/License-MIT-green?style=flat)](LICENSE)

---

## ✨ Features

| Layer | Capability |
|-------|-----------|
| **Signal Engine** | Momentum, Breakout, Mean-Reversion, Swing strategies with conviction tiers (TRADE / LEADER / WATCH) |
| **Regime Router** | VIX-entropy probabilistic regime detection (RISK_ON / RISK_OFF / NEUTRAL) with EMA hysteresis |
| **Expert Council** | Multi-agent weighted-accuracy voting across 10+ specialist engines |
| **Portfolio Risk** | Fixed-fractional sizing, ATR stops, correlation guards, drawdown circuit breaker, trailing stops |
| **Live Dashboard** | Alpine.js single-page UI — morning brief, signals, regime status, position tracker, playbook |
| **Scheduler** | APScheduler pre-market signal generation, intraday refresh, EOD brief + portfolio review |
| **Discord Alerts** | Real-time trade signals, regime changes, and EOD summaries via Discord bot |

---

## 🏗 Architecture

```
src/
├── api/
│   ├── main.py              # FastAPI app + lifespan startup
│   ├── deps.py              # Canonical auth deps (verify_api_key, sanitize_for_json)
│   ├── routers/             # 10 feature routers (brief, intel, playbook, decision …)
│   └── templates/index.html # Alpine.js dashboard (~3100 lines)
├── engines/
│   ├── regime_router.py     # VIX/breadth/entropy regime classification
│   ├── signal_engine.py     # UniverseFilter + 4 strategy engines
│   ├── multi_ranker.py      # TRADE=18 / LEADER=12 / WATCH=6 scoring
│   └── expert_council.py    # Weighted multi-agent voting
├── algo/
│   └── position_manager.py  # Position sizing, trailing stops, exit logic
├── services/
│   ├── regime_service.py    # RegimeService singleton (4h cache)
│   ├── brief_data_service.py
│   └── indicators.py        # compute_indicators() shared shim
├── scheduler/main.py        # APScheduler jobs (premarket / intraday / EOD)
├── core/
│   └── risk_limits.py       # RISK, VIX, UNIVERSE_GATES, SIGNAL_THRESHOLDS
└── notifications/
    └── discord_bot.py       # Discord alert integration
```

---

## 🚀 Quick Start

### Docker (recommended on macOS — avoids Gatekeeper pydantic scan)

```bash
docker compose up --build
# Dashboard → http://localhost:8001
```

### Native (Linux / CI)

```bash
python -m venv venv && source venv/bin/activate
pip install -r requirements/requirements.txt
python _cc_instant.py          # starts uvicorn on :8000 → :8001
```

### Environment Variables

| Variable | Default | Description |
|----------|---------|-------------|
| `API_KEY` | `""` | Bearer token for protected endpoints |
| `DISCORD_BOT_TOKEN` | `""` | Discord bot token |
| `DISCORD_CHANNEL_ID` | `""` | Channel for alerts |
| `OPENAI_API_KEY` | `""` | GPT signal validation (optional) |
| `VIX_CRISIS` | `35.0` | VIX threshold → NO TRADE |
| `RISK_MAX_POSITIONS` | `10` | Max concurrent open positions |
| `RISK_MAX_DRAWDOWN_PCT` | `0.15` | Portfolio drawdown circuit breaker |

---

## 📊 Trading Domain Defaults

| Concept | Value |
|---------|-------|
| Conviction tiers | TRADE > LEADER > WATCH (weights 18 / 12 / 6) |
| Risk per trade | 1% fixed-fractional |
| R:R minimum | 2:1 WATCH · 3:1 TRADE |
| VIX regime | <14 RISK_ON · 14–20 normal · 20–28 elevated · 28–35 high · >35 crisis NO TRADE |
| Max open positions | 10 (hard cap) |
| Correlation guard | No >0.7 corr between any two new positions |
| Stop discipline | Hard stop at 1R; trail only after +1R in profit |

---

## 🧪 Tests

```bash
source venv/bin/activate
python -m pytest test_position_manager.py test_regime_router.py -v   # 27 risk-critical tests
python -m pytest test_sprint73.py -v                                  # 33 sprint integration tests
```

---

## 📁 Key Files

| File | Purpose |
|------|---------|
| `src/api/templates/index.html` | Full dashboard (Alpine.js) |
| `src/api/routers/brief.py` | Morning brief + changelog endpoints |
| `src/api/deps.py` | FastAPI Depends callables — canonical auth |
| `src/services/regime_service.py` | RegimeService singleton (4h cache) |
| `src/engines/regime_router.py` | VIX/breadth/entropy regime classification |
| `src/engines/signal_engine.py` | UniverseFilter + strategy engines |
| `src/core/risk_limits.py` | All risk constants — RISK, VIX, UNIVERSE_GATES |
| `src/scheduler/main.py` | TradingScheduler — premarket/intraday/EOD jobs |
| `data/brief-*.json` | Daily brief data files |
| `_cc_instant.py` | Server launcher (venv auto-detect) |

---

## 🗺 Roadmap

See [ROADMAP.md](ROADMAP.md) and [TODO.md](TODO.md) for planned work.
Sprint history in [CHANGELOG.md](CHANGELOG.md).

---

## ⚠️ Disclaimer

This software is for **educational and research purposes only**. It does not constitute financial advice. Past performance of any algorithmic strategy does not guarantee future results. Always paper-trade before risking real capital.

---

*Built with ❤️ by cheafi*
