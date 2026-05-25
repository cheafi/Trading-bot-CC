"""
Daily Decision State Router
===========================

Single truthful first-page decision endpoint.

This endpoint intentionally separates actionable trades from watchlist ideas:
- BUY_NOW only when action, confidence, R:R, entry/stop/target, and regime pass.
- RS leaders are WATCHLIST candidates only; they never become buy-now without levels.
"""

from __future__ import annotations

import asyncio
import json
import logging
import time
from datetime import date, datetime, timezone
from pathlib import Path
from typing import Any, Dict, List

from fastapi import APIRouter, Query, Request

from src.api.deps import sanitize_for_json

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/v7/daily-decision", tags=["daily-decision"])

_RS_CACHE_TTL_SECONDS = 5 * 60
_rs_cache: Dict[str, Any] = {"ts": 0.0, "rows": [], "refreshing": False}
_SNAPSHOT_REGIME_CACHE: Dict[str, Any] = {}


def _as_dict(item: Any) -> Dict[str, Any]:
    if isinstance(item, dict):
        return dict(item)
    if hasattr(item, "model_dump"):
        try:
            return dict(item.model_dump())
        except Exception:
            pass
    if hasattr(item, "__dict__"):
        return {k: v for k, v in vars(item).items() if not k.startswith("_")}
    return {}


def _as_float(value: Any, default: float = 0.0) -> float:
    try:
        if value is None or value == "":
            return default
        return float(value)
    except (TypeError, ValueError):
        return default


def _unit_confidence(row: Dict[str, Any]) -> float:
    raw = (
        row.get("confidence")
        or row.get("final_conf")
        or row.get("confidence_score")
        or row.get("score")
        or 0.0
    )
    value = _as_float(raw)
    if value > 1:
        value /= 100.0
    return max(0.0, min(1.0, value))


def _risk_reward(row: Dict[str, Any]) -> float:
    rr = _as_float(
        row.get("risk_reward") or row.get("rr") or row.get("risk_reward_ratio")
    )
    if rr > 0:
        return rr
    entry = _as_float(row.get("entry_price") or row.get("entry"))
    stop = _as_float(row.get("stop_price") or row.get("stop"))
    target = _as_float(row.get("target_price") or row.get("target"))
    risk = abs(entry - stop)
    if entry > 0 and target > 0 and risk > 0:
        return round(abs(target - entry) / risk, 2)
    return 0.0


def _has_trade_levels(row: Dict[str, Any]) -> bool:
    return all(
        _as_float(row.get(field)) > 0
        for field in ("entry_price", "stop_price", "target_price")
    )


def _regime_tradeable(regime: Dict[str, Any]) -> bool:
    if regime.get("should_trade") is False:
        return False
    vix = _as_float(regime.get("vix"))
    if vix >= 28:
        return False
    tradeability = str(regime.get("tradeability") or "").upper()
    if tradeability in {"NO_TRADE", "WAIT"}:
        return False
    return True


def _normalize_trade_candidate(row: Dict[str, Any], source: str) -> Dict[str, Any]:
    ticker = row.get("ticker") or row.get("symbol") or ""
    action = str(
        row.get("action")
        or row.get("recommendation")
        or row.get("conviction")
        or "WATCH"
    ).upper()
    confidence = _unit_confidence(row)
    rr = _risk_reward(row)
    normalized = {
        **row,
        "ticker": ticker,
        "action": action,
        "confidence": confidence,
        "final_conf": confidence,
        "risk_reward": rr,
        "entry_price": row.get("entry_price") or row.get("entry") or row.get("price"),
        "stop_price": row.get("stop_price") or row.get("stop"),
        "target_price": row.get("target_price")
        or row.get("target")
        or row.get("target_2r"),
        "setup": row.get("setup") or row.get("strategy") or source,
        "why_now": row.get("why_now") or row.get("reason") or row.get("notes") or "",
        "confidence_source": row.get("confidence_source") or source,
        "source": source,
    }
    normalized["buy_now"] = _is_actionable(normalized, regime_ok=True)
    if not normalized.get("grade"):
        normalized["grade"] = (
            "A" if confidence >= 0.75 else "B" if confidence >= 0.6 else "C"
        )
    return normalized


def _is_actionable(row: Dict[str, Any], *, regime_ok: bool) -> bool:
    action = str(row.get("action") or "").upper()
    return (
        regime_ok
        and action in {"BUY", "TRADE", "STRONG_TRADE", "PILOT"}
        and _unit_confidence(row) >= (0.65 if action != "PILOT" else 0.55)
        and _risk_reward(row) >= 2.0
        and _has_trade_levels(row)
    )


