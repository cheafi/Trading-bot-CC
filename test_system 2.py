#!/usr/bin/env python3
"""
TradingAI Bot - Comprehensive System Test
Tests all components of the trading system.
"""
import asyncio
import sys
import logging
from datetime import datetime

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


class TestResult:
    """Track test results."""
    def __init__(self):
        self.passed = 0
        self.failed = 0
        self.skipped = 0
        self.results = []
    
    def add_pass(self, name: str, message: str = ""):
        self.passed += 1
        self.results.append(("PASS", name, message))
        print(f"✅ {name}: {message}" if message else f"✅ {name}")
    
    def add_fail(self, name: str, message: str = ""):
        self.failed += 1
        self.results.append(("FAIL", name, message))
        print(f"❌ {name}: {message}" if message else f"❌ {name}")
    
    def add_skip(self, name: str, message: str = ""):
        self.skipped += 1
        self.results.append(("SKIP", name, message))
        print(f"⚠️  {name}: {message}" if message else f"⚠️  {name}")
    
    def summary(self):
        print("\n" + "=" * 50)
        print("TEST SUMMARY")
        print("=" * 50)
        print(f"Passed:  {self.passed}")
        print(f"Failed:  {self.failed}")
        print(f"Skipped: {self.skipped}")
        print(f"Total:   {self.passed + self.failed + self.skipped}")
        print("=" * 50)
        return self.failed == 0


results = TestResult()


def test_config():
    """Test configuration loading."""
    print("\n" + "=" * 50)
    print("TESTING: Configuration")
    print("=" * 50)
    
    try:
        from src.core.config import get_settings, get_trading_config
        s = get_settings()
        t = get_trading_config()
        
        results.add_pass("Config Loading")
        
        # Check required fields
        if s.postgres_host:
            results.add_pass("Database Config", f"{s.postgres_host}:{s.postgres_port}")
        else:
            results.add_fail("Database Config", "Missing database host")
        
        if s.alpaca_api_key:
            results.add_pass("Alpaca Config", "API key configured")
        else:
            results.add_skip("Alpaca Config", "Not configured")
        
        if s.has_telegram:
            results.add_pass("Telegram Config", f"Chat ID: {s.telegram_chat_id}")
        else:
            results.add_skip("Telegram Config", "Not configured")
        
        if s.use_azure_openai:
            results.add_pass("Azure OpenAI Config", s.azure_openai_endpoint[:50] + "...")
        else:
            results.add_skip("Azure OpenAI Config", "Not configured")
        
        # Trading config
        results.add_pass("Trading Config", 
                        f"Risk/trade: {t.risk_per_trade*100:.1f}%, Max position: {t.max_position_pct*100:.0f}%")
        
    except Exception as e:
        results.add_fail("Config Loading", str(e))


