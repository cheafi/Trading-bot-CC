"""
Meta-Ensemble Weight Optimizer (Sprint 38).

Replaces the fixed ``DEFAULT_WEIGHTS`` in OpportunityEnsembler
with ML-learned weights that adapt to recent trade outcomes.

Pipeline:
  1. Collect (component_vector, outcome_pnl) pairs from closed trades.
  2. Train a lightweight model (ridge regression on component→PnL).
  3. Extract coefficient importances → normalise to new weights.
  4. OpportunityEnsembler.set_weights(learned_weights) hot-swaps.

The fallback is always the hand-tuned DEFAULT_WEIGHTS so the
system degrades gracefully if < MIN_SAMPLES trades are recorded.
"""
from __future__ import annotations

import logging
import math
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Tuple

logger = logging.getLogger(__name__)

# Component names must match OpportunityEnsembler._compute_score keys
COMPONENT_NAMES = [
    "net_expectancy",
    "calibrated_pwin",
    "expected_r",
    "regime_fit",
    "strategy_health",
    "timing_quality",
    "risk_reward",
    "conviction_bonus",
]

MIN_SAMPLES = 30        # don't learn until we have 30+ trades
RETRAIN_INTERVAL = 10   # re-learn every N new trades
RIDGE_ALPHA = 1.0       # L2 regularisation
MIN_WEIGHT = 0.02       # floor so no component gets zeroed


@dataclass
class TrainingSample:
    """One (component_vector, outcome) pair."""
    components: Dict[str, float]
    pnl_pct: float
    r_multiple: float = 0.0
    regime_label: str = ""
    strategy_id: str = ""


@dataclass
class MetaEnsembleState:
    """Serialisable snapshot of the learned model."""
    weights: Dict[str, float] = field(default_factory=dict)
    n_samples: int = 0
    r_squared: float = 0.0
    last_retrained_at: str = ""
    coefficient_importances: Dict[str, float] = field(
        default_factory=dict,
    )

    def to_dict(self) -> Dict[str, Any]:
        return {
            "weights": self.weights,
            "n_samples": self.n_samples,
            "r_squared": round(self.r_squared, 4),
            "last_retrained_at": self.last_retrained_at,
            "coefficient_importances": {
                k: round(v, 4)
                for k, v in self.coefficient_importances.items()
            },
        }


