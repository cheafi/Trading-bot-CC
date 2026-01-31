# B) Data Model & Schema

## Database Architecture

```
PostgreSQL 15 + TimescaleDB Extension
├── time_series (schema)     -- OHLCV, features, signals
├── documents (schema)       -- News, social posts, reports  
├── analytics (schema)       -- Backtests, performance metrics
└── system (schema)          -- Config, jobs, audit logs
```

---

## Core Tables

### 1. Price Data (TimescaleDB Hypertable)

```sql
-- time_series.ohlcv
CREATE TABLE time_series.ohlcv (
    ts              TIMESTAMPTZ NOT NULL,
    ticker          VARCHAR(10) NOT NULL,
    open            NUMERIC(12,4),
    high            NUMERIC(12,4),
    low             NUMERIC(12,4),
    close           NUMERIC(12,4),
    volume          BIGINT,
    vwap            NUMERIC(12,4),
    trade_count     INTEGER,
    source          VARCHAR(20) DEFAULT 'polygon',
    created_at      TIMESTAMPTZ DEFAULT NOW()
);

-- Convert to hypertable with 1-day chunks
SELECT create_hypertable('time_series.ohlcv', 'ts', chunk_time_interval => INTERVAL '1 day');

-- Compression policy (compress after 7 days)
ALTER TABLE time_series.ohlcv SET (
    timescaledb.compress,
    timescaledb.compress_segmentby = 'ticker'
);
SELECT add_compression_policy('time_series.ohlcv', INTERVAL '7 days');

-- Indexes
CREATE INDEX idx_ohlcv_ticker_ts ON time_series.ohlcv (ticker, ts DESC);
```

### 2. Fundamentals

```sql
-- time_series.fundamentals
CREATE TABLE time_series.fundamentals (
    ticker              VARCHAR(10) NOT NULL,
    report_date         DATE NOT NULL,
    fiscal_period       VARCHAR(10),  -- Q1, Q2, Q3, Q4, FY
    
    -- Income Statement
    revenue             NUMERIC(18,2),
    gross_profit        NUMERIC(18,2),
    operating_income    NUMERIC(18,2),
    net_income          NUMERIC(18,2),
    eps_basic           NUMERIC(10,4),
    eps_diluted         NUMERIC(10,4),
    
    -- Balance Sheet
    total_assets        NUMERIC(18,2),
    total_liabilities   NUMERIC(18,2),
    total_equity        NUMERIC(18,2),
    cash_and_equiv      NUMERIC(18,2),
    total_debt          NUMERIC(18,2),
    
    -- Ratios
    pe_ratio            NUMERIC(10,2),
    pb_ratio            NUMERIC(10,2),
    ps_ratio            NUMERIC(10,2),
    ev_ebitda           NUMERIC(10,2),
    debt_to_equity      NUMERIC(10,4),
    current_ratio       NUMERIC(10,4),
    roe                 NUMERIC(10,4),
    
    -- Metadata
    source              VARCHAR(20),
    created_at          TIMESTAMPTZ DEFAULT NOW(),
    
    PRIMARY KEY (ticker, report_date, fiscal_period)
);
```

### 3. News Articles

```sql
-- documents.news_articles
CREATE TABLE documents.news_articles (
    id                  UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    published_at        TIMESTAMPTZ NOT NULL,
    source              VARCHAR(50),
    author              VARCHAR(100),
    title               TEXT NOT NULL,
    summary             TEXT,
    content             TEXT,
    url                 TEXT,
    
    -- Extracted entities
    tickers             VARCHAR(10)[] DEFAULT '{}',
    sectors             VARCHAR(50)[] DEFAULT '{}',
    topics              VARCHAR(50)[] DEFAULT '{}',
    
    -- Sentiment (computed by GPT)
    sentiment_score     NUMERIC(5,2),      -- -100 to +100
    sentiment_label     VARCHAR(20),       -- bearish, neutral, bullish
    sentiment_rationale TEXT,
    
    -- Classification
    article_type        VARCHAR(30),       -- earnings, macro, analyst, m&a, etc.
    urgency             VARCHAR(10),       -- low, medium, high, breaking
    
    -- Metadata
    raw_json            JSONB,
    processed           BOOLEAN DEFAULT FALSE,
    created_at          TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX idx_news_tickers ON documents.news_articles USING GIN (tickers);
CREATE INDEX idx_news_published ON documents.news_articles (published_at DESC);
```

### 4. Social Posts

