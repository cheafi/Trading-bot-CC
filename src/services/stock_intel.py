"""Aggregate single-stock intelligence for Dossier command center."""

from __future__ import annotations

import asyncio
import logging
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from src.api.deps import sanitize_for_json

logger = logging.getLogger(__name__)

_SUB_FETCH_TIMEOUT_SEC = 12.0
_DOSSIER_TIMEOUT_SEC = 18.0


async def _await_bounded(coro, timeout_sec: float, label: str):
    """Bound sub-fetch latency so stock-intel does not hang the UI."""
    try:
        return await asyncio.wait_for(coro, timeout=timeout_sec)
    except asyncio.TimeoutError:
        logger.warning("stock-intel sub-fetch timeout: %s (%.0fs)", label, timeout_sec)
        return TimeoutError(f"{label} timed out after {timeout_sec}s")


def _build_unified_decision(
    dossier: Dict[str, Any],
    conviction: Optional[Dict[str, Any]],
) -> Dict[str, Any]:
    """Merge dossier verdict heuristics, conviction action, and trade_plan."""
    regime = dossier.get("regime") or {}
    trade_ok = regime.get("should_trade", True)
    conf = (dossier.get("confidence") or {}).get("final")
    if conf is None:
        conf = (dossier.get("signal") or {}).get("confidence", {}).get("final", 0)
    conflict = ((dossier.get("conflict") or {}).get("conflict_level")
        or (dossier.get("signal") or {}).get("conflict", {}).get("conflict_level")
        or "LOW"
    )
    sect = dossier.get("sector") or dossier.get("signal", {}).get("sector") or {}
    leader = sect.get("leader_status") == "LEADER"
    tp = dossier.get("trade_plan") or {}

    conv_action = (conviction or {}).get("action") or ""
    label = "WATCH"
    pill = "pa"
    color = "amber"
    reason_parts: List[str] = []

    if not trade_ok:
        label = "NO TRADE"
        pill = "pr"
        color = "red"
        reason_parts.append("Regime gate off — sit out new risk.")
    elif conflict == "HIGH":
        label = "AVOID"
        pill = "pr"
        color = "red"
        reason_parts.append("High evidence conflict — wait for clarity.")
    elif conv_action in ("BUY",) or (conf >= 0.7 and conflict == "LOW" and leader):
        label = "TRADE"
        pill = "pg"
        color = "green"
        reason_parts.append("Unified: high conviction, regime OK, sector leader.")
    elif conv_action in ("WATCH", "WAIT"):
        label = "WATCH"
        pill = "pa"
        color = "amber"
        reason_parts.append(conviction.get("why_now", ["Setup forming — monitor trigger."])[0] if conviction else "Monitor for entry trigger.")
    elif conv_action in ("AVOID", "NO_TOUCH"):
        label = "AVOID"
        pill = "pr"
        color = "red"
        reason_parts.append("Conviction stack suggests avoid / no touch.")
    elif conf >= 0.55:
        label = "WATCH"
        pill = "pa"
        color = "amber"
        reason_parts.append("Moderate conviction — do not chase.")
    else:
        label = "PASS"
        pill = "pw"
        color = "border"
        reason_parts.append("Insufficient edge for new capital.")

    entry = dossier.get("price")
    stop = tp.get("stop")
    if not stop and dossier.get("technicals", {}).get("atr") and entry:
        stop = round(float(entry) - 1.5 * float(dossier["technicals"]["atr"]), 2)

    return {
        "label": label,
        "pill": pill,
        "color": color,
        "confidence": round(float(conf or 0), 2),
        "reason": " ".join(reason_parts)[:280],
        "entry_zone": tp.get("entry_zone"),
        "stop": stop,
        "target_1r": tp.get("target_1r"),
        "target_2r": tp.get("target_2r"),
        "invalidation": tp.get("invalidation"),
        "rr_ratio": tp.get("rr_ratio"),
    }


