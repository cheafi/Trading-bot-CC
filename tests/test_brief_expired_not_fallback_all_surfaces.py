"""Brief >2d expired — never fallback language on any surface copy."""

from __future__ import annotations

from src.services.copy_safety import sanitize_for_render
from src.services.fetch_surface_state import global_truth_strip
from src.services.operator_surface import build_operator_block, build_research_surface_block
from src.services.system_truth import resolve_system_truth, typed_freshness_display


def _expired_truth():
    return resolve_system_truth(
        {
            "market_regime": {"tradeability": "WAIT", "should_trade": True},
            "filter_funnel": {"note": "brief fallback board visible"},
            "used_brief_fallback": True,
        },
        cc_header={},
        ops={},
        brief_age_days=21,
    )


def test_truth_brief_freshness_expired_not_fallback():
    truth = _expired_truth()
    assert truth["brief_freshness"] == "expired"
    assert truth["brief_expired"] is True
    assert "FALLBACK_BRIEF" not in truth["reason_codes"]


def test_typed_freshness_strip_says_expired_not_fallback():
    truth = _expired_truth()
    line = typed_freshness_display(truth)
    assert "Expired" in line
    assert "fallback" not in line.lower()


def test_global_truth_strip_no_fallback_when_expired():
    truth = _expired_truth()
    strip = global_truth_strip(truth)
    assert "Expired" in strip
    assert "fallback" not in strip.lower()


def test_operator_surfaces_no_brief_fallback_when_expired():
    truth = _expired_truth()
    for page in ("dashboard", "playbook", "agent"):
        block = build_operator_block(truth, page)
        blob = " ".join(str(block.get(k) or "") for k in ("now", "why", "allowed", "blocked", "next"))
        assert "brief fallback" not in blob.lower()
    research = build_research_surface_block(truth, surface="discovery")
    blob = " ".join(str(research.get(k) or "") for k in ("now", "blocker", "next"))
    assert "brief fallback" not in blob.lower()


def test_sanitize_for_render_expired_replaces_fallback():
    out = sanitize_for_render(
        "Using brief fallback for ranking",
        {"brief_expired": True, "brief_age_days": 21},
    )
    assert "brief fallback" not in out.lower()
    assert "expired" in out.lower()
