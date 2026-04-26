<p align="center">
  <img src="https://img.shields.io/badge/Python-3.11+-3776AB?logo=python&logoColor=white" />
  <img src="https://img.shields.io/badge/FastAPI-0.104+-009688?logo=fastapi&logoColor=white" />
  <img src="https://img.shields.io/badge/Discord-Primary_Interface-5865F2?logo=discord&logoColor=white" />
  <img src="https://img.shields.io/badge/License-MIT-blue" />
  <img src="https://img.shields.io/badge/Status-Beta_(v9.0)-orange" />
</p>

# CC — Regime-Aware Market Intelligence Platform

> **An open-source, Discord-first AI agent that turns market data into explainable, risk-aware signals — so every trade idea has a clear _why_, a transparent _confidence level_, and an honest _what could go wrong_.**

<p align="center">
  <a href="https://cheafi.github.io/Trading-bot-CC/">🔗 Live Demo (Synthetic Data)</a> ·
  <a href="docs/ARCHITECTURE.md">📐 Architecture</a> ·
  <a href="docs/SETUP_GUIDE.md">🚀 Setup Guide</a> ·
  <a href="docs/BOT_GUIDE.md">📖 Command Reference</a>
</p>

---

## What CC Is

CC is a **financial intelligence and monitoring platform** that:

- Detects market regime (bull/bear/sideways/crisis) and adjusts behavior
- Scores trade setups across 4 strategy families (swing, breakout, momentum, mean reversion)
- Delivers alerts to Discord with confidence scores, entry/stop/target, and plain-language reasoning
- Tracks portfolio exposure, risk, and performance
- Supports paper and live broker connections (Alpaca, Futu, IBKR, MT5)

**CC is a research and decision-support tool. It is not financial advice, not a guaranteed profit system, and not a replacement for your own judgment.**

## Who It's For

- Traders and investors who want structured, explainable market intelligence
- Developers who want to build on an open-source quant/trading platform
- Teams who want a Discord-based monitoring and alerting system

## Who It's NOT For

- Anyone expecting guaranteed profits or zero-risk automation
- Anyone unwilling to do their own due diligence
- Anyone looking for a "set and forget" trading bot — CC requires active engagement and judgment

---

## Current Status — Honest Assessment

| Component | Maturity | Notes |
|---|---|---|
| Regime detection | ⚙️ Beta | 9-state classifier, needs more validation |
| Signal scoring | ⚙️ Beta | 4 strategies, research-quality — not battle-tested at scale |
| Discord bot | ✅ Functional | 64 slash commands, rich embeds |
| Paper trading | ✅ Functional | Safe for simulation and learning |
| Live broker execution | ⚠️ Experimental | Use at your own risk with small capital first |
| Options research | ⚠️ Synthetic only | No live options chain — demo/learning only |
| AI/LLM narratives | ⚠️ Experimental | May hallucinate — always verify |
| Backtesting | ⚙️ Beta | Walk-forward + Monte Carlo, needs more robustness testing |
| **Phase 9 Engines** | | |
| Structure Detector | ✅ Functional | HH/HL trend classification, S/R levels, breakout quality |
| Entry Quality Gate | ✅ Functional | Pre-trade timing, structure, and R:R assessment |
| Breakout Monitor | ✅ Functional | Post-signal tracking with persistence |
| Portfolio Gate | ✅ Functional | Sector concentration, correlation, max exposure |
| Earnings Calendar | ✅ Functional | Real earnings dates via yfinance, blackout zones |
| Fundamental Data | ✅ Functional | Live ROE, P/E, moat detection, quality scoring |
| Decision Journal | ✅ Functional | Persistent decision logging + expert accuracy |

---

## 6 Decision Surfaces

| # | Surface | What It Answers | Data Mode |
|---|---------|----------------|-----------|
| 🎯 | **Regime** | "What state is the market in? What's the playbook?" | Live · Paper · Synthetic |
| 📡 | **Signals** | "Which setups deserve attention today, and _why_?" | Live · Backtest · Synthetic |
| 🔍 | **Symbol Dossier** | "Full picture on one ticker — technicals, catalysts, risk." | Live · Synthetic |
| 📋 | **Portfolio Brief** | "What happened today? What needs action?" | Live · Paper · Synthetic |
| 🔮 | **Options Lab** | "Which contracts have edge?" | Synthetic only |
| 📊 | **Track Record** | "Show win rate, drawdown, sample size." | Backtest · Paper |

> **Every surface shows a trust strip** — you always see: data mode (LIVE / PAPER / BACKTEST / SYNTHETIC), source, freshness, and assumptions.

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
              └────────────────┘  └──────────────┘  └─────────────────┘
                           │             │              │
                    ┌──────▼─────────────▼──────────────▼─────────┐
                    │           DATA & BROKER LAYER                │
                    │  yfinance · Alpaca · Futu · IBKR · MT5      │
                    │  Redis cache · Postgres persistence          │
                    └─────────────────────────────────────────────┘
```

---

## Quick Start

### Option A — Discord Bot Only (fastest)

```bash
git clone https://github.com/cheafi/Trading-bot-CC && cd Trading-bot-CC
python -m venv venv && source venv/bin/activate
pip install -r requirements/base.txt
cp .env.example .env       # Add DISCORD_BOT_TOKEN (minimum required)
python run_discord_bot.py
```

### Option B — API + Dashboard

```bash
pip install -r requirements/base.txt
python run_bot.py          # FastAPI on localhost:8000
```

### Option C — Full Stack (Docker Compose)

```bash
cp .env.example .env       # Fill in ALL credentials, change default passwords
docker compose up -d       # API, Discord, Postgres, Redis, scheduler, ...
```

📖 Full setup: [docs/SETUP_GUIDE.md](docs/SETUP_GUIDE.md)

> **⚠️ Security:** Never commit `.env`. Use paper/sandbox mode first. See [SECURITY.md](SECURITY.md).

---

## Discord Alert Format

CC alerts in Discord include structured, actionable information:

```
🟢 AAPL — Swing Long (Score: 78/100)
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

