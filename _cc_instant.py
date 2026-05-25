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
import gzip
import urllib.error
import urllib.request
from pathlib import Path

os.chdir(os.path.dirname(os.path.abspath(__file__)) or ".")

PORT = 8000
BACKEND_PORT = 8001
TEMPLATE = Path("src/api/templates/index.html").read_text()
TEMPLATE_BYTES = TEMPLATE.encode()
TEMPLATE_GZIP = gzip.compress(TEMPLATE_BYTES)
_backend_ready = False
_start = time.time()
_SNAPSHOT_PATH = Path("data/market_overview_last_good.json")


def _proxy_timeout(path: str) -> int:
    """Keep dashboard-critical calls from hanging the instant server."""
    if path.startswith("/api/v7/opportunity-scanner") and "force_refresh=true" in path:
        return 35
    if path.startswith(
        (
            "/healthz",
            "/readyz",
            "/api/health",
            "/api/live/market",
            "/api/recommendations",
            "/api/v7/today",
        )
    ):
        return 5
    if "strategy-factory" in path:
        return 120
    if path.startswith("/api/v7/macro-intel"):
        return 120
    if path.startswith(
        (
            "/api/v7/portfolio-brief",
            "/api/v7/performance-lab",
            "/api/v7/regime-screener",
            "/api/v7/compare-overlay",
            "/api/live/backtest",
            "/api/live/brief",
            "/api/live/dossier/",
            "/api/live/time-travel",
            "/api/v7/stock-intel/",
            "/api/v7/decision-hub",
            "/api/v7/portfolio-decision",
            "/api/dossier/",
            "/api/v7/playbook/no-trade",
        )
    ):
        return 90
    return 20


def _dashboard_api_key(header_value: str | None) -> str | None:
    """Return the API key the local dashboard proxy should send upstream.

    The static dashboard historically falls back to ``dev-secret-local``. In
    prod-local runs the real key can be supplied from ``.env`` and differ from
    that fallback, which caused authenticated Ops panels to stay blank with
    401s. Keep the real key server-side and only rewrite the known dashboard
    fallback inside this local proxy.
    """
    actual = os.environ.get("API_SECRET_KEY") or None
    if actual and (not header_value or header_value == "dev-secret-local"):
        return actual
    return header_value


def _load_snapshot():
    """Return last-good market overview bytes (with stale flag), or None."""
    try:
        if not _SNAPSHOT_PATH.is_file():
            return None
        raw = _SNAPSHOT_PATH.read_bytes()
        try:
            data = json.loads(raw)
            trust = dict(data.get("trust") or {})
            trust.update(
                {
                    "source": "snapshot",
                    "stale": True,
                    "reason": "backend importing",
                }
            )
            data["trust"] = trust
            return json.dumps(data).encode()
        except Exception:
            return raw
    except Exception:
        return None


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
        global _backend_ready

        # Dashboard — always local
        if self.path in ("/", ""):
            use_gzip = "gzip" in self.headers.get("Accept-Encoding", "").lower()
            body = TEMPLATE_GZIP if use_gzip else TEMPLATE_BYTES
            self.send_response(200)
            self.send_header("Content-Type", "text/html; charset=utf-8")
            if use_gzip:
                self.send_header("Content-Encoding", "gzip")
            self.send_header("Content-Length", str(len(body)))
            self.send_header("Cache-Control", "public, max-age=30")
            self._cors_headers()
            self.end_headers()
            self.wfile.write(body)
            return

        # Health — local fast path (mode=full only when uvicorn is listening)
        if self.path in ("/health", "/api/health"):
            listening = _backend_listening()
            data = json.dumps(
                {
                    "status": "ok",
                    "version": "9.0.0",
                    "uptime_seconds": round(time.time() - _start, 1),
                    "mode": "full" if listening else "loading",
                    "phase9_engines": {
                        "loaded": listening,
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
                            if listening
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

        # All other paths → proxy to backend (must be listening, not just imported)
        if _mark_backend_ready():
            self._proxy()
        else:
            # Snapshot-first fallback for dashboard-critical endpoints so the
            # UI never gets stuck on a "warming up" 503 during cold start.
            if self.path.startswith("/api/live/market"):
                snap = _load_snapshot()
                if snap is not None:
                    self.send_response(200)
                    self.send_header("Content-Type", "application/json")
                    self._cors_headers()
                    self.end_headers()
                    self.wfile.write(snap)
                    return
            if self.path in ("/healthz", "/readyz"):
                self.send_response(200)
                self.send_header("Content-Type", "application/json")
                self._cors_headers()
                self.end_headers()
                self.wfile.write(
                    json.dumps(
                        {
                            "status": "ok",
                            "alive": True,
                            "ready": False,
                            "mode": "loading",
                            "uptime_seconds": round(time.time() - _start, 1),
                        }
                    ).encode()
                )
                return
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
            api_key = _dashboard_api_key(self.headers.get("X-API-Key"))
            if api_key:
                req.add_header("X-API-Key", api_key)

            _timeout = _proxy_timeout(self.path)
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


def _backend_listening() -> bool:
    import socket

    try:
        with socket.create_connection(("127.0.0.1", BACKEND_PORT), timeout=0.5):
            return True
    except OSError:
        return False


def _mark_backend_ready() -> bool:
    """Set ready flag once uvicorn is accepting connections."""
    global _backend_ready
    if _backend_listening():
        _backend_ready = True
    return _backend_ready


def _run_backend():
    """Import FastAPI app and start uvicorn IN-PROCESS (no subprocess).

    This avoids the macOS Gatekeeper double-scan that causes 5-10 min hangs
    when a subprocess re-imports pydantic/numpy .so files.
    """
    global _backend_ready
    try:
        print("[backend] importing src.api.main (in-process)...", flush=True)
        t0 = time.time()

        # Heavy import happens HERE in this thread — same process,
        # so Gatekeeper only scans .so files once.
        import uvicorn
        from src.api.main import app as _app  # noqa: F811

        elapsed = time.time() - t0
        print(
            f"[backend] import done in {elapsed:.0f}s — starting uvicorn...", flush=True
        )

        def _mark_ready_on_startup():
            global _backend_ready
            _backend_ready = True
            print("[backend] uvicorn listening — proxy enabled", flush=True)

        @_app.on_event("startup")
        async def _cc_backend_startup():
            _mark_ready_on_startup()

        # Run uvicorn in this thread (blocking — but it's a daemon thread)
        _uvicorn_kw: dict = {
            "host": "127.0.0.1",
            "port": BACKEND_PORT,
            "timeout_keep_alive": 5,
            "log_level": "warning",
        }
        # Dev: no concurrency cap — macro-intel + verify burst otherwise get 503
        if os.getenv("CC_ENV") != "development":
            _uvicorn_kw["limit_concurrency"] = 20
        uvicorn.run(_app, **_uvicorn_kw)
    except Exception as e:
        print(f"[backend] FATAL: {e}", flush=True)
        import traceback

        traceback.print_exc()


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
