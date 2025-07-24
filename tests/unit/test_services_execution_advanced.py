"""
Advanced test coverage for OrderExecution service.

This module provides comprehensive testing of the order execution service,
focusing on order execution workflows, state management, execution engines,
order lifecycle management, and execution optimization patterns.
"""

import asyncio
from datetime import datetime
from unittest.mock import patch

import pytest

from app.models.quotes import Quote
from app.schemas.orders import (
    MultiLegOrder,
    OrderCreate,
    OrderLeg,
    OrderStatus,
    OrderType,
)
from app.schemas.positions import Portfolio, Position
from app.services.estimators import SlippageEstimator
from app.services.market_impact import MarketImpactCalculator
from app.services.order_execution import OrderExecutionResult, OrderFillSimulator
from app.services.order_execution_engine import OrderExecutionEngine
from app.services.order_lifecycle import OrderStateMachine
from app.services.order_queue import (
    OrderQueue as ExecutionQueue,
)


class MockQuoteService:
    """Mock quote service for testing."""

    def __init__(self):
        self._quotes = {}

    def set_quote(self, symbol: str, quote: Quote):
        self._quotes[symbol] = quote

    async def get_quote(self, symbol: str) -> Quote:
        if symbol not in self._quotes:
            # Default quote for unknown symbols
            return Quote(
                symbol=symbol,
                current_price=100.0,
                bid=99.5,
                ask=100.5,
                high=102.0,
                low=98.0,
                volume=1000000,
                market_cap=1000000000.0,
            )
        return self._quotes[symbol]


@pytest.fixture
def mock_quote_service():
    """Create mock quote service for testing."""
    service = MockQuoteService()

    # Set up standard quotes
    service.set_quote(
        "AAPL",
        Quote(
            symbol="AAPL",
            current_price=155.0,
            bid=154.5,
            ask=155.5,
            high=158.0,
            low=152.0,
            volume=1500000,
            market_cap=2500000000.0,
        ),
    )

    service.set_quote(
        "GOOGL",
        Quote(
            symbol="GOOGL",
            current_price=2600.0,
            bid=2595.0,
            ask=2605.0,
            high=2650.0,
            low=2580.0,
            volume=800000,
            market_cap=1700000000.0,
        ),
    )

    return service


@pytest.fixture
def order_execution_engine(mock_quote_service):
    """Create OrderExecutionEngine for testing."""
    engine = OrderExecutionEngine(quote_service=mock_quote_service)
    return engine


@pytest.fixture
def sample_portfolio():
    """Create sample portfolio for testing."""
    positions = [
        Position(
            symbol="AAPL",
            quantity=50,
            average_cost=150.0,
            current_price=155.0,
            market_value=7750.0,
            unrealized_pnl=250.0,
            unrealized_pnl_percent=3.33,
        )
    ]

    return Portfolio(
        cash_balance=50000.0,
        total_value=57750.0,
        positions=positions,
        unrealized_pnl=250.0,
        unrealized_pnl_percent=0.43,
    )


