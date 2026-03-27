"""Sprint 3 regression tests — 28 tests covering all new modules."""
import sys, os, unittest, importlib.util
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))


def _load(name, path):
    """Direct-load a module bypassing __init__.py chains."""
    spec = importlib.util.spec_from_file_location(name, path)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


# Direct-load to avoid pandas/sqlalchemy chain in __init__.py
_models = _load("models", "src/core/models.py")
_regime = _load("regime_router", "src/engines/regime_router.py")
_ensemb = _load("opportunity_ensembler",
                 "src/engines/opportunity_ensembler.py")
_expr = _load("expression_engine",
              "src/engines/expression_engine.py")
_ctx = _load("context_assembler",
             "src/engines/context_assembler.py")
_lb = _load("strategy_leaderboard",
            "src/engines/strategy_leaderboard.py")


class TestTradeRecommendationModels(unittest.TestCase):

    def test_instrument_type_enum(self):
        IT = _models.InstrumentType
        self.assertEqual(IT.STOCK, "stock")
        self.assertEqual(IT.CALL, "call")
        self.assertEqual(IT.PUT, "put")
        self.assertEqual(IT.DEBIT_SPREAD, "debit_spread")

    def test_trade_recommendation_creation(self):
        TR = _models.TradeRecommendation
        rec = TR(ticker="AAPL", direction="LONG",
                 instrument_type="stock",
                 composite_score=0.75,
                 strategy_id="momentum",
                 regime_weight=0.8)
        self.assertEqual(rec.ticker, "AAPL")
        self.assertEqual(rec.composite_score, 0.75)
        self.assertEqual(rec.instrument_type, "stock")

    def test_expression_plan_creation(self):
        EP = _models.ExpressionPlan
        plan = EP(instrument_type="call",
                  why_this_expression="cheap IV")
        self.assertEqual(plan.instrument_type, "call")

    def test_regime_state_creation(self):
        RS = _models.RegimeState
        st = RS(risk_on_uptrend=0.6, neutral_range=0.25,
                risk_off_downtrend=0.15, entropy=0.5,
                should_trade=True, confidence=0.6)
        total = (st.risk_on_uptrend + st.neutral_range
                 + st.risk_off_downtrend)
        self.assertAlmostEqual(total, 1.0, places=2)
        self.assertTrue(st.should_trade)

    def test_strategy_score_creation(self):
        SS = _models.StrategyScore
        ss = SS(strategy_id="vcp_01", composite_score=0.65,
                status="active")
        self.assertEqual(ss.strategy_id, "vcp_01")
        self.assertEqual(ss.status, "active")

    def test_setup_grade_enum(self):
        SG = _models.SetupGrade
        self.assertEqual(SG.A, "A")
        self.assertEqual(SG.C, "C")
        self.assertEqual(SG.REJECT, "Reject")

    def test_mistake_type_enum(self):
        MT = _models.MistakeType
        self.assertEqual(MT.CHASED_ENTRY, "chased_entry")
        self.assertEqual(MT.OVERSIZED, "oversized")
        self.assertEqual(MT.PREMATURE_EXIT, "premature_exit")

    def test_learning_tag_enum(self):
        LT = _models.LearningTag
        self.assertEqual(LT.REGIME_CORRECT, "regime_correct")


class TestScenarioPlanContract(unittest.TestCase):

    def test_scenario_plan_keys(self):
        with open("src/engines/signal_engine.py") as f:
            src = f.read()
        self.assertIn('"base_case"', src)
        self.assertIn('"bull_case"', src)
        self.assertIn('"bear_case"', src)
        self.assertNotIn('"bull_trigger":', src)
        self.assertNotIn('"bear_trigger":', src)


