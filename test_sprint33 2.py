"""
Sprint 33 — Regime Contract + Explanation Fields + Suppression
==============================================================

Tests:
  1-8   RegimeRouter.classify() returns derived labels
  9-14  TradeRecommendation explanation field carry-through
 15-20  OpportunityEnsembler expanded suppression
 21-24  to_api_dict() includes expression + explanation
 25-28  Edge cases and backward compat
"""
import sys
import types
import unittest
from unittest.mock import MagicMock, patch
from datetime import datetime, timezone

# ── Stub heavy deps before any src import ──────────────────
_stubs = {}
for mod_name in (
    "sqlalchemy", "sqlalchemy.orm", "sqlalchemy.ext",
    "sqlalchemy.ext.declarative", "sqlalchemy.dialects",
    "sqlalchemy.dialects.postgresql",
    "pydantic_settings", "discord", "discord.ext",
    "discord.ext.commands", "discord.ext.tasks",
    "discord.app_commands", "tenacity",
):
    if mod_name not in sys.modules:
        _stubs[mod_name] = MagicMock()
        sys.modules[mod_name] = _stubs[mod_name]

db_stub = types.ModuleType("src.core.database")
db_stub.check_database_health = MagicMock(return_value={})
db_stub.get_session = MagicMock()
sys.modules["src.core.database"] = db_stub


# ═══════════════════════════════════════════════════════════
# 1. REGIME CONTRACT
# ═══════════════════════════════════════════════════════════

class TestRegimeContract(unittest.TestCase):
    """RegimeRouter.classify() must return derived labels."""

    def _classify(self, **overrides):
        from src.engines.regime_router import RegimeRouter
        r = RegimeRouter()
        base = {
            "vix": 18.0, "spy_return_20d": 0.0,
            "breadth_pct": 0.50, "hy_spread": 0.0,
            "realized_vol_20d": 0.15, "vix_term_slope": 0.0,
        }
        base.update(overrides)
        return r.classify(base)

    def test_01_regime_key_present(self):
        s = self._classify()
        self.assertIn("regime", s)
        self.assertIn(
            s["regime"], ("RISK_ON", "NEUTRAL", "RISK_OFF"),
        )

    def test_02_risk_regime_present(self):
        s = self._classify()
        self.assertIn("risk_regime", s)
        self.assertIn(
            s["risk_regime"],
            ("risk_on", "neutral", "risk_off"),
        )

    def test_03_trend_regime_present(self):
        s = self._classify()
        self.assertIn("trend_regime", s)
        self.assertIn(
            s["trend_regime"],
            ("uptrend", "downtrend", "sideways"),
        )

    def test_04_volatility_regime_present(self):
        s = self._classify()
        self.assertIn("volatility_regime", s)
        self.assertIn(
            s["volatility_regime"],
            ("low_vol", "normal_vol", "elevated_vol",
             "high_vol", "crisis_vol"),
        )

    def test_05_no_trade_reason_empty_when_should_trade(self):
        s = self._classify(vix=15.0)
        if s["should_trade"]:
            self.assertEqual(s["no_trade_reason"], "")

    def test_06_no_trade_reason_crisis(self):
        s = self._classify(vix=40.0)
        self.assertFalse(s["should_trade"])
        self.assertIn("VIX", s["no_trade_reason"])
        self.assertIn("crisis", s["no_trade_reason"])

    def test_07_risk_on_labels(self):
        s = self._classify(
            vix=12.0, spy_return_20d=0.05, breadth_pct=0.75,
        )
        self.assertEqual(s["regime"], "RISK_ON")
        self.assertEqual(s["risk_regime"], "risk_on")

    def test_08_risk_off_labels(self):
        s = self._classify(
            vix=30.0, spy_return_20d=-0.08,
            breadth_pct=0.25, hy_spread=2.0,
        )
        self.assertEqual(s["regime"], "RISK_OFF")
        self.assertEqual(s["risk_regime"], "risk_off")


