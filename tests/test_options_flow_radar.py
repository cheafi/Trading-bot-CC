from __future__ import annotations

import asyncio
import os
import sys
from datetime import datetime, timedelta, timezone

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from src.engines.options_flow_radar import OptionsFlowRadar
from src.services.options_flow_mock import MockOptionsFlowProvider
from src.services.options_flow_persistence import OptionsFlowPersistence
from src.services.options_flow_provider import OptionsFlowEvent, OptionsFlowTrust


def test_mock_scan_surfaces_small_less_followed_flow():
    radar = OptionsFlowRadar(MockOptionsFlowProvider())

    snapshot = asyncio.run(
        radar.scan(["SOUN", "AAPL", "RILY"], limit=10, min_grade="C")
    )

    candidates = snapshot.candidates
    assert candidates
    assert candidates[0]["underlying"] == "SOUN"
    assert candidates[0]["quality_grade"] in {"A", "B"}
    assert candidates[0]["action_label"] in {"IDEA", "SUPPORTING_EVIDENCE", "WATCH"}
    assert snapshot.summary["small_less_followed"] >= 1
    assert snapshot.trust["mode"] == "mock"


def test_high_quality_sweep_scores_above_noisy_lottery_flow():
    radar = OptionsFlowRadar()
    now = datetime.now(timezone.utc)
    quality = OptionsFlowEvent(
        underlying="SOUN",
        contract_symbol="SOUN260515C00008000",
        side_bias="CALL_BUYING",
        call_put="C",
        strike=8.0,
        expiry=(now + timedelta(days=3)).date(),
        dte=3,
        trade_timestamp=now,
        premium=420_000,
        price=1.40,
        size=3000,
        bid=1.32,
        ask=1.48,
        volume=8200,
        open_interest=2100,
        volume_vs_avg_ratio=5.4,
        sweep_flag=True,
        block_flag=True,
        repeated_directional_prints=7,
        iv_change=0.18,
        stock_price=7.65,
        stock_move_pct=1.2,
        underlying_dollar_volume=145_000_000,
        market_cap=1_900_000_000,
        regime_alignment=0.72,
        relative_strength=0.66,
        trust=OptionsFlowTrust(source="unit", mode="snapshot"),
    )
    noisy = OptionsFlowEvent(
        underlying="RILY",
        contract_symbol="RILY260515P00005000",
        side_bias="PUT_BUYING",
        call_put="P",
        strike=5.0,
        expiry=(now + timedelta(days=2)).date(),
        dte=2,
        trade_timestamp=now,
        premium=8_000,
        price=0.08,
        size=1000,
        bid=0.01,
        ask=0.15,
        volume=1100,
        open_interest=80,
        volume_vs_avg_ratio=7.0,
        iv_change=0.35,
        stock_price=7.1,
        stock_move_pct=-8.5,
        underlying_dollar_volume=5_500_000,
        market_cap=210_000_000,
        regime_alignment=0.20,
        relative_strength=0.10,
        trust=OptionsFlowTrust(source="unit", mode="snapshot"),
    )

    scored_quality = radar.score_event(quality)
    scored_noisy = radar.score_event(noisy)

    assert scored_quality.radar_score > scored_noisy.radar_score
    assert scored_quality.quality_grade in {"A", "B"}
    assert scored_noisy.action_label == "AVOID_NOW"
    assert not radar.is_candidate(scored_noisy)


def test_stale_event_is_filtered_out():
    radar = OptionsFlowRadar()
    now = datetime.now(timezone.utc)
    event = OptionsFlowEvent(
        underlying="PLTR",
        contract_symbol="PLTR260515C00030000",
        side_bias="CALL_BUYING",
        call_put="C",
        strike=30.0,
        expiry=(now + timedelta(days=7)).date(),
        dte=7,
        trade_timestamp=now - timedelta(hours=1),
        premium=250_000,
        price=1.0,
        size=2500,
        bid=0.98,
        ask=1.02,
        volume=5000,
        open_interest=1000,
        volume_vs_avg_ratio=4.0,
        underlying_dollar_volume=500_000_000,
        trust=OptionsFlowTrust(source="unit", mode="delayed", delay_seconds=1800),
    )

    scored = radar.score_event(event)

    assert not radar.is_candidate(scored)


def test_persistence_round_trips_snapshot(tmp_path):
    service = OptionsFlowPersistence(db_path=str(tmp_path / "options_radar.db"))
    snapshot = {
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "status": "snapshot",
        "source": "unit",
        "universe_size": 1,
        "candidates": [
            {
                "underlying": "SOUN",
                "contract_symbol": "SOUN260515C00008000",
                "quality_grade": "A",
                "action_label": "IDEA",
                "radar_score": 82.0,
                "premium": 420_000,
                "volume_oi_ratio": 3.9,
                "volume_vs_avg_ratio": 5.4,
            }
        ],
        "summary": {"grade_a": 1, "grade_b": 0, "grade_c": 0},
        "trust": {"provider": "unit"},
    }

    snapshot_id = service.save_snapshot(snapshot)
    latest = service.latest_snapshot()
    events = service.events_for_ticker("SOUN")

    assert snapshot_id > 0
    assert latest is not None
    assert latest["source"] == "unit"
    assert events[0]["quality_grade"] == "A"


def test_options_radar_top_endpoint_uses_mock_provider(monkeypatch, tmp_path):
    import src.services.options_flow_persistence as persistence_module
    from fastapi import FastAPI
    from fastapi.testclient import TestClient
    from src.api.routers.options_radar import router

    monkeypatch.setenv("OPTIONS_RADAR_PROVIDER", "mock")
    persistence_module._service = OptionsFlowPersistence(
        db_path=str(tmp_path / "options_radar_api.db")
    )
    app = FastAPI()
    app.include_router(router)
    client = TestClient(app)

    response = client.get("/api/v1/options-radar/top?limit=1")

    assert response.status_code == 200
    payload = response.json()
    assert payload["candidates"]
    assert payload["candidates"][0]["trust"]["synthetic"] is True
    assert payload["trust"]["mode"] == "mock"
