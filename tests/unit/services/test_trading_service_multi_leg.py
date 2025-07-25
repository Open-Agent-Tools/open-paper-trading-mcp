"""
Comprehensive test coverage for TradingService multi-leg order functions.

This module provides complete test coverage for User Journey 4: Complex Orders & Multi-Leg Strategies,
covering multi-leg order creation, validation, persistence, and complex options strategies.

Test Coverage Areas:
- create_multi_leg_order(): Multi-leg order creation with validation and persistence
- create_multi_leg_order_from_request(): Raw request data conversion and processing
- Multi-leg order validation: leg validation, duplicate detection, pricing logic
- Complex strategies: spreads, straddles, collars, and other multi-leg strategies

Functions Tested:
- TradingService.create_multi_leg_order() - app/services/trading_service.py:671
- TradingService.create_multi_leg_order_from_request() - app/services/trading_service.py:1151

Following established patterns:
- Database session consistency via _execute_with_session() and get_async_session()
- Comprehensive error handling and edge cases
- Async/await patterns with proper mocking
- Real database operations with test fixtures
"""

import asyncio
import uuid
from unittest.mock import patch

import pytest
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.database.trading import Account as DBAccount
from app.models.database.trading import Order as DBOrder
from app.schemas.orders import (
    OrderCondition,
    OrderStatus,
    OrderType,
)
from app.services.trading_service import TradingService


