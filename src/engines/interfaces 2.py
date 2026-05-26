"""
CC — Engine Interfaces (Abstract Base Classes)
================================================
Defines clean boundaries between engines so they can be
developed, tested, and swapped independently.

Reference: QuantConnect's modular alpha → portfolio → risk → execution.

Each engine has a well-defined interface:
  - AlphaEngine: generates trade ideas (signals)
  - PortfolioEngine: constructs portfolio from ideas
  - RiskEngine: applies risk constraints and throttles
  - ExecutionEngine: routes orders to brokers
  - CalibrationInterface: calibrates confidence
  - MetaLabelInterface: go/no-go decisions
"""
from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import Any, Dict, List, Optional


# ── Alpha Layer ───────────────────────────────────────────────

@dataclass
class AlphaSignal:
    """Standardized signal output from any alpha engine."""
    ticker: str
    direction: str  # LONG / SHORT
    score: float  # 0-100
    confidence: float  # 0-1
    strategy: str
    regime: str
    evidence_for: List[str]
    evidence_against: List[str]
    invalidation: str = ""
    time_horizon_days: int = 5


class AlphaEngine(ABC):
    """Interface for any signal-generating engine."""

    @abstractmethod
    def generate_signals(
        self, universe: List[str], **kwargs: Any
    ) -> List[AlphaSignal]:
        """Generate ranked trade ideas."""
        ...

    @abstractmethod
    def name(self) -> str:
        """Engine identifier."""
        ...


# ── Portfolio Construction Layer ──────────────────────────────

@dataclass
class PortfolioTarget:
    """Target position from portfolio construction."""
    ticker: str
    direction: str
    weight_pct: float
    size_shares: int = 0
    reason: str = ""


class PortfolioEngine(ABC):
    """Interface for portfolio construction."""

    @abstractmethod
    def construct(
        self,
        signals: List[AlphaSignal],
        current_positions: Dict[str, Any],
        capital: float,
    ) -> List[PortfolioTarget]:
        """Convert signals into portfolio targets."""
        ...


# ── Risk Layer ────────────────────────────────────────────────

@dataclass
class RiskVerdict:
    """Risk engine output for a proposed trade."""
    approved: bool
    throttle_state: str = "normal"
    size_multiplier: float = 1.0
    vetoes: List[str] = None
    warnings: List[str] = None

    def __post_init__(self):
        if self.vetoes is None:
            self.vetoes = []
        if self.warnings is None:
            self.warnings = []


class RiskEngine(ABC):
    """Interface for risk management."""

    @abstractmethod
    def evaluate(
        self,
        target: PortfolioTarget,
        portfolio_state: Dict[str, Any],
    ) -> RiskVerdict:
        """Approve/reject/resize a proposed trade."""
        ...

    @abstractmethod
    def current_throttle(self) -> str:
        """Current portfolio-level throttle state."""
        ...


# ── Execution Layer ───────────────────────────────────────────

@dataclass
class OrderRequest:
    """Standardized order request."""
    ticker: str
    direction: str  # BUY / SELL
    quantity: int
    order_type: str = "market"  # market / limit
    limit_price: Optional[float] = None
    time_in_force: str = "day"


@dataclass
class OrderResult:
    """Execution result."""
    order_id: str
    status: str  # filled / partial / rejected
    filled_quantity: int = 0
    avg_price: float = 0.0
    message: str = ""


class ExecutionEngine(ABC):
    """Interface for order routing and execution."""

    @abstractmethod
    async def submit_order(
        self, order: OrderRequest
    ) -> OrderResult:
        """Submit order to broker."""
        ...

    @abstractmethod
    async def cancel_order(self, order_id: str) -> bool:
        """Cancel pending order."""
        ...

    @abstractmethod
    async def get_positions(self) -> Dict[str, Any]:
        """Get current broker positions."""
        ...


# ── Calibration Interface ─────────────────────────────────────

class CalibrationInterface(ABC):
    """Interface for confidence calibration."""

    @abstractmethod
    def calibrate(
        self, raw_confidence: float, regime: str
    ) -> float:
        """Return calibrated probability."""
        ...

    @abstractmethod
    def reliability_bucket(
        self, calibrated_prob: float
    ) -> str:
        """Return reliability bucket label."""
        ...


# ── Meta-Label Interface ──────────────────────────────────────

class MetaLabelInterface(ABC):
    """Interface for go/no-go trade decisions."""

    @abstractmethod
    def should_trade(
        self,
        signal: AlphaSignal,
        portfolio_state: Dict[str, Any],
        market_state: Dict[str, Any],
    ) -> Dict[str, Any]:
        """Return decision dict with verdict + reasons."""
        ...
