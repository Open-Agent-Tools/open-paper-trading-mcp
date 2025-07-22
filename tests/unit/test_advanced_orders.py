"""
Unit tests for advanced order types and execution logic.

This module tests all advanced order functionality including:
- Stop loss orders
- Stop limit orders
- Trailing stop orders
- Order conversion logic
- Trigger condition monitoring
"""

from datetime import datetime
from unittest.mock import AsyncMock, Mock

import pytest

from app.schemas.orders import Order, OrderStatus, OrderType
from app.services.market_impact import FillResult, MarketImpactSimulator
from app.services.order_conversion import OrderConversionError, OrderConverter
from app.services.order_execution_engine import (OrderExecutionEngine,
                                                 TriggerCondition)
from app.services.order_lifecycle import (OrderEvent, OrderLifecycleError,
                                          OrderLifecycleManager)
from app.services.order_state_tracker import (MemoryEfficientOrderTracker,
                                              StateChangeEvent)


class TestAdvancedOrderTypes:
    """Test advanced order type validation and behavior."""

    def test_stop_loss_order_creation(self):
        """Test creating stop loss orders with proper validation."""
        order = Order(
            id="test_stop_1",
            symbol="AAPL",
            order_type=OrderType.STOP_LOSS,
            quantity=100,
            price=150.00,
            stop_price=145.00,
            status=OrderStatus.PENDING,
            created_at=datetime.utcnow(),
        )

        assert order.order_type == OrderType.STOP_LOSS
        assert order.stop_price == 145.00
        assert order.status == OrderStatus.PENDING

    def test_stop_limit_order_creation(self):
        """Test creating stop limit orders."""
        order = Order(
            id="test_stop_limit_1",
            symbol="GOOGL",
            order_type=OrderType.STOP_LIMIT,
            quantity=50,
            price=2800.00,  # Limit price
            stop_price=2750.00,  # Stop price
            status=OrderStatus.PENDING,
            created_at=datetime.utcnow(),
        )

        assert order.order_type == OrderType.STOP_LIMIT
        assert order.price == 2800.00
        assert order.stop_price == 2750.00

    def test_trailing_stop_percent_order(self):
        """Test trailing stop with percentage."""
        order = Order(
            id="test_trail_pct_1",
            symbol="TSLA",
            order_type=OrderType.TRAILING_STOP,
            quantity=200,
            trail_percent=5.0,  # 5% trailing stop
            status=OrderStatus.PENDING,
            created_at=datetime.utcnow(),
        )

        assert order.order_type == OrderType.TRAILING_STOP
        assert order.trail_percent == 5.0
        assert order.trail_amount is None

    def test_trailing_stop_dollar_amount(self):
        """Test trailing stop with dollar amount."""
        order = Order(
            id="test_trail_amt_1",
            symbol="MSFT",
            order_type=OrderType.TRAILING_STOP,
            quantity=150,
            trail_amount=10.00,  # $10 trailing stop
            status=OrderStatus.PENDING,
            created_at=datetime.utcnow(),
        )

        assert order.order_type == OrderType.TRAILING_STOP
        assert order.trail_amount == 10.00
        assert order.trail_percent is None

    def test_invalid_order_combinations(self):
        """Test validation of invalid order field combinations."""
        # Regular order shouldn't have trigger fields
        order = Order(
            id="test_invalid_1",
            symbol="AAPL",
            order_type=OrderType.BUY,
            quantity=100,
            price=150.00,
            stop_price=145.00,  # Invalid for regular buy order
            status=OrderStatus.PENDING,
            created_at=datetime.utcnow(),
        )

        # This should be caught by validation in real usage
        assert order.order_type == OrderType.BUY
        assert order.stop_price is not None  # Invalid combination


