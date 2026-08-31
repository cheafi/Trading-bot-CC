"""
CC — Decision Product API (Sprint 57)
======================================
Transforms raw signals into decision-ready endpoints:
  /api/v7/today          — Market regime + top picks + filter funnel + action
  /api/v7/opportunities  — Ranked candidates with why-now/why-not/action
  /api/v7/filter-funnel  — Universe → actionable pipeline visualization
  /api/v7/signal-card/{ticker} — Decision-grade signal card
"""

import asyncio
import logging
import time
from datetime import date, datetime, timedelta, timezone
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, Depends, HTTPException, Query, Request

from src.api.deps import sanitize_for_json, verify_api_key
from src.services.regime_service import get_regime as _fetch_regime
from src.utils.numeric_parse import parse_ratio

logger = logging.getLogger(__name__)


def _signal_rr(signal: dict, default: float = 0.0) -> float:
    return parse_ratio(signal.get("risk_reward"), default) or default


router = APIRouter(tags=["decision-product"])

# ════════════════════════════════════════════════════════════════════
# P2: Module-level engine singletons — instantiated ONCE, persist across requests
# ════════════════════════════════════════════════════════════════════

_council_instance = None
_rs_engine_instance = None
_learning_loop_instance = None
_meta_instance = None
_today_cache: Optional[Dict[str, Any]] = None
_today_cache_ts: float = 0.0
_today_lock = asyncio.Lock()
_TODAY_CACHE_TTL = 120.0
_TODAY_SCAN_TIMEOUT = 3.0
_RESEARCH_CACHE_TTL = 20.0
_RESEARCH_CACHE_MAX_KEYS = 16
_research_cache: Dict[str, Dict[str, Any]] = {}


def _research_cache_get(key: str) -> Optional[Dict[str, Any]]:
    entry = _research_cache.get(key)
    if not entry:
        return None
    if time.time() - entry["ts"] < _RESEARCH_CACHE_TTL:
        return entry["data"]
    return None


def _research_cache_set(key: str, data: Dict[str, Any]) -> None:
    _research_cache[key] = {"data": data, "ts": time.time()}
    if len(_research_cache) > _RESEARCH_CACHE_MAX_KEYS:
        oldest = min(_research_cache.items(), key=lambda item: item[1]["ts"])[0]
        _research_cache.pop(oldest, None)


def _stale_today_payload(reason: str) -> Dict[str, Any]:
    now = datetime.now(timezone.utc)
    return {
        "date": now.strftime("%Y-%m-%d"),
        "narrative": "Decision board is warming up — using degraded fast path.",
        "market_regime": {
            "label": "NEUTRAL",
            "risk_state": "NEUTRAL",
            "should_trade": False,
            "confidence": 0.0,
            "tradeability": "WAIT",
            "summary": reason,
            "trend": "SIDEWAYS",
            "volatility": "NORMAL",
            "score": 0,
            "vix": None,
            "breadth": None,
            "entropy": None,
        },
        "market_pulse": {},
        "top_5": [],
        "filter_funnel": {
            "universe": 0,
            "signals_triggered": 0,
            "score_above_6": 0,
            "actionable_above_7": 0,
            "high_conviction_above_8": 0,
        },
        "best_setup_family": None,
        "family_breakdown": {},
        "avoid": [reason],
        "what_changed": [reason],
        "event_risks": [],
        "sector_summary": {},
        "action_summary": {},
        "ai_narrative": None,
        "trust": {
            "mode": "PAPER",
            "source": "today-degraded",
            "freshness": "DEGRADED",
            "stale": True,
            "reason": reason,
            "ai_powered": False,
            "as_of": now.isoformat() + "Z",
        },
        "generated_at": now.isoformat() + "Z",
    }


def _cached_today_payload(reason: str) -> Optional[Dict[str, Any]]:
    if not _today_cache:
        return None
    payload = dict(_today_cache)
    trust = dict(payload.get("trust") or {})
    trust.update({"source": "today-cache", "stale": True, "reason": reason})
    payload["trust"] = trust
    return payload


def _council(request=None):
    """Return ExpertCouncil — prefers app.state singleton over module-level."""
    global _council_instance
    # Prefer the app-level singleton (survives HMR, accumulates state)
    if request is not None:
        council = getattr(
            getattr(request, "app", None) and request.app.state, "expert_council", None
        )
        if council is not None:
            return council
    if _council_instance is None:
        from src.engines.expert_council import ExpertCouncil

        _council_instance = ExpertCouncil()
    return _council_instance


def _rs_engine():
    """RSRankingEngine singleton."""
    global _rs_engine_instance
    if _rs_engine_instance is None:
        from src.engines.rs_ranking import RSRankingEngine

        _rs_engine_instance = RSRankingEngine()
    return _rs_engine_instance


def _learning_loop():
    """LearningLoopPipeline singleton."""
    global _learning_loop_instance
    if _learning_loop_instance is None:
        from src.engines.learning_loop import LearningLoopPipeline

        _learning_loop_instance = LearningLoopPipeline()
    return _learning_loop_instance


def _meta():
    """MetaEnsemble singleton."""
    global _meta_instance
    if _meta_instance is None:
        from src.engines.meta_ensemble import MetaEnsemble

        _meta_instance = MetaEnsemble()
    return _meta_instance


# ══════════════════════════════════════════════════════════════════════
# Helpers
# ══════════════════════════════════════════════════════════════════════


def _timing_label(distance_to_pivot_pct: float) -> str:
    """Classify timing relative to pivot/entry zone."""
    if distance_to_pivot_pct < 1.0:
        return "NEAR_PIVOT"
    elif distance_to_pivot_pct < 3.0:
        return "EARLY"
    elif distance_to_pivot_pct < 7.0:
        return "ON_TIME"
    elif distance_to_pivot_pct < 12.0:
        return "EXTENDED"
    else:
        return "LATE"


def _action_from_signal(signal: dict, regime_ok: bool) -> tuple[str, str]:
    """Derive action + reason from signal context."""
    score = signal.get("score", 0)
    rr = _signal_rr(signal)
    timing = signal.get("_timing", "ON_TIME")
    strategy = signal.get("strategy", "unknown")

    if not regime_ok:
        return "WAIT", "Market regime unfavorable"
    if score >= 8.0 and rr >= 2.5 and timing in ("NEAR_PIVOT", "EARLY"):
        return "BUY", f"Strong {strategy} setup near pivot"
    if score >= 7.0 and rr >= 2.0:
        return "BUY_ON_DIP", f"Good {strategy} — wait for pullback to entry"
    if score >= 6.0:
        return "WATCH", f"Decent {strategy} — monitor for confirmation"
    if timing == "LATE":
        return "AVOID", "Extended — chase risk too high"
    return "WATCH", "Score below action threshold"


def _why_now(signal: dict) -> List[str]:
    """Generate why-now evidence list."""
    reasons = []
    rsi = signal.get("rsi", 50)
    vol_r = signal.get("vol_ratio", 1.0)
    regime = signal.get("regime", "SIDEWAYS")
    strategy = signal.get("strategy", "")

    if regime == "UPTREND":
        reasons.append("Trending above 50/200 SMA")
    if 40 < rsi < 65:
        reasons.append(f"RSI {rsi:.0f} — healthy momentum zone")
    elif rsi < 35:
        reasons.append(f"RSI {rsi:.0f} — oversold bounce candidate")
    if vol_r > 1.5:
        reasons.append(f"Volume {vol_r:.1f}x average — institutional interest")
    rr = _signal_rr(signal)
    if rr >= 3.0:
        reasons.append(f"R:R {rr:.1f} — excellent risk/reward")
    if strategy == "breakout":
        reasons.append("Near 20-day high — breakout structure")
    elif strategy == "swing":
        reasons.append("Pullback to support — swing entry zone")
    elif strategy == "momentum":
        reasons.append("Moving averages aligned — momentum confirmed")

    return reasons or ["Signal triggered by quantitative model"]


def _why_not(signal: dict) -> List[str]:
    """Generate risk/warning reasons."""
    warnings = []
    rsi = signal.get("rsi", 50)
    atr_pct = signal.get("atr_pct", 1.0)
    vol_r = signal.get("vol_ratio", 1.0)
    rr = _signal_rr(signal, 0.0)

    if rsi > 75:
        warnings.append(f"RSI {rsi:.0f} — overbought risk")
    if atr_pct > 4.0:
        warnings.append(f"ATR {atr_pct:.1f}% — high volatility")
    if vol_r < 0.7:
        warnings.append("Volume below average — weak conviction")
    if rr < 1.5:
        warnings.append(f"R:R only {rr:.1f} — thin margin")

    return warnings


def _invalidation(signal: dict) -> str:
    """Describe what invalidates this setup."""
    stop = signal.get("stop_price", 0)
    strategy = signal.get("strategy", "")
    if strategy == "breakout":
        return f"Close below ${stop:.2f} (breakout failure)"
    elif strategy == "swing":
        return f"Close below ${stop:.2f} (swing support lost)"
    elif strategy == "momentum":
        return f"Close below ${stop:.2f} (momentum broken)"
    return f"Stop at ${stop:.2f}"


def _position_hint(signal: dict, regime_ok: bool) -> str:
    """Suggest position sizing approach."""
    score = signal.get("score", 0)
    if not regime_ok:
        return "NO_POSITION"
    if score >= 8.5:
        return "STANDARD"
    elif score >= 7.0:
        return "STARTER"
    elif score >= 5.5:
        return "WATCH_ONLY"
    return "NO_POSITION"


def _setup_family(strategy: str) -> str:
    """Map strategy to user-friendly setup family."""
    families = {
        "momentum": "龍頭 Momentum",
        "breakout": "突破 Breakout",
        "swing": "擺動 Swing",
        "mean_reversion": "均值回歸 Mean Reversion",
    }
    return families.get(strategy, strategy.title())


async def _cross_asset_for_today(
    request: Request,
    *,
    market_regime: Dict[str, Any],
    should_trade: bool,
) -> Dict[str, Any]:
    import asyncio

    try:
        from src.services.cross_asset_confirmation import (
            build_cross_asset_confirmation,
        )

        return await asyncio.wait_for(
            build_cross_asset_confirmation(
                request,
                regime=market_regime,
                should_trade=should_trade,
            ),
            timeout=12.0,
        )
    except asyncio.TimeoutError:
        logger.debug("cross_asset_confirmation timed out")
        return {
            "alignment": "unknown",
            "summary": "Cross-asset proxies slow — retry",
            "assets": [],
            "confirms": [],
            "conflicts": [],
        }
    except Exception:
        logger.debug("cross_asset_confirmation failed", exc_info=True)
        return {"alignment": "unknown", "summary": "Cross-asset data unavailable"}


def _build_score_reconciliation_for_today(
    rows: list,
    *,
    cross_asset: Optional[Dict[str, Any]] = None,
    deploy_open: bool = False,
    tradeability: str = "WAIT",
    brief_stale: bool = False,
) -> Dict[str, Any]:
    from src.services.score_families import build_score_reconciliation

    return build_score_reconciliation(
        rows,
        cross_asset=cross_asset,
        deploy_open=deploy_open,
        tradeability=tradeability,
        brief_stale=brief_stale,
    )


# ══════════════════════════════════════════════════════════════════════
# /api/v7/today — Decision Homepage
# ══════════════════════════════════════════════════════════════════════


def _scan_cache_has_recs(request: Request) -> bool:
    sc = getattr(request.app.state, "scan_cache", None) or {}
    return bool(sc.get("recs"))


@router.get("/api/v7/warmup/brief-board")
async def warmup_brief_board(limit: int = Query(30, ge=1, le=100)):
    """Fast local brief board for UI bootstrap — monitor only, no deploy authority."""
    from src.services.playbook_board_fallback import build_compressed_fallback

    payload = build_compressed_fallback(
        limit, reason="warmup brief board — monitor only"
    )
    return payload


