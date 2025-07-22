"""
Performance tests for high-volume order processing.

This module tests system performance under high load conditions
including throughput, latency, and resource utilization.
"""

import asyncio
import gc
import time
from datetime import datetime
from unittest.mock import AsyncMock, Mock

import psutil
import pytest

from app.schemas.orders import Order, OrderStatus, OrderType
from app.services.order_execution_engine import OrderExecutionEngine
from app.services.order_queue import BatchConfig, OrderQueue, QueuePriority
from app.services.order_state_tracker import (
    MemoryEfficientOrderTracker,
    OrderStateTrackingConfig,
    StateChangeEvent,
)
from app.services.performance_benchmarks import PerformanceMonitor


class PerformanceTestConfig:
    """Configuration for performance tests."""

    HIGH_VOLUME_ORDER_COUNT = 1000
    STRESS_TEST_ORDER_COUNT = 5000
    CONCURRENT_WORKERS = 20
    MAX_LATENCY_MS = 100.0
    MIN_THROUGHPUT_OPS_SEC = 50.0
    MAX_MEMORY_MB = 100.0


@pytest.fixture
def performance_monitor():
    """Create performance monitor for testing."""
    return PerformanceMonitor()


@pytest.fixture
def mock_trading_service():
    """High-performance mock trading service."""
    service = AsyncMock()

    # Fast quote responses
    service.get_current_quote = AsyncMock(
        return_value=Mock(price=150.00, bid=149.95, ask=150.05)
    )

    # Fast execution simulation
    async def fast_execute(order):
        await asyncio.sleep(0.001)  # 1ms execution time
        return True

    service.execute_order = fast_execute
    return service


@pytest.fixture
async def high_performance_queue():
    """Create high-performance order queue."""
    config = BatchConfig(
        max_batch_size=50,
        max_wait_time_ms=10,
        enable_batching=True,
        batch_by_symbol=True,
    )

    queue = OrderQueue(max_concurrent_workers=20, batch_config=config)
    await queue.start()

    yield queue

    await queue.stop()


@pytest.fixture
async def memory_efficient_tracker():
    """Create memory-efficient state tracker."""
    config = OrderStateTrackingConfig(
        max_snapshots_per_order=20,
        max_total_snapshots=50000,
        max_history_days=1,
        cleanup_interval_minutes=1,
        enable_metrics=True,
    )

    tracker = MemoryEfficientOrderTracker(config)
    await tracker.start()

    yield tracker

    await tracker.stop()