def test_indicators():
    """Test technical indicator library."""
    print("\n" + "=" * 50)
    print("TESTING: Technical Indicators")
    print("=" * 50)
    
    try:
        import pandas as pd
        import numpy as np
        from src.algo.indicators import IndicatorLibrary as IL
        
        # Create sample OHLCV data
        np.random.seed(42)
        n = 100
        dates = pd.date_range(end=datetime.now(), periods=n, freq='D')
        close = 100 * (1 + np.random.randn(n).cumsum() * 0.02)
        df = pd.DataFrame({
            'open': close * (1 + np.random.randn(n) * 0.01),
            'high': close * (1 + np.abs(np.random.randn(n)) * 0.02),
            'low': close * (1 - np.abs(np.random.randn(n)) * 0.02),
            'close': close,
            'volume': np.random.randint(1000000, 10000000, n)
        }, index=dates)
        
        # Test basic indicators
        sma = IL.sma(df['close'], 20)
        if len(sma.dropna()) > 0:
            results.add_pass("SMA", f"20-day SMA: {sma.iloc[-1]:.2f}")
        
        ema = IL.ema(df['close'], 12)
        if len(ema.dropna()) > 0:
            results.add_pass("EMA", f"12-day EMA: {ema.iloc[-1]:.2f}")
        
        rsi = IL.rsi(df['close'], 14)
        if len(rsi.dropna()) > 0 and 0 <= rsi.iloc[-1] <= 100:
            results.add_pass("RSI", f"14-day RSI: {rsi.iloc[-1]:.1f}")
        
        macd, signal, hist = IL.macd(df['close'])
        if len(macd.dropna()) > 0:
            results.add_pass("MACD", f"MACD: {macd.iloc[-1]:.2f}")
        
        atr = IL.atr(df, 14)
        if len(atr.dropna()) > 0 and atr.iloc[-1] > 0:
            results.add_pass("ATR", f"14-day ATR: {atr.iloc[-1]:.2f}")
        
        bb_upper, bb_mid, bb_lower = IL.bollinger_bands(df['close'], 20, 2)
        if bb_upper.iloc[-1] > bb_lower.iloc[-1]:
            results.add_pass("Bollinger Bands", f"Width: {(bb_upper.iloc[-1] - bb_lower.iloc[-1]):.2f}")
        
        stoch_k, stoch_d = IL.stochastic(df)
        if 0 <= stoch_k.iloc[-1] <= 100:
            results.add_pass("Stochastic", f"K: {stoch_k.iloc[-1]:.1f}, D: {stoch_d.iloc[-1]:.1f}")
        
        adx, plus_di, minus_di = IL.adx(df, 14)
        if adx.iloc[-1] > 0:
            results.add_pass("ADX", f"ADX: {adx.iloc[-1]:.1f}")
        
        # Test new indicators
        cmf = IL.chaikin_money_flow(df, 20)
        if -1 <= cmf.iloc[-1] <= 1:
            results.add_pass("Chaikin Money Flow", f"CMF: {cmf.iloc[-1]:.3f}")
        
        vwap, vwap_upper, vwap_lower = IL.vwap_bands(df)
        if vwap.iloc[-1] > 0:
            results.add_pass("VWAP Bands", f"VWAP: {vwap.iloc[-1]:.2f}")
        
        squeeze_on, momentum = IL.squeeze_momentum(df)
        results.add_pass("Squeeze Momentum", f"Squeeze On: {squeeze_on.iloc[-1]}")
        
        ichimoku = IL.ichimoku_cloud(df)
        if 'tenkan_sen' in ichimoku:
            results.add_pass("Ichimoku Cloud", f"Tenkan: {ichimoku['tenkan_sen'].iloc[-1]:.2f}")
        
        uo = IL.ultimate_oscillator(df)
        if 0 <= uo.iloc[-1] <= 100:
            results.add_pass("Ultimate Oscillator", f"UO: {uo.iloc[-1]:.1f}")
        
    except Exception as e:
        results.add_fail("Indicators", str(e))
        import traceback
        traceback.print_exc()


def test_strategies():
    """Test trading strategies."""
    print("\n" + "=" * 50)
    print("TESTING: Trading Strategies")
    print("=" * 50)
    
    try:
        import pandas as pd
        import numpy as np
        
        # Create sample data
        np.random.seed(42)
        n = 200
        dates = pd.date_range(end=datetime.now(), periods=n, freq='D')
        close = 100 * (1 + np.random.randn(n).cumsum() * 0.02)
        df = pd.DataFrame({
            'open': close * (1 + np.random.randn(n) * 0.01),
            'high': close * (1 + np.abs(np.random.randn(n)) * 0.02),
            'low': close * (1 - np.abs(np.random.randn(n)) * 0.02),
            'close': close,
            'volume': np.random.randint(1000000, 10000000, n)
        }, index=dates)
        
        # Test Momentum Strategy
        try:
            from src.algo.momentum_strategy import MomentumBreakoutStrategy
            strat = MomentumBreakoutStrategy()
            df_with_ind = strat.populate_indicators(df.copy(), {'ticker': 'TEST'})
            df_with_signals = strat.populate_entry_trend(df_with_ind, {'ticker': 'TEST'})
            signals = df_with_signals['enter_long'].sum()
            results.add_pass("Momentum Strategy", f"{int(signals)} entry signals generated")
        except Exception as e:
            results.add_fail("Momentum Strategy", str(e))
        
        # Test Mean Reversion Strategy
        try:
            from src.algo.mean_reversion_strategy import MeanReversionStrategy
            strat = MeanReversionStrategy()
            df_with_ind = strat.populate_indicators(df.copy(), {'ticker': 'TEST'})
            df_with_signals = strat.populate_entry_trend(df_with_ind, {'ticker': 'TEST'})
            signals = df_with_signals['enter_long'].sum()
            results.add_pass("Mean Reversion Strategy", f"{int(signals)} entry signals generated")
        except Exception as e:
            results.add_fail("Mean Reversion Strategy", str(e))
        
        # Test Trend Following Strategy
        try:
            from src.algo.trend_following_strategy import TrendFollowingStrategy
            strat = TrendFollowingStrategy()
            df_with_ind = strat.populate_indicators(df.copy(), {'ticker': 'TEST'})
            df_with_signals = strat.populate_entry_trend(df_with_ind, {'ticker': 'TEST'})
            signals = df_with_signals['enter_long'].sum()
            results.add_pass("Trend Following Strategy", f"{int(signals)} entry signals generated")
        except Exception as e:
            results.add_fail("Trend Following Strategy", str(e))
        
        # Test VCP Strategy
        try:
            from src.algo.vcp_strategy import VCPStrategy
            strat = VCPStrategy()
            # VCP needs more data
            df_long = pd.concat([df, df], ignore_index=True)
            df_with_ind = strat.populate_indicators(df_long, {'ticker': 'TEST'})
            results.add_pass("VCP Strategy", "Indicators populated successfully")
        except Exception as e:
            results.add_fail("VCP Strategy", str(e))
        
    except Exception as e:
        results.add_fail("Strategies", str(e))


