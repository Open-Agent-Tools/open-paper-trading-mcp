"""
Async order queue management for high-throughput order processing.

This module provides efficient queuing and processing of orders with
priority handling, batch processing, and flow control mechanisms.
"""

import asyncio
import contextlib
import heapq
import logging
from collections import defaultdict
from collections.abc import Callable
from dataclasses import dataclass, field
from datetime import datetime, UTC
from enum import Enum, IntEnum
from typing import Any

from ..schemas.orders import Order, OrderType

logger = logging.getLogger(__name__)


class QueuePriority(IntEnum):
    """Order queue priorities (lower number = higher priority)."""

    URGENT = 1  # Market close, expiration, etc.
    HIGH = 2  # Stop orders, triggered orders
    NORMAL = 3  # Regular market orders
    LOW = 4  # Limit orders, GTC orders
    BATCH = 5  # Batch processing orders


class ProcessingStatus(str, Enum):
    """Order processing status in queue."""

    QUEUED = "queued"
    PROCESSING = "processing"
    COMPLETED = "completed"
    FAILED = "failed"
    RETRYING = "retrying"


@dataclass
class QueuedOrder:
    """Order wrapper for queue processing."""

    order: Order
    priority: QueuePriority
    queued_at: datetime
    attempts: int = 0
    max_attempts: int = 3
    status: ProcessingStatus = ProcessingStatus.QUEUED
    metadata: dict[str, Any] = field(default_factory=dict)
    callback: Callable[..., Any] | None = None

    def __lt__(self, other: "QueuedOrder") -> bool:
        """Priority comparison for heap queue."""
        if self.priority != other.priority:
            return self.priority < other.priority
        return self.queued_at < other.queued_at


@dataclass
class BatchConfig:
    """Configuration for batch processing."""

    max_batch_size: int = 10
    max_wait_time_ms: int = 100
    enable_batching: bool = True
    batch_by_symbol: bool = True


@dataclass
class QueueMetrics:
    """Queue performance metrics."""

    total_enqueued: int = 0
    total_processed: int = 0
    total_failed: int = 0
    current_queue_depth: int = 0
    avg_processing_time_ms: float = 0
    avg_queue_wait_time_ms: float = 0
    throughput_orders_per_sec: float = 0
    last_reset: datetime = field(default_factory=datetime.utcnow)