# ═══════════════════════════════════════════════════════════
# 2. TRADE RECOMMENDATION EXPLANATION FIELDS
# ═══════════════════════════════════════════════════════════

class TestRecommendationExplanation(unittest.TestCase):
    """TradeRecommendation carries explanation fields end-to-end."""

    def _make_signal(self):
        from src.core.models import (
            Signal, Invalidation, Target,
        )
        return Signal(
            ticker="AAPL",
            direction="LONG",
            horizon="SWING_1_5D",
            entry_price=180.0,
            entry_logic="Breakout above resistance",
            invalidation=Invalidation(
                stop_price=175.0, stop_type="HARD",
            ),
            targets=[Target(price=190.0, pct_position=100)],
            catalyst="Earnings beat",
            key_risks=["Market risk"],
            confidence=75,
            rationale="Strong momentum setup",
            strategy_id="momentum_breakout",
            why_now="Just broke 50d high on 2x volume",
            approval_status="approved",
            approval_flags={"volume": True, "trend": True},
            scenario_plan={"bull": "+5%", "bear": "-3%"},
            evidence=["Above 200 SMA", "RSI rising"],
            event_risk="Earnings in 14d",
            portfolio_fit="good",
            setup_grade="A",
        )

    def test_09_from_signal_carries_why_now(self):
        from src.core.models import TradeRecommendation
        sig = self._make_signal()
        rec = TradeRecommendation.from_signal(sig)
        self.assertEqual(
            rec.why_now, "Just broke 50d high on 2x volume",
        )

    def test_10_from_signal_carries_approval(self):
        from src.core.models import TradeRecommendation
        sig = self._make_signal()
        rec = TradeRecommendation.from_signal(sig)
        self.assertEqual(rec.approval_status, "approved")
        self.assertTrue(rec.approval_flags.get("volume"))

    def test_11_from_signal_carries_scenario(self):
        from src.core.models import TradeRecommendation
        sig = self._make_signal()
        rec = TradeRecommendation.from_signal(sig)
        self.assertIsNotNone(rec.scenario_plan)
        self.assertIn("bull", rec.scenario_plan)

    def test_12_from_signal_carries_evidence(self):
        from src.core.models import TradeRecommendation
        sig = self._make_signal()
        rec = TradeRecommendation.from_signal(sig)
        self.assertEqual(len(rec.evidence), 2)
        self.assertIn("Above 200 SMA", rec.evidence)

    def test_13_from_signal_carries_event_risk(self):
        from src.core.models import TradeRecommendation
        sig = self._make_signal()
        rec = TradeRecommendation.from_signal(sig)
        self.assertEqual(rec.event_risk, "Earnings in 14d")

    def test_14_from_signal_carries_portfolio_fit(self):
        from src.core.models import TradeRecommendation
        sig = self._make_signal()
        rec = TradeRecommendation.from_signal(sig)
        self.assertEqual(rec.portfolio_fit, "good")


# ═══════════════════════════════════════════════════════════
# 3. EXPANDED SUPPRESSION
# ═══════════════════════════════════════════════════════════

