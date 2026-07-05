"""
Sprint 57 – Decision Product API
==================================
1. /api/v7/today — regime + top 5 + filter funnel + tradeability
2. /api/v7/opportunities — ranked candidates with decision fields
3. /api/v7/filter-funnel — pipeline visualization
4. /api/v7/signal-card/{ticker} — full decision card
"""

import ast
import pathlib

import pytest

SRC = pathlib.Path(__file__).resolve().parent / "src"
DECISION_ROUTER = SRC / "api" / "routers" / "decision.py"
DECISION_SRC = DECISION_ROUTER.read_text()
MAIN_SRC = (SRC / "api" / "main.py").read_text()


# ── 1. Code structure ───────────────────────────────────────────────


class TestDecisionRouterStructure:
    def test_router_exists(self):
        assert DECISION_ROUTER.exists()

    def test_router_parses(self):
        ast.parse(DECISION_SRC)

    def test_router_included_in_main(self):
        assert "decision_router" in MAIN_SRC

    def test_today_endpoint_defined(self):
        assert "/api/v7/today" in DECISION_SRC

    def test_opportunities_endpoint_defined(self):
        assert "/api/v7/opportunities" in DECISION_SRC

    def test_filter_funnel_endpoint_defined(self):
        assert "/api/v7/filter-funnel" in DECISION_SRC

    def test_signal_card_endpoint_defined(self):
        assert "/api/v7/signal-card/" in DECISION_SRC

    def test_has_timing_label_helper(self):
        assert "def _timing_label" in DECISION_SRC

    def test_has_action_helper(self):
        assert "def _action_from_signal" in DECISION_SRC

    def test_has_why_now_helper(self):
        assert "def _why_now" in DECISION_SRC

    def test_has_why_not_helper(self):
        assert "def _why_not" in DECISION_SRC

    def test_has_invalidation_helper(self):
        assert "def _invalidation" in DECISION_SRC

    def test_has_position_hint_helper(self):
        assert "def _position_hint" in DECISION_SRC

    def test_has_setup_family_helper(self):
        assert "def _setup_family" in DECISION_SRC


# ── 2. Helper function unit tests ───────────────────────────────────


class TestHelperFunctions:
    @pytest.fixture(autouse=True)
    def _import(self):
        import sys

        sys.path.insert(0, str(SRC.parent))
        from src.api.routers.decision import (
            _action_from_signal,
            _invalidation,
            _position_hint,
            _setup_family,
            _timing_label,
            _why_not,
            _why_now,
        )

        self.timing = _timing_label
        self.action = _action_from_signal
        self.why_now = _why_now
        self.why_not = _why_not
        self.invalidation = _invalidation
        self.position = _position_hint
        self.family = _setup_family

    def test_timing_near_pivot(self):
        assert self.timing(0.5) == "NEAR_PIVOT"

    def test_timing_early(self):
        assert self.timing(2.0) == "EARLY"

    def test_timing_on_time(self):
        assert self.timing(5.0) == "ON_TIME"

    def test_timing_extended(self):
        assert self.timing(10.0) == "EXTENDED"

    def test_timing_late(self):
        assert self.timing(15.0) == "LATE"

    def test_action_no_regime(self):
        action, _ = self.action({"score": 9}, False)
        assert action == "WAIT"

    def test_action_strong_buy(self):
        sig = {
            "score": 8.5,
            "risk_reward": 3.0,
            "_timing": "NEAR_PIVOT",
            "strategy": "momentum",
        }
        action, _ = self.action(sig, True)
        assert action == "BUY"

    def test_action_watch_low_score(self):
        sig = {
            "score": 5.5,
            "risk_reward": 1.5,
            "_timing": "ON_TIME",
            "strategy": "swing",
        }
        action, _ = self.action(sig, True)
        assert action == "WATCH"

    def test_why_now_returns_list(self):
        sig = {
            "rsi": 55,
            "vol_ratio": 2.0,
            "regime": "UPTREND",
            "strategy": "momentum",
            "risk_reward": 3.0,
        }
        reasons = self.why_now(sig)
        assert isinstance(reasons, list)
        assert len(reasons) > 0

    def test_why_not_overbought(self):
        sig = {"rsi": 80, "atr_pct": 1.0, "vol_ratio": 1.0, "risk_reward": 2.0}
        warnings = self.why_not(sig)
        assert any("overbought" in w for w in warnings)

    def test_invalidation_has_price(self):
        sig = {"stop_price": 95.00, "strategy": "breakout"}
        inv = self.invalidation(sig)
        assert "$95.00" in inv

    def test_position_hint_no_regime(self):
        assert self.position({"score": 9}, False) == "NO_POSITION"

    def test_position_hint_standard(self):
        assert self.position({"score": 9}, True) == "STANDARD"

    def test_position_hint_starter(self):
        assert self.position({"score": 7.5}, True) == "STARTER"

    def test_setup_family_mapping(self):
        assert "Momentum" in self.family("momentum")
        assert "Breakout" in self.family("breakout")
        assert "Swing" in self.family("swing")


