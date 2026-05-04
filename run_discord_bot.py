#!/usr/bin/env python3
"""
TradingAI Pro — Discord Bot Launcher
=====================================

Run this to start the Discord bot:
    python run_discord_bot.py

Requirements:
    - DISCORD_BOT_TOKEN set in .env
    - discord.py installed (pip install discord.py)
    - PostgreSQL & Redis running (docker compose up -d)

The bot will:
    1. Connect to your Discord server
    2. Auto-create organized channels (signals, portfolio, alerts, etc.)
    3. Send a welcome embed with all commands
    4. Register 40+ slash commands
    5. Respond to /help, /price, /ai, /market, and more
"""
import asyncio
import sys
import os
import signal
import logging

# Add project root to path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

# Logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s  %(levelname)-8s  %(name)s  %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)
logger = logging.getLogger("discord_launcher")


def main():
    print("=" * 56)
    print("  🤖  TradingAI Pro v2.0 — Discord Bot")
    print("=" * 56)
    print()

    # Quick checks
    try:
        import discord  # noqa: F401
    except ImportError:
        print("❌  discord.py not installed.")
        print("    Run:  pip install discord.py")
        sys.exit(1)

    from src.notifications.discord_bot import DiscordInteractiveBot

    bot = DiscordInteractiveBot()
    if not bot.is_configured:
        print("❌  DISCORD_BOT_TOKEN not found in .env")
        print("    1. Go to https://discord.com/developers/applications")
        print("    2. Create application → Bot → Copy token")
        print("    3. Add to .env:  DISCORD_BOT_TOKEN=your_token_here")
        sys.exit(1)

    print("✅  Bot token found")
    print("🚀  Connecting to Discord...\n")

    # Graceful shutdown
    def _shutdown(signum, frame):
        print("\n🛑  Shutting down...")
        sys.exit(0)

    signal.signal(signal.SIGINT, _shutdown)
    signal.signal(signal.SIGTERM, _shutdown)

    # Run
    asyncio.run(bot.run_interactive_bot())


if __name__ == "__main__":
    main()
