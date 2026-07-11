"""Release audit scripts — authority language and visible copy."""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def _run(script: str, *args: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [sys.executable, str(ROOT / "scripts" / script), *args],
        cwd=ROOT,
        capture_output=True,
        text=True,
        check=False,
    )


def test_authority_language_audit_runs():
    proc = _run("audit-authority-language.py")
    assert proc.returncode == 0, proc.stdout + proc.stderr


def test_visible_copy_audit_runs():
    proc = _run("audit-visible-copy.py", "--fail-on", "critical")
    assert proc.returncode == 0, proc.stdout + proc.stderr


def test_threshold_review_status_line_no_live_changes():
    from src.services.threshold_proposal_service import threshold_governance_summary_for_dashboard

    summary = threshold_governance_summary_for_dashboard()
    line = summary["status_line"]
    assert "Threshold Review:" in line
    assert "Review only · no live changes" in line or "live change" in line
    assert summary["can_auto_loosen"] is False


def test_decision_quality_never_authorizes_deploy():
    from src.services.opportunity_quality_engine import build_decision_quality_dashboard
    from src.services.system_truth import resolve_system_truth

    truth = resolve_system_truth(
        {"market_regime": {"tradeability": "TRADE"}, "trust": {"stale": False}},
        cc_header={"data_tier": "FRESH"},
        ops_console={"engine_running": True},
    )
    dq = build_decision_quality_dashboard(truth=truth)
    assert dq["may_authorize_deploy"] is False
    assert dq["authority_effect"] == "none"
    assert dq["collapsed"] is True
