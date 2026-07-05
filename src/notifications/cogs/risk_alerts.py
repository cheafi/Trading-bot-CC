"""
CC Discord Bot — Risk Alerts Cog
=================================
Handles risk escalation commands and regime warning displays.

Commands:
  /risk_status — Show current risk state and regime warnings
  /circuit_breaker — Display circuit breaker status
"""
from __future__ import annotations

import logging
from datetime import datetime, timezone

import discord
from discord import app_commands
from discord.ext import commands

from src.notifications._embeds import (
    RiskAlertEmbed,
    RegimeEmbed,
    EmbedColors,
)
from src.engines.regime_throttle import RegimeThrottle

logger = logging.getLogger(__name__)


class RiskAlertsCog(commands.Cog, name="Risk Alerts"):
    """Risk monitoring and escalation commands."""

    def __init__(self, bot: commands.Bot):
        self.bot = bot
        self.throttle = RegimeThrottle()

    @app_commands.command(
        name="risk_status",
        description="Show current risk state and regime warnings",
    )
    async def risk_status(self, interaction: discord.Interaction):
        """Display the current risk environment."""
        await interaction.response.defer()

        # Try to get regime from signal engine if available
        regime_state = "unknown"
        regime_warning = None

        try:
            engine = getattr(self.bot, "_signal_engine", None)
            if engine:
                market_state = engine.get_market_state()
                if market_state:
                    regime_state = market_state.get(
                        "regime_label", "unknown"
                    )
                    regime_warning = market_state.get(
                        "regime_warning"
                    )
        except Exception as e:
            logger.warning(f"Could not fetch regime state: {e}")

        # Build embed
        warning = self.throttle.get_regime_warning(regime_state)
        throttle_rate = self.throttle.get_rate(regime_state)

        embed = discord.Embed(
            title="🛡️ Risk Status",
            color=(
                EmbedColors.RED if throttle_rate < 0.5
                else EmbedColors.GOLD if throttle_rate < 0.8
                else EmbedColors.GREEN
            ),
            timestamp=datetime.now(timezone.utc),
        )

        # Regime
        regime_emoji = (
            "🟢" if throttle_rate >= 0.8
            else "🟡" if throttle_rate >= 0.5
            else "🔴"
        )
        embed.add_field(
            name="Regime",
            value=f"{regime_emoji} {regime_state}",
            inline=True,
        )

        # Throttle
        embed.add_field(
            name="Signal Throttle",
            value=f"{throttle_rate:.0%} of signals passing",
            inline=True,
        )

        # Warning
        if warning:
            embed.add_field(
                name="⚠️ Regime Warning",
                value=warning,
                inline=False,
            )
        else:
            embed.add_field(
                name="Status",
                value="✅ No active regime warnings",
                inline=False,
            )

        # Regime-specific guidance
        if throttle_rate < 0.5:
            embed.add_field(
                name="🔴 Guidance",
                value=(
                    "Capital preservation mode. Most signals suppressed. "
                    "Consider reducing exposure and avoiding new positions."
                ),
                inline=False,
            )
        elif throttle_rate < 0.8:
            embed.add_field(
                name="🟡 Guidance",
                value=(
                    "Elevated caution. Signal quality may be lower. "
                    "Consider smaller position sizes and wider stops."
                ),
                inline=False,
            )

        embed.set_footer(
            text=(
                "Risk status is informational, not financial advice. "
                "Always apply your own risk management."
            )
        )

        await interaction.followup.send(embed=embed)

    @app_commands.command(
        name="circuit_breaker",
        description="Show circuit breaker status and limits",
    )
    async def circuit_breaker(self, interaction: discord.Interaction):
        """Display circuit breaker configuration and status."""
        await interaction.response.defer()

        embed = discord.Embed(
            title="⚡ Circuit Breaker Status",
            color=EmbedColors.GOLD,
            timestamp=datetime.now(timezone.utc),
        )

        # Default limits from config
        embed.add_field(
            name="Daily Loss Limit",
            value="3% of portfolio",
            inline=True,
        )
        embed.add_field(
            name="Weekly Loss Limit",
            value="5% of portfolio",
            inline=True,
        )
        embed.add_field(
            name="Status",
            value="✅ Active — monitoring",
            inline=True,
        )

        embed.add_field(
            name="What Happens When Triggered",
            value=(
                "• All new signal generation paused\n"
                "• 🔴 Urgent alert sent to risk channel\n"
                "• Existing positions NOT auto-closed (your decision)\n"
                "• Resumes next trading day or after manual reset"
            ),
            inline=False,
        )

        embed.set_footer(
            text="Circuit breakers protect against cascading losses. "
                 "Review SECURITY.md for full risk control docs."
        )

        await interaction.followup.send(embed=embed)


async def setup(bot: commands.Bot):
    """Load this cog into the bot."""
    await bot.add_cog(RiskAlertsCog(bot))
