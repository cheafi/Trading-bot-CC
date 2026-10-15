"""Cross-market snapshots with per-symbol fallback (Vibe-Trading style)."""

from __future__ import annotations

import logging
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)

# Representative symbols per region — research universe, not execution lists.
REGION_SYMBOLS: Dict[str, List[str]] = {
    "US": ["SPY", "QQQ", "AAPL"],
    "HK": ["0700.HK", "9988.HK"],
    "CA": ["SHOP.TO"],
    "UK": ["AZN.L"],
    "IN": ["RELIANCE.NS"],
    "KR": ["005930.KS"],
    "CRYPTO": ["BTC-USD", "ETH-USD", "SOL-USD"],
    "FUTURES": ["ES=F", "GC=F"],
}

_DEFAULT_REGIONS = ("US", "CRYPTO", "HK")


async def fetch_cross_market_snapshots(
    mds,
    *,
    regions: Optional[List[str]] = None,
    period: str = "1mo",
    max_symbols_per_region: int = 3,
) -> Dict[str, Any]:
    """Load OHLCV summaries per region; failed symbols are skipped with reason."""
    selected = [r.upper() for r in (regions or list(_DEFAULT_REGIONS)) if r]
    out: Dict[str, Any] = {
        "regions": {},
        "fallbacks": [],
        "data_tier": "LIVE_OR_CACHED",
    }
    for region in selected:
        symbols = (REGION_SYMBOLS.get(region) or [])[:max_symbols_per_region]
        if not symbols and region not in REGION_SYMBOLS:
            out["fallbacks"].append(
                {"region": region, "reason": "unknown_region", "used": "US+CRYPTO"}
            )
            continue
        rows: List[Dict[str, Any]] = []
        for sym in symbols:
            row = await _load_symbol_summary(mds, sym, period=period, region=region)
            rows.append(row)
            if not row.get("ok") and region == "US":
                alt = await _load_symbol_summary(mds, "SPY", period=period, region="US")
                if alt.get("ok"):
                    out["fallbacks"].append(
                        {"region": region, "symbol": sym, "fallback": "SPY"}
                    )
        out["regions"][region] = rows
    return out


async def _load_symbol_summary(
    mds, symbol: str, *, period: str, region: str
) -> Dict[str, Any]:
    try:
        hist = await mds.get_history(symbol, period=period, interval="1d")
    except Exception as exc:
        logger.debug("cross_market history failed %s: %s", symbol, exc)
        return {
            "ok": False,
            "symbol": symbol,
            "region": region,
            "error": type(exc).__name__,
        }
    if hist is None or getattr(hist, "empty", True):
        return {
            "ok": False,
            "symbol": symbol,
            "region": region,
            "error": "no_bars",
        }
    close_col = "Close" if "Close" in hist.columns else "close"
    last = float(hist[close_col].iloc[-1])
    first = float(hist[close_col].iloc[0])
    chg_pct = round((last / first - 1.0) * 100.0, 2) if first else None
    return {
        "ok": True,
        "symbol": symbol,
        "region": region,
        "bars": len(hist),
        "last_close": round(last, 4),
        "period_return_pct": chg_pct,
    }


def resolve_symbols_from_prompt(
    text: str, *, default_regions: Optional[List[str]] = None
) -> List[str]:
    """Merge explicit tickers from text with default cross-market basket."""
    from src.services.vibe_agent import _extract_assets

    found = _extract_assets(text)
    for sym in found:
        if sym in {"BTC", "ETH", "SOL"}:
            continue
    crypto_map = {"BTC": "BTC-USD", "ETH": "ETH-USD", "SOL": "SOL-USD"}
    symbols: List[str] = []
    for t in found:
        if t in crypto_map:
            symbols.append(crypto_map[t])
        elif "." not in t and len(t) <= 5:
            symbols.append(t.upper())
        else:
            symbols.append(t)
    if not symbols:
        for region in default_regions or _DEFAULT_REGIONS:
            for sym in (REGION_SYMBOLS.get(region.upper()) or [])[:1]:
                if sym not in symbols:
                    symbols.append(sym)
    return symbols[:10]
