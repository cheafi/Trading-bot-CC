"""
Sprint 49 Tests — Expert Council Review Fixes
==============================================
1. Signal decay tracker
2. Learning loop pipeline
3. Fallback scoring RSI gates + evidence + grading
4. Expert committee integration
5. Selectivity / concentration warnings
6. API endpoints
"""
import pytest
import asyncio
from datetime import datetime, timezone, timedelta
from unittest.mock import MagicMock, patch


# ── 1. Signal Decay Tracker ──

class TestSignalDecayTracker:
    def test_track_signal(self):
        from src.engines.signal_decay import SignalDecayTracker
        tracker = SignalDecayTracker()
        sig = tracker.track("AAPL", "LONG", 170.0, 160.0, 190.0, 0.75, "B")
        assert sig.ticker == "AAPL"
        assert sig.direction == "LONG"
        assert sig.setup_grade == "B"
        assert sig.age_hours < 1
        assert not sig.is_expired

    def test_expiry(self):
        from src.engines.signal_decay import SignalDecayTracker, TrackedSignal
        tracker = SignalDecayTracker()
        sig = tracker.track("MSFT", "LONG", 400.0, 380.0, 440.0, 0.6, "C", time_stop_days=0)
        # Force old creation time
        sig.created_at = datetime.now(timezone.utc) - timedelta(days=2)
        assert sig.is_expired
        expired = tracker.check_expiry()
        assert len(expired) == 1
        assert expired[0].ticker == "MSFT"

    def test_active_vs_expired(self):
        from src.engines.signal_decay import SignalDecayTracker
        tracker = SignalDecayTracker()
        s1 = tracker.track("AAPL", "LONG", 170.0, 160.0, 190.0, 0.75, "B")
        s2 = tracker.track("MSFT", "LONG", 400.0, 380.0, 440.0, 0.6, "C", time_stop_days=0)
        s2.created_at = datetime.now(timezone.utc) - timedelta(days=2)

        active = tracker.active_signals()
        expired = tracker.expired_signals()
        assert len(active) == 1
        assert active[0]["ticker"] == "AAPL"
        assert len(expired) == 1
        assert expired[0]["ticker"] == "MSFT"

    def test_record_outcome(self):
        from src.engines.signal_decay import SignalDecayTracker
        tracker = SignalDecayTracker()
        tracker.track("NVDA", "LONG", 800.0, 750.0, 900.0, 0.8, "A")
        tracker.record_outcome("NVDA", "LONG", "hit_target", pnl_pct=5.0)
        summary = tracker.summary()
        assert summary["total_tracked"] == 1

    def test_performance_by_age(self):
        from src.engines.signal_decay import SignalDecayTracker
        tracker = SignalDecayTracker()
        tracker.track("AAPL", "LONG", 170.0, 160.0, 190.0, 0.7, "B")
        tracker.record_outcome("AAPL", "LONG", "hit_target")
        perf = tracker.performance_by_age()
        assert "0-1d" in perf
        assert perf["0-1d"]["count"] == 1

    def test_summary(self):
        from src.engines.signal_decay import SignalDecayTracker
        tracker = SignalDecayTracker()
        summary = tracker.summary()
        assert "active_count" in summary
        assert "expired_count" in summary
        assert "performance_by_age" in summary

    def test_max_tracked_eviction(self):
        from src.engines.signal_decay import SignalDecayTracker
        tracker = SignalDecayTracker()
        tracker.MAX_TRACKED = 5
        for i in range(8):
            tracker.track(f"SYM{i}", "LONG", 100.0, 90.0, 110.0, 0.5, "C")
        assert len(tracker._signals) == 5

    def test_to_dict(self):
        from src.engines.signal_decay import SignalDecayTracker
        tracker = SignalDecayTracker()
        sig = tracker.track("AMD", "LONG", 150.0, 140.0, 170.0, 0.65, "B")
        d = sig.to_dict()
        assert d["ticker"] == "AMD"
        assert d["setup_grade"] == "B"
        assert d["outcome"] == "active"
        assert "age_hours" in d
        assert "age_days" in d


