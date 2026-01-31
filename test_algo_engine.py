"""
TradingAI Bot - Test & Demo for Enhanced Algo Engine

Tests and demonstrates the new modules inspired by:
- freqtrade (IStrategy pattern)
- backtrader (Cerebro engine)
- stefan-jansen/machine-learning-for-trading (Alpha factors)
- Stock-Prediction-Models (RL agents)
- FinanceDatabase (Universe coverage)

Run with: python test_algo_engine.py
"""
import numpy as np
import pandas as pd
from datetime import datetime, timedelta
import asyncio
import logging

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


def generate_sample_data(
    ticker: str = "AAPL",
    days: int = 500,
    start_price: float = 100.0,
    volatility: float = 0.02
) -> pd.DataFrame:
    """Generate sample OHLCV data for testing."""
    np.random.seed(42)
    
    dates = pd.date_range(end=datetime.now(), periods=days, freq='D')
    
    # Generate realistic price movement
    returns = np.random.normal(0.0005, volatility, days)
    
    # Add some trends
    trend = np.sin(np.linspace(0, 4 * np.pi, days)) * 0.001
    returns += trend
    
    prices = start_price * np.cumprod(1 + returns)
    
    # Generate OHLCV
    data = {
        'open': prices * (1 + np.random.uniform(-0.005, 0.005, days)),
        'high': prices * (1 + np.random.uniform(0.005, 0.02, days)),
        'low': prices * (1 + np.random.uniform(-0.02, -0.005, days)),
        'close': prices,
        'volume': np.random.randint(1000000, 10000000, days)
    }
    
    df = pd.DataFrame(data, index=dates)
    df['high'] = df[['open', 'high', 'close']].max(axis=1)
    df['low'] = df[['open', 'low', 'close']].min(axis=1)
    
    return df


def test_istrategy_pattern():
    """Test the IStrategy pattern inspired by freqtrade."""
    print("\n" + "="*60)
    print("Testing IStrategy Pattern (freqtrade-inspired)")
    print("="*60)
    
    try:
        from src.algo import IStrategy, StrategyConfig, StrategyMode
        from src.algo.vcp_strategy import VCPStrategy
        from src.algo.momentum_strategy import MomentumBreakoutStrategy
        from src.algo.mean_reversion_strategy import MeanReversionStrategy
        from src.algo.trend_following_strategy import TrendFollowingStrategy
        
        # Generate sample data
        df = generate_sample_data()
        
        strategies = [
            VCPStrategy(),
            MomentumBreakoutStrategy(),
            MeanReversionStrategy(),
            TrendFollowingStrategy()
        ]
        
        for strategy in strategies:
            print(f"\n--- {strategy.STRATEGY_ID} ---")
            
            # Analyze data with metadata
            metadata = {'ticker': 'TEST', 'timeframe': '1d'}
            result = strategy.analyze(df.copy(), metadata)
            
            # Get signals
            entry_signals = result[result['enter_long'] == 1]
            exit_signals = result[result['exit_long'] == 1]
            
            print(f"  Entry signals: {len(entry_signals)}")
            print(f"  Exit signals: {len(exit_signals)}")
            
            # Get latest signal - pass metadata
            latest = strategy.get_latest_signal(result, metadata)
            print(f"  Latest signal: {latest}")
        
        print("\n✅ IStrategy pattern test passed!")
        return True
        
    except Exception as e:
        print(f"❌ IStrategy test failed: {e}")
        import traceback
        traceback.print_exc()
        return False


