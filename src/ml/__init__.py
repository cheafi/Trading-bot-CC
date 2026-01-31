"""
TradingAI Bot - ML Alpha Factor Engine

Inspired by stefan-jansen/machine-learning-for-trading:
- Alpha factor engineering
- Factor evaluation with Alphalens-style metrics
- ML model integration for price prediction
- Feature importance analysis

This module provides:
- Pre-built alpha factors (momentum, value, quality, volatility)
- Factor combination and ranking
- ML model wrapper for predictions
- Optional integration (can be disabled)
"""
import numpy as np
import pandas as pd
from typing import List, Dict, Optional, Any, Tuple, Callable
from dataclasses import dataclass
from enum import Enum
from datetime import datetime, timedelta
import logging
from abc import ABC, abstractmethod

logger = logging.getLogger(__name__)


class FactorCategory(str, Enum):
    """Alpha factor categories."""
    MOMENTUM = "momentum"
    VALUE = "value"
    QUALITY = "quality"
    VOLATILITY = "volatility"
    LIQUIDITY = "liquidity"
    SENTIMENT = "sentiment"
    TECHNICAL = "technical"


@dataclass
class AlphaFactor:
    """Definition of an alpha factor."""
    name: str
    category: FactorCategory
    description: str
    lookback_days: int
    higher_is_better: bool = True  # For ranking direction
    
    # Optional: Custom calculation function
    calculate_fn: Optional[Callable] = None


