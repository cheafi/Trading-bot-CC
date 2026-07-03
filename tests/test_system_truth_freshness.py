"""Brief freshness — expired brief is not fallback."""

from __future__ import annotations

from src.services.system_truth import BRIEF_EXPIRE_DAYS, resolve_system_truth, typed_freshness_display


def test_brief_older_than_expire_days_is_expired_not_fallback():
    truth = resolve_system_truth(
        {
            "market_regime": {"tradeability": "WAIT", "should_trade": True},
            "used_brief_fallback": True,
            "filter_funnel": {"note": "board context: brief fallback"},
            "trust": {"source": "brief-fallback", "stale": True},
        },
        cc_header={},
        ops={},
        brief_age_days=BRIEF_EXPIRE_DAYS + 21,
    )
    assert truth["brief_freshness"] == "expired"
    assert truth["brief_freshness"] != "fallback"
    assert "BRIEF_EXPIRED" in truth["reason_codes"]
    assert "FALLBACK_BRIEF" not in truth["reason_codes"]
    line = typed_freshness_display(truth)
    assert "Expired" in line
    assert "Fallback" not in line.split("Brief:")[1].split("·")[0]
