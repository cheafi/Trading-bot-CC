#!/usr/bin/env python3
"""Start server, test all pages, report results."""
import subprocess, time, urllib.request, sys, os

os.chdir("/Users/chantszwai/Documents/GitHub/TradingAI_Bot-main")

# Kill existing
subprocess.run("pkill -9 -f 'uvicorn src.api'", shell=True, capture_output=True)
time.sleep(2)

# Start server
proc = subprocess.Popen(
    [sys.executable, "-m", "uvicorn", "src.api.main:app", "--host", "127.0.0.1", "--port", "8000"],
    stdout=subprocess.PIPE, stderr=subprocess.STDOUT
)
print(f"Server PID={proc.pid}")

# Wait for startup
for i in range(15):
    time.sleep(1)
    try:
        urllib.request.urlopen("http://127.0.0.1:8000/health", timeout=2)
        print(f"Server ready after {i+1}s")
        break
    except Exception:
        pass
else:
    print("Server failed to start!")
    proc.terminate()
    sys.exit(1)

# Test all pages
pages = ['/', '/signal-explorer', '/regime-screener', '/portfolio-brief', '/compare', '/performance-lab', '/options-lab']
all_ok = True
for p in pages:
    try:
        r = urllib.request.urlopen(f'http://127.0.0.1:8000{p}', timeout=10)
        body = r.read()
        status = r.status
        has_html = b'<html' in body.lower() or b'<!doctype' in body.lower()
        print(f"  {p:25s} -> {status}  ({len(body):>6} bytes)  HTML={'✓' if has_html else '✗'}")
        if status != 200:
            all_ok = False
    except Exception as e:
        print(f"  {p:25s} -> ERROR: {e}")
        all_ok = False

# Test APIs
apis = ['/api/v7/regime-screener', '/api/v7/portfolio-brief', '/api/v7/performance-lab']
for a in apis:
    try:
        r = urllib.request.urlopen(f'http://127.0.0.1:8000{a}', timeout=30)
        body = r.read()
        print(f"  {a:45s} -> {r.status}  ({len(body):>6} bytes)")
    except Exception as e:
        print(f"  {a:45s} -> ERROR: {e}")

print(f"\n{'ALL PAGES OK ✓' if all_ok else 'SOME PAGES FAILED ✗'}")
print(f"Server still running at http://127.0.0.1:8000 (PID={proc.pid})")
