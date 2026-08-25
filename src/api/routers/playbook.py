"""
CC — Playbook & Scanner API Router
=====================================
Decision-oriented endpoints for the upgraded platform.

Endpoints:
  GET  /api/v7/playbook/today       — Today's regime + playbook
  GET  /api/v7/playbook/ranked      — 3-layer ranked opportunities
  GET  /api/v7/playbook/scanners    — Scanner matrix results
  GET  /api/v7/playbook/vcp/{ticker} — VCP intelligence for ticker
  GET  /api/v7/playbook/dossier/{ticker} — Full symbol dossier
  GET  /api/v7/playbook/no-trade    — Current no-trade / avoid list
"""

from __future__ import annotations

import asyncio
import logging
import statistics
import time
from typing import Any, Callable, Dict, List

from fastapi import APIRouter, Depends, Query, Request

from src.api.deps import verify_api_key

from src.core.stock_universe import (
    OPPORTUNITY_COVERAGE_UNIVERSE,
    RS_UNIVERSE,
    rs_sector_for,
)
from src.scanners.intl_universe import (
    AU_TICKERS,
    CRYPTO_TICKERS,
    HK_TICKERS,
    IN_TICKERS,
    JP_TICKERS,
    KR_TICKERS,
    TW_TICKERS,
)
from src.scanners.us_universe import US_UNIVERSE

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/v7/playbook", tags=["playbook"])

_RANKED_CACHE_TTL = 10 * 60
_RANKED_STALE_SERVE_TTL = 30 * 60
_RANKED_LOAD_TIMEOUT_SECONDS = 15.0
_RANKED_TIMEOUT_SECONDS = 30.0
_RANKED_CACHE_MAX_KEYS = 32
_RS_RANKING_CACHE_MAX_KEYS = 16
_ranked_cache: Dict[str, Dict[str, Any]] = {}
_ranked_refreshing: set[str] = set()
_FLOW_CACHE_TTL = 10 * 60
_FLOW_LOAD_TIMEOUT_SECONDS = 2.5
_flow_cache: Dict[str, Any] = {"ts": 0.0, "data": None}
_RS_RANKING_CACHE_TTL = 5 * 60
_rs_ranking_cache: Dict[str, Dict[str, Any]] = {}
_rs_ranking_refreshing: set[str] = set()
_SCANNER_SIGNAL_UNIVERSE_TARGET = 3000
_SCANNER_DISCOVERY_EXTRA_TICKERS = [
    "BUG",
    "FDN",
    "PNQI",
    "IYR",
    "PAVE",
    "SPHB",
    "SPHQ",
]
_SCANNER_DISCOVERY_UNIVERSE = list(
    dict.fromkeys(
        list(OPPORTUNITY_COVERAGE_UNIVERSE)
        + list(US_UNIVERSE)
        + list(HK_TICKERS)
        + list(JP_TICKERS)
        + list(KR_TICKERS)
        + list(TW_TICKERS)
        + list(AU_TICKERS)
        + list(IN_TICKERS)
        + list(CRYPTO_TICKERS)
        + _SCANNER_DISCOVERY_EXTRA_TICKERS
    )
)


# ── Real data access ─────────────────────────────────────────────────


async def _real_regime() -> Dict[str, Any]:
    """Get real regime — uses RegimeService (no import from main.py)."""
    try:
        from src.services.regime_service import RegimeService  # noqa: PLC0415

        state_dict = await asyncio.to_thread(RegimeService.get)
        return {
            "should_trade": state_dict.get("should_trade", True),
            "trend": state_dict.get("trend", "sideways"),
            "vix": state_dict.get("vix", 18.0),
            "macro_trend": state_dict.get("macro_trend", "neutral"),
            "macro_event_nearby": state_dict.get("macro_event_nearby", False),
            "confidence": state_dict.get("confidence", 0.5),
        }
    except Exception as e:
        logger.warning("Regime fallback: %s", e)
        return {
            "should_trade": True,
            "trend": "NEUTRAL",
            "vix": 18.5,
            "macro_trend": "neutral",
            "macro_event_nearby": False,
        }


async def _real_signals(
    *,
    scan_fn: Callable[..., Any] | None = None,
) -> List[Dict[str, Any]]:
    """Pipeline-ready signals — normalized brief, optional live scan top-up."""
    from src.services.playbook_signal_universe import load_playbook_signals

    signals, _meta = await load_playbook_signals(scan_fn=scan_fn)
    return signals


def _brief_row_to_scanner_signal(row: Dict[str, Any]) -> Dict[str, Any]:
    """Normalize morning-brief rows for scanner_matrix heuristics."""
    from src.services.playbook_signal_universe import normalize_brief_row

    return normalize_brief_row(row)


async def _scanner_signal_universe(
    *,
    scan_fn: Callable[..., Any] | None = None,
) -> tuple[List[Dict[str, Any]], str]:
    """
    Signals for scanner hub — brief first, then RS default pool.

    Returns (signals, universe_label).
    """
    signals = await _real_signals(scan_fn=scan_fn)
    if signals:
        pooled: List[Dict[str, Any]] = list(signals)
        seen = {str((row or {}).get("ticker") or "").strip().upper() for row in pooled}
        for ticker in _SCANNER_DISCOVERY_UNIVERSE:
            if len(pooled) >= _SCANNER_SIGNAL_UNIVERSE_TARGET:
                break
            tk = str(ticker or "").strip().upper()
            if not tk or tk in seen:
                continue
            pooled.append(
                {
                    "ticker": tk,
                    "score": 5.0,
                    "strategy": "default",
                    "pattern": "universe",
                }
            )
            seen.add(tk)
        label = "watchlist" if len(pooled) <= 50 else "broad_universe"
        return pooled, label

    try:
        from src.services.brief_data_service import load_brief  # noqa: PLC0415

        brief = await asyncio.to_thread(load_brief)
        pooled: List[Dict[str, Any]] = []
        for section in (
            "actionable",
            "watch",
            "review",
            "monitor",
            "pilot",
            "near_miss",
            "candidates",
        ):
            for row in brief.get(section) or []:
                sig = _brief_row_to_scanner_signal(row)
                if sig:
                    pooled.append(sig)
        if pooled:
            return pooled, "watchlist"
    except Exception as exc:
        logger.debug("Scanner brief pool fallback: %s", exc)

    default = [
        {"ticker": t, "score": 5.0, "strategy": "default", "pattern": "universe"}
        for t in _SCANNER_DISCOVERY_UNIVERSE[:_SCANNER_SIGNAL_UNIVERSE_TARGET]
    ]
    return default, "synthetic_default"


def _get_pipeline():
    """Lazy import to avoid circular deps."""
    from src.engines.sector_pipeline import SectorPipeline

    return SectorPipeline()


def _get_vcp():
    from src.engines.vcp_intelligence import VCPIntelligence

    return VCPIntelligence()


def _get_scanner():
    from src.engines.scanner_matrix import ScannerMatrix

    return ScannerMatrix()


def _ranked_cache_key(limit: int, action: str | None, sector: str | None) -> str:
    return f"{limit}:{(action or '').upper()}:{(sector or '').upper()}"


def _get_ranked_cached(key: str, *, allow_stale: bool = False) -> Dict[str, Any] | None:
    entry = _ranked_cache.get(key)
    if not entry:
        return None
    age = time.time() - entry["ts"]
    max_age = _RANKED_STALE_SERVE_TTL if allow_stale else _RANKED_CACHE_TTL
    if age < max_age:
        return {
            **entry["data"],
            "cached": True,
            "stale": age >= _RANKED_CACHE_TTL,
            "age_seconds": int(age),
        }
    return None


def _set_ranked_cached(key: str, data: Dict[str, Any]) -> None:
    _ranked_cache[key] = {"data": data, "ts": time.time()}
    if len(_ranked_cache) > _RANKED_CACHE_MAX_KEYS:
        oldest = min(_ranked_cache.items(), key=lambda item: item[1]["ts"])[0]
        if oldest != key:
            _ranked_cache.pop(oldest, None)


def _rs_ranking_cache_key(sector: str | None, cap: str | None, limit: int) -> str:
    return f"{(sector or '').upper()}:{(cap or '').upper()}:{limit}"


def _get_rs_ranking_cached(key: str) -> Dict[str, Any] | None:
    entry = _rs_ranking_cache.get(key)
    if not entry:
        return None
    age = time.time() - entry["ts"]
    if age < _RS_RANKING_CACHE_TTL:
        return {**entry["data"], "cached": True, "age_seconds": int(age)}
    return None


def _set_rs_ranking_cached(key: str, data: Dict[str, Any]) -> None:
    _rs_ranking_cache[key] = {"data": data, "ts": time.time()}
    if len(_rs_ranking_cache) > _RS_RANKING_CACHE_MAX_KEYS:
        oldest = min(_rs_ranking_cache.items(), key=lambda item: item[1]["ts"])[0]
        _rs_ranking_cache.pop(oldest, None)


