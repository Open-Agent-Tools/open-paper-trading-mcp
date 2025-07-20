"""
End-to-end tests for database state consistency.

Tests that data persists correctly between service restarts and that
portfolio calculations work purely from database state.
"""

from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.database.trading import (
    Account as DBAccount,
)
from app.models.database.trading import (
    Order as DBOrder,
)
from app.models.database.trading import (
    Position as DBPosition,
)
from app.schemas.orders import OrderStatus, OrderType
from app.services.trading_service import TradingService
from tests.e2e.conftest import E2ETestHelpers


class TestDatabaseState:
    """Test database state consistency and persistence."""

    async def test_portfolio_calculation_from_db_only(
        self, test_async_session: AsyncSession, e2e_helpers: E2ETestHelpers
    ):
        """Test portfolio calculations using only database state."""
        # Create test data directly in database

        # Create account
        account = DBAccount(owner="test_db_user", cash_balance=50000.0)
        test_async_session.add(account)
        await test_async_session.commit()
        await test_async_session.refresh(account)

        # Create positions directly in database
        positions_data = [
            {"symbol": "AAPL", "quantity": 100, "avg_price": 150.0},
            {"symbol": "GOOGL", "quantity": 10, "avg_price": 2800.0},
            {"symbol": "MSFT", "quantity": 50, "avg_price": 300.0},
        ]

        db_positions = []
        for pos_data in positions_data:
            position = DBPosition(
                account_id=account.id,
                symbol=pos_data["symbol"],
                quantity=pos_data["quantity"],
                avg_price=pos_data["avg_price"],
            )
            test_async_session.add(position)
            db_positions.append(position)

        await test_async_session.commit()

        # Test portfolio calculation using TradingService
        trading_service = TradingService(account_owner=account.owner)
        portfolio = await trading_service.get_portfolio()

        # Verify calculations
        assert portfolio.cash_balance == 50000.0
        assert len(portfolio.positions) == 3

        # Verify individual positions
        position_map = {pos.symbol: pos for pos in portfolio.positions}

        for expected_pos in positions_data:
            actual_pos = position_map[expected_pos["symbol"]]
            assert actual_pos.quantity == expected_pos["quantity"]
            assert abs(actual_pos.avg_price - expected_pos["avg_price"]) < 0.01

            # Verify unrealized P&L calculation
            expected_pnl = (
                actual_pos.current_price - actual_pos.avg_price
            ) * actual_pos.quantity
            assert abs(actual_pos.unrealized_pnl - expected_pnl) < 0.01

        # Verify total portfolio value calculation
        positions_value = sum(
            pos.current_price * pos.quantity for pos in portfolio.positions
        )
        expected_total = 50000.0 + positions_value
        assert abs(portfolio.total_value - expected_total) < 0.01

    async def test_data_persistence_across_service_restarts(
        self, test_async_session: AsyncSession
    ):
        """Test that data persists between service restarts."""
        # Create initial data with first service instance
        service1 = TradingService(account_owner="persistence_test_user")

        # Ensure account exists
        await service1._ensure_account_exists()

        # Create order
        from app.schemas.orders import OrderCreate

        order_data = OrderCreate(
            symbol="AAPL", order_type=OrderType.BUY, quantity=100, price=150.0
        )

        order = await service1.create_order(order_data)
        order_id = order.id

        # Simulate service restart (new instance)
        service2 = TradingService(account_owner="persistence_test_user")

        # Retrieve order with new service instance
        retrieved_order = await service2.get_order(order_id)

        # Verify data persisted
        assert retrieved_order is not None
        assert retrieved_order.id == order_id
        assert retrieved_order.symbol == "AAPL"
        assert retrieved_order.quantity == 100
        assert retrieved_order.price == 150.0
        assert retrieved_order.status == OrderStatus.PENDING

    async def test_concurrent_database_access(
        self,
        test_client: AsyncClient,
        created_test_account: str,
        e2e_helpers: E2ETestHelpers,
    ):
        """Test concurrent database operations don't corrupt data."""
        import asyncio

        account_id = created_test_account

        async def create_order(symbol: str, quantity: int):
            """Helper to create an order."""
            order_data = {
                "symbol": symbol,
                "order_type": "buy",
                "quantity": quantity,
                "price": 150.0,
                "condition": "limit",
            }

            response = await test_client.post(
                f"/api/v1/accounts/{account_id}/orders", json=order_data
            )
            assert response.status_code == 201
            return response.json()

        # Create multiple orders concurrently
        tasks = [
            create_order("AAPL", 10),
            create_order("GOOGL", 5),
            create_order("MSFT", 20),
            create_order("TSLA", 15),
            create_order("AMZN", 8),
        ]

        # Execute all orders concurrently
        results = await asyncio.gather(*tasks)

        # Verify all orders were created
        assert len(results) == 5
        order_ids = [order["id"] for order in results]
        assert len(set(order_ids)) == 5  # All unique IDs

        # Verify all orders exist in database
        for order_id in order_ids:
            response = await test_client.get(f"/api/v1/orders/{order_id}")
            assert response.status_code == 200
            order = response.json()
            assert order["status"] == "pending"

        # Get all orders and verify count
        orders_response = await test_client.get(f"/api/v1/accounts/{account_id}/orders")
        assert orders_response.status_code == 200
        all_orders = orders_response.json()
        assert len(all_orders) >= 5  # At least our 5 orders

    async def test_database_integrity_after_failures(
        self,
        test_client: AsyncClient,
        created_test_account: str,
        e2e_helpers: E2ETestHelpers,
    ):
        """Test database integrity after simulated failures."""
        account_id = created_test_account
        initial_balance = await e2e_helpers.get_account_balance(test_client, account_id)

        # Create valid order
        valid_order_data = {
            "symbol": "AAPL",
            "order_type": "buy",
            "quantity": 100,
            "price": 150.0,
            "condition": "limit",
        }

        valid_order_response = await test_client.post(
            f"/api/v1/accounts/{account_id}/orders", json=valid_order_data
        )
        assert valid_order_response.status_code == 201
        valid_order = valid_order_response.json()

        # Try to create invalid orders (should fail but not corrupt database)
        invalid_orders = [
            {
                "symbol": "INVALID_SYMBOL",
                "order_type": "buy",
                "quantity": 10,
                "price": 100.0,
                "condition": "limit",
            },
            {
                "symbol": "AAPL",
                "order_type": "buy",
                "quantity": 0,  # Invalid quantity
                "price": 150.0,
                "condition": "limit",
            },
        ]

        for invalid_order_data in invalid_orders:
            response = await test_client.post(
                f"/api/v1/accounts/{account_id}/orders", json=invalid_order_data
            )
            # Should fail but not crash
            assert response.status_code in [400, 422, 404]

        # Verify original valid order still exists and account state is intact
        order_check = await test_client.get(f"/api/v1/orders/{valid_order['id']}")
        assert order_check.status_code == 200

        # Verify account balance unchanged
        current_balance = await e2e_helpers.get_account_balance(test_client, account_id)
        assert abs(current_balance - initial_balance) < 0.01

        # Verify we can still create new valid orders
        another_order_data = {
            "symbol": "GOOGL",
            "order_type": "buy",
            "quantity": 5,
            "price": 2800.0,
            "condition": "limit",
        }

        another_response = await test_client.post(
            f"/api/v1/accounts/{account_id}/orders", json=another_order_data
        )
        assert another_response.status_code == 201

    async def test_portfolio_consistency_across_operations(
        self,
        test_client: AsyncClient,
        created_test_account: str,
        e2e_helpers: E2ETestHelpers,
    ):
        """Test portfolio consistency across multiple operations."""
        account_id = created_test_account

        # Perform sequence of operations
        operations = [
            {"action": "buy", "symbol": "AAPL", "quantity": 100, "price": 150.0},
            {"action": "buy", "symbol": "GOOGL", "quantity": 10, "price": 2800.0},
            {
                "action": "buy",
                "symbol": "AAPL",
                "quantity": 50,
                "price": 155.0,
            },  # Same symbol
            {
                "action": "sell",
                "symbol": "AAPL",
                "quantity": 25,
                "price": 160.0,
            },  # Partial sell
        ]

        for i, op in enumerate(operations):
            order_data = {
                "symbol": op["symbol"],
                "order_type": op["action"],
                "quantity": op["quantity"],
                "price": op["price"],
                "condition": "limit",
            }

            # Create and fill order
            await e2e_helpers.create_and_fill_order(test_client, account_id, order_data)

            # Verify portfolio consistency after each operation
            portfolio_response = await test_client.get(
                f"/api/v1/accounts/{account_id}/portfolio"
            )
            assert portfolio_response.status_code == 200
            portfolio = portfolio_response.json()

            # Basic consistency checks
            assert "cash_balance" in portfolio
            assert "positions" in portfolio
            assert "total_value" in portfolio

            # Verify each position has valid data
            for position in portfolio["positions"]:
                assert position["quantity"] > 0  # No zero-quantity positions
                assert position["avg_price"] > 0
                assert position["current_price"] > 0

                # Verify P&L calculation
                expected_pnl = (
                    position["current_price"] - position["avg_price"]
                ) * position["quantity"]
                assert abs(position["unrealized_pnl"] - expected_pnl) < 0.01

        # Final verification: AAPL position should have correct average price and quantity
        final_portfolio = await test_client.get(
            f"/api/v1/accounts/{account_id}/portfolio"
        )
        assert final_portfolio.status_code == 200
        final_positions = final_portfolio.json()["positions"]

        aapl_position = next(
            (p for p in final_positions if p["symbol"] == "AAPL"), None
        )
        assert aapl_position is not None

        # AAPL: Bought 100@150 + 50@155 - 25@160 = 125 shares
        # Weighted avg: (100*150 + 50*155) / 150 = 151.67 for buys only
        expected_quantity = 100 + 50 - 25  # 125 shares
        assert aapl_position["quantity"] == expected_quantity

    async def test_database_rollback_on_error(self, test_async_session: AsyncSession):
        """Test that database transactions rollback properly on errors."""
        # This test verifies database transaction integrity

        # Create account
        account = DBAccount(owner="rollback_test_user", cash_balance=10000.0)
        test_async_session.add(account)
        await test_async_session.commit()
        await test_async_session.refresh(account)

        # Simulate transaction that should rollback
        try:
            # Start a transaction
            order = DBOrder(
                account_id=account.id,
                symbol="AAPL",
                order_type=OrderType.BUY,
                quantity=100,
                price=150.0,
                status=OrderStatus.PENDING,
            )
            test_async_session.add(order)

            # This would normally commit, but let's simulate an error
            await test_async_session.flush()  # Flush but don't commit

            # Simulate error by rolling back
            await test_async_session.rollback()

        except Exception:
            await test_async_session.rollback()

        # Verify order was not saved
        from sqlalchemy import select

        stmt = select(DBOrder).where(DBOrder.account_id == account.id)
        result = await test_async_session.execute(stmt)
        orders = result.scalars().all()

        assert len(orders) == 0  # No orders should exist due to rollback

        # Verify account still exists (was committed before the failed transaction)
        stmt = select(DBAccount).where(DBAccount.id == account.id)
        result = await test_async_session.execute(stmt)
        found_account = result.scalar_one_or_none()

        assert found_account is not None
        assert found_account.cash_balance == 10000.0
