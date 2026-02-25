# D) Daily Report Format — v6 Pro Desk Edition

## Overview

v6 replaces the flat "market summary" with an **institutional decision-memo** format.
Every report section now maps to a concrete trading action or risk limit.

| Report           | When                | Delivery             | Builder Function           |
|------------------|---------------------|----------------------|---------------------------|
| Morning Memo     | ~09:30 ET pre-open  | Discord #daily-brief | `build_morning_memo()`    |
| Market Now       | On-demand /market_now | Discord ephemeral  | `build_regime_snapshot()` |
| EOD Scorecard    | ~16:10 ET post-close | Discord #daily-brief | `build_eod_scorecard()`   |
| Signal Card      | Per new signal      | Discord #signals     | `build_signal_card()`     |

All builders live in `src/notifications/report_generator.py` and return
format-agnostic dicts that Discord, Telegram, and the web API can render.

---

## v6 Report Template Structure

```
┌───────────────────────────────────────────────────────────────────────────────────┐
│                     ☀️ MORNING DECISION MEMO — v6 Pro Desk                        │
│                     [Date] — Pre-Market Edition                                   │
├───────────────────────────────────────────────────────────────────────────────────┤
│                                                                                   │
│  1. REGIME SCOREBOARD                                                             │
│     - Regime label (RISK_ON / NEUTRAL / RISK_OFF)                                 │
│     - Risk-On Score (0-100)                                                       │
│     - Trend state · Vol state                                                     │
│     - Risk budgets (max gross, net long, single name, sector)                     │
│                                                                                   │
│  2. STRATEGY PLAYBOOK                                                             │
│     - Strategies ON (active today)                                                │
│     - Strategies CONDITIONAL (with trigger conditions)                            │
│     - Strategies OFF (not suitable for regime)                                    │
│                                                                                   │
│  3. DELTA DECK — What Changed                                                     │
│     - SPX / NDX / IWM 1-day %                                                    │
│     - VIX close + change                                                          │
│     - Bullish change items vs Bearish change items                                │
│                                                                                   │
│  4. SCENARIO PLAN                                                                 │
│     - Base case (probability + description)                                       │
│     - Bull case (probability + description)                                       │
│     - Bear case (probability + description)                                       │
│     - Trigger events                                                              │
│                                                                                   │
│  5. TOP 5 TRADE IDEAS                                                             │
│     - v6 signal cards with setup_grade, approval_status                           │
│     - edge_type, why_now, evidence stack                                          │
│     - scenario_plan per trade                                                     │
│     - time_stop_days, event_risk, portfolio_fit                                   │
│                                                                                   │
│  6. NO-TRADE TRIGGERS / RISK FLAGS                                                │
│     - VIX thresholds                                                              │
│     - Divergence warnings                                                         │
│     - Event risk calendar                                                         │
│                                                                                   │
│  7. MACRO SNAPSHOT                                                                │
│     - VIX, TLT, Gold, BTC                                                        │
│     - Futures, Asia recap                                                         │
│                                                                                   │
│  DISCLAIMER                                                                       │
│                                                                                   │
└───────────────────────────────────────────────────────────────────────────────────┘
```

---

## v6 Signal Card Schema

Each signal card includes these v6 fields beyond the legacy signal:

| Field               | Type           | Description                                        |
|---------------------|----------------|----------------------------------------------------|
| `setup_grade`       | A / B / C / F  | Overall setup quality grade                        |
| `edge_type`         | string         | E.g. `trend_continuation`, `mean_reversion`, `event` |
| `approval_status`   | APPROVED / NEEDS_REVIEW / REJECTED | GPT gatekeeper verdict |
| `approval_flags`    | list[str]      | Reasons for review/rejection                       |
| `why_now`           | string         | 1-2 sentence narrative: why this trade today       |
| `evidence`          | list[str]      | 3-8 evidence bullets (price, volume, sector, etc.) |
| `scenario_plan`     | ScenarioPlan   | Base/bull/bear with probabilities                  |
| `time_stop_days`    | int            | Auto-exit if thesis not working after N days       |
| `event_risk`        | string         | Upcoming event that could invalidate thesis        |
| `portfolio_fit`     | string         | `adds_diversification`, `correlated`, `concentrated` |
| `expected_value`    | float          | Simplified EV = P(win) × reward - P(loss) × risk  |

