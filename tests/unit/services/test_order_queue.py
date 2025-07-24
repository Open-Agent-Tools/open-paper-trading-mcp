"""
Comprehensive tests for app/services/order_queue.py - Async order queue management.

Tests cover:
- Queue initialization and configuration
- Order enqueuing with priority handling
- Worker lifecycle and task management
- Batch processing and timer operations
- Priority queue operations and metrics
- Error handling and retry logic
- Flow control and rate limiting
- Concurrent processing and thread safety
- Queue draining and shutdown procedures
- Performance monitoring and metrics
"""

import asyncio
from datetime import datetime
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.schemas.orders import Order, OrderSide, OrderStatus, OrderType
from app.services.order_queue import (
    BatchConfig,
    OrderQueue,
    ProcessingStatus,
    QueuedOrder,
    QueueMetrics,
    QueuePriority,
    get_order_queue,
    initialize_order_queue,
)


class TestQueuedOrder:
    """Test suite for QueuedOrder data class."""

    def test_queued_order_creation(self):
        """Test QueuedOrder creation with defaults."""
        order = Order(
            id="test-123",
            symbol="AAPL",
            order_type=OrderType.MARKET,
            side=OrderSide.BUY,
            quantity=100,
            status=OrderStatus.PENDING_NEW,
        )

        queued_order = QueuedOrder(
            order=order, priority=QueuePriority.NORMAL, queued_at=datetime.utcnow()
        )

        assert queued_order.order == order
        assert queued_order.priority == QueuePriority.NORMAL
        assert queued_order.attempts == 0
        assert queued_order.max_attempts == 3
        assert queued_order.status == ProcessingStatus.QUEUED
        assert queued_order.metadata == {}
        assert queued_order.callback is None

    def test_queued_order_priority_comparison(self):
        """Test priority comparison for heap operations."""
        order1 = Order(
            id="1",
            symbol="AAPL",
            order_type=OrderType.MARKET,
            side=OrderSide.BUY,
            quantity=100,
            status=OrderStatus.PENDING_NEW,
        )
        order2 = Order(
            id="2",
            symbol="MSFT",
            order_type=OrderType.LIMIT,
            side=OrderSide.SELL,
            quantity=50,
            status=OrderStatus.PENDING_NEW,
        )

        queued1 = QueuedOrder(
            order=order1, priority=QueuePriority.HIGH, queued_at=datetime.utcnow()
        )
        queued2 = QueuedOrder(
            order=order2, priority=QueuePriority.LOW, queued_at=datetime.utcnow()
        )

        assert queued1 < queued2  # Higher priority (lower number) comes first

    def test_queued_order_time_comparison(self):
        """Test time-based comparison for same priority."""
        order1 = Order(
            id="1",
            symbol="AAPL",
            order_type=OrderType.MARKET,
            side=OrderSide.BUY,
            quantity=100,
            status=OrderStatus.PENDING_NEW,
        )
        order2 = Order(
            id="2",
            symbol="MSFT",
            order_type=OrderType.LIMIT,
            side=OrderSide.SELL,
            quantity=50,
            status=OrderStatus.PENDING_NEW,
        )

        time1 = datetime.utcnow()
        time2 = datetime.utcnow()

        queued1 = QueuedOrder(
            order=order1, priority=QueuePriority.NORMAL, queued_at=time1
        )
        queued2 = QueuedOrder(
            order=order2, priority=QueuePriority.NORMAL, queued_at=time2
        )

        assert queued1 < queued2  # Earlier time comes first


class TestBatchConfig:
    """Test suite for BatchConfig data class."""

    def test_batch_config_defaults(self):
        """Test BatchConfig default values."""
        config = BatchConfig()

        assert config.max_batch_size == 10
        assert config.max_wait_time_ms == 100
        assert config.enable_batching is True
        assert config.batch_by_symbol is True

    def test_batch_config_custom_values(self):
        """Test BatchConfig with custom values."""
        config = BatchConfig(
            max_batch_size=20,
            max_wait_time_ms=200,
            enable_batching=False,
            batch_by_symbol=False,
        )

        assert config.max_batch_size == 20
        assert config.max_wait_time_ms == 200
        assert config.enable_batching is False
        assert config.batch_by_symbol is False


