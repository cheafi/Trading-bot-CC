"""Slippage and execution cost models."""

from __future__ import annotations

import math
from dataclasses import dataclass
from typing import Optional


@dataclass
class SlippageEstimate:
    """Estimated execution costs for a trade."""
    spread_cost_bps: float       # half bid-ask spread
    market_impact_bps: float     # price impact from order size
    commission_bps: float        # broker commission
    total_cost_bps: float        # all-in one-way cost

    @property
    def round_trip_bps(self) -> float:
        return self.total_cost_bps * 2


def estimate_slippage(
    price: float,
    size_shares: int,
    avg_daily_volume: int,
    avg_spread_pct: float = 0.05,
    commission_per_share: float = 0.005,
) -> SlippageEstimate:
    """Estimate all-in execution cost.

    Parameters
    ----------
    price : float
        Current mid price.
    size_shares : int
        Order size in shares.
    avg_daily_volume : int
        Average daily volume.
    avg_spread_pct : float
        Average bid-ask spread as % of mid.
    commission_per_share : float
        Broker commission per share.
    """
    # Spread cost = half the spread
    spread_bps = avg_spread_pct * 100 / 2

    # Market impact (square-root model)
    participation = (
        size_shares / max(avg_daily_volume, 1)
    )
    impact_bps = 10 * math.sqrt(participation) * 100

    # Commission
    comm_bps = (
        commission_per_share / max(price, 0.01) * 10000
    )

    total = spread_bps + impact_bps + comm_bps

    return SlippageEstimate(
        spread_cost_bps=round(spread_bps, 2),
        market_impact_bps=round(impact_bps, 2),
        commission_bps=round(comm_bps, 2),
        total_cost_bps=round(total, 2),
    )
