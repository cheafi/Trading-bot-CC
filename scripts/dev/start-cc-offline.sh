#!/usr/bin/env bash
# Start CC dashboard WITHOUT :8001 backend — brief/snapshot boards only (fast, no uvicorn).
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/../.." && pwd)"
cd "$ROOT"

if lsof -ti :8000 >/dev/null 2>&1; then
  echo "Port 8000 is in use. Stop Docker first:"
  echo "  docker compose -f docker-compose.dev.yml stop api"
  echo "Or kill the process: lsof -ti :8000 | xargs kill -9"
  exit 1
fi

export CC_INSTANT_NO_BACKEND=1
echo "Starting CC offline at http://localhost:8000 (brief fallback only, no live backend)"
exec python3 -u _cc_instant.py
