"""
TradingAI Bot - Feature Engineering Pipeline

Provides comprehensive feature engineering for ML models:
- Technical features from price/volume data
- Factor-based features
- Temporal features (day of week, month, etc.)
- Cross-sectional features (relative to sector/market)
"""
import numpy as np
import pandas as pd
from typing import List, Dict, Optional, Tuple
from dataclasses import dataclass, field
from datetime import datetime
import logging

logger = logging.getLogger(__name__)


@dataclass
class FeatureConfig:
    """Configuration for feature engineering."""
    
    # Price-based features
    include_returns: bool = True
    return_periods: List[int] = field(default_factory=lambda: [1, 5, 10, 21, 63, 126, 252])
    
    # Volatility features
    include_volatility: bool = True
    volatility_periods: List[int] = field(default_factory=lambda: [10, 20, 60])
    
    # Technical features
    include_technicals: bool = True
    sma_periods: List[int] = field(default_factory=lambda: [5, 10, 20, 50, 200])
    rsi_period: int = 14
    
    # Volume features
    include_volume: bool = True
    volume_periods: List[int] = field(default_factory=lambda: [5, 10, 20])
    
    # Temporal features
    include_temporal: bool = True
    
    # Cross-sectional features
    include_cross_sectional: bool = True
    
    # Target configuration
    target_period: int = 5  # Days forward for target return
    target_type: str = "return"  # "return" or "direction"


