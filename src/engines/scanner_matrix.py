"""
CC — Scanner Matrix
=====================
Registry of scanners organized by category:
  A. Pattern — VCP, breakout, pullback, squeeze, RS leader
  B. Flow — abnormal volume, options, insider, institutional
  C. Sector — rotation, leader/laggard, crowding, breadth
  D. Risk — earnings, extension, liquidity, spread, macro
  E. Validation — similar outcomes, edge decay, calibration

Each scanner returns ScannerHit objects that feed into the
ranked opportunity pipeline.
"""

from __future__ import annotations

import logging
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Dict, List

logger = logging.getLogger(__name__)


# ── Scanner Category ─────────────────────────────────────────────────


class ScannerCategory(str, Enum):
    PATTERN = "PATTERN"
    FLOW = "FLOW"
    SECTOR = "SECTOR"
    RISK = "RISK"
    VALIDATION = "VALIDATION"


class ScannerPriority(str, Enum):
    URGENT = "URGENT"  # Immediate action needed
    HIGH = "HIGH"  # High attention
    NORMAL = "NORMAL"
    LOW = "LOW"  # Background monitoring


@dataclass
class ScannerHit:
    """A single scanner detection result."""

    scanner_name: str
    category: ScannerCategory
    ticker: str
    priority: ScannerPriority = ScannerPriority.NORMAL
    score: float = 0.0  # 0-10
    headline: str = ""
    detail: str = ""
    is_warning: bool = False  # Risk scanners produce warnings
    metadata: Dict[str, Any] = field(default_factory=dict)
    timestamp: str = ""

    def to_dict(self) -> Dict[str, Any]:
        return {
            "scanner": self.scanner_name,
            "category": self.category.value,
            "ticker": self.ticker,
            "priority": self.priority.value,
            "score": round(self.score, 1),
            "headline": self.headline,
            "detail": self.detail,
            "is_warning": self.is_warning,
            "metadata": self.metadata,
        }


class BaseScanner(ABC):
    """Scanner interface."""

    name: str = "base"
    category: ScannerCategory = ScannerCategory.PATTERN

    @abstractmethod
    def scan(
        self,
        signals: List[Dict[str, Any]],
        regime: Dict[str, Any],
    ) -> List[ScannerHit]: ...


# ═════════════════════════════════════════════════════════════════════
# A. PATTERN SCANNERS
# ═════════════════════════════════════════════════════════════════════


class VCPScanner(BaseScanner):
    name = "vcp"
    category = ScannerCategory.PATTERN

    def scan(self, signals, regime) -> List[ScannerHit]:
        hits = []
        for sig in signals:
            strategy = sig.get("strategy", "").lower()
            pattern = sig.get("pattern", "").lower()
            cc = sig.get("contraction_count", 0)
            if "vcp" in strategy or "vcp" in pattern or cc >= 2:
                score = min(10, sig.get("score", 5) + cc * 0.5)
                hits.append(
                    ScannerHit(
                        scanner_name=self.name,
                        category=self.category,
                        ticker=sig.get("ticker", ""),
                        score=score,
                        headline=f"VCP ({cc} contractions)",
                        detail=f"Base depth {sig.get('base_depth_pct', 0):.0f}%",
                        priority=(
                            ScannerPriority.HIGH
                            if score >= 7
                            else ScannerPriority.NORMAL
                        ),
                        metadata={"contraction_count": cc},
                    )
                )
        return hits


class BreakoutScanner(BaseScanner):
    name = "breakout"
    category = ScannerCategory.PATTERN

    def scan(self, signals, regime) -> List[ScannerHit]:
        hits = []
        for sig in signals:
            strategy = sig.get("strategy", "").lower()
            if "breakout" in strategy or sig.get("is_breakout", False):
                vol = sig.get("vol_ratio", 1.0)
                score = min(10, sig.get("score", 5))
                if vol > 1.5:
                    score = min(10, score + 1.0)
                hits.append(
                    ScannerHit(
                        scanner_name=self.name,
                        category=self.category,
                        ticker=sig.get("ticker", ""),
                        score=score,
                        headline=f"Breakout (vol {vol:.1f}x)",
                        priority=(
                            ScannerPriority.HIGH
                            if vol > 2.0
                            else ScannerPriority.NORMAL
                        ),
                    )
                )
        return hits


