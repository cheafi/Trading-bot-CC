"""
src/engines/walk_forward.py — walk-forward, cost-aware evidence for a rule
=========================================================================

Answers one question for the evidence gate: *does this exact entry rule have
an edge out of sample, after costs?* Pure computation on supplied bars — no
network, no LLM, no defaults standing in for missing data.

Guarantees
----------
* **No look-ahead.** Rules see only bars up to the signal bar. Entries fill at
  the *next* bar's open. A trade still open at the last bar is dropped, never
  marked to an unknown exit.
* **Conservative fills.** A gap through the stop exits at the open; a bar that
  touches both stop and target is scored as the stop.
* **Costs on both sides.** Commission, slippage and half the spread are charged
  on entry and exit; results are also reported at 0× and 2× costs.
* **Purged walk-forward.** Parameters are chosen on each train window using
  only trades that exited before the test window starts, then scored on the
  test window. Only test-window trades are out of sample, and only those are
  graded.
* **Sample size is not validation.** Grading is delegated to
  ``grade_strategy_evidence`` (n ≥ 100 OOS, Wilson CI, PF, expectancy,
  drawdown). A universe that is not point-in-time caps the grade at
  PRELIMINARY, because today's ticker list is survivorship-biased.
"""

from __future__ import annotations

import math
from dataclasses import dataclass
from datetime import timedelta
from typing import Any, Callable, Dict, Iterable, List, Mapping, Optional, Sequence

import pandas as pd

from src.engines.strategy_evidence import (
    EvidenceGrade,
    TradeRecord,
    grade_strategy_evidence,
)

__all__ = [
    "CostModel",
    "Rule",
    "SimTrade",
    "RULES",
    "simulate_trades",
    "walk_forward_report",
]

TRAIN_DAYS = 365
TEST_DAYS = 91
MIN_IS_TRADES_FOR_SELECTION = 5
LOOKBACK_WINDOWS = (("90d", 90), ("6m", 182), ("1y", 365), ("2y", 730))


@dataclass(frozen=True)
class CostModel:
    """Per-side costs in basis points of notional."""

    commission_bps: float = 1.0
    slippage_bps: float = 5.0
    spread_bps: float = 4.0

    @property
    def per_side(self) -> float:
        return (self.commission_bps + self.slippage_bps + self.spread_bps / 2) / 1e4

    def to_dict(self) -> Dict[str, float]:
        return {
            "commission_bps": self.commission_bps,
            "slippage_bps": self.slippage_bps,
            "spread_bps": self.spread_bps,
            "per_side_pct": round(self.per_side * 100, 4),
        }


@dataclass(frozen=True)
class SimTrade:
    ticker: str
    entry_date: pd.Timestamp
    exit_date: pd.Timestamp
    entry_raw: float
    exit_raw: float
    risk_per_share: float
    exit_reason: str
    params_key: str

    def r_multiple(self, cost_per_side: float) -> float:
        entry = self.entry_raw * (1 + cost_per_side)
        exit_ = self.exit_raw * (1 - cost_per_side)
        return (exit_ - entry) / self.risk_per_share


SignalFn = Callable[[pd.DataFrame, Optional[pd.Series], Mapping[str, Any]], pd.Series]


@dataclass(frozen=True)
class Rule:
    """A deterministic long entry rule plus its exit geometry."""

    strategy_id: str
    description: str
    signal: SignalFn
    param_grid: Sequence[Mapping[str, Any]]
    needs_benchmark: bool = False


# ── Indicators (causal: value at t uses bars ≤ t) ─────────────────────────────


def _cols(df: pd.DataFrame) -> Dict[str, str]:
    names = ("Open", "High", "Low", "Close", "Volume")
    return {k: k if k in df.columns else k.lower() for k in names}


def atr_series(df: pd.DataFrame, period: int = 14) -> pd.Series:
    c = _cols(df)
    prev = df[c["Close"]].shift(1)
    tr = pd.concat(
        [
            df[c["High"]] - df[c["Low"]],
            (df[c["High"]] - prev).abs(),
            (df[c["Low"]] - prev).abs(),
        ],
        axis=1,
    ).max(axis=1, skipna=False)
    return tr.rolling(period).mean()


