"""Tests for IBKR connectivity diagnosis."""

import unittest
from unittest.mock import patch

from src.services.ibkr_diagnosis import (
    DIAG_GATEWAY_UP_CONNECT,
    DIAG_HANDOFF_READY,
    DIAG_MODE_PORT_MISMATCH,
    DIAG_WRONG_HOST_DOCKER,
    build_ibkr_diagnosis,
    clear_probe_cache,
)


class TestIBKRDiagnosis(unittest.TestCase):
    def setUp(self):
        clear_probe_cache()

    @patch("src.services.ibkr_diagnosis.probe_tcp_port")
    def test_gateway_up_need_connect(self, mock_probe):
        mock_probe.return_value = True
        d = build_ibkr_diagnosis(
            mode="paper",
            host="127.0.0.1",
            port=7497,
            socket_connected=False,
            session_usable=False,
        )
        self.assertEqual(d["code"], DIAG_GATEWAY_UP_CONNECT)
        self.assertEqual(d["short"], "LOGIN")
        self.assertTrue(d["gateway_reachable"])
        self.assertTrue(d["api_port_open"])

    @patch("src.services.ibkr_diagnosis.probe_tcp_port")
    def test_port_unreachable(self, mock_probe):
        mock_probe.return_value = False
        d = build_ibkr_diagnosis(
            mode="paper",
            host="127.0.0.1",
            port=7497,
        )
        self.assertEqual(d["short"], "OFFLINE")
        self.assertFalse(d["gateway_reachable"])

    @patch("src.services.ibkr_diagnosis.probe_tcp_port")
    def test_wrong_host_docker(self, mock_probe):
        def _probe(host, port, **_kw):
            return host == "host.docker.internal" and port == 7497

        mock_probe.side_effect = _probe
        d = build_ibkr_diagnosis(
            mode="paper",
            host="127.0.0.1",
            port=7497,
            docker=True,
        )
        self.assertEqual(d["code"], DIAG_WRONG_HOST_DOCKER)

    @patch("src.services.ibkr_diagnosis.probe_tcp_port")
    def test_mode_port_mismatch(self, mock_probe):
        def _probe(host, port, **_kw):
            return port == 4001

        mock_probe.side_effect = _probe
        d = build_ibkr_diagnosis(
            mode="paper",
            host="127.0.0.1",
            port=7497,
            paper_port=7497,
            live_ports=[4001, 7496],
        )
        self.assertEqual(d["code"], DIAG_MODE_PORT_MISMATCH)
        self.assertIn("7497", d.get("mode_mismatch") or "")

    def test_handoff_ready(self):
        d = build_ibkr_diagnosis(
            trade_handoff_ready=True,
            session_usable=True,
            ibapi_available=True,
        )
        self.assertEqual(d["code"], DIAG_HANDOFF_READY)
        self.assertEqual(d["short"], "READY")

    def test_unified_labels_use_diagnosis(self):
        from src.services.ibkr_health import build_unified_labels

        labels = build_unified_labels(
            {},
            diagnosis={
                "short": "LOGIN",
                "label": "Gateway port open — API session not started",
            },
            gateway_reachable=True,
        )
        self.assertEqual(labels["unified_short"], "LOGIN")
        self.assertEqual(labels["level"], "partial")


if __name__ == "__main__":
    unittest.main()
