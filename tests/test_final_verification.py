"""Final verification pass — pytest hang regression, partials, authority gates."""

from __future__ import annotations

import time
from pathlib import Path
from unittest.mock import patch

from src.services.decision_truth_model import finalize_ranked_payload_authority
from src.services.fetch_surface_state import soak_confirmation_signals
from src.services.ibkr_diagnosis import probe_tcp_port

ROOT = Path(__file__).resolve().parents[1]
INDEX_HTML = ROOT / "src/api/templates/index.html"
BUILD_SCRIPT = ROOT / "scripts/build-cc-template.mjs"
CC_HELPERS = ROOT / "src/api/static/cc-helpers.js"


def test_finalize_ranked_payload_authority_completes_without_tcp_probe():
    """Regression: ranked authority must not call status() / probe_tcp_port (CI hang)."""
    payload = {
        "source": "ranked_pipeline",
        "best_action": {"tradeability": "WAIT"},
        "opportunities": [
            {"ticker": "A", "action": "TRADE", "score": 7.0, "risk_reward": 2.0},
        ],
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
    assert out["near_miss"][0].get("effective_action")


def test_ibkr_authority_gate_snapshot_memory_only():
    from src.services.ibkr_service import ibkr_authority_gate_snapshot

    with patch("src.services.ibkr_diagnosis.probe_tcp_port") as probe:
        snap = ibkr_authority_gate_snapshot()
        probe.assert_not_called()
    assert "connected" in snap


def test_soak_confirmation_signals_stable():
    signals = soak_confirmation_signals()
    assert "deploy_strip" in signals
    assert 'data-cc="deploy-status-strip"' in signals["deploy_strip"]
    assert "CONFIRM ONLY" in signals["route_abort_dossier"]


def test_deploy_surfaces_partial_wired():
    raw = INDEX_HTML.read_text(encoding="utf-8")
    assert "<!-- @cc-partial deploy_surfaces -->" in raw
    assert 'data-cc="deploy-status-strip"' in raw
    script = BUILD_SCRIPT.read_text(encoding="utf-8")
    assert "deploy_surfaces:" in script
    js = CC_HELPERS.read_text(encoding="utf-8")
    assert "soakConfirmationSelectors" in js


def test_probe_tcp_port_still_works_when_called_directly():
    assert probe_tcp_port("", 0) is False
