"""
CC — Sector-Aware Discord Alert Builder
=========================================
Builds Discord embeds with full sector-adaptive context.

Alert Taxonomy:
  URGENT       — Immediate action needed
  ACTIONABLE   — Trade-worthy setup
  WATCHLIST    — Promising, needs confirmation
  INFORMATIONAL — FYI / context update
  MACRO_WARNING — Market/macro risk alert
  NO_TRADE     — Explicit avoid signal
  REVIEW       — Post-trade review reminder
  PORTFOLIO    — Portfolio risk alert

Channel Routing:
  #top-opportunities    — ACTIONABLE/URGENT
  #growth-ai            — HIGH_GROWTH signals
  #cyclical-macro        — CYCLICAL signals
  #defensive-rotation    — DEFENSIVE signals
  #theme-speculation     — THEME_HYPE signals
  #pattern-upgrades      — VCP/breakout upgrades
  #earnings-risk         — Earnings proximity warnings
  #no-trade-alerts       — Explicit no-trade signals
  #portfolio-brief       — Daily portfolio summary
  #post-trade-review     — Review reminders
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Dict, List

from src.engines.sector_classifier import SectorBucket

logger = logging.getLogger(__name__)


class AlertType(str, Enum):
    URGENT = "URGENT"
    ACTIONABLE = "ACTIONABLE"
    WATCHLIST = "WATCHLIST"
    INFORMATIONAL = "INFORMATIONAL"
    MACRO_WARNING = "MACRO_WARNING"
    NO_TRADE = "NO_TRADE"
    REVIEW = "REVIEW"
    PORTFOLIO = "PORTFOLIO"


# Sector → Discord channel mapping
_SECTOR_CHANNELS: Dict[SectorBucket, str] = {
    SectorBucket.HIGH_GROWTH: "growth-ai",
    SectorBucket.CYCLICAL: "cyclical-macro",
    SectorBucket.DEFENSIVE: "defensive-rotation",
    SectorBucket.THEME_HYPE: "theme-speculation",
    SectorBucket.UNKNOWN: "top-opportunities",
}


@dataclass
class SectorAlert:
    """Full sector-aware alert for Discord delivery."""

    ticker: str = ""
    alert_type: AlertType = AlertType.INFORMATIONAL
    channel: str = "top-opportunities"

    # Core decision
    action: str = ""
    grade: str = ""
    final_confidence: float = 0.0
    risk_level: str = ""

    # Sector context
    sector_bucket: str = ""
    theme: str = ""
    sector_stage: str = ""
    leader_status: str = ""
    strategy: str = ""

    # Confidence breakdown
    thesis_conf: float = 0.0
    timing_conf: float = 0.0
    execution_conf: float = 0.0
    data_conf: float = 0.0

    # Trade details
    entry_zone: str = ""
    invalidation: str = ""
    take_profit: str = ""

    # Explanation
    why_now: str = ""
    why_not_stronger: str = ""
    key_evidence: List[str] = field(default_factory=list)
    key_contradiction: List[str] = field(default_factory=list)
    better_alternative: str = ""

    # Conflict
    conflict_level: str = "LOW"

    # Freshness
    data_freshness: str = "live"

    def to_embed_dict(self) -> Dict[str, Any]:
        """Convert to Discord embed-compatible dict."""
        # Color by alert type
        colors = {
            AlertType.URGENT: 0xFF0000,
            AlertType.ACTIONABLE: 0x00FF00,
            AlertType.WATCHLIST: 0xFFAA00,
            AlertType.NO_TRADE: 0x888888,
            AlertType.MACRO_WARNING: 0xFF6600,
            AlertType.REVIEW: 0x0066FF,
            AlertType.PORTFOLIO: 0x9900FF,
            AlertType.INFORMATIONAL: 0x3399FF,
        }

        # Action emoji
        action_emoji = {
            "TRADE": "🟢",
            "WATCH": "🟡",
            "WAIT": "⏳",
            "NO_TRADE": "🔴",
            "REDUCE": "⚠️",
            "EXIT": "🚪",
        }

        emoji = action_emoji.get(self.action, "📊")
        title = f"{emoji} {self.ticker} — " f"{self.action} ({self.grade})"

        fields = [
            {
                "name": "📍 Sector",
                "value": (
                    f"{self.theme or self.sector_bucket}\n"
                    f"Stage: {self.sector_stage} | "
                    f"Leader: {self.leader_status}"
                ),
                "inline": True,
            },
            {
                "name": "📊 Confidence",
                "value": (
                    f"Thesis: {self.thesis_conf:.0%}\n"
                    f"Timing: {self.timing_conf:.0%}\n"
                    f"Execution: {self.execution_conf:.0%}\n"
                    f"Data: {self.data_conf:.0%}\n"
                    f"**Final: {self.final_confidence:.0%}**"
                ),
                "inline": True,
            },
            {
                "name": "🎯 Setup",
                "value": (
                    f"Strategy: {self.strategy}\n"
                    f"Entry: {self.entry_zone}\n"
                    f"Invalidation: {self.invalidation}\n"
                    f"Risk: {self.risk_level}"
                ),
                "inline": True,
            },
            {
                "name": "💡 Why Now",
                "value": self.why_now or "—",
                "inline": False,
            },
        ]

        if self.why_not_stronger:
            fields.append(
                {
                    "name": "⚠️ Why Not Stronger",
                    "value": self.why_not_stronger,
                    "inline": False,
                }
            )

        if self.key_contradiction:
            fields.append(
                {
                    "name": "🔴 Contradictions",
                    "value": "\n".join(f"• {c}" for c in self.key_contradiction[:3]),
                    "inline": False,
                }
            )

        if self.better_alternative:
            fields.append(
                {
                    "name": "🔄 Better Alternative",
                    "value": self.better_alternative,
                    "inline": False,
                }
            )

        return {
            "title": title,
            "color": colors.get(self.alert_type, 0x3399FF),
            "fields": fields,
            "footer": {
                "text": (
                    f"Conflict: {self.conflict_level} | " f"Data: {self.data_freshness}"
                ),
            },
        }


class SectorAlertBuilder:
    """Build sector-aware Discord alerts from pipeline results."""

    def build(self, pipeline_result) -> SectorAlert:
        """Build alert from a PipelineResult."""
        r = pipeline_result
        sig = r.signal
        ticker = sig.get("ticker", "")

        alert = SectorAlert(ticker=ticker)

        # Alert type from action
        action = r.decision.action
        if action == "TRADE" and r.confidence.final >= 0.7:
            alert.alert_type = AlertType.URGENT
        elif action == "TRADE":
            alert.alert_type = AlertType.ACTIONABLE
        elif action == "WATCH":
            alert.alert_type = AlertType.WATCHLIST
        elif action == "NO_TRADE":
            alert.alert_type = AlertType.NO_TRADE
        elif action in ("REDUCE", "EXIT"):
            alert.alert_type = AlertType.MACRO_WARNING
        else:
            alert.alert_type = AlertType.INFORMATIONAL

        # Channel routing
        bucket = r.sector.sector_bucket
        if alert.alert_type == AlertType.NO_TRADE:
            alert.channel = "no-trade-alerts"
        elif alert.alert_type in (AlertType.URGENT, AlertType.ACTIONABLE):
            alert.channel = "top-opportunities"
        else:
            alert.channel = _SECTOR_CHANNELS.get(bucket, "top-opportunities")

        # Core fields
        alert.action = action
        alert.grade = r.fit.grade
        alert.final_confidence = r.confidence.final
        alert.risk_level = r.decision.risk_level

        # Sector context
        alert.sector_bucket = bucket.value
        alert.theme = r.sector.theme
        alert.sector_stage = r.sector.sector_stage.value
        alert.leader_status = r.sector.leader_status.value
        alert.strategy = sig.get("strategy", "")

        # Confidence breakdown
        alert.thesis_conf = r.confidence.thesis
        alert.timing_conf = r.confidence.timing
        alert.execution_conf = r.confidence.execution
        alert.data_conf = r.confidence.data

        # Trade details
        alert.entry_zone = sig.get("entry_zone", "")
        alert.invalidation = r.explanation.invalidation
        alert.take_profit = sig.get("take_profit", "")

        # Explanation
        alert.why_now = r.explanation.why_now
        alert.why_not_stronger = r.explanation.why_not_stronger
        alert.key_evidence = r.explanation.key_evidence
        alert.key_contradiction = r.explanation.key_contradiction
        alert.better_alternative = r.explanation.better_alternative

        # Conflict
        if r.conflict:
            alert.conflict_level = r.conflict.conflict_level

        return alert

    def build_batch(self, results) -> List[SectorAlert]:
        """Build alerts for all pipeline results."""
        return [self.build(r) for r in results]

    def filter_actionable(self, alerts: List[SectorAlert]) -> List[SectorAlert]:
        """Filter to only actionable alerts worth sending."""
        return [
            a
            for a in alerts
            if a.alert_type
            in (
                AlertType.URGENT,
                AlertType.ACTIONABLE,
                AlertType.NO_TRADE,
                AlertType.MACRO_WARNING,
            )
        ]