def _brief_rs_ranking_fallback(
    limit: int, sector: str | None = None, cap: str | None = None
) -> Dict[str, Any]:
    if cap:
        return {
            "count": 0,
            "rankings": [],
            "sector_rs": [],
            "breakouts": [],
            "breakdowns": [],
            "cached": False,
            "stale": True,
            "refreshing": True,
            "source": "brief_rs_fallback",
            "warning": "live RS ranking is warming; no stale cap-specific fallback available",
        }
    try:
        from src.services.brief_data_service import load_brief  # noqa: PLC0415

        brief = load_brief()
    except Exception as exc:
        logger.warning("RS brief fallback unavailable: %s", exc)
        brief = {}

    rows = []
    for item in [*(brief.get("watch") or []), *(brief.get("actionable") or [])]:
        item_sector = item.get("sector") or _SECTOR_MAP.get(item.get("ticker", ""), "")
        if sector and str(item_sector).upper() != sector.upper():
            continue
        rs_score = float(item.get("rs_score") or item.get("score") or 0.0)
        rows.append(
            {
                "ticker": item.get("ticker") or item.get("symbol"),
                "sector": item_sector,
                "market_cap": "LARGE",
                "rs_1w": round(rs_score * 0.98, 1),
                "rs_1m": rs_score,
                "rs_3m": round(rs_score * 1.02, 1),
                "rs_6m": round(rs_score * 0.95, 1),
                "rs_change_1w": 0.0,
                "rs_change_1m": 0.0,
                "rs_composite": rs_score,
                "rs_percentile": min(99, max(1, int(rs_score))),
                "status": (
                    "LEADER"
                    if str(item.get("conviction") or "").upper() in {"LEADER", "TRADE"}
                    else "WATCH"
                ),
                "trend": "STALE",
                "price": item.get("price") or item.get("entry"),
                "change_pct": 0,
                "source": "stale-brief-watchlist",
            }
        )
    rows = sorted(rows, key=lambda row: row.get("rs_composite") or 0, reverse=True)[
        :limit
    ]
    return {
        "count": len(rows),
        "rankings": rows,
        "stale_watchlist": rows,
        "sector_rs": [],
        "breakouts": [],
        "breakdowns": [],
        "cached": False,
        "stale": True,
        "refreshing": True,
        "source": "brief_rs_fallback",
        "warning": "live RS ranking is warming; stale watchlist is NOT actionable",
    }


async def _compute_rs_ranking_response(
    limit: int, sector: str | None = None, cap: str | None = None
) -> Dict[str, Any]:
    engine = _get_rs_engine()
    universe = await _build_rs_universe()
    benchmark = await _build_benchmark()

    entries = engine.rank(universe, benchmark)

    if sector:
        entries = [e for e in entries if e.sector.upper() == sector.upper()]
    if cap:
        entries = [e for e in entries if e.market_cap.upper() == cap.upper()]

    sector_rs = engine.get_sector_rankings(entries)
    breakouts = engine.get_breakouts(entries)
    breakdowns = engine.get_breakdowns(entries)

    return {
        "count": min(limit, len(entries)),
        "rankings": [e.to_dict() for e in entries[:limit]],
        "sector_rs": [s.to_dict() for s in sector_rs],
        "breakouts": [e.to_dict() for e in breakouts[:10]],
        "breakdowns": [e.to_dict() for e in breakdowns[:10]],
        "cached": False,
        "stale": False,
        "refreshing": False,
    }


async def _refresh_rs_ranking_cache(
    key: str, limit: int, sector: str | None = None, cap: str | None = None
) -> None:
    if key in _rs_ranking_refreshing:
        return
    _rs_ranking_refreshing.add(key)
    try:
        response = await _compute_rs_ranking_response(limit, sector, cap)
        _set_rs_ranking_cached(key, response)
    except Exception as exc:
        logger.warning("RS ranking background refresh failed: %s", exc)
    finally:
        _rs_ranking_refreshing.discard(key)


def _finalize_ranked_response(
    data: Dict[str, Any],
    *,
    from_live: bool = False,
    limit: int = 30,
    action: str | None = None,
    sector: str | None = None,
) -> Dict[str, Any]:
    """Attach best_action, board_mode, and overlap metadata."""
    if not data.get("best_action"):
        from src.services.best_action import enrich_ranked_payload

        data = enrich_ranked_payload(data)
    from src.services.playbook_board_fallback import (
        annotate_board_mode,
        board_has_content,
        supplement_zero_deploy_board,
    )

    annotate_board_mode(data, from_live=from_live)
    data = supplement_zero_deploy_board(data, limit, action=action, sector=sector)
    if not board_has_content(data):
        fallback = _brief_ranked_fallback(
            limit, action, sector, reason="board empty after live scan"
        )
        if board_has_content(fallback):
            data = {
                **fallback,
                **{
                    k: v
                    for k, v in data.items()
                    if k
                    in (
                        "best_action",
                        "surface_authority",
                        "restraint",
                        "warning",
                    )
                    and v
                },
            }
            annotate_board_mode(data, from_live=False)
    funnel = data.get("filter_funnel") or {}
    opps = data.get("opportunities") or []
    near = data.get("near_miss") or []
    deploy = int(funnel.get("execution_ready_setups") or 0)
    ba = data.get("best_action") or {}
    tb = ba.get("tradeability") or "WAIT"
    try:
        from src.services.decision_truth_model import (
            normalize_playbook_funnel,
            playbook_scan_ranked_count,
            rejection_clusters_reconcile_note,
        )
        from src.services.today_insights import build_unlock_deploy

        funnel = normalize_playbook_funnel(funnel, opportunities=opps, near_miss=near)
        data["filter_funnel"] = funnel
        wq = int(funnel.get("watch_qualified_setups") or 0)
        deploy = int(funnel.get("deploy_qualified_setups") or 0)
        tb = ba.get("tradeability") or "WAIT"
        scanner_degraded = bool(data.get("compressed") or data.get("stale"))
        sr = playbook_scan_ranked_count(funnel, opportunity_count=len(opps))
        data["unlock_deploy"] = build_unlock_deploy(
            tradeability=tb,
            should_trade=tb not in ("NO_TRADE", "WAIT"),
            watch_qualified_count=wq,
            deployable_count=deploy,
            scan_ranked_count=sr,
            scanner_degraded=scanner_degraded,
            execution_readiness=ba.get("execution_readiness") or {},
        )
        note = rejection_clusters_reconcile_note(
            data.get("rejection_clusters"), data.get("avoid_grouped")
        )
        if note:
            data["rejection_clusters_note"] = note
    except Exception:
        pass
    try:
        from src.services.surface_authority import resolve_authority

        data["surface_authority"] = resolve_authority(
            "playbook",
            tradeability=tb,
            board_mode=data.get("board_mode"),
            deployable_count=deploy,
        )
    except Exception:
        pass
    try:
        from src.services.anti_overtrading import restraint_from_today_context

        opps = data.get("opportunities") or []
        pilot_n = sum(1 for r in opps if (r.get("action") or "").upper() == "PILOT")
        data["restraint"] = restraint_from_today_context(
            tradeability=tb,
            deployable_count=deploy,
            pilot_ready_count=pilot_n,
            opportunities=opps,
        )
    except Exception:
        pass
    try:
        from src.services.decision_truth_model import finalize_ranked_payload_authority
        from src.services.score_families import build_score_reconciliation

        data = finalize_ranked_payload_authority(data)
        opps = data.get("opportunities") or []
        data["score_reconciliation"] = build_score_reconciliation(
            opps,
            contradiction_flags=[
                c
                for r in opps[:12]
                if str(r.get("conflict_level") or "").upper() == "HIGH"
                for c in [f"{r.get('ticker')}: high conflict"]
            ],
        )
    except Exception:
        pass
    try:
        from src.services.opportunity_quality import (
            attach_quality_to_rows,
            build_opportunity_verdict,
            resolve_brief_stale_context,
        )

        scanner_degraded = bool(data.get("compressed") or data.get("stale"))
        brief_ctx = resolve_brief_stale_context(
            used_brief_fallback=bool(data.get("from_brief") or data.get("brief_fallback")),
        )
        _brief_stale = bool(brief_ctx.get("brief_stale"))
        for key in ("opportunities", "near_miss", "near_miss_rows"):
            rows = data.get(key)
            if rows:
                data[key] = attach_quality_to_rows(
                    rows,
                    data_stale=scanner_degraded,
                    brief_stale=_brief_stale,
                )
        data["brief_context"] = brief_ctx
        data["data_stale"] = scanner_degraded
        data["brief_stale"] = _brief_stale
        data["top_ranked"] = data.get("opportunities") or []
        data["opportunity_verdict"] = build_opportunity_verdict(data)
    except Exception:
        pass
    try:
        from src.services.cc_state import build_cc_state

        ba = data.get("best_action") or {}
        data["cc_state"] = build_cc_state(
            tradeability=tb,
            should_trade=tb not in ("NO_TRADE", "WAIT"),
            decision_authority=data.get("decision_authority") or {},
            execution_readiness=ba.get("execution_readiness") or {},
            surface_authority=data.get("surface_authority"),
            trust=data.get("trust") if isinstance(data.get("trust"), dict) else None,
        )
    except Exception:
        pass
    try:
        from src.services.playbook_operator_intelligence import enrich_playbook_payload

        data = enrich_playbook_payload(data)
    except Exception:
        pass
    try:
        from src.services.cc_state import attach_page_capability, attach_system_state

        data = attach_system_state(data)
        data = attach_page_capability(data, "signals")
    except Exception:
        pass
    try:
        from src.services.decision_board_service import attach_decision_board

        attach_decision_board(data, source="playbook")
    except Exception:
        pass
    return data


