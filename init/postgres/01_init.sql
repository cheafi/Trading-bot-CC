-- TradingAI Bot - Database Initialization
-- This script runs automatically when the PostgreSQL container starts

-- Enable required extensions
CREATE EXTENSION IF NOT EXISTS "uuid-ossp";
CREATE EXTENSION IF NOT EXISTS "pg_trgm";  -- For text search

-- Create schemas
CREATE SCHEMA IF NOT EXISTS time_series;
CREATE SCHEMA IF NOT EXISTS documents;
CREATE SCHEMA IF NOT EXISTS analytics;
CREATE SCHEMA IF NOT EXISTS system;

-- Grant permissions
GRANT ALL ON SCHEMA time_series TO tradingai;
GRANT ALL ON SCHEMA documents TO tradingai;
GRANT ALL ON SCHEMA analytics TO tradingai;
GRANT ALL ON SCHEMA system TO tradingai;

-- =============================================================================
-- TIME SERIES SCHEMA
-- =============================================================================

-- OHLCV data (will be converted to hypertable)
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
    created_at      TIMESTAMPTZ DEFAULT NOW(),
    -- Unique constraint to prevent duplicate data
    CONSTRAINT ohlcv_unique_ts_ticker_source UNIQUE (ts, ticker, source)
);

-- Convert to hypertable (TimescaleDB)
SELECT create_hypertable('time_series.ohlcv', 'ts', 
    chunk_time_interval => INTERVAL '1 day',
    if_not_exists => TRUE
);

-- Compression policy
ALTER TABLE time_series.ohlcv SET (
    timescaledb.compress,
    timescaledb.compress_segmentby = 'ticker'
);
SELECT add_compression_policy('time_series.ohlcv', INTERVAL '7 days', if_not_exists => TRUE);

-- Indexes
CREATE INDEX IF NOT EXISTS idx_ohlcv_ticker_ts ON time_series.ohlcv (ticker, ts DESC);

-- Tickers reference table
CREATE TABLE time_series.tickers (
    ticker          VARCHAR(10) PRIMARY KEY,
    name            VARCHAR(200),
    sector          VARCHAR(50),
    industry        VARCHAR(100),
    market_cap      BIGINT,
    exchange        VARCHAR(20),
    is_active       BOOLEAN DEFAULT TRUE,
    created_at      TIMESTAMPTZ DEFAULT NOW(),
    updated_at      TIMESTAMPTZ DEFAULT NOW()
);

-- Features table
CREATE TABLE time_series.features (
    ts                  TIMESTAMPTZ NOT NULL,
    ticker              VARCHAR(10) NOT NULL,
    
    -- Price returns
    return_1d           NUMERIC(10,6),
    return_5d           NUMERIC(10,6),
    return_21d          NUMERIC(10,6),
    return_63d          NUMERIC(10,6),
    
    -- Volatility
    volatility_21d      NUMERIC(10,6),
    atr_14              NUMERIC(12,4),
    rsi_14              NUMERIC(6,2),
    
    -- Moving averages
    sma_20              NUMERIC(12,4),
    sma_50              NUMERIC(12,4),
    sma_200             NUMERIC(12,4),
    dist_from_sma20     NUMERIC(10,6),
    dist_from_sma50     NUMERIC(10,6),
    dist_from_sma200    NUMERIC(10,6),
    
    -- Bollinger bands
    bb_upper            NUMERIC(12,4),
    bb_lower            NUMERIC(12,4),
    bb_width            NUMERIC(10,6),
    
    -- Volume
    volume_sma_20       NUMERIC(18,2),
    relative_volume     NUMERIC(10,4),
    obv                 NUMERIC(18,2),
    
    -- Trend
    adx_14              NUMERIC(6,2),
    macd                NUMERIC(12,4),
    macd_signal         NUMERIC(12,4),
    macd_histogram      NUMERIC(12,4),
    
    -- Composite scores
    momentum_score      NUMERIC(6,2),
    trend_score         NUMERIC(6,2),
    volatility_rank     NUMERIC(6,2),
    
    -- Sentiment
    news_sentiment_1d   NUMERIC(5,2),
    news_sentiment_7d   NUMERIC(5,2),
    social_sentiment_1d NUMERIC(5,2),
    social_mention_count INTEGER,
    sentiment_momentum  NUMERIC(10,6),
    
    created_at          TIMESTAMPTZ DEFAULT NOW(),
    
    PRIMARY KEY (ts, ticker)
);

