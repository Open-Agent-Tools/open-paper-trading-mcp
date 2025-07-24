"""
Comprehensive performance and load testing for adapter integrations.

Tests performance characteristics of:
- High-volume data operations
- Concurrent access patterns
- Memory usage under load
- Cache performance optimization
- Database query optimization
- File system throughput
- Scalability limits
- Resource cleanup efficiency
"""

import asyncio
import gc
import tempfile
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime
from unittest.mock import MagicMock, Mock, patch

import psutil
import pytest

from app.adapters.accounts import DatabaseAccountAdapter, LocalFileSystemAccountAdapter
from app.adapters.cache import CachedQuoteAdapter, QuoteCache
from app.adapters.config import AdapterFactory
from app.models.assets import Stock
from app.models.quotes import Quote
from app.schemas.accounts import Account


class PerformanceProfiler:
    """Performance profiling utility for tests."""

    def __init__(self):
        self.measurements = {}
        self.start_times = {}

    def start(self, operation: str):
        """Start timing an operation."""
        self.start_times[operation] = time.time()

    def end(self, operation: str) -> float:
        """End timing and return duration."""
        if operation not in self.start_times:
            return 0.0

        duration = time.time() - self.start_times[operation]
        if operation not in self.measurements:
            self.measurements[operation] = []

        self.measurements[operation].append(duration)
        return duration

    def get_stats(self, operation: str) -> dict[str, float]:
        """Get statistics for an operation."""
        if operation not in self.measurements:
            return {}

        measurements = self.measurements[operation]
        return {
            "count": len(measurements),
            "total": sum(measurements),
            "average": sum(measurements) / len(measurements),
            "min": min(measurements),
            "max": max(measurements),
        }


class MemoryProfiler:
    """Memory profiling utility for tests."""

    def __init__(self):
        self.process = psutil.Process()
        self.baseline_memory = self.get_memory_usage()

    def get_memory_usage(self) -> float:
        """Get current memory usage in MB."""
        return self.process.memory_info().rss / 1024 / 1024

    def get_memory_delta(self) -> float:
        """Get memory usage delta from baseline."""
        return self.get_memory_usage() - self.baseline_memory

    def reset_baseline(self):
        """Reset baseline memory measurement."""
        gc.collect()  # Force garbage collection
        self.baseline_memory = self.get_memory_usage()