@router.get("/api/v7/today")
async def today_summary(request: Request, _: bool = Depends(verify_api_key)):
    """Decision homepage: regime + top 5 + filter funnel + action guidance.

    This is the first thing a trader should see — answers:
    "Should I trade today? What are the best opportunities? What to avoid?"
    """
    global _today_cache, _today_cache_ts
    now_ts = time.time()
    if _today_cache and now_ts - _today_cache_ts < _TODAY_CACHE_TTL:
        trust = _today_cache.get("trust") or {}
        if trust.get("stale") and _scan_cache_has_recs(request):
            _today_cache = None
            _today_cache_ts = 0.0
        else:
            return await _refresh_today_authority(request, _today_cache)
    if _today_lock.locked():
        cached = _cached_today_payload("fresh scan already running")
        if cached:
            return await _refresh_today_authority(request, cached)
        return _stale_today_payload("fresh scan already running")

    async with _today_lock:
        now_ts = time.time()
        if _today_cache and now_ts - _today_cache_ts < _TODAY_CACHE_TTL:
            return await _refresh_today_authority(request, _today_cache)

    # 1. Market Regime
    regime_state = await _fetch_regime(request)
    regime_label = getattr(regime_state, "regime", "NEUTRAL")
    should_trade = getattr(regime_state, "should_trade", False)
    confidence = getattr(regime_state, "confidence", 0.5)
    vix_val = getattr(regime_state, "vix", 18.0)
    breadth = getattr(regime_state, "breadth_pct", 0.50)
    breadth_val = (
        round(float(breadth) * 100) if float(breadth) <= 1.0 else round(float(breadth))
    )
    entropy = getattr(regime_state, "entropy", 1.0)

    # Map regime fields properly
    trend_map = {
        "uptrend": "UPTREND",
        "downtrend": "DOWNTREND",
        "sideways": "SIDEWAYS",
    }
    vol_map = {
        "low_vol": "LOW",
        "normal_vol": "NORMAL",
        "elevated_vol": "ELEVATED",
        "high_vol": "HIGH",
        "crisis_vol": "CRISIS",
    }
    trend_label = trend_map.get(
        getattr(regime_state, "trend_regime", "sideways"), "SIDEWAYS"
    )
    vol_label = vol_map.get(
        getattr(regime_state, "volatility_regime", "normal_vol"),
        "NORMAL",
    )
    # `confidence == confidence` is False for NaN — guards int(NaN) on degraded data.
    _conf_ok = isinstance(confidence, (int, float)) and confidence == confidence
    score = max(
        0,
        min(
            100,
            int(confidence * 100) if _conf_ok else 50,
        ),
    )

    risk_state = (
        "RISK_ON"
        if regime_label == "RISK_ON"
        else ("RISK_OFF" if regime_label == "RISK_OFF" else "NEUTRAL")
    )

    # 2. Market pulse — fetch indices/sectors from live endpoint
    market_pulse = {}
    try:
        _LIVE_INDICES = request.app.state.live_indices
        _LIVE_SECTORS = request.app.state.live_sectors

        mds = request.app.state.market_data
        # Quick lookup from cache if available — fetch all in parallel
        idx_data = []
        sec_data = []

        async def _fetch_idx(sym, name):
            try:
                hist = await mds.get_history(sym, period="5d", interval="1d")
                if hist is not None and len(hist) >= 2:
                    c = "Close" if "Close" in hist.columns else "close"
                    cur = float(hist[c].iloc[-1])
                    prev = float(hist[c].iloc[-2])
                    chg = round((cur / prev - 1) * 100, 2)
                    return {
                        "symbol": sym,
                        "name": name,
                        "price": round(cur, 2),
                        "change_pct": chg,
                    }
            except Exception:
                pass
            return None

        async def _fetch_sec(sym, name):
            try:
                hist = await mds.get_history(sym, period="5d", interval="1d")
                if hist is not None and len(hist) >= 2:
                    c = "Close" if "Close" in hist.columns else "close"
                    cur = float(hist[c].iloc[-1])
                    prev = float(hist[c].iloc[-2])
                    chg = round((cur / prev - 1) * 100, 2)
                    return {"symbol": sym, "name": name, "change_pct": chg}
            except Exception:
                pass
            return None

        import asyncio as _aio

        idx_results, sec_results = await _aio.wait_for(
            _aio.gather(
                _aio.gather(*[_fetch_idx(sym, name) for sym, name in _LIVE_INDICES]),
                _aio.gather(
                    *[_fetch_sec(sym, name) for sym, name in _LIVE_SECTORS[:6]]
                ),
            ),
            timeout=2.5,
        )
        idx_data = [r for r in idx_results if r]
        sec_data = sorted(
            [r for r in sec_results if r], key=lambda x: x["change_pct"], reverse=True
        )
        market_pulse = {
            "indices": idx_data,
            "sector_leaders": sec_data[:3],
            "sector_laggards": (sec_data[-3:][::-1] if len(sec_data) > 3 else []),
        }
    except Exception as exc:
        logger.debug("Market pulse unavailable: %s", exc)

    # 3. Scanner cache (app.state.scan_cache aliases module _scan_cache from lifespan)
    from src.services.cc_live_policy import (
        build_live_unavailable_today_payload,
        cc_live_data_only_enabled,
    )

    live_only = cc_live_data_only_enabled()
    scanner_degraded = False
    scanner_reason = ""
    scan_cache = getattr(request.app.state, "scan_cache", None) or {}
    scanned = list(scan_cache.get("recs", []))[:50]
    scores = dict(scan_cache.get("scores", {}) or {})
    if not scanned:
        scanner_degraded = True
        scanner_reason = "scanner cache warming"
    if scores.get("_degraded"):
        scanner_degraded = True
        scanner_reason = str(scores.get("_reason") or "scanner degraded")

    if live_only and scanner_degraded:
        try:
            live_recs, live_scores = await asyncio.wait_for(
                request.app.state.scan_signals(limit=50),
                timeout=_TODAY_SCAN_TIMEOUT,
            )
            if live_recs:
                scanned = list(live_recs)[:50]
                scores = dict(live_scores or {})
                scanner_degraded = False
                scanner_reason = ""
            else:
                try:
                    from src.api.app_state import get_engine

                    engine = get_engine(request.app)
                    if engine and not bool(getattr(engine, "_running", False)):
                        await asyncio.wait_for(engine.run_one_cycle(), timeout=30.0)
                        scan_cache = (
                            getattr(request.app.state, "scan_cache", None) or {}
                        )
                        scanned = list(scan_cache.get("recs", []))[:50]
                        scores = dict(scan_cache.get("scores", {}) or {})
                        if scanned:
                            scanner_degraded = False
                            scanner_reason = ""
                except Exception as exc:
                    logger.debug("live-only engine cycle failed: %s", exc)
        except Exception as exc:
            logger.debug("live-only scan_signals failed: %s", exc)

        if scanner_degraded and not scanned:
            reason = (
                scanner_reason
                or "live-only mode — scanner empty after live scan and engine cycle"
            )
            return build_live_unavailable_today_payload(reason=reason)

    # 4. Filter funnel
    universe = len(getattr(request.app.state, "_scan_watchlist", []))
    if universe == 0:
        universe = len(getattr(request.app.state, "scan_watchlist", []))

    actionable = len([s for s in scanned if s.get("score", 0) >= 7.0])

    # 5. Top 5 ranked — sector-adaptive pipeline
    # 5. Top 5 ranked — Expert Council pipeline
    council = _council(request)
    regime_ctx = {
        "regime": trend_label,
        "volatility": vol_label,
        "should_trade": should_trade,
        "vix": vix_val,
        "breadth": breadth,
        "entropy": entropy,
    }
    council_results = council.evaluate_batch(scanned, regime_ctx)
    sector_summary = council.pipeline.get_sector_summary(
        [cr.pipeline for cr in council_results]
    )
    action_summary = council.pipeline.get_action_summary(
        [cr.pipeline for cr in council_results]
    )

    from src.services.decision_truth_model import (
        _score as _fit_score,
    )
    from src.services.decision_truth_model import (
        build_avoid_grouped,
        build_bucket_quality_summary,
        build_honest_funnel,
        build_three_layer_model,
        enrich_opportunity_row,
        is_execution_ready,
        refine_action,
        sector_rank_adjustment,
    )

    funnel = build_honest_funnel(
        universe=universe,
        scanned=scanned,
        council_results=council_results,
    )
    execution_ready_count = funnel.get("execution_ready_setups", 0)
    pilot_ready_count = funnel.get("pilot_eligible_setups", 0)
    council_high_8 = funnel.get("high_conviction_above_8", 0)
    avoid_grouped = build_avoid_grouped(council_results)
    bucket_quality = build_bucket_quality_summary(council_results)

    _ACTION_SORT = {
        "TRADE": 0,
        "PILOT": 1,
        "WATCH": 2,
        "WAIT": 3,
        "AVOID": 4,
        "NO_TRADE": 5,
    }

    sector_leaders = market_pulse.get("sector_leaders") or []
    sector_laggards = market_pulse.get("sector_laggards") or []

    def _council_sort_key(cr: Any) -> tuple:
        act = refine_action(cr)
        pr = cr.pipeline
        adj_row = {
            "sector_type": pr.sector.sector_bucket.value,
            "leader": pr.sector.leader_status.value,
        }
        adj = sector_rank_adjustment(
            adj_row,
            sector_leaders=sector_leaders,
            sector_laggards=sector_laggards,
        )
        return (_ACTION_SORT.get(act, 9), -(_fit_score(cr) + adj))

    sorted_council = sorted(council_results, key=_council_sort_key)

    top5 = []
    seen_tickers = set()
    for cr in sorted_council:
        pr = cr.pipeline
        sig = pr.signal
        ticker = sig.get("ticker", "")
        if ticker in seen_tickers:
            continue
        seen_tickers.add(ticker)

        row = {
            "rank": len(top5) + 1,
            "ticker": ticker,
            "strategy": _setup_family(sig.get("strategy", "")),
            "score": pr.fit.final_score,
            "grade": pr.fit.grade,
            "timing": _timing_label(
                abs(sig.get("entry_price", 0) - sig.get("stop_price", 0))
                / max(sig.get("entry_price", 1), 1)
                * 100
            ),
            "action": refine_action(cr),
            "action_reason": pr.decision.rationale,
            "why_now": ([pr.explanation.why_now] if pr.explanation.why_now else []),
            "entry_price": sig.get("entry_price", 0),
            "target_price": sig.get("target_price", 0),
            "stop_price": sig.get("stop_price", 0),
            "risk_reward": sig.get("risk_reward", 0)
            or getattr(pr.decision, "risk_reward", None)
            or getattr(pr.decision, "risk_reward_ratio", None)
            or 0,
            "rsi": sig.get("rsi", 0),
            "invalidation": getattr(pr.explanation, "invalidation", None)
            or _invalidation(sig),
            "position_hint": _position_hint(sig, should_trade),
            "sector_bucket": pr.sector.sector_bucket.value,
            "final_conf": round(pr.confidence.final, 2),
            "confidence_breakdown": pr.confidence.to_dict(),
            "decision": pr.decision.to_dict(),
            "explanation": pr.explanation.to_dict(),
            "expert_council": cr.verdict.to_dict(),
        }
        if row["action"] == "PILOT":
            row["why_pilot"] = pr.decision.why_pilot or ""
            row["upgrade_to_trade"] = pr.decision.upgrade_to_trade or ""
            row["downgrade_to_watch_avoid"] = pr.decision.downgrade_to_watch_avoid or ""
        top5.append(
            enrich_opportunity_row(
                cr,
                row,
                sector_leaders=sector_leaders,
                sector_laggards=sector_laggards,
            )
        )
        if len(top5) >= 5:
            break

    from src.services.decision_truth_model import build_runner_up_comparison

    for i, row in enumerate(top5):
        if i < len(top5) - 1:
            nxt = top5[i + 1]
            cmp_row = build_runner_up_comparison(row, nxt)
            if cmp_row:
                row["runner_up"] = cmp_row

    # 6. Full candidate list (for table)
    cands = []
    seen_cands = set()
    for cr in council_results:
        pr = cr.pipeline
        sig = pr.signal
        tker = sig.get("ticker", "")
        if tker in seen_cands:
            continue
        seen_cands.add(tker)
        cands.append(
            {
                "ticker": tker,
                "score": pr.fit.final_score,
                "action_tier": pr.decision.action,
                "sector": sig.get("sector", ""),
                "price": sig.get("entry_price", str(sig.get("current_price", 0))),
                "target": sig.get("target_price", 0),
                "stop_loss": sig.get("stop_price", 0),
                "rr": sig.get("risk_reward", 0)
                or getattr(pr.decision, "risk_reward", None)
                or getattr(pr.decision, "risk_reward_ratio", None)
                or 0,
                "strategy": _setup_family(sig.get("strategy", "")),
                "reason": pr.decision.rationale,
            }
        )

    # 6. Best setup family today
    family_counts: Dict[str, int] = {}
    family_scores: Dict[str, float] = {}
    for sig in scanned:
        fam = _setup_family(sig.get("strategy", ""))
        family_counts[fam] = family_counts.get(fam, 0) + 1
        family_scores[fam] = family_scores.get(fam, 0) + sig.get("score", 0)

    best_family = None
    if family_scores:
        best_family = max(
            family_scores,
            key=lambda k: family_scores[k] / max(family_counts[k], 1),
        )

    # 7. Avoid list placeholder — filled after tradeability (section 9)
    avoid: list = []
    avoid_now: list = []

    # 8. Narrative — morning-briefing style
    idx_summary = ""
    if market_pulse.get("indices"):
        parts = []
        for ix in market_pulse["indices"][:3]:
            sign = "+" if ix["change_pct"] >= 0 else ""
            parts.append(f"{ix['name']} {sign}{ix['change_pct']:.2f}%")
        idx_summary = ", ".join(parts)

    # Stricter summary generation based on PM feedback
    trade_count = sum(1 for cr in council_results if is_execution_ready(cr))

    if not should_trade:
        narrative = (
            f"Risk-off regime detected. VIX at {vix_val:.0f}. "
            f"No new positions recommended. "
            f"Protect existing capital."
        )
    elif trade_count >= 3:
        narrative = (
            f"Active scanning day. {idx_summary}. "
            f"Found {trade_count} highly actionable (TRADE) setups out of {actionable} above 7.0. "
            f"Require strict confidence guards. "
            f"Best family: {best_family or 'Mixed'}."
        )
    elif trade_count >= 1:
        narrative = (
            f"Selective opportunity day. {idx_summary}. "
            f"Found {trade_count} TRADE-ready setup(s). "
            f"Wait for rigorous confirmation. "
            f"Regime: {trend_label.lower()}."
        )
    elif actionable >= 3:
        narrative = (
            f"Wait/Watch environment. {idx_summary}. "
            f"Found {actionable} setups but NONE triggered TRADE thresholds. "
            f"Patience required until entry criteria are met."
        )
    elif actionable >= 1:
        narrative = (
            f"Wait/Watch environment. {idx_summary}. "
            f"Found 1 setup but NO strong actionable setups. "
            f"Review watchlists."
        )
    else:
        narrative = (
            f"No actionable setups today. {idx_summary}. "
            f"The scanner is being selective — "
            f"good setups are rare by design. "
            f"Review the watchlist for developing patterns."
        )

    # 9. Tradeability — council-validated, not raw scanner ≥8 alone
    breadth_val = breadth * 100 if breadth <= 1 else breadth
    if not should_trade:
        tradeability = "NO_TRADE"
    else:
        tradeability = "WAIT"

    from src.services.today_insights import build_avoid_now_engine

    avoid_now = build_avoid_now_engine(
        regime_label=regime_label,
        should_trade=should_trade,
        tradeability=tradeability,
        vix=vix_val,
        breadth=breadth_val,
        confidence=confidence,
        council_results=council_results,
        scanned=scanned,
        top5=top5,
    )
    avoid = [
        f"{a.get('ticker', '—')}: {a.get('reason')}"
        if a.get("ticker") != "—"
        else a.get("reason", "")
        for a in avoid_now
    ]
    if not avoid:
        if not should_trade:
            avoid.append("All new positions — regime unfavorable")
        if regime_label == "RISK_OFF":
            avoid.append("Aggressive breakouts — risk-off environment")
        if vix_val > 30:
            avoid.append(f"VIX at {vix_val:.0f} — size down or sit out")

    # 10. What Changed
    what_changed = []
    if regime_label == "RISK_OFF":
        what_changed.append("Regime shifted to RISK_OFF — defensive posture")
    if council_high_8 >= 1:
        what_changed.append(
            f"{council_high_8} council-validated high-score setup(s) (fit ≥8.0)"
        )
    if raw_hi := funnel.get("raw_scanner_above_8", 0):
        if raw_hi != council_high_8:
            what_changed.append(
                f"Scanner raw ≥8: {raw_hi} — council validated: {council_high_8}"
            )
    if best_family:
        what_changed.append(f"Leading setup family: {best_family}")
    # Sector movers
    leaders = market_pulse.get("sector_leaders", [])
    if leaders and leaders[0].get("change_pct", 0) > 1.0:
        ldr = leaders[0]
        what_changed.append(f"Sector leader: {ldr['name']} +{ldr['change_pct']:.1f}%")
    laggards = market_pulse.get("sector_laggards", [])
    if laggards and laggards[0].get("change_pct", 0) < -1.0:
        what_changed.append(
            f"Sector laggard: {laggards[0]['name']} {laggards[0]['change_pct']:.1f}%"
        )

    # 11. Event risk
    event_risks = []
    if vix_val > 25:
        event_risks.append(f"VIX at {vix_val:.0f} — elevated fear")
    if breadth < 0.35:
        event_risks.append(f"Breadth {breadth:.0%} — narrow participation")
    if not should_trade:
        event_risks.append("Regime guard active — no new entries")
    if entropy < 0.5:
        event_risks.append("Low entropy — regime reading uncertain")

    now = datetime.now(timezone.utc)

    from src.services.today_insights import (
        best_net_edge_from_opportunities,
        build_evidence_badges,
        build_monitor_triggers,
        build_near_miss_candidates,
        build_no_setup_diagnosis,
        build_quant_cluster_hints,
        build_regime_wait_explanation,
        build_sleeve_summary,
        build_todays_decision,
        build_unlock_deploy,
        load_equity_dd_pct_for_hints,
        merge_brief_board_fallback,
        resolve_book_dd_utilization_for_hints,
    )

    top5_tickers = {x["ticker"] for x in top5 if x.get("ticker")}
    near_miss = build_near_miss_candidates(council_results, top5_tickers, limit=8)
    top5, near_miss, used_brief_fallback = merge_brief_board_fallback(
        top5,
        near_miss,
        scanner_degraded=scanner_degraded,
    )
    if used_brief_fallback:
        top5_tickers = {x["ticker"] for x in top5 if x.get("ticker")}
        funnel = {
            **funnel,
            "note": "Brief fallback — scanner cache empty; WATCH rows are not deployable",
        }
        if not scanner_reason:
            scanner_reason = "scanner cache empty — brief watch fallback"
        narrative = (
            "Morning brief fallback — live scanner unavailable. "
            "Informational watch candidates only; not execution-grade."
        )
    validated_count = int(funnel.get("watch_qualified_setups") or 0)
    no_setup_diagnosis = build_no_setup_diagnosis(
        council_results,
        scanner_degraded=scanner_degraded,
        tradeability=tradeability,
        should_trade=should_trade,
        validated_count=validated_count,
        deployable_count=execution_ready_count,
    )
    regime_wait_explanation = build_regime_wait_explanation(
        trend_label=trend_label,
        tradeability=tradeability,
        trade_count=trade_count,
        actionable=actionable,
        should_trade=should_trade,
        vix=vix_val,
        breadth=breadth * 100 if breadth <= 1 else breadth,
    )
    sleeve_summary: Dict[str, Any] = {
        "cards": [],
        "note": "lazy-load via /api/fund-lab/cards",
    }
    fund_cards: List[Dict[str, Any]] = []
    fund_cache = getattr(request.app.state, "fund_cards_cache", None)
    if isinstance(fund_cache, dict) and fund_cache.get("cards"):
        fund_cards = fund_cache.get("cards") or []
    else:
        try:
            from src.api.routers.funds import _build_payload

            pl = await _build_payload(request, benchmark="SPY", period="1y", top_n=5)
            fund_cards = pl.get("cards") or []
            fund_cache = getattr(request.app.state, "fund_cards_cache", None)
        except Exception:
            logger.debug("fund cards preload for today failed", exc_info=True)
    if fund_cards:
        sleeve_summary = build_sleeve_summary(
            fund_cards,
            regime=regime_label,
            sector_leaders=market_pulse.get("sector_leaders"),
        )

    def _row_for_action(cr: Any) -> Dict[str, Any]:
        pr = cr.pipeline
        sig = pr.signal
        return {
            "ticker": sig.get("ticker", ""),
            "action": refine_action(cr),
            "final_conf": round(float(pr.confidence.final), 2),
            "score": pr.fit.final_score,
            "entry_price": sig.get("entry_price"),
            "stop_price": sig.get("stop_price"),
            "risk_reward": sig.get("risk_reward")
            or getattr(pr.decision, "risk_reward", None)
            or getattr(pr.decision, "risk_reward_ratio", None),
            "upgrade_trigger": pr.decision.entry_trigger
            or getattr(pr.explanation, "upgrade_trigger", None),
            "invalidation": getattr(pr.explanation, "invalidation", None)
            or _invalidation(sig),
            "sector_type": pr.sector.sector_bucket.value,
            "why_pilot": pr.decision.why_pilot or "",
            "data_conf": float(pr.confidence.data),
            "thesis_conf": round(float(pr.confidence.thesis), 2),
            "timing_conf": round(float(pr.confidence.timing), 2),
            "exec_conf": round(float(pr.confidence.execution), 2),
            "leader": pr.sector.leader_status.value,
            "execution_ready": is_execution_ready(cr),
        }

    all_opps_for_action = [_row_for_action(cr) for cr in sorted_council]
    top5_for_action = all_opps_for_action[:12]
    try:
        from src.api.app_state import get_engine
        from src.services.best_action import build_best_action, compute_theme_overlap
        from src.services.execution_readiness import build_execution_readiness
        from src.services.ibkr_service import get_ibkr_service
        from src.services.runtime_truth import (
            engine_runtime_snapshot,
            merge_execution_runtime_truth,
        )

        ibkr_st = get_ibkr_service().status()
        engine = get_engine(request.app)
        runtime = engine_runtime_snapshot(engine)
        eng_running = bool(runtime.get("running"))
        eng_breaker = bool(runtime.get("circuit_breaker"))
        bracket_ready = bool(
            top5_for_action
            and top5_for_action[0].get("entry_price")
            and top5_for_action[0].get("stop_price")
        )
        execution_readiness = build_execution_readiness(
            ibkr_connected=bool(ibkr_st.get("connected")),
            ibkr_mode=ibkr_st.get("mode") or "paper",
            bracket_ready=bracket_ready,
            portfolio_source="manual",
            engine_running=eng_running,
            circuit_breaker=eng_breaker,
        )
        execution_readiness = merge_execution_runtime_truth(
            execution_readiness,
            engine=engine,
        )
        best_action = build_best_action(
            top5_for_action,
            tradeability=tradeability,
            should_trade=should_trade,
            regime_label=regime_label,
            ibkr_connected=bool(ibkr_st.get("connected")),
            ibkr_mode=ibkr_st.get("mode") or "paper",
            source="decision_engine",
            stale=scanner_degraded,
            as_of=now.isoformat() + "Z",
        )
        overlap_warning = compute_theme_overlap(top5_for_action)
    except Exception:
        logger.debug("today best_action/execution failed", exc_info=True)
        best_action = {}
        overlap_warning = {"warnings": [], "level": "low"}
        execution_readiness = {}

    bracket_ready = bool(
        top5 and top5[0].get("entry_price") and top5[0].get("stop_price")
    )
    ibkr_connected = bool(
        (best_action.get("execution_readiness") or {}).get("ibkr_connected")
    )
    decision_model = build_three_layer_model(
        should_trade=should_trade,
        trend_label=trend_label,
        tradeability=tradeability,
        vix=vix_val,
        breadth=breadth_val,
        council_results=council_results,
        execution_ready=execution_ready_count,
        pilot_ready=pilot_ready_count,
        ibkr_connected=ibkr_connected,
        bracket_ready=bracket_ready,
    )
    if should_trade:
        tradeability = decision_model.get("honest_tradeability", tradeability)

    from src.services.decision_truth_model import (
        apply_authority_to_rows,
        build_decision_authority,
    )

    eng_running = bool(
        (execution_readiness or {}).get("engine_running")
        or (best_action.get("execution_readiness") or {}).get("engine_running")
    )
    exec_blocked = bool(
        (execution_readiness or {}).get("circuit_breaker")
        or (best_action.get("execution_readiness") or {}).get("circuit_breaker")
    )
    if not eng_running or not exec_blocked:
        try:
            from src.api.app_state import get_engine
            from src.services.runtime_truth import (
                engine_runtime_snapshot,
                merge_execution_runtime_truth,
            )

            engine = get_engine(request.app)
            if engine:
                execution_readiness = merge_execution_runtime_truth(
                    execution_readiness,
                    engine=engine,
                )
                runtime = engine_runtime_snapshot(engine)
                if not eng_running:
                    eng_running = bool(runtime.get("running"))
                if not exec_blocked:
                    exec_blocked = bool(runtime.get("circuit_breaker"))
        except Exception:
            pass

    decision_authority = build_decision_authority(
        tradeability=tradeability,
        should_trade=should_trade,
        scanner_degraded=scanner_degraded,
        scanner_loading=scanner_degraded and not scanned,
        data_stale=scanner_degraded,
        fallback_brief=used_brief_fallback,
        broker_offline=not ibkr_connected,
        engine_off=not eng_running,
        exec_blocked=exec_blocked,
        trust_source="brief-fallback" if used_brief_fallback else "decision_engine",
        ranked_stale=scanner_degraded,
        council_count=len(council_results),
        deploy_ideas_count=execution_ready_count,
        live_council_count=len(council_results) if not used_brief_fallback else 0,
        live_deploy_count=execution_ready_count if not used_brief_fallback else 0,
    )
    top5 = apply_authority_to_rows(top5, decision_authority)
    all_opps_for_action = apply_authority_to_rows(
        all_opps_for_action, decision_authority
    )
    near_miss = apply_authority_to_rows(near_miss, decision_authority)

    cross_asset_confirmation = await _cross_asset_for_today(
        request,
        market_regime={
            "trend": trend_label,
            "vix": round(vix_val, 1),
            "breadth": round(breadth * 100),
            "should_trade": should_trade,
            "tradeability": tradeability,
        },
        should_trade=should_trade,
    )
    from src.services.index_regime import build_index_regime_for_today

    index_regime_summary = await build_index_regime_for_today(
        request,
        market_regime={
            "trend": trend_label,
            "vix": round(vix_val, 1),
            "breadth": round(breadth * 100),
            "should_trade": should_trade,
            "tradeability": tradeability,
            "volatility": vol_label,
        },
        cross_asset=cross_asset_confirmation,
        funnel=funnel,
    )
    regime_strip = {
        "line": index_regime_summary.get("strip_line")
        or index_regime_summary.get("summary"),
        "posture": index_regime_summary.get("posture"),
        "posture_label": index_regime_summary.get("posture_label"),
        "authority": "monitor_only",
        "data_mode": "regime_filter",
        "degraded": bool(index_regime_summary.get("degraded")),
        "may_authorize_deploy": False,
    }
    equity_dd_pct = None
    if not used_brief_fallback and not scanner_degraded:
        equity_dd_pct = await load_equity_dd_pct_for_hints(request)
    quant_cluster_hints = build_quant_cluster_hints(
        tradeability=tradeability,
        deploy_qualified_count=execution_ready_count,
        best_net_score=best_net_edge_from_opportunities(all_opps_for_action),
        dd_utilization_pct=resolve_book_dd_utilization_for_hints(
            fallback_or_stale=used_brief_fallback or scanner_degraded,
            equity_dd_pct=equity_dd_pct,
        ),
    )
    prior_near_miss: List[Dict[str, Any]] = []
    if not used_brief_fallback:
        try:
            from src.services.playbook_board_fallback import load_playbook_snapshot

            snap = load_playbook_snapshot()
            if snap:
                prior_near_miss = list(snap.get("near_miss") or [])
        except Exception:
            prior_near_miss = []
    monitor_triggers = build_monitor_triggers(
        market_pulse=market_pulse,
        near_miss=near_miss,
        vix=vix_val,
        breadth=breadth * 100 if breadth <= 1 else breadth,
        tradeability=tradeability,
        quant_cluster_hints=quant_cluster_hints,
        prior_near_miss=prior_near_miss or None,
    )

    from src.services.ai_intelligence import (
        attach_row_ai_hints,
        build_ai_intelligence_for_today,
    )

    ai_intel = build_ai_intelligence_for_today(
        market_regime={
            "trend": trend_label,
            "vix": round(vix_val, 1),
            "breadth": round(breadth * 100),
            "should_trade": should_trade,
            "tradeability": tradeability,
        },
        index_regime=index_regime_summary,
        decision_authority=decision_authority,
        quant_cluster_hints=quant_cluster_hints,
        near_miss=near_miss,
        prior_near_miss=prior_near_miss or None,
        monitor_triggers=monitor_triggers,
        top_ranked=top5,
        event_risks=event_risks,
        sleeve_summary=sleeve_summary,
        scanner_degraded=scanner_degraded or used_brief_fallback,
    )
    regime_stack_summary = ai_intel.get("regime_stack_summary") or {}
    allocator_stance = ai_intel.get("allocator_stance") or {}
    ai_reason_codes = ai_intel.get("ai_reason_codes") or []

    _mr_ctx = {
        "trend": trend_label,
        "tradeability": tradeability,
        "breadth": round(breadth * 100),
    }
    all_opps_for_action = attach_row_ai_hints(
        all_opps_for_action,
        market_regime=_mr_ctx,
        index_regime=index_regime_summary,
        event_risks=event_risks,
    )
    top5 = attach_row_ai_hints(
        top5,
        market_regime=_mr_ctx,
        index_regime=index_regime_summary,
        event_risks=event_risks,
    )
    near_miss = attach_row_ai_hints(
        near_miss,
        market_regime=_mr_ctx,
        index_regime=index_regime_summary,
        event_risks=event_risks,
    )

    from src.services.opportunity_pipeline import finalize_opportunity_pipeline
    from src.services.opportunity_quality import (
        build_opportunity_verdict,
        resolve_brief_stale_context,
    )

    brief_ctx = resolve_brief_stale_context(
        used_brief_fallback=used_brief_fallback,
    )
    _quality_stale = scanner_degraded or used_brief_fallback
    _brief_stale = bool(brief_ctx.get("brief_stale"))
    _pipe = finalize_opportunity_pipeline(
        {
            "top_ranked": top5,
            "near_miss": near_miss,
            "opportunities": all_opps_for_action,
            "filter_funnel": funnel,
            "brief_context": brief_ctx,
            "data_stale": _quality_stale,
            "brief_stale": _brief_stale,
            "best_action": best_action,
        },
        source="today",
        index_regime=index_regime_summary,
        tradeability=tradeability,
    )
    top5 = _pipe.get("top_ranked") or top5
    near_miss = _pipe.get("near_miss") or near_miss
    all_opps_for_action = _pipe.get("opportunities") or all_opps_for_action
    _opportunity_verdict = _pipe.get("opportunity_verdict")

    todays_decision = build_todays_decision(
        tradeability=tradeability,
        should_trade=should_trade,
        trend_label=trend_label,
        decision_model=decision_model,
        best_action=best_action,
        opportunities=all_opps_for_action,
        near_miss=near_miss,
        no_setup_diagnosis=no_setup_diagnosis,
        regime_wait_explanation=regime_wait_explanation,
        execution_readiness=execution_readiness,
        event_risks=event_risks,
        narrative=narrative,
        execution_ready_count=execution_ready_count,
        decision_authority=decision_authority,
    )
    from src.services.decision_truth_model import playbook_scan_ranked_count

    unlock_deploy = build_unlock_deploy(
        tradeability=tradeability,
        should_trade=should_trade,
        watch_qualified_count=validated_count,
        deployable_count=execution_ready_count,
        scan_ranked_count=playbook_scan_ranked_count(funnel),
        scanner_degraded=scanner_degraded,
        execution_readiness=execution_readiness,
    )

    from src.services.anti_overtrading import restraint_from_today_context
    from src.services.buffett_judgment import buffett_clarity_strip_for_today
    from src.services.crisis_regime import crisis_strip_for_today
    from src.services.decision_hierarchy import hierarchy_for_dashboard
    from src.services.decision_quality_naval import naval_clarity_strip_for_today
    from src.services.index_fund_judgment import index_fund_posture_strip_for_today
    from src.services.passive_baseline import build_passive_baseline_for_today
    from src.services.principles_engine import principles_posture_for_today
    from src.services.score_families import complexity_verdict
    from src.services.surface_authority import authority_strip_for_today

    restraint = restraint_from_today_context(
        tradeability=tradeability,
        deployable_count=execution_ready_count,
        pilot_ready_count=pilot_ready_count,
        opportunities=all_opps_for_action,
    )
    crisis_regime = crisis_strip_for_today(
        {
            "tradeability": tradeability,
            "vix": round(vix_val, 1),
            "breadth": round(breadth * 100),
            "should_trade": should_trade,
            "entropy": round(entropy, 2),
        },
        decision_model,
        execution_readiness=execution_readiness,
    )
    naval_clarity = naval_clarity_strip_for_today(
        {
            "tradeability": tradeability,
            "vix": round(vix_val, 1),
            "breadth": round(breadth * 100),
            "should_trade": should_trade,
        },
        decision_model,
        opportunities=all_opps_for_action,
        deployable_count=execution_ready_count,
    )
    buffett_clarity = buffett_clarity_strip_for_today(
        {
            "tradeability": tradeability,
            "vix": round(vix_val, 1),
            "breadth": round(breadth * 100),
            "should_trade": should_trade,
        },
        decision_model,
        opportunities=all_opps_for_action,
        deployable_count=execution_ready_count,
    )
    index_fund_posture = index_fund_posture_strip_for_today(
        {
            "tradeability": tradeability,
            "vix": round(vix_val, 1),
            "breadth": round(breadth * 100),
            "should_trade": should_trade,
        },
        decision_model,
        benchmark="SPY",
    )
    principles_posture = principles_posture_for_today(
        {
            "tradeability": tradeability,
            "vix": round(vix_val, 1),
            "breadth": round(breadth * 100),
            "should_trade": should_trade,
        },
        decision_model,
        opportunities=all_opps_for_action,
        deployable_count=execution_ready_count,
    )
    decision_hierarchy = hierarchy_for_dashboard(
        decision_model=decision_model,
        execution_readiness=execution_readiness,
        restraint=restraint,
        should_trade=should_trade,
        tradeability=tradeability,
        execution_ready_count=execution_ready_count,
        pilot_ready_count=pilot_ready_count,
        crisis_bundle=crisis_regime,
        market_regime={
            "tradeability": tradeability,
            "vix": round(vix_val, 1),
            "breadth": round(breadth * 100),
            "should_trade": should_trade,
            "entropy": round(entropy, 2),
        },
    )
    best_net = None
    for row in all_opps_for_action[:12]:
        net = row.get("net_deploy_score")
        if net is not None:
            best_net = max(best_net or 0, float(net))
    complexity = complexity_verdict(
        deployable_count=execution_ready_count,
        net_edge=best_net,
        tradeability=tradeability,
    )
    pf_count = 0
    pf_local_only = False
    try:
        from src.api.routers.portfolio import _user_portfolio

        pf_holdings = _user_portfolio.get("holdings") or []
        pf_count = len(pf_holdings)
        pf_local_only = (_user_portfolio.get("source") or "manual") != "ibkr"
    except Exception:
        pass
    passive_baseline = await build_passive_baseline_for_today(
        opportunities=all_opps_for_action,
        deployable_count=execution_ready_count,
        position_count=pf_count,
        local_only=pf_local_only,
    )
    surface_authority = authority_strip_for_today(
        tradeability=decision_model.get("honest_tradeability") or tradeability,
        ibkr_connected=ibkr_connected,
        deployable_count=execution_ready_count,
    )

    from src.services.execution_analytics import (
        build_empty_execution_analytics_state,
        build_execution_analytics,
    )

    if ibkr_connected and not scanner_degraded and not used_brief_fallback:
        execution_analytics = build_execution_analytics(
            ibkr_connected=True,
            degraded=False,
        )
    else:
        execution_analytics = build_empty_execution_analytics_state()

    from src.services.cc_state import build_cc_state

    trust = {
        "mode": "LIVE" if should_trade else "PAPER",
        "source": (
            "brief-fallback"
            if used_brief_fallback
            else (
                "decision_engine"
                if not scanner_degraded
                else "decision_engine_degraded"
            )
        ),
        "freshness": "REAL_TIME" if not scanner_degraded else "DEGRADED",
        "stale": scanner_degraded or used_brief_fallback,
        "reason": scanner_reason
        or ("brief fallback board" if used_brief_fallback else ""),
        "as_of": now.isoformat() + "Z",
        "ai_powered": False,
    }

    payload = {
        "date": now.strftime("%Y-%m-%d"),
        "narrative": narrative,
        "market_regime": {
            "label": regime_label,
            "risk_state": risk_state,
            "should_trade": should_trade,
            "confidence": round(confidence, 2),
            "tradeability": tradeability,
            "honest_tradeability": decision_model.get(
                "honest_tradeability", tradeability
            ),
            "summary": narrative,
            "trend": trend_label,
            "volatility": vol_label,
            "score": score,
            "vix": round(vix_val, 1),
            "breadth": round(breadth * 100),
            "entropy": round(entropy, 2),
        },
        "market_pulse": market_pulse,
        "top_5": top5,
        "top_ranked": top5,
        "filter_funnel": funnel,
        "best_setup_family": best_family,
        "family_breakdown": {
            k: {
                "count": family_counts.get(k, 0),
                "avg_score": round(v / max(family_counts.get(k, 1), 1), 1),
            }
            for k, v in family_scores.items()
        },
        "avoid": avoid,
        "avoid_now": avoid_now,
        "what_changed": what_changed,
        "event_risks": event_risks,
        "sector_summary": sector_summary,
        "action_summary": action_summary,
        "best_action": best_action,
        "todays_decision": todays_decision,
        "overlap_warning": overlap_warning,
        "near_miss": near_miss,
        "no_setup_diagnosis": no_setup_diagnosis,
        "unlock_deploy": unlock_deploy,
        "regime_wait_explanation": regime_wait_explanation,
        "monitor_triggers": monitor_triggers,
        "quant_cluster_hints": quant_cluster_hints,
        "sleeve_summary": sleeve_summary,
        "execution_readiness": execution_readiness,
        "execution_analytics": execution_analytics,
        "evidence_badges": build_evidence_badges(
            scanner_degraded=scanner_degraded,
            regime_synthetic=bool(
                getattr(request.app.state, "regime_synthetic", False)
            ),
            ai_powered=False,
        ),
        "decision_model": decision_model,
        "decision_hierarchy": decision_hierarchy,
        "passive_baseline": passive_baseline,
        "complexity_challenge": complexity,
        "restraint": restraint,
        "surface_authority": surface_authority,
        "crisis_regime": crisis_regime,
        "naval_clarity": naval_clarity,
        "buffett_clarity": buffett_clarity,
        "index_fund_posture": index_fund_posture,
        "principles_posture": principles_posture,
        "avoid_grouped": avoid_grouped,
        "bucket_quality": bucket_quality,
        "cross_asset_confirmation": cross_asset_confirmation,
        "index_regime_summary": index_regime_summary,
        "regime_strip": regime_strip,
        "regime_stack_summary": regime_stack_summary,
        "allocator_stance": allocator_stance,
        "ai_reason_codes": ai_reason_codes,
        "ai_intelligence": ai_intel,
        "score_reconciliation": _pipe.get("score_reconciliation")
        or _build_score_reconciliation_for_today(
            top5,
            cross_asset=cross_asset_confirmation,
            deploy_open=bool((decision_authority or {}).get("deploy_open")),
            tradeability=str(
                decision_model.get("honest_tradeability") or tradeability
            ).upper(),
            brief_stale=_brief_stale,
        ),
        "score_families_summary": _pipe.get("score_families_summary"),
        "decision_authority": decision_authority,
        "trust": trust,
        "generated_at": now.isoformat() + "Z",
        "brief_context": brief_ctx,
        "data_stale": _quality_stale,
        "brief_stale": _brief_stale,
    }
    payload["opportunity_verdict"] = _opportunity_verdict or build_opportunity_verdict(payload)
    payload["cc_state"] = build_cc_state(
        tradeability=decision_model.get("honest_tradeability") or tradeability,
        should_trade=should_trade,
        decision_authority=decision_authority,
        execution_readiness=execution_readiness,
        surface_authority=surface_authority,
        trust=trust,
    )
    from src.services.cc_state import attach_page_capability, attach_system_state

    payload = attach_system_state(payload)
    payload = attach_page_capability(payload, "today")
    try:
        from src.services.bdr_operator_summary import build_bdr_from_today_payload

        payload["bdr_summary"] = build_bdr_from_today_payload(
            payload,
            ops={
                "running": eng_running,
                "breaker": exec_blocked,
            },
        )
    except Exception:
        logger.debug("bdr_summary build failed", exc_info=True)
    try:
        from src.services.decision_board_service import attach_decision_board

        attach_decision_board(
            payload,
            ops={"running": eng_running, "breaker": exec_blocked},
            source="today",
        )
    except Exception:
        logger.debug("decision_board attach failed", exc_info=True)
    try:
        from src.engines.feature_ic import get_feature_ic_status

        payload["feature_ic_status"] = get_feature_ic_status()
    except Exception:
        logger.debug("feature_ic_status failed", exc_info=True)
    try:
        from src.services.ml_advisory_summary import build_ml_advisory_summary

        payload["ml_advisory"] = build_ml_advisory_summary()
    except Exception:
        logger.debug("ml_advisory build failed", exc_info=True)
    try:
        from src.services.operator_state_contract import (
            pick_dashboard_monitors,
            structural_valid_for_monitor,
        )

        payload["dashboard_monitors"] = pick_dashboard_monitors(
            watch_qualified=[
                r
                for r in (payload.get("top_ranked") or [])
                if structural_valid_for_monitor(r)
                and str(r.get("action") or "").upper() in ("WATCH", "PILOT", "MONITOR")
            ],
            near_miss=payload.get("near_miss") or [],
            top_ranked=payload.get("top_ranked") or [],
        )
    except Exception:
        pass
    # Degraded/empty market data can leave NaN/Inf floats in the payload, which
    # the JSON encoder rejects (500). Sanitize once before caching + returning.
    payload = sanitize_for_json(payload)
    if not scanner_degraded:
        _today_cache = payload
        _today_cache_ts = time.time()
    else:
        _today_cache = None
        _today_cache_ts = 0.0
    try:
        prev = getattr(request.app.state, "today_v7_cache", None) or {}
        old_regime = str((prev.get("market_regime") or {}).get("trend") or "")
        new_regime = str((payload.get("market_regime") or {}).get("trend") or "")
        vix = float((payload.get("market_regime") or {}).get("vix") or 0)
        if old_regime and new_regime and old_regime != new_regime:
            from src.services.alert_service import on_regime_change

            on_regime_change(old_regime, new_regime, vix)

        prev_unlock = (prev.get("unlock_deploy") or {}).get("unlocked")
        new_unlock = (payload.get("unlock_deploy") or {}).get("unlocked")
        if (
            prev_unlock is not None
            and new_unlock is not None
            and prev_unlock != new_unlock
        ):
            from src.services.alert_service import on_deploy_gate_change

            ud = payload.get("unlock_deploy") or {}
            on_deploy_gate_change(
                unlocked=bool(new_unlock),
                summary=str(ud.get("summary") or ""),
                tradeability=str(
                    (payload.get("market_regime") or {}).get("tradeability") or ""
                ),
                remaining=ud.get("remaining") or [],
            )

        prev_bdr = str((prev.get("bdr_summary") or {}).get("decision_code") or "")
        new_bdr = str((payload.get("bdr_summary") or {}).get("decision_code") or "")
        if prev_bdr and new_bdr and prev_bdr != new_bdr:
            from src.services.alert_service import on_bdr_decision_change

            on_bdr_decision_change(
                prev_bdr,
                new_bdr,
                str((payload.get("bdr_summary") or {}).get("decision_line") or ""),
            )
    except Exception:
        pass
    try:
        request.app.state.today_v7_cache = payload
    except Exception:
        pass
    return payload


