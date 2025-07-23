"""
Comprehensive tests for app/utils/schema_converters.py

Tests schema conversion logic, utility functions, and all converter classes
with proper mocking of dependencies and external services.
"""

import pytest
from datetime import datetime, date
from decimal import Decimal
from typing import Optional
from unittest.mock import AsyncMock, MagicMock, Mock, patch

from app.models.assets import Stock, Option, OptionType, asset_factory
from app.models.database.trading import Account as DBAccount
from app.models.database.trading import Order as DBOrder
from app.models.database.trading import Position as DBPosition
from app.schemas.accounts import Account
from app.schemas.orders import Order, OrderCondition, OrderStatus, OrderType
from app.schemas.positions import Position
from app.schemas.trading import StockQuote

# Import the module under test
from app.utils.schema_converters import (
    AccountConverter,
    ConversionError,
    OrderConverter,
    PositionConverter,
    SchemaConverter,
    db_account_to_schema,
    db_order_to_schema,
    db_position_to_schema,
    schema_account_to_db,
    schema_order_to_db,
    schema_position_to_db,
)


class TestSchemaConverter:
    """Test the abstract base SchemaConverter class."""

    def test_schema_converter_is_abstract(self):
        """Test that SchemaConverter cannot be instantiated directly."""
        with pytest.raises(TypeError):
            SchemaConverter()

    def test_schema_converter_abstract_methods(self):
        """Test that abstract methods are properly defined."""
        assert hasattr(SchemaConverter, "to_schema")
        assert hasattr(SchemaConverter, "to_database")
        
        # Check that they are abstract
        assert getattr(SchemaConverter.to_schema, "__isabstractmethod__", False)
        assert getattr(SchemaConverter.to_database, "__isabstractmethod__", False)

    def test_schema_converter_generic_types(self):
        """Test that SchemaConverter is properly generic."""
        # This tests that the class accepts type parameters
        assert hasattr(SchemaConverter, "__orig_bases__")


class TestAccountConverter:
    """Test AccountConverter functionality."""

    def setup_method(self):
        """Set up test fixtures."""
        self.mock_trading_service = AsyncMock()
        self.converter = AccountConverter(self.mock_trading_service)
        self.converter_no_service = AccountConverter()

    def create_db_account(self, **kwargs):
        """Create a mock database account."""
        defaults = {
            "id": "acc_123",
            "owner": "testuser",
            "cash_balance": 10000.0,
            "created_at": datetime(2023, 6, 15, 10, 0, 0),
        }
        defaults.update(kwargs)
        
        db_account = MagicMock(spec=DBAccount)
        for key, value in defaults.items():
            setattr(db_account, key, value)
        
        return db_account

    def create_schema_account(self, **kwargs):
        """Create a schema account."""
        defaults = {
            "id": "acc_123",
            "owner": "testuser",
            "cash_balance": 10000.0,
            "name": "testuser",
            "positions": [],
        }
        defaults.update(kwargs)
        
        return Account(**defaults)

    @pytest.mark.asyncio
    async def test_to_schema_basic_conversion(self):
        """Test basic account conversion from DB to schema."""
        db_account = self.create_db_account()
        db_account.positions = []
        
        result = await self.converter.to_schema(db_account)
        
        assert isinstance(result, Account)
        assert result.id == "acc_123"
        assert result.owner == "testuser"
        assert result.cash_balance == 10000.0
        assert result.name == "testuser"  # Uses owner as name
        assert result.positions == []

    @pytest.mark.asyncio
    async def test_to_schema_without_trading_service(self):
        """Test account conversion without trading service."""
        db_account = self.create_db_account()
        
        result = await self.converter_no_service.to_schema(db_account)
        
        assert isinstance(result, Account)
        assert result.positions == []

    @pytest.mark.asyncio
    async def test_to_schema_with_positions(self):
        """Test account conversion with positions."""
        # Create mock positions
        mock_position_1 = MagicMock(spec=DBPosition)
        mock_position_2 = MagicMock(spec=DBPosition)
        
        db_account = self.create_db_account()
        db_account.positions = [mock_position_1, mock_position_2]
        
        # Mock position converter
        mock_schema_position_1 = MagicMock(spec=Position)
        mock_schema_position_2 = MagicMock(spec=Position)
        
        with patch("app.utils.schema_converters.PositionConverter") as MockPositionConverter:
            mock_converter = MockPositionConverter.return_value
            mock_converter.to_schema = AsyncMock(side_effect=[
                mock_schema_position_1,
                mock_schema_position_2
            ])
            
            result = await self.converter.to_schema(db_account)
            
            assert len(result.positions) == 2
            assert result.positions[0] == mock_schema_position_1
            assert result.positions[1] == mock_schema_position_2
            
            # Verify position converter was called correctly
            MockPositionConverter.assert_called_once_with(self.mock_trading_service)
            assert mock_converter.to_schema.call_count == 2

    @pytest.mark.asyncio
    async def test_to_schema_no_positions_attribute(self):
        """Test account conversion when db_account has no positions attribute."""
        db_account = self.create_db_account()
        # Remove positions attribute
        del db_account.positions
        
        result = await self.converter.to_schema(db_account)
        
        assert result.positions == []

    def test_to_database_basic_conversion(self):
        """Test basic account conversion from schema to DB."""
        schema_account = self.create_schema_account()
        
        result = self.converter.to_database(schema_account)
        
        assert isinstance(result, DBAccount)
        assert result.id == "acc_123"
        assert result.owner == "testuser"
        assert result.cash_balance == 10000.0

    def test_to_database_with_name_fallback(self):
        """Test account conversion using name when owner is None."""
        schema_account = self.create_schema_account(owner=None, name="fallback_name")
        
        result = self.converter.to_database(schema_account)
        
        assert result.owner == "fallback_name"

    def test_to_database_with_unknown_fallback(self):
        """Test account conversion with unknown fallback."""
        schema_account = self.create_schema_account(owner=None, name=None)
        
        result = self.converter.to_database(schema_account)
        
        assert result.owner == "unknown"

    def test_converter_initialization(self):
        """Test converter initialization with and without trading service."""
        converter_with_service = AccountConverter(self.mock_trading_service)
        assert converter_with_service.trading_service == self.mock_trading_service
        
        converter_without_service = AccountConverter()
        assert converter_without_service.trading_service is None


