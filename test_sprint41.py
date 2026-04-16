"""
Sprint 41 — Institutional Review Implementation:
meta-labeler, post-trade attribution, broker reconciliation,
gap-risk backtester, new API endpoints, doc naming alignment.
"""

import asyncio
import os
import sys

import pytest

sys.path.insert(0, os.path.dirname(__file__))

_loop = None


def _run(coro):
    global _loop
    if _loop is None:
        _loop = asyncio.new_event_loop()
    return _loop.run_until_complete(coro)


# ── Meta-Labeler ──────────────────────────────────────────────


class TestMetaLabeler:
    def test_import(self):
        from src.engines.meta_labeler import (
            MetaDecision,
            MetaLabeler,
            SignalContext,
        )

        assert MetaDecision.STRONG_BUY is not None

    def test_default_watch(self):
        from src.engines.meta_labeler import (
            MetaDecision,
            MetaLabeler,
            SignalContext,
        )

        ml = MetaLabeler()
        ctx = SignalContext(ticker="AAPL")
        label = ml.evaluate(ctx)
        assert label.decision in MetaDecision
        assert isinstance(label.size_multiplier, float)
        assert "composite" in label.scores

    def test_veto_spread(self):
        from src.engines.meta_labeler import (
            MetaDecision,
            MetaLabeler,
            SignalContext,
        )

        ml = MetaLabeler()
        ctx = SignalContext(ticker="ILLIQ", spread_bps=200)
        label = ml.evaluate(ctx)
        assert label.decision == MetaDecision.NO_TRADE
        assert label.size_multiplier == 0.0
        assert any("spread" in v for v in label.vetoes)

    def test_veto_earnings(self):
        from src.engines.meta_labeler import (
            MetaDecision,
            MetaLabeler,
            SignalContext,
        )

        ml = MetaLabeler()
        ctx = SignalContext(
            ticker="EARN",
            days_to_earnings=1,
        )
        label = ml.evaluate(ctx)
        assert label.decision == MetaDecision.NO_TRADE

    def test_veto_market_closed(self):
        from src.engines.meta_labeler import (
            MetaDecision,
            MetaLabeler,
            SignalContext,
        )

        ml = MetaLabeler()
        ctx = SignalContext(
            ticker="OFF",
            session_quality="off",
        )
        label = ml.evaluate(ctx)
        assert label.decision == MetaDecision.NO_TRADE

    def test_strong_buy(self):
        from src.engines.meta_labeler import (
            MetaDecision,
            MetaLabeler,
            SignalContext,
        )

        ml = MetaLabeler()
        ctx = SignalContext(
            ticker="GOOD",
            calibrated_probability=0.85,
            regime_fit=0.8,
            reliability_sample_size=100,
            uncertainty_width=0.15,
            spread_bps=5,
            avg_daily_volume=5e6,
        )
        label = ml.evaluate(ctx)
        assert label.decision == MetaDecision.STRONG_BUY
        assert label.size_multiplier > 0

    def test_to_dict(self):
        from src.engines.meta_labeler import (
            MetaLabeler,
            SignalContext,
        )

        ml = MetaLabeler()
        ctx = SignalContext(ticker="AAPL")
        d = ml.evaluate(ctx).to_dict()
        assert "ticker" in d
        assert "decision" in d
        assert "scores" in d


# ── Post-Trade Attribution ────────────────────────────────────


class TestPostTradeAttribution:
    def test_import(self):
        from src.engines.post_trade_attribution import (
            PostTradeAttribution,
            TradeRecord,
        )

        assert TradeRecord is not None

    def test_record_and_report(self):
        from src.engines.post_trade_attribution import (
            PostTradeAttribution,
            TradeRecord,
        )

        pa = PostTradeAttribution()
        pa.record_trade(
            TradeRecord(
                trade_id="t1",
                ticker="AAPL",
                strategy="momentum",
                regime="bull",
                stated_confidence=0.7,
                confidence_bucket="high",
                realized_pnl_pct=0.03,
                holding_days=5,
                exit_reason="take_profit",
            )
        )
        pa.record_trade(
            TradeRecord(
                trade_id="t2",
                ticker="TSLA",
                strategy="mean_reversion",
                regime="choppy",
                stated_confidence=0.5,
                confidence_bucket="moderate",
                realized_pnl_pct=-0.02,
                holding_days=3,
                exit_reason="stop_loss",
            )
        )
        report = pa.full_report()
        assert report["total_trades"] == 2
        assert "bull" in report["by_regime"]
        assert "momentum" in report["by_strategy"]
        assert "high" in report["by_bucket"]
        assert "calibration_check" in report

    def test_regime_heatmap(self):
        from src.engines.post_trade_attribution import (
            PostTradeAttribution,
            TradeRecord,
        )

        pa = PostTradeAttribution()
        pa.record_trade(
            TradeRecord(
                strategy="trend",
                regime="bull",
                realized_pnl_pct=0.05,
            )
        )
        hm = pa.regime_heatmap()
        assert "bull" in hm
        assert "trend" in hm["bull"]

    def test_bull_case_accuracy(self):
        from src.engines.post_trade_attribution import (
            PostTradeAttribution,
            TradeRecord,
        )

        pa = PostTradeAttribution()
        pa.record_trade(
            TradeRecord(
                bull_case_played_out=True,
                realized_pnl_pct=0.02,
            )
        )
        pa.record_trade(
            TradeRecord(
                bull_case_played_out=False,
                realized_pnl_pct=-0.01,
            )
        )
        report = pa.full_report()
        assert report["bull_case_accuracy"]["accuracy"] == 0.5


