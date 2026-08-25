"""Cross-asset confirmation for Today tab — rates / vol / equity alignment."""

from __future__ import annotations

import asyncio
import logging
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional, Tuple

from src.services.p2_cache import get_cached, set_cached

logger = logging.getLogger(__name__)

_CACHE_ATTR = "cross_asset_confirmation_cache"

# symbol, label, role for PM strip
_PROXY_ASSETS: Tuple[Tuple[str, str, str], ...] = (
    ("SPY", "US equities", "equity"),
    ("QQQ", "Growth / tech", "equity"),
    ("IWM", "Small cap", "equity"),
    ("TLT", "Long duration rates", "rates"),
    ("UUP", "USD (DXY proxy)", "fx"),
)


def _stance_for_asset(
    *,
    symbol: str,
    role: str,
    change_1d: Optional[float],
    change_20d: Optional[float],
    trend: str,
    vix: Optional[float],
    breadth: Optional[float],
) -> str:
    """Per-asset: confirm / neutral / conflict."""
    t = (trend or "SIDEWAYS").upper()
    c20 = change_20d if change_20d is not None else 0.0
    c1 = change_1d if change_1d is not None else 0.0

    if symbol == "SPY":
        if t == "UPTREND" and c20 > 0:
            return "confirm"
        if t == "UPTREND" and c20 < -2:
            return "conflict"
        return "neutral"
    if symbol == "QQQ":
        if c20 > 1 and t in ("UPTREND", "SIDEWAYS"):
            return "confirm"
        if c20 < -2 and t == "UPTREND":
            return "conflict"
        return "neutral"
    if symbol == "IWM":
        if c20 > 0 and breadth is not None and float(breadth) > 45:
            return "confirm"
        if c20 < -3:
            return "conflict"
        return "neutral"
    if symbol == "TLT":
        if c20 > 2 and t == "UPTREND":
            return "conflict"
        if c20 < -1 and t == "UPTREND":
            return "confirm"
        return "neutral"
    if symbol == "UUP":
        if c20 > 2 and t == "UPTREND":
            return "conflict"
        if abs(c20) < 1:
            return "neutral"
        return "neutral"
    if role == "vol" and vix is not None:
        if float(vix) < 18:
            return "confirm"
        if float(vix) > 25:
            return "conflict"
        return "neutral"
    if abs(c1) < 0.15 and abs(c20) < 0.5:
        return "neutral"
    return "neutral"


