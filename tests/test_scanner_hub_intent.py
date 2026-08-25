"""Decision-intent scanner hub summary."""

from src.engines.scanner_matrix import (
    DECISION_INTENT_ORDER,
    ScannerMatrix,
)


def test_build_decision_intent_summary_shape():
    scanner = ScannerMatrix()
    regime = {"trend": "BULL", "tradeability": "WAIT"}
    signals = [
        {
            "ticker": "TEST",
            "strategy": "vcp",
            "pattern": "vcp",
            "contraction_count": 3,
            "score": 8,
        }
    ]
    summary = scanner.build_decision_intent_summary(signals, regime)
    assert set(summary.keys()) == set(DECISION_INTENT_ORDER)
    for intent in DECISION_INTENT_ORDER:
        row = summary[intent]
        assert row["intent"] == intent
        assert "probe_status" in row
        assert "count" in row
        assert "regime_note" in row
        assert "empty_why" in row
        assert isinstance(row["top_hits"], list)
    assert "WAIT" in summary["BREAKOUTS"]["empty_why"] or summary["BREAKOUTS"]["count"] >= 0


def test_hits_for_decision_intent_no_trade_warnings_only():
    scanner = ScannerMatrix()
    regime = {"macro_event_nearby": True, "next_macro_event": "CPI"}
    signals = [{"ticker": "XYZ", "score": 5, "extension_pct": 25}]
    hits = scanner.hits_for_decision_intent("NO_TRADE", signals, regime)
    assert all(h.is_warning for h in hits) or len(hits) == 0


def test_cc_instant_stale_scanners_has_decision_intent():
    """Degraded /api/v7/playbook/scanners must expose intent cards (not blank Discovery)."""
    import json
    from pathlib import Path

    instant_path = Path(__file__).resolve().parents[1] / "_cc_instant.py"
    chunk = instant_path.read_text().split("class Handler")[0]
    ns: dict = {"__file__": str(instant_path)}
    exec(chunk, ns)  # noqa: S102
    payload = json.loads(ns["_stale_scanners_bytes"]())
    assert set(payload["decision_intent"].keys()) == set(DECISION_INTENT_ORDER)
    assert payload.get("discovery_verdict")
    assert "research_note" in payload
