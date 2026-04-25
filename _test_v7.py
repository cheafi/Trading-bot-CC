#!/usr/bin/env python3
"""Test all v7 endpoints."""
import json
import subprocess
import sys
import time
import urllib.request

proc = subprocess.Popen(
    [sys.executable, "_cc_instant.py"],
    stdout=subprocess.DEVNULL,
    stderr=subprocess.DEVNULL,
)

# Wait for server
for i in range(30):
    time.sleep(1)
    try:
        urllib.request.urlopen("http://localhost:8001/api/health", timeout=2)
        print(f"✅ Server up after {i+1}s")
        break
    except Exception:
        pass
else:
    print("❌ Server didn't start")
    proc.terminate()
    sys.exit(1)


def get(path):
    try:
        r = urllib.request.urlopen(f"http://localhost:8001{path}", timeout=180)
        return json.loads(r.read())
    except Exception as e:
        return {"error": str(e)}


# 1. /api/v7/regime
print("\n── /api/v7/regime ──")
d = get("/api/v7/regime")
print(f"  Regime: {d.get('regime')} | Trend: {d.get('trend')} | VIX: {d.get('vix')}")
print(f"  Should trade: {d.get('should_trade')} | Breadth: {d.get('breadth_pct')}%")
xa = d.get("cross_asset", {})
print(f"  Stress: {xa.get('stress_level')} ({xa.get('stress_score')})")

# 2. /api/v7/cross-asset
print("\n── /api/v7/cross-asset ──")
d = get("/api/v7/cross-asset")
ms = d.get("market_state", {})
print(f"  VIX: {ms.get('vix')} | SPY 20d: {ms.get('spy_return_20d')}%")
sr = d.get("stress_report", {})
print(f"  Stress: {sr.get('stress_level')} | Signals: {len(sr.get('signals', []))}")

# 3. /api/v7/learning
print("\n── /api/v7/learning ──")
d = get("/api/v7/learning")
s = d.get("summary", {})
print(f"  Trades: {s.get('total_trades')} | Win rate: {s.get('win_rate')}")

# 4. /api/v7/today (triggers full scan ~60s)
print("\n── /api/v7/today (scanning...) ──")
d = get("/api/v7/today")
if "error" in d:
    print(f"  Error: {d['error'][:100]}")
else:
    t = d.get("top_5", [])
    print(f"  Top {len(t)} signals:")
    for s in t[:5]:
        ec = s.get("expert_council", {})
        print(
            f"    {s['ticker']:5s} action={s['action']:6s} grade={s['grade']:3s} "
            f"sector={s.get('sector_bucket','?')} "
            f"council={ec.get('direction','?')} agree={ec.get('agreement_ratio',0):.0%}"
        )
    print(f"  Actions: {d.get('action_summary', {})}")

# 5. /api/v7/signal-card/AAPL
print("\n── /api/v7/signal-card/AAPL ──")
d = get("/api/v7/signal-card/AAPL")
if "error" in d:
    print(f"  Error: {d['error'][:100]}")
else:
    print(
        f"  {d.get('ticker')} score={d.get('score')} grade={d.get('grade')} "
        f"action={d.get('action')} sector={d.get('sector_bucket','?')}"
    )
    ec = d.get("expert_council", {})
    print(f"  Council: {ec.get('direction')} agree={ec.get('agreement_ratio',0):.0%}")

print("\n✅ ALL TESTS COMPLETE")
proc.terminate()
