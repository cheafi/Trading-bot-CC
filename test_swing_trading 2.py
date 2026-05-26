"""
Test Short-Term Swing Trading Framework

Tests the complete swing trading framework including:
1. Swing trading indicators (Fibonacci, swing points, candlestick patterns)
2. 4 swing trading strategies
3. 3 earnings/event strategies
4. Position manager and risk management
5. Integration tests
"""
import sys
import os
import pandas as pd
import numpy as np
from datetime import datetime, timedelta
from typing import Dict, List

# Add src to path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))


def generate_swing_data(days: int = 200, trend: str = "up") -> pd.DataFrame:
    """Generate realistic price data with swing patterns."""
    np.random.seed(42)
    
    dates = pd.date_range(start='2025-01-01', periods=days, freq='D')
    
    # Create trend with swings
    if trend == "up":
        base_trend = np.linspace(100, 150, days)
    elif trend == "down":
        base_trend = np.linspace(150, 100, days)
    else:  # sideways
        base_trend = np.full(days, 125)
    
    # Add swing oscillations
    swing_cycle = np.sin(np.linspace(0, 8 * np.pi, days)) * 8
    noise = np.random.randn(days) * 2
    
    close = base_trend + swing_cycle + noise
    
    # Generate OHLC
    high = close + np.random.uniform(0.5, 2.5, days)
    low = close - np.random.uniform(0.5, 2.5, days)
    open_price = close + np.random.randn(days) * 1.0
    
    # Volume with spikes
    base_volume = np.random.randint(500000, 2000000, days)
    volume_spikes = np.where(
        np.abs(np.diff(close, prepend=close[0])) > 3,
        base_volume * 2.5,
        base_volume
    )
    
    df = pd.DataFrame({
        'open': open_price,
        'high': high,
        'low': low,
        'close': close,
        'volume': volume_spikes.astype(int)
    }, index=dates)
    
    return df


def generate_earnings_gap_data(days: int = 100) -> pd.DataFrame:
    """Generate data with an earnings gap."""
    np.random.seed(123)
    
    dates = pd.date_range(start='2025-01-01', periods=days, freq='D')
    
    # Pre-earnings trend up
    pre_earnings = np.linspace(100, 110, 50)
    pre_earnings += np.random.randn(50) * 1.5
    
    # Earnings gap at day 50
    gap = 8.0  # 8% gap up
    post_earnings_start = pre_earnings[-1] * (1 + gap/100)
    
    # Post-earnings drift
    post_earnings = np.linspace(post_earnings_start, post_earnings_start * 1.10, 50)
    post_earnings += np.random.randn(50) * 2
    
    close = np.concatenate([pre_earnings, post_earnings])
    
    # Generate OHLC
    high = close + np.random.uniform(0.5, 2, days)
    low = close - np.random.uniform(0.5, 2, days)
    open_price = np.concatenate([
        close[:50] + np.random.randn(50) * 0.5,
        [post_earnings_start],  # Gap open
        close[51:] + np.random.randn(49) * 0.5
    ])
    
    # High volume on gap day
    volume = np.random.randint(500000, 1500000, days)
    volume[50] = volume[50] * 3  # 3x volume on earnings
    
    df = pd.DataFrame({
        'open': open_price,
        'high': high,
        'low': low,
        'close': close,
        'volume': volume
    }, index=dates)
    
    return df


