"""
Unit tests for the OrderQueue class.

These tests verify that the order queue correctly manages order processing,
respects priorities, handles errors, and tracks metrics.
"""

import asyncio
from datetime import datetime, timedelta
from unittest.mock import AsyncMock, patch

import pytest

from app.schemas.orders import Order, OrderType
from app.services.order_queue import (
    BatchConfig,
    OrderQueue,
    ProcessingStatus,
    QueuedOrder,
    QueuePriority,
)


@pytest.fixture
def sample_order():
    """Create a sample order for testing."""
    return Order(
        id="test-order-1",
        symbol="AAPL",
        order_type=OrderType.BUY,
        quantity=100,
        price=150.0,
        created_at=datetime.utcnow(),
    )


@pytest.fixture
def order_queue():
    """Create an OrderQueue instance for testing."""
    queue = OrderQueue(max_concurrent_workers=2)
    return queue


class TestQueuedOrder:
    """Tests for the QueuedOrder class."""

    def test_init(self, sample_order):
        """Test QueuedOrder initialization."""
        queued_order = QueuedOrder(
            order=sample_order,
            priority=QueuePriority.NORMAL,
            queued_at=datetime.utcnow(),
        )

        assert queued_order.order == sample_order
        assert queued_order.priority == QueuePriority.NORMAL
        assert queued_order.queued_at is not None
        assert queued_order.attempts == 0
        assert queued_order.max_attempts == 3
        assert queued_order.status == ProcessingStatus.QUEUED
        assert isinstance(queued_order.metadata, dict)
        assert queued_order.callback is None

    def test_lt_comparison(self, sample_order):
        """Test priority comparison for heap queue."""
        now = datetime.utcnow()

        # Same priority, different time
        order1 = QueuedOrder(
            order=sample_order,
            priority=QueuePriority.NORMAL,
            queued_at=now,
        )
        order2 = QueuedOrder(
            order=sample_order,
            priority=QueuePriority.NORMAL,
            queued_at=now + timedelta(seconds=1),
        )
        assert order1 < order2  # Earlier time should be higher priority

        # Different priority, same time
        order3 = QueuedOrder(
            order=sample_order,
            priority=QueuePriority.HIGH,
            queued_at=now,
        )
        order4 = QueuedOrder(
            order=sample_order,
            priority=QueuePriority.NORMAL,
            queued_at=now,
        )
        assert (
            order3 < order4
        )  # Higher priority (lower number) should be higher priority

        # Different priority, different time
        order5 = QueuedOrder(
            order=sample_order,
            priority=QueuePriority.LOW,
            queued_at=now,
        )
        order6 = QueuedOrder(
            order=sample_order,
            priority=QueuePriority.NORMAL,
            queued_at=now + timedelta(seconds=10),
        )
        assert order6 < order5  # Priority should take precedence over time


