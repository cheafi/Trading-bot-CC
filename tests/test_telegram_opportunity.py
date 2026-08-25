"""Telegram dispatch and opportunity alert behavior."""

from __future__ import annotations

import json
import os
import tempfile
import unittest
from unittest import mock

from src.notifications import telegram as tg
from src.services import opportunity_telegram_alerts as ota


def _deploy_row(ticker: str = "NVDA", **extra) -> dict:
    base = {
        "ticker": ticker,
        "action": "TRADE",
        "score": 8.5,
        "thesis_conf": 0.72,
        "timing_conf": 0.68,
        "risk_reward": 2.8,
        "execution_ready": True,
        "priority_tier": "A",
        "trade_bar": {
            "score_ok": True,
            "thesis_ok": True,
            "timing_ok": True,
            "rr_ok": True,
            "execution_ready": True,
            "passes_trade_bar": True,
        },
    }
    base.update(extra)
    return base


def _watch_row(ticker: str = "AMD", **extra) -> dict:
    base = {
        "ticker": ticker,
        "action": "WATCH",
        "score": 7.4,
        "thesis_conf": 0.55,
        "timing_conf": 0.52,
        "risk_reward": 2.1,
        "execution_ready": False,
        "priority_tier": "High",
        "whats_missing": "timing not fully confirmed",
    }
    base.update(extra)
    return base


class TestTelegramDispatch(unittest.TestCase):
    def test_unconfigured_when_no_env(self):
        with mock.patch.dict("os.environ", {}, clear=True):
            self.assertFalse(tg.telegram_is_configured())

    def test_configured_with_token_and_chat(self):
        with mock.patch.dict(
            "os.environ",
            {
                "TELEGRAM_BOT_TOKEN": "123:ABC",
                "TELEGRAM_CHAT_ID": "999888",
            },
            clear=True,
        ):
            self.assertTrue(tg.telegram_is_configured())
            st = tg.telegram_config_status()
            self.assertTrue(st["telegram_configured"])
            self.assertTrue(st["chat_id_valid"])

    def test_validate_ticker_rejects_invalid(self):
        self.assertIsNone(tg.validate_ticker(""))
        self.assertIsNone(tg.validate_ticker("bad ticker!"))
        self.assertEqual(tg.validate_ticker("nvda"), "NVDA")

    def test_dedupe_blocks_repeat(self):
        tg._DEDUPE.clear()
        with mock.patch.dict("os.environ", {"TELEGRAM_ALERT_COOLDOWN_SEC": "300"}, clear=True):
            self.assertFalse(tg.dedupe_blocked_for_alert("deploy", "NVDA", "A"))
            self.assertTrue(tg.dedupe_blocked_for_alert("deploy", "NVDA", "A"))

    def test_send_message_async_success(self):
        async def _run():
            with mock.patch.dict(
                "os.environ",
                {"TELEGRAM_BOT_TOKEN": "1:a", "TELEGRAM_CHAT_ID": "1"},
                clear=True,
            ):
                class FakeResp:
                    status = 200

                    async def json(self):
                        return {"ok": True}

                    async def text(self):
                        return ""

                    async def __aenter__(self):
                        return self

                    async def __aexit__(self, *args):
                        return False

                class FakeSession:
                    async def __aenter__(self):
                        return self

                    async def __aexit__(self, *args):
                        return False

                    def post(self, url, json=None):
                        self.url = url
                        self.payload = json
                        return FakeResp()

                with mock.patch("aiohttp.ClientSession", FakeSession):
                    ok = await tg.send_message_async("hello")
                    self.assertTrue(ok)

        import asyncio

        asyncio.run(_run())

    def test_send_message_async_failure_status(self):
        async def _run():
            with mock.patch.dict(
                "os.environ",
                {"TELEGRAM_BOT_TOKEN": "1:a", "TELEGRAM_CHAT_ID": "1"},
                clear=True,
            ):
                class FakeResp:
                    status = 400

                    async def json(self):
                        return {"ok": False}

                    async def text(self):
                        return "bad request"

                    async def __aenter__(self):
                        return self

                    async def __aexit__(self, *args):
                        return False

                class FakeSession:
                    async def __aenter__(self):
                        return self

                    async def __aexit__(self, *args):
                        return False

                    def post(self, url, json=None):
                        return FakeResp()

                with mock.patch("aiohttp.ClientSession", FakeSession):
                    ok = await tg.send_message_async("hello")
                    self.assertFalse(ok)

        import asyncio

        asyncio.run(_run())


class TestOpportunityTelegramAlerts(unittest.TestCase):
    def setUp(self):
        self._tmpdir = tempfile.mkdtemp()
        self._state_path = os.path.join(self._tmpdir, "state.json")
        ota._STATE_PATH = self._state_path
        tg._DEDUPE.clear()

    def test_bootstrap_scan_sends_nothing(self):
        payload = {"opportunities": [_deploy_row()]}
        prev = {"tickers": {}}
        alerts = ota._detect_alerts(payload, prev)
        self.assertEqual(alerts, [])

    def test_new_deploy_after_bootstrap(self):
        payload = {"opportunities": [_deploy_row()]}
        prev = {
            "last_scan_ts": "2026-01-01T00:00:00Z",
            "tickers": {},
            "top_ticker": None,
        }
        alerts = ota._detect_alerts(payload, prev)
        self.assertEqual(len(alerts), 1)
        self.assertEqual(alerts[0]["kind"], "deploy")
        self.assertEqual(alerts[0]["ticker"], "NVDA")

    def test_monitor_not_deploy_without_execution_ready(self):
        payload = {"opportunities": [_watch_row()]}
        prev = {"last_scan_ts": "2026-01-01T00:00:00Z", "tickers": {}}
        alerts = ota._detect_alerts(payload, prev)
        self.assertEqual(len(alerts), 1)
        self.assertEqual(alerts[0]["kind"], "monitor")

    def test_deploy_requires_trade_bar(self):
        row = _deploy_row(score=7.0, thesis_conf=0.5, timing_conf=0.5)
        payload = {"opportunities": [row]}
        prev = {"last_scan_ts": "2026-01-01T00:00:00Z", "tickers": {}}
        alerts = ota._detect_alerts(payload, prev)
        self.assertEqual(alerts, [])

    def test_notify_live_playbook_scan_mocked(self):
        payload = {
            "opportunities": [_deploy_row()],
            "board_mode": "full_live",
        }
        with mock.patch.dict(
            "os.environ",
            {"TELEGRAM_BOT_TOKEN": "1:a", "TELEGRAM_CHAT_ID": "1"},
            clear=True,
        ):
            with mock.patch.object(ota, "_load_state") as load_state:
                load_state.side_effect = [
                    {"tickers": {}, "last_scan_ts": "2026-01-01T00:00:00Z"},
                ]
                with mock.patch.object(ota, "_save_state"):
                    with mock.patch.object(ota, "send_message", return_value=True) as send:
                        result = ota.notify_live_playbook_scan(payload)
                        self.assertEqual(result["sent"], 1)
                        send.assert_called_once()
                        body = send.call_args[0][0]
                        self.assertIn("DEPLOY", body)
                        self.assertIn("可部署", body)

    def test_format_message_bilingual_monitor(self):
        text = ota._format_message(
            kind="monitor",
            ticker="AMD",
            tier="High",
            score=7.2,
            rr=2.0,
            blocker="timing",
            headline="New",
        )
        self.assertIn("NOT deploy permission", text)
        self.assertIn("監控", text)


if __name__ == "__main__":
    unittest.main()
