"""
Keep / Discard Strategy Evaluator — Sprint 73
================================================
Fixed evaluator + mutable strategy config = controlled self-improvement.

Rules:
  - Evaluator is LOCKED. AI cannot change it.
  - Strategy config (weights, caps, stops) is MUTABLE.
  - Every experiment is logged with before/after.
  - Keep best variant, discard weak ones.

Score formula (fixed):
  0.35 * outperformance_vs_benchmark
  0.20 * sharpe_ratio
  0.15 * max_drawdown_penalty
  0.15 * turnover_penalty
  0.15 * stability_score
"""

from __future__ import annotations

import json
import logging
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)

EXPERIMENT_DIR = Path("data/experiments")
EXPERIMENT_DIR.mkdir(parents=True, exist_ok=True)


# ── Strategy Variant (MUTABLE) ──────────────────────────────────────────────

@dataclass
class StrategyVariant:
    """
    The mutable part — AI can change these parameters.
    Everything else stays locked.
    """
    name: str = "baseline"
    version: int = 1

    # Ranking weights (must sum to 1.0)
    w_rs_quality: float = 0.30
    w_trend: float = 0.20
    w_sector: float = 0.15
    w_setup: float = 0.15
    w_liquidity: float = 0.10
    w_tradeability: float = 0.10

    # Position rules
    max_positions: int = 10
    max_single_pct: float = 0.10
    max_sector_pct: float = 0.30

    # Stop/exit rules
    stop_atr_multiple: float = 2.0
    trail_after_r: float = 1.0
    take_profit_r: float = 3.0

    # Entry filters
    min_rs_composite: float = 105.0
    min_confidence: int = 60
    min_rr_ratio: float = 2.0

    # Rebalance
    rebalance_days: int = 5

    def to_dict(self) -> Dict[str, Any]:
        return {
            "name": self.name, "version": self.version,
            "weights": {
                "rs_quality": self.w_rs_quality, "trend": self.w_trend,
                "sector": self.w_sector, "setup": self.w_setup,
                "liquidity": self.w_liquidity, "tradeability": self.w_tradeability,
            },
            "position_rules": {
                "max_positions": self.max_positions,
                "max_single_pct": self.max_single_pct,
                "max_sector_pct": self.max_sector_pct,
            },
            "stop_rules": {
                "stop_atr_multiple": self.stop_atr_multiple,
                "trail_after_r": self.trail_after_r,
                "take_profit_r": self.take_profit_r,
            },
            "entry_filters": {
                "min_rs_composite": self.min_rs_composite,
                "min_confidence": self.min_confidence,
                "min_rr_ratio": self.min_rr_ratio,
            },
            "rebalance_days": self.rebalance_days,
        }

    def save(self, path: Optional[Path] = None) -> None:
        p = path or EXPERIMENT_DIR / f"variant_{self.name}_v{self.version}.json"
        p.write_text(json.dumps(self.to_dict(), indent=2))

    @classmethod
    def load(cls, path: Path) -> "StrategyVariant":
        data = json.loads(path.read_text())
        v = cls(name=data.get("name", ""), version=data.get("version", 1))
        w = data.get("weights", {})
        v.w_rs_quality = w.get("rs_quality", 0.30)
        v.w_trend = w.get("trend", 0.20)
        v.w_sector = w.get("sector", 0.15)
        v.w_setup = w.get("setup", 0.15)
        v.w_liquidity = w.get("liquidity", 0.10)
        v.w_tradeability = w.get("tradeability", 0.10)
        pr = data.get("position_rules", {})
        v.max_positions = pr.get("max_positions", 10)
        v.max_single_pct = pr.get("max_single_pct", 0.10)
        v.max_sector_pct = pr.get("max_sector_pct", 0.30)
        sr = data.get("stop_rules", {})
        v.stop_atr_multiple = sr.get("stop_atr_multiple", 2.0)
        v.trail_after_r = sr.get("trail_after_r", 1.0)
        v.take_profit_r = sr.get("take_profit_r", 3.0)
        ef = data.get("entry_filters", {})
        v.min_rs_composite = ef.get("min_rs_composite", 105.0)
        v.min_confidence = ef.get("min_confidence", 60)
        v.min_rr_ratio = ef.get("min_rr_ratio", 2.0)
        v.rebalance_days = data.get("rebalance_days", 5)
        return v


# ── Experiment Result ────────────────────────────────────────────────────────

@dataclass
class ExperimentResult:
    """Result of evaluating one strategy variant."""
    variant_name: str = ""
    variant_version: int = 0
    # Raw metrics
    total_return_pct: float = 0.0
    benchmark_return_pct: float = 0.0
    outperformance: float = 0.0
    sharpe: float = 0.0
    max_drawdown_pct: float = 0.0
    turnover: float = 0.0   # trades per month
    stability: float = 0.0  # rolling sharpe consistency
    # Composite score (from fixed evaluator)
    score: float = 0.0
    # Verdict
    verdict: str = "PENDING"   # KEEP / DISCARD / BASELINE
    reason: str = ""
    evaluated_at: str = ""

    def to_dict(self) -> Dict[str, Any]:
        return {
            "variant": f"{self.variant_name}_v{self.variant_version}",
            "total_return_pct": self.total_return_pct,
            "benchmark_return_pct": self.benchmark_return_pct,
            "outperformance": self.outperformance,
            "sharpe": self.sharpe,
            "max_drawdown_pct": self.max_drawdown_pct,
            "turnover": self.turnover,
            "stability": self.stability,
            "score": round(self.score, 2),
            "verdict": self.verdict,
            "reason": self.reason,
            "evaluated_at": self.evaluated_at,
        }


