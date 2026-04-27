"""
CC — Decision Mapper
======================
Maps fit score + confidence → one of 7 canonical actions:
  TRADE / WATCH / WAIT / HOLD / REDUCE / EXIT / NO_TRADE

Also produces a one-line rationale for each decision.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import Any, Dict

from src.engines.confidence_engine import ConfidenceBreakdown
from src.engines.fit_scorer import FitScores
from src.engines.sector_classifier import SectorBucket, SectorContext

logger = logging.getLogger(__name__)


class Action:
    TRADE = "TRADE"
    WATCH = "WATCH"
    WAIT = "WAIT"
    HOLD = "HOLD"
    REDUCE = "REDUCE"
    EXIT = "EXIT"
    NO_TRADE = "NO_TRADE"

    ALL = (TRADE, WATCH, WAIT, HOLD, REDUCE, EXIT, NO_TRADE)


@dataclass
class Decision:
    """Final decision output."""

    action: str = Action.NO_TRADE
    rationale: str = ""
    score: float = 0.0
    grade: str = "F"
    confidence: float = 0.0
    confidence_label: str = "LOW"
    risk_level: str = "HIGH"  # LOW / MEDIUM / HIGH / EXTREME
    position_size_pct: float = 0.0  # % of portfolio
    size_rationale: str = ""
    # Entry/exit instructions (Priority 4 from review)
    entry_trigger: str = ""    # e.g. "Buy above $152.30 on 1.5x avg volume"
    stop_price: float = 0.0   # Computed from structure, not passed in
    stop_rationale: str = ""   # e.g. "Below swing low at $145.20"
    target_price: float = 0.0
    risk_reward: float = 0.0   # Computed entry→stop / entry→target

    def to_dict(self) -> Dict[str, Any]:
        d = {
            "action": self.action,
            "rationale": self.rationale,
            "score": round(self.score, 1),
            "grade": self.grade,
            "confidence": round(self.confidence, 2),
            "confidence_label": self.confidence_label,
            "risk_level": self.risk_level,
            "position_size_pct": round(self.position_size_pct, 1),
            "size_rationale": self.size_rationale,
        }
        if self.entry_trigger:
            d["entry_trigger"] = self.entry_trigger
        if self.stop_price > 0:
            d["stop_price"] = round(self.stop_price, 2)
            d["stop_rationale"] = self.stop_rationale
        if self.target_price > 0:
            d["target_price"] = round(self.target_price, 2)
        if self.risk_reward > 0:
            d["risk_reward"] = round(self.risk_reward, 2)
        return d


class DecisionMapper:
    """Map fit + confidence → action."""

    def decide(
        self,
        fit: FitScores,
        confidence: ConfidenceBreakdown,
        sector: SectorContext,
        regime: Dict[str, Any],
    ) -> Decision:
        d = Decision(
            score=fit.final_score,
            grade=fit.grade,
            confidence=confidence.final,
            confidence_label=confidence.label,
        )

        should_trade = regime.get("should_trade", True)
        score = fit.final_score
        conf = confidence.final

        # Hard blocks
        if not should_trade:
            d.action = Action.NO_TRADE
            d.rationale = "Market regime blocks new entries"
            d.risk_level = "EXTREME"
            return d

        if fit.evidence_conflicts and len(fit.evidence_conflicts) >= 3:
            d.action = Action.NO_TRADE
            d.rationale = f"Too many conflicts: {', '.join(fit.evidence_conflicts[:2])}"
            d.risk_level = "HIGH"
            return d

        # Theme/hype in distribution
        from src.engines.sector_classifier import SectorStage

        if (
            sector.sector_bucket == SectorBucket.THEME_HYPE
            and sector.sector_stage == SectorStage.DISTRIBUTION
        ):
            d.action = Action.NO_TRADE
            d.rationale = "Theme in distribution stage — avoid"
            d.risk_level = "EXTREME"
            return d

        # Score+confidence matrix
        # Minimum confidence floor — very low confidence = NO_TRADE
        if conf < 0.35:
            d.action = Action.NO_TRADE
            d.rationale = f"Confidence too low ({conf:.0%}) — insufficient conviction"
            d.risk_level = "HIGH"
        elif score >= 8.0 and conf >= 0.65:
            d.action = Action.TRADE
            d.rationale = "High-conviction setup — actionable"
            d.risk_level = "LOW"
        elif score >= 7.0 and conf >= 0.55:
            d.action = Action.TRADE
            d.rationale = "Good setup with decent confidence"
            d.risk_level = "MEDIUM"
        elif score >= 6.5 and conf >= 0.5:
            d.action = Action.WATCH
            d.rationale = "Promising but needs confirmation"
            d.risk_level = "MEDIUM"
        elif score >= 5.5 and conf >= 0.4:
            d.action = Action.WAIT
            d.rationale = "Setup forming — wait for better entry"
            d.risk_level = "MEDIUM"
        elif score >= 4.0:
            d.action = Action.WATCH
            d.rationale = "Weak setup — monitor only"
            d.risk_level = "HIGH"
        else:
            d.action = Action.NO_TRADE
            d.rationale = "Insufficient quality"
            d.risk_level = "HIGH"

        # Override for laggards
        from src.engines.sector_classifier import LeaderStatus

        if sector.leader_status == LeaderStatus.LAGGARD and d.action == Action.TRADE:
            d.action = Action.WATCH
            d.rationale += " (downgraded: laggard, not leader)"
            d.risk_level = "MEDIUM"

        # Position sizing (only for TRADE)
        if d.action == Action.TRADE:
            atr = fit.raw.get("atr_pct", 0) if hasattr(fit, "raw") else 0
            d.position_size_pct, d.size_rationale = self._size(
                conf, d.risk_level, score, atr_pct=atr
            )

        # Entry trigger + stop/target from structure (Priority 4)
        if d.action in (Action.TRADE, Action.WATCH):
            sig = fit.raw if hasattr(fit, "raw") else {}
            self._set_entry_exit(d, sig)

        return d

    @staticmethod
    def _set_entry_exit(d: "Decision", sig: dict) -> None:
        """Populate entry trigger, stop, target from signal data."""
        resistance = sig.get("nearest_resistance", sig.get("resistance", 0))
        support = sig.get("nearest_support", sig.get("support", 0))
        price = sig.get("price", sig.get("close", 0))
        avg_vol = sig.get("avg_volume", 0)

        # Entry trigger: buy above resistance with volume
        if resistance > 0 and price > 0:
            d.entry_trigger = (
                f"Buy above ${resistance:.2f}"
                + (f" on ≥{int(avg_vol * 1.5):,} vol"
                   if avg_vol > 0 else " with volume confirmation")
            )
        elif price > 0:
            d.entry_trigger = f"Buy near ${price:.2f} with volume confirmation"

        # Stop from structure (swing low / support)
        if support > 0:
            d.stop_price = round(support * 0.99, 2)  # 1% below support
            d.stop_rationale = f"Below support at ${support:.2f}"
        elif price > 0:
            atr_pct = sig.get("atr_pct", 2.0)
            d.stop_price = round(price * (1 - atr_pct / 100 * 2), 2)
            d.stop_rationale = f"2x ATR ({atr_pct:.1f}%) below entry"

        # Target: 2:1 R:R minimum or resistance
        if d.stop_price > 0 and price > 0:
            risk = price - d.stop_price
            if risk > 0:
                d.target_price = round(price + risk * 2.5, 2)
                d.risk_reward = round(2.5, 2)
            elif resistance > price:
                d.target_price = resistance
                r = (resistance - price)
                d.risk_reward = round(r / abs(risk), 2) if risk != 0 else 0

    @staticmethod
    def _size(
        conf: float, risk_level: str, score: float,
        atr_pct: float = 0.0,
    ) -> tuple[float, str]:
        """Compute position size as % of portfolio, ATR-normalized."""
        # Base: 2% for medium, scale by confidence
        base = {"LOW": 3.0, "MEDIUM": 2.0, "HIGH": 1.0, "EXTREME": 0.5}
        size = base.get(risk_level, 2.0)

        # Scale by confidence (0.5-1.0 → 0.5x-1.5x)
        size *= 0.5 + conf

        # Score bonus
        if score >= 8.5:
            size *= 1.2

        # ATR normalization: high-vol stocks get smaller positions
        # Target ~2% dollar risk → if ATR is 4%, halve the position
        if atr_pct > 0:
            atr_factor = 2.0 / atr_pct  # normalize to 2% ATR baseline
            atr_factor = max(0.3, min(2.0, atr_factor))  # clamp
            size *= atr_factor

        size = round(max(0.5, min(5.0, size)), 1)
        parts = []
        if risk_level == "LOW":
            parts.append("low risk")
        if conf >= 0.7:
            parts.append(f"high conf {conf:.0%}")
        if score >= 8.5:
            parts.append("A+ score")
        if atr_pct > 0:
            parts.append(f"ATR {atr_pct:.1f}%")
        rationale = ", ".join(parts) if parts else "standard"
        return size, rationale