class TestOrderConverter:
    """Test OrderConverter functionality."""

    def setup_method(self):
        """Set up test fixtures."""
        self.converter = OrderConverter()

    def create_db_order(self, **kwargs):
        """Create a mock database order."""
        defaults = {
            "id": "order_123",
            "account_id": "acc_123",
            "symbol": "AAPL",
            "order_type": OrderType.BUY,
            "quantity": 100,
            "price": 155.0,
            "status": OrderStatus.PENDING,
            "created_at": datetime(2023, 6, 15, 10, 0, 0),
            "filled_at": None,
            "stop_price": None,
            "trail_percent": None,
            "trail_amount": None,
        }
        defaults.update(kwargs)
        
        db_order = MagicMock(spec=DBOrder)
        for key, value in defaults.items():
            setattr(db_order, key, value)
        
        return db_order

    def create_schema_order(self, **kwargs):
        """Create a schema order."""
        defaults = {
            "id": "order_123",
            "symbol": "AAPL",
            "order_type": OrderType.BUY,
            "quantity": 100,
            "price": 155.0,
            "status": OrderStatus.PENDING,
            "condition": OrderCondition.LIMIT,
            "created_at": datetime(2023, 6, 15, 10, 0, 0),
            "filled_at": None,
            "legs": [],
            "net_price": 155.0,
            "stop_price": None,
            "trail_percent": None,
            "trail_amount": None,
        }
        defaults.update(kwargs)
        
        return Order(**defaults)

    @pytest.mark.asyncio
    async def test_to_schema_basic_conversion(self):
        """Test basic order conversion from DB to schema."""
        db_order = self.create_db_order()
        
        result = await self.converter.to_schema(db_order)
        
        assert isinstance(result, Order)
        assert result.id == "order_123"
        assert result.symbol == "AAPL"
        assert result.order_type == OrderType.BUY
        assert result.quantity == 100
        assert result.price == 155.0
        assert result.status == OrderStatus.PENDING
        assert result.condition == OrderCondition.MARKET  # Default
        assert result.legs == []
        assert result.net_price == 155.0  # Same as price for simple orders

    @pytest.mark.asyncio
    async def test_to_schema_with_stop_fields(self):
        """Test order conversion with stop price and trail fields."""
        db_order = self.create_db_order(
            stop_price=150.0,
            trail_percent=5.0,
            trail_amount=2.5
        )
        
        result = await self.converter.to_schema(db_order)
        
        assert result.stop_price == 150.0
        assert result.trail_percent == 5.0
        assert result.trail_amount == 2.5

    @pytest.mark.asyncio
    async def test_to_schema_with_filled_at(self):
        """Test order conversion with filled_at timestamp."""
        filled_time = datetime(2023, 6, 15, 10, 30, 0)
        db_order = self.create_db_order(
            status=OrderStatus.FILLED,
            filled_at=filled_time
        )
        
        result = await self.converter.to_schema(db_order)
        
        assert result.status == OrderStatus.FILLED
        assert result.filled_at == filled_time

    def test_to_database_basic_conversion(self):
        """Test basic order conversion from schema to DB."""
        schema_order = self.create_schema_order()
        
        result = self.converter.to_database(schema_order, account_id="acc_123")
        
        assert isinstance(result, DBOrder)
        assert result.id == "order_123"
        assert result.account_id == "acc_123"
        assert result.symbol == "AAPL"
        assert result.order_type == OrderType.BUY
        assert result.quantity == 100
        assert result.price == 155.0
        assert result.status == OrderStatus.PENDING

    def test_to_database_missing_account_id(self):
        """Test order conversion fails without account_id."""
        schema_order = self.create_schema_order()
        
        with pytest.raises(ConversionError) as exc_info:
            self.converter.to_database(schema_order)
        
        assert "account_id is required" in str(exc_info.value)

    def test_to_database_with_timestamps(self):
        """Test order conversion preserves timestamps."""
        created_time = datetime(2023, 6, 15, 10, 0, 0)
        filled_time = datetime(2023, 6, 15, 10, 30, 0)
        
        schema_order = self.create_schema_order(
            status=OrderStatus.FILLED,
            created_at=created_time,
            filled_at=filled_time
        )
        
        result = self.converter.to_database(schema_order, account_id="acc_123")
        
        assert result.created_at == created_time
        assert result.filled_at == filled_time


