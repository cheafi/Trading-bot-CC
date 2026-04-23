"""
CC — Decision Product API (Sprint 57)
======================================
Transforms raw signals into decision-ready endpoints:
  /api/v7/today          — Market regime + top picks + filter funnel + action
  /api/v7/opportunities  — Ranked candidates with why-now/why-not/action
  /api/v7/filter-funnel  — Universe → actionable pipeline visualization
  /api/v7/signal-card/{ticker} — Decision-grade signal card
"""

import logging
from datetime import datetime, timezone
from typing import Dict, List

from fastapi import APIRouter, HTTPException, Query, Request

logger = logging.getLogger(__name__)

router = APIRouter(tags=["decision-product"])


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
        reasons.append(f"R:R {signal['risk_reward']:.1f} — excellent risk/reward")
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


# ══════════════════════════════════════════════════════════════════════
# /api/v7/today — Decision Homepage
# ══════════════════════════════════════════════════════════════════════


@router.get("/api/v7/today")
async def today_summary(request: Request):
    """Decision homepage: regime + top 5 + filter funnel + action guidance.

    This is the first thing a trader should see — answers:
    "Should I trade today? What are the best opportunities? What to avoid?"
    """
    from src.api.main import _get_regime, _scan_live_signals

    # 1. Market Regime
    regime_state = await _get_regime()
    regime_label = getattr(regime_state, "regime", "NEUTRAL")
    should_trade = getattr(regime_state, "should_trade", True)
    confidence = getattr(regime_state, "confidence", 0.5)

    risk_state = (
        "RISK_ON"
        if regime_label == "RISK_ON"
        else ("RISK_OFF" if regime_label == "RISK_OFF" else "NEUTRAL")
    )

    # 2. Scan signals
    scanned, scores = await _scan_live_signals(limit=50)

    # 3. Filter funnel
    universe = len(getattr(request.app.state, "_scan_watchlist", []))
    if universe == 0:
        from src.api.main import _SCAN_WATCHLIST

        universe = len(_SCAN_WATCHLIST)

    total_scanned = universe
    with_data = len(scanned) + max(0, universe - len(scanned))
    triggered = len(scanned)
    high_score = len([s for s in scanned if s.get("score", 0) >= 6.0])
    actionable = len([s for s in scanned if s.get("score", 0) >= 7.0])

    funnel = {
        "universe": total_scanned,
        "data_available": with_data,
        "signals_triggered": triggered,
        "score_above_6": high_score,
        "actionable_above_7": actionable,
    }

    # 4. Top 5 ranked
    ranked = sorted(scanned, key=lambda x: x.get("score", 0), reverse=True)
    top5 = []
    for rank, sig in enumerate(ranked[:5], 1):
        distance = abs(sig.get("entry_price", 0) - sig.get("stop_price", 0))
        dist_pct = (
            (distance / sig["entry_price"] * 100) if sig.get("entry_price") else 0
        )
        timing = _timing_label(dist_pct)
        sig["_timing"] = timing
        action, action_reason = _action_from_signal(sig, should_trade)

        top5.append(
            {
                "rank": rank,
                "ticker": sig.get("ticker", ""),
                "strategy": _setup_family(sig.get("strategy", "")),
                "score": sig.get("score", 0),
                "timing": timing,
                "action": action,
                "why_now": _why_now(sig)[:2],
                "risk_reward": sig.get("risk_reward", 0),
            }
        )

    # 5. Best setup family today
    family_counts: Dict[str, int] = {}
    family_scores: Dict[str, float] = {}
    for sig in scanned:
        fam = _setup_family(sig.get("strategy", ""))
        family_counts[fam] = family_counts.get(fam, 0) + 1
        family_scores[fam] = family_scores.get(fam, 0) + sig.get("score", 0)

    best_family = None
    if family_scores:
        best_family = max(
            family_scores, key=lambda k: family_scores[k] / max(family_counts[k], 1)
        )

    # 6. Avoid list
    avoid = []
    if not should_trade:
        avoid.append("All new positions — regime unfavorable")
    if regime_label == "RISK_OFF":
        avoid.append("Aggressive breakouts — risk-off environment")
        avoid.append("Extended momentum plays — reversal risk")
    if confidence < 0.4:
        avoid.append("Large positions — low regime confidence")

    # 7. Trade/Wait/Avoid summary
    if not should_trade:
        tradeability = "NO_TRADE"
        trade_summary = "Market regime says wait. No new positions."
    elif actionable >= 3:
        tradeability = "TRADE"
        trade_summary = f"{actionable} actionable ideas. Focus on top-ranked."
    elif actionable >= 1:
        tradeability = "SELECTIVE"
        trade_summary = f"Only {actionable} idea(s) qualify. Be selective."
    else:
        tradeability = "WAIT"
        trade_summary = "No high-conviction setups today. Watch only."

    # 8. What Changed (compare to yesterday-like heuristics)
    what_changed = []
    if regime_label == "RISK_OFF":
        what_changed.append("Regime shifted to RISK_OFF — defensive posture")
    if actionable >= 5:
        what_changed.append(f"{actionable} signals above 7.0 — opportunity cluster")
    if best_family:
        what_changed.append(f"Best setup family: {best_family}")
    for sig in ranked[:3]:
        t = sig.get("ticker", "?")
        s = sig.get("score", 0)
        what_changed.append(f"{t} scored {s:.1f} — top of today's board")

    # 9. Event risk (basic — earnings proximity, VIX, etc.)
    event_risks = []
    vix_level = getattr(regime_state, "vix", None)
    if vix_level and vix_level > 25:
        event_risks.append(f"VIX at {vix_level:.0f} — elevated fear")
    if not should_trade:
        event_risks.append("Regime guard active — no new entries")

    now = datetime.now(timezone.utc)

    return {
        "date": now.strftime("%Y-%m-%d"),
        "market_regime": {
            "label": regime_label,
            "risk_state": risk_state,
            "should_trade": should_trade,
            "confidence": round(confidence, 2),
            "tradeability": tradeability,
            "summary": trade_summary,
            "trend": getattr(regime_state, "trend", "UNKNOWN"),
            "volatility": getattr(regime_state, "volatility", "NORMAL"),
            "score": getattr(regime_state, "score", 50),
        },
        "top_5": top5,
        "filter_funnel": funnel,
        "best_setup_family": best_family,
        "avoid": avoid,
        "what_changed": what_changed,
        "event_risks": event_risks,
        "trust": {
            "mode": "LIVE" if should_trade else "PAPER",
            "source": "decision_engine",
            "freshness": "REAL_TIME",
            "as_of": now.isoformat() + "Z",
        },
        "generated_at": now.isoformat() + "Z",
    }


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
    from src.api.main import _get_regime, _scan_live_signals

    regime_state = await _get_regime()
    should_trade = getattr(regime_state, "should_trade", True)

    scanned, _ = await _scan_live_signals(limit=100)

    # Filter
    if setup_filter:
        scanned = [s for s in scanned if s.get("strategy") == setup_filter]
    if min_score > 0:
        scanned = [s for s in scanned if s.get("score", 0) >= min_score]

    # Enrich with decision fields
    enriched = []
    for sig in scanned:
        distance = abs(sig.get("entry_price", 0) - sig.get("stop_price", 0))
        dist_pct = (
            (distance / sig["entry_price"] * 100) if sig.get("entry_price") else 0
        )
        timing = _timing_label(dist_pct)
        sig["_timing"] = timing
        action, action_reason = _action_from_signal(sig, should_trade)

        sma20_dist = 0
        entry = sig.get("entry_price", 0)

        enriched.append(
            {
                "ticker": sig.get("ticker", ""),
                "strategy": _setup_family(sig.get("strategy", "")),
                "score": sig.get("score", 0),
                "grade": sig.get("grade", ""),
                "timing": timing,
                "risk_reward": sig.get("risk_reward", 0),
                "rsi": sig.get("rsi", 0),
                "vol_quality": (
                    "HIGH"
                    if sig.get("vol_ratio", 0) > 1.5
                    else ("OK" if sig.get("vol_ratio", 0) > 0.8 else "LOW")
                ),
                "regime_fit": sig.get("regime", ""),
                "entry_price": sig.get("entry_price", 0),
                "target_price": sig.get("target_price", 0),
                "stop_price": sig.get("stop_price", 0),
                "action": action,
                "action_reason": action_reason,
                "why_now": _why_now(sig),
                "why_not": _why_not(sig),
                "invalidation": _invalidation(sig),
                "position_hint": _position_hint(sig, should_trade),
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
    from src.api.main import _SCAN_WATCHLIST, _scan_live_signals

    scanned, _ = await _scan_live_signals(limit=100)

    # Build funnel stages
    universe = len(_SCAN_WATCHLIST)
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
    from src.api.main import (
        _compute_4layer_confidence,
        _compute_indicators,
        _get_regime,
    )
    from src.engines.conformal_predictor import ConformalPredictor
    from src.engines.expert_committee import ExpertCommittee

    ticker = ticker.upper().strip()
    mds = request.app.state.market_data
    regime_state = await _get_regime()
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

        # Expert committee
        ec = ExpertCommittee()
        votes = ec.collect_votes(
            regime="UPTREND" if trending else "SIDEWAYS",
            rsi=float(rsi[i]),
            vol_ratio=float(vol_ratio[i]),
            trending=trending,
            rr_ratio=2.0,
            atr_pct=float(atr_pct[i]),
        )
        verdict = ec.deliberate(votes, regime="UPTREND" if trending else "SIDEWAYS")

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
        rr = round((target_price - cur_price) / max(cur_price - stop_price, 0.01), 1)

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

        timing = _timing_label(abs(dist_20ma))
        signal["_timing"] = timing
        action, action_reason = _action_from_signal(signal, should_trade)

        return {
            "ticker": ticker,
            "current_price": cur_price,
            "strategy": _setup_family(strategy),
            "score": signal["score"],
            "grade": conf["grade"],
            "direction": verdict.direction,
            "committee_confidence": round(verdict.agreement_ratio, 2),
            "timing": timing,
            "action": action,
            "action_reason": action_reason,
            "position_hint": _position_hint(signal, should_trade),
            "entry_price": cur_price,
            "target_price": target_price,
            "stop_price": stop_price,
            "risk_reward": rr,
            "why_now": _why_now(signal),
            "why_not": _why_not(signal),
            "invalidation": _invalidation(signal),
            "technicals": {
                "rsi": signal["rsi"],
                "vol_ratio": signal["vol_ratio"],
                "atr_pct": signal["atr_pct"],
                "distance_to_20ma_pct": dist_20ma,
                "above_50sma": bool(close[i] > sma50[i]),
                "above_200sma": bool(close[i] > sma200[i]),
                "regime": signal["regime"],
            },
            "prediction_interval": interval.to_dict() if interval else None,
            "regime_allows_trading": should_trade,
            "generated_at": datetime.now(timezone.utc).isoformat() + "Z",
        }

    except HTTPException:
        raise
    except Exception as exc:
        raise HTTPException(500, f"Signal card error: {exc}") from exc
