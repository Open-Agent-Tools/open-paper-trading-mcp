"""
Advanced test coverage for PerformanceBenchmarks service.

This module provides comprehensive testing of the performance benchmarking service,
focusing on performance monitoring, latency measurement, throughput analysis,
and optimization recommendations.
"""

import asyncio
import time
from datetime import datetime
from unittest.mock import patch

import pytest
import pytest_asyncio

from app.services.performance_benchmarks import (
    BenchmarkResult,
    LatencyDistribution,
    OptimizationRecommendation,
    PerformanceBenchmarker,
    PerformanceMetric,
    SystemResourceMetrics,
    ThroughputResult,
)


@pytest.fixture
def performance_benchmarker():
    """Create PerformanceBenchmarker instance for testing."""
    return PerformanceBenchmarker(
        enable_detailed_logging=True,
        alert_thresholds={
            "high_latency_ms": 1000,
            "low_throughput_ops_sec": 10,
            "error_rate_percent": 5.0,
        },
    )


@pytest.fixture
def sample_metrics():
    """Create sample performance metrics for testing."""
    base_time = time.time()
    metrics = []

    for i in range(100):
        metrics.append(
            PerformanceMetric(
                operation=f"test_operation_{i % 5}",
                start_time=base_time + i * 0.1,
                end_time=base_time
                + i * 0.1
                + 0.05
                + (i % 3) * 0.01,  # Variable latency
                duration_ms=(50 + (i % 3) * 10) + (i % 10),  # 50-70ms range
                success=i % 20 != 0,  # 5% error rate
                error="Timeout error" if i % 20 == 0 else None,
                metadata={
                    "request_size_bytes": 1024 + (i % 5) * 256,
                    "response_size_bytes": 2048 + (i % 3) * 512,
                    "cache_hit": i % 4 == 0,
                },
            )
        )

    return metrics


class TestPerformanceBenchmarkerInitialization:
    """Test PerformanceBenchmarker initialization and configuration."""

    def test_initialization_default_config(self):
        """Test benchmarker initializes with default configuration."""
        benchmarker = PerformanceBenchmarker()

        assert benchmarker.enable_detailed_logging is False
        assert benchmarker.alert_thresholds is not None
        assert "high_latency_ms" in benchmarker.alert_thresholds
        assert benchmarker.metrics_buffer is not None
        assert benchmarker.resource_monitor is not None

    def test_initialization_custom_config(self):
        """Test benchmarker with custom configuration."""
        custom_thresholds = {
            "high_latency_ms": 500,
            "low_throughput_ops_sec": 50,
            "error_rate_percent": 2.0,
            "cpu_utilization_percent": 80.0,
            "memory_utilization_percent": 85.0,
        }

        benchmarker = PerformanceBenchmarker(
            enable_detailed_logging=True,
            alert_thresholds=custom_thresholds,
            buffer_size=5000,
        )

        assert benchmarker.enable_detailed_logging is True
        assert benchmarker.alert_thresholds == custom_thresholds
        assert benchmarker.metrics_buffer.maxlen == 5000

    def test_metric_collection_initialization(self, performance_benchmarker):
        """Test metric collection components are initialized."""
        assert performance_benchmarker.operation_counters is not None
        assert performance_benchmarker.latency_histograms is not None
        assert performance_benchmarker.error_trackers is not None


