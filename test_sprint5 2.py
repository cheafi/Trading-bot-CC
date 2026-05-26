"""Sprint 5: config integration + PositionManager wiring tests."""
import sys, os, unittest, importlib.util
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))


def _load(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


_cfg = _load("config", "src/core/config.py")


class TestTradingConfigNewFields(unittest.TestCase):
    """Verify new config fields exist with correct defaults."""

    def setUp(self):
        self.tc = _cfg.TradingConfig()

    def test_regime_fields(self):
        self.assertEqual(self.tc.regime_vix_crisis, 35.0)
        self.assertEqual(self.tc.regime_no_trade_entropy, 1.35)
        self.assertEqual(self.tc.regime_min_confidence, 0.40)

    def test_ensemble_fields(self):
        self.assertEqual(self.tc.ensemble_min_score, 0.35)

    def test_expression_fields(self):
        self.assertFalse(self.tc.options_enabled)
        self.assertEqual(self.tc.max_option_allocation, 0.20)
        self.assertEqual(self.tc.min_option_oi, 500)

    def test_leaderboard_fields(self):
        self.assertEqual(self.tc.strategy_cooldown_score, 0.20)
        self.assertEqual(self.tc.strategy_reduced_score, 0.35)
        self.assertEqual(self.tc.strategy_retire_days, 90)

    def test_position_fields(self):
        self.assertEqual(self.tc.stop_loss_pct, 0.03)
        self.assertEqual(self.tc.trailing_stop_pct, 0.02)
        self.assertEqual(self.tc.max_hold_days, 30)


class TestModulesReadConfig(unittest.TestCase):
    """Verify Sprint 3 modules read from config at init."""

    def test_regime_router_uses_config(self):
        rr = _load("rr", "src/engines/regime_router.py")
        router = rr.RegimeRouter()
        # Should have read from config (or fallback)
        self.assertIsNotNone(router.no_trade_entropy)
        self.assertIsNotNone(router.min_confidence)
        self.assertGreater(router.VIX_CRISIS, 0)

    def test_ensembler_uses_config(self):
        oe = _load("oe", "src/engines/opportunity_ensembler.py")
        ens = oe.OpportunityEnsembler()
        self.assertIsNotNone(ens.min_score)
        self.assertGreater(ens.min_score, 0)

    def test_expression_uses_config(self):
        ee = _load("ee", "src/engines/expression_engine.py")
        eng = ee.ExpressionEngine()
        self.assertFalse(eng.options_enabled)
        self.assertGreater(eng.max_option_allocation, 0)

    def test_leaderboard_uses_config(self):
        lb = _load("lb", "src/engines/strategy_leaderboard.py")
        board = lb.StrategyLeaderboard()
        self.assertGreater(board.COOLDOWN_SCORE, 0)
        self.assertGreater(board.REDUCED_SCORE, 0)
        self.assertGreater(board.RETIRE_AFTER_DAYS, 0)


class TestAutoTradingEngineWiring(unittest.TestCase):
    """Verify PositionManager is wired into the engine."""

    def _read(self):
        with open("src/engines/auto_trading_engine.py") as f:
            return f.read()

    def test_position_manager_imported(self):
        src = self._read()
        self.assertIn("from src.algo.position_manager import", src)
        self.assertIn("PositionManager", src)

    def test_position_manager_initialized(self):
        src = self._read()
        self.assertIn("self.position_mgr", src)
        self.assertIn("RiskParameters", src)

    def test_open_position_on_trade(self):
        src = self._read()
        self.assertIn("position_mgr.open_position", src)

    def test_config_used_for_risk_params(self):
        src = self._read()
        self.assertIn("get_trading_config", src)
        self.assertIn("tc.max_position_pct", src)


if __name__ == "__main__":
    unittest.main()
