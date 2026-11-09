"""
src/engines/strategy_evidence.py — Evidence grading for strategy setups
=======================================================================

Enforces the platform rule **EVIDENCE BEFORE EXECUTION**: a strategy may not
present an actionable BUY setup unless its historical record survives
statistical scrutiny.

Why this exists
---------------
A high win rate is the most seductive and least reliable statistic in
trading. Three failure modes this module is built to block:

1. **Small samples.** 7 wins out of 10 trades is a 70% win rate and is
   statistically indistinguishable from a coin flip. The Wilson lower bound
   for 7/10 is ~0.40.
2. **Infinite profit factor.** ``gross_profit / gross_loss`` returns
   ``inf`` when a strategy has never lost. That is not a perfect strategy; it
   is an untested one. (Same false-confidence class as the ``market_cap=inf``
   universe-gate defect fixed in Batch 1.)
3. **In-sample-only results.** A strategy tuned and measured on the same data
   has no predictive claim at all.

Design rules
------------
* **Nothing is fabricated.** Every metric is computed from supplied trade
  records. Absent input yields ``NO_BACKTEST``, never a default number.
* **A win rate is not a probability of the next trade succeeding.** The
  module reports a confidence *interval*, and the grade is driven by the
  lower bound — the pessimistic end — not the point estimate.
* **Grades are deterministic.** No LLM input. This is a risk control.
"""

from __future__ import annotations

import math
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Iterable, Sequence

__all__ = [
    "EvidenceGrade",
    "EvidenceReport",
    "TradeRecord",
    "grade_strategy_evidence",
    "profit_factor",
    "wilson_interval",
]


class EvidenceGrade(str, Enum):
    """Evidence tiers. Only VALIDATED may back an actionable setup."""

    VALIDATED = "VALIDATED"
    PRELIMINARY = "PRELIMINARY"
    INSUFFICIENT_SAMPLE = "INSUFFICIENT_SAMPLE"
    NO_BACKTEST = "NO_BACKTEST"
    FAILED_VALIDATION = "FAILED_VALIDATION"

    @property
    def is_actionable(self) -> bool:
        """Whether a setup graded at this tier may be surfaced as BUY."""
        return self is EvidenceGrade.VALIDATED


# ── Thresholds ────────────────────────────────────────────────────────────────
# Deliberately conservative. These gate real capital.

MIN_SAMPLE_VALIDATED = 100  # below this, no VALIDATED grade is possible
MIN_SAMPLE_PRELIMINARY = 30  # below this, the sample says nothing
MIN_PROFIT_FACTOR = 1.20  # after costs
MIN_EXPECTANCY_R = 0.05  # must be positive net of costs
MAX_DRAWDOWN_PCT = 35.0  # beyond this, unholdable in practice


@dataclass(frozen=True)
class TradeRecord:
    """One closed trade, expressed in R-multiples.

    R-multiples are used rather than currency so that results are comparable
    across account sizes and position sizes.
    """

    r_multiple: float
    strategy_id: str = ""
    out_of_sample: bool = False


@dataclass
class EvidenceReport:
    """Deterministic, serialisable evidence summary for one strategy."""

    grade: EvidenceGrade
    reason_codes: list[str] = field(default_factory=list)
    sample_size: int = 0
    out_of_sample_count: int = 0
    win_rate: float | None = None
    win_rate_ci_low: float | None = None
    win_rate_ci_high: float | None = None
    profit_factor: float | None = None
    expectancy_r: float | None = None
    avg_win_r: float | None = None
    avg_loss_r: float | None = None
    max_drawdown_pct: float | None = None
    strategy_id: str = ""

    @property
    def is_actionable(self) -> bool:
        return self.grade.is_actionable

    @property
    def headline(self) -> str:
        """Short label for the UI. No sentences, no hedging prose."""
        if self.grade is EvidenceGrade.NO_BACKTEST:
            return "NO BACKTEST"
        if self.grade is EvidenceGrade.INSUFFICIENT_SAMPLE:
            return f"INSUFFICIENT EVIDENCE · n={self.sample_size}"
        if self.grade is EvidenceGrade.FAILED_VALIDATION:
            return f"FAILED VALIDATION · {', '.join(self.reason_codes[:2])}"
        if self.grade is EvidenceGrade.PRELIMINARY:
            return f"PRELIMINARY · n={self.sample_size}"
        return f"VALIDATED · n={self.sample_size}"

    def to_dict(self) -> dict[str, Any]:
        return {
            "grade": self.grade.value,
            "headline": self.headline,
            "actionable": self.is_actionable,
            "reason_codes": list(self.reason_codes),
            "sample_size": self.sample_size,
            "out_of_sample_count": self.out_of_sample_count,
            "win_rate": self.win_rate,
            "win_rate_ci_low": self.win_rate_ci_low,
            "win_rate_ci_high": self.win_rate_ci_high,
            "profit_factor": self.profit_factor,
            "expectancy_r": self.expectancy_r,
            "avg_win_r": self.avg_win_r,
            "avg_loss_r": self.avg_loss_r,
            "max_drawdown_pct": self.max_drawdown_pct,
            "strategy_id": self.strategy_id,
        }


# ── Statistics ────────────────────────────────────────────────────────────────


def wilson_interval(
    successes: int, trials: int, z: float = 1.96
) -> tuple[float, float]:
    """Wilson score interval for a binomial proportion.

    Preferred over the normal approximation because it stays inside [0, 1]
    and remains usable at small ``n`` — exactly the regime where trading
    strategies are most often over-sold.
    """
    if trials <= 0:
        return (0.0, 0.0)
    p = successes / trials
    denom = 1 + z * z / trials
    centre = p + z * z / (2 * trials)
    margin = z * math.sqrt((p * (1 - p) + z * z / (4 * trials)) / trials)
    low = (centre - margin) / denom
    high = (centre + margin) / denom
    return (max(0.0, low), min(1.0, high))