class TestPositionConverter:
    """Test PositionConverter functionality."""

    def setup_method(self):
        """Set up test fixtures."""
        self.mock_trading_service = AsyncMock()
        self.converter = PositionConverter(self.mock_trading_service)
        self.converter_no_service = PositionConverter()

    def create_db_position(self, **kwargs):
        """Create a mock database position."""
        defaults = {
            "account_id": "acc_123",
            "symbol": "AAPL",
            "quantity": 100,
            "avg_price": 150.0,
        }
        defaults.update(kwargs)
        
        db_position = MagicMock(spec=DBPosition)
        for key, value in defaults.items():
            setattr(db_position, key, value)
        
        return db_position

    def create_schema_position(self, **kwargs):
        """Create a schema position."""
        defaults = {
            "symbol": "AAPL",
            "quantity": 100,
            "avg_price": 150.0,
            "current_price": 155.0,
            "unrealized_pnl": 500.0,
            "realized_pnl": 0.0,
            "asset": None,
        }
        defaults.update(kwargs)
        
        return Position(**defaults)

    @pytest.mark.asyncio
    async def test_to_schema_basic_conversion(self):
        """Test basic position conversion from DB to schema."""
        db_position = self.create_db_position()
        current_price = 155.0
        
        with patch("app.utils.schema_converters.asset_factory") as mock_asset_factory:
            mock_asset = MagicMock(spec=Stock)
            mock_asset_factory.return_value = mock_asset
            
            result = await self.converter.to_schema(db_position, current_price)
            
            assert isinstance(result, Position)
            assert result.symbol == "AAPL"
            assert result.quantity == 100
            assert result.avg_price == 150.0
            assert result.current_price == 155.0
            assert result.unrealized_pnl == 500.0  # (155 - 150) * 100
            assert result.realized_pnl == 0.0
            assert result.asset == mock_asset

    @pytest.mark.asyncio
    async def test_to_schema_with_trading_service_quote(self):
        """Test position conversion using trading service for current price."""
        db_position = self.create_db_position()
        
        # Mock quote from trading service
        mock_quote = MagicMock(spec=StockQuote)
        mock_quote.price = 160.0
        self.mock_trading_service.get_quote.return_value = mock_quote
        
        with patch("app.utils.schema_converters.asset_factory") as mock_asset_factory:
            mock_asset = MagicMock(spec=Stock)
            mock_asset_factory.return_value = mock_asset
            
            result = await self.converter.to_schema(db_position)
            
            assert result.current_price == 160.0
            assert result.unrealized_pnl == 1000.0  # (160 - 150) * 100
            self.mock_trading_service.get_quote.assert_called_once_with("AAPL")

    @pytest.mark.asyncio
    async def test_to_schema_trading_service_quote_error(self):
        """Test position conversion when trading service quote fails."""
        db_position = self.create_db_position()
        
        # Mock trading service to raise exception
        self.mock_trading_service.get_quote.side_effect = Exception("Quote failed")
        
        with patch("app.utils.schema_converters.asset_factory") as mock_asset_factory:
            mock_asset = MagicMock(spec=Stock)
            mock_asset_factory.return_value = mock_asset
            
            result = await self.converter.to_schema(db_position)
            
            # Should fall back to avg_price
            assert result.current_price == 150.0
            assert result.unrealized_pnl == 0.0

    @pytest.mark.asyncio
    async def test_to_schema_without_trading_service(self):
        """Test position conversion without trading service."""
        db_position = self.create_db_position()
        current_price = 155.0
        
        with patch("app.utils.schema_converters.asset_factory") as mock_asset_factory:
            mock_asset = MagicMock(spec=Stock)
            mock_asset_factory.return_value = mock_asset
            
            result = await self.converter_no_service.to_schema(db_position, current_price)
            
            assert result.current_price == 155.0
            assert result.unrealized_pnl == 500.0

    @pytest.mark.asyncio
    async def test_to_schema_option_asset(self):
        """Test position conversion with option asset."""
        db_position = self.create_db_position(symbol="AAPL_230616C00150000")
        
        with patch("app.utils.schema_converters.asset_factory") as mock_asset_factory:
            # Mock option asset
            mock_underlying = MagicMock(spec=Stock)
            mock_underlying.symbol = "AAPL"
            
            mock_option = MagicMock(spec=Option)
            # Add hasattr behavior for the asset properties
            def mock_hasattr(obj, attr):
                return attr in ["option_type", "strike", "expiration", "underlying"]
            
            with patch("builtins.hasattr", side_effect=mock_hasattr):
                mock_option.option_type = OptionType.CALL
                mock_option.strike = 150.0
                mock_option.expiration = date(2023, 6, 16)
                mock_option.underlying = mock_underlying
                
                mock_asset_factory.return_value = mock_option
                
                result = await self.converter.to_schema(db_position, 5.25)
                
                assert result.option_type == OptionType.CALL
                assert result.strike == 150.0
                assert result.expiration_date == date(2023, 6, 16)
                assert result.underlying_symbol == "AAPL"

    @pytest.mark.asyncio
    async def test_to_schema_option_without_underlying(self):
        """Test position conversion with option that has no underlying."""
        db_position = self.create_db_position(symbol="AAPL_230616C00150000")
        
        with patch("app.utils.schema_converters.asset_factory") as mock_asset_factory:
            mock_option = MagicMock(spec=Option)
            # Add hasattr behavior for the asset properties
            def mock_hasattr(obj, attr):
                return attr in ["option_type", "strike", "expiration", "underlying"]
            
            with patch("builtins.hasattr", side_effect=mock_hasattr):
                mock_option.option_type = OptionType.CALL
                mock_option.strike = 150.0
                mock_option.expiration = date(2023, 6, 16)
                mock_option.underlying = None
                
                mock_asset_factory.return_value = mock_option
                
                result = await self.converter.to_schema(db_position, 5.25)
                
                assert result.option_type == OptionType.CALL
                assert result.strike == 150.0
                assert result.expiration_date == date(2023, 6, 16)
                assert result.underlying_symbol is None

    @pytest.mark.asyncio
    async def test_to_schema_no_asset(self):
        """Test position conversion when asset_factory returns None."""
        db_position = self.create_db_position()
        
        with patch("app.utils.schema_converters.asset_factory") as mock_asset_factory:
            mock_asset_factory.return_value = None
            
            result = await self.converter.to_schema(db_position, 155.0)
            
            assert result.asset is None
            assert result.option_type is None
            assert result.strike is None
            assert result.expiration_date is None
            assert result.underlying_symbol is None

    def test_to_schema_sync_basic(self):
        """Test synchronous version of to_schema."""
        db_position = self.create_db_position()
        current_price = 155.0
        
        with patch("app.utils.schema_converters.asset_factory") as mock_asset_factory:
            mock_asset = MagicMock(spec=Stock)
            mock_asset_factory.return_value = mock_asset
            
            result = self.converter.to_schema_sync(db_position, current_price)
            
            assert isinstance(result, Position)
            assert result.symbol == "AAPL"
            assert result.current_price == 155.0
            assert result.unrealized_pnl == 500.0

    def test_to_schema_sync_fallback_price(self):
        """Test synchronous to_schema falls back to avg_price."""
        db_position = self.create_db_position()
        
        with patch("app.utils.schema_converters.asset_factory") as mock_asset_factory:
            mock_asset = MagicMock(spec=Stock)
            mock_asset_factory.return_value = mock_asset
            
            result = self.converter.to_schema_sync(db_position)
            
            assert result.current_price == 150.0  # avg_price
            assert result.unrealized_pnl == 0.0

    def test_to_database_basic_conversion(self):
        """Test basic position conversion from schema to DB."""
        schema_position = self.create_schema_position()
        
        result = self.converter.to_database(schema_position, account_id="acc_123")
        
        assert isinstance(result, DBPosition)
        assert result.account_id == "acc_123"
        assert result.symbol == "AAPL"
        assert result.quantity == 100
        assert result.avg_price == 150.0

    def test_to_database_missing_account_id(self):
        """Test position conversion fails without account_id."""
        schema_position = self.create_schema_position()
        
        with pytest.raises(ConversionError) as exc_info:
            self.converter.to_database(schema_position)
        
        assert "account_id is required" in str(exc_info.value)

    def test_converter_initialization(self):
        """Test converter initialization with and without trading service."""
        converter_with_service = PositionConverter(self.mock_trading_service)
        assert converter_with_service.trading_service == self.mock_trading_service
        
        converter_without_service = PositionConverter()
        assert converter_without_service.trading_service is None


