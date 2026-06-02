#!/usr/bin/env bash
# Minimal health check + restart for _cc_instant.py (port 8000).
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT"
LOG="${CC_SERVER_LOG:-/tmp/cc_server.log}"
PY="${ROOT}/venv/bin/python3"
if curl -sf --max-time 3 http://127.0.0.1:8000/health >/dev/null 2>&1; then
  exit 0
fi
if lsof -nP -iTCP:8000 -sTCP:LISTEN >/dev/null 2>&1; then
  exit 1
fi
nohup "$PY" _cc_instant.py >>"$LOG" 2>&1 &
