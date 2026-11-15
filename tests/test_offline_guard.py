"""The suite runs offline unless CC_TEST_NETWORK=1."""

from __future__ import annotations

import os
import socket

import pytest

from tests.conftest import NETWORK_ALLOWED, _is_local

pytestmark = pytest.mark.skipif(NETWORK_ALLOWED, reason="network explicitly allowed")


def test_external_connect_refused_fast():
    s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    try:
        with pytest.raises(ConnectionRefusedError):
            s.connect(("203.0.113.10", 443))
        assert s.connect_ex(("203.0.113.10", 443)) == 111
    finally:
        s.close()


def test_proxy_env_points_at_dead_loopback():
    assert os.environ["HTTPS_PROXY"] == "http://127.0.0.1:9"
    assert "127.0.0.1" in os.environ["NO_PROXY"]


@pytest.mark.parametrize(
    "addr,local",
    [
        (("127.0.0.1", 80), True),
        (("::1", 80, 0, 0), True),
        (("localhost", 80), True),
        (("8.8.8.8", 53), False),
        (("query1.finance.yahoo.com", 443), False),
        ("/tmp/sock", True),
    ],
)
def test_is_local(addr, local):
    assert _is_local(addr) is local


def test_market_data_does_not_back_off_offline():
    import src.services.market_data as market_data

    assert market_data.MAX_RETRIES == 1


def test_loopback_still_allowed():
    srv = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    srv.bind(("127.0.0.1", 0))
    srv.listen(1)
    cli = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    try:
        cli.connect(srv.getsockname())
    finally:
        cli.close()
        srv.close()
