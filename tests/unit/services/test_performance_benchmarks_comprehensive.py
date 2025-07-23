"""
Test cases for performance benchmarks and monitoring.

Tests performance monitoring, benchmarking, latency measurements,
throughput analysis, and alert systems.
"""

import pytest
import asyncio
from unittest.mock import Mock, patch, MagicMock, AsyncMock
import time
from datetime import datetime, timedelta

from app.services.performance_benchmarks import (
    PerformanceMonitor,
    LatencyDistribution,
    PerformanceMetric,
    BenchmarkResult,
    PerformanceThresholds,
    PerformanceAlert,
    SyncMeasurementContext,
    AsyncMeasurementContext,
    get_performance_monitor,
    configure_performance_thresholds,
    performance_monitor,
    OptimizationRecommendation,
    PerformanceBenchmarker,
    SystemResourceMetrics,
    ThroughputResult,
)


class TestPerformanceMonitor:
    """Test performance monitor functionality."""

    def test_monitor_initialization(self):
        """Test performance monitor initialization."""
        monitor = PerformanceMonitor()
        
        assert monitor is not None
        assert isinstance(monitor.thresholds, PerformanceThresholds)
        assert isinstance(monitor.metrics, dict)
        assert isinstance(monitor.counters, dict)
        assert isinstance(monitor.gauges, dict)
        assert isinstance(monitor.timing_buckets, dict)
        assert isinstance(monitor.active_measurements, dict)
        assert isinstance(monitor.alerts, list)
        assert monitor.is_monitoring is False

    def test_monitor_with_custom_thresholds(self):
        """Test monitor initialization with custom thresholds."""
        custom_thresholds = PerformanceThresholds(
            max_avg_latency_ms=50.0,
            max_p95_latency_ms=100.0,
            min_success_rate=0.99
        )
        
        monitor = PerformanceMonitor(custom_thresholds)
        
        assert monitor.thresholds.max_avg_latency_ms == 50.0
        assert monitor.thresholds.max_p95_latency_ms == 100.0
        assert monitor.thresholds.min_success_rate == 0.99

    def test_global_monitor_access(self):
        """Test global monitor access functions."""
        global_monitor = get_performance_monitor()
        
        assert global_monitor is not None
        assert isinstance(global_monitor, PerformanceMonitor)
        assert global_monitor is performance_monitor

    def test_configure_thresholds(self):
        """Test threshold configuration."""
        new_thresholds = PerformanceThresholds(max_avg_latency_ms=75.0)
        
        configure_performance_thresholds(new_thresholds)
        
        updated_monitor = get_performance_monitor()
        assert updated_monitor.thresholds.max_avg_latency_ms == 75.0

    @pytest.mark.asyncio
    async def test_start_stop_monitoring(self):
        """Test starting and stopping performance monitoring."""
        monitor = PerformanceMonitor()
        
        # Start monitoring
        await monitor.start_monitoring()
        assert monitor.is_monitoring is True
        assert monitor.monitoring_task is not None
        
        # Stop monitoring
        await monitor.stop_monitoring()
        assert monitor.is_monitoring is False

    @pytest.mark.asyncio
    async def test_start_monitoring_already_running(self):
        """Test starting monitoring when already running."""
        monitor = PerformanceMonitor()
        
        await monitor.start_monitoring()
        initial_task = monitor.monitoring_task
        
        # Try to start again
        await monitor.start_monitoring()
        
        # Should not create new task
        assert monitor.monitoring_task is initial_task
        
        await monitor.stop_monitoring()

    def test_measurement_lifecycle(self):
        """Test complete measurement lifecycle."""
        monitor = PerformanceMonitor()
        
        # Start measurement
        measurement_id = monitor.start_measurement("test_operation")
        
        assert measurement_id
        assert measurement_id in monitor.active_measurements
        assert measurement_id.startswith("test_operation_")
        
        # Add small delay
        time.sleep(0.01)
        
        # End measurement
        metric = monitor.end_measurement(measurement_id, success=True)
        
        assert isinstance(metric, PerformanceMetric)
        assert metric.operation == "test_operation"
        assert metric.success is True
        assert metric.duration_ms > 0
        assert measurement_id not in monitor.active_measurements

    def test_measurement_with_metadata(self):
        """Test measurement with metadata."""
        monitor = PerformanceMonitor()
        
        metadata = {"user_id": "123", "order_type": "market"}
        
        measurement_id = monitor.start_measurement("order_processing", metadata)
        metric = monitor.end_measurement(
            measurement_id, 
            success=True, 
            metadata={"result": "filled"}
        )
        
        assert metric.metadata["result"] == "filled"

    def test_measurement_with_error(self):
        """Test measurement ending with error."""
        monitor = PerformanceMonitor()
        
        measurement_id = monitor.start_measurement("failing_operation")
        metric = monitor.end_measurement(
            measurement_id, 
            success=False, 
            error="Connection timeout"
        )
        
        assert metric.success is False
        assert metric.error == "Connection timeout"

    def test_measurement_not_found(self):
        """Test ending measurement that doesn't exist."""
        monitor = PerformanceMonitor()
        
        metric = monitor.end_measurement("nonexistent_id")
        
        assert metric is None

    def test_sync_measurement_context(self):
        """Test synchronous measurement context manager."""
        monitor = PerformanceMonitor()
        
        with monitor.measure_sync("sync_operation") as ctx:
            time.sleep(0.01)  # Simulate work
            assert isinstance(ctx, SyncMeasurementContext)
        
        # Check that metric was recorded
        assert "sync_operation" in monitor.metrics
        assert len(monitor.metrics["sync_operation"]) == 1
        
        metric = monitor.metrics["sync_operation"][0]
        assert metric.operation == "sync_operation"
        assert metric.success is True
        assert metric.duration_ms > 0

    def test_sync_measurement_context_with_exception(self):
        """Test sync context manager with exception."""
        monitor = PerformanceMonitor()
        
        try:
            with monitor.measure_sync("failing_sync_operation"):
                raise ValueError("Test error")
        except ValueError:
            pass  # Expected
        
        # Check that error was recorded
        metric = monitor.metrics["failing_sync_operation"][0]
        assert metric.success is False
        assert "Test error" in metric.error

    @pytest.mark.asyncio
    async def test_async_measurement_context(self):
        """Test asynchronous measurement context manager."""
        monitor = PerformanceMonitor()
        
        async with monitor.measure_async("async_operation") as ctx:
            await asyncio.sleep(0.01)  # Simulate async work
            assert isinstance(ctx, AsyncMeasurementContext)
        
        # Check that metric was recorded
        metric = monitor.metrics["async_operation"][0]
        assert metric.operation == "async_operation"
        assert metric.success is True
        assert metric.duration_ms > 0

    @pytest.mark.asyncio
    async def test_async_measurement_context_with_exception(self):
        """Test async context manager with exception."""
        monitor = PerformanceMonitor()
        
        try:
            async with monitor.measure_async("failing_async_operation"):
                raise ValueError("Async test error")
        except ValueError:
            pass  # Expected
        
        # Check that error was recorded
        metric = monitor.metrics["failing_async_operation"][0]
        assert metric.success is False
        assert "Async test error" in metric.error

    def test_counter_recording(self):
        """Test counter value recording."""
        monitor = PerformanceMonitor()
        
        # Record counter values
        monitor.record_counter("orders_processed", 5)
        monitor.record_counter("orders_processed", 3)
        monitor.record_counter("errors", 1)
        
        assert monitor.counters["orders_processed"] == 8
        assert monitor.counters["errors"] == 1

    def test_gauge_recording(self):
        """Test gauge value recording."""
        monitor = PerformanceMonitor()
        
        # Record gauge values
        monitor.record_gauge("cpu_usage", 75.5)
        monitor.record_gauge("memory_usage", 60.2)
        monitor.record_gauge("cpu_usage", 80.1)  # Update existing
        
        assert monitor.gauges["cpu_usage"] == 80.1
        assert monitor.gauges["memory_usage"] == 60.2

    def test_current_stats_calculation(self):
        """Test current statistics calculation."""
        monitor = PerformanceMonitor()
        
        # Add some metrics
        for i in range(10):
            measurement_id = monitor.start_measurement("test_op")
            time.sleep(0.001)  # Small delay
            monitor.end_measurement(measurement_id, success=(i < 8))  # 80% success rate
        
        stats = monitor.get_current_stats("test_op")
        
        assert stats["total_operations"] == 10
        assert stats["successful_operations"] == 8
        assert stats["error_rate"] == 0.2
        assert stats["avg_latency_ms"] > 0
        assert stats["median_latency_ms"] > 0
        assert stats["min_latency_ms"] > 0
        assert stats["max_latency_ms"] > 0

    def test_current_stats_with_percentiles(self):
        """Test statistics calculation with percentiles."""
        monitor = PerformanceMonitor()
        
        # Add many metrics for reliable percentiles
        for i in range(100):
            measurement_id = monitor.start_measurement("perf_test")
            time.sleep(0.001 * (i % 10))  # Variable delays
            monitor.end_measurement(measurement_id, success=True)
        
        stats = monitor.get_current_stats("perf_test")
        
        assert "p95_latency_ms" in stats
        assert "p99_latency_ms" in stats
        assert stats["p95_latency_ms"] >= stats["median_latency_ms"]
        assert stats["p99_latency_ms"] >= stats["p95_latency_ms"]

    def test_all_stats_retrieval(self):
        """Test retrieval of all operation statistics."""
        monitor = PerformanceMonitor()
        
        # Add metrics for multiple operations
        operations = ["order_create", "order_execute", "portfolio_update"]
        
        for op in operations:
            measurement_id = monitor.start_measurement(op)
            time.sleep(0.001)
            monitor.end_measurement(measurement_id, success=True)
        
        # Add some counters and gauges
        monitor.record_counter("total_orders", 100)
        monitor.record_gauge("queue_depth", 25)
        
        all_stats = monitor.get_all_stats()
        
        for op in operations:
            assert op in all_stats
            assert "total_operations" in all_stats[op]
        
        assert "_counters" in all_stats
        assert "_gauges" in all_stats
        assert all_stats["_counters"]["total_orders"] == 100
        assert all_stats["_gauges"]["queue_depth"] == 25

    @pytest.mark.asyncio
    async def test_benchmark_execution(self):
        """Test benchmark execution."""
        monitor = PerformanceMonitor()
        
        # Mock test function
        async def mock_test_function(op_id, **kwargs):
            await asyncio.sleep(0.001)  # Simulate work
            if op_id % 10 == 0:  # 10% failure rate
                raise ValueError(f"Test failure for operation {op_id}")
            return f"result_{op_id}"
        
        result = await monitor.run_benchmark(
            "test_benchmark",
            mock_test_function,
            num_operations=50,
            concurrency=5,
            extra_param="test_value"
        )
        
        assert isinstance(result, BenchmarkResult)
        assert result.test_name == "test_benchmark"
        assert result.total_operations <= 50  # Some might fail
        assert result.successful_operations > 0
        assert result.failed_operations > 0
        assert result.error_rate > 0
        assert result.throughput_ops_sec > 0
        assert result.total_duration_ms > 0

    @pytest.mark.asyncio
    async def test_benchmark_with_all_success(self):
        """Test benchmark with all operations succeeding."""
        monitor = PerformanceMonitor()
        
        async def success_test_function(op_id, **kwargs):
            await asyncio.sleep(0.001)
            return f"success_{op_id}"
        
        result = await monitor.run_benchmark(
            "success_benchmark",
            success_test_function,
            num_operations=20,
            concurrency=2
        )
        
        assert result.total_operations == 20
        assert result.successful_operations == 20
        assert result.failed_operations == 0
        assert result.error_rate == 0.0
        assert result.avg_latency_ms > 0
        assert result.p95_latency_ms > 0

    @pytest.mark.asyncio
    async def test_monitoring_loop_threshold_checking(self):
        """Test monitoring loop threshold checking."""
        thresholds = PerformanceThresholds(
            max_avg_latency_ms=1.0,  # Very low threshold
            min_success_rate=0.99
        )
        
        monitor = PerformanceMonitor(thresholds)
        
        # Add metrics that exceed thresholds
        for i in range(5):
            measurement_id = monitor.start_measurement("slow_operation")
            time.sleep(0.01)  # Exceed 1ms threshold
            monitor.end_measurement(measurement_id, success=(i < 4))  # 80% success rate
        
        # Run threshold check manually
        await monitor._check_performance_thresholds()
        
        # Should have generated alerts
        assert len(monitor.alerts) > 0
        
        # Check for specific alert types
        alert_types = [alert.alert_type for alert in monitor.alerts]
        assert "high_latency" in alert_types
        assert "low_success_rate" in alert_types

    def test_alert_creation(self):
        """Test performance alert creation."""
        monitor = PerformanceMonitor()
        
        monitor._create_alert(
            "test_alert",
            "warning",
            "Test alert message",
            "test_metric",
            100.0,
            50.0
        )
        
        assert len(monitor.alerts) == 1
        alert = monitor.alerts[0]
        
        assert isinstance(alert, PerformanceAlert)
        assert alert.alert_type == "test_alert"
        assert alert.severity == "warning"
        assert alert.message == "Test alert message"
        assert alert.metric_name == "test_metric"
        assert alert.current_value == 100.0
        assert alert.threshold_value == 50.0

    def test_alert_callbacks(self):
        """Test alert callback functionality."""
        monitor = PerformanceMonitor()
        
        # Mock callback function
        callback_called = []
        
        def mock_callback(alert):
            callback_called.append(alert)
        
        monitor.add_alert_callback(mock_callback)
        
        # Trigger alert
        monitor._create_alert(
            "callback_test",
            "critical",
            "Callback test alert",
            "test_metric",
            200.0,
            100.0
        )
        
        assert len(callback_called) == 1
        assert callback_called[0].alert_type == "callback_test"

    def test_recent_alerts_filtering(self):
        """Test filtering of recent alerts."""
        monitor = PerformanceMonitor()
        
        # Create old alert
        old_alert = PerformanceAlert(
            alert_type="old_alert",
            severity="warning",
            message="Old alert",
            metric_name="old_metric",
            current_value=100.0,
            threshold_value=50.0,
            timestamp=datetime.utcnow() - timedelta(hours=25)  # 25 hours ago
        )
        
        # Create recent alert
        recent_alert = PerformanceAlert(
            alert_type="recent_alert",
            severity="warning",
            message="Recent alert",
            metric_name="recent_metric",
            current_value=100.0,
            threshold_value=50.0,
            timestamp=datetime.utcnow() - timedelta(hours=1)  # 1 hour ago
        )
        
        monitor.alerts.extend([old_alert, recent_alert])
        
        # Get recent alerts (last 24 hours)
        recent = monitor.get_recent_alerts(24)
        
        assert len(recent) == 1
        assert recent[0].alert_type == "recent_alert"

    def test_metrics_clearing(self):
        """Test clearing of stored metrics."""
        monitor = PerformanceMonitor()
        
        # Add metrics for multiple operations
        for op in ["op1", "op2"]:
            measurement_id = monitor.start_measurement(op)
            monitor.end_measurement(measurement_id, success=True)
        
        monitor.record_counter("op1_counter", 5)
        monitor.record_counter("op2_counter", 3)
        
        # Clear specific operation
        monitor.clear_metrics("op1")
        
        assert len(monitor.metrics["op1"]) == 0
        assert len(monitor.metrics["op2"]) == 1
        assert "op1_counter" not in monitor.counters
        assert "op2_counter" in monitor.counters
        
        # Clear all metrics
        monitor.clear_metrics()
        
        assert len(monitor.metrics) == 0
        assert len(monitor.counters) == 0

    def test_metrics_export(self):
        """Test metrics export functionality."""
        monitor = PerformanceMonitor()
        
        # Add some metrics
        measurement_id = monitor.start_measurement("export_test")
        time.sleep(0.001)
        monitor.end_measurement(measurement_id, success=True)
        
        monitor.record_counter("export_counter", 10)
        monitor.record_gauge("export_gauge", 75.5)
        
        # Add an alert
        monitor._create_alert(
            "export_alert",
            "warning",
            "Export test alert",
            "export_metric",
            100.0,
            50.0
        )
        
        # Export all metrics
        export_data = monitor.export_metrics()
        
        assert "timestamp" in export_data
        assert "stats" in export_data
        assert "alerts" in export_data
        
        assert "export_test" in export_data["stats"]
        assert "_counters" in export_data["stats"]
        assert "_gauges" in export_data["stats"]
        assert len(export_data["alerts"]) == 1

    def test_operation_specific_export(self):
        """Test operation-specific metrics export."""
        monitor = PerformanceMonitor()
        
        # Add metrics
        measurement_id = monitor.start_measurement("specific_op")
        monitor.end_measurement(measurement_id, success=True)
        
        export_data = monitor.export_metrics("specific_op")
        
        assert "raw_metrics" in export_data
        assert len(export_data["raw_metrics"]) == 1
        assert export_data["raw_metrics"][0]["operation"] == "specific_op"

    def test_timing_buckets_management(self):
        """Test timing buckets size management."""
        monitor = PerformanceMonitor()
        
        # Add many measurements to test bucket size limits
        for i in range(1500):  # More than the 1000 limit
            measurement_id = monitor.start_measurement("bucket_test")
            monitor.end_measurement(measurement_id, success=True)
        
        # Should be limited to last 1000 measurements
        assert len(monitor.timing_buckets["bucket_test"]) == 1000

    def test_alert_list_size_management(self):
        """Test alert list size management."""
        monitor = PerformanceMonitor()
        
        # Add many alerts to test size limits
        for i in range(1200):  # More than the 1000 limit
            monitor._create_alert(
                f"alert_{i}",
                "warning",
                f"Alert {i}",
                f"metric_{i}",
                float(i),
                50.0
            )
        
        # Should be limited to 500 recent alerts
        assert len(monitor.alerts) == 500


