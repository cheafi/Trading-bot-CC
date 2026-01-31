"""
TradingAI Bot - Technical Indicator Library

Comprehensive library of technical indicators for strategy development.
Inspired by freqtrade's indicator utilities and TA-Lib patterns.

Provides:
- Trend indicators (SMA, EMA, MACD, etc.)
- Momentum indicators (RSI, Stochastic, CCI, etc.)
- Volatility indicators (ATR, Bollinger Bands, Keltner, etc.)
- Volume indicators (OBV, VWAP, Money Flow, etc.)
- Pattern recognition (VCP, Cup & Handle, etc.)
- Alpha factors (momentum, value, quality, etc.)
"""
import numpy as np
import pandas as pd
from typing import Optional, Tuple, Dict
import logging

logger = logging.getLogger(__name__)


class IndicatorLibrary:
    """
    Technical indicator library with optimized calculations.
    
    All methods are static and work with pandas Series/DataFrame.
    """
    
    # ========== Trend Indicators ==========
    
    @staticmethod
    def sma(series: pd.Series, period: int = 20) -> pd.Series:
        """Simple Moving Average."""
        return series.rolling(window=period, min_periods=1).mean()
    
    @staticmethod
    def ema(series: pd.Series, period: int = 20) -> pd.Series:
        """Exponential Moving Average."""
        return series.ewm(span=period, adjust=False).mean()
    
    @staticmethod
    def wma(series: pd.Series, period: int = 20) -> pd.Series:
        """Weighted Moving Average."""
        weights = np.arange(1, period + 1)
        return series.rolling(period).apply(
            lambda x: np.dot(x, weights) / weights.sum(), 
            raw=True
        )
    
    @staticmethod
    def macd(
        series: pd.Series, 
        fast: int = 12, 
        slow: int = 26, 
        signal: int = 9
    ) -> Tuple[pd.Series, pd.Series, pd.Series]:
        """
        MACD (Moving Average Convergence Divergence).
        
        Returns:
            (macd_line, signal_line, histogram)
        """
        ema_fast = series.ewm(span=fast, adjust=False).mean()
        ema_slow = series.ewm(span=slow, adjust=False).mean()
        macd_line = ema_fast - ema_slow
        signal_line = macd_line.ewm(span=signal, adjust=False).mean()
        histogram = macd_line - signal_line
        return macd_line, signal_line, histogram
    
    @staticmethod
    def supertrend(
        df: pd.DataFrame, 
        period: int = 10, 
        multiplier: float = 3.0
    ) -> Tuple[pd.Series, pd.Series]:
        """
        Supertrend indicator.
        
        Returns:
            (supertrend_line, trend_direction)
            trend_direction: 1 = bullish, -1 = bearish
        """
        hl2 = (df['high'] + df['low']) / 2
        atr = IndicatorLibrary.atr(df, period)
        
        upper_band = hl2 + (multiplier * atr)
        lower_band = hl2 - (multiplier * atr)
        
        supertrend = pd.Series(index=df.index, dtype=float)
        direction = pd.Series(index=df.index, dtype=int)
        
        for i in range(1, len(df)):
            if df['close'].iloc[i] > upper_band.iloc[i-1]:
                supertrend.iloc[i] = lower_band.iloc[i]
                direction.iloc[i] = 1
            elif df['close'].iloc[i] < lower_band.iloc[i-1]:
                supertrend.iloc[i] = upper_band.iloc[i]
                direction.iloc[i] = -1
            else:
                supertrend.iloc[i] = supertrend.iloc[i-1]
                direction.iloc[i] = direction.iloc[i-1]
        
        return supertrend, direction
    
    # ========== Momentum Indicators ==========
    
    @staticmethod
    def rsi(series: pd.Series, period: int = 14) -> pd.Series:
        """Relative Strength Index."""
        delta = series.diff()
        gain = (delta.where(delta > 0, 0)).rolling(window=period).mean()
        loss = (-delta.where(delta < 0, 0)).rolling(window=period).mean()
        rs = gain / loss.replace(0, np.inf)
        return 100 - (100 / (1 + rs))
    
    @staticmethod
    def stochastic(
        df: pd.DataFrame, 
        k_period: int = 14, 
        d_period: int = 3
    ) -> Tuple[pd.Series, pd.Series]:
        """
        Stochastic Oscillator.
        
        Returns:
            (stoch_k, stoch_d)
        """
        lowest_low = df['low'].rolling(window=k_period).min()
        highest_high = df['high'].rolling(window=k_period).max()
        
        stoch_k = 100 * (df['close'] - lowest_low) / (highest_high - lowest_low)
        stoch_d = stoch_k.rolling(window=d_period).mean()
        
        return stoch_k, stoch_d
    
    @staticmethod
    def cci(df: pd.DataFrame, period: int = 20) -> pd.Series:
        """Commodity Channel Index."""
        typical_price = (df['high'] + df['low'] + df['close']) / 3
        sma_tp = typical_price.rolling(window=period).mean()
        mean_dev = typical_price.rolling(window=period).apply(
            lambda x: np.abs(x - x.mean()).mean()
        )
        return (typical_price - sma_tp) / (0.015 * mean_dev)
    
    @staticmethod
    def williams_r(df: pd.DataFrame, period: int = 14) -> pd.Series:
        """Williams %R."""
        highest_high = df['high'].rolling(window=period).max()
        lowest_low = df['low'].rolling(window=period).min()
        return -100 * (highest_high - df['close']) / (highest_high - lowest_low)
    
    @staticmethod
    def mfi(df: pd.DataFrame, period: int = 14) -> pd.Series:
        """Money Flow Index."""
        typical_price = (df['high'] + df['low'] + df['close']) / 3
        raw_money_flow = typical_price * df['volume']
        
        positive_flow = pd.Series(0.0, index=df.index)
        negative_flow = pd.Series(0.0, index=df.index)
        
        tp_diff = typical_price.diff()
        positive_flow = raw_money_flow.where(tp_diff > 0, 0)
        negative_flow = raw_money_flow.where(tp_diff < 0, 0)
        
        positive_sum = positive_flow.rolling(window=period).sum()
        negative_sum = negative_flow.rolling(window=period).sum()
        
        money_ratio = positive_sum / negative_sum.replace(0, np.inf)
        return 100 - (100 / (1 + money_ratio))
    
    @staticmethod
    def roc(series: pd.Series, period: int = 10) -> pd.Series:
        """Rate of Change (Momentum)."""
        return ((series - series.shift(period)) / series.shift(period)) * 100
    
    # ========== Volatility Indicators ==========
    
    @staticmethod
    def atr(df: pd.DataFrame, period: int = 14) -> pd.Series:
        """Average True Range."""
        high_low = df['high'] - df['low']
        high_close = (df['high'] - df['close'].shift()).abs()
        low_close = (df['low'] - df['close'].shift()).abs()
        true_range = pd.concat([high_low, high_close, low_close], axis=1).max(axis=1)
        return true_range.rolling(window=period).mean()
    
    @staticmethod
    def bollinger_bands(
        series: pd.Series, 
        period: int = 20, 
        std_dev: float = 2.0
    ) -> Tuple[pd.Series, pd.Series, pd.Series]:
        """
        Bollinger Bands.
        
        Returns:
            (upper_band, middle_band, lower_band)
        """
        middle = series.rolling(window=period).mean()
        std = series.rolling(window=period).std()
        upper = middle + (std_dev * std)
        lower = middle - (std_dev * std)
        return upper, middle, lower
    
    @staticmethod
    def bollinger_bandwidth(series: pd.Series, period: int = 20) -> pd.Series:
        """Bollinger Bandwidth (measures volatility squeeze)."""
        upper, middle, lower = IndicatorLibrary.bollinger_bands(series, period)
        return ((upper - lower) / middle) * 100
    
    @staticmethod
    def keltner_channels(
        df: pd.DataFrame, 
        period: int = 20, 
        multiplier: float = 2.0
    ) -> Tuple[pd.Series, pd.Series, pd.Series]:
        """
        Keltner Channels.
        
        Returns:
            (upper_band, middle_band, lower_band)
        """
        typical_price = (df['high'] + df['low'] + df['close']) / 3
        middle = typical_price.ewm(span=period, adjust=False).mean()
        atr = IndicatorLibrary.atr(df, period)
        upper = middle + (multiplier * atr)
        lower = middle - (multiplier * atr)
        return upper, middle, lower
    
    @staticmethod
    def volatility_contraction_ratio(
        df: pd.DataFrame, 
        short_period: int = 10, 
        long_period: int = 50
    ) -> pd.Series:
        """
        Volatility Contraction Ratio for VCP pattern detection.
        
        Lower values indicate tighter consolidation (good for breakouts).
        """
        atr_short = IndicatorLibrary.atr(df, short_period)
        atr_long = IndicatorLibrary.atr(df, long_period)
        return atr_short / atr_long.replace(0, np.inf)
    
    @staticmethod
    def historical_volatility(series: pd.Series, period: int = 20) -> pd.Series:
        """Historical Volatility (annualized)."""
        log_returns = np.log(series / series.shift(1))
        return log_returns.rolling(window=period).std() * np.sqrt(252)
    
    # ========== Volume Indicators ==========
    
    @staticmethod
    def obv(df: pd.DataFrame) -> pd.Series:
        """On-Balance Volume."""
        obv = pd.Series(0.0, index=df.index)
        obv.iloc[0] = df['volume'].iloc[0]
        
        for i in range(1, len(df)):
            if df['close'].iloc[i] > df['close'].iloc[i-1]:
                obv.iloc[i] = obv.iloc[i-1] + df['volume'].iloc[i]
            elif df['close'].iloc[i] < df['close'].iloc[i-1]:
                obv.iloc[i] = obv.iloc[i-1] - df['volume'].iloc[i]
            else:
                obv.iloc[i] = obv.iloc[i-1]
        
        return obv
    
    @staticmethod
    def vwap(df: pd.DataFrame) -> pd.Series:
        """Volume Weighted Average Price."""
        typical_price = (df['high'] + df['low'] + df['close']) / 3
        return (typical_price * df['volume']).cumsum() / df['volume'].cumsum()
    
    @staticmethod
    def volume_sma(df: pd.DataFrame, period: int = 20) -> pd.Series:
        """Volume Simple Moving Average."""
        return df['volume'].rolling(window=period).mean()
    
    @staticmethod
    def relative_volume(df: pd.DataFrame, period: int = 20) -> pd.Series:
        """Relative Volume (current vs average)."""
        avg_volume = df['volume'].rolling(window=period).mean()
        return df['volume'] / avg_volume.replace(0, np.inf)
    
    @staticmethod
    def volume_profile(df: pd.DataFrame, num_bins: int = 20) -> pd.DataFrame:
        """
        Volume Profile analysis.
        
        Returns DataFrame with price levels and volume at each level.
        """
        price_range = df['close'].max() - df['close'].min()
        bin_size = price_range / num_bins
        
        bins = np.arange(df['close'].min(), df['close'].max() + bin_size, bin_size)
        df_temp = df.copy()
        df_temp['price_bin'] = pd.cut(df_temp['close'], bins=bins)
        
        volume_profile = df_temp.groupby('price_bin')['volume'].sum()
        return volume_profile.reset_index()
    
    @staticmethod
    def accumulation_distribution(df: pd.DataFrame) -> pd.Series:
        """Accumulation/Distribution Line."""
        clv = ((df['close'] - df['low']) - (df['high'] - df['close'])) / (df['high'] - df['low'])
        clv = clv.replace([np.inf, -np.inf], 0).fillna(0)
        ad = (clv * df['volume']).cumsum()
        return ad
    
    # ========== Pattern Recognition ==========
    
    @staticmethod
    def is_vcp_setup(
        df: pd.DataFrame,
        contractions: int = 3,
        min_base_length: int = 20,
        max_base_length: int = 65,
        max_depth_pct: float = 0.30
    ) -> Tuple[bool, Dict]:
        """
        Detect VCP (Volatility Contraction Pattern) - Mark Minervini style.
        
        VCP Characteristics:
        1. Stock is in an uptrend (above rising 50-day and 200-day MA)
        2. Price corrects in a series of tighter contractions
        3. Each successive contraction is shallower
        4. Volume dries up during consolidation
        5. Pivot point forms at the end of the pattern
        
        Args:
            df: OHLCV DataFrame (minimum 65 days)
            contractions: Minimum number of volatility contractions
            min_base_length: Minimum days in the base
            max_base_length: Maximum days in the base
            max_depth_pct: Maximum correction depth from high
        
        Returns:
            (is_vcp, details_dict)
        """
        if len(df) < max_base_length:
            return False, {'reason': 'Insufficient data'}
        
        # Get recent data for analysis
        recent = df.tail(max_base_length).copy()
        
        # 1. Check uptrend condition
        sma_50 = IndicatorLibrary.sma(df['close'], 50)
        sma_200 = IndicatorLibrary.sma(df['close'], 200)
        
        if sma_50.iloc[-1] < sma_200.iloc[-1]:
            return False, {'reason': 'Not in uptrend (50MA < 200MA)'}
        
        current_price = recent['close'].iloc[-1]
        if current_price < sma_50.iloc[-1]:
            return False, {'reason': 'Price below 50MA'}
        
        # 2. Find the highest high in the base
        base_high = recent['high'].max()
        base_high_idx = recent['high'].idxmax()
        
        # 3. Calculate correction depth
        base_low = recent['low'].min()
        correction_depth = (base_high - base_low) / base_high
        
        if correction_depth > max_depth_pct:
            return False, {
                'reason': f'Correction too deep ({correction_depth:.1%} > {max_depth_pct:.1%})'
            }
        
        # 4. Detect contractions (volatility getting tighter)
        window_size = max_base_length // contractions
        contraction_depths = []
        
        for i in range(contractions):
            start_idx = i * window_size
            end_idx = min((i + 1) * window_size, len(recent))
            segment = recent.iloc[start_idx:end_idx]
            
            if len(segment) > 0:
                segment_range = (segment['high'].max() - segment['low'].min()) / segment['high'].max()
                contraction_depths.append(segment_range)
        
        # Check if contractions are getting tighter
        if len(contraction_depths) >= 2:
            contracting = all(
                contraction_depths[i] >= contraction_depths[i+1] * 0.8
                for i in range(len(contraction_depths) - 1)
            )
        else:
            contracting = False
        
        if not contracting:
            return False, {'reason': 'Contractions not getting tighter'}
        
        # 5. Check volume dry-up
        recent_vol = recent['volume'].tail(10).mean()
        base_vol = recent['volume'].head(20).mean()
        volume_contraction = recent_vol / base_vol if base_vol > 0 else 1
        
        volume_drying = volume_contraction < 0.7
        
        # 6. Check for pivot point (recent high near base high)
        recent_high = recent['high'].tail(5).max()
        pivot_forming = (base_high - recent_high) / base_high < 0.03  # Within 3% of high
        
        # 7. Calculate VCP score
        vcp_score = 0
        vcp_score += 25 if contracting else 0
        vcp_score += 25 if volume_drying else 0
        vcp_score += 25 if pivot_forming else 0
        vcp_score += 25 if correction_depth < max_depth_pct * 0.7 else 0
        
        is_vcp = vcp_score >= 75
        
        details = {
            'is_vcp': is_vcp,
            'vcp_score': vcp_score,
            'base_high': base_high,
            'base_low': base_low,
            'correction_depth': correction_depth,
            'contraction_depths': contraction_depths,
            'volume_contraction': volume_contraction,
            'pivot_forming': pivot_forming,
            'entry_price': base_high * 1.01,  # Buy on breakout above high
            'stop_loss': base_low * 0.97,     # Stop below base low
            'target_price': base_high * (1 + correction_depth),  # Measured move
        }
        
        return is_vcp, details
    
    @staticmethod
    def is_cup_and_handle(
        df: pd.DataFrame,
        cup_min_length: int = 30,
        cup_max_length: int = 120,
        handle_max_depth: float = 0.15
    ) -> Tuple[bool, Dict]:
        """
        Detect Cup and Handle pattern.
        
        Returns:
            (is_cup_handle, details_dict)
        """
        if len(df) < cup_min_length:
            return False, {'reason': 'Insufficient data'}
        
        # Find potential cup
        recent = df.tail(cup_max_length).copy()
        
        # Left rim (high before cup)
        left_rim_idx = recent['high'].iloc[:len(recent)//3].idxmax()
        left_rim = recent.loc[left_rim_idx, 'high']
        
        # Cup bottom
        middle_start = len(recent)//4
        middle_end = 3 * len(recent)//4
        cup_bottom_idx = recent['low'].iloc[middle_start:middle_end].idxmin()
        cup_bottom = recent.loc[cup_bottom_idx, 'low']
        
        # Right rim area
        right_section = recent.iloc[middle_end:]
        if len(right_section) < 5:
            return False, {'reason': 'Handle section too short'}
        
        right_rim = right_section['high'].max()
        
        # Check cup shape
        cup_depth = (left_rim - cup_bottom) / left_rim
        if cup_depth < 0.12 or cup_depth > 0.35:
            return False, {'reason': f'Cup depth not in range ({cup_depth:.1%})'}
        
        # Check handle
        handle = right_section.tail(10)
        handle_high = handle['high'].max()
        handle_low = handle['low'].min()
        handle_depth = (handle_high - handle_low) / handle_high
        
        if handle_depth > handle_max_depth:
            return False, {'reason': f'Handle too deep ({handle_depth:.1%})'}
        
        # Validate pattern
        is_cup_handle = (
            abs(left_rim - right_rim) / left_rim < 0.05 and  # Rims similar height
            handle_depth < handle_max_depth and
            df['close'].iloc[-1] > df['close'].iloc[-5].mean() * 0.97  # Price holding
        )
        
        return is_cup_handle, {
            'left_rim': left_rim,
            'cup_bottom': cup_bottom,
            'right_rim': right_rim,
            'cup_depth': cup_depth,
            'handle_depth': handle_depth,
            'entry_price': right_rim * 1.01,
            'stop_loss': handle_low * 0.97,
            'target_price': right_rim + (left_rim - cup_bottom),
        }
    
    @staticmethod
    def is_tight_consolidation(
        df: pd.DataFrame, 
        period: int = 10, 
        max_range_pct: float = 0.05
    ) -> Tuple[bool, float]:
        """
        Detect tight price consolidation (squeeze before breakout).
        
        Returns:
            (is_tight, range_pct)
        """
        recent = df.tail(period)
        high = recent['high'].max()
        low = recent['low'].min()
        range_pct = (high - low) / high
        
        return range_pct <= max_range_pct, range_pct
    
    # ========== Alpha Factors ==========
    
    @staticmethod
    def momentum_factor(series: pd.Series, period: int = 20) -> pd.Series:
        """
        Momentum factor (returns over period).
        Used in factor-based investing.
        """
        return series.pct_change(periods=period)
    
    @staticmethod
    def reversal_factor(series: pd.Series, period: int = 5) -> pd.Series:
        """
        Short-term reversal factor.
        """
        return -series.pct_change(periods=period)
    
    @staticmethod
    def price_distance_from_52w_high(df: pd.DataFrame) -> pd.Series:
        """Distance from 52-week high (higher = stronger)."""
        high_52w = df['high'].rolling(window=252).max()
        return df['close'] / high_52w
    
    @staticmethod
    def relative_strength(
        stock_series: pd.Series, 
        benchmark_series: pd.Series, 
        period: int = 63
    ) -> pd.Series:
        """
        Relative Strength vs benchmark (e.g., SPY).
        
        Used for Mansfield Relative Strength.
        """
        stock_return = stock_series.pct_change(periods=period)
        benchmark_return = benchmark_series.pct_change(periods=period)
        return stock_return - benchmark_return
    
    @staticmethod
    def rs_rating(stock_series: pd.Series, period: int = 252) -> float:
        """
        Calculate RS Rating (1-99) similar to IBD RS Rating.
        
        Combines multiple momentum periods.
        """
        if len(stock_series) < period:
            return 50.0
        
        # Calculate returns over different periods
        ret_63d = (stock_series.iloc[-1] / stock_series.iloc[-63] - 1) if len(stock_series) >= 63 else 0
        ret_126d = (stock_series.iloc[-1] / stock_series.iloc[-126] - 1) if len(stock_series) >= 126 else 0
        ret_189d = (stock_series.iloc[-1] / stock_series.iloc[-189] - 1) if len(stock_series) >= 189 else 0
        ret_252d = (stock_series.iloc[-1] / stock_series.iloc[-252] - 1) if len(stock_series) >= 252 else 0
        
        # Weight: 40% recent quarter, 20% each older quarter
        weighted_return = 0.40 * ret_63d + 0.20 * ret_126d + 0.20 * ret_189d + 0.20 * ret_252d
        
        # Convert to 1-99 scale (simplified - in reality you'd compare vs universe)
        rs_rating = 50 + (weighted_return * 100)
        return max(1, min(99, rs_rating))
    
    # ========== Swing Trading Indicators ==========
    
    @staticmethod
    def fibonacci_retracement(
        df: pd.DataFrame,
        lookback: int = 50
    ) -> Dict[str, pd.Series]:
        """
        Calculate Fibonacci retracement levels from recent swing high/low.
        
        Key levels: 0%, 23.6%, 38.2%, 50%, 61.8%, 78.6%, 100%
        
        Returns:
            Dict with fib_0, fib_236, fib_382, fib_500, fib_618, fib_786, fib_100
        """
        recent = df.tail(lookback)
        swing_high = recent['high'].max()
        swing_low = recent['low'].min()
        diff = swing_high - swing_low
        
        # Standard Fibonacci levels (from high to low for uptrend retracement)
        fib_levels = {
            'fib_0': pd.Series(swing_high, index=df.index),        # 0% (high)
            'fib_236': pd.Series(swing_high - diff * 0.236, index=df.index),
            'fib_382': pd.Series(swing_high - diff * 0.382, index=df.index),
            'fib_500': pd.Series(swing_high - diff * 0.500, index=df.index),
            'fib_618': pd.Series(swing_high - diff * 0.618, index=df.index),
            'fib_786': pd.Series(swing_high - diff * 0.786, index=df.index),
            'fib_100': pd.Series(swing_low, index=df.index),       # 100% (low)
            'swing_high': pd.Series(swing_high, index=df.index),
            'swing_low': pd.Series(swing_low, index=df.index),
        }
        return fib_levels
    
    @staticmethod
    def swing_highs_lows(
        df: pd.DataFrame,
        swing_period: int = 5
    ) -> Tuple[pd.Series, pd.Series]:
        """
        Identify swing highs and swing lows.
        
        A swing high is when the high is higher than the surrounding bars.
        A swing low is when the low is lower than the surrounding bars.
        
        Returns:
            (swing_highs, swing_lows) - Series with values at swing points, NaN elsewhere
        """
        swing_highs = pd.Series(np.nan, index=df.index)
        swing_lows = pd.Series(np.nan, index=df.index)
        
        for i in range(swing_period, len(df) - swing_period):
            # Check for swing high
            is_swing_high = True
            for j in range(1, swing_period + 1):
                if df['high'].iloc[i] <= df['high'].iloc[i-j] or df['high'].iloc[i] <= df['high'].iloc[i+j]:
                    is_swing_high = False
                    break
            if is_swing_high:
                swing_highs.iloc[i] = df['high'].iloc[i]
            
            # Check for swing low
            is_swing_low = True
            for j in range(1, swing_period + 1):
                if df['low'].iloc[i] >= df['low'].iloc[i-j] or df['low'].iloc[i] >= df['low'].iloc[i+j]:
                    is_swing_low = False
                    break
            if is_swing_low:
                swing_lows.iloc[i] = df['low'].iloc[i]
        
        return swing_highs, swing_lows
    
    @staticmethod
    def pullback_days(df: pd.DataFrame) -> pd.Series:
        """
        Count consecutive down days (pullback length).
        
        Returns series with count of consecutive days where close < previous close.
        """
        down_day = df['close'] < df['close'].shift(1)
        
        pullback_count = pd.Series(0, index=df.index)
        count = 0
        for i in range(1, len(df)):
            if down_day.iloc[i]:
                count += 1
            else:
                count = 0
            pullback_count.iloc[i] = count
        
        return pullback_count
    
    @staticmethod
    def pullback_depth(df: pd.DataFrame, lookback: int = 20) -> pd.Series:
        """
        Calculate pullback depth from recent high as percentage.
        
        Returns percentage decline from recent high.
        """
        recent_high = df['high'].rolling(window=lookback).max()
        return (recent_high - df['close']) / recent_high * 100
    
    @staticmethod
    def donchian_channels(
        df: pd.DataFrame,
        period: int = 20
    ) -> Tuple[pd.Series, pd.Series, pd.Series]:
        """
        Donchian Channels (used in Turtle Trading).
        
        Returns:
            (upper_channel, middle_channel, lower_channel)
        """
        upper = df['high'].rolling(window=period).max()
        lower = df['low'].rolling(window=period).min()
        middle = (upper + lower) / 2
        return upper, middle, lower
    
    # ========== Candlestick Patterns ==========
    
    @staticmethod
    def is_hammer(df: pd.DataFrame) -> pd.Series:
        """
        Detect hammer candlestick pattern (bullish reversal).
        
        Criteria:
        - Small real body at top of range
        - Lower shadow at least 2x the real body
        - Little or no upper shadow
        """
        body = abs(df['close'] - df['open'])
        full_range = df['high'] - df['low']
        lower_shadow = pd.DataFrame({
            'open': df['open'],
            'close': df['close']
        }).min(axis=1) - df['low']
        upper_shadow = df['high'] - pd.DataFrame({
            'open': df['open'],
            'close': df['close']
        }).max(axis=1)
        
        is_hammer = (
            (lower_shadow >= 2 * body) &          # Long lower wick
            (upper_shadow <= body * 0.5) &        # Small upper wick
            (body <= full_range * 0.35) &         # Small body
            (body > 0)                            # Has a body
        )
        return is_hammer.astype(int)
    
    @staticmethod
    def is_bullish_engulfing(df: pd.DataFrame) -> pd.Series:
        """
        Detect bullish engulfing pattern.
        
        Criteria:
        - Previous candle is bearish (close < open)
        - Current candle is bullish (close > open)
        - Current body engulfs previous body
        """
        prev_bearish = df['close'].shift(1) < df['open'].shift(1)
        curr_bullish = df['close'] > df['open']
        engulfs = (
            (df['close'] > df['open'].shift(1)) &
            (df['open'] < df['close'].shift(1))
        )
        
        is_engulfing = prev_bearish & curr_bullish & engulfs
        return is_engulfing.astype(int)
    
    @staticmethod
    def is_doji(df: pd.DataFrame, threshold: float = 0.1) -> pd.Series:
        """
        Detect doji candlestick (indecision pattern).
        
        Body is very small compared to range.
        """
        body = abs(df['close'] - df['open'])
        full_range = df['high'] - df['low']
        
        is_doji = (body <= full_range * threshold) & (full_range > 0)
        return is_doji.astype(int)
    
    @staticmethod
    def is_morning_star(df: pd.DataFrame) -> pd.Series:
        """
        Detect morning star pattern (3-candle bullish reversal).
        
        Day 1: Long bearish candle
        Day 2: Small body (star) that gaps down
        Day 3: Long bullish candle that closes above day 1 midpoint
        """
        # Day 1: Bearish
        day1_bearish = (df['close'].shift(2) < df['open'].shift(2))
        day1_body = abs(df['close'].shift(2) - df['open'].shift(2))
        day1_range = df['high'].shift(2) - df['low'].shift(2)
        day1_long = day1_body > day1_range * 0.5
        
        # Day 2: Small body (star)
        day2_body = abs(df['close'].shift(1) - df['open'].shift(1))
        day2_range = df['high'].shift(1) - df['low'].shift(1)
        day2_small = day2_body < day2_range * 0.3
        
        # Day 3: Bullish, closes above day 1 midpoint
        day3_bullish = df['close'] > df['open']
        day1_midpoint = (df['open'].shift(2) + df['close'].shift(2)) / 2
        day3_strong = df['close'] > day1_midpoint
        
        is_morning_star = day1_bearish & day1_long & day2_small & day3_bullish & day3_strong
        return is_morning_star.astype(int)
    
    @staticmethod
    def is_bullish_reversal(df: pd.DataFrame) -> pd.Series:
        """
        Combined bullish reversal signal.
        
        Combines hammer, bullish engulfing, and morning star.
        """
        hammer = IndicatorLibrary.is_hammer(df)
        engulfing = IndicatorLibrary.is_bullish_engulfing(df)
        morning_star = IndicatorLibrary.is_morning_star(df)
        
        return ((hammer == 1) | (engulfing == 1) | (morning_star == 1)).astype(int)
    
    # ========== Trend Strength Indicators ==========
    
    @staticmethod
    def adx(df: pd.DataFrame, period: int = 14) -> Tuple[pd.Series, pd.Series, pd.Series]:
        """
        Average Directional Index - measures trend strength.
        
        Returns:
            (adx, plus_di, minus_di)
            ADX > 25: Strong trend
            ADX < 20: Weak/no trend (range-bound)
        """
        high = df['high']
        low = df['low']
        close = df['close']
        
        # +DM and -DM
        plus_dm = high.diff()
        minus_dm = low.shift(1) - low
        
        plus_dm = plus_dm.where((plus_dm > minus_dm) & (plus_dm > 0), 0)
        minus_dm = minus_dm.where((minus_dm > plus_dm) & (minus_dm > 0), 0)
        
        # True Range
        tr = pd.concat([
            high - low,
            (high - close.shift(1)).abs(),
            (low - close.shift(1)).abs()
        ], axis=1).max(axis=1)
        
        # Smoothed values
        atr = tr.ewm(span=period, adjust=False).mean()
        plus_di = 100 * (plus_dm.ewm(span=period, adjust=False).mean() / atr)
        minus_di = 100 * (minus_dm.ewm(span=period, adjust=False).mean() / atr)
        
        # DX and ADX
        dx = 100 * (plus_di - minus_di).abs() / (plus_di + minus_di).replace(0, 1)
        adx = dx.ewm(span=period, adjust=False).mean()
        
        return adx, plus_di, minus_di
    
    @staticmethod
    def trend_strength_score(df: pd.DataFrame) -> pd.Series:
        """
        Composite trend strength score (0-100).
        
        Combines:
        - Price vs moving averages
        - Moving average alignment
        - ADX trend strength
        """
        score = pd.Series(0.0, index=df.index)
        
        # Price vs MAs
        sma_20 = IndicatorLibrary.sma(df['close'], 20)
        sma_50 = IndicatorLibrary.sma(df['close'], 50)
        sma_200 = IndicatorLibrary.sma(df['close'], 200)
        
        # Points for price above MAs
        score += (df['close'] > sma_20).astype(int) * 15
        score += (df['close'] > sma_50).astype(int) * 20
        score += (df['close'] > sma_200).astype(int) * 25
        
        # Points for MA alignment
        score += (sma_20 > sma_50).astype(int) * 20
        score += (sma_50 > sma_200).astype(int) * 20
        
        return score
    
    @staticmethod
    def momentum_score(df: pd.DataFrame) -> pd.Series:
        """
        Multi-period momentum score for ranking stocks.
        
        Combines 1-week, 1-month, 3-month, 6-month returns.
        """
        ret_5d = df['close'].pct_change(5) * 100
        ret_21d = df['close'].pct_change(21) * 100
        ret_63d = df['close'].pct_change(63) * 100
        ret_126d = df['close'].pct_change(126) * 100
        
        # Weight recent performance more
        score = (0.4 * ret_21d + 0.3 * ret_63d + 0.2 * ret_126d + 0.1 * ret_5d)
        return score
    
    # ========== Support/Resistance Detection ==========
    
    @staticmethod
    def find_support_resistance(
        df: pd.DataFrame,
        lookback: int = 50,
        tolerance: float = 0.02
    ) -> Dict[str, list]:
        """
        Find support and resistance levels from price clusters.
        
        Returns:
            Dict with 'support' and 'resistance' lists
        """
        recent = df.tail(lookback)
        
        # Get swing highs and lows
        swing_highs, swing_lows = IndicatorLibrary.swing_highs_lows(recent, swing_period=3)
        
        resistance_levels = swing_highs.dropna().tolist()
        support_levels = swing_lows.dropna().tolist()
        
        # Cluster nearby levels
        def cluster_levels(levels, tolerance):
            if not levels:
                return []
            levels = sorted(levels)
            clusters = []
            current_cluster = [levels[0]]
            
            for level in levels[1:]:
                if (level - current_cluster[-1]) / current_cluster[-1] <= tolerance:
                    current_cluster.append(level)
                else:
                    clusters.append(sum(current_cluster) / len(current_cluster))
                    current_cluster = [level]
            clusters.append(sum(current_cluster) / len(current_cluster))
            return clusters
        
        return {
            'support': cluster_levels(support_levels, tolerance),
            'resistance': cluster_levels(resistance_levels, tolerance),
            'current_price': df['close'].iloc[-1]
        }
    
    # ========== Volume Analysis ==========
    
    @staticmethod
    def volume_trend(df: pd.DataFrame, period: int = 20) -> pd.Series:
        """
        Volume trend: 1 = increasing volume, -1 = decreasing, 0 = neutral.
        """
        vol_ma = IndicatorLibrary.volume_sma(df, period)
        vol_ma_short = IndicatorLibrary.volume_sma(df, period // 2)
        
        trend = pd.Series(0, index=df.index)
        trend = trend.where(vol_ma_short <= vol_ma * 1.1, 1)
        trend = trend.where(vol_ma_short >= vol_ma * 0.9, -1)
        return trend
    
    @staticmethod
    def volume_breakout(df: pd.DataFrame, threshold: float = 2.0) -> pd.Series:
        """
        Detect volume breakouts (volume > threshold * average).
        """
        avg_vol = IndicatorLibrary.volume_sma(df, 20)
        return (df['volume'] > threshold * avg_vol).astype(int)
    
    # ========== Time-based Exit Calculations ==========
    
    @staticmethod
    def bars_since_entry(df: pd.DataFrame, entry_signal: pd.Series) -> pd.Series:
        """
        Count bars since last entry signal.
        
        Useful for time-based exits.
        """
        bars = pd.Series(0, index=df.index)
        count = 0
        in_trade = False
        
        for i in range(len(df)):
            if entry_signal.iloc[i] == 1:
                in_trade = True
                count = 0
            elif in_trade:
                count += 1
            bars.iloc[i] = count
        
        return bars
