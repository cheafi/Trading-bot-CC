"""
TradingAI Bot - VCP Strategy (Volatility Contraction Pattern)

Implements Mark Minervini's SEPA (Specific Entry Point Analysis) and VCP pattern.

VCP Pattern Characteristics:
1. Stock in Stage 2 uptrend (above rising 50-day and 200-day MA)
2. Price corrects in a series of tighter and tighter consolidations
3. Each successive contraction is shallower (e.g., 25% → 15% → 8%)
4. Volume dries up during consolidation
5. Breakout occurs on increasing volume at pivot point

Entry Criteria (SEPA):
- Trend Template: Above 150-day and 200-day MA, both rising
- 52-week high/low: Within 25% of 52-week high, at least 25% above 52-week low
- Relative Strength: Outperforming market
- Accumulation: Volume expanding on up days, contracting on down days

Reference: Mark Minervini - "Trade Like a Stock Market Wizard"
"""
import pandas as pd
import numpy as np
from typing import Dict, Any, Optional, List
from datetime import datetime

from .base_strategy import IStrategy, StrategyConfig, TimeFrame
from .indicators import IndicatorLibrary


class VCPStrategy(IStrategy):
    """
    VCP (Volatility Contraction Pattern) Strategy.
    
    This is Mark Minervini's signature pattern for finding stocks
    ready to make explosive moves. The strategy identifies stocks
    in a proper uptrend that are consolidating with decreasing volatility.
    
    Parameters:
        trend_template_enabled: Whether to apply full trend template
        min_contractions: Minimum number of volatility contractions
        max_base_depth: Maximum correction depth in base (default 30%)
        min_days_in_base: Minimum base length
        max_days_in_base: Maximum base length
        volume_contraction_threshold: Volume must contract by this much
        rs_min_rating: Minimum relative strength rating
    """
    
    STRATEGY_ID = "vcp"
    VERSION = "1.0"
    
    # Default timeframe (daily for swing trading)
    timeframe = TimeFrame.D1
    startup_candle_count = 250  # Need 252 days for 52-week calculations
    
    # Risk management
    stoploss = -0.07  # 7% stop loss
    trailing_stop = True
    trailing_stop_positive = 0.05  # Start trailing at 5% profit
    trailing_stop_positive_offset = 0.07  # Activate after 7% profit
    
    # ROI targets (Mark Minervini often takes profits in stages)
    minimal_roi = {
        "0": 0.20,    # 20% anytime
        "14": 0.15,   # 15% after 2 weeks
        "30": 0.10,   # 10% after 1 month
        "60": 0.05    # 5% after 2 months
    }
    
    def __init__(self, config: Optional[StrategyConfig] = None):
        super().__init__(config)
        
        # VCP-specific parameters
        params = getattr(config, 'parameters', {}) if config else {}
        
        self.trend_template_enabled = params.get('trend_template_enabled', True)
        self.min_contractions = params.get('min_contractions', 2)
        self.max_base_depth = params.get('max_base_depth', 0.30)
        self.min_days_in_base = params.get('min_days_in_base', 15)
        self.max_days_in_base = params.get('max_days_in_base', 65)
        self.volume_contraction_threshold = params.get('volume_contraction_threshold', 0.7)
        self.rs_min_rating = params.get('rs_min_rating', 70)
        
    def populate_indicators(
        self, 
        dataframe: pd.DataFrame, 
        metadata: Dict[str, Any]
    ) -> pd.DataFrame:
        """Add VCP-related indicators."""
        
        # Moving Averages for Trend Template
        dataframe['sma_50'] = IndicatorLibrary.sma(dataframe['close'], 50)
        dataframe['sma_150'] = IndicatorLibrary.sma(dataframe['close'], 150)
        dataframe['sma_200'] = IndicatorLibrary.sma(dataframe['close'], 200)
        
        # 52-week high/low
        dataframe['high_52w'] = dataframe['high'].rolling(window=252).max()
        dataframe['low_52w'] = dataframe['low'].rolling(window=252).min()
        
        # Distance from 52-week high/low
        dataframe['dist_from_52w_high'] = (
            (dataframe['high_52w'] - dataframe['close']) / dataframe['high_52w']
        )
        dataframe['dist_from_52w_low'] = (
            (dataframe['close'] - dataframe['low_52w']) / dataframe['low_52w']
        )
        
        # Moving average slopes (to check if rising)
        dataframe['sma_50_slope'] = dataframe['sma_50'].diff(10) / 10
        dataframe['sma_150_slope'] = dataframe['sma_150'].diff(10) / 10
        dataframe['sma_200_slope'] = dataframe['sma_200'].diff(10) / 10
        
        # ATR for volatility
        dataframe['atr'] = IndicatorLibrary.atr(dataframe, 14)
        dataframe['atr_pct'] = dataframe['atr'] / dataframe['close']
        
        # Volatility contraction ratio
        dataframe['vcr'] = IndicatorLibrary.volatility_contraction_ratio(dataframe, 10, 50)
        
        # Volume analysis
        dataframe['vol_sma_20'] = IndicatorLibrary.volume_sma(dataframe, 20)
        dataframe['vol_sma_50'] = IndicatorLibrary.volume_sma(dataframe, 50)
        dataframe['rel_volume'] = IndicatorLibrary.relative_volume(dataframe, 20)
        
        # RS Rating (simplified - would ideally compare to market)
        dataframe['rs_rating'] = dataframe['close'].rolling(window=min(252, len(dataframe))).apply(
            lambda x: IndicatorLibrary.rs_rating(x) if len(x) >= 63 else 50,
            raw=False
        )
        
        # Trend Template conditions (Mark Minervini's 8 criteria)
        dataframe['tt_price_above_150ma'] = dataframe['close'] > dataframe['sma_150']
        dataframe['tt_price_above_200ma'] = dataframe['close'] > dataframe['sma_200']
        dataframe['tt_150ma_above_200ma'] = dataframe['sma_150'] > dataframe['sma_200']
        dataframe['tt_200ma_rising'] = dataframe['sma_200_slope'] > 0
        dataframe['tt_50ma_above_150ma'] = dataframe['sma_50'] > dataframe['sma_150']
        dataframe['tt_price_above_50ma'] = dataframe['close'] > dataframe['sma_50']
        dataframe['tt_within_25pct_of_high'] = dataframe['dist_from_52w_high'] <= 0.25
        dataframe['tt_above_25pct_of_low'] = dataframe['dist_from_52w_low'] >= 0.25
        
        # Count trend template criteria met
        tt_columns = [col for col in dataframe.columns if col.startswith('tt_')]
        dataframe['tt_score'] = dataframe[tt_columns].sum(axis=1)
        
        # Full trend template (all 8 criteria)
        dataframe['trend_template'] = dataframe['tt_score'] >= 8
        
        # Detect tight consolidation
        tight_results = dataframe.apply(
            lambda row: self._detect_tight_range(dataframe.loc[:row.name].tail(10)) 
            if len(dataframe.loc[:row.name]) >= 10 else (False, 0),
            axis=1
        )
        dataframe['tight_consolidation'] = tight_results.apply(lambda x: x[0])
        dataframe['consolidation_range'] = tight_results.apply(lambda x: x[1])
        
        return dataframe
    
    def _detect_tight_range(self, df: pd.DataFrame) -> tuple:
        """Detect if price is in a tight trading range."""
        if len(df) < 5:
            return False, 0
        
        high = df['high'].max()
        low = df['low'].min()
        range_pct = (high - low) / high
        
        is_tight = range_pct < 0.08  # Less than 8% range
        return is_tight, range_pct
    
    def populate_entry_trend(
        self, 
        dataframe: pd.DataFrame, 
        metadata: Dict[str, Any]
    ) -> pd.DataFrame:
        """Generate VCP entry signals."""
        
        # Ensure columns exist
        if 'enter_long' not in dataframe.columns:
            dataframe['enter_long'] = 0
        
        # VCP entry conditions
        conditions = (
            # Trend Template (if enabled)
            (
                (dataframe['tt_score'] >= 7) if self.trend_template_enabled
                else (dataframe['close'] > dataframe['sma_50'])
            ) &
            
            # Price above key moving averages
            (dataframe['close'] > dataframe['sma_50']) &
            (dataframe['close'] > dataframe['sma_200']) &
            
            # Volatility is contracting (VCR < 1 means short-term vol < long-term vol)
            (dataframe['vcr'] < 0.8) &
            
            # In a tight consolidation
            (dataframe['tight_consolidation'] == True) &
            
            # Volume was dry RECENTLY (prior 5 days avg below average)
            (dataframe['volume'].rolling(5).mean().shift(1) < dataframe['vol_sma_50'] * 0.8) &
            
            # RS Rating above threshold
            (dataframe['rs_rating'] >= self.rs_min_rating) &
            
            # Within 25% of 52-week high
            (dataframe['dist_from_52w_high'] <= 0.25) &
            
            # At least 25% above 52-week low (Minervini original)
            (dataframe['dist_from_52w_low'] >= 0.25) &
            
            # TODAY is the breakout: volume surges above average
            (dataframe['volume'] > dataframe['vol_sma_20'] * 1.3)
        )
        
        dataframe.loc[conditions, 'enter_long'] = 1
        dataframe.loc[conditions, 'enter_tag'] = 'vcp_breakout'
        
        return dataframe
    
    def populate_exit_trend(
        self, 
        dataframe: pd.DataFrame, 
        metadata: Dict[str, Any]
    ) -> pd.DataFrame:
        """Generate VCP exit signals."""
        
        if 'exit_long' not in dataframe.columns:
            dataframe['exit_long'] = 0
        
        # Exit conditions
        exit_conditions = (
            # Close below 50-day MA for 2 consecutive days
            (dataframe['close'] < dataframe['sma_50']) &
            (dataframe['close'].shift(1) < dataframe['sma_50'].shift(1))
        ) | (
            # Close below 200-day MA
            (dataframe['close'] < dataframe['sma_200'])
        ) | (
            # Volume surge on down day (distribution)
            (dataframe['close'] < dataframe['open']) &
            (dataframe['rel_volume'] > 2.0)
        )
        
        dataframe.loc[exit_conditions, 'exit_long'] = 1
        dataframe.loc[exit_conditions, 'exit_tag'] = 'trend_break'
        
        return dataframe
    
    def custom_stoploss(
        self,
        ticker: str,
        trade_date: datetime,
        current_time: datetime,
        current_rate: float,
        current_profit: float,
        **kwargs
    ) -> float:
        """
        Custom stoploss based on ATR (volatility-adjusted).
        
        Instead of fixed percentage, use 2x ATR below entry.
        """
        # Get the dataframe if available
        dataframe = kwargs.get('dataframe')
        if dataframe is None or len(dataframe) == 0:
            return self.stoploss
        
        # Get current ATR percentage
        current_atr_pct = dataframe['atr_pct'].iloc[-1] if 'atr_pct' in dataframe.columns else 0.02
        
        # Stop loss at 2x ATR (converted to negative ratio)
        atr_stop = -2 * current_atr_pct
        
        # Don't allow stop wider than 10% or tighter than 3%
        atr_stop = max(-0.10, min(-0.03, atr_stop))
        
        return atr_stop
    
    def scan_universe(
        self,
        universe_data: Dict[str, pd.DataFrame],
        min_score: int = 6
    ) -> List[Dict[str, Any]]:
        """
        Scan a universe of stocks for VCP setups.
        
        Args:
            universe_data: Dict mapping ticker to OHLCV DataFrame
            min_score: Minimum trend template score to include
        
        Returns:
            List of VCP candidates with scores and details
        """
        candidates = []
        
        for ticker, df in universe_data.items():
            try:
                # Add indicators
                metadata = {'ticker': ticker, 'timeframe': self.timeframe.value}
                df = self.populate_indicators(df.copy(), metadata)
                
                if len(df) == 0:
                    continue
                
                last = df.iloc[-1]
                
                # Check if meets basic VCP criteria
                if last.get('tt_score', 0) >= min_score:
                    # Check for VCP pattern
                    is_vcp, vcp_details = IndicatorLibrary.is_vcp_setup(
                        df,
                        contractions=self.min_contractions,
                        min_base_length=self.min_days_in_base,
                        max_base_length=self.max_days_in_base,
                        max_depth_pct=self.max_base_depth
                    )
                    
                    candidates.append({
                        'ticker': ticker,
                        'price': last['close'],
                        'tt_score': last['tt_score'],
                        'rs_rating': last.get('rs_rating', 50),
                        'is_vcp': is_vcp,
                        'vcp_score': vcp_details.get('vcp_score', 0),
                        'dist_from_52w_high': last.get('dist_from_52w_high', 0),
                        'vcr': last.get('vcr', 1.0),
                        'volume_contraction': vcp_details.get('volume_contraction', 1.0),
                        'entry_price': vcp_details.get('entry_price'),
                        'stop_loss': vcp_details.get('stop_loss'),
                        'target_price': vcp_details.get('target_price'),
                        'tight_consolidation': last.get('tight_consolidation', False),
                    })
                    
            except Exception as e:
                self.logger.debug(f"Error scanning {ticker}: {e}")
                continue
        
        # Sort by VCP score, then RS rating
        candidates.sort(key=lambda x: (x['is_vcp'], x['vcp_score'], x['rs_rating']), reverse=True)
        
        return candidates


