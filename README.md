# TradingAI Bot — v6 Pro Desk

> 24/7 automated trading intelligence platform delivered entirely through Discord.
> **54 slash commands · 23 background tasks · 50-stock universe · self-learning AI engine.**

---

## At a Glance

| Feature | Detail |
|---------|--------|
| **Interface** | Discord only — all intelligence via rich embeds + buttons |
| **Commands** | 54 slash commands across 8 categories |
| **Auto-tasks** | 23 background tasks running 24/7 |
| **Universe** | 50 US stocks + 10 crypto + 3 Asia indices + 11 sectors |
| **Strategies** | SWING · BREAKOUT · MOMENTUM · MEAN_REVERSION |
| **AI Engine** | Regime detection · walk-forward backtest · param sweep · self-correction |
| **Signal Cards** | WHY BUY · WHY THIS STOP · ML regime check on every signal |
| **News** | All 50 stocks tracked every 15 min · headlines auto-attached to alerts |
| **Data** | yfinance (no paid API) + optional OpenAI for narrative |
| **Language** | Python 3.13 · discord.py · scikit-learn · pandas · numpy |

---

## System Architecture

```
┌─────────────────────────────────────────────────────────────────────┐
│                   DISCORD INTERFACE (54 commands)                    │
│  /why  /backtest  /best_strategy  /analyze  /market  /news  ...     │
└──────────────────────────┬──────────────────────────────────────────┘
                           │
┌──────────────────────────▼──────────────────────────────────────────┐
│                  src/discord_bot.py (5,596 lines)                    │
│  ┌─────────────┐  ┌────────────────┐  ┌────────────────────────┐   │
│  │  23 Auto    │  │  Signal Card   │  │  Price Alert Engine    │   │
│  │  Tasks      │  │  Builder       │  │  3-min · 50 tickers    │   │
│  │  (24/7)     │  │  WHY BUY       │  │  + news auto-attach    │   │
│  │             │  │  WHY STOP      │  │                        │   │
│  │             │  │  ML Check      │  │                        │   │
│  └─────────────┘  └────────────────┘  └────────────────────────┘   │
└──────┬──────────────────┬──────────────────────┬───────────────────┘
       │                  │                      │
┌──────▼──────────┐ ┌─────▼──────────┐  ┌───────▼─────────────────┐
│ Strategy        │ │ Signal Engine  │  │ Data Layer              │
│ Optimizer       │ │ (1,244 lines)  │  │ yfinance (50 stocks)    │
│ (936 lines)     │ │                │  │ Yahoo Finance news      │
│                 │ │ Swing/Breakout │  │ Optional: OpenAI GPT    │
│ 4 backtests     │ │ Momentum/MR    │  └─────────────────────────┘
│ Walk-forward    │ │ Score 0–100    │
│ Param sweep     │ │ WHY BUY/STOP   │
│ 9 regimes       │ │ GPT validate   │
│ Self-correct    │ └────────────────┘
└─────────────────┘
```

---

## 24-Hour Automation Timeline

```
UTC    HKT    Task
────── ────── ──────────────────────────────────────────────────────
00:00  08:00  📰 Auto News Feed · ₿ Crypto Pulse · 🌍 Global Update
01:00  09:00  ☀️ ASIA MORNING BRIEF · 🌏 Asia Preview
       ↓      🚨 Price Alerts (3 min · ALL 50 stocks)
       ↓      📰 Ticker News (15 min · rotating 50-stock coverage)
       ↓      ⚠️ VIX Fear Monitor (5 min) · 💚 Health Check (30 min)
       ↓      📡 Market Pulse (15 min · extended hours)
07:00  15:00  ☀️ EUROPE MORNING BRIEF
08:00  16:00  🔥 Movers (30 min) · 🏭 Sector Heatmap (60 min)
       ↓      🐋 Whale Scan (45 min · 8–22 UTC)
       ↓      🤖 AI Strategy Learn (6 h · weekdays) → #ai-signals
       ↓      🔄 Swing Scan (6 h) · 🚀 Breakout (4 h) · ⚡ Momentum (2 h)
13:30  21:30  ☀️ US PRE-MARKET BRIEF · 📊 v6 Morning Decision Memo
       ↓      🤖 AI Signal Scan (3 h) · 🎯 Opportunity Scanner (30 min)
20:10  04:10  🌙 EOD SCORECARD
21:00  05:00  Sunday: 📅 WEEKLY RECAP

ALWAYS ON: 🚨 Alerts(3m) · ⚠️ VIX(5m) · 📰 News(30m) · 📰 Tickers(15m) · 💚 Health(30m)
```