# ══════════════════════════════════════════════════════════════════════
# /api/v7/decision/bdr-summary — BDR operator decision brief
# ══════════════════════════════════════════════════════════════════════


def _board_ops_snapshot(request: Request) -> Dict[str, Any]:
    try:
        from src.api.app_state import get_engine
        from src.services.runtime_truth import engine_runtime_snapshot

        engine = get_engine(request.app)
        runtime = engine_runtime_snapshot(engine) if engine else {}
        return {
            "running": bool(runtime.get("running")),
            "breaker": bool(runtime.get("circuit_breaker")),
        }
    except Exception:
        return {}


async def _refresh_today_authority(
    request: Request, payload: Dict[str, Any]
) -> Dict[str, Any]:
    """Recompute deploy authority on cached scan body — never serve stale deploy_open."""
    from copy import deepcopy

    from src.services.cc_state import attach_page_capability, attach_system_state, build_cc_state
    from src.services.decision_board_service import attach_decision_board
    from src.services.decision_truth_model import build_decision_authority

    out = deepcopy(payload)
    regime_state = await _fetch_regime(request)
    should_trade = bool(getattr(regime_state, "should_trade", False))

    mr = dict(out.get("market_regime") or {})
    if not should_trade:
        mr["should_trade"] = False
        regime_label = str(getattr(regime_state, "regime", "") or "").upper()
        if regime_label == "RISK_OFF" or getattr(regime_state, "no_trade_reason", ""):
            mr["tradeability"] = "NO_TRADE"
        else:
            mr["tradeability"] = "WAIT"
    else:
        mr["should_trade"] = True
    out["market_regime"] = mr

    dm = out.get("decision_model") or {}
    tradeability = str(
        dm.get("honest_tradeability") or mr.get("tradeability") or "WAIT"
    ).upper()
    if not should_trade:
        tradeability = str(mr.get("tradeability") or "WAIT").upper()

    ops = _board_ops_snapshot(request)
    eng_running = bool(ops.get("running"))
    exec_blocked = bool(ops.get("breaker"))
    try:
        from src.services.ibkr_service import get_ibkr_service

        ibkr_st = get_ibkr_service().status()
        ibkr_connected = bool(
            ibkr_st.get("session_usable") or ibkr_st.get("connected")
        )
    except Exception:
        ibkr_connected = False

    trust = out.get("trust") or {}
    scanner_degraded = bool(
        trust.get("stale") or trust.get("freshness") == "DEGRADED"
    )
    da_prev = out.get("decision_authority") or {}
    da_source = str(da_prev.get("source") or trust.get("source") or "")
    used_brief_fallback = "brief" in da_source or "fallback" in da_source
    funnel = out.get("filter_funnel") or {}
    deploy_count = int(
        funnel.get("deploy_qualified_setups")
        or funnel.get("execution_ready_setups")
        or 0
    )

    decision_authority = build_decision_authority(
        tradeability=tradeability,
        should_trade=should_trade,
        scanner_degraded=scanner_degraded,
        scanner_loading=scanner_degraded and deploy_count < 1,
        data_stale=scanner_degraded,
        fallback_brief=used_brief_fallback,
        broker_offline=not ibkr_connected,
        engine_off=not eng_running,
        exec_blocked=exec_blocked,
        trust_source=da_source or "decision_engine",
        ranked_stale=scanner_degraded,
        deploy_ideas_count=deploy_count,
    )
    out["decision_authority"] = decision_authority

    execution_readiness = dict(out.get("execution_readiness") or {})
    execution_readiness["engine_running"] = eng_running
    execution_readiness["circuit_breaker"] = exec_blocked
    execution_readiness["broker_connected"] = ibkr_connected
    execution_readiness["ibkr_connected"] = ibkr_connected
    out["execution_readiness"] = execution_readiness

    surface_authority = out.get("surface_authority")
    out["cc_state"] = build_cc_state(
        tradeability=tradeability,
        should_trade=should_trade,
        decision_authority=decision_authority,
        execution_readiness=execution_readiness,
        surface_authority=surface_authority,
        trust=trust if isinstance(trust, dict) else None,
    )
    attach_system_state(out)
    attach_page_capability(out, "today")
    try:
        attach_decision_board(out, ops=ops, source="today")
    except Exception:
        logger.debug("refresh today authority: decision_board attach failed", exc_info=True)
    return sanitize_for_json(out)


