"""Telegram notifier via Bot API (HTTPS)."""

from __future__ import annotations

import logging

from src.core.config import get_settings
from src.notifications.telegram import send_message_async, telegram_is_configured

settings = get_settings()


class TelegramNotifier:
    """Send plain-text notifications through Telegram Bot API."""

    def __init__(self):
        self.bot_token = settings.telegram_bot_token
        self.chat_id = settings.telegram_chat_id
        self.logger = logging.getLogger(__name__)

    @property
    def is_configured(self) -> bool:
        return telegram_is_configured()

    async def send_message(self, text: str) -> bool:
        if not self.is_configured:
            return False
        return await send_message_async(text, parse_mode="HTML")
