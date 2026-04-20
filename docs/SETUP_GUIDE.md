# Setup Guide

> Full installation and deployment guide for CC — Regime-Aware Market Intelligence Platform.

---

## Prerequisites

| Requirement | Version | Notes |
|------------|---------|-------|
| Python | 3.11+ | Tested on 3.13.5 |
| Discord Bot Token | — | Required |
| OpenAI API Key | — | Optional — enables GPT narratives |
| PostgreSQL | 14+ | Optional — enables persistence |
| Git | any | For cloning |

---

## Installation

### 1. Clone & Create Environment

```bash
git clone https://github.com/cheafi/Trading-bot-CC
cd Trading-bot-CC
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

```bash
cp .env.example .env
```

Edit `.env` and fill in at minimum:
- `DISCORD_BOT_TOKEN` — required
- `OPENAI_API_KEY` — optional, for AI narratives

See [`.env.example`](../.env.example) for all available settings with descriptions.

> ⚠️ **Never commit `.env` to version control.** It's already in `.gitignore`.

### 4. Create Discord Bot

1. Go to [discord.com/developers/applications](https://discord.com/developers/applications)
2. **New Application** → name it **CC Trading Bot**
3. **Bot** tab → **Add Bot** → copy Token → paste into `.env`
4. Under **Privileged Gateway Intents** enable:
   - ✅ Message Content Intent
   - ✅ Server Members Intent
   - ✅ Presence Intent
5. **OAuth2** → **URL Generator**:
   - Scopes: `bot` + `applications.commands`
   - Bot permissions: `Send Messages`, `Use Slash Commands`, `Embed Links`, `Attach Files`, `Read Message History`, `Manage Messages`
   - **Do NOT grant `Administrator`** — use least-privilege
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
✅ Logged in as CC Bot
📋 Synced 64 commands to CC
🚀 CC v6.1.0 online
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
docker compose up -d discord_bot
```

Or build standalone:
```bash
docker build -f docker/Dockerfile.discord -t tradingbot .
docker run -d --env-file .env tradingbot
```

---

## Broker Setup

CC defaults to **paper trading** (no broker API needed). To connect a real broker, follow the specific guide below.

> ⚠️ **Start with paper mode.** Test thoroughly before connecting live accounts. Live trading is experimental. You are responsible for all trades.

### Paper Broker (Default)

No configuration needed. Set in `.env`:
```dotenv
BROKER=paper
```
Simulates trades with $100,000 virtual capital. No API key required.

### Alpaca

1. Create an account at [alpaca.markets](https://alpaca.markets)
2. Generate API keys from the dashboard
3. **Start with paper trading:**
```dotenv
BROKER=alpaca
ALPACA_API_KEY=your_key
ALPACA_SECRET_KEY=your_secret
ALPACA_BASE_URL=https://paper-api.alpaca.markets
```
4. For live trading (use with extreme caution):
```dotenv
ALPACA_BASE_URL=https://api.alpaca.markets
```

**Safety notes:**
- Paper mode API keys are separate from live keys
- Never grant withdrawal permissions to API keys
- Monitor positions independently — do not rely solely on CC

### Futu (富途)

Futu requires FutuOpenD (a local gateway) running on your machine.

1. Download and install [FutuOpenD](https://www.futunn.com/download/openAPI)
2. Log in to FutuOpenD with your Futu account
3. Configure in `.env`:
```dotenv
BROKER=futu
FUTU_HOST=127.0.0.1
FUTU_PORT=11111
```

**Safety notes:**
- ⚠️ **Never expose FutuOpenD port (11111) to the public internet.** It has no authentication.
- FutuOpenD must be running whenever the bot needs broker access
- Use a Futu paper/demo account first
- Futu has rate limits — the bot handles these automatically
- Session may disconnect after inactivity — the bot attempts reconnection
- HK and US markets have different trading hours — the bot respects market schedules

### Interactive Brokers

Requires TWS (Trader Workstation) or IB Gateway running locally.

```dotenv
BROKER=ibkr
IB_HOST=127.0.0.1
IB_PORT=7497    # 7497 = paper, 7496 = live
IB_CLIENT_ID=1
```

**Safety notes:**
- ⚠️ **Use port 7497 (paper) first.** Port 7496 is live trading.
- Enable API connections in TWS: File → Global Configuration → API → Settings
- Set a maximum order size limit in TWS as a safety net
- TWS/Gateway must remain running — it disconnects after ~24h inactivity unless auto-restart is configured

### MetaTrader 5

Windows only. Requires MetaTrader 5 terminal installed.

```dotenv
BROKER=mt5
MT5_LOGIN=your_login
MT5_PASSWORD=your_password
MT5_SERVER=your_broker_server
```

**Safety notes:**
- Use a demo account first
- MT5 runs as a Windows application — not suitable for headless Linux servers
- Passwords are stored in `.env` — keep this file secure

### Multi-Broker Support

CC's broker abstraction (`src/brokers/base.py`) allows switching brokers by changing the `BROKER` environment variable. Only one broker is active at a time. Multi-broker simultaneous execution is not yet supported.

---

## Channel Setup (Recommended)

The bot auto-creates channels via `/setup`, or you can create these manually:

| Channel | Purpose |
|---------|---------|
| `#swing-trades` | 🔄 Swing setups (read-only, bot posts) |
| `#breakout-setups` | 🚀 Breakout alerts (read-only, bot posts) |
| `#momentum-alerts` | ⚡ Momentum signals (read-only, bot posts) |
| `#daily-brief` | ☀️ Morning memo + 🌙 EOD summary |
| `#bot-commands` | All slash commands here |
| `#trading-chat` | Discussion channel |
| `#admin-log` | Audit trail + bot status |

---

## First Run Checklist

- [ ] `.env` file created with `DISCORD_BOT_TOKEN`
- [ ] Bot invited to server with correct permissions
- [ ] `python run_discord_bot.py` runs without errors
- [ ] All commands visible in Discord after typing `/`
- [ ] Type `/status` → background tasks showing as Active
- [ ] Type `/market_now` → live prices appear
- [ ] Paper broker working → `/portfolio` returns virtual positions

---

## Optional: Database

Without a database the bot operates fully in memory. To enable persistence:

```bash
# Start Postgres
docker run -d --name tradingdb \
  -e POSTGRES_DB=tradingbot \
  -e POSTGRES_USER=trader \
  -e POSTGRES_PASSWORD=CHANGE_THIS_PASSWORD \
  -p 5432:5432 postgres:16

# Set DATABASE_URL in .env
# DATABASE_URL=postgresql://trader:CHANGE_THIS_PASSWORD@localhost:5432/tradingbot

# Run schema migrations
psql $DATABASE_URL < init/postgres/01_init.sql
```

> ⚠️ Change the default database password before any non-local deployment. Do not expose Postgres port to the public internet.

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
| Futu connection refused | Is FutuOpenD running? Check `FUTU_HOST` and `FUTU_PORT` |
| IB not connecting | Is TWS/Gateway running? Check API settings and port number |

---

## Environment Files Reference

| File | Contents |
|------|---------|
| `requirements/base.txt` | discord.py, yfinance, scikit-learn, pandas, numpy |
| `requirements/notifications.txt` | Discord, OpenAI for formatting |
| `requirements/engine.txt` | TA-lib, additional ML libs |
| `requirements/backtest.txt` | Backtesting utilities |
| `.env` | All secrets (never commit) |
| `config/default.yaml` | Default configuration (strategies, risk, scheduler) |
| `run_discord_bot.py` | Entry-point launcher |

---

Back to [README.md](../README.md)