class TestPerformanceMetricCollection:
    """Test performance metric collection and storage."""

    def test_record_metric_success(self, performance_benchmarker):
        """Test recording successful performance metric."""
        metric = PerformanceMetric(
            operation="test_operation",
            start_time=time.time(),
            end_time=time.time() + 0.1,
            duration_ms=100.0,
            success=True,
            metadata={"test": "data"},
        )

        performance_benchmarker.record_metric(metric)

        # Verify metric was stored
        assert len(performance_benchmarker.metrics_buffer) == 1
        assert performance_benchmarker.operation_counters["test_operation"] == 1
        assert "test_operation" in performance_benchmarker.latency_histograms

    def test_record_metric_failure(self, performance_benchmarker):
        """Test recording failed performance metric."""
        metric = PerformanceMetric(
            operation="failing_operation",
            start_time=time.time(),
            end_time=time.time() + 0.2,
            duration_ms=200.0,
            success=False,
            error="Database connection timeout",
            metadata={"retry_count": 3},
        )

        performance_benchmarker.record_metric(metric)

        # Verify error was tracked
        assert performance_benchmarker.error_trackers["failing_operation"]["total"] == 1
        assert (
            "Database connection timeout"
            in performance_benchmarker.error_trackers["failing_operation"]["errors"]
        )

    def test_metric_buffer_overflow(self, performance_benchmarker):
        """Test metric buffer overflow handling."""
        # Fill buffer beyond capacity
        buffer_size = performance_benchmarker.metrics_buffer.maxlen

        for i in range(buffer_size + 100):
            metric = PerformanceMetric(
                operation=f"test_op_{i}",
                start_time=time.time(),
                end_time=time.time() + 0.01,
                duration_ms=10.0,
                success=True,
            )
            performance_benchmarker.record_metric(metric)

        # Buffer should not exceed max size
        assert len(performance_benchmarker.metrics_buffer) == buffer_size

    @pytest_asyncio.async_test
    async def test_context_manager_metric_recording(self, performance_benchmarker):
        """Test automatic metric recording with context manager."""
        async with performance_benchmarker.measure_operation(
            "async_test_op"
        ) as measurement:
            # Simulate async work
            await asyncio.sleep(0.1)
            measurement.add_metadata({"processed_items": 10})

        # Verify metric was automatically recorded
        assert len(performance_benchmarker.metrics_buffer) == 1
        metric = performance_benchmarker.metrics_buffer[0]
        assert metric.operation == "async_test_op"
        assert metric.success is True
        assert metric.duration_ms >= 100  # At least 100ms from sleep
        assert metric.metadata["processed_items"] == 10

    @pytest_asyncio.async_test
    async def test_context_manager_exception_handling(self, performance_benchmarker):
        """Test context manager handles exceptions properly."""
        with pytest.raises(ValueError, match="Test error"):
            async with performance_benchmarker.measure_operation("failing_op"):
                await asyncio.sleep(0.05)
                raise ValueError("Test error")

        # Verify failed metric was recorded
        assert len(performance_benchmarker.metrics_buffer) == 1
        metric = performance_benchmarker.metrics_buffer[0]
        assert metric.operation == "failing_op"
        assert metric.success is False
        assert "Test error" in metric.error


class TestBenchmarkExecution:
    """Test benchmark execution and analysis."""

    def test_run_benchmark_single_operation(self, performance_benchmarker):
        """Test running benchmark for single operation type."""

        def test_operation():
            time.sleep(0.01)  # 10ms operation
            return "success"

        result = performance_benchmarker.run_benchmark(
            "sleep_test", test_operation, iterations=50, warmup_iterations=5
        )

        assert isinstance(result, BenchmarkResult)
        assert result.test_name == "sleep_test"
        assert result.total_operations == 50
        assert result.successful_operations <= 50
        assert result.avg_latency_ms >= 10.0  # Should be at least 10ms
        assert result.throughput_ops_sec > 0

    @pytest_asyncio.async_test
    async def test_run_async_benchmark(self, performance_benchmarker):
        """Test running async benchmark."""

        async def async_operation():
            await asyncio.sleep(0.02)  # 20ms async operation
            return "async_success"

        result = await performance_benchmarker.run_async_benchmark(
            "async_sleep_test", async_operation, iterations=30, concurrency=5
        )

        assert isinstance(result, BenchmarkResult)
        assert result.test_name == "async_sleep_test"
        assert result.total_operations == 30
        assert result.avg_latency_ms >= 20.0
        assert result.throughput_ops_sec > 0

    def test_benchmark_with_failures(self, performance_benchmarker):
        """Test benchmark execution with some failures."""

        def unreliable_operation():
            import random

            if random.random() < 0.2:  # 20% failure rate
                raise Exception("Random failure")
            time.sleep(0.005)
            return "success"

        result = performance_benchmarker.run_benchmark(
            "unreliable_test", unreliable_operation, iterations=100
        )

        assert result.failed_operations > 0
        assert result.error_rate > 0
        assert result.error_rate <= 0.3  # Should be around 20%
        assert result.successful_operations + result.failed_operations == 100

    @pytest_asyncio.async_test
    async def test_concurrent_benchmark_execution(self, performance_benchmarker):
        """Test concurrent benchmark execution."""

        async def concurrent_operation(operation_id: int):
            await asyncio.sleep(0.01 + (operation_id % 3) * 0.005)  # Variable latency
            if operation_id % 10 == 0:
                raise Exception(f"Failure {operation_id}")
            return f"result_{operation_id}"

        result = await performance_benchmarker.run_concurrent_benchmark(
            "concurrent_test",
            concurrent_operation,
            total_operations=100,
            max_concurrency=10,
        )

        assert result.total_operations == 100
        assert result.failed_operations > 0  # Should have some failures
        assert result.throughput_ops_sec > 0
        assert result.p95_latency_ms > result.median_latency_ms