class TestHighVolumeOrderProcessing:
    """Test high-volume order processing performance."""

    @pytest.mark.asyncio
    async def test_high_throughput_order_processing(
        self, high_performance_queue, performance_monitor
    ):
        """Test processing high volume of orders."""
        print("\n🚀 Testing high-throughput order processing...")

        order_count = PerformanceTestConfig.HIGH_VOLUME_ORDER_COUNT
        start_time = time.perf_counter()

        # Create orders
        orders = []
        for i in range(order_count):
            order = Order(
                id=f"perf_test_{i}",
                symbol=f"STOCK{i % 10}",  # 10 different symbols
                order_type=OrderType.BUY if i % 2 == 0 else OrderType.SELL,
                quantity=100 + (i % 100),
                price=100.0 + (i % 50),
                status=OrderStatus.PENDING,
                created_at=datetime.utcnow(),
            )
            orders.append(order)

        # Register fast processor
        processed_orders = []

        async def fast_processor(order):
            measurement_id = performance_monitor.start_measurement("order_processing")
            try:
                await asyncio.sleep(0.001)  # Simulate 1ms processing
                processed_orders.append(order.id)
                return {"processed": True, "order_id": order.id}
            finally:
                performance_monitor.end_measurement(measurement_id, success=True)

        high_performance_queue.register_processor(OrderType.BUY, fast_processor)
        high_performance_queue.register_processor(OrderType.SELL, fast_processor)

        # Enqueue all orders
        queue_start = time.perf_counter()

        enqueue_tasks = []
        for order in orders:
            priority = (
                QueuePriority.HIGH
                if order.order_type == OrderType.SELL
                else QueuePriority.NORMAL
            )
            task = high_performance_queue.enqueue_order(order, priority)
            enqueue_tasks.append(task)

        # Wait for all enqueues to complete
        await asyncio.gather(*enqueue_tasks)
        queue_time = time.perf_counter() - queue_start

        # Wait for processing to complete
        processing_start = time.perf_counter()

        while len(processed_orders) < order_count:
            await asyncio.sleep(0.1)
            queue_status = await high_performance_queue.get_queue_status()
            if (
                queue_status["queue_depth"] == 0
                and queue_status["processing_orders"] == 0
            ):
                break

        processing_time = time.perf_counter() - processing_start
        total_time = time.perf_counter() - start_time

        # Calculate metrics
        throughput = order_count / total_time
        queue_throughput = order_count / queue_time if queue_time > 0 else float("inf")
        processing_throughput = (
            len(processed_orders) / processing_time
            if processing_time > 0
            else float("inf")
        )

        # Get performance stats
        stats = performance_monitor.get_current_stats("order_processing")

        print("📊 Performance Results:")
        print(f"   Orders processed: {len(processed_orders)}/{order_count}")
        print(f"   Total time: {total_time:.3f}s")
        print(f"   Queue time: {queue_time:.3f}s")
        print(f"   Processing time: {processing_time:.3f}s")
        print(f"   Overall throughput: {throughput:.1f} orders/sec")
        print(f"   Queue throughput: {queue_throughput:.1f} orders/sec")
        print(f"   Processing throughput: {processing_throughput:.1f} orders/sec")

        if stats:
            print(f"   Avg latency: {stats.get('avg_latency_ms', 0):.2f}ms")
            print(f"   Max latency: {stats.get('max_latency_ms', 0):.2f}ms")

        # Verify performance requirements
        assert len(processed_orders) == order_count, "Not all orders were processed"
        assert (
            throughput >= PerformanceTestConfig.MIN_THROUGHPUT_OPS_SEC
        ), f"Throughput {throughput:.1f} below minimum {PerformanceTestConfig.MIN_THROUGHPUT_OPS_SEC}"

        if stats:
            avg_latency = stats.get("avg_latency_ms", 0)
            assert (
                avg_latency <= PerformanceTestConfig.MAX_LATENCY_MS
            ), f"Average latency {avg_latency:.2f}ms exceeds maximum {PerformanceTestConfig.MAX_LATENCY_MS}ms"

    @pytest.mark.asyncio
    async def test_concurrent_order_execution(
        self, mock_trading_service, performance_monitor
    ):
        """Test concurrent order execution performance."""
        print("\n⚡ Testing concurrent order execution...")

        execution_engine = OrderExecutionEngine(mock_trading_service)
        await execution_engine.start()

        try:
            order_count = 500
            concurrent_orders = []

            # Create mixed order types
            for i in range(order_count):
                if i % 3 == 0:
                    # Stop loss order
                    order = Order(
                        id=f"concurrent_stop_{i}",
                        symbol=f"STOCK{i % 5}",
                        order_type=OrderType.STOP_LOSS,
                        quantity=100,
                        stop_price=90.0 + (i % 20),
                        status=OrderStatus.PENDING,
                        created_at=datetime.utcnow(),
                    )
                elif i % 3 == 1:
                    # Trailing stop order
                    order = Order(
                        id=f"concurrent_trail_{i}",
                        symbol=f"STOCK{i % 5}",
                        order_type=OrderType.TRAILING_STOP,
                        quantity=200,
                        trail_percent=5.0,
                        stop_price=95.0 + (i % 10),
                        status=OrderStatus.PENDING,
                        created_at=datetime.utcnow(),
                    )
                else:
                    # Stop limit order
                    order = Order(
                        id=f"concurrent_limit_{i}",
                        symbol=f"STOCK{i % 5}",
                        order_type=OrderType.STOP_LIMIT,
                        quantity=150,
                        price=110.0 + (i % 15),
                        stop_price=100.0 + (i % 15),
                        status=OrderStatus.PENDING,
                        created_at=datetime.utcnow(),
                    )

                concurrent_orders.append(order)

            # Add all orders to execution engine
            start_time = time.perf_counter()

            for order in concurrent_orders:
                execution_engine.add_trigger_order(order)

            # Simulate market conditions that trigger orders
            trigger_tasks = []
            for symbol in [f"STOCK{i}" for i in range(5)]:
                # Create tasks to trigger orders
                task = execution_engine._check_trigger_conditions(
                    symbol, 80.0
                )  # Price that triggers stops
                trigger_tasks.append(task)

            # Execute all triggers concurrently
            await asyncio.gather(*trigger_tasks, return_exceptions=True)

            execution_time = time.perf_counter() - start_time

            # Calculate performance metrics
            throughput = len(concurrent_orders) / execution_time

            print("📊 Concurrent Execution Results:")
            print(f"   Orders processed: {len(concurrent_orders)}")
            print(f"   Execution time: {execution_time:.3f}s")
            print(f"   Throughput: {throughput:.1f} orders/sec")
            print(
                f"   Execution calls: {mock_trading_service.execute_order.call_count}"
            )

            # Verify some orders were triggered
            assert (
                mock_trading_service.execute_order.call_count > 0
            ), "No orders were executed"

        finally:
            await execution_engine.stop()

    @pytest.mark.asyncio
    async def test_memory_usage_under_load(
        self, memory_efficient_tracker, performance_monitor
    ):
        """Test memory usage under high load."""
        print("\n💾 Testing memory usage under load...")

        # Get initial memory usage
        process = psutil.Process()
        initial_memory_mb = process.memory_info().rss / 1024 / 1024

        order_count = 2000
        state_changes_per_order = 5

        start_time = time.perf_counter()

        # Create many orders with multiple state changes
        for i in range(order_count):
            order_id = f"memory_test_{i}"
            symbol = f"STOCK{i % 20}"

            # Track multiple state changes per order
            for j in range(state_changes_per_order):
                if j == 0:
                    event = StateChangeEvent.CREATED
                    status = OrderStatus.PENDING
                elif j == 1:
                    event = StateChangeEvent.SUBMITTED
                    status = OrderStatus.PENDING
                elif j == 2:
                    event = StateChangeEvent.TRIGGERED
                    status = OrderStatus.TRIGGERED
                elif j == 3:
                    event = StateChangeEvent.PARTIALLY_FILLED
                    status = OrderStatus.PARTIALLY_FILLED
                else:
                    event = StateChangeEvent.FILLED
                    status = OrderStatus.FILLED

                memory_efficient_tracker.track_state_change(
                    order_id,
                    status,
                    event,
                    symbol=symbol,
                    quantity=100 + j,
                    metadata={"iteration": i, "change": j},
                )

        tracking_time = time.perf_counter() - start_time

        # Get memory after load
        peak_memory_mb = process.memory_info().rss / 1024 / 1024
        memory_increase_mb = peak_memory_mb - initial_memory_mb

        # Get tracker metrics
        metrics = memory_efficient_tracker.get_performance_metrics()

        # Force garbage collection
        gc.collect()
        final_memory_mb = process.memory_info().rss / 1024 / 1024

        print("📊 Memory Usage Results:")
        print(f"   Orders tracked: {order_count}")
        print(f"   State changes: {order_count * state_changes_per_order}")
        print(f"   Tracking time: {tracking_time:.3f}s")
        print(f"   Initial memory: {initial_memory_mb:.1f} MB")
        print(f"   Peak memory: {peak_memory_mb:.1f} MB")
        print(f"   Memory increase: {memory_increase_mb:.1f} MB")
        print(f"   Final memory (after GC): {final_memory_mb:.1f} MB")
        print(f"   Tracker estimated usage: {metrics['memory_usage_kb']:.1f} KB")
        print(f"   Total snapshots: {metrics['total_snapshots']}")
        print(f"   Avg snapshots per order: {metrics['avg_snapshots_per_order']:.1f}")

        # Verify memory efficiency
        assert (
            memory_increase_mb <= PerformanceTestConfig.MAX_MEMORY_MB
        ), f"Memory usage {memory_increase_mb:.1f}MB exceeds limit {PerformanceTestConfig.MAX_MEMORY_MB}MB"

        # Verify tracker bounds are respected
        assert (
            metrics["total_snapshots"]
            <= memory_efficient_tracker.config.max_total_snapshots
        )

        # Test cleanup effectiveness
        cleanup_start = time.perf_counter()
        cleanup_results = memory_efficient_tracker.cleanup_old_data(force=True)
        cleanup_time = time.perf_counter() - cleanup_start

        post_cleanup_memory_mb = process.memory_info().rss / 1024 / 1024

        print(f"   Cleanup time: {cleanup_time:.3f}s")
        print(f"   Orders cleaned: {cleanup_results['orders_cleaned']}")
        print(f"   Snapshots removed: {cleanup_results['snapshots_removed']}")
        print(f"   Memory after cleanup: {post_cleanup_memory_mb:.1f} MB")


