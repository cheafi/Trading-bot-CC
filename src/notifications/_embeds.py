"""
CC Discord Bot — Embed Helpers
===============================
Lightweight embed builder for webhook mode (no discord.py dependency)
and paginated embed handler for long data.

v6.1: Added SignalEmbed for structured trade signal alerts with
      strategy labeling, confidence bars, invalidation, and trust strips.
"""
from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Dict, List, Optional


# ══════════════════════════════════════════════════════════════════════
# COLOR PALETTE
# ══════════════════════════════════════════════════════════════════════

class EmbedColors:
    """Consistent color scheme for Discord embeds."""
    BLURPLE = 0x5865F2        # Default / informational
    GREEN = 0x00D4AA          # Long / bullish / success
    RED = 0xFF4444            # Short / bearish / error / urgent
    GOLD = 0xFFBF00           # Warning / important
    BLUE = 0x3B82F6           # Informational / regime
    GRAY = 0x6B7280           # Neutral / low priority
    ORANGE = 0xF97316         # Caution / experimental


# ══════════════════════════════════════════════════════════════════════
# SEVERITY TIERS
# ══════════════════════════════════════════════════════════════════════

class AlertSeverity:
    """Alert severity tiers for Discord notifications."""
    URGENT = "🔴"             # Circuit breaker, tail risk, stop hit
    IMPORTANT = "🟡"          # New signal, regime change, earnings warning
    INFORMATIONAL = "🔵"      # Regime update, news digest, watchlist


# ══════════════════════════════════════════════════════════════════════
# BASE EMBED
# ══════════════════════════════════════════════════════════════════════

class DiscordEmbed:
    """
    Lightweight embed builder compatible with Discord webhook API.
    Does not require discord.py — works with raw webhook POSTs.
    """

    def __init__(
        self,
        title: str = "",
        description: str = "",
        color: int = EmbedColors.BLURPLE,
        url: str = "",
    ):
        self.title = title
        self.description = description
        self.color = color
        self.url = url
        self.fields: List[Dict[str, Any]] = []
        self.footer: Optional[str] = None
        self.thumbnail: Optional[str] = None
        self.image: Optional[str] = None
        self.timestamp: Optional[str] = None

    def add_field(
        self,
        name: str,
        value: str,
        inline: bool = False,
    ) -> "DiscordEmbed":
        self.fields.append({
            "name": name,
            "value": value,
            "inline": inline,
        })
        return self

    def set_footer(self, text: str) -> "DiscordEmbed":
        self.footer = text
        return self

    def set_thumbnail(self, url: str) -> "DiscordEmbed":
        self.thumbnail = url
        return self

    def set_image(self, url: str) -> "DiscordEmbed":
        self.image = url
        return self

    def set_timestamp(self) -> "DiscordEmbed":
        self.timestamp = datetime.now(
            timezone.utc
        ).isoformat()
        return self

    def to_dict(self) -> Dict[str, Any]:
        d: Dict[str, Any] = {}
        if self.title:
            d["title"] = self.title
        if self.description:
            d["description"] = self.description
        if self.color:
            d["color"] = self.color
        if self.url:
            d["url"] = self.url
        if self.fields:
            d["fields"] = self.fields
        if self.footer:
            d["footer"] = {"text": self.footer}
        if self.thumbnail:
            d["thumbnail"] = {"url": self.thumbnail}
        if self.image:
            d["image"] = {"url": self.image}
        if self.timestamp:
            d["timestamp"] = self.timestamp
        return d


# ══════════════════════════════════════════════════════════════════════
# SIGNAL EMBED — Structured trade signal alerts
# ══════════════════════════════════════════════════════════════════════

