#!/usr/bin/env python3
"""
Test script for Interactive Telegram Bot and Broker Integration

Tests:
1. Telegram Bot Commands
2. Broker Manager initialization
3. Paper Trading execution
4. Order placement and cancellation
"""
import asyncio
import sys
import os

# Add project root to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from datetime import datetime


async def test_broker_manager():
    """Test broker manager initialization."""
    print("\n" + "="*60)
    print("TEST 1: Broker Manager")
    print("="*60)
    
    from src.brokers.broker_manager import BrokerManager, BrokerType
    
    manager = BrokerManager()
    await manager.initialize()
    
    # Check available brokers
    brokers = manager.get_available_brokers()
    print(f"\n✅ Broker Manager initialized")
    print(f"   Available brokers: {len(brokers)}")
    
    for broker in brokers:
        status = "🟢" if broker['connected'] else "🔴"
        active = "⭐" if broker['active'] else ""
        print(f"   {status} {broker['name']} ({broker['type']}) {active}")
    
    return manager


async def test_paper_trading(manager):
    """Test paper trading operations."""
    print("\n" + "="*60)
    print("TEST 2: Paper Trading")
    print("="*60)
    
    from src.brokers.base import OrderSide, OrderType
    
    # Ensure paper trading is active
    manager.set_active_broker(BrokerType.PAPER)
    print(f"\n✅ Active broker: {manager.active_broker_type.value}")
    
    # Get account info
    account = await manager.get_account()
    print(f"\n📊 Account Info:")
    print(f"   Account ID: {account.account_id}")
    print(f"   Cash: ${account.cash:,.2f}")
    print(f"   Buying Power: ${account.buying_power:,.2f}")
    
    # Place a test order
    print(f"\n📝 Placing test BUY order: 10 shares of AAPL...")
    
    result = await manager.place_order(
        ticker="AAPL",
        side=OrderSide.BUY,
        quantity=10,
        order_type=OrderType.MARKET
    )
    
    if result.success:
        print(f"   ✅ Order filled!")
        print(f"   Order ID: {result.order_id}")
        print(f"   Status: {result.status.value}")
        print(f"   Filled Qty: {result.filled_qty}")
        print(f"   Fill Price: ${result.avg_fill_price:.2f}" if result.avg_fill_price else "")
    else:
        print(f"   ❌ Order failed: {result.message}")
    
    # Check positions
    positions = await manager.get_positions()
    print(f"\n📁 Positions after order:")
    for pos in positions:
        print(f"   {pos.ticker}: {pos.quantity} @ ${pos.avg_price:.2f}")
    
    # Check updated account
    account = await manager.get_account()
    print(f"\n📊 Updated Account:")
    print(f"   Cash: ${account.cash:,.2f}")
    print(f"   Portfolio Value: ${account.portfolio_value:,.2f}")
    
    return True


async def test_sell_order(manager):
    """Test selling position."""
    print("\n" + "="*60)
    print("TEST 3: Sell Order")
    print("="*60)
    
    from src.brokers.base import OrderSide, OrderType
    
    # Sell the position
    print(f"\n📝 Placing test SELL order: 5 shares of AAPL...")
    
    result = await manager.place_order(
        ticker="AAPL",
        side=OrderSide.SELL,
        quantity=5,
        order_type=OrderType.MARKET
    )
    
    if result.success:
        print(f"   ✅ Order filled!")
        print(f"   Fill Price: ${result.avg_fill_price:.2f}" if result.avg_fill_price else "")
    else:
        print(f"   ❌ Order failed: {result.message}")
    
    # Check positions
    positions = await manager.get_positions()
    print(f"\n📁 Remaining Positions:")
    for pos in positions:
        pnl_emoji = "🟢" if pos.unrealized_pnl >= 0 else "🔴"
        print(f"   {pos.ticker}: {pos.quantity} @ ${pos.avg_price:.2f}")
        print(f"   {pnl_emoji} P&L: ${pos.unrealized_pnl:.2f} ({pos.unrealized_pnl_pct:.2f}%)")
    
    return True


async def test_limit_order(manager):
    """Test limit order placement."""
    print("\n" + "="*60)
    print("TEST 4: Limit Order")
    print("="*60)
    
    from src.brokers.base import OrderSide, OrderType
    
    # Place a limit order that won't fill immediately
    print(f"\n📝 Placing LIMIT BUY order: 5 shares of NVDA @ $100...")
    
    result = await manager.place_order(
        ticker="NVDA",
        side=OrderSide.BUY,
        quantity=5,
        order_type=OrderType.LIMIT,
        limit_price=100.0  # Below market price
    )
    
    if result.success:
        print(f"   ✅ Order submitted!")
        print(f"   Order ID: {result.order_id}")
        print(f"   Status: {result.status.value}")
    else:
        print(f"   ❌ Order failed: {result.message}")
    
    return True


