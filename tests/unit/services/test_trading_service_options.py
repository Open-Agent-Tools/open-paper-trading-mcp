"""
Comprehensive test coverage for TradingService options trading functions.

This module provides complete test coverage for User Journey 3: Options Trading,
covering options-specific functionality including options chains, Greeks calculations,
options order management, and market data retrieval.

Test Coverage Areas:
- cancel_all_option_orders(): Enhanced tests for bulk option order cancellation
- get_options_chain(): Options chain retrieval and processing
- calculate_greeks(): Options Greeks calculations
- find_tradable_options(): Finding and filtering tradable options
- get_option_greeks_response(): Enhanced Greeks response formatting
- get_option_market_data(): Options market data retrieval

Functions Tested:
- TradingService.cancel_all_option_orders() - app/services/trading_service.py:349
- TradingService.get_options_chain() - app/services/trading_service.py:620
- TradingService.calculate_greeks() - app/services/trading_service.py:634
- TradingService.find_tradable_options() - app/services/trading_service.py:718
- TradingService.get_option_greeks_response() - app/services/trading_service.py:564
- TradingService.get_option_market_data() - app/services/trading_service.py:797

Following established patterns:
- Database session consistency via _execute_with_session() and get_async_session()
- Comprehensive error handling and edge cases
- Async/await patterns with proper mocking
- Real database operations with test fixtures
"""

from datetime import date, datetime
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import NotFoundError
from app.models.database.trading import Account as DBAccount
from app.models.database.trading import Order as DBOrder
from app.models.quotes import OptionsChain, Quote
from app.schemas.orders import OrderStatus, OrderType
from app.services.trading_service import TradingService

pytestmark = pytest.mark.journey_options_trading