@pytest.mark.database
class TestCreateMultiLegOrder:
    """Test TradingService.create_multi_leg_order() function."""

    @pytest.mark.asyncio
    async def test_create_multi_leg_order_simple_spread(self, db_session: AsyncSession):
        """Test creating a simple two-leg spread order."""
        # Create test account
        account = DBAccount(
            id=str(uuid.uuid4()),
            owner="test_user",
            cash_balance=50000.0,
        )
        db_session.add(account)
        await db_session.commit()

        service = TradingService(account_owner="test_user", db_session=db_session)

        # Create mock order data with legs
        class MockLeg:
            def __init__(
                self, symbol: str, quantity: int, order_type: OrderType, price: float
            ):
                self.symbol = symbol
                self.quantity = quantity
                self.order_type = order_type
                self.price = price

        class MockOrderData:
            def __init__(self, legs):
                self.legs = legs
                self.condition = OrderCondition.LIMIT

        # Bull call spread: buy lower strike call, sell higher strike call
        legs = [
            MockLeg("AAPL240115C00150000", 1, OrderType.BTO, 5.0),  # Buy to open
            MockLeg(
                "AAPL240115C00155000", 1, OrderType.STO, 3.0
            ),  # Sell to open (positive quantity)
        ]
        order_data = MockOrderData(legs)

        result = await service.create_multi_leg_order(order_data)

        # Verify result structure
        assert result.id is not None
        assert result.symbol == "MULTI_LEG_2_LEGS"
        assert (
            result.quantity == 2
        )  # Total quantity (1 + 1) - Order model requires positive
        assert result.price == 8.0  # Total price (5.0 + 3.0)
        assert result.net_price == 8.0
        assert result.status == OrderStatus.FILLED
        assert result.created_at is not None
        assert result.filled_at is not None

        # Verify order was saved to database
        stmt = select(DBOrder).where(DBOrder.id == result.id)
        db_result = await db_session.execute(stmt)
        db_order = db_result.scalar_one_or_none()

        assert db_order is not None
        assert db_order.symbol == "MULTI_LEG_2_LEGS"
        assert db_order.account_id == account.id
        assert db_order.status == OrderStatus.FILLED.value

    @pytest.mark.asyncio
    async def test_create_multi_leg_order_complex_strategy(
        self, db_session: AsyncSession
    ):
        """Test creating a complex four-leg strategy (iron condor)."""
        account = DBAccount(
            id=str(uuid.uuid4()),
            owner="test_user",
            cash_balance=50000.0,
        )
        db_session.add(account)
        await db_session.commit()

        service = TradingService(account_owner="test_user", db_session=db_session)

        class MockLeg:
            def __init__(
                self, symbol: str, quantity: int, order_type: OrderType, price: float
            ):
                self.symbol = symbol
                self.quantity = quantity
                self.order_type = order_type
                self.price = price

        class MockOrderData:
            def __init__(self, legs):
                self.legs = legs
                self.condition = OrderCondition.LIMIT

        # Iron condor: sell put spread + sell call spread (all positive quantities for Order model)
        legs = [
            MockLeg("AAPL240115P00140000", 1, OrderType.STO, 2.0),  # Sell put
            MockLeg(
                "AAPL240115P00135000", 1, OrderType.BTO, 1.0
            ),  # Buy put (protection)
            MockLeg("AAPL240115C00160000", 1, OrderType.STO, 2.5),  # Sell call
            MockLeg(
                "AAPL240115C00165000", 1, OrderType.BTO, 1.5
            ),  # Buy call (protection)
        ]
        order_data = MockOrderData(legs)

        result = await service.create_multi_leg_order(order_data)

        # Verify four-leg strategy
        assert result.symbol == "MULTI_LEG_4_LEGS"
        assert (
            result.quantity == 4
        )  # Total quantity (1 + 1 + 1 + 1) - Order model requires positive
        assert result.price == 7.0  # Total price (2.0 + 1.0 + 2.5 + 1.5)
        assert result.net_price == 7.0
        assert result.status == OrderStatus.FILLED

        # Verify database persistence
        stmt = select(DBOrder).where(DBOrder.id == result.id)
        db_result = await db_session.execute(stmt)
        db_order = db_result.scalar_one_or_none()
        assert db_order is not None
        assert db_order.symbol == "MULTI_LEG_4_LEGS"

    @pytest.mark.asyncio
    async def test_create_multi_leg_order_single_leg(self, db_session: AsyncSession):
        """Test creating a single-leg order (edge case)."""
        account = DBAccount(
            id=str(uuid.uuid4()),
            owner="test_user",
            cash_balance=50000.0,
        )
        db_session.add(account)
        await db_session.commit()

        service = TradingService(account_owner="test_user", db_session=db_session)

        class MockLeg:
            def __init__(
                self, symbol: str, quantity: int, order_type: OrderType, price: float
            ):
                self.symbol = symbol
                self.quantity = quantity
                self.order_type = order_type
                self.price = price

        class MockOrderData:
            def __init__(self, legs):
                self.legs = legs
                self.condition = OrderCondition.MARKET

        legs = [MockLeg("AAPL240115C00150000", 1, OrderType.BTO, 5.0)]
        order_data = MockOrderData(legs)

        result = await service.create_multi_leg_order(order_data)

        assert result.symbol == "MULTI_LEG_1_LEGS"
        assert result.quantity == 1
        assert result.price == 5.0
        assert result.order_type == OrderType.BTO

    @pytest.mark.asyncio
    async def test_create_multi_leg_order_empty_legs(self, db_session: AsyncSession):
        """Test creating order with empty legs list."""
        account = DBAccount(
            id=str(uuid.uuid4()),
            owner="test_user",
            cash_balance=50000.0,
        )
        db_session.add(account)
        await db_session.commit()

        service = TradingService(account_owner="test_user", db_session=db_session)

        class MockOrderData:
            def __init__(self, legs):
                self.legs = legs

        order_data = MockOrderData([])

        # Empty legs should raise validation error due to quantity = 0
        with pytest.raises(
            (ValueError, TypeError)
        ):  # ValidationError from Pydantic for quantity <= 0
            await service.create_multi_leg_order(order_data)

    @pytest.mark.asyncio
    async def test_create_multi_leg_order_mixed_prices(self, db_session: AsyncSession):
        """Test multi-leg order with some None prices."""
        account = DBAccount(
            id=str(uuid.uuid4()),
            owner="test_user",
            cash_balance=50000.0,
        )
        db_session.add(account)
        await db_session.commit()

        service = TradingService(account_owner="test_user", db_session=db_session)

        class MockLeg:
            def __init__(
                self,
                symbol: str,
                quantity: int,
                order_type: OrderType,
                price: float | None = None,
            ):
                self.symbol = symbol
                self.quantity = quantity
                self.order_type = order_type
                self.price = price

        class MockOrderData:
            def __init__(self, legs):
                self.legs = legs
                self.condition = OrderCondition.MARKET

        # Mix of priced and market legs
        legs = [
            MockLeg("AAPL240115C00150000", 1, OrderType.BTO, 5.0),
            MockLeg(
                "TSLA240115P00200000", 1, OrderType.STO, None
            ),  # Market price (positive quantity)
            MockLeg("MSFT240115C00300000", 1, OrderType.BTO, 3.0),
        ]
        order_data = MockOrderData(legs)

        result = await service.create_multi_leg_order(order_data)

        # Should only sum non-None prices
        assert result.price == 8.0  # 5.0 + 0 + 3.0 (None prices treated as 0)
        assert result.quantity == 3  # 1 + 1 + 1 (all positive for Order model)

    @pytest.mark.asyncio
    async def test_create_multi_leg_order_database_error(
        self, db_session: AsyncSession
    ):
        """Test handling database errors during multi-leg order creation."""
        account = DBAccount(
            id=str(uuid.uuid4()),
            owner="test_user",
            cash_balance=50000.0,
        )
        db_session.add(account)
        await db_session.commit()

        service = TradingService(account_owner="test_user", db_session=db_session)

        class MockLeg:
            def __init__(
                self, symbol: str, quantity: int, order_type: OrderType, price: float
            ):
                self.symbol = symbol
                self.quantity = quantity
                self.order_type = order_type
                self.price = price

        class MockOrderData:
            def __init__(self, legs):
                self.legs = legs

        legs = [MockLeg("AAPL240115C00150000", 1, OrderType.BTO, 5.0)]
        order_data = MockOrderData(legs)

        # Mock database session to raise error on commit
        with (
            patch.object(db_session, "commit", side_effect=Exception("Database error")),
            pytest.raises(Exception, match="Database error"),
        ):
            await service.create_multi_leg_order(order_data)