def _brief_rs_leader_signal(
    df: pd.DataFrame, bench: Optional[pd.Series], p: Mapping[str, Any]
) -> pd.Series:
    """data/generate_brief.py TRADE tier: RS63 vs SPY ≥ 15, ≤5% off the 52w
    closing high, volume ≥ 1.2× the prior 20-day average."""
    c = _cols(df)
    close = df[c["Close"]]
    vol = df[c["Volume"]]
    if bench is None:
        return pd.Series(False, index=df.index)
    spy = bench.reindex(df.index).ffill()
    rs = (close / close.shift(62) - 1 - (spy / spy.shift(62) - 1)) * 100
    near_high = close >= p["near_high_frac"] * close.rolling(252, min_periods=1).max()
    vol_ratio = vol / vol.shift(1).rolling(20).mean()
    sig = (rs >= p["rs_min"]) & near_high & (vol_ratio >= p["vol_ratio_min"])
    return sig.fillna(False).astype(bool)


RULES: Dict[str, Rule] = {
    "brief_rs_leader_v1": Rule(
        strategy_id="brief_rs_leader_v1",
        description=(
            "Daily brief TRADE tier (RS63 vs SPY ≥ 15, near 52w high, volume "
            "≥ 1.2×); stop 1×ATR14, target 2R or 3R (the brief's two targets, "
            "chosen per fold in-sample), 20-bar time stop"
        ),
        signal=_brief_rs_leader_signal,
        param_grid=tuple(
            {
                "rs_min": 15.0,
                "near_high_frac": 0.95,
                "vol_ratio_min": 1.2,
                "stop_atr": 1.0,
                "target_r": target_r,
                "max_hold": 20,
            }
            for target_r in (2.0, 3.0)
        ),
        needs_benchmark=True,
    ),
}


def _params_key(p: Mapping[str, Any]) -> str:
    return ",".join(f"{k}={p[k]}" for k in sorted(p))


# ── Simulation ────────────────────────────────────────────────────────────────


def simulate_trades(
    df: pd.DataFrame,
    signal: pd.Series,
    params: Mapping[str, Any],
    *,
    ticker: str = "",
) -> List[SimTrade]:
    """One position at a time; entry at next open after a signal bar."""
    c = _cols(df)
    o = df[c["Open"]].to_numpy(float)
    h = df[c["High"]].to_numpy(float)
    lo = df[c["Low"]].to_numpy(float)
    cl = df[c["Close"]].to_numpy(float)
    atr = atr_series(df).to_numpy(float)
    sig = signal.reindex(df.index).fillna(False).to_numpy(bool)
    idx = df.index
    n = len(df)
    stop_atr = float(params["stop_atr"])
    target_r = float(params["target_r"])
    max_hold = int(params["max_hold"])
    key = _params_key(params)

    trades: List[SimTrade] = []
    t = 0
    while t < n - 1:
        if not sig[t] or not math.isfinite(atr[t]) or atr[t] <= 0:
            t += 1
            continue
        e = t + 1
        entry = o[e]
        if not math.isfinite(entry) or entry <= 0:
            t += 1
            continue
        risk = stop_atr * atr[t]
        stop = entry - risk
        target = entry + target_r * risk
        exit_i, exit_px, reason = None, None, None
        last = min(e + max_hold - 1, n - 1)
        for j in range(e, last + 1):
            if j > e and o[j] <= stop:
                exit_i, exit_px, reason = j, o[j], "stop_gap"
            elif lo[j] <= stop:
                exit_i, exit_px, reason = j, stop, "stop"
            elif j > e and o[j] >= target:
                exit_i, exit_px, reason = j, o[j], "target_gap"
            elif h[j] >= target:
                exit_i, exit_px, reason = j, target, "target"
            if exit_i is not None:
                break
        if exit_i is None:
            if e + max_hold - 1 > n - 1:
                break  # still open at the last bar: outcome unknown, not scored
            exit_i, exit_px, reason = last, cl[last], "time"
        trades.append(
            SimTrade(
                ticker=ticker,
                entry_date=idx[e],
                exit_date=idx[exit_i],
                entry_raw=float(entry),
                exit_raw=float(exit_px),
                risk_per_share=float(risk),
                exit_reason=reason,
                params_key=key,
            )
        )
        t = exit_i + 1
    return trades


# ── Walk-forward ──────────────────────────────────────────────────────────────


