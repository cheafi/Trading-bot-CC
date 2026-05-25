from __future__ import annotations

import logging
from collections import Counter
from datetime import datetime, timezone
from typing import Any, Dict, Iterable, List, Optional

from src.services.options_flow_provider import (
    OptionsFlowEvent,
    OptionsFlowProvider,
    OptionsRadarSnapshot,
)

logger = logging.getLogger(__name__)


class OptionsFlowRadar:
    """Score and rank unusual options activity as evidence, not decisions."""

    MEGA_CAPS = {
        "AAPL",
        "MSFT",
        "NVDA",
        "AMZN",
        "META",
        "GOOGL",
        "GOOG",
        "TSLA",
        "AVGO",
        "BRK.B",
        "JPM",
        "LLY",
        "V",
        "MA",
        "UNH",
        "XOM",
        "COST",
        "WMT",
        "NFLX",
    }
    MAX_SPREAD_PCT = 8.0
    ABSURD_SPREAD_PCT = 20.0
    MIN_PREMIUM = 25_000
    MIN_SIZE = 25
    MIN_UNDERLYING_DOLLAR_VOLUME = 5_000_000
    STALE_SECONDS = 900

    def __init__(self, provider: Optional[OptionsFlowProvider] = None):
        self.provider = provider

    async def scan(
        self,
        universe: Optional[List[str]] = None,
        *,
        limit: int = 50,
        min_grade: str = "C",
    ) -> OptionsRadarSnapshot:
        if self.provider is None:
            return self._empty_snapshot("unavailable", "none", "provider unavailable")

        status = await self.provider.health()
        raw_events = await self.provider.fetch_recent_events(
            universe, limit=max(limit * 10, 100)
        )
        scored = [self.score_event(event) for event in raw_events]
        filtered = [event for event in scored if self.is_candidate(event)]
        filtered.sort(key=lambda event: event.radar_score, reverse=True)
        candidates = self._apply_grade_filter(filtered, min_grade)[:limit]
        source = status.provider
        snapshot_status = (
            "live"
            if status.mode == "realtime"
            else "snapshot" if status.mode == "mock" else "stale"
        )
        return OptionsRadarSnapshot(
            timestamp=datetime.now(timezone.utc).isoformat(),
            status=snapshot_status,
            source=source,
            universe_size=len(universe or []),
            candidates=[event.to_dict() for event in candidates],
            summary=self._summary(scored, candidates),
            trust=status.to_dict(),
        )

    def score_event(self, event: OptionsFlowEvent) -> OptionsFlowEvent:
        magnitude = self._flow_magnitude(event)
        novelty = self._flow_novelty(event)
        tradeability = self._tradeability(event)
        context = self._context_quality(event)
        noise_penalty = self._noise_penalty(event)
        less_followed_bonus = self._less_followed_bonus(event)
        mega_cap_penalty = (
            8.0 if event.underlying in self.MEGA_CAPS and novelty < 55 else 0.0
        )

        event.anomaly_score = self._clamp(
            (magnitude * 0.45) + (novelty * 0.55) - noise_penalty
        )
        event.tradeability_score = tradeability
        event.opportunity_relevance_score = self._clamp(
            context + less_followed_bonus - mega_cap_penalty
        )
        event.radar_score = self._clamp(
            event.anomaly_score * 0.45
            + event.tradeability_score * 0.25
            + event.opportunity_relevance_score * 0.30
        )
        event.quality_grade = self._grade(event)
        event.action_label = self._action_label(event)
        event.explanation = self._explanation(event)
        return event

    def is_candidate(self, event: OptionsFlowEvent) -> bool:
        if event.trust.stale or event.trust.delay_seconds > self.STALE_SECONDS:
            return False
        if event.size < self.MIN_SIZE or event.premium < self.MIN_PREMIUM:
            return False
        if event.spread_pct > self.ABSURD_SPREAD_PCT:
            return False
        if (
            event.underlying_dollar_volume is not None
            and event.underlying_dollar_volume < self.MIN_UNDERLYING_DOLLAR_VOLUME
        ):
            return False
        if event.mid > 0 and event.price < 0.05 and event.dte <= 7:
            return False
        return event.radar_score >= 35

    def _flow_magnitude(self, event: OptionsFlowEvent) -> float:
        premium_score = self._tier(
            event.premium,
            [(1_000_000, 100), (500_000, 85), (100_000, 65), (50_000, 45)],
        )
        size_score = self._tier(
            event.size, [(5_000, 100), (2_000, 80), (500, 60), (100, 35)]
        )
        repeat_score = min(100.0, event.repeated_directional_prints * 14.0)
        flag_score = (
            100.0
            if event.sweep_flag and event.block_flag
            else 80.0 if event.sweep_flag or event.block_flag else 0.0
        )
        return self._clamp(
            premium_score * 0.45
            + size_score * 0.25
            + repeat_score * 0.20
            + flag_score * 0.10
        )

    def _flow_novelty(self, event: OptionsFlowEvent) -> float:
        vol_oi = self._tier(
            event.volume_oi_ratio, [(3.0, 100), (2.0, 85), (1.0, 65), (0.5, 35)]
        )
        vol_avg = self._tier(
            event.volume_vs_avg_ratio, [(5.0, 100), (3.0, 85), (2.0, 65), (1.5, 45)]
        )
        iv_jump = self._tier(
            abs(event.iv_change or 0.0),
            [(0.25, 100), (0.15, 80), (0.08, 55), (0.03, 25)],
        )
        dte_conc = self._tier(
            max(0, 30 - event.dte), [(28, 100), (23, 80), (14, 55), (1, 25)]
        )
        return self._clamp(
            vol_oi * 0.30 + vol_avg * 0.35 + iv_jump * 0.20 + dte_conc * 0.15
        )

    def _tradeability(self, event: OptionsFlowEvent) -> float:
        spread = 100.0 - min(100.0, max(0.0, event.spread_pct) * 12.0)
        oi = self._tier(
            event.open_interest, [(5000, 100), (1000, 80), (250, 55), (50, 25)]
        )
        underlying_liquidity = self._tier(
            event.underlying_dollar_volume or 0,
            [(500_000_000, 100), (100_000_000, 80), (25_000_000, 60), (5_000_000, 35)],
        )
        return self._clamp(spread * 0.45 + oi * 0.25 + underlying_liquidity * 0.30)

    def _context_quality(self, event: OptionsFlowEvent) -> float:
        regime = self._clamp(event.regime_alignment * 100)
        rs = self._clamp(event.relative_strength * 100)
        not_fully_moved = 100.0 - min(100.0, abs(event.stock_move_pct) * 12.0)
        directional_alignment = 65.0
        if event.call_put == "C" and event.stock_move_pct >= 0:
            directional_alignment = 80.0
        elif event.call_put == "P" and event.stock_move_pct <= 0:
            directional_alignment = 80.0
        return self._clamp(
            regime * 0.30
            + rs * 0.25
            + not_fully_moved * 0.25
            + directional_alignment * 0.20
        )

    def _noise_penalty(self, event: OptionsFlowEvent) -> float:
        penalty = 0.0
        if event.spread_pct > self.MAX_SPREAD_PCT:
            penalty += 18.0
        if event.open_interest < 25:
            penalty += 12.0
        if event.price < 0.10 and event.dte <= 7:
            penalty += 15.0
        if abs(event.stock_move_pct) > 8.0:
            penalty += 10.0
        if event.volume > 0 and event.open_interest == 0:
            penalty += 5.0
        return penalty

    def _less_followed_bonus(self, event: OptionsFlowEvent) -> float:
        if event.underlying in self.MEGA_CAPS:
            return 0.0
        market_cap = event.market_cap or 0.0
        dollar_volume = event.underlying_dollar_volume or 0.0
        if (
            500_000_000 <= market_cap <= 15_000_000_000
            and dollar_volume >= self.MIN_UNDERLYING_DOLLAR_VOLUME
        ):
            return 12.0
        return 7.0 if market_cap == 0 and dollar_volume >= 25_000_000 else 0.0

    def _grade(self, event: OptionsFlowEvent) -> str:
        if event.radar_score >= 75 and event.tradeability_score >= 45:
            return "A"
        if event.radar_score >= 55 and event.tradeability_score >= 30:
            return "B"
        return "C"

    def _action_label(self, event: OptionsFlowEvent) -> str:
        if event.tradeability_score < 30 or event.spread_pct > self.MAX_SPREAD_PCT:
            return "AVOID_NOW"
        if event.quality_grade == "A" and event.opportunity_relevance_score >= 60:
            return "IDEA"
        if event.quality_grade == "A":
            return "SUPPORTING_EVIDENCE"
        return "WATCH" if event.quality_grade == "B" else "AVOID_NOW"

    def _explanation(self, event: OptionsFlowEvent) -> str:
        reasons = []
        if event.premium >= 100_000:
            reasons.append(f"${event.premium/1000:.0f}k premium")
        if event.volume_vs_avg_ratio >= 2:
            reasons.append(f"volume {event.volume_vs_avg_ratio:.1f}x avg")
        if event.volume_oi_ratio >= 1:
            reasons.append(f"vol/OI {event.volume_oi_ratio:.1f}")
        if event.sweep_flag:
            reasons.append("sweep behavior")
        if event.block_flag:
            reasons.append("block print")
        if event.dte <= 7:
            reasons.append(f"{event.dte} DTE")
        if event.iv_change and abs(event.iv_change) >= 0.08:
            reasons.append(f"IV jump {event.iv_change:+.0%}")
        if abs(event.stock_move_pct) < 2:
            reasons.append("stock not fully confirmed yet")
        return " | ".join(reasons) or "elevated options activity"

    def _summary(
        self, scored: Iterable[OptionsFlowEvent], candidates: Iterable[OptionsFlowEvent]
    ) -> Dict[str, Any]:
        scored_list = list(scored)
        candidate_list = list(candidates)
        grade_counts = Counter(event.quality_grade for event in candidate_list)
        return {
            "events_scored": len(scored_list),
            "candidates": len(candidate_list),
            "grade_a": grade_counts["A"],
            "grade_b": grade_counts["B"],
            "grade_c": grade_counts["C"],
            "small_less_followed": len(
                [
                    event
                    for event in candidate_list
                    if event.underlying not in self.MEGA_CAPS
                ]
            ),
        }

    def _apply_grade_filter(
        self, events: List[OptionsFlowEvent], min_grade: str
    ) -> List[OptionsFlowEvent]:
        rank = {"A": 3, "B": 2, "C": 1}
        threshold = rank.get(min_grade.upper(), 1)
        return [
            event for event in events if rank.get(event.quality_grade, 0) >= threshold
        ]

    def _empty_snapshot(
        self, status: str, source: str, message: str
    ) -> OptionsRadarSnapshot:
        return OptionsRadarSnapshot(
            timestamp=datetime.now(timezone.utc).isoformat(),
            status=status,
            source=source,
            universe_size=0,
            candidates=[],
            summary={"events_scored": 0, "candidates": 0, "message": message},
            trust={
                "provider": source,
                "enabled": False,
                "status": status,
                "message": message,
            },
        )

    @staticmethod
    def _tier(value: float, thresholds: List[tuple[float, float]]) -> float:
        return next((score for floor, score in thresholds if value >= floor), 0.0)

    @staticmethod
    def _clamp(value: float, lo: float = 0.0, hi: float = 100.0) -> float:
        return max(lo, min(hi, value))
