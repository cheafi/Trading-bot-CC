"""IDOS mechanical separation — learning loop cannot open deploy."""

from __future__ import annotations

import pytest

from src.core.deployment_manifest import (
    load_deployment_manifest,
    write_deployment_manifest,
)
from src.services.autonomous_learning_loop import run_learning_cycle


@pytest.fixture(autouse=True)
def _isolate_manifest(tmp_path, monkeypatch):
    path = tmp_path / "deployment_manifest.json"
    monkeypatch.setattr(
        "src.core.deployment_manifest.deployment_manifest_path",
        lambda: path,
    )
    monkeypatch.setattr(
        "src.services.autonomous_learning_loop._STATE_PATH",
        tmp_path / "autonomous_learning_loop_state.json",
    )
    monkeypatch.setattr(
        "src.services.autonomous_learning_loop._DATA_DIR",
        tmp_path,
    )
    write_deployment_manifest(
        {"deploy_open": False, "candidates": []},
        updated_by="ops",
        caller="ops",
        path=path,
    )
    yield path


def test_learning_loop_cannot_write_deployment_manifest() -> None:
    with pytest.raises(PermissionError):
        write_deployment_manifest(
            {"deploy_open": True},
            updated_by="autonomous_learning_loop",
            caller="autonomous_learning_loop",
        )


def test_high_score_learning_cycle_leaves_deploy_closed(
    monkeypatch: pytest.MonkeyPatch,
    _isolate_manifest,
) -> None:
    monkeypatch.setattr(
        "src.services.autonomous_learning_loop._propose",
        lambda trades: {
            "beliefs_due": 0,
            "ab_experiments_proposed": 99,
            "may_authorize_deploy": False,
            "score": 0.99,
        },
    )
    monkeypatch.setattr(
        "src.services.autonomous_learning_loop._observe",
        lambda: {"closed_trades": 100, "forward_marks_with_r": 50},
    )
    monkeypatch.setattr(
        "src.services.autonomous_learning_loop._label",
        lambda trades: {"channels": {"score": 0.99}},
    )
    monkeypatch.setattr(
        "src.services.autonomous_learning_loop._calibrate",
        lambda: {"drift_alert": False},
    )

    before = load_deployment_manifest()
    result = run_learning_cycle(phases=["observe", "label", "calibrate", "propose"])
    after = load_deployment_manifest()

    assert result["may_authorize_deploy"] is False
    assert before["deploy_open"] is False
    assert after["deploy_open"] is False
    assert result.get("deployment_manifest_unchanged") is True


def test_decision_committee_deploy_open_provenance() -> None:
    from src.services.decision_committee import build_committee_review

    review = build_committee_review(ticker="MSFT", deploy_open=True, llm_vote=True)
    prov = review["deploy_open_provenance"]
    assert prov["deploy_open"] is True
    assert prov["broker_eligible"] is False
    assert prov["llm_vote_affects_broker"] is False