class TestOrderExecutionEngine:
    """Test OrderExecutionEngine functionality."""

    @pytest.mark.asyncio
    async def test_execute_market_buy_order(
        self, order_execution_engine, sample_portfolio
    ):
        """Test execution of market buy order."""
        order = OrderCreate(
            symbol="AAPL", quantity=100, order_type=OrderType.MARKET, side="buy"
        )

        result = await order_execution_engine.execute_order(order, sample_portfolio)

        assert isinstance(result, OrderExecutionResult)
        assert result.success is True
        assert result.order_id is not None
        assert result.cash_change < 0  # Cash should decrease for buy
        assert result.executed_quantity == 100
        assert result.executed_price > 0
        assert len(result.positions_created) == 0  # Should modify existing position
        assert len(result.positions_modified) == 1

    @pytest.mark.asyncio
    async def test_execute_market_sell_order(
        self, order_execution_engine, sample_portfolio
    ):
        """Test execution of market sell order."""
        order = OrderCreate(
            symbol="AAPL",
            quantity=25,  # Partial sell
            order_type=OrderType.MARKET,
            side="sell",
        )

        result = await order_execution_engine.execute_order(order, sample_portfolio)

        assert result.success is True
        assert result.cash_change > 0  # Cash should increase for sell
        assert result.executed_quantity == 25
        assert len(result.positions_modified) == 1

        # Position should be reduced
        modified_position = result.positions_modified[0]
        assert modified_position.quantity == 25  # 50 - 25 = 25

    @pytest.mark.asyncio
    async def test_execute_limit_order(self, order_execution_engine, sample_portfolio):
        """Test execution of limit order."""
        order = OrderCreate(
            symbol="AAPL",
            quantity=100,
            order_type=OrderType.LIMIT,
            side="buy",
            limit_price=154.0,  # Below current ask
        )

        result = await order_execution_engine.execute_order(order, sample_portfolio)

        assert result.success is True
        assert result.executed_price <= order.limit_price
        assert result.execution_strategy == "limit_order"

    @pytest.mark.asyncio
    async def test_execute_stop_order(self, order_execution_engine, sample_portfolio):
        """Test execution of stop order."""
        order = OrderCreate(
            symbol="AAPL",
            quantity=25,
            order_type=OrderType.STOP,
            side="sell",
            stop_price=150.0,  # Below current price, should trigger
        )

        result = await order_execution_engine.execute_order(order, sample_portfolio)

        assert result.success is True
        assert result.execution_strategy == "stop_order"
        assert result.executed_price <= order.stop_price

    @pytest.mark.asyncio
    async def test_insufficient_shares_error(
        self, order_execution_engine, sample_portfolio
    ):
        """Test execution failure due to insufficient shares."""
        order = OrderCreate(
            symbol="AAPL",
            quantity=100,  # Portfolio only has 50 shares
            order_type=OrderType.MARKET,
            side="sell",
        )

        result = await order_execution_engine.execute_order(order, sample_portfolio)

        assert result.success is False
        assert "insufficient shares" in result.message.lower()
        assert result.executed_quantity == 0

    @pytest.mark.asyncio
    async def test_insufficient_cash_error(
        self, order_execution_engine, sample_portfolio
    ):
        """Test execution failure due to insufficient cash."""
        order = OrderCreate(
            symbol="GOOGL",
            quantity=100,  # Would cost ~$260k, portfolio has $50k cash
            order_type=OrderType.MARKET,
            side="buy",
        )

        result = await order_execution_engine.execute_order(order, sample_portfolio)

        assert result.success is False
        assert "insufficient funds" in result.message.lower()
        assert result.cash_change == 0

    @pytest.mark.asyncio
    async def test_new_position_creation(
        self, order_execution_engine, sample_portfolio
    ):
        """Test creation of new position from order execution."""
        order = OrderCreate(
            symbol="MSFT",  # New symbol not in portfolio
            quantity=50,
            order_type=OrderType.MARKET,
            side="buy",
        )

        result = await order_execution_engine.execute_order(order, sample_portfolio)

        assert result.success is True
        assert len(result.positions_created) == 1
        assert len(result.positions_modified) == 0

        new_position = result.positions_created[0]
        assert new_position.symbol == "MSFT"
        assert new_position.quantity == 50


