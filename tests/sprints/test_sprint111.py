"""Sprint 111 — Experiment Ledger / Keep-Discard Board.

Tests:
  1.  _append_ledger writes a file
  2.  _append_ledger rolling cap (_LEDGER_MAX)
  3.  get_experiment_ledger returns newest-first
  4.  get_experiment_ledger filter by status
  5.  get_experiment_ledger filter by param
  6.  get_experiment_ledger empty ledger returns []
  7.  get_experiment_ledger limit respected
  8.  propose_ab_shadow wires ledger (status='shadow')
  9.  evaluate_ab_promotion wires ledger on promote (status='promoted')
  10. evaluate_ab_promotion wires ledger on discard (status='discarded')
  11. REST GET /api/v7/self-learn/experiment-ledger returns 200
  12. REST experiment-ledger?status=promoted filter works
"""

from __future__ import annotations

import json
import types
import unittest.mock as mock
from pathlib import Path

import pytest

# ── helpers ─────────────────────────────────────────────────────────────────


def _patch_ledger(tmp_path: Path, monkeypatch):
    """Redirect ledger and AB file to tmp_path."""
    import src.engines.self_learning as sl

    ledger_file = tmp_path / "experiment_ledger.json"
    ab_file = tmp_path / "ab_shadow.json"
    monkeypatch.setattr(sl, "_LEDGER_FILE", ledger_file)
    monkeypatch.setattr(sl, "_AB_FILE", ab_file)
    monkeypatch.setattr(sl, "AUDIT_DIR", tmp_path)
    return ledger_file, ab_file


# ── 1. _append_ledger writes file ──────────────────────────────────────────


def test_append_ledger_writes_file(tmp_path, monkeypatch):
    ledger_file, _ = _patch_ledger(tmp_path, monkeypatch)
    from src.engines.self_learning import _append_ledger

    _append_ledger({"param": "min_score", "status": "shadow"})
    assert ledger_file.exists()
    data = json.loads(ledger_file.read_text())
    assert len(data) == 1
    assert data[0]["param"] == "min_score"


# ── 2. rolling cap ────────────────────────────────────────────────────────


def test_append_ledger_rolling_cap(tmp_path, monkeypatch):
    ledger_file, _ = _patch_ledger(tmp_path, monkeypatch)
    import src.engines.self_learning as sl
    from src.engines.self_learning import _append_ledger

    monkeypatch.setattr(sl, "_LEDGER_MAX", 5)
    for i in range(8):
        _append_ledger({"seq": i, "status": "shadow"})
    data = json.loads(ledger_file.read_text())
    assert len(data) == 5
    assert data[-1]["seq"] == 7  # newest is last raw entry


# ── 3. get_experiment_ledger newest-first ─────────────────────────────────


def test_get_experiment_ledger_newest_first(tmp_path, monkeypatch):
    _patch_ledger(tmp_path, monkeypatch)
    from src.engines.self_learning import _append_ledger, get_experiment_ledger

    for i in range(3):
        _append_ledger(
            {"experiment_id": f"ab_p_{i}", "param": "p", "status": "shadow", "seq": i}
        )
    entries = get_experiment_ledger()
    assert entries[0]["seq"] == 2  # newest first


# ── 4. filter by status ───────────────────────────────────────────────────


def test_get_experiment_ledger_filter_status(tmp_path, monkeypatch):
    _patch_ledger(tmp_path, monkeypatch)
    from src.engines.self_learning import _append_ledger, get_experiment_ledger

    _append_ledger({"experiment_id": "x1", "param": "a", "status": "shadow"})
    _append_ledger({"experiment_id": "x1", "param": "a", "status": "promoted"})
    _append_ledger({"experiment_id": "x2", "param": "b", "status": "shadow"})
    promoted = get_experiment_ledger(status="promoted")
    assert all(e["status"] == "promoted" for e in promoted)


# ── 5. filter by param ────────────────────────────────────────────────────


def test_get_experiment_ledger_filter_param(tmp_path, monkeypatch):
    _patch_ledger(tmp_path, monkeypatch)
    from src.engines.self_learning import _append_ledger, get_experiment_ledger

    _append_ledger({"experiment_id": "a1", "param": "alpha", "status": "shadow"})
    _append_ledger({"experiment_id": "b1", "param": "beta", "status": "shadow"})
    entries = get_experiment_ledger(param="alpha")
    assert all(e["param"] == "alpha" for e in entries)
    assert len(entries) == 1


# ── 6. empty ledger ───────────────────────────────────────────────────────


def test_get_experiment_ledger_empty(tmp_path, monkeypatch):
    _patch_ledger(tmp_path, monkeypatch)
    from src.engines.self_learning import get_experiment_ledger

    assert get_experiment_ledger() == []


# ── 7. limit respected ────────────────────────────────────────────────────


def test_get_experiment_ledger_limit(tmp_path, monkeypatch):
    _patch_ledger(tmp_path, monkeypatch)
    from src.engines.self_learning import _append_ledger, get_experiment_ledger

    for i in range(20):
        _append_ledger({"experiment_id": f"ab_{i}", "param": "p", "status": "shadow"})
    assert len(get_experiment_ledger(limit=5)) == 5


# ── 8. propose_ab_shadow wires ledger ─────────────────────────────────────