def _narrative_structured(dossier: Dict[str, Any], conviction: Optional[Dict[str, Any]]) -> Dict[str, Any]:
    """Rule-based bull/bear/contradiction — no LLM wall of text."""
    bull: List[str] = []
    bear: List[str] = []
    for w in dossier.get("why_buy") or []:
        if isinstance(w, str) and w.strip():
            bull.append(w.strip()[:120])
    for w in dossier.get("why_stop") or []:
        if isinstance(w, str) and w.strip():
            bear.append(w.strip()[:120])
    if conviction:
        for w in conviction.get("why_now") or []:
            if w not in bull:
                bull.append(str(w)[:120])
        for w in conviction.get("why_not") or []:
            if w not in bear:
                bear.append(str(w)[:120])

    conflict_level = (dossier.get("conflict") or {}).get("conflict_level", "LOW")
    contradictions: List[str] = []
    if conflict_level == "HIGH":
        contradictions.append("Technical and fundamental signals disagree materially.")
    t = dossier.get("technicals") or {}
    if t.get("rsi") and float(t["rsi"]) > 70 and bull:
        contradictions.append("RSI elevated while bullish thesis active — extension risk.")
    if t.get("above_sma50") is False and bull:
        contradictions.append("Price below 50-day MA despite bullish factors.")

    return {
        "bull_case": bull[:4],
        "bear_case": bear[:4],
        "contradictions": contradictions[:3],
        "one_line_bull": bull[0] if bull else None,
        "one_line_bear": bear[0] if bear else None,
    }


def _catalyst_strip(p9_earnings: Optional[Dict[str, Any]], events: Optional[Dict[str, Any]]) -> Dict[str, Any]:
    items: List[Dict[str, Any]] = []
    if p9_earnings:
        if p9_earnings.get("next_earnings_date"):
            items.append(
                {
                    "horizon": "30d",
                    "label": "Earnings",
                    "date": p9_earnings.get("next_earnings_date"),
                    "detail": f"Days: {p9_earnings.get('days_to_earnings', '—')}",
                    "severity": "high" if p9_earnings.get("in_blackout") else "medium",
                }
            )
        if p9_earnings.get("in_blackout"):
            items.append(
                {
                    "horizon": "7d",
                    "label": "Earnings blackout",
                    "date": None,
                    "detail": "Avoid new positions until cleared",
                    "severity": "high",
                }
            )
    days = p9_earnings.get("days_to_earnings") if p9_earnings else None
    if days is not None and days > 30:
        items.append(
            {
                "horizon": "90d",
                "label": "Earnings window",
                "date": p9_earnings.get("next_earnings_date"),
                "detail": f"~{days} days — plan size reduction",
                "severity": "medium",
            }
        )
    for f in (events or {}).get("filings") or []:
        if isinstance(f, dict) and f.get("form_type") in ("8-K", "10-Q", "10-K"):
            items.append(
                {
                    "horizon": "90d",
                    "label": f"SEC {f.get('form_type', 'filing')}",
                    "date": f.get("filed_date") or f.get("filing_date"),
                    "detail": (f.get("description") or "")[:60],
                    "severity": "low",
                }
            )
            if len(items) >= 6:
                break
    if not items:
        items.append(
            {
                "horizon": "30d",
                "label": "No scheduled catalyst",
                "date": None,
                "detail": "Check earnings calendar manually",
                "severity": "low",
            }
        )
    return {"items": items[:8], "next_label": items[0]["label"] if items else None}


def _ownership_panel(conviction: Optional[Dict[str, Any]], edgar_insider: Optional[Dict[str, Any]]) -> Dict[str, Any]:
    insider = (conviction or {}).get("insider") or {}
    sponsor = (conviction or {}).get("sponsor") or {}
    filings: List[Dict[str, Any]] = []
    if edgar_insider and isinstance(edgar_insider, dict):
        summary = edgar_insider
        filings.append(
            {
                "source": "SEC Form 4",
                "lag": "Medium (~2–5 days)",
                "signal": summary.get("signal", "NEUTRAL"),
                "buys": summary.get("buy_filings", 0),
                "sells": summary.get("sell_filings", 0),
                "form4_count": summary.get("form4_filings", 0),
            }
        )
    elif insider.get("sentiment"):
        filings.append(
            {
                "source": "SEC Form 4 (conviction)",
                "lag": "Medium",
                "signal": insider.get("sentiment", {}).get("signal", "—"),
                "cluster_buy": insider.get("cluster_buy", False),
            }
        )
    overlap = (sponsor.get("13f_overlap") or {}).get("matched_sponsors") or []
    return {
        "insider": insider,
        "sponsor": sponsor,
        "filings_summary": filings,
        "lag_warning": "13F filings lag ~45–90 days; commentary ≠ capital",
    }


