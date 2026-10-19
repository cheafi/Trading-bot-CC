"""Daily decision engine — TradeDecision contract and ranking."""

from __future__ import annotations

from src.core.trade_decision import DataFreshness, ExecutionReadiness
from src.engines.daily_decision_engine import DailyDecisionEngine


def test_pipeline_no_candidates_no_trade() -> None:
    eng = DailyDecisionEngine()
    out = eng.build([], regime={"regime": "NEUTRAL", "should_trade": True})
    assert out.no_trade is True
    assert out.decisions == []
    assert "NO TRADE" in out.no_trade_summary.upper() or "No candidates" in out.no_trade_summary


def test_pipeline_ranks_and_separates_confidence_dimensions() -> None:
    eng = DailyDecisionEngine()
    regime = {
        "regime": "RISK_ON",
        "should_trade": True,
        "risk_on_uptrend": 0.7,
        "neutral_range": 0.2,
        "risk_off_downtrend": 0.1,
        "entropy": 0.4,
    }
    candidates = [
        {
            "ticker": "AAPL",
            "direction": "LONG",
            "strategy_id": "momentum",
            "score": 0.72,
            "confidence": 72,
            "entry_price": 100.0,
            "stop_price": 95.0,
            "target_price": 110.0,
            "risk_reward_ratio": 2.0,
            "entry_logic": "Breakout above pivot",
            "why_now": "RS leader",
        },
        {
            "ticker": "XYZ",
            "direction": "LONG",
            "strategy_id": "momentum",
            "score": 0.4,
            "entry_price": 0,
            "stop_price": 0,
        },
    ]
    out = eng.build(candidates, regime=regime)
    assert len(out.decisions) >= 1
    assert len(out.top_3) <= 3
    top = out.decisions[0]
    assert top.symbol == "AAPL"
    assert top.signal_quality >= 0
    assert top.evidence_quality > 0.5
    assert top.data_freshness == DataFreshness.VERIFIED
    weak = next(d for d in out.decisions if d.symbol == "XYZ")
    assert weak.data_freshness == DataFreshness.UNVERIFIED
    assert weak.execution_readiness in (
        ExecutionReadiness.BLOCKED,
        ExecutionReadiness.NOT_EXECUTABLE,
    )
    assert weak.requires_approval is True


def test_no_trade_when_regime_blocks() -> None:
    eng = DailyDecisionEngine()
    regime = {"regime": "RISK_OFF", "should_trade": False, "entropy": 0.95}
    candidates = [
        {
            "ticker": "MSFT",
            "entry_price": 400,
            "stop_price": 390,
            "target_price": 420,
            "score": 0.8,
            "confidence": 80,
            "strategy_id": "breakout",
        }
    ]
    out = eng.build(candidates, regime=regime)
    assert all(d.action != "BUY" or d.execution_readiness != ExecutionReadiness.REQUIRES_APPROVAL for d in out.decisions)
