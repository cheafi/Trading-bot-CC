#!/usr/bin/env bash
# Fix blank/black CC dashboard — stops broken Docker shell, starts fixed instant server.
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/../.." && pwd)"
cd "$ROOT"

echo "==> Rebuild dashboard gzip bundle..."
if command -v node >/dev/null 2>&1; then
  node scripts/build-cc-template.mjs >/dev/null 2>&1 || true
fi
gzip -c src/api/templates/index.html > src/api/static/cc-dashboard.html.gz
mkdir -p data/cache
cp src/api/static/cc-dashboard.html.gz data/cache/cc-dashboard.html.gz
echo "    gzip bytes: $(wc -c < data/cache/cc-dashboard.html.gz)"

echo "==> Stop Docker API (if running)..."
docker compose -f docker-compose.dev.yml stop api 2>/dev/null || true

echo "==> Free port 8000 and stale instant lock..."
rm -f /tmp/cc_instant.lock
if lsof -ti :8000 >/dev/null 2>&1; then
  lsof -ti :8000 | xargs kill -9 2>/dev/null || true
  sleep 2
fi

export API_SECRET_KEY="${API_SECRET_KEY:-dev-secret-local}"
CC_PORT="${CC_PORT:-8000}"
if lsof -ti :"${CC_PORT}" >/dev/null 2>&1; then
  echo "WARN: port ${CC_PORT} still busy — trying 8080"
  CC_PORT=8080
  if lsof -ti :8080 >/dev/null 2>&1; then
    lsof -ti :8080 | xargs kill -9 2>/dev/null || true
    sleep 1
  fi
fi
export CC_PORT
echo "==> Starting fixed CC instant on http://localhost:${CC_PORT}"
echo "    (Ctrl+C to stop; re-run docker compose up when Docker path is fixed)"
exec python3 -u _cc_instant.py