class MetaEnsemble:
    """
    Adaptive weight optimizer for OpportunityEnsembler.

    Usage::

        meta = MetaEnsemble()
        # After each closed trade:
        meta.record_outcome(rec.components, pnl_pct=3.5)
        # Periodically:
        new_weights = meta.get_learned_weights()
        if new_weights:
            ensembler.set_weights(new_weights)
    """

    def __init__(
        self,
        min_samples: int = MIN_SAMPLES,
        retrain_interval: int = RETRAIN_INTERVAL,
        ridge_alpha: float = RIDGE_ALPHA,
    ):
        self._samples: List[TrainingSample] = []
        self._min_samples = min_samples
        self._retrain_interval = retrain_interval
        self._ridge_alpha = ridge_alpha
        self._state = MetaEnsembleState()
        self._trades_since_retrain = 0

    # ── Recording ─────────────────────────────────────────────

    def record_outcome(
        self,
        components: Dict[str, float],
        pnl_pct: float,
        r_multiple: float = 0.0,
        regime_label: str = "",
        strategy_id: str = "",
    ):
        """Record a closed-trade outcome with its component scores."""
        self._samples.append(TrainingSample(
            components=components,
            pnl_pct=pnl_pct,
            r_multiple=r_multiple,
            regime_label=regime_label,
            strategy_id=strategy_id,
        ))
        self._trades_since_retrain += 1

        if (
            len(self._samples) >= self._min_samples
            and self._trades_since_retrain >= self._retrain_interval
        ):
            self._train()

    # ── Training ──────────────────────────────────────────────

    def _train(self):
        """Train ridge regression: components → PnL."""
        from datetime import datetime, timezone
        n = len(self._samples)
        if n < self._min_samples:
            return

        # Build feature matrix X and target y
        X: List[List[float]] = []
        y: List[float] = []
        for s in self._samples:
            row = [
                s.components.get(name, 0.0)
                for name in COMPONENT_NAMES
            ]
            X.append(row)
            y.append(s.pnl_pct)

        # Ridge regression: w = (X^T X + αI)^-1 X^T y
        # Pure Python — no numpy dependency required
        k = len(COMPONENT_NAMES)
        coefficients = self._ridge_solve(X, y, k)

        if coefficients is None:
            logger.warning("Meta-ensemble: ridge solve failed")
            return

        # R² computation
        y_mean = sum(y) / len(y)
        ss_tot = sum((yi - y_mean) ** 2 for yi in y)
        y_pred = [
            sum(X[i][j] * coefficients[j] for j in range(k))
            for i in range(len(X))
        ]
        ss_res = sum(
            (y[i] - y_pred[i]) ** 2 for i in range(len(y))
        )
        r_sq = 1 - ss_res / ss_tot if ss_tot > 0 else 0

        # Convert coefficients to weights (absolute value, normalised)
        abs_coefs = [abs(c) for c in coefficients]
        total = sum(abs_coefs) or 1.0
        raw_weights = {
            COMPONENT_NAMES[i]: max(
                MIN_WEIGHT, abs_coefs[i] / total
            )
            for i in range(k)
        }
        # Re-normalise after flooring
        w_total = sum(raw_weights.values())
        weights = {
            name: round(w / w_total, 4)
            for name, w in raw_weights.items()
        }

        self._state = MetaEnsembleState(
            weights=weights,
            n_samples=n,
            r_squared=r_sq,
            last_retrained_at=datetime.now(
                timezone.utc
            ).isoformat(),
            coefficient_importances={
                COMPONENT_NAMES[i]: coefficients[i]
                for i in range(k)
            },
        )
        self._trades_since_retrain = 0
        logger.info(
            "Meta-ensemble retrained: n=%d, R²=%.3f, weights=%s",
            n, r_sq, weights,
        )

    def _ridge_solve(
        self,
        X: List[List[float]],
        y: List[float],
        k: int,
    ) -> Optional[List[float]]:
        """Pure-Python ridge regression solver.

        Solves (X^T X + αI) w = X^T y via Cholesky-like LU.
        """
        n = len(X)
        alpha = self._ridge_alpha

        # X^T X  (k×k)
        XtX = [[0.0] * k for _ in range(k)]
        for i in range(k):
            for j in range(k):
                s = 0.0
                for row in range(n):
                    s += X[row][i] * X[row][j]
                XtX[i][j] = s
            XtX[i][i] += alpha  # regularisation

        # X^T y  (k×1)
        Xty = [0.0] * k
        for i in range(k):
            s = 0.0
            for row in range(n):
                s += X[row][i] * y[row]
            Xty[i] = s

        # Gaussian elimination with partial pivoting
        A = [row[:] + [Xty[i]] for i, row in enumerate(XtX)]
        for col in range(k):
            # Pivot
            max_row = col
            for row in range(col + 1, k):
                if abs(A[row][col]) > abs(A[max_row][col]):
                    max_row = row
            A[col], A[max_row] = A[max_row], A[col]

            if abs(A[col][col]) < 1e-12:
                return None

            for row in range(col + 1, k):
                factor = A[row][col] / A[col][col]
                for j in range(col, k + 1):
                    A[row][j] -= factor * A[col][j]

        # Back substitution
        w = [0.0] * k
        for i in range(k - 1, -1, -1):
            s = A[i][k]
            for j in range(i + 1, k):
                s -= A[i][j] * w[j]
            w[i] = s / A[i][i]

        return w

    # ── Access ────────────────────────────────────────────────

    def get_learned_weights(self) -> Optional[Dict[str, float]]:
        """Return learned weights, or None if not enough data."""
        if self._state.n_samples >= self._min_samples:
            return dict(self._state.weights)
        return None

    def get_state(self) -> MetaEnsembleState:
        """Return full model state for API / dashboard."""
        return self._state

    @property
    def is_trained(self) -> bool:
        return self._state.n_samples >= self._min_samples

    @property
    def sample_count(self) -> int:
        return len(self._samples)
