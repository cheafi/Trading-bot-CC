"""HTTP-level tests for instant server auth, static paths, and POST body handling."""

from __future__ import annotations

import http.client
import json
import threading
from contextlib import contextmanager
from typing import Iterator

import pytest

import _cc_instant as instant


@contextmanager
def _instant_http_server(
    monkeypatch: pytest.MonkeyPatch,
    *,
    backend_ready: bool = False,
) -> Iterator[tuple[str, int]]:
    monkeypatch.setattr(instant, "_backend_ready", backend_ready)

    def _mark() -> bool:
        return backend_ready

    monkeypatch.setattr(instant, "_mark_backend_ready", _mark)

    server = instant.ReusableTCPServer(("127.0.0.1", 0), instant.Handler)
    host, port = server.server_address
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        yield host, port
    finally:
        server.shutdown()
        server.server_close()
        thread.join(timeout=5)


def _request(
    host: str,
    port: int,
    method: str,
    path: str,
    *,
    headers: dict[str, str] | None = None,
    body: bytes | None = None,
) -> tuple[int, bytes]:
    conn = http.client.HTTPConnection(host, port, timeout=10)
    try:
        conn.request(method, path, body=body, headers=headers or {})
        resp = conn.getresponse()
        return resp.status, resp.read()
    finally:
        conn.close()


def test_static_path_traversal_rejected(monkeypatch: pytest.MonkeyPatch) -> None:
    with _instant_http_server(monkeypatch) as (host, port):
        for path in (
            "/static/../../_cc_instant.py",
            "/static/%2e%2e/%2e%2e/_cc_instant.py",
            "/static/../templates/index.html",
        ):
            status, _ = _request(host, port, "GET", path)
            assert status == 404


def test_static_known_asset_served(monkeypatch: pytest.MonkeyPatch) -> None:
    js_path = instant._INSTANT_STATIC_DIR / "cc-app.js"
    if not js_path.is_file():
        pytest.skip("cc-app.js not present in static dir")
    with _instant_http_server(monkeypatch) as (host, port):
        status, body = _request(host, port, "GET", "/static/cc-app.js")
        assert status == 200
        assert len(body) > 100


def test_degraded_portfolio_monitor_requires_api_key(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("API_SECRET_KEY", "integration-test-secret-key")
    with _instant_http_server(monkeypatch) as (host, port):
        status, raw = _request(host, port, "GET", "/api/portfolio/monitor")
        assert status == 401
        assert json.loads(raw.decode()).get("detail")

        status, _ = _request(
            host,
            port,
            "GET",
            "/api/portfolio/monitor",
            headers={"X-API-Key": "wrong-key"},
        )
        assert status == 401

        status, raw = _request(
            host,
            port,
            "GET",
            "/api/portfolio/monitor",
            headers={"X-API-Key": "integration-test-secret-key"},
        )
        assert status == 200
        payload = json.loads(raw.decode())
        assert "positions" in payload


def test_degraded_portfolio_position_post_requires_api_key(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path,
) -> None:
    monkeypatch.setenv("API_SECRET_KEY", "integration-test-secret-key")
    monkeypatch.setattr(
        instant, "_PORTFOLIO_LOCAL_PATH", tmp_path / "portfolio_local_holdings.json"
    )

    body = json.dumps(
        {"ticker": "AAPL", "shares": 1, "entry_price": 100.0}
    ).encode()

    with _instant_http_server(monkeypatch) as (host, port):
        status, _ = _request(host, port, "POST", "/api/portfolio/position", body=body)
        assert status == 401

        status, raw = _request(
            host,
            port,
            "POST",
            "/api/portfolio/position",
            body=body,
            headers={
                "Content-Type": "application/json",
                "X-API-Key": "integration-test-secret-key",
            },
        )
        assert status == 200
        assert json.loads(raw.decode()).get("status") == "added"


def test_proxy_receives_pre_read_post_body(monkeypatch: pytest.MonkeyPatch) -> None:
    """Proxy must use the body read once in _handle (no second rfile.read)."""
    captured: dict[str, bytes | None] = {}

    def spy_proxy(self, body: bytes | None = None) -> bool:
        captured["body"] = body
        return False

    monkeypatch.setattr(instant.Handler, "_proxy", spy_proxy)

    payload = b'{"mode":"paper"}'
    with _instant_http_server(monkeypatch, backend_ready=True) as (host, port):
        status, raw = _request(
            host,
            port,
            "POST",
            "/api/ibkr/connect",
            body=payload,
            headers={"Content-Type": "application/json"},
        )
        assert captured.get("body") == payload
        assert status == 503
        detail = json.loads(raw.decode())
        assert detail.get("degraded") is True or detail.get("ok") is False


def test_safe_static_file_rejects_traversal() -> None:
    assert instant._safe_static_file("/static/../../_cc_instant.py") is None
    assert instant._safe_static_file("/static/foo/../../../etc/passwd") is None
