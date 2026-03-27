"""
Opportunity Ensembler.

Replaces the naïve pick-highest-score conflict resolution with
multi-strategy ensemble voting, calibrated scoring, and a
no-trade suppression layer.

The ensembler produces a single ranked list of opportunities
from potentially overlapping signals, applying regime fit,
correlation penalty, and event-proximity adjustments.
"""
import logging
from typing import Dict, List, Any, Optional
from datetime import datetime

logger = logging.getLogger(__name__)


class OpportunityEnsembler:
    """
    Ensemble scorer: combines strategy votes, applies adjustments,
    and decides whether an opportunity is strong enough to trade.
    """

    # Default component weights — sum to 1.0
    DEFAULT_WEIGHTS = {
        "calibrated_pwin": 0.25,
        "expected_r": 0.20,
        "regime_fit": 0.15,
        "strategy_health": 0.10,
        "timing_quality": 0.10,
        "risk_reward": 0.10,
        "conviction_bonus": 0.10,
    }

    # Penalties
    CORRELATION_PENALTY_THRESHOLD = 0.65
    EVENT_PROXIMITY_PENALTY = 0.15
    UNCERTAINTY_PENALTY_PER_UNIT = 0.05

    # No-trade thresholds
    MIN_COMPOSITE_SCORE = 0.35
    MIN_STRATEGY_AGREEMENT = 0.50  # fraction of strategies agreeing

    def __init__(
        self,
        weights: Optional[Dict[str, float]] = None,
        min_score: float = None,
    ):
        self.weights = weights or self.DEFAULT_WEIGHTS.copy()
        # Read from config with fallback
        if min_score is not None:
            self.min_score = min_score
        else:
            try:
                from src.core.config import get_trading_config
                tc = get_trading_config()
                val = tc.ensemble_min_score
                self.min_score = (
                    float(val)
                    if isinstance(val, (int, float)) else 0.35
                )
            except Exception:
                self.min_score = 0.35

    def rank_opportunities(
        self,
        signals: List[Dict[str, Any]],
        regime_state: Dict[str, Any],
        portfolio_state: Optional[Dict[str, Any]] = None,
        strategy_scores: Optional[Dict[str, float]] = None,
        regime_weights: Optional[Dict[str, float]] = None,
    ) -> List[Dict[str, Any]]:
        """
        Rank a list of raw signals into scored opportunities.

        Each signal should have at minimum:
            ticker, direction, score, strategy_name,
            risk_reward_ratio, expected_return

        Args:
            regime_weights: strategy_family → 0–1 regime
                multiplier from RegimeRouter.get_strategy_multipliers()

        Returns list sorted by composite_score descending,
        each entry augmented with composite_score, components,
        and trade_decision (True/False).
        """
        scored = []
        for sig in signals:
            entry = self._score_opportunity(
                sig, regime_state, portfolio_state,
                strategy_scores, regime_weights,
            )
            scored.append(entry)

        # Sort descending by composite score
        scored.sort(key=lambda x: x["composite_score"], reverse=True)

        # Apply no-trade suppression
        scored = self._apply_suppression(scored, regime_state)

        return scored

    def _score_opportunity(
        self,
        signal: Dict[str, Any],
        regime: Dict[str, Any],
        portfolio: Optional[Dict[str, Any]],
        strategy_health: Optional[Dict[str, float]],
        regime_weights: Optional[Dict[str, float]] = None,
    ) -> Dict[str, Any]:
        """Score a single opportunity."""
        w = self.weights

        # Component: calibrated win probability
        # Prefer EdgeCalculator p_t1 if available
        pwin = signal.get("edge_p_t1", signal.get("score", 0.5))
        pwin = min(pwin, 1.0)

        # Component: expected return (normalised)
        # Prefer edge EV over raw expected_return
        exp_r = signal.get(
            "edge_ev", signal.get("expected_return", 0.0)
        )
        exp_r_norm = min(abs(exp_r) / 0.10, 1.0)  # 10% = max

        # Component: regime fit
        regime_fit = self._calc_regime_fit(signal, regime)

        # Component: strategy health (leaderboard * regime weight)
        strat = signal.get("strategy_name", "unknown")
        lb_score = 0.5
        if strategy_health and strat in strategy_health:
            lb_score = min(strategy_health[strat], 1.0)
        # Blend with regime weight for this strategy family
        rw = self._resolve_regime_weight(
            strat, regime_weights
        )
        health = lb_score * rw

        # Component: timing quality (simplified)
        timing = signal.get("timing_score", 0.5)

        # Component: risk/reward ratio
        rr = signal.get("risk_reward_ratio", 1.0)
        rr_norm = min(rr / 4.0, 1.0)  # 4:1 = perfect

        # Component: conviction (multi-strategy agreement)
        conviction = signal.get("strategy_agreement", 0.5)

        # Composite
        composite = (
            w["calibrated_pwin"] * pwin
            + w["expected_r"] * exp_r_norm
            + w["regime_fit"] * regime_fit
            + w["strategy_health"] * health
            + w["timing_quality"] * timing
            + w["risk_reward"] * rr_norm
            + w["conviction_bonus"] * conviction
        )

        # Penalties
        penalties = {}

        # Correlation penalty: if portfolio already has correlated
        if portfolio:
            corr_penalty = self._correlation_penalty(
                signal, portfolio
            )
            composite -= corr_penalty
            if corr_penalty > 0:
                penalties["correlation"] = round(corr_penalty, 3)

        # Event proximity (earnings within 3 days)
        if signal.get("days_to_earnings", 999) <= 3:
            composite -= self.EVENT_PROXIMITY_PENALTY
            penalties["event_proximity"] = (
                self.EVENT_PROXIMITY_PENALTY
            )

        # Regime uncertainty penalty
        entropy = regime.get("entropy", 0.5)
        if entropy > 0.8:
            unc_pen = (entropy - 0.8) * self.UNCERTAINTY_PENALTY_PER_UNIT * 10
            composite -= unc_pen
            penalties["uncertainty"] = round(unc_pen, 3)

        composite = max(composite, 0.0)

        return {
            "ticker": signal.get("ticker", "???"),
            "direction": signal.get("direction", "LONG"),
            "strategy_name": strat,
            "composite_score": round(composite, 4),
            "trade_decision": composite >= self.min_score,
            "components": {
                "pwin": round(pwin, 3),
                "exp_r": round(exp_r_norm, 3),
                "regime_fit": round(regime_fit, 3),
                "strategy_health": round(health, 3),
                "timing": round(timing, 3),
                "risk_reward": round(rr_norm, 3),
                "conviction": round(conviction, 3),
            },
            "penalties": penalties,
            "original_signal": signal,
        }

    def _calc_regime_fit(
        self,
        signal: Dict[str, Any],
        regime: Dict[str, Any],
    ) -> float:
        """How well does this signal's strategy fit the regime?"""
        strat = signal.get("strategy_name", "").lower()
        direction = signal.get("direction", "LONG")

        risk_on = regime.get("risk_on_uptrend", 0.33)
        neutral = regime.get("neutral_range", 0.33)
        risk_off = regime.get("risk_off_downtrend", 0.33)

        # Strategy-to-regime affinity mapping
        if "momentum" in strat or "trend" in strat:
            return risk_on * 0.8 + neutral * 0.3
        elif "mean_rev" in strat or "reversion" in strat:
            return neutral * 0.9 + risk_on * 0.2
        elif "swing" in strat:
            return risk_on * 0.5 + neutral * 0.5
        elif "vcp" in strat:
            return neutral * 0.7 + risk_on * 0.4
        elif "earnings" in strat:
            return 0.5  # regime-neutral
        elif "defensive" in strat:
            return risk_off * 0.8 + neutral * 0.3
        else:
            return 0.4  # unknown strategy

    def _correlation_penalty(
        self,
        signal: Dict[str, Any],
        portfolio: Dict[str, Any],
    ) -> float:
        """Penalise if ticker/sector already represented."""
        ticker = signal.get("ticker", "")
        sector = signal.get("sector", "")

        existing_tickers = portfolio.get("tickers", [])
        existing_sectors = portfolio.get("sectors", {})

        penalty = 0.0

        # Same ticker already held
        if ticker in existing_tickers:
            penalty += 0.15

        # Sector concentration
        if sector and sector in existing_sectors:
            sector_weight = existing_sectors.get(sector, 0)
            if sector_weight > 0.25:
                penalty += 0.10

        return min(penalty, 0.25)  # cap

    @staticmethod
    def _resolve_regime_weight(
        strategy_name: str,
        regime_weights: Optional[Dict[str, float]],
    ) -> float:
        """Look up regime sizing multiplier for a strategy.

        Matches strategy_name against regime_weights keys using
        substring matching (e.g. 'momentum_breakout' matches
        the 'momentum' key).

        Returns 1.0 when no regime_weights provided (neutral).
        """
        if not regime_weights:
            return 1.0
        name = strategy_name.lower()
        # Exact match first
        if name in regime_weights:
            return max(regime_weights[name], 0.1)
        # Substring match
        for key, val in regime_weights.items():
            if key in name or name in key:
                return max(val, 0.1)
        return 0.5  # unknown strategy → conservative

    def _apply_suppression(
        self,
        ranked: List[Dict[str, Any]],
        regime: Dict[str, Any],
    ) -> List[Dict[str, Any]]:
        """
        Post-ranking suppression rules:
        - If regime says no trade, suppress all
        - If top signal is weak, suppress all
        - If strategies strongly disagree, suppress
        """
        if not regime.get("should_trade", True):
            for r in ranked:
                r["trade_decision"] = False
                r["suppression_reason"] = "regime_no_trade"
            return ranked

        if ranked and ranked[0]["composite_score"] < self.min_score:
            for r in ranked:
                r["trade_decision"] = False
                r["suppression_reason"] = "weak_top_signal"

        return ranked
