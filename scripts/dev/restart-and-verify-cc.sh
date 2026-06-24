#!/usr/bin/env bash
# Restart CC API and verify brief/stock data is visible on :8000
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/../.." && pwd)"
cd "$ROOT"

echo "==> Restarting CC API (Docker dev)..."
if docker compose -f docker-compose.dev.yml restart api 2>/dev/null; then
  echo "    docker restart sent"
else
  echo "    docker restart failed — try: docker compose -f docker-compose.dev.yml up -d --force-recreate api"
fi

echo "==> Waiting for health..."
for i in $(seq 1 24); do
  if curl -sf -m 3 http://127.0.0.1:8000/health >/dev/null 2>&1; then
    break
  fi
  sleep 2
done

echo "==> /health"
curl -s -m 5 http://127.0.0.1:8000/health | python3 -m json.tool 2>/dev/null | head -40 || true

echo "==> / (dashboard HTML size)"
curl -s -m 10 -H "Accept-Encoding: gzip" http://127.0.0.1:8000/ -o /tmp/cc_verify.gz || true
curl -s -m 10 -H "Accept-Encoding: identity" http://127.0.0.1:8000/ -o /tmp/cc_verify.html || true
python3 -c "
import gzip
from pathlib import Path
gz=Path('/tmp/cc_verify.gz')
plain=Path('/tmp/cc_verify.html')
if gz.is_file() and gz.stat().st_size>0:
    try:
        data=gzip.decompress(gz.read_bytes())
        print('gzip_bytes', gz.stat().st_size, 'decompressed', len(data))
        ok=len(data)>=600_000 and data.rstrip().endswith(b'</html>')
        print('OK: full dashboard (gzip)' if ok else 'FAIL: gzip decompress truncated — restart api')
    except Exception as e:
        print('gzip decompress failed', e)
elif plain.is_file():
    n=plain.stat().st_size
    t=plain.read_text(encoding='utf-8', errors='ignore')
    print('html_bytes', n)
    if n<600_000 or not t.rstrip().endswith('</html>'):
        print('FAIL: HTML truncated — ensure src/api/static/cc-dashboard.html.gz exists and restart api')
    else:
        print('OK: full dashboard template served')
else:
    print('homepage check failed')
" 2>/dev/null || echo "homepage check failed"

echo "==> /api/v7/playbook/ranked (tickers)"
curl -s -m 10 "http://127.0.0.1:8000/api/v7/playbook/ranked?limit=8" | python3 -c "
import json,sys
d=json.load(sys.stdin)
opps=d.get('opportunities') or []
print('count', d.get('count'), 'source', d.get('source'))
print('tickers', [o.get('ticker') for o in opps[:8]])
if not opps:
    print('WARN: still empty — check docker logs cc_api_dev --tail 50')
    wd=(d.get('warmup_diagnostics') or {})
    if wd: print('warmup_diagnostics', wd)
" 2>/dev/null || echo "ranked request failed"

echo "==> /api/v7/today (top5)"
curl -s -m 10 http://127.0.0.1:8000/api/v7/today | python3 -c "
import json,sys
d=json.load(sys.stdin)
print('top5', [x.get('ticker') for x in (d.get('top_5') or [])])
print('trust', (d.get('trust') or {}).get('source'))
" 2>/dev/null || echo "today request failed"

echo "Done. Hard-refresh browser (Cmd+Shift+R)."