class TestStressTestScenarios:
    """Stress test scenarios for extreme conditions."""

    @pytest.mark.asyncio
    async def test_burst_order_processing(
        self, high_performance_queue, performance_monitor
    ):
        """Test system handling of burst order loads."""
        print("\n💥 Testing burst order processing...")

        # Register processor
        async def burst_processor(order):
            measurement_id = performance_monitor.start_measurement("burst_processing")
            try:
                await asyncio.sleep(0.002)  # 2ms processing
                return {"processed": True}
            finally:
                performance_monitor.end_measurement(measurement_id, success=True)

        high_performance_queue.register_processor(OrderType.BUY, burst_processor)

        # Create burst loads with pauses
        burst_sizes = [100, 200, 500, 100, 50]  # Variable burst sizes
        total_processed = 0

        for burst_idx, burst_size in enumerate(burst_sizes):
            print(f"   Processing burst {burst_idx + 1}: {burst_size} orders...")

            burst_start = time.perf_counter()

            # Create burst of orders
            burst_orders = []
            for i in range(burst_size):
                order = Order(
                    id=f"burst_{burst_idx}_{i}",
                    symbol=f"BURST{i % 5}",
                    order_type=OrderType.BUY,
                    quantity=100,
                    price=100.0,
                    status=OrderStatus.PENDING,
                    created_at=datetime.utcnow(),
                )
                burst_orders.append(order)

            # Enqueue burst
            enqueue_tasks = [
                high_performance_queue.enqueue_order(order, QueuePriority.HIGH)
                for order in burst_orders
            ]
            await asyncio.gather(*enqueue_tasks)

            # Wait for burst to complete
            while True:
                await asyncio.sleep(0.1)
                status = await high_performance_queue.get_queue_status()
                if status["queue_depth"] == 0 and status["processing_orders"] == 0:
                    break

            burst_time = time.perf_counter() - burst_start
            burst_throughput = burst_size / burst_time
            total_processed += burst_size

            print(
                f"      Completed in {burst_time:.3f}s ({burst_throughput:.1f} orders/sec)"
            )

            # Brief pause between bursts
            if burst_idx < len(burst_sizes) - 1:
                await asyncio.sleep(0.2)

        # Final metrics
        queue_status = await high_performance_queue.get_queue_status()
        stats = performance_monitor.get_current_stats("burst_processing")

        print("📊 Burst Processing Results:")
        print(f"   Total bursts: {len(burst_sizes)}")
        print(f"   Total orders: {total_processed}")
        print(f"   Orders processed: {queue_status['total_processed']}")

        if stats:
            print(f"   Avg latency: {stats.get('avg_latency_ms', 0):.2f}ms")
            print(f"   P95 latency: {stats.get('p95_latency_ms', 0):.2f}ms")

        assert (
            queue_status["total_processed"] == total_processed
        ), "Not all orders processed"

    @pytest.mark.asyncio
    @pytest.mark.slow
    async def test_extended_load_stability(
        self, memory_efficient_tracker, performance_monitor
    ):
        """Test system stability under extended load."""
        print("\n⏱️  Testing extended load stability...")

        duration_seconds = 30  # 30-second test
        orders_per_second = 20

        start_time = time.perf_counter()
        total_orders = 0
        error_count = 0

        # Run continuous load
        while (time.perf_counter() - start_time) < duration_seconds:
            batch_start = time.perf_counter()

            # Create batch of orders
            try:
                for i in range(orders_per_second):
                    order_id = f"stability_{total_orders}_{i}"

                    memory_efficient_tracker.track_state_change(
                        order_id,
                        OrderStatus.PENDING,
                        StateChangeEvent.CREATED,
                        symbol=f"STOCK{i % 10}",
                        quantity=100,
                    )

                    # Random state progression
                    if i % 3 == 0:
                        memory_efficient_tracker.track_state_change(
                            order_id, OrderStatus.FILLED, StateChangeEvent.FILLED
                        )

                total_orders += orders_per_second

            except Exception as e:
                error_count += 1
                print(f"Error in batch: {e}")

            # Maintain rate
            batch_time = time.perf_counter() - batch_start
            sleep_time = max(0, 1.0 - batch_time)
            if sleep_time > 0:
                await asyncio.sleep(sleep_time)

        total_time = time.perf_counter() - start_time

        # Get final metrics
        metrics = memory_efficient_tracker.get_performance_metrics()

        print("📊 Extended Load Results:")
        print(f"   Duration: {total_time:.1f}s")
        print(f"   Total orders: {total_orders}")
        print(f"   Errors: {error_count}")
        print(f"   Average rate: {total_orders / total_time:.1f} orders/sec")
        print(f"   Error rate: {error_count / total_orders * 100:.2f}%")
        print(f"   Final memory usage: {metrics['memory_usage_kb']:.1f} KB")
        print(f"   Active orders: {metrics['active_orders']}")

        # Verify stability
        assert (
            error_count <= total_orders * 0.01
        ), f"Error rate {error_count / total_orders * 100:.2f}% too high"
        assert metrics["active_orders"] > 0, "No orders tracked"