def _brief_ranked_fallback(
    limit: int,
    action: str | None = None,
    sector: str | None = None,
    *,
    reason: str = "ranked pipeline unavailable",
) -> Dict[str, Any]:
    from src.services.playbook_board_fallback import build_compressed_fallback

    return build_compressed_fallback(limit, action, sector, reason=reason)


def _get_flow_cached(*, allow_stale: bool = False) -> Dict[str, Any] | None:
    data = _flow_cache.get("data")
    if not data:
        return None
    age = time.time() - float(_flow_cache.get("ts") or 0)
    if allow_stale or age < _FLOW_CACHE_TTL:
        return {
            **data,
            "cached": True,
            "stale": age >= _FLOW_CACHE_TTL,
            "age_seconds": int(age),
        }
    return None


def _set_flow_cached(data: Dict[str, Any]) -> None:
    _flow_cache.update({"data": data, "ts": time.time()})


# ── Today / Playbook ─────────────────────────────────────────────────


@router.get("/today")
async def today_playbook() -> Dict[str, Any]:
    """Today's market regime, sector playbook, top 5, avoid list."""
    pipeline = _get_pipeline()

    regime = await _real_regime()
    signals = await _real_signals()

    results = pipeline.process_batch(signals, regime)

    # Top 5 by conviction
    top5 = []
    for i, r in enumerate(results[:5]):
        entry = {
            "rank": i + 1,
            "ticker": r.signal.get("ticker"),
            "sector": r.sector.sector_bucket.value,
            "theme": r.sector.theme,
            "action": r.decision.action,
            "grade": r.fit.grade,
            "confidence": round(r.confidence.final, 2),
            "why_now": r.explanation.why_now,
            # Phase 9 pass-through
            "structure": r.signal.get("structure"),
            "entry_quality": r.signal.get("entry_quality"),
            "earnings": r.signal.get("earnings"),
            "fundamentals": r.signal.get("fundamentals"),
            "portfolio_gate": r.signal.get("portfolio_gate"),
        }
        # Why This Not That — attach runner-up for comparison
        if i < len(results) - 1:
            nxt = results[i + 1]
            entry["runner_up"] = {
                "ticker": nxt.signal.get("ticker"),
                "score": round(nxt.confidence.final, 2),
                "reason": (
                    f"Higher conviction"
                    f" ({round(r.confidence.final, 2)}"
                    f" vs {round(nxt.confidence.final, 2)})"
                    + (
                        ", better sector fit (" + r.sector.sector_bucket.value + ")"
                        if r.sector.sector_bucket != nxt.sector.sector_bucket
                        else ""
                    )
                ),
            }
        top5.append(entry)

    # Avoid list
    avoid = [
        {
            "ticker": r.signal.get("ticker"),
            "reason": r.decision.rationale,
        }
        for r in results
        if r.decision.action == "NO_TRADE"
    ]

    # Sector playbook
    sector_summary = pipeline.get_sector_summary(results)
    action_summary = pipeline.get_action_summary(results)

    return {
        "regime": regime,
        "tradeability": "TRADE" if regime.get("should_trade") else "NO_TRADE",
        "sector_playbook": sector_summary,
        "action_summary": action_summary,
        "top_5": top5,
        "avoid_list": avoid[:10],
        "total_signals": len(results),
    }


def _ranked_fallback_chain(
    cache_key: str,
    limit: int,
    action: str | None,
    sector: str | None,
    *,
    reason: str,
) -> Dict[str, Any]:
    """Memory stale → disk snapshot → compressed → emergency."""
    from src.services.cc_live_policy import (
        build_live_unavailable_ranked,
        cc_live_data_only_enabled,
    )

    if cc_live_data_only_enabled():
        return build_live_unavailable_ranked(reason=reason)

    from src.services.playbook_board_fallback import (
        BOARD_MODE_EMERGENCY,
        build_emergency_response,
        load_playbook_snapshot,
        save_playbook_snapshot,
    )

    if stale := _get_ranked_cached(cache_key, allow_stale=True):
        return _finalize_ranked_response(
            {**stale, "warning": f"{reason} — serving cached board"},
            limit=limit,
            action=action,
            sector=sector,
        )
    if snap := load_playbook_snapshot(cache_key):
        _set_ranked_cached(cache_key, snap)
        return _finalize_ranked_response(
            {**snap, "warning": f"{reason} — serving last-good snapshot"},
            limit=limit,
            action=action,
            sector=sector,
        )
    fallback = _brief_ranked_fallback(limit, action, sector, reason=reason)
    if fallback.get("board_mode") == BOARD_MODE_EMERGENCY:
        emergency = build_emergency_response(reason=reason, detail=reason)
        _set_ranked_cached(cache_key, emergency)
        return _finalize_ranked_response(
            emergency, limit=limit, action=action, sector=sector
        )
    _set_ranked_cached(cache_key, fallback)
    save_playbook_snapshot(fallback, cache_key)
    return _finalize_ranked_response(
        {**fallback, "warning": f"{reason} — serving compressed fallback"},
        limit=limit,
        action=action,
        sector=sector,
    )


async def _compute_ranked_live(
    limit: int,
    action: str | None,
    sector: str | None,
    *,
    scan_fn: Callable[..., Any] | None = None,
) -> Dict[str, Any]:
    """Full live ranked pipeline."""
    from src.services.playbook_signal_universe import load_playbook_signals

    pipeline = _get_pipeline()
    regime, (signals, signal_meta) = await asyncio.wait_for(
        asyncio.gather(
            _real_regime(),
            load_playbook_signals(scan_fn=scan_fn),
        ),
        timeout=_RANKED_LOAD_TIMEOUT_SECONDS,
    )
    results = await asyncio.wait_for(
        asyncio.to_thread(pipeline.process_batch, signals, regime),
        timeout=_RANKED_TIMEOUT_SECONDS,
    )

    if action:
        results = [r for r in results if r.decision.action == action.upper()]
    if sector:
        sb = sector.upper()
        results = [r for r in results if r.sector.sector_bucket.value == sb]

    from src.services.decision_truth_model import (
        _PipelineWrap,
        build_avoid_grouped,
        build_honest_funnel,
        build_runner_up_comparison,
        enrich_opportunity_row,
        refine_action,
        sector_rank_adjustment,
    )
    from src.services.playbook_board_fallback import _rejection_clusters_from_grouped
    from src.services.today_insights import build_unlock_deploy

    sector_leaders: list = []
    sector_laggards: list = []
    if isinstance(regime, dict):
        sector_leaders = regime.get("sector_leaders") or []
        sector_laggards = regime.get("sector_laggards") or []

    def _rank_sort_key(res: Any) -> tuple:
        wrap = _PipelineWrap(res)
        act = refine_action(wrap)
        _ACTION_ORDER = {
            "TRADE": 0,
            "PILOT": 1,
            "WATCH": 2,
            "WAIT": 3,
            "AVOID": 4,
            "NO_TRADE": 5,
        }
        adj = sector_rank_adjustment(
            {
                "sector_type": res.sector.sector_bucket.value,
                "leader": res.sector.leader_status.value,
            },
            sector_leaders=sector_leaders,
            sector_laggards=sector_laggards,
        )
        return (
            _ACTION_ORDER.get(act, 9),
            -(float(res.fit.final_score) + adj),
        )

    results = sorted(results, key=_rank_sort_key)

    rows = []
    for r in results[:limit]:
        row = {
            "ticker": r.signal.get("ticker"),
            "sector_type": r.sector.sector_bucket.value,
            "theme": r.sector.theme,
            "setup": r.signal.get("strategy", ""),
            "stage": r.sector.sector_stage.value,
            "leader": r.sector.leader_status.value,
            "score": round(r.fit.final_score, 1),
            "grade": r.fit.grade,
            "thesis_conf": round(r.confidence.thesis, 2),
            "timing_conf": round(r.confidence.timing, 2),
            "exec_conf": round(r.confidence.execution, 2),
            "data_conf": round(r.confidence.data, 2),
            "final_conf": round(r.confidence.final, 2),
            "action": r.decision.action,
            "risk_level": r.decision.risk_level,
            "entry_price": r.signal.get("entry_price"),
            "target_price": r.signal.get("target_price"),
            "stop_price": r.signal.get("stop_price"),
            "risk_reward": r.signal.get("risk_reward"),
            "entry_trigger": r.decision.entry_trigger,
            "why_now": (r.explanation.why_now if r.explanation else None),
            "why_not": (r.explanation.why_not_stronger if r.explanation else None),
            "trigger_quality": (
                r.fit.setup_quality if hasattr(r.fit, "setup_quality") else 0
            ),
            "relative_strength": (
                r.sector.relative_strength
                if hasattr(r.sector, "relative_strength")
                else 0
            ),
            "invalidation": (r.explanation.invalidation if r.explanation else None),
            "structure": r.signal.get("structure"),
            "entry_quality": r.signal.get("entry_quality"),
            "earnings": r.signal.get("earnings"),
            "fundamentals": r.signal.get("fundamentals"),
            "portfolio_gate": r.signal.get("portfolio_gate"),
        }
        if r.ranking:
            row["discovery_rank"] = r.ranking.discovery_rank
            row["action_rank"] = r.ranking.action_rank
            row["conviction_rank"] = r.ranking.conviction_rank
        if r.conflict:
            row["conflict_level"] = r.conflict.conflict_level
        row = enrich_opportunity_row(
            _PipelineWrap(r),
            row,
            sector_leaders=sector_leaders,
            sector_laggards=sector_laggards,
        )
        rows.append(row)

    for i, row in enumerate(rows):
        if i < len(rows) - 1:
            cmp_row = build_runner_up_comparison(row, rows[i + 1])
            if cmp_row:
                row["runner_up"] = cmp_row

    council_wraps = [_PipelineWrap(r) for r in results]
    funnel = build_honest_funnel(
        universe=len(signals) if signals else len(results),
        scanned=[{"score": r.fit.final_score} for r in results],
        council_results=council_wraps,
    )
    avoid_grouped = build_avoid_grouped(council_wraps)
    watch_qualified = int(funnel.get("watch_qualified_setups") or 0)
    deployable = int(funnel.get("deploy_qualified_setups") or 0)
    from src.services.decision_truth_model import (
        playbook_scan_ranked_count,
        rejection_clusters_reconcile_note,
    )

    rejection_clusters = _rejection_clusters_from_grouped(avoid_grouped)
    scan_ranked = playbook_scan_ranked_count(funnel, opportunity_count=len(rows))
    cluster_note = rejection_clusters_reconcile_note(rejection_clusters, avoid_grouped)

    return {
        "count": len(rows),
        "opportunities": rows,
        "cached": False,
        "stale": False,
        "source": "ranked_pipeline",
        "board_mode": "full_live",
        "filter_funnel": funnel,
        "avoid_grouped": avoid_grouped,
        "rejection_clusters": rejection_clusters,
        "rejection_clusters_note": cluster_note,
        "signal_universe": signal_meta,
        "unlock_deploy": build_unlock_deploy(
            tradeability="WAIT",
            should_trade=bool(regime.get("should_trade", True)),
            watch_qualified_count=watch_qualified,
            deployable_count=deployable,
            scan_ranked_count=scan_ranked,
            scanner_degraded=False,
        ),
    }


