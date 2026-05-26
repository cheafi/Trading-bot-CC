#!/usr/bin/env python
"""Debug signal generation."""
import sys
sys.path.insert(0, '.')

import numpy as np
import pandas as pd
from datetime import datetime, timedelta
from src.engines.feature_engine import FeatureEngine
from src.strategies import get_all_strategies

# Create realistic data with proper price action
np.random.seed(42)
data = []
base_date = datetime.now() - timedelta(days=300)

tickers = ['AAPL', 'MSFT', 'NVDA']
for ticker in tickers:
    price = 150.0
    for i in range(250):
        date = base_date + timedelta(days=i)
        
        # Random daily return with upward drift
        daily_return = np.random.normal(0.0005, 0.015)  # 0.05% drift, 1.5% volatility
        price = price * (1 + daily_return)
        
        # Realistic intraday range
        daily_vol = abs(np.random.normal(0, 0.01))
        high = price * (1 + daily_vol)
        low = price * (1 - daily_vol)
        open_price = price * (1 + np.random.uniform(-0.005, 0.005))
        
        # Volume with some variation
        volume = int(np.random.uniform(800000, 2000000))
        
        data.append({
            'date': date,
            'ticker': ticker,
            'open': open_price,
            'high': high,
            'low': low,
            'close': price,
            'volume': volume
        })

df = pd.DataFrame(data)
# Create proper MultiIndex (date, ticker) that FeatureEngine expects
df = df.set_index(['date', 'ticker'])
print(f'Input data: {df.shape}')
print(f'Index levels: {df.index.names}')

fe = FeatureEngine()
features = fe.calculate_features(df)
print(f'Features: {features.shape}')
print(f'Feature columns: {list(features.columns)[:10]}...')

# Get latest features (should be 1 row per ticker)
latest = fe.get_latest_features(features)
print(f'Latest features: {latest.shape}')
print(f'Latest index: {latest.index}')

# Check key indicator values for debugging
print(f'\n=== Key Indicator Values ===')
for idx in latest.index:
    print(f'\n{idx}:')
    row = latest.loc[idx]
    print(f'  close={row.get("close", "N/A"):.2f}')
    print(f'  sma_50={row.get("sma_50", "N/A"):.2f}, sma_200={row.get("sma_200", "N/A"):.2f}')
    print(f'  adx_14={row.get("adx_14", "N/A")}')
    print(f'  rsi_14={row.get("rsi_14", "N/A"):.2f}')
    print(f'  return_21d={row.get("return_21d", "N/A"):.4f}')
    print(f'  relative_volume={row.get("relative_volume", "N/A"):.2f}')

# Test strategies
strategies = get_all_strategies()
print(f'\n=== Strategy Tests ===')
print(f'Strategies: {[s.STRATEGY_ID for s in strategies]}')

market_data = {'vix': 18, 'market_open': True, 'is_trading_day': True}
universe = ['AAPL', 'MSFT', 'NVDA']

# Debug momentum filters
print('\n--- Momentum Filter Debug ---')
print('Requirements: close > sma_50 > sma_200, adx > 25, rsi 50-70, rel_vol > 1.0, top 20% return_21d')
for idx in latest.index:
    row = latest.loc[idx]
    uptrend = row['close'] > row['sma_50'] > row['sma_200']
    adx_ok = row['adx_14'] > 25
    rsi_ok = 50 <= row['rsi_14'] <= 70
    vol_ok = row['relative_volume'] > 1.0
    print(f'{idx}: uptrend={uptrend}, adx>25={adx_ok}, rsi_50-70={rsi_ok}, vol>1={vol_ok}')

# Calculate momentum rank
latest_copy = latest.copy()
latest_copy['momentum_rank'] = latest_copy['return_21d'].rank(pct=True)
print(f'\nMomentum ranks (need >= 0.80):')
for idx in latest_copy.index:
    print(f'  {idx}: rank={latest_copy.loc[idx, "momentum_rank"]:.2f}')

for strategy in strategies:
    try:
        signals = strategy.generate_signals(universe, latest, market_data)
        print(f'\n{strategy.STRATEGY_ID}: {len(signals)} signals')
        for sig in signals[:3]:
            print(f'  - {sig.ticker}: {sig.direction.value} @ ${sig.entry_price:.2f} (conf={sig.confidence:.2f})')
    except Exception as e:
        import traceback
        print(f'{strategy.STRATEGY_ID}: Error - {type(e).__name__}: {e}')
        traceback.print_exc()