def test_swing_indicators():
    """Test new swing trading indicators."""
    print("\n" + "="*60)
    print("TEST 1: Swing Trading Indicators")
    print("="*60)
    
    from src.algo.indicators import IndicatorLibrary as IL
    
    df = generate_swing_data(200, trend="up")
    
    # Test Fibonacci retracements
    fib = IL.fibonacci_retracement(df, lookback=50)
    print(f"\n✓ Fibonacci Levels:")
    print(f"  - Swing High: ${fib['swing_high'].iloc[-1]:.2f}")
    print(f"  - Swing Low: ${fib['swing_low'].iloc[-1]:.2f}")
    print(f"  - 38.2% retracement: ${fib['fib_382'].iloc[-1]:.2f}")
    print(f"  - 50% retracement: ${fib['fib_500'].iloc[-1]:.2f}")
    print(f"  - 61.8% retracement: ${fib['fib_618'].iloc[-1]:.2f}")
    
    # Test swing highs/lows
    swing_highs, swing_lows = IL.swing_highs_lows(df, swing_period=5)
    num_swing_highs = swing_highs.notna().sum()
    num_swing_lows = swing_lows.notna().sum()
    print(f"\n✓ Swing Points Detected:")
    print(f"  - Swing Highs: {num_swing_highs}")
    print(f"  - Swing Lows: {num_swing_lows}")
    
    # Test pullback detection
    pullback_days = IL.pullback_days(df)
    max_pullback = pullback_days.max()
    print(f"\n✓ Pullback Detection:")
    print(f"  - Max consecutive down days: {max_pullback}")
    
    # Test pullback depth
    pullback_depth = IL.pullback_depth(df, lookback=20)
    print(f"  - Current pullback depth: {pullback_depth.iloc[-1]:.2f}%")
    
    # Test Donchian channels
    dc_upper, dc_middle, dc_lower = IL.donchian_channels(df, 20)
    print(f"\n✓ Donchian Channels (20-day):")
    print(f"  - Upper: ${dc_upper.iloc[-1]:.2f}")
    print(f"  - Middle: ${dc_middle.iloc[-1]:.2f}")
    print(f"  - Lower: ${dc_lower.iloc[-1]:.2f}")
    
    # Test candlestick patterns
    hammers = IL.is_hammer(df).sum()
    engulfing = IL.is_bullish_engulfing(df).sum()
    doji = IL.is_doji(df).sum()
    reversals = IL.is_bullish_reversal(df).sum()
    print(f"\n✓ Candlestick Patterns:")
    print(f"  - Hammers: {hammers}")
    print(f"  - Bullish Engulfing: {engulfing}")
    print(f"  - Doji: {doji}")
    print(f"  - Total Bullish Reversals: {reversals}")
    
    # Test ADX trend strength
    adx, plus_di, minus_di = IL.adx(df, 14)
    print(f"\n✓ ADX Trend Strength:")
    print(f"  - ADX: {adx.iloc[-1]:.2f}")
    print(f"  - +DI: {plus_di.iloc[-1]:.2f}")
    print(f"  - -DI: {minus_di.iloc[-1]:.2f}")
    print(f"  - Trend: {'Strong' if adx.iloc[-1] > 25 else 'Weak'}")
    
    # Test trend and momentum scores
    trend_score = IL.trend_strength_score(df)
    momentum_score = IL.momentum_score(df)
    print(f"\n✓ Composite Scores:")
    print(f"  - Trend Score: {trend_score.iloc[-1]:.1f}/100")
    print(f"  - Momentum Score: {momentum_score.iloc[-1]:.2f}")
    
    # Test support/resistance
    sr_levels = IL.find_support_resistance(df, lookback=50)
    print(f"\n✓ Support/Resistance Levels:")
    print(f"  - Current Price: ${sr_levels['current_price']:.2f}")
    if sr_levels['support']:
        print(f"  - Support Levels: {[f'${x:.2f}' for x in sr_levels['support'][:3]]}")
    if sr_levels['resistance']:
        print(f"  - Resistance Levels: {[f'${x:.2f}' for x in sr_levels['resistance'][:3]]}")
    
    print("\n✅ PASS - Swing Trading Indicators")
    return True