class TestQueueMetrics:
    """Test suite for QueueMetrics data class."""

    def test_queue_metrics_defaults(self):
        """Test QueueMetrics default values."""
        metrics = QueueMetrics()

        assert metrics.total_enqueued == 0
        assert metrics.total_processed == 0
        assert metrics.total_failed == 0
        assert metrics.current_queue_depth == 0
        assert metrics.avg_processing_time_ms == 0
        assert metrics.avg_queue_wait_time_ms == 0
        assert metrics.throughput_orders_per_sec == 0
        assert isinstance(metrics.last_reset, datetime)


class TestOrderQueue:
    """Test suite for OrderQueue functionality."""

    @pytest.fixture
    def sample_order(self):
        """Create sample order for testing."""
        return Order(
            id="test-order-123",
            symbol="AAPL",
            order_type=OrderType.MARKET,
            side=OrderSide.BUY,
            quantity=100,
            status=OrderStatus.PENDING_NEW,
        )

    @pytest.fixture
    def batch_config(self):
        """Create batch configuration."""
        return BatchConfig(
            max_batch_size=5,
            max_wait_time_ms=50,
            enable_batching=True,
            batch_by_symbol=True,
        )

    @pytest.fixture
    def order_queue(self, batch_config):
        """Create OrderQueue instance."""
        return OrderQueue(max_concurrent_workers=3, batch_config=batch_config)

    @pytest.fixture
    def mock_processor(self):
        """Create mock order processor."""
        return AsyncMock()

    def test_order_queue_initialization(self, order_queue):
        """Test OrderQueue initialization."""
        assert order_queue.max_workers == 3
        assert isinstance(order_queue.batch_config, BatchConfig)
        assert order_queue.priority_queue == []
        assert order_queue.processing_orders == {}
        assert order_queue.completed_orders == {}
        assert len(order_queue.workers) == 0
        assert order_queue.is_running is False
        assert order_queue.is_draining is False
        assert isinstance(order_queue.metrics, QueueMetrics)

    @pytest.mark.asyncio
    async def test_queue_start_and_stop(self, order_queue):
        """Test queue startup and shutdown."""
        assert not order_queue.is_running

        # Start the queue
        await order_queue.start()
        assert order_queue.is_running
        assert len(order_queue.workers) == 3
        assert order_queue.batch_timer_task is not None

        # Stop the queue
        await order_queue.stop(drain=False)
        assert not order_queue.is_running
        assert len(order_queue.workers) == 0
        assert order_queue.batch_timer_task is None

    @pytest.mark.asyncio
    async def test_queue_start_when_already_running(self, order_queue):
        """Test starting queue when already running."""
        await order_queue.start()
        initial_workers = len(order_queue.workers)

        # Try to start again
        await order_queue.start()

        # Should not create additional workers
        assert len(order_queue.workers) == initial_workers

        await order_queue.stop(drain=False)

    @pytest.mark.asyncio
    async def test_enqueue_order_success(self, order_queue, sample_order):
        """Test successful order enqueuing."""
        await order_queue.start()

        queue_id = await order_queue.enqueue_order(
            sample_order, priority=QueuePriority.HIGH, metadata={"test": "data"}
        )

        assert isinstance(queue_id, str)
        assert queue_id.startswith("queue_test-order-123")
        assert order_queue.metrics.total_enqueued == 1
        assert order_queue.metrics.current_queue_depth == 1
        assert len(order_queue.priority_queue) == 1

        await order_queue.stop(drain=False)

    @pytest.mark.asyncio
    async def test_enqueue_order_not_running(self, order_queue, sample_order):
        """Test enqueuing order when queue not running."""
        with pytest.raises(RuntimeError, match="Order queue is not running"):
            await order_queue.enqueue_order(sample_order)

    @pytest.mark.asyncio
    async def test_enqueue_order_while_draining(self, order_queue, sample_order):
        """Test enqueuing order while queue is draining."""
        await order_queue.start()
        order_queue.is_draining = True

        with pytest.raises(RuntimeError, match="Order queue is draining"):
            await order_queue.enqueue_order(sample_order)

        await order_queue.stop(drain=False)

    @pytest.mark.asyncio
    async def test_enqueue_batch_orders(self, order_queue):
        """Test batch order enqueuing."""
        orders = [
            Order(
                id=f"order-{i}",
                symbol="AAPL",
                order_type=OrderType.MARKET,
                side=OrderSide.BUY,
                quantity=100,
                status=OrderStatus.PENDING_NEW,
            )
            for i in range(3)
        ]

        await order_queue.start()
        queue_ids = await order_queue.enqueue_batch(orders)

        assert len(queue_ids) == 3
        assert order_queue.metrics.total_enqueued == 3
        assert order_queue.metrics.current_queue_depth == 3

        await order_queue.stop(drain=False)

    def test_register_processor(self, order_queue, mock_processor):
        """Test registering order processor."""
        order_queue.register_processor(OrderType.MARKET, mock_processor)

        assert OrderType.MARKET in order_queue.order_processors
        assert order_queue.order_processors[OrderType.MARKET] == mock_processor

    def test_register_completion_callback(self, order_queue):
        """Test registering completion callback."""
        callback = MagicMock()
        order_queue.register_completion_callback(callback)

        assert callback in order_queue.completion_callbacks

    @pytest.mark.asyncio
    async def test_get_queue_status(self, order_queue, sample_order):
        """Test getting queue status."""
        await order_queue.start()
        await order_queue.enqueue_order(sample_order)

        status = await order_queue.get_queue_status()

        assert status["is_running"] is True
        assert status["is_draining"] is False
        assert status["queue_depth"] == 1
        assert status["processing_orders"] == 0
        assert status["completed_orders"] == 0
        assert status["total_enqueued"] == 1
        assert "throughput_orders_per_sec" in status
        assert "active_workers" in status

        await order_queue.stop(drain=False)

    @pytest.mark.asyncio
    async def test_get_next_order(self, order_queue, sample_order):
        """Test getting next order from queue."""
        await order_queue.start()
        await order_queue.enqueue_order(sample_order, priority=QueuePriority.HIGH)

        # Get next order
        queued_order = await order_queue._get_next_order()

        assert queued_order is not None
        assert queued_order.order.id == "test-order-123"
        assert queued_order.status == ProcessingStatus.PROCESSING
        assert order_queue.metrics.current_queue_depth == 0
        assert "test-order-123" in order_queue.processing_orders

        await order_queue.stop(drain=False)

    @pytest.mark.asyncio
    async def test_get_next_order_empty_queue(self, order_queue):
        """Test getting next order from empty queue."""
        await order_queue.start()

        queued_order = await order_queue._get_next_order()

        assert queued_order is None

        await order_queue.stop(drain=False)

    @pytest.mark.asyncio
    async def test_process_order_success(
        self, order_queue, sample_order, mock_processor
    ):
        """Test successful order processing."""
        await order_queue.start()
        order_queue.register_processor(OrderType.MARKET, mock_processor)
        mock_processor.return_value = "success"

        queued_order = QueuedOrder(
            order=sample_order,
            priority=QueuePriority.NORMAL,
            queued_at=datetime.utcnow(),
        )

        await order_queue._process_order(queued_order, worker_id=0)

        assert queued_order.status == ProcessingStatus.COMPLETED
        assert queued_order.metadata["result"] == "success"
        assert order_queue.metrics.total_processed == 1
        mock_processor.assert_called_once_with(sample_order)

        await order_queue.stop(drain=False)

    @pytest.mark.asyncio
    async def test_process_order_no_processor(self, order_queue, sample_order):
        """Test processing order with no registered processor."""
        await order_queue.start()

        queued_order = QueuedOrder(
            order=sample_order,
            priority=QueuePriority.NORMAL,
            queued_at=datetime.utcnow(),
        )

        await order_queue._process_order(queued_order, worker_id=0)

        assert queued_order.status == ProcessingStatus.RETRYING
        assert queued_order.attempts == 1

        await order_queue.stop(drain=False)

    @pytest.mark.asyncio
    async def test_process_order_with_retry(
        self, order_queue, sample_order, mock_processor
    ):
        """Test order processing with retry logic."""
        await order_queue.start()
        order_queue.register_processor(OrderType.MARKET, mock_processor)
        mock_processor.side_effect = Exception("Processing failed")

        queued_order = QueuedOrder(
            order=sample_order,
            priority=QueuePriority.NORMAL,
            queued_at=datetime.utcnow(),
            max_attempts=2,
        )

        await order_queue._process_order(queued_order, worker_id=0)

        assert queued_order.status == ProcessingStatus.RETRYING
        assert queued_order.attempts == 1

        await order_queue.stop(drain=False)

    @pytest.mark.asyncio
    async def test_process_order_max_retries_exceeded(
        self, order_queue, sample_order, mock_processor
    ):
        """Test order processing when max retries exceeded."""
        await order_queue.start()
        order_queue.register_processor(OrderType.MARKET, mock_processor)
        mock_processor.side_effect = Exception("Processing failed")

        queued_order = QueuedOrder(
            order=sample_order,
            priority=QueuePriority.NORMAL,
            queued_at=datetime.utcnow(),
            max_attempts=1,  # Only 1 attempt allowed
        )

        await order_queue._process_order(queued_order, worker_id=0)

        assert queued_order.status == ProcessingStatus.FAILED
        assert queued_order.attempts == 1
        assert order_queue.metrics.total_failed == 1
        assert "Processing failed" in queued_order.metadata["error"]

        await order_queue.stop(drain=False)

    @pytest.mark.asyncio
    async def test_process_order_with_callback(
        self, order_queue, sample_order, mock_processor
    ):
        """Test order processing with completion callback."""
        await order_queue.start()
        order_queue.register_processor(OrderType.MARKET, mock_processor)
        mock_processor.return_value = "success"

        callback = AsyncMock()
        queued_order = QueuedOrder(
            order=sample_order,
            priority=QueuePriority.NORMAL,
            queued_at=datetime.utcnow(),
            callback=callback,
        )

        await order_queue._process_order(queued_order, worker_id=0)

        callback.assert_called_once_with(sample_order, "success", None)

        await order_queue.stop(drain=False)

    @pytest.mark.asyncio
    async def test_process_order_with_error_callback(
        self, order_queue, sample_order, mock_processor
    ):
        """Test order processing with error callback."""
        await order_queue.start()
        order_queue.register_processor(OrderType.MARKET, mock_processor)
        mock_processor.side_effect = Exception("Processing failed")

        callback = AsyncMock()
        queued_order = QueuedOrder(
            order=sample_order,
            priority=QueuePriority.NORMAL,
            queued_at=datetime.utcnow(),
            max_attempts=1,
            callback=callback,
        )

        await order_queue._process_order(queued_order, worker_id=0)

        # Should call error callback
        callback.assert_called_once()
        args = callback.call_args[0]
        assert args[0] == sample_order
        assert args[1] is None  # No result
        assert isinstance(args[2], Exception)

        await order_queue.stop(drain=False)

    @pytest.mark.asyncio
    async def test_requeue_after_delay(self, order_queue, sample_order):
        """Test re-queuing order after delay."""
        await order_queue.start()

        queued_order = QueuedOrder(
            order=sample_order,
            priority=QueuePriority.NORMAL,
            queued_at=datetime.utcnow(),
            attempts=1,
        )

        initial_depth = order_queue.metrics.current_queue_depth

        # Use short delay for testing
        with patch("asyncio.sleep", new_callable=AsyncMock) as mock_sleep:
            await order_queue._requeue_after_delay(queued_order, 0.01)
            mock_sleep.assert_called_once_with(0.01)

        assert queued_order.status == ProcessingStatus.QUEUED
        assert order_queue.metrics.current_queue_depth == initial_depth + 1

        await order_queue.stop(drain=False)

    @pytest.mark.asyncio
    async def test_worker_loop_processing(
        self, order_queue, sample_order, mock_processor
    ):
        """Test worker loop processing orders."""
        await order_queue.start()
        order_queue.register_processor(OrderType.MARKET, mock_processor)
        mock_processor.return_value = "processed"

        # Enqueue an order
        await order_queue.enqueue_order(sample_order)

        # Give workers time to process
        await asyncio.sleep(0.1)

        # Check that order was processed
        assert order_queue.metrics.total_processed >= 1

        await order_queue.stop(drain=False)

    @pytest.mark.asyncio
    async def test_batch_timer_loop(self, order_queue):
        """Test batch timer loop functionality."""
        batch_config = BatchConfig(enable_batching=True, max_wait_time_ms=10)
        queue = OrderQueue(max_concurrent_workers=1, batch_config=batch_config)

        await queue.start()

        # Give batch timer time to run
        await asyncio.sleep(0.05)

        await queue.stop(drain=False)

    @pytest.mark.asyncio
    async def test_drain_queue(self, order_queue, sample_order, mock_processor):
        """Test queue draining functionality."""
        await order_queue.start()
        order_queue.register_processor(OrderType.MARKET, mock_processor)
        mock_processor.return_value = "processed"

        # Enqueue orders
        for i in range(3):
            order = Order(
                id=f"order-{i}",
                symbol="AAPL",
                order_type=OrderType.MARKET,
                side=OrderSide.BUY,
                quantity=100,
                status=OrderStatus.PENDING_NEW,
            )
            await order_queue.enqueue_order(order)

        # Start draining
        await order_queue._drain_queue()

        # All orders should be processed
        assert len(order_queue.priority_queue) == 0
        assert len(order_queue.processing_orders) == 0

        await order_queue.stop(drain=False)

    @pytest.mark.asyncio
    async def test_force_process_order(self, order_queue, sample_order, mock_processor):
        """Test forcing immediate order processing."""
        await order_queue.start()
        order_queue.register_processor(OrderType.MARKET, mock_processor)
        mock_processor.return_value = "forced"

        await order_queue.enqueue_order(sample_order)

        # Force process the order
        success = await order_queue.force_process_order("test-order-123")

        assert success is True
        assert order_queue.metrics.current_queue_depth == 0

        await order_queue.stop(drain=False)

    @pytest.mark.asyncio
    async def test_force_process_nonexistent_order(self, order_queue):
        """Test forcing processing of nonexistent order."""
        await order_queue.start()

        success = await order_queue.force_process_order("nonexistent")

        assert success is False

        await order_queue.stop(drain=False)

    @pytest.mark.asyncio
    async def test_cancel_order(self, order_queue, sample_order):
        """Test cancelling queued order."""
        await order_queue.start()

        await order_queue.enqueue_order(sample_order)

        # Cancel the order
        success = await order_queue.cancel_order("test-order-123")

        assert success is True
        assert order_queue.metrics.current_queue_depth == 0

        await order_queue.stop(drain=False)

    @pytest.mark.asyncio
    async def test_cancel_nonexistent_order(self, order_queue):
        """Test cancelling nonexistent order."""
        await order_queue.start()

        success = await order_queue.cancel_order("nonexistent")

        assert success is False

        await order_queue.stop(drain=False)

    def test_calculate_avg_processing_time(self, order_queue):
        """Test average processing time calculation."""
        order_queue._processing_times = [100.0, 200.0, 300.0]

        avg_time = order_queue._calculate_avg_processing_time()

        assert avg_time == 200.0

    def test_calculate_avg_processing_time_empty(self, order_queue):
        """Test average processing time with no data."""
        avg_time = order_queue._calculate_avg_processing_time()

        assert avg_time == 0.0

    def test_calculate_avg_wait_time(self, order_queue):
        """Test average wait time calculation."""
        order_queue._queue_wait_times = [50.0, 100.0, 150.0]

        avg_time = order_queue._calculate_avg_wait_time()

        assert avg_time == 100.0

    def test_reset_metrics(self, order_queue):
        """Test metrics reset functionality."""
        # Set some metrics
        order_queue.metrics.total_enqueued = 10
        order_queue.metrics.total_processed = 8
        order_queue._processing_times = [100.0, 200.0]
        order_queue._queue_wait_times = [50.0, 75.0]

        order_queue.reset_metrics()

        assert order_queue.metrics.total_enqueued == 0
        assert order_queue.metrics.total_processed == 0
        assert len(order_queue._processing_times) == 0
        assert len(order_queue._queue_wait_times) == 0

    @pytest.mark.asyncio
    async def test_priority_queue_ordering(self, order_queue):
        """Test that orders are processed in priority order."""
        await order_queue.start()

        # Create orders with different priorities
        priorities = [
            QueuePriority.LOW,
            QueuePriority.URGENT,
            QueuePriority.NORMAL,
            QueuePriority.HIGH,
        ]

        for i, priority in enumerate(priorities):
            order = Order(
                id=f"order-{i}",
                symbol="AAPL",
                order_type=OrderType.MARKET,
                side=OrderSide.BUY,
                quantity=100,
                status=OrderStatus.PENDING_NEW,
            )
            await order_queue.enqueue_order(order, priority=priority)

        # Get orders in processing order
        processed_priorities = []
        while len(order_queue.priority_queue) > 0:
            queued_order = await order_queue._get_next_order()
            processed_priorities.append(queued_order.priority)

        # Should be processed in priority order (URGENT, HIGH, NORMAL, LOW)
        expected_order = [
            QueuePriority.URGENT,
            QueuePriority.HIGH,
            QueuePriority.NORMAL,
            QueuePriority.LOW,
        ]
        assert processed_priorities == expected_order

        await order_queue.stop(drain=False)

    @pytest.mark.asyncio
    async def test_concurrent_worker_processing(self, order_queue, mock_processor):
        """Test multiple workers processing orders concurrently."""
        # Use more workers for this test
        queue = OrderQueue(max_concurrent_workers=5)
        await queue.start()
        queue.register_processor(OrderType.MARKET, mock_processor)

        # Simulate slow processing
        async def slow_processor(order):
            await asyncio.sleep(0.01)
            return f"processed-{order.id}"

        queue.register_processor(OrderType.MARKET, slow_processor)

        # Enqueue multiple orders
        orders = []
        for i in range(10):
            order = Order(
                id=f"order-{i}",
                symbol="AAPL",
                order_type=OrderType.MARKET,
                side=OrderSide.BUY,
                quantity=100,
                status=OrderStatus.PENDING_NEW,
            )
            await queue.enqueue_order(order)
            orders.append(order)

        # Wait for processing
        await asyncio.sleep(0.2)

        # All orders should be processed
        assert queue.metrics.total_processed >= len(orders)

        await queue.stop(drain=False)

    @pytest.mark.asyncio
    async def test_error_handling_in_worker_loop(self, order_queue, mock_processor):
        """Test error handling in worker loop."""
        await order_queue.start()

        # Create a processor that raises an exception
        async def failing_processor(order):
            raise Exception("Processor error")

        order_queue.register_processor(OrderType.MARKET, failing_processor)

        order = Order(
            id="failing-order",
            symbol="AAPL",
            order_type=OrderType.MARKET,
            side=OrderSide.BUY,
            quantity=100,
            status=OrderStatus.PENDING_NEW,
        )

        await order_queue.enqueue_order(order)

        # Give time for processing and error handling
        await asyncio.sleep(0.1)

        # Worker should continue running despite the error
        active_workers = [w for w in order_queue.workers if not w.done()]
        assert len(active_workers) > 0

        await order_queue.stop(drain=False)

    @pytest.mark.asyncio
    async def test_stop_with_drain(self, order_queue, sample_order, mock_processor):
        """Test stopping queue with draining."""
        await order_queue.start()
        order_queue.register_processor(OrderType.MARKET, mock_processor)
        mock_processor.return_value = "processed"

        # Enqueue orders
        for i in range(3):
            order = Order(
                id=f"order-{i}",
                symbol="AAPL",
                order_type=OrderType.MARKET,
                side=OrderSide.BUY,
                quantity=100,
                status=OrderStatus.PENDING_NEW,
            )
            await order_queue.enqueue_order(order)

        # Stop with drain
        await order_queue.stop(drain=True)

        # All orders should be processed
        assert order_queue.metrics.total_processed >= 3

    @pytest.mark.asyncio
    async def test_completion_callbacks(
        self, order_queue, sample_order, mock_processor
    ):
        """Test completion callbacks are triggered."""
        await order_queue.start()
        order_queue.register_processor(OrderType.MARKET, mock_processor)
        mock_processor.return_value = "processed"

        callback = AsyncMock()
        order_queue.register_completion_callback(callback)

        await order_queue.enqueue_order(sample_order)

        # Give time for processing
        await asyncio.sleep(0.1)

        # Callback should be called
        callback.assert_called()

        await order_queue.stop(drain=False)


