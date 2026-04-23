#!/usr/bin/env python3
"""Ultra-minimal HTTP server - zero dependencies, starts instantly.
Serves dashboard HTML + proxies to full app once loaded."""
import http.server
import json
import os
import threading
import time
from pathlib import Path

os.chdir(os.path.dirname(os.path.abspath(__file__)) or ".")

PORT = 8000
TEMPLATE = Path("src/api/templates/index.html").read_text()
_full_app = None
_start = time.time()


class Handler(http.server.SimpleHTTPRequestHandler):
    def do_GET(self):
        if self.path == "/health" or self.path == "/api/health":
            data = json.dumps({"status": "ok",
                               "uptime_seconds": round(time.time() - _start, 1),
                               "mode": "full" if _full_app else "lite"})
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.end_headers()
            self.wfile.write(data.encode())
        elif self.path == "/" or self.path == "":
            self.send_response(200)
            self.send_header("Content-Type", "text/html; charset=utf-8")
            self.end_headers()
            self.wfile.write(TEMPLATE.encode())
        elif self.path.startswith("/static/"):
            self.directory = "src/api"
            super().do_GET()
        else:
            self.send_response(404)
            self.send_header("Content-Type", "application/json")
            self.end_headers()
            self.wfile.write(json.dumps({"error": "not found", "path": self.path}).encode())

    def log_message(self, format, *args):
        pass  # quiet


def _load_full():
    global _full_app
    time.sleep(5)
    try:
        print("Loading full FastAPI app in background...", flush=True)
        from src.api.main import app
        _full_app = app
        print("Full app loaded! Restarting on uvicorn...", flush=True)
        # Replace this server with uvicorn
        import uvicorn
        server.shutdown()
        uvicorn.run(app, host="0.0.0.0", port=PORT, log_level="info")
    except Exception as e:
        print(f"Background load failed: {e}", flush=True)


print(f"CC Lite server starting on http://0.0.0.0:{PORT}", flush=True)
server = http.server.HTTPServer(("0.0.0.0", PORT), Handler)
threading.Thread(target=_load_full, daemon=True).start()
print(f"✅ Dashboard ready at http://localhost:{PORT}", flush=True)
server.serve_forever()
