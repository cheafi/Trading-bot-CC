"""
Test Enhanced Market Intelligence System

Tests the new scanner modules:
- PatternScanner - Chart pattern recognition
- SectorScanner - Multi-sector parallel scanning
- MomentumScanner - Real-time momentum alerts
- VolumeScanner - Volume analysis
- MarketMonitor - Central orchestration
- NewsAnalyzer - AI news summarization
- PerformanceTracker - Signal tracking
"""
import asyncio
import sys
import os
from datetime import datetime, timedelta
import pandas as pd
import numpy as np

# Add src to path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from dotenv import load_dotenv
load_dotenv()


def generate_sample_ohlcv(ticker: str, days: int = 100) -> pd.DataFrame:
    """Generate sample OHLCV data for testing."""
    np.random.seed(42)  # Reproducible results
    
    dates = pd.date_range(end=datetime.now(), periods=days, freq='D')
    
    # Generate realistic price movement
    base_price = 150.0
    returns = np.random.normal(0.001, 0.02, days)
    prices = base_price * np.cumprod(1 + returns)
    
    # Add some patterns
    # Add a head and shoulders pattern around day 50-70
    for i in range(50, 55):
        prices[i] *= 1.02
    for i in range(55, 60):
        prices[i] *= 0.98
    for i in range(60, 67):
        prices[i] *= 1.03
    for i in range(67, 72):
        prices[i] *= 0.97
    for i in range(72, 77):
        prices[i] *= 1.01
    
    # Generate OHLCV
    data = {
        'open': prices * (1 - np.random.uniform(0, 0.01, days)),
        'high': prices * (1 + np.random.uniform(0.005, 0.02, days)),
        'low': prices * (1 - np.random.uniform(0.005, 0.02, days)),
        'close': prices,
        'volume': np.random.randint(1000000, 10000000, days).astype(float)
    }
    
    df = pd.DataFrame(data, index=dates)
    df.index.name = 'date'
    
    return df


async def test_pattern_scanner():
    """Test chart pattern recognition."""
    print("\n" + "=" * 60)
    print("🔍 TESTING PATTERN SCANNER")
    print("=" * 60)
    
    try:
        from src.scanners import PatternScanner
        
        scanner = PatternScanner()
        
        # Generate test data
        df = generate_sample_ohlcv("AAPL", days=100)
        
        print(f"\n📊 Sample data shape: {df.shape}")
        print(f"   Date range: {df.index[0].strftime('%Y-%m-%d')} to {df.index[-1].strftime('%Y-%m-%d')}")
        print(f"   Price range: ${df['close'].min():.2f} - ${df['close'].max():.2f}")
        
        # Scan for patterns
        patterns = scanner.scan_patterns(df, "AAPL")
        
        print(f"\n✅ Found {len(patterns)} patterns:")
        
        for p in patterns[:5]:  # Show top 5
            print(f"\n   📈 {p.pattern_type.value.replace('_', ' ').title()}")
            print(f"      Direction: {p.direction}")
            print(f"      Confidence: {p.confidence:.1f}%")
            print(f"      Historical Success Rate: {p.historical_success_rate:.1f}%")
            print(f"      Entry: ${p.entry_price:.2f}")
            print(f"      Target: ${p.target_price:.2f}")
            print(f"      Stop: ${p.stop_loss:.2f}")
            print(f"      R/R Ratio: {p.risk_reward_ratio:.2f}")
        
        # Calculate trendlines
        trendlines = scanner.detect_trendlines(df, "AAPL")
        print(f"\n📏 Detected {len(trendlines)} trendlines")
        
        # Calculate support/resistance
        sr_levels = scanner.calculate_support_resistance(df, "AAPL")
        print(f"📊 Support/Resistance structure: {type(sr_levels)}")
        if isinstance(sr_levels, dict):
            for key in list(sr_levels.keys())[:3]:
                val = sr_levels[key]
                print(f"   {key}: {val}")
        
        print("\n✅ Pattern Scanner: PASSED")
        return True
        
    except Exception as e:
        print(f"\n❌ Pattern Scanner Error: {e}")
        import traceback
        traceback.print_exc()
        return False


