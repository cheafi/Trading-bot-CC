"""
Signal tracker — persistent, research-only ledger for every generated signal.

This is the foundation for cohort intelligence, conversion-funnel analysis, and
forward-outcome (5/10/20/60d, MFE/MAE) learning. It records what was scanned and
follows each signal to its outcome over time. It NEVER authorizes deploy: every
payload it produces is capped at research_only via signal_provenance.

Persistence: append-only JSONL event log under data/artifacts/signal_ledger.jsonl.
Each line is a full state snapshot for a signal id; current state is the latest
event per id (reducer). Append-only keeps the audit trail honest — we never
silently rewrite history, we layer stage transitions and outcomes on top.

Authority: research_only / monitor_only. Cohort edge stats are evidence, not a
trade trigger. Sample size, calibration age, and live-vs-simulated are always
labeled so a thin or backtest-only cohort can never masquerade as conviction.
"""

from __future__ import annotations

import json
import os
import threading
from collections import defaultdict
from typing import Any, Dict, List, Optional

from src.services.signal_provenance import (
    SIGNAL_SIGNAL_COHORT,
    build_provenance_envelope,
)

# ---------------------------------------------------------------------------
# Funnel stages (ordered). A signal advances monotonically through these.
# ---------------------------------------------------------------------------
STAGE_SCANNED = "scanned"
STAGE_MONITOR = "monitor"
STAGE_NEAR_MISS = "near_miss"
STAGE_WATCH_QUALIFIED = "watch_qualified"
STAGE_DEPLOY_QUALIFIED = "deploy_qualified"
STAGE_EXECUTED = "executed"
STAGE_STOPPED = "stopped"
STAGE_WINNER = "winner"
STAGE_TIMING_MISS = "timing_miss"

FUNNEL_STAGES: tuple[str, ...] = (
    STAGE_SCANNED,
    STAGE_MONITOR,
    STAGE_NEAR_MISS,
    STAGE_WATCH_QUALIFIED,
    STAGE_DEPLOY_QUALIFIED,
    STAGE_EXECUTED,
    STAGE_STOPPED,
    STAGE_WINNER,
    STAGE_TIMING_MISS,
)
_STAGE_RANK = {s: i for i, s in enumerate(FUNNEL_STAGES)}

# Terminal outcome stages — once reached the signal is closed.
TERMINAL_STAGES = frozenset({STAGE_STOPPED, STAGE_WINNER, STAGE_TIMING_MISS})

DEFAULT_LEDGER_PATH = os.path.join("data", "artifacts", "signal_ledger.jsonl")

# Evidence-quality thresholds — never let a thin sample look like an edge.
_THIN_SAMPLE = 8
_MODERATE_SAMPLE = 25


def vix_bucket(vix: Optional[float]) -> str:
    """Coarse VIX regime bucket; 'unknown' when data is missing (honest)."""
    if vix is None:
        return "unknown"
    try:
        v = float(vix)
    except (TypeError, ValueError):
        return "unknown"
    if v < 15:
        return "calm"
    if v < 20:
        return "normal"
    if v < 28:
        return "elevated"
    if v < 40:
        return "high"
    return "extreme"


def rs_bucket(rs_pct: Optional[float]) -> str:
    """Relative-strength percentile bucket (0-100 input)."""
    if rs_pct is None:
        return "unknown"
    try:
        r = float(rs_pct)
    except (TypeError, ValueError):
        return "unknown"
    if r >= 90:
        return "top_decile"
    if r >= 70:
        return "strong"
    if r >= 40:
        return "neutral"
    if r >= 20:
        return "weak"
    return "laggard"


def _evidence_quality(n: int, *, live: bool) -> Dict[str, Any]:
    if n < _THIN_SAMPLE:
        label = "thin_sample"
    elif n < _MODERATE_SAMPLE:
        label = "moderate_sample"
    else:
        label = "robust_sample"
    return {
        "n": n,
        "sample_label": label,
        "live": bool(live),
        "data_mode": "live" if live else "simulated",
        "reliable": n >= _MODERATE_SAMPLE and live,
    }