class TestRegimeRouter(unittest.TestCase):

    def setUp(self):
        self.router = _regime.RegimeRouter()

    def test_calm_market_risk_on(self):
        st = self.router.classify(
            {"vix": 12.0, "spy_return_20d": 0.03,
             "breadth_pct": 0.70, "hy_spread": 0.0})
        self.assertGreater(st["risk_on_uptrend"], 0.4)
        self.assertTrue(st["should_trade"])

    def test_crisis_vix_blocks(self):
        st = self.router.classify(
            {"vix": 40.0, "spy_return_20d": -0.15,
             "breadth_pct": 0.20})
        self.assertFalse(st["should_trade"])

    def test_probs_sum_one(self):
        st = self.router.classify({"vix": 20.0})
        total = (st["risk_on_uptrend"] + st["neutral_range"]
                 + st["risk_off_downtrend"])
        self.assertAlmostEqual(total, 1.0, places=2)

    def test_entropy_bounded(self):
        st = self.router.classify({"vix": 18.0})
        self.assertGreaterEqual(st["entropy"], 0)
        self.assertLessEqual(st["entropy"], 1.1)

    def test_strategy_multipliers(self):
        st = self.router.classify({"vix": 14.0})
        m = self.router.get_strategy_multipliers(st)
        self.assertIn("momentum", m)
        self.assertIn("mean_reversion", m)
        for v in m.values():
            self.assertGreaterEqual(v, 0)
            self.assertLessEqual(v, 1.0)


class TestOpportunityEnsembler(unittest.TestCase):

    def setUp(self):
        self.ens = _ensemb.OpportunityEnsembler()

    def test_rank_sorted(self):
        sigs = [
            {"ticker": "AAPL", "score": 0.5,
             "direction": "LONG", "strategy_name": "momentum",
             "risk_reward_ratio": 2.0, "expected_return": 0.03},
            {"ticker": "MSFT", "score": 0.8,
             "direction": "LONG", "strategy_name": "trend",
             "risk_reward_ratio": 3.0, "expected_return": 0.05},
        ]
        reg = {"risk_on_uptrend": 0.6, "neutral_range": 0.3,
               "risk_off_downtrend": 0.1,
               "should_trade": True, "entropy": 0.4}
        ranked = self.ens.rank_opportunities(sigs, reg)
        self.assertEqual(len(ranked), 2)
        self.assertGreaterEqual(
            ranked[0]["composite_score"],
            ranked[1]["composite_score"])

    def test_no_trade_suppresses(self):
        sigs = [{"ticker": "AAPL", "score": 0.9,
                 "direction": "LONG",
                 "strategy_name": "momentum",
                 "risk_reward_ratio": 3.0,
                 "expected_return": 0.05}]
        reg = {"should_trade": False, "entropy": 1.5,
               "risk_on_uptrend": 0.2, "neutral_range": 0.3,
               "risk_off_downtrend": 0.5}
        ranked = self.ens.rank_opportunities(sigs, reg)
        for r in ranked:
            self.assertFalse(r["trade_decision"])

    def test_components_present(self):
        sigs = [{"ticker": "XYZ", "score": 0.7,
                 "direction": "LONG",
                 "strategy_name": "swing",
                 "risk_reward_ratio": 2.5,
                 "expected_return": 0.04}]
        reg = {"risk_on_uptrend": 0.5, "neutral_range": 0.3,
               "risk_off_downtrend": 0.2,
               "should_trade": True, "entropy": 0.5}
        ranked = self.ens.rank_opportunities(sigs, reg)
        comp = ranked[0]["components"]
        for k in ["pwin", "exp_r", "regime_fit", "risk_reward"]:
            self.assertIn(k, comp)


