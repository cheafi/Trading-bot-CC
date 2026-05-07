"""
Regime Filter Engine — Sprint 52
==================================
Regime-aware signal quality filter that suppresses low-quality
setups in adverse market conditions.

This goes beyond the TradeGate (which is binary allow/block).
The RegimeFilter adjusts signal quality thresholds based on regime:
 - In RISK_ON: normal thresholds, more setups pass
 - In SIDEWAYS: tighter filters, only strong setups pass
 - In RISK_OFF: only A-grade setups with strong evidence pass
 - In CRISIS: near-total suppression, only extreme oversold bounce candidates

The key insight: the SAME signal quality means different things
in different regimes. RSI 45 in an uptrend is fine; RSI 45 in
a bear market is noise.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Optional


@dataclass
class FilterResult:
    """Result of regime-aware filtering."""

    passed: bool
    original_score: float
    adjusted_score: float
    regime: str
    min_score_required: float
    min_grade_required: str
    adjustments: list[str] = field(default_factory=list)
    suppression_reason: Optional[str] = None

    def to_dict(self) -> dict:
        return {
            "passed": self.passed,
            "original_score": self.original_score,
            "adjusted_score": self.adjusted_score,
            "regime": self.regime,
            "min_score_required": self.min_score_required,
            "min_grade_required": self.min_grade_required,
            "adjustments": self.adjustments,
            "suppression_reason": self.suppression_reason,
        }


# Regime-specific thresholds
_REGIME_THRESHOLDS = {
    "RISK_ON": {
        "min_score": 0.45,
        "min_grade": "C",
        "score_boost": 0.05,
        "label": "Favorable — normal filters",
    },
    "UPTREND": {
        "min_score": 0.45,
        "min_grade": "C",
        "score_boost": 0.05,
        "label": "Favorable — normal filters",
    },
    "SIDEWAYS": {
        "min_score": 0.60,
        "min_grade": "B",
        "score_boost": 0.0,
        "label": "Neutral — tighter filters",
    },
    "TRANSITIONAL": {
        "min_score": 0.65,
        "min_grade": "B",
        "score_boost": -0.05,
        "label": "Uncertain — cautious filters",
    },
    "RISK_OFF": {
        "min_score": 0.70,
        "min_grade": "A",
        "score_boost": -0.10,
        "label": "Adverse — only high-conviction setups",
    },
    "DOWNTREND": {
        "min_score": 0.70,
        "min_grade": "A",
        "score_boost": -0.10,
        "label": "Adverse — only high-conviction setups",
    },
    "CRISIS": {
        "min_score": 0.85,
        "min_grade": "A",
        "score_boost": -0.20,
        "label": "Crisis — near-total suppression",
    },
}

_DEFAULT_THRESHOLD = {
    "min_score": 0.55,
    "min_grade": "B",
    "score_boost": 0.0,
    "label": "Unknown regime — moderate filters",
}

_GRADE_ORDER = {"A": 4, "B": 3, "C": 2, "D": 1, "F": 0}


class RegimeFilter:
    """
    Regime-aware signal quality filter.
    """

    def evaluate(
        self,
        score: float,
        setup_grade: str,
        regime: str,
        direction: str = "LONG",
        rsi: float = 50.0,
        vix: Optional[float] = None,
    ) -> FilterResult:
        """
        Evaluate whether a signal passes regime-adjusted filters.
        """
        config = _REGIME_THRESHOLDS.get(regime, _DEFAULT_THRESHOLD)
        min_score = config["min_score"]
        min_grade = config["min_grade"]
        boost = config["score_boost"]

        adjustments: list[str] = []
        adjusted = score + boost

        if boost != 0:
            adjustments.append(f"Regime '{regime}' adjustment: {boost:+.2f}")

        # SHORT signals in RISK_OFF/CRISIS get a bonus
        if direction == "SHORT" and regime in ("RISK_OFF", "DOWNTREND", "CRISIS"):
            adjusted += 0.10
            adjustments.append("SHORT in bearish regime: +0.10 bonus")

        # Extreme RSI adjustments
        if rsi > 80 and direction == "LONG":
            adjusted -= 0.15
            adjustments.append(f"RSI {rsi:.0f} overbought penalty: -0.15")
        elif rsi < 25 and direction == "LONG":
            adjusted += 0.10
            adjustments.append(f"RSI {rsi:.0f} oversold bonus: +0.10")

        # VIX adjustment
        if vix is not None and vix > 35:
            adjusted -= 0.05
            adjustments.append(f"VIX {vix:.0f} elevated: -0.05")

        adjusted = max(0.0, min(1.0, adjusted))

        # Grade check
        grade_val = _GRADE_ORDER.get(setup_grade, 0)
        min_grade_val = _GRADE_ORDER.get(min_grade, 0)
        grade_pass = grade_val >= min_grade_val

        # Score check
        score_pass = adjusted >= min_score

        passed = score_pass and grade_pass
        reason = None
        if not passed:
            parts = []
            if not score_pass:
                parts.append(
                    f"Score {adjusted:.2f} < {min_score:.2f} " f"required in {regime}"
                )
            if not grade_pass:
                parts.append(
                    f"Grade {setup_grade} below {min_grade} " f"required in {regime}"
                )
            reason = "; ".join(parts)

        return FilterResult(
            passed=passed,
            original_score=score,
            adjusted_score=round(adjusted, 3),
            regime=regime,
            min_score_required=min_score,
            min_grade_required=min_grade,
            adjustments=adjustments,
            suppression_reason=reason,
        )

    def batch_filter(
        self,
        candidates: list[dict],
        regime: str,
    ) -> dict:
        """
        Filter a list of candidates and return pass/fail stats.

        candidates: [{"ticker": str, "score": float, "setup_grade": str, ...}]
        """
        passed = []
        filtered_out = []

        for c in candidates:
            result = self.evaluate(
                score=c.get("score", 0),
                setup_grade=c.get("setup_grade", "D"),
                regime=regime,
                direction=c.get("direction", "LONG"),
                rsi=c.get("rsi", 50),
            )
            c_out = {**c, "filter_result": result.to_dict()}
            if result.passed:
                passed.append(c_out)
            else:
                filtered_out.append(c_out)

        return {
            "regime": regime,
            "total_candidates": len(candidates),
            "passed_count": len(passed),
            "filtered_count": len(filtered_out),
            "selectivity": round(len(passed) / max(len(candidates), 1), 3),
            "passed": passed,
            "filtered_out": filtered_out,
        }

    def summary(self) -> dict:
        return {
            "engine": "RegimeFilter",
            "regime_thresholds": {
                k: {
                    "min_score": v["min_score"],
                    "min_grade": v["min_grade"],
                    "label": v["label"],
                }
                for k, v in _REGIME_THRESHOLDS.items()
            },
        }
