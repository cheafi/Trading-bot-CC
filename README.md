# TradingAI Bot 🤖📈

> **An elite algorithmic trading platform** — regime-aware signal generation, multi-expert council decisions, portfolio risk management, and a live Alpine.js dashboard. Built for professionals.

[![Python](https://img.shields.io/badge/Python-3.13-blue?style=flat&logo=python&logoColor=white)](https://python.org)
[![FastAPI](https://img.shields.io/badge/FastAPI-0.136-009688?style=flat&logo=fastapi&logoColor=white)](https://fastapi.tiangolo.com)
[![Docker](https://img.shields.io/badge/Docker-ready-2496ED?style=flat&logo=docker&logoColor=white)](https://docker.com)
[![License](https://img.shields.io/badge/License-MIT-green?style=flat)](LICENSE)

---

## ✨ Features

| Layer              | Capability                                                                                                     |
| ------------------ | -------------------------------------------------------------------------------------------------------------- |
| **Signal Engine**  | Momentum, Breakout, Mean-Reversion, Swing strategies with conviction tiers (TRADE / LEADER / WATCH)            |
| **Regime Router**  | VIX-entropy probabilistic regime detection (RISK_ON / RISK_OFF / NEUTRAL) with EMA hysteresis                  |
| **Expert Council** | Multi-agent weighted-accuracy voting across 10+ specialist engines                                             |
| **Portfolio Risk** | Fixed-fractional sizing, ATR stops, correlation guards, drawdown circuit breaker, trailing stops               |
| **AI Advisor**     | Local Docker Model Runner routing — PM memos, expert-view narratives, trade review with similar-case retrieval |
| **Live Dashboard** | Alpine.js single-page UI — morning brief, signals, regime status, position tracker, playbook, AI panels        |
| **Scheduler**      | APScheduler pre-market signal generation, intraday refresh, EOD brief + portfolio review                       |
| **Discord Alerts** | Real-time trade signals, regime changes, and EOD summaries via Discord bot                                     |

---

## 🏗 Architecture

```
src/
├── api/
│   ├── main.py              # FastAPI app + lifespan startup
│   ├── deps.py              # Canonical auth deps (verify_api_key, sanitize_for_json)
│   ├── routers/             # 10 feature routers (brief, intel, playbook, decision …)
│   ├── templates/index.html # Alpine.js dashboard (~3100 lines)
│   └── routers/ai_advisor.py # PM memo / expert-view / trade review endpoints
├── engines/
│   ├── regime_router.py     # VIX/breadth/entropy regime classification
│   ├── signal_engine.py     # UniverseFilter + 4 strategy engines
│   ├── multi_ranker.py      # TRADE=18 / LEADER=12 / WATCH=6 scoring
│   └── expert_council.py    # Weighted multi-agent voting
├── algo/
│   └── position_manager.py  # Position sizing, trailing stops, exit logic
├── services/
│   ├── regime_service.py        # RegimeService singleton (4h cache)
│   ├── brief_data_service.py
│   ├── indicators.py            # compute_indicators() shared shim
│   ├── ai_service.py            # Multi-provider AI router (local → cloud fallback)
│   ├── fund_ai_service.py       # PM memo + expert-view generation
│   ├── trade_review_ai_service.py # JSON-structured trade review
│   └── trade_memory_service.py  # Embedding-aware similar-trade retrieval
├── scheduler/main.py        # APScheduler jobs (premarket / intraday / EOD)
├── core/
│   └── risk_limits.py       # RISK, VIX, UNIVERSE_GATES, SIGNAL_THRESHOLDS
└── notifications/
    └── discord_bot.py       # Discord alert integration
```

---

## 🚀 Quick Start

### Docker (recommended on macOS — avoids Gatekeeper pydantic scan)

**CC dev dashboard** (live-reload API, paper by default):

```bash
cp .env.example .env          # add OPENAI_API_KEY or enable Docker Model Runner
docker compose -f docker-compose.dev.yml up --build
# Dashboard → http://localhost:8000
```

**Unattended trading stack** (IB gateway, postgres, reconciler, venue orchestrators):

```bash
cp .env.example .env          # POSTGRES_PASSWORD, TWS_USERID, TWS_PASSWORD
cp docker-compose.override.yml.example docker-compose.override.yml
docker compose up -d --build  # base: ib-gateway, postgres, reconciler
# With orchestrators: services from override file start automatically
# Live gate (fail-closed): LIVE_TRADING=1 + IB_MODE=live + IB_API_PORT=4003
```

Profiles: `--profile dev` (Jupyter/pgAdmin), `--profile research` (nightly stub), `--profile ops` (backup/Watchtower stubs), `--profile ai` (API LLM sidecar in override).

See [docs/CC_X_DOCKER_AI.md](docs/CC_X_DOCKER_AI.md) for AI provider setup in containers.

### Native (Linux / CI)

```bash
python -m venv venv && source venv/bin/activate
pip install -r requirements/requirements.txt
python _cc_instant.py          # starts uvicorn on :8000 → :8001
```

### Public access (dev demos)

Share CC on the internet via Cloudflare or ngrok tunnel:

```bash
./scripts/dev/expose-cc-public.sh   # CC must already be on :8000
```

See [docs/CC_X_PRODUCTION_READINESS.md](docs/CC_X_PRODUCTION_READINESS.md) for security notes, Docker tunnel profile, and LAN access.

### Environment Variables

| Variable                  | Default                    | Description                                      |
| ------------------------- | -------------------------- | ------------------------------------------------ |
| `API_SECRET_KEY`          | `dev-secret-local`         | Bearer token for protected endpoints             |
| `DISCORD_BOT_TOKEN`       | `""`                       | Discord bot token                                |
| `DISCORD_CHANNEL_ID`      | `""`                       | Channel for alerts                               |
| `AI_DISABLED`             | `""`                       | Set `1` to disable all LLM calls                 |
| `OPENAI_API_KEY`          | `""`                       | Cloud LLM fallback when Azure unset              |
| `AZURE_OPENAI_ENDPOINT`   | `""`                       | Azure OpenAI endpoint (preferred path)           |
| `AZURE_OPENAI_API_KEY`    | `""`                       | Azure key or use SP vars below                   |
| `AZURE_OPENAI_DEPLOYMENT` | `""`                       | Azure deployment name                            |
| `AZURE_OPENAI_ENABLED`    | auto                       | Set `false` to disable Azure even if creds exist |
| `AZURE_SEARCH_*`          | `""`                       | Optional knowledge/lessons search hook           |
| `LOCAL_LLM_ENABLED`       | `auto`                     | Docker Model Runner: auto/on/off                 |
| `LOCAL_LLM_URL`           | auto (host/container)      | Docker Model Runner endpoint                     |
| `LOCAL_MODEL_ADVISOR`     | `ai/gemma3`                | PM memo / narrative model                        |
| `LOCAL_MODEL_REVIEWER`    | `ai/qwen3-coder`           | Trade review model                               |
| `LOCAL_MODEL_EMBED`       | `ai/all-minilm-l6-v2-vllm` | Embedding model for similar-trade search         |
| `TRADING_ENV` / `BROKER`  | `paper`                    | Paper mode default in Docker dev                 |
| `VIX_CRISIS`              | `35.0`                     | VIX threshold → NO TRADE                         |
| `RISK_MAX_POSITIONS`      | `10`                       | Max concurrent open positions                    |
| `RISK_MAX_DRAWDOWN_PCT`   | `0.15`                     | Portfolio drawdown circuit breaker               |

---

## 📊 Trading Domain Defaults

| Concept            | Value                                                                          |
| ------------------ | ------------------------------------------------------------------------------ |
| Conviction tiers   | TRADE > LEADER > WATCH (weights 18 / 12 / 6)                                   |
| Risk per trade     | 1% fixed-fractional                                                            |
| R:R minimum        | 2:1 WATCH · 3:1 TRADE                                                          |
| VIX regime         | <14 RISK_ON · 14–20 normal · 20–28 elevated · 28–35 high · >35 crisis NO TRADE |
| Max open positions | 10 (hard cap)                                                                  |
| Correlation guard  | No >0.7 corr between any two new positions                                     |
| Stop discipline    | Hard stop at 1R; trail only after +1R in profit                                |

---

## 🧪 Tests

```bash
source venv/bin/activate
python -m pytest test_position_manager.py test_regime_router.py -v   # 27 risk-critical tests
python -m pytest test_sprint73.py -v                                  # 33 sprint integration tests
```

---

## 📁 Key Files

| File                                   | Purpose                                                            |
| -------------------------------------- | ------------------------------------------------------------------ |
| `src/api/templates/index.html`         | Full dashboard (Alpine.js)                                         |
| `src/api/routers/brief.py`             | Morning brief + changelog endpoints                                |
| `src/api/deps.py`                      | FastAPI Depends callables — canonical auth                         |
| `src/services/regime_service.py`       | RegimeService singleton (4h cache)                                 |
| `src/engines/regime_router.py`         | VIX/breadth/entropy regime classification                          |
| `src/engines/signal_engine.py`         | UniverseFilter + strategy engines                                  |
| `src/core/risk_limits.py`              | All risk constants — RISK, VIX, UNIVERSE_GATES                     |
| `src/scheduler/main.py`                | TradingScheduler — premarket/intraday/EOD jobs                     |
| `src/services/ai_service.py`           | Multi-provider AI router with fail-fast on auth errors             |
| `src/services/fund_ai_service.py`      | PM memo + expert-view with deterministic fallbacks                 |
| `src/services/trade_memory_service.py` | Embedding-aware similar-trade retrieval from `closed_trades.jsonl` |
| `src/api/routers/ai_advisor.py`        | AI advisor REST routes (memo / expert-view / overview / review)    |
| `data/brief-*.json`                    | Daily brief data files                                             |
| `data/closed_trades.jsonl`             | Trade history for AI similarity search                             |
| `_cc_instant.py`                       | Server launcher (venv auto-detect)                                 |

---

## 🗺 Roadmap

See [ROADMAP.md](ROADMAP.md) and [TODO.md](TODO.md) for planned work.
Sprint history in [CHANGELOG.md](CHANGELOG.md).

---

## ⚠️ Disclaimer

This software is for **educational and research purposes only**. It does not constitute financial advice. Past performance of any algorithmic strategy does not guarantee future results. Always paper-trade before risking real capital.

---

_Built with ❤️ by cheafi_