def _notify_live_ranked_scan(payload: Dict[str, Any], *, source: str) -> None:
    """Fire-and-forget Telegram alerts after a live ranked scan (non-fatal)."""
    try:
        from src.services.opportunity_telegram_alerts import notify_live_playbook_scan

        notify_live_playbook_scan(payload, source=source)
    except Exception as exc:
        logger.debug("Telegram opportunity notify skipped: %s", exc)


async def _refresh_ranked_cache(
    cache_key: str,
    limit: int,
    action: str | None,
    sector: str | None,
) -> None:
    if cache_key in _ranked_refreshing:
        return
    _ranked_refreshing.add(cache_key)
    try:
        from src.services.playbook_board_fallback import save_playbook_snapshot

        response = await _compute_ranked_live(limit, action, sector)
        response = _finalize_ranked_response(
            response, from_live=True, limit=limit, action=action, sector=sector
        )
        _set_ranked_cached(cache_key, response)
        save_playbook_snapshot(response, cache_key)
        _notify_live_ranked_scan(response, source="playbook_refresh")
    except Exception as exc:
        logger.warning("Ranked background refresh failed: %s", exc)
    finally:
        _ranked_refreshing.discard(cache_key)


async def warm_playbook_discovery_cache(app) -> None:
    """
    Prefetch Playbook ranked + RS ranking on API boot so first Discovery/Playbook
    load is not empty. Does not loosen deploy gates.
    """
    scan_fn = getattr(app.state, "scan_signals", None)
    cache_key = _ranked_cache_key(50, None, None)
    try:
        if not _get_ranked_cached(cache_key):
            response = await asyncio.wait_for(
                _compute_ranked_live(50, None, None, scan_fn=scan_fn),
                timeout=_RANKED_LOAD_TIMEOUT_SECONDS + _RANKED_TIMEOUT_SECONDS,
            )
            response = _finalize_ranked_response(response, from_live=True, limit=50)
            _set_ranked_cached(cache_key, response)
            from src.services.playbook_board_fallback import save_playbook_snapshot

            save_playbook_snapshot(response, cache_key)
            _notify_live_ranked_scan(response, source="playbook_prewarm")
            logger.info(
                "[Prewarm] Playbook ranked cache: %d opps, %d near-miss",
                len(response.get("opportunities") or []),
                len(response.get("near_miss") or []),
            )
        app.state.playbook_ranked_cache = _get_ranked_cached(cache_key) or {}
    except Exception as exc:
        logger.warning("[Prewarm] Playbook ranked warm failed (non-fatal): %s", exc)

    rs_key = _rs_ranking_cache_key(None, None, 50)
    if not _get_rs_ranking_cached(rs_key):
        asyncio.create_task(_refresh_rs_ranking_cache(rs_key, 50, None, None))
        fb = _brief_rs_ranking_fallback(50, None, None)
        if fb.get("stale_watchlist"):
            _set_rs_ranking_cached(rs_key, fb)
            logger.info(
                "[Prewarm] RS ranking brief fallback: %d leaders",
                len(fb.get("stale_watchlist") or []),
            )


# ── Ranked Opportunities ─────────────────────────────────────────────


@router.get("/ranked/snapshot")
async def ranked_snapshot(
    limit: int = Query(50, ge=1, le=100),
    action: str = Query(None),
    sector: str = Query(None),
    _: bool = Depends(verify_api_key),
) -> Dict[str, Any]:
    """Instant last-good board — memory or disk only, no live compute."""
    from src.services.cc_live_policy import (
        build_live_unavailable_ranked,
        cc_live_data_only_enabled,
    )
    from src.services.playbook_board_fallback import (
        BOARD_MODE_EMERGENCY,
        build_emergency_response,
    )

    if cc_live_data_only_enabled():
        return _finalize_ranked_response(
            build_live_unavailable_ranked(
                reason="live-only mode — snapshot endpoint disabled; use /ranked?refresh=true"
            ),
            limit=limit,
            action=action,
            sector=sector,
        )

    cache_key = _ranked_cache_key(limit, action, sector)
    if cached := _get_ranked_cached(cache_key, allow_stale=True):
        return _finalize_ranked_response(
            {**cached, "refreshing": False}, limit=limit, action=action, sector=sector
        )
    from src.services.playbook_board_fallback import load_playbook_snapshot

    if snap := load_playbook_snapshot(cache_key):
        return _finalize_ranked_response(
            {**snap, "refreshing": False}, limit=limit, action=action, sector=sector
        )
    fallback = _brief_ranked_fallback(
        limit, action, sector, reason="no cached playbook snapshot"
    )
    if fallback.get("board_mode") != BOARD_MODE_EMERGENCY:
        return _finalize_ranked_response(
            fallback, limit=limit, action=action, sector=sector
        )
    return _finalize_ranked_response(
        build_emergency_response(
            reason="No cached playbook snapshot yet",
            detail="Run ranked refresh or wait for the live pipeline to complete once.",
        ),
        limit=limit,
        action=action,
        sector=sector,
    )


