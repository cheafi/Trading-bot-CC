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
    # Decision-intent categories (map to underlying)
    LEADERS = "LEADERS"
    PULLBACKS = "PULLBACKS"
    BREAKOUTS = "BREAKOUTS"
    NO_TRADE = "NO_TRADE"


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
                        detail=(
                            f"Base depth"
                            f" {sig.get('base_depth_pct', 0):.0f}%"
                        ),
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
            bq = sig.get("breakout_quality")
            strategy = sig.get("strategy", "").lower()
            if bq or "breakout" in strategy:
                vol = sig.get("vol_ratio", 1.0)
                quality = bq or "unknown"
                score = {
                    "genuine": 8.5,
                    "weak": 5.5,
                    "fake": 2.0,
                    "exhaustion": 3.0,
                }.get(quality, 5.0)
                if vol > 1.5 and quality != "fake":
                    score = min(10, score + 1.0)
                hits.append(
                    ScannerHit(
                        scanner_name=self.name,
                        category=self.category,
                        ticker=sig.get("ticker", ""),
                        score=score,
                        headline=f"Breakout ({quality}, vol {vol:.1f}x)",
                        priority=(
                            ScannerPriority.HIGH
                            if quality == "genuine"
                            else ScannerPriority.NORMAL
                        ),
                        metadata={"breakout_quality": quality},
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
            is_breakdown = sig.get("is_breakdown", False)
            # Only fire RSI 25-30 zone; below 25 is BreakdownScanner territory
            # Skip if already flagged as breakdown
            if 25 <= rsi < 30 and not is_breakdown:
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
                            ScannerPriority.HIGH
                            if vol > 3
                            else ScannerPriority.NORMAL
                        ),
                        metadata={"vol_ratio": vol},
                    )
                )
        return hits


class VolumeSurgeScanner(BaseScanner):
    """Detects volume surges into tight ranges (heuristic proxy, NOT real options flow)."""

    name = "volume_surge"
    category = ScannerCategory.FLOW

    def scan(self, signals, regime) -> List[ScannerHit]:
        hits = []
        for sig in signals:
            # Detect unusual activity from computed fields:
            # High volume + near resistance + uptrend = smart money positioning
            vol = sig.get("vol_ratio", 1.0)
            at_res = sig.get("is_at_resistance", False)
            trend = sig.get("trend_structure", "")
            bb = sig.get("bb_width", 10)
            if vol >= 2.5 and trend in ("strong_uptrend", "uptrend") and bb < 5:
                hits.append(
                    ScannerHit(
                        scanner_name=self.name,
                        category=self.category,
                        ticker=sig.get("ticker", ""),
                        score=7.0,
                        headline=f"Unusual activity: {vol:.1f}x vol, tight BB ({bb:.1f})",
                        detail="Volume surge into tight range = potential breakout setup",
                        priority=ScannerPriority.HIGH,
                        metadata={
                            "vol_ratio": vol,
                            "bb_width": bb,
                            "data_source": "heuristic_proxy",
                        },
                    )
                )
        return hits


class QuietAccumulationScanner(BaseScanner):
    """Detects quiet accumulation patterns (heuristic proxy, NOT real insider data)."""

    name = "quiet_accumulation"
    category = ScannerCategory.FLOW

    def scan(self, signals, regime) -> List[ScannerHit]:
        hits = []
        for sig in signals:
            # Detect accumulation pattern: rising price on below-avg volume
            # (quiet accumulation) or strong uptrend + near support
            vol = sig.get("vol_ratio", 1.0)
            trend = sig.get("trend_structure", "")
            near_support = sig.get("is_near_support", False)
            rs = sig.get("rs_rank", 50)
            if trend in ("strong_uptrend", "uptrend") and vol < 0.8 and rs >= 70:
                hits.append(
                    ScannerHit(
                        scanner_name=self.name,
                        category=self.category,
                        ticker=sig.get("ticker", ""),
                        score=7.0,
                        headline="Quiet accumulation (low vol, strong RS)",
                        detail=f"RS rank {rs}, vol ratio {vol:.1f}x",
                        priority=ScannerPriority.HIGH,
                    )
                )
            elif near_support and trend in ("strong_uptrend", "uptrend"):
                hits.append(
                    ScannerHit(
                        scanner_name=self.name,
                        category=self.category,
                        ticker=sig.get("ticker", ""),
                        score=6.5,
                        headline="Pullback to support in uptrend",
                        priority=ScannerPriority.NORMAL,
                    )
                )
        return hits