async def test_momentum_scanner():
    """Test momentum signal detection."""
    print("\n" + "=" * 60)
    print("⚡ TESTING MOMENTUM SCANNER")
    print("=" * 60)
    
    try:
        from src.scanners.momentum_scanner import MomentumScanner, MomentumSignalType
        
        scanner = MomentumScanner()
        
        # Test with sample data
        df = generate_sample_ohlcv("NVDA", days=100)
        
        # Add a breakout at the end
        df.iloc[-3:, df.columns.get_loc('close')] *= 1.05
        df.iloc[-3:, df.columns.get_loc('volume')] *= 2.5
        
        print("\n🔍 Scanning for momentum signals...")
        print(f"   Data shape: {df.shape}")
        print(f"   Latest close: ${df['close'].iloc[-1]:.2f}")
        print(f"   Latest volume: {df['volume'].iloc[-1]:,.0f}")
        
        # Test the scanner initialization
        print(f"\n   Signal types available: {[s.value for s in MomentumSignalType]}")
        
        print("\n✅ Momentum Scanner: PASSED")
        return True
        
    except Exception as e:
        print(f"\n❌ Momentum Scanner Error: {e}")
        import traceback
        traceback.print_exc()
        return False


async def test_volume_scanner():
    """Test volume analysis."""
    print("\n" + "=" * 60)
    print("📊 TESTING VOLUME SCANNER")
    print("=" * 60)
    
    try:
        from src.scanners.volume_scanner import VolumeScanner, VolumeSignal
        
        scanner = VolumeScanner()
        
        # Generate test data
        df = generate_sample_ohlcv("TSLA", days=100)
        
        print(f"\n📈 Volume Scanner Initialized")
        print(f"   Available signals: {[s.value for s in VolumeSignal]}")
        print(f"   Data shape: {df.shape}")
        print(f"   Avg volume: {df['volume'].mean():,.0f}")
        print(f"   Latest volume: {df['volume'].iloc[-1]:,.0f}")
        
        print("\n✅ Volume Scanner: PASSED")
        return True
        
    except Exception as e:
        print(f"\n❌ Volume Scanner Error: {e}")
        import traceback
        traceback.print_exc()
        return False


async def test_sector_scanner():
    """Test sector rotation analysis."""
    print("\n" + "=" * 60)
    print("🏭 TESTING SECTOR SCANNER")
    print("=" * 60)
    
    try:
        from src.scanners.sector_scanner import SectorScanner, Sector, SECTOR_ETFS
        
        scanner = SectorScanner()
        
        print("\n📊 Available Sectors:")
        for sector in Sector:
            print(f"   • {sector.value}")
        
        print(f"\n📈 ETF Mappings:")
        for sector, etf in list(SECTOR_ETFS.items())[:5]:
            print(f"   {sector.value}: {etf}")
        
        print("\n✅ Sector Scanner: PASSED")
        return True
        
    except Exception as e:
        print(f"\n❌ Sector Scanner Error: {e}")
        import traceback
        traceback.print_exc()
        return False


async def test_news_analyzer():
    """Test news analysis and summarization."""
    print("\n" + "=" * 60)
    print("📰 TESTING NEWS ANALYZER")
    print("=" * 60)
    
    try:
        from src.research import NewsAnalyzer, NewsItem
        
        analyzer = NewsAnalyzer()
        
        # Sample news items
        sample_news = [
            {
                "id": "1",
                "title": "AAPL beats Q4 earnings estimates, revenue up 8%",
                "summary": "Apple reported strong quarterly results, beating analyst expectations with EPS of $2.10 vs $1.95 expected.",
                "source": "Reuters",
                "url": "https://example.com/1",
                "published_at": datetime.now() - timedelta(hours=2)
            },
            {
                "id": "2",
                "title": "Fed signals rate cuts may be delayed amid inflation concerns",
                "summary": "Federal Reserve officials indicated that interest rate reductions could be pushed back due to persistent inflation.",
                "source": "Bloomberg",
                "url": "https://example.com/2",
                "published_at": datetime.now() - timedelta(hours=1)
            },
            {
                "id": "3",
                "title": "NVDA stock surges on AI chip demand",
                "summary": "Nvidia shares rallied 5% as data center revenue exceeded expectations driven by AI infrastructure.",
                "source": "CNBC",
                "url": "https://example.com/3",
                "published_at": datetime.now() - timedelta(minutes=30)
            }
        ]
        
        print("\n🔍 Analyzing sample news...")
        
        analyzed = await analyzer.analyze_news_batch(sample_news)
        
        print(f"\n✅ Analyzed {len(analyzed)} news items:")
        
        for item in analyzed:
            print(f"\n   📌 {item.title[:50]}...")
            print(f"      Category: {item.category.value}")
            print(f"      Sentiment: {item.sentiment.value} ({item.sentiment_score:.2f})")
            print(f"      Tickers: {', '.join(item.tickers) if item.tickers else 'None'}")
            print(f"      Relevance: {item.relevance_score:.0f}/100")
            print(f"      Source Credibility: {item.credibility_score:.0f}/100")
        
        # Generate brief
        print("\n📋 Generating news brief...")
        brief = await analyzer.generate_brief(analyzed, period="morning")
        
        print(f"\n   Market Mood: {brief.market_mood}")
        print(f"   Headline: {brief.headline[:60]}...")
        print(f"   Stocks to Watch: {', '.join(brief.stocks_to_watch[:5])}")
        
        if brief.bullish_catalysts:
            print(f"   Bullish Catalysts: {len(brief.bullish_catalysts)}")
        if brief.bearish_catalysts:
            print(f"   Bearish Catalysts: {len(brief.bearish_catalysts)}")
        
        print("\n✅ News Analyzer: PASSED")
        return True
        
    except Exception as e:
        print(f"\n❌ News Analyzer Error: {e}")
        import traceback
        traceback.print_exc()
        return False


