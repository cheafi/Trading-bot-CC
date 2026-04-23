"""FRED / ALFRED macro data ingestion.

Fetches key macro indicators from the Federal Reserve Economic Data API:
- Treasury yields (2Y, 5Y, 10Y, 30Y)
- Fed Funds Rate
- CPI / inflation
- Unemployment rate
- GDP growth
- VIX (from FRED mirror)
- Credit spreads (BAA-AAA)
- ISM Manufacturing

Requires FRED_API_KEY environment variable.
Free key: https://fred.stlouisfed.org/docs/api/api_key.html
"""

from __future__ import annotations

import logging
import os
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from typing import Any, Optional

logger = logging.getLogger(__name__)

__all__ = ["FredClient", "MacroSnapshot", "FRED_SERIES"]


# ═══════════════════════════════════════════════════════════════
# Series definitions
# ═══════════════════════════════════════════════════════════════

FRED_SERIES: dict[str, dict[str, str]] = {
    "DGS2": {"name": "2-Year Treasury Yield", "category": "rates", "frequency": "daily"},
    "DGS5": {"name": "5-Year Treasury Yield", "category": "rates", "frequency": "daily"},
    "DGS10": {"name": "10-Year Treasury Yield", "category": "rates", "frequency": "daily"},
    "DGS30": {"name": "30-Year Treasury Yield", "category": "rates", "frequency": "daily"},
    "DFF": {"name": "Fed Funds Rate", "category": "rates", "frequency": "daily"},
    "T10Y2Y": {"name": "10Y-2Y Spread (yield curve)", "category": "rates", "frequency": "daily"},
    "T10Y3M": {"name": "10Y-3M Spread", "category": "rates", "frequency": "daily"},
    "CPIAUCSL": {"name": "CPI (All Urban)", "category": "inflation", "frequency": "monthly"},
    "CPILFESL": {"name": "Core CPI (ex food & energy)", "category": "inflation", "frequency": "monthly"},
    "PCEPI": {"name": "PCE Price Index", "category": "inflation", "frequency": "monthly"},
    "UNRATE": {"name": "Unemployment Rate", "category": "labor", "frequency": "monthly"},
    "PAYEMS": {"name": "Nonfarm Payrolls", "category": "labor", "frequency": "monthly"},
    "ICSA": {"name": "Initial Jobless Claims", "category": "labor", "frequency": "weekly"},
    "GDP": {"name": "GDP (nominal)", "category": "output", "frequency": "quarterly"},
    "GDPC1": {"name": "Real GDP", "category": "output", "frequency": "quarterly"},
    "VIXCLS": {"name": "VIX", "category": "volatility", "frequency": "daily"},
    "BAMLC0A0CM": {"name": "IG Corporate Spread", "category": "credit", "frequency": "daily"},
    "BAMLH0A0HYM2": {"name": "HY Corporate Spread", "category": "credit", "frequency": "daily"},
    "MANEMP": {"name": "Manufacturing Employment", "category": "manufacturing", "frequency": "monthly"},
    "UMCSENT": {"name": "U Michigan Consumer Sentiment", "category": "sentiment", "frequency": "monthly"},
    "MORTGAGE30US": {"name": "30-Year Mortgage Rate", "category": "rates", "frequency": "weekly"},
    "WALCL": {"name": "Fed Balance Sheet", "category": "liquidity", "frequency": "weekly"},
}


@dataclass(frozen=True)
class MacroSnapshot:
    """Point-in-time macro snapshot."""

    timestamp: str
    indicators: dict[str, Any]
    yield_curve_signal: str  # NORMAL, FLAT, INVERTED
    inflation_trend: str  # RISING, STABLE, FALLING
    labor_trend: str  # STRONG, MIXED, WEAK
    credit_stress: str  # LOW, MODERATE, HIGH
    overall_regime_hint: str  # EXPANSIONARY, LATE_CYCLE, CONTRACTIONARY, RECOVERY

    def to_dict(self) -> dict:
        return {
            "timestamp": self.timestamp,
            "indicators": self.indicators,
            "yield_curve_signal": self.yield_curve_signal,
            "inflation_trend": self.inflation_trend,
            "labor_trend": self.labor_trend,
            "credit_stress": self.credit_stress,
            "overall_regime_hint": self.overall_regime_hint,
        }


# ═══════════════════════════════════════════════════════════════
# Client
# ═══════════════════════════════════════════════════════════════


