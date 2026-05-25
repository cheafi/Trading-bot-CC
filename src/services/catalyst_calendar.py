"""Catalyst calendar — forward events for portfolio / watchlist."""

from __future__ import annotations

import logging
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)


async def build_catalyst_calendar(
    request,
    tickers: Optional[List[str]] = None,
    *,
    limit: int = 20,
) -> Dict[str, Any]:
    """Upcoming catalysts for holdings or explicit ticker list."""
    symbols: List[str] = []
    if tickers:
        symbols = [t.strip().upper() for t in tickers if t.strip()]
    else:
        try:
            from src.api.routers.portfolio import _user_portfolio

            symbols = [
                h.get("ticker", "").upper()
                for h in (_user_portfolio.get("holdings") or [])
                if h.get("ticker")
            ]
        except Exception:
            pass

    mds = getattr(request.app.state, "market_data", None)
    events: List[Dict[str, Any]] = []

    for sym in symbols[:15]:
        days: Optional[int] = None
        try:
            if mds:
                from src.services.scanner import days_to_earnings

                days = await days_to_earnings(sym, mds)
        except Exception as exc:
            logger.debug("catalyst %s: %s", sym, exc)

        if days is not None and days <= 30:
            severity = "high" if days <= 3 else "medium" if days <= 7 else "low"
            events.append(
                {
                    "ticker": sym,
                    "event_type": "earnings",
                    "label": f"Earnings ~{days}d",
                    "days_until": days,
                    "severity": severity,
                    "action_hint": "Reduce size or avoid new adds inside blackout",
                }
            )

    events.sort(key=lambda e: (e.get("days_until") or 999))
    macro_events = [
        {
            "ticker": "MACRO",
            "event_type": "macro",
            "label": "FOMC / rates — check Today regime",
            "days_until": None,
            "severity": "medium",
            "action_hint": "Align sizing with VIX and breadth on Today tab",
        },
    ]

    return {
        "as_of": datetime.now(timezone.utc).isoformat() + "Z",
        "events": (events + macro_events)[:limit],
        "holdings_scanned": len(symbols),
        "evidence": {
            "earnings_source": "market_data_calendar",
            "label": "Earnings dates approximate — confirm before trading",
        },
    }
