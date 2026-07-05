"""
Fundamental Data Engine — Real Company Financials.

Fetches from yfinance and provides:
1. Revenue / Earnings growth
2. Margins (gross, operating, net)
3. ROE / ROA
4. P/E, P/S, P/B valuation
5. Cash flow quality
6. Debt levels
7. Moat indicators

Cached per ticker (12h TTL).
Used by Expert Council's Fundamental Analyst.
"""

from __future__ import annotations

import logging
import time
from typing import Any, Dict, Optional

logger = logging.getLogger(__name__)

_FUND_CACHE: Dict[str, Dict[str, Any]] = {}
_CACHE_TTL = 3600 * 12  # 12 hours


def get_fundamentals(
    ticker: str,
) -> Dict[str, Any]:
    """
    Get fundamental data for a ticker.

    Returns standardized dict with financial metrics.
    """
    now = time.time()
    cached = _FUND_CACHE.get(ticker)
    if cached and now - cached.get("_ts", 0) < _CACHE_TTL:
        return {k: v for k, v in cached.items() if not k.startswith("_")}

    result = _fetch(ticker)
    result["_ts"] = now
    _FUND_CACHE[ticker] = result
    return {k: v for k, v in result.items() if not k.startswith("_")}


def _fetch(ticker: str) -> Dict[str, Any]:
    """Fetch fundamentals from yfinance."""
    try:
        import yfinance as yf

        t = yf.Ticker(ticker)
        info = t.info or {}

        # Growth
        rev_growth = info.get("revenueGrowth")
        earn_growth = info.get("earningsGrowth")

        # Profitability
        gross_margin = info.get("grossMargins")
        op_margin = info.get("operatingMargins")
        net_margin = info.get("profitMargins")
        roe = info.get("returnOnEquity")
        roa = info.get("returnOnAssets")

        # Valuation
        pe_trailing = info.get("trailingPE")
        pe_forward = info.get("forwardPE")
        ps = info.get("priceToSalesTrailing12Months")
        pb = info.get("priceToBook")

        # Balance sheet
        debt_equity = info.get("debtToEquity")
        current_ratio = info.get("currentRatio")
        free_cf = info.get("freeCashflow")
        market_cap = info.get("marketCap")

        # Quality score (simple composite)
        quality = _calc_quality(
            roe,
            gross_margin,
            debt_equity,
            rev_growth,
            free_cf,
        )

        return {
            "ticker": ticker,
            "source": "yfinance",
            "growth": {
                "revenue_growth": _pct(rev_growth),
                "earnings_growth": _pct(earn_growth),
            },
            "profitability": {
                "gross_margin": _pct(gross_margin),
                "operating_margin": _pct(op_margin),
                "net_margin": _pct(net_margin),
                "roe": _pct(roe),
                "roa": _pct(roa),
            },
            "valuation": {
                "pe_trailing": _rnd(pe_trailing),
                "pe_forward": _rnd(pe_forward),
                "price_to_sales": _rnd(ps),
                "price_to_book": _rnd(pb),
            },
            "balance_sheet": {
                "debt_to_equity": _rnd(debt_equity),
                "current_ratio": _rnd(current_ratio),
                "free_cash_flow": free_cf,
                "market_cap": market_cap,
            },
            "quality_score": quality,
            "moat_indicators": _moat_check(
                gross_margin,
                roe,
                rev_growth,
            ),
        }
    except Exception as e:
        logger.debug(
            "Fundamental fetch failed for %s: %s",
            ticker,
            e,
        )
        return {
            "ticker": ticker,
            "source": "unavailable",
            "error": str(e),
            "quality_score": 50,
        }


def _pct(val: Optional[float]) -> Optional[float]:
    """Convert ratio to percentage."""
    if val is None:
        return None
    return round(val * 100, 2)


def _rnd(val: Optional[float]) -> Optional[float]:
    if val is None:
        return None
    return round(val, 2)


def _calc_quality(
    roe: Optional[float],
    gross_margin: Optional[float],
    debt_equity: Optional[float],
    rev_growth: Optional[float],
    free_cf: Optional[float],
) -> int:
    """
    Simple fundamental quality score 0-100.

    Components:
    - ROE > 15% = good
    - Gross margin > 40% = good
    - Debt/equity < 100% = good
    - Revenue growth > 10% = good
    - Positive free CF = good
    """
    score = 50

    if roe is not None:
        if roe > 0.20:
            score += 12
        elif roe > 0.15:
            score += 8
        elif roe > 0.10:
            score += 3
        elif roe < 0:
            score -= 10

    if gross_margin is not None:
        if gross_margin > 0.60:
            score += 10
        elif gross_margin > 0.40:
            score += 5
        elif gross_margin < 0.20:
            score -= 8

    if debt_equity is not None:
        if debt_equity < 50:
            score += 8
        elif debt_equity < 100:
            score += 3
        elif debt_equity > 200:
            score -= 10

    if rev_growth is not None:
        if rev_growth > 0.20:
            score += 10
        elif rev_growth > 0.10:
            score += 5
        elif rev_growth < 0:
            score -= 5

    if free_cf is not None:
        if free_cf > 0:
            score += 5
        else:
            score -= 5

    return max(0, min(100, score))


def _moat_check(
    gross_margin: Optional[float],
    roe: Optional[float],
    rev_growth: Optional[float],
) -> Dict[str, Any]:
    """Simple moat indicators."""
    indicators = []
    moat_score = 0

    if gross_margin and gross_margin > 0.60:
        indicators.append("High margins — pricing power")
        moat_score += 1
    if roe and roe > 0.20:
        indicators.append("High ROE — capital efficiency")
        moat_score += 1
    if rev_growth and rev_growth > 0.15:
        indicators.append("Strong growth — competitive advantage")
        moat_score += 1

    return {
        "has_moat": moat_score >= 2,
        "moat_score": moat_score,
        "indicators": indicators,
    }
