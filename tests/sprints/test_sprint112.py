"""Sprint 112 — Auto-Experiment Scheduler.

Tests:
  1.  auto_schedule proposes when win_rate < 0.45 (tighten)
  2.  auto_schedule proposes when win_rate > 0.60 (relax)
  3.  auto_schedule skips when win_rate in [0.45, 0.60]
  4.  auto_schedule skips param already in active shadow
  5.  auto_schedule respects max_per_run cap
  6.  auto_schedule handles empty trade_outcomes (no crash)
  7.  auto_schedule handles multiple regimes, worst first
  8.  auto_schedule persists state file
  9.  get_auto_schedule_status returns empty if no state file
  10. get_auto_schedule_status reads persisted state
  11. REST POST /auto-schedule-experiments returns 200 with proposed list
  12. REST GET /auto-schedule-experiments/status returns 200
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import List, Dict, Any

import pytest

# ── helpers ──────────────────────────────────────────────────────────────────


def _patch_auto(tmp_path: Path, monkeypatch):
    """Redirect all file paths to tmp_path."""
    import src.engines.self_learning as sl

    monkeypatch.setattr(sl, "_LEDGER_FILE", tmp_path / "experiment_ledger.json")
    monkeypatch.setattr(sl, "_AB_FILE", tmp_path / "ab_shadow.json")
    monkeypatch.setattr(
        sl, "_AUTO_SCHEDULE_STATE_FILE", tmp_path / "auto_schedule_state.json"
    )
    monkeypatch.setattr(sl, "_REGIME_PARAMS_FILE", tmp_path / "regime_params.json")
    monkeypatch.setattr(sl, "AUDIT_DIR", tmp_path)
    monkeypatch.setattr(
        sl,
        "load_regime_params",
        lambda: {
            "BULL": {
                "ensemble_min_score": 0.33,
                "stop_loss_pct": 0.03,
                "max_position_pct": 0.06,
            },
            "BEAR": {
                "ensemble_min_score": 0.42,
                "stop_loss_pct": 0.025,
                "max_position_pct": 0.035,
            },
            "SIDEWAYS": {
                "ensemble_min_score": 0.38,
                "stop_loss_pct": 0.03,
                "max_position_pct": 0.05,
            },
        },
    )
    monkeypatch.setattr(sl, "save_regime_params", lambda x: None)


def _outcomes_with_win_rate(
    regime: str, n: int, win_rate: float
) -> List[Dict[str, Any]]:
    wins = int(n * win_rate)
    trades = [{"regime": regime, "pnl_pct": 1.0} for _ in range(wins)]
    trades += [{"regime": regime, "pnl_pct": -1.0} for _ in range(n - wins)]
    return trades


# ── 1. proposes when win_rate < 0.45 ─────────────────────────────────────────


def test_auto_schedule_proposes_low_win_rate(tmp_path, monkeypatch):
    _patch_auto(tmp_path, monkeypatch)
    from src.engines.self_learning import auto_schedule_experiments

    trades = _outcomes_with_win_rate("BULL", 20, 0.30)  # below 0.45
    result = auto_schedule_experiments(trades)
    assert result["total_proposed"] >= 1
    assert all(e["win_rate"] < 0.45 for e in result["proposed"])


# ── 2. proposes when win_rate > 0.60 ─────────────────────────────────────────


def test_auto_schedule_proposes_high_win_rate(tmp_path, monkeypatch):
    _patch_auto(tmp_path, monkeypatch)
    from src.engines.self_learning import auto_schedule_experiments

    trades = _outcomes_with_win_rate("BEAR", 20, 0.75)  # above 0.60
    result = auto_schedule_experiments(trades)
    assert result["total_proposed"] >= 1
    assert all(e["win_rate"] > 0.60 for e in result["proposed"])


# ── 3. skips when win_rate in range ──────────────────────────────────────────


def test_auto_schedule_skips_in_range(tmp_path, monkeypatch):
    _patch_auto(tmp_path, monkeypatch)
    from src.engines.self_learning import auto_schedule_experiments

    trades = _outcomes_with_win_rate("SIDEWAYS", 20, 0.52)  # 0.45–0.60
    result = auto_schedule_experiments(trades)
    assert result["total_proposed"] == 0


# ── 4. skips param already in active shadow ───────────────────────────────────


def test_auto_schedule_skips_active_shadow(tmp_path, monkeypatch):
    _patch_auto(tmp_path, monkeypatch)
    import src.engines.self_learning as sl
    from src.engines.self_learning import auto_schedule_experiments

    # Pre-seed ab_shadow with ensemble_min_score already active
    ab_file = tmp_path / "ab_shadow.json"
    ab_file.write_text(
        json.dumps(
            {
                "challenger": {
                    "ensemble_min_score": {"value": 0.35, "status": "shadow"},
                    "max_position_pct": {"value": 0.05, "status": "shadow"},
                    "stop_loss_pct": {"value": 0.025, "status": "shadow"},
                },
                "champion": {},
            }
        )
    )

    trades = _outcomes_with_win_rate("BULL", 20, 0.30)
    result = auto_schedule_experiments(trades)
    assert result["total_proposed"] == 0
    assert any(
        "already in active shadow" in s.get("reason", "") for s in result["skipped"]
    )


# ── 5. max_per_run cap ────────────────────────────────────────────────────────


def test_auto_schedule_respects_max_per_run(tmp_path, monkeypatch):
    _patch_auto(tmp_path, monkeypatch)
    from src.engines.self_learning import auto_schedule_experiments

    trades = (
        _outcomes_with_win_rate("BULL", 20, 0.30)
        + _outcomes_with_win_rate("BEAR", 20, 0.75)
        + _outcomes_with_win_rate("SIDEWAYS", 20, 0.20)
    )
    result = auto_schedule_experiments(trades, max_per_run=2)
    assert result["total_proposed"] <= 2


# ── 6. empty trade outcomes ───────────────────────────────────────────────────


def test_auto_schedule_empty_outcomes(tmp_path, monkeypatch):
    _patch_auto(tmp_path, monkeypatch)
    from src.engines.self_learning import auto_schedule_experiments

    result = auto_schedule_experiments([])
    assert result["total_proposed"] == 0
    assert isinstance(result["proposed"], list)


# ── 7. worst regimes scheduled first ─────────────────────────────────────────


def test_auto_schedule_worst_first(tmp_path, monkeypatch):
    _patch_auto(tmp_path, monkeypatch)
    from src.engines.self_learning import auto_schedule_experiments

    # SIDEWAYS at 0.20 (far from 0.50) should be proposed before BULL at 0.43
    trades = _outcomes_with_win_rate("SIDEWAYS", 20, 0.20) + _outcomes_with_win_rate(
        "BULL", 20, 0.43
    )
    result = auto_schedule_experiments(trades, max_per_run=1)
    assert result["total_proposed"] == 1
    assert result["proposed"][0]["regime"] == "SIDEWAYS"


# ── 8. persists state file ────────────────────────────────────────────────────


def test_auto_schedule_persists_state(tmp_path, monkeypatch):
    _patch_auto(tmp_path, monkeypatch)
    from src.engines.self_learning import auto_schedule_experiments

    trades = _outcomes_with_win_rate("BULL", 20, 0.30)
    auto_schedule_experiments(trades)
    state_file = tmp_path / "auto_schedule_state.json"
    assert state_file.exists()
    state = json.loads(state_file.read_text())
    assert "run_at" in state
    assert "total_proposed" in state


# ── 9. get_auto_schedule_status returns empty when no file ────────────────────


def test_get_auto_schedule_status_empty(tmp_path, monkeypatch):
    _patch_auto(tmp_path, monkeypatch)
    from src.engines.self_learning import get_auto_schedule_status

    status = get_auto_schedule_status()
    assert status["run_at"] is None
    assert status["total_proposed"] == 0


# ── 10. get_auto_schedule_status reads persisted state ───────────────────────


def test_get_auto_schedule_status_reads_state(tmp_path, monkeypatch):
    _patch_auto(tmp_path, monkeypatch)
    from src.engines.self_learning import (
        auto_schedule_experiments,
        get_auto_schedule_status,
    )

    trades = _outcomes_with_win_rate("BEAR", 20, 0.75)
    auto_schedule_experiments(trades)
    status = get_auto_schedule_status()
    assert status["run_at"] is not None


# ── 11. REST POST /auto-schedule-experiments returns 200 ─────────────────────


def test_rest_auto_schedule_post_200(tmp_path, monkeypatch):
    _patch_auto(tmp_path, monkeypatch)
    import src.engines.self_learning as sl

    monkeypatch.setenv("API_KEY", "test-key-112")
    monkeypatch.setattr(
        sl,
        "pull_closed_trades_from_learning_loop",
        lambda: _outcomes_with_win_rate("BULL", 20, 0.30),
    )

    from fastapi import FastAPI
    from fastapi.testclient import TestClient
    from src.api.routers.self_learn import router

    app = FastAPI()
    app.include_router(router)
    client = TestClient(app, raise_server_exceptions=True)

    resp = client.post(
        "/api/v7/self-learn/auto-schedule-experiments",
        headers={"X-API-Key": "test-key-112"},
    )
    assert resp.status_code == 200
    body = resp.json()
    assert "proposed" in body
    assert "total_proposed" in body


# ── 12. REST GET /auto-schedule-experiments/status returns 200 ───────────────


def test_rest_auto_schedule_status_200(tmp_path, monkeypatch):
    _patch_auto(tmp_path, monkeypatch)
    monkeypatch.setenv("API_KEY", "test-key-112")

    from fastapi import FastAPI
    from fastapi.testclient import TestClient
    from src.api.routers.self_learn import router

    app = FastAPI()
    app.include_router(router)
    client = TestClient(app, raise_server_exceptions=True)

    resp = client.get(
        "/api/v7/self-learn/auto-schedule-experiments/status",
        headers={"X-API-Key": "test-key-112"},
    )
    assert resp.status_code == 200
    body = resp.json()
    assert "total_proposed" in body
