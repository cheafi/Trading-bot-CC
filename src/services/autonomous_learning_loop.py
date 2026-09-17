"""Autonomous Learning Loop — observe → label → calibrate → propose (research_only).

Closes the IDOS learning cycle without granting deploy authority or auto-applying
parameter changes. Human/IC review is required before any belief or config apply.
"""

from __future__ import annotations

import json
import logging
import os
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)

# Production default: OFF — set AUTONOMOUS_LEARNING=1 to enable scheduler/API runs.
_AUTONOMOUS_LEARNING_ENV = "AUTONOMOUS_LEARNING"


def is_autonomous_learning_enabled() -> bool:
    """Return True when autonomous learning loop is explicitly enabled."""
    return os.environ.get(_AUTONOMOUS_LEARNING_ENV, "0").strip().lower() in (
        "1",
        "true",
        "yes",
    )


_DATA_DIR = Path(__file__).resolve().parents[2] / "data"
_STATE_PATH = _DATA_DIR / "autonomous_learning_loop_state.json"
_WEEKLY_IC_CACHE = _DATA_DIR / "weekly_ic_digest_latest.json"


def _utcnow_iso() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def _load_state() -> Dict[str, Any]:
    if not _STATE_PATH.is_file():
        return {}
    try:
        data = json.loads(_STATE_PATH.read_text(encoding="utf-8"))
        return data if isinstance(data, dict) else {}
    except (json.JSONDecodeError, OSError):
        return {}


def _save_state(state: Dict[str, Any]) -> None:
    try:
        _DATA_DIR.mkdir(parents=True, exist_ok=True)
        _STATE_PATH.write_text(json.dumps(state, indent=2), encoding="utf-8")
    except OSError as exc:
        logger.debug("autonomous learning loop state save failed: %s", exc)


def _observe() -> Dict[str, Any]:
    """Collect closed trades, forward marks, and journal counts."""
    from src.engines.self_learning import pull_closed_trades_from_learning_loop
    from src.services.decision_journal import load_recent
    from src.services.forward_outcomes import load_forward_outcomes

    trades = pull_closed_trades_from_learning_loop()
    outcomes = load_forward_outcomes(limit=500)
    journal = load_recent(limit=200)
    marked = sum(1 for o in outcomes if o.get("mark_r") is not None)
    return {
        "closed_trades": len(trades),
        "forward_outcome_rows": len(outcomes),
        "forward_marks_with_r": marked,
        "journal_entries": len(journal),
    }


def _label(trades: List[Dict[str, Any]]) -> Dict[str, Any]:
    """Run unified feedback channels (Brier, Thompson, IC, A/B shadow)."""
    if not trades:
        return {"skipped": True, "reason": "no_closed_trades", "channels": {}}
    from src.engines.self_learning import process_closed_trades_batch

    return process_closed_trades_batch(trades)


def _calibrate() -> Dict[str, Any]:
    """Build quarterly calibration report + Brier status."""
    from src.engines.self_learning import get_calibration_status
    from src.services.calibration_report import build_calibration_report

    report = build_calibration_report(limit=200)
    brier = get_calibration_status()
    return {
        "calibration_report": report,
        "brier": brier,
        "drift_alert": bool(brier.get("alert")),
    }


def _propose(trades: List[Dict[str, Any]]) -> Dict[str, Any]:
    """Queue belief-review items and A/B experiment proposals — never apply."""
    from src.engines.self_learning import (
        auto_schedule_experiments,
        get_auto_schedule_status,
    )
    from src.services.belief_review import build_belief_items
    from src.services.forward_outcomes import load_forward_outcomes

    outcomes = load_forward_outcomes(limit=50)
    belief_items = build_belief_items(outcomes)
    due = sum(1 for it in belief_items if str(it.get("status") or "") == "due_review")

    schedule_result: Dict[str, Any] = {
        "total_proposed": 0,
        "proposed": [],
        "skipped": [],
    }
    if trades:
        schedule_result = auto_schedule_experiments(trades)

    return {
        "beliefs_due": due,
        "belief_queue_size": len(belief_items),
        "ab_experiments_proposed": schedule_result.get("total_proposed", 0),
        "ab_proposals": (schedule_result.get("proposed") or [])[:5],
        "last_auto_schedule": get_auto_schedule_status(),
        "may_authorize_deploy": False,
        "note": "Proposals require human IC review — research_only.",
    }


def _assert_no_deployment_manifest_write() -> None:
    """IDOS mechanical separation — learning loop never mutates deploy manifest."""
    from src.core.deployment_manifest import load_deployment_manifest

    before = load_deployment_manifest()
    if before.get("updated_by") not in (None, "system", "ops", "human"):
        logger.warning(
            "autonomous_learning_loop: unexpected deployment manifest owner %s",
            before.get("updated_by"),
        )


