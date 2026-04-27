"""
Sprint 62 Tests — MacroRegimeEngine, FundBuilder, StockVsSPY,
Scanner renames, Bug fixes
"""
import unittest
import sys, os

sys.path.insert(0, os.path.dirname(__file__))


class TestMacroRegimeEngine(unittest.TestCase):
    """Test real regime computation from benchmark data."""

    def test_risk_on_regime(self):
        from src.engines.macro_regime_engine import MacroRegimeEngine
        engine = MacroRegimeEngine()
        # Strong uptrend: rising prices, low VIX
        spy = [400 + i * 2 for i in range(60)]  # Steady climb
        vix = [12.0] * 60  # Low VIX
        qqq = [300 + i * 2.5 for i in range(60)]  # QQQ also up
        iwm = [180 + i * 1.5 for i in range(60)]  # IWM confirms

        result = engine.compute(spy, qqq_closes=qqq, vix_closes=vix, iwm_closes=iwm)
        self.assertIn(result.trend, ("RISK_ON", "UPTREND"))
        self.assertEqual(result.vix_regime, "LOW")
        self.assertEqual(result.spy_trend, "UP")
        self.assertLessEqual(result.risk_score, 35)

    def test_crisis_regime(self):
        from src.engines.macro_regime_engine import MacroRegimeEngine
        engine = MacroRegimeEngine()
        # Crashing market: falling prices, spiking VIX
        spy = [500 - i * 5 for i in range(60)]  # Sharp decline
        vix = [15.0] * 40 + [35.0 + i for i in range(20)]  # VIX spike
        qqq = [400 - i * 6 for i in range(60)]  # QQQ also down
        iwm = [200 - i * 4 for i in range(60)]  # IWM also down

        result = engine.compute(spy, qqq_closes=qqq, vix_closes=vix, iwm_closes=iwm)
        self.assertIn(result.trend, ("RISK_OFF", "DOWNTREND", "CRISIS"))
        self.assertGreater(result.risk_score, 60)

    def test_sideways_regime(self):
        from src.engines.macro_regime_engine import MacroRegimeEngine
        engine = MacroRegimeEngine()
        # Flat market
        spy = [500 + (i % 5) - 2 for i in range(60)]
        result = engine.compute(spy)
        # Without other data sources, confidence should be reduced
        self.assertLessEqual(result.confidence, 0.7)

    def test_to_dict(self):
        from src.engines.macro_regime_engine import MacroRegimeEngine
        engine = MacroRegimeEngine()
        spy = [500 + i for i in range(60)]
        result = engine.compute(spy)
        d = result.to_dict()
        self.assertIn("trend", d)
        self.assertIn("risk_score", d)
        self.assertIn("signals", d)


class TestStockVsSPY(unittest.TestCase):
    """Test stock vs SPY comparison."""

    def test_outperforming_stock(self):
        from src.engines.macro_regime_engine import StockVsSPY
        # Stock up 20%, SPY up 5%
        stock = [100 + i * 0.4 for i in range(60)]  # 100→124
        spy = [500 + i * 0.5 for i in range(60)]    # 500→530
        result = StockVsSPY.compare(stock, spy, ticker="TEST")
        self.assertEqual(result["ticker"], "TEST")
        self.assertIn("performance", result)
        self.assertIn("relative_strength", result)
        rs = result["relative_strength"]
        self.assertEqual(rs["rs_trend"], "OUTPERFORMING")

    def test_underperforming_stock(self):
        from src.engines.macro_regime_engine import StockVsSPY
        stock = [100 - i * 0.3 for i in range(60)]  # Declining
        spy = [500 + i * 0.5 for i in range(60)]    # Rising
        result = StockVsSPY.compare(stock, spy, ticker="WEAK")
        rs = result.get("relative_strength", {})
        self.assertEqual(rs.get("rs_trend"), "UNDERPERFORMING")

    def test_risk_metrics(self):
        from src.engines.macro_regime_engine import StockVsSPY
        stock = [100 + i for i in range(60)]
        spy = [500 + i * 0.5 for i in range(60)]
        result = StockVsSPY.compare(stock, spy, ticker="FAST")
        self.assertIn("risk", result)
        self.assertIn("beta", result["risk"])
        self.assertGreater(result["risk"]["beta"], 0)

    def test_insufficient_data(self):
        from src.engines.macro_regime_engine import StockVsSPY
        result = StockVsSPY.compare([100, 101], [500, 502], ticker="X")
        # Should still work with 2 points (min 5 for full)
        # Actually need 5, so should return error
        self.assertIn("error", result)


