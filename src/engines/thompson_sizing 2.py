"""
Thompson Sampling RL Sizing Engine — Sprint 103
=================================================
Adaptive position-sizing via Thompson sampling.

For each (strategy, regime) arm, maintain a Beta(alpha, beta) distribution.
  • After a WIN:  alpha += reward_weight
  • After a LOSS: beta  += 1

Sample from the Beta to get a "confidence multiplier" [0, 1].
Final size = base_kelly_pct × multiplier × account_equity.

This replaces static fractional-Kelly with an arm that learns over time
which strategy/regime combinations deserve larger allocation.

Persistence: models/thompson_arms.json
"""

from __future__ import annotations

import json
import logging
import random
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

logger = logging.getLogger(__name__)

_THOMPSON_FILE = Path("models/thompson_arms.json")
_DEFAULT_ALPHA = 1.0  # uninformative prior (uniform Beta(1,1))
_DEFAULT_BETA = 1.0
_REWARD_WEIGHT = 1.5  # winning trades get 1.5× alpha update (risk-adjusted)
_MIN_MULTIPLIER = 0.25  # floor: never go below 25% of base Kelly
_MAX_MULTIPLIER = 2.0  # ceiling: never go above 2× base Kelly


@dataclass
class ThompsonArm:
    """Beta distribution arm for one (strategy, regime) combination."""

    key: str  # "{strategy}:{regime}"
    alpha: float = _DEFAULT_ALPHA
    beta: float = _DEFAULT_BETA
    n_wins: int = 0
    n_losses: int = 0

    @property
    def n_total(self) -> int:
        return self.n_wins + self.n_losses

    @property
    def win_rate(self) -> float:
        return self.n_wins / self.n_total if self.n_total > 0 else 0.5

    @property
    def mean(self) -> float:
        """Expected value of the Beta distribution."""
        return self.alpha / (self.alpha + self.beta)

    def sample(self) -> float:
        """
        Draw one sample from Beta(alpha, beta) using Gamma variates.
        Returns a sizing multiplier clamped to [MIN_MULTIPLIER, MAX_MULTIPLIER].
        """
        # Python's random.betavariate uses alpha, beta directly
        raw = random.betavariate(self.alpha, self.beta)
        return max(_MIN_MULTIPLIER, min(_MAX_MULTIPLIER, raw * _MAX_MULTIPLIER))

    def update(self, win: bool, reward_weight: float = _REWARD_WEIGHT) -> None:
        """Update Beta parameters from one outcome."""
        if win:
            self.alpha += reward_weight
            self.n_wins += 1
        else:
            self.beta += 1.0
            self.n_losses += 1

    def to_dict(self) -> Dict[str, Any]:
        return {
            "key": self.key,
            "alpha": round(self.alpha, 4),
            "beta": round(self.beta, 4),
            "n_wins": self.n_wins,
            "n_losses": self.n_losses,
            "n_total": self.n_total,
            "win_rate": round(self.win_rate, 4),
            "mean_multiplier": round(self.mean * _MAX_MULTIPLIER, 4),
        }


class ThompsonSizingEngine:
    """
    Manages a collection of Thompson arms indexed by (strategy, regime).

    Usage:
        engine = ThompsonSizingEngine()
        multiplier = engine.sample("PULLBACK_TREND", "BULL")
        final_size_usd = base_kelly_usd * multiplier

        # After trade closes:
        engine.update("PULLBACK_TREND", "BULL", win=True)
        engine.save()
    """

    def __init__(self) -> None:
        self._arms: Dict[str, ThompsonArm] = {}
        self._load()

    # ── Public API ─────────────────────────────────────────────────────────

    def sample(self, strategy: str, regime: str) -> float:
        """Sample a sizing multiplier from the arm for (strategy, regime)."""
        arm = self._get_or_create(strategy, regime)
        mult = arm.sample()
        logger.debug(
            "[Thompson] arm=%s sample=%.3f (α=%.2f β=%.2f)",
            arm.key,
            mult,
            arm.alpha,
            arm.beta,
        )
        return mult

    def update(
        self,
        strategy: str,
        regime: str,
        win: bool,
        reward_weight: float = _REWARD_WEIGHT,
    ) -> ThompsonArm:
        """Update the arm after a trade closes."""
        arm = self._get_or_create(strategy, regime)
        arm.update(win, reward_weight)
        self.save()
        logger.info(
            "[Thompson] arm=%s updated win=%s → α=%.2f β=%.2f mean=%.3f",
            arm.key,
            win,
            arm.alpha,
            arm.beta,
            arm.mean,
        )
        return arm

    def get_arm(self, strategy: str, regime: str) -> Optional[ThompsonArm]:
        key = _arm_key(strategy, regime)
        return self._arms.get(key)

    def get_all_arms(self) -> List[Dict[str, Any]]:
        return [
            a.to_dict()
            for a in sorted(self._arms.values(), key=lambda a: a.n_total, reverse=True)
        ]

    def recommend_best_arm(self) -> Optional[Dict[str, Any]]:
        """Return the arm with the highest current mean (exploitation view)."""
        if not self._arms:
            return None
        best = max(self._arms.values(), key=lambda a: a.mean)
        return best.to_dict()

    def reset_arm(self, strategy: str, regime: str) -> None:
        """Reset arm to uninformative prior (use when strategy changes fundamentally)."""
        key = _arm_key(strategy, regime)
        self._arms[key] = ThompsonArm(key=key)
        self.save()

    # ── Persistence ────────────────────────────────────────────────────────

    def save(self) -> None:
        try:
            _THOMPSON_FILE.parent.mkdir(exist_ok=True)
            data = {k: v.to_dict() for k, v in self._arms.items()}
            with open(_THOMPSON_FILE, "w") as f:
                json.dump(data, f, indent=2)
        except Exception as e:
            logger.debug("[Thompson] save error: %s", e)

    def _load(self) -> None:
        if not _THOMPSON_FILE.exists():
            return
        try:
            with open(_THOMPSON_FILE) as f:
                raw = json.load(f)
            for key, d in raw.items():
                arm = ThompsonArm(
                    key=key,
                    alpha=d.get("alpha", _DEFAULT_ALPHA),
                    beta=d.get("beta", _DEFAULT_BETA),
                    n_wins=d.get("n_wins", 0),
                    n_losses=d.get("n_losses", 0),
                )
                self._arms[key] = arm
            logger.debug(
                "[Thompson] loaded %d arms from %s", len(self._arms), _THOMPSON_FILE
            )
        except Exception as e:
            logger.debug("[Thompson] load error: %s", e)

    def _get_or_create(self, strategy: str, regime: str) -> ThompsonArm:
        key = _arm_key(strategy, regime)
        if key not in self._arms:
            self._arms[key] = ThompsonArm(key=key)
            logger.debug("[Thompson] new arm created: %s", key)
        return self._arms[key]


def _arm_key(strategy: str, regime: str) -> str:
    return f"{strategy.upper().strip()}:{regime.upper().strip()}"


# ── Singleton ──────────────────────────────────────────────────────────────

_engine: Optional[ThompsonSizingEngine] = None


def get_thompson_engine() -> ThompsonSizingEngine:
    global _engine
    if _engine is None:
        _engine = ThompsonSizingEngine()
    return _engine
