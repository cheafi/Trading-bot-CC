-- =============================================================================
-- TradingAI Bot — Decision-Layer Persistence (Sprint 11)
-- Run AFTER 02_pro_desk_upgrade.sql  (all statements are idempotent)
-- =============================================================================

-- ─────────────────────────────────────────────────────────────────────────────
-- 1. TRADE OUTCOMES (ML learning loop persistence)
-- ─────────────────────────────────────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS analytics.trade_outcomes (
    id                  UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    trade_id            VARCHAR(100) NOT NULL,
    ticker              VARCHAR(10) NOT NULL,
    direction           VARCHAR(10) NOT NULL,          -- LONG / SHORT
    strategy            VARCHAR(50) NOT NULL,

    entry_price         NUMERIC(12,4) NOT NULL,
    exit_price          NUMERIC(12,4) NOT NULL,
    entry_time          TIMESTAMPTZ,
    exit_time           TIMESTAMPTZ,

    pnl_pct             NUMERIC(10,6),
    is_winner           BOOLEAN GENERATED ALWAYS AS (pnl_pct > 0) STORED,
    confidence          INTEGER CHECK (confidence BETWEEN 0 AND 100),
    horizon             VARCHAR(20),                   -- scalp / day / swing / position
    exit_reason         VARCHAR(50),                   -- stop_loss / target / trailing / time / manual

    -- Context at entry (for ML features)
    regime_at_entry     VARCHAR(20),
    vix_at_entry        NUMERIC(8,2),
    rsi_at_entry        NUMERIC(6,2),
    adx_at_entry        NUMERIC(6,2),
    relative_volume     NUMERIC(10,4),
    setup_grade         VARCHAR(2),
    composite_score     NUMERIC(8,4),

    hold_hours          NUMERIC(10,2),
    feature_snapshot    JSONB,

    created_at          TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_outcomes_ticker
    ON analytics.trade_outcomes (ticker, exit_time DESC);
CREATE INDEX IF NOT EXISTS idx_outcomes_strategy
    ON analytics.trade_outcomes (strategy, exit_time DESC);
CREATE INDEX IF NOT EXISTS idx_outcomes_winner
    ON analytics.trade_outcomes (is_winner, exit_time DESC);

-- ─────────────────────────────────────────────────────────────────────────────
-- 2. STRATEGY LEADERBOARD (rolling performance per strategy)
-- ─────────────────────────────────────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS analytics.strategy_leaderboard (
    id                  UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    snapshot_date       DATE NOT NULL,
    strategy_id         VARCHAR(50) NOT NULL,

    total_trades        INTEGER DEFAULT 0,
    wins                INTEGER DEFAULT 0,
    losses              INTEGER DEFAULT 0,
    win_rate            NUMERIC(6,4),
    avg_pnl_pct         NUMERIC(10,6),
    total_pnl_pct       NUMERIC(10,6),
    profit_factor       NUMERIC(8,4),
    avg_hold_hours      NUMERIC(10,2),
    sharpe_estimate     NUMERIC(8,4),

    elo_rating          NUMERIC(8,2) DEFAULT 1500,
    rank                INTEGER,

    created_at          TIMESTAMPTZ DEFAULT NOW(),
    UNIQUE (snapshot_date, strategy_id)
);

CREATE INDEX IF NOT EXISTS idx_leaderboard_date
    ON analytics.strategy_leaderboard (snapshot_date DESC);

-- ─────────────────────────────────────────────────────────────────────────────
-- 3. REGIME SNAPSHOTS (regime classification over time)
-- ─────────────────────────────────────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS analytics.regime_snapshots (
    id                  UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    snapshot_time       TIMESTAMPTZ NOT NULL,

    risk_regime         VARCHAR(20),                   -- RISK_ON / RISK_OFF / NEUTRAL
    trend_regime        VARCHAR(20),                   -- STRONG_UPTREND / UPTREND / ...
    volatility_regime   VARCHAR(20),                   -- LOW_VOL / NORMAL / HIGH_VOL / CRISIS
    composite_regime    VARCHAR(30),                   -- combined label

    should_trade        BOOLEAN DEFAULT TRUE,
    entropy             NUMERIC(8,4),
    vix_level           NUMERIC(8,2),
    pct_above_sma50     NUMERIC(6,2),

    context_snapshot    JSONB,

    created_at          TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_regime_time
    ON analytics.regime_snapshots (snapshot_time DESC);

-- ─────────────────────────────────────────────────────────────────────────────
-- 4. ENGINE HEALTH LOG (periodic health snapshots for monitoring)
-- ─────────────────────────────────────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS system.engine_health_log (
    id                  UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    check_time          TIMESTAMPTZ NOT NULL DEFAULT NOW(),

    status              VARCHAR(20) NOT NULL,          -- healthy / degraded / unhealthy
    cycle_count         INTEGER,
    signals_today       INTEGER,
    trades_today        INTEGER,

    circuit_breaker_on  BOOLEAN DEFAULT FALSE,
    circuit_breaker_reason VARCHAR(200),

    components          JSONB,                         -- {regime_router: true, ...}
    phase_latencies_ms  JSONB,                         -- {context: 12, regime: 5, ...}

    created_at          TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_health_time
    ON system.engine_health_log (check_time DESC);

-- ─────────────────────────────────────────────────────────────────────────────
-- 5. CONTINUOUS AGGREGATE: daily strategy performance (materialised view)
-- ─────────────────────────────────────────────────────────────────────────────
-- Note: This is a standard view; upgrade to TimescaleDB continuous aggregate
-- if TimescaleDB is available.
CREATE OR REPLACE VIEW analytics.v_daily_strategy_performance AS
SELECT
    DATE(exit_time)             AS trade_date,
    strategy                    AS strategy_id,
    COUNT(*)                    AS total_trades,
    COUNT(*) FILTER (WHERE pnl_pct > 0) AS wins,
    COUNT(*) FILTER (WHERE pnl_pct <= 0) AS losses,
    ROUND(AVG(pnl_pct)::numeric, 6)     AS avg_pnl_pct,
    ROUND(SUM(pnl_pct)::numeric, 6)     AS total_pnl_pct,
    ROUND(AVG(hold_hours)::numeric, 2)   AS avg_hold_hours
FROM analytics.trade_outcomes
WHERE exit_time IS NOT NULL
GROUP BY DATE(exit_time), strategy;

COMMIT;
