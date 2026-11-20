"""Suite-wide test isolation: no live network unless explicitly allowed.

Live providers (Yahoo via yfinance/curl_cffi, FRED, EDGAR, brokers) make the
suite slow, flaky and order-dependent, and throttled Yahoo can block a test
indefinitely. By default every outbound connection fails fast, so code under
test exercises its degraded / fail-closed path deterministically.

Opt in with ``CC_TEST_NETWORK=1``; tests that only make sense against a live
provider should be marked ``@pytest.mark.network`` and are skipped otherwise.
"""

from __future__ import annotations

import importlib
import ipaddress
import os
import shutil
import socket
from pathlib import Path

import pytest

NETWORK_ALLOWED = os.environ.get("CC_TEST_NETWORK") == "1"

# libcurl (curl_cffi → yfinance), requests and httpx honour proxy variables;
# port 9 (discard) on loopback refuses immediately.
_DEAD_PROXY = "http://127.0.0.1:9"
_PROXY_VARS = (
    "HTTPS_PROXY",
    "HTTP_PROXY",
    "ALL_PROXY",
    "https_proxy",
    "http_proxy",
    "all_proxy",
)
_NO_PROXY = "localhost,127.0.0.1,::1,testserver"

_real_connect = socket.socket.connect
_real_connect_ex = socket.socket.connect_ex


def _is_local(address) -> bool:
    if not isinstance(address, tuple) or not address:
        return True  # AF_UNIX paths and other non-IP families
    host = str(address[0])
    if host in ("localhost", "testserver"):
        return True
    try:
        return ipaddress.ip_address(host.split("%")[0]).is_loopback
    except ValueError:
        return False


def _guarded_connect(self, address):
    if not _is_local(address):
        raise ConnectionRefusedError(f"network disabled in tests: {address!r}")
    return _real_connect(self, address)


def _guarded_connect_ex(self, address):
    if not _is_local(address):
        return 111  # ECONNREFUSED
    return _real_connect_ex(self, address)


def pytest_configure(config):
    if NETWORK_ALLOWED:
        return
    for var in _PROXY_VARS:
        os.environ[var] = _DEAD_PROXY
    os.environ["NO_PROXY"] = os.environ["no_proxy"] = _NO_PROXY
    socket.socket.connect = _guarded_connect
    socket.socket.connect_ex = _guarded_connect_ex
    # Offline, a retry can never succeed; back-off sleeps across a ~480-ticker
    # scan otherwise stall a single request for minutes.
    import src.services.market_data as market_data

    market_data.MAX_RETRIES = 1


def pytest_unconfigure(config):
    socket.socket.connect = _real_connect
    socket.socket.connect_ex = _real_connect_ex


# Tracked research data the suite must never rewrite: (module, attribute, file).
_TRACKED_DATA_WRITERS = (
    ("src.engines.learning_loop", "_TRADES_FILE", "closed_trades.jsonl"),
    ("src.api.routers.ledger", "LEDGER_PATH", "closed_trades.jsonl"),
    ("src.api.routers.position_alerts", "ALERTS_LOG", "alerts.jsonl"),
    ("src.engines.decision_tracker", "_DB_PATH", "decision_tracker.db"),
)
_REPO_DATA = Path(__file__).resolve().parents[1] / "data"


@pytest.fixture(scope="session")
def _tracked_data_copy(tmp_path_factory):
    root = tmp_path_factory.mktemp("tracked_data")
    for name in {f for _, _, f in _TRACKED_DATA_WRITERS}:
        src = _REPO_DATA / name
        if src.exists():
            shutil.copy2(src, root / name)
    return root


@pytest.fixture(autouse=True)
def _isolate_tracked_data(_tracked_data_copy, monkeypatch):
    """Point writers of tracked data/ files at a session copy, so tests still
    read the real rows but never append to or rewrite the user's files."""
    for module, attr, name in _TRACKED_DATA_WRITERS:
        try:
            mod = importlib.import_module(module)
        except Exception:
            continue
        current = getattr(mod, attr, None)
        if current is None:
            continue
        target = _tracked_data_copy / name
        monkeypatch.setattr(mod, attr, target if isinstance(current, Path) else str(target))


def pytest_collection_modifyitems(config, items):
    if NETWORK_ALLOWED:
        return
    skip = pytest.mark.skip(reason="live network test; set CC_TEST_NETWORK=1")
    for item in items:
        if "network" in item.keywords:
            item.add_marker(skip)
