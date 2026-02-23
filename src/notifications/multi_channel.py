"""Multi-channel notification dispatcher."""
from __future__ import annotations

import logging
from typing import Any, Dict, List

from src.notifications.telegram import TelegramNotifier
from src.notifications.discord import DiscordNotifier
from src.notifications.whatsapp import WhatsAppNotifier


class MultiChannelNotifier:
    """Fan-out notifications to configured channels."""

    def __init__(self):
        self.logger = logging.getLogger(__name__)
        self.telegram = TelegramNotifier()
        self.discord = DiscordNotifier()
        self.whatsapp = WhatsAppNotifier()

    @property
    def channels_status(self) -> Dict[str, bool]:
        return {
            "telegram": self.telegram.is_configured,
            "discord": self.discord.is_configured,
            "whatsapp": self.whatsapp.is_configured,
        }

    @property
    def is_configured(self) -> bool:
        status = self.channels_status
        return any(status.values())

    async def send_message(self, message: str) -> Dict[str, bool]:
        results = {
            "telegram": False,
            "discord": False,
            "whatsapp": False,
        }

        if self.telegram.is_configured:
            results["telegram"] = await self.telegram.send_message(message)
        if self.discord.is_configured:
            results["discord"] = await self.discord.send_message(message)
        if self.whatsapp.is_configured:
            results["whatsapp"] = await self.whatsapp.send_message(message)

        return results

    async def send_signal(self, signal: Any) -> Dict[str, bool]:
        results = {
            "telegram": False,
            "discord": False,
            "whatsapp": False,
        }

        if self.telegram.is_configured:
            results["telegram"] = await self.telegram.send_signal(signal)
        if self.discord.is_configured:
            results["discord"] = await self.discord.send_signal(signal)
        if self.whatsapp.is_configured:
            results["whatsapp"] = await self.whatsapp.send_signal(signal)

        return results

    async def send_signals_batch(self, signals: List[Any]) -> Dict[str, int]:
        sent = {
            "telegram": 0,
            "discord": 0,
            "whatsapp": 0,
        }

        if self.telegram.is_configured:
            sent["telegram"] = await self.telegram.send_signals_batch(signals)
        if self.discord.is_configured:
            sent["discord"] = await self.discord.send_signals_batch(signals)
        if self.whatsapp.is_configured:
            sent["whatsapp"] = await self.whatsapp.send_signals_batch(signals)

        return sent

    async def send_daily_report(self, report: Dict[str, Any]) -> Dict[str, bool]:
        message = self.telegram._format_daily_report_message(report)
        return await self.send_message(message)

    async def send_alert(self, title: str, message: str, level: str = "INFO") -> Dict[str, bool]:
        text = self.telegram._format_alert_message(title=title, message=message, level=level)
        return await self.send_message(text)