def test_swing_strategies():
    """Test all swing trading strategies."""
    print("\n" + "="*60)
    print("TEST 2: Swing Trading Strategies")
    print("="*60)
    
    from src.algo.swing_strategies import (
        ShortTermTrendFollowingStrategy,
        ClassicSwingStrategy,
        MomentumRotationStrategy,
        ShortTermMeanReversionStrategy,
        list_swing_strategies,
    )
    
    df = generate_swing_data(200, trend="up")
    metadata = {'ticker': 'TEST', 'timeframe': '1d'}
    
    strategies = [
        ShortTermTrendFollowingStrategy(),
        ClassicSwingStrategy(),
        MomentumRotationStrategy(),
        ShortTermMeanReversionStrategy(),
    ]
    
    print(f"\nAvailable swing strategies: {list_swing_strategies()}")
    
    for strategy in strategies:
        print(f"\n--- {strategy.STRATEGY_ID} ---")
        
        # Analyze
        result = strategy.analyze(df.copy(), metadata)
        
        # Count signals
        entries = result['enter_long'].sum()
        exits = result['exit_long'].sum()
        
        # Get short signals if supported
        short_entries = result.get('enter_short', pd.Series([0])).sum() if strategy.can_short else 0
        short_exits = result.get('exit_short', pd.Series([0])).sum() if strategy.can_short else 0
        
        print(f"  Long entries: {entries}")
        print(f"  Long exits: {exits}")
        if strategy.can_short:
            print(f"  Short entries: {short_entries}")
            print(f"  Short exits: {short_exits}")
        
        # Get latest signal
        signal = strategy.get_latest_signal(df.copy(), metadata)
        print(f"  Latest signal: {signal['signal_type']}")
        
        # Check parameters
        params = strategy.get_parameters()
        print(f"  Stoploss: {params['stoploss']*100:.1f}%")
        print(f"  Trailing stop: {params['trailing_stop']}")
    
    print("\n✅ PASS - Swing Trading Strategies")
    return True


def test_earnings_strategies():
    """Test earnings/event trading strategies."""
    print("\n" + "="*60)
    print("TEST 3: Earnings & Event Strategies")
    print("="*60)
    
    from src.algo.earnings_strategies import (
        PreEarningsMomentumStrategy,
        PostEarningsDriftStrategy,
        EarningsBreakoutStrategy,
        list_earnings_strategies,
    )
    
    # Use data with earnings gap
    df = generate_earnings_gap_data(100)
    metadata = {'ticker': 'TEST', 'timeframe': '1d'}
    
    strategies = [
        PreEarningsMomentumStrategy(),
        PostEarningsDriftStrategy(),
        EarningsBreakoutStrategy(),
    ]
    
    print(f"\nAvailable earnings strategies: {list_earnings_strategies()}")
    
    for strategy in strategies:
        print(f"\n--- {strategy.STRATEGY_ID} ---")
        
        # Analyze
        result = strategy.analyze(df.copy(), metadata)
        
        # Count signals
        entries = result['enter_long'].sum()
        exits = result['exit_long'].sum()
        
        print(f"  Long entries: {entries}")
        print(f"  Long exits: {exits}")
        
        if strategy.can_short:
            short_entries = result.get('enter_short', pd.Series([0])).sum()
            short_exits = result.get('exit_short', pd.Series([0])).sum()
            print(f"  Short entries: {short_entries}")
            print(f"  Short exits: {short_exits}")
        
        # Get parameters
        params = strategy.get_parameters()
        print(f"  Stoploss: {params['stoploss']*100:.1f}%")
        print(f"  ROI targets: {params['minimal_roi']}")
    
    print("\n✅ PASS - Earnings & Event Strategies")
    return True