# ── 2. Learning Loop Pipeline ──

class TestLearningLoop:
    def test_record_trade_long_win(self):
        from src.engines.learning_loop import LearningLoopPipeline
        loop = LearningLoopPipeline()
        result = loop.record_closed_trade(
            ticker="AAPL", direction="LONG",
            entry_price=170.0, exit_price=180.0,
            entry_time="2026-04-01", exit_time="2026-04-10",
            strategy_id="momentum", regime_at_entry="UPTREND",
            setup_grade="A",
        )
        assert result["trade"]["won"] is True
        assert result["trade"]["pnl_pct"] > 0

    def test_record_trade_long_loss(self):
        from src.engines.learning_loop import LearningLoopPipeline
        loop = LearningLoopPipeline()
        result = loop.record_closed_trade(
            ticker="MSFT", direction="LONG",
            entry_price=400.0, exit_price=380.0,
            entry_time="2026-04-01", exit_time="2026-04-05",
            strategy_id="breakout", setup_grade="C",
        )
        assert result["trade"]["won"] is False
        assert result["trade"]["pnl_pct"] < 0

    def test_win_rate_by_grade(self):
        from src.engines.learning_loop import LearningLoopPipeline
        loop = LearningLoopPipeline()
        loop.record_closed_trade("A1", "LONG", 100, 110, "", "", "s1", setup_grade="A")
        loop.record_closed_trade("A2", "LONG", 100, 105, "", "", "s1", setup_grade="A")
        loop.record_closed_trade("C1", "LONG", 100, 90, "", "", "s2", setup_grade="C")
        rates = loop.win_rate_by_grade()
        assert rates["A"]["win_rate"] == 1.0
        assert rates["C"]["win_rate"] == 0.0

    def test_win_rate_by_regime(self):
        from src.engines.learning_loop import LearningLoopPipeline
        loop = LearningLoopPipeline()
        loop.record_closed_trade("X", "LONG", 100, 110, "", "", "s", regime_at_entry="UPTREND")
        loop.record_closed_trade("Y", "LONG", 100, 90, "", "", "s", regime_at_entry="CRISIS")
        rates = loop.win_rate_by_regime()
        assert rates["UPTREND"]["win_rate"] == 1.0
        assert rates["CRISIS"]["win_rate"] == 0.0

    def test_summary(self):
        from src.engines.learning_loop import LearningLoopPipeline
        loop = LearningLoopPipeline()
        loop.record_closed_trade("Z", "LONG", 100, 110, "", "", "s")
        s = loop.summary()
        assert s["total_trades"] == 1
        assert s["wins"] == 1
        assert s["win_rate"] == 1.0
        assert "by_grade" in s
        assert "by_regime" in s

    def test_trade_log(self):
        from src.engines.learning_loop import LearningLoopPipeline
        loop = LearningLoopPipeline()
        loop.record_closed_trade("T1", "LONG", 100, 110, "", "", "s")
        loop.record_closed_trade("T2", "LONG", 100, 90, "", "", "s")
        log = loop.get_trade_log()
        assert len(log) == 2
        assert log[0]["ticker"] == "T1"

    def test_short_trade(self):
        from src.engines.learning_loop import LearningLoopPipeline
        loop = LearningLoopPipeline()
        result = loop.record_closed_trade(
            ticker="TSLA", direction="SHORT",
            entry_price=200.0, exit_price=180.0,
            entry_time="", exit_time="",
            strategy_id="bearish",
        )
        assert result["trade"]["won"] is True
        assert result["trade"]["pnl_pct"] > 0


# ── 3. Expert Committee ──

