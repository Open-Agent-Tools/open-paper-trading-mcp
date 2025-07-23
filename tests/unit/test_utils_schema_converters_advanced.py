"""
Advanced test suite for schema converter utilities.

Tests comprehensive conversion patterns between database models and API schemas,
including bidirectional conversions, edge cases, and error handling.
"""

import uuid
from datetime import datetime
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.models.assets import Option as OptionAsset
from app.models.assets import Stock as StockAsset
from app.models.database.trading import Account as DBAccount
from app.models.database.trading import Order as DBOrder
from app.models.database.trading import Position as DBPosition
from app.schemas.accounts import Account
from app.schemas.orders import Order, OrderCondition, OrderStatus, OrderType
from app.schemas.positions import Position
from app.utils.schema_converters import (
    AccountConverter,
    ConversionError,
    OrderConverter,
    PositionConverter,
    db_account_to_schema,
    db_order_to_schema,
    db_position_to_schema,
    schema_account_to_db,
    schema_order_to_db,
    schema_position_to_db,
)


class TestSchemaConverterBase:
    """Test base converter interface and common functionality."""

    def test_schema_converter_interface(self):
        """Test that converters implement the base interface."""
        account_converter = AccountConverter()
        order_converter = OrderConverter()
        position_converter = PositionConverter()

        # Check all converters have required methods
        assert hasattr(account_converter, "to_schema")
        assert hasattr(account_converter, "to_database")
        assert hasattr(order_converter, "to_schema")
        assert hasattr(order_converter, "to_database")
        assert hasattr(position_converter, "to_schema")
        assert hasattr(position_converter, "to_database")


class TestAccountConverter:
    """Test account schema conversion functionality."""

    @pytest.fixture
    def sample_db_account(self) -> DBAccount:
        """Create a sample database account for testing."""
        account = DBAccount()
        account.id = str(uuid.uuid4())
        account.owner = "testuser@example.com"
        account.cash_balance = 10000.50
        account.created_at = datetime.utcnow()
        account.positions = []  # Empty positions list
        return account

    @pytest.fixture
    def sample_schema_account(self) -> Account:
        """Create a sample schema account for testing."""
        return Account(
            id=str(uuid.uuid4()),
            owner="testuser@example.com",
            cash_balance=10000.50,
            name="Test Account",
            positions=[],
        )

    @pytest.fixture
    def mock_trading_service(self) -> MagicMock:
        """Create a mock trading service."""
        service = MagicMock()
        service.get_quote = AsyncMock()
        return service

    async def test_account_to_schema_basic(self, sample_db_account: DBAccount):
        """Test basic database account to schema conversion."""
        converter = AccountConverter()
        schema_account = await converter.to_schema(sample_db_account)

        assert schema_account.id == sample_db_account.id
        assert schema_account.owner == sample_db_account.owner
        assert schema_account.cash_balance == sample_db_account.cash_balance
        assert schema_account.name == sample_db_account.owner  # Uses owner as name
        assert schema_account.positions == []

    async def test_account_to_schema_with_positions(
        self, sample_db_account: DBAccount, mock_trading_service: MagicMock
    ):
        """Test account conversion with positions."""
        # Create a mock position
        db_position = MagicMock()
        db_position.symbol = "AAPL"
        db_position.quantity = 100
        db_position.avg_price = 150.0
        sample_db_account.positions = [db_position]

        converter = AccountConverter(mock_trading_service)

        with patch(
            "app.utils.schema_converters.PositionConverter"
        ) as mock_pos_converter:
            mock_pos_instance = mock_pos_converter.return_value
            mock_pos_instance.to_schema = AsyncMock(
                return_value=Position(
                    symbol="AAPL",
                    quantity=100,
                    avg_price=150.0,
                    current_price=155.0,
                    unrealized_pnl=500.0,
                    realized_pnl=0.0,
                    asset=None,
                )
            )

            schema_account = await converter.to_schema(sample_db_account)

            assert len(schema_account.positions) == 1
            assert schema_account.positions[0].symbol == "AAPL"
            mock_pos_instance.to_schema.assert_called_once_with(db_position)

    async def test_account_to_schema_without_trading_service(
        self, sample_db_account: DBAccount
    ):
        """Test account conversion without trading service (no positions loaded)."""
        sample_db_account.positions = [MagicMock()]  # Has positions but service is None

        converter = AccountConverter(trading_service=None)
        schema_account = await converter.to_schema(sample_db_account)

        assert schema_account.positions == []  # Should be empty without service

    def test_schema_to_database_basic(self, sample_schema_account: Account):
        """Test basic schema account to database conversion."""
        converter = AccountConverter()
        db_account = converter.to_database(sample_schema_account)

        assert db_account.id == sample_schema_account.id
        assert db_account.owner == sample_schema_account.owner
        assert db_account.cash_balance == sample_schema_account.cash_balance

    def test_schema_to_database_fallback_owner(self):
        """Test schema conversion with fallback owner logic."""
        converter = AccountConverter()

        # Test with name but no owner
        account_with_name = Account(
            id="test-id", cash_balance=1000.0, name="Test Account", owner=None
        )
        db_account = converter.to_database(account_with_name)
        assert db_account.owner == "Test Account"

        # Test with neither owner nor name
        account_no_info = Account(
            id="test-id", cash_balance=1000.0, name=None, owner=None
        )
        db_account = converter.to_database(account_no_info)
        assert db_account.owner == "unknown"

    async def test_convenience_functions_account(
        self, sample_db_account: DBAccount, sample_schema_account: Account
    ):
        """Test convenience functions for account conversion."""
        # Test db to schema
        schema_account = await db_account_to_schema(sample_db_account)
        assert isinstance(schema_account, Account)
        assert schema_account.id == sample_db_account.id

        # Test schema to db
        db_account = schema_account_to_db(sample_schema_account)
        assert isinstance(db_account, DBAccount)
        assert db_account.id == sample_schema_account.id