class TestLatencyAnalysis:
    """Test latency measurement and analysis."""

    def test_latency_distribution_calculation(
        self, performance_benchmarker, sample_metrics
    ):
        """Test latency distribution calculation."""
        for metric in sample_metrics:
            performance_benchmarker.record_metric(metric)

        distribution = performance_benchmarker.calculate_latency_distribution(
            "test_operation_0"
        )

        assert isinstance(distribution, LatencyDistribution)
        assert distribution.p50_ms > 0
        assert distribution.p95_ms >= distribution.p50_ms
        assert distribution.p99_ms >= distribution.p95_ms
        assert distribution.max_ms >= distribution.p99_ms
        assert distribution.mean_ms > 0
        assert distribution.std_dev_ms >= 0

    def test_latency_percentile_accuracy(self, performance_benchmarker):
        """Test accuracy of latency percentile calculations."""
        # Create metrics with known latencies
        known_latencies = [10, 20, 30, 40, 50, 60, 70, 80, 90, 100]  # ms

        for i, latency in enumerate(known_latencies):
            metric = PerformanceMetric(
                operation="known_latency_test",
                start_time=time.time() + i,
                end_time=time.time() + i + latency / 1000,
                duration_ms=float(latency),
                success=True,
            )
            performance_benchmarker.record_metric(metric)

        distribution = performance_benchmarker.calculate_latency_distribution(
            "known_latency_test"
        )

        # P50 should be around 55ms (middle of 50 and 60)
        assert 52 <= distribution.p50_ms <= 58
        # P90 should be around 90ms
        assert 88 <= distribution.p90_ms <= 92
        # Max should be 100ms
        assert distribution.max_ms == 100.0

    def test_latency_trend_analysis(self, performance_benchmarker):
        """Test latency trend analysis over time."""
        base_time = time.time()

        # Create metrics with increasing latency trend
        for i in range(50):
            latency = 50 + i * 2  # Increasing from 50ms to 148ms
            metric = PerformanceMetric(
                operation="trending_operation",
                start_time=base_time + i * 10,
                end_time=base_time + i * 10 + latency / 1000,
                duration_ms=float(latency),
                success=True,
            )
            performance_benchmarker.record_metric(metric)

        trend = performance_benchmarker.analyze_latency_trend(
            "trending_operation", time_window_minutes=60
        )

        assert trend.slope > 0  # Positive trend (increasing latency)
        assert trend.correlation > 0.8  # Strong positive correlation
        assert trend.trend_direction == "increasing"


