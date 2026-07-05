"""
Confidence-based position sizing suggestions — template only, not deploy permission.

Wired into /api/v7/today actionable_today[] and Playbook trade/pilot rows in daily mode.
"""

from __future__ import annotations

import os
from typing import Any, Dict, List, Optional, Tuple


def _env_float(name: str, default: float) -> float:
    raw = os.environ.get(name, "").strip()
    if not raw:
        return default
    try:
        return float(raw)
    except ValueError:
        return default
from src.services.opportunity_quality import _row_data_quality_pct, _row_sample_size

ACTION_FULL = "full"
ACTION_HALF = "half"
ACTION_QUARTER = "quarter"
ACTION_WAIT = "wait"
ACTION_MONITOR = "monitor_only"

_AVOID = frozenset({"AVOID", "NO_TRADE", "PASS", "EXIT", "REDUCE", "BLOCKED"})
_ACTIONABLE = frozenset(
    {"TRADE", "BUY", "BUY_ON_DIP", "PILOT", "STRONG_TRADE", "TRADE_NOW"}
)
_PILOT_GRADES = frozenset({"B+", "B"})


def _deploy_tier(truth: Dict[str, Any]) -> str:
    tier = str(truth.get("deploy_authority_tier") or truth.get("deployAuthority") or "").lower()
    if tier in ("allowed", "paper_only", "pilot_only", "blocked"):
        return tier
    return "allowed" if truth.get("deploy_authority") else "blocked"


def _full_pct() -> float:
    return _env_float("CC_MAX_POSITION_PCT", 0.01)


def _pct_label(pct: float, suffix: str) -> str:
    return f"{pct * 100:.1f}% · {suffix}"


def _candidate_action(candidate: Dict[str, Any]) -> str:
    return str(
        candidate.get("effective_action")
        or candidate.get("action")
        or "WATCH"
    ).upper()


def _candidate_conf(candidate: Dict[str, Any]) -> float:
    for key in ("final_conf", "confidence"):
        val = candidate.get(key)
        if val is not None:
            try:
                v = float(val)
                return v / 100.0 if v > 1.0 else v
            except (TypeError, ValueError):
                pass
    breakdown = candidate.get("confidence_breakdown") or {}
    if breakdown.get("final") is not None:
        try:
            v = float(breakdown["final"])
            return v / 100.0 if v > 1.0 else v
        except (TypeError, ValueError):
            pass
    return 0.0


def _candidate_rr(candidate: Dict[str, Any]) -> float:
    for key in ("risk_reward", "rr_ratio", "rr"):
        val = candidate.get(key)
        if val is not None:
            try:
                return float(val)
            except (TypeError, ValueError):
                pass
    return 0.0


def _is_uncalibrated(candidate: Dict[str, Any]) -> bool:
    sample = _row_sample_size(candidate)
    dq = _row_data_quality_pct(candidate)
    if sample < 20:
        return True
    if dq > 0 and dq < 55:
        return True
    cal = candidate.get("calibration") or {}
    if cal.get("calibrated") is False:
        return True
    ev = candidate.get("setup_evidence") or candidate.get("evidence") or {}
    if ev.get("heuristic_only"):
        return True
    return False


def _confidence_band(candidate: Dict[str, Any]) -> Tuple[str, bool]:
    """Return (band, uncalibrated). band: high | medium | low | very_low."""
    score = float(candidate.get("score") or 0)
    conf = _candidate_conf(candidate)
    rr = _candidate_rr(candidate)
    dq = _row_data_quality_pct(candidate)
    uncal = _is_uncalibrated(candidate)

    if score >= 7.5 and conf >= 0.65 and rr >= 2.0 and dq >= 70:
        return "high", uncal
    if score >= 7.0 and conf >= 0.55 and rr >= 1.8:
        return "medium", uncal
    grade = str(candidate.get("grade") or candidate.get("setup_grade") or "").upper()
    if grade in _PILOT_GRADES or score >= 7.0:
        return "low", uncal
    return "very_low", uncal


def _structure_note(candidate: Dict[str, Any]) -> str:
    grade = str(candidate.get("grade") or candidate.get("setup_grade") or "").strip()
    score = candidate.get("score")
    parts: List[str] = []
    if grade:
        parts.append(f"{grade} structure")
    elif score is not None:
        parts.append(f"score {score}")
    rr = _candidate_rr(candidate)
    if rr > 0:
        parts.append(f"R:R {rr:.1f}")
    dq = _row_data_quality_pct(candidate)
    if dq > 0:
        parts.append(f"data {int(dq)}%")
    return ", ".join(parts) if parts else "developing setup"


def _band_zh(band: str) -> str:
    return {
        "high": "高信心 · 可較大倉位",
        "medium": "中信心 · 半倉試探",
        "low": "低信心 · 小倉探路",
        "very_low": "等待確認",
    }.get(band, "等待確認")


def _build_rationale(
    candidate: Dict[str, Any],
    *,
    band: str,
    uncalibrated: bool,
    en_action: str,
) -> str:
    struct = _structure_note(candidate)
    zh = _band_zh(band)
    if uncalibrated:
        zh_note = "啟發式評分 · 上限半倉"
        en_note = "heuristic scoring — cap at half size"
    else:
        zh_note = ""
        en_note = ""
    zh_line = f"{zh}" + (f" ({en_action})" if en_action else "")
    if zh_note:
        zh_line += f" — {zh_note}"
    en_line = f"{struct} — {en_action or 'wait'}"
    if en_note:
        en_line += f" ({en_note})"
    return f"{struct} — {zh_note or zh.split('·')[0].strip()} · {en_line}"


