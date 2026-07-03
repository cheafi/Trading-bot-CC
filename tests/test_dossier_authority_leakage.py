"""Dossier authority leakage contract — degraded modes must not expose trade plan."""

from __future__ import annotations

from pathlib import Path

from src.services.dossier_mode import (
    DOSSIER_CONFIRM_ONLY_STRIP,
    MONITOR_RULE_BUTTON,
    MONITOR_RULE_HINT,
    build_dossier_mode_block,
    dossier_evidence_status_panel,
    paper_draft_visible,
    resolve_dossier_mode,
    trade_plan_visible,
)

ROOT = Path(__file__).resolve().parents[1]
INDEX_HTML = ROOT / "src" / "api" / "templates" / "index.html"
CC_HELPERS = ROOT / "src" / "api" / "static" / "cc-helpers.js"


def _degraded_intel_block():
    return build_dossier_mode_block(
        mode="unavailable",
        ticker="XLP",
        unified_label="CONFIRM ONLY",
        instant_degraded=True,
        brief_backed=False,
        has_quote=False,
        has_technicals=False,
        has_peers=False,
        has_options=False,
        has_catalysts=False,
        has_risk=False,
        playbook_deploy_allowed=False,
        has_narrative=False,
        broker_online=False,
    )


def test_degraded_payload_hides_trade_authority():
    block = _degraded_intel_block()
    assert block["hide_trade_plan"] is True
    assert block["hide_paper_draft"] is True
    assert block["hide_sizing"] is True
    assert block["evidence_status"]["show"] is True
    assert block["dossier_operator_block"]["blocked"] == [
        "no trade plan",
        "no paper draft",
        "no sizing",
        "no handoff",
    ]


def test_paper_draft_hidden_unless_usable_authority_broker():
    assert (
        paper_draft_visible(
            mode="structure_review_only",
            playbook_watch_plus=True,
            deploy_blocked=False,
            broker_online=True,
        )
        is False
    )
    assert (
        paper_draft_visible(
            mode="usable",
            playbook_watch_plus=True,
            deploy_blocked=False,
            broker_online=True,
        )
        is True
    )
    assert (
        paper_draft_visible(
            mode="usable",
            playbook_watch_plus=True,
            deploy_blocked=True,
            broker_online=True,
        )
        is False
    )


def test_trade_plan_hidden_without_deploy_authority():
    assert trade_plan_visible(
        mode="usable",
        deploy_blocked=True,
        broker_online=True,
        playbook_watch_plus=True,
    ) is False
    assert trade_plan_visible(
        mode="usable",
        deploy_blocked=False,
        broker_online=True,
        playbook_watch_plus=True,
    ) is True


def test_evidence_panel_when_quote_missing():
    panel = dossier_evidence_status_panel(
        mode="unavailable",
        has_quote=False,
        has_narrative=False,
    )
    assert panel["show"] is True
    assert panel["headline"] == "Structure unavailable"


def test_index_no_set_alert_button_text():
    text = INDEX_HTML.read_text(encoding="utf-8")
    dossier_slice = text[text.index('data-cc="dossier-confirm-only-blocks"'): text.index("<!-- PM 30-second answer")]
    assert "Set Alert" not in dossier_slice
    assert MONITOR_RULE_BUTTON in text
    assert MONITOR_RULE_HINT in CC_HELPERS.read_text(encoding="utf-8")


def test_index_no_entry_stop_in_recovery_grid():
    text = INDEX_HTML.read_text(encoding="utf-8")
    idx = text.index('x-show="dossierUsable()" class="grid gap-2')
    grid = text[idx : idx + 600]
    assert "Entry zone" in grid
    assert 'x-show="dossierUsable()"' in text
    recovery_idx = text.index("dossierRecoveryMode()")
    recovery = text[recovery_idx : recovery_idx + 1200]
    assert "Entry zone" not in recovery or "dossierUsable()" in recovery


def test_index_no_contradictions_placeholder_when_degraded():
    text = INDEX_HTML.read_text(encoding="utf-8")
    assert "No major contradictions flagged" not in text
    assert "dossierEvidenceStatusVisible()" in text


def test_index_single_confirm_only_banner():
    text = INDEX_HTML.read_text(encoding="utf-8")
    assert text.count(DOSSIER_CONFIRM_ONLY_STRIP) == 1


def test_confirm_only_loading_modes_not_usable():
    for kwargs in (
        dict(unified_label="CONFIRM ONLY", has_quote=False, instant_degraded=True),
        dict(load_phase="core", has_quote=True),
        dict(failed_fetch=True, has_quote=False),
    ):
        mode = resolve_dossier_mode(**kwargs)
        assert mode != "usable"