class TestThroughputAnalysis:
    """Test throughput measurement and analysis."""

    def test_throughput_calculation(self, performance_benchmarker, sample_metrics):
        """Test throughput calculation accuracy."""
        # Record metrics within specific time window
        for metric in sample_metrics:
            performance_benchmarker.record_metric(metric)

        throughput = performance_benchmarker.calculate_throughput(
            time_window_seconds=10.0
        )

        assert isinstance(throughput, ThroughputResult)
        assert throughput.ops_per_second > 0
        assert throughput.total_operations > 0
        assert throughput.time_window_seconds == 10.0
        assert throughput.success_rate >= 0.9  # Should be around 95%

    def test_throughput_by_operation(self, performance_benchmarker, sample_metrics):
        """Test throughput calculation by operation type."""
        for metric in sample_metrics:
            performance_benchmarker.record_metric(metric)

        throughput_by_op = performance_benchmarker.calculate_throughput_by_operation(
            time_window_seconds=10.0
        )

        assert isinstance(throughput_by_op, dict)
        assert len(throughput_by_op) == 5  # test_operation_0 through test_operation_4

        for operation, throughput in throughput_by_op.items():
            assert throughput.ops_per_second > 0
            assert operation.startswith("test_operation_")

    @pytest_asyncio.async_test
    async def test_real_time_throughput_monitoring(self, performance_benchmarker):
        """Test real-time throughput monitoring."""
        # Start throughput monitoring
        monitoring_task = asyncio.create_task(
            performance_benchmarker.monitor_throughput_realtime(
                interval_seconds=0.1, duration_seconds=1.0
            )
        )

        # Generate operations during monitoring
        async def generate_operations():
            for _i in range(20):
                metric = PerformanceMetric(
                    operation="realtime_test",
                    start_time=time.time(),
                    end_time=time.time() + 0.01,
                    duration_ms=10.0,
                    success=True,
                )
                performance_benchmarker.record_metric(metric)
                await asyncio.sleep(0.05)  # 20 ops/sec

        # Run both monitoring and operation generation
        operation_task = asyncio.create_task(generate_operations())

        throughput_samples = await monitoring_task
        await operation_task

        # Should have captured multiple throughput samples
        assert len(throughput_samples) >= 8  # At least 8 samples over 1 second
        assert all(sample.ops_per_second >= 0 for sample in throughput_samples)


class TestResourceMonitoring:
    """Test system resource monitoring integration."""

    def test_system_resource_collection(self, performance_benchmarker):
        """Test system resource metrics collection."""
        metrics = performance_benchmarker.collect_system_metrics()

        assert isinstance(metrics, SystemResourceMetrics)
        assert 0 <= metrics.cpu_percent <= 100
        assert metrics.memory_percent > 0
        assert metrics.memory_used_mb > 0
        assert metrics.disk_io_read_mb >= 0
        assert metrics.disk_io_write_mb >= 0
        assert metrics.network_bytes_sent >= 0
        assert metrics.network_bytes_recv >= 0

    @pytest_asyncio.async_test
    async def test_resource_monitoring_during_load(self, performance_benchmarker):
        """Test resource monitoring during high load operations."""
        # Start resource monitoring
        monitoring_task = asyncio.create_task(
            performance_benchmarker.monitor_resources_during_operation(
                sample_interval_seconds=0.1, duration_seconds=2.0
            )
        )

        # Generate CPU/memory intensive operations
        async def intensive_operations():
            for i in range(100):
                # CPU intensive task
                result = sum(j * j for j in range(1000))

                # Memory allocation
                temp_data = [i] * 10000

                metric = PerformanceMetric(
                    operation="intensive_op",
                    start_time=time.time(),
                    end_time=time.time() + 0.01,
                    duration_ms=10.0,
                    success=True,
                    metadata={"cpu_work": result, "memory_alloc": len(temp_data)},
                )
                performance_benchmarker.record_metric(metric)
                await asyncio.sleep(0.02)

        # Run both monitoring and intensive operations
        operation_task = asyncio.create_task(intensive_operations())

        resource_samples = await monitoring_task
        await operation_task

        # Should have captured resource usage during load
        assert len(resource_samples) >= 15  # Multiple samples
        max_cpu = max(sample.cpu_percent for sample in resource_samples)
        max_memory = max(sample.memory_percent for sample in resource_samples)

        # Should show some resource usage
        assert max_cpu > 0
        assert max_memory > 0


