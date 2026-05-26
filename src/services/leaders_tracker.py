"""Top leaders / repeated accumulation — supplemental smart-money overlay."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Dict, List

from src.core.stock_universe import CORE_WATCHLIST


def _now() -> str:
    return datetime.now(timezone.utc).isoformat() + "Z"


def build_leaders_snapshot(
    *,
    tickers: List[str] | None = None,
    limit: int = 15,
) -> Dict[str, Any]:
    """
    Stub institutional leader map — wire 13F ingest for production.
    Returns structured overlay, not buy signals.
    """
    universe = tickers or CORE_WATCHLIST[:20]
    rows: List[Dict[str, Any]] = []
    for i, t in enumerate(universe[:limit]):
        rows.append(
            {
                "ticker": t,
                "leader_overlap_count": 1 if i % 4 == 0 else 0,
                "quality_bucket": "tier_1" if i % 5 == 0 else "tier_2",
                "accumulation_trend": "watch" if i % 3 == 0 else "neutral",
                "crowding_score": min(100, 20 + i * 3),
                "signal_quality": "delayed_filing",
                "usefulness": "supplemental_only",
            }
        )
    repeated = [r for r in rows if r["leader_overlap_count"] >= 1][:5]
    return {
        "as_of": _now(),
        "repeated_accumulation": repeated,
        "newly_discovered": [r["ticker"] for r in rows if r["accumulation_trend"] == "watch"][:3],
        "broadly_trimmed": [],
        "rows": rows,
        "evidence": {
            "basis": "placeholder_universe_scan",
            "label": "Wire 13F delta feed — not live leader filings",
        },
    }