class TestExpressionEngine(unittest.TestCase):

    def setUp(self):
        self.eng = _expr.ExpressionEngine(options_enabled=True)
        self.eng_off = _expr.ExpressionEngine(
            options_enabled=False)

    def test_disabled_returns_stock(self):
        p = self.eng_off.select_expression(
            "AAPL", "LONG",
            {"hold_period_days": 5, "confidence": 0.8})
        self.assertEqual(p["instrument"], "stock")
        self.assertEqual(p["reason"], "options_disabled")

    def test_no_data_returns_stock(self):
        p = self.eng.select_expression(
            "AAPL", "LONG",
            {"hold_period_days": 5, "confidence": 0.8})
        self.assertEqual(p["instrument"], "stock")

    def test_cheap_iv_option(self):
        p = self.eng.select_expression(
            "AAPL", "LONG",
            {"hold_period_days": 10, "confidence": 0.75,
             "expected_return": 0.05, "risk_reward_ratio": 2.0},
            options_data={"iv_percentile": 20,
                          "avg_open_interest": 5000,
                          "avg_bid_ask_spread": 0.02})
        self.assertEqual(p["instrument"], "CALL")

    def test_illiquid_stock(self):
        p = self.eng.select_expression(
            "AAPL", "LONG",
            {"hold_period_days": 5, "confidence": 0.8},
            options_data={"iv_percentile": 25,
                          "avg_open_interest": 50,
                          "avg_bid_ask_spread": 0.01})
        self.assertEqual(p["instrument"], "stock")
        self.assertEqual(p["reason"], "illiquid_options")


class TestContextAssembler(unittest.TestCase):

    def test_sync_all_keys(self):
        asm = _ctx.ContextAssembler()
        ctx = asm.assemble_sync()
        for k in ["market_state", "portfolio_state",
                   "news_by_ticker", "sentiment",
                   "calendar_events", "timestamp"]:
            self.assertIn(k, ctx)

    def test_market_state_vix(self):
        asm = _ctx.ContextAssembler()
        ctx = asm.assemble_sync()
        self.assertIn("vix", ctx["market_state"])


class TestStrategyLeaderboard(unittest.TestCase):

    def setUp(self):
        self.lb = _lb.StrategyLeaderboard()

    def test_update_score(self):
        e = self.lb.update("mom_v2", {
            "oos_sharpe": 1.5, "expectancy": 1.2,
            "calmar_ratio": 2.0, "win_rate": 0.55,
            "profit_factor": 2.0, "max_drawdown": 0.08,
            "consistency": 0.6, "trade_count": 50})
        self.assertGreater(e["blended_score"], 0)
        self.assertEqual(e["name"], "mom_v2")

    def test_poor_cooldown(self):
        e = self.lb.update("bad", {
            "oos_sharpe": 0.1, "expectancy": 0.05,
            "calmar_ratio": 0.2, "win_rate": 0.30,
            "profit_factor": 0.8, "max_drawdown": 0.25,
            "consistency": 0.2, "trade_count": 50})
        self.assertEqual(
            e["status"], _lb.StrategyStatus.COOLDOWN)

    def test_active_list(self):
        self.lb.update("good", {
            "oos_sharpe": 1.8, "expectancy": 1.5,
            "calmar_ratio": 2.5, "win_rate": 0.60,
            "profit_factor": 2.5, "max_drawdown": 0.05,
            "consistency": 0.7, "trade_count": 100})
        self.assertIn("good", self.lb.get_active_strategies())

    def test_sizing_mult(self):
        self.lb.update("ts", {
            "oos_sharpe": 1.0, "expectancy": 1.0,
            "calmar_ratio": 1.5, "win_rate": 0.55,
            "profit_factor": 1.5, "max_drawdown": 0.10,
            "consistency": 0.5, "trade_count": 30})
        self.assertIn(
            self.lb.get_sizing_multiplier("ts"),
            [0.0, 0.5, 1.0])


class TestAutoTradingEngineSizing(unittest.TestCase):

    def test_size_method_exists(self):
        with open("src/engines/auto_trading_engine.py") as f:
            src = f.read()
        self.assertIn("def _calculate_position_size", src)
        self.assertNotIn("quantity=1,", src)

    def test_monitor_implemented(self):
        with open("src/engines/auto_trading_engine.py") as f:
            src = f.read()
        idx = src.index("async def _monitor_positions")
        body = src[idx:idx + 500]
        self.assertNotIn("pass  # Integrates", body)
        self.assertIn("stop", body.lower())


if __name__ == "__main__":
    unittest.main()
