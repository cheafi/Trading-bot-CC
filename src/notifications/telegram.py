"""Telegram notifier via Bot API."""

from __future__ import annotations

import logging
from typing import Any, List

import aiohttp

from src.core.config import get_settings
from src.notifications.formatter import SignalNarrativeFormatter

settings = get_settings()


class TelegramNotifier:
    """Send notifications through Telegram Bot API."""

    def __init__(self):
        self.bot_token = settings.telegram_bot_token
        self.chat_id = settings.telegram_chat_id
        self.logger = logging.getLogger(__name__)
        self._formatter = SignalNarrativeFormatter()

    @property
    def is_configured(self) -> bool:
        return bool(self.bot_token and self.chat_id)

    async def send_message(self, text: str) -> bool:
        if not self.is_configured:
            self.logger.warning("Telegram notifier not configured")
            return False

        chunks = self._split_text(text, 3500)
        url = f"https://api.telegram.org/bot{self.bot_token}/sendMessage"

        try:
            async with aiohttp.ClientSession() as session:
                for chunk in chunks:
                    payload = {
                        "chat_id": self.chat_id,
                        "text": chunk,
                        "disable_web_page_preview": True,
                    }
                    async with session.post(url, json=payload) as resp:
                        if resp.status != 200:
                            body = await resp.text()
                            self.logger.error(
                                "Telegram send error %s: %s",
                                resp.status,
                                body[:200],
                            )
                            return False
            return True
        except Exception as exc:
            self.logger.error("Telegram send error: %s", exc)
            return False

    async def send_signal(self, signal: Any) -> bool:
        msg = self._formatter.format_signal(signal, as_html=False)
        return await self.send_message(msg)

    async def send_signals_batch(self, signals: List[Any]) -> int:
        if not signals:
            return 0
        sent = 0
        for signal in signals[:3]:
            if await self.send_signal(signal):
                sent += 1
        return sent

    @staticmethod
    def _split_text(text: str, max_len: int) -> List[str]:
        if len(text) <= max_len:
            return [text]

        chunks: List[str] = []
        remaining = text
        while remaining:
            if len(remaining) <= max_len:
                chunks.append(remaining)
                break
            idx = remaining.rfind("\n\n", 0, max_len)
            if idx < 0:
                idx = remaining.rfind(". ", 0, max_len)
            if idx < 0:
                idx = max_len
            chunks.append(remaining[:idx].strip())
            remaining = remaining[idx:].strip()
        return chunks
