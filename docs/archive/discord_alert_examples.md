# Discord Alert Examples

## Sector-Aware Alert Format

Every Discord alert now carries full sector-adaptive context.

---

### Example 1: High-Growth Leader — TRADE

**Channel**: `#top-opportunities`

```
🟢 NVDA — TRADE (A)

📍 Sector
   AI/Semis
   Stage: ACCELERATION | Leader: LEADER

📊 Confidence
   Thesis:    87%
   Timing:    74%
   Execution: 82%
   Data:      91%
   Final:     83%

🎯 Setup
   Strategy: VCP Breakout
   Entry: Near $145 pivot
   Invalidation: Close below $138
   Risk: LOW

💡 Why Now
   NVDA VCP Grade A (AT_PIVOT). Quality 8.2/10, Context 8.5/10.
   Sector leader. Sector accelerating.

⚠️ Why Not Stronger
   No major detractors — strong conviction

📎 Conflict: LOW | Data: live
```

---

### Example 2: Cyclical Warning — WATCH

**Channel**: `#cyclical-macro`

```
🟡 XOM — WATCH (B+)

📍 Sector
   Oil/Integrated
   Stage: ACCELERATION | Leader: EARLY_FOLLOWER

📊 Confidence
   Thesis:    71%
   Timing:    58%
   Execution: 65%
   Data:      85%
   Final:     66%

🎯 Setup
   Strategy: Pullback to EMA 21
   Entry: Near $108
   Invalidation: Close below $104
   Risk: MEDIUM

💡 Why Now
   XOM pullback to support with commodity base intact.

⚠️ Why Not Stronger
   Conviction limited by: regime not fully supportive;
   wide ATR; weekend geopolitical risk

🔴 Contradictions
   • Commodity equity vs futures divergence
   • Weekend geopolitical risk for commodities

📎 Conflict: MEDIUM | Data: live
```

---

### Example 3: Theme Avoid — NO_TRADE

**Channel**: `#no-trade-alerts`

```
🔴 IONQ — NO_TRADE (D)

📍 Sector
   Quantum Computing
   Stage: DISTRIBUTION | Leader: LAGGARD

📊 Confidence
   Thesis:    32%
   Timing:    25%
   Execution: 41%
   Data:      78%
   Final:     33%

💡 Why Now
   IONQ not actionable now — Theme in distribution stage

🔴 Contradictions
   • Sector in DISTRIBUTION stage
   • Laggard — not leading
   • Social heat extreme

🔄 Better Alternative
   Consider PLTR instead — sector leader, higher confidence.
   Same sector, cleaner setup.

📎 Conflict: HIGH | Data: live
```

---

## Alert Types

| Type          | Color     | When                    |
| ------------- | --------- | ----------------------- |
| URGENT        | 🔴 Red    | TRADE + confidence ≥70% |
| ACTIONABLE    | 🟢 Green  | TRADE                   |
| WATCHLIST     | 🟡 Amber  | WATCH                   |
| NO_TRADE      | ⚪ Grey   | Explicit avoid          |
| MACRO_WARNING | 🟠 Orange | Market-level risk       |
| REVIEW        | 🔵 Blue   | Post-trade reminder     |

## Channel Routing

| Channel             | Content                     |
| ------------------- | --------------------------- |
| #top-opportunities  | URGENT + ACTIONABLE         |
| #growth-ai          | HIGH_GROWTH signals         |
| #cyclical-macro     | CYCLICAL signals            |
| #defensive-rotation | DEFENSIVE signals           |
| #theme-speculation  | THEME_HYPE signals          |
| #no-trade-alerts    | NO_TRADE signals            |
| #earnings-risk      | Earnings proximity warnings |
| #portfolio-brief    | Daily portfolio summary     |

## Commands

| Command            | Description                     |
| ------------------ | ------------------------------- |
| `/today`           | Today's regime + playbook       |
| `/top`             | Top 5 opportunities             |
| `/why TICKER`      | Full explanation for ticker     |
| `/why-not TICKER`  | What prevents higher conviction |
| `/vcp TICKER`      | VCP intelligence analysis       |
| `/risk TICKER`     | Risk warnings for ticker        |
| `/sector TICKER`   | Sector context for ticker       |
| `/compare T1 T2`   | Side-by-side comparison         |
| `/portfolio brief` | Portfolio summary               |
| `/review today`    | Today's trade reviews           |
