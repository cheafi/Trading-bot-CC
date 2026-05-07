"""Sprint 113 — Closed-Trade Auto-Feedback Pipeline.

Tests:
  1.  process_closed_trade updates Brier channel
  2.  process_closed_trade updates Thompson channel
  3.  process_closed_trade updates Feature IC channel when feats present
  4.  process_closed_trade updates A/B shadow channel for active challengers
  5.  process_closed_trade win detection — pnl_pct > 0 treated as win
  6.  process_closed_trade win detection — outcome="win" string
  7.  process_closed_trade channels_updated count correct
  8.  process_closed_trade persists feedback_stats.json
  9.  process_closed_trades_batch aggregates correctly
  10. get_feedback_stats returns empty struct when no file
  11. REST POST /feedback/process-closed-trade returns 200
  12. REST GET /feedback/stats returns 200 with expected keys
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Dict
from unittest.mock import MagicMock, patch

import pytest

# ── helpers ──────────────────────────────────────────────────────────────────


def _patch_feedback(tmp_path: Path, monkeypatch):
    import src.engines.self_learning as sl

    monkeypatch.setattr(sl, "_BRIER_FILE", tmp_path / "brier_scores.json")
    monkeypatch.setattr(sl, "_AB_FILE", tmp_path / "ab_shadow.json")
    monkeypatch.setattr(sl, "_FEEDBACK_STATS_FILE", tmp_path / "feedback_stats.json")
    monkeypatch.setattr(sl, "AUDIT_DIR", tmp_path)


def _make_trade(**kwargs) -> Dict[str, Any]:
    defaults: Dict[str, Any] = {
        "strategy": "MOMENTUM",
        "regime": "BULL",
        "pnl_pct": 2.5,
        "outcome": "win",
        "final_confidence": 0.75,
        "forward_return_pct": 2.5,
        "mae_pct": 0.8,
        "rs_composite": 0.6,
    }
    return {**defaults, **kwargs}


# ── 1. Brier channel updated ─────────────────────────────────────────────────


def test_process_trade_updates_brier(tmp_path, monkeypatch):
    _patch_feedback(tmp_path, monkeypatch)
    import src.engines.self_learning as sl

    brier_calls = []
    orig = sl.record_prediction_outcome

    def spy(*a, **kw):
        brier_calls.append((a, kw))
        return orig(*a, **kw)

    monkeypatch.setattr(sl, "record_prediction_outcome", spy)

    with patch(
        "src.engines.thompson_sizing.get_thompson_engine", return_value=MagicMock()
    ):
        with patch("src.engines.feature_ic.record_feature_outcomes", return_value=None):
            from src.engines.self_learning import process_closed_trade

            result = process_closed_trade(_make_trade())

    assert len(brier_calls) == 1
    assert result["brier"] is not None


# ── 2. Thompson channel updated ───────────────────────────────────────────────


def test_process_trade_updates_thompson(tmp_path, monkeypatch):
    _patch_feedback(tmp_path, monkeypatch)
    mock_eng = MagicMock()

    with patch(
        "src.engines.thompson_sizing.get_thompson_engine", return_value=mock_eng
    ):
        with patch("src.engines.feature_ic.record_feature_outcomes"):
            from src.engines.self_learning import process_closed_trade

            result = process_closed_trade(_make_trade())

    mock_eng.update.assert_called_once()
    assert result["thompson"] is True


# ── 3. Feature IC channel updated ─────────────────────────────────────────────


def test_process_trade_updates_feature_ic(tmp_path, monkeypatch):
    _patch_feedback(tmp_path, monkeypatch)
    ic_calls = []

    with patch(
        "src.engines.thompson_sizing.get_thompson_engine", return_value=MagicMock()
    ):
        with patch(
            "src.engines.feature_ic.record_feature_outcomes",
            side_effect=lambda f, **kw: ic_calls.append(f),
        ):
            from src.engines.self_learning import process_closed_trade

            result = process_closed_trade(_make_trade(rs_composite=0.7))

    assert len(ic_calls) == 1
    assert result["feature_ic"] is True


# ── 4. A/B shadow channel updated for active challengers ─────────────────────


def test_process_trade_updates_ab_shadow(tmp_path, monkeypatch):
    _patch_feedback(tmp_path, monkeypatch)
    ab_file = tmp_path / "ab_shadow.json"
    ab_file.write_text(
        json.dumps(
            {
                "challenger": {
                    "ensemble_min_score": {
                        "value": 0.35,
                        "status": "shadow",
                        "shadow_trades": 0,
                        "shadow_wins": 0,
                        "days_tracked": 0,
                    }
                },
                "champion": {},
            }
        )
    )

    with patch(
        "src.engines.thompson_sizing.get_thompson_engine", return_value=MagicMock()
    ):
        with patch("src.engines.feature_ic.record_feature_outcomes"):
            from src.engines.self_learning import process_closed_trade

            result = process_closed_trade(_make_trade())

    assert "ensemble_min_score" in result["ab_updated"]


# ── 5. win detection via pnl_pct ─────────────────────────────────────────────


def test_process_trade_win_from_pnl(tmp_path, monkeypatch):
    _patch_feedback(tmp_path, monkeypatch)
    brier_calls = []
    import src.engines.self_learning as sl

    orig = sl.record_prediction_outcome

    def spy(*a, **kw):
        brier_calls.append(kw.get("actual_win", a[1] if len(a) > 1 else None))
        return orig(*a, **kw)

    monkeypatch.setattr(sl, "record_prediction_outcome", spy)

    with patch(
        "src.engines.thompson_sizing.get_thompson_engine", return_value=MagicMock()
    ):
        with patch("src.engines.feature_ic.record_feature_outcomes"):
            from src.engines.self_learning import process_closed_trade

            process_closed_trade(
                _make_trade(pnl_pct=3.0, outcome="")
            )  # no outcome string

    assert brier_calls[0] is True  # inferred from pnl_pct > 0


# ── 6. win detection via outcome string ──────────────────────────────────────


def test_process_trade_win_from_outcome_string(tmp_path, monkeypatch):
    _patch_feedback(tmp_path, monkeypatch)
    brier_calls = []
    import src.engines.self_learning as sl

    orig = sl.record_prediction_outcome

    def spy(*a, **kw):
        brier_calls.append(kw.get("actual_win", a[1] if len(a) > 1 else None))
        return orig(*a, **kw)

    monkeypatch.setattr(sl, "record_prediction_outcome", spy)

    with patch(
        "src.engines.thompson_sizing.get_thompson_engine", return_value=MagicMock()
    ):
        with patch("src.engines.feature_ic.record_feature_outcomes"):
            from src.engines.self_learning import process_closed_trade

            process_closed_trade(_make_trade(pnl_pct=-1.0, outcome="WIN"))  # uppercase

    assert brier_calls[0] is True


# ── 7. channels_updated count ────────────────────────────────────────────────


def test_process_trade_channels_updated_count(tmp_path, monkeypatch):
    _patch_feedback(tmp_path, monkeypatch)

    with patch(
        "src.engines.thompson_sizing.get_thompson_engine", return_value=MagicMock()
    ):
        with patch("src.engines.feature_ic.record_feature_outcomes"):
            from src.engines.self_learning import process_closed_trade

            result = process_closed_trade(_make_trade())

    # Brier + Thompson + Feature IC = 3 (AB skipped, no active challengers)
    assert result["channels_updated"] >= 3


# ── 8. persists feedback_stats.json ──────────────────────────────────────────


def test_process_trade_persists_stats(tmp_path, monkeypatch):
    _patch_feedback(tmp_path, monkeypatch)
    stats_file = tmp_path / "feedback_stats.json"

    with patch(
        "src.engines.thompson_sizing.get_thompson_engine", return_value=MagicMock()
    ):
        with patch("src.engines.feature_ic.record_feature_outcomes"):
            from src.engines.self_learning import process_closed_trade

            process_closed_trade(_make_trade())
            process_closed_trade(_make_trade())

    assert stats_file.exists()
    stats = json.loads(stats_file.read_text())
    assert stats["total_processed"] == 2
    assert stats["last_processed_at"] is not None


# ── 9. batch aggregates correctly ────────────────────────────────────────────


def test_process_closed_trades_batch(tmp_path, monkeypatch):
    _patch_feedback(tmp_path, monkeypatch)

    with patch(
        "src.engines.thompson_sizing.get_thompson_engine", return_value=MagicMock()
    ):
        with patch("src.engines.feature_ic.record_feature_outcomes"):
            from src.engines.self_learning import process_closed_trades_batch

            result = process_closed_trades_batch(
                [_make_trade(), _make_trade(), _make_trade()]
            )

    assert result["total"] == 3
    assert result["channels"]["thompson"] == 3
    assert result["channels"]["brier"] == 3


# ── 10. get_feedback_stats returns empty when no file ─────────────────────────


def test_get_feedback_stats_empty(tmp_path, monkeypatch):
    _patch_feedback(tmp_path, monkeypatch)
    from src.engines.self_learning import get_feedback_stats

    stats = get_feedback_stats()
    assert stats["total_processed"] == 0
    assert stats["last_processed_at"] is None


# ── 11. REST POST /feedback/process-closed-trade ─────────────────────────────


def test_rest_feedback_process_trade_200(tmp_path, monkeypatch):
    _patch_feedback(tmp_path, monkeypatch)
    monkeypatch.setenv("API_KEY", "test-key-113")

    with patch(
        "src.engines.thompson_sizing.get_thompson_engine", return_value=MagicMock()
    ):
        with patch("src.engines.feature_ic.record_feature_outcomes"):
            from fastapi import FastAPI
            from fastapi.testclient import TestClient
            from src.api.routers.self_learn import router

            app = FastAPI()
            app.include_router(router)
            client = TestClient(app, raise_server_exceptions=True)

            resp = client.post(
                "/api/v7/self-learn/feedback/process-closed-trade",
                json=_make_trade(),
                headers={"X-API-Key": "test-key-113"},
            )

    assert resp.status_code == 200
    body = resp.json()
    assert "brier" in body
    assert "thompson" in body
    assert "channels_updated" in body


# ── 12. REST GET /feedback/stats returns 200 ─────────────────────────────────


def test_rest_feedback_stats_200(tmp_path, monkeypatch):
    _patch_feedback(tmp_path, monkeypatch)
    monkeypatch.setenv("API_KEY", "test-key-113")

    from fastapi import FastAPI
    from fastapi.testclient import TestClient
    from src.api.routers.self_learn import router

    app = FastAPI()
    app.include_router(router)
    client = TestClient(app, raise_server_exceptions=True)

    resp = client.get(
        "/api/v7/self-learn/feedback/stats",
        headers={"X-API-Key": "test-key-113"},
    )
    assert resp.status_code == 200
    body = resp.json()
    assert "total_processed" in body
    assert "active_shadow_count" in body
