#!/usr/bin/env python3
"""Test Alpaca API prices to ensure accuracy."""
import asyncio
import aiohttp
from src.core.config import get_settings

settings = get_settings()

async def test_prices():
    headers = {
        'APCA-API-KEY-ID': settings.alpaca_api_key,
        'APCA-API-SECRET-KEY': settings.alpaca_secret_key
    }
    
    tickers = ['PANW', 'AAPL', 'NVDA', 'MSFT', 'TSLA']
    
    async with aiohttp.ClientSession() as session:
        for ticker in tickers:
            print(f"\n=== {ticker} ===")
            
            # Method 1: Latest quote (bid/ask)
            url = f'https://data.alpaca.markets/v2/stocks/{ticker}/quotes/latest'
            async with session.get(url, headers=headers) as resp:
                if resp.status == 200:
                    data = await resp.json()
                    quote = data.get('quote', {})
                    bid = float(quote.get('bp', 0))
                    ask = float(quote.get('ap', 0))
                    mid = (bid + ask) / 2 if bid and ask else 0
                    ts = quote.get('t', 'N/A')
                    print(f"Quote: Bid=${bid:.2f}, Ask=${ask:.2f}, Mid=${mid:.2f}")
                    print(f"  Timestamp: {ts}")
            
            # Method 2: Latest trade
            url = f'https://data.alpaca.markets/v2/stocks/{ticker}/trades/latest'
            async with session.get(url, headers=headers, params={'feed': 'iex'}) as resp:
                if resp.status == 200:
                    data = await resp.json()
                    trade = data.get('trade', {})
                    price = float(trade.get('p', 0))
                    ts = trade.get('t', 'N/A')
                    print(f"Trade: ${price:.2f}")
                    print(f"  Timestamp: {ts}")
            
            # Method 3: Latest bar
            url = f'https://data.alpaca.markets/v2/stocks/{ticker}/bars/latest'
            async with session.get(url, headers=headers, params={'feed': 'iex'}) as resp:
                if resp.status == 200:
                    data = await resp.json()
                    bar = data.get('bar', {})
                    close = float(bar.get('c', 0))
                    ts = bar.get('t', 'N/A')
                    print(f"Bar Close: ${close:.2f}")
                    print(f"  Timestamp: {ts}")

if __name__ == '__main__':
    asyncio.run(test_prices())
