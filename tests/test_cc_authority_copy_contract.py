"""Deploy-blocked primary state must not read as SELECTIVE deploy authority."""

from __future__ import annotations

from src.services.authority_engine import primary_operator_state
from src.services.operator_surface import build_operator_block
from src.services.system_truth import resolve_system_truth


def test_dashboard_primary_not_selective_when_blocked():
    """Runtime UI contract: trust-strip primary must not show SELECTIVE when deploy blocked."""
    from pathlib import Path

    raw = Path(__file__).resolve().parents[1] / "src" / "api" / "templates" / "index.html"
    html = raw.read_text(encoding="utf-8", errors="replace")
    assert 'trust-strip-tier-primary' in html
    primary = html.split('trust-strip-tier-primary', 1)[1].split("</div>", 1)[0]
    assert "todayPrimaryStateLine()" in primary or "runtimePrimaryStateLine()" in primary
    assert 'x-text="today7.tradeability' not in primary


def test_deploy_blocked_primary_is_monitor_only_not_selective():
    truth = resolve_system_truth(
        {
            "market_regime": {"tradeability": "SELECTIVE", "should_trade": True},
            "trust": {"stale": True, "source": "decision_engine_degraded"},
            "decision_authority": {
                "authority_level": "research",
                "gates_active": True,
                "allows_trade_labels": False,
            },
            "execution_readiness": {"broker_connected": False},
            "qualification_levels": {"deploy_qualified": 2, "setup_qualified": 3},
            "top_5": [{"ticker": "XLP", "action": "WATCH"}],
        },
        cc_header={"data_tier": "STALE"},
        ops_console={"engine_running": True},
    )
    posture = primary_operator_state(truth)
    assert posture["primary"] == "MONITOR ONLY"
    assert posture["secondary"] == "SELECTIVE"
    block = build_operator_block(truth, "dashboard")
    assert block["now"] == "MONITOR ONLY · Deploy blocked"
    assert block["now"] != "SELECTIVE"
    assert block["blocked"] == "no sizing, no handoff, no pilot entry"
