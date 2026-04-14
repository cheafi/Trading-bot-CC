#!/usr/bin/env python3
"""Test the Macro Intelligence API endpoint."""
import json
import urllib.request

r = urllib.request.urlopen(
    'http://127.0.0.1:8000/api/v7/macro-intel', timeout=300)
d = json.loads(r.read())

print('=== MACRO INTEL API ===')
rates = d.get('rates', {})
print(f'Rates: {len(rates.get("yields", []))} yields')
print(f'  Curve: {rates.get("curve", {})}')
print(f'  Direction: {rates.get("direction")}')
print(f'  ETFs: {len(rates.get("etfs", []))}')

pol = d.get('political_risk', {})
print(f'Political: {len(pol.get("basket", []))} tickers')
print(f'  Trump: {pol.get("trump_sentiment")}')
print(f'  DJT: ${pol.get("djt_price")}')

war = d.get('war_geopolitical', {})
print(f'War: {len(war.get("basket", []))} tickers')
print(f'  Risk: {war.get("risk_label")} ({war.get("risk_score")}/100)')

ins = d.get('insider_proxy', {})
print(f'Insider: {len(ins.get("watchlist", []))} execs')
print(f'  Accumulate: {ins.get("accumulate_count")}')
print(f'  Distribute: {ins.get("distribute_count")}')

corr = d.get('correlations', {})
print(f'Correlations: {len(corr.get("labels", []))} factors')
print(f'  Insights: {len(corr.get("insights", []))}')
for i in corr.get('insights', []):
    print(f'    {i["factor"]} r={i["corr"]}: {i["text"]}')

print(f'Summary: {d.get("summary", {})}')
print(f'Generated: {d.get("generated_at")}')
