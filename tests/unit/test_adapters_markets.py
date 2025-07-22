"""Tests for market adapters (PaperMarketAdapter and OrderImpact)."""

from datetime import datetime
from unittest.mock import patch

import pytest

from app.adapters.base import QuoteAdapter
from app.adapters.markets import (
    OrderImpact,
    PaperMarketAdapter,
)
from app.models.assets import Stock
from app.models.quotes import Quote
from app.schemas.orders import Order, OrderCondition, OrderStatus, OrderType
from app.services.estimators import MarketEstimator, MidpointEstimator


class TestOrderImpact:
    """Test OrderImpact functionality."""

    def test_order_impact_initialization(self):
        """Test OrderImpact initialization."""
        order = Order(
            symbol="AAPL",
            order_type=OrderType.BUY,
            condition=OrderCondition.MARKET,
            quantity=100,
        )

        impact = OrderImpact(order, 150.0)

        assert impact.order is order
        assert impact.current_price == 150.0
        assert impact.executed_price == 150.0
        assert impact.slippage == 0.0
        assert impact.commission == 0.0
        assert impact.total_cost == 0.0
        assert impact.impact_percentage == 0.0

    def test_calculate_impact_market_buy_order(self):
        """Test impact calculation for market buy order."""
        order = Order(
            symbol="AAPL",
            order_type=OrderType.BUY,
            condition=OrderCondition.MARKET,
            quantity=100,
        )

        impact = OrderImpact(order, 150.0)
        result = impact.calculate_impact(slippage_bps=10.0, commission_per_share=0.01)

        # Market buy should have positive slippage (higher price)
        assert impact.executed_price > 150.0
        assert impact.executed_price == 150.0 * 1.001  # 10bps = 0.1%
        assert impact.slippage > 0.0
        assert impact.commission == 1.0  # 100 shares * $0.01
        assert impact.total_cost > 0.0
        assert impact.impact_percentage > 0.0

        # Verify returned dictionary
        assert result["executed_price"] == impact.executed_price
        assert result["slippage"] == impact.slippage
        assert result["commission"] == impact.commission
        assert result["total_cost"] == impact.total_cost
        assert result["impact_percentage"] == impact.impact_percentage

    def test_calculate_impact_market_sell_order(self):
        """Test impact calculation for market sell order."""
        order = Order(
            symbol="AAPL",
            order_type=OrderType.SELL,
            condition=OrderCondition.MARKET,
            quantity=100,
        )

        impact = OrderImpact(order, 150.0)
        impact.calculate_impact(slippage_bps=10.0, commission_per_share=0.01)

        # Market sell should have negative slippage (lower price)
        assert impact.executed_price < 150.0
        assert impact.executed_price == 150.0 / 1.001  # 10bps slippage
        assert impact.slippage > 0.0  # Absolute value
        assert impact.commission == 1.0
        assert impact.total_cost > 0.0  # Net proceeds after commission
        assert impact.impact_percentage > 0.0

    def test_calculate_impact_limit_order(self):
        """Test impact calculation for limit order."""
        order = Order(
            symbol="AAPL",
            order_type=OrderType.BUY,
            condition=OrderCondition.LIMIT,
            quantity=100,
            price=149.50,  # Limit price
        )

        impact = OrderImpact(order, 150.0)
        impact.calculate_impact(commission_per_share=0.01)

        # Limit order should execute at limit price
        assert impact.executed_price == 149.50
        assert impact.slippage == 50.0  # |149.50 - 150.0| * 100
        assert impact.commission == 1.0
        assert impact.total_cost == 14951.0  # (149.50 * 100) + 1.0

    def test_calculate_impact_limit_order_no_price(self):
        """Test impact calculation for limit order with no price set."""
        order = Order(
            symbol="AAPL",
            order_type=OrderType.BUY,
            condition=OrderCondition.LIMIT,
            quantity=100,
            price=None,  # No limit price set
        )

        impact = OrderImpact(order, 150.0)
        impact.calculate_impact()

        # Should default to current price
        assert impact.executed_price == 150.0

    def test_calculate_impact_option_orders(self):
        """Test impact calculation for option orders."""
        # Test BTO (Buy to Open)
        bto_order = Order(
            symbol="AAPL170324C00150000",
            order_type=OrderType.BTO,
            condition=OrderCondition.MARKET,
            quantity=10,
        )

        impact = OrderImpact(bto_order, 5.50)
        impact.calculate_impact(slippage_bps=20.0, commission_per_share=0.02)

        assert impact.executed_price > 5.50  # Buy order has positive slippage
        assert impact.commission == 0.20  # 10 contracts * $0.02

        # Test BTC (Buy to Close)
        btc_order = Order(
            symbol="AAPL170324C00150000",
            order_type=OrderType.BTC,
            condition=OrderCondition.MARKET,
            quantity=10,
        )

        impact2 = OrderImpact(btc_order, 5.50)
        impact2.calculate_impact(slippage_bps=20.0, commission_per_share=0.02)

        assert impact2.executed_price > 5.50  # BTC is also a buy

    def test_calculate_impact_custom_parameters(self):
        """Test impact calculation with custom slippage and commission."""
        order = Order(
            symbol="AAPL",
            order_type=OrderType.BUY,
            condition=OrderCondition.MARKET,
            quantity=1000,  # Large order
        )

        impact = OrderImpact(order, 100.0)
        impact.calculate_impact(
            slippage_bps=50.0,  # Higher slippage
            commission_per_share=0.005,  # Lower commission
        )

        expected_executed_price = 100.0 * 1.005  # 50bps = 0.5%
        assert impact.executed_price == expected_executed_price
        assert impact.commission == 5.0  # 1000 * $0.005

        # Impact percentage should be calculated correctly
        order_value = 100.0 * 1000  # 100,000
        expected_impact_pct = (
            (impact.slippage + impact.commission) / order_value
        ) * 100
        assert abs(impact.impact_percentage - expected_impact_pct) < 0.001

    def test_calculate_impact_zero_quantity(self):
        """Test impact calculation with zero quantity."""
        order = Order(
            symbol="AAPL",
            order_type=OrderType.BUY,
            condition=OrderCondition.MARKET,
            quantity=0,
        )

        impact = OrderImpact(order, 150.0)
        impact.calculate_impact()

        assert impact.slippage == 0.0
        assert impact.commission == 0.0
        assert impact.total_cost == 0.0
        assert impact.impact_percentage == 0.0  # Avoid division by zero


