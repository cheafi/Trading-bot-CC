#!/bin/bash
set -e
cd /Users/chantszwai/Documents/GitHub/TradingAI_Bot-main

echo "=== ROUTES ==="
for r in slippage/check portfolio/var-historical strategy-health/per-strategy; do
  printf "%-40s " "$r:"
  curl -s -o /dev/null -w "%{http_code}\n" -X OPTIONS "http://127.0.0.1:8000/api/$r"
done

echo ""
echo "=== STRATEGY HEALTH (window=0 all-time) ==="
curl -s "http://127.0.0.1:8000/api/strategy-health/per-strategy?window=0" \
  -H "X-API-Key: dev-secret-local" | python3 ./_smoke_strat.py

echo ""
echo "=== SLIPPAGE GATE (AAPL 100sh @ \$200) ==="
curl -s -X POST http://127.0.0.1:8000/api/slippage/check \
  -H "Content-Type: application/json" \
  -H "X-API-Key: dev-secret-local" \
  -d '{"ticker":"AAPL","size_shares":100,"current_price":200,"side":"BUY"}' | python3 -m json.tool

echo ""
echo "=== SLIPPAGE GATE (illiquid: tiny ticker huge size) ==="
curl -s -X POST http://127.0.0.1:8000/api/slippage/check \
  -H "Content-Type: application/json" \
  -H "X-API-Key: dev-secret-local" \
  -d '{"ticker":"AAPL","size_shares":50000000,"current_price":200,"side":"BUY"}' | python3 -c "import json,sys;d=json.load(sys.stdin);print('verdict:',d.get('verdict'));print('reasons:'); [print('  •',r) for r in d.get('reasons',[])]; print('participation:',d.get('participation_pct'),'%')"

echo ""
echo "=== SERVED HTML MARKER CHECK ==="
curl -s http://127.0.0.1:8000/ | grep -c -E "stratSpark|bracketArchive|slippage/check|HISTSIM"