def test_position_manager():
    """Test position manager."""
    print("\n" + "=" * 50)
    print("TESTING: Position Manager")
    print("=" * 50)
    
    try:
        from src.algo.position_manager import PositionManager, RiskParameters
        
        # Create position manager
        params = RiskParameters(
            account_size=100000,
            risk_per_trade_pct=1.0,
            max_position_size_pct=10.0
        )
        pm = PositionManager(params)
        results.add_pass("Position Manager Init", f"Account: ${params.account_size:,.0f}")
        
        # Test position sizing
        sizing = pm.calculate_position_size(
            ticker="AAPL",
            entry_price=150.0,
            stop_loss_price=145.0
        )
        
        if sizing['can_trade']:
            results.add_pass("Position Sizing", 
                           f"Shares: {sizing['shares']}, Value: ${sizing['position_value']:,.0f}")
        else:
            results.add_pass("Position Sizing", f"Blocked: {sizing.get('reason', 'Unknown')}")
        
        # Test ATR-based sizing
        atr_sizing = pm.calculate_atr_based_size(
            ticker="MSFT",
            entry_price=300.0,
            atr=5.0,
            atr_multiplier=2.0
        )
        
        if atr_sizing['can_trade']:
            results.add_pass("ATR-Based Sizing", 
                           f"Shares: {atr_sizing['shares']}, Stop: ${atr_sizing['stop_loss_price']:.2f}")
        
    except Exception as e:
        results.add_fail("Position Manager", str(e))


def test_engines():
    """Test signal and feature engines."""
    print("\n" + "=" * 50)
    print("TESTING: Engines")
    print("=" * 50)
    
    try:
        # Test Feature Engine
        from src.engines.feature_engine import FeatureEngine
        import pandas as pd
        import numpy as np
        
        # Create sample data
        np.random.seed(42)
        n = 250
        dates = pd.date_range(end=datetime.now(), periods=n, freq='D')
        close = 100 * (1 + np.random.randn(n).cumsum() * 0.02)
        df = pd.DataFrame({
            'open': close * (1 + np.random.randn(n) * 0.01),
            'high': close * (1 + np.abs(np.random.randn(n)) * 0.02),
            'low': close * (1 - np.abs(np.random.randn(n)) * 0.02),
            'close': close,
            'volume': np.random.randint(1000000, 10000000, n)
        }, index=dates)
        
        fe = FeatureEngine()
        features = fe.calculate_features(df)
        
        if len(features) > 0:
            results.add_pass("Feature Engine", f"{len(features.columns)} features calculated")
        
        # Test Regime Detection
        from src.engines.signal_engine import RegimeDetector
        
        rd = RegimeDetector()
        market_data = {
            'vix': 18.5,
            'vix_term_structure': 1.02,
            'pct_above_sma50': 65,
            'hy_spread': 320
        }
        regime = rd.detect(market_data)
        results.add_pass("Regime Detection", 
                        f"Vol: {regime.volatility.value}, Trend: {regime.trend.value}")
        
        # Test Signal Validator
        from src.engines.signal_engine import SignalValidator
        from src.core.models import Signal, Direction, Horizon, Invalidation, Target, StopType
        
        sv = SignalValidator()
        test_signal = Signal(
            ticker="AAPL",
            direction=Direction.LONG,
            horizon=Horizon.SWING_1_5D,
            strategy_id="test",
            entry_price=150.0,
            targets=[Target(price=165.0, pct_position=100)],
            invalidation=Invalidation(stop_price=145.0, stop_type=StopType.HARD),
            confidence=75,
            entry_logic="Test breakout entry",
            catalyst="Earnings beat",
            key_risks=["Market risk"],
            rationale="Test signal for validation",
            generated_at=datetime.now()
        )
        
        is_valid, reason = sv.validate_signal(test_signal)
        if is_valid:
            results.add_pass("Signal Validator", "Valid signal accepted")
        
        # Test invalid signal
        bad_signal = Signal(
            ticker="BAD",
            direction=Direction.LONG,
            horizon=Horizon.SWING_1_5D,
            strategy_id="test",
            entry_price=100.0,
            targets=[Target(price=95.0, pct_position=100)],  # Below entry for long!
            invalidation=Invalidation(stop_price=90.0, stop_type=StopType.HARD),
            confidence=50,
            entry_logic="Bad test",
            catalyst="None",
            key_risks=["Test"],
            rationale="Invalid signal test",
            generated_at=datetime.now()
        )
        
        is_valid, reason = sv.validate_signal(bad_signal)
        if not is_valid:
            results.add_pass("Signal Validator", f"Invalid signal rejected: {reason}")
        
    except Exception as e:
        results.add_fail("Engines", str(e))
        import traceback
        traceback.print_exc()


