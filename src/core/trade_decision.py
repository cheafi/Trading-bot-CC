"""
Typed daily decision contract (PM-facing).

Separates signal quality, evidence quality, execution readiness, and portfolio fit.
A recommendation is not an executable order.
"""

from __future__ import annotations

from datetime import datetime, timezone
from enum import Enum
from typing import Any, Dict, List, Optional
from uuid import uuid4

from pydantic import BaseModel, Field

from src.core.models import TradeRecommendation


class DataFreshness(str, Enum):
    VERIFIED = "verified"
    STALE = "stale"
    UNVERIFIED = "unverified"


class ExecutionReadiness(str, Enum):
    READY = "ready"
    BLOCKED = "blocked"
    REQUIRES_APPROVAL = "requires_approval"
    NOT_EXECUTABLE = "not_executable"


class TradeDecision(BaseModel):
    """Single ranked decision for Today / Discover surfaces."""

    recommendation_id: str = Field(default_factory=lambda: uuid4().hex[:16])
    as_of: str = Field(
        default_factory=lambda: datetime.now(timezone.utc)
        .isoformat()
        .replace("+00:00", "Z")
    )
    symbol: str
    action: str = "WAIT"
    market_regime: str = ""
    entry_trigger: str = ""
    entry_range: Optional[str] = None
    stop_loss: Optional[float] = None
    take_profit_1: Optional[float] = None
    take_profit_2: Optional[float] = None
    suggested_quantity: Optional[int] = None
    risk_amount: Optional[float] = None
    risk_pct_of_equity: Optional[float] = None
    risk_reward_ratio: Optional[float] = None
    time_horizon: str = ""
    evidence: List[str] = Field(default_factory=list)
    counter_arguments: List[str] = Field(default_factory=list)
    invalidation_reason: str = ""
    signal_quality: float = Field(ge=0.0, le=1.0, default=0.0)
    evidence_quality: float = Field(ge=0.0, le=1.0, default=0.0)
    execution_readiness: ExecutionReadiness = ExecutionReadiness.NOT_EXECUTABLE
    portfolio_fit: Optional[str] = None
    data_freshness: DataFreshness = DataFreshness.UNVERIFIED
    requires_approval: bool = True
    quote_timestamp: Optional[str] = None
    suppression_reason: str = ""
    strategy_id: str = ""

    def to_api_dict(self) -> Dict[str, Any]:
        return self.model_dump(mode="json")


class DailyDecisionPipelineResult(BaseModel):
    """Output of the daily decision engine (up to 10, top 3 highlighted)."""

    as_of: str = Field(
        default_factory=lambda: datetime.now(timezone.utc)
        .isoformat()
        .replace("+00:00", "Z")
    )
    market_regime: str = "UNKNOWN"
    regime_should_trade: bool = False
    no_trade: bool = True
    no_trade_summary: str = ""
    decisions: List[TradeDecision] = Field(default_factory=list)
    top_3: List[TradeDecision] = Field(default_factory=list)

    def to_api_dict(self) -> Dict[str, Any]:
        return {
            "as_of": self.as_of,
            "market_regime": self.market_regime,
            "regime_should_trade": self.regime_should_trade,
            "no_trade": self.no_trade,
            "no_trade_summary": self.no_trade_summary,
            "decisions": [d.to_api_dict() for d in self.decisions],
            "top_3": [d.to_api_dict() for d in self.top_3],
        }


def _map_action(rec: TradeRecommendation, *, regime_ok: bool) -> str:
    if not regime_ok:
        return "NO TRADE"
    if rec.trade_decision and rec.entry_price > 0 and rec.stop_price > 0:
        return "BUY" if rec.direction.upper() in ("LONG", "BUY") else "WAIT"
    if rec.suppression_reason:
        return "WAIT"
    return "WATCH"


def _evidence_freshness(rec: TradeRecommendation) -> DataFreshness:
    if rec.entry_price <= 0:
        return DataFreshness.UNVERIFIED
    if rec.stop_price <= 0:
        return DataFreshness.UNVERIFIED
    meta = getattr(rec, "metadata", {}) or {}
    if meta.get("data_stale") or meta.get("stale"):
        return DataFreshness.STALE
    return DataFreshness.VERIFIED


def _evidence_quality_score(freshness: DataFreshness, rec: TradeRecommendation) -> float:
    if freshness == DataFreshness.UNVERIFIED:
        return 0.2
    if freshness == DataFreshness.STALE:
        return 0.45
    base = 0.7
    if rec.evidence:
        base += min(0.25, 0.05 * len(rec.evidence))
    return min(1.0, base)


def _execution_readiness(
    rec: TradeRecommendation,
    *,
    regime_ok: bool,
    freshness: DataFreshness,
) -> ExecutionReadiness:
    if freshness != DataFreshness.VERIFIED:
        return ExecutionReadiness.BLOCKED
    if not regime_ok:
        return ExecutionReadiness.BLOCKED
    if not rec.trade_decision:
        return ExecutionReadiness.NOT_EXECUTABLE
    if rec.entry_price <= 0 or rec.stop_price <= 0:
        return ExecutionReadiness.BLOCKED
    return ExecutionReadiness.REQUIRES_APPROVAL


def trade_decision_from_recommendation(
    rec: TradeRecommendation,
    *,
    regime: Dict[str, Any],
) -> TradeDecision:
    regime_label = str(
        regime.get("regime") or regime.get("label") or rec.regime_label or "UNKNOWN"
    )
    regime_ok = bool(regime.get("should_trade", True))
    freshness = _evidence_freshness(rec)
    target = None
    meta = getattr(rec, "metadata", {}) or {}
    orig = meta.get("_original_dict") if isinstance(meta, dict) else {}
    if isinstance(orig, dict):
        target = orig.get("target_price") or orig.get("target")
    if target is None and rec.risk_reward_ratio and rec.entry_price and rec.stop_price:
        risk = abs(rec.entry_price - rec.stop_price)
        if risk > 0:
            target = rec.entry_price + risk * rec.risk_reward_ratio

    readiness = _execution_readiness(rec, regime_ok=regime_ok, freshness=freshness)
    counter: List[str] = list(rec.key_risks or [])
    if rec.suppression_reason:
        counter.append(rec.suppression_reason)
    if freshness == DataFreshness.UNVERIFIED:
        counter.append("Missing verified entry/stop levels or quote")

    return TradeDecision(
        recommendation_id=rec.recommendation_id or uuid4().hex[:16],
        symbol=rec.ticker.upper(),
        action=_map_action(rec, regime_ok=regime_ok),
        market_regime=regime_label,
        entry_trigger=rec.entry_logic or rec.why_now or "",
        entry_range=(
            f"{rec.entry_price:.2f}" if rec.entry_price > 0 else None
        ),
        stop_loss=rec.stop_price if rec.stop_price > 0 else None,
        take_profit_1=float(target) if target else None,
        take_profit_2=None,
        risk_reward_ratio=rec.risk_reward_ratio or None,
        time_horizon=rec.horizon or "",
        evidence=list(rec.evidence or [])[:8],
        counter_arguments=counter[:6],
        invalidation_reason=rec.suppression_reason or "",
        signal_quality=max(0.0, min(1.0, rec.composite_score)),
        evidence_quality=_evidence_quality_score(freshness, rec),
        execution_readiness=readiness,
        portfolio_fit=rec.portfolio_fit or None,
        data_freshness=freshness,
        requires_approval=True,
        suppression_reason=rec.suppression_reason or "",
        strategy_id=rec.strategy_id or "",
    )