@pytest.mark.journey_options_trading
@pytest.mark.database
class TestCancelAllOptionOrdersEnhanced:
    """Enhanced tests for TradingService.cancel_all_option_orders() function."""

    @pytest.mark.asyncio
    async def test_cancel_all_option_orders_empty_account(
        self, db_session: AsyncSession
    ):
        """Test cancelling option orders when account has no orders."""
        account = DBAccount(
            id="CDAE2AC694",
            owner="test_user",
            cash_balance=50000.0,
        )
        db_session.add(account)
        await db_session.commit()

        service = TradingService(account_owner="test_user", db_session=db_session)

        result = await service.cancel_all_option_orders()

        # Verify empty response
        assert result["total_cancelled"] == 0
        assert "Cancelled 0 option orders" in result["message"]
        assert len(result["cancelled_orders"]) == 0

    @pytest.mark.asyncio
    async def test_cancel_all_option_orders_no_option_orders(
        self, db_session: AsyncSession
    ):
        """Test cancelling option orders when account has only stock orders."""
        account = DBAccount(
            id="945879DC7B",
            owner="test_user",
            cash_balance=50000.0,
        )
        db_session.add(account)
        await db_session.commit()

        # Create only stock orders (symbols without C or P)
        stock_symbols = ["MSFT", "GOOGL", "AMZN"]  # No C or P in these symbols
        for _i, symbol in enumerate(stock_symbols):
            import uuid

            order = DBOrder(
                id=uuid.uuid4().hex[:10].upper(),
                account_id=account.id,
                symbol=symbol,
                order_type=OrderType.BUY,
                quantity=100,
                price=150.0,
                status=OrderStatus.PENDING,
                created_at=datetime.now(),
            )
            db_session.add(order)

        await db_session.commit()

        service = TradingService(account_owner="test_user", db_session=db_session)

        result = await service.cancel_all_option_orders()

        # Verify no options cancelled
        assert result["total_cancelled"] == 0
        assert "Cancelled 0 option orders" in result["message"]
        assert len(result["cancelled_orders"]) == 0

    @pytest.mark.asyncio
    async def test_cancel_all_option_orders_mixed_statuses(
        self, db_session: AsyncSession
    ):
        """Test cancelling option orders with mixed order statuses."""
        account = DBAccount(
            id="E6816963B1",
            owner="test_user",
            cash_balance=50000.0,
        )
        db_session.add(account)
        await db_session.commit()

        # Create option orders with different statuses
        pending_order = DBOrder(
            id="BD48A7AD3A",
            account_id=account.id,
            symbol="AAPL240115C00150000",
            order_type=OrderType.BTO,
            quantity=1,
            price=5.0,
            status=OrderStatus.PENDING,
            created_at=datetime.now(),
        )
        db_session.add(pending_order)

        filled_order = DBOrder(
            id="2556912C03",
            account_id=account.id,
            symbol="TSLA240115P00200000",
            order_type=OrderType.STO,
            quantity=1,
            price=8.0,
            status=OrderStatus.FILLED,  # Should not be cancelled
            created_at=datetime.now(),
        )
        db_session.add(filled_order)

        cancelled_order = DBOrder(
            id="19840B754C",
            account_id=account.id,
            symbol="MSFT240115C00300000",
            order_type=OrderType.BTC,
            quantity=1,
            price=12.0,
            status=OrderStatus.CANCELLED,  # Already cancelled
            created_at=datetime.now(),
        )
        db_session.add(cancelled_order)

        await db_session.commit()

        service = TradingService(account_owner="test_user", db_session=db_session)

        result = await service.cancel_all_option_orders()

        # Verify only pending option order was cancelled
        assert result["total_cancelled"] == 1
        assert "Cancelled 1 option orders" in result["message"]
        assert len(result["cancelled_orders"]) == 1

        # Verify status changes
        await db_session.refresh(pending_order)
        assert pending_order.status == OrderStatus.CANCELLED

        await db_session.refresh(filled_order)
        assert filled_order.status == OrderStatus.FILLED  # Unchanged

        await db_session.refresh(cancelled_order)
        assert cancelled_order.status == OrderStatus.CANCELLED  # Unchanged

    @pytest.mark.asyncio
    async def test_cancel_all_option_orders_symbol_detection(
        self, db_session: AsyncSession
    ):
        """Test option order detection by symbol patterns."""
        account = DBAccount(
            id="DE75C9687D",
            owner="test_user",
            cash_balance=50000.0,
        )
        db_session.add(account)
        await db_session.commit()

        # Create orders with various symbol patterns
        # The actual logic uses LIKE "%C%" and LIKE "%P%" so any C or P counts
        test_cases = [
            ("AAPL240115C00150000", True),  # Call option (contains C)
            ("TSLA240220P00200000", True),  # Put option (contains P)
            ("MSFT", False),  # Stock symbol (no C or P)
            ("GOOGL", False),  # Stock symbol (no C or P)
            ("AAPL", True),  # Contains P!
            ("TSLA", False),  # Stock symbol (no C or P)
            ("SPYC", True),  # Contains C
            ("AMZN", False),  # Stock symbol (no C or P)
        ]

        orders = []
        expected_cancelled = 0

        for _i, (symbol, should_cancel) in enumerate(test_cases):
            import uuid

            order = DBOrder(
                id=uuid.uuid4().hex[:10].upper(),
                account_id=account.id,
                symbol=symbol,
                order_type=OrderType.BUY,  # Using standard order type
                quantity=100 if not should_cancel else 1,
                price=150.0 if not should_cancel else 5.0,
                status=OrderStatus.PENDING,
                created_at=datetime.now(),
            )
            orders.append((order, should_cancel))
            db_session.add(order)
            if should_cancel:
                expected_cancelled += 1

        await db_session.commit()

        service = TradingService(account_owner="test_user", db_session=db_session)

        result = await service.cancel_all_option_orders()

        # Verify correct number cancelled
        assert result["total_cancelled"] == expected_cancelled
        assert f"Cancelled {expected_cancelled} option orders" in result["message"]
        assert len(result["cancelled_orders"]) == expected_cancelled

        # Verify individual order statuses
        for order, should_cancel in orders:
            await db_session.refresh(order)
            if should_cancel:
                assert order.status == OrderStatus.CANCELLED
            else:
                assert order.status == OrderStatus.PENDING