def test_position_manager():
    """Test position sizing and risk management."""
    print("\n" + "="*60)
    print("TEST 4: Position Manager & Risk Management")
    print("="*60)
    
    from src.algo.position_manager import (
        PositionManager,
        RiskParameters,
        Position,
        PositionStatus,
        calculate_risk_reward,
        calculate_kelly_fraction,
        suggested_risk_parameters,
    )
    
    # Create position manager with $100,000 account
    params = RiskParameters(
        account_size=100000,
        risk_per_trade_pct=1.0,
        max_open_positions=5,
        max_sector_exposure_pct=30.0,
    )
    
    pm = PositionManager(params)
    
    print(f"\n✓ Account Setup:")
    print(f"  - Account Size: ${params.account_size:,.0f}")
    print(f"  - Risk per Trade: {params.risk_per_trade_pct}%")
    print(f"  - Max Positions: {params.max_open_positions}")
    
    # Test position sizing
    print("\n✓ Position Sizing Test:")
    
    sizing = pm.calculate_position_size(
        ticker="AAPL",
        entry_price=180.00,
        stop_loss_price=175.00,  # $5 risk per share
        sector="Technology"
    )
    
    print(f"  - Entry: $180.00, Stop: $175.00")
    print(f"  - Risk per share: $5.00")
    print(f"  - Calculated shares: {sizing['shares']}")
    print(f"  - Position value: ${sizing['position_value']:,.0f}")
    print(f"  - Risk amount: ${sizing['risk_amount']:.0f}")
    print(f"  - Risk %: {sizing['risk_pct']:.2f}%")
    print(f"  - Target price (2R): ${sizing['target_price']:.2f}")
    print(f"  - % of account: {sizing['pct_of_account']:.1f}%")
    
    # Test ATR-based sizing
    print("\n✓ ATR-Based Position Sizing:")
    atr_sizing = pm.calculate_atr_based_size(
        ticker="MSFT",
        entry_price=400.00,
        atr=8.00,  # $8 ATR
        atr_multiplier=2.0,
        sector="Technology"
    )
    print(f"  - Entry: $400.00, ATR: $8.00, Multiplier: 2.0x")
    print(f"  - Stop: ${400 - 8*2:.2f}")
    print(f"  - Shares: {atr_sizing['shares']}")
    print(f"  - Risk %: {atr_sizing['risk_pct']:.2f}%")
    
    # Test opening positions
    print("\n✓ Opening Positions:")
    
    pos1 = pm.open_position(
        ticker="AAPL",
        strategy_id="swing_trading",
        entry_price=180.00,
        shares=sizing['shares'],
        stop_loss_price=175.00,
        take_profit_price=190.00,
        max_hold_days=20,
        sector="Technology"
    )
    print(f"  - Opened AAPL: {pos1.shares} shares @ ${pos1.entry_price}")
    
    pos2 = pm.open_position(
        ticker="NVDA",
        strategy_id="momentum",
        entry_price=450.00,
        shares=50,
        stop_loss_price=435.00,
        take_profit_price=480.00,
        sector="Technology"
    )
    print(f"  - Opened NVDA: {pos2.shares} shares @ ${pos2.entry_price}")
    
    # Test exposure report
    print("\n✓ Exposure Report:")
    report = pm.get_exposure_report()
    print(f"  - Open Positions: {report['open_positions']}/{report['max_positions']}")
    print(f"  - Total Exposure: ${report['total_exposure']:,.0f} ({report['total_exposure_pct']:.1f}%)")
    print(f"  - Cash Available: ${report['cash_available']:,.0f}")
    print(f"  - Sector Exposure: {report['sector_exposure']}")
    
    # Test position updates
    print("\n✓ Position Updates:")
    positions_to_close = pm.update_all_positions(
        prices={'AAPL': 188.00, 'NVDA': 465.00},
        current_date=datetime.now()
    )
    
    # Get updated positions
    summary = pm.get_open_positions_summary()
    for pos in summary:
        print(f"  - {pos['ticker']}: ${pos['entry_price']:.2f} → ${pos['current_price']:.2f}")
        print(f"    P/L: ${pos['unrealized_pnl']:.2f} ({pos['unrealized_pnl_pct']:.2f}%)")
    
    # Test closing position
    print("\n✓ Closing Position:")
    closed = pm.close_position("AAPL", exit_price=189.00, reason="take_profit")
    print(f"  - Closed AAPL @ ${closed.exit_price}")
    print(f"  - Realized P/L: ${closed.realized_pnl:.2f} ({closed.realized_pnl_pct:.2f}%)")
    print(f"  - Status: {closed.status.value}")
    
    # Test performance stats
    print("\n✓ Performance Stats:")
    stats = pm.get_performance_stats()
    print(f"  - Total Trades: {stats['total_trades']}")
    print(f"  - Win Rate: {stats['win_rate']:.1f}%")
    print(f"  - Avg Win: ${stats['avg_win']:.2f}")
    print(f"  - Total P/L: ${stats['total_pnl']:.2f}")
    
    # Test helper functions
    print("\n✓ Risk/Reward Calculation:")
    rr = calculate_risk_reward(entry_price=100, stop_loss=95, target=115)
    print(f"  - Entry: $100, Stop: $95, Target: $115")
    print(f"  - Risk/Reward: 1:{rr:.1f}")
    
    print("\n✓ Kelly Criterion:")
    kelly = calculate_kelly_fraction(win_rate=55, avg_win=200, avg_loss=100)
    print(f"  - Win Rate: 55%, Avg Win: $200, Avg Loss: $100")
    print(f"  - Half Kelly: {kelly*100:.1f}%")
    
    # Test suggested parameters
    print("\n✓ Suggested Risk Parameters:")
    for style in ['conservative', 'moderate', 'aggressive']:
        suggested = suggested_risk_parameters(100000, style)
        print(f"  {style.capitalize()}: {suggested.risk_per_trade_pct}% risk, {suggested.max_open_positions} positions")
    
    print("\n✅ PASS - Position Manager & Risk Management")
    return True