class TestExpertCommittee:
    def test_collect_votes(self):
        from src.engines.expert_committee import ExpertCommittee
        ec = ExpertCommittee()
        votes = ec.collect_votes(
            regime="UPTREND", rsi=65, vol_ratio=1.2,
            trending=True, rr_ratio=2.0, atr_pct=0.02,
        )
        assert len(votes) == 7
        for v in votes:
            assert v.direction in ("LONG", "SHORT", "FLAT", "ABSTAIN")
            assert 0 <= v.conviction <= 100

    def test_deliberate(self):
        from src.engines.expert_committee import ExpertCommittee
        ec = ExpertCommittee()
        votes = ec.collect_votes(
            regime="UPTREND", rsi=55, vol_ratio=1.5,
            trending=True, rr_ratio=2.5, atr_pct=0.02,
        )
        verdict = ec.deliberate(votes, regime="UPTREND")
        assert verdict.direction in ("LONG", "SHORT", "FLAT", "ABSTAIN")
        assert 0 <= verdict.composite_conviction <= 100
        assert 0 <= verdict.agreement_ratio <= 1

    def test_overbought_rsi_reduces_consensus(self):
        from src.engines.expert_committee import ExpertCommittee
        ec = ExpertCommittee()
        # RSI 90 — mean reversion should vote FLAT
        votes = ec.collect_votes(
            regime="UPTREND", rsi=90, vol_ratio=1.0,
            trending=True, rr_ratio=2.0, atr_pct=0.02,
        )
        mr_vote = [v for v in votes if v.expert_name == "MeanReversion"][0]
        assert mr_vote.direction == "FLAT"

    def test_crisis_regime(self):
        from src.engines.expert_committee import ExpertCommittee
        ec = ExpertCommittee()
        votes = ec.collect_votes(
            regime="CRISIS", rsi=25, vol_ratio=2.0,
            trending=False, rr_ratio=1.0, atr_pct=0.06,
            vix=40,
        )
        macro_vote = [v for v in votes if v.expert_name == "Macro"][0]
        assert macro_vote.direction == "FLAT"
        risk_vote = [v for v in votes if v.expert_name == "Risk"][0]
        assert risk_vote.direction == "FLAT"

    def test_verdict_to_dict(self):
        from src.engines.expert_committee import ExpertCommittee
        ec = ExpertCommittee()
        votes = ec.collect_votes(
            regime="UPTREND", rsi=55, vol_ratio=1.0,
            trending=True, rr_ratio=2.0, atr_pct=0.02,
        )
        verdict = ec.deliberate(votes, "UPTREND")
        d = verdict.to_dict()
        assert "direction" in d
        assert "composite_conviction" in d
        assert "agreement_ratio" in d
        assert "dominant_risk" in d
        assert "verdict_summary" in d


# ── 4. Screener API Integration ──