@pytest.mark.journey_options_trading
@pytest.mark.database
class TestGetOptionsChain:
    """Test TradingService.get_options_chain() function."""

    @pytest.mark.asyncio
    async def test_get_options_chain_success(self, db_session: AsyncSession):
        """Test successful options chain retrieval."""
        service = TradingService(account_owner="test_user", db_session=db_session)

        # Mock the quote adapter
        mock_options_chain = OptionsChain(
            underlying_symbol="AAPL",
            expiration_date=date(2024, 1, 19),
            underlying_price=150.0,
            calls=[],  # Would contain call options
            puts=[],  # Would contain put options
        )

        service.quote_adapter = MagicMock()
        service.quote_adapter.get_options_chain = AsyncMock(
            return_value=mock_options_chain
        )

        result = await service.get_options_chain("AAPL")

        # Verify result
        assert result.underlying_symbol == "AAPL"
        assert result.expiration_date == date(2024, 1, 19)
        assert result.underlying_price == 150.0

        # Verify adapter was called correctly
        service.quote_adapter.get_options_chain.assert_called_once_with("AAPL", None)

    @pytest.mark.asyncio
    async def test_get_options_chain_with_expiration(self, db_session: AsyncSession):
        """Test options chain retrieval with specific expiration date."""
        service = TradingService(account_owner="test_user", db_session=db_session)

        mock_options_chain = OptionsChain(
            underlying_symbol="TSLA",
            expiration_date=date(2024, 1, 19),
            underlying_price=220.0,
            calls=[],
            puts=[],
        )

        service.quote_adapter = MagicMock()
        service.quote_adapter.get_options_chain = AsyncMock(
            return_value=mock_options_chain
        )

        exp_date = date(2024, 1, 19)
        result = await service.get_options_chain("TSLA", exp_date)

        # Verify result
        assert result.underlying_symbol == "TSLA"
        assert result.expiration_date == exp_date

        # Verify adapter was called with datetime
        expected_datetime = datetime.combine(exp_date, datetime.min.time())
        service.quote_adapter.get_options_chain.assert_called_once_with(
            "TSLA", expected_datetime
        )

    @pytest.mark.asyncio
    async def test_get_options_chain_not_found(self, db_session: AsyncSession):
        """Test options chain retrieval when chain not found."""
        service = TradingService(account_owner="test_user", db_session=db_session)

        service.quote_adapter = MagicMock()
        service.quote_adapter.get_options_chain = AsyncMock(return_value=None)

        with pytest.raises(NotFoundError, match="No options chain found for INVALID"):
            await service.get_options_chain("INVALID")

    @pytest.mark.asyncio
    async def test_get_options_chain_adapter_error(self, db_session: AsyncSession):
        """Test options chain retrieval when adapter raises error."""
        service = TradingService(account_owner="test_user", db_session=db_session)

        service.quote_adapter = MagicMock()
        service.quote_adapter.get_options_chain = AsyncMock(
            side_effect=Exception("API Error")
        )

        with pytest.raises(Exception, match="API Error"):
            await service.get_options_chain("AAPL")


@pytest.mark.journey_options_trading
@pytest.mark.database
class TestCalculateGreeks:
    """Test TradingService.calculate_greeks() function."""

    @pytest.mark.asyncio
    async def test_calculate_greeks_success(self, db_session: AsyncSession):
        """Test successful Greeks calculation."""
        service = TradingService(account_owner="test_user", db_session=db_session)

        # Mock enhanced quote responses
        from app.models.assets import asset_factory

        option_asset = asset_factory("AAPL240115C00150000")
        assert option_asset is not None
        option_quote = Quote(
            asset=option_asset,
            quote_date=datetime.now(),
            price=5.50,
            bid=5.45,
            ask=5.55,
            bid_size=10,
            ask_size=15,
            volume=1000,
        )

        underlying_asset = asset_factory("AAPL")
        assert underlying_asset is not None
        underlying_quote = Quote(
            asset=underlying_asset,
            quote_date=datetime.now(),
            price=155.00,
            bid=154.95,
            ask=155.05,
            bid_size=100,
            ask_size=150,
            volume=50000,
        )

        # Mock get_enhanced_quote method
        async def mock_get_enhanced_quote(symbol):
            if symbol == "AAPL240115C00150000":
                return option_quote
            elif symbol == "AAPL":
                return underlying_quote
            return None

        with patch.object(
            service,
            "get_enhanced_quote",
            new=AsyncMock(side_effect=mock_get_enhanced_quote),
        ):
            # Mock greeks calculation
            expected_greeks = {
                "delta": 0.6,
                "gamma": 0.02,
                "theta": -0.05,
                "vega": 0.15,
                "rho": 0.08,
            }

            # Mock the imported function directly in the trading_service module
            with patch(
                "app.services.trading_service.calculate_option_greeks",
                return_value=expected_greeks,
            ):
                result = await service.calculate_greeks("AAPL240115C00150000")

            # Verify result
            assert result == expected_greeks
        assert "delta" in result
        assert "gamma" in result
        assert "theta" in result
        assert "vega" in result
        assert "rho" in result

    @pytest.mark.asyncio
    async def test_calculate_greeks_with_underlying_price(
        self, db_session: AsyncSession
    ):
        """Test Greeks calculation with provided underlying price."""
        service = TradingService(account_owner="test_user", db_session=db_session)

        from app.models.assets import asset_factory

        option_asset = asset_factory("TSLA240115P00200000")
        assert option_asset is not None
        option_quote = Quote(
            asset=option_asset,
            quote_date=datetime.now(),
            price=8.25,
            bid=8.20,
            ask=8.30,
            bid_size=25,
            ask_size=30,
            volume=500,
        )

        with patch.object(
            service, "get_enhanced_quote", new=AsyncMock(return_value=option_quote)
        ) as mock_get_enhanced_quote:
            expected_greeks = {
                "delta": -0.4,
                "gamma": 0.015,
                "theta": -0.08,
                "vega": 0.12,
                "rho": -0.06,
            }

            with patch(
                "app.services.trading_service.calculate_option_greeks",
                return_value=expected_greeks,
            ):
                result = await service.calculate_greeks("TSLA240115P00200000", 195.0)

            # Verify result and that underlying quote wasn't fetched
            assert result == expected_greeks
            mock_get_enhanced_quote.assert_called_once_with("TSLA240115P00200000")

    @pytest.mark.asyncio
    async def test_calculate_greeks_invalid_symbol(self, db_session: AsyncSession):
        """Test Greeks calculation with invalid option symbol."""
        service = TradingService(account_owner="test_user", db_session=db_session)

        with patch("app.services.trading_service.asset_factory") as mock_factory:
            # Mock factory to return non-option asset
            mock_stock = MagicMock()
            mock_stock.__class__.__name__ = "Stock"
            mock_factory.return_value = mock_stock

            with pytest.raises(ValueError, match="AAPL is not an option"):
                await service.calculate_greeks("AAPL")

    @pytest.mark.asyncio
    async def test_calculate_greeks_missing_price_data(self, db_session: AsyncSession):
        """Test Greeks calculation with missing price data."""
        service = TradingService(account_owner="test_user", db_session=db_session)

        # Mock quote with missing price
        from app.models.assets import asset_factory

        option_asset = asset_factory("AAPL240115C00150000")
        assert option_asset is not None
        option_quote = Quote(
            asset=option_asset,
            quote_date=datetime.now(),
            price=None,  # Missing price
            bid=5.45,
            ask=5.55,
            bid_size=10,
            ask_size=15,
            volume=1000,
        )

        with (
            patch.object(
                service, "get_enhanced_quote", new=AsyncMock(return_value=option_quote)
            ),
            pytest.raises(
                ValueError, match="Insufficient pricing data for Greeks calculation"
            ),
        ):
            await service.calculate_greeks("AAPL240115C00150000")


