"""
Fund Persistence — Sprint 92
=============================
SQLite store for:
  - fund_holdings   : current snapshot per fund per day
  - fund_trades     : trade log (buy/sell/rebalance)
  - fund_performance: daily NAV metrics
  - engine_state    : CalibrationEngine _stats + peak_equity (key/value JSON)

Pattern mirrors decision_tracker.py — WAL SQLite, _get_db(), _init_tables().
"""

from __future__ import annotations

import json
import logging
import os
import sqlite3
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)

_DB_DIR = os.path.join(os.path.dirname(__file__), "..", "..", "data")
_DB_PATH = os.path.join(_DB_DIR, "fund_state.db")


def _get_db(db_path: str | None = None) -> sqlite3.Connection:
    path = db_path or _DB_PATH
    os.makedirs(os.path.dirname(path), exist_ok=True)
    conn = sqlite3.connect(path, check_same_thread=False)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA wal_autocheckpoint=1000")
    conn.execute("PRAGMA synchronous=NORMAL")
    _init_tables(conn)
    return conn


def _init_tables(conn: sqlite3.Connection) -> None:
    conn.executescript("""
        CREATE TABLE IF NOT EXISTS fund_holdings (
            id          INTEGER PRIMARY KEY AUTOINCREMENT,
            fund_id     TEXT NOT NULL,
            ticker      TEXT NOT NULL,
            weight      REAL,
            entry_score REAL,
            action_state TEXT,
            regime_at_entry TEXT,
            recorded_at TEXT NOT NULL,
            date_key    TEXT NOT NULL,
            UNIQUE(fund_id, ticker, date_key)
        );
        CREATE INDEX IF NOT EXISTS idx_fh_fund_date
            ON fund_holdings(fund_id, date_key);

        CREATE TABLE IF NOT EXISTS fund_trades (
            id            INTEGER PRIMARY KEY AUTOINCREMENT,
            fund_id       TEXT NOT NULL,
            ticker        TEXT NOT NULL,
            action        TEXT NOT NULL,
            weight_before REAL,
            weight_after  REAL,
            reason        TEXT,
            regime        TEXT,
            recorded_at   TEXT NOT NULL
        );
        CREATE INDEX IF NOT EXISTS idx_ft_fund
            ON fund_trades(fund_id, recorded_at);

        CREATE TABLE IF NOT EXISTS fund_performance (
            id                INTEGER PRIMARY KEY AUTOINCREMENT,
            fund_id           TEXT NOT NULL,
            date_key          TEXT NOT NULL,
            total_return_pct  REAL,
            annualized_pct    REAL,
            sharpe            REAL,
            max_drawdown_pct  REAL,
            excess_return_pct REAL,
            benchmark         TEXT,
            UNIQUE(fund_id, date_key)
        );
        CREATE INDEX IF NOT EXISTS idx_fp_fund_date
            ON fund_performance(fund_id, date_key);

        CREATE TABLE IF NOT EXISTS engine_state (
            key         TEXT PRIMARY KEY,
            value_json  TEXT NOT NULL,
            updated_at  TEXT NOT NULL
        );
        """)
    conn.commit()


# ── Engine-state helpers (CalibrationEngine + peak_equity) ───────────────────


def save_engine_state(key: str, value: Any, db_path: str | None = None) -> None:
    """Upsert a JSON-serialisable value under `key` in engine_state."""
    conn = _get_db(db_path)
    now = datetime.now(timezone.utc).isoformat()
    try:
        conn.execute(
            """
            INSERT INTO engine_state(key, value_json, updated_at)
            VALUES (?, ?, ?)
            ON CONFLICT(key) DO UPDATE SET
                value_json = excluded.value_json,
                updated_at = excluded.updated_at
            """,
            (key, json.dumps(value, default=str), now),
        )
        conn.commit()
    except Exception as e:
        logger.warning("fund_persistence.save_engine_state failed: %s", e)


def load_engine_state(key: str, db_path: str | None = None) -> Optional[Any]:
    """Return the parsed JSON value for `key`, or None if not found."""
    try:
        conn = _get_db(db_path)
        row = conn.execute(
            "SELECT value_json FROM engine_state WHERE key = ?", (key,)
        ).fetchone()
        if row:
            return json.loads(row["value_json"])
    except Exception as e:
        logger.warning("fund_persistence.load_engine_state failed: %s", e)
    return None


# ── Holdings ─────────────────────────────────────────────────────────────────


