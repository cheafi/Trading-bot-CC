#!/usr/bin/env python3
"""
Run the TradingAI Telegram Bot.

Usage:
    python run_telegram_bot.py

The bot will start polling for messages and respond to commands.
Press Ctrl+C to stop.

Features:
- Auto-recovery from network errors
- Watchdog for background task health
- Graceful shutdown handling
"""
import asyncio
import logging
import signal
import sys
import os

# Setup logging with more detail
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler(),
        logging.FileHandler('telegram_bot.log', mode='a')  # Also log to file
    ]
)
logger = logging.getLogger(__name__)

# Track shutdown state
shutdown_event = asyncio.Event()


def signal_handler(sig, frame):
    """Handle shutdown signals gracefully."""
    logger.info(f"Received signal {sig}, initiating graceful shutdown...")
    shutdown_event.set()


async def main():
    """Run the Telegram bot with auto-recovery."""
    from src.notifications.telegram_bot import TelegramBot
    
    bot = TelegramBot()
    
    if not bot.is_configured:
        print("❌ Telegram bot not configured!")
        print("   Set TELEGRAM_BOT_TOKEN and TELEGRAM_CHAT_ID in .env")
        sys.exit(1)
    
    print("=" * 50)
    print("🤖 TradingAI Telegram Bot")
    print("=" * 50)
    print("✅ Telegram: Configured")
    print(f"📊 Commands: {len(bot.COMMANDS)}")
    print(f"📈 Stocks: {len(bot.TOP_STOCKS)}")
    print("🛡️  Auto-recovery: ENABLED")
    print("📝 Logging to: telegram_bot.log")
    print("=" * 50)
    print()
    print("🚀 Bot is now running!")
    print("   Send /help in Telegram to see commands")
    print("   Press Ctrl+C to stop")
    print()
    
    restart_count = 0
    max_restarts = 10
    
    while not shutdown_event.is_set():
        try:
            await bot.start()
            
            # Keep running until shutdown signal
            while not shutdown_event.is_set():
                await asyncio.sleep(1)
                
        except KeyboardInterrupt:
            logger.info("Keyboard interrupt received")
            break
        except Exception as e:
            restart_count += 1
            logger.error(f"Bot crashed with error: {e}")
            
            if restart_count >= max_restarts:
                logger.error(f"Too many restarts ({restart_count}), giving up")
                break
            
            # Exponential backoff for restarts
            wait_time = min(300, 10 * (2 ** (restart_count - 1)))
            logger.info(f"Restarting bot in {wait_time}s (attempt {restart_count}/{max_restarts})")
            
            try:
                await bot.stop()
            except Exception:
                pass
            
            await asyncio.sleep(wait_time)
    
    # Graceful shutdown
    logger.info("Shutting down bot...")
    try:
        await bot.stop()
    except Exception as e:
        logger.error(f"Error during shutdown: {e}")
    
    logger.info("Bot stopped successfully")
    print("\n👋 Goodbye!")


if __name__ == "__main__":
    # Register signal handlers for graceful shutdown
    signal.signal(signal.SIGINT, signal_handler)
    signal.signal(signal.SIGTERM, signal_handler)
    
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("\n👋 Goodbye!")
