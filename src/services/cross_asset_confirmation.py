"""Cross-asset confirmation for Today tab — rates / vol / equity alignment."""

from __future__ import annotations

import asyncio
import logging
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from src.services.p2_cache import get_cached, set_cached

logger = logging.getLogger(__name__)

_CACHE_ATTR = "cross_asset_confirmation_cache"


async def build_cross_asset_confirmation(
    request,
    *,
    regime: Optional[Dict[str, Any]] = None,
    should_trade: bool = True,
) -> Dict[str, Any]:
    """
    PM-readable cross-asset strip: do macro assets confirm equity stance?
    Uses live ETF proxies only (no heavy ContextAssembler — keeps /today fast).
    """
    regime = regime or {}
    cache_key = (
        f"{regime.get('trend')}_{regime.get('vix')}_{regime.get('breadth')}_{should_trade}"
    )
    cached = get_cached(request.app.state, f"{_CACHE_ATTR}_{cache_key}")
    if cached is not None:
        return cached

    assets: List[Dict[str, Any]] = []
    mds = getattr(request.app.state, "market_data", None)
    proxies = [
        ("SPY", "US equities"),
        ("QQQ", "Growth / tech"),
        ("TLT", "Long duration rates"),
    ]

    async def _chg(sym: str, label: str):
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
            return {
                "symbol": sym,
                "label": label,
                "change_1d_pct": chg,
                "change_20d_pct": chg_20,
            }
        except (asyncio.TimeoutError, Exception):
            return None

    if mds:
        fetched = await asyncio.gather(*[_chg(s, l) for s, l in proxies])
        assets = [a for a in fetched if a]

    vix = regime.get("vix")
    breadth = regime.get("breadth")
    trend = regime.get("trend", "SIDEWAYS")

    confirms: List[str] = []
    conflicts: List[str] = []

    spy = next((a for a in assets if a["symbol"] == "SPY"), None)
    qqq = next((a for a in assets if a["symbol"] == "QQQ"), None)
    tlt = next((a for a in assets if a["symbol"] == "TLT"), None)

    if spy and (spy.get("change_20d_pct") or 0) > 0 and trend == "UPTREND":
        confirms.append("SPY 20d positive aligns with UPTREND regime")
    if spy and (spy.get("change_20d_pct") or 0) < -2 and trend == "UPTREND":
        conflicts.append("SPY 20d weak vs UPTREND label — caution")

    if qqq and spy:
        if (qqq.get("change_20d_pct") or 0) > (spy.get("change_20d_pct") or 0) + 2:
            confirms.append("QQQ leading SPY — growth risk-on")
        elif (qqq.get("change_20d_pct") or 0) < (spy.get("change_20d_pct") or 0) - 2:
            conflicts.append("QQQ lagging SPY — narrow leadership")

    if tlt and (tlt.get("change_20d_pct") or 0) > 2:
        conflicts.append("TLT rally — rates falling; check growth vs defensive mix")

    if vix is not None and float(vix) > 22:
        conflicts.append(f"VIX {float(vix):.0f} elevated — size down equity adds")
    elif vix is not None and float(vix) < 16:
        confirms.append(f"VIX {float(vix):.0f} subdued — vol supports risk")

    if breadth is not None and float(breadth) < 45:
        conflicts.append(f"Breadth {breadth}% weak — rally may be narrow")
    elif breadth is not None and float(breadth) > 55:
        confirms.append(f"Breadth {breadth}% healthy")

    score = 50 + len(confirms) * 12 - len(conflicts) * 15
    score = max(0, min(100, score))
    alignment = (
        "confirmed"
        if score >= 65 and not conflicts
        else "mixed"
        if score >= 40
        else "conflicted"
    )

    equity_stance = "RISK_ON" if should_trade and alignment != "conflicted" else "CAUTIOUS"

    result = {
        "as_of": datetime.now(timezone.utc).isoformat() + "Z",
        "equity_stance": equity_stance,
        "alignment": alignment,
        "confirmation_score": score,
        "confirms": confirms[:6],
        "conflicts": conflicts[:6],
        "assets": assets,
        "summary": (
            f"{alignment.upper()}: {len(confirms)} confirm · {len(conflicts)} conflict"
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
