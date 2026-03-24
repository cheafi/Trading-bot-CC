# 🤖 Discord Bot Guide — TradingAI Bot v6

The complete reference for all 52 slash commands, 21 background tasks, automated channels, and recommended workflows.

---

## Quick Start — 7 Essential Commands

| Command | What You Get |
|---------|-------------|
| `/dashboard` | Full trading terminal — regime + portfolio + markets + signals |
| `/market_now` | Live regime scoreboard with risk budgets |
| `/ai TICKER` | Deep AI analysis with narrative reasoning |
| `/signals` | Latest ranked trade setups |
| `/portfolio` | Positions, P&L, exposure metrics |
| `/alert AAPL above 200` | Auto-monitored price alert (checked every 3 min) |
| `/watchlist add TSLA` | Personal watchlist (up to 20 tickers) |

---

## All 52 Commands by Category

### 📊 Market Intelligence (14 commands)

| Command | Description | Cooldown |
|---------|-------------|----------|
| `/dashboard` | Mega 3-embed dashboard — regime, markets, signals | 30s |
| `/market_now` | Live regime scoreboard + risk budgets + playbook | 30s |
| `/daily_update` | Full intelligence brief with delta deck | 30s |
| `/daily` | Alias for `/daily_update` | 30s |
| `/report` | On-demand morning or EOD report | 30s |
| `/market` | US index overview — SPY, QQQ, DIA, VIX | — |
| `/sector` | 11-sector performance heatmap | — |
| `/macro` | Gold, Oil, BTC, Bonds, Dollar | — |
| `/movers` | Top gainers and losers in watchlist | — |
| `/news TICKER` | Latest news headlines for a ticker | — |
| `/premarket` | S&P and Nasdaq futures snapshot | — |
| `/price TICKER` | Real-time price with key metrics | — |
| `/quote TICKER` | Detailed quote with fundamentals | — |
| `/status` | System health and connectivity check | — |

### 🔬 Deep Analysis (7 commands)

| Command | Description |
|---------|-------------|
| `/ai TICKER` | Full AI analysis — technicals + sentiment + GPT narrative |
| `/analyze TICKER` | Technical breakdown — SMA, RSI, MACD, Bollinger, volume |
| `/advise TICKER` | AI buy / hold / sell recommendation with reasoning |
| `/score TICKER` | AI score 1–10 with component breakdown |
| `/compare A B` | Side-by-side technical comparison |
| `/levels TICKER` | Support and resistance levels from price history |
| `/why TICKER` | Why is it moving? News + volume + technical context |

### 🎯 Signals & Scanners (8 commands)

| Command | Description |
|---------|-------------|
| `/signals` | Latest AI-ranked trading signals with signal cards |
| `/scan` | Fresh scan across all strategies |
| `/momentum` | High-momentum stocks (big moves + volume) |
| `/swing` | Swing trade setups (2–10 day hold) |
| `/breakout` | Breakout candidates near consolidation highs |
| `/dip` | Dip-buying opportunities (oversold bounces) |
| `/whale` | Unusual volume / whale accumulation alerts |
| `/squeeze` | Short squeeze candidates |

### 🌏 Multi-Market Coverage (5 commands)

| Command | Description |
|---------|-------------|
| `/asia` | Japan + Hong Kong + China composite dashboard |
| `/japan` | Japan market top picks |
| `/hk` | Hong Kong market top picks |
| `/crypto` | Crypto dashboard — BTC, ETH, SOL, and more |
| `/btc` | Bitcoin detailed analysis |

### 💼 Portfolio & Trading (8 commands)

| Command | Description |
|---------|-------------|
| `/portfolio` | Full portfolio — value, positions, P&L, risk metrics |
| `/pnl` | Today's P&L with W/L count, best/worst position |
| `/positions` | Open positions list |
| `/stats` | Trading statistics — ROI, win rate, Sharpe |
| `/risk TICKER` | Position sizing calculator based on account + volatility |
| `/buy TICKER QTY` | Buy shares (paper or live broker) |
| `/sell TICKER QTY` | Sell shares (paper or live broker) |
| `/backtest` | Backtest a strategy on historical data |

### 🔔 Personal Monitoring (4 commands)