Strategy:    Swing · Pullback to rising 21 EMA
Confidence:  ██████░░ 78%  (Grade: B+)
Regime:      🟢 Bull Trending

Entry Zone:  $185.20 – $186.00
Stop:        $181.50 (–2.0%)
Target 1:    $192.00 (+3.7%)
Target 2:    $198.00 (+6.9%)

Why Buy:     Pullback to 21 EMA on declining volume in
             uptrend. RSI 52 — not overbought. Sector
             (Tech) showing relative strength.
Why Not:     Earnings in 12 days — event risk. Broad
             market breadth narrowing.
Invalidation: Close below $181.50 on volume.

⏱ 14:32 ET · LIVE · yfinance · Freshness: <1min
```

See [docs/DISCORD_ALERTS.md](docs/DISCORD_ALERTS.md) for the full alert design guide.

---

## Strategy Styles

CC supports (or plans to support) these strategy families:

| Style | Status | Key Filters |
|-------|--------|-------------|
| **Swing** | ✅ Active | Pullback quality, trend context, holding 3–15 days |
| **Breakout** | ✅ Active | Volume expansion, base quality, false-breakout filters |
| **Momentum** | ✅ Active | Relative strength, acceleration, regime alignment |
| **Mean Reversion** | ✅ Active | Only in sideways regimes, volatility-adjusted |
| **VCP** | 🔄 Planned | Contraction quality, pivot detection, volume dry-up |
| **Trend Following** | 🔄 Planned | Trend persistence, pullback entries vs late chasing |
| **Event-Driven** | 🔄 Planned | Earnings, macro releases, catalyst timing |
| **Sector Rotation** | 🔄 Planned | Money flow, relative strength across sectors |

Each alert labels its strategy style so you know _what type_ of setup generated it.

---

## Broker Support

| Broker | Status | Markets | Notes |
|--------|--------|---------|-------|
| Paper | ✅ Default | All | No API key needed. Start here. |
| Alpaca | ✅ | US equities + crypto | Paper mode available |
| Futu (富途) | ✅ | HK / US equities | Requires FutuOpenD locally |
| Interactive Brokers | ✅ | Global multi-asset | Requires TWS/Gateway |
| MetaTrader 5 | ✅ | Forex + CFDs | Windows only |

> **⚠️ Live trading is experimental.** Start with paper mode. Small positions. Your own risk management. See [SECURITY.md](SECURITY.md) for credential safety.

---

## Data Coverage

| Market | Tickers | Source | Delay |
|--------|---------|--------|-------|
| US Equities | ~2,750 | yfinance | ~1 min (live) |
| Hong Kong | ~78 | yfinance | 15-min delayed |
| Japan | ~60 | yfinance | 15-min delayed |
| Crypto | ~63 | yfinance | Real-time |
| Macro / Indices | 20+ | yfinance | ~1 min |

> **Honest about limits:** yfinance is free but rate-limited with 15-min delay on international markets. CC labels data freshness on every alert and degrades gracefully when data is stale.

---

## Project Structure

```
src/
├── algo/           # Trading strategies (swing, breakout, momentum, mean reversion)
├── api/            # FastAPI REST endpoints + dashboard templates
├── backtest/       # Walk-forward backtesting with Monte Carlo
├── brokers/        # Broker integrations (Paper, Alpaca, Futu, IBKR, MT5)
├── core/           # Shared models, config, risk limits, errors
├── engines/        # Signal engine, auto-trading engine, regime router
├── ingestors/      # Market data and news ingestion
├── ml/             # ML models (regime classification, quality gate)
├── notifications/  # Discord bot (primary), embeds, formatters, tasks
├── performance/    # Performance tracking and attribution
├── research/       # Research artifact generation
├── scanners/       # Market scanners and screeners
├── scheduler/      # Background task scheduling
├── services/       # Shared services (market data, context, options)
└── strategies/     # Strategy configuration and registry
```

---

## Running Tests

```bash
python -m pytest tests/ -v --tb=short -c /dev/null
```

---

## Contributing

See [CONTRIBUTING.md](CONTRIBUTING.md) for setup, standards, and workflow.

## Security

See [SECURITY.md](SECURITY.md) for secrets handling, least-privilege guidance, and responsible disclosure.

## Roadmap

See [ROADMAP.md](ROADMAP.md) for planned improvements and priorities.

## Changelog

See [CHANGELOG.md](CHANGELOG.md) for version history.

---

## ⚠️ Disclaimer

**CC is a research, education, and decision-support tool. It is not financial advice.**

- All signals, scores, and narratives are algorithmic outputs for informational purposes only.
- Past backtest performance does not guarantee future results.
- Synthetic/demo data is clearly labeled — never mistake it for live market data.
- AI/LLM outputs may contain errors or hallucinations — always verify independently.
- The platform may have bugs, produce incorrect signals, or miss important information.
- You are solely responsible for your own trading and investment decisions.
- Always apply your own judgment, risk management, and due diligence.
- The authors accept no liability for trading losses or decisions made using this platform.
- This software is provided "as is" under the MIT License.

---

## License

MIT — see [LICENSE](LICENSE) for details.

---

<p align="center">
  <b>CC</b> — clarity · discipline · risk-awareness · better decisions
</p>
