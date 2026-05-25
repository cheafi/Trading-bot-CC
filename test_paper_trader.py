import asyncio
import sys
import os
sys.path.append(os.getcwd())

async def run_test():
    try:
        from src.engines.paper_trading_engine import PaperTradingEngine
        engine = PaperTradingEngine()
        print("PaperTradingEngine initialized successfully.")
    except Exception as e:
        print(f"Error initializing: {e}")

if __name__ == "__main__":
    asyncio.run(run_test())