def test_strategy_integration():
    """Test full strategy integration with position manager."""
    print("\n" + "="*60)
    print("TEST 5: Strategy + Position Manager Integration")
    print("="*60)
    
    from src.algo import (
        get_strategy,
        list_all_strategies,
        PositionManager,
        RiskParameters,
    )
    
    # List all available strategies
    all_strategies = list_all_strategies()
    print(f"\n✓ All Available Strategies by Category:")
    for category, strategies in all_strategies.items():
        print(f"  {category}: {strategies}")
    
    # Create position manager
    pm = PositionManager(RiskParameters(account_size=100000))
    
    # Generate data
    df = generate_swing_data(200, trend="up")
    metadata = {'ticker': 'AAPL', 'timeframe': '1d'}
    
    # Get strategy and analyze
    strategy = get_strategy('classic_swing')
    result = strategy.analyze(df.copy(), metadata)
    
    # Find entry signals
    entries = result[result['enter_long'] == 1]
    print(f"\n✓ Found {len(entries)} entry signals from {strategy.STRATEGY_ID}")
    
    if len(entries) > 0:
        # Take first entry
        entry_row = entries.iloc[0]
        entry_price = entry_row['close']
        atr = entry_row.get('atr', 2.0)
        
        # Calculate position size
        sizing = pm.calculate_atr_based_size(
            ticker='AAPL',
            entry_price=entry_price,
            atr=atr,
            atr_multiplier=2.0,
            sector='Technology'
        )
        
        print(f"\n✓ Position Sizing for Entry:")
        print(f"  - Entry Price: ${entry_price:.2f}")
        print(f"  - ATR: ${atr:.2f}")
        print(f"  - Position Size: {sizing['shares']} shares")
        print(f"  - Stop Loss: ${sizing['stop_loss_price']:.2f}")
        print(f"  - Target (2R): ${sizing['target_price']:.2f}")
        print(f"  - Risk Amount: ${sizing['risk_amount']:.0f}")
        
        # Open position
        if sizing['can_trade']:
            pos = pm.open_position(
                ticker='AAPL',
                strategy_id=strategy.STRATEGY_ID,
                entry_price=entry_price,
                shares=sizing['shares'],
                stop_loss_price=sizing['stop_loss_price'],
                take_profit_price=sizing['target_price'],
                atr=atr,
                max_hold_days=strategy.minimal_roi.get('0', 20),
                sector='Technology',
                entry_reason='Swing entry signal'
            )
            print(f"\n✓ Position Opened:")
            print(f"  - Position ID: {pos.position_id}")
            print(f"  - Status: {pos.status.value}")
    
    print("\n✅ PASS - Strategy + Position Manager Integration")
    return True


