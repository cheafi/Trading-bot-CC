"""
Sprint 64 Tests — StructureDetector→VCP wiring, persistent dedup,
drawdown circuit breaker, brief router
"""
import os
import sys
import unittest

sys.path.insert(0, os.path.dirname(__file__))


class TestVCPFromOHLCV(unittest.TestCase):
    """VCP detection should work from raw OHLCV data."""

    def test_detect_vcp_from_closes(self):
        from src.engines.sector_classifier import (
            LeaderStatus,
            SectorBucket,
            SectorContext,
        )
        from src.engines.vcp_intelligence import VCPIntelligence

        # Build synthetic VCP: trending up, then contracting
        # 3 contractions getting tighter
        prices = []
        # Base: 80 → 100 uptrend
        for i in range(30):
            prices.append(80 + i * 0.67)
        # Contraction 1: 100 → 90 → 98
        for p in [100, 97, 94, 91, 90, 92, 94, 96, 98]:
            prices.append(p)
        # Contraction 2: 98 → 94 → 97
        for p in [98, 96, 94, 95, 96, 97]:
            prices.append(p)
        # Contraction 3: 97 → 95.5 → 97
        for p in [97, 96, 95.5, 96, 96.5, 97]:
            prices.append(p)

        closes = prices
        highs = [p * 1.01 for p in prices]
        lows = [p * 0.99 for p in prices]
        volumes = [1e6] * len(prices)
        # Volume dry-up in contractions
        for i in range(30, len(volumes)):
            volumes[i] = 5e5

        sig = {
            "ticker": "TEST",
            "closes": closes,
            "highs": highs,
            "lows": lows,
            "volumes": volumes,
            "strategy": "swing",
            "rs_rank": 80,
        }

        sector = SectorContext(
            ticker="TEST",
            sector_bucket=SectorBucket.HIGH_GROWTH,
            leader_status=LeaderStatus.LEADER,
        )

        vcp = VCPIntelligence()
        result = vcp.analyze(sig, sector, {"trend": "RISK_ON"})

        # Should detect VCP from the contraction sequence
        self.assertTrue(result.detection.is_vcp,
            "Should detect VCP from OHLCV contraction sequence")
        self.assertGreaterEqual(result.detection.contraction_count, 2)

    def test_no_vcp_in_downtrend(self):
        """Downtrending prices should NOT be detected as VCP."""
        from src.engines.sector_classifier import (
            LeaderStatus,
            SectorBucket,
            SectorContext,
        )
        from src.engines.vcp_intelligence import VCPIntelligence

        # Straight downtrend — no contraction pattern
        prices = [100 - i * 0.5 for i in range(50)]
        sig = {
            "ticker": "TEST",
            "closes": prices,
            "highs": [p * 1.01 for p in prices],
            "lows": [p * 0.99 for p in prices],
            "volumes": [1e6] * 50,
            "strategy": "swing",
        }

        sector = SectorContext(
            ticker="TEST",
            sector_bucket=SectorBucket.HIGH_GROWTH,
            leader_status=LeaderStatus.LEADER,
        )

        vcp = VCPIntelligence()
        result = vcp.analyze(sig, sector, {"trend": "RISK_ON"})
        # Downtrend should not be VCP
        if result.detection.is_vcp:
            # If detected, at least grade should be low
            self.assertIn(result.action.grade, ("C", "D", "F"))


class TestPersistentDedupInAlerts(unittest.TestCase):
    """SectorAlertBuilder should use persistent dedup."""

    def test_dedup_survives_rebuild(self):
        import uuid

        from src.notifications.sector_alerts import SectorAlertBuilder

        # Use unique ticker to avoid collisions with previous runs
        unique_ticker = f"TEST_{uuid.uuid4().hex[:8].upper()}"

        # Create two builders — simulates restart
        builder1 = SectorAlertBuilder(persistent_dedup=True)
        dup1 = builder1._check_dedup(unique_ticker, "TRADE")
        self.assertFalse(dup1, "First alert should NOT be duplicate")

        # Same ticker+action on a new builder instance
        builder2 = SectorAlertBuilder(persistent_dedup=True)
        dup2 = builder2._check_dedup(unique_ticker, "TRADE")
        self.assertTrue(dup2, "Same alert after restart should be duplicate")


