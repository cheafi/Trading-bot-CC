# 🗄️ Data Model & Schema — TradingAI Bot v6

Data structures, runtime state, Pydantic models, and optional PostgreSQL persistence.

---

## Runtime State (In-Memory)

The Discord bot maintains these live data structures:

| Store | Type | Purpose | Persistent? |
|-------|------|---------|:-----------:|
| `_user_watchlists` | `Dict[int, List[str]]` | Per-user watchlist (up to 20) | ❌ |
| `_user_alerts` | `Dict[int, List[dict]]` | Per-user price alerts | ❌ |
| `_last_prices` | `Dict[str, float]` | Last known price per ticker | ❌ |
| `_spike_cooldown` | `Dict[str, float]` | Alert cooldown timestamps | ❌ |
| `_opp_cooldown` | `Dict[str, float]` | Opportunity alert cooldowns | ❌ |
| `_news_seen` | `set` | Dedupe URLs for news feed | ❌ |
| `_morning_posted` | `set` | Once-per-day morning brief | ❌ |
| `_eod_posted` | `set` | Once-per-day EOD report | ❌ |
| `_smart_morning_posted` | `Dict[str, set]` | Per-session morning flags | ❌ |
| `_vix_last_alert` | `float` | VIX alert cooldown | ❌ |