SELECT create_hypertable('time_series.features', 'ts', 
    chunk_time_interval => INTERVAL '1 day',
    if_not_exists => TRUE
);

-- Market breadth
CREATE TABLE time_series.market_breadth (
    ts                      TIMESTAMPTZ PRIMARY KEY,
    
    advancers               INTEGER,
    decliners               INTEGER,
    unchanged               INTEGER,
    ad_ratio                NUMERIC(8,4),
    ad_line                 NUMERIC(18,2),
    mcclellan_oscillator    NUMERIC(10,4),
    mcclellan_summation     NUMERIC(18,2),
    
    new_52w_highs           INTEGER,
    new_52w_lows            INTEGER,
    hi_lo_ratio             NUMERIC(8,4),
    
    pct_above_sma20         NUMERIC(6,2),
    pct_above_sma50         NUMERIC(6,2),
    pct_above_sma200        NUMERIC(6,2),
    
    vix_close               NUMERIC(8,2),
    vix_term_structure      NUMERIC(8,4),
    
    sector_performance      JSONB,
    risk_on_score           NUMERIC(6,2),
    regime_label            VARCHAR(20),
    
    created_at              TIMESTAMPTZ DEFAULT NOW()
);

SELECT create_hypertable('time_series.market_breadth', 'ts', 
    chunk_time_interval => INTERVAL '1 month',
    if_not_exists => TRUE
);

