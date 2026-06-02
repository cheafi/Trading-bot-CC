"""Unit tests for IBKR health state model."""

import unittest

from src.services.ibkr_health import IBKRHealthTracker, build_unified_labels
from src.services.ibkr_service import IBKRHealthState


class TestIBKRHealthState(unittest.TestCase):
    def test_1100_session_lost(self):
        h = IBKRHealthState()
        h.apply_ib_code(1100, "Connectivity lost")
        self.assertEqual(h.session_status, "lost")
        self.assertIsNotNone(h.last_disconnect_at)

    def test_1102_session_restored(self):
        h = IBKRHealthState()
        h.apply_ib_code(1100)
        h.apply_ib_code(1102, "Data maintained")
        self.assertEqual(h.session_status, "restored_data_maintained")
        self.assertIsNotNone(h.last_restore_at)

    def test_2107_hmds_dormant_not_fatal(self):
        h = IBKRHealthState()
        h.apply_ib_code(2107, "HMDS data farm connection is OK")
        self.assertEqual(h.hmds_status, "dormant")
        h.refresh_derived(
            socket_connected=True,
            authenticated=True,
            account_loaded=True,
            bracket_ready=False,
        )
        self.assertEqual(h.handoff_status, "monitoring_only")
        self.assertIn("dormant", " ".join(h.degraded_reasons).lower())

    def test_account_ok_while_market_data_degraded(self):
        h = IBKRHealthState()
        h.apply_ib_code(2103)
        h.note_account_ok()
        h.refresh_derived(
            socket_connected=True,
            authenticated=True,
            account_loaded=True,
        )
        self.assertTrue(h.session_usable())
        self.assertEqual(h.account_status, "ok")
        self.assertEqual(h.market_data_status, "degraded")
        self.assertEqual(h.handoff_status, "monitoring_only")

    def test_recent_incidents_on_farm_degrade(self):
        h = IBKRHealthState()
        h.apply_ib_code(2157, "Sec-def broken")
        self.assertTrue(h._recent_incidents)
        self.assertEqual(h._recent_incidents[0]["kind"], "secdef_degraded")


class TestIBKRHealthTracker(unittest.TestCase):
    def test_unified_label_partial_when_account_ok(self):
        health = IBKRHealthTracker()
        health.ingest_code(2103)
        health.on_account_loaded()
        health.finalize(
            socket_connected=True,
            account_loaded=True,
            next_order_id=42,
        )
        labels = build_unified_labels(
            health.to_dict(),
            ibkr_mode="paper",
            gateway_reachable=True,
        )
        self.assertEqual(labels["level"], "partial")
        self.assertNotEqual(labels["unified_short"], "OFFLINE")


if __name__ == "__main__":
    unittest.main()
