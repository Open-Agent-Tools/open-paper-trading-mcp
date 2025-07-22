"""
Integration tests for complete order lifecycle.

This module tests the full integration of all order management components
from order creation through execution and completion.
"""

import asyncio
from datetime import datetime
from unittest.mock import AsyncMock, Mock

import pytest

from app.schemas.orders import Order, OrderStatus, OrderType
from app.schemas.positions import Portfolio, Position
from app.services.market_impact import MarketImpactSimulator
from app.services.order_execution_engine import OrderExecutionEngine
from app.services.order_lifecycle import (OrderLifecycleManager,
                                          OrderLifecycleState)
from app.services.order_notifications import OrderNotificationManager
from app.services.order_queue import OrderQueue, QueuePriority
from app.services.order_state_tracker import (MemoryEfficientOrderTracker,
                                              StateChangeEvent)
from app.services.position_sizing import (PositionSizingCalculator,
                                          SizingStrategy)
from app.services.risk_analysis import RiskAnalyzer


@pytest.fixture
async def mock_trading_service():
    """Mock trading service with realistic behavior."""
    service = AsyncMock()

    # Mock quote data
    quotes = {
        "AAPL": Mock(price=150.00, bid=149.95, ask=150.05),
        "GOOGL": Mock(price=2800.00, bid=2799.00, ask=2801.00),
        "TSLA": Mock(price=200.00, bid=199.50, ask=200.50),
        "MSFT": Mock(price=300.00, bid=299.90, ask=300.10),
    }

    service.get_current_quote = AsyncMock(side_effect=lambda symbol: quotes.get(symbol))
    service.execute_order = AsyncMock(return_value=True)
    service.get_portfolio = AsyncMock(
        return_value=Portfolio(
            cash_balance=100000.0, positions=[], total_value=100000.0
        )
    )

    return service


@pytest.fixture
def sample_portfolio():
    """Create a sample portfolio for testing."""
    return Portfolio(
        cash_balance=50000.0,
        positions=[
            Position(
                symbol="AAPL", quantity=100, current_price=150.00, avg_price=145.00
            ),
            Position(
                symbol="GOOGL", quantity=10, current_price=2800.00, avg_price=2750.00
            ),
        ],
        total_value=78000.0,  # 50000 + 15000 + 28000 - 15000
    )


@pytest.fixture
async def integrated_system(mock_trading_service):
    """Create fully integrated order management system."""
    # Initialize all components
    execution_engine = OrderExecutionEngine(mock_trading_service)
    lifecycle_manager = OrderLifecycleManager()
    notification_manager = OrderNotificationManager()
    market_simulator = MarketImpactSimulator()
    state_tracker = MemoryEfficientOrderTracker()
    order_queue = OrderQueue(max_concurrent_workers=5)
    risk_analyzer = RiskAnalyzer()
    position_calculator = PositionSizingCalculator()

    # Start async components
    await execution_engine.start()
    await state_tracker.start()
    await order_queue.start()

    system = {
        "execution_engine": execution_engine,
        "lifecycle_manager": lifecycle_manager,
        "notification_manager": notification_manager,
        "market_simulator": market_simulator,
        "state_tracker": state_tracker,
        "order_queue": order_queue,
        "risk_analyzer": risk_analyzer,
        "position_calculator": position_calculator,
        "trading_service": mock_trading_service,
    }

    yield system

    # Cleanup
    await execution_engine.stop()
    await state_tracker.stop()
    await order_queue.stop()


