"""v7 product surface API endpoints."""

from __future__ import annotations

import asyncio
import logging
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, HTTPException, Query, Request

from src.api.deps import sanitize_for_json, validate_ticker
from src.api.live_analytics import compute_4layer_confidence as _compute_4layer_confidence
from src.api.live_state import fetch_regime_state

logger = logging.getLogger(__name__)
router = APIRouter(tags=["v7-surface"])


def _engine():
    from src.api.main import _get_engine
    return _get_engine()


async def _regime(request: Request):
    return await fetch_regime_state(request)



@router.get("/api/v7/regime-screener", tags=["v7-surface"])
async def regime_screener_data(request: Request):
    """
    v7 Regime Screener — one screen, one decision.

    Reads from singleton sources:
      - Regime: ``_get_regime()`` (canonical RegimeState)
      - Candidates: engine ``_cached_recommendations`` (TradeRecommendation)
      - Fallback: live-quote scoring for a representative universe
    """
    import asyncio

    from src.core.models import RegimeScoreboard

    # ── 1. Regime from singleton ──
    regime_state = await _regime(request)
    if hasattr(regime_state, "to_dict"):
        regime_dict = regime_state.to_dict()
    elif isinstance(regime_state, dict):
        regime_dict = regime_state
    else:
        regime_dict = {}

    sb = RegimeScoreboard.from_regime_state(regime_dict)

    # ── 2. Try real engine candidates first ──
    candidates = []
    engine = _engine()
    real_recs = []

    if engine:
        raw = list(getattr(engine, "_cached_recommendations", []))
        for rec in raw[:20]:
            try:
                if hasattr(rec, "__dict__"):
                    r = rec.__dict__ if not hasattr(rec, "dict") else rec.dict()
                elif isinstance(rec, dict):
                    r = rec
                else:
                    continue

                ticker = r.get("ticker", r.get("symbol", ""))
                if not ticker:
                    continue

                real_recs.append(
                    {
                        "ticker": ticker,
                        "engine": r.get("strategy_id", r.get("strategy", "unknown")),
                        "score": round(r.get("score", r.get("confidence", 0.5)), 2),
                        "direction": r.get("direction", "LONG"),
                        "entry": r.get("entry_price", r.get("entry", 0)),
                        "stop": r.get("stop_loss", r.get("stop", 0)),
                        "tp1": r.get("target_price", r.get("tp1", 0)),
                        "tp2": r.get("target_2", r.get("tp2", 0)),
                        "rr": round(r.get("risk_reward_ratio", r.get("rr", 0)), 1),
                        "confidence": int(
                            r.get("confidence", r.get("score", 0.5)) * 100
                        ),
                        "ev": round(r.get("expected_value", r.get("ev", 0)), 2),
                        "why": r.get("why_now", r.get("reason", "")),
                        "risks": r.get("event_risk", r.get("risks", [])),
                        "change_pct": r.get("change_pct", 0),
                        "rsi": r.get("rsi", 50),
                        "volume_ratio": r.get("volume_ratio", 1.0),
                        "sector": r.get("sector", ""),
                        "source": "engine_cache",
                    }
                )
            except Exception:
                continue

    if real_recs:
        candidates = sorted(
            real_recs,
            key=lambda x: x.get("score", 0),
            reverse=True,
        )[:20]
    else:
        # ── 3. Fallback: score a representative universe via live quotes ──
        universe = [
            "NVDA",
            "AAPL",
            "MSFT",
            "GOOGL",
            "AMZN",
            "META",
            "TSLA",
            "AMD",
            "AVGO",
            "CRM",
            "NFLX",
            "COST",
            "LLY",
            "JPM",
            "V",
            "UNH",
            "MU",
            "PLTR",
        ]

        regime_label = sb.regime_label

        async def _score_ticker(sym: str):
            try:
                q_resp = await live_quote(sym)
                q = q_resp.get("quote", {})
                price = q.get("price", 0)
                if price <= 0:
                    return None

                rsi = q.get("rsi", 50)
                vol_ratio = q.get("volume_ratio", 1.0)
                above_sma20 = q.get("above_sma20", False)
                above_sma50 = q.get("above_sma50", False)
                change_pct = q.get("change_pct", 0)

                score = 0.5
                if regime_label == "RISK_ON":
                    if above_sma20 and above_sma50:
                        score += 0.15
                    if (
                        SIGNAL_THRESHOLDS.rsi_momentum_low
                        < rsi
                        < SIGNAL_THRESHOLDS.rsi_overbought
                    ):
                        score += 0.1
                    if vol_ratio > SIGNAL_THRESHOLDS.volume_surge_threshold:
                        score += 0.1
                elif regime_label == "RISK_OFF":
                    if rsi < SIGNAL_THRESHOLDS.rsi_near_oversold:
                        score += 0.15
                    if change_pct < -2:
                        score += 0.1
                else:
                    if above_sma20:
                        score += 0.1
                    if 40 < rsi < 60:
                        score += 0.1

                score = min(0.99, max(0.1, score))

                # Use MDS for ATR if available
                mds = request.app.state.market_data
                atr_est = price * 0.025
                try:
                    hist = await mds.get_history(
                        sym,
                        period="1mo",
                        interval="1d",
                    )
                    if hist is not None and len(hist) >= 14:
                        h_col = "High" if "High" in hist.columns else "high"
                        l_col = "Low" if "Low" in hist.columns else "low"
                        c_col = "Close" if "Close" in hist.columns else "close"
                        import numpy as np

                        tr = np.maximum(
                            hist[h_col].values[-14:] - hist[l_col].values[-14:],
                            np.abs(
                                hist[h_col].values[-14:] - hist[c_col].values[-15:-1]
                            ),
                        )
                        atr_est = float(np.mean(tr))
                except Exception:
                    pass

                direction = "LONG" if score > 0.5 else "SHORT"
                stop = (
                    round(
                        price - atr_est * 2,
                        2,
                    )
                    if direction == "LONG"
                    else round(
                        price + atr_est * 2,
                        2,
                    )
                )
                tp1 = (
                    round(
                        price + atr_est * 3,
                        2,
                    )
                    if direction == "LONG"
                    else round(
                        price - atr_est * 3,
                        2,
                    )
                )
                risk = abs(price - stop)
                reward = abs(tp1 - price)
                rr = round(reward / risk, 1) if risk > 0 else 0

                reasons = []
                if above_sma20:
                    reasons.append("Above SMA20")
                if above_sma50:
                    reasons.append("Above SMA50")
                if vol_ratio > SIGNAL_THRESHOLDS.volume_surge_threshold:
                    reasons.append(f"Volume {vol_ratio:.1f}x avg")
                if rsi < SIGNAL_THRESHOLDS.rsi_near_oversold:
                    reasons.append(f"RSI oversold {rsi:.0f}")
                elif rsi > SIGNAL_THRESHOLDS.rsi_near_overbought:
                    reasons.append(f"RSI strong {rsi:.0f}")

                    # ── RSI sanity gates (Sprint 49) ──
                    extension_warning = ""
                    if rsi > 80:
                        score = max(score - 0.25, 0.15)
                        extension_warning = f"RSI {rsi:.0f} EXTENDED"
                        direction = "FLAT"
                    elif rsi > 70:
                        score = max(score - 0.10, 0.20)
                        extension_warning = f"RSI {rsi:.0f} overbought"

                    # ── Setup quality grade ──
                    if score >= 0.75 and rr >= 2.0:
                        setup_grade = "A"
                    elif score >= 0.60 and rr >= 1.5:
                        setup_grade = "B"
                    elif score >= 0.45:
                        setup_grade = "C"
                    else:
                        setup_grade = "D"

                    # ── Evidence FOR / AGAINST ──
                    evidence_for = list(reasons)
                    evidence_against = []
                    if rsi > 70:
                        evidence_against.append(f"RSI overbought ({rsi:.0f})")
                    if rsi > 80:
                        evidence_against.append("Extremely extended")
                    if vol_ratio < 0.7:
                        evidence_against.append(f"Low volume ({vol_ratio:.1f}x)")
                    if rr < 1.5:
                        evidence_against.append(f"R:R {rr:.1f} below min")
                    if not above_sma20:
                        evidence_against.append("Below SMA20")

                    invalidation = (
                        f"Close below ${stop:.2f}"
                        if direction == "LONG"
                        else f"Close above ${stop:.2f}"
                    )

                    return {
                        "ticker": sym,
                        "engine": "screener_fallback",
                        "score": round(score, 2),
                        "direction": direction,
                        "entry": round(price, 2),
                        "stop": stop,
                        "tp1": tp1,
                        "tp2": round(tp1 + atr_est * 2, 2),
                        "rr": rr,
                        "confidence": int(score * 100),
                        "ev": round(score * rr * 0.3, 2),
                        "why": ". ".join(reasons) if reasons else "Regime-aligned",
                        "risks": [extension_warning] if extension_warning else [],
                        "change_pct": round(change_pct, 2),
                        "rsi": round(rsi, 1),
                        "volume_ratio": round(vol_ratio, 2),
                        "sector": "",
                        "source": "live_quote_fallback",
                        "setup_grade": setup_grade,
                        "evidence_for": evidence_for,
                        "evidence_against": evidence_against,
                        "invalidation": invalidation,
                        "is_fallback": True,
                    }
            except Exception:
                return None

        sem = asyncio.Semaphore(8)

        async def _limited(sym):
            async with sem:
                return await _score_ticker(sym)

        results = await asyncio.gather(
            *[_limited(s) for s in universe],
        )
        raw_candidates = sorted(
            [r for r in results if r is not None and r["score"] > 0.4],
            key=lambda x: x["score"],
            reverse=True,
        )[:20]

        # ── Expert Committee enrichment (Sprint 49) ──
        from src.engines.expert_committee import ExpertCommittee as _ECfb

        _ec_fb = _ECfb()
        for c in raw_candidates:
            try:
                _rsi = c.get("rsi", 50)
                _vr = c.get("volume_ratio", 1.0)
                _trending = c.get("direction") == "LONG" and _rsi > 40
                _entry = c.get("entry", 0)
                _stop = c.get("stop", 0)
                _atr_p = abs(_entry - _stop) / _entry / 2 if _entry > 0 else 0.02
                _rlbl = regime_label or "SIDEWAYS"
                votes = _ec_fb.collect_votes(
                    regime=_rlbl,
                    rsi=_rsi,
                    vol_ratio=_vr,
                    trending=_trending,
                    rr_ratio=c.get("rr", 1.5),
                    atr_pct=_atr_p,
                    vix=sb.risk_on_score / 3.5,
                )
                vd = _ec_fb.deliberate(
                    votes,
                    regime=_rlbl,
                ).to_dict()
                c["committee"] = {
                    "direction": vd.get("direction"),
                    "conviction": round(
                        vd.get("composite_conviction", 0),
                        1,
                    ),
                    "agreement": round(
                        vd.get("agreement_ratio", 0),
                        2,
                    ),
                    "dominant_risk": vd.get("dominant_risk"),
                    "summary": vd.get("verdict_summary"),
                    "dissent_count": len(vd.get("dissenting_views", [])),
                }
            except Exception:
                c["committee"] = None

        candidates = sorted(
            raw_candidates,
            key=lambda x: x.get("score", 0),
            reverse=True,
        )

    data_source = "engine_cache" if real_recs else "live_quote_fallback"

    return {
        "regime": {
            "risk": sb.regime_label,
            "trend": sb.trend_state,
            "vol": sb.vol_state,
            "risk_on_score": sb.risk_on_score,
            "risk_budget": {
                "max_gross_pct": sb.max_gross_pct,
                "max_single_name_pct": sb.max_single_name_pct,
                "max_sector_pct": sb.max_sector_pct,
            },
            "strategies_on": sb.strategies_on,
            "strategies_conditional": sb.strategies_conditional,
            "strategies_off": sb.strategies_off,
            "no_trade_triggers": sb.no_trade_triggers,
            "top_drivers": sb.top_drivers,
        },
        "candidates": candidates,
        "universe_size": len(real_recs) if real_recs else 18,
        "candidate_count": len(candidates),
        "actionable_count": len(
            [
                c
                for c in candidates
                if c.get("direction") not in ("FLAT", "ABSTAIN")
                and c.get("setup_grade", "D") in ("A", "B")
            ]
        ),
        "selectivity": {
            "total_scanned": len(real_recs) if real_recs else 18,
            "passed_filters": len(candidates),
            "extended_count": len([c for c in candidates if c.get("rsi", 0) > 80]),
        },
        "warnings": [
            w
            for w in [
                ("Running on fallback scoring" if not real_recs else None),
            ]
            if w is not None
        ],
        "trust": {
            "mode": "PAPER" if engine else "SYNTHETIC",
            "source": data_source,
            "engine_available": engine is not None,
        },
        "generated_at": datetime.now(timezone.utc).isoformat() + "Z",
    }


