"""
Sprint 110 — Confidence Calibration Buckets
============================================
Tests for:
- record_prediction_outcome extended signature (fwd_return, mae, regime)
- get_calibration_buckets() grouping, hit_rate, avg_forward_return, avg_mae
- ECE computation
- regime breakdown per bucket
- /calibration/buckets REST endpoint
"""

from __future__ import annotations

import json
import os
import tempfile
from pathlib import Path
from unittest.mock import patch

import pytest
from fastapi.testclient import TestClient

# ── Helpers ──────────────────────────────────────────────────────────────────


def _patched_brier_path(tmp_path: Path):
    """Return a context manager that redirects _BRIER_FILE to a temp file."""
    brier_file = tmp_path / "brier_scores.json"
    return patch("src.engines.self_learning._BRIER_FILE", brier_file)


def _seed_history(tmp_path: Path, records: list[dict]):
    """Write records directly to the temp brier file."""
    brier_file = tmp_path / "brier_scores.json"
    brier_file.write_text(json.dumps({"history": records}))


# ── Tests: record_prediction_outcome extended ─────────────────────────────────


class TestRecordOutcomeExtended:
    def test_stores_forward_return(self, tmp_path):
        from src.engines.self_learning import (
            record_prediction_outcome,
            _load_brier_data,
        )

        with _patched_brier_path(tmp_path):
            for i in range(6):
                record_prediction_outcome(
                    0.75, True, forward_return_pct=3.5, mae_pct=1.2, regime="BULL"
                )
            from src.engines.self_learning import _BRIER_FILE

            data = json.loads(_BRIER_FILE.read_text())

        entry = data["history"][-1]
        assert "fwd_ret" in entry
        assert entry["fwd_ret"] == pytest.approx(3.5, abs=0.01)

    def test_stores_mae(self, tmp_path):
        from src.engines.self_learning import record_prediction_outcome

        with _patched_brier_path(tmp_path):
            record_prediction_outcome(0.70, False, mae_pct=2.1)
            from src.engines.self_learning import _BRIER_FILE

            data = json.loads(_BRIER_FILE.read_text())

        entry = data["history"][-1]
        assert "mae" in entry
        assert entry["mae"] == pytest.approx(2.1, abs=0.01)

    def test_stores_regime(self, tmp_path):
        from src.engines.self_learning import record_prediction_outcome

        with _patched_brier_path(tmp_path):
            record_prediction_outcome(0.65, True, regime="BEAR")
            from src.engines.self_learning import _BRIER_FILE

            data = json.loads(_BRIER_FILE.read_text())

        entry = data["history"][-1]
        assert entry.get("regime") == "BEAR"

    def test_no_fwd_stored_when_zero(self, tmp_path):
        """When forward_return_pct=0 (default), do not pollute history entry."""
        from src.engines.self_learning import record_prediction_outcome

        with _patched_brier_path(tmp_path):
            record_prediction_outcome(0.60, True)
            from src.engines.self_learning import _BRIER_FILE

            data = json.loads(_BRIER_FILE.read_text())

        entry = data["history"][-1]
        assert "fwd_ret" not in entry

    def test_backward_compat_old_format(self, tmp_path):
        """Old-format entries (no fwd_ret/mae/regime) should still compute Brier via record call."""
        from src.engines.self_learning import record_prediction_outcome

        last = None
        with _patched_brier_path(tmp_path):
            for _ in range(10):
                last = record_prediction_outcome(0.7, True)
        assert last is not None
        assert last["window"] >= 5


# ── Tests: get_calibration_buckets ────────────────────────────────────────────


