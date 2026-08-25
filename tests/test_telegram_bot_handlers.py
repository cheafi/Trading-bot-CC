"""Telegram inbound command handler tests."""

from __future__ import annotations

import unittest
from unittest import mock

from src.notifications import telegram_bot_handlers as handlers


class TestTelegramBotHandlers(unittest.TestCase):
    def test_start_welcome_includes_branding(self):
        with mock.patch.dict("os.environ", {}, clear=True):
            text = handlers.format_start_welcome(chat_id=123456)
            self.assertIn("CC Live Intelligence", text)
            self.assertIn("Welcome", text)
            self.assertIn("123456", text)
            self.assertIn("TELEGRAM_CHAT_ID", text)

    def test_start_welcome_includes_cc_link(self):
        with mock.patch.dict(
            "os.environ",
            {"CC_PUBLIC_BASE_URL": "https://cc.example.com"},
            clear=True,
        ):
            text = handlers.format_start_welcome(chat_id=1)
            self.assertIn("https://cc.example.com", text)

    def test_unauthorized_for_restricted_chat(self):
        with mock.patch.dict(
            "os.environ",
            {"TELEGRAM_CHAT_ID": "999"},
            clear=True,
        ):
            self.assertFalse(handlers.is_chat_authorized(111))
            reply = handlers.handle_telegram_command(
                "/status",
                111,
                cc_get=lambda p: {},
                cc_post=lambda p: {},
            )
            self.assertIn("Unauthorized", reply)

    def test_start_allowed_for_any_chat(self):
        with mock.patch.dict(
            "os.environ",
            {"TELEGRAM_CHAT_ID": "999"},
            clear=True,
        ):
            reply = handlers.handle_telegram_command(
                "/start",
                111,
                cc_get=lambda p: {},
                cc_post=lambda p: {},
            )
            self.assertIn("Welcome", reply)
            self.assertNotIn("Unauthorized", reply)

    def test_status_includes_deploy_open(self):
        notify = {
            "telegram": {"telegram_configured": True, "cc_base_url_set": True},
            "last_alert_ts": "2026-08-25T08:00:00Z",
            "last_alert_type": "deploy",
        }
        board = {
            "deploy_open": True,
            "tradeability": "TRADE",
            "regime": {"label": "BULL"},
            "gate_reasons": [],
            "system_state": {"blocker_compact": "—"},
        }

        def cc_get(path: str):
            if path.endswith("/status"):
                return notify
            return board

        with mock.patch.dict("os.environ", {"TELEGRAM_CHAT_ID": "1"}, clear=True):
            reply = handlers.handle_telegram_command(
                "/status",
                1,
                cc_get=cc_get,
                cc_post=lambda p: {},
            )
            self.assertIn("OPEN", reply)
            self.assertIn("TRADE", reply)
            self.assertIn("BULL", reply)

    def test_test_command_success(self):
        with mock.patch.dict("os.environ", {"TELEGRAM_CHAT_ID": "1"}, clear=True):
            reply = handlers.handle_telegram_command(
                "/test",
                1,
                cc_get=lambda p: {},
                cc_post=lambda p: {"pushed_to_telegram": True},
            )
            self.assertIn("Test alert dispatched", reply)

    def test_normalize_command_strips_bot_suffix(self):
        self.assertEqual(handlers.normalize_command("/start@TradingAI_AlertsCC_bot"), "/start")


if __name__ == "__main__":
    unittest.main()
