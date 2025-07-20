"""
End-to-end tests for complete order flow scenarios.

Tests the complete lifecycle from order creation through execution,
position creation, and account balance updates.
"""

from httpx import AsyncClient

from tests.e2e.conftest import E2ETestHelpers


class TestOrderFlow:
    """Test complete order flow scenarios."""

    async def test_market_order_complete_flow(
        self,
        test_client: AsyncClient,
        test_account_data: dict,
        e2e_helpers: E2ETestHelpers,
    ):
        """Test complete market order from creation to execution."""
        # 1. Create account with initial balance
        account_response = await test_client.post(
            "/api/v1/accounts", json=test_account_data
        )
        assert account_response.status_code == 201
        account = account_response.json()
        account_id = account["id"]
        initial_balance = account["cash_balance"]

        # 2. Create market order
        order_data = {
            "symbol": "AAPL",
            "order_type": "buy",
            "quantity": 100,
            "price": 150.0,
            "condition": "market",
        }
        order_response = await test_client.post(
            f"/api/v1/accounts/{account_id}/orders", json=order_data
        )
        assert order_response.status_code == 201
        order = order_response.json()
        order_id = order["id"]

        # 3. Verify order in database
        order_check = await test_client.get(f"/api/v1/orders/{order_id}")
        assert order_check.status_code == 200
        order_data_check = order_check.json()
        assert order_data_check["status"] == "pending"
        assert order_data_check["symbol"] == "AAPL"
        assert order_data_check["quantity"] == 100

        # 4. Simulate order execution
        execution_data = {"status": "filled", "filled_price": 149.50}
        execution_response = await test_client.patch(
            f"/api/v1/orders/{order_id}", json=execution_data
        )
        assert execution_response.status_code == 200

        # 5. Verify position created
        positions_response = await test_client.get(
            f"/api/v1/accounts/{account_id}/positions"
        )
        assert positions_response.status_code == 200
        positions = positions_response.json()
        assert len(positions) == 1

        position = positions[0]
        assert position["symbol"] == "AAPL"
        assert position["quantity"] == 100
        assert abs(position["avg_price"] - 149.50) < 0.01

        # 6. Verify account balance updated
        final_balance = await e2e_helpers.get_account_balance(test_client, account_id)
        expected_balance = initial_balance - (100 * 149.50)
        assert abs(final_balance - expected_balance) < 0.01

    async def test_limit_order_flow(
        self,
        test_client: AsyncClient,
        created_test_account: str,
        e2e_helpers: E2ETestHelpers,
    ):
        """Test limit order creation and execution."""
        account_id = created_test_account
        initial_balance = await e2e_helpers.get_account_balance(test_client, account_id)

        # Create limit order
        order_data = {
            "symbol": "GOOGL",
            "order_type": "buy",
            "quantity": 50,
            "price": 2800.0,
            "condition": "limit",
        }

        order = await e2e_helpers.create_and_fill_order(
            test_client, account_id, order_data, fill_price=2795.0
        )

        # Verify position created with correct average price
        positions_response = await test_client.get(
            f"/api/v1/accounts/{account_id}/positions"
        )
        assert positions_response.status_code == 200
        positions = positions_response.json()

        googl_position = next((p for p in positions if p["symbol"] == "GOOGL"), None)
        assert googl_position is not None
        assert googl_position["quantity"] == 50
        assert abs(googl_position["avg_price"] - 2795.0) < 0.01

        # Verify account balance
        final_balance = await e2e_helpers.get_account_balance(test_client, account_id)
        expected_balance = initial_balance - (50 * 2795.0)
        assert abs(final_balance - expected_balance) < 0.01

    async def test_sell_order_flow(
        self,
        test_client: AsyncClient,
        populated_test_account: dict,
        e2e_helpers: E2ETestHelpers,
    ):
        """Test selling existing position."""
        account_id = populated_test_account["account_id"]
        initial_balance = await e2e_helpers.get_account_balance(test_client, account_id)

        # Get current positions
        positions_response = await test_client.get(
            f"/api/v1/accounts/{account_id}/positions"
        )
        assert positions_response.status_code == 200
        positions = positions_response.json()
        assert len(positions) > 0

        # Sell partial position
        position_to_sell = positions[0]
        sell_quantity = position_to_sell["quantity"] // 2  # Sell half

        sell_order_data = {
            "symbol": position_to_sell["symbol"],
            "order_type": "sell",
            "quantity": sell_quantity,
            "price": 155.0,
            "condition": "limit",
        }

        sell_order = await e2e_helpers.create_and_fill_order(
            test_client, account_id, sell_order_data, fill_price=155.0
        )

        # Verify position quantity reduced
        updated_positions_response = await test_client.get(
            f"/api/v1/accounts/{account_id}/positions"
        )
        assert updated_positions_response.status_code == 200
        updated_positions = updated_positions_response.json()

        updated_position = next(
            (p for p in updated_positions if p["symbol"] == position_to_sell["symbol"]),
            None,
        )

        if updated_position:  # Position should still exist if partially sold
            expected_quantity = position_to_sell["quantity"] - sell_quantity
            assert updated_position["quantity"] == expected_quantity

        # Verify account balance increased
        final_balance = await e2e_helpers.get_account_balance(test_client, account_id)
        expected_increase = sell_quantity * 155.0
        assert final_balance >= initial_balance + expected_increase - 0.01

    async def test_order_cancellation_flow(
        self, test_client: AsyncClient, created_test_account: str
    ):
        """Test order cancellation before execution."""
        account_id = created_test_account

        # Create order
        order_data = {
            "symbol": "MSFT",
            "order_type": "buy",
            "quantity": 25,
            "price": 300.0,
            "condition": "limit",
        }

        order_response = await test_client.post(
            f"/api/v1/accounts/{account_id}/orders", json=order_data
        )
        assert order_response.status_code == 201
        order = order_response.json()
        order_id = order["id"]

        # Verify order is pending
        order_check = await test_client.get(f"/api/v1/orders/{order_id}")
        assert order_check.status_code == 200
        assert order_check.json()["status"] == "pending"

        # Cancel order
        cancel_response = await test_client.delete(f"/api/v1/orders/{order_id}")
        assert cancel_response.status_code == 200

        # Verify order is cancelled
        cancelled_order_check = await test_client.get(f"/api/v1/orders/{order_id}")
        assert cancelled_order_check.status_code == 200
        assert cancelled_order_check.json()["status"] == "cancelled"

        # Verify no position created
        positions_response = await test_client.get(
            f"/api/v1/accounts/{account_id}/positions"
        )
        assert positions_response.status_code == 200
        positions = positions_response.json()

        msft_position = next((p for p in positions if p["symbol"] == "MSFT"), None)
        assert msft_position is None

    async def test_invalid_order_scenarios(
        self,
        test_client: AsyncClient,
        created_test_account: str,
        e2e_helpers: E2ETestHelpers,
    ):
        """Test various invalid order scenarios."""
        account_id = created_test_account
        current_balance = await e2e_helpers.get_account_balance(test_client, account_id)

        # Test insufficient funds
        expensive_order_data = {
            "symbol": "AAPL",
            "order_type": "buy",
            "quantity": 1000000,  # Way too many shares
            "price": 150.0,
            "condition": "limit",
        }

        expensive_response = await test_client.post(
            f"/api/v1/accounts/{account_id}/orders", json=expensive_order_data
        )
        # This should either be rejected (400) or created but fail validation
        assert expensive_response.status_code in [400, 422]

        # Test invalid symbol
        invalid_symbol_data = {
            "symbol": "INVALID_SYMBOL_XYZ",
            "order_type": "buy",
            "quantity": 10,
            "price": 100.0,
            "condition": "limit",
        }

        invalid_response = await test_client.post(
            f"/api/v1/accounts/{account_id}/orders", json=invalid_symbol_data
        )
        # Should be rejected due to invalid symbol
        assert invalid_response.status_code in [400, 422, 404]

        # Test zero quantity
        zero_quantity_data = {
            "symbol": "AAPL",
            "order_type": "buy",
            "quantity": 0,  # Invalid quantity
            "price": 150.0,
            "condition": "limit",
        }

        zero_response = await test_client.post(
            f"/api/v1/accounts/{account_id}/orders", json=zero_quantity_data
        )
        # Should be rejected due to validation
        assert zero_response.status_code == 422

    async def test_multiple_orders_same_symbol(
        self,
        test_client: AsyncClient,
        created_test_account: str,
        e2e_helpers: E2ETestHelpers,
    ):
        """Test multiple orders for the same symbol."""
        account_id = created_test_account

        # Create multiple orders for AAPL
        orders = []
        for i in range(3):
            order_data = {
                "symbol": "AAPL",
                "order_type": "buy",
                "quantity": 10 * (i + 1),  # 10, 20, 30 shares
                "price": 150.0 + i,  # $150, $151, $152
                "condition": "limit",
            }

            order = await e2e_helpers.create_and_fill_order(
                test_client, account_id, order_data
            )
            orders.append(order)

        # Verify single position with combined quantity and weighted average price
        positions_response = await test_client.get(
            f"/api/v1/accounts/{account_id}/positions"
        )
        assert positions_response.status_code == 200
        positions = positions_response.json()

        aapl_positions = [p for p in positions if p["symbol"] == "AAPL"]
        assert len(aapl_positions) == 1

        position = aapl_positions[0]
        expected_total_quantity = 10 + 20 + 30  # 60 shares
        assert position["quantity"] == expected_total_quantity

        # Calculate expected weighted average price
        # (10*150 + 20*151 + 30*152) / 60 = (1500 + 3020 + 4560) / 60 = 150.77
        expected_avg_price = (10 * 150.0 + 20 * 151.0 + 30 * 152.0) / 60
        assert abs(position["avg_price"] - expected_avg_price) < 0.01

    async def test_portfolio_calculation_after_trades(
        self,
        test_client: AsyncClient,
        created_test_account: str,
        e2e_helpers: E2ETestHelpers,
    ):
        """Test portfolio calculations after various trades."""
        account_id = created_test_account
        initial_balance = await e2e_helpers.get_account_balance(test_client, account_id)

        # Execute several trades
        trades = [
            {"symbol": "AAPL", "quantity": 100, "price": 150.0},
            {"symbol": "GOOGL", "quantity": 10, "price": 2800.0},
            {"symbol": "MSFT", "quantity": 50, "price": 300.0},
        ]

        total_invested = 0
        for trade in trades:
            order_data = {
                "symbol": trade["symbol"],
                "order_type": "buy",
                "quantity": trade["quantity"],
                "price": trade["price"],
                "condition": "limit",
            }

            await e2e_helpers.create_and_fill_order(test_client, account_id, order_data)
            total_invested += trade["quantity"] * trade["price"]

        # Get portfolio summary
        portfolio_response = await test_client.get(
            f"/api/v1/accounts/{account_id}/portfolio"
        )
        assert portfolio_response.status_code == 200
        portfolio = portfolio_response.json()

        # Verify portfolio calculations
        assert len(portfolio["positions"]) == 3

        # Check individual positions exist
        symbols = {pos["symbol"] for pos in portfolio["positions"]}
        assert symbols == {"AAPL", "GOOGL", "MSFT"}

        # Verify cash balance
        expected_cash_balance = initial_balance - total_invested
        assert abs(portfolio["cash_balance"] - expected_cash_balance) < 0.01

        # Verify total portfolio value (cash + positions)
        positions_value = sum(
            pos["quantity"] * pos["current_price"] for pos in portfolio["positions"]
        )
        expected_total_value = expected_cash_balance + positions_value
        assert abs(portfolio["total_value"] - expected_total_value) < 0.01