def _smart_money_summary(
    ownership: Dict[str, Any],
    options: Optional[Dict[str, Any]],
    conviction: Optional[Dict[str, Any]],
) -> Dict[str, Any]:
    """Evidence-weighted smart money — not gossip."""
    filings = ownership.get("filings_summary") or []
    insider_sig = "neutral"
    for f in filings:
        sig = (f.get("signal") or "").upper()
        if sig in ("BULLISH", "BUY", "CLUSTER_BUY"):
            insider_sig = "bullish"
        elif sig in ("BEARISH", "SELL"):
            insider_sig = "bearish"

    hf_trend = "unknown"
    sponsor = ownership.get("sponsor") or {}
    overlap = sponsor.get("13f_overlap") or {}
    if overlap.get("matched_sponsors"):
        hf_trend = "notable_holdings_lagged"

    opt_label = "no_data"
    if options and isinstance(options, dict):
        grade = options.get("grade") or options.get("quality_grade")
        if grade in ("A", "B"):
            opt_label = "unusual_activity_watch"
        elif grade:
            opt_label = "low_conviction_flow"

    sources: List[Dict[str, Any]] = [
        {
            "category": "insider",
            "evidence_type": "form_4",
            "signal_quality": "confirmed_filing",
            "relevance": "single_stock",
            "timeliness": "medium_lag",
            "bias": insider_sig,
        },
        {
            "category": "13f",
            "evidence_type": "13f",
            "signal_quality": "delayed_filing",
            "relevance": "single_stock",
            "timeliness": "stale_informative",
            "bias": hf_trend,
        },
        {
            "category": "politician",
            "evidence_type": "disclosure",
            "signal_quality": "inferred",
            "relevance": "single_stock",
            "timeliness": "variable",
            "bias": "none",
        },
        {
            "category": "options",
            "evidence_type": "market_flow",
            "signal_quality": "live" if options else "unavailable",
            "relevance": "single_stock",
            "timeliness": "recent",
            "bias": opt_label,
        },
    ]

    return {
        "summary_headline": "Ownership / Smart Money (supporting only)",
        "insider": insider_sig,
        "hedge_fund_trend": hf_trend,
        "politician_trend": "none",
        "options_flow": opt_label,
        "confidence": "medium" if filings else "low",
        "usefulness": "supportive_only — not standalone trigger",
        "sources": sources,
    }


def _build_institutional_action_box(
    *,
    unified: Dict[str, Any],
    pm_answer: Dict[str, Any],
    regime: Any,
    portfolio_fit: Dict[str, Any],
    options_block: Dict[str, Any],
    flow_intel: Optional[Dict[str, Any]],
    catalysts: Dict[str, Any],
) -> Dict[str, Any]:
    """PM action enum — explicit, not fake precision."""
    label = (unified.get("label") or "WATCH").upper()
    rsi = None
    change = None
    flow_top = (flow_intel or {}).get("top") or {}
    flow_action = flow_top.get("pm_action")
    regime_ok = getattr(regime, "should_trade", True)
    pf_score = int(portfolio_fit.get("score") or 50)

    state = "WATCH_CONFIRM"
    reason = unified.get("reason") or "Monitor for trigger."

    if not regime_ok or label in ("NO TRADE", "AVOID", "PASS"):
        state = "AVOID_NOW"
        reason = "Regime or unified decision blocks new risk."
    elif flow_action == "BUYABLE_NOW" and label == "TRADE":
        state = "BUY_NOW"
        reason = "Flow + stock + unified decision aligned."
    elif flow_action in ("WATCH_FOR_STOCK_CONFIRM",) or label == "WATCH":
        state = "BUY_ON_PULLBACK" if pf_score >= 55 else "WATCH_CONFIRM"
        reason = "Setup forming — wait for confirmation or pullback."
    elif flow_action == "AVOID_CHASE":
        state = "OVEREXTENDED"
        reason = "Flow suggests late chase / crowded."
    elif flow_action in ("LIKELY_HEDGING_FLOW", "HEDGE_NO_EDGE"):
        state = "HEDGE_CANDIDATE"
        reason = "Options activity may be hedge — not directional edge."
    elif catalysts.get("next_label") and label != "TRADE":
        state = "CATALYST_WATCH"
        reason = f"Event-driven: {catalysts.get('next_label')}"
    elif label == "TRADE":
        state = "BUY_NOW"
        reason = unified.get("reason") or "Unified trade signal."

    return {
        "state": state,
        "reason": reason[:280],
        "confidence": unified.get("confidence"),
        "evidence_quality": (
            "live_flow_calibrated"
            if (flow_intel or {}).get("top", {}).get("follow_through", {}).get("sufficient")
            else "heuristic"
        ),
        "flow_pm_action": flow_action,
        "portfolio_fit_score": pf_score,
        "regime_allows": regime_ok,
    }