def _get_blocker_reason(row: Dict[str, Any], *, regime_ok: bool) -> str:
    action = str(row.get("action") or "").upper()
    if not regime_ok:
        return "regime"
    if action not in {"BUY", "TRADE", "STRONG_TRADE", "PILOT"}:
        return "thesis/action"
    if not _has_trade_levels(row):
        return "missing entry/stop/target"
    if _risk_reward(row) < 2.0:
        return "poor R:R"
    if _unit_confidence(row) < (0.65 if action != "PILOT" else 0.55):
        return "low conviction"
    return "unknown"


def _normalize_regime(data: Dict[str, Any]) -> Dict[str, Any]:
    data = dict(data or {})

    label = (
        data.get("label") or data.get("regime") or data.get("risk_state") or "UNKNOWN"
    )
    confidence = _as_float(data.get("confidence"), 0.0)
    if confidence > 1:
        confidence /= 100.0
    return {
        **data,
        "label": label,
        "confidence": confidence,
        "tradeability": data.get("tradeability")
        or ("TRADE" if data.get("should_trade", True) else "NO_TRADE"),
        "vix": data.get("vix"),
        "breadth": data.get("breadth") or data.get("breadth_pct"),
        "trend": str(data.get("trend") or data.get("trend_regime") or "").upper()
        or "UNKNOWN",
    }


def _snapshot_regime() -> Dict[str, Any]:
    global _SNAPSHOT_REGIME_CACHE
    if _SNAPSHOT_REGIME_CACHE:
        return dict(_SNAPSHOT_REGIME_CACHE)
    try:
        path = Path.cwd() / "data" / "market_overview_last_good.json"
        if not path.exists():
            path = Path("/app/data/market_overview_last_good.json")
        data = json.loads(path.read_text()) if path.exists() else {}
        regime = data.get("regime") or {}
        if regime:
            _SNAPSHOT_REGIME_CACHE = _normalize_regime(
                {
                    **regime,
                    "regime": regime.get("label") or regime.get("regime"),
                    "source": "market_overview_last_good",
                }
            )
            return dict(_SNAPSHOT_REGIME_CACHE)
    except Exception as exc:
        logger.debug("daily decision snapshot regime unavailable: %s", exc)
    return _normalize_regime(
        {"regime": "UNKNOWN", "should_trade": True, "confidence": 0.0, "vix": 18.0}
    )


def _request_cached_regime(request: Request) -> Dict[str, Any] | None:
    cache = getattr(request.app.state, "regime_cache", None)
    if cache is not None:
        data = _as_dict(cache)
        if data:
            return _normalize_regime(data)
    try:
        from src.services.regime_service import RegimeService  # noqa: PLC0415

        if RegimeService._cache:
            return _normalize_regime(RegimeService._cache)
    except Exception:
        pass
    return None


async def _warm_regime_cache() -> None:
    try:
        from src.services.regime_service import RegimeService  # noqa: PLC0415

        await asyncio.to_thread(RegimeService.get)
    except Exception as exc:
        logger.debug("daily decision background regime warm failed: %s", exc)


def _engine_recommendations(request: Request, limit: int) -> List[Dict[str, Any]]:
    engine = getattr(request.app.state, "engine", None)
    if not engine:
        return []
    rows = []
    for rec in list(getattr(engine, "_cached_recommendations", []) or [])[:limit]:
        data = _as_dict(rec)
        if data:
            rows.append(_normalize_trade_candidate(data, "engine_cache"))
    return rows


def _map_rs_rankings(
    rankings: List[Dict[str, Any]], limit: int, source: str
) -> List[Dict[str, Any]]:
    rows = []
    for item in rankings[:limit]:
        rs_percentile = _as_float(
            item.get("rs_percentile") or item.get("rs_composite"), 0.0
        )
        confidence = min(
            0.74, max(0.55, rs_percentile / 100.0 if rs_percentile else 0.55)
        )
        rows.append(
            {
                "ticker": item.get("ticker"),
                "action": "WATCH",
                "buy_now": False,
                "score": rs_percentile,
                "rs_percentile": item.get("rs_percentile"),
                "rs_composite": item.get("rs_composite"),
                "confidence": confidence,
                "final_conf": confidence,
                "confidence_source": "rs-watchlist",
                "sector": item.get("sector") or "",
                "sector_type": item.get("sector") or "",
                "entry_price": item.get("price"),
                "stop_price": None,
                "target_price": None,
                "risk_reward": 0,
                "setup": "relative_strength_watchlist",
                "grade": (
                    "A" if rs_percentile >= 90 else "B" if rs_percentile >= 75 else "C"
                ),
                "why_now": f"RS leader · {item.get('status', 'WATCH')} · percentile {item.get('rs_percentile', '—')} · trend {item.get('trend', '—')}",
                "why_not": "No confirmed setup levels yet; target/stop hidden until scanner or brief confirms.",
                "position_hint": "Watchlist only — no full-size entry",
                "source": source,
            }
        )
    return rows