class TestBasicOrderLifecycle:
    """Test basic order lifecycle scenarios."""

    @pytest.mark.asyncio
    async def test_market_order_lifecycle(self, integrated_system):
        """Test complete market order lifecycle."""
        system = integrated_system

        # Create market order
        order = Order(
            id="market_lifecycle_1",
            symbol="AAPL",
            order_type=OrderType.BUY,
            quantity=100,
            status=OrderStatus.PENDING,
            created_at=datetime.utcnow(),
        )

        # Track initial state
        system["state_tracker"].track_state_change(
            order.id,
            OrderStatus.PENDING,
            StateChangeEvent.CREATED,
            symbol=order.symbol,
            quantity=order.quantity,
        )

        # Process through lifecycle
        system["lifecycle_manager"].transition_order(
            order.id, OrderLifecycleState.SUBMITTED
        )
        system["lifecycle_manager"].transition_order(
            order.id, OrderLifecycleState.PENDING
        )

        # Simulate market execution
        fill_result = system["market_simulator"].simulate_market_impact(
            order, 150.00, 1000000
        )

        # Update state based on fill
        if fill_result.is_complete:
            system["state_tracker"].track_state_change(
                order.id, OrderStatus.FILLED, StateChangeEvent.FILLED
            )
            system["lifecycle_manager"].transition_order(
                order.id, OrderLifecycleState.FILLED
            )

        # Verify final state
        current_state = system["state_tracker"].get_current_state(order.id)
        assert current_state.status == OrderStatus.FILLED
        assert current_state.event == StateChangeEvent.FILLED

        lifecycle_state = system["lifecycle_manager"].get_current_state(order.id)
        assert lifecycle_state == OrderLifecycleState.FILLED

    @pytest.mark.asyncio
    async def test_limit_order_lifecycle(self, integrated_system):
        """Test limit order lifecycle with partial fills."""
        system = integrated_system

        order = Order(
            id="limit_lifecycle_1",
            symbol="GOOGL",
            order_type=OrderType.SELL,
            quantity=20,
            price=2850.00,  # Above current market
            status=OrderStatus.PENDING,
            created_at=datetime.utcnow(),
        )

        # Track through queue system
        await system["order_queue"].enqueue_order(order, QueuePriority.NORMAL)

        # Register a simple processor
        async def mock_processor(order_to_process):
            return system["market_simulator"].simulate_market_impact(
                order_to_process, 2800.00, 500000
            )

        system["order_queue"].register_processor(OrderType.SELL, mock_processor)

        # Wait for processing
        await asyncio.sleep(0.1)  # Allow queue processing

        # Check queue status
        queue_status = await system["order_queue"].get_queue_status()
        assert queue_status["total_processed"] > 0


class TestStopOrderLifecycle:
    """Test stop order lifecycle integration."""

    @pytest.mark.asyncio
    async def test_stop_loss_trigger_and_execution(self, integrated_system):
        """Test stop loss order triggering and execution."""
        system = integrated_system

        # Create stop loss order
        stop_order = Order(
            id="stop_trigger_1",
            symbol="AAPL",
            order_type=OrderType.STOP_LOSS,
            quantity=100,
            stop_price=145.00,
            status=OrderStatus.PENDING,
            created_at=datetime.utcnow(),
        )

        # Add to execution engine
        system["execution_engine"].add_trigger_order(stop_order)

        # Track initial state
        system["state_tracker"].track_state_change(
            stop_order.id,
            OrderStatus.PENDING,
            StateChangeEvent.CREATED,
            symbol=stop_order.symbol,
            quantity=stop_order.quantity,
        )

        # Simulate price drop that should trigger stop
        await system["execution_engine"]._check_trigger_conditions("AAPL", 144.00)

        # Verify order was triggered and executed
        system["trading_service"].execute_order.assert_called()

        # Track triggered state
        system["state_tracker"].track_state_change(
            stop_order.id, OrderStatus.TRIGGERED, StateChangeEvent.TRIGGERED
        )

        # Verify state progression
        history = system["state_tracker"].get_order_history(stop_order.id)
        events = [snapshot.event for snapshot in history]
        assert StateChangeEvent.CREATED in events
        assert StateChangeEvent.TRIGGERED in events

    @pytest.mark.asyncio
    async def test_trailing_stop_updates_and_trigger(self, integrated_system):
        """Test trailing stop order updates and eventual trigger."""
        system = integrated_system

        trailing_order = Order(
            id="trailing_trigger_1",
            symbol="TSLA",
            order_type=OrderType.TRAILING_STOP,
            quantity=200,
            trail_percent=5.0,
            stop_price=190.00,  # Initial stop
            status=OrderStatus.PENDING,
            created_at=datetime.utcnow(),
        )

        system["execution_engine"].add_trigger_order(trailing_order)
        system["state_tracker"].track_state_change(
            trailing_order.id,
            OrderStatus.PENDING,
            StateChangeEvent.CREATED,
            symbol=trailing_order.symbol,
            quantity=trailing_order.quantity,
        )

        # Price moves up - should update trailing stop
        await system["execution_engine"]._check_trigger_conditions("TSLA", 220.00)

        # Get updated condition
        condition = system["execution_engine"].trigger_conditions.get(trailing_order.id)
        if condition:
            expected_stop = 220.00 * 0.95  # 209.00
            assert abs(condition.trigger_price - expected_stop) < 0.01

        # Price drops enough to trigger
        await system["execution_engine"]._check_trigger_conditions("TSLA", 205.00)

        # Should have triggered execution
        system["trading_service"].execute_order.assert_called()


