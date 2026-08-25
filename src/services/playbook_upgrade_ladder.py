"""Playbook monitor + upgrade ladder — distance gaps, buckets, operator language."""

from __future__ import annotations

from typing import Any, Dict, List

from src.services.decision_truth_model import (
    TRADE_RR_THRESHOLD,
    build_trade_bar_status,
    parse_ratio,
)

THESIS_GATE = 0.65
TIMING_TRADE_GATE = 0.65
TIMING_WATCH_GATE = 0.50
EXEC_GATE = 0.40
DATA_GATE = 0.35

_TRADE_ACTIONS = frozenset({"TRADE", "BUY", "BUY_ON_DIP", "TRADE_NOW", "STRONG_TRADE"})
_REJECT_ACTIONS = frozenset({"AVOID", "NO_TRADE"})


def _f(val: Any, default: float = 0.0) -> float:
    try:
        return float(val if val is not None else default)
    except (TypeError, ValueError):
        return default


def compute_upgrade_gaps(row: Dict[str, Any]) -> Dict[str, str]:
    """Compact gap labels for thesis / timing / R:R / exec / data."""
    thesis = _f(row.get("thesis_conf"))
    timing = _f(row.get("timing_conf"))
    exec_c = _f(row.get("exec_conf"))
    data_c = _f(row.get("data_conf"))
    rr = parse_ratio(row.get("risk_reward"), 0.0) or 0.0

    gaps: Dict[str, str] = {}
    if thesis < THESIS_GATE:
        gaps["thesis"] = f"+{int(max(0, (THESIS_GATE - thesis) * 100))}"
    else:
        gaps["thesis"] = "ok"

    if timing < TIMING_TRADE_GATE:
        gaps["timing"] = f"+{int(max(0, (TIMING_TRADE_GATE - timing) * 100))}"
    elif timing < TIMING_WATCH_GATE:
        gaps["timing"] = f"+{int(max(0, (TIMING_WATCH_GATE - timing) * 100))}"
    else:
        gaps["timing"] = "ok"

    if rr > 0 and rr < TRADE_RR_THRESHOLD:
        gaps["rr"] = f"+{TRADE_RR_THRESHOLD - rr:.1f}"
    elif rr <= 0:
        gaps["rr"] = "n/a"
    else:
        gaps["rr"] = "ok"

    if exec_c < EXEC_GATE or not row.get("execution_ready"):
        gaps["exec"] = "blocked" if exec_c < EXEC_GATE else "not ready"
    else:
        gaps["exec"] = "ok"

    if data_c < DATA_GATE:
        gaps["data"] = f"+{int(max(0, (DATA_GATE - data_c) * 100))}"
    else:
        gaps["data"] = "ok"

    return gaps


def upgrade_proximity_score(row: Dict[str, Any]) -> float:
    """Lower score = closer to upgrade (sort ascending)."""
    thesis = _f(row.get("thesis_conf"))
    timing = _f(row.get("timing_conf"))
    exec_c = _f(row.get("exec_conf"))
    data_c = _f(row.get("data_conf"))
    rr = parse_ratio(row.get("risk_reward"), 0.0) or 0.0
    score = 0.0
    score += max(0.0, THESIS_GATE - thesis) * 100
    score += max(0.0, TIMING_TRADE_GATE - timing) * 100
    if rr > 0 and rr < TRADE_RR_THRESHOLD:
        score += (TRADE_RR_THRESHOLD - rr) * 10
    if exec_c < EXEC_GATE:
        score += (EXEC_GATE - exec_c) * 80
    if not row.get("execution_ready"):
        score += 25
    if data_c < DATA_GATE:
        score += (DATA_GATE - data_c) * 40
    act = (row.get("action") or "").upper()
    if act in _REJECT_ACTIONS:
        score += 500
    return round(score, 2)


def classify_ladder_bucket(row: Dict[str, Any]) -> str:
    """deploy_ready | pilot_ready | watch_upgrade | hard_reject."""
    act = (row.get("action") or "").upper()
    if act in _REJECT_ACTIONS:
        return "hard_reject"
    bar = row.get("trade_bar") or build_trade_bar_status(row)
    if (
        act in _TRADE_ACTIONS
        and row.get("execution_ready")
        and bar.get("passes_trade_bar")
    ):
        return "deploy_ready"
    if act == "PILOT" and not row.get("pilot_downgraded"):
        return "pilot_ready"
    return "watch_upgrade"


