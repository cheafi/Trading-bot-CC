#!/usr/bin/env python
"""
Full end-to-end test with historical data for signal generation.
"""
import asyncio
import sys
sys.path.insert(0, '.')

async def test_with_historical_data():
    print('🚀 TradingAI - Full Pipeline Test with Historical Data')
    print('=' * 60)
    
    from src.core.config import get_settings
    import aiohttp
    import pandas as pd
    from datetime import datetime, timedelta
    
    settings = get_settings()
    tickers = ['AAPL', 'MSFT', 'NVDA', 'GOOGL', 'AMZN']
    
    # Step 1: Fetch historical bars from Alpaca
    # Need 250+ days for SMA_200 and other long-term indicators
    print('\n📊 Step 1: Fetching 1 year of historical data from Alpaca...')
    
    all_bars = []
    end = datetime.now()
    start = end - timedelta(days=365)  # 1 year of history
    
    async with aiohttp.ClientSession() as session:
        headers = {
            'APCA-API-KEY-ID': settings.alpaca_api_key,
            'APCA-API-SECRET-KEY': settings.alpaca_secret_key
        }
        
        for ticker in tickers:
            url = f"https://data.alpaca.markets/v2/stocks/{ticker}/bars"
            params = {
                'start': start.strftime('%Y-%m-%d'),
                'end': end.strftime('%Y-%m-%d'),
                'timeframe': '1Day',
                'limit': 1000,  # Get up to 1000 bars (~4 years)
                'feed': 'iex'  # Use IEX feed (free tier)
            }
            
            try:
                async with session.get(url, headers=headers, params=params) as response:
                    if response.status == 200:
                        data = await response.json()
                        bars = data.get('bars', [])
                        for bar in bars:
                            all_bars.append({
                                'ticker': ticker,
                                'ts': bar['t'],
                                'open': bar['o'],
                                'high': bar['h'],
                                'low': bar['l'],
                                'close': bar['c'],
                                'volume': bar['v']
                            })
                        print(f'   ✅ {ticker}: {len(bars)} bars')
            except Exception as e:
                print(f'   ❌ {ticker}: {e}')
    
    if not all_bars:
        print('   ❌ No historical data fetched')
        return
    
    df = pd.DataFrame(all_bars)
    # Parse timestamp and create proper MultiIndex
    df['date'] = pd.to_datetime(df['ts']).dt.tz_localize(None)
    df = df.set_index(['date', 'ticker'])
    df = df.drop(columns=['ts'])
    df = df.sort_index()
    print(f'\n   Total bars: {len(df)} (Index: {df.index.names})')
    
    # Step 2: Compute features
    print('\n⚙️ Step 2: Computing technical features...')
    from src.engines.feature_engine import FeatureEngine
    
    feature_engine = FeatureEngine()
    features = feature_engine.calculate_features(df)
    print(f'   ✅ Features shape: {features.shape}')
    
    # Get latest features only
    latest_features = feature_engine.get_latest_features(features)
    print(f'   ✅ Latest features: {len(latest_features)} tickers')
    
    # Show key indicator values
    print('\n   Key indicators per ticker:')
    for idx in latest_features.index:
        row = latest_features.loc[idx]
        uptrend = row['close'] > row['sma_50'] > row['sma_200'] if 'sma_50' in row and pd.notna(row['sma_50']) else 'N/A'
        print(f'   {idx}: close=${row["close"]:.2f}, rsi={row["rsi_14"]:.1f}, adx={row["adx_14"]:.1f}, uptrend={uptrend}')
    
    # Step 3: Detect regime
    print('\n🌡️ Step 3: Analyzing market regime...')
    from src.engines.signal_engine import RegimeDetector
    
    market_data = {
        'vix': 18.5,
        'vix_percentile': 45,
        'spy_rsi': 55,
        'spy_return_1d': 0.5,
        'spy_return_5d': 1.2,
        'advance_decline_ratio': 1.3,
        'new_highs': 150,
        'new_lows': 30,
        'market_open': True,
        'is_trading_day': True,
        'sp500_above_200ma': True
    }
    
    regime_detector = RegimeDetector()
    regime = regime_detector.detect(market_data)
    print(f'   ✅ Regime: {regime.volatility.value}/{regime.trend.value}/{regime.risk.value}')
    print(f'   ✅ Active strategies: {regime.active_strategies}')
    
    # Step 4: Generate signals
    print('\n🎯 Step 4: Generating signals...')
    
    # Debug: Check breakout conditions
    print('\n   --- Breakout Debug ---')
    print('   Requirements: close > high_20d * 0.99 AND relative_volume >= 2.0')
    for idx in latest_features.index:
        row = latest_features.loc[idx]
        high_20d = row.get('high_20d', row['close'] * 1.05)  # fallback
        rel_vol = row.get('relative_volume', 1.0)
        close_near_high = row['close'] > high_20d * 0.99
        vol_high = rel_vol >= 2.0
        print(f'   {idx}: close=${row["close"]:.2f}, high_20d=${high_20d:.2f}, rel_vol={rel_vol:.2f} | near_high={close_near_high}, vol_2x={vol_high}')
    
    # Debug: Check mean reversion conditions
    print('\n   --- Mean Reversion Debug ---')
    print('   Requirements: RSI < 30 OR close < bb_lower, zscore_21d < -2.0, close > sma_200')
    for idx in latest_features.index:
        row = latest_features.loc[idx]
        rsi_low = row['rsi_14'] < 30
        bb_low = row['close'] < row.get('bb_lower', float('inf'))
        above_200 = row['close'] > row.get('sma_200', 0)
        print(f'   {idx}: rsi={row["rsi_14"]:.1f}, bb_lower={row.get("bb_lower", "N/A")}, sma_200={row.get("sma_200", "N/A"):.2f} | oversold={rsi_low or bb_low}, above_200={above_200}')
    
    from src.engines.signal_engine import SignalEngine
    
    signal_engine = SignalEngine()
    signals = signal_engine.generate_signals(
        universe=tickers,
        features=latest_features,
        market_data=market_data,
        portfolio={}
    )
    
    print(f'\n   ✅ Generated {len(signals)} signals')
    
    if signals:
        print('\n📈 Trading Signals:')
        print('-' * 60)
        for signal in signals:
            print(f'\n   {signal.ticker} - {signal.direction.value}')
            print(f'   Confidence: {signal.confidence:.1%}')
            print(f'   Entry: ${signal.entry_price:.2f}')
            if signal.targets:
                targets = [f"${t.price:.2f}" for t in signal.targets]
                print(f'   Targets: {targets}')
            if signal.stop_loss:
                print(f'   Stop: ${signal.stop_loss.price:.2f}')
            print(f'   Strategy: {signal.strategy_id}')
            print(f'   Rationale: {signal.rationale[:100]}...')
        
        # Step 5: Validate with GPT
        print('\n🤖 Step 5: Validating with GPT...')
        try:
            from src.engines.gpt_validator import GPTValidator
            
            validator = GPTValidator()
            validated = await validator.validate_signal(signals[0])
            
            print(f'   ✅ Signal: {validated.ticker}')
            print(f'   ✅ GPT Approved: {validated.gpt_approved}')
            print(f'   ✅ GPT Confidence: {validated.gpt_confidence:.1%}')
            print(f'   ✅ Commentary: {validated.gpt_commentary[:150]}...')
        except Exception as e:
            print(f'   ❌ GPT validation error: {e}')
        
        # Step 6: Send to Telegram
        print('\n📱 Step 6: Sending to Telegram...')
        try:
            from src.notifications.telegram import TelegramNotifier
            
            notifier = TelegramNotifier()
            await notifier.send_signal(signals[0])
            print('   ✅ Signal sent to Telegram')
        except Exception as e:
            print(f'   ❌ Telegram error: {e}')
    
    # Summary
    print('\n' + '=' * 60)
    print('📊 Pipeline Test Complete')
    print('=' * 60)
    print(f'   Historical bars: {len(df)}')
    print(f'   Tickers: {len(tickers)}')
    print(f'   Features: {features.shape}')
    print(f'   Signals: {len(signals)}')
    print('=' * 60)

if __name__ == '__main__':
    asyncio.run(test_with_historical_data())
