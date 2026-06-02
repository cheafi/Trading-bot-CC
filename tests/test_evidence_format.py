"""Evidence formatting helpers."""

from __future__ import annotations

from src.utils.evidence_format import format_evidence, playbook_evidence_line


def test_format_evidence_score_and_data_quality():
    text = format_evidence({"validated_score": 4.8, "data_conf": 0.5})
    assert "score 4.8" in text
    assert "data quality 50%" in text
    assert "validated" not in text


def test_playbook_evidence_line():
    text = playbook_evidence_line({"validated_score": 4.8, "data_conf": 0.5})
    assert text == "Evidence score 4.8 · data quality 50%"
