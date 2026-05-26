"""
Actionable Scanner Results — Evidence-backed scanner output (Sprint 71)
=======================================================================

Redesigns scanner output so every result carries:
  - A specific recommended action (buy, sell, trim, add, hedge, watch, avoid)
  - Supporting evidence (pattern, catalyst, technical trigger, fundamental shift)
  - Confidence score with calibration history
  - Clear next-step trigger (price level, date, earnings event)

No more naked rankings — every result is actionable or it doesn't ship.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)


class ScannerAction(str, Enum):
    """Recommended actions for scanner results."""
    BUY = "BUY"
    SELL = "SELL"
    TRIM = "TRIM"
    ADD = "ADD"
    HEDGE = "HEDGE"
    WATCH = "WATCH"
    AVOID = "AVOID"


class EvidenceType(str, Enum):
    """Types of supporting evidence."""
    PATTERN_DETECTED = "pattern_detected"
    CATALYST_CONFIRMED = "catalyst_confirmed"
    TECHNICAL_TRIGGER = "technical_trigger"
    FUNDAMENTAL_SHIFT = "fundamental_shift"
    VOLUME_CONFIRMATION = "volume_confirmation"
    RS_LEADERSHIP = "rs_leadership"
    REGIME_ALIGNMENT = "regime_alignment"
    SECTOR_ROTATION = "sector_rotation"
    BREAKOUT = "breakout"
    MEAN_REVERSION = "mean_reversion"


@dataclass
class Evidence:
    """A single piece of supporting evidence."""
    evidence_type: EvidenceType
    description: str
    strength: float = 0.0  # 0–1
    source: str = ""

    def to_dict(self) -> Dict[str, Any]:
        return {
            "type": self.evidence_type.value,
            "description": self.description,
            "strength": round(self.strength, 3),
            "source": self.source,
        }


@dataclass
class NextStepTrigger:
    """Clear next-step trigger for the recommendation."""
    trigger_type: str = ""  # "price_level", "date", "earnings", "regime_change"
    description: str = ""
    trigger_value: str = ""
    urgency: str = ""  # "immediate", "this_week", "this_month"

    def to_dict(self) -> Dict[str, Any]:
        return {
            "type": self.trigger_type,
            "description": self.description,
            "value": self.trigger_value,
            "urgency": self.urgency,
        }


@dataclass
class ActionableResult:
    """A single actionable scanner result."""
    ticker: str
    action: ScannerAction
    confidence: float = 0.0  # 0–100
    calibrated_confidence: Optional[float] = None

    # Evidence
    evidence: List[Evidence] = field(default_factory=list)

    # Next step
    next_step: Optional[NextStepTrigger] = None

    # Context
    strategy: str = ""
    scanner_source: str = ""
    detected_at: str = ""

    # Price levels
    current_price: float = 0.0
    entry_zone: tuple = (0.0, 0.0)
    stop_loss: float = 0.0
    targets: List[float] = field(default_factory=list)

    # Risk
    risk_reward_ratio: float = 0.0
    position_size_suggestion: str = ""

    # Calibration history
    historical_accuracy: Optional[float] = None
    historical_sample_size: int = 0

    def to_dict(self) -> Dict[str, Any]:
        return {
            "ticker": self.ticker,
            "action": self.action.value,
            "confidence": round(self.confidence, 1),
            "calibrated_confidence": (
                round(self.calibrated_confidence, 1)
                if self.calibrated_confidence is not None else None
            ),
            "evidence": [e.to_dict() for e in self.evidence],
            "next_step": self.next_step.to_dict() if self.next_step else None,
            "strategy": self.strategy,
            "scanner_source": self.scanner_source,
            "detected_at": self.detected_at,
            "current_price": round(self.current_price, 2),
            "entry_zone": list(self.entry_zone),
            "stop_loss": round(self.stop_loss, 2),
            "targets": [round(t, 2) for t in self.targets],
            "risk_reward_ratio": round(self.risk_reward_ratio, 2),
            "position_size_suggestion": self.position_size_suggestion,
            "historical_accuracy": (
                round(self.historical_accuracy, 3)
                if self.historical_accuracy is not None else None
            ),
            "historical_sample_size": self.historical_sample_size,
        }


@dataclass
class ActionableScannerOutput:
    """Complete output from an actionable scanner run."""
    scanner_name: str = ""
    run_at: str = ""
    total_scanned: int = 0
    total_actionable: int = 0
    results: List[ActionableResult] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "scanner_name": self.scanner_name,
            "run_at": self.run_at,
            "total_scanned": self.total_scanned,
            "total_actionable": self.total_actionable,
            "results": [r.to_dict() for r in self.results],
        }


class ActionableScannerEngine:
    """Wraps raw scanner output into actionable results with evidence.

    Usage::

        engine = ActionableScannerEngine()
        output = engine.process_raw_results(
            scanner_name="momentum",
            raw_results=[...],
            calibration_data=calibrator,
        )
    """

    def process_raw_results(
        self,
        scanner_name: str,
        raw_results: List[Dict[str, Any]],
        *,
        calibration_data: Optional[Any] = None,
    ) -> ActionableScannerOutput:
        """Process raw scanner results into actionable output."""
        now = datetime.now(timezone.utc).isoformat()
        output = ActionableScannerOutput(
            scanner_name=scanner_name,
            run_at=now,
            total_scanned=len(raw_results),
        )

        for raw in raw_results:
            result = self._process_single(raw, scanner_name, calibration_data)
            if result is not None:
                output.results.append(result)

        output.total_actionable = len(output.results)

        # Sort by confidence descending
        output.results.sort(key=lambda r: r.confidence, reverse=True)

        return output

    def _process_single(
        self,
        raw: Dict[str, Any],
        scanner_name: str,
        calibration_data: Optional[Any],
    ) -> Optional[ActionableResult]:
        """Process a single raw result into an actionable result."""
        ticker = raw.get("ticker") or raw.get("symbol", "")
        if not ticker:
            return None

        # Determine action
        action = self._determine_action(raw)
        if action is None:
            return None  # Skip results without a clear action

        # Build evidence list
        evidence = self._extract_evidence(raw)

        # Need at least one piece of evidence
        if not evidence:
            return None
        # Confidence
        confidence = raw.get("confidence", raw.get("score", 50))
        if isinstance(confidence, (int, float)) and confidence > 1:
            confidence = min(confidence, 100)
        else:
            confidence = (confidence or 0.5) * 100

        # Calibrated confidence
        calibrated = None
        if calibration_data and hasattr(calibration_data, "calibrate"):
            try:
                calibrated = calibration_data.calibrate(confidence / 100) * 100
            except Exception:
                pass

        # Next step trigger
        next_step = self._build_next_step(raw, action)

        # Price levels
        entry_zone = (
            raw.get("entry_low", 0.0),
            raw.get("entry_high", 0.0),
        )
        stop_loss = raw.get("stop_loss", 0.0)
        targets = raw.get("targets", [])

        # Risk/reward
        current = raw.get("current_price", raw.get("price", 0.0))
        rr = 0.0
        if stop_loss > 0 and targets and current > 0:
            risk = abs(current - stop_loss)
            reward = abs(targets[0] - current) if targets else 0
            rr = reward / risk if risk > 0 else 0

        result = ActionableResult(
            ticker=ticker,
            action=action,
            confidence=confidence,
            calibrated_confidence=calibrated,
            evidence=evidence,
            next_step=next_step,
            strategy=raw.get("strategy", scanner_name),
            scanner_source=scanner_name,
            detected_at=raw.get("detected_at", datetime.now(timezone.utc).isoformat()),
            current_price=current,
            entry_zone=entry_zone,
            stop_loss=stop_loss,
            targets=targets,
            risk_reward_ratio=rr,
        )

        return result

    def _determine_action(
        self, raw: Dict[str, Any]
    ) -> Optional[ScannerAction]:
        """Determine the recommended action from raw data."""
        # Explicit action field
        action_str = raw.get("action", "").upper()
        if action_str:
            try:
                return ScannerAction(action_str)
            except ValueError:
                pass

        # Derive from signal properties
        direction = raw.get("direction", "").upper()
        signal_type = raw.get("signal_type", "").upper()
        confidence = raw.get("confidence", raw.get("score", 0))
        if isinstance(confidence, (int, float)) and confidence > 1:
            pass  # already 0-100
        else:
            confidence = (confidence or 0) * 100

        # Already holding?
        is_held = raw.get("is_held", False)

        if direction == "LONG" or signal_type in ("BREAKOUT", "GAP_UP", "RS_NEW_HIGH"):
            if is_held:
                return ScannerAction.ADD if confidence >= 70 else ScannerAction.WATCH
            return ScannerAction.BUY if confidence >= 60 else ScannerAction.WATCH
        elif direction == "SHORT" or signal_type in ("BREAKDOWN", "GAP_DOWN"):
            if is_held:
                return ScannerAction.TRIM if confidence >= 60 else ScannerAction.HEDGE
            return ScannerAction.AVOID if confidence >= 70 else ScannerAction.WATCH
        elif signal_type == "MEAN_REVERSION":
            return ScannerAction.WATCH

        return None

    def _extract_evidence(self, raw: Dict[str, Any]) -> List[Evidence]:
        """Extract supporting evidence from raw data."""
        evidence = []

        # Pattern detection
        pattern = raw.get("pattern") or raw.get("pattern_detected")
        if pattern:
            evidence.append(Evidence(
                evidence_type=EvidenceType.PATTERN_DETECTED,
                description=f"Pattern: {pattern}",
                strength=raw.get("pattern_strength", 0.7),
                source="pattern_scanner",
            ))

        # Technical trigger
        triggers = raw.get("triggers", [])
        if isinstance(triggers, list):
            for t in triggers:
                if isinstance(t, str):
                    evidence.append(Evidence(
                        evidence_type=EvidenceType.TECHNICAL_TRIGGER,
                        description=t,
                        strength=0.7,
                    ))
                elif isinstance(t, dict):
                    evidence.append(Evidence(
                        evidence_type=EvidenceType.TECHNICAL_TRIGGER,
                        description=t.get("description", str(t)),
                        strength=t.get("strength", 0.7),
                    ))

        # Volume confirmation
        if raw.get("volume_confirmation") or raw.get("volume_surge"):
            evidence.append(Evidence(
                evidence_type=EvidenceType.VOLUME_CONFIRMATION,
                description="Volume confirms price action",
                strength=0.8,
            ))

        # RS leadership
        rs = raw.get("relative_strength", raw.get("rs_rank"))
        if rs and (isinstance(rs, (int, float)) and rs > 0.7):
            evidence.append(Evidence(
                evidence_type=EvidenceType.RS_LEADERSHIP,
                description=f"Relative strength: {rs:.2f}",
                strength=min(rs, 1.0),
            ))

        # Catalyst
        catalyst = raw.get("catalyst")
        if catalyst:
            evidence.append(Evidence(
                evidence_type=EvidenceType.CATALYST_CONFIRMED,
                description=str(catalyst),
                strength=raw.get("catalyst_strength", 0.8),
            ))

        # Fundamental shift
        fund_change = raw.get("fundamental_shift")
        if fund_change:
            evidence.append(Evidence(
                evidence_type=EvidenceType.FUNDAMENTAL_SHIFT,
                description=str(fund_change),
                strength=0.7,
            ))

        # Regime alignment
        if raw.get("regime_aligned") or raw.get("trend_aligned"):
            evidence.append(Evidence(
                evidence_type=EvidenceType.REGIME_ALIGNMENT,
                description="Signal aligned with current regime",
                strength=0.6,
            ))

        return evidence

    def _build_next_step(
        self, raw: Dict[str, Any], action: ScannerAction
    ) -> Optional[NextStepTrigger]:
        """Build a clear next-step trigger."""
        # Price trigger
        if action in (ScannerAction.BUY, ScannerAction.ADD):
            entry_high = raw.get("entry_high", 0)
            if entry_high:
                return NextStepTrigger(
                    trigger_type="price_level",
                    description=f"Enter on pullback to ${entry_high:.2f} or below",
                    trigger_value=str(entry_high),
                    urgency="this_week",
                )

        if action == ScannerAction.WATCH:
            breakout = raw.get("breakout_level")
            if breakout:
                return NextStepTrigger(
                    trigger_type="price_level",
                    description=f"Watch for breakout above ${breakout:.2f}",
                    trigger_value=str(breakout),
                    urgency="this_week",
                )

        # Earnings trigger
        earnings_date = raw.get("earnings_date")
        if earnings_date:
            return NextStepTrigger(
                trigger_type="earnings",
                description=f"Earnings on {earnings_date} — reassess after",
                trigger_value=str(earnings_date),
                urgency="this_month",
            )

        # Regime trigger
        if action == ScannerAction.AVOID:
            return NextStepTrigger(
                trigger_type="regime_change",
                description="Re-evaluate if regime shifts to RISK_ON",
                trigger_value="RISK_ON",
                urgency="this_month",
            )

        return None
