"""Qualification levels — honest setup / trade / execution / deploy counts."""

from __future__ import annotations

from typing import Any, Dict, List, Optional

from src.services.decision_truth_model import _AVOID_ACTIONS
from src.services.score_sanity import apply_score_sanity_to_row

_SETUP_MIN_SCORE = 6.5
_TRADE_ACTIONS = frozenset({"TRADE", "BUY", "BUY_ON_DIP", "STRONG_TRADE", "TRADE_NOW"})
_PILOT_ACTIONS = frozenset({"PILOT"})
_WATCH_ACTIONS = frozenset({"WATCH", "WAIT", "WATCH_TRIGGER", "LEADER", "LEADER_MONITOR"})


def _norm(action: Optional[str]) -> str:
    return (action or "WATCH").upper().strip()


def _row_setup_qualified(row: Dict[str, Any]) -> bool:
    act = _norm(row.get("action"))
    if act in _AVOID_ACTIONS:
        return False
    try:
        score = float(row.get("score") or 0)
    except (TypeError, ValueError):
        return False
    if score < _SETUP_MIN_SCORE or score > 10:
        return False
    return bool(row.get("ticker"))


def _row_trade_qualified(row: Dict[str, Any]) -> bool:
    if not _row_setup_qualified(row):
        return False
    act = _norm(row.get("action"))
    if act not in _TRADE_ACTIONS and act not in _PILOT_ACTIONS:
        return False
    thesis = float(row.get("thesis_conf") or row.get("final_conf") or 0)
    timing = float(row.get("timing_conf") or row.get("final_conf") or 0)
    return thesis >= 0.55 or timing >= 0.50


def _row_execution_qualified(row: Dict[str, Any]) -> bool:
    return bool(row.get("execution_ready")) and _row_trade_qualified(row)


def _row_deploy_qualified(row: Dict[str, Any], *, deploy_authority: bool) -> bool:
    if not deploy_authority:
        return False
    return _row_execution_qualified(row)


def compute_qualification_levels(
    opportunities: List[Dict[str, Any]],
    *,
    deploy_authority: bool = False,
    funnel: Optional[Dict[str, Any]] = None,
    sample_size: Optional[int] = None,
) -> Dict[str, Any]:
    """Per-row and aggregate qualification — deploy_qualified requires deploy_authority."""
    rows = [apply_score_sanity_to_row(r, sample_size=sample_size) for r in opportunities]
    setup = [r for r in rows if _row_setup_qualified(r)]
    trade = [r for r in rows if _row_trade_qualified(r)]
    execution = [r for r in rows if _row_execution_qualified(r)]
    deploy = [r for r in rows if _row_deploy_qualified(r, deploy_authority=deploy_authority)]

    f = funnel or {}
    setup_n = len(setup) or int(f.get("watch_qualified_setups") or f.get("triggered_setups") or 0)
    trade_n = len(trade)
    exec_n = len(execution) or int(f.get("execution_ready_setups") or 0)
    deploy_n = len(deploy) if deploy_authority else 0

    count_line = (
        f"{setup_n} setup-qualified · {deploy_n} deploy-qualified"
    )

    return {
        "setup_qualified": setup_n,
        "trade_qualified": trade_n,
        "execution_qualified": exec_n,
        "deploy_qualified": deploy_n,
        "count_line": count_line,
        "setup_tickers": [r.get("ticker") for r in setup[:8] if r.get("ticker")],
        "deploy_tickers": [r.get("ticker") for r in deploy[:5] if r.get("ticker")],
        "deploy_authority_required": True,
        "rows_sanitized": rows,
    }


def qualification_count_line(levels: Optional[Dict[str, Any]] = None) -> str:
    lv = levels or {}
    return str(
        lv.get("count_line")
        or f"{lv.get('setup_qualified', 0)} setup-qualified · {lv.get('deploy_qualified', 0)} deploy-qualified"
    )
