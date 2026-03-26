"""
Strategy Leaderboard.

Ranks strategies by out-of-sample performance and manages
lifecycle: active → reduced → cooldown → retired.

The leaderboard is consumed by the OpportunityEnsembler to
weight strategy votes, and by the RegimeRouter to adjust
strategy multipliers based on recent track record.
"""
import logging
from typing import Dict, List, Any, Optional
from datetime import datetime, timedelta
from enum import Enum

logger = logging.getLogger(__name__)


class StrategyStatus(str, Enum):
    ACTIVE = "active"
    REDUCED = "reduced"       # still trading, half size
    COOLDOWN = "cooldown"     # paused, will re-evaluate
    RETIRED = "retired"       # permanently removed


class StrategyLeaderboard:
    """
    Maintains a ranked list of strategies with lifecycle
    management based on rolling out-of-sample metrics.
    """

    # Blended score component weights
    SCORE_WEIGHTS = {
        "oos_sharpe": 0.25,
        "expectancy": 0.20,
        "calmar_ratio": 0.15,
        "win_rate": 0.10,
        "profit_factor": 0.10,
        "max_drawdown_penalty": 0.10,
        "consistency": 0.10,
    }

    # Lifecycle thresholds
    COOLDOWN_SCORE = 0.20     # below this → cooldown
    REDUCED_SCORE = 0.35      # below this → reduced
    RETIRE_AFTER_DAYS = 90    # if cooldown > 90d → retired
    MIN_TRADES_FOR_EVAL = 20  # need this many trades

    def __init__(self):
        self._strategies: Dict[str, Dict[str, Any]] = {}
        self._history: List[Dict[str, Any]] = []

    def update(
        self,
        strategy_name: str,
        metrics: Dict[str, float],
    ) -> Dict[str, Any]:
        """
        Update strategy metrics and recalculate status.

        Args:
            strategy_name: e.g. "momentum_v2"
            metrics: dict with keys matching SCORE_WEIGHTS

        Returns:
            Updated strategy entry with score and status.
        """
        entry = self._strategies.get(strategy_name, {
            "name": strategy_name,
            "status": StrategyStatus.ACTIVE,
            "created_at": datetime.utcnow().isoformat(),
            "cooldown_since": None,
            "trade_count": 0,
        })

        # Update metrics
        entry["metrics"] = metrics
        entry["trade_count"] = metrics.get("trade_count", 0)
        entry["last_updated"] = datetime.utcnow().isoformat()

        # Calculate blended score
        score = self._calculate_score(metrics)
        entry["blended_score"] = round(score, 4)

        # Update lifecycle status
        entry["status"] = self._evaluate_status(entry)

        self._strategies[strategy_name] = entry

        # Record history
        self._history.append({
            "strategy": strategy_name,
            "score": entry["blended_score"],
            "status": entry["status"],
            "timestamp": datetime.utcnow().isoformat(),
        })

        return entry

    def get_rankings(self) -> List[Dict[str, Any]]:
        """
        Return all strategies sorted by blended score descending.
        """
        ranked = sorted(
            self._strategies.values(),
            key=lambda x: x.get("blended_score", 0),
            reverse=True,
        )
        return ranked

    def get_active_strategies(self) -> List[str]:
        """Return names of strategies that can trade."""
        return [
            name for name, entry in self._strategies.items()
            if entry.get("status") in (
                StrategyStatus.ACTIVE,
                StrategyStatus.REDUCED,
            )
        ]

    def get_strategy_scores(self) -> Dict[str, float]:
        """Return name→score map for active strategies."""
        return {
            name: entry.get("blended_score", 0.0)
            for name, entry in self._strategies.items()
            if entry.get("status") != StrategyStatus.RETIRED
        }

    def get_sizing_multiplier(
        self, strategy_name: str,
    ) -> float:
        """
        Returns sizing multiplier based on strategy status.
        ACTIVE=1.0, REDUCED=0.5, COOLDOWN/RETIRED=0.0
        """
        entry = self._strategies.get(strategy_name)
        if not entry:
            return 0.5  # unknown → conservative

        status = entry.get("status", StrategyStatus.ACTIVE)
        if status == StrategyStatus.ACTIVE:
            return 1.0
        elif status == StrategyStatus.REDUCED:
            return 0.5
        else:
            return 0.0

    def _calculate_score(
        self, metrics: Dict[str, float],
    ) -> float:
        """Blended score from strategy metrics."""
        w = self.SCORE_WEIGHTS
        score = 0.0

        # OOS Sharpe (normalised: 2.0 = perfect)
        sharpe = metrics.get("oos_sharpe", 0)
        score += w["oos_sharpe"] * min(sharpe / 2.0, 1.0)

        # Expectancy (normalised: $2 per $1 risked = perfect)
        exp = metrics.get("expectancy", 0)
        score += w["expectancy"] * min(exp / 2.0, 1.0)

        # Calmar ratio (normalised: 3.0 = perfect)
        calmar = metrics.get("calmar_ratio", 0)
        score += w["calmar_ratio"] * min(calmar / 3.0, 1.0)

        # Win rate (directly 0-1)
        wr = metrics.get("win_rate", 0)
        score += w["win_rate"] * min(wr, 1.0)

        # Profit factor (normalised: 3.0 = perfect)
        pf = metrics.get("profit_factor", 0)
        score += w["profit_factor"] * min(pf / 3.0, 1.0)

        # Max drawdown penalty (inverted: 0% = perfect)
        mdd = abs(metrics.get("max_drawdown", 0))
        dd_score = max(0, 1.0 - mdd / 0.20)  # 20% dd = 0
        score += w["max_drawdown_penalty"] * dd_score

        # Consistency (low variance of monthly returns)
        consistency = metrics.get("consistency", 0.5)
        score += w["consistency"] * min(consistency, 1.0)

        return max(score, 0.0)

    def _evaluate_status(
        self, entry: Dict[str, Any],
    ) -> StrategyStatus:
        """Determine lifecycle status based on score."""
        score = entry.get("blended_score", 0)
        trades = entry.get("trade_count", 0)
        current = entry.get("status", StrategyStatus.ACTIVE)

        # Not enough data to judge
        if trades < self.MIN_TRADES_FOR_EVAL:
            return StrategyStatus.ACTIVE

        # Check if should retire (been in cooldown too long)
        if current == StrategyStatus.COOLDOWN:
            cd_since = entry.get("cooldown_since")
            if cd_since:
                try:
                    cd_dt = datetime.fromisoformat(cd_since)
                    days_in_cd = (
                        datetime.utcnow() - cd_dt
                    ).days
                    if days_in_cd > self.RETIRE_AFTER_DAYS:
                        return StrategyStatus.RETIRED
                except (ValueError, TypeError):
                    pass

        # Score-based transitions
        if score < self.COOLDOWN_SCORE:
            if current != StrategyStatus.COOLDOWN:
                entry["cooldown_since"] = (
                    datetime.utcnow().isoformat()
                )
            return StrategyStatus.COOLDOWN
        elif score < self.REDUCED_SCORE:
            entry["cooldown_since"] = None
            return StrategyStatus.REDUCED
        else:
            entry["cooldown_since"] = None
            return StrategyStatus.ACTIVE
