"""
DEPRECATED — This file is a stale duplicate.
The canonical source is src/notifications/discord_bot.py.
This shim re-exports DiscordInteractiveBot so old imports don't break.
"""
from src.notifications.discord_bot import DiscordInteractiveBot  # noqa: F401

__all__ = ["DiscordInteractiveBot"]
