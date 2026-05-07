"""Options analysis — Greeks, strategy payoff, IV surface."""

from __future__ import annotations

import math
from dataclasses import dataclass
from typing import List, Optional


@dataclass
class Greeks:
    """Option Greeks snapshot."""
    delta: float
    gamma: float
    theta: float
    vega: float
    rho: float


def black_scholes_greeks(
    spot: float,
    strike: float,
    dte: int,
    iv: float,
    rf: float = 0.045,
    is_call: bool = True,
) -> Greeks:
    """Compute Black-Scholes Greeks for a European option."""
    from scipy.stats import norm

    T = max(dte / 365, 1e-6)
    d1 = (
        (math.log(spot / strike) + (rf + iv**2 / 2) * T)
        / (iv * math.sqrt(T))
    )
    d2 = d1 - iv * math.sqrt(T)

    nd1 = norm.pdf(d1)
    Nd1 = norm.cdf(d1)
    Nd2 = norm.cdf(d2)

    if is_call:
        delta = Nd1
        rho = strike * T * math.exp(-rf * T) * Nd2 / 100
    else:
        delta = Nd1 - 1
        rho = -strike * T * math.exp(-rf * T) * norm.cdf(-d2) / 100

    gamma = nd1 / (spot * iv * math.sqrt(T))
    theta = (
        -(spot * nd1 * iv) / (2 * math.sqrt(T))
        - rf * strike * math.exp(-rf * T) * (Nd2 if is_call else norm.cdf(-d2))
    ) / 365
    vega = spot * nd1 * math.sqrt(T) / 100

    return Greeks(
        delta=round(delta, 4),
        gamma=round(gamma, 6),
        theta=round(theta, 4),
        vega=round(vega, 4),
        rho=round(rho, 4),
    )


def strategy_payoff(
    legs: List[dict],
    spot_range: Optional[List[float]] = None,
    spot: float = 100,
) -> List[dict]:
    """Compute payoff at expiry for a multi-leg strategy.

    Each leg: {"type": "CALL"|"PUT", "strike": float,
               "side": "BUY"|"SELL", "premium": float, "qty": int}
    """
    if spot_range is None:
        spot_range = [
            round(spot * (0.8 + i * 0.02), 2)
            for i in range(21)
        ]

    results = []
    for s in spot_range:
        pnl = 0.0
        for leg in legs:
            k = leg["strike"]
            prem = leg.get("premium", 0)
            qty = leg.get("qty", 1)
            mult = 1 if leg["side"] == "BUY" else -1

            if leg["type"] == "CALL":
                intrinsic = max(0, s - k)
            else:
                intrinsic = max(0, k - s)

            pnl += mult * qty * (intrinsic - prem) * 100

        results.append({"spot": s, "pnl": round(pnl, 2)})

    return results