class FactorLibrary:
    """
    Pre-built alpha factors for equity selection.
    
    Factors are inspired by:
    - Fama-French: Size, Value, Momentum
    - AQR: Quality, Low Volatility
    - Academic research: Various momentum and reversal factors
    """
    
    # ========== Momentum Factors ==========
    
    @staticmethod
    def momentum_1m(prices: pd.Series) -> pd.Series:
        """1-month momentum (returns over last 21 days)."""
        return prices.pct_change(periods=21)
    
    @staticmethod
    def momentum_3m(prices: pd.Series) -> pd.Series:
        """3-month momentum (returns over last 63 days)."""
        return prices.pct_change(periods=63)
    
    @staticmethod
    def momentum_6m(prices: pd.Series) -> pd.Series:
        """6-month momentum (returns over last 126 days)."""
        return prices.pct_change(periods=126)
    
    @staticmethod
    def momentum_12m(prices: pd.Series) -> pd.Series:
        """12-month momentum (returns over last 252 days)."""
        return prices.pct_change(periods=252)
    
    @staticmethod
    def momentum_12_1(prices: pd.Series) -> pd.Series:
        """
        12-1 momentum (Jegadeesh & Titman style).
        12-month return excluding most recent month.
        """
        ret_12m = prices.pct_change(periods=252)
        ret_1m = prices.pct_change(periods=21)
        return ret_12m - ret_1m
    
    @staticmethod
    def momentum_3_12(prices: pd.Series) -> pd.Series:
        """
        3-12 momentum.
        Average of 3m, 6m, and 12m momentum.
        """
        mom_3m = prices.pct_change(periods=63)
        mom_6m = prices.pct_change(periods=126)
        mom_12m = prices.pct_change(periods=252)
        return (mom_3m + mom_6m + mom_12m) / 3
    
    @staticmethod
    def reversal_short_term(prices: pd.Series) -> pd.Series:
        """Short-term reversal (1-week returns, inverted)."""
        return -prices.pct_change(periods=5)
    
    # ========== Volatility Factors ==========
    
    @staticmethod
    def volatility_20d(prices: pd.Series) -> pd.Series:
        """20-day realized volatility (annualized)."""
        returns = prices.pct_change()
        return returns.rolling(20).std() * np.sqrt(252)
    
    @staticmethod
    def volatility_60d(prices: pd.Series) -> pd.Series:
        """60-day realized volatility (annualized)."""
        returns = prices.pct_change()
        return returns.rolling(60).std() * np.sqrt(252)
    
    @staticmethod
    def beta(stock_returns: pd.Series, market_returns: pd.Series, window: int = 252) -> pd.Series:
        """
        Rolling beta vs market.
        
        Args:
            stock_returns: Stock returns series
            market_returns: Market (e.g., SPY) returns series
            window: Rolling window for beta calculation
        """
        cov = stock_returns.rolling(window).cov(market_returns)
        var = market_returns.rolling(window).var()
        return cov / var
    
    @staticmethod
    def idiosyncratic_volatility(
        stock_returns: pd.Series, 
        market_returns: pd.Series,
        window: int = 60
    ) -> pd.Series:
        """
        Idiosyncratic volatility (residual vol after market adjustment).
        
        Lower is often better (low idiosyncratic vol anomaly).
        """
        # Calculate beta
        cov = stock_returns.rolling(window).cov(market_returns)
        var = market_returns.rolling(window).var()
        beta_series = cov / var
        
        # Calculate residuals
        expected_returns = beta_series * market_returns
        residuals = stock_returns - expected_returns
        
        return residuals.rolling(window).std() * np.sqrt(252)
    
    # ========== Technical Factors ==========
    
    @staticmethod
    def price_to_52w_high(prices: pd.DataFrame) -> pd.Series:
        """
        Distance from 52-week high.
        
        Higher values = closer to high = stronger.
        """
        high_52w = prices['high'].rolling(252).max()
        return prices['close'] / high_52w
    
    @staticmethod
    def price_to_52w_low(prices: pd.DataFrame) -> pd.Series:
        """
        Distance from 52-week low.
        
        Higher values = further from low = stronger.
        """
        low_52w = prices['low'].rolling(252).min()
        return prices['close'] / low_52w
    
    @staticmethod
    def relative_strength_index(prices: pd.Series, period: int = 14) -> pd.Series:
        """RSI as a factor (mean-reversion signal)."""
        delta = prices.diff()
        gain = delta.where(delta > 0, 0).rolling(period).mean()
        loss = (-delta.where(delta < 0, 0)).rolling(period).mean()
        rs = gain / loss.replace(0, np.inf)
        return 100 - (100 / (1 + rs))
    
    @staticmethod
    def sma_cross_signal(prices: pd.Series, short: int = 20, long: int = 50) -> pd.Series:
        """
        SMA crossover signal.
        
        1 = short > long (bullish)
        -1 = short < long (bearish)
        """
        sma_short = prices.rolling(short).mean()
        sma_long = prices.rolling(long).mean()
        return (sma_short > sma_long).astype(int) * 2 - 1
    
    # ========== Liquidity Factors ==========
    
    @staticmethod
    def turnover(volume: pd.Series, shares_outstanding: float) -> pd.Series:
        """
        Stock turnover ratio.
        
        Higher turnover = more liquid.
        """
        return volume / shares_outstanding
    
    @staticmethod
    def volume_to_avg(volume: pd.Series, period: int = 20) -> pd.Series:
        """
        Relative volume vs average.
        
        Higher = more interest/liquidity today.
        """
        avg_vol = volume.rolling(period).mean()
        return volume / avg_vol
    
    @staticmethod
    def amihud_illiquidity(
        prices: pd.Series, 
        volume: pd.Series, 
        period: int = 20
    ) -> pd.Series:
        """
        Amihud Illiquidity Ratio.
        
        Lower = more liquid (easier to trade without price impact).
        """
        returns = prices.pct_change().abs()
        dollar_volume = prices * volume
        ratio = returns / dollar_volume
        return ratio.rolling(period).mean()


