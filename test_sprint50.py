"""
Sprint 50 Tests — Position Sizing, Concentration Risk, Trade Gate, Decision Journal
=====================================================================================
40+ tests covering all new engines and API endpoints.
"""

import sys
import os
import pytest
import httpx

# Ensure /tmp/cc_temp is importable
sys.path.insert(0, "/tmp/cc_temp")

# ═══════════════════════════════════════════════════════════════════
# 1. Position Sizer unit tests
# ═══════════════════════════════════════════════════════════════════

from src.engines.position_sizer import PositionSizer, SizingResult


class TestPositionSizer:
    def test_basic_sizing(self):
        ps = PositionSizer(equity=100_000)
        r = ps.size_position("AAPL", price=200, stop_price=190)
        assert isinstance(r, SizingResult)
        assert r.shares > 0
        assert r.risk_per_share == 10.0
        assert r.method == "atr_fixed_risk"

    def test_risk_capped(self):
        ps = PositionSizer(equity=100_000, max_risk_pct=0.01)
        r = ps.size_position("TSLA", price=300, stop_price=250)
        # Risk per share = 50, max risk = 1000, so max shares = 20
        assert r.total_risk <= 1_000 + 50  # allow 1 share tolerance

    def test_zero_price(self):
        ps = PositionSizer()
        r = ps.size_position("BAD", price=0, stop_price=10)
        assert r.shares == 0

    def test_stop_equals_price(self):
        ps = PositionSizer()
        r = ps.size_position("X", price=100, stop_price=100)
        assert r.shares == 0
        assert "Risk per share" in r.notes[0]

    def test_kelly_method(self):
        ps = PositionSizer(equity=100_000)
        r = ps.size_position(
            "NVDA", price=120, stop_price=115,
            win_rate=0.6, avg_win_loss_ratio=2.0,
            method="kelly",
        )
        assert r.method == "kelly"
        assert r.shares > 0
        assert any("Kelly" in n for n in r.notes)

    def test_heat_throttle(self):
        ps = PositionSizer(
            equity=100_000,
            max_portfolio_heat=0.06,
            current_heat_pct=0.06,
        )
        r = ps.size_position("AAPL", price=200, stop_price=190)
        assert r.shares == 0
        assert "heat" in r.notes[0].lower()

    def test_equal_weight_method(self):
        ps = PositionSizer(equity=100_000, max_position_pct=0.05)
        r = ps.size_position(
            "GOOGL", price=150, stop_price=140,
            method="equal_weight",
        )
        assert r.position_pct <= 0.05 + 0.01

    def test_summary(self):
        ps = PositionSizer(equity=50_000)
        s = ps.summary()
        assert s["equity"] == 50_000
        assert "max_risk_pct" in s

    def test_negative_kelly(self):
        """When win_rate is too low, Kelly returns 0."""
        ps = PositionSizer(equity=100_000)
        r = ps.size_position(
            "BAD", price=100, stop_price=90,
            win_rate=0.2, avg_win_loss_ratio=0.5,
            method="kelly",
        )
        assert r.shares == 0


# ═══════════════════════════════════════════════════════════════════
# 2. Correlation Risk Engine unit tests
# ═══════════════════════════════════════════════════════════════════

from src.engines.correlation_risk import (
    CorrelationRiskEngine,
    get_sector,
)


class TestCorrelationRisk:
    def test_sector_lookup(self):
        assert get_sector("AAPL") == "Technology"
        assert get_sector("JPM") == "Financials"
        assert get_sector("ZZZZZ") == "Unknown"

    def test_concentrated_portfolio(self):
        engine = CorrelationRiskEngine()
        holdings = [
            {"ticker": "AAPL", "market_value": 80_000},
            {"ticker": "MSFT", "market_value": 10_000},
            {"ticker": "GOOGL", "market_value": 10_000},
        ]
        report = engine.analyse(holdings)
        assert report.top_ticker == "AAPL"
        assert report.top_concentration_pct > 0.5
        assert len(report.warnings) > 0
        assert report.grade in ("C", "D")

    def test_diversified_portfolio(self):
        engine = CorrelationRiskEngine()
        holdings = [
            {"ticker": "AAPL", "market_value": 20_000},
            {"ticker": "JPM", "market_value": 20_000},
            {"ticker": "UNH", "market_value": 20_000},
            {"ticker": "XOM", "market_value": 20_000},
            {"ticker": "COST", "market_value": 20_000},
        ]
        report = engine.analyse(holdings)
        assert report.grade in ("A", "B")
        assert report.hhi_score < 2500

    def test_empty_portfolio(self):
        engine = CorrelationRiskEngine()
        report = engine.analyse([])
        assert report.grade == "F"

    def test_correlation_flags(self):
        engine = CorrelationRiskEngine()
        flags = engine.estimate_correlation_flags(
            ["AAPL", "MSFT", "JPM", "BAC"]
        )
        # AAPL-MSFT (both Tech), JPM-BAC (both Financials)
        assert len(flags) >= 2
        sectors = {(f.ticker_a, f.ticker_b) for f in flags}
        assert ("AAPL", "MSFT") in sectors
        assert ("JPM", "BAC") in sectors

    def test_summary(self):
        engine = CorrelationRiskEngine()
        holdings = [
            {"ticker": "AAPL", "market_value": 50_000},
            {"ticker": "MSFT", "market_value": 50_000},
        ]
        s = engine.summary(holdings)
        assert "grade" in s
        assert "hhi" in s
        assert "correlated_pairs" in s

    def test_crowding_detection(self):
        engine = CorrelationRiskEngine()
        holdings = [
            {"ticker": "AAPL", "market_value": 15_000},
            {"ticker": "MSFT", "market_value": 15_000},
            {"ticker": "NVDA", "market_value": 15_000},
            {"ticker": "AMD", "market_value": 15_000},
            {"ticker": "JPM", "market_value": 10_000},
        ]
        report = engine.analyse(holdings)
        # 4 Tech stocks at 60% weight should trigger crowding
        assert len(report.crowding_flags) > 0