@router.get("/ranked")
async def ranked_opportunities(
    request: Request,
    limit: int = Query(50, ge=1, le=100),
    action: str = Query(None, description="Filter by action"),
    sector: str = Query(None, description="Filter by sector bucket"),
    refresh: bool = Query(
        False, description="Skip stale snapshot fast-path and await live compute"
    ),
    _: bool = Depends(verify_api_key),
) -> Dict[str, Any]:
    """3-layer ranked opportunity board."""
    from src.services.cc_live_policy import cc_live_data_only_enabled
    from src.services.playbook_board_fallback import (
        board_has_content,
        load_playbook_snapshot,
        save_playbook_snapshot,
    )

    cache_key = _ranked_cache_key(limit, action, sector)
    live_only = cc_live_data_only_enabled()
    if cached := _get_ranked_cached(cache_key, allow_stale=not refresh):
        fresh_enough = not cached.get("stale")
        if not live_only or (
            cached.get("source") == "ranked_pipeline" and fresh_enough
        ):
            if cached.get("stale") and not refresh and not action and not sector:
                asyncio.create_task(
                    _refresh_ranked_cache(cache_key, limit, action, sector)
                )
                cached = {
                    **cached,
                    "refreshing": True,
                    "warning": cached.get("warning")
                    or "Serving cached board while live refresh runs",
                }
            return _finalize_ranked_response(
                cached, limit=limit, action=action, sector=sector
            )

    if not live_only and not refresh and not action and not sector:
        if snap := load_playbook_snapshot(cache_key):
            asyncio.create_task(_refresh_ranked_cache(cache_key, limit, action, sector))
            return _finalize_ranked_response(
                {
                    **snap,
                    "refreshing": True,
                    "warning": snap.get("warning")
                    or "Serving last-good board while live refresh runs",
                },
                limit=limit,
                action=action,
                sector=sector,
            )

    try:
        scan_fn = getattr(request.app.state, "scan_signals", None)
        response = await _compute_ranked_live(limit, action, sector, scan_fn=scan_fn)
        response = _finalize_ranked_response(
            response, from_live=True, limit=limit, action=action, sector=sector
        )
        if not board_has_content(response):
            return _ranked_fallback_chain(
                cache_key,
                limit,
                action,
                sector,
                reason="live pipeline returned no ranked rows",
            )
        _set_ranked_cached(cache_key, response)
        save_playbook_snapshot(response, cache_key)
        _notify_live_ranked_scan(response, source="playbook_ranked")
        return response
    except asyncio.TimeoutError:
        logger.warning("Ranked playbook timeout")
        return _ranked_fallback_chain(
            cache_key,
            limit,
            action,
            sector,
            reason="ranked pipeline timeout",
        )
    except Exception as e:
        import traceback

        traceback.print_exc()
        logger.warning("Ranked playbook fallback: %s", e)
        return _ranked_fallback_chain(
            cache_key,
            limit,
            action,
            sector,
            reason="ranked pipeline unavailable",
        )


# ── Scanner Hub ──────────────────────────────────────────────────────


def _scanner_hub_warming_payload(
    *,
    reason: str,
    universe_label: str = "warming",
    universe_size: int = 0,
) -> Dict[str, Any]:
    """Honest hub skeleton when matrix cannot run — never a blank Discovery tab."""
    from src.engines.scanner_matrix import DECISION_INTENT_ORDER  # noqa: PLC0415

    regime_note = "Hub warming"
    decision_intent = {
        intent: {
            "intent": intent,
            "count": 0,
            "probe_status": "warming",
            "regime_note": regime_note,
            "empty_why": (
                f"{reason} Scanner universe is warming — "
                "intent cards stay visible at 0 hits."
            ),
            "top_hits": [],
        }
        for intent in DECISION_INTENT_ORDER
    }
    return {
        "scanners": {},
        "category_summary": {},
        "decision_intent": decision_intent,
        "total_hits": 0,
        "universe_size": universe_size,
        "universe_label": universe_label,
        "merged_top_names": [],
        "discovery_verdict": {
            "best_scanner_today": None,
            "best_scanner_hits": 0,
            "best_confirmed_name": None,
            "best_speculative_name": None,
            "avoid_now_count": 0,
            "discovery_breadth": "0/5 categories active (warming)",
            "active_categories": 0,
            "total_unique_names": 0,
            "universe_size": universe_size,
            "regime": "—",
        },
        "scanner_overlap": {},
        "scanner_quality": {
            "label": "WARMING",
            "note": reason,
        },
        "diagnostics": {
            "last_run": None,
            "symbols_scanned": universe_size,
            "source": "warming",
            "data_freshness": "warming",
            "tradeability": None,
            "regime_trend": "—",
            "failures": [reason],
            "reason_no_hits": reason,
        },
        "research_note": (
            "Decision-intent scanners are research/supporting unless Playbook confirms. "
            "Hub is warming — zero hits is normal until signals or brief pool loads."
        ),
        "hub_status": "warming",
    }


def _scanner_hub_diagnostics(
    regime: Dict[str, Any],
    signals: List[Dict[str, Any]],
    *,
    universe_label: str = "",
) -> Dict[str, Any]:
    from datetime import datetime

    tradeability = str(
        regime.get("tradeability") or regime.get("regime_tradeability") or ""
    ).upper()
    signals_empty = len(signals) == 0
    if universe_label == "synthetic_default":
        reason_no_hits = (
            "Running on RS default pool — live brief/signal cache empty; "
            "hits are heuristic until upstream refreshes."
        )
    elif signals_empty:
        reason_no_hits = "Upstream signal cache empty — scanners run on default pool or brief watchlist."
    else:
        reason_no_hits = (
            "No names passed strict scanner thresholds for the selected filter."
        )
    if tradeability in ("WAIT", "NO_TRADE"):
        reason_no_hits = (
            f"Board gate {tradeability} — expect fewer or zero deploy-grade hits; "
            "discovery is research-only until Playbook confirms."
        )
    return {
        "last_run": regime.get("generated_at", datetime.now().isoformat() + "Z"),
        "symbols_scanned": len(signals) if signals else 0,
        "source": "playbook",
        "data_freshness": (
            "synthetic"
            if universe_label == "synthetic_default" or regime.get("synthetic")
            else "live"
        ),
        "universe_label": universe_label or None,
        "tradeability": tradeability or None,
        "regime_trend": str(regime.get("trend") or regime.get("label") or "—"),
        "failures": (
            ["No active signals produced by upstream"] if signals_empty else []
        ),
        "reason_no_hits": reason_no_hits,
    }


async def _scanner_rejection_preview(
    regime: Dict[str, Any],
    signals: List[Dict[str, Any]],
    *,
    limit: int = 5,
) -> List[Dict[str, Any]]:
    """Pipeline-blocked names for NO_TRADE intent (honest, not simulated)."""
    if not signals:
        return []
    try:
        from src.services.rejection_audit import enrich_no_trade_list  # noqa: PLC0415

        pipeline = _get_pipeline()
        results = pipeline.process_batch(signals[:80], regime)
        blocked = [
            r
            for r in results
            if r.decision.action in ("NO_TRADE", "EXIT", "REDUCE", "AVOID")
        ]
        rows, _ = enrich_no_trade_list(blocked, regime)
        preview: List[Dict[str, Any]] = []
        for row in rows[:limit]:
            preview.append(
                {
                    "ticker": row.get("ticker"),
                    "failed_rule": row.get("primary_blocker")
                    or row.get("reason")
                    or row.get("action"),
                    "score": row.get("timing_conf") or row.get("thesis_conf"),
                    "blocker_category": row.get("blocker_category"),
                }
            )
        return preview
    except Exception as e:
        logger.warning("Scanner rejection preview failed: %s", e)
        return []


def _discovery_brief_leader_rows(*, limit: int = 12) -> List[Dict[str, Any]]:
    """Research-only brief leaders when live scanner hits are empty."""
    from src.services.playbook_signal_universe import normalize_brief_row

    try:
        from src.services.brief_data_service import load_brief  # noqa: PLC0415

        brief = load_brief()
    except Exception:
        return []

    rows: List[Dict[str, Any]] = []
    seen: set[str] = set()
    for section in (
        "actionable",
        "watch",
        "review",
        "monitor",
        "pilot",
        "near_miss",
        "candidates",
    ):
        for raw in brief.get(section) or []:
            if not isinstance(raw, dict):
                continue
            sig = normalize_brief_row(raw)
            ticker = str(sig.get("ticker") or "").upper()
            if not ticker or ticker in seen:
                continue
            seen.add(ticker)
            rows.append(
                {
                    "ticker": ticker,
                    "overlap": 0,
                    "scanners": ["brief_cache"],
                    "categories": ["BRIEF"],
                    "max_score": round(float(sig.get("score") or 5.0), 1),
                    "avg_score": round(float(sig.get("score") or 5.0), 1),
                    "action": "WATCH",
                    "urgency": "LOW",
                    "confidence": 0.35,
                    "regime_alignment": "brief",
                    "why_flagged": f"Cached brief · {section}",
                    "status": "cached",
                    "score_display_mode": "fallback_rank",
                    "score_source": "brief-cache",
                    "score_display": "Cached leader",
                    "score_display_label": "Cached brief · research only",
                    "research_only": True,
                    "brief_section": section,
                }
            )
            if len(rows) >= limit:
                return rows
    return rows