class TestConversionError:
    """Test ConversionError exception."""

    def test_conversion_error_is_exception(self):
        """Test that ConversionError is a proper exception."""
        assert issubclass(ConversionError, Exception)

    def test_conversion_error_message(self):
        """Test ConversionError with custom message."""
        message = "Test conversion error"
        error = ConversionError(message)
        assert str(error) == message

    def test_conversion_error_raised(self):
        """Test that ConversionError can be raised and caught."""
        with pytest.raises(ConversionError) as exc_info:
            raise ConversionError("Test error")
        
        assert "Test error" in str(exc_info.value)


class TestConvenienceFunctions:
    """Test convenience functions for direct usage."""

    def setup_method(self):
        """Set up test fixtures."""
        self.mock_trading_service = AsyncMock()

    @pytest.mark.asyncio
    @patch("app.utils.schema_converters.AccountConverter")
    async def test_db_account_to_schema(self, MockAccountConverter):
        """Test db_account_to_schema convenience function."""
        mock_db_account = MagicMock(spec=DBAccount)
        mock_schema_account = MagicMock(spec=Account)
        
        mock_converter = MockAccountConverter.return_value
        mock_converter.to_schema = AsyncMock(return_value=mock_schema_account)
        
        result = await db_account_to_schema(mock_db_account, self.mock_trading_service)
        
        assert result == mock_schema_account
        MockAccountConverter.assert_called_once_with(self.mock_trading_service)
        mock_converter.to_schema.assert_called_once_with(mock_db_account)

    @pytest.mark.asyncio
    @patch("app.utils.schema_converters.AccountConverter")
    async def test_db_account_to_schema_no_service(self, MockAccountConverter):
        """Test db_account_to_schema without trading service."""
        mock_db_account = MagicMock(spec=DBAccount)
        mock_schema_account = MagicMock(spec=Account)
        
        mock_converter = MockAccountConverter.return_value
        mock_converter.to_schema = AsyncMock(return_value=mock_schema_account)
        
        result = await db_account_to_schema(mock_db_account)
        
        assert result == mock_schema_account
        MockAccountConverter.assert_called_once_with(None)

    @patch("app.utils.schema_converters.AccountConverter")
    def test_schema_account_to_db(self, MockAccountConverter):
        """Test schema_account_to_db convenience function."""
        mock_schema_account = MagicMock(spec=Account)
        mock_db_account = MagicMock(spec=DBAccount)
        
        mock_converter = MockAccountConverter.return_value
        mock_converter.to_database.return_value = mock_db_account
        
        result = schema_account_to_db(mock_schema_account)
        
        assert result == mock_db_account
        MockAccountConverter.assert_called_once_with()
        mock_converter.to_database.assert_called_once_with(mock_schema_account)

    @pytest.mark.asyncio
    @patch("app.utils.schema_converters.OrderConverter")
    async def test_db_order_to_schema(self, MockOrderConverter):
        """Test db_order_to_schema convenience function."""
        mock_db_order = MagicMock(spec=DBOrder)
        mock_schema_order = MagicMock(spec=Order)
        
        mock_converter = MockOrderConverter.return_value
        mock_converter.to_schema = AsyncMock(return_value=mock_schema_order)
        
        result = await db_order_to_schema(mock_db_order)
        
        assert result == mock_schema_order
        MockOrderConverter.assert_called_once_with()
        mock_converter.to_schema.assert_called_once_with(mock_db_order)

    @patch("app.utils.schema_converters.OrderConverter")
    def test_schema_order_to_db(self, MockOrderConverter):
        """Test schema_order_to_db convenience function."""
        mock_schema_order = MagicMock(spec=Order)
        mock_db_order = MagicMock(spec=DBOrder)
        
        mock_converter = MockOrderConverter.return_value
        mock_converter.to_database.return_value = mock_db_order
        
        result = schema_order_to_db(mock_schema_order, "acc_123")
        
        assert result == mock_db_order
        MockOrderConverter.assert_called_once_with()
        mock_converter.to_database.assert_called_once_with(mock_schema_order, account_id="acc_123")

    @pytest.mark.asyncio
    @patch("app.utils.schema_converters.PositionConverter")
    async def test_db_position_to_schema(self, MockPositionConverter):
        """Test db_position_to_schema convenience function."""
        mock_db_position = MagicMock(spec=DBPosition)
        mock_schema_position = MagicMock(spec=Position)
        
        mock_converter = MockPositionConverter.return_value
        mock_converter.to_schema = AsyncMock(return_value=mock_schema_position)
        
        result = await db_position_to_schema(
            mock_db_position, 
            self.mock_trading_service, 
            155.0
        )
        
        assert result == mock_schema_position
        MockPositionConverter.assert_called_once_with(self.mock_trading_service)
        mock_converter.to_schema.assert_called_once_with(mock_db_position, 155.0)

    @pytest.mark.asyncio
    @patch("app.utils.schema_converters.PositionConverter")
    async def test_db_position_to_schema_defaults(self, MockPositionConverter):
        """Test db_position_to_schema with default parameters."""
        mock_db_position = MagicMock(spec=DBPosition)
        mock_schema_position = MagicMock(spec=Position)
        
        mock_converter = MockPositionConverter.return_value
        mock_converter.to_schema = AsyncMock(return_value=mock_schema_position)
        
        result = await db_position_to_schema(mock_db_position)
        
        assert result == mock_schema_position
        MockPositionConverter.assert_called_once_with(None)
        mock_converter.to_schema.assert_called_once_with(mock_db_position, None)

    @patch("app.utils.schema_converters.PositionConverter")
    def test_schema_position_to_db(self, MockPositionConverter):
        """Test schema_position_to_db convenience function."""
        mock_schema_position = MagicMock(spec=Position)
        mock_db_position = MagicMock(spec=DBPosition)
        
        mock_converter = MockPositionConverter.return_value
        mock_converter.to_database.return_value = mock_db_position
        
        result = schema_position_to_db(mock_schema_position, "acc_123")
        
        assert result == mock_db_position
        MockPositionConverter.assert_called_once_with()
        mock_converter.to_database.assert_called_once_with(mock_schema_position, account_id="acc_123")


