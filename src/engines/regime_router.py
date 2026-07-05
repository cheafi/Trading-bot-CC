"""
Probabilistic Regime Router.

Replaces hard-threshold regime detection with a soft probabilistic
assessment that outputs regime probabilities, entropy, and a
should_trade flag.

Sprint 34: canonical RegimeState dataclass — one object used by
AutoTradingEngine, SignalEngine, OpportunityEnsembler,
ExpressionEngine, API, bots, and dashboard.

P3: Added EMA smoothing + minimum hold time to prevent regime whipsaw.
"""

import logging
import math
import time as _time
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from typing import Any, Dict, Optional

import numpy as np

logger = logging.getLogger(__name__)


# ─── Canonical RegimeState ────────────────────────────────────
@dataclass
class RegimeState:
    """Single source of truth for market regime across all layers.

    Every component (strategy routing, sizing, explanation,
    dashboard, API, bots) consumes this same object.
    """
    # Derived labels
    regime: str = "NEUTRAL"             # RISK_ON / NEUTRAL / RISK_OFF
    risk_regime: str = "neutral"        # risk_on / neutral / risk_off
    trend_regime: str = "sideways"      # uptrend / downtrend / sideways
    volatility_regime: str = "normal_vol"  # low_vol / normal_vol / elevated_vol / high_vol / crisis_vol
    no_trade_reason: str = ""

    # Probabilities
    risk_on_uptrend: float = 0.333
    neutral_range: float = 0.334
    risk_off_downtrend: float = 0.333
    entropy: float = 1.0
    should_trade: bool = True
    confidence: float = 0.334

    # Sizing scalar (Sprint 34: graduated, not binary)
    size_scalar: float = 1.0

    # Raw inputs
    vix: float = 18.0
    vix_term_slope: float = 0.0
    breadth_pct: float = 0.50
    credit_spread_z: float = 0.0
    realized_vol_20d: float = 0.15
    timestamp: str = ""

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dict for backward compatibility."""
        return asdict(self)

    def get(self, key: str, default=None):
        """Dict-like access for backward compatibility."""
        return getattr(self, key, default)

    def __getitem__(self, key: str):
        """Support state['key'] access for backward compat."""
        if hasattr(self, key):
            return getattr(self, key)
        raise KeyError(key)

    def __contains__(self, key: str) -> bool:
        """Support 'key' in state."""
        return hasattr(self, key)


class RegimeRouter:
    """
    Probabilistic regime classifier.

    Inputs: VIX, VIX term slope, breadth, HY spread, realized vol,
            cross-sectional correlation, dispersion, market drawdown.

    Outputs: RegimeState with probabilities for each regime bucket,
             entropy (uncertainty), and a should_trade flag.
    """

    # Thresholds loaded from risk_limits (env-var overrideable); hardcoded fallback for safety
    try:
        from src.core.risk_limits import VIX as _VIX  # noqa: PLC0415

        VIX_LOW: float = _VIX.low
        VIX_MID: float = _VIX.mid
        VIX_HIGH: float = _VIX.high
        VIX_CRISIS: float = _VIX.crisis
    except Exception:
        VIX_LOW = 14.0
        VIX_MID = 20.0
        VIX_HIGH = 28.0
        VIX_CRISIS = 35.0

    BREADTH_BULL = 0.65
    BREADTH_BEAR = 0.35

    def __init__(
        self,
        no_trade_entropy: float = None,
        min_confidence: float = None,
        ema_alpha: float = 0.3,
        min_hold_seconds: int = 300,
    ):
        """
        Args:
            no_trade_entropy: if entropy exceeds this, should_trade = False
            min_confidence: if max regime prob < this, reduce sizing
            ema_alpha: smoothing factor for probability EMA (0=no update, 1=no smoothing)
            min_hold_seconds: minimum seconds before regime can flip (default 5 min)
        """
        # ── Hysteresis state (P3) ──
        self._ema_probs: Optional[np.ndarray] = None  # [risk_on, neutral, risk_off]
        self._ema_alpha = ema_alpha
        self._min_hold_seconds = min_hold_seconds
        self._last_regime: Optional[str] = None
        self._regime_since: float = 0.0  # timestamp of last regime change

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
        hy_spread = market_data.get(
            "hy_spread", 0.0
        )  # percentage points (e.g. 3.5 = 350bps)
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
        raw_probs = self._softmax(scores, temperature=1.5)

        # ── EMA smoothing (P3: regime hysteresis) ──
        # Prevents whipsaw by smoothing probability transitions.
        if self._ema_probs is None:
            self._ema_probs = raw_probs.copy()
        else:
            a = self._ema_alpha
            self._ema_probs = a * raw_probs + (1 - a) * self._ema_probs
        probs = self._ema_probs

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
        raw_regime = max(_probs, key=_probs.get)

        # ── Minimum hold time (P3: regime hysteresis) ──
        # Don't flip regime label unless min_hold_seconds have elapsed,
        # UNLESS it's a crisis override (VIX spike).
        now_ts = _time.time()
        if self._last_regime is None:
            # First call — accept whatever the model says
            regime = raw_regime
            self._last_regime = regime
            self._regime_since = now_ts
        elif raw_regime != self._last_regime:
            elapsed = now_ts - self._regime_since
            is_crisis = vix >= self.VIX_CRISIS
            if elapsed >= self._min_hold_seconds or is_crisis:
                # Enough time has passed (or crisis) — allow the flip
                regime = raw_regime
                self._last_regime = regime
                self._regime_since = now_ts
                logger.info(
                    f"Regime flip: {self._last_regime} → {regime} "
                    f"(after {elapsed:.0f}s, crisis={is_crisis})"
                )
            else:
                # Hold the old regime — too soon to flip
                regime = self._last_regime
        else:
            regime = self._last_regime

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

        # ── Graduated size scalar (Sprint 34) ──────────────────
        # crisis → 0 (no trade), high entropy → 0.5, weak
        # confidence → 0.6, normal → 1.0
        if vix >= self.VIX_CRISIS:
            size_scalar = 0.0
        elif entropy > self.no_trade_entropy:
            size_scalar = 0.5  # half size in uncertain regime
        elif max_prob < self.min_confidence:
            size_scalar = 0.6  # A-grade setups only
        elif entropy > 0.8:
            size_scalar = 0.75
        else:
            size_scalar = 1.0

        return RegimeState(
            # Derived labels
            regime=regime,
            risk_regime=risk_regime,
            trend_regime=trend_regime,
            volatility_regime=volatility_regime,
            no_trade_reason=no_trade_reason,
            # Probabilities
            risk_on_uptrend=round(risk_on_prob, 3),
            neutral_range=round(neutral_prob, 3),
            risk_off_downtrend=round(risk_off_prob, 3),
            entropy=round(entropy, 3),
            should_trade=should_trade,
            confidence=round(max_prob, 3),
            # Sizing
            size_scalar=size_scalar,
            # Raw inputs
            vix=vix,
            vix_term_slope=vix_term_slope,
            breadth_pct=breadth,
            credit_spread_z=hy_spread,
            realized_vol_20d=realized_vol,
            timestamp=datetime.now(timezone.utc).isoformat(),
        )

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
        self, regime_state,
    ) -> Dict[str, float]:
        """
        Convert regime state into strategy-family multipliers.

        Accepts both RegimeState object and plain dict.
        Returns dict mapping strategy family → sizing multiplier (0-1).
        """
        if isinstance(regime_state, RegimeState):
            risk_on = regime_state.risk_on_uptrend
            neutral = regime_state.neutral_range
            risk_off = regime_state.risk_off_downtrend
        else:
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
