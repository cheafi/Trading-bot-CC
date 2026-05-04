# Daily Report Timeline

> Full 24-hour automation schedule — all 23 background tasks mapped by time (UTC and HKT).

---

## Timeline Overview

```
UTC    HKT    Task                                    Channel
────── ────── ──────────────────────────────────────  ───────────────
00:00  08:00  🌍 global_market_update (hourly)        #general
00:30  08:30  ₿ auto_crypto (30 min)                  #crypto
              📰 auto_news_feed (30 min)               #news

01:00  09:00  ☀️ morning_brief (daily)                #daily-reports
01:00  09:00  🌏 asia_preview (daily)                 #daily-reports

       ↕ CONTINUOUS ALL DAY ↕

Every  Every  🚨 realtime_price_alerts (3 min)        #alerts
3 min  3 min      → price spikes · user alerts
                  → news auto-attached to spikes

Every  Every  ⚠️  vix_fear_monitor (5 min)            #alerts
5 min  5 min      → VIX spike warnings

Every  Every  📡 market_pulse (15 min)                #general
15min  15min      → SPY/QQQ/BTC pulse

Every  Every  📰 auto_ticker_news (15 min)            #news
15min  15min      → rotating 50-stock news coverage

Every  Every  📰 auto_news_feed (30 min)              #news
30min  30min      → 25-source aggregated news

Every  Every  💚 health_check (30 min)                internal
30min  30min      → internal diagnostics

       ──────────────────────────────────────────────────────

08:00  16:00  🔥 auto_movers starts (30 min · 8–22UTC) #general
08:00  16:00  🏭 auto_sector_macro starts (60m · 8–22) #general
08:00  16:00  🐋 auto_whale_scan starts (45m · 8–22)  #signals

       ──────────────────────────────────────────────────────

13:00  21:00  🤖 auto_signal_scan (3h · 13–21 UTC)   #signals
13:00  21:00  🎯 opportunity_scanner (30m · 13–21)    #signals

13:30  21:30  ☀️ smart_morning_update (daily)         #daily-reports
              = v6 US Pre-Market Decision Memo

       ──────────────────────────────────────────────────────

WEEKDAYS ONLY — scanning tasks:

Every  Every  ⚡ auto_momentum_scan (2 h)             #signals
2h     2h

Every  Every  🚀 auto_breakout_scan (4 h)             #signals
4h     4h

Every  Every  🔄 auto_swing_scan (6 h)                #signals
6h     6h

Every  Every  🤖 auto_strategy_learn (6 h)            #ai-signals
6h     6h         → AI self-learning backtest update

       ──────────────────────────────────────────────────────

20:10  04:10  🌙 eod_report (daily)                   #daily-reports

Sunday Sunday  📅 weekly_recap (weekly · Sun 21 UTC)  #daily-reports
21:00  05:00

Every  Every  🌀 update_presence (1 min)              Bot status
1min   1min
```

---

## Morning Sequence (HKT 08:00–10:00)

### 08:00 HKT — Global Update
`global_market_update` posts:
- World indices: SPY, QQQ, Nikkei, Hang Seng, Shanghai, DAX, FTSE
- USD/CNH, USD/JPY, Gold, Oil, BTC
- Overnight futures context

### 08:30 HKT — First Crypto + News Pulse
- `auto_crypto`: BTC/ETH/SOL/DOGE/ADA/AVAX with 24h change
- `auto_news_feed`: Top headlines from 25 sources

### 09:00 HKT — Asia Morning Brief
`morning_brief` posts to `#daily-reports`:

```
☀️ ASIA MORNING BRIEF — Mon 2 Jun 2025  09:00 HKT

  OVERNIGHT: SPY +0.4% · QQQ +0.6% · BTC $97,200

  ASIA SESSION
  Nikkei 225:   38,420  +0.8%  🟢
  Hang Seng:    19,840  −0.3%  🔴
  Shanghai:     3,380   +0.1%  ⚪

  TOP 3 SIGNALS FROM OVERNIGHT SCANS
  1. 🟢 NVDA BREAKOUT  Score 87  Target $162
  2. 🟢 MSFT SWING     Score 74  Target $448
  3. ⚪ TSLA WATCH     Score 52  Wait for entry

  TOP NEWS
  • NVDA: New enterprise GPU orders confirmed (Reuters)
  • FED: No rate surprise expected (Bloomberg)
```

---

## US Session (HKT 21:30–06:00)

### 21:30 HKT — Pre-Market Decision Memo
`smart_morning_update` posts to `#daily-reports`:

