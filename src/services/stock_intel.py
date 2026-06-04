"""Aggregate single-stock intelligence for Dossier command center."""

from __future__ import annotations

import asyncio
import logging
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from src.api.deps import sanitize_for_json

logger = logging.getLogger(__name__)

_SUB_FETCH_TIMEOUT_SEC = 12.0
_CORE_DOSSIER_TIMEOUT_SEC = 10.0
_FULL_DOSSIER_TIMEOUT_SEC = 18.0


def _fetch_failed(result: Any, label: str) -> Optional[str]:
    """Return error message when a bounded sub-fetch failed."""
    if isinstance(result, BaseException):
        return str(result)
    if isinstance(result, dict) and result.get("_fetch_error"):
        return str(result.get("detail") or result.get("_fetch_error"))
    return None


async def _await_bounded(coro, timeout_sec: float, label: str):
    """Bound sub-fetch latency so stock-intel does not hang the UI."""
    try:
        return await asyncio.wait_for(coro, timeout=timeout_sec)
    except asyncio.TimeoutError:
        logger.warning("stock-intel sub-fetch timeout: %s (%.0fs)", label, timeout_sec)
        return {
            "_fetch_error": label,
            "detail": f"{label} timed out after {timeout_sec}s",
        }
    except Exception as exc:
        logger.warning("stock-intel sub-fetch failed: %s (%s)", label, exc)
        return {
            "_fetch_error": label,
            "detail": f"{label} failed: {exc}",
        }


async def _minimal_dossier(request, ticker: str) -> Dict[str, Any]:
    """Fast quote-only dossier when full live_dossier is slow or unavailable."""
    mds = request.app.state.market_data
    q_raw = await mds.get_quote(ticker)
    if q_raw is None:
        raise ValueError(f"No quote for {ticker}")
    from src.utils.numeric_parse import coerce_float

    price = coerce_float(q_raw["price"], 0.0)
    change_pct = coerce_float(q_raw.get("change_pct"), 0.0)
    return {
        "symbol": ticker,
        "price": round(price, 2),
        "change_pct": round(change_pct, 2),
        "prev_close": round(price - coerce_float(q_raw.get("change"), 0.0), 2),
        "volume": q_raw.get("volume", 0),
        "technicals": {},
        "why_buy": [],
        "why_stop": [],
        "trade_plan": {},
        "regime": {"should_trade": True},
        "trust": {
            "mode": "RESEARCH",
            "source": "market_data_service",
            "as_of": datetime.now(timezone.utc).isoformat() + "Z",
        },
        "_partial": True,
        "_partial_reason": "quote_only_fallback",
    }


async def _resolve_dossier(
    request,
    ticker: str,
    *,
    timeout_sec: float = _CORE_DOSSIER_TIMEOUT_SEC,
) -> tuple[Dict[str, Any], Dict[str, Optional[str]]]:
    """Fetch dossier with timeout; fall back to minimal quote payload."""
    from src.api.routers.live_dossier import live_dossier

    module_errors: Dict[str, Optional[str]] = {}
    dossier_raw = await _await_bounded(
        live_dossier(ticker, request), timeout_sec, "dossier"
    )
    err = _fetch_failed(dossier_raw, "dossier")
    if err:
        module_errors["dossier"] = err
        try:
            dossier_raw = await _await_bounded(
                _minimal_dossier(request, ticker), 5.0, "dossier_minimal"
            )
            err = _fetch_failed(dossier_raw, "dossier_minimal")
            if err:
                module_errors["dossier_minimal"] = err
                raise ValueError(f"Dossier fetch failed: {module_errors['dossier']}")
        except ValueError:
            raise
        except Exception as exc:
            raise ValueError(f"Dossier fetch failed: {module_errors['dossier']}") from exc
    dossier = dossier_raw if isinstance(dossier_raw, dict) else {}
    if not dossier.get("symbol") and not dossier.get("price"):
        raise ValueError("Dossier returned empty payload")
    return dossier, module_errors


