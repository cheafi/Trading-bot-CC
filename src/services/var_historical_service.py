"""
Historical-Simulation VaR Service
==================================
Computes 1-day 95% Value-at-Risk from REAL historical returns of the
current portfolio positions — no normality assumption, no fake covariance.

Method:
  1. Fetch N trading-day closes per position via market_data.get_history()
  2. Compute daily simple returns per ticker
  3. Align dates across all positions (intersection)
  4. Build portfolio daily return = Σ w_i × r_i   (w = current market_value / total)
  5. Return 5th-percentile loss (VaR-95) + average tail (CVaR-95)

Trust tiers (by sample_size of aligned days):
  >= 252 : HISTSIM_FULL       (1y of trading data, institutional standard)
  >= 126 : HISTSIM_HALF       (6mo — acceptable, flagged)
  >=  60 : HISTSIM_SHORT      (3mo — directional only, warning)
  <   60 : INSUFFICIENT       (fall back to parametric on frontend)
"""

from __future__ import annotations

import asyncio
import logging
from typing import Any, Dict, List

import numpy as np

logger = logging.getLogger(__name__)

MIN_SAMPLE_DAYS = 60
TRUSTED_SAMPLE = 252
HALF_SAMPLE = 126


async def compute_historical_var(
    positions: List[Dict[str, Any]],
    market_data,  # MarketDataService instance
    equity: float,
    confidence: float = 0.95,
    lookback_period: str = "1y",
) -> Dict[str, Any]:
    """
    Compute 1-day historical-simulation VaR for a portfolio.

    Args:
        positions: list of dicts with keys {ticker, market_value} (or shares + current_price)
        market_data: app.state.market_data singleton (must expose async get_history)
        equity: portfolio reference equity ($)
        confidence: 0.95 → 5th percentile loss
        lookback_period: yfinance period string ('1y', '6mo', '3mo')

    Returns:
        {
          method: 'historical_sim' | 'insufficient',
          var_95_pct, var_95_dollar, cvar_95_pct, cvar_95_dollar,
          sample_size, tier, lookback_period,
          worst_day_pct, best_day_pct,
          per_ticker_weights: { ticker: weight },
          warning: str | None,
          as_of: ISO timestamp,
        }
    """
    from datetime import datetime, timezone

    as_of = datetime.now(timezone.utc).isoformat() + "Z"

    if not positions:
        return {
            "method": "insufficient",
            "warning": "No positions to compute VaR for.",
            "sample_size": 0,
            "tier": "EMPTY",
            "as_of": as_of,
        }

    # ── Normalise positions: extract ticker + market_value ──
    normalised: List[Dict[str, float]] = []
    total_mv = 0.0
    for p in positions:
        ticker = (p.get("ticker") or p.get("symbol") or "").upper().strip()
        if not ticker:
            continue
        mv = p.get("market_value")
        if mv is None:
            px = (
                p.get("current_price")
                or p.get("last_price")
                or p.get("entry_price")
                or 0
            )
            sh = p.get("shares") or p.get("quantity") or 0
            mv = float(px) * float(sh)
        mv = abs(float(mv))  # gross exposure (long-only assumption for v1)
        if mv <= 0:
            continue
        normalised.append({"ticker": ticker, "market_value": mv})
        total_mv += mv

    if not normalised or total_mv <= 0:
        return {
            "method": "insufficient",
            "warning": "All positions have zero market value.",
            "sample_size": 0,
            "tier": "EMPTY",
            "as_of": as_of,
        }

    # ── Fetch histories in parallel ──
    tasks = [
        market_data.get_history(p["ticker"], period=lookback_period, interval="1d")
        for p in normalised
    ]
    try:
        histories = await asyncio.gather(*tasks, return_exceptions=True)
    except Exception as exc:  # pragma: no cover
        logger.warning("historical_var: gather failed: %s", exc)
        return {
            "method": "insufficient",
            "warning": f"Failed to fetch histories: {exc}",
            "sample_size": 0,
            "tier": "ERROR",
            "as_of": as_of,
        }

    # ── Build per-ticker daily return series ──
    returns_by_ticker: Dict[str, "pd.Series"] = {}
    weights: Dict[str, float] = {}
    failed: List[str] = []

    for pos, hist in zip(normalised, histories):
        t = pos["ticker"]
        if isinstance(hist, Exception) or hist is None or len(hist) == 0:
            failed.append(t)
            continue
        c_col = "Close" if "Close" in hist.columns else "close"
        closes = hist[c_col].dropna()
        if len(closes) < 2:
            failed.append(t)
            continue
        rets = closes.pct_change().dropna()
        if len(rets) < MIN_SAMPLE_DAYS // 2:
            failed.append(t)
            continue
        returns_by_ticker[t] = rets
        weights[t] = pos["market_value"] / total_mv

    if not returns_by_ticker:
        return {
            "method": "insufficient",
            "warning": f"No usable historical data (failed: {failed}).",
            "sample_size": 0,
            "tier": "NO_DATA",
            "failed_tickers": failed,
            "as_of": as_of,
        }

    # ── Re-normalise weights over surviving tickers ──
    wsum = sum(weights.values())
    if wsum <= 0:
        return {
            "method": "insufficient",
            "warning": "Weight sum is zero after filtering.",
            "sample_size": 0,
            "tier": "EMPTY",
            "as_of": as_of,
        }
    weights = {t: w / wsum for t, w in weights.items()}

    # ── Align on date intersection ──
    import pandas as pd

    aligned = pd.DataFrame(returns_by_ticker).dropna(how="any")
    sample_size = len(aligned)

    if sample_size < MIN_SAMPLE_DAYS:
        return {
            "method": "insufficient",
            "warning": (
                f"Only {sample_size} aligned trading days "
                f"(need ≥{MIN_SAMPLE_DAYS}). Use parametric fallback."
            ),
            "sample_size": sample_size,
            "tier": "INSUFFICIENT",
            "failed_tickers": failed,
            "as_of": as_of,
        }

    # ── Portfolio daily return series ──
    w_array = np.array([weights[t] for t in aligned.columns])
    port_returns = (aligned.values * w_array).sum(axis=1)  # shape: (sample_size,)

    # ── 5th-percentile loss = VaR-95 (one-sided) ──
    alpha = 1 - confidence  # 0.05
    var_pct = float(np.percentile(port_returns, alpha * 100))  # negative number
    tail = port_returns[port_returns <= var_pct]
    cvar_pct = float(np.mean(tail)) if len(tail) > 0 else var_pct

    worst = float(np.min(port_returns))
    best = float(np.max(port_returns))

    # ── Tier classification ──
    if sample_size >= TRUSTED_SAMPLE:
        tier = "HISTSIM_FULL"
        warning = None
    elif sample_size >= HALF_SAMPLE:
        tier = "HISTSIM_HALF"
        warning = f"Only {sample_size} aligned days (<252). Confidence reduced."
    else:
        tier = "HISTSIM_SHORT"
        warning = f"Only {sample_size} aligned days (<126). Directional only."

    if failed:
        extra = f" Excluded tickers (no data): {failed}."
        warning = (warning + extra) if warning else extra.strip()

    return {
        "method": "historical_sim",
        "tier": tier,
        "sample_size": sample_size,
        "lookback_period": lookback_period,
        "confidence": confidence,
        "var_95_pct": round(var_pct * 100, 3),  # negative = loss
        "var_95_dollar": round(equity * var_pct, 2),
        "cvar_95_pct": round(cvar_pct * 100, 3),
        "cvar_95_dollar": round(equity * cvar_pct, 2),
        "worst_day_pct": round(worst * 100, 3),
        "best_day_pct": round(best * 100, 3),
        "weights": {t: round(w, 4) for t, w in weights.items()},
        "n_positions_used": len(returns_by_ticker),
        "n_positions_failed": len(failed),
        "failed_tickers": failed,
        "warning": warning,
        "as_of": as_of,
    }