class PullbackScanner(BaseScanner):
    name = "pullback"
    category = ScannerCategory.PATTERN

    def scan(self, signals, regime) -> List[ScannerHit]:
        hits = []
        for sig in signals:
            strategy = sig.get("strategy", "").lower()
            if "pullback" in strategy or "retracement" in strategy:
                hits.append(
                    ScannerHit(
                        scanner_name=self.name,
                        category=self.category,
                        ticker=sig.get("ticker", ""),
                        score=sig.get("score", 5),
                        headline="Pullback to support",
                    )
                )
        return hits


class SqueezeScanner(BaseScanner):
    name = "squeeze"
    category = ScannerCategory.PATTERN

    def scan(self, signals, regime) -> List[ScannerHit]:
        hits = []
        for sig in signals:
            bb_width = sig.get("bb_width", 999)
            atr_pct = sig.get("atr_pct", 5)
            if bb_width < 4 or atr_pct < 1.5:
                hits.append(
                    ScannerHit(
                        scanner_name=self.name,
                        category=self.category,
                        ticker=sig.get("ticker", ""),
                        score=min(10, 8 - bb_width * 0.5),
                        headline="Tight squeeze / contraction",
                        detail=f"BB width {bb_width:.1f}, ATR {atr_pct:.1f}%",
                    )
                )
        return hits


class RSLeaderScanner(BaseScanner):
    name = "rs_leader"
    category = ScannerCategory.PATTERN

    def scan(self, signals, regime) -> List[ScannerHit]:
        hits = []
        for sig in signals:
            rs = sig.get("rs_rank", 50)
            if rs >= 85:
                hits.append(
                    ScannerHit(
                        scanner_name=self.name,
                        category=self.category,
                        ticker=sig.get("ticker", ""),
                        score=min(10, rs / 10),
                        headline=f"RS Leader (rank {rs})",
                        priority=ScannerPriority.HIGH,
                    )
                )
        return hits


class MeanReversionScanner(BaseScanner):
    name = "mean_reversion"
    category = ScannerCategory.PATTERN

    def scan(self, signals, regime) -> List[ScannerHit]:
        hits = []
        for sig in signals:
            rsi = sig.get("rsi", 50)
            if rsi < 30:
                hits.append(
                    ScannerHit(
                        scanner_name=self.name,
                        category=self.category,
                        ticker=sig.get("ticker", ""),
                        score=min(10, (30 - rsi) / 3 + 5),
                        headline=f"Oversold RSI {rsi:.0f}",
                    )
                )
        return hits


class BreakdownScanner(BaseScanner):
    name = "breakdown_risk"
    category = ScannerCategory.PATTERN

    def scan(self, signals, regime) -> List[ScannerHit]:
        hits = []
        for sig in signals:
            if sig.get("is_breakdown", False) or sig.get("rsi", 50) < 25:
                hits.append(
                    ScannerHit(
                        scanner_name=self.name,
                        category=self.category,
                        ticker=sig.get("ticker", ""),
                        score=sig.get("score", 5),
                        headline="Breakdown / Exit Risk",
                        is_warning=True,
                        priority=ScannerPriority.URGENT,
                    )
                )
        return hits


# ═════════════════════════════════════════════════════════════════════
# B. FLOW SCANNERS
# ═════════════════════════════════════════════════════════════════════


