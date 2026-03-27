"""
TradingAI Bot - Signal Engine (v6 — Pro Desk)
Main orchestrator for signal generation pipeline.

Upgrades (v6):
  • Data quality gates run BEFORE features/signals
  • Delta tracker + regime scoreboard integration
  • Signal v6 fields: setup_grade, edge_type, time_stop_days, event_risk,
    scenario_plan, portfolio_fit, evidence, expected_value, approval_status, why_now
  • Universe quality filter — removes illiquid / penny / corporate-action noise
  • Unified score (0-100) with calibration hooks
  • Edge Checklist per signal (setup_tags + regime_required)
  • NO TRADE as a hard gate stored in system.market_state
  • Signal dedup + conflict resolution
"""
import asyncio
import hashlib
from datetime import datetime, date, timedelta
from typing import List, Dict, Optional, Any, Tuple
import logging
import pandas as pd

from src.core.models import (
    Signal, MarketRegime, VolatilityRegime, TrendRegime, RiskRegime,
    MarketPlaybook, TradeBrief, RiskBulletin,
)
from src.core.config import get_trading_config
from src.strategies import get_strategy, get_all_strategies, BaseStrategy
from src.engines.insight_engine import InsightEngine


# ═══════════════════════════════════════════════════════════════════════
# UNIVERSE QUALITY FILTER
# ═══════════════════════════════════════════════════════════════════════

class UniverseFilter:
    """
    Hard quality gates — reject tickers that destroy edge in live trading.
    These run BEFORE any strategy, saving compute and preventing bad signals.
    """

    # Configurable thresholds (override via config dict)
    DEFAULT_GATES = {
        "min_price":           5.0,        # No penny stocks
        "min_dollar_vol_20d":  5_000_000,  # $5M daily dollar volume minimum
        "min_avg_volume_20d":  200_000,    # 200K shares/day minimum
        "max_spread_pct":      1.0,        # Proxy: (high-low)/close < 1%
        "min_market_cap":      500_000_000, # $500M minimum market cap
        "min_history_days":    60,          # Need 60 days of clean data
        "earnings_blackout_days": 2,        # Skip 2 days before earnings
    }

    def __init__(self, overrides: Optional[Dict] = None):
        self.gates = {**self.DEFAULT_GATES, **(overrides or {})}
        self.logger = logging.getLogger(__name__)
        self._rejection_log: List[Dict] = []

    def filter(
        self,
        universe: List[str],
        features: pd.DataFrame,
        calendar_events: Optional[List[Dict]] = None,
        corporate_actions: Optional[List[Dict]] = None,
    ) -> Tuple[List[str], Dict[str, str]]:
        """
        Filter universe to tradeable names only.

        Returns:
            (clean_universe, rejection_map) where rejection_map = {ticker: reason}
        """
        rejections: Dict[str, str] = {}
        clean: List[str] = []

        # Build earnings-blackout set
        blackout_tickers = set()
        if calendar_events:
            cutoff = date.today() + timedelta(days=self.gates["earnings_blackout_days"])
            for ev in calendar_events:
                if ev.get("event_type") == "earnings" and ev.get("ticker"):
                    ev_date = ev.get("event_date")
                    if isinstance(ev_date, str):
                        ev_date = date.fromisoformat(ev_date)
                    if ev_date and ev_date <= cutoff:
                        blackout_tickers.add(ev["ticker"])

        # Build corporate-action-flagged set
        action_tickers = set()
        if corporate_actions:
            recent = date.today() - timedelta(days=5)
            for ca in corporate_actions:
                ca_date = ca.get("action_date")
                if isinstance(ca_date, str):
                    ca_date = date.fromisoformat(ca_date)
                if ca_date and ca_date >= recent:
                    action_tickers.add(ca["ticker"])

        for ticker in universe:
            # Per-ticker feature row (latest)
            tf = features[features.index.get_level_values("ticker") == ticker] if "ticker" in features.index.names else features[features.get("ticker") == ticker] if "ticker" in features.columns else pd.DataFrame()

            # Fallback: try simple column lookup
            row = {}
            if not tf.empty:
                row = tf.iloc[-1].to_dict() if hasattr(tf.iloc[-1], "to_dict") else {}

            price = row.get("close", row.get("sma_20", 0)) or 0
            avg_vol = row.get("volume_sma_20", 0) or 0
            mkt_cap = row.get("market_cap", float("inf")) or float("inf")
            history_len = len(tf)

            dollar_vol = price * avg_vol

            # --- Gate checks ---
            if price < self.gates["min_price"]:
                rejections[ticker] = f"price ${price:.2f} < ${self.gates['min_price']}"
                continue
            if dollar_vol < self.gates["min_dollar_vol_20d"]:
                rejections[ticker] = f"dollar_vol ${dollar_vol:,.0f} < ${self.gates['min_dollar_vol_20d']:,.0f}"
                continue
            if avg_vol < self.gates["min_avg_volume_20d"]:
                rejections[ticker] = f"avg_vol {avg_vol:,.0f} < {self.gates['min_avg_volume_20d']:,.0f}"
                continue
            if mkt_cap < self.gates["min_market_cap"]:
                rejections[ticker] = f"mkt_cap ${mkt_cap:,.0f} < ${self.gates['min_market_cap']:,.0f}"
                continue
            if history_len < self.gates["min_history_days"]:
                rejections[ticker] = f"history {history_len}d < {self.gates['min_history_days']}d"
                continue
            if ticker in blackout_tickers:
                rejections[ticker] = "earnings_blackout"
                continue
            if ticker in action_tickers:
                rejections[ticker] = "recent_corporate_action"
                continue

            clean.append(ticker)

        self.logger.info(
            f"Universe filter: {len(universe)} → {len(clean)} "
            f"({len(rejections)} rejected)"
        )
        self._rejection_log = [{"ticker": t, "reason": r} for t, r in rejections.items()]
        return clean, rejections