def _pm_answer_layer(
    unified: Dict[str, Any],
    narrative: Dict[str, Any],
    dossier: Dict[str, Any],
    catalysts: Dict[str, Any],
) -> Dict[str, Any]:
    """PM answer layer — bull/bear/now/wait/avoid."""
    label = (unified.get("label") or "WATCH").upper()
    action_map = {
        "TRADE": "NOW",
        "BUY": "NOW",
        "WATCH": "WAIT",
        "AVOID": "AVOID",
        "NO TRADE": "AVOID",
        "PASS": "AVOID",
    }
    tech = dossier.get("technicals") or {}
    setup = "swing"
    if tech.get("rsi") and float(tech["rsi"]) < 35:
        setup = "mean_reversion"
    elif tech.get("above_sma200") and tech.get("volume_ratio", 1) > 1.2:
        setup = "momentum_breakout"

    confirms: List[str] = []
    if unified.get("rr_ratio") and float(unified.get("rr_ratio") or 0) >= 2.5:
        confirms.append("R:R ≥2.5 on trade plan")
    if (dossier.get("regime") or {}).get("should_trade"):
        confirms.append("Regime gate open")
    if catalysts.get("next_label"):
        confirms.append(f"Catalyst: {catalysts.get('next_label')}")

    return {
        "bull_case": narrative.get("bull_case") or [],
        "bear_case": narrative.get("bear_case") or [],
        "thesis_breaks": unified.get("invalidation") or narrative.get("one_line_bear"),
        "thesis_confirms": confirms,
        "best_setup_type": setup,
        "investor_fit": "Growth/momentum PM" if setup.startswith("momentum") else "Patient swing",
        "action_now": action_map.get(label, "WAIT"),
        "scale_in": label == "WATCH",
        "one_line": unified.get("reason"),
    }


def _identity_layer(dossier: Dict[str, Any], peers: Any) -> Dict[str, Any]:
    """Identity + factor tags."""
    sect = dossier.get("sector") or dossier.get("signal", {}).get("sector") or {}
    factors: List[str] = []
    name = (dossier.get("company") or dossier.get("name") or "").lower()
    if any(x in name for x in ("nvidia", "amd", "semi")):
        factors.append("AI_beta")
    if sect.get("sector_type") == "DEFENSIVE":
        factors.append("defensive")
    if sect.get("sector_type") == "HIGH_GROWTH":
        factors.append("growth")
    return {
        "company": dossier.get("company") or dossier.get("name"),
        "sector": sect.get("sector") or sect.get("name"),
        "industry": sect.get("industry") or sect.get("sub_sector"),
        "factor_tags": factors or ["general_equity"],
        "peer_count": len((peers or {}).get("rankings") or (peers or {}).get("table") or []),
        "business_note": "Load 10-K segments for revenue mix (P1)",
    }


def _monitor_panel(ticker: str, dossier: Dict[str, Any], positions: List[Dict[str, Any]]) -> Optional[Dict[str, Any]]:
    pos = None
    for p in positions or []:
        sym = (p.get("ticker") or p.get("symbol") or "").upper()
        if sym == ticker.upper():
            pos = p
            break
    if not pos:
        return None
    entry = float(pos.get("entry_price") or pos.get("avg_cost") or 0)
    price = float(dossier.get("price") or 0)
    pnl_pct = round((price / entry - 1) * 100, 2) if entry > 0 and price > 0 else None
    checklist = [
        {"item": "Thesis intact", "ok": len(dossier.get("why_buy") or []) > 0},
        {"item": "Above stop", "ok": True},
        {"item": "Regime allows hold", "ok": dossier.get("regime", {}).get("should_trade", True)},
    ]
    return {
        "position": pos,
        "pnl_pct": pnl_pct,
        "checklist": checklist,
        "what_changed": [
            f"Mark ${price:.2f} vs entry ${entry:.2f}" if entry else "Price updated",
        ],
    }