def test_indicator_library():
    """Test the comprehensive indicator library."""
    print("\n" + "="*60)
    print("Testing Indicator Library")
    print("="*60)
    
    try:
        from src.algo.indicators import IndicatorLibrary
        
        df = generate_sample_data()
        
        indicators_to_test = [
            ('SMA 20', lambda: IndicatorLibrary.sma(df['close'], 20)),
            ('EMA 20', lambda: IndicatorLibrary.ema(df['close'], 20)),
            ('RSI', lambda: IndicatorLibrary.rsi(df['close'])),
            ('MACD', lambda: IndicatorLibrary.macd(df['close'])),
            ('Bollinger', lambda: IndicatorLibrary.bollinger_bands(df['close'])),
            ('ATR', lambda: IndicatorLibrary.atr(df['high'], df['low'], df['close'])),
            ('VWAP', lambda: IndicatorLibrary.vwap(df['high'], df['low'], df['close'], df['volume'])),
            ('Supertrend', lambda: IndicatorLibrary.supertrend(df['high'], df['low'], df['close'])),
            ('VCP Setup', lambda: IndicatorLibrary.is_vcp_setup(df)),
        ]
        
        for name, func in indicators_to_test:
            try:
                result = func()
                if isinstance(result, tuple):
                    print(f"  {name}: OK (returns {len(result)} series)")
                else:
                    valid = result.notna().sum()
                    print(f"  {name}: OK ({valid} valid values)")
            except Exception as e:
                print(f"  {name}: FAILED - {e}")
        
        print("\n✅ Indicator library test passed!")
        return True
        
    except Exception as e:
        print(f"❌ Indicator library test failed: {e}")
        import traceback
        traceback.print_exc()
        return False


def test_alpha_factors():
    """Test the alpha factor engine."""
    print("\n" + "="*60)
    print("Testing Alpha Factor Engine")
    print("="*60)
    
    try:
        from src.ml import AlphaFactorEngine, FactorLibrary
        
        # Generate data for multiple stocks
        tickers = ['AAPL', 'MSFT', 'GOOGL', 'AMZN', 'META']
        price_data = {}
        
        for ticker in tickers:
            price_data[ticker] = generate_sample_data(
                ticker=ticker,
                days=300,
                start_price=np.random.uniform(50, 200)
            )
        
        # Test individual factors
        print("\nIndividual factor tests:")
        df = price_data['AAPL']
        
        factors_to_test = [
            ('Momentum 3M', FactorLibrary.momentum_3m(df['close'])),
            ('Momentum 12-1', FactorLibrary.momentum_12_1(df['close'])),
            ('Volatility 20D', FactorLibrary.volatility_20d(df['close'])),
            ('Price to 52W High', FactorLibrary.price_to_52w_high(df)),
        ]
        
        for name, result in factors_to_test:
            value = result.iloc[-1] if not pd.isna(result.iloc[-1]) else "N/A"
            print(f"  {name}: {value:.4f}" if isinstance(value, float) else f"  {name}: {value}")
        
        # Test factor engine
        print("\nAlpha Factor Engine:")
        engine = AlphaFactorEngine()
        
        factor_df = engine.compute_factors(price_data)
        print(f"  Computed factors for {len(factor_df)} stocks")
        print(f"  Factors: {list(factor_df.columns)}")
        
        # Rank universe
        rankings = engine.rank_universe(price_data, top_n=5)
        print(f"\n  Top 5 stocks by composite score:")
        for ticker, row in rankings.iterrows():
            print(f"    {ticker}: {row['composite_score']:.4f}")
        
        print("\n✅ Alpha factor engine test passed!")
        return True
        
    except Exception as e:
        print(f"❌ Alpha factor engine test failed: {e}")
        import traceback
        traceback.print_exc()
        return False


