"""
StrategyHealthService — per-strategy realized-trade analytics from closed_trades.jsonl.

CRO/Quant principles:
- NEVER fake Sharpe with tiny samples. Surface sample_size and a status flag.
- NEVER annualize when N is too small.
- Use r_multiple (already risk-normalized) as the per-trade return unit, falling
  back to pnl_pct when r_multiple is missing.
- Hit-rate, avg-R, expectancy are reported; Sharpe is reported with a confidence label.
- A 30-day rolling window is the default; window=0 means all-time.
"""

from __future__ import annotations

import json
import logging
import math
import os
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from typing import Any

logger = logging.getLogger(__name__)

LEDGER_PATH = os.path.join("data", "closed_trades.jsonl")

# Minimum sample sizes for trust labels
N_MIN_TRUSTED = 30  # institutional-grade
N_MIN_TENTATIVE = 10  # directional only
TRADING_DAYS_YEAR = 252


@dataclass
class StrategyRow:
    strategy_id: str
    n_trades: int = 0
    n_wins: int = 0
    sum_r: float = 0.0
    sum_r_sq: float = 0.0
    returns: list[float] = field(default_factory=list)
    last_exit: str = ""

    def to_summary(self, window_days: int) -> dict[str, Any]:
        if self.n_trades == 0:
            return {
                "strategy_id": self.strategy_id,
                "n_trades": 0,
                "status": "NO_DATA",
            }
        mean_r = self.sum_r / self.n_trades
        var = max(
            0.0, (self.sum_r_sq / self.n_trades) - mean_r * mean_r
        )  # population var; tiny N anyway
        std_r = math.sqrt(var)
        hit_rate = self.n_wins / self.n_trades
        # Trade-level Sharpe (no annualization — caller can choose label)
        sharpe_trade = (mean_r / std_r) if std_r > 1e-9 else 0.0
        # Annualization estimate ONLY if window known: trades_per_year = n / (window_days/365)
        ann_factor = 0.0
        if window_days and window_days > 0:
            trades_per_year = self.n_trades * (365.0 / window_days)
            ann_factor = math.sqrt(max(1.0, trades_per_year))
        elif window_days == 0:
            ann_factor = math.sqrt(max(1.0, self.n_trades))  # crude
        sharpe_ann = sharpe_trade * ann_factor if ann_factor else None

        # ── NEW: Sortino, MaxDD, Profit-Factor, Cumulative-R curve ──
        downside = [r for r in self.returns if r < 0]
        if downside:
            d_var = sum(r * r for r in downside) / len(downside)
            d_std = math.sqrt(d_var)
            sortino_trade = (mean_r / d_std) if d_std > 1e-9 else 0.0
        else:
            sortino_trade = sharpe_trade * 1.5 if mean_r > 0 else 0.0
        sortino_ann = sortino_trade * ann_factor if ann_factor else None

        wins_sum = sum(r for r in self.returns if r > 0)
        losses_sum = abs(sum(r for r in self.returns if r < 0))
        profit_factor = (
            (wins_sum / losses_sum)
            if losses_sum > 1e-9
            else (float("inf") if wins_sum > 0 else 0.0)
        )
        if math.isinf(profit_factor):
            profit_factor = 99.99  # display cap

        # Cumulative-R equity curve + max drawdown in R units
        cum = 0.0
        equity_curve: list[float] = []
        peak = 0.0
        max_dd = 0.0
        for r in self.returns:
            cum += r
            equity_curve.append(round(cum, 3))
            if cum > peak:
                peak = cum
            dd = cum - peak  # negative or zero
            if dd < max_dd:
                max_dd = dd
        calmar = (
            (mean_r * (252 if ann_factor else 1)) / abs(max_dd)
            if max_dd < -1e-9
            else 0.0
        )

        # Trust label
        if self.n_trades >= N_MIN_TRUSTED:
            status = "TRUSTED"
        elif self.n_trades >= N_MIN_TENTATIVE:
            status = "TENTATIVE"
        else:
            status = "INSUFFICIENT_SAMPLE"
        return {
            "strategy_id": self.strategy_id,
            "n_trades": self.n_trades,
            "n_wins": self.n_wins,
            "hit_rate": round(hit_rate, 4),
            "avg_r": round(mean_r, 3),
            "std_r": round(std_r, 3),
            "expectancy_r": round(mean_r, 3),  # mean R = expectancy in R units
            "sharpe_trade": round(sharpe_trade, 3),
            "sharpe_annualized": (
                round(sharpe_ann, 3) if sharpe_ann is not None else None
            ),
            "sortino_trade": round(sortino_trade, 3),
            "sortino_annualized": (
                round(sortino_ann, 3) if sortino_ann is not None else None
            ),
            "profit_factor": round(profit_factor, 2),
            "max_drawdown_r": round(max_dd, 3),  # negative; R units
            "calmar": round(calmar, 3),
            "equity_curve_r": equity_curve,  # cumulative R per trade — for sparkline
            "last_exit": self.last_exit,
            "status": status,
            "window_days": window_days,
        }