class TestExecutionStrategies:
    """Test different execution strategies."""

    @pytest.mark.asyncio
    async def test_twap_execution_strategy(
        self, order_execution_engine, sample_portfolio
    ):
        """Test Time Weighted Average Price execution strategy."""
        large_order = OrderCreate(
            symbol="AAPL",
            quantity=1000,  # Large order
            order_type=OrderType.MARKET,
            side="buy",
            execution_strategy="TWAP",
            time_horizon_minutes=30,
        )

        with patch.object(
            order_execution_engine, "_execute_twap_strategy"
        ) as mock_twap:
            mock_twap.return_value = OrderExecutionResult(
                success=True,
                message="TWAP execution completed",
                executed_quantity=1000,
                executed_price=155.25,  # Average price
                cash_change=-155250.0,
                execution_strategy="TWAP",
                execution_details={
                    "child_orders": 10,
                    "execution_time_minutes": 30,
                    "avg_price": 155.25,
                    "price_improvement": 0.15,
                },
            )

            result = await order_execution_engine.execute_order(
                large_order, sample_portfolio
            )

            assert result.success is True
            assert result.execution_strategy == "TWAP"
            assert result.execution_details["child_orders"] == 10
            mock_twap.assert_called_once()

    @pytest.mark.asyncio
    async def test_vwap_execution_strategy(
        self, order_execution_engine, sample_portfolio
    ):
        """Test Volume Weighted Average Price execution strategy."""
        large_order = OrderCreate(
            symbol="AAPL",
            quantity=2000,
            order_type=OrderType.MARKET,
            side="buy",
            execution_strategy="VWAP",
        )

        with patch.object(
            order_execution_engine, "_execute_vwap_strategy"
        ) as mock_vwap:
            mock_vwap.return_value = OrderExecutionResult(
                success=True,
                message="VWAP execution completed",
                executed_quantity=2000,
                executed_price=154.85,
                cash_change=-309700.0,
                execution_strategy="VWAP",
                execution_details={
                    "volume_participation_rate": 0.20,
                    "execution_buckets": 15,
                    "vwap_benchmark": 154.90,
                    "performance_vs_vwap": -0.05,  # 5 cents better
                },
            )

            result = await order_execution_engine.execute_order(
                large_order, sample_portfolio
            )

            assert result.success is True
            assert result.execution_strategy == "VWAP"
            assert result.execution_details["performance_vs_vwap"] == -0.05
            mock_vwap.assert_called_once()

    @pytest.mark.asyncio
    async def test_iceberg_execution_strategy(
        self, order_execution_engine, sample_portfolio
    ):
        """Test Iceberg execution strategy for large orders."""
        iceberg_order = OrderCreate(
            symbol="AAPL",
            quantity=5000,  # Very large order
            order_type=OrderType.LIMIT,
            side="buy",
            limit_price=155.0,
            execution_strategy="ICEBERG",
            display_quantity=100,  # Only show 100 shares at a time
        )

        with patch.object(
            order_execution_engine, "_execute_iceberg_strategy"
        ) as mock_iceberg:
            mock_iceberg.return_value = OrderExecutionResult(
                success=True,
                message="Iceberg execution completed",
                executed_quantity=5000,
                executed_price=154.95,
                cash_change=-774750.0,
                execution_strategy="ICEBERG",
                execution_details={
                    "total_slices": 50,
                    "display_quantity": 100,
                    "hidden_quantity": 4900,
                    "avg_fill_price": 154.95,
                    "market_impact": 0.05,  # 5 cents impact
                },
            )

            result = await order_execution_engine.execute_order(
                iceberg_order, sample_portfolio
            )

            assert result.success is True
            assert result.execution_strategy == "ICEBERG"
            assert result.execution_details["total_slices"] == 50
            mock_iceberg.assert_called_once()


class TestOrderFillSimulation:
    """Test order fill simulation logic."""

    def test_market_order_fill_simulation(self):
        """Test market order fill simulation."""
        simulator = OrderFillSimulator()

        quote = Quote(
            symbol="AAPL",
            current_price=155.0,
            bid=154.5,
            ask=155.5,
            high=158.0,
            low=152.0,
            volume=1000000,
            market_cap=2500000000.0,
        )

        # Buy order should fill at ask
        buy_fill = simulator.simulate_market_fill("buy", 100, quote)
        assert buy_fill.fill_price == quote.ask
        assert buy_fill.fill_quantity == 100
        assert buy_fill.fill_probability == 1.0

        # Sell order should fill at bid
        sell_fill = simulator.simulate_market_fill("sell", 100, quote)
        assert sell_fill.fill_price == quote.bid
        assert sell_fill.fill_quantity == 100

    def test_limit_order_fill_simulation(self):
        """Test limit order fill simulation."""
        simulator = OrderFillSimulator()

        quote = Quote(
            symbol="AAPL",
            current_price=155.0,
            bid=154.5,
            ask=155.5,
            high=158.0,
            low=152.0,
            volume=1000000,
            market_cap=2500000000.0,
        )

        # Aggressive buy limit (above ask) should fill immediately
        aggressive_buy = simulator.simulate_limit_fill("buy", 100, 156.0, quote)
        assert aggressive_buy.fill_probability > 0.9
        assert aggressive_buy.fill_price <= 156.0

        # Conservative buy limit (below bid) should have low fill probability
        conservative_buy = simulator.simulate_limit_fill("buy", 100, 154.0, quote)
        assert conservative_buy.fill_probability < 0.5

    def test_partial_fill_simulation(self):
        """Test partial fill simulation for large orders."""
        simulator = OrderFillSimulator()

        quote = Quote(
            symbol="AAPL",
            current_price=155.0,
            bid=154.5,
            ask=155.5,
            high=158.0,
            low=152.0,
            volume=1000000,
            market_cap=2500000000.0,
        )

        # Very large order should result in partial fill
        large_order_fill = simulator.simulate_market_fill("buy", 100000, quote)

        # Should be partially filled due to market impact
        assert large_order_fill.fill_quantity <= 100000
        assert large_order_fill.market_impact > 0
        assert large_order_fill.slippage > 0

    def test_volatility_impact_on_fills(self):
        """Test impact of volatility on order fills."""
        simulator = OrderFillSimulator()

        # High volatility stock
        volatile_quote = Quote(
            symbol="TSLA",
            current_price=750.0,
            bid=745.0,
            ask=755.0,
            high=780.0,
            low=720.0,  # Wide daily range indicates volatility
            volume=2000000,
            market_cap=800000000.0,
        )

        # Low volatility stock
        stable_quote = Quote(
            symbol="KO",
            current_price=60.0,
            bid=59.95,
            ask=60.05,
            high=60.10,
            low=59.90,  # Narrow range
            volume=500000,
            market_cap=260000000.0,
        )

        volatile_fill = simulator.simulate_limit_fill("buy", 100, 750.0, volatile_quote)
        stable_fill = simulator.simulate_limit_fill("buy", 100, 60.0, stable_quote)

        # Volatile stock should have higher uncertainty in fill
        assert volatile_fill.price_uncertainty > stable_fill.price_uncertainty