def upsert_holdings(
    fund_id: str,
    picks: List[Dict[str, Any]],
    regime: str = "unknown",
    db_path: str | None = None,
) -> None:
    """Write today's holdings snapshot for a fund (upserts by fund+ticker+date)."""
    conn = _get_db(db_path)
    date_key = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    now = datetime.now(timezone.utc).isoformat()
    for pick in picks:
        ticker = pick.get("ticker", "")
        if not ticker:
            continue
        try:
            conn.execute(
                """
                INSERT INTO fund_holdings
                    (fund_id, ticker, weight, entry_score, action_state,
                     regime_at_entry, recorded_at, date_key)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(fund_id, ticker, date_key) DO UPDATE SET
                    weight       = excluded.weight,
                    entry_score  = excluded.entry_score,
                    action_state = excluded.action_state,
                    recorded_at  = excluded.recorded_at
                """,
                (
                    fund_id,
                    ticker,
                    pick.get("weight"),
                    pick.get("score"),
                    pick.get("action_state"),
                    regime,
                    now,
                    date_key,
                ),
            )
        except Exception as e:
            logger.warning("upsert_holdings error for %s/%s: %s", fund_id, ticker, e)
    conn.commit()


def get_holdings(
    fund_id: str, date_key: Optional[str] = None, db_path: str | None = None
) -> List[Dict[str, Any]]:
    """Return holdings for a fund on a given date (defaults to today)."""
    conn = _get_db(db_path)
    dk = date_key or datetime.now(timezone.utc).strftime("%Y-%m-%d")
    rows = conn.execute(
        "SELECT * FROM fund_holdings WHERE fund_id=? AND date_key=? ORDER BY weight DESC",
        (fund_id, dk),
    ).fetchall()
    return [dict(r) for r in rows]


# ── Trade log ─────────────────────────────────────────────────────────────────


def log_trade(
    fund_id: str,
    ticker: str,
    action: str,
    weight_before: float = 0.0,
    weight_after: float = 0.0,
    reason: str = "",
    regime: str = "unknown",
    db_path: str | None = None,
) -> None:
    conn = _get_db(db_path)
    now = datetime.now(timezone.utc).isoformat()
    try:
        conn.execute(
            """
            INSERT INTO fund_trades
                (fund_id, ticker, action, weight_before, weight_after,
                 reason, regime, recorded_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (fund_id, ticker, action, weight_before, weight_after, reason, regime, now),
        )
        conn.commit()
    except Exception as e:
        logger.warning("log_trade error: %s", e)


def get_trade_log(
    fund_id: str, limit: int = 50, db_path: str | None = None
) -> List[Dict[str, Any]]:
    conn = _get_db(db_path)
    rows = conn.execute(
        "SELECT * FROM fund_trades WHERE fund_id=? ORDER BY recorded_at DESC LIMIT ?",
        (fund_id, limit),
    ).fetchall()
    return [dict(r) for r in rows]


# ── Performance history ───────────────────────────────────────────────────────


def upsert_performance(
    fund_id: str,
    metrics: Dict[str, Any],
    benchmark: str = "SPY",
    db_path: str | None = None,
) -> None:
    conn = _get_db(db_path)
    date_key = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    try:
        conn.execute(
            """
            INSERT INTO fund_performance
                (fund_id, date_key, total_return_pct, annualized_pct, sharpe,
                 max_drawdown_pct, excess_return_pct, benchmark)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(fund_id, date_key) DO UPDATE SET
                total_return_pct  = excluded.total_return_pct,
                annualized_pct    = excluded.annualized_pct,
                sharpe            = excluded.sharpe,
                max_drawdown_pct  = excluded.max_drawdown_pct,
                excess_return_pct = excluded.excess_return_pct
            """,
            (
                fund_id,
                date_key,
                metrics.get("total_return"),
                metrics.get("annualized"),
                metrics.get("sharpe"),
                metrics.get("max_drawdown"),
                metrics.get("excess_return"),
                benchmark,
            ),
        )
        conn.commit()
    except Exception as e:
        logger.warning("upsert_performance error for %s: %s", fund_id, e)


def get_performance_history(
    fund_id: str, days: int = 30, db_path: str | None = None
) -> List[Dict[str, Any]]:
    conn = _get_db(db_path)
    rows = conn.execute(
        """
        SELECT * FROM fund_performance
        WHERE fund_id=?
        ORDER BY date_key DESC LIMIT ?
        """,
        (fund_id, days),
    ).fetchall()
    return [dict(r) for r in rows]