```
☀️ v6 PRE-MARKET MEMO — 21:30 HKT

  FUTURES: ES +0.3% · NQ +0.5% · RTY +0.1%
  PRE-MARKET MOVERS (4am–9:30am ET):
    🟢 NVDA  +1.8%  on volume  (earnings beat)
    🔴 AMZN  −0.4%  light volume
    🟢 AAPL  +0.6%

  TODAY'S FOCUS STOCKS: NVDA · MSFT · AMD
  KEY LEVELS TO WATCH:
    SPY: Support 545 / Resistance 552
    QQQ: Support 470 / Resistance 478

  TOP OPPORTUNITY: NVDA BREAKOUT setup confirmed pre-market
  RISK: VIX 18.4 — normal · Risk-ON posture
```

### 21:30–02:00 HKT — US Session Scanning
All scanners running during US market hours:
- `auto_signal_scan` (every 3h)
- `opportunity_scanner` (every 30min)
- `auto_momentum_scan` (every 2h)
- `auto_breakout_scan` (every 4h)
- `auto_whale_scan` (every 45min)
- `realtime_price_alerts` (every 3min)
- `auto_ticker_news` (every 15min)

### 04:10 HKT — EOD Scorecard
`eod_report` posts to `#daily-reports`:

```
🌙 EOD SCORECARD — Mon 2 Jun 2025

  US MARKET CLOSE
  SPY:  +0.8%  QQQ: +1.1%  DIA: +0.4%  IWM: +1.3%
  VIX:  17.2 (−0.8)  — Fear declining

  TOP SIGNALS FIRED TODAY
  ✅ NVDA BREAKOUT — fired at 142.50, hit 144.80 (+1.6%)
  ✅ MSFT SWING    — fired at 422.10, in profit +0.8%
  ⏳ AMD MOMENTUM  — fired at 162.00, pending

  PORTFOLIO SNAPSHOT
  Positions: 3  · Day P&L: +$480 (+1.2%)
  Best: NVDA +$210  · Worst: n/a

  UPCOMING CATALYSTS
  Tue: CPI Data (high impact)
  Wed: FOMC Minutes
  Thu: AMD Earnings
```

---

## Weekly Recap (Sunday 05:00 HKT)

`weekly_recap` posts to `#daily-reports`:

```
📅 WEEKLY RECAP — Week of 26 May – 1 Jun 2025

  MARKET PERFORMANCE
  SPY:   +1.8%  QQQ: +2.4%  DIA: +0.9%

  SIGNALS SUMMARY (this week)
  Total signals:  12
  Wins:           8   (67%)
  Losses:         2   (17%)
  Open:           2   (pending)
  Best win:  +8.4% (NVDA BREAKOUT)
  Worst:     −3.2% (TSLA)

  STRATEGY BREAKDOWN
  BREAKOUT:     4 signals  75% win rate
  MOMENTUM:     3 signals  67% win rate
  SWING:        3 signals  67% win rate
  MEAN_REV:     2 signals  50% win rate

  NEXT WEEK KEY EVENTS
  Mon: PCE inflation
  Wed: FOMC
  Fri: Jobs report (NFP)
```

---

## 23 Background Tasks — Quick Reference

| # | Task | Interval | Active Hours |
|---|------|----------|-------------|
| 1 | `update_presence` | 1 min | always |
| 2 | `market_pulse` | 15 min | always |
| 3 | `auto_movers` | 30 min | 8–22 UTC |
| 4 | `auto_sector_macro` | 60 min | 8–22 UTC |
| 5 | `auto_crypto` | 30 min | always |
| 6 | `global_market_update` | 60 min | always |
| 7 | `auto_swing_scan` | 6 h | weekdays |
| 8 | `auto_breakout_scan` | 4 h | weekdays |
| 9 | `auto_momentum_scan` | 2 h | weekdays |
| 10 | `auto_signal_scan` | 3 h | 13–21 UTC |
| 11 | `morning_brief` | daily | 01:00 UTC |
| 12 | `eod_report` | daily | 20:10 UTC |
| 13 | `asia_preview` | daily | 01:00 UTC |
| 14 | `auto_whale_scan` | 45 min | 8–22 UTC |
| 15 | `weekly_recap` | weekly | Sun 21 UTC |
| 16 | `realtime_price_alerts` | 3 min | always |
| 17 | `auto_news_feed` | 30 min | always |
| 18 | `auto_ticker_news` | 15 min | always |
| 19 | `auto_strategy_learn` | 6 h | weekdays |
| 20 | `smart_morning_update` | daily | 13:30 UTC |
| 21 | `opportunity_scanner` | 30 min | 13–21 UTC |
| 22 | `vix_fear_monitor` | 5 min | always |
| 23 | `health_check` | 30 min | always |

Use `/status` to see live state of all 23 tasks.

---

Back to [README.md](../README.md)