@router.get("/api/v7/portfolio-brief", tags=["v7-surface"])
async def portfolio_brief_data(
    date_str: Optional[str] = Query(None, alias="date"),
    holdings: Optional[str] = Query(
        None,
        description=(
            "Comma-separated ticker list to use as real holdings. "
            "Overrides static watchlist. e.g. NVDA,AAPL,MSFT"
        ),
    ),
):
    """
    v7 Portfolio Brief — aggregated intelligence for holdings.

    Accepts optional ``holdings`` param for real portfolio input.
    Falls back to static watchlist when not provided.
    Integrates catalyst narrative via CatalystSummarizer.
    """
    target_date = date_str or date.today().isoformat()

    # Try to load from artifact file first
    artifact_path = Path("data") / f"brief-{target_date}.json"
    if artifact_path.exists() and not holdings:
        import json

        with open(artifact_path) as f:
            return json.load(f)

    # Determine watchlist source
    if holdings:
        watchlist = [t.strip().upper() for t in holdings.split(",") if t.strip()]
        watchlist_type = "user_holdings"
    else:
        watchlist = [
            "NVDA",
            "AAPL",
            "MSFT",
            "AMD",
            "MU",
            "CRDO",
            "SOFI",
            "INTC",
            "PLTR",
            "AVGO",
            "SMCI",
            "META",
            "GOOGL",
            "AMZN",
        ]
        watchlist_type = "static_default"

    holdings_with_signals = []
    holdings_no_signal = []
    sector_tickers = {}

    for sym in watchlist:
        try:
            q_resp = await live_quote(sym)
            q = q_resp.get("quote", {})
            price = q.get("price", 0)
            change_pct = q.get("change_pct", 0)
            rsi = q.get("rsi", 50)
            above_ma20 = q.get("above_sma20", False)
            above_ma50 = q.get("above_sma50", False)

            entry = {
                "ticker": sym,
                "change_pct": round(change_pct, 1),
                "indicators": {
                    "rsi": round(rsi, 0),
                    "above_ma20": above_ma20,
                    "above_ma50": above_ma50,
                },
            }

            # Determine if this has a "signal"
            has_signal = (
                abs(change_pct) > 2
                or rsi < SIGNAL_THRESHOLDS.rsi_oversold
                or rsi > SIGNAL_THRESHOLDS.rsi_overbought
            )
            if has_signal:
                if change_pct > 2:
                    entry["note"] = "Large move" if change_pct > 4 else "Strong rally"
                    entry["signal_type"] = "momentum_breakout"
                elif change_pct < -2:
                    entry["note"] = "Sharp decline — watch support levels"
                    entry["signal_type"] = "pullback_warning"
                elif rsi < SIGNAL_THRESHOLDS.rsi_oversold:
                    entry["note"] = (
                        f"RSI {rsi:.0f} oversold — check reversal conditions"
                    )
                    entry["signal_type"] = "oversold"
                elif rsi > SIGNAL_THRESHOLDS.rsi_overbought:
                    entry["note"] = f"RSI {rsi:.0f} overbought — pullback risk"
                    entry["signal_type"] = "overbought"
                else:
                    entry["note"] = "Signal triggered"
                    entry["signal_type"] = "signal"
                holdings_with_signals.append(entry)
            elif (
                abs(change_pct) > 0.5
                or rsi < SIGNAL_THRESHOLDS.rsi_near_oversold
                or rsi > SIGNAL_THRESHOLDS.rsi_near_overbought
            ):
                if rsi < SIGNAL_THRESHOLDS.rsi_near_oversold:
                    entry["note"] = f"RSI {rsi:.0f} low — worth watching"
                elif rsi > SIGNAL_THRESHOLDS.rsi_near_overbought:
                    entry["note"] = f"RSI {rsi:.0f} elevated — momentum continues"
                else:
                    entry["note"] = f"Move {change_pct:+.1f}%"
                entry["watch_reason"] = "near_extreme"
                holdings_no_signal.append(entry)

            # Sector clustering — broader map
            _SECTOR_MAP = {
                "Semiconductor": [
                    "NVDA",
                    "AMD",
                    "MU",
                    "CRDO",
                    "INTC",
                    "AVGO",
                    "SMCI",
                    "MRVL",
                    "ARM",
                    "QCOM",
                    "TXN",
                    "LRCX",
                    "ASML",
                    "KLAC",
                ],
                "Big Tech": [
                    "AAPL",
                    "MSFT",
                    "GOOGL",
                    "GOOG",
                    "META",
                    "AMZN",
                ],
                "Software / AI": [
                    "PLTR",
                    "CRM",
                    "SNOW",
                    "NET",
                    "DDOG",
                    "PANW",
                    "ZS",
                ],
                "Fintech": ["SOFI", "SQ", "PYPL", "COIN", "HOOD"],
            }
            for sector_name, sector_syms in _SECTOR_MAP.items():
                if sym in sector_syms:
                    sector_tickers.setdefault(
                        sector_name,
                        [],
                    ).append({"ticker": sym, "change": change_pct})
        except Exception:
            continue

    # ── What-changed-since-yesterday (diff against prior artifact) ──
    what_changed = []
    try:
        from datetime import timedelta as _td

        yesterday_date = (date.fromisoformat(target_date) - _td(days=1)).isoformat()
        yesterday_path = Path("data") / f"brief-{yesterday_date}.json"
        if yesterday_path.exists():
            import json as _json

            with open(yesterday_path) as _f:
                prev = _json.load(_f)
            prev_signals = {h["ticker"] for h in prev.get("holdings_with_signals", [])}
            curr_signals = {h["ticker"] for h in holdings_with_signals}
            new_signals = curr_signals - prev_signals
            cleared = prev_signals - curr_signals
            if new_signals:
                what_changed.append(f"New signals: {', '.join(sorted(new_signals))}")
            if cleared:
                what_changed.append(f"Cleared: {', '.join(sorted(cleared))}")
            if not new_signals and not cleared:
                what_changed.append("No signal changes vs yesterday")
    except Exception:
        pass

    # ── Classify: actionable vs watch ──
    for h in holdings_with_signals:
        # Actionable = strong move + directional RSI alignment
        rsi_v = h["indicators"]["rsi"]
        chg = h["change_pct"]
        if abs(chg) > 3 or rsi_v < 25 or rsi_v > 75:
            h["action"] = "ACTIONABLE"
        else:
            h["action"] = "REVIEW"
    for h in holdings_no_signal:
        h["action"] = "WATCH"

    # Build sector clusters
    sector_clustering = {}
    for sector, items in sector_tickers.items():
        if len(items) >= 2:
            avg_chg = sum(i["change"] for i in items) / len(items)
            if abs(avg_chg) > 1.5:
                sector_clustering[sector] = {
                    "tickers": [i["ticker"] for i in items],
                    "avg_change": round(avg_chg, 1),
                    "narrative": (
                        f"{sector} sector {'rallying' if avg_chg > 0 else 'selling off'} "
                        f"avg {avg_chg:+.1f}%"
                    ),
                }

    # Count no-change
    signaled_tickers = {h["ticker"] for h in holdings_with_signals + holdings_no_signal}
    no_change_count = sum(1 for t in watchlist if t not in signaled_tickers)

    # Catalysts — use CatalystSummarizer for real news narrative
    catalyst_data = None
    try:
        from src.services.catalyst_summarizer import CatalystSummarizer

        mds = request.app.state.market_data
        cs = CatalystSummarizer(mds)
        catalyst_data = await cs.summarize(watchlist, max_items_per_ticker=3)
    except Exception as exc:
        logger.warning("catalyst summarizer error: %s", exc)

    # Fallback heuristic catalysts if summarizer failed
    catalysts = []
    if catalyst_data and catalyst_data.get("catalysts"):
        catalysts = catalyst_data["catalysts"][:10]
    else:
        if any(abs(h["change_pct"]) > 3 for h in holdings_with_signals):
            catalysts.append(
                {
                    "headline": "High volatility day — check for catalysts",
                    "sentiment": "neutral",
                }
            )
        if sector_clustering:
            for s in sector_clustering:
                catalysts.append(
                    {"headline": f"{s} sector correlated move", "sentiment": "neutral"}
                )

    # Follow-up prompts — prefer catalyst summarizer output
    prompts = []
    if catalyst_data and catalyst_data.get("follow_up_questions"):
        prompts = catalyst_data["follow_up_questions"]
    else:
        for h in holdings_no_signal[:2]:
            prompts.append(f"How does {h['ticker']} look technically?")
        if sector_clustering:
            for s in sector_clustering:
                prompts.append(f"Is {s} rally short-term or trending?")
        if holdings_with_signals:
            prompts.append(
                f"Should I adjust {holdings_with_signals[0]['ticker']} "
                f"position after this move?"
            )

    # ── Build analyst-quality narrative ──
    actionable_count = sum(
        1 for h in holdings_with_signals if h.get("action") == "ACTIONABLE"
    )
    review_count = sum(1 for h in holdings_with_signals if h.get("action") == "REVIEW")

    # Headline: analyst-note style
    if actionable_count > 0:
        top = [
            h["ticker"]
            for h in holdings_with_signals
            if h.get("action") == "ACTIONABLE"
        ]
        headline = (
            f"{actionable_count} actionable signal"
            f"{'s' if actionable_count > 1 else ''}: "
            f"{', '.join(top[:3])}"
        )
    elif holdings_with_signals:
        headline = (
            f"{len(holdings_with_signals)} signals for review"
            " — none requiring immediate action"
        )
    else:
        headline = "All holdings stable — no major signals"

    # Portfolio story: analyst-note paragraph
    story_parts = []
    if sector_clustering:
        for sn, sc in sector_clustering.items():
            story_parts.append(sc["narrative"])
    if actionable_count:
        story_parts.append(
            f"{actionable_count} position"
            f"{'s' if actionable_count > 1 else ''}"
            " warrant attention"
        )
    if review_count:
        story_parts.append(f"{review_count} under review")
    if what_changed:
        story_parts.extend(what_changed)
    portfolio_story = (
        ". ".join(story_parts) + "." if story_parts else "All positions stable."
    )

    brief = {
        "date": target_date,
        "headline": headline,
        "portfolio_story": portfolio_story,
        "what_changed": what_changed,
        "actionable": [
            h for h in holdings_with_signals if h.get("action") == "ACTIONABLE"
        ],
        "review": [h for h in holdings_with_signals if h.get("action") == "REVIEW"],
        "watch": holdings_no_signal,
        # backward compat
        "holdings_with_signals": holdings_with_signals,
        "holdings_no_signal": holdings_no_signal,
        "sector_clustering": sector_clustering,
        "top_catalysts": (
            catalysts
            if catalysts
            else [{"headline": "No major catalysts today", "sentiment": "neutral"}]
        ),
        "sector_summary": (
            catalyst_data.get("sector_summary", "") if catalyst_data else ""
        ),
        "no_change_summary": (
            f"Remaining {no_change_count} watchlist names unchanged"
            if no_change_count > 0
            else None
        ),
        "follow_up_prompts": prompts[:5],
        "trust": {
            "mode": "LIVE",
            "source": (
                "catalyst_summarizer" if catalyst_data else "watchlist_heuristic"
            ),
            "watchlist_type": watchlist_type,
            "sample_size": len(watchlist),
            "data_note": (
                "Uses real holdings input. "
                if watchlist_type == "user_holdings"
                else "Uses static watchlist, not real holdings. "
            )
            + "Indicators from MarketDataService.",
        },
        "as_of": datetime.now(timezone.utc).isoformat() + "Z",
    }

    # Save artifact
    try:
        artifact_dir = Path("data")
        artifact_dir.mkdir(exist_ok=True)
        import json

        with open(artifact_path, "w") as f:
            json.dump(brief, f, indent=2, ensure_ascii=False)
    except Exception:
        pass

    return brief


