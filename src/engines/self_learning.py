"""
Controlled Self-Learning Engine.

Implements safe, bounded self-learning for portfolio and rule tuning:

  1. Parameter sensitivity analysis — which rules have most impact
  2. Outcome-based rule adjustment — only after sufficient sample size
  3. Guardrails — max adjustment per cycle, no extreme values
  4. Audit trail — every adjustment logged with before/after
  5. Kill switch — disable auto-tuning at any time

Design principle: the system learns from outcomes but never
drifts beyond human-defined bounds. Every adjustment is reversible.
"""
from __future__ import annotations

import json
import logging
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

logger = logging.getLogger(__name__)

AUDIT_DIR = Path("models")
AUDIT_DIR.mkdir(exist_ok=True)


@dataclass
class RuleAdjustment:
    """A single rule parameter adjustment."""
    rule_name: str
    parameter: str
    old_value: float
    new_value: float
    reason: str
    confidence: float  # 0-1, how confident we are this helps
    sample_size: int  # how many outcomes informed this
    timestamp: str = ""
    applied: bool = False

    def to_dict(self) -> Dict[str, Any]:
        return {
            "rule_name": self.rule_name,
            "parameter": self.parameter,
            "old_value": self.old_value,
            "new_value": self.new_value,
            "reason": self.reason,
            "confidence": round(self.confidence, 2),
            "sample_size": self.sample_size,
            "timestamp": self.timestamp,
            "applied": self.applied,
        }


@dataclass
class LearningState:
    """Current state of the self-learning system."""
    enabled: bool = True
    total_adjustments: int = 0
    adjustments_this_cycle: int = 0
    max_adjustments_per_cycle: int = 3
    min_sample_size: int = 30  # minimum trades before tuning
    max_adjustment_pct: float = 0.15  # max 15% change per parameter per cycle
    last_cycle_timestamp: str = ""
    audit_log: List[Dict[str, Any]] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "enabled": self.enabled,
            "total_adjustments": self.total_adjustments,
            "adjustments_this_cycle": self.adjustments_this_cycle,
            "max_adjustments_per_cycle": self.max_adjustments_per_cycle,
            "min_sample_size": self.min_sample_size,
            "max_adjustment_pct": self.max_adjustment_pct,
            "last_cycle_timestamp": self.last_cycle_timestamp,
            "recent_adjustments": self.audit_log[-10:],
        }


# ── Tunable rules with bounds ──────────────────────────────────────

TUNABLE_RULES: Dict[str, Dict[str, Any]] = {
    "ensemble_min_score": {
        "description": "Minimum composite score to trade",
        "min": 0.20,
        "max": 0.50,
        "default": 0.35,
        "step": 0.02,
    },
    "signal_cooldown_hours": {
        "description": "Hours before same signal can re-fire",
        "min": 1,
        "max": 12,
        "default": 4,
        "step": 0.5,
    },
    "anti_flip_hours": {
        "description": "Hours before opposite direction allowed",
        "min": 2,
        "max": 16,
        "default": 6,
        "step": 1.0,
    },
    "max_position_pct": {
        "description": "Max single-name position size",
        "min": 0.02,
        "max": 0.10,
        "default": 0.05,
        "step": 0.005,
    },
    "stop_loss_pct": {
        "description": "Default stop loss percentage",
        "min": 0.01,
        "max": 0.08,
        "default": 0.03,
        "step": 0.005,
    },
    "trailing_stop_pct": {
        "description": "Trailing stop activation distance",
        "min": 0.01,
        "max": 0.05,
        "default": 0.02,
        "step": 0.005,
    },
}