def _build_unified_decision(
    dossier: Dict[str, Any],
    conviction: Optional[Dict[str, Any]],
) -> Dict[str, Any]:
    """Merge dossier verdict heuristics, conviction action, and trade_plan."""
    from src.utils.numeric_parse import coerce_float, normalize_trade_plan, parse_numeric

    regime = dossier.get("regime") or {}
    trade_ok = regime.get("should_trade", True)
    conf = (dossier.get("confidence") or {}).get("final")
    if conf is None:
        conf = (dossier.get("signal") or {}).get("confidence", {}).get("final")
    conflict = ((dossier.get("conflict") or {}).get("conflict_level")
        or (dossier.get("signal") or {}).get("conflict", {}).get("conflict_level")
        or "LOW"
    )
    sect = dossier.get("sector") or dossier.get("signal", {}).get("sector") or {}
    leader = sect.get("leader_status") == "LEADER"
    tp = normalize_trade_plan(dossier.get("trade_plan") or {})
    conf_value = parse_numeric(conf, None) if conf is not None else None

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
    elif conv_action in ("BUY",) or (
        conf_value is not None and conf_value >= 0.7 and conflict == "LOW" and leader
    ):
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
    elif conf_value is not None and conf_value >= 0.55:
        label = "WATCH"
        pill = "pa"
        color = "amber"
        reason_parts.append("Moderate conviction — do not chase.")
    else:
        label = "PASS"
        pill = "pw"
        color = "border"
        reason_parts.append("Insufficient edge for new capital.")

    entry = coerce_float(dossier.get("price"), 0.0)
    stop = tp.get("stop")
    tech = dossier.get("technicals") or {}
    atr = coerce_float(tech.get("atr"), 0.0)
    if not stop and atr > 0 and entry > 0:
        stop = round(entry - 1.5 * atr, 2)

    rr_value = coerce_float(tp.get("rr_ratio"), 0.0)
    if rr_value <= 0 and tp.get("rr_ratio_label"):
        rr_value = coerce_float(tp.get("rr_ratio_label"), 0.0)

    return {
        "label": label,
        "pill": pill,
        "color": color,
        "confidence": round(conf_value, 2) if conf_value is not None else None,
        "reason": " ".join(reason_parts)[:280],
        "entry_zone": tp.get("entry_zone"),
        "stop": stop,
        "target_1r": tp.get("target_1r"),
        "target_2r": tp.get("target_2r"),
        "invalidation": tp.get("invalidation"),
        "rr_ratio": rr_value if rr_value > 0 else None,
        "rr_ratio_display": (
            tp.get("rr_ratio_label")
            if rr_value <= 0 and tp.get("rr_ratio_label")
            else (f"{rr_value:.1f}" if rr_value > 0 else None)
        ),
        "rr_ratio_label": tp.get("rr_ratio_label"),
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

    if not bull:
        price = dossier.get("price")
        if price:
            bull.append(f"Live quote ${price} — research from market data (no engine cycle required).")
        elif dossier.get("_partial"):
            bull.append("Partial quote load — full dossier may still be warming.")
    if not bear:
        bear.append("Confirm structure, regime, and risk before sizing new capital.")

    return {
        "bull_case": bull[:4],
        "bear_case": bear[:4],
        "contradictions": contradictions[:3],
        "one_line_bull": bull[0] if bull else None,
        "one_line_bear": bear[0] if bear else None,
    }


def _catalyst_strip(p9_earnings: Optional[Dict[str, Any]], events: Optional[Dict[str, Any]]) -> Dict[str, Any]:
    items: List[Dict[str, Any]] = []
    earnings_status = "unavailable"
    dividend_status = "unavailable"
    feed_status = "unavailable"

    if p9_earnings:
        if p9_earnings.get("next_earnings_date"):
            earnings_status = "confirmed"
            items.append(
                {
                    "horizon": "30d",
                    "label": "Earnings",
                    "date": p9_earnings.get("next_earnings_date"),
                    "detail": f"Days: {p9_earnings.get('days_to_earnings', '—')}",
                    "severity": "high" if p9_earnings.get("in_blackout") else "medium",
                    "status": "confirmed",
                }
            )
        elif p9_earnings.get("_fetch_error") or p9_earnings.get("error"):
            earnings_status = "delayed"
            items.append(
                {
                    "horizon": "30d",
                    "label": "Earnings",
                    "date": None,
                    "detail": "Earnings feed delayed — retry shortly",
                    "severity": "low",
                    "status": "delayed",
                }
            )
        else:
            items.append(
                {
                    "horizon": "30d",
                    "label": "Earnings",
                    "date": None,
                    "detail": "Earnings date unavailable",
                    "severity": "low",
                    "status": "unavailable",
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
                    "status": "confirmed",
                }
            )
        days = p9_earnings.get("days_to_earnings")
        if days is not None and days > 30 and earnings_status == "confirmed":
            items.append(
                {
                    "horizon": "90d",
                    "label": "Earnings window",
                    "date": p9_earnings.get("next_earnings_date"),
                    "detail": f"~{days} days — plan size reduction",
                    "severity": "medium",
                    "status": "confirmed",
                }
            )
        if p9_earnings.get("dividend_date") or p9_earnings.get("next_dividend_date"):
            dividend_status = "confirmed"
            items.append(
                {
                    "horizon": "90d",
                    "label": "Dividend",
                    "date": p9_earnings.get("dividend_date") or p9_earnings.get("next_dividend_date"),
                    "detail": "Ex-div on calendar",
                    "severity": "low",
                    "status": "confirmed",
                }
            )
    else:
        items.append(
            {
                "horizon": "30d",
                "label": "Earnings",
                "date": None,
                "detail": "Earnings date unavailable",
                "severity": "low",
                "status": "unavailable",
            }
        )

    if dividend_status == "unavailable" and not any(i.get("label") == "Dividend" for i in items):
        items.append(
            {
                "horizon": "90d",
                "label": "Dividend",
                "date": None,
                "detail": "Dividend schedule unavailable",
                "severity": "low",
                "status": "unavailable",
            }
        )

    event_count = 0
    for f in (events or {}).get("filings") or []:
        if isinstance(f, dict) and f.get("form_type") in ("8-K", "10-Q", "10-K"):
            event_count += 1
            items.append(
                {
                    "horizon": "90d",
                    "label": f"SEC {f.get('form_type', 'filing')}",
                    "date": f.get("filed_date") or f.get("filing_date"),
                    "detail": (f.get("description") or "")[:60],
                    "severity": "low",
                    "status": "confirmed",
                }
            )
            if len(items) >= 8:
                break

    if event_count:
        feed_status = "confirmed"
    elif events and (events.get("filings") is not None or events.get("upcoming_events")):
        feed_status = "delayed"
    elif items and any(i.get("status") == "confirmed" for i in items):
        feed_status = "confirmed"

    if feed_status == "unavailable":
        items.append(
            {
                "horizon": "30d",
                "label": "Catalyst feed",
                "date": None,
                "detail": "Catalyst feed unavailable",
                "severity": "low",
                "status": "unavailable",
            }
        )

    catalyst_data_incomplete = (
        earnings_status == "unavailable" and dividend_status == "unavailable"
    )
    unavailable_guidance = None
    if catalyst_data_incomplete:
        unavailable_guidance = (
            "Catalyst data incomplete. Earnings and dividend timing are currently unavailable "
            "in this view. Do not assume event risk is clean; verify the event calendar before "
            "sizing or drafting orders."
        )

    return {
        "items": items[:8],
        "next_label": next((i["label"] for i in items if i.get("status") == "confirmed"), None),
        "earnings_status": earnings_status,
        "dividend_status": dividend_status,
        "feed_status": feed_status,
        "catalyst_data_incomplete": catalyst_data_incomplete,
        "unavailable_guidance": unavailable_guidance,
    }


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
    *,
    unified: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    """Evidence-weighted smart money — not gossip."""
    filings = ownership.get("filings_summary") or []
    insider_data = (conviction or {}).get("insider") or ownership.get("insider") or {}
    insider_sig = "neutral"
    cluster_buy = bool(insider_data.get("cluster_buy"))
    cluster_sell = bool(insider_data.get("cluster_sell"))
    buys_30d = insider_data.get("buys_30d") or insider_data.get("buy_count_30d")
    sells_30d = insider_data.get("sells_30d") or insider_data.get("sell_count_30d")
    buys_90d = insider_data.get("buys_90d") or insider_data.get("buy_count_90d")
    sells_90d = insider_data.get("sells_90d") or insider_data.get("sell_count_90d")

    for f in filings:
        sig = (f.get("signal") or "").upper()
        if sig in ("BULLISH", "BUY", "CLUSTER_BUY"):
            insider_sig = "bullish"
        elif sig in ("BEARISH", "SELL"):
            insider_sig = "bearish"
        if f.get("buys") is not None and buys_30d is None:
            buys_30d = f.get("buys")
        if f.get("sells") is not None and sells_30d is None:
            sells_30d = f.get("sells")

    if cluster_buy:
        insider_sig = "bullish"
    elif cluster_sell:
        insider_sig = "bearish"

    net_30d = None
    if buys_30d is not None or sells_30d is not None:
        net_30d = int(buys_30d or 0) - int(sells_30d or 0)
    net_90d = None
    if buys_90d is not None or sells_90d is not None:
        net_90d = int(buys_90d or 0) - int(sells_90d or 0)

    hf_trend = "unknown"
    sponsor = ownership.get("sponsor") or {}
    overlap = sponsor.get("13f_overlap") or {}
    if overlap.get("matched_sponsors"):
        hf_trend = "notable_holdings_lagged"
    elif sponsor.get("accumulation_score", 0) >= 60:
        hf_trend = "accumulation_lagged"

    opt_label = "no_data"
    if options and isinstance(options, dict):
        grade = options.get("grade") or options.get("quality_grade")
        if grade in ("A", "B"):
            opt_label = "unusual_activity_watch"
        elif grade:
            opt_label = "low_conviction_flow"

    verdict = (unified or {}).get("label", "WATCH").upper()
    thesis_support = "neutral"
    if insider_sig == "bullish" and verdict in ("TRADE", "WATCH"):
        thesis_support = "support"
    elif insider_sig == "bearish" and verdict in ("TRADE", "WATCH"):
        thesis_support = "contradict"
    elif insider_sig == "bearish":
        thesis_support = "contradict"

    def _row(signal: str, status: str, strength: str, timing: str, use: str) -> Dict[str, str]:
        return {"signal": signal, "status": status, "strength": strength, "timing": timing, "use": use}

    support_matrix = [
        _row(
            "Insider Form 4",
            insider_sig if filings or insider_data else "unavailable",
            "cluster_buy" if cluster_buy else ("cluster_sell" if cluster_sell else insider_sig),
            "medium_lag (~2–5d)",
            "supportive_only",
        ),
        _row(
            "13F institutional",
            hf_trend,
            "low" if hf_trend == "unknown" else "medium",
            "stale (~45–90d)",
            "supportive_only",
        ),
        _row(
            "Options flow",
            opt_label,
            "medium" if opt_label == "unusual_activity_watch" else "low",
            "recent",
            "supportive_only",
        ),
        _row(
            "Thesis alignment",
            thesis_support,
            "contextual",
            "now",
            "not_standalone_trigger",
        ),
    ]

    return {
        "summary_headline": "Ownership / Smart Money (supporting only)",
        "guidance": (
            "Ownership and options are secondary context only. Current ownership / smart-money "
            "inputs do not add enough conviction to upgrade the name. Options remain mock / "
            "non-actionable, and ownership signals are supportive at best. Do not use either "
            "as a standalone reason to buy."
        ),
        "insider": insider_sig,
        "insider_30d_net": net_30d,
        "insider_90d_net": net_90d,
        "cluster_buy": cluster_buy,
        "cluster_sell": cluster_sell,
        "hedge_fund_trend": hf_trend,
        "politician_trend": "none",
        "options_flow": opt_label,
        "thesis_support": thesis_support,
        "lag_warning": ownership.get("lag_warning") or "13F filings lag ~45–90 days; commentary ≠ capital",
        "confidence": "medium" if filings else "low",
        "usefulness": "supportive_only — not standalone trigger",
        "support_matrix": support_matrix,
        "sources": [
            {
                "category": "insider",
                "evidence_type": "form_4",
                "signal_quality": "confirmed_filing" if filings else "unavailable",
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
                "category": "options",
                "evidence_type": "market_flow",
                "signal_quality": "live" if options else "unavailable",
                "relevance": "single_stock",
                "timeliness": "recent",
                "bias": opt_label,
            },
        ],
    }


def _price_in_entry_zone(price: float, entry_zone: Any) -> bool:
    """True when mark is inside the trade-plan entry band."""
    from src.utils.numeric_parse import coerce_float

    if not entry_zone or not isinstance(entry_zone, (list, tuple)) or len(entry_zone) < 2:
        return False
    lo = coerce_float(entry_zone[0], 0.0)
    hi = coerce_float(entry_zone[1], 0.0)
    if lo <= 0 or hi <= 0 or price <= 0:
        return False
    return lo <= price <= hi


def _timing_assessment(
    dossier: Dict[str, Any],
    unified: Dict[str, Any],
) -> Dict[str, Any]:
    """Entry-zone vs extension / RSI — separates thesis quality from timing."""
    from src.utils.numeric_parse import coerce_float

    tech = dossier.get("technicals") or {}
    price = coerce_float(dossier.get("price"), 0.0)
    rsi = coerce_float(tech.get("rsi"), None)
    rsi_overheated = rsi is not None and rsi > 70
    rsi_oversold = rsi is not None and rsi < 35
    in_zone = _price_in_entry_zone(price, unified.get("entry_zone"))

    extended = False
    ez = unified.get("entry_zone")
    if ez and len(ez) >= 2 and price > 0:
        hi = coerce_float(ez[1], 0.0)
        if hi > 0 and price > hi * 1.02:
            extended = True
    if tech.get("above_sma50") and rsi_overheated:
        extended = True

    why_buy = dossier.get("why_buy") or []
    thesis_constructive = bool(why_buy) and (
        tech.get("above_sma50") is not False or tech.get("above_sma200") is not False
    )

    return {
        "in_entry_zone": in_zone,
        "rsi": round(rsi, 1) if rsi is not None else None,
        "rsi_overheated": rsi_overheated,
        "rsi_oversold": rsi_oversold,
        "extended": extended,
        "thesis_constructive": thesis_constructive,
        "timing_weak": rsi_overheated or extended or not in_zone,
    }


def _build_why_not_now(
    action_now: str,
    unified: Dict[str, Any],
    timing: Dict[str, Any],
    exec_mode: str,
) -> List[str]:
    """Why-not copy — never claim 'outside zone' when price is inside but timing is weak."""
    if action_now == "AVOID":
        return [unified.get("reason") or "Risk/reward or regime blocks new entry"]
    if action_now != "WAIT":
        return []

    in_zone = timing.get("in_entry_zone")
    extended = timing.get("extended")
    rsi_hot = timing.get("rsi_overheated")

    if in_zone and (extended or rsi_hot):
        parts: List[str] = []
        if extended:
            parts.append("the setup is extended")
        if rsi_hot:
            parts.append("RSI is overheated")
        detail = " and ".join(parts) if parts else "entry quality is still mediocre"
        return [
            "Price is technically within the wider zone, but entry quality is still mediocre "
            f"because {detail}. Prefer a cleaner pullback or stronger confirmation before upgrading."
        ]

    if in_zone:
        return [
            "Price is in the entry zone, but board gate and setup quality do not support "
            "immediate action — wait for confirmation or cleaner timing."
        ]

    if unified.get("entry_zone"):
        return ["Price outside entry zone — wait for pullback into the defined zone."]

    if exec_mode in ("BUY_ON_PULLBACK", "WATCH_CONFIRM"):
        return ["Setup forming — need confirmation or better entry."]

    return [unified.get("reason") or "No actionable trigger yet"]


def _decision_stack_interpretation(
    primary_state: str,
    execution_style: Optional[str],
    board_gate: str,
) -> str:
    if primary_state in ("AVOID", "NO TRADE", "PASS"):
        return "Do not deploy new capital — regime, conflict, or setup quality blocks action."
    if primary_state == "TRADE" and board_gate == "NOW":
        return "Unified thesis, timing, and board gate align — sized entry is justified per plan."
    if primary_state == "WATCH" and board_gate == "WAIT":
        return (
            "The stock is worth monitoring, but current board conditions and setup quality "
            "do not support immediate action."
        )
    if execution_style == "BUY_ON_PULLBACK":
        return (
            "Thesis may be valid on pullback, but the board gate still blocks immediate entry "
            "until timing and confirmation improve."
        )
    return "Monitor the decision stack — conditions may change with price, catalysts, or regime."


def _build_decision_stack(
    unified: Dict[str, Any],
    action_box: Dict[str, Any],
    pm_answer: Dict[str, Any],
    *,
    regime_ok: bool = True,
) -> Dict[str, Any]:
    """Institutional decision stack — primary state, optional execution style, board gate."""
    verdict = (unified.get("label") or "WATCH").upper()
    exec_state = (action_box or {}).get("state") or "WATCH_CONFIRM"
    board_gate = pm_answer.get("action_now") or "WAIT"

    primary_map = {
        "TRADE": "TRADE",
        "BUY": "TRADE",
        "WATCH": "WATCH",
        "AVOID": "AVOID",
        "NO TRADE": "NO TRADE",
        "PASS": "PASS",
    }
    primary_state = primary_map.get(verdict, "WATCH")

    execution_style: Optional[str] = None
    if exec_state in ("BUY_ON_PULLBACK", "BUY_NOW") and primary_state in ("WATCH", "TRADE"):
        execution_style = exec_state
    elif exec_state not in ("AVOID_NOW", "WATCH_CONFIRM") and primary_state != "AVOID":
        execution_style = exec_state

    if not regime_ok:
        board_gate = "AVOID"

    return {
        "primary_state": primary_state,
        "execution_style": execution_style,
        "board_gate": board_gate,
        "interpretation": _decision_stack_interpretation(
            primary_state, execution_style, board_gate
        ),
    }


def _build_confidence_metrics(
    conf_display: Dict[str, Any],
    confluence: Optional[Dict[str, Any]],
    portfolio_fit: Optional[Dict[str, Any]],
) -> Dict[str, Any]:
    """Two-metric confidence model — decision reliability vs thesis quality."""
    cf = int((confluence or {}).get("score") or 0)
    pf = int((portfolio_fit or {}).get("score") or 50)
    thesis_score = round(cf * 0.6 + pf * 0.4) if cf else pf
    thesis_score = max(0, min(100, thesis_score))

    if thesis_score >= 75:
        tlabel = "positive"
    elif thesis_score >= 60:
        tlabel = "neutral-positive"
    elif thesis_score >= 40:
        tlabel = "neutral"
    else:
        tlabel = "weak"

    dc_pct = conf_display.get("confidence_pct")
    if dc_pct is None:
        dc_label = conf_display.get("confidence_label") or "Pending calibration"
    elif dc_pct >= 55:
        dc_label = "calibrated"
    elif dc_pct >= 30:
        dc_label = "low proxy"
    else:
        dc_label = "very low proxy"

    return {
        "decision_confidence": conf_display.get("confidence"),
        "decision_confidence_pct": dc_pct,
        "decision_confidence_label": dc_label,
        "decision_confidence_available": conf_display.get("confidence_available", False),
        "decision_confidence_source": conf_display.get("confidence_source"),
        "thesis_quality": thesis_score,
        "thesis_quality_label": tlabel,
        "thesis_quality_display": f"{thesis_score}/100 {tlabel}",
    }


def _compute_size_shares(
    dossier: Dict[str, Any],
    unified: Dict[str, Any],
    *,
    equity: float = 100_000.0,
    risk_pct: float = 0.01,
) -> Dict[str, Any]:
    """1% risk sizing from entry-zone midpoint vs stop (ATR fallback)."""
    from src.utils.numeric_parse import coerce_float

    ez = unified.get("entry_zone")
    stop = unified.get("stop")
    atr = coerce_float((dossier.get("technicals") or {}).get("atr"), 0.0)

    risk_per_share: Optional[float] = None
    mid: Optional[float] = None
    if ez and len(ez) >= 2:
        mid = (coerce_float(ez[0], 0.0) + coerce_float(ez[1], 0.0)) / 2
        if mid > 0 and stop is not None:
            risk_per_share = abs(mid - coerce_float(stop, 0.0))
    if (not risk_per_share or risk_per_share <= 0) and atr > 0:
        risk_per_share = 1.5 * atr

    shares = 0
    if risk_per_share and risk_per_share > 0:
        shares = max(0, int((equity * risk_pct) / risk_per_share))

    stop_str = f"${coerce_float(stop, 0):.2f}" if stop is not None else "structure stop"
    explanation = (
        f"Size @1% risk: {shares} shares — Based on entry zone midpoint, stop at {stop_str}, "
        "and current paper risk budget."
        if shares
        else "Size unavailable — need entry zone, stop, and ATR."
    )

    return {
        "shares": shares,
        "risk_per_share": round(risk_per_share, 2) if risk_per_share else None,
        "size_explanation": explanation,
        "size_basis": "entry_zone_midpoint_stop_1pct_risk",
        "entry_midpoint": round(mid, 2) if mid else None,
        "sizing_blocked": False,
    }


_RESEARCH_ONLY_LABELS = frozenset(
    {"RESEARCH ONLY", "CONFIRM ONLY", "REFERENCE ONLY", "WATCH ONLY", "PASS"}
)


def _rr_unavailable(unified: Dict[str, Any]) -> bool:
    """True when R:R is missing or not actionable for sizing."""
    from src.utils.numeric_parse import coerce_float

    rr = unified.get("rr_ratio_display")
    if rr is None or rr == "":
        rr = unified.get("rr_ratio")
    if rr is None or rr == "" or rr == "—":
        return True
    if isinstance(rr, str):
        s = rr.strip()
        if s in ("", "—", "null", "None"):
            return True
        if ":" in s or "/" in s:
            parts = s.replace(":", "/").split("/")
            if len(parts) == 2:
                a = coerce_float(parts[0], 0.0)
                b = coerce_float(parts[1], 0.0)
                return not (a > 0 and b > 0)
        return coerce_float(s, 0.0) <= 0
    return coerce_float(rr, 0.0) <= 0


def _blocked_size_info(reason: str) -> Dict[str, Any]:
    return {
        "shares": 0,
        "risk_per_share": None,
        "size_explanation": reason,
        "size_basis": None,
        "entry_midpoint": None,
        "sizing_blocked": True,
    }


def _sizing_block_reason(
    *,
    load_phase: str,
    unified: Dict[str, Any],
    dossier: Dict[str, Any],
    module_errors: Optional[Dict[str, str]] = None,
) -> Optional[str]:
    """Return blocked-copy reason when dossier must not expose actionable sizing."""
    module_errors = module_errors or {}
    if load_phase == "core":
        return "Sizing blocked until live dossier loads"
    if dossier.get("_partial"):
        return "Sizing blocked until live dossier loads"
    trust = dossier.get("trust") or {}
    src = str(trust.get("source") or "")
    if src in ("instant-degraded", "brief-fallback") or "instant-degraded" in src:
        return "Sizing blocked until live dossier loads"
    if module_errors.get("dossier"):
        return "Sizing blocked until live dossier loads"
    label = str(unified.get("label") or "").upper()
    if label in _RESEARCH_ONLY_LABELS:
        return "No sizing guidance in confirm-only mode"
    if _rr_unavailable(unified):
        return "Size unavailable"
    return None


def _apply_sizing_authority(
    size_info: Dict[str, Any],
    *,
    load_phase: str,
    unified: Dict[str, Any],
    dossier: Dict[str, Any],
    module_errors: Optional[Dict[str, str]] = None,
) -> tuple[Dict[str, Any], bool]:
    reason = _sizing_block_reason(
        load_phase=load_phase,
        unified=unified,
        dossier=dossier,
        module_errors=module_errors,
    )
    if reason:
        return _blocked_size_info(reason), True
    return {**size_info, "sizing_blocked": False}, False


def _build_page_summary(
    ticker: str,
    unified: Dict[str, Any],
    decision_stack: Dict[str, Any],
    timing: Dict[str, Any],
) -> str:
    """One-line institutional summary for dossier header."""
    sym = ticker.upper()
    primary = decision_stack.get("primary_state") or "WATCH"

    if primary in ("TRADE", "BUY"):
        return (
            f"{sym} is actionable today — thesis, timing, and board gate align. "
            "Size per plan; do not chase outside the entry zone."
        )
    if primary in ("AVOID", "NO TRADE", "PASS"):
        return (
            f"{sym} is not a buy-quality name right now. "
            f"{unified.get('reason') or 'Regime or setup quality blocks new risk.'}"
        )

    qual = f"{sym} is a watch-quality name, not a buy-quality name right now."
    tail_parts: List[str] = []
    if timing.get("extended"):
        tail_parts.append("the setup is extended")
    if timing.get("rsi_overheated"):
        tail_parts.append("RSI is overheated")

    if timing.get("thesis_constructive") and tail_parts:
        tail = ", ".join(tail_parts)
        return (
            f"{qual} The trend structure is still constructive, but {tail}, and the current "
            "decision stack is not strong enough to justify immediate entry."
        )
    if tail_parts:
        return (
            f"{qual} {tail_parts[0].capitalize()}"
            f"{', ' + ', '.join(tail_parts[1:]) if len(tail_parts) > 1 else ''}, and the current "
            "decision stack is not strong enough to justify immediate entry."
        )
    return (
        f"{qual} "
        f"{decision_stack.get('interpretation') or unified.get('reason') or 'Monitor for a cleaner trigger.'}"
    )


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
    *,
    action_box: Optional[Dict[str, Any]] = None,
    portfolio_fit: Optional[Dict[str, Any]] = None,
    timing: Optional[Dict[str, Any]] = None,
    decision_stack: Optional[Dict[str, Any]] = None,
    size_info: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    """PM answer layer — bull/bear/now/wait/avoid with 30-second card."""
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
    from src.utils.numeric_parse import coerce_float

    if coerce_float(unified.get("rr_ratio"), 0) >= 2.5:
        confirms.append("R:R ≥2.5 on trade plan")
    if (dossier.get("regime") or {}).get("should_trade"):
        confirms.append("Regime gate open")
    if catalysts.get("next_label"):
        confirms.append(f"Catalyst: {catalysts.get('next_label')}")

    action_now = action_map.get(label, "WAIT")
    exec_mode = (action_box or {}).get("state") or "WATCH_CONFIRM"
    pf = portfolio_fit or {}
    pf_score = int(pf.get("score") or 50)
    timing = timing or _timing_assessment(dossier, unified)

    why_not_now = _build_why_not_now(action_now, unified, timing, exec_mode)

    what_buyable: List[str] = []
    if unified.get("entry_zone"):
        ez = unified["entry_zone"]
        what_buyable.append(
            f"Pullback into ${ez[0]}–${ez[1]} with stop ${unified.get('stop') or '—'} and RSI cooling"
        )
    if timing.get("rsi_overheated"):
        what_buyable.append("RSI cools below 60 with price holding structure")
    if confirms:
        what_buyable.append(confirms[0])
    if not what_buyable:
        what_buyable.append("Regime + structure align with defined trade plan")

    watch_to_buy: List[str] = []
    watch_to_avoid: List[str] = []
    if label in ("WATCH", "TRADE"):
        if unified.get("entry_zone"):
            ez = unified["entry_zone"]
            watch_to_buy.append(
                f"Price pulls back into ${ez[0]}–${ez[1]} with volume confirmation"
            )
            watch_to_buy.append("RSI cools from overheated levels while structure holds")
        watch_to_buy.append("Conviction stack upgrades to BUY with flow + insider confirm")
        watch_to_buy.append("Board gate moves WAIT → NOW with conflict staying LOW")
        watch_to_buy.append("Regime gate stays open and catalyst risk clears")
        watch_to_avoid.append(f"Break below stop ${unified.get('stop') or 'structure'}")
        watch_to_avoid.append(
            unified.get("invalidation") or narrative.get("one_line_bear") or "Thesis invalidation on volume"
        )
        watch_to_avoid.append("Regime gate closes or HIGH conflict emerges")
        if catalysts.get("earnings_status") == "confirmed":
            watch_to_avoid.append("Earnings blackout or negative surprise without edge")
        else:
            watch_to_avoid.append("Unverified event risk — confirm calendar before sizing")
    else:
        watch_to_buy.append("Conflict resolves LOW and regime reopens")
        watch_to_buy.append("Fresh base forms with RS vs SPY turning positive")
        watch_to_avoid.append("Chase into extension without pullback")
        watch_to_avoid.append("Crowded flow / late momentum without defined stop")

    catalyst_risk = "low"
    if catalysts.get("unavailable_guidance"):
        catalyst_risk = catalysts.get("unavailable_guidance")
    elif catalysts.get("earnings_status") == "confirmed":
        catalyst_risk = "elevated — earnings on calendar"
    elif catalysts.get("feed_status") == "unavailable":
        catalyst_risk = "unknown — catalyst feed unavailable"

    verdict_line = label
    if timing.get("thesis_constructive") and timing.get("timing_weak") and label == "WATCH":
        verdict_line = "WATCH / Thesis constructive, timing weak"

    size_guidance = pf.get("recommended_sizing_context") or "Standard 0.5–1R starter"
    if label == "WATCH":
        size_guidance = "Starter only if upgraded — not full size"
    elif size_info and size_info.get("size_explanation"):
        size_guidance = size_info["size_explanation"]

    return {
        "bull_case": narrative.get("bull_case") or [],
        "bear_case": narrative.get("bear_case") or [],
        "thesis_breaks": unified.get("invalidation") or narrative.get("one_line_bear"),
        "thesis_confirms": confirms,
        "best_setup_type": setup,
        "investor_fit": "Growth/momentum PM" if setup.startswith("momentum") else "Patient swing",
        "action_now": action_now,
        "execution_mode": exec_mode,
        "verdict": label,
        "scale_in": label == "WATCH",
        "one_line": unified.get("reason"),
        "thirty_second": {
            "verdict": verdict_line,
            "why_not_buy_now": why_not_now[0] if why_not_now else "—",
            "what_makes_buyable": what_buyable[0] if what_buyable else "—",
            "breaks_thesis": unified.get("invalidation") or narrative.get("one_line_bear") or "—",
            "size_guidance": size_guidance,
            "catalyst_risk": catalyst_risk,
            "book_fit": f"{pf_score}/100 · {pf.get('fit_label', 'neutral')}",
        },
        "mind_change": {
            "watch_to_buy": watch_to_buy[:5],
            "watch_to_avoid": watch_to_avoid[:5],
        },
    }


def _build_decision_hierarchy(
    unified: Dict[str, Any],
    action_box: Dict[str, Any],
    pm_answer: Dict[str, Any],
) -> Dict[str, Any]:
    """Chained verdict → execution mode → current action (not parallel equals)."""
    verdict = (unified.get("label") or "WATCH").upper()
    execution_mode = (action_box or {}).get("state") or pm_answer.get("execution_mode") or "WATCH_CONFIRM"
    current_action = pm_answer.get("action_now") or "WAIT"
    exec_labels = {
        "BUY_NOW": "BUY_NOW",
        "BUY_ON_PULLBACK": "BUY_ON_PULLBACK",
        "WATCH_CONFIRM": "WATCH_CONFIRM",
        "AVOID_NOW": "AVOID_NOW",
        "OVEREXTENDED": "OVEREXTENDED",
        "HEDGE_CANDIDATE": "HEDGE_ONLY",
        "CATALYST_WATCH": "CATALYST_WATCH",
    }
    execution_mode = exec_labels.get(execution_mode, execution_mode)
    return {
        "verdict": verdict,
        "execution_mode": execution_mode,
        "current_action": current_action,
        "chain_summary": f"{verdict} → {execution_mode} → {current_action}",
        "verdict_reason": unified.get("reason"),
        "execution_reason": (action_box or {}).get("reason"),
        "action_reason": pm_answer.get("one_line"),
    }


def _resolve_confidence_display(
    unified: Dict[str, Any],
    dossier: Dict[str, Any],
    confluence: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    """Never surface 0% when confidence is unknown — map confluence when possible."""
    from src.utils.numeric_parse import parse_numeric

    raw = unified.get("confidence")
    conf_value = parse_numeric(raw, None) if raw is not None else None

    if conf_value is None or conf_value == 0:
        doss_conf = (dossier.get("confidence") or {}).get("final")
        if doss_conf is None:
            doss_conf = (dossier.get("signal") or {}).get("confidence", {}).get("final")
        if doss_conf is not None:
            conf_value = parse_numeric(doss_conf, None)

    source = "dossier"
    if (conf_value is None or conf_value == 0) and confluence:
        cf_score = confluence.get("score")
        if cf_score and cf_score > 0:
            conf_value = cf_score / 100.0
            source = "confluence"

    if conf_value is None or conf_value == 0:
        return {
            "confidence": None,
            "confidence_pct": None,
            "confidence_label": "Pending calibration",
            "confidence_available": False,
            "confidence_source": None,
        }

    if conf_value > 1:
        pct = round(conf_value)
        norm = conf_value / 100.0
    else:
        pct = round(conf_value * 100)
        norm = conf_value

    label = "Calibrated" if pct >= 55 else "Low conviction"
    if source == "confluence":
        label = f"Confluence proxy ({pct}%)"

    return {
        "confidence": round(norm, 2),
        "confidence_pct": pct,
        "confidence_label": label,
        "confidence_available": True,
        "confidence_source": source,
    }


def _peer_context(
    dossier: Dict[str, Any],
    peers: Any,
    conviction: Optional[Dict[str, Any]],
) -> Dict[str, Any]:
    """Peer-relative context for institutional dossier."""
    sect = dossier.get("sector") or dossier.get("signal", {}).get("sector") or {}
    rs_spy = None
    if conviction:
        rs_spy = conviction.get("relative_strength_vs_spy_pct")

    peer_rows = []
    self_rank = None
    if isinstance(peers, dict):
        peer_rows = peers.get("rankings") or peers.get("table") or []
        ticker = (dossier.get("symbol") or "").upper()
        for i, row in enumerate(peer_rows):
            if (row.get("ticker") or "").upper() == ticker or row.get("is_self"):
                self_rank = i + 1
                break

    return {
        "vs_sector_etf": sect.get("sector") or sect.get("name") or "Sector ETF — unavailable",
        "sector_rs": sect.get("rs_vs_sector"),
        "vs_index": "SPY",
        "rs_vs_spy_pct": rs_spy,
        "peer_count": len(peer_rows),
        "peer_rank": self_rank,
        "peer_verdict": (peers or {}).get("verdict") if isinstance(peers, dict) else None,
        "stronger_peer": (peers or {}).get("stronger_peer") if isinstance(peers, dict) else None,
        "weaker_peer": (peers or {}).get("weaker_peer") if isinstance(peers, dict) else None,
        "has_data": bool(peer_rows or rs_spy is not None),
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


def _trade_plan_human(
    trade_plan: Dict[str, Any],
    unified: Dict[str, Any],
) -> List[Dict[str, str]]:
    """Human-readable trade plan rows for dossier UI."""
    from src.utils.numeric_parse import coerce_float

    tp = trade_plan or {}
    ez = tp.get("entry_zone") or unified.get("entry_zone")
    entry_label = f"${ez[0]}–${ez[1]}" if ez and len(ez) >= 2 else "—"
    stop = tp.get("stop") or unified.get("stop")
    t1 = tp.get("target_1r") or unified.get("target_1r")
    t2 = tp.get("target_2r") or unified.get("target_2r")
    risk_per_share = None
    if stop and ez:
        mid = (coerce_float(ez[0], 0) + coerce_float(ez[1], 0)) / 2
        if mid > 0 and stop:
            risk_per_share = round(abs(mid - coerce_float(stop, 0)), 2)

    rows = [
        {"label": "Entry zone", "value": entry_label},
        {"label": "Stop", "value": f"${stop}" if stop else "—"},
        {"label": "T1 / T2", "value": f"${t1} / ${t2}" if t1 and t2 else "—"},
        {
            "label": "Risk/share",
            "value": f"${risk_per_share}" if risk_per_share else "—",
        },
        {
            "label": "R:R",
            "value": str(
                unified.get("rr_ratio_display")
                or unified.get("rr_ratio")
                or tp.get("rr_ratio_label")
                or "—"
            ),
        },
        {
            "label": "Invalidation",
            "value": str(tp.get("invalidation") or unified.get("invalidation") or "—"),
        },
        {
            "label": "Note",
            "value": _dossier_trade_plan_note_value(tp, unified),
        },
    ]
    return rows


def _dossier_trade_plan_note_value(
    trade_plan: Dict[str, Any],
    unified: Dict[str, Any],
) -> str:
    from src.services.fetch_surface_state import dossier_trade_plan_note

    tp = trade_plan or {}
    ez = tp.get("entry_zone") or unified.get("entry_zone")
    has_entry = bool(ez and len(ez) >= 2)
    stop = tp.get("stop") or unified.get("stop")
    t1 = tp.get("target_1r") or unified.get("target_1r")
    t2 = tp.get("target_2r") or unified.get("target_2r")
    levels_blank = not (has_entry or stop or t1 or t2)
    label_upper = str(unified.get("label") or "").upper()
    research_only = label_upper in _RESEARCH_ONLY_LABELS
    return dossier_trade_plan_note(
        note=str(tp.get("note") or ""),
        setup_type=str(tp.get("setup_type") or ""),
        research_only=research_only,
        levels_blank=levels_blank,
    )


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


async def _fetch_enrichments_parallel(request, ticker: str) -> Dict[str, Any]:
    """Slow enrichment modules — each fails independently."""
    from src.api.routers.conviction import stock_conviction as _conviction_endpoint
    from src.api.routers.dossier import peer_comparison

    mds = request.app.state.market_data
    results = await asyncio.gather(
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

    module_errors: Dict[str, str] = {}
    labels = (
        "conviction",
        "peers",
        "p9_fundamentals",
        "p9_earnings",
        "p9_structure",
        "options",
        "events",
        "edgar_insider",
        "ibkr_status",
    )

    def _unwrap(idx: int, default: Any) -> Any:
        r = results[idx]
        err = _fetch_failed(r, labels[idx])
        if err:
            module_errors[labels[idx]] = err
            return default
        if isinstance(r, Exception):
            module_errors[labels[idx]] = str(r)
            return default
        return r

    return {
        "module_errors": module_errors,
        "conviction": _unwrap(0, None),
        "peers": _unwrap(1, {"rankings": []}),
        "p9": {
            "fundamentals": _unwrap(2, None),
            "earnings": _unwrap(3, None),
            "structure": _unwrap(4, None),
        },
        "options": _unwrap(5, None),
        "events": _unwrap(6, {}),
        "edgar_insider": _unwrap(7, None),
        "ibkr": _unwrap(8, {"connected": False, "mode": "paper"}),
    }


async def _build_intel_payload(
    request,
    ticker: str,
    dossier: Dict[str, Any],
    *,
    conviction: Any = None,
    peers: Any = None,
    p9: Optional[Dict[str, Any]] = None,
    options: Any = None,
    events: Any = None,
    edgar_insider: Any = None,
    ibkr: Optional[Dict[str, Any]] = None,
    module_errors: Optional[Dict[str, str]] = None,
    load_phase: str = "full",
    include_flow: bool = True,
) -> Dict[str, Any]:
    """Assemble stock-intel response from dossier core and enrichment modules."""
    from src.api.live_state import fetch_regime_state
    from src.services.confluence_engine import build_confluence
    from src.services.decision_bar import bar_from_stock
    from src.services.pm_memory import build_thesis_block, get_memory
    from src.services.portfolio_fit import build_portfolio_fit
    from src.services.thesis_drift import build_thesis_drift
    from src.utils.numeric_parse import normalize_trade_plan

    p9 = p9 or {"fundamentals": None, "earnings": None, "structure": None}
    events = events if isinstance(events, dict) else {}
    ibkr = ibkr or {"connected": False, "mode": "paper"}
    module_errors = dict(module_errors or {})

    dossier = dict(dossier)
    dossier["_p9"] = p9
    if dossier.get("trade_plan"):
        dossier["trade_plan"] = normalize_trade_plan(dossier["trade_plan"])
    unified = _build_unified_decision(dossier, conviction if isinstance(conviction, dict) else None)
    narrative = _narrative_structured(
        dossier, conviction if isinstance(conviction, dict) else None
    )
    catalysts = _catalyst_strip(p9.get("earnings"), events)
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

    sect_name = identity.get("sector") if (identity := _identity_layer(dossier, peers)) else None
    portfolio_fit = build_portfolio_fit(ticker, positions, sector=sect_name)
    fundamentals_block = _fundamentals_block(p9.get("fundamentals"), dossier)
    peers_block = _peers_block(peers)
    options_block = _options_block(options, unified=unified)

    flow_intel = None
    if include_flow:
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
                options_block = _options_block(
                    options, unified=unified, flow_intel=flow_intel
                )
        except Exception as exc:
            logger.debug("ticker flow intel skipped for %s: %s", ticker, exc)
            module_errors["flow_intel"] = str(exc)[:120]

    action_box = _build_institutional_action_box(
        unified=unified,
        pm_answer={},  # placeholder — rebuilt below
        regime=regime,
        portfolio_fit=portfolio_fit,
        options_block=options_block,
        flow_intel=flow_intel,
        catalysts=catalysts,
    )

    timing = _timing_assessment(dossier, unified)
    equity = sum(float(p.get("market_value") or 0) for p in positions) or 100_000.0
    if equity < 10_000:
        equity = 100_000.0
    size_info = _compute_size_shares(dossier, unified, equity=equity)
    decision_stack = _build_decision_stack(
        unified,
        action_box,
        {"action_now": "WAIT" if unified.get("label") == "WATCH" else "NOW"},
        regime_ok=regime.should_trade,
    )

    pm_answer = _pm_answer_layer(
        unified,
        narrative,
        dossier,
        catalysts,
        action_box=action_box,
        portfolio_fit=portfolio_fit,
        timing=timing,
        decision_stack=decision_stack,
        size_info=size_info,
    )
    action_box = _build_institutional_action_box(
        unified=unified,
        pm_answer=pm_answer,
        regime=regime,
        portfolio_fit=portfolio_fit,
        options_block=options_block,
        flow_intel=flow_intel,
        catalysts=catalysts,
    )
    decision_stack = _build_decision_stack(
        unified,
        action_box,
        pm_answer,
        regime_ok=regime.should_trade,
    )

    smart_money = _smart_money_summary(
        ownership, options, conviction, unified=unified
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
    thesis = build_thesis_block(
        ticker,
        {"narrative": narrative, "pm_answer": pm_answer, "unified_decision": unified},
    )
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

    conf_display = _resolve_confidence_display(unified, dossier, confluence)
    confidence_metrics = _build_confidence_metrics(conf_display, confluence, portfolio_fit)
    unified = {**unified, **conf_display, **confidence_metrics}

    from src.services.cost_adjusted_edge import compute_net_edge
    from src.services.random_walk_guardrails import build_random_walk_guardrails

    raw_for_edge = float(
        unified.get("validated_score")
        or unified.get("score")
        or confidence_metrics.get("thesis_quality", 50) / 10.0
    )
    if raw_for_edge > 10:
        raw_for_edge = raw_for_edge / 10.0
    cost_edge = compute_net_edge(
        raw_for_edge,
        turnover_burden=0.22 if timing.get("timing_weak") else 0.16,
        spread_burden=0.32 if timing.get("extended") else 0.16,
        action=unified.get("label"),
        extended=bool(timing.get("extended")),
        partial_data=bool(dossier.get("_partial")) or bool(module_errors),
    )
    confidence_metrics = {
        **confidence_metrics,
        "raw_score": cost_edge["raw_score"],
        "net_deploy_score": cost_edge["net_deploy_score"],
        "net_edge_display": cost_edge["display"],
        "cost_edge_detail": cost_edge,
    }
    unified = {**unified, **cost_edge}

    layers_preview = {
        "identity": bool(identity),
        "fundamentals": bool(p9.get("fundamentals") or fundamentals_block),
        "technicals": bool(dossier.get("technicals")),
        "peers": bool(peers_block.get("rows")),
        "options": bool(options_block.get("has_data")),
        "smart_money": bool(smart_money),
    }
    random_walk_guardrails = build_random_walk_guardrails(
        ticker=ticker,
        dossier=dossier,
        unified=unified,
        timing=timing,
        confluence=confluence,
        portfolio_fit=portfolio_fit,
        options_block=options_block,
        smart_money=smart_money,
        confidence_metrics=confidence_metrics,
        conf_display=conf_display,
        layers=layers_preview,
        module_errors=module_errors,
        narrative=narrative,
        peers_block=peers_block,
        regime_ok=regime.should_trade,
    )
    decision_hierarchy = _build_decision_hierarchy(unified, action_box, pm_answer)
    page_summary = _build_page_summary(ticker, unified, decision_stack, timing)
    peer_context = _peer_context(dossier, peers, conviction if isinstance(conviction, dict) else None)
    trade_plan_human = _trade_plan_human(dossier.get("trade_plan") or {}, unified)

    from src.services.candlestick_context import build_candlestick_analysis

    candlestick_analysis = build_candlestick_analysis(
        dossier,
        unified=unified,
        regime={"label": regime.regime, "should_trade": regime.should_trade},
    )

    from src.services.crisis_regime import build_crisis_context
    from src.services.buffett_judgment import build_buffett_owner_view
    from src.services.decision_quality_naval import build_naval_thinking
    from src.services.principles_engine import build_principles_memo

    crisis_context = build_crisis_context(
        ticker=ticker,
        regime=regime,
        dossier=dossier,
        unified=unified,
    )
    naval_thinking = build_naval_thinking(
        ticker=ticker,
        dossier=dossier,
        unified=unified if isinstance(unified, dict) else {},
        regime={"tradeability": getattr(regime, "tradeability", None), "should_trade": regime.should_trade},
    )
    buffett_owner_view = build_buffett_owner_view(
        ticker=ticker,
        dossier=dossier,
        unified=unified if isinstance(unified, dict) else {},
        fundamentals_block=fundamentals_block if isinstance(fundamentals_block, dict) else None,
        regime={"tradeability": getattr(regime, "tradeability", None), "should_trade": regime.should_trade},
    )
    principles_memo = build_principles_memo(
        ticker=ticker,
        dossier=dossier,
        unified=unified if isinstance(unified, dict) else {},
        regime={"tradeability": getattr(regime, "tradeability", None), "should_trade": regime.should_trade},
    )

    partial = bool(dossier.get("_partial")) or bool(module_errors)
    size_info, sizing_blocked = _apply_sizing_authority(
        size_info,
        load_phase=load_phase,
        unified=unified,
        dossier=dossier,
        module_errors=module_errors,
    )
    label_upper = str(unified.get("label") or "").upper()
    research_only = bool(
        sizing_blocked
        or partial
        or load_phase == "core"
        or label_upper in _RESEARCH_ONLY_LABELS
        or dossier.get("_partial")
    )
    return sanitize_for_json(
        {
            "ticker": ticker,
            "as_of": datetime.now(timezone.utc).isoformat() + "Z",
            "load_phase": load_phase,
            "partial": partial,
            "research_only": research_only,
            "sizing_blocked": sizing_blocked,
            "module_errors": module_errors,
            "page_summary": page_summary,
            "decision_stack": decision_stack,
            "confidence_metrics": confidence_metrics,
            "random_walk_guardrails": random_walk_guardrails,
            "size_info": size_info,
            "timing": timing,
            "decision_bar": decision_bar,
            "decision_hierarchy": decision_hierarchy,
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
            "peer_context": peer_context,
            "trade_plan_human": trade_plan_human,
            "candlestick_analysis": candlestick_analysis,
            "crisis_context": crisis_context,
            "naval_thinking": naval_thinking,
            "buffett_owner_view": buffett_owner_view,
            "principles_memo": principles_memo,
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


async def build_stock_intel_enrichments(request, ticker: str) -> Dict[str, Any]:
    """Enrichment-only payload for async second-phase dossier load."""
    ticker = ticker.strip().upper()
    if not ticker:
        raise ValueError("Ticker required")
    enrich = await _fetch_enrichments_parallel(request, ticker)
    return sanitize_for_json(
        {
            "ticker": ticker,
            "load_phase": "enrichments",
            "as_of": datetime.now(timezone.utc).isoformat() + "Z",
            "module_errors": enrich.get("module_errors") or {},
            "conviction": enrich.get("conviction"),
            "peers": enrich.get("peers"),
            "p9": enrich.get("p9"),
            "options": enrich.get("options"),
            "events": enrich.get("events"),
            "edgar_insider": enrich.get("edgar_insider"),
            "ibkr": enrich.get("ibkr"),
        }
    )


async def build_stock_intel(
    request,
    ticker: str,
    *,
    lite: bool = False,
    enrichments_only: bool = False,
) -> Dict[str, Any]:
    """Single-call aggregate for Dossier UI (core, enrichments, or full)."""
    ticker = ticker.strip().upper()
    if not ticker:
        raise ValueError("Ticker required")

    if enrichments_only:
        return await build_stock_intel_enrichments(request, ticker)

    dossier_timeout = _CORE_DOSSIER_TIMEOUT_SEC if lite else _FULL_DOSSIER_TIMEOUT_SEC
    dossier, module_errors = await _resolve_dossier(
        request, ticker, timeout_sec=dossier_timeout
    )

    if lite:
        return await _build_intel_payload(
            request,
            ticker,
            dossier,
            module_errors=module_errors,
            load_phase="core",
            include_flow=False,
        )

    enrich = await _fetch_enrichments_parallel(request, ticker)
    module_errors.update(enrich.get("module_errors") or {})

    return await _build_intel_payload(
        request,
        ticker,
        dossier,
        conviction=enrich.get("conviction"),
        peers=enrich.get("peers"),
        p9=enrich.get("p9"),
        options=enrich.get("options"),
        events=enrich.get("events"),
        edgar_insider=enrich.get("edgar_insider"),
        ibkr=enrich.get("ibkr"),
        module_errors=module_errors,
        load_phase="full",
        include_flow=True,
    )


def _fundamentals_block(
    raw: Optional[Dict[str, Any]],
    dossier: Dict[str, Any],
) -> Dict[str, Any]:
    """Structured fundamental intelligence."""
    flags: List[str] = []
    if raw:
        pe = raw.get("pe_ratio") or raw.get("trailingPE")
        from src.utils.numeric_parse import coerce_float

        if pe and coerce_float(pe, 0) > 40:
            flags.append("rich_valuation")
        growth = raw.get("revenue_growth") or raw.get("revenueGrowth")
        if growth and coerce_float(growth, 0) < 0:
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


def _options_block(
    options: Optional[Dict[str, Any]],
    *,
    unified: Optional[Dict[str, Any]] = None,
    flow_intel: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    """Options intelligence with feed state and thesis alignment."""
    if not options or not isinstance(options, dict):
        feed_state = "unavailable"
        if flow_intel and flow_intel.get("synthetic"):
            feed_state = "mock"
        elif flow_intel and flow_intel.get("top"):
            feed_state = "live"
        return {
            "has_data": bool(flow_intel and flow_intel.get("top")),
            "feed_state": feed_state,
            "flow_quality_score": 0,
            "classification": "no_data",
            "actionable": False,
            "use_label": "NOT_ACTIONABLE",
            "guidance": (
                "Options remain mock / non-actionable in this view. Do not use flow as a "
                "standalone reason to buy."
            ),
            "thesis_alignment": "neutral",
            "call_put_bias": "unknown",
            "iv_note": "IV data unavailable",
            "vol_oi_note": "Volume/OI unavailable",
        }

    grade = options.get("grade") or options.get("quality_grade") or "—"
    feed_state = "delayed"
    if flow_intel and flow_intel.get("synthetic"):
        feed_state = "mock"
    elif flow_intel and flow_intel.get("top"):
        feed_state = "live"

    pc_ratio = options.get("put_call_ratio") or options.get("skew")
    call_put_bias = "neutral"
    if pc_ratio is not None:
        try:
            pcr = float(pc_ratio)
            call_put_bias = "put_heavy" if pcr > 1.1 else "call_heavy" if pcr < 0.9 else "balanced"
        except (TypeError, ValueError):
            pass

    verdict = (unified or {}).get("label", "WATCH").upper()
    thesis_alignment = "supportive_only"
    if grade in ("A", "B"):
        thesis_alignment = "confirm" if verdict in ("TRADE", "WATCH") else "neutral"
    elif grade in ("D", "F"):
        thesis_alignment = "contradict"

    top = (flow_intel or {}).get("top") or {}
    flow_action = top.get("pm_action") or ""
    if flow_action in ("AVOID_CHASE", "LIKELY_HEDGING_FLOW", "HEDGE_NO_EDGE"):
        thesis_alignment = "contradict"

    iv_rank = options.get("iv_rank") or options.get("iv_percentile")
    iv_note = f"IV rank {iv_rank}" if iv_rank is not None else "IV rank unavailable"

    contracts = options.get("contracts") or []
    vol_oi_note = "Volume/OI unavailable"
    if contracts:
        top_c = contracts[0] if isinstance(contracts[0], dict) else {}
        vol_oi_note = f"Sample OI {top_c.get('oi', '—')} · vol {top_c.get('volume', '—')}"

    actionable = feed_state == "live" and not (flow_intel or {}).get("synthetic")
    opt_guidance = (
        "Options flow is supportive context only — not a standalone trigger."
        if actionable
        else "Options remain mock / non-actionable in this view. Do not use flow as a "
        "standalone reason to buy."
    )

    return {
        "has_data": True,
        "feed_state": feed_state,
        "iv_percentile": options.get("iv_percentile"),
        "iv_rank": options.get("iv_rank"),
        "put_call_skew": pc_ratio,
        "call_put_bias": call_put_bias,
        "unusual_volume": options.get("unusual_activity"),
        "leaps_note": options.get("leaps_accumulation"),
        "flow_quality_score": 70 if grade in ("A", "B") else 40,
        "classification": (
            "directional_conviction"
            if grade in ("A", "B")
            else "short_dated_noise"
        ),
        "expected_move": options.get("expected_move"),
        "iv_note": iv_note,
        "vol_oi_note": vol_oi_note,
        "thesis_alignment": thesis_alignment,
        "actionable": actionable,
        "guidance": opt_guidance,
        "use_label": "ACTIONABLE" if actionable else "NOT_ACTIONABLE — supportive only",
        "raw_summary": options.get("summary") or options.get("headline"),
        "flow_pm_action": top.get("pm_action"),
        "flow_grade": top.get("quality_grade"),
        "flow_synthetic": top.get("synthetic") or (flow_intel or {}).get("synthetic"),
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
        from src.services.ibkr_service import get_ibkr_service

        st = get_ibkr_service().status()
        return {
            "connected": bool(st.get("connected")),
            "mode": st.get("mode", "paper"),
            "gateway_reachable": bool(st.get("gateway_reachable")),
        }
    except Exception:
        return {"connected": False, "mode": "paper", "gateway_reachable": False}