def run_learning_cycle(
    *,
    phases: Optional[List[str]] = None,
    apply_changes: bool = False,
) -> Dict[str, Any]:
    """
    Run the autonomous learning loop.

    Default phases: observe, label, calibrate, propose.
    ``apply_changes`` is ignored unless explicitly True — kept for API parity;
    parameter apply remains on EOD self-learning with kill switch + min sample.
    """
    if apply_changes:
        logger.warning(
            "autonomous_learning_loop: apply_changes=True ignored — "
            "use Ops self-learn trigger for bounded parameter apply"
        )

    _assert_no_deployment_manifest_write()
    manifest_before = None
    try:
        from src.core.deployment_manifest import load_deployment_manifest

        manifest_before = load_deployment_manifest()
    except Exception:
        manifest_before = None

    active_phases = phases or ["observe", "label", "calibrate", "propose"]
    started = _utcnow_iso()
    result: Dict[str, Any] = {
        "as_of": started,
        "authority": "research_only",
        "may_authorize_deploy": False,
        "phases_run": active_phases,
        "apply_changes": False,
    }

    observe_data: Dict[str, Any] = {}
    trades: List[Dict[str, Any]] = []

    if "observe" in active_phases:
        observe_data = _observe()
        result["observe"] = observe_data
        if observe_data.get("closed_trades"):
            from src.engines.self_learning import pull_closed_trades_from_learning_loop

            trades = pull_closed_trades_from_learning_loop()

    if "label" in active_phases:
        result["label"] = _label(trades)

    if "calibrate" in active_phases:
        result["calibrate"] = _calibrate()

    if "propose" in active_phases:
        result["propose"] = _propose(trades)

    result["headline"] = _headline(result)
    state = _load_state()
    state["last_run"] = result
    state["last_run_at"] = started
    state["run_count"] = int(state.get("run_count") or 0) + 1
    _save_state(state)

    if manifest_before is not None:
        from src.core.deployment_manifest import load_deployment_manifest

        manifest_after = load_deployment_manifest()
        result["deployment_manifest_unchanged"] = manifest_before.get(
            "deploy_open"
        ) == manifest_after.get("deploy_open") and manifest_before.get(
            "updated_at"
        ) == manifest_after.get("updated_at")
    return result


def _headline(payload: Dict[str, Any]) -> str:
    obs = payload.get("observe") or {}
    cal = (payload.get("calibrate") or {}).get("calibration_report") or {}
    prop = payload.get("propose") or {}
    marks = (
        (cal.get("sample") or {}).get("forward_marks")
        or obs.get("forward_marks_with_r")
        or 0
    )
    due = prop.get("beliefs_due") or 0
    if marks == 0 and obs.get("closed_trades", 0) == 0:
        return "Learning loop idle — log decisions and close trades to compound."
    parts = [f"{marks} calibration marks"]
    if due:
        parts.append(f"{due} beliefs due review")
    if prop.get("ab_experiments_proposed"):
        parts.append(f"{prop['ab_experiments_proposed']} A/B proposals queued")
    return " · ".join(parts)


def build_meta_intelligence_summary() -> Dict[str, Any]:
    """
    Ops Meta Intelligence panel — usage telemetry + outcomes + learning loop state.

    Research_only; never sets deploy_open.
    """
    from src.services.calibration_report import build_calibration_report
    from src.services.override_journal import build_override_summary
    from src.services.usage_log import build_ai_usage_summary, build_usage_summary

    state = _load_state()
    last_run = state.get("last_run") or {}
    observe = last_run.get("observe") or _observe()
    calibration = build_calibration_report(limit=100)
    usage = build_usage_summary()
    ai_usage = build_ai_usage_summary()
    overrides = build_override_summary()

    return {
        "as_of": _utcnow_iso(),
        "authority": "research_only",
        "may_authorize_deploy": False,
        "loop": {
            "last_run_at": state.get("last_run_at"),
            "run_count": int(state.get("run_count") or 0),
            "headline": last_run.get("headline") or _headline({"observe": observe}),
            "observe": observe,
            "propose": last_run.get("propose") or {},
        },
        "calibration": {
            "headline": calibration.get("headline"),
            "sample": calibration.get("sample"),
            "recommendation": calibration.get("recommendation"),
        },
        "surface_usage": {
            "total_events": usage.get("total_events"),
            "deletion_candidates": usage.get("deletion_candidates"),
            "by_surface": usage.get("by_surface"),
        },
        "ai_usage": ai_usage,
        "overrides": {
            "total": overrides.get("total"),
            "in_cooldown": (overrides.get("cooldown") or {}).get("in_cooldown"),
        },
        "idos_questions": {
            "know": f"{observe.get('forward_marks_with_r', 0)} forward marks on record",
            "believe": (last_run.get("propose") or {}).get("beliefs_due", 0),
            "doubt": "Calibration drift"
            if (last_run.get("calibrate") or {}).get("drift_alert")
            else 0,
            "act": "Human deploy gate unchanged",
        },
    }


def persist_weekly_ic_digest(
    *, board: Optional[Dict[str, Any]] = None
) -> Dict[str, Any]:
    """Scheduler hook — cache weekly IC digest JSON for Ops export."""
    from src.services.weekly_ic_digest import build_weekly_ic_digest

    digest = build_weekly_ic_digest(board=board)
    digest["cached_at"] = _utcnow_iso()
    try:
        _DATA_DIR.mkdir(parents=True, exist_ok=True)
        _WEEKLY_IC_CACHE.write_text(json.dumps(digest, indent=2), encoding="utf-8")
    except OSError as exc:
        logger.debug("weekly IC digest cache failed: %s", exc)
    return digest


def load_cached_weekly_ic_digest() -> Optional[Dict[str, Any]]:
    if not _WEEKLY_IC_CACHE.is_file():
        return None
    try:
        return json.loads(_WEEKLY_IC_CACHE.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        return None