class TestCalibrationBuckets:
    def _make_records(
        self,
        conf: float,
        n: int,
        win_rate: float,
        fwd_ret: float = 2.0,
        mae: float = 0.8,
        regime: str = "BULL",
    ):
        """Build n synthetic records at a given conf/win_rate."""
        records = []
        wins = int(n * win_rate)
        for i in range(n):
            records.append(
                {
                    "conf": conf,
                    "win": 1 if i < wins else 0,
                    "fwd_ret": fwd_ret if i < wins else -fwd_ret,
                    "mae": mae,
                    "regime": regime,
                }
            )
        return records

    def test_buckets_structure(self, tmp_path):
        from src.engines.self_learning import get_calibration_buckets

        records = self._make_records(0.75, 10, 0.7)
        _seed_history(tmp_path, records)

        with _patched_brier_path(tmp_path):
            result = get_calibration_buckets()

        assert "buckets" in result
        assert len(result["buckets"]) == 5  # 50-60, 60-70, 70-80, 80-90, 90+
        labels = [b["bucket"] for b in result["buckets"]]
        assert "70-80" in labels
        assert "90+" in labels

    def test_hit_rate_correct(self, tmp_path):
        from src.engines.self_learning import get_calibration_buckets

        # 10 records at conf=0.75 (→ 70-80 bucket), 7 wins
        records = self._make_records(0.75, 10, 0.7)
        _seed_history(tmp_path, records)

        with _patched_brier_path(tmp_path):
            result = get_calibration_buckets()

        bucket = next(b for b in result["buckets"] if b["bucket"] == "70-80")
        assert bucket["n"] == 10
        assert bucket["hit_rate"] == pytest.approx(0.7, abs=0.001)

    def test_avg_forward_return(self, tmp_path):
        from src.engines.self_learning import get_calibration_buckets

        # 10 records: 7 wins with fwd=3.0, 3 losses with fwd=-3.0
        records = self._make_records(0.75, 10, 0.7, fwd_ret=3.0)
        _seed_history(tmp_path, records)

        with _patched_brier_path(tmp_path):
            result = get_calibration_buckets()

        bucket = next(b for b in result["buckets"] if b["bucket"] == "70-80")
        expected = (7 * 3.0 + 3 * -3.0) / 10  # = 1.2
        assert bucket["avg_forward_return_pct"] == pytest.approx(expected, abs=0.01)

    def test_avg_mae(self, tmp_path):
        from src.engines.self_learning import get_calibration_buckets

        records = self._make_records(0.75, 10, 0.7, mae=1.5)
        _seed_history(tmp_path, records)

        with _patched_brier_path(tmp_path):
            result = get_calibration_buckets()

        bucket = next(b for b in result["buckets"] if b["bucket"] == "70-80")
        assert bucket["avg_mae_pct"] == pytest.approx(1.5, abs=0.01)

    def test_empty_bucket_n_zero(self, tmp_path):
        from src.engines.self_learning import get_calibration_buckets

        # Only records in 70-80 bucket
        records = self._make_records(0.75, 5, 0.6)
        _seed_history(tmp_path, records)

        with _patched_brier_path(tmp_path):
            result = get_calibration_buckets()

        bucket_90 = next(b for b in result["buckets"] if b["bucket"] == "90+")
        assert bucket_90["n"] == 0
        assert bucket_90["hit_rate"] is None

    def test_calibrated_status_good(self, tmp_path):
        from src.engines.self_learning import get_calibration_buckets

        # conf=0.75 (midpoint=0.75), hit_rate=0.74 → gap=0.01 → good
        records = self._make_records(0.75, 10, 0.74)
        _seed_history(tmp_path, records)

        with _patched_brier_path(tmp_path):
            result = get_calibration_buckets()

        bucket = next(b for b in result["buckets"] if b["bucket"] == "70-80")
        assert bucket["calibrated"] == "good"

    def test_calibrated_status_poor(self, tmp_path):
        from src.engines.self_learning import get_calibration_buckets

        # conf=0.75 but hit_rate=0.40 → gap=0.35 → poor
        records = self._make_records(0.75, 10, 0.40)
        _seed_history(tmp_path, records)

        with _patched_brier_path(tmp_path):
            result = get_calibration_buckets()

        bucket = next(b for b in result["buckets"] if b["bucket"] == "70-80")
        assert bucket["calibrated"] == "poor"

    def test_regime_breakdown(self, tmp_path):
        from src.engines.self_learning import get_calibration_buckets

        bull = self._make_records(0.75, 6, 0.8, regime="BULL")
        bear = self._make_records(0.75, 4, 0.25, regime="BEAR")
        _seed_history(tmp_path, bull + bear)

        with _patched_brier_path(tmp_path):
            result = get_calibration_buckets()

        bucket = next(b for b in result["buckets"] if b["bucket"] == "70-80")
        assert "BULL" in bucket["regime_breakdown"]
        assert "BEAR" in bucket["regime_breakdown"]
        assert bucket["regime_breakdown"]["BULL"]["n"] == 6
        assert bucket["regime_breakdown"]["BEAR"]["n"] == 4

    def test_ece_computed(self, tmp_path):
        from src.engines.self_learning import get_calibration_buckets

        records = self._make_records(0.75, 10, 0.74)
        _seed_history(tmp_path, records)

        with _patched_brier_path(tmp_path):
            result = get_calibration_buckets()

        assert result["ece"] is not None
        assert 0.0 <= result["ece"] <= 0.5

    def test_total_records(self, tmp_path):
        from src.engines.self_learning import get_calibration_buckets

        records = self._make_records(0.75, 12, 0.7)
        _seed_history(tmp_path, records)

        with _patched_brier_path(tmp_path):
            result = get_calibration_buckets()

        assert result["total_records"] == 12


# ── REST endpoint tests ────────────────────────────────────────────────────────


class TestCalibrationBucketsEndpoint:
    @pytest.fixture
    def client(self):
        os.environ.setdefault("API_KEY", "test-key")
        from src.api.main import app

        return TestClient(app)

    def test_endpoint_exists(self, client):
        resp = client.get(
            "/api/v7/self-learn/calibration/buckets",
            headers={"X-API-Key": "test-key"},
        )
        assert resp.status_code == 200

    def test_endpoint_returns_buckets_key(self, client):
        resp = client.get(
            "/api/v7/self-learn/calibration/buckets",
            headers={"X-API-Key": "test-key"},
        )
        data = resp.json()
        assert "buckets" in data
        assert isinstance(data["buckets"], list)
        assert len(data["buckets"]) == 5

    def test_record_endpoint_accepts_new_fields(self, client, tmp_path):
        """POST /calibration/record accepts forward_return_pct, mae_pct, regime."""
        with _patched_brier_path(tmp_path):
            resp = client.post(
                "/api/v7/self-learn/calibration/record"
                "?confidence=0.75&win=true&forward_return_pct=2.5&mae_pct=0.8&regime=BULL",
                headers={"X-API-Key": "test-key"},
            )
        assert resp.status_code == 200
