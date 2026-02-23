# 🤖 TradingAI Bot - Complete Guide

## 📊 Bot Overview

| Stat | Value |
|------|-------|
| **Total Commands** | 186 |
| **US Stocks Tracked** | 1,435 |
| **Crypto Assets** | 21 |
| **Japan ADRs** | 24 |
| **Hong Kong ADRs** | 28 |
| **AI Model** | GPT-5.2 |

---

## 🧭 8-PILLAR HELP SYSTEM

The bot's 186 commands are organized into 8 easy-to-navigate pillars:

| Pillar | Commands | Description |
|--------|----------|-------------|
| 🎯 **Signals** | `/signals`, `/picks`, `/best` | Get actionable trades |
| 🔍 **Analyze** | `/ai`, `/shouldi`, `/score` | Research before buying |
| 📊 **Market** | `/market`, `/noise`, `/movers` | Big picture view |
| ⏰ **Alerts** | `/alert`, `/watch`, `/subscribe` | Stay informed |
| 💰 **Trade** | `/buy`, `/sell`, `/sizing` | Execute trades |
| 📈 **Track** | `/portfolio`, `/trackrecord` | Monitor performance |
| 📚 **Learn** | `/metrics`, `/changelog` | Understand the system |
| 🔧 **Settings** | `/broker`, `/setrisk` | Customize your setup |

Use `/help` to see the pillar menu with quick-tap buttons.

---

## 🎯 KEY DISTINCTION: /signals vs /picks

| Command | Purpose | Score Range | Label |
|---------|---------|-------------|-------|
| `/signals` | **Ready to trade NOW** | 7.5+ | BUY |
| `/picks` | **Watch & wait** | 5.5-7.5 | WATCH |

### Signal Card Format (`/signals`)
```
📊 SIGNAL CARD #1

NVDA — 🟢 LONG
💰 Price: $142.50 (+2.3%)
🎯 AI Score: 8.4/10

📍 ENTRY:
   Zone: $141.75 - $143.25

🛑 STOP LOSS:
   $137.00 (-3.9%)

🎯 TARGETS:
   T1: $150.25 (1.5R)
   T2: $158.00 (2.5R)
   T3: $170.00 (4R)

⏱️ TIMEFRAME: Swing
   Expected hold: 1-3 weeks

📈 STATS:
   Est. Win Rate: ~68%
   Kelly Size: 12% of portfolio
```

---

## 🎯 WORKFLOW: 3-Step Profit Flow

```
┌─────────────────────────────────────────────────────────────┐
│  STEP 1: GET PICKS    →    STEP 2: ANALYZE    →    STEP 3: EXECUTE  │
│     /best /signals         /ai AAPL              /buy AAPL 10       │
│     /crypto /japan         /shouldi NVDA         /sizing AAPL 100   │
└─────────────────────────────────────────────────────────────┘
```

### Step 1: Get Top Picks
```
/best          → Top AI-scored stocks with Win Rate & Kelly %
/signals       → Live trading signals with entry/exit levels
/crypto        → Bitcoin, Ethereum, miners dashboard
/japan         → Japan market picks (Toyota, Sony, etc.)
/hk            → Hong Kong/China picks (BABA, TCEHY, etc.)
/safe          → Low-risk defensive picks
/risky         → High-risk high-reward plays
```

### Step 2: Analyze Before Buy
```
/ai AAPL       → Full AI analysis (technicals + sentiment)
/shouldi NVDA  → Simple BUY/HOLD/SELL recommendation
/deep MU       → Deep dive with charts & levels
/levels TSLA   → Support/resistance levels
/why TSLA      → Why is it moving?
```

### Step 3: Execute & Track
```
/buy AAPL 10   → Buy 10 shares
/sizing AAPL   → Calculate position size based on risk
/portfolio     → View your positions
/pnl           → Check profit/loss
/alerts        → Set price alerts
```

---

## 🧠 AI SCORING SYSTEM

### Score Breakdown (0-10)

