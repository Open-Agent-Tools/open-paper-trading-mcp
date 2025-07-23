"""
Order processing performance benchmarks and monitoring.

This module provides comprehensive performance benchmarking and monitoring
for order processing operations, including latency measurements, throughput
analysis, and performance optimization recommendations.
"""

import asyncio
import contextlib
import logging
import threading
import time
from collections import defaultdict, deque
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from statistics import mean, median, stdev
from typing import Any

logger = logging.getLogger(__name__)


@dataclass
class LatencyDistribution:
    """Represents the latency distribution of a set of measurements."""

    min_ms: float = 0.0
    max_ms: float = 0.0
    avg_ms: float = 0.0
    median_ms: float = 0.0
    p95_ms: float = 0.0
    p99_ms: float = 0.0
    std_dev: float = 0.0


@dataclass
class PerformanceMetric:
    """Individual performance measurement."""

    operation: str
    start_time: float
    end_time: float
    duration_ms: float
    success: bool
    error: str | None = None
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass
class BenchmarkResult:
    """Benchmark test result."""

    test_name: str
    total_operations: int
    successful_operations: int
    failed_operations: int
    total_duration_ms: float
    avg_latency_ms: float
    median_latency_ms: float
    p95_latency_ms: float
    p99_latency_ms: float
    throughput_ops_sec: float
    error_rate: float
    start_time: datetime
    end_time: datetime
    detailed_metrics: list[PerformanceMetric] = field(default_factory=list)


@dataclass
class PerformanceThresholds:
    """Performance alert thresholds."""

    max_avg_latency_ms: float = 100.0
    max_p95_latency_ms: float = 200.0
    min_success_rate: float = 0.95
    min_throughput_ops_sec: float = 10.0
    max_queue_depth: int = 1000


@dataclass
class PerformanceAlert:
    """Performance alert."""

    alert_type: str
    severity: str  # warning, critical
    message: str
    metric_name: str
    current_value: float
    threshold_value: float
    timestamp: datetime = field(default_factory=datetime.utcnow)