# ═══════════════════════════════════════════════════════════════════
# 3. Trade Gate unit tests
# ═══════════════════════════════════════════════════════════════════

from src.engines.trade_gate import TradeGate, GateResult


class TestTradeGate:
    def test_normal_conditions_allowed(self):
        gate = TradeGate()
        r = gate.evaluate(vix=18, open_positions=3)
        assert r.allowed is True
        assert len(r.hard_blocks) == 0

    def test_high_drawdown_blocked(self):
        gate = TradeGate(max_drawdown_pct=0.10)
        r = gate.evaluate(current_drawdown_pct=0.12)
        assert r.allowed is False
        assert len(r.hard_blocks) > 0
        assert "Drawdown" in r.hard_blocks[0]

    def test_max_positions_blocked(self):
        gate = TradeGate(max_open_positions=10)
        r = gate.evaluate(open_positions=10)
        assert r.allowed is False

    def test_extreme_vix_blocked(self):
        gate = TradeGate(vix_hard_block=45)
        r = gate.evaluate(vix=50)
        assert r.allowed is False
        assert "VIX" in r.hard_blocks[0]

    def test_elevated_vix_soft_warning(self):
        gate = TradeGate(vix_soft_warn=25, vix_hard_block=45)
        r = gate.evaluate(vix=30)
        assert r.allowed is True
        assert r.size_multiplier < 1.0
        assert len(r.soft_warnings) > 0

    def test_regime_uncertainty(self):
        gate = TradeGate()
        r = gate.evaluate(regime="CONFLICTED")
        assert r.size_multiplier <= 0.5
        assert any("uncertain" in w.lower() for w in r.soft_warnings)

    def test_earnings_week(self):
        gate = TradeGate()
        r = gate.evaluate(
            ticker="AAPL", is_earnings_week=True,
        )
        assert r.size_multiplier <= 0.5

    def test_off_hours(self):
        gate = TradeGate()
        r = gate.evaluate(current_hour_utc=5)  # 1am ET
        assert r.size_multiplier < 1.0
        assert any("hours" in w.lower() for w in r.soft_warnings)

    def test_portfolio_heat_blocked(self):
        gate = TradeGate(max_portfolio_heat=0.06)
        r = gate.evaluate(portfolio_heat_pct=0.07)
        assert r.allowed is False

    def test_to_dict(self):
        gate = TradeGate()
        r = gate.evaluate(vix=20)
        d = r.to_dict()
        assert "allowed" in d
        assert "gate_timestamp" in d

    def test_summary(self):
        gate = TradeGate()
        s = gate.summary()
        assert "max_open_positions" in s


# ═══════════════════════════════════════════════════════════════════
# 4. Decision Journal unit tests
# ═══════════════════════════════════════════════════════════════════

from src.engines.decision_journal import DecisionJournal, JournalEntry


