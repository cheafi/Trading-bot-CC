"""Leader / Holdings Tracking module tests."""

import os
import tempfile

import pytest


@pytest.fixture
def leader_db(tmp_path):
    path = str(tmp_path / "test_leader.db")
    os.environ["LEADER_DB_PATH"] = path
    from src.services.leader_tracking_service import ensure_seeded

    ensure_seeded(force=True)
    yield path
    os.environ.pop("LEADER_DB_PATH", None)


def test_list_leaders(leader_db):
    from src.services.leader_tracking_service import list_leaders_enriched

    rows = list_leaders_enriched()
    assert len(rows) >= 5
    assert any(r["id"] == "berkshire-13f" for r in rows)
    assert rows[0].get("source_quality_label")


def test_leader_detail_has_decision_box(leader_db):
    from src.services.leader_tracking_service import get_leader_detail

    d = get_leader_detail("kol-tech-leaps")
    assert d is not None
    assert d["decision"]["labels"]["not_verified_holding"] is True
    assert any("inferred" in w.lower() or "verified" in w.lower() for w in d["decision"]["warnings"])


def test_consensus_nvda_overlap(leader_db):
    from src.services.leader_tracking_service import get_consensus_ticker

    c = get_consensus_ticker("NVDA")
    assert c["ticker"] == "NVDA"
    assert len(c["leaders"]) >= 2


def test_flow_heuristic_labeled(leader_db):
    from src.services.leader_tracking_service import get_flow_tracked

    data = get_flow_tracked()
    assert data["data_mode"] == "heuristic"
    assert "disclaimer" in data


def test_api_router_import():
    from src.api.routers.leaders import router

    paths = [getattr(r, "path", "") for r in router.routes]
    assert "/api/leaders" in paths
    assert "/api/consensus" in paths


def test_ticker_embed_nvda(leader_db):
    from src.services.leader_tracking_service import get_ticker_embed

    emb = get_ticker_embed("NVDA")
    assert emb["ticker"] == "NVDA"
    assert "disclaimer" in emb
    assert len(emb.get("tracked_by", [])) >= 1


def test_portfolio_overlap(leader_db):
    from src.services.leader_tracking_service import get_portfolio_overlap

    out = get_portfolio_overlap(["NVDA", "AAPL"])
    assert out["holdings_checked"] == 2
    assert len(out["rows"]) == 2
    assert "summary" in out