---

## All 54 Slash Commands

### 📊 Market Intelligence (15)

| Command | What It Does |
|---------|-------------|
| `/market` | Full dashboard — indices, VIX, breadth, futures |
| `/market_now` | Instant snapshot — SPY/QQQ/DIA/IWM/VIX |
| `/premarket` | Pre-market movers + overnight futures |
| `/sector` | 11-sector heatmap with performance bars |
| `/macro` | Gold, Oil, Bonds, Dollar, BTC |
| `/movers` | Top gainers + losers from watchlist |
| `/crypto` | Top 6 crypto with sentiment gauge |
| `/asia` | Nikkei, Hang Seng, Shanghai |
| `/japan` | Nikkei detail |
| `/hk` | Hang Seng detail |
| `/btc` | Bitcoin deep-dive |
| `/daily` | Comprehensive daily summary |
| `/daily_update` | Trigger fresh market update |
| `/risk` | Risk regime + VIX + allocation guidance |
| `/whale` | Unusual volume scan across 50 stocks |

### 🤖 AI Analysis (9)

| Command | What It Does |
|---------|-------------|
| `/ai TICKER` | GPT-powered analysis — trend, sentiment, thesis |
| `/analyze TICKER` | Deep technical analysis — all indicators |
| `/advise TICKER` | Buy/hold/sell recommendation + reasoning |
| `/score TICKER` | Signal quality score 0–100 with breakdown |
| `/compare A B` | Side-by-side comparison of two tickers |
| `/levels TICKER` | Key support, resistance, pivot levels |
| `/why TICKER` | Full conviction engine: score −100→+100, WHY BUY, WHY THIS STOP, analyst consensus, news |
| `/price TICKER` | Real-time quote with extended-hours |
| `/quote TICKER` | Compact price quote |

### 🎯 Signals & Scanners (9)

| Command | What It Does |
|---------|-------------|
| `/signals` | Latest AI trading signals overview |
| `/scan STRATEGY` | Run named scanner (vcp/breakout/dip/momentum/swing) |
| `/breakout` | Consolidation breakout scanner |
| `/dip` | Dip-buying opportunity scanner |
| `/momentum` | High-momentum stocks scanner |
| `/swing` | Swing pullback setups |
| `/squeeze` | Bollinger Band squeeze setups |
| `/setup TICKER` | Full setup analysis for one ticker |
| `/news TICKER` | Latest news + sentiment |

### 📈 Backtest & Strategy AI (3)

| Command | What It Does |
|---------|-------------|
| `/backtest TICKER [PERIOD]` | 4 strategies ranked · walk-forward OOS · param sweep · cross-check · Monte Carlo · regime diagnosis |
| `/best_strategy TICKER` | Which strategy wins in current regime? (fast 6mo) |
| `/strategy_report` | Live self-learning accuracy + score correction log |

### 💼 Portfolio & P&L (5)

| Command | What It Does |
|---------|-------------|
| `/portfolio` | Full portfolio — positions, P&L, exposure |
| `/positions` | Open positions with live P&L |
| `/pnl` | P&L — today, week, month, all-time |
| `/buy TICKER` | Paper buy with position size guidance |
| `/sell TICKER` | Paper sell with exit analysis |

### 📋 Reports & Dashboard (4)

| Command | What It Does |
|---------|-------------|
| `/dashboard` | Interactive full market dashboard |
| `/report` | Comprehensive formatted report |
| `/stats` | Bot statistics — signals, accuracy, uptime |
| `/status` | Status of all 23 background tasks |