```sql
-- documents.social_posts
CREATE TABLE documents.social_posts (
    id                  UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    platform            VARCHAR(20) NOT NULL,  -- x, reddit, threads
    post_id             VARCHAR(100) NOT NULL,
    posted_at           TIMESTAMPTZ NOT NULL,
    author_handle       VARCHAR(100),
    author_followers    INTEGER,
    
    -- Content
    content             TEXT NOT NULL,
    url                 TEXT,
    
    -- Engagement
    likes               INTEGER DEFAULT 0,
    reposts             INTEGER DEFAULT 0,
    replies             INTEGER DEFAULT 0,
    
    -- Extracted data
    tickers             VARCHAR(10)[] DEFAULT '{}',
    cashtags            VARCHAR(10)[] DEFAULT '{}',
    
    -- Sentiment
    sentiment_score     NUMERIC(5,2),
    sentiment_label     VARCHAR(20),
    
    -- Flags
    is_influencer       BOOLEAN DEFAULT FALSE,
    is_verified         BOOLEAN DEFAULT FALSE,
    spam_score          NUMERIC(5,2),
    
    created_at          TIMESTAMPTZ DEFAULT NOW(),
    
    UNIQUE (platform, post_id)
);

CREATE INDEX idx_social_tickers ON documents.social_posts USING GIN (tickers);
CREATE INDEX idx_social_posted ON documents.social_posts (posted_at DESC);
```

### 5. Feature Store

```sql
-- time_series.features
CREATE TABLE time_series.features (
    ts                  TIMESTAMPTZ NOT NULL,
    ticker              VARCHAR(10) NOT NULL,
    
    -- Technical Features
    return_1d           NUMERIC(10,6),
    return_5d           NUMERIC(10,6),
    return_21d          NUMERIC(10,6),
    return_63d          NUMERIC(10,6),
    
    volatility_21d      NUMERIC(10,6),
    atr_14              NUMERIC(12,4),
    rsi_14              NUMERIC(6,2),
    
    sma_20              NUMERIC(12,4),
    sma_50              NUMERIC(12,4),
    sma_200             NUMERIC(12,4),
    
    dist_from_sma20     NUMERIC(10,6),
    dist_from_sma50     NUMERIC(10,6),
    dist_from_sma200    NUMERIC(10,6),
    
    bb_upper            NUMERIC(12,4),
    bb_lower            NUMERIC(12,4),
    bb_width            NUMERIC(10,6),
    
    volume_sma_20       NUMERIC(18,2),
    relative_volume     NUMERIC(10,4),
    obv                 NUMERIC(18,2),
    
    adx_14              NUMERIC(6,2),
    macd                NUMERIC(12,4),
    macd_signal         NUMERIC(12,4),
    macd_histogram      NUMERIC(12,4),
    
    -- Composite scores
    momentum_score      NUMERIC(6,2),      -- 0-100
    trend_score         NUMERIC(6,2),      -- 0-100
    volatility_rank     NUMERIC(6,2),      -- 0-100 percentile
    
    -- Sentiment features
    news_sentiment_1d   NUMERIC(5,2),
    news_sentiment_7d   NUMERIC(5,2),
    social_sentiment_1d NUMERIC(5,2),
    social_mention_count INTEGER,
    sentiment_momentum  NUMERIC(10,6),
    
    -- Metadata
    created_at          TIMESTAMPTZ DEFAULT NOW(),
    
    PRIMARY KEY (ts, ticker)
);

SELECT create_hypertable('time_series.features', 'ts', chunk_time_interval => INTERVAL '1 day');
```

### 6. Market Breadth

```sql
-- time_series.market_breadth
CREATE TABLE time_series.market_breadth (
    ts                      TIMESTAMPTZ PRIMARY KEY,
    
    -- Advance/Decline
    advancers               INTEGER,
    decliners               INTEGER,
    unchanged               INTEGER,
    ad_ratio                NUMERIC(8,4),
    ad_line                 NUMERIC(18,2),
    mcclellan_oscillator    NUMERIC(10,4),
    mcclellan_summation     NUMERIC(18,2),
    
    -- New Highs/Lows
    new_52w_highs           INTEGER,
    new_52w_lows            INTEGER,
    hi_lo_ratio             NUMERIC(8,4),
    
    -- Breadth Indicators
    pct_above_sma20         NUMERIC(6,2),
    pct_above_sma50         NUMERIC(6,2),
    pct_above_sma200        NUMERIC(6,2),
    
    -- Volatility
    vix_close               NUMERIC(8,2),
    vix_term_structure      NUMERIC(8,4),  -- VIX/VIX3M ratio
    
    -- Sector Performance
    sector_performance      JSONB,         -- {XLK: 1.2, XLF: -0.3, ...}
    
    -- Regime indicators
    risk_on_score           NUMERIC(6,2),  -- 0-100
    regime_label            VARCHAR(20),   -- risk_on, risk_off, neutral
    
    created_at              TIMESTAMPTZ DEFAULT NOW()
);
```

