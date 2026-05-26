"""Flow follow-through — honest calibration proxy from self-learning history."""

from __future__ import annotations

import time
from typing import Any, Dict, Optional

_GRADE_CONF = {"A": 0.78, "B": 0.68, "C": 0.58}
_CALIB_CACHE: Optional[Dict[str, Any]] = None
_CALIB_CACHE_TS = 0.0
_CALIB_TTL_SEC = 60.0


def clear_calibration_cache() -> None:
    """Test hook — reset cached calibration payload."""
    global _CALIB_CACHE, _CALIB_CACHE_TS
    _CALIB_CACHE = None
    _CALIB_CACHE_TS = 0.0


def _calibration_data() -> Optional[Dict[str, Any]]:
    """Load calibration buckets once per TTL (avoids N× reload per flow scan)."""
    global _CALIB_CACHE, _CALIB_CACHE_TS
    now = time.monotonic()
    if _CALIB_CACHE is not None and (now - _CALIB_CACHE_TS) < _CALIB_TTL_SEC:
        return _CALIB_CACHE
    try:
        from src.engines.self_learning import get_calibration_buckets
    except Exception:
        return None
    _CALIB_CACHE = get_calibration_buckets()
    _CALIB_CACHE_TS = now
    return _CALIB_CACHE


def _confidence_from_flow(*, radar_score: Optional[float], grade: str) -> float:
    if radar_score is not None and radar_score > 0:
        return min(0.95, max(0.50, float(radar_score) / 100.0))
    return _GRADE_CONF.get((grade or "C").upper(), 0.58)


def lookup_flow_follow_through(
    *,
    radar_score: Optional[float] = None,
    grade: str = "C",
    cal: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    """
    Map flow score/grade to nearest calibration bucket (trade outcomes).
    Returns explicit basis — not fake precision when n is low.
    """
    cal = cal if cal is not None else _calibration_data()
    if cal is None:
        return _empty_follow_through("calibration_module_unavailable")

    total = int(cal.get("total_records") or 0)
    if total < 5:
        return _empty_follow_through("insufficient_calibration_sample", total=total)

    conf = _confidence_from_flow(radar_score=radar_score, grade=grade)
    bucket = None
    for b in cal.get("buckets") or []:
        lo = float(b.get("lo") or 0)
        hi = float(b.get("hi") or 1)
        if lo <= conf < hi:
            bucket = b
            break

    if not bucket or int(bucket.get("n") or 0) < 3:
        return {
            "follow_through_percentile": None,
            "hit_rate": None,
            "avg_forward_return_pct": None,
            "sample_n": int(bucket.get("n") or 0) if bucket else 0,
            "total_calibration_n": total,
            "bucket": bucket.get("label") if bucket else None,
            "basis": "calibration_sparse",
            "label": "Insufficient bucket sample (need n≥3)",
            "sufficient": False,
        }

    hit = bucket.get("hit_rate")
    avg_fwd = bucket.get("avg_forward_return_pct")
    percentile = round(float(hit) * 100, 1) if hit is not None else None

    return {
        "follow_through_percentile": percentile,
        "hit_rate": hit,
        "avg_forward_return_pct": avg_fwd,
        "avg_mae_pct": bucket.get("avg_mae_pct"),
        "sample_n": int(bucket.get("n") or 0),
        "total_calibration_n": total,
        "bucket": bucket.get("label"),
        "calibrated": bucket.get("calibrated"),
        "basis": "self_learning_trade_outcomes",
        "label": (
            f"Similar-confidence trades: {percentile}% hit, "
            f"{avg_fwd:+.2f}% avg fwd (n={bucket.get('n')})"
            if percentile is not None and avg_fwd is not None
            else f"Bucket {bucket.get('label')} n={bucket.get('n')}"
        ),
        "sufficient": int(bucket.get("n") or 0) >= 5,
    }


def _empty_follow_through(reason: str, *, total: int = 0) -> Dict[str, Any]:
    return {
        "follow_through_percentile": None,
        "hit_rate": None,
        "avg_forward_return_pct": None,
        "sample_n": 0,
        "total_calibration_n": total,
        "bucket": None,
        "basis": reason,
        "label": "Not calibrated — deploy sizing only after sample grows",
        "sufficient": False,
    }


def global_calibration_summary(*, cal: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    """Platform-wide flow grade calibration headline for Flow tab."""
    cal = cal if cal is not None else _calibration_data()
    if cal is None:
        return {"available": False, "reason": "module_unavailable"}

    total = int(cal.get("total_records") or 0)
    if total < 5:
        return {
            "available": False,
            "total_records": total,
            "reason": "insufficient_sample",
            "label": f"Need 5+ closed trades with forward returns (have {total})",
        }

    buckets = cal.get("buckets") or []
    best = max(
        (b for b in buckets if b.get("n", 0) >= 3),
        key=lambda x: float(x.get("hit_rate") or 0),
        default=None,
    )
    return {
        "available": True,
        "total_records": total,
        "ece": cal.get("calibration_quality"),
        "best_bucket": best.get("label") if best else None,
        "best_hit_rate": best.get("hit_rate") if best else None,
        "best_avg_fwd_pct": best.get("avg_forward_return_pct") if best else None,
        "label": (
            f"Calibration active — {total} records; best bucket "
            f"{best.get('label')}: {(best.get('hit_rate') or 0)*100:.0f}% hit"
            if best
            else f"Calibration active — {total} records"
        ),
    }