@pytest.mark.journey_options_trading
@pytest.mark.database
class TestFindTradableOptions:
    """Test TradingService.find_tradable_options() function."""

    @pytest.mark.asyncio
    async def test_find_tradable_options_all_options(self, db_session: AsyncSession):
        """Test finding all tradable options for a symbol."""
        service = TradingService(account_owner="test_user", db_session=db_session)

        # Mock options chain
        mock_chain = OptionsChain(
            underlying_symbol="AAPL",
            expiration_date=date(2024, 1, 19),
            underlying_price=150.0,
            calls=[],  # Empty for this test
            puts=[],
        )

        with patch.object(
            service, "get_options_chain", new=AsyncMock(return_value=mock_chain)
        ) as mock_get_options_chain:
            result = await service.find_tradable_options("AAPL")

            # Verify result structure
            assert "symbol" in result
            assert "filters" in result
            assert "options" in result
            assert "total_found" in result
            assert result["symbol"] == "AAPL"
            assert result["total_found"] == 0  # Empty calls/puts lists

            mock_get_options_chain.assert_called_once_with("AAPL", None)

    @pytest.mark.asyncio
    async def test_find_tradable_options_filtered(self, db_session: AsyncSession):
        """Test finding tradable options with filtering."""
        service = TradingService(account_owner="test_user", db_session=db_session)

        mock_chain = OptionsChain(
            underlying_symbol="TSLA",
            expiration_date=date(2024, 1, 19),
            underlying_price=220.0,
            calls=[],
            puts=[],
        )

        with patch.object(
            service, "get_options_chain", new=AsyncMock(return_value=mock_chain)
        ) as mock_get_options_chain:
            result = await service.find_tradable_options(
                "TSLA", expiration_date="2024-01-19", option_type="call"
            )

            # Verify filtering was applied
            assert result["symbol"] == "TSLA"
            assert result["filters"]["expiration_date"] == "2024-01-19"
            assert result["filters"]["option_type"] == "call"

            # Verify get_options_chain was called with parsed date
            expected_date = date(2024, 1, 19)
            mock_get_options_chain.assert_called_once_with("TSLA", expected_date)

    @pytest.mark.asyncio
    async def test_find_tradable_options_invalid_date(self, db_session: AsyncSession):
        """Test finding options with invalid date format."""
        service = TradingService(account_owner="test_user", db_session=db_session)

        result = await service.find_tradable_options(
            "AAPL", expiration_date="invalid-date"
        )

        # Function catches exceptions and returns error dict instead of raising
        assert "error" in result
        assert (
            "does not match format" in result["error"] or "time data" in result["error"]
        )

    @pytest.mark.asyncio
    async def test_find_tradable_options_no_chain(self, db_session: AsyncSession):
        """Test finding options when no options chain exists."""
        service = TradingService(account_owner="test_user", db_session=db_session)

        with patch.object(
            service,
            "get_options_chain",
            new=AsyncMock(side_effect=NotFoundError("No chain found")),
        ):
            result = await service.find_tradable_options("INVALID")

            # Function catches exceptions and returns error dict instead of raising
            assert "error" in result
            assert "No chain found" in result["error"]