class TestDataClasses:
    """Test data classes used in performance monitoring."""

    def test_latency_distribution(self):
        """Test LatencyDistribution data class."""
        distribution = LatencyDistribution(
            min_ms=1.0,
            max_ms=100.0,
            avg_ms=25.0,
            median_ms=20.0,
            p95_ms=80.0,
            p99_ms=95.0,
            std_dev=15.5
        )
        
        assert distribution.min_ms == 1.0
        assert distribution.max_ms == 100.0
        assert distribution.avg_ms == 25.0
        assert distribution.p95_ms == 80.0
        assert distribution.std_dev == 15.5

    def test_performance_metric(self):
        """Test PerformanceMetric data class."""
        start_time = time.perf_counter()
        end_time = start_time + 0.05
        
        metric = PerformanceMetric(
            operation="test_operation",
            start_time=start_time,
            end_time=end_time,
            duration_ms=50.0,
            success=True,
            metadata={"user_id": "123"}
        )
        
        assert metric.operation == "test_operation"
        assert metric.duration_ms == 50.0
        assert metric.success is True
        assert metric.metadata["user_id"] == "123"

    def test_benchmark_result(self):
        """Test BenchmarkResult data class."""
        start_time = datetime.utcnow()
        end_time = start_time + timedelta(seconds=5)
        
        result = BenchmarkResult(
            test_name="load_test",
            total_operations=1000,
            successful_operations=950,
            failed_operations=50,
            total_duration_ms=5000.0,
            avg_latency_ms=25.5,
            median_latency_ms=20.0,
            p95_latency_ms=80.0,
            p99_latency_ms=150.0,
            throughput_ops_sec=200.0,
            error_rate=0.05,
            start_time=start_time,
            end_time=end_time
        )
        
        assert result.test_name == "load_test"
        assert result.total_operations == 1000
        assert result.successful_operations == 950
        assert result.error_rate == 0.05
        assert result.throughput_ops_sec == 200.0

    def test_performance_thresholds(self):
        """Test PerformanceThresholds data class."""
        thresholds = PerformanceThresholds()
        
        # Test defaults
        assert thresholds.max_avg_latency_ms == 100.0
        assert thresholds.max_p95_latency_ms == 200.0
        assert thresholds.min_success_rate == 0.95
        assert thresholds.min_throughput_ops_sec == 10.0
        assert thresholds.max_queue_depth == 1000
        
        # Test custom values
        custom_thresholds = PerformanceThresholds(
            max_avg_latency_ms=50.0,
            min_success_rate=0.99
        )
        
        assert custom_thresholds.max_avg_latency_ms == 50.0
        assert custom_thresholds.min_success_rate == 0.99

    def test_performance_alert(self):
        """Test PerformanceAlert data class."""
        alert = PerformanceAlert(
            alert_type="high_latency",
            severity="warning",
            message="Average latency exceeded threshold",
            metric_name="order_processing_avg_latency",
            current_value=150.0,
            threshold_value=100.0
        )
        
        assert alert.alert_type == "high_latency"
        assert alert.severity == "warning"
        assert alert.current_value == 150.0
        assert alert.threshold_value == 100.0
        assert isinstance(alert.timestamp, datetime)


