"""Single-stock institutional conviction stack — honest, layered evidence."""

from __future__ import annotations

import logging
from typing import Any, Dict, List

from fastapi import APIRouter, HTTPException, Request

from src.api.deps import sanitize_for_json
from src.engines.options_flow_radar import OptionsFlowRadar
from src.services.event_data import get_event_data_service
from src.services.options_flow_mock import MockOptionsFlowProvider
from src.services.options_flow_polygon import PolygonOptionsFlowProvider

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/v1/conviction", tags=["conviction"])


def _options_provider():
    import os

    mode = (os.getenv("OPTIONS_RADAR_PROVIDER") or "auto").strip().lower()
    if mode == "mock":
        return MockOptionsFlowProvider()
    if os.getenv("POLYGON_API_KEY", "").strip():
        return PolygonOptionsFlowProvider()
    return MockOptionsFlowProvider()


def _classify_action(
    *,
    technical_ok: bool,
    options_support: bool,
    insider_bullish: bool,
    regime_ok: bool,
) -> str:
    score = sum(
        [
            2 if technical_ok else 0,
            1 if options_support else 0,
            1 if insider_bullish else 0,
            1 if regime_ok else 0,
        ]
    )
    if not regime_ok:
        return "NO_TOUCH"
    if score >= 4:
        return "BUY"
    if score >= 2:
        return "WATCH"
    if score <= 1 and not technical_ok:
        return "AVOID"
    return "WAIT"


async def _load_edgar_sponsor(ticker: str) -> tuple[Dict[str, Any], Dict[str, Any], bool]:
    """Return insider_block, sponsor_block, sponsor_bullish from SEC EDGAR."""
    from src.ingestors.edgar import EdgarClient
    from src.services.sponsor_index import lookup_13f_sponsor_overlap

    edgar = EdgarClient()
    sponsor_13f = await lookup_13f_sponsor_overlap(ticker)
    insider_summary = await edgar.get_insider_summary(ticker)
    recent_filings = await edgar.get_recent_filings(ticker, limit=8)
    filing_dicts = [
        f.to_dict() if hasattr(f, "to_dict") else f for f in recent_filings
    ]

    signal = insider_summary.get("signal", "NEUTRAL")
    buy_f = int(insider_summary.get("buy_filings") or 0)
    sell_f = int(insider_summary.get("sell_filings") or 0)

    insider_block: Dict[str, Any] = {
        "transactions": [],
        "sentiment": {
            "signal": signal.lower().replace("insider_", ""),
            "buys": buy_f,
            "sells": sell_f,
            "form4_count": insider_summary.get("form4_filings", 0),
        },
        "cluster_buy": signal == "INSIDER_BUYING",
        "trust": {
            "source": "sec_edgar",
            "mode": "delayed",
            "note": insider_summary.get("note"),
        },
    }

    accum = 0
    if signal == "INSIDER_BUYING":
        accum += 40
    elif signal == "NEUTRAL":
        accum += 15
    if buy_f > sell_f:
        accum += min(30, (buy_f - sell_f) * 10)
    recent_8k = sum(
        1
        for f in filing_dicts
        if str(f.get("form_type", "")).upper() in ("8-K", "SC 13D", "SC 13G")
    )
    if recent_8k:
        accum += min(20, recent_8k * 10)

    matched = list(sponsor_13f.get("matched_sponsors") or [])
    tier_a = int(sponsor_13f.get("tier_a_count") or 0)
    if matched:
        accum += min(35, len(matched) * 8 + tier_a * 5)
    crowding = sponsor_13f.get("crowding_risk") or "unknown"

    sponsor_block: Dict[str, Any] = {
        "status": "ok" if matched else "partial",
        "recent_filings": filing_dicts[:5],
        "insider_signal": signal,
        "form4_activity": insider_summary,
        "accumulation_score": min(100, accum),
        "crowding_risk": crowding,
        "13f_overlap": {
            "sponsor_count": len(matched),
            "tier_a_count": tier_a,
            "matched_sponsors": matched[:8],
            "filing_hits": sponsor_13f.get("filing_hits", 0),
        },
        "trust": {
            "source": "sec_edgar",
            "mode": "delayed",
            **(sponsor_13f.get("trust") or {}),
        },
        "message": (
            f"Form 4 + filings + {len(matched)} curated 13F sponsor match(es)."
            if matched
            else "Form 4 + filings only — no curated 13F sponsor overlap in last ~6mo."
        ),
    }
    sponsor_bullish = (
        signal == "INSIDER_BUYING"
        or accum >= 55
        or (tier_a >= 1 and len(matched) >= 2)
    )
    return insider_block, sponsor_block, sponsor_bullish