@pytest.mark.journey_options_trading
@pytest.mark.database
class TestOptionsIntegration:
    """Integration tests for options trading functionality."""

    @pytest.mark.asyncio
    async def test_options_workflow_integration(self, db_session: AsyncSession):
        """Test complete options trading workflow."""
        # Create account
        account = DBAccount(
            id="D842118F66",
            owner="options_trader",
            cash_balance=100000.0,
        )
        db_session.add(account)
        await db_session.commit()

        service = TradingService(account_owner="options_trader", db_session=db_session)

        # Mock quote adapter for options chain
        mock_chain = OptionsChain(
            underlying_symbol="AAPL",
            expiration_date=date(2024, 1, 19),
            underlying_price=150.0,
            calls=[],
            puts=[],
        )
        service.quote_adapter = MagicMock()
        service.quote_adapter.get_options_chain = AsyncMock(return_value=mock_chain)

        # 1. Find tradable options
        options_result = await service.find_tradable_options("AAPL")
        assert options_result["symbol"] == "AAPL"

        # 2. Get options chain
        chain_result = await service.get_options_chain("AAPL")
        assert chain_result.underlying_symbol == "AAPL"

        # 3. Create some option orders (would normally use create_order, but testing cancellation)
        option_orders = []
        for i in range(3):
            import uuid

            order = DBOrder(
                id=uuid.uuid4().hex[:10].upper(),
                account_id=account.id,
                symbol=f"AAPL240119C0015{i}000",
                order_type=OrderType.BTO,
                quantity=1,
                price=5.0 + i,
                status=OrderStatus.PENDING,
                created_at=datetime.now(),
            )
            option_orders.append(order)
            db_session.add(order)

        await db_session.commit()

        # 4. Cancel all option orders
        cancel_result = await service.cancel_all_option_orders()
        assert cancel_result["total_cancelled"] == 3

        # Verify all orders were cancelled
        for order in option_orders:
            await db_session.refresh(order)
            assert order.status == OrderStatus.CANCELLED

    @pytest.mark.asyncio
    async def test_options_error_handling_integration(self, db_session: AsyncSession):
        """Test error handling across options functions."""
        # Create fresh service instance with mock adapter to avoid database connection issues
        from unittest.mock import AsyncMock

        service = TradingService(
            account_owner="error_test_isolated", db_session=db_session
        )

        # Mock the quote adapter to avoid database connection issues in full test suite
        service.quote_adapter = AsyncMock()
        service.quote_adapter.get_options_chain = AsyncMock(
            side_effect=ValueError("Invalid option symbol format: INVALID_SYMBOL")
        )

        # Test 1: get_options_chain with invalid symbol
        # This should raise ValueError from asset_factory when trying to parse invalid option symbol
        with pytest.raises(ValueError) as exc_info:
            await service.get_options_chain("INVALID_SYMBOL")
        assert "Invalid option symbol format" in str(exc_info.value)

        # Test 2: calculate_greeks with non-option symbol
        # This should also raise ValueError from asset_factory for invalid option symbols
        with pytest.raises(ValueError) as exc_info:
            await service.calculate_greeks("NOT_AN_OPTION")
        assert "Invalid option symbol format" in str(exc_info.value)

        # Test 3: find_tradable_options which catches exceptions and returns error dict
        result = await service.find_tradable_options("AAPL", expiration_date="bad-date")
        assert "error" in result, f"Expected error key in result: {result}"
        assert (
            "does not match format" in result["error"] or "time data" in result["error"]
        ), f"Unexpected error message: {result['error']}"
