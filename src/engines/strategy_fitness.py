"""
Strategy Fitness Matrix — per-ticker × strategy eligibility (research_only).

Expectancy-first gate: OOS Sharpe, profit factor, OOS/IS stability, DSR.
Never grants deploy authority — feeds research ranking and bandit context only.
"""

from __future__ import annotations

import json
import logging
import math
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional, Sequence, Union

logger = logging.getLogger(__name__)

_DATA_DIR = Path(__file__).resolve().parents[2] / "data"
_MATRIX_PATH = _DATA_DIR / "strategy_fitness_matrix.json"

_EULER = 0.5772156649
_SQRT2 = math.sqrt(2.0)

# Eligibility gates (expectancy-first, not win-rate)
_MIN_OOS_TRADES = 60
_MIN_OOS_SHARPE = 0.8
_MIN_OOS_IS_RATIO = 0.6
_MIN_PROFIT_FACTOR = 1.3
_MIN_DSR = 0.95
_DEFAULT_SLIPPAGE_PF_DISCOUNT = 0.92
_DEFAULT_ANNUALISATION = 252


@dataclass
class StrategyFitnessRecord:
    """Per (ticker, strategy) walk-forward fitness row."""

    ticker: str
    strategy: str
    oos_sharpe: float
    profit_factor: float
    max_dd: float
    trade_count: int
    oos_is_ratio: float
    dsr_score: float
    dsr_passed: bool
    eligible: bool
    is_sharpe: float = 0.0
    after_slippage: bool = False
    ineligible_reasons: List[str] = field(default_factory=list)
    authority: str = "research_only"
    may_authorize_deploy: bool = False

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


def _norm_cdf(z: float) -> float:
    """Standard normal CDF via erf — no scipy dependency."""
    if not math.isfinite(z):
        return 0.0
    return 0.5 * (1.0 + math.erf(z / _SQRT2))


def _norm_ppf(p: float) -> float:
    """
    Acklam rational approximation for inverse standard normal CDF.
    Valid for 0 < p < 1; clamps near boundaries.
    """
    if p <= 0.0:
        return -10.0
    if p >= 1.0:
        return 10.0

    a = (
        -3.969683028665376e01,
        2.209460984245205e02,
        -2.759285104469687e02,
        1.383577518672690e02,
        -3.066479806614716e01,
        2.506628277459239e00,
    )
    b = (
        -5.447609879822406e01,
        1.615858368580409e02,
        -1.556989798598866e02,
        6.680131188771972e01,
        -1.328068155288572e01,
    )
    c = (
        -7.784894002430293e-03,
        -3.223964580411365e-01,
        -2.400758277161838e00,
        -2.549539540214597e00,
        4.374664141464968e00,
        2.938163982698783e00,
    )
    d = (
        7.784695709041446e-03,
        3.224671290700398e-01,
        2.445134137142996e00,
        3.754408661907416e00,
    )
    plow = 0.02425
    phigh = 1.0 - plow

    if p < plow:
        q = math.sqrt(-2.0 * math.log(p))
        return (
            (((((c[0] * q + c[1]) * q + c[2]) * q + c[3]) * q + c[4]) * q + c[5])
            / ((((d[0] * q + d[1]) * q + d[2]) * q + d[3]) * q + 1.0)
        )
    if p > phigh:
        q = math.sqrt(-2.0 * math.log(1.0 - p))
        return -(
            (((((c[0] * q + c[1]) * q + c[2]) * q + c[3]) * q + c[4]) * q + c[5])
            / ((((d[0] * q + d[1]) * q + d[2]) * q + d[3]) * q + 1.0)
        )

    q = p - 0.5
    r = q * q
    return (
        (((((a[0] * r + a[1]) * r + a[2]) * r + a[3]) * r + a[4]) * r + a[5])
        * q
        / (((((b[0] * r + b[1]) * r + b[2]) * r + b[3]) * r + b[4]) * r + 1.0)
    )