class HighVolumeLeaderScanner(BaseScanner):
    """Detects high-volume RS leaders (heuristic proxy, NOT real 13F data)."""

    name = "high_volume_leader"
    category = ScannerCategory.FLOW

    def scan(self, signals, regime) -> List[ScannerHit]:
        hits = []
        for sig in signals:
            # Detect institutional-grade accumulation:
            # High volume + uptrend + leader RS = big money buying
            vol = sig.get("vol_ratio", 1.0)
            rs = sig.get("rs_rank", 50)
            trend = sig.get("trend_structure", "")
            vol_confirms = sig.get("volume_confirms", False)
            if vol >= 2.0 and rs >= 80 and vol_confirms:
                hits.append(
                    ScannerHit(
                        scanner_name=self.name,
                        category=self.category,
                        ticker=sig.get("ticker", ""),
                        score=8.0,
                        headline=f"Institutional accumulation ({vol:.1f}x vol, RS {rs})",
                        priority=ScannerPriority.HIGH,
                        metadata={"vol_ratio": vol, "rs_rank": rs},
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
                        headline=(
                            f"{bucket} sector"
                            f" rotation"
                            f" (avg RS"
                            f" {avg_rs:.0f})"
                        ),
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
                        headline=(
                            f"Extended"
                            f" ({dist:.0f}%"
                            f" above 50MA,"
                            f" RSI {rsi:.0f})"
                        ),
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
        """Find signals with similar structure patterns for cross-validation."""
        hits = []
        # Group signals by trend_structure + breakout_quality
        pattern_groups: Dict[str, List[Dict]] = {}
        for sig in signals:
            trend = sig.get("trend_structure", "unknown")
            bq = sig.get("breakout_quality", "none")
            key = f"{trend}_{bq}"
            pattern_groups.setdefault(key, []).append(sig)

        # Flag groups with 3+ similar patterns (cluster validation)
        for key, group in pattern_groups.items():
            if len(group) >= 3:
                tickers = [s.get("ticker", "?") for s in group[:5]]
                for sig in group:
                    hits.append(
                        ScannerHit(
                            scanner_name=self.name,
                            category=self.category,
                            ticker=sig.get("ticker", ""),
                            score=6.5,
                            headline=f"Pattern cluster: {len(group)} similar setups",
                            detail=f"Same pattern as: {', '.join(t for t in tickers if t != sig.get('ticker'))}",
                            metadata={"pattern_key": key, "cluster_size": len(group)},
                        )
                    )
        return hits


class EdgeDecayScanner(BaseScanner):
    name = "edge_decay"
    category = ScannerCategory.VALIDATION

    def scan(self, signals, regime) -> List[ScannerHit]:
        """Detect signals showing edge decay patterns."""
        hits = []
        for sig in signals:
            # Edge decay indicators:
            # - Volume exhaustion (climax volume after extended move)
            # - Fake breakout quality
            # - High extension + high RSI + crowding
            vol_exhaust = sig.get("volume_exhaustion", False)
            bq = sig.get("breakout_quality", "")
            is_extended = sig.get("is_extended", False)
            rsi = sig.get("rsi", 50)
            trap_risk = sig.get("liquidity_trap_risk", 0.0)

            warnings = []
            if vol_exhaust:
                warnings.append("volume exhaustion")
            if bq == "fake":
                warnings.append("fake breakout")
            if bq == "exhaustion":
                warnings.append("exhaustion breakout")
            if is_extended and rsi > 75:
                warnings.append(f"extended (RSI {rsi:.0f})")
            if trap_risk > 0.5:
                warnings.append(f"liquidity trap risk {trap_risk:.0%}")

            if len(warnings) >= 2:
                hits.append(
                    ScannerHit(
                        scanner_name=self.name,
                        category=self.category,
                        ticker=sig.get("ticker", ""),
                        score=3.0,
                        headline="Edge decay warning",
                        detail="; ".join(warnings),
                        is_warning=True,
                        priority=ScannerPriority.HIGH,
                        metadata={"decay_signals": warnings},
                    )
                )
        return hits


# ═════════════════════════════════════════════════════════════════════
# SCANNER REGISTRY
# Backward-compat aliases (old misleading names → honest names)
OptionsFlowScanner = VolumeSurgeScanner
InsiderScanner = QuietAccumulationScanner
InstitutionalScanner = HighVolumeLeaderScanner

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
            VolumeSurgeScanner(),
            QuietAccumulationScanner(),
            HighVolumeLeaderScanner(),
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
        results: Dict[str, List[ScannerHit]] = {
            c.value: [] for c in ScannerCategory
        }
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
                "urgent": sum(
                    1 for h in hits
                    if h.priority == ScannerPriority.URGENT
                ),
                "warnings": sum(1 for h in hits if h.is_warning),
                "top_hits": [
                    h.to_dict()
                    for h in sorted(
                        hits,
                        key=lambda x: x.score,
                        reverse=True,
                    )[:5]
                ],
            }
            for category, hits in all_hits.items()
        }