class TestOrderConverter:
    """Test order schema conversion functionality."""

    @pytest.fixture
    def sample_db_order(self) -> DBOrder:
        """Create a sample database order for testing."""
        order = DBOrder()
        order.id = str(uuid.uuid4())
        order.account_id = str(uuid.uuid4())
        order.symbol = "AAPL"
        order.order_type = OrderType.BUY
        order.quantity = 100
        order.price = 150.0
        order.status = OrderStatus.PENDING
        order.created_at = datetime.utcnow()
        order.filled_at = None
        return order

    @pytest.fixture
    def sample_schema_order(self) -> Order:
        """Create a sample schema order for testing."""
        return Order(
            id=str(uuid.uuid4()),
            symbol="AAPL",
            order_type=OrderType.BUY,
            quantity=100,
            price=150.0,
            status=OrderStatus.PENDING,
            condition=OrderCondition.MARKET,
            legs=[],
            net_price=150.0,
            created_at=datetime.utcnow(),
            filled_at=None,
        )

    async def test_order_to_schema_basic(self, sample_db_order: DBOrder):
        """Test basic database order to schema conversion."""
        converter = OrderConverter()
        schema_order = await converter.to_schema(sample_db_order)

        assert schema_order.id == sample_db_order.id
        assert schema_order.symbol == sample_db_order.symbol
        assert schema_order.order_type == sample_db_order.order_type
        assert schema_order.quantity == sample_db_order.quantity
        assert schema_order.price == sample_db_order.price
        assert schema_order.status == sample_db_order.status
        assert schema_order.created_at == sample_db_order.created_at
        assert schema_order.filled_at == sample_db_order.filled_at

        # Check schema-only defaults
        assert schema_order.condition == OrderCondition.MARKET
        assert schema_order.legs == []
        assert schema_order.net_price == sample_db_order.price

    async def test_order_to_schema_filled_order(self, sample_db_order: DBOrder):
        """Test conversion of filled order."""
        sample_db_order.status = OrderStatus.FILLED
        sample_db_order.filled_at = datetime.utcnow()

        converter = OrderConverter()
        schema_order = await converter.to_schema(sample_db_order)

        assert schema_order.status == OrderStatus.FILLED
        assert schema_order.filled_at is not None

    def test_schema_to_database_basic(self, sample_schema_order: Order):
        """Test basic schema order to database conversion."""
        converter = OrderConverter()
        account_id = str(uuid.uuid4())

        db_order = converter.to_database(sample_schema_order, account_id=account_id)

        assert db_order.id == sample_schema_order.id
        assert db_order.account_id == account_id
        assert db_order.symbol == sample_schema_order.symbol
        assert db_order.order_type == sample_schema_order.order_type
        assert db_order.quantity == sample_schema_order.quantity
        assert db_order.price == sample_schema_order.price
        assert db_order.status == sample_schema_order.status

    def test_schema_to_database_missing_account_id(self, sample_schema_order: Order):
        """Test schema conversion fails without account_id."""
        converter = OrderConverter()

        with pytest.raises(ConversionError, match="account_id is required"):
            converter.to_database(sample_schema_order)

    async def test_convenience_functions_order(
        self, sample_db_order: DBOrder, sample_schema_order: Order
    ):
        """Test convenience functions for order conversion."""
        # Test db to schema
        schema_order = await db_order_to_schema(sample_db_order)
        assert isinstance(schema_order, Order)
        assert schema_order.id == sample_db_order.id

        # Test schema to db
        account_id = str(uuid.uuid4())
        db_order = schema_order_to_db(sample_schema_order, account_id)
        assert isinstance(db_order, DBOrder)
        assert db_order.id == sample_schema_order.id
        assert db_order.account_id == account_id


