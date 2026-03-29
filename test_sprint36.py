"""
Sprint 36 tests — Trust Layer.

New module:
  src/core/trust_metadata.py — TrustBadge, FreshnessLevel,
    ContradictionLevel, ConfidenceTier, PnLBreakdown,
    TradeAttribution, NoTradeCard, TrustMetadata

Wiring changes:
  src/core/models.py               — trust field on TradeRecommendation
  src/engines/auto_trading_engine.py — trust on entry/exit cards,
                                        attribution on close, no-trade card
  src/notifications/multi_channel.py — enhanced entry/exit/no-trade cards

30 new tests.
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


def _load(name, path):
    spec = importlib.util.spec_from_file_location(
        name, os.path.join(BASE, path),
    )
    mod = importlib.util.module_from_spec(spec)
    sys.modules[name] = mod
    spec.loader.exec_module(mod)
    return mod


_tm_mod = _load(
    "src.core.trust_metadata",
    "src/core/trust_metadata.py",
)

TrustBadge = _tm_mod.TrustBadge
FreshnessLevel = _tm_mod.FreshnessLevel
ContradictionLevel = _tm_mod.ContradictionLevel
ConfidenceTier = _tm_mod.ConfidenceTier
PnLBreakdown = _tm_mod.PnLBreakdown
TradeAttribution = _tm_mod.TradeAttribution
NoTradeCard = _tm_mod.NoTradeCard
TrustMetadata = _tm_mod.TrustMetadata
MODEL_VERSION = _tm_mod.MODEL_VERSION


# ═════════════════════════════════════════════════════════
#  A. TrustBadge enum
# ═════════════════════════════════════════════════════════

class TestTrustBadge(unittest.TestCase):
    """A1-A2: Badge values and serialization."""

    def test_badge_values(self):
        self.assertEqual(TrustBadge.LIVE.value, "LIVE")
        self.assertEqual(TrustBadge.PAPER.value, "PAPER")
        self.assertEqual(TrustBadge.BACKTEST.value, "BACKTEST")
        self.assertEqual(TrustBadge.RESEARCH.value, "RESEARCH")

    def test_badge_from_string(self):
        b = TrustBadge("LIVE")
        self.assertEqual(b, TrustBadge.LIVE)


# ═════════════════════════════════════════════════════════
#  B. FreshnessLevel classification
# ═════════════════════════════════════════════════════════

class TestFreshnessClassification(unittest.TestCase):
    """B1-B3: Freshness classification from age."""

    def test_fresh(self):
        level = TrustMetadata.classify_freshness(5)
        self.assertEqual(level, FreshnessLevel.FRESH)

    def test_aging(self):
        level = TrustMetadata.classify_freshness(60)
        self.assertEqual(level, FreshnessLevel.AGING)

    def test_stale(self):
        level = TrustMetadata.classify_freshness(180)
        self.assertEqual(level, FreshnessLevel.STALE)


# ═════════════════════════════════════════════════════════
#  C. ConfidenceTier classification
# ═════════════════════════════════════════════════════════

class TestConfidenceTier(unittest.TestCase):
    """C1-C3: Confidence tier from score."""

    def test_high(self):
        tier = TrustMetadata.classify_confidence(85)
        self.assertEqual(tier, ConfidenceTier.HIGH)

    def test_medium(self):
        tier = TrustMetadata.classify_confidence(60)
        self.assertEqual(tier, ConfidenceTier.MEDIUM)

    def test_low(self):
        tier = TrustMetadata.classify_confidence(30)
        self.assertEqual(tier, ConfidenceTier.LOW)


# ═════════════════════════════════════════════════════════
#  D. PnLBreakdown
# ═════════════════════════════════════════════════════════

class TestPnLBreakdown(unittest.TestCase):
    """D1-D5: PnL breakdown decomposition."""

    def test_from_trade_basic(self):
        pnl = PnLBreakdown.from_trade(
            gross_pnl_pct=2.50,
            fees_pct=0.10,
            slippage_pct=0.05,
        )
        self.assertAlmostEqual(pnl.net_pnl_pct, 2.35, places=2)
        self.assertTrue(pnl.is_win)

    def test_loss_trade(self):
        pnl = PnLBreakdown.from_trade(
            gross_pnl_pct=-1.50,
            fees_pct=0.10,
            slippage_pct=0.05,
        )
        self.assertAlmostEqual(pnl.net_pnl_pct, -1.65, places=2)
        self.assertFalse(pnl.is_win)

    def test_to_dict(self):
        pnl = PnLBreakdown.from_trade(2.0, 0.1, 0.05)
        d = pnl.to_dict()
        self.assertIn("gross_pnl_pct", d)
        self.assertIn("net_pnl_pct", d)
        self.assertIn("fees_pct", d)
        self.assertIn("is_win", d)

    def test_summary_line(self):
        pnl = PnLBreakdown.from_trade(2.0, 0.1, 0.05)
        line = pnl.summary_line()
        self.assertIn("Gross", line)
        self.assertIn("Net", line)
        self.assertIn("fees", line)
        self.assertIn("slip", line)

    def test_auto_net_calculation(self):
        """net_pnl_pct is auto-computed in __post_init__."""
        pnl = PnLBreakdown(
            gross_pnl_pct=3.0,
            fees_pct=0.2,
            slippage_pct=0.1,
        )
        self.assertAlmostEqual(pnl.net_pnl_pct, 2.7, places=1)


# ═════════════════════════════════════════════════════════
#  E. TradeAttribution
# ═════════════════════════════════════════════════════════

class TestTradeAttribution(unittest.TestCase):
    """E1-E5: Trade attribution auto-generation."""

    def test_winning_trade_attribution(self):
        attr = TradeAttribution.from_closed_trade(
            pnl_pct=2.0,
            exit_reason="target_hit",
            regime_at_entry="risk_on",
            regime_at_exit="risk_on",
            direction="LONG",
        )
        self.assertTrue(attr.signal_correct)
        self.assertTrue(attr.regime_correct)
        self.assertGreater(len(attr.what_worked), 0)

    def test_losing_trade_attribution(self):
        attr = TradeAttribution.from_closed_trade(
            pnl_pct=-1.5,
            exit_reason="stop_loss",
            regime_at_entry="risk_on",
            regime_at_exit="risk_off",
            direction="LONG",
        )
        self.assertFalse(attr.signal_correct)
        self.assertFalse(attr.regime_correct)
        self.assertGreater(len(attr.what_failed), 0)
        # Should mention regime shift
        failed_text = " ".join(attr.what_failed)
        self.assertIn("Regime", failed_text)

    def test_time_stop_attribution(self):
        attr = TradeAttribution.from_closed_trade(
            pnl_pct=0.2,
            exit_reason="time_stop",
            direction="LONG",
        )
        failed_text = " ".join(attr.what_failed)
        self.assertIn("Timed out", failed_text)

    def test_to_dict(self):
        attr = TradeAttribution.from_closed_trade(
            pnl_pct=1.0, exit_reason="tp1",
        )
        d = attr.to_dict()
        self.assertIn("what_worked", d)
        self.assertIn("what_failed", d)
        self.assertIn("regime_correct", d)

    def test_summary_lines(self):
        attr = TradeAttribution.from_closed_trade(
            pnl_pct=2.0,
            exit_reason="target_hit",
            regime_at_entry="risk_on",
            regime_at_exit="risk_on",
        )
        text = attr.summary_lines()
        self.assertIn("✅", text)

    def test_exit_capture_quality(self):
        """Measures how much of the target move was captured."""
        attr = TradeAttribution.from_closed_trade(
            pnl_pct=3.0,
            exit_reason="tp1",
            entry_price=100.0,
            exit_price=103.0,
            target_price=105.0,
            direction="LONG",
        )
        # 3/5 = 60% capture → exit_optimal
        self.assertTrue(attr.exit_optimal)


# ═════════════════════════════════════════════════════════
#  F. NoTradeCard
# ═════════════════════════════════════════════════════════

class TestNoTradeCard(unittest.TestCase):
    """F1-F4: No-trade card generation."""

    def test_from_regime_risk_off(self):
        regime = {
            "should_trade": False,
            "regime": "risk_off_downtrend",
            "risk_regime": "risk_off",
            "no_trade_reason": "VIX crisis",
        }
        card = NoTradeCard.from_regime(regime)
        self.assertEqual(card.reason, "VIX crisis")
        self.assertEqual(card.regime_label, "risk_off_downtrend")
        self.assertGreater(len(card.resume_conditions), 0)

    def test_from_regime_no_reason(self):
        regime = {"should_trade": False, "regime": "unknown"}
        card = NoTradeCard.from_regime(regime)
        self.assertEqual(card.reason, "Regime unfavourable")

    def test_format_card(self):
        card = NoTradeCard(
            reason="High entropy",
            regime_label="neutral_range",
            resume_conditions=["VIX drops below 25"],
        )
        text = card.format_card()
        self.assertIn("No Trade", text)
        self.assertIn("High entropy", text)
        self.assertIn("Resume when", text)

    def test_to_dict(self):
        card = NoTradeCard(reason="test")
        d = card.to_dict()
        self.assertIn("reason", d)
        self.assertIn("resume_conditions", d)
        self.assertIn("timestamp", d)


# ═════════════════════════════════════════════════════════
#  G. TrustMetadata
# ═════════════════════════════════════════════════════════

class TestTrustMetadata(unittest.TestCase):
    """G1-G6: TrustMetadata construction and serialization."""

    def test_for_entry(self):
        meta = TrustMetadata.for_entry(
            badge=TrustBadge.LIVE,
            confidence=80,
            source_count=3,
            data_age_minutes=5,
            regime_label="risk_on_uptrend",
        )
        self.assertEqual(meta.badge, TrustBadge.LIVE)
        self.assertEqual(meta.freshness, FreshnessLevel.FRESH)
        self.assertEqual(meta.confidence_tier, ConfidenceTier.HIGH)
        self.assertEqual(meta.source_count, 3)

    def test_for_exit(self):
        pnl = PnLBreakdown.from_trade(2.0, 0.1, 0.05)
        attr = TradeAttribution.from_closed_trade(
            pnl_pct=2.0, exit_reason="tp1",
        )
        meta = TrustMetadata.for_exit(
            badge=TrustBadge.PAPER,
            pnl=pnl,
            attribution=attr,
        )
        self.assertEqual(meta.badge, TrustBadge.PAPER)
        self.assertIsNotNone(meta.pnl)
        self.assertIsNotNone(meta.attribution)

    def test_to_dict(self):
        meta = TrustMetadata.for_entry(
            badge=TrustBadge.LIVE,
            confidence=70,
        )
        d = meta.to_dict()
        self.assertEqual(d["badge"], "LIVE")
        self.assertIn("freshness", d)
        self.assertIn("model_version", d)
        self.assertIn("confidence_tier", d)

    def test_to_dict_with_pnl(self):
        pnl = PnLBreakdown.from_trade(1.5, 0.1, 0.05)
        meta = TrustMetadata.for_exit(pnl=pnl)
        d = meta.to_dict()
        self.assertIn("pnl", d)
        self.assertIn("net_pnl_pct", d["pnl"])

    def test_badge_emoji(self):
        meta = TrustMetadata(badge=TrustBadge.LIVE)
        self.assertIn("LIVE", meta.badge_emoji())
        meta2 = TrustMetadata(badge=TrustBadge.PAPER)
        self.assertIn("PAPER", meta2.badge_emoji())

    def test_header_line(self):
        meta = TrustMetadata.for_entry(
            badge=TrustBadge.LIVE,
            confidence=80,
            source_count=2,
            regime_label="risk_on",
        )
        header = meta.header_line()
        self.assertIn("LIVE", header)
        self.assertIn("Sources: 2", header)
        self.assertIn("risk_on", header)

    def test_footer_line(self):
        meta = TrustMetadata(
            badge=TrustBadge.PAPER,
            data_age_minutes=10,
        )
        footer = meta.footer_line()
        self.assertIn("PAPER", footer)
        self.assertIn("10m ago", footer)

    def test_model_version(self):
        meta = TrustMetadata()
        self.assertEqual(meta.model_version, MODEL_VERSION)
        self.assertTrue(meta.model_version.startswith("v"))


# ═════════════════════════════════════════════════════════
#  H. Wiring — source code inspection
# ═════════════════════════════════════════════════════════

class TestAutoTradingEngineWiring(unittest.TestCase):
    """H1-H4: Verify Sprint 36 wiring in source."""

    @classmethod
    def setUpClass(cls):
        ate_path = os.path.join(
            BASE, "src", "engines", "auto_trading_engine.py",
        )
        with open(ate_path) as f:
            cls.src = f.read()

    def test_import_trust_metadata(self):
        self.assertIn(
            "from src.core.trust_metadata import",
            self.src,
        )

    def test_trust_on_entry(self):
        self.assertIn(
            "TrustMetadata.for_entry(",
            self.src,
        )

    def test_trust_on_exit(self):
        self.assertIn(
            "TrustMetadata.for_exit(",
            self.src,
        )

    def test_attribution_on_close(self):
        self.assertIn(
            "TradeAttribution.from_closed_trade(",
            self.src,
        )

    def test_pnl_breakdown_on_close(self):
        self.assertIn(
            "PnLBreakdown.from_trade(",
            self.src,
        )

    def test_no_trade_card(self):
        self.assertIn(
            "NoTradeCard.from_regime(",
            self.src,
        )

    def test_trust_field_in_entry_dict(self):
        self.assertIn(
            '"trust": rec.trust',
            self.src,
        )


class TestModelsWiring(unittest.TestCase):
    """H5-H6: Verify trust field in models."""

    @classmethod
    def setUpClass(cls):
        models_path = os.path.join(
            BASE, "src", "core", "models.py",
        )
        with open(models_path) as f:
            cls.src = f.read()

    def test_trust_field_exists(self):
        self.assertIn(
            "trust: Dict[str, Any]",
            self.src,
        )

    def test_trust_in_api_dict(self):
        self.assertIn(
            'd["trust"] = self.trust',
            self.src,
        )


class TestMultiChannelWiring(unittest.TestCase):
    """H7-H8: Verify enhanced notification cards."""

    @classmethod
    def setUpClass(cls):
        mc_path = os.path.join(
            BASE, "src", "notifications", "multi_channel.py",
        )
        with open(mc_path) as f:
            cls.src = f.read()

    def test_exit_has_attribution(self):
        self.assertIn("what_worked", self.src)
        self.assertIn("what_failed", self.src)

    def test_exit_has_pnl_breakdown(self):
        self.assertIn("gross_pnl_pct", self.src)
        self.assertIn("net_pnl_pct", self.src)

    def test_no_trade_alert(self):
        self.assertIn("send_no_trade_alert", self.src)


if __name__ == "__main__":
    unittest.main()
