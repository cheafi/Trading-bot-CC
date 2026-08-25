#!/bin/bash
# Skip restart if :8000 already serves /health (avoids killing slow backend import).
_lock=/tmp/cc_instant.lock
if [ -f "$_lock" ]; then
  _pid=$(tr -d '[:space:]' < "$_lock" 2>/dev/null)
  if [ -n "$_pid" ] && kill -0 "$_pid" 2>/dev/null; then
    _http=$(curl -s -o /dev/null -w "%{http_code}" --max-time 3 http://127.0.0.1:8000/health 2>/dev/null || echo "000")
    if [ "$_http" = "200" ]; then
      echo "Already healthy on :8000 (pid $_pid) — skip kill/restart"
      curl -s http://127.0.0.1:8000/health
      echo ""
      exit 0
    fi
    if lsof -nP -iTCP:8000 -sTCP:LISTEN >/dev/null 2>&1; then
      echo "CC server pid $_pid still listening on :8000 (import may be in progress) — skip kill/restart"
      exit 0
    fi
    echo "Stale CC server pid $_pid (no listener on :8000) — stopping before restart"
    kill -TERM "$_pid" 2>/dev/null || true
    sleep 1
  else
    echo "Removing stale lock (pid ${_pid:-?} not running)"
  fi
  rm -f "$_lock"
fi

_http=$(curl -s -o /dev/null -w "%{http_code}" --max-time 3 http://127.0.0.1:8000/health 2>/dev/null || echo "000")
if [ "$_http" = "200" ]; then
  echo "Already healthy on :8000 — skip kill/restart"
  curl -s http://127.0.0.1:8000/health
  echo ""
  exit 0
fi
if lsof -nP -iTCP:8000 -sTCP:LISTEN >/dev/null 2>&1; then
  echo "Port 8000 listening (import may be in progress) — skip kill/restart"
  exit 0
fi

# Kill stale listeners only when nothing is listening (SIGTERM only)
for _port in 8000 8001; do
  for _pid in $(lsof -tiTCP:"$_port" -sTCP:LISTEN 2>/dev/null); do
    kill -TERM "$_pid" 2>/dev/null
  done
done
sleep 1

cd "$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
_py="python3"
if [ -x "./venv/bin/python3" ]; then
  _py="./venv/bin/python3"
fi
nohup "$_py" -u _cc_instant.py >> /tmp/cc_server.log 2>&1 &
echo "PID=$!"
sleep 5
curl -s http://127.0.0.1:8000/health
echo ""