def _enrich_discovery_zero_hits(
    payload: Dict[str, Any],
    *,
    regime: Dict[str, Any],
    scanner: Any,
) -> Dict[str, Any]:
    """Pad Discovery with honest cached brief leaders — no deploy authority."""
    if int(payload.get("total_hits") or 0) > 0:
        return payload
    cached = _discovery_brief_leader_rows(limit=12)
    if not cached:
        return payload

    payload = dict(payload)
    payload["cached_leaders"] = cached
    payload["hub_status"] = payload.get("hub_status") or "degraded"
    payload.setdefault(
        "research_note",
        "Live scanner produced zero hits — cached brief leaders shown (research only).",
    )
    merged = list(payload.get("merged_top_names") or [])
    seen = {str(r.get("ticker") or "").upper() for r in merged}
    for row in cached:
        tk = str(row.get("ticker") or "").upper()
        if tk and tk not in seen:
            merged.append(row)
            seen.add(tk)
    payload["merged_top_names"] = merged[:40]

    intent = dict(payload.get("decision_intent") or {})
    leaders = dict(intent.get("LEADERS") or {})
    if not leaders.get("top_hits"):
        from src.engines.scanner_matrix import ScannerCategory, ScannerHit
        from src.engines.scanner_matrix import ScannerMatrix as _SM

        top_hits = [
            _SM.enrich_hit_for_ui(
                ScannerHit(
                    scanner_name="brief_cache",
                    category=ScannerCategory.PATTERN,
                    ticker=r["ticker"],
                    score=float(r.get("max_score") or 5.0),
                    headline=r.get("why_flagged") or "Cached brief leader",
                    detail="Research only — confirm in Playbook",
                    metadata={"brief_section": r.get("brief_section")},
                ),
                score_display_mode="fallback_rank",
            )
            for r in cached[:8]
        ]
        leaders = {
            **leaders,
            "intent": "LEADERS",
            "count": len(top_hits),
            "probe_status": "cached",
            "regime_note": leaders.get("regime_note")
            or str(regime.get("trend") or "—"),
            "empty_why": "Live scan empty — showing cached brief leaders (research only).",
            "top_hits": top_hits,
        }
        intent["LEADERS"] = leaders
        payload["decision_intent"] = intent

    verdict = dict(payload.get("discovery_verdict") or {})
    if not verdict.get("best_speculative_name") and cached:
        verdict["best_speculative_name"] = cached[0]
        verdict["total_unique_names"] = max(
            int(verdict.get("total_unique_names") or 0), len(cached)
        )
    payload["discovery_verdict"] = verdict
    diag = dict(payload.get("diagnostics") or {})
    diag["cached_leader_count"] = len(cached)
    diag["data_freshness"] = "cached_brief"
    payload["diagnostics"] = diag
    return payload


@router.get("/scanners")
async def scanner_hub(
    request: Request,
    category: str = Query(
        None,
        description="LEADERS/PULLBACKS/BREAKOUTS/FLOW/NO_TRADE",
    ),
) -> Dict[str, Any]:
    """
    Scanner matrix results grouped by category.

    Decision-intent scanners are research/supporting unless Playbook confirms.
    """
    from src.engines.scanner_matrix import (  # noqa: PLC0415
        DECISION_INTENT_ORDER,
        ScannerCategory,
    )
    from src.engines.scanner_matrix import (
        ScannerMatrix as _SM,
    )

    research_note = (
        "Decision-intent scanners are research/supporting unless Playbook confirms. "
        "Page gate (WAIT/NO_TRADE) outranks scanner rank — zero hits can be correct."
    )

    try:
        scanner = _get_scanner()
        regime = await _real_regime()
        scan_fn = getattr(request.app.state, "scan_signals", None)
        live_signals = await _real_signals(scan_fn=scan_fn)
        signals, universe_label = await _scanner_signal_universe(scan_fn=scan_fn)
        diagnostic_info = _scanner_hub_diagnostics(
            regime, signals, universe_label=universe_label
        )
        score_display_mode = (
            "fallback_rank"
            if (
                not live_signals
                or universe_label == "synthetic_default"
                or diagnostic_info.get("data_freshness") == "synthetic"
            )
            else "live"
        )
        intent_summary = scanner.build_decision_intent_summary(signals, regime)
    except Exception as exc:
        logger.exception("Scanner hub failed: %s", exc)
        payload = _scanner_hub_warming_payload(
            reason=f"Scanner hub error — {exc!s}"[:200],
        )
        if category:
            cat_upper = category.upper()
            row = (payload.get("decision_intent") or {}).get(cat_upper) or {}
            return {
                "category": cat_upper,
                "hits": [],
                "count": 0,
                "probe_status": "warming",
                "regime_note": row.get("regime_note"),
                "empty_why": row.get("empty_why"),
                "near_misses": [],
                "diagnostics": payload["diagnostics"],
                "research_note": payload["research_note"],
            }
        return payload

    if category:
        cat_upper = category.upper()
        if cat_upper in DECISION_INTENT_ORDER:
            intent_row = intent_summary.get(cat_upper) or {}
            all_hits = scanner.hits_for_decision_intent(cat_upper, signals, regime)
            payload: Dict[str, Any] = {
                "category": cat_upper,
                "hits": [
                    _SM.enrich_hit_for_ui(h, score_display_mode=score_display_mode)
                    for h in all_hits
                ],
                "count": len(all_hits),
                "probe_status": intent_row.get("probe_status", "idle"),
                "regime_note": intent_row.get("regime_note"),
                "empty_why": intent_row.get("empty_why"),
                "near_misses": [],
                "diagnostics": diagnostic_info,
                "research_note": research_note,
            }
            if cat_upper == "NO_TRADE":
                payload["rejection_preview"] = await _scanner_rejection_preview(
                    regime, signals
                )
                if not all_hits and payload["rejection_preview"]:
                    payload["near_misses"] = payload["rejection_preview"][:3]
                payload["rejections_href"] = "/api/v7/playbook/no-trade"
            elif len(signals) > 0 and len(all_hits) == 0:
                payload["near_misses"] = []
                payload["empty_why"] = intent_row.get("empty_why")
            return payload

        try:
            cat = ScannerCategory(cat_upper)
            hits = scanner.scan_category(cat, signals, regime)
            intent_row = intent_summary.get(cat_upper) or {}
            return {
                "category": cat_upper,
                "hits": [
                    _SM.enrich_hit_for_ui(h, score_display_mode=score_display_mode)
                    for h in hits
                ],
                "count": len(hits),
                "probe_status": "active" if hits else "idle",
                "regime_note": intent_row.get("regime_note"),
                "empty_why": intent_row.get(
                    "empty_why",
                    f"No {cat_upper} scanner hits in this run.",
                ),
                "near_misses": [],
                "diagnostics": diagnostic_info,
                "research_note": research_note,
            }
        except ValueError:
            return {"error": f"Unknown category: {category}"}

    grouped = scanner.get_grouped_by_scanner(
        signals, regime, score_display_mode=score_display_mode
    )
    summary = scanner.get_summary(
        signals, regime, score_display_mode=score_display_mode
    )
    total_hits = sum(int((s or {}).get("count") or 0) for s in summary.values())
    universe_size = len(signals) if signals else 0
    discovery = _SM.build_merged_discovery_rank(
        grouped,
        summary,
        regime,
        universe_size=universe_size,
        score_display_mode=score_display_mode,
    )
    discovery_verdict = discovery["discovery_verdict"]
    if score_display_mode == "fallback_rank" and discovery_verdict.get(
        "best_speculative_name"
    ):
        spec = dict(discovery_verdict["best_speculative_name"])
        tier = _SM.fallback_priority_tier(float(spec.get("max_score") or 0))
        spec["score_display_mode"] = "fallback_rank"
        spec["priority_tier"] = tier
        spec["score_display"] = tier
        discovery_verdict = {**discovery_verdict, "best_speculative_name": spec}
    payload = {
        "scanners": grouped,
        "category_summary": summary,
        "decision_intent": intent_summary,
        "total_hits": total_hits,
        "universe_size": universe_size,
        "universe_label": universe_label,
        "score_display_mode": score_display_mode,
        "merged_top_names": discovery["merged_top_names"],
        "discovery_verdict": discovery_verdict,
        "scanner_overlap": discovery["scanner_overlap"],
        "scanner_quality": {
            "label": (
                "FALLBACK RANK"
                if score_display_mode == "fallback_rank"
                else "HEURISTIC"
            ),
            "note": (
                "Fallback rank · relevance only — not deploy-grade calibrated scores."
                if score_display_mode == "fallback_rank"
                else "Live calibration stats pending — ranks use overlap × score."
            ),
        },
        "diagnostics": diagnostic_info,
        "research_note": research_note,
        "hub_status": "live",
    }
    if not intent_summary:
        warming = _scanner_hub_warming_payload(
            reason="Scanner matrix returned no decision-intent summary.",
            universe_label=universe_label,
            universe_size=universe_size,
        )
        payload["decision_intent"] = warming["decision_intent"]
        payload["hub_status"] = "warming"
    payload = _enrich_discovery_zero_hits(payload, regime=regime, scanner=scanner)
    from src.services.playbook_near_miss import build_discovery_near_miss_strip

    near_strip = build_discovery_near_miss_strip(payload.get("merged_top_names") or [])
    payload["near_miss_strip"] = near_strip
    verdict = dict(payload.get("discovery_verdict") or {})
    ranked_cache = getattr(request.app.state, "playbook_ranked_cache", None) or {}
    funnel = ranked_cache.get("filter_funnel") or {}
    deploy_n = int(
        funnel.get("deploy_qualified_setups")
        or funnel.get("execution_ready_setups")
        or 0
    )
    verdict["deploy_qualified"] = deploy_n
    verdict["merged_top_count"] = len(payload.get("merged_top_names") or [])
    verdict["near_miss_strip_count"] = len(near_strip)
    payload["discovery_verdict"] = verdict
    return payload


# ── VCP Intelligence ─────────────────────────────────────────────────