@router.get("/api/v7/why-moved/{ticker}", tags=["v7-surface"])
async def why_moved(request: Request, ticker: str):
    """v7 Why Moved — explain why a ticker moved today."""
    ticker = ticker.upper()
    try:
        q_resp = await live_quote(ticker)
        q = q_resp.get("quote", {})
    except Exception:
        raise HTTPException(404, f"No data for {ticker}")

    change_pct = q.get("change_pct", 0)
    rsi = q.get("rsi", 50)
    vol_ratio = q.get("volume_ratio", 1.0)

    reasons = []
    if abs(change_pct) > 2:
        reasons.append(
            {
                "source": "technical",
                "text": f"價格變動 {change_pct:+.1f}%，{'突破' if change_pct > 0 else '跌破'}重要技術位",
            }
        )
    if vol_ratio > SIGNAL_THRESHOLDS.volume_strong_surge:
        reasons.append(
            {
                "source": "volume",
                "text": f"成交量 {vol_ratio:.1f}x 平均 — 有異常資金流入",
            }
        )
    if rsi > SIGNAL_THRESHOLDS.rsi_overbought:
        reasons.append(
            {
                "source": "technical",
                "text": f"RSI {rsi:.0f} 超買區域",
            }
        )
    elif rsi < SIGNAL_THRESHOLDS.rsi_oversold:
        reasons.append(
            {
                "source": "technical",
                "text": f"RSI {rsi:.0f} 超賣區域",
            }
        )
    if q.get("above_sma20") and q.get("above_sma50"):
        reasons.append(
            {
                "source": "trend",
                "text": "價格在 SMA20 和 SMA50 之上 — 上升趨勢確認",
            }
        )

    if not reasons:
        reasons.append(
            {
                "source": "neutral",
                "text": "今日無重大技術面變化",
            }
        )

    return {
        "ticker": ticker,
        "change_pct": round(change_pct, 2),
        "reasons": reasons,
        "confidence": 0.7,
    }


