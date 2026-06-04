"""Pass 2 — Today mission quant clusters + exec diagnostic + playbook decay line."""

from __future__ import annotations

from pathlib import Path

from src.services.cost_adjusted_ranker import rank_single_row
from src.services.fetch_surface_state import (
    today_execution_readiness_diagnostic,
    today_mission_quant_cluster_lines,
)
from src.services.strategy_validity import (
    FLAG_DECAY,
    STRATEGY_DECAY_DOWNGRADE_COPY,
    resolve_strategy_decay_line,
)
from src.services.today_insights import build_quant_cluster_hints

ROOT = Path(__file__).resolve().parents[1]
INDEX_HTML = ROOT / "src" / "api" / "templates" / "index.html"
CC_HELPERS = ROOT / "src" / "api" / "static" / "cc-helpers.js"
DEPLOY_PARTIAL = ROOT / "src/api/templates/cc/partials/deploy_surfaces.html"


def test_today_mission_quant_cluster_lines_monitor_only():
    hints = build_quant_cluster_hints(tradeability="WAIT", best_net_score=5.0)
    lines = today_mission_quant_cluster_lines(hints)
    assert lines
    assert all("monitor" in ln.lower() or "blocked" in ln.lower() or "near-miss" in ln.lower() for ln in lines)
    assert not any("deploy authority" in ln.lower() and "not" not in ln.lower() for ln in lines)


def test_execution_readiness_diagnostic_gaps():
    line = today_execution_readiness_diagnostic(
        {
            "sub_status": {
                "broker_transport": "down",
                "session_auth": "inactive",
                "handoff_readiness": "blocked",
                "bracket_readiness": "draft",
                "engine": "off",
            },
            "degraded_reasons": ["Gateway reachable — not logged in"],
        }
    )
    assert "Exec diagnostic" in line
    assert "not deploy authority" in line
    assert "transport down" in line


def test_execution_readiness_diagnostic_empty_when_ready():
    assert (
        today_execution_readiness_diagnostic(
            {
                "trade_handoff_ready": True,
                "sub_status": {
                    "broker_transport": "up",
                    "session_auth": "active",
                    "handoff_readiness": "ready",
                    "bracket_readiness": "ready",
                    "engine": "on",
                },
            }
        )
        == ""
    )


def test_strategy_decay_line_on_cost_drag_row():
    row = rank_single_row(
        {"ticker": "XYZ", "raw_score": 8.0, "score": 8.0, "extended": True},
        tradeability="SELECTIVE",
    )
    if row.get("cost_rank_label") == "cost_too_high":
        assert row.get("strategy_decay_line") == STRATEGY_DECAY_DOWNGRADE_COPY
    else:
        assert resolve_strategy_decay_line({**row, "validity_flags": [FLAG_DECAY]}) == STRATEGY_DECAY_DOWNGRADE_COPY


def test_index_pass2_wiring():
    raw = INDEX_HTML.read_text(encoding="utf-8")
    partial = DEPLOY_PARTIAL.read_text(encoding="utf-8")
    assert "todayMissionQuantClusterLines" in raw
    assert "todayExecutionReadinessDiagnostic" in raw
    assert "playbookStrategyDecayLine" in raw
    assert "quant_cluster_lines" in raw
    assert "Quant clusters (monitor)" in partial
    js = CC_HELPERS.read_text(encoding="utf-8")
    assert "todayMissionQuantClusterLines" in js
    assert "todayExecutionReadinessDiagnostic" in js
    assert "playbookStrategyDecayLine" in js
