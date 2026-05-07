"""
Controlled Self-Learning Engine — Sprint 96 (upgraded from Sprint 49)
======================================================================
Implements safe, bounded self-learning for portfolio and rule tuning:

  1. Parameter sensitivity analysis — which rules have most impact
  2. Outcome-based rule adjustment — only after sufficient sample size
  3. Guardrails — max adjustment per cycle, no extreme values
  4. Audit trail — every adjustment logged with before/after
  5. Kill switch — disable auto-tuning at any time
  6. Regime-conditioned params — separate parameter sets per regime
  7. Fund weight auto-tuner — adjusts sleeve allocations by rolling Sharpe
  8. Learning loop integration — pull closed trades from LearningLoopPipeline

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
                len(trade_outcomes),
                self.state.min_sample_size,
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
        threshold_adjustment = self._analyze_ensemble_threshold(
            trade_outcomes, current_rules
        )
        if threshold_adjustment:
            recommendations.append(threshold_adjustment)

        # Apply guardrails
        recommendations = self._apply_guardrails(recommendations)

        # Limit per cycle
        recommendations = recommendations[: self.state.max_adjustments_per_cycle]

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
                    adj.parameter,
                    exc,
                )

            logger.info(
                "Self-learning: %s.%s %s → %s (reason: %s, sample=%d)",
                adj.rule_name,
                adj.parameter,
                adj.old_value,
                adj.new_value,
                adj.reason,
                adj.sample_size,
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
            o
            for o in outcomes
            if o.get("exit_reason") in ("stop_hit", "trailing_stop", "sl_hit")
        ]
        if len(stop_exits) < 10:
            return None

        # Check if stopped-out trades would have recovered
        # (MAE analysis: if price went back above stop within 5 days)
        premature_stops = sum(
            1 for o in stop_exits if o.get("would_have_recovered", False)
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
        cooldown_blocks = [o for o in outcomes if o.get("blocked_by_cooldown", False)]
        if len(cooldown_blocks) < 5:
            return None

        missed_moves = sum(
            1 for o in cooldown_blocks if abs(o.get("missed_return_pct", 0)) > 3.0
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
            o for o in outcomes if abs(o.get("composite_score", 0.5) - threshold) < 0.1
        ]

        if len(near_threshold) < 10:
            return None

        win_rate = sum(1 for o in near_threshold if o.get("pnl_pct", 0) > 0) / len(
            near_threshold
        )

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
            adj.new_value = max(
                rule.get("min", 0), min(rule.get("max", 1), adj.new_value)
            )

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
            self.state.total_adjustments = data.get("state", {}).get(
                "total_adjustments", 0
            )
            self.state.audit_log = data.get("audit_log", [])
        except Exception as e:
            logger.debug("Self-learning audit load error: %s", e)


# ── Regime-conditioned parameter store ──────────────────────────────────────

_DEFAULT_REGIME_PARAMS: Dict[str, Dict[str, float]] = {
    "BULL": {
        "ensemble_min_score": 0.33,
        "stop_loss_pct": 0.03,
        "max_position_pct": 0.06,
        "signal_cooldown_hours": 3.0,
    },
    "BEAR": {
        "ensemble_min_score": 0.42,
        "stop_loss_pct": 0.025,
        "max_position_pct": 0.035,
        "signal_cooldown_hours": 6.0,
    },
    "SIDEWAYS": {
        "ensemble_min_score": 0.38,
        "stop_loss_pct": 0.03,
        "max_position_pct": 0.05,
        "signal_cooldown_hours": 4.0,
    },
    "CHOPPY": {
        "ensemble_min_score": 0.45,
        "stop_loss_pct": 0.02,
        "max_position_pct": 0.025,
        "signal_cooldown_hours": 8.0,
    },
}

_REGIME_PARAMS_FILE = AUDIT_DIR / "regime_params.json"


def load_regime_params() -> Dict[str, Dict[str, float]]:
    """Load regime-conditioned parameters from disk, falling back to defaults."""
    if not _REGIME_PARAMS_FILE.exists():
        return dict(_DEFAULT_REGIME_PARAMS)
    try:
        with open(_REGIME_PARAMS_FILE, "r") as f:
            stored = json.load(f)
        # Merge stored over defaults so new regimes always have values
        merged = dict(_DEFAULT_REGIME_PARAMS)
        for regime, params in stored.items():
            merged[regime] = {**merged.get(regime, {}), **params}
        return merged
    except Exception as e:
        logger.debug("Regime params load error: %s", e)
        return dict(_DEFAULT_REGIME_PARAMS)


def save_regime_params(params: Dict[str, Dict[str, float]]) -> None:
    try:
        with open(_REGIME_PARAMS_FILE, "w") as f:
            json.dump(params, f, indent=2)
    except Exception as e:
        logger.debug("Regime params save error: %s", e)


def get_params_for_regime(regime: str) -> Dict[str, float]:
    """Return the best known parameter set for the given regime."""
    all_params = load_regime_params()
    normalised = regime.upper().replace("_TRENDING", "").replace("BULL", "BULL")
    # Fuzzy match: bull_trending → BULL, bear_trending → BEAR
    for key in all_params:
        if normalised.startswith(key):
            return all_params[key]
    return all_params.get("SIDEWAYS", {})


# ── Fund weight auto-tuner ───────────────────────────────────────────────────

_FUND_WEIGHTS_FILE = AUDIT_DIR / "fund_weights.json"

# Default equal-weight allocation across the 4 sleeves
_DEFAULT_FUND_WEIGHTS: Dict[str, float] = {
    "FUND_ALPHA": 0.25,
    "FUND_PENDA": 0.25,
    "FUND_CAT": 0.25,
    "FUND_MACRO": 0.25,
}

# Bounds: no single fund can dominate or be zeroed out
_FUND_WEIGHT_MIN = 0.10
_FUND_WEIGHT_MAX = 0.50


def load_fund_weights() -> Dict[str, float]:
    if not _FUND_WEIGHTS_FILE.exists():
        return dict(_DEFAULT_FUND_WEIGHTS)
    try:
        with open(_FUND_WEIGHTS_FILE, "r") as f:
            w = json.load(f)
        # Normalise so weights sum to 1.0
        total = sum(w.values())
        if total <= 0:
            return dict(_DEFAULT_FUND_WEIGHTS)
        return {k: round(v / total, 4) for k, v in w.items()}
    except Exception:
        return dict(_DEFAULT_FUND_WEIGHTS)


def tune_fund_weights(
    fund_metrics: List[Dict[str, Any]],
    learning_rate: float = 0.10,
) -> Dict[str, float]:
    """
    Adjust fund sleeve allocation weights proportional to rolling Sharpe.

    fund_metrics: list of dicts with keys "name" and "metrics.sharpe"
    learning_rate: fraction of current weight to shift (0.10 = 10% nudge)

    Returns new normalised weights (saved to disk).
    """
    current = load_fund_weights()

    sharpes: Dict[str, float] = {}
    for fm in fund_metrics:
        name = fm.get("name", "")
        sharpe = float(fm.get("metrics", {}).get("sharpe", 0.0))
        if name and name in current:
            sharpes[name] = max(sharpe, 0.0)  # floor at 0 to avoid punishing all

    if not sharpes or sum(sharpes.values()) == 0:
        return current  # no signal, keep as-is

    # Proportional target weights from Sharpe
    total_sharpe = sum(sharpes.values())
    target: Dict[str, float] = {k: sharpes.get(k, 0.0) / total_sharpe for k in current}

    # Blend: new = current + learning_rate * (target - current)
    new_weights: Dict[str, float] = {}
    for k in current:
        nudged = current[k] + learning_rate * (target.get(k, current[k]) - current[k])
        new_weights[k] = max(_FUND_WEIGHT_MIN, min(_FUND_WEIGHT_MAX, nudged))

    # Re-normalise
    total = sum(new_weights.values())
    normalised = {k: round(v / total, 4) for k, v in new_weights.items()}

    save_fund_weights(normalised)
    logger.info("Fund weights auto-tuned: %s", normalised)
    return normalised


def save_fund_weights(weights: Dict[str, float]) -> None:
    try:
        with open(_FUND_WEIGHTS_FILE, "w") as f:
            json.dump(weights, f, indent=2)
    except Exception as e:
        logger.debug("Fund weights save error: %s", e)


# ── Regime performance analyser ─────────────────────────────────────────────


def analyze_regime_performance(
    trade_outcomes: List[Dict[str, Any]],
) -> Dict[str, Dict[str, Any]]:
    """
    Aggregate win-rate and expectancy per regime from closed trade outcomes.

    Returns:
        {
          "BULL": {"win_rate": 0.62, "avg_pnl": 1.8, "sample": 45},
          "BEAR": {...},
          ...
        }
    """
    by_regime: Dict[str, List[float]] = {}
    for t in trade_outcomes:
        regime = (t.get("regime") or "UNKNOWN").upper()
        regime = regime.replace("_TRENDING", "").split("_")[0]
        pnl = float(t.get("pnl_pct", 0.0))
        by_regime.setdefault(regime, []).append(pnl)

    result: Dict[str, Dict[str, Any]] = {}
    for regime, pnls in by_regime.items():
        wins = sum(1 for p in pnls if p > 0)
        result[regime] = {
            "win_rate": round(wins / len(pnls), 3) if pnls else 0.0,
            "avg_pnl": round(sum(pnls) / len(pnls), 2) if pnls else 0.0,
            "avg_win": round(sum(p for p in pnls if p > 0) / max(wins, 1), 2),
            "avg_loss": round(
                sum(abs(p) for p in pnls if p <= 0) / max(len(pnls) - wins, 1), 2
            ),
            "sample": len(pnls),
        }
    return result


# ── Learning loop integration helper ────────────────────────────────────────


def pull_closed_trades_from_learning_loop() -> List[Dict[str, Any]]:
    """
    Pull closed trades from LearningLoopPipeline for use in SelfLearningEngine.

    Returns list of trade dicts compatible with analyze_and_recommend().
    """
    try:
        from src.engines.learning_loop import LearningLoopPipeline

        pipeline = LearningLoopPipeline()
        return [t.to_dict() for t in pipeline._closed_trades]
    except Exception as e:
        logger.debug("Could not pull trades from LearningLoopPipeline: %s", e)
        return []


# ── Per-regime parameter auto-adjuster ──────────────────────────────────────

# How aggressively to tighten/loosen params based on win-rate deviation from 50%
_REGIME_TUNE_LEARNING_RATE = 0.08  # 8% nudge per cycle
_REGIME_MIN_SAMPLE = 15  # minimum trades per regime before tuning

# Which params to auto-tune per regime and in which direction
_REGIME_PARAM_DIRECTION: Dict[str, Dict[str, str]] = {
    # When win-rate is LOW → tighten (raise threshold, lower size, raise stop)
    # When win-rate is HIGH → relax (lower threshold, raise size)
    "ensemble_min_score": {"low_wr": "raise", "high_wr": "lower"},
    "max_position_pct": {"low_wr": "lower", "high_wr": "raise"},
    "stop_loss_pct": {"low_wr": "lower", "high_wr": "raise"},
}


def tune_regime_params(
    trade_outcomes: List[Dict[str, Any]],
    learning_rate: float = _REGIME_TUNE_LEARNING_RATE,
    min_sample: int = _REGIME_MIN_SAMPLE,
) -> Dict[str, Dict[str, Any]]:
    """
    Auto-adjust per-regime parameters based on observed win-rates.

    Logic per regime:
      - win_rate < 0.45 → tighten (raise score threshold, lower position size, tighten stop)
      - win_rate > 0.60 → relax  (lower score threshold, raise position size)
      - 0.45–0.60      → no change

    Returns a dict of {regime: {param: {"old": x, "new": y, "reason": "..."}}}
    """
    perf = analyze_regime_performance(trade_outcomes)
    current_all = load_regime_params()
    changes: Dict[str, Dict[str, Any]] = {}

    for regime, stats in perf.items():
        sample = stats.get("sample", 0)
        if sample < min_sample:
            continue

        win_rate = stats.get("win_rate", 0.5)
        current = current_all.get(
            regime, dict(_DEFAULT_REGIME_PARAMS.get("SIDEWAYS", {}))
        )
        regime_changes: Dict[str, Any] = {}

        for param, directions in _REGIME_PARAM_DIRECTION.items():
            rule = TUNABLE_RULES.get(param, {})
            old_val = current.get(param, rule.get("default", 0.0))
            step = rule.get("step", 0.005)

            if win_rate < 0.45:
                # tighten
                direction = directions["low_wr"]
            elif win_rate > 0.60:
                # relax
                direction = directions["high_wr"]
            else:
                continue  # no change needed

            nudge = step * max(1, round(abs(win_rate - 0.50) / step))
            nudge = min(
                nudge, old_val * learning_rate
            )  # cap at learning_rate% of current

            new_val = old_val + nudge if direction == "raise" else old_val - nudge
            new_val = max(rule.get("min", 0.0), min(rule.get("max", 1.0), new_val))
            new_val = round(new_val, 4)

            if new_val != old_val:
                regime_changes[param] = {
                    "old": old_val,
                    "new": new_val,
                    "reason": f"win_rate={win_rate:.0%} (n={sample}) → {direction} {param}",
                }
                current[param] = new_val

        if regime_changes:
            current_all[regime] = current
            changes[regime] = regime_changes

    if changes:
        save_regime_params(current_all)
        logger.info("Regime params auto-tuned for: %s", list(changes.keys()))

        # Auto-propose A/B shadow for params that shifted > 5% of their old value
        try:
            for regime_changes in changes.values():
                for param, chg in regime_changes.items():
                    old_val = chg.get("old", 0)
                    new_val = chg.get("new", 0)
                    if old_val and abs(new_val - old_val) / abs(old_val) > 0.05:
                        propose_ab_shadow(param, new_val)
                        logger.info(
                            "[AB-AutoPropose] param=%s old=%.4f new=%.4f (>5%% shift)",
                            param,
                            old_val,
                            new_val,
                        )
        except Exception as e:
            logger.debug("A/B auto-propose error (non-fatal): %s", e)

    return changes


# ── Brier score calibration tracker ─────────────────────────────────────────

_BRIER_FILE = AUDIT_DIR / "brier_scores.json"
_BRIER_DRIFT_THRESHOLD = 0.05  # alert if Brier score degrades by >5%
_BRIER_WINDOW = 50  # rolling window of predictions


def record_prediction_outcome(
    confidence: float,
    actual_win: bool,
    strategy: str = "",
    forward_return_pct: float = 0.0,
    mae_pct: float = 0.0,
    regime: str = "",
) -> Dict[str, Any]:
    """
    Record one (confidence, outcome) pair and compute rolling Brier score.

    Brier score = mean((forecast_prob - actual_outcome)²)
    Lower is better (0 = perfect, 0.25 = random).

    Sprint 110 additions:
    - ``forward_return_pct`` — actual forward return (positive = profit)
    - ``mae_pct`` — maximum adverse excursion as positive pct
    - ``regime`` — regime label at time of trade (BULL/BEAR/etc.)
    - Stored in ``data["history"]`` entries for bucket analysis

    Returns {"brier_score": float, "window": int, "drift": float, "alert": bool}
    """
    data = _load_brier_data()
    entry: Dict[str, Any] = {"conf": round(confidence, 4), "win": int(actual_win)}
    if forward_return_pct != 0.0:
        entry["fwd_ret"] = round(forward_return_pct, 4)
    if mae_pct != 0.0:
        entry["mae"] = round(mae_pct, 4)
    if regime:
        entry["regime"] = regime.upper().strip()
    data["history"].append(entry)
    # Keep only last _BRIER_WINDOW entries
    data["history"] = data["history"][-_BRIER_WINDOW:]

    # ── Per-strategy tracking ──
    if strategy:
        bucket = strategy.upper().strip()
        by_strat = data.setdefault("by_strategy", {})
        strat_hist = by_strat.setdefault(bucket, [])
        strat_hist.append(entry)
        by_strat[bucket] = strat_hist[-_BRIER_WINDOW:]

    history = data["history"]
    n = len(history)
    if n < 5:
        _save_brier_data(data)
        return {"brier_score": None, "window": n, "drift": 0.0, "alert": False}

    brier = sum((e["conf"] - e["win"]) ** 2 for e in history) / n
    brier = round(brier, 4)

    # Detect drift: compare current score vs baseline (first half of window)
    baseline = data.get("baseline_brier")
    drift = 0.0
    alert = False
    if baseline is None and n >= _BRIER_WINDOW:
        # Establish baseline once we have a full window
        data["baseline_brier"] = brier
        baseline = brier
    elif baseline is not None:
        drift = round(brier - baseline, 4)
        alert = drift > _BRIER_DRIFT_THRESHOLD

    data["latest_brier"] = brier
    data["latest_n"] = n
    _save_brier_data(data)

    if alert:
        logger.warning(
            "CALIBRATION DRIFT: Brier score %.4f vs baseline %.4f (drift +%.4f > %.4f threshold)",
            brier,
            baseline,
            drift,
            _BRIER_DRIFT_THRESHOLD,
        )

    return {
        "brier_score": brier,
        "baseline": baseline,
        "window": n,
        "drift": drift,
        "alert": alert,
    }


def get_calibration_status() -> Dict[str, Any]:
    """Return current Brier score status, drift alert, and per-strategy breakdown."""
    data = _load_brier_data()
    history = data.get("history", [])
    n = len(history)
    brier = data.get("latest_brier")
    baseline = data.get("baseline_brier")
    drift = (
        round((brier - baseline), 4)
        if (brier is not None and baseline is not None)
        else 0.0
    )

    # Per-strategy decomposition
    by_strategy: Dict[str, Any] = {}
    for strat, hist in data.get("by_strategy", {}).items():
        m = len(hist)
        if m < 3:
            by_strategy[strat] = {"brier_score": None, "window": m}
            continue
        s_brier = round(sum((e["conf"] - e["win"]) ** 2 for e in hist) / m, 4)
        by_strategy[strat] = {"brier_score": s_brier, "window": m}

    return {
        "brier_score": brier,
        "baseline_brier": baseline,
        "drift": drift,
        "alert": drift > _BRIER_DRIFT_THRESHOLD if brier is not None else False,
        "window": n,
        "status": (
            "ok"
            if (brier is None or drift <= _BRIER_DRIFT_THRESHOLD)
            else "drift_detected"
        ),
        "by_strategy": by_strategy,
    }


# Sprint 110 — Confidence calibration bucket report
_CONF_BUCKETS = [
    ("50-60", 0.50, 0.60),
    ("60-70", 0.60, 0.70),
    ("70-80", 0.70, 0.80),
    ("80-90", 0.80, 0.90),
    ("90+", 0.90, 1.01),
]


def get_calibration_buckets() -> Dict[str, Any]:
    """
    Sprint 110: Group calibration history into confidence buckets and compute
    per-bucket hit_rate, avg_forward_return, avg_mae, and regime breakdown.

    Returns dict with:
      - ``buckets``: list of bucket dicts ordered 50-60 … 90+
      - ``total_records``: total trades with confidence data
      - ``calibration_quality``: overall ECE (Expected Calibration Error)
    """
    data = _load_brier_data()
    history = data.get("history", [])

    bucket_stats: Dict[str, Any] = {}
    for label, lo, hi in _CONF_BUCKETS:
        bucket_stats[label] = {
            "label": label,
            "lo": lo,
            "hi": hi,
            "n": 0,
            "wins": 0,
            "sum_fwd_ret": 0.0,
            "sum_mae": 0.0,
            "n_fwd": 0,
            "n_mae": 0,
            "regimes": {},
        }

    for e in history:
        conf = e.get("conf", 0.0)
        win = int(e.get("win", 0))
        fwd = e.get("fwd_ret")
        mae = e.get("mae")
        regime = e.get("regime", "UNKNOWN")

        for label, lo, hi in _CONF_BUCKETS:
            if lo <= conf < hi:
                b = bucket_stats[label]
                b["n"] += 1
                b["wins"] += win
                if fwd is not None:
                    b["sum_fwd_ret"] += fwd
                    b["n_fwd"] += 1
                if mae is not None:
                    b["sum_mae"] += mae
                    b["n_mae"] += 1
                # Regime breakdown
                r_key = regime or "UNKNOWN"
                rb = b["regimes"].setdefault(r_key, {"n": 0, "wins": 0})
                rb["n"] += 1
                rb["wins"] += win
                break

    buckets_out = []
    ece_sum = 0.0
    ece_n = 0
    for label, lo, hi in _CONF_BUCKETS:
        b = bucket_stats[label]
        n = b["n"]
        midpoint = (lo + hi) / 2 if hi < 1.01 else 0.95
        hit_rate = round(b["wins"] / n, 4) if n > 0 else None
        avg_fwd = round(b["sum_fwd_ret"] / b["n_fwd"], 4) if b["n_fwd"] > 0 else None
        avg_mae = round(b["sum_mae"] / b["n_mae"], 4) if b["n_mae"] > 0 else None

        # Calibration status: is hit_rate close to midpoint conf?
        calibrated = None
        if hit_rate is not None and n >= 5:
            gap = abs(hit_rate - midpoint)
            calibrated = "good" if gap < 0.08 else ("fair" if gap < 0.15 else "poor")
            ece_sum += gap * n
            ece_n += n

        # Regime hit-rates
        regime_summary = {}
        for r_key, rb in b["regimes"].items():
            regime_summary[r_key] = {
                "n": rb["n"],
                "hit_rate": round(rb["wins"] / rb["n"], 3) if rb["n"] > 0 else None,
            }

        buckets_out.append(
            {
                "bucket": label,
                "n": n,
                "midpoint_conf": round(midpoint, 2),
                "hit_rate": hit_rate,
                "avg_forward_return_pct": avg_fwd,
                "avg_mae_pct": avg_mae,
                "calibrated": calibrated,
                "regime_breakdown": regime_summary,
            }
        )

    ece = round(ece_sum / ece_n, 4) if ece_n > 0 else None
    return {
        "buckets": buckets_out,
        "total_records": len(history),
        "ece": ece,
        "note": "ECE = Expected Calibration Error (lower=better). Buckets need n≥5 for calibration judgement.",
    }


def _load_brier_data() -> Dict[str, Any]:
    if not _BRIER_FILE.exists():
        return {"history": [], "baseline_brier": None, "latest_brier": None}
    try:
        with open(_BRIER_FILE, "r") as f:
            return json.load(f)
    except Exception:
        return {"history": [], "baseline_brier": None, "latest_brier": None}


def _save_brier_data(data: Dict[str, Any]) -> None:
    try:
        AUDIT_DIR.mkdir(exist_ok=True)
        with open(_BRIER_FILE, "w") as f:
            json.dump(data, f, indent=2)
    except Exception as e:
        logger.debug("Brier data save error: %s", e)


# ── A/B shadow parameter harness ─────────────────────────────────────────────

_AB_FILE = AUDIT_DIR / "ab_shadow.json"
_AB_MIN_DAYS = 3  # minimum days before promoting shadow params


def propose_ab_shadow(
    param: str,
    challenger_value: float,
    reason: str = "",
) -> Dict[str, Any]:
    """
    Propose a challenger parameter value for A/B shadow testing.

    The challenger is paper-tracked for _AB_MIN_DAYS days before
    being eligible for promotion to live params.

    Returns the current A/B state dict.
    """
    data = _load_ab_data()
    now = datetime.now(timezone.utc).isoformat()
    rule = TUNABLE_RULES.get(param, {})
    champion = data.get("champion", {}).get(
        param, rule.get("default", challenger_value)
    )

    data.setdefault("challenger", {})[param] = {
        "value": challenger_value,
        "champion_value": champion,
        "reason": reason,
        "proposed_at": now,
        "days_tracked": 0,
        "shadow_wins": 0,
        "shadow_trades": 0,
        "status": "shadow",
    }
    _save_ab_data(data)
    logger.info(
        "A/B shadow: proposed %s=%.4f (champion=%.4f) — %s",
        param,
        challenger_value,
        champion,
        reason,
    )
    return data["challenger"][param]


def record_ab_outcome(
    param: str,
    used_challenger: bool,
    pnl_pct: float,
) -> None:
    """Record one trade outcome for the A/B shadow harness."""
    data = _load_ab_data()
    challenger = data.get("challenger", {}).get(param)
    if challenger is None or challenger.get("status") != "shadow":
        return

    challenger["shadow_trades"] = challenger.get("shadow_trades", 0) + 1
    if pnl_pct > 0 and used_challenger:
        challenger["shadow_wins"] = challenger.get("shadow_wins", 0) + 1

    # Advance day counter (simplified: count every 10 trades as ~1 day)
    if challenger["shadow_trades"] % 10 == 0:
        challenger["days_tracked"] = challenger.get("days_tracked", 0) + 1

    data["challenger"][param] = challenger
    _save_ab_data(data)


def evaluate_ab_promotion(param: str) -> Dict[str, Any]:
    """
    Evaluate whether to promote the challenger to champion.

    Promotes if:
      - days_tracked >= _AB_MIN_DAYS
      - challenger win_rate >= champion proxy win_rate (assumed 0.50)

    Returns {"promoted": bool, "reason": str, "new_value": float|None}
    """
    data = _load_ab_data()
    challenger = data.get("challenger", {}).get(param)
    if challenger is None:
        return {"promoted": False, "reason": "no challenger"}

    days = challenger.get("days_tracked", 0)
    trades = challenger.get("shadow_trades", 0)
    wins = challenger.get("shadow_wins", 0)
    win_rate = wins / trades if trades > 0 else 0.0

    if days < _AB_MIN_DAYS:
        return {"promoted": False, "reason": f"only {days}/{_AB_MIN_DAYS} days tracked"}

    if win_rate >= 0.52:
        # Promote: write challenger value to regime_params champion
        challenger["status"] = "promoted"
        challenger["promoted_at"] = datetime.now(timezone.utc).isoformat()
        data.setdefault("champion", {})[param] = challenger["value"]
        data["challenger"][param] = challenger
        _save_ab_data(data)
        # Also persist to regime params (default / all regimes)
        all_params = load_regime_params()
        for regime_key in all_params:
            if param in all_params[regime_key]:
                all_params[regime_key][param] = challenger["value"]
        save_regime_params(all_params)
        logger.info(
            "A/B PROMOTED: %s=%.4f (win_rate=%.0%%, n=%d)",
            param,
            challenger["value"],
            win_rate,
            trades,
        )
        return {
            "promoted": True,
            "reason": f"win_rate={win_rate:.0%} >= 52% over {days} days",
            "new_value": challenger["value"],
        }

    # Not ready — keep shadowing
    return {"promoted": False, "reason": f"win_rate={win_rate:.0%} < 52% (n={trades})"}


def get_ab_status() -> Dict[str, Any]:
    """Return current A/B shadow state for all tracked params."""
    data = _load_ab_data()
    challengers = data.get("challenger", {})
    champions = data.get("champion", {})
    return {
        "challengers": challengers,
        "champions": champions,
        "active": [p for p, v in challengers.items() if v.get("status") == "shadow"],
    }


def _load_ab_data() -> Dict[str, Any]:
    if not _AB_FILE.exists():
        return {"challenger": {}, "champion": {}}
    try:
        with open(_AB_FILE, "r") as f:
            return json.load(f)
    except Exception:
        return {"challenger": {}, "champion": {}}


def _save_ab_data(data: Dict[str, Any]) -> None:
    try:
        AUDIT_DIR.mkdir(exist_ok=True)
        with open(_AB_FILE, "w") as f:
            json.dump(data, f, indent=2, default=str)
    except Exception as e:
        logger.debug("A/B data save error: %s", e)
