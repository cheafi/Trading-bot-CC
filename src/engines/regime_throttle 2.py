"""
Regime-based signal throttling.

Reduces signal volume in hostile market environments instead of
completely shutting off. This sits between signal generation and
output delivery.

Configuration lives in config/default.yaml under:
  regime:
    throttle:
      bear_volatile: 0.5    # emit 50% of signals
      crisis: 0.25           # emit 25% of signals

Usage:
    throttle = RegimeThrottle()
    signals = throttle.apply(signals, regime_state="bear_volatile")
"""
from __future__ import annotations

import logging
from typing import Dict, Optional

logger = logging.getLogger(__name__)

# Default throttle rates per regime state.
# 1.0 = no throttle (all signals pass).
# 0.5 = keep 50% of signals (top-scored ones).
# 0.0 = block all signals.
DEFAULT_THROTTLE_RATES: Dict[str, float] = {
    "bull_trending": 1.0,
    "bull_volatile": 0.85,
    "bull_exhaustion": 0.7,
    "neutral_consolidation": 1.0,
    "sideways": 0.8,
    "bear_rally": 0.6,
    "bear_trending": 0.4,
    "bear_volatile": 0.3,
    "crisis": 0.15,
}


class RegimeThrottle:
    """
    Throttle signal output based on current market regime.

    In hostile regimes (bear_volatile, crisis), the best action is often
    to do nothing. This throttle keeps only the highest-scored signals
    and discards the rest, reducing noise and impulsive trading.

    Strategy:
    - Signals are sorted by score (highest first)
    - Only the top N% are kept, where N is the throttle rate
    - At least 1 signal always passes (if any exist) to avoid total silence
    """

    def __init__(self, overrides: Optional[Dict[str, float]] = None):
        self.rates = {**DEFAULT_THROTTLE_RATES, **(overrides or {})}

    def get_rate(self, regime_state: str) -> float:
        """Get the throttle rate for a regime. 1.0 = no throttle."""
        return self.rates.get(regime_state, 1.0)

    def apply(
        self,
        signals: list,
        regime_state: str,
        min_keep: int = 1,
    ) -> list:
        """
        Apply regime-based throttling to a list of signals.

        Args:
            signals: List of Signal objects (must have .confidence attr)
            regime_state: Current regime string (e.g. "bear_volatile")
            min_keep: Always keep at least this many signals (default 1)

        Returns:
            Filtered list of signals (highest-scored first)
        """
        if not signals:
            return signals

        rate = self.get_rate(regime_state)

        # No throttle needed
        if rate >= 1.0:
            return signals

        # Sort by confidence descending (best signals first)
        sorted_signals = sorted(
            signals,
            key=lambda s: getattr(s, "confidence", 0),
            reverse=True,
        )

        # Calculate how many to keep
        keep_count = max(
            min_keep,
            int(len(sorted_signals) * rate),
        )

        kept = sorted_signals[:keep_count]
        dropped = len(sorted_signals) - len(kept)

        if dropped > 0:
            logger.info(
                f"Regime throttle [{regime_state}] rate={rate:.0%}: "
                f"kept {len(kept)}/{len(sorted_signals)} signals "
                f"(dropped {dropped} lower-scored)"
            )

        return kept

    def should_suppress_alerts(self, regime_state: str) -> bool:
        """Whether the regime is hostile enough to add extra warnings."""
        return self.get_rate(regime_state) < 0.5

    def get_regime_warning(self, regime_state: str) -> Optional[str]:
        """Get a human-readable warning for hostile regimes."""
        rate = self.get_rate(regime_state)
        if rate >= 0.8:
            return None
        if rate >= 0.5:
            return (
                f"⚠️ Market regime is {regime_state}. "
                "Signal confidence may be lower than usual. "
                "Consider smaller position sizes."
            )
        if rate >= 0.2:
            return (
                f"🔴 Market regime is {regime_state}. "
                "Most signals are being suppressed. "
                "Only highest-conviction setups are shown. "
                "Consider staying in cash."
            )
        return (
            f"🚨 CRISIS regime detected ({regime_state}). "
            "Nearly all signals suppressed. "
            "Capital preservation is the priority. "
            "Do not trade unless you have a specific, "
            "well-reasoned thesis."
        )
