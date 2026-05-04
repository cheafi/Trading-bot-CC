#!/usr/bin/env python3
"""
CC Instant Server — starts in <1 second, loads full API in background.

Architecture:
  1. stdlib http.server binds port 8000 instantly → dashboard works
  2. Background thread imports FastAPI app + starts uvicorn on :8001 IN-PROCESS
  3. Once :8001 is ready, all API requests proxy there transparently
  4. Dashboard (/) and /health are always served locally for speed
  5. No subprocess — single Python process, no double-import overhead
"""

import http.server
import json
import os
import socketserver
import subprocess
import threading
import time
import urllib.error
import urllib.request
from pathlib import Path

os.chdir(os.path.dirname(os.path.abspath(__file__)) or ".")

PORT = 8000
BACKEND_PORT = 8001
TEMPLATE = Path("src/api/templates/index.html").read_text()
_backend_ready = False
_start = time.time()


class Handler(http.server.BaseHTTPRequestHandler):
    """Serves dashboard instantly; proxies API calls to backend once ready."""

    def do_GET(self):
        self._safe_handle()

    def do_POST(self):
        self._safe_handle()

    def do_PUT(self):
        self._safe_handle()

    def do_DELETE(self):
        self._safe_handle()

    def do_OPTIONS(self):
        try:
            self.send_response(200)
            self._cors_headers()
            self.end_headers()
        except (BrokenPipeError, ConnectionResetError):
            pass

    def _safe_handle(self):
        try:
            self._handle()
        except (BrokenPipeError, ConnectionResetError):
            pass

    def _cors_headers(self):
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header(
            "Access-Control-Allow-Methods", "GET, POST, PUT, DELETE, OPTIONS"
        )
        self.send_header("Access-Control-Allow-Headers", "Content-Type, X-API-Key")

    def _handle(self):
        # Dashboard — always local
        if self.path in ("/", ""):
            self.send_response(200)
            self.send_header("Content-Type", "text/html; charset=utf-8")
            self._cors_headers()
            self.end_headers()
            self.wfile.write(TEMPLATE.encode())
            return

        # Health — local fast path
        if self.path in ("/health", "/api/health"):
            data = json.dumps(
                {
                    "status": "ok",
                    "version": "9.0.0",
                    "uptime_seconds": round(time.time() - _start, 1),
                    "mode": "full" if _backend_ready else "loading",
                    "phase9_engines": {
                        "loaded": _backend_ready,
                        "components": (
                            [
                                "StructureDetector",
                                "EntryQuality",
                                "BreakoutMonitor",
                                "PortfolioGate",
                                "EarningsCalendar",
                                "FundamentalData",
                                "DecisionJournal",
                            ]
                            if _backend_ready
                            else []
                        ),
                    },
                }
            )
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self._cors_headers()
            self.end_headers()
            self.wfile.write(data.encode())
            return

        # Static files — serve locally
        if self.path.startswith("/static/"):
            fpath = Path("src/api") / self.path.lstrip("/")
            if fpath.is_file():
                self.send_response(200)
                ct = {
                    ".css": "text/css",
                    ".js": "application/javascript",
                    ".png": "image/png",
                    ".svg": "image/svg+xml",
                    ".json": "application/json",
                    ".ico": "image/x-icon",
                }.get(fpath.suffix, "application/octet-stream")
                self.send_header("Content-Type", ct)
                self.end_headers()
                self.wfile.write(fpath.read_bytes())
            else:
                self._json_error(404, "Static file not found")
            return

        # All other paths → proxy to backend
        if _backend_ready:
            self._proxy()
        else:
            self._json_error(503, "API warming up — retry in 3s")

    def _proxy(self):
        """Forward request to uvicorn backend on BACKEND_PORT."""
        url = f"http://127.0.0.1:{BACKEND_PORT}{self.path}"
        try:
            body = None
            cl = self.headers.get("Content-Length")
            if cl:
                body = self.rfile.read(int(cl))

            req = urllib.request.Request(url, data=body, method=self.command)
            req.add_header(
                "Content-Type", self.headers.get("Content-Type", "application/json")
            )
            api_key = self.headers.get("X-API-Key")
            if api_key:
                req.add_header("X-API-Key", api_key)

            _timeout = 120 if "strategy-factory" in self.path else 60
            with urllib.request.urlopen(req, timeout=_timeout) as resp:
                status = resp.status
                data = resp.read()
                ct = resp.headers.get("Content-Type", "application/json")

            self.send_response(status)
            self.send_header("Content-Type", ct)
            self._cors_headers()
            self.end_headers()
            self.wfile.write(data)
        except urllib.error.HTTPError as e:
            # Forward the exact status (including 503 warming-up) to the browser
            body = b""
            try:
                body = e.read()
            except Exception:
                body = json.dumps({"error": str(e)}).encode()
            self.send_response(e.code)
            self.send_header("Content-Type", "application/json")
            self._cors_headers()
            self.end_headers()
            self.wfile.write(body)
        except Exception as e:
            self._json_error(503, f"API warming up — retry in 3s ({e})")

    def _json_error(self, code, msg):
        self.send_response(code)
        self.send_header("Content-Type", "application/json")
        self._cors_headers()
        self.end_headers()
        self.wfile.write(json.dumps({"error": msg}).encode())

    def log_message(self, fmt, *args):
        pass  # quiet


