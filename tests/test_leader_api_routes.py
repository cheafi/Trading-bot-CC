"""HTTP route ordering and leader API smoke tests."""

import os

import pytest
from fastapi.testclient import TestClient


@pytest.fixture
def client(tmp_path):
    os.environ["LEADER_DB_PATH"] = str(tmp_path / "leader_api.db")
    from src.api.main import app
    from src.services.leader_tracking_service import ensure_seeded

    ensure_seeded(force=True)
    return TestClient(app)


def test_portfolio_overlap_not_captured_by_leader_id(client):
    r = client.get("/api/leaders/portfolio-overlap", params={"tickers": "NVDA,AAPL"})
    assert r.status_code == 200
    body = r.json()
    assert body["holdings_checked"] == 2
    assert len(body["rows"]) == 2


def test_leader_detail_still_works(client):
    r = client.get("/api/leaders/berkshire-13f")
    assert r.status_code == 200
    assert "Berkshire" in r.json().get("name", "")