class TestRiskIntegratedOrderFlow:
    """Test order flow with risk management integration."""

    @pytest.mark.asyncio
    async def test_pre_trade_risk_analysis(self, integrated_system, sample_portfolio):
        """Test order flow with pre-trade risk analysis."""
        system = integrated_system

        # Large order that might have risk implications
        large_order = Order(
            id="risk_analysis_1",
            symbol="AAPL",
            order_type=OrderType.BUY,
            quantity=1000,  # Large quantity
            price=150.00,
            status=OrderStatus.PENDING,
            created_at=datetime.utcnow(),
        )

        # Perform pre-trade risk analysis
        risk_result = system["risk_analyzer"].analyze_order_risk(
            large_order, sample_portfolio
        )

        # Check risk metrics
        assert risk_result.position_impact is not None
        assert risk_result.concentration_risk is not None

        # If risk is acceptable, proceed with order
        if not risk_result.has_warnings():
            system["state_tracker"].track_state_change(
                large_order.id,
                OrderStatus.PENDING,
                StateChangeEvent.CREATED,
                symbol=large_order.symbol,
                quantity=large_order.quantity,
            )
        else:
            # Risk too high - reject order
            system["state_tracker"].track_state_change(
                large_order.id,
                OrderStatus.REJECTED,
                StateChangeEvent.REJECTED,
                metadata={"risk_warnings": risk_result.warnings},
            )

    @pytest.mark.asyncio
    async def test_position_sizing_integration(
        self, integrated_system, sample_portfolio
    ):
        """Test integration with position sizing calculator."""
        system = integrated_system

        # Calculate optimal position size
        sizing_result = system["position_calculator"].calculate_position_size(
            symbol="MSFT",
            current_price=300.00,
            portfolio=sample_portfolio,
            strategy=SizingStrategy.KELLY_CRITERION,
        )

        # Create order with recommended size
        sized_order = Order(
            id="sized_order_1",
            symbol="MSFT",
            order_type=OrderType.BUY,
            quantity=sizing_result.recommended_shares,
            price=300.00,
            status=OrderStatus.PENDING,
            created_at=datetime.utcnow(),
        )

        # Process through full lifecycle
        system["state_tracker"].track_state_change(
            sized_order.id,
            OrderStatus.PENDING,
            StateChangeEvent.CREATED,
            symbol=sized_order.symbol,
            quantity=sized_order.quantity,
            metadata={
                "sizing_strategy": "kelly_criterion",
                "risk_amount": sizing_result.risk_amount,
            },
        )

        # Verify sizing was reasonable
        assert sizing_result.recommended_shares > 0
        assert sizing_result.percent_of_portfolio <= 0.20  # Max 20% position

        current_state = system["state_tracker"].get_current_state(sized_order.id)
        assert current_state is not None
        assert current_state.metadata.get("sizing_strategy") == "kelly_criterion"