class SignalTracker:
    """Append-only JSONL ledger with an in-memory reducer.

    Thread-safe for the modest concurrency of a single FastAPI process. For a
    real multi-process deployment this would move to SQLite/Postgres — the
    public API here is deliberately storage-agnostic so that swap is contained.
    """

    def __init__(self, path: str = DEFAULT_LEDGER_PATH) -> None:
        self.path = path
        self._lock = threading.Lock()

    # -- low-level io -------------------------------------------------------
    def _append(self, event: Dict[str, Any]) -> None:
        with self._lock:
            os.makedirs(os.path.dirname(self.path) or ".", exist_ok=True)
            with open(self.path, "a", encoding="utf-8") as fh:
                fh.write(json.dumps(event, separators=(",", ":")) + "\n")

    def _read_events(self) -> List[Dict[str, Any]]:
        if not os.path.exists(self.path):
            return []
        events: List[Dict[str, Any]] = []
        with self._lock:
            with open(self.path, "r", encoding="utf-8") as fh:
                for line in fh:
                    line = line.strip()
                    if not line:
                        continue
                    try:
                        events.append(json.loads(line))
                    except json.JSONDecodeError:
                        # Skip a corrupt line rather than crash the whole view.
                        continue
        return events

    # -- write api ----------------------------------------------------------
    @staticmethod
    def make_id(ticker: str, date: str, family: str) -> str:
        return f"{str(ticker).upper()}|{date}|{family}"

    def record_signal(
        self,
        *,
        ticker: str,
        date: str,
        strategy_family: str,
        entry_mode: str = "breakout",
        regime_at_entry: Optional[Dict[str, Any]] = None,
        vix: Optional[float] = None,
        breadth: Optional[float] = None,
        rs_pct: Optional[float] = None,
        sector: Optional[str] = None,
        follow_through_quality: Optional[str] = None,
        stop_type: Optional[str] = None,
        live: bool = False,
        stage: str = STAGE_SCANNED,
    ) -> str:
        """Record a freshly generated signal at its initial funnel stage.

        Returns the signal id. Idempotent on (ticker, date, family): a repeat
        call layers a new event but the reducer collapses to latest state.
        """
        sid = self.make_id(ticker, date, strategy_family)
        snapshot = {
            "id": sid,
            "ticker": str(ticker).upper(),
            "date": date,
            "strategy_family": strategy_family,
            "entry_mode": entry_mode,
            "regime_at_entry": dict(regime_at_entry or {}),
            "vix": vix,
            "vix_bucket": vix_bucket(vix),
            "breadth": breadth,
            "rs_pct": rs_pct,
            "rs_bucket": rs_bucket(rs_pct),
            "sector": sector or "unknown",
            "follow_through_quality": follow_through_quality,
            "stop_type": stop_type,
            "live": bool(live),
            "stage": stage,
            "deploy_qualified": stage == STAGE_DEPLOY_QUALIFIED,
            "failed": False,
            "failure_reason": None,
            "mfe_pct": None,
            "mae_pct": None,
            "fwd": {},
            "event": "record",
        }
        self._append(snapshot)
        return sid

    def advance_stage(
        self,
        sid: str,
        stage: str,
        *,
        failure_reason: Optional[str] = None,
    ) -> bool:
        """Advance a signal to a later funnel stage (monotonic).

        Returns False if the signal is unknown or the move is backwards (we
        never rewind a funnel — that would falsify the conversion record).
        """
        if stage not in _STAGE_RANK:
            raise ValueError(f"unknown stage {stage!r}")
        current = self.current().get(sid)
        if current is None:
            return False
        if _STAGE_RANK[stage] < _STAGE_RANK[current["stage"]]:
            return False
        nxt = dict(current)
        nxt["stage"] = stage
        nxt["deploy_qualified"] = current.get("deploy_qualified") or stage in (
            STAGE_DEPLOY_QUALIFIED,
            STAGE_EXECUTED,
            STAGE_WINNER,
        )
        if stage in (STAGE_STOPPED, STAGE_TIMING_MISS):
            nxt["failed"] = True
            nxt["failure_reason"] = failure_reason or current.get("failure_reason")
        nxt["event"] = "advance"
        self._append(nxt)
        return True

    def record_outcome(
        self,
        sid: str,
        *,
        fwd: Optional[Dict[str, float]] = None,
        mfe_pct: Optional[float] = None,
        mae_pct: Optional[float] = None,
    ) -> bool:
        """Attach forward returns / excursions to a tracked signal."""
        current = self.current().get(sid)
        if current is None:
            return False
        nxt = dict(current)
        merged = dict(current.get("fwd") or {})
        merged.update(fwd or {})
        nxt["fwd"] = merged
        if mfe_pct is not None:
            nxt["mfe_pct"] = mfe_pct
        if mae_pct is not None:
            nxt["mae_pct"] = mae_pct
        nxt["event"] = "outcome"
        self._append(nxt)
        return True

    # -- read api -----------------------------------------------------------
    def current(self) -> Dict[str, Dict[str, Any]]:
        """Reduce the event log to latest state per signal id."""
        state: Dict[str, Dict[str, Any]] = {}
        for ev in self._read_events():
            sid = ev.get("id")
            if sid:
                state[sid] = ev
        return state

    def conversion_funnel(self) -> Dict[str, Any]:
        """Cumulative counts per funnel stage + drop-off ratios.

        Counts are cumulative: a 'winner' also counted as having passed
        scanned/.../executed, so the funnel reads top-down honestly.
        """
        rows = list(self.current().values())
        reached = {s: 0 for s in FUNNEL_STAGES}
        for r in rows:
            rank = _STAGE_RANK.get(r["stage"], 0)
            for s in FUNNEL_STAGES[: rank + 1]:
                # Branch stages (stopped/winner/timing_miss) are mutually
                # exclusive terminals — only count the one actually reached.
                if s in TERMINAL_STAGES and s != r["stage"]:
                    continue
                reached[s] += 1
        executed = reached[STAGE_EXECUTED] or 0
        winners = reached[STAGE_WINNER] or 0
        return {
            "total_signals": len(rows),
            "stages": reached,
            "win_rate_on_executed": round(winners / executed, 4) if executed else None,
            "evidence_quality": _evidence_quality(
                len(rows), live=any(r.get("live") for r in rows)
            ),
        }

    def cohort_summary(self, dimension: str) -> Dict[str, Any]:
        """Aggregate forward edge by a cohort dimension.

        dimension ∈ {regime, vix_bucket, sector, rs_bucket, strategy_family,
        entry_mode, follow_through_quality, stop_type}. Each bucket reports win
        rate, mean forward returns, MFE/MAE, and an evidence-quality label so a
        thin cohort can never be read as a reliable edge.
        """
        key = "regime" if dimension == "regime" else dimension
        rows = list(self.current().values())
        buckets: Dict[str, List[Dict[str, Any]]] = defaultdict(list)
        for r in rows:
            if key == "regime":
                bucket = str((r.get("regime_at_entry") or {}).get("trend") or "unknown")
            else:
                bucket = str(r.get(key, "unknown"))
            buckets[bucket].append(r)

        out: List[Dict[str, Any]] = []
        for bucket, items in sorted(buckets.items()):
            closed = [i for i in items if i["stage"] in TERMINAL_STAGES]
            winners = [i for i in closed if i["stage"] == STAGE_WINNER]
            fwd20 = [
                i["fwd"]["d20"]
                for i in items
                if isinstance(i.get("fwd"), dict) and i["fwd"].get("d20") is not None
            ]
            mfes = [i["mfe_pct"] for i in items if i.get("mfe_pct") is not None]
            maes = [i["mae_pct"] for i in items if i.get("mae_pct") is not None]
            live = any(i.get("live") for i in items)
            out.append(
                {
                    "bucket": bucket,
                    "n_signals": len(items),
                    "n_closed": len(closed),
                    "win_rate": round(len(winners) / len(closed), 4)
                    if closed
                    else None,
                    "mean_fwd_20d": round(sum(fwd20) / len(fwd20), 4)
                    if fwd20
                    else None,
                    "mean_mfe_pct": round(sum(mfes) / len(mfes), 4) if mfes else None,
                    "mean_mae_pct": round(sum(maes) / len(maes), 4) if maes else None,
                    "evidence_quality": _evidence_quality(len(closed), live=live),
                }
            )
        out.sort(key=lambda x: x["n_signals"], reverse=True)
        return {"dimension": dimension, "cohorts": out}


