"""
Relative Value Engine — Peer/sector/index comparison (Sprint 71)
================================================================

For every stock recommendation, surfaces a structured comparison
against peers, sector median, and index on key metrics with
quantified deltas.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)


@dataclass
class MetricComparison:
    """Single metric comparison across peer group."""
    metric_name: str
    display_name: str
    stock_value: float = 0.0
    peer_median: float = 0.0
    sector_median: float = 0.0
    index_value: float = 0.0
    unit: str = ""  # "x", "%", "$", etc.

    @property
    def vs_peer_delta(self) -> float:
        return self.stock_value - self.peer_median

    @property
    def vs_sector_delta(self) -> float:
        return self.stock_value - self.sector_median

    @property
    def vs_index_delta(self) -> float:
        return self.stock_value - self.index_value

    @property
    def stock_wins_on(self) -> List[str]:
        """Which comparisons the stock beats (lower is better for some)."""
        wins = []
        lower_is_better = self.metric_name in (
            "pe_ratio", "debt_to_equity", "volatility", "beta",
        )
        if lower_is_better:
            if self.stock_value < self.peer_median:
                wins.append("peer")
            if self.stock_value < self.sector_median:
                wins.append("sector")
            if self.stock_value < self.index_value:
                wins.append("index")
        else:
            if self.stock_value > self.peer_median:
                wins.append("peer")
            if self.stock_value > self.sector_median:
                wins.append("sector")
            if self.stock_value > self.index_value:
                wins.append("index")
        return wins

    def to_dict(self) -> Dict[str, Any]:
        return {
            "metric": self.metric_name,
            "display": self.display_name,
            "stock": round(self.stock_value, 3),
            "peer_median": round(self.peer_median, 3),
            "sector_median": round(self.sector_median, 3),
            "index": round(self.index_value, 3),
            "unit": self.unit,
            "vs_peer_delta": round(self.vs_peer_delta, 3),
            "vs_sector_delta": round(self.vs_sector_delta, 3),
            "vs_index_delta": round(self.vs_index_delta, 3),
            "wins_on": self.stock_wins_on,
        }


@dataclass
class RelativeValueReport:
    """Full relative value comparison for a stock."""
    ticker: str
    sector: str = ""
    industry: str = ""
    benchmark_index: str = "SPY"

    # Metric comparisons
    metrics: List[MetricComparison] = field(default_factory=list)

    # Conviction drivers
    conviction_drivers: List[str] = field(default_factory=list)
    conviction_risks: List[str] = field(default_factory=list)

    # Catalyst timeline
    catalysts: List[Dict[str, str]] = field(default_factory=list)

    # Overall edge score (0–100)
    edge_score: float = 0.0
    edge_summary: str = ""

    def to_dict(self) -> Dict[str, Any]:
        return {
            "ticker": self.ticker,
            "sector": self.sector,
            "industry": self.industry,
            "benchmark_index": self.benchmark_index,
            "metrics": [m.to_dict() for m in self.metrics],
            "conviction_drivers": self.conviction_drivers,
            "conviction_risks": self.conviction_risks,
            "catalysts": self.catalysts,
            "edge_score": round(self.edge_score, 1),
            "edge_summary": self.edge_summary,
        }


class RelativeValueEngine:
    """Compare a stock against peers, sector, and index.

    Usage::

        engine = RelativeValueEngine()
        report = engine.compare(
            ticker="AAPL",
            stock_data={...},
            peer_data=[{...}, ...],
            sector_data={...},
            index_data={...},
        )
    """

    # Metrics to compare with display names and units
    METRIC_DEFS = [
        ("pe_ratio", "P/E Ratio", "x"),
        ("forward_pe", "Forward P/E", "x"),
        ("peg_ratio", "PEG Ratio", "x"),
        ("price_to_book", "P/B Ratio", "x"),
        ("revenue_growth", "Revenue Growth", "%"),
        ("earnings_growth", "Earnings Growth", "%"),
        ("profit_margin", "Profit Margin", "%"),
        ("roe", "Return on Equity", "%"),
        ("debt_to_equity", "Debt/Equity", "x"),
        ("beta", "Beta", "x"),
        ("volatility_30d", "30D Volatility", "%"),
        ("momentum_3m", "3M Momentum", "%"),
        ("dividend_yield", "Dividend Yield", "%"),
        ("market_cap", "Market Cap", "$B"),
    ]

    def compare(
        self,
        ticker: str,
        stock_data: Dict[str, Any],
        peer_data: Optional[List[Dict[str, Any]]] = None,
        sector_data: Optional[Dict[str, Any]] = None,
        index_data: Optional[Dict[str, Any]] = None,
        catalysts: Optional[List[Dict[str, str]]] = None,
    ) -> RelativeValueReport:
        """Build full relative value comparison."""
        peer_data = peer_data or []
        sector_data = sector_data or {}
        index_data = index_data or {}

        report = RelativeValueReport(
            ticker=ticker,
            sector=stock_data.get("sector", ""),
            industry=stock_data.get("industry", ""),
        )

        # Build metric comparisons
        for field_name, display, unit in self.METRIC_DEFS:
            stock_val = self._extract_metric(stock_data, field_name)
            peer_med = self._median_metric(peer_data, field_name)
            sector_val = self._extract_metric(sector_data, field_name)
            index_val = self._extract_metric(index_data, field_name)

            if stock_val is not None:
                mc = MetricComparison(
                    metric_name=field_name,
                    display_name=display,
                    stock_value=stock_val,
                    peer_median=peer_med,
                    sector_median=sector_val,
                    index_value=index_val,
                    unit=unit,
                )
                report.metrics.append(mc)

        # Conviction drivers (metrics where stock wins on 2+ comparisons)
        for mc in report.metrics:
            wins = mc.stock_wins_on
            if len(wins) >= 2:
                report.conviction_drivers.append(
                    f"{mc.display_name} beats {'/'.join(wins)} "
                    f"(stock {mc.stock_value:.2f}{mc.unit} vs "
                    f"peer median {mc.peer_median:.2f}{mc.unit})"
                )
            elif len(wins) == 0:
                report.conviction_risks.append(
                    f"{mc.display_name} trails all benchmarks "
                    f"({mc.stock_value:.2f}{mc.unit})"
                )

        # Catalysts
        report.catalysts = catalysts or []

        # Edge score
        total_metrics = len(report.metrics)
        if total_metrics > 0:
            driver_pct = len(report.conviction_drivers) / total_metrics
            risk_pct = len(report.conviction_risks) / total_metrics
            report.edge_score = max(0, min(100,
                50 + (driver_pct * 60) - (risk_pct * 40)
            ))

        if report.edge_score >= 70:
            report.edge_summary = "Strong relative edge — stock outperforms on most metrics"
        elif report.edge_score >= 50:
            report.edge_summary = "Moderate edge — mixed relative positioning"
        elif report.edge_score >= 30:
            report.edge_summary = "Weak edge — trails on several key metrics"
        else:
            report.edge_summary = "No clear edge — consider alternatives"

        return report

    def _extract_metric(
        self, data: Dict[str, Any], field_name: str
    ) -> Optional[float]:
        """Extract a metric from data, checking common key patterns."""
        # Direct lookup
        val = data.get(field_name)
        if val is not None:
            try:
                return float(val)
            except (ValueError, TypeError):
                return None

        # Check nested fundamentals
        fund = data.get("fundamentals", {})
        val = fund.get(field_name)
        if val is not None:
            try:
                return float(val)
            except (ValueError, TypeError):
                return None

        return None

    def _median_metric(
        self, peers: List[Dict[str, Any]], field_name: str
    ) -> float:
        """Compute median of a metric across peer group."""
        values = []
        for p in peers:
            v = self._extract_metric(p, field_name)
            if v is not None:
                values.append(v)
        if not values:
            return 0.0
        values.sort()
        n = len(values)
        if n % 2 == 0:
            return (values[n // 2 - 1] + values[n // 2]) / 2
        return values[n // 2]