class TestEdgeCases:
    """Test edge cases and error conditions."""

    def setup_method(self):
        """Set up test fixtures."""
        self.mock_trading_service = AsyncMock()

    @pytest.mark.asyncio
    async def test_position_converter_asset_factory_exception(self):
        """Test position converter when asset_factory raises exception."""
        converter = PositionConverter()
        db_position = MagicMock(spec=DBPosition)
        db_position.symbol = "INVALID_SYMBOL"
        db_position.quantity = 100
        db_position.avg_price = 150.0
        
        with patch("app.utils.schema_converters.asset_factory") as mock_asset_factory:
            mock_asset_factory.side_effect = Exception("Asset creation failed")
            
            # The current implementation doesn't catch asset_factory exceptions,
            # so this should raise an exception
            with pytest.raises(Exception, match="Asset creation failed"):
                await converter.to_schema(db_position, 155.0)

    @pytest.mark.asyncio
    async def test_account_converter_position_conversion_error(self):
        """Test account converter when position conversion fails."""
        converter = AccountConverter(self.mock_trading_service)
        db_account = MagicMock(spec=DBAccount)
        db_account.id = "acc_123"
        db_account.owner = "testuser" 
        db_account.cash_balance = 10000.0
        
        mock_position = MagicMock(spec=DBPosition)
        db_account.positions = [mock_position]
        
        with patch("app.utils.schema_converters.PositionConverter") as MockPositionConverter:
            mock_converter = MockPositionConverter.return_value
            mock_converter.to_schema.side_effect = Exception("Position conversion failed")
            
            # Should propagate the exception
            with pytest.raises(Exception) as exc_info:
                await converter.to_schema(db_account)
            
            assert "Position conversion failed" in str(exc_info.value)

    def test_order_converter_with_none_values(self):
        """Test order converter with None values in database model."""
        converter = OrderConverter()
        db_order = MagicMock(spec=DBOrder)
        db_order.id = None
        db_order.symbol = "AAPL"
        db_order.order_type = OrderType.BUY
        db_order.quantity = 100
        db_order.price = None
        db_order.status = OrderStatus.PENDING
        db_order.created_at = None
        db_order.filled_at = None
        db_order.stop_price = None
        db_order.trail_percent = None
        db_order.trail_amount = None
        
        # Should handle None values gracefully
        result = converter.to_database(
            Order(
                id=None,
                symbol="AAPL",
                order_type=OrderType.BUY,
                quantity=100,
                price=None,
                status=OrderStatus.PENDING,
                condition=OrderCondition.MARKET,
                created_at=None,
                filled_at=None,
                legs=[],
                net_price=None,
                stop_price=None,
                trail_percent=None,
                trail_amount=None,
            ),
            account_id="acc_123"
        )
        
        assert result.id is None
        assert result.price is None

    @pytest.mark.asyncio
    async def test_position_converter_negative_quantity(self):
        """Test position converter with negative quantity (short position)."""
        converter = PositionConverter()
        db_position = MagicMock(spec=DBPosition)
        db_position.symbol = "AAPL"
        db_position.quantity = -100  # Short position
        db_position.avg_price = 150.0
        
        with patch("app.utils.schema_converters.asset_factory") as mock_asset_factory:
            mock_asset = MagicMock(spec=Stock)
            mock_asset_factory.return_value = mock_asset
            
            result = await converter.to_schema(db_position, 155.0)
            
            # For short position, P&L calculation should be inverted
            assert result.quantity == -100
            assert result.unrealized_pnl == -500.0  # (155 - 150) * -100

    @pytest.mark.asyncio
    async def test_position_converter_zero_quantity(self):
        """Test position converter with zero quantity."""
        converter = PositionConverter()
        db_position = MagicMock(spec=DBPosition)
        db_position.symbol = "AAPL"
        db_position.quantity = 0
        db_position.avg_price = 150.0
        
        with patch("app.utils.schema_converters.asset_factory") as mock_asset_factory:
            mock_asset = MagicMock(spec=Stock)
            mock_asset_factory.return_value = mock_asset
            
            result = await converter.to_schema(db_position, 155.0)
            
            assert result.quantity == 0
            assert result.unrealized_pnl == 0.0


