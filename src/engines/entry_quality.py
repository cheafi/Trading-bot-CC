"""
Entry Quality Filter — Pre-Trade Gatekeeper.

Before ANY trade, this engine asks:
1. Is the entry late? (days since breakout)
2. Is price extended? (% above SMA20/pivot)
3. Is R/R acceptable? (using actual S/R, not just ATR)
4. Is price near resistance? (ceiling risk)
5. Is volume confirming? (conviction check)
6. Is the setup sector-appropriate?

Output: PASS / WATCH / WAIT / REJECT with reasons.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Dict, Optional

import numpy as np

logger = logging.getLogger(__name__)


class EntryVerdict(str, Enum):
    PASS = "pass"  # Good entry — proceed
    WATCH = "watch"  # Setup forming, not ready
    WAIT = "wait"  # Right idea, wrong time
    REJECT = "reject"  # Bad entry — skip


@dataclass
class EntryQualityReport:
    """Entry quality assessment."""

    verdict: EntryVerdict = EntryVerdict.WATCH
    score: float = 50.0  # 0-100
    reasons_pass: list = field(default_factory=list)
    reasons_fail: list = field(default_factory=list)

    # Individual checks
    days_since_breakout: int = 0
    is_late_entry: bool = False
    extension_pct: float = 0.0
    is_extended: bool = False
    risk_reward_ratio: float = 0.0
    rr_acceptable: bool = False
    distance_to_resistance_pct: float = 0.0
    near_resistance: bool = False
    volume_confirming: bool = False
    volume_declining: bool = False

    # Sector-specific
    sector_type: str = "unknown"
    sector_appropriate: bool = True

    def to_dict(self) -> Dict[str, Any]:
        return {
            "verdict": self.verdict.value,
            "score": round(self.score, 1),
            "reasons_pass": self.reasons_pass[:5],
            "reasons_fail": self.reasons_fail[:5],
            "days_since_breakout": self.days_since_breakout,
            "is_late_entry": self.is_late_entry,
            "extension_pct": round(self.extension_pct, 2),
            "is_extended": self.is_extended,
            "risk_reward": round(self.risk_reward_ratio, 2),
            "rr_acceptable": self.rr_acceptable,
            "distance_to_resistance_pct": round(self.distance_to_resistance_pct, 2),
            "near_resistance": self.near_resistance,
            "volume_confirming": self.volume_confirming,
            "volume_declining": self.volume_declining,
            "sector_type": self.sector_type,
            "sector_appropriate": self.sector_appropriate,
        }


class EntryQualityEngine:
    """
    Entry quality gatekeeper.

    "NO TRADE is a valid output."
    """

    # Sector-specific thresholds
    SECTOR_PARAMS = {
        "high_growth": {
            "max_extension_pct": 8.0,
            "min_rr": 2.0,
            "max_days_late": 5,
            "atr_stop_mult": 2.5,
        },
        "cyclical": {
            "max_extension_pct": 5.0,
            "min_rr": 2.5,
            "max_days_late": 3,
            "atr_stop_mult": 2.0,
        },
        "defensive": {
            "max_extension_pct": 3.0,
            "min_rr": 3.0,
            "max_days_late": 3,
            "atr_stop_mult": 1.5,
        },
        "theme_speculative": {
            "max_extension_pct": 10.0,
            "min_rr": 3.0,
            "max_days_late": 2,
            "atr_stop_mult": 3.0,
        },
        "unknown": {
            "max_extension_pct": 5.0,
            "min_rr": 2.5,
            "max_days_late": 3,
            "atr_stop_mult": 2.0,
        },
    }

    def assess(
        self,
        close: np.ndarray,
        high: np.ndarray,
        low: np.ndarray,
        volume: np.ndarray,
        atr: float,
        entry_price: float,
        stop_price: float,
        target_price: float,
        nearest_resistance: Optional[float] = None,
        nearest_support: Optional[float] = None,
        sector_type: str = "unknown",
    ) -> EntryQualityReport:
        """Full entry quality assessment."""
        report = EntryQualityReport()
        report.sector_type = sector_type
        params = self.SECTOR_PARAMS.get(sector_type, self.SECTOR_PARAMS["unknown"])

        score = 50.0

        # ── 1. Days since breakout ──
        if len(high) > 1:
            recent_high_idx = int(np.argmax(high[-20:]))
            days_ago = len(high[-20:]) - 1 - recent_high_idx
            report.days_since_breakout = days_ago
            max_days = params["max_days_late"]
            if days_ago > max_days:
                report.is_late_entry = True
                report.reasons_fail.append(
                    f"Late entry: {days_ago}d since breakout"
                    f" (max {max_days}d for {sector_type})"
                )
                score -= 15
            elif days_ago <= 1:
                report.reasons_pass.append("Day 1-2 of breakout — optimal timing")
                score += 15
            else:
                report.reasons_pass.append(f"Day {days_ago} — acceptable window")
                score += 5

        # ── 2. Extension check ──
        if len(close) >= 20:
            sma20 = float(np.mean(close[-20:]))
            ext = (entry_price - sma20) / sma20 * 100
            report.extension_pct = ext
            max_ext = params["max_extension_pct"]
            if ext > max_ext:
                report.is_extended = True
                report.reasons_fail.append(
                    f"Extended {ext:.1f}% above SMA20"
                    f" (max {max_ext}% for {sector_type})"
                )
                score -= 15
            elif ext > max_ext * 0.7:
                report.reasons_fail.append(f"Somewhat extended ({ext:.1f}%)")
                score -= 5
            else:
                report.reasons_pass.append(f"Not extended ({ext:.1f}% from SMA20)")
                score += 10

        # ── 3. R/R ratio ──
        risk = abs(entry_price - stop_price)
        reward = abs(target_price - entry_price)
        if risk > 0:
            rr = reward / risk
            report.risk_reward_ratio = rr
            min_rr = params["min_rr"]
            if rr >= min_rr:
                report.rr_acceptable = True
                report.reasons_pass.append(
                    f"R/R {rr:.1f}:1 — acceptable" f" (min {min_rr}:1)"
                )
                score += 15
            else:
                report.reasons_fail.append(
                    f"Poor R/R {rr:.1f}:1" f" (need {min_rr}:1 for {sector_type})"
                )
                score -= 15

        # Use S/R for better R/R if available
        if nearest_support and nearest_support < entry_price:
            sr_risk = entry_price - nearest_support
            if nearest_resistance:
                sr_reward = nearest_resistance - entry_price
                if sr_risk > 0:
                    sr_rr = sr_reward / sr_risk
                    if sr_rr > report.risk_reward_ratio:
                        report.reasons_pass.append(
                            f"S/R-based R/R {sr_rr:.1f}:1" " — structure confirms"
                        )

        # ── 4. Near resistance? ──
        if nearest_resistance and nearest_resistance > 0:
            dist = (nearest_resistance - entry_price) / entry_price * 100
            report.distance_to_resistance_pct = dist
            if dist < 1.5:
                report.near_resistance = True
                report.reasons_fail.append(
                    f"Only {dist:.1f}% below resistance" f" (${nearest_resistance:.2f})"
                )
                score -= 15
            elif dist < 3.0:
                report.reasons_fail.append(f"Resistance nearby ({dist:.1f}% away)")
                score -= 5

        # ── 5. Volume check ──
        if len(volume) >= 20:
            avg_vol = float(np.mean(volume[-20:]))
            cur_vol = float(volume[-1])
            if cur_vol > avg_vol * 1.5:
                report.volume_confirming = True
                report.reasons_pass.append(
                    f"Volume {cur_vol / avg_vol:.1f}x" " — conviction confirmed"
                )
                score += 10
            elif cur_vol < avg_vol * 0.7:
                report.volume_declining = True
                report.reasons_fail.append("Volume below average — weak conviction")
                score -= 10

        # ── 6. Sector appropriateness ──
        report.sector_appropriate = True
        if sector_type == "theme_speculative":
            if report.is_late_entry:
                report.sector_appropriate = False
                report.reasons_fail.append("Theme stock + late entry = highest risk")
                score -= 10
        elif sector_type == "defensive":
            if report.is_extended:
                report.sector_appropriate = False
                report.reasons_fail.append(
                    "Defensive stock extended — " "mean reversion likely"
                )
                score -= 10

        # ── Final verdict ──
        report.score = max(0, min(100, score))

        if report.score >= 70:
            report.verdict = EntryVerdict.PASS
        elif report.score >= 55:
            report.verdict = EntryVerdict.WATCH
        elif report.score >= 40:
            report.verdict = EntryVerdict.WAIT
        else:
            report.verdict = EntryVerdict.REJECT

        return report


def check_entry_quality(
    close: list,
    high: list,
    low: list,
    volume: list,
    atr: float,
    entry_price: float,
    stop_price: float,
    target_price: float,
    nearest_resistance: float = None,
    nearest_support: float = None,
    sector_type: str = "unknown",
) -> Dict[str, Any]:
    """Convenience function."""
    engine = EntryQualityEngine()
    report = engine.assess(
        np.array(close, dtype=float),
        np.array(high, dtype=float),
        np.array(low, dtype=float),
        np.array(volume, dtype=float),
        atr,
        entry_price,
        stop_price,
        target_price,
        nearest_resistance,
        nearest_support,
        sector_type,
    )
    return report.to_dict()