async def _refresh_rs_cache(limit: int) -> None:
    if _rs_cache.get("refreshing"):
        return
    _rs_cache["refreshing"] = True
    try:
        from src.api.routers.playbook import rs_ranking  # noqa: PLC0415

        payload = await asyncio.wait_for(
            rs_ranking(sector=None, cap=None, limit=max(limit, 8)), timeout=10.0
        )
        rankings = payload.get("rankings", []) if isinstance(payload, dict) else []
        rows = _map_rs_rankings(rankings, max(limit, 8), "rs-watchlist")
        if rows:
            _rs_cache.update({"ts": time.time(), "rows": rows})
    except Exception as exc:
        logger.warning("daily decision RS background refresh failed: %s", exc)
    finally:
        _rs_cache["refreshing"] = False


async def _brief_watchlist(limit: int) -> List[Dict[str, Any]]:
    try:
        from src.services.brief_data_service import load_brief  # noqa: PLC0415

        brief = await asyncio.to_thread(load_brief)
    except Exception as exc:
        logger.warning("daily decision brief watchlist unavailable: %s", exc)
        return []

    rows = []
    for item in list(brief.get("watch") or [])[:limit]:
        rs_score = _as_float(item.get("rs_score"), 0.0)
        confidence = min(0.7, max(0.5, rs_score / 100.0 if rs_score else 0.55))
        rows.append(
            {
                "ticker": item.get("ticker") or item.get("symbol"),
                "action": "WATCH",
                "buy_now": False,
                "score": rs_score,
                "confidence": confidence,
                "final_conf": confidence,
                "confidence_source": "stale-brief-watchlist",
                "sector": item.get("sector") or "",
                "sector_type": item.get("sector") or "",
                "entry_price": item.get("price") or item.get("entry"),
                "stop_price": None,
                "target_price": None,
                "risk_reward": 0,
                "setup": "stale_brief_watchlist",
                "grade": (
                    "B"
                    if str(item.get("conviction") or "").upper() in {"LEADER", "TRADE"}
                    else "C"
                ),
                "why_now": f"Stale brief watchlist · RS {item.get('rs_score', '—')} · conviction {item.get('conviction', 'WATCH')}",
                "why_not": "Brief data is stale and lacks current confirmation; wait for live RS/scanner levels.",
                "position_hint": "Stale watchlist only — no entry until live confirmation",
                "source": "stale-brief-watchlist",
            }
        )
    return rows


async def _rs_watchlist(limit: int) -> List[Dict[str, Any]]:
    age = time.time() - float(_rs_cache.get("ts") or 0.0)
    cached = list(_rs_cache.get("rows") or [])
    if cached and age < _RS_CACHE_TTL_SECONDS:
        return cached[:limit]

    if not _rs_cache.get("refreshing"):
        asyncio.create_task(_refresh_rs_cache(limit))

    if cached:
        return [{**row, "source": "rs-watchlist-stale"} for row in cached[:limit]]

    try:
        return await asyncio.wait_for(_brief_watchlist(limit), timeout=0.45)
    except asyncio.TimeoutError:
        logger.debug("daily decision brief fallback timed out; returning refresh state")
        return []


def _no_trade_reasons(
    *,
    regime: Dict[str, Any],
    actionable_count: int,
    engine_count: int,
    watchlist_count: int,
) -> List[str]:
    reasons: List[str] = []
    if not _regime_tradeable(regime):
        reasons.append(
            str(
                regime.get("no_trade_reason")
                or "Regime gate is not permissive enough for new buy-now entries."
            )
        )
    if actionable_count == 0:
        reasons.append(
            "No candidate currently passes action + confidence + R:R + entry/stop/target checks."
        )
    if engine_count == 0:
        reasons.append(
            "Engine recommendation cache is empty (0 candidates matched strict setup rules); using watchlist diagnostics instead of fabricating trades."
        )
    if watchlist_count > 0:
        reasons.append(
            "Relative-strength leaders are available as WATCH only until setup levels confirm."
        )
    return list(dict.fromkeys([r for r in reasons if r]))