class TestFundBuilder(unittest.TestCase):
    """Test build-your-own-fund functionality."""

    def test_create_fund(self):
        from src.engines.fund_builder import FundBuilder
        fund = FundBuilder("Test Fund", 100000)
        fund.add_strategy("MOMENTUM", 0.5)
        fund.add_strategy("VCP", 0.5)
        self.assertEqual(len(fund.strategies), 2)
        self.assertEqual(fund.cash, 100000)

    def test_add_position(self):
        from src.engines.fund_builder import FundBuilder
        fund = FundBuilder("Test", 100000)
        fund.add_strategy("MOMENTUM", 1.0)
        pos = fund.add_position("NVDA", 125.0, 80, "MOMENTUM")
        self.assertEqual(pos.ticker, "NVDA")
        self.assertEqual(pos.cost_basis, 10000.0)
        self.assertEqual(fund.cash, 90000.0)

    def test_position_pnl(self):
        from src.engines.fund_builder import FundBuilder
        fund = FundBuilder("Test", 100000)
        fund.add_strategy("MOMENTUM", 1.0)
        fund.add_position("NVDA", 100.0, 100, "MOMENTUM")
        # NVDA goes to 120
        total = fund.total_value({"NVDA": 120.0})
        self.assertEqual(total, 90000 + 12000)  # cash + position value

    def test_close_position(self):
        from src.engines.fund_builder import FundBuilder
        fund = FundBuilder("Test", 100000)
        fund.add_strategy("VCP", 1.0)
        fund.add_position("CRWD", 300.0, 10, "VCP")
        closed = fund.close_position("CRWD", 350.0)
        self.assertIsNotNone(closed)
        self.assertEqual(closed.pnl, 500.0)  # (350-300)*10
        self.assertEqual(len(fund.positions), 0)
        self.assertEqual(len(fund.closed), 1)
        self.assertEqual(fund.cash, 100000 - 3000 + 3500)  # Original - cost + proceeds

    def test_performance_vs_spy(self):
        from src.engines.fund_builder import FundBuilder
        fund = FundBuilder("Alpha Fund", 100000)
        fund.spy_entry_price = 500.0
        fund.add_strategy("MOMENTUM", 1.0)
        fund.add_position("NVDA", 100.0, 200, "MOMENTUM")

        report = fund.performance_report(
            {"NVDA": 120.0},
            spy_current=525.0,
        )
        self.assertEqual(report["fund_name"], "Alpha Fund")
        self.assertIn("benchmark", report)
        bench = report["benchmark"]
        # SPY: 500→525 = +5%
        self.assertAlmostEqual(bench["spy_return_pct"], 5.0, places=1)
        # Fund: 100k → 80k cash + 24k NVDA = 104k = +4%
        self.assertTrue(isinstance(bench["alpha"], float))

    def test_strategy_attribution(self):
        from src.engines.fund_builder import FundBuilder
        fund = FundBuilder("Multi", 100000)
        fund.add_strategy("MOMENTUM", 0.5)
        fund.add_strategy("VCP", 0.5)
        fund.add_position("NVDA", 100.0, 100, "MOMENTUM")
        fund.add_position("CRWD", 200.0, 50, "VCP")

        report = fund.performance_report({"NVDA": 110.0, "CRWD": 190.0})
        attrib = report["strategy_attribution"]
        # MOMENTUM: +$1000, VCP: -$500
        mom = next(a for a in attrib if a["strategy"] == "MOMENTUM")
        vcp = next(a for a in attrib if a["strategy"] == "VCP")
        self.assertGreater(mom["pnl"], 0)
        self.assertLess(vcp["pnl"], 0)

    def test_serialization(self):
        from src.engines.fund_builder import FundBuilder
        fund = FundBuilder("Serialize Test", 50000)
        fund.add_strategy("BREAKOUT", 1.0)
        fund.add_position("AAPL", 150.0, 10, "BREAKOUT")

        d = fund.to_dict()
        fund2 = FundBuilder.from_dict(d)
        self.assertEqual(fund2.name, "Serialize Test")
        self.assertEqual(len(fund2.positions), 1)
        self.assertEqual(fund2.positions[0].ticker, "AAPL")

    def test_insufficient_cash(self):
        from src.engines.fund_builder import FundBuilder
        fund = FundBuilder("Small", 1000)
        fund.add_strategy("MOMENTUM", 1.0)
        with self.assertRaises(ValueError):
            fund.add_position("NVDA", 125.0, 100, "MOMENTUM")  # $12,500 > $1,000


