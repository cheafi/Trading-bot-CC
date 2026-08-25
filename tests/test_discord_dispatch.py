"""Discord dispatch — configuration and push behavior."""

from __future__ import annotations

import unittest
from unittest import mock

from src.notifications import discord_dispatch as dd


class TestDiscordDispatch(unittest.TestCase):
    def test_unconfigured_when_no_env(self):
        with mock.patch.dict("os.environ", {}, clear=True):
            self.assertFalse(dd.discord_is_configured())

    def test_configured_with_webhook(self):
        with mock.patch.dict(
            "os.environ",
            {"DISCORD_WEBHOOK_URL": "https://discord.com/api/webhooks/x/y"},
            clear=True,
        ):
            self.assertTrue(dd.discord_is_configured())
            st = dd.discord_config_status()
            self.assertEqual(st["mode"], "webhook")

    def test_configured_with_bot_and_channel(self):
        with mock.patch.dict(
            "os.environ",
            {
                "DISCORD_BOT_TOKEN": "token",
                "DISCORD_CHANNEL_ID": "123456",
            },
            clear=True,
        ):
            self.assertTrue(dd.discord_is_configured())
            self.assertEqual(dd.discord_config_status()["mode"], "bot_channel")

    def test_configured_with_bot_and_channel_name(self):
        with mock.patch.dict(
            "os.environ",
            {
                "DISCORD_BOT_TOKEN": "token",
                "DISCORD_CHANNEL_NAME": "Trading CC",
            },
            clear=True,
        ):
            self.assertTrue(dd.discord_is_configured())
            st = dd.discord_config_status()
            self.assertEqual(st["mode"], "bot_channel")
            self.assertEqual(st["channel_name"], "Trading CC")

    def test_cached_channel_id(self):
        with mock.patch.object(dd, "_CHANNEL_CACHE_PATH") as mock_path:
            mock_path.exists.return_value = True
            mock_path.read_text.return_value = '{"channel_id": "999"}'
            with mock.patch.dict("os.environ", {"DISCORD_BOT_TOKEN": "t"}, clear=True):
                self.assertEqual(dd._cached_channel_id(), "999")
                self.assertTrue(dd.discord_is_configured())

    def test_normalize_severity(self):
        self.assertEqual(dd._normalize_severity("HIGH"), "critical")
        self.assertEqual(dd._normalize_severity("warn"), "warning")

    def test_research_muted_by_default(self):
        with mock.patch.dict(
            "os.environ",
            {"DISCORD_WEBHOOK_URL": "https://discord.com/api/webhooks/x/y"},
            clear=True,
        ):
            self.assertFalse(
                dd._should_send("validation", "info")
            )
            self.assertTrue(
                dd._should_send("validation", "warning")
            )

    def test_embed_has_footer(self):
        emb = dd._build_embed(
            title="Test",
            message="Hello",
            severity="info",
            event_type="test",
        )
        self.assertIn("Playbook", emb["footer"]["text"])

    def test_embed_bilingual_zh_summary(self):
        emb = dd._build_embed(
            title="Test",
            message="English body",
            severity="info",
            event_type="test",
            zh_summary="中文摘要",
        )
        self.assertIn("中文摘要", emb["description"])
        self.assertIn("zh-TW", emb["description"])


if __name__ == "__main__":
    unittest.main()