@router.get("")
async def daily_decision_state(
    request: Request,
    limit: int = Query(8, ge=1, le=30),
) -> Dict[str, Any]:
    """Canonical daily PM decision state for first-page dashboard UX."""
    started = time.perf_counter()
    regime = _request_cached_regime(request) or _snapshot_regime()
    if regime.get("source") == "market_overview_last_good":
        asyncio.create_task(_warm_regime_cache())
    regime_ok = _regime_tradeable(regime)

    engine_rows = _engine_recommendations(request, limit)

    # Deduplicate by ticker across engine candidates
    trade_candidates = []
    seen = set()
    for row in engine_rows:
        tc = _normalize_trade_candidate(row, row.get("source", "engine_cache"))
        tk = tc.get("ticker", "")
        if tk and tk not in seen:
            seen.add(tk)
            trade_candidates.append(tc)

    actionable = [
        row for row in trade_candidates if _is_actionable(row, regime_ok=regime_ok)
    ]
    watch_from_engine = [row for row in trade_candidates if row not in actionable]

    rs_rows_raw = await _rs_watchlist(limit)
    rs_rows = []
    for row in rs_rows_raw:
        tk = row.get("ticker", "")
        if tk and tk not in seen:
            seen.add(tk)
            rs_rows.append(row)

    watchlist = (watch_from_engine + rs_rows)[:limit]

    # Calculate blockers
    blockers = {
        "regime": 0,
        "thesis/action": 0,
        "poor R:R": 0,
        "low conviction": 0,
        "missing entry/stop/target": 0,
        "unknown": 0,
    }
    for tc in trade_candidates + rs_rows:
        if tc not in actionable:
            br = _get_blocker_reason(tc, regime_ok=regime_ok)
            blockers[br] = blockers.get(br, 0) + 1

    pruned_watchlist = []
    for w in watchlist:
        action = str(w.get("action") or "").upper()
        rr = _risk_reward(w)
        if action in {"BUY", "TRADE", "STRONG_TRADE"} and rr < 1.0:
            continue
        pruned_watchlist.append(w)

    best_near_miss = None
    if pruned_watchlist:
        near_misses = sorted(
            [w for w in pruned_watchlist],
            key=lambda x: _unit_confidence(x),
            reverse=True,
        )
        if near_misses:
            best_near_miss = near_misses[0]
            best_near_miss["upgrade_trigger"] = _get_blocker_reason(
                best_near_miss, regime_ok=regime_ok
            )

    if actionable:
        decision = "BUY_NOW"
        tradeability = "TRADE"
        summary = (
            "Actionable setups identified. Trade only with stated stop and target."
        )
    elif best_near_miss:
        decision = "WATCHLIST" if regime_ok else "WAIT"
        tradeability = "WAIT"
        summary = "No buy-now setup. Focus on near-miss upgrades and watchlist."
    else:
        decision = "WAIT"
        tradeability = "WAIT"
        summary = "No actionable setups. Market context requires patience."

    reasons = _no_trade_reasons(
        regime=regime,
        actionable_count=len(actionable),
        engine_count=len(engine_rows),
        watchlist_count=len(watchlist),
    )

    top_ranked = actionable + pruned_watchlist
    payload = {
        "status": "ok",
        "date": date.today().isoformat(),
        "decision": decision,
        "tradeability": tradeability,
        "summary": summary,
        "buy_now": actionable[0] if actionable else None,
        "best_near_miss": best_near_miss,
        "blockers": blockers,
        "actionable": actionable,
        "watchlist": pruned_watchlist,
        "top_ranked": top_ranked[:limit],
        "avoid_list": [{"ticker": "⚠", "reason": reason} for reason in reasons],
        "no_trade_reasons": reasons,
        "regime_gate": {
            "ok": regime_ok,
            "label": regime.get("label"),
            "tradeability": tradeability,
            "should_trade": regime.get("should_trade", True),
            "confidence": regime.get("confidence"),
            "trend": regime.get("trend"),
            "vix": regime.get("vix"),
            "breadth": regime.get("breadth"),
        },
        "confidence": {
            "status": "unproven" if not actionable else "candidate-level",
            "source": (
                "decision-ledger + live engine"
                if engine_rows
                else "rs-watchlist fallback"
            ),
            "sample_note": "Show sample size/Brier proof before treating confidence as predictive.",
        },
        "sources": {
            "engine_cache": {"count": len(engine_rows)},
            "actionable": {"count": len(actionable)},
            "rs_watchlist": {
                "count": len(rs_rows),
                "stale": bool(_rs_cache.get("rows"))
                and (time.time() - float(_rs_cache.get("ts") or 0.0))
                >= _RS_CACHE_TTL_SECONDS,
                "refreshing": bool(_rs_cache.get("refreshing")),
            },
        },
        "trust": {
            "mode": (
                "PAPER"
                if getattr(getattr(request.app.state, "engine", None), "dry_run", True)
                else "LIVE"
            ),
            "source": "daily-decision-state",
            "feature_stage": "BETA",
            "as_of": datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
            "rule": "BUY_NOW requires regime + action + confidence >=65% + R:R >=2 + entry/stop/target.",
        },
        "latency_ms": round((time.perf_counter() - started) * 1000, 1),
    }
    return sanitize_for_json(payload)
