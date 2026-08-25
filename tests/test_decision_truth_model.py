"""Tests for institutional decision truth model."""

from src.engines.decision_mapper import Decision
from src.services.decision_truth_model import (
    build_honest_funnel,
    build_pilot_explanations,
    compute_honest_tradeability,
    refine_action,
)


class _Conf:
    def __init__(self, **kw):
        self.final = kw.get("final", 0.5)
        self.thesis = kw.get("thesis", 0.5)
        self.timing = kw.get("timing", 0.5)
        self.execution = kw.get("execution", 0.5)
        self.data = kw.get("data", 0.5)


class _Fit:
    final_score = 6.2
    grade = "C"


class _Decision:
    action = "PILOT"
    rationale = "test"
    risk_reward = 2.0
    invalidation = ""
    entry_trigger = ""
    why_pilot = ""
    upgrade_to_trade = ""
    downgrade_to_watch_avoid = ""


class _Sector:
    leader_status = type("L", (), {"value": "LEADER"})()
    sector_bucket = type("B", (), {"value": "HIGH_GROWTH"})()


class _Pipeline:
    signal = {
        "ticker": "WEAK",
        "entry_price": 10,
        "stop_price": 9,
        "target_price": 12,
        "risk_reward": 2.0,
        "score": 6.2,
    }
    confidence = _Conf(final=0.42, thesis=0.4, timing=0.42, execution=0.5, data=0.5)
    fit = _Fit()
    decision = _Decision()


class _CR:
    pipeline = _Pipeline()


def test_mediocre_setup_downgrades_pilot_to_watch():
    assert refine_action(_CR()) == "WATCH"


def test_funnel_separates_raw_scanner_from_council():
    funnel = build_honest_funnel(
        universe=100,
        scanned=[{"score": 8.5}, {"score": 8.1}],
        council_results=[],
    )
    assert funnel["raw_scanner_above_8"] == 2
    assert funnel["high_conviction_above_8"] == 0


def test_pilot_explanations_without_decision_invalidation_field():
    """Sector Decision has no invalidation — must read explanation/signal."""
    expl = type("Expl", (), {"invalidation": "Close below $9.50"})()
    pr = type(
        "PR",
        (),
        {
            "signal": {"ticker": "TEST", "risk_reward": 2.2},
            "decision": Decision(action="PILOT", risk_reward=2.2),
            "confidence": _Conf(
                final=0.72,
                thesis=0.68,
                timing=0.58,
                execution=0.55,
                data=0.5,
            ),
            "fit": type("F", (), {"final_score": 7.8})(),
            "explanation": expl,
        },
    )()
    cr = type("CR", (), {"pipeline": pr})()
    out = build_pilot_explanations(cr)
    assert "invalidation" in out["downgrade_to_watch_avoid"].lower() or "$9.50" in str(out)


def test_strong_tradeability_requires_execution_ready():
    assert (
        compute_honest_tradeability(
            should_trade=True,
            execution_ready=1,
            pilot_ready=0,
            council_high_8=5,
            macro="Supportive",
            opportunity="Mixed",
        )
        == "TRADE"
    )
    assert (
        compute_honest_tradeability(
            should_trade=True,
            execution_ready=0,
            pilot_ready=0,
            council_high_8=10,
            macro="Supportive",
            opportunity="Weak",
        )
        == "WAIT"
    )
