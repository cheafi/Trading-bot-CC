#!/usr/bin/env python3
"""Profile import times for main.py and its heavy deps."""

import time, sys

t0 = time.time()
print("Starting import profiling...", flush=True)

for mod in ["pydantic", "numpy", "pandas", "fastapi", "uvicorn", "apscheduler"]:
    t1 = time.time()
    try:
        __import__(mod)
        print(f"  {mod}: {time.time()-t1:.1f}s", flush=True)
    except Exception as e:
        print(f"  {mod}: FAIL {e}", flush=True)

print(f"Deps total: {time.time()-t0:.1f}s", flush=True)

t2 = time.time()
from src.api.main import app  # noqa: F401

print(f"main.py import: {time.time()-t2:.1f}s", flush=True)
print(f"TOTAL: {time.time()-t0:.1f}s", flush=True)
print("IMPORT_OK")
