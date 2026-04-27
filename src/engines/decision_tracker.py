"""
Persistent Decision Tracker — Sprint 63
=========================================
SQLite-backed decision tracking for:
  1. Decision diff view (what changed since yesterday)
  2. Persistent alert dedup (survives restarts)
  3. Regime change detection

Storage: data/decision_tracker.db
"""

from __future__ import annotations

import json
import logging
import os
import sqlite3
from datetime import date, datetime
from typing import Optional

logger = logging.getLogger(__name__)

_DB_DIR = os.path.join(os.path.dirname(__file__), "..", "..", "data")
_DB_PATH = os.path.join(_DB_DIR, "decision_tracker.db")


def _get_db(db_path: str | None = None) -> sqlite3.Connection:
    path = db_path or _DB_PATH
    os.makedirs(os.path.dirname(path), exist_ok=True)
    conn = sqlite3.connect(path)
    conn.execute("PRAGMA journal_mode=WAL")
    _init_tables(conn)
    return conn


def _init_tables(conn: sqlite3.Connection) -> None:
    conn.executescript(
        """
        CREATE TABLE IF NOT EXISTS decisions (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            ticker TEXT NOT NULL,
            action TEXT NOT NULL,
            score REAL,
            grade TEXT,
            confidence REAL,
            rationale TEXT,
            entry_trigger TEXT,
            stop_price REAL,
            target_price REAL,
            regime TEXT,
            recorded_at TEXT NOT NULL,
            date_key TEXT NOT NULL
        );
        CREATE INDEX IF NOT EXISTS idx_dt_ticker_date
            ON decisions(ticker, date_key);
        CREATE INDEX IF NOT EXISTS idx_dt_date
            ON decisions(date_key);

        CREATE TABLE IF NOT EXISTS alert_dedup (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            ticker TEXT NOT NULL,
            action TEXT NOT NULL,
            date_key TEXT NOT NULL,
            sent_at TEXT NOT NULL,
            UNIQUE(ticker, action, date_key)
        );

        CREATE TABLE IF NOT EXISTS regime_history (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            trend TEXT NOT NULL,
            risk_score REAL,
            vix_level REAL,
            signals_json TEXT,
            recorded_at TEXT NOT NULL
        );
    """
    )
    conn.commit()


