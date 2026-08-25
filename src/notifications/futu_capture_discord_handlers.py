"""Discord handlers for Futu portfolio screenshot capture — advisory only."""

from __future__ import annotations

import logging
import os
from datetime import datetime, timezone
from typing import TYPE_CHECKING

import aiohttp

if TYPE_CHECKING:
    import discord
    from discord.ext import commands

logger = logging.getLogger(__name__)


def register_futu_capture_handlers(
    bot: "commands.Bot",
    *,
    api_base_url: str,
    color_buy: int,
    color_info: int,
) -> None:
    """Register on_message image relay + /portfolio-futu-capture slash command."""
    import discord
    from discord import app_commands

    @bot.event
    async def on_message_futu_capture(message: discord.Message):
        if message.author.bot or not message.attachments:
            return
        target_channel = os.getenv("DISCORD_FUTU_CAPTURE_CHANNEL", "").strip().lower()
        if target_channel:
            ch_name = (message.channel.name or "").lower()
            if (
                target_channel not in ch_name
                and str(message.channel.id) != target_channel
            ):
                return
        img = next(
            (
                a
                for a in message.attachments
                if (a.content_type or "").startswith("image/")
            ),
            None,
        )
        if not img:
            return
        if img.size and img.size > 10 * 1024 * 1024:
            await message.reply("⚠️ Image too large (max 10MB).", mention_author=False)
            return
        try:
            data = await img.read()
            form = aiohttp.FormData()
            form.add_field(
                "file",
                data,
                filename="futu_capture.png",
                content_type=img.content_type or "image/png",
            )
            form.add_field("notify_discord", "false")
            async with aiohttp.ClientSession() as sess:
                async with sess.post(
                    f"{api_base_url}/api/v7/portfolio/futu-capture",
                    data=form,
                    timeout=aiohttp.ClientTimeout(total=120),
                ) as resp:
                    if resp.status != 200:
                        txt = await resp.text()
                        await message.reply(
                            f"❌ Futu capture failed ({resp.status}): {txt[:200]}",
                            mention_author=False,
                        )
                        return
                    result = await resp.json()
            count = result.get("count", 0)
            adv = result.get("advisory") or {}
            e = discord.Embed(
                title="📸 Futu Capture Parsed",
                description=(
                    f"**{count} holdings** via `{result.get('parse_method', '?')}`\n"
                    f"_{adv.get('disclaimer_en', 'ADVISORY ONLY')}_"
                ),
                color=color_info,
                timestamp=datetime.now(timezone.utc),
            )
            for h in (result.get("holdings") or [])[:12]:
                pnl = h.get("pnl_pct")
                pnl_s = f"{pnl:+.1f}%" if pnl is not None else "—"
                e.add_field(
                    name=h["ticker"],
                    value=f"{h.get('shares', 0):g} sh @ ${h.get('avg_cost', 0):,.2f} · {pnl_s}",
                    inline=True,
                )
            summary = adv.get("summary_en") or adv.get("summary_zh") or ""
            if summary:
                e.add_field(name="AI Advisory", value=summary[:1024], inline=False)
            e.set_footer(text="Advisory only — confirm in CC Portfolio tab")
            await message.reply(embed=e, mention_author=False)
        except Exception as exc:
            logger.warning("Futu capture on_message failed: %s", exc)
            await message.reply(f"❌ Futu capture error: {exc}", mention_author=False)

    @bot.event
    async def on_message(message: discord.Message):
        await on_message_futu_capture(message)

    @bot.tree.command(
        name="portfolio-futu-capture",
        description="Upload Futu screenshot → parse holdings + AI advisory",
    )
    @app_commands.describe(screenshot="Futu portfolio screenshot (PNG/JPEG)")
    @app_commands.checks.cooldown(1, 30, key=lambda i: i.user.id)
    async def cmd_portfolio_futu_capture(
        interaction: discord.Interaction,
        screenshot: discord.Attachment,
    ):
        await interaction.response.defer()
        if not (screenshot.content_type or "").startswith("image/"):
            await interaction.followup.send("⚠️ Please upload a PNG/JPEG screenshot.")
            return
        if screenshot.size and screenshot.size > 10 * 1024 * 1024:
            await interaction.followup.send("⚠️ Image too large (max 10MB).")
            return
        try:
            data = await screenshot.read()
            form = aiohttp.FormData()
            form.add_field(
                "file",
                data,
                filename="futu_capture.png",
                content_type=screenshot.content_type or "image/png",
            )
            form.add_field("notify_discord", "true")
            async with aiohttp.ClientSession() as sess:
                async with sess.post(
                    f"{api_base_url}/api/v7/portfolio/futu-capture",
                    data=form,
                    timeout=aiohttp.ClientTimeout(total=120),
                ) as resp:
                    if resp.status != 200:
                        txt = await resp.text()
                        await interaction.followup.send(
                            f"❌ Capture failed ({resp.status}): {txt[:300]}"
                        )
                        return
                    result = await resp.json()
            adv = result.get("advisory") or {}
            e = discord.Embed(
                title="📸 Futu Capture · 富途持倉",
                description=(
                    f"**{result.get('count', 0)} holdings** · `{result.get('parse_method')}`\n"
                    f"_{adv.get('disclaimer_en', 'ADVISORY ONLY')}_"
                ),
                color=color_buy,
                timestamp=datetime.now(timezone.utc),
            )
            for h in (result.get("holdings") or [])[:15]:
                pnl = h.get("pnl_pct")
                pnl_s = f"{pnl:+.1f}%" if pnl is not None else "—"
                e.add_field(
                    name=h["ticker"],
                    value=(
                        f"{h.get('shares', 0):g} sh · cost ${h.get('avg_cost', 0):,.2f} · {pnl_s}"
                    ),
                    inline=True,
                )
            if adv.get("summary_en"):
                e.add_field(
                    name="AI · EN", value=adv["summary_en"][:1024], inline=False
                )
            if adv.get("summary_zh"):
                e.add_field(
                    name="AI · 繁中", value=adv["summary_zh"][:1024], inline=False
                )
            e.set_footer(text="Advisory only — human approval required")
            await interaction.followup.send(embed=e)
        except Exception as exc:
            await interaction.followup.send(f"❌ Futu capture failed: {exc}")