def test_all_exports():
    """Test that all exports work correctly."""
    print("\n" + "="*60)
    print("TEST 6: Module Exports")
    print("="*60)
    
    from src.algo import (
        # Core
        IStrategy,
        StrategyConfig,
        StrategyMode,
        TimeFrame,
        StrategyManager,
        IndicatorLibrary,
        
        # Strategies
        VCPStrategy,
        MomentumBreakoutStrategy,
        MomentumRotationStrategy,
        MeanReversionStrategy,
        ShortTermMeanReversionStrategy,
        TrendFollowingStrategy,
        ShortTermTrendFollowingStrategy,
        ClassicSwingStrategy,
        PreEarningsMomentumStrategy,
        PostEarningsDriftStrategy,
        EarningsBreakoutStrategy,
        
        # Swing helpers
        SwingStyle,
        SwingTradeConfig,
        SWING_STRATEGIES,
        get_swing_strategy,
        list_swing_strategies,
        
        # Earnings helpers
        EarningsEvent,
        EarningsReaction,
        EarningsCalendar,
        EARNINGS_STRATEGIES,
        get_earnings_strategy,
        list_earnings_strategies,
        
        # Position management
        PositionManager,
        Position,
        PositionStatus,
        RiskParameters,
        calculate_risk_reward,
        calculate_kelly_fraction,
        suggested_risk_parameters,
        
        # Master helpers
        ALL_STRATEGIES,
        get_strategy,
        list_all_strategies,
    )
    
    print("\n✓ Core classes imported successfully")
    print(f"  - IStrategy: {IStrategy}")
    print(f"  - StrategyMode options: {[m.value for m in StrategyMode]}")
    print(f"  - TimeFrame options: {[t.value for t in TimeFrame]}")
    
    print("\n✓ All 11 strategies imported successfully")
    strategies_list = [
        VCPStrategy, MomentumBreakoutStrategy, MomentumRotationStrategy,
        MeanReversionStrategy, ShortTermMeanReversionStrategy,
        TrendFollowingStrategy, ShortTermTrendFollowingStrategy,
        ClassicSwingStrategy, PreEarningsMomentumStrategy,
        PostEarningsDriftStrategy, EarningsBreakoutStrategy,
    ]
    for s in strategies_list:
        print(f"  - {s.__name__}: {s().STRATEGY_ID}")
    
    print("\n✓ Position management imported successfully")
    print(f"  - PositionStatus options: {[s.value for s in PositionStatus]}")
    print(f"  - SwingStyle options: {[s.value for s in SwingStyle]}")
    
    print("\n✓ Strategy helpers work correctly")
    print(f"  - ALL_STRATEGIES: {len(ALL_STRATEGIES)} strategies")
    print(f"  - SWING_STRATEGIES: {list(SWING_STRATEGIES.keys())}")
    print(f"  - EARNINGS_STRATEGIES: {list(EARNINGS_STRATEGIES.keys())}")
    
    print("\n✅ PASS - Module Exports")
    return True