class TestMeasurementContexts:
    """Test measurement context managers."""

    def test_sync_context_initialization(self):
        """Test sync measurement context initialization."""
        monitor = PerformanceMonitor()
        
        context = SyncMeasurementContext(
            monitor, "test_operation", {"key": "value"}
        )
        
        assert context.monitor is monitor
        assert context.operation == "test_operation"
        assert context.metadata == {"key": "value"}
        assert context.measurement_id is None

    def test_async_context_initialization(self):
        """Test async measurement context initialization."""
        monitor = PerformanceMonitor()
        
        context = AsyncMeasurementContext(
            monitor, "async_test", {"async": True}
        )
        
        assert context.monitor is monitor
        assert context.operation == "async_test"
        assert context.metadata == {"async": True}
        assert context.measurement_id is None

    def test_sync_context_manual_usage(self):
        """Test sync context manager manual usage."""
        monitor = PerformanceMonitor()
        context = SyncMeasurementContext(monitor, "manual_test")
        
        # Enter context
        ctx = context.__enter__()
        assert ctx is context
        assert context.measurement_id is not None
        
        # Exit context
        context.__exit__(None, None, None)
        
        # Should have recorded metric
        assert len(monitor.metrics["manual_test"]) == 1

    @pytest.mark.asyncio
    async def test_async_context_manual_usage(self):
        """Test async context manager manual usage."""
        monitor = PerformanceMonitor()
        context = AsyncMeasurementContext(monitor, "async_manual_test")
        
        # Enter context
        ctx = await context.__aenter__()
        assert ctx is context
        assert context.measurement_id is not None
        
        # Exit context
        await context.__aexit__(None, None, None)
        
        # Should have recorded metric
        assert len(monitor.metrics["async_manual_test"]) == 1