> ⚠️ All in-memory state resets on bot restart. See [Persistence Recommendations](#persistence-recommendations) below.

---

## Pydantic Models (`src/core/models.py`)

767 lines defining the shared type system across all layers.

### Enums

| Enum | Values | Used For |
|------|--------|----------|
| `Direction` | LONG, SHORT, CLOSE, NEUTRAL | Signal direction |
| `Horizon` | INTRADAY, SWING_1_5D, SWING_5_15D, POSITION_15_60D | Hold window |
| `StopType` | HARD, CLOSE_BELOW, TRAILING_ATR | Stop loss behavior |
| `SignalStatus` | pending, active, closed, expired, cancelled | Signal lifecycle |
| `VolatilityRegime` | CRISIS, HIGH_VOL, NORMAL, LOW_VOL | VIX-based regime |
| `TrendRegime` | STRONG_UPTREND → STRONG_DOWNTREND | Trend state |
| `RiskRegime` | RISK_ON, NEUTRAL, RISK_OFF | Overall risk stance |
| `SentimentLabel` | very_bearish → very_bullish | News/social sentiment |

### Market Models

| Model | Key Fields | Purpose |
|-------|-----------|---------|
| `OHLCV` | ts, ticker, open, high, low, close, volume, vwap | Price bars |
| `Quote` | ticker, price, change, change_pct, volume, bid, ask | Real-time quotes |
| `MarketSnapshot` | spx, ndx, djia, iwm, vix, futures, put_call | Market overview |

### Feature Models

| Model | Key Fields | Purpose |
|-------|-----------|---------|
| `TechnicalFeatures` | returns, volatility, SMAs, RSI, MACD, BBands, ADX, volume | Per-ticker TA |
| `MarketBreadth` | AD ratio, new highs/lows, % above SMAs, McClellan | Market health |
| `MarketRegime` | volatility, trend, risk, active_strategies | Regime classification |

### Signal Models

| Model | Key Fields | Purpose |
|-------|-----------|---------|
| `Signal` | ticker, direction, horizon, confidence, entry, stop, targets | Core signal |
| `Target` | price, pct_position | Take-profit level |
| `Invalidation` | stop_price, stop_type, condition | Stop loss config |

### v6 Pro Desk Models

| Model | Key Fields | Purpose |
|-------|-----------|---------|
| `RegimeScoreboard` | regime_label, risk_on_score, trend, vol, budgets, playbook | Morning memo backbone |
| `ScenarioPlan` | base_case, bull_case, bear_case, triggers | Scenario planning |
| `DeltaSnapshot` | spx/ndx/iwm 1d%, vix_close, vix_change | What changed |
| `DataQualityReport` | status, stale_feeds, gaps | Pipeline health |
| `BacktestDiagnostic` | sharpe, win_rate, max_dd, profit_factor | Backtest results |
| `ChangeItem` | description, direction, magnitude | Delta deck item |

---

## Signal Schema (JSON)

```json
{
  "ticker": "NVDA",
  "direction": "LONG",
  "horizon": "SWING_5_15D",
  "confidence": 82,
  "entry_logic": "Breakout above $142 with volume confirmation",
  "invalidation": {
    "stop_price": 135.00,
    "stop_type": "HARD",
    "condition": "Close below 50-SMA"
  },
  "targets": [
    {"price": 150.0, "pct_position": 50},
    {"price": 160.0, "pct_position": 30},
    {"price": 175.0, "pct_position": 20}
  ],
  "catalyst": "AI chip demand cycle + data center capex",
  "key_risks": ["Earnings in 3 weeks", "Sector rotation risk"],
  "rationale": "Strong momentum with volume support in risk-on regime"
}
```

---

## Regime Scoreboard Schema

```json
{
  "regime_label": "RISK_ON",
  "risk_on_score": 72.5,
  "trend_state": "UPTREND",
  "vol_state": "NORMAL",
  "max_gross_pct": 150,
  "net_long_target_low": 60,
  "net_long_target_high": 100,
  "max_single_name_pct": 5,
  "max_sector_pct": 30,
  "strategies_on": ["Momentum", "Breakout", "Trend-Follow"],
  "strategies_conditional": [],
  "strategies_off": ["Mean-Reversion"],
  "no_trade_triggers": [],
  "scenarios": {
    "base_case": {"probability": "55%", "description": "Consolidation near highs"},
    "bull_case": {"probability": "30%", "description": "Breakout above resistance"},
    "bear_case": {"probability": "15%", "description": "VIX spike on macro data"}
  }
}
```

---

## Optional PostgreSQL Schema

Bootstrap scripts: `init/postgres/01_init.sql` and `02_pro_desk_upgrade.sql`

### Recommended Tables

#### Signal History

```sql
CREATE TABLE signals (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    ticker          VARCHAR(20) NOT NULL,
    direction       VARCHAR(10) NOT NULL,
    horizon         VARCHAR(20) NOT NULL,
    confidence      NUMERIC(6,2),
    entry_price     NUMERIC(18,6),
    stop_price      NUMERIC(18,6),
    target_price    NUMERIC(18,6),
    entry_logic     TEXT,
    rationale       TEXT,
    generated_at    TIMESTAMPTZ NOT NULL,
    status          VARCHAR(20) DEFAULT 'pending',
    closed_at       TIMESTAMPTZ,
    pnl_pct         NUMERIC(8,4),
    raw_payload     JSONB,
    created_at      TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX idx_signals_ticker ON signals (ticker, generated_at DESC);
CREATE INDEX idx_signals_status ON signals (status);
```

#### Regime Snapshots

```sql
CREATE TABLE regime_snapshots (
    ts              TIMESTAMPTZ PRIMARY KEY,
    regime_label    VARCHAR(20) NOT NULL,
    risk_on_score   NUMERIC(6,2),
    trend_state     VARCHAR(20),
    vol_state       VARCHAR(20),
    vix_close       NUMERIC(8,2),
    spy_pct         NUMERIC(8,4),
    payload         JSONB,
    created_at      TIMESTAMPTZ DEFAULT NOW()
);
```

#### User Watchlists (Persistent)

```sql
CREATE TABLE user_watchlists (
    user_id     BIGINT NOT NULL,
    ticker      VARCHAR(20) NOT NULL,
    added_at    TIMESTAMPTZ DEFAULT NOW(),
    PRIMARY KEY (user_id, ticker)
);
```

#### User Alerts (Persistent)

```sql
CREATE TABLE user_alerts (
    id              BIGSERIAL PRIMARY KEY,
    user_id         BIGINT NOT NULL,
    ticker          VARCHAR(20) NOT NULL,
    condition       VARCHAR(10) NOT NULL,
    target_price    NUMERIC(18,6) NOT NULL,
    triggered       BOOLEAN DEFAULT FALSE,
    triggered_at    TIMESTAMPTZ,
    created_at      TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX idx_alerts_user ON user_alerts (user_id, triggered);
```

#### Data Quality Reports

```sql
CREATE TABLE data_quality_reports (
    ts              TIMESTAMPTZ PRIMARY KEY,
    status          VARCHAR(20) NOT NULL,
    stale_feeds     INTEGER DEFAULT 0,
    gaps_detected   INTEGER DEFAULT 0,
    payload         JSONB
);
```

---

## Persistence Recommendations

Priority order for making state durable:

| Priority | What | Why |
|:--------:|------|-----|
| 1 | User alerts | Users expect alerts to survive restarts |
| 2 | User watchlists | Personal config should persist |
| 3 | Signal history | Enables performance measurement |
| 4 | Regime snapshots | Historical regime context for backtesting |
| 5 | Report archives | Audit trail |

---

_Last updated: March 2026 · v6 Pro Desk Edition_
