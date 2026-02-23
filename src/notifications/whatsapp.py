"""WhatsApp notifier via Twilio API."""
from __future__ import annotations

import logging
from typing import Any, List

import aiohttp

from src.core.config import get_settings
from src.notifications.formatter import SignalNarrativeFormatter

settings = get_settings()


class WhatsAppNotifier:
    """Send notifications through Twilio WhatsApp."""

    def __init__(self):
        self.account_sid = settings.twilio_account_sid
        self.auth_token = settings.twilio_auth_token
        self.whatsapp_from = settings.twilio_whatsapp_from
        self.whatsapp_to = settings.whatsapp_to
        self.logger = logging.getLogger(__name__)
        self._formatter = SignalNarrativeFormatter()

    @property
    def is_configured(self) -> bool:
        return bool(self.account_sid and self.auth_token and self.whatsapp_from and self.whatsapp_to)

    async def send_message(self, text: str) -> bool:
        if not self.is_configured:
            return False

        # WhatsApp practical display limit: keep concise chunks
        chunks = self._split_text(text, 1200)
        url = f"https://api.twilio.com/2010-04-01/Accounts/{self.account_sid}/Messages.json"

        try:
            async with aiohttp.ClientSession(auth=aiohttp.BasicAuth(self.account_sid, self.auth_token)) as session:
                for chunk in chunks:
                    payload = {
                        "From": self.whatsapp_from,
                        "To": self.whatsapp_to,
                        "Body": chunk,
                    }
                    async with session.post(url, data=payload) as resp:
                        if resp.status not in (200, 201):
                            body = await resp.text()
                            self.logger.error(f"Twilio WhatsApp error {resp.status}: {body[:200]}")
                            return False
            return True
        except Exception as e:
            self.logger.error(f"WhatsApp send error: {e}")
            return False

    async def send_signal(self, signal: Any) -> bool:
        msg = self._formatter.format_signal(signal, as_html=False)
        return await self.send_message(msg)

    async def send_signals_batch(self, signals: List[Any]) -> int:
        if not signals:
            return 0
        success = 0
        for s in signals[:3]:
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
