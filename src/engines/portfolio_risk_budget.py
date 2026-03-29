"""
Portfolio Risk Budget — book-level risk management (Sprint 35).

A professional PM thinks in terms of portfolio risk, not
individual trade risk.  This module enforces:

  • max single-name concentration (5%)
  • max sector concentration (30%)
  • max high-beta cluster exposure (25%)
  • max earnings-within-48h exposure (10%)
  • max correlation-bucket concentration
  • max gross long-only in risk-off regime (50%)
  • max open positions cap
  • portfolio-beta limit (1.5)

The PortfolioRiskBudget is consumed by:
  - OpportunityEnsembler._correlation_penalty()  (enhanced)
  - AutoTradingEngine._calculate_position_size()  (multiplier)
  - API / Discord for exposure display
"""
import logging
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Set

logger = logging.getLogger(__name__)


@dataclass
class ExposureSnapshot:
    """Current portfolio exposure state."""

    # Sector weights: {sector: weight_pct}
    sector_weights: Dict[str, float] = field(
        default_factory=dict,
    )

    # Beta exposure
    portfolio_beta: float = 1.0
    high_beta_weight: float = 0.0  # pct in beta > 1.3

    # Earnings exposure
    earnings_48h_tickers: Set[str] = field(
        default_factory=set,
    )
    earnings_48h_weight: float = 0.0

    # Gross / net
    gross_exposure: float = 0.0  # sum(abs(weight))
    net_exposure: float = 0.0    # long - short
    long_weight: float = 0.0
    short_weight: float = 0.0

    # Correlation buckets: {bucket_name: [tickers]}
    correlated_clusters: Dict[str, List[str]] = field(
        default_factory=dict,
    )

    # Open count
    open_positions: int = 0
    max_positions: int = 15

    def to_dict(self) -> Dict[str, Any]:
        return {
            "sector_weights": self.sector_weights,
            "portfolio_beta": round(self.portfolio_beta, 2),
            "high_beta_weight": round(
                self.high_beta_weight, 3,
            ),
            "earnings_48h_tickers": list(
                self.earnings_48h_tickers,
            ),
            "earnings_48h_weight": round(
                self.earnings_48h_weight, 3,
            ),
            "gross_exposure": round(self.gross_exposure, 2),
            "net_exposure": round(self.net_exposure, 2),
            "long_weight": round(self.long_weight, 3),
            "short_weight": round(self.short_weight, 3),
            "open_positions": self.open_positions,
            "max_positions": self.max_positions,
        }