class TestTypeChecking:
    """Test type checking and validation."""

    def test_converter_generic_types(self):
        """Test that converters properly implement generic types."""
        account_converter = AccountConverter()
        order_converter = OrderConverter()
        position_converter = PositionConverter()
        
        # These should be instances of SchemaConverter with appropriate types
        assert isinstance(account_converter, SchemaConverter)
        assert isinstance(order_converter, SchemaConverter)
        assert isinstance(position_converter, SchemaConverter)

    def test_type_checking_imports(self):
        """Test that TYPE_CHECKING imports work correctly."""
        # This tests that the TYPE_CHECKING block doesn't cause runtime errors
        from app.utils.schema_converters import AccountConverter
        
        # Should be able to create converter without importing TradingService at runtime
        converter = AccountConverter()
        assert converter.trading_service is None


class TestPerformance:
    """Test performance-related aspects."""

    @pytest.mark.asyncio
    async def test_position_converter_caching_behavior(self):
        """Test that position converter doesn't unnecessarily call external services."""
        converter = PositionConverter()
        db_position = MagicMock(spec=DBPosition)
        db_position.symbol = "AAPL"
        db_position.quantity = 100
        db_position.avg_price = 150.0
        
        with patch("app.utils.schema_converters.asset_factory") as mock_asset_factory:
            mock_asset = MagicMock(spec=Stock)
            mock_asset_factory.return_value = mock_asset
            
            # When current_price is provided, should not call trading service
            result = await converter.to_schema(db_position, 155.0)
            
            assert result.current_price == 155.0
            # asset_factory should only be called once
            mock_asset_factory.assert_called_once_with("AAPL")

    def test_converter_memory_efficiency(self):
        """Test that converters don't hold unnecessary references."""
        converter = AccountConverter()
        
        # Converter should not hold references to converted objects
        import gc
        initial_objects = len(gc.get_objects())
        
        # Create and convert multiple objects
        for i in range(100):
            schema = Account(
                id=f"acc_{i}",
                owner=f"user_{i}",
                cash_balance=10000.0,
                name=f"user_{i}",
                positions=[]
            )
            converter.to_database(schema)
        
        # Force garbage collection
        gc.collect()
        
        # Should not have significantly more objects
        final_objects = len(gc.get_objects())
        # Allow some tolerance for test overhead
        assert final_objects - initial_objects < 50


