import asyncio
import yfinance as yf
import time
from src.scanners.us_universe import US_UNIVERSE

async def run():
    tickers = list(dict.fromkeys(US_UNIVERSE))
    print(f"Total tickers: {len(tickers)}")
    t0 = time.time()
    
    chunk_size = 100
    chunks = [tickers[i : i + chunk_size] for i in range(0, len(tickers), chunk_size)]
    
    sem = asyncio.Semaphore(10)
    
    async def _download_chunk(chunk):
        async with sem:
            return await asyncio.to_thread(
                yf.download,
                " ".join(chunk),
                period="2mo",
                auto_adjust=True,
                group_by="ticker",
                progress=False,
                threads=True,
            )

    dfs = await asyncio.gather(*[_download_chunk(c) for c in chunks])
    print(f"Took {time.time()-t0:.2f} seconds for all")

asyncio.run(run())
