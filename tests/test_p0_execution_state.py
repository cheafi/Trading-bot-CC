"""Sprint 2 regression tests — execution-state correctness & price safety.

Covers:
  * Exit detection must not mutate exit state before a confirmed fill
  * Idempotent partial-exit commits (duplicate / out-of-order fill events)
  * Rejected orders must leave the partial level retryable
  * Short-direction partial P&L sign
  * Fail-closed price validation (NaN / Inf / negative / zero / missing)
  * Stop-placement side validation for long and short
"""

from __future__ import annotations

from datetime import datetime

import pytest

from src.core.price_validation import (
    InvalidPriceError,
    PriceRejectionCode,
    validate_price,
    validate_stop_placement,
)


def _long_position(**overrides):
    from src.algo.position_manager import Position, PositionStatus

    pos = Position(ticker="AAPL", strategy_id="momentum")
    pos.entry_price = 100.0
    pos.shares = 300
    pos.original_shares = 300
    pos.stop_loss_price = 95.0
    pos.target_1r_price = 105.0
    pos.target_2r_price = 110.0
    pos.status = PositionStatus.OPEN
    pos.entry_date = datetime(2026, 1, 5)
    for key, value in overrides.items():
        setattr(pos, key, value)
    return pos


# ══════════════════════════════════════════════════════════════
# Price validation
# ══════════════════════════════════════════════════════════════


class TestPriceValidation:
    @pytest.mark.parametrize(
        "value,code",
        [
            (None, PriceRejectionCode.MISSING),
            (float("nan"), PriceRejectionCode.NAN),
            (float("inf"), PriceRejectionCode.INFINITE),
            (float("-inf"), PriceRejectionCode.INFINITE),
            (-1.0, PriceRejectionCode.NEGATIVE),
            (0.0, PriceRejectionCode.ZERO),
            ("abc", PriceRejectionCode.NOT_NUMERIC),
            (True, PriceRejectionCode.NOT_NUMERIC),
        ],
    )
    def test_invalid_prices_rejected_with_reason_code(self, value, code):
        ok, reason = validate_price(value)
        assert ok is False
        assert reason == code

    def test_valid_price_accepted(self):
        assert validate_price(101.25) == (True, PriceRejectionCode.OK)

    def test_zero_allowed_when_sentinel(self):
        ok, _ = validate_price(0.0, allow_zero=True)
        assert ok is True


class TestStopPlacement:
    def test_long_stop_below_entry_is_valid(self):
        ok, _ = validate_stop_placement(
            entry_price=100.0, stop_price=95.0, direction="long"
        )
        assert ok is True

    def test_long_stop_above_entry_rejected(self):
        ok, code = validate_stop_placement(
            entry_price=100.0, stop_price=105.0, direction="long"
        )
        assert ok is False
        assert code == "STOP_WRONG_SIDE_LONG"

    def test_short_stop_above_entry_is_valid(self):
        ok, _ = validate_stop_placement(
            entry_price=100.0, stop_price=105.0, direction="short"
        )
        assert ok is True

    def test_short_stop_below_entry_rejected(self):
        ok, code = validate_stop_placement(
            entry_price=100.0, stop_price=95.0, direction="short"
        )
        assert ok is False
        assert code == "STOP_WRONG_SIDE_SHORT"

    def test_stop_equal_to_entry_rejected(self):
        ok, code = validate_stop_placement(
            entry_price=100.0, stop_price=100.0, direction="long"
        )
        assert ok is False
        assert code == "STOP_WRONG_SIDE_LONG"

    def test_missing_stop_reported_not_silently_accepted(self):
        ok, code = validate_stop_placement(
            entry_price=100.0, stop_price=0.0, direction="long"
        )
        assert ok is False
        assert code == "STOP_MISSING"

    def test_nan_entry_rejected(self):
        ok, code = validate_stop_placement(
            entry_price=float("nan"), stop_price=95.0, direction="long"
        )
        assert ok is False
        assert code.startswith("ENTRY_")


