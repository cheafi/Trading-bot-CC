"""
TradingAI Bot - Notifications Module

Provides:
- DiscordInteractiveBot: Rich embeds + slash commands
- MultiChannelNotifier: Unified multi-channel dispatch
"""
from src.notifications.discord_bot import DiscordInteractiveBot
from src.notifications.multi_channel import MultiChannelNotifier

__all__ = [
    'DiscordInteractiveBot',
    'MultiChannelNotifier',
]