### Signal Card Example (JSON)

```json
{
  "ticker": "NVDA",
  "direction": "BUY",
  "confidence": 0.78,
  "strategy": "momentum",
  "entry_price": 878.50,
  "stop_loss": 842.00,
  "take_profit": 920.00,
  "setup_grade": "A",
  "edge_type": "trend_continuation",
  "approval_status": "APPROVED",
  "approval_flags": [],
  "why_now": "Breaking 3-week consolidation on 2.1x vol; GTC catalyst in 3 weeks",
  "evidence": [
    "Price > SMA20 > SMA50 — bullish alignment",
    "RSI 62, rising — momentum confirmed",
    "Volume 2.1x 20d avg — institutional participation",
    "Sector (XLK) +1.24% — tech leadership",
    "OBV accumulation — smart money bid"
  ],
  "scenario_plan": {
    "base_case": {"probability": "55%", "description": "Grind to $920 (+4.7%)"},
    "bull_case": {"probability": "30%", "description": "Squeeze to $965 (+9.8%)"},
    "bear_case": {"probability": "15%", "description": "Fail at $880, retrace to $842"},
    "triggers": ["GTC conference", "Earnings preview", "Export restrictions"]
  },
  "time_stop_days": 15,
  "event_risk": "GTC conference in 3 weeks",
  "portfolio_fit": "adds_diversification",
  "expected_value": 2.45
}
```

---

## RegimeScoreboard Schema

The scoreboard drives all position sizing and strategy selection:

```json
{
  "regime_label": "RISK_ON",
  "risk_on_score": 72,
  "trend_state": "UPTREND",
  "vol_state": "NORMAL",
  "max_gross_pct": 150,
  "net_long_target_low": 60,
  "net_long_target_high": 100,
  "max_single_name_pct": 5,
  "max_sector_pct": 30,
  "strategies_on": ["Momentum", "Swing", "VCP"],
  "strategies_conditional": [],
  "strategies_off": [],
  "no_trade_triggers": [],
  "top_drivers": ["SPX +0.82%", "VIX 15.4"],
  "scenarios": {
    "base_case": {"probability": "55%", "description": "Range-bound near highs"},
    "bull_case": {"probability": "30%", "description": "Break to new ATH on earnings"},
    "bear_case": {"probability": "15%", "description": "Geopolitical shock, VIX spike"},
    "triggers": ["Macro data", "Fed commentary", "Earnings"]
  }
}
```

### Regime → Risk Budget Mapping

| Regime    | Max Gross | Net Long Range | Max Single | Max Sector |
|-----------|-----------|----------------|------------|------------|
| RISK_ON   | 150%      | 60-100%        | 5%         | 30%        |
| NEUTRAL   | 100%      | 30-70%         | 4%         | 25%        |
| RISK_OFF  | 60%       | 0-30%          | 2%         | 15%        |

### Regime → Strategy Playbook Matrix

| Regime   | Trend    | Vol     | ON                          | CONDITIONAL          | OFF                     |
|----------|----------|---------|-----------------------------|--------------------|-------------------------|
| RISK_ON  | UPTREND  | LOW_VOL | Momentum, Breakout, Trend   |                    | Mean-Reversion          |
| RISK_ON  | UPTREND  | NORMAL  | Momentum, Swing, VCP        |                    |                         |
| RISK_ON  | NEUTRAL  | LOW_VOL | Mean-Reversion, Swing       |                    | Momentum                |
| NEUTRAL  | UPTREND  | NORMAL  | Momentum, VCP               | Swing (pullback>3d)| |
| NEUTRAL  | NEUTRAL  | NORMAL  | Mean-Reversion              | Swing (A grade)    | Momentum                |
| NEUTRAL  | DOWNTREND| NORMAL  | Mean-Reversion              |                    | Momentum, Breakout      |
| RISK_OFF | DOWNTREND| HIGH_VOL|                             |                    | All aggressive           |
| RISK_OFF | NEUTRAL  | HIGH_VOL| Mean-Reversion              |                    | Momentum, Breakout      |

