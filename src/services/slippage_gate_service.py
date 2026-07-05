"""
Slippage Gate Service
======================
Pre-trade hard/soft gate before sending an order to IBKR.

Inputs:
  - ticker, size_shares, side, current_price
  - market_data singleton (for ADV + last 5d bar)

Rules (institutional defaults):
  HARD_BLOCK   spread_bps > 50          (illiquid; refuse)
  HARD_BLOCK   participation > 10%      (>10% of ADV; refuse)
  SOFT_WARN    spread_bps > 25          (warn but allow)
  SOFT_WARN    participation > 5%       (warn but allow)
  SOFT_WARN    total_cost > 20bps       (warn; round-trip > 40bps)
  PASS         else

Returns deterministic dict with verdict + reasons + estimate.
"""

from __future__ import annotations

import logging
from typing import Any, Dict

from src.research_lab.slippage import estimate_slippage

logger = logging.getLogger(__name__)

# Thresholds (single source of truth)
HARD_SPREAD_BPS = 50.0
HARD_PARTICIPATION = 0.10
SOFT_SPREAD_BPS = 25.0
SOFT_PARTICIPATION = 0.05
SOFT_TOTAL_COST_BPS = 20.0


async def check_slippage(
    ticker: str,
    size_shares: int,
    current_price: float,
    market_data,  # MarketDataService singleton
    side: str = "BUY",
) -> Dict[str, Any]:
    """
    Pre-trade slippage check.

    Returns:
      {
        verdict: 'PASS' | 'WARN' | 'BLOCK',
        reasons: [str, ...],
        spread_bps: float, participation_pct: float,
        avg_daily_volume: int, estimate: {...},
        thresholds: {...},
      }
    """
    from datetime import datetime, timezone

    as_of = datetime.now(timezone.utc).isoformat() + "Z"
    reasons: list[str] = []
    verdict = "PASS"

    ticker = (ticker or "").upper().strip()
    if not ticker or size_shares <= 0 or current_price <= 0:
        return {
            "verdict": "BLOCK",
            "reasons": ["Invalid inputs (ticker/size/price)."],
            "as_of": as_of,
        }

    # ── Pull 5-day bar to estimate ADV + spread proxy ──
    adv = 0
    spread_bps = 50.0  # conservative default if data missing
    try:
        hist = await market_data.get_history(ticker, period="1mo", interval="1d")
        if hist is not None and len(hist) > 0:
            v_col = "Volume" if "Volume" in hist.columns else "volume"
            h_col = "High" if "High" in hist.columns else "high"
            l_col = "Low" if "Low" in hist.columns else "low"
            c_col = "Close" if "Close" in hist.columns else "close"

            vols = hist[v_col].dropna().astype(float)
            adv = int(vols.tail(20).mean()) if len(vols) >= 5 else int(vols.mean())

            # Proxy spread from intraday range (no L2 data) — last 5 bars
            tail = hist.tail(5)
            if not tail.empty:
                ranges = (tail[h_col] - tail[l_col]) / tail[c_col].replace(0, 1)
                avg_range_pct = float(ranges.mean())
                # Realistic spread is much tighter than range — use 5% of range as proxy
                spread_bps = max(2.0, min(80.0, avg_range_pct * 10000 * 0.05))
    except Exception as exc:
        reasons.append(f"Market-data unavailable ({exc}); using conservative defaults.")
        verdict = "WARN"

    # ── Compute participation + slippage estimate ──
    participation = (size_shares / max(adv, 1)) if adv > 0 else 1.0
    est = estimate_slippage(
        price=current_price,
        size_shares=int(size_shares),
        avg_daily_volume=max(adv, 1),
        avg_spread_pct=spread_bps / 100.0,
    )

    # ── Apply gates ──
    if spread_bps > HARD_SPREAD_BPS:
        verdict = "BLOCK"
        reasons.append(
            f"Spread {spread_bps:.1f}bps > HARD limit {HARD_SPREAD_BPS:.0f}bps "
            f"(illiquid)."
        )
    elif spread_bps > SOFT_SPREAD_BPS:
        if verdict != "BLOCK":
            verdict = "WARN"
        reasons.append(
            f"Spread {spread_bps:.1f}bps > soft {SOFT_SPREAD_BPS:.0f}bps "
            f"(elevated execution cost)."
        )

    if participation > HARD_PARTICIPATION:
        verdict = "BLOCK"
        reasons.append(
            f"Order is {participation * 100:.1f}% of ADV — exceeds HARD limit "
            f"{HARD_PARTICIPATION * 100:.0f}% (material impact)."
        )
    elif participation > SOFT_PARTICIPATION:
        if verdict != "BLOCK":
            verdict = "WARN"
        reasons.append(
            f"Order is {participation * 100:.1f}% of ADV — exceeds soft "
            f"{SOFT_PARTICIPATION * 100:.0f}% (size carefully)."
        )

    if est.total_cost_bps > SOFT_TOTAL_COST_BPS:
        if verdict != "BLOCK":
            verdict = "WARN"
        reasons.append(
            f"Round-trip cost {est.round_trip_bps:.1f}bps "
            f"(one-way {est.total_cost_bps:.1f}bps > soft {SOFT_TOTAL_COST_BPS:.0f}bps)."
        )

    if not reasons:
        reasons.append("All gates passed.")

    return {
        "verdict": verdict,
        "reasons": reasons,
        "ticker": ticker,
        "side": side.upper(),
        "size_shares": int(size_shares),
        "current_price": float(current_price),
        "spread_bps": round(spread_bps, 2),
        "participation_pct": round(participation * 100, 3),
        "avg_daily_volume": int(adv),
        "estimate": {
            "spread_cost_bps": round(est.spread_cost_bps, 2),
            "market_impact_bps": round(est.market_impact_bps, 2),
            "commission_bps": round(est.commission_bps, 2),
            "total_cost_bps": round(est.total_cost_bps, 2),
            "round_trip_bps": round(est.round_trip_bps, 2),
        },
        "thresholds": {
            "hard_spread_bps": HARD_SPREAD_BPS,
            "hard_participation_pct": HARD_PARTICIPATION * 100,
            "soft_spread_bps": SOFT_SPREAD_BPS,
            "soft_participation_pct": SOFT_PARTICIPATION * 100,
            "soft_total_cost_bps": SOFT_TOTAL_COST_BPS,
        },
        "as_of": as_of,
    }
