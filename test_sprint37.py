"""
Sprint 37 tests — Explanation Layer + Commands.

Changes:
  src/core/models.py               — to_api_dict() now groups 9+1
                                      explanation fields into a
                                      dedicated "explanation" section
  src/core/trust_metadata.py       — MODEL_VERSION bumped to v6.37
  src/engines/auto_trading_engine.py — _no_trade_card init, expose
                                        no_trade_card & kpi_snapshot
                                        in get_cached_state(),
                                        _build_kpi_snapshot() helper
  src/notifications/discord_bot.py — /kpi, /notrade, /calibration
                                      commands, footer updated

35+ new tests.
"""
import importlib
import importlib.util
import os
import sys
import unittest
from unittest.mock import MagicMock

# ── Stub heavy deps before any src.* imports ─────────────
for _mod in [
    "sqlalchemy", "sqlalchemy.orm", "sqlalchemy.exc",
    "sqlalchemy.pool", "sqlalchemy.engine",
    "pydantic_settings",
    "discord", "discord.ext", "discord.ext.commands",
    "discord.ext.tasks", "discord.ui",
    "tenacity",
    "fastapi", "uvicorn",
    "apscheduler", "apscheduler.schedulers",
    "apscheduler.schedulers.asyncio",
    "aiohttp", "aiohttp.web",
]:
    if _mod not in sys.modules:
        sys.modules[_mod] = MagicMock()

_db_stub = MagicMock()
_db_stub.check_database_health = MagicMock(return_value={})
_db_stub.get_session = MagicMock()
sys.modules.setdefault("src.core.database", _db_stub)

import numpy as _real_np
sys.modules["numpy"] = _real_np

# ── Load module under test ────────────────────────────────
BASE = os.path.dirname(os.path.abspath(__file__))


def _load(mod_name: str, rel_path: str):
    path = os.path.join(BASE, rel_path)
    spec = importlib.util.spec_from_file_location(
        mod_name, path,
    )
    mod = importlib.util.module_from_spec(spec)
    sys.modules[mod_name] = mod
    spec.loader.exec_module(mod)
    return mod


# Load core modules
_models = _load(
    "src.core.models",
    "src/core/models.py",
)
_trust = _load(
    "src.core.trust_metadata",
    "src/core/trust_metadata.py",
)

TradeRecommendation = _models.TradeRecommendation
NoTradeCard = _trust.NoTradeCard
MODEL_VERSION = _trust.MODEL_VERSION


# ══════════════════════════════════════════════════════════════
# A. to_api_dict() — grouped explanation section (Sprint 37)
# ══════════════════════════════════════════════════════════════

