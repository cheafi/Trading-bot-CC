#!/usr/bin/env bash
# Quick integration sweep for TradingAI API — exit 1 on any failure
set -euo pipefail
BASE="${BASE_URL:-http://127.0.0.1:8000}"
fail=0

check() {
  local name="$1" url="$2" expect="${3:-200}"
  local timeout="${4:-30}" code tries=4
  for _ in $(seq 1 "$tries"); do
    code=$(curl -s -o /tmp/cc_test_body.json -w '%{http_code}' --max-time "$timeout" "$url" || echo "000")
    if [ "$code" = "$expect" ]; then
      echo "OK  $code $name"
      sleep 0.35
      return 0
    fi
    sleep 2
  done
  echo "FAIL $code (want $expect) $name"
  head -c 200 /tmp/cc_test_body.json 2>/dev/null; echo
  fail=1
  sleep 0.35
}

check_post() {
  local name="$1" url="$2" data="$3" expect="${4:-200}"
  local timeout="${5:-30}" code tries=4
  for _ in $(seq 1 "$tries"); do
    code=$(curl -s -o /tmp/cc_test_body.json -w '%{http_code}' --max-time "$timeout" \
      -X POST -H "Content-Type: application/json" -H "X-API-Key: dev-secret-local" \
      -d "$data" "$url" || echo "000")
    if [ "$code" = "$expect" ]; then
      echo "OK  $code $name"
      sleep 0.35
      return 0
    fi
    sleep 2
  done
  echo "FAIL $code (want $expect) $name"
  head -c 200 /tmp/cc_test_body.json 2>/dev/null; echo
  fail=1
  sleep 0.35
}

echo "=== Core ==="
check health "$BASE/health"
check healthz "$BASE/healthz"
check dashboard "$BASE/" 200

echo "=== Live (extracted routers) ==="
check live_market "$BASE/api/live/market"
check live_quote "$BASE/api/live/quote/AAPL"
check live_spark "$BASE/api/live/spark/AAPL"
check live_strategies "$BASE/api/live/strategies"
check live_chart "$BASE/api/live/chart/AAPL?period=3mo"
check live_dossier "$BASE/api/live/dossier/AAPL" 200 45
check stock_intel "$BASE/api/v7/stock-intel/AAPL" 200 120
check live_perf "$BASE/api/live/perf-vs-spy/AAPL?period=1y" 200 45

echo "=== Decision / playbook ==="
check today "$BASE/api/v7/today" 200 30
check decision_hub "$BASE/api/v7/decision-hub" 200 60
check ranked "$BASE/api/v7/playbook/ranked?limit=3" 200 45
check dossier_peers "$BASE/api/dossier/AAPL/peers" 200 90
check rs "$BASE/api/v7/playbook/rs-ranking?limit=3" 200 45
check no_trade "$BASE/api/v7/playbook/no-trade" 200 90
check flow "$BASE/api/v7/playbook/flow?limit=5" 200 30

echo "=== New routers ==="
check conviction "$BASE/api/v1/conviction/NVDA" 200 30
check funds "$BASE/api/fund-lab/cards" 200 45
check radar "$BASE/api/v1/options-radar/top?limit=2" 200 30
check edgar "$BASE/api/edgar/AAPL/insider" 200 20
check fred "$BASE/api/macro/fred" 200 20
check scenarios "$BASE/api/scenarios" 200 15
check v7_screener "$BASE/api/v7/regime-screener" 200 60
check v7_today "$BASE/api/v7/playbook/today" 200 60

echo "=== Risk / ops ==="
check_post slippage "$BASE/api/slippage/check" '{"ticker":"AAPL","size_shares":100,"current_price":200,"side":"BUY"}'
check strat_health "$BASE/api/strategy-health/per-strategy?window=30"
check ops "$BASE/api/ops/status" 200 15
check live_brief_ep "$BASE/api/live/brief" 200 30
code=$(curl -s -o /tmp/cc_test_body.json -w '%{http_code}' --max-time 90 -X POST \
  "$BASE/api/live/backtest?ticker=AAPL&period=3mo&strategy=momentum" || echo "000")
if [ "$code" = "200" ]; then echo "OK  $code live_backtest"; else echo "FAIL $code (want 200) live_backtest"; head -c 200 /tmp/cc_test_body.json; echo; fail=1; fi
sleep 0.5

if [ "$fail" -ne 0 ]; then
  echo "=== SOME CHECKS FAILED ==="
  exit 1
fi
echo "=== ALL CHECKS PASSED ==="