@router.get("/api/v7/compare-overlay", tags=["v7-surface"])
async def compare_overlay_data(
    tickers: str = Query(..., description="Comma-separated tickers"),
    period: str = Query("6M", description="1M, 3M, 6M, 1Y, 2Y"),
    mode: str = Query(
        "normalized",
        description=(
            "normalized / relative_strength / " "rolling_correlation / rolling_beta"
        ),
    ),
    join: str = Query(
        "strict",
        description="strict (inner join) / smooth (outer + ffill)",
    ),
    benchmark: str = Query("SPY", description="Benchmark ticker"),
    rolling_window: int = Query(
        60,
        description="Rolling window for corr/beta",
    ),
):
    """
    v7 Compare Overlay — date-aligned multi-instrument comparison.

    Modes:
      - **normalized** — rebased to 100
      - **relative_strength** — ticker / benchmark ratio
      - **rolling_correlation** — pairwise rolling Pearson
      - **rolling_beta** — rolling OLS beta vs benchmark

    Join strategies:
      - **strict** — inner join (only shared trading dates)
      - **smooth** — outer join + forward-fill (mixed calendars)
    """
    import asyncio

    from src.services.compare_overlay_service import CompareOverlayService

    ticker_list = [t.strip().upper() for t in tickers.split(",") if t.strip()]
    if not ticker_list:
        raise HTTPException(400, "Provide at least one ticker")

    # Ensure benchmark is included for relative_strength / rolling_beta
    if benchmark.upper() not in ticker_list and mode in (
        "relative_strength",
        "rolling_beta",
    ):
        ticker_list.append(benchmark.upper())

    period_map = {
        "1M": "1mo",
        "3M": "3mo",
        "6M": "6mo",
        "1Y": "1y",
        "2Y": "2y",
    }
    yf_period = period_map.get(period.upper(), "6mo")
    mds = request.app.state.market_data

    # Fetch histories concurrently
    async def _fetch(sym: str):
        try:
            return sym, await mds.get_history(
                sym,
                period=yf_period,
                interval="1d",
            )
        except Exception:
            return sym, None

    results = await asyncio.gather(
        *[_fetch(s) for s in ticker_list],
    )
    history_map = {sym: df for sym, df in results if df is not None and not df.empty}

    if not history_map:
        raise HTTPException(404, "No data for any ticker")

    # Run comparison engine
    svc = CompareOverlayService()
    try:
        result = svc.compare(
            history_map,
            mode=mode,
            join=join,
            benchmark=benchmark.upper(),
            rolling_window=rolling_window,
        )
    except ValueError as exc:
        raise HTTPException(400, str(exc))

    response = {
        "tickers": result.tickers,
        "dates": result.dates,
        "series": result.series,
        "stats": result.stats,
        "correlation_matrix": result.correlation_matrix,
        "alignment": result.alignment,
        "period": period,
        "trust": {
            "mode": "LIVE",
            "source": "market_data_service",
            "join_strategy": join,
            "comparison_mode": mode,
        },
        "as_of": datetime.now(timezone.utc).isoformat() + "Z",
    }

    # ── Write immutable research artifact ──
    try:
        from src.services.artifacts.research_artifact_writer import (
            ResearchArtifactWriter,
        )

        writer = ResearchArtifactWriter()
        response["artifact"] = writer.write(
            "compare-overlay",
            response,
        )
    except Exception as exc:
        logger.warning("compare-overlay artifact write failed: %s", exc)
        response["artifact"] = None

    return response