class TestPerformanceAlerts:
    """Test performance alerting and threshold monitoring."""

    def test_high_latency_alert(self, performance_benchmarker):
        """Test high latency alert generation."""
        # Create high latency metric
        high_latency_metric = PerformanceMetric(
            operation="slow_operation",
            start_time=time.time(),
            end_time=time.time() + 2.0,
            duration_ms=2000.0,  # 2 seconds - above threshold
            success=True,
        )

        performance_benchmarker.record_metric(high_latency_metric)
        alerts = performance_benchmarker.check_alert_conditions()

        # Should generate high latency alert
        latency_alerts = [a for a in alerts if a.alert_type == "high_latency"]
        assert len(latency_alerts) >= 1
        assert latency_alerts[0].severity in ["warning", "critical"]
        assert "2000" in latency_alerts[0].message  # Should mention the latency

    def test_high_error_rate_alert(self, performance_benchmarker):
        """Test high error rate alert generation."""
        # Create metrics with high error rate
        for i in range(20):
            metric = PerformanceMetric(
                operation="error_prone_op",
                start_time=time.time() + i * 0.1,
                end_time=time.time() + i * 0.1 + 0.05,
                duration_ms=50.0,
                success=i % 2 == 0,  # 50% error rate
                error="Test error" if i % 2 == 1 else None,
            )
            performance_benchmarker.record_metric(metric)

        alerts = performance_benchmarker.check_alert_conditions()

        # Should generate high error rate alert
        error_alerts = [a for a in alerts if a.alert_type == "high_error_rate"]
        assert len(error_alerts) >= 1
        assert error_alerts[0].severity == "critical"
        assert "50" in error_alerts[0].message  # Should mention error rate

    def test_low_throughput_alert(self, performance_benchmarker):
        """Test low throughput alert generation."""
        # Create very few metrics to simulate low throughput
        for i in range(3):  # Very low operation count
            metric = PerformanceMetric(
                operation="low_throughput_op",
                start_time=time.time() + i * 5,  # Spread over 10 seconds
                end_time=time.time() + i * 5 + 1,
                duration_ms=1000.0,
                success=True,
            )
            performance_benchmarker.record_metric(metric)

        alerts = performance_benchmarker.check_alert_conditions()

        # Should generate low throughput alert
        throughput_alerts = [a for a in alerts if a.alert_type == "low_throughput"]
        assert len(throughput_alerts) >= 1
        assert throughput_alerts[0].severity in ["warning", "critical"]

    @pytest_asyncio.async_test
    async def test_alert_escalation(self, performance_benchmarker):
        """Test alert escalation for persistent issues."""
        # Generate persistent high latency
        for round_num in range(3):
            for i in range(10):
                metric = PerformanceMetric(
                    operation="persistent_slow_op",
                    start_time=time.time() + round_num * 60 + i,
                    end_time=time.time() + round_num * 60 + i + 1.5,
                    duration_ms=1500.0,  # Consistently high latency
                    success=True,
                )
                performance_benchmarker.record_metric(metric)

            # Check alerts after each round
            alerts = performance_benchmarker.check_alert_conditions()
            latency_alerts = [a for a in alerts if a.alert_type == "high_latency"]

            if round_num == 2:  # Third round should escalate
                assert any(a.severity == "critical" for a in latency_alerts)


