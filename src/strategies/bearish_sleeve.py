"""
Bearish Sleeve Strategy (Sprint 38).

Dedicated short + protective-put strategy activated when
the regime router signals risk-off or crisis conditions.

Entry signals:
  - Breakdown below 50-SMA with rising volume
  - Failed rally (lower high + reversal candle)
  - Sector weakness relative to SPY

Regime gate: only active in RISK_OFF or CRISIS regimes.
Put expression: auto-generates protective put plan via
ExpressionEngine when options data is available.
"""
from __future__ import annotations

import logging
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)


# Regime labels that enable the bearish sleeve
BEARISH_REGIMES = {
    "risk_off", "crisis", "risk_off_downtrend",
}


@dataclass
class BearishSetup:
    """A single bearish trade setup."""
    ticker: str
    direction: str = "SHORT"
    entry_price: float = 0.0
    stop_price: float = 0.0
    target_price: float = 0.0
    setup_type: str = "breakdown"   # breakdown | failed_rally | sector_weak
    confidence: float = 50.0
    risk_reward: float = 1.5
    sector: str = ""
    regime_label: str = ""

    # Optional protective put parameters
    put_strike: Optional[float] = None
    put_expiry: Optional[str] = None
    put_delta: float = -0.30

    def to_dict(self) -> Dict[str, Any]:
        d = {
            "ticker": self.ticker,
            "direction": self.direction,
            "entry_price": self.entry_price,
            "stop_price": self.stop_price,
            "target_price": self.target_price,
            "setup_type": self.setup_type,
            "confidence": self.confidence,
            "risk_reward": round(self.risk_reward, 2),
            "sector": self.sector,
            "regime_label": self.regime_label,
        }
        if self.put_strike:
            d["put_strike"] = self.put_strike
            d["put_expiry"] = self.put_expiry
            d["put_delta"] = self.put_delta
        return d


class BearishSleeve:
    """
    Generates short / put setups for risk-off regimes.

    Works alongside the long-only strategies. The engine
    only calls ``scan()`` when the regime gate allows it.

    Usage::

        sleeve = BearishSleeve()
        setups = sleeve.scan(
            tickers=["AAPL", "TSLA"],
            price_data={"AAPL": {...}, "TSLA": {...}},
            regime_state={"regime": "risk_off", ...},
        )
    """

    # Breakdown thresholds
    SMA_PERIOD = 50
    VOLUME_SURGE = 1.5     # relative volume for confirmation
    MIN_DECLINE_PCT = 2.0  # min % below SMA50

    def __init__(self):
        self._setups: List[BearishSetup] = []

    def is_active(
        self, regime_state: Dict[str, Any],
    ) -> bool:
        """Check if bearish sleeve should be active."""
        regime = regime_state.get("regime", "")
        risk = regime_state.get("risk_regime", "")
        return (
            regime in BEARISH_REGIMES
            or risk in ("risk_off", "crisis")
        )

    def scan(
        self,
        tickers: List[str],
        price_data: Dict[str, Dict[str, Any]],
        regime_state: Dict[str, Any],
    ) -> List[BearishSetup]:
        """Scan tickers for bearish setups.

        Args:
            tickers: list of tickers to scan
            price_data: ticker → {close, sma50, volume,
                        avg_volume, high_52w, rsi_14, ...}
            regime_state: current regime classification

        Returns:
            List of BearishSetup objects sorted by confidence
        """
        if not self.is_active(regime_state):
            return []

        regime_label = regime_state.get("regime", "risk_off")
        setups: List[BearishSetup] = []

        for ticker in tickers:
            data = price_data.get(ticker, {})
            if not data:
                continue

            setup = self._evaluate_ticker(
                ticker, data, regime_label,
            )
            if setup:
                setups.append(setup)

        # Sort by confidence descending
        setups.sort(key=lambda s: -s.confidence)
        self._setups = setups
        return setups

    def _evaluate_ticker(
        self,
        ticker: str,
        data: Dict[str, Any],
        regime_label: str,
    ) -> Optional[BearishSetup]:
        """Evaluate a single ticker for bearish setup."""
        close = data.get("close", 0)
        sma50 = data.get("sma50", 0)
        volume = data.get("volume", 0)
        avg_volume = data.get("avg_volume", 1)
        rsi = data.get("rsi_14", 50)
        high_52w = data.get("high_52w", close)
        sector = data.get("sector", "")

        if not close or not sma50:
            return None

        # Check breakdown: price below SMA50
        pct_below = (sma50 - close) / sma50 * 100
        rel_vol = volume / avg_volume if avg_volume > 0 else 1

        # Breakdown setup
        if (
            pct_below >= self.MIN_DECLINE_PCT
            and rel_vol >= self.VOLUME_SURGE
        ):
            confidence = min(
                85, 50 + pct_below * 3 + (rel_vol - 1) * 10,
            )
            # Stop above SMA50
            stop = sma50 * 1.02
            # Target: -2x the stop distance
            risk = stop - close
            target = close - risk * 2
            rr = abs(close - target) / abs(
                stop - close
            ) if abs(stop - close) > 0 else 1.5

            return BearishSetup(
                ticker=ticker,
                entry_price=close,
                stop_price=round(stop, 2),
                target_price=round(target, 2),
                setup_type="breakdown",
                confidence=round(confidence, 0),
                risk_reward=round(rr, 2),
                sector=sector,
                regime_label=regime_label,
            )

        # Failed rally: RSI > 60 but still below SMA50
        if pct_below > 0 and rsi > 60:
            confidence = min(70, 40 + rsi - 60 + pct_below * 2)
            stop = sma50 * 1.01
            risk = stop - close
            target = close - risk * 1.5

            return BearishSetup(
                ticker=ticker,
                entry_price=close,
                stop_price=round(stop, 2),
                target_price=round(max(0, target), 2),
                setup_type="failed_rally",
                confidence=round(confidence, 0),
                risk_reward=1.5,
                sector=sector,
                regime_label=regime_label,
            )

        return None

    def get_cached_setups(self) -> List[Dict[str, Any]]:
        """Return cached setups as dicts."""
        return [s.to_dict() for s in self._setups]
