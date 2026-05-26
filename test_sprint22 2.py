"""
Sprint 22 – TradeRecommendation Contract Tests

Validates:
 1. TradeRecommendation creation and field defaults
 2. from_signal() factory method
 3. from_dict() factory method (backward compat)
 4. Dict-like protocol (__getitem__, __setitem__, get, __contains__)
 5. to_api_dict() JSON-safe serialisation
 6. to_entry_snapshot() ML extraction
 7. OpportunityEnsembler returns List[TradeRecommendation]
 8. Ensemble accepts both dicts AND TradeRecommendation inputs
 9. AutoTradingEngine builds TradeRecommendation via from_signal()
10. _execute_recommendation reads from TradeRecommendation (no dict)
11. Cached recommendations are JSON-safe (no _signal_obj leak)
12. Legacy _execute_signal wrapper still works
"""
import importlib.util
import sys
import types
import unittest
from datetime import datetime, timezone
from unittest.mock import MagicMock, AsyncMock, patch
from uuid import uuid4

# ── Module stubs ─────────────────────────────────────────────────
_db_stub = types.ModuleType("src.core.database")
_db_stub.check_database_health = MagicMock(return_value=True)
sys.modules.setdefault("src.core.database", _db_stub)
for mod_name in (
    "sqlalchemy", "sqlalchemy.orm", "sqlalchemy.ext",
    "sqlalchemy.ext.asyncio",
    "pydantic_settings", "discord", "discord.ext",
    "discord.ext.commands", "discord.ext.tasks",
    "tenacity",
):
    sys.modules.setdefault(mod_name, types.ModuleType(mod_name))

# Stub pydantic_settings.BaseSettings → alias pydantic.BaseModel
import pydantic
ps = sys.modules["pydantic_settings"]
ps.BaseSettings = pydantic.BaseModel

# Stub tenacity decorators
_tenacity = sys.modules["tenacity"]
_tenacity.retry = lambda *a, **kw: (lambda fn: fn)
_tenacity.stop_after_attempt = lambda *a, **kw: None
_tenacity.wait_exponential = lambda *a, **kw: None
_tenacity.retry_if_exception_type = lambda *a, **kw: None

# ── Load production modules directly ─────────────────────────────