class TestGlobalOrderQueue:
    """Test suite for global order queue functions."""

    def test_initialize_order_queue(self):
        """Test global order queue initialization."""
        queue = initialize_order_queue(max_workers=5)

        assert isinstance(queue, OrderQueue)
        assert queue.max_workers == 5

    def test_get_order_queue_initialized(self):
        """Test getting initialized global queue."""
        initialize_order_queue(max_workers=3)
        queue = get_order_queue()

        assert isinstance(queue, OrderQueue)
        assert queue.max_workers == 3

    def test_get_order_queue_not_initialized(self):
        """Test getting uninitialized global queue."""
        # Reset global queue
        import app.services.order_queue as oq_module

        oq_module.order_queue = None

        with pytest.raises(RuntimeError, match="Order queue not initialized"):
            get_order_queue()


class TestOrderQueueIntegration:
    """Integration tests for OrderQueue with real scenarios."""

    @pytest.mark.asyncio
    async def test_high_throughput_scenario(self):
        """Test high throughput order processing."""
        queue = OrderQueue(max_concurrent_workers=10)
        await queue.start()

        # Simple processor
        async def fast_processor(order):
            return f"processed-{order.id}"

        queue.register_processor(OrderType.MARKET, fast_processor)
        queue.register_processor(OrderType.LIMIT, fast_processor)

        # Enqueue many orders quickly
        order_count = 100
        for i in range(order_count):
            order_type = OrderType.MARKET if i % 2 == 0 else OrderType.LIMIT
            order = Order(
                id=f"order-{i}",
                symbol="AAPL",
                order_type=order_type,
                side=OrderSide.BUY,
                quantity=100,
                status=OrderStatus.PENDING_NEW,
            )
            await queue.enqueue_order(order, priority=QueuePriority.NORMAL)

        # Wait for processing
        await asyncio.sleep(1.0)

        # Check throughput
        status = await queue.get_queue_status()
        assert status["total_processed"] >= order_count * 0.8  # At least 80% processed

        await queue.stop(drain=True)

    @pytest.mark.asyncio
    async def test_mixed_priority_scenario(self):
        """Test processing orders with mixed priorities."""
        queue = OrderQueue(max_concurrent_workers=2)
        await queue.start()

        processed_orders = []

        async def tracking_processor(order):
            processed_orders.append(order.id)
            await asyncio.sleep(0.01)  # Small delay
            return f"processed-{order.id}"

        queue.register_processor(OrderType.MARKET, tracking_processor)

        # Enqueue orders with different priorities
        priorities = [
            (QueuePriority.LOW, "low-1"),
            (QueuePriority.URGENT, "urgent-1"),
            (QueuePriority.NORMAL, "normal-1"),
            (QueuePriority.HIGH, "high-1"),
            (QueuePriority.LOW, "low-2"),
            (QueuePriority.URGENT, "urgent-2"),
        ]

        for priority, order_id in priorities:
            order = Order(
                id=order_id,
                symbol="AAPL",
                order_type=OrderType.MARKET,
                side=OrderSide.BUY,
                quantity=100,
                status=OrderStatus.PENDING_NEW,
            )
            await queue.enqueue_order(order, priority=priority)

        # Wait for processing
        await queue.stop(drain=True)

        # Urgent orders should be processed first
        urgent_indices = [
            i for i, order_id in enumerate(processed_orders) if "urgent" in order_id
        ]
        low_indices = [
            i for i, order_id in enumerate(processed_orders) if "low" in order_id
        ]

        # All urgent orders should come before low priority orders
        if urgent_indices and low_indices:
            assert max(urgent_indices) < min(low_indices)

    @pytest.mark.asyncio
    async def test_error_recovery_scenario(self):
        """Test error recovery and retry behavior."""
        queue = OrderQueue(max_concurrent_workers=1)
        await queue.start()

        call_count = 0

        async def flaky_processor(order):
            nonlocal call_count
            call_count += 1
            if call_count <= 2:  # Fail first two attempts
                raise Exception(f"Attempt {call_count} failed")
            return f"processed-{order.id}"

        queue.register_processor(OrderType.MARKET, flaky_processor)

        order = Order(
            id="retry-order",
            symbol="AAPL",
            order_type=OrderType.MARKET,
            side=OrderSide.BUY,
            quantity=100,
            status=OrderStatus.PENDING_NEW,
        )

        await queue.enqueue_order(order)

        # Wait for retries and eventual success
        await asyncio.sleep(10)  # Allow time for retries with exponential backoff

        status = await queue.get_queue_status()
        assert status["total_processed"] >= 1  # Should eventually succeed

        await queue.stop(drain=False)