class AlphaFactorEngine:
    """
    Engine for computing and combining alpha factors.
    
    Features:
    - Compute multiple factors across a universe
    - Normalize and rank factors
    - Combine factors into composite score
    - Evaluate factor performance
    """
    
    def __init__(self, factors: Optional[List[AlphaFactor]] = None):
        """
        Initialize with list of factors to compute.
        
        Args:
            factors: List of AlphaFactor definitions
        """
        self.factors = factors or self._default_factors()
        self.logger = logging.getLogger(__name__)
    
    def _default_factors(self) -> List[AlphaFactor]:
        """Default set of alpha factors."""
        return [
            AlphaFactor(
                name="momentum_3m",
                category=FactorCategory.MOMENTUM,
                description="3-month price momentum",
                lookback_days=63,
                higher_is_better=True
            ),
            AlphaFactor(
                name="momentum_12_1",
                category=FactorCategory.MOMENTUM,
                description="12-1 month momentum",
                lookback_days=252,
                higher_is_better=True
            ),
            AlphaFactor(
                name="volatility_20d",
                category=FactorCategory.VOLATILITY,
                description="20-day volatility",
                lookback_days=20,
                higher_is_better=False  # Low vol preferred
            ),
            AlphaFactor(
                name="price_to_52w_high",
                category=FactorCategory.TECHNICAL,
                description="Distance from 52-week high",
                lookback_days=252,
                higher_is_better=True
            ),
            AlphaFactor(
                name="reversal_short_term",
                category=FactorCategory.MOMENTUM,
                description="1-week reversal",
                lookback_days=5,
                higher_is_better=True  # Buy recent losers
            ),
        ]
    
    def compute_factors(
        self,
        price_data: Dict[str, pd.DataFrame],
        as_of_date: Optional[datetime] = None
    ) -> pd.DataFrame:
        """
        Compute all factors for a universe of stocks.
        
        Args:
            price_data: Dict mapping ticker to OHLCV DataFrame
            as_of_date: Date to compute factors for (default: latest)
        
        Returns:
            DataFrame with tickers as rows and factors as columns
        """
        results = []
        
        for ticker, df in price_data.items():
            if len(df) < 252:
                self.logger.debug(f"Skipping {ticker}: insufficient data")
                continue
            
            try:
                row = {'ticker': ticker}
                
                for factor in self.factors:
                    value = self._compute_single_factor(df, factor)
                    row[factor.name] = value
                
                results.append(row)
                
            except Exception as e:
                self.logger.debug(f"Factor computation failed for {ticker}: {e}")
        
        return pd.DataFrame(results).set_index('ticker')
    
    def _compute_single_factor(
        self, 
        df: pd.DataFrame, 
        factor: AlphaFactor
    ) -> float:
        """Compute a single factor for one stock."""
        
        prices = df['close']
        
        # Use custom function if provided
        if factor.calculate_fn:
            return factor.calculate_fn(df)
        
        # Use library functions
        if factor.name == "momentum_1m":
            return FactorLibrary.momentum_1m(prices).iloc[-1]
        elif factor.name == "momentum_3m":
            return FactorLibrary.momentum_3m(prices).iloc[-1]
        elif factor.name == "momentum_6m":
            return FactorLibrary.momentum_6m(prices).iloc[-1]
        elif factor.name == "momentum_12m":
            return FactorLibrary.momentum_12m(prices).iloc[-1]
        elif factor.name == "momentum_12_1":
            return FactorLibrary.momentum_12_1(prices).iloc[-1]
        elif factor.name == "momentum_3_12":
            return FactorLibrary.momentum_3_12(prices).iloc[-1]
        elif factor.name == "reversal_short_term":
            return FactorLibrary.reversal_short_term(prices).iloc[-1]
        elif factor.name == "volatility_20d":
            return FactorLibrary.volatility_20d(prices).iloc[-1]
        elif factor.name == "volatility_60d":
            return FactorLibrary.volatility_60d(prices).iloc[-1]
        elif factor.name == "price_to_52w_high":
            return FactorLibrary.price_to_52w_high(df).iloc[-1]
        elif factor.name == "price_to_52w_low":
            return FactorLibrary.price_to_52w_low(df).iloc[-1]
        elif factor.name == "rsi":
            return FactorLibrary.relative_strength_index(prices).iloc[-1]
        elif factor.name == "volume_to_avg":
            return FactorLibrary.volume_to_avg(df['volume']).iloc[-1]
        else:
            self.logger.warning(f"Unknown factor: {factor.name}")
            return np.nan
    
    def normalize_factors(
        self,
        factor_df: pd.DataFrame,
        method: str = "zscore"
    ) -> pd.DataFrame:
        """
        Normalize factors for comparability.
        
        Args:
            factor_df: DataFrame with raw factor values
            method: "zscore", "rank", or "minmax"
        
        Returns:
            DataFrame with normalized factors
        """
        normalized = factor_df.copy()
        
        for col in normalized.columns:
            if method == "zscore":
                mean = normalized[col].mean()
                std = normalized[col].std()
                if std > 0:
                    normalized[col] = (normalized[col] - mean) / std
            elif method == "rank":
                normalized[col] = normalized[col].rank(pct=True)
            elif method == "minmax":
                min_val = normalized[col].min()
                max_val = normalized[col].max()
                if max_val > min_val:
                    normalized[col] = (normalized[col] - min_val) / (max_val - min_val)
        
        return normalized
    
    def compute_composite_score(
        self,
        factor_df: pd.DataFrame,
        weights: Optional[Dict[str, float]] = None
    ) -> pd.Series:
        """
        Compute composite alpha score from multiple factors.
        
        Args:
            factor_df: DataFrame with normalized factor values
            weights: Optional dict of factor weights (default: equal weight)
        
        Returns:
            Series of composite scores
        """
        # Normalize first
        norm_df = self.normalize_factors(factor_df)
        
        # Adjust direction (multiply by -1 if lower is better)
        for factor in self.factors:
            if factor.name in norm_df.columns and not factor.higher_is_better:
                norm_df[factor.name] = -norm_df[factor.name]
        
        # Apply weights
        if weights is None:
            weights = {f.name: 1.0 / len(self.factors) for f in self.factors}
        
        # Compute weighted sum
        score = pd.Series(0.0, index=norm_df.index)
        for factor_name, weight in weights.items():
            if factor_name in norm_df.columns:
                score += weight * norm_df[factor_name].fillna(0)
        
        return score
    
    def rank_universe(
        self,
        price_data: Dict[str, pd.DataFrame],
        top_n: int = 20,
        weights: Optional[Dict[str, float]] = None
    ) -> pd.DataFrame:
        """
        Rank stocks by composite alpha score.
        
        Args:
            price_data: Dict mapping ticker to OHLCV DataFrame
            top_n: Number of top stocks to return
            weights: Optional factor weights
        
        Returns:
            DataFrame with top stocks and their scores
        """
        # Compute factors
        factor_df = self.compute_factors(price_data)
        
        if factor_df.empty:
            return pd.DataFrame()
        
        # Compute composite score
        scores = self.compute_composite_score(factor_df, weights)
        
        # Combine with original factors
        result = factor_df.copy()
        result['composite_score'] = scores
        
        # Rank and select top
        result = result.sort_values('composite_score', ascending=False)
        result['rank'] = range(1, len(result) + 1)
        
        return result.head(top_n)