class TestOptimizationRecommendations:
    """Test optimization recommendation generation."""

    def test_latency_optimization_recommendations(
        self, performance_benchmarker, sample_metrics
    ):
        """Test latency optimization recommendations."""
        for metric in sample_metrics:
            performance_benchmarker.record_metric(metric)

        recommendations = (
            performance_benchmarker.generate_optimization_recommendations()
        )

        assert isinstance(recommendations, list)
        assert len(recommendations) > 0

        # Should have latency-related recommendations
        latency_recs = [
            r for r in recommendations if "latency" in r.description.lower()
        ]
        assert len(latency_recs) > 0

        for rec in latency_recs:
            assert isinstance(rec, OptimizationRecommendation)
            assert rec.category in ["performance", "latency", "throughput", "resources"]
            assert rec.priority in ["low", "medium", "high", "critical"]

    def test_throughput_optimization_recommendations(self, performance_benchmarker):
        """Test throughput optimization recommendations."""
        # Create low throughput scenario
        for i in range(5):
            metric = PerformanceMetric(
                operation="low_throughput_op",
                start_time=time.time() + i * 2,  # Very slow operation rate
                end_time=time.time() + i * 2 + 0.1,
                duration_ms=100.0,
                success=True,
            )
            performance_benchmarker.record_metric(metric)

        recommendations = (
            performance_benchmarker.generate_optimization_recommendations()
        )

        throughput_recs = [
            r for r in recommendations if "throughput" in r.description.lower()
        ]
        assert len(throughput_recs) > 0

        # Should suggest concurrency or batching improvements
        assert any(
            "concurrency" in r.description.lower() or "batch" in r.description.lower()
            for r in throughput_recs
        )

    def test_resource_optimization_recommendations(self, performance_benchmarker):
        """Test resource-based optimization recommendations."""
        # Simulate high resource usage
        with patch.object(
            performance_benchmarker, "collect_system_metrics"
        ) as mock_metrics:
            mock_metrics.return_value = SystemResourceMetrics(
                cpu_percent=95.0,  # Very high CPU
                memory_percent=90.0,  # Very high memory
                memory_used_mb=8192,
                disk_io_read_mb=1000,
                disk_io_write_mb=500,
                network_bytes_sent=1000000,
                network_bytes_recv=1500000,
                timestamp=datetime.utcnow(),
            )

            recommendations = (
                performance_benchmarker.generate_optimization_recommendations()
            )

            resource_recs = [
                r
                for r in recommendations
                if r.category == "resources"
                or "cpu" in r.description.lower()
                or "memory" in r.description.lower()
            ]
            assert len(resource_recs) > 0

            # Should suggest resource optimization
            assert any(
                "cpu" in r.description.lower() or "memory" in r.description.lower()
                for r in resource_recs
            )


class TestConcurrencyAndStressScenarios:
    """Test concurrent benchmarking and stress scenarios."""

    @pytest_asyncio.async_test
    async def test_concurrent_metric_collection(self, performance_benchmarker):
        """Test thread-safe metric collection under concurrency."""

        async def generate_metrics(worker_id: int, count: int):
            for i in range(count):
                metric = PerformanceMetric(
                    operation=f"concurrent_op_worker_{worker_id}",
                    start_time=time.time(),
                    end_time=time.time() + 0.01,
                    duration_ms=10.0,
                    success=True,
                    metadata={"worker_id": worker_id, "iteration": i},
                )
                performance_benchmarker.record_metric(metric)
                await asyncio.sleep(0.001)  # Small delay to create interleaving

        # Run multiple workers concurrently
        tasks = [generate_metrics(worker_id, 50) for worker_id in range(5)]
        await asyncio.gather(*tasks)

        # Verify all metrics were collected
        assert (
            len(performance_benchmarker.metrics_buffer) == 250
        )  # 5 workers * 50 metrics

        # Verify operation counters
        for worker_id in range(5):
            op_name = f"concurrent_op_worker_{worker_id}"
            assert performance_benchmarker.operation_counters[op_name] == 50

    @pytest_asyncio.async_test
    async def test_stress_test_scenario(self, performance_benchmarker):
        """Test performance under stress conditions."""

        async def stress_operation(operation_id: int):
            # Simulate variable load
            if operation_id % 10 == 0:
                await asyncio.sleep(0.1)  # Occasional slow operation
            elif operation_id % 50 == 0:
                raise Exception("Stress-induced failure")
            else:
                await asyncio.sleep(0.005)  # Normal operation

            return f"stress_result_{operation_id}"

        # Run stress test
        result = await performance_benchmarker.run_stress_test(
            "stress_scenario",
            stress_operation,
            total_operations=500,
            max_concurrency=20,
            ramp_up_seconds=1.0,
        )

        assert result.total_operations == 500
        assert result.failed_operations > 0  # Should have some failures
        assert result.max_concurrency == 20
        assert result.avg_latency_ms > 5.0  # Should show latency impact

        # Should capture performance degradation under load
        assert result.p99_latency_ms > result.p50_latency_ms * 2

    @pytest_asyncio.async_test
    async def test_load_ramp_up_analysis(self, performance_benchmarker):
        """Test performance analysis during load ramp-up."""
        load_levels = [1, 5, 10, 20, 50]  # Increasing concurrency levels
        results = []

        async def ramp_test_operation():
            await asyncio.sleep(0.01)
            return "ramp_result"

        for concurrency in load_levels:
            result = await performance_benchmarker.run_concurrent_benchmark(
                f"ramp_test_concurrency_{concurrency}",
                ramp_test_operation,
                total_operations=concurrency * 10,
                max_concurrency=concurrency,
            )
            results.append((concurrency, result))

            # Brief pause between load levels
            await asyncio.sleep(0.5)

        # Analyze performance degradation
        throughputs = [result.throughput_ops_sec for _, result in results]
        latencies = [result.avg_latency_ms for _, result in results]

        # Should show throughput increase initially, then plateau/decrease
        assert max(throughputs) > throughputs[0]  # Should improve with some concurrency

        # Latency should generally increase with higher concurrency
        assert latencies[-1] > latencies[0]  # Higher latency at max load


