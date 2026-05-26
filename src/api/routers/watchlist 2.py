"""
Watchlist Decision Board Router — Sprint 72
=============================================
/api/watchlist          — Full decision board for all scan tickers
/api/watchlist/{ticker} — Single ticker decision card
/api/watchlist/search   — Command-K palette: search + popular fallback

Each row returns:
  - action tier (TRADE / LEADER / WATCH / WAIT / NO_TRADE)
  - conviction score (0-100)
  - RS rank vs SPY
  - sector + sector stage
  - regime gate (allowed / blocked)
  - next catalyst (earnings, event)
  - brief note
"""

from __future__ import annotations

import logging
import time
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, Query

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/watchlist", tags=["watchlist"])

# ---------------------------------------------------------------------------
# Popular fallback tickers for Command-K empty-state
# ---------------------------------------------------------------------------
_POPULAR = [
    "NVDA", "AAPL", "MSFT", "TSLA", "META",
    "AMZN", "GOOGL", "AMD", "SPY", "QQQ",
]

# Simple in-process cache: {ticker: (timestamp, card)}
_CARD_CACHE: Dict[str, tuple[float, Dict]] = {}
_CACHE_TTL = 300  # 5 minutes


def _cached_card(ticker: str) -> Optional[Dict]:
    entry = _CARD_CACHE.get(ticker)
    if entry and (time.time() - entry[0]) < _CACHE_TTL:
        return entry[1]
    return None


def _store_card(ticker: str, card: Dict) -> None:
    _CARD_CACHE[ticker] = (time.time(), card)


# ---------------------------------------------------------------------------
# Core card builder
# ---------------------------------------------------------------------------
def _build_decision_card(ticker: str, brief_data: Dict, regime: Dict) -> Dict:
    """Build a decision card from brief data + regime for a single ticker."""
    ticker = ticker.upper()

    # Find the ticker across actionable / watch / review sections
    action = "WAIT"
    conviction = 0
    note = ""
    setup = ""
    due_date = None
    rs_score = None

    for section, tier in [
        ("actionable", "TRADE"),
        ("watch", "WATCH"),
        ("review", "LEADER"),
    ]:
        for item in brief_data.get(section, []):
            if item.get("ticker", "").upper() == ticker:
                action = tier
                conviction = item.get("score", item.get("conviction", 0))
                note = item.get("note", item.get("thesis", ""))
                setup = item.get("setup", item.get("strategy", ""))
                due_date = item.get("due_date") or item.get("catalyst_date")
                indicators = item.get("indicators") or {}
                rs_score = indicators.get("rs")
                break
        else:
            continue
        break

    # Regime gate
    regime_ok = regime.get("should_trade", True)
    vix = regime.get("vix", regime.get("vix_level", 18.0))
    vix_regime = regime.get("vix_regime", "NORMAL")
    regime_trend = regime.get("trend", "SIDEWAYS")

    if not regime_ok or vix_regime == "RISK_OFF":
        gate = "BLOCKED"
        action = "NO_TRADE" if action == "TRADE" else action
    else:
        gate = "ALLOWED"

    return {
        "ticker": ticker,
        "action": action,
        "conviction": conviction,
        "setup": setup or "—",
        "note": note or "—",
        "rs_score": rs_score,
        "catalyst": due_date,
        "regime": {
            "trend": regime_trend,
            "vix": vix,
            "vix_regime": vix_regime,
            "gate": gate,
        },
        "synthetic": regime.get("synthetic", False),
    }


def _load_brief_data() -> Dict:
    from src.services.brief_data_service import load_brief
    return load_brief()


# ---------------------------------------------------------------------------
# Routes
# ---------------------------------------------------------------------------
@router.get("")
async def watchlist_board(
    limit: int = Query(default=50, ge=1, le=200),
    action: Optional[str] = Query(default=None, description="Filter: TRADE, WATCH, WAIT, NO_TRADE"),
):  # noqa: C901
    """
    Full decision board — all scan tickers ranked by conviction.
    Returns action tier, conviction, RS, regime gate, catalyst for each.
    """
    from src.services.regime_service import RegimeService

    regime = await RegimeService.aget()
    brief_data = _load_brief_data()
    seen = set()
    cards: List[Dict[str, Any]] = []

    for section in ("actionable", "watch", "review"):
        for item in brief_data.get(section, []):
            t = item.get("ticker", "").upper()
            if t and t not in seen:
                seen.add(t)
                card = _build_decision_card(t, brief_data, regime)
                _store_card(t, card)
                cards.append(card)

    # Filter by action tier if requested
    if action:
        action_upper = action.upper()
        cards = [c for c in cards if c["action"] == action_upper]

    # Sort: TRADE first, then WATCH, then LEADER, then rest; by conviction desc
    tier_order = {"TRADE": 0, "LEADER": 1, "WATCH": 2, "WAIT": 3, "NO_TRADE": 4}
    cards.sort(key=lambda c: (tier_order.get(c["action"], 9), -(c["conviction"] or 0)))

    return {
        "count": len(cards[:limit]),
        "total": len(cards),
        "regime": {
            "trend": regime.get("trend", "UNKNOWN"),
            "should_trade": regime.get("should_trade", True),
            "vix": regime.get("vix", 18.0),
        },
        "board": cards[:limit],
        "synthetic": regime.get("synthetic", False),
    }


@router.get("/search")
async def watchlist_search(
    q: str = Query(default="", description="Ticker or company name"),
    limit: int = Query(default=10, ge=1, le=30),
):
    """
    Command-K palette search.
    Returns tickers with action/conviction/regime enrichment.
    When q is empty, returns popular tickers with live enrichment.
    """
    from src.services.regime_service import RegimeService

    regime = await RegimeService.aget()
    brief_data = _load_brief_data()

    q = q.strip().upper()

    if not q:
        # Return popular tickers enriched
        tickers = _POPULAR[:limit]
    else:
        # Build ticker list from brief first, then pad with popular
        from_brief = [
            item.get("ticker", "").upper()
            for section in ("actionable", "watch", "review")
            for item in brief_data.get(section, [])
            if q in item.get("ticker", "").upper()
        ]
        # Also match popular
        from_popular = [t for t in _POPULAR if q in t]
        combined = list(dict.fromkeys(from_brief + from_popular))
        tickers = combined[:limit] if combined else []

    results = []
    for t in tickers:
        cached = _cached_card(t)
        if cached:
            results.append(cached)
        else:
            card = _build_decision_card(t, brief_data, regime)
            _store_card(t, card)
            results.append(card)

    return {
        "query": q,
        "results": results,
        "count": len(results),
        "popular_fallback": not bool(q),
    }


@router.get("/{ticker}")
async def watchlist_ticker(ticker: str):
    """
    Single ticker decision card.
    Returns action tier, conviction, setup, note, regime gate, catalyst.
    """
    from src.services.regime_service import RegimeService

    ticker = ticker.upper()
    cached = _cached_card(ticker)
    if cached:
        return cached

    regime = await RegimeService.aget()
    brief_data = _load_brief_data()
    card = _build_decision_card(ticker, brief_data, regime)
    _store_card(ticker, card)
    return card