@router.get("/api/v7/performance-lab", tags=["v7-surface"])
async def performance_lab_data(
    source: str = Query(
        "live",
        description="live / paper / backtest / synthetic",
    ),
    strategy: str = Query("all"),
    period: str = Query("1y"),
):
    """
    v7 Performance Lab — auditable KPI dashboard.

    Data priority:
      1. TradeOutcomeRepository (persistent closed trades)
      2. Engine singleton KPI snapshot
      3. Explicit SYNTHETIC demo mode — only when requested
         or when no real data exists.

    Every response carries ``mode``, ``source``, ``sample_size``,
    ``assumptions``, and ``as_of`` for full trust/audit.
    """

    import numpy as np

    mode = source.upper()  # LIVE / PAPER / BACKTEST / SYNTHETIC
    sample_size = 0
    FEES_BPS = 5  # round-trip commission estimate
    SLIPPAGE_BPS = 3  # market-impact estimate
    TOTAL_COST_BPS = FEES_BPS + SLIPPAGE_BPS  # 8 bps per trade
    assumptions = {
        "gross_or_net": "net",
        "fees_bps": FEES_BPS,
        "slippage_bps": SLIPPAGE_BPS,
        "total_cost_bps": TOTAL_COST_BPS,
        "benchmark": "SPY (S&P 500 ETF)",
    }

    # ── 1. Try persistent closed trades from TradeOutcomeRepository ──
    real_trades = []
    try:
        engine = _engine()
        if engine and hasattr(engine, "trade_repo"):
            repo = engine.trade_repo
            if hasattr(repo, "get_recent_outcomes"):

                real_trades = (
                    await repo.get_recent_outcomes(
                        limit=500,
                    )
                    or []
                )
    except Exception:
        pass

    if not real_trades:
        try:
            from src.core.trade_repo import TradeOutcomeRepository

            repo = TradeOutcomeRepository()
            if hasattr(repo, "get_recent_outcomes"):
                real_trades = (
                    await repo.get_recent_outcomes(
                        limit=500,
                    )
                    or []
                )
        except Exception:
            pass

    # ── 2. Try PerformanceTracker as secondary source ──
    if not real_trades:
        try:
            from src.performance.performance_tracker import PerformanceTracker

            tracker = PerformanceTracker()
            if hasattr(tracker, "get_recent_outcomes"):
                real_trades = tracker.get_recent_outcomes() or []
            elif hasattr(tracker, "get_closed_trades"):
                real_trades = tracker.get_closed_trades() or []
        except Exception:
            pass

    # ── 3. Try engine KPI snapshot ──
    engine_kpi_snap = None
    engine = _engine()
    if engine and hasattr(engine, "kpi"):
        try:
            if hasattr(engine.kpi, "snapshot"):
                engine_kpi_snap = engine.kpi.snapshot()
        except Exception:
            pass

    # ── Decide mode based on what data we actually have ──
    has_real_data = len(real_trades) >= 5
    has_kpi = (
        engine_kpi_snap
        and hasattr(engine_kpi_snap, "total_trades")
        and engine_kpi_snap.total_trades > 0
    )

    if mode != "SYNTHETIC" and not has_real_data and not has_kpi:
        # Caller asked for live/paper/backtest but no real data
        mode = "SYNTHETIC"

    # ── Build return series ──
    if has_real_data and mode != "SYNTHETIC":
        returns = [t.pnl_pct / 100 for t in real_trades if hasattr(t, "pnl_pct")]
        if not returns:
            returns = [0.0] * len(real_trades)
        monthly_rets = np.array(
            returns[-24:] if len(returns) >= 24 else returns,
        )
        sample_size = len(real_trades)
    else:
        # SYNTHETIC — deterministic seed, clearly labelled
        mode = "SYNTHETIC"
        np.random.seed(42)
        n_months = 24
        monthly_rets = np.random.normal(0.03, 0.05, n_months)
        monthly_rets = np.clip(monthly_rets, -0.15, 0.20)
        sample_size = 0

    n_months = len(monthly_rets)

    # Build equity curve
    equity = [100.0]
    for r in monthly_rets:
        equity.append(round(equity[-1] * (1 + r), 2))

    # SPY benchmark — fetch real if possible, else synthetic
    spy_monthly = None
    benchmark_source = "SYNTHETIC"
    if mode != "SYNTHETIC":
        try:
            mds = request.app.state.market_data
            spy_df = await mds.get_history(
                "SPY",
                period="2y",
                interval="1mo",
            )
            if spy_df is not None and len(spy_df) >= n_months:
                c = "Close" if "Close" in spy_df.columns else "close"
                spy_c = spy_df[c].values[-n_months - 1 :]
                spy_monthly = np.diff(spy_c) / spy_c[:-1]
                benchmark_source = "LIVE"
        except Exception:
            pass

    if spy_monthly is None or len(spy_monthly) < n_months:
        np.random.seed(99)
        spy_monthly = np.random.normal(0.008, 0.035, n_months)

    benchmark = [100.0]
    for r in spy_monthly[:n_months]:
        benchmark.append(round(benchmark[-1] * (1 + r), 2))

    # Dates
    end_date = date.today()
    dates = []
    for i in range(n_months + 1):
        d = end_date - timedelta(days=(n_months - i) * 30)
        dates.append(d.isoformat())

    # Monthly returns heatmap
    monthly_returns = {}
    month_names = [
        "Jan",
        "Feb",
        "Mar",
        "Apr",
        "May",
        "Jun",
        "Jul",
        "Aug",
        "Sep",
        "Oct",
        "Nov",
        "Dec",
    ]
    for i in range(n_months):
        d = end_date - timedelta(
            days=(n_months - 1 - i) * 30,
        )
        year = str(d.year)
        month = month_names[d.month - 1]
        if year not in monthly_returns:
            monthly_returns[year] = {}
        monthly_returns[year][month] = round(
            float(monthly_rets[i]) * 100,
            1,
        )

    # Annual returns — real benchmark where available
    annual_returns = []
    spy_ann = float(np.mean(spy_monthly) * 12 * 100)
    for year_str, months_data in monthly_returns.items():
        yr_ret = 1.0
        for v in months_data.values():
            yr_ret *= 1 + v / 100
        yr_ret = (yr_ret - 1) * 100
        annual_returns.append(
            {
                "year": int(year_str),
                "return_pct": round(yr_ret, 1),
                "benchmark": round(spy_ann, 1),
                "alpha": round(yr_ret - spy_ann, 1),
            }
        )

    # Drawdowns
    eq_arr = np.array(equity)
    peak = np.maximum.accumulate(eq_arr)
    dd = (eq_arr - peak) / peak * 100
    drawdowns = []
    in_dd = False
    dd_start = None
    dd_trough = None
    dd_depth = 0.0
    for i, d_val in enumerate(dd):
        if d_val < -1 and not in_dd:
            in_dd = True
            dd_start = dates[i] if i < len(dates) else ""
            dd_depth = d_val
            dd_trough = dd_start
        elif in_dd and d_val < dd_depth:
            dd_depth = d_val
            dd_trough = dates[i] if i < len(dates) else ""
        elif in_dd and d_val >= -0.5:
            drawdowns.append(
                {
                    "start": dd_start,
                    "trough": dd_trough,
                    "recovery": (dates[i] if i < len(dates) else ""),
                    "depth": round(dd_depth, 1),
                }
            )
            in_dd = False
    if in_dd:
        drawdowns.append(
            {
                "start": dd_start,
                "trough": dd_trough,
                "recovery": None,
                "depth": round(dd_depth, 1),
            }
        )

    # Summary metrics — all computed, never random
    total_ret = (equity[-1] / equity[0] - 1) * 100
    ann_ret = total_ret / max(n_months / 12, 0.01)
    # Gross return: add back the cost assumption
    gross_ann_ret = ann_ret + (TOTAL_COST_BPS / 100) * 12
    vol = float(np.std(monthly_rets) * np.sqrt(12) * 100)
    sharpe = (
        float(np.mean(monthly_rets) / np.std(monthly_rets) * np.sqrt(12))
        if np.std(monthly_rets) > 0
        else 0.0
    )
    sortino_d = monthly_rets[monthly_rets < 0]
    sortino = (
        float(np.mean(monthly_rets) / np.std(sortino_d) * np.sqrt(12))
        if len(sortino_d) > 0 and np.std(sortino_d) > 0
        else sharpe * 1.3
    )
    max_dd = float(np.min(dd))
    calmar = ann_ret / abs(max_dd) if max_dd != 0 else 0

    # Beta from real covariance (not random)
    beta = 0.0
    if len(spy_monthly) >= n_months and n_months > 2:
        cov = np.cov(monthly_rets, spy_monthly[:n_months])
        if cov[1, 1] > 0:
            beta = float(cov[0, 1] / cov[1, 1])

    alpha = ann_ret - spy_ann
    win_rate = float(np.mean(monthly_rets > 0))

    # Win/loss distribution from real trades if available
    if has_real_data and mode != "SYNTHETIC":
        trade_rets = np.array([t.pnl_pct for t in real_trades if hasattr(t, "pnl_pct")])
    else:
        np.random.seed(42)
        trade_rets = np.random.normal(2, 6, 100)
    bins = list(range(-10, 16, 2))
    counts = [int(np.sum((trade_rets >= b) & (trade_rets < b + 2))) for b in bins]

    # Profit factor from real trades
    wins = monthly_rets[monthly_rets > 0]
    losses = monthly_rets[monthly_rets < 0]
    profit_factor = (
        float(np.sum(wins) / abs(np.sum(losses)))
        if len(losses) > 0 and np.sum(losses) != 0
        else 2.0
    )

    # VaR / CVaR
    p5 = float(np.percentile(monthly_rets, 5))
    tail = monthly_rets[monthly_rets <= p5]
    cvar = float(np.mean(tail)) if len(tail) > 0 else p5

    response = {
        "summary": {
            "annual_return_net": round(ann_ret, 1),
            "annual_return_gross": round(gross_ann_ret, 1),
            "annual_return": round(ann_ret, 1),  # backward compat
            "alpha": round(alpha, 1),
            "beta": round(beta, 2),
            "sharpe": round(sharpe, 2),
            "sortino": round(sortino, 2),
            "calmar": round(calmar, 2),
            "max_drawdown": round(max_dd, 1),
            "win_rate": round(win_rate, 2),
            "profit_factor": round(profit_factor, 2),
            "var_95": round(p5 * 100, 1),
            "cvar_95": round(cvar * 100, 1),
        },
        "trust": {
            "mode": mode,
            "source": ("trade_repository" if has_real_data else "synthetic_demo"),
            "benchmark": "SPY",
            "benchmark_source": benchmark_source,
            "sample_size": sample_size,
            "assumptions": assumptions,
            "data_warning": (
                "SYNTHETIC DATA \u2014 simulated returns for demo. "
                "Not based on real trade history."
                if mode == "SYNTHETIC"
                else None
            ),
        },
        "equity_curve": {
            "dates": dates,
            "values": equity,
            "benchmark": benchmark,
        },
        "monthly_returns": monthly_returns,
        "annual_returns": annual_returns,
        "drawdowns": drawdowns[:5],
        "win_loss_distribution": {
            "bins": bins,
            "counts": counts,
        },
        "as_of": datetime.now(timezone.utc).isoformat() + "Z",
    }

    # ── Write immutable artifact bundle (json/csv/png/md) ──
    try:
        from src.services.artifacts.performance_artifact_writer import (
            PerformanceArtifactWriter,
        )

        writer = PerformanceArtifactWriter()
        artifact_meta = writer.write(response)
        response["artifact"] = artifact_meta
    except Exception as exc:
        logger.warning("performance artifact write failed: %s", exc)
        response["artifact"] = None

    return response