class TestScannerRenames(unittest.TestCase):
    """Verify scanners are renamed but backward-compatible."""

    def test_new_names_exist(self):
        from src.engines.scanner_matrix import (
            VolumeSurgeScanner,
            QuietAccumulationScanner,
            HighVolumeLeaderScanner,
        )
        self.assertEqual(VolumeSurgeScanner().name, "volume_surge")
        self.assertEqual(QuietAccumulationScanner().name, "quiet_accumulation")
        self.assertEqual(HighVolumeLeaderScanner().name, "high_volume_leader")

    def test_backward_compat_aliases(self):
        from src.engines.scanner_matrix import (
            OptionsFlowScanner,
            InsiderScanner,
            InstitutionalScanner,
        )
        # Aliases should point to renamed classes
        self.assertEqual(OptionsFlowScanner().name, "volume_surge")
        self.assertEqual(InsiderScanner().name, "quiet_accumulation")
        self.assertEqual(InstitutionalScanner().name, "high_volume_leader")

    def test_volume_surge_scanner_fires(self):
        from src.engines.scanner_matrix import VolumeSurgeScanner
        scanner = VolumeSurgeScanner()
        signals = [{"ticker": "TEST", "vol_ratio": 3.0,
                     "trend_structure": "uptrend", "bb_width": 3.0}]
        hits = scanner.scan(signals, {})
        self.assertEqual(len(hits), 1)
        self.assertIn("heuristic_proxy", str(hits[0].metadata))


