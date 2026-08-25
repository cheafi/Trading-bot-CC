"""Lightweight ML / self-learn advisory for Dashboard — research-only, no deploy authority."""

from __future__ import annotations

import logging
from typing import Any, Dict, List

logger = logging.getLogger(__name__)

_AUTHORITY_NOTE = (
    "Advisory only — ML insights do not grant deploy authority. "
    "研究/監控參考 only."
)


def build_ml_advisory_summary() -> Dict[str, Any]:
    """Aggregate feature IC, calibration, learning loop, Thompson for Today tab."""
    lines: List[str] = []
    payload: Dict[str, Any] = {
        "authority_note": _AUTHORITY_NOTE,
        "active": False,
        "lines": lines,
        "status": "inactive",
    }

    try:
        from src.engines.feature_ic import get_feature_ic_status

        ic = get_feature_ic_status()
        payload["feature_ic"] = ic
        alerts = ic.get("alerts") or []
        if alerts:
            payload["active"] = True
            lines.append(
                f"Feature IC decay · {', '.join(str(a) for a in alerts[:3])} "
                "— review timing/signal weights (advisory)"
            )
    except Exception:
        logger.debug("ml_advisory feature_ic failed", exc_info=True)

    try:
        from src.engines.self_learning import get_calibration_status

        cal = get_calibration_status()
        payload["calibration"] = cal
        if cal.get("alert"):
            payload["active"] = True
            brier = cal.get("brier_score")
            lines.append(
                f"Calibration drift · Brier {brier} — confidence may be overstated"
            )
    except Exception:
        logger.debug("ml_advisory calibration failed", exc_info=True)

    try:
        from src.engines.learning_loop import LearningLoopPipeline

        loop = LearningLoopPipeline()
        summary = loop.summary()
        payload["learning_loop"] = summary
        total = int(summary.get("total_trades") or 0)
        if total >= 5:
            payload["active"] = True
            wr = float(summary.get("win_rate") or 0) * 100
            lines.append(
                f"Learning loop · {total} closed trades, {wr:.0f}% win rate "
                f"({'trained' if summary.get('meta_ensemble_trained') else 'warming'})"
            )
        elif total > 0:
            lines.append(
                f"Learning loop warming · {total} trades "
                f"(need ≥30 for self-learn adjustments)"
            )
    except Exception:
        logger.debug("ml_advisory learning_loop failed", exc_info=True)

    try:
        from src.engines.thompson_sizing import get_thompson_engine

        eng = get_thompson_engine()
        arms = eng.get_all_arms() if eng else []
        payload["thompson_arm_count"] = len(arms)
        if len(arms) >= 3:
            payload["active"] = True
            lines.append(
                f"Thompson sizing · {len(arms)} strategy×regime arms active (1R advise uses this)"
            )
    except Exception:
        logger.debug("ml_advisory thompson failed", exc_info=True)

    payload["lines"] = lines[:5]
    payload["status"] = "active" if payload["active"] else ("warming" if lines else "inactive")
    return payload
