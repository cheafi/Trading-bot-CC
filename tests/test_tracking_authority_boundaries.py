"""Authority-boundary guard tests for the new tracking surfaces.

These enforce the non-negotiable rule: tracking / cohort / regime-timeline
surfaces are research-only and can NEVER authorize a deploy, upgrade
tradeability, or override a WAIT board. If any of these fail, an upgrade has
leaked deploy authority onto a research surface.
"""

from __future__ import annotations

from src.services.market_regime_tracker import (
    MarketRegimeTracker,
    build_regime_timeline_context,
)
from src.services.signal_provenance import (
    SIGNAL_REGIME_TIMELINE,
    SIGNAL_SIGNAL_COHORT,
    assert_no_deploy_from_signals,
    authority_ceiling,
    may_authorize_deploy,
    quant_authority_cannot,
)
from src.services.signal_tracker import SignalTracker, build_signal_tracking_context
from src.services.surface_authority import AUTHORITY_RESEARCH


def test_new_signal_types_are_research_only():
    assert authority_ceiling(SIGNAL_SIGNAL_COHORT) == AUTHORITY_RESEARCH
    assert authority_ceiling(SIGNAL_REGIME_TIMELINE) == AUTHORITY_RESEARCH


def test_new_signal_types_cannot_deploy():
    assert may_authorize_deploy(SIGNAL_SIGNAL_COHORT) is False
    assert may_authorize_deploy(SIGNAL_REGIME_TIMELINE) is False


def test_cannot_lists_block_deploy_and_override():
    for st in (SIGNAL_SIGNAL_COHORT, SIGNAL_REGIME_TIMELINE):
        cannot = quant_authority_cannot(st)
        assert "authorize_deploy" in cannot
        assert "override_wait" in cannot


def test_signal_tracking_context_is_non_authoritative(tmp_path):
    trk = SignalTracker(path=str(tmp_path / "ledger.jsonl"))
    trk.record_signal(ticker="A", date="d", strategy_family="b")
    ctx = build_signal_tracking_context(trk)
    assert ctx["authority_ceiling"] == AUTHORITY_RESEARCH
    assert ctx["provenance"]["deploy_from_signal_alone"] is False
    assert ctx["provenance"]["page_gate_required"] is True
    assert_no_deploy_from_signals([ctx])


def test_regime_timeline_context_is_non_authoritative(tmp_path):
    trk = MarketRegimeTracker(path=str(tmp_path / "regime.jsonl"))
    trk.record_snapshot(
        date="d1", trend="UP", tradeability="GO",
        index_change_pct=0.5, vix=18.0, breadth=55.0,
    )
    ctx = build_regime_timeline_context(trk)
    assert ctx["authority_ceiling"] == AUTHORITY_RESEARCH
    assert ctx["provenance"]["deploy_from_signal_alone"] is False
    assert ctx["provenance"].get("downgrade_only") is True
    assert_no_deploy_from_signals([ctx])