class TestDatabaseAdapterPerformance:
    """Performance tests for database adapter operations."""

    @pytest.fixture
    def db_adapter(self):
        """Create database adapter for performance testing."""
        return DatabaseAccountAdapter()

    @pytest.fixture
    def profiler(self):
        """Create performance profiler."""
        return PerformanceProfiler()

    @pytest.fixture
    def memory_profiler(self):
        """Create memory profiler."""
        return MemoryProfiler()

    def create_test_accounts(self, count: int) -> list[Account]:
        """Create test accounts for performance testing."""
        accounts = []
        for i in range(count):
            account = Account(
                id=f"perf-test-{i:06d}",
                cash_balance=float(10000 + i * 100),
                positions=[],
                name=f"Performance Test Account {i}",
                owner=f"perf_user_{i}",
            )
            accounts.append(account)
        return accounts

    @pytest.mark.performance
    def test_bulk_account_creation_performance(
        self, db_adapter, profiler, memory_profiler
    ):
        """Test performance of bulk account creation."""
        memory_profiler.reset_baseline()
        accounts = self.create_test_accounts(100)

        with patch("app.adapters.accounts.get_sync_session") as mock_session:
            mock_db = MagicMock()
            mock_session.return_value.__enter__.return_value = mock_db
            mock_db.query.return_value.filter.return_value.first.return_value = None

            profiler.start("bulk_creation")

            for account in accounts:
                db_adapter.put_account(account)

            duration = profiler.end("bulk_creation")

            # Performance assertions
            assert duration < 5.0, (
                f"Bulk creation took {duration:.3f}s, expected < 5.0s"
            )
            assert mock_db.add.call_count == 100
            assert mock_db.commit.call_count == 100

            # Memory usage should be reasonable
            memory_delta = memory_profiler.get_memory_delta()
            assert memory_delta < 50.0, (
                f"Memory usage increased by {memory_delta:.1f}MB"
            )

            stats = profiler.get_stats("bulk_creation")
            print(f"Bulk creation stats: {stats}")

    @pytest.mark.performance
    def test_concurrent_account_operations_performance(self, db_adapter, profiler):
        """Test performance of concurrent account operations."""
        accounts = self.create_test_accounts(50)
        results = []
        errors = []

        def account_worker(worker_accounts: list[Account]):
            """Worker function for concurrent operations."""
            worker_results = []
            try:
                with patch("app.adapters.accounts.get_sync_session") as mock_session:
                    mock_db = MagicMock()
                    mock_session.return_value.__enter__.return_value = mock_db
                    mock_db.query.return_value.filter.return_value.first.return_value = None

                    start_time = time.time()

                    for account in worker_accounts:
                        db_adapter.put_account(account)
                        retrieved = db_adapter.get_account(account.id)
                        worker_results.append((account.id, retrieved is not None))

                    end_time = time.time()
                    return worker_results, end_time - start_time

            except Exception as e:
                errors.append(str(e))
                return [], 0.0

        # Split accounts among workers
        chunk_size = 10
        account_chunks = [
            accounts[i : i + chunk_size] for i in range(0, len(accounts), chunk_size)
        ]

        profiler.start("concurrent_operations")

        with ThreadPoolExecutor(max_workers=5) as executor:
            futures = [
                executor.submit(account_worker, chunk) for chunk in account_chunks
            ]

            for future in as_completed(futures):
                worker_results, worker_duration = future.result()
                results.extend(worker_results)

        total_duration = profiler.end("concurrent_operations")

        # Performance assertions
        assert total_duration < 10.0, (
            f"Concurrent operations took {total_duration:.3f}s"
        )
        assert len(errors) == 0, f"Errors occurred: {errors}"
        assert len(results) == 50, f"Expected 50 results, got {len(results)}"

        # Verify all operations succeeded
        success_count = sum(1 for _, success in results if success)
        assert success_count >= 45, f"Only {success_count}/50 operations succeeded"

    @pytest.mark.performance
    def test_account_query_performance(self, db_adapter, profiler):
        """Test performance of account queries."""
        account_ids = [f"query-test-{i:06d}" for i in range(1000)]

        with patch("app.adapters.accounts.get_sync_session") as mock_session:
            mock_db = MagicMock()
            mock_session.return_value.__enter__.return_value = mock_db

            # Mock some accounts exist, some don't
            def mock_query_response(account_id: str):
                if hash(account_id) % 3 == 0:  # ~33% exist
                    mock_account = Mock()
                    mock_account.id = account_id
                    mock_account.cash_balance = 10000.0
                    mock_account.owner = "test_user"
                    return mock_account
                return None

            mock_db.query.return_value.filter.return_value.first.side_effect = (
                lambda: mock_query_response(
                    mock_db.query.return_value.filter.call_args[0][0]
                )
            )

            profiler.start("bulk_queries")

            found_count = 0
            for account_id in account_ids:
                account = db_adapter.get_account(account_id)
                if account:
                    found_count += 1

            duration = profiler.end("bulk_queries")

            # Performance assertions
            assert duration < 3.0, f"Bulk queries took {duration:.3f}s, expected < 3.0s"
            assert found_count > 300, f"Expected ~333 accounts found, got {found_count}"

            # Calculate queries per second
            qps = len(account_ids) / duration
            assert qps > 300, f"Query rate {qps:.1f} QPS too low, expected > 300 QPS"

    @pytest.mark.performance
    def test_memory_usage_scaling(self, db_adapter, memory_profiler):
        """Test memory usage scaling with data volume."""
        memory_profiler.reset_baseline()

        # Create increasingly large datasets
        dataset_sizes = [100, 500, 1000, 2000]
        memory_usage = []

        for size in dataset_sizes:
            accounts = self.create_test_accounts(size)

            with patch("app.adapters.accounts.get_sync_session") as mock_session:
                mock_db = MagicMock()
                mock_session.return_value.__enter__.return_value = mock_db
                mock_db.query.return_value.filter.return_value.first.return_value = None

                # Process accounts
                for account in accounts:
                    db_adapter.put_account(account)

                # Measure memory usage
                memory_delta = memory_profiler.get_memory_delta()
                memory_usage.append((size, memory_delta))

                # Clean up for next iteration
                del accounts
                gc.collect()

        # Verify memory usage grows reasonably
        for i in range(1, len(memory_usage)):
            prev_size, prev_memory = memory_usage[i - 1]
            curr_size, curr_memory = memory_usage[i]

            # Memory should scale somewhat linearly
            size_ratio = curr_size / prev_size
            memory_ratio = curr_memory / max(prev_memory, 1.0)  # Avoid division by zero

            # Memory growth should not be excessive
            assert memory_ratio < size_ratio * 2, (
                f"Memory growth too high: {memory_ratio:.2f}x for {size_ratio:.2f}x data"
            )

        print(f"Memory scaling: {memory_usage}")


