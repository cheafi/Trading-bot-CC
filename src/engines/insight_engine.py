"""
TradingAI Bot — Insight Engine (v5)

The layer between raw signals and user-facing outputs.
Converts metrics + signals into *decision-grade* narratives and action plans.

Outputs:
  • MarketPlaybook  — daily regime → strategies → risk stance
  • TradeBrief      — per-signal institutional trade memo
  • RiskBulletin    — portfolio-level warnings

Everything is data-derived — no GPT hallucination.
"""
import logging
from datetime import datetime, date, timezone, timedelta
from typing import Dict, Any, List, Optional, Tuple

from src.core.models import (
    Signal, Direction, Horizon, MarketRegime,
    VolatilityRegime, TrendRegime, RiskRegime,
    MarketPlaybook, TradeBrief, RiskBulletin,
    ExecutionPlan, RiskPlan, EdgeModel,
    SetupBlock, EvidenceBlock, KeyLevel, ChangeItem,
)

logger = logging.getLogger(__name__)


# ═══════════════════════════════════════════════════════════════════════
# MARKET PLAYBOOK BUILDER
# ═══════════════════════════════════════════════════════════════════════

class PlaybookBuilder:
    """
    Builds the daily Market Playbook from regime + breadth + macro data.
    Answers: 'What regime are we in, and what's the playbook?'
    """

    # Regime → playbook text mapping (data-derived, not GPT)
    PLAYBOOK_MAP = {
        ("RISK_ON", "UPTREND", "NORMAL"): {
            "text": "Risk-on uptrend with normal volatility — full playbook active. "
                    "Breakouts, momentum, and trend-following are primary strategies. "
                    "Size positions at 100% normal. Allow breakout entries.",
            "strategies": ["momentum_breakout", "trend_following", "vcp", "classic_swing"],
            "stance": "full",
        },
        ("RISK_ON", "UPTREND", "LOW_VOL"): {
            "text": "Low-vol uptrend — ideal for VCP/squeeze setups. "
                    "Watch for BB squeezes releasing. Size at 100%. "
                    "Mean reversion less needed (trend is clean).",
            "strategies": ["vcp", "momentum_breakout", "classic_swing", "trend_following"],
            "stance": "full",
        },
        ("RISK_ON", "STRONG_UPTREND", "NORMAL"): {
            "text": "Strong uptrend with broad participation — stay aggressive. "
                    "Chase strength, add on pullbacks to 10/20 MA. "
                    "Avoid shorting. Size at 100-120% if win streak active.",
            "strategies": ["momentum_breakout", "trend_following", "momentum_rotation"],
            "stance": "full",
        },
        ("NEUTRAL", "NEUTRAL", "NORMAL"): {
            "text": "Choppy/neutral market — reduce conviction. "
                    "Prefer mean reversion and range-bound setups. "
                    "Size at 50-75%. Widen stops. Avoid breakouts (they fail in chop).",
            "strategies": ["mean_reversion", "short_term_mean_reversion"],
            "stance": "half",
        },
        ("NEUTRAL", "UPTREND", "HIGH_VOL"): {
            "text": "Uptrend but elevated volatility — be selective. "
                    "Only take A+ setups. Reduce size to 50-75%. "
                    "Wider stops (1.5x ATR). Avoid small caps.",
            "strategies": ["trend_following", "classic_swing"],
            "stance": "half",
        },
        ("RISK_OFF", "DOWNTREND", "HIGH_VOL"): {
            "text": "Risk-off regime — defensive mode. "
                    "Cash up to 50%+. Only mean reversion on oversold bounces. "
                    "No breakouts. Consider hedges (long VIX, short IWM).",
            "strategies": ["mean_reversion"],
            "stance": "cash_up",
        },
        ("RISK_OFF", "STRONG_DOWNTREND", "CRISIS"): {
            "text": "CRISIS MODE — NO NEW LONGS. "
                    "Cash is the position. Protect capital. "
                    "Wait for VIX to peak and breadth to trough before re-engaging.",
            "strategies": [],
            "stance": "cash_up",
        },
    }

    def build(
        self,
        regime: MarketRegime,
        market_data: Dict[str, Any],
        yesterday_regime: Optional[Dict[str, str]] = None,
        calendar_events: Optional[List[Dict]] = None,
    ) -> MarketPlaybook:
        """Build today's playbook from market state."""

        # Lookup playbook template
        key = (regime.risk.value, regime.trend.value, regime.volatility.value)
        template = self.PLAYBOOK_MAP.get(key)

        # Fallback: find closest match
        if not template:
            template = self._closest_match(key)

        # ── Key levels ──
        key_levels = self._derive_key_levels(market_data)

        # ── What changed? ──
        changes = self._detect_changes(regime, yesterday_regime, market_data)

        # ── Risk bulletin items ──
        risk_items = self._risk_bulletin_items(market_data, calendar_events)

        playbook = MarketPlaybook(
            playbook_date=date.today(),
            session="US_RTH",
            regime_label=f"{regime.risk.value}_{regime.trend.value}",
            volatility_regime=regime.volatility.value,
            trend_regime=regime.trend.value,
            risk_regime=regime.risk.value,
            risk_on_score=market_data.get("risk_on_score", 50),
            playbook_text=template["text"],
            recommended_strategies=template["strategies"],
            sizing_stance=template["stance"],
            key_levels=key_levels,
            change_summary=changes,
            risk_bulletin=risk_items,
        )

        logger.info(
            f"Playbook built: {playbook.regime_label} / "
            f"stance={playbook.sizing_stance} / "
            f"{len(playbook.recommended_strategies)} strategies"
        )
        return playbook

    def _closest_match(self, key: tuple) -> Dict:
        """Find closest playbook template when exact match missing."""
        risk, trend, vol = key
        # Try relaxing volatility first
        for v in ["NORMAL", "LOW_VOL", "HIGH_VOL"]:
            if (risk, trend, v) in self.PLAYBOOK_MAP:
                return self.PLAYBOOK_MAP[(risk, trend, v)]
        # Try relaxing trend
        for t in ["NEUTRAL", "UPTREND", "DOWNTREND"]:
            if (risk, t, vol) in self.PLAYBOOK_MAP:
                return self.PLAYBOOK_MAP[(risk, t, vol)]
        # Ultimate fallback
        return {
            "text": "Mixed conditions — be selective. Size at 50%. Only A+ setups.",
            "strategies": ["mean_reversion", "classic_swing"],
            "stance": "half",
        }

    def _derive_key_levels(self, market_data: Dict) -> List[KeyLevel]:
        """Derive key S/R levels from market data."""
        levels = []
        spx = market_data.get("spx_close", 0)
        if spx:
            levels.append(KeyLevel(
                label="SPX", price=round(spx, 2),
                significance="Current level"))
            # Round number levels
            for mult in [50, 100]:
                above = ((spx // mult) + 1) * mult
                below = (spx // mult) * mult
                levels.append(KeyLevel(
                    label=f"SPX R ({int(above)})", price=above,
                    significance=f"Round {mult} resistance"))
                levels.append(KeyLevel(
                    label=f"SPX S ({int(below)})", price=below,
                    significance=f"Round {mult} support"))

        vix = market_data.get("vix", 0)
        if vix:
            levels.append(KeyLevel(
                label="VIX Flip",
                price=20.0 if vix < 20 else 30.0,
                significance="Risk regime inflection"))

        return levels[:6]

    def _detect_changes(
        self,
        regime: MarketRegime,
        yesterday: Optional[Dict[str, str]],
        market_data: Dict,
    ) -> List[ChangeItem]:
        """Detect what changed overnight / since yesterday."""
        changes = []
        if yesterday:
            if yesterday.get("risk") != regime.risk.value:
                changes.append(ChangeItem(
                    category="regime",
                    description=f"Risk regime shifted: {yesterday.get('risk')} → {regime.risk.value}",
                    severity="warning"))
            if yesterday.get("volatility") != regime.volatility.value:
                changes.append(ChangeItem(
                    category="volatility",
                    description=f"Vol regime: {yesterday.get('volatility')} → {regime.volatility.value}",
                    severity="warning" if regime.volatility in [VolatilityRegime.HIGH_VOL, VolatilityRegime.CRISIS] else "info"))
            if yesterday.get("trend") != regime.trend.value:
                changes.append(ChangeItem(
                    category="leadership",
                    description=f"Trend: {yesterday.get('trend')} → {regime.trend.value}",
                    severity="info"))

        vix = market_data.get("vix", 0)
        vix_change = market_data.get("vix_change", 0)
        if abs(vix_change) > 2:
            changes.append(ChangeItem(
                category="volatility",
                description=f"VIX moved {vix_change:+.1f} to {vix:.1f}",
                severity="warning" if vix > 22 else "info"))

        spx_change = market_data.get("spx_change_pct", 0)
        if abs(spx_change) > 1.0:
            changes.append(ChangeItem(
                category="macro",
                description=f"SPX moved {spx_change:+.1f}% overnight",
                severity="warning" if spx_change < -1.5 else "info"))

        if not changes:
            changes.append(ChangeItem(
                category="macro",
                description="No major regime or macro shifts overnight.",
                severity="info"))

        return changes

    def _risk_bulletin_items(
        self,
        market_data: Dict,
        calendar_events: Optional[List[Dict]],
    ) -> List[str]:
        """Generate portfolio-level + market-structure warnings."""
        warnings = []
        vix = market_data.get("vix", 0)
        if vix > 25:
            warnings.append(f"⚠️ VIX at {vix:.1f} — elevated; widen stops and reduce size")
        if vix > 35:
            warnings.append(f"🔥 VIX CRISIS at {vix:.1f} — NO NEW LONGS recommended")

        breadth = market_data.get("pct_above_sma50", 50)
        if breadth < 30:
            warnings.append(f"📉 Breadth narrowing: only {breadth:.0f}% above 50-MA — correlation spike risk")
        if breadth > 80:
            warnings.append(f"📈 Breadth extreme: {breadth:.0f}% above 50-MA — potential mean-reversion setup for indices")

        if calendar_events:
            today = date.today()
            week_ahead = today + timedelta(days=7)
            earnings_count = sum(
                1 for ev in calendar_events
                if ev.get("event_type") == "earnings"
                and ev.get("event_date")
                and (today <= (date.fromisoformat(str(ev["event_date"])) if isinstance(ev["event_date"], str) else ev["event_date"]) <= week_ahead)
            )
            if earnings_count >= 5:
                warnings.append(
                    f"📅 {earnings_count} earnings this week — cluster risk; "
                    f"reduce mega-cap concentration")
            macro_events = [
                ev for ev in calendar_events
                if ev.get("event_type") in ("fomc", "cpi", "nfp", "ppi", "gdp")
                and ev.get("event_date")
                and (today <= (date.fromisoformat(str(ev["event_date"])) if isinstance(ev["event_date"], str) else ev["event_date"]) <= week_ahead)
            ]
            if macro_events:
                ev_names = ", ".join(ev.get("title", ev["event_type"]).upper() for ev in macro_events[:3])
                warnings.append(f"📊 Macro events this week: {ev_names} — consider hedging or reducing size")

        return warnings


# ═══════════════════════════════════════════════════════════════════════
# CALIBRATED EDGE MODEL (historically-conditioned probabilities)
# ═══════════════════════════════════════════════════════════════════════

class EdgeCalculator:
    """
    Computes calibrated P(T1), P(T2), P(stop), EV
    conditioned on strategy × regime × setup tags.

    Data source: analytics.signal_outcomes + analytics.regime_edge_stats tables.
    Falls back to base-rate estimates when insufficient data.
    """

    # Base-rate priors (used when calibration data is insufficient)
    BASE_RATES = {
        "momentum_breakout":  {"p_t1": 0.55, "p_t2": 0.35, "p_stop": 0.40, "ev": 0.8, "mae": -1.5, "days": 8},
        "vcp":                {"p_t1": 0.58, "p_t2": 0.38, "p_stop": 0.35, "ev": 1.0, "mae": -1.2, "days": 10},
        "mean_reversion":     {"p_t1": 0.62, "p_t2": 0.30, "p_stop": 0.38, "ev": 0.6, "mae": -1.8, "days": 5},
        "trend_following":    {"p_t1": 0.50, "p_t2": 0.32, "p_stop": 0.42, "ev": 0.9, "mae": -2.0, "days": 15},
        "classic_swing":      {"p_t1": 0.52, "p_t2": 0.33, "p_stop": 0.40, "ev": 0.7, "mae": -1.6, "days": 7},
    }
    DEFAULT_RATE = {"p_t1": 0.50, "p_t2": 0.30, "p_stop": 0.45, "ev": 0.5, "mae": -1.5, "days": 7}

    def __init__(self):
        self._calibration_cache: Dict[str, Dict] = {}
        self.logger = logging.getLogger(__name__)

    def load_calibration(self, rows: List[Dict]):
        """Load pre-computed regime edge stats from DB."""
        for r in rows:
            key = r.get("calibration_bucket", "")
            self._calibration_cache[key] = r

    def compute(
        self,
        signal: Signal,
        regime: MarketRegime,
        features: Dict[str, Any],
    ) -> EdgeModel:
        """
        Compute edge model for a signal.
        Uses calibration data if available, else base-rate priors with regime adjustments.
        """
        strategy = signal.strategy_id or "unknown"
        bucket = f"{strategy}|{regime.risk.value}|{regime.volatility.value}"

        # Check calibration cache
        calibrated = self._calibration_cache.get(bucket)
        if calibrated and calibrated.get("sample_size", 0) >= 30:
            return EdgeModel(
                p_stop=calibrated.get("p_stop", 0.5),
                p_t1=calibrated.get("p_t1", 0.5),
                p_t2=calibrated.get("p_t2", 0.3),
                expected_return_pct=calibrated.get("expected_return_pct", 0),
                expected_mae_pct=calibrated.get("expected_mae_pct", -1.5),
                expected_holding_days=calibrated.get("expected_holding_days", 7),
                calibration_bucket=bucket,
                sample_size=calibrated.get("sample_size", 0),
            )

        # Base rate + regime adjustments
        base = self.BASE_RATES.get(strategy, self.DEFAULT_RATE)
        p_t1 = base["p_t1"]
        p_t2 = base["p_t2"]
        p_stop = base["p_stop"]
        ev = base["ev"]
        mae = base["mae"]
        days = base["days"]

        # Regime adjustments (mechanical, not guessed)
        if regime.risk == RiskRegime.RISK_ON and regime.trend in [TrendRegime.UPTREND, TrendRegime.STRONG_UPTREND]:
            p_t1 += 0.05; p_t2 += 0.05; p_stop -= 0.05; ev += 0.3
        elif regime.risk == RiskRegime.RISK_OFF:
            p_t1 -= 0.08; p_t2 -= 0.05; p_stop += 0.08; ev -= 0.5; mae -= 0.5
        if regime.volatility == VolatilityRegime.HIGH_VOL:
            mae -= 0.5; days += 3
        elif regime.volatility == VolatilityRegime.LOW_VOL:
            mae += 0.3; days -= 2

        # Feature adjustments
        rel_vol = features.get("relative_volume", 1)
        if rel_vol >= 2.0:
            p_t1 += 0.03; ev += 0.1
        rsi = features.get("rsi_14", 50)
        if strategy in ("mean_reversion",) and rsi < 30:
            p_t1 += 0.05  # oversold bounce works better

        # Clamp
        p_t1 = max(0.1, min(0.9, p_t1))
        p_t2 = max(0.05, min(0.8, p_t2))
        p_stop = max(0.1, min(0.8, p_stop))

        return EdgeModel(
            p_stop=round(p_stop, 3),
            p_t1=round(p_t1, 3),
            p_t2=round(p_t2, 3),
            expected_return_pct=round(ev, 2),
            expected_mae_pct=round(mae, 2),
            expected_holding_days=max(1, round(days)),
            calibration_bucket=bucket,
            sample_size=0,  # indicates base-rate fallback
        )


# ═══════════════════════════════════════════════════════════════════════
# TRADE BRIEF BUILDER
# ═══════════════════════════════════════════════════════════════════════

class TradeBriefBuilder:
    """
    Converts a Signal + EdgeModel + regime into a full TradeBrief.
    Answers the 6 trader questions:
      1. Why this trade now?
      2. How to enter?
      3. What invalidates it?
      4. What are the odds?
      5. What could kill me?
      6. What changes my mind?
    """

    def build(
        self,
        signal: Signal,
        edge: EdgeModel,
        regime: MarketRegime,
        features: Dict[str, Any],
        calendar_events: Optional[List[Dict]] = None,
    ) -> TradeBrief:

        # ── Execution plan ──
        exec_plan = self._build_execution_plan(signal, features, calendar_events)

        # ── Risk plan ──
        risk_plan = self._build_risk_plan(signal, features)

        # ── Setup block ──
        setup_tags = (signal.feature_snapshot or {}).get("setup_tags", [])
        setup = SetupBlock(
            setup_tags=setup_tags,
            trigger=self._derive_trigger(signal),
            time_stop_days=self._time_stop(signal.horizon),
        )

        # ── Evidence ──
        evidence = EvidenceBlock(
            market_regime={
                "risk": regime.risk.value,
                "trend": regime.trend.value,
                "vol": regime.volatility.value,
            },
            features={
                "rsi_14": features.get("rsi_14", 0),
                "adx_14": features.get("adx_14", 0),
                "relative_volume": features.get("relative_volume", 1),
            },
        )

        # ── What changes my mind? ──
        invalidation = self._invalidation_sentence(signal)
        what_changes = self._what_changes_mind(signal, regime)

        return TradeBrief(
            ticker=signal.ticker,
            direction=signal.direction,
            horizon=signal.horizon,
            entry_logic=signal.entry_logic,
            invalidation_sentence=invalidation,
            catalyst=signal.catalyst,
            key_risks=signal.key_risks[:5],
            confidence=signal.confidence,
            rationale=signal.rationale,
            setup=setup,
            execution_plan=exec_plan,
            risk_plan=risk_plan,
            edge_model=edge,
            evidence=evidence,
            what_changes_mind=what_changes,
        )

    def _build_execution_plan(
        self, signal: Signal, features: Dict, calendar: Optional[List[Dict]]
    ) -> ExecutionPlan:
        avoid_times = []
        if calendar:
            today = date.today()
            for ev in calendar:
                ev_date = ev.get("event_date")
                if isinstance(ev_date, str):
                    ev_date = date.fromisoformat(ev_date)
                if ev_date == today and ev.get("event_type") in ("fomc", "cpi", "nfp"):
                    avoid_times.append(f"{ev['event_type'].upper()} @ {ev.get('event_time', 'TBD')}")

        # Order type heuristic
        rel_vol = features.get("relative_volume", 1)
        if signal.direction == Direction.LONG:
            order_type = "STOP_LIMIT" if rel_vol < 2 else "MARKET"
        else:
            order_type = "LIMIT"

        return ExecutionPlan(
            order_type=order_type,
            entry_window="first_90_min_or_after_11am",
            avoid_times=avoid_times,
            scale_in=[
                {"pct": 50, "condition": "breakout + volume confirmation"},
                {"pct": 50, "condition": "retest of breakout level holds"},
            ] if signal.horizon in (Horizon.SWING_5_15D, Horizon.POSITION_15_60D) else [],
        )

    def _build_risk_plan(self, signal: Signal, features: Dict) -> RiskPlan:
        stop_dist = abs(signal.entry_price - signal.invalidation.stop_price) if signal.invalidation else 0
        risk_pct = (stop_dist / signal.entry_price * 100) if signal.entry_price else 5

        target_1 = signal.targets[0].price if signal.targets else signal.entry_price * 1.05
        reward_dist = abs(target_1 - signal.entry_price)
        rr_t1 = reward_dist / stop_dist if stop_dist else 0

        target_2 = signal.targets[1].price if len(signal.targets) > 1 else None
        rr_t2 = (abs(target_2 - signal.entry_price) / stop_dist) if target_2 and stop_dist else None

        # Liquidity tier
        dollar_vol = features.get("dollar_volume_20d", 0)
        if dollar_vol >= 50_000_000:
            liq_tier = "A"
        elif dollar_vol >= 10_000_000:
            liq_tier = "B"
        else:
            liq_tier = "C"

        # Gap risk: earnings within 5 days
        earn_days = (signal.feature_snapshot or {}).get("earnings_risk_days")
        gap_flag = earn_days is not None and isinstance(earn_days, int) and earn_days <= 5

        return RiskPlan(
            risk_per_trade_pct=1.0,
            position_size_pct=round(1.0 / (risk_pct / 100) * 0.01, 2) if risk_pct > 0 else 3.0,
            rr_to_t1=round(rr_t1, 2),
            rr_to_t2=round(rr_t2, 2) if rr_t2 else None,
            gap_risk_flag=gap_flag,
            liquidity_tier=liq_tier,
        )

    def _derive_trigger(self, signal: Signal) -> str:
        direction = signal.direction.value
        if direction == "LONG":
            return f"Buy stop above ${signal.entry_price:.2f}"
        return f"Sell limit below ${signal.entry_price:.2f}"

    def _time_stop(self, horizon: Horizon) -> int:
        return {
            Horizon.INTRADAY: 1,
            Horizon.SWING_1_5D: 5,
            Horizon.SWING_5_15D: 10,
            Horizon.POSITION_15_60D: 30,
        }.get(horizon, 10)

    def _invalidation_sentence(self, signal: Signal) -> str:
        if signal.invalidation:
            return (
                f"Close {'below' if signal.direction == Direction.LONG else 'above'} "
                f"${signal.invalidation.stop_price:.2f} "
                f"({signal.invalidation.stop_type.value}) — trade is dead."
            )
        return "No explicit invalidation level set."

    def _what_changes_mind(self, signal: Signal, regime: MarketRegime) -> str:
        parts = []
        if regime.risk == RiskRegime.RISK_ON:
            parts.append("If VIX > 30 and breadth < 30%, downgrade to NEUTRAL")
        if signal.direction == Direction.LONG:
            parts.append(f"If {signal.ticker} closes below stop for 2 consecutive days, exit")
        parts.append("If regime flips RISK_OFF, reduce all positions by 50%")
        return ". ".join(parts) + "."


# ═══════════════════════════════════════════════════════════════════════
# RISK BULLETIN BUILDER
# ═══════════════════════════════════════════════════════════════════════

class RiskBulletinBuilder:
    """Portfolio-level risk warnings."""

    def build(
        self,
        signals: List[Signal],
        regime: MarketRegime,
        market_data: Dict[str, Any],
        portfolio: Optional[Dict] = None,
        calendar_events: Optional[List[Dict]] = None,
    ) -> RiskBulletin:
        warnings = []

        # ── VIX ──
        vix = market_data.get("vix", 0)
        if vix > 25:
            warnings.append(f"VIX at {vix:.1f} — reduce position sizes by 30%")
        if vix > 35:
            warnings.append(f"VIX CRISIS at {vix:.1f} — close all longs, go to cash")

        # ── Breadth ──
        breadth = market_data.get("pct_above_sma50", 50)
        correlation_risk = breadth < 30
        if correlation_risk:
            warnings.append(f"Breadth at {breadth:.0f}% — correlation spike risk")

        # ── Earnings cluster ──
        earnings_cluster = False
        event_windows = []
        if calendar_events:
            today = date.today()
            week = today + timedelta(days=7)
            earn_tickers = [
                ev.get("ticker", "?") for ev in calendar_events
                if ev.get("event_type") == "earnings"
                and ev.get("event_date")
                and (today <= (date.fromisoformat(str(ev["event_date"])) if isinstance(ev["event_date"], str) else ev["event_date"]) <= week)
            ]
            if len(earn_tickers) >= 5:
                earnings_cluster = True
                warnings.append(f"{len(earn_tickers)} earnings this week: {', '.join(earn_tickers[:10])}")
            macro_events = [
                ev for ev in calendar_events
                if ev.get("event_type") in ("fomc", "cpi", "nfp", "ppi", "gdp")
                and ev.get("event_date")
                and (today <= (date.fromisoformat(str(ev["event_date"])) if isinstance(ev["event_date"], str) else ev["event_date"]) <= week)
            ]
            event_windows = [f"{ev.get('title', ev['event_type'])} on {ev['event_date']}" for ev in macro_events]

        # ── Open risk ──
        max_risk = 0.0
        if portfolio:
            positions = portfolio.get("positions", {})
            for sym, pos in positions.items():
                risk_pct = abs(pos.get("entry_price", 0) - pos.get("stop_loss", 0)) / pos.get("entry_price", 1) * 100
                max_risk += risk_pct * pos.get("weight", 0)

        # Recommendation
        if regime.volatility == VolatilityRegime.CRISIS:
            rec = "FULL DEFENSIVE — no new positions"
        elif len(warnings) >= 3:
            rec = "CAUTION — reduce size and widen stops"
        elif not warnings:
            rec = "ALL CLEAR — normal operations"
        else:
            rec = "SELECTIVE — proceed with A+ setups only"

        return RiskBulletin(
            generated_at=datetime.now(timezone.utc),
            warnings=warnings,
            earnings_cluster_risk=earnings_cluster,
            correlation_spike_risk=correlation_risk,
            event_windows=event_windows,
            max_open_risk_pct=round(max_risk, 2),
            recommendation=rec,
        )


# ═══════════════════════════════════════════════════════════════════════
# INSIGHT ENGINE  (master orchestrator)
# ═══════════════════════════════════════════════════════════════════════

class InsightEngine:
    """
    Master orchestrator: converts raw signals + market data into
    decision-grade insight contracts.

    Pipeline:
      market_data → PlaybookBuilder → MarketPlaybook
      signals     → EdgeCalculator → TradeBriefBuilder → TradeBrief[]
      portfolio   → RiskBulletinBuilder → RiskBulletin
    """

    def __init__(self):
        self.playbook_builder = PlaybookBuilder()
        self.edge_calculator = EdgeCalculator()
        self.brief_builder = TradeBriefBuilder()
        self.risk_builder = RiskBulletinBuilder()
        self.logger = logging.getLogger(__name__)

    def generate_insights(
        self,
        signals: List[Signal],
        regime: MarketRegime,
        market_data: Dict[str, Any],
        features_by_ticker: Dict[str, Dict[str, Any]],
        portfolio: Optional[Dict] = None,
        calendar_events: Optional[List[Dict]] = None,
        yesterday_regime: Optional[Dict[str, str]] = None,
    ) -> Dict[str, Any]:
        """
        Full insight generation pipeline.

        Returns:
            {
                "playbook": MarketPlaybook,
                "trade_briefs": [TradeBrief, ...],
                "risk_bulletin": RiskBulletin,
            }
        """
        # 1. Market Playbook
        playbook = self.playbook_builder.build(
            regime, market_data, yesterday_regime, calendar_events
        )

        # 2. Trade Briefs (one per signal)
        briefs = []
        for sig in signals:
            feat = features_by_ticker.get(sig.ticker, {})
            edge = self.edge_calculator.compute(sig, regime, feat)
            brief = self.brief_builder.build(
                sig, edge, regime, feat, calendar_events
            )
            briefs.append(brief)

        # 3. Risk Bulletin
        bulletin = self.risk_builder.build(
            signals, regime, market_data, portfolio, calendar_events
        )

        self.logger.info(
            f"InsightEngine: playbook={playbook.sizing_stance}, "
            f"briefs={len(briefs)}, warnings={len(bulletin.warnings)}"
        )

        return {
            "playbook": playbook,
            "trade_briefs": briefs,
            "risk_bulletin": bulletin,
        }
