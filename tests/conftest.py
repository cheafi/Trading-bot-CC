"""Suite-wide test isolation: no live network unless explicitly allowed.

Live providers (Yahoo via yfinance/curl_cffi, FRED, EDGAR, brokers) make the
suite slow, flaky and order-dependent, and throttled Yahoo can block a test
indefinitely. By default every outbound connection fails fast, so code under
test exercises its degraded / fail-closed path deterministically.

Opt in with ``CC_TEST_NETWORK=1``; tests that only make sense against a live
provider should be marked ``@pytest.mark.network`` and are skipped otherwise.
"""

from __future__ import annotations

import ipaddress
import os
import socket

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


def pytest_collection_modifyitems(config, items):
    if NETWORK_ALLOWED:
        return
    skip = pytest.mark.skip(reason="live network test; set CC_TEST_NETWORK=1")
    for item in items:
        if "network" in item.keywords:
            item.add_marker(skip)
