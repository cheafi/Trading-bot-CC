# Schema Reference

> Pydantic models, runtime state, and data structures used in TradingAI Bot v6.

---

## Core Models (`src/core/models.py` — 766 lines)

### SignalCard

The primary output of every scanner and strategy.

```python
class SignalCard(BaseModel):
    ticker: str                     # e.g. "NVDA"
    direction: str                  # "LONG" | "SHORT" | "WATCH"
    strategy: str                   # "SWING" | "BREAKOUT" | "MOMENTUM" | "MEAN_REVERSION"
    price: float                    # entry price
    target: float                   # price target
    stop: float                     # stop-loss price
    score: int                      # 0–100 signal quality score
    rr_ratio: float                 # risk/reward ratio
    rsi: float                      # RSI at signal time
    rel_volume: float               # relative volume (1.0 = average)
    hold_period: str                # e.g. "1–4 weeks"
    conditions: list[str]           # bullet-point reasons for the signal
    buy_thesis: str                 # WHY BUY narrative (new v6)
    stop_reason: str                # WHY THIS STOP logic (new v6)
    ml_regime: str                  # detected regime from optimizer
    ml_score: int                   # backtest score (0–100)
    ml_multiplier: float            # self-correction multiplier (0.6–1.4)
    news_headline: str | None       # most recent news headline
    timestamp: datetime             # signal generation time
```

### TradeSetup

Extended version of SignalCard used by `/setup` and `/advise`.

```python
class TradeSetup(BaseModel):
    signal: SignalCard
    support_levels: list[float]
    resistance_levels: list[float]
    pivot: float
    atr: float
    stop_atr_multiple: float        # stop distance / ATR
    liquidity_ok: bool              # avg daily volume > $10M
    avg_daily_volume_usd: float
    macd_hist: float
    bb_width: float                 # Bollinger Band width %
    adx: float
    analyst_target: float | None
    analyst_rating: str | None      # e.g. "Buy" | "Hold" | "Sell"
```

### BrokerPosition

Paper or live position.

```python
class BrokerPosition(BaseModel):
    ticker: str
    shares: float
    entry_price: float
    current_price: float
    pnl_dollars: float
    pnl_pct: float
    stop_price: float
    target_price: float
    strategy: str
    opened_at: datetime
```

### WatchlistItem

User personal watchlist entry.

```python
class WatchlistItem(BaseModel):
    user_id: int                    # Discord user ID
    ticker: str
    added_at: datetime
    note: str | None
```

### PriceAlert

User-set or auto-generated price alert.

```python
class PriceAlert(BaseModel):
    alert_id: str                   # UUID
    user_id: int                    # Discord user ID
    ticker: str
    condition: str                  # "above" | "below"
    price: float
    created_at: datetime
    fired: bool                     # True once triggered
```

---

## Backtest Models (`src/engines/strategy_optimizer.py`)

### StrategyResult

Output of a single strategy backtest.

```python
class StrategyResult(BaseModel):
    strategy_type: str              # "SWING" | "BREAKOUT" | etc.
    ticker: str
    period: str                     # "6mo" | "1y" | "2y"
    regime: str                     # detected regime
    regime_confidence: float        # 0.0–1.0

    # Core stats
    total_trades: int
    win_rate: float                 # 0.0–1.0
    avg_return: float               # percentage
    max_drawdown: float             # percentage (negative)
    profit_factor: float            # gross wins / gross losses

    # Walk-forward
    train_win_rate: float
    oos_win_rate: float
    oos_degradation: float          # train_win_rate - oos_win_rate

    # Parameters
    best_params: dict               # {"rsi_period": 14, "sma_period": 50, ...}
    param_stability: float          # 0–100

    # Cross-check
    cross_check_score: float        # 0–100

    # Monte Carlo
    mc_mean_return: float
    mc_5th_pct: float
    mc_95th_pct: float

    # Self-correction
    correction_multiplier: float    # 0.6–1.4
    raw_score: float                # pre-correction
    final_score: float              # post-correction (0–100)

    computed_at: datetime
```

### BacktestReport

Full `/backtest` output — 4 strategies ranked.

