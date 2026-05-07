"""
TradingAI Bot — Delta Tracker + Regime Scoreboard (v6)

Two critical missing layers that turn "market summary" into "market intelligence":

1. DeltaTracker  — computes what changed (in code, not GPT) then feeds to GPT for attribution
2. ScoreboardBuilder — builds the regime scoreboard + risk budget + strategy playbook

Both are data-derived, deterministic, and auditable.
"""
import logging
from datetime import date, datetime, timezone, timedelta
from typing import Dict, Any, List, Optional, Tuple

from src.core.models import (
    DeltaSnapshot, RegimeScoreboard, ScenarioPlan,
    MarketRegime, VolatilityRegime, TrendRegime, RiskRegime,
    ChangeItem,
)

logger = logging.getLogger(__name__)


# ═══════════════════════════════════════════════════════════════════════
# DELTA TRACKER  — "What changed since last report"
# ═══════════════════════════════════════════════════════════════════════

class DeltaTracker:
    """
    Computes deltas between today's market data and yesterday's snapshot.
    All math happens here in deterministic code — GPT only interprets the deltas.

    This is the FASTEST way to stop sounding generic:
    "VIX is 16.4" → "VIX fell 2.3 pts (from 18.7) as mega-cap earnings beat — noise, not regime shift"
    """

    def compute(
        self,
        today: Dict[str, Any],
        yesterday: Optional[Dict[str, Any]] = None,
        week_ago: Optional[Dict[str, Any]] = None,
    ) -> DeltaSnapshot:
        """
        Compute all deltas from raw market data dicts.

        Expected keys in market data:
            spx_close, spx_change_pct, ndx_close, ndx_change_pct,
            iwm_close, iwm_change_pct, vix, vix_change,
            yield_10y, pct_above_sma50, new_52w_highs, new_52w_lows,
            sector_performance, news_sentiment_1d, social_sentiment_1d,
            put_call_ratio
        """
        yesterday = yesterday or {}
        week_ago = week_ago or {}

        # Index deltas
        spx_1d = today.get("spx_change_pct", 0)
        ndx_1d = today.get("ndx_change_pct", 0)
        iwm_1d = today.get("iwm_change_pct", 0)

        spx_5d = self._pct_change(today.get("spx_close", 0), week_ago.get("spx_close", 0))
        ndx_5d = self._pct_change(today.get("ndx_close", 0), week_ago.get("ndx_close", 0))
        iwm_5d = self._pct_change(today.get("iwm_close", 0), week_ago.get("iwm_close", 0))

        # VIX deltas
        vix = today.get("vix", 0)
        vix_1d = today.get("vix_change", 0) or (vix - yesterday.get("vix", vix))
        vix_5d = vix - week_ago.get("vix", vix)

        # Rates
        y10 = today.get("yield_10y", 0)
        y10_1d_bp = (y10 - yesterday.get("yield_10y", y10)) * 100
        y10_5d_bp = (y10 - week_ago.get("yield_10y", y10)) * 100

        # Breadth
        pct50 = today.get("pct_above_sma50", 50)
        pct50_1d = pct50 - yesterday.get("pct_above_sma50", pct50)

        # Sector leadership
        sectors = today.get("sector_performance", {})
        sorted_sectors = sorted(sectors.items(), key=lambda x: x[1], reverse=True)
        top_3 = [{"name": s[0], "pct": round(s[1], 2)} for s in sorted_sectors[:3]]
        bottom_3 = [{"name": s[0], "pct": round(s[1], 2)} for s in sorted_sectors[-3:]]

        # Sentiment delta
        news_delta = (
            today.get("news_sentiment_1d", 50) - yesterday.get("news_sentiment_1d", 50)
        )
        social_delta = (
            today.get("social_sentiment_1d", 50) - yesterday.get("social_sentiment_1d", 50)
        )

        return DeltaSnapshot(
            snapshot_date=date.today(),
            spx_1d_pct=round(spx_1d, 2),
            spx_5d_pct=round(spx_5d, 2),
            ndx_1d_pct=round(ndx_1d, 2),
            ndx_5d_pct=round(ndx_5d, 2),
            iwm_1d_pct=round(iwm_1d, 2),
            iwm_5d_pct=round(iwm_5d, 2),
            vix_close=round(vix, 1),
            vix_1d_change=round(vix_1d, 1),
            vix_5d_change=round(vix_5d, 1),
            yield_10y=round(y10, 3),
            yield_10y_1d_bp=round(y10_1d_bp, 1),
            yield_10y_5d_bp=round(y10_5d_bp, 1),
            pct_above_50dma=round(pct50, 1),
            pct_above_50dma_1d_change=round(pct50_1d, 1),
            new_highs=today.get("new_52w_highs", 0),
            new_lows=today.get("new_52w_lows", 0),
            top_3_sectors=top_3,
            bottom_3_sectors=bottom_3,
            news_sentiment_change=round(news_delta, 1),
            social_sentiment_change=round(social_delta, 1),
            put_call_ratio=today.get("put_call_ratio"),
            iv_rank_spy=today.get("iv_rank_spy"),
        )

    def classify_changes(self, delta: DeltaSnapshot) -> Tuple[List[ChangeItem], List[ChangeItem]]:
        """
        Classify deltas into bullish and bearish change items.
        Returns: (bullish_changes, bearish_changes)
        """
        bullish: List[ChangeItem] = []
        bearish: List[ChangeItem] = []

        # Index moves
        if delta.spx_1d_pct > 0.5:
            bullish.append(ChangeItem(category="macro", description=f"SPX +{delta.spx_1d_pct:.1f}% — broad rally", severity="info"))
        elif delta.spx_1d_pct < -0.5:
            bearish.append(ChangeItem(category="macro", description=f"SPX {delta.spx_1d_pct:.1f}% — selling pressure", severity="warning" if delta.spx_1d_pct < -1.5 else "info"))

        if delta.ndx_1d_pct > 0.5:
            bullish.append(ChangeItem(category="leadership", description=f"Nasdaq outperforming +{delta.ndx_1d_pct:.1f}%", severity="info"))
        elif delta.ndx_1d_pct < -0.5:
            bearish.append(ChangeItem(category="leadership", description=f"Nasdaq weak {delta.ndx_1d_pct:.1f}%", severity="info"))

        # Small caps (breadth signal)
        if delta.iwm_1d_pct > 0.8:
            bullish.append(ChangeItem(category="breadth", description=f"Small caps rallying +{delta.iwm_1d_pct:.1f}% — risk appetite healthy", severity="info"))
        elif delta.iwm_1d_pct < -0.8:
            bearish.append(ChangeItem(category="breadth", description=f"Small caps weak {delta.iwm_1d_pct:.1f}% — narrow leadership", severity="warning"))

        # VIX
        if delta.vix_1d_change < -2:
            bullish.append(ChangeItem(category="volatility", description=f"VIX fell {delta.vix_1d_change:.1f} to {delta.vix_close:.1f} — fear receding", severity="info"))
        elif delta.vix_1d_change > 2:
            bearish.append(ChangeItem(category="volatility", description=f"VIX jumped +{delta.vix_1d_change:.1f} to {delta.vix_close:.1f} — hedging activity", severity="warning" if delta.vix_close > 22 else "info"))

        # Rates
        if delta.yield_10y_1d_bp < -5:
            bullish.append(ChangeItem(category="macro", description=f"10Y yield fell {delta.yield_10y_1d_bp:.0f}bp to {delta.yield_10y:.2f}% — growth-friendly", severity="info"))
        elif delta.yield_10y_1d_bp > 5:
            bearish.append(ChangeItem(category="macro", description=f"10Y yield rose +{delta.yield_10y_1d_bp:.0f}bp to {delta.yield_10y:.2f}% — valuation pressure", severity="warning" if delta.yield_10y > 4.5 else "info"))

        # Breadth
        if delta.pct_above_50dma_1d_change > 3:
            bullish.append(ChangeItem(category="breadth", description=f"Breadth expanding: +{delta.pct_above_50dma_1d_change:.0f}% stocks above 50DMA → {delta.pct_above_50dma:.0f}%", severity="info"))
        elif delta.pct_above_50dma_1d_change < -3:
            bearish.append(ChangeItem(category="breadth", description=f"Breadth narrowing: {delta.pct_above_50dma_1d_change:.0f}% stocks lost 50DMA → {delta.pct_above_50dma:.0f}%", severity="warning"))

        # Sector leadership
        if delta.top_3_sectors:
            top_names = ", ".join(s["name"] for s in delta.top_3_sectors)
            bullish.append(ChangeItem(category="leadership", description=f"Leading: {top_names}", severity="info"))
        if delta.bottom_3_sectors:
            bot_names = ", ".join(s["name"] for s in delta.bottom_3_sectors)
            bearish.append(ChangeItem(category="leadership", description=f"Lagging: {bot_names}", severity="info"))

        # Sentiment
        if delta.news_sentiment_change > 10:
            bullish.append(ChangeItem(category="sentiment", description=f"News sentiment improving (+{delta.news_sentiment_change:.0f})", severity="info"))
        elif delta.news_sentiment_change < -10:
            bearish.append(ChangeItem(category="sentiment", description=f"News sentiment deteriorating ({delta.news_sentiment_change:.0f})", severity="info"))

        return bullish, bearish

    @staticmethod
    def _pct_change(current: float, previous: float) -> float:
        if previous == 0:
            return 0.0
        return ((current - previous) / previous) * 100