@router.get("/{ticker}")
async def stock_conviction(ticker: str, request: Request) -> Dict[str, Any]:
    """Unified conviction layer for one name (technical + flow + insider + regime)."""
    ticker = ticker.upper().strip()
    if not ticker or len(ticker) > 12:
        raise HTTPException(400, "Invalid ticker")

    mds = getattr(request.app.state, "market_data", None)
    regime_ok = True
    regime_label = "UNKNOWN"
    try:
        regime_service = getattr(request.app.state, "regime_service", None)
        if regime_service is not None:
            regime_payload = await regime_service.get()
            regime_label = (
                regime_payload.get("label")
                or regime_payload.get("trend")
                or "UNKNOWN"
            )
            regime_ok = bool(regime_payload.get("should_trade", True))
    except Exception:
        logger.debug("conviction regime fetch failed", exc_info=True)

    technical_ok = False
    rs_vs_spy: float | None = None
    price: float | None = None
    if mds is not None:
        try:
            hist = await mds.get_history(ticker, period="6mo", interval="1d")
            if hist is not None and not hist.empty and len(hist) >= 50:
                c_col = "Close" if "Close" in hist.columns else "close"
                close = hist[c_col].astype(float)
                price = float(close.iloc[-1])
                sma50 = float(close.tail(50).mean())
                technical_ok = price > sma50
                spy = await mds.get_history("SPY", period="6mo", interval="1d")
                if spy is not None and not spy.empty:
                    spy_c = spy[c_col].astype(float)
                    if len(spy_c) >= 20 and len(close) >= 20:
                        stock_ret = float(close.iloc[-1] / close.iloc[-21] - 1)
                        spy_ret = float(spy_c.iloc[-1] / spy_c.iloc[-21] - 1)
                        rs_vs_spy = round((stock_ret - spy_ret) * 100, 2)
        except Exception:
            logger.debug("conviction technicals failed for %s", ticker, exc_info=True)

    options_block: Dict[str, Any] = {
        "status": "unavailable",
        "candidates": [],
        "top_grade": None,
        "confirmation": False,
        "trust": {"message": "Options radar unavailable"},
    }
    try:
        radar = OptionsFlowRadar(_options_provider())
        snap = await radar.scan([ticker], limit=5, min_grade="C")
        candidates: List[Dict[str, Any]] = list(snap.candidates or [])
        top = candidates[0] if candidates else None
        options_block = {
            "status": snap.status,
            "candidates": candidates,
            "top_grade": top.get("quality_grade") if top else None,
            "confirmation": bool(
                top
                and top.get("quality_grade") in ("A", "B")
                and top.get("action_label") in ("IDEA", "SUPPORTING_EVIDENCE")
            ),
            "trust": snap.trust,
        }
    except Exception as exc:
        options_block["trust"] = {"message": f"Options scan error: {exc}"}

    sponsor_bullish = False
    try:
        insider_block, sponsor_block, sponsor_bullish = await _load_edgar_sponsor(
            ticker
        )
    except Exception as exc:
        logger.warning("conviction edgar fetch failed for %s: %s", ticker, exc)
        insider_block = {
            "transactions": [],
            "sentiment": None,
            "cluster_buy": False,
            "trust": {"source": "sec_edgar", "mode": "unavailable", "message": str(exc)},
        }
        sponsor_block = {
            "status": "unavailable",
            "recent_filings": [],
            "insider_signal": None,
            "accumulation_score": 0,
            "crowding_risk": None,
            "trust": {"source": "sec_edgar", "mode": "unavailable", "message": str(exc)},
            "message": "EDGAR fetch failed — sponsor layer degraded.",
        }
        try:
            events = await get_event_data_service().get_ticker_events(ticker)
            insider_block["transactions"] = events.get("insider_transactions") or []
            insider_block["sentiment"] = events.get("insider_sentiment")
            sentiment = events.get("insider_sentiment") or {}
            insider_block["cluster_buy"] = sentiment.get("signal") == "bullish"
            sponsor_bullish = insider_block["cluster_buy"]
        except Exception:
            pass

    action = _classify_action(
        technical_ok=technical_ok,
        options_support=bool(options_block.get("confirmation")),
        insider_bullish=bool(insider_block.get("cluster_buy") or sponsor_bullish),
        regime_ok=regime_ok,
    )

    why_now: List[str] = []
    why_not: List[str] = []
    if technical_ok:
        why_now.append("Price above 50-day — trend structure intact")
    else:
        why_not.append("Below 50-day — weak technical structure")
    if options_block.get("confirmation"):
        why_now.append(
            f"Options flow confirmation (grade {options_block.get('top_grade')})"
        )
    elif options_block.get("candidates"):
        why_not.append("Options flow present but below confirmation threshold")
    if insider_block.get("cluster_buy"):
        why_now.append("Recent insider buy cluster (SEC Form 4)")
    elif (insider_block.get("sentiment") or {}).get("signal") in (
        "bearish",
        "selling",
    ):
        why_not.append("Insider selling dominates recent Form 4 filings")
    if sponsor_block.get("accumulation_score", 0) >= 55:
        why_now.append(
            "Sponsor/accumulation score "
            f"{sponsor_block.get('accumulation_score')} (SEC filings)"
        )
    overlap = (sponsor_block.get("13f_overlap") or {}).get("matched_sponsors") or []
    if overlap:
        names = ", ".join(m.get("name", "") for m in overlap[:3])
        why_now.append(f"Curated 13F sponsor overlap: {names}")
    elif sponsor_block.get("status") == "partial":
        why_not.append(sponsor_block.get("message", ""))
    if not regime_ok:
        why_not.append(f"Regime gate closed ({regime_label})")

    return sanitize_for_json(
        {
            "ticker": ticker,
            "price": price,
            "action": action,
            "regime": {"label": regime_label, "should_trade": regime_ok},
            "relative_strength_vs_spy_pct": rs_vs_spy,
            "technical": {"structure_ok": technical_ok},
            "options": options_block,
            "insider": insider_block,
            "sponsor": sponsor_block,
            "why_now": why_now,
            "why_not": why_not,
            "disclaimer": (
                "Conviction stack is decision support only — not a trade signal. "
                "Verify data trust flags before sizing."
            ),
        }
    )