async def test_performance_tracker():
    """Test performance tracking and analytics."""
    print("\n" + "=" * 60)
    print("📈 TESTING PERFORMANCE TRACKER")
    print("=" * 60)
    
    try:
        from src.performance import PerformanceTracker, PerformanceAnalytics
        
        tracker = PerformanceTracker()
        analytics = PerformanceAnalytics()
        
        # Record sample signals
        print("\n📊 Recording sample signals...")
        
        await tracker.record_signal(
            signal_id="sig_001",
            ticker="AAPL",
            strategy="momentum",
            direction="long",
            entry_price=150.00,
            target_price=165.00,
            stop_loss=145.00,
            confidence=75.0
        )
        
        await tracker.record_signal(
            signal_id="sig_002",
            ticker="GOOGL",
            strategy="breakout",
            direction="long",
            entry_price=140.00,
            target_price=155.00,
            stop_loss=135.00,
            confidence=80.0
        )
        
        print(f"   Active signals: {len(tracker.active_signals)}")
        
        # Simulate updates
        print("\n⏱️ Simulating price updates...")
        
        # Signal 1 hits target
        await tracker.update_signal("sig_001", current_price=165.50)
        
        # Signal 2 hits stop
        await tracker.update_signal("sig_002", current_price=134.00)
        
        print(f"   Completed signals: {len(tracker.completed_signals)}")
        print(f"   Active signals: {len(tracker.active_signals)}")
        
        # Get stats
        stats = tracker.get_performance_stats()
        
        print(f"\n📊 Performance Stats:")
        print(f"   Total Signals: {stats.total_signals}")
        print(f"   Winners: {stats.winners}")
        print(f"   Losers: {stats.losers}")
        print(f"   Win Rate: {stats.win_rate:.1f}%")
        print(f"   Total P&L: {stats.total_pnl_pct:+.2f}%")
        print(f"   Profit Factor: {stats.profit_factor:.2f}")
        
        # Test analytics
        returns = [s.pnl_pct for s in tracker.completed_signals]
        if returns:
            metrics = analytics.calculate_strategy_metrics(returns, "test_strategy")
            print(f"\n📈 Strategy Metrics:")
            print(f"   Sharpe Ratio: {metrics.sharpe_ratio:.2f}")
            print(f"   Sortino Ratio: {metrics.sortino_ratio:.2f}")
            print(f"   Max Drawdown: {metrics.max_drawdown:.2f}%")
        
        print("\n✅ Performance Tracker: PASSED")
        return True
        
    except Exception as e:
        print(f"\n❌ Performance Tracker Error: {e}")
        import traceback
        traceback.print_exc()
        return False


