"""Surface-aware header summary — no playbook chips on Guide / research tabs."""

from __future__ import annotations

from src.services.surface_authority import (
    SURFACE_MODES,
    build_header_summary,
    build_header_summary_for_tab,
    header_summary_for_tab,
    resolve_surface_mode,
    surface_shows_decision_chips,
)

_REQUIRED_MODES = frozenset(
    {
        "dashboard_core",
        "playbook_core",
        "discovery_research",
        "dossier_research",
        "portfolio_manual",
        "funds_research",
        "flow_supporting",
        "rs_supporting",
        "rejections_diagnostic",
        "ops_diagnostic",
        "ibkr_execution",
        "backtest_research",
        "guide_reference",
    }
)


def test_all_required_surface_modes_mapped():
    mapped = set(SURFACE_MODES.values())
    assert _REQUIRED_MODES <= mapped


def test_surface_modes_cover_core_tabs():
    assert SURFACE_MODES["today"] == "dashboard_core"
    assert SURFACE_MODES["signals"] == "playbook_core"
    assert SURFACE_MODES["scanners"] == "discovery_research"
    assert SURFACE_MODES["guide"] == "guide_reference"
    assert SURFACE_MODES["notrade"] == "rejections_diagnostic"
    assert SURFACE_MODES["btlab"] == "backtest_research"


def test_resolve_surface_mode_aliases():
    assert resolve_surface_mode("signals") == "playbook_core"
    assert resolve_surface_mode("dossier") == "dossier_research"
    assert resolve_surface_mode("stock-intel") == "dossier_research"
    assert resolve_surface_mode("rejections") == "rejections_diagnostic"
    assert resolve_surface_mode("backtest") == "backtest_research"
    assert resolve_surface_mode("command") == "command_research"


def test_guide_header_has_no_deploy_chips():
    summary = header_summary_for_tab("guide")
    assert summary["surface_mode"] == "guide_reference"
    assert summary["badge"] == "GUIDE MODE"
    assert summary["show_decision_chips"] is False
    assert not any("Idea" in c["label"] for c in summary["chips"])
    assert "QCOM" not in str(summary["chips"])


def test_funds_header_research_only_not_playbook():
    summary = header_summary_for_tab(
        "funds",
        {"tradeability": "TRADE", "best_idea_ticker": "QCOM", "deploy_label": "REDUCE"},
    )
    assert summary["surface_mode"] == "funds_research"
    assert summary["show_decision_chips"] is False
    assert not any("QCOM" in c["label"] for c in summary["chips"])
    assert not any("REDUCE" in c["label"] for c in summary["chips"])


def test_rejections_header_no_playbook_leak():
    summary = build_header_summary_for_tab(
        "notrade",
        {"best_idea_ticker": "QCOM", "deploy_label": "REDUCE", "avoid_count": 3},
    )
    assert summary["surface_mode"] == "rejections_diagnostic"
    assert summary["show_decision_chips"] is False
    assert "QCOM" not in str(summary["chips"])


def test_playbook_header_includes_idea_when_authoritative():
    summary = build_header_summary(
        "playbook_core",
        {
            "tradeability": "SELECTIVE",
            "deploy_label": "WATCH",
            "best_idea_ticker": "QCOM",
            "avoid_count": 1,
        },
    )
    assert summary["show_decision_chips"] is True
    labels = [c["label"] for c in summary["chips"]]
    assert "Idea QCOM" in labels
    assert "Avoid 1" in labels


def test_discovery_not_authoritative_when_ok():
    summary = build_header_summary("discovery_research", {})
    assert summary["fetch_state"] == "not_authoritative"
    assert summary["show_decision_chips"] is False


def test_surface_shows_decision_chips_only_dashboard_playbook():
    assert surface_shows_decision_chips("dashboard_core") is True
    assert surface_shows_decision_chips("playbook_core") is True
    assert surface_shows_decision_chips("flow_supporting") is False


def test_portfolio_tab_blocked_when_ibkr_offline():
    from src.services.surface_authority import AUTHORITY_BLOCKED, resolve_authority_for_ui_tab

    auth = resolve_authority_for_ui_tab(
        "portfolio",
        tradeability="TRADE",
        ibkr_connected=False,
        deployable_count=3,
    )
    assert auth["tab"] == "portfolio"
    assert auth["authority"] == AUTHORITY_BLOCKED


def test_portfolio_surface_short_describes_book():
    from src.services.surface_authority import resolve_authority

    auth = resolve_authority("portfolio", tradeability="WAIT")
    assert auth["surface"] == "Portfolio"
    assert "book" in auth["short"].lower()


def test_cc_header_portfolio_context_shape():
    from src.services.portfolio_positions import portfolio_header_snapshot

    ctx = portfolio_header_snapshot(ibkr_connected=False)
    required = {
        "mode",
        "book_label",
        "positions_label",
        "broker_sync",
        "broker_sync_label",
        "rebalance_label",
    }
    assert required.issubset(ctx.keys())
    assert ctx["rebalance_label"] == "Rebalance support only"


def test_command_surface_hidden_from_primary_nav():
    from src.services.surface_authority import TAB_SURFACE_MAP

    assert TAB_SURFACE_MAP["command"].get("hide_from_primary_nav") is True
