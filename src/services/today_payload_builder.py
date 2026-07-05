"""Staged helpers for /api/v7/today payload assembly."""

from __future__ import annotations

from src.services.cc_display_constants import CC_TOP_MONITOR_COUNT
import asyncio
import logging
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional, Tuple

from fastapi import Request

Row = Dict[str, Any]
logger = logging.getLogger(__name__)

_TODAY_SCAN_TIMEOUT = 3.0


async def _fetch_market_pulse(request: Request) -> Dict[str, Any]:
    """Indices + sector leaders/laggards (bounded parallel history fetches)."""
    market_pulse: Dict[str, Any] = {}
    try:
        _LIVE_INDICES = request.app.state.live_indices
        _LIVE_SECTORS = request.app.state.live_sectors
        mds = request.app.state.market_data

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

        idx_results, sec_results = await asyncio.wait_for(
            asyncio.gather(
                asyncio.gather(*[_fetch_idx(sym, name) for sym, name in _LIVE_INDICES]),
                asyncio.gather(
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
    return market_pulse


@dataclass
class TodaySideContext:
    equity_dd_pct: Optional[float]
    pf_holdings: List[Row]
    pf_count: int
    pf_local_only: bool


def load_portfolio_holdings_snapshot() -> Tuple[List[Row], int, bool]:
    """Sync portfolio snapshot for passive baseline / CC OS context."""
    try:
        from src.api.routers.portfolio import _user_portfolio

        holdings = _user_portfolio.get("holdings") or []
        local_only = (_user_portfolio.get("source") or "manual") != "ibkr"
        return list(holdings), len(holdings), local_only
    except Exception:
        return [], 0, True


async def gather_today_side_context(
    request,
    *,
    used_brief_fallback: bool,
    scanner_degraded: bool,
) -> TodaySideContext:
    """Parallel side fetches: equity drawdown + portfolio holdings."""
    from src.services.today_insights import load_equity_dd_pct_for_hints

    async def _equity_dd() -> Optional[float]:
        if used_brief_fallback or scanner_degraded:
            return None
        return await load_equity_dd_pct_for_hints(request)

    equity_dd_pct, pf_tuple = await asyncio.gather(
        _equity_dd(),
        asyncio.to_thread(load_portfolio_holdings_snapshot),
    )
    pf_holdings, pf_count, pf_local_only = pf_tuple
    return TodaySideContext(
        equity_dd_pct=equity_dd_pct,
        pf_holdings=pf_holdings,
        pf_count=pf_count,
        pf_local_only=pf_local_only,
    )


def enrich_today_rows_post_regime(
    *,
    top5: List[Row],
    near_miss: List[Row],
    all_opps_for_action: List[Row],
    index_regime_summary: Dict[str, Any],
    tradeability: str,
    trend_label: str,
    breadth_pct: float,
    event_risks: List[str],
) -> Tuple[List[Row], List[Row], List[Row]]:
    """Cost rank + AI hints after index regime (authority already applied)."""
    from src.services.ranked_board_pipeline import enrich_ranked_board_row_groups

    market_regime = {
        "trend": trend_label,
        "tradeability": tradeability,
        "breadth": breadth_pct,
    }
    enriched = enrich_ranked_board_row_groups(
        {
            "top5": top5,
            "near_miss": near_miss,
            "all_opps": all_opps_for_action,
        },
        decision_authority=None,
        index_regime=index_regime_summary,
        tradeability=tradeability,
        market_regime=market_regime,
        event_risks=event_risks,
        apply_authority=False,
        authority_first=True,
    )
    return enriched["top5"], enriched["near_miss"], enriched["all_opps"]


def apply_today_opportunity_quality(
    *,
    top5: List[Row],
    near_miss: List[Row],
    tradeability: str,
    event_risks: List[str],
) -> Tuple[List[Row], List[Row]]:
    """Late opportunity-quality pass for deploy-adjacent row groups."""
    from src.services.ranked_board_pipeline import enrich_ranked_board_row_groups

    enriched = enrich_ranked_board_row_groups(
        {"top5": top5, "near_miss": near_miss},
        tradeability=tradeability,
        event_risks=event_risks,
        apply_authority=False,
        apply_cost_rank=False,
        apply_ai_hints=False,
        quality_keys={"top5", "near_miss"},
    )
    return enriched["top5"], enriched["near_miss"]


async def build_today_payload(request: Request) -> Tuple[Dict[str, Any], bool]:
    """Assemble full /api/v7/today payload.

    Returns (payload, cache_ok) where cache_ok mirrors legacy scanner_degraded gate.
    """
    from src.api.routers.decision import (
        _build_score_reconciliation_for_today,
        _council,
        _cross_asset_for_today,
        _invalidation,
        _position_hint,
        _setup_family,
        _timing_label,
    )
    from src.services.regime_service import get_regime as _fetch_regime

    # 1. Market Regime + pulse (independent I/O — run in parallel)
    regime_state, market_pulse = await asyncio.gather(
        _fetch_regime(request),
        _fetch_market_pulse(request),
    )
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

    # 2. Market pulse already fetched alongside regime (app.state.scan_cache aliases module _scan_cache from lifespan)
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
                        scan_cache = getattr(request.app.state, "scan_cache", None) or {}
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
        act = refine_action(cr)
        if act in ("AVOID", "NO_TRADE", "PASS"):
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
            "invalidation": getattr(pr.explanation, "invalidation", None) or _invalidation(sig),
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
        if len(top5) >= CC_TOP_MONITOR_COUNT:
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
    trade_count = sum(
        1 for cr in council_results if is_execution_ready(cr)
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
        best_net_edge_from_opportunities,
        build_candidate_bucket_counts,
        build_evidence_badges,
        build_evidence_conflict,
        build_monitor_triggers,
        build_near_miss_candidates,
        build_no_setup_diagnosis,
        build_quant_cluster_hints,
        build_regime_wait_explanation,
        build_sleeve_summary,
        build_todays_decision,
        build_top_monitor,
        build_top_opportunities,
        build_unlock_deploy,
        filter_valid_opportunities,
        merge_brief_board_fallback,
        resolve_book_dd_utilization_for_hints,
    )

    brief_age_days = 0
    brief_expired = False
    try:
        from src.api.routers.brief_regenerate import _latest_brief

        brief_info = _latest_brief() or {}
        brief_age_days = int(brief_info.get("age_days") or 0)
        from src.services.system_truth import BRIEF_EXPIRE_DAYS

        brief_expired = brief_age_days > BRIEF_EXPIRE_DAYS
    except Exception:
        brief_info = {}

    top5_tickers = {x["ticker"] for x in top5 if x.get("ticker")}
    near_miss = build_near_miss_candidates(council_results, top5_tickers, limit=3)
    live_board_available = not scanner_degraded and bool(top5 or near_miss)
    if brief_expired and not live_board_available:
        near_miss = []
    top5, near_miss, used_brief_fallback = merge_brief_board_fallback(
        top5,
        near_miss,
        scanner_degraded=scanner_degraded,
        brief_age_days=brief_age_days,
        top_limit=CC_TOP_MONITOR_COUNT,
    )
    if brief_expired:
        used_brief_fallback = False
        if live_board_available:
            narrative = (
                f"Brief expired {brief_age_days}d — live scanner board active. "
                "Brief narrative excluded; monitor watch candidates until deploy gates unlock."
            )
            if not scanner_reason:
                scanner_reason = f"Brief expired {brief_age_days}d — using live scanner"
        elif brief_age_days > 0:
            scanner_reason = scanner_reason or (
                f"Brief expired {brief_age_days}d — not used for ranking"
            )
            narrative = (
                f"Brief expired {brief_age_days}d — not used for ranking. "
                "No valid candidates. Best action: preserve capital."
            )
    elif used_brief_fallback:
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
    sleeve_summary: Dict[str, Any] = {"cards": [], "note": "lazy-load via /api/fund-lab/cards"}
    fund_cards: List[Dict[str, Any]] = []
    fund_cache = getattr(request.app.state, "fund_cards_cache", None)
    if isinstance(fund_cache, dict) and fund_cache.get("cards"):
        fund_cards = fund_cache.get("cards") or []
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
            "invalidation": getattr(pr.explanation, "invalidation", None) or _invalidation(sig),
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

        ibkr_st = get_ibkr_service().status()
        engine = get_engine(request.app)
        eng_running = bool(getattr(engine, "_running", False)) if engine else False
        from src.services.execution_guards import circuit_breaker_tripped

        eng_breaker = circuit_breaker_tripped(engine) if engine else False
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

    bracket_ready = bool(
        top5
        and top5[0].get("entry_price")
        and top5[0].get("stop_price")
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

    from src.services.execution_guards import circuit_breaker_tripped, engine_is_running

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

            engine = get_engine(request.app)
            if engine:
                if not eng_running:
                    eng_running = engine_is_running(engine)
                if not exec_blocked:
                    exec_blocked = circuit_breaker_tripped(engine)
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
    all_opps_for_action = apply_authority_to_rows(all_opps_for_action, decision_authority)
    near_miss = apply_authority_to_rows(near_miss, decision_authority)

    cross_asset_confirmation, side_ctx = await asyncio.gather(
        _cross_asset_for_today(
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
        gather_today_side_context(
            request,
            used_brief_fallback=used_brief_fallback,
            scanner_degraded=scanner_degraded,
        ),
    )
    from src.services.index_regime import build_index_regime_for_today
    from src.services.passive_baseline import build_passive_baseline_for_today

    pf_holdings = side_ctx.pf_holdings
    pf_count = side_ctx.pf_count
    pf_local_only = side_ctx.pf_local_only
    index_regime_summary, passive_baseline = await asyncio.gather(
        build_index_regime_for_today(
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
        ),
        build_passive_baseline_for_today(
            opportunities=all_opps_for_action,
            deployable_count=execution_ready_count,
            position_count=pf_count,
            local_only=pf_local_only,
        ),
    )
    regime_strip = {
        "line": index_regime_summary.get("strip_line") or index_regime_summary.get("summary"),
        "posture": index_regime_summary.get("posture"),
        "posture_label": index_regime_summary.get("posture_label"),
        "authority": "monitor_only",
        "data_mode": "regime_filter",
        "degraded": bool(index_regime_summary.get("degraded")),
        "may_authorize_deploy": False,
    }
    equity_dd_pct = side_ctx.equity_dd_pct
    top5, near_miss, all_opps_for_action = enrich_today_rows_post_regime(
        top5=top5,
        near_miss=near_miss,
        all_opps_for_action=all_opps_for_action,
        index_regime_summary=index_regime_summary,
        tradeability=tradeability,
        trend_label=trend_label,
        breadth_pct=round(breadth * 100),
        event_risks=event_risks,
    )
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

    unlock_degradation_notes: list[str] = []
    if scanner_degraded:
        unlock_degradation_notes.append(
            f"scanner context: {scanner_reason or 'warming'}"
        )
    if used_brief_fallback:
        unlock_degradation_notes.append("board context: brief fallback")
    unlock_deploy = build_unlock_deploy(
        tradeability=tradeability,
        should_trade=should_trade,
        watch_qualified_count=validated_count,
        deployable_count=execution_ready_count,
        scan_ranked_count=playbook_scan_ranked_count(funnel),
        scanner_degraded=scanner_degraded or used_brief_fallback,
        degradation_notes=unlock_degradation_notes or None,
        execution_readiness=execution_readiness,
    )

    from src.services.anti_overtrading import restraint_from_today_context
    from src.services.buffett_judgment import buffett_clarity_strip_for_today
    from src.services.crisis_regime import crisis_strip_for_today
    from src.services.decision_hierarchy import hierarchy_for_dashboard
    from src.services.decision_quality_naval import naval_clarity_strip_for_today
    from src.services.index_fund_judgment import index_fund_posture_strip_for_today
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
    surface_authority = authority_strip_for_today(
        tradeability=decision_model.get("honest_tradeability") or tradeability,
        ibkr_connected=ibkr_connected,
        deployable_count=execution_ready_count,
    )

    from src.services.cc_operating_system import build_cc_operating_system_context
    from src.services.drawdown_sizer import evaluate_drawdown_sizing
    from src.services.execution_analytics import (
        build_empty_execution_analytics_state,
        build_execution_analytics_from_ibkr,
    )
    from src.services.cc_tracker_wave import build_tracker_wave_context
    from src.services.safe_automation_support import build_safe_automation_context

    ibkr_fills: List[Dict[str, Any]] = []

    drawdown_sizing: Dict[str, Any] = {}
    if not used_brief_fallback and not scanner_degraded:
        dd_pct = equity_dd_pct if equity_dd_pct is not None else 0.0
        drawdown_sizing = evaluate_drawdown_sizing(
            current_dd_pct=dd_pct,
            fallback_or_stale=False,
        )
    else:
        drawdown_sizing = evaluate_drawdown_sizing(
            current_dd_pct=0.0,
            fallback_or_stale=True,
        )

    if ibkr_connected and not scanner_degraded and not used_brief_fallback:
        try:
            from src.services.ibkr_service import get_ibkr_service

            ibkr_fills = get_ibkr_service().get_recent_fills()
            execution_analytics = build_execution_analytics_from_ibkr(
                ibkr_fills,
                ibkr_connected=True,
            )
        except Exception:
            execution_analytics = build_empty_execution_analytics_state()
    else:
        execution_analytics = build_empty_execution_analytics_state()

    top5, near_miss = apply_today_opportunity_quality(
        top5=top5,
        near_miss=near_miss,
        tradeability=tradeability,
        event_risks=event_risks,
    )

    safe_automation = build_safe_automation_context(
        near_miss=near_miss,
        prior_near_miss=prior_near_miss or None,
        monitor_triggers=monitor_triggers,
        tradeability=tradeability,
        narrative=narrative,
        deployable_count=execution_ready_count,
        ibkr_connected=ibkr_connected,
        degraded=scanner_degraded or used_brief_fallback,
        quant_cluster_hints=quant_cluster_hints,
    )
    cc_os = build_cc_operating_system_context(
        trend=trend_label,
        vix=vix_val,
        breadth=breadth * 100 if breadth <= 1 else breadth,
        tradeability=tradeability,
        should_trade=should_trade,
        narrative=narrative,
        cross_asset=cross_asset_confirmation,
        index_regime_summary=index_regime_summary,
        sector_leaders=market_pulse.get("sector_leaders"),
        near_miss=near_miss,
        top5=top5,
        monitor_triggers=monitor_triggers,
        quant_cluster_hints=quant_cluster_hints,
        event_risks=event_risks,
        drawdown_sizing=drawdown_sizing,
        execution_analytics=execution_analytics,
        execution_readiness=execution_readiness,
        sleeve_summary=sleeve_summary,
        passive_baseline=passive_baseline,
        safe_automation=safe_automation,
        ai_intelligence=ai_intel,
        ibkr_connected=ibkr_connected,
        ibkr_fills=ibkr_fills,
        equity_dd_pct=equity_dd_pct,
        deployable_count=execution_ready_count,
        discovery_count=int(funnel.get("watch_qualified_setups") or 0),
        degraded=scanner_degraded or used_brief_fallback,
        positions=pf_holdings,
    )
    curve_gov = ((cc_os.get("modules") or {}).get("curve_governance")) if cc_os else None
    tracker_wave = build_tracker_wave_context(
        tradeability=tradeability,
        execution_analytics=execution_analytics,
        drawdown_sizing=drawdown_sizing,
        monitor_triggers=monitor_triggers,
        quant_cluster_hints=quant_cluster_hints,
        near_miss=near_miss,
        safe_automation=safe_automation,
        degraded=scanner_degraded or used_brief_fallback,
        ibkr_connected=ibkr_connected,
        curve_governance=curve_gov,
    )

    from src.services.decision_truth_model import finalize_funnel_qualification
    from src.services.qualification_levels import compute_qualification_levels
    from src.services.system_truth import resolve_system_truth

    funnel = finalize_funnel_qualification(
        funnel,
        decision_authority=decision_authority,
        execution_ready_count=execution_ready_count,
        tradeability=tradeability,
        should_trade=should_trade,
    )
    execution_ready_count = int(funnel.get("execution_qualified_setups") or execution_ready_count)
    deploy_qualified_count = int(funnel.get("deploy_qualified_setups") or 0)

    deploy_auth_flag = bool(
        (decision_authority or {}).get("allows_trade_labels")
        and (decision_authority or {}).get("authority_level") == "deploy"
        and not (decision_authority or {}).get("gates_active")
    )
    qualification_levels = compute_qualification_levels(
        all_opps_for_action,
        deploy_authority=deploy_auth_flag,
        funnel=funnel,
    )

    valid_top5 = build_top_opportunities(top5, limit=CC_TOP_MONITOR_COUNT)
    score_reconciliation = _build_score_reconciliation_for_today(
        valid_top5,
        cross_asset=cross_asset_confirmation,
    )
    evidence_conflict = build_evidence_conflict(
        top5=valid_top5,
        near_miss=near_miss if not brief_expired or live_board_available else [],
        score_reconciliation=score_reconciliation,
        todays_decision=todays_decision,
    )
    top_monitor = build_top_monitor(
        top5=valid_top5,
        near_miss=near_miss if not brief_expired or live_board_available else [],
        todays_decision=todays_decision,
    )
    candidate_counts = build_candidate_bucket_counts(
        council_results=council_results,
        funnel=funnel,
        top5=valid_top5,
        near_miss=near_miss if not brief_expired or live_board_available else [],
        avoid_grouped=avoid_grouped,
    )

    truth_seed = {
        "trust": {
            "stale": scanner_degraded or used_brief_fallback,
            "source": (
                "brief-expired"
                if brief_expired
                else (
                    "brief-fallback"
                    if used_brief_fallback
                    else (
                        "decision_engine"
                        if not scanner_degraded
                        else "decision_engine_degraded"
                    )
                )
            ),
            "freshness": "REAL_TIME" if not scanner_degraded else "DEGRADED",
        },
        "brief_status": brief_info if brief_info else {"age_days": brief_age_days},
        "used_brief_fallback": used_brief_fallback,
        "top_5": valid_top5,
        "filter_funnel": funnel,
        "market_regime": {
            "label": regime_label,
            "tradeability": tradeability,
            "honest_tradeability": decision_model.get("honest_tradeability", tradeability),
            "should_trade": should_trade,
        },
        "decision_authority": decision_authority,
        "execution_readiness": execution_readiness,
        "qualification_levels": qualification_levels,
        "execution_ready_count": execution_ready_count,
        "pilot_eligible_count": int(
            pilot_ready_count or funnel.get("pilot_eligible_setups") or 0
        ),
        "todays_decision": todays_decision,
        "scanner_degraded": scanner_degraded,
    }
    cc_header_ctx = {
        "data_tier": (
            "EXPIRED"
            if brief_expired
            else ("STALE" if scanner_degraded or used_brief_fallback else "FRESH")
        ),
        "freshness_tier": (
            "EXPIRED"
            if brief_expired
            else ("STALE" if scanner_degraded or used_brief_fallback else "FRESH")
        ),
        "brief_fallback": used_brief_fallback and not brief_expired,
        "brief_expired": brief_expired,
        "brief_age_days": brief_age_days,
        "scanner_degraded": scanner_degraded,
        "tradeability": tradeability,
        "should_trade": should_trade,
        "ibkr_ready": ibkr_connected,
        "ibkr_connected": ibkr_connected,
        "exec_blocked": exec_blocked,
    }
    ops_ctx = {
        "engine_running": eng_running,
        "exec_blocked": exec_blocked,
    }
    system_truth = resolve_system_truth(
        truth_seed, cc_header_ctx, ops_ctx, brief_age_days=brief_age_days
    )
    from src.services.operator_surface import build_operator_block

    operator_block = {
        "dashboard": build_operator_block(system_truth, "dashboard"),
        "playbook": build_operator_block(system_truth, "playbook"),
        "dossier": build_operator_block(system_truth, "dossier"),
        "funds": build_operator_block(system_truth, "funds"),
        "agent": build_operator_block(system_truth, "agent"),
    }
    system_truth = {
        **system_truth,
        "operator_block": operator_block.get("dashboard"),
        "truth_strip": system_truth.get("truth_strip") or "",
    }
    from src.services.opportunity_quality import build_opportunity_status
    from src.services.options_availability import batch_options_availability

    deploy_blocked = str(system_truth.get("deploy_authority_tier") or "") != "allowed"
    from src.services.cc_daily_trading import build_actionable_today

    actionable_today = build_actionable_today(
        valid_top5 + list(near_miss or []),
        system_truth=system_truth,
        near_miss=near_miss if not brief_expired or live_board_available else [],
        limit=3,
    )
    options_signals = batch_options_availability(
        valid_top5 + list(near_miss or []),
        deploy_blocked=deploy_blocked,
        limit=CC_TOP_MONITOR_COUNT,
    )
    opportunity_status = build_opportunity_status(
        system_truth,
        candidates=valid_top5,
        near_miss=near_miss if not brief_expired or live_board_available else [],
        unlock_deploy=unlock_deploy,
        sector_leaders=market_pulse.get("sector_leaders"),
        options_signals=options_signals,
    )
    from src.services.position_sizing import attach_sizing_to_rows

    valid_top5 = attach_sizing_to_rows(valid_top5, system_truth)

    todays_decision = {
        **todays_decision,
        "morning_decision_line": system_truth.get("morning_decision_line"),
        "system_reason_codes": system_truth.get("reason_codes"),
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
            "honest_tradeability": decision_model.get("honest_tradeability", tradeability),
            "summary": narrative,
            "trend": trend_label,
            "volatility": vol_label,
            "score": score,
            "vix": round(vix_val, 1),
            "breadth": round(breadth * 100),
            "entropy": round(entropy, 2),
        },
        "market_pulse": market_pulse,
        "top_5": valid_top5,
        "top_monitor": top_monitor,
        "top_opportunities": valid_top5,
        "candidate_counts": candidate_counts,
        "evidence_conflict": evidence_conflict,
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
        "opportunity_status": opportunity_status,
        "regime_wait_explanation": regime_wait_explanation,
        "monitor_triggers": monitor_triggers,
        "quant_cluster_hints": quant_cluster_hints,
        "sleeve_summary": sleeve_summary,
        "execution_readiness": execution_readiness,
        "execution_analytics": execution_analytics,
        "drawdown_sizing": drawdown_sizing,
        "tracker_wave": tracker_wave,
        "cc_os": cc_os,
        "safe_automation": safe_automation,
        "evidence_badges": build_evidence_badges(
            scanner_degraded=scanner_degraded,
            regime_synthetic=bool(getattr(request.app.state, "regime_synthetic", False)),
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
        "score_reconciliation": score_reconciliation,
        "decision_authority": decision_authority,
        "system_truth": system_truth,
        "actionable_today": actionable_today,
        "operator_block": operator_block,
        "qualification_levels": qualification_levels,
        "trust": {
            "mode": "LIVE" if should_trade else "PAPER",
            "source": (
                "brief-expired"
                if brief_expired
                else (
                    "brief-fallback"
                    if used_brief_fallback
                    else (
                        "decision_engine"
                        if not scanner_degraded
                        else "decision_engine_degraded"
                    )
                )
            ),
            "freshness": system_truth.get("freshness_tier") or (
                "REAL_TIME" if not scanner_degraded else "DEGRADED"
            ),
            "freshness_tier": system_truth.get("freshness_tier"),
            "stale": scanner_degraded or used_brief_fallback or brief_expired,
            "reason": scanner_reason or (
                f"Brief expired {brief_age_days}d — not used for ranking"
                if brief_expired
                else ("brief fallback board" if used_brief_fallback else "")
            ),
            "as_of": now.isoformat() + "Z",
            "ai_powered": False,
        },
        "generated_at": now.isoformat() + "Z",
    }
    return payload, not scanner_degraded
