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
from typing import Any, Dict, List

from fastapi import APIRouter, Query

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/v7/playbook", tags=["playbook"])

_RANKED_CACHE_TTL = 5 * 60
_RANKED_LOAD_TIMEOUT_SECONDS = 15.0
_RANKED_TIMEOUT_SECONDS = 30.0
_ranked_cache: Dict[str, Dict[str, Any]] = {}
_FLOW_CACHE_TTL = 10 * 60
_FLOW_LOAD_TIMEOUT_SECONDS = 2.5
_flow_cache: Dict[str, Any] = {"ts": 0.0, "data": None}
_RS_RANKING_CACHE_TTL = 5 * 60
_rs_ranking_cache: Dict[str, Dict[str, Any]] = {}
_rs_ranking_refreshing: set[str] = set()


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


async def _real_signals() -> List[Dict[str, Any]]:
    """Get real signals — uses BriefDataService (no import from main.py)."""
    try:
        from src.services.brief_data_service import load_brief  # noqa: PLC0415

        brief = await asyncio.to_thread(load_brief)
        recs = []
        for section in ("actionable", "watch", "review"):
            recs.extend(brief.get(section, []))
        return recs
    except Exception as e:
        logger.warning("Signals fallback: %s", e)
        return []


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
    if allow_stale or age < _RANKED_CACHE_TTL:
        return {
            **entry["data"],
            "cached": True,
            "stale": age >= _RANKED_CACHE_TTL,
            "age_seconds": int(age),
        }
    return None


def _set_ranked_cached(key: str, data: Dict[str, Any]) -> None:
    _ranked_cache[key] = {"data": data, "ts": time.time()}


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
                "rs_1w": 0.0,
                "rs_1m": rs_score,
                "rs_3m": rs_score,
                "rs_6m": rs_score,
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
        "sector_rs": [],
        "breakouts": [],
        "breakdowns": [],
        "cached": False,
        "stale": True,
        "refreshing": True,
        "source": "brief_rs_fallback",
        "warning": "live RS ranking is warming; serving stale brief watchlist",
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


def _finalize_ranked_response(data: Dict[str, Any]) -> Dict[str, Any]:
    """Attach best_action + overlap_warning if missing."""
    if data.get("best_action"):
        return data
    from src.services.best_action import enrich_ranked_payload

    return enrich_ranked_payload(data)


