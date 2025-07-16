import pytest
from datetime import datetime

from app.services.trading_service import TradingService
from app.schemas.orders import OrderCreate, OrderType, OrderStatus
from app.core.exceptions import NotFoundError


class TestTradingService:
    """Test the trading service functionality."""

    def setup_method(self):
        """Setup fresh trading service for each test."""
        self.service = TradingService()

    def test_get_quote_success(self):
        """Test getting valid stock quote."""
        quote = self.service.get_quote("AAPL")

        assert quote.symbol == "AAPL"
        assert quote.price > 0
        assert isinstance(quote.change, float)
        assert isinstance(quote.change_percent, float)
        assert quote.volume > 0
        assert isinstance(quote.last_updated, datetime)

    def test_get_quote_invalid_symbol(self):
        """Test getting quote for invalid symbol."""
        with pytest.raises(NotFoundError):
            self.service.get_quote("INVALID")

    def test_get_quote_case_insensitive(self):
        """Test that symbol lookup is case insensitive."""
        quote_upper = self.service.get_quote("AAPL")
        quote_lower = self.service.get_quote("aapl")

        assert quote_upper.symbol == quote_lower.symbol
        assert quote_upper.price == quote_lower.price

    def test_create_order_success(self):
        """Test creating valid order."""
        order_data = OrderCreate(
            symbol="AAPL", order_type=OrderType.BUY, quantity=10, price=150.0
        )

        order = self.service.create_order(order_data)

        assert order.id is not None
        assert order.symbol == "AAPL"
        assert order.order_type == OrderType.BUY
        assert order.quantity == 10
        assert order.price == 150.0
        assert order.status == OrderStatus.PENDING
        assert order.created_at is not None
        assert order.filled_at is None

    def test_create_order_invalid_symbol(self):
        """Test creating order with invalid symbol."""
        order_data = OrderCreate(
            symbol="INVALID", order_type=OrderType.BUY, quantity=10, price=150.0
        )

        with pytest.raises(NotFoundError):
            self.service.create_order(order_data)

    def test_create_order_symbol_case_normalization(self):
        """Test that order symbol is normalized to uppercase."""
        order_data = OrderCreate(
            symbol="aapl", order_type=OrderType.BUY, quantity=10, price=150.0
        )

        order = self.service.create_order(order_data)
        assert order.symbol == "AAPL"

    def test_get_orders_empty(self):
        """Test getting orders when none exist."""
        orders = self.service.get_orders()
        assert orders == []

    def test_get_orders_with_data(self):
        """Test getting orders when some exist."""
        # Create a few orders
        order_data1 = OrderCreate(
            symbol="AAPL", order_type=OrderType.BUY, quantity=10, price=150.0
        )
        order_data2 = OrderCreate(
            symbol="GOOGL", order_type=OrderType.SELL, quantity=5, price=2800.0
        )

        order1 = self.service.create_order(order_data1)
        order2 = self.service.create_order(order_data2)

        orders = self.service.get_orders()
        assert len(orders) == 2
        assert order1 in orders
        assert order2 in orders

    def test_get_order_success(self):
        """Test getting specific order."""
        order_data = OrderCreate(
            symbol="AAPL", order_type=OrderType.BUY, quantity=10, price=150.0
        )
        created_order = self.service.create_order(order_data)

        retrieved_order = self.service.get_order(created_order.id)

        assert retrieved_order.id == created_order.id
        assert retrieved_order.symbol == created_order.symbol
        assert retrieved_order.order_type == created_order.order_type

    def test_get_order_not_found(self):
        """Test getting non-existent order."""
        with pytest.raises(NotFoundError):
            self.service.get_order("invalid_id")

    def test_cancel_order_success(self):
        """Test canceling order successfully."""
        order_data = OrderCreate(
            symbol="AAPL", order_type=OrderType.BUY, quantity=10, price=150.0
        )
        created_order = self.service.create_order(order_data)

        result = self.service.cancel_order(created_order.id)

        assert result["message"] == "Order cancelled successfully"

        # Verify order is actually cancelled
        updated_order = self.service.get_order(created_order.id)
        assert updated_order.status == OrderStatus.CANCELLED

    def test_cancel_order_not_found(self):
        """Test canceling non-existent order."""
        with pytest.raises(NotFoundError):
            self.service.cancel_order("invalid_id")

    def test_get_portfolio(self):
        """Test getting portfolio."""
        portfolio = self.service.get_portfolio()

        assert portfolio.cash_balance == 10000.0
        assert portfolio.total_value > 0
        assert isinstance(portfolio.positions, list)
        assert len(portfolio.positions) == 2  # Default mock positions
        assert isinstance(portfolio.daily_pnl, float)
        assert isinstance(portfolio.total_pnl, float)

    def test_get_portfolio_summary(self):
        """Test getting portfolio summary."""
        summary = self.service.get_portfolio_summary()

        assert summary.total_value > 0
        assert summary.cash_balance == 10000.0
        assert summary.invested_value > 0
        assert isinstance(summary.daily_pnl, float)
        assert isinstance(summary.daily_pnl_percent, float)
        assert isinstance(summary.total_pnl, float)
        assert isinstance(summary.total_pnl_percent, float)

    def test_get_positions(self):
        """Test getting all positions."""
        positions = self.service.get_positions()

        assert isinstance(positions, list)
        assert len(positions) == 2  # Default mock positions

        for position in positions:
            assert hasattr(position, "symbol")
            assert hasattr(position, "quantity")
            assert hasattr(position, "avg_price")
            assert hasattr(position, "current_price")
            assert hasattr(position, "unrealized_pnl")

    def test_get_position_success(self):
        """Test getting specific position."""
        position = self.service.get_position("AAPL")

        assert position.symbol == "AAPL"
        assert position.quantity == 10
        assert position.avg_price == 145.0
        assert position.current_price == 150.0
        assert position.unrealized_pnl == 50.0

    def test_get_position_case_insensitive(self):
        """Test that position lookup is case insensitive."""
        position_upper = self.service.get_position("AAPL")
        position_lower = self.service.get_position("aapl")

        assert position_upper.symbol == position_lower.symbol
        assert position_upper.quantity == position_lower.quantity

    def test_get_position_not_found(self):
        """Test getting non-existent position."""
        with pytest.raises(NotFoundError):
            self.service.get_position("INVALID")


# Enhanced Method Stubs
def test_get_enhanced_quote_stock():
    pytest.fail("Test not implemented")


def test_get_enhanced_quote_option():
    pytest.fail("Test not implemented")


def test_get_options_chain():
    pytest.fail("Test not implemented")


def test_calculate_greeks():
    pytest.fail("Test not implemented")


def test_analyze_portfolio_strategies():
    pytest.fail("Test not implemented")


def test_calculate_margin_requirement():
    pytest.fail("Test not implemented")


def test_validate_account_state():
    pytest.fail("Test not implemented")


def test_get_test_scenarios():
    pytest.fail("Test not implemented")


def test_set_test_date():
    pytest.fail("Test not implemented")


def test_get_available_symbols():
    pytest.fail("Test not implemented")


def test_get_sample_data_info():
    pytest.fail("Test not implemented")


def test_get_expiration_dates():
    pytest.fail("Test not implemented")


def test_create_multi_leg_order():
    pytest.fail("Test not implemented")