# ──────────────────────────────────────────────────────────────────
# Strategy Portfolio Lab — multi-strategy sleeve optimizer
# ──────────────────────────────────────────────────────────────────


@router.get("/api/v7/strategy-portfolio-lab", tags=["v7-surface"])
async def strategy_portfolio_lab_data(
    strategies: str = Query(
        "swing,momentum,mean_reversion",
        description="Comma-separated strategy names",
    ),
    period: str = Query(
        "1y",
        description="Lookback: 6m / 1y / 2y",
    ),
):
    """
    v7 Strategy Portfolio Lab — "How to mix strategy sleeves optimally?"

    Accepts strategy return streams (real or synthetic demo),
    runs max-Sharpe / min-drawdown / risk-parity optimization,
    returns weights, correlation matrix, combined equity curve,
    and attribution breakdown.
    """
    import numpy as np

    from src.services.strategy_portfolio_lab import StrategyPortfolioLab

    strategy_names = [s.strip() for s in strategies.split(",") if s.strip()]
    if len(strategy_names) < 2:
        raise HTTPException(
            400,
            "Need ≥ 2 strategy names (comma-separated)",
        )

    # ── Try to source real strategy returns from engine ──
    return_streams: Dict[str, list] = {}
    engine = _engine()
    regime_label = None

    if engine:
        try:
            regime = await _regime(request)
            if regime:
                regime_label = regime.get(
                    "regime_label",
                    regime.get("risk", "NEUTRAL"),
                )
        except Exception:
            pass

        # Check if engine has strategy-level return tracking
        for sname in strategy_names:
            try:
                if hasattr(engine, "strategy_returns"):
                    sr = engine.strategy_returns.get(sname)
                    if sr and len(sr) >= 10:
                        return_streams[sname] = list(sr)
            except Exception:
                pass

    # ── Fallback: synthetic demo returns for unmatched strategies ──
    mode = "LIVE" if return_streams else "SYNTHETIC"
    np.random.seed(42)
    n_periods = {"6m": 126, "1y": 252, "2y": 504}.get(period, 252)

    # Strategy archetypes for synthetic demo
    archetypes = {
        "swing": (0.0008, 0.015),  # moderate return, moderate vol
        "momentum": (0.0012, 0.022),  # higher return, higher vol
        "mean_reversion": (0.0005, 0.010),  # lower return, low vol
        "trend_following": (0.0010, 0.020),
        "breakout": (0.0009, 0.018),
        "value": (0.0006, 0.012),
        "pairs": (0.0004, 0.008),
        "volatility": (0.0007, 0.025),
    }

    for sname in strategy_names:
        if sname not in return_streams:
            mu, sigma = archetypes.get(sname, (0.0006, 0.015))
            return_streams[sname] = list(
                np.random.normal(mu, sigma, n_periods),
            )
            if mode != "SYNTHETIC":
                mode = "MIXED"  # some real, some synthetic

    # ── Run optimizer ──
    lab = StrategyPortfolioLab()
    try:
        result = lab.optimize(
            return_streams,
            regime=regime_label,
        )
    except ValueError as exc:
        raise HTTPException(400, str(exc))

    # Build response
    optimizations = []
    for opt in result.optimizations:
        optimizations.append(
            {
                "objective": opt.objective,
                "weights": opt.weights,
                "expected_return_pct": opt.expected_return,
                "expected_vol_pct": opt.expected_vol,
                "sharpe": opt.sharpe,
                "max_drawdown_pct": opt.max_drawdown,
                "equity_curve": opt.equity_curve,
            }
        )

    response = {
        "strategies": result.strategies,
        "correlation_matrix": result.correlation_matrix,
        "optimizations": optimizations,
        "recommended": optimizations[0] if optimizations else None,
        "combined_equity": result.combined_equity,
        "combined_dates": result.combined_dates,
        "attribution": result.attribution,
        "regime_weights": result.regime_weights,
        "trust": {
            "mode": mode,
            "source": (
                "engine_strategy_returns" if mode == "LIVE" else "synthetic_archetypes"
            ),
            "sample_size": n_periods,
            "assumptions": {
                "risk_free_rate": lab.rf,
                "annualization": ("daily" if n_periods > 60 else "monthly"),
            },
            "data_warning": (
                "SYNTHETIC DATA — simulated strategy returns. "
                "Not based on real trade history."
                if mode == "SYNTHETIC"
                else None
            ),
        },
        "as_of": datetime.now(timezone.utc).isoformat() + "Z",
    }

    # ── Write immutable research artifact ──
    try:
        from src.services.artifacts.research_artifact_writer import (
            ResearchArtifactWriter,
        )

        writer = ResearchArtifactWriter()
        response["artifact"] = writer.write(
            "strategy-portfolio-lab",
            response,
        )
    except Exception as exc:
        logger.warning("strategy-lab artifact write failed: %s", exc)
        response["artifact"] = None

    return response


@router.get("/api/v7/options-screen", tags=["v7-surface"])
async def options_screen_data(
    ticker: str = Query(..., description="Stock ticker"),
    strategy: str = Query(
        "auto", description="long_call / long_put / debit_spread / credit_spread / auto"
    ),
):
    """
    v7 Options Lab — research-grade options surface.

    Uses OptionsMapper + ExpressionEngine pipeline:
      1. Fetch chain from OptionsDataProvider
      2. Run ExpressionEngine to decide instrument type
      3. Rank contracts by liquidity score + EV
      4. Generate IV term structure
      5. Surface warnings (earnings, IV-crush, ex-div)
    """
    from src.engines.expression_engine import ExpressionEngine
    from src.ingestors.options_data import get_options_provider
    from src.services.options.options_mapper import OptionsMapper

    ticker = ticker.upper()

    # Get spot price from live_quote endpoint
    try:
        q_resp = await live_quote(ticker)
        q = q_resp.get("quote", {})
        spot = q.get("price", 0)
        if spot <= 0:
            raise HTTPException(404, f"No price data for {ticker}")
    except HTTPException:
        raise
    except Exception:
        raise HTTPException(404, f"Cannot fetch {ticker}")

    rsi = q.get("rsi", 50)

    # Resolve regime from singleton
    regime_label = "NEUTRAL"
    try:
        regime = await _regime(request)
        if regime:
            regime_label = regime.get(
                "regime_label",
                regime.get("risk", "NEUTRAL"),
            )
    except Exception:
        pass

    # Build screen via OptionsMapper + ExpressionEngine pipeline
    provider = get_options_provider()
    ee = ExpressionEngine()
    mapper = OptionsMapper(
        options_provider=provider,
        expression_engine=ee,
    )

    result = await mapper.build_screen(
        ticker=ticker,
        spot=spot,
        rsi=rsi,
        strategy=strategy,
        regime=regime_label,
    )

    response = {
        "ticker": result.ticker,
        "spot_price": result.spot_price,
        "expression_decision": result.expression_decision,
        "expression_rationale": result.expression_rationale,
        "rejection_reasons": result.rejection_reasons,
        "market_context": result.market_context,
        "contracts": result.contracts[:10],
        "iv_term_structure": result.iv_term_structure,
        "warnings": result.warnings,
        "data_source": result.data_source,
        "data_warning": (
            "SYNTHETIC OPTIONS DATA — simulated IV/OI/contracts. "
            "Not from live options chain feed."
            if result.data_source == "SYNTHETIC"
            else None
        ),
        "trust": result.trust,
        "generated_at": datetime.now(timezone.utc).isoformat() + "Z",
    }

    # ── Write immutable research artifact ──
    try:
        from src.services.artifacts.research_artifact_writer import (
            ResearchArtifactWriter,
        )

        writer = ResearchArtifactWriter()
        response["artifact"] = writer.write(
            "options-screen",
            response,
        )
    except Exception as exc:
        logger.warning("options-screen artifact write failed: %s", exc)
        response["artifact"] = None

    return response


