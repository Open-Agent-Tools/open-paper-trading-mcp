import json

from app.mcp.tools import (
    get_stock_quote,
    create_buy_order,
    create_sell_order,
    get_all_orders,
    get_order,
    cancel_order,
    get_portfolio,
    get_portfolio_summary,
    get_all_positions,
    get_position,
)
from app.mcp.tools import (
    GetQuoteArgs,
    CreateOrderArgs,
    GetOrderArgs,
    CancelOrderArgs,
    GetPositionArgs,
)
from app.models.trading import OrderType


class TestMCPTools:
    """Test MCP tools functionality."""

    def test_get_stock_quote_success(self):
        """Test getting stock quote successfully."""
        args = GetQuoteArgs(symbol="AAPL")
        result = get_stock_quote(args)

        data = json.loads(result)
        assert data["symbol"] == "AAPL"
        assert "price" in data
        assert "change" in data
        assert "volume" in data
        assert "last_updated" in data

    def test_get_stock_quote_invalid_symbol(self):
        """Test getting quote for invalid symbol."""
        args = GetQuoteArgs(symbol="INVALID")
        result = get_stock_quote(args)

        assert "Error getting quote" in result
        assert "not found" in result

    def test_create_buy_order_success(self):
        """Test creating buy order successfully."""
        args = CreateOrderArgs(
            symbol="AAPL", order_type=OrderType.BUY, quantity=10, price=150.0
        )
        result = create_buy_order(args)

        data = json.loads(result)
        assert data["symbol"] == "AAPL"
        assert data["order_type"] == "buy"
        assert data["quantity"] == 10
        assert data["price"] == 150.0
        assert data["status"] == "pending"
        assert "id" in data

    def test_create_sell_order_success(self):
        """Test creating sell order successfully."""
        args = CreateOrderArgs(
            symbol="GOOGL", order_type=OrderType.SELL, quantity=5, price=2800.0
        )
        result = create_sell_order(args)

        data = json.loads(result)
        assert data["symbol"] == "GOOGL"
        assert data["order_type"] == "sell"
        assert data["quantity"] == 5
        assert data["price"] == 2800.0
        assert data["status"] == "pending"
        assert "id" in data

    def test_get_all_orders(self):
        """Test getting all orders."""
        result = get_all_orders()

        data = json.loads(result)
        assert isinstance(data, list)
        # Orders from previous tests should be present
        assert len(data) >= 0

    def test_get_order_success(self):
        """Test getting specific order."""
        # First create an order
        create_args = CreateOrderArgs(
            symbol="MSFT", order_type=OrderType.BUY, quantity=20, price=420.0
        )
        create_result = create_buy_order(create_args)
        order_data = json.loads(create_result)
        order_id = order_data["id"]

        # Now get the order
        get_args = GetOrderArgs(order_id=order_id)
        result = get_order(get_args)

        data = json.loads(result)
        assert data["id"] == order_id
        assert data["symbol"] == "MSFT"
        assert data["quantity"] == 20

    def test_get_order_not_found(self):
        """Test getting non-existent order."""
        args = GetOrderArgs(order_id="invalid_id")
        result = get_order(args)

        assert "Error getting order" in result
        assert "not found" in result

    def test_cancel_order_success(self):
        """Test canceling order successfully."""
        # First create an order
        create_args = CreateOrderArgs(
            symbol="TSLA", order_type=OrderType.BUY, quantity=15, price=245.0
        )
        create_result = create_buy_order(create_args)
        order_data = json.loads(create_result)
        order_id = order_data["id"]

        # Now cancel the order
        cancel_args = CancelOrderArgs(order_id=order_id)
        result = cancel_order(cancel_args)

        data = json.loads(result)
        assert "message" in data
        assert "cancelled" in data["message"]

    def test_cancel_order_not_found(self):
        """Test canceling non-existent order."""
        args = CancelOrderArgs(order_id="invalid_id")
        result = cancel_order(args)

        assert "Error cancelling order" in result
        assert "not found" in result

    def test_get_portfolio(self):
        """Test getting portfolio."""
        result = get_portfolio()

        data = json.loads(result)
        assert "cash_balance" in data
        assert "total_value" in data
        assert "positions" in data
        assert "daily_pnl" in data
        assert "total_pnl" in data
        assert isinstance(data["positions"], list)

    def test_get_portfolio_summary(self):
        """Test getting portfolio summary."""
        result = get_portfolio_summary()

        data = json.loads(result)
        assert "total_value" in data
        assert "cash_balance" in data
        assert "invested_value" in data
        assert "daily_pnl" in data
        assert "daily_pnl_percent" in data
        assert "total_pnl" in data
        assert "total_pnl_percent" in data

    def test_get_all_positions(self):
        """Test getting all positions."""
        result = get_all_positions()

        data = json.loads(result)
        assert isinstance(data, list)
        if data:  # If there are positions
            position = data[0]
            assert "symbol" in position
            assert "quantity" in position
            assert "avg_price" in position
            assert "current_price" in position
            assert "unrealized_pnl" in position

    def test_get_position_success(self):
        """Test getting specific position."""
        args = GetPositionArgs(symbol="AAPL")
        result = get_position(args)

        data = json.loads(result)
        assert data["symbol"] == "AAPL"
        assert "quantity" in data
        assert "avg_price" in data
        assert "current_price" in data
        assert "unrealized_pnl" in data

    def test_get_position_not_found(self):
        """Test getting non-existent position."""
        args = GetPositionArgs(symbol="INVALID")
        result = get_position(args)

        assert "Error getting position" in result
        assert "not found" in result
