# Setup Guide

> Full installation and deployment guide for TradingAI Bot v6 Pro Desk.

---

## Prerequisites

| Requirement | Version | Notes |
|------------|---------|-------|
| Python | 3.11 + | Tested on 3.13.5 |
| Discord Bot Token | — | Required |
| OpenAI API Key | — | Optional — enables GPT narratives |
| PostgreSQL | 14 + | Optional — enables persistence |
| Git | any | For cloning |

---

## Installation

### 1. Clone & Create Environment

```bash
git clone https://github.com/cheafi/Trading-bot-CC
cd TradingAI_Bot-main
python -m venv venv
source venv/bin/activate          # macOS / Linux
# venv\Scripts\activate           # Windows
```

### 2. Install Dependencies

```bash
# Minimum (bot only)
pip install -r requirements/base.txt

# Full (notifications + AI)
pip install -r requirements/notifications.txt
pip install -r requirements/engine.txt
```

### 3. Environment Variables

Create a `.env` file in the project root:

```dotenv
# ── REQUIRED ─────────────────────────────────────────────────
DISCORD_BOT_TOKEN=your_discord_bot_token_here

# ── OPTIONAL: GPT NARRATIVES ──────────────────────────────────
OPENAI_API_KEY=sk-...

# ── OPTIONAL: DATABASE ────────────────────────────────────────
DATABASE_URL=postgresql://user:pass@localhost:5432/tradingbot

# ── OPTIONAL: BROKER CONNECTIONS ─────────────────────────────
ALPACA_API_KEY=
ALPACA_SECRET_KEY=
ALPACA_BASE_URL=https://paper-api.alpaca.markets
IB_HOST=127.0.0.1
IB_PORT=7497
IB_CLIENT_ID=1
FUTU_HOST=127.0.0.1
FUTU_PORT=11111

# ── OPTIONAL: TELEGRAM ────────────────────────────────────────
TELEGRAM_BOT_TOKEN=
TELEGRAM_CHAT_ID=
```

### 4. Create Discord Bot

1. Go to [discord.com/developers/applications](https://discord.com/developers/applications)
2. **New Application** → name it **TradingAI Bot**
3. **Bot** tab → **Add Bot** → copy Token → paste into `.env`
4. Under **Privileged Gateway Intents** enable:
   - ✅ Message Content Intent
   - ✅ Server Members Intent
   - ✅ Presence Intent
5. **OAuth2** → **URL Generator**:
   - Scopes: `bot` + `applications.commands`
   - Bot permissions: `Send Messages`, `Use Slash Commands`, `Embed Links`, `Attach Files`, `Read Message History`, `Manage Messages`
6. Copy the generated URL → open in browser → invite to your server

---

## Running the Bot

### Option A — Local Development

```bash
source venv/bin/activate
python run_discord_bot.py
```

Expected startup output:
```
✅ Signal Engine loaded
✅ Strategy Optimizer ready
✅ Logged in as TradingAI Bot#8419
📋 Synced 54 commands to Trading CC
🚀 v6 Pro Desk online
```

### Option B — Background Process (macOS/Linux)

```bash
nohup python run_discord_bot.py > logs/bot.log 2>&1 &
echo $! > bot.pid
```

Stop it:
```bash
kill $(cat bot.pid)
```

### Option C — Docker

```bash
docker compose -f docker-compose.yml up -d telegram   # adapt for discord
```

Or build standalone:
```bash
docker build -f docker/Dockerfile.telegram -t tradingbot .
docker run -d --env-file .env tradingbot
```

---

## Channel Setup (Recommended)

Create these text channels in your Discord server for best experience:

| Channel | Purpose |
|---------|---------|
| `#general` | Main bot output, market updates |
| `#signals` | Trading signals from scanners |
| `#ai-signals` | ML strategy learning reports |
| `#alerts` | Price alerts + spike notifications |
| `#analysis` | Detailed ticker analysis |
| `#news` | Auto news feed (30 min) + ticker news |
| `#daily-reports` | Morning brief, EOD scorecard, weekly recap |
| `#crypto` | Crypto-specific signals and updates |

---

## Slash Command Sync

Commands sync automatically on first start. If they don't appear:

```
/sync          # Not available — sync is automatic at startup
```

Or restart the bot. Discord can take up to 1 hour to propagate new commands globally, but guild-synced commands appear instantly.

---

## First Run Checklist

- [ ] `.env` file created with `DISCORD_BOT_TOKEN`
- [ ] Bot invited to server with correct permissions
- [ ] `python run_discord_bot.py` runs without errors
- [ ] All 54 commands visible in Discord after typing `/`
- [ ] Type `/status` → all 23 tasks showing as Active
- [ ] Type `/market_now` → live prices appear

---

## Optional: Database

Without a database the bot operates fully in memory (signals cached in Python dicts). To enable persistence:

```bash
# Start Postgres
docker run -d --name tradingdb \
  -e POSTGRES_DB=tradingbot \
  -e POSTGRES_USER=trader \
  -e POSTGRES_PASSWORD=secret \
  -p 5432:5432 postgres:16

# Set DATABASE_URL in .env
DATABASE_URL=postgresql://trader:secret@localhost:5432/tradingbot

# Run schema migrations (if applicable)
psql $DATABASE_URL < init/postgres/01_init.sql
```

See [docs/SCHEMA.md](SCHEMA.md) for the full model catalog.

---

## Updating the Bot

```bash
git pull origin main
pip install -r requirements/base.txt   # picks up new deps
# restart the process
```

---

## Troubleshooting

| Symptom | Fix |
|---------|-----|
| `discord.errors.LoginFailure` | Check `DISCORD_BOT_TOKEN` in `.env` |
| Commands not showing in Discord | Wait up to 1 hour, or kick/re-invite bot |
| `ModuleNotFoundError` | `pip install -r requirements/base.txt` |
| `No data for TICKER` | yfinance throttled — wait 60s and retry |
| Price alerts not firing | Check `/status` — `realtime_price_alerts` must be Active |
| GPT responses missing | Set `OPENAI_API_KEY` in `.env` |
| Strategy Optimizer slow | Normal on first `/backtest` — caches results for 6h |

---

## Environment Files Reference

| File | Contents |
|------|---------|
| `requirements/base.txt` | discord.py, yfinance, scikit-learn, pandas, numpy |
| `requirements/notifications.txt` | openai, aiohttp extras |
| `requirements/engine.txt` | TA-lib, additional ML libs |
| `requirements/backtest.txt` | Backtesting utilities |
| `.env` | All secrets (never commit) |
| `run_discord_bot.py` | Entry-point launcher |

---

Back to [README.md](../README.md)