class FactorEvaluator:
    """
    Evaluate factor performance (similar to Alphalens).
    
    Provides:
    - Information Coefficient (IC) analysis
    - Quantile returns
    - Factor decay analysis
    """
    
    @staticmethod
    def compute_ic(
        factor: pd.Series,
        forward_returns: pd.Series
    ) -> float:
        """
        Compute Information Coefficient (Spearman correlation).
        
        IC measures how well factor ranks predict future returns.
        """
        # Align indices
        common_idx = factor.index.intersection(forward_returns.index)
        factor = factor.loc[common_idx]
        returns = forward_returns.loc[common_idx]
        
        # Spearman correlation
        return factor.corr(returns, method='spearman')
    
    @staticmethod
    def compute_ic_time_series(
        factor_df: pd.DataFrame,
        price_data: Dict[str, pd.DataFrame],
        forward_periods: List[int] = [1, 5, 10, 21]
    ) -> pd.DataFrame:
        """
        Compute IC over time for different holding periods.
        
        Args:
            factor_df: DataFrame with factor values (indexed by ticker)
            price_data: Dict mapping ticker to price DataFrame
            forward_periods: Holding periods in days
        
        Returns:
            DataFrame with IC for each factor and period
        """
        results = []
        
        for period in forward_periods:
            for factor_name in factor_df.columns:
                if factor_name in ['rank', 'composite_score']:
                    continue
                
                # Calculate forward returns for each ticker
                fwd_returns = {}
                for ticker in factor_df.index:
                    if ticker in price_data:
                        prices = price_data[ticker]['close']
                        if len(prices) > period:
                            fwd_returns[ticker] = (prices.iloc[-1] / prices.iloc[-period-1]) - 1
                
                fwd_series = pd.Series(fwd_returns)
                factor_series = factor_df[factor_name]
                
                # Compute IC
                ic = FactorEvaluator.compute_ic(factor_series, fwd_series)
                
                results.append({
                    'factor': factor_name,
                    'period': period,
                    'ic': ic
                })
        
        return pd.DataFrame(results)
    
    @staticmethod
    def quantile_returns(
        factor: pd.Series,
        forward_returns: pd.Series,
        n_quantiles: int = 5
    ) -> pd.Series:
        """
        Compute average returns by factor quantile.
        
        High IC factors should show monotonic returns across quantiles.
        """
        # Align
        common_idx = factor.index.intersection(forward_returns.index)
        factor = factor.loc[common_idx]
        returns = forward_returns.loc[common_idx]
        
        # Create quantiles
        quantiles = pd.qcut(factor, n_quantiles, labels=range(1, n_quantiles + 1))
        
        # Average returns per quantile
        return returns.groupby(quantiles).mean()


