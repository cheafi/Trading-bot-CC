"""
TradingAI Bot - Notifications Module

Provides:
- TelegramNotifier: One-way push notifications
- TelegramBot: Interactive bot with commands
- DiscordInteractiveBot: Rich embeds + slash commands
- MultiChannelNotifier: Unified multi-channel dispatch
"""
from src.notifications.telegram import TelegramNotifier
from src.notifications.telegram_bot import TelegramBot, start_telegram_bot
from src.notifications.discord_bot import DiscordInteractiveBot
from src.notifications.multi_channel import MultiChannelNotifier

__all__ = [
    'TelegramNotifier',
    'TelegramBot',
    'start_telegram_bot',
    'DiscordInteractiveBot',
    'MultiChannelNotifier',
]