class TestFileSystemAdapterPerformance:
    """Performance tests for file system adapter operations."""

    @pytest.fixture
    def temp_dir(self):
        """Create temporary directory for testing."""
        with tempfile.TemporaryDirectory() as temp_dir:
            yield temp_dir

    @pytest.fixture
    def file_adapter(self, temp_dir):
        """Create file system adapter."""
        return LocalFileSystemAccountAdapter(root_path=temp_dir)

    @pytest.fixture
    def profiler(self):
        """Create performance profiler."""
        return PerformanceProfiler()

    def create_test_accounts(self, count: int) -> list[Account]:
        """Create test accounts for performance testing."""
        accounts = []
        for i in range(count):
            account = Account(
                id=f"file-perf-{i:06d}",
                cash_balance=float(5000 + i * 50),
                positions=[],
                name=f"File Performance Test Account {i}",
                owner=f"file_user_{i}",
            )
            accounts.append(account)
        return accounts

    @pytest.mark.performance
    def test_file_io_throughput(self, file_adapter, profiler):
        """Test file I/O throughput performance."""
        accounts = self.create_test_accounts(200)

        profiler.start("file_writes")

        for account in accounts:
            file_adapter.put_account(account)

        write_duration = profiler.end("file_writes")

        # Test read throughput
        profiler.start("file_reads")

        for account in accounts:
            retrieved = file_adapter.get_account(account.id)
            assert retrieved is not None

        read_duration = profiler.end("file_reads")

        # Performance assertions
        assert write_duration < 3.0, (
            f"File writes took {write_duration:.3f}s, expected < 3.0s"
        )
        assert read_duration < 2.0, (
            f"File reads took {read_duration:.3f}s, expected < 2.0s"
        )

        # Calculate throughput
        write_throughput = len(accounts) / write_duration
        read_throughput = len(accounts) / read_duration

        assert write_throughput > 60, (
            f"Write throughput {write_throughput:.1f} ops/s too low"
        )
        assert read_throughput > 90, (
            f"Read throughput {read_throughput:.1f} ops/s too low"
        )

        print(
            f"File I/O throughput - Write: {write_throughput:.1f} ops/s, Read: {read_throughput:.1f} ops/s"
        )

    @pytest.mark.performance
    def test_concurrent_file_operations(self, file_adapter, profiler):
        """Test concurrent file operations performance."""
        accounts = self.create_test_accounts(100)
        results = []
        errors = []

        def file_worker(worker_accounts: list[Account]):
            """Worker function for concurrent file operations."""
            worker_results = []
            try:
                start_time = time.time()

                for account in worker_accounts:
                    file_adapter.put_account(account)
                    retrieved = file_adapter.get_account(account.id)
                    worker_results.append((account.id, retrieved is not None))

                end_time = time.time()
                return worker_results, end_time - start_time

            except Exception as e:
                errors.append(str(e))
                return [], 0.0

        # Split accounts among workers
        chunk_size = 20
        account_chunks = [
            accounts[i : i + chunk_size] for i in range(0, len(accounts), chunk_size)
        ]

        profiler.start("concurrent_file_ops")

        with ThreadPoolExecutor(max_workers=5) as executor:
            futures = [executor.submit(file_worker, chunk) for chunk in account_chunks]

            for future in as_completed(futures):
                worker_results, worker_duration = future.result()
                results.extend(worker_results)

        total_duration = profiler.end("concurrent_file_ops")

        # Performance assertions
        assert total_duration < 8.0, (
            f"Concurrent file operations took {total_duration:.3f}s"
        )
        assert len(errors) <= 1, (
            f"Too many errors: {errors}"
        )  # Allow for some file contention
        assert len(results) >= 95, f"Expected ~100 results, got {len(results)}"

        # Verify most operations succeeded
        success_count = sum(1 for _, success in results if success)
        assert success_count >= 90, (
            f"Only {success_count}/{len(results)} operations succeeded"
        )

    @pytest.mark.performance
    def test_large_file_handling(self, file_adapter, profiler, memory_profiler):
        """Test handling of large account files."""
        memory_profiler.reset_baseline()

        # Create accounts with large data
        large_accounts = []
        for i in range(50):
            # Simulate large position data
            large_data = "x" * 10000  # 10KB per account
            account = Account(
                id=f"large-file-{i:06d}",
                cash_balance=float(50000 + i * 1000),
                positions=[],  # Would be large in real scenario
                name=f"Large File Test Account {i} - {large_data[:100]}...",
                owner=f"large_user_{i}",
            )
            large_accounts.append(account)

        profiler.start("large_file_operations")

        # Write large files
        for account in large_accounts:
            file_adapter.put_account(account)

        # Read them back
        retrieved_count = 0
        for account in large_accounts:
            retrieved = file_adapter.get_account(account.id)
            if retrieved:
                retrieved_count += 1

        duration = profiler.end("large_file_operations")

        # Performance assertions
        assert duration < 5.0, f"Large file operations took {duration:.3f}s"
        assert retrieved_count == len(large_accounts), (
            f"Only retrieved {retrieved_count}/{len(large_accounts)} accounts"
        )

        # Memory usage should be reasonable
        memory_delta = memory_profiler.get_memory_delta()
        assert memory_delta < 100.0, f"Memory usage increased by {memory_delta:.1f}MB"

    @pytest.mark.performance
    def test_directory_scanning_performance(self, file_adapter, profiler):
        """Test performance of directory scanning operations."""
        # Create many files
        accounts = self.create_test_accounts(500)
        for account in accounts:
            file_adapter.put_account(account)

        # Test get_account_ids performance (directory scan)
        profiler.start("directory_scan")

        account_ids = file_adapter.get_account_ids()

        duration = profiler.end("directory_scan")

        # Performance assertions
        assert duration < 1.0, f"Directory scan took {duration:.3f}s, expected < 1.0s"
        assert len(account_ids) == len(accounts), (
            f"Expected {len(accounts)} IDs, got {len(account_ids)}"
        )

        # Test multiple scans (caching effectiveness)
        profiler.start("repeated_scans")

        for _ in range(10):
            ids = file_adapter.get_account_ids()
            assert len(ids) == len(accounts)

        repeated_duration = profiler.end("repeated_scans")

        # Repeated scans should be consistent
        average_scan_time = repeated_duration / 10
        assert average_scan_time < 0.2, (
            f"Average scan time {average_scan_time:.3f}s too high"
        )


