"""Dossier plan endpoint + removal of fabricated dossier levels/regime defaults."""

from __future__ import annotations

import json
import math
import time

import pandas as pd
import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from src.api.routers import dossier
from src.services import strategy_health_service as shs

VERIFIED_REGIME = {"should_trade": True, "synthetic": False, "vix": 15.0}
SYNTHETIC_REGIME = {"should_trade": True, "synthetic": True, "vix": 18.0}


def _bars(n=90, last_ts=None):
    last_ts = last_ts or time.time()
    out = []
    for i in range(n):
        c = 100.0 + 10.0 * math.sin(2 * math.pi * i / 20)
        out.append(
            {"time": last_ts - (n - 1 - i) * 86400, "high": c + 1, "low": c - 1, "close": c}
        )
    return out


def _evidence(grade):
    return {"grade": grade, "headline": grade}


class TestBuildPlanResponse:
    def _call(self, **kw):
        args = dict(
            strategy_id="momentum",
            regime=VERIFIED_REGIME,
            evidence=_evidence("VALIDATED"),
            signal={"status": "QUALIFIED"},
            now_ts=time.time(),
            entry=100.0,
            stop=95.0,
            targets=[115.0],
        )
        args.update(kw)
        bars = args.pop("bars", _bars())
        return dossier.build_plan_response("TEST", bars, **args)

    def test_validated_evidence_verified_regime_is_buy_setup(self):
        out = self._call()
        assert out["action"] == "BUY SETUP"
        assert "no order" in out["execution_note"].lower()

    def test_plan_without_signal_is_not_buy(self):
        out = self._call(signal={"status": "NONE"})
        assert out["action"] == "WAIT"
        assert out["signal"]["status"] == "NONE"

    def test_insufficient_evidence_caps_at_watch(self):
        out = self._call(evidence=_evidence("INSUFFICIENT_SAMPLE"))
        assert out["action"] == "WATCH"

    def test_synthetic_regime_is_unverified(self):
        out = self._call(regime=SYNTHETIC_REGIME)
        assert out["regime"] == {"verified": False, "allowed": None}
        assert out["action"] == "WAIT"

    def test_stale_bars_fail_closed(self):
        old = time.time() - 30 * 86400
        out = self._call(bars=_bars(last_ts=old))
        assert out["plan"]["status"] == "STALE_DATA"
        assert out["action"] == "NO TRADE"

    def test_no_bars_no_levels(self):
        out = self._call(bars=[])
        assert out["plan"]["status"] == "INSUFFICIENT_HISTORY"
        assert out["plan"]["stop"] is None
        assert out["action"] == "NO TRADE"


class _FakeMDS:
    def __init__(self, hist):
        self.hist = hist

    async def get_history(self, ticker, period="1y", interval="1d"):
        return self.hist


def _hist_frame():
    bars = _bars()
    idx = pd.to_datetime([b["time"] for b in bars], unit="s", utc=True)
    return pd.DataFrame(
        {
            "Open": [b["close"] for b in bars],
            "High": [b["high"] for b in bars],
            "Low": [b["low"] for b in bars],
            "Close": [b["close"] for b in bars],
            "Volume": [1000] * len(bars),
        },
        index=idx,
    )


@pytest.fixture
def client(monkeypatch):
    from src.services.regime_service import RegimeService

    monkeypatch.setattr(RegimeService, "get", classmethod(lambda cls: VERIFIED_REGIME))
    monkeypatch.setattr(dossier, "_load_brief_data", lambda: {"actionable": []})
    app = FastAPI()
    app.include_router(dossier.router)
    app.state.market_data = _FakeMDS(_hist_frame())
    return TestClient(app)