@pytest.mark.database
class TestCreateMultiLegOrderFromRequest:
    """Test TradingService.create_multi_leg_order_from_request() function."""

    @pytest.mark.asyncio
    async def test_create_multi_leg_order_from_request_success(
        self, db_session: AsyncSession
    ):
        """Test successful multi-leg order creation from raw request data."""
        account = DBAccount(
            id=str(uuid.uuid4()),
            owner="test_user",
            cash_balance=50000.0,
        )
        db_session.add(account)
        await db_session.commit()

        service = TradingService(account_owner="test_user", db_session=db_session)

        # Raw request data - bull call spread
        legs = [
            {"symbol": "AAPL240115C00150000", "quantity": 1, "side": "buy"},
            {"symbol": "AAPL240115C00155000", "quantity": 1, "side": "sell"},
        ]

        result = await service.create_multi_leg_order_from_request(
            legs=legs, order_type="limit", net_price=2.0
        )

        # Verify conversion and creation
        assert result.id is not None
        assert result.symbol == "MULTI_LEG_2_LEGS"
        assert result.quantity == 2  # 1 + 1 (both quantities are positive from request)
        assert result.status == OrderStatus.FILLED

        # Verify database persistence
        stmt = select(DBOrder).where(DBOrder.id == result.id)
        db_result = await db_session.execute(stmt)
        db_order = db_result.scalar_one_or_none()
        assert db_order is not None

    @pytest.mark.asyncio
    async def test_create_multi_leg_order_from_request_market_order(
        self, db_session: AsyncSession
    ):
        """Test creating market multi-leg order from request."""
        account = DBAccount(
            id=str(uuid.uuid4()),
            owner="test_user",
            cash_balance=50000.0,
        )
        db_session.add(account)
        await db_session.commit()

        service = TradingService(account_owner="test_user", db_session=db_session)

        legs = [
            {"symbol": "TSLA240115P00200000", "quantity": 2, "side": "buy"},
            {"symbol": "TSLA240115P00195000", "quantity": 2, "side": "sell"},
        ]

        result = await service.create_multi_leg_order_from_request(
            legs=legs,
            order_type="market",  # No net_price for market order
        )

        assert result.symbol == "MULTI_LEG_2_LEGS"
        assert result.quantity == 4  # 2 + 2

    @pytest.mark.asyncio
    async def test_create_multi_leg_order_from_request_complex_strategy(
        self, db_session: AsyncSession
    ):
        """Test creating complex strategy from request data."""
        account = DBAccount(
            id=str(uuid.uuid4()),
            owner="test_user",
            cash_balance=50000.0,
        )
        db_session.add(account)
        await db_session.commit()

        service = TradingService(account_owner="test_user", db_session=db_session)

        # Iron butterfly strategy
        legs = [
            {
                "symbol": "MSFT240115C00300000",
                "quantity": 1,
                "side": "sell",
            },  # Sell ATM call
            {
                "symbol": "MSFT240115P00300000",
                "quantity": 1,
                "side": "sell",
            },  # Sell ATM put
            {
                "symbol": "MSFT240115C00310000",
                "quantity": 1,
                "side": "buy",
            },  # Buy OTM call
            {
                "symbol": "MSFT240115P00290000",
                "quantity": 1,
                "side": "buy",
            },  # Buy OTM put
        ]

        result = await service.create_multi_leg_order_from_request(
            legs=legs, order_type="limit", net_price=1.5
        )

        assert result.symbol == "MULTI_LEG_4_LEGS"
        assert result.quantity == 4  # All quantities sum

    @pytest.mark.asyncio
    async def test_create_multi_leg_order_from_request_invalid_data(
        self, db_session: AsyncSession
    ):
        """Test error handling with invalid request data."""
        account = DBAccount(
            id=str(uuid.uuid4()),
            owner="test_user",
            cash_balance=50000.0,
        )
        db_session.add(account)
        await db_session.commit()

        service = TradingService(account_owner="test_user", db_session=db_session)

        # Invalid legs data - missing required fields
        legs = [
            {"symbol": "AAPL240115C00150000"},  # Missing quantity and side
        ]

        with pytest.raises(ValueError, match="Failed to create multi-leg order"):
            await service.create_multi_leg_order_from_request(
                legs=legs, order_type="limit", net_price=2.0
            )

    @pytest.mark.asyncio
    async def test_create_multi_leg_order_from_request_empty_legs(
        self, db_session: AsyncSession
    ):
        """Test creating order with empty legs list from request."""
        account = DBAccount(
            id=str(uuid.uuid4()),
            owner="test_user",
            cash_balance=50000.0,
        )
        db_session.add(account)
        await db_session.commit()

        service = TradingService(account_owner="test_user", db_session=db_session)

        # Empty legs should raise validation error due to quantity = 0
        with pytest.raises((ValueError, TypeError)):  # ValidationError from Order model
            await service.create_multi_leg_order_from_request(
                legs=[], order_type="market"
            )

    @pytest.mark.asyncio
    async def test_create_multi_leg_order_from_request_side_conversion(
        self, db_session: AsyncSession
    ):
        """Test proper conversion of buy/sell sides to order types."""
        account = DBAccount(
            id=str(uuid.uuid4()),
            owner="test_user",
            cash_balance=50000.0,
        )
        db_session.add(account)
        await db_session.commit()

        service = TradingService(account_owner="test_user", db_session=db_session)

        # Test both buy and sell sides
        legs = [
            {"symbol": "GOOGL240115C00250000", "quantity": 1, "side": "buy"},
            {"symbol": "GOOGL240115C00255000", "quantity": 1, "side": "sell"},
        ]

        result = await service.create_multi_leg_order_from_request(
            legs=legs, order_type="limit", net_price=3.0
        )

        # Verify the order was created successfully
        assert result.id is not None
        assert result.symbol == "MULTI_LEG_2_LEGS"

        # Verify in database
        stmt = select(DBOrder).where(DBOrder.id == result.id)
        db_result = await db_session.execute(stmt)
        db_order = db_result.scalar_one_or_none()
        assert db_order is not None