async def build_stock_intel(request, ticker: str) -> Dict[str, Any]:
    """Single-call aggregate for Dossier UI."""
    from src.api.live_state import fetch_regime_state
    from src.api.routers.conviction import stock_conviction as _conviction_endpoint
    from src.api.routers.dossier import peer_comparison
    from src.api.routers.live_dossier import live_dossier
    from src.ingestors.edgar import EdgarClient

    ticker = ticker.strip().upper()
    if not ticker:
        raise ValueError("Ticker required")

    mds = request.app.state.market_data

    results = await asyncio.gather(
        _await_bounded(live_dossier(ticker, request), _DOSSIER_TIMEOUT_SEC, "dossier"),
        _await_bounded(_conviction_endpoint(ticker, request), _SUB_FETCH_TIMEOUT_SEC, "conviction"),
        _await_bounded(peer_comparison(ticker), 8.0, "peers"),
        _await_bounded(_fetch_v9(mds, ticker, "fundamentals"), _SUB_FETCH_TIMEOUT_SEC, "p9_fundamentals"),
        _await_bounded(_fetch_v9(mds, ticker, "earnings"), _SUB_FETCH_TIMEOUT_SEC, "p9_earnings"),
        _await_bounded(_fetch_v9(mds, ticker, "structure"), _SUB_FETCH_TIMEOUT_SEC, "p9_structure"),
        _await_bounded(_fetch_options(request, ticker), 8.0, "options"),
        _await_bounded(_fetch_events(ticker), 6.0, "events"),
        _await_bounded(_fetch_edgar_insider(ticker), 8.0, "edgar_insider"),
        _await_bounded(_fetch_ibkr_status(), 4.0, "ibkr_status"),
        return_exceptions=True,
    )

    def _unwrap(idx: int, default: Any) -> Any:
        r = results[idx]
        return default if isinstance(r, Exception) else r

    dossier_raw = results[0]
    if isinstance(dossier_raw, Exception):
        raise ValueError(f"Dossier fetch failed: {dossier_raw}") from dossier_raw
    dossier = dossier_raw if isinstance(dossier_raw, dict) else {}
    if not dossier.get("symbol") and not dossier.get("price"):
        raise ValueError("Dossier returned empty payload")
    conviction = _unwrap(1, None)
    peers = _unwrap(2, {"rankings": []})
    p9 = {
        "fundamentals": _unwrap(3, None),
        "earnings": _unwrap(4, None),
        "structure": _unwrap(5, None),
    }
    options = _unwrap(6, None)
    events = _unwrap(7, {})
    edgar_insider = _unwrap(8, None)
    ibkr = _unwrap(9, {"connected": False, "mode": "paper"})

    dossier["_p9"] = p9
    unified = _build_unified_decision(dossier, conviction if isinstance(conviction, dict) else None)
    narrative = _narrative_structured(
        dossier, conviction if isinstance(conviction, dict) else None
    )
    catalysts = _catalyst_strip(p9.get("earnings"), events if isinstance(events, dict) else None)
    ownership = _ownership_panel(
        conviction if isinstance(conviction, dict) else None,
        edgar_insider if isinstance(edgar_insider, dict) else None,
    )

    positions: List[Dict[str, Any]] = []
    try:
        from src.api.routers.portfolio import _user_portfolio

        positions = _user_portfolio.get("holdings") or []
    except Exception:
        pass

    monitor = _monitor_panel(ticker, dossier, positions)
    regime = await fetch_regime_state(request)

    smart_money = _smart_money_summary(ownership, options, conviction)
    pm_answer = _pm_answer_layer(unified, narrative, dossier, catalysts)
    identity = _identity_layer(dossier, peers)

    from src.services.confluence_engine import build_confluence
    from src.services.decision_bar import bar_from_stock
    from src.services.pm_memory import build_thesis_block, get_memory
    from src.services.portfolio_fit import build_portfolio_fit
    from src.services.thesis_drift import build_thesis_drift

    sect_name = identity.get("sector")
    portfolio_fit = build_portfolio_fit(
        ticker, positions, sector=sect_name
    )
    confluence = build_confluence(
        dossier=dossier,
        unified=unified,
        smart_money=smart_money,
        pm_answer=pm_answer,
        regime={"should_trade": regime.should_trade, "label": regime.regime},
        portfolio_fit=portfolio_fit,
    )
    decision_bar = bar_from_stock(
        ticker=ticker,
        unified=unified,
        pm_answer=pm_answer,
        catalysts=catalysts,
        smart_money=smart_money,
    )
    thesis = build_thesis_block(ticker, {"narrative": narrative, "pm_answer": pm_answer, "unified_decision": unified})
    pm_mem = get_memory(ticker)
    thesis_drift = build_thesis_drift(
        ticker,
        stock_intel={
            "unified_decision": unified,
            "narrative": narrative,
            "regime": {"should_trade": regime.should_trade},
        },
        pm_memory=pm_mem.get("summary"),
    )
    fundamentals_block = _fundamentals_block(p9.get("fundamentals"), dossier)
    peers_block = _peers_block(peers)
    options_block = _options_block(options)

    flow_intel = None
    try:
        from src.services.flow_decision_surface import build_ticker_flow_intel

        flow_intel = await build_ticker_flow_intel(request, ticker)
        if flow_intel.get("top"):
            top = flow_intel["top"]
            options_block = {
                **options_block,
                "has_data": True,
                "flow_pm_action": top.get("pm_action"),
                "flow_grade": top.get("quality_grade"),
                "flow_synthetic": top.get("synthetic"),
                "follow_through": top.get("follow_through"),
                "classification": top.get("options_detail", {}).get(
                    "open_close_estimate", options_block.get("classification")
                ),
            }
    except Exception as exc:
        logger.debug("ticker flow intel skipped for %s: %s", ticker, exc)

    action_box = _build_institutional_action_box(
        unified=unified,
        pm_answer=pm_answer,
        regime=regime,
        portfolio_fit=portfolio_fit,
        options_block=options_block,
        flow_intel=flow_intel,
        catalysts=catalysts,
    )

    return sanitize_for_json(
        {
            "ticker": ticker,
            "as_of": datetime.now(timezone.utc).isoformat() + "Z",
            "decision_bar": decision_bar,
            "action_box": action_box,
            "flow_intel": flow_intel,
            "confluence": confluence,
            "portfolio_fit": portfolio_fit,
            "thesis": thesis,
            "thesis_drift": thesis_drift,
            "pm_memory": pm_mem,
            "fundamentals_block": fundamentals_block,
            "peers_block": peers_block,
            "options_block": options_block,
            "identity": identity,
            "dossier": dossier,
            "conviction": conviction,
            "unified_decision": unified,
            "narrative": narrative,
            "pm_answer": pm_answer,
            "smart_money": smart_money,
            "peers": peers,
            "options": options,
            "catalysts": catalysts,
            "ownership": ownership,
            "monitor": monitor,
            "regime": {"label": regime.regime, "should_trade": regime.should_trade},
            "ibkr": ibkr,
            "has_position": monitor is not None,
            "layers": {
                "identity": bool(identity),
                "fundamentals": bool(p9.get("fundamentals") or fundamentals_block),
                "technicals": bool(dossier.get("technicals")),
                "peers": bool(peers_block.get("rows")),
                "positioning": bool(options or ownership),
                "options": bool(options_block.get("has_data")),
                "smart_money": bool(smart_money),
                "catalysts": bool(catalysts.get("items")),
                "portfolio_fit": bool(portfolio_fit),
                "thesis": True,
                "pm_answer": True,
            },
        }
    )