@router.get("/vcp/{ticker}")
async def vcp_analysis(ticker: str) -> Dict[str, Any]:
    """Full VCP intelligence analysis for a ticker."""
    pipeline = _get_pipeline()
    vcp = _get_vcp()
    regime = await _real_regime()

    signal = _get_signal_for_ticker(ticker)
    if not signal:
        return {"error": f"No signal data for {ticker}"}

    sector = pipeline.classifier.classify(ticker, signal)
    result = vcp.analyze(signal, sector, regime)

    return {
        "ticker": ticker,
        "vcp": result.to_dict(),
    }


# ── Symbol Dossier ───────────────────────────────────────────────────


@router.get("/dossier/{ticker}")
async def symbol_dossier(ticker: str) -> Dict[str, Any]:
    """Complete decision dossier for a single symbol."""
    from src.engines.decision_object import DecisionObject  # noqa: PLC0415

    pipeline = _get_pipeline()
    vcp = _get_vcp()
    regime = await _real_regime()

    signal = _get_signal_for_ticker(ticker)
    if not signal:
        return {"error": f"No signal data for {ticker}"}

    # Full pipeline
    result = pipeline.process(signal, regime)

    # Build canonical DecisionObject from pipeline result
    decision_obj = DecisionObject.from_pipeline_result(result, regime)

    # VCP analysis (if applicable)
    vcp_result = vcp.analyze(signal, result.sector, regime)

    # Scanner warnings
    scanner = _get_scanner()
    warnings = scanner.get_warnings([signal], regime)
    ticker_warnings = [w.to_dict() for w in warnings if w.ticker == ticker]

    return {
        "ticker": ticker,
        "signal": decision_obj.to_dict(),
        "vcp": vcp_result.to_dict() if vcp_result.detection.is_vcp else None,
        "warnings": ticker_warnings,
    }


# ── No-Trade / Avoid List ───────────────────────────────────────────


@router.get("/no-trade")
async def no_trade_list() -> Dict[str, Any]:
    """Current no-trade and avoid signals with categorized audit blockers."""
    from src.services.rejection_audit import enrich_no_trade_list  # noqa: PLC0415

    pipeline = _get_pipeline()
    regime = await _real_regime()
    signals = await _real_signals()

    results = pipeline.process_batch(signals, regime)
    blocked = [
        r
        for r in results
        if r.decision.action in ("NO_TRADE", "EXIT", "REDUCE", "AVOID")
    ]
    no_trades, summary = enrich_no_trade_list(blocked, regime)

    trend = str(regime.get("trend") or regime.get("trend_regime") or "SIDEWAYS").upper()
    tradeability = str(regime.get("tradeability") or "WAIT").upper()

    return {
        "count": len(no_trades),
        "no_trade_signals": no_trades,
        "rejection_summary": summary,
        "regime": {
            "trend": trend,
            "tradeability": tradeability,
            "should_trade": regime.get("should_trade", True),
        },
    }


# ── Data builders for RS / Flow ──────────────────────────────────────


_RS_UNIVERSE = RS_UNIVERSE

_SECTOR_MAP = {t: rs_sector_for(t) for t in _RS_UNIVERSE}


async def _build_rs_universe() -> List[Dict[str, Any]]:
    """Build RS universe from real yfinance data."""
    import asyncio

    try:
        import yfinance as yf

        data = await asyncio.to_thread(
            yf.download,
            _RS_UNIVERSE + ["SPY"],
            period="6mo",
            interval="1wk",
            auto_adjust=True,
            progress=False,
        )
        if data is None or data.empty:
            return []
        close = data["Close"]
        universe = []
        for t in _RS_UNIVERSE:
            if t not in close.columns:
                continue
            s = close[t].dropna()
            if len(s) < 4:
                continue
            price = float(s.iloc[-1])
            r1w = float((s.iloc[-1] / s.iloc[-2] - 1) * 100)
            ret4 = float((s.iloc[-1] / s.iloc[-4] - 1) * 100)
            r1m = ret4 if len(s) >= 5 else 0.0
            ret12 = float((s.iloc[-1] / s.iloc[-12] - 1) * 100)
            r3m = ret12 if len(s) >= 13 else r1m
            ret0 = float((s.iloc[-1] / s.iloc[0] - 1) * 100)
            r6m = ret0 if len(s) >= 20 else r3m
            universe.append(
                {
                    "ticker": t,
                    "sector": _SECTOR_MAP.get(t, "Other"),
                    "market_cap": "LARGE",
                    "price": price,
                    "return_1w": r1w,
                    "return_1m": r1m,
                    "return_3m": r3m,
                    "return_6m": r6m,
                }
            )
        return universe
    except Exception as e:
        logger.warning("RS universe build failed: %s", e)
        return []


async def _build_benchmark() -> Dict[str, Any]:
    """Build benchmark returns from SPY."""
    import asyncio

    try:
        import yfinance as yf

        data = await asyncio.to_thread(
            yf.download,
            "SPY",
            period="6mo",
            interval="1wk",
            auto_adjust=True,
            progress=False,
        )
        if data is None or data.empty:
            return {}
        c = data["Close"]
        if hasattr(c, "columns"):
            c = c["SPY"] if "SPY" in c.columns else c.iloc[:, 0]
        c = c.dropna()
        if len(c) < 4:
            return {}

        def _price_at(index: int) -> float:
            value = c.iloc[index]
            if hasattr(value, "iloc"):
                value = value.iloc[0]
            return float(value)

        last = _price_at(-1)
        r1w = float((last / _price_at(-2) - 1) * 100)
        r1m = float((last / _price_at(-4) - 1) * 100) if len(c) >= 5 else 0.0
        r3m = float((last / _price_at(-12) - 1) * 100) if len(c) >= 13 else 0.0
        r6m = float((last / _price_at(0) - 1) * 100) if len(c) >= 20 else 0.0
        return {
            "return_1w": r1w,
            "return_1m": r1m,
            "return_3m": r3m,
            "return_6m": r6m,
        }
    except Exception as e:
        logger.warning("Benchmark build failed: %s", e)
        return {}


async def _build_flow_universe() -> List[Dict[str, Any]]:
    """Build flow universe from real yfinance data."""
    import asyncio

    try:
        import yfinance as yf

        data = await asyncio.to_thread(
            yf.download,
            _RS_UNIVERSE,
            period="3mo",
            interval="1d",
            auto_adjust=True,
            progress=False,
        )
        if data is None or data.empty:
            return []
        universe = []
        for t in _RS_UNIVERSE:
            try:
                c = data["Close"][t].dropna()
                v = data["Volume"][t].dropna()
                if len(c) < 20 or len(v) < 20:
                    continue
                avg_vol = float(v.iloc[-20:].mean())
                cur_vol = float(v.iloc[-1])
                universe.append(
                    {
                        "ticker": t,
                        "price": float(c.iloc[-1]),
                        "volume": cur_vol,
                        "avg_volume_20d": avg_vol,
                        "vol_ratio": (
                            round(cur_vol / avg_vol, 2) if avg_vol > 0 else 1.0
                        ),
                        "close_5d": [float(x) for x in c.iloc[-5:]],
                        "volume_5d": [float(x) for x in v.iloc[-5:]],
                    }
                )
            except Exception:
                continue
        return universe
    except Exception as e:
        logger.warning("Flow universe build failed: %s", e)
        return []


def _get_rs_engine():
    from src.engines.rs_ranking import RSRankingEngine

    return RSRankingEngine()


def _get_flow_engine():
    from src.engines.flow_intelligence import FlowIntelligenceEngine

    return FlowIntelligenceEngine()


@router.get("/rs-ranking")
async def rs_ranking(
    request: Request,
    sector: str = Query(None, description="Filter by sector"),
    cap: str = Query(None, description="MEGA/LARGE/MID/SMALL"),
    limit: int = Query(50, ge=1, le=100),
    live: bool = Query(
        False,
        description="Await live RS compute (use /rs-decision for full PM surface)",
    ),
) -> Dict[str, Any]:
    """Relative Strength ranking with sector/size filters."""
    cache_key = _rs_ranking_cache_key(sector, cap, limit)
    if cached := _get_rs_ranking_cached(cache_key):
        return cached

    if live:
        try:
            from src.services.rs_decision_surface import build_rs_decision_surface

            surf = await build_rs_decision_surface(
                request, limit=limit, sector=sector, wait_live_sec=50.0
            )
            rankings = surf.get("live_leaders") or []
            return {
                "count": len(rankings),
                "rankings": rankings,
                "stale_watchlist": surf.get("stale_watchlist") or [],
                "sector_rs": surf.get("sector_rotation") or [],
                "actionable_top3": surf.get("actionable_top3") or [],
                "freshness": surf.get("freshness"),
                "cached": False,
                "stale": not bool(rankings),
                "refreshing": False,
                "warning": surf.get("warning"),
            }
        except Exception as exc:
            logger.warning("rs-ranking live=true failed: %s", exc)

    asyncio.create_task(_refresh_rs_ranking_cache(cache_key, limit, sector, cap))
    return _brief_rs_ranking_fallback(limit, sector, cap)


