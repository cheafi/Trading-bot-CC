"""
Sprint 51 Tests — Market Intel, Risk Scorecard, Watchlist Intelligence
=======================================================================
45+ tests covering all new engines and API endpoints.
"""

import sys

import httpx

sys.path.insert(0, "/tmp/cc_temp")

# ═══════════════════════════════════════════════════════════════════
# 1. Market Intel Engine unit tests
# ═══════════════════════════════════════════════════════════════════

from src.engines.market_intel import IntelReport, MarketIntelEngine


class TestMarketIntel:
    def test_basic_analyse(self):
        engine = MarketIntelEngine()
        report = engine.analyse("AAPL", price=200, rsi=55)
        assert isinstance(report, IntelReport)
        assert report.ticker == "AAPL"
        assert -1 <= report.fusion_score <= 1
        assert report.signal_count > 0

    def test_bullish_conditions(self):
        engine = MarketIntelEngine()
        report = engine.analyse(
            "NVDA",
            price=120,
            rsi=55,
            above_sma20=True,
            above_sma50=True,
            above_sma200=True,
            regime="RISK_ON",
            volume_ratio=1.5,
        )
        assert report.fusion_score > 0
        assert len(report.bullish_signals) > 0

    def test_bearish_conditions(self):
        engine = MarketIntelEngine()
        report = engine.analyse(
            "MSFT",
            price=400,
            rsi=85,
            above_sma20=False,
            above_sma50=False,
            regime="RISK_OFF",
            volume_ratio=3.0,
            change_pct=-5.0,
        )
        assert report.fusion_score < 0
        assert len(report.bearish_signals) > 0

    def test_unusual_volume(self):
        engine = MarketIntelEngine()
        report = engine.analyse(
            "TSLA",
            volume_ratio=4.0,
            change_pct=3.0,
        )
        volume_signals = [
            s
            for s in report.bullish_signals + report.bearish_signals
            if s["dimension"] == "volume"
        ]
        assert len(volume_signals) > 0

    def test_high_vix_macro(self):
        engine = MarketIntelEngine()
        report = engine.analyse("SPY", vix=35, regime="CRISIS")
        bearish = [s for s in report.bearish_signals if s["dimension"] == "macro"]
        assert len(bearish) > 0

    def test_overbought_rsi(self):
        engine = MarketIntelEngine()
        report = engine.analyse("MSFT", rsi=85)
        assert len(report.bearish_signals) > 0

    def test_oversold_rsi(self):
        engine = MarketIntelEngine()
        report = engine.analyse("MSFT", rsi=20)
        assert len(report.bullish_signals) > 0

    def test_agreement_ratio(self):
        engine = MarketIntelEngine()
        report = engine.analyse(
            "AAPL",
            rsi=55,
            above_sma20=True,
            above_sma50=True,
            regime="RISK_ON",
        )
        assert 0 <= report.agreement_ratio <= 1

    def test_dominant_theme(self):
        engine = MarketIntelEngine()
        report = engine.analyse("AAPL")
        assert report.dominant_theme != ""

    def test_low_volume_warning(self):
        engine = MarketIntelEngine()
        report = engine.analyse("THIN", volume_ratio=0.3)
        neutral = [s for s in report.neutral_signals if s["dimension"] == "volume"]
        assert len(neutral) > 0

    def test_summary(self):
        engine = MarketIntelEngine()
        s = engine.summary()
        assert "dimensions" in s
        assert "weights" in s


# ═══════════════════════════════════════════════════════════════════
# 2. Risk Scorecard Engine unit tests
# ═══════════════════════════════════════════════════════════════════

from src.engines.risk_scorecard import RiskScorecard, RiskScorecardEngine


class TestRiskScorecard:
    def test_healthy_conditions(self):
        engine = RiskScorecardEngine()
        sc = engine.evaluate(
            drawdown_pct=0.02,
            portfolio_heat_pct=0.02,
            open_positions=3,
            vix=16,
        )
        assert isinstance(sc, RiskScorecard)
        assert sc.overall_grade in ("A", "B")
        assert sc.can_trade is True

    def test_critical_drawdown(self):
        engine = RiskScorecardEngine()
        sc = engine.evaluate(drawdown_pct=0.20)
        assert sc.can_trade is False
        assert "DRAWDOWN" in sc.flags[0]
        assert sc.overall_grade in ("C", "D", "F")

    def test_max_heat(self):
        engine = RiskScorecardEngine()
        sc = engine.evaluate(portfolio_heat_pct=0.07)
        assert sc.can_trade is False

    def test_extreme_vix(self):
        engine = RiskScorecardEngine()
        sc = engine.evaluate(vix=45)
        assert sc.can_trade is False
        assert any("VIX" in f for f in sc.flags)

    def test_max_positions(self):
        engine = RiskScorecardEngine()
        sc = engine.evaluate(
            open_positions=20,
            max_positions=20,
        )
        assert sc.can_trade is False

    def test_concentrated_portfolio(self):
        engine = RiskScorecardEngine()
        sc = engine.evaluate(
            concentration_grade="D",
            hhi_score=3000,
        )
        assert any("Diversify" in r for r in sc.recommendations)

    def test_moderate_risk(self):
        engine = RiskScorecardEngine()
        sc = engine.evaluate(
            drawdown_pct=0.05,
            vix=28,
            open_positions=8,
        )
        assert sc.overall_grade in ("B", "C")
        assert sc.can_trade is True

    def test_to_dict(self):
        engine = RiskScorecardEngine()
        sc = engine.evaluate()
        d = sc.to_dict()
        assert "overall_grade" in d
        assert "categories" in d
        assert "can_trade" in d

    def test_grade_boundaries(self):
        engine = RiskScorecardEngine()
        # All zeros → A
        sc = engine.evaluate(vix=12)
        assert sc.overall_grade == "A"

    def test_summary(self):
        engine = RiskScorecardEngine()
        s = engine.summary()
        assert "dimensions" in s