class TestMarketImpactCalculation:
    """Test market impact calculation for large orders."""

    def test_linear_market_impact_model(self):
        """Test linear market impact model."""
        calculator = MarketImpactCalculator()

        quote = Quote(
            symbol="AAPL",
            current_price=155.0,
            bid=154.5,
            ask=155.5,
            high=158.0,
            low=152.0,
            volume=1000000,
            market_cap=2500000000.0,
        )

        # Small order should have minimal impact
        small_impact = calculator.calculate_linear_impact(100, quote)
        assert 0 <= small_impact <= 0.01  # Less than 1 cent

        # Large order should have significant impact
        large_impact = calculator.calculate_linear_impact(100000, quote)
        assert large_impact > 0.10  # More than 10 cents
        assert large_impact > small_impact

    def test_square_root_impact_model(self):
        """Test square root market impact model."""
        calculator = MarketImpactCalculator()

        quote = Quote(
            symbol="AAPL",
            current_price=155.0,
            bid=154.5,
            ask=155.5,
            high=158.0,
            low=152.0,
            volume=1000000,
            market_cap=2500000000.0,
        )

        # Test different order sizes
        order_sizes = [100, 1000, 10000, 100000]
        impacts = [
            calculator.calculate_sqrt_impact(size, quote) for size in order_sizes
        ]

        # Impact should increase with order size but at decreasing rate
        for i in range(1, len(impacts)):
            assert impacts[i] > impacts[i - 1]

        # Square root model should show diminishing returns
        ratio_1_2 = impacts[1] / impacts[0]
        ratio_3_4 = impacts[3] / impacts[2]
        assert ratio_1_2 > ratio_3_4  # Diminishing marginal impact

    def test_volume_based_impact(self):
        """Test volume-based market impact calculation."""
        calculator = MarketImpactCalculator()

        high_volume_quote = Quote(
            symbol="AAPL",
            current_price=155.0,
            bid=154.5,
            ask=155.5,
            high=158.0,
            low=152.0,
            volume=5000000,  # High volume
            market_cap=2500000000.0,
        )

        low_volume_quote = Quote(
            symbol="SMALLCAP",
            current_price=25.0,
            bid=24.75,
            ask=25.25,
            high=25.50,
            low=24.50,
            volume=100000,  # Low volume
            market_cap=100000000.0,
        )

        order_quantity = 10000

        high_vol_impact = calculator.calculate_volume_impact(
            order_quantity, high_volume_quote
        )
        low_vol_impact = calculator.calculate_volume_impact(
            order_quantity, low_volume_quote
        )

        # Same order size should have higher impact on low volume stock
        assert low_vol_impact > high_vol_impact