### 7. Signals

```sql
-- time_series.signals
CREATE TABLE time_series.signals (
    id                  UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    generated_at        TIMESTAMPTZ NOT NULL,
    
    -- Signal identification
    ticker              VARCHAR(10) NOT NULL,
    strategy_id         VARCHAR(50) NOT NULL,
    strategy_version    VARCHAR(20),
    
    -- Direction & Timing
    direction           VARCHAR(10) NOT NULL,  -- long, short, close
    horizon             VARCHAR(20),           -- intraday, swing, position
    entry_type          VARCHAR(20),           -- market, limit, stop
    
    -- Price levels
    entry_price         NUMERIC(12,4),
    stop_loss           NUMERIC(12,4),
    target_1            NUMERIC(12,4),
    target_2            NUMERIC(12,4),
    target_3            NUMERIC(12,4),
    
    -- Risk metrics
    risk_reward_ratio   NUMERIC(6,2),
    position_size_pct   NUMERIC(6,4),         -- % of portfolio
    max_loss_pct        NUMERIC(6,4),
    
    -- Confidence & validation
    confidence_score    INTEGER CHECK (confidence_score BETWEEN 0 AND 100),
    gpt_validated       BOOLEAN DEFAULT FALSE,
    gpt_rationale       TEXT,
    
    -- Context
    entry_logic         TEXT,
    invalidation        TEXT,
    catalyst            TEXT,
    key_risks           TEXT[],
    
    -- Feature snapshot (for backtesting)
    feature_snapshot    JSONB,
    
    -- Lifecycle
    status              VARCHAR(20) DEFAULT 'pending',  -- pending, active, closed, expired, cancelled
    expires_at          TIMESTAMPTZ,
    activated_at        TIMESTAMPTZ,
    closed_at           TIMESTAMPTZ,
    close_reason        VARCHAR(50),
    
    -- Performance (filled post-trade)
    actual_entry        NUMERIC(12,4),
    actual_exit         NUMERIC(12,4),
    pnl_pct             NUMERIC(10,6),
    pnl_dollars         NUMERIC(12,2),
    mae_pct             NUMERIC(10,6),        -- Max Adverse Excursion
    mfe_pct             NUMERIC(10,6),        -- Max Favorable Excursion
    
    created_at          TIMESTAMPTZ DEFAULT NOW(),
    updated_at          TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX idx_signals_ticker ON time_series.signals (ticker, generated_at DESC);
CREATE INDEX idx_signals_status ON time_series.signals (status, generated_at DESC);
CREATE INDEX idx_signals_strategy ON time_series.signals (strategy_id, generated_at DESC);
```

### 8. Calendar Events

```sql
-- documents.calendar_events
CREATE TABLE documents.calendar_events (
    id                  UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    event_date          DATE NOT NULL,
    event_time          TIME,
    
    event_type          VARCHAR(30) NOT NULL,  -- earnings, dividend, split, fda, fomc, cpi, etc.
    ticker              VARCHAR(10),           -- NULL for macro events
    
    -- Event details
    title               TEXT,
    description         TEXT,
    
    -- Earnings specific
    eps_estimate        NUMERIC(10,4),
    eps_actual          NUMERIC(10,4),
    revenue_estimate    NUMERIC(18,2),
    revenue_actual      NUMERIC(18,2),
    surprise_pct        NUMERIC(8,4),
    
    -- Importance
    importance          VARCHAR(10),           -- low, medium, high
    
    -- Status
    status              VARCHAR(20) DEFAULT 'scheduled',  -- scheduled, confirmed, completed, cancelled
    
    created_at          TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX idx_calendar_date ON documents.calendar_events (event_date, event_type);
CREATE INDEX idx_calendar_ticker ON documents.calendar_events (ticker, event_date);
```

### 9. Daily Reports

```sql
-- documents.daily_reports
CREATE TABLE documents.daily_reports (
    id                  UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    report_date         DATE NOT NULL UNIQUE,
    generated_at        TIMESTAMPTZ NOT NULL,
    
    -- Report content
    markdown_content    TEXT NOT NULL,
    html_content        TEXT,
    
    -- Structured data
    market_summary      JSONB,
    signals_generated   JSONB,
    key_events          JSONB,
    
    -- Metadata
    generation_time_ms  INTEGER,
    gpt_tokens_used     INTEGER,
    
    created_at          TIMESTAMPTZ DEFAULT NOW()
);
```

### 10. Backtest Results