class PerformanceMonitor:
    """
    Monitor and benchmark order processing performance.

    Tracks various performance metrics including:
    - Order creation latency
    - Order execution latency
    - Throughput measurements
    - Error rates
    - Queue depths
    """

    def __init__(self, thresholds: PerformanceThresholds | None = None):
        self.thresholds = thresholds or PerformanceThresholds()

        # Metric storage
        self.metrics: dict[str, deque[PerformanceMetric]] = defaultdict(
            lambda: deque(maxlen=10000)  # Keep last 10k measurements
        )

        # Real-time counters
        self.counters: dict[str, int] = defaultdict(int)
        self.gauges: dict[str, float] = defaultdict(float)
        self.timing_buckets: dict[str, list[float]] = defaultdict(list)

        # Active measurements
        self.active_measurements: dict[str, float] = {}

        # Alerts
        self.alerts: list[PerformanceAlert] = []
        self.alert_callbacks: list[Any] = []

        # Thread safety
        self._lock = threading.Lock()

        # Monitoring task
        self.monitoring_task: asyncio.Task[None] | None = None
        self.is_monitoring = False

    async def start_monitoring(self) -> None:
        """Start performance monitoring."""
        if self.is_monitoring:
            logger.warning("Performance monitoring already started")
            return

        self.is_monitoring = True
        self.monitoring_task = asyncio.create_task(self._monitoring_loop())
        logger.info("Performance monitoring started")

    async def stop_monitoring(self) -> None:
        """Stop performance monitoring."""
        if not self.is_monitoring:
            return

        self.is_monitoring = False

        if self.monitoring_task:
            self.monitoring_task.cancel()
            with contextlib.suppress(asyncio.CancelledError):
                await self.monitoring_task

        logger.info("Performance monitoring stopped")

    def start_measurement(self, operation: str, metadata: dict[str, Any] | None = None) -> str:
        """Start timing an operation."""
        measurement_id = f"{operation}_{int(time.time() * 1000000)}"

        with self._lock:
            self.active_measurements[measurement_id] = time.perf_counter()

        return measurement_id

    def end_measurement(
        self,
        measurement_id: str,
        success: bool = True,
        error: str | None = None,
        metadata: dict[str, Any] | None = None,
    ) -> PerformanceMetric | None:
        """End timing an operation."""
        end_time = time.perf_counter()

        with self._lock:
            if measurement_id not in self.active_measurements:
                logger.warning(f"Measurement {measurement_id} not found")
                return None

            start_time = self.active_measurements.pop(measurement_id)
            duration_ms = (end_time - start_time) * 1000

            # Extract operation name
            operation = measurement_id.split("_")[0]

            metric = PerformanceMetric(
                operation=operation,
                start_time=start_time,
                end_time=end_time,
                duration_ms=duration_ms,
                success=success,
                error=error,
                metadata=metadata or {},
            )

            # Store metric
            self.metrics[operation].append(metric)

            # Update counters
            self.counters[f"{operation}_total"] += 1
            if success:
                self.counters[f"{operation}_success"] += 1
            else:
                self.counters[f"{operation}_error"] += 1

            # Update timing buckets for real-time stats
            self.timing_buckets[operation].append(duration_ms)
            if len(self.timing_buckets[operation]) > 1000:
                self.timing_buckets[operation] = self.timing_buckets[operation][-1000:]

        return metric

    def measure_sync(self, operation: str, metadata: dict[str, Any] | None = None) -> "SyncMeasurementContext":
        """Context manager for synchronous operations."""
        return SyncMeasurementContext(self, operation, metadata)

    def measure_async(self, operation: str, metadata: dict[str, Any] | None = None) -> "AsyncMeasurementContext":
        """Context manager for asynchronous operations."""
        return AsyncMeasurementContext(self, operation, metadata)

    def record_counter(self, name: str, value: int = 1) -> None:
        """Record a counter value."""
        with self._lock:
            self.counters[name] += value

    def record_gauge(self, name: str, value: float) -> None:
        """Record a gauge value."""
        with self._lock:
            self.gauges[name] = value

    def get_current_stats(self, operation: str) -> dict[str, Any]:
        """Get current statistics for an operation."""
        with self._lock:
            if operation not in self.metrics:
                return {}

            recent_metrics = list(self.metrics[operation])

        if not recent_metrics:
            return {}

        # Calculate statistics
        durations = [m.duration_ms for m in recent_metrics]
        success_count = sum(1 for m in recent_metrics if m.success)

        stats = {
            "total_operations": len(recent_metrics),
            "successful_operations": success_count,
            "error_rate": 1 - (success_count / len(recent_metrics)),
            "avg_latency_ms": mean(durations),
            "median_latency_ms": median(durations),
            "min_latency_ms": min(durations),
            "max_latency_ms": max(durations),
        }

        if len(durations) > 1:
            stats["std_latency_ms"] = stdev(durations)

            # Percentiles
            sorted_durations = sorted(durations)
            p95_idx = int(0.95 * len(sorted_durations))
            p99_idx = int(0.99 * len(sorted_durations))

            stats["p95_latency_ms"] = sorted_durations[p95_idx]
            stats["p99_latency_ms"] = sorted_durations[p99_idx]

        # Throughput (last minute)
        one_minute_ago = time.perf_counter() - 60
        recent_ops = [m for m in recent_metrics if m.start_time > one_minute_ago]
        stats["throughput_ops_sec"] = len(recent_ops) / 60.0

        return stats

    def get_all_stats(self) -> dict[str, dict[str, Any]]:
        """Get statistics for all operations."""
        stats = {}

        with self._lock:
            operations = list(self.metrics.keys())

        for operation in operations:
            stats[operation] = self.get_current_stats(operation)

        # Add system-wide counters and gauges
        stats["_counters"] = dict(self.counters)
        stats["_gauges"] = dict(self.gauges)

        return stats

    async def run_benchmark(
        self,
        test_name: str,
        test_function: Any,
        num_operations: int = 100,
        concurrency: int = 10,
        **kwargs: Any,
    ) -> BenchmarkResult:
        """Run a performance benchmark test."""
        logger.info(
            f"Running benchmark: {test_name} ({num_operations} ops, {concurrency} concurrent)"
        )

        start_time = datetime.utcnow()
        start_perf = time.perf_counter()

        # Create semaphore for concurrency control
        semaphore = asyncio.Semaphore(concurrency)
        metrics = []

        async def run_single_operation(op_id: int) -> None:
            async with semaphore:
                measurement_id = self.start_measurement(test_name, {"op_id": op_id})

                try:
                    await test_function(op_id, **kwargs)
                    metric = self.end_measurement(measurement_id, success=True)
                except Exception as e:
                    metric = self.end_measurement(
                        measurement_id, success=False, error=str(e)
                    )

                if metric:
                    metrics.append(metric)

        # Run all operations
        tasks = [run_single_operation(i) for i in range(num_operations)]
        await asyncio.gather(*tasks, return_exceptions=True)

        end_time = datetime.utcnow()
        end_perf = time.perf_counter()

        # Calculate results
        total_duration_ms = (end_perf - start_perf) * 1000
        successful = [m for m in metrics if m.success]
        failed = [m for m in metrics if not m.success]

        durations = [m.duration_ms for m in successful]

        result = BenchmarkResult(
            test_name=test_name,
            total_operations=len(metrics),
            successful_operations=len(successful),
            failed_operations=len(failed),
            total_duration_ms=total_duration_ms,
            avg_latency_ms=mean(durations) if durations else 0,
            median_latency_ms=median(durations) if durations else 0,
            p95_latency_ms=0,
            p99_latency_ms=0,
            throughput_ops_sec=(
                len(successful) / (total_duration_ms / 1000)
                if total_duration_ms > 0
                else 0
            ),
            error_rate=len(failed) / len(metrics) if metrics else 0,
            start_time=start_time,
            end_time=end_time,
            detailed_metrics=metrics,
        )

        # Calculate percentiles
        if durations:
            sorted_durations = sorted(durations)
            if len(sorted_durations) > 1:
                p95_idx = int(0.95 * len(sorted_durations))
                p99_idx = int(0.99 * len(sorted_durations))
                result.p95_latency_ms = sorted_durations[p95_idx]
                result.p99_latency_ms = sorted_durations[p99_idx]

        logger.info(
            f"Benchmark completed: {result.successful_operations}/{result.total_operations} succeeded"
        )
        logger.info(
            f"Performance: {result.avg_latency_ms:.2f}ms avg, {result.throughput_ops_sec:.2f} ops/sec"
        )

        return result

    async def _monitoring_loop(self) -> None:
        """Background monitoring loop to check thresholds."""
        logger.info("Starting performance monitoring loop")

        while self.is_monitoring:
            try:
                await self._check_performance_thresholds()
                await asyncio.sleep(10)  # Check every 10 seconds
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"Error in monitoring loop: {e}", exc_info=True)
                await asyncio.sleep(30)  # Back off on error

    async def _check_performance_thresholds(self) -> None:
        """Check performance metrics against thresholds."""
        with self._lock:
            operations = list(self.metrics.keys())

        for operation in operations:
            stats = self.get_current_stats(operation)
            if not stats:
                continue

            # Check average latency
            avg_latency = stats.get("avg_latency_ms", 0)
            if avg_latency > self.thresholds.max_avg_latency_ms:
                self._create_alert(
                    "high_latency",
                    "warning",
                    f"High average latency for {operation}: {avg_latency:.2f}ms",
                    f"{operation}_avg_latency_ms",
                    avg_latency,
                    self.thresholds.max_avg_latency_ms,
                )

            # Check P95 latency
            p95_latency = stats.get("p95_latency_ms", 0)
            if p95_latency > self.thresholds.max_p95_latency_ms:
                self._create_alert(
                    "high_p95_latency",
                    "warning",
                    f"High P95 latency for {operation}: {p95_latency:.2f}ms",
                    f"{operation}_p95_latency_ms",
                    p95_latency,
                    self.thresholds.max_p95_latency_ms,
                )

            # Check success rate
            error_rate = stats.get("error_rate", 0)
            success_rate = 1 - error_rate
            if success_rate < self.thresholds.min_success_rate:
                self._create_alert(
                    "low_success_rate",
                    "critical",
                    f"Low success rate for {operation}: {success_rate:.1%}",
                    f"{operation}_success_rate",
                    success_rate,
                    self.thresholds.min_success_rate,
                )

            # Check throughput
            throughput = stats.get("throughput_ops_sec", 0)
            if throughput < self.thresholds.min_throughput_ops_sec:
                self._create_alert(
                    "low_throughput",
                    "warning",
                    f"Low throughput for {operation}: {throughput:.2f} ops/sec",
                    f"{operation}_throughput",
                    throughput,
                    self.thresholds.min_throughput_ops_sec,
                )

    def _create_alert(
        self,
        alert_type: str,
        severity: str,
        message: str,
        metric_name: str,
        current_value: float,
        threshold_value: float,
    ) -> None:
        """Create a performance alert."""
        alert = PerformanceAlert(
            alert_type=alert_type,
            severity=severity,
            message=message,
            metric_name=metric_name,
            current_value=current_value,
            threshold_value=threshold_value,
        )

        self.alerts.append(alert)

        # Keep only recent alerts
        if len(self.alerts) > 1000:
            self.alerts = self.alerts[-500:]

        # Trigger callbacks
        for callback in self.alert_callbacks:
            try:
                callback(alert)
            except Exception as e:
                logger.error(f"Error in alert callback: {e}")

        logger.warning(f"Performance alert: {message}")

    def add_alert_callback(self, callback: Any) -> None:
        """Add alert callback function."""
        self.alert_callbacks.append(callback)

    def get_recent_alerts(self, hours: int = 24) -> list[PerformanceAlert]:
        """Get recent alerts."""
        cutoff = datetime.utcnow() - timedelta(hours=hours)
        return [alert for alert in self.alerts if alert.timestamp > cutoff]

    def clear_metrics(self, operation: str | None = None) -> None:
        """Clear stored metrics."""
        with self._lock:
            if operation:
                self.metrics[operation].clear()
                # Clear related counters
                keys_to_clear = [k for k in self.counters if k.startswith(operation)]
                for key in keys_to_clear:
                    del self.counters[key]
            else:
                self.metrics.clear()
                self.counters.clear()

    def export_metrics(self, operation: str | None = None) -> dict[str, Any]:
        """Export metrics for external analysis."""
        data = {
            "timestamp": datetime.utcnow().isoformat(),
            "stats": self.get_all_stats(),
            "alerts": [
                {
                    "type": a.alert_type,
                    "severity": a.severity,
                    "message": a.message,
                    "timestamp": a.timestamp.isoformat(),
                }
                for a in self.get_recent_alerts()
            ],
        }

        if operation:
            with self._lock:
                if operation in self.metrics:
                    data["raw_metrics"] = [
                        {
                            "operation": m.operation,
                            "duration_ms": m.duration_ms,
                            "success": m.success,
                            "error": m.error,
                            "metadata": m.metadata,
                        }
                        for m in self.metrics[operation]
                    ]

        return data