@pytest.mark.asyncio
async def test_benchmark_comparison():
    """Compare performance across different configurations."""
    print("\n🏁 Running benchmark comparison...")

    configurations = [
        {"workers": 5, "batch_size": 10, "name": "Conservative"},
        {"workers": 10, "batch_size": 25, "name": "Balanced"},
        {"workers": 20, "batch_size": 50, "name": "Aggressive"},
    ]

    results = []

    for config in configurations:
        print(f"   Testing {config['name']} configuration...")

        # Create queue with specific config
        batch_config = BatchConfig(
            max_batch_size=config["batch_size"],
            max_wait_time_ms=10,
            enable_batching=True,
        )

        queue = OrderQueue(
            max_concurrent_workers=config["workers"], batch_config=batch_config
        )

        await queue.start()

        try:
            # Test orders
            test_orders = []
            order_count = 500

            for i in range(order_count):
                order = Order(
                    id=f"benchmark_{config['name']}_{i}",
                    symbol=f"STOCK{i % 10}",
                    order_type=OrderType.BUY,
                    quantity=100,
                    status=OrderStatus.PENDING,
                    created_at=datetime.utcnow(),
                )
                test_orders.append(order)

            # Register processor
            processed = []

            async def benchmark_processor(order):
                await asyncio.sleep(0.001)  # 1ms processing
                processed.append(order.id)
                return {"processed": True}

            queue.register_processor(OrderType.BUY, benchmark_processor)

            # Time the processing
            start_time = time.perf_counter()

            # Enqueue orders
            for order in test_orders:
                await queue.enqueue_order(order, QueuePriority.NORMAL)

            # Wait for completion
            while len(processed) < order_count:
                await asyncio.sleep(0.1)
                status = await queue.get_queue_status()
                if status["queue_depth"] == 0 and status["processing_orders"] == 0:
                    break

            processing_time = time.perf_counter() - start_time
            throughput = len(processed) / processing_time

            results.append(
                {
                    "config": config["name"],
                    "workers": config["workers"],
                    "batch_size": config["batch_size"],
                    "orders_processed": len(processed),
                    "time": processing_time,
                    "throughput": throughput,
                }
            )

            print(
                f"      {len(processed)} orders in {processing_time:.3f}s ({throughput:.1f} orders/sec)"
            )

        finally:
            await queue.stop()

    # Print comparison
    print("\n📊 Benchmark Comparison:")
    print(
        f"{'Configuration':<12} {'Workers':<8} {'Batch':<6} {'Throughput':<12} {'Time':<8}"
    )
    print("-" * 50)

    for result in results:
        print(
            f"{result['config']:<12} {result['workers']:<8} {result['batch_size']:<6} {result['throughput']:<12.1f} {result['time']:<8.3f}"
        )

    # Find best performer
    best_config = max(results, key=lambda x: x["throughput"])
    print(
        f"\n🏆 Best performer: {best_config['config']} ({best_config['throughput']:.1f} orders/sec)"
    )


if __name__ == "__main__":
    pytest.main([__file__, "-v", "-s"])