@dataclass
class _Fold:
    train_start: pd.Timestamp
    test_start: pd.Timestamp
    test_end: pd.Timestamp


def _folds(start: pd.Timestamp, end: pd.Timestamp) -> List[_Fold]:
    folds = []
    test_start = start + timedelta(days=TRAIN_DAYS)
    while test_start < end:
        folds.append(
            _Fold(
                train_start=test_start - timedelta(days=TRAIN_DAYS),
                test_start=test_start,
                test_end=min(test_start + timedelta(days=TEST_DAYS), end),
            )
        )
        test_start += timedelta(days=TEST_DAYS)
    return folds


def in_sample_trades(trades: Iterable[SimTrade], fold: _Fold) -> List[SimTrade]:
    """Train-window trades that closed before the test window opened (purged)."""
    return [
        tr
        for tr in trades
        if fold.train_start <= tr.entry_date < fold.test_start
        and tr.exit_date < fold.test_start
    ]


def _stats(rs: Sequence[float]) -> Dict[str, Any]:
    if not rs:
        return {
            "trades": 0,
            "win_rate": None,
            "expectancy_r": None,
            "profit_factor": None,
            "total_r": 0.0,
        }
    wins = [r for r in rs if r > 0]
    loss = abs(sum(r for r in rs if r <= 0))
    return {
        "trades": len(rs),
        "win_rate": round(len(wins) / len(rs), 4),
        "expectancy_r": round(sum(rs) / len(rs), 4),
        "profit_factor": round(sum(wins) / loss, 3) if loss > 0 else None,
        "total_r": round(sum(rs), 3),
    }


