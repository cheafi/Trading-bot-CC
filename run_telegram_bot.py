#!/usr/bin/env python3
"""
Run the TradingAI Telegram Bot.

Usage:
    python run_telegram_bot.py

The bot will start polling for messages and respond to commands.
Press Ctrl+C to stop.
"""
import asyncio
import logging
import sys

# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


async def main():
    """Run the Telegram bot."""
    from src.notifications.telegram_bot import TelegramBot
    
    bot = TelegramBot()
    
    if not bot.is_configured:
        print("❌ Telegram bot not configured!")
        print("   Set TELEGRAM_BOT_TOKEN and TELEGRAM_CHAT_ID in .env")
        sys.exit(1)
    
    print("=" * 50)
    print("🤖 TradingAI Telegram Bot")
    print("=" * 50)
    print(f"✅ Bot Token: ...{bot.bot_token[-10:]}")
    print(f"✅ Chat ID: {bot.chat_id}")
    print(f"📊 Commands: {len(bot.COMMANDS)}")
    print("=" * 50)
    print()
    print("🚀 Bot is now running!")
    print("   Send /help in Telegram to see commands")
    print("   Press Ctrl+C to stop")
    print()
    
    try:
        await bot.start()
        
        # Keep running
        while True:
            await asyncio.sleep(1)
            
    except KeyboardInterrupt:
        print("\n👋 Shutting down bot...")
        await bot.stop()
        print("✅ Bot stopped")


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("\n👋 Goodbye!")