def _today_payload_for_board(request: Request) -> Optional[Dict[str, Any]]:
    """Prefer any cached today payload — never block board on live scan."""
    cached = getattr(request.app.state, "today_v7_cache", None)
    if isinstance(cached, dict) and cached.get("market_regime"):
        return cached
    stale = _cached_today_payload("decision board")
    if stale and stale.get("market_regime"):
        return stale
    if _today_cache and _today_cache.get("market_regime"):
        return _today_cache
    return None


def _build_board_payload(
    today: Dict[str, Any], *, ops: Dict[str, Any], source: str = "board"
) -> Dict[str, Any]:
    from src.services.decision_board_service import build_decision_board

    return build_decision_board(today, ops=ops, source=source)


@router.get("/api/v7/decision/board")
async def decision_board(request: Request, _: bool = Depends(verify_api_key)):
    """Lightweight canonical decision board for header / cross-surface polling."""
    t0 = time.perf_counter()
    ops = _board_ops_snapshot(request)
    today = _today_payload_for_board(request)
    if today:
        try:
            refreshed = await _refresh_today_authority(request, today)
            board = _build_board_payload(refreshed, ops=ops, source="board")
            logger.debug(
                "decision_board %.0fms deploy_open=%s (cached today)",
                (time.perf_counter() - t0) * 1000,
                board.get("deploy_open"),
            )
            return sanitize_for_json(board)
        except Exception as exc:
            logger.debug("decision board from cache failed: %s", exc)

    if _today_lock.locked():
        stale = _cached_today_payload("today scan in progress")
        if stale:
            try:
                refreshed = await _refresh_today_authority(request, stale)
                board = _build_board_payload(refreshed, ops=ops, source="board")
                logger.debug(
                    "decision_board %.0fms deploy_open=%s (stale today)",
                    (time.perf_counter() - t0) * 1000,
                    board.get("deploy_open"),
                )
                return sanitize_for_json(board)
            except Exception as exc:
                logger.debug("decision board from stale today failed: %s", exc)
        warmed = _stale_today_payload("today scan in progress")
        board = _build_board_payload(warmed, ops=ops, source="board")
        logger.debug(
            "decision_board %.0fms deploy_open=%s (warming)",
            (time.perf_counter() - t0) * 1000,
            board.get("deploy_open"),
        )
        return sanitize_for_json(board)

    today = await today_summary(request)
    if isinstance(today, dict) and today.get("error"):
        raise HTTPException(503, today.get("error") or "today payload unavailable")
    try:
        board = _build_board_payload(today, ops=ops, source="board")
        logger.debug(
            "decision_board %.0fms deploy_open=%s (live today)",
            (time.perf_counter() - t0) * 1000,
            board.get("deploy_open"),
        )
        return sanitize_for_json(board)
    except Exception as exc:
        logger.warning("decision board failed: %s", exc)
        raise HTTPException(500, f"Decision board error: {exc}") from exc