class TestOrderQueue:
    """Tests for the OrderQueue class."""

    @pytest.mark.asyncio
    async def test_init(self):
        """Test OrderQueue initialization."""
        queue = OrderQueue(max_concurrent_workers=5)

        assert queue.max_workers == 5
        assert isinstance(queue.batch_config, BatchConfig)
        assert len(queue.priority_queue) == 0
        assert len(queue.processing_orders) == 0
        assert len(queue.completed_orders) == 0
        assert len(queue.workers) == 0
        assert queue.worker_semaphore._value == 5
        assert isinstance(queue.batch_queue, dict)
        assert queue.batch_timer_task is None
        assert queue.metrics is not None
        assert not queue.is_running
        assert not queue.is_draining
        assert isinstance(queue.order_processors, dict)
        assert len(queue.completion_callbacks) == 0

    @pytest.mark.asyncio
    async def test_start_stop(self, order_queue):
        """Test starting and stopping the order queue."""
        # Start the queue
        await order_queue.start()
        assert order_queue.is_running
        assert len(order_queue.workers) == 2  # max_concurrent_workers=2
        assert all(not worker.done() for worker in order_queue.workers)

        # Stop the queue
        await order_queue.stop(drain=False)
        assert not order_queue.is_running
        assert all(worker.done() for worker in order_queue.workers)
        assert len(order_queue.workers) == 0

    @pytest.mark.asyncio
    async def test_enqueue_order(self, order_queue, sample_order):
        """Test enqueueing an order."""
        # Start the queue
        await order_queue.start()

        # Mock the _process_order method to avoid actual processing
        order_queue._process_order = AsyncMock()

        try:
            # Enqueue an order
            queue_id = await order_queue.enqueue_order(
                sample_order, priority=QueuePriority.HIGH
            )

            # Verify the order was enqueued
            assert queue_id.startswith(f"queue_{sample_order.id}_")
            assert order_queue.metrics.total_enqueued == 1

            # Wait a bit for the order to be processed
            await asyncio.sleep(0.1)

            # Verify the order was processed
            assert order_queue._process_order.called

        finally:
            # Stop the queue
            await order_queue.stop(drain=False)

    @pytest.mark.asyncio
    async def test_enqueue_order_not_running(self, order_queue, sample_order):
        """Test enqueueing an order when the queue is not running."""
        # Try to enqueue an order - should raise an error
        with pytest.raises(RuntimeError):
            await order_queue.enqueue_order(sample_order)

    @pytest.mark.asyncio
    async def test_enqueue_batch(self, order_queue):
        """Test enqueueing a batch of orders."""
        # Start the queue
        await order_queue.start()

        # Mock the _process_order method to avoid actual processing
        order_queue._process_order = AsyncMock()

        try:
            # Create a batch of orders
            orders = [
                Order(
                    id=f"test-order-{i}",
                    symbol="AAPL",
                    order_type=OrderType.BUY,
                    quantity=100,
                    price=150.0,
                    created_at=datetime.utcnow(),
                )
                for i in range(3)
            ]

            # Enqueue the batch
            queue_ids = await order_queue.enqueue_batch(orders)

            # Verify the orders were enqueued
            assert len(queue_ids) == 3
            assert all(id.startswith("queue_test-order-") for id in queue_ids)
            assert order_queue.metrics.total_enqueued == 3

            # Wait a bit for the orders to be processed
            await asyncio.sleep(0.1)

            # Verify the orders were processed
            assert order_queue._process_order.call_count == 3

        finally:
            # Stop the queue
            await order_queue.stop(drain=False)

    @pytest.mark.asyncio
    async def test_register_processor(self, order_queue, sample_order):
        """Test registering a processor function."""
        # Start the queue
        await order_queue.start()

        try:
            # Create a mock processor
            processor = AsyncMock(return_value={"status": "success"})

            # Register the processor
            order_queue.register_processor(OrderType.BUY, processor)

            # Enqueue an order
            await order_queue.enqueue_order(sample_order)

            # Wait a bit for the order to be processed
            await asyncio.sleep(0.1)

            # Verify the processor was called
            processor.assert_called_once_with(sample_order)

        finally:
            # Stop the queue
            await order_queue.stop(drain=False)

    @pytest.mark.asyncio
    async def test_register_completion_callback(self, order_queue, sample_order):
        """Test registering a completion callback."""
        # Start the queue
        await order_queue.start()

        try:
            # Create a mock processor and callback
            processor = AsyncMock(return_value={"status": "success"})
            callback = AsyncMock()

            # Register the processor and callback
            order_queue.register_processor(OrderType.BUY, processor)
            order_queue.register_completion_callback(callback)

            # Enqueue an order
            await order_queue.enqueue_order(sample_order)

            # Wait a bit for the order to be processed
            await asyncio.sleep(0.1)

            # Verify the callback was called
            assert callback.called

        finally:
            # Stop the queue
            await order_queue.stop(drain=False)

    @pytest.mark.asyncio
    async def test_get_queue_status(self, order_queue, sample_order):
        """Test getting queue status."""
        # Start the queue
        await order_queue.start()

        # Mock the _process_order method to avoid actual processing
        order_queue._process_order = AsyncMock()

        try:
            # Enqueue an order
            await order_queue.enqueue_order(sample_order)

            # Get queue status
            status = await order_queue.get_queue_status()

            # Verify the status
            assert status["is_running"] is True
            assert status["is_draining"] is False
            assert status["total_enqueued"] == 1
            assert "queue_depth" in status
            assert "processing_orders" in status
            assert "completed_orders" in status
            assert "throughput_orders_per_sec" in status
            assert "avg_processing_time_ms" in status
            assert "avg_queue_wait_time_ms" in status
            assert "active_workers" in status

        finally:
            # Stop the queue
            await order_queue.stop(drain=False)

    @pytest.mark.asyncio
    async def test_worker_loop(self, order_queue, sample_order):
        """Test the worker loop."""
        # Start the queue
        await order_queue.start()

        try:
            # Create a mock processor
            processor = AsyncMock(return_value={"status": "success"})

            # Register the processor
            order_queue.register_processor(OrderType.BUY, processor)

            # Enqueue an order
            await order_queue.enqueue_order(sample_order)

            # Wait a bit for the order to be processed
            await asyncio.sleep(0.1)

            # Verify the processor was called
            processor.assert_called_once_with(sample_order)

            # Verify the order was moved to completed_orders
            assert sample_order.id in order_queue.completed_orders
            assert (
                order_queue.completed_orders[sample_order.id].status
                == ProcessingStatus.COMPLETED
            )

        finally:
            # Stop the queue
            await order_queue.stop(drain=False)

    @pytest.mark.asyncio
    async def test_process_order_error(self, order_queue, sample_order):
        """Test error handling in order processing."""
        # Start the queue
        await order_queue.start()

        try:
            # Create a processor that raises an error
            processor = AsyncMock(side_effect=Exception("Test error"))

            # Register the processor
            order_queue.register_processor(OrderType.BUY, processor)

            # Mock _requeue_after_delay to avoid actual requeuing
            order_queue._requeue_after_delay = AsyncMock()

            # Enqueue an order
            await order_queue.enqueue_order(sample_order)

            # Wait a bit for the order to be processed
            await asyncio.sleep(0.1)

            # Verify the processor was called
            processor.assert_called_once_with(sample_order)

            # Verify _requeue_after_delay was called
            order_queue._requeue_after_delay.assert_called_once()
            queued_order = order_queue._requeue_after_delay.call_args[0][0]
            assert queued_order.order.id == sample_order.id
            assert queued_order.status == ProcessingStatus.RETRYING
            assert queued_order.attempts == 1

        finally:
            # Stop the queue
            await order_queue.stop(drain=False)

    @pytest.mark.asyncio
    async def test_process_order_max_retries(self, order_queue, sample_order):
        """Test order processing with max retries exceeded."""
        # Start the queue
        await order_queue.start()

        try:
            # Create a processor that raises an error
            processor = AsyncMock(side_effect=Exception("Test error"))

            # Register the processor
            order_queue.register_processor(OrderType.BUY, processor)

            # Create a queued order with max_attempts reached
            queued_order = QueuedOrder(
                order=sample_order,
                priority=QueuePriority.NORMAL,
                queued_at=datetime.utcnow(),
                attempts=3,  # Already at max_attempts
                max_attempts=3,
            )

            # Process the order directly
            await order_queue._process_order(queued_order, 0)

            # Verify the order was marked as failed
            assert queued_order.status == ProcessingStatus.FAILED
            assert "error" in queued_order.metadata
            assert order_queue.metrics.total_failed == 1

        finally:
            # Stop the queue
            await order_queue.stop(drain=False)

    @pytest.mark.asyncio
    async def test_requeue_after_delay(self, order_queue, sample_order):
        """Test requeueing an order after a delay."""
        # Create a queued order
        queued_order = QueuedOrder(
            order=sample_order,
            priority=QueuePriority.NORMAL,
            queued_at=datetime.utcnow(),
            attempts=1,
        )

        # Mock asyncio.sleep to avoid actual delay
        with patch("asyncio.sleep", new_callable=AsyncMock) as mock_sleep:
            # Requeue the order
            await order_queue._requeue_after_delay(queued_order, 2.0)

            # Verify sleep was called with the correct delay
            mock_sleep.assert_called_once_with(2.0)

            # Verify the order was requeued
            assert queued_order in order_queue.priority_queue
            assert queued_order.status == ProcessingStatus.QUEUED
            assert order_queue.metrics.current_queue_depth == 1

    @pytest.mark.asyncio
    async def test_drain_queue(self, order_queue, sample_order):
        """Test draining the queue."""
        # Start the queue
        await order_queue.start()

        try:
            # Create a slow processor
            async def slow_processor(order):
                await asyncio.sleep(0.2)
                return {"status": "success"}

            # Register the processor
            order_queue.register_processor(OrderType.BUY, slow_processor)

            # Enqueue multiple orders
            for i in range(5):
                order = Order(
                    id=f"test-order-{i}",
                    symbol="AAPL",
                    order_type=OrderType.BUY,
                    quantity=100,
                    price=150.0,
                    created_at=datetime.utcnow(),
                )
                await order_queue.enqueue_order(order)

            # Mock asyncio.sleep to speed up the test
            original_sleep = asyncio.sleep
            with patch("asyncio.sleep", new_callable=AsyncMock) as mock_sleep:
                # Allow the first sleep call to proceed normally
                mock_sleep.side_effect = lambda t: original_sleep(0.01)

                # Drain the queue
                order_queue.is_draining = True
                await order_queue._drain_queue()

                # Verify the queue was drained
                assert len(order_queue.priority_queue) == 0
                assert len(order_queue.processing_orders) == 0

        finally:
            # Stop the queue
            await order_queue.stop(drain=False)

    @pytest.mark.asyncio
    async def test_force_process_order(self, order_queue, sample_order):
        """Test forcing immediate processing of an order."""
        # Start the queue
        await order_queue.start()

        # Mock the _process_order method to avoid actual processing
        order_queue._process_order = AsyncMock()

        try:
            # Enqueue an order
            await order_queue.enqueue_order(sample_order)

            # Force process the order
            result = await order_queue.force_process_order(sample_order.id)

            # Verify the result
            assert result is True
            assert order_queue._process_order.called

        finally:
            # Stop the queue
            await order_queue.stop(drain=False)

    @pytest.mark.asyncio
    async def test_cancel_order(self, order_queue, sample_order):
        """Test cancelling a queued order."""
        # Start the queue
        await order_queue.start()

        try:
            # Enqueue an order
            await order_queue.enqueue_order(sample_order)

            # Cancel the order
            result = await order_queue.cancel_order(sample_order.id)

            # Verify the result
            assert result is True
            assert len(order_queue.priority_queue) == 0
            assert order_queue.metrics.current_queue_depth == 0

        finally:
            # Stop the queue
            await order_queue.stop(drain=False)

    @pytest.mark.asyncio
    async def test_cancel_order_not_found(self, order_queue):
        """Test cancelling a non-existent order."""
        # Start the queue
        await order_queue.start()

        try:
            # Cancel a non-existent order
            result = await order_queue.cancel_order("non-existent-order")

            # Verify the result
            assert result is False

        finally:
            # Stop the queue
            await order_queue.stop(drain=False)

    def test_calculate_avg_processing_time(self, order_queue):
        """Test calculating average processing time."""
        # Add some processing times
        order_queue._processing_times = [10.0, 20.0, 30.0]

        # Calculate average
        avg_time = order_queue._calculate_avg_processing_time()

        # Verify the result
        assert avg_time == 20.0

    def test_calculate_avg_wait_time(self, order_queue):
        """Test calculating average wait time."""
        # Add some wait times
        order_queue._queue_wait_times = [5.0, 10.0, 15.0]

        # Calculate average
        avg_time = order_queue._calculate_avg_wait_time()

        # Verify the result
        assert avg_time == 10.0

    def test_reset_metrics(self, order_queue):
        """Test resetting metrics."""
        # Add some metrics
        order_queue.metrics.total_enqueued = 10
        order_queue.metrics.total_processed = 8
        order_queue.metrics.total_failed = 2
        order_queue._processing_times = [10.0, 20.0, 30.0]
        order_queue._queue_wait_times = [5.0, 10.0, 15.0]

        # Reset metrics
        order_queue.reset_metrics()

        # Verify the metrics were reset
        assert order_queue.metrics.total_enqueued == 0
        assert order_queue.metrics.total_processed == 0
        assert order_queue.metrics.total_failed == 0
        assert len(order_queue._processing_times) == 0
        assert len(order_queue._queue_wait_times) == 0
