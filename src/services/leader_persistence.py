"""
Leader / Holdings Tracking — SQLite persistence (Phase 1+).

Stores leaders, holdings, events, consensus aggregates, flow signals,
shadow baskets, and alerts. Verified vs inferred data is always tagged.
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
_DB_PATH = os.environ.get(
    "LEADER_DB_PATH",
    os.path.join(_DB_DIR, "leader_tracking.db"),
)


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _get_db(db_path: str | None = None) -> sqlite3.Connection:
    path = db_path or _DB_PATH
    os.makedirs(os.path.dirname(path), exist_ok=True)
    conn = sqlite3.connect(path, check_same_thread=False)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL")
    _init_tables(conn)
    return conn


def _init_tables(conn: sqlite3.Connection) -> None:
    conn.executescript("""
        CREATE TABLE IF NOT EXISTS leaders (
            id TEXT PRIMARY KEY,
            name TEXT NOT NULL,
            slug TEXT NOT NULL UNIQUE,
            category TEXT NOT NULL,
            entity_type TEXT NOT NULL,
            description TEXT,
            focus_area TEXT,
            source_type TEXT NOT NULL,
            source_quality TEXT NOT NULL,
            disclosure_delay_days INTEGER DEFAULT 0,
            region TEXT,
            active INTEGER DEFAULT 1,
            created_at TEXT NOT NULL,
            updated_at TEXT NOT NULL
        );

        CREATE TABLE IF NOT EXISTS leader_sources (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            leader_id TEXT NOT NULL,
            source_name TEXT NOT NULL,
            source_type TEXT NOT NULL,
            source_url TEXT,
            source_quality TEXT NOT NULL,
            parser_type TEXT,
            last_checked_at TEXT,
            active INTEGER DEFAULT 1,
            FOREIGN KEY (leader_id) REFERENCES leaders(id)
        );

        CREATE TABLE IF NOT EXISTS leader_holdings (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            leader_id TEXT NOT NULL,
            ticker TEXT NOT NULL,
            security_name TEXT,
            action_type TEXT NOT NULL,
            size_bucket TEXT,
            weight_estimate REAL,
            source_name TEXT,
            source_quality TEXT NOT NULL,
            disclosure_date TEXT,
            effective_date TEXT,
            first_seen_at TEXT NOT NULL,
            last_seen_at TEXT NOT NULL,
            sector TEXT,
            theme TEXT,
            verified_flag INTEGER DEFAULT 0,
            inferred_flag INTEGER DEFAULT 0,
            price_since_disclosure REAL,
            setup_quality TEXT,
            actionability TEXT,
            notes TEXT,
            FOREIGN KEY (leader_id) REFERENCES leaders(id)
        );
        CREATE INDEX IF NOT EXISTS idx_lh_leader ON leader_holdings(leader_id);
        CREATE INDEX IF NOT EXISTS idx_lh_ticker ON leader_holdings(ticker);

        CREATE TABLE IF NOT EXISTS leader_events (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            leader_id TEXT NOT NULL,
            ticker TEXT,
            event_type TEXT NOT NULL,
            event_date TEXT NOT NULL,
            disclosure_date TEXT,
            summary TEXT NOT NULL,
            source_name TEXT,
            source_quality TEXT NOT NULL,
            context_tag TEXT,
            size_bucket TEXT,
            created_at TEXT NOT NULL,
            FOREIGN KEY (leader_id) REFERENCES leaders(id)
        );
        CREATE INDEX IF NOT EXISTS idx_le_leader ON leader_events(leader_id, event_date);

        CREATE TABLE IF NOT EXISTS ticker_consensus (
            ticker TEXT PRIMARY KEY,
            mention_count INTEGER DEFAULT 0,
            verified_count INTEGER DEFAULT 0,
            inferred_count INTEGER DEFAULT 0,
            add_count INTEGER DEFAULT 0,
            reduce_count INTEGER DEFAULT 0,
            exit_count INTEGER DEFAULT 0,
            new_buy_count INTEGER DEFAULT 0,
            consensus_score REAL DEFAULT 0,
            flow_confirmation_score REAL DEFAULT 0,
            last_updated TEXT NOT NULL
        );

        CREATE TABLE IF NOT EXISTS ticker_flow_signals (
            ticker TEXT PRIMARY KEY,
            leaps_oi_change REAL,
            far_dated_flow_score REAL,
            iv_term_change REAL,
            unusual_flow_score REAL,
            spot_confirmation_score REAL,
            final_confirmation_score REAL,
            data_mode TEXT DEFAULT 'heuristic',
            updated_at TEXT NOT NULL
        );

        CREATE TABLE IF NOT EXISTS shadow_baskets (
            id TEXT PRIMARY KEY,
            name TEXT NOT NULL,
            basket_type TEXT NOT NULL,
            methodology TEXT,
            rebalance_rule TEXT,
            benchmark TEXT DEFAULT 'SPY',
            active INTEGER DEFAULT 1,
            created_at TEXT NOT NULL,
            updated_at TEXT NOT NULL
        );

        CREATE TABLE IF NOT EXISTS shadow_basket_members (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            basket_id TEXT NOT NULL,
            ticker TEXT NOT NULL,
            weight REAL NOT NULL,
            source_basis TEXT,
            start_date TEXT,
            end_date TEXT,
            active INTEGER DEFAULT 1,
            FOREIGN KEY (basket_id) REFERENCES shadow_baskets(id)
        );

        CREATE TABLE IF NOT EXISTS leader_alerts (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            alert_type TEXT NOT NULL,
            related_entity_type TEXT,
            related_entity_id TEXT,
            ticker TEXT,
            severity TEXT NOT NULL,
            message TEXT NOT NULL,
            seen INTEGER DEFAULT 0,
            created_at TEXT NOT NULL
        );

        CREATE TABLE IF NOT EXISTS meta (
            key TEXT PRIMARY KEY,
            value TEXT NOT NULL
        );
        """)
    conn.commit()


def _row_to_dict(row: sqlite3.Row | None) -> Optional[Dict[str, Any]]:
    if row is None:
        return None
    return dict(row)


def get_meta(key: str, db_path: str | None = None) -> Optional[str]:
    conn = _get_db(db_path)
    try:
        cur = conn.execute("SELECT value FROM meta WHERE key = ?", (key,))
        r = cur.fetchone()
        return r["value"] if r else None
    finally:
        conn.close()


def set_meta(key: str, value: str, db_path: str | None = None) -> None:
    conn = _get_db(db_path)
    try:
        conn.execute(
            "INSERT OR REPLACE INTO meta (key, value) VALUES (?, ?)",
            (key, value),
        )
        conn.commit()
    finally:
        conn.close()


def upsert_leader(leader: Dict[str, Any], db_path: str | None = None) -> None:
    conn = _get_db(db_path)
    try:
        conn.execute(
            """
            INSERT OR REPLACE INTO leaders (
                id, name, slug, category, entity_type, description, focus_area,
                source_type, source_quality, disclosure_delay_days, region,
                active, created_at, updated_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                leader["id"],
                leader["name"],
                leader["slug"],
                leader["category"],
                leader["entity_type"],
                leader.get("description"),
                leader.get("focus_area"),
                leader["source_type"],
                leader["source_quality"],
                leader.get("disclosure_delay_days", 0),
                leader.get("region"),
                1 if leader.get("active", True) else 0,
                leader.get("created_at", _now()),
                _now(),
            ),
        )
        conn.commit()
    finally:
        conn.close()


