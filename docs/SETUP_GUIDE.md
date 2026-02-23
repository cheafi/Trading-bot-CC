# TradingAI Bot v2.0 — Setup Guide

> AI-Powered Multi-Market Trading System covering US, HK, JP equities and Crypto.

---

## Table of Contents

1. [Prerequisites](#1-prerequisites)
2. [Clone & Install](#2-clone--install)
3. [Environment Variables](#3-environment-variables)
4. [Database Setup](#4-database-setup)
5. [Run Locally (Development)](#5-run-locally-development)
6. [Run with Docker (Production)](#6-run-with-docker-production)
7. [Connect Brokers](#7-connect-brokers)
8. [Connect Notifications](#8-connect-notifications)
9. [Enable AI Features](#9-enable-ai-features)
10. [24/7 Cloud Deployment](#10-247-cloud-deployment)
11. [Troubleshooting](#11-troubleshooting)

---

## 1. Prerequisites

| Tool        | Version  | Purpose                        |
|-------------|----------|--------------------------------|
| Python      | 3.11+    | Core runtime                   |
| PostgreSQL  | 15+      | Database (TimescaleDB recommended) |
| Redis       | 7+       | Cache, pub/sub, real-time      |
| Docker      | 24+      | Container deployment           |
| Node.js     | 18+      | (Optional) Frontend tooling    |

### System Libraries (macOS)

```bash
brew install postgresql redis ta-lib
brew services start postgresql
brew services start redis
```

### System Libraries (Ubuntu/Debian)

```bash
sudo apt install -y postgresql redis-server libta-lib-dev
```

---

## 2. Clone & Install

```bash
# Clone the repository
git clone https://github.com/your-org/TradingAI_Bot.git
cd TradingAI_Bot-main

# Create virtual environment
python -m venv .venv
source .venv/bin/activate  # macOS/Linux
# .venv\Scripts\activate   # Windows

# Install base dependencies
pip install -r requirements/base.txt

# Install specific service dependencies
pip install -r requirements/engine.txt       # Signal + Feature engine
pip install -r requirements/ingestor.txt     # Data ingestion
pip install -r requirements/api.txt          # Web dashboard
pip install -r requirements/notifications.txt # Telegram + Discord
pip install -r requirements/scheduler.txt    # Job scheduling
pip install -r requirements/backtest.txt     # Backtesting
```

---

## 3. Environment Variables

Create a `.env` file in the project root:

```bash
cp .env.example .env
```

### Required Variables

```env
# === Database ===
POSTGRES_USER=tradingai
POSTGRES_PASSWORD=your_secure_password
POSTGRES_DB=tradingai
DATABASE_URL=postgresql://tradingai:your_secure_password@localhost:5432/tradingai

# === Redis ===
REDIS_PASSWORD=your_redis_password
REDIS_URL=redis://:your_redis_password@localhost:6379/0

# === API Security ===
API_SECRET_KEY=your_random_secret_key_here
```

### Market Data (at least one required)

```env
# Alpaca (Free - recommended for US stocks + crypto)
ALPACA_API_KEY=your_key
ALPACA_SECRET_KEY=your_secret

# Polygon.io (US stocks, detailed data)
POLYGON_API_KEY=your_key
```

### AI / LLM (recommended)

```env
# Option A: Azure OpenAI (enterprise)
AZURE_TENANT_ID=...
AZURE_CLIENT_ID=...
AZURE_CLIENT_SECRET=...
AZURE_OPENAI_ENDPOINT=https://your-resource.openai.azure.com
AZURE_OPENAI_DEPLOYMENT=gpt-4o

# Option B: Standard OpenAI
OPENAI_API_KEY=sk-...
```

### Notifications (optional)

```env
# Telegram Bot
TELEGRAM_BOT_TOKEN=123456:ABC-DEF...
TELEGRAM_CHAT_ID=-100123456789

# Discord Bot
DISCORD_BOT_TOKEN=your_discord_bot_token
DISCORD_CHANNEL_NAME=Trading CC
```

### Broker Connections (optional)

```env
# MetaTrader 5 (Windows only)
MT5_LOGIN=12345678
MT5_PASSWORD=your_password
MT5_SERVER=MetaQuotes-Demo

# Futu (富途)
FUTU_HOST=127.0.0.1
FUTU_PORT=11111

# Interactive Brokers
IB_HOST=127.0.0.1
IB_PORT=7497
```

---

## 4. Database Setup

### Option A: Local PostgreSQL

```bash
# Create database
createdb tradingai

# Run schema migration
psql -d tradingai -f init/postgres/01_init.sql
```

### Option B: Docker (recommended)

```bash
docker compose up -d postgres redis
# Wait for health checks to pass
docker compose logs -f postgres
```

---

## 5. Run Locally (Development)

### Start the Web Dashboard

```bash
python run_dashboard.py
# → Open http://localhost:8000
```

### Start the Telegram Bot

```bash
python run_telegram_bot.py
```

### Start Individual Services

```bash
# Feature Engine
python -m src.engines.feature_engine

# Signal Engine
python -m src.engines.signal_engine

# Market Data Ingestor
python -m src.ingestors.market_data

# Auto Trading Engine (24/7)
python -m src.engines.auto_trading_engine
```

---

## 6. Run with Docker (Production)

### Start All Services

```bash
# Start core services (DB, Redis, API, Telegram, Engines)
docker compose up -d

# Start with monitoring (Prometheus + Grafana)
docker compose up -d

# Start development tools (pgAdmin, Jupyter)
docker compose --profile dev up -d
```

### Service Ports

| Service        | Port  | URL                          |
|----------------|-------|------------------------------|
| Web Dashboard  | 8000  | http://localhost:8000        |
| API Docs       | 8000  | http://localhost:8000/api/docs |
| Grafana        | 3000  | http://localhost:3000        |
| Prometheus     | 9090  | http://localhost:9090        |
| pgAdmin        | 5050  | http://localhost:5050        |
| Jupyter        | 8888  | http://localhost:8888        |

### View Logs

```bash
docker compose logs -f api
docker compose logs -f signal_engine
docker compose logs -f auto_trader
docker compose logs -f discord_bot
```

---

## 7. Connect Brokers

### Paper Trading (Default — No Setup Required)

Paper trading is always active. All signals will be executed in simulation mode.

### Alpaca (US Stocks + Crypto)

1. Sign up at [alpaca.markets](https://alpaca.markets)
2. Get API keys from the dashboard
3. Add to `.env`:
   ```env
   ALPACA_API_KEY=your_key
   ALPACA_SECRET_KEY=your_secret
   ```

### MetaTrader 5 (Forex/CFD)

1. Install MT5 terminal (Windows only)
2. Open a demo or live account
3. Add to `.env`:
   ```env
   MT5_LOGIN=12345678
   MT5_PASSWORD=your_password
   MT5_SERVER=MetaQuotes-Demo
   ```

### Interactive Brokers

1. Install TWS or IB Gateway
2. Enable API connections in TWS settings
3. Add to `.env`:
   ```env
   IB_HOST=127.0.0.1
   IB_PORT=7497
   ```

---

## 8. Connect Notifications

### Telegram Bot

1. Message [@BotFather](https://t.me/BotFather) on Telegram
2. Create a new bot with `/newbot`
3. Copy the bot token
4. Add the bot to your group/channel
5. Get chat ID: `https://api.telegram.org/bot<TOKEN>/getUpdates`
6. Add to `.env`:
   ```env
   TELEGRAM_BOT_TOKEN=123456:ABC-DEF...
   TELEGRAM_CHAT_ID=-100123456789
   ```

### Discord Bot

1. Go to [Discord Developer Portal](https://discord.com/developers/applications)
2. Create a new application → Bot → copy token
3. Enable **Message Content Intent** under Bot settings
4. Invite bot to server with proper permissions
5. Add to `.env`:
   ```env
   DISCORD_BOT_TOKEN=your_token
   DISCORD_CHANNEL_NAME=Trading CC
   ```

---

## 9. Enable AI Features

### GPT Signal Validation

Validates every trading signal through GPT before execution.
Requires OpenAI API key (see step 3).

### AI Advisor (Chain-of-Thought)

Provides daily market briefs with full reasoning chain.
Enabled automatically when OpenAI is configured.

### ML Trade Learning

Learns from trade outcomes to improve future predictions.
Starts collecting data immediately, begins predicting after 20 trades.

### Auto Trading Engine

24/7 autonomous execution with circuit breakers:
- **Daily loss limit**: 3% of portfolio
- **Max drawdown**: 10%
- **Consecutive loss limit**: 5 trades
- **Cooldown period**: 1 hour after circuit breaker

---

## 10. 24/7 Cloud Deployment

### Option A: Docker on VPS (Recommended)

```bash
# On your VPS (e.g., DigitalOcean, AWS EC2, Hetzner)
git clone https://github.com/your-org/TradingAI_Bot.git
cd TradingAI_Bot-main

# Create .env with your configuration
nano .env

# Start everything
docker compose up -d

# Enable auto-restart on reboot
docker update --restart=always $(docker ps -q)
```

### Option B: Railway / Render

1. Connect your GitHub repo
2. Set environment variables in the dashboard
3. Deploy — services auto-start

---

## 11. Troubleshooting

### Common Issues

| Issue | Solution |
|-------|----------|
| `ModuleNotFoundError` | Run `pip install -r requirements/base.txt` |
| Database connection failed | Check `DATABASE_URL` in `.env` |
| Redis connection refused | Start Redis: `redis-server` or `docker compose up redis` |
| TA-Lib import error | Install C library: `brew install ta-lib` (macOS) |
| MT5 not connecting | MT5 only works on Windows with terminal running |
| Discord bot not responding | Check bot token and channel permissions |
| Stale data warning | Verify market data API keys are set |

### Health Check

```bash
# Check API health
curl http://localhost:8000/health/live

# Check all services
docker compose ps

# View error logs
docker compose logs --tail=50 signal_engine
```

### Reset Everything

```bash
docker compose down -v  # WARNING: destroys all data
docker compose up -d
```

---

## Project Structure

```
TradingAI_Bot-main/
├── src/
│   ├── algo/          # Strategy library (VCP, momentum, swing, earnings)
│   ├── api/           # FastAPI web dashboard + REST API
│   ├── backtest/      # Backtesting frameworks
│   ├── brokers/       # Broker connectors (Futu, IB, MT5, Paper)
│   ├── core/          # Config, models, database
│   ├── engines/       # Signal generation, AI advisor, auto trading
│   ├── ingestors/     # Market data, news, social, real-time feeds
│   ├── ml/            # ML models, RL agents, trade learning
│   ├── notifications/ # Telegram, Discord, WhatsApp
│   ├── performance/   # P&L analytics, backtest analysis
│   ├── research/      # News/earnings/macro intelligence
│   ├── scanners/      # Pattern, sector, momentum scanners
│   └── scheduler/     # Job scheduling
├── docker/            # Dockerfiles for each service
├── init/postgres/     # Database schema
├── requirements/      # Pip dependencies per service
├── docs/              # Documentation
└── docker-compose.yml # Full stack orchestration
```

---

*For more details, see [ARCHITECTURE.md](ARCHITECTURE.md) and [SIGNALS.md](SIGNALS.md).*