def test_indicator_additions():
    """Test all new indicator additions."""
    print("\n" + "="*60)
    print("TEST 7: Complete Indicator Coverage")
    print("="*60)
    
    from src.algo.indicators import IndicatorLibrary as IL
    
    df = generate_swing_data(200)
    
    # Test all swing indicators
    swing_indicators = {
        'Fibonacci Retracement': lambda: IL.fibonacci_retracement(df, 50),
        'Swing Highs/Lows': lambda: IL.swing_highs_lows(df, 5),
        'Pullback Days': lambda: IL.pullback_days(df),
        'Pullback Depth': lambda: IL.pullback_depth(df, 20),
        'Donchian Channels': lambda: IL.donchian_channels(df, 20),
        'Hammer Pattern': lambda: IL.is_hammer(df),
        'Bullish Engulfing': lambda: IL.is_bullish_engulfing(df),
        'Doji Pattern': lambda: IL.is_doji(df),
        'Morning Star': lambda: IL.is_morning_star(df),
        'Bullish Reversal': lambda: IL.is_bullish_reversal(df),
        'ADX': lambda: IL.adx(df, 14),
        'Trend Strength Score': lambda: IL.trend_strength_score(df),
        'Momentum Score': lambda: IL.momentum_score(df),
        'Support/Resistance': lambda: IL.find_support_resistance(df, 50),
        'Volume Trend': lambda: IL.volume_trend(df, 20),
        'Volume Breakout': lambda: IL.volume_breakout(df, 2.0),
    }
    
    print("\n✓ Testing all swing trading indicators:")
    all_passed = True
    for name, func in swing_indicators.items():
        try:
            result = func()
            print(f"  ✓ {name}")
        except Exception as e:
            print(f"  ✗ {name}: {e}")
            all_passed = False
    
    # Test existing indicators still work
    existing_indicators = {
        'SMA': lambda: IL.sma(df['close'], 20),
        'EMA': lambda: IL.ema(df['close'], 20),
        'RSI': lambda: IL.rsi(df['close'], 14),
        'MACD': lambda: IL.macd(df['close']),
        'Bollinger Bands': lambda: IL.bollinger_bands(df['close'], 20),
        'ATR': lambda: IL.atr(df, 14),
        'Stochastic': lambda: IL.stochastic(df, 14, 3),
        'OBV': lambda: IL.obv(df),
        'VWAP': lambda: IL.vwap(df),
        'VCP Setup': lambda: IL.is_vcp_setup(df),
    }
    
    print("\n✓ Testing existing indicators:")
    for name, func in existing_indicators.items():
        try:
            result = func()
            print(f"  ✓ {name}")
        except Exception as e:
            print(f"  ✗ {name}: {e}")
            all_passed = False
    
    if all_passed:
        print("\n✅ PASS - Complete Indicator Coverage")
    else:
        print("\n❌ FAIL - Some indicators failed")
    
    return all_passed


def run_all_tests():
    """Run all tests."""
    print("\n" + "="*70)
    print(" SWING TRADING FRAMEWORK TEST SUITE")
    print("="*70)
    print(f" Date: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print("="*70)
    
    tests = [
        ("Swing Trading Indicators", test_swing_indicators),
        ("Swing Trading Strategies", test_swing_strategies),
        ("Earnings & Event Strategies", test_earnings_strategies),
        ("Position Manager", test_position_manager),
        ("Strategy Integration", test_strategy_integration),
        ("Module Exports", test_all_exports),
        ("Complete Indicator Coverage", test_indicator_additions),
    ]
    
    results = []
    for name, test_func in tests:
        try:
            result = test_func()
            results.append((name, result))
        except Exception as e:
            print(f"\n❌ FAIL - {name}: {e}")
            import traceback
            traceback.print_exc()
            results.append((name, False))
    
    # Summary
    print("\n" + "="*70)
    print(" TEST SUMMARY")
    print("="*70)
    
    passed = sum(1 for _, r in results if r)
    total = len(results)
    
    for name, result in results:
        status = "✅ PASS" if result else "❌ FAIL"
        print(f"  {status} - {name}")
    
    print(f"\nTotal: {passed}/{total} tests passed")
    
    if passed == total:
        print("\n🎉 All tests passed! The swing trading framework is ready.")
        print("\n" + "-"*70)
        print("AVAILABLE STRATEGIES:")
        print("-"*70)
        print("""
SHORT-TERM SWING TRADING (2 days - 8 weeks):
  1. short_term_trend_following - Ride trends for 2-8 weeks
  2. classic_swing - Support to resistance swings (2-4 weeks)
  3. momentum_rotation - Weekly rotation to strongest (1-8 weeks)
  4. short_term_mean_reversion - Oversold bounces (days to 2-3 weeks)

EARNINGS & EVENT-DRIVEN:
  5. pre_earnings_momentum - Buy before earnings run-up
  6. post_earnings_drift - Trade post-earnings drift (PEAD)
  7. earnings_breakout - Trade VCP patterns after earnings

POSITION MANAGEMENT:
  - Risk-based sizing (0.25-1% per trade)
  - ATR-based stops
  - Trailing stops with activation levels
  - Sector exposure limits
  - Drawdown monitoring
  - Time-based exits
        """)
    else:
        print("\n⚠️ Some tests failed. Please check the output above.")
    
    return passed == total


if __name__ == "__main__":
    success = run_all_tests()
    sys.exit(0 if success else 1)
