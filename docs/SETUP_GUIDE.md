# 🛠️ Setup Guide — TradingAI Bot v6

Complete installation, configuration, and deployment walkthrough.

---

## Table of Contents

1. [Prerequisites](#1-prerequisites)
2. [Clone & Install](#2-clone--install)
3. [Environment Variables](#3-environment-variables)
4. [Database Setup (Optional)](#4-database-setup-optional)
5. [Start the Discord Bot](#5-start-the-discord-bot)
6. [Start the Web Dashboard (Optional)](#6-start-the-web-dashboard-optional)
7. [Connect a Broker](#7-connect-a-broker)
8. [Enable AI / GPT Features](#8-enable-ai--gpt-features)
9. [Discord Server Auto-Setup](#9-discord-server-auto-setup)
10. [Verify the Install](#10-verify-the-install)
11. [Production Deployment](#11-production-deployment)
12. [Troubleshooting](#12-troubleshooting)

---

## 1. Prerequisites

| Tool | Version | Required? | Purpose |
|------|---------|:---------:|---------|
| **Python** | 3.11+ | ✅ | Core runtime (tested 3.13.5) |
| **Discord Bot Token** | — | ✅ | Primary interface |
| **TA-Lib** | latest | 📌 Recommended | Technical indicators |
| PostgreSQL | 15+ | Optional | Historical persistence |
| Redis | 7+ | Optional | Cache / queue |
| Docker | 24+ | Optional | Container deployment |

### macOS

```bash
brew install python@3.13 ta-lib
# Optional:
brew install postgresql redis
```

### Ubuntu / Debian

```bash
sudo apt update && sudo apt install -y \
  python3 python3-venv python3-pip libta-lib-dev \
  postgresql redis-server  # optional
```

### Get a Discord Bot Token

1. Go to [Discord Developer Portal](https://discord.com/developers/applications)
2. Create Application → Bot → **Copy Token**
3. Under **OAuth2 → URL Generator**: select `bot` + `applications.commands`
4. Select permissions: Send Messages, Embed Links, Manage Channels, Manage Roles
5. Copy the invite URL → open it → add bot to your server

---

## 2. Clone & Install

```bash
git clone https://github.com/cheafi/Trading-bot-CC.git
cd TradingAI_Bot-main

python -m venv venv
source venv/bin/activate     # macOS / Linux
# venv\Scripts\activate      # Windows

# Install all dependencies at once
pip install -r requirements/base.txt \
            -r requirements/engine.txt \
            -r requirements/notifications.txt \
            -r requirements/api.txt \
            -r requirements/backtest.txt \
            -r requirements/ingestor.txt
```

### Key packages installed

| Package | Purpose |
|---------|---------|
| `discord.py` | Discord bot framework |
| `yfinance` | Free market data (no API key needed) |
| `pandas` / `numpy` | Data manipulation |
| `ta-lib` | Technical indicators |
| `openai` | GPT analysis (optional) |
| `alpaca-py` | Broker integration (optional) |
| `fastapi` / `uvicorn` | Web dashboard (optional) |
| `pydantic` | Data models |

---

## 3. Environment Variables

Create `.env` in the project root:

```bash
cp .env.example .env    # if example exists, or create manually
```

### 🔴 Required

```env
DISCORD_BOT_TOKEN=your_discord_bot_token_here
```

### 🟡 Optional — AI Features

```env
# OpenAI
OPENAI_API_KEY=sk-your-key-here

# Or Azure OpenAI
AZURE_OPENAI_KEY=your-azure-key
AZURE_OPENAI_ENDPOINT=https://your-resource.openai.azure.com
AZURE_OPENAI_DEPLOYMENT=gpt-4
```

### 🟡 Optional — Broker

```env
# Alpaca (recommended — free paper trading)
ALPACA_API_KEY=your_key
ALPACA_SECRET_KEY=your_secret
ALPACA_BASE_URL=https://paper-api.alpaca.markets

# Interactive Brokers
IB_HOST=127.0.0.1
IB_PORT=7497
IB_CLIENT_ID=1

# Futu (HK / CN markets)
FUTU_HOST=127.0.0.1
FUTU_PORT=11111
```

### 🟡 Optional — Database

```env
POSTGRES_USER=tradingai
POSTGRES_PASSWORD=your_secure_password
POSTGRES_DB=tradingai
DATABASE_URL=postgresql://tradingai:your_secure_password@localhost:5432/tradingai
REDIS_URL=redis://localhost:6379/0
```

---

## 4. Database Setup (Optional)

The Discord bot runs fully without PostgreSQL — it uses yfinance for live data and in-memory state. Database is for historical persistence and expansion.

```bash
createdb tradingai
psql tradingai < init/postgres/01_init.sql
psql tradingai < init/postgres/02_pro_desk_upgrade.sql
```

Or with Docker:
```bash
docker-compose up -d postgres redis
```

---

## 5. Start the Discord Bot

```bash
source venv/bin/activate
python run_discord_bot.py
```

### Expected output

```
✅ TradingAI Bot connected as TradingAI Bot#XXXX
   Servers: Your Server Name
   Synced 52 slash commands
   🔄 Started 18 auto-pilot tasks
   🚨 Real-time alerts: prices(3min) + news(30min) + VIX(5min)
   ☀️ Smart morning: Asia(01UTC) + Europe(07UTC) + US(13:30UTC)
   🎯 Opportunity scanner: every 30min, score≥75 only
```

### Run in background (production)

```bash
nohup ./venv/bin/python run_discord_bot.py > /tmp/discord_bot.log 2>&1 &

# Monitor
tail -f /tmp/discord_bot.log

# Stop
pkill -f run_discord_bot.py
```

---

## 6. Start the Web Dashboard (Optional)

```bash
python run_dashboard.py
```

| URL | What |
|-----|------|
| `http://localhost:8000` | Dashboard UI |
| `http://localhost:8000/docs` | Interactive API docs (Swagger) |
| `http://localhost:8000/redoc` | Alternative API docs |

---

## 7. Connect a Broker

### Alpaca (Recommended)

1. Sign up at [alpaca.markets](https://alpaca.markets) (free)
2. Generate Paper Trading API keys
3. Add `ALPACA_API_KEY`, `ALPACA_SECRET_KEY`, `ALPACA_BASE_URL` to `.env`
4. Verify: `/portfolio` in Discord → shows live positions + P&L

### Paper Broker (Built-in)

If no broker is configured, `/buy` and `/sell` use the built-in paper broker.

### Interactive Brokers

1. Install TWS or IB Gateway
2. Enable API in TWS settings
3. Set `IB_HOST`, `IB_PORT`, `IB_CLIENT_ID` in `.env`

---

## 8. Enable AI / GPT Features

GPT enhances analysis but is **optional** — the bot works fully without it.

**With GPT:** `/ai`, `/advise`, `/why` give GPT-powered narrative analysis, signal validation, and reasoning.

**Without GPT:** All technical analysis, scanning, scoring, alerts, and dashboards work normally.

---

## 9. Discord Server Auto-Setup

When the bot joins a server, it auto-creates:

**📊 TRADING category:**
`#daily-brief` · `#signals` · `#swing-trades` · `#breakout-setups`

**📈 MARKETS category:**
`#momentum-alerts` · `#ai-signals` · `#bot-commands` · `#trading-chat`

**🔧 ADMIN category:**
`#admin-log`

**Roles:** 🟢 Trader · 🔴 Admin · 🟡 VIP

Re-run anytime with `/setup`.

---

## 10. Verify the Install

| Test Command | Expected Result |
|--------------|-----------------|
| `/status` | ✅ All systems green |
| `/price AAPL` | Live price + chart info |
| `/market` | SPY / QQQ / DIA / VIX |
| `/dashboard` | 3-embed mega dashboard |
| `/watchlist add TSLA` | Ticker added confirmation |
| `/alert AAPL above 200` | Alert registered |
| `/my_alerts` | Shows your active alerts |

Check `#admin-log` for the health check embed (posts every 30 min).

---

## 11. Production Deployment

### Option A — Background Process (simplest)

```bash
nohup ./venv/bin/python run_discord_bot.py > /tmp/discord_bot.log 2>&1 &

# Auto-restart on crash (crontab)
crontab -e
*/5 * * * * pgrep -f run_discord_bot.py || cd /path/to/project && nohup ./venv/bin/python run_discord_bot.py >> /tmp/discord_bot.log 2>&1 &
```

### Option B — systemd (Linux server)

```ini
# /etc/systemd/system/tradingai.service
[Unit]
Description=TradingAI Discord Bot
After=network.target

[Service]
Type=simple
User=ubuntu
WorkingDirectory=/home/ubuntu/TradingAI_Bot-main
ExecStart=/home/ubuntu/TradingAI_Bot-main/venv/bin/python run_discord_bot.py
Restart=always
RestartSec=10
Environment=PYTHONUNBUFFERED=1

[Install]
WantedBy=multi-user.target
```

```bash
sudo systemctl enable tradingai && sudo systemctl start tradingai
sudo journalctl -u tradingai -f
```

### Option C — Docker

```bash
docker-compose up -d
```

---

## 12. Troubleshooting

| Problem | Solution |
|---------|----------|
| Bot won't start | `python -c "import ast; ast.parse(open('src/discord_bot.py').read()); print('OK')"` |
| Token error | Verify `DISCORD_BOT_TOKEN` is set in `.env` |
| 0 commands synced | Re-invite bot with `applications.commands` scope, wait 1 min |
| No auto-posts | Check channel names exist; run `/setup` |
| No market data | `python -c "import yfinance as yf; print(yf.Ticker('AAPL').fast_info)"` |
| Import errors | `pip install -r requirements/base.txt -r requirements/engine.txt -r requirements/notifications.txt` |

### ⚠️ Important: Keep Both Bot Files in Sync

```bash
cp src/discord_bot.py src/notifications/discord_bot.py
```

The canonical source is `src/discord_bot.py`. The launcher imports from `src/notifications/discord_bot.py`. Always sync after editing.

---

## Quick Reference Card

| Action | Command |
|--------|---------|
| Start bot | `python run_discord_bot.py` |
| Background bot | `nohup ./venv/bin/python run_discord_bot.py > /tmp/discord_bot.log 2>&1 &` |
| Stop bot | `pkill -f run_discord_bot.py` |
| View logs | `tail -f /tmp/discord_bot.log` |
| Start dashboard | `python run_dashboard.py` |
| Sync bot files | `cp src/discord_bot.py src/notifications/discord_bot.py` |
| Syntax check | `python -c "import ast; ast.parse(open('src/discord_bot.py').read()); print('OK')"` |

---

_Last updated: March 2026 · v6 Pro Desk Edition_