@router.get("/api/v7/decision/bdr-summary")
async def bdr_operator_summary(request: Request, _: bool = Depends(verify_api_key)):
    """Auto-generated BDR-style operator brief from live today / playbook state."""
    today = await today_summary(request)
    if isinstance(today, dict) and today.get("error"):
        raise HTTPException(503, today.get("error") or "today payload unavailable")
    try:
        from src.api.app_state import get_engine
        from src.services.runtime_truth import engine_runtime_snapshot

        engine = get_engine(request.app)
        runtime = engine_runtime_snapshot(engine) if engine else {}
        ops = {
            "running": bool(runtime.get("running")),
            "breaker": bool(runtime.get("circuit_breaker")),
        }
    except Exception:
        ops = {}
    try:
        from src.services.bdr_operator_summary import build_bdr_from_today_payload

        summary = build_bdr_from_today_payload(today, ops=ops)
        return sanitize_for_json(summary)
    except Exception as exc:
        logger.warning("bdr-summary failed: %s", exc)
        raise HTTPException(500, f"BDR summary error: {exc}") from exc


# ══════════════════════════════════════════════════════════════════════
# /api/v7/opportunities — Full Ranked Board
# ══════════════════════════════════════════════════════════════════════


@router.get("/api/v7/opportunities")
async def ranked_opportunities(
    request: Request,
    sort_by: str = Query(
        "score", description="Sort: score, timing, risk_reward, strategy"
    ),
    setup_filter: str = Query(
        None, description="Filter: momentum, breakout, swing, mean_reversion"
    ),
    min_score: float = Query(0, description="Minimum score threshold"),
    limit: int = Query(30, description="Max results"),
):
    """Full ranked opportunity board — the decision table.

    Each row answers: What? Why? Why now? Why not? What to do? When to bail?
    """
    regime_state = await _fetch_regime(request)
    should_trade = getattr(regime_state, "should_trade", False)

    import asyncio as _asyncio

    try:
        scanned, _ = await _asyncio.wait_for(
            request.app.state.scan_signals(limit=100), timeout=35.0
        )
    except _asyncio.TimeoutError:
        logger.warning("[opportunities] scan_signals timed out after 35s")
        scanned = []
    except Exception as exc:
        logger.warning("[opportunities] scan_signals failed: %s", exc)
        scanned = []

    # Filter
    if setup_filter:
        scanned = [s for s in scanned if s.get("strategy") == setup_filter]
    if min_score > 0:
        scanned = [s for s in scanned if s.get("score", 0) >= min_score]

    # Enrich via ExpertCouncil pipeline
    council = _council(request)
    regime_label = getattr(regime_state, "trend_regime", "sideways")
    trend_map = {
        "uptrend": "UPTREND",
        "downtrend": "DOWNTREND",
        "sideways": "SIDEWAYS",
    }
    vix_val = getattr(regime_state, "vix", 18.0)
    breadth = getattr(regime_state, "breadth_pct", 0.5)
    regime_ctx = {
        "regime": trend_map.get(regime_label, "SIDEWAYS"),
        "volatility": "NORMAL",
        "should_trade": should_trade,
        "vix": vix_val,
        "breadth": breadth,
        "entropy": getattr(regime_state, "entropy", 0.8),
    }
    council_results = council.evaluate_batch(scanned, regime_ctx)

    from src.services.ai_intelligence import attach_row_ai_hints
    from src.services.cost_adjusted_ranker import enrich_opportunity_rows
    from src.services.decision_truth_model import (
        apply_authority_to_rows,
        build_decision_authority,
        build_honest_funnel,
        enrich_opportunity_row,
    )
    from src.services.index_regime import build_index_regime_summary

    trend_label = trend_map.get(regime_label, "SIDEWAYS")
    breadth_val = (
        round(float(breadth) * 100) if float(breadth) <= 1.0 else round(float(breadth))
    )
    funnel = build_honest_funnel(
        universe=len(scanned),
        scanned=scanned,
        council_results=council_results,
    )
    execution_ready_count = int(funnel.get("execution_ready_setups") or 0)
    if not should_trade:
        tradeability = "NO_TRADE"
    elif execution_ready_count >= 1:
        tradeability = "SELECTIVE"
    else:
        tradeability = "WAIT"

    enriched: List[Dict[str, Any]] = []
    for cr in council_results:
        pr = cr.pipeline
        sig = pr.signal
        row = {
            "ticker": sig.get("ticker", ""),
            "strategy": _setup_family(sig.get("strategy", "")),
            "score": pr.fit.final_score,
            "grade": pr.fit.grade,
            "timing": _timing_label(
                abs(sig.get("entry_price", 0) - sig.get("stop_price", 0))
                / max(sig.get("entry_price", 1), 1)
                * 100
            ),
            "risk_reward": sig.get("risk_reward", 0)
            or getattr(pr.decision, "risk_reward", None)
            or getattr(pr.decision, "risk_reward_ratio", None)
            or 0,
            "rsi": sig.get("rsi", 0),
            "vol_quality": (
                "HIGH"
                if sig.get("vol_ratio", 0) > 1.5
                else ("OK" if sig.get("vol_ratio", 0) > 0.8 else "LOW")
            ),
            "sector_bucket": pr.sector.sector_bucket.value,
            "sector_type": pr.sector.sector_bucket.value,
            "entry_price": sig.get("entry_price", 0),
            "target_price": sig.get("target_price", 0),
            "stop_price": sig.get("stop_price", 0),
            "action": pr.decision.action,
            "action_reason": pr.decision.rationale,
            "why_now": ([pr.explanation.why_now] if pr.explanation.why_now else []),
            "why_not": (pr.explanation.why_not_stronger if pr.explanation else None),
            "invalidation": getattr(pr.explanation, "invalidation", None)
            or _invalidation(sig),
            "position_hint": _position_hint(sig, should_trade),
            "confidence_breakdown": pr.confidence.to_dict(),
            "decision": pr.decision.to_dict(),
            "expert_council": cr.verdict.to_dict(),
            "thesis_conf": round(float(pr.confidence.thesis), 2),
            "timing_conf": round(float(pr.confidence.timing), 2),
            "exec_conf": round(float(pr.confidence.execution), 2),
            "data_conf": float(pr.confidence.data),
            "final_conf": round(float(pr.confidence.final), 2),
            "leader": pr.sector.leader_status.value,
        }
        enriched.append(enrich_opportunity_row(cr, row))

    index_regime_summary = build_index_regime_summary(
        tradeability=tradeability,
        should_trade=should_trade,
        degraded=False,
    )
    enriched = enrich_opportunity_rows(
        enriched,
        index_regime=index_regime_summary,
        tradeability=tradeability,
    )
    market_regime = {
        "trend": trend_label,
        "tradeability": tradeability,
        "breadth": breadth_val,
    }
    enriched = attach_row_ai_hints(
        enriched,
        market_regime=market_regime,
        index_regime=index_regime_summary,
        event_risks=[],
    )
    decision_authority = build_decision_authority(
        tradeability=tradeability,
        should_trade=should_trade,
        scanner_degraded=False,
        deploy_ideas_count=execution_ready_count,
        live_deploy_count=execution_ready_count,
    )
    enriched = apply_authority_to_rows(enriched, decision_authority)

    sort_keys = {
        "score": lambda x: -float(x.get("score") or 0),
        "timing": lambda x: [
            "NEAR_PIVOT",
            "EARLY",
            "ON_TIME",
            "EXTENDED",
            "LATE",
        ].index(x.get("timing") or "LATE"),
        "risk_reward": lambda x: -float(x.get("risk_reward") or 0),
        "strategy": lambda x: x.get("strategy") or "",
    }
    sort_fn = sort_keys.get(sort_by, sort_keys["score"])
    enriched.sort(key=sort_fn)

    for i, item in enumerate(enriched[:limit], 1):
        item["rank"] = i

    return {
        "regime_allows_trading": should_trade,
        "tradeability": tradeability,
        "total_signals": len(enriched),
        "opportunities": enriched[:limit],
        "index_regime_summary": index_regime_summary,
        "sort_by": sort_by,
        "generated_at": datetime.now(timezone.utc).isoformat() + "Z",
        "enrichment_authority": "monitor_only",
        "may_authorize_deploy": False,
    }


# ══════════════════════════════════════════════════════════════════════
# /api/v7/filter-funnel — Pipeline Visualization
# ══════════════════════════════════════════════════════════════════════


@router.get("/api/v7/filter-funnel")
async def filter_funnel(request: Request):
    """Filter funnel: universe → liquidity → trend → RS → structure → final.

    Shows how 5000+ tickers get narrowed to the actionable few.
    """
    scanned, _ = await request.app.state.scan_signals(limit=100)

    # Build funnel stages
    universe = len(getattr(request.app.state, "scan_watchlist", []))
    triggered = len(scanned)
    above_6 = len([s for s in scanned if s.get("score", 0) >= 6.0])
    above_7 = len([s for s in scanned if s.get("score", 0) >= 7.0])
    above_8 = len([s for s in scanned if s.get("score", 0) >= 8.0])

    # Strategy breakdown
    by_strategy: Dict[str, int] = {}
    for s in scanned:
        strat = s.get("strategy", "unknown")
        by_strategy[strat] = by_strategy.get(strat, 0) + 1

    # Regime breakdown
    uptrend_count = len([s for s in scanned if s.get("regime") == "UPTREND"])
    sideways_count = len([s for s in scanned if s.get("regime") == "SIDEWAYS"])

    return {
        "funnel": [
            {"stage": "Universe (Watchlist)", "count": universe, "pct": 100},
            {
                "stage": "Signal Triggered",
                "count": triggered,
                "pct": round(triggered / max(universe, 1) * 100, 1),
            },
            {
                "stage": "Score ≥ 6.0 (Decent)",
                "count": above_6,
                "pct": round(above_6 / max(universe, 1) * 100, 1),
            },
            {
                "stage": "Score ≥ 7.0 (Actionable)",
                "count": above_7,
                "pct": round(above_7 / max(universe, 1) * 100, 1),
            },
            {
                "stage": "Score ≥ 8.0 (High Conviction)",
                "count": above_8,
                "pct": round(above_8 / max(universe, 1) * 100, 1),
            },
        ],
        "by_strategy": by_strategy,
        "by_regime": {
            "uptrend": uptrend_count,
            "sideways": sideways_count,
        },
        "generated_at": datetime.now(timezone.utc).isoformat() + "Z",
    }


# ══════════════════════════════════════════════════════════════════════
# ── AI signal analysis helper ──