def list_leaders(
    category: Optional[str] = None,
    source_quality: Optional[str] = None,
    search: Optional[str] = None,
    db_path: str | None = None,
) -> List[Dict[str, Any]]:
    conn = _get_db(db_path)
    try:
        q = "SELECT * FROM leaders WHERE active = 1"
        params: List[Any] = []
        if category:
            q += " AND category = ?"
            params.append(category)
        if source_quality:
            q += " AND source_quality = ?"
            params.append(source_quality)
        if search:
            q += " AND (name LIKE ? OR focus_area LIKE ?)"
            params.extend([f"%{search}%", f"%{search}%"])
        q += " ORDER BY updated_at DESC"
        rows = conn.execute(q, params).fetchall()
        return [_row_to_dict(r) for r in rows if r]
    finally:
        conn.close()


def get_leader(leader_id: str, db_path: str | None = None) -> Optional[Dict[str, Any]]:
    conn = _get_db(db_path)
    try:
        row = conn.execute(
            "SELECT * FROM leaders WHERE id = ?", (leader_id,),
        ).fetchone()
        return _row_to_dict(row)
    finally:
        conn.close()


def get_holdings(
    leader_id: str,
    action_type: Optional[str] = None,
    db_path: str | None = None,
) -> List[Dict[str, Any]]:
    conn = _get_db(db_path)
    try:
        q = "SELECT * FROM leader_holdings WHERE leader_id = ?"
        params: List[Any] = [leader_id]
        if action_type:
            q += " AND action_type = ?"
            params.append(action_type)
        q += " ORDER BY last_seen_at DESC"
        rows = conn.execute(q, params).fetchall()
        return [_row_to_dict(r) for r in rows if r]
    finally:
        conn.close()