class SignalEmbed:
    """
    Build a structured Discord embed for a trade signal.

    Every signal embed includes:
    - Ticker + direction + strategy style label
    - Confidence score with visual bar + letter grade
    - Entry / Stop / Target
    - "Why Buy" (or "Why Short") — conviction narrative
    - "Why Not" — key risk or contradiction
    - Invalidation condition
    - Regime context
    - Trust strip footer (data mode, source, freshness)
    """

    GRADE_MAP = [
        (90, "A+"), (80, "A"), (75, "A-"),
        (70, "B+"), (65, "B"), (60, "B-"),
        (55, "C+"), (50, "C"), (0, "D"),
    ]

    @staticmethod
    def _confidence_bar(score: float, width: int = 8) -> str:
        filled = int(max(0, min(score, 100)) / 100 * width)
        return "█" * filled + "░" * (width - filled)

    @staticmethod
    def _grade(score: float) -> str:
        for threshold, grade in SignalEmbed.GRADE_MAP:
            if score >= threshold:
                return grade
        return "F"

    @classmethod
    def build(
        cls,
        ticker: str,
        direction: str,
        strategy: str,
        score: float,
        entry_price: float,
        stop_price: float,
        target_price: float,
        why_buy: str = "",
        why_not: str = "",
        invalidation: str = "",
        regime: str = "",
        setup_description: str = "",
        data_mode: str = "LIVE",
        data_source: str = "yfinance",
        freshness: str = "<1min",
        catalyst: str = "",
        factor_chips: str = "",
        timestamp: Optional[datetime] = None,
    ) -> DiscordEmbed:
        """Build a complete signal alert embed."""

        direction_upper = direction.upper()
        is_long = direction_upper in ("LONG", "BUY")

        # Color by direction
        color = EmbedColors.GREEN if is_long else EmbedColors.RED
        dir_emoji = "🟢" if is_long else "🔴"

        grade = cls._grade(score)
        bar = cls._confidence_bar(score)

        title = f"{dir_emoji} {ticker} — {strategy} {direction_upper} (Score: {score:.0f}/100)"

        embed = DiscordEmbed(
            title=title,
            color=color,
        )
        embed.set_timestamp()

        # Row 1: Strategy + Confidence + Regime (inline)
        strategy_text = strategy
        if setup_description:
            strategy_text += f" · {setup_description}"
        embed.add_field(name="Strategy", value=strategy_text, inline=True)
        embed.add_field(
            name="Confidence",
            value=f"{bar} {score:.0f}%  (Grade: {grade})",
            inline=True,
        )
        if regime:
            embed.add_field(name="Regime", value=regime, inline=True)

        # Row 2: Trade plan
        risk_pct = abs((stop_price - entry_price) / entry_price * 100) if entry_price else 0
        reward_pct = abs((target_price - entry_price) / entry_price * 100) if entry_price else 0
        rr_ratio = reward_pct / risk_pct if risk_pct > 0 else 0

        trade_plan = (
            f"**Entry:** ${entry_price:,.2f}\n"
            f"**Stop:** ${stop_price:,.2f} (–{risk_pct:.1f}%)\n"
            f"**Target:** ${target_price:,.2f} (+{reward_pct:.1f}%)\n"
            f"**R:R** {rr_ratio:.1f}:1"
        )
        embed.add_field(name="Trade Plan", value=trade_plan, inline=False)

        # Row 3: Why Buy / Why Not
        why_label = "Why Buy" if is_long else "Why Short"
        if why_buy:
            embed.add_field(name=f"✅ {why_label}", value=why_buy, inline=False)
        if why_not:
            embed.add_field(name="⚠️ Risk / Why Not", value=why_not, inline=False)

        # Row 4: Invalidation
        if invalidation:
            embed.add_field(name="❌ Invalidation", value=invalidation, inline=False)

        # Optional: catalyst, factor chips
        if catalyst:
            embed.add_field(name="📅 Catalyst", value=catalyst, inline=True)
        if factor_chips:
            embed.add_field(name="🧩 Factors", value=factor_chips, inline=True)

        # Footer: trust strip
        ts = timestamp or datetime.now(timezone.utc)
        ts_str = ts.strftime("%H:%M ET") if ts else ""
        embed.set_footer(
            f"⏱ {ts_str} · {data_mode} · {data_source} · Freshness: {freshness}"
        )

        return embed


class RegimeEmbed:
    """Build a regime change notification embed."""

    @staticmethod
    def build(
        old_regime: str,
        new_regime: str,
        probability: float = 0.0,
        playbook: str = "",
        data_mode: str = "LIVE",
    ) -> DiscordEmbed:
        embed = DiscordEmbed(
            title=f"📊 Regime Shift: {old_regime} → {new_regime}",
            color=EmbedColors.BLUE,
        )
        embed.set_timestamp()

        embed.add_field(
            name="Previous", value=old_regime or "Unknown", inline=True,
        )
        embed.add_field(
            name="Current", value=new_regime or "Unknown", inline=True,
        )
        if probability:
            embed.add_field(
                name="Probability",
                value=f"{probability:.0%}",
                inline=True,
            )
        if playbook:
            embed.add_field(name="Playbook", value=playbook, inline=False)

        embed.set_footer(f"{data_mode} · Regime classification is probabilistic, not certain")
        return embed


class RiskAlertEmbed:
    """Build an urgent risk escalation embed."""

    @staticmethod
    def build(
        title: str,
        description: str,
        risk_level: str = "HIGH",
        action_required: str = "",
    ) -> DiscordEmbed:
        embed = DiscordEmbed(
            title=f"🔴 RISK ALERT: {title}",
            description=description,
            color=EmbedColors.RED,
        )
        embed.set_timestamp()

        embed.add_field(name="Risk Level", value=risk_level, inline=True)
        if action_required:
            embed.add_field(name="Action Required", value=action_required, inline=False)

        embed.set_footer("This is an automated risk alert, not financial advice. Review immediately.")
        return embed


# ══════════════════════════════════════════════════════════════════════
# PAGINATOR (unchanged from v6)
# ══════════════════════════════════════════════════════════════════════

class EmbedPaginator:
    """
    Splits long content across multiple embeds to
    stay within Discord's 4096-char description limit.
    """

    MAX_DESC = 4000  # Leave room for formatting

    def __init__(
        self,
        title: str,
        color: int = EmbedColors.BLURPLE,
    ):
        self.title = title
        self.color = color
        self._pages: List[str] = []
        self._current: str = ""

    def add_line(self, line: str) -> None:
        if len(self._current) + len(line) + 1 > self.MAX_DESC:
            self._pages.append(self._current)
            self._current = ""
        self._current += line + "\n"

    def add_block(self, text: str) -> None:
        for line in text.split("\n"):
            self.add_line(line)

    def build(self) -> List[DiscordEmbed]:
        if self._current:
            self._pages.append(self._current)
        embeds = []
        total = len(self._pages)
        for i, page in enumerate(self._pages):
            title = self.title
            if total > 1:
                title += f" ({i + 1}/{total})"
            embeds.append(DiscordEmbed(
                title=title,
                description=page,
                color=self.color,
            ))
        return embeds