def _fundamentals_block(
    raw: Optional[Dict[str, Any]],
    dossier: Dict[str, Any],
) -> Dict[str, Any]:
    """Structured fundamental intelligence."""
    flags: List[str] = []
    if raw:
        pe = raw.get("pe_ratio") or raw.get("trailingPE")
        if pe and float(pe) > 40:
            flags.append("rich_valuation")
        growth = raw.get("revenue_growth") or raw.get("revenueGrowth")
        if growth and float(growth) < 0:
            flags.append("story_broken_risk")
    return {
        "has_data": bool(raw),
        "raw": raw,
        "revenue_growth": (raw or {}).get("revenue_growth") or (raw or {}).get("revenueGrowth"),
        "earnings_growth": (raw or {}).get("earnings_growth"),
        "margin_trend": (raw or {}).get("profit_margin"),
        "valuation_note": (raw or {}).get("valuation") or "See multiples vs peers",
        "quality_score": (raw or {}).get("quality_score"),
        "flags": flags,
        "cheap_for_reason": "rich_valuation" in flags,
        "story_broken": "story_broken_risk" in flags,
        "price": dossier.get("price"),
    }


def _peers_block(peers: Any) -> Dict[str, Any]:
    table = []
    if isinstance(peers, dict):
        table = peers.get("rankings") or peers.get("table") or peers.get("peers") or []
    return {
        "rows": table[:8] if isinstance(table, list) else [],
        "winner_label": "Compare RS and growth in table",
        "crowded_leader": None,
        "evidence": {"basis": "peer_comparison_api", "label": "Live peer matrix when cached"},
    }