class OrderQueue:
    """
    High-performance async order queue with priority handling.

    Features:
    - Priority-based order processing
    - Batch processing for efficiency
    - Automatic retry with backoff
    - Flow control and rate limiting
    - Comprehensive metrics and monitoring
    """

    def __init__(
        self,
        max_concurrent_workers: int = 10,
        batch_config: BatchConfig | None = None,
    ):
        self.max_workers = max_concurrent_workers
        self.batch_config = batch_config or BatchConfig()

        # Queue storage
        self.priority_queue: list[QueuedOrder] = []
        self.processing_orders: dict[str, QueuedOrder] = {}
        self.completed_orders: dict[str, QueuedOrder] = {}

        # Worker management
        self.workers: set[asyncio.Task[None]] = set()
        self.worker_semaphore = asyncio.Semaphore(max_concurrent_workers)

        # Batch processing
        self.batch_queue: dict[str, list[QueuedOrder]] = defaultdict(list)
        self.batch_timer_task: asyncio.Task[None] | None = None

        # Metrics
        self.metrics = QueueMetrics()
        self._processing_times: list[float] = []
        self._queue_wait_times: list[float] = []

        # Control flags
        self.is_running = False
        self.is_draining = False

        # Callbacks
        self.order_processors: dict[OrderType, Callable[..., Any]] = {}
        self.completion_callbacks: list[Callable[..., Any]] = []

        # Thread safety
        self._queue_lock = asyncio.Lock()

    async def start(self) -> None:
        """Start the order queue processing."""
        if self.is_running:
            logger.warning("Order queue is already running")
            return

        self.is_running = True

        # Start worker tasks
        for i in range(self.max_workers):
            worker_task = asyncio.create_task(self._worker_loop(i))
            self.workers.add(worker_task)

        # Start batch processing timer if enabled
        if self.batch_config.enable_batching:
            self.batch_timer_task = asyncio.create_task(self._batch_timer_loop())

        logger.info(f"Order queue started with {self.max_workers} workers")

    async def stop(self, drain: bool = True) -> None:
        """Stop the order queue processing."""
        if not self.is_running:
            return

        logger.info("Stopping order queue...")

        if drain:
            self.is_draining = True
            await self._drain_queue()

        self.is_running = False

        # Cancel all worker tasks
        for worker in self.workers:
            worker.cancel()

        if self.workers:
            await asyncio.gather(*self.workers, return_exceptions=True)
        self.workers.clear()

        # Cancel batch timer
        if self.batch_timer_task:
            self.batch_timer_task.cancel()
            with contextlib.suppress(asyncio.CancelledError):
                await self.batch_timer_task

        logger.info("Order queue stopped")

    async def enqueue_order(
        self,
        order: Order,
        priority: QueuePriority = QueuePriority.NORMAL,
        callback: Callable[..., Any] | None = None,
        metadata: dict[str, Any] | None = None,
    ) -> str:
        """
        Add an order to the processing queue.

        Args:
            order: Order to process
            priority: Processing priority
            callback: Optional completion callback
            metadata: Additional metadata

        Returns:
            Queue entry ID for tracking
        """
        if not self.is_running:
            raise RuntimeError("Order queue is not running")

        if self.is_draining:
            raise RuntimeError("Order queue is draining, not accepting new orders")

        queued_order = QueuedOrder(
            order=order,
            priority=priority,
            queued_at=datetime.now(UTC),
            callback=callback,
            metadata=metadata or {},
        )

        async with self._queue_lock:
            heapq.heappush(self.priority_queue, queued_order)
            self.metrics.total_enqueued += 1
            self.metrics.current_queue_depth += 1

        logger.debug(f"Enqueued order {order.id} with priority {priority.name}")
        return f"queue_{order.id}_{int(queued_order.queued_at.timestamp())}"

    async def enqueue_batch(
        self, orders: list[Order], priority: QueuePriority = QueuePriority.BATCH
    ) -> list[str]:
        """Enqueue multiple orders as a batch."""
        queue_ids = []

        for order in orders:
            queue_id = await self.enqueue_order(order, priority)
            queue_ids.append(queue_id)

        logger.info(f"Enqueued batch of {len(orders)} orders")
        return queue_ids

    def register_processor(
        self, order_type: OrderType, processor: Callable[[Order], Any]
    ) -> None:
        """Register a processor function for a specific order type."""
        self.order_processors[order_type] = processor
        logger.info(f"Registered processor for {order_type}")

    def register_completion_callback(self, callback: Callable[..., Any]) -> None:
        """Register a callback for order completion events."""
        self.completion_callbacks.append(callback)

    async def get_queue_status(self) -> dict[str, Any]:
        """Get current queue status and metrics."""
        async with self._queue_lock:
            queue_depth = len(self.priority_queue)
            processing_count = len(self.processing_orders)

        # Calculate recent throughput
        recent_processed = self.metrics.total_processed
        time_elapsed = (datetime.now(UTC) - self.metrics.last_reset).total_seconds()
        throughput = recent_processed / time_elapsed if time_elapsed > 0 else 0

        return {
            "is_running": self.is_running,
            "is_draining": self.is_draining,
            "queue_depth": queue_depth,
            "processing_orders": processing_count,
            "completed_orders": len(self.completed_orders),
            "total_enqueued": self.metrics.total_enqueued,
            "total_processed": self.metrics.total_processed,
            "total_failed": self.metrics.total_failed,
            "throughput_orders_per_sec": throughput,
            "avg_processing_time_ms": self._calculate_avg_processing_time(),
            "avg_queue_wait_time_ms": self._calculate_avg_wait_time(),
            "active_workers": len([w for w in self.workers if not w.done()]),
        }

    async def _worker_loop(self, worker_id: int) -> None:
        """Main worker loop for processing orders."""
        logger.info(f"Worker {worker_id} started")

        while self.is_running or (self.is_draining and len(self.priority_queue) > 0):
            try:
                async with self.worker_semaphore:
                    # Get next order from queue
                    queued_order = await self._get_next_order()

                    if queued_order is None:
                        # No orders available, wait a bit
                        await asyncio.sleep(0.01)
                        continue

                    # Process the order
                    await self._process_order(queued_order, worker_id)

            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"Error in worker {worker_id}: {e}", exc_info=True)
                await asyncio.sleep(1)  # Brief pause on error

        logger.info(f"Worker {worker_id} stopped")

    async def _get_next_order(self) -> QueuedOrder | None:
        """Get the next order from the priority queue."""
        async with self._queue_lock:
            if self.priority_queue:
                queued_order = heapq.heappop(self.priority_queue)
                self.metrics.current_queue_depth -= 1

                # Track in processing
                if queued_order.order.id:
                    self.processing_orders[queued_order.order.id] = queued_order

                queued_order.status = ProcessingStatus.PROCESSING

                # Calculate queue wait time
                wait_time = (
                    datetime.now(UTC) - queued_order.queued_at
                ).total_seconds() * 1000
                self._queue_wait_times.append(wait_time)
                if len(self._queue_wait_times) > 1000:
                    self._queue_wait_times = self._queue_wait_times[-500:]

                return queued_order

        return None

    async def _process_order(self, queued_order: QueuedOrder, worker_id: int) -> None:
        """Process a single order."""
        start_time = datetime.now(UTC)

        try:
            # Find appropriate processor
            processor = self.order_processors.get(queued_order.order.order_type)

            if processor is None:
                raise ValueError(
                    f"No processor registered for order type {queued_order.order.order_type}"
                )

            # Execute processor
            if asyncio.iscoroutinefunction(processor):
                result = await processor(queued_order.order)
            else:
                result = processor(queued_order.order)

            # Mark as completed
            queued_order.status = ProcessingStatus.COMPLETED
            queued_order.metadata["result"] = result
            queued_order.metadata["processed_by_worker"] = worker_id

            # Update metrics
            self.metrics.total_processed += 1

            # Call completion callback if provided
            if queued_order.callback:
                try:
                    if asyncio.iscoroutinefunction(queued_order.callback):
                        await queued_order.callback(queued_order.order, result, None)
                    else:
                        queued_order.callback(queued_order.order, result, None)
                except Exception as e:
                    logger.error(f"Error in order callback: {e}")

            logger.debug(f"Successfully processed order {queued_order.order.id}")

        except Exception as e:
            # Handle processing error
            queued_order.attempts += 1

            if queued_order.attempts < queued_order.max_attempts:
                # Retry with exponential backoff
                queued_order.status = ProcessingStatus.RETRYING
                delay = 2**queued_order.attempts  # 2, 4, 8 seconds

                logger.warning(
                    f"Order {queued_order.order.id} failed, retrying in {delay}s (attempt {queued_order.attempts})"
                )

                # Re-queue after delay
                asyncio.create_task(self._requeue_after_delay(queued_order, delay))
            else:
                # Max retries exceeded
                queued_order.status = ProcessingStatus.FAILED
                queued_order.metadata["error"] = str(e)

                self.metrics.total_failed += 1

                logger.error(
                    f"Order {queued_order.order.id} failed permanently after {queued_order.attempts} attempts: {e}"
                )

                # Call error callback if provided
                if queued_order.callback:
                    try:
                        if asyncio.iscoroutinefunction(queued_order.callback):
                            await queued_order.callback(queued_order.order, None, e)
                        else:
                            queued_order.callback(queued_order.order, None, e)
                    except Exception as callback_error:
                        logger.error(f"Error in error callback: {callback_error}")

        finally:
            # Clean up processing tracking
            if queued_order.order.id in self.processing_orders:
                del self.processing_orders[queued_order.order.id]

            # Store completed order for history
            if queued_order.order.id:
                self.completed_orders[queued_order.order.id] = queued_order

            # Update processing time metrics
            processing_time = (datetime.now(UTC) - start_time).total_seconds() * 1000
            self._processing_times.append(processing_time)
            if len(self._processing_times) > 1000:
                self._processing_times = self._processing_times[-500:]

            # Trigger completion callbacks
            for callback in self.completion_callbacks:
                try:
                    if asyncio.iscoroutinefunction(callback):
                        await callback(queued_order)
                    else:
                        callback(queued_order)
                except Exception as e:
                    logger.error(f"Error in completion callback: {e}")

    async def _requeue_after_delay(
        self, queued_order: QueuedOrder, delay: float
    ) -> None:
        """Re-queue an order after a delay for retry."""
        await asyncio.sleep(delay)

        # Reset status and re-queue
        queued_order.status = ProcessingStatus.QUEUED
        queued_order.queued_at = datetime.now(UTC)

        async with self._queue_lock:
            heapq.heappush(self.priority_queue, queued_order)
            self.metrics.current_queue_depth += 1

    async def _batch_timer_loop(self) -> None:
        """Timer loop for batch processing."""
        logger.info("Batch timer started")

        while self.is_running:
            try:
                await asyncio.sleep(self.batch_config.max_wait_time_ms / 1000.0)
                await self._process_pending_batches()
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"Error in batch timer: {e}", exc_info=True)

        logger.info("Batch timer stopped")

    async def _process_pending_batches(self) -> None:
        """Process any pending batches that have reached time limit."""
        if not self.batch_config.enable_batching:
            return

        # This is a simplified implementation
        # In practice, would need more sophisticated batch management
        pass

    async def _drain_queue(self) -> None:
        """Wait for all queued orders to be processed."""
        logger.info("Draining order queue...")

        while True:
            async with self._queue_lock:
                queue_empty = len(self.priority_queue) == 0
                processing_empty = len(self.processing_orders) == 0

            if queue_empty and processing_empty:
                break

            await asyncio.sleep(0.1)

        logger.info("Queue drained successfully")

    def _calculate_avg_processing_time(self) -> float:
        """Calculate average processing time."""
        if self._processing_times:
            return sum(self._processing_times) / len(self._processing_times)
        return 0.0

    def _calculate_avg_wait_time(self) -> float:
        """Calculate average queue wait time."""
        if self._queue_wait_times:
            return sum(self._queue_wait_times) / len(self._queue_wait_times)
        return 0.0

    def reset_metrics(self) -> None:
        """Reset performance metrics."""
        self.metrics = QueueMetrics()
        self._processing_times.clear()
        self._queue_wait_times.clear()

    async def force_process_order(self, order_id: str) -> bool:
        """Force immediate processing of a specific order."""
        async with self._queue_lock:
            # Find order in queue
            for i, queued_order in enumerate(self.priority_queue):
                if queued_order.order.id == order_id:
                    # Remove from queue and process immediately
                    self.priority_queue.pop(i)
                    heapq.heapify(self.priority_queue)  # Re-heapify
                    self.metrics.current_queue_depth -= 1

                    # Process in background task
                    asyncio.create_task(self._process_order(queued_order, -1))
                    return True

        return False

    async def cancel_order(self, order_id: str) -> bool:
        """Cancel a queued order."""
        async with self._queue_lock:
            # Find and remove from queue
            for i, queued_order in enumerate(self.priority_queue):
                if queued_order.order.id == order_id:
                    self.priority_queue.pop(i)
                    heapq.heapify(self.priority_queue)
                    self.metrics.current_queue_depth -= 1

                    queued_order.status = ProcessingStatus.FAILED
                    queued_order.metadata["cancelled"] = True

                    logger.info(f"Cancelled queued order {order_id}")
                    return True

        return False


# Global order queue instance
order_queue: OrderQueue | None = None


def get_order_queue() -> OrderQueue:
    """Get the global order queue instance."""
    if order_queue is None:
        raise RuntimeError("Order queue not initialized")
    return order_queue


def initialize_order_queue(
    max_workers: int = 10, batch_config: BatchConfig | None = None
) -> OrderQueue:
    """Initialize the global order queue."""
    global order_queue
    order_queue = OrderQueue(max_workers, batch_config)
    return order_queue
