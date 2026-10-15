"""Paper mock-test ops endpoint — engine cycle + backtest leg."""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from src.api.routers import ops as ops_router


@pytest.fixture
def ops_client(monkeypatch: pytest.MonkeyPatch) -> TestClient:
    from src.core import config

    monkeypatch.setattr(config.settings, "api_secret_key", "test-secret-key", raising=False)
    app = FastAPI()
    app.include_router(ops_router.router)
    app.state.engine_task = None
    app.state.engine_init_done = True
    return TestClient(app)


def test_mock_test_requires_api_key(ops_client: TestClient) -> None:
    r = ops_client.post("/api/ops/engine/mock-test")
    assert r.status_code == 401


def test_mock_test_ok_with_stubbed_engine(ops_client: TestClient) -> None:
    engine = MagicMock()
    engine._running = False
    engine.run_one_cycle = AsyncMock(
        return_value={
            "cycle_count": 1,
            "cached_recommendations": 3,
            "signals_today": 2,
            "trades_today": 0,
            "last_cycle": None,
        }
    )

    async def _fake_cycle(app):
        return {
            "ok": True,
            "cycle": await engine.run_one_cycle(),
            "engine": {"running": False},
        }

    fake_bt = {
        "best_strategy": "momentum",
        "total_trades": 12,
        "trust": {"mode": "backtest"},
    }

    with patch("src.api.routers.ops.get_engine", return_value=engine):
        with patch.object(ops_router, "_run_engine_cycle_once", side_effect=_fake_cycle):
            with patch(
                "src.api.routers.live_backtest.live_backtest",
                new=AsyncMock(return_value=fake_bt),
            ):
                r = ops_client.post(
                    "/api/ops/engine/mock-test",
                    headers={"X-API-Key": "test-secret-key"},
                )
    assert r.status_code == 200
    body = r.json()
    assert body.get("ok") is True
    assert body.get("authority") == "paper_mock"
    assert body.get("backtest", {}).get("ok") is True