class SEPAScreener:
    """
    SEPA (Specific Entry Point Analysis) Screener.
    
    Mark Minervini's 8-point Trend Template for identifying
    Stage 2 uptrending stocks:
    
    1. Current price above both 150-day and 200-day MA
    2. 150-day MA is above 200-day MA
    3. 200-day MA is trending up (rising) for at least 1 month
    4. 50-day MA is above both 150-day and 200-day MA
    5. Current price is above 50-day MA
    6. Current price is at least 25% above 52-week low
    7. Current price is within 25% of 52-week high
    8. RS Rating >= 70 (relative strength vs market)
    """
    
    @staticmethod
    def screen(df: pd.DataFrame) -> Dict[str, Any]:
        """
        Screen a single stock against the Trend Template.
        
        Args:
            df: OHLCV DataFrame with at least 252 days of data
        
        Returns:
            Dict with criteria results and overall score
        """
        if len(df) < 252:
            return {'score': 0, 'passed': False, 'criteria': {}}
        
        # Calculate indicators
        sma_50 = IndicatorLibrary.sma(df['close'], 50)
        sma_150 = IndicatorLibrary.sma(df['close'], 150)
        sma_200 = IndicatorLibrary.sma(df['close'], 200)
        
        current_price = df['close'].iloc[-1]
        high_52w = df['high'].rolling(252).max().iloc[-1]
        low_52w = df['low'].rolling(252).min().iloc[-1]
        
        # Calculate RS Rating (simplified)
        rs_rating = IndicatorLibrary.rs_rating(df['close'])
        
        # Check each criterion
        criteria = {
            '1_above_150_200_ma': current_price > sma_150.iloc[-1] and current_price > sma_200.iloc[-1],
            '2_150_above_200': sma_150.iloc[-1] > sma_200.iloc[-1],
            '3_200_rising': sma_200.iloc[-1] > sma_200.iloc[-21],  # Rising over 1 month
            '4_50_above_150_200': sma_50.iloc[-1] > sma_150.iloc[-1] and sma_50.iloc[-1] > sma_200.iloc[-1],
            '5_above_50_ma': current_price > sma_50.iloc[-1],
            '6_above_25pct_of_low': current_price >= low_52w * 1.25,
            '7_within_25pct_of_high': current_price >= high_52w * 0.75,
            '8_rs_rating_70': rs_rating >= 70
        }
        
        score = sum(criteria.values())
        passed = score >= 8
        
        return {
            'score': score,
            'passed': passed,
            'criteria': criteria,
            'current_price': current_price,
            'sma_50': sma_50.iloc[-1],
            'sma_150': sma_150.iloc[-1],
            'sma_200': sma_200.iloc[-1],
            'high_52w': high_52w,
            'low_52w': low_52w,
            'rs_rating': rs_rating,
            'dist_from_high': (high_52w - current_price) / high_52w,
            'dist_from_low': (current_price - low_52w) / low_52w
        }
