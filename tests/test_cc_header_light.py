"""CC header light mode — must not claim FRESH without probing."""

from __future__ import annotations

import pytest


@pytest.mark.anyio
async def test_cc_header_light_data_pill_unknown_not_fresh():
    from httpx import ASGITransport, AsyncClient

    from src.api.main import app

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        r = await client.get(
            "/api/ops/cc-header",
            params={"light": "1"},
            headers={"X-API-Key": "dev-secret-local"},
        )
    assert r.status_code == 200
    data = r.json()
    assert data["light_mode"] is True
    assert data["pills"]["data"] == "UNKNOWN"
    assert data["pills"]["data"] != "FRESH"
    assert data.get("light_banner")
    assert data["trust"]["freshness"] == "UNKNOWN"
    assert data["trust"]["stale"] is True


@pytest.mark.anyio
async def test_cc_header_light_healthy_false():
    from httpx import ASGITransport, AsyncClient

    from src.api.main import app

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        r = await client.get(
            "/api/ops/cc-header",
            params={"light": "1"},
            headers={"X-API-Key": "dev-secret-local"},
        )
    assert r.status_code == 200
    data = r.json()
    assert data["healthy"] is False
    da = data.get("decision_authority") or {}
    assert da.get("gates", {}).get("data_stale") is True