class TestSlippageEstimation:
    """Test slippage estimation for different order types."""

    def test_bid_ask_spread_slippage(self):
        """Test slippage calculation based on bid-ask spread."""
        estimator = SlippageEstimator()

        # Wide spread stock
        wide_spread_quote = Quote(
            symbol="ILLIQUID",
            current_price=50.0,
            bid=49.0,
            ask=51.0,  # 2 dollar spread
            high=52.0,
            low=48.0,
            volume=50000,
            market_cap=500000000.0,
        )

        # Tight spread stock
        tight_spread_quote = Quote(
            symbol="LIQUID",
            current_price=100.0,
            bid=99.95,
            ask=100.05,  # 10 cent spread
            high=101.0,
            low=99.0,
            volume=2000000,
            market_cap=2000000000.0,
        )

        wide_slippage = estimator.estimate_spread_slippage("buy", wide_spread_quote)
        tight_slippage = estimator.estimate_spread_slippage("buy", tight_spread_quote)

        # Wide spread should result in higher slippage
        assert wide_slippage > tight_slippage
        assert wide_slippage >= 1.0  # At least half the spread
        assert tight_slippage <= 0.10  # Should be minimal

    def test_time_based_slippage(self):
        """Test time-based slippage estimation."""
        estimator = SlippageEstimator()

        quote = Quote(
            symbol="AAPL",
            current_price=155.0,
            bid=154.5,
            ask=155.5,
            high=158.0,
            low=152.0,
            volume=1000000,
            market_cap=2500000000.0,
        )

        # Immediate execution should have minimal time slippage
        immediate_slippage = estimator.estimate_time_slippage(0, quote)  # 0 minutes
        assert immediate_slippage == 0

        # Delayed execution should have higher slippage
        delayed_slippage = estimator.estimate_time_slippage(30, quote)  # 30 minutes
        assert delayed_slippage > 0
        assert delayed_slippage > immediate_slippage

    def test_volatility_based_slippage(self):
        """Test volatility-based slippage estimation."""
        estimator = SlippageEstimator()

        # High volatility scenario
        with patch.object(estimator, "_get_historical_volatility") as mock_volatility:
            mock_volatility.return_value = 0.45  # 45% annual volatility

            quote = Quote(
                symbol="VOLATILE",
                current_price=100.0,
                bid=99.0,
                ask=101.0,
                high=110.0,
                low=90.0,
                volume=1000000,
                market_cap=1000000000.0,
            )

            high_vol_slippage = estimator.estimate_volatility_slippage(
                1000, quote, 15
            )  # 15 min execution

            # Reset volatility to low
            mock_volatility.return_value = 0.15  # 15% annual volatility

            low_vol_slippage = estimator.estimate_volatility_slippage(1000, quote, 15)

            # High volatility should result in higher slippage
            assert high_vol_slippage > low_vol_slippage


