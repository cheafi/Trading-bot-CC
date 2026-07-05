#!/usr/bin/env python3
"""Quick test: start server, wait for scan, test /api/v7/today."""
import json
import subprocess
import sys
import time
import urllib.request

print("Starting server...")
proc = subprocess.Popen(
    [sys.executable, "_cc_instant.py"],
    stdout=subprocess.PIPE,
    stderr=subprocess.STDOUT,
)

# Wait for uvicorn to start
for i in range(90):
    time.sleep(1)
    try:
        r = urllib.request.urlopen("http://localhost:8001/api/health", timeout=2)
        if r.status == 200:
            print(f"Server up after {i+1}s")
            break
    except Exception:
        pass
else:
    print("Server didn't start in 90s")
    proc.terminate()
    sys.exit(1)

# Hit /api/v7/today (triggers scan)
print("Fetching /api/v7/today (scan will run ~60s)...")
try:
    r = urllib.request.urlopen("http://localhost:8001/api/v7/today", timeout=180)
    d = json.loads(r.read())
    t = d.get("top_5", [])
    print(f"\nTop {len(t)} signals:")
    for s in t[:5]:
        ec = s.get("expert_council", {})
        print(
            f"  {s['ticker']:5s} action={s['action']:6s} grade={s['grade']:3s} "
            f"sector={s.get('sector_bucket','?')}"
        )
        print(
            f"         council={ec.get('direction','?')} "
            f"agree={ec.get('agreement_ratio',0):.0%} "
            f"risk={ec.get('dominant_risk','?')}"
        )
    print(f"\naction_summary: {d.get('action_summary', {})}")
    print(
        f"sector_summary buckets: {list(d.get('sector_summary', {}).get('buckets', {}).keys())}"
    )
    print("\n✅ SUCCESS")
except Exception as e:
    print(f"ERROR: {e}")

proc.terminate()
