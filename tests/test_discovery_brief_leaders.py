"""Discovery cached brief leaders when live scanner hits are empty."""

from src.api.routers.playbook import _enrich_discovery_zero_hits
from src.engines.scanner_matrix import DECISION_INTENT_ORDER, RSLeaderScanner, ScannerMatrix


def test_enrich_discovery_zero_hits_adds_cached_leaders(monkeypatch):
    monkeypatch.setattr(
        "src.api.routers.playbook._discovery_brief_leader_rows",
        lambda **_: [
            {
                "ticker": "AMD",
                "max_score": 8.5,
                "why_flagged": "Cached brief · actionable",
                "brief_section": "actionable",
            }
        ],
    )
    payload = {
        "total_hits": 0,
        "merged_top_names": [],
        "decision_intent": {k: {"intent": k, "top_hits": []} for k in DECISION_INTENT_ORDER},
        "discovery_verdict": {},
        "diagnostics": {},
    }
    out = _enrich_discovery_zero_hits(
        payload,
        regime={"trend": "SIDEWAYS"},
        scanner=ScannerMatrix(),
    )
    assert out.get("cached_leaders")
    assert out["merged_top_names"]
    assert out["decision_intent"]["LEADERS"]["top_hits"]


def test_rs_leader_scanner_uses_rs_score():
    rs = RSLeaderScanner()
    hits = rs.scan([{"ticker": "TEST", "rs_score": 88.0}], {})
    assert len(hits) == 1
    assert hits[0].ticker == "TEST"