# ── 3. Server endpoint tests ────────────────────────────────────────


class TestDecisionEndpoints:
    @pytest.fixture(scope="class")
    def client(self):
        import sys

        sys.path.insert(0, str(SRC.parent))
        from starlette.testclient import TestClient

        from src.api.main import app

        return TestClient(app)

    def test_today_returns_200(self, client):
        r = client.get("/api/v7/today")
        assert r.status_code == 200

    def test_today_has_regime(self, client):
        d = client.get("/api/v7/today").json()
        assert "market_regime" in d
        regime = d["market_regime"]
        assert "label" in regime
        assert "should_trade" in regime
        assert "tradeability" in regime
        assert "summary" in regime

    def test_today_has_top5(self, client):
        d = client.get("/api/v7/today").json()
        assert "top_5" in d
        assert isinstance(d["top_5"], list)
        if d["top_5"]:
            item = d["top_5"][0]
            assert "rank" in item
            assert "ticker" in item
            assert "strategy" in item
            assert "action" in item
            assert "why_now" in item

    def test_today_has_funnel(self, client):
        d = client.get("/api/v7/today").json()
        assert "filter_funnel" in d
        funnel = d["filter_funnel"]
        assert "universe" in funnel
        assert "actionable_above_7" in funnel

    def test_today_has_avoid(self, client):
        d = client.get("/api/v7/today").json()
        assert "avoid" in d

    def test_opportunities_returns_200(self, client):
        r = client.get("/api/v7/opportunities")
        assert r.status_code == 200

    def test_opportunities_has_ranked_items(self, client):
        d = client.get("/api/v7/opportunities").json()
        assert "opportunities" in d
        assert "total_signals" in d
        if d["opportunities"]:
            opp = d["opportunities"][0]
            for field in [
                "ticker",
                "strategy",
                "score",
                "timing",
                "action",
                "why_now",
                "why_not",
                "invalidation",
                "position_hint",
            ]:
                assert field in opp, f"Missing field: {field}"

    def test_opportunities_sort_by_score(self, client):
        d = client.get("/api/v7/opportunities?sort_by=score").json()
        opps = d["opportunities"]
        if len(opps) >= 2:
            assert opps[0]["score"] >= opps[1]["score"]

    def test_opportunities_filter_by_strategy(self, client):
        r = client.get("/api/v7/opportunities?setup_filter=swing")
        assert r.status_code == 200

    def test_filter_funnel_returns_200(self, client):
        r = client.get("/api/v7/filter-funnel")
        assert r.status_code == 200

    def test_filter_funnel_has_stages(self, client):
        d = client.get("/api/v7/filter-funnel").json()
        assert "funnel" in d
        stages = d["funnel"]
        assert len(stages) >= 4
        assert stages[0]["stage"] == "Universe (Watchlist)"

    def test_filter_funnel_has_strategy_breakdown(self, client):
        d = client.get("/api/v7/filter-funnel").json()
        assert "by_strategy" in d

    def test_signal_card_returns_200(self, client):
        r = client.get("/api/v7/signal-card/AAPL")
        assert r.status_code == 200

    def test_signal_card_has_decision_fields(self, client):
        d = client.get("/api/v7/signal-card/AAPL").json()
        for field in [
            "ticker",
            "strategy",
            "score",
            "timing",
            "action",
            "why_now",
            "why_not",
            "invalidation",
            "position_hint",
            "entry_price",
            "target_price",
            "stop_price",
            "risk_reward",
            "technicals",
        ]:
            assert field in d, f"Missing field: {field}"

    def test_signal_card_has_committee(self, client):
        d = client.get("/api/v7/signal-card/AAPL").json()
        assert "direction" in d
        assert "committee_confidence" in d

    def test_signal_card_has_prediction(self, client):
        d = client.get("/api/v7/signal-card/AAPL").json()
        # prediction_interval may be None if insufficient data
        assert "prediction_interval" in d

    def test_signal_card_invalid_ticker(self, client):
        r = client.get("/api/v7/signal-card/ZZZZZZZ")
        assert r.status_code in (404, 500)


# ── 4. Regression ───────────────────────────────────────────────────


class TestRegression:
    @pytest.fixture(scope="class")
    def client(self):
        import sys

        sys.path.insert(0, str(SRC.parent))
        from starlette.testclient import TestClient

        from src.api.main import app

        return TestClient(app)

    def test_health_still_works(self, client):
        assert client.get("/api/health").status_code == 200

    def test_portfolio_still_works(self, client):
        assert client.get("/api/portfolio/holdings").status_code == 200

    def test_operator_still_works(self, client):
        assert client.get("/api/operator/status").status_code == 200

    def test_delta_scoreboard_still_works(self, client):
        assert client.get("/api/v6/delta-scoreboard").status_code == 200
