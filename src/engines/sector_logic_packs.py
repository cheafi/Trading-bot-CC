"""
CC — Sector Logic Packs
========================
Sector-specific interpretation rules. Same pattern (breakout, VCP,
pullback) gets different treatment depending on sector bucket.

Each pack defines:
  - what to emphasize
  - what to warn about
  - how to adjust scores
  - sector-specific invalidation conditions
"""

from __future__ import annotations

import logging
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Any, Dict, List

from src.engines.sector_classifier import (
    LeaderStatus,
    SectorBucket,
    SectorContext,
    SectorStage,
)

logger = logging.getLogger(__name__)


@dataclass
class SectorAdjustment:
    """Score adjustments + warnings from sector logic."""

    score_modifier: float = 0.0
    confidence_modifier: float = 0.0
    warnings: List[str] = field(default_factory=list)
    emphasis: List[str] = field(default_factory=list)
    alert_tone: str = "neutral"  # bullish / cautious / warning
    discord_channel: str = "#opportunities"

    def to_dict(self) -> Dict[str, Any]:
        return {
            "score_modifier": round(self.score_modifier, 2),
            "confidence_modifier": round(self.confidence_modifier, 2),
            "warnings": self.warnings,
            "emphasis": self.emphasis,
            "alert_tone": self.alert_tone,
            "discord_channel": self.discord_channel,
        }


class SectorLogicPack(ABC):
    """Base class for sector-specific logic."""

    @abstractmethod
    def adjust(
        self,
        signal: Dict[str, Any],
        sector: SectorContext,
        regime: Dict[str, Any],
    ) -> SectorAdjustment: ...

    @abstractmethod
    def get_key_metrics(self) -> List[str]:
        """Which metrics matter most for this sector."""
        ...


class HighGrowthPack(SectorLogicPack):
    """Tech / AI / Semis / SaaS — growth-driven names."""

    def adjust(self, signal, sector, regime) -> SectorAdjustment:
        adj = SectorAdjustment()
        adj.discord_channel = "#growth-ai"
        rsi = signal.get("rsi", 50)
        vol_ratio = signal.get("vol_ratio", 1.0)

        # Emphasis
        adj.emphasis = [
            "growth_acceleration",
            "innovation_cycle",
            "theme_narrative",
            "RS_vs_QQQ_SOXX",
        ]

        # Sector in acceleration → boost
        if sector.sector_stage == SectorStage.ACCELERATION:
            adj.score_modifier += 0.5
            adj.confidence_modifier += 0.05

        # Leader bonus
        if sector.leader_status == LeaderStatus.LEADER:
            adj.score_modifier += 0.5
            adj.alert_tone = "bullish"

        # Crowding / overheated warnings
        if sector.crowding_risk > 0.6:
            adj.score_modifier -= 1.0
            adj.confidence_modifier -= 0.08
            adj.warnings.append("Elevated crowding risk in growth sector")

        if rsi > 75 and vol_ratio > 2.5:
            adj.warnings.append("Climax volume + overbought — late chase risk")
            adj.alert_tone = "warning"
            adj.score_modifier -= 1.5

        # Laggard after leaders exhausted
        if (
            sector.leader_status == LeaderStatus.LAGGARD
            and sector.sector_stage == SectorStage.CLIMAX
        ):
            msg = "Laggard moving after" " leaders peak — high risk"
            adj.warnings.append(msg)
            adj.score_modifier -= 2.0
            adj.confidence_modifier -= 0.15
            adj.alert_tone = "warning"

        # Valuation detached (proxy: extended from MA)
        dist_ma = signal.get("distance_from_50ma_pct", 0)
        if dist_ma > 20:
            adj.warnings.append("Extended >20% above 50MA — pullback risk")

        return adj

    def get_key_metrics(self) -> List[str]:
        return [
            "RS vs QQQ/SOXX",
            "theme_heat",
            "crowding_risk",
            "growth_acceleration",
            "earnings_catalyst",
            "valuation_vs_growth",
        ]


class CyclicalPack(SectorLogicPack):
    """Energy / Metals / Mining / Commodities / Industrials."""

    def adjust(self, signal, sector, regime) -> SectorAdjustment:
        adj = SectorAdjustment()
        adj.discord_channel = "#cyclical-macro"

        adj.emphasis = [
            "commodity_price_trend",
            "macro_cycle",
            "inflation_rates_USD",
            "supply_demand",
            "geopolitical_risk",
            "EMA21_EMA50",
        ]

        # Macro support
        macro_trend = regime.get("macro_trend", "neutral")
        if macro_trend in ("inflationary", "commodity_bull"):
            adj.score_modifier += 0.5

        # Futures confirmation
        futures_aligned = signal.get("futures_aligned", None)
        if futures_aligned is False:
            adj.warnings.append("Commodity equity vs futures" " divergence — caution")
            adj.score_modifier -= 1.5
            adj.confidence_modifier -= 0.1
            adj.alert_tone = "cautious"

        # ATR / stop width
        atr_pct = signal.get("atr_pct", 2.0)
        if atr_pct > 4.0:
            adj.warnings.append(f"Wide ATR ({atr_pct:.1f}%) — large stop")

        # Weekend geopolitical risk
        day_of_week = signal.get("day_of_week", 2)
        if day_of_week >= 4:  # Thursday/Friday
            adj.warnings.append("Weekend geopolitical risk for commodities")

        # Key support/resistance emphasis
        adj.emphasis.append("key_support_resistance_levels")
        adj.emphasis.append("repeated_test_count")

        return adj

    def get_key_metrics(self) -> List[str]:
        return [
            "commodity_futures_trend",
            "USD_DXY",
            "inflation_expectations",
            "EMA21_EMA50",
            "ATR_stop_width",
            "macro_calendar",
        ]


