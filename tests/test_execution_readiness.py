"""Unit tests for execution_readiness service."""

import unittest
from unittest.mock import MagicMock, patch

from src.services.execution_readiness import build_execution_readiness
from src.services.ibkr_health import build_unified_labels


class TestExecutionReadiness(unittest.TestCase):
    def test_offline_label(self):
        r = build_execution_readiness(
            ibkr_connected=False,
            gateway_reachable=False,
        )
        self.assertEqual(r["level"], "offline")
        self.assertIn("offline", r["readiness_label"].lower())

    def test_ready_when_handoff(self):
        r = build_execution_readiness(
            ibkr_connected=True,
            ibkr_mode="paper",
            bracket_ready=True,
            gateway_reachable=True,
            engine_running=True,
        )
        self.assertIn(r["level"], ("ready", "partial"))

    def test_unified_labels_monitoring_not_offline(self):
        health = {
            "session_operational": True,
            "session_usable": True,
            "account_status": "ok",
            "handoff_status": "monitoring_only",
            "summary_label": "Session restored, Account API OK, Market data degraded, Monitoring only",
            "degraded_reasons": ["Market data farm degraded (2103)"],
        }
        labels = build_unified_labels(
            health,
            ibkr_mode="paper",
            gateway_reachable=True,
        )
        self.assertEqual(labels["level"], "partial")
        self.assertNotIn("OFFLINE", labels["unified_label"])

    @patch("src.services.ibkr_service.get_ibkr_service")
    def test_health_fields_exposed(self, mock_get_svc):
        svc = MagicMock()
        svc.status.return_value = {
            "connected": True,
            "session_usable": True,
            "socket_connected": True,
            "mode": "paper",
            "host": "127.0.0.1",
            "port": 7497,
            "next_order_id": 1,
            "monitoring_only": True,
        }
        svc.build_health_state.return_value = {
            "session_usable": True,
            "session_operational": True,
            "account_status": "ok",
            "market_data_status": "degraded",
            "handoff_status": "monitoring_only",
            "summary_label": "Account API OK, Market data degraded, Monitoring only",
            "degraded_reasons": ["Market data farm degraded (2103)"],
            "last_disconnect_at": "2026-05-29T14:00:00Z",
            "last_restore_at": "2026-05-29T14:01:00Z",
        }
        svc._last_heartbeat_ts = None
        svc._last_order_ok = None
        svc._last_order_fail = None
        svc.get_transport_snapshot.return_value = {"gateway_reachable": True}
        mock_get_svc.return_value = svc

        r = build_execution_readiness(gateway_reachable=True)
        self.assertTrue(r["session_usable"])
        self.assertEqual(r["health"]["account_status"], "ok")
        self.assertEqual(r["last_restore_at"], "2026-05-29T14:01:00Z")
        self.assertEqual(r["level"], "partial")
        self.assertNotEqual(r["unified_short"], "OFFLINE")


if __name__ == "__main__":
    unittest.main()
