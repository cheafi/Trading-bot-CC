import asyncio
import logging

from src.engines.paper_trading_engine import PaperTradingEngine

# Setup basic logging to see the output in the console
logging.basicConfig(level=logging.INFO, format="%(message)s")

async def force_run():
    print("🚀 Triggering Paper Trading Engine...")
    engine = PaperTradingEngine()
    await engine.execute_top_strategy()
    print("✅ Paper Trading run complete. Check IB Gateway for orders!")

if __name__ == "__main__":
    asyncio.run(force_run())