async def _get_ai_signal_analysis(signal: dict) -> Optional[str]:
    """Get AI analysis for a signal, returns None if unavailable."""
    try:
        from src.services.ai_service import get_ai_service

        ai = get_ai_service()
        if not ai.is_configured:
            return None
        result = await ai.analyze_signal(signal)
        return result.get("ai_analysis") if result else None
    except Exception:
        return None


# /api/v7/signal-card/{ticker} — Decision-Grade Signal Card
# ══════════════════════════════════════════════════════════════════════


@router.get("/api/v7/signal-card/{ticker}")
async def signal_card(ticker: str, request: Request):
    """Full decision card for a single ticker.

    Answers everything a trader needs:
    - What strategy? What score?
    - Why now? Why not?
    - What's the action? Entry/target/stop?
    - When does this setup fail?
    - Position size hint?
    """
    from src.engines.conformal_predictor import ConformalPredictor
    from src.services.confidence import (
        compute_4layer_confidence as _compute_4layer_confidence,
    )
    from src.services.indicators import compute_indicators as _compute_indicators

    ticker = ticker.upper().strip()
    mds = request.app.state.market_data
    regime_state = await _fetch_regime(request)
    should_trade = getattr(regime_state, "should_trade", False)

    try:
        hist = await mds.get_history(ticker, period="1y", interval="1d")
        if hist is None or hist.empty or len(hist) < 60:
            raise HTTPException(404, f"Insufficient data for {ticker}")

        c_col = "Close" if "Close" in hist.columns else "close"
        v_col = "Volume" if "Volume" in hist.columns else "volume"
        close = hist[c_col].values.astype(float)
        volume = hist[v_col].values.astype(float)
        n = len(close)
        i = n - 1

        _ind = _compute_indicators(close, volume)
        sma20 = _ind["sma20"]
        sma50 = _ind["sma50"]
        sma200 = _ind["sma200"]
        rsi = _ind["rsi"]
        vol_ratio = _ind["vol_ratio"]
        atr_pct = _ind["atr_pct"]

        trending = bool(close[i] > sma50[i] and sma50[i] > sma200[i])
        cur_price = round(float(close[i]), 2)

        # 4-layer confidence
        conf = _compute_4layer_confidence(
            close,
            sma20,
            sma50,
            sma200,
            rsi,
            atr_pct,
            vol_ratio,
            i,
            volume,
            trending,
        )

        # Expert Council (sector-adaptive)
        council = _council(request)
        regime_ctx = {
            "regime": "UPTREND" if trending else "SIDEWAYS",
            "volatility": "NORMAL",
            "should_trade": should_trade,
            "vix": getattr(regime_state, "vix", 18.0),
            "breadth": getattr(regime_state, "breadth_pct", 0.5),
            "entropy": getattr(regime_state, "entropy", 0.8),
        }

        # Conformal prediction
        interval = None
        try:
            cp = ConformalPredictor(confidence_level=0.90)
            cp.calibrate_from_returns(close, horizon_days=20)
            interval = cp.predict(cur_price * 1.05)
        except Exception:
            pass

        # Determine strategy
        strategy = "momentum"  # default
        rsi_val = float(rsi[i])
        if rsi_val < 35:
            strategy = "mean_reversion"
        elif float(vol_ratio[i]) > 1.8:
            strategy = "breakout"
        elif rsi_val < 45 and close[i] > sma50[i]:
            strategy = "swing"

        cur_atr = max(float(atr_pct[i]), 0.005)
        stop_price = round(cur_price * (1 - cur_atr * 2), 2)
        target_price = round(cur_price * (1 + cur_atr * 4), 2)
        rr = round(
            (target_price - cur_price) / max(cur_price - stop_price, 0.01),
            1,
        )

        # Distance to 20MA
        dist_20ma = round((cur_price / float(sma20[i]) - 1) * 100, 2)

        signal = {
            "ticker": ticker,
            "strategy": strategy,
            "entry_price": cur_price,
            "target_price": target_price,
            "stop_price": stop_price,
            "risk_reward": rr,
            "score": round(conf["composite"] / 10, 1),
            "rsi": round(rsi_val, 1),
            "vol_ratio": round(float(vol_ratio[i]), 2),
            "atr_pct": round(float(atr_pct[i]) * 100, 2),
            "regime": "UPTREND" if trending else "SIDEWAYS",
        }

        # Run through ExpertCouncil
        cr = council.evaluate(signal, regime_ctx)
        pr = cr.pipeline

        return {
            "ticker": ticker,
            "current_price": cur_price,
            "strategy": _setup_family(strategy),
            "score": pr.fit.final_score,
            "grade": pr.fit.grade,
            "direction": cr.verdict.direction,
            "committee_confidence": round(
                cr.verdict.agreement_ratio,
                2,
            ),
            "timing": _timing_label(abs(dist_20ma)),
            "action": pr.decision.action,
            "action_reason": pr.decision.rationale,
            "position_hint": _position_hint(signal, should_trade),
            "entry_price": cur_price,
            "target_price": target_price,
            "stop_price": stop_price,
            "risk_reward": rr,
            "sector_bucket": pr.sector.sector_bucket.value,
            "confidence_breakdown": pr.confidence.to_dict(),
            "decision": pr.decision.to_dict(),
            "explanation": pr.explanation.to_dict(),
            "expert_council": cr.verdict.to_dict(),
            "technicals": {
                "rsi": signal["rsi"],
                "vol_ratio": signal["vol_ratio"],
                "atr_pct": signal["atr_pct"],
                "distance_to_20ma_pct": dist_20ma,
                "above_50sma": bool(close[i] > sma50[i]),
                "above_200sma": bool(close[i] > sma200[i]),
                "regime": signal["regime"],
            },
            "prediction_interval": (interval.to_dict() if interval else None),
            "regime_allows_trading": should_trade,
            "ai_analysis": await _get_ai_signal_analysis(signal),
            "generated_at": (datetime.now(timezone.utc).isoformat() + "Z"),
            "historical_win_rate": conf.get("historical_win_rate", 0),
            "historical_analog": conf.get("historical_analog", {}),
            "historical_analog_count": conf.get("historical_analog_count", 0),
        }

    except HTTPException:
        raise
    except Exception as exc:
        try:
            from src.services.platform_error_log import capture_exception

            capture_exception(
                component="decision",
                message=f"Signal card failed for {ticker}",
                exc=exc,
                dedupe_key=f"decision:signal-card:{ticker}",
            )
        except Exception:
            logger.debug("platform error log append failed", exc_info=True)
        raise HTTPException(500, f"Signal card error: {exc}") from exc


# ══════════════════════════════════════════════════════════════════════
# /api/v7/regime — Market Regime Classification
# ══════════════════════════════════════════════════════════════════════


@router.get("/api/v7/regime")
async def regime_summary(request: Request):
    """Full regime classification with cross-asset context."""
    regime_state = await _fetch_regime(request)
    trend_map = {
        "uptrend": "UPTREND",
        "downtrend": "DOWNTREND",
        "sideways": "SIDEWAYS",
    }
    vol_map = {
        "low_vol": "LOW",
        "normal_vol": "NORMAL",
        "elevated_vol": "ELEVATED",
        "high_vol": "HIGH",
        "crisis_vol": "CRISIS",
    }

    label = getattr(regime_state, "regime", "NEUTRAL")
    trend = trend_map.get(
        getattr(regime_state, "trend_regime", "sideways"),
        "SIDEWAYS",
    )
    vol = vol_map.get(
        getattr(regime_state, "volatility_regime", "normal_vol"),
        "NORMAL",
    )
    vix = getattr(regime_state, "vix", 18.0)
    breadth = getattr(regime_state, "breadth_pct", 0.5)
    should_trade = getattr(regime_state, "should_trade", False)
    confidence = getattr(regime_state, "confidence", 0.5)

    # Cross-asset stress
    cross_asset = {}
    try:
        from src.engines.context_assembler import ContextAssembler

        ca = ContextAssembler()
        ctx = await ca.assemble()
        cross_asset = ctx.get("cross_asset", {})
    except Exception:
        pass

    return {
        "regime": label,
        "trend": trend,
        "volatility": vol,
        "vix": round(vix, 1),
        "breadth_pct": round(breadth * 100, 1),
        "confidence": round(confidence, 2),
        "should_trade": should_trade,
        "cross_asset": cross_asset,
        "generated_at": (datetime.now(timezone.utc).isoformat() + "Z"),
    }


# ══════════════════════════════════════════════════════════════════════
# /api/v7/cross-asset — Cross-Asset Stress Monitor
# ══════════════════════════════════════════════════════════════════════


@router.get("/api/v7/cross-asset")
async def cross_asset_report():
    """Full cross-asset stress analysis with live data."""
    from src.engines.context_assembler import ContextAssembler

    ca = ContextAssembler()
    ctx = await ca.assemble()
    report = ctx.get("cross_asset", {})
    market = ctx.get("market_state", {})

    return {
        "market_state": {
            "vix": market.get("vix"),
            "spy_return_20d": market.get("spy_return_20d"),
            "breadth_pct": market.get("breadth_pct"),
            "realized_vol_20d": market.get("realized_vol_20d"),
            "data_source": market.get("data_source"),
        },
        "stress_report": report,
        "generated_at": (datetime.now(timezone.utc).isoformat() + "Z"),
    }


# ══════════════════════════════════════════════════════════════════════
# /api/v7/learning — Learning Loop Summary
# ══════════════════════════════════════════════════════════════════════


@router.get("/api/v7/learning")
async def learning_summary():
    """Learning loop summary: win rates, regime performance."""
    loop = _learning_loop()
    return {
        "summary": loop.summary(),
        "recent_trades": loop.get_trade_log(limit=20),
        "generated_at": (datetime.now(timezone.utc).isoformat() + "Z"),
    }


@router.get("/api/v7/belief-review/summary")
async def belief_review_summary():
    """Belief Review — v14 compounding loop (research_only, no deploy authority)."""
    cache_key = "belief_review"
    if cached := _research_cache_get(cache_key):
        return cached

    from src.services.belief_review import build_belief_items, build_deploy_belief_flags
    from src.services.decision_journal import maybe_stub_from_decision_id
    from src.services.forward_outcomes import load_forward_outcomes

    t0 = time.perf_counter()
    outcomes = await asyncio.to_thread(load_forward_outcomes, limit=50)
    items = build_belief_items(outcomes)
    for it in items:
        did = str(it.get("decision_id") or "").strip()
        if did:
            await asyncio.to_thread(
                maybe_stub_from_decision_id,
                decision_id=did,
                ticker=str(it.get("ticker") or ""),
                source="belief_review_hook",
            )
    due = sum(1 for it in items if str(it.get("status") or "") == "due_review")
    reviewed = sum(1 for it in items if str(it.get("status") or "") == "reviewed")

    deploy_open = False
    holdings: list = []
    try:
        from src.api.routers import portfolio as portfolio_router
        from src.services.decision_board_service import build_decision_board

        board = build_decision_board()
        deploy_open = bool((board.get("system_state") or {}).get("deploy_open"))
        book = portfolio_router._user_portfolio
        if not isinstance(book, dict):
            book = portfolio_router._load_portfolio_from_disk()
        holdings = book.get("holdings") or []
    except Exception:
        pass
    deploy_flags = build_deploy_belief_flags(holdings, deploy_open=deploy_open)

    payload = sanitize_for_json(
        {
            "status": "phase2" if items else "stub",
            "authority": "research_only",
            "beliefs_due": due,
            "beliefs_reviewed_mtd": reviewed,
            "forward_outcome_marks": len(outcomes),
            "headline": "Belief Review · 信念複核 — thesis + kill conditions (research only)",
            "next_review": "Monthly · first business day",
            "items": items,
            "editable_fields": ["thesis", "kill_condition", "conviction", "status"],
            "deploy_flags": deploy_flags,
            "generated_at": datetime.now(timezone.utc).isoformat() + "Z",
        }
    )
    _research_cache_set(cache_key, payload)
    logger.debug("belief_review_summary %.0fms", (time.perf_counter() - t0) * 1000)
    return payload


@router.patch("/api/v7/belief-review/items/{item_id}")
async def belief_review_update_item(item_id: str, body: Dict[str, Any]):
    """Persist belief thesis/kill edits — research_only; never grants deploy."""
    from src.services.belief_review import update_belief_item

    try:
        item = update_belief_item(item_id, body or {})
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return sanitize_for_json(
        {
            "ok": True,
            "authority": "research_only",
            "item": item,
            "generated_at": datetime.now(timezone.utc).isoformat() + "Z",
        }
    )


@router.get("/api/v7/capital/marginal-roc")
async def marginal_roc_summary():
    """Marginal ROC stub — capital ladder hint (research_only, no deploy authority)."""
    from src.services.marginal_roc import build_marginal_roc_ladder

    deploy_open = False
    try:
        from src.services.decision_board_service import build_decision_board

        board = build_decision_board()
        deploy_open = bool((board.get("system_state") or {}).get("deploy_open"))
    except Exception:
        deploy_open = False
    payload = build_marginal_roc_ladder(deploy_open=deploy_open)
    payload["generated_at"] = datetime.now(timezone.utc).isoformat() + "Z"
    return sanitize_for_json(payload)


def _next_weekday(from_day: date, weekday: int) -> date:
    """Next calendar date on weekday (0=Mon … 6=Sun)."""
    delta = (weekday - from_day.weekday()) % 7
    if delta == 0:
        delta = 7
    return from_day + timedelta(days=delta)


def _first_business_day(year: int, month: int) -> date:
    """First Mon–Fri of month."""
    day = date(year, month, 1)
    while day.weekday() >= 5:
        day += timedelta(days=1)
    return day


def _next_first_business_day(from_day: date) -> date:
    if from_day.month == 12:
        target = _first_business_day(from_day.year + 1, 1)
    else:
        target = _first_business_day(from_day.year, from_day.month + 1)
    if from_day <= target:
        return target
    if target.month == 12:
        return _first_business_day(target.year + 1, 1)
    return _first_business_day(target.year, target.month + 1)


def _next_quarterly_belief_review(from_day: date) -> date:
    """Week after quarter-end (first weekday after Q close + 7d)."""
    quarter_ends = (
        date(from_day.year, 3, 31),
        date(from_day.year, 6, 30),
        date(from_day.year, 9, 30),
        date(from_day.year, 12, 31),
    )
    for q_end in quarter_ends:
        if q_end >= from_day:
            candidate = q_end + timedelta(days=7)
            while candidate.weekday() >= 5:
                candidate += timedelta(days=1)
            return candidate
    candidate = date(from_day.year + 1, 3, 31) + timedelta(days=7)
    while candidate.weekday() >= 5:
        candidate += timedelta(days=1)
    return candidate