# Test fixtures
@pytest.fixture
def mock_trading_service():
    """Provide a mock trading service."""
    return AsyncMock()


@pytest.fixture
def sample_db_account():
    """Provide a sample database account."""
    db_account = MagicMock(spec=DBAccount)
    db_account.id = "acc_123"
    db_account.owner = "testuser"
    db_account.cash_balance = 10000.0
    db_account.created_at = datetime(2023, 6, 15, 10, 0, 0)
    db_account.positions = []
    return db_account


@pytest.fixture
def sample_db_order():
    """Provide a sample database order."""
    db_order = MagicMock(spec=DBOrder)
    db_order.id = "order_123"
    db_order.account_id = "acc_123"
    db_order.symbol = "AAPL"
    db_order.order_type = OrderType.BUY
    db_order.quantity = 100
    db_order.price = 155.0
    db_order.status = OrderStatus.PENDING
    db_order.created_at = datetime(2023, 6, 15, 10, 0, 0)
    db_order.filled_at = None
    db_order.stop_price = None
    db_order.trail_percent = None
    db_order.trail_amount = None
    return db_order


@pytest.fixture
def sample_db_position():
    """Provide a sample database position."""
    db_position = MagicMock(spec=DBPosition)
    db_position.account_id = "acc_123"
    db_position.symbol = "AAPL"
    db_position.quantity = 100
    db_position.avg_price = 150.0
    return db_position