"""
Alpha Object — CC X institutional memory schema.

Survives forever as the knowledge-layer artifact linking hypothesis → evidence →
outcome → lessons. InvestmentObject feeds Decision; AlphaObject feeds Knowledge.

Authority: research_only by default; never implies deploy permission.
"""

from __future__ import annotations

from datetime import datetime, timezone
from enum import Enum
from typing import Any, Dict, List, Optional
from uuid import uuid4

from pydantic import BaseModel, ConfigDict, Field


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


class AlphaLifecycleStage(str, Enum):
    """AlphaObject persists across the full investment lifecycle."""

    HYPOTHESIS = "HYPOTHESIS"
    EVIDENCE_GATHERING = "EVIDENCE_GATHERING"
    UNDER_REVIEW = "UNDER_REVIEW"
    ACTIVE = "ACTIVE"
    TRADED = "TRADED"
    CLOSED = "CLOSED"
    ARCHIVED = "ARCHIVED"


class AlphaEvidence(BaseModel):
    """Single evidence item supporting or refuting the alpha hypothesis."""

    model_config = ConfigDict(extra="forbid")

    evidence_id: str = Field(default_factory=lambda: str(uuid4()))
    as_of: datetime = Field(default_factory=_utcnow)
    source: str = ""  # dossier | graph | analog | macro | insider | manual
    summary: str = ""
    data_ref: Optional[str] = None  # artifact_id, URL, or journal ref
    weight: float = Field(default=1.0, ge=0.0, le=1.0)
    supports_hypothesis: bool = True


class AlphaUpdate(BaseModel):
    """Chronological update to hypothesis, confidence, or thesis."""

    model_config = ConfigDict(extra="forbid")

    update_id: str = Field(default_factory=lambda: str(uuid4()))
    as_of: datetime = Field(default_factory=_utcnow)
    author: str = "system"  # operator | council | system
    summary: str = ""
    confidence_delta: Optional[float] = None
    fields_changed: List[str] = Field(default_factory=list)


class AlphaReview(BaseModel):
    """Structured review checkpoint — council, PM, or post-mortem."""

    model_config = ConfigDict(extra="forbid")

    review_id: str = Field(default_factory=lambda: str(uuid4()))
    as_of: datetime = Field(default_factory=_utcnow)
    reviewer: str = ""
    review_type: str = "pm"  # pm | council | post_mortem | compliance
    verdict: str = ""  # uphold | revise | retire
    notes: str = ""
    confidence_after: Optional[float] = Field(default=None, ge=0.0, le=1.0)


class AlphaTradeLink(BaseModel):
    """Link to executed or proposed trades tied to this alpha hypothesis."""

    model_config = ConfigDict(extra="forbid")

    trade_id: str = ""
    decision_id: Optional[str] = None
    ticker: str = ""
    as_of: datetime = Field(default_factory=_utcnow)
    action: str = ""  # proposed | deployed | closed
    outcome_r: Optional[float] = None
    alpha_contribution_bps: Optional[float] = None


class AlphaPortfolioImpact(BaseModel):
    """Portfolio-level impact of acting on this alpha hypothesis."""

    model_config = ConfigDict(extra="forbid")

    fit_score: int = Field(default=50, ge=0, le=100)
    marginal_return_on_capital: Optional[float] = None
    sector_overlap_pct: float = Field(default=0.0, ge=0.0, le=100.0)
    what_becomes_worse: List[str] = Field(default_factory=list)
    sell_first_candidates: List[str] = Field(default_factory=list)
    capital_allocation_note: str = ""


class AlphaOutcome(BaseModel):
    """Final or interim outcome record for institutional attribution."""

    model_config = ConfigDict(extra="forbid")

    as_of: datetime = Field(default_factory=_utcnow)
    outcome_r: Optional[float] = None
    alpha_produced_bps: Optional[float] = None
    alpha_lost_bps: Optional[float] = None
    alpha_preserved_bps: Optional[float] = None
    alpha_missed_bps: Optional[float] = None
    verdict: str = ""  # validated | invalidated | inconclusive
    attribution_chain_ref: Optional[str] = None


class AlphaLesson(BaseModel):
    """Extracted lesson for Knowledge Engine / Market Memory."""

    model_config = ConfigDict(extra="forbid")

    lesson_id: str = Field(default_factory=lambda: str(uuid4()))
    as_of: datetime = Field(default_factory=_utcnow)
    summary: str = ""
    failure_mode: str = ""
    best_exit_note: str = ""
    analog_tags: List[str] = Field(default_factory=list)  # e.g. "March 2024", "July 2025"
    linked_knowledge_ids: List[str] = Field(default_factory=list)


class AlphaKnowledgeLink(BaseModel):
    """Cross-reference to Knowledge Graph nodes, analogs, or prior AlphaObjects."""

    model_config = ConfigDict(extra="forbid")

    link_id: str = Field(default_factory=lambda: str(uuid4()))
    link_type: str = ""  # graph_node | analog | prior_alpha | market_memory
    target_id: str = ""
    label: str = ""
    similarity: Optional[float] = Field(default=None, ge=0.0, le=1.0)


class AlphaObject(BaseModel):
    """
    Institutional memory object — survives forever.

    InvestmentObject → Decision layer (deploy gate, execution).
    AlphaObject → Knowledge layer (hypothesis, evidence, lessons).

    Only decision_truth_model + council + operator_state_contract may
    authorize deploy via linked InvestmentObject; AlphaObject never does.
    """

    model_config = ConfigDict(extra="ignore")

    # ── Identity ──
    alpha_id: str = Field(default_factory=lambda: str(uuid4()))
    ticker: str = ""
    investment_id: Optional[str] = None  # link to InvestmentObject when active
    as_of: datetime = Field(default_factory=_utcnow)
    version: str = "1.0"
    stage: AlphaLifecycleStage = AlphaLifecycleStage.HYPOTHESIS

    # ── Authority (always research/knowledge — never deploy) ──
    authority: str = "research_only"
    may_authorize_deploy: bool = False

    # ── Core thesis ──
    hypothesis: str = ""
    setup_type: str = ""
    expected_alpha_bps: Optional[float] = None
    expected_holding_days: Optional[float] = None

    # ── Evidence & confidence ──
    evidence: List[AlphaEvidence] = Field(default_factory=list)
    confidence: float = Field(default=0.5, ge=0.0, le=1.0)
    calibrated_confidence: Optional[float] = Field(default=None, ge=0.0, le=1.0)

    # ── Lifecycle records ──
    updates: List[AlphaUpdate] = Field(default_factory=list)
    reviews: List[AlphaReview] = Field(default_factory=list)
    trades: List[AlphaTradeLink] = Field(default_factory=list)
    portfolio_impact: AlphaPortfolioImpact = Field(default_factory=AlphaPortfolioImpact)
    final_outcome: Optional[AlphaOutcome] = None
    lessons: List[AlphaLesson] = Field(default_factory=list)
    knowledge_links: List[AlphaKnowledgeLink] = Field(default_factory=list)

    # ── Attribution hooks ──
    attribution_root_ref: Optional[str] = None  # PnL → position → decision chain
    market_data_refs: List[str] = Field(default_factory=list)
    feature_snapshot: Dict[str, Any] = Field(default_factory=dict)

    def is_knowledge_only(self) -> bool:
        return self.authority == "research_only" or not self.may_authorize_deploy
