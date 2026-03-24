# 📋 Daily Reports & Auto Briefs — TradingAI Bot v6

How the reporting system delivers structured market intelligence across global trading sessions.

---

## Report Schedule (24-Hour View)

```
UTC    HKT    Report
────── ────── ─────────────────────────────────────────────────────
00:00  08:00  📰 Auto News · ₿ Crypto Pulse · 🌍 Global Update
01:00  09:00  ☀️ ASIA MORNING BRIEF · 🌏 Asia Preview
       ↓      📡 Market Pulse (15min) · 📰 News (30min)
07:00  15:00  ☀️ EUROPE MORNING BRIEF
08:00  16:00  📡 Pulse · 🔥 Movers · 🏭 Sectors · 🐋 Whales begin
       ↓      ⚡ Momentum scans · 🚀 Breakout scans
13:00  21:00  🤖 AI Signal Scan · 🎯 Opportunity Scanner
13:30  21:30  ☀️ US PRE-MARKET BRIEF · 📊 Morning Brief (v6 Decision Memo)
       ↓      All scans running at full frequency
16:00  00:00  📰 News · ₿ Crypto · 🌍 Global Update
20:10  04:10  🌙 EOD SCORECARD
21:00  05:00  Sunday: 📅 WEEKLY RECAP
22:00  06:00  Session tasks wind down

ALWAYS ON: 🚨 Price Alerts (3min) · ⚠️ VIX Fear (5min) · 📰 News (30min) · 💚 Health (30min)
```

---

## Report Types in Detail

### ☀️ Smart Morning Update

**Fires 3× daily** for global timezone coverage:

| Session | UTC | Local Time | Extra Markets |
|---------|-----|------------|---------------|
| 🌏 Asia | 01:00 | 09:00 HKT | Nikkei, Hang Seng, Shanghai |
| 🌍 Europe | 07:00 | 08:00 CET | DAX, FTSE |
| 🇺🇸 US | 13:30 | 09:30 ET | S&P Futures, Nasdaq Futures |

**Each brief contains:**

```
☀️ Asia Morning Brief — Monday, March 24
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
🟢 RISK ON • Risk: 72/100 █████████░ • AI: 🟢 NORMAL

🇺🇸 US Indices
🟢 SPY $582.40 (+0.85%) | 🟢 QQQ $498.20 (+1.12%)

📊 Session Markets
🟢 Nikkei: +0.45% | 🔴 Hang Seng: -0.20%

🌍 Macro
VIX: 14.8 🟢 | Gold: +0.15% | Bonds: -0.08% | BTC: $67,420 (+2.1%)

📋 Today's Playbook
`Momentum` · `Breakout`

🛡️ Risk
✅ All clear — normal sizing
```

---

### 📊 Morning Brief (v6 Decision Memo)

**Fires once** at ~13:30 UTC (09:30 ET) on weekdays.

Full institutional-style morning memo with:
- **Regime Scoreboard** — label, risk-on score, trend, volatility
- **Risk Budgets** — max gross, net long, single name, sector limits
- **Strategy Playbook** — ON / CONDITIONAL / OFF strategies
- **Delta Deck** — what changed overnight (SPX, NDX, IWM, VIX)
- **Scenario Plan** — base / bull / bear with probabilities
- **Top 5 Trade Ideas** — v6 signal cards with full context
- **Risk Flags** — VIX warnings, divergence alerts, event risk

---

### 🌙 EOD Scorecard

**Fires once** at ~20:10 UTC (16:10 ET) on weekdays.

Closing summary with:
- Regime at close (RISK_ON / NEUTRAL / RISK_OFF)
- Index performance + bars
- Sector heatmap (11 sectors sorted)
- Top movers + laggards from watchlist
- Market breadth (% green)
- VIX close analysis
- Overnight outlook

---

### 🌏 Asia Preview

**Fires once** at ~01:00 UTC (09:00 HKT).

Bridges US close into Asia open with:
- Nikkei, Hang Seng, Shanghai performance
- US closing levels as context
- Overnight event preview

---

### 📅 Weekly Recap

**Fires Sunday** ~21:00 UTC.

Full week summary: all major indices + crypto + preview of next week's calendar.

---

## High-Frequency Auto-Reports

These run continuously without user action:

| Report | Frequency | Channel | Content |
|--------|-----------|---------|---------|
| **⏱️ Market Pulse** | 15 min | `#daily-brief` | SPY/QQQ/DIA + VIX fear gauge |
| **🔥 Big Movers** | 30 min | `#signals` | Stocks moving ≥ 2% with volume |
| **🏭 Sector Heatmap** | 60 min | `#daily-brief` | All 11 S&P sectors |
| **🌍 Macro Snapshot** | 60 min | `#daily-brief` | Gold, Oil, Bonds, Dollar, BTC |
| **₿ Crypto Pulse** | 2 hr | `#daily-brief` | Top 6 crypto + sentiment |
| **🌍 Global Update** | 4 hr | `#daily-brief` | Cross-session overview |
| **📰 News Feed** | 30 min | `#daily-brief` | Top headlines from Yahoo Finance |

---

## Alert-Driven Reports (fire only when triggered)

| Alert | Trigger | Channel |
|-------|---------|---------|
| **🚨 Price Spike/Crash** | Stock ≥ 3%, Index ≥ 1.2%, Crypto ≥ 5% | `#momentum-alerts` |
| **⚠️ VIX Fear Alert** | VIX +10% or above 25/30 thresholds | `#daily-brief` + `#momentum-alerts` |
| **🐋 Whale Alert** | Volume ≥ 3× 20-day average | `#signals` |
| **🎯 Opportunity Flash** | Signal score ≥ 75 | `#momentum-alerts` |
| **🔔 User Price Alert** | User target crossed | DM + `#signals` |

---

## Channel Destination Map

| Channel | What Goes There |
|---------|----------------|
| `#daily-brief` | Morning briefs, EOD, macro, sectors, news, VIX, global |
| `#signals` | Whale alerts, user alerts, movers |
| `#momentum-alerts` | Price spikes, momentum scans, opportunities |
| `#swing-trades` | Swing scan results |
| `#breakout-setups` | Breakout scan results |
| `#ai-signals` | Combined AI-ranked signals |
| `#admin-log` | Health checks, audit trail |

---

## Report Design Principles

1. **Actionable** — every report answers "what should I do?"
2. **Regime-aware** — strategy recommendations adapt to market conditions
3. **Layered** — quick headline + detailed fields for those who want depth
4. **Timely** — fires at the right time for the right timezone
5. **Non-spammy** — cooldowns, deduplication, and thresholds prevent noise

---

## Implementation Files

| File | Purpose |
|------|---------|
| `src/discord_bot.py` | All 21 background tasks that generate reports |
| `src/notifications/report_generator.py` | Format-agnostic report builders |
| `src/engines/delta_scoreboard.py` | Regime change tracking |
| `src/engines/data_quality.py` | Feed health monitoring |
| `src/core/models.py` | `RegimeScoreboard`, `DeltaSnapshot`, `ScenarioPlan` |

---

_Last updated: March 2026 · v6 Pro Desk Edition_
