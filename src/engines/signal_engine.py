"""
TradingAI Bot - Signal Engine
Main orchestrator for signal generation pipeline.
"""
import asyncio
from datetime import datetime, date
from typing import List, Dict, Optional, Any
import logging
import pandas as pd

from src.core.models import Signal, MarketRegime, VolatilityRegime, TrendRegime, RiskRegime
from src.core.config import get_trading_config
from src.strategies import get_strategy, get_all_strategies, BaseStrategy


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
        active_strategies = self._get_active_strategies(vol_regime, trend_regime, risk_regime)
        
        self.logger.info(
            f"Regime detected: vol={vol_regime.value}, trend={trend_regime.value}, "
            f"risk={risk_regime.value}, strategies={active_strategies}"
        )
        
        return MarketRegime(
            timestamp=datetime.utcnow(),
            volatility=vol_regime,
            trend=trend_regime,
            risk=risk_regime,
            active_strategies=active_strategies
        )
    
    def _get_active_strategies(
        self, 
        vol: VolatilityRegime, 
        trend: TrendRegime, 
        risk: RiskRegime
    ) -> List[str]:
        """Map regime to active strategies."""
        
        # NO TRADE conditions
        if vol == VolatilityRegime.CRISIS:
            return []
        
        if trend == TrendRegime.STRONG_DOWNTREND and risk == RiskRegime.RISK_OFF:
            return []
        
        active = []
        
        # Momentum & trend strategies work in uptrends with normal volatility
        if trend in [TrendRegime.UPTREND, TrendRegime.STRONG_UPTREND]:
            if vol != VolatilityRegime.HIGH_VOL:
                active.append("momentum_breakout")
                active.append("short_term_trend_following")  # Pullback buying in uptrends
                active.append("trend_following")  # Turtle-style trend following
                active.append("momentum_rotation")  # Sector rotation
        
        # VCP works in low vol (tight base / squeeze setup)
        if vol in [VolatilityRegime.LOW_VOL, VolatilityRegime.NORMAL]:
            if trend in [TrendRegime.UPTREND, TrendRegime.STRONG_UPTREND, TrendRegime.NEUTRAL]:
                active.append("vcp")
        
        # Mean reversion works in normal/low vol environments
        if vol in [VolatilityRegime.NORMAL, VolatilityRegime.LOW_VOL]:
            if trend != TrendRegime.STRONG_DOWNTREND:
                active.append("mean_reversion")
                active.append("short_term_mean_reversion")
        
        # Classic swing works in neutral/uptrend markets
        if trend in [TrendRegime.NEUTRAL, TrendRegime.UPTREND, TrendRegime.STRONG_UPTREND]:
            active.append("classic_swing")
        
        return active


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
        
        # Filter out existing positions
        existing_positions = set(portfolio.get('positions', {}).keys())
        signals = [s for s in signals if s.ticker not in existing_positions]
        
        # Calculate position sizes
        for signal in signals:
            signal.position_size_pct = self._calculate_position_size(signal, portfolio)
        
        # Filter out signals with 0 position size
        signals = [s for s in signals if (s.position_size_pct or 0) > 0]
        
        self.logger.info(f"Risk model: {len(signals)} signals passed filters")
        
        return signals
    
    def _calculate_position_size(self, signal: Signal, portfolio: Dict) -> float:
        """Calculate position size based on risk parameters."""
        equity = portfolio.get('equity', 100000)
        risk_per_trade = portfolio.get('risk_per_trade', 0.01)  # Configurable, default 1%
        
        # Risk-based sizing
        if signal.invalidation.stop_price and signal.entry_price:
            stop_distance = abs(signal.entry_price - signal.invalidation.stop_price)
            stop_pct = stop_distance / signal.entry_price if signal.entry_price > 0 else 0.05
            
            if stop_pct > 0:
                base_size = risk_per_trade / stop_pct
            else:
                base_size = self.max_position_pct * 0.5  # Conservative fallback
        else:
            base_size = self.max_position_pct * 0.5  # Conservative fallback
        
        # Confidence adjustment (scale 0.5-1.0 based on confidence)
        confidence_factor = 0.5 + (signal.confidence / 200)  # 50 conf → 0.75x, 80 conf → 0.90x
        
        # Volatility adjustment: reduce size in high vol
        vol_factor = 1.0
        if hasattr(signal, 'metadata') and signal.metadata:
            atr_pct = signal.metadata.get('atr_pct', 0.02)
            if atr_pct > 0.04:  # High volatility stock
                vol_factor = 0.6
            elif atr_pct > 0.03:
                vol_factor = 0.8
        
        # Calculate final size
        position_size = base_size * confidence_factor * vol_factor
        
        # Cap at max position size
        return min(position_size, self.max_position_pct)


class SignalEngine:
    """
    Main signal generation pipeline.
    
    Orchestrates:
    1. Regime detection
    2. Strategy execution
    3. Risk filtering
    4. Signal output
    """
    
    def __init__(
        self, 
        strategies: Optional[List[BaseStrategy]] = None,
        regime_detector: Optional[RegimeDetector] = None,
        risk_model: Optional[RiskModel] = None
    ):
        self.strategies = strategies or get_all_strategies()
        self.regime_detector = regime_detector or RegimeDetector()
        self.risk_model = risk_model or RiskModel()
        self.logger = logging.getLogger(__name__)
    
    def generate_signals(
        self,
        universe: List[str],
        features: pd.DataFrame,
        market_data: Dict[str, Any],
        portfolio: Optional[Dict] = None
    ) -> List[Signal]:
        """
        Main signal generation pipeline.
        
        Args:
            universe: List of tickers to consider
            features: Pre-computed features DataFrame
            market_data: Market-level data (VIX, breadth, etc.)
            portfolio: Current portfolio state
        
        Returns:
            List of validated and sized signals
        """
        # 1. Pre-flight checks
        can_trade, reason = self._preflight_check(market_data)
        if not can_trade:
            self.logger.warning(f"Signal generation skipped: {reason}")
            return []
        
        # 2. Detect regime
        regime = self.regime_detector.detect(market_data)
        
        if not regime.should_trade:
            self.logger.warning("Regime indicates no trading")
            return []
        
        # 3. Run active strategies
        raw_signals = []
        for strategy in self.strategies:
            if strategy.STRATEGY_ID in regime.active_strategies:
                try:
                    signals = strategy.generate_signals(universe, features, market_data)
                    self.logger.info(f"Strategy {strategy.STRATEGY_ID}: {len(signals)} signals")
                    raw_signals.extend(signals)
                except Exception as e:
                    self.logger.error(f"Error in strategy {strategy.STRATEGY_ID}: {e}")
        
        self.logger.info(f"Total raw signals: {len(raw_signals)}")
        
        # 4. Apply risk model
        filtered_signals = self.risk_model.filter_and_size(raw_signals, portfolio)
        
        self.logger.info(f"Filtered signals: {len(filtered_signals)}")
        
        # 5. Sort by confidence and apply final limits
        filtered_signals = sorted(filtered_signals, key=lambda s: s.confidence, reverse=True)
        
        # Limit to top signals per session
        max_signals = 10
        if len(filtered_signals) > max_signals:
            filtered_signals = filtered_signals[:max_signals]
            self.logger.info(f"Limited to top {max_signals} signals")
        
        return filtered_signals
    
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
