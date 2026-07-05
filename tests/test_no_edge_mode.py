"""No edge mode — only rejected names."""

from __future__ import annotations

from src.services.playbook_truth import bucket_counts, is_no_edge_mode, no_edge_copy


def test_no_edge_when_only_rejected():
    counts = {"Deploy": 0, "Pilot": 0, "Watch": 0, "Near-miss": 0, "Rejected": 12}
    assert is_no_edge_mode(counts) is True
    copy = no_edge_copy(counts)
    assert copy.startswith("NO EDGE TODAY")
    assert "0 Deploy" in copy
    assert "Rejected hidden" in copy
    assert "do nothing" in copy


def test_not_no_edge_when_watch_present():
    counts = {"Deploy": 0, "Pilot": 0, "Watch": 2, "Near-miss": 0, "Rejected": 5}
    assert is_no_edge_mode(counts) is False


def test_bucket_counts_no_edge_from_rows():
    rows = [{"ticker": f"R{i}", "action": "AVOID"} for i in range(4)]
    counts = bucket_counts(rows, deploy_authority=False)
    assert is_no_edge_mode(counts) is True