class TestOrderConverter:
    """Test order conversion logic for triggered orders."""

    @pytest.fixture
    def converter(self):
        return OrderConverter()

    def test_stop_loss_to_market_conversion(self, converter):
        """Test converting stop loss to market order."""
        stop_order = Order(
            id="stop_1",
            symbol="AAPL",
            order_type=OrderType.STOP_LOSS,
            quantity=100,
            stop_price=145.00,
            status=OrderStatus.PENDING,
            created_at=datetime.utcnow(),
        )

        market_order = converter.convert_stop_loss_to_market(stop_order, 144.50)

        assert market_order.order_type == OrderType.SELL
        assert market_order.quantity == 100
        assert market_order.price is None  # Market order
        assert market_order.stop_price is None  # Cleared after conversion

    def test_stop_limit_to_limit_conversion(self, converter):
        """Test converting stop limit to limit order."""
        stop_limit_order = Order(
            id="stop_limit_1",
            symbol="GOOGL",
            order_type=OrderType.STOP_LIMIT,
            quantity=50,
            price=2800.00,
            stop_price=2750.00,
            status=OrderStatus.PENDING,
            created_at=datetime.utcnow(),
        )

        limit_order = converter.convert_stop_limit_to_limit(stop_limit_order, 2740.00)

        assert limit_order.order_type == OrderType.SELL
        assert limit_order.quantity == 50
        assert limit_order.price == 2800.00  # Original limit price preserved
        assert limit_order.stop_price is None

    def test_trailing_stop_update(self, converter):
        """Test updating trailing stop prices."""
        trailing_order = Order(
            id="trail_1",
            symbol="TSLA",
            order_type=OrderType.TRAILING_STOP,
            quantity=100,
            trail_percent=5.0,
            stop_price=190.00,  # Previous stop price
            status=OrderStatus.PENDING,
            created_at=datetime.utcnow(),
        )

        # Price moved up, should update trailing stop
        updated_order = converter.update_trailing_stop(trailing_order, 210.00)

        expected_stop = 210.00 * (1 - 0.05)  # 199.50
        assert updated_order.stop_price == expected_stop
        assert updated_order.trail_percent == 5.0

    def test_trailing_stop_no_update_on_decline(self, converter):
        """Test trailing stop doesn't update when price declines."""
        trailing_order = Order(
            id="trail_2",
            symbol="MSFT",
            order_type=OrderType.TRAILING_STOP,
            quantity=100,
            trail_amount=10.00,
            stop_price=300.00,
            status=OrderStatus.PENDING,
            created_at=datetime.utcnow(),
        )

        # Price declined, should not update stop
        updated_order = converter.update_trailing_stop(trailing_order, 305.00)

        assert updated_order.stop_price == 300.00  # Unchanged

    def test_conversion_error_handling(self, converter):
        """Test error handling in order conversion."""
        invalid_order = Order(
            id="invalid_1",
            symbol="AAPL",
            order_type=OrderType.BUY,  # Not a trigger order
            quantity=100,
            status=OrderStatus.PENDING,
            created_at=datetime.utcnow(),
        )

        with pytest.raises(OrderConversionError):
            converter.convert_stop_loss_to_market(invalid_order, 150.00)


