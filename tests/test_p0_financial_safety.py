"""Regression tests for P0 financial-safety and security fixes.

Covers:
  * Timing-safe API key comparison (src/api/deps.py)
  * Exchange-calendar holding periods (src/core/trading_calendar.py,
    src/algo/position_manager.Position.days_held)
  * Universe market-cap data-quality gate (src/engines/signal_engine.py)
  * Risk configuration validation (src/core/risk_limits.py)
"""

from __future__ import annotations

from datetime import date, datetime, timezone

import pytest

from src.core.trading_calendar import (
    is_trading_day,
    nyse_holidays,
    trading_days_between,
)

# ══════════════════════════════════════════════════════════════
# Trading calendar
# ══════════════════════════════════════════════════════════════


class TestTradingCalendar:
    def test_weekend_is_not_a_trading_day(self):
        assert not is_trading_day(date(2026, 10, 24 + 1))  # Sunday 25 Oct
        assert is_trading_day(date(2026, 10, 23))  # Friday

    @pytest.mark.parametrize(
        "day",
        [
            date(2026, 1, 1),  # New Year's Day
            date(2026, 1, 19),  # MLK Day (3rd Mon Jan)
            date(2026, 2, 16),  # Washington's Birthday
            date(2026, 4, 3),  # Good Friday
            date(2026, 5, 25),  # Memorial Day
            date(2026, 6, 19),  # Juneteenth
            date(2026, 7, 3),  # Independence Day observed (4 Jul = Sat)
            date(2026, 9, 7),  # Labor Day
            date(2026, 11, 26),  # Thanksgiving
            date(2026, 12, 25),  # Christmas
        ],
    )
    def test_known_nyse_holidays_are_closed(self, day):
        assert day in nyse_holidays(day.year)
        assert not is_trading_day(day)

    def test_juneteenth_not_observed_before_2022(self):
        assert date(2021, 6, 18) not in nyse_holidays(2021)

    def test_same_day_entry_exit_is_zero(self):
        d = datetime(2026, 10, 19, 9, 30)
        assert trading_days_between(d, d) == 0

    def test_weekend_span_counts_only_sessions(self):
        # Fri 16 Oct 2026 -> Mon 19 Oct 2026 == 1 session elapsed.
        assert trading_days_between(date(2026, 10, 16), date(2026, 10, 19)) == 1

    def test_old_five_sevenths_approximation_was_wrong(self):
        # Mon -> Fri is 4 sessions; the legacy int(days * 5/7) gave 2.
        start, end = date(2026, 10, 19), date(2026, 10, 23)
        assert trading_days_between(start, end) == 4
        assert int((end - start).days * 5 / 7) == 2

    def test_holiday_inside_range_is_excluded(self):
        # Thanksgiving week: Mon 23 Nov -> Fri 27 Nov 2026.
        # Sessions: Mon, Tue, Wed, (Thu closed) = 4 weekdays - 1 holiday = 3.
        assert trading_days_between(date(2026, 11, 23), date(2026, 11, 27)) == 3

    def test_reversed_range_never_negative(self):
        assert trading_days_between(date(2026, 10, 23), date(2026, 10, 19)) == 0

    def test_long_multi_year_span_is_consistent(self):
        total = trading_days_between(date(2024, 1, 1), date(2025, 1, 1))
        # A US equity year has ~250-253 sessions.
        assert 248 <= total <= 254

    def test_timezone_aware_input_normalised_to_exchange_date(self):
        # 2026-10-20T01:00Z is still 2026-10-19 in New York.
        utc_entry = datetime(2026, 10, 20, 1, 0, tzinfo=timezone.utc)
        assert trading_days_between(utc_entry, date(2026, 10, 20)) == 1

    def test_extra_holidays_honoured(self):
        assert (
            trading_days_between(
                date(2026, 10, 19),
                date(2026, 10, 23),
                extra_holidays=[date(2026, 10, 21)],
            )
            == 3
        )


