#!/usr/bin/env python3
import urllib.request

pages = [
    '/', '/signals/explorer', '/regime-screener',
    '/portfolio-brief', '/compare', '/performance-lab',
    '/options-lab', '/macro-intel',
]
for p in pages:
    try:
        r = urllib.request.urlopen(
            f'http://127.0.0.1:8000{p}', timeout=15)
        body = r.read()
        has_new = (b'JetBrains Mono' in body
                   or b'--bg:#0d1117' in body)
        print(f'{p:25s} -> {r.status}'
              f'  {len(body):>6}b  new_design={has_new}')
    except Exception as e:
        print(f'{p:25s} -> ERR: {e}')
print('Done')
