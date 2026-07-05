"""Score display sanity — hide fake precision on invalid or uncalibrated values."""

from __future__ import annotations

from typing import Any, Dict, Optional

_SCORE_MIN = 0.0
_SCORE_MAX = 10.0


def calibration_state(*, sample_size: Optional[int] = None, score: Optional[float] = None) -> str:
    """heuristic | provisional | invalid — when no sample size, scores are provisional."""
    if score is not None and not _score_in_range(score):
        return "invalid"
    if sample_size is None or int(sample_size) <= 0:
        return "provisional"
    if int(sample_size) < 30:
        return "provisional"
    return "heuristic"


def _score_in_range(score: float) -> bool:
    return _SCORE_MIN <= float(score) <= _SCORE_MAX


def sanitize_score_display(
    score: Any,
    *,
    sample_size: Optional[int] = None,
    raw_label: str = "",
) -> Dict[str, Any]:
    """
    Clamp or omit nonsensical scores (e.g. -491.5).

    Returns display fields for UI — never surfaces invalid numbers as precision.
    """
    try:
        val = float(score)
    except (TypeError, ValueError):
        return {
            "score_raw": score,
            "score_display": "invalid",
            "score_display_label": raw_label or "invalid",
            "calibration_state": "invalid",
            "valid": False,
        }

    cal = calibration_state(sample_size=sample_size, score=val)
    if not _score_in_range(val):
        return {
            "score_raw": val,
            "score_display": "invalid",
            "score_display_label": "invalid",
            "calibration_state": "invalid",
            "valid": False,
        }

    return {
        "score_raw": round(val, 1),
        "score_display": round(val, 1),
        "score_display_label": raw_label or str(round(val, 1)),
        "calibration_state": cal,
        "valid": True,
    }


def apply_score_sanity_to_row(row: Dict[str, Any], *, sample_size: Optional[int] = None) -> Dict[str, Any]:
    """Attach sanitized score fields to an opportunity / scanner row."""
    out = dict(row)
    raw = out.get("score") if out.get("score") is not None else out.get("strength")
    sane = sanitize_score_display(raw, sample_size=sample_size or out.get("calibration_n"))
    out.update(sane)
    if not sane.get("valid"):
        out["score"] = None
        if "strength" in out:
            out["strength"] = None
    return out