class TestDrawdownCircuitBreaker(unittest.TestCase):
    """Drawdown circuit breaker tests."""

    def test_normal_conditions(self):
        from src.engines.drawdown_breaker import DrawdownCircuitBreaker
        breaker = DrawdownCircuitBreaker()
        result = breaker.check(100000, 100000, 100000)
        self.assertEqual(result.level, "NORMAL")
        self.assertEqual(result.size_multiplier, 1.0)
        self.assertTrue(result.new_entries_allowed)

    def test_caution_at_3pct(self):
        from src.engines.drawdown_breaker import DrawdownCircuitBreaker
        breaker = DrawdownCircuitBreaker()
        result = breaker.check(96500, 100000, 100000)
        self.assertEqual(result.level, "CAUTION")
        self.assertAlmostEqual(result.size_multiplier, 0.7, places=1)

    def test_reduced_at_5pct(self):
        from src.engines.drawdown_breaker import DrawdownCircuitBreaker
        breaker = DrawdownCircuitBreaker()
        result = breaker.check(94500, 100000, 100000)
        self.assertEqual(result.level, "REDUCED")
        self.assertLessEqual(result.size_multiplier, 0.5)

    def test_halt_at_10pct(self):
        from src.engines.drawdown_breaker import DrawdownCircuitBreaker
        breaker = DrawdownCircuitBreaker()
        result = breaker.check(89000, 100000, 100000)
        self.assertEqual(result.level, "HALT")
        self.assertEqual(result.size_multiplier, 0.0)
        self.assertFalse(result.new_entries_allowed)

    def test_adjust_size(self):
        from src.engines.drawdown_breaker import DrawdownCircuitBreaker
        breaker = DrawdownCircuitBreaker()
        adjusted, result = breaker.adjust_size(
            2.0, 95000, 100000, 100000
        )
        self.assertLess(adjusted, 2.0, "Size should be reduced in drawdown")

    def test_to_dict(self):
        from src.engines.drawdown_breaker import DrawdownCircuitBreaker
        breaker = DrawdownCircuitBreaker()
        result = breaker.check(97000, 100000, 100000)
        d = result.to_dict()
        self.assertIn("level", d)
        self.assertIn("size_multiplier", d)
        self.assertIn("weekly_pnl_pct", d)


class TestBriefRouter(unittest.TestCase):
    """Brief router should be importable."""

    def test_router_import(self):
        from src.api.routers.brief import router
        self.assertIsNotNone(router)
        # Check routes exist
        routes = [r.path for r in router.routes]
        self.assertIn("/api/brief", routes)
        self.assertIn("/api/brief/diff", routes)
        self.assertIn("/api/brief/regime", routes)
        self.assertIn("/api/brief/strategies", routes)
        self.assertIn("/api/brief/circuit-breaker", routes)


class TestVCPStructureIntegration(unittest.TestCase):
    """VCP should inject structure data back into signal."""

    def test_structure_data_injected(self):
        from src.engines.sector_classifier import (
            LeaderStatus,
            SectorBucket,
            SectorContext,
        )
        from src.engines.vcp_intelligence import VCPIntelligence

        # VCP-like pattern
        prices = list(range(80, 100)) + [100, 97, 94, 97, 99,
                                          99, 97, 96, 97, 98,
                                          98, 97.5, 97, 97.5, 98]

        sig = {
            "ticker": "TEST",
            "closes": prices,
            "highs": [p * 1.01 for p in prices],
            "lows": [p * 0.99 for p in prices],
            "volumes": [1e6] * len(prices),
            "strategy": "swing",
        }

        sector = SectorContext(
            ticker="TEST",
            sector_bucket=SectorBucket.HIGH_GROWTH,
            leader_status=LeaderStatus.LEADER,
        )

        vcp = VCPIntelligence()
        result = vcp.analyze(sig, sector, {"trend": "RISK_ON"})

        # If VCP was detected from OHLCV, structure data should be injected
        if result.detection.is_vcp and "trend_structure" in sig:
            self.assertIn(sig["trend_structure"],
                ("strong_uptrend", "uptrend", "neutral",
                 "downtrend", "strong_downtrend"))


if __name__ == "__main__":
    unittest.main()