# ══════════════════════════════════════════════════════════════
# Position price hygiene
# ══════════════════════════════════════════════════════════════


class TestPositionPriceHygiene:
    @pytest.mark.parametrize("bad", [float("nan"), float("inf"), -5.0, 0.0, None])
    def test_update_price_rejects_invalid_quote(self, bad):
        pos = _long_position()
        with pytest.raises(InvalidPriceError):
            pos.update_price(bad)

    def test_nan_quote_does_not_poison_unrealized_pnl(self):
        pos = _long_position()
        pos.update_price(110.0)
        good_pnl = pos.unrealized_pnl
        with pytest.raises(InvalidPriceError):
            pos.update_price(float("nan"))
        # State must be unchanged, not NaN.
        assert pos.unrealized_pnl == good_pnl
        assert pos.current_price == 110.0

    def test_close_position_rejects_invalid_fill_price(self):
        pos = _long_position()
        with pytest.raises(InvalidPriceError):
            pos.close_position(float("nan"), datetime(2026, 2, 2), "manual")


# ══════════════════════════════════════════════════════════════
# Exit lifecycle: detection vs confirmation
# ══════════════════════════════════════════════════════════════


class TestExitDetectionIsPure:
    def test_touching_target_does_not_mark_partial_filled(self):
        """A price touch is not an execution."""
        pos = _long_position()
        should_exit, reason = pos.check_exit_conditions(105.0, datetime(2026, 1, 6))
        assert (should_exit, reason) == (True, "partial_1r")
        assert pos.partial_exit_1r is False  # no fill yet

    def test_touching_target_does_not_move_stop(self):
        """The operator's stop must not move without a fill."""
        pos = _long_position()
        pos.check_exit_conditions(105.0, datetime(2026, 1, 6))
        assert pos.stop_loss_price == 95.0

    def test_unfilled_level_is_resignalled_on_next_poll(self):
        """A rejected order must not consume the partial-exit slot."""
        pos = _long_position()
        first = pos.check_exit_conditions(105.0, datetime(2026, 1, 6))
        second = pos.check_exit_conditions(106.0, datetime(2026, 1, 7))
        assert first == second == (True, "partial_1r")

    def test_repeated_price_updates_are_stable(self):
        pos = _long_position()
        results = [
            pos.check_exit_conditions(105.0, datetime(2026, 1, 6)) for _ in range(5)
        ]
        assert all(r == (True, "partial_1r") for r in results)
        assert pos.partial_exit_1r is False


class TestPartialExitCommit:
    def test_commit_moves_stop_to_breakeven(self):
        pos = _long_position()
        assert pos.commit_partial_exit("partial_1r") is True
        assert pos.partial_exit_1r is True
        assert pos.stop_loss_price == 100.0  # breakeven, after the fill

    def test_duplicate_fill_event_is_ignored(self):
        pos = _long_position()
        assert pos.commit_partial_exit("partial_1r") is True
        assert pos.commit_partial_exit("partial_1r") is False

    def test_out_of_order_fill_events_do_not_corrupt_state(self):
        pos = _long_position()
        assert pos.commit_partial_exit("partial_2r") is True
        assert pos.commit_partial_exit("partial_1r") is True
        assert pos.partial_exit_1r is True
        assert pos.partial_exit_2r is True

    def test_after_commit_level_no_longer_signals(self):
        pos = _long_position()
        pos.commit_partial_exit("partial_1r")
        should_exit, reason = pos.check_exit_conditions(105.0, datetime(2026, 1, 6))
        assert reason != "partial_1r"

    def test_short_commit_moves_stop_down_to_breakeven(self):
        pos = _long_position(
            direction="short",
            stop_loss_price=105.0,
            target_1r_price=95.0,
            target_2r_price=90.0,
        )
        assert pos.commit_partial_exit("partial_1r") is True
        assert pos.stop_loss_price == 100.0

    def test_unknown_reason_commits_nothing(self):
        pos = _long_position()
        assert pos.commit_partial_exit("stop_loss") is False
        assert pos.partial_exit_1r is False