def get_events(leader_id: str, db_path: str | None = None) -> List[Dict[str, Any]]:
    conn = _get_db(db_path)
    try:
        rows = conn.execute(
            """
            SELECT * FROM leader_events
            WHERE leader_id = ?
            ORDER BY event_date DESC, id DESC
            """,
            (leader_id,),
        ).fetchall()
        return [_row_to_dict(r) for r in rows if r]
    finally:
        conn.close()


def insert_holding(h: Dict[str, Any], db_path: str | None = None) -> None:
    conn = _get_db(db_path)
    try:
        conn.execute(
            """
            INSERT INTO leader_holdings (
                leader_id, ticker, security_name, action_type, size_bucket,
                weight_estimate, source_name, source_quality, disclosure_date,
                effective_date, first_seen_at, last_seen_at, sector, theme,
                verified_flag, inferred_flag, price_since_disclosure,
                setup_quality, actionability, notes
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                h["leader_id"], h["ticker"], h.get("security_name"),
                h["action_type"], h.get("size_bucket"), h.get("weight_estimate"),
                h.get("source_name"), h["source_quality"],
                h.get("disclosure_date"), h.get("effective_date"),
                h.get("first_seen_at", _now()), h.get("last_seen_at", _now()),
                h.get("sector"), h.get("theme"),
                1 if h.get("verified_flag") else 0,
                1 if h.get("inferred_flag") else 0,
                h.get("price_since_disclosure"), h.get("setup_quality"),
                h.get("actionability"), h.get("notes"),
            ),
        )
        conn.commit()
    finally:
        conn.close()


def insert_event(e: Dict[str, Any], db_path: str | None = None) -> None:
    conn = _get_db(db_path)
    try:
        conn.execute(
            """
            INSERT INTO leader_events (
                leader_id, ticker, event_type, event_date, disclosure_date,
                summary, source_name, source_quality, context_tag, size_bucket,
                created_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                e["leader_id"], e.get("ticker"), e["event_type"], e["event_date"],
                e.get("disclosure_date"), e["summary"], e.get("source_name"),
                e["source_quality"], e.get("context_tag"), e.get("size_bucket"),
                _now(),
            ),
        )
        conn.commit()
    finally:
        conn.close()


def upsert_consensus(row: Dict[str, Any], db_path: str | None = None) -> None:
    conn = _get_db(db_path)
    try:
        conn.execute(
            """
            INSERT OR REPLACE INTO ticker_consensus (
                ticker, mention_count, verified_count, inferred_count,
                add_count, reduce_count, exit_count, new_buy_count,
                consensus_score, flow_confirmation_score, last_updated
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                row["ticker"], row.get("mention_count", 0),
                row.get("verified_count", 0), row.get("inferred_count", 0),
                row.get("add_count", 0), row.get("reduce_count", 0),
                row.get("exit_count", 0), row.get("new_buy_count", 0),
                row.get("consensus_score", 0),
                row.get("flow_confirmation_score", 0), _now(),
            ),
        )
        conn.commit()
    finally:
        conn.close()


def list_consensus(
    verified_only: bool = False,
    min_overlap: int = 1,
    db_path: str | None = None,
) -> List[Dict[str, Any]]:
    conn = _get_db(db_path)
    try:
        q = """
            SELECT * FROM ticker_consensus
            WHERE mention_count >= ?
        """
        params: List[Any] = [min_overlap]
        if verified_only:
            q += " AND verified_count > 0 AND inferred_count = 0"
        q += " ORDER BY consensus_score DESC"
        rows = conn.execute(q, params).fetchall()
        return [_row_to_dict(r) for r in rows if r]
    finally:
        conn.close()


def upsert_flow_signal(row: Dict[str, Any], db_path: str | None = None) -> None:
    conn = _get_db(db_path)
    try:
        conn.execute(
            """
            INSERT OR REPLACE INTO ticker_flow_signals (
                ticker, leaps_oi_change, far_dated_flow_score,
                iv_term_change, unusual_flow_score, spot_confirmation_score,
                final_confirmation_score, data_mode, updated_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                row["ticker"], row.get("leaps_oi_change"),
                row.get("far_dated_flow_score"), row.get("iv_term_change"),
                row.get("unusual_flow_score"), row.get("spot_confirmation_score"),
                row.get("final_confirmation_score", 0),
                row.get("data_mode", "heuristic"), _now(),
            ),
        )
        conn.commit()
    finally:
        conn.close()