class TestPlanHttp:
    def test_plan_returns_levels_and_no_backtest_without_strategy(self, client):
        r = client.get("/api/dossier/AAPL/plan")
        assert r.status_code == 200
        body = r.json()
        assert body["plan"]["status"] == "OK"
        assert body["plan"]["support"] and body["plan"]["resistance"]
        assert body["evidence"]["grade"] == "NO_BACKTEST"
        assert body["signal"]["status"] == "NONE"
        assert body["action"] in ("WATCH", "WAIT")

    def test_overrides_recalculate(self, client):
        r = client.get(
            "/api/dossier/AAPL/plan",
            params={"entry": 100, "stop": 95, "target": [115, 120]},
        )
        plan = r.json()["plan"]
        assert plan["risk_per_share"] == 5.0
        assert [t["reward_risk"] for t in plan["targets"]] == [3.0, 4.0]

    def test_wrong_side_stop_rejected(self, client):
        r = client.get("/api/dossier/AAPL/plan", params={"entry": 100, "stop": 110})
        body = r.json()
        assert body["plan"]["status"] == "INVALID_STOP"
        assert body["action"] == "NO TRADE"

    def test_invalid_ticker_rejected(self, client):
        r = client.get("/api/dossier/..%2Fetc/plan")
        assert r.status_code in (400, 404, 422)


class TestDossierFailClosed:
    def test_synthetic_regime_blocks_gate(self, monkeypatch):
        from src.services.regime_service import RegimeService

        monkeypatch.setattr(RegimeService, "get", classmethod(lambda cls: SYNTHETIC_REGIME))
        monkeypatch.setattr(
            dossier,
            "_load_brief_data",
            lambda: {"actionable": [{"ticker": "ZZZ", "score": 9}]},
        )
        d = dossier._build_dossier("ZZZ")
        assert d["decision"]["regime_gate"] == "BLOCKED"
        assert d["decision"]["regime_verified"] is False
        assert d["decision"]["action"] == "NO_TRADE"
        assert d["regime"]["vix"] is None
        assert d["regime"]["should_trade"] is False

    def test_trade_advice_never_invents_stop_or_target(self):
        advice = dossier._compute_trade_advice(
            "ZZZ",
            buy_price=100.0,
            current_price=101.0,
            dossier={"decision": {}, "risk": {}, "regime": {}, "confidence": {}, "indicators": {}},
        )
        assert advice["suggestion"]["stop_price"] is None
        assert advice["suggestion"]["target_price"] is None
        assert advice["suggestion"]["regime_gate"] == "BLOCKED"

    def test_missing_indicators_give_no_heuristic_score(self, monkeypatch):
        from src.services.regime_service import RegimeService

        monkeypatch.setattr(RegimeService, "get", classmethod(lambda cls: SYNTHETIC_REGIME))
        monkeypatch.setattr(
            dossier,
            "_load_brief_data",
            lambda: {"actionable": [{"ticker": "ZZZ", "score": 9}]},
        )
        conf = dossier._build_dossier("ZZZ")["confidence"]
        assert conf["timing"] is None
        assert conf["overall"] is None
        assert conf["calibrated"] is False

    def test_unknown_score_never_triggers_buy_more(self):
        advice = dossier._compute_trade_advice(
            "ZZZ",
            buy_price=100.0,
            current_price=101.0,
            dossier={
                "decision": {"conviction_tier": "TRADE", "regime_gate": "ALLOWED"},
                "risk": {},
                "regime": {},
                "confidence": {"overall": None},
                "indicators": {},
            },
        )
        assert advice["action"] != "BUY MORE"
        assert not any("%" in w and "score" in w.lower() for w in advice["warnings"])


class TestStrategyHealthEvidence:
    def _ledger(self, tmp_path, rows):
        p = tmp_path / "closed.jsonl"
        p.write_text("\n".join(json.dumps(r) for r in rows))
        return str(p)

    def test_trusted_status_does_not_imply_validated(self, tmp_path):
        rows = [
            {"strategy_id": "s", "r_multiple": 1.5 if i % 2 else -1.0, "exit_time": "2026-01-01"}
            for i in range(40)
        ]
        out = shs.load_per_strategy(window_days=0, ledger_path=self._ledger(tmp_path, rows))
        row = out["strategies"][0]
        assert row["status"] == "TRUSTED"
        assert row["evidence"]["grade"] == "PRELIMINARY"
        assert "NO_OUT_OF_SAMPLE_TRADES" in row["evidence"]["reason_codes"]

    def test_unknown_strategy_is_no_backtest(self, tmp_path):
        path = self._ledger(tmp_path, [{"strategy_id": "s", "r_multiple": 1.0}])
        assert shs.evidence_for_strategy("nope", ledger_path=path)["grade"] == "NO_BACKTEST"
        assert shs.evidence_for_strategy(None, ledger_path=path)["grade"] == "NO_BACKTEST"