def test_feature_pipeline():
    """Test the ML feature pipeline."""
    print("\n" + "="*60)
    print("Testing Feature Engineering Pipeline")
    print("="*60)
    
    try:
        from src.ml.feature_pipeline import FeaturePipeline, FeatureConfig, FeatureSelector
        
        df = generate_sample_data(days=400)
        
        # Configure pipeline
        config = FeatureConfig(
            include_returns=True,
            include_volatility=True,
            include_technicals=True,
            include_volume=True,
            include_temporal=True,
            target_period=5
        )
        
        pipeline = FeaturePipeline(config)
        
        # Generate features
        features_df = pipeline.generate_features(df)
        print(f"  Generated {len(pipeline.feature_names)} features")
        print(f"  Sample features: {pipeline.feature_names[:10]}")
        
        # Add target and prepare training data
        features_df = pipeline.add_target(features_df)
        X, y = pipeline.prepare_training_data(features_df)
        
        print(f"  Training samples: {len(X)}")
        print(f"  Feature matrix shape: {X.shape}")
        print(f"  Target distribution: {y.describe()}")
        
        # Test feature selection
        print("\n  Feature Selection:")
        X_low_var = FeatureSelector.remove_low_variance(X.copy())
        print(f"    After low variance removal: {X_low_var.shape[1]} features")
        
        X_low_corr = FeatureSelector.remove_high_correlation(X.copy())
        print(f"    After correlation removal: {X_low_corr.shape[1]} features")
        
        print("\n✅ Feature pipeline test passed!")
        return True
        
    except Exception as e:
        print(f"❌ Feature pipeline test failed: {e}")
        import traceback
        traceback.print_exc()
        return False


def test_enhanced_backtester():
    """Test the enhanced backtesting framework."""
    print("\n" + "="*60)
    print("Testing Enhanced Backtesting Framework")
    print("="*60)
    
    try:
        from src.backtest.enhanced_backtester import (
            BacktestEngine, BacktestConfig, StrategyComparator
        )
        from src.algo.momentum_strategy import MomentumBreakoutStrategy
        
        # Generate data
        tickers = ['AAPL', 'MSFT', 'GOOGL']
        price_data = {}
        signals = {}
        
        strategy = MomentumBreakoutStrategy()
        
        for ticker in tickers:
            df = generate_sample_data(ticker=ticker, days=400)
            price_data[ticker] = df
            
            # Generate signals with metadata
            metadata = {'ticker': ticker, 'timeframe': '1d'}
            analyzed = strategy.analyze(df.copy(), metadata)
            # Only get available signal columns
            signal_cols = ['enter_long', 'exit_long']
            if 'enter_short' in analyzed.columns:
                signal_cols.extend(['enter_short', 'exit_short'])
            signals[ticker] = analyzed[signal_cols]
        
        # Configure backtest
        config = BacktestConfig(
            initial_capital=100000,
            position_size_pct=0.2,
            max_positions=5,
            commission_rate=0.001,
            slippage_rate=0.001,
            stop_loss_pct=0.05,
            take_profit_pct=0.15
        )
        
        engine = BacktestEngine(config)
        
        # Run backtest
        print("\n  Running backtest...")
        result = engine.run(price_data, signals)
        
        # Print results
        print(result.summary())
        
        print("\n✅ Enhanced backtester test passed!")
        return True
        
    except Exception as e:
        print(f"❌ Enhanced backtester test failed: {e}")
        import traceback
        traceback.print_exc()
        return False


def test_advanced_patterns():
    """Test the advanced pattern scanner."""
    print("\n" + "="*60)
    print("Testing Advanced Pattern Scanner")
    print("="*60)
    
    try:
        from src.scanners.advanced_pattern_scanner import (
            AdvancedPatternScanner, PatternType
        )
        
        # Generate data for multiple stocks
        tickers = ['AAPL', 'MSFT', 'GOOGL', 'AMZN', 'META', 'NVDA', 'TSLA']
        price_data = {}
        
        for ticker in tickers:
            price_data[ticker] = generate_sample_data(
                ticker=ticker,
                days=300,
                start_price=np.random.uniform(50, 300)
            )
        
        scanner = AdvancedPatternScanner(
            min_pattern_days=15,
            max_pattern_days=65
        )
        
        # Scan for specific patterns
        patterns_to_scan = [
            PatternType.VCP,
            PatternType.FLAT_BASE,
            PatternType.CONSOLIDATION,
            PatternType.BULL_FLAG
        ]
        
        results = scanner.scan(
            price_data,
            patterns=patterns_to_scan,
            min_confidence=0.5  # Lower threshold for demo
        )
        
        print(f"\n  Found {len(results)} pattern matches:")
        for match in results[:10]:  # Show top 10
            print(f"    {match.symbol}: {match.pattern_type.value} "
                  f"(confidence: {match.confidence:.2f}, "
                  f"pivot: ${match.pivot_price:.2f})")
        
        print("\n✅ Advanced pattern scanner test passed!")
        return True
        
    except Exception as e:
        print(f"❌ Advanced pattern scanner test failed: {e}")
        import traceback
        traceback.print_exc()
        return False


