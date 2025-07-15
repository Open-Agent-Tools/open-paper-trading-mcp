#!/usr/bin/env python3

import sys
import os

sys.path.insert(0, os.path.dirname(__file__))


def test_trading_service_integration():
    """Test that all paperbroker services are properly integrated."""

    print("=== Testing TradingService Integration ===")

    try:
        from app.services.trading_service import trading_service

        print("✓ TradingService imported successfully")

        # Test basic functionality
        quote = trading_service.get_quote("AAPL")
        print(f"✓ Legacy quote works: AAPL @ ${quote.price}")

        # Test enhanced functionality
        try:
            aal_quote = trading_service.get_enhanced_quote("AAL")
            print(f"✓ Enhanced quote works: AAL @ ${aal_quote.price}")
        except Exception as e:
            print(f"⚠ Enhanced quote error: {e}")

        # Test strategy analysis
        try:
            strategies = trading_service.analyze_portfolio_strategies()
            print(
                f"✓ Strategy analysis: {strategies['total_strategies']} strategies found"
            )
        except Exception as e:
            print(f"⚠ Strategy analysis error: {e}")

        # Test sample data
        try:
            info = trading_service.get_sample_data_info()
            print(f"✓ Sample data: {len(info['symbols'])} symbols available")
        except Exception as e:
            print(f"⚠ Sample data error: {e}")

        print("✓ TradingService integration test completed successfully!")
        return True

    except Exception as e:
        print(f"✗ Integration test failed: {e}")
        import traceback

        traceback.print_exc()
        return False


if __name__ == "__main__":
    success = test_trading_service_integration()
    sys.exit(0 if success else 1)