def _primary_gap(row: Dict[str, Any], gaps: Dict[str, str]) -> str:
    order = ["exec", "timing", "thesis", "rr", "data"]
    for key in order:
        val = gaps.get(key, "ok")
        if val not in ("ok", "n/a"):
            return key
    return ""


def operator_action_line(row: Dict[str, Any]) -> str:
    """Short monitoring language — not order advice."""
    act = (row.get("action") or "").upper()
    if act in _REJECT_ACTIONS:
        return "Avoid until RS improves"
    gaps = row.get("upgrade_gaps") or compute_upgrade_gaps(row)
    primary = _primary_gap(row, gaps)
    if primary == "exec":
        return "Wait for breakout reclaim"
    if primary == "timing":
        if _f(row.get("thesis_conf")) >= THESIS_GATE:
            return "Wait for pullback hold"
        return "Monitor only"
    if primary == "thesis":
        return "Monitor only"
    if primary == "rr":
        return "Monitor only"
    if primary == "data":
        return "Monitor only"
    if act == "PILOT":
        return "Pilot review only — page gate applies"
    bar = row.get("trade_bar") or build_trade_bar_status(row)
    if bar.get("passes_trade_bar"):
        return "Review path only — confirm page gate"
    return "Monitor only"


def holder_guidance_line(row: Dict[str, Any]) -> str:
    stop = row.get("stop_price") or row.get("invalidation_price")
    inv = row.get("invalidation") or ""
    act = (row.get("action") or "").upper()
    if act in _REJECT_ACTIONS:
        return "Existing holders: exit thesis if monitor zone lost"
    if stop:
        try:
            sp = float(stop)
            return f"Hold if above monitor zone ${sp:.2f}; reduce if loses zone"
        except (TypeError, ValueError):
            pass
    if inv:
        return f"Hold if thesis intact; reduce if {inv}"
    return "Hold if above monitor zone; reduce if thesis breaks"


def alert_trigger_line(row: Dict[str, Any]) -> str:
    """Alert-ready monitoring string."""
    entry = row.get("entry_price")
    stop = row.get("stop_price")
    trigger = row.get("upgrade_trigger") or ""
    if trigger:
        return str(trigger)[:120]
    parts: List[str] = []
    if entry:
        try:
            parts.append(f"above ${float(entry):.2f} on volume")
        except (TypeError, ValueError):
            pass
    if stop:
        try:
            parts.append(f"hold monitor zone ${float(stop):.2f}")
        except (TypeError, ValueError):
            pass
    leader = (row.get("leader") or "").upper()
    if leader == "LAGGARD":
        parts.append("recover relative strength rank")
    if not parts:
        parts.append("break monitor zone on volume")
    return " · ".join(parts)


def why_here_line(row: Dict[str, Any]) -> str:
    """One-line rank explanation."""
    explain = row.get("rank_explain") or []
    if explain:
        return str(explain[0])[:140]
    gaps = row.get("upgrade_gaps") or compute_upgrade_gaps(row)
    thesis = gaps.get("thesis") == "ok"
    timing = gaps.get("timing") == "ok"
    rr_ok = gaps.get("rr") in ("ok", "n/a")
    exec_ok = gaps.get("exec") == "ok"
    if thesis and not timing:
        return "Strong thesis, weak timing"
    if timing and not thesis:
        return "Strong timing, weak thesis"
    if rr_ok and not exec_ok:
        return "R:R okay, execution blocked"
    if (row.get("leader") or "").upper() == "LAGGARD":
        return "Sector leadership weak"
    rr = parse_ratio(row.get("risk_reward"), 0.0) or 0.0
    if rr >= TRADE_RR_THRESHOLD:
        return "Best R:R among blocked names"
    score = _f(row.get("score"))
    return f"Fit score {score:.1f} — monitor priority"


def enrich_row_ladder_fields(row: Dict[str, Any]) -> Dict[str, Any]:
    """Attach ladder fields to a playbook row."""
    row = dict(row)
    row["upgrade_gaps"] = compute_upgrade_gaps(row)
    row["ladder_bucket"] = classify_ladder_bucket(row)
    row["upgrade_proximity"] = upgrade_proximity_score(row)
    row["operator_action"] = operator_action_line(row)
    row["holder_guidance"] = holder_guidance_line(row)
    row["alert_trigger"] = alert_trigger_line(row)
    row["why_here"] = why_here_line(row)
    if not row.get("upgrade_trigger"):
        row["upgrade_trigger"] = alert_trigger_line(row)
    return row


def sort_rows_by_upgrade_proximity(rows: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    return sorted(rows, key=lambda r: (upgrade_proximity_score(r), -_f(r.get("score"))))
