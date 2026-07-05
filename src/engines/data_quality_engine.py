"""
Data Quality Engine — Universal failure-state transparency (Sprint 71)
=====================================================================

Every data point and recommendation carries a quality descriptor so users
never mistake stale/partial/synthetic data for live, complete data.

Quality states:
  REAL_TIME   — live feed, < 15 s age
  DELAYED     — official feed with exchange delay (15 min typical)
  FRESH       — cached but recently refreshed (< 15 min)
  AGING       — cached, 15 min – 2 h old
  STALE       — > 2 h old, may be materially wrong
  PARTIAL     — some fields present, others missing
  DEGRADED    — present but confidence reduced due to anomalies
  SYNTHETIC   — model-generated / heuristic, not real market data
  UNAVAILABLE — no data at all

Escalation rules:
  - Any STALE or UNAVAILABLE on a held position → automatic alert
  - DEGRADED confidence reduction ≥ 30 % → warning banner
  - SYNTHETIC on a LIVE-mode signal → hard block
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)


# ─────────────────────────────────────────────────────────────────────
# Enums
# ─────────────────────────────────────────────────────────────────────

class DataQualityState(str, Enum):
    """Universal data quality classification."""
    REAL_TIME = "REAL_TIME"
    DELAYED = "DELAYED"
    FRESH = "FRESH"
    AGING = "AGING"
    STALE = "STALE"
    PARTIAL = "PARTIAL"
    DEGRADED = "DEGRADED"
    SYNTHETIC = "SYNTHETIC"
    UNAVAILABLE = "UNAVAILABLE"


class QualitySeverity(str, Enum):
    """Escalation severity for quality issues."""
    OK = "OK"            # green — no action needed
    INFO = "INFO"        # blue — informational
    WARNING = "WARNING"  # amber — degraded but usable
    CRITICAL = "CRITICAL"  # red — do not act on this data


# Quality state → default severity mapping
_SEVERITY_MAP: Dict[DataQualityState, QualitySeverity] = {
    DataQualityState.REAL_TIME: QualitySeverity.OK,
    DataQualityState.DELAYED: QualitySeverity.INFO,
    DataQualityState.FRESH: QualitySeverity.OK,
    DataQualityState.AGING: QualitySeverity.INFO,
    DataQualityState.STALE: QualitySeverity.WARNING,
    DataQualityState.PARTIAL: QualitySeverity.WARNING,
    DataQualityState.DEGRADED: QualitySeverity.WARNING,
    DataQualityState.SYNTHETIC: QualitySeverity.INFO,
    DataQualityState.UNAVAILABLE: QualitySeverity.CRITICAL,
}


# ─────────────────────────────────────────────────────────────────────
# Data classes
# ─────────────────────────────────────────────────────────────────────

@dataclass
class FieldQuality:
    """Quality metadata for a single data field."""
    field_name: str
    state: DataQualityState
    age_seconds: Optional[float] = None
    missing_fields: List[str] = field(default_factory=list)
    confidence_reduction: float = 0.0  # 0–1, how much confidence was reduced
    source: str = ""
    reason: str = ""
    methodology: str = ""  # for SYNTHETIC data

    def to_dict(self) -> Dict[str, Any]:
        d: Dict[str, Any] = {
            "field": self.field_name,
            "state": self.state.value,
            "severity": _SEVERITY_MAP[self.state].value,
        }
        if self.age_seconds is not None:
            d["age_seconds"] = round(self.age_seconds, 1)
            d["age_human"] = _human_age(self.age_seconds)
        if self.missing_fields:
            d["missing_fields"] = self.missing_fields
            d["missing_count"] = len(self.missing_fields)
        if self.confidence_reduction > 0:
            d["confidence_reduction"] = round(self.confidence_reduction, 3)
        if self.source:
            d["source"] = self.source
        if self.reason:
            d["reason"] = self.reason
        if self.methodology:
            d["methodology"] = self.methodology
        return d


@dataclass
class DataQualityReport:
    """Aggregated quality report for a card, signal, or portfolio.

    The *overall* state is the worst state across all fields.
    """
    overall_state: DataQualityState = DataQualityState.REAL_TIME
    overall_severity: QualitySeverity = QualitySeverity.OK
    fields: List[FieldQuality] = field(default_factory=list)
    as_of: str = ""
    escalation_triggered: bool = False
    escalation_reasons: List[str] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "overall_state": self.overall_state.value,
            "overall_severity": self.overall_severity.value,
            "fields": [f.to_dict() for f in self.fields],
            "as_of": self.as_of,
            "escalation_triggered": self.escalation_triggered,
            "escalation_reasons": self.escalation_reasons,
        }

    def summary_line(self) -> str:
        """One-liner for cards."""
        parts = [f"Data: {self.overall_state.value}"]
        if self.escalation_triggered:
            parts.append("⚠ ESCALATED")
        return " | ".join(parts)


@dataclass
class PortfolioQualitySummary:
    """Aggregate quality summary across all holdings."""
    total_holdings: int = 0
    by_state: Dict[str, int] = field(default_factory=dict)
    worst_state: DataQualityState = DataQualityState.REAL_TIME
    escalation_count: int = 0
    holdings_with_issues: List[Dict[str, Any]] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "total_holdings": self.total_holdings,
            "by_state": self.by_state,
            "worst_state": self.worst_state.value,
            "escalation_count": self.escalation_count,
            "holdings_with_issues": self.holdings_with_issues,
        }


# ─────────────────────────────────────────────────────────────────────
# Engine
# ─────────────────────────────────────────────────────────────────────

class DataQualityEngine:
    """Evaluates and aggregates data quality across signals and portfolios.

    Usage::

        engine = DataQualityEngine()
        report = engine.evaluate_signal_quality(signal_dict)
        portfolio_summary = engine.summarize_portfolio(holding_reports)
    """

    # Thresholds
    STALE_THRESHOLD_S = 2 * 3600       # 2 hours
    AGING_THRESHOLD_S = 15 * 60        # 15 minutes
    REAL_TIME_THRESHOLD_S = 15         # 15 seconds
    DEGRADED_CONFIDENCE_THRESHOLD = 0.3  # 30% reduction → warning

    def evaluate_signal_quality(
        self,
        signal: Dict[str, Any],
        *,
        now: Optional[datetime] = None,
    ) -> DataQualityReport:
        """Evaluate quality for a single signal's data fields."""
        now = now or datetime.now(timezone.utc)
        report = DataQualityReport(as_of=now.isoformat())
        fields: List[FieldQuality] = []

        # Price data quality
        price_field = self._eval_price_quality(signal, now)
        if price_field:
            fields.append(price_field)

        # Volume data quality
        vol_field = self._eval_volume_quality(signal, now)
        if vol_field:
            fields.append(vol_field)

        # Fundamental data quality
        fund_field = self._eval_fundamental_quality(signal)
        if fund_field:
            fields.append(fund_field)

        # News / catalyst quality
        news_field = self._eval_news_quality(signal, now)
        if news_field:
            fields.append(news_field)

        # Model / confidence quality
        model_field = self._eval_model_quality(signal)
        if model_field:
            fields.append(model_field)

        # Trust metadata from signal
        trust = signal.get("trust", {})
        if trust.get("mode") == "SYNTHETIC":
            fields.append(FieldQuality(
                field_name="execution_mode",
                state=DataQualityState.SYNTHETIC,
                source="trust_metadata",
                reason="Signal generated from synthetic/heuristic data",
                methodology=trust.get("methodology", "heuristic"),
            ))

        report.fields = fields
        report.overall_state = self._worst_state(fields)
        report.overall_severity = _SEVERITY_MAP[report.overall_state]

        # Check escalation
        report.escalation_triggered, report.escalation_reasons = (
            self._check_escalation(fields, signal)
        )

        return report

    def evaluate_holding_quality(
        self,
        ticker: str,
        holding: Dict[str, Any],
        *,
        now: Optional[datetime] = None,
    ) -> DataQualityReport:
        """Evaluate quality for a single portfolio holding."""
        now = now or datetime.now(timezone.utc)
        report = DataQualityReport(as_of=now.isoformat())
        fields: List[FieldQuality] = []

        # Last price age
        last_update = holding.get("last_update") or holding.get("last_price_at")
        if last_update:
            try:
                dt = datetime.fromisoformat(last_update.replace("Z", "+00:00"))
                age = (now - dt).total_seconds()
                state = self._age_to_state(age)
                fields.append(FieldQuality(
                    field_name="last_price",
                    state=state,
                    age_seconds=age,
                    source=holding.get("price_source", "unknown"),
                ))
            except (ValueError, TypeError):
                fields.append(FieldQuality(
                    field_name="last_price",
                    state=DataQualityState.UNAVAILABLE,
                    reason="Cannot parse last update timestamp",
                ))
        else:
            fields.append(FieldQuality(
                field_name="last_price",
                state=DataQualityState.UNAVAILABLE,
                reason="No last_update timestamp on holding",
            ))

        # Check for missing fields
        required = ["ticker", "shares", "avg_cost", "current_price"]
        missing = [f for f in required if not holding.get(f)]
        if missing:
            fields.append(FieldQuality(
                field_name="holding_fields",
                state=DataQualityState.PARTIAL,
                missing_fields=missing,
                reason=f"Missing {len(missing)} required field(s)",
            ))

        report.fields = fields
        report.overall_state = self._worst_state(fields)
        report.overall_severity = _SEVERITY_MAP[report.overall_state]
        report.escalation_triggered, report.escalation_reasons = (
            self._check_escalation(fields, {"ticker": ticker})
        )
        return report

    def summarize_portfolio(
        self,
        holding_reports: Dict[str, DataQualityReport],
    ) -> PortfolioQualitySummary:
        """Aggregate quality across all holdings."""
        summary = PortfolioQualitySummary(
            total_holdings=len(holding_reports),
        )
        state_counts: Dict[str, int] = {}
        worst = DataQualityState.REAL_TIME
        worst_rank = list(DataQualityState).index(worst)

        for ticker, report in holding_reports.items():
            state_val = report.overall_state.value
            state_counts[state_val] = state_counts.get(state_val, 0) + 1

            rank = list(DataQualityState).index(report.overall_state)
            if rank > worst_rank:
                worst = report.overall_state
                worst_rank = rank

            if report.escalation_triggered:
                summary.escalation_count += 1
                summary.holdings_with_issues.append({
                    "ticker": ticker,
                    "state": report.overall_state.value,
                    "severity": report.overall_severity.value,
                    "reasons": report.escalation_reasons,
                })

        summary.by_state = state_counts
        summary.worst_state = worst
        return summary

    # ── Private helpers ──────────────────────────────────────────────

    def _eval_price_quality(
        self, signal: Dict, now: datetime
    ) -> Optional[FieldQuality]:
        price_ts = signal.get("price_timestamp") or signal.get("as_of")
        if not price_ts:
            # Check if trust metadata has freshness info
            trust = signal.get("trust", {})
            freshness = trust.get("freshness", "")
            if freshness == "REAL_TIME":
                return FieldQuality(
                    field_name="price", state=DataQualityState.REAL_TIME,
                    source="trust_metadata",
                )
            elif freshness == "DELAYED":
                return FieldQuality(
                    field_name="price", state=DataQualityState.DELAYED,
                    source="trust_metadata",
                )
            return None
        try:
            dt = datetime.fromisoformat(str(price_ts).replace("Z", "+00:00"))
            age = (now - dt).total_seconds()
            return FieldQuality(
                field_name="price",
                state=self._age_to_state(age),
                age_seconds=age,
                source=signal.get("price_source", ""),
            )
        except (ValueError, TypeError):
            return None

    def _eval_volume_quality(
        self, signal: Dict, now: datetime
    ) -> Optional[FieldQuality]:
        vol = signal.get("volume") or signal.get("avg_volume")
        if vol is None or vol == 0:
            return FieldQuality(
                field_name="volume",
                state=DataQualityState.PARTIAL,
                reason="Volume data missing or zero",
            )
        return None  # volume present → OK

    def _eval_fundamental_quality(self, signal: Dict) -> Optional[FieldQuality]:
        fund = signal.get("fundamentals", {})
        if not fund:
            return FieldQuality(
                field_name="fundamentals",
                state=DataQualityState.PARTIAL,
                reason="No fundamental data available",
                missing_fields=["pe_ratio", "revenue_growth", "market_cap"],
            )
        missing = [k for k in ("pe_ratio", "revenue_growth", "market_cap")
                   if not fund.get(k)]
        if len(missing) >= 2:
            return FieldQuality(
                field_name="fundamentals",
                state=DataQualityState.PARTIAL,
                missing_fields=missing,
            )
        return None

    def _eval_news_quality(
        self, signal: Dict, now: datetime
    ) -> Optional[FieldQuality]:
        news_ts = signal.get("news_freshness")
        if not news_ts:
            return FieldQuality(
                field_name="news",
                state=DataQualityState.PARTIAL,
                reason="No news/catalyst data attached",
            )
        try:
            dt = datetime.fromisoformat(str(news_ts).replace("Z", "+00:00"))
            age = (now - dt).total_seconds()
            return FieldQuality(
                field_name="news",
                state=self._age_to_state(age),
                age_seconds=age,
            )
        except (ValueError, TypeError):
            return None

    def _eval_model_quality(self, signal: Dict) -> Optional[FieldQuality]:
        confidence = signal.get("confidence")
        if confidence is None:
            return None
        # Check for degraded confidence
        raw = signal.get("raw_confidence")
        if raw and raw > 0:
            reduction = (raw - confidence) / raw
            if reduction >= self.DEGRADED_CONFIDENCE_THRESHOLD:
                return FieldQuality(
                    field_name="model_confidence",
                    state=DataQualityState.DEGRADED,
                    confidence_reduction=reduction,
                    reason=(
                        f"Confidence reduced {reduction:.0%} from raw "
                        f"{raw:.2f} → calibrated {confidence:.2f}"
                    ),
                )
        return None

    def _age_to_state(self, age_seconds: float) -> DataQualityState:
        if age_seconds < self.REAL_TIME_THRESHOLD_S:
            return DataQualityState.REAL_TIME
        elif age_seconds < self.AGING_THRESHOLD_S:
            return DataQualityState.FRESH
        elif age_seconds < self.STALE_THRESHOLD_S:
            return DataQualityState.AGING
        else:
            return DataQualityState.STALE

    def _worst_state(self, fields: List[FieldQuality]) -> DataQualityState:
        if not fields:
            return DataQualityState.REAL_TIME
        worst_rank = 0
        worst = fields[0].state
        for f in fields:
            rank = list(DataQualityState).index(f.state)
            if rank > worst_rank:
                worst = f.state
                worst_rank = rank
        return worst

    def _check_escalation(
        self,
        fields: List[FieldQuality],
        context: Dict[str, Any],
    ) -> tuple[bool, List[str]]:
        """Check if quality issues warrant escalation."""
        reasons: List[str] = []
        ticker = context.get("ticker", "—")

        for f in fields:
            if f.state == DataQualityState.STALE:
                reasons.append(
                    f"{ticker}: {f.field_name} is STALE "
                    f"({f.age_human if f.age_seconds else 'unknown age'})"
                )
            elif f.state == DataQualityState.UNAVAILABLE:
                reasons.append(
                    f"{ticker}: {f.field_name} is UNAVAILABLE — {f.reason}"
                )
            elif (f.state == DataQualityState.DEGRADED
                  and f.confidence_reduction >= self.DEGRADED_CONFIDENCE_THRESHOLD):
                reasons.append(
                    f"{ticker}: {f.field_name} confidence degraded "
                    f"{f.confidence_reduction:.0%}"
                )
            elif (f.state == DataQualityState.SYNTHETIC
                  and context.get("trust", {}).get("mode") == "LIVE"):
                reasons.append(
                    f"{ticker}: SYNTHETIC data in LIVE mode — BLOCK"
                )

        return (len(reasons) > 0, reasons)


# ─────────────────────────────────────────────────────────────────────
# Helpers
# ─────────────────────────────────────────────────────────────────────

def _human_age(seconds: float) -> str:
    """Convert seconds to human-readable age string."""
    if seconds < 60:
        return f"{int(seconds)}s"
    elif seconds < 3600:
        return f"{int(seconds / 60)}m"
    elif seconds < 86400:
        return f"{int(seconds / 3600)}h {int((seconds % 3600) / 60)}m"
    else:
        return f"{int(seconds / 86400)}d {int((seconds % 86400) / 3600)}h"
