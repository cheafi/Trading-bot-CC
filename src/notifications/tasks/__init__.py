"""
CC Discord Bot — Background Tasks Package
==========================================
Scheduled background loops for the CC Discord bot.

Each module handles a logical task group:
- market_tasks: market pulse, auto movers, sector/macro updates
- scan_tasks: swing/breakout/momentum/signal scanning
- brief_tasks: morning brief, EOD report, weekly recap
- alert_tasks: real-time price alerts, VIX fear monitor
- news_tasks: auto news feed, ticker news
- misc_tasks: strategy learning, opportunity scanner, health check

Tasks are registered as discord.ext.tasks loops and started in on_ready().
"""