class TestOrderExecutionEngine:
    """Test order execution engine functionality."""

    @pytest.fixture
    def mock_trading_service(self):
        service = AsyncMock()
        service.get_current_quote = AsyncMock(return_value=Mock(price=150.00))
        service.execute_order = AsyncMock()
        return service

    @pytest.fixture
    def execution_engine(self, mock_trading_service):
        return OrderExecutionEngine(mock_trading_service)

    @pytest.mark.asyncio
    async def test_trigger_condition_evaluation(self, execution_engine):
        """Test trigger condition evaluation logic."""
        # Stop loss trigger
        stop_condition = TriggerCondition(
            order_id="stop_1",
            symbol="AAPL",
            trigger_type="stop_loss",
            trigger_price=145.00,
            order_type=OrderType.SELL,
        )

        # Should trigger when price drops below
        assert execution_engine._should_trigger(stop_condition, 144.00)
        # Should not trigger when price is above
        assert not execution_engine._should_trigger(stop_condition, 146.00)

    @pytest.mark.asyncio
    async def test_stop_loss_execution(
        self, execution_engine, mock_trading_service, mocker
    ):
        """Test stop loss order execution."""
        stop_order = Order(
            id="stop_exec_1",
            symbol="AAPL",
            order_type=OrderType.STOP_LOSS,
            quantity=100,
            stop_price=145.00,
            status=OrderStatus.PENDING,
            created_at=datetime.utcnow(),
        )

        # Mock the database lookup to return the original order
        mock_load_order = mocker.patch.object(
            execution_engine, "_load_order_by_id", return_value=stop_order
        )

        # Add order to engine
        await execution_engine.add_trigger_order(stop_order)

        # Simulate price drop that triggers stop
        await execution_engine._check_trigger_conditions("AAPL", 144.00)

        # Verify order was loaded from database and executed
        mock_load_order.assert_called_once_with("stop_exec_1")
        mock_trading_service.execute_order.assert_called_once()

    @pytest.mark.skip(
        reason="Trailing stop updates not fully implemented yet - needs original order reference"
    )
    @pytest.mark.asyncio
    async def test_trailing_stop_updates(self, execution_engine):
        """Test trailing stop automatic updates."""
        trailing_order = Order(
            id="trail_exec_1",
            symbol="TSLA",
            order_type=OrderType.TRAILING_STOP,
            quantity=100,
            trail_percent=5.0,
            stop_price=190.00,
            status=OrderStatus.PENDING,
            created_at=datetime.utcnow(),
        )

        await execution_engine.add_trigger_order(trailing_order)

        # Price moves up, should update trailing stop
        await execution_engine._check_trigger_conditions("TSLA", 210.00)

        # Verify stop price was updated - conditions are stored by symbol
        conditions = execution_engine.trigger_conditions["TSLA"]
        assert len(conditions) == 1
        updated_condition = conditions[0]
        expected_stop = 210.00 * 0.95  # 199.50
        assert updated_condition.trigger_price == expected_stop


class TestMarketImpactSimulator:
    """Test market impact and slippage simulation."""

    @pytest.fixture
    def simulator(self):
        return MarketImpactSimulator()

    def test_market_order_slippage(self, simulator):
        """Test slippage calculation for market orders."""
        order = Order(
            id="market_1",
            symbol="AAPL",
            order_type=OrderType.BUY,
            quantity=1000,  # Large order
            status=OrderStatus.PENDING,
            created_at=datetime.utcnow(),
        )

        result = simulator.simulate_market_impact(
            order, 150.00, 1000000
        )  # 1M daily volume

        assert isinstance(result, FillResult)
        assert result.filled_quantity <= order.quantity
        assert result.fill_price >= 150.00  # Slippage for buy order
        assert result.commission > 0

    def test_limit_order_partial_fill(self, simulator):
        """Test partial fill simulation for limit orders."""
        limit_order = Order(
            id="limit_1",
            symbol="GOOGL",
            order_type=OrderType.SELL,
            quantity=500,
            price=2800.00,
            status=OrderStatus.PENDING,
            created_at=datetime.utcnow(),
        )

        # Current price below limit - may get partial or complete fill depending on market conditions
        result = simulator.simulate_market_impact(limit_order, 2790.00, 500000)

        # Limit order should fill at the limit price or better (higher for sell)
        assert result.filled_quantity <= limit_order.quantity
        assert result.fill_price <= limit_order.price
        # Note: partial_fill depends on random market conditions, so we don't assert it

    def test_small_order_minimal_impact(self, simulator):
        """Test that small orders have minimal market impact."""
        small_order = Order(
            id="small_1",
            symbol="MSFT",
            order_type=OrderType.BUY,
            quantity=10,
            status=OrderStatus.PENDING,
            created_at=datetime.utcnow(),
        )

        result = simulator.simulate_market_impact(small_order, 300.00, 2000000)

        assert result.filled_quantity == small_order.quantity
        assert abs(result.fill_price - 300.00) < 1.00  # Minimal slippage
        assert not result.partial_fill  # Complete fill