class TestPositionConverter:
    """Test position schema conversion functionality."""

    @pytest.fixture
    def sample_db_position(self) -> DBPosition:
        """Create a sample database position for testing."""
        position = DBPosition()
        position.id = str(uuid.uuid4())
        position.account_id = str(uuid.uuid4())
        position.symbol = "AAPL"
        position.quantity = 100
        position.avg_price = 150.0
        return position

    @pytest.fixture
    def sample_schema_position(self) -> Position:
        """Create a sample schema position for testing."""
        return Position(
            symbol="AAPL",
            quantity=100,
            avg_price=150.0,
            current_price=155.0,
            unrealized_pnl=500.0,
            realized_pnl=0.0,
            asset=StockAsset(symbol="AAPL"),
        )

    @pytest.fixture
    def mock_trading_service(self) -> MagicMock:
        """Create a mock trading service."""
        service = MagicMock()
        service.get_quote = AsyncMock()
        return service

    async def test_position_to_schema_basic(self, sample_db_position: DBPosition):
        """Test basic database position to schema conversion."""
        converter = PositionConverter()
        current_price = 155.0

        with patch("app.utils.schema_converters.asset_factory") as mock_asset_factory:
            mock_asset = StockAsset(symbol="AAPL")
            mock_asset_factory.return_value = mock_asset

            schema_position = await converter.to_schema(
                sample_db_position, current_price=current_price
            )

            assert schema_position.symbol == sample_db_position.symbol
            assert schema_position.quantity == sample_db_position.quantity
            assert schema_position.avg_price == sample_db_position.avg_price
            assert schema_position.current_price == current_price
            assert schema_position.unrealized_pnl == 500.0  # (155-150) * 100
            assert schema_position.asset == mock_asset

    async def test_position_to_schema_with_trading_service(
        self, sample_db_position: DBPosition, mock_trading_service: MagicMock
    ):
        """Test position conversion with trading service for price lookup."""
        converter = PositionConverter(mock_trading_service)

        # Mock quote response
        mock_quote = MagicMock()
        mock_quote.price = 160.0
        mock_trading_service.get_quote.return_value = mock_quote

        with patch("app.utils.schema_converters.asset_factory") as mock_asset_factory:
            mock_asset = StockAsset(symbol="AAPL")
            mock_asset_factory.return_value = mock_asset

            schema_position = await converter.to_schema(sample_db_position)

            assert schema_position.current_price == 160.0
            assert schema_position.unrealized_pnl == 1000.0  # (160-150) * 100
            mock_trading_service.get_quote.assert_called_once_with("AAPL")

    async def test_position_to_schema_quote_error(
        self, sample_db_position: DBPosition, mock_trading_service: MagicMock
    ):
        """Test position conversion when quote lookup fails."""
        converter = PositionConverter(mock_trading_service)

        # Mock quote to raise exception
        mock_trading_service.get_quote.side_effect = Exception("Quote error")

        with patch("app.utils.schema_converters.asset_factory") as mock_asset_factory:
            mock_asset = StockAsset(symbol="AAPL")
            mock_asset_factory.return_value = mock_asset

            schema_position = await converter.to_schema(sample_db_position)

            # Should fall back to avg_price
            assert schema_position.current_price == sample_db_position.avg_price
            assert schema_position.unrealized_pnl == 0.0

    async def test_position_to_schema_option_asset(
        self, sample_db_position: DBPosition
    ):
        """Test position conversion with option asset."""
        sample_db_position.symbol = "AAPL_2024-01-19_150.00_C"
        converter = PositionConverter()

        with patch("app.utils.schema_converters.asset_factory") as mock_asset_factory:
            mock_underlying = StockAsset(symbol="AAPL")
            mock_option = OptionAsset(
                symbol="AAPL_2024-01-19_150.00_C",
                underlying=mock_underlying,
                option_type="call",
                strike=150.0,
                expiration=datetime(2024, 1, 19).date(),
            )
            mock_asset_factory.return_value = mock_option

            schema_position = await converter.to_schema(
                sample_db_position, current_price=155.0
            )

            assert schema_position.option_type == "call"
            assert schema_position.strike == 150.0
            assert schema_position.expiration_date == datetime(2024, 1, 19).date()
            assert schema_position.underlying_symbol == "AAPL"

    def test_position_to_schema_sync(self, sample_db_position: DBPosition):
        """Test synchronous position conversion."""
        converter = PositionConverter()

        with patch("app.utils.schema_converters.asset_factory") as mock_asset_factory:
            mock_asset = StockAsset(symbol="AAPL")
            mock_asset_factory.return_value = mock_asset

            schema_position = converter.to_schema_sync(
                sample_db_position, current_price=155.0
            )

            assert schema_position.symbol == sample_db_position.symbol
            assert schema_position.current_price == 155.0
            assert schema_position.unrealized_pnl == 500.0

    def test_schema_to_database_basic(self, sample_schema_position: Position):
        """Test basic schema position to database conversion."""
        converter = PositionConverter()
        account_id = str(uuid.uuid4())

        db_position = converter.to_database(
            sample_schema_position, account_id=account_id
        )

        assert db_position.account_id == account_id
        assert db_position.symbol == sample_schema_position.symbol
        assert db_position.quantity == sample_schema_position.quantity
        assert db_position.avg_price == sample_schema_position.avg_price

    def test_schema_to_database_missing_account_id(
        self, sample_schema_position: Position
    ):
        """Test schema conversion fails without account_id."""
        converter = PositionConverter()

        with pytest.raises(ConversionError, match="account_id is required"):
            converter.to_database(sample_schema_position)

    async def test_convenience_functions_position(
        self, sample_db_position: DBPosition, sample_schema_position: Position
    ):
        """Test convenience functions for position conversion."""
        with patch("app.utils.schema_converters.asset_factory"):
            # Test db to schema
            schema_position = await db_position_to_schema(sample_db_position)
            assert isinstance(schema_position, Position)
            assert schema_position.symbol == sample_db_position.symbol

            # Test schema to db
            account_id = str(uuid.uuid4())
            db_position = schema_position_to_db(sample_schema_position, account_id)
            assert isinstance(db_position, DBPosition)
            assert db_position.symbol == sample_schema_position.symbol
            assert db_position.account_id == account_id