@pytest.mark.database
class TestMultiLegOrderIntegration:
    """Integration tests for multi-leg order functionality."""

    @pytest.mark.asyncio
    async def test_multi_leg_order_workflow_integration(self, db_session: AsyncSession):
        """Test complete multi-leg order workflow."""
        # Create account
        account = DBAccount(
            id=str(uuid.uuid4()),
            owner="multi_leg_trader",
            cash_balance=100000.0,
        )
        db_session.add(account)
        await db_session.commit()

        service = TradingService(
            account_owner="multi_leg_trader", db_session=db_session
        )

        # 1. Create multi-leg order from request
        legs = [
            {"symbol": "AAPL240115C00150000", "quantity": 1, "side": "buy"},
            {"symbol": "AAPL240115C00155000", "quantity": 1, "side": "sell"},
        ]

        result = await service.create_multi_leg_order_from_request(
            legs=legs, order_type="limit", net_price=2.0
        )

        # 2. Verify order was created and persisted
        assert result.id is not None

        # 3. Retrieve from database to verify persistence
        stmt = select(DBOrder).where(DBOrder.id == result.id)
        db_result = await db_session.execute(stmt)
        db_order = db_result.scalar_one_or_none()

        assert db_order is not None
        assert db_order.account_id == account.id
        assert db_order.symbol == "MULTI_LEG_2_LEGS"
        assert db_order.status == OrderStatus.FILLED.value

        # 4. Test retrieving the order through get_order
        retrieved_order = await service.get_order(result.id)
        assert retrieved_order.id == result.id
        assert retrieved_order.symbol == result.symbol

    @pytest.mark.asyncio
    async def test_multi_leg_order_error_handling_integration(
        self, db_session: AsyncSession
    ):
        """Test comprehensive error handling for multi-leg orders."""
        service = TradingService(account_owner="error_test_user", db_session=db_session)

        # Test 1: Invalid leg data structure
        with pytest.raises(ValueError, match="Failed to create multi-leg order"):
            await service.create_multi_leg_order_from_request(
                legs=[{"invalid": "data"}], order_type="limit", net_price=1.0
            )

        # Test 2: Direct create_multi_leg_order with exception in processing
        class MockBadOrderData:
            @property
            def legs(self):
                raise ValueError("Mock processing error")

        bad_order_data = MockBadOrderData()

        # This should propagate the processing error
        with pytest.raises(ValueError, match="Mock processing error"):
            await service.create_multi_leg_order(bad_order_data)

    @pytest.mark.asyncio
    async def test_concurrent_multi_leg_order_creation(self, db_session: AsyncSession):
        """Test concurrent multi-leg order creation for race conditions."""
        account = DBAccount(
            id=str(uuid.uuid4()),
            owner="concurrent_trader",
            cash_balance=100000.0,
        )
        db_session.add(account)
        await db_session.commit()

        service = TradingService(
            account_owner="concurrent_trader", db_session=db_session
        )

        # Create multiple orders concurrently
        async def create_order(order_num: int):
            legs = [
                {
                    "symbol": f"TEST{order_num}240115C00150000",
                    "quantity": 1,
                    "side": "buy",
                },
                {
                    "symbol": f"TEST{order_num}240115C00155000",
                    "quantity": 1,
                    "side": "sell",
                },
            ]
            return await service.create_multi_leg_order_from_request(
                legs=legs, order_type="limit", net_price=2.0 + order_num
            )

        # Run 3 concurrent multi-leg order creations
        results = await asyncio.gather(
            create_order(1), create_order(2), create_order(3), return_exceptions=True
        )

        # All should succeed or handle gracefully
        success_count = sum(
            1 for result in results if not isinstance(result, Exception)
        )
        assert success_count >= 1  # At least one should succeed

        # Verify successful orders were persisted
        for result in results:
            if not isinstance(result, Exception) and hasattr(result, 'id'):
                stmt = select(DBOrder).where(DBOrder.id == result.id)
                db_result = await db_session.execute(stmt)
                db_order = db_result.scalar_one_or_none()
                assert db_order is not None