class TestStubClasses:
    """Test stub classes that will be implemented later."""

    def test_optimization_recommendation_stub(self):
        """Test OptimizationRecommendation stub class."""
        recommendation = OptimizationRecommendation()
        assert recommendation is not None
        assert isinstance(recommendation, OptimizationRecommendation)

    def test_performance_benchmarker_stub(self):
        """Test PerformanceBenchmarker stub class."""
        benchmarker = PerformanceBenchmarker()
        assert benchmarker is not None
        assert isinstance(benchmarker, PerformanceBenchmarker)

    def test_system_resource_metrics_stub(self):
        """Test SystemResourceMetrics stub class."""
        metrics = SystemResourceMetrics()
        assert metrics is not None
        assert isinstance(metrics, SystemResourceMetrics)

    def test_throughput_result_stub(self):
        """Test ThroughputResult stub class."""
        result = ThroughputResult()
        assert result is not None
        assert isinstance(result, ThroughputResult)


class TestRealWorldScenarios:
    """Test realistic performance monitoring scenarios."""

    @pytest.mark.asyncio
    async def test_order_processing_monitoring(self):
        """Test monitoring order processing performance."""
        monitor = PerformanceMonitor()
        
        # Simulate order processing operations
        operations = [
            "order_validation",
            "risk_check",
            "order_execution",
            "portfolio_update",
            "notification_send"
        ]
        
        # Process multiple orders
        for order_id in range(20):
            for operation in operations:
                async with monitor.measure_async(operation):
                    # Simulate variable processing times
                    delay = 0.001 + (order_id % 5) * 0.002
                    await asyncio.sleep(delay)
                    
                    # Simulate occasional failures
                    if order_id % 15 == 0 and operation == "order_execution":
                        raise Exception("Market closed")
        
        # Analyze performance
        for operation in operations:
            stats = monitor.get_current_stats(operation)
            assert stats["total_operations"] == 20
            
            if operation == "order_execution":
                # Should have some failures
                assert stats["error_rate"] > 0
            else:
                # Should be mostly successful
                assert stats["error_rate"] <= 0.05

    def test_high_frequency_monitoring(self):
        """Test monitoring high-frequency operations."""
        monitor = PerformanceMonitor()
        
        # Simulate high-frequency quote processing
        start_time = time.perf_counter()
        
        for i in range(1000):
            with monitor.measure_sync("quote_processing"):
                # Very fast operation
                time.sleep(0.0001)
        
        end_time = time.perf_counter()
        total_time = (end_time - start_time) * 1000  # Convert to ms
        
        stats = monitor.get_current_stats("quote_processing")
        
        assert stats["total_operations"] == 1000
        assert stats["avg_latency_ms"] < 1.0  # Should be very fast
        assert stats["throughput_ops_sec"] > 100  # High throughput

    @pytest.mark.asyncio
    async def test_load_testing_scenario(self):
        """Test load testing scenario with concurrent operations."""
        monitor = PerformanceMonitor()
        
        async def simulate_api_call(call_id):
            """Simulate API call with variable latency."""
            async with monitor.measure_async("api_call"):
                # Simulate network latency
                base_delay = 0.01
                variable_delay = (call_id % 10) * 0.005
                await asyncio.sleep(base_delay + variable_delay)
                
                # Simulate occasional timeouts
                if call_id % 50 == 0:
                    raise TimeoutError("Request timeout")
        
        # Run concurrent load test
        tasks = [simulate_api_call(i) for i in range(200)]
        results = await asyncio.gather(*tasks, return_exceptions=True)
        
        # Analyze results
        stats = monitor.get_current_stats("api_call")
        
        assert stats["total_operations"] == 200
        assert stats["error_rate"] > 0  # Should have some timeouts
        assert stats["avg_latency_ms"] > 10  # Should reflect network latency
        assert "p95_latency_ms" in stats
        assert "p99_latency_ms" in stats

    def test_performance_degradation_detection(self):
        """Test detection of performance degradation."""
        thresholds = PerformanceThresholds(
            max_avg_latency_ms=10.0,
            min_success_rate=0.95
        )
        
        monitor = PerformanceMonitor(thresholds)
        
        # Simulate normal performance
        for i in range(50):
            with monitor.measure_sync("normal_operation"):
                time.sleep(0.005)  # 5ms - within threshold
        
        # Simulate performance degradation
        for i in range(20):
            measurement_id = monitor.start_measurement("degraded_operation")
            time.sleep(0.02)  # 20ms - exceeds threshold
            success = i < 15  # 75% success rate - below threshold
            monitor.end_measurement(measurement_id, success=success)
        
        # Check for performance issues
        normal_stats = monitor.get_current_stats("normal_operation")
        degraded_stats = monitor.get_current_stats("degraded_operation")
        
        assert normal_stats["avg_latency_ms"] < thresholds.max_avg_latency_ms
        assert degraded_stats["avg_latency_ms"] > thresholds.max_avg_latency_ms
        assert degraded_stats["error_rate"] > (1 - thresholds.min_success_rate)

    @pytest.mark.asyncio
    async def test_benchmark_comparison(self):
        """Test benchmark comparison between different implementations."""
        monitor = PerformanceMonitor()
        
        # Benchmark "old" implementation
        async def old_implementation(op_id):
            await asyncio.sleep(0.01)  # Slower implementation
            return f"old_result_{op_id}"
        
        # Benchmark "new" implementation
        async def new_implementation(op_id):
            await asyncio.sleep(0.005)  # Faster implementation
            return f"new_result_{op_id}"
        
        # Run benchmarks
        old_result = await monitor.run_benchmark(
            "old_implementation",
            old_implementation,
            num_operations=50,
            concurrency=5
        )
        
        new_result = await monitor.run_benchmark(
            "new_implementation",
            new_implementation,
            num_operations=50,
            concurrency=5
        )
        
        # Compare results
        assert new_result.avg_latency_ms < old_result.avg_latency_ms
        assert new_result.throughput_ops_sec > old_result.throughput_ops_sec
        
        # Both should have no errors
        assert old_result.error_rate == 0.0
        assert new_result.error_rate == 0.0

    def test_resource_usage_tracking(self):
        """Test tracking of resource usage metrics."""
        monitor = PerformanceMonitor()
        
        # Simulate resource usage tracking
        monitor.record_gauge("cpu_usage_percent", 75.5)
        monitor.record_gauge("memory_usage_mb", 1024)
        monitor.record_gauge("disk_io_ops_sec", 150)
        monitor.record_gauge("network_bytes_sec", 1000000)
        
        monitor.record_counter("requests_served", 1000)
        monitor.record_counter("cache_hits", 850)
        monitor.record_counter("cache_misses", 150)
        
        # Calculate derived metrics
        cache_hit_ratio = monitor.gauges.get("cache_hits", 0) / (
            monitor.counters.get("cache_hits", 0) + monitor.counters.get("cache_misses", 1)
        )
        
        monitor.record_gauge("cache_hit_ratio", cache_hit_ratio)
        
        # Verify tracking
        assert monitor.gauges["cpu_usage_percent"] == 75.5
        assert monitor.gauges["memory_usage_mb"] == 1024
        assert monitor.counters["requests_served"] == 1000
        assert monitor.gauges["cache_hit_ratio"] > 0.8  # Good cache performance

    @pytest.mark.asyncio
    async def test_real_time_alerting(self):
        """Test real-time alerting on threshold violations."""
        # Set strict thresholds
        thresholds = PerformanceThresholds(
            max_avg_latency_ms=5.0,
            min_success_rate=0.98,
            min_throughput_ops_sec=50.0
        )
        
        monitor = PerformanceMonitor(thresholds)
        
        # Set up alert callback
        alerts_received = []
        
        def alert_handler(alert):
            alerts_received.append(alert)
        
        monitor.add_alert_callback(alert_handler)
        
        # Generate operations that violate thresholds
        for i in range(30):
            measurement_id = monitor.start_measurement("alerting_test")
            
            # Varying performance - some exceed thresholds
            if i < 20:
                time.sleep(0.002)  # Fast
                success = True
            else:
                time.sleep(0.01)   # Slow - exceeds 5ms threshold
                success = i < 25   # Some failures
            
            monitor.end_measurement(measurement_id, success=success)
        
        # Manually trigger threshold checking
        await monitor._check_performance_thresholds()
        
        # Should have generated alerts
        assert len(monitor.alerts) > 0
        assert len(alerts_received) > 0
        
        # Check alert types
        alert_types = {alert.alert_type for alert in monitor.alerts}
        expected_types = {"high_latency", "low_success_rate"}
        
        assert len(alert_types.intersection(expected_types)) > 0