class TestPositionDaysHeld:
    def test_days_held_uses_exchange_calendar(self):
        from src.algo.position_manager import Position

        pos = Position(ticker="AAPL", strategy_id="momentum")
        pos.entry_date = datetime(2026, 10, 19)
        pos.exit_date = datetime(2026, 10, 23)
        assert pos.days_held == 4  # legacy approximation returned 2

    def test_days_held_without_entry_date_is_zero(self):
        from src.algo.position_manager import Position

        assert Position(ticker="AAPL", strategy_id="s").days_held == 0

    def test_max_hold_exit_uses_trading_days_not_calendar_days(self):
        """max_hold_days is a trading-day budget; calendar days exited early."""
        from src.algo.position_manager import Position, PositionStatus

        pos = Position(ticker="AAPL", strategy_id="momentum")
        pos.entry_date = datetime(2026, 1, 5)  # Monday
        pos.entry_price = 100.0
        pos.current_price = 100.0
        pos.status = PositionStatus.OPEN
        pos.max_hold_days = 10
        pos.stop_loss_price = 0.0
        pos.take_profit_price = 0.0
        pos.trailing_stop_price = 0.0

        # 16 Jan 2026 is 11 calendar days but only 9 sessions after entry.
        # The legacy calendar comparison (11 >= 10) exited here; the
        # trading-day budget has not actually been spent yet.
        assert trading_days_between(pos.entry_date, datetime(2026, 1, 16)) == 9
        should_exit, _ = pos.check_exit_conditions(100.0, datetime(2026, 1, 16))
        assert should_exit is False

        # The 10th session completes on 19 Jan 2026.
        should_exit, reason = pos.check_exit_conditions(100.0, datetime(2026, 1, 19))
        assert should_exit is True
        assert reason == "max_hold_time"


# ══════════════════════════════════════════════════════════════
# Risk configuration validation
# ══════════════════════════════════════════════════════════════


class TestRiskConfigValidation:
    """Validate the parsers/dataclasses directly.

    Module-level reload is deliberately avoided: a failed reload leaves
    ``sys.modules`` in a partially-initialised state and makes the test
    order-dependent.
    """

    def test_defaults_are_sane(self):
        from src.core.risk_limits import RISK, VIX

        assert 0 < RISK.max_position_pct <= 1.0
        assert RISK.max_positions >= 1
        assert VIX.low < VIX.mid < VIX.high < VIX.crisis

    def test_negative_position_limit_rejected(self, monkeypatch):
        from src.core.risk_limits import RiskConfigError, _env_float

        monkeypatch.setenv("RISK_MAX_POSITION_PCT", "-0.05")
        with pytest.raises(RiskConfigError, match="below minimum"):
            _env_float("RISK_MAX_POSITION_PCT", 0.05, lo=0.001, hi=1.0)

    def test_zero_max_positions_rejected(self, monkeypatch):
        from src.core.risk_limits import RiskConfigError, _env_int

        monkeypatch.setenv("RISK_MAX_POSITIONS", "0")
        with pytest.raises(RiskConfigError, match="below minimum"):
            _env_int("RISK_MAX_POSITIONS", 10, lo=1, hi=200)

    def test_malformed_env_rejected(self, monkeypatch):
        from src.core.risk_limits import RiskConfigError, _env_float

        monkeypatch.setenv("RISK_MAX_DRAWDOWN_PCT", "fifteen-percent")
        with pytest.raises(RiskConfigError, match="not a valid number"):
            _env_float("RISK_MAX_DRAWDOWN_PCT", 0.15, lo=0.01, hi=0.90)

    def test_drawdown_above_range_rejected(self, monkeypatch):
        from src.core.risk_limits import RiskConfigError, _env_float

        monkeypatch.setenv("RISK_MAX_DRAWDOWN_PCT", "1.5")
        with pytest.raises(RiskConfigError, match="exceeds maximum"):
            _env_float("RISK_MAX_DRAWDOWN_PCT", 0.15, lo=0.01, hi=0.90)

    def test_non_finite_env_rejected(self, monkeypatch):
        from src.core.risk_limits import RiskConfigError, _env_float

        monkeypatch.setenv("RISK_MAX_POSITION_PCT", "inf")
        with pytest.raises(RiskConfigError):
            _env_float("RISK_MAX_POSITION_PCT", 0.05, lo=0.001, hi=1.0)

    def test_non_monotonic_vix_thresholds_rejected(self):
        from src.core.risk_limits import RiskConfigError, VIXThresholds

        with pytest.raises(RiskConfigError, match="strictly increasing"):
            VIXThresholds(low=14.0, mid=20.0, high=28.0, crisis=10.0)

    def test_valid_env_override_accepted(self, monkeypatch):
        from src.core.risk_limits import _env_float

        monkeypatch.setenv("RISK_MAX_POSITION_PCT", "0.03")
        assert _env_float("RISK_MAX_POSITION_PCT", 0.05, lo=0.001, hi=1.0) == 0.03