class TestScreenerAPI:
    """Integration tests requiring running server."""

    @pytest.fixture
    def client(self):
        import httpx
        return httpx.Client(base_url="http://127.0.0.1:8000", timeout=30)

    def test_regime_screener_has_new_fields(self, client):
        r = client.get("/api/v7/regime-screener")
        if r.status_code != 200:
            pytest.skip("Server not running")
        data = r.json()
        # Sprint 49: selectivity
        assert "selectivity" in data
        assert "warnings" in data
        assert "actionable_count" in data

    def test_candidates_have_evidence(self, client):
        r = client.get("/api/v7/regime-screener")
        if r.status_code != 200:
            pytest.skip("Server not running")
        data = r.json()
        for c in data.get("candidates", [])[:3]:
            assert "setup_grade" in c
            assert c["setup_grade"] in ("A", "B", "C", "D")
            assert "evidence_for" in c
            assert "evidence_against" in c
            assert isinstance(c["evidence_for"], list)
            assert isinstance(c["evidence_against"], list)
            assert "invalidation" in c

    def test_candidates_have_committee(self, client):
        r = client.get("/api/v7/regime-screener")
        if r.status_code != 200:
            pytest.skip("Server not running")
        data = r.json()
        for c in data.get("candidates", [])[:3]:
            cm = c.get("committee")
            if cm is not None:
                assert "direction" in cm
                assert "conviction" in cm
                assert "agreement" in cm
                assert "dominant_risk" in cm

    def test_overbought_suppressed(self, client):
        r = client.get("/api/v7/regime-screener")
        if r.status_code != 200:
            pytest.skip("Server not running")
        data = r.json()
        for c in data.get("candidates", []):
            rsi = c.get("rsi", 50)
            if rsi > 80:
                assert c["direction"] == "FLAT"
                assert len(c.get("risks", [])) > 0

    def test_signal_decay_endpoint(self, client):
        r = client.get("/api/v6/signal-decay")
        if r.status_code != 200:
            pytest.skip("Server not running")
        data = r.json()
        assert "active_count" in data
        assert "performance_by_age" in data

    def test_learning_loop_endpoint(self, client):
        r = client.get("/api/v6/learning-loop")
        if r.status_code != 200:
            pytest.skip("Server not running")
        data = r.json()
        assert "total_trades" in data
        assert "by_grade" in data
        assert "by_regime" in data
        assert "meta_ensemble_trained" in data

    def test_selectivity_ratio(self, client):
        r = client.get("/api/v7/regime-screener")
        if r.status_code != 200:
            pytest.skip("Server not running")
        data = r.json()
        sel = data.get("selectivity", {})
        assert "total_scanned" in sel
        assert "passed_filters" in sel
        assert sel["passed_filters"] <= sel["total_scanned"]


# ── 5. Meta-Ensemble (property access) ──

class TestMetaEnsembleProperties:
    def test_is_trained_property(self):
        from src.engines.meta_ensemble import MetaEnsemble
        me = MetaEnsemble()
        assert me.is_trained is False  # property, not method
        assert me.sample_count == 0

    def test_get_learned_weights(self):
        from src.engines.meta_ensemble import MetaEnsemble
        me = MetaEnsemble()
        w = me.get_learned_weights()
        assert w is None  # not trained yet


# ── 6. ClosedTrade dataclass ──

class TestClosedTrade:
    def test_won_property(self):
        from src.engines.learning_loop import ClosedTrade
        t = ClosedTrade("A", "LONG", 100, 110, "", "", "s", 10.0, 2.0)
        assert t.won is True
        t2 = ClosedTrade("B", "LONG", 100, 90, "", "", "s", -10.0, -2.0)
        assert t2.won is False

    def test_to_dict(self):
        from src.engines.learning_loop import ClosedTrade
        t = ClosedTrade("X", "LONG", 100, 110, "t1", "t2", "strat", 10.0, 2.0,
                        regime_at_entry="UPTREND", setup_grade="A")
        d = t.to_dict()
        assert d["ticker"] == "X"
        assert d["regime"] == "UPTREND"
        assert d["setup_grade"] == "A"
        assert d["won"] is True


# ── 7. TrackedSignal dataclass ──

class TestTrackedSignal:
    def test_to_dict_fields(self):
        from src.engines.signal_decay import TrackedSignal
        sig = TrackedSignal(
            "NVDA", "LONG", 800.0, 750.0, 900.0, 0.8, "A",
            datetime.now(timezone.utc),
        )
        d = sig.to_dict()
        assert d["ticker"] == "NVDA"
        assert d["setup_grade"] == "A"
        assert d["outcome"] == "active"
        assert d["expired"] is False

    def test_expired_signal_to_dict(self):
        from src.engines.signal_decay import TrackedSignal
        sig = TrackedSignal(
            "OLD", "LONG", 100.0, 90.0, 120.0, 0.5, "D",
            datetime.now(timezone.utc) - timedelta(days=10),
            time_stop_days=5,
        )
        d = sig.to_dict()
        assert d["expired"] is True
        assert d["outcome"] == "expired"
