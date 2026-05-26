#!/usr/bin/env python
"""Debug Alpaca historical data API."""
import asyncio
import aiohttp
import sys
sys.path.insert(0, '.')

from src.core.config import get_settings
from datetime import datetime, timedelta

async def test():
    settings = get_settings()
    
    end = datetime.now()
    start = end - timedelta(days=30)
    
    async with aiohttp.ClientSession() as session:
        headers = {
            'APCA-API-KEY-ID': settings.alpaca_api_key,
            'APCA-API-SECRET-KEY': settings.alpaca_secret_key
        }
        
        url = 'https://data.alpaca.markets/v2/stocks/AAPL/bars'
        params = {
            'start': start.strftime('%Y-%m-%d'),
            'end': end.strftime('%Y-%m-%d'),
            'timeframe': '1Day',
            'limit': 30,
            'feed': 'iex'  # Use IEX feed (free tier)
        }
        
        print(f'URL: {url}')
        print(f'Params: {params}')
        
        async with session.get(url, headers=headers, params=params) as response:
            print(f'Status: {response.status}')
            data = await response.json()
            print(f'Response keys: {data.keys() if isinstance(data, dict) else type(data)}')
            if 'bars' in data:
                bars = data['bars']
                print(f'Bars: {len(bars) if bars else 0}')
                if bars:
                    print(f'First bar: {bars[0]}')
            else:
                print(f'Full response: {data}')

asyncio.run(test())