class TestConversionErrorHandling:
    """Test error handling in schema conversions."""

    def test_conversion_error_creation(self):
        """Test ConversionError exception creation."""
        error = ConversionError("Test error message")
        assert str(error) == "Test error message"
        assert isinstance(error, Exception)

    def test_order_conversion_error_propagation(self):
        """Test that conversion errors are properly propagated."""
        converter = OrderConverter()
        order = Order(
            id="test-id",
            symbol="AAPL",
            order_type=OrderType.BUY,
            quantity=100,
            price=150.0,
            status=OrderStatus.PENDING,
        )

        with pytest.raises(ConversionError):
            converter.to_database(order)  # Missing account_id

    def test_position_conversion_error_propagation(self):
        """Test that position conversion errors are properly propagated."""
        converter = PositionConverter()
        position = Position(
            symbol="AAPL",
            quantity=100,
            avg_price=150.0,
            current_price=155.0,
            unrealized_pnl=500.0,
            realized_pnl=0.0,
            asset=None,
        )

        with pytest.raises(ConversionError):
            converter.to_database(position)  # Missing account_id


class TestEdgeCases:
    """Test edge cases and boundary conditions."""

    async def test_position_with_zero_quantity(self):
        """Test position conversion with zero quantity."""
        db_position = DBPosition()
        db_position.symbol = "AAPL"
        db_position.quantity = 0
        db_position.avg_price = 150.0

        converter = PositionConverter()
        with patch("app.utils.schema_converters.asset_factory"):
            schema_position = await converter.to_schema(
                db_position, current_price=155.0
            )

            assert schema_position.quantity == 0
            assert schema_position.unrealized_pnl == 0.0  # 0 * (155-150)

    async def test_position_with_negative_quantity(self):
        """Test position conversion with negative quantity (short position)."""
        db_position = DBPosition()
        db_position.symbol = "AAPL"
        db_position.quantity = -100
        db_position.avg_price = 150.0

        converter = PositionConverter()
        with patch("app.utils.schema_converters.asset_factory"):
            schema_position = await converter.to_schema(
                db_position, current_price=155.0
            )

            assert schema_position.quantity == -100
            assert schema_position.unrealized_pnl == -500.0  # -100 * (155-150)

    def test_account_with_extreme_cash_balance(self):
        """Test account conversion with extreme cash balances."""
        converter = AccountConverter()

        # Very large balance
        large_account = Account(
            id="test-id",
            cash_balance=999_999_999.99,
            owner="test",
            positions=[],
        )
        db_account = converter.to_database(large_account)
        assert db_account.cash_balance == 999_999_999.99

        # Negative balance
        negative_account = Account(
            id="test-id",
            cash_balance=-1000.0,
            owner="test",
            positions=[],
        )
        db_account = converter.to_database(negative_account)
        assert db_account.cash_balance == -1000.0

    async def test_order_with_decimal_price(self):
        """Test order conversion with decimal precision prices."""
        db_order = DBOrder()
        db_order.id = "test-id"
        db_order.symbol = "AAPL"
        db_order.order_type = OrderType.BUY
        db_order.quantity = 1
        db_order.price = 150.123456789  # High precision
        db_order.status = OrderStatus.PENDING
        db_order.created_at = datetime.utcnow()

        converter = OrderConverter()
        schema_order = await converter.to_schema(db_order)

        assert schema_order.price == 150.123456789
        assert schema_order.net_price == 150.123456789

    async def test_asset_factory_returns_none(self):
        """Test position conversion when asset_factory returns None."""
        db_position = DBPosition()
        db_position.symbol = "INVALID_SYMBOL"
        db_position.quantity = 100
        db_position.avg_price = 150.0

        converter = PositionConverter()
        with patch(
            "app.utils.schema_converters.asset_factory", return_value=None
        ) as mock_factory:
            schema_position = await converter.to_schema(
                db_position, current_price=155.0
            )

            assert schema_position.asset is None
            assert schema_position.option_type is None
            assert schema_position.strike is None
            mock_factory.assert_called_once_with("INVALID_SYMBOL")