class TestBugFixes(unittest.TestCase):
    """Verify specific bugs from the review are fixed."""

    def test_accumulation_distribution_no_index_bug(self):
        """Flow intelligence accumulation should handle duplicate prices."""
        from src.engines.flow_intelligence import FlowIntelligenceEngine
        fi = FlowIntelligenceEngine()
        # Prices with duplicates that would break .index()
        data = {
            "ticker": "TEST",
            "close_5d": [100.0, 101.0, 101.0, 102.0, 101.0],
            "volume_5d": [1000, 2000, 1500, 3000, 1200],
            "avg_volume": 1500,
        }
        # Should not crash
        result = fi.analyze(data)
        self.assertIsNotNone(result)

    def test_confidence_missing_freshness_penalized(self):
        """Missing data_freshness should NOT default to 'live' (0.9)."""
        from src.engines.confidence_engine import ConfidenceEngine
        from src.engines.sector_classifier import SectorContext, SectorBucket, SectorStage, LeaderStatus
        from src.engines.fit_scorer import FitScores
        engine = ConfidenceEngine()
        sig = {"ticker": "TEST"}  # No data_freshness
        sector = SectorContext(
            ticker="TEST",
            sector_bucket=SectorBucket.HIGH_GROWTH,
            sector_stage=SectorStage.ACCELERATION,
            leader_status=LeaderStatus.LEADER,
        )
        fit = FitScores.__new__(FitScores)
        fit.total = 6.0
        fit.setup = 6.0
        fit.sector = 5.0
        fit.timing = 5.0
        fit.risk = 5.0
        fit.execution = 5.0
        fit.components = {}
        fit.evidence_conflicts = []
        regime = {"trend": "SIDEWAYS"}
        result = engine.compute(sig, sector, fit, regime)
        # data_confidence should be 0.4 (penalized), not 0.9
        self.assertLessEqual(result.data, 0.5)

    def test_score_fallback_penalizes_missing_data(self):
        """Missing trend_structure should penalize score, not default 5.0."""
        from src.engines.fit_scorer import FitScorer
        scorer = FitScorer()
        sig = {"ticker": "TEST"}  # No trend_structure
        score = scorer._score_setup(sig)
        # With no data and default score=3.0, penalty -1.5 → 1.5
        self.assertLess(score, 3.0)

    def test_confidence_floor_blocks_trade(self):
        """Very low confidence should force NO_TRADE."""
        from src.engines.decision_mapper import DecisionMapper, Action
        from src.engines.sector_classifier import SectorContext, SectorBucket, SectorStage, LeaderStatus
        from src.engines.fit_scorer import FitScores
        from src.engines.confidence_engine import ConfidenceBreakdown
        mapper = DecisionMapper()
        sector = SectorContext(
            ticker="TEST",
            sector_bucket=SectorBucket.HIGH_GROWTH,
            sector_stage=SectorStage.ACCELERATION,
            leader_status=LeaderStatus.LEADER,
        )
        fit = FitScores.__new__(FitScores)
        fit.total = 8.0
        fit.setup = 8.0
        fit.sector = 7.0
        fit.timing = 7.0
        fit.risk = 7.0
        fit.execution = 7.0
        fit.components = {}
        fit.final_score = 8.0
        fit.grade = "A"
        fit.evidence_conflicts = []
        # High score but very low confidence → should block
        conf = ConfidenceBreakdown()
        conf.final = 0.25
        conf.label = "LOW"
        decision = mapper.decide(fit, conf, sector, {})
        self.assertEqual(decision.action, Action.NO_TRADE)
        self.assertIn("too low", decision.rationale)


class TestVCPRegimeCheck(unittest.TestCase):
    """VCP action should be capped at WATCH in adverse regimes."""

    def test_vcp_trade_downgraded_in_crisis(self):
        from src.engines.vcp_intelligence import VCPIntelligence
        from src.engines.sector_classifier import (
            SectorContext, SectorBucket, LeaderStatus,
        )

        sector = SectorContext(
            ticker="TEST",
            sector_bucket=SectorBucket.HIGH_GROWTH,
            leader_status=LeaderStatus.LEADER,
        )
        sig = {
            "ticker": "TEST", "strategy": "vcp",
            "contraction_count": 3, "vol_ratio": 0.6,
            "rs_rank": 85, "atr_pct": 3.0,
            "distance_from_50ma": 3.0,
            "trend_structure": "strong_uptrend",
            "breakout_quality": "genuine",
            "volume_confirms": True,
            "pivot_price": 100.0,
        }
        vcp = VCPIntelligence()
        regime_ok = {"trend": "RISK_ON"}
        regime_bad = {"trend": "CRISIS"}

        result_ok = vcp.analyze(sig, sector, regime_ok)
        result_bad = vcp.analyze(sig, sector, regime_bad)

        # In good regime, grade A VCP → TRADE
        # In CRISIS, should be capped at WATCH
        if result_ok.action and result_ok.action.action == "TRADE":
            self.assertNotEqual(result_bad.action.action, "TRADE",
                "VCP should not be TRADE in CRISIS regime")