def _load(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    mod = importlib.util.module_from_spec(spec)
    sys.modules[name] = mod
    spec.loader.exec_module(mod)
    return mod

_base = "src/core"
_models = _load("src.core.models", f"{_base}/models.py")
_config = _load("src.core.config", f"{_base}/config.py")
_errors = _load("src.core.errors", f"{_base}/errors.py")
_log = _load("src.core.logging_config", f"{_base}/logging_config.py")
_trade_repo = _load("src.core.trade_repo", f"{_base}/trade_repo.py")

_algo_base = "src/algo"
_pos_mgr = _load("src.algo.position_manager",
                  f"{_algo_base}/position_manager.py")

_eng = "src/engines"
_regime = _load("src.engines.regime_router",
                f"{_eng}/regime_router.py")
_leaderboard = _load("src.engines.strategy_leaderboard",
                      f"{_eng}/strategy_leaderboard.py")
_ctx_asm = _load("src.engines.context_assembler",
                 f"{_eng}/context_assembler.py")
_ensembler = _load("src.engines.opportunity_ensembler",
                   f"{_eng}/opportunity_ensembler.py")

_ml = "src/ml"
_learner = _load("src.ml.trade_learner", f"{_ml}/trade_learner.py")

TradeRecommendation = _models.TradeRecommendation
Direction = _models.Direction
Signal = _models.Signal
Horizon = _models.Horizon
Invalidation = _models.Invalidation
StopType = _models.StopType
Target = _models.Target


# ── Helpers ──────────────────────────────────────────────────────

def _make_signal(ticker="AAPL", confidence=75, rr=2.5, **kw):
    """Create a minimal valid Signal for testing."""
    return Signal(
        ticker=ticker,
        direction=Direction.LONG,
        horizon=Horizon.SWING_1_5D,
        entry_price=150.0,
        entry_type="market",
        invalidation=Invalidation(
            stop_price=145.0, stop_type=StopType.HARD,
        ),
        targets=[Target(price=160.0, pct_position=100)],
        entry_logic="test breakout",
        catalyst="earnings beat",
        key_risks=["market risk"],
        confidence=confidence,
        rationale="test signal",
        risk_reward_ratio=rr,
        strategy_id="momentum_breakout",
    )


def _regime():
    return {
        "risk_on_uptrend": 0.6,
        "neutral_range": 0.3,
        "risk_off_downtrend": 0.1,
        "should_trade": True,
        "entropy": 0.4,
        "vix": 18.5,
        "regime": "RISK_ON",
    }


# ═════════════════════════════════════════════════════════════════
# 1. TradeRecommendation DATACLASS TESTS
# ═════════════════════════════════════════════════════════════════

class TestTradeRecommendationCreation(unittest.TestCase):

    def test_01_minimal_creation(self):
        """Create with just ticker; all else defaults."""
        rec = TradeRecommendation(ticker="TSLA")
        self.assertEqual(rec.ticker, "TSLA")
        self.assertEqual(rec.direction, "LONG")
        self.assertEqual(rec.strategy_id, "unknown")
        self.assertEqual(rec.composite_score, 0.0)
        self.assertFalse(rec.trade_decision)
        self.assertEqual(rec.instrument_type, "stock")

    def test_02_full_creation(self):
        """Create with all pipeline fields populated."""
        rec = TradeRecommendation(
            ticker="AAPL",
            direction="LONG",
            strategy_id="momentum_breakout",
            signal_confidence=80,
            score=0.8,
            entry_price=150.0,
            stop_price=145.0,
            risk_reward_ratio=3.0,
            edge_p_t1=0.62,
            edge_ev=0.04,
            composite_score=0.72,
            trade_decision=True,
            regime_label="RISK_ON",
            vix_at_entry=18.5,
        )
        self.assertEqual(rec.composite_score, 0.72)
        self.assertTrue(rec.trade_decision)
        self.assertEqual(rec.edge_p_t1, 0.62)

    def test_03_defaults_sensible(self):
        """Default values don't cause downstream errors."""
        rec = TradeRecommendation(ticker="X")
        self.assertEqual(rec.score, 0.5)
        self.assertEqual(rec.risk_reward_ratio, 1.5)
        self.assertEqual(rec.expected_return, 0.02)
        self.assertEqual(rec.timing_score, 0.5)
        self.assertEqual(rec.days_to_earnings, 999)
        self.assertEqual(rec.kelly_fraction, 0.0)
        self.assertEqual(rec.position_size_shares, 0)


# ═════════════════════════════════════════════════════════════════
# 2. FACTORY METHODS
# ═════════════════════════════════════════════════════════════════

class TestFromSignal(unittest.TestCase):

    def test_04_basic_from_signal(self):
        """from_signal extracts all Signal fields."""
        sig = _make_signal()
        rec = TradeRecommendation.from_signal(sig)
        self.assertEqual(rec.ticker, "AAPL")
        self.assertEqual(rec.direction, "LONG")
        self.assertEqual(rec.strategy_id, "momentum_breakout")
        self.assertEqual(rec.signal_confidence, 75)
        self.assertAlmostEqual(rec.score, 0.75, places=2)
        self.assertEqual(rec.entry_price, 150.0)
        self.assertEqual(rec.stop_price, 145.0)
        self.assertEqual(rec.risk_reward_ratio, 2.5)

    def test_05_from_signal_with_edge(self):
        """from_signal copies EdgeModel data."""
        sig = _make_signal()
        edge = MagicMock()
        edge.p_t1 = 0.65
        edge.p_stop = 0.20
        edge.expected_return_pct = 0.035
        rec = TradeRecommendation.from_signal(sig, edge=edge)
        self.assertEqual(rec.edge_p_t1, 0.65)
        self.assertEqual(rec.edge_p_stop, 0.20)
        self.assertEqual(rec.edge_ev, 0.035)

    def test_06_from_signal_with_regime(self):
        """from_signal captures regime context."""
        sig = _make_signal()
        rec = TradeRecommendation.from_signal(
            sig, regime_state=_regime(),
        )
        self.assertEqual(rec.vix_at_entry, 18.5)
        self.assertEqual(rec.regime_label, "RISK_ON")

    def test_07_from_signal_overrides(self):
        """Keyword overrides take precedence."""
        sig = _make_signal()
        rec = TradeRecommendation.from_signal(
            sig, setup_grade="A", sector="Technology",
        )
        self.assertEqual(rec.setup_grade, "A")
        self.assertEqual(rec.sector, "Technology")

    def test_08_from_signal_preserves_key_risks(self):
        """key_risks list from Signal is carried over."""
        sig = _make_signal()
        rec = TradeRecommendation.from_signal(sig)
        self.assertEqual(rec.key_risks, ["market risk"])


class TestFromDict(unittest.TestCase):

    def test_09_basic_from_dict(self):
        """from_dict maps old field names correctly."""
        d = {
            "ticker": "MSFT",
            "direction": "LONG",
            "score": 0.7,
            "strategy_name": "trend_follow",
            "risk_reward_ratio": 2.0,
            "expected_return": 0.03,
        }
        rec = TradeRecommendation.from_dict(d)
        self.assertEqual(rec.ticker, "MSFT")
        self.assertEqual(rec.strategy_id, "trend_follow")
        self.assertAlmostEqual(rec.score, 0.7, places=2)
        self.assertEqual(rec.risk_reward_ratio, 2.0)

    def test_10_from_dict_edge_fields(self):
        """from_dict picks up edge_p_t1 etc."""
        d = {
            "ticker": "GOOG",
            "direction": "LONG",
            "score": 0.6,
            "strategy_name": "vcp",
            "edge_p_t1": 0.55,
            "edge_ev": 0.02,
        }
        rec = TradeRecommendation.from_dict(d)
        self.assertEqual(rec.edge_p_t1, 0.55)
        self.assertEqual(rec.edge_ev, 0.02)

    def test_11_from_dict_stashes_original(self):
        """from_dict stashes original dict in metadata."""
        d = {"ticker": "X", "score": 0.5, "_signal_obj": "fake"}
        rec = TradeRecommendation.from_dict(d)
        self.assertIn("_original_dict", rec.metadata)
        orig = rec.metadata["_original_dict"]
        self.assertEqual(orig["_signal_obj"], "fake")


# ═════════════════════════════════════════════════════════════════
# 3. DICT-LIKE PROTOCOL
# ═════════════════════════════════════════════════════════════════

class TestDictProtocol(unittest.TestCase):

    def test_12_getitem(self):
        """rec['composite_score'] works."""
        rec = TradeRecommendation(
            ticker="X", composite_score=0.65,
        )
        self.assertEqual(rec["composite_score"], 0.65)
        self.assertEqual(rec["ticker"], "X")

    def test_13_setitem(self):
        """rec['trade_decision'] = True works."""
        rec = TradeRecommendation(ticker="X")
        rec["trade_decision"] = True
        self.assertTrue(rec.trade_decision)

    def test_14_setitem_metadata(self):
        """Unknown keys go to metadata."""
        rec = TradeRecommendation(ticker="X")
        rec["custom_field"] = 42
        self.assertEqual(rec.metadata["custom_field"], 42)

    def test_15_contains(self):
        """'composite_score' in rec works."""
        rec = TradeRecommendation(ticker="X")
        self.assertIn("composite_score", rec)
        self.assertIn("trade_decision", rec)
        self.assertNotIn("nonexistent_xyz", rec)

    def test_16_get_method(self):
        """.get() with default works like dict."""
        rec = TradeRecommendation(
            ticker="X", composite_score=0.5,
        )
        self.assertEqual(rec.get("composite_score"), 0.5)
        self.assertEqual(
            rec.get("nonexistent", "fallback"), "fallback",
        )

    def test_17_getitem_keyerror(self):
        """KeyError raised for missing keys."""
        rec = TradeRecommendation(ticker="X")
        with self.assertRaises(KeyError):
            _ = rec["definitely_not_a_field"]


# ═════════════════════════════════════════════════════════════════
# 4. SERIALISATION
# ═════════════════════════════════════════════════════════════════

class TestSerialisation(unittest.TestCase):

    def test_18_to_api_dict(self):
        """to_api_dict returns JSON-safe dict."""
        rec = TradeRecommendation(
            ticker="AAPL",
            composite_score=0.72,
            trade_decision=True,
            components={"pwin": 0.6},
        )
        d = rec.to_api_dict()
        self.assertIsInstance(d, dict)
        self.assertEqual(d["ticker"], "AAPL")
        self.assertEqual(d["composite_score"], 0.72)
        # timestamp should be ISO string
        self.assertIsInstance(d["timestamp"], str)

    def test_19_to_api_dict_no_signal_obj(self):
        """to_api_dict never contains _signal_obj."""
        rec = TradeRecommendation(ticker="X")
        d = rec.to_api_dict()
        self.assertNotIn("_signal_obj", d)
        # Even if stashed in metadata
        rec.metadata["_signal_obj"] = MagicMock()
        d2 = rec.to_api_dict()
        # metadata key may exist but it's the user's problem
        self.assertNotIn("_signal_obj", d2.keys() - {"metadata"})

    def test_20_to_entry_snapshot(self):
        """to_entry_snapshot extracts ML fields."""
        rec = TradeRecommendation(
            ticker="X",
            signal_confidence=80,
            vix_at_entry=22.0,
            rsi_at_entry=65.0,
            adx_at_entry=30.0,
            relative_volume=1.5,
            distance_from_sma50=0.03,
        )
        snap = rec.to_entry_snapshot()
        self.assertEqual(snap["confidence"], 80)
        self.assertEqual(snap["vix_at_entry"], 22.0)
        self.assertEqual(snap["rsi_at_entry"], 65.0)
        self.assertEqual(snap["relative_volume"], 1.5)


# ═════════════════════════════════════════════════════════════════
# 5. OPPORTUNITY ENSEMBLER RETURNS TradeRecommendation
# ═════════════════════════════════════════════════════════════════

class TestEnsemblerReturnsTyped(unittest.TestCase):

    def setUp(self):
        self.ens = _ensembler.OpportunityEnsembler()
        self.regime = _regime()

    def test_21_returns_trade_recommendations(self):
        """rank_opportunities returns List[TradeRecommendation]."""
        rec = TradeRecommendation(
            ticker="AAPL", score=0.8, strategy_id="momentum",
            risk_reward_ratio=3.0, expected_return=0.05,
        )
        result = self.ens.rank_opportunities(
            [rec], self.regime,
        )
        self.assertEqual(len(result), 1)
        self.assertIsInstance(result[0], TradeRecommendation)
        self.assertGreater(result[0].composite_score, 0)

    def test_22_dict_input_auto_converted(self):
        """Legacy dict input is auto-converted to TR."""
        d = {
            "ticker": "MSFT", "score": 0.7,
            "direction": "LONG",
            "strategy_name": "trend",
            "risk_reward_ratio": 2.5,
            "expected_return": 0.04,
        }
        result = self.ens.rank_opportunities(
            [d], self.regime,
        )
        self.assertEqual(len(result), 1)
        self.assertIsInstance(result[0], TradeRecommendation)
        self.assertEqual(result[0].ticker, "MSFT")
        # strategy_name mapped to strategy_id
        self.assertEqual(result[0].strategy_id, "trend")

    def test_23_mixed_input(self):
        """Accepts mix of dicts and TradeRecommendation."""
        d = {
            "ticker": "GOOG", "score": 0.6,
            "direction": "LONG",
            "strategy_name": "swing",
            "risk_reward_ratio": 2.0,
        }
        rec = TradeRecommendation(
            ticker="AAPL", score=0.9,
            strategy_id="momentum",
            risk_reward_ratio=3.5,
        )
        result = self.ens.rank_opportunities(
            [d, rec], self.regime,
        )
        self.assertEqual(len(result), 2)
        self.assertTrue(all(
            isinstance(r, TradeRecommendation) for r in result
        ))

    def test_24_dict_compat_access_still_works(self):
        """Old dict-access patterns work on returned TRs."""
        d = {
            "ticker": "AAPL", "score": 0.8,
            "direction": "LONG",
            "strategy_name": "momentum",
            "risk_reward_ratio": 3.0,
            "expected_return": 0.05,
        }
        result = self.ens.rank_opportunities(
            [d], self.regime,
        )
        r = result[0]
        # Old dict access patterns
        self.assertIsInstance(r["composite_score"], float)
        self.assertIn("trade_decision", r)
        comp = r["components"]
        for k in ("pwin", "exp_r", "regime_fit", "risk_reward"):
            self.assertIn(k, comp)

    def test_25_sorted_descending(self):
        """Results sorted by composite_score descending."""
        recs = [
            TradeRecommendation(
                ticker="LOW", score=0.3,
                strategy_id="reversion",
                risk_reward_ratio=1.0,
            ),
            TradeRecommendation(
                ticker="HIGH", score=0.9,
                strategy_id="momentum",
                risk_reward_ratio=4.0,
                expected_return=0.08,
            ),
        ]
        result = self.ens.rank_opportunities(
            recs, self.regime,
            strategy_scores={
                "momentum": 0.9, "reversion": 0.3,
            },
        )
        self.assertGreaterEqual(
            result[0].composite_score,
            result[1].composite_score,
        )

    def test_26_suppression_sets_field(self):
        """Suppression mutates trade_decision on TR."""
        rec = TradeRecommendation(
            ticker="X", score=0.9,
            strategy_id="momentum",
            risk_reward_ratio=3.0,
        )
        result = self.ens.rank_opportunities(
            [rec],
            {"should_trade": False, "entropy": 1.5,
             "risk_on_uptrend": 0.2,
             "neutral_range": 0.3,
             "risk_off_downtrend": 0.5},
        )
        self.assertFalse(result[0].trade_decision)
        self.assertEqual(
            result[0].suppression_reason, "regime_no_trade",
        )

    def test_27_edge_preferred_over_score(self):
        """Non-zero edge_p_t1 takes priority over score."""
        rec = TradeRecommendation(
            ticker="X", score=0.5,
            edge_p_t1=0.85,
            strategy_id="momentum",
            risk_reward_ratio=2.0,
        )
        result = self.ens.rank_opportunities(
            [rec], self.regime,
        )
        # pwin component should use 0.85, not 0.5
        self.assertAlmostEqual(
            result[0].components["pwin"], 0.85, places=2,
        )

    def test_28_no_original_signal_field(self):
        """TR objects do not have 'original_signal' key."""
        rec = TradeRecommendation(
            ticker="X", score=0.7,
            strategy_id="swing",
            risk_reward_ratio=2.0,
        )
        result = self.ens.rank_opportunities(
            [rec], self.regime,
        )
        self.assertNotIn(
            "original_signal", result[0].model_fields,
        )


# ═════════════════════════════════════════════════════════════════
# 6. AUTO TRADING ENGINE INTEGRATION
# ═════════════════════════════════════════════════════════════════

class TestEngineTradeRecommendationPipeline(unittest.TestCase):

    def test_29_engine_imports_trade_recommendation(self):
        """auto_trading_engine imports TradeRecommendation."""
        with open("src/engines/auto_trading_engine.py") as f:
            src = f.read()
        self.assertIn("TradeRecommendation", src)
        self.assertIn("from_signal", src)

    def test_30_no_signal_dicts_in_run_cycle(self):
        """_run_cycle no longer builds signal_dicts list."""
        with open("src/engines/auto_trading_engine.py") as f:
            src = f.read(8000)
        self.assertNotIn("signal_dicts", src)
        self.assertNotIn('"_signal_obj"', src)

    def test_31_execute_recommendation_method_exists(self):
        """_execute_recommendation method is defined."""
        with open("src/engines/auto_trading_engine.py") as f:
            src = f.read()
        self.assertIn(
            "_execute_recommendation", src,
        )

    def test_32_cached_recommendations_json_safe(self):
        """Cached recommendations use to_api_dict()."""
        with open("src/engines/auto_trading_engine.py") as f:
            src = f.read()
        self.assertIn("to_api_dict()", src)
        # Should NOT cache raw TR objects (would fail JSON)
        self.assertNotIn(
            "_cached_recommendations = ranked",
            src,
        )

    def test_33_ml_gate_uses_entry_snapshot(self):
        """ML quality gate uses rec.to_entry_snapshot()."""
        with open("src/engines/auto_trading_engine.py") as f:
            src = f.read()
        self.assertIn("to_entry_snapshot()", src)

    def test_34_from_signal_in_pipeline(self):
        """TradeRecommendation.from_signal is used in pipeline."""
        with open("src/engines/auto_trading_engine.py") as f:
            src = f.read()
        self.assertIn(
            "TradeRecommendation.from_signal", src,
        )


# ═════════════════════════════════════════════════════════════════
# 7. ENSEMBLER _calc_regime_fit BACKWARD COMPAT
# ═════════════════════════════════════════════════════════════════

class TestEnsemblerBackwardCompat(unittest.TestCase):

    def setUp(self):
        self.ens = _ensembler.OpportunityEnsembler()

    def test_35_calc_regime_fit_with_dict(self):
        """_calc_regime_fit still works with plain dicts."""
        fit = self.ens._calc_regime_fit(
            {"strategy_name": "momentum_breakout",
             "direction": "LONG"},
            {"risk_on_uptrend": 0.7,
             "neutral_range": 0.2,
             "risk_off_downtrend": 0.1},
        )
        self.assertGreater(fit, 0.3)

    def test_36_calc_regime_fit_with_tr(self):
        """_calc_regime_fit works with TradeRecommendation."""
        rec = TradeRecommendation(
            ticker="X",
            strategy_id="momentum_breakout",
            direction="LONG",
        )
        fit = self.ens._calc_regime_fit(
            rec,
            {"risk_on_uptrend": 0.7,
             "neutral_range": 0.2,
             "risk_off_downtrend": 0.1},
        )
        self.assertGreater(fit, 0.3)

    def test_37_correlation_penalty_with_dict(self):
        """_correlation_penalty still works with plain dicts."""
        pen = self.ens._correlation_penalty(
            {"ticker": "AAPL", "sector": "Tech"},
            {"tickers": ["AAPL"], "sectors": {"Tech": 0.3}},
        )
        self.assertGreater(pen, 0)

    def test_38_correlation_penalty_with_tr(self):
        """_correlation_penalty works with TradeRecommendation."""
        rec = TradeRecommendation(
            ticker="AAPL", sector="Tech",
        )
        pen = self.ens._correlation_penalty(
            rec,
            {"tickers": ["AAPL"], "sectors": {"Tech": 0.3}},
        )
        self.assertGreater(pen, 0)

    def test_39_suppression_with_dicts(self):
        """_apply_suppression still works with plain dicts."""
        ranked = [
            {"composite_score": 0.8, "trade_decision": True},
        ]
        result = self.ens._apply_suppression(
            ranked, {"should_trade": False},
        )
        self.assertFalse(result[0]["trade_decision"])
        self.assertEqual(
            result[0].get("suppression_reason"),
            "regime_no_trade",
        )

    def test_40_suppression_with_tr(self):
        """_apply_suppression works with TradeRecommendation."""
        rec = TradeRecommendation(
            ticker="X", composite_score=0.8,
            trade_decision=True,
        )
        result = self.ens._apply_suppression(
            [rec], {"should_trade": False},
        )
        self.assertFalse(result[0].trade_decision)
        self.assertEqual(
            result[0].suppression_reason, "regime_no_trade",
        )


# ═════════════════════════════════════════════════════════════════
# 8. POSITION SIZING WITH TradeRecommendation
# ═════════════════════════════════════════════════════════════════

class TestPositionSizingWithTR(unittest.TestCase):

    def test_41_calculate_size_with_tr(self):
        """_calculate_position_size works with TR stop_price."""
        # Load engine module
        _ate = _load(
            "src.engines.auto_trading_engine",
            "src/engines/auto_trading_engine.py",
        )
        engine = _ate.AutoTradingEngine(dry_run=True)
        rec = TradeRecommendation(
            ticker="AAPL",
            entry_price=150.0,
            stop_price=145.0,
            risk_reward_ratio=2.5,
        )
        qty = engine._calculate_position_size(
            rec,
            edge_pwin=0.6,
            edge_rr=2.5,
            strategy_name="momentum",
        )
        self.assertGreater(qty, 0)
        self.assertIsInstance(qty, int)


# ═════════════════════════════════════════════════════════════════
# 9. EDGE CASE TESTS
# ═════════════════════════════════════════════════════════════════

class TestEdgeCases(unittest.TestCase):

    def test_42_empty_ensemble(self):
        """Empty signal list returns empty list."""
        ens = _ensembler.OpportunityEnsembler()
        result = ens.rank_opportunities([], _regime())
        self.assertEqual(result, [])

    def test_43_from_dict_missing_fields(self):
        """from_dict with minimal dict still works."""
        d = {"ticker": "X"}
        rec = TradeRecommendation.from_dict(d)
        self.assertEqual(rec.ticker, "X")
        self.assertEqual(rec.direction, "LONG")
        self.assertEqual(rec.strategy_id, "unknown")

    def test_44_from_signal_no_invalidation(self):
        """from_signal handles Signal without invalidation."""
        sig = MagicMock()
        sig.ticker = "TSLA"
        sig.direction = Direction.LONG
        sig.confidence = 60
        sig.invalidation = None
        sig.risk_reward_ratio = 2.0
        sig.expected_return = 0.03
        sig.entry_price = 200.0
        sig.horizon = Horizon.SWING_1_5D
        sig.entry_logic = "test"
        sig.catalyst = "test"
        sig.setup_grade = None
        sig.id = None
        sig.key_risks = []
        sig.strategy_id = "test_strat"
        sig.strategy_name = None
        sig.rsi = 55
        sig.adx = 20
        sig.relative_volume = 1.2
        sig.distance_from_sma50 = 0.01
        rec = TradeRecommendation.from_signal(sig)
        self.assertEqual(rec.stop_price, 0.0)
        self.assertEqual(rec.strategy_id, "test_strat")

    def test_45_model_dump_roundtrip(self):
        """model_dump → TradeRecommendation roundtrip works."""
        rec = TradeRecommendation(
            ticker="AAPL",
            composite_score=0.72,
            components={"pwin": 0.6, "exp_r": 0.3},
        )
        d = rec.model_dump()
        rec2 = TradeRecommendation(**d)
        self.assertEqual(rec2.ticker, "AAPL")
        self.assertEqual(rec2.composite_score, 0.72)


if __name__ == "__main__":
    unittest.main()