---

## DeltaSnapshot Schema

Captures "what changed" vs yesterday:

```json
{
  "snapshot_date": "2026-01-30",
  "spx_1d_pct": 0.49,
  "ndx_1d_pct": 0.75,
  "iwm_1d_pct": -0.54,
  "vix_close": 16.42,
  "vix_1d_change": -0.8,
  "put_call_ratio": 0.82,
  "advance_decline_ratio": 1.49,
  "pct_above_sma20": 68.2,
  "pct_above_sma50": 71.4,
  "hi_lo_ratio": 5.57,
  "sector_leader": "XLK",
  "sector_laggard": "XLE",
  "new_highs": 156,
  "new_lows": 28
}
```

---

## DataQualityReport Schema

Pipeline health check:

```json
{
  "report_date": "2026-01-30",
  "total_tickers_expected": 50,
  "tickers_with_data": 48,
  "coverage_pct": 96.0,
  "stale_tickers": ["ABNB", "DDOG"],
  "gap_tickers": [],
  "schema_issues": [],
  "freshness_median_minutes": 5.0,
  "freshness_p95_minutes": 12.0,
  "overall_grade": "A"
}
```

---

## API Endpoints (v6)

| Endpoint                         | Method | Description                              |
|----------------------------------|--------|------------------------------------------|
| `/api/v6/scoreboard`             | GET    | Live regime scoreboard + risk budgets    |
| `/api/v6/delta`                  | GET    | Today's delta snapshot                   |
| `/api/v6/regime-snapshot`        | GET    | Formatted regime report (embeds + MD)    |
| `/api/v6/data-quality`           | GET    | Data pipeline health report              |
| `/api/v6/signal-card/{ticker}`   | GET    | v6 signal card with evidence + scenarios |

---

## Discord Commands (v6)

| Command        | Description                                              |
|----------------|----------------------------------------------------------|
| `/market_now`  | Instant regime scoreboard + delta + playbook (v6)        |
| `/morning`     | Triggers morning decision memo with scenario map         |
| `/scan`        | Scan for trade setups with v6 scoring                    |
| `/ai <ticker>` | Full institutional analysis with GPT validation          |

---

## Report Generation Code (v6)

```python
from src.notifications.report_generator import (
    build_signal_card,
    build_regime_snapshot,
    build_morning_memo,
    build_eod_scorecard,
    embeds_to_markdown,
)
from src.core.models import RegimeScoreboard, DeltaSnapshot, ScenarioPlan, Signal

# Build regime scoreboard from live data
scoreboard = RegimeScoreboard(
    regime_label="RISK_ON", risk_on_score=72,
    trend_state="UPTREND", vol_state="NORMAL",
    max_gross_pct=150, net_long_target_low=60, net_long_target_high=100,
    max_single_name_pct=5, max_sector_pct=30,
    strategies_on=["Momentum", "Swing", "VCP"],
    strategies_conditional=[], strategies_off=[],
    no_trade_triggers=[], top_drivers=["SPX +0.82%"],
    scenarios=ScenarioPlan(
        base_case={"probability": "55%", "description": "Range-bound"},
        bull_case={"probability": "30%", "description": "Break to ATH"},
        bear_case={"probability": "15%", "description": "Vol spike"},
        triggers=["Macro", "Earnings"],
    ),
)

# Generate morning memo (returns list of embed dicts)
memo_embeds = build_morning_memo(
    scoreboard=scoreboard, delta=delta,
    bullish_changes=bullish, bearish_changes=bearish,
    top_signals=top_5_signals, market_prices=prices,
)

# Convert to Markdown for export
markdown = embeds_to_markdown(memo_embeds)
```

---

*Report specification v6.0 — TradingAI Pro Desk*
*Data sources: yfinance, Polygon.io, NewsAPI, OpenAI/Azure*
*Builder: `src/notifications/report_generator.py`*
