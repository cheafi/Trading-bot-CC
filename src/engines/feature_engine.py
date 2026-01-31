"""
TradingAI Bot - Feature Engine
Calculates technical and sentiment features for the signal engine.
"""
import pandas as pd
import numpy as np
from datetime import datetime, timedelta
from typing import List, Optional, Dict, Any
import logging

from src.core.models import TechnicalFeatures


class FeatureEngine:
    """
    Calculates features for the signal engine.
    
    Features calculated:
    - Price momentum (returns over various periods)
    - Volatility metrics (ATR, std dev, BB width)
    - Moving averages and distances
    - RSI, MACD, ADX
    - Volume metrics
    - Composite scores
    """
    
    def __init__(self):
        self.logger = logging.getLogger(__name__)
    
    def calculate_features(
        self, 
        ohlcv: pd.DataFrame,
        sentiment_data: Optional[pd.DataFrame] = None
    ) -> pd.DataFrame:
        """
        Calculate all features for given OHLCV data.
        
        Args:
            ohlcv: DataFrame with columns: open, high, low, close, volume
                   Index should be MultiIndex (date, ticker) or single ticker
            sentiment_data: Optional sentiment scores
        
        Returns:
            DataFrame with all calculated features
        """
        if ohlcv.empty:
            return pd.DataFrame()
        
        # Check if multi-ticker or single ticker
        if isinstance(ohlcv.index, pd.MultiIndex):
            return self._calculate_multi_ticker(ohlcv, sentiment_data)
        else:
            return self._calculate_single_ticker(ohlcv, sentiment_data)
    
    def _calculate_single_ticker(
        self, 
        df: pd.DataFrame,
        sentiment: Optional[pd.DataFrame] = None
    ) -> pd.DataFrame:
        """Calculate features for a single ticker."""
        features = pd.DataFrame(index=df.index)
        
        close = df['close']
        high = df['high']
        low = df['low']
        volume = df['volume']
        
        # Returns
        features['return_1d'] = close.pct_change(1)
        features['return_5d'] = close.pct_change(5)
        features['return_21d'] = close.pct_change(21)
        features['return_63d'] = close.pct_change(63)
        
        # Volatility
        features['volatility_21d'] = close.pct_change().rolling(21).std() * np.sqrt(252)
        features['atr_14'] = self._calculate_atr(high, low, close, 14)
        features['rsi_14'] = self._calculate_rsi(close, 14)
        
        # Moving Averages
        features['sma_20'] = close.rolling(20).mean()
        features['sma_50'] = close.rolling(50).mean()
        features['sma_200'] = close.rolling(200).mean()
        
        # Distance from MAs
        features['dist_from_sma20'] = (close - features['sma_20']) / features['sma_20']
        features['dist_from_sma50'] = (close - features['sma_50']) / features['sma_50']
        features['dist_from_sma200'] = (close - features['sma_200']) / features['sma_200']
        
        # Bollinger Bands
        bb_std = close.rolling(20).std()
        features['bb_upper'] = features['sma_20'] + (2 * bb_std)
        features['bb_lower'] = features['sma_20'] - (2 * bb_std)
        features['bb_width'] = (features['bb_upper'] - features['bb_lower']) / features['sma_20']
        
        # Volume metrics
        features['volume_sma_20'] = volume.rolling(20).mean()
        features['relative_volume'] = volume / features['volume_sma_20']
        features['obv'] = self._calculate_obv(close, volume)
        
        # Trend indicators
        features['adx_14'] = self._calculate_adx(high, low, close, 14)
        macd, signal, hist = self._calculate_macd(close)
        features['macd'] = macd
        features['macd_signal'] = signal
        features['macd_histogram'] = hist
        
        # High/Low tracking
        features['high_20d'] = high.rolling(20).max()
        features['low_20d'] = low.rolling(20).min()
        features['high_52w'] = high.rolling(252).max()
        features['low_52w'] = low.rolling(252).min()
        features['dist_from_52w_high'] = (features['high_52w'] - close) / features['high_52w']
        
        # Composite scores
        features['momentum_score'] = self._calculate_momentum_score(features)
        features['trend_score'] = self._calculate_trend_score(features)
        
        # Copy close for reference
        features['close'] = close
        
        return features
    
    def _calculate_multi_ticker(
        self, 
        df: pd.DataFrame,
        sentiment: Optional[pd.DataFrame] = None
    ) -> pd.DataFrame:
        """Calculate features for multiple tickers."""
        # Group by ticker and calculate features
        results = []
        
        for ticker in df.index.get_level_values('ticker').unique():
            ticker_data = df.xs(ticker, level='ticker')
            features = self._calculate_single_ticker(ticker_data, sentiment)
            features['ticker'] = ticker
            results.append(features)
        
        if results:
            combined = pd.concat(results)
            combined = combined.set_index('ticker', append=True)
            return combined
        
        return pd.DataFrame()
    
    def _calculate_atr(
        self, 
        high: pd.Series, 
        low: pd.Series, 
        close: pd.Series, 
        period: int = 14
    ) -> pd.Series:
        """Calculate Average True Range."""
        high_low = high - low
        high_close = (high - close.shift()).abs()
        low_close = (low - close.shift()).abs()
        
        tr = pd.concat([high_low, high_close, low_close], axis=1).max(axis=1)
        atr = tr.rolling(period).mean()
        
        return atr
    
    def _calculate_rsi(self, close: pd.Series, period: int = 14) -> pd.Series:
        """Calculate Relative Strength Index."""
        delta = close.diff()
        
        gain = delta.where(delta > 0, 0)
        loss = (-delta).where(delta < 0, 0)
        
        avg_gain = gain.rolling(period).mean()
        avg_loss = loss.rolling(period).mean()
        
        rs = avg_gain / avg_loss
        rsi = 100 - (100 / (1 + rs))
        
        return rsi
    
    def _calculate_obv(self, close: pd.Series, volume: pd.Series) -> pd.Series:
        """Calculate On-Balance Volume."""
        obv = (np.sign(close.diff()) * volume).fillna(0).cumsum()
        return obv
    
    def _calculate_adx(
        self, 
        high: pd.Series, 
        low: pd.Series, 
        close: pd.Series, 
        period: int = 14
    ) -> pd.Series:
        """Calculate Average Directional Index."""
        plus_dm = high.diff()
        minus_dm = low.diff().abs()
        
        plus_dm = plus_dm.where((plus_dm > minus_dm) & (plus_dm > 0), 0)
        minus_dm = minus_dm.where((minus_dm > plus_dm) & (minus_dm > 0), 0)
        
        atr = self._calculate_atr(high, low, close, period)
        
        plus_di = 100 * (plus_dm.rolling(period).mean() / atr)
        minus_di = 100 * (minus_dm.rolling(period).mean() / atr)
        
        dx = 100 * (abs(plus_di - minus_di) / (plus_di + minus_di))
        adx = dx.rolling(period).mean()
        
        return adx.fillna(0)
    
    def _calculate_macd(
        self, 
        close: pd.Series, 
        fast: int = 12, 
        slow: int = 26, 
        signal: int = 9
    ) -> tuple[pd.Series, pd.Series, pd.Series]:
        """Calculate MACD."""
        ema_fast = close.ewm(span=fast, adjust=False).mean()
        ema_slow = close.ewm(span=slow, adjust=False).mean()
        
        macd_line = ema_fast - ema_slow
        signal_line = macd_line.ewm(span=signal, adjust=False).mean()
        histogram = macd_line - signal_line
        
        return macd_line, signal_line, histogram
    
    def _calculate_momentum_score(self, features: pd.DataFrame) -> pd.Series:
        """Calculate composite momentum score (0-100)."""
        score = pd.Series(50, index=features.index)
        
        # RSI component
        rsi = features.get('rsi_14', pd.Series(50, index=features.index))
        score += (rsi - 50) * 0.3
        
        # Price vs MAs component
        dist_50 = features.get('dist_from_sma50', pd.Series(0, index=features.index))
        score += np.clip(dist_50 * 100, -20, 20)
        
        # MACD histogram component
        macd_hist = features.get('macd_histogram', pd.Series(0, index=features.index))
        score += np.sign(macd_hist) * 10
        
        return score.clip(0, 100)
    
    def _calculate_trend_score(self, features: pd.DataFrame) -> pd.Series:
        """Calculate trend strength score (0-100)."""
        score = pd.Series(50, index=features.index)
        
        # ADX component (higher = stronger trend)
        adx = features.get('adx_14', pd.Series(0, index=features.index))
        score += (adx - 25) * 0.5
        
        # MA alignment component
        close = features.get('close', pd.Series(0, index=features.index))
        sma_50 = features.get('sma_50', close)
        sma_200 = features.get('sma_200', close)
        
        # Bullish alignment: close > sma50 > sma200
        alignment = ((close > sma_50) & (sma_50 > sma_200)).astype(int) * 20
        score += alignment
        
        return score.clip(0, 100)
    
    def get_latest_features(self, features: pd.DataFrame) -> pd.DataFrame:
        """Get the most recent feature values for each ticker."""
        if isinstance(features.index, pd.MultiIndex):
            # Get latest date for each ticker
            latest = features.groupby('ticker').tail(1)
            # Reset to ticker index only
            latest = latest.droplevel('date') if 'date' in features.index.names else latest
            return latest
        else:
            # Single ticker - return last row
            return features.tail(1)
