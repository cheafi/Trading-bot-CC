"""Walk-forward artifacts: compute, atomic save, fail-closed load, evidence routing."""

from __future__ import annotations

import asyncio
import json
import time

import numpy as np
import pandas as pd
import pytest

from src.services import strategy_health_service as shs
from src.services import walk_forward_service as wfs

SID = "brief_rs_leader_v1"


def _bars(n=900, seed=0):
    rng = np.random.default_rng(seed)
    close = 100 * np.exp(np.cumsum(rng.normal(0.0008, 0.015, n)))
    idx = pd.date_range("2021-01-04", periods=n, freq="B")
    return pd.DataFrame(
        {
            "Open": close,
            "High": close * 1.01,
            "Low": close * 0.99,
            "Close": close,
            "Volume": rng.integers(5e5, 3e6, n).astype(float),
        },
        index=idx,
    )


class FakeMDS:
    def __init__(self, missing=()):
        self.missing = set(missing)
        self.calls = []

    async def get_history(self, ticker, period="1y", interval="1d"):
        self.calls.append((ticker, period, interval))
        if ticker in self.missing:
            return None
        return _bars(seed=hash(ticker) % 1000)


def _report(**over):
    rep = {
        "strategy_id": SID,
        "schema_version": wfs.SCHEMA_VERSION,
        "computed_at": time.time(),
        "as_of": "2026-11-13",
        "evidence": {"grade": "PRELIMINARY", "sample_size": 40},
    }
    rep.update(over)
    return rep


def test_compute_uses_5y_and_reports_missing():
    mds = FakeMDS(missing={"ZZZ"})
    rep = asyncio.run(wfs.compute(SID, ["aaa", "BBB", "ZZZ", "SPY"], mds=mds))
    assert rep["missing_tickers"] == ["ZZZ"]
    assert rep["universe"] == ["AAA", "BBB"]
    assert {c[1] for c in mds.calls} == {"5y"}
    assert rep["evidence"]["basis"] == "walk_forward_oos_backtest"
    assert rep["evidence"]["grade"] != "VALIDATED"  # universe not point-in-time


def test_compute_without_benchmark_is_no_backtest():
    rep = asyncio.run(wfs.compute(SID, ["AAA"], mds=FakeMDS(missing={"SPY"})))
    assert rep["evidence"]["grade"] == "NO_BACKTEST"
    assert rep["evidence"]["reason_codes"] == ["NO_BENCHMARK_DATA"]


def test_unknown_strategy_rejected(tmp_path):
    with pytest.raises(KeyError):
        asyncio.run(wfs.compute("../etc/passwd", ["AAA"], mds=FakeMDS()))
    with pytest.raises(KeyError):
        wfs.save(_report(strategy_id="../../x"), directory=tmp_path)
    assert wfs.load("../../x", directory=tmp_path) is None
    assert list(tmp_path.iterdir()) == []


def test_save_load_roundtrip_atomic(tmp_path):
    path = wfs.save(_report(), directory=tmp_path)
    assert path.name == f"{SID}.json"
    assert [p.name for p in tmp_path.iterdir()] == [path.name]
    art = wfs.load(SID, directory=tmp_path)
    assert art["evidence"]["grade"] == "PRELIMINARY" and art["age_s"] >= 0


@pytest.mark.parametrize(
    "mutate",
    [
        lambda r: r.update(computed_at=time.time() - wfs.MAX_ARTIFACT_AGE_S - 10),
        lambda r: r.update(computed_at=time.time() + 3600),
        lambda r: r.update(computed_at="yesterday"),
        lambda r: r.update(schema_version=0),
        lambda r: r.update(strategy_id="other"),
        lambda r: r.update(evidence={}),
    ],
)
def test_stale_or_malformed_artifact_loads_none(tmp_path, mutate):
    rep = _report()
    mutate(rep)
    (tmp_path / f"{SID}.json").write_text(json.dumps(rep))
    assert wfs.load(SID, directory=tmp_path) is None


def test_corrupt_artifact_loads_none(tmp_path):
    (tmp_path / f"{SID}.json").write_text("{not json")
    assert wfs.load(SID, directory=tmp_path) is None


def _ledger(tmp_path, rs):
    path = tmp_path / "closed.jsonl"
    with path.open("w") as fh:
        for i, r in enumerate(rs):
            fh.write(
                json.dumps(
                    {
                        "strategy_id": SID,
                        "r_multiple": r,
                        "closed_at": f"2026-0{1 + i % 9}-01T00:00:00Z",
                    }
                )
                + "\n"
            )
    return str(path)


def test_evidence_prefers_walk_forward(tmp_path, monkeypatch):
    art = {**_report(), "age_s": 1.0}
    monkeypatch.setattr(wfs, "load", lambda sid, **kw: art if sid == SID else None)
    ev = shs.evidence_for_strategy(SID, ledger_path=str(tmp_path / "none.jsonl"))
    assert ev["source"] == "walk_forward" and ev["grade"] == "PRELIMINARY"
    assert (
        shs.evidence_for_strategy("other", ledger_path=str(tmp_path / "none.jsonl"))[
            "source"
        ]
        == "none"
    )


def test_ledger_failure_overrides_walk_forward(tmp_path, monkeypatch):
    art = {**_report(evidence={"grade": "VALIDATED"}), "age_s": 1.0}
    monkeypatch.setattr(wfs, "load", lambda sid, **kw: art)
    monkeypatch.setattr(
        shs,
        "load_per_strategy",
        lambda **kw: {
            "strategies": [
                {"strategy_id": SID, "evidence": {"grade": "FAILED_VALIDATION"}}
            ]
        },
    )
    ev = shs.evidence_for_strategy(SID)
    assert ev["grade"] == "FAILED_VALIDATION" and ev["source"] == "realized_trades"


def test_endpoint_unknown_and_missing(monkeypatch):
    from src.api.routers import evidence

    monkeypatch.setattr(wfs, "load", lambda sid, **kw: None)
    from fastapi import HTTPException

    with pytest.raises(HTTPException) as exc:
        asyncio.run(evidence.get_walk_forward("nope", _=True))
    assert exc.value.status_code == 404
    out = asyncio.run(evidence.get_walk_forward(SID, _=True))
    assert out["available"] is False and out["evidence"]["grade"] == "NO_BACKTEST"
    listing = asyncio.run(evidence.list_walk_forward(_=True))
    assert listing["strategies"][0]["grade"] == "NO_BACKTEST"


def test_brief_tags_trade_tier_with_registered_rule():
    from pathlib import Path

    from src.engines.walk_forward import RULES

    root = Path(__file__).resolve().parents[1]
    src = (root / "data" / "generate_brief.py").read_text()
    assert '"strategy_id": "brief_rs_leader_v1" if conviction == "TRADE"' in src
    assert "brief_rs_leader_v1" in RULES