def test_propose_ab_shadow_writes_ledger(tmp_path, monkeypatch):
    ledger_file, _ = _patch_ledger(tmp_path, monkeypatch)
    import src.engines.self_learning as sl
    from src.engines.self_learning import propose_ab_shadow

    # Patch regime_params so champion lookup doesn't fail
    monkeypatch.setattr(sl, "load_regime_params", lambda: {})
    monkeypatch.setattr(sl, "TUNABLE_RULES", {"min_score": {"default": 0.60}})

    propose_ab_shadow("min_score", 0.65, reason="test proposal")

    assert ledger_file.exists()
    data = json.loads(ledger_file.read_text())
    assert len(data) == 1
    entry = data[0]
    assert entry["param"] == "min_score"
    assert entry["status"] == "shadow"
    assert entry["challenger_value"] == 0.65


# ── 9. evaluate_ab_promotion — promoted path ──────────────────────────────


def test_evaluate_ab_promotion_writes_promoted(tmp_path, monkeypatch):
    ledger_file, ab_file = _patch_ledger(tmp_path, monkeypatch)
    import src.engines.self_learning as sl
    from src.engines.self_learning import evaluate_ab_promotion

    # Pre-populate ab_shadow.json with a shadow challenger that meets criteria
    ab_data = {
        "challenger": {
            "min_score": {
                "value": 0.65,
                "champion_value": 0.60,
                "reason": "test",
                "proposed_at": "2025-01-01T00:00:00+00:00",
                "days_tracked": 5,
                "shadow_wins": 26,
                "shadow_trades": 40,
                "status": "shadow",
                "experiment_id": "ab_min_score_202501",
            }
        },
        "champion": {},
    }
    ab_file.write_text(json.dumps(ab_data))

    monkeypatch.setattr(sl, "load_regime_params", lambda: {})
    monkeypatch.setattr(sl, "save_regime_params", lambda x: None)

    result = evaluate_ab_promotion("min_score")
    assert result["promoted"] is True
    data = json.loads(ledger_file.read_text())
    assert any(e["status"] == "promoted" for e in data)


# ── 10. evaluate_ab_promotion — discarded path ───────────────────────────


def test_evaluate_ab_promotion_writes_discarded(tmp_path, monkeypatch):
    ledger_file, ab_file = _patch_ledger(tmp_path, monkeypatch)
    import src.engines.self_learning as sl
    from src.engines.self_learning import evaluate_ab_promotion

    ab_data = {
        "challenger": {
            "min_score": {
                "value": 0.65,
                "champion_value": 0.60,
                "reason": "test",
                "proposed_at": "2025-01-01T00:00:00+00:00",
                "days_tracked": 5,
                "shadow_wins": 5,  # low win rate
                "shadow_trades": 40,
                "status": "shadow",
                "experiment_id": "ab_min_score_discard",
            }
        },
        "champion": {},
    }
    ab_file.write_text(json.dumps(ab_data))
    monkeypatch.setattr(sl, "load_regime_params", lambda: {})

    result = evaluate_ab_promotion("min_score")
    assert result["promoted"] is False
    data = json.loads(ledger_file.read_text())
    assert any(e["status"] == "discarded" for e in data)


# ── 11. REST GET /experiment-ledger returns 200 ───────────────────────────


def test_rest_experiment_ledger_200(tmp_path, monkeypatch):
    from fastapi.testclient import TestClient

    _patch_ledger(tmp_path, monkeypatch)
    import src.engines.self_learning as sl

    monkeypatch.setenv("API_KEY", "test-key-111")
    monkeypatch.setattr(sl, "load_regime_params", lambda: {})

    from src.api.routers.self_learn import router
    from fastapi import FastAPI

    app = FastAPI()
    app.include_router(router)

    client = TestClient(app, raise_server_exceptions=True)
    resp = client.get(
        "/api/v7/self-learn/experiment-ledger",
        headers={"X-API-Key": "test-key-111"},
    )
    assert resp.status_code == 200
    body = resp.json()
    assert "entries" in body
    assert "total" in body


# ── 12. REST filter ?status=promoted ─────────────────────────────────────


def test_rest_experiment_ledger_filter(tmp_path, monkeypatch):
    ledger_file, _ = _patch_ledger(tmp_path, monkeypatch)
    import src.engines.self_learning as sl

    monkeypatch.setenv("API_KEY", "test-key-111")
    monkeypatch.setattr(sl, "load_regime_params", lambda: {})

    # Seed ledger with mixed statuses
    entries = [
        {"experiment_id": "x1", "param": "p", "status": "promoted"},
        {"experiment_id": "x2", "param": "q", "status": "discarded"},
    ]
    ledger_file.write_text(json.dumps(entries))

    from src.api.routers.self_learn import router
    from fastapi import FastAPI
    from fastapi.testclient import TestClient

    app = FastAPI()
    app.include_router(router)
    client = TestClient(app, raise_server_exceptions=True)

    resp = client.get(
        "/api/v7/self-learn/experiment-ledger?status=promoted",
        headers={"X-API-Key": "test-key-111"},
    )
    assert resp.status_code == 200
    body = resp.json()
    assert all(e["status"] == "promoted" for e in body["entries"])