def _sharpe_std_error(
    sharpe: float,
    num_observations: int,
    *,
    skew: float = 0.0,
    kurtosis: float = 3.0,
) -> float:
    """
    Standard error of Sharpe ratio estimate (Bailey & López de Prado, 2014).

    Assumes i.i.d. returns; kurtosis is raw (Gaussian = 3.0, not excess).
    """
    if num_observations < 2:
        return float("inf")
    adj = 1.0 - skew * sharpe + ((kurtosis - 1.0) / 4.0) * sharpe * sharpe
    adj = max(adj, 1e-9)
    return math.sqrt(adj / (num_observations - 1))


def _expected_max_sharpe(num_trials: int, sharpe_std: float) -> float:
    """Expected maximum Sharpe under null (selection bias), simplified EVT."""
    if num_trials < 2 or not math.isfinite(sharpe_std) or sharpe_std <= 0:
        return 0.0
    z1 = _norm_ppf(1.0 - 1.0 / num_trials)
    z2 = _norm_ppf(1.0 - 1.0 / (num_trials * math.e))
    return sharpe_std * ((1.0 - _EULER) * z1 + _EULER * z2)


def compute_deflated_sharpe(
    observed_sharpe: float,
    *,
    num_trials: int = 1,
    num_observations: int = 60,
    skew: float = 0.0,
    kurtosis: float = 3.0,
    annualisation_factor: int = _DEFAULT_ANNUALISATION,
) -> float:
    """
    Bailey & López de Prado Deflated Sharpe Ratio (simplified).

    Returns P(true Sharpe > 0) after correcting for:
      - Multiple testing (num_trials strategy variants tried)
      - Finite sample (num_observations OOS trades or periods)
      - Non-normality via skew/kurtosis adjustment on SR standard error

    Assumptions (documented):
      - Sharpe is annualized from per-trade or per-period returns
      - Trials are independent strategy/parameter variants on same ticker
      - No serial correlation adjustment (conservative: may overstate DSR)
      - Gaussian null for max-Sharpe via simplified extreme-value approximation

    Returns value in [0, 1]; higher = more confidence edge is real, not luck.
    """
    if num_observations < 2:
        return 0.0
    if not math.isfinite(observed_sharpe):
        return 0.0

    ann = max(int(annualisation_factor or _DEFAULT_ANNUALISATION), 1)
    sharpe_ann = observed_sharpe * math.sqrt(ann / max(num_observations, 1))

    sr_std = _sharpe_std_error(
        sharpe_ann,
        num_observations,
        skew=skew,
        kurtosis=kurtosis,
    )
    if not math.isfinite(sr_std) or sr_std <= 0:
        return 0.0

    sr_star = _expected_max_sharpe(max(num_trials, 1), sr_std)
    z = (sharpe_ann - sr_star) / sr_std
    return round(_norm_cdf(z), 6)


def dsr_passed(dsr_score: float, *, min_dsr: float = _MIN_DSR) -> bool:
    return float(dsr_score) >= float(min_dsr)


def effective_profit_factor(
    profit_factor: float,
    *,
    gross_loss: float = 0.0,
) -> float:
    """Profit factor with zero gross-loss edge case (infinite PF → pass gate)."""
    if gross_loss == 0.0 and profit_factor > 0:
        return float("inf")
    return float(profit_factor)


def evaluate_eligibility(
    *,
    oos_sharpe: float,
    profit_factor: float,
    trade_count: int,
    oos_is_ratio: float,
    after_slippage: bool = False,
    dsr_score: Optional[float] = None,
) -> tuple[bool, List[str]]:
    """
    Expectancy-first eligibility gates.

    PF threshold applies after_slippage discount when flag is True.
    DSR is a conjunctive gate (dsr_passed).
    """
    reasons: List[str] = []
    pf = float(profit_factor)
    if after_slippage:
        pf *= _DEFAULT_SLIPPAGE_PF_DISCOUNT

    if trade_count < _MIN_OOS_TRADES:
        reasons.append(f"oos_trades<{_MIN_OOS_TRADES}")
    if oos_sharpe <= _MIN_OOS_SHARPE:
        reasons.append(f"oos_sharpe<={_MIN_OOS_SHARPE}")
    if oos_is_ratio < _MIN_OOS_IS_RATIO:
        reasons.append(f"oos_is_ratio<{_MIN_OOS_IS_RATIO}")
    if pf < _MIN_PROFIT_FACTOR:
        reasons.append(f"profit_factor<{_MIN_PROFIT_FACTOR}")
    if dsr_score is not None and not dsr_passed(dsr_score):
        reasons.append(f"dsr<{_MIN_DSR}")

    eligible = len(reasons) == 0
    return eligible, reasons


