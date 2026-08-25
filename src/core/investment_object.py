"""
Investment Object — CC X canonical schema.

Single structured object consumed by Knowledge → Research → Decision →
Portfolio → Execution → Learning layers. Extends decision/trade brief
concepts without replacing deploy authority (see decision_truth_model.py).
"""

from __future__ import annotations

from datetime import datetime, timezone
from enum import Enum
from typing import Any, Dict, List, Optional
from uuid import uuid4

from pydantic import BaseModel, ConfigDict, Field

from src.core.models import EdgeModel


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


class InvestmentStage(str, Enum):
    IDEA = "IDEA"
    VALIDATED = "VALIDATED"
    SIMULATED = "SIMULATED"
    FIT_CHECKED = "FIT_CHECKED"
    GATED = "GATED"
    DEPLOYED = "DEPLOYED"
    CLOSED = "CLOSED"


class ProvenanceBlock(BaseModel):
    """Mandatory lineage for every market- or score-derived field."""

    model_config = ConfigDict(extra="forbid")

    source: str = ""
    as_of: datetime = Field(default_factory=_utcnow)
    mode: str = "UNVERIFIED"  # LIVE | CACHED | DEGRADED | MOCK | SYNTHETIC
    lag_days: int = 0
    data_freshness_minutes: int = -1


class HistoricalAnalog(BaseModel):
    """Research-only pattern match — never implies deploy."""

    match_date: str
    similarity: float = Field(ge=0.0, le=1.0)
    outcome_r: Optional[float] = None
    setup_label: str = ""
    sample_note: str = ""


class PortfolioImpactBlock(BaseModel):
    """Answers: what becomes worse if I buy this?"""

    model_config = ConfigDict(extra="forbid")

    fit_score: int = Field(default=50, ge=0, le=100)
    sector_overlap_pct: float = Field(default=0.0, ge=0.0, le=100.0)
    correlation_note: str = ""
    replacement_delta: Optional[float] = None
    what_becomes_worse: List[str] = Field(default_factory=list)
    concentration_label: str = "neutral"  # low | neutral | high


class InvestmentObject(BaseModel):
    """
    Canonical investment artifact for CC X.

    Only decision_truth_model + council + operator_state_contract may set
    deploy_eligible=True. All other producers default research_only.
    """

    model_config = ConfigDict(extra="ignore")

    # ── Identity ──
    investment_id: str = Field(default_factory=lambda: str(uuid4()))
    ticker: str
    as_of: datetime = Field(default_factory=_utcnow)
    artifact_id: Optional[str] = None
    version: str = "1.0"

    # ── Authority (gates are server-authoritative) ──
    authority: str = "research_only"
    may_authorize_deploy: bool = False
    deploy_eligible: bool = False
    gate_reasons: List[str] = Field(default_factory=list)

    # ── Provenance ──
    provenance: ProvenanceBlock = Field(default_factory=ProvenanceBlock)

    # ── Alpha thesis ──
    alpha_source: str = ""  # bull_scanner | brief | council | manual
    edge_hypothesis: str = ""
    setup_type: str = ""
    strategy_style: str = ""
    expected_alpha_bps: Optional[float] = None
    expected_holding_days: Optional[float] = None
    vol_bucket: str = ""

    # ── Probability / EV ──
    edge_model: EdgeModel = Field(default_factory=EdgeModel)
    ev_score: Optional[float] = None
    ev_components: Dict[str, float] = Field(default_factory=dict)
    confidence: int = Field(default=50, ge=0, le=100)
    calibrated_confidence: Optional[float] = Field(default=None, ge=0.0, le=1.0)

    # ── Factor / theme / macro ──
    factor_exposures: Dict[str, float] = Field(default_factory=dict)
    theme_tags: List[str] = Field(default_factory=list)
    sector: str = ""
    macro_sensitivity: Dict[str, float] = Field(default_factory=dict)

    # ── Risk / liquidity / decay ──
    capacity_class: str = ""  # scale_clean | pilot_only | blocked
    liquidity_score: Optional[float] = Field(default=None, ge=0.0, le=100.0)
    crowding: str = ""
    half_life_sessions: Optional[int] = None
    decay_confidence: str = "low"

    # ── Portfolio impact ──
    portfolio_impact: PortfolioImpactBlock = Field(default_factory=PortfolioImpactBlock)

    # ── Knowledge graph ──
    graph_neighbors: List[str] = Field(default_factory=list)
    theme_cluster_id: Optional[str] = None

    # ── Analogs (research only) ──
    historical_analogs: List[HistoricalAnalog] = Field(default_factory=list)

    # ── Execution structure ──
    entry_zone: str = ""
    stop: Optional[float] = None
    target: Optional[float] = None
    rr_ratio: Optional[float] = None
    execution_quality: str = ""
    execution_cost_bps: Optional[float] = None

    # ── Lifecycle ──
    stage: InvestmentStage = InvestmentStage.IDEA
    decision_id: Optional[str] = None
    outcome_r: Optional[float] = None

    # ── Learning hooks ──
    regime_at_signal: str = ""
    feature_snapshot: Dict[str, Any] = Field(default_factory=dict)
    journal_ref: Optional[str] = None

    def is_research_only(self) -> bool:
        return self.authority == "research_only" or not self.may_authorize_deploy