# ═══════════════════════════════════════════════════════════════════
# v7 RESEARCH ARTIFACT REPLAY — immutable artifact retrieval
# ═══════════════════════════════════════════════════════════════════


@router.get("/api/v7/research/artifacts/{artifact_id}", tags=["v7-surface"])
async def research_artifact_replay(request: Request, artifact_id: str):
    """
    Replay a research artifact by its immutable ID.

    Returns the full JSON snapshot that was recorded when the
    research surface was originally executed.
    """
    from src.services.artifacts.research_artifact_writer import ResearchArtifactWriter

    writer = ResearchArtifactWriter()
    data = writer.load(artifact_id)
    if data is None:
        raise HTTPException(
            404,
            f"Artifact '{artifact_id}' not found",
        )
    return data


@router.get("/api/v7/research/artifacts", tags=["v7-surface"])
async def research_artifact_list(
    surface: Optional[str] = Query(
        None,
        description=(
            "Filter by surface: compare-overlay, "
            "options-screen, strategy-portfolio-lab"
        ),
    ),
    limit: int = Query(50, description="Max results"),
):
    """List recent research artifacts with optional surface filter."""
    from src.services.artifacts.research_artifact_writer import ResearchArtifactWriter

    writer = ResearchArtifactWriter()
    return {
        "artifacts": writer.list_artifacts(
            surface=surface,
            limit=limit,
        ),
        "as_of": datetime.now(timezone.utc).isoformat() + "Z",
    }


# ═══════════════════════════════════════════════════════════════════
# MARKET INTEL routes extracted → src/api/routers/market_intel.py
# (Sprint 81 RISK-3 — registered below with other routers)
# ═══════════════════════════════════════════════════════════════════


# ═══════════════════════════════════════════════════════════════════
# v7 MACRO INTELLIGENCE — rates, political risk, insider, war, corr
# ═══════════════════════════════════════════════════════════════════

_RATE_TICKERS = [
    ("^IRX", "3-Month T-Bill", "3M"),
    ("^FVX", "5-Year Yield", "5Y"),
    ("^TNX", "10-Year Yield", "10Y"),
    ("^TYX", "30-Year Yield", "30Y"),
]
_RATE_ETF = [
    ("TLT", "20Y+ Bond ETF"),
    ("SHY", "1-3Y Bond ETF"),
    ("IEF", "7-10Y Bond ETF"),
    ("HYG", "High Yield Corp"),
    ("LQD", "Investment Grade"),
]
_POLITICAL_TICKERS = [
    ("DJT", "Trump Media & Technology"),
    ("GEO", "GEO Group"),
    ("CXW", "CoreCivic"),
    ("LMT", "Lockheed Martin"),
    ("RTX", "RTX (Raytheon)"),
    ("NOC", "Northrop Grumman"),
    ("GD", "General Dynamics"),
    ("BA", "Boeing"),
]
_WAR_HEDGE = [
    ("ITA", "Aerospace & Defense ETF", "defense"),
    ("XAR", "S&P Aero & Def ETF", "defense"),
    ("XLE", "Energy Select", "energy"),
    ("USO", "US Oil Fund", "energy"),
    ("GLD", "Gold SPDR", "safe_haven"),
    ("SLV", "Silver", "safe_haven"),
    ("BTC-USD", "Bitcoin", "safe_haven"),
    ("^VIX", "VIX", "fear"),
    ("UUP", "US Dollar Bull", "macro"),
]
_INSIDER_WATCH = [
    ("AAPL", "Tim Cook"),
    ("MSFT", "Satya Nadella"),
    ("NVDA", "Jensen Huang"),
    ("TSLA", "Elon Musk"),
    ("META", "Mark Zuckerberg"),
    ("AMZN", "Andy Jassy"),
    ("GOOG", "Sundar Pichai"),
    ("JPM", "Jamie Dimon"),
    ("BRK-B", "Warren Buffett"),
    ("DJT", "Trump Family"),
]
_CORR_SYMBOLS = [
    ("SPY", "S&P 500"),
    ("^TNX", "10Y Yield"),
    ("DJT", "Trump Media"),
    ("ITA", "Defense ETF"),
    ("GLD", "Gold"),
    ("USO", "Oil"),
    ("^VIX", "VIX"),
    ("BTC-USD", "Bitcoin"),
    ("XLE", "Energy"),
    ("TLT", "20Y Bonds"),
]