class TestExecutionQueue:
    """Test order execution queue management."""

    @pytest.mark.asyncio
    async def test_queue_order_processing(self):
        """Test processing orders from execution queue."""
        queue = ExecutionQueue()

        orders = [
            OrderCreate(
                symbol="AAPL", quantity=100, order_type=OrderType.MARKET, side="buy"
            ),
            OrderCreate(
                symbol="GOOGL",
                quantity=10,
                order_type=OrderType.LIMIT,
                side="buy",
                limit_price=2500.0,
            ),
            OrderCreate(
                symbol="MSFT", quantity=50, order_type=OrderType.MARKET, side="sell"
            ),
        ]

        # Add orders to queue
        for order in orders:
            await queue.add_order(order, priority=1)

        assert queue.size() == 3
        assert not queue.is_empty()

        # Process orders
        processed_orders = []
        while not queue.is_empty():
            order = await queue.get_next_order()
            processed_orders.append(order)

        assert len(processed_orders) == 3
        assert queue.is_empty()

    @pytest.mark.asyncio
    async def test_priority_queue_ordering(self):
        """Test priority-based order processing."""
        queue = ExecutionQueue()

        # Add orders with different priorities
        low_priority_order = OrderCreate(
            symbol="LOW", quantity=100, order_type=OrderType.MARKET, side="buy"
        )
        high_priority_order = OrderCreate(
            symbol="HIGH", quantity=100, order_type=OrderType.MARKET, side="buy"
        )
        medium_priority_order = OrderCreate(
            symbol="MED", quantity=100, order_type=OrderType.MARKET, side="buy"
        )

        await queue.add_order(low_priority_order, priority=3)
        await queue.add_order(high_priority_order, priority=1)  # Highest priority
        await queue.add_order(medium_priority_order, priority=2)

        # Orders should be processed by priority (1, 2, 3)
        first_order = await queue.get_next_order()
        second_order = await queue.get_next_order()
        third_order = await queue.get_next_order()

        assert first_order.symbol == "HIGH"
        assert second_order.symbol == "MED"
        assert third_order.symbol == "LOW"

    @pytest.mark.asyncio
    async def test_queue_cancellation(self):
        """Test order cancellation in queue."""
        queue = ExecutionQueue()

        order = OrderCreate(
            symbol="AAPL",
            quantity=100,
            order_type=OrderType.LIMIT,
            side="buy",
            limit_price=150.0,
        )
        order_id = await queue.add_order(order, priority=1)

        assert queue.size() == 1

        # Cancel the order
        cancelled = await queue.cancel_order(order_id)
        assert cancelled is True
        assert queue.size() == 0
        assert queue.is_empty()

        # Try to cancel non-existent order
        fake_cancelled = await queue.cancel_order("fake-id")
        assert fake_cancelled is False

    @pytest.mark.asyncio
    async def test_concurrent_queue_operations(self):
        """Test concurrent queue operations."""
        queue = ExecutionQueue()

        async def producer(start_idx: int, count: int):
            """Add orders to queue concurrently."""
            for i in range(count):
                order = OrderCreate(
                    symbol=f"STOCK{start_idx + i}",
                    quantity=10,
                    order_type=OrderType.MARKET,
                    side="buy",
                )
                await queue.add_order(order, priority=1)

        async def consumer(consumed_orders: list):
            """Process orders from queue concurrently."""
            while len(consumed_orders) < 30:  # Expect 3 producers * 10 orders each
                try:
                    order = await asyncio.wait_for(queue.get_next_order(), timeout=1.0)
                    consumed_orders.append(order)
                except TimeoutError:
                    break

        # Start concurrent producers and consumer
        consumed_orders = []
        tasks = [
            producer(0, 10),  # Producer 1: STOCK0-STOCK9
            producer(10, 10),  # Producer 2: STOCK10-STOCK19
            producer(20, 10),  # Producer 3: STOCK20-STOCK29
            consumer(consumed_orders),
        ]

        await asyncio.gather(*tasks)

        # All orders should be processed
        assert len(consumed_orders) == 30
        symbols = {order.symbol for order in consumed_orders}
        assert len(symbols) == 30  # All unique symbols


class TestOrderStateMachine:
    """Test order state management and transitions."""

    def test_order_state_transitions(self):
        """Test valid order state transitions."""
        state_machine = OrderStateMachine()

        order = OrderCreate(
            symbol="AAPL",
            quantity=100,
            order_type=OrderType.LIMIT,
            side="buy",
            limit_price=150.0,
        )

        # Initial state should be PENDING
        assert state_machine.get_state(order) == OrderStatus.PENDING

        # Valid transitions
        assert (
            state_machine.transition(order, OrderStatus.PENDING, OrderStatus.SUBMITTED)
            is True
        )
        assert (
            state_machine.transition(
                order, OrderStatus.SUBMITTED, OrderStatus.PARTIALLY_FILLED
            )
            is True
        )
        assert (
            state_machine.transition(
                order, OrderStatus.PARTIALLY_FILLED, OrderStatus.FILLED
            )
            is True
        )

        # Final state
        assert state_machine.get_state(order) == OrderStatus.FILLED

    def test_invalid_state_transitions(self):
        """Test invalid order state transitions."""
        state_machine = OrderStateMachine()

        order = OrderCreate(
            symbol="AAPL", quantity=100, order_type=OrderType.MARKET, side="buy"
        )

        # Invalid transitions should be rejected
        assert (
            state_machine.transition(order, OrderStatus.PENDING, OrderStatus.FILLED)
            is False
        )  # Skip states
        assert (
            state_machine.transition(
                order, OrderStatus.CANCELLED, OrderStatus.SUBMITTED
            )
            is False
        )  # From terminal state
        assert (
            state_machine.transition(order, OrderStatus.FILLED, OrderStatus.PENDING)
            is False
        )  # Backwards

    def test_cancellation_transitions(self):
        """Test order cancellation state transitions."""
        state_machine = OrderStateMachine()

        order = OrderCreate(
            symbol="AAPL",
            quantity=100,
            order_type=OrderType.LIMIT,
            side="buy",
            limit_price=150.0,
        )

        # Can cancel from most states
        state_machine.transition(order, OrderStatus.PENDING, OrderStatus.SUBMITTED)
        assert (
            state_machine.transition(
                order, OrderStatus.SUBMITTED, OrderStatus.CANCELLED
            )
            is True
        )

        # Reset for another test
        order2 = OrderCreate(
            symbol="GOOGL",
            quantity=10,
            order_type=OrderType.LIMIT,
            side="sell",
            limit_price=2600.0,
        )
        state_machine.transition(order2, OrderStatus.PENDING, OrderStatus.SUBMITTED)
        state_machine.transition(
            order2, OrderStatus.SUBMITTED, OrderStatus.PARTIALLY_FILLED
        )

        # Can cancel partially filled orders
        assert (
            state_machine.transition(
                order2, OrderStatus.PARTIALLY_FILLED, OrderStatus.CANCELLED
            )
            is True
        )

    def test_state_machine_callbacks(self):
        """Test state machine callbacks and events."""
        state_machine = OrderStateMachine()
        callback_history = []

        def state_change_callback(order, old_state, new_state):
            callback_history.append(
                {
                    "order_symbol": order.symbol,
                    "old_state": old_state,
                    "new_state": new_state,
                    "timestamp": datetime.utcnow(),
                }
            )

        state_machine.add_callback(state_change_callback)

        order = OrderCreate(
            symbol="AAPL", quantity=100, order_type=OrderType.MARKET, side="buy"
        )

        # Perform state transitions
        state_machine.transition(order, OrderStatus.PENDING, OrderStatus.SUBMITTED)
        state_machine.transition(order, OrderStatus.SUBMITTED, OrderStatus.FILLED)

        # Verify callbacks were triggered
        assert len(callback_history) == 2
        assert callback_history[0]["old_state"] == OrderStatus.PENDING
        assert callback_history[0]["new_state"] == OrderStatus.SUBMITTED
        assert callback_history[1]["old_state"] == OrderStatus.SUBMITTED
        assert callback_history[1]["new_state"] == OrderStatus.FILLED


