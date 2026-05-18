"""
TradingAI Bot - Notifications Module

Provides:
- DiscordInteractiveBot: Rich embeds + slash commands
- MultiChannelNotifier: Unified multi-channel dispatch
- TelegramNotifier: Telegram Bot API delivery
"""

from src.notifications.discord_bot import DiscordInteractiveBot
from src.notifications.multi_channel import MultiChannelNotifier
from src.notifications.telegram import TelegramNotifier

__all__ = [
    "DiscordInteractiveBot",
    "MultiChannelNotifier",
    "TelegramNotifier",
]