def list_flow_signals(db_path: str | None = None) -> List[Dict[str, Any]]:
    conn = _get_db(db_path)
    try:
        rows = conn.execute(
            "SELECT * FROM ticker_flow_signals ORDER BY final_confirmation_score DESC",
        ).fetchall()
        return [_row_to_dict(r) for r in rows if r]
    finally:
        conn.close()


def get_flow_signal(ticker: str, db_path: str | None = None) -> Optional[Dict[str, Any]]:
    conn = _get_db(db_path)
    try:
        row = conn.execute(
            "SELECT * FROM ticker_flow_signals WHERE ticker = ?",
            (ticker.upper(),),
        ).fetchone()
        return _row_to_dict(row)
    finally:
        conn.close()


def list_baskets(db_path: str | None = None) -> List[Dict[str, Any]]:
    conn = _get_db(db_path)
    try:
        rows = conn.execute(
            "SELECT * FROM shadow_baskets WHERE active = 1 ORDER BY name",
        ).fetchall()
        return [_row_to_dict(r) for r in rows if r]
    finally:
        conn.close()


def get_basket(basket_id: str, db_path: str | None = None) -> Optional[Dict[str, Any]]:
    conn = _get_db(db_path)
    try:
        b = conn.execute(
            "SELECT * FROM shadow_baskets WHERE id = ?", (basket_id,),
        ).fetchone()
        if not b:
            return None
        out = _row_to_dict(b)
        members = conn.execute(
            """
            SELECT * FROM shadow_basket_members
            WHERE basket_id = ? AND active = 1
            ORDER BY weight DESC
            """,
            (basket_id,),
        ).fetchall()
        out["members"] = [_row_to_dict(m) for m in members if m]
        return out
    finally:
        conn.close()


def upsert_basket(b: Dict[str, Any], db_path: str | None = None) -> None:
    conn = _get_db(db_path)
    try:
        conn.execute(
            """
            INSERT OR REPLACE INTO shadow_baskets (
                id, name, basket_type, methodology, rebalance_rule,
                benchmark, active, created_at, updated_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                b["id"], b["name"], b["basket_type"], b.get("methodology"),
                b.get("rebalance_rule"), b.get("benchmark", "SPY"),
                1 if b.get("active", True) else 0,
                b.get("created_at", _now()), _now(),
            ),
        )
        conn.commit()
    finally:
        conn.close()


def insert_basket_member(m: Dict[str, Any], db_path: str | None = None) -> None:
    conn = _get_db(db_path)
    try:
        conn.execute(
            """
            INSERT INTO shadow_basket_members (
                basket_id, ticker, weight, source_basis, start_date, active
            ) VALUES (?, ?, ?, ?, ?, 1)
            """,
            (
                m["basket_id"], m["ticker"], m["weight"],
                m.get("source_basis"), m.get("start_date", _now()[:10]),
            ),
        )
        conn.commit()
    finally:
        conn.close()


def list_alerts(unseen_only: bool = True, db_path: str | None = None) -> List[Dict[str, Any]]:
    conn = _get_db(db_path)
    try:
        q = "SELECT * FROM leader_alerts"
        if unseen_only:
            q += " WHERE seen = 0"
        q += " ORDER BY created_at DESC LIMIT 50"
        rows = conn.execute(q).fetchall()
        return [_row_to_dict(r) for r in rows if r]
    finally:
        conn.close()


def insert_alert(a: Dict[str, Any], db_path: str | None = None) -> None:
    conn = _get_db(db_path)
    try:
        conn.execute(
            """
            INSERT INTO leader_alerts (
                alert_type, related_entity_type, related_entity_id,
                ticker, severity, message, seen, created_at
            ) VALUES (?, ?, ?, ?, ?, ?, 0, ?)
            """,
            (
                a["alert_type"], a.get("related_entity_type"),
                a.get("related_entity_id"), a.get("ticker"),
                a["severity"], a["message"], _now(),
            ),
        )
        conn.commit()
    finally:
        conn.close()


def clear_demo_data(db_path: str | None = None) -> None:
    conn = _get_db(db_path)
    try:
        for table in (
            "leader_alerts", "shadow_basket_members", "shadow_baskets",
            "ticker_flow_signals", "ticker_consensus", "leader_events",
            "leader_holdings", "leader_sources", "leaders",
        ):
            conn.execute(f"DELETE FROM {table}")
        conn.commit()
    finally:
        conn.close()
