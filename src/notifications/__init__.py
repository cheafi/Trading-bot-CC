"""
TradingAI Bot - Notifications Module

Provides:
- DiscordInteractiveBot: Rich embeds + slash commands
- MultiChannelNotifier: Unified multi-channel dispatch

Imports are lazy to avoid blocking the API server startup
(discord_bot.py is 7000+ lines with heavy dependencies).
"""


def __getattr__(name: str):
    if name == "DiscordInteractiveBot":
        from src.notifications.discord_bot import DiscordInteractiveBot
        return DiscordInteractiveBot
    if name == "MultiChannelNotifier":
        from src.notifications.multi_channel import MultiChannelNotifier
        return MultiChannelNotifier
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")


__all__ = [
    'DiscordInteractiveBot',
    'MultiChannelNotifier',
]