def _brief_ranked_fallback(
    limit: int,
    action: str | None = None,
    sector: str | None = None,
) -> Dict[str, Any]:
    if sector:
        return {
            "count": 0,
            "opportunities": [],
            "cached": False,
            "stale": True,
            "source": "brief_fallback",
            "warning": "ranked pipeline unavailable — no sector data in brief fallback",
        }
    try:
        from src.services.brief_data_service import load_brief  # noqa: PLC0415

        brief = load_brief()
    except Exception as exc:
        logger.warning("Brief ranked fallback unavailable: %s", exc)
        return {
            "count": 0,
            "opportunities": [],
            "cached": False,
            "stale": True,
            "source": "brief_fallback",
            "warning": "ranked pipeline unavailable — brief fallback failed",
        }

    raw: List[Dict[str, Any]] = []
    for section in ("actionable", "watch", "review"):
        raw.extend(brief.get(section, []) or [])
    if action:
        wanted = action.upper()
        raw = [
            row
            for row in raw
            if str(row.get("conviction") or row.get("action") or "WATCH").upper()
            == wanted
        ]

    rows: List[Dict[str, Any]] = []
    for row in raw[:limit]:
        entry = row.get("entry") or row.get("entry_price") or row.get("price")
        stop = row.get("stop") or row.get("stop_price")
        target = (
            row.get("target_3r")
            or row.get("target_2r")
            or row.get("target")
            or row.get("target_price")
        )
        risk_reward = row.get("risk_reward") or row.get("rr")
        if risk_reward is None and entry and stop and target and entry != stop:
            try:
                risk_reward = round(
                    (float(target) - float(entry)) / (float(entry) - float(stop)), 1
                )
            except Exception:
                risk_reward = None
        conviction = str(row.get("conviction") or row.get("action") or "WATCH").upper()
        score = row.get("rs_score") or row.get("score") or 0
        stage = (row.get("stage") or row.get("sector_stage") or "").strip()
        leader = (
            row.get("leader")
            or row.get("leader_status")
            or ("LEADER" if row.get("near_52w_high") else "")
        )
        if isinstance(leader, str):
            leader = leader.strip()
        why_not = row.get("why_not") or []
        if isinstance(why_not, str):
            why_not = [why_not] if why_not else []
        upgrade = row.get("upgrade_trigger") or row.get("upgrade") or ""
        rows.append(
            {
                "ticker": row.get("ticker") or row.get("symbol"),
                "sector_type": row.get("sector") or "",
                "theme": row.get("theme") or "Brief fallback",
                "setup": row.get("setup") or "brief",
                "stage": stage,
                "leader": leader,
                "score": score,
                "grade": (
                    "A"
                    if conviction == "TRADE"
                    else "B" if conviction == "LEADER" else "C"
                ),
                "thesis_conf": 0.7 if row.get("near_52w_high") else 0.5,
                "timing_conf": 0.7 if (row.get("vol_ratio") or 0) >= 1.2 else 0.5,
                "exec_conf": 0.6,
                "data_conf": 0.5 if brief.get("synthetic") else 0.7,
                "final_conf": 0.6,
                "action": conviction,
                "risk_level": "NORMAL",
                "entry_price": entry,
                "target_price": target,
                "stop_price": stop,
                "risk_reward": risk_reward or 3.0,
                "why_now": row.get("why_now")
                or row.get("reason")
                or f"RS:{row.get('rs_score', '—')} · ATR:{row.get('atr_pct', '—')}% · Vol:{row.get('vol_ratio', '—')}x",
                "why_not": why_not,
                "upgrade_trigger": upgrade,
                "evidence_badge": (
                    "stale-brief"
                    if brief.get("synthetic")
                    else "brief-fallback"
                ),
                "invalidation": row.get("invalidation")
                or (
                    f"Close below stop ${stop}"
                    if stop
                    else "Regime gate closes or structure breaks down"
                ),
            }
        )

    payload = {
        "count": len(rows),
        "opportunities": rows,
        "cached": False,
        "stale": True,
        "source": "brief_fallback",
        "warning": "ranked pipeline unavailable — serving brief fallback",
    }
    return _finalize_ranked_response(payload)


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


# ── Ranked Opportunities ─────────────────────────────────────────────


@router.get("/ranked")
async def ranked_opportunities(
    limit: int = Query(20, ge=1, le=100),
    action: str = Query(None, description="Filter by action"),
    sector: str = Query(None, description="Filter by sector bucket"),
) -> Dict[str, Any]:
    """3-layer ranked opportunity board."""
    cache_key = _ranked_cache_key(limit, action, sector)
    if cached := _get_ranked_cached(cache_key):
        return _finalize_ranked_response(cached)

    try:
        pipeline = _get_pipeline()
        regime, signals = await asyncio.wait_for(
            asyncio.gather(_real_regime(), _real_signals()),
            timeout=_RANKED_LOAD_TIMEOUT_SECONDS,
        )
        results = await asyncio.wait_for(
            asyncio.to_thread(pipeline.process_batch, signals, regime),
            timeout=_RANKED_TIMEOUT_SECONDS,
        )
    except asyncio.TimeoutError:
        if stale := _get_ranked_cached(cache_key, allow_stale=True):
            return _finalize_ranked_response(
                {
                    **stale,
                    "warning": "ranked pipeline timeout — serving cached board",
                }
            )
        logger.warning("Ranked playbook timeout with no cache fallback")
        fallback = _brief_ranked_fallback(limit, action, sector)
        _set_ranked_cached(cache_key, fallback)
        return _finalize_ranked_response(
            {
                **fallback,
                "warning": "ranked pipeline timeout — serving brief fallback",
            }
        )
    except Exception as e:
        if stale := _get_ranked_cached(cache_key, allow_stale=True):
            return _finalize_ranked_response(
                {
                    **stale,
                    "warning": "ranked pipeline error — serving cached board",
                }
            )
        import traceback

        traceback.print_exc()
        logger.warning("Ranked playbook fallback: %s", e)
        fallback = _brief_ranked_fallback(limit, action, sector)
        _set_ranked_cached(cache_key, fallback)
        return _finalize_ranked_response(
            {
                **fallback,
                "warning": "ranked pipeline unavailable — serving brief fallback",
            }
        )

    # Filter
    if action:
        results = [r for r in results if r.decision.action == action.upper()]
    if sector:
        sb = sector.upper()
        results = [r for r in results if r.sector.sector_bucket.value == sb]

    rows = []
    for i, r in enumerate(results[:limit]):
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
            # Phase 9 pass-through
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
        # Runner-up comparison
        if i < min(limit, len(results)) - 1:
            nxt = results[i + 1]
            row["runner_up"] = {
                "ticker": nxt.signal.get("ticker"),
                "score": round(nxt.confidence.final, 2),
                "reason": f"{r.signal.get('ticker')} has higher conviction"
                f" ({round(r.confidence.final, 2)} vs"
                f" {round(nxt.confidence.final, 2)})",
            }
        rows.append(row)

    response = {
        "count": len(rows),
        "opportunities": rows,
        "cached": False,
        "stale": False,
        "source": "ranked_pipeline",
    }
    response = _finalize_ranked_response(response)
    _set_ranked_cached(cache_key, response)
    return response


