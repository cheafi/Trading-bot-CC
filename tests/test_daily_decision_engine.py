"""Daily decision engine — TradeDecision contract, safety gates, ranking."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone

from src.core.trade_decision import (
    DataFreshness,
    ExecutionReadiness,
    assess_trade_eligibility,
    normalize_regime_state,
    trade_decision_from_recommendation,
)
from src.core.models import TradeRecommendation
from src.engines.daily_decision_engine import DailyDecisionEngine


def _tradeable_regime() -> dict:
    return {
        "regime": "RISK_ON",
        "should_trade": True,
        "risk_on_uptrend": 0.7,
        "neutral_range": 0.2,
        "risk_off_downtrend": 0.1,
        "entropy": 0.4,
    }


def _verified_quote_fields(*, minutes_ago: float = 5.0) -> dict:
    ts = (
        datetime.now(timezone.utc) - timedelta(minutes=minutes_ago)
    ).isoformat().replace("+00:00", "Z")
    return {
        "price_timestamp": ts,
        "price_source": "yfinance_daily",
        "trust": {"mode": "LIVE", "freshness": "REAL_TIME", "source": "market_data"},
    }


def _base_candidate(**overrides) -> dict:
    row = {
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
        **_verified_quote_fields(),
    }
    row.update(overrides)
    return row


def test_pipeline_no_candidates_no_trade() -> None:
    eng = DailyDecisionEngine()
    out = eng.build([], regime={"regime": "NEUTRAL", "should_trade": True})
    assert out.no_trade is True
    assert out.decisions == []
    assert out.top_3 == []
    assert "NO TRADE" in out.no_trade_summary.upper() or "No candidates" in out.no_trade_summary


def test_missing_regime_fail_closed() -> None:
    norm = normalize_regime_state(None)
    assert norm["regime"] == "UNKNOWN"
    assert norm["should_trade"] is False
    eng = DailyDecisionEngine()
    out = eng.build([_base_candidate()], regime=None)
    assert out.regime_should_trade is False
    assert out.no_trade is True
    assert all(not d.is_actionable for d in out.decisions)


def test_missing_should_trade_defaults_false() -> None:
    eng = DailyDecisionEngine()
    out = eng.build([_base_candidate()], regime={"regime": "NEUTRAL"})
    assert out.regime_should_trade is False
    assert out.no_trade is True
    d = out.decisions[0]
    assert d.action != "BUY" or not d.is_actionable


def test_happy_path_verified_timestamped_quote() -> None:
    eng = DailyDecisionEngine()
    candidates = [
        _base_candidate(),
        {
            "ticker": "XYZ",
            "direction": "LONG",
            "strategy_id": "momentum",
            "score": 0.4,
            "entry_price": 0,
            "stop_price": 0,
        },
    ]
    out = eng.build(candidates, regime=_tradeable_regime())
    aapl = next(d for d in out.decisions if d.symbol == "AAPL")
    assert aapl.data_freshness == DataFreshness.VERIFIED
    assert aapl.action == "BUY"
    assert aapl.execution_readiness == ExecutionReadiness.REQUIRES_APPROVAL
    assert aapl.is_actionable
    assert aapl.quote_timestamp is not None
    assert aapl.quote_source is not None
    assert aapl.take_profit_1 == 110.0
    assert aapl.risk_reward_ratio == 2.0
    assert len(out.top_3) == 1
    assert out.no_trade is False
    weak = next(d for d in out.decisions if d.symbol == "XYZ")
    assert weak.data_freshness == DataFreshness.UNVERIFIED
    assert weak.action != "BUY"
    assert weak in out.watchlist


def test_hardcoded_price_without_provenance_not_verified() -> None:
    rec = TradeRecommendation.from_dict(
        {
            "ticker": "MSFT",
            "entry_price": 400,
            "stop_price": 390,
            "target_price": 420,
            "score": 0.9,
        }
    )
    rec.stop_price = 390.0
    rec.trade_decision = True
    elig = assess_trade_eligibility(rec, _tradeable_regime())
    assert elig.freshness == DataFreshness.UNVERIFIED
    assert elig.action != "BUY"


def test_missing_quote_timestamp() -> None:
    row = _base_candidate()
    row.pop("price_timestamp")
    eng = DailyDecisionEngine()
    d = eng.build([row], regime=_tradeable_regime()).decisions[0]
    assert d.data_freshness == DataFreshness.UNVERIFIED
    assert d.action != "BUY"
    assert d.execution_readiness == ExecutionReadiness.BLOCKED


def test_missing_quote_source() -> None:
    row = _base_candidate(price_source="", trust={})
    eng = DailyDecisionEngine()
    d = eng.build([row], regime=_tradeable_regime()).decisions[0]
    assert d.data_freshness == DataFreshness.UNVERIFIED
    assert d.action != "BUY"


def test_expired_quote_stale() -> None:
    row = _base_candidate(**_verified_quote_fields(minutes_ago=200.0))
    eng = DailyDecisionEngine()
    d = eng.build([row], regime=_tradeable_regime()).decisions[0]
    assert d.data_freshness == DataFreshness.STALE
    assert d.action != "BUY"


def test_future_quote_unverified() -> None:
    future = (datetime.now(timezone.utc) + timedelta(days=1)).isoformat().replace(
        "+00:00", "Z"
    )
    row = _base_candidate(price_timestamp=future)
    eng = DailyDecisionEngine()
    d = eng.build([row], regime=_tradeable_regime()).decisions[0]
    assert d.data_freshness == DataFreshness.UNVERIFIED
    assert d.action != "BUY"


def test_invalid_stop_geometry_blocks_actionable() -> None:
    row = _base_candidate(stop_price=105.0)
    eng = DailyDecisionEngine()
    d = eng.build([row], regime=_tradeable_regime()).decisions[0]
    assert d.action != "BUY"
    assert not d.is_actionable


def test_invalid_target_blocks_actionable() -> None:
    row = _base_candidate(target_price=99.0)
    eng = DailyDecisionEngine()
    d = eng.build([row], regime=_tradeable_regime()).decisions[0]
    assert d.action != "BUY"


def test_stale_strong_scoring_candidate_not_buy() -> None:
    row = _base_candidate(score=0.95, confidence=95, data_stale=True)
    eng = DailyDecisionEngine()
    d = eng.build([row], regime=_tradeable_regime()).decisions[0]
    assert d.data_freshness == DataFreshness.STALE
    assert d.action != "BUY"
    assert d.signal_quality >= 0.3


def test_all_blocked_no_trade() -> None:
    eng = DailyDecisionEngine()
    out = eng.build(
        [
            _base_candidate(ticker="A", price_timestamp=None, price_source=None, trust={}),
            _base_candidate(ticker="B", price_timestamp=None, price_source=None, trust={}),
        ],
        regime=_tradeable_regime(),
    )
    assert out.no_trade is True
    assert out.top_3 == []
    assert len(out.watchlist) == len(out.decisions)


def test_two_qualifying_exactly_two_top() -> None:
    eng = DailyDecisionEngine()
    out = eng.build(
        [
            _base_candidate(ticker="AAA"),
            _base_candidate(ticker="BBB", score=0.68, confidence=68),
        ],
        regime=_tradeable_regime(),
    )
    actionable = [d for d in out.decisions if d.is_actionable]
    assert len(actionable) == 2
    assert len(out.top_3) == 2
    assert out.no_trade is False


def test_suppressed_cannot_become_buy() -> None:
    row = _base_candidate()
    row["suppression_reason"] = "manual_hold"
    rec = TradeRecommendation.from_dict(row)
    rec.suppression_reason = "manual_hold"
    rec.trade_decision = True
    d = trade_decision_from_recommendation(rec, regime=_tradeable_regime())
    assert d.action == "BLOCKED"
    assert d.action != "BUY"


def test_no_trade_when_regime_blocks() -> None:
    eng = DailyDecisionEngine()
    regime = {"regime": "RISK_OFF", "should_trade": False, "entropy": 0.95}
    out = eng.build([_base_candidate()], regime=regime)
    assert out.no_trade is True
    assert all(not d.is_actionable for d in out.decisions)


def test_buy_and_readiness_share_eligibility() -> None:
    """Displayed BUY must match REQUIRES_APPROVAL readiness."""
    eng = DailyDecisionEngine()
    for d in eng.build([_base_candidate()], regime=_tradeable_regime()).decisions:
        if d.action == "BUY":
            assert d.execution_readiness == ExecutionReadiness.REQUIRES_APPROVAL
            assert d.data_freshness == DataFreshness.VERIFIED
        if d.execution_readiness == ExecutionReadiness.REQUIRES_APPROVAL:
            assert d.action == "BUY"
