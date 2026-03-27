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

    # ------------------------------------------------------------------
    # Sprint 25: structured trade-execution alerts
    # ------------------------------------------------------------------

    async def send_trade_alert(self, trade_info: Dict[str, Any]) -> Dict[str, bool]:
        """Send a structured trade execution notification.

        Args:
            trade_info: dict with keys like ticker, direction, quantity,
                        fill_price, strategy, confidence, stop_price, etc.
        """
        direction = trade_info.get("direction", "LONG")
        ticker = trade_info.get("ticker", "???")
        qty = trade_info.get("quantity", 0)
        fill = trade_info.get("fill_price", 0)
        strategy = trade_info.get("strategy", "unknown")
        confidence = trade_info.get("confidence", 0)
        stop = trade_info.get("stop_price", 0)
        score = trade_info.get("composite_score", 0)

        emoji = "\U0001f7e2" if direction == "LONG" else "\U0001f534"  # green / red circle
        text = (
            f"{emoji} Trade Executed: {direction} {ticker}\n"
            f"Qty: {qty} @ ${fill:.2f}\n"
            f"Strategy: {strategy} (conf={confidence:.0f}%)\n"
            f"Stop: ${stop:.2f} | Score: {score:.3f}\n"
            f"Time: {trade_info.get('time', 'now')}"
        )
        return await self.send_message(text)

    async def send_exit_alert(self, exit_info: Dict[str, Any]) -> Dict[str, bool]:
        """Send a structured position-exit notification.

        Args:
            exit_info: dict with keys like ticker, exit_price, pnl_pct,
                       reason, hold_hours, direction.
        """
        ticker = exit_info.get("ticker", "???")
        exit_price = exit_info.get("exit_price", 0)
        pnl_pct = exit_info.get("pnl_pct", 0)
        reason = exit_info.get("reason", "unknown")
        hold_h = exit_info.get("hold_hours", 0)

        emoji = "\u2705" if pnl_pct >= 0 else "\u274c"  # check / cross
        text = (
            f"{emoji} Position Closed: {ticker}\n"
            f"Exit: ${exit_price:.2f} | PnL: {pnl_pct:+.2f}%\n"
            f"Reason: {reason}\n"
            f"Held: {hold_h:.1f}h"
        )
        return await self.send_message(text)
