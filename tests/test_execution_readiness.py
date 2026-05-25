"""Unit tests for execution_readiness service."""

import unittest

from src.services.execution_readiness import build_execution_readiness


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