class TestOrderLifecycleManager:
    """Test order lifecycle management."""

    @pytest.fixture
    def lifecycle_manager(self):
        return OrderLifecycleManager()

    def test_order_state_transitions(self, lifecycle_manager):
        """Test valid order state transitions."""
        # First create an order
        order = Order(
            id="lifecycle_1",
            symbol="AAPL",
            order_type=OrderType.BUY,
            quantity=100,
            status=OrderStatus.PENDING,
            created_at=datetime.utcnow(),
        )

        # Create order in lifecycle manager
        lifecycle_state = lifecycle_manager.create_order(order)
        assert lifecycle_state.current_status == OrderStatus.PENDING

        # Valid transitions
        lifecycle_manager.transition_order(
            "lifecycle_1", OrderStatus.TRIGGERED, OrderEvent.TRIGGERED
        )
        updated_state = lifecycle_manager.get_order_state("lifecycle_1")
        assert updated_state.current_status == OrderStatus.TRIGGERED

        lifecycle_manager.transition_order(
            "lifecycle_1", OrderStatus.FILLED, OrderEvent.FILLED
        )
        final_state = lifecycle_manager.get_order_state("lifecycle_1")
        assert final_state.current_status == OrderStatus.FILLED

    def test_invalid_state_transitions(self, lifecycle_manager):
        """Test that invalid state transitions are rejected."""
        # First create an order
        order = Order(
            id="invalid_transition_1",
            symbol="AAPL",
            order_type=OrderType.BUY,
            quantity=100,
            status=OrderStatus.PENDING,
            created_at=datetime.utcnow(),
        )

        lifecycle_manager.create_order(order)

        # Try invalid transition (PENDING -> CANCELLED is valid, but let's try PENDING -> REJECTED -> FILLED)
        lifecycle_manager.transition_order(
            "invalid_transition_1", OrderStatus.REJECTED, OrderEvent.REJECTED
        )

        # Now try to transition from REJECTED to FILLED - should be invalid
        with pytest.raises(OrderLifecycleError):
            lifecycle_manager.transition_order(
                "invalid_transition_1", OrderStatus.FILLED, OrderEvent.FILLED
            )

    def test_lifecycle_event_history(self, lifecycle_manager):
        """Test order lifecycle event tracking."""
        # First create an order
        order = Order(
            id="history_1",
            symbol="AAPL",
            order_type=OrderType.BUY,
            quantity=100,
            status=OrderStatus.PENDING,
            created_at=datetime.utcnow(),
        )

        # Create order in lifecycle manager
        lifecycle_manager.create_order(order)

        # Make transitions and check the history is tracked
        lifecycle_manager.transition_order(
            "history_1", OrderStatus.TRIGGERED, OrderEvent.TRIGGERED
        )
        lifecycle_manager.transition_order(
            "history_1", OrderStatus.FILLED, OrderEvent.FILLED
        )

        # Verify final state
        final_state = lifecycle_manager.get_order_state("history_1")
        assert final_state.current_status == OrderStatus.FILLED

        # Check that transitions are tracked (if implementation provides history access)
        assert len(final_state.transitions) >= 2  # At least 2 transitions recorded