```sql
-- analytics.backtest_results
CREATE TABLE analytics.backtest_results (
    id                  UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    run_id              VARCHAR(50) NOT NULL,
    run_at              TIMESTAMPTZ NOT NULL,
    
    -- Configuration
    strategy_id         VARCHAR(50) NOT NULL,
    strategy_version    VARCHAR(20),
    parameters          JSONB,
    
    -- Test period
    start_date          DATE NOT NULL,
    end_date            DATE NOT NULL,
    universe            TEXT[],
    
    -- Performance Metrics
    total_return        NUMERIC(10,6),
    annualized_return   NUMERIC(10,6),
    sharpe_ratio        NUMERIC(8,4),
    sortino_ratio       NUMERIC(8,4),
    calmar_ratio        NUMERIC(8,4),
    max_drawdown        NUMERIC(10,6),
    max_drawdown_days   INTEGER,
    
    -- Trade Statistics
    total_trades        INTEGER,
    winning_trades      INTEGER,
    losing_trades       INTEGER,
    win_rate            NUMERIC(6,4),
    avg_win             NUMERIC(10,6),
    avg_loss            NUMERIC(10,6),
    profit_factor       NUMERIC(8,4),
    expectancy          NUMERIC(10,6),
    
    -- Risk Metrics
    var_95              NUMERIC(10,6),
    cvar_95             NUMERIC(10,6),
    volatility          NUMERIC(10,6),
    beta                NUMERIC(8,4),
    alpha               NUMERIC(10,6),
    
    -- Detailed results
    trades_json         JSONB,
    equity_curve        JSONB,
    monthly_returns     JSONB,
    
    created_at          TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX idx_backtest_strategy ON analytics.backtest_results (strategy_id, run_at DESC);
```

---

## Entity Relationship Diagram

```
┌──────────────┐       ┌──────────────┐       ┌──────────────┐
│    ohlcv     │       │  features    │       │   signals    │
│──────────────│       │──────────────│       │──────────────│
│ ts           │──┐    │ ts           │──┐    │ id           │
│ ticker       │  │    │ ticker       │  │    │ generated_at │
│ open/high/   │  │    │ return_*     │  │    │ ticker       │
│ low/close    │  │    │ volatility_* │  ├───>│ direction    │
│ volume       │  │    │ sentiment_*  │  │    │ confidence   │
└──────────────┘  │    └──────────────┘  │    └──────────────┘
                  │           │          │           │
                  │           ▼          │           │
                  │    ┌──────────────┐  │           │
                  └───>│   tickers    │<─┘           │
                       │ (reference)  │              │
                       │──────────────│              │
                       │ ticker       │              │
                       │ name         │              │
                       │ sector       │              │
                       │ market_cap   │              │
                       └──────────────┘              │
                              │                      │
                              ▼                      │
┌──────────────┐       ┌──────────────┐              │
│news_articles │       │ fundamentals │              │
│──────────────│       │──────────────│              │
│ id           │       │ ticker       │              │
│ tickers[]    │──────>│ report_date  │              │
│ sentiment    │       │ revenue      │              │
│ content      │       │ eps          │              │
└──────────────┘       └──────────────┘              │
                              │                      │
                              ▼                      │
                       ┌──────────────┐              │
                       │  backtest_   │<─────────────┘
                       │   results    │
                       │──────────────│
                       │ strategy_id  │
                       │ sharpe_ratio │
                       │ win_rate     │
                       └──────────────┘
```

---

## Redis Cache Schema

```python
# Key patterns for Redis caching

REDIS_KEYS = {
    # Real-time quotes (TTL: 60 seconds)
    "quote:{ticker}": {
        "price": 150.25,
        "change": 1.25,
        "change_pct": 0.84,
        "volume": 15234567,
        "updated_at": "2026-01-30T14:30:00Z"
    },
    
    # Feature cache (TTL: 5 minutes)
    "features:{ticker}:{date}": {
        "momentum_score": 72.5,
        "trend_score": 65.0,
        # ... all features
    },
    
    # Sentiment cache (TTL: 15 minutes)
    "sentiment:{ticker}:1d": {
        "news_score": 45.2,
        "social_score": 62.1,
        "combined": 53.65
    },
    
    # Rate limiting
    "ratelimit:{api}:{window}": 45,  # current count
    
    # Job queue
    "queue:signals": [...],  # list of pending signal jobs
    "queue:reports": [...],  # list of pending report jobs
}
```

---

## Data Retention Policy

| Table | Hot Storage | Warm Storage | Archive |
|-------|-------------|--------------|---------|
| ohlcv (1-min) | 30 days | 1 year | S3 Glacier |
| ohlcv (daily) | Forever | - | - |
| features | 90 days | 2 years | S3 |
| signals | Forever | - | - |
| news_articles | 1 year | 3 years | S3 |
| social_posts | 90 days | 1 year | Delete |
| backtest_results | Forever | - | - |