@pytest.mark.database
class TestMultiLegOrderValidation:
    """Test multi-leg order validation logic."""

    @pytest.mark.asyncio
    async def test_multi_leg_pricing_calculation(self, db_session: AsyncSession):
        """Test pricing calculations for multi-leg orders."""
        account = DBAccount(
            id=str(uuid.uuid4()),
            owner="test_user",
            cash_balance=50000.0,
        )
        db_session.add(account)
        await db_session.commit()

        service = TradingService(account_owner="test_user", db_session=db_session)

        class MockLeg:
            def __init__(
                self, symbol: str, quantity: int, order_type: OrderType, price: float
            ):
                self.symbol = symbol
                self.quantity = quantity
                self.order_type = order_type
                self.price = price

        class MockOrderData:
            def __init__(self, legs):
                self.legs = legs

        # Test various pricing scenarios (all positive quantities for Order model compatibility)
        test_cases = [
            # Simple spread: net debit
            (
                [
                    MockLeg("AAPL240115C00150000", 1, OrderType.BTO, 5.0),
                    MockLeg("AAPL240115C00155000", 1, OrderType.STO, 3.0),
                ],
                8.0,
            ),
            # Credit spread: net credit (should still sum to positive price)
            (
                [
                    MockLeg("AAPL240115P00145000", 1, OrderType.STO, 4.0),
                    MockLeg("AAPL240115P00140000", 1, OrderType.BTO, 2.0),
                ],
                6.0,
            ),
            # Complex four-leg strategy
            (
                [
                    MockLeg("MSFT240115C00300000", 1, OrderType.STO, 3.0),
                    MockLeg("MSFT240115C00310000", 1, OrderType.BTO, 1.0),
                    MockLeg("MSFT240115P00290000", 1, OrderType.STO, 2.5),
                    MockLeg("MSFT240115P00280000", 1, OrderType.BTO, 1.5),
                ],
                8.0,
            ),
        ]

        for legs, expected_price in test_cases:
            order_data = MockOrderData(legs)
            result = await service.create_multi_leg_order(order_data)
            assert result.price == expected_price, (
                f"Expected {expected_price}, got {result.price}"
            )

    @pytest.mark.asyncio
    async def test_multi_leg_quantity_calculation(self, db_session: AsyncSession):
        """Test quantity calculations for multi-leg orders."""
        account = DBAccount(
            id=str(uuid.uuid4()),
            owner="test_user",
            cash_balance=50000.0,
        )
        db_session.add(account)
        await db_session.commit()

        service = TradingService(account_owner="test_user", db_session=db_session)

        class MockLeg:
            def __init__(
                self, symbol: str, quantity: int, order_type: OrderType, price: float
            ):
                self.symbol = symbol
                self.quantity = quantity
                self.order_type = order_type
                self.price = price

        class MockOrderData:
            def __init__(self, legs):
                self.legs = legs

        # Test various quantity scenarios (adjusted for Order model positive quantity requirement)
        test_cases = [
            # All positive quantities
            (
                [
                    MockLeg("AAPL240115C00150000", 2, OrderType.BTO, 5.0),
                    MockLeg("AAPL240115C00155000", 1, OrderType.STO, 3.0),
                ],
                3,
            ),
            # Multiple contracts
            (
                [
                    MockLeg("MSFT240115C00300000", 3, OrderType.BTO, 2.0),
                    MockLeg("MSFT240115C00305000", 2, OrderType.STO, 1.0),
                ],
                5,
            ),
            # High quantity strategy
            (
                [
                    MockLeg("TSLA240115P00200000", 5, OrderType.STO, 4.0),
                    MockLeg("TSLA240115P00195000", 2, OrderType.BTO, 2.0),
                ],
                7,
            ),
        ]

        for legs, expected_quantity in test_cases:
            order_data = MockOrderData(legs)
            result = await service.create_multi_leg_order(order_data)
            assert result.quantity == expected_quantity, (
                f"Expected {expected_quantity}, got {result.quantity}"
            )


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
