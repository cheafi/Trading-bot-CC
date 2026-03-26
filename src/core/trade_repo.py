"""
TradingAI Bot — Trade Outcome Repository (Sprint 11)

Database persistence layer for trade outcomes, leaderboard snapshots,
and regime snapshots.  Falls back silently to no-op when the DB is
unavailable (e.g. local dev without PostgreSQL).
"""
import logging
from datetime import date, datetime, timezone
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)


class TradeOutcomeRepository:
    """
    Persist and query trade outcomes in PostgreSQL.

    Usage:
        repo = TradeOutcomeRepository()
        await repo.save_outcome(record_dict)
        outcomes = await repo.get_recent(limit=50)
    """

    # ── INSERT templates ────────────────────────────────────
    _INSERT_OUTCOME = """
        INSERT INTO analytics.trade_outcomes
            (trade_id, ticker, direction, strategy,
             entry_price, exit_price, entry_time, exit_time,
             pnl_pct, confidence, horizon, exit_reason,
             regime_at_entry, vix_at_entry, rsi_at_entry,
             adx_at_entry, relative_volume, setup_grade,
             composite_score, hold_hours, feature_snapshot)
        VALUES
            (:trade_id, :ticker, :direction, :strategy,
             :entry_price, :exit_price, :entry_time, :exit_time,
             :pnl_pct, :confidence, :horizon, :exit_reason,
             :regime_at_entry, :vix_at_entry, :rsi_at_entry,
             :adx_at_entry, :relative_volume, :setup_grade,
             :composite_score, :hold_hours, :feature_snapshot)
        ON CONFLICT DO NOTHING
    """

    _INSERT_LEADERBOARD = """
        INSERT INTO analytics.strategy_leaderboard
            (snapshot_date, strategy_id,
             total_trades, wins, losses, win_rate,
             avg_pnl_pct, total_pnl_pct, profit_factor,
             avg_hold_hours, elo_rating, rank)
        VALUES
            (:snapshot_date, :strategy_id,
             :total_trades, :wins, :losses, :win_rate,
             :avg_pnl_pct, :total_pnl_pct, :profit_factor,
             :avg_hold_hours, :elo_rating, :rank)
        ON CONFLICT (snapshot_date, strategy_id)
        DO UPDATE SET
            total_trades = EXCLUDED.total_trades,
            wins         = EXCLUDED.wins,
            losses       = EXCLUDED.losses,
            win_rate     = EXCLUDED.win_rate,
            avg_pnl_pct  = EXCLUDED.avg_pnl_pct,
            total_pnl_pct= EXCLUDED.total_pnl_pct,
            profit_factor= EXCLUDED.profit_factor,
            elo_rating   = EXCLUDED.elo_rating,
            rank         = EXCLUDED.rank
    """

    _INSERT_REGIME = """
        INSERT INTO analytics.regime_snapshots
            (snapshot_time, risk_regime, trend_regime,
             volatility_regime, composite_regime,
             should_trade, entropy, vix_level,
             pct_above_sma50, context_snapshot)
        VALUES
            (:snapshot_time, :risk_regime, :trend_regime,
             :volatility_regime, :composite_regime,
             :should_trade, :entropy, :vix_level,
             :pct_above_sma50, :context_snapshot)
    """

    _INSERT_HEALTH = """
        INSERT INTO system.engine_health_log
            (check_time, status, cycle_count,
             signals_today, trades_today,
             circuit_breaker_on, circuit_breaker_reason,
             components, phase_latencies_ms)
        VALUES
            (:check_time, :status, :cycle_count,
             :signals_today, :trades_today,
             :circuit_breaker_on, :circuit_breaker_reason,
             :components, :phase_latencies_ms)
    """

    # ── public API ──────────────────────────────────────────

    async def save_outcome(self, record: Dict[str, Any]) -> bool:
        """Persist a single trade outcome row. Returns True on success."""
        return await self._execute(self._INSERT_OUTCOME, record)

    async def save_outcomes_batch(
        self, records: List[Dict[str, Any]]
    ) -> int:
        """Persist multiple outcomes. Returns count of rows saved."""
        saved = 0
        for rec in records:
            if await self._execute(self._INSERT_OUTCOME, rec):
                saved += 1
        return saved

    async def save_leaderboard_snapshot(
        self, rows: List[Dict[str, Any]]
    ) -> bool:
        """Persist a daily leaderboard snapshot."""
        ok = True
        for row in rows:
            if not await self._execute(self._INSERT_LEADERBOARD, row):
                ok = False
        return ok

    async def save_regime_snapshot(
        self, snapshot: Dict[str, Any]
    ) -> bool:
        """Persist a regime classification snapshot."""
        return await self._execute(self._INSERT_REGIME, snapshot)

    async def save_health_snapshot(
        self, snapshot: Dict[str, Any]
    ) -> bool:
        """Persist an engine health snapshot."""
        return await self._execute(self._INSERT_HEALTH, snapshot)

    async def get_recent_outcomes(
        self, limit: int = 100
    ) -> List[Dict[str, Any]]:
        """Fetch the most recent trade outcomes."""
        query = (
            "SELECT * FROM analytics.trade_outcomes "
            "ORDER BY created_at DESC LIMIT :limit"
        )
        return await self._fetch(query, {"limit": limit})

    async def get_strategy_stats(
        self, strategy_id: str
    ) -> Optional[Dict[str, Any]]:
        """Get aggregate stats for a single strategy."""
        query = """
            SELECT
                strategy,
                COUNT(*) AS total_trades,
                COUNT(*) FILTER (WHERE pnl_pct > 0) AS wins,
                ROUND(AVG(pnl_pct)::numeric, 4) AS avg_pnl,
                ROUND(SUM(pnl_pct)::numeric, 4) AS total_pnl,
                ROUND(AVG(hold_hours)::numeric, 1) AS avg_hold
            FROM analytics.trade_outcomes
            WHERE strategy = :strategy_id
            GROUP BY strategy
        """
        rows = await self._fetch(query, {"strategy_id": strategy_id})
        return rows[0] if rows else None

    # ── internal helpers ────────────────────────────────────

    async def _execute(
        self, sql: str, params: Dict[str, Any]
    ) -> bool:
        """Execute a write query. Returns True on success."""
        try:
            from sqlalchemy import text
            from src.core.database import get_session
            async with get_session() as session:
                await session.execute(text(sql), params)
            return True
        except Exception as e:
            logger.debug("TradeOutcomeRepository write skipped: %s", e)
            return False

    async def _fetch(
        self, sql: str, params: Dict[str, Any]
    ) -> List[Dict[str, Any]]:
        """Execute a read query. Returns list of row dicts."""
        try:
            from sqlalchemy import text
            from src.core.database import get_read_session
            async with get_read_session() as session:
                result = await session.execute(text(sql), params)
                cols = list(result.keys())
                return [dict(zip(cols, row)) for row in result.fetchall()]
        except Exception as e:
            logger.debug("TradeOutcomeRepository read skipped: %s", e)
            return []
