"""Alpha quality store — append-only snapshots."""

from __future__ import annotations

from src.services.alpha_quality_store import (
    AlphaQualityByStage,
    AlphaQualitySnapshot,
    AlphaQualityStore,
    make_snapshot_id,
)


def test_append_snapshot(tmp_path):
    store = AlphaQualityStore(
        snapshots_path=str(tmp_path / "snapshots.jsonl"),
        by_stage_path=str(tmp_path / "by_stage.jsonl"),
        by_family_path=str(tmp_path / "by_family.jsonl"),
    )
    snap = AlphaQualitySnapshot(
        snapshot_id=make_snapshot_id(),
        sample_size=3,
        status="learning",
        by_stage=[AlphaQualityByStage(stage="near_miss", sample_size=2).to_dict()],
    )
    sid = store.append_snapshot(snap)
    assert sid == snap.snapshot_id
    rows = store.load_snapshots()
    assert len(rows) == 1
    assert rows[0]["may_authorize_deploy"] is False
    assert rows[0]["authority_effect"] == "none"
    assert rows[0]["learning_mode"] is True


def test_summary_learning_mode(tmp_path):
    store = AlphaQualityStore(
        snapshots_path=str(tmp_path / "snapshots.jsonl"),
        by_stage_path=str(tmp_path / "by_stage.jsonl"),
        by_family_path=str(tmp_path / "by_family.jsonl"),
    )
    store.append_snapshot(
        AlphaQualitySnapshot(snapshot_id=make_snapshot_id(), sample_size=4, status="learning")
    )
    s = store.summary()
    assert s["learning_mode"] is True
    assert s["may_authorize_deploy"] is False