def _firm_cadence_rituals(from_day: date, *, forward_marks: int) -> list[dict[str, Any]]:
    daily_done = forward_marks >= 0  # gate check surfaced elsewhere; stub checklist
    rituals = [
        {
            "id": "daily_ciio",
            "label": "Daily CIIO routine",
            "label_bilingual": "Daily CIIO · 每日情報官",
            "cadence": "daily",
            "committee": "CIIO",
            "next_due": from_day.isoformat(),
            "status": "due_today" if not daily_done else "on_track",
            "checklist": [
                {"item": "Gate check", "done": True},
                {"item": "Attention queue", "done": False},
                {"item": "One-line journal", "done": False},
            ],
        },
        {
            "id": "weekly_ic",
            "label": "Weekly Investment Committee",
            "label_bilingual": "Weekly IC · 週投資委員會",
            "cadence": "weekly",
            "committee": "Investment Committee",
            "next_due": _next_weekday(from_day, 0).isoformat(),
            "status": "scheduled",
            "checklist": [
                {"item": "Regime review", "done": False},
                {"item": "Portfolio health", "done": False},
                {"item": "Mistake of the week", "done": False},
            ],
        },
        {
            "id": "monthly_capital",
            "label": "Monthly Capital Review",
            "label_bilingual": "Monthly Capital · 月度資本複核",
            "cadence": "monthly",
            "committee": "Capital Committee",
            "next_due": _next_first_business_day(from_day).isoformat(),
            "status": "scheduled",
            "checklist": [
                {"item": "Marginal ROC ladder", "done": False},
                {"item": "Cash vs deploy audit", "done": False},
                {"item": "System Evolution Review", "done": False},
            ],
        },
        {
            "id": "quarterly_belief",
            "label": "Quarterly Belief Review",
            "label_bilingual": "Quarterly Belief · 季度信念複核",
            "cadence": "quarterly",
            "committee": "Belief Committee",
            "next_due": _next_quarterly_belief_review(from_day).isoformat(),
            "status": "scheduled",
            "checklist": [
                {"item": "Calibration report", "done": forward_marks > 0},
                {"item": "Belief death certificates", "done": False},
                {"item": "Kill condition refresh", "done": False},
            ],
        },
        {
            "id": "annual_learning",
            "label": "Annual Learning Summit",
            "label_bilingual": "Annual Learning · 年度學習峰會",
            "cadence": "annual",
            "committee": "Learning Committee",
            "next_due": date(
                from_day.year if from_day.month < 12 else from_day.year + 1, 12, 15
            ).isoformat(),
            "status": "scheduled",
            "checklist": [
                {"item": "Attribution tree", "done": False},
                {"item": "Letter to future self", "done": False},
                {"item": "Investment policy refresh", "done": False},
            ],
        },
    ]
    return rituals


@router.get("/api/v7/daily-ic/summary")
async def daily_ic_summary():
    """Daily IC 5-min one-pager — Mission/Market/Portfolio/Capital/One Belief (research_only)."""
    from src.services.daily_ic_summary import build_daily_ic_summary

    board: Dict[str, Any] = {}
    belief_item: Optional[Dict[str, Any]] = None
    try:
        from src.services.decision_board_service import attach_decision_board

        source = dict(_today_cache or {})
        if source:
            attach_decision_board(source, source="today")
            board = source
    except Exception:
        board = {}
    try:
        from src.services.belief_review import build_belief_items
        from src.services.forward_outcomes import load_forward_outcomes

        outcomes = load_forward_outcomes(limit=50)
        items = build_belief_items(outcomes)
        belief_item = items[0] if items else None
    except Exception:
        belief_item = None
    payload = build_daily_ic_summary(board=board, belief_item=belief_item)
    return sanitize_for_json(payload)


@router.get("/api/v7/firm-cadence/summary")
async def firm_cadence_summary():
    """Firm cadence checklist — v16 governance (research_only, no deploy authority)."""
    cache_key = "firm_cadence"
    if cached := _research_cache_get(cache_key):
        return cached

    from src.services.forward_outcomes import load_forward_outcomes

    t0 = time.perf_counter()
    today = datetime.now(timezone.utc).date()
    outcomes = await asyncio.to_thread(load_forward_outcomes, limit=50)
    rituals = _firm_cadence_rituals(today, forward_marks=len(outcomes))
    next_ritual = min(rituals, key=lambda r: r["next_due"])
    payload = sanitize_for_json(
        {
            "status": "stub",
            "authority": "research_only",
            "headline": "Firm cadence · 機構節奏 — governance rituals (display only)",
            "next_ritual": {
                "id": next_ritual["id"],
                "label": next_ritual["label_bilingual"],
                "due": next_ritual["next_due"],
            },
            "rituals": rituals,
            "forward_outcome_marks": len(outcomes),
            "generated_at": datetime.now(timezone.utc).isoformat() + "Z",
        }
    )
    _research_cache_set(cache_key, payload)
    logger.debug("firm_cadence_summary %.0fms", (time.perf_counter() - t0) * 1000)
    return payload


# ══════════════════════════════════════════════════════════════════════
# IDOS Decision Journal + challenge engines (research_only)
# ══════════════════════════════════════════════════════════════════════


@router.post("/api/v7/decision-journal/entry")
async def decision_journal_create_entry(body: Dict[str, Any]):
    """Persist pre-outcome decision journal entry — research_only; never grants deploy."""
    from src.services.decision_journal import append_entry, record_deploy_intent_stub

    payload = body or {}
    try:
        entry = append_entry(payload)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    decision_id = str(payload.get("decision_id") or entry.get("decision_id") or "").strip()
    ticker = str(payload.get("ticker") or entry.get("ticker") or "").upper()
    decision = str(entry.get("decision") or "").upper()
    if decision_id and decision in {"DEPLOY", "DEPLOY_INTENT", "TRADE", "BUY"}:
        record_deploy_intent_stub(
            ticker=ticker,
            decision_id=decision_id,
            thesis=str(entry.get("thesis") or ""),
        )
    return sanitize_for_json(
        {
            "ok": True,
            "authority": "research_only",
            "entry": entry,
            "generated_at": datetime.now(timezone.utc).isoformat() + "Z",
        }
    )


@router.get("/api/v7/decision-journal/recent")
async def decision_journal_recent(limit: int = Query(20, ge=1, le=100)):
    """Recent IDOS decision journal entries — research_only."""
    cache_key = f"journal_recent:{limit}"
    if cached := _research_cache_get(cache_key):
        return cached

    from src.services.decision_journal import summary

    t0 = time.perf_counter()
    payload = sanitize_for_json(await asyncio.to_thread(summary, limit=limit))
    _research_cache_set(cache_key, payload)
    logger.debug("decision_journal_recent %.0fms", (time.perf_counter() - t0) * 1000)
    return payload


@router.get("/api/v7/decision-journal/deploy-intent-checklist")
async def decision_journal_deploy_intent_checklist(
    ticker: str = Query("", max_length=16),
    decision_id: str = Query("", max_length=64),
):
    """Deploy-intent journal checklist — display only when deploy_open (research_only)."""
    from src.services.decision_journal import deploy_intent_journal_status

    sym = str(ticker or "").strip().upper()
    did = str(decision_id or "").strip()
    if not sym and not did and _today_cache:
        ba = _today_cache.get("best_action") or {}
        td = _today_cache.get("todays_decision") or {}
        ss = _today_cache.get("system_state") or {}
        if ss.get("deploy_open"):
            sym = str(
                (ba.get("best_trade_now") or td.get("best_trade") or {}).get("ticker") or ""
            ).upper()
        else:
            sym = str(
                (ba.get("best_watch_upgrade") or td.get("best_watch") or {}).get("ticker") or ""
            ).upper()
        for key in ("top_5", "top_ranked", "opportunities", "near_miss"):
            for row in _today_cache.get(key) or []:
                if isinstance(row, dict) and row.get("decision_id"):
                    did = str(row["decision_id"])
                    break
            if did:
                break

    payload = sanitize_for_json(
        await asyncio.to_thread(
            deploy_intent_journal_status,
            decision_id=did,
            ticker=sym,
        )
    )
    return payload


@router.get("/api/v7/red-team/challenge")
async def red_team_challenge(ticker: str = Query("", max_length=16)):
    """Red Team structured challenge stub — research_only."""
    from src.services.red_team import build_red_team_challenge

    return sanitize_for_json(build_red_team_challenge(ticker=ticker))


@router.get("/api/v7/outside-view/base-rate")
async def outside_view_base_rate(setup_type: str = Query("generic_breakout", max_length=64)):
    """Outside View base-rate stub — research_only."""
    from src.services.outside_view import build_outside_view_base_rate

    return sanitize_for_json(build_outside_view_base_rate(setup_type=setup_type))


@router.get("/api/v7/decision-committee/review")
async def decision_committee_review(ticker: str = Query("", max_length=16)):
    """Decision Committee virtual debate stub — research_only."""
    from src.services.decision_committee import build_committee_review

    return sanitize_for_json(build_committee_review(ticker=ticker))


@router.get("/api/v7/decision-health/summary")
async def decision_health_summary():
    """Decision Health calibration inputs stub — research_only, non-blocking."""
    from src.services.decision_health import build_decision_health_summary

    return sanitize_for_json(build_decision_health_summary())


# ══════════════════════════════════════════════════════════════════════
# Workflow loops — Pre-Decision · Research Queue · Decision Cooling
# ══════════════════════════════════════════════════════════════════════


@router.get("/api/v7/decision-readiness/checklist")
async def decision_readiness_get(
    ticker: str = Query(..., min_length=1, max_length=10),
):
    """Pre-decision checklist — display only; never grants deploy authority."""
    from src.api.deps import validate_ticker
    from src.services.decision_readiness import checklist_schema, load_checklist

    sym = validate_ticker(ticker)
    payload = load_checklist(sym)
    payload.update(checklist_schema())
    payload["generated_at"] = datetime.now(timezone.utc).isoformat() + "Z"
    return sanitize_for_json(payload)


@router.post("/api/v7/decision-readiness/checklist")
async def decision_readiness_save(body: Dict[str, Any]):
    """Persist pre-decision checklist answers — research_only."""
    from src.api.deps import validate_ticker
    from src.services.decision_readiness import checklist_schema, save_checklist

    ticker_raw = str((body or {}).get("ticker") or "")
    sym = validate_ticker(ticker_raw)
    answers = (body or {}).get("answers") or body or {}
    try:
        payload = save_checklist(sym, answers)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    payload.update(checklist_schema())
    payload["ok"] = True
    payload["generated_at"] = datetime.now(timezone.utc).isoformat() + "Z"
    return sanitize_for_json(payload)


@router.get("/api/v7/research-queue")
async def research_queue_list():
    """CIIO research time queue — not watchlist/scanner."""
    from src.services.research_queue import list_queue

    payload = list_queue()
    payload["generated_at"] = datetime.now(timezone.utc).isoformat() + "Z"
    return sanitize_for_json(payload)