class TestExpandedSuppression(unittest.TestCase):
    """OpportunityEnsembler provides detailed no-trade reasons."""

    def _make_rec(self, **kw):
        from src.core.models import TradeRecommendation
        defaults = dict(
            ticker="TEST", direction="LONG",
            strategy_id="test", composite_score=0.5,
            trade_decision=True, signal_confidence=60,
        )
        defaults.update(kw)
        return TradeRecommendation(**defaults)

    def test_15_regime_suppression_with_reason(self):
        from src.engines.opportunity_ensembler import (
            OpportunityEnsembler,
        )
        ens = OpportunityEnsembler()
        rec = self._make_rec(composite_score=0.8)
        regime = {
            "should_trade": False,
            "no_trade_reason": "VIX at 40.0 exceeds crisis",
        }
        result = ens._apply_suppression([rec], regime)
        self.assertFalse(result[0]["trade_decision"])
        self.assertIn(
            "VIX", result[0].get("why_not_trade", ""),
        )

    def test_16_weak_signal_suppression_reason(self):
        from src.engines.opportunity_ensembler import (
            OpportunityEnsembler,
        )
        ens = OpportunityEnsembler(min_score=0.5)
        rec = self._make_rec(
            composite_score=0.2,
            components={"pwin": 0.2, "risk_reward": 0.1},
        )
        regime = {"should_trade": True, "entropy": 0.5}
        result = ens._apply_suppression([rec], regime)
        self.assertFalse(result[0]["trade_decision"])
        why = result[0].get("why_not_trade", "")
        self.assertIn("Composite score", why)

    def test_17_event_risk_suppression(self):
        from src.engines.opportunity_ensembler import (
            OpportunityEnsembler,
        )
        ens = OpportunityEnsembler()
        rec = self._make_rec(
            composite_score=0.6,
            days_to_earnings=1,
            components={"pwin": 0.6, "risk_reward": 0.5},
        )
        regime = {"should_trade": True, "entropy": 0.5}
        result = ens._apply_suppression([rec], regime)
        why = result[0].get("why_not_trade", "")
        self.assertIn("Earnings", why)

    def test_18_high_entropy_suppression(self):
        from src.engines.opportunity_ensembler import (
            OpportunityEnsembler,
        )
        ens = OpportunityEnsembler()
        rec = self._make_rec(
            composite_score=0.6,
            components={"pwin": 0.6, "risk_reward": 0.5},
        )
        regime = {"should_trade": True, "entropy": 1.0}
        result = ens._apply_suppression([rec], regime)
        why = result[0].get("why_not_trade", "")
        self.assertIn("entropy", why)

    def test_19_correlation_suppression(self):
        from src.engines.opportunity_ensembler import (
            OpportunityEnsembler,
        )
        ens = OpportunityEnsembler()
        rec = self._make_rec(
            composite_score=0.6,
            components={"pwin": 0.6, "risk_reward": 0.5},
            penalties={"correlation": 0.15},
        )
        regime = {"should_trade": True, "entropy": 0.5}
        result = ens._apply_suppression([rec], regime)
        why = result[0].get("why_not_trade", "")
        self.assertIn("correlated", why)

    def test_20_pass_through_when_strong(self):
        from src.engines.opportunity_ensembler import (
            OpportunityEnsembler,
        )
        ens = OpportunityEnsembler(min_score=0.3)
        rec = self._make_rec(
            composite_score=0.7,
            components={"pwin": 0.7, "risk_reward": 0.6},
        )
        regime = {"should_trade": True, "entropy": 0.5}
        result = ens._apply_suppression([rec], regime)
        # No suppression applied
        self.assertFalse(
            result[0].get("why_not_trade", ""),
        )


# ═══════════════════════════════════════════════════════════
# 4. TO_API_DICT INCLUDES EXPRESSION + EXPLANATION
# ═══════════════════════════════════════════════════════════