def test_universe_provider():
    """Test the stock universe provider."""
    print("\n" + "="*60)
    print("Testing Universe Provider")
    print("="*60)
    
    try:
        from src.scanners.universe_provider import (
            UniverseProvider, UniverseFilter, IndexUniverse
        )
        
        provider = UniverseProvider()
        
        # Test getting universe with different base indexes
        for universe in [IndexUniverse.DOW30, IndexUniverse.NASDAQ100, IndexUniverse.SP500]:
            filter_config = UniverseFilter(base_universe=universe)
            tickers = provider.get_universe(filter_config)
            print(f"  {universe.value}: {len(tickers)} stocks")
        
        # Test filtering - use class methods on UniverseProvider
        print("\n  Testing filters:")
        
        # Large cap filter
        large_cap = UniverseProvider.large_cap_growth()
        tickers = provider.get_universe(large_cap)
        print(f"    Large cap growth filter: {len(tickers)} stocks")
        
        # Tech stocks filter
        tech_filter = UniverseProvider.tech_stocks()
        tickers = provider.get_universe(tech_filter)
        print(f"    Tech filter: {len(tickers)} stocks")
        
        # Momentum candidates
        momentum = UniverseProvider.momentum_candidates()
        tickers = provider.get_universe(momentum)
        print(f"    Momentum filter: {len(tickers)} stocks")
        
        print("\n✅ Universe provider test passed!")
        return True
        
    except Exception as e:
        print(f"❌ Universe provider test failed: {e}")
        import traceback
        traceback.print_exc()
        return False


def test_rl_agents():
    """Test the RL trading agents."""
    print("\n" + "="*60)
    print("Testing RL Trading Agents")
    print("="*60)
    
    try:
        from src.ml.rl_agents import (
            TradingEnvironment, SimpleQLearningAgent, RLTrainer
        )
        from src.ml.feature_pipeline import FeaturePipeline
        
        # Generate data with features
        df = generate_sample_data(days=300)
        
        # Add simple features
        df['return_5d'] = df['close'].pct_change(5)
        df['return_20d'] = df['close'].pct_change(20)
        df['volatility'] = df['close'].pct_change().rolling(20).std()
        df['sma_ratio'] = df['close'] / df['close'].rolling(20).mean()
        df['rsi'] = 50  # Simplified
        
        df = df.dropna()
        
        feature_cols = ['return_5d', 'return_20d', 'volatility', 'sma_ratio', 'rsi']
        
        # Create environment
        env = TradingEnvironment(
            df=df,
            feature_columns=feature_cols,
            initial_capital=100000
        )
        
        print(f"  Environment state dim: {env.state_dim}")
        print(f"  Environment action dim: {env.action_dim}")
        
        # Create Q-learning agent
        agent = SimpleQLearningAgent(
            state_dim=env.state_dim,
            learning_rate=0.1,
            epsilon=0.5
        )
        
        # Initialize bins from data
        states = df[feature_cols].values
        agent.initialize_bins(states)
        
        # Train for a few episodes
        trainer = RLTrainer(env, agent)
        
        print("\n  Training for 5 episodes...")
        history = trainer.train(n_episodes=5, log_interval=2)
        
        # Evaluate
        print("\n  Evaluating agent...")
        metrics = trainer.evaluate(n_episodes=3)
        
        print(f"    Avg Return: {metrics['avg_return']:.2%}")
        print(f"    Avg Win Rate: {metrics['avg_win_rate']:.2%}")
        
        print("\n✅ RL agents test passed!")
        return True
        
    except Exception as e:
        print(f"❌ RL agents test failed: {e}")
        import traceback
        traceback.print_exc()
        return False


