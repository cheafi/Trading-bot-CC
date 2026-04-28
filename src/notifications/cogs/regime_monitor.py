"""
CC Discord Bot — Regime Monitoring Cog
=======================================
Sends regime change notifications to the designated channel.

This cog provides:
  /regime — Show current market regime with full detail
  Background task: monitor regime changes and alert on transitions
"""
from __future__ import annotations

import logging
from datetime import datetime, timezone

import discord
from discord import app_commands
from discord.ext import commands, tasks

from src.notifications._embeds import (
    RegimeEmbed,
    EmbedColors,
)

logger = logging.getLogger(__name__)


class RegimeMonitorCog(commands.Cog, name="Regime Monitor"):
    """Market regime monitoring and change notifications."""

    def __init__(self, bot: commands.Bot):
        self.bot = bot
        self._last_regime: str = ""

    @app_commands.command(
        name="regime",
        description="Show current market regime classification",
    )
    async def regime(self, interaction: discord.Interaction):
        """Display the current regime state with details."""
        await interaction.response.defer()

        regime_state = "unknown"
        playbook = ""
        risk_score = 50.0
        signals_list: list[str] = []

        try:
            from src.services.regime_service import (
                RegimeService,
            )
            regime = RegimeService.get()
            # Map MacroRegimeEngine trends to cog labels
            _TREND_MAP = {
                "RISK_ON": "bull_trending",
                "UPTREND": "bull_trending",
                "SIDEWAYS": "neutral_consolidation",
                "TRANSITIONAL": "sideways",
                "RISK_OFF": "bear_trending",
                "DOWNTREND": "bear_trending",
                "CRISIS": "crisis",
            }
            raw_trend = regime.get("trend", "SIDEWAYS")
            regime_state = _TREND_MAP.get(
                raw_trend, "sideways"
            )
            risk_score = regime.get("risk_score", 50)
            signals_list = regime.get("signals", [])
            # Build playbook from regime
            if risk_score < 30:
                playbook = (
                    "Full allocation. Momentum + breakout."
                )
            elif risk_score < 60:
                playbook = "Standard allocation. Selective."
            else:
                playbook = (
                    "Reduced exposure. Capital preservation."
                )
        except Exception as e:
            logger.warning(f"Could not fetch regime: {e}")

        # Build regime embed
        regime_colors = {
            "bull_trending": EmbedColors.GREEN,
            "bull_volatile": EmbedColors.GREEN,
            "bull_exhaustion": EmbedColors.GOLD,
            "neutral_consolidation": EmbedColors.BLUE,
            "sideways": EmbedColors.GRAY,
            "bear_rally": EmbedColors.GOLD,
            "bear_trending": EmbedColors.RED,
            "bear_volatile": EmbedColors.RED,
            "crisis": EmbedColors.RED,
        }

        regime_descriptions = {
            "bull_trending": (
                "Market in a confirmed uptrend. Trend-following and "
                "momentum strategies favored. Breakouts more reliable."
            ),
            "bull_volatile": (
                "Uptrend with elevated volatility. Opportunities exist "
                "but wider stops needed. Position sizes should be smaller."
            ),
            "bull_exhaustion": (
                "Uptrend showing signs of fatigue. Breadth narrowing, "
                "leaders rotating. Reduce new long exposure."
            ),
            "neutral_consolidation": (
                "Market consolidating. Range-bound strategies work. "
                "Watch for breakout direction."
            ),
            "sideways": (
                "No clear trend. Mean reversion may work. "
                "Reduce position sizes and be selective."
            ),
            "bear_rally": (
                "Bounce within a downtrend. Short-lived. "
                "Do not chase. Tighten stops on longs."
            ),
            "bear_trending": (
                "Confirmed downtrend. Most long signals suppressed. "
                "Capital preservation is the priority."
            ),
            "bear_volatile": (
                "Downtrend with high volatility. Very dangerous. "
                "Stay mostly in cash. Only highest-conviction trades."
            ),
            "crisis": (
                "Extreme market stress. Nearly all signals suppressed. "
                "Protect capital. Do not trade unless you have a "
                "specific, well-reasoned thesis."
            ),
        }

        color = regime_colors.get(
            regime_state, EmbedColors.GRAY
        )
        description = regime_descriptions.get(
            regime_state,
            "Regime not classified. Check /status for system health.",
        )

        embed = discord.Embed(
            title=f"📊 Market Regime: {regime_state}",
            description=description,
            color=color,
            timestamp=datetime.now(timezone.utc),
        )

        if playbook:
            embed.add_field(
                name="📋 Playbook",
                value=playbook[:1024],
                inline=False,
            )

        if signals_list:
            embed.add_field(
                name="📡 Signals",
                value="\n".join(
                    f"• {s}" for s in signals_list[:5]
                ),
                inline=False,
            )

        embed.add_field(
            name="⚡ Risk Score",
            value=f"{risk_score:.0f}/100",
            inline=True,
        )

        # Strategy guidance per regime
        strategy_guidance = {
            "bull_trending": "✅ Swing · ✅ Breakout · ✅ Momentum · ❌ Mean Rev",
            "bull_volatile": "✅ Swing · 🟡 Breakout · ✅ Momentum · ❌ Mean Rev",
            "bull_exhaustion": "🟡 Swing · 🟡 Breakout · 🟡 Momentum · ❌ Mean Rev",
            "neutral_consolidation": "✅ Swing · ✅ Breakout · 🟡 Momentum · ✅ Mean Rev",
            "sideways": "🟡 Swing · 🟡 Breakout · ❌ Momentum · ✅ Mean Rev",
            "bear_rally": "🟡 Swing · ❌ Breakout · ❌ Momentum · ✅ Mean Rev",
            "bear_trending": "❌ Swing · ❌ Breakout · ❌ Momentum · ❌ Mean Rev",
            "bear_volatile": "❌ Swing · ❌ Breakout · ❌ Momentum · ❌ Mean Rev",
            "crisis": "❌ All strategies suppressed",
        }

        guidance = strategy_guidance.get(regime_state, "Check /status")
        embed.add_field(
            name="Strategy Activity",
            value=guidance,
            inline=False,
        )

        embed.set_footer(
            text=(
                "Regime classification is probabilistic. "
                "It can change rapidly. Not financial advice."
            )
        )

        await interaction.followup.send(embed=embed)


async def setup(bot: commands.Bot):
    """Load this cog into the bot."""
    await bot.add_cog(RegimeMonitorCog(bot))