@router.get("/api/v7/macro-intel", tags=["v7-surface"])
async def macro_intel_data(request: Request):
    """
    v7 Macro Intelligence — political-economic risk monitor.
    Returns US rates & yield curve, political-risk tickers,
    war/geopolitical hedge basket, insider sentiment proxy,
    and cross-correlation matrix between all factors and SPY.
    """
    import asyncio
    import time as _time

    import numpy as np

    _cache = getattr(request.app.state, "macro_intel_cache", None)
    _cache_ts = float(getattr(request.app.state, "macro_intel_cache_ts", 0.0) or 0.0)
    if _cache is not None and (_time.monotonic() - _cache_ts) < 120:
        return _cache

    mds = request.app.state.market_data
    _yf_sem = asyncio.Semaphore(6)

    async def _factor(sym):
        try:
            async with _yf_sem:
                q = await mds.get_quote(sym)
                price = q["price"] if q else 0
                chg = q["change_pct"] if q else 0
                h = await mds.get_history(
                    sym,
                    period="3mo",
                    interval="1d",
                )
                w1 = w4 = ytd_pct = 0
                if h is not None and len(h) >= 2:
                    c_col = "Close" if "Close" in h.columns else "close"
                    c = h[c_col]
                    if len(c) >= 5:
                        w1 = float(
                            (c.iloc[-1] / c.iloc[-5] - 1) * 100,
                        )
                    if len(c) >= 20:
                        w4 = float(
                            (c.iloc[-1] / c.iloc[-20] - 1) * 100,
                        )
                    yr = f"{datetime.now(timezone.utc).year}-01-01"
                    jan = c.loc[c.index >= yr]
                    if len(jan) >= 2:
                        ytd_pct = float(
                            (c.iloc[-1] / jan.iloc[0] - 1) * 100,
                        )
            return {
                "symbol": sym,
                "price": round(price, 4),
                "change_pct": round(chg, 2),
                "week1_pct": round(w1, 2),
                "month1_pct": round(w4, 2),
                "ytd_pct": round(ytd_pct, 2),
            }
        except Exception:
            return {
                "symbol": sym,
                "price": 0,
                "change_pct": 0,
                "week1_pct": 0,
                "month1_pct": 0,
                "ytd_pct": 0,
            }

    async def _hist(sym, period="6mo"):
        try:
            async with _yf_sem:
                h = await mds.get_history(
                    sym,
                    period=period,
                    interval="1d",
                )
            return h if h is not None and len(h) > 5 else None
        except Exception:
            return None

    # ── 1. US Rates ────────────────────────────────
    rate_r = await asyncio.gather(
        *[_factor(s) for s, _, _ in _RATE_TICKERS], return_exceptions=True
    )
    etf_r = await asyncio.gather(
        *[_factor(s) for s, _ in _RATE_ETF], return_exceptions=True
    )

    rates = []
    for i, (sym, name, tenor) in enumerate(_RATE_TICKERS):
        r = rate_r[i] if not isinstance(rate_r[i], Exception) else {}
        rates.append(
            {
                "tenor": tenor,
                "name": name,
                "symbol": sym,
                "yield_pct": r.get("price", 0),
                "change_bps": round(r.get("change_pct", 0) * 100, 1),
                "week1_bps": round(r.get("week1_pct", 0) * 100, 1),
                "month1_bps": round(r.get("month1_pct", 0) * 100, 1),
            }
        )

    y = {r["tenor"]: r["yield_pct"] for r in rates}
    c10_3m = (
        round(y.get("10Y", 0) - y.get("3M", 0), 3)
        if y.get("10Y") and y.get("3M")
        else None
    )
    c30_10 = (
        round(y.get("30Y", 0) - y.get("10Y", 0), 3)
        if y.get("30Y") and y.get("10Y")
        else None
    )
    inv = (
        "INVERTED"
        if (c10_3m and c10_3m < 0)
        else ("NORMAL" if (c10_3m and c10_3m > 0.5) else "FLAT")
    )

    rate_etfs = []
    for i, (sym, name) in enumerate(_RATE_ETF):
        r = etf_r[i]
        if isinstance(r, dict):
            r["name"] = name
            rate_etfs.append(r)

    # ── 2. Political Risk Basket ───────────────────
    pol_r = await asyncio.gather(
        *[_factor(s) for s, _ in _POLITICAL_TICKERS], return_exceptions=True
    )
    political = []
    for i, (sym, name) in enumerate(_POLITICAL_TICKERS):
        r = pol_r[i]
        if isinstance(r, dict):
            r["name"] = name
            political.append(r)

    djt = next((p for p in political if p.get("symbol") == "DJT"), {})
    ts = (
        "BULLISH"
        if djt.get("change_pct", 0) > 2
        else ("BEARISH" if djt.get("change_pct", 0) < -2 else "NEUTRAL")
    )

    # ── 3. War / Geopolitical Hedge Basket ─────────
    war_r = await asyncio.gather(
        *[_factor(s) for s, _, _ in _WAR_HEDGE], return_exceptions=True
    )
    war_basket = []
    for i, (sym, name, cat) in enumerate(_WAR_HEDGE):
        r = war_r[i]
        if isinstance(r, dict):
            r["name"] = name
            r["category"] = cat
            war_basket.append(r)

    def_avg = (
        float(
            np.mean(
                [
                    w.get("month1_pct", 0)
                    for w in war_basket
                    if w.get("category") == "defense"
                ]
            )
        )
        if war_basket
        else 0
    )
    vix_p = next(
        (w.get("price", 0) for w in war_basket if w.get("symbol") == "^VIX"), 0
    )
    gld_ytd = next(
        (w.get("ytd_pct", 0) for w in war_basket if w.get("symbol") == "GLD"), 0
    )
    wrs = min(
        100,
        max(
            0,
            int(
                30
                + def_avg * 2
                + (vix_p - 18) * 2
                + (gld_ytd * 0.5 if gld_ytd > 0 else 0)
            ),
        ),
    )
    wrl = "HIGH" if wrs > 65 else ("ELEVATED" if wrs > 45 else "LOW")

    # ── 4. Insider / Executive Proxy ───────────────
    ins_r = await asyncio.gather(
        *[_factor(s) for s, _ in _INSIDER_WATCH], return_exceptions=True
    )
    insiders = []
    for i, (sym, exec_name) in enumerate(_INSIDER_WATCH):
        r = ins_r[i]
        if isinstance(r, dict):
            r["name"] = exec_name
            r["ticker"] = sym
            m1 = r.get("month1_pct", 0)
            r["insider_signal"] = (
                "ACCUMULATE" if m1 > 5 else "DISTRIBUTE" if m1 < -5 else "HOLD"
            )
            insiders.append(r)

    # ── 5. Cross-Correlation Matrix ────────────────
    ch = await asyncio.gather(
        *[_hist(s) for s, _ in _CORR_SYMBOLS], return_exceptions=True
    )
    rd = {}
    for i, (sym, label) in enumerate(_CORR_SYMBOLS):
        h = ch[i]
        if h is not None and not isinstance(h, Exception):
            if len(h) > 5:
                c_col = "Close" if "Close" in h.columns else "close"
                rd[label] = h[c_col].pct_change().dropna()
    cl = list(rd.keys())
    cm = {}
    for a in cl:
        row = {}
        for b in cl:
            ix = rd[a].index.intersection(rd[b].index)
            if len(ix) > 10:
                row[b] = round(
                    float(
                        np.corrcoef(rd[a].loc[ix].values, rd[b].loc[ix].values)[0, 1]
                    ),
                    3,
                )
            else:
                row[b] = 0
        cm[a] = row

    sc = cm.get("S&P 500", {})
    insights = []
    _ins = [
        (
            "Trump Media",
            0.3,
            -0.3,
            "DJT 與大盤正相關 — 政治信心推動市場",
            "DJT 與大盤負相關 — 政策不確定性增加",
        ),
        ("10Y Yield", 99, -0.3, "", "利率上升壓制股市 — 注意聯準會動向"),
        ("VIX", 99, -0.7, "", "VIX 與市場強烈負相關 — 恐慌指標有效"),
        ("Gold", 99, -0.2, "", "黃金避險需求上升 — 資金輪動離開股市"),
        ("Defense ETF", 0.3, -99, "國防股與大盤同步 — 地緣政治推升整體市場", ""),
        (
            "Oil",
            0.3,
            -0.3,
            "石油與大盤正相關 — 經濟擴張期",
            "石油與大盤負相關 — 供給衝擊風險",
        ),
        (
            "Bitcoin",
            0.4,
            -0.4,
            "加密貨幣與股市高度相關 — 風險偏好一致",
            "加密貨幣與股市負相關 — 避險分流",
        ),
    ]
    for fac, hi, lo, txt_hi, txt_lo in _ins:
        v = sc.get(fac, 0)
        if v > hi and txt_hi:
            insights.append(
                {"factor": fac, "corr": v, "text": txt_hi, "severity": "info"}
            )
        elif v < lo and txt_lo:
            insights.append(
                {"factor": fac, "corr": v, "text": txt_lo, "severity": "warning"}
            )

    rd_dir = "RISING" if sum(r.get("change_bps", 0) for r in rates) > 0 else "FALLING"
    pm = (
        round(float(np.mean([p.get("month1_pct", 0) for p in political])), 2)
        if political
        else 0
    )

    result = {
        "rates": {
            "yields": rates,
            "curve": {"spread_10y_3m": c10_3m, "spread_30y_10y": c30_10, "status": inv},
            "direction": rd_dir,
            "etfs": rate_etfs,
        },
        "political_risk": {
            "basket": political,
            "trump_sentiment": ts,
            "djt_price": djt.get("price", 0),
            "djt_change": djt.get("change_pct", 0),
            "basket_momentum_1m": pm,
        },
        "war_geopolitical": {
            "basket": war_basket,
            "risk_score": wrs,
            "risk_label": wrl,
            "defense_momentum_1m": round(def_avg, 2),
            "vix": vix_p,
            "gold_ytd": round(float(gld_ytd), 2),
        },
        "insider_proxy": {
            "watchlist": insiders,
            "accumulate_count": len(
                [x for x in insiders if x.get("insider_signal") == "ACCUMULATE"]
            ),
            "distribute_count": len(
                [x for x in insiders if x.get("insider_signal") == "DISTRIBUTE"]
            ),
        },
        "correlations": {
            "matrix": cm,
            "labels": cl,
            "spy_factors": sc,
            "insights": insights,
        },
        "summary": {
            "rate_direction": rd_dir,
            "yield_curve": inv,
            "trump_sentiment": ts,
            "war_risk": wrl,
            "war_risk_score": wrs,
            "political_momentum": pm,
        },
        "generated_at": datetime.now(timezone.utc).isoformat() + "Z",
    }
    request.app.state.macro_intel_cache = result
    request.app.state.macro_intel_cache_ts = _time.monotonic()
    return result