### 🔔 Alerts & Watchlist (4)

| Command | What It Does |
|---------|-------------|
| `/alert TICKER above/below PRICE` | Set a personal price alert |
| `/my_alerts` | View all your active alerts |
| `/clear_alerts` | Remove all your alerts |
| `/watchlist [add/remove/clear] [TICKER]` | Manage personal watchlist (up to 20) |

### ⚙️ Admin & Utilities (5)

| Command | What It Does |
|---------|-------------|
| `/help` | Interactive guide with navigation buttons |
| `/announce MESSAGE` | Admin broadcast |
| `/pin MESSAGE` | Pin a message |
| `/purge N` | Delete last N messages |
| `/slowmode SECONDS` | Set channel slowmode |

---

## Signal Card Anatomy

```
┌──────────────────────────────────────────────────────────────┐
│  🟢 LONG  NVDA  —  $142.50  [BREAKOUT]                      │
│  🟢 HIGH CONVICTION • Score 87/100  ████████░░               │
│  • 🚀 BREAKING OUT above $141.00                             │
│  • 🔥 Volume 2.3x avg — institutional demand                 │
│  • ✅ Above SMA50 — trend intact                             │
├──────────────────────────────────────────────────────────────┤
│  🎯 Target: $162.00  │  🛑 Stop: $132.00  │  R:R: 2.4:1    │
│  RSI: ⚪ 58          │  Rel Vol: 🔥 2.3x  │  Hold: 1-4wk   │
├──────────────────────────────────────────────────────────────┤
│  🛑 Invalidation: Close below $132.00 (consolidation low)   │
│  🟢 WHY BUY  — narrative explaining the specific edge       │
│  🛑 WHY THIS STOP — exact placement logic + risk %          │
│  🧠 ML Regime Check — backtest score · regime fit           │
│  💰 Liquidity: ✅ $42.1M/day  │  Stop/ATR: 1.5×            │
│  [Deep Analysis]  [Position Sizer]  [Set Alert]              │
└──────────────────────────────────────────────────────────────┘
```

---

## Tracked Universe (50 US stocks)

```
Mega-cap : AAPL MSFT GOOGL AMZN NVDA META TSLA
Semi     : AMD INTC AVGO MU ARM SMCI QCOM
Software : CRM ADBE NOW SNOW PLTR NET CRWD PANW
Finance  : JPM BAC GS V MA COIN SOFI HOOD
Consumer : NFLX DIS UBER ABNB SHOP ROKU SNAP BABA
Health   : LLY JNJ MRNA ABBV
Spec/Vol : RIVN NIO MARA GME DKNG PYPL LULU
```

Plus: 10 crypto · 3 Asia indices · SPY/QQQ/DIA/IWM/^VIX · 11 S&P sectors

---

## Key Source Files

| File | Lines | Purpose |
|------|------:|---------|
| `src/discord_bot.py` | 5,596 | All 54 commands + 23 tasks |
| `src/engines/strategy_optimizer.py` | 936 | AI backtest engine (new) |
| `src/engines/signal_engine.py` | 1,244 | Core signal generation |
| `src/engines/gpt_validator.py` | 1,058 | GPT narrative + validation |
| `src/algo/indicators.py` | 1,272 | Technical indicator library |
| `src/core/models.py` | 766 | Pydantic type system |

---

## Quick Start

```bash
git clone https://github.com/cheafi/Trading-bot-CC
cd TradingAI_Bot-main
python -m venv venv && source venv/bin/activate
pip install -r requirements/base.txt
cp .env.example .env        # add DISCORD_BOT_TOKEN
python run_discord_bot.py
```

Full setup: [docs/SETUP_GUIDE.md](docs/SETUP_GUIDE.md) · Full command reference: [docs/BOT_GUIDE.md](docs/BOT_GUIDE.md)

---

> ⚠️ **Risk Notice** — All signals and analysis are for educational purposes only. Past backtest performance does not guarantee future results. Always apply your own judgement and risk management.
