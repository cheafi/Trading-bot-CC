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

        Sprint 36: includes trust badge, regime, model version.

        Args:
            trade_info: dict with keys like ticker, direction, quantity,
                        fill_price, strategy, confidence, stop_price,
                        trust (TrustMetadata dict), etc.
        """
        direction = trade_info.get("direction", "LONG")
        ticker = trade_info.get("ticker", "???")
        qty = trade_info.get("quantity", 0)
        fill = trade_info.get("fill_price", 0)
        strategy = trade_info.get("strategy", "unknown")
        confidence = trade_info.get("confidence", 0)
        stop = trade_info.get("stop_price", 0)
        score = trade_info.get("composite_score", 0)

        emoji = (
            "\U0001f7e2" if direction == "LONG"
            else "\U0001f534"
        )

        # Sprint 36: trust metadata line
        trust = trade_info.get("trust", {})
        badge = trust.get("badge", "PAPER")
        badge_icon = {
            "LIVE": "\U0001f7e2",
            "PAPER": "\U0001f4cb",
            "BACKTEST": "\U0001f52c",
            "RESEARCH": "\U0001f50d",
        }.get(badge, "\u2753")
        model_ver = trust.get("model_version", "")
        regime = trust.get("regime_label", "")
        freshness = trust.get("freshness", "")

        lines = [
            f"{emoji} Trade Executed: {direction} {ticker}",
            f"Qty: {qty} @ ${fill:.2f}",
            f"Strategy: {strategy} (conf={confidence:.0f}%)",
            f"Stop: ${stop:.2f} | Score: {score:.3f}",
            f"Time: {trade_info.get('time', 'now')}",
        ]
        # Trust footer
        trust_parts = [f"{badge_icon} {badge}"]
        if regime:
            trust_parts.append(f"Regime: {regime}")
        if freshness:
            trust_parts.append(freshness)
        if model_ver:
            trust_parts.append(model_ver)
        lines.append(" \u2502 ".join(trust_parts))

        text = "\n".join(lines)
        return await self.send_message(text)

    async def send_exit_alert(self, exit_info: Dict[str, Any]) -> Dict[str, bool]:
        """Send a structured position-exit notification.

        Sprint 36: includes gross/net P&L breakdown, what worked
        / what failed attribution, and trust badge.

        Args:
            exit_info: dict with keys like ticker, exit_price,
                       pnl_pct, reason, hold_hours,
                       trust, pnl_breakdown, attribution.
        """
        ticker = exit_info.get("ticker", "???")
        exit_price = exit_info.get("exit_price", 0)
        pnl_pct = exit_info.get("pnl_pct", 0)
        reason = exit_info.get("reason", "unknown")
        hold_h = exit_info.get("hold_hours", 0)

        emoji = "\u2705" if pnl_pct >= 0 else "\u274c"

        lines = [
            f"{emoji} Position Closed: {ticker}",
            f"Exit: ${exit_price:.2f} | PnL: {pnl_pct:+.2f}%",
            f"Reason: {reason}",
            f"Held: {hold_h:.1f}h",
        ]

        # Sprint 36: gross/net breakdown
        pnl_bd = exit_info.get("pnl_breakdown", {})
        if pnl_bd:
            gross = pnl_bd.get("gross_pnl_pct", pnl_pct)
            net = pnl_bd.get("net_pnl_pct", pnl_pct)
            fees = pnl_bd.get("fees_pct", 0)
            slip = pnl_bd.get("slippage_pct", 0)
            lines.append(
                f"Gross {gross:+.2f}% \u2192 "
                f"Net {net:+.2f}% "
                f"(fees {fees:.2f}%, slip {slip:.2f}%)"
            )

        # Sprint 36: attribution
        attr = exit_info.get("attribution", {})
        worked = attr.get("what_worked", [])
        failed = attr.get("what_failed", [])
        if worked:
            lines.append(
                "\u2705 " + " | ".join(worked[:3])
            )
        if failed:
            lines.append(
                "\u274c " + " | ".join(failed[:3])
            )

        # Sprint 36: trust badge
        trust = exit_info.get("trust", {})
        badge = trust.get("badge", "PAPER")
        model_ver = trust.get("model_version", "")
        badge_icon = {
            "LIVE": "\U0001f7e2",
            "PAPER": "\U0001f4cb",
        }.get(badge, "\u2753")
        trust_line = f"{badge_icon} {badge}"
        if model_ver:
            trust_line += f" \u2502 {model_ver}"
        lines.append(trust_line)

        text = "\n".join(lines)
        return await self.send_message(text)

    async def send_no_trade_alert(
        self, no_trade_info: Dict[str, Any],
    ) -> Dict[str, bool]:
        """Send a no-trade card when system passes (Sprint 36).

        Args:
            no_trade_info: dict from NoTradeCard.to_dict()
        """
        reason = no_trade_info.get("reason", "")
        regime = no_trade_info.get("regime_label", "")
        resume = no_trade_info.get("resume_conditions", [])
        tickers = no_trade_info.get("tickers_considered", [])

        lines = [
            "\U0001f6ab No Trade",
            f"Regime: {regime}",
            f"Reason: {reason}",
        ]
        if tickers:
            lines.append(
                f"Considered: {', '.join(tickers[:5])}"
            )
        if resume:
            lines.append("Resume when:")
            for c in resume[:3]:
                lines.append(f"  \u2022 {c}")
        text = "\n".join(lines)
        return await self.send_message(text)
