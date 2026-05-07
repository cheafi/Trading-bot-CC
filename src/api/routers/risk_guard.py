"""
Risk Guard Router — Sprint 100
================================
Live portfolio-level risk gates exposed over REST.

Routes:
  POST /api/v7/risk/correlation-guard  — check new ticker vs open positions
  GET  /api/v7/risk/var-gate           — 1-day 95% VaR vs drawdown limit
  GET  /api/v7/risk/concentration      — HHI + sector weights + grade
  GET  /api/v7/risk/summary            — combined risk dashboard payload
"""

from __future__ import annotations

import asyncio
import logging
import math
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, Depends, Query, Request

from src.api.deps import sanitize_for_json, verify_api_key
from src.core.risk_limits import RISK

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/v7/risk", tags=["risk-guard"])

# ── Helpers ───────────────────────────────────────────────────────────────────

_CORR_GUARD_THRESHOLD = 0.70  # matches copilot-instructions.md
_VAR_CONFIDENCE = 0.95
_TRADING_DAYS_YEAR = 252


def _get_open_positions() -> List[Dict[str, Any]]:
    """Pull open paper positions from fund_persistence."""
    try:
        from src.services.fund_persistence import get_open_paper_positions

        return get_open_paper_positions()
    except Exception as e:
        logger.debug("Could not load open paper positions: %s", e)
        return []


async def _fetch_returns(
    tickers: List[str], period: str = "3mo"
) -> Dict[str, List[float]]:
    """Fetch daily returns for a list of tickers via yfinance."""
    import yfinance as yf

    def _dl():
        data = yf.download(
            tickers, period=period, interval="1d", progress=False, auto_adjust=True
        )
        close = data["Close"] if "Close" in data.columns else data
        return {
            t: close[t].pct_change().dropna().tolist()
            for t in tickers
            if t in close.columns
        }

    try:
        return await asyncio.to_thread(_dl)
    except Exception as e:
        logger.debug("Return fetch failed: %s", e)
        return {}


def _pearson(a: List[float], b: List[float]) -> float:
    """Compute Pearson correlation between two return series."""
    n = min(len(a), len(b))
    if n < 10:
        return 0.0
    a, b = a[-n:], b[-n:]
    mean_a = sum(a) / n
    mean_b = sum(b) / n
    cov = sum((x - mean_a) * (y - mean_b) for x, y in zip(a, b)) / n
    std_a = math.sqrt(sum((x - mean_a) ** 2 for x in a) / n) or 1e-9
    std_b = math.sqrt((sum((y - mean_b) ** 2 for y in b)) / n) or 1e-9
    return round(cov / (std_a * std_b), 4)


def _parametric_var(
    returns: List[float], confidence: float = 0.95, position_usd: float = 10_000.0
) -> float:
    """
    1-day parametric VaR at given confidence level.
    VaR = position × (μ - z × σ)  (negative = loss)
    """
    if len(returns) < 5:
        return 0.0
    n = len(returns)
    mu = sum(returns) / n
    variance = sum((r - mu) ** 2 for r in returns) / n
    sigma = math.sqrt(variance)
    # z-score for 95% one-tail: 1.645
    z = 1.645 if confidence == 0.95 else 2.326
    var_pct = mu - z * sigma  # negative = loss expected
    return round(abs(var_pct) * position_usd, 2)


# ── Endpoints ─────────────────────────────────────────────────────────────────


@router.post("/correlation-guard")
async def correlation_guard(
    ticker: str,
    direction: str = "LONG",
    position_usd: float = Query(10_000.0, ge=0),
    _: bool = Depends(verify_api_key),
) -> Dict[str, Any]:
    """
    Check whether adding `ticker` would breach the 0.70 correlation guard
    against current open paper positions.

    Uses 3-month daily returns. Falls back to sector-heuristic if data unavailable.
    """
    ticker = ticker.upper()
    open_positions = _get_open_positions()
    existing_tickers = list(
        {p.get("ticker", "") for p in open_positions if p.get("ticker")}
    )

    if not existing_tickers:
        return {
            "ticker": ticker,
            "approved": True,
            "reason": "no open positions to correlate against",
            "correlated_pairs": [],
            "max_correlation": None,
        }

    all_tickers = [ticker] + existing_tickers
    returns_map = await _fetch_returns(all_tickers, period="3mo")

    new_returns = returns_map.get(ticker, [])
    correlated: List[Dict[str, Any]] = []

    for existing in existing_tickers:
        existing_returns = returns_map.get(existing, [])
        if new_returns and existing_returns:
            corr = _pearson(new_returns, existing_returns)
        else:
            # Sector-heuristic fallback
            try:
                from src.engines.correlation_risk import get_sector

                corr = 0.65 if get_sector(ticker) == get_sector(existing) else 0.30
            except Exception:
                corr = 0.30

        if abs(corr) >= _CORR_GUARD_THRESHOLD:
            correlated.append(
                {
                    "existing_ticker": existing,
                    "correlation": corr,
                    "breaches_guard": True,
                }
            )
        else:
            correlated.append(
                {
                    "existing_ticker": existing,
                    "correlation": corr,
                    "breaches_guard": False,
                }
            )

    breaches = [c for c in correlated if c["breaches_guard"]]
    max_corr = max((abs(c["correlation"]) for c in correlated), default=0.0)
    approved = len(breaches) == 0

    return sanitize_for_json(
        {
            "ticker": ticker,
            "direction": direction,
            "approved": approved,
            "max_correlation": round(max_corr, 4),
            "threshold": _CORR_GUARD_THRESHOLD,
            "breach_count": len(breaches),
            "correlated_pairs": correlated,
            "reason": (
                f"breaches 0.70 guard with {', '.join(b['existing_ticker'] for b in breaches)}"
                if breaches
                else "within correlation limits"
            ),
        }
    )


