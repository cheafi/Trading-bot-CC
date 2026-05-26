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
import os
import time
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, HTTPException, Query, Request

from src.services.regime_service import get_regime as _fetch_regime

logger = logging.getLogger(__name__)

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
_TODAY_CACHE_TTL = 90.0
_TODAY_SCAN_TIMEOUT = 3.0


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
    rr = signal.get("risk_reward", 0)
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
    if signal.get("risk_reward", 0) >= 3.0:
        rr = signal["risk_reward"]
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
    rr = signal.get("risk_reward", 0)

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


# ══════════════════════════════════════════════════════════════════════
# /api/v7/today — Decision Homepage
# ══════════════════════════════════════════════════════════════════════


def _scan_cache_has_recs(request: Request) -> bool:
    sc = getattr(request.app.state, "scan_cache", None) or {}
    return bool(sc.get("recs"))


@router.get("/api/v7/today")
async def today_summary(request: Request):
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
            return _today_cache
    if _today_lock.locked():
        cached = _cached_today_payload("fresh scan already running")
        if cached:
            return cached
        return _stale_today_payload("fresh scan already running")

    async with _today_lock:
        now_ts = time.time()
        if _today_cache and now_ts - _today_cache_ts < _TODAY_CACHE_TTL:
            return _today_cache

    # 1. Market Regime
    regime_state = await _fetch_regime(request)
    regime_label = getattr(regime_state, "regime", "NEUTRAL")
    should_trade = getattr(regime_state, "should_trade", True)
    confidence = getattr(regime_state, "confidence", 0.5)
    vix_val = getattr(regime_state, "vix", 18.0)
    breadth = getattr(regime_state, "breadth_pct", 0.50)
    breadth_val = round(float(breadth) * 100) if float(breadth) <= 1.0 else round(float(breadth))
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
    score = max(
        0,
        min(
            100,
            int(confidence * 100) if isinstance(confidence, (int, float)) else 50,
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
            timeout=1.25,
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

    # 4. Filter funnel
    universe = len(getattr(request.app.state, "_scan_watchlist", []))
    if universe == 0:
        universe = len(getattr(request.app.state, "scan_watchlist", []))

    triggered = len(scanned)
    high_score = len([s for s in scanned if s.get("score", 0) >= 6.0])
    actionable = len([s for s in scanned if s.get("score", 0) >= 7.0])
    high_conv = len([s for s in scanned if s.get("score", 0) >= 8.0])

    funnel = {
        "universe": universe,
        "signals_triggered": triggered,
        "score_above_6": high_score,
        "actionable_above_7": actionable,
        "high_conviction_above_8": high_conv,
    }

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

    top5 = []
    seen_tickers = set()
    for cr in council_results:
        pr = cr.pipeline
        sig = pr.signal
        ticker = sig.get("ticker", "")
        if ticker in seen_tickers:
            continue
        seen_tickers.add(ticker)

        top5.append(
            {
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
                "action": pr.decision.action,
                "action_reason": pr.decision.rationale,
                "why_now": ([pr.explanation.why_now] if pr.explanation.why_now else []),
                "entry_price": sig.get("entry_price", 0),
                "target_price": sig.get("target_price", 0),
                "stop_price": sig.get("stop_price", 0),
                "risk_reward": sig.get("risk_reward", 0)
                or pr.decision.risk_reward_ratio
                or 0,
                "rsi": sig.get("rsi", 0),
                "invalidation": pr.explanation.invalidation,
                "position_hint": _position_hint(sig, should_trade),
                "sector_bucket": pr.sector.sector_bucket.value,
                "final_conf": round(pr.confidence.final, 2),
                "confidence_breakdown": pr.confidence.to_dict(),
                "decision": pr.decision.to_dict(),
                "explanation": pr.explanation.to_dict(),
                "expert_council": cr.verdict.to_dict(),
            }
        )
        if len(top5) >= 5:
            break

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
                "rr": sig.get("risk_reward", 0) or pr.decision.risk_reward_ratio or 0,
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
    trade_count = sum(
        1 for c in top5 if c.get("action") in ("TRADE", "BUY", "BUY_ON_DIP")
    )

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

    # 9. Tradeability
    if not should_trade:
        tradeability = "NO_TRADE"
    elif high_conv >= 3:
        tradeability = "STRONG_TRADE"
    elif actionable >= 3:
        tradeability = "TRADE"
    elif actionable >= 1:
        tradeability = "SELECTIVE"
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
        f"{a.get('ticker', '—')}: {a.get('reason')}" if a.get("ticker") != "—" else a.get("reason", "")
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
    if high_conv >= 3:
        what_changed.append(f"{high_conv} high-conviction signals (≥8.0)")
    if best_family:
        what_changed.append(f"Leading setup family: {best_family}")
    # Sector movers
    leaders = market_pulse.get("sector_leaders", [])
    if leaders and leaders[0].get("change_pct", 0) > 1.0:
        ldr = leaders[0]
        what_changed.append(
            f"Sector leader: {ldr['name']}" f" +{ldr['change_pct']:.1f}%"
        )
    laggards = market_pulse.get("sector_laggards", [])
    if laggards and laggards[0].get("change_pct", 0) < -1.0:
        what_changed.append(
            f"Sector laggard: {laggards[0]['name']} "
            f"{laggards[0]['change_pct']:.1f}%"
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
        build_evidence_badges,
        build_monitor_triggers,
        build_near_miss_candidates,
        build_no_setup_diagnosis,
        build_regime_wait_explanation,
        build_sleeve_summary,
    )

    top5_tickers = {x["ticker"] for x in top5 if x.get("ticker")}
    near_miss = build_near_miss_candidates(council_results, top5_tickers, limit=3)
    no_setup_diagnosis = build_no_setup_diagnosis(
        council_results, scanner_degraded=scanner_degraded
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
    monitor_triggers = build_monitor_triggers(
        market_pulse=market_pulse,
        near_miss=near_miss,
        vix=vix_val,
        breadth=breadth * 100 if breadth <= 1 else breadth,
        tradeability=tradeability,
    )
    sleeve_summary: Dict[str, Any] = {"cards": [], "note": "lazy-load via /api/fund-lab/cards"}
    fund_cards: List[Dict[str, Any]] = []
    fund_cache = getattr(request.app.state, "fund_cards_cache", None)
    if isinstance(fund_cache, dict) and fund_cache.get("cards"):
        fund_cards = fund_cache.get("cards") or []
    else:
        try:
            from src.api.routers.funds import _build_payload

            pl = await _build_payload(
                request, benchmark="SPY", period="1y", top_n=5
            )
            fund_cards = pl.get("cards") or []
            fund_cache = getattr(request.app.state, "fund_cards_cache", None)
        except Exception:
            logger.debug("fund cards preload for today failed", exc_info=True)
    if fund_cards:
        sleeve_summary = build_sleeve_summary(fund_cards, regime=regime_label)

    top5_for_action = [
        {
            "ticker": x["ticker"],
            "action": x["action"],
            "final_conf": (x.get("confidence_breakdown") or {}).get("final", 0.6),
            "entry_price": x.get("entry_price"),
            "stop_price": x.get("stop_price"),
            "upgrade_trigger": (x.get("explanation") or {}).get("upgrade_trigger"),
            "invalidation": x.get("invalidation"),
            "sector_type": x.get("sector_bucket"),
        }
        for x in top5
    ]
    try:
        from src.api.app_state import get_engine
        from src.services.best_action import build_best_action, compute_theme_overlap
        from src.services.execution_readiness import build_execution_readiness
        from src.services.ibkr_service import get_ibkr_service

        ibkr_st = get_ibkr_service().status()
        engine = get_engine(request.app)
        eng_running = bool(getattr(engine, "_running", False)) if engine else False
        eng_breaker = bool(getattr(engine, "circuit_breaker_triggered", False)) if engine else False
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

    payload = {
        "date": now.strftime("%Y-%m-%d"),
        "narrative": narrative,
        "market_regime": {
            "label": regime_label,
            "risk_state": risk_state,
            "should_trade": should_trade,
            "confidence": round(confidence, 2),
            "tradeability": tradeability,
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
        "overlap_warning": overlap_warning,
        "near_miss": near_miss,
        "no_setup_diagnosis": no_setup_diagnosis,
        "regime_wait_explanation": regime_wait_explanation,
        "monitor_triggers": monitor_triggers,
        "sleeve_summary": sleeve_summary,
        "execution_readiness": execution_readiness,
        "evidence_badges": build_evidence_badges(
            scanner_degraded=scanner_degraded,
            regime_synthetic=bool(getattr(request.app.state, "regime_synthetic", False)),
            ai_powered=False,
        ),
        "cross_asset_confirmation": await _cross_asset_for_today(
            request,
            market_regime={
                "trend": trend_label,
                "vix": round(vix_val, 1),
                "breadth": round(breadth * 100),
                "should_trade": should_trade,
                "tradeability": tradeability,
            },
            should_trade=should_trade,
        ),
        "trust": {
            "mode": "LIVE" if should_trade else "PAPER",
            "source": (
                "decision_engine"
                if not scanner_degraded
                else "decision_engine_degraded"
            ),
            "freshness": "REAL_TIME" if not scanner_degraded else "DEGRADED",
            "stale": scanner_degraded,
            "reason": scanner_reason,
            "as_of": now.isoformat() + "Z",
            "ai_powered": False,
        },
        "generated_at": now.isoformat() + "Z",
    }
    if not scanner_degraded:
        _today_cache = payload
        _today_cache_ts = time.time()
    else:
        _today_cache = None
        _today_cache_ts = 0.0
    try:
        request.app.state.today_v7_cache = payload
    except Exception:
        pass
    return payload


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
    should_trade = getattr(regime_state, "should_trade", True)

    scanned, _ = await request.app.state.scan_signals(limit=100)

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

    enriched = []
    for cr in council_results:
        pr = cr.pipeline
        sig = pr.signal
        enriched.append(
            {
                "ticker": sig.get("ticker", ""),
                "strategy": _setup_family(sig.get("strategy", "")),
                "score": pr.fit.final_score,
                "grade": pr.fit.grade,
                "timing": _timing_label(
                    abs(sig.get("entry_price", 0) - sig.get("stop_price", 0))
                    / max(sig.get("entry_price", 1), 1)
                    * 100
                ),
                "risk_reward": sig.get("risk_reward", 0),
                "rsi": sig.get("rsi", 0),
                "vol_quality": (
                    "HIGH"
                    if sig.get("vol_ratio", 0) > 1.5
                    else ("OK" if sig.get("vol_ratio", 0) > 0.8 else "LOW")
                ),
                "sector_bucket": pr.sector.sector_bucket.value,
                "regime_fit": sig.get("regime", ""),
                "entry_price": sig.get("entry_price", 0),
                "target_price": sig.get("target_price", 0),
                "stop_price": sig.get("stop_price", 0),
                "action": pr.decision.action,
                "action_reason": pr.decision.rationale,
                "why_now": ([pr.explanation.why_now] if pr.explanation.why_now else []),
                "position_hint": _position_hint(sig, should_trade),
                "confidence_breakdown": pr.confidence.to_dict(),
                "decision": pr.decision.to_dict(),
                "expert_council": cr.verdict.to_dict(),
            }
        )

    # Sort
    sort_keys = {
        "score": lambda x: -x["score"],
        "timing": lambda x: [
            "NEAR_PIVOT",
            "EARLY",
            "ON_TIME",
            "EXTENDED",
            "LATE",
        ].index(x["timing"]),
        "risk_reward": lambda x: -x["risk_reward"],
        "strategy": lambda x: x["strategy"],
    }
    sort_fn = sort_keys.get(sort_by, sort_keys["score"])
    enriched.sort(key=sort_fn)

    # Add rank
    for i, item in enumerate(enriched[:limit], 1):
        item["rank"] = i

    return {
        "regime_allows_trading": should_trade,
        "total_signals": len(enriched),
        "opportunities": enriched[:limit],
        "sort_by": sort_by,
        "generated_at": datetime.now(timezone.utc).isoformat() + "Z",
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
    from src.services.confidence import (
        compute_4layer_confidence as _compute_4layer_confidence,
    )
    from src.services.indicators import compute_indicators as _compute_indicators
    from src.engines.conformal_predictor import ConformalPredictor

    ticker = ticker.upper().strip()
    mds = request.app.state.market_data
    regime_state = await _fetch_regime(request)
    should_trade = getattr(regime_state, "should_trade", True)

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
    should_trade = getattr(regime_state, "should_trade", True)
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
    real attribution (no decorative badges).
    """
    try:
        from src.services.ai_service import get_ai_service

        ai = get_ai_service()
        if not ai.is_configured:
            return {
                "ai_narrative": None,
                "provider": "none",
                "model": "",
                "configured": False,
            }

        regime_ctx = payload.get("regime_ctx", {})
        top5 = payload.get("top_5", [])
        market_pulse = payload.get("market_pulse", {})
        funnel = payload.get("filter_funnel", {})

        narrative = await ai.generate_narrative(regime_ctx, top5, market_pulse, funnel)
        return {
            "ai_narrative": narrative,
            "provider": getattr(ai, "_provider_used", "unknown"),
            "model": getattr(ai, "_last_model", ""),
            "configured": True,
        }
    except Exception as exc:
        return {
            "ai_narrative": f"Error: {exc}",
            "provider": "error",
            "model": "",
            "configured": False,
        }
