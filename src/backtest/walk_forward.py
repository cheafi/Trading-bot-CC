"""
Purged + embargoed walk-forward validation for time-series strategies.

This is the standard de-facto methodology in quantitative finance
(López de Prado, "Advances in Financial Machine Learning", 2018) to
prevent the most common backtest fraud: train/test contamination from
overlapping holding periods.

Why naive train/test split breaks:
  • Strategies hold positions across the train/test boundary, so the
    train set "knows" outcomes from the test set.
  • Sample weights derived from forward returns leak future info.
  • Same-day features in train and test create autocorrelation leakage.

This module provides:

  PurgedWalkForward
    Splits a date range into rolling train/test windows with:
      • train length (months/days)
      • test length (months/days)
      • step size (how far the window advances)
      • purge_days (gap between train end and test start) — eliminates
        overlap from positions held for up to N days
      • embargo_days (gap between test end and next train start) —
        eliminates contamination from positions opened in test set

  iter_splits(start, end) -> Iterator of (train_start, train_end,
                                          test_start, test_end)

Designed to be backtester-agnostic; callers loop over splits and
drive their own backtest harness per window. Results across windows
should be aggregated (mean Sharpe, worst-drawdown, hit-rate of windows
with positive Sharpe) rather than reporting a single overstated number
from a one-shot split.
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime, timedelta
from typing import Iterator, List, Tuple, Union

DateLike = Union[date, datetime]


@dataclass(frozen=True)
class WalkForwardSplit:
    """One train/test window with purge + embargo gaps."""

    train_start: date
    train_end: date          # inclusive — last day in train
    test_start: date         # = train_end + purge_days + 1
    test_end: date           # inclusive — last day in test

    def as_tuple(self) -> Tuple[date, date, date, date]:
        return (
            self.train_start,
            self.train_end,
            self.test_start,
            self.test_end,
        )


class PurgedWalkForward:
    """
    Walk-forward splitter with purge + embargo for time-series leakage.

    Parameters
    ----------
    train_days : int
        Length of the training window in calendar days.
    test_days : int
        Length of the test (out-of-sample) window in calendar days.
    step_days : int
        How far the window advances each iteration. Set equal to
        ``test_days`` for non-overlapping (anchored) walks.
    purge_days : int
        Calendar days between train end and test start. Must be >= the
        maximum holding period of any strategy you backtest, otherwise
        positions opened in train will close in test (leakage).
    embargo_days : int
        Calendar days of dead zone after each test window before the
        next train window may reuse those dates. Prevents
        information from test positions bleeding back into the next
        train fold.

    Notes
    -----
    The window uses calendar days, not trading days, for simplicity.
    For US equities the ~30% calendar/trading day gap is conservative.
    """

    def __init__(
        self,
        train_days: int = 252 * 2,   # ~2 trading years
        test_days: int = 63,         # ~1 quarter
        step_days: int = 63,
        purge_days: int = 10,        # >= longest holding period
        embargo_days: int = 5,
    ):
        if train_days <= 0 or test_days <= 0 or step_days <= 0:
            raise ValueError("train/test/step days must be positive")
        if purge_days < 0 or embargo_days < 0:
            raise ValueError("purge/embargo must be non-negative")
        self.train_days = train_days
        self.test_days = test_days
        self.step_days = step_days
        self.purge_days = purge_days
        self.embargo_days = embargo_days

    @staticmethod
    def _as_date(d: DateLike) -> date:
        return d.date() if isinstance(d, datetime) else d

    def iter_splits(
        self,
        start: DateLike,
        end: DateLike,
    ) -> Iterator[WalkForwardSplit]:
        """
        Yield purged train/test windows from ``start`` to ``end``.

        Yields nothing if the range is too short for a single
        train + purge + test fold.
        """
        s = self._as_date(start)
        e = self._as_date(end)
        if e <= s:
            return

        train_start = s
        while True:
            train_end = train_start + timedelta(days=self.train_days - 1)
            test_start = train_end + timedelta(days=self.purge_days + 1)
            test_end = test_start + timedelta(days=self.test_days - 1)
            if test_end > e:
                return
            yield WalkForwardSplit(
                train_start=train_start,
                train_end=train_end,
                test_start=test_start,
                test_end=test_end,
            )
            # Advance with embargo built into the step
            train_start = train_start + timedelta(
                days=self.step_days + self.embargo_days
            )

    def split_list(
        self,
        start: DateLike,
        end: DateLike,
    ) -> List[WalkForwardSplit]:
        """Materialized list of splits (handy for testing/reporting)."""
        return list(self.iter_splits(start, end))


def assert_no_overlap(splits: List[WalkForwardSplit]) -> None:
    """
    Sanity check: no train window may overlap any other window's
    [test_start - purge, test_end + embargo]. Useful in tests.

    Raises
    ------
    AssertionError
        If overlap is detected, with the offending pair.
    """
    for i, a in enumerate(splits):
        for j, b in enumerate(splits):
            if i == j:
                continue
            if a.train_end >= b.test_start and a.train_start <= b.test_end:
                raise AssertionError(
                    f"Train window {i} {a.train_start}..{a.train_end} "
                    f"overlaps test window {j} {b.test_start}..{b.test_end}"
                )