class TestDecisionJournal:
    def test_record_and_retrieve(self):
        dj = DecisionJournal()
        e = dj.record("AAPL", "TRADE", price=150, score=0.8)
        assert isinstance(e, JournalEntry)
        assert e.entry_id == "DJ-000001"
        assert dj.count == 1

    def test_multiple_records(self):
        dj = DecisionJournal()
        dj.record("AAPL", "TRADE")
        dj.record("MSFT", "PASS")
        dj.record("NVDA", "BLOCKED")
        assert dj.count == 3

    def test_stats(self):
        dj = DecisionJournal()
        dj.record("AAPL", "TRADE")
        dj.record("MSFT", "PASS")
        dj.record("NVDA", "TRADE")
        s = dj.stats()
        assert s["total_decisions"] == 3
        assert s["trades"] == 2
        assert s["passes"] == 1

    def test_by_ticker(self):
        dj = DecisionJournal()
        dj.record("AAPL", "TRADE")
        dj.record("MSFT", "PASS")
        dj.record("AAPL", "PASS")
        entries = dj.by_ticker("AAPL")
        assert len(entries) == 2

    def test_record_outcome(self):
        dj = DecisionJournal()
        e = dj.record("AAPL", "TRADE")
        ok = dj.record_outcome(e.entry_id, "WIN", pnl_pct=5.2)
        assert ok is True
        assert dj.entries[0].outcome == "WIN"
        assert dj.entries[0].pnl_pct == 5.2

    def test_win_rate_calculation(self):
        dj = DecisionJournal()
        e1 = dj.record("AAPL", "TRADE")
        e2 = dj.record("MSFT", "TRADE")
        e3 = dj.record("NVDA", "TRADE")
        dj.record_outcome(e1.entry_id, "WIN")
        dj.record_outcome(e2.entry_id, "LOSS")
        dj.record_outcome(e3.entry_id, "WIN")
        s = dj.stats()
        assert s["win_rate"] == pytest.approx(0.667, abs=0.01)

    def test_selectivity(self):
        dj = DecisionJournal()
        dj.record("AAPL", "TRADE")
        dj.record("MSFT", "PASS")
        dj.record("NVDA", "PASS")
        dj.record("GOOGL", "PASS")
        s = dj.stats()
        assert s["selectivity"] == 0.25

    def test_recent(self):
        dj = DecisionJournal()
        for i in range(10):
            dj.record(f"T{i}", "TRADE")
        r = dj.recent(3)
        assert len(r) == 3
        assert r[-1]["ticker"] == "T9"

    def test_to_dict(self):
        dj = DecisionJournal()
        e = dj.record(
            "AAPL", "TRADE", price=150,
            evidence_for=["RSI healthy"],
            evidence_against=["Late in trend"],
        )
        d = e.to_dict()
        assert d["ticker"] == "AAPL"
        assert "RSI healthy" in d["evidence_for"]

    def test_summary(self):
        dj = DecisionJournal()
        dj.record("AAPL", "TRADE")
        s = dj.summary()
        assert "total_decisions" in s
        assert "recent" in s


# ═══════════════════════════════════════════════════════════════════
# 5. API integration tests (require running server at :8000)
# ═══════════════════════════════════════════════════════════════════

BASE = "http://127.0.0.1:8000"


def _get(path, **params):
    r = httpx.get(f"{BASE}{path}", params=params, timeout=15)
    return r


class TestPositionSizeAPI:
    def test_basic(self):
        r = _get("/api/v6/position-size", ticker="AAPL", price=200, stop_price=190)
        assert r.status_code == 200
        d = r.json()
        assert d["shares"] > 0
        assert d["method"] == "atr_fixed_risk"

    def test_tight_stop(self):
        r = _get("/api/v6/position-size", ticker="MSFT", price=400, stop_price=398)
        assert r.status_code == 200
        d = r.json()
        assert d["risk_per_share"] == 2.0


class TestTradeGateAPI:
    def test_normal(self):
        r = _get("/api/v6/trade-gate", vix=18, drawdown_pct=0.02)
        assert r.status_code == 200
        assert r.json()["allowed"] is True

    def test_blocked(self):
        r = _get("/api/v6/trade-gate", vix=50, drawdown_pct=0.20)
        assert r.status_code == 200
        assert r.json()["allowed"] is False
        assert len(r.json()["hard_blocks"]) >= 2


class TestConcentrationRiskAPI:
    def test_no_portfolio(self):
        r = _get("/api/v6/concentration-risk")
        assert r.status_code == 200
        d = r.json()
        assert d.get("status") == "no_portfolio" or "grade" in d


class TestDecisionJournalAPI:
    def test_empty_journal(self):
        r = _get("/api/v6/decision-journal")
        assert r.status_code == 200
        d = r.json()
        assert "total_decisions" in d

    def test_record_and_retrieve(self):
        # Record
        r = httpx.post(
            f"{BASE}/api/v6/decision-journal/record",
            params={"ticker": "TEST", "decision": "TRADE", "price": 100},
            timeout=15,
        )
        assert r.status_code == 200
        assert r.json()["recorded"] is True

        # Retrieve by ticker
        r2 = _get("/api/v6/decision-journal", ticker="TEST")
        assert r2.status_code == 200
        assert r2.json()["count"] >= 1
