"""
Probabilistic Regime Router.

Replaces hard-threshold regime detection with a soft probabilistic
assessment that outputs regime probabilities, entropy, and a
should_trade flag.

The deterministic RegimeDetector in signal_engine.py is kept as
fallback; this module sits above it and provides richer context
for the OpportunityEnsembler and ExpressionEngine.
"""
import logging
import math
from typing import Dict, Optional, Any
from datetime import datetime, timezone

import numpy as np

logger = logging.getLogger(__name__)


class RegimeRouter:
    """
    Probabilistic regime classifier.

    Inputs: VIX, VIX term slope, breadth, HY spread, realized vol,
            cross-sectional correlation, dispersion, market drawdown.

    Outputs: RegimeState with probabilities for each regime bucket,
             entropy (uncertainty), and a should_trade flag.
    """

    # Thresholds for soft classification
    VIX_LOW = 14.0
    VIX_MID = 20.0
    VIX_HIGH = 28.0
    VIX_CRISIS = 35.0

    BREADTH_BULL = 0.65
    BREADTH_BEAR = 0.35

    def __init__(self, no_trade_entropy: float = None,
                 min_confidence: float = None):
        """
        Args:
            no_trade_entropy: if entropy exceeds this, should_trade = False
            min_confidence: if max regime prob < this, reduce sizing
        """
        # Read from config with fallback defaults
        try:
            from src.core.config import get_trading_config
            tc = get_trading_config()
            _nte = tc.regime_no_trade_entropy
            _mc = tc.regime_min_confidence
            _vc = tc.regime_vix_crisis
            self.no_trade_entropy = (
                no_trade_entropy
                or (float(_nte) if isinstance(
                    _nte, (int, float)
                ) else 1.35)
            )
            self.min_confidence = (
                min_confidence
                or (float(_mc) if isinstance(
                    _mc, (int, float)
                ) else 0.40)
            )
            self.VIX_CRISIS = (
                float(_vc) if isinstance(
                    _vc, (int, float)
                ) else 35.0
            )
        except Exception:
            self.no_trade_entropy = no_trade_entropy or 1.35
            self.min_confidence = min_confidence or 0.40

    def classify(self, market_data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Produce a probabilistic regime assessment.

        Args:
            market_data: dict with keys like vix, spy_return_20d,
                         breadth_pct, hy_spread, realized_vol_20d, etc.

        Returns:
            RegimeState-compatible dict with probabilities and flags.
        """
        vix = market_data.get("vix", 18.0)
        spy_ret = market_data.get("spy_return_20d", 0.0)
        breadth = market_data.get("breadth_pct", 0.50)
        hy_spread = market_data.get("hy_spread", 0.0)
        realized_vol = market_data.get("realized_vol_20d", 0.15)
        vix_term_slope = market_data.get("vix_term_slope", 0.0)

        # ── Compute soft scores for each regime bucket ────────────
        # Risk-on uptrend signals
        risk_on_score = 0.0
        risk_on_score += self._sigmoid(self.VIX_MID - vix, k=0.3)  # low VIX → bullish
        risk_on_score += self._sigmoid(spy_ret * 100, k=0.5)  # positive return
        risk_on_score += self._sigmoid((breadth - 0.5) * 5, k=0.8)  # breadth > 50%
        risk_on_score += self._sigmoid(-vix_term_slope, k=0.3)  # contango (negative slope = calm)

        # Neutral range signals
        neutral_score = 0.0
        neutral_score += 1.0 - abs(self._sigmoid(vix - self.VIX_MID, k=0.2) - 0.5) * 2
        neutral_score += 1.0 - abs(spy_ret * 20)  # flat return
        neutral_score += 1.0 - abs(breadth - 0.5) * 4

        # Risk-off downtrend signals
        risk_off_score = 0.0
        risk_off_score += self._sigmoid(vix - self.VIX_MID, k=0.3)  # high VIX
        risk_off_score += self._sigmoid(-spy_ret * 100, k=0.5)  # negative return
        risk_off_score += self._sigmoid((0.5 - breadth) * 5, k=0.8)  # breadth < 50%
        risk_off_score += self._sigmoid(hy_spread - 1.0, k=0.5)  # wide HY spread

        # Normalise to probabilities via softmax
        scores = np.array([
            max(risk_on_score, 0.01),
            max(neutral_score, 0.01),
            max(risk_off_score, 0.01),
        ])
        probs = self._softmax(scores, temperature=1.5)

        risk_on_prob = float(probs[0])
        neutral_prob = float(probs[1])
        risk_off_prob = float(probs[2])

        # Entropy: 0 = certain, ln(3)≈1.10 = max uncertainty
        entropy = float(-sum(
            p * math.log(p + 1e-10) for p in [risk_on_prob, neutral_prob, risk_off_prob]
        ))

        max_prob = max(risk_on_prob, neutral_prob, risk_off_prob)

        # Should-trade logic
        should_trade = True
        if vix >= self.VIX_CRISIS:
            should_trade = False  # Crisis override
        elif entropy > self.no_trade_entropy:
            should_trade = False  # Too uncertain
        elif max_prob < self.min_confidence:
            should_trade = False  # No clear regime

        # ── Derived labels ─────────────────────────────────────
        # Downstream contract: regime, risk_regime, trend_regime,
        # volatility_regime, no_trade_reason.
        _probs = {
            "RISK_ON": risk_on_prob,
            "NEUTRAL": neutral_prob,
            "RISK_OFF": risk_off_prob,
        }
        regime = max(_probs, key=_probs.get)

        # risk_regime: simplified risk-appetite label
        if risk_on_prob >= 0.50:
            risk_regime = "risk_on"
        elif risk_off_prob >= 0.50:
            risk_regime = "risk_off"
        else:
            risk_regime = "neutral"

        # trend_regime: SPY return + breadth
        if spy_ret > 0.02 and breadth > self.BREADTH_BULL:
            trend_regime = "uptrend"
        elif spy_ret < -0.02 and breadth < self.BREADTH_BEAR:
            trend_regime = "downtrend"
        else:
            trend_regime = "sideways"

        # volatility_regime: VIX-driven
        if vix < self.VIX_LOW:
            volatility_regime = "low_vol"
        elif vix < self.VIX_MID:
            volatility_regime = "normal_vol"
        elif vix < self.VIX_HIGH:
            volatility_regime = "elevated_vol"
        elif vix < self.VIX_CRISIS:
            volatility_regime = "high_vol"
        else:
            volatility_regime = "crisis_vol"

        # no_trade_reason: human-readable explanation
        no_trade_reason = ""
        if not should_trade:
            if vix >= self.VIX_CRISIS:
                no_trade_reason = (
                    f"VIX at {vix:.1f} exceeds crisis "
                    f"threshold ({self.VIX_CRISIS})"
                )
            elif entropy > self.no_trade_entropy:
                no_trade_reason = (
                    f"Regime uncertainty too high "
                    f"(entropy {entropy:.2f} > "
                    f"{self.no_trade_entropy})"
                )
            elif max_prob < self.min_confidence:
                no_trade_reason = (
                    f"No regime has sufficient confidence "
                    f"(best {max_prob:.1%} < "
                    f"{self.min_confidence:.0%})"
                )

        return {
            # Derived labels (downstream contract)
            "regime": regime,
            "risk_regime": risk_regime,
            "trend_regime": trend_regime,
            "volatility_regime": volatility_regime,
            "no_trade_reason": no_trade_reason,
            # Probabilities
            "risk_on_uptrend": round(risk_on_prob, 3),
            "neutral_range": round(neutral_prob, 3),
            "risk_off_downtrend": round(risk_off_prob, 3),
            "entropy": round(entropy, 3),
            "should_trade": should_trade,
            "confidence": round(max_prob, 3),
            # Raw inputs (for transparency)
            "vix": vix,
            "vix_term_slope": vix_term_slope,
            "breadth_pct": breadth,
            "credit_spread_z": hy_spread,
            "realized_vol_20d": realized_vol,
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }

    @staticmethod
    def _sigmoid(x: float, k: float = 1.0) -> float:
        """Smooth activation function."""
        return 1.0 / (1.0 + math.exp(-k * x))

    @staticmethod
    def _softmax(x: np.ndarray, temperature: float = 1.0) -> np.ndarray:
        """Softmax with temperature scaling."""
        x_scaled = x / max(temperature, 0.01)
        e_x = np.exp(x_scaled - np.max(x_scaled))
        return e_x / e_x.sum()

    def get_strategy_multipliers(
        self, regime_state: Dict[str, Any]
    ) -> Dict[str, float]:
        """
        Convert regime state into strategy-family multipliers.

        Returns dict mapping strategy family → sizing multiplier (0-1).
        """
        risk_on = regime_state.get("risk_on_uptrend", 0.33)
        neutral = regime_state.get("neutral_range", 0.33)
        risk_off = regime_state.get("risk_off_downtrend", 0.33)

        return {
            "momentum": min(1.0, risk_on * 1.5),
            "trend_following": min(1.0, risk_on * 1.3),
            "breakout": min(1.0, (risk_on + neutral * 0.5) * 1.2),
            "mean_reversion": min(1.0, neutral * 1.8),
            "swing": min(1.0, (risk_on * 0.8 + neutral * 0.5)),
            "vcp": min(1.0, neutral * 1.5),
            "earnings": 0.5,  # always moderate
            "defensive": min(1.0, risk_off * 1.5),
        }
