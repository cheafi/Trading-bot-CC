"""
Regime-Sector Gate — Macro Routing Logic.

Before scoring, check if this sector bucket is compatible
with the current market regime. Incompatible combos get
score modifiers that effectively downgrade signals.

  RISK_OFF + HIGH_GROWTH  → -2.0
  RISK_OFF + THEME_HYPE   → -3.0
  CRISIS   + HIGH_GROWTH  → -4.0
  CRISIS   + CYCLICAL     → -2.0
  CRISIS   + THEME_HYPE   → -5.0
  RISK_ON  + DEFENSIVE    → -1.0
"""

from __future__ import annotations

from src.engines.sector_classifier import SectorBucket

# regime_label → { bucket → score modifier }
_REGIME_SECTOR_COMPAT: dict[str, dict[SectorBucket, float]] = {
    "RISK_OFF": {
        SectorBucket.HIGH_GROWTH: -2.0,
        SectorBucket.THEME_HYPE: -3.0,
        SectorBucket.CYCLICAL: -1.0,
    },
    "BEARISH": {
        SectorBucket.HIGH_GROWTH: -2.0,
        SectorBucket.THEME_HYPE: -3.0,
        SectorBucket.CYCLICAL: -1.0,
    },
    "CRISIS": {
        SectorBucket.HIGH_GROWTH: -4.0,
        SectorBucket.CYCLICAL: -2.0,
        SectorBucket.THEME_HYPE: -5.0,
    },
    "RISK_ON": {
        SectorBucket.DEFENSIVE: -1.0,
    },
    "BULLISH": {
        SectorBucket.DEFENSIVE: -1.0,
    },
}


def get_regime_sector_modifier(
    regime: dict,
    bucket: SectorBucket,
) -> float:
    """
    Return a score modifier for this regime+sector combo.

    Negative = penalise, zero = neutral.
    """
    trend = regime.get("trend", "").upper()
    compat = _REGIME_SECTOR_COMPAT.get(trend, {})
    return compat.get(bucket, 0.0)


def is_regime_blocked(
    regime: dict,
    bucket: SectorBucket,
) -> bool:
    """
    Returns True if this regime+sector combo should
    auto-downgrade to WATCH (modifier <= -3.0).
    """
    return get_regime_sector_modifier(regime, bucket) <= -3.0
