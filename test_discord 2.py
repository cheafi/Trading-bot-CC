"""Quick test: send a message to Discord and exit."""
import discord
import asyncio
import os
from dotenv import load_dotenv

load_dotenv()
token = os.getenv("DISCORD_BOT_TOKEN")

intents = discord.Intents.default()
intents.message_content = True
client = discord.Client(intents=intents)


@client.event
async def on_ready():
    print(f"Bot connected as: {client.user}")
    for guild in client.guilds:
        print(f"  Server: {guild.name}")
        for ch in guild.text_channels:
            if ch.permissions_for(guild.me).send_messages:
                embed = discord.Embed(
                    title="\U0001f916 TradingAI Bot v2.0 \u2014 Online",
                    description=(
                        "Multi-Market AI Trading System connected successfully.\n\n"
                        "**Coverage:** US \u00b7 HK \u00b7 JP \u00b7 Crypto\n"
                        "**Brokers:** Alpaca (Paper) \u00b7 Futu \u00b7 IB\n"
                        "**AI:** GPT Signal Validation \u00b7 ML Trade Learning\n"
                        "**Status:** All systems operational"
                    ),
                    color=0x00FF88,
                )
                embed.set_footer(text="TradingAI Pro \u2022 24/7 Autonomous Trading")
                await ch.send(embed=embed)
                print(f"Message sent to #{ch.name}")
                break
    await client.close()


asyncio.run(client.start(token))
