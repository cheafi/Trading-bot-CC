"""Feed MetaEnsemble from backtest / signal track record (research weights only)."""

from __future__ import annotations

import logging
from typing import Any

logger = logging.getLogger(__name__)


def apply_backtrader_outcomes(
    backtest: dict[str, Any],
    *,
    ticker: str,
    strategy_id: str = "backtrader_sma",
) -> dict[str, Any]:
    """Update ensemble from aggregate backtest stats — does not write closed_trades.jsonl."""
    if not backtest.get("ok"):
        return {"ok": False, "reason": "backtest_not_ok"}

    try:
        from src.engines.meta_ensemble import MetaEnsemble

        ensemble = MetaEnsemble()
    except Exception as exc:
        logger.debug("MetaEnsemble unavailable: %s", exc)
        return {"ok": False, "reason": "ensemble_unavailable"}

    ret = float(backtest.get("return_pct") or 0)
    win_rate = float(backtest.get("win_rate") or 50)
    component_scores = {
        "trend": min(1.0, max(0.0, ret / 20.0 + 0.5)),
        "momentum": min(1.0, max(0.0, win_rate / 100.0)),
        "mean_reversion": 0.5,
        "breakout": 0.5,
    }
    try:
        ensemble.record_outcome(
            component_scores=component_scores,
            pnl_pct=ret,
            r_multiple=ret / 5.0,
            regime_label="research",
            strategy_id=f"research_{strategy_id}",
        )
    except Exception as exc:
        logger.warning("ensemble record_outcome failed: %s", exc)
        return {"ok": False, "reason": "record_failed"}

    return {
        "ok": True,
        "ticker": ticker,
        "strategy_id": strategy_id,
        "ensemble_samples": getattr(ensemble, "sample_count", None),
        "ensemble_trained": getattr(ensemble, "is_trained", False),
        "note": "Research-only weight nudge from backtest aggregate",
    }