class FeaturePipeline:
    """
    Pipeline for generating ML features from price data.
    
    Usage:
        pipeline = FeaturePipeline()
        features = pipeline.generate_features(price_df)
        X, y = pipeline.prepare_training_data(features)
    """
    
    def __init__(self, config: Optional[FeatureConfig] = None):
        """
        Initialize pipeline.
        
        Args:
            config: Feature configuration
        """
        self.config = config or FeatureConfig()
        self.feature_names: List[str] = []
    
    def generate_features(self, df: pd.DataFrame) -> pd.DataFrame:
        """
        Generate all features from OHLCV data.
        
        Args:
            df: DataFrame with columns [open, high, low, close, volume]
        
        Returns:
            DataFrame with all features
        """
        features = df.copy()
        
        if self.config.include_returns:
            features = self._add_return_features(features)
        
        if self.config.include_volatility:
            features = self._add_volatility_features(features)
        
        if self.config.include_technicals:
            features = self._add_technical_features(features)
        
        if self.config.include_volume:
            features = self._add_volume_features(features)
        
        if self.config.include_temporal:
            features = self._add_temporal_features(features)
        
        # Store feature names (exclude OHLCV and target)
        ohlcv_cols = ['open', 'high', 'low', 'close', 'volume']
        self.feature_names = [col for col in features.columns 
                             if col not in ohlcv_cols and not col.startswith('target')]
        
        return features
    
    def _add_return_features(self, df: pd.DataFrame) -> pd.DataFrame:
        """Add return-based features."""
        prices = df['close']
        
        for period in self.config.return_periods:
            df[f'return_{period}d'] = prices.pct_change(periods=period)
        
        # Log returns (more normally distributed)
        for period in self.config.return_periods:
            df[f'log_return_{period}d'] = np.log(prices / prices.shift(period))
        
        # Cumulative returns
        df['cum_return_5d'] = prices.pct_change(5)
        df['cum_return_20d'] = prices.pct_change(20)
        
        return df
    
    def _add_volatility_features(self, df: pd.DataFrame) -> pd.DataFrame:
        """Add volatility-based features."""
        returns = df['close'].pct_change()
        
        for period in self.config.volatility_periods:
            df[f'volatility_{period}d'] = returns.rolling(period).std() * np.sqrt(252)
            df[f'volatility_{period}d_rank'] = df[f'volatility_{period}d'].rank(pct=True)
        
        # Volatility ratio (short vs long term)
        if 10 in self.config.volatility_periods and 60 in self.config.volatility_periods:
            df['vol_ratio_10_60'] = df['volatility_10d'] / df['volatility_60d']
        
        # Parkinson volatility (using high-low)
        df['parkinson_vol'] = np.sqrt(
            (1 / (4 * np.log(2))) * 
            (np.log(df['high'] / df['low'])**2).rolling(20).mean()
        ) * np.sqrt(252)
        
        # ATR
        df['atr'] = self._calculate_atr(df, period=14)
        df['atr_pct'] = df['atr'] / df['close']
        
        return df
    
    def _calculate_atr(self, df: pd.DataFrame, period: int = 14) -> pd.Series:
        """Calculate Average True Range."""
        high = df['high']
        low = df['low']
        close = df['close']
        
        tr1 = high - low
        tr2 = abs(high - close.shift(1))
        tr3 = abs(low - close.shift(1))
        
        tr = pd.concat([tr1, tr2, tr3], axis=1).max(axis=1)
        return tr.rolling(period).mean()
    
    def _add_technical_features(self, df: pd.DataFrame) -> pd.DataFrame:
        """Add technical indicator features."""
        close = df['close']
        high = df['high']
        low = df['low']
        
        # SMA features
        for period in self.config.sma_periods:
            sma = close.rolling(period).mean()
            df[f'sma_{period}'] = sma
            df[f'price_sma_{period}_ratio'] = close / sma
        
        # EMA features
        for period in [12, 26, 50]:
            ema = close.ewm(span=period, adjust=False).mean()
            df[f'ema_{period}'] = ema
            df[f'price_ema_{period}_ratio'] = close / ema
        
        # MACD
        ema_12 = close.ewm(span=12, adjust=False).mean()
        ema_26 = close.ewm(span=26, adjust=False).mean()
        df['macd'] = ema_12 - ema_26
        df['macd_signal'] = df['macd'].ewm(span=9, adjust=False).mean()
        df['macd_histogram'] = df['macd'] - df['macd_signal']
        
        # RSI
        df['rsi'] = self._calculate_rsi(close, self.config.rsi_period)
        
        # Stochastic
        df['stoch_k'] = self._calculate_stochastic_k(df, 14)
        df['stoch_d'] = df['stoch_k'].rolling(3).mean()
        
        # Bollinger Bands
        bb_period = 20
        bb_std = 2
        sma_bb = close.rolling(bb_period).mean()
        std_bb = close.rolling(bb_period).std()
        df['bb_upper'] = sma_bb + bb_std * std_bb
        df['bb_lower'] = sma_bb - bb_std * std_bb
        df['bb_width'] = (df['bb_upper'] - df['bb_lower']) / sma_bb
        df['bb_position'] = (close - df['bb_lower']) / (df['bb_upper'] - df['bb_lower'])
        
        # Price momentum
        df['momentum_5d'] = close / close.shift(5) - 1
        df['momentum_10d'] = close / close.shift(10) - 1
        df['momentum_20d'] = close / close.shift(20) - 1
        
        # Price range features
        df['daily_range'] = (high - low) / close
        df['range_10d'] = (high.rolling(10).max() - low.rolling(10).min()) / close
        
        # Higher highs / lower lows
        df['hh'] = (high > high.shift(1)).astype(int).rolling(5).sum()
        df['ll'] = (low < low.shift(1)).astype(int).rolling(5).sum()
        
        return df
    
    def _calculate_rsi(self, prices: pd.Series, period: int) -> pd.Series:
        """Calculate RSI."""
        delta = prices.diff()
        gain = delta.where(delta > 0, 0).rolling(period).mean()
        loss = (-delta.where(delta < 0, 0)).rolling(period).mean()
        rs = gain / loss.replace(0, np.inf)
        return 100 - (100 / (1 + rs))
    
    def _calculate_stochastic_k(self, df: pd.DataFrame, period: int) -> pd.Series:
        """Calculate Stochastic %K."""
        lowest_low = df['low'].rolling(period).min()
        highest_high = df['high'].rolling(period).max()
        return 100 * (df['close'] - lowest_low) / (highest_high - lowest_low)
    
    def _add_volume_features(self, df: pd.DataFrame) -> pd.DataFrame:
        """Add volume-based features."""
        volume = df['volume']
        close = df['close']
        
        for period in self.config.volume_periods:
            avg_vol = volume.rolling(period).mean()
            df[f'volume_sma_{period}'] = avg_vol
            df[f'volume_ratio_{period}'] = volume / avg_vol
        
        # Dollar volume
        df['dollar_volume'] = volume * close
        df['dollar_volume_20d_avg'] = df['dollar_volume'].rolling(20).mean()
        
        # On-Balance Volume
        df['obv'] = (np.sign(close.diff()) * volume).cumsum()
        df['obv_change_5d'] = df['obv'].pct_change(5)
        
        # Volume price trend
        df['vpt'] = (volume * close.pct_change()).cumsum()
        
        # Up/Down volume ratio
        up_vol = volume.where(close.diff() > 0, 0)
        down_vol = volume.where(close.diff() < 0, 0)
        df['up_down_vol_ratio'] = up_vol.rolling(10).sum() / down_vol.rolling(10).sum()
        
        return df
    
    def _add_temporal_features(self, df: pd.DataFrame) -> pd.DataFrame:
        """Add temporal/cyclical features."""
        if not isinstance(df.index, pd.DatetimeIndex):
            return df
        
        # Day of week (0=Monday, 4=Friday)
        df['day_of_week'] = df.index.dayofweek
        
        # Cyclical encoding
        df['day_sin'] = np.sin(2 * np.pi * df.index.dayofweek / 5)
        df['day_cos'] = np.cos(2 * np.pi * df.index.dayofweek / 5)
        
        # Month
        df['month'] = df.index.month
        df['month_sin'] = np.sin(2 * np.pi * df.index.month / 12)
        df['month_cos'] = np.cos(2 * np.pi * df.index.month / 12)
        
        # Quarter
        df['quarter'] = df.index.quarter
        
        # Beginning/End of month
        df['is_month_start'] = df.index.is_month_start.astype(int)
        df['is_month_end'] = df.index.is_month_end.astype(int)
        
        # Days to month end
        df['days_to_month_end'] = df.index.daysinmonth - df.index.day
        
        return df
    
    def add_target(
        self,
        df: pd.DataFrame,
        target_period: Optional[int] = None,
        target_type: Optional[str] = None
    ) -> pd.DataFrame:
        """
        Add target variable for ML training.
        
        Args:
            df: DataFrame with features
            target_period: Days forward for target
            target_type: "return" for regression, "direction" for classification
        
        Returns:
            DataFrame with target column
        """
        target_period = target_period or self.config.target_period
        target_type = target_type or self.config.target_type
        
        future_return = df['close'].shift(-target_period) / df['close'] - 1
        
        if target_type == "return":
            df['target'] = future_return
        elif target_type == "direction":
            df['target'] = (future_return > 0).astype(int)
        else:
            raise ValueError(f"Unknown target type: {target_type}")
        
        return df
    
    def prepare_training_data(
        self,
        df: pd.DataFrame,
        dropna: bool = True
    ) -> Tuple[pd.DataFrame, pd.Series]:
        """
        Prepare X (features) and y (target) for ML training.
        
        Args:
            df: DataFrame with features and target
            dropna: Whether to drop rows with missing values
        
        Returns:
            Tuple of (X, y)
        """
        if 'target' not in df.columns:
            df = self.add_target(df)
        
        # Select feature columns
        X = df[self.feature_names].copy()
        y = df['target'].copy()
        
        if dropna:
            valid_mask = X.notna().all(axis=1) & y.notna()
            X = X.loc[valid_mask]
            y = y.loc[valid_mask]
        
        return X, y
    
    def generate_cross_sectional_features(
        self,
        all_data: Dict[str, pd.DataFrame],
        market_data: Optional[pd.DataFrame] = None
    ) -> Dict[str, pd.DataFrame]:
        """
        Generate cross-sectional features (relative to market/sector).
        
        Args:
            all_data: Dict mapping ticker to DataFrame with features
            market_data: Optional market index data (e.g., SPY)
        
        Returns:
            Dict with cross-sectional features added
        """
        result = {}
        
        # Get latest values for ranking
        latest_returns = {}
        latest_volumes = {}
        latest_volatilities = {}
        
        for ticker, df in all_data.items():
            if len(df) > 20:
                latest_returns[ticker] = df['close'].iloc[-1] / df['close'].iloc[-21] - 1
                latest_volumes[ticker] = df['volume'].iloc[-1]
                latest_volatilities[ticker] = df['close'].pct_change().iloc[-20:].std()
        
        # Create rank Series
        return_ranks = pd.Series(latest_returns).rank(pct=True)
        volume_ranks = pd.Series(latest_volumes).rank(pct=True)
        volatility_ranks = pd.Series(latest_volatilities).rank(pct=True)
        
        for ticker, df in all_data.items():
            df_copy = df.copy()
            
            # Relative strength vs market
            if market_data is not None and len(df_copy) == len(market_data):
                df_copy['relative_strength'] = (
                    df_copy['close'].pct_change(20) - 
                    market_data['close'].pct_change(20)
                )
            
            # Cross-sectional ranks
            if ticker in return_ranks:
                df_copy['return_rank'] = return_ranks[ticker]
            if ticker in volume_ranks:
                df_copy['volume_rank'] = volume_ranks[ticker]
            if ticker in volatility_ranks:
                df_copy['volatility_rank'] = volatility_ranks[ticker]
            
            result[ticker] = df_copy
        
        return result


