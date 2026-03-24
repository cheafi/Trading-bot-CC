<p align="center">
  <img src="https://img.shields.io/badge/v6-Pro%20Desk-gold?style=for-the-badge" />
  <img src="https://img.shields.io/badge/Python-3.11+-3776AB?style=for-the-badge&logo=python&logoColor=white" />
  <img src="https://img.shields.io/badge/Discord-Bot-5865F2?style=for-the-badge&logo=discord&logoColor=white" />
  <img src="https://img.shields.io/badge/24%2F7-Automated-00C853?style=for-the-badge" />
</p>

# TradingAI Bot v6

**A 24/7 Discord-native market intelligence system** that monitors US equities, crypto, and global indices around the clock, delivering real-time alerts, AI-powered analysis, and structured trade setups across short, medium, and longer-term horizons — all inside Discord.

> ⚠️ **Risk Disclaimer** — This system is for educational and research purposes only. It does not constitute financial advice. Past performance does not guarantee future results. Trading involves substantial risk of loss. Never trade with money you cannot afford to lose. No win rate, ROI, or profit guarantee is expressed or implied.

---

## ⚡ At a Glance

```
┌─────────────────────────────────────────────────────────────────────┐
│                     TradingAI Bot v6 Pro Desk                       │
├──────────────────┬──────────────────────────────────────────────────┤
│  52 Commands     │  /dashboard /ai /signals /portfolio /alert ...   │
│  21 Auto-Tasks   │  price alerts · news · VIX · scans · reports    │
│  24/7 Coverage   │  US · Crypto · Asia · Europe · Macro            │
│  5 Brokers       │  Alpaca · IB · Futu · MT5 · Paper              │
│  6 Strategies    │  Momentum · Swing · Breakout · VCP · MR · Event │
│  3 Morning Briefs│  Asia 09:00 HKT · Europe 08:00 CET · US 9:30ET │
└──────────────────┴──────────────────────────────────────────────────┘
```

---

## 🔥 What Makes This Different

| Feature | Traditional Bot | TradingAI v6 |
|---------|-----------------|--------------|
| **Monitoring** | You run commands | 21 tasks run for you 24/7 |
| **Alerts** | Price crosses only | Spikes + VIX + whale + news + regime shifts |
| **Analysis** | Basic TA | Multi-strategy scoring + GPT validation |
| **Horizons** | Single timeframe | Short (intraday) · Medium (swing) · Long (position) |
| **Risk** | None built-in | Regime detection · VIX budgets · stop/target logic |
| **Global** | US hours only | Asia · Europe · US sessions covered |

---

## 🏗️ Core Capabilities

### 🚨 Real-Time Intelligence (runs without you touching anything)

| Task | Frequency | Coverage | Channel |
|------|-----------|----------|---------|
| **Price Spike/Crash Alerts** | Every 3 min | 30 stocks + 10 crypto + indices | `#momentum-alerts` |
| **VIX Fear Monitor** | Every 5 min | Volatility regime | `#daily-brief` |
| **News Feed** | Every 30 min | Top headlines via Yahoo Finance | `#daily-brief` |
| **Opportunity Scanner** | Every 30 min | Score ≥ 75 setups only | `#momentum-alerts` |
| **Whale / Volume Alerts** | Every 45 min | 3x+ avg volume detection | `#signals` |
| **User Price Alerts** | Every 3 min | Your `/alert` targets | DM + `#signals` |

### 📊 Scheduled Reports

| Report | When | What It Covers |
|--------|------|----------------|
| **🌏 Asia Morning Brief** | 01:00 UTC (09:00 HKT) | Regime + indices + macro + playbook |
| **🌍 Europe Morning Brief** | 07:00 UTC (08:00 CET) | European markets + global context |
| **🇺🇸 US Pre-Market Brief** | 13:30 UTC (09:30 ET) | Futures + risk assessment + strategy |
| **Market Pulse** | Every 15 min | SPY/QQQ/DIA/VIX snapshot |
| **Big Movers** | Every 30 min | Stocks moving ≥ 2% |
| **Sector Heatmap** | Hourly | All 11 S&P sectors |
| **Global Update** | Every 4 hr | Cross-session macro overview |
| **EOD Scorecard** | ~16:10 ET | Close regime + sector heat + breadth |
| **Weekly Recap** | Sunday | Full week summary |

### 🎯 Multi-Strategy Signal Scans

| Strategy | Scan Interval | Hold Window | Channel |
|----------|---------------|-------------|---------|
| **Momentum** | Every 2 hr | Days to 2 weeks | `#momentum-alerts` |
| **Swing** | Every 6 hr | 2–8 weeks | `#swing-trades` |
| **Breakout / VCP** | Every 4 hr | 1–4 weeks | `#breakout-setups` |
| **Combined AI Rank** | Every 3 hr | Mixed | `#ai-signals` |
| **Mean Reversion** | On-demand | Days | `/signals` |
| **Event-Driven** | On-demand | Event-specific | `/ai` |

---

## 🖥️ Command Reference

### 📈 Market Intelligence
| Command | Description |
|---------|-------------|
| `/dashboard` | **Mega command** — regime, portfolio, risk, markets, signals in 3 embeds |
| `/market_now` | Live regime scoreboard with risk budgets and strategy playbook |
| `/daily_update` | Full intelligence brief with delta deck and scenarios |
| `/market` | US indices overview |
| `/sector` | 11-sector performance heatmap |
| `/macro` | Gold, Oil, BTC, Bonds, Dollar |
| `/movers` | Top gainers and losers |
| `/news TICKER` | Latest headlines for a stock |
| `/premarket` | Futures snapshot |
| `/report` | On-demand morning or EOD report |