class DefensivePack(SectorLogicPack):
    """Utilities / Healthcare / Staples / REITs / Dividend."""

    def adjust(self, signal, sector, regime) -> SectorAdjustment:
        adj = SectorAdjustment()
        adj.discord_channel = "#defensive-rotation"

        adj.emphasis = [
            "defensive_rotation_signal",
            "VIX_level",
            "RS_vs_SPY",
            "yield_beta_hedge",
            "balance_sheet_quality",
        ]

        # VIX spike = defensive rotation opportunity
        vix = regime.get("vix", 18)
        if vix > 25:
            adj.score_modifier += 0.5
            adj.emphasis.append("VIX elevated — defensive rotation")

        # Yield trap warning
        div_yield = signal.get("dividend_yield", 0)
        payout_ratio = signal.get("payout_ratio", 0)
        debt_equity = signal.get("debt_equity", 0)
        if div_yield > 5.0 and (payout_ratio > 90 or debt_equity > 2.0):
            adj.warnings.append(
                "Potential yield trap — high yield but weak balance sheet"
            )
            adj.score_modifier -= 1.5
            adj.confidence_modifier -= 0.1
            adj.alert_tone = "warning"

        # Overbought defensive
        rsi = signal.get("rsi", 50)
        if rsi > 72 and sector.relative_strength > 0.3:
            adj.warnings.append("Defensive overbought after rotation")

        # Bond yield sensitivity
        rate_sensitive = signal.get("rate_sensitive", False)
        if rate_sensitive:
            adj.emphasis.append("bond_yield_sensitivity")

        return adj

    def get_key_metrics(self) -> List[str]:
        return [
            "VIX",
            "RS_vs_SPY",
            "drawdown_resistance",
            "dividend_yield",
            "debt_payout_FCF",
            "bond_yield_direction",
        ]


class ThemeHypePack(SectorLogicPack):
    """Meme / SPAC / Concept / Narrative — speculation driven."""

    def adjust(self, signal, sector, regime) -> SectorAdjustment:
        adj = SectorAdjustment()
        adj.discord_channel = "#theme-speculation"

        adj.emphasis = [
            "sentiment_phase",
            "speculative_flow",
            "social_heat",
            "leader_stock_effect",
        ]

        # Phase-specific logic
        stage = sector.sector_stage

        if stage == SectorStage.LAUNCH:
            adj.alert_tone = "bullish"
            adj.emphasis.append("early entry — leader identification")

        elif stage == SectorStage.ACCELERATION:
            adj.alert_tone = "bullish"
            adj.score_modifier += 0.5
            if sector.leader_status == LeaderStatus.LEADER:
                adj.emphasis.append("theme leader — momentum play")

        elif stage == SectorStage.CLIMAX:
            adj.alert_tone = "cautious"
            adj.score_modifier -= 1.0
            adj.confidence_modifier -= 0.1
            adj.warnings.append("Theme at climax — distribution may begin")
            adj.warnings.append("Volume climax — news may be fully priced")

            if sector.leader_status == LeaderStatus.LAGGARD:
                adj.score_modifier -= 2.0
                adj.warnings.append("Laggard at theme climax" " — highest risk tier")

        elif stage == SectorStage.DISTRIBUTION:
            adj.alert_tone = "warning"
            adj.score_modifier -= 3.0
            adj.confidence_modifier -= 0.2
            adj.warnings.append("Theme in distribution — avoid new entries")

        # Social heat
        social_heat = signal.get("social_heat", 0)
        if social_heat > 80:
            adj.warnings.append("Social heat extreme" " — sentiment exhaustion risk")

        return adj

    def get_key_metrics(self) -> List[str]:
        return [
            "theme_phase",
            "leader_vs_laggard",
            "social_heat",
            "volume_climax",
            "news_catalyst_freshness",
        ]


# ── Registry ─────────────────────────────────────────────────────────


_PACKS: Dict[SectorBucket, SectorLogicPack] = {
    SectorBucket.HIGH_GROWTH: HighGrowthPack(),
    SectorBucket.CYCLICAL: CyclicalPack(),
    SectorBucket.DEFENSIVE: DefensivePack(),
    SectorBucket.THEME_HYPE: ThemeHypePack(),
}


def get_sector_adjustment(
    signal: Dict[str, Any],
    sector: SectorContext,
    regime: Dict[str, Any],
) -> SectorAdjustment:
    """Get sector-specific adjustment for a signal."""
    pack = _PACKS.get(sector.sector_bucket)
    if pack is None:
        return SectorAdjustment()
    return pack.adjust(signal, sector, regime)


def get_sector_key_metrics(bucket: SectorBucket) -> List[str]:
    """Get key metrics for a sector bucket."""
    pack = _PACKS.get(bucket)
    return pack.get_key_metrics() if pack else []