class TestReportingAndVisualization:
    """Test performance reporting and data visualization."""

    def test_performance_report_generation(
        self, performance_benchmarker, sample_metrics
    ):
        """Test comprehensive performance report generation."""
        for metric in sample_metrics:
            performance_benchmarker.record_metric(metric)

        report = performance_benchmarker.generate_performance_report(
            time_window_hours=1.0, include_recommendations=True, include_trends=True
        )

        assert "summary" in report
        assert "latency_analysis" in report
        assert "throughput_analysis" in report
        assert "error_analysis" in report
        assert "resource_usage" in report
        assert "recommendations" in report
        assert "trends" in report

        # Verify report data structure
        summary = report["summary"]
        assert "total_operations" in summary
        assert "success_rate" in summary
        assert "avg_latency_ms" in summary
        assert "operations_per_second" in summary

    def test_trend_analysis_report(self, performance_benchmarker):
        """Test trend analysis in performance reports."""
        base_time = time.time()

        # Generate metrics with clear trends
        for i in range(100):
            # Latency increases over time
            latency = 50 + i * 0.5
            metric = PerformanceMetric(
                operation="trending_op",
                start_time=base_time + i * 30,  # Every 30 seconds
                end_time=base_time + i * 30 + latency / 1000,
                duration_ms=latency,
                success=True,
            )
            performance_benchmarker.record_metric(metric)

        report = performance_benchmarker.generate_performance_report(
            time_window_hours=1.0, include_trends=True
        )

        trends = report["trends"]
        assert "latency_trend" in trends
        assert "throughput_trend" in trends

        latency_trend = trends["latency_trend"]
        assert latency_trend["direction"] == "increasing"
        assert latency_trend["slope"] > 0
        assert latency_trend["confidence"] > 0.8  # Strong trend

    def test_comparative_analysis_report(self, performance_benchmarker):
        """Test comparative analysis between different operations."""
        operations = ["fast_op", "medium_op", "slow_op"]
        base_latencies = [10, 50, 200]  # ms

        for op_name, base_latency in zip(operations, base_latencies, strict=False):
            for i in range(30):
                metric = PerformanceMetric(
                    operation=op_name,
                    start_time=time.time() + i * 0.1,
                    end_time=time.time() + i * 0.1 + base_latency / 1000,
                    duration_ms=base_latency + (i % 5),  # Small variance
                    success=True,
                )
                performance_benchmarker.record_metric(metric)

        report = performance_benchmarker.generate_comparative_report(operations)

        assert len(report["operation_comparisons"]) == 3

        for comparison in report["operation_comparisons"]:
            assert "operation" in comparison
            assert "avg_latency_ms" in comparison
            assert "throughput_ops_sec" in comparison
            assert "success_rate" in comparison

        # Verify ordering (fast_op should have lowest latency)
        latencies = [comp["avg_latency_ms"] for comp in report["operation_comparisons"]]
        assert (
            latencies[0] < latencies[1] < latencies[2]
        )  # Should be ordered by performance