class MockQuoteAdapter(QuoteAdapter):
    """Mock quote adapter for testing."""

    def __init__(self):
        self.quotes = {}
        self.market_open = True

    async def get_quote(self, asset):
        return self.quotes.get(asset.symbol)

    async def get_quotes(self, assets):
        results = {}
        for asset in assets:
            quote = self.quotes.get(asset.symbol)
            if quote:
                results[asset] = quote
        return results

    async def get_chain(self, underlying, expiration_date=None):
        return []

    async def get_options_chain(self, underlying, expiration_date=None):
        return None

    async def is_market_open(self):
        return self.market_open

    async def get_market_hours(self):
        return {"open": "09:30", "close": "16:00"}

    def get_sample_data_info(self):
        return {"test": "data"}

    def get_expiration_dates(self, underlying):
        return []

    def get_test_scenarios(self):
        return {}

    def set_date(self, date):
        pass

    def get_available_symbols(self):
        return []


class TestPaperMarketAdapter:
    """Test PaperMarketAdapter functionality."""

    @pytest.fixture
    def quote_adapter(self):
        """Create mock quote adapter."""
        return MockQuoteAdapter()

    @pytest.fixture
    def adapter(self, quote_adapter):
        """Create paper market adapter."""
        return PaperMarketAdapter(quote_adapter)

    def test_adapter_initialization(self, quote_adapter):
        """Test adapter initialization."""
        adapter = PaperMarketAdapter(quote_adapter)

        assert adapter.quote_adapter is quote_adapter
        assert len(adapter.pending_orders) == 0
        assert len(adapter.filled_orders) == 0
        assert isinstance(adapter.midpoint_estimator, MidpointEstimator)
        assert isinstance(adapter.market_estimator, MarketEstimator)

    @pytest.mark.asyncio
    async def test_submit_order_generates_id(self, adapter):
        """Test that submit_order generates an ID if none exists."""
        order = Order(
            symbol="AAPL",
            order_type=OrderType.BUY,
            condition=OrderCondition.LIMIT,
            quantity=100,
            price=150.0,
        )

        submitted = await adapter.submit_order(order)

        assert submitted.id is not None
        assert len(submitted.id) == 8  # Short UUID
        assert submitted.status == OrderStatus.PENDING
        assert isinstance(submitted.created_at, datetime)
        assert len(adapter.pending_orders) == 1
        assert adapter.pending_orders[0] is submitted

    @pytest.mark.asyncio
    async def test_submit_order_preserves_existing_id(self, adapter):
        """Test that submit_order preserves existing order ID."""
        order = Order(
            id="existing-id",
            symbol="AAPL",
            order_type=OrderType.BUY,
            condition=OrderCondition.LIMIT,
            quantity=100,
            price=150.0,
        )

        submitted = await adapter.submit_order(order)

        assert submitted.id == "existing-id"
        assert submitted.status == OrderStatus.PENDING

    @pytest.mark.asyncio
    async def test_submit_market_order_immediate_fill_attempt(
        self, adapter, quote_adapter
    ):
        """Test that market orders attempt immediate fill."""
        # Setup quote for AAPL
        stock = Stock(symbol="AAPL", name="Apple Inc.")
        quote = Quote(
            asset=stock,
            quote_date=datetime.now(),
            price=150.0,
            bid=149.95,
            ask=150.05,
            bid_size=100,
            ask_size=100,
            volume=1000000,
        )
        quote_adapter.quotes["AAPL"] = quote

        # Mock asset factory
        with patch("app.models.assets.asset_factory", return_value=stock):
            order = Order(
                symbol="AAPL",
                order_type=OrderType.BUY,
                condition=OrderCondition.MARKET,
                quantity=100,
            )

            submitted = await adapter.submit_order(order)

        # Market order should be filled immediately
        assert submitted.status == OrderStatus.FILLED
        assert submitted.filled_at is not None
        assert len(adapter.pending_orders) == 0  # No longer pending
        assert len(adapter.filled_orders) == 1

    @pytest.mark.asyncio
    async def test_submit_limit_order_remains_pending(self, adapter, quote_adapter):
        """Test that limit orders remain pending until conditions are met."""
        order = Order(
            symbol="AAPL",
            order_type=OrderType.BUY,
            condition=OrderCondition.LIMIT,
            quantity=100,
            price=149.0,  # Below market
        )

        submitted = await adapter.submit_order(order)

        # Limit order should remain pending
        assert submitted.status == OrderStatus.PENDING
        assert submitted.filled_at is None
        assert len(adapter.pending_orders) == 1
        assert len(adapter.filled_orders) == 0

    def test_cancel_order_success(self, adapter):
        """Test successful order cancellation."""
        # Add a pending order
        order = Order(
            id="cancel-me",
            symbol="AAPL",
            order_type=OrderType.BUY,
            condition=OrderCondition.LIMIT,
            quantity=100,
            price=149.0,
            status=OrderStatus.PENDING,
        )
        adapter.pending_orders.append(order)

        result = adapter.cancel_order("cancel-me")

        assert result is True
        assert order.status == OrderStatus.CANCELLED
        assert len(adapter.pending_orders) == 0

    def test_cancel_order_not_found(self, adapter):
        """Test cancellation of non-existent order."""
        result = adapter.cancel_order("nonexistent-id")
        assert result is False

    def test_cancel_order_multiple_orders(self, adapter):
        """Test cancelling specific order when multiple exist."""
        # Add multiple pending orders
        orders = [
            Order(
                id="order1",
                symbol="AAPL",
                order_type=OrderType.BUY,
                condition=OrderCondition.LIMIT,
                quantity=100,
                price=149.0,
                status=OrderStatus.PENDING,
            ),
            Order(
                id="order2",
                symbol="GOOGL",
                order_type=OrderType.SELL,
                condition=OrderCondition.LIMIT,
                quantity=50,
                price=2501.0,
                status=OrderStatus.PENDING,
            ),
            Order(
                id="order3",
                symbol="MSFT",
                order_type=OrderType.BUY,
                condition=OrderCondition.LIMIT,
                quantity=75,
                price=299.0,
                status=OrderStatus.PENDING,
            ),
        ]
        adapter.pending_orders.extend(orders)

        # Cancel middle order
        result = adapter.cancel_order("order2")

        assert result is True
        assert orders[1].status == OrderStatus.CANCELLED
        assert len(adapter.pending_orders) == 2
        assert "order1" in [o.id for o in adapter.pending_orders]
        assert "order3" in [o.id for o in adapter.pending_orders]

    def test_get_pending_orders(self, adapter):
        """Test getting pending orders."""
        # Add some orders
        orders = [
            Order(
                id="order1",
                symbol="AAPL",
                order_type=OrderType.BUY,
                condition=OrderCondition.LIMIT,
                quantity=100,
                price=149.0,
                status=OrderStatus.PENDING,
            ),
            Order(
                id="order2",
                symbol="GOOGL",
                order_type=OrderType.SELL,
                condition=OrderCondition.LIMIT,
                quantity=50,
                price=2501.0,
                status=OrderStatus.PENDING,
            ),
        ]
        adapter.pending_orders.extend(orders)

        pending = adapter.get_pending_orders()

        assert len(pending) == 2
        assert pending[0].id == "order1"
        assert pending[1].id == "order2"

        # Verify it returns a copy
        pending.clear()
        assert len(adapter.get_pending_orders()) == 2

    def test_get_pending_orders_with_account_filter(self, adapter):
        """Test getting pending orders with account filter (placeholder)."""
        # Add some orders
        order = Order(
            id="order1",
            symbol="AAPL",
            order_type=OrderType.BUY,
            condition=OrderCondition.LIMIT,
            quantity=100,
            price=149.0,
            status=OrderStatus.PENDING,
        )
        adapter.pending_orders.append(order)

        # Note: Current implementation ignores account_id filter
        pending = adapter.get_pending_orders(account_id="test-account")

        assert len(pending) == 1
        assert pending[0].id == "order1"

    @pytest.mark.asyncio
    async def test_simulate_order_success(self, adapter, quote_adapter):
        """Test successful order simulation."""
        # Setup quote
        stock = Stock(symbol="AAPL", name="Apple Inc.")
        quote = Quote(
            asset=stock,
            quote_date=datetime.now(),
            price=150.0,
            bid=149.95,
            ask=150.05,
            bid_size=100,
            ask_size=100,
            volume=1000000,
        )
        quote_adapter.quotes["AAPL"] = quote

        order = Order(
            symbol="AAPL",
            order_type=OrderType.BUY,
            condition=OrderCondition.MARKET,
            quantity=100,
        )

        with patch("app.models.assets.asset_factory", return_value=stock):
            result = await adapter.simulate_order(order)

        assert result["success"] is True
        assert result["would_fill"] is True
        assert "current_price" in result
        assert "impact" in result
        assert "quote" in result
        assert result["quote"] is quote

    @pytest.mark.asyncio
    async def test_simulate_order_invalid_symbol(self, adapter):
        """Test order simulation with invalid symbol."""
        order = Order(
            symbol="INVALID",
            order_type=OrderType.BUY,
            condition=OrderCondition.MARKET,
            quantity=100,
        )

        with patch("app.models.assets.asset_factory", return_value=None):
            result = await adapter.simulate_order(order)

        assert result["success"] is False
        assert result["reason"] == "Invalid symbol"
        assert result["impact"] is None

    @pytest.mark.asyncio
    async def test_simulate_order_no_quote(self, adapter, quote_adapter):
        """Test order simulation with no quote available."""
        stock = Stock(symbol="AAPL", name="Apple Inc.")
        # No quote in quote_adapter.quotes

        order = Order(
            symbol="AAPL",
            order_type=OrderType.BUY,
            condition=OrderCondition.MARKET,
            quantity=100,
        )

        with patch("app.models.assets.asset_factory", return_value=stock):
            result = await adapter.simulate_order(order)

        assert result["success"] is False
        assert result["reason"] == "No quote available"
        assert result["impact"] is None

    @pytest.mark.asyncio
    async def test_simulate_limit_order_would_not_fill(self, adapter, quote_adapter):
        """Test simulating limit order that wouldn't fill."""
        # Setup quote
        stock = Stock(symbol="AAPL", name="Apple Inc.")
        quote = Quote(
            asset=stock,
            quote_date=datetime.now(),
            price=150.0,
            bid=149.95,
            ask=150.05,
            bid_size=100,
            ask_size=100,
            volume=1000000,
        )
        quote_adapter.quotes["AAPL"] = quote

        # Limit buy order above ask price (would fill)
        buy_order = Order(
            symbol="AAPL",
            order_type=OrderType.BUY,
            condition=OrderCondition.LIMIT,
            quantity=100,
            price=150.10,  # Above ask
        )

        with patch("app.models.assets.asset_factory", return_value=stock):
            result = await adapter.simulate_order(buy_order)

        assert result["success"] is True
        assert result["would_fill"] is True

        # Limit buy order below ask price (wouldn't fill)
        buy_order_low = Order(
            symbol="AAPL",
            order_type=OrderType.BUY,
            condition=OrderCondition.LIMIT,
            quantity=100,
            price=150.00,  # Below ask
        )

        with patch("app.models.assets.asset_factory", return_value=stock):
            result = await adapter.simulate_order(buy_order_low)

        assert result["success"] is True
        assert result["would_fill"] is False

    @pytest.mark.asyncio
    async def test_process_pending_orders(self, adapter, quote_adapter):
        """Test processing pending orders."""
        # Setup quotes
        stock = Stock(symbol="AAPL", name="Apple Inc.")
        quote = Quote(
            asset=stock,
            quote_date=datetime.now(),
            price=150.0,
            bid=149.95,
            ask=150.05,
            bid_size=100,
            ask_size=100,
            volume=1000000,
        )
        quote_adapter.quotes["AAPL"] = quote

        # Add mixed pending orders
        market_order = Order(
            id="market1",
            symbol="AAPL",
            order_type=OrderType.BUY,
            condition=OrderCondition.MARKET,
            quantity=100,
            status=OrderStatus.PENDING,
        )

        limit_order_fill = Order(
            id="limit1",
            symbol="AAPL",
            order_type=OrderType.BUY,
            condition=OrderCondition.LIMIT,
            quantity=100,
            price=150.10,  # Above ask, should fill
            status=OrderStatus.PENDING,
        )

        limit_order_no_fill = Order(
            id="limit2",
            symbol="AAPL",
            order_type=OrderType.BUY,
            condition=OrderCondition.LIMIT,
            quantity=100,
            price=149.00,  # Below ask, won't fill
            status=OrderStatus.PENDING,
        )

        adapter.pending_orders.extend(
            [market_order, limit_order_fill, limit_order_no_fill]
        )

        with patch("app.models.assets.asset_factory", return_value=stock):
            filled = await adapter.process_pending_orders()

        # Should have filled 2 orders
        assert len(filled) == 2
        filled_ids = [o.id for o in filled]
        assert "market1" in filled_ids
        assert "limit1" in filled_ids

        # One order should remain pending
        assert len(adapter.pending_orders) == 1
        assert adapter.pending_orders[0].id == "limit2"

        # Filled orders should have correct status
        for order in filled:
            assert order.status == OrderStatus.FILLED
            assert order.filled_at is not None

    @pytest.mark.asyncio
    async def test_try_fill_order_market_buy(self, adapter, quote_adapter):
        """Test filling market buy order."""
        stock = Stock(symbol="AAPL", name="Apple Inc.")
        quote = Quote(
            asset=stock,
            quote_date=datetime.now(),
            price=150.0,
            bid=149.95,
            ask=150.05,
            bid_size=100,
            ask_size=100,
            volume=1000000,
        )
        quote_adapter.quotes["AAPL"] = quote

        order = Order(
            symbol="AAPL",
            order_type=OrderType.BUY,
            condition=OrderCondition.MARKET,
            quantity=100,
            status=OrderStatus.PENDING,
        )

        with patch("app.models.assets.asset_factory", return_value=stock):
            filled = await adapter._try_fill_order(order)

        assert filled is True
        assert order.status == OrderStatus.FILLED
        assert order.filled_at is not None
        assert len(adapter.filled_orders) == 1

    @pytest.mark.asyncio
    async def test_try_fill_order_market_sell(self, adapter, quote_adapter):
        """Test filling market sell order."""
        stock = Stock(symbol="AAPL", name="Apple Inc.")
        quote = Quote(
            asset=stock,
            quote_date=datetime.now(),
            price=150.0,
            bid=149.95,
            ask=150.05,
            bid_size=100,
            ask_size=100,
            volume=1000000,
        )
        quote_adapter.quotes["AAPL"] = quote

        order = Order(
            symbol="AAPL",
            order_type=OrderType.SELL,
            condition=OrderCondition.MARKET,
            quantity=100,
            status=OrderStatus.PENDING,
        )

        with patch("app.models.assets.asset_factory", return_value=stock):
            filled = await adapter._try_fill_order(order)

        assert filled is True
        assert order.status == OrderStatus.FILLED

    @pytest.mark.asyncio
    async def test_try_fill_order_limit_conditions(self, adapter, quote_adapter):
        """Test limit order fill conditions."""
        stock = Stock(symbol="AAPL", name="Apple Inc.")
        quote = Quote(
            asset=stock,
            quote_date=datetime.now(),
            price=150.0,
            bid=149.95,
            ask=150.05,
            bid_size=100,
            ask_size=100,
            volume=1000000,
        )
        quote_adapter.quotes["AAPL"] = quote

        # Test buy limit at/above ask (should fill)
        buy_order_fill = Order(
            symbol="AAPL",
            order_type=OrderType.BUY,
            condition=OrderCondition.LIMIT,
            quantity=100,
            price=150.05,  # At ask
            status=OrderStatus.PENDING,
        )

        with patch("app.models.assets.asset_factory", return_value=stock):
            filled = await adapter._try_fill_order(buy_order_fill)
        assert filled is True

        # Test buy limit below ask (shouldn't fill)
        buy_order_no_fill = Order(
            symbol="AAPL",
            order_type=OrderType.BUY,
            condition=OrderCondition.LIMIT,
            quantity=100,
            price=150.00,  # Below ask
            status=OrderStatus.PENDING,
        )

        with patch("app.models.assets.asset_factory", return_value=stock):
            filled = await adapter._try_fill_order(buy_order_no_fill)
        assert filled is False

        # Test sell limit at/below bid (should fill)
        sell_order_fill = Order(
            symbol="AAPL",
            order_type=OrderType.SELL,
            condition=OrderCondition.LIMIT,
            quantity=100,
            price=149.95,  # At bid
            status=OrderStatus.PENDING,
        )

        with patch("app.models.assets.asset_factory", return_value=stock):
            filled = await adapter._try_fill_order(sell_order_fill)
        assert filled is True

        # Test sell limit above bid (shouldn't fill)
        sell_order_no_fill = Order(
            symbol="AAPL",
            order_type=OrderType.SELL,
            condition=OrderCondition.LIMIT,
            quantity=100,
            price=150.00,  # Above bid
            status=OrderStatus.PENDING,
        )

        with patch("app.models.assets.asset_factory", return_value=stock):
            filled = await adapter._try_fill_order(sell_order_no_fill)
        assert filled is False

    @pytest.mark.asyncio
    async def test_try_fill_order_stop_conditions(self, adapter, quote_adapter):
        """Test stop order fill conditions."""
        stock = Stock(symbol="AAPL", name="Apple Inc.")
        quote = Quote(
            asset=stock,
            quote_date=datetime.now(),
            price=150.0,
            bid=149.95,
            ask=150.05,
            bid_size=100,
            ask_size=100,
            volume=1000000,
        )
        quote_adapter.quotes["AAPL"] = quote

        # Test buy stop above current price (should trigger)
        buy_stop_trigger = Order(
            symbol="AAPL",
            order_type=OrderType.BUY,
            condition=OrderCondition.STOP,
            quantity=100,
            price=149.0,  # Below current price
            status=OrderStatus.PENDING,
        )

        with patch("app.models.assets.asset_factory", return_value=stock):
            filled = await adapter._try_fill_order(buy_stop_trigger)
        assert filled is True

        # Test sell stop below current price (should trigger)
        sell_stop_trigger = Order(
            symbol="AAPL",
            order_type=OrderType.SELL,
            condition=OrderCondition.STOP,
            quantity=100,
            price=151.0,  # Above current price
            status=OrderStatus.PENDING,
        )

        with patch("app.models.assets.asset_factory", return_value=stock):
            filled = await adapter._try_fill_order(sell_stop_trigger)
        assert filled is True

    @pytest.mark.asyncio
    async def test_try_fill_order_no_asset(self, adapter):
        """Test trying to fill order with invalid asset."""
        order = Order(
            symbol="INVALID",
            order_type=OrderType.BUY,
            condition=OrderCondition.MARKET,
            quantity=100,
            status=OrderStatus.PENDING,
        )

        with patch("app.models.assets.asset_factory", return_value=None):
            filled = await adapter._try_fill_order(order)

        assert filled is False
        assert order.status == OrderStatus.PENDING  # Should remain unchanged

    @pytest.mark.asyncio
    async def test_try_fill_order_no_quote(self, adapter, quote_adapter):
        """Test trying to fill order with no quote available."""
        stock = Stock(symbol="AAPL", name="Apple Inc.")
        # No quote in quote_adapter

        order = Order(
            symbol="AAPL",
            order_type=OrderType.BUY,
            condition=OrderCondition.MARKET,
            quantity=100,
            status=OrderStatus.PENDING,
        )

        with patch("app.models.assets.asset_factory", return_value=stock):
            filled = await adapter._try_fill_order(order)

        assert filled is False
        assert order.status == OrderStatus.PENDING

    @pytest.mark.asyncio
    async def test_try_fill_order_zero_price(self, adapter, quote_adapter):
        """Test trying to fill order when calculated fill price is zero."""
        stock = Stock(symbol="AAPL", name="Apple Inc.")
        quote = Quote(
            asset=stock,
            quote_date=datetime.now(),
            price=0.0,  # Zero price
            bid=0.0,
            ask=0.0,
            bid_size=100,
            ask_size=100,
            volume=1000000,
        )
        quote_adapter.quotes["AAPL"] = quote

        order = Order(
            symbol="AAPL",
            order_type=OrderType.BUY,
            condition=OrderCondition.MARKET,
            quantity=100,
            status=OrderStatus.PENDING,
        )

        with patch("app.models.assets.asset_factory", return_value=stock):
            filled = await adapter._try_fill_order(order)

        assert filled is False  # Zero price shouldn't fill
        assert order.status == OrderStatus.PENDING

    def test_order_processing_integration(self, adapter, quote_adapter):
        """Test complete order processing workflow."""
        # This test demonstrates a complete workflow
        stock = Stock(symbol="AAPL", name="Apple Inc.")
        quote = Quote(
            asset=stock,
            quote_date=datetime.now(),
            price=150.0,
            bid=149.95,
            ask=150.05,
            bid_size=100,
            ask_size=100,
            volume=1000000,
        )
        quote_adapter.quotes["AAPL"] = quote

        # Simulate a trading session
        with patch("app.models.assets.asset_factory", return_value=stock):
            # 1. Submit various orders
            market_buy = Order(
                symbol="AAPL",
                order_type=OrderType.BUY,
                condition=OrderCondition.MARKET,
                quantity=100,
            )
            limit_sell = Order(
                symbol="AAPL",
                order_type=OrderType.SELL,
                condition=OrderCondition.LIMIT,
                quantity=50,
                price=149.90,
            )
            stop_buy = Order(
                symbol="AAPL",
                order_type=OrderType.BUY,
                condition=OrderCondition.STOP,
                quantity=75,
                price=149.00,
            )

            # Submit orders asynchronously
            import asyncio

            async def submit_orders():
                await adapter.submit_order(market_buy)
                await adapter.submit_order(limit_sell)
                await adapter.submit_order(stop_buy)

                # Check states
                assert (
                    market_buy.status == OrderStatus.FILLED
                )  # Market order filled immediately
                assert (
                    limit_sell.status == OrderStatus.PENDING
                )  # Limit sell below bid, pending
                assert stop_buy.status == OrderStatus.FILLED  # Stop triggered

                # Process any remaining pending orders
                filled = await adapter.process_pending_orders()

                return filled

            asyncio.run(submit_orders())

            # Verify final state
            assert (
                len(adapter.filled_orders) >= 2
            )  # At least market and stop orders filled
            assert all(order.filled_at is not None for order in adapter.filled_orders)
            assert all(
                order.status == OrderStatus.FILLED for order in adapter.filled_orders
            )