class FeatureSelector:
    """
    Feature selection utilities for ML models.
    
    Provides:
    - Correlation-based filtering
    - Variance threshold
    - Importance-based selection
    """
    
    @staticmethod
    def remove_low_variance(
        X: pd.DataFrame,
        threshold: float = 0.01
    ) -> pd.DataFrame:
        """Remove features with low variance."""
        variances = X.var()
        low_var_cols = variances[variances < threshold].index.tolist()
        logger.info(f"Removing {len(low_var_cols)} low variance features")
        return X.drop(columns=low_var_cols)
    
    @staticmethod
    def remove_high_correlation(
        X: pd.DataFrame,
        threshold: float = 0.95
    ) -> pd.DataFrame:
        """Remove highly correlated features."""
        corr_matrix = X.corr().abs()
        upper = corr_matrix.where(
            np.triu(np.ones(corr_matrix.shape), k=1).astype(bool)
        )
        
        to_drop = [col for col in upper.columns if any(upper[col] > threshold)]
        logger.info(f"Removing {len(to_drop)} highly correlated features")
        return X.drop(columns=to_drop)
    
    @staticmethod
    def select_by_importance(
        X: pd.DataFrame,
        y: pd.Series,
        n_features: int = 30,
        model_type: str = "random_forest"
    ) -> List[str]:
        """
        Select top features by importance from a tree model.
        
        Returns list of selected feature names.
        """
        try:
            if model_type == "random_forest":
                from sklearn.ensemble import RandomForestRegressor
                model = RandomForestRegressor(n_estimators=50, max_depth=5, random_state=42)
            else:
                from sklearn.ensemble import GradientBoostingRegressor
                model = GradientBoostingRegressor(n_estimators=50, max_depth=3, random_state=42)
            
            # Handle missing values
            X_clean = X.fillna(X.mean())
            y_clean = y.fillna(y.mean())
            
            model.fit(X_clean, y_clean)
            
            importance = pd.Series(
                model.feature_importances_,
                index=X.columns
            ).sort_values(ascending=False)
            
            return importance.head(n_features).index.tolist()
            
        except ImportError:
            logger.warning("sklearn not installed. Returning all features.")
            return X.columns.tolist()
