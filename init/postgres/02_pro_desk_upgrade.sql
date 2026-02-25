-- =============================================================================
-- TradingAI Bot — Pro Desk Upgrade v6
-- Run AFTER 01_init.sql  (all statements are idempotent)
-- =============================================================================

-- ─────────────────────────────────────────────────────────────────────────────
-- 1. TICKER METADATA + LIQUIDITY CONSTRAINTS
-- ─────────────────────────────────────────────────────────────────────────────
DO $$ BEGIN
    ALTER TABLE time_series.tickers ADD COLUMN IF NOT EXISTS avg_daily_volume      BIGINT;
    ALTER TABLE time_series.tickers ADD COLUMN IF NOT EXISTS avg_dollar_volume_20d NUMERIC(18,2);
    ALTER TABLE time_series.tickers ADD COLUMN IF NOT EXISTS float_shares          BIGINT;
    ALTER TABLE time_series.tickers ADD COLUMN IF NOT EXISTS short_interest_pct    NUMERIC(6,2);
    ALTER TABLE time_series.tickers ADD COLUMN IF NOT EXISTS borrow_available      BOOLEAN DEFAULT TRUE;
    ALTER TABLE time_series.tickers ADD COLUMN IF NOT EXISTS has_options           BOOLEAN DEFAULT FALSE;
    ALTER TABLE time_series.tickers ADD COLUMN IF NOT EXISTS liquidity_tier        VARCHAR(2);  -- A/B/C
    ALTER TABLE time_series.tickers ADD COLUMN IF NOT EXISTS ipo_date              DATE;
    ALTER TABLE time_series.tickers ADD COLUMN IF NOT EXISTS country               VARCHAR(3) DEFAULT 'US';
    ALTER TABLE time_series.tickers ADD COLUMN IF NOT EXISTS currency              VARCHAR(3) DEFAULT 'USD';
EXCEPTION WHEN OTHERS THEN NULL;
END $$;

-- ─────────────────────────────────────────────────────────────────────────────
-- 2. OPTIONS / VOL SURFACE SUMMARY
-- ─────────────────────────────────────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS time_series.options_summary (
    ts                  TIMESTAMPTZ NOT NULL,
    ticker              VARCHAR(10) NOT NULL,

    iv_30d              NUMERIC(8,4),           -- 30-day implied volatility
    iv_rank             NUMERIC(6,2),           -- percentile rank (0-100)
    iv_percentile       NUMERIC(6,2),
    hv_30d              NUMERIC(8,4),           -- 30-day historical vol
    iv_hv_spread        NUMERIC(8,4),           -- iv_30d - hv_30d
    iv_term_structure   NUMERIC(8,4),           -- front/back ratio

    put_call_ratio      NUMERIC(8,4),
    put_call_oi_ratio   NUMERIC(8,4),

    implied_move_pct    NUMERIC(8,4),           -- next-earnings implied move
    max_pain_strike     NUMERIC(12,2),

    total_call_oi       BIGINT,
    total_put_oi        BIGINT,
    total_call_volume   BIGINT,
    total_put_volume    BIGINT,

    created_at          TIMESTAMPTZ DEFAULT NOW(),
    PRIMARY KEY (ts, ticker)
);

DO $$ BEGIN
    SELECT create_hypertable('time_series.options_summary', 'ts',
        chunk_time_interval => INTERVAL '1 day',
        if_not_exists => TRUE);
EXCEPTION WHEN OTHERS THEN NULL;
END $$;

CREATE INDEX IF NOT EXISTS idx_options_ticker ON time_series.options_summary (ticker, ts DESC);

