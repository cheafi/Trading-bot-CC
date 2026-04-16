"""
CC Discord Bot — Cogs Package
==============================
Modular command groups (discord.py Cogs) for the CC Discord bot.

Each cog handles a logical command group:
- getting_started: /help, /menu, /status
- market_data: /price, /quote, /market, /sector, /macro, etc.
- ai_analysis: /ai, /analyze, /advise, /score, /compare, etc.
- signals: /signals, /scan, /breakout, /dip, /momentum, etc.
- multi_market: /asia, /japan, /hk, /crypto, /btc
- trading: /portfolio, /buy, /sell, /positions, /pnl, etc.
- tools: /backtest, /best_strategy, /watchlist, /alert, etc.
- dashboard: /daily, /dashboard, /report
- admin: /setup, /announce, /purge, /slowmode, /pin
- advanced: /regime, /leaderboard, /recommendations, etc.

Migration path:
1. New commands should be added as Cogs in this package
2. Existing commands will be gradually migrated from discord_bot.py
3. The bot loads cogs via bot.load_extension() at startup
"""