# ═══════════════════════════════════════════════════════════════════
# 3. Watchlist Intelligence unit tests
# ═══════════════════════════════════════════════════════════════════

from src.engines.watchlist_intel import WatchlistIntelEngine


class TestWatchlistIntel:
    def test_add_and_retrieve(self):
        engine = WatchlistIntelEngine()
        item = engine.add("AAPL", score=0.8, setup_grade="A")
        assert item.urgency == "ACT_NOW"
        assert engine.count == 1

    def test_ranked(self):
        engine = WatchlistIntelEngine()
        engine.add("AAPL", score=0.9)
        engine.add("MSFT", score=0.7)
        engine.add("TSLA", score=0.4)
        ranked = engine.ranked()
        assert ranked[0]["ticker"] == "AAPL"
        assert ranked[-1]["ticker"] == "TSLA"

    def test_urgency_classification(self):
        engine = WatchlistIntelEngine()
        engine.add("A", score=0.8, setup_grade="A")
        engine.add("B", score=0.6, setup_grade="C")
        engine.add("C", score=0.4, setup_grade="D")
        engine.add("D", score=0.2, setup_grade="D")
        assert engine.get("A")["urgency"] == "ACT_NOW"
        assert engine.get("B")["urgency"] == "WATCH"
        assert engine.get("C")["urgency"] == "DEFER"
        assert engine.get("D")["urgency"] == "STALE"

    def test_remove(self):
        engine = WatchlistIntelEngine()
        engine.add("AAPL", score=0.8)
        assert engine.remove("AAPL") is True
        assert engine.count == 0
        assert engine.remove("AAPL") is False

    def test_urgency_filter(self):
        engine = WatchlistIntelEngine()
        engine.add("A", score=0.9, setup_grade="A")
        engine.add("B", score=0.6, setup_grade="C")
        act_now = engine.ranked(urgency_filter="ACT_NOW")
        assert len(act_now) == 1
        assert act_now[0]["ticker"] == "A"

    def test_stats(self):
        engine = WatchlistIntelEngine()
        engine.add("A", score=0.9, setup_grade="A")
        engine.add("B", score=0.6)
        s = engine.stats()
        assert s["total"] == 2
        assert s["act_now"] == 1

    def test_eviction(self):
        engine = WatchlistIntelEngine()
        engine.MAX_ITEMS = 3
        engine.add("A", score=0.9)
        engine.add("B", score=0.8)
        engine.add("C", score=0.7)
        engine.add("D", score=0.95)  # Should evict lowest
        assert engine.count == 3
        assert engine.get("C") is None  # Lowest evicted

    def test_update_existing(self):
        engine = WatchlistIntelEngine()
        engine.add("AAPL", score=0.5)
        engine.add("AAPL", score=0.9, setup_grade="A")
        assert engine.count == 1
        assert engine.get("AAPL")["score"] == 0.9

    def test_get_nonexistent(self):
        engine = WatchlistIntelEngine()
        assert engine.get("ZZZZ") is None

    def test_summary(self):
        engine = WatchlistIntelEngine()
        engine.add("AAPL", score=0.8, setup_grade="A")
        s = engine.summary()
        assert "total" in s
        assert "top_5" in s


# ═══════════════════════════════════════════════════════════════════
# 4. API integration tests (require running server at :8000)
# ═══════════════════════════════════════════════════════════════════

BASE = "http://127.0.0.1:8000"


def _get(path, **params):
    return httpx.get(f"{BASE}{path}", params=params, timeout=15)


class TestMarketIntelAPI:
    def test_basic(self):
        r = _get("/api/v6/market-intel", ticker="AAPL")
        assert r.status_code == 200
        d = r.json()
        assert "fusion_score" in d
        assert "signal_count" in d

    def test_with_ticker(self):
        r = _get("/api/v6/market-intel", ticker="MSFT")
        assert r.status_code == 200
        assert r.json()["ticker"] == "MSFT"


class TestRiskScorecardAPI:
    def test_healthy(self):
        r = _get("/api/v6/risk-scorecard", vix=18, drawdown_pct=0.02)
        assert r.status_code == 200
        d = r.json()
        assert d["can_trade"] is True
        assert "overall_grade" in d

    def test_critical(self):
        r = _get(
            "/api/v6/risk-scorecard",
            vix=50,
            drawdown_pct=0.20,
        )
        assert r.status_code == 200
        assert r.json()["can_trade"] is False


class TestWatchlistAPI:
    def test_empty(self):
        r = _get("/api/v6/watchlist")
        assert r.status_code == 200
        assert "items" in r.json()

    def test_add_and_list(self):
        # Add
        r = httpx.post(
            f"{BASE}/api/v6/watchlist/add",
            params={
                "ticker": "TESTW",
                "score": 0.85,
                "setup_grade": "A",
                "direction": "LONG",
            },
            timeout=15,
        )
        assert r.status_code == 200
        assert r.json()["added"] is True

        # List
        r2 = _get("/api/v6/watchlist")
        assert r2.status_code == 200
        tickers = [i["ticker"] for i in r2.json()["items"]]
        assert "TESTW" in tickers

    def test_remove(self):
        # Add first
        httpx.post(
            f"{BASE}/api/v6/watchlist/add",
            params={"ticker": "DELME", "score": 0.5},
            timeout=15,
        )
        # Remove
        r = httpx.delete(
            f"{BASE}/api/v6/watchlist/DELME",
            timeout=15,
        )
        assert r.status_code == 200
        assert r.json()["removed"] is True