# ═══════════════════════════════════════════════════════════════════════
# SCORE UNIFICATION
# ═══════════════════════════════════════════════════════════════════════

class ScoreUnifier:
    """
    One canonical signal_score_0_100.
    Everything else derives from it — no "vibes" scoring.
    """

    # Calibration table: strategy+regime → score→win_rate (loaded from DB)
    _calibration: Dict[str, Dict[int, float]] = {}

    @staticmethod
    def unify(raw_confidence: int) -> Dict[str, Any]:
        """Map raw confidence (0-100) to all derived scores."""
        score = max(0, min(100, raw_confidence))
        return {
            "signal_score_0_100": score,
            "ai_score_0_10": round(score / 10, 1),
            "confidence_bucket": (
                "HIGH" if score >= 80 else
                "GOOD" if score >= 65 else
                "MODERATE" if score >= 50 else
                "LOW"
            ),
            "display_bar": "█" * (score // 10) + "░" * (10 - score // 10),
        }

    @classmethod
    def calibrated_win_rate(
        cls,
        strategy_id: str,
        regime_label: str,
        score: int,
    ) -> Optional[float]:
        """
        Look up historically-calibrated win rate for this score bracket.
        Returns None if no calibration data exists yet.
        """
        key = f"{strategy_id}:{regime_label}"
        bucket = (score // 10) * 10  # 0,10,20,...90
        return cls._calibration.get(key, {}).get(bucket)

    @classmethod
    def load_calibration(cls, rows: List[Dict]):
        """Load calibration rows from analytics.score_calibration table."""
        for r in rows:
            key = f"{r['strategy_id']}:{r.get('regime_label', 'ALL')}"
            if key not in cls._calibration:
                cls._calibration[key] = {}
            cls._calibration[key][r["score_bucket_low"]] = r["historical_win_rate"]


# ═══════════════════════════════════════════════════════════════════════
# EDGE CHECKLIST
# ═══════════════════════════════════════════════════════════════════════

class EdgeChecklist:
    """
    Standardized, mechanical setup validation per signal.
    Stored with the signal so GPT validates the *checklist*, not vibes.
    """

    @staticmethod
    def build(
        signal: Signal,
        features_row: Dict[str, Any],
        regime: MarketRegime,
        calendar_events: Optional[List[Dict]] = None,
    ) -> Dict[str, Any]:
        """Build edge checklist for a signal."""
        # Setup tags from features
        tags: List[str] = []
        rsi = features_row.get("rsi_14", 50)
        adx = features_row.get("adx_14", 0)
        rel_vol = features_row.get("relative_volume", 1.0)
        dist_sma20 = features_row.get("dist_from_sma20", 0)
        dist_sma50 = features_row.get("dist_from_sma50", 0)
        dist_sma200 = features_row.get("dist_from_sma200", 0)

        if dist_sma20 > 0:
            tags.append("above_sma20")
        if dist_sma50 > 0:
            tags.append("above_sma50")
        if dist_sma200 > 0:
            tags.append("above_sma200")
        if adx > 25:
            tags.append("trend_strong")
        if rel_vol >= 2.0:
            tags.append("rel_volume_2x")
        elif rel_vol >= 1.5:
            tags.append("vol_expansion")
        if 30 <= rsi <= 45:
            tags.append("rsi_oversold_bounce")
        if 55 <= rsi <= 70:
            tags.append("rsi_momentum_zone")
        if rsi > 75:
            tags.append("rsi_overbought")
        if rsi < 25:
            tags.append("rsi_extreme_oversold")

        # Trend alignment
        if dist_sma20 > 0 and dist_sma50 > 0 and dist_sma200 > 0:
            tags.append("all_ma_aligned_up")
        elif dist_sma20 < 0 and dist_sma50 < 0 and dist_sma200 < 0:
            tags.append("all_ma_aligned_down")

        # Regime required
        regime_required: List[str] = []
        if regime.risk != RiskRegime.RISK_OFF:
            regime_required.append(regime.risk.value)
        if regime.trend.value in ["UPTREND", "STRONG_UPTREND"]:
            regime_required.append(regime.trend.value)
        regime_required.append(regime.volatility.value)

        # Earnings risk proximity
        earnings_days: Optional[int] = None
        if calendar_events:
            today = date.today()
            for ev in calendar_events:
                if ev.get("event_type") == "earnings" and ev.get("ticker") == signal.ticker:
                    ev_date = ev.get("event_date")
                    if isinstance(ev_date, str):
                        ev_date = date.fromisoformat(ev_date)
                    if ev_date and ev_date >= today:
                        earnings_days = (ev_date - today).days
                        break

        # R:R validation
        stop_dist = abs(signal.entry_price - signal.invalidation.stop_price) if signal.invalidation else 0
        target_dist = abs(signal.targets[0].price - signal.entry_price) if signal.targets else 0
        rr_ratio = target_dist / stop_dist if stop_dist > 0 else 0

        # ATR check: is stop too tight?
        atr = features_row.get("atr_14", 0)
        stop_vs_atr = stop_dist / atr if atr > 0 else float("inf")

        return {
            "setup_tags": tags,
            "regime_required": regime_required,
            "regime_at_signal": {
                "volatility": regime.volatility.value,
                "trend": regime.trend.value,
                "risk": regime.risk.value,
            },
            "earnings_risk_days": earnings_days,
            "rr_ratio": round(rr_ratio, 2),
            "stop_vs_atr": round(stop_vs_atr, 2),
            "stop_too_tight": stop_vs_atr < 0.5,
            "rsi": round(rsi, 1),
            "adx": round(adx, 1),
            "relative_volume": round(rel_vol, 2),
            "dollar_volume_20d": features_row.get("dollar_volume_20d", 0),
        }


# ═══════════════════════════════════════════════════════════════════════
# SIGNAL DEDUP + CONFLICT RESOLUTION
# ═══════════════════════════════════════════════════════════════════════

class SignalDedup:
    """Prevent duplicate and conflicting signals."""

    @staticmethod
    def dedupe_key(signal: Signal) -> str:
        """Generate deterministic dedup key."""
        raw = f"{signal.ticker}:{signal.direction.value}:{signal.horizon.value}:{signal.strategy_id or 'unknown'}"
        return hashlib.sha256(raw.encode()).hexdigest()[:32]

    @staticmethod
    def resolve_conflicts(signals: List[Signal]) -> Tuple[List[Signal], List[Dict]]:
        """
        When multiple strategies hit the same ticker with different directions,
        keep the higher-confidence one and log the resolution.
        """
        from collections import defaultdict
        by_ticker: Dict[str, List[Signal]] = defaultdict(list)
        for s in signals:
            by_ticker[s.ticker].append(s)

        kept: List[Signal] = []
        resolutions: List[Dict] = []

        for ticker, group in by_ticker.items():
            if len(group) == 1:
                kept.append(group[0])
                continue

            # Check for direction conflicts
            directions = set(s.direction.value for s in group)
            if len(directions) > 1:
                # Conflict: different directions on same ticker
                winner = max(group, key=lambda s: s.confidence)
                losers = [s for s in group if s is not winner]
                kept.append(winner)
                resolutions.append({
                    "ticker": ticker,
                    "kept": f"{winner.strategy_id}:{winner.direction.value} (conf={winner.confidence})",
                    "dropped": [f"{s.strategy_id}:{s.direction.value} (conf={s.confidence})" for s in losers],
                    "reason": "direction_conflict",
                })
            else:
                # Same direction: keep highest confidence
                winner = max(group, key=lambda s: s.confidence)
                kept.append(winner)
                if len(group) > 1:
                    resolutions.append({
                        "ticker": ticker,
                        "kept": f"{winner.strategy_id} (conf={winner.confidence})",
                        "dropped": [f"{s.strategy_id} (conf={s.confidence})" for s in group if s is not winner],
                        "reason": "duplicate_same_direction",
                    })

        return kept, resolutions


class RegimeDetector:
    """
    Detects current market regime to determine which strategies to run.
    """
    
    def __init__(self):
        self.logger = logging.getLogger(__name__)
    
    def detect(self, market_data: Dict[str, Any]) -> MarketRegime:
        """
        Classify current market regime.
        
        Args:
            market_data: Dict with keys like 'vix', 'vix_term_structure', 
                        'pct_above_sma50', 'hy_spread', etc.
        
        Returns:
            MarketRegime with volatility, trend, risk classification and active strategies
        """
        vix = market_data.get('vix', 20)
        vix_term = market_data.get('vix_term_structure', 1.0)
        pct_above_50 = market_data.get('pct_above_sma50', 50)
        hy_spread = market_data.get('hy_spread', 350)
        
        # Volatility regime
        if vix > 35:
            vol_regime = VolatilityRegime.CRISIS
        elif vix > 25:
            vol_regime = VolatilityRegime.HIGH_VOL
        elif vix > 18:
            vol_regime = VolatilityRegime.NORMAL
        else:
            vol_regime = VolatilityRegime.LOW_VOL
        
        # Trend regime based on breadth
        if pct_above_50 > 70:
            trend_regime = TrendRegime.STRONG_UPTREND
        elif pct_above_50 > 55:
            trend_regime = TrendRegime.UPTREND
        elif pct_above_50 > 45:
            trend_regime = TrendRegime.NEUTRAL
        elif pct_above_50 > 30:
            trend_regime = TrendRegime.DOWNTREND
        else:
            trend_regime = TrendRegime.STRONG_DOWNTREND
        
        # Risk regime based on VIX term structure and credit
        if vix_term < 0.9 and hy_spread > 400:
            risk_regime = RiskRegime.RISK_OFF
        elif vix_term > 1.05 and hy_spread < 350:
            risk_regime = RiskRegime.RISK_ON
        else:
            risk_regime = RiskRegime.NEUTRAL
        
        # Determine active strategies
        strategy_weights = self._get_active_strategies(vol_regime, trend_regime, risk_regime)
        active_strategies = list(strategy_weights.keys())
        
        self.logger.info(
            f"Regime detected: vol={vol_regime.value}, trend={trend_regime.value}, "
            f"risk={risk_regime.value}, strategies={active_strategies}"
        )
        
        return MarketRegime(
            timestamp=datetime.utcnow(),
            volatility=vol_regime,
            trend=trend_regime,
            risk=risk_regime,
            active_strategies=active_strategies,
            strategy_weights=strategy_weights,
        )
    
    def _get_active_strategies(
        self, 
        vol: VolatilityRegime, 
        trend: TrendRegime, 
        risk: RiskRegime
    ) -> Dict[str, float]:
        """
        Map regime to active strategies with confidence weights.
        
        Returns:
            Dict mapping strategy_id -> weight (0.0-1.0).
            Higher weight = more regime-appropriate = higher position sizing.
        """
        
        # NO TRADE conditions
        if vol == VolatilityRegime.CRISIS:
            return {}
        
        if trend == TrendRegime.STRONG_DOWNTREND and risk == RiskRegime.RISK_OFF:
            return {}
        
        weights: Dict[str, float] = {}
        
        # ── Base weights by trend alignment ───────────────────────
        is_uptrend = trend in [TrendRegime.UPTREND, TrendRegime.STRONG_UPTREND]
        is_neutral = trend == TrendRegime.NEUTRAL
        is_downtrend = trend in [TrendRegime.DOWNTREND, TrendRegime.STRONG_DOWNTREND]
        is_low_vol = vol in [VolatilityRegime.LOW_VOL, VolatilityRegime.NORMAL]
        
        # Momentum / trend strategies - best in uptrends with normal vol
        if is_uptrend and vol != VolatilityRegime.HIGH_VOL:
            boost = 1.0 if trend == TrendRegime.STRONG_UPTREND else 0.8
            weights["momentum_breakout"] = boost
            weights["momentum_v1"] = boost
            weights["short_term_trend_following"] = boost * 0.9
            weights["trend_following"] = boost
            weights["momentum_rotation"] = boost * 0.85
        
        # VCP works in low vol (tight base / squeeze)
        if is_low_vol and not is_downtrend:
            weights["vcp"] = 0.9 if vol == VolatilityRegime.LOW_VOL else 0.7
        
        # Mean reversion - normal/low vol, avoid strong downtrend
        if is_low_vol and not is_downtrend:
            mr_w = 0.85 if is_neutral else 0.65
            weights["mean_reversion"] = mr_w
            weights["mean_reversion_v1"] = mr_w
            weights["short_term_mean_reversion"] = mr_w * 0.9
        
        # Breakout and swing - neutral/uptrend
        if not is_downtrend:
            sw_w = 0.9 if is_uptrend else 0.7
            weights["breakout_v1"] = sw_w
            weights["classic_swing"] = sw_w
        
        # Earnings strategies - always active (self-filter on calendar)
        weights["pre_earnings_momentum"] = 0.6
        weights["post_earnings_drift"] = 0.6
        weights["earnings_breakout"] = 0.6
        
        # ── Global risk dampener ──────────────────────────────────
        if vol == VolatilityRegime.HIGH_VOL:
            weights = {k: v * 0.6 for k, v in weights.items()}
        if risk == RiskRegime.RISK_OFF:
            weights = {k: v * 0.5 for k, v in weights.items()}
        
        return weights


class RiskModel:
    """
    Portfolio-level risk management.
    """
    
    def __init__(self, config: Optional[Dict] = None):
        trading_config = get_trading_config()
        config = config or {}
        self.max_position_pct = config.get('max_position_pct', trading_config.max_position_pct)
        self.max_sector_pct = config.get('max_sector_pct', trading_config.max_sector_pct)
        self.max_correlation = config.get('max_correlation', trading_config.max_correlation)
        self.min_confidence = config.get('min_confidence', trading_config.min_confidence)
        self.logger = logging.getLogger(__name__)
    
    def filter_and_size(
        self, 
        signals: List[Signal], 
        portfolio: Optional[Dict] = None
    ) -> List[Signal]:
        """
        Apply risk filters and calculate position sizes.
        
        Args:
            signals: Raw signals from strategies
            portfolio: Current portfolio state (positions, cash, etc.)
        
        Returns:
            Filtered and sized signals
        """
        portfolio = portfolio or {}
        
        # Filter by minimum confidence
        signals = [s for s in signals if s.confidence >= self.min_confidence]
        
        # Filter out duplicates (same ticker from different strategies)
        seen_tickers = set()
        unique_signals = []
        for signal in sorted(signals, key=lambda s: s.confidence, reverse=True):
            if signal.ticker not in seen_tickers:
                seen_tickers.add(signal.ticker)
                unique_signals.append(signal)
        
        signals = unique_signals
        
        # Filter out existing positions — use positions_by_ticker (dict)
        # with fallback to positions (may be list or dict)
        pos_raw = portfolio.get('positions_by_ticker',
                                portfolio.get('positions', {}))
        if isinstance(pos_raw, dict):
            existing_positions = set(pos_raw.keys())
        elif isinstance(pos_raw, list):
            existing_positions = {
                getattr(p, 'ticker', getattr(p, 'symbol', ''))
                if not isinstance(p, dict)
                else p.get('ticker', p.get('symbol', ''))
                for p in pos_raw
            }
        else:
            existing_positions = set()
        signals = [s for s in signals if s.ticker not in existing_positions]
        
        # Calculate position sizes
        for signal in signals:
            signal.position_size_pct = self._calculate_position_size(signal, portfolio)
        
        # Filter out signals with 0 position size
        signals = [s for s in signals if (s.position_size_pct or 0) > 0]
        
        self.logger.info(f"Risk model: {len(signals)} signals passed filters")
        
        return signals
    
    def _calculate_position_size(
        self, signal: Signal, portfolio: Dict,
    ) -> float:
        """Calculate position size based on risk parameters.

        Uses half-Kelly fraction when EdgeCalculator data
        (p_t1, risk_reward_ratio) is available on the signal,
        otherwise falls back to confidence-scaled risk sizing.
        """
        equity = portfolio.get('equity', 100000)
        risk_per_trade = portfolio.get(
            'risk_per_trade', 0.01,
        )  # Configurable, default 1%

        # Risk-based sizing
        if signal.invalidation.stop_price and signal.entry_price:
            stop_distance = abs(
                signal.entry_price
                - signal.invalidation.stop_price
            )
            stop_pct = (
                stop_distance / signal.entry_price
                if signal.entry_price > 0 else 0.05
            )

            if stop_pct > 0:
                base_size = risk_per_trade / stop_pct
            else:
                base_size = self.max_position_pct * 0.5
        else:
            base_size = self.max_position_pct * 0.5

        # ── Half-Kelly overlay ──────────────────────────────
        # If EdgeCalculator data is on the signal, use Kelly
        # fraction to scale position (conservative half-Kelly).
        edge_pwin = getattr(signal, 'edge_p_t1', 0)
        edge_rr = getattr(
            signal, 'risk_reward_ratio',
            getattr(signal, 'edge_rr', 0),
        )
        if edge_pwin > 0 and edge_rr > 0:
            kelly_f = (
                edge_pwin - (1.0 - edge_pwin) / edge_rr
            )
            kelly_f = max(kelly_f, 0.0)
            kelly_mult = min(kelly_f * 0.5, 1.0)
            kelly_mult = max(kelly_mult, 0.25) if kelly_mult > 0 else 0.25
            base_size *= kelly_mult
        else:
            # Confidence adjustment (legacy fallback)
            confidence_factor = 0.5 + (signal.confidence / 200)
            base_size *= confidence_factor

        # Volatility adjustment: reduce size in high vol
        vol_factor = 1.0
        if hasattr(signal, 'metadata') and signal.metadata:
            atr_pct = signal.metadata.get('atr_pct', 0.02)
            if atr_pct > 0.04:
                vol_factor = 0.6
            elif atr_pct > 0.03:
                vol_factor = 0.8

        position_size = base_size * vol_factor

        # Cap at max position size
        return min(position_size, self.max_position_pct)


class SignalEngine:
    """
    Main signal generation pipeline (v6 — Pro Desk).
    
    Orchestrates:
    0.  Data quality gates (reject stale/bad data)
    1.  Universe quality filter (hard gates)
    2.  Market-state NO TRADE check
    3.  Regime detection + scoreboard build
    4.  Delta tracking (what changed overnight)
    5.  Strategy execution
    6.  Edge checklist per signal
    7.  Score unification + calibration
    8.  Dedup + conflict resolution
    9.  Risk filtering + sizing
    10. Insight enrichment (playbook + trade briefs + risk bulletin)
    11. Signal v6 field population
    12. Signal output
    """
    
    def __init__(
        self, 
        strategies: Optional[List[BaseStrategy]] = None,
        regime_detector: Optional[RegimeDetector] = None,
        risk_model: Optional[RiskModel] = None,
        universe_filter: Optional[UniverseFilter] = None,
        insight_engine: Optional[InsightEngine] = None,
    ):
        self.strategies = strategies or get_all_strategies()
        self.regime_detector = regime_detector or RegimeDetector()
        self.risk_model = risk_model or RiskModel()
        self.universe_filter = universe_filter or UniverseFilter()
        self.insight_engine = insight_engine or InsightEngine()
        self.dedup = SignalDedup()
        self.score_unifier = ScoreUnifier()
        self.logger = logging.getLogger(__name__)
        self._last_market_state: Optional[Dict] = None
        self._last_insights: Optional[Dict] = None
        self._last_scoreboard = None
        self._last_delta_snapshot = None
        self._last_bullish_changes = None
        self._last_bearish_changes = None
        self._last_data_quality = None

        # Lazy-import v6 components (avoid circular)
        self._data_quality_gate = None
        self._delta_tracker = None
        self._scoreboard_builder = None
    
    def _get_data_quality_gate(self):
        if self._data_quality_gate is None:
            from src.engines.data_quality import DataQualityGate
            self._data_quality_gate = DataQualityGate()
        return self._data_quality_gate

    def _get_delta_tracker(self):
        if self._delta_tracker is None:
            from src.engines.delta_scoreboard import (
                DeltaTracker, ScoreboardBuilder,
            )
            self._delta_tracker = DeltaTracker()
            self._scoreboard_builder = ScoreboardBuilder()
        return self._delta_tracker, self._scoreboard_builder
    
    def generate_signals(
        self,
        universe: List[str],
        features: pd.DataFrame,
        market_data: Dict[str, Any],
        portfolio: Optional[Dict] = None,
        calendar_events: Optional[List[Dict]] = None,
        corporate_actions: Optional[List[Dict]] = None,
        yesterday_market_data: Optional[Dict[str, Any]] = None,
        week_ago_market_data: Optional[Dict[str, Any]] = None,
    ) -> List[Signal]:
        """
        Main signal generation pipeline (v6).
        
        Args:
            universe: List of tickers to consider
            features: Pre-computed features DataFrame
            market_data: Market-level data (VIX, breadth, etc.)
            portfolio: Current portfolio state
            calendar_events: Upcoming earnings/macro events
            corporate_actions: Recent splits/dividends/mergers
            yesterday_market_data: Yesterday's market data for delta tracking
            week_ago_market_data: Week-ago market data for delta tracking
        
        Returns:
            List of validated, sized, deduplicated signals with v6 fields
        """
        # ── -1. Data quality gates (v6) ─────────────────────────
        try:
            dq_gate = self._get_data_quality_gate()
            dq_passed, dq_reports = dq_gate.run_all_checks(market_data)
            self._last_data_quality = dq_reports
            if not dq_passed:
                critical = [r for r in dq_reports
                            if r.severity == "critical"
                            and not r.passed]
                reasons = "; ".join(
                    f"{r.feed_name}:{r.check_type}"
                    for r in critical
                )
                self.logger.warning(
                    f"🚫 Data quality gate FAILED: {reasons}"
                )
                return []
        except Exception as e:
            self.logger.warning(
                f"Data quality check error (continuing): {e}"
            )
            self._last_data_quality = None

        # ── 0. Universe quality filter ──────────────────────────
        clean_universe, rejections = self.universe_filter.filter(
            universe, features, calendar_events, corporate_actions
        )
        if not clean_universe:
            self.logger.warning("No tickers passed universe filter")
            return []
        
        # ── 1. Pre-flight NO TRADE check ───────────────────────
        can_trade, reason = self._preflight_check(market_data)
        self._last_market_state = {
            "ts": datetime.utcnow().isoformat(),
            "can_trade": can_trade,
            "no_trade_reason": reason if not can_trade else None,
            "vix": market_data.get("vix", 0),
            "spx_change_pct": market_data.get("spx_change_pct", 0),
        }
        if not can_trade:
            self.logger.warning(f"🚫 NO TRADE: {reason}")
            return []
        
        # ── 2. Detect regime ───────────────────────────────────
        regime = self.regime_detector.detect(market_data)
        
        if not regime.should_trade:
            self.logger.warning("Regime indicates no trading")
            self._last_market_state["no_trade_reason"] = (
                "regime_no_trade"
            )
            return []

        # ── 2b. Build delta snapshot + scoreboard (v6) ─────────
        try:
            dt, sb_builder = self._get_delta_tracker()
            self._last_delta_snapshot = dt.compute(
                today=market_data,
                yesterday=yesterday_market_data or {},
                week_ago=week_ago_market_data or {},
            )
            bull, bear = dt.classify_changes(
                self._last_delta_snapshot
            )
            self._last_bullish_changes = bull
            self._last_bearish_changes = bear
            self._last_scoreboard = sb_builder.build(
                regime, market_data
            )
            self.logger.info(
                f"Scoreboard: {self._last_scoreboard.regime_label} "
                f"| budget={self._last_scoreboard.risk_budget_pct}%"
            )
        except Exception as e:
            self.logger.warning(
                f"Delta/scoreboard build error (continuing): {e}"
            )
            self._last_delta_snapshot = None
            self._last_scoreboard = None
        
        # ── 3. Run active strategies ───────────────────────────
        raw_signals = []
        for strategy in self.strategies:
            if strategy.STRATEGY_ID in regime.active_strategies:
                try:
                    signals = strategy.generate_signals(
                        clean_universe, features, market_data
                    )
                    self.logger.info(
                        f"Strategy {strategy.STRATEGY_ID}: "
                        f"{len(signals)} signals"
                    )
                    raw_signals.extend(signals)
                except Exception as e:
                    self.logger.error(
                        f"Error in strategy {strategy.STRATEGY_ID}: {e}"
                    )
        
        self.logger.info(f"Total raw signals: {len(raw_signals)}")
        if not raw_signals:
            return []
        
        # ── 4. Edge checklist per signal ───────────────────────
        for sig in raw_signals:
            try:
                feat_row = self._get_feature_row(sig.ticker, features)
                checklist = EdgeChecklist.build(
                    sig, feat_row, regime, calendar_events
                )
                sig.feature_snapshot = sig.feature_snapshot or {}
                sig.feature_snapshot["edge_checklist"] = checklist
                sig.feature_snapshot["setup_tags"] = (
                    checklist["setup_tags"]
                )
                sig.feature_snapshot["regime_at_signal"] = (
                    checklist["regime_at_signal"]
                )
                sig.feature_snapshot["earnings_risk_days"] = (
                    checklist["earnings_risk_days"]
                )
                sig.feature_snapshot["dollar_volume_20d"] = (
                    checklist["dollar_volume_20d"]
                )
            except Exception as e:
                self.logger.warning(
                    f"Edge checklist error for {sig.ticker}: {e}"
                )
        
        # ── 5. Score unification ───────────────────────────────
        for sig in raw_signals:
            scores = self.score_unifier.unify(sig.confidence)
            sig.feature_snapshot = sig.feature_snapshot or {}
            sig.feature_snapshot["unified_scores"] = scores
            cal_wr = self.score_unifier.calibrated_win_rate(
                sig.strategy_id or "unknown",
                regime.trend.value,
                sig.confidence,
            )
            if cal_wr is not None:
                sig.feature_snapshot["calibrated_win_rate"] = (
                    round(cal_wr, 4)
                )
        
        # ── 6. Dedup + conflict resolution ─────────────────────
        deduped_signals, resolutions = (
            self.dedup.resolve_conflicts(raw_signals)
        )
        if resolutions:
            self.logger.info(
                f"Conflict resolutions: {len(resolutions)}"
            )
            for r in resolutions:
                self.logger.info(
                    f"  {r['ticker']}: kept {r['kept']}, "
                    f"dropped {r['dropped']}"
                )
        
        for sig in deduped_signals:
            sig.feature_snapshot = sig.feature_snapshot or {}
            sig.feature_snapshot["dedupe_key"] = (
                self.dedup.dedupe_key(sig)
            )
        
        # ── 7. Risk model filter + sizing ──────────────────────
        filtered_signals = self.risk_model.filter_and_size(
            deduped_signals, portfolio
        )
        
        self.logger.info(
            f"Filtered signals: {len(filtered_signals)}"
        )
        
        # ── 8. Sort + limit ────────────────────────────────────
        filtered_signals = sorted(
            filtered_signals,
            key=lambda s: s.confidence,
            reverse=True,
        )
        max_signals = 10
        if len(filtered_signals) > max_signals:
            filtered_signals = filtered_signals[:max_signals]
            self.logger.info(f"Limited to top {max_signals} signals")
        
        # ── 9. Insight enrichment (v5) ─────────────────────────
        try:
            features_by_ticker = {}
            for sig in filtered_signals:
                features_by_ticker[sig.ticker] = (
                    self._get_feature_row(sig.ticker, features)
                )
            self._last_insights = self.insight_engine.generate_insights(
                signals=filtered_signals,
                regime=regime,
                market_data=market_data,
                features_by_ticker=features_by_ticker,
                portfolio=portfolio,
                calendar_events=calendar_events,
                yesterday_regime=(
                    self._last_market_state.get("yesterday_regime")
                    if self._last_market_state else None
                ),
            )
            trade_briefs = self._last_insights.get(
                "trade_briefs", []
            )
            for sig, brief in zip(filtered_signals, trade_briefs):
                sig.feature_snapshot = sig.feature_snapshot or {}
                sig.feature_snapshot["edge_model"] = (
                    brief.edge_model.model_dump()
                    if brief.edge_model else {}
                )
                sig.feature_snapshot["execution_plan"] = (
                    brief.execution_plan.model_dump()
                    if brief.execution_plan else {}
                )
                sig.feature_snapshot["risk_plan"] = (
                    brief.risk_plan.model_dump()
                    if brief.risk_plan else {}
                )
                sig.feature_snapshot["trade_brief"] = (
                    brief.model_dump()
                )
        except Exception as e:
            self.logger.error(
                f"InsightEngine enrichment failed: {e}",
                exc_info=True,
            )
            self._last_insights = None
            trade_briefs = []

        # ── 10. Populate Signal v6 fields (pro desk) ──────────
        self._populate_v6_fields(
            filtered_signals, trade_briefs, regime,
            features, calendar_events, portfolio,
        )
        
        return filtered_signals
    
    def _populate_v6_fields(
        self,
        signals: List[Signal],
        trade_briefs: List[Any],
        regime: MarketRegime,
        features: pd.DataFrame,
        calendar_events: Optional[List[Dict]],
        portfolio: Optional[Dict],
    ) -> None:
        """
        Populate Signal v6 fields from edge model, checklist,
        regime scoreboard, and delta snapshot.
        """
        brief_map = {}
        for i, tb in enumerate(trade_briefs):
            if i < len(signals):
                brief_map[signals[i].ticker] = tb

        for sig in signals:
            try:
                checklist = (
                    (sig.feature_snapshot or {})
                    .get("edge_checklist", {})
                )
                tb = brief_map.get(sig.ticker)
                edge = tb.edge_model if tb else None
                rp = tb.risk_plan if tb else None

                # setup_grade: A/B/C/D based on tag count + regime
                tag_count = len(checklist.get("setup_tags", []))
                regime_ok = checklist.get(
                    "regime_at_signal", {}
                ).get("risk", "") != "RISK_OFF"
                if tag_count >= 5 and regime_ok:
                    sig.setup_grade = "A"
                elif tag_count >= 3 and regime_ok:
                    sig.setup_grade = "B"
                elif tag_count >= 2:
                    sig.setup_grade = "C"
                else:
                    sig.setup_grade = "D"

                # edge_type
                strat = sig.strategy_id or ""
                if "momentum" in strat or "trend" in strat:
                    sig.edge_type = "trend"
                elif "mean_reversion" in strat:
                    sig.edge_type = "reversion"
                elif "vcp" in strat:
                    sig.edge_type = "pattern"
                elif "swing" in strat:
                    sig.edge_type = "swing"
                else:
                    sig.edge_type = "mixed"

                # time_stop_days from edge model
                if edge:
                    sig.time_stop_days = (
                        edge.expected_holding_days
                    )
                else:
                    sig.time_stop_days = 5

                # event_risk
                earn_days = checklist.get("earnings_risk_days")
                if earn_days is not None and earn_days <= 5:
                    sig.event_risk = (
                        f"Earnings in {earn_days}d"
                    )
                else:
                    sig.event_risk = None

                # scenario_plan from scoreboard
                if self._last_scoreboard and self._last_scoreboard.scenarios:
                    sc = self._last_scoreboard.scenarios
                    sig.scenario_plan = {
                        "base_case": sc.base_case,
                        "base_probability": sc.base_probability,
                        "bull_case": sc.bull_trigger,
                        "bear_case": sc.bear_trigger,
                    }

                # portfolio_fit
                if portfolio:
                    existing = set(
                        portfolio.get("positions", {}).keys()
                    )
                    sector = (sig.metadata or {}).get("sector", "")
                    same_sector = sum(
                        1 for p in existing
                        if portfolio.get("positions", {})
                        .get(p, {}).get("sector") == sector
                    ) if sector else 0
                    if same_sector >= 3:
                        sig.portfolio_fit = "over_concentrated"
                    elif same_sector >= 2:
                        sig.portfolio_fit = "sector_heavy"
                    else:
                        sig.portfolio_fit = "fits"
                else:
                    sig.portfolio_fit = "no_portfolio_data"

                # evidence list
                evidence = []
                for tag in checklist.get("setup_tags", [])[:5]:
                    evidence.append(f"Setup: {tag}")
                if edge:
                    evidence.append(
                        f"P(T1)={edge.p_t1*100:.0f}%, "
                        f"EV={edge.expected_return_pct:+.1f}%"
                    )
                if checklist.get("rr_ratio"):
                    evidence.append(
                        f"R:R={checklist['rr_ratio']:.1f}"
                    )
                sig.evidence = evidence

                # expected_value
                if edge:
                    sig.expected_value = (
                        edge.expected_return_pct
                    )

                # why_now — compose from regime + catalyst
                parts = []
                if self._last_scoreboard:
                    parts.append(
                        f"Regime: {self._last_scoreboard.regime_label}"
                    )
                if tb and tb.catalyst:
                    parts.append(f"Catalyst: {tb.catalyst}")
                if checklist.get("relative_volume", 1) >= 1.5:
                    parts.append(
                        f"Volume {checklist['relative_volume']:.1f}x"
                    )
                sig.why_now = " | ".join(parts) if parts else None

                # approval_status will be set by GPT validator later
                # default to conditional until validated
                if not sig.approval_status:
                    sig.approval_status = "conditional"

            except Exception as e:
                self.logger.warning(
                    f"v6 field population error for "
                    f"{sig.ticker}: {e}"
                )
    
    def _get_feature_row(self, ticker: str, features: pd.DataFrame) -> Dict:
        """Extract latest feature row for a ticker."""
        try:
            if "ticker" in features.index.names:
                tf = features.xs(ticker, level="ticker")
            elif "ticker" in features.columns:
                tf = features[features["ticker"] == ticker]
            else:
                return {}
            if tf.empty:
                return {}
            return tf.iloc[-1].to_dict() if hasattr(tf.iloc[-1], "to_dict") else {}
        except Exception:
            return {}
    
    def get_market_state(self) -> Optional[Dict]:
        """Return the latest market state for display / DB storage."""
        return self._last_market_state
    
    def get_insights(self) -> Optional[Dict]:
        """Return the latest insights (playbook, trade briefs, risk bulletin)."""
        return self._last_insights
    
    def get_playbook(self) -> Optional[MarketPlaybook]:
        """Convenience: return just the playbook."""
        if self._last_insights:
            return self._last_insights.get("playbook")
        return None
    
    def get_trade_briefs(self) -> List[TradeBrief]:
        """Convenience: return trade briefs."""
        if self._last_insights:
            return self._last_insights.get("trade_briefs", [])
        return []
    
    def get_risk_bulletin(self) -> Optional[RiskBulletin]:
        """Convenience: return risk bulletin."""
        if self._last_insights:
            return self._last_insights.get("risk_bulletin")
        return None

    # ── v6 getters ──────────────────────────────────────────────

    def get_scoreboard(self):
        """Return the last computed RegimeScoreboard."""
        return self._last_scoreboard

    def get_delta_snapshot(self):
        """Return the last computed DeltaSnapshot."""
        return self._last_delta_snapshot

    def get_delta_changes(self):
        """Return (bullish_changes, bearish_changes) ChangeItem lists."""
        return (
            self._last_bullish_changes or [],
            self._last_bearish_changes or [],
        )

    def get_data_quality(self):
        """Return the last data quality report list."""
        return self._last_data_quality
    
    def _preflight_check(self, market_data: Dict) -> tuple[bool, str]:
        """
        Pre-flight checks before signal generation.
        
        Ensures market conditions are suitable for trading.
        Returns (can_trade, reason) tuple.
        """
        vix = market_data.get('vix', 20)
        spx_change = market_data.get('spx_change_pct', 0)
        is_fomc = market_data.get('is_fomc_day', False)
        is_quad_witching = market_data.get('is_quad_witching', False)
        data_fresh = market_data.get('data_fresh', True)
        data_staleness_seconds = market_data.get('data_staleness_seconds', 0)
        
        # NO TRADE conditions with specific reason codes
        checks = [
            (vix < 40, "NO_TRADE_vix_crisis", f"VIX too high ({vix:.1f}) - crisis mode"),
            (spx_change > -3.0, "NO_TRADE_circuit_breaker", f"Market down {abs(spx_change):.1f}% - circuit breaker risk"),
            (not is_fomc, "NO_TRADE_fomc_day", "FOMC day - high volatility expected"),
            (not is_quad_witching, "NO_TRADE_quad_witching", "Quad witching - unusual volume/volatility"),
            (data_fresh, "NO_TRADE_stale_data", "Market data too stale"),
            (data_staleness_seconds < 900, "NO_TRADE_data_15min", f"Data staleness {data_staleness_seconds}s > 15min threshold"),
        ]
        
        for condition, code, reason in checks:
            if not condition:
                # Track rejection reasons
                self._track_rejection(code, reason)
                return False, f"{code}: {reason}"
        
        return True, "All checks passed"
    
    def _track_rejection(self, code: str, reason: str):
        """Track rejection reasons for observability."""
        if not hasattr(self, '_rejection_counts'):
            self._rejection_counts = {}
        
        self._rejection_counts[code] = self._rejection_counts.get(code, 0) + 1
        self.logger.info(f"Signal rejected: {code} - {reason}")
    
    def get_rejection_stats(self) -> Dict[str, int]:
        """Get rejection reason statistics."""
        return getattr(self, '_rejection_counts', {})
    
    async def generate_signals_async(
        self,
        universe: List[str],
        features: pd.DataFrame,
        market_data: Dict[str, Any],
        portfolio: Optional[Dict] = None
    ) -> List[Signal]:
        """Async version of signal generation."""
        # Run in thread pool to not block
        loop = asyncio.get_event_loop()
        return await loop.run_in_executor(
            None,
            self.generate_signals,
            universe, features, market_data, portfolio
        )


class SignalValidator:
    """
    Additional signal validation layer.
    
    Performs sanity checks on generated signals before they're sent out.
    """
    
    def __init__(self):
        self.logger = logging.getLogger(__name__)
    
    def validate_signal(self, signal: Signal) -> tuple[bool, str]:
        """
        Validate a single signal.
        
        Returns:
            (is_valid, reason)
        """
        # Basic price checks
        if signal.entry_price <= 0:
            return False, "Invalid entry price"
        
        stop_loss = signal.invalidation.stop_price if hasattr(signal, 'invalidation') else getattr(signal, 'stop_loss', 0)
        take_profit = signal.targets[0].price if hasattr(signal, 'targets') and signal.targets else getattr(signal, 'take_profit', 0)
        
        if stop_loss <= 0:
            return False, "Invalid stop loss"
        
        if take_profit <= 0:
            return False, "Invalid take profit"
        
        # Get direction as string
        direction = signal.direction.value if hasattr(signal.direction, 'value') else str(signal.direction)
        
        # Direction consistency
        if direction == "LONG":
            if stop_loss >= signal.entry_price:
                return False, "Stop loss must be below entry for long"
            if take_profit <= signal.entry_price:
                return False, "Take profit must be above entry for long"
        elif direction == "SHORT":
            if stop_loss <= signal.entry_price:
                return False, "Stop loss must be above entry for short"
            if take_profit >= signal.entry_price:
                return False, "Take profit must be below entry for short"
        
        # Risk/Reward ratio check
        risk = abs(signal.entry_price - stop_loss)
        reward = abs(take_profit - signal.entry_price)
        
        if risk > 0:
            rr_ratio = reward / risk
            if rr_ratio < 1.0:
                return False, f"R:R ratio too low ({rr_ratio:.2f})"
        
        # Confidence check
        confidence = signal.confidence
        if confidence < 0 or confidence > 100:
            return False, f"Invalid confidence: {confidence}"
        
        return True, "Valid"
    
    def validate_signals(self, signals: List[Signal]) -> List[Signal]:
        """Validate a list of signals, returning only valid ones."""
        valid_signals = []
        
        for signal in signals:
            is_valid, reason = self.validate_signal(signal)
            if is_valid:
                valid_signals.append(signal)
            else:
                self.logger.warning(f"Signal {signal.ticker} invalid: {reason}")
        
        return valid_signals
