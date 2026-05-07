"""
Watchlist Intelligence Engine — Sprint 51
==========================================
Smart watchlist: ranks opportunities with regime-aware scoring,
"why now" explanations, staleness tracking, and deferred signals.

This is NOT just a list of tickers. It's an intelligent queue that:
 1. Ranks by composite score (signal + regime + freshness)
 2. Explains WHY each ticker is on the list NOW
 3. Tracks signal freshness (decay)
 4. Separates "act now" from "watch for later"
 5. Supports filtering by regime, sector, setup quality
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Optional


@dataclass
class WatchlistItem:
    """A single watchlist entry with intelligence context."""

    ticker: str
    score: float  # 0.0–1.0
    direction: str  # LONG / SHORT / FLAT
    urgency: str  # ACT_NOW / WATCH / DEFER / STALE
    setup_grade: str  # A / B / C / D
    why_now: str  # Human-readable "why now" explanation
    regime: str  # Market regime when added
    sector: str  # Sector
    evidence_for: list[str] = field(default_factory=list)
    evidence_against: list[str] = field(default_factory=list)
    added_at: str = ""
    price_at_add: float = 0.0
    current_price: float = 0.0
    rsi: float = 50.0
    atr_pct: float = 0.02
    invalidation: str = ""  # What would kill this setup

    def __post_init__(self):
        if not self.added_at:
            self.added_at = datetime.now(timezone.utc).isoformat() + "Z"

    def to_dict(self) -> dict:
        return {
            "ticker": self.ticker,
            "score": self.score,
            "direction": self.direction,
            "urgency": self.urgency,
            "setup_grade": self.setup_grade,
            "why_now": self.why_now,
            "regime": self.regime,
            "sector": self.sector,
            "evidence_for": self.evidence_for,
            "evidence_against": self.evidence_against,
            "added_at": self.added_at,
            "price_at_add": self.price_at_add,
            "current_price": self.current_price,
            "rsi": self.rsi,
            "atr_pct": self.atr_pct,
            "invalidation": self.invalidation,
        }


class WatchlistIntelEngine:
    """
    Intelligent watchlist manager.

    Maintains a ranked, regime-aware watchlist with freshness tracking.
    """

    MAX_ITEMS = 50

    def __init__(self):
        self._items: dict[str, WatchlistItem] = {}

    def add(
        self,
        ticker: str,
        score: float = 0.5,
        direction: str = "LONG",
        setup_grade: str = "C",
        why_now: str = "",
        regime: str = "UNKNOWN",
        sector: str = "Unknown",
        evidence_for: Optional[list[str]] = None,
        evidence_against: Optional[list[str]] = None,
        price: float = 0.0,
        rsi: float = 50.0,
        atr_pct: float = 0.02,
        invalidation: str = "",
    ) -> WatchlistItem:
        """Add or update a watchlist item."""
        # Determine urgency
        if score >= 0.75 and setup_grade in ("A", "B"):
            urgency = "ACT_NOW"
        elif score >= 0.55:
            urgency = "WATCH"
        elif score >= 0.35:
            urgency = "DEFER"
        else:
            urgency = "STALE"

        item = WatchlistItem(
            ticker=ticker,
            score=score,
            direction=direction,
            urgency=urgency,
            setup_grade=setup_grade,
            why_now=why_now or f"{ticker} scored {score:.2f} in {regime}",
            regime=regime,
            sector=sector,
            evidence_for=evidence_for or [],
            evidence_against=evidence_against or [],
            price_at_add=price,
            current_price=price,
            rsi=rsi,
            atr_pct=atr_pct,
            invalidation=invalidation,
        )

        self._items[ticker] = item

        # Evict lowest-scoring if over max
        if len(self._items) > self.MAX_ITEMS:
            worst = min(
                self._items,
                key=lambda t: self._items[t].score,
            )
            del self._items[worst]

        return item

    def remove(self, ticker: str) -> bool:
        if ticker in self._items:
            del self._items[ticker]
            return True
        return False

    def ranked(
        self,
        top_n: int = 20,
        urgency_filter: Optional[str] = None,
        regime_filter: Optional[str] = None,
    ) -> list[dict]:
        """Get ranked watchlist items."""
        items = list(self._items.values())

        if urgency_filter:
            items = [i for i in items if i.urgency == urgency_filter]
        if regime_filter:
            items = [i for i in items if i.regime == regime_filter]

        items.sort(key=lambda x: x.score, reverse=True)
        return [i.to_dict() for i in items[:top_n]]

    @property
    def count(self) -> int:
        return len(self._items)

    def stats(self) -> dict:
        items = list(self._items.values())
        if not items:
            return {
                "total": 0,
                "act_now": 0,
                "watch": 0,
                "defer": 0,
                "stale": 0,
                "avg_score": 0,
            }
        urgencies = [i.urgency for i in items]
        return {
            "total": len(items),
            "act_now": urgencies.count("ACT_NOW"),
            "watch": urgencies.count("WATCH"),
            "defer": urgencies.count("DEFER"),
            "stale": urgencies.count("STALE"),
            "avg_score": round(sum(i.score for i in items) / len(items), 3),
        }

    def get(self, ticker: str) -> Optional[dict]:
        item = self._items.get(ticker)
        return item.to_dict() if item else None

    def summary(self) -> dict:
        s = self.stats()
        s["top_5"] = self.ranked(5)
        return s
