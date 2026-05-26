#!/usr/bin/env python
"""
Test signal generation with artificially created conditions
to verify the full pipeline works when criteria are met.
"""
import sys
sys.path.insert(0, '.')

import numpy as np
import pandas as pd
from datetime import datetime, timedelta
from src.engines.feature_engine import FeatureEngine
from src.engines.signal_engine import SignalEngine, RegimeDetector
from src.strategies import get_all_strategies

print('🧪 Testing Signal Pipeline with Forced Conditions')
print('=' * 60)

# Create data that WILL trigger signals
np.random.seed(42)
data = []
base_date = datetime.now() - timedelta(days=300)

tickers = ['MOM', 'REV', 'BRK']  # Valid ticker format (1-5 uppercase letters)

for ticker in tickers:
    price = 100.0
    
    for i in range(250):
        date = base_date + timedelta(days=i)
        
        if ticker == 'MOM':
            # Strong momentum: consistent uptrend with moderate RSI
            if i < 240:
                daily_return = 0.002 + np.random.normal(0, 0.008)  # 0.2% drift
            else:
                # Slight pullback to get RSI in range
                daily_return = -0.005
            price = max(price * (1 + daily_return), 80)
            volume = 1800000 if i > 240 else 1000000
            
        elif ticker == 'REV':
            # Mean reversion: uptrend then sharp drop but still above SMA200
            if i < 200:
                daily_return = 0.003 + np.random.normal(0, 0.008)  # Build up
            elif i < 240:
                daily_return = np.random.normal(0, 0.01)  # Consolidate
            else:
                daily_return = -0.02  # Drop but stay above long-term trend
            price = max(price * (1 + daily_return), 110)  # Floor above SMA200
            volume = 1500000
            
        elif ticker == 'BRK':
            # Breakout: long consolidation then explosive break above high
            if i < 249:
                # Tight consolidation around 100 for a long time
                price = 100 + np.random.uniform(-3, 3)
            else:
                # Final day: MASSIVE breakout above the consolidation range
                price = 150  # Way above the 100-103 consolidation range
            price = max(price, 95)
            volume = 5000000 if i == 249 else 800000  # Huge volume on breakout day
        
        # Realistic intraday range
        daily_vol = abs(np.random.normal(0.01, 0.005))
        high = price * (1 + daily_vol)
        low = price * (1 - daily_vol)
        
        data.append({
            'date': date,
            'ticker': ticker,
            'open': price * (1 + np.random.uniform(-0.003, 0.003)),
            'high': high,
            'low': low,
            'close': price,
            'volume': int(volume)
        })

df = pd.DataFrame(data)
df = df.set_index(['date', 'ticker'])
df = df.sort_index()
print(f'Input data: {df.shape}')

# Compute features
fe = FeatureEngine()
features = fe.calculate_features(df)
print(f'Features: {features.shape}')

latest = fe.get_latest_features(features)
print(f'Latest features: {latest.shape}')

# Show key indicators
print('\n📊 Key Indicator Values:')
for idx in latest.index:
    row = latest.loc[idx]
    uptrend = row['close'] > row['sma_50'] > row['sma_200'] if pd.notna(row['sma_50']) else 'N/A'
    high_20d = row.get('high_20d', row['close'] * 1.05)
    print(f'\n{idx}:')
    print(f'  close=${row["close"]:.2f}, sma50=${row["sma_50"]:.2f}, sma200=${row["sma_200"]:.2f}')
    print(f'  uptrend={uptrend}, rsi={row["rsi_14"]:.1f}, adx={row["adx_14"]:.1f}')
    print(f'  rel_vol={row["relative_volume"]:.2f}, return_21d={row["return_21d"]:.4f}')
    print(f'  high_20d=${high_20d:.2f}, breakout={row["close"] > high_20d * 0.99}')

# Test regime
print('\n🌡️ Market Regime:')
market_data = {
    'vix': 18, 
    'market_open': True, 
    'is_trading_day': True,
    'sp500_above_200ma': True
}
regime_detector = RegimeDetector()
regime = regime_detector.detect(market_data)
print(f'  Regime: {regime.volatility.value}/{regime.trend.value}/{regime.risk.value}')
print(f'  Active strategies: {regime.active_strategies}')

# Generate signals
print('\n🎯 Generating Signals:')
strategies = get_all_strategies()

for strategy in strategies:
    print(f'\n--- {strategy.STRATEGY_ID} ---')
    try:
        signals = strategy.generate_signals(
            universe=tickers,
            features=latest,
            market_data=market_data
        )
        print(f'Generated {len(signals)} signals')
        for sig in signals:
            print(f'  ✅ {sig.ticker}: {sig.direction.value} @ ${sig.entry_price:.2f}')
            print(f'     Confidence: {sig.confidence}%')
            print(f'     Rationale: {sig.rationale[:80]}...')
    except Exception as e:
        import traceback
        print(f'Error: {e}')
        traceback.print_exc()

# Use full signal engine
print('\n\n🔧 Full Signal Engine Test:')
signal_engine = SignalEngine()
all_signals = signal_engine.generate_signals(
    universe=tickers,
    features=latest,
    market_data=market_data,
    portfolio={}
)
print(f'Total signals from engine: {len(all_signals)}')

for sig in all_signals:
    print(f'\n  📈 {sig.ticker} - {sig.direction.value}')
    print(f'     Strategy: {sig.strategy_id}')
    print(f'     Entry: ${sig.entry_price:.2f}')
    print(f'     Confidence: {sig.confidence}%')

print('\n' + '=' * 60)
print('Test Complete!')
