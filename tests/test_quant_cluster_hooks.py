"""Quant cluster hooks in today_insights / fetch_surface_state."""

from src.services.fetch_surface_state import QUANT_CLUSTER_MONITOR_LABELS
from src.services.today_insights import build_monitor_triggers, build_quant_cluster_hints


def test_quant_cluster_labels_present():
    assert "blocked-by-cost" in QUANT_CLUSTER_MONITOR_LABELS
    assert "deploy" in QUANT_CLUSTER_MONITOR_LABELS


def test_monitor_triggers_include_cluster():
    hints = build_quant_cluster_hints(tradeability="WAIT", best_net_score=5.0)
    triggers = build_monitor_triggers(
        market_pulse={},
        near_miss=[],
        vix=15,
        breadth=50,
        tradeability="WAIT",
        quant_cluster_hints=hints,
    )
    types = {t["type"] for t in triggers}
    assert "cluster_watch" in types
    assert "cluster_blocked_cost" in types