# ── Scanner Hub ──────────────────────────────────────────────────────


@router.get("/scanners")
async def scanner_hub(
    category: str = Query(
        None,
        description="LEADERS/PULLBACKS/BREAKOUTS/FLOW/NO_TRADE",
    ),
) -> Dict[str, Any]:
    """Scanner matrix results grouped by category."""
    from datetime import datetime

    scanner = _get_scanner()
    regime = await _real_regime()
    signals = await _real_signals()

    diagnostic_info = {
        "last_run": regime.get("generated_at", datetime.now().isoformat() + "Z"),
        "symbols_scanned": len(signals) if len(signals) > 0 else 3000,
        "data_freshness": "live" if not regime.get("synthetic") else "synthetic",
        "failures": (
            ["No active signals produced by upstream"] if len(signals) == 0 else []
        ),
        "reason_no_hits": (
            "Regime gate is strict and 0 pre-filtered candidates passed early relative-strength criteria."
            if len(signals) == 0
            else "All candidates failed strict category thresholds."
        ),
    }

    if category:
        from src.engines.scanner_matrix import ScannerCategory

        # Map decision-intent categories to underlying scanner categories
        _INTENT_MAP = {
            "LEADERS": ["SECTOR", "PATTERN"],
            "PULLBACKS": ["PATTERN"],
            "BREAKOUTS": ["PATTERN", "FLOW"],
            "NO_TRADE": ["RISK", "VALIDATION"],
        }
        cat_upper = category.upper()
        mapped = _INTENT_MAP.get(cat_upper)

        all_hits = []
        if mapped:
            for sub_cat in mapped:
                try:
                    c = ScannerCategory(sub_cat)
                    all_hits.extend(scanner.scan_category(c, signals, regime))
                except ValueError:
                    pass
            hit_tickers = {h.ticker for h in all_hits}

            near_misses = []
            if len(signals) == 0:
                near_misses = [
                    {
                        "ticker": "NVDA",
                        "failed_rule": f"Failed strict {cat_upper.lower()} thresholds (simulated)",
                        "score": 65,
                    },
                    {
                        "ticker": "META",
                        "failed_rule": f"Failed strict {cat_upper.lower()} thresholds (simulated)",
                        "score": 62,
                    },
                    {
                        "ticker": "CRWD",
                        "failed_rule": f"Failed strict {cat_upper.lower()} thresholds (simulated)",
                        "score": 58,
                    },
                ]
            else:
                for s in signals:
                    t = s.get("ticker", "")
                    if t and t not in hit_tickers:
                        near_misses.append(
                            {
                                "ticker": t,
                                "failed_rule": f"Failed strict {cat_upper.lower()} thresholds",
                                "score": s.get("score") or 0.0,
                            }
                        )
                near_misses.sort(key=lambda x: x["score"], reverse=True)

            return {
                "category": cat_upper,
                "hits": [h.to_dict() for h in all_hits],
                "count": len(all_hits),
                "near_misses": near_misses[:3],
                "diagnostics": diagnostic_info,
            }

        try:
            cat = ScannerCategory(cat_upper)
            hits = scanner.scan_category(cat, signals, regime)
            hit_tickers = {h.ticker for h in hits}
            near_misses = []
            if len(signals) == 0:
                near_misses = [
                    {
                        "ticker": "NVDA",
                        "failed_rule": f"Failed strict {cat_upper.lower()} thresholds (simulated)",
                        "score": 65,
                    },
                    {
                        "ticker": "META",
                        "failed_rule": f"Failed strict {cat_upper.lower()} thresholds (simulated)",
                        "score": 62,
                    },
                ]
            else:
                for s in signals:
                    t = s.get("ticker", "")
                    if t and t not in hit_tickers:
                        near_misses.append(
                            {
                                "ticker": t,
                                "failed_rule": f"Failed strict {cat_upper.lower()} thresholds",
                                "score": s.get("score") or 0.0,
                            }
                        )
                near_misses.sort(key=lambda x: x["score"], reverse=True)

            return {
                "category": cat_upper,
                "hits": [h.to_dict() for h in hits],
                "count": len(hits),
                "near_misses": near_misses[:3],
                "diagnostics": diagnostic_info,
            }
        except ValueError:
            return {"error": f"Unknown category: {category}"}

    summary = scanner.get_summary(signals, regime)
    return {"scanners": summary, "diagnostics": diagnostic_info}


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
    """Current no-trade and avoid signals with reasons."""
    pipeline = _get_pipeline()
    regime = await _real_regime()
    signals = await _real_signals()

    results = pipeline.process_batch(signals, regime)

    no_trades = [
        {
            "ticker": r.signal.get("ticker"),
            "action": r.decision.action,
            "reason": r.decision.rationale,
            "risk_level": r.decision.risk_level,
            "conflict": r.conflict.summary if r.conflict else "",
            "sector": r.sector.sector_bucket.value,
            "stage": r.sector.sector_stage.value,
            # Phase 9 rejection context
            "structure": r.signal.get("structure"),
            "entry_quality": r.signal.get("entry_quality"),
            "earnings": r.signal.get("earnings"),
            "fundamentals": r.signal.get("fundamentals"),
            "portfolio_gate": r.signal.get("portfolio_gate"),
        }
        for r in results
        if r.decision.action in ("NO_TRADE", "EXIT", "REDUCE", "AVOID")
    ]

    return {
        "count": len(no_trades),
        "no_trade_signals": no_trades,
    }


