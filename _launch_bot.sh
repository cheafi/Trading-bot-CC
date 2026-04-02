#!/bin/bash
cd /Users/chantszwai/Documents/GitHub/TradingAI_Bot-main
PYTHONUNBUFFERED=1 nohup ./venv/bin/python -u -m src.notifications.discord_bot > _bot.log 2>&1 &
echo "Bot PID: $!"
