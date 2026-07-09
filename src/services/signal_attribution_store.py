"""
Signal Attribution Store — persistent aggregates by family/setup/regime/sector/horizon.

Backtest evidence isolated from live forward evidence. Status lifecycle:
learning → unvalidated → useful → noisy/harmful → retired.
"""

from __future__ import annotations

import json
import logging
import os
import sqlite3
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional, Tuple

logger = logging.getLogger(__name__)

_DATA_DIR = os.path.join(
    os.path.dirname(__file__), "..", "..", "data", "decision_journal"
)
_AGG_DB_PATH = os.environ.get("SIGNAL_ATTRIBUTION_DB_PATH") or os.path.join(
    _DATA_DIR, "signal_attribution.db"
)
_LIVE_EVENTS_PATH = os.environ.get("SIGNAL_ATTRIBUTION_EVENTS_PATH") or os.path.join(
    _DATA_DIR, "attribution_events.jsonl"
)

ATTRIBUTION_STATUSES = (
    "learning",
    "unvalidated",
    "useful",
    "noisy",
    "harmful",
    "retired",
)

MIN_USEFUL_SAMPLE = 20
MIN_LEARNING_THRESHOLD = 8
HARMFUL_FP_RATE = 0.45
HARMFUL_MEAN_R = -0.3
NOISY_FP_RATE = 0.35


def _ensure_dir(path: str) -> None:
    os.makedirs(os.path.dirname(path) or ".", exist_ok=True)


def _get_db(db_path: Optional[str] = None) -> sqlite3.Connection:
    path = db_path or _AGG_DB_PATH
    _ensure_dir(path)
    conn = sqlite3.connect(path, check_same_thread=False)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL")
    conn.executescript(
        """
        CREATE TABLE IF NOT EXISTS signal_aggregates (
            id              INTEGER PRIMARY KEY AUTOINCREMENT,
            family          TEXT NOT NULL,
            setup_tag       TEXT DEFAULT '',
            regime          TEXT DEFAULT '',
            sector          TEXT DEFAULT '',
            horizon         INTEGER DEFAULT 5,
            evidence_source TEXT NOT NULL DEFAULT 'live_forward',
            sample_size     INTEGER DEFAULT 0,
            forward_r_sum   REAL DEFAULT 0,
            forward_r_count INTEGER DEFAULT 0,
            win_count       INTEGER DEFAULT 0,
            loss_count      INTEGER DEFAULT 0,
            false_positive  INTEGER DEFAULT 0,
            false_negative  INTEGER DEFAULT 0,
            status          TEXT DEFAULT 'learning',
            updated_at      TEXT NOT NULL,
            UNIQUE(family, setup_tag, regime, sector, horizon, evidence_source)
        );
        CREATE INDEX IF NOT EXISTS idx_sa_family ON signal_aggregates(family);
        CREATE INDEX IF NOT EXISTS idx_sa_status ON signal_aggregates(status);
        """
    )
    return conn


def resolve_aggregate_status(
    *,
    sample_size: int,
    forward_r_mean: Optional[float] = None,
    false_positive_rate: Optional[float] = None,
    evidence_source: str = "live_forward",
    retired: bool = False,
) -> str:
    if retired:
        return "retired"
    if evidence_source == "backtest":
        return "unvalidated"
    if sample_size < MIN_LEARNING_THRESHOLD:
        return "learning"
    if false_positive_rate is not None and false_positive_rate >= HARMFUL_FP_RATE:
        if forward_r_mean is not None and forward_r_mean < HARMFUL_MEAN_R:
            return "harmful"
        return "noisy"
    if forward_r_mean is not None and forward_r_mean < HARMFUL_MEAN_R and sample_size >= MIN_USEFUL_SAMPLE:
        return "harmful"
    if false_positive_rate is not None and false_positive_rate >= NOISY_FP_RATE:
        return "noisy"
    if sample_size >= MIN_USEFUL_SAMPLE and forward_r_mean is not None and forward_r_mean > 0.2:
        return "useful"
    if sample_size >= MIN_LEARNING_THRESHOLD:
        return "unvalidated"
    return "learning"


def _aggregate_key(
    family: str,
    setup_tag: str = "",
    regime: str = "",
    sector: str = "",
    horizon: int = 5,
    evidence_source: str = "live_forward",
) -> Tuple[str, str, str, str, int, str]:
    return (
        family,
        setup_tag or "",
        regime or "",
        sector or "",
        int(horizon),
        evidence_source,
    )


