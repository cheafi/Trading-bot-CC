"""Discord webhook notifier."""
from __future__ import annotations

import logging
from typing import Optional, List, Any

import aiohttp

from src.core.config import get_settings
from src.notifications.formatter import SignalNarrativeFormatter

settings = get_settings()


class DiscordNotifier:
    """Send notifications to Discord via webhook."""

    def __init__(self):
        self.webhook_url = settings.discord_webhook_url
        self.logger = logging.getLogger(__name__)
        self._formatter = SignalNarrativeFormatter()

    @property
    def is_configured(self) -> bool:
        return bool(self.webhook_url)

    async def send_message(self, text: str) -> bool:
        if not self.is_configured:
            return False

        # Discord message limit ~2000 chars
        chunks = self._split_text(text, 1900)

        try:
            async with aiohttp.ClientSession() as session:
                for chunk in chunks:
                    async with session.post(self.webhook_url, json={"content": chunk}) as resp:
                        if resp.status not in (200, 204):
                            body = await resp.text()
                            self.logger.error(f"Discord webhook error {resp.status}: {body[:200]}")
                            return False
            return True
        except Exception as e:
            self.logger.error(f"Discord send error: {e}")
            return False

    async def send_signal(self, signal: Any) -> bool:
        msg = self._formatter.format_signal(signal, as_html=False)
        return await self.send_message(msg)

    async def send_signals_batch(self, signals: List[Any]) -> int:
        if not signals:
            return 0
        success = 0
        for s in signals[:5]:
            if await self.send_signal(s):
                success += 1
        return success

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