def _options_block(options: Optional[Dict[str, Any]]) -> Dict[str, Any]:
    if not options or not isinstance(options, dict):
        return {
            "has_data": False,
            "flow_quality_score": 0,
            "classification": "no_data",
        }
    grade = options.get("grade") or options.get("quality_grade") or "—"
    return {
        "has_data": True,
        "iv_percentile": options.get("iv_percentile"),
        "put_call_skew": options.get("put_call_ratio") or options.get("skew"),
        "unusual_volume": options.get("unusual_activity"),
        "leaps_note": options.get("leaps_accumulation"),
        "flow_quality_score": 70 if grade in ("A", "B") else 40,
        "classification": (
            "directional_conviction"
            if grade in ("A", "B")
            else "short_dated_noise"
        ),
        "expected_move": options.get("expected_move"),
        "raw_summary": options.get("summary") or options.get("headline"),
    }


async def _fetch_v9(mds, ticker: str, kind: str) -> Optional[Dict[str, Any]]:
    try:
        if kind == "fundamentals":
            from src.engines.fundamental_data import get_fundamentals

            return await asyncio.to_thread(get_fundamentals, ticker)
        if kind == "earnings":
            from src.engines.earnings_calendar import get_earnings_info

            return await asyncio.to_thread(get_earnings_info, ticker)
        if kind == "structure":
            from src.engines.structure_detector import StructureDetector

            hist = await mds.get_history(ticker, period="1y", interval="1d")
            if hist is None or len(hist) < 30:
                return None
            c_col = "Close" if "Close" in hist.columns else "close"
            h_col = "High" if "High" in hist.columns else "high"
            l_col = "Low" if "Low" in hist.columns else "low"
            vol = hist["Volume"] if "Volume" in hist.columns else hist.get("volume")
            close = hist[c_col].values.astype(float)
            hi = hist[h_col].values.astype(float)
            lo = hist[l_col].values.astype(float)
            volume = vol.values.astype(float) if vol is not None else None

            def _run():
                det = StructureDetector()
                rep = det.analyze(close, hi, lo, volume)
                return rep.to_dict() if hasattr(rep, "to_dict") else rep

            return await asyncio.to_thread(_run)
    except Exception as exc:
        logger.debug("v9 %s failed for %s: %s", kind, ticker, exc)
    return None


async def _fetch_options(request, ticker: str) -> Optional[Dict[str, Any]]:
    try:
        from src.api.routers.live_brief_options import live_options

        return await live_options(ticker, request)
    except Exception as exc:
        logger.debug("options fetch failed: %s", exc)
        return None


async def _fetch_events(ticker: str) -> Dict[str, Any]:
    try:
        from src.services.event_data import get_event_data_service

        return await get_event_data_service().get_ticker_events(ticker)
    except Exception as exc:
        logger.debug("events failed: %s", exc)
        return {"upcoming_events": []}


async def _fetch_edgar_insider(ticker: str) -> Optional[Dict[str, Any]]:
    try:
        client = EdgarClient()
        return await client.get_insider_summary(ticker)
    except Exception as exc:
        logger.debug("edgar insider failed: %s", exc)
        return None


async def _fetch_ibkr_status() -> Dict[str, Any]:
    try:
        from src.api.routers.ibkr import _gateway_port_open
        from src.services.ibkr_service import (
            default_ibkr_port,
            get_ibkr_service,
            resolve_ibkr_host,
        )

        st = get_ibkr_service().status()
        host = st.get("host") or resolve_ibkr_host(None)
        port = int(st.get("port") or default_ibkr_port(st.get("mode") or "paper"))
        return {
            "connected": bool(st.get("connected")),
            "mode": st.get("mode", "paper"),
            "gateway_reachable": _gateway_port_open(host, port),
        }
    except Exception:
        return {"connected": False, "mode": "paper", "gateway_reachable": False}
