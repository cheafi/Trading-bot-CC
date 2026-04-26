"""Test all endpoints to find problems."""

import json
import urllib.request

endpoints = [
    "/health",
    "/api/live/market",
    "/api/recommendations",
    "/api/v7/today",
    "/api/v7/opportunities",
    "/api/v7/playbook/ranked",
    "/api/v7/playbook/scanners",
    "/api/v7/playbook/no-trade",
    "/api/v7/playbook/rs-ranking",
    "/api/v7/playbook/flow",
    "/api/v7/playbook/backtest-vs-benchmark?period=1y&benchmark=SPY",
]

for ep in endpoints:
    try:
        r = urllib.request.urlopen(f"http://127.0.0.1:8001{ep}", timeout=10)
        d = json.loads(r.read())
        keys = list(d.keys())[:6]
        size = len(json.dumps(d))
        empty = all(
            (isinstance(v, (list, dict)) and len(v) == 0)
            or (isinstance(v, (int, float)) and v == 0)
            or (isinstance(v, str) and len(v) < 3)
            or v is None
            for v in d.values()
        )
        tag = "EMPTY" if empty else "OK"
        print(f"{tag:6} {ep:50} {size:>6}b keys={keys}")
    except urllib.error.URLError as e:
        if "timed out" in str(e):
            print(f"SLOW   {ep:50} timeout >10s (yfinance?)")
        else:
            print(f"ERROR  {ep:50} {str(e)[:80]}")
    except Exception as e:
        print(f"ERROR  {ep:50} {str(e)[:80]}")
