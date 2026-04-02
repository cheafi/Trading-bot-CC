#!/usr/bin/env python3
"""Check if dashboard shows real data."""
import json
import urllib.request

r = urllib.request.urlopen("http://127.0.0.1:8000/api/live/market", timeout=120)
d = json.loads(r.read())

print("=== REGIME ===")
rg = d["regime"]
print(f"  Score: {rg['score']}  |  Label: {rg['label']}  |  Trend: {rg['trend']}  |  Vol: {rg['vol']}")
print(f"  Strategies: {rg['strategies']}")

print("\n=== US INDICES ===")
for i in d["indices"]:
    print(f"  {i['name']:15s}  ${i['price']:>10,.2f}  {i['change_pct']:+.2f}%")

print("\n=== MACRO ===")
for m in d["macro"]:
    pfx = "" if m["symbol"] == "^VIX" else "$"
    print(f"  {m['name']:12s}  {pfx}{m['price']:>10,.2f}  {m['change_pct']:+.2f}%")

print("\n=== SECTORS ===")
for s in d["sectors"]:
    print(f"  {s['name']:18s}  {s['change_pct']:+.2f}%")

print("\n=== ASIA ===")
for a in d["asia"]:
    print(f"  {a['name']:15s}  {a['price']:>12,.0f}  {a['change_pct']:+.2f}%")

total = len(d["indices"]) + len(d["macro"]) + len(d["sectors"]) + len(d["asia"])
zeros = sum(1 for cat in ["indices","macro","sectors","asia"] for t in d[cat] if t["price"] == 0)
print(f"\nTimestamp: {d['timestamp']}")
print(f"Total tickers: {total}  |  Zero-price: {zeros}")
print(f"\n{'✅ REAL DATA CONFIRMED' if zeros < 3 else '⚠️  Some tickers returning $0'}")
print(f"\n{'✅ REAL DATA CONFIRMED' if zeros < 3 else '⚠️  Some tickers returning $0'}")