class TestCachePerformance:
    """Performance tests for cache operations."""

    @pytest.fixture
    def cache(self):
        """Create cache for performance testing."""
        return QuoteCache(default_ttl=300.0, max_size=10000)

    @pytest.fixture
    def profiler(self):
        """Create performance profiler."""
        return PerformanceProfiler()

    @pytest.fixture
    def memory_profiler(self):
        """Create memory profiler."""
        return MemoryProfiler()

    def create_test_quotes(self, count: int) -> list[Quote]:
        """Create test quotes for cache performance testing."""
        quotes = []
        for i in range(count):
            stock = Stock(symbol=f"PERF{i:04d}", name=f"Performance Test Stock {i}")
            quote = Quote(
                asset=stock,
                quote_date=datetime.now(),
                price=100.0 + i * 0.1,
                bid=99.9 + i * 0.1,
                ask=100.1 + i * 0.1,
                bid_size=100,
                ask_size=100,
                volume=1000000 + i * 1000,
            )
            quotes.append(quote)
        return quotes

    @pytest.mark.performance
    def test_cache_put_performance(self, cache, profiler, memory_profiler):
        """Test cache put operation performance."""
        memory_profiler.reset_baseline()
        quotes = self.create_test_quotes(5000)

        profiler.start("cache_puts")

        for i, quote in enumerate(quotes):
            cache.put(f"perf_quote_{i}", quote)

        duration = profiler.end("cache_puts")

        # Performance assertions
        assert duration < 2.0, f"Cache puts took {duration:.3f}s, expected < 2.0s"
        assert len(cache._cache) <= cache.max_size

        # Calculate put rate
        put_rate = len(quotes) / duration
        assert put_rate > 2500, (
            f"Put rate {put_rate:.1f} ops/s too low, expected > 2500 ops/s"
        )

        # Memory usage should be reasonable
        memory_delta = memory_profiler.get_memory_delta()
        assert memory_delta < 200.0, f"Memory usage increased by {memory_delta:.1f}MB"

        print(
            f"Cache put performance: {put_rate:.1f} ops/s, memory delta: {memory_delta:.1f}MB"
        )

    @pytest.mark.performance
    def test_cache_get_performance(self, cache, profiler):
        """Test cache get operation performance."""
        quotes = self.create_test_quotes(1000)

        # Populate cache
        for i, quote in enumerate(quotes):
            cache.put(f"get_perf_{i}", quote)

        # Test get performance
        profiler.start("cache_gets")

        hit_count = 0
        for i in range(10000):  # More gets than puts (realistic scenario)
            key = f"get_perf_{i % len(quotes)}"
            result = cache.get(key)
            if result is not None:
                hit_count += 1

        duration = profiler.end("cache_gets")

        # Performance assertions
        assert duration < 1.0, f"Cache gets took {duration:.3f}s, expected < 1.0s"
        assert hit_count >= 9000, f"Hit count {hit_count} too low, expected >= 9000"

        # Calculate get rate
        get_rate = 10000 / duration
        assert get_rate > 10000, (
            f"Get rate {get_rate:.1f} ops/s too low, expected > 10000 ops/s"
        )

        # Verify hit rate
        stats = cache.get_stats()
        assert stats["hit_rate"] > 0.9, f"Hit rate {stats['hit_rate']:.3f} too low"

        print(
            f"Cache get performance: {get_rate:.1f} ops/s, hit rate: {stats['hit_rate']:.3f}"
        )

    @pytest.mark.performance
    def test_cache_cleanup_performance(self, cache, profiler):
        """Test cache cleanup operation performance."""
        # Fill cache with items with different TTLs
        for i in range(2000):
            ttl = 0.1 if i % 3 == 0 else 300.0  # 1/3 will expire quickly
            cache.put(f"cleanup_test_{i}", f"value_{i}", ttl=ttl)

        # Wait for some items to expire
        time.sleep(0.2)

        profiler.start("cache_cleanup")

        # Force cleanup
        removed_count = cache._cleanup_expired()

        duration = profiler.end("cache_cleanup")

        # Performance assertions
        assert duration < 0.5, f"Cache cleanup took {duration:.3f}s, expected < 0.5s"
        assert removed_count > 600, (
            f"Removed count {removed_count} too low, expected > 600"
        )

        # Cache size should be reduced
        assert len(cache._cache) < 1400, (
            f"Cache size {len(cache._cache)} still too large"
        )

        print(
            f"Cache cleanup performance: removed {removed_count} items in {duration:.3f}s"
        )

    @pytest.mark.performance
    def test_concurrent_cache_access(self, cache, profiler):
        """Test concurrent cache access performance."""
        quotes = self.create_test_quotes(100)

        # Pre-populate cache
        for i, quote in enumerate(quotes):
            cache.put(f"concurrent_{i}", quote)

        results = []
        errors = []

        def cache_worker(worker_id: int, operation_count: int):
            """Worker function for concurrent cache operations."""
            worker_stats = {"hits": 0, "misses": 0, "puts": 0}
            try:
                for i in range(operation_count):
                    if i % 3 == 0:  # 1/3 puts, 2/3 gets
                        key = f"worker_{worker_id}_item_{i}"
                        cache.put(key, f"value_{worker_id}_{i}")
                        worker_stats["puts"] += 1
                    else:
                        key = f"concurrent_{i % len(quotes)}"
                        result = cache.get(key)
                        if result is not None:
                            worker_stats["hits"] += 1
                        else:
                            worker_stats["misses"] += 1

                return worker_stats

            except Exception as e:
                errors.append(f"Worker {worker_id}: {e!s}")
                return worker_stats

        profiler.start("concurrent_cache")

        with ThreadPoolExecutor(max_workers=8) as executor:
            futures = [
                executor.submit(cache_worker, worker_id, 500) for worker_id in range(8)
            ]

            for future in as_completed(futures):
                worker_stats = future.result()
                results.append(worker_stats)

        duration = profiler.end("concurrent_cache")

        # Performance assertions
        assert duration < 3.0, f"Concurrent cache operations took {duration:.3f}s"
        assert len(errors) == 0, f"Errors occurred: {errors}"
        assert len(results) == 8, f"Expected 8 worker results, got {len(results)}"

        # Aggregate statistics
        total_ops = sum(
            stats["hits"] + stats["misses"] + stats["puts"] for stats in results
        )
        ops_per_second = total_ops / duration

        assert ops_per_second > 5000, (
            f"Concurrent ops rate {ops_per_second:.1f} ops/s too low"
        )

        print(
            f"Concurrent cache performance: {ops_per_second:.1f} ops/s with 8 workers"
        )

    @pytest.mark.performance
    def test_cache_memory_efficiency(self, cache, memory_profiler):
        """Test cache memory efficiency."""
        memory_profiler.reset_baseline()

        # Add progressively more items
        item_counts = [1000, 2000, 5000, 8000]
        memory_measurements = []

        for count in item_counts:
            # Clear cache first
            cache.clear()
            gc.collect()
            memory_profiler.reset_baseline()

            # Add items
            for i in range(count):
                cache.put(f"memory_test_{i}", f"value_{i}")

            memory_delta = memory_profiler.get_memory_delta()
            memory_measurements.append((count, memory_delta))

            # Memory efficiency check
            memory_per_item = memory_delta / count if count > 0 else 0
            assert memory_per_item < 0.01, (
                f"Memory per item {memory_per_item:.6f}MB too high at count {count}"
            )

        print(f"Cache memory efficiency: {memory_measurements}")