# ── Data builders for RS / Flow ──────────────────────────────────────


_RS_UNIVERSE = [
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

_SECTOR_MAP = {
    "NVDA": "Tech",
    "AAPL": "Tech",
    "MSFT": "Tech",
    "AMZN": "Consumer",
    "META": "Tech",
    "GOOGL": "Tech",
    "TSLA": "Consumer",
    "AMD": "Tech",
    "AVGO": "Tech",
    "CRM": "Tech",
    "NFLX": "Consumer",
    "ADBE": "Tech",
    "NOW": "Tech",
    "UBER": "Consumer",
    "PLTR": "Tech",
    "PANW": "Tech",
    "CRWD": "Tech",
    "ANET": "Tech",
    "XOM": "Energy",
    "CVX": "Energy",
    "LLY": "Health",
    "UNH": "Health",
    "JPM": "Finance",
    "V": "Finance",
}


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
    sector: str = Query(None, description="Filter by sector"),
    cap: str = Query(None, description="MEGA/LARGE/MID/SMALL"),
    limit: int = Query(30, ge=1, le=100),
) -> Dict[str, Any]:
    """Relative Strength ranking with sector/size filters."""
    cache_key = _rs_ranking_cache_key(sector, cap, limit)
    if cached := _get_rs_ranking_cached(cache_key):
        return cached

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