class TestMultiLegOrderExecution:
    """Test multi-leg order execution strategies."""

    @pytest.mark.asyncio
    async def test_spread_order_execution(
        self, order_execution_engine, sample_portfolio
    ):
        """Test execution of spread orders."""
        spread_legs = [
            OrderLeg(
                symbol="AAPL240119C00155000",  # Buy call
                quantity=1,
                side="buy",
                order_type=OrderType.LIMIT,
                limit_price=5.0,
            ),
            OrderLeg(
                symbol="AAPL240119C00160000",  # Sell call
                quantity=1,
                side="sell",
                order_type=OrderType.LIMIT,
                limit_price=3.0,
            ),
        ]

        spread_order = MultiLegOrder(
            strategy_type="call_spread", legs=spread_legs, net_debit=2.0
        )

        with patch.object(
            order_execution_engine, "_execute_spread_order"
        ) as mock_spread:
            mock_spread.return_value = OrderExecutionResult(
                success=True,
                message="Spread order executed",
                executed_quantity=1,
                executed_price=2.0,  # Net debit
                cash_change=-200.0,  # $2.00 * 100 * 1 contract
                execution_strategy="spread_order",
                positions_created=[
                    Position(
                        symbol="AAPL240119C00155000", quantity=1, average_cost=5.0
                    ),
                    Position(
                        symbol="AAPL240119C00160000", quantity=-1, average_cost=-3.0
                    ),
                ],
            )

            result = await order_execution_engine.execute_multileg_order(
                spread_order, sample_portfolio
            )

            assert result.success is True
            assert result.execution_strategy == "spread_order"
            assert len(result.positions_created) == 2
            mock_spread.assert_called_once()

    @pytest.mark.asyncio
    async def test_iron_condor_execution(
        self, order_execution_engine, sample_portfolio
    ):
        """Test execution of iron condor strategy."""
        iron_condor_legs = [
            OrderLeg(
                symbol="AAPL240119P00145000", quantity=1, side="buy", limit_price=1.0
            ),
            OrderLeg(
                symbol="AAPL240119P00150000", quantity=1, side="sell", limit_price=2.0
            ),
            OrderLeg(
                symbol="AAPL240119C00160000", quantity=1, side="sell", limit_price=3.0
            ),
            OrderLeg(
                symbol="AAPL240119C00165000", quantity=1, side="buy", limit_price=1.5
            ),
        ]

        iron_condor = MultiLegOrder(
            strategy_type="iron_condor",
            legs=iron_condor_legs,
            net_credit=2.5,  # Net credit received
        )

        with patch.object(
            order_execution_engine, "_execute_iron_condor"
        ) as mock_condor:
            mock_condor.return_value = OrderExecutionResult(
                success=True,
                message="Iron condor executed",
                executed_quantity=1,
                executed_price=-2.5,  # Net credit (negative indicates credit)
                cash_change=250.0,  # $2.50 * 100 * 1 contract credit
                execution_strategy="iron_condor",
                positions_created=[
                    Position(
                        symbol="AAPL240119P00145000", quantity=1, average_cost=1.0
                    ),
                    Position(
                        symbol="AAPL240119P00150000", quantity=-1, average_cost=-2.0
                    ),
                    Position(
                        symbol="AAPL240119C00160000", quantity=-1, average_cost=-3.0
                    ),
                    Position(
                        symbol="AAPL240119C00165000", quantity=1, average_cost=1.5
                    ),
                ],
            )

            result = await order_execution_engine.execute_multileg_order(
                iron_condor, sample_portfolio
            )

            assert result.success is True
            assert result.cash_change > 0  # Should receive credit
            assert len(result.positions_created) == 4
            mock_condor.assert_called_once()