def _coerce_float(val: Any, default: float = 0.0) -> float:
    try:
        return float(val)
    except (TypeError, ValueError):
        return default


def _coerce_int(val: Any, default: int = 0) -> int:
    try:
        return int(val)
    except (TypeError, ValueError):
        return default


def _extract_rows(
    walk_forward_results: Union[Dict[str, Any], List[Dict[str, Any]]],
) -> List[Dict[str, Any]]:
    """Normalize walk-forward optimizer output into flat row dicts."""
    if isinstance(walk_forward_results, list):
        return [r for r in walk_forward_results if isinstance(r, dict)]

    if not isinstance(walk_forward_results, dict):
        return []

    ticker = str(walk_forward_results.get("ticker") or "").upper()
    rows: List[Dict[str, Any]] = []

    # Flat list under "records" or "matrix"
    for key in ("records", "matrix", "rows"):
        nested = walk_forward_results.get(key)
        if isinstance(nested, list):
            for item in nested:
                if isinstance(item, dict):
                    row = dict(item)
                    if ticker and not row.get("ticker"):
                        row["ticker"] = ticker
                    rows.append(row)
            if rows:
                return rows

    # strategy_optimizer.full_analysis shape: walk_forward[strategy] -> metrics
    wf = walk_forward_results.get("walk_forward")
    strategy_results = walk_forward_results.get("strategy_results") or {}

    if isinstance(wf, dict):
        for strategy, metrics in wf.items():
            if not isinstance(metrics, dict):
                continue
            is_metrics = (
                strategy_results.get(strategy)
                if isinstance(strategy_results, dict)
                else {}
            )
            if not isinstance(is_metrics, dict):
                is_metrics = {}

            oos_trades = _coerce_int(
                metrics.get("oos_trades")
                or metrics.get("trade_count")
                or metrics.get("trades")
                or sum(
                    f.get("trades", 0)
                    for f in (metrics.get("fold_detail") or [])
                    if isinstance(f, dict)
                )
            )
            is_sharpe = _coerce_float(
                is_metrics.get("sharpe") or metrics.get("is_sharpe")
            )
            oos_sharpe = _coerce_float(
                metrics.get("oos_sharpe")
                or metrics.get("avg_oos_sharpe")
                or metrics.get("sharpe")
            )
            rows.append(
                {
                    "ticker": ticker,
                    "strategy": str(strategy),
                    "oos_sharpe": oos_sharpe,
                    "is_sharpe": is_sharpe,
                    "profit_factor": _coerce_float(
                        metrics.get("profit_factor") or metrics.get("pf")
                    ),
                    "max_dd": _coerce_float(
                        metrics.get("max_dd") or metrics.get("max_drawdown")
                    ),
                    "trade_count": oos_trades,
                    "after_slippage": bool(metrics.get("after_slippage")),
                }
            )
        return rows

    return rows