class TestAdapterFactoryPerformance:
    """Performance tests for adapter factory operations."""

    @pytest.fixture
    def factory(self):
        """Create adapter factory."""
        return AdapterFactory()

    @pytest.fixture
    def profiler(self):
        """Create performance profiler."""
        return PerformanceProfiler()

    @pytest.mark.performance
    def test_adapter_creation_performance(self, factory, profiler):
        """Test adapter creation performance."""
        profiler.start("adapter_creation")

        adapters = []
        for _i in range(100):
            adapter = factory.create_adapter("test_data")
            if adapter:
                adapters.append(adapter)

        duration = profiler.end("adapter_creation")

        # Performance assertions
        assert duration < 3.0, f"Adapter creation took {duration:.3f}s, expected < 3.0s"
        assert len(adapters) == 100, f"Expected 100 adapters, got {len(adapters)}"

        # Calculate creation rate
        creation_rate = len(adapters) / duration
        assert creation_rate > 30, (
            f"Creation rate {creation_rate:.1f} adapters/s too low"
        )

        print(f"Adapter creation performance: {creation_rate:.1f} adapters/s")

    @pytest.mark.performance
    def test_cached_adapter_creation_performance(self, factory, profiler):
        """Test cached adapter creation performance."""
        profiler.start("cached_adapter_creation")

        cached_adapters = []
        for _i in range(50):
            cached_adapter = factory.create_cached_adapter("test_data")
            if cached_adapter:
                cached_adapters.append(cached_adapter)

        duration = profiler.end("cached_adapter_creation")

        # Performance assertions
        assert duration < 2.0, f"Cached adapter creation took {duration:.3f}s"
        assert len(cached_adapters) == 50, (
            f"Expected 50 cached adapters, got {len(cached_adapters)}"
        )

        # Verify all are properly cached
        for cached_adapter in cached_adapters:
            assert isinstance(cached_adapter, CachedQuoteAdapter)
            assert cached_adapter.adapter is not None
            assert cached_adapter.cache is not None

    @pytest.mark.performance
    @pytest.mark.asyncio
    async def test_cache_warming_performance(self, factory, profiler):
        """Test cache warming performance."""
        adapter = factory.create_adapter("test_data")
        assert adapter is not None

        # Mock the adapter's get_quote method for performance
        async def mock_get_quote(asset):
            # Simulate some processing time
            await asyncio.sleep(0.001)  # 1ms per quote
            return Quote(
                asset=asset,
                quote_date=datetime.now(),
                price=100.0,
                bid=99.5,
                ask=100.5,
                bid_size=100,
                ask_size=100,
                volume=1000000,
            )

        with patch.object(adapter, "get_quote", side_effect=mock_get_quote):
            symbols = [f"WARM{i:03d}" for i in range(100)]

            profiler.start("cache_warming")

            stats = await factory.warm_cache(adapter, symbols)

            duration = profiler.end("cache_warming")

            # Performance assertions
            assert duration < 10.0, (
                f"Cache warming took {duration:.3f}s, expected < 10.0s"
            )
            assert stats["total_symbols"] == 100
            assert stats["successful"] >= 95  # Allow for some failures

            # Calculate warming rate
            warming_rate = stats["total_symbols"] / duration
            assert warming_rate > 10, (
                f"Warming rate {warming_rate:.1f} symbols/s too low"
            )

            print(
                f"Cache warming performance: {warming_rate:.1f} symbols/s, success rate: {stats['successful']}/{stats['total_symbols']}"
            )