### 🔬 Deep Analysis
| Command | Description |
|---------|-------------|
| `/ai TICKER` | Full AI analysis — technicals + sentiment + narrative |
| `/analyze TICKER` | Technical breakdown — SMA, RSI, MACD, volume |
| `/advise TICKER` | Buy / Hold / Sell recommendation |
| `/score TICKER` | AI score 1–10 with component breakdown |
| `/compare A B` | Side-by-side comparison |
| `/levels TICKER` | Support and resistance levels |
| `/why TICKER` | Why is it moving? |

### 🎯 Signal Discovery
| Command | Description |
|---------|-------------|
| `/signals` | Latest AI-ranked trading signals |
| `/scan` | Run a fresh scan across strategies |
| `/momentum` | High-momentum stocks |
| `/swing` | Swing trade setups (2–10 days) |
| `/breakout` | Breakout candidates near highs |
| `/dip` | Dip-buying opportunities |
| `/whale` | Unusual volume / whale accumulation |
| `/squeeze` | Short squeeze candidates |

### 🌏 Multi-Market
| Command | Description |
|---------|-------------|
| `/asia` | Japan + HK + China dashboard |
| `/japan` | Japan market picks |
| `/hk` | Hong Kong market picks |
| `/crypto` | Crypto market dashboard |
| `/btc` | Bitcoin deep analysis |

### 💼 Portfolio & Trading
| Command | Description |
|---------|-------------|
| `/portfolio` | Full portfolio — value, positions, P&L, exposure |
| `/pnl` | Today's P&L with W/L breakdown |
| `/positions` | Open positions list |
| `/stats` | Trading statistics and performance metrics |
| `/risk TICKER` | Position sizing calculator |
| `/buy TICKER QTY` | Buy shares (paper/live) |
| `/sell TICKER QTY` | Sell shares (paper/live) |
| `/backtest` | Backtest a strategy |

### 🔔 Personal Monitoring
| Command | Description |
|---------|-------------|
| `/watchlist` | Add / remove / view your watchlist (20 per user) |
| `/alert TICKER above/below PRICE` | Set price alert — auto-monitored every 3 min |
| `/my_alerts` | View active and triggered alerts |
| `/clear_alerts` | Remove all your alerts |

### 🔧 Admin
| Command | Description |
|---------|-------------|
| `/setup` | Re-run full server channel/role setup |
| `/announce` | Post announcement to `#daily-brief` |
| `/status` | System connectivity check |

---

## 🚀 Quick Start

```bash
git clone https://github.com/cheafi/Trading-bot-CC.git
cd TradingAI_Bot-main

python -m venv venv && source venv/bin/activate

pip install -r requirements/base.txt -r requirements/engine.txt \
            -r requirements/notifications.txt -r requirements/api.txt

echo "DISCORD_BOT_TOKEN=your_token_here" > .env

python run_discord_bot.py
```

See [docs/SETUP_GUIDE.md](docs/SETUP_GUIDE.md) for the complete setup walkthrough.

---

## 📁 Project Structure

```
TradingAI_Bot-main/
├── run_discord_bot.py          # Discord bot launcher
├── run_dashboard.py            # Web dashboard launcher
├── src/
│   ├── discord_bot.py          # 4,800+ line canonical bot (52 cmds, 21 tasks)
│   ├── algo/                   # 6 strategy implementations + indicators
│   ├── engines/                # Signal, GPT, feature, quality engines
│   ├── brokers/                # Alpaca, IB, Futu, MT5, paper broker
│   ├── core/                   # Config, models, database
│   ├── api/                    # FastAPI dashboard + REST endpoints
│   ├── notifications/          # Discord bot runtime copy + report generator
│   ├── backtest/               # Backtesting framework
│   ├── ml/                     # ML / RL agents
│   └── ingestors/              # Market data, news, social ingestors
├── docs/                       # This documentation
├── init/postgres/              # Database migration scripts
├── requirements/               # Per-service dependency files
└── docker/                     # Container definitions
```

---

## 📚 Documentation

| Document | Description |
|----------|-------------|
| [Setup Guide](docs/SETUP_GUIDE.md) | Installation, config, first run, deployment |
| [Architecture](docs/ARCHITECTURE.md) | System design, data flow, layer breakdown |
| [Bot Guide](docs/BOT_GUIDE.md) | All 52 commands, workflows, channel map |
| [Signals](docs/SIGNALS.md) | Strategy logic, scoring, signal lifecycle |
| [Schema](docs/SCHEMA.md) | Data models, database design, persistence |
| [Backtesting](docs/BACKTESTING.md) | Evaluation metrics, testing framework |
| [Daily Reports](docs/DAILY_REPORT.md) | Report types, schedules, content format |

---

## 🔄 Automation Timeline (24-Hour View)

```
UTC   HKT   What Fires
───── ───── ──────────────────────────────────────────
00:00 08:00  Crypto pulse · Global update · News
01:00 09:00  ☀️ ASIA MORNING BRIEF · Asia preview
04:00 12:00  Crypto pulse · Global update
07:00 15:00  ☀️ EUROPE MORNING BRIEF
08:00 16:00  Market pulse begins · Movers · Sectors · Whale scan
13:00 21:00  Breakout scan · Momentum scan · AI signal scan
13:30 21:30  ☀️ US PRE-MARKET BRIEF · Morning brief
16:00 00:00  Crypto pulse · Global update
20:10 04:10  🌙 EOD SCORECARD
21:00 05:00  Sunday: Weekly recap
22:00 06:00  Session tasks wind down

Always running: Price alerts (3min) · VIX (5min) · News (30min)
              Opportunities (30min) · Health (30min) · Presence (5min)
```

---

_Last updated: March 2026 · v6 Pro Desk Edition_