class DecisionTracker:
    """
    Persistent decision tracking with diff and dedup.

    Usage:
        tracker = DecisionTracker()
        tracker.record("NVDA", "TRADE", score=8.5, grade="A")
        diffs = tracker.get_diffs()
        is_dup = tracker.check_dedup("NVDA", "TRADE")
    """

    def __init__(self, db_path: str | None = None):
        self._db_path = db_path
        self._conn: sqlite3.Connection | None = None

    @property
    def conn(self) -> sqlite3.Connection:
        if self._conn is None:
            self._conn = _get_db(self._db_path)
        return self._conn

    def record(
        self,
        ticker: str,
        action: str,
        score: float = 0.0,
        grade: str = "",
        confidence: float = 0.0,
        rationale: str = "",
        entry_trigger: str = "",
        stop_price: float = 0.0,
        target_price: float = 0.0,
        regime: str = "",
    ) -> None:
        """Record a decision for today."""
        now = datetime.now()
        self.conn.execute(
            """INSERT INTO decisions
               (ticker, action, score, grade, confidence, rationale,
                entry_trigger, stop_price, target_price, regime,
                recorded_at, date_key)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (
                ticker,
                action,
                score,
                grade,
                confidence,
                rationale,
                entry_trigger,
                stop_price,
                target_price,
                regime,
                now.isoformat(),
                now.strftime("%Y-%m-%d"),
            ),
        )
        self.conn.commit()

    def record_from_decision(
        self, ticker: str, decision_dict: dict, regime: str = ""
    ) -> None:
        """Record from a Decision.to_dict() output."""
        self.record(
            ticker=ticker,
            action=decision_dict.get("action", ""),
            score=decision_dict.get("score", 0),
            grade=decision_dict.get("grade", ""),
            confidence=decision_dict.get("confidence", 0),
            rationale=decision_dict.get("rationale", ""),
            entry_trigger=decision_dict.get("entry_trigger", ""),
            stop_price=decision_dict.get("stop_price", 0),
            target_price=decision_dict.get("target_price", 0),
            regime=regime,
        )

    # ── Decision Diff ──

    def get_diffs(
        self,
        today: str | None = None,
        yesterday: str | None = None,
    ) -> list[dict]:
        """
        Compare today's decisions vs previous day.
        Returns upgrades, downgrades, new entries, removals.
        """
        if not today:
            today = date.today().strftime("%Y-%m-%d")
        if not yesterday:
            row = self.conn.execute(
                "SELECT DISTINCT date_key FROM decisions "
                "WHERE date_key < ? ORDER BY date_key DESC LIMIT 1",
                (today,),
            ).fetchone()
            if not row:
                return []
            yesterday = row[0]

        today_map = self._latest_by_ticker(today)
        yesterday_map = self._latest_by_ticker(yesterday)
        diffs = []
        all_tickers = set(list(today_map.keys()) + list(yesterday_map.keys()))

        _RANK = {"TRADE": 4, "WATCH": 3, "WAIT": 2, "NO_TRADE": 1}

        for ticker in sorted(all_tickers):
            t = today_map.get(ticker)
            y = yesterday_map.get(ticker)

            if t and not y:
                diffs.append(
                    {
                        "ticker": ticker,
                        "change": "NEW",
                        "action": t["action"],
                        "score": t["score"],
                        "detail": f"New: {t['action']} ({t['grade']})",
                    }
                )
            elif y and not t:
                diffs.append(
                    {
                        "ticker": ticker,
                        "change": "REMOVED",
                        "prev_action": y["action"],
                        "detail": f"Removed (was {y['action']})",
                    }
                )
            elif t and y and t["action"] != y["action"]:
                tr = _RANK.get(t["action"], 0)
                yr = _RANK.get(y["action"], 0)
                chg = "UPGRADE" if tr > yr else "DOWNGRADE"
                diffs.append(
                    {
                        "ticker": ticker,
                        "change": chg,
                        "from": y["action"],
                        "to": t["action"],
                        "score_delta": round(t["score"] - y["score"], 1),
                        "detail": (
                            f"{y['action']}→{t['action']} "
                            f"({y['score']:.1f}→{t['score']:.1f})"
                        ),
                    }
                )

        return diffs

    def _latest_by_ticker(self, date_key: str) -> dict:
        rows = self.conn.execute(
            "SELECT ticker, action, score, grade, confidence, rationale "
            "FROM decisions WHERE date_key = ? "
            "ORDER BY recorded_at DESC",
            (date_key,),
        ).fetchall()
        result = {}
        for r in rows:
            if r[0] not in result:
                result[r[0]] = {
                    "ticker": r[0],
                    "action": r[1],
                    "score": r[2],
                    "grade": r[3],
                    "confidence": r[4],
                    "rationale": r[5],
                }
        return result

    # ── Persistent Dedup ──

    def check_dedup(self, ticker: str, action: str) -> bool:
        """
        Returns True if already sent today (duplicate).
        Registers if new.
        """
        today = date.today().strftime("%Y-%m-%d")
        try:
            self.conn.execute(
                "INSERT INTO alert_dedup (ticker, action, date_key, sent_at) "
                "VALUES (?, ?, ?, ?)",
                (ticker, action, today, datetime.now().isoformat()),
            )
            self.conn.commit()
            return False  # Not a duplicate
        except sqlite3.IntegrityError:
            return True  # Duplicate

    def clear_old_dedup(self, before_date: str | None = None) -> int:
        if not before_date:
            before_date = date.today().strftime("%Y-%m-%d")
        cur = self.conn.execute(
            "DELETE FROM alert_dedup WHERE date_key < ?",
            (before_date,),
        )
        self.conn.commit()
        return cur.rowcount

    # ── Regime History ──

    def record_regime(
        self,
        trend: str,
        risk_score: float = 0.0,
        vix_level: float = 0.0,
        signals: list[str] | None = None,
    ) -> Optional[dict]:
        """Record regime. Returns change dict if regime shifted."""
        now = datetime.now()
        last = self.conn.execute(
            "SELECT trend, risk_score FROM regime_history " "ORDER BY id DESC LIMIT 1"
        ).fetchone()

        self.conn.execute(
            "INSERT INTO regime_history "
            "(trend, risk_score, vix_level, signals_json, recorded_at) "
            "VALUES (?, ?, ?, ?, ?)",
            (trend, risk_score, vix_level, json.dumps(signals or []), now.isoformat()),
        )
        self.conn.commit()

        if last and last[0] != trend:
            return {
                "changed": True,
                "from": last[0],
                "to": trend,
                "risk_score": risk_score,
                "vix_level": vix_level,
                "timestamp": now.isoformat(),
            }
        return None

    def get_regime_history(self, limit: int = 10) -> list[dict]:
        rows = self.conn.execute(
            "SELECT trend, risk_score, vix_level, signals_json, recorded_at "
            "FROM regime_history ORDER BY id DESC LIMIT ?",
            (limit,),
        ).fetchall()
        return [
            {
                "trend": r[0],
                "risk_score": r[1],
                "vix_level": r[2],
                "signals": json.loads(r[3]) if r[3] else [],
                "recorded_at": r[4],
            }
            for r in rows
        ]

    def close(self) -> None:
        if self._conn:
            self._conn.close()
            self._conn = None