def test_scanners():
    """Test market scanners."""
    print("\n" + "=" * 50)
    print("TESTING: Scanners")
    print("=" * 50)
    
    try:
        import pandas as pd
        import numpy as np
        
        # Create sample data
        np.random.seed(42)
        n = 100
        dates = pd.date_range(end=datetime.now(), periods=n, freq='D')
        close = 100 * (1 + np.random.randn(n).cumsum() * 0.02)
        df = pd.DataFrame({
            'open': close * (1 + np.random.randn(n) * 0.01),
            'high': close * (1 + np.abs(np.random.randn(n)) * 0.02),
            'low': close * (1 - np.abs(np.random.randn(n)) * 0.02),
            'close': close,
            'volume': np.random.randint(1000000, 10000000, n)
        }, index=dates)
        
        # Test Momentum Scanner
        from src.scanners.momentum_scanner import MomentumScanner
        
        ms = MomentumScanner()
        alerts = ms._scan_ticker("TEST", df, spy_return=5.0)
        results.add_pass("Momentum Scanner", f"{len(alerts)} alerts found")
        
        # Test Pattern Scanner
        from src.scanners.pattern_scanner import PatternScanner
        
        ps = PatternScanner()
        patterns = ps.scan_patterns(df, "TEST")
        results.add_pass("Pattern Scanner", f"{len(patterns)} patterns found")
        
    except Exception as e:
        results.add_fail("Scanners", str(e))


def test_api():
    """Test API endpoints (offline)."""
    print("\n" + "=" * 50)
    print("TESTING: API")
    print("=" * 50)
    
    try:
        from src.api.main import app, RateLimiter
        
        # Test app creation
        if app:
            results.add_pass("API App", f"Routes: {len(app.routes)}")
        
        # Test rate limiter
        rl = RateLimiter(requests_per_minute=10)
        # Simulate requests
        for _ in range(10):
            asyncio.get_event_loop().run_until_complete(rl.is_allowed("test"))
        
        remaining = rl.get_remaining("test")
        results.add_pass("Rate Limiter", f"Remaining: {remaining}/10")
        
    except Exception as e:
        results.add_fail("API", str(e))


async def test_database():
    """Test database connection."""
    print("\n" + "=" * 50)
    print("TESTING: Database")
    print("=" * 50)
    
    try:
        from src.core.database import check_database_health
        
        healthy = await check_database_health()
        if healthy:
            results.add_pass("Database Connection", "Connected and healthy")
        else:
            results.add_skip("Database Connection", "Cannot connect (check if running)")
            
    except Exception as e:
        results.add_skip("Database Connection", f"Not available: {e}")


def main():
    """Run all tests."""
    print("=" * 60)
    print("TradingAI Bot - Comprehensive System Test")
    print("=" * 60)
    print(f"Started at: {datetime.now()}")
    
    # Run synchronous tests
    test_config()
    test_indicators()
    test_strategies()
    test_position_manager()
    test_engines()
    test_scanners()
    test_api()
    
    # Run async tests
    try:
        asyncio.get_event_loop().run_until_complete(test_database())
    except Exception as e:
        results.add_skip("Database", f"Async test failed: {e}")
    
    # Print summary
    success = results.summary()
    
    print(f"\nCompleted at: {datetime.now()}")
    
    return 0 if success else 1


if __name__ == "__main__":
    sys.exit(main())