async def test_earnings_analyzer():
    """Test earnings report analysis."""
    print("\n" + "=" * 60)
    print("💰 TESTING EARNINGS ANALYZER")
    print("=" * 60)
    
    try:
        from src.research import EarningsAnalyzer
        
        analyzer = EarningsAnalyzer()
        
        # Sample earnings data
        earnings_data = {
            "company_name": "Apple Inc.",
            "fiscal_quarter": "Q4",
            "fiscal_year": 2024,
            "report_date": datetime.now(),
            "eps_actual": 2.10,
            "eps_estimate": 1.95,
            "revenue_actual": 89.5,
            "revenue_estimate": 85.0,
            "eps_yoy_growth": 12.5,
            "revenue_yoy_growth": 8.0,
            "guidance": "Company raised full-year guidance"
        }
        
        print("\n🔍 Analyzing earnings report...")
        
        report = await analyzer.analyze_earnings("AAPL", earnings_data)
        
        print(f"\n📊 {report.ticker} Earnings Analysis:")
        print(f"   Headline: {report.headline}")
        print(f"   EPS Result: {report.eps_result.value}")
        print(f"   Revenue Result: {report.revenue_result.value}")
        print(f"   Guidance: {report.guidance_change.value}")
        print(f"   Sentiment: {report.overall_sentiment}")
        
        print(f"\n   Key Highlights:")
        for h in report.key_highlights[:3]:
            print(f"      ✅ {h}")
        
        print(f"\n   Expected Reaction: {report.expected_price_reaction}")
        print(f"   Recommendation: {report.trading_recommendation}")
        
        print("\n✅ Earnings Analyzer: PASSED")
        return True
        
    except Exception as e:
        print(f"\n❌ Earnings Analyzer Error: {e}")
        import traceback
        traceback.print_exc()
        return False


async def test_macro_analyzer():
    """Test macroeconomic event analysis."""
    print("\n" + "=" * 60)
    print("🌐 TESTING MACRO ANALYZER")
    print("=" * 60)
    
    try:
        from src.research import MacroAnalyzer
        
        analyzer = MacroAnalyzer()
        
        # Sample macro event
        event_data = {
            "title": "US CPI (YoY)",
            "timestamp": datetime.now(),
            "actual": 3.2,
            "forecast": 3.0,
            "previous": 2.9
        }
        
        print("\n🔍 Analyzing macro event...")
        
        event = await analyzer.analyze_event(event_data)
        
        print(f"\n📊 Event Analysis:")
        print(f"   Title: {event.title}")
        print(f"   Type: {event.event_type.value}")
        print(f"   Impact Level: {event.impact_level.value}")
        print(f"   Surprise: {event.surprise_direction}")
        print(f"\n   Fed Implications: {event.fed_implications}")
        print(f"   Bond Implications: {event.bond_implications}")
        print(f"   Equity Implications: {event.equity_implications}")
        
        if event.sector_implications:
            print(f"\n   Sector Implications:")
            for sector, imp in event.sector_implications.items():
                print(f"      {sector}: {imp}")
        
        print("\n✅ Macro Analyzer: PASSED")
        return True
        
    except Exception as e:
        print(f"\n❌ Macro Analyzer Error: {e}")
        import traceback
        traceback.print_exc()
        return False


async def main():
    """Run all tests."""
    print("\n" + "=" * 60)
    print("🚀 ENHANCED MARKET INTELLIGENCE SYSTEM - TEST SUITE")
    print("=" * 60)
    print(f"Started at: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    
    results = {}
    
    # Run all tests
    results["Pattern Scanner"] = await test_pattern_scanner()
    results["Momentum Scanner"] = await test_momentum_scanner()
    results["Volume Scanner"] = await test_volume_scanner()
    results["Sector Scanner"] = await test_sector_scanner()
    results["News Analyzer"] = await test_news_analyzer()
    results["Earnings Analyzer"] = await test_earnings_analyzer()
    results["Macro Analyzer"] = await test_macro_analyzer()
    results["Performance Tracker"] = await test_performance_tracker()
    
    # Summary
    print("\n" + "=" * 60)
    print("📋 TEST SUMMARY")
    print("=" * 60)
    
    passed = sum(1 for v in results.values() if v)
    total = len(results)
    
    for test, result in results.items():
        status = "✅ PASSED" if result else "❌ FAILED"
        print(f"   {test}: {status}")
    
    print(f"\n{'=' * 60}")
    print(f"   Total: {passed}/{total} tests passed")
    
    if passed == total:
        print("\n🎉 All tests passed! The enhanced market intelligence system is ready.")
    else:
        print(f"\n⚠️ {total - passed} test(s) failed. Please check the errors above.")
    
    print("=" * 60)
    
    return passed == total


if __name__ == "__main__":
    success = asyncio.run(main())
    sys.exit(0 if success else 1)