class AbnormalVolumeScanner(BaseScanner):
    name = "abnormal_volume"
    category = ScannerCategory.FLOW

    def scan(self, signals, regime) -> List[ScannerHit]:
        hits = []
        for sig in signals:
            vol = sig.get("vol_ratio", 1.0)
            if vol >= 2.0:
                hits.append(
                    ScannerHit(
                        scanner_name=self.name,
                        category=self.category,
                        ticker=sig.get("ticker", ""),
                        score=min(10, 5 + vol),
                        headline=f"Abnormal volume {vol:.1f}x",
                        priority=(
                            ScannerPriority.HIGH if vol > 3 else ScannerPriority.NORMAL
                        ),
                        metadata={"vol_ratio": vol},
                    )
                )
        return hits


class OptionsFlowScanner(BaseScanner):
    name = "options_flow"
    category = ScannerCategory.FLOW

    def scan(self, signals, regime) -> List[ScannerHit]:
        hits = []
        for sig in signals:
            if sig.get("options_bullish", False) or sig.get("unusual_options", False):
                hits.append(
                    ScannerHit(
                        scanner_name=self.name,
                        category=self.category,
                        ticker=sig.get("ticker", ""),
                        score=7.0,
                        headline="Unusual options activity",
                        priority=ScannerPriority.HIGH,
                    )
                )
        return hits


class InsiderScanner(BaseScanner):
    name = "insider_activity"
    category = ScannerCategory.FLOW

    def scan(self, signals, regime) -> List[ScannerHit]:
        hits = []
        for sig in signals:
            if sig.get("insider_buy", False):
                hits.append(
                    ScannerHit(
                        scanner_name=self.name,
                        category=self.category,
                        ticker=sig.get("ticker", ""),
                        score=7.5,
                        headline="Insider buying",
                        detail=sig.get("insider_detail", ""),
                        priority=ScannerPriority.HIGH,
                    )
                )
        return hits


class InstitutionalScanner(BaseScanner):
    name = "institutional_flow"
    category = ScannerCategory.FLOW

    def scan(self, signals, regime) -> List[ScannerHit]:
        hits = []
        for sig in signals:
            if sig.get("institutional_buy", False):
                hits.append(
                    ScannerHit(
                        scanner_name=self.name,
                        category=self.category,
                        ticker=sig.get("ticker", ""),
                        score=8.0,
                        headline="Institutional accumulation",
                        priority=ScannerPriority.HIGH,
                    )
                )
        return hits


# ═════════════════════════════════════════════════════════════════════
# C. SECTOR / ROTATION SCANNERS
# ═════════════════════════════════════════════════════════════════════


class SectorRotationScanner(BaseScanner):
    name = "sector_rotation"
    category = ScannerCategory.SECTOR

    def scan(self, signals, regime) -> List[ScannerHit]:
        # Aggregate by sector and detect rotation
        from collections import defaultdict

        sector_scores = defaultdict(list)
        for sig in signals:
            bucket = sig.get("sector_bucket", "UNKNOWN")
            rs = sig.get("rs_rank", 50)
            sector_scores[bucket].append(rs)

        hits = []
        for bucket, rs_list in sector_scores.items():
            avg_rs = sum(rs_list) / len(rs_list) if rs_list else 50
            if avg_rs > 70:
                hits.append(
                    ScannerHit(
                        scanner_name=self.name,
                        category=self.category,
                        ticker=bucket,
                        score=min(10, avg_rs / 10),
                        headline=f"{bucket} sector rotation (avg RS {avg_rs:.0f})",
                    )
                )
        return hits


class LeaderLaggardScanner(BaseScanner):
    name = "leader_laggard"
    category = ScannerCategory.SECTOR

    def scan(self, signals, regime) -> List[ScannerHit]:
        hits = []
        for sig in signals:
            rs = sig.get("rs_rank", 50)
            vol = sig.get("vol_ratio", 1.0)
            # Laggard with high volume = potential late chase
            if rs < 40 and vol > 2.0:
                hits.append(
                    ScannerHit(
                        scanner_name=self.name,
                        category=self.category,
                        ticker=sig.get("ticker", ""),
                        score=4.0,
                        headline="Laggard with volume surge",
                        detail="Late chase risk — leader likely peaked",
                        is_warning=True,
                    )
                )
        return hits


