"""
Strategy Promoter — 2-stage promotion pipeline (Sprint 34).

Stage 1: fast StrategyOptimizer finds candidate parameter sets.
Stage 2: EnhancedBacktester validates under realistic conditions.

Only strategies passing both stages are promoted to live.

Promotion gates (all must pass):
  • positive net alpha vs SPY
  • CVaR-95 above floor (not too tail-heavy)
  • max drawdown below threshold
  • slippage-adjusted profit factor above minimum
  • minimum trade count for statistical significance

This replaces the old "optimizer picks → goes live" flow with a
proper quant promotion pipeline.
"""
import logging
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)


@dataclass
class PromotionResult:
    """Outcome of a 2-stage strategy evaluation."""

    strategy_name: str
    promoted: bool
    stage1_score: float = 0.0          # optimizer composite
    stage2_passed: bool = False

    # Gate results
    alpha: Optional[float] = None       # vs SPY
    cvar_95: Optional[float] = None
    max_drawdown: Optional[float] = None
    profit_factor: Optional[float] = None
    sharpe: Optional[float] = None
    total_trades: int = 0
    avg_slippage_bps: float = 0.0

    # Rejection reasons (empty = promoted)
    rejections: List[str] = field(default_factory=list)

    def summary(self) -> str:
        status = "✅ PROMOTED" if self.promoted else "❌ REJECTED"
        lines = [
            f"{status}: {self.strategy_name}",
            f"  Stage-1 score: {self.stage1_score:.1f}",
            f"  Alpha: {self.alpha:.2%}" if self.alpha is not None else "",
            f"  CVaR-95: {self.cvar_95:.2%}" if self.cvar_95 is not None else "",
            f"  Max DD: {self.max_drawdown:.2%}" if self.max_drawdown is not None else "",
            f"  PF: {self.profit_factor:.2f}" if self.profit_factor is not None else "",
            f"  Sharpe: {self.sharpe:.2f}" if self.sharpe is not None else "",
            f"  Trades: {self.total_trades}",
            f"  Avg slip: {self.avg_slippage_bps:.1f} bps",
        ]
        if self.rejections:
            lines.append(f"  Reasons: {'; '.join(self.rejections)}")
        return "\n".join(l for l in lines if l)


class StrategyPromoter:
    """
    2-stage promotion pipeline.

    Stage 1: StrategyOptimizer scores candidate strategies
             using walk-forward backtest on dev data.
    Stage 2: EnhancedBacktester runs the candidate through
             realistic execution (slippage, benchmark) on
             holdout data.

    Only strategies passing all Stage-2 gates go live.
    """

    # Configurable promotion gates
    DEFAULT_GATES = {
        "min_alpha": 0.0,           # must beat SPY (positive alpha)
        "min_cvar_95": -0.03,       # CVaR-95 floor (daily)
        "max_drawdown": -0.15,      # max 15% drawdown
        "min_profit_factor": 1.2,   # slippage-adjusted PF
        "min_sharpe": 0.5,          # minimum Sharpe ratio
        "min_trades": 10,           # statistical significance
        "min_stage1_score": 40.0,   # optimizer composite gate
    }

    def __init__(
        self,
        gates: Optional[Dict[str, float]] = None,
    ):
        self.gates = {**self.DEFAULT_GATES, **(gates or {})}

    def evaluate(
        self,
        strategy_name: str,
        stage1_score: float,
        backtest_result: Optional[Any] = None,
    ) -> PromotionResult:
        """
        Run 2-stage evaluation.

        Args:
            strategy_name: strategy identifier
            stage1_score: score from StrategyOptimizer (0-100)
            backtest_result: BacktestResult from EnhancedBacktester
                             (None = stage 2 not run)

        Returns:
            PromotionResult with promoted=True/False + details
        """
        g = self.gates
        result = PromotionResult(
            strategy_name=strategy_name,
            promoted=False,
            stage1_score=stage1_score,
        )

        # Stage 1 gate
        if stage1_score < g["min_stage1_score"]:
            result.rejections.append(
                f"Stage-1 score {stage1_score:.1f} < "
                f"{g['min_stage1_score']}"
            )
            return result

        # Stage 2 requires a backtest result
        if backtest_result is None:
            result.rejections.append(
                "No Stage-2 backtest result provided"
            )
            return result

        result.stage2_passed = True

        # Extract metrics from BacktestResult
        result.alpha = getattr(
            backtest_result, "alpha", None
        )
        result.cvar_95 = getattr(
            backtest_result, "cvar_95", None
        )
        result.max_drawdown = getattr(
            backtest_result, "max_drawdown", None
        )
        result.profit_factor = getattr(
            backtest_result, "profit_factor", None
        )
        result.sharpe = getattr(
            backtest_result, "sharpe_ratio", None
        )
        result.total_trades = getattr(
            backtest_result, "total_trades", 0
        )
        result.avg_slippage_bps = getattr(
            backtest_result, "avg_slippage_bps", 0.0
        )

        # Gate checks
        if result.total_trades < g["min_trades"]:
            result.rejections.append(
                f"Only {result.total_trades} trades "
                f"(need {g['min_trades']})"
            )

        if (result.alpha is not None
                and result.alpha < g["min_alpha"]):
            result.rejections.append(
                f"Alpha {result.alpha:.2%} < "
                f"{g['min_alpha']:.2%}"
            )

        if (result.cvar_95 is not None
                and result.cvar_95 < g["min_cvar_95"]):
            result.rejections.append(
                f"CVaR-95 {result.cvar_95:.2%} < "
                f"{g['min_cvar_95']:.2%}"
            )

        if (result.max_drawdown is not None
                and result.max_drawdown < g["max_drawdown"]):
            result.rejections.append(
                f"Max DD {result.max_drawdown:.2%} < "
                f"{g['max_drawdown']:.2%}"
            )

        if (result.profit_factor is not None
                and result.profit_factor < g["min_profit_factor"]):
            result.rejections.append(
                f"PF {result.profit_factor:.2f} < "
                f"{g['min_profit_factor']:.2f}"
            )

        if (result.sharpe is not None
                and result.sharpe < g["min_sharpe"]):
            result.rejections.append(
                f"Sharpe {result.sharpe:.2f} < "
                f"{g['min_sharpe']:.2f}"
            )

        # Promoted if no rejections
        result.promoted = len(result.rejections) == 0
        return result

    def evaluate_batch(
        self,
        candidates: List[Dict[str, Any]],
    ) -> List[PromotionResult]:
        """
        Evaluate multiple candidates.

        Each candidate dict should have:
          - strategy_name: str
          - stage1_score: float
          - backtest_result: BacktestResult (optional)

        Returns list of PromotionResult sorted by stage1_score desc.
        """
        results = []
        for c in candidates:
            r = self.evaluate(
                strategy_name=c["strategy_name"],
                stage1_score=c.get("stage1_score", 0),
                backtest_result=c.get("backtest_result"),
            )
            results.append(r)

        results.sort(
            key=lambda x: x.stage1_score, reverse=True,
        )
        promoted = [r for r in results if r.promoted]
        rejected = [r for r in results if not r.promoted]

        logger.info(
            "Strategy promotion: %d/%d promoted, "
            "%d rejected",
            len(promoted), len(results), len(rejected),
        )
        for r in rejected:
            logger.info(
                "  Rejected %s: %s",
                r.strategy_name, "; ".join(r.rejections),
            )

        return results