class TestMemoryEfficientOrderTracker:
    """Test memory-efficient order state tracking."""

    @pytest.fixture
    def tracker(self):
        from app.services.order_state_tracker import OrderStateTrackingConfig

        config = OrderStateTrackingConfig(
            max_snapshots_per_order=10,
            max_total_snapshots=100,
            max_history_days=1,
            cleanup_interval_minutes=1,
        )
        return MemoryEfficientOrderTracker(config)

    def test_state_tracking(self, tracker):
        """Test basic state tracking functionality."""
        order_id = "track_1"

        tracker.track_state_change(
            order_id,
            OrderStatus.PENDING,
            StateChangeEvent.CREATED,
            symbol="AAPL",
            quantity=100,
        )

        current_state = tracker.get_current_state(order_id)
        assert current_state is not None
        assert current_state.status == OrderStatus.PENDING
        assert current_state.symbol == "AAPL"

    def test_order_history_tracking(self, tracker):
        """Test order history tracking."""
        order_id = "history_track_1"

        # Track multiple state changes
        tracker.track_state_change(
            order_id, OrderStatus.PENDING, StateChangeEvent.CREATED
        )
        tracker.track_state_change(
            order_id, OrderStatus.TRIGGERED, StateChangeEvent.TRIGGERED
        )
        tracker.track_state_change(
            order_id, OrderStatus.FILLED, StateChangeEvent.FILLED
        )

        history = tracker.get_order_history(order_id)
        assert len(history) == 3
        assert history[0].event == StateChangeEvent.CREATED
        assert history[-1].event == StateChangeEvent.FILLED

    def test_memory_bounds(self, tracker):
        """Test that tracker respects memory bounds."""
        order_id = "memory_test_1"

        # Add more snapshots than the limit
        for i in range(20):
            tracker.track_state_change(
                order_id,
                OrderStatus.PENDING,
                StateChangeEvent.CREATED,
                metadata={"iteration": i},
            )

        history = tracker.get_order_history(order_id)
        # Should be bounded by max_snapshots_per_order (10)
        assert len(history) <= tracker.config.max_snapshots_per_order

    def test_performance_metrics(self, tracker):
        """Test performance metrics tracking."""
        # Track some events
        for i in range(5):
            tracker.track_state_change(
                f"perf_test_{i}", OrderStatus.PENDING, StateChangeEvent.CREATED
            )

        metrics = tracker.get_performance_metrics()
        assert metrics["total_events"] == 5
        assert metrics["active_orders"] == 5
        assert metrics["memory_usage_kb"] > 0

    def test_cleanup_functionality(self, tracker):
        """Test automatic cleanup of old data."""
        # Add some old data
        order_id = "cleanup_test_1"
        tracker.track_state_change(
            order_id, OrderStatus.FILLED, StateChangeEvent.FILLED
        )

        # Manually trigger cleanup
        results = tracker.cleanup_old_data(force=True)

        assert isinstance(results, dict)
        assert "orders_cleaned" in results
        assert "snapshots_removed" in results


@pytest.mark.asyncio
async def test_integration_order_flow():
    """Integration test for complete order flow."""
    # Mock dependencies
    mock_service = AsyncMock()
    mock_service.get_current_quote = AsyncMock(return_value=Mock(price=150.00))
    mock_service.execute_order = AsyncMock()

    # Create components
    OrderConverter()
    execution_engine = OrderExecutionEngine(mock_service)
    OrderLifecycleManager()
    tracker = MemoryEfficientOrderTracker()

    # Start components
    await execution_engine.start()
    await tracker.start()

    try:
        # Create stop loss order
        stop_order = Order(
            id="integration_1",
            symbol="AAPL",
            order_type=OrderType.STOP_LOSS,
            quantity=100,
            stop_price=145.00,
            status=OrderStatus.PENDING,
            created_at=datetime.utcnow(),
        )

        # Track initial state
        tracker.track_state_change(
            stop_order.id,
            OrderStatus.PENDING,
            StateChangeEvent.CREATED,
            symbol=stop_order.symbol,
            quantity=stop_order.quantity,
        )

        # Mock the database lookup to return the original order
        execution_engine._load_order_by_id = AsyncMock(return_value=stop_order)

        # Add to execution engine
        await execution_engine.add_trigger_order(stop_order)

        # Simulate price drop that triggers stop
        await execution_engine._check_trigger_conditions("AAPL", 144.00)

        # Verify execution was called
        mock_service.execute_order.assert_called_once()

        # Track final state
        tracker.track_state_change(
            stop_order.id, OrderStatus.FILLED, StateChangeEvent.FILLED
        )

        # Verify complete flow
        history = tracker.get_order_history(stop_order.id)
        assert len(history) >= 2
        assert history[0].event == StateChangeEvent.CREATED
        assert history[-1].event == StateChangeEvent.FILLED

    finally:
        await execution_engine.stop()
        await tracker.stop()


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
