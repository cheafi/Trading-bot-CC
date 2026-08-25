"""Shared opportunity pipeline — quality, IO/Alpha enrichment, verdict (rank ≠ deploy)."""

from __future__ import annotations

import logging
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)

_ROW_KEYS = ("opportunities", "near_miss", "near_miss_rows", "top_ranked", "top_5")


def _resolve_tradeability(payload: Dict[str, Any]) -> str:
    ba = payload.get("best_action") or {}
    tb = ba.get("tradeability") or payload.get("tradeability") or ""
    if not tb:
        ss = payload.get("system_state") or {}
        tb = ss.get("tradeability") or ""
    if not tb:
        td = payload.get("todays_decision") or {}
        tb = td.get("tradeability") or "WAIT"
    return str(tb).upper()


def _resolve_index_regime(payload: Dict[str, Any]) -> Optional[Dict[str, Any]]:
    for key in ("index_regime_summary", "index_regime"):
        val = payload.get(key)
        if isinstance(val, dict) and val:
            return val
    return None


def _resolve_stale_flags(payload: Dict[str, Any]) -> tuple[bool, bool]:
    brief_ctx = payload.get("brief_context") or {}
    data_stale = bool(
        payload.get("data_stale")
        or payload.get("scanner_degraded")
        or payload.get("compressed")
        or payload.get("stale")
    )
    brief_stale = bool(
        brief_ctx.get("brief_stale")
        or payload.get("brief_stale")
        or payload.get("from_brief")
        or payload.get("brief_fallback")
    )
    return data_stale, brief_stale


def _row_lists(payload: Dict[str, Any]) -> List[str]:
    return [k for k in _ROW_KEYS if payload.get(k)]


def finalize_opportunity_pipeline(
    payload: Dict[str, Any],
    *,
    source: str = "unknown",
    index_regime: Optional[Dict[str, Any]] = None,
    tradeability: str = "",
    run_id: Optional[str] = None,
    attach_board: bool = False,
    ops: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    """Apply quality attach, IO/Alpha enrich, and opportunity verdict consistently."""
    out = dict(payload)
    tb = str(tradeability or _resolve_tradeability(out)).upper()
    idx = index_regime if index_regime is not None else _resolve_index_regime(out)
    data_stale, brief_stale = _resolve_stale_flags(out)

    try:
        from src.services.cost_adjusted_ranker import enrich_opportunity_rows

        for key in _row_lists(out):
            rows = out.get(key)
            if isinstance(rows, list) and rows:
                out[key] = enrich_opportunity_rows(
                    rows,
                    index_regime=idx,
                    tradeability=tb,
                    run_id=run_id,
                )
    except Exception:
        logger.debug("opportunity_pipeline enrich failed (%s)", source, exc_info=True)

    try:
        from src.services.opportunity_quality import (
            attach_quality_to_rows,
            attach_opportunity_verdict_to_payload,
            resolve_brief_stale_context,
        )

        if not out.get("brief_context"):
            out["brief_context"] = resolve_brief_stale_context(
                used_brief_fallback=bool(out.get("from_brief") or out.get("brief_fallback")),
            )
        out["data_stale"] = data_stale
        out["brief_stale"] = brief_stale
        for key in _row_lists(out):
            rows = out.get(key)
            if isinstance(rows, list) and rows:
                out[key] = attach_quality_to_rows(
                    rows,
                    data_stale=data_stale,
                    brief_stale=brief_stale,
                )
        if out.get("opportunities") and not out.get("top_ranked"):
            out["top_ranked"] = out["opportunities"]
        out = attach_opportunity_verdict_to_payload(out)
    except Exception:
        logger.debug("opportunity_pipeline quality/verdict failed (%s)", source, exc_info=True)

    if attach_board:
        try:
            from src.services.decision_board_service import attach_decision_board

            attach_decision_board(out, ops=ops, source=source)
        except Exception:
            logger.debug("opportunity_pipeline board attach failed (%s)", source, exc_info=True)

    out["pipeline_source"] = source
    return out
