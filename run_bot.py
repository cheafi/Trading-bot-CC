#!/usr/bin/env python3
"""
TradingAI Bot — 24/7 Launcher
Runs the Discord bot with auto-restart on crash.
"""
import sys
import os
import asyncio

# Ensure project root is on path
ROOT = os.path.dirname(os.path.abspath(__file__))
os.chdir(ROOT)
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

from src.notifications.discord_bot import main

if __name__ == "__main__":
    asyncio.run(main())