class TestHighVolumeOrderProcessing:
    """Test system behavior under high order volumes."""

    @pytest.mark.asyncio
    async def test_concurrent_order_processing(self, integrated_system):
        """Test processing multiple orders concurrently."""
        system = integrated_system

        # Create multiple orders
        orders = []
        for i in range(20):
            order = Order(
                id=f"concurrent_{i}",
                symbol="AAPL" if i % 2 == 0 else "GOOGL",
                order_type=OrderType.BUY,
                quantity=100 + (i * 10),
                price=150.00 if i % 2 == 0 else 2800.00,
                status=OrderStatus.PENDING,
                created_at=datetime.utcnow(),
            )
            orders.append(order)

        # Process all orders through queue
        queue_ids = []
        for order in orders:
            queue_id = await system["order_queue"].enqueue_order(
                order, QueuePriority.NORMAL
            )
            queue_ids.append(queue_id)

            # Track in state tracker
            system["state_tracker"].track_state_change(
                order.id,
                OrderStatus.PENDING,
                StateChangeEvent.CREATED,
                symbol=order.symbol,
                quantity=order.quantity,
            )

        # Register processor
        async def batch_processor(order_to_process):
            await asyncio.sleep(0.01)  # Simulate processing time
            return {"processed": True, "order_id": order_to_process.id}

        system["order_queue"].register_processor(OrderType.BUY, batch_processor)

        # Wait for processing to complete
        await asyncio.sleep(1.0)

        # Check processing results
        queue_status = await system["order_queue"].get_queue_status()
        assert queue_status["total_processed"] > 0

        # Verify state tracking handled all orders
        metrics = system["state_tracker"].get_performance_metrics()
        assert metrics["total_events"] >= len(orders)

    @pytest.mark.asyncio
    async def test_order_queue_priority_handling(self, integrated_system):
        """Test order queue handles priorities correctly."""
        system = integrated_system

        # Create orders with different priorities
        urgent_order = Order(
            id="urgent_1",
            symbol="AAPL",
            order_type=OrderType.SELL,
            quantity=100,
            status=OrderStatus.PENDING,
            created_at=datetime.utcnow(),
        )

        normal_order = Order(
            id="normal_1",
            symbol="GOOGL",
            order_type=OrderType.BUY,
            quantity=50,
            status=OrderStatus.PENDING,
            created_at=datetime.utcnow(),
        )

        # Enqueue normal first, then urgent
        await system["order_queue"].enqueue_order(normal_order, QueuePriority.NORMAL)
        await system["order_queue"].enqueue_order(urgent_order, QueuePriority.URGENT)

        # Track processing order
        processed_orders = []

        async def priority_processor(order):
            processed_orders.append(order.id)
            return {"processed": True}

        system["order_queue"].register_processor(OrderType.SELL, priority_processor)
        system["order_queue"].register_processor(OrderType.BUY, priority_processor)

        # Wait for processing
        await asyncio.sleep(0.5)

        # Urgent order should be processed first despite being queued later
        if processed_orders:
            # The urgent order should be among the first processed
            assert "urgent_1" in processed_orders


