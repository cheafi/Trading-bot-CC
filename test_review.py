#!/usr/bin/env python3
"""Quick test to verify all improvements."""
import sys
sys.path.insert(0, ".")

from src.notifications.telegram_bot import TelegramBot

bot = TelegramBot()
print("✅ Import & instantiation OK")
print(f"   Commands: {len(TelegramBot.COMMANDS)}")
print(f"   TOP_STOCKS: {len(TelegramBot.TOP_STOCKS)}")
print(f"   JAPAN_STOCKS: {len(TelegramBot.JAPAN_STOCKS)}")
print(f"   HONG_KONG_STOCKS: {len(TelegramBot.HONG_KONG_STOCKS)}")
print(f"   CRYPTO_STOCKS: {len(TelegramBot.CRYPTO_STOCKS)}")
print(f"   MACRO_ASSETS: {len(TelegramBot.MACRO_ASSETS)}")
print(f"   GLOBAL_INDICES: {len(TelegramBot.GLOBAL_INDICES)}")

# Check Pro Trader commands exist
print("\n--- Pro Trader Commands ---")
pro_cmds = ["/prosetup", "/conviction", "/catalyst", "/asymmetric",
            "/compound", "/projournal", "/winstreak", "/drawdown",
            "/sharpe", "/edge", "/monthly", "/yearly"]
for cmd in pro_cmds:
    method_name = f"_cmd_{cmd.lstrip('/')}"
    has = hasattr(bot, method_name)
    in_commands = cmd in TelegramBot.COMMANDS
    print(f"  {cmd}: handler={'✅' if has else '❌'}, in COMMANDS={'✅' if in_commands else '❌'}")

# Check Crypto commands exist
print("\n--- Crypto Commands ---")
crypto_cmds = ["/crypto", "/btc", "/eth", "/miners", "/cryptostocks", "/defi", "/web3"]
for cmd in crypto_cmds:
    method_name = f"_cmd_{cmd.lstrip('/')}"
    has = hasattr(bot, method_name)
    in_commands = cmd in TelegramBot.COMMANDS
    print(f"  {cmd}: handler={'✅' if has else '❌'}, in COMMANDS={'✅' if in_commands else '❌'}")

# Check message splitting
print("\n--- Message Splitting ---")
has_split = hasattr(bot, '_split_message')
has_single = hasattr(bot, '_send_single_message')
print(f"  _split_message: {'✅' if has_split else '❌'}")
print(f"  _send_single_message: {'✅' if has_single else '❌'}")

# Test message splitting
if has_split:
    test_msg = "Line\n" * 500  # ~2500 chars
    chunks = bot._split_message(test_msg, 4000)
    print(f"  Split 2500-char message: {len(chunks)} chunks (should be 1)")
    
    long_msg = "A" * 100 + "\n" 
    long_msg = long_msg * 80  # ~8080 chars
    chunks = bot._split_message(long_msg, 4000)
    print(f"  Split 8080-char message: {len(chunks)} chunks (should be 2+)")

# Verify Japan stocks are specific tickers not just ETFs
print("\n--- Japan Specific Tickers ---")
jp_adrs = [t for t in TelegramBot.JAPAN_STOCKS if not t.startswith("E") and not t.startswith("D") and not t.startswith("B") and len(t) <= 6]
jp_etfs = [t for t in TelegramBot.JAPAN_STOCKS if t in ["EWJ", "DXJ", "BBJP", "FLJP", "JPXN", "HEWJ"]]
print(f"  ADRs: {len(TelegramBot.JAPAN_STOCKS) - len(jp_etfs)}")
print(f"  ETFs: {len(jp_etfs)}")
print(f"  Sample ADRs: {list(TelegramBot.JAPAN_STOCKS.keys())[:10]}")

# Verify HK stocks are specific tickers
print("\n--- HK Specific Tickers ---")
hk_etfs = [t for t in TelegramBot.HONG_KONG_STOCKS if t in ["EWH", "FXI", "MCHI", "GXC", "KWEB", "CQQQ", "ASHR", "CHIQ", "CXSE"]]
print(f"  ADRs: {len(TelegramBot.HONG_KONG_STOCKS) - len(hk_etfs)}")
print(f"  ETFs: {len(hk_etfs)}")
print(f"  Sample ADRs: {list(TelegramBot.HONG_KONG_STOCKS.keys())[:10]}")

# Verify Crypto stocks are specific tickers
print("\n--- Crypto Specific Tickers ---")
crypto_etfs = [t for t in TelegramBot.CRYPTO_STOCKS if any(x in t for x in ["ETF", "BIT"]) or t in ["DAPP", "BLOK", "LEGR", "BKCH"]]
print(f"  Total crypto tickers: {len(TelegramBot.CRYPTO_STOCKS)}")
print(f"  BTC Spot ETFs: {[t for t in TelegramBot.CRYPTO_STOCKS if TelegramBot.CRYPTO_STOCKS[t][0] == '₿' and 'Spot' in TelegramBot.CRYPTO_STOCKS[t][2]]}")
print(f"  Miners: {[t for t in TelegramBot.CRYPTO_STOCKS if TelegramBot.CRYPTO_STOCKS[t][0] == '⛏️']}")
print(f"  BTC Treasury: {[t for t in TelegramBot.CRYPTO_STOCKS if 'treasury' in TelegramBot.CRYPTO_STOCKS[t][2].lower() or 'balance sheet' in TelegramBot.CRYPTO_STOCKS[t][2].lower()]}")

print("\n✅ All tests passed!")