# ── Fixed Evaluator (LOCKED — do not modify) ────────────────────────────────

class StrategyEvaluator:
    """
    LOCKED evaluator. AI must NOT modify this scoring function.
    Only the StrategyVariant config is mutable.

    Score = weighted composite of 5 factors:
      0.35 * outperformance_vs_benchmark (normalized 0-100)
      0.20 * sharpe_ratio (normalized 0-100)
      0.15 * drawdown_penalty (inverted, 0-100)
      0.15 * turnover_penalty (inverted, 0-100)
      0.15 * stability_score (0-100)
    """

    # DO NOT CHANGE THESE WEIGHTS
    W_OUTPERFORMANCE = 0.35
    W_SHARPE = 0.20
    W_DRAWDOWN = 0.15
    W_TURNOVER = 0.15
    W_STABILITY = 0.15

    def evaluate(
        self,
        variant: StrategyVariant,
        total_return: float,
        benchmark_return: float,
        sharpe: float,
        max_drawdown: float,
        turnover: float,
        stability: float,
    ) -> ExperimentResult:
        """Score a strategy variant. Returns ExperimentResult."""
        outperf = total_return - benchmark_return

        # Normalize each factor to 0-100
        outperf_score = min(100, max(0, (outperf + 10) * 5))   # -10% → 0, +10% → 100
        sharpe_score = min(100, max(0, sharpe * 33))             # 0 → 0, 3 → 100
        dd_score = min(100, max(0, 100 - abs(max_drawdown) * 3))  # 0% → 100, 33% → 0
        turn_score = min(100, max(0, 100 - turnover * 10))       # 0/mo → 100, 10/mo → 0
        stab_score = min(100, max(0, stability))                  # already 0-100

        score = (
            self.W_OUTPERFORMANCE * outperf_score
            + self.W_SHARPE * sharpe_score
            + self.W_DRAWDOWN * dd_score
            + self.W_TURNOVER * turn_score
            + self.W_STABILITY * stab_score
        )

        result = ExperimentResult(
            variant_name=variant.name,
            variant_version=variant.version,
            total_return_pct=total_return,
            benchmark_return_pct=benchmark_return,
            outperformance=round(outperf, 2),
            sharpe=sharpe,
            max_drawdown_pct=max_drawdown,
            turnover=turnover,
            stability=stability,
            score=score,
            evaluated_at=datetime.now(timezone.utc).isoformat(),
        )

        return result

    def compare(
        self,
        baseline: ExperimentResult,
        candidate: ExperimentResult,
        min_improvement: float = 3.0,
    ) -> ExperimentResult:
        """
        Compare candidate vs baseline.
        Keep only if score improves by at least min_improvement points.
        """
        delta = candidate.score - baseline.score

        if delta >= min_improvement:
            candidate.verdict = "KEEP"
            candidate.reason = f"Score improved by {delta:.1f} (baseline {baseline.score:.1f} → {candidate.score:.1f})"
        elif delta > -min_improvement:
            candidate.verdict = "DISCARD"
            candidate.reason = f"Marginal change ({delta:+.1f}), not enough to justify switch"
        else:
            candidate.verdict = "DISCARD"
            candidate.reason = f"Score degraded by {abs(delta):.1f}"

        return candidate


# ── Experiment Log ───────────────────────────────────────────────────────────

class ExperimentLog:
    """Persistent experiment log — every variant tested is recorded."""

    def __init__(self, path: Optional[Path] = None) -> None:
        self.path = path or EXPERIMENT_DIR / "experiment_log.json"
        self.entries: List[Dict[str, Any]] = []
        self._load()

    def _load(self) -> None:
        if self.path.exists():
            try:
                self.entries = json.loads(self.path.read_text())
            except Exception:
                self.entries = []

    def record(self, variant: StrategyVariant, result: ExperimentResult) -> None:
        """Record an experiment."""
        self.entries.append({
            "variant": variant.to_dict(),
            "result": result.to_dict(),
            "timestamp": datetime.now(timezone.utc).isoformat(),
        })
        self._save()
        logger.info(
            "[KeepDiscard] %s v%d → score %.1f → %s",
            variant.name, variant.version, result.score, result.verdict,
        )

    def _save(self) -> None:
        self.path.write_text(json.dumps(self.entries[-200:], indent=2))

    def best_variant(self) -> Optional[Dict[str, Any]]:
        """Return the highest-scoring variant ever tested."""
        if not self.entries:
            return None
        return max(self.entries, key=lambda e: e["result"]["score"])

    def summary(self) -> Dict[str, Any]:
        """Summary of all experiments."""
        if not self.entries:
            return {"experiments": 0, "best": None}
        best = self.best_variant()
        return {
            "experiments": len(self.entries),
            "best_variant": best["result"]["variant"] if best else None,
            "best_score": best["result"]["score"] if best else 0,
            "kept": sum(1 for e in self.entries if e["result"]["verdict"] == "KEEP"),
            "discarded": sum(1 for e in self.entries if e["result"]["verdict"] == "DISCARD"),
        }