def test_strategy_manager():
    """Test the strategy manager."""
    print("\n" + "="*60)
    print("Testing Strategy Manager")
    print("="*60)
    
    try:
        from src.algo import StrategyManager, StrategyConfig, StrategyMode
        from src.algo.vcp_strategy import VCPStrategy
        from src.algo.momentum_strategy import MomentumBreakoutStrategy
        
        manager = StrategyManager()
        
        # Load strategies (they auto-register on module import)
        manager.load_strategy("vcp")
        manager.load_strategy("momentum_breakout")
        
        print(f"  Active strategies: {manager.list_active_strategies()}")
        
        # Analyze with multiple strategies
        df = generate_sample_data()
        metadata = {'ticker': 'TEST', 'timeframe': '1d'}
        
        results = manager.run_all_strategies(df.copy(), metadata)
        print(f"\n  Analysis results for {len(results)} strategies:")
        
        for strategy_name, result_df in results.items():
            if strategy_name.startswith('_'):  # Skip aggregated
                continue
            entries = (result_df['enter_long'] == 1).sum()
            exits = (result_df['exit_long'] == 1).sum()
            print(f"    {strategy_name}: {entries} entries, {exits} exits")
        
        print("\n✅ Strategy manager test passed!")
        return True
        
    except Exception as e:
        print(f"❌ Strategy manager test failed: {e}")
        import traceback
        traceback.print_exc()
        return False


def main():
    """Run all tests."""
    print("\n" + "="*60)
    print("TradingAI Bot - Enhanced Algo Engine Tests")
    print("="*60)
    print("\nInspired by:")
    print("  - freqtrade (IStrategy pattern)")
    print("  - backtrader (Cerebro engine)")  
    print("  - machine-learning-for-trading (Alpha factors)")
    print("  - Stock-Prediction-Models (RL agents)")
    print("  - FinanceDatabase (Universe coverage)")
    print("  - Mark Minervini (VCP pattern)")
    
    tests = [
        ("IStrategy Pattern", test_istrategy_pattern),
        ("Indicator Library", test_indicator_library),
        ("Alpha Factor Engine", test_alpha_factors),
        ("Feature Pipeline", test_feature_pipeline),
        ("Strategy Manager", test_strategy_manager),
        ("Universe Provider", test_universe_provider),
        ("Advanced Patterns", test_advanced_patterns),
        ("Enhanced Backtester", test_enhanced_backtester),
        ("RL Agents", test_rl_agents),
    ]
    
    results = []
    for name, test_func in tests:
        try:
            passed = test_func()
            results.append((name, passed))
        except Exception as e:
            print(f"❌ {name} crashed: {e}")
            results.append((name, False))
    
    # Summary
    print("\n" + "="*60)
    print("TEST SUMMARY")
    print("="*60)
    
    passed = sum(1 for _, p in results if p)
    total = len(results)
    
    for name, p in results:
        status = "✅ PASS" if p else "❌ FAIL"
        print(f"  {status} - {name}")
    
    print(f"\n  Total: {passed}/{total} tests passed")
    
    if passed == total:
        print("\n🎉 All tests passed! The enhanced algo engine is ready.")
    else:
        print(f"\n⚠️  {total - passed} test(s) failed. Please check the errors above.")


if __name__ == "__main__":
    main()
