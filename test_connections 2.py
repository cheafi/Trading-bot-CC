#!/usr/bin/env python3
"""
TradingAI Bot - Connection Test Script
Tests all configured API connections.
"""
import asyncio
import sys


async def test_config():
    """Test configuration loading."""
    print("\n=== Testing Configuration ===")
    from src.core.config import get_settings
    s = get_settings()
    
    print(f"✅ Config loaded")
    print(f"   Database: {s.postgres_host}:{s.postgres_port}/{s.postgres_db}")
    print(f"   Redis: {s.redis_host}:{s.redis_port}")
    print(f"   Azure OpenAI: {s.use_azure_openai}")
    print(f"   S3 Storage: {s.has_s3}")
    print(f"   Alpaca: {bool(s.alpaca_api_key)}")
    return True


async def test_azure_openai():
    """Test Azure OpenAI connection."""
    print("\n=== Testing Azure OpenAI ===")
    from src.engines.gpt_validator import get_openai_client
    from src.core.config import get_settings
    
    s = get_settings()
    if not s.use_azure_openai:
        print("⚠️  Azure OpenAI not configured, skipping")
        return False
    
    try:
        client = get_openai_client()
        print(f"   Client type: {type(client).__name__}")
        print(f"   Endpoint: {s.azure_openai_endpoint}")
        print(f"   Deployment: {s.azure_openai_deployment}")
        
        # Make a simple API call
        response = await client.chat.completions.create(
            model=s.azure_openai_deployment,
            messages=[
                {"role": "user", "content": "Reply with just: OK"}
            ],
            max_tokens=10
        )
        result = response.choices[0].message.content.strip()
        print(f"✅ Azure OpenAI working - Response: {result}")
        return True
    except Exception as e:
        print(f"❌ Azure OpenAI failed: {e}")
        return False


async def test_alpaca():
    """Test Alpaca API connection."""
    print("\n=== Testing Alpaca ===")
    from src.core.config import get_settings
    import aiohttp
    
    s = get_settings()
    if not s.alpaca_api_key:
        print("⚠️  Alpaca not configured, skipping")
        return False
    
    try:
        headers = {
            "APCA-API-KEY-ID": s.alpaca_api_key,
            "APCA-API-SECRET-KEY": s.alpaca_secret_key
        }
        
        async with aiohttp.ClientSession() as session:
            async with session.get(
                f"{s.alpaca_endpoint}/account",
                headers=headers
            ) as response:
                if response.status == 200:
                    data = await response.json()
                    print(f"✅ Alpaca connected")
                    print(f"   Account: {data.get('account_number', 'N/A')}")
                    print(f"   Buying Power: ${float(data.get('buying_power', 0)):,.2f}")
                    return True
                else:
                    text = await response.text()
                    print(f"❌ Alpaca failed: {response.status} - {text}")
                    return False
    except Exception as e:
        print(f"❌ Alpaca error: {e}")
        return False


async def main():
    """Run all tests."""
    print("=" * 50)
    print("TradingAI Bot - Connection Tests")
    print("=" * 50)
    
    results = {}
    
    results["config"] = await test_config()
    results["azure_openai"] = await test_azure_openai()
    results["alpaca"] = await test_alpaca()
    
    print("\n" + "=" * 50)
    print("Summary:")
    print("=" * 50)
    
    all_ok = True
    for name, ok in results.items():
        status = "✅" if ok else "❌"
        print(f"  {status} {name}")
        if not ok:
            all_ok = False
    
    print()
    return 0 if all_ok else 1


if __name__ == "__main__":
    exit_code = asyncio.run(main())
    sys.exit(exit_code)