class SignalAttributionStore:
    """Persistent signal family attribution aggregates."""

    def __init__(
        self,
        db_path: Optional[str] = None,
        events_path: Optional[str] = None,
    ) -> None:
        self.db_path = db_path or _AGG_DB_PATH
        self.events_path = events_path or _LIVE_EVENTS_PATH
        _ensure_dir(self.events_path)

    def _append_event(self, payload: Dict[str, Any]) -> None:
        line = json.dumps(payload, separators=(",", ":"), default=str) + "\n"
        with open(self.events_path, "a", encoding="utf-8") as f:
            f.write(line)

    def record_outcome(
        self,
        *,
        family: str,
        forward_r: Optional[float] = None,
        event_type: str = "WATCH_CANDIDATE",
        setup_tag: str = "",
        regime: str = "",
        sector: str = "",
        horizon: int = 5,
        evidence_source: str = "live_forward",
        event_id: str = "",
        ticker: str = "",
    ) -> Dict[str, Any]:
        """Increment aggregate from one forward outcome observation."""
        conn = _get_db(self.db_path)
        key = _aggregate_key(
            family, setup_tag, regime, sector, horizon, evidence_source
        )
        row = conn.execute(
            """
            SELECT * FROM signal_aggregates
            WHERE family=? AND setup_tag=? AND regime=? AND sector=?
              AND horizon=? AND evidence_source=?
            """,
            key,
        ).fetchone()

        sample = 1
        r_sum = float(forward_r or 0)
        r_count = 1 if forward_r is not None else 0
        wins = 1 if forward_r is not None and forward_r > 0 else 0
        losses = 1 if forward_r is not None and forward_r < 0 else 0
        fp = 1 if event_type == "DEPLOY_CANDIDATE" and forward_r is not None and forward_r < 0 else 0
        fn = 1 if event_type in ("WATCH_CANDIDATE", "NEAR_MISS") and forward_r is not None and forward_r > 1.0 else 0

        if row:
            sample = int(row["sample_size"]) + 1
            r_sum = float(row["forward_r_sum"]) + (float(forward_r) if forward_r is not None else 0)
            r_count = int(row["forward_r_count"]) + (1 if forward_r is not None else 0)
            wins = int(row["win_count"]) + (1 if forward_r is not None and forward_r > 0 else 0)
            losses = int(row["loss_count"]) + (1 if forward_r is not None and forward_r < 0 else 0)
            fp = int(row["false_positive"]) + fp
            fn = int(row["false_negative"]) + fn

        r_mean = round(r_sum / r_count, 3) if r_count > 0 else None
        fp_rate = round(fp / max(r_count, 1), 3) if r_count > 0 else None
        status = resolve_aggregate_status(
            sample_size=sample,
            forward_r_mean=r_mean,
            false_positive_rate=fp_rate,
            evidence_source=evidence_source,
        )

        now = datetime.now(timezone.utc).isoformat()
        conn.execute(
            """
            INSERT INTO signal_aggregates
            (family, setup_tag, regime, sector, horizon, evidence_source,
             sample_size, forward_r_sum, forward_r_count, win_count, loss_count,
             false_positive, false_negative, status, updated_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(family, setup_tag, regime, sector, horizon, evidence_source)
            DO UPDATE SET
                sample_size=excluded.sample_size,
                forward_r_sum=excluded.forward_r_sum,
                forward_r_count=excluded.forward_r_count,
                win_count=excluded.win_count,
                loss_count=excluded.loss_count,
                false_positive=excluded.false_positive,
                false_negative=excluded.false_negative,
                status=excluded.status,
                updated_at=excluded.updated_at
            """,
            (
                *key,
                sample,
                r_sum,
                r_count,
                wins,
                losses,
                fp,
                fn,
                status,
                now,
            ),
        )
        conn.commit()
        conn.close()

        event_record = {
            "record_type": "attribution_event",
            "family": family,
            "setup_tag": setup_tag,
            "regime": regime,
            "sector": sector,
            "horizon": horizon,
            "evidence_source": evidence_source,
            "forward_r": forward_r,
            "event_type": event_type,
            "event_id": event_id,
            "ticker": ticker,
            "timestamp": now,
            "authority_effect": "none",
            "may_authorize_deploy": False,
        }
        self._append_event(event_record)

        return {
            "family": family,
            "setup_tag": setup_tag,
            "regime": regime,
            "sector": sector,
            "horizon": horizon,
            "evidence_source": evidence_source,
            "sample_size": sample,
            "forward_r_mean": r_mean,
            "false_positive_rate": fp_rate,
            "status": status,
            "learning_mode": sample < MIN_USEFUL_SAMPLE,
            "may_authorize_deploy": False,
        }

    def get_family_calibration(
        self, family: str, *, evidence_source: str = "live_forward"
    ) -> Dict[str, Any]:
        conn = _get_db(self.db_path)
        rows = conn.execute(
            """
            SELECT * FROM signal_aggregates
            WHERE family=? AND evidence_source=?
            ORDER BY sample_size DESC
            """,
            (family, evidence_source),
        ).fetchall()
        conn.close()
        if not rows:
            return {
                "family": family,
                "sample_size": 0,
                "forward_r_mean": None,
                "false_positive_rate": None,
                "status": "learning",
                "evidence_source": evidence_source,
                "learning_mode": True,
            }
        total_n = sum(int(r["sample_size"]) for r in rows)
        total_r = sum(float(r["forward_r_sum"]) for r in rows)
        total_rc = sum(int(r["forward_r_count"]) for r in rows)
        total_fp = sum(int(r["false_positive"]) for r in rows)
        r_mean = round(total_r / total_rc, 3) if total_rc > 0 else None
        fp_rate = round(total_fp / max(total_rc, 1), 3) if total_rc > 0 else None
        statuses = [str(r["status"]) for r in rows]
        status = resolve_aggregate_status(
            sample_size=total_n,
            forward_r_mean=r_mean,
            false_positive_rate=fp_rate,
            evidence_source=evidence_source,
        )
        if "harmful" in statuses:
            status = "harmful"
        elif "noisy" in statuses and status == "useful":
            status = "noisy"
        return {
            "family": family,
            "sample_size": total_n,
            "forward_r_mean": r_mean,
            "false_positive_rate": fp_rate,
            "status": status,
            "evidence_source": evidence_source,
            "learning_mode": total_n < MIN_USEFUL_SAMPLE,
            "live_calibration": evidence_source == "live_forward" and total_n >= MIN_LEARNING_THRESHOLD,
        }

    def get_all_calibrations(
        self, *, evidence_source: str = "live_forward"
    ) -> Dict[str, Dict[str, Any]]:
        conn = _get_db(self.db_path)
        families = conn.execute(
            "SELECT DISTINCT family FROM signal_aggregates WHERE evidence_source=?",
            (evidence_source,),
        ).fetchall()
        conn.close()
        return {
            str(r["family"]): self.get_family_calibration(
                str(r["family"]), evidence_source=evidence_source
            )
            for r in families
        }

    def summarize(self, *, evidence_source: str = "live_forward") -> Dict[str, Any]:
        conn = _get_db(self.db_path)
        rows = conn.execute(
            "SELECT * FROM signal_aggregates WHERE evidence_source=?",
            (evidence_source,),
        ).fetchall()
        conn.close()
        useful: List[str] = []
        noisy: List[str] = []
        harmful: List[str] = []
        learning: List[str] = []
        total_n = 0
        for r in rows:
            fam = str(r["family"])
            st = str(r["status"])
            total_n += int(r["sample_size"])
            if st == "useful":
                useful.append(fam)
            elif st == "noisy":
                noisy.append(fam)
            elif st == "harmful":
                harmful.append(fam)
            elif st in ("learning", "unvalidated"):
                learning.append(fam)
        return {
            "families_tracked": len({r["family"] for r in rows}),
            "useful_families": sorted(set(useful)),
            "noisy_families": sorted(set(noisy)),
            "harmful_families": sorted(set(harmful)),
            "learning_families": sorted(set(learning)),
            "best_validated_family": useful[0] if useful else None,
            "noisy_family": noisy[0] if noisy else None,
            "harmful_family": harmful[0] if harmful else None,
            "aggregate_sample_size": total_n,
            "learning_mode": total_n < MIN_USEFUL_SAMPLE,
            "evidence_source": evidence_source,
            "may_authorize_deploy": False,
            "authority_effect": "none",
        }

    def update_from_forward_outcomes(
        self, outcomes: List[Dict[str, Any]], events_by_id: Dict[str, Dict[str, Any]]
    ) -> int:
        """Bulk update aggregates from resolved forward outcomes."""
        updated = 0
        for outcome in outcomes:
            eid = str(outcome.get("event_id") or "")
            event = events_by_id.get(eid, {})
            families = list(event.get("signal_families") or ["setup_quality"])
            for fam in families:
                self.record_outcome(
                    family=str(fam),
                    forward_r=outcome.get("forward_r"),
                    event_type=str(event.get("event_type") or outcome.get("event_type") or ""),
                    setup_tag=str(event.get("candidate_bucket") or ""),
                    regime=str((event.get("market_state") or {}).get("regime") or ""),
                    sector=str(event.get("sector") or ""),
                    horizon=int(outcome.get("horizon") or 5),
                    evidence_source="live_forward",
                    event_id=eid,
                    ticker=str(outcome.get("ticker") or event.get("ticker") or ""),
                )
                updated += 1
        return updated


def get_signal_attribution_store(
    db_path: Optional[str] = None,
) -> SignalAttributionStore:
    return SignalAttributionStore(db_path=db_path)
