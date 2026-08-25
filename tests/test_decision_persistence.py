from __future__ import annotations

from types import SimpleNamespace

from src.engines.decision_persistence import DecisionJournal


def _recommendation(**overrides):
    rec = {
        "ticker": "MSFT",
        "strategy": "momentum",
        "score": 8.2,
        "confidence": 82,
        "grade": "A",
        "direction": "LONG",
        "entry_price": 100,
        "stop_price": 95,
        "target_price": 115,
        "risk_reward": 3,
        "regime": "BULL",
        "sector": "Technology",
        "calibrated_confidence": {
            "forecast_probability": 0.62,
            "historical_reliability_bucket": "high",
            "uncertainty_band": {"low": 70, "high": 90},
        },
        "trust_strip": {
            "mode": "SCAN",
            "source": "yfinance",
            "freshness": "delayed_15m",
            "feature_stage": "BETA",
        },
    }
    rec.update(overrides)
    return rec


def test_recommendation_ledger_records_canonical_fields(tmp_path):
    journal = DecisionJournal(path=str(tmp_path / "decision_journal.jsonl"))

    summary = journal.record_recommendations(
        [_recommendation()],
        source="live_scanner",
        mode="SCAN",
        regime="BULL",
        response_trust={"assumptions": "gross returns"},
        data_freshness={"status": "fresh"},
    )
    records = journal.get_recent_recommendations(10)

    assert summary == {"written": 1, "deduped": 0}
    assert len(records) == 1
    record = records[0]
    assert record["record_type"] == "recommendation"
    assert record["ticker"] == "MSFT"
    assert record["decision_tier"] == "A"
    assert record["risk_reward"] == 3
    assert record["forecast_probability"] == 0.62
    assert record["confidence_source"] == "calibrated_confidence"
    assert record["data_freshness"] == {"status": "fresh"}
    assert record["trust_strip"]["recommendation_source"] == "live_scanner"
    assert record["trust_strip"]["confidence_source"] == "calibrated_confidence"


def test_recommendation_ledger_dedupes_repeated_refreshes(tmp_path):
    journal = DecisionJournal(path=str(tmp_path / "decision_journal.jsonl"))
    rec = _recommendation()

    first = journal.record_recommendations([rec], source="engine_cache", mode="PAPER")
    second = journal.record_recommendations([rec], source="engine_cache", mode="PAPER")
    records = journal.get_recent_recommendations(10)

    assert first == {"written": 1, "deduped": 0}
    assert second == {"written": 0, "deduped": 1}
    assert len(records) == 1


def test_recommendation_ledger_accepts_object_inputs_and_score_confidence(tmp_path):
    journal = DecisionJournal(path=str(tmp_path / "decision_journal.jsonl"))
    rec = SimpleNamespace(
        ticker="NVDA",
        strategy="breakout",
        score=7.6,
        grade="B",
        entry_price=200,
        stop_price=190,
        target_price=230,
        risk_reward=3,
    )

    summary = journal.record_recommendations([rec], source="unit", mode="TEST")
    records = journal.get_recent_recommendations(10)

    assert summary == {"written": 1, "deduped": 0}
    assert records[0]["ticker"] == "NVDA"
    assert records[0]["confidence"] == 76
    assert records[0]["confidence_source"] == "raw_recommendation_confidence"
    assert records[0]["predicted_prob"] == 0.76