# Module-level default instance (request-scoped routers can share it).
_DEFAULT_TRACKER: Optional[SignalTracker] = None


def get_tracker() -> SignalTracker:
    global _DEFAULT_TRACKER
    if _DEFAULT_TRACKER is None:
        _DEFAULT_TRACKER = SignalTracker()
    return _DEFAULT_TRACKER


def build_signal_tracking_context(
    tracker: Optional[SignalTracker] = None,
    *,
    cohort_dimension: str = "regime",
    degraded: bool = False,
) -> Dict[str, Any]:
    """Research-only API payload: funnel + cohort summary wrapped in provenance.

    Authority: research_only. The provenance envelope hard-codes
    deploy_from_signal_alone=False and page_gate_required=True, so this surface
    can inform Discovery/Review context but never authorize a trade.
    """
    trk = tracker or get_tracker()
    funnel = trk.conversion_funnel()
    cohorts = trk.cohort_summary(cohort_dimension)
    thin = funnel["total_signals"] < _MODERATE_SAMPLE
    return build_provenance_envelope(
        signal_type=SIGNAL_SIGNAL_COHORT,
        source="signal_ledger.jsonl",
        degraded=degraded or thin,
        data_mode="research_only",
        extra={
            "funnel": funnel,
            "cohorts": cohorts,
            "thin_sample": thin,
            "note": "Cohort edge is evidence, not authorization — board gate still required.",
        },
    )