| Command | Description |
|---------|-------------|
| `/watchlist [add/remove/show]` | Manage your personal watchlist (20 max) |
| `/alert TICKER above/below PRICE` | Set price alert — monitored every 3 min, DM on trigger |
| `/my_alerts` | View active and recently triggered alerts |
| `/clear_alerts` | Remove all your alerts |

### 🔧 Admin (5 commands)

| Command | Description |
|---------|-------------|
| `/setup` | Re-run full server channel & role setup |
| `/announce TEXT` | Post announcement to `#daily-brief` |
| `/purge N` | Delete last N messages in channel |
| `/slowmode SECONDS` | Set slowmode for channel |
| `/pin` | Pin the last message |

---

## 📋 Recommended Workflows

### Workflow 1: Morning Routine (5 minutes)

```
1. Check #daily-brief → read the morning brief
2. /dashboard         → regime + portfolio + risk at a glance
3. /market_now        → risk budgets and strategy playbook
4. Review #momentum-alerts and #swing-trades
5. /ai on anything interesting
```

### Workflow 2: Finding Setups

```
Short-term          Medium-term           Longer-term
─────────────       ─────────────         ─────────────
/momentum           /swing                /dashboard
/movers             /breakout             /market_now
/why TICKER         /signals              /portfolio
#momentum-alerts    #swing-trades         #daily-brief
                    #breakout-setups      EOD reports
```

### Workflow 3: Before Acting on a Signal

```
1. /ai TICKER        → full AI analysis with reasoning
2. /analyze TICKER   → technical confirmation
3. /levels TICKER    → define entry/stop/target zones
4. /risk TICKER      → calculate position size
5. /buy or /sell     → execute
6. /alert TICKER     → set exit alert
```

### Workflow 4: Passive Monitoring (just read what the bot posts)

The bot auto-posts to these channels without you doing anything:

| Channel | What Appears | How Often |
|---------|-------------|-----------|
| `#daily-brief` | Morning briefs, EOD, news, macro, VIX alerts | Continuous |
| `#momentum-alerts` | Price spikes, opportunity alerts | Every 3–30 min |
| `#swing-trades` | Swing scan results | Every 6 hr |
| `#breakout-setups` | Breakout scan results | Every 4 hr |
| `#ai-signals` | Combined AI-ranked signals | Every 3 hr |
| `#signals` | Whale alerts, user price alerts | Every 45 min |

---

## 🔔 Personal Alert System

### How it works

1. You set: `/alert AAPL above 200`
2. Bot stores it in memory
3. Every 3 minutes, `realtime_price_alerts` checks all user alerts
4. When AAPL crosses $200:
   - Alert is marked triggered
   - Bot DMs you with the alert embed
   - Alert is also posted to `#signals`
5. View all: `/my_alerts`
6. Clear all: `/clear_alerts`

### Limits
- 20 alerts per user
- Conditions: `above` or `below`
- Checked every 3 minutes
- Alerts are in-memory (reset on bot restart)

---

## 🛡️ Signal Card Anatomy

Every auto-posted signal includes:

```
🎯 SWING LONG — NVDA $142.50
━━━━━━━━━━━━━━━━━━━━━━━━━━━━
Score: 82/100  │  Direction: 🟢 LONG
Entry: ~$142.50
Target: $155.00  │  Stop: $135.00
R:R: 2.4:1
RSI: 55  │  Rel Vol: 1.8x  │  ATR: $4.20

Reasons:
• Price above rising 50-SMA with volume confirmation
• RSI in neutral zone with room to expand
• Sector (Tech) showing relative strength

[Deep Analysis] [Position Sizer] [Set Alert]
```

---

## 📊 Health Monitoring

Every 30 minutes, the bot posts a health check to `#admin-log`:

```
💚 Bot Health Check
Uptime: Since 2026-02-25  │  Guilds: 1  │  Latency: 42ms

🔄 Running Tasks:
✅ Presence
✅ Market Pulse
✅ 🚨 Price Alerts (3min)
✅ 📰 News Feed (30min)
✅ ☀️ Smart Morning (3x/day)
✅ 🎯 Oppty Scanner (30min)
✅ ⚠️ VIX Fear Monitor (5min)
✅ Auto Movers
✅ AI Signals
✅ Crypto
✅ Global Update (4h)
✅ Whale Scan
✅ Morning Brief
✅ EOD Report
```

---

_Last updated: March 2026 · v6 Pro Desk Edition_