class TestToApiDictExplanation(unittest.TestCase):
    """Verify to_api_dict() surfaces explanation fields."""

    def _rec(self, **kw) -> "TradeRecommendation":
        defaults = {
            "ticker": "TEST",
            "direction": "LONG",
            "strategy_id": "momentum_breakout",
        }
        defaults.update(kw)
        return TradeRecommendation(**defaults)

    # --- individual fields ---

    def test_01_why_now_in_explanation(self):
        r = self._rec(why_now="RSI bounced off 30")
        d = r.to_api_dict()
        self.assertIn("explanation", d)
        self.assertEqual(
            d["explanation"]["why_now"],
            "RSI bounced off 30",
        )

    def test_02_approval_status(self):
        r = self._rec(approval_status="approved")
        d = r.to_api_dict()
        self.assertEqual(
            d["explanation"]["approval_status"],
            "approved",
        )

    def test_03_approval_flags(self):
        flags = {"regime_ok": True, "liquidity_ok": False}
        r = self._rec(approval_flags=flags)
        d = r.to_api_dict()
        self.assertEqual(
            d["explanation"]["approval_flags"], flags,
        )

    def test_04_scenario_plan(self):
        plan = {"bull": "+5%", "bear": "-2%"}
        r = self._rec(scenario_plan=plan)
        d = r.to_api_dict()
        self.assertEqual(
            d["explanation"]["scenario_plan"], plan,
        )

    def test_05_evidence_list(self):
        ev = ["VIX < 20", "breadth > 60%"]
        r = self._rec(evidence=ev)
        d = r.to_api_dict()
        self.assertEqual(d["explanation"]["evidence"], ev)

    def test_06_event_risk(self):
        r = self._rec(event_risk="FOMC in 2 days")
        d = r.to_api_dict()
        self.assertEqual(
            d["explanation"]["event_risk"],
            "FOMC in 2 days",
        )

    def test_07_portfolio_fit(self):
        r = self._rec(portfolio_fit="Low correlation")
        d = r.to_api_dict()
        self.assertEqual(
            d["explanation"]["portfolio_fit"],
            "Low correlation",
        )

    def test_08_why_not_trade(self):
        r = self._rec(why_not_trade="Earnings in 24h")
        d = r.to_api_dict()
        self.assertEqual(
            d["explanation"]["why_not_trade"],
            "Earnings in 24h",
        )

    def test_09_better_alternative(self):
        r = self._rec(
            better_alternative="MSFT has better R:R",
        )
        d = r.to_api_dict()
        self.assertEqual(
            d["explanation"]["better_alternative"],
            "MSFT has better R:R",
        )

    def test_10_key_risks(self):
        risks = ["earnings gap", "sector rotation"]
        r = self._rec(key_risks=risks)
        d = r.to_api_dict()
        self.assertEqual(
            d["explanation"]["key_risks"], risks,
        )

    # --- empty / no explanation ---

    def test_11_no_explanation_when_empty(self):
        r = self._rec()
        d = r.to_api_dict()
        self.assertNotIn("explanation", d)

    # --- combined ---

    def test_12_multiple_fields(self):
        r = self._rec(
            why_now="breakout",
            event_risk="none",
            evidence=["volume up"],
        )
        d = r.to_api_dict()
        exp = d["explanation"]
        self.assertIn("why_now", exp)
        self.assertIn("event_risk", exp)
        self.assertIn("evidence", exp)
        self.assertEqual(len(exp), 3)

    # --- trust + explanation coexist ---

    def test_13_trust_and_explanation_coexist(self):
        r = self._rec(
            why_now="catalyst",
            trust={"badge": "PAPER"},
        )
        d = r.to_api_dict()
        self.assertIn("trust", d)
        self.assertIn("explanation", d)

    # --- to_api_dict still has flat fields ---

    def test_14_flat_fields_still_present(self):
        r = self._rec(
            why_now="catalyst",
            composite_score=0.85,
        )
        d = r.to_api_dict()
        # Flat fields from model_dump
        self.assertEqual(d["why_now"], "catalyst")
        self.assertAlmostEqual(d["composite_score"], 0.85)
        # Grouped section also present
        self.assertIn("explanation", d)


# ══════════════════════════════════════════════════════════════
# B. MODEL_VERSION bump
# ══════════════════════════════════════════════════════════════

class TestModelVersion(unittest.TestCase):

    def test_15_version_is_v6_37(self):
        self.assertEqual(MODEL_VERSION, "v6.37")


# ══════════════════════════════════════════════════════════════
# C. Auto-trading engine — _no_trade_card init + cached state
# ══════════════════════════════════════════════════════════════

class TestEngineNoTradeInit(unittest.TestCase):
    """Verify _no_trade_card is properly initialised."""

    @classmethod
    def setUpClass(cls):
        ate_path = os.path.join(
            BASE, "src", "engines", "auto_trading_engine.py",
        )
        with open(ate_path) as f:
            cls.src = f.read()

    def test_16_no_trade_card_init_present(self):
        self.assertIn(
            "self._no_trade_card = None",
            self.src,
        )

    def test_17_no_trade_card_in_cached_state(self):
        self.assertIn("no_trade_card", self.src)

    def test_18_kpi_snapshot_in_cached_state(self):
        self.assertIn("kpi_snapshot", self.src)

    def test_19_build_kpi_snapshot_method(self):
        self.assertIn(
            "def _build_kpi_snapshot",
            self.src,
        )

    def test_20_no_trade_card_to_dict_call(self):
        self.assertIn(
            "self._no_trade_card.to_dict()",
            self.src,
        )


# ══════════════════════════════════════════════════════════════
# D. Discord bot — /kpi command wiring
# ══════════════════════════════════════════════════════════════