# ═════════════════════════════════════════════════════════════════════
# D. RISK SCANNERS
# ═════════════════════════════════════════════════════════════════════


class EarningsRiskScanner(BaseScanner):
    name = "earnings_risk"
    category = ScannerCategory.RISK

    def scan(self, signals, regime) -> List[ScannerHit]:
        hits = []
        for sig in signals:
            dte = sig.get("days_to_earnings", 30)
            if dte < 7:
                hits.append(
                    ScannerHit(
                        scanner_name=self.name,
                        category=self.category,
                        ticker=sig.get("ticker", ""),
                        score=3.0,
                        headline=f"Earnings in {dte} days",
                        is_warning=True,
                        priority=ScannerPriority.URGENT,
                    )
                )
        return hits


class ExtensionRiskScanner(BaseScanner):
    name = "extension_risk"
    category = ScannerCategory.RISK

    def scan(self, signals, regime) -> List[ScannerHit]:
        hits = []
        for sig in signals:
            dist = sig.get("distance_from_50ma_pct", 0)
            rsi = sig.get("rsi", 50)
            if dist > 15 or rsi > 78:
                hits.append(
                    ScannerHit(
                        scanner_name=self.name,
                        category=self.category,
                        ticker=sig.get("ticker", ""),
                        score=3.0,
                        headline=f"Extended ({dist:.0f}% above 50MA, RSI {rsi:.0f})",
                        is_warning=True,
                    )
                )
        return hits


class LowLiquidityScanner(BaseScanner):
    name = "low_liquidity"
    category = ScannerCategory.RISK

    def scan(self, signals, regime) -> List[ScannerHit]:
        hits = []
        for sig in signals:
            vol = sig.get("avg_volume", 1_000_000)
            if vol < 200_000:
                hits.append(
                    ScannerHit(
                        scanner_name=self.name,
                        category=self.category,
                        ticker=sig.get("ticker", ""),
                        score=3.0,
                        headline=f"Low liquidity ({vol:,.0f} avg vol)",
                        is_warning=True,
                    )
                )
        return hits


class MacroRiskScanner(BaseScanner):
    name = "macro_risk"
    category = ScannerCategory.RISK

    def scan(self, signals, regime) -> List[ScannerHit]:
        hits = []
        macro_event = regime.get("macro_event_nearby", False)
        if macro_event:
            event_name = regime.get("next_macro_event", "macro release")
            # Warn all signals
            for sig in signals:
                hits.append(
                    ScannerHit(
                        scanner_name=self.name,
                        category=self.category,
                        ticker=sig.get("ticker", ""),
                        score=4.0,
                        headline=f"Macro risk: {event_name}",
                        is_warning=True,
                    )
                )
        return hits


class ConfidenceConflictScanner(BaseScanner):
    name = "confidence_conflict"
    category = ScannerCategory.RISK

    def scan(self, signals, regime) -> List[ScannerHit]:
        hits = []
        for sig in signals:
            # High score but low confidence
            score = sig.get("score", 5)
            conf = sig.get("confidence", 0.5)
            if score >= 7 and conf < 0.4:
                hits.append(
                    ScannerHit(
                        scanner_name=self.name,
                        category=self.category,
                        ticker=sig.get("ticker", ""),
                        score=4.0,
                        headline="Score/confidence mismatch",
                        detail=f"Score {score:.0f} but confidence {conf:.0%}",
                        is_warning=True,
                    )
                )
        return hits


class LateStageThemeScanner(BaseScanner):
    name = "late_stage_theme"
    category = ScannerCategory.RISK

    def scan(self, signals, regime) -> List[ScannerHit]:
        hits = []
        for sig in signals:
            bucket = sig.get("sector_bucket", "")
            stage = sig.get("sector_stage", "")
            if bucket == "THEME_HYPE" and stage in ("CLIMAX", "DISTRIBUTION"):
                hits.append(
                    ScannerHit(
                        scanner_name=self.name,
                        category=self.category,
                        ticker=sig.get("ticker", ""),
                        score=2.0,
                        headline=f"Theme in {stage} — avoid",
                        is_warning=True,
                        priority=ScannerPriority.URGENT,
                    )
                )
        return hits