| Component | Weight | Description |
|-----------|--------|-------------|
| **Technical** | 30% | RSI, MACD, moving averages |
| **Momentum** | 20% | Price velocity, volume trend |
| **Volume** | 15% | Unusual volume detection |
| **Sentiment** | 15% | News & social sentiment |
| **Pattern** | 10% | Chart patterns (VCP, breakout) |
| **Sector** | 10% | Sector relative strength |

### Confidence Levels

| Emoji | Level | Score | Win Rate | Kelly % |
|-------|-------|-------|----------|---------|
| 🟢🟢🟢 | HIGH | 8.5+ | 70%+ | 15%+ |
| 🟢🟢 | GOOD | 7.5+ | 60%+ | 10%+ |
| 🟢 | MODERATE | 6.5+ | 55%+ | 5%+ |
| 🟡 | LOW | <6.5 | <55% | <5% |

### Kelly % (Position Sizing)
```
Kelly % = (Win% × AvgWin - Loss% × AvgLoss) / AvgWin

Example:
- Win Rate: 65%
- Avg Win: $200
- Avg Loss: $100
- Kelly = (0.65 × 200 - 0.35 × 100) / 200 = 47%
- Use Half-Kelly: 23% of portfolio max
```

---

## 📈 STRATEGY COMMANDS

### Swing Trading (2-8 weeks)
```
/swing         → Best swing setups
/vcp           → VCP pattern breakouts
/breakout      → Imminent breakouts
/dip           → Dip-buying opportunities
```

### Day Trading
```
/orb           → Opening Range Breakout (9:30-10:00)
/vwapbounce    → VWAP bounce plays
/gap           → Gap up/down plays
/scalp5        → Top 5 scalp trades NOW
/power         → Power hour setups (3-4 PM)
```

### Smart Money Detection
```
/smartmoney    → Whale activity tracker
/insider       → Insider buying/selling patterns
/bigflow       → Large options bets
/whale         → Whale accumulation
/darkpool      → Dark pool activity
```

### Crypto
```
/crypto        → Full crypto dashboard
/btc           → Bitcoin analysis
/eth           → Ethereum analysis
/miners        → Mining stocks (MARA, RIOT, CLSK)
/defi          → DeFi & blockchain stocks
```

### Asia Markets
```
/japan         → Japan market overview
/hk            → Hong Kong market overview
/asia          → Full Asia dashboard
/nikkei        → Nikkei 225 analysis
/hangseng      → Hang Seng analysis
/overnight     → Asia overnight recap
```

---

## ⚙️ SETTINGS & CUSTOMIZATION

### User Settings
```
/setaccount 50000    → Set account size to $50,000
/setrisk 1.5         → Set risk per trade to 1.5%
/setstyle swing      → Set trading style (day/swing/position)
/settings            → View all your settings
```

### Alert Settings
```
/alert AAPL above 200    → Alert when AAPL > $200
/volumealert AAPL 200%   → Alert on 200% volume spike
/subscribe on            → Enable push notifications
/smartalert              → AI-powered smart alerts
```

### Auto Features
```
/autoscan        → Enable background scanning
/autowatch       → Auto-analyze watchlist hourly
/nightwatch      → Monitor Asia markets overnight
/turbo           → Turbo mode (faster updates)
```

---

## 🎯 TRADING LOGIC & STRATEGIES

### Entry Rules (AI Checks)
1. **Score ≥ 7.5** - Strong enough signal
2. **Win Rate ≥ 60%** - Historical edge
3. **Kelly % ≥ 5%** - Worth the position size
4. **Volume ≥ 1.5x avg** - Institutional interest
5. **RSI 30-70** - Not overbought/oversold
6. **Above key MA** - Trend confirmation

### Exit Rules
1. **Take Profit**: 2:1 or 3:1 R:R ratio
2. **Stop Loss**: 1-2 ATR below entry
3. **Time Stop**: Exit if no move in 5 days
4. **Trailing Stop**: Lock in profits at +5%

### Risk Management
```
Max Risk Per Trade:     1-2% of account
Max Daily Loss:         3% of account
Max Open Positions:     5-10
Correlation Check:      No 2 stocks in same sector
```