def build_fitness_matrix(
    walk_forward_results: Union[Dict[str, Any], List[Dict[str, Any]]],
    *,
    num_trials: int = 1,
    after_slippage: bool = False,
) -> List[StrategyFitnessRecord]:
    """Build fitness records from walk-forward optimizer output."""
    raw_rows = _extract_rows(walk_forward_results)
    records: List[StrategyFitnessRecord] = []

    for row in raw_rows:
        ticker = str(row.get("ticker") or "").upper()
        strategy = str(row.get("strategy") or row.get("strategy_name") or "")
        if not ticker or not strategy:
            continue

        oos_sharpe = _coerce_float(row.get("oos_sharpe"))
        is_sharpe = _coerce_float(row.get("is_sharpe"))
        profit_factor = _coerce_float(row.get("profit_factor") or row.get("pf"))
        max_dd = _coerce_float(row.get("max_dd") or row.get("max_drawdown"))
        trade_count = _coerce_int(row.get("trade_count") or row.get("oos_trades") or row.get("trades"))
        row_slippage = bool(row.get("after_slippage")) or after_slippage

        if is_sharpe > 0:
            oos_is_ratio = oos_sharpe / is_sharpe
        elif oos_sharpe > 0:
            oos_is_ratio = 1.0
        else:
            oos_is_ratio = 0.0

        dsr = compute_deflated_sharpe(
            oos_sharpe,
            num_trials=max(num_trials, 1),
            num_observations=max(trade_count, 2),
            skew=_coerce_float(row.get("skew")),
            kurtosis=_coerce_float(row.get("kurtosis"), 3.0),
        )
        gross_loss = _coerce_float(row.get("gross_loss"))
        adj_pf = effective_profit_factor(profit_factor, gross_loss=gross_loss)
        eligible, reasons = evaluate_eligibility(
            oos_sharpe=oos_sharpe,
            profit_factor=adj_pf if math.isfinite(adj_pf) else profit_factor,
            trade_count=trade_count,
            oos_is_ratio=oos_is_ratio,
            after_slippage=row_slippage,
            dsr_score=dsr,
        )

        records.append(
            StrategyFitnessRecord(
                ticker=ticker,
                strategy=strategy,
                oos_sharpe=round(oos_sharpe, 4),
                profit_factor=round(profit_factor, 4),
                max_dd=round(max_dd, 4),
                trade_count=trade_count,
                oos_is_ratio=round(oos_is_ratio, 4),
                dsr_score=dsr,
                dsr_passed=dsr_passed(dsr),
                eligible=eligible,
                is_sharpe=round(is_sharpe, 4),
                after_slippage=row_slippage,
                ineligible_reasons=reasons,
            )
        )

    records.sort(
        key=lambda r: (r.eligible, r.dsr_score, r.oos_sharpe),
        reverse=True,
    )
    return records


def persist_fitness_matrix(
    records: Sequence[StrategyFitnessRecord],
    *,
    path: Optional[Path] = None,
) -> str:
    """Persist matrix to JSON; returns file path string."""
    target = path or _MATRIX_PATH
    target.parent.mkdir(parents=True, exist_ok=True)
    payload = {
        "generated_at": datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
        "authority": "research_only",
        "may_authorize_deploy": False,
        "record_count": len(records),
        "eligible_count": sum(1 for r in records if r.eligible),
        "records": [r.to_dict() for r in records],
    }
    target.write_text(json.dumps(payload, indent=2), encoding="utf-8")
    return str(target)


def load_fitness_matrix(
    *,
    path: Optional[Path] = None,
) -> Dict[str, Any]:
    """Load persisted matrix; empty shell if missing."""
    target = path or _MATRIX_PATH
    empty = {
        "authority": "research_only",
        "may_authorize_deploy": False,
        "record_count": 0,
        "eligible_count": 0,
        "records": [],
    }
    if not target.is_file():
        return empty
    try:
        data = json.loads(target.read_text(encoding="utf-8"))
        if not isinstance(data, dict):
            return empty
        data.setdefault("authority", "research_only")
        data.setdefault("may_authorize_deploy", False)
        return data
    except (json.JSONDecodeError, OSError) as exc:
        logger.debug("strategy fitness matrix load failed: %s", exc)
        return empty


def build_fitness_matrix_payload(
    walk_forward_results: Optional[Union[Dict[str, Any], List[Dict[str, Any]]]] = None,
    *,
    num_trials: int = 1,
    after_slippage: bool = False,
    persist: bool = False,
) -> Dict[str, Any]:
    """API-friendly payload — loads disk cache when no fresh results supplied."""
    if walk_forward_results is not None:
        records = build_fitness_matrix(
            walk_forward_results,
            num_trials=num_trials,
            after_slippage=after_slippage,
        )
        if persist:
            persist_fitness_matrix(records)
        return {
            "generated_at": datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
            "authority": "research_only",
            "may_authorize_deploy": False,
            "record_count": len(records),
            "eligible_count": sum(1 for r in records if r.eligible),
            "records": [r.to_dict() for r in records],
            "source": "computed",
        }

    cached = load_fitness_matrix()
    cached["source"] = "disk"
    return cached