class TestScalabilityLimits:
    """Test scalability limits of adapter systems."""

    @pytest.fixture
    def memory_profiler(self):
        """Create memory profiler."""
        return MemoryProfiler()

    @pytest.mark.performance
    def test_maximum_cache_size_handling(self, memory_profiler):
        """Test handling of maximum cache sizes."""
        memory_profiler.reset_baseline()

        # Test increasingly large cache sizes
        cache_sizes = [1000, 5000, 10000, 20000]
        performance_results = []

        for max_size in cache_sizes:
            cache = QuoteCache(default_ttl=300.0, max_size=max_size)

            start_time = time.time()

            # Fill cache to capacity
            for i in range(max_size):
                cache.put(f"scale_test_{i}", f"value_{i}")

            fill_time = time.time() - start_time

            # Test access performance
            start_time = time.time()

            hit_count = 0
            for i in range(min(1000, max_size)):  # Test subset for performance
                result = cache.get(f"scale_test_{i}")
                if result is not None:
                    hit_count += 1

            access_time = time.time() - start_time

            memory_delta = memory_profiler.get_memory_delta()
            memory_profiler.reset_baseline()

            performance_results.append(
                {
                    "cache_size": max_size,
                    "fill_time": fill_time,
                    "access_time": access_time,
                    "memory_usage": memory_delta,
                    "hit_rate": hit_count / min(1000, max_size),
                }
            )

            # Performance should degrade gracefully
            assert fill_time < max_size * 0.001, (
                f"Fill time {fill_time:.3f}s too high for size {max_size}"
            )
            assert access_time < 1.0, (
                f"Access time {access_time:.3f}s too high for size {max_size}"
            )
            assert hit_rate > 0.95, (
                f"Hit rate {hit_rate:.3f} too low for size {max_size}"
            )

        print(f"Scalability test results: {performance_results}")

    @pytest.mark.performance
    def test_concurrent_user_simulation(self):
        """Test system behavior under concurrent user load."""
        user_count = 20
        operations_per_user = 50

        # Shared resources
        cache = QuoteCache(default_ttl=60.0, max_size=5000)

        results = []
        errors = []

        def simulate_user(user_id: int):
            """Simulate user operations."""
            user_stats = {"operations": 0, "cache_hits": 0, "cache_misses": 0}

            try:
                for i in range(operations_per_user):
                    # Mix of cache operations
                    if i % 3 == 0:  # Write operation
                        cache.put(f"user_{user_id}_data_{i}", f"data_{user_id}_{i}")
                        user_stats["operations"] += 1
                    else:  # Read operation
                        key = f"user_{user_id}_data_{i // 2}"  # Some cache hits
                        result = cache.get(key)
                        if result is not None:
                            user_stats["cache_hits"] += 1
                        else:
                            user_stats["cache_misses"] += 1
                        user_stats["operations"] += 1

                return user_stats

            except Exception as e:
                errors.append(f"User {user_id}: {e!s}")
                return user_stats

        start_time = time.time()

        with ThreadPoolExecutor(max_workers=user_count) as executor:
            futures = [
                executor.submit(simulate_user, user_id) for user_id in range(user_count)
            ]

            for future in as_completed(futures):
                user_stats = future.result()
                results.append(user_stats)

        end_time = time.time()
        total_duration = end_time - start_time

        # Analyze results
        total_operations = sum(stats["operations"] for stats in results)
        total_cache_hits = sum(stats["cache_hits"] for stats in results)
        total_cache_misses = sum(stats["cache_misses"] for stats in results)

        # Performance assertions
        assert total_duration < 10.0, (
            f"Concurrent simulation took {total_duration:.3f}s"
        )
        assert len(errors) == 0, f"Errors occurred: {errors}"
        assert len(results) == user_count, (
            f"Expected {user_count} users, got {len(results)}"
        )

        # Calculate metrics
        ops_per_second = total_operations / total_duration
        cache_hit_rate = (
            total_cache_hits / (total_cache_hits + total_cache_misses)
            if (total_cache_hits + total_cache_misses) > 0
            else 0
        )

        assert ops_per_second > 500, (
            f"Operations rate {ops_per_second:.1f} ops/s too low"
        )
        assert cache_hit_rate > 0.3, f"Cache hit rate {cache_hit_rate:.3f} too low"

        print(
            f"Concurrent user simulation: {user_count} users, {ops_per_second:.1f} ops/s, {cache_hit_rate:.3f} hit rate"
        )

    @pytest.mark.performance
    def test_resource_cleanup_efficiency(self, memory_profiler):
        """Test efficiency of resource cleanup operations."""
        memory_profiler.reset_baseline()

        # Create and destroy resources repeatedly
        cleanup_cycles = 10
        items_per_cycle = 1000

        cleanup_times = []

        for cycle in range(cleanup_cycles):
            # Create resources
            cache = QuoteCache(default_ttl=0.1, max_size=items_per_cycle)  # Short TTL

            for i in range(items_per_cycle):
                cache.put(f"cleanup_cycle_{cycle}_item_{i}", f"data_{i}")

            # Wait for expiration
            time.sleep(0.2)

            # Measure cleanup time
            start_time = time.time()
            removed_count = cache._cleanup_expired()
            cleanup_time = time.time() - start_time

            cleanup_times.append(cleanup_time)

            # Verify cleanup effectiveness
            assert removed_count >= items_per_cycle * 0.9, (
                f"Cleanup removed only {removed_count}/{items_per_cycle} items"
            )
            assert cleanup_time < 0.5, f"Cleanup took {cleanup_time:.3f}s, too slow"

            # Clean up for next cycle
            del cache
            gc.collect()

        # Verify memory is being reclaimed
        final_memory = memory_profiler.get_memory_delta()
        assert final_memory < 50.0, (
            f"Memory increased by {final_memory:.1f}MB after cleanup cycles"
        )

        # Cleanup times should be consistent
        avg_cleanup_time = sum(cleanup_times) / len(cleanup_times)
        max_cleanup_time = max(cleanup_times)

        assert max_cleanup_time < avg_cleanup_time * 3, (
            f"Cleanup time variance too high: max {max_cleanup_time:.3f}s, avg {avg_cleanup_time:.3f}s"
        )

        print(
            f"Resource cleanup efficiency: avg {avg_cleanup_time:.3f}s, max {max_cleanup_time:.3f}s per {items_per_cycle} items"
        )