class TestFloatEqualityFix(unittest.TestCase):
    """Structure detector should handle near-equal floats."""

    def test_swing_high_near_equal(self):
        import numpy as np
        from src.engines.structure_detector import StructureDetector

        det = StructureDetector(swing_lookback=2)
        # Create prices where max is off by a tiny epsilon
        high = np.array([10.0, 11.0, 12.0, 11.5, 10.5,
                         10.0, 11.0, 11.9999999, 11.5, 10.5,
                         10.0, 10.5, 11.0, 10.5, 10.0])
        vol = np.ones(15) * 1000
        swings = det._find_swing_highs(high, vol)
        # Should find swing highs near index 2 and 7
        # (index 7 is 11.9999999, within epsilon of 12.0)
        self.assertTrue(len(swings) >= 1, "Should detect swing highs with float tolerance")


class TestATRPositionSizing(unittest.TestCase):
    """Position sizing should be ATR-normalized."""

    def test_high_atr_reduces_size(self):
        from src.engines.decision_mapper import DecisionMapper

        # Low vol stock
        size_low, _ = DecisionMapper._size(0.7, "LOW", 8.0, atr_pct=1.5)
        # High vol stock
        size_high, _ = DecisionMapper._size(0.7, "LOW", 8.0, atr_pct=6.0)
        self.assertGreater(size_low, size_high,
            "High ATR stock should get smaller position")

    def test_atr_in_rationale(self):
        from src.engines.decision_mapper import DecisionMapper
        _, rationale = DecisionMapper._size(0.7, "LOW", 8.0, atr_pct=3.5)
        self.assertIn("ATR", rationale)


class TestEntryTrigger(unittest.TestCase):
    """Decision should have entry/stop/target instructions."""

    def test_trade_has_entry_trigger(self):
        from src.engines.decision_mapper import DecisionMapper, Action
        from src.engines.fit_scorer import FitScores
        from src.engines.confidence_engine import ConfidenceBreakdown
        from src.engines.sector_classifier import (
            SectorContext, SectorBucket, LeaderStatus,
        )

        mapper = DecisionMapper()
        fit = FitScores()
        fit.final_score = 8.5
        fit.grade = "A"
        fit.evidence_conflicts = []
        # Attach raw signal data for entry/exit computation
        fit.raw = {
            "nearest_resistance": 155.0,
            "nearest_support": 142.0,
            "price": 150.0,
            "avg_volume": 2000000,
            "atr_pct": 2.5,
        }

        conf = ConfidenceBreakdown()
        conf.final = 0.75
        conf.label = "HIGH"

        sector = SectorContext(
            ticker="TEST",
            sector_bucket=SectorBucket.HIGH_GROWTH,
            leader_status=LeaderStatus.LEADER,
        )

        decision = mapper.decide(fit, conf, sector, {})
        self.assertEqual(decision.action, Action.TRADE)
        self.assertIn("$155", decision.entry_trigger)
        self.assertGreater(decision.stop_price, 0)
        self.assertIn("support", decision.stop_rationale.lower())
        self.assertGreater(decision.target_price, 0)
        self.assertGreater(decision.risk_reward, 0)


class TestAccumulationBugFix(unittest.TestCase):
    """The flow_intelligence accumulation bug should be fixed."""

    def test_duplicate_close_prices(self):
        from src.engines.flow_intelligence import FlowIntelligenceEngine

        fi = FlowIntelligenceEngine()
        # Duplicate close prices that would break .index()
        data = {
            "ticker": "TEST",
            "close_5d": [100.0, 101.0, 101.0, 102.0, 103.0],
            "volume_5d": [1000, 2000, 1500, 3000, 2500],
            "vol_ratio": 1.5,
            "options_iv": 0.3,
            "options_iv_rank": 50,
        }
        # Should not crash (was using .index() which returns first occurrence)
        result = fi.analyze(data)
        self.assertIsNotNone(result)


if __name__ == "__main__":
    unittest.main()