# ══════════════════════════════════════════════════════════════
# Manager-level partial exits
# ══════════════════════════════════════════════════════════════


def _manager():
    from src.algo.position_manager import PositionManager

    return PositionManager()


class TestReducePosition:
    def _seed(self, mgr, pos):
        mgr.positions[pos.ticker] = pos
        return pos

    def test_short_partial_pnl_sign_is_correct(self):
        """Shorts profit when price falls; the long-only formula inverted it."""
        mgr = _manager()
        pos = self._seed(
            mgr,
            _long_position(direction="short", stop_loss_price=105.0),
        )
        pnl = mgr.reduce_position("AAPL", 100, 90.0, "partial_1r")
        # Short from 100, covering 100 shares at 90 => +1000.
        assert pnl == pytest.approx(1000.0)

    def test_long_partial_pnl_unchanged(self):
        mgr = _manager()
        self._seed(mgr, _long_position())
        pnl = mgr.reduce_position("AAPL", 100, 110.0, "partial_1r")
        assert pnl == pytest.approx(1000.0)

    def test_remaining_quantity_is_preserved(self):
        mgr = _manager()
        pos = self._seed(mgr, _long_position())
        mgr.reduce_position("AAPL", 100, 110.0, "partial_1r")
        assert pos.shares == 200

    def test_invalid_fill_price_rejected_without_state_change(self):
        mgr = _manager()
        pos = self._seed(mgr, _long_position())
        assert mgr.reduce_position("AAPL", 100, float("nan"), "partial_1r") is None
        assert pos.shares == 300
        assert pos.partial_exit_1r is False

    def test_non_positive_size_rejected(self):
        mgr = _manager()
        pos = self._seed(mgr, _long_position())
        assert mgr.reduce_position("AAPL", 0, 110.0, "partial_1r") is None
        assert pos.shares == 300

    def test_unknown_ticker_is_safe(self):
        mgr = _manager()
        assert mgr.reduce_position("ZZZZ", 10, 110.0, "partial_1r") is None


class TestUpdateAllPositionsLifecycle:
    def test_partial_committed_only_after_fill(self):
        mgr = _manager()
        pos = _long_position()
        mgr.positions["AAPL"] = pos
        mgr.update_all_positions({"AAPL": 105.0}, datetime(2026, 1, 6))
        assert pos.partial_exit_1r is True
        assert pos.shares == 200

    def test_failed_fill_leaves_level_retryable(self, monkeypatch):
        """Broker rejection / disconnection must not consume the level."""
        mgr = _manager()
        pos = _long_position()
        mgr.positions["AAPL"] = pos

        monkeypatch.setattr(mgr, "reduce_position", lambda *a, **k: None)
        mgr.update_all_positions({"AAPL": 105.0}, datetime(2026, 1, 6))

        assert pos.partial_exit_1r is False
        assert pos.shares == 300
        assert pos.stop_loss_price == 95.0

        # Next poll re-signals the same level.
        should_exit, reason = pos.check_exit_conditions(105.0, datetime(2026, 1, 7))
        assert (should_exit, reason) == (True, "partial_1r")

    def test_repeated_polls_do_not_double_submit(self):
        mgr = _manager()
        pos = _long_position()
        mgr.positions["AAPL"] = pos

        calls: list[int] = []
        original = mgr.reduce_position

        def _spy(ticker, shares, price, reason="partial"):
            calls.append(shares)
            return original(ticker, shares, price, reason)

        mgr.reduce_position = _spy
        for _ in range(4):
            mgr.update_all_positions({"AAPL": 105.0}, datetime(2026, 1, 6))

        # partial_1r fires once; subsequent polls fall through to partial_2r
        # only if its target is touched (110 > 105), so exactly one call.
        assert len(calls) == 1
