#!/usr/bin/env python
"""Test the signal generation pipeline."""
import asyncio
import sys
sys.path.insert(0, '.')

async def test_signal_generation():
    print('🚀 Testing Signal Generation Pipeline...')
    print('=' * 50)
    
    from src.engines.signal_engine import SignalEngine
    from src.core.config import get_settings
    
    settings = get_settings()
    print('✅ Config loaded')
    
    # Initialize the signal engine
    engine = SignalEngine()
    print('✅ Signal engine initialized')
    
    # Test with some popular tickers
    tickers = ['AAPL', 'MSFT', 'NVDA', 'GOOGL', 'AMZN']
    print(f'📊 Generating signals for: {tickers}')
    print()
    
    try:
        signals = await engine.generate_signals(tickers)
        print(f'✅ Generated {len(signals)} signals')
        print()
        
        for signal in signals[:5]:
            print(f'📈 {signal.ticker}: {signal.direction.value}')
            print(f'   Confidence: {signal.confidence:.1%}')
            print(f'   Entry: ${signal.entry_price:.2f}')
            if signal.targets:
                targets_str = [f"${t.price:.2f}" for t in signal.targets]
                print(f'   Targets: {targets_str}')
            print(f'   Rationale: {signal.rationale[:100]}...')
            print()
            
        return signals
    except Exception as e:
        print(f'❌ Error: {type(e).__name__}: {e}')
        import traceback
        traceback.print_exc()
        return []

if __name__ == '__main__':
    asyncio.run(test_signal_generation())