-- ─────────────────────────────────────────────────────────────────────────────
-- 3. USER PERSONALISATION
-- ─────────────────────────────────────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS system.user_settings (
    user_id             VARCHAR(64) PRIMARY KEY,  -- Discord/Telegram user ID
    platform            VARCHAR(10) DEFAULT 'discord',
    display_name        VARCHAR(100),

    -- Risk profile
    risk_pct_per_trade  NUMERIC(5,2) DEFAULT 1.0,
    max_position_pct    NUMERIC(5,2) DEFAULT 5.0,
    max_sector_pct      NUMERIC(5,2) DEFAULT 25.0,
    max_open_trades     INTEGER DEFAULT 10,

    -- Style preferences
    trading_style       VARCHAR(20) DEFAULT 'swing',   -- day/swing/position
    preferred_horizon   VARCHAR(20) DEFAULT 'SWING_5_15D',
    min_confidence      INTEGER DEFAULT 60,
    preferred_strategies TEXT[] DEFAULT '{}',

    -- Account link
    broker_type         VARCHAR(20),
    account_size_approx NUMERIC(14,2),

    -- Notification prefs
    notify_signals      BOOLEAN DEFAULT TRUE,
    notify_morning      BOOLEAN DEFAULT TRUE,
    notify_risk         BOOLEAN DEFAULT TRUE,
    notify_eod          BOOLEAN DEFAULT TRUE,

    created_at          TIMESTAMPTZ DEFAULT NOW(),
    updated_at          TIMESTAMPTZ DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS system.user_watchlists (
    id                  UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id             VARCHAR(64) NOT NULL,
    name                VARCHAR(50) DEFAULT 'default',
    tickers             TEXT[] DEFAULT '{}',
    created_at          TIMESTAMPTZ DEFAULT NOW(),
    updated_at          TIMESTAMPTZ DEFAULT NOW(),
    UNIQUE (user_id, name)
);

CREATE TABLE IF NOT EXISTS analytics.user_performance (
    id                  UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id             VARCHAR(64) NOT NULL,
    period_start        DATE NOT NULL,
    period_end          DATE NOT NULL,
    period_type         VARCHAR(10) DEFAULT 'weekly', -- daily/weekly/monthly

    total_signals_taken INTEGER DEFAULT 0,
    wins                INTEGER DEFAULT 0,
    losses              INTEGER DEFAULT 0,
    win_rate            NUMERIC(6,4),
    total_pnl_pct       NUMERIC(10,6),
    avg_r_multiple      NUMERIC(8,4),
    best_trade_ticker   VARCHAR(10),
    worst_trade_ticker  VARCHAR(10),

    created_at          TIMESTAMPTZ DEFAULT NOW(),
    UNIQUE (user_id, period_start, period_type)
);

-- ─────────────────────────────────────────────────────────────────────────────
-- 4. EXTENDED SIGNAL FIELDS (pro-desk upgrade)
-- ─────────────────────────────────────────────────────────────────────────────
DO $$ BEGIN
    -- v6: Pro desk signal fields
    ALTER TABLE time_series.signals ADD COLUMN IF NOT EXISTS setup_grade         VARCHAR(2);   -- A/B/C
    ALTER TABLE time_series.signals ADD COLUMN IF NOT EXISTS time_stop_days      INTEGER;
    ALTER TABLE time_series.signals ADD COLUMN IF NOT EXISTS event_risk          JSONB;
    ALTER TABLE time_series.signals ADD COLUMN IF NOT EXISTS scenario_plan       JSONB;        -- base/bull/bear
    ALTER TABLE time_series.signals ADD COLUMN IF NOT EXISTS portfolio_fit       JSONB;        -- correlation, sector, factor
    ALTER TABLE time_series.signals ADD COLUMN IF NOT EXISTS evidence            JSONB;        -- structured reasons
    ALTER TABLE time_series.signals ADD COLUMN IF NOT EXISTS expected_value      NUMERIC(10,6);
    ALTER TABLE time_series.signals ADD COLUMN IF NOT EXISTS edge_type           VARCHAR(30);  -- trend/mean-reversion/catalyst/volatility
    ALTER TABLE time_series.signals ADD COLUMN IF NOT EXISTS approval_status     VARCHAR(20) DEFAULT 'pending'; -- approved/conditional/rejected
    ALTER TABLE time_series.signals ADD COLUMN IF NOT EXISTS approval_flags      JSONB;
    ALTER TABLE time_series.signals ADD COLUMN IF NOT EXISTS gpt_validation_json JSONB;
    ALTER TABLE time_series.signals ADD COLUMN IF NOT EXISTS prompt_version      VARCHAR(20);
EXCEPTION WHEN OTHERS THEN NULL;
END $$;

CREATE INDEX IF NOT EXISTS idx_signals_approval ON time_series.signals (approval_status, generated_at DESC);
CREATE INDEX IF NOT EXISTS idx_signals_grade    ON time_series.signals (setup_grade, generated_at DESC);

-- ─────────────────────────────────────────────────────────────────────────────
-- 5. DATA QUALITY GATE LOG
-- ─────────────────────────────────────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS system.data_quality_log (
    id                  UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    check_time          TIMESTAMPTZ DEFAULT NOW(),
    feed_name           VARCHAR(50) NOT NULL,         -- ohlcv, features, breadth, news, social
    check_type          VARCHAR(30) NOT NULL,         -- freshness, missing_bars, outlier, symbol_map
    passed              BOOLEAN DEFAULT TRUE,
    severity            VARCHAR(10) DEFAULT 'info',   -- info/warning/critical
    details             JSONB,
    affected_tickers    TEXT[],
    created_at          TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_dq_feed ON system.data_quality_log (feed_name, check_time DESC);

-- ─────────────────────────────────────────────────────────────────────────────
-- 6. PROMPT VERSIONING
-- ─────────────────────────────────────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS system.prompt_versions (
    id                  UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    prompt_name         VARCHAR(50) NOT NULL,     -- signal_validation, market_summary, trade_brief, sentiment
    version             VARCHAR(20) NOT NULL,
    prompt_text         TEXT NOT NULL,
    prompt_hash         VARCHAR(64),
    is_active           BOOLEAN DEFAULT TRUE,
    created_at          TIMESTAMPTZ DEFAULT NOW(),
    UNIQUE (prompt_name, version)
);

-- ─────────────────────────────────────────────────────────────────────────────
-- 7. DELTA TRACKING (what changed since last report)
-- ─────────────────────────────────────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS analytics.delta_snapshots (
    id                  UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    snapshot_date       DATE NOT NULL,
    session             VARCHAR(10) DEFAULT 'close',  -- open/close

    -- Index returns
    spx_1d_pct          NUMERIC(8,4),
    spx_5d_pct          NUMERIC(8,4),
    ndx_1d_pct          NUMERIC(8,4),
    ndx_5d_pct          NUMERIC(8,4),
    iwm_1d_pct          NUMERIC(8,4),
    iwm_5d_pct          NUMERIC(8,4),

    -- Volatility
    vix_close           NUMERIC(8,2),
    vix_1d_change       NUMERIC(8,2),
    vix_5d_change       NUMERIC(8,2),

    -- Rates
    yield_10y           NUMERIC(6,3),
    yield_10y_1d_bp     NUMERIC(6,1),
    yield_10y_5d_bp     NUMERIC(6,1),

    -- Breadth
    pct_above_50dma     NUMERIC(6,2),
    pct_above_50dma_1d  NUMERIC(6,2),
    new_highs           INTEGER,
    new_lows            INTEGER,

    -- Sector leadership
    top_3_sectors       JSONB,    -- [{"name":"XLK","pct":1.2},...]
    bottom_3_sectors    JSONB,

    -- Sentiment
    news_sentiment_1d   NUMERIC(5,2),
    social_sentiment_1d NUMERIC(5,2),
    sentiment_change    NUMERIC(5,2),

    -- Flows / positioning
    put_call_ratio      NUMERIC(8,4),
    iv_rank_spy         NUMERIC(6,2),

    created_at          TIMESTAMPTZ DEFAULT NOW(),
    UNIQUE (snapshot_date, session)
);

-- ─────────────────────────────────────────────────────────────────────────────
-- 8. BACKTEST DIAGNOSTICS (regime / sector / vol bucket breakdowns)
-- ─────────────────────────────────────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS analytics.backtest_diagnostics (
    id                  UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    backtest_run_id     UUID NOT NULL,
    strategy_id         VARCHAR(50) NOT NULL,

    -- Slice type: regime / sector / volatility / exit_type
    slice_type          VARCHAR(20) NOT NULL,
    slice_label         VARCHAR(50) NOT NULL,

    total_trades        INTEGER,
    wins                INTEGER,
    losses              INTEGER,
    win_rate            NUMERIC(6,4),
    avg_pnl_pct         NUMERIC(10,6),
    avg_rr_realized     NUMERIC(8,4),
    sharpe              NUMERIC(8,4),
    avg_mae_pct         NUMERIC(10,6),
    avg_mfe_pct         NUMERIC(10,6),
    avg_holding_days    NUMERIC(6,1),

    -- Stop vs time-stop attribution
    stop_exits          INTEGER DEFAULT 0,
    time_stop_exits     INTEGER DEFAULT 0,
    target_exits        INTEGER DEFAULT 0,
    trail_stop_exits    INTEGER DEFAULT 0,

    created_at          TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_bt_diag_run ON analytics.backtest_diagnostics (backtest_run_id);
CREATE INDEX IF NOT EXISTS idx_bt_diag_strat ON analytics.backtest_diagnostics (strategy_id, slice_type);

COMMIT;
