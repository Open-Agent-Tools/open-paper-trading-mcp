#!/usr/bin/env python3
"""
Test script for the database-backed test data adapter.

This script tests the new TestDataDBQuoteAdapter to ensure it works correctly
with the database-stored test data.
"""

import asyncio
import sys
from pathlib import Path

# Add the app directory to the path
sys.path.insert(0, str(Path(__file__).parent.parent))

from app.adapters.test_data_db import TestDataDBQuoteAdapter
from app.models.assets import Stock, asset_factory
from app.services.trading_service import TradingService


async def test_db_adapter():
    """Test the database-backed test data adapter."""
    print("Testing Database-Backed Test Data Adapter")
    print("=" * 50)

    # Create adapter
    adapter = TestDataDBQuoteAdapter(current_date="2017-03-24", scenario="default")

    # Test basic functionality
    print("\n1. Testing adapter initialization...")
    print(f"Adapter name: {adapter.name}")
    print(f"Current date: {adapter.current_date}")
    print(f"Scenario: {adapter.scenario}")

    # Test available dates
    print("\n2. Testing available dates...")
    available_dates = await adapter.get_available_dates()
    print(f"Available dates: {available_dates}")

    # Test available scenarios
    print("\n3. Testing available scenarios...")
    available_scenarios = await adapter.get_available_scenarios()
    print(f"Available scenarios: {available_scenarios}")

    # Test stock quote
    print("\n4. Testing stock quote...")
    stock = Stock(symbol="AAL")
    stock_quote = await adapter.get_quote(stock)

    if stock_quote:
        print(f"Stock quote for {stock.symbol}:")
        print(f"  Price: ${stock_quote.price}")
        print(f"  Bid: ${stock_quote.bid}")
        print(f"  Ask: ${stock_quote.ask}")
        print(f"  Volume: {stock_quote.volume}")
        print(f"  Date: {stock_quote.quote_date}")
    else:
        print(f"No stock quote found for {stock.symbol}")

    # Test option quote
    print("\n5. Testing option quote...")
    option_symbol = "AAL170203P00047000"
    option_asset = asset_factory(option_symbol)
    option_quote = await adapter.get_quote(option_asset)

    if option_quote:
        print(f"Option quote for {option_symbol}:")
        print(f"  Price: ${option_quote.price}")
        print(f"  Bid: ${option_quote.bid}")
        print(f"  Ask: ${option_quote.ask}")
        print(f"  Underlying price: ${option_quote.underlying_price}")
        print(f"  Date: {option_quote.quote_date}")
        if hasattr(option_quote, "delta") and option_quote.delta:
            print(f"  Delta: {option_quote.delta}")
    else:
        print(f"No option quote found for {option_symbol}")

    # Test performance metrics
    print("\n6. Testing performance metrics...")
    metrics = adapter.get_performance_metrics()
    print(f"Performance metrics: {metrics}")

    # Test sample data info
    print("\n7. Testing sample data info...")
    sample_info = adapter.get_sample_data_info()
    print(f"Sample data info: {sample_info}")

    # Test available symbols
    print("\n8. Testing available symbols...")
    symbols = adapter.get_available_symbols()
    print(f"Available symbols: {symbols}")

    print("\n" + "=" * 50)
    print("Database adapter test completed!")


async def test_trading_service_integration():
    """Test the integration with TradingService."""
    print("\nTesting TradingService Integration")
    print("=" * 50)

    # Create TradingService with the new adapter
    adapter = TestDataDBQuoteAdapter(current_date="2017-03-24", scenario="default")
    trading_service = TradingService(quote_adapter=adapter)

    # Test getting quotes through TradingService
    print("\n1. Testing quote retrieval through TradingService...")

    # Test stock quote
    stock_quote = await trading_service.get_quote("AAL")
    if stock_quote:
        print(f"Stock quote for AAL: ${stock_quote.price}")
    else:
        print("No stock quote found for AAL")

    # Test option quote
    option_quote = await trading_service.get_quote("AAL170203P00047000")
    if option_quote:
        print(f"Option quote for AAL170203P00047000: ${option_quote.price}")
    else:
        print("No option quote found for AAL170203P00047000")

    print("\n" + "=" * 50)
    print("TradingService integration test completed!")


async def main():
    """Main test runner."""
    try:
        await test_db_adapter()
        await test_trading_service_integration()

        print("\n✅ All tests passed!")

    except Exception as e:
        print(f"\n❌ Test failed: {e}")
        import traceback

        traceback.print_exc()
        sys.exit(1)


if __name__ == "__main__":
    asyncio.run(main())
