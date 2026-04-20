"""
CC Discord Bot — Cogs Package
==============================
Modular command groups (discord.py Cogs) for the CC Discord bot.

Each cog handles a logical command group. New commands should be
added as Cogs in this package. Existing commands in discord_bot.py
will be gradually migrated here.

Available Cogs:
- risk_alerts:    /risk_status, /circuit_breaker
- regime_monitor: /regime

Migration path:
1. New commands → add as Cogs here
2. Existing commands → gradually migrate from discord_bot.py
3. The bot loads cogs via bot.load_extension() at startup

To load all cogs at bot startup:
    for ext in EXTENSIONS:
        await bot.load_extension(ext)
"""

EXTENSIONS = [
    "src.notifications.cogs.risk_alerts",
    "src.notifications.cogs.regime_monitor",
]