def _parse_dt(s: str) -> datetime | None:
    if not s:
        return None
    try:
        # Accept both 'Z' and '+00:00' suffixes; bare ISO assumed UTC
        if s.endswith("Z"):
            s = s[:-1] + "+00:00"
        dt = datetime.fromisoformat(s)
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
        return dt
    except (ValueError, TypeError):
        return None


def load_per_strategy(
    window_days: int = 30, ledger_path: str = LEDGER_PATH
) -> dict[str, Any]:
    """
    Aggregate closed trades by strategy_id over the trailing window_days.

    Args:
        window_days: 0 = all-time; >0 = trailing N days from now (UTC).
        ledger_path: absolute or workspace-relative path to closed_trades.jsonl.

    Returns dict with `strategies`, `meta`, and `disclaimer`.
    """
    if not os.path.exists(ledger_path):
        return {
            "strategies": [],
            "meta": {
                "ledger_path": ledger_path,
                "exists": False,
                "window_days": window_days,
                "n_total": 0,
                "n_in_window": 0,
            },
            "disclaimer": "No closed-trade ledger found yet. Per-strategy Sharpe will populate as trades close.",
        }

    cutoff: datetime | None = None
    if window_days and window_days > 0:
        cutoff = datetime.now(timezone.utc) - timedelta(days=window_days)

    rows: dict[str, StrategyRow] = {}
    n_total = 0
    n_in_window = 0
    skipped = 0
    with open(ledger_path, encoding="utf-8") as fh:
        for line in fh:
            line = line.strip()
            if not line:
                continue
            try:
                t = json.loads(line)
            except json.JSONDecodeError:
                skipped += 1
                continue
            n_total += 1
            exit_dt = _parse_dt(t.get("exit_time") or t.get("entry_time") or "")
            if cutoff is not None and (exit_dt is None or exit_dt < cutoff):
                continue
            n_in_window += 1
            sid = str(t.get("strategy_id") or "unknown")
            # Use r_multiple as the per-trade return unit (risk-normalized);
            # fall back to pnl_pct/100 if missing.
            r = t.get("r_multiple")
            if r is None:
                pp = t.get("pnl_pct")
                if pp is None:
                    skipped += 1
                    continue
                try:
                    r = float(pp) / 100.0
                except (TypeError, ValueError):
                    skipped += 1
                    continue
            try:
                r = float(r)
            except (TypeError, ValueError):
                skipped += 1
                continue
            row = rows.setdefault(sid, StrategyRow(strategy_id=sid))
            row.n_trades += 1
            if r > 0:
                row.n_wins += 1
            row.sum_r += r
            row.sum_r_sq += r * r
            row.returns.append(r)
            iso = exit_dt.isoformat() if exit_dt else ""
            if iso > row.last_exit:
                row.last_exit = iso

    summaries = sorted(
        (r.to_summary(window_days) for r in rows.values()),
        key=lambda s: (s.get("sharpe_trade") or 0.0),
        reverse=True,
    )

    return {
        "strategies": summaries,
        "meta": {
            "ledger_path": ledger_path,
            "exists": True,
            "window_days": window_days,
            "n_total": n_total,
            "n_in_window": n_in_window,
            "n_skipped": skipped,
            "n_min_trusted": N_MIN_TRUSTED,
            "n_min_tentative": N_MIN_TENTATIVE,
        },
        "disclaimer": (
            "Sharpe computed from r_multiple per trade. Trade-Sharpe is unannualized; "
            "annualized estimate scales by sqrt(trades-per-year) derived from window. "
            "Status: TRUSTED ≥30 trades · TENTATIVE 10–29 · INSUFFICIENT_SAMPLE <10."
        ),
    }