-- Signals
CREATE TABLE time_series.signals (
    id                  UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    generated_at        TIMESTAMPTZ NOT NULL,
    
    ticker              VARCHAR(10) NOT NULL,
    strategy_id         VARCHAR(50) NOT NULL,
    strategy_version    VARCHAR(20),
    
    direction           VARCHAR(10) NOT NULL,
    horizon             VARCHAR(20),
    entry_type          VARCHAR(20),
    
    entry_price         NUMERIC(12,4),
    stop_loss           NUMERIC(12,4),
    target_1            NUMERIC(12,4),
    target_2            NUMERIC(12,4),
    target_3            NUMERIC(12,4),
    
    risk_reward_ratio   NUMERIC(6,2),
    position_size_pct   NUMERIC(6,4),
    max_loss_pct        NUMERIC(6,4),
    
    confidence_score    INTEGER CHECK (confidence_score BETWEEN 0 AND 100),
    gpt_validated       BOOLEAN DEFAULT FALSE,
    gpt_rationale       TEXT,
    
    entry_logic         TEXT,
    invalidation        TEXT,
    catalyst            TEXT,
    key_risks           TEXT[],
    
    feature_snapshot    JSONB,
    
    status              VARCHAR(20) DEFAULT 'pending',
    expires_at          TIMESTAMPTZ,
    activated_at        TIMESTAMPTZ,
    closed_at           TIMESTAMPTZ,
    close_reason        VARCHAR(50),
    
    actual_entry        NUMERIC(12,4),
    actual_exit         NUMERIC(12,4),
    pnl_pct             NUMERIC(10,6),
    pnl_dollars         NUMERIC(12,2),
    mae_pct             NUMERIC(10,6),
    mfe_pct             NUMERIC(10,6),
    
    created_at          TIMESTAMPTZ DEFAULT NOW(),
    updated_at          TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX idx_signals_ticker ON time_series.signals (ticker, generated_at DESC);
CREATE INDEX idx_signals_status ON time_series.signals (status, generated_at DESC);
CREATE INDEX idx_signals_strategy ON time_series.signals (strategy_id, generated_at DESC);

-- =============================================================================
-- DOCUMENTS SCHEMA
-- =============================================================================

-- News articles
CREATE TABLE documents.news_articles (
    id                  UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    published_at        TIMESTAMPTZ NOT NULL,
    source              VARCHAR(50),
    author              VARCHAR(100),
    title               TEXT NOT NULL,
    summary             TEXT,
    content             TEXT,
    url                 TEXT,
    
    tickers             VARCHAR(10)[] DEFAULT '{}',
    sectors             VARCHAR(50)[] DEFAULT '{}',
    topics              VARCHAR(50)[] DEFAULT '{}',
    
    sentiment_score     NUMERIC(5,2),
    sentiment_label     VARCHAR(20),
    sentiment_rationale TEXT,
    
    article_type        VARCHAR(30),
    urgency             VARCHAR(10),
    
    raw_json            JSONB,
    processed           BOOLEAN DEFAULT FALSE,
    created_at          TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX idx_news_tickers ON documents.news_articles USING GIN (tickers);
CREATE INDEX idx_news_published ON documents.news_articles (published_at DESC);
CREATE INDEX idx_news_title_trgm ON documents.news_articles USING GIN (title gin_trgm_ops);

-- Social posts
CREATE TABLE documents.social_posts (
    id                  UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    platform            VARCHAR(20) NOT NULL,
    post_id             VARCHAR(100) NOT NULL,
    posted_at           TIMESTAMPTZ NOT NULL,
    author_handle       VARCHAR(100),
    author_followers    INTEGER,
    
    content             TEXT NOT NULL,
    url                 TEXT,
    
    likes               INTEGER DEFAULT 0,
    reposts             INTEGER DEFAULT 0,
    replies             INTEGER DEFAULT 0,
    
    tickers             VARCHAR(10)[] DEFAULT '{}',
    cashtags            VARCHAR(10)[] DEFAULT '{}',
    
    sentiment_score     NUMERIC(5,2),
    sentiment_label     VARCHAR(20),
    
    is_influencer       BOOLEAN DEFAULT FALSE,
    is_verified         BOOLEAN DEFAULT FALSE,
    spam_score          NUMERIC(5,2),
    
    created_at          TIMESTAMPTZ DEFAULT NOW(),
    
    UNIQUE (platform, post_id)
);

CREATE INDEX idx_social_tickers ON documents.social_posts USING GIN (tickers);
CREATE INDEX idx_social_posted ON documents.social_posts (posted_at DESC);

-- Calendar events
CREATE TABLE documents.calendar_events (
    id                  UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    event_date          DATE NOT NULL,
    event_time          TIME,
    
    event_type          VARCHAR(30) NOT NULL,
    ticker              VARCHAR(10),
    
    title               TEXT,
    description         TEXT,
    
    eps_estimate        NUMERIC(10,4),
    eps_actual          NUMERIC(10,4),
    revenue_estimate    NUMERIC(18,2),
    revenue_actual      NUMERIC(18,2),
    surprise_pct        NUMERIC(8,4),
    
    importance          VARCHAR(10),
    status              VARCHAR(20) DEFAULT 'scheduled',
    
    created_at          TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX idx_calendar_date ON documents.calendar_events (event_date, event_type);
CREATE INDEX idx_calendar_ticker ON documents.calendar_events (ticker, event_date);

-- Daily reports
CREATE TABLE documents.daily_reports (
    id                  UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    report_date         DATE NOT NULL UNIQUE,
    generated_at        TIMESTAMPTZ NOT NULL,
    
    markdown_content    TEXT NOT NULL,
    html_content        TEXT,
    
    market_summary      JSONB,
    signals_generated   JSONB,
    key_events          JSONB,
    
    generation_time_ms  INTEGER,
    gpt_tokens_used     INTEGER,
    
    created_at          TIMESTAMPTZ DEFAULT NOW()
);

-- =============================================================================
-- ANALYTICS SCHEMA
-- =============================================================================

-- Backtest results
CREATE TABLE analytics.backtest_results (
    id                  UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    run_id              VARCHAR(50) NOT NULL,
    run_at              TIMESTAMPTZ NOT NULL,
    
    strategy_id         VARCHAR(50) NOT NULL,
    strategy_version    VARCHAR(20),
    parameters          JSONB,
    
    start_date          DATE NOT NULL,
    end_date            DATE NOT NULL,
    universe            TEXT[],
    
    total_return        NUMERIC(10,6),
    annualized_return   NUMERIC(10,6),
    sharpe_ratio        NUMERIC(8,4),
    sortino_ratio       NUMERIC(8,4),
    calmar_ratio        NUMERIC(8,4),
    max_drawdown        NUMERIC(10,6),
    max_drawdown_days   INTEGER,
    
    total_trades        INTEGER,
    winning_trades      INTEGER,
    losing_trades       INTEGER,
    win_rate            NUMERIC(6,4),
    avg_win             NUMERIC(10,6),
    avg_loss            NUMERIC(10,6),
    profit_factor       NUMERIC(8,4),
    expectancy          NUMERIC(10,6),
    
    var_95              NUMERIC(10,6),
    cvar_95             NUMERIC(10,6),
    volatility          NUMERIC(10,6),
    beta                NUMERIC(8,4),
    alpha               NUMERIC(10,6),
    
    trades_json         JSONB,
    equity_curve        JSONB,
    monthly_returns     JSONB,
    
    created_at          TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX idx_backtest_strategy ON analytics.backtest_results (strategy_id, run_at DESC);

-- Live performance tracking
CREATE TABLE analytics.live_performance (
    id                  UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    date                DATE NOT NULL,
    strategy_id         VARCHAR(50),
    
    daily_pnl           NUMERIC(12,2),
    daily_return        NUMERIC(10,6),
    cumulative_return   NUMERIC(10,6),
    
    signals_generated   INTEGER,
    signals_triggered   INTEGER,
    signals_won         INTEGER,
    signals_lost        INTEGER,
    
    hit_rate            NUMERIC(6,4),
    expectancy          NUMERIC(10,6),
    
    created_at          TIMESTAMPTZ DEFAULT NOW(),
    
    UNIQUE (date, strategy_id)
);

-- =============================================================================
-- SYSTEM SCHEMA
-- =============================================================================

-- Job history
CREATE TABLE system.job_history (
    id                  UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    job_name            VARCHAR(100) NOT NULL,
    started_at          TIMESTAMPTZ NOT NULL,
    finished_at         TIMESTAMPTZ,
    status              VARCHAR(20),
    records_processed   INTEGER,
    error_message       TEXT,
    metadata            JSONB,
    created_at          TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX idx_job_history_name ON system.job_history (job_name, started_at DESC);

-- API keys
CREATE TABLE system.api_keys (
    id                  UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    key_hash            VARCHAR(64) NOT NULL UNIQUE,
    name                VARCHAR(100),
    permissions         VARCHAR(50)[] DEFAULT '{}',
    rate_limit          INTEGER DEFAULT 100,
    is_active           BOOLEAN DEFAULT TRUE,
    expires_at          TIMESTAMPTZ,
    last_used_at        TIMESTAMPTZ,
    created_at          TIMESTAMPTZ DEFAULT NOW()
);

-- Audit log
CREATE TABLE system.audit_log (
    id                  UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    action              VARCHAR(50) NOT NULL,
    entity_type         VARCHAR(50),
    entity_id           UUID,
    user_id             UUID,
    details             JSONB,
    ip_address          INET,
    created_at          TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX idx_audit_log_action ON system.audit_log (action, created_at DESC);

-- =============================================================================
-- CORPORATE ACTIONS (survivorship-bias protection)
-- =============================================================================

CREATE TABLE documents.corporate_actions (
    id                  UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    ticker              VARCHAR(10) NOT NULL,
    action_date         DATE NOT NULL,
    action_type         VARCHAR(30) NOT NULL,  -- SPLIT, DIVIDEND, SYMBOL_CHANGE, MERGER, SPINOFF, DELIST
    factor              NUMERIC(12,6),          -- split ratio or dividend amount
    old_ticker          VARCHAR(10),            -- for symbol changes
    new_ticker          VARCHAR(10),
    notes               TEXT,
    created_at          TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX idx_corp_actions_ticker ON documents.corporate_actions (ticker, action_date DESC);
CREATE INDEX idx_corp_actions_date   ON documents.corporate_actions (action_date DESC);

-- =============================================================================
-- MARKET STATE (NO-TRADE hard gate + regime history)
-- =============================================================================

CREATE TABLE system.market_state (
    ts                  TIMESTAMPTZ PRIMARY KEY DEFAULT NOW(),
    regime_label        VARCHAR(30),
    volatility_regime   VARCHAR(20),
    trend_regime        VARCHAR(20),
    risk_regime         VARCHAR(20),
    risk_on_score       NUMERIC(6,2),
    no_trade_flag       BOOLEAN DEFAULT FALSE,
    no_trade_reason     TEXT,
    active_strategies   TEXT[],
    vix                 NUMERIC(8,2),
    spx_change_pct      NUMERIC(8,4),
    breadth_pct50       NUMERIC(6,2),
    metadata            JSONB,
    created_at          TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX idx_market_state_ts ON system.market_state (ts DESC);

-- =============================================================================
-- LLM GOVERNANCE (every GPT call is tracked)
-- =============================================================================

CREATE TABLE system.llm_calls (
    id                  UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    call_type           VARCHAR(50) NOT NULL,  -- signal_validation, sentiment, summary, report
    model               VARCHAR(50),
    prompt_hash         VARCHAR(64),            -- SHA-256 of system+user prompt
    prompt_version      VARCHAR(20),
    input_tokens        INTEGER,
    output_tokens       INTEGER,
    latency_ms          INTEGER,
    cost_usd            NUMERIC(8,6),
    
    ticker              VARCHAR(10),
    signal_id           UUID,
    
    request_json        JSONB,                  -- full prompt (minus API key)
    response_json       JSONB,                  -- full response
    parsed_result       JSONB,                  -- extracted structured output
    
    success             BOOLEAN DEFAULT TRUE,
    error_message       TEXT,
    
    created_at          TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX idx_llm_calls_type ON system.llm_calls (call_type, created_at DESC);
CREATE INDEX idx_llm_calls_ticker ON system.llm_calls (ticker, created_at DESC);

-- =============================================================================
-- SIGNAL DEDUP + CONFLICT RESOLUTION
-- =============================================================================

-- Add columns to existing signals table (safe for existing data)
DO $$ BEGIN
    ALTER TABLE time_series.signals ADD COLUMN IF NOT EXISTS dedupe_key VARCHAR(128);
    ALTER TABLE time_series.signals ADD COLUMN IF NOT EXISTS conflict_group_id UUID;
    ALTER TABLE time_series.signals ADD COLUMN IF NOT EXISTS conflict_resolution JSONB;
    ALTER TABLE time_series.signals ADD COLUMN IF NOT EXISTS feature_version VARCHAR(20);
    ALTER TABLE time_series.signals ADD COLUMN IF NOT EXISTS data_snapshot_id UUID;
    ALTER TABLE time_series.signals ADD COLUMN IF NOT EXISTS setup_tags TEXT[];
    ALTER TABLE time_series.signals ADD COLUMN IF NOT EXISTS regime_at_signal JSONB;
    ALTER TABLE time_series.signals ADD COLUMN IF NOT EXISTS earnings_risk_days INTEGER;
    ALTER TABLE time_series.signals ADD COLUMN IF NOT EXISTS dollar_volume_20d NUMERIC(18,2);
    ALTER TABLE time_series.signals ADD COLUMN IF NOT EXISTS edge_checklist JSONB;
    ALTER TABLE time_series.signals ADD COLUMN IF NOT EXISTS why_now TEXT;
    ALTER TABLE time_series.signals ADD COLUMN IF NOT EXISTS invalidation_sentence TEXT;
EXCEPTION WHEN OTHERS THEN NULL;
END $$;

CREATE INDEX IF NOT EXISTS idx_signals_dedupe ON time_series.signals (dedupe_key);

-- Add model_version to news_articles for reproducibility
DO $$ BEGIN
    ALTER TABLE documents.news_articles ADD COLUMN IF NOT EXISTS model_version VARCHAR(30);
    ALTER TABLE documents.news_articles ADD COLUMN IF NOT EXISTS embedding JSONB;
EXCEPTION WHEN OTHERS THEN NULL;
END $$;

-- Add feature_version + pattern_features to features table
DO $$ BEGIN
    ALTER TABLE time_series.features ADD COLUMN IF NOT EXISTS feature_version VARCHAR(20);
    ALTER TABLE time_series.features ADD COLUMN IF NOT EXISTS dollar_volume_20d NUMERIC(18,2);
    -- v5: Pattern features JSONB — closes the live↔backtest mismatch for breakout strategies
    --   Keys: high_20d, low_20d, consolidation_days, consolidation_high, consolidation_low,
    --          bb_squeeze_flag, pivot_level, gap_pct, gap_filled_flag, high_52w, low_52w
    ALTER TABLE time_series.features ADD COLUMN IF NOT EXISTS pattern_features JSONB;
EXCEPTION WHEN OTHERS THEN NULL;
END $$;

-- =============================================================================
-- v5: Add execution_plan / risk_plan / edge_model to signals
-- =============================================================================
DO $$ BEGIN
    ALTER TABLE time_series.signals ADD COLUMN IF NOT EXISTS execution_plan JSONB;
    ALTER TABLE time_series.signals ADD COLUMN IF NOT EXISTS risk_plan JSONB;
    ALTER TABLE time_series.signals ADD COLUMN IF NOT EXISTS edge_model JSONB;
    ALTER TABLE time_series.signals ADD COLUMN IF NOT EXISTS market_playbook_id UUID;
EXCEPTION WHEN OTHERS THEN NULL;
END $$;

-- =============================================================================
-- SCORE CALIBRATION TABLE (maps score → historical win-rate per strategy+regime)
-- =============================================================================

CREATE TABLE IF NOT EXISTS analytics.score_calibration (
    id                  UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    strategy_id         VARCHAR(50) NOT NULL,
    regime_label        VARCHAR(30),
    score_bucket_low    INTEGER,
    score_bucket_high   INTEGER,
    sample_size         INTEGER,
    historical_win_rate NUMERIC(6,4),
    avg_rr_ratio        NUMERIC(8,4),
    avg_pnl_pct         NUMERIC(10,6),
    calibrated_at       TIMESTAMPTZ DEFAULT NOW(),
    UNIQUE (strategy_id, regime_label, score_bucket_low, score_bucket_high)
);

-- =============================================================================
-- SIGNAL OUTCOMES (per-signal T1/T2/stop labels for calibration)
-- =============================================================================
CREATE TABLE IF NOT EXISTS analytics.signal_outcomes (
    id                  UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    signal_id           UUID NOT NULL,
    strategy_id         VARCHAR(50),
    regime_label        VARCHAR(30),
    volatility_regime   VARCHAR(20),
    setup_tags          TEXT[],
    calibration_bucket  VARCHAR(100),

    hit_t1              BOOLEAN,
    hit_t2              BOOLEAN,
    hit_stop            BOOLEAN,
    hit_time_stop       BOOLEAN,

    time_to_t1_days     INTEGER,
    time_to_t2_days     INTEGER,
    holding_days        INTEGER,

    mae_pct             NUMERIC(10,6),
    mfe_pct             NUMERIC(10,6),
    pnl_pct             NUMERIC(10,6),

    entry_price         NUMERIC(12,4),
    exit_price          NUMERIC(12,4),
    exit_reason         VARCHAR(50),

    created_at          TIMESTAMPTZ DEFAULT NOW()
);
CREATE INDEX IF NOT EXISTS idx_outcomes_bucket ON analytics.signal_outcomes (calibration_bucket);
CREATE INDEX IF NOT EXISTS idx_outcomes_strategy ON analytics.signal_outcomes (strategy_id, regime_label);

-- =============================================================================
-- REGIME EDGE STATS (pre-computed P(win) / EV per strategy+regime bucket)
-- =============================================================================
CREATE TABLE IF NOT EXISTS analytics.regime_edge_stats (
    id                  UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    calibration_bucket  VARCHAR(100) NOT NULL,
    strategy_id         VARCHAR(50) NOT NULL,
    regime_label        VARCHAR(30),
    volatility_regime   VARCHAR(20),

    sample_size         INTEGER,
    p_t1                NUMERIC(6,4),
    p_t2                NUMERIC(6,4),
    p_stop              NUMERIC(6,4),
    expected_return_pct NUMERIC(10,6),
    expected_mae_pct    NUMERIC(10,6),
    expected_holding_days NUMERIC(6,1),
    avg_rr_realized     NUMERIC(8,4),

    computed_at         TIMESTAMPTZ DEFAULT NOW(),
    UNIQUE (calibration_bucket, strategy_id, regime_label, volatility_regime)
);

-- =============================================================================
-- MARKET PLAYBOOK (daily regime → strategy mapping + risk stance)
-- =============================================================================
CREATE TABLE IF NOT EXISTS analytics.market_playbook (
    id                  UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    playbook_date       DATE NOT NULL,
    session             VARCHAR(20) DEFAULT 'US_RTH',

    regime_label        VARCHAR(30),
    volatility_regime   VARCHAR(20),
    trend_regime        VARCHAR(20),
    risk_regime         VARCHAR(20),
    risk_on_score       NUMERIC(6,2),

    playbook_text       TEXT,
    recommended_strategies TEXT[],
    sizing_stance       VARCHAR(20),
    key_levels          JSONB,
    change_summary      JSONB,
    risk_bulletin       JSONB,

    created_at          TIMESTAMPTZ DEFAULT NOW(),
    UNIQUE (playbook_date, session)
);

-- =============================================================================
-- ATTRIBUTION REPORTS (regime / sector / event / factor / trade-mgmt)
-- =============================================================================
CREATE TABLE IF NOT EXISTS analytics.attribution_reports (
    id                  UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    report_type         VARCHAR(30) NOT NULL,
    strategy_id         VARCHAR(50),
    period_start        DATE,
    period_end          DATE,
    attribution_data    JSONB NOT NULL,
    computed_at         TIMESTAMPTZ DEFAULT NOW()
);
CREATE INDEX IF NOT EXISTS idx_attribution_type ON analytics.attribution_reports (report_type, strategy_id);

-- =============================================================================
-- HELPER FUNCTIONS
-- =============================================================================

-- Function to update updated_at timestamp
CREATE OR REPLACE FUNCTION update_updated_at_column()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = NOW();
    RETURN NEW;
END;
$$ language 'plpgsql';

-- Apply trigger to signals table
CREATE TRIGGER update_signals_updated_at
    BEFORE UPDATE ON time_series.signals
    FOR EACH ROW
    EXECUTE FUNCTION update_updated_at_column();

-- Apply trigger to tickers table
CREATE TRIGGER update_tickers_updated_at
    BEFORE UPDATE ON time_series.tickers
    FOR EACH ROW
    EXECUTE FUNCTION update_updated_at_column();

-- =============================================================================
-- SEED DATA
-- =============================================================================

-- Insert common sector ETFs for reference
INSERT INTO time_series.tickers (ticker, name, sector) VALUES
    ('SPY', 'SPDR S&P 500 ETF', 'Broad Market'),
    ('QQQ', 'Invesco QQQ Trust', 'Technology'),
    ('IWM', 'iShares Russell 2000 ETF', 'Small Cap'),
    ('XLK', 'Technology Select Sector SPDR', 'Technology'),
    ('XLF', 'Financial Select Sector SPDR', 'Financials'),
    ('XLE', 'Energy Select Sector SPDR', 'Energy'),
    ('XLV', 'Health Care Select Sector SPDR', 'Healthcare'),
    ('XLI', 'Industrial Select Sector SPDR', 'Industrials'),
    ('XLC', 'Communication Services Select Sector SPDR', 'Communication'),
    ('XLY', 'Consumer Discretionary Select Sector SPDR', 'Consumer Discretionary'),
    ('XLP', 'Consumer Staples Select Sector SPDR', 'Consumer Staples'),
    ('XLU', 'Utilities Select Sector SPDR', 'Utilities'),
    ('XLB', 'Materials Select Sector SPDR', 'Materials'),
    ('XLRE', 'Real Estate Select Sector SPDR', 'Real Estate')
ON CONFLICT (ticker) DO NOTHING;

COMMIT;