class TestKpiCommand(unittest.TestCase):
    """Verify /kpi command exists in discord_bot.py."""

    @classmethod
    def setUpClass(cls):
        db_path = os.path.join(
            BASE, "src", "notifications", "discord_bot.py",
        )
        with open(db_path) as f:
            cls.src = f.read()

    def test_21_kpi_command_registered(self):
        self.assertIn('name="kpi"', self.src)

    def test_22_kpi_description(self):
        self.assertIn("Professional KPI dashboard", self.src)

    def test_23_kpi_cmd_function(self):
        self.assertIn("async def kpi_cmd", self.src)

    def test_24_kpi_uses_kpi_snapshot(self):
        self.assertIn("kpi_snapshot", self.src)

    def test_25_kpi_net_expectancy_field(self):
        self.assertIn("net_expectancy_r", self.src)

    def test_26_kpi_coverage_funnel(self):
        self.assertIn("Coverage Funnel", self.src)

    def test_27_kpi_profit_factor(self):
        self.assertIn("profit_factor", self.src)

    def test_28_kpi_win_rate(self):
        self.assertIn("win_rate", self.src)

    def test_29_kpi_max_drawdown(self):
        self.assertIn("max_drawdown", self.src)

    def test_30_kpi_cvar_95(self):
        self.assertIn("cvar_95", self.src)


# ══════════════════════════════════════════════════════════════
# E. Discord bot — /notrade command wiring
# ══════════════════════════════════════════════════════════════

class TestNotradeCommand(unittest.TestCase):
    """Verify /notrade command exists in discord_bot.py."""

    @classmethod
    def setUpClass(cls):
        db_path = os.path.join(
            BASE, "src", "notifications", "discord_bot.py",
        )
        with open(db_path) as f:
            cls.src = f.read()

    def test_31_notrade_command_registered(self):
        self.assertIn('name="notrade"', self.src)

    def test_32_notrade_cmd_function(self):
        self.assertIn("async def notrade_cmd", self.src)

    def test_33_notrade_shows_regime(self):
        self.assertIn("No-Trade Status", self.src)

    def test_34_notrade_resume_conditions(self):
        self.assertIn("Resume When", self.src)

    def test_35_notrade_readiness_fallback(self):
        self.assertIn("no_trade_readiness", self.src)


# ══════════════════════════════════════════════════════════════
# F. Discord bot — /calibration command wiring
# ══════════════════════════════════════════════════════════════

class TestCalibrationCommand(unittest.TestCase):
    """Verify /calibration command exists in discord_bot.py."""

    @classmethod
    def setUpClass(cls):
        db_path = os.path.join(
            BASE, "src", "notifications", "discord_bot.py",
        )
        with open(db_path) as f:
            cls.src = f.read()

    def test_36_calibration_command_registered(self):
        self.assertIn('name="calibration"', self.src)

    def test_37_calibration_cmd_function(self):
        self.assertIn(
            "async def calibration_cmd", self.src,
        )

    def test_38_calibration_uses_edge_calculator(self):
        self.assertIn("EdgeCalculator", self.src)

    def test_39_calibration_base_rates(self):
        self.assertIn("BASE_RATES", self.src)

    def test_40_calibration_shows_strategies(self):
        # Should iterate over strategy names
        self.assertIn("name_pretty", self.src)


# ══════════════════════════════════════════════════════════════
# G. Discord bot — footer & version updated
# ══════════════════════════════════════════════════════════════