```python
class BacktestReport(BaseModel):
    ticker: str
    period: str
    regime: str
    regime_confidence: float
    strategies: list[StrategyResult]   # sorted by final_score desc
    best_strategy: str
    recommendation: str
    computed_at: datetime
```

---

## Runtime State

The following are live in-memory dictionaries (not persisted unless `DATABASE_URL` is set):

```python
# Active user price alerts
_alerts: dict[str, PriceAlert]          # keyed by alert_id

# Recent signals (last 100 per strategy)
_signal_cache: dict[str, list[SignalCard]]   # keyed by strategy type

# Paper trading positions
_paper_positions: dict[str, BrokerPosition] # keyed by ticker

# User watchlists
_user_watchlists: dict[int, list[WatchlistItem]]  # keyed by Discord user_id

# Strategy optimizer cache (expires after 6h)
_optimizer_cache: dict[str, BacktestReport]  # keyed by "ticker:period"

# Strategy accuracy tracking (for self-correction)
_strategy_accuracy: dict[str, dict]  # keyed by strategy_type
```

---

## Indicator Output Schema

`indicators.py` functions return typed dicts. Example:

```python
# indicators.calculate_all(ticker, period="1y") returns:
{
    "price": float,
    "sma20": float,
    "sma50": float,
    "sma200": float,
    "ema9": float,
    "ema21": float,
    "vwap": float,
    "rsi14": float,
    "macd": float,
    "macd_signal": float,
    "macd_hist": float,
    "bb_upper": float,
    "bb_mid": float,
    "bb_lower": float,
    "bb_width": float,       # (upper - lower) / mid * 100
    "atr14": float,
    "adx14": float,
    "volume": float,
    "avg_volume_20d": float,
    "rel_volume": float,     # volume / avg_volume_20d
    "obv_trend": str,        # "rising" | "falling" | "flat"
    "regime": str,           # 9-state classification
    "trend_direction": str,  # "uptrend" | "downtrend" | "sideways"
}
```

---

## Database Schema (Optional)

Only used when `DATABASE_URL` is set. Schema defined in `init/postgres/01_init.sql`.

### signals table
```sql
CREATE TABLE signals (
    id          UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    ticker      VARCHAR(10) NOT NULL,
    strategy    VARCHAR(30) NOT NULL,
    direction   VARCHAR(10) NOT NULL,
    price       DECIMAL(12,4),
    target      DECIMAL(12,4),
    stop        DECIMAL(12,4),
    score       INT,
    regime      VARCHAR(40),
    ml_score    INT,
    buy_thesis  TEXT,
    stop_reason TEXT,
    created_at  TIMESTAMPTZ DEFAULT NOW()
);
```

### positions table
```sql
CREATE TABLE positions (
    id          UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id     BIGINT NOT NULL,
    ticker      VARCHAR(10) NOT NULL,
    shares      DECIMAL(12,4),
    entry_price DECIMAL(12,4),
    stop_price  DECIMAL(12,4),
    target      DECIMAL(12,4),
    strategy    VARCHAR(30),
    opened_at   TIMESTAMPTZ DEFAULT NOW(),
    closed_at   TIMESTAMPTZ,
    exit_price  DECIMAL(12,4)
);
```

### alerts table
```sql
CREATE TABLE alerts (
    id          UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id     BIGINT NOT NULL,
    ticker      VARCHAR(10) NOT NULL,
    condition   VARCHAR(10) NOT NULL,
    price       DECIMAL(12,4),
    fired       BOOLEAN DEFAULT FALSE,
    created_at  TIMESTAMPTZ DEFAULT NOW(),
    fired_at    TIMESTAMPTZ
);
```

---

## Config Reference (`src/core/config.py`)

```python
class Settings(BaseSettings):
    discord_bot_token: str          # Required
    openai_api_key: str = ""        # Optional
    database_url: str = ""          # Optional
    alpaca_api_key: str = ""
    alpaca_secret_key: str = ""
    alpaca_base_url: str = "https://paper-api.alpaca.markets"
    ib_host: str = "127.0.0.1"
    ib_port: int = 7497
    futu_host: str = "127.0.0.1"
    futu_port: int = 11111
    timezone: str = "Asia/Hong_Kong"

settings = Settings()
```

---

Back to [README.md](../README.md)