class PortfolioRiskBudget:
    """
    Book-level risk limits and marginal sizing.

    All limits are expressed as fractions of total equity.
    check_budget() returns {allowed, size_scalar, violations,
    budget_remaining} so the caller can decide whether to
    enter, reduce size, or skip.
    """

    DEFAULT_LIMITS = {
        "max_single_position": 0.05,     # 5 %
        "max_sector_weight": 0.30,       # 30 %
        "max_high_beta_weight": 0.25,    # 25 %
        "max_earnings_48h_weight": 0.10, # 10 %
        "max_correlated_bucket": 3,      # max names
        "max_gross_risk_off": 0.50,      # 50 %
        "max_positions": 15,
        "portfolio_beta_limit": 1.50,    # vs SPY
    }

    def __init__(
        self,
        limits: Optional[Dict[str, float]] = None,
    ):
        self.limits = {**self.DEFAULT_LIMITS, **(limits or {})}

    # ── main entry-point ────────────────────────────────────
    def check_budget(
        self,
        ticker: str,
        sector: str,
        position_weight: float,
        exposure: "ExposureSnapshot",
        regime_risk: str = "neutral",
        beta: float = 1.0,
        days_to_earnings: int = 999,
        correlation_bucket: str = "",
    ) -> Dict[str, Any]:
        """
        Check if adding *ticker* at *position_weight* would
        breach any book-level limit.

        Returns
        -------
        dict with keys:
            allowed        – bool
            size_scalar    – 0.0-1.0 suggested reduction
            violations     – list[str] human-readable
            budget_remaining – dict of headroom per limit
        """
        lim = self.limits
        violations: List[str] = []
        scalars: List[float] = [1.0]

        # ── 1. Single-name ──────────────────────────────────
        max_single = lim["max_single_position"]
        if position_weight > max_single:
            scalars.append(max_single / position_weight)
            violations.append(
                f"Position {position_weight:.1%} > "
                f"max {max_single:.0%}",
            )

        # ── 2. Sector concentration ─────────────────────────
        cur_sector = exposure.sector_weights.get(sector, 0)
        new_sector = cur_sector + position_weight
        max_sect = lim["max_sector_weight"]
        if new_sector > max_sect:
            headroom = max(0, max_sect - cur_sector)
            if headroom <= 0:
                violations.append(
                    f"Sector {sector} at {cur_sector:.0%} "
                    f"(limit {max_sect:.0%})",
                )
                scalars.append(0.0)
            else:
                scalars.append(headroom / position_weight)
                violations.append(
                    f"Sector {sector} near limit: "
                    f"{new_sector:.0%} > {max_sect:.0%}",
                )

        # ── 3. High-beta cluster ────────────────────────────
        if beta > 1.3:
            new_hb = exposure.high_beta_weight + position_weight
            max_hb = lim["max_high_beta_weight"]
            if new_hb > max_hb:
                headroom = max(
                    0, max_hb - exposure.high_beta_weight,
                )
                if headroom <= 0:
                    violations.append(
                        f"High-beta at "
                        f"{exposure.high_beta_weight:.0%} "
                        f"(limit {max_hb:.0%})",
                    )
                    scalars.append(0.0)
                else:
                    scalars.append(headroom / position_weight)

        # ── 4. Earnings-within-48h ──────────────────────────
        if days_to_earnings <= 2:
            new_earn = (
                exposure.earnings_48h_weight + position_weight
            )
            max_earn = lim["max_earnings_48h_weight"]
            if new_earn > max_earn:
                headroom = max(
                    0, max_earn - exposure.earnings_48h_weight,
                )
                if headroom <= 0:
                    violations.append(
                        f"Earnings-48h exposure at "
                        f"{exposure.earnings_48h_weight:.0%}",
                    )
                    scalars.append(0.0)
                else:
                    scalars.append(headroom / position_weight)

        # ── 5. Correlation bucket ───────────────────────────
        if correlation_bucket:
            bucket_names = exposure.correlated_clusters.get(
                correlation_bucket, [],
            )
            max_bucket = int(lim["max_correlated_bucket"])
            if len(bucket_names) >= max_bucket:
                violations.append(
                    f"Correlation bucket "
                    f"'{correlation_bucket}' already has "
                    f"{len(bucket_names)} names "
                    f"(cap {max_bucket})",
                )
                scalars.append(0.0)

        # ── 6. Gross exposure in risk-off ───────────────────
        if regime_risk == "risk_off":
            new_gross = (
                exposure.gross_exposure + position_weight
            )
            max_gross = lim["max_gross_risk_off"]
            if new_gross > max_gross:
                headroom = max(
                    0, max_gross - exposure.gross_exposure,
                )
                if headroom <= 0:
                    violations.append(
                        f"Gross {exposure.gross_exposure:.0%}"
                        f" in risk-off "
                        f"(limit {max_gross:.0%})",
                    )
                    scalars.append(0.0)
                else:
                    scalars.append(headroom / position_weight)

        # ── 7. Max positions ────────────────────────────────
        if exposure.open_positions >= lim["max_positions"]:
            violations.append(
                f"At max positions "
                f"({int(lim['max_positions'])})",
            )
            scalars.append(0.0)

        # ── 8. Portfolio beta ───────────────────────────────
        beta_lim = lim["portfolio_beta_limit"]
        if exposure.portfolio_beta > beta_lim:
            # Already over beta limit → scale down
            scalar = max(
                beta_lim / exposure.portfolio_beta, 0.0,
            )
            scalars.append(scalar)
            violations.append(
                f"Portfolio beta {exposure.portfolio_beta:.2f}"
                f" > {beta_lim:.2f}",
            )

        # Final scalar = most restrictive
        size_scalar = max(min(scalars), 0.0)
        allowed = size_scalar > 0

        budget_remaining = {
            "sector": round(
                max(0, max_sect - cur_sector), 4,
            ),
            "high_beta": round(
                max(
                    0,
                    lim["max_high_beta_weight"]
                    - exposure.high_beta_weight,
                ),
                4,
            )
            if beta > 1.3
            else 1.0,
            "earnings_48h": round(
                max(
                    0,
                    lim["max_earnings_48h_weight"]
                    - exposure.earnings_48h_weight,
                ),
                4,
            )
            if days_to_earnings <= 2
            else 1.0,
            "gross_risk_off": round(
                max(
                    0,
                    lim["max_gross_risk_off"]
                    - exposure.gross_exposure,
                ),
                4,
            )
            if regime_risk == "risk_off"
            else 1.0,
            "positions": max(
                0,
                int(lim["max_positions"])
                - exposure.open_positions,
            ),
        }

        return {
            "allowed": allowed,
            "size_scalar": round(size_scalar, 3),
            "violations": violations,
            "budget_remaining": budget_remaining,
        }

    # ── exposure builder ────────────────────────────────────
    def build_exposure(
        self,
        positions: List[Dict[str, Any]],
        equity: float = 100_000.0,
    ) -> "ExposureSnapshot":
        """
        Build ExposureSnapshot from a list of position dicts.

        Each dict should have:
          ticker, sector, market_value, direction,
          beta (opt), days_to_earnings (opt),
          correlation_bucket (opt)
        """
        snap = ExposureSnapshot()
        snap.max_positions = int(self.limits["max_positions"])
        snap.open_positions = len(positions)

        if equity <= 0:
            return snap

        sectors: Dict[str, float] = {}
        high_beta_val = 0.0
        long_val = 0.0
        short_val = 0.0
        earn_val = 0.0
        clusters: Dict[str, List[str]] = {}
        weighted_beta = 0.0

        for pos in positions:
            mv = abs(pos.get("market_value", 0))
            weight = mv / equity
            sector = pos.get("sector", "Unknown")
            b = pos.get("beta", 1.0)
            direction = pos.get("direction", "LONG")
            dte = pos.get("days_to_earnings", 999)
            bucket = pos.get("correlation_bucket", "")
            tkr = pos.get("ticker", "")

            sectors[sector] = sectors.get(sector, 0) + weight
            weighted_beta += b * weight

            if b > 1.3:
                high_beta_val += mv

            if direction == "LONG":
                long_val += mv
            else:
                short_val += mv

            if dte <= 2:
                snap.earnings_48h_tickers.add(tkr)
                earn_val += mv

            if bucket:
                clusters.setdefault(bucket, []).append(tkr)

        snap.sector_weights = {
            k: round(v, 4) for k, v in sectors.items()
        }
        snap.high_beta_weight = round(
            high_beta_val / equity, 4,
        )
        snap.long_weight = round(long_val / equity, 4)
        snap.short_weight = round(short_val / equity, 4)
        snap.gross_exposure = round(
            (long_val + short_val) / equity, 4,
        )
        snap.net_exposure = round(
            (long_val - short_val) / equity, 4,
        )
        snap.earnings_48h_weight = round(
            earn_val / equity, 4,
        )
        snap.portfolio_beta = round(
            weighted_beta if positions else 1.0, 3,
        )
        snap.correlated_clusters = clusters

        return snap