class SelfLearningEngine:
    """
    Controlled self-learning for portfolio and rule tuning.

    Only adjusts parameters after:
      1. Sufficient sample size (min_sample_size trades)
      2. Clear statistical signal (win rate or expectancy deviation)
      3. Within guardrail bounds (max_adjustment_pct)
      4. Not exceeding max_adjustments_per_cycle
    """

    def __init__(self):
        self.state = LearningState()
        self._audit_path = AUDIT_DIR / "self_learning_audit.json"
        self._load_audit()

    def analyze_and_recommend(
        self,
        trade_outcomes: List[Dict[str, Any]],
        current_rules: Dict[str, float],
    ) -> List[RuleAdjustment]:
        """
        Analyze trade outcomes and recommend rule adjustments.

        Args:
            trade_outcomes: list of closed trade dicts with keys:
                strategy, pnl_pct, confidence, regime, exit_reason, etc.
            current_rules: current parameter values {rule_name: value}

        Returns:
            List of recommended adjustments (not yet applied)
        """
        if not self.state.enabled:
            return []

        if len(trade_outcomes) < self.state.min_sample_size:
            logger.info(
                "Self-learning: %d trades < %d minimum — no adjustments",
                len(trade_outcomes), self.state.min_sample_size,
            )
            return []

        recommendations: List[RuleAdjustment] = []

        # Analyze stop-loss effectiveness
        stop_adjustment = self._analyze_stop_loss(trade_outcomes, current_rules)
        if stop_adjustment:
            recommendations.append(stop_adjustment)

        # Analyze cooldown effectiveness
        cooldown_adjustment = self._analyze_cooldown(trade_outcomes, current_rules)
        if cooldown_adjustment:
            recommendations.append(cooldown_adjustment)

        # Analyze position sizing
        sizing_adjustment = self._analyze_position_sizing(trade_outcomes, current_rules)
        if sizing_adjustment:
            recommendations.append(sizing_adjustment)

        # Analyze ensemble threshold
        threshold_adjustment = self._analyze_ensemble_threshold(trade_outcomes, current_rules)
        if threshold_adjustment:
            recommendations.append(threshold_adjustment)

        # Apply guardrails
        recommendations = self._apply_guardrails(recommendations)

        # Limit per cycle
        recommendations = recommendations[:self.state.max_adjustments_per_cycle]

        return recommendations

    def apply_adjustments(
        self, adjustments: List[RuleAdjustment]
    ) -> List[RuleAdjustment]:
        """Apply approved adjustments, persist to config, and log them."""
        from src.core.config import save_trading_config_override

        applied = []
        for adj in adjustments:
            adj.timestamp = datetime.now(timezone.utc).isoformat()
            adj.applied = True
            self.state.total_adjustments += 1
            self.state.adjustments_this_cycle += 1
            self.state.audit_log.append(adj.to_dict())
            applied.append(adj)

            # Write-back: persist the new value so it survives restarts
            try:
                save_trading_config_override(adj.parameter, adj.new_value)
            except Exception as exc:
                logger.warning(
                    "Self-learning: failed to persist %s override: %s",
                    adj.parameter, exc,
                )

            logger.info(
                "Self-learning: %s.%s %s → %s (reason: %s, sample=%d)",
                adj.rule_name, adj.parameter,
                adj.old_value, adj.new_value,
                adj.reason, adj.sample_size,
            )
        self._save_audit()
        return applied

    def reset_cycle(self):
        """Reset per-cycle counters (call at start of new trading day)."""
        self.state.adjustments_this_cycle = 0
        self.state.last_cycle_timestamp = datetime.now(timezone.utc).isoformat()

    def disable(self):
        """Kill switch: disable all auto-tuning."""
        self.state.enabled = False
        logger.warning("Self-learning DISABLED by user")

    def enable(self):
        """Re-enable auto-tuning."""
        self.state.enabled = True
        logger.info("Self-learning re-enabled")

    # ── Analysis methods ──────────────────────────────────────────

    def _analyze_stop_loss(
        self, outcomes: List[Dict], rules: Dict[str, float]
    ) -> Optional[RuleAdjustment]:
        """Check if stops are too tight (many stop-outs that recover)."""
        stop_exits = [
            o for o in outcomes
            if o.get("exit_reason") in ("stop_hit", "trailing_stop", "sl_hit")
        ]
        if len(stop_exits) < 10:
            return None

        # Check if stopped-out trades would have recovered
        # (MAE analysis: if price went back above stop within 5 days)
        premature_stops = sum(
            1 for o in stop_exits
            if o.get("would_have_recovered", False)
        )
        premature_pct = premature_stops / len(stop_exits) * 100

        if premature_pct > 40:
            # Stops too tight — widen
            current = rules.get("stop_loss_pct", 0.03)
            rule = TUNABLE_RULES["stop_loss_pct"]
            new_val = min(rule["max"], current + rule["step"])
            if new_val != current:
                return RuleAdjustment(
                    rule_name="trading_config",
                    parameter="stop_loss_pct",
                    old_value=current,
                    new_value=new_val,
                    reason=f"Premature stop-outs: {premature_pct:.0f}% of stopped trades recovered",
                    confidence=min(0.8, premature_pct / 100),
                    sample_size=len(stop_exits),
                )

        return None

    def _analyze_cooldown(
        self, outcomes: List[Dict], rules: Dict[str, float]
    ) -> Optional[RuleAdjustment]:
        """Check if cooldown is too long (missing good re-entries)."""
        # Look for patterns where same ticker was re-signaled
        # but blocked by cooldown, then moved significantly
        cooldown_blocks = [
            o for o in outcomes
            if o.get("blocked_by_cooldown", False)
        ]
        if len(cooldown_blocks) < 5:
            return None

        missed_moves = sum(
            1 for o in cooldown_blocks
            if abs(o.get("missed_return_pct", 0)) > 3.0
        )
        if missed_moves > len(cooldown_blocks) * 0.5:
            current = rules.get("signal_cooldown_hours", 4)
            rule = TUNABLE_RULES["signal_cooldown_hours"]
            new_val = max(rule["min"], current - rule["step"])
            if new_val != current:
                return RuleAdjustment(
                    rule_name="trading_config",
                    parameter="signal_cooldown_hours",
                    old_value=current,
                    new_value=new_val,
                    reason=f"Cooldown blocking good re-entries: {missed_moves}/{len(cooldown_blocks)} missed >3% moves",
                    confidence=0.5,
                    sample_size=len(cooldown_blocks),
                )

        return None

    def _analyze_position_sizing(
        self, outcomes: List[Dict], rules: Dict[str, float]
    ) -> Optional[RuleAdjustment]:
        """Check if position sizing is suboptimal."""
        if len(outcomes) < 20:
            return None

        # Check if winning trades are undersized relative to losers
        wins = [o for o in outcomes if o.get("pnl_pct", 0) > 0]
        losses = [o for o in outcomes if o.get("pnl_pct", 0) <= 0]

        if not wins or not losses:
            return None

        avg_win = sum(o.get("pnl_pct", 0) for o in wins) / len(wins)
        avg_loss = abs(sum(o.get("pnl_pct", 0) for o in losses) / len(losses))

        # If avg_win/avg_loss < 1.5, winners are too small
        if avg_loss > 0 and avg_win / avg_loss < 1.0:
            # Suggest increasing position size for high-confidence trades
            current = rules.get("max_position_pct", 0.05)
            rule = TUNABLE_RULES["max_position_pct"]
            new_val = min(rule["max"], current + rule["step"])
            if new_val != current:
                return RuleAdjustment(
                    rule_name="trading_config",
                    parameter="max_position_pct",
                    old_value=current,
                    new_value=new_val,
                    reason=f"Win/loss ratio {avg_win/avg_loss:.2f} < 1.0 — winners undersized",
                    confidence=0.4,
                    sample_size=len(outcomes),
                )

        return None

    def _analyze_ensemble_threshold(
        self, outcomes: List[Dict], rules: Dict[str, float]
    ) -> Optional[RuleAdjustment]:
        """Check if ensemble threshold is too high or too low."""
        if len(outcomes) < 20:
            return None

        # Check win rate of trades near the threshold
        threshold = rules.get("ensemble_min_score", 0.35)
        near_threshold = [
            o for o in outcomes
            if abs(o.get("composite_score", 0.5) - threshold) < 0.1
        ]

        if len(near_threshold) < 10:
            return None

        win_rate = sum(
            1 for o in near_threshold if o.get("pnl_pct", 0) > 0
        ) / len(near_threshold)

        if win_rate > 0.65:
            # Threshold too high — lower it to capture more winners
            current = rules.get("ensemble_min_score", 0.35)
            rule = TUNABLE_RULES["ensemble_min_score"]
            new_val = max(rule["min"], current - rule["step"])
            if new_val != current:
                return RuleAdjustment(
                    rule_name="trading_config",
                    parameter="ensemble_min_score",
                    old_value=current,
                    new_value=new_val,
                    reason=f"Near-threshold win rate {win_rate:.0%} — threshold may be too restrictive",
                    confidence=0.5,
                    sample_size=len(near_threshold),
                )
        elif win_rate < 0.40:
            # Threshold too low — raise it
            current = rules.get("ensemble_min_score", 0.35)
            rule = TUNABLE_RULES["ensemble_min_score"]
            new_val = min(rule["max"], current + rule["step"])
            if new_val != current:
                return RuleAdjustment(
                    rule_name="trading_config",
                    parameter="ensemble_min_score",
                    old_value=current,
                    new_value=new_val,
                    reason=f"Near-threshold win rate {win_rate:.0%} — threshold may be too permissive",
                    confidence=0.5,
                    sample_size=len(near_threshold),
                )

        return None

    def _apply_guardrails(
        self, adjustments: List[RuleAdjustment]
    ) -> List[RuleAdjustment]:
        """Ensure adjustments stay within bounds."""
        approved = []
        for adj in adjustments:
            rule = TUNABLE_RULES.get(adj.parameter, {})
            max_pct = self.state.max_adjustment_pct

            old = adj.old_value
            new = adj.new_value
            if old != 0:
                change_pct = abs(new - old) / abs(old)
            else:
                change_pct = abs(new)

            if change_pct > max_pct:
                # Clamp to max adjustment
                if new > old:
                    adj.new_value = old * (1 + max_pct)
                else:
                    adj.new_value = old * (1 - max_pct)

            # Hard bounds
            adj.new_value = max(rule.get("min", 0), min(rule.get("max", 1), adj.new_value))

            if adj.new_value != adj.old_value:
                approved.append(adj)

        return approved

    # ── Persistence ────────────────────────────────────────────────

    def _save_audit(self):
        try:
            data = {
                "state": self.state.to_dict(),
                "audit_log": self.state.audit_log[-200:],
            }
            with open(self._audit_path, "w") as f:
                json.dump(data, f, indent=2, default=str)
        except Exception as e:
            logger.debug("Self-learning audit save error: %s", e)

    def _load_audit(self):
        if not self._audit_path.exists():
            return
        try:
            with open(self._audit_path, "r") as f:
                data = json.load(f)
            self.state.total_adjustments = data.get("state", {}).get("total_adjustments", 0)
            self.state.audit_log = data.get("audit_log", [])
        except Exception as e:
            logger.debug("Self-learning audit load error: %s", e)