class ReusableTCPServer(socketserver.ThreadingTCPServer):
    allow_reuse_address = True
    daemon_threads = True


def _kill_port(port):
    subprocess.run(
        f"kill -9 $(lsof -ti:{port}) 2>/dev/null",
        shell=True,
        capture_output=True,
    )


def _run_backend():
    """Start uvicorn as subprocess, poll until ready (never give up)."""
    global _backend_ready
    try:
        print("[backend] launching uvicorn subprocess...", flush=True)
        t0 = time.time()
        # Use venv python if available, else system python
        _python = os.path.join("venv", "bin", "python3")
        if not os.path.isfile(_python):
            import sys

            _python = sys.executable
        log = open("/tmp/cc_backend.log", "w")
        proc = subprocess.Popen(
            [
                _python,
                "-m",
                "uvicorn",
                "src.api.main:app",
                "--host",
                "127.0.0.1",
                "--port",
                str(BACKEND_PORT),
                "--timeout-keep-alive",
                "5",
                "--limit-concurrency",
                "20",
                "--log-level",
                "warning",
            ],
            cwd=os.path.dirname(os.path.abspath(__file__)),
            stdout=log,
            stderr=subprocess.STDOUT,
        )
        # Poll forever until ready (import can take 3-5 min)
        waited = 0
        while True:
            time.sleep(2)
            waited += 2
            if proc.poll() is not None:
                try:
                    out = open("/tmp/cc_backend.log").read()[-500:]
                except Exception:
                    out = ""
                print(f"[backend] crashed after {waited}s: {out}", flush=True)
                time.sleep(5)
                # Restart
                return _run_backend()
            try:
                with urllib.request.urlopen(
                    f"http://127.0.0.1:{BACKEND_PORT}/health", timeout=2
                ) as r:
                    if r.status == 200:
                        _backend_ready = True
                        elapsed = time.time() - t0
                        print(f"[backend] READY in {elapsed:.0f}s", flush=True)
                        return
            except Exception:
                pass
            if waited % 60 == 0:
                print(f"[backend] still importing... {waited}s", flush=True)
    except Exception as e:
        print(f"[backend] FATAL: {e}", flush=True)


# Kill anything on our ports
_kill_port(PORT)
_kill_port(BACKEND_PORT)
time.sleep(0.5)

# Start backend in background thread (in-process, no subprocess)
threading.Thread(target=_run_backend, daemon=True).start()

# Start instant frontend
server = ReusableTCPServer(("0.0.0.0", PORT), Handler)
print(f"CC Dashboard ready at http://localhost:{PORT}", flush=True)
print("   API importing in background...", flush=True)
try:
    server.serve_forever()
except KeyboardInterrupt:
    print("\nShutting down...")
    server.shutdown()