### Position Sizing Formula
```
Position Size = (Account × Risk%) / (Entry - Stop)

Example:
- Account: $100,000
- Risk: 1% = $1,000
- Entry: $150
- Stop: $145 (ATR-based)
- Position = $1,000 / $5 = 200 shares
```

---

## 📊 MARKET REGIME DETECTION

### Regime Types
| Regime | Indicators | Strategy |
|--------|------------|----------|
| 🟢 **RISK-ON** | SPY↑, VIX↓, QQQ>SPY | Aggressive, buy dips |
| 🔴 **RISK-OFF** | SPY↓, VIX↑, GLD↑ | Defensive, raise cash |
| 🟡 **CHOPPY** | Mixed signals | Small positions, wait |

### What to Watch
```
/market        → Quick market regime check
/noise         → AI market noise filter
/macro         → Gold, BTC, Oil, Bonds, Dollar
/sector        → Sector rotation signals
```

---

## 🔔 BACKGROUND MONITORS (7 Active)

| Monitor | Interval | Purpose |
|---------|----------|---------|
| Signal Scanner | 10 min | Find hot setups |
| Price Monitor | 10 min | Track big movers |
| Scheduled Alerts | varies | Time-based alerts |
| Unusual Activity | 10 min | Volume spikes |
| Smart Money | 10 min | Whale detection |
| Asia Night Watch | 5 min | Overnight Asia |
| Cache Cleanup | 10 min | Memory management |

---

## 📱 QUICK COMMANDS (Most Used)

### Morning Routine
```
/morning       → Morning market brief
/premarket     → Pre-market movers
/setup         → Top 10 setups for today
/market        → Market overview
```

### During Trading
```
/best          → Best picks NOW
/signals       → Live signals
/hotlist       → Real-time hot stocks
/momentum      → Momentum scanner
```

### End of Day
```
/eod           → End of day report
/pnl           → Check P&L
/journal       → Trade journal
/evening       → Evening summary
```

---

## 🏆 PRO TIPS

### 1. Use the 3-Step Flow
Don't just buy random picks. Always:
- Get pick → Analyze → Size → Execute

### 2. Check Confidence First
```
🟢🟢🟢 = Take full position
🟢🟢   = Take half position
🟢     = Small position or skip
🟡     = Skip
```

### 3. Use Kelly % for Sizing
Higher Kelly = Bigger position (but cap at 25%)

### 4. Watch Correlation
Don't hold 5 tech stocks - diversify sectors

### 5. Honor Stop Losses
Set them BEFORE entering. Never move them down.

### 6. Track Your Trades
```
/journal       → Log your trades
/accuracy      → Check win rate
/monthly       → Monthly P&L
```

---

## 🎯 100% ANNUAL RETURN TARGET

### Monthly Target: ~6% (compounds to 100%+)

| Strategy Mix | Allocation |
|--------------|------------|
| Swing Trades | 50% |
| Day Trades | 20% |
| Crypto | 15% |
| Asia Markets | 15% |

### Key Commands for Target
```
/prosetup      → Pro-grade setups
/conviction    → Highest conviction trades
/asymmetric    → Best risk/reward plays (3:1+)
/compound      → Compounding strategy
/yearly        → Track annual goal
```

---

## 🔧 PERFORMANCE SETTINGS

### Cache (Optimized)
```python
Quote Cache:     60 seconds
Analysis Cache:  5 minutes
Batch Size:      50 stocks
Concurrent:      20 requests
```

### Scan Intervals
```
Market Hours:    10 minutes
After Hours:     30 minutes
Turbo Mode:      2 minutes
```

---

## 📞 HELP COMMANDS

```
/help          → Main help (3-step flow)
/help picks    → Stock picking explained
/help trading  → Trading strategies
/help market   → Market commands
/help alerts   → Alert setup
/help all      → All commands list
/tutorial      → Interactive tutorials
/faq           → Frequently asked questions
```

---

**Last Updated:** February 2026  
**AI Model:** GPT-5.2  
**Version:** TradingAI Bot v2.0