class TestExecutionPerformanceOptimization:
    """Test execution performance optimization techniques."""

    @pytest.mark.asyncio
    async def test_batch_order_execution(
        self, order_execution_engine, sample_portfolio
    ):
        """Test batch execution of multiple orders."""
        orders = [
            OrderCreate(
                symbol="AAPL", quantity=10, order_type=OrderType.MARKET, side="buy"
            ),
            OrderCreate(
                symbol="GOOGL", quantity=1, order_type=OrderType.MARKET, side="buy"
            ),
            OrderCreate(
                symbol="MSFT", quantity=5, order_type=OrderType.MARKET, side="buy"
            ),
        ]

        start_time = asyncio.get_event_loop().time()

        # Execute orders in batch
        results = await order_execution_engine.execute_batch_orders(
            orders, sample_portfolio
        )

        end_time = asyncio.get_event_loop().time()
        execution_time = end_time - start_time

        assert len(results) == 3
        assert all(result.success for result in results)

        # Batch execution should be faster than sequential
        assert execution_time < 1.0  # Should complete within 1 second

    @pytest.mark.asyncio
    async def test_execution_caching(self, order_execution_engine, sample_portfolio):
        """Test caching of execution-related calculations."""
        order = OrderCreate(
            symbol="AAPL", quantity=100, order_type=OrderType.MARKET, side="buy"
        )

        # First execution (should cache market data)
        start_time1 = asyncio.get_event_loop().time()
        result1 = await order_execution_engine.execute_order(order, sample_portfolio)
        end_time1 = asyncio.get_event_loop().time()

        # Second execution (should use cache)
        start_time2 = asyncio.get_event_loop().time()
        result2 = await order_execution_engine.execute_order(order, sample_portfolio)
        end_time2 = asyncio.get_event_loop().time()

        time1 = end_time1 - start_time1
        time2 = end_time2 - start_time2

        # Both should succeed
        assert result1.success and result2.success

        # Second execution should benefit from caching
        assert time2 <= time1  # Allow for some variance

    @pytest.mark.asyncio
    async def test_concurrent_execution_safety(
        self, order_execution_engine, sample_portfolio
    ):
        """Test thread safety of concurrent order executions."""
        orders = [
            OrderCreate(
                symbol="AAPL",
                quantity=10,
                order_type=OrderType.MARKET,
                side="buy" if i % 2 == 0 else "sell",
            )
            for i in range(20)
        ]

        # Execute orders concurrently
        tasks = [
            order_execution_engine.execute_order(order, sample_portfolio)
            for order in orders
        ]

        results = await asyncio.gather(*tasks, return_exceptions=True)

        # Check that all executions completed without exceptions
        successful_results = [r for r in results if isinstance(r, OrderExecutionResult)]
        exceptions = [r for r in results if isinstance(r, Exception)]

        assert len(successful_results) >= 15  # Allow for some order rejections
        assert len(exceptions) == 0  # No exceptions should occur

        # Verify portfolio consistency
        # (In real implementation, would check position calculations)
        buy_results = [r for r in successful_results if r.success and r.cash_change < 0]
        sell_results = [
            r for r in successful_results if r.success and r.cash_change > 0
        ]

        assert len(buy_results) > 0
        assert len(sell_results) > 0
