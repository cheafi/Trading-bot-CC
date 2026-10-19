"""
Typed daily decision contract (PM-facing).

Separates signal quality, evidence quality, execution readiness, and portfolio fit.
A recommendation is not an executable order.

evidence_quality is a deterministic heuristic (0–1) from quote provenance and evidence
completeness — not a calibrated win probability or estimated hit rate.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Any, Dict, List, Optional, Tuple
from uuid import uuid4

from pydantic import BaseModel, Field

from src.core.models import TradeRecommendation
from src.engines.data_quality_engine import DataQualityEngine

# Align quote TTL with DataQualityEngine documented cache tiers (see module docstring).
_QUOTE_FRESH_MAX_AGE_S = DataQualityEngine.AGING_THRESHOLD_S  # 15 minutes
_QUOTE_STALE_AGE_S = DataQualityEngine.STALE_THRESHOLD_S  # 2 hours


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
    evidence_quality: float = Field(
        ge=0.0,
        le=1.0,
        default=0.0,
        description="Heuristic data/evidence completeness — not win probability.",
    )
    execution_readiness: ExecutionReadiness = ExecutionReadiness.NOT_EXECUTABLE
    portfolio_fit: Optional[str] = None
    data_freshness: DataFreshness = DataFreshness.UNVERIFIED
    requires_approval: bool = True
    quote_timestamp: Optional[str] = None
    quote_source: Optional[str] = None
    suppression_reason: str = ""
    strategy_id: str = ""
    block_reason: str = ""

    def to_api_dict(self) -> Dict[str, Any]:
        return self.model_dump(mode="json")

    @property
    def is_actionable(self) -> bool:
        """Qualifies for top actionable list (human approval workflow only)."""
        return (
            self.action == "BUY"
            and self.execution_readiness == ExecutionReadiness.REQUIRES_APPROVAL
            and self.data_freshness == DataFreshness.VERIFIED
        )


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
    watchlist: List[TradeDecision] = Field(default_factory=list)

    def to_api_dict(self) -> Dict[str, Any]:
        return {
            "as_of": self.as_of,
            "market_regime": self.market_regime,
            "regime_should_trade": self.regime_should_trade,
            "no_trade": self.no_trade,
            "no_trade_summary": self.no_trade_summary,
            "decisions": [d.to_api_dict() for d in self.decisions],
            "top_3": [d.to_api_dict() for d in self.top_3],
            "watchlist": [d.to_api_dict() for d in self.watchlist],
        }


def normalize_regime_state(regime: Optional[Dict[str, Any]]) -> Dict[str, Any]:
    """Fail-closed regime normalization for decision eligibility."""
    if not regime:
        return {
            "regime": "UNKNOWN",
            "should_trade": False,
            "no_trade_reason": "missing_regime",
        }
    out = dict(regime)
    label = str(out.get("regime") or out.get("label") or "").strip()
    if not label:
        out["regime"] = "UNKNOWN"
    else:
        out["regime"] = label
    if "should_trade" not in out:
        out["should_trade"] = False
    else:
        out["should_trade"] = bool(out["should_trade"])
    return out


def regime_allows_new_entries(regime: Dict[str, Any]) -> bool:
    if "should_trade" not in regime:
        return False
    if not regime.get("should_trade"):
        return False
    label = str(regime.get("regime") or "").upper()
    if not label or label == "UNKNOWN":
        return False
    return True


def _original_dict(rec: TradeRecommendation) -> Dict[str, Any]:
    meta = getattr(rec, "metadata", {}) or {}
    orig = meta.get("_original_dict") if isinstance(meta, dict) else {}
    return orig if isinstance(orig, dict) else {}


def _quote_provenance(rec: TradeRecommendation) -> Tuple[Optional[str], Optional[str], Optional[str]]:
    """Return (timestamp_iso, source, trust_freshness label)."""
    meta = getattr(rec, "metadata", {}) or {}
    orig = _original_dict(rec)
    trust = dict(rec.trust or {})
    if not trust and isinstance(orig.get("trust"), dict):
        trust = dict(orig["trust"])

    ts = (
        orig.get("price_timestamp")
        or orig.get("quote_timestamp")
        or meta.get("price_timestamp")
        or meta.get("quote_timestamp")
    )
    source = (
        orig.get("price_source")
        or orig.get("quote_source")
        or meta.get("price_source")
        or meta.get("quote_source")
        or trust.get("source")
    )
    mode = str(trust.get("mode") or "").upper()
    if not source and mode in ("LIVE", "DELAYED"):
        source = f"trust_mode:{mode.lower()}"
    freshness = trust.get("freshness") or orig.get("data_freshness")
    if ts is not None:
        ts = str(ts).strip() or None
    if source is not None:
        source = str(source).strip() or None
    return ts, source, str(freshness).upper() if freshness else None


def _parse_timestamp(ts: str, *, now: datetime) -> Tuple[Optional[datetime], Optional[str]]:
    try:
        dt = datetime.fromisoformat(ts.replace("Z", "+00:00"))
    except (ValueError, TypeError):
        return None, "malformed_quote_timestamp"
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    if dt > now:
        return None, "future_dated_quote"
    return dt, None


def _explicit_stale_flags(rec: TradeRecommendation, trust_freshness: Optional[str]) -> bool:
    meta = getattr(rec, "metadata", {}) or {}
    orig = _original_dict(rec)
    if meta.get("data_stale") or meta.get("stale"):
        return True
    if orig.get("data_stale") or orig.get("stale"):
        return True
    if trust_freshness in {
        "STALE",
        "CRITICAL",
        "DEGRADED",
        "UNAVAILABLE",
        "SYNTHETIC",
    }:
        return True
    return False


def _long_price_geometry(rec: TradeRecommendation) -> Tuple[bool, str, Optional[float], Optional[float]]:
    """Long-only geometry; target only from explicit fields (no synthetic TP)."""
    entry = float(rec.entry_price or 0)
    stop = float(rec.stop_price or 0)
    if entry <= 0:
        return False, "missing_entry", None, None
    if stop <= 0:
        return False, "missing_stop", None, None
    direction = str(rec.direction or "LONG").upper()
    if direction not in ("LONG", "BUY"):
        return False, "non_long_direction", None, None
    if stop >= entry:
        return False, "stop_not_below_entry", None, None

    orig = _original_dict(rec)
    target_raw = orig.get("target_price") or orig.get("target")
    target: Optional[float] = None
    if target_raw is not None:
        try:
            target = float(target_raw)
        except (TypeError, ValueError):
            return False, "invalid_target", None, None
    if target is None or target <= 0:
        return False, "missing_target", None, None
    if target <= entry:
        return False, "target_not_above_entry", None, None

    risk = entry - stop
    if risk <= 0:
        return False, "non_positive_risk", None, None
    reward = target - entry
    if reward <= 0:
        return False, "non_positive_reward", None, None
    rr = round(reward / risk, 2)
    return True, "", target, rr


def _evidence_freshness(
    rec: TradeRecommendation,
    *,
    now: Optional[datetime] = None,
) -> Tuple[DataFreshness, Optional[str], Optional[str], Optional[str]]:
    """
    Quote provenance gate. Populated entry/stop alone are not verification.

    Returns (freshness, quote_timestamp, quote_source, detail_reason).
    """
    now = now or datetime.now(timezone.utc)
    ts_str, source, trust_fresh = _quote_provenance(rec)

    if _explicit_stale_flags(rec, trust_fresh):
        return DataFreshness.STALE, ts_str, source, "explicit_stale_flag"

    geom_ok, geom_reason, _, _ = _long_price_geometry(rec)
    if not geom_ok and geom_reason in (
        "missing_entry",
        "missing_stop",
        "stop_not_below_entry",
        "invalid_target",
        "missing_target",
        "target_not_above_entry",
    ):
        return DataFreshness.UNVERIFIED, ts_str, source, geom_reason

    if not ts_str:
        return DataFreshness.UNVERIFIED, None, source, "missing_quote_timestamp"
    if not source:
        return DataFreshness.UNVERIFIED, ts_str, None, "missing_quote_source"

    dt, ts_err = _parse_timestamp(ts_str, now=now)
    if ts_err or dt is None:
        return DataFreshness.UNVERIFIED, ts_str, source, ts_err or "bad_timestamp"

    age_s = (now - dt).total_seconds()
    if age_s >= _QUOTE_STALE_AGE_S:
        return DataFreshness.STALE, ts_str, source, "quote_age_exceeds_stale_threshold"
    if age_s >= _QUOTE_FRESH_MAX_AGE_S:
        return DataFreshness.STALE, ts_str, source, "quote_age_exceeds_fresh_ttl"

    if not geom_ok:
        return DataFreshness.UNVERIFIED, ts_str, source, geom_reason

    return DataFreshness.VERIFIED, ts_str, source, None


def _evidence_quality_score(
    freshness: DataFreshness,
    rec: TradeRecommendation,
    *,
    has_quote_provenance: bool,
) -> float:
    """Heuristic completeness score — not a probability of success."""
    if not has_quote_provenance:
        return min(0.35, 0.15 + 0.05 * min(len(rec.evidence or []), 4))
    if freshness == DataFreshness.UNVERIFIED:
        return 0.25
    if freshness == DataFreshness.STALE:
        return 0.45
    base = 0.65
    if rec.evidence:
        base += min(0.25, 0.05 * len(rec.evidence))
    return min(1.0, base)


@dataclass
class _Eligibility:
    action: str
    readiness: ExecutionReadiness
    freshness: DataFreshness
    quote_timestamp: Optional[str]
    quote_source: Optional[str]
    target: Optional[float]
    risk_reward_ratio: Optional[float]
    block_reason: str = ""
    counter: List[str] = field(default_factory=list)


def assess_trade_eligibility(
    rec: TradeRecommendation,
    regime: Dict[str, Any],
    *,
    now: Optional[datetime] = None,
) -> _Eligibility:
    """Single gate for displayed action and execution_readiness."""
    now = now or datetime.now(timezone.utc)
    regime_norm = normalize_regime_state(regime)
    regime_ok = regime_allows_new_entries(regime_norm)

    freshness, q_ts, q_src, fresh_detail = _evidence_freshness(rec, now=now)
    geom_ok, geom_reason, target, rr = _long_price_geometry(rec)

    counter: List[str] = list(rec.key_risks or [])
    if rec.suppression_reason:
        counter.append(rec.suppression_reason)
    if rec.why_not_trade:
        counter.append(rec.why_not_trade)

    block_parts: List[str] = []

    if rec.suppression_reason:
        block_parts.append(f"suppressed:{rec.suppression_reason}")
        return _Eligibility(
            action="BLOCKED",
            readiness=ExecutionReadiness.BLOCKED,
            freshness=freshness,
            quote_timestamp=q_ts,
            quote_source=q_src,
            target=target if geom_ok else None,
            risk_reward_ratio=rr if geom_ok else None,
            block_reason="; ".join(block_parts),
            counter=counter,
        )

    if not regime_ok:
        block_parts.append(
            regime_norm.get("no_trade_reason")
            or "regime_not_actionable"
        )
        action = "NO TRADE" if not regime_allows_new_entries(regime_norm) else "WAIT"
        if str(regime_norm.get("regime", "")).upper() == "UNKNOWN":
            action = "NO TRADE"
        counter.append("Market regime unknown or not trade-enabled")
        return _Eligibility(
            action=action,
            readiness=ExecutionReadiness.BLOCKED,
            freshness=freshness,
            quote_timestamp=q_ts,
            quote_source=q_src,
            target=target if geom_ok else None,
            risk_reward_ratio=rr if geom_ok else None,
            block_reason="; ".join(block_parts),
            counter=counter,
        )

    if freshness != DataFreshness.VERIFIED:
        if fresh_detail:
            block_parts.append(fresh_detail)
        if geom_reason and not geom_ok:
            block_parts.append(geom_reason)
        counter.append("Quote unverified or stale — not actionable")
        return _Eligibility(
            action="WATCH" if rec.composite_score >= 0.35 else "WAIT",
            readiness=ExecutionReadiness.BLOCKED,
            freshness=freshness,
            quote_timestamp=q_ts,
            quote_source=q_src,
            target=target if geom_ok else None,
            risk_reward_ratio=rr if geom_ok else None,
            block_reason="; ".join(block_parts) or "data_not_verified",
            counter=counter,
        )

    if not geom_ok:
        block_parts.append(geom_reason or "invalid_price_geometry")
        counter.append("Invalid long entry/stop/target geometry")
        return _Eligibility(
            action="WAIT",
            readiness=ExecutionReadiness.BLOCKED,
            freshness=freshness,
            quote_timestamp=q_ts,
            quote_source=q_src,
            target=None,
            risk_reward_ratio=None,
            block_reason="; ".join(block_parts),
            counter=counter,
        )

    if not rec.trade_decision:
        block_parts.append("ensemble_trade_decision_false")
        counter.append("Strategy gates did not approve trade_decision")
        return _Eligibility(
            action="WAIT",
            readiness=ExecutionReadiness.NOT_EXECUTABLE,
            freshness=freshness,
            quote_timestamp=q_ts,
            quote_source=q_src,
            target=target,
            risk_reward_ratio=rr,
            block_reason="; ".join(block_parts),
            counter=counter,
        )

    direction = str(rec.direction or "LONG").upper()
    if direction not in ("LONG", "BUY"):
        return _Eligibility(
            action="WAIT",
            readiness=ExecutionReadiness.NOT_EXECUTABLE,
            freshness=freshness,
            quote_timestamp=q_ts,
            quote_source=q_src,
            target=target,
            risk_reward_ratio=rr,
            block_reason="non_long_direction",
            counter=counter,
        )

    return _Eligibility(
        action="BUY",
        readiness=ExecutionReadiness.REQUIRES_APPROVAL,
        freshness=freshness,
        quote_timestamp=q_ts,
        quote_source=q_src,
        target=target,
        risk_reward_ratio=rr,
        block_reason="",
        counter=counter,
    )


def trade_decision_from_recommendation(
    rec: TradeRecommendation,
    *,
    regime: Dict[str, Any],
    now: Optional[datetime] = None,
) -> TradeDecision:
    regime_norm = normalize_regime_state(regime)
    regime_label = str(regime_norm.get("regime") or "UNKNOWN")
    elig = assess_trade_eligibility(rec, regime_norm, now=now)

    ts_str, source, _ = _quote_provenance(rec)
    has_provenance = bool(ts_str and source)

    return TradeDecision(
        recommendation_id=rec.recommendation_id or uuid4().hex[:16],
        symbol=rec.ticker.upper(),
        action=elig.action,
        market_regime=regime_label,
        entry_trigger=rec.entry_logic or rec.why_now or "",
        entry_range=f"{rec.entry_price:.2f}" if rec.entry_price > 0 else None,
        stop_loss=rec.stop_price if rec.stop_price > 0 else None,
        take_profit_1=elig.target,
        take_profit_2=None,
        risk_reward_ratio=elig.risk_reward_ratio,
        time_horizon=rec.horizon or "",
        evidence=list(rec.evidence or [])[:8],
        counter_arguments=elig.counter[:6],
        invalidation_reason=rec.suppression_reason or rec.why_not_trade or "",
        signal_quality=max(0.0, min(1.0, rec.composite_score)),
        evidence_quality=_evidence_quality_score(
            elig.freshness, rec, has_quote_provenance=has_provenance
        ),
        execution_readiness=elig.readiness,
        portfolio_fit=rec.portfolio_fit or None,
        data_freshness=elig.freshness,
        requires_approval=True,
        quote_timestamp=elig.quote_timestamp,
        quote_source=elig.quote_source,
        suppression_reason=rec.suppression_reason or "",
        strategy_id=rec.strategy_id or "",
        block_reason=elig.block_reason,
    )