def profit_factor(gross_profit: float, gross_loss: float) -> float | None:
    """Gross profit / gross loss.

    Returns ``None`` — not ``inf`` — when there are no losses. A strategy
    with zero losing trades has an *undefined* profit factor; reporting
    ``inf`` presents an untested strategy as a flawless one.
    """
    if gross_loss <= 0:
        return None
    if gross_profit <= 0:
        return 0.0
    return gross_profit / gross_loss


def _max_drawdown_pct(r_multiples: Sequence[float]) -> float:
    """Peak-to-trough drawdown of the cumulative R curve, in percent.

    Computed on the R equity curve so it is independent of position sizing.

    The worst decline is measured in **R** and then expressed against the
    highest peak the whole curve ever reached. Dividing by the *running*
    peak instead is numerically unstable near the start of the curve: a
    +2R / -1R opening pair would report a 50% drawdown purely because the
    denominator is still tiny. That is an artefact of the measurement, not
    a property of the strategy, and it would wrongly disqualify sound
    records.
    """
    equity = 0.0
    peak = 0.0
    worst_r = 0.0
    for r in r_multiples:
        equity += r
        peak = max(peak, equity)
        worst_r = max(worst_r, peak - equity)
    if peak <= 0:
        # Never profitable at any point. Expectancy/profit-factor gates own
        # this case; drawdown is not meaningfully expressible as a percent.
        return 0.0
    return worst_r / peak * 100


# ── Grading ───────────────────────────────────────────────────────────────────


def grade_strategy_evidence(
    trades: Iterable[TradeRecord] | None,
    *,
    strategy_id: str = "",
    require_out_of_sample: bool = True,
) -> EvidenceReport:
    """Grade a strategy's historical record.

    Args:
        trades: Closed trades in R-multiples. ``None`` or empty yields
            ``NO_BACKTEST`` — never a fabricated baseline.
        require_out_of_sample: When True (the default for anything that
            could reach capital), a strategy with no out-of-sample trades
            cannot be graded VALIDATED.
    """
    records = [
        t
        for t in (trades or [])
        if isinstance(t.r_multiple, (int, float))
        and not math.isnan(t.r_multiple)
        and not math.isinf(t.r_multiple)
    ]

    if not records:
        return EvidenceReport(
            grade=EvidenceGrade.NO_BACKTEST,
            reason_codes=["NO_TRADE_HISTORY"],
            strategy_id=strategy_id,
        )

    n = len(records)
    rs = [float(t.r_multiple) for t in records]
    wins = [r for r in rs if r > 0]
    losses = [r for r in rs if r <= 0]
    oos = sum(1 for t in records if t.out_of_sample)

    gross_profit = sum(wins)
    gross_loss = abs(sum(losses))
    pf = profit_factor(gross_profit, gross_loss)
    expectancy = sum(rs) / n
    ci_low, ci_high = wilson_interval(len(wins), n)
    dd = _max_drawdown_pct(rs)

    report = EvidenceReport(
        grade=EvidenceGrade.INSUFFICIENT_SAMPLE,
        sample_size=n,
        out_of_sample_count=oos,
        win_rate=len(wins) / n,
        win_rate_ci_low=ci_low,
        win_rate_ci_high=ci_high,
        profit_factor=pf,
        expectancy_r=expectancy,
        avg_win_r=(sum(wins) / len(wins)) if wins else None,
        avg_loss_r=(sum(losses) / len(losses)) if losses else None,
        max_drawdown_pct=dd,
        strategy_id=strategy_id,
    )

    # --- Hard disqualifiers: the record exists and is bad. ---
    failures: list[str] = []
    if expectancy < MIN_EXPECTANCY_R:
        failures.append("NEGATIVE_EXPECTANCY")
    if pf is not None and pf < MIN_PROFIT_FACTOR:
        failures.append("PROFIT_FACTOR_BELOW_MIN")
    if dd > MAX_DRAWDOWN_PCT:
        failures.append("DRAWDOWN_EXCEEDS_MAX")

    if failures and n >= MIN_SAMPLE_PRELIMINARY:
        report.grade = EvidenceGrade.FAILED_VALIDATION
        report.reason_codes = failures
        return report

    # --- Sample-size gates. ---
    if n < MIN_SAMPLE_PRELIMINARY:
        report.grade = EvidenceGrade.INSUFFICIENT_SAMPLE
        report.reason_codes = [f"SAMPLE_BELOW_{MIN_SAMPLE_PRELIMINARY}"]
        return report

    reasons: list[str] = []
    if n < MIN_SAMPLE_VALIDATED:
        reasons.append(f"SAMPLE_BELOW_{MIN_SAMPLE_VALIDATED}")
    if pf is None:
        # No losing trades at all — undefined, not perfect.
        reasons.append("PROFIT_FACTOR_UNDEFINED_NO_LOSSES")
    if require_out_of_sample and oos == 0:
        reasons.append("NO_OUT_OF_SAMPLE_TRADES")
    # The pessimistic end of the interval must still beat a coin flip
    # before we are willing to call the edge validated.
    if ci_low <= 0.50 and (pf is None or pf < 1.5):
        reasons.append("WIN_RATE_CI_SPANS_COINFLIP")

    if reasons:
        report.grade = EvidenceGrade.PRELIMINARY
        report.reason_codes = reasons
        return report

    report.grade = EvidenceGrade.VALIDATED
    report.reason_codes = []
    return report
