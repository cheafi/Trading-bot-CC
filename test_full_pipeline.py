#!/usr/bin/env python
"""
Full end-to-end test of the TradingAI signal generation pipeline.
This fetches real market data from Alpaca and generates trading signals.
"""
import asyncio
import sys
sys.path.insert(0, '.')

async def test_full_pipeline():
    print('🚀 TradingAI - Full Pipeline Test')
    print('=' * 60)

    # Step 1: Load config and check connections
    print('\n📋 Step 1: Loading configuration...')
    from src.core.config import get_settings
    settings = get_settings()
    print('   ✅ Config loaded')

    # Step 2: Fetch market data from Alpaca
    print('\n📊 Step 2: Fetching market data from Alpaca...')
    import aiohttp
    from datetime import datetime
    import yfinance as yf

    quotes = {}
    histories = {}
    tickers = ['AAPL', 'MSFT', 'NVDA', 'GOOGL', 'AMZN']

    try:
        async with aiohttp.ClientSession() as session:
            headers = {
                'APCA-API-KEY-ID': settings.alpaca_api_key,
                'APCA-API-SECRET-KEY': settings.alpaca_secret_key
            }

            # Get latest quotes from Alpaca
            url = f"https://data.alpaca.markets/v2/stocks/quotes/latest?symbols={','.join(tickers)}"
            async with session.get(url, headers=headers) as response:
                if response.status == 200:
                    data = await response.json()
                    for ticker, quote_data in data.get('quotes', {}).items():
                        quotes[ticker] = {
                            'price': quote_data.get('ap', 0),  # ask price
                            'bid': quote_data.get('bp', 0),
                            'ask': quote_data.get('ap', 0),
                        }
                    print(f'   ✅ Got quotes for {len(quotes)} tickers')
                    for ticker, quote in list(quotes.items())[:3]:
                        print(f'      {ticker}: ${quote["price"]:.2f}')
                else:
                    print(f'   ⚠️ Alpaca API returned {response.status}')
    except Exception as e:
        print(f'   ❌ Error fetching quotes: {e}')
        quotes = {}

    if not quotes:
        print("   🔁 Falling back to yfinance...")
        try:
            data = yf.download(
                tickers,
                period="260d",
                progress=False,
                group_by="ticker",
                auto_adjust=False,
                threads=True,
            )
            for ticker in tickers:
                df = data[ticker].dropna() if len(tickers) > 1 else data.dropna()
                if df.empty:
                    continue
                histories[ticker] = df.rename(columns=str.lower)
                quotes[ticker] = {
                    "price": float(df["Close"].iloc[-1]),
                    "bid": float(df["Close"].iloc[-1]),
                    "ask": float(df["Close"].iloc[-1]),
                }
            print(f"   ✅ yfinance fallback returned {len(quotes)} tickers")
        except Exception as e:
            print(f"   ❌ yfinance fallback failed: {e}")

    # Step 3: Compute features
    print('\n⚙️ Step 3: Computing technical features...')
    from src.engines.feature_engine import FeatureEngine
    import pandas as pd

    try:
        feature_engine = FeatureEngine()

        latest_features = []
        for ticker in tickers:
            df = histories.get(ticker)
            if df is None or df.empty:
                continue
            feats = feature_engine.calculate_features(df)
            if feats.empty:
                continue
            latest = feats.iloc[[-1]].copy()
            latest["ticker"] = ticker
            latest_features.append(latest)

        if latest_features:
            features = pd.concat(latest_features, ignore_index=True)
            print(f'   ✅ Computed features: {features.shape}')
        else:
            features = pd.DataFrame()
            print('   ⚠️ No data for feature computation')
    except Exception as e:
        print(f'   ❌ Error computing features: {e}')
        features = pd.DataFrame()

    # Step 4: Get market regime data
    print('\n🌡️ Step 4: Analyzing market regime...')
    try:
        # Create mock market data for regime detection
        market_data = {
            "vix": 18.5,
            "vix_percentile": 45,
            "spy_rsi": 55,
            "spy_return_1d": 0.5,
            "spy_return_5d": 1.2,
            "advance_decline_ratio": 1.3,
            "new_highs": 150,
            "new_lows": 30,
            "market_open": True,
            "is_trading_day": True,
            "sp500_above_200ma": True,
            "spx_change_pct": 0.5,
            "pct_above_sma50": 62,
            "hy_spread": 320,
            "vix_term_structure": 1.0,
            "data_fresh": True,
            "data_staleness_seconds": 0,
            "feed_timestamps": {
                "ohlcv": datetime.utcnow().isoformat(),
                "features": datetime.utcnow().isoformat(),
                "market_breadth": datetime.utcnow().isoformat(),
            },
            "universe_coverage_pct": (
                (len(features) / len(tickers)) * 100 if len(tickers) else 0
            ),
        }

        from src.engines.signal_engine import RegimeDetector
        regime_detector = RegimeDetector()
        regime = regime_detector.detect(market_data)

        print(f'   ✅ Volatility: {regime.volatility.value}')
        print(f'   ✅ Trend: {regime.trend.value}')
        print(f'   ✅ Risk: {regime.risk.value}')
        print(f'   ✅ Should trade: {regime.should_trade}')
        print(f'   ✅ Active strategies: {regime.active_strategies}')
    except Exception as e:
        print(f'   ❌ Error detecting regime: {e}')
        import traceback
        traceback.print_exc()
        regime = None

    # Step 5: Generate signals
    print('\n🎯 Step 5: Generating trading signals...')
    try:
        from src.engines.signal_engine import SignalEngine

        signal_engine = SignalEngine()

        if not features.empty:
            signals = signal_engine.generate_signals(
                universe=tickers,
                features=features,
                market_data=market_data,
                portfolio={}
            )

            print(f'   ✅ Generated {len(signals)} signals')

            for signal in signals[:5]:
                print(f'\n   📈 {signal.ticker}: {signal.direction.value}')
                print(f'      Confidence: {signal.confidence:.1%}')
                print(f'      Entry: ${signal.entry_price:.2f}')
                if signal.targets:
                    targets = [f"${t.price:.2f}" for t in signal.targets]
                    print(f'      Targets: {targets}')
                print(f'      Rationale: {signal.rationale[:80]}...')
        else:
            print('   ⚠️ Skipped - no features available')
            signals = []
    except Exception as e:
        print(f'   ❌ Error generating signals: {e}')
        import traceback
        traceback.print_exc()
        signals = []

    # Step 6: Test GPT validation (if signals exist)
    if signals:
        print('\n🤖 Step 6: Validating signals with GPT...')
        try:
            from src.engines.gpt_validator import GPTValidator

            validator = GPTValidator()
            validated = await validator.validate_signal(signals[0])

            print(f'   ✅ GPT Validation complete')
            print(f'      Approved: {validated.gpt_approved}')
            print(f'      Confidence: {validated.gpt_confidence:.1%}')
            print(f'      Commentary: {validated.gpt_commentary[:100]}...')
        except Exception as e:
            print(f'   ❌ Error validating: {e}')

    # Step 7: Test Telegram notification
    print('\n📱 Step 7: Testing Telegram notification...')
    try:
        from src.notifications.telegram import TelegramNotifier

        notifier = TelegramNotifier()
        test_msg = "🧪 TradingAI Pipeline Test\n\n✅ All systems operational!"
        await notifier.send_message(test_msg)
        print('   ✅ Telegram notification sent')
    except Exception as e:
        print(f'   ❌ Error sending notification: {e}')

    # Summary
    print('\n' + '=' * 60)
    print('📊 Pipeline Test Summary')
    print('=' * 60)
    print(f'   Tickers analyzed: {len(tickers)}')
    print(f'   Quotes fetched: {len(quotes)}')
    print(f'   Features computed: {features.shape[0] if not features.empty else 0} rows')
    print(f'   Signals generated: {len(signals)}')
    print('=' * 60)

    return signals

if __name__ == '__main__':
    asyncio.run(test_full_pipeline())