# ═════════════════════════════════════════════════════════════════════
# E. VALIDATION SCANNERS
# ═════════════════════════════════════════════════════════════════════


class SimilarPatternScanner(BaseScanner):
    name = "similar_pattern"
    category = ScannerCategory.VALIDATION

    def scan(self, signals, regime) -> List[ScannerHit]:
        # Placeholder — would query historical pattern DB
        return []


class EdgeDecayScanner(BaseScanner):
    name = "edge_decay"
    category = ScannerCategory.VALIDATION

    def scan(self, signals, regime) -> List[ScannerHit]:
        # Placeholder — would check rolling performance
        return []


# ═════════════════════════════════════════════════════════════════════
# SCANNER REGISTRY
# ═════════════════════════════════════════════════════════════════════


class ScannerMatrix:
    """Central registry that runs all scanners."""

    def __init__(self):
        self.scanners: List[BaseScanner] = [
            # Pattern
            VCPScanner(),
            BreakoutScanner(),
            PullbackScanner(),
            SqueezeScanner(),
            RSLeaderScanner(),
            MeanReversionScanner(),
            BreakdownScanner(),
            # Flow
            AbnormalVolumeScanner(),
            OptionsFlowScanner(),
            InsiderScanner(),
            InstitutionalScanner(),
            # Sector
            SectorRotationScanner(),
            LeaderLaggardScanner(),
            # Risk
            EarningsRiskScanner(),
            ExtensionRiskScanner(),
            LowLiquidityScanner(),
            MacroRiskScanner(),
            ConfidenceConflictScanner(),
            LateStageThemeScanner(),
            # Validation
            SimilarPatternScanner(),
            EdgeDecayScanner(),
        ]

    def scan_all(
        self,
        signals: List[Dict[str, Any]],
        regime: Dict[str, Any],
    ) -> Dict[str, List[ScannerHit]]:
        """Run all scanners, return grouped by category."""
        results: Dict[str, List[ScannerHit]] = {c.value: [] for c in ScannerCategory}
        for scanner in self.scanners:
            try:
                hits = scanner.scan(signals, regime)
                results[scanner.category.value].extend(hits)
            except Exception as e:
                logger.warning("Scanner %s error: %s", scanner.name, e)
        return results

    def scan_category(
        self,
        category: ScannerCategory,
        signals: List[Dict[str, Any]],
        regime: Dict[str, Any],
    ) -> List[ScannerHit]:
        """Run scanners of a specific category."""
        hits = []
        for scanner in self.scanners:
            if scanner.category == category:
                try:
                    hits.extend(scanner.scan(signals, regime))
                except Exception as e:
                    logger.warning("Scanner %s error: %s", scanner.name, e)
        return hits

    def get_warnings(
        self,
        signals: List[Dict[str, Any]],
        regime: Dict[str, Any],
    ) -> List[ScannerHit]:
        """Get only warning/risk hits."""
        all_hits = self.scan_all(signals, regime)
        warnings = []
        for hits in all_hits.values():
            warnings.extend(h for h in hits if h.is_warning)
        return warnings

    def get_summary(
        self,
        signals: List[Dict[str, Any]],
        regime: Dict[str, Any],
    ) -> Dict[str, Any]:
        """Dashboard summary of scanner activity."""
        all_hits = self.scan_all(signals, regime)
        return {
            category: {
                "count": len(hits),
                "urgent": sum(1 for h in hits if h.priority == ScannerPriority.URGENT),
                "warnings": sum(1 for h in hits if h.is_warning),
                "top_hits": [
                    h.to_dict()
                    for h in sorted(hits, key=lambda x: x.score, reverse=True)[:5]
                ],
            }
            for category, hits in all_hits.items()
        }
