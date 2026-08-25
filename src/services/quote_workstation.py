"""Six-panel quote workstation — single-ticker command view."""

from __future__ import annotations

import asyncio
import logging
from datetime import datetime, timezone
from typing import Any, Dict

logger = logging.getLogger(__name__)

_PANEL_TIMEOUT = 10.0
_INTEL_TIMEOUT_SEC = 18.0


async def _panel(coro, label: str, timeout: float = _PANEL_TIMEOUT):
    try:
        return await asyncio.wait_for(coro, timeout=timeout)
    except asyncio.TimeoutError:
        return {"error": f"{label} timed out"}
    except Exception as exc:
        return {"error": str(exc)[:120]}


async def build_quote_workstation(request, ticker: str) -> Dict[str, Any]:
    """Aggregate six panels in parallel for low latency."""
    sym = ticker.strip().upper()

    async def _quote():
        from src.api.routers.live_quotes import live_quote

        return await live_quote(sym, request)

    async def _perf():
        from src.api.routers.live_quotes import live_perf_vs_spy

        return await live_perf_vs_spy(sym, request, period="6mo")

    async def _chart():
        from src.api.routers.live_chart import live_chart_data

        return await live_chart_data(sym, request, period="6mo", interval="1d")

    async def _options():
        from src.api.routers.live_brief_options import live_options

        return await live_options(sym, request)

    async def _intel():
        from src.services.stock_intel import build_stock_intel

        intel = await build_stock_intel(request, sym)
        return {
            "decision_bar": intel.get("decision_bar"),
            "confluence": intel.get("confluence"),
            "unified_decision": intel.get("unified_decision"),
            "smart_money": intel.get("smart_money"),
        }

    async def _regime():
        from src.services.regime_service import get_regime

        regime = await get_regime(request)
        return {
            "label": getattr(regime, "regime", "—"),
            "should_trade": getattr(regime, "should_trade", False),
            "vix": getattr(regime, "vix", None),
            "breadth_pct": getattr(regime, "breadth_pct", None),
            "tradeability": getattr(regime, "tradeability", "WAIT"),
        }

    keys = ("quote", "performance", "chart", "options", "intel", "regime")
    coros = (
        _panel(_quote(), "quote", 6.0),
        _panel(_perf(), "performance", 12.0),
        _panel(_chart(), "chart", 10.0),
        _panel(_options(), "options", 8.0),
        _panel(_intel(), "intel", _INTEL_TIMEOUT_SEC),
        _panel(_regime(), "regime", 6.0),
    )
    results = await asyncio.gather(*coros, return_exceptions=True)

    panels: Dict[str, Any] = {}
    for key, res in zip(keys, results):
        if isinstance(res, Exception):
            panels[key] = {"error": str(res)[:120]}
        else:
            panels[key] = res

    return {
        "ticker": sym,
        "as_of": datetime.now(timezone.utc).isoformat() + "Z",
        "panels": {
            "1_quote": panels.get("quote"),
            "2_chart": panels.get("chart"),
            "3_performance_vs_spy": panels.get("performance"),
            "4_options": panels.get("options"),
            "5_intel_decision": panels.get("intel"),
            "6_regime": panels.get("regime"),
        },
        "panel_order": [
            "1_quote",
            "2_chart",
            "3_performance_vs_spy",
            "4_options",
            "5_intel_decision",
            "6_regime",
        ],
    }
