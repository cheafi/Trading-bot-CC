"""
Learning loop service scaffold — bridges closed trades to opportunity quality.

Delegates persistence to engines.learning_loop when available; otherwise no-ops.
"""

from __future__ import annotations

from typing import Any, Dict, List, Optional

from src.services.opportunity_quality import OpportunityQualityScore, score_opportunity


def ingest_closed_trade(trade: Dict[str, Any]) -> Dict[str, Any]:
    """Record a closed trade for future weight adaptation (stub)."""
    ticker = str(trade.get("ticker") or "")
    quality = score_opportunity(ticker=ticker, trade=trade)
    return {
        "accepted": bool(ticker),
        "quality": quality.to_dict(),
        "learning_applied": False,
        "note": "Learning loop scaffold — outcome logged only",
    }


def summarize_learning_window(
    trades: Optional[List[Dict[str, Any]]] = None,
    *,
    window_days: int = 30,
) -> Dict[str, Any]:
    """Aggregate learning-window stats for Ops / Strategy Lab surfaces."""
    rows = trades or []
    scores = [score_opportunity(ticker=t.get("ticker", ""), trade=t) for t in rows]
    composites = [s.composite for s in scores]
    avg = sum(composites) / len(composites) if composites else 0.0
    return {
        "window_days": int(window_days),
        "sample_size": len(rows),
        "avg_composite": round(avg, 2),
        "ready_for_ui": len(rows) >= 5,
        "status": "scaffold",
        "top_tags": ["scaffold"],
    }


def bridge_to_engine_pipeline(trade: Dict[str, Any]) -> Optional[Dict[str, Any]]:
    """Optional hook into engines.learning_loop — safe import, no crash if missing."""
    try:
        from src.engines.learning_loop import LearningLoopPipeline

        pipe = LearningLoopPipeline()
        if hasattr(pipe, "process_trade_dict"):
            return pipe.process_trade_dict(trade)  # type: ignore[attr-defined]
    except Exception:
        return None
    return None
