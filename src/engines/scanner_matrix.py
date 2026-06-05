"""
CC — Scanner Matrix
=====================
Registry of scanners organized by category:
  A. Pattern — VCP, breakout, pullback, squeeze, RS leader
  B. Flow — abnormal volume, options, insider, institutional
  C. Sector — rotation, leader/laggard, crowding, breadth
  D. Risk — earnings, extension, liquidity, spread, macro
  E. Validation — similar outcomes, edge decay, calibration

Decision-intent buckets (Leaders, Pullbacks, Breakouts, Flow, No-Trade) exposed
in Discovery are research/supporting unless Playbook confirms deployability.

Each scanner returns ScannerHit objects that feed into the
ranked opportunity pipeline.
"""

from __future__ import annotations

import logging
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Dict, List, Optional, Tuple, Union

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


class GapScanner(BaseScanner):
    """Detect price gaps from OHLCV data using GapDetector."""
    name = "gap"
    category = ScannerCategory.PATTERN

    def scan(self, signals, regime) -> List[ScannerHit]:
        hits = []
        try:
            from src.engines.gap_detector import GapDetector
        except ImportError:
            return hits
        detector = GapDetector()
        for sig in signals:
            opens = sig.get("opens")
            closes = sig.get("closes")
            if not opens or not closes or len(opens) < 5:
                continue
            highs = sig.get("highs", closes)
            lows = sig.get("lows", closes)
            # Build bar dicts expected by GapDetector.detect(bars)
            bars = [
                {"open": o, "high": h, "low": l, "close": c}
                for o, h, l, c in zip(opens, highs, lows, closes)
            ]
            report = detector.detect(bars, ticker=sig.get("ticker", ""))
            gaps = report.gaps if report else []
            if not gaps:
                continue
            latest = gaps[-1]
            score = {"BREAKAWAY": 8.0, "EXHAUSTION": 3.0, "COMMON": 5.0}.get(
                latest.gap_type, 5.0
            )
            hits.append(
                ScannerHit(
                    scanner_name=self.name,
                    category=self.category,
                    ticker=sig.get("ticker", ""),
                    score=score,
                    headline=f"{latest.gap_type} gap {latest.gap_pct:+.1f}%",
                    detail=f"Bar {latest.bar_index}, filled={latest.filled}",
                    priority=(
                        ScannerPriority.HIGH
                        if latest.gap_type == "BREAKAWAY"
                        else ScannerPriority.NORMAL
                    ),
                    is_warning=latest.gap_type == "EXHAUSTION",
                    metadata={"gap_type": latest.gap_type, "gap_pct": latest.gap_pct},
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
            vol = sig.get("vol_ratio", 1.0)
            rs = sig.get("rs_rank", 50)
            vol_confirms = sig.get("volume_confirms", False)
            if vol >= 2.0 and rs >= 80 and vol_confirms:
                hits.append(
                    ScannerHit(
                        scanner_name=self.name,
                        category=self.category,
                        ticker=sig.get("ticker", ""),
                        score=8.0,
                        headline=(
                            f"High-vol leader: {vol:.1f}x vol, RS {rs}"
                        ),
                        priority=ScannerPriority.HIGH,
                        metadata={
                            "vol_ratio": vol,
                            "rs_rank": rs,
                            "data_source": "heuristic_proxy",
                        },
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


# Categories shown in Discovery hub (excludes decision-intent-only enum values).
_CORE_SCANNER_CATEGORIES: Tuple[ScannerCategory, ...] = (
    ScannerCategory.PATTERN,
    ScannerCategory.FLOW,
    ScannerCategory.SECTOR,
    ScannerCategory.RISK,
    ScannerCategory.VALIDATION,
)

# Decision-intent buckets for Discovery tab (research/supporting — not deploy authority).
DECISION_INTENT_ORDER: Tuple[str, ...] = (
    "LEADERS",
    "PULLBACKS",
    "BREAKOUTS",
    "FLOW",
    "NO_TRADE",
)

DECISION_INTENT_UNDERLYING: Dict[str, Tuple[str, ...]] = {
    "LEADERS": ("SECTOR", "PATTERN"),
    "PULLBACKS": ("PATTERN",),
    "BREAKOUTS": ("PATTERN", "FLOW"),
    "FLOW": ("FLOW",),
    "NO_TRADE": ("RISK", "VALIDATION"),
}

DECISION_INTENT_SCANNERS: Dict[str, Tuple[str, ...]] = {
    "LEADERS": (
        "rs_leader",
        "leader_laggard",
        "sector_rotation",
        "high_volume_leader",
    ),
    "PULLBACKS": ("pullback", "mean_reversion"),
    "BREAKOUTS": ("breakout", "squeeze", "vcp", "gap"),
    "FLOW": (
        "abnormal_volume",
        "volume_surge",
        "quiet_accumulation",
        "high_volume_leader",
    ),
    "NO_TRADE": (
        "earnings_risk",
        "extension_risk",
        "low_liquidity",
        "macro_risk",
        "confidence_conflict",
        "late_stage_theme",
        "edge_decay",
        "breakdown_risk",
    ),
}

INTENT_EMPTY_WHY: Dict[str, str] = {
    "LEADERS": "No RS leaders or sector leadership signals in the scanned universe.",
    "PULLBACKS": "No pullback or mean-reversion setups met score thresholds.",
    "BREAKOUTS": "No breakout, squeeze, VCP, or gap triggers fired.",
    "FLOW": "No unusual volume or flow-style triggers in the scanned universe.",
    "NO_TRADE": "No composite avoid-now risk flags from scanners (see Rejections for pipeline blocks).",
}


class ScannerMatrix:
    """Central registry that runs all scanners."""

    def __init__(self):
        self.scanners: List[BaseScanner] = [
            # Pattern
            VCPScanner(),
            GapScanner(),
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

    @staticmethod
    def fallback_priority_tier(score: float) -> str:
        """Relevance tier when live calibrated scores are unavailable."""
        if score >= 7.5:
            return "High"
        if score >= 6.0:
            return "Medium"
        return "Low"

    @staticmethod
    def enrich_hit_for_ui(
        hit: ScannerHit,
        *,
        score_display_mode: str = "live",
    ) -> Dict[str, Any]:
        """Decision-card fields for Discovery / scanner hub UI."""
        payload = hit.to_dict()
        priority = hit.priority.value if hasattr(hit.priority, "value") else str(hit.priority)
        score = float(hit.score or 0)
        nison_meta: Dict[str, Any] = {}
        if hit.category == ScannerCategory.PATTERN and hit.metadata:
            from src.services.candlestick_context import demote_scanner_hit_metadata

            nison_meta = demote_scanner_hit_metadata(hit.metadata, hit.metadata)
        elif hit.category == ScannerCategory.PATTERN:
            from src.services.candlestick_context import demote_scanner_hit_metadata

            nison_meta = demote_scanner_hit_metadata({"score": score})
        if hit.is_warning:
            next_action = "Review risk — avoid new size until cleared"
        elif score >= 7.5:
            next_action = "Open dossier · compare to best setup"
        elif score >= 6.0:
            next_action = "Add to watch · wait for trigger"
        else:
            next_action = "Monitor only"
        status = (
            "avoid"
            if hit.is_warning
            else "actionable"
            if score >= 7.5
            else "monitor"
        )
        if nison_meta.get("nison_demoted") and status == "actionable":
            status = "monitor"
            next_action = "Verify candlestick context in dossier before acting"
        payload.update(
            {
                "why_surfaced": hit.headline or hit.detail or "Scanner rule matched",
                "signal_source": hit.scanner_name,
                "freshness": hit.timestamp or "live",
                "strength": round(score, 1),
                "risk_note": hit.detail if hit.is_warning else "",
                "next_action": next_action,
                "severity": "WARNING" if hit.is_warning else priority,
                "reason": hit.detail,
                "status": status,
                "urgency": (
                    "HIGH"
                    if hit.is_warning or priority == "URGENT"
                    else "NORMAL"
                ),
                "confidence": round(min(0.95, 0.35 + score * 0.06), 2),
                **nison_meta,
            }
        )
        if score_display_mode == "fallback_rank":
            tier = ScannerMatrix.fallback_priority_tier(score)
            payload["score_display_mode"] = "fallback_rank"
            payload["priority_tier"] = tier
            payload["score_source"] = "brief-fallback"
            payload["score_display"] = tier
            payload["score_display_label"] = f"Fallback rank · {tier.lower()}"
        else:
            payload["score_display_mode"] = "live"
        return payload

    @staticmethod
    def normalize_scanner_bucket(
        hits: List[Dict[str, Any]],
    ) -> Dict[str, Any]:
        """UI-safe bucket: count always matches top_hits length cap."""
        top = hits[:10]
        return {"count": len(hits), "top_hits": top, "display_count": len(top)}

    @staticmethod
    def hits_from_bucket(
        bucket: Union[List[Dict[str, Any]], Dict[str, Any], None],
    ) -> List[Dict[str, Any]]:
        """Extract hit list from raw array or normalized bucket."""
        if bucket is None:
            return []
        if isinstance(bucket, list):
            return bucket
        if isinstance(bucket, dict):
            top = bucket.get("top_hits")
            if isinstance(top, list):
                return top
        return []

    @staticmethod
    def _category_summary_entry(
        hits: List[ScannerHit],
        enrich: Any,
    ) -> Dict[str, Any]:
        enriched = [enrich(h) for h in hits]
        total = len(hits)
        top = sorted(hits, key=lambda x: x.score, reverse=True)[:5]
        top_enriched = [enrich(h) for h in top]
        return {
            "count": total,
            "urgent_count": sum(
                1 for h in hits if h.priority == ScannerPriority.URGENT
            ),
            "warning_count": sum(1 for h in hits if h.is_warning),
            "urgent": sum(
                1 for h in hits if h.priority == ScannerPriority.URGENT
            ),
            "warnings": sum(1 for h in hits if h.is_warning),
            "top_hits": top_enriched,
            "display_count": max(total, len(top_enriched)),
        }

    def get_grouped_by_scanner(
        self,
        signals: List[Dict[str, Any]],
        regime: Dict[str, Any],
        *,
        score_display_mode: str = "live",
    ) -> Dict[str, Dict[str, Dict[str, Any]]]:
        """
        Per-category, per-scanner hit lists for the dashboard.

        Shape: { "FLOW": { "abnormal_volume": { count, top_hits }, ... }, ... }
        """
        raw: Dict[str, Dict[str, List[Dict[str, Any]]]] = {}
        for scanner in self.scanners:
            try:
                hits = scanner.scan(signals, regime)
            except Exception as e:
                logger.warning("Scanner %s error: %s", scanner.name, e)
                continue
            if not hits:
                continue
            cat = scanner.category.value
            if cat not in raw:
                raw[cat] = {}
            key = scanner.name
            bucket = raw[cat].setdefault(key, [])
            for hit in hits:
                bucket.append(
                    self.enrich_hit_for_ui(hit, score_display_mode=score_display_mode)
                )
        grouped: Dict[str, Dict[str, Dict[str, Any]]] = {}
        for cat, scanners in raw.items():
            grouped[cat] = {
                name: self.normalize_scanner_bucket(hits)
                for name, hits in scanners.items()
            }
        return grouped

    def get_summary(
        self,
        signals: List[Dict[str, Any]],
        regime: Dict[str, Any],
        *,
        score_display_mode: str = "live",
    ) -> Dict[str, Any]:
        """Dashboard summary — only core categories; count aligned with hits."""
        all_hits = self.scan_all(signals, regime)
        enrich = lambda h: self.enrich_hit_for_ui(
            h, score_display_mode=score_display_mode
        )
        return {
            cat.value: self._category_summary_entry(
                all_hits.get(cat.value, []),
                enrich,
            )
            for cat in _CORE_SCANNER_CATEGORIES
        }

    @staticmethod
    def build_merged_discovery_rank(
        grouped: Dict[str, Dict[str, Dict[str, Any]]],
        summary: Dict[str, Any],
        regime: Dict[str, Any],
        *,
        universe_size: int = 0,
        score_display_mode: str = "live",
    ) -> Dict[str, Any]:
        """
        Cross-scanner overlap ranking and discovery verdict for Discovery tab.
        """
        regime_label = str(regime.get("label") or regime.get("regime") or "—")
        by_ticker: Dict[str, Dict[str, Any]] = {}
        scanner_totals: Dict[str, int] = {}

        for cat, scanners in grouped.items():
            for scan_name, bucket in scanners.items():
                hits = ScannerMatrix.hits_from_bucket(bucket)
                scanner_totals[scan_name] = (
                    scanner_totals.get(scan_name, 0) + len(hits)
                )
                for h in hits:
                    tk = str(h.get("ticker") or "").upper()
                    if not tk:
                        continue
                    entry = by_ticker.setdefault(
                        tk,
                        {
                            "ticker": tk,
                            "scanners": [],
                            "categories": set(),
                            "scores": [],
                            "is_warning": False,
                            "why": [],
                        },
                    )
                    sn = h.get("signal_source") or h.get("scanner") or scan_name
                    if sn and sn not in entry["scanners"]:
                        entry["scanners"].append(sn)
                    entry["categories"].add(cat)
                    score = float(h.get("strength") or h.get("score") or 0)
                    entry["scores"].append(score)
                    if h.get("is_warning"):
                        entry["is_warning"] = True
                    why = h.get("why_surfaced") or h.get("headline") or ""
                    if why and why not in entry["why"]:
                        entry["why"].append(why)

        merged_top_names: List[Dict[str, Any]] = []
        for tk, entry in by_ticker.items():
            overlap = len(entry["scanners"])
            max_score = max(entry["scores"]) if entry["scores"] else 0.0
            avg_score = (
                sum(entry["scores"]) / len(entry["scores"])
                if entry["scores"]
                else 0.0
            )
            if entry["is_warning"]:
                action = "AVOID"
                urgency = "HIGH"
            elif overlap >= 2 and max_score >= 7.0:
                action = "TRADE"
                urgency = "URGENT" if max_score >= 8.0 else "HIGH"
            elif max_score >= 6.5:
                action = "WATCH"
                urgency = "NORMAL"
            else:
                action = "WATCH"
                urgency = "LOW"
            confidence = min(
                0.95,
                0.35
                + 0.12 * overlap
                + 0.06 * max_score
                - (0.2 if entry["is_warning"] else 0),
            )
            row: Dict[str, Any] = {
                "ticker": tk,
                "overlap": overlap,
                "scanners": list(entry["scanners"]),
                "categories": sorted(entry["categories"]),
                "max_score": round(max_score, 1),
                "avg_score": round(avg_score, 1),
                "action": action,
                "urgency": urgency,
                "confidence": round(confidence, 2),
                "regime_alignment": regime_label,
                "why_flagged": " · ".join(entry["why"][:3]),
                "status": (
                    "confirmed"
                    if overlap >= 2 and not entry["is_warning"]
                    else "speculative"
                    if overlap == 1
                    else "caution"
                ),
            }
            if score_display_mode == "fallback_rank":
                tier = ScannerMatrix.fallback_priority_tier(max_score)
                row["score_display_mode"] = "fallback_rank"
                row["priority_tier"] = tier
                row["score_source"] = "brief-fallback"
                row["score_display"] = tier
                row["score_display_label"] = f"Fallback rank · {tier.lower()}"
            else:
                row["score_display_mode"] = "live"
            merged_top_names.append(row)

        merged_top_names.sort(
            key=lambda x: (x["overlap"], x["max_score"]),
            reverse=True,
        )
        merged_top_names = merged_top_names[:15]

        best_scanner_today: Optional[str] = None
        if scanner_totals:
            best_scanner_today = max(
                scanner_totals.keys(),
                key=lambda k: scanner_totals[k],
            )

        confirmed = [
            m for m in merged_top_names if m["overlap"] >= 2 and m["action"] != "AVOID"
        ]
        speculative = [
            m
            for m in merged_top_names
            if m["overlap"] == 1 and m["action"] in ("TRADE", "WATCH")
        ]
        avoid_now_count = int((summary.get("RISK") or {}).get("count") or 0) + int(
            (summary.get("RISK") or {}).get("warning_count") or 0
        )
        active_cats = sum(
            1
            for cat in _CORE_SCANNER_CATEGORIES
            if int((summary.get(cat.value) or {}).get("count") or 0) > 0
        )
        scanner_overlap = {
            m["ticker"]: m["overlap"] for m in merged_top_names
        }

        discovery_verdict = {
            "best_scanner_today": best_scanner_today,
            "best_scanner_hits": scanner_totals.get(best_scanner_today or "", 0),
            "best_confirmed_name": confirmed[0] if confirmed else None,
            "best_confirmed_label": (
                "Most represented scanner sample"
                if confirmed
                else None
            ),
            "best_speculative_name": speculative[0] if speculative else None,
            "avoid_now_count": avoid_now_count,
            "discovery_breadth": f"{active_cats}/{len(_CORE_SCANNER_CATEGORIES)} categories active",
            "active_categories": active_cats,
            "total_unique_names": len(by_ticker),
            "universe_size": universe_size,
            "regime": regime_label,
        }

        return {
            "merged_top_names": merged_top_names,
            "discovery_verdict": discovery_verdict,
            "scanner_overlap": scanner_overlap,
        }

    def hits_for_decision_intent(
        self,
        intent: str,
        signals: List[Dict[str, Any]],
        regime: Dict[str, Any],
    ) -> List[ScannerHit]:
        """Collect scanner hits for a decision-intent category (LEADERS, etc.)."""
        intent_upper = str(intent or "").upper()
        underlying = DECISION_INTENT_UNDERLYING.get(intent_upper)
        if not underlying:
            return []
        scanner_names = set(DECISION_INTENT_SCANNERS.get(intent_upper, ()))
        hits: List[ScannerHit] = []
        for scanner in self.scanners:
            if scanner.category.value not in underlying:
                continue
            if scanner_names and scanner.name not in scanner_names:
                continue
            try:
                hits.extend(scanner.scan(signals, regime))
            except Exception as e:
                logger.warning("Scanner %s error: %s", scanner.name, e)
        if intent_upper == "NO_TRADE":
            hits = [h for h in hits if h.is_warning]
        return hits

    def build_decision_intent_summary(
        self,
        signals: List[Dict[str, Any]],
        regime: Dict[str, Any],
    ) -> Dict[str, Dict[str, Any]]:
        """
        Per-intent probe status for Discovery hub cards.

        Decision-intent scanners are research/supporting unless Playbook confirms.
        """
        enrich = self.enrich_hit_for_ui
        trend = str(regime.get("trend") or regime.get("label") or "—")
        tradeability = str(
            regime.get("tradeability") or regime.get("regime_tradeability") or ""
        ).upper()
        regime_note = f"{trend}"
        if tradeability:
            regime_note = f"{trend} · board {tradeability}"
        signals_empty = len(signals) == 0
        board_strict = tradeability in ("WAIT", "NO_TRADE")

        out: Dict[str, Dict[str, Any]] = {}
        for intent in DECISION_INTENT_ORDER:
            raw_hits = self.hits_for_decision_intent(intent, signals, regime)
            count = len(raw_hits)
            if signals_empty:
                probe = "warming"
            elif count > 0:
                probe = "active"
            else:
                probe = "idle"
            empty_why = INTENT_EMPTY_WHY.get(intent, "No hits in this intent filter.")
            if board_strict and count == 0:
                empty_why = (
                    f"{empty_why} Page gate is {tradeability} — "
                    "discovery is research-only; confirm in Playbook before sizing."
                )
            elif signals_empty and count == 0:
                empty_why = (
                    f"{empty_why} Scanner universe is warming "
                    "(no upstream signals yet)."
                )
            top = sorted(raw_hits, key=lambda x: x.score, reverse=True)[:5]
            out[intent] = {
                "intent": intent,
                "count": count,
                "probe_status": probe,
                "regime_note": regime_note,
                "empty_why": empty_why,
                "top_hits": [enrich(h) for h in top],
            }
        return out