def walk_forward_report(
    data: Mapping[str, pd.DataFrame],
    rule: Rule,
    *,
    benchmark: Optional[pd.Series] = None,
    costs: CostModel = CostModel(),
    point_in_time_universe: bool = False,
) -> Dict[str, Any]:
    """Purged rolling walk-forward over a universe of tickers."""
    base = {
        "strategy_id": rule.strategy_id,
        "rule": rule.description,
        "costs": costs.to_dict(),
        "method": {
            "type": "purged_rolling_walk_forward",
            "train_days": TRAIN_DAYS,
            "test_days": TEST_DAYS,
            "entry": "next bar open after signal close",
            "same_bar_stop_and_target": "scored as stop",
            "open_trades_at_end": "excluded",
        },
        "universe": sorted(data),
        "point_in_time_universe": point_in_time_universe,
    }

    def _no_backtest(reason: str) -> Dict[str, Any]:
        ev = grade_strategy_evidence([], strategy_id=rule.strategy_id).to_dict()
        ev["reason_codes"] = [reason]
        return {**base, "evidence": ev, "folds": [], "windows": {}, "trades": 0}

    frames = {t: df for t, df in data.items() if df is not None and len(df) > 0}
    if not frames:
        return _no_backtest("NO_PRICE_DATA")
    if rule.needs_benchmark and (benchmark is None or len(benchmark) == 0):
        return _no_backtest("NO_BENCHMARK_DATA")

    start = min(df.index[0] for df in frames.values())
    end = max(df.index[-1] for df in frames.values())
    folds = _folds(pd.Timestamp(start), pd.Timestamp(end))
    if not folds:
        return _no_backtest("HISTORY_SHORTER_THAN_TRAIN_WINDOW")

    # Full-history trade lists per (params, ticker): every trade is causal, so
    # folds only slice by entry/exit date.
    all_trades: Dict[str, List[SimTrade]] = {}
    for params in rule.param_grid:
        key = _params_key(params)
        trades: List[SimTrade] = []
        for t, df in frames.items():
            sig = rule.signal(df, benchmark, params)
            trades.extend(simulate_trades(df, sig, params, ticker=t))
        all_trades[key] = trades

    c = costs.per_side
    oos: List[SimTrade] = []
    is_rs_by_fold: List[float] = []
    fold_rows = []
    # One position per ticker across folds: when the chosen params change, a
    # trade from the previous fold may still be open.
    busy_until: Dict[str, pd.Timestamp] = {}
    overlaps_skipped = 0
    for f in folds:
        best_key, best_exp, selection = None, -math.inf, "in_sample_expectancy"
        for key, trades in all_trades.items():
            is_rs = [tr.r_multiple(c) for tr in in_sample_trades(trades, f)]
            if len(is_rs) < MIN_IS_TRADES_FOR_SELECTION:
                continue
            exp = sum(is_rs) / len(is_rs)
            if exp > best_exp:
                best_key, best_exp = key, exp
        if best_key is None:
            best_key = _params_key(rule.param_grid[0])
            best_exp = None
            selection = "default_params_insufficient_in_sample"
        test = []
        for tr in sorted(
            (
                tr
                for tr in all_trades[best_key]
                if f.test_start <= tr.entry_date < f.test_end
            ),
            key=lambda tr: tr.entry_date,
        ):
            held = busy_until.get(tr.ticker)
            if held is not None and tr.entry_date <= held:
                overlaps_skipped += 1
                continue
            busy_until[tr.ticker] = tr.exit_date
            test.append(tr)
        oos.extend(test)
        if best_exp is not None:
            is_rs_by_fold.append(best_exp)
        st = _stats([tr.r_multiple(c) for tr in test])
        fold_rows.append(
            {
                "test_start": f.test_start.date().isoformat(),
                "test_end": f.test_end.date().isoformat(),
                "params": best_key,
                "selection": selection,
                "in_sample_expectancy_r": None
                if best_exp is None
                else round(best_exp, 4),
                "oos": st,
            }
        )

    oos_rs = [tr.r_multiple(c) for tr in oos]
    report = grade_strategy_evidence(
        [
            TradeRecord(r_multiple=r, strategy_id=rule.strategy_id, out_of_sample=True)
            for r in oos_rs
        ],
        strategy_id=rule.strategy_id,
    )
    if not point_in_time_universe and report.grade is EvidenceGrade.VALIDATED:
        report.grade = EvidenceGrade.PRELIMINARY
        report.reason_codes = ["UNIVERSE_NOT_POINT_IN_TIME"]
    evidence = report.to_dict()
    evidence["basis"] = "walk_forward_oos_backtest"
    evidence["caveats"] = [
        "Daily bars: intrabar order unknown, scored conservatively",
        "Rule thresholds were set by hand, not fitted here",
    ] + (
        []
        if point_in_time_universe
        else [
            "Universe is today's ticker list (survivorship bias) — "
            "grade capped at PRELIMINARY",
        ]
    )

    as_of = pd.Timestamp(end)
    windows = {}
    for label, days in LOOKBACK_WINDOWS:
        cut = as_of - timedelta(days=days)
        rs = [tr.r_multiple(c) for tr in oos if tr.entry_date >= cut]
        windows[label] = {
            **_stats(rs),
            "grade": grade_strategy_evidence(
                [TradeRecord(r_multiple=r, out_of_sample=True) for r in rs]
            ).grade.value,
        }

    folds_with_trades = [r for r in fold_rows if r["oos"]["trades"] > 0]
    positive = [r for r in folds_with_trades if (r["oos"]["expectancy_r"] or 0) > 0]
    is_mean = sum(is_rs_by_fold) / len(is_rs_by_fold) if is_rs_by_fold else None
    oos_mean = sum(oos_rs) / len(oos_rs) if oos_rs else None

    return {
        **base,
        "as_of": as_of.date().isoformat(),
        "evidence": evidence,
        "trades": len(oos),
        "windows": windows,
        "in_sample_vs_oos": {
            "in_sample_expectancy_r": None if is_mean is None else round(is_mean, 4),
            "oos_expectancy_r": None if oos_mean is None else round(oos_mean, 4),
            "degradation_ratio": (
                round(oos_mean / is_mean, 3)
                if is_mean not in (None, 0) and oos_mean is not None
                else None
            ),
        },
        "fold_consistency": {
            "folds": len(fold_rows),
            "folds_with_trades": len(folds_with_trades),
            "positive_folds": len(positive),
            "overlapping_trades_skipped": overlaps_skipped,
        },
        "cost_sensitivity": {
            f"{m}x": _stats([tr.r_multiple(c * m) for tr in oos])["expectancy_r"]
            for m in (0, 1, 2)
        },
        "exit_reasons": _count(tr.exit_reason for tr in oos),
        "folds": fold_rows,
    }


def _count(items: Iterable[str]) -> Dict[str, int]:
    out: Dict[str, int] = {}
    for it in items:
        out[it] = out.get(it, 0) + 1
    return out