class MLPredictor(ABC):
    """
    Abstract base class for ML prediction models.
    
    Provides interface for:
    - Training on historical data
    - Making predictions
    - Feature importance
    """
    
    @abstractmethod
    def fit(self, X: pd.DataFrame, y: pd.Series) -> None:
        """Train the model."""
        pass
    
    @abstractmethod
    def predict(self, X: pd.DataFrame) -> pd.Series:
        """Make predictions."""
        pass
    
    @abstractmethod
    def feature_importance(self) -> pd.Series:
        """Get feature importance."""
        pass


class SimpleMLPredictor(MLPredictor):
    """
    Simple ML predictor using sklearn-compatible models.
    
    Supports:
    - Random Forest
    - Gradient Boosting
    - Linear models
    """
    
    def __init__(self, model_type: str = "random_forest", **kwargs):
        """
        Initialize predictor.
        
        Args:
            model_type: "random_forest", "gradient_boosting", or "linear"
            **kwargs: Model hyperparameters
        """
        self.model_type = model_type
        self.model = None
        self.feature_names = None
        
        # Store kwargs for model creation
        self.model_kwargs = kwargs
    
    def _create_model(self):
        """Create the ML model."""
        try:
            if self.model_type == "random_forest":
                from sklearn.ensemble import RandomForestRegressor
                return RandomForestRegressor(
                    n_estimators=self.model_kwargs.get('n_estimators', 100),
                    max_depth=self.model_kwargs.get('max_depth', 10),
                    random_state=42
                )
            elif self.model_type == "gradient_boosting":
                from sklearn.ensemble import GradientBoostingRegressor
                return GradientBoostingRegressor(
                    n_estimators=self.model_kwargs.get('n_estimators', 100),
                    max_depth=self.model_kwargs.get('max_depth', 5),
                    random_state=42
                )
            elif self.model_type == "linear":
                from sklearn.linear_model import Ridge
                return Ridge(alpha=self.model_kwargs.get('alpha', 1.0))
            else:
                raise ValueError(f"Unknown model type: {self.model_type}")
        except ImportError:
            logger.warning("sklearn not installed. ML features disabled.")
            return None
    
    def fit(self, X: pd.DataFrame, y: pd.Series) -> None:
        """Train the model."""
        self.model = self._create_model()
        if self.model is None:
            return
        
        self.feature_names = X.columns.tolist()
        
        # Handle missing values
        X_clean = X.fillna(X.mean())
        y_clean = y.fillna(y.mean())
        
        self.model.fit(X_clean, y_clean)
    
    def predict(self, X: pd.DataFrame) -> pd.Series:
        """Make predictions."""
        if self.model is None:
            return pd.Series(0, index=X.index)
        
        X_clean = X.fillna(X.mean())
        predictions = self.model.predict(X_clean)
        return pd.Series(predictions, index=X.index)
    
    def feature_importance(self) -> pd.Series:
        """Get feature importance."""
        if self.model is None or self.feature_names is None:
            return pd.Series()
        
        if hasattr(self.model, 'feature_importances_'):
            return pd.Series(
                self.model.feature_importances_,
                index=self.feature_names
            ).sort_values(ascending=False)
        elif hasattr(self.model, 'coef_'):
            return pd.Series(
                np.abs(self.model.coef_),
                index=self.feature_names
            ).sort_values(ascending=False)
        else:
            return pd.Series()