def _wait_result(
    *,
    band: str,
    label: str = "Wait",
    zh: str = "等待確認",
    rationale: str = "",
) -> Dict[str, Any]:
    return {
        "action": ACTION_WAIT,
        "size_pct": 0.0,
        "size_label": f"{label} · {zh}",
        "confidence_band": band,
        "rationale": rationale or f"不可部署 · 僅監察，不定倉 · {label} — structure weak or gates closed",
    }


def _monitor_result(truth: Dict[str, Any], candidate: Dict[str, Any]) -> Dict[str, Any]:
    band, _ = _confidence_band(candidate)
    blocker = str(truth.get("primary_blocker") or "deploy blocked")
    return {
        "action": ACTION_MONITOR,
        "size_pct": 0.0,
        "size_label": "Wait · 僅監察",
        "confidence_band": band,
        "rationale": (
            f"不可部署 · 僅監察，不定倉 · Deploy blocked ({blocker}) — "
            f"{_structure_note(candidate)}"
        ),
        "sanitized": True,
    }


def suggest_position_size(
    candidate: Dict[str, Any],
    truth: Optional[Dict[str, Any]] = None,
    portfolio_context: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    """
    Template sizing from confidence + deploy authority tier — not capital permission.

    Returns action, size_pct, size_label, confidence_band, rationale (中文 + EN).
    """
    _ = portfolio_context
    c = dict(candidate or {})
    t = dict(truth or {})
    tier = _deploy_tier(t)
    act = _candidate_action(c)
    band, uncalibrated = _confidence_band(c)
    full = _full_pct()
    half = round(full * 0.5, 4)
    quarter = round(full * 0.25, 4)

    if act in _AVOID:
        return _wait_result(
            band=band,
            label="Wait",
            zh="等待確認",
            rationale=f"{_structure_note(c)} — AVOID / no edge · 等待確認",
        )

    if tier == "blocked":
        return _monitor_result(t, c)

    execution_ready = bool(c.get("execution_ready"))

    def _pack(action: str, pct: float, label_suffix: str, en_action: str) -> Dict[str, Any]:
        if uncalibrated and pct > half:
            pct = half
            action = ACTION_HALF
            label_suffix = "Half (heuristic cap)"
        return {
            "action": action,
            "size_pct": round(pct, 4),
            "size_label": _pct_label(pct, label_suffix),
            "confidence_band": band,
            "rationale": _build_rationale(
                c, band=band, uncalibrated=uncalibrated, en_action=en_action
            ),
            "heuristic_cap": uncalibrated,
        }

    if tier == "paper_only":
        if band in ("high", "medium"):
            return _pack(ACTION_HALF, half, "Half pilot (paper)", "paper half pilot")
        if band == "low":
            return _pack(ACTION_QUARTER, quarter, "Probe (paper)", "paper quarter probe")
        return _wait_result(
            band=band,
            rationale=f"{_structure_note(c)} — paper path · 等待確認 · wait for confirmation",
        )

    if tier in ("allowed", "pilot_only"):
        if not execution_ready and tier == "allowed" and act not in ("PILOT",):
            if band == "very_low":
                return _wait_result(
                    band=band,
                    rationale=f"{_structure_note(c)} — not execution-ready · 等待確認",
                )
        if band == "high" and execution_ready and tier == "allowed":
            return _pack(ACTION_FULL, full, "Full pilot", "full pilot")
        if band in ("high", "medium"):
            return _pack(ACTION_HALF, half, "Half", "half probe")
        if band == "low":
            return _pack(ACTION_QUARTER, quarter, "Probe", "quarter probe")
        return _wait_result(
            band=band,
            rationale=f"{_structure_note(c)} — 等待確認 · wait for stronger confirmation",
        )

    return _monitor_result(t, c)


def sanitize_sizing_for_authority(
    sizing: Dict[str, Any],
    truth: Optional[Dict[str, Any]] = None,
    candidate: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    """Strip positive sizing when deploy blocked (not paper_only)."""
    t = dict(truth or {})
    tier = _deploy_tier(t)
    c = dict(candidate or {})
    if tier == "paper_only":
        s = dict(sizing or {})
        if float(s.get("size_pct") or 0) > _full_pct() * 0.5:
            s["size_pct"] = round(_full_pct() * 0.5, 4)
            s["action"] = ACTION_HALF
            s["size_label"] = _pct_label(s["size_pct"], "Half (paper max)")
        return s
    if tier != "blocked":
        return dict(sizing or {})
    return _monitor_result(t, c)


def _is_actionable_row(row: Dict[str, Any]) -> bool:
    act = _candidate_action(row)
    if act in _AVOID:
        return False
    if act in _ACTIONABLE:
        return True
    if act == "PILOT":
        return True
    score = float(row.get("score") or 0)
    grade = str(row.get("grade") or "").upper()
    return score >= 7.0 or grade in _PILOT_GRADES


def attach_sizing_to_row(
    row: Dict[str, Any],
    truth: Optional[Dict[str, Any]] = None,
    *,
    portfolio_context: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    """Mutate row in place with sanitized sizing."""
    sizing = suggest_position_size(row, truth, portfolio_context)
    row["sizing"] = sanitize_sizing_for_authority(sizing, truth, row)
    return row


def attach_sizing_to_rows(
    rows: Optional[List[Dict[str, Any]]],
    truth: Optional[Dict[str, Any]] = None,
    *,
    portfolio_context: Optional[Dict[str, Any]] = None,
    trade_pilot_only: bool = False,
) -> List[Dict[str, Any]]:
    out: List[Dict[str, Any]] = []
    for row in rows or []:
        r = dict(row)
        act = _candidate_action(r)
        if trade_pilot_only and act not in _ACTIONABLE and act != "PILOT":
            out.append(r)
            continue
        attach_sizing_to_row(r, truth, portfolio_context=portfolio_context)
        out.append(r)
    return out