class TestApiDict(unittest.TestCase):
    """to_api_dict() serialises expression and explanation fields."""

    def test_21_api_dict_has_expression(self):
        from src.core.models import TradeRecommendation
        rec = TradeRecommendation(
            ticker="NVDA", direction="LONG",
        )
        d = rec.to_api_dict()
        self.assertIn("expression", d)
        self.assertIn("instrument_type", d["expression"])

    def test_22_api_dict_has_why_this_expression(self):
        from src.core.models import (
            TradeRecommendation, ExpressionPlan,
        )
        rec = TradeRecommendation(
            ticker="NVDA", direction="LONG",
            expression=ExpressionPlan(
                why_this_expression="low IV, long call",
            ),
        )
        d = rec.to_api_dict()
        self.assertEqual(
            d["why_this_expression"], "low IV, long call",
        )

    def test_23_api_dict_has_explanation_fields(self):
        from src.core.models import TradeRecommendation
        rec = TradeRecommendation(
            ticker="AAPL", direction="LONG",
            why_now="breakout", event_risk="none",
            approval_status="approved",
            evidence=["trend", "volume"],
            portfolio_fit="good",
        )
        d = rec.to_api_dict()
        self.assertEqual(d["why_now"], "breakout")
        self.assertEqual(d["event_risk"], "none")
        self.assertEqual(d["approval_status"], "approved")
        self.assertEqual(len(d["evidence"]), 2)
        self.assertEqual(d["portfolio_fit"], "good")

    def test_24_api_dict_has_why_not_trade(self):
        from src.core.models import TradeRecommendation
        rec = TradeRecommendation(
            ticker="TSLA", direction="LONG",
            why_not_trade="Win probability too low",
        )
        d = rec.to_api_dict()
        self.assertEqual(
            d["why_not_trade"], "Win probability too low",
        )


# ═══════════════════════════════════════════════════════════
# 5. EDGE CASES AND BACKWARD COMPAT
# ═══════════════════════════════════════════════════════════

class TestEdgeCases(unittest.TestCase):

    def test_25_regime_still_has_probabilities(self):
        """Old probability keys still present."""
        from src.engines.regime_router import RegimeRouter
        r = RegimeRouter()
        s = r.classify({"vix": 18.0})
        for key in (
            "risk_on_uptrend", "neutral_range",
            "risk_off_downtrend", "entropy",
            "should_trade", "confidence",
        ):
            self.assertIn(key, s)

    def test_26_regime_labels_match_probabilities(self):
        """regime label matches highest probability."""
        from src.engines.regime_router import RegimeRouter
        r = RegimeRouter()
        s = r.classify({
            "vix": 12.0, "spy_return_20d": 0.05,
            "breadth_pct": 0.80,
        })
        probs = {
            "RISK_ON": s["risk_on_uptrend"],
            "NEUTRAL": s["neutral_range"],
            "RISK_OFF": s["risk_off_downtrend"],
        }
        expected = max(probs, key=probs.get)
        self.assertEqual(s["regime"], expected)

    def test_27_from_signal_defaults_when_missing(self):
        """Explanation fields default gracefully."""
        from src.core.models import TradeRecommendation
        sig = MagicMock()
        sig.ticker = "XYZ"
        sig.direction = MagicMock(value="LONG")
        sig.confidence = 60
        sig.invalidation = None
        sig.strategy_id = "test"
        sig.horizon = MagicMock(value="SWING_1_5D")
        sig.entry_price = 100.0
        sig.entry_logic = "test logic"
        sig.catalyst = "test catalyst"
        sig.setup_grade = "B"
        sig.risk_reward_ratio = 2.0
        sig.expected_return = 0.03
        sig.key_risks = []
        sig.rsi = 50
        sig.adx = 25
        sig.relative_volume = 1.0
        sig.distance_from_sma50 = 0.0
        sig.id = "sig1"
        sig.feature_snapshot = None
        # No explanation fields
        del sig.why_now
        del sig.scenario_plan
        del sig.evidence
        del sig.event_risk
        del sig.portfolio_fit
        del sig.approval_status
        del sig.approval_flags
        rec = TradeRecommendation.from_signal(sig)
        self.assertEqual(rec.why_now, "")
        self.assertIsNone(rec.scenario_plan)
        self.assertEqual(rec.evidence, [])

    def test_28_volatility_regime_low(self):
        from src.engines.regime_router import RegimeRouter
        r = RegimeRouter()
        s = r.classify({"vix": 10.0})
        self.assertEqual(s["volatility_regime"], "low_vol")


if __name__ == "__main__":
    unittest.main()
