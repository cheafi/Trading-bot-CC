"""
CC Discord Bot — Embed Helpers
===============================
Lightweight embed builder for webhook mode (no discord.py dependency)
and paginated embed handler for long data.
"""
from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Dict, List, Optional


class DiscordEmbed:
    """
    Lightweight embed builder compatible with Discord webhook API.
    Does not require discord.py — works with raw webhook POSTs.
    """

    def __init__(
        self,
        title: str = "",
        description: str = "",
        color: int = 0x5865F2,
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


class EmbedPaginator:
    """
    Splits long content across multiple embeds to
    stay within Discord's 4096-char description limit.
    """

    MAX_DESC = 4000  # Leave room for formatting

    def __init__(
        self,
        title: str,
        color: int = 0x5865F2,
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
