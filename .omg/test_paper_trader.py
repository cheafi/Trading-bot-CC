import asyncio
from src.engines.paper_trading_engine import PaperTradingEngine

import logging
logging.basicConfig(level=logging.INFO)

async def main():
    engine = PaperTradingEngine()
    await engine.execute_top_strategy()

if __name__ == "__main__":
    asyncio.run(main())