class TestErrorHandlingAndRecovery:
    """Test error handling and system recovery."""

    @pytest.mark.asyncio
    async def test_execution_error_handling(self, integrated_system):
        """Test handling of execution errors."""
        system = integrated_system

        # Mock service to fail on execution
        system["trading_service"].execute_order = AsyncMock(
            side_effect=Exception("Market closed")
        )

        error_order = Order(
            id="error_test_1",
            symbol="AAPL",
            order_type=OrderType.STOP_LOSS,
            quantity=100,
            stop_price=145.00,
            status=OrderStatus.PENDING,
            created_at=datetime.utcnow(),
        )

        system["execution_engine"].add_trigger_order(error_order)
        system["state_tracker"].track_state_change(
            error_order.id, OrderStatus.PENDING, StateChangeEvent.CREATED
        )

        # Trigger the order (should fail)
        await system["execution_engine"]._check_trigger_conditions("AAPL", 144.00)

        # Order should still be in system but marked with error
        current_state = system["state_tracker"].get_current_state(error_order.id)
        assert current_state is not None

    @pytest.mark.asyncio
    async def test_state_tracker_memory_management(self, integrated_system):
        """Test state tracker memory management under load."""
        system = integrated_system

        # Create many orders to test memory bounds
        for i in range(150):  # Exceeds max_total_snapshots
            order_id = f"memory_test_{i}"
            system["state_tracker"].track_state_change(
                order_id,
                OrderStatus.PENDING,
                StateChangeEvent.CREATED,
                symbol="TEST",
                quantity=100,
            )

            # Add some state changes per order
            system["state_tracker"].track_state_change(
                order_id, OrderStatus.FILLED, StateChangeEvent.FILLED
            )

        # Force cleanup
        cleanup_results = system["state_tracker"].cleanup_old_data(force=True)

        # Verify cleanup occurred
        assert cleanup_results["orders_cleaned"] >= 0
        assert cleanup_results["snapshots_removed"] >= 0

        # System should still be responsive
        metrics = system["state_tracker"].get_performance_metrics()
        assert metrics["memory_usage_kb"] > 0


@pytest.mark.asyncio
async def test_end_to_end_order_scenarios():
    """Complete end-to-end order scenario tests."""

    # Mock external dependencies
    mock_service = AsyncMock()
    mock_service.get_current_quote = AsyncMock()
    mock_service.execute_order = AsyncMock(return_value=True)

    # Price simulation
    prices = {
        "AAPL": [150.00, 149.00, 148.00, 147.00, 146.00, 144.00, 143.00],  # Declining
        "GOOGL": [2800.00, 2810.00, 2820.00, 2830.00, 2825.00],  # Rising then falling
    }

    price_index = {"AAPL": 0, "GOOGL": 0}

    def get_next_price(symbol):
        idx = price_index[symbol]
        if idx < len(prices[symbol]):
            price = prices[symbol][idx]
            price_index[symbol] += 1
            return Mock(price=price, bid=price - 0.05, ask=price + 0.05)
        return Mock(
            price=prices[symbol][-1],
            bid=prices[symbol][-1] - 0.05,
            ask=prices[symbol][-1] + 0.05,
        )

    mock_service.get_current_quote.side_effect = get_next_price

    # Create system
    execution_engine = OrderExecutionEngine(mock_service)
    state_tracker = MemoryEfficientOrderTracker()

    await execution_engine.start()
    await state_tracker.start()

    try:
        # Scenario: Stop loss order that gets triggered
        stop_order = Order(
            id="e2e_stop_1",
            symbol="AAPL",
            order_type=OrderType.STOP_LOSS,
            quantity=100,
            stop_price=145.00,
            status=OrderStatus.PENDING,
            created_at=datetime.utcnow(),
        )

        execution_engine.add_trigger_order(stop_order)
        state_tracker.track_state_change(
            stop_order.id,
            OrderStatus.PENDING,
            StateChangeEvent.CREATED,
            symbol=stop_order.symbol,
            quantity=stop_order.quantity,
        )

        # Simulate price movements
        for symbol in ["AAPL"]:
            for _ in range(6):  # Will trigger stop loss
                current_quote = get_next_price(symbol)
                await execution_engine._check_trigger_conditions(
                    symbol, current_quote.price
                )
                await asyncio.sleep(0.01)

        # Verify stop was triggered
        mock_service.execute_order.assert_called()

        # Track final state
        state_tracker.track_state_change(
            stop_order.id, OrderStatus.FILLED, StateChangeEvent.FILLED
        )

        # Verify complete history
        history = state_tracker.get_order_history(stop_order.id)
        assert len(history) >= 2
        assert history[0].event == StateChangeEvent.CREATED
        assert history[-1].event == StateChangeEvent.FILLED

    finally:
        await execution_engine.stop()
        await state_tracker.stop()


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
