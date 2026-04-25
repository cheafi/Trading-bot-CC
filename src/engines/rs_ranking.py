"""
CC — Relative Strength (RS) Ranking Engine
=============================================
Computes RS scores relative to benchmark, tracks RS changes,
and provides ranked leaderboards with sector/size filtering.

RS Score = stock's % change / benchmark % change × 100
  - RS > 100 = outperforming
  - RS < 100 = underperforming

Provides:
  - RS score for multiple timeframes (1W, 1M, 3M, 6M)
  - RS change (Δ) — momentum of RS itself
  - RS percentile within universe
  - Sector-level RS aggregation
  - Leader/laggard classification
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)


class RSTimeframe(str, Enum):
    W1 = "1W"
    M1 = "1M"
    M3 = "3M"
    M6 = "6M"


class RSStatus(str, Enum):
    LEADER = "LEADER"
    STRONG = "STRONG"
    NEUTRAL = "NEUTRAL"
    WEAK = "WEAK"
    LAGGARD = "LAGGARD"


class RSTrend(str, Enum):
    ACCELERATING = "ACCELERATING"
    STEADY = "STEADY"
    DECELERATING = "DECELERATING"
    BREAKING_OUT = "BREAKING_OUT"
    BREAKING_DOWN = "BREAKING_DOWN"


@dataclass
class RSEntry:
    """RS score for a single ticker."""

    ticker: str
    sector: str = ""
    market_cap: str = ""  # MEGA/LARGE/MID/SMALL

    # RS scores by timeframe
    rs_1w: float = 100.0
    rs_1m: float = 100.0
    rs_3m: float = 100.0
    rs_6m: float = 100.0

    # RS change (delta vs prior period)
    rs_change_1w: float = 0.0
    rs_change_1m: float = 0.0

    # Composite
    rs_composite: float = 100.0
    rs_percentile: int = 50  # 0-99

    # Classification
    status: RSStatus = RSStatus.NEUTRAL
    trend: RSTrend = RSTrend.STEADY

    # Price context
    price: float = 0.0
    change_pct: float = 0.0

    def to_dict(self) -> Dict[str, Any]:
        return {
            "ticker": self.ticker,
            "sector": self.sector,
            "market_cap": self.market_cap,
            "rs_1w": round(self.rs_1w, 1),
            "rs_1m": round(self.rs_1m, 1),
            "rs_3m": round(self.rs_3m, 1),
            "rs_6m": round(self.rs_6m, 1),
            "rs_change_1w": round(self.rs_change_1w, 1),
            "rs_change_1m": round(self.rs_change_1m, 1),
            "rs_composite": round(self.rs_composite, 1),
            "rs_percentile": self.rs_percentile,
            "status": self.status.value,
            "trend": self.trend.value,
            "price": round(self.price, 2),
            "change_pct": round(self.change_pct, 2),
        }


@dataclass
class SectorRS:
    """Aggregated RS for a sector."""

    sector: str
    rs_composite: float = 100.0
    rs_change: float = 0.0
    leader_count: int = 0
    laggard_count: int = 0
    total: int = 0
    top_tickers: List[str] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "sector": self.sector,
            "rs_composite": round(self.rs_composite, 1),
            "rs_change": round(self.rs_change, 1),
            "leader_count": self.leader_count,
            "laggard_count": self.laggard_count,
            "total": self.total,
            "top_tickers": self.top_tickers[:5],
        }


class RSRankingEngine:
    """
    Computes relative strength rankings for a universe of stocks.

    Usage:
        engine = RSRankingEngine()
        rankings = engine.rank(price_data, benchmark_data)
    """

    # Weights for composite RS
    WEIGHTS = {
        RSTimeframe.W1: 0.1,
        RSTimeframe.M1: 0.25,
        RSTimeframe.M3: 0.35,
        RSTimeframe.M6: 0.3,
    }

    def rank(
        self,
        universe: List[Dict[str, Any]],
        benchmark: Optional[Dict[str, Any]] = None,
    ) -> List[RSEntry]:
        """
        Rank universe by relative strength.

        Each item in universe should have:
          ticker, sector, market_cap, price,
          return_1w, return_1m, return_3m, return_6m,
          prev_rs_1w, prev_rs_1m (for change calc)

        benchmark should have:
          return_1w, return_1m, return_3m, return_6m
        """
        if not benchmark:
            benchmark = {"return_1w": 0, "return_1m": 0, "return_3m": 0, "return_6m": 0}

        entries: List[RSEntry] = []
        for stock in universe:
            entry = self._compute_rs(stock, benchmark)
            entries.append(entry)

        # Sort by composite RS descending
        entries.sort(key=lambda e: e.rs_composite, reverse=True)

        # Assign percentiles
        n = len(entries)
        for i, entry in enumerate(entries):
            entry.rs_percentile = int(((n - i - 1) / max(n - 1, 1)) * 99)

        # Classify status
        for entry in entries:
            entry.status = self._classify_status(entry)
            entry.trend = self._classify_trend(entry)

        return entries

    def _compute_rs(self, stock: Dict[str, Any], bench: Dict[str, Any]) -> RSEntry:
        """Compute RS scores for a single stock."""

        def rs_score(stock_ret: float, bench_ret: float) -> float:
            if bench_ret == 0:
                return 100.0 + stock_ret * 10
            return max(0, min(300, (1 + stock_ret / 100) / (1 + bench_ret / 100) * 100))

        rs_1w = rs_score(stock.get("return_1w", 0), bench.get("return_1w", 0))
        rs_1m = rs_score(stock.get("return_1m", 0), bench.get("return_1m", 0))
        rs_3m = rs_score(stock.get("return_3m", 0), bench.get("return_3m", 0))
        rs_6m = rs_score(stock.get("return_6m", 0), bench.get("return_6m", 0))

        composite = (
            rs_1w * self.WEIGHTS[RSTimeframe.W1]
            + rs_1m * self.WEIGHTS[RSTimeframe.M1]
            + rs_3m * self.WEIGHTS[RSTimeframe.M3]
            + rs_6m * self.WEIGHTS[RSTimeframe.M6]
        )

        # RS change = current RS - previous RS
        rs_change_1w = rs_1w - stock.get("prev_rs_1w", rs_1w)
        rs_change_1m = rs_1m - stock.get("prev_rs_1m", rs_1m)

        return RSEntry(
            ticker=stock.get("ticker", ""),
            sector=stock.get("sector", ""),
            market_cap=stock.get("market_cap", ""),
            rs_1w=rs_1w,
            rs_1m=rs_1m,
            rs_3m=rs_3m,
            rs_6m=rs_6m,
            rs_change_1w=rs_change_1w,
            rs_change_1m=rs_change_1m,
            rs_composite=composite,
            price=stock.get("price", 0),
            change_pct=stock.get("change_pct", 0),
        )

    def _classify_status(self, entry: RSEntry) -> RSStatus:
        if entry.rs_percentile >= 85:
            return RSStatus.LEADER
        if entry.rs_percentile >= 65:
            return RSStatus.STRONG
        if entry.rs_percentile >= 35:
            return RSStatus.NEUTRAL
        if entry.rs_percentile >= 15:
            return RSStatus.WEAK
        return RSStatus.LAGGARD

    def _classify_trend(self, entry: RSEntry) -> RSTrend:
        chg = entry.rs_change_1w
        if chg > 5:
            if entry.rs_percentile < 50:
                return RSTrend.BREAKING_OUT
            return RSTrend.ACCELERATING
        if chg < -5:
            if entry.rs_percentile > 50:
                return RSTrend.BREAKING_DOWN
            return RSTrend.DECELERATING
        return RSTrend.STEADY

    def get_sector_rankings(self, entries: List[RSEntry]) -> List[SectorRS]:
        """Aggregate RS by sector."""
        sector_map: Dict[str, List[RSEntry]] = {}
        for e in entries:
            sector_map.setdefault(e.sector or "Other", []).append(e)

        sectors: List[SectorRS] = []
        for name, stocks in sector_map.items():
            avg_rs = sum(s.rs_composite for s in stocks) / len(stocks)
            avg_chg = sum(s.rs_change_1w for s in stocks) / len(stocks)
            leaders = sum(
                1 for s in stocks if s.status in (RSStatus.LEADER, RSStatus.STRONG)
            )
            laggards = sum(
                1 for s in stocks if s.status in (RSStatus.WEAK, RSStatus.LAGGARD)
            )
            top = [
                s.ticker
                for s in sorted(stocks, key=lambda x: x.rs_composite, reverse=True)[:5]
            ]
            sectors.append(
                SectorRS(
                    sector=name,
                    rs_composite=avg_rs,
                    rs_change=avg_chg,
                    leader_count=leaders,
                    laggard_count=laggards,
                    total=len(stocks),
                    top_tickers=top,
                )
            )

        sectors.sort(key=lambda s: s.rs_composite, reverse=True)
        return sectors

    def get_leaders(self, entries: List[RSEntry], limit: int = 20) -> List[RSEntry]:
        """Top RS leaders."""
        return [e for e in entries if e.status in (RSStatus.LEADER, RSStatus.STRONG)][
            :limit
        ]

    def get_breakouts(self, entries: List[RSEntry]) -> List[RSEntry]:
        """Stocks with RS breaking out (new strength)."""
        return [e for e in entries if e.trend == RSTrend.BREAKING_OUT]

    def get_breakdowns(self, entries: List[RSEntry]) -> List[RSEntry]:
        """Stocks with RS breaking down (losing strength)."""
        return [e for e in entries if e.trend == RSTrend.BREAKING_DOWN]
