"""Today payload quant cluster + near-miss gate ordering."""

from src.services.today_insights import (
    best_net_edge_from_opportunities,
    build_monitor_triggers,
    build_near_miss_candidates,
    build_quant_cluster_hints,
    _near_miss_gate_distance,
)


def test_best_net_edge_picks_highest_after_cost():
    rows = [
        {"ticker": "A", "score": 8.0},
        {"ticker": "B", "score": 7.5, "extended": True},
    ]
    best = best_net_edge_from_opportunities(rows)
    assert best is not None
    assert best >= 6.0


def test_near_miss_gate_distance_prefers_fewer_gaps():
    a = {"gaps": ["timing", "thesis"], "score": 8.0, "final_conf": 0.7}
    b = {"gaps": ["timing"], "score": 7.0, "final_conf": 0.6}
    assert _near_miss_gate_distance(b) < _near_miss_gate_distance(a)


def test_monitor_triggers_near_miss_includes_distance():
    near = [
        {
            "ticker": "XYZ",
            "upgrade_trigger": "Reclaim entry",
            "distance_to_pass": "timing +5pts",
        }
    ]
    triggers = build_monitor_triggers(
        market_pulse={},
        near_miss=near,
        vix=18,
        breadth=55,
        tradeability="WAIT",
        quant_cluster_hints=build_quant_cluster_hints(
            tradeability="WAIT", best_net_score=5.2
        ),
    )
    nm = [t for t in triggers if t["type"] == "near_miss"][0]
    assert "XYZ" in nm["label"]
    assert "timing +5pts" in nm["detail"]
    assert nm.get("monitoring_only") is True
    assert "cluster_watch" in {t["type"] for t in triggers}


def test_fetch_surface_state_single_playbook_monitor_helper():
    import inspect

    from src.services import fetch_surface_state as fss

    defs = [
        n
        for n, obj in inspect.getmembers(fss)
        if n == "playbook_what_to_monitor_line" and inspect.isfunction(obj)
    ]
    assert len(defs) == 1
    line = fss.playbook_what_to_monitor_line(
        wait_day=True, top_symbol="aapl", near_miss_count=2
    )
    assert "Monitor only" in line
    assert "no deploy authority" in line


def test_build_near_miss_candidates_importable():
    assert callable(build_near_miss_candidates)