@router.post("/api/v7/research-queue/add")
async def research_queue_add(body: Dict[str, Any]):
    """Add validated ticker to research queue with time budget."""
    from src.api.deps import validate_ticker
    from src.services.research_queue import add_item

    sym = validate_ticker(str((body or {}).get("ticker") or ""))
    try:
        payload = add_item(
            sym,
            budget_minutes=(body or {}).get("budget_minutes", 30),
            category=str((body or {}).get("category") or "Research"),
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    payload["ok"] = True
    payload["generated_at"] = datetime.now(timezone.utc).isoformat() + "Z"
    return sanitize_for_json(payload)


@router.post("/api/v7/research-queue/remove")
async def research_queue_remove(body: Dict[str, Any]):
    """Remove ticker from research queue."""
    from src.api.deps import validate_ticker
    from src.services.research_queue import remove_item

    sym = validate_ticker(str((body or {}).get("ticker") or ""))
    try:
        payload = remove_item(sym)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    payload["ok"] = True
    payload["generated_at"] = datetime.now(timezone.utc).isoformat() + "Z"
    return sanitize_for_json(payload)


@router.get("/api/v7/attention-budget/summary")
async def attention_budget_summary(
    research: int = Query(0, ge=0, le=600),
    portfolio: int = Query(0, ge=0, le=600),
    market: int = Query(0, ge=0, le=600),
):
    """Attention budget defaults + optional client-reported session usage."""
    from src.services.attention_budget import build_attention_budget_summary

    usage = {"research": research, "portfolio": portfolio, "market": market}
    return sanitize_for_json(build_attention_budget_summary(usage=usage))


@router.get("/api/v7/knowledge/lessons")
async def knowledge_lessons(ticker: str = Query(..., min_length=1, max_length=10)):
    """Prior lessons from decision journal + belief review for ticker."""
    from src.api.deps import validate_ticker
    from src.services.knowledge_retrieval import build_ticker_lessons

    sym = validate_ticker(ticker)
    try:
        payload = await asyncio.to_thread(build_ticker_lessons, sym)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    payload["generated_at"] = datetime.now(timezone.utc).isoformat() + "Z"
    return sanitize_for_json(payload)


@router.get("/api/v7/pre-decision/gate")
async def pre_decision_gate(ticker: str = Query("", max_length=10)):
    """
    Pre-decision gate bundle — readiness, red team, outside view, journal status.

    Display only when deploy_open; never grants deploy authority.
    """
    from src.api.deps import validate_ticker
    from src.services.decision_journal import deploy_intent_journal_status
    from src.services.decision_readiness import load_checklist
    from src.services.outside_view import build_outside_view_base_rate
    from src.services.red_team import build_red_team_challenge

    sym = str(ticker or "").strip().upper()
    deploy_open = False
    setup_type = "generic_breakout"
    decision_id = ""
    if not sym and _today_cache:
        ba = _today_cache.get("best_action") or {}
        td = _today_cache.get("todays_decision") or {}
        ss = _today_cache.get("system_state") or {}
        deploy_open = bool(ss.get("deploy_open"))
        if deploy_open:
            sym = str(
                (ba.get("best_trade_now") or td.get("best_trade") or {}).get("ticker") or ""
            ).upper()
        top = (_today_cache.get("top_ranked") or [None])[0]
        if isinstance(top, dict):
            if not sym:
                sym = str(top.get("ticker") or "").upper()
            setup_type = str(top.get("setup_type") or top.get("pattern") or setup_type)
            decision_id = str(top.get("decision_id") or "")
    else:
        try:
            from src.services.decision_board_service import build_decision_board

            board = build_decision_board()
            deploy_open = bool((board.get("system_state") or {}).get("deploy_open"))
        except Exception:
            pass

    if sym:
        try:
            sym = validate_ticker(sym)
        except HTTPException:
            sym = sym[:10]

    checklist = load_checklist(sym) if sym else {"complete": False, "ticker": sym}
    red_team = build_red_team_challenge(ticker=sym or "GENERIC")
    outside_view = build_outside_view_base_rate(setup_type=setup_type)
    journal = deploy_intent_journal_status(decision_id=decision_id, ticker=sym)

    return sanitize_for_json(
        {
            "authority": "research_only",
            "may_authorize_deploy": False,
            "deploy_open": deploy_open,
            "visible": bool(deploy_open and sym),
            "ticker": sym or None,
            "setup_type": setup_type,
            "decision_id": decision_id or None,
            "checklist": checklist,
            "red_team": red_team,
            "outside_view": outside_view,
            "journal": journal,
            "headline": "Pre-Decision Gate · 部署前閘 — acknowledge checklist (display only)",
            "generated_at": datetime.now(timezone.utc).isoformat() + "Z",
        }
    )


@router.post("/api/v7/decision-cooling/start")
async def decision_cooling_start(body: Dict[str, Any]):
    """Start 10-minute cooling window — research_only; no deploy authority."""
    from src.api.deps import validate_ticker
    from src.services.decision_cooling import start_cooling

    sym = validate_ticker(str((body or {}).get("ticker") or ""))
    counterargument = str((body or {}).get("counterargument") or "")
    try:
        payload = start_cooling(sym, counterargument=counterargument)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    payload["ok"] = True
    payload["generated_at"] = datetime.now(timezone.utc).isoformat() + "Z"
    return sanitize_for_json(payload)


@router.get("/api/v7/decision-cooling/status")
async def decision_cooling_status(
    session_id: str = Query(..., min_length=4, max_length=64),
):
    """Poll cooling session — READY_TO_CONFIRM when window elapses."""
    from src.services.decision_cooling import get_status

    try:
        payload = get_status(session_id)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    payload["generated_at"] = datetime.now(timezone.utc).isoformat() + "Z"
    return sanitize_for_json(payload)


@router.post("/api/v7/decision-cooling/cancel")
async def decision_cooling_cancel(body: Dict[str, Any]):
    """Cancel cooling — WAIT / quality drop / portfolio change / new evidence."""
    from src.services.decision_cooling import cancel_cooling

    session_id = str((body or {}).get("session_id") or "")
    reason = str((body or {}).get("reason") or "operator_cancel")
    try:
        payload = cancel_cooling(session_id, reason=reason)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    payload["ok"] = True
    payload["generated_at"] = datetime.now(timezone.utc).isoformat() + "Z"
    return sanitize_for_json(payload)


# ══════════════════════════════════════════════════════════════════════
# /api/v8/portfolios — 3 Model Portfolios vs SPY
# ══════════════════════════════════════════════════════════════════════

# Module-level singleton so portfolio state persists across requests
_model_portfolio_engine = None


def _get_portfolio_engine():
    global _model_portfolio_engine
    if _model_portfolio_engine is None:
        from src.services.strategy_portfolio_lab import ModelPortfolioEngine

        _model_portfolio_engine = ModelPortfolioEngine()
    return _model_portfolio_engine


@router.get("/api/v8/portfolios")
async def model_portfolios(request: Request):
    """3 model portfolios (momentum / breakout / swing) vs SPY.

    Returns live stats for each sleeve:
      - win rate, avg R, total return, Sharpe, max drawdown
      - alpha vs SPY
      - plain-English explanation of why each sleeve is winning/losing
      - strategy keep/discard verdicts from MetaEnsemble
    """
    engine = _get_portfolio_engine()

    # Fetch SPY return for benchmark comparison
    spy_return = 0.0
    try:
        mds = request.app.state.market_data
        hist = await mds.get_history("SPY", period="1y", interval="1d")
        if hist is not None and len(hist) >= 2:
            c = "Close" if "Close" in hist.columns else "close"
            spy_return = round(
                (float(hist[c].iloc[-1]) / float(hist[c].iloc[0]) - 1) * 100, 2
            )
    except Exception as exc:
        logger.debug("SPY return unavailable: %s", exc)

    summary = engine.summary(spy_return_pct=spy_return)

    # Strategy keep/discard verdicts from MetaEnsemble
    strategy_verdicts = []
    try:
        meta = _meta()
        if meta is not None:
            verdicts = meta.evaluate_strategies()
            strategy_verdicts = [v.to_dict() for v in verdicts]
    except Exception as exc:
        logger.debug("MetaEnsemble verdicts unavailable: %s", exc)

    # Factor combo golden rules (from closed trades)
    golden_rules = []
    try:
        from src.engines.strategy_optimizer import FactorComboTester

        trades = []
        loop = _learning_loop()
        if loop is not None:
            trades = loop.get_trade_log(limit=500)
        if len(trades) >= 30:
            tester = FactorComboTester()
            rules = tester.get_golden_rules(trades, min_oos_sharpe=0.5)
            golden_rules = [r.to_dict() for r in rules[:10]]
    except Exception as exc:
        logger.debug("Golden rules unavailable: %s", exc)

    return {
        **summary,
        "strategy_verdicts": strategy_verdicts,
        "golden_rules": golden_rules,
        "generated_at": datetime.now(timezone.utc).isoformat() + "Z",
    }


@router.post("/api/v8/portfolios/{sleeve}/trade")
async def record_portfolio_trade(
    sleeve: str,
    ticker: str = Query(..., description="Ticker symbol"),
    entry_price: float = Query(..., description="Entry price"),
    exit_price: float = Query(..., description="Exit price"),
    r_multiple: float = Query(0.0, description="R-multiple achieved"),
    regime: str = Query("", description="Regime at entry"),
):
    """Record a closed trade into a model portfolio sleeve.

    sleeve must be one of: momentum | breakout | swing
    """
    from src.services.strategy_portfolio_lab import SLEEVE_NAMES

    if sleeve not in SLEEVE_NAMES:
        from fastapi import HTTPException

        raise HTTPException(
            400,
            f"Unknown sleeve '{sleeve}'. Valid: {SLEEVE_NAMES}",
        )

    engine = _get_portfolio_engine()
    engine.record_trade(
        sleeve=sleeve,
        ticker=ticker.upper(),
        entry_price=entry_price,
        exit_price=exit_price,
        r_multiple=r_multiple,
        regime=regime,
        closed_at=datetime.now(timezone.utc).isoformat(),
    )

    sleeve_stats = engine.get_sleeve(sleeve)
    return {
        "recorded": True,
        "sleeve": sleeve,
        "ticker": ticker.upper(),
        "pnl_pct": (
            round((exit_price - entry_price) / entry_price * 100, 2)
            if entry_price > 0
            else 0
        ),
        "sleeve_stats": sleeve_stats.to_dict() if sleeve_stats else {},
        "generated_at": datetime.now(timezone.utc).isoformat() + "Z",
    }


# ══════════════════════════════════════════════════════════════════════
# /api/v8/rs — 3-Layer Relative Strength
# ══════════════════════════════════════════════════════════════════════


@router.get("/api/v8/rs")
async def three_layer_rs(
    request: Request,
    sector: str = Query(None, description="Filter by sector"),
):
    """3-layer RS: stock vs SPY → vs sector ETF → vs peers.

    Returns ranked list with rs_vs_spy, rs_vs_sector_etf, rs_vs_peers
    and a three_layer_verdict for each ticker.
    """
    scanned, _ = await request.app.state.scan_signals(limit=100)

    # Build universe from scanned signals
    universe = []
    for sig in scanned:
        universe.append(
            {
                "ticker": sig.get("ticker", ""),
                "sector": sig.get("sector", ""),
                "market_cap": sig.get("market_cap", ""),
                "price": sig.get("entry_price", 0),
                "change_pct": sig.get("change_pct", 0),
                "return_1w": sig.get("return_1w", 0),
                "return_1m": sig.get("return_1m", 0),
                "return_3m": sig.get("return_3m", 0),
                "return_6m": sig.get("return_6m", 0),
            }
        )

    if sector:
        universe = [
            u for u in universe if u.get("sector", "").lower() == sector.lower()
        ]

    # Sector ETF map (standard SPDR ETFs)
    sector_etf_map = {
        "Technology": "XLK",
        "Financials": "XLF",
        "Healthcare": "XLV",
        "Energy": "XLE",
        "Consumer Discretionary": "XLY",
        "Consumer Staples": "XLP",
        "Industrials": "XLI",
        "Materials": "XLB",
        "Utilities": "XLU",
        "Real Estate": "XLRE",
        "Communication Services": "XLC",
    }

    # Fetch sector ETF returns
    sector_etf_returns = {}
    try:
        mds = request.app.state.market_data
        for sec_name, etf in sector_etf_map.items():
            try:
                hist = await mds.get_history(etf, period="6mo", interval="1d")
                if hist is not None and len(hist) >= 20:
                    c = "Close" if "Close" in hist.columns else "close"
                    prices = hist[c].values.astype(float)
                    n = len(prices)
                    sector_etf_returns[sec_name] = {
                        "return_1w": round(
                            (prices[-1] / prices[max(n - 5, 0)] - 1) * 100, 2
                        ),
                        "return_1m": round(
                            (prices[-1] / prices[max(n - 21, 0)] - 1) * 100, 2
                        ),
                        "return_3m": round(
                            (prices[-1] / prices[max(n - 63, 0)] - 1) * 100, 2
                        ),
                        "return_6m": round((prices[-1] / prices[0] - 1) * 100, 2),
                    }
            except Exception:
                pass
    except Exception as exc:
        logger.debug("Sector ETF data unavailable: %s", exc)

    engine = _rs_engine()
    results = engine.three_layer_rs(
        universe=universe,
        sector_etf_returns=sector_etf_returns or None,
    )

    # Sort by rs_vs_spy descending
    results.sort(key=lambda x: x.get("rs_vs_spy", 0), reverse=True)

    return {
        "count": len(results),
        "sector_filter": sector,
        "results": results,
        "sector_etfs_loaded": list(sector_etf_returns.keys()),
        "generated_at": datetime.now(timezone.utc).isoformat() + "Z",
    }


@router.post("/api/v7/today/ai-narrative")
async def generate_today_ai_narrative(payload: dict):
    """Standalone AI narrative decoupled from the hot path.

    Returns the literal provider + model used so the UI can display
    real attribution (no decorative badges). When no LLM is configured,
    returns a deterministic stub so Generate always produces text.
    """
    regime_ctx = payload.get("regime_ctx") or {}
    top5 = payload.get("top_5") or []
    market_pulse = payload.get("market_pulse") or {}
    funnel = payload.get("filter_funnel") or {}
    board_narrative = payload.get("narrative") or ""

    try:
        from src.services.ai_service import (
            AI_SETUP_HINT,
            build_stub_narrative,
            get_ai_service,
        )

        ai = get_ai_service()
        try:
            await asyncio.wait_for(ai.probe_local_llm(), timeout=3.0)
        except (asyncio.TimeoutError, Exception):
            logger.debug("Local LLM probe skipped or timed out for ai-narrative")

        if not ai.is_configured:
            from src.services.usage_log import record_surface_event

            record_surface_event(
                surface="ai_narrative",
                event="stub",
                meta={"reason": "unconfigured", "authority": "research_only"},
            )
            return {
                "ai_narrative": build_stub_narrative(
                    regime_ctx, top5, market_pulse, funnel, board_narrative
                ),
                "provider": "stub",
                "model": "deterministic",
                "configured": False,
                "research_only": True,
                "authority": "research_only",
                "message": "LLM not configured — showing rule-based narrative.",
                "setup_hint": AI_SETUP_HINT,
            }

        narrative = await ai.generate_narrative(regime_ctx, top5, market_pulse, funnel)
        if narrative:
            from src.services.usage_log import record_ai_call, record_surface_event

            record_surface_event(
                surface="ai_narrative",
                event="generate",
                meta={
                    "provider": getattr(ai, "_provider_used", "unknown"),
                    "model": getattr(ai, "_last_model", ""),
                    "authority": "research_only",
                },
            )
            record_ai_call(
                task="today_narrative",
                provider=getattr(ai, "_provider_used", "unknown"),
                model=getattr(ai, "_last_model", ""),
                success=True,
                chars=len(narrative),
            )
            return {
                "ai_narrative": narrative,
                "provider": getattr(ai, "_provider_used", "unknown"),
                "model": getattr(ai, "_last_model", ""),
                "configured": True,
                "research_only": True,
                "authority": "research_only",
            }

        stub = build_stub_narrative(
            regime_ctx, top5, market_pulse, funnel, board_narrative
        )
        logger.warning("AI narrative generation returned empty — using stub fallback")
        return {
            "ai_narrative": stub,
            "provider": "stub",
            "model": "deterministic",
            "configured": True,
            "research_only": True,
            "authority": "research_only",
            "message": "LLM call failed — showing rule-based fallback.",
            "setup_hint": "",
        }
    except Exception as exc:
        logger.warning("AI narrative generation failed: %s", exc)
        try:
            from src.services.ai_service import AI_SETUP_HINT, build_stub_narrative

            stub = build_stub_narrative(
                regime_ctx, top5, market_pulse, funnel, board_narrative
            )
        except Exception:
            stub = f"Error generating commentary: {exc}"
        return {
            "ai_narrative": stub,
            "provider": "error",
            "model": "",
            "configured": False,
            "research_only": True,
            "authority": "research_only",
            "message": f"Error: {exc}",
            "setup_hint": AI_SETUP_HINT,
        }


@router.post("/api/v7/override-journal/entry")
async def override_journal_entry(body: Dict[str, Any]):
    """Log operator override — research_only audit trail."""
    from src.services.override_journal import record_override

    payload = record_override(
        advice_class=str((body or {}).get("advice_class") or "cc_recommendation"),
        action=str((body or {}).get("action") or "ignored"),
        reason=str((body or {}).get("reason") or ""),
        ticker=str((body or {}).get("ticker") or ""),
        decision_id=str((body or {}).get("decision_id") or ""),
    )
    payload["ok"] = True
    return sanitize_for_json(payload)


@router.get("/api/v7/override-journal/summary")
async def override_journal_summary():
    """Override journal + cooldown status."""
    from src.services.override_journal import build_override_summary

    return sanitize_for_json(build_override_summary())


@router.get("/api/v7/calibration/report")
async def calibration_report():
    """Quarterly-style calibration — research_only."""
    from src.services.calibration_report import build_calibration_report

    return sanitize_for_json(build_calibration_report())


@router.get("/api/v7/weekly-ic/digest")
async def weekly_ic_digest(request: Request):
    """Weekly Investment Committee one-pager."""
    from src.services.weekly_ic_digest import build_weekly_ic_digest

    board = _today_payload_for_board(request) or {}
    return sanitize_for_json(build_weekly_ic_digest(board=board))


@router.post("/api/v7/usage-log/event")
async def usage_log_event(body: Dict[str, Any]):
    """MIE surface usage event — open/dismiss/ignore."""
    from src.services.usage_log import record_surface_event

    payload = record_surface_event(
        surface=str((body or {}).get("surface") or "unknown"),
        event=str((body or {}).get("event") or "open"),
        tab=str((body or {}).get("tab") or ""),
        meta=(body or {}).get("meta") if isinstance((body or {}).get("meta"), dict) else {},
    )
    payload["ok"] = True
    return sanitize_for_json(payload)


@router.get("/api/v7/usage-log/summary")
async def usage_log_summary():
    """MIE usage summary + deletion candidates."""
    from src.services.usage_log import build_usage_summary

    return sanitize_for_json(build_usage_summary())