@router.get("/flow")
async def flow_intelligence(
    limit: int = Query(20, ge=1, le=50),
    refresh: bool = Query(
        False, description="Run a bounded live refresh instead of cache-only response"
    ),
) -> Dict[str, Any]:
    """Flow / smart money intelligence."""
    if cached := _get_flow_cached():
        return {
            **cached,
            "count": min(limit, len(cached.get("profiles") or [])),
            "profiles": (cached.get("profiles") or [])[:limit],
            "unusual_activity": (cached.get("unusual_activity") or [])[:10],
        }

    if not refresh:
        return {
            "count": 0,
            "profiles": [],
            "unusual_activity": [],
            "cached": False,
            "stale": True,
            "warning": "flow intelligence is lazy-loaded; call refresh=true for bounded live refresh",
        }

    try:
        engine = _get_flow_engine()
        universe = await asyncio.wait_for(
            _build_flow_universe(), timeout=_FLOW_LOAD_TIMEOUT_SECONDS
        )
        profiles = await asyncio.wait_for(
            asyncio.to_thread(engine.analyze_batch, universe), timeout=1.0
        )
        unusual = engine.get_unusual_activity(profiles)
        payload = {
            "count": min(limit, len(profiles)),
            "profiles": [p.to_dict() for p in profiles],
            "unusual_activity": [p.to_dict() for p in unusual],
            "cached": False,
            "stale": False,
        }
        _set_flow_cached(payload)
        return {
            **payload,
            "profiles": payload["profiles"][:limit],
            "unusual_activity": payload["unusual_activity"][:10],
        }
    except asyncio.TimeoutError:
        if stale := _get_flow_cached(allow_stale=True):
            return {
                **stale,
                "profiles": (stale.get("profiles") or [])[:limit],
                "unusual_activity": (stale.get("unusual_activity") or [])[:10],
                "warning": "flow intelligence timeout — serving cached data",
            }
        logger.warning("Flow intelligence timeout with no cache fallback")
        return {
            "count": 0,
            "profiles": [],
            "unusual_activity": [],
            "cached": False,
            "stale": True,
            "warning": "flow intelligence timeout — no cached data yet",
        }
    except Exception as exc:
        if stale := _get_flow_cached(allow_stale=True):
            return {
                **stale,
                "profiles": (stale.get("profiles") or [])[:limit],
                "unusual_activity": (stale.get("unusual_activity") or [])[:10],
                "warning": "flow intelligence error — serving cached data",
            }
        logger.warning("Flow intelligence fallback: %s", exc)
        return {
            "count": 0,
            "profiles": [],
            "unusual_activity": [],
            "cached": False,
            "stale": True,
            "warning": "flow intelligence unavailable",
        }


# ── Backtest: Scanner Picks vs Benchmark ─────────────────────────────


@router.get("/backtest-vs-benchmark")
async def backtest_vs_benchmark(
    period: str = Query("5y", description="1y/2y/5y"),
    benchmark: str = Query("SPY", description="SPY or QQQ"),
) -> Dict[str, Any]:
    """Compare hypothetical scanner top-pick returns vs SPY/QQQ.

    Uses RS leadership methodology: buy top-5 RS leaders monthly,
    equal-weight, rebalance monthly, compare to buy-and-hold benchmark.
    """
    import asyncio

    try:
        import pandas as pd
        import yfinance as yf
    except ImportError:
        return {"error": "yfinance/pandas not available"}

    # RS leadership universe (top liquid names)
    universe = [
        "NVDA",
        "AAPL",
        "MSFT",
        "AMZN",
        "META",
        "GOOGL",
        "TSLA",
        "AMD",
        "AVGO",
        "CRM",
        "NFLX",
        "ADBE",
        "NOW",
        "UBER",
        "PLTR",
        "PANW",
        "CRWD",
        "ANET",
        "XOM",
        "CVX",
        "LLY",
        "UNH",
        "JPM",
        "V",
    ]
    tickers = universe + [benchmark]

    try:
        data = await asyncio.to_thread(
            yf.download,
            tickers,
            period=period,
            interval="1mo",
            auto_adjust=True,
            progress=False,
        )
        if data is None or data.empty:  # type: ignore[union-attr]
            return {"error": "No data returned from yfinance"}
        close = data["Close"].dropna(how="all")  # type: ignore[index]
    except Exception as e:
        return {"error": f"Data fetch failed: {e}"}

    if close.empty or len(close) < 3:
        return {"error": "Insufficient data"}

    # Monthly returns
    returns = close.pct_change().dropna()

    # RS ranking: 3-month rolling return
    rs_window = 3
    rolling_ret = close.pct_change(rs_window).dropna()

    # Strategy: each month, buy top-5 RS leaders, equal weight
    strategy_returns = []
    benchmark_returns = []
    months = []
    picks_history = []

    for i in range(rs_window, len(close) - 1):
        date_idx = close.index[i]
        next_idx = close.index[i + 1]

        # RS rank at this month
        rs_scores = {}
        for t in universe:
            if t in rolling_ret.columns:  # type: ignore
                val = rolling_ret.loc[rolling_ret.index <= date_idx, t]
                if len(val) > 0 and pd.notna(val.iloc[-1]):  # type: ignore
                    rs_scores[t] = val.iloc[-1]  # type: ignore

        if len(rs_scores) < 5:
            continue

        # Top 5 leaders
        ranked = sorted(rs_scores.items(), key=lambda x: x[1], reverse=True)
        top5 = [t for t, _ in ranked[:5]]

        # Next month return for top5 (equal weight)
        port_ret = 0.0
        valid = 0
        for t in top5:
            if t in returns.columns:  # type: ignore
                r_vals = returns.loc[returns.index <= next_idx, t]
                if (
                    hasattr(r_vals, "__len__")
                    and len(r_vals) > 0  # type: ignore[arg-type]
                    and pd.notna(r_vals.iloc[-1])  # type: ignore
                ):
                    port_ret += float(r_vals.iloc[-1])  # type: ignore
                    valid += 1
        if valid > 0:
            port_ret /= valid

        # Benchmark return
        bm_ret = 0.0
        if benchmark in returns.columns:  # type: ignore
            bm_vals = returns.loc[returns.index <= next_idx, benchmark]
            if len(bm_vals) > 0 and pd.notna(bm_vals.iloc[-1]):  # type: ignore
                bm_ret = bm_vals.iloc[-1]  # type: ignore

        strategy_returns.append(port_ret)
        benchmark_returns.append(bm_ret)
        months.append(str(next_idx.date()))
        picks_history.append(
            {
                "date": str(date_idx.date()),
                "picks": top5,
            }
        )

    if not strategy_returns:
        return {"error": "Not enough data for backtest"}

    # Cumulative returns
    strat_cum = 1.0
    bench_cum = 1.0
    strat_curve = [1.0]
    bench_curve = [1.0]
    for sr, br in zip(
        strategy_returns,
        benchmark_returns,
        strict=True,
    ):
        strat_cum *= 1 + sr
        bench_cum *= 1 + br
        strat_curve.append(round(strat_cum, 4))
        bench_curve.append(round(bench_cum, 4))

    # Stats
    n = len(strategy_returns)
    strat_ann = (strat_cum ** (12.0 / n) - 1) if n > 0 else 0
    bench_ann = (bench_cum ** (12.0 / n) - 1) if n > 0 else 0
    strat_vol = statistics.stdev(strategy_returns) * (12**0.5) if n > 1 else 0
    bench_vol = statistics.stdev(benchmark_returns) * (12**0.5) if n > 1 else 0
    alpha = strat_ann - bench_ann
    win_months = sum(
        1
        for s, b in zip(
            strategy_returns,
            benchmark_returns,
            strict=True,
        )
        if s > b
    )

    win_rate = round(win_months / n * 100, 1) if n > 0 else 0

    return {
        "period": period,
        "benchmark": benchmark,
        "months": n,
        "strategy": {
            "name": "RS Top-5 Leaders (Monthly Rebal)",
            "total_return": round((strat_cum - 1) * 100, 2),
            "annualized": round(strat_ann * 100, 2),
            "volatility": round(strat_vol * 100, 2),
            "sharpe": (round(strat_ann / strat_vol, 2) if strat_vol > 0 else 0),
        },
        "benchmark_stats": {
            "total_return": round((bench_cum - 1) * 100, 2),
            "annualized": round(bench_ann * 100, 2),
            "volatility": round(bench_vol * 100, 2),
            "sharpe": (round(bench_ann / bench_vol, 2) if bench_vol > 0 else 0),
        },
        "alpha_annualized": round(alpha * 100, 2),
        "win_rate_vs_benchmark": win_rate,
        "equity_curve": {
            "dates": ["start"] + months,
            "strategy": strat_curve,
            "benchmark": bench_curve,
        },
        "recent_picks": picks_history[-6:],
    }


def _get_signal_for_ticker(
    ticker: str,
) -> Dict[str, Any] | None:
    """Look up a ticker from brief data (no import from main.py)."""
    try:
        from src.services.brief_data_service import find_signal  # noqa: PLC0415

        sig, _ = find_signal(ticker)
        if sig:
            return sig
    except Exception:
        pass
    return {"ticker": ticker, "score": 5, "strategy": "scan"}
