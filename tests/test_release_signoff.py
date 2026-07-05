"""Release sign-off gates — template integrity, authority hang, soak anchors."""

from __future__ import annotations

import subprocess
import time
from pathlib import Path
from unittest.mock import patch

from src.services.decision_truth_model import finalize_ranked_payload_authority
from src.services.fetch_surface_state import soak_confirmation_signals
from src.services.ibkr_diagnosis import probe_tcp_port

ROOT = Path(__file__).resolve().parents[1]
INDEX_HTML = ROOT / "src/api/templates/index.html"
CC_HELPERS = ROOT / "src/api/static/cc-helpers.js"


def test_release_index_html_single_cc_app():
    raw = INDEX_HTML.read_text(encoding="utf-8")
    assert raw.count("function cc(){return{") == 1
    assert raw.count('<!-- ══════ ALPINE JS ══════ -->') == 1
    assert raw.count('data-cc="playbook-surface"') == 1


def test_release_template_drift_gate_passes():
    proc = subprocess.run(
        ["node", "scripts/build-cc-template.mjs", "--check"],
        cwd=ROOT,
        capture_output=True,
        text=True,
        check=False,
    )
    assert proc.returncode == 0, proc.stderr or proc.stdout


def test_release_ranked_authority_no_tcp_probe_hang():
    payload = {
        "source": "ranked_pipeline",
        "best_action": {"tradeability": "WAIT"},
        "opportunities": [{"ticker": "A", "action": "TRADE", "score": 7.0}],
        "near_miss": [{"ticker": "B", "action": "WATCH", "score": 6.2}],
    }

    def _fail_probe(*_args, **_kwargs):
        raise AssertionError("probe_tcp_port must not run during ranked authority finalize")

    with patch("src.services.ibkr_diagnosis.probe_tcp_port", side_effect=_fail_probe):
        t0 = time.monotonic()
        out = finalize_ranked_payload_authority(payload)
        elapsed = time.monotonic() - t0

    assert elapsed < 2.0
    assert out["opportunities"][0].get("effective_action")
    assert probe_tcp_port("", 0) is False


def test_release_soak_anchor_parity():
    py = soak_confirmation_signals()
    js = CC_HELPERS.read_text(encoding="utf-8")
    for key in (
        "instant_degraded",
        "warmup_strip",
        "deploy_strip",
        "mission_panel",
        "playbook_surface",
        "ops_runbook",
    ):
        assert key in py
        assert py[key].split('"')[1] in js
