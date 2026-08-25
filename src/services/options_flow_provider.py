from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import asdict, dataclass, field
from datetime import date, datetime, timezone
from typing import Any, Dict, List, Literal, Optional

OptionsDataMode = Literal["realtime", "delayed", "snapshot", "mock", "unavailable"]
OptionsSideBias = Literal[
    "CALL_BUYING", "PUT_BUYING", "CALL_SELLING", "PUT_SELLING", "BALANCED", "UNKNOWN"
]
OptionsCallPut = Literal["C", "P"]
OptionsQualityGrade = Literal["A", "B", "C"]
OptionsActionLabel = Literal["IDEA", "WATCH", "SUPPORTING_EVIDENCE", "AVOID_NOW"]


@dataclass
class OptionsFlowTrust:
    """Trust metadata for normalized options-flow data."""

    source: str = "unknown"
    mode: OptionsDataMode = "unavailable"
    delay_seconds: int = 0
    stale: bool = False
    synthetic: bool = False
    as_of: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


@dataclass
class OptionsFlowEvent:
    """Provider-normalized options activity event.

    This is intentionally vendor-neutral. Polygon/Cboe/OPRA-style feeds can map
    their raw trade, quote, open-interest, and IV fields into this schema before
    the radar engine scores anything.
    """

    underlying: str
    contract_symbol: str
    side_bias: OptionsSideBias
    call_put: OptionsCallPut
    strike: float
    expiry: str | date
    dte: int
    trade_timestamp: str | datetime
    premium: float
    price: float
    size: int
    bid: float = 0.0
    ask: float = 0.0
    mid: float = 0.0
    spread_pct: float = 0.0
    volume: int = 0
    open_interest: int = 0
    volume_oi_ratio: float = 0.0
    volume_vs_avg_ratio: float = 0.0
    sweep_flag: bool = False
    block_flag: bool = False
    repeated_directional_prints: int = 0
    iv: Optional[float] = None
    iv_change: Optional[float] = None
    stock_price: Optional[float] = None
    stock_move_pct: float = 0.0
    underlying_avg_volume: Optional[int] = None
    underlying_dollar_volume: Optional[float] = None
    market_cap: Optional[float] = None
    catalyst: Optional[str] = None
    regime_alignment: float = 0.5
    relative_strength: float = 0.5
    liquidity_score: float = 0.0
    anomaly_score: float = 0.0
    tradeability_score: float = 0.0
    opportunity_relevance_score: float = 0.0
    radar_score: float = 0.0
    quality_grade: OptionsQualityGrade = "C"
    action_label: OptionsActionLabel = "WATCH"
    explanation: str = ""
    trust: OptionsFlowTrust = field(default_factory=OptionsFlowTrust)

    def __post_init__(self) -> None:
        self.underlying = self.underlying.upper().strip()
        if isinstance(self.expiry, date):
            self.expiry = self.expiry.isoformat()
        if isinstance(self.trade_timestamp, datetime):
            self.trade_timestamp = self.trade_timestamp.astimezone(
                timezone.utc
            ).isoformat()
        if self.mid <= 0 and self.bid > 0 and self.ask > 0:
            self.mid = (self.bid + self.ask) / 2
        if self.spread_pct <= 0 and self.mid > 0 and self.ask >= self.bid:
            self.spread_pct = ((self.ask - self.bid) / self.mid) * 100
        if self.premium <= 0:
            self.premium = max(0.0, self.price * max(self.size, 0) * 100)
        if self.volume_oi_ratio <= 0 and self.open_interest > 0:
            self.volume_oi_ratio = self.volume / self.open_interest

    def to_dict(self) -> Dict[str, Any]:
        data = asdict(self)
        data["trust"] = self.trust.to_dict()
        return data


@dataclass
class OptionsProviderStatus:
    provider: str
    enabled: bool
    mode: OptionsDataMode
    status: Literal["ok", "degraded", "unavailable"]
    message: str = ""
    last_update: Optional[str] = None
    delay_seconds: int = 0

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


@dataclass
class OptionsRadarSnapshot:
    timestamp: str
    status: Literal["live", "stale", "snapshot", "unavailable"]
    source: str
    universe_size: int
    candidates: List[Dict[str, Any]]
    summary: Dict[str, Any]
    trust: Dict[str, Any]

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


class OptionsFlowProvider(ABC):
    """Vendor-neutral interface for options-flow data providers."""

    name: str = "base"

    @abstractmethod
    async def fetch_recent_events(
        self,
        universe: Optional[List[str]] = None,
        *,
        limit: int = 500,
    ) -> List[OptionsFlowEvent]:
        """Return recent normalized options-flow events."""

    @abstractmethod
    async def health(self) -> OptionsProviderStatus:
        """Return provider status without forcing a heavy connection."""
