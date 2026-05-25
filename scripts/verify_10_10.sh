#!/usr/bin/env bash
# Clarity Console 10/10 verification — exit 1 on any failure
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
BASE="${BASE_URL:-http://127.0.0.1:8000}"
KEY="${API_KEY:-dev-secret-local}"
fail=0

say() { echo "$*"; }
ok() { say "  OK  $*"; }
bad() { say "  FAIL $*"; fail=1; }

# Retry transient 503s (uvicorn concurrency / proxy warmup under burst load)
check_http() {
  local label="$1" url="$2" timeout="${3:-45}" method="${4:-GET}"
  local c tries=4
  for _ in $(seq 1 "$tries"); do
    if [ "$method" = "POST" ]; then
      c=$(curl -s -o /dev/null -w '%{http_code}' --max-time "$timeout" -X POST "$url" || echo "000")
    else
      c=$(curl -s -o /dev/null -w '%{http_code}' --max-time "$timeout" "$url" || echo "000")
    fi
    if [ "$c" = "200" ]; then
      ok "$label"
      return 0
    fi
    sleep 2
  done
  bad "$label HTTP $c"
  return 0
}

say "=== CC 10/10 verify ==="

# Wait for uvicorn backend (proxy /api/health reports mode:full when ready)
for i in $(seq 1 40); do
  mode=$(curl -sf --max-time 3 "$BASE/api/health" 2>/dev/null \
    | python3 -c "import json,sys; print(json.load(sys.stdin).get('mode',''))" 2>/dev/null \
    || echo "")
  if [ "$mode" = "full" ]; then
    ok "backend ready (${i})"
    break
  fi
  sleep 3
done

# Heavy endpoint first while server is idle (avoids 503 after endpoint burst)
sleep 8
check_http "/api/v7/macro-intel" "$BASE/api/v7/macro-intel" 120

# 1) CC header aggregate (freshness can take ~10s on first poll after cold start)
sleep 2
data="?" brief="?" alerts="-1" mode="?"
for _ in $(seq 1 6); do
  hdr=$(curl -sf --max-time 45 -H "X-API-Key: $KEY" "$BASE/api/ops/cc-header" 2>/dev/null || echo "")
  data=$(echo "$hdr" | python3 -c "import json,sys; d=json.load(sys.stdin); print((d.get('pills') or {}).get('data','?'))" 2>/dev/null || echo "?")
  brief=$(echo "$hdr" | python3 -c "import json,sys; d=json.load(sys.stdin); print((d.get('pills') or {}).get('brief','?'))" 2>/dev/null || echo "?")
  alerts=$(echo "$hdr" | python3 -c "import json,sys; d=json.load(sys.stdin); print((d.get('pills') or {}).get('alerts',-1))" 2>/dev/null || echo "-1")
  mode=$(echo "$hdr" | python3 -c "import json,sys; d=json.load(sys.stdin); print(d.get('display_mode','?'))" 2>/dev/null || echo "?")
  if [ "$data" = "FRESH" ] && [ "$brief" = "FRESH" ] && [ "$alerts" = "0" ]; then
    break
  fi
  sleep 3
done

if [ "$data" = "FRESH" ]; then ok "DATA $data"; else bad "DATA $data (want FRESH)"; fi
if [ "$brief" = "FRESH" ]; then ok "BRIEF $brief"; else bad "BRIEF $brief (want FRESH)"; fi
if [ "$alerts" = "0" ]; then ok "ALERTS 0"; else bad "ALERTS $alerts (want 0)"; fi
if [ "$mode" = "PAPER" ] || [ "$mode" = "LIVE" ]; then ok "MODE $mode"; else bad "MODE $mode"; fi

sleep 1
# 2) Smoke
if bash "$ROOT/_smoke.sh" >/dev/null 2>&1; then ok "smoke.sh"; else bad "smoke.sh"; fi

sleep 8
# 3) API sweep (retry once — prior cc-header/smoke can briefly saturate concurrency)
api_ok=0
for _ in 1 2; do
  if bash "$ROOT/scripts/test_api_endpoints.sh" >/dev/null 2>&1; then
    api_ok=1
    break
  fi
  sleep 5
done
if [ "$api_ok" = "1" ]; then ok "test_api_endpoints.sh"; else bad "test_api_endpoints.sh"; fi

sleep 3
# 4) Extracted live routes (retries on transient 503)
check_http "/api/live/brief" "$BASE/api/live/brief" 90
check_http "/api/live/options/AAPL" "$BASE/api/live/options/AAPL" 30
check_http "POST /api/live/backtest" \
  "$BASE/api/live/backtest?ticker=AAPL&period=3mo&strategy=momentum" 60 POST
check_http "/api/v6/scoreboard" "$BASE/api/v6/scoreboard" 45
check_http "/api/v7/regime-screener" "$BASE/api/v7/regime-screener" 45
sleep 1
check_http "/api/v7/playbook/today" "$BASE/api/v7/playbook/today" 45
check_http "/api/v7/stock-intel/AAPL" "$BASE/api/v7/stock-intel/AAPL" 120
check_http "/api/v7/decision-hub" "$BASE/api/v7/decision-hub" 60
check_http "/api/v7/portfolio-decision" "$BASE/api/v7/portfolio-decision" 45

# 5) Unit tests (host) — no pytest required
if python3 -m unittest tests.test_best_action tests.test_today_insights tests.test_execution_readiness tests.test_fund_manager_console tests.test_stock_intel tests.test_decision_hub tests.test_portfolio_decision_console -q 2>/dev/null; then
  ok "unittest best_action today_insights execution_readiness stock_intel"
else
  bad "unittest suite"
fi

# 6) Optional pytest
if python3 -m pytest "$ROOT/tests/test_data_freshness_service.py" -q --tb=line 2>/dev/null; then
  ok "pytest data_freshness"
else
  say "  SKIP pytest data_freshness (optional)"
fi

if [ "$fail" -ne 0 ]; then
  say "=== NOT 10/10 — fix failures above ==="
  exit 1
fi
say "=== 10/10 PASS (IBKR optional — connect Gateway for broker pill) ==="
