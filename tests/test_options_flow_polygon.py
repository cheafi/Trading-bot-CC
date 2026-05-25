from __future__ import annotations

import asyncio
import os
import sys
from datetime import date, timedelta
from unittest.mock import patch

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from src.services.options_flow_polygon import PolygonOptionsFlowProvider


def _sample_chain(underlying: str = "AAPL") -> dict:
    expiry = (date.today() + timedelta(days=14)).isoformat()
    return {
        "results": [
            {
                "details": {
                    "ticker": f"O:{underlying}{expiry.replace('-', '')}C00250000",
                    "contract_type": "call",
                    "strike_price": 250.0,
                    "expiration_date": expiry,
                },
                "day": {
                    "volume": 1200,
                    "vwap": 2.50,
                    "change_percent": 3.5,
                },
                "open_interest": 4500,
                "last_quote": {"bid": 2.45, "ask": 2.55, "midpoint": 2.50},
                "underlying_asset": {"price": 238.0},
                "greeks": {"implied_volatility": 0.32},
            },
            {
                "details": {
                    "contract_type": "put",
                    "strike_price": 230.0,
                    "expiration_date": expiry,
                },
                "day": {"volume": 10, "vwap": 0.50},
                "open_interest": 100,
            },
        ]
    }


def test_polygon_normalizes_high_volume_contracts():
    provider = PolygonOptionsFlowProvider(api_key="test-key")

    class FakeResp:
        status = 200

        async def json(self):
            return _sample_chain("AAPL")

        async def text(self):
            return ""

        async def __aenter__(self):
            return self

        async def __aexit__(self, *args):
            return False

    class FakeSession:
        def get(self, url, params=None):
            return FakeResp()

        async def __aenter__(self):
            return self

        async def __aexit__(self, *args):
            return False

    with patch("aiohttp.ClientSession", return_value=FakeSession()):
        events = asyncio.run(
            provider.fetch_recent_events(["AAPL"], limit=10)
        )

    assert len(events) == 1
    event = events[0]
    assert event.underlying == "AAPL"
    assert event.call_put == "C"
    assert event.premium == 1200 * 2.50 * 100
    assert event.trust.source == "polygon"
    assert event.trust.synthetic is False


def test_polygon_returns_empty_without_api_key():
    provider = PolygonOptionsFlowProvider(api_key="")
    events = asyncio.run(provider.fetch_recent_events(["AAPL"], limit=5))
    assert events == []


def test_polygon_health_without_key():
    provider = PolygonOptionsFlowProvider(api_key="")
    status = asyncio.run(provider.health())
    assert status.enabled is False
    assert status.mode == "unavailable"