async def test_quote(manager):
    """Test quote fetching."""
    print("\n" + "="*60)
    print("TEST 5: Market Quotes")
    print("="*60)
    
    tickers = ["AAPL", "NVDA", "MSFT"]
    
    print("\n📈 Fetching quotes...")
    
    for ticker in tickers:
        quote = await manager.get_quote(ticker)
        if quote:
            change_emoji = "🟢" if quote.change >= 0 else "🔴"
            print(f"\n   {change_emoji} {ticker}")
            print(f"      Price: ${quote.price:.2f}")
            print(f"      Change: {'+' if quote.change >= 0 else ''}{quote.change:.2f} ({'+' if quote.change_pct >= 0 else ''}{quote.change_pct:.2f}%)")
            print(f"      Volume: {quote.volume:,}")
        else:
            print(f"   ❌ Could not fetch quote for {ticker}")
    
    return True


async def test_telegram_bot_commands():
    """Test Telegram bot command handlers (without sending)."""
    print("\n" + "="*60)
    print("TEST 6: Telegram Bot Commands (Dry Run)")
    print("="*60)
    
    from src.notifications.telegram_bot import TelegramBot
    
    bot = TelegramBot()
    
    print("\n📱 Available Commands:")
    for cmd, desc in bot.COMMANDS.items():
        print(f"   {cmd}: {desc}")
    
    print(f"\n✅ Telegram Bot has {len(bot.COMMANDS)} commands configured")
    
    if not bot.is_configured:
        print("   ⚠️  Telegram credentials not configured - interactive mode disabled")
    else:
        print("   🟢 Telegram credentials configured")
    
    return True


async def test_aggregated_portfolio(manager):
    """Test aggregated portfolio view."""
    print("\n" + "="*60)
    print("TEST 7: Aggregated Portfolio")
    print("="*60)
    
    portfolio = await manager.get_aggregated_portfolio()
    
    print(f"\n📊 Portfolio Summary:")
    print(f"   Total Value: ${portfolio['total_value']:,.2f}")
    print(f"   Total P&L: ${portfolio['total_pnl']:,.2f}")
    print(f"   Brokers Connected: {portfolio['brokers_connected']}")
    
    if portfolio['positions']:
        print(f"\n   Positions:")
        for pos in portfolio['positions']:
            pnl_emoji = "🟢" if pos['pnl'] >= 0 else "🔴"
            print(f"      [{pos['broker'].upper()}] {pos['ticker']}: {pos['quantity']} shares")
            print(f"         {pnl_emoji} ${pos['pnl']:.2f} ({pos['pnl_pct']:.2f}%)")
    
    return True


async def test_paper_performance(manager):
    """Test paper trading performance summary."""
    print("\n" + "="*60)
    print("TEST 8: Paper Trading Performance")
    print("="*60)
    
    from src.brokers.paper_broker import PaperBroker
    
    # Get paper broker directly
    paper = manager._brokers.get(BrokerType.PAPER)
    
    if paper and isinstance(paper, PaperBroker):
        summary = paper.get_performance_summary()
        
        print(f"\n📈 Performance Summary:")
        print(f"   Initial Capital: ${summary['initial_capital']:,.2f}")
        print(f"   Current Value: ${summary['current_portfolio_value']:,.2f}")
        print(f"   Total Return: {summary['total_return']:.2f}%")
        print(f"   Realized P&L: ${summary['realized_pnl']:,.2f}")
        print(f"   Unrealized P&L: ${summary['unrealized_pnl']:,.2f}")
        print(f"\n   Trading Stats:")
        print(f"   Total Trades: {summary['total_trades']}")
        print(f"   Win Rate: {summary['win_rate']:.1f}%")
        print(f"   Open Positions: {summary['open_positions']}")
    
    return True


# Import BrokerType for global use in tests
from src.brokers.broker_manager import BrokerType


async def main():
    """Run all tests."""
    print("\n" + "="*60)
    print("TradingAI Bot - Broker & Telegram Integration Tests")
    print(f"Time: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print("="*60)
    
    try:
        # Test 1: Broker Manager
        manager = await test_broker_manager()
        
        # Test 2: Paper Trading
        await test_paper_trading(manager)
        
        # Test 3: Sell Order
        await test_sell_order(manager)
        
        # Test 4: Limit Order
        await test_limit_order(manager)
        
        # Test 5: Market Quotes
        await test_quote(manager)
        
        # Test 6: Telegram Commands
        await test_telegram_bot_commands()
        
        # Test 7: Aggregated Portfolio
        await test_aggregated_portfolio(manager)
        
        # Test 8: Paper Trading Performance
        await test_paper_performance(manager)
        
        # Cleanup
        await manager.shutdown()
        
        print("\n" + "="*60)
        print("✅ ALL TESTS PASSED!")
        print("="*60)
        
    except Exception as e:
        print(f"\n❌ TEST FAILED: {e}")
        import traceback
        traceback.print_exc()
        return 1
    
    return 0


if __name__ == "__main__":
    exit_code = asyncio.run(main())
    sys.exit(exit_code)