class SyncMeasurementContext:
    """Context manager for synchronous performance measurement."""

    def __init__(
        self,
        monitor: PerformanceMonitor,
        operation: str,
        metadata: dict[str, Any] | None = None,
    ):
        self.monitor = monitor
        self.operation = operation
        self.metadata = metadata
        self.measurement_id: str | None = None

    def __enter__(self) -> "SyncMeasurementContext":
        self.measurement_id = self.monitor.start_measurement(
            self.operation, self.metadata
        )
        return self

    def __exit__(self, exc_type: Any, exc_val: Any, exc_tb: Any) -> None:
        if self.measurement_id:
            success = exc_type is None
            error = str(exc_val) if exc_val else None
            self.monitor.end_measurement(self.measurement_id, success, error)


class AsyncMeasurementContext:
    """Context manager for asynchronous performance measurement."""

    def __init__(
        self,
        monitor: PerformanceMonitor,
        operation: str,
        metadata: dict[str, Any] | None = None,
    ):
        self.monitor = monitor
        self.operation = operation
        self.metadata = metadata
        self.measurement_id: str | None = None

    async def __aenter__(self) -> "AsyncMeasurementContext":
        self.measurement_id = self.monitor.start_measurement(
            self.operation, self.metadata
        )
        return self

    async def __aexit__(self, exc_type: Any, exc_val: Any, exc_tb: Any) -> None:
        if self.measurement_id:
            success = exc_type is None
            error = str(exc_val) if exc_val else None
            self.monitor.end_measurement(self.measurement_id, success, error)


# Global performance monitor
performance_monitor = PerformanceMonitor()


def get_performance_monitor() -> PerformanceMonitor:
    """Get the global performance monitor."""
    return performance_monitor


def configure_performance_thresholds(thresholds: PerformanceThresholds) -> None:
    """Configure performance monitoring thresholds."""
    global performance_monitor
    performance_monitor.thresholds = thresholds


class OptimizationRecommendation:
    """
    A stub for the OptimizationRecommendation.
    """
    pass


class PerformanceBenchmarker:
    """
    A stub for the PerformanceBenchmarker.
    """
    pass


class SystemResourceMetrics:
    """
    A stub for the SystemResourceMetrics.
    """
    pass


class ThroughputResult:
    """
    A stub for the ThroughputResult.
    """
    pass
