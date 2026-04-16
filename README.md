<p align="center">
  <img src="https://img.shields.io/badge/Python-3.11+-3776AB?logo=python&logoColor=white" />
  <img src="https://img.shields.io/badge/FastAPI-0.104+-009688?logo=fastapi&logoColor=white" />
  <img src="https://img.shields.io/badge/Tests-214_passing-00d4aa" />
  <img src="https://img.shields.io/badge/License-MIT-blue" />
  <img src="https://img.shields.io/badge/Demo-Live-fbbf24?logo=github&logoColor=white" />
</p>

# CC — Regime-Aware Market Intelligence Platform

> **CC turns signals, options research, portfolio briefs, and track-record analytics into explainable, auditable decision surfaces — so every trade has a clear _why_, a transparent _how confident_, and a verifiable _track record_.**

<p align="center">
  <a href="https://cheafi.github.io/Trading-bot-CC/">🔗 Live Demo (GitHub Pages)</a> · <a href="docs/ARCHITECTURE.md">📐 Architecture</a> · <a href="docs/SETUP_GUIDE.md">🚀 Setup Guide</a> · <a href="docs/BOT_GUIDE.md">📖 Command Reference</a>
</p>

---

## What CC Does — 6 Decision Surfaces

CC is not a feature buffet. It's **6 focused surfaces**, each designed to help you make one decision faster and with more confidence.

| # | Surface | What It Answers | Mode |
|---|---------|----------------|------|
| 🎯 | **Today / Regime** | "What state is the market in right now? What's the playbook?" | Live · Paper · Synthetic |
| 📡 | **Signals / Scanner** | "Which setups are worth my attention today, and _why_?" | Live · Backtest · Synthetic |
| 🔍 | **Symbol Dossier** | "Give me the full picture on this one ticker — technicals, catalysts, risk." | Live · Synthetic |
| 📋 | **Portfolio Brief** | "What happened to my holdings today? What needs action?" | Live · Paper · Synthetic |
| 🔮 | **Options Research** | "Which contracts have edge? Show me strike, IV, skew, EV." | Synthetic |
| 📊 | **Track Record** | "Prove it. Show me win rate, drawdown, sample size, gross vs net." | Backtest · Paper |

> **Every surface carries a trust strip** — you always know: data mode (LIVE / PAPER / BACKTEST / SYNTHETIC), source, freshness, sample size, and assumptions.

---

## Architecture

```
                    ┌─────────────────────────────────────────────┐
                    │            USER INTERFACES                   │
                    │  Discord (64 cmds) · FastAPI · GitHub Pages  │
                    └───────────────────┬─────────────────────────┘
                                        │
                    ┌───────────────────▼─────────────────────────┐
                    │          DECISION LAYER                      │
                    │  RegimeRouter → RegimeState (canonical)      │
                    │  OpportunityEnsembler · EdgeCalculator       │
                    │  StrategyLeaderboard · ContextAssembler      │
                    └──────┬─────────────┬──────────────┬─────────┘
                           │             │              │
              ┌────────────▼───┐  ┌──────▼───────┐  ┌──▼──────────────┐
              │  Signal Engine  │  │  Auto-Trade  │  │  Research Layer  │
              │  4 strategies   │  │  Engine      │  │  Options Mapper  │
              │  Score 0–100    │  │  Heartbeat   │  │  Compare Overlay │
              │  WHY BUY/STOP   │  │  Circuit-brk │  │  Perf Lab        │
              │  Factor chips   │  │  R-based size│  │  Portfolio Brief │
              └────────────────┘  └──────────────┘  └─────────────────┘
                           │             │              │
                    ┌──────▼─────────────▼──────────────▼─────────┐
                    │           DATA & BROKER LAYER                │
                    │  yfinance · Alpaca · Futu · IBKR · MT5      │
                    │  3,000+ tickers · US + HK + JP + Crypto     │
                    │  Redis cache · Postgres persistence          │
                    └─────────────────────────────────────────────┘
```

---

## Modes — What Is Real vs Simulated

CC is honest about what's live and what isn't. Every data point is tagged.

