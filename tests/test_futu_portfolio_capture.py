"""Tests for Futu portfolio capture parser, advisor, and API."""

from __future__ import annotations

import io
import unittest
from unittest.mock import AsyncMock, MagicMock, patch

from src.services.futu_portfolio_parser import (
    FutuHolding,
    holdings_from_rows,
    parse_futu_text,
    sanitize_ticker,
)


class TestFutuTextParser(unittest.TestCase):
    FIXTURE_US = """
    持仓 Positions
    AAPL  Apple Inc   100   150.50   168.20   +1769.00   +11.8%
    NVDA  NVIDIA      50    420.00   455.30   +1765.00   +8.4%
    """

    FIXTURE_HK = """
    持倉
    00700  腾讯控股  500  320.00  335.50  +7750  +4.8%
    09988  阿里巴巴  200  72.50   68.10   -880   -6.1%
    """

    FIXTURE_EN = """
    Symbol  Qty  Cost  Price  P&L
    TSLA 25 180.00 195.50 +387.50 +8.6%
    MSFT 40 350.00 365.20 +608.00 +4.3%
    """

    def test_sanitize_ticker_us(self):
        self.assertEqual(sanitize_ticker("aapl"), "AAPL")
        self.assertEqual(sanitize_ticker("NVDA"), "NVDA")

    def test_sanitize_ticker_hk_pad(self):
        self.assertEqual(sanitize_ticker("700"), "00700")
        self.assertEqual(sanitize_ticker("00700"), "00700")

    def test_sanitize_rejects_invalid(self):
        self.assertIsNone(sanitize_ticker(""))
        self.assertIsNone(sanitize_ticker("TOOLONGTICKERX"))

    def test_parse_us_fixture(self):
        holdings, method = parse_futu_text(self.FIXTURE_US)
        self.assertIn(method, ("text_regex", "text_token_scan"))
        tickers = {h.ticker for h in holdings}
        self.assertIn("AAPL", tickers)
        self.assertIn("NVDA", tickers)
        aapl = next(h for h in holdings if h.ticker == "AAPL")
        self.assertEqual(aapl.shares, 100)
        self.assertEqual(aapl.avg_cost, 150.5)

    def test_parse_hk_fixture(self):
        holdings, _ = parse_futu_text(self.FIXTURE_HK)
        tickers = {h.ticker for h in holdings}
        self.assertIn("00700", tickers)
        self.assertIn("09988", tickers)

    def test_parse_en_fixture(self):
        holdings, _ = parse_futu_text(self.FIXTURE_EN)
        tickers = {h.ticker for h in holdings}
        self.assertIn("TSLA", tickers)
        self.assertIn("MSFT", tickers)

    def test_holdings_from_rows(self):
        rows = [
            {"ticker": "aapl", "shares": 10, "avg_cost": 100, "pnl_pct": 5.2},
            {"symbol": "BAD", "shares": 0, "avg_cost": 1},
        ]
        out = holdings_from_rows(rows)
        self.assertEqual(len(out), 1)
        self.assertEqual(out[0].ticker, "AAPL")


class TestFutuVisionMock(unittest.IsolatedAsyncioTestCase):
    async def test_vision_parser_mock(self):
        mock_ai = MagicMock()
        mock_ai.analyze_image_json = AsyncMock(
            return_value={
                "holdings": [
                    {"ticker": "AAPL", "shares": 50, "avg_cost": 150.0, "current_price": 160.0}
                ]
            }
        )
        with patch(
            "src.services.ai_service.get_ai_service",
            return_value=mock_ai,
        ):
            from src.services.futu_portfolio_parser import parse_futu_image_vision

            holdings, method, _ = await parse_futu_image_vision(b"fakepng", "image/png")
        self.assertEqual(method, "vision")
        self.assertEqual(holdings[0].ticker, "AAPL")
        self.assertEqual(holdings[0].shares, 50)


class TestFutuAdvisoryMock(unittest.IsolatedAsyncioTestCase):
    async def test_advisory_is_advisory_only(self):
        from src.services.futu_portfolio_advisor import build_futu_advisory

        mds = MagicMock()
        mds.get_history = AsyncMock(return_value=None)
        holdings = [
            {
                "ticker": "AAPL",
                "shares": 10,
                "avg_cost": 100,
                "market_value": 1100,
                "pnl_pct": 10,
            }
        ]
        mock_ai = MagicMock()
        mock_ai.is_configured = False
        with patch("src.services.ai_service.get_ai_service", return_value=mock_ai):
            result = await build_futu_advisory(holdings, market_data=mds, regime={})
        self.assertTrue(result["advisory_only"])
        self.assertIn("ADVISORY", result["disclaimer_en"])
        self.assertEqual(len(result["advice"]), 1)


class TestFutuCaptureApi(unittest.TestCase):
    def test_api_endpoint_with_ocr_text(self):
        try:
            from starlette.testclient import TestClient
        except ImportError:
            self.skipTest("starlette not installed")
        import sys
        from pathlib import Path

        sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
        from src.api.main import app

        client = TestClient(app)
        png = io.BytesIO(b"\x89PNG\r\n\x1a\n" + b"\x00" * 64)
        r = client.post(
            "/api/v7/portfolio/futu-capture",
            files={"file": ("cap.png", png, "image/png")},
            data={
                "ocr_text": "AAPL 100 150.50 168.20 +1769 11.8%",
                "notify_discord": "false",
            },
        )
        self.assertEqual(r.status_code, 200, r.text)
        body = r.json()
        self.assertTrue(body.get("advisory_only"))
        self.assertGreaterEqual(body.get("count", 0), 1)
        self.assertEqual(body["holdings"][0]["ticker"], "AAPL")

    @patch("src.services.futu_capture_notify.push_notice_async", new_callable=AsyncMock)
    def test_discord_notify_mock(self, mock_push):
        mock_push.return_value = True
        from src.services.futu_capture_notify import notify_futu_capture_discord
        import asyncio

        ok = asyncio.run(
            notify_futu_capture_discord(
                holdings=[{"ticker": "AAPL", "shares": 10, "avg_cost": 100, "pnl_pct": 5}],
                advisory={
                    "portfolio_summary": {"holdings_count": 1, "total_value": 1000},
                    "summary_en": "Test summary",
                    "summary_zh": "測試摘要",
                    "disclaimer_en": "ADVISORY ONLY",
                },
                parse_method="text_regex",
            )
        )
        self.assertTrue(ok)
        mock_push.assert_called_once()


if __name__ == "__main__":
    unittest.main()
