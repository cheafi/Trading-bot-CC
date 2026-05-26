"""Institutional flow decision surface — evidence ladder + PM action states."""

from __future__ import annotations

import asyncio
import logging
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)

_PM_ACTIONS = (
    "BUYABLE_NOW",
    "WATCH_FOR_STOCK_CONFIRM",
    "AVOID_CHASE",
    "HEDGE_NO_EDGE",
    "LIKELY_HEDGING_FLOW",
    "FAILED_FOLLOW_THROUGH",
    "NOT_ACTIONABLE",
)

_METHODOLOGY = (
    "Radar score blends flow magnitude, novelty (vol/OI, IV), tradeability (spread, "
    "liquidity), and stock/regime context. Grades are heuristic — not backtest-calibrated "
    "until historical follow-through is wired."
)


def _evidence_ladder(
    row: Dict[str, Any],
    *,
    follow_through: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    stock_move = float(row.get("stock_move_pct") or 0)
    cp = (row.get("call_put") or "C").upper()
    stock_confirmed = abs(stock_move) >= 2 and (
        (cp == "C" and stock_move > 0) or (cp == "P" and stock_move < 0)
    )
    ft = follow_through or {}
    return {
        "flow_detected": True,
        "opening_estimate": row.get("volume_oi_ratio", 0) >= 0.8,
        "aggressive_side": (
            "ask"
            if row.get("side_bias", "").endswith("BUYING")
            else "bid/mid"
        ),
        "sweep_or_block": bool(row.get("sweep_flag") or row.get("block_flag")),
        "stock_confirmed": stock_confirmed,
        "volume_confirmed": float(row.get("volume_vs_avg_ratio") or 0) >= 1.5,
        "iv_skew_confirmed": abs(float(row.get("iv_change") or 0)) >= 0.05,
        "catalyst_nearby": bool(row.get("catalyst")),
        "follow_through_percentile": ft.get("follow_through_percentile"),
        "follow_through_label": ft.get("label"),
        "follow_through_basis": ft.get("basis"),
        "follow_through_sufficient": ft.get("sufficient"),
        "steps_passed": sum(
            [
                True,
                float(row.get("volume_oi_ratio") or 0) >= 0.5,
                bool(row.get("sweep_flag") or row.get("block_flag")),
                stock_confirmed,
                float(row.get("volume_vs_avg_ratio") or 0) >= 1.2,
            ]
        ),
    }


def _pm_action(
    row: Dict[str, Any],
    *,
    regime_tradeability: str,
    synthetic: bool,
) -> Dict[str, Any]:
    if synthetic:
        return {
            "pm_action": "NOT_ACTIONABLE",
            "actionable": False,
            "reason": "Synthetic/mock flow — not for capital deployment",
        }

    stock_move = float(row.get("stock_move_pct") or 0)
    cp = (row.get("call_put") or "C").upper()
    stock_confirmed = abs(stock_move) >= 2 and (
        (cp == "C" and stock_move > 0) or (cp == "P" and stock_move < 0)
    )
    spread = float(row.get("spread_pct") or 0)
    trade_score = float(row.get("tradeability_score") or 0)
    grade = row.get("quality_grade") or "C"
    regime_ok = regime_tradeability in ("TRADE", "STRONG_TRADE", "SELECTIVE")

    if spread > 12 or trade_score < 25:
        return {
            "pm_action": "LIKELY_HEDGING_FLOW",
            "actionable": False,
            "reason": "Wide spread / low tradeability — may be hedge noise",
        }
    if trade_score < 30:
        return {
            "pm_action": "HEDGE_NO_EDGE",
            "actionable": False,
            "reason": "Poor options liquidity or structure",
        }
    if abs(stock_move) > 8:
        return {
            "pm_action": "AVOID_CHASE",
            "actionable": False,
            "reason": "Underlying already extended — late chase risk",
        }
    if grade == "A" and not stock_confirmed:
        return {
            "pm_action": "WATCH_FOR_STOCK_CONFIRM",
            "actionable": False,
            "reason": "Options lead — wait for stock confirmation",
        }
    if float(row.get("radar_score") or 0) < 40 and grade != "A":
        return {
            "pm_action": "FAILED_FOLLOW_THROUGH",
            "actionable": False,
            "reason": "Flow score deteriorated — weak follow-through",
        }
    if grade in ("A", "B") and stock_confirmed and regime_ok and spread <= 8:
        return {
            "pm_action": "BUYABLE_NOW",
            "actionable": True,
            "reason": "Flow + stock aligned — deploy selective size",
        }
    if grade == "B":
        return {
            "pm_action": "WATCH_FOR_STOCK_CONFIRM",
            "actionable": False,
            "reason": "Decent flow — needs tighter stock follow-through",
        }
    return {
        "pm_action": "AVOID_CHASE" if grade == "C" else "WATCH_FOR_STOCK_CONFIRM",
        "actionable": False,
        "reason": row.get("explanation") or "Insufficient edge",
    }


def _options_detail(row: Dict[str, Any]) -> Dict[str, Any]:
    prem = float(row.get("premium") or 0)
    vol_avg = float(row.get("volume_vs_avg_ratio") or 0)
    return {
        "call_put": "CALL" if (row.get("call_put") or "C") == "C" else "PUT",
        "strike": row.get("strike"),
        "expiry": row.get("expiry"),
        "premium_usd": round(prem, 0),
        "size_contracts": row.get("size"),
        "dte": row.get("dte"),
        "implied_move_note": (
            f"~{abs(float(row.get('iv_change') or 0) * 100):.0f}% IV shift"
            if row.get("iv_change")
            else "—"
        ),
        "volume_oi": row.get("volume_oi_ratio"),
        "volume_vs_20d": vol_avg,
        "sweep": bool(row.get("sweep_flag")),
        "block": bool(row.get("block_flag")),
        "open_close_estimate": (
            "likely_opening" if float(row.get("volume_oi_ratio") or 0) >= 1.0 else "unclear"
        ),
        "aggressiveness": row.get("side_bias") or "UNKNOWN",
        "unusual_vs_baseline": (
            "elevated"
            if vol_avg >= 2
            else "normal" if vol_avg >= 1.2
            else "quiet"
        ),
    }


async def _stock_linkage(request, ticker: str) -> Dict[str, Any]:
    out: Dict[str, Any] = {"ticker": ticker}
    mds = getattr(request.app.state, "market_data", None)
    if mds is None:
        return out
    try:
        q = await asyncio.wait_for(mds.get_quote(ticker), timeout=4.0)
        if q:
            out["price"] = q.get("price")
            out["change_pct"] = q.get("change_pct")
    except Exception:
        pass
    try:
        h = await asyncio.wait_for(
            mds.get_history(ticker, period="1mo", interval="1d"), timeout=5.0
        )
        if h is not None and len(h) >= 5:
            c = "Close" if "Close" in h.columns else "close"
            s = h[c]
            out["vs_20d_high_pct"] = round(
                (float(s.iloc[-1]) / float(s.max()) - 1) * 100, 2
            )
    except Exception:
        pass
    return out


def _enrich_candidate(
    row: Dict[str, Any],
    *,
    regime_tradeability: str,
    stock_link: Optional[Dict[str, Any]] = None,
    cal: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    from src.services.flow_follow_through import lookup_flow_follow_through

    trust = row.get("trust") or {}
    synthetic = bool(trust.get("synthetic") or trust.get("mode") == "mock")
    ft = lookup_flow_follow_through(
        radar_score=float(row.get("radar_score") or 0) or None,
        grade=str(row.get("quality_grade") or "C"),
        cal=cal,
    )
    out = dict(row)
    out["synthetic"] = synthetic
    out["data_freshness"] = "MOCK" if synthetic else "LIVE"
    out["follow_through"] = ft
    out["evidence_ladder"] = _evidence_ladder(row, follow_through=ft)
    out["options_detail"] = _options_detail(row)
    act = _pm_action(row, regime_tradeability=regime_tradeability, synthetic=synthetic)
    out.update(act)
    out["stock_linkage"] = {**(stock_link or {}), "move_pct": row.get("stock_move_pct")}
    out["score_method"] = (
        "Heuristic radar — not calibrated hit-rate"
        if synthetic
        else (ft.get("label") if ft.get("sufficient") else _METHODOLOGY[:80])
    )
    return out


async def build_ticker_flow_intel(
    request,
    ticker: str,
    *,
    limit: int = 8,
) -> Dict[str, Any]:
    """Single-ticker flow slice for Dossier 360 fusion."""
    from src.api.routers.options_radar import _scan_with_fallback

    ticker = ticker.strip().upper()
    tradeability = "WAIT"
    try:
        today = getattr(request.app.state, "today_v7_cache", None) or {}
        tradeability = str(
            (today.get("market_regime") or {}).get("tradeability") or "WAIT"
        )
    except Exception:
        pass

    payload = await _scan_with_fallback([ticker], limit=limit, min_grade="C")
    trust = payload.get("trust") or {}
    synthetic = bool(
        trust.get("synthetic")
        or trust.get("mode") == "mock"
        or trust.get("fallback") == "mock"
    )
    raw = [
        r
        for r in (payload.get("candidates") or [])
        if (r.get("underlying") or "").upper() == ticker
    ]
    link = await _stock_linkage(request, ticker)
    from src.services.flow_follow_through import _calibration_data

    cal = _calibration_data()
    enriched = [
        _enrich_candidate(
            r,
            regime_tradeability=tradeability,
            stock_link=link,
            cal=cal,
        )
        for r in raw
    ]
    top = sorted(enriched, key=lambda x: float(x.get("radar_score") or 0), reverse=True)
    return {
        "ticker": ticker,
        "synthetic": synthetic,
        "count": len(top),
        "top": top[0] if top else None,
        "all": top[:5],
        "provider": trust.get("provider") or payload.get("source"),
        "warning": payload.get("warning"),
    }


async def build_flow_decision_surface(
    request,
    *,
    limit: int = 20,
) -> Dict[str, Any]:
    """PM-grade flow console from options radar + stock linkage."""
    from src.api.routers.options_radar import _scan_with_fallback
    from src.services.flow_follow_through import _calibration_data, global_calibration_summary

    t0 = datetime.now(timezone.utc)
    cal = _calibration_data()
    regime: Dict[str, Any] = {}
    tradeability = "WAIT"
    try:
        today = getattr(request.app.state, "today_v7_cache", None) or {}
        regime = today.get("market_regime") or {}
        tradeability = str(regime.get("tradeability") or "WAIT")
    except Exception:
        pass

    payload = await _scan_with_fallback(None, limit=limit, min_grade="C")
    trust = payload.get("trust") or {}
    global_synthetic = bool(
        trust.get("synthetic")
        or trust.get("mode") == "mock"
        or trust.get("fallback") == "mock"
    )

    raw = payload.get("candidates") or []
    live_raw: List[Dict[str, Any]] = []
    mock_raw: List[Dict[str, Any]] = []
    for row in raw:
        rt = row.get("trust") or {}
        if rt.get("synthetic") or rt.get("mode") == "mock" or global_synthetic:
            mock_raw.append(row)
        else:
            live_raw.append(row)

    top_for_quotes = [r.get("underlying") for r in live_raw[:8] if r.get("underlying")]
    link_map: Dict[str, Dict[str, Any]] = {}
    if top_for_quotes:
        links = await asyncio.gather(
            *[_stock_linkage(request, t) for t in top_for_quotes],
            return_exceptions=True,
        )
        for t, lk in zip(top_for_quotes, links):
            if isinstance(lk, dict):
                link_map[t] = lk

    live_enriched = [
        _enrich_candidate(
            r,
            regime_tradeability=tradeability,
            stock_link=link_map.get(r.get("underlying") or ""),
            cal=cal,
        )
        for r in live_raw
    ]
    mock_enriched = [
        _enrich_candidate(r, regime_tradeability=tradeability, cal=cal)
        for r in mock_raw
    ]

    actionable = [c for c in live_enriched if c.get("actionable")][:3]
    watch_confirm = [
        c
        for c in live_enriched
        if c.get("pm_action") == "WATCH_FOR_STOCK_CONFIRM"
    ][:3]
    crowded = [
        c for c in live_enriched if c.get("pm_action") == "AVOID_CHASE"
    ][:3]
    bearish = [c for c in live_enriched if (c.get("call_put") or "C") == "P"][:3]
    bullish = [c for c in live_enriched if (c.get("call_put") or "C") == "C"][:3]

    return {
        "as_of": t0.isoformat() + "Z",
        "regime": {
            "tradeability": tradeability,
            "trend": regime.get("trend"),
            "vix": regime.get("vix"),
            "stance": (
                "Flow confirms risk-on selectively"
                if tradeability in ("TRADE", "SELECTIVE", "STRONG_TRADE")
                else "Stand down — regime blocks flow chasing"
            ),
        },
        "freshness": {
            "provider": trust.get("provider") or payload.get("source"),
            "mode": trust.get("mode") or payload.get("status"),
            "synthetic": global_synthetic,
            "as_of": payload.get("timestamp"),
            "warning": payload.get("warning"),
            "methodology": _METHODOLOGY,
            "events_scored": (payload.get("summary") or {}).get("events_scored"),
        },
        "actionable_top3": actionable,
        "watch_for_confirm": watch_confirm,
        "best_bullish_flow": sorted(
            bullish, key=lambda x: float(x.get("radar_score") or 0), reverse=True
        )[:3],
        "best_bearish_flow": sorted(
            bearish, key=lambda x: float(x.get("radar_score") or 0), reverse=True
        )[:3],
        "crowded_trap_risk": crowded,
        "live_flow": live_enriched,
        "mock_flow": mock_enriched,
        "count_live": len(live_enriched),
        "count_mock": len(mock_enriched),
        "summary": payload.get("summary"),
        "warning": (
            "MOCK MODE — grades are illustrative only"
            if global_synthetic and not live_enriched
            else payload.get("warning")
        ),
        "calibration": global_calibration_summary(cal=cal),
        "provider_hint": (
            "Set POLYGON_API_KEY or OPTIONS_RADAR_PROVIDER=polygon for live flow"
            if global_synthetic
            else None
        ),
    }
