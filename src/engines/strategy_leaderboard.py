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
from datetime import datetime, timedelta, timezone
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
    # Sprint 34: expectancy is primary, win_rate demoted
    SCORE_WEIGHTS = {
        "oos_sharpe": 0.25,
        "expectancy": 0.25,
        "calmar_ratio": 0.15,
        "win_rate": 0.05,
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
        # Read from config with fallback
        try:
            from src.core.config import get_trading_config
            tc = get_trading_config()
            self.COOLDOWN_SCORE = tc.strategy_cooldown_score
            self.REDUCED_SCORE = tc.strategy_reduced_score
            self.RETIRE_AFTER_DAYS = tc.strategy_retire_days
        except Exception:
            pass  # use class-level defaults

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
            "created_at": datetime.now(timezone.utc).isoformat(),
            "cooldown_since": None,
            "trade_count": 0,
        })

        # Update metrics
        entry["metrics"] = metrics
        entry["trade_count"] = metrics.get("trade_count", 0)
        entry["last_updated"] = datetime.now(timezone.utc).isoformat()

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
            "timestamp": datetime.now(timezone.utc).isoformat(),
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

    def get_health_multiplier(
        self, strategy_name: str,
    ) -> float:
        """Sprint 28: composite health multiplier for live sizing.

        Factors:
          - lifecycle status   (active=1.0, reduced=0.5, else=0.0)
          - rolling win rate   (0.6+ → 1.0, 0.4-0.6 → linear, <0.4 → 0.5)
          - blended score      (scaled 0.5-1.0)
          - recent drawdown    (deep DD → reduce)

        Returns 0.0-1.0 multiplier that feeds into position sizing.
        """
        entry = self._strategies.get(strategy_name)
        if not entry:
            return 0.5  # unknown strategy → conservative

        # 1. Lifecycle gate
        status = entry.get("status", StrategyStatus.ACTIVE)
        if status == StrategyStatus.COOLDOWN:
            return 0.0
        if status == StrategyStatus.RETIRED:
            return 0.0
        status_mult = 1.0 if status == StrategyStatus.ACTIVE else 0.5

        # 2. Rolling win rate factor
        metrics = entry.get("metrics", {})
        wr = metrics.get("win_rate", 0.5)
        if wr >= 0.60:
            wr_mult = 1.0
        elif wr >= 0.40:
            wr_mult = 0.5 + (wr - 0.40) / 0.20 * 0.5  # linear 0.5→1.0
        else:
            wr_mult = 0.5

        # 3. Blended score factor (0.5-1.0 range)
        score = entry.get("blended_score", 0.5)
        score_mult = 0.5 + min(score, 1.0) * 0.5

        # 4. Drawdown penalty
        mdd = abs(metrics.get("max_drawdown", 0))
        if mdd > 0.15:
            dd_mult = 0.5
        elif mdd > 0.10:
            dd_mult = 0.75
        else:
            dd_mult = 1.0

        health = status_mult * wr_mult * score_mult * dd_mult
        return round(max(0.0, min(health, 1.0)), 3)

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
                        datetime.now(timezone.utc) - cd_dt
                    ).days
                    if days_in_cd > self.RETIRE_AFTER_DAYS:
                        return StrategyStatus.RETIRED
                except (ValueError, TypeError):
                    pass

        # Score-based transitions
        if score < self.COOLDOWN_SCORE:
            if current != StrategyStatus.COOLDOWN:
                entry["cooldown_since"] = (
                    datetime.now(timezone.utc).isoformat()
                )
            return StrategyStatus.COOLDOWN
        elif score < self.REDUCED_SCORE:
            entry["cooldown_since"] = None
            return StrategyStatus.REDUCED
        else:
            entry["cooldown_since"] = None
            return StrategyStatus.ACTIVE

    def record_outcome(
        self,
        strategy_name: str,
        is_win: bool,
        pnl_pct: float,
        regime: str = "",
        direction: str = "",
        market: str = "",
    ):
        """Record a closed-trade outcome and recompute blended score.

        Sprint 34: called from _record_learning_outcome() at
        position-close time, not from EOD entry records.
        Tracks by regime/direction/market for granular analytics.
        Applies Bayesian shrinkage so a handful of trades do not
        overrule a long track record.
        """
        # Ensure outcome tracking fields exist
        entry = self._strategies.get(strategy_name, {})
        entry.setdefault("trades", 0)
        entry.setdefault("wins", 0)
        entry.setdefault("total_pnl", 0.0)
        entry.setdefault("pnl_history", [])
        entry.setdefault("regime_breakdown", {})
        entry.setdefault("direction_breakdown", {})
        entry.setdefault("market_breakdown", {})

        entry["trades"] += 1
        if is_win:
            entry["wins"] += 1
        entry["total_pnl"] += pnl_pct
        entry["pnl_history"].append(pnl_pct)

        # Track breakdowns
        for bk_key, bk_val in [
            ("regime_breakdown", regime),
            ("direction_breakdown", direction),
            ("market_breakdown", market),
        ]:
            if bk_val:
                sub = entry[bk_key].setdefault(bk_val, {
                    "trades": 0, "wins": 0, "total_pnl": 0.0,
                })
                sub["trades"] += 1
                if is_win:
                    sub["wins"] += 1
                sub["total_pnl"] += pnl_pct

        # Derive rolling metrics from outcome history
        trades = entry["trades"]
        wins = entry["wins"]
        pnl_hist = entry["pnl_history"]

        # Bayesian shrinkage: blend observed win rate with prior
        # prior = 0.50 (uninformative), weight = min(trades, 200)
        prior_wr = 0.50
        shrinkage_n = 200  # full weight at 200 trades
        raw_wr = wins / trades if trades > 0 else 0.5
        shrink_w = min(trades, shrinkage_n) / shrinkage_n
        win_rate = shrink_w * raw_wr + (1 - shrink_w) * prior_wr

        avg_win = (
            sum(p for p in pnl_hist if p > 0) / max(wins, 1)
        )
        avg_loss = abs(
            sum(p for p in pnl_hist if p <= 0) / max(trades - wins, 1)
        )
        profit_factor = avg_win / avg_loss if avg_loss > 0 else 1.0
        expectancy = win_rate * avg_win - (1 - win_rate) * avg_loss

        metrics = {
            "trade_count": trades,
            "win_rate": win_rate,
            "profit_factor": min(profit_factor, 5.0),
            "expectancy": expectancy,
            "oos_sharpe": entry.get("metrics", {}).get("oos_sharpe", 0),
            "calmar_ratio": entry.get("metrics", {}).get("calmar_ratio", 0),
            "max_drawdown": entry.get("metrics", {}).get("max_drawdown", 0),
            "consistency": entry.get("metrics", {}).get("consistency", 0.5),
        }

        # Reuse update() so blended_score + status stay consistent
        self._strategies[strategy_name] = entry
        self.update(strategy_name, metrics)