# ═══════════════════════════════════════════════════════════════════════
# REGIME SCOREBOARD BUILDER  — the decision layer
# ═══════════════════════════════════════════════════════════════════════

class ScoreboardBuilder:
    """
    Builds the daily Regime Scoreboard from market regime + market data.
    Auto-derives risk budget, strategy playbook, scenarios, and no-trade triggers.

    This goes at the TOP of every report — it's what makes the system "pro".
    """

    # Regime → risk budget mapping
    RISK_BUDGETS = {
        "RISK_ON": {
            "max_gross_pct": 100.0,
            "net_long_low": 55.0,
            "net_long_high": 80.0,
            "max_single_name": 5.0,
            "max_sector": 25.0,
        },
        "NEUTRAL": {
            "max_gross_pct": 70.0,
            "net_long_low": 25.0,
            "net_long_high": 50.0,
            "max_single_name": 3.5,
            "max_sector": 20.0,
        },
        "RISK_OFF": {
            "max_gross_pct": 40.0,
            "net_long_low": 0.0,
            "net_long_high": 25.0,
            "max_single_name": 2.0,
            "max_sector": 15.0,
        },
    }

    # Standard no-trade triggers
    NO_TRADE_TRIGGERS = [
        "VIX > 40",
        "SPX intraday -3% or worse",
        "FOMC decision day (wait until 2:30 ET)",
        "Data feeds stale > 15 min",
        "Multiple critical data quality gates failing",
    ]

    def build(
        self,
        regime: MarketRegime,
        market_data: Dict[str, Any],
        delta: Optional[DeltaSnapshot] = None,
        calendar_events: Optional[List[Dict]] = None,
    ) -> RegimeScoreboard:
        """Build the complete regime scoreboard."""

        risk_label = regime.risk.value  # RISK_ON / NEUTRAL / RISK_OFF
        budget = self.RISK_BUDGETS.get(risk_label, self.RISK_BUDGETS["NEUTRAL"])

        # Adjust for vol regime
        if regime.volatility == VolatilityRegime.HIGH_VOL:
            budget = {k: v * 0.7 for k, v in budget.items()}
        elif regime.volatility == VolatilityRegime.CRISIS:
            budget = {k: v * 0.3 for k, v in budget.items()}

        # Strategy playbook
        strats_on, strats_cond, strats_off = self._strategy_playbook(regime)

        # Top drivers
        drivers = self._derive_drivers(market_data, delta, calendar_events)

        # Scenarios
        scenarios = self._build_scenarios(regime, market_data, delta)

        # Map trend to simpler label
        trend_map = {
            TrendRegime.STRONG_UPTREND: "UPTREND",
            TrendRegime.UPTREND: "UPTREND",
            TrendRegime.NEUTRAL: "RANGE",
            TrendRegime.DOWNTREND: "DOWNTREND",
            TrendRegime.STRONG_DOWNTREND: "DOWNTREND",
        }

        return RegimeScoreboard(
            regime_label=risk_label.replace("_", "-"),
            risk_on_score=round(market_data.get("risk_on_score", 50), 0),
            trend_state=trend_map.get(regime.trend, "RANGE"),
            vol_state=regime.volatility.value.replace("_", " "),

            max_gross_pct=round(budget["max_gross_pct"], 0),
            net_long_target_low=round(budget["net_long_low"], 0),
            net_long_target_high=round(budget["net_long_high"], 0),
            max_single_name_pct=round(budget["max_single_name"], 1),
            max_sector_pct=round(budget["max_sector"], 0),

            strategies_on=strats_on,
            strategies_conditional=strats_cond,
            strategies_off=strats_off,
            no_trade_triggers=self.NO_TRADE_TRIGGERS,

            top_drivers=drivers,
            scenarios=scenarios,
        )

    def _strategy_playbook(self, regime: MarketRegime) -> Tuple[List[str], List[Dict[str, str]], List[str]]:
        """Auto-derive which strategies are ON, CONDITIONAL, or OFF."""
        on: List[str] = []
        conditional: List[Dict[str, str]] = []
        off: List[str] = []

        all_strategies = [
            "momentum_breakout", "trend_following", "vcp", "classic_swing",
            "mean_reversion", "short_term_mean_reversion",
            "momentum_rotation", "event_driven",
        ]

        active = set(regime.active_strategies)

        for strat in all_strategies:
            if strat in active:
                on.append(strat)
            else:
                # Determine if conditional or fully off
                if regime.risk == RiskRegime.RISK_OFF:
                    if strat == "mean_reversion":
                        conditional.append({
                            "strategy": strat,
                            "condition": "Only at strong support + positive tape confirmation",
                        })
                    else:
                        off.append(strat)
                elif regime.volatility == VolatilityRegime.HIGH_VOL:
                    if strat in ("momentum_breakout", "vcp"):
                        conditional.append({
                            "strategy": strat,
                            "condition": "Only A+ setups with 2x normal stop width",
                        })
                    else:
                        off.append(strat)
                elif strat == "event_driven":
                    conditional.append({
                        "strategy": strat,
                        "condition": "Defined-risk only (spreads) into binary events",
                    })
                else:
                    off.append(strat)

        return on, conditional, off

    def _derive_drivers(
        self,
        market_data: Dict[str, Any],
        delta: Optional[DeltaSnapshot],
        calendar_events: Optional[List[Dict]],
    ) -> List[str]:
        """Derive top 3 market drivers from data."""
        drivers: List[str] = []

        # Rates driver
        y10 = market_data.get("yield_10y", 0)
        if y10 > 4.3:
            drivers.append(f"Rates: 10Y at {y10:.2f}% — growth vs value rotation risk")
        elif y10 < 3.5:
            drivers.append(f"Rates: 10Y at {y10:.2f}% — accommodative, supports growth")
        else:
            drivers.append(f"Rates: 10Y at {y10:.2f}% — neutral zone")

        # VIX / vol driver
        vix = market_data.get("vix", 20)
        if vix > 25:
            drivers.append(f"Volatility: VIX at {vix:.1f} — elevated, hedging demand")
        elif vix < 15:
            drivers.append(f"Volatility: VIX at {vix:.1f} — complacency, squeeze risk")
        else:
            drivers.append(f"Volatility: VIX at {vix:.1f} — normal risk appetite")

        # Calendar / earnings
        if calendar_events:
            today = date.today()
            upcoming = [
                ev for ev in calendar_events
                if ev.get("event_date") and ev.get("importance") in ("high", "⭐⭐⭐")
            ]
            if upcoming:
                ev = upcoming[0]
                drivers.append(f"Event: {ev.get('title', ev.get('event_type', 'unknown'))} — binary risk")
            else:
                breadth = market_data.get("pct_above_sma50", 50)
                drivers.append(f"Breadth: {breadth:.0f}% above 50DMA — {'expanding' if breadth > 55 else 'narrowing' if breadth < 45 else 'neutral'}")
        else:
            breadth = market_data.get("pct_above_sma50", 50)
            drivers.append(f"Breadth: {breadth:.0f}% above 50DMA — {'expanding' if breadth > 55 else 'narrowing' if breadth < 45 else 'neutral'}")

        return drivers[:3]

    def _build_scenarios(
        self,
        regime: MarketRegime,
        market_data: Dict[str, Any],
        delta: Optional[DeltaSnapshot],
    ) -> ScenarioPlan:
        """Build base/bull/bear scenario map with triggers."""
        vix = market_data.get("vix", 20)
        spx = market_data.get("spx_close", 5000)
        breadth = market_data.get("pct_above_sma50", 50)

        if regime.risk == RiskRegime.RISK_ON:
            return ScenarioPlan(
                base_case={
                    "probability": 55,
                    "description": "Orderly uptrend continues; dips bought at 20DMA",
                    "action": "Maintain long bias, focus on leaders, trail stops",
                },
                bull_case={
                    "probability": 25,
                    "description": f"Breadth expands above {breadth+5:.0f}%, VIX stays < 18 — melt-up",
                    "action": "Press breakouts, add on pullbacks, size up to 120%",
                },
                bear_case={
                    "probability": 20,
                    "description": f"VIX spikes above {max(vix+10, 25):.0f} or SPX breaks below {spx*0.97:.0f}",
                    "action": "Cut gross to 50%, hedge via VIX calls or IWM puts",
                },
                triggers=[
                    f"BULL trigger: breadth > {breadth+5:.0f}% and VIX < 18",
                    f"BEAR trigger: VIX > {max(vix+10, 25):.0f} or SPX < {spx*0.97:.0f}",
                    f"NO TRADE trigger: VIX > 40 or SPX -3% intraday",
                ],
            )
        elif regime.risk == RiskRegime.RISK_OFF:
            return ScenarioPlan(
                base_case={
                    "probability": 50,
                    "description": "Continued weakness; rallies sold into resistance",
                    "action": "Cash 50%+, only mean-reversion at extreme oversold",
                },
                bull_case={
                    "probability": 20,
                    "description": f"VIX peaks and breadth troughs — capitulation washout",
                    "action": "Begin scaling into high-quality names at support",
                },
                bear_case={
                    "probability": 30,
                    "description": f"Credit spreads widen, breadth collapses below 20%",
                    "action": "Full cash, consider tail hedges",
                },
                triggers=[
                    f"RELIEF trigger: VIX drops below {max(vix-5, 20):.0f} + positive breadth divergence",
                    f"CRISIS trigger: HY spreads > 500bp or SPX -5% week",
                ],
            )
        else:
            return ScenarioPlan(
                base_case={
                    "probability": 50,
                    "description": "Choppy range — neither bulls nor bears in control",
                    "action": "Reduce size to 50-75%, prefer mean reversion at range extremes",
                },
                bull_case={
                    "probability": 25,
                    "description": f"Breadth expands, VIX drops below 18 — regime shifts risk-on",
                    "action": "Gradually increase long exposure, add breakout trades",
                },
                bear_case={
                    "probability": 25,
                    "description": f"VIX breaks above 25, SPX loses key support",
                    "action": "Cut to 30% gross, tighten all stops, add hedges",
                },
                triggers=[
                    f"RISK-ON trigger: breadth > 60% and VIX < 18 for 2 consecutive days",
                    f"RISK-OFF trigger: VIX > 25 and breadth < 40%",
                ],
            )

    def format_scoreboard_text(self, sb: RegimeScoreboard) -> str:
        """Format the scoreboard as a clean text block for reports/Discord."""
        lines = [
            f"## ✅ REGIME SCOREBOARD (Decision Layer)",
            f"- **Regime**: {sb.regime_label} (score: {sb.risk_on_score:.0f}/100)",
            f"- **Trend**: {sb.trend_state}",
            f"- **Volatility**: {sb.vol_state}",
            f"- **Risk Budget Today**:",
            f"  - Max Gross: {sb.max_gross_pct:.0f}%",
            f"  - Net Long Target: {sb.net_long_target_low:.0f}–{sb.net_long_target_high:.0f}%",
            f"  - Max Single Name: {sb.max_single_name_pct:.1f}%",
            f"  - Max Sector: {sb.max_sector_pct:.0f}%",
            f"- **Strategy Playbook**:",
        ]
        for s in sb.strategies_on:
            lines.append(f"  - ✅ {s}: ON")
        for sc in sb.strategies_conditional:
            lines.append(f"  - ⚠️ {sc['strategy']}: {sc['condition']}")
        for s in sb.strategies_off:
            lines.append(f"  - ❌ {s}: OFF")
        lines.append(f"- **No-Trade Triggers**: {', '.join(sb.no_trade_triggers[:3])}")

        return "\n".join(lines)