async def build_cross_asset_confirmation(
    request,
    *,
    regime: Optional[Dict[str, Any]] = None,
    should_trade: bool = True,
) -> Dict[str, Any]:
    """
    PM-readable cross-asset strip: SPY, QQQ, IWM, TLT, DXY, VIX, breadth.
    """
    regime = regime or {}
    cache_key = f"{regime.get('trend')}_{regime.get('vix')}_{regime.get('breadth')}_{should_trade}"
    cached = get_cached(request.app.state, f"{_CACHE_ATTR}_{cache_key}")
    if cached is not None:
        return cached

    assets: List[Dict[str, Any]] = []
    mds = getattr(request.app.state, "market_data", None)
    trend = regime.get("trend", "SIDEWAYS")
    vix = regime.get("vix")
    breadth = regime.get("breadth")

    async def _chg(sym: str, label: str, role: str):
        if mds is None:
            return None
        try:
            h = await asyncio.wait_for(
                mds.get_history(sym, period="1mo", interval="1d"),
                timeout=4.0,
            )
            if h is None or len(h) < 2:
                return None
            c = "Close" if "Close" in h.columns else "close"
            cur = float(h[c].iloc[-1])
            prev = float(h[c].iloc[-2])
            chg = round((cur / prev - 1) * 100, 2)
            chg_20 = None
            if len(h) >= 21:
                chg_20 = round((cur / float(h[c].iloc[-21]) - 1) * 100, 2)
            stance = _stance_for_asset(
                symbol=sym,
                role=role,
                change_1d=chg,
                change_20d=chg_20,
                trend=trend,
                vix=vix,
                breadth=breadth,
            )
            return {
                "symbol": sym,
                "label": label,
                "role": role,
                "change_1d_pct": chg,
                "change_20d_pct": chg_20,
                "stance": stance,
            }
        except (asyncio.TimeoutError, Exception):
            return None

    if mds:
        fetched = await asyncio.gather(
            *[_chg(s, label, r) for s, label, r in _PROXY_ASSETS]
        )
        assets = [a for a in fetched if a]

    if vix is not None:
        vix_stance = _stance_for_asset(
            symbol="VIX",
            role="vol",
            change_1d=None,
            change_20d=None,
            trend=trend,
            vix=vix,
            breadth=breadth,
        )
        assets.append(
            {
                "symbol": "VIX",
                "label": "Volatility",
                "role": "vol",
                "change_1d_pct": None,
                "change_20d_pct": None,
                "level": round(float(vix), 1),
                "stance": vix_stance,
            }
        )

    if breadth is not None:
        b = float(breadth)
        b_stance = "confirm" if b > 55 else "conflict" if b < 40 else "neutral"
        assets.append(
            {
                "symbol": "BREADTH",
                "label": "Market breadth",
                "role": "breadth",
                "change_1d_pct": None,
                "change_20d_pct": None,
                "level": round(b, 0),
                "stance": b_stance,
            }
        )

    confirms: List[str] = []
    conflicts: List[str] = []

    for a in assets:
        sym = a.get("symbol", "")
        st = a.get("stance", "neutral")
        if st == "confirm":
            if sym == "VIX" and a.get("level") is not None:
                confirms.append(f"VIX {a['level']:.0f} subdued")
            elif sym == "BREADTH" and a.get("level") is not None:
                confirms.append(f"Breadth {a['level']:.0f}% healthy")
            elif a.get("change_20d_pct") is not None:
                confirms.append(f"{sym} 20d {a['change_20d_pct']:+.1f}% aligns")
        elif st == "conflict":
            if sym == "VIX" and a.get("level") is not None:
                conflicts.append(f"VIX {a['level']:.0f} elevated")
            elif sym == "BREADTH" and a.get("level") is not None:
                conflicts.append(f"Breadth {a['level']:.0f}% narrow")
            elif sym == "TLT" and (a.get("change_20d_pct") or 0) > 2:
                conflicts.append("TLT rally — rates falling; check growth mix")
            elif sym == "UUP" and (a.get("change_20d_pct") or 0) > 2:
                conflicts.append("USD strength — headwind for risk assets")
            elif a.get("change_20d_pct") is not None:
                conflicts.append(f"{sym} 20d weak vs regime label")

    score = 50 + len(confirms) * 10 - len(conflicts) * 12
    score = max(0, min(100, score))
    confirm_n = sum(1 for a in assets if a.get("stance") == "confirm")
    conflict_n = sum(1 for a in assets if a.get("stance") == "conflict")
    alignment = (
        "confirmed"
        if score >= 65 and conflict_n <= 1
        else "mixed"
        if score >= 40
        else "conflicted"
    )

    equity_stance = (
        "RISK_ON" if should_trade and alignment != "conflicted" else "CAUTIOUS"
    )

    result = {
        "as_of": datetime.now(timezone.utc).isoformat() + "Z",
        "equity_stance": equity_stance,
        "alignment": alignment,
        "confirmation_score": score,
        "confirm_count": confirm_n,
        "conflict_count": conflict_n,
        "confirms": confirms[:8],
        "conflicts": conflicts[:8],
        "assets": assets,
        "summary": (
            f"{alignment.upper()}: {confirm_n} confirm · {conflict_n} conflict · "
            f"{len(assets)} checks"
        ),
        "action_hint": (
            "Deploy selective — macro confirms"
            if alignment == "confirmed"
            else "Wait for breadth/VIX improvement"
            if alignment == "conflicted"
            else "Monitor — mixed macro"
        ),
        "evidence": {
            "basis": "live_proxy_returns",
            "label": "ETF proxies — not full macro model",
        },
    }
    set_cached(request.app.state, f"{_CACHE_ATTR}_{cache_key}", result, ttl_sec=90)
    return result
