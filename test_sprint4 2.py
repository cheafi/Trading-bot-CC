"""Sprint 4 integration tests — verify modules are wired in."""
import sys, os, unittest, importlib.util
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))


class TestAutoTradingEngineIntegration(unittest.TestCase):
    """Verify Sprint 3 modules are wired into the engine."""

    def _read_engine(self):
        with open("src/engines/auto_trading_engine.py") as f:
            return f.read()

    def test_imports_present(self):
        src = self._read_engine()
        for name in [
            "RegimeRouter", "OpportunityEnsembler",
            "ContextAssembler", "StrategyLeaderboard",
        ]:
            self.assertIn(
                f"import {name}", src,
                f"Missing import: {name}",
            )

    def test_init_components(self):
        src = self._read_engine()
        for attr in [
            "self.regime_router",
            "self.ensembler",
            "self.context_assembler",
            "self.leaderboard",
        ]:
            self.assertIn(attr, src, f"Missing init: {attr}")

    def test_regime_gate_exists(self):
        src = self._read_engine()
        self.assertIn("regime_router.classify", src)
        self.assertIn("should_trade", src)

    def test_context_assembly_in_cycle(self):
        src = self._read_engine()
        self.assertIn("context_assembler.assemble_sync", src)

    def test_ensembler_used(self):
        src = self._read_engine()
        self.assertIn("ensembler.rank_opportunities", src)
        self.assertIn("composite_score", src)

    def test_context_fed_to_validation(self):
        src = self._read_engine()
        self.assertIn('news_by_ticker=self._context', src)
        self.assertIn('sentiment_by_ticker=self._context', src)

    def test_portfolio_fed_to_signals(self):
        src = self._read_engine()
        # portfolio should use context, not empty dict
        self.assertNotIn("portfolio={}", src)
        self.assertIn("portfolio_state", src)

    def test_leaderboard_scores_fed(self):
        src = self._read_engine()
        self.assertIn(
            "leaderboard.get_strategy_scores", src,
        )

    def test_no_empty_dict_news(self):
        """news_by_ticker should not be hardcoded {}."""
        src = self._read_engine()
        self.assertNotIn("news_by_ticker={}", src)

    def test_no_empty_dict_sentiment(self):
        """sentiment_by_ticker should not be hardcoded {}."""
        src = self._read_engine()
        self.assertNotIn("sentiment_by_ticker={}", src)


class TestRegimeRouterUnit(unittest.TestCase):
    """Additional regime router edge-case tests."""

    def setUp(self):
        spec = importlib.util.spec_from_file_location(
            "rr", "src/engines/regime_router.py")
        self.mod = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(self.mod)
        self.router = self.mod.RegimeRouter()

    def test_empty_input_defaults(self):
        st = self.router.classify({})
        self.assertIn("should_trade", st)
        self.assertIn("entropy", st)
        total = (st["risk_on_uptrend"] + st["neutral_range"]
                 + st["risk_off_downtrend"])
        self.assertAlmostEqual(total, 1.0, places=2)

    def test_extreme_bull(self):
        st = self.router.classify({
            "vix": 10, "spy_return_20d": 0.08,
            "breadth_pct": 0.85})
        self.assertGreater(st["risk_on_uptrend"], 0.5)

    def test_high_entropy_no_trade(self):
        router = self.mod.RegimeRouter(no_trade_entropy=0.01)
        st = router.classify({"vix": 20})
        self.assertFalse(st["should_trade"])


class TestEnsemblerEdgeCases(unittest.TestCase):

    def setUp(self):
        spec = importlib.util.spec_from_file_location(
            "oe", "src/engines/opportunity_ensembler.py")
        self.mod = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(self.mod)
        self.ens = self.mod.OpportunityEnsembler()

    def test_empty_signals(self):
        regime = {"should_trade": True, "entropy": 0.3,
                  "risk_on_uptrend": 0.5,
                  "neutral_range": 0.3,
                  "risk_off_downtrend": 0.2}
        ranked = self.ens.rank_opportunities([], regime)
        self.assertEqual(ranked, [])

    def test_correlation_penalty(self):
        sigs = [{"ticker": "AAPL", "score": 0.8,
                 "direction": "LONG",
                 "strategy_name": "momentum",
                 "risk_reward_ratio": 3.0,
                 "expected_return": 0.05}]
        regime = {"should_trade": True, "entropy": 0.3,
                  "risk_on_uptrend": 0.6,
                  "neutral_range": 0.3,
                  "risk_off_downtrend": 0.1}
        port = {"tickers": ["AAPL"], "sectors": {}}
        ranked = self.ens.rank_opportunities(
            sigs, regime, portfolio_state=port)
        # Should have correlation penalty applied
        self.assertIn("correlation",
                       ranked[0].get("penalties", {}))


if __name__ == "__main__":
    unittest.main()