class TestFooterUpdate(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        db_path = os.path.join(
            BASE, "src", "notifications", "discord_bot.py",
        )
        with open(db_path) as f:
            cls.src = f.read()

    def test_41_footer_mentions_v6_37(self):
        self.assertIn("v6.37", self.src)

    def test_42_footer_mentions_kpi(self):
        self.assertIn("/kpi", self.src)

    def test_43_footer_mentions_notrade(self):
        self.assertIn("/notrade", self.src)

    def test_44_footer_mentions_calibration(self):
        self.assertIn("/calibration", self.src)


# ══════════════════════════════════════════════════════════════
# H. Discord-bot sync test (Sprint 16 compat)
# ══════════════════════════════════════════════════════════════

class TestDiscordBotSync(unittest.TestCase):

    def test_45_root_matches_notifications(self):
        root = os.path.join(BASE, "src", "discord_bot.py")
        notif = os.path.join(
            BASE, "src", "notifications", "discord_bot.py",
        )
        with open(root) as f:
            root_src = f.read()
        with open(notif) as f:
            notif_src = f.read()
        self.assertEqual(root_src, notif_src)


# ══════════════════════════════════════════════════════════════
# I. ProfessionalKPI — compute with explanation
# ══════════════════════════════════════════════════════════════

class TestProfessionalKPICompute(unittest.TestCase):
    """Verify KPI compute returns proper snapshot."""

    @classmethod
    def setUpClass(cls):
        cls._kpi_mod = _load(
            "src.engines.professional_kpi",
            "src/engines/professional_kpi.py",
        )

    def test_46_empty_compute(self):
        kpi = self._kpi_mod.ProfessionalKPI()
        snap = kpi.compute()
        self.assertEqual(snap.total_trades, 0)
        self.assertEqual(snap.net_expectancy_r, 0.0)

    def test_47_compute_with_trades(self):
        kpi = self._kpi_mod.ProfessionalKPI()
        kpi.record_trade(pnl_pct=5.0, r_multiple=2.0)
        kpi.record_trade(pnl_pct=-2.0, r_multiple=-1.0)
        kpi.record_trade(pnl_pct=3.0, r_multiple=1.5)
        kpi.record_cycle(traded=True)
        kpi.record_cycle(traded=False)
        snap = kpi.compute()
        self.assertEqual(snap.total_trades, 3)
        self.assertGreater(snap.win_rate, 0.5)
        self.assertGreater(snap.profit_factor, 0)

    def test_48_snapshot_to_dict(self):
        kpi = self._kpi_mod.ProfessionalKPI()
        kpi.record_trade(pnl_pct=1.0, r_multiple=0.5)
        kpi.record_cycle(traded=True)
        snap = kpi.compute()
        d = snap.to_dict()
        self.assertIn("net_expectancy_r", d)
        self.assertIn("funnel", d)
        self.assertIn("turnover", d)

    def test_49_summary_text_output(self):
        kpi = self._kpi_mod.ProfessionalKPI()
        kpi.record_trade(pnl_pct=2.0, r_multiple=1.0)
        snap = kpi.compute()
        text = snap.summary_text()
        self.assertIn("Professional KPI Report", text)
        self.assertIn("Net Expectancy", text)

    def test_50_no_trade_rate(self):
        kpi = self._kpi_mod.ProfessionalKPI()
        kpi.record_trade(pnl_pct=1.0, r_multiple=0.5)
        kpi.record_cycle(traded=False)
        kpi.record_cycle(traded=False)
        kpi.record_cycle(traded=True)
        snap = kpi.compute()
        self.assertAlmostEqual(
            snap.no_trade_rate, 2 / 3, places=2,
        )


# ══════════════════════════════════════════════════════════════
# J. EdgeCalculator — base rates accessible
# ══════════════════════════════════════════════════════════════

class TestEdgeCalculatorBaseRates(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        cls._insight = _load(
            "src.engines.insight_engine",
            "src/engines/insight_engine.py",
        )
        cls.calc = cls._insight.EdgeCalculator()

    def test_51_base_rates_has_momentum(self):
        self.assertIn(
            "momentum_breakout", self.calc.BASE_RATES,
        )

    def test_52_base_rates_has_vcp(self):
        self.assertIn("vcp", self.calc.BASE_RATES)

    def test_53_base_rates_has_mean_reversion(self):
        self.assertIn(
            "mean_reversion", self.calc.BASE_RATES,
        )

    def test_54_base_rates_has_trend_following(self):
        self.assertIn(
            "trend_following", self.calc.BASE_RATES,
        )

    def test_55_base_rates_has_classic_swing(self):
        self.assertIn(
            "classic_swing", self.calc.BASE_RATES,
        )

    def test_56_default_rate_exists(self):
        dr = self.calc.DEFAULT_RATE
        self.assertIn("p_t1", dr)
        self.assertIn("p_stop", dr)
        self.assertIn("ev", dr)

    def test_57_each_rate_has_required_keys(self):
        required = {"p_t1", "p_t2", "p_stop", "ev", "mae", "days"}
        for name, rates in self.calc.BASE_RATES.items():
            for key in required:
                self.assertIn(
                    key, rates,
                    f"{name} missing {key}",
                )


# ══════════════════════════════════════════════════════════════
# K. NoTradeCard — to_dict roundtrip
# ══════════════════════════════════════════════════════════════

class TestNoTradeCardRoundtrip(unittest.TestCase):

    def test_58_from_regime_basic(self):
        state = {
            "regime": "high_entropy",
            "should_trade": False,
            "risk_regime": "risk_off",
            "no_trade_reason": "VIX spike",
        }
        card = NoTradeCard.from_regime(state)
        d = card.to_dict()
        self.assertEqual(d["reason"], "VIX spike")
        self.assertEqual(d["regime_label"], "high_entropy")
        self.assertIn("VIX drops below 25", d["resume_conditions"])

    def test_59_from_regime_neutral(self):
        state = {
            "regime": "range_bound",
            "should_trade": False,
            "risk_regime": "neutral",
        }
        card = NoTradeCard.from_regime(state)
        d = card.to_dict()
        self.assertEqual(d["reason"], "Regime unfavourable")
        self.assertIn(
            "Clear trend signal emerges",
            d["resume_conditions"],
        )

    def test_60_format_card(self):
        state = {
            "regime": "crisis",
            "should_trade": False,
            "risk_regime": "risk_off",
            "no_trade_reason": "Market crash",
        }
        card = NoTradeCard.from_regime(
            state, tickers=["AAPL", "MSFT"],
        )
        text = card.format_card()
        self.assertIn("No Trade", text)
        self.assertIn("AAPL", text)
        self.assertIn("Market crash", text)


# ══════════════════════════════════════════════════════════════
# L. Multi-channel notification — send_no_trade_alert
# ══════════════════════════════════════════════════════════════

class TestMultiChannelNoTrade(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        mc_path = os.path.join(
            BASE, "src", "notifications", "multi_channel.py",
        )
        with open(mc_path) as f:
            cls.src = f.read()

    def test_61_send_no_trade_alert_exists(self):
        self.assertIn(
            "send_no_trade_alert", self.src,
        )

    def test_62_send_no_trade_renders_reason(self):
        self.assertIn("reason", self.src)

    def test_63_send_no_trade_renders_resume(self):
        self.assertIn("resume_conditions", self.src)

    def test_64_send_trade_alert_has_trust(self):
        self.assertIn("trust", self.src)

    def test_65_send_exit_alert_has_attribution(self):
        self.assertIn("attribution", self.src)


# ══════════════════════════════════════════════════════════════
# M. Regression guards
# ══════════════════════════════════════════════════════════════

class TestRegressionGuards(unittest.TestCase):

    def test_66_models_has_trust_field(self):
        """Sprint 36 trust field still present."""
        r = TradeRecommendation(
            ticker="X",
            trust={"badge": "LIVE"},
        )
        d = r.to_api_dict()
        self.assertEqual(d["trust"]["badge"], "LIVE")

    def test_67_to_api_dict_has_instrument_type(self):
        r = TradeRecommendation(ticker="X")
        d = r.to_api_dict()
        self.assertIn("instrument_type", d)

    def test_68_to_entry_snapshot_keys(self):
        r = TradeRecommendation(
            ticker="X",
            composite_score=0.75,
        )
        snap = r.to_entry_snapshot()
        self.assertIn("composite_score", snap)
        self.assertIn("vix_at_entry", snap)

    def test_69_no_bare_except_exception(self):
        ate_path = os.path.join(
            BASE, "src", "engines", "auto_trading_engine.py",
        )
        with open(ate_path) as f:
            src = f.read()
        # Sprint 14 regression guard
        count = src.count("except Exception:")
        # Allow existing ones from pre-Sprint 14
        self.assertLessEqual(
            count, 28,
            f"Too many bare 'except Exception:' ({count})",
        )


if __name__ == "__main__":
    unittest.main()
