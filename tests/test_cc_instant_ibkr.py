"""Instant-server IBKR degraded handlers — status/connect during API warm-up."""

from __future__ import annotations

import json
from pathlib import Path
from unittest.mock import patch

import pytest

ROOT = Path(__file__).resolve().parents[1]
CC_INSTANT = ROOT / "_cc_instant.py"


def _load_instant_ibkr_helpers():
    """Import _cc_instant IBKR helpers without starting the HTTP server."""
    source = CC_INSTANT.read_text(encoding="utf-8")
    block = source.split("def _parse_ibkr_json_body(body: bytes)")[1].split(
        "def _degraded_portfolio_monitor_bytes"
    )[0]
    ns: dict = {}
    exec(  # noqa: S102
        "import json\nfrom pathlib import Path\nimport urllib.parse\n"
        + "def _encode_degraded(p, reason=None):\n"
        + "  out=dict(p); out.setdefault('degraded', True); return json.dumps(out).encode()\n"
        + "def _parse_ibkr_json_body(body: bytes)"
        + block,
        ns,
    )
    return ns


@pytest.fixture
def ibkr_instant():
    return _load_instant_ibkr_helpers()


@patch("src.services.ibkr_diagnosis.probe_tcp_port", return_value=True)
def test_degraded_ibkr_status_includes_login_diagnosis(mock_probe, ibkr_instant):
    body = ibkr_instant["_degraded_ibkr_status_bytes"]("/api/ibkr/status")
    payload = json.loads(body)
    assert payload["connected"] is False
    assert payload["api_port_open"] is True
    assert payload["diagnosis"]["short"] == "LOGIN"
    assert payload["backend_warming"] is True
    mock_probe.assert_called()


@patch("src.services.ibkr_diagnosis.probe_tcp_port", return_value=False)
def test_degraded_ibkr_connect_blocked_while_warming(mock_probe, ibkr_instant):
    status, body = ibkr_instant["_degraded_ibkr_connect_post"](
        json.dumps({"mode": "paper", "host": "127.0.0.1"}).encode()
    )
    payload = json.loads(body)
    assert status == 503
    assert payload["ok"] is False
    assert "mode=full" in payload["detail"]
    assert payload["diagnosis"]["short"] == "OFFLINE"
    mock_probe.assert_called()


def test_cc_instant_wires_ibkr_degraded_paths():
    raw = CC_INSTANT.read_text(encoding="utf-8")
    assert 'path_only == "/api/ibkr/status"' in raw
    assert 'path_only == "/api/ibkr/connect"' in raw
    assert 'path_only == "/api/ibkr/ping"' in raw
    assert "/api/ibkr/" in raw and "startswith" in raw


def test_cc_helpers_ibkr_warmup_copy():
    raw = (ROOT / "src/api/static/cc-helpers.js").read_text(encoding="utf-8")
    assert "ibkr_execution:" in raw
    assert "mode=full" in raw