class FredClient:
    """FRED API client for macro data ingestion.

    Requires FRED_API_KEY env var.
    Falls back to cached/stub data if API unavailable.
    """

    BASE_URL = "https://api.stlouisfed.org/fred/series/observations"

    def __init__(self, api_key: Optional[str] = None) -> None:
        self.api_key = api_key or os.environ.get("FRED_API_KEY", "")
        self._cache: dict[str, dict] = {}
        self._cache_ts: float = 0.0
        self._cache_ttl: float = 3600  # 1 hour

    @property
    def is_configured(self) -> bool:
        return bool(self.api_key)

    async def fetch_series(
        self,
        series_id: str,
        limit: int = 5,
    ) -> list[dict[str, str]]:
        """Fetch recent observations for a FRED series."""
        if not self.is_configured:
            logger.debug(f"[FRED] No API key — skipping {series_id}")
            return []

        try:
            import aiohttp

            params = {
                "series_id": series_id,
                "api_key": self.api_key,
                "file_type": "json",
                "sort_order": "desc",
                "limit": limit,
            }
            async with aiohttp.ClientSession() as session:
                async with session.get(self.BASE_URL, params=params, timeout=aiohttp.ClientTimeout(total=10)) as resp:
                    if resp.status != 200:
                        logger.warning(f"[FRED] {series_id} HTTP {resp.status}")
                        return []
                    data = await resp.json()
                    observations = data.get("observations", [])
                    return [
                        {"date": o["date"], "value": o["value"]}
                        for o in observations
                        if o.get("value", ".") != "."
                    ]
        except Exception as exc:
            logger.debug(f"[FRED] {series_id} error: {exc}")
            return []

    async def fetch_snapshot(
        self,
        series_ids: Optional[list[str]] = None,
    ) -> MacroSnapshot:
        """Fetch a macro snapshot with key indicators.

        Args:
            series_ids: specific series to fetch; defaults to core set
        """
        core_series = series_ids or [
            "DGS2", "DGS10", "DGS30", "DFF", "T10Y2Y",
            "CPIAUCSL", "UNRATE", "VIXCLS",
            "BAMLH0A0HYM2", "ICSA",
        ]

        indicators: dict[str, Any] = {}
        for sid in core_series:
            obs = await self.fetch_series(sid, limit=2)
            meta = FRED_SERIES.get(sid, {"name": sid})
            if obs:
                latest = obs[0]
                try:
                    val = float(latest["value"])
                except (ValueError, KeyError):
                    val = None
                indicators[sid] = {
                    "name": meta.get("name", sid),
                    "value": val,
                    "date": latest.get("date"),
                    "category": meta.get("category", "unknown"),
                }
                # Previous value for trend
                if len(obs) > 1:
                    try:
                        indicators[sid]["previous"] = float(obs[1]["value"])
                    except (ValueError, KeyError):
                        pass

        # Derive signals
        yield_curve = self._classify_yield_curve(indicators)
        inflation = self._classify_inflation(indicators)
        labor = self._classify_labor(indicators)
        credit = self._classify_credit(indicators)
        regime = self._infer_regime(yield_curve, inflation, labor, credit)

        return MacroSnapshot(
            timestamp=datetime.utcnow().isoformat(),
            indicators=indicators,
            yield_curve_signal=yield_curve,
            inflation_trend=inflation,
            labor_trend=labor,
            credit_stress=credit,
            overall_regime_hint=regime,
        )

    # ── Classification helpers ──────────────────────────────

    @staticmethod
    def _classify_yield_curve(ind: dict) -> str:
        spread = ind.get("T10Y2Y", {}).get("value")
        if spread is None:
            return "UNKNOWN"
        if spread < -0.2:
            return "INVERTED"
        if spread < 0.2:
            return "FLAT"
        return "NORMAL"

    @staticmethod
    def _classify_inflation(ind: dict) -> str:
        cpi = ind.get("CPIAUCSL", {})
        val = cpi.get("value")
        prev = cpi.get("previous")
        if val is None or prev is None:
            return "UNKNOWN"
        if val > prev * 1.001:
            return "RISING"
        if val < prev * 0.999:
            return "FALLING"
        return "STABLE"

    @staticmethod
    def _classify_labor(ind: dict) -> str:
        unrate = ind.get("UNRATE", {}).get("value")
        if unrate is None:
            return "UNKNOWN"
        if unrate < 4.5:
            return "STRONG"
        if unrate < 6.0:
            return "MIXED"
        return "WEAK"

    @staticmethod
    def _classify_credit(ind: dict) -> str:
        hy = ind.get("BAMLH0A0HYM2", {}).get("value")
        if hy is None:
            return "UNKNOWN"
        if hy > 6.0:
            return "HIGH"
        if hy > 4.0:
            return "MODERATE"
        return "LOW"

    @staticmethod
    def _infer_regime(yc: str, inflation: str, labor: str, credit: str) -> str:
        if credit == "HIGH" or yc == "INVERTED":
            return "CONTRACTIONARY"
        if labor == "WEAK":
            return "RECOVERY" if inflation == "FALLING" else "CONTRACTIONARY"
        if inflation == "RISING" and labor == "STRONG":
            return "LATE_CYCLE"
        if labor == "STRONG" and yc == "NORMAL":
            return "EXPANSIONARY"
        return "MIXED"
