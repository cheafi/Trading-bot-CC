"""Whole-page CC Time Travel replay tests."""

from __future__ import annotations

import pytest

from src.services.cc_replay_service import (
    ReplaySnapshotError,
    build_replay_cc_header_overlay,
    build_replay_ranked_payload,
    build_replay_today_payload,
    list_replay_dates,
    resolve_brief_for_as_of,
)


def test_list_replay_dates_returns_brief_files():
    dates = list_replay_dates()
    assert isinstance(dates, list)
    if dates:
        assert all(len(d) == 10 and d[4] == "-" for d in dates)


def test_resolve_brief_exact_or_nearest():
    dates = list_replay_dates()
    if not dates:
        pytest.skip("no brief snapshots in data/")
    exact = dates[0]
    resolved, brief, note = resolve_brief_for_as_of(exact)
    assert resolved == exact
    assert isinstance(brief, dict)
    assert note is None


def test_resolve_brief_invalid_date_raises():
    with pytest.raises(ReplaySnapshotError):
        resolve_brief_for_as_of("not-a-date")


def test_replay_today_payload_blocks_deploy():
    dates = list_replay_dates()
    if not dates:
        pytest.skip("no brief snapshots in data/")
    payload = build_replay_today_payload(dates[0])
    assert payload["replay_mode"] is True
    assert payload["replay_as_of"] == dates[0]
    assert payload["system_truth"]["deploy_authority"] is False
    assert payload["decision_authority"]["deploy_authority"] is False
    assert payload["unlock_deploy"]["unlocked"] is False
    assert payload["execution_readiness"]["trade_handoff_ready"] is False
    assert payload["market_regime"]["replay_snapshot"] is True
    assert isinstance(payload.get("top_5"), list)


def test_replay_ranked_payload_blocks_deploy():
    dates = list_replay_dates()
    if not dates:
        pytest.skip("no brief snapshots in data/")
    payload = build_replay_ranked_payload(dates[0], limit=10)
    assert payload["replay_mode"] is True
    assert payload["decision_authority"]["deploy_authority"] is False
    assert payload["system_truth"]["deploy_authority"] is False
    assert "opportunities" in payload


def test_replay_cc_header_overlay():
    dates = list_replay_dates()
    if not dates:
        pytest.skip("no brief snapshots in data/")
    overlay = build_replay_cc_header_overlay(dates[0])
    assert overlay["display_mode"] == "BACKTEST"
    assert overlay["replay_mode"] is True
    assert overlay["decision_authority"]["deploy_authority"] is False


@pytest.mark.asyncio
async def test_today_endpoint_accepts_as_of(client):
    dates = list_replay_dates()
    if not dates:
        pytest.skip("no brief snapshots in data/")
    response = await client.get(f"/api/v7/today?as_of={dates[0]}")
    assert response.status_code == 200
    data = response.json()
    assert data["replay_mode"] is True
    assert data["system_truth"]["deploy_authority"] is False


@pytest.mark.asyncio
async def test_today_endpoint_as_of_missing_date_returns_404(client):
    response = await client.get("/api/v7/today?as_of=1999-01-01")
    assert response.status_code == 404
    detail = response.json().get("detail")
    if isinstance(detail, dict):
        assert "available_dates" in detail


@pytest.mark.asyncio
async def test_replay_dates_endpoint(client):
    response = await client.get("/api/cc/replay/dates")
    assert response.status_code == 200
    body = response.json()
    assert "dates" in body
    assert "hint" in body


@pytest.mark.asyncio
async def test_playbook_ranked_as_of(client):
    dates = list_replay_dates()
    if not dates:
        pytest.skip("no brief snapshots in data/")
    response = await client.get(f"/api/v7/playbook/ranked?as_of={dates[0]}&limit=10")
    assert response.status_code == 200
    data = response.json()
    assert data["replay_mode"] is True
    assert data["decision_authority"]["deploy_authority"] is False