# ── Broker Reconciliation ────────────────────────────────────


class TestBrokerReconciliation:
    def test_import(self):
        from src.engines.broker_reconciliation import (
            BrokerReconciliationEngine,
            OrderState,
        )

        assert OrderState.FILLED is not None

    def test_order_lifecycle(self):
        from src.engines.broker_reconciliation import (
            BrokerReconciliationEngine,
            OrderState,
        )

        eng = BrokerReconciliationEngine()
        rec = eng.record_order(
            "o1",
            "AAPL",
            "BUY",
            100,
            150.0,
        )
        assert rec.state == OrderState.SENT
        eng.record_fill("o1", 100, 150.05)
        assert eng._orders["o1"].state == OrderState.FILLED

    def test_reconcile_ok(self):
        from src.engines.broker_reconciliation import (
            BrokerReconciliationEngine,
            ReconciliationStatus,
        )

        eng = BrokerReconciliationEngine()
        eng.record_order("o1", "AAPL", "BUY", 100)
        eng.record_fill("o1", 100, 150.0)
        status = eng.reconcile({"AAPL": 100})
        assert status == ReconciliationStatus.OK
        assert eng.can_trade()

    def test_reconcile_mismatch(self):
        from src.engines.broker_reconciliation import (
            BrokerReconciliationEngine,
            ReconciliationStatus,
        )

        eng = BrokerReconciliationEngine()
        eng.record_order("o1", "AAPL", "BUY", 100)
        eng.record_fill("o1", 100, 150.0)
        status = eng.reconcile({"AAPL": 50})
        assert status == ReconciliationStatus.MISMATCH

    def test_status_report(self):
        from src.engines.broker_reconciliation import (
            BrokerReconciliationEngine,
        )

        eng = BrokerReconciliationEngine()
        eng.record_order("o1", "AAPL", "BUY", 100)
        s = eng.status()
        assert s["total_orders"] == 1
        assert s["pending"] == 1

    def test_rejection(self):
        from src.engines.broker_reconciliation import (
            BrokerReconciliationEngine,
            OrderState,
        )

        eng = BrokerReconciliationEngine()
        eng.record_order("o1", "AAPL", "BUY", 100)
        eng.record_rejection("o1", "insufficient buying power")
        assert eng._orders["o1"].state == OrderState.REJECTED


# ── Backtester Gap Risk ───────────────────────────────────────


class TestBacktesterGapRisk:
    def test_gap_risk_param(self):
        from src.backtest.backtester import Backtester

        b = Backtester(gap_risk_pct=0.05)
        assert b.gap_risk_pct == 0.05

    def test_market_hours_param(self):
        from src.backtest.backtester import Backtester

        b = Backtester(enforce_market_hours=False)
        assert b.enforce_market_hours is False


# ── New API Endpoints ─────────────────────────────────────────


class TestNewAPIEndpointsV2:
    def test_exposure_dashboard(self):
        from src.api.main import exposure_dashboard

        result = _run(exposure_dashboard())
        assert "gross_exposure_pct" in result

    def test_meta_label(self):
        from src.api.main import meta_label_ticker

        result = _run(meta_label_ticker("AAPL"))
        assert "decision" in result
        assert "scores" in result

    def test_post_trade_report(self):
        from src.api.main import post_trade_report

        result = _run(post_trade_report())
        assert "total_trades" in result

    def test_regime_heatmap(self):
        from src.api.main import regime_heatmap

        result = _run(regime_heatmap())
        assert "heatmap" in result

    def test_broker_reconciliation(self):
        from src.api.main import broker_reconciliation_status

        result = _run(broker_reconciliation_status())
        assert "reconciliation_status" in result


# ── Doc Naming Alignment ─────────────────────────────────────


class TestDocNaming:
    def test_bot_guide_says_64(self):
        with open("docs/BOT_GUIDE.md") as f:
            first_line = f.readline()
        assert "64" in first_line

    def test_setup_guide_says_cc(self):
        with open("docs/SETUP_GUIDE.md") as f:
            content = f.read(500)
        assert "CC" in content

    def test_architecture_says_cc(self):
        with open("docs/ARCHITECTURE.md") as f:
            content = f.read(500)
        assert "CC" in content


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