| Mode | Meaning | Where Used |
|------|---------|-----------|
| 🟢 **LIVE** | Real market data, real broker connection | Quotes, positions, alerts |
| 🟡 **PAPER** | Real data, simulated execution | Paper trading, demo orders |
| 🔵 **BACKTEST** | Historical data, strategy replay | Strategy optimizer, track record |
| 🟠 **SYNTHETIC** | Generated/demo data, no market connection | GitHub Pages demo, offline mode |

> The GitHub Pages demo at [cheafi.github.io/Trading-bot-CC](https://cheafi.github.io/Trading-bot-CC/) runs in **SYNTHETIC** mode — all prices are from a point-in-time snapshot, not live feeds.

---

## Quick Start

### Option A — Standalone (API + Dashboard)

```bash
git clone https://github.com/cheafi/Trading-bot-CC
cd Trading-bot-CC
python -m venv venv && source venv/bin/activate
pip install -r requirements/base.txt
python run_bot.py          # FastAPI on localhost:8000
```

### Option B — Full Stack (Docker Compose)

```bash
git clone https://github.com/cheafi/Trading-bot-CC
cd Trading-bot-CC
cp .env.example .env       # add DISCORD_BOT_TOKEN, ALPACA_API_KEY, etc.
docker compose up -d       # 9 services: API, Discord, Postgres, Redis, ...
```

### Option C — Discord Bot Only

```bash
pip install -r requirements/base.txt discord.py
cp .env.example .env       # add DISCORD_BOT_TOKEN
python run_discord_bot.py  # 64 slash commands live
```

📖 Full setup: [docs/SETUP_GUIDE.md](docs/SETUP_GUIDE.md)

---

## Feature Map

### Core Intelligence
- **Regime Detection** — 9-state classifier (bull_trending → bear_volatile → sideways) with probability distribution
- **4 Signal Strategies** — Swing, Breakout, Momentum, Mean Reversion — each scored 0–100
- **Factor Contribution** — every score decomposed into chips: `Breakout +28`, `Risk Penalty -12`, `Liquidity ✓`
- **Historical Analog Engine** — "10 most similar past setups" with 5D/10D/20D forward returns and win rate
- **WHY BUY / WHY THIS STOP** — plain-language conviction narrative on every signal

### Research Surfaces
- **Compare Overlay** — normalized returns, relative strength, rolling correlation, rolling beta
- **Options Lab** — LEAPS screen with strike, DTE, IV, OI, EV, delta, skew, spread quality
- **Portfolio Brief** — daily intelligence: actionable / review / watch classification, sector cluster, what_changed
- **Macro Intel** — rates, VIX, DXY, yield curve, gold, oil, crypto — structured as signal context, not news

### Execution & Operations
- **AutoTradingEngine** — autonomous loop: heartbeat, circuit breaker, R-based position sizing
- **5 Brokers** — Paper (default), Alpaca, Futu, IBKR, MT5
- **23 Background Tasks** — 24/7 automation: scans, briefs, alerts, health checks
- **64 Discord Commands** — full interactive interface with rich embeds

### Trust & Auditability
- **Trust Strip** — every page shows: mode, source, freshness, sample size, assumptions
- **Performance Lab** — gross/net returns, Sharpe, max drawdown, profit factor, trade count
- **Artifact Archive** — daily briefs cached as JSON, portfolio snapshots timestamped
- **131 Automated Tests** — 4 test suites covering all API surfaces and data contracts

---

## Data Coverage

| Market | Tickers | Source | Update Freq |
|--------|---------|--------|-------------|
| US Equities | 2,751 (S&P 500/400, NASDAQ-100, Russell 2000) | yfinance | 1-min (live) / daily (backtest) |
| Hong Kong | 78 (HSI + H-shares + tech) | yfinance | 15-min delayed |
| Japan | 60 (TOPIX / Nikkei 225) | yfinance | 15-min delayed |
| Korea / Taiwan / AU / IN | 51 | yfinance | 15-min delayed |
| Crypto | 63 (BTC, ETH, SOL + DeFi + L1/L2) | yfinance | Real-time |
| Macro / Indices | 20+ (VIX, DXY, yields, gold, oil) | yfinance | 1-min (live) |
| Options | Derived / synthetic | Options mapper | On-demand |
| News / Sentiment | Per-ticker | yfinance + optional OpenAI | 15-min rotation |

> **Honest about limitations:** yfinance is free but has rate limits and 15-min delay on international markets. CC falls back gracefully when data is stale or missing — never silently serves old numbers as fresh.

---

## Key Files

| File | Purpose |
|------|---------|
| `src/api/main.py` | FastAPI app — all REST endpoints + 8 HTML dashboard templates |
| `src/engines/auto_trading_engine.py` | Autonomous trading loop with full decision pipeline |
| `src/engines/regime_router.py` | Canonical RegimeState — single source of truth for market state |
| `src/engines/signal_engine.py` | 4-strategy signal generation with scoring |
| `src/engines/context_assembler.py` | Assembles market context (regime + portfolio + news) |
| `src/core/models.py` | Pydantic v2 type system — TradeRecommendation, RegimeScoreboard |
| `src/services/compare_overlay_service.py` | Normalized return comparison engine |
| `src/services/options/options_mapper.py` | Options chain → scored contract table |
| `src/algo/indicators.py` | 1,200+ line technical indicator library |
| `docs/index.html` | GitHub Pages static demo (SYNTHETIC mode) |

---

## Docker Services (11)

| Service | Purpose |
|---------|---------|
| `postgres` | Primary database (trade outcomes, briefs, signals) |
| `redis` | Cache + pub/sub (regime state, quote cache) |
| `market_data_ingestor` | OHLCV ingest pipeline |
| `signal_engine` | Signal generation + GPT validation |
| `auto_trader` | AutoTradingEngine (autonomous loop) |
| `scheduler` | Cron-based task orchestration |
| `discord_bot` | Discord interface (64 commands) |
| `api` | FastAPI REST + dashboard |
| `jupyter` | Research notebooks (dev profile) |

---

## Broker Support

| Broker | Status | Markets |
|--------|--------|---------|
| Paper | ✅ Default | No API key needed |
| Alpaca | ✅ | US equities + crypto |
| Futu (富途) | ✅ | HK / US equities |
| Interactive Brokers | ✅ | Global multi-asset |
| MetaTrader 5 | ✅ | Forex + CFDs |

---

## Running Tests

```bash
python -m pytest tests/test_vnext_truthful_surfaces.py \
                 tests/test_vnext_sprint2.py \
                 tests/test_vnext_sprint3.py \
                 tests/test_vnext_p1_review.py \
                 -c /dev/null -v
# Expected: 131 passed
```

---

## Roadmap

- [x] Sprint 1–3: Core 16 commits (A–P) — regime, signals, compare, options, brief, perf lab
- [x] P0 Review: 6 architecture fixes (singleton pattern, decoupled imports, TOML syntax)
- [x] P1 Review: 6 trust fixes (await bugs, deterministic hashing, trust strips, gross/net returns)
- [x] Public Readiness: GitHub Pages demo, real-time prices, search stock feature
- [ ] Symbol Dossier: full single-ticker research page (technicals + catalysts + risk)
- [ ] Historical Analog Engine: "10 most similar past setups" with forward return validation
- [ ] Daily Macro Brief: structured table (indicator, actual, consensus, surprise, regime impact)
- [ ] Operator Console: live system health, exposure, risk budget, provider status
- [ ] Artifact Archive: browse/replay prior day briefs, signals, regime snapshots

---

## ⚠️ Risk Disclaimer

**CC is a research and education tool, not financial advice.**

- All signals, scores, and recommendations are algorithmic outputs for informational purposes only.
- Past backtest performance does not guarantee future results.
- Synthetic/demo data is clearly labeled — never mistake it for live market data.
- Always apply your own judgment, risk management, and due diligence.
- The authors accept no liability for trading losses.

---

## License

MIT — see [LICENSE](LICENSE) for details.

---

<p align="center">
  <b>CC</b> — clarity · trust · auditability · decision compression
</p>
