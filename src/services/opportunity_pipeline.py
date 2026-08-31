"""Shared opportunity pipeline — quality, IO/Alpha enrichment, verdict (rank ≠ deploy)."""

from __future__ import annotations

import logging
from datetime import datetime, timezone
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


def _attach_attribution_to_rows(rows: List[Any]) -> List[Any]:
    """CCX-005 — decision_id + attribution_root_ref on every board row."""
    from src.services.attribution_tree import enrich_board_row_attribution

    out: List[Any] = []
    for row in rows:
        if isinstance(row, dict) and row.get("ticker"):
            out.append(enrich_board_row_attribution(row))
        else:
            out.append(row)
    return out


def _attach_provenance_to_rows(
    rows: List[Any],
    *,
    source: str,
    as_of: str,
    mode: str,
    data_stale: bool,
) -> List[Any]:
    """CCX-006 — mandatory source/as_of/mode on scored rows."""
    from src.services.provenance_contract import enrich_row_provenance

    out: List[Any] = []
    for row in rows:
        if isinstance(row, dict) and row.get("ticker"):
            enriched = enrich_row_provenance(
                row,
                source=str(row.get("source") or source)[:64],
                as_of=str(row.get("as_of") or as_of),
                mode=str(row.get("mode") or row.get("data_mode") or mode)[:32],
            )
            if data_stale:
                enriched["data_stale"] = True
            out.append(enriched)
        else:
            out.append(row)
    return out


def _resolve_deploy_open(payload: Dict[str, Any], tradeability: str) -> bool:
    ss = payload.get("system_state") or {}
    if "deploy_open" in ss:
        return bool(ss["deploy_open"])
    board = payload.get("decision_board") or {}
    if "deploy_open" in board:
        return bool(board["deploy_open"])
    da = payload.get("decision_authority") or {}
    if da.get("deploy_open") is not None:
        return bool(da["deploy_open"])
    tb = str(tradeability).upper()
    if tb in ("WAIT", "NO_TRADE") or da.get("gates_active"):
        return False
    return bool(da.get("authority_level") == "deploy")


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
        prov_as_of = str(
            out.get("as_of")
            or (out.get("brief_context") or {}).get("as_of")
            or datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")
        )
        prov_mode = "STALE" if data_stale else str(out.get("mode") or out.get("data_mode") or "LIVE")
        for key in _row_lists(out):
            rows = out.get(key)
            if isinstance(rows, list) and rows:
                out[key] = _attach_attribution_to_rows(rows)
                out[key] = _attach_provenance_to_rows(
                    out[key],
                    source=source,
                    as_of=prov_as_of,
                    mode=prov_mode,
                    data_stale=data_stale,
                )
        if out.get("opportunities") and not out.get("top_ranked"):
            out["top_ranked"] = out["opportunities"]
        out = attach_opportunity_verdict_to_payload(out)
    except Exception:
        logger.debug("opportunity_pipeline quality/verdict failed (%s)", source, exc_info=True)

    try:
        from src.services.score_families import (
            attach_score_families_disagreement_to_rows,
            build_score_families_summary,
            build_score_reconciliation,
        )

        deploy_open = _resolve_deploy_open(out, tb)
        for key in _row_lists(out):
            rows = out.get(key)
            if isinstance(rows, list) and rows:
                out[key] = attach_score_families_disagreement_to_rows(
                    rows,
                    deploy_open=deploy_open,
                    tradeability=tb,
                    brief_stale=brief_stale,
                )
        primary = list(
            out.get("top_ranked") or out.get("top_5") or out.get("opportunities") or []
        )
        out["score_families_summary"] = build_score_families_summary(
            primary,
            deploy_open=deploy_open,
            tradeability=tb,
            brief_stale=brief_stale,
        )
        out["score_reconciliation"] = build_score_reconciliation(
            primary,
            deploy_open=deploy_open,
            tradeability=tb,
            brief_stale=brief_stale,
            cross_asset=out.get("cross_asset_confirmation"),
        )
    except Exception:
        logger.debug("opportunity_pipeline score_families failed (%s)", source, exc_info=True)

    if attach_board:
        try:
            from src.services.decision_board_service import attach_decision_board

            attach_decision_board(out, ops=ops, source=source)
        except Exception:
            logger.debug("opportunity_pipeline board attach failed (%s)", source, exc_info=True)

    out["pipeline_source"] = source
    return out