@router.get("/var-gate")
async def var_gate(
    account_equity: float = Query(100_000.0, ge=1000.0),
    _: bool = Depends(verify_api_key),
) -> Dict[str, Any]:
    """
    1-day 95% parametric VaR for the current open paper position portfolio.

    Compares total VaR to RISK.max_drawdown_pct × equity to determine
    whether the portfolio is within risk budget.
    """
    open_positions = _get_open_positions()
    if not open_positions:
        return {
            "approved": True,
            "reason": "no open positions",
            "total_var_usd": 0.0,
            "total_var_pct": 0.0,
            "var_budget_usd": round(
                RISK.get("max_drawdown_pct", 0.15) * account_equity, 2
            ),
            "positions": [],
        }

    tickers = list({p.get("ticker", "") for p in open_positions if p.get("ticker")})
    returns_map = await _fetch_returns(tickers, period="3mo")

    max_dd_pct = RISK.get("max_drawdown_pct", 0.15)
    var_budget = max_dd_pct * account_equity
    position_details: List[Dict[str, Any]] = []
    total_var = 0.0

    for pos in open_positions:
        t = pos.get("ticker", "")
        shares = pos.get("shares", 0) or 1
        current_price = pos.get("current_price") or pos.get("entry_price", 100.0)
        pos_usd = shares * current_price
        rets = returns_map.get(t, [])
        var_1d = _parametric_var(rets, _VAR_CONFIDENCE, pos_usd)
        total_var += var_1d
        position_details.append(
            {
                "ticker": t,
                "position_usd": round(pos_usd, 2),
                "var_1d_usd": var_1d,
                "var_1d_pct": round(var_1d / pos_usd * 100, 2) if pos_usd > 0 else 0.0,
            }
        )

    total_var_pct = total_var / account_equity * 100
    approved = total_var <= var_budget

    return sanitize_for_json(
        {
            "approved": approved,
            "total_var_usd": round(total_var, 2),
            "total_var_pct": round(total_var_pct, 3),
            "var_budget_usd": round(var_budget, 2),
            "var_budget_pct": round(max_dd_pct * 100, 1),
            "confidence": _VAR_CONFIDENCE,
            "reason": (
                f"VaR ${total_var:.0f} exceeds budget ${var_budget:.0f}"
                if not approved
                else "within VaR budget"
            ),
            "positions": position_details,
        }
    )


@router.get("/concentration")
async def concentration(
    _: bool = Depends(verify_api_key),
) -> Dict[str, Any]:
    """
    HHI concentration score + sector weights + correlation grade
    for the current open paper portfolio.
    """
    open_positions = _get_open_positions()
    if not open_positions:
        return {
            "grade": "N/A",
            "reason": "no open positions",
            "hhi": 0,
            "sector_weights": {},
        }

    holdings = [
        {
            "ticker": p.get("ticker", ""),
            "market_value": (p.get("shares", 1) or 1)
            * (p.get("current_price") or p.get("entry_price", 100.0)),
        }
        for p in open_positions
    ]

    try:
        from src.engines.correlation_risk import CorrelationRiskEngine

        engine = CorrelationRiskEngine()
        summary = engine.summary(holdings)
        return sanitize_for_json(summary)
    except Exception as e:
        logger.warning("Concentration analysis failed: %s", e)
        return {"error": str(e)}


@router.get("/summary")
async def risk_summary(
    account_equity: float = Query(100_000.0, ge=1000.0),
    _: bool = Depends(verify_api_key),
) -> Dict[str, Any]:
    """
    Combined risk dashboard: VaR gate + concentration grade + open position count.
    """
    open_positions = _get_open_positions()
    n_open = len(open_positions)
    max_positions = RISK.get("max_positions", 10)

    # VaR (re-use logic inline to avoid duplicate yfinance calls)
    tickers = list({p.get("ticker", "") for p in open_positions if p.get("ticker")})
    returns_map = await _fetch_returns(tickers, period="3mo") if tickers else {}
    max_dd_pct = RISK.get("max_drawdown_pct", 0.15)
    var_budget = max_dd_pct * account_equity
    total_var = 0.0
    for pos in open_positions:
        t = pos.get("ticker", "")
        shares = pos.get("shares", 1) or 1
        price = pos.get("current_price") or pos.get("entry_price", 100.0)
        pos_usd = shares * price
        total_var += _parametric_var(returns_map.get(t, []), _VAR_CONFIDENCE, pos_usd)

    # Concentration
    concentration_grade = "N/A"
    if open_positions:
        try:
            from src.engines.correlation_risk import CorrelationRiskEngine

            holdings = [
                {
                    "ticker": p.get("ticker", ""),
                    "market_value": (p.get("shares", 1) or 1)
                    * (p.get("current_price") or p.get("entry_price", 100.0)),
                }
                for p in open_positions
            ]
            concentration_grade = CorrelationRiskEngine().analyse(holdings).grade
        except Exception:
            pass

    gates = {
        "positions_ok": n_open < max_positions,
        "var_ok": total_var <= var_budget,
        "concentration_ok": concentration_grade in ("A", "B", "N/A"),
    }
    all_ok = all(gates.values())

    return sanitize_for_json(
        {
            "all_gates_ok": all_ok,
            "open_positions": n_open,
            "max_positions": max_positions,
            "total_var_usd": round(total_var, 2),
            "var_budget_usd": round(var_budget, 2),
            "concentration_grade": concentration_grade,
            "gates": gates,
        }
    )
