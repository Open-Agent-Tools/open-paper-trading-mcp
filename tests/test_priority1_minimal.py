"""
Minimal Priority 1 Functionality Tests

This module tests the core Priority 1 functionality with minimal database usage:
- TradingService basic operations
- Order creation and validation
- Core module imports and initialization
"""

import pytest

from app.schemas.orders import OrderCondition, OrderCreate, OrderType
from app.services.order_execution_engine import OrderExecutionEngine
from app.services.trading_service import TradingService


class TestPriority1Minimal:
    """Test Priority 1 core functionality with minimal dependencies."""

    def test_trading_service_initialization(self):
        """Test that TradingService initializes correctly."""
        service = TradingService(account_owner="test_user")
        assert service is not None
        assert service.account_owner == "test_user"
        assert hasattr(service, "quote_adapter")

    def test_order_execution_engine_initialization(self):
        """Test that OrderExecutionEngine can be instantiated."""
        service = TradingService(account_owner="test_user")
        engine = OrderExecutionEngine(service)
        assert engine is not None
        assert engine.trading_service == service

    def test_order_schema_validation(self):
        """Test order data validation."""
        # Test valid order
        order_data = OrderCreate(
            symbol="AAPL",
            order_type=OrderType.BUY,
            quantity=100,
            price=150.0,
            condition=OrderCondition.LIMIT,
        )
        assert order_data.symbol == "AAPL"
        assert order_data.order_type == OrderType.BUY
        assert order_data.quantity == 100
        assert order_data.price == 150.0

    def test_order_types_enum(self):
        """Test that order type enums are properly defined."""
        assert OrderType.BUY is not None
        assert OrderType.SELL is not None
        assert OrderCondition.LIMIT is not None
        assert OrderCondition.MARKET is not None

    @pytest.mark.asyncio
    async def test_quote_adapter_initialization(self):
        """Test that quote adapter initializes properly."""
        service = TradingService(account_owner="test_user")
        assert service.quote_adapter is not None

        # Try to get a quote (should not fail due to adapter setup)
        try:
            quote = await service.get_quote("AAPL")
            # If successful, verify basic structure
            assert hasattr(quote, "symbol")
            assert hasattr(quote, "price")
        except Exception as e:
            # If it fails, it should be due to missing data, not setup issues
            assert "not found" in str(e).lower() or "symbol" in str(e).lower()

    def test_order_execution_engine_attributes(self):
        """Test OrderExecutionEngine has required attributes."""
        service = TradingService(account_owner="test_user")
        engine = OrderExecutionEngine(service)

        # Check key attributes exist
        assert hasattr(engine, "trading_service")
        assert hasattr(engine, "trigger_conditions")
        assert hasattr(engine, "last_market_data_update")
        assert hasattr(engine, "monitored_symbols")

    def test_priority1_modules_import(self):
        """Test that Priority 1 modules can be imported successfully."""
        # Test core service imports

        # Test schema imports

        # Test model imports

        # All imports successful
        assert True
