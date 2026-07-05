import yfinance as yf
import time
from src.scanners.us_universe import US_UNIVERSE

tickers = list(dict.fromkeys(US_UNIVERSE))
print(f"Total tickers: {len(tickers)}")
t0 = time.time()
df = yf.download(" ".join(tickers), period="1y", auto_adjust=True, group_by="ticker", progress=False, threads=True)
print(f"Took {time.time()-t0:.2f} seconds for all")