# ══════════════════════════════════════════════════════════════
# API key timing-safe comparison
# ══════════════════════════════════════════════════════════════


class TestApiKeyComparison:
    def test_uses_timing_safe_compare_digest(self):
        """Guard against regression to a plain `!=` string comparison."""
        import inspect

        from src.api import deps

        source = inspect.getsource(deps._require_matching_api_key)
        assert "!=" not in source
        assert "_header_api_key_valid" in source

        optional_src = inspect.getsource(deps.optional_api_key)
        assert "!=" not in optional_src

    def test_header_api_key_valid_rejects_wrong_and_empty(self):
        from src.api.deps import _header_api_key_valid

        assert _header_api_key_valid("secret", "secret") is True
        assert _header_api_key_valid("secret", "secreT") is False
        assert _header_api_key_valid("secret", "") is False
        assert _header_api_key_valid("secret", None) is False


# ══════════════════════════════════════════════════════════════
# Universe data-quality gate
# ══════════════════════════════════════════════════════════════


class TestUniverseMarketCapDataQuality:
    def _features(self, market_cap, rows: int = 100):
        pd = pytest.importorskip("pandas")
        data = {
            "ticker": ["AAPL"] * rows,
            "close": [100.0] * rows,
            "volume_sma_20": [1_000_000] * rows,
        }
        if market_cap is not _MISSING:
            data["market_cap"] = [market_cap] * rows
        return pd.DataFrame(data)

    def test_missing_market_cap_is_rejected_by_default(self):
        from src.engines.signal_engine import UniverseFilter

        clean, rejections = UniverseFilter().filter(["AAPL"], self._features(_MISSING))
        assert clean == []
        assert "MISSING" in rejections["AAPL"]

    def test_none_market_cap_is_rejected(self):
        from src.engines.signal_engine import UniverseFilter

        clean, rejections = UniverseFilter().filter(["AAPL"], self._features(None))
        assert clean == []
        assert "MISSING" in rejections["AAPL"]

    def test_malformed_market_cap_is_rejected(self):
        from src.engines.signal_engine import UniverseFilter

        clean, rejections = UniverseFilter().filter(
            ["AAPL"], self._features("not-a-number")
        )
        assert clean == []
        assert "MISSING" in rejections["AAPL"]

    def test_research_mode_may_opt_out(self):
        from src.engines.signal_engine import UniverseFilter

        clean, _ = UniverseFilter(require_market_cap=False).filter(
            ["AAPL"], self._features(_MISSING)
        )
        assert clean == ["AAPL"]

    def test_small_cap_still_rejected_on_value(self):
        from src.engines.signal_engine import UniverseFilter

        clean, rejections = UniverseFilter().filter(
            ["AAPL"], self._features(1_000_000.0)
        )
        assert clean == []
        assert "mkt_cap" in rejections["AAPL"]

    def test_valid_large_cap_passes(self):
        from src.engines.signal_engine import UniverseFilter

        clean, rejections = UniverseFilter().filter(
            ["AAPL"], self._features(3_000_000_000_000.0)
        )
        assert clean == ["AAPL"], rejections


_MISSING = object()
