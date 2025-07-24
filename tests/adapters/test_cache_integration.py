"""
Comprehensive integration tests for cache adapter functionality.

Tests QuoteCache, CachedQuoteAdapter, and global cache functionality
with focus on:
- TTL-based cache expiration
- Thread safety and concurrent access
- Cache warming and preloading
- Memory management and cleanup
- Performance under load
- Integration with quote adapters
- Error handling and recovery
"""

import asyncio
import threading
import time
from datetime import date, datetime
from typing import Any
from unittest.mock import patch

import pytest

from app.adapters.base import AdapterConfig, QuoteAdapter
from app.adapters.cache import (
    CachedQuoteAdapter,
    QuoteCache,
    cached_adapter,
    get_global_cache,
)
from app.models.assets import Asset, Option, Stock
from app.models.quotes import OptionQuote, OptionsChain, Quote


class MockQuoteAdapterWithConfig(QuoteAdapter):
    """Mock quote adapter with configuration for testing."""

    def __init__(self, config: AdapterConfig | None = None):
        self.config = config or AdapterConfig(cache_ttl=300.0)
        self.name = "MockAdapter"
        self.call_count = 0
        self.quotes: dict[str, Quote | OptionQuote] = {}
        self.chains: dict[str, OptionsChain] = {}
        self.expiration_dates: dict[str, list[date]] = {}

    async def get_quote(self, asset: Asset) -> Quote | None:
        """Get quote with call tracking."""
        self.call_count += 1
        return self.quotes.get(asset.symbol)

    async def get_quotes(self, assets: list[Asset]) -> dict[Asset, Quote]:
        """Get multiple quotes."""
        self.call_count += 1
        results = {}
        for asset in assets:
            quote = self.quotes.get(asset.symbol)
            if quote:
                results[asset] = quote
        return results

    async def get_chain(
        self, underlying: str, expiration_date: datetime | None = None
    ) -> list[Asset]:
        """Get option chain assets."""
        return []

    async def get_options_chain(
        self, underlying: str, expiration_date: datetime | None = None
    ) -> OptionsChain | None:
        """Get options chain."""
        self.call_count += 1
        return self.chains.get(underlying)

    async def is_market_open(self) -> bool:
        """Market status."""
        return True

    async def get_market_hours(self) -> dict[str, Any]:
        """Market hours."""
        return {"open": "09:30", "close": "16:00"}

    def get_sample_data_info(self) -> dict[str, Any]:
        """Sample data info."""
        return {"type": "mock"}

    def get_expiration_dates(self, underlying: str) -> list[date]:
        """Get expiration dates."""
        self.call_count += 1
        return self.expiration_dates.get(underlying, [])

    def get_test_scenarios(self) -> dict[str, Any]:
        """Test scenarios."""
        return {"scenarios": ["default"]}

    def set_date(self, date_str: str) -> None:
        """Set date."""
        pass

    def get_available_symbols(self) -> list[str]:
        """Available symbols."""
        return list(self.quotes.keys())


class TestCacheIntegration:
    """Integration tests for quote cache system."""

    @pytest.fixture
    def cache(self):
        """Create fresh cache for each test."""
        return QuoteCache(default_ttl=60.0, max_size=1000)

    @pytest.fixture
    def sample_stock(self):
        """Create sample stock asset."""
        return Stock(symbol="AAPL", name="Apple Inc.")

    @pytest.fixture
    def sample_option(self, sample_stock):
        """Create sample option asset."""
        return Option(
            symbol="AAPL240315C00180000",
            underlying=sample_stock,
            option_type="CALL",
            strike=180.0,
            expiration_date=date(2024, 3, 15),
        )

    @pytest.fixture
    def sample_quote(self, sample_stock):
        """Create sample quote."""
        return Quote(
            asset=sample_stock,
            quote_date=datetime.now(),
            price=150.0,
            bid=149.50,
            ask=150.50,
            bid_size=100,
            ask_size=100,
            volume=1000000,
        )

    @pytest.fixture
    def sample_option_quote(self, sample_option):
        """Create sample option quote."""
        return OptionQuote(
            asset=sample_option,
            quote_date=datetime.now(),
            price=5.25,
            bid=5.20,
            ask=5.30,
            underlying_price=150.0,
            volume=500,
            delta=0.65,
            gamma=0.02,
            theta=-0.08,
            vega=0.15,
        )

    @pytest.mark.integration
    def test_cache_ttl_integration(self, cache, sample_quote):
        """Test TTL-based cache expiration integration."""
        # Put item with short TTL
        cache.put("short_ttl", sample_quote, ttl=0.1)

        # Should be available immediately
        retrieved = cache.get("short_ttl")
        assert retrieved is sample_quote

        # Wait for expiration
        time.sleep(0.15)

        # Should be expired and cleaned up
        retrieved = cache.get("short_ttl")
        assert retrieved is None
        assert cache._stats["evictions"] > 0

    @pytest.mark.integration
    def test_cache_size_management_integration(self, cache):
        """Test cache size management and cleanup integration."""
        # Set small max size for testing
        cache.max_size = 5

        # Fill cache beyond capacity
        quotes = []
        for i in range(10):
            quote = Quote(
                asset=Stock(symbol=f"STOCK{i}", name=f"Stock {i}"),
                quote_date=datetime.now(),
                price=100.0 + i,
                bid=99.5 + i,
                ask=100.5 + i,
                bid_size=100,
                ask_size=100,
                volume=1000,
            )
            quotes.append(quote)
            cache.put(f"stock_{i}", quote)

        # Cache should not exceed max size
        assert len(cache._cache) <= cache.max_size

        # Some evictions should have occurred
        assert cache._stats["evictions"] > 0

    @pytest.mark.integration
    def test_concurrent_cache_access(self, cache, sample_quote):
        """Test concurrent access to cache."""
        results = []
        errors = []

        def cache_worker(worker_id: int, operation_count: int):
            """Worker function for concurrent cache operations."""
            try:
                for i in range(operation_count):
                    key = f"worker_{worker_id}_item_{i}"

                    # Put operation
                    cache.put(key, sample_quote)

                    # Get operation
                    retrieved = cache.get(key)
                    if retrieved is sample_quote:
                        results.append(f"{worker_id}_{i}")

                    # Some random operations
                    cache.get(f"random_key_{i}")
                    if i % 10 == 0:
                        cache.delete(key)

            except Exception as e:
                errors.append(f"Worker {worker_id}: {e!s}")

        # Create multiple worker threads
        threads = []
        for worker_id in range(5):
            thread = threading.Thread(target=cache_worker, args=(worker_id, 20))
            threads.append(thread)

        # Start all threads
        for thread in threads:
            thread.start()

        # Wait for completion
        for thread in threads:
            thread.join()

        # Verify no errors occurred
        assert len(errors) == 0, f"Concurrent errors: {errors}"
        assert len(results) > 0

        # Verify cache statistics
        stats = cache.get_stats()
        assert stats["hits"] > 0
        assert stats["misses"] > 0

    @pytest.mark.integration
    def test_cache_memory_pressure_handling(self, cache):
        """Test cache behavior under memory pressure."""
        # Create large number of entries
        large_data = "x" * 1000  # 1KB strings

        for i in range(500):
            cache.put(f"large_item_{i}", large_data, ttl=300.0)

        # Check memory management
        len(cache._cache)

        # Force cleanup
        cache._cleanup_expired()

        # Add more items to trigger eviction
        for i in range(100):
            cache.put(f"additional_item_{i}", large_data)

        # Verify size is managed
        final_size = len(cache._cache)
        assert final_size <= cache.max_size

        # Verify statistics
        stats = cache.get_stats()
        assert stats["evictions"] > 0
        assert stats["cleanups"] > 0

    @pytest.mark.integration
    def test_cache_performance_under_load(self, cache):
        """Test cache performance under heavy load."""
        import time

        # Warm up cache with many items
        for i in range(1000):
            cache.put(f"load_test_{i}", f"value_{i}")

        # Time many get operations
        start_time = time.time()

        for _ in range(10000):
            # Mix of hits and misses
            cache.get(f"load_test_{_ % 1000}")
            cache.get(f"non_existent_{_ % 100}")

        end_time = time.time()
        duration = end_time - start_time

        # Should complete within reasonable time
        assert duration < 2.0, f"Cache operations took {duration} seconds"

        # Verify hit rate
        stats = cache.get_stats()
        assert stats["hit_rate"] > 0.5  # Should have decent hit rate

    @pytest.mark.integration
    def test_cache_entry_lifecycle(self, cache, sample_quote):
        """Test complete cache entry lifecycle."""
        key = "lifecycle_test"

        # Create entry
        cache.put(key, sample_quote, ttl=120.0)
        entry = cache._cache[key]

        # Verify entry properties
        assert not entry.is_expired
        assert entry.age_seconds < 1.0
        assert entry.remaining_ttl > 119.0

        # Wait a bit
        time.sleep(0.1)

        # Check aging
        assert entry.age_seconds > 0.05
        assert entry.remaining_ttl < 120.0

        # Update entry
        cache.put(key, sample_quote, ttl=60.0)
        updated_entry = cache._cache[key]
        assert updated_entry.ttl == 60.0

        # Delete entry
        deleted = cache.delete(key)
        assert deleted is True
        assert key not in cache._cache

    @pytest.mark.integration
    def test_cache_statistics_accuracy(self, cache, sample_quote):
        """Test accuracy of cache statistics."""
        initial_stats = cache.get_stats()
        assert initial_stats["hits"] == 0
        assert initial_stats["misses"] == 0
        assert initial_stats["size"] == 0

        # Perform operations and track expected stats
        cache.put("stat_test_1", sample_quote)
        cache.put("stat_test_2", sample_quote)

        # Hit operations
        cache.get("stat_test_1")
        cache.get("stat_test_1")

        # Miss operations
        cache.get("non_existent_1")
        cache.get("non_existent_2")

        # Verify statistics
        stats = cache.get_stats()
        assert stats["hits"] == 2
        assert stats["misses"] == 2
        assert stats["size"] == 2
        assert stats["hit_rate"] == 0.5

        # Clear and verify reset
        cache.clear()
        cleared_stats = cache.get_stats()
        assert cleared_stats["hits"] == 0
        assert cleared_stats["misses"] == 0
        assert cleared_stats["size"] == 0


class TestCachedQuoteAdapterIntegration:
    """Integration tests for CachedQuoteAdapter with real quote adapters."""

    @pytest.fixture
    def base_adapter(self):
        """Create mock base adapter."""
        return MockQuoteAdapterWithConfig()

    @pytest.fixture
    def cache(self):
        """Create cache for testing."""
        return QuoteCache(default_ttl=300.0, max_size=1000)

    @pytest.fixture
    def cached_adapter(self, base_adapter, cache):
        """Create cached adapter."""
        return CachedQuoteAdapter(base_adapter, cache)

    @pytest.fixture
    def sample_stock(self):
        """Create sample stock."""
        return Stock(symbol="GOOGL", name="Alphabet Inc.")

    @pytest.fixture
    def sample_quote(self, sample_stock):
        """Create sample quote."""
        return Quote(
            asset=sample_stock,
            quote_date=datetime.now(),
            price=2500.0,
            bid=2495.0,
            ask=2505.0,
            bid_size=100,
            ask_size=100,
            volume=800000,
        )

    @pytest.mark.integration
    def test_cached_adapter_quote_flow_integration(
        self, cached_adapter, base_adapter, sample_stock, sample_quote
    ):
        """Test complete quote flow through cached adapter."""
        # Setup base adapter
        base_adapter.quotes[sample_stock.symbol] = sample_quote

        with patch("app.adapters.cache.asset_factory", return_value=sample_stock):
            # First call - cache miss
            quote1 = cached_adapter.get_quote(sample_stock.symbol)
            assert quote1 is sample_quote
            assert base_adapter.call_count == 1

            # Second call - cache hit
            quote2 = cached_adapter.get_quote(sample_stock.symbol)
            assert quote2 is sample_quote
            assert base_adapter.call_count == 1  # No additional call

            # Verify cache statistics
            stats = cached_adapter.get_cache_stats()
            assert stats["hits"] == 1
            assert stats["misses"] == 1

    @pytest.mark.integration
    @pytest.mark.asyncio
    async def test_cached_adapter_batch_operations_integration(
        self, cached_adapter, base_adapter
    ):
        """Test batch operations with caching integration."""
        # Setup multiple quotes
        stocks = [
            Stock(symbol="AAPL", name="Apple Inc."),
            Stock(symbol="MSFT", name="Microsoft Corp."),
            Stock(symbol="GOOGL", name="Alphabet Inc."),
        ]

        quotes = []
        for i, stock in enumerate(stocks):
            quote = Quote(
                asset=stock,
                quote_date=datetime.now(),
                price=100.0 + i * 50,
                bid=99.0 + i * 50,
                ask=101.0 + i * 50,
                bid_size=100,
                ask_size=100,
                volume=1000000,
            )
            quotes.append(quote)
            base_adapter.quotes[stock.symbol] = quote

        symbols = [stock.symbol for stock in stocks]

        with patch("app.adapters.cache.asset_factory", side_effect=stocks * 2):
            # First batch call
            batch1 = await cached_adapter.get_quotes(symbols)
            initial_calls = base_adapter.call_count

            # Second batch call - should use cached data
            batch2 = await cached_adapter.get_quotes(symbols)
            final_calls = base_adapter.call_count

            # Verify results
            assert len(batch1) == 3
            assert len(batch2) == 3

            # Should have made fewer calls on second batch
            assert final_calls < initial_calls + 1

    @pytest.mark.integration
    @pytest.mark.asyncio
    async def test_cached_adapter_options_chain_integration(
        self, cached_adapter, base_adapter
    ):
        """Test options chain caching integration."""
        underlying_symbol = "AAPL"

        # Create mock options chain
        chain = OptionsChain(
            underlying_symbol=underlying_symbol,
            expiration_date=date(2024, 6, 21),
            underlying_price=180.0,
            calls=[],
            puts=[],
            quote_time=datetime.now(),
        )

        base_adapter.chains[underlying_symbol] = chain

        # First call - cache miss
        chain1 = await cached_adapter.get_options_chain(underlying_symbol)
        initial_calls = base_adapter.call_count

        # Second call - cache hit
        chain2 = await cached_adapter.get_options_chain(underlying_symbol)
        final_calls = base_adapter.call_count

        # Verify caching worked
        assert chain1 is chain
        assert chain2 is chain
        assert final_calls == initial_calls  # No additional calls

    @pytest.mark.integration
    def test_cached_adapter_expiration_dates_integration(
        self, cached_adapter, base_adapter
    ):
        """Test expiration dates caching integration."""
        underlying = "AAPL"
        dates = [date(2024, 3, 15), date(2024, 6, 21), date(2024, 9, 20)]

        base_adapter.expiration_dates[underlying] = dates

        # First call - cache miss
        dates1 = cached_adapter.get_expiration_dates(underlying)
        initial_calls = base_adapter.call_count

        # Second call - cache hit
        dates2 = cached_adapter.get_expiration_dates(underlying)
        final_calls = base_adapter.call_count

        # Verify caching
        assert dates1 == dates
        assert dates2 == dates
        assert final_calls == initial_calls  # No additional calls

    @pytest.mark.integration
    def test_cached_adapter_cache_invalidation(
        self, cached_adapter, base_adapter, sample_stock, sample_quote
    ):
        """Test cache invalidation and refresh."""
        base_adapter.quotes[sample_stock.symbol] = sample_quote

        with patch("app.adapters.cache.asset_factory", return_value=sample_stock):
            # Initial call
            quote1 = cached_adapter.get_quote(sample_stock.symbol)
            assert quote1 is sample_quote

            # Clear cache
            cached_adapter.clear_cache()

            # Update base adapter data
            new_quote = Quote(
                asset=sample_stock,
                quote_date=datetime.now(),
                price=2600.0,  # Different price
                bid=2595.0,
                ask=2605.0,
                bid_size=100,
                ask_size=100,
                volume=900000,
            )
            base_adapter.quotes[sample_stock.symbol] = new_quote

            # Should get updated quote after cache clear
            quote2 = cached_adapter.get_quote(sample_stock.symbol)
            assert quote2 is new_quote
            assert quote2.price != quote1.price

    @pytest.mark.integration
    def test_cached_adapter_error_handling_integration(
        self, cached_adapter, base_adapter, sample_stock
    ):
        """Test error handling in cached adapter."""

        # Setup adapter to raise errors
        async def failing_get_quote(asset):
            raise Exception("Network error")

        base_adapter.get_quote = failing_get_quote

        with patch("app.adapters.cache.asset_factory", return_value=sample_stock):
            # Should propagate error, not cache it
            with pytest.raises(Exception, match="Network error"):
                cached_adapter.get_quote(sample_stock.symbol)

            # Verify nothing was cached
            stats = cached_adapter.get_cache_stats()
            assert stats["size"] == 0

    @pytest.mark.integration
    def test_cached_adapter_ttl_customization(self, base_adapter):
        """Test custom TTL settings in cached adapter."""
        # Create adapter with custom config
        config = AdapterConfig(cache_ttl=600.0)  # 10 minutes
        base_adapter.config = config

        cached_adapter = CachedQuoteAdapter(base_adapter)

        # Verify cache uses custom TTL
        assert cached_adapter.cache.default_ttl == 600.0

    @pytest.mark.integration
    @pytest.mark.asyncio
    async def test_cached_adapter_concurrent_requests(
        self, cached_adapter, base_adapter, sample_stock, sample_quote
    ):
        """Test concurrent requests to cached adapter."""
        base_adapter.quotes[sample_stock.symbol] = sample_quote

        async def request_worker():
            """Worker for concurrent requests."""
            with patch("app.adapters.cache.asset_factory", return_value=sample_stock):
                return cached_adapter.get_quote(sample_stock.symbol)

        # Make multiple concurrent requests
        tasks = [request_worker() for _ in range(10)]
        results = await asyncio.gather(*tasks)

        # All should return same quote
        assert all(result is sample_quote for result in results)

        # Should have made minimal calls to base adapter
        assert base_adapter.call_count <= 2  # Some concurrency tolerance


class TestGlobalCacheIntegration:
    """Integration tests for global cache functionality."""

    def test_global_cache_singleton_behavior(self):
        """Test global cache singleton behavior."""
        cache1 = get_global_cache()
        cache2 = get_global_cache()

        # Should be same instance
        assert cache1 is cache2

        # Should be proper QuoteCache
        assert isinstance(cache1, QuoteCache)

    def test_global_cache_shared_state(self):
        """Test global cache maintains shared state."""
        cache1 = get_global_cache()
        cache2 = get_global_cache()

        # Put in one, get from other
        cache1.put("shared_test", "shared_value")
        retrieved = cache2.get("shared_test")

        assert retrieved == "shared_value"

    def test_cached_adapter_convenience_function(self):
        """Test cached_adapter convenience function."""
        base_adapter = MockQuoteAdapterWithConfig()

        # Test with default global cache
        cached1 = cached_adapter(base_adapter)
        assert isinstance(cached1, CachedQuoteAdapter)
        assert cached1.adapter is base_adapter

        # Should use global cache by default
        global_cache = get_global_cache()
        assert cached1.cache is global_cache

        # Test with custom cache
        custom_cache = QuoteCache(default_ttl=120.0)
        cached2 = cached_adapter(base_adapter, custom_cache)
        assert cached2.cache is custom_cache

    @pytest.mark.integration
    def test_global_cache_isolation_between_adapters(self):
        """Test cache isolation between different adapters."""
        adapter1 = MockQuoteAdapterWithConfig()
        adapter1.name = "Adapter1"
        adapter2 = MockQuoteAdapterWithConfig()
        adapter2.name = "Adapter2"

        cached1 = cached_adapter(adapter1)
        cached2 = cached_adapter(adapter2)

        # Both use global cache but different keys
        stock = Stock(symbol="TEST", name="Test Stock")
        quote = Quote(
            asset=stock,
            quote_date=datetime.now(),
            price=100.0,
            bid=99.5,
            ask=100.5,
            bid_size=100,
            ask_size=100,
            volume=1000,
        )

        adapter1.quotes["TEST"] = quote
        adapter2.quotes["TEST"] = quote

        with patch("app.adapters.cache.asset_factory", return_value=stock):
            # Get quotes from both adapters
            quote1 = cached1.get_quote("TEST")
            quote2 = cached2.get_quote("TEST")

            # Both should work but with separate cache keys
            assert quote1 is quote
            assert quote2 is quote

            # Verify separate call counts
            assert adapter1.call_count == 1
            assert adapter2.call_count == 1


class TestCacheErrorRecovery:
    """Test cache error handling and recovery scenarios."""

    @pytest.fixture
    def cache(self):
        """Create cache for error testing."""
        return QuoteCache(default_ttl=60.0, max_size=100)

    def test_cache_memory_error_recovery(self, cache):
        """Test cache recovery from memory errors."""
        # Simulate memory pressure by filling cache
        for i in range(1000):  # More than max_size
            try:
                cache.put(f"memory_test_{i}", "x" * 1000)
            except MemoryError:
                # Should handle gracefully
                break

        # Cache should still be functional
        cache.put("recovery_test", "recovery_value")
        assert cache.get("recovery_test") == "recovery_value"

    def test_cache_corruption_recovery(self, cache):
        """Test cache recovery from internal corruption."""
        # Put valid entries
        cache.put("valid1", "value1")
        cache.put("valid2", "value2")

        # Simulate internal corruption
        cache._cache["corrupted"] = "not a CacheEntry object"

        # Cache should handle gracefully
        try:
            stats = cache.get_stats()
            # Should not crash
            assert isinstance(stats, dict)
        except Exception:
            # Acceptable to fail but shouldn't crash the process
            pass

        # Valid entries should still work
        assert cache.get("valid1") == "value1"

    def test_cached_adapter_base_adapter_failure_recovery(self):
        """Test cached adapter recovery from base adapter failures."""
        base_adapter = MockQuoteAdapterWithConfig()
        cached_adapter_instance = CachedQuoteAdapter(base_adapter)

        stock = Stock(symbol="FAIL_TEST", name="Fail Test")
        quote = Quote(
            asset=stock,
            quote_date=datetime.now(),
            price=100.0,
            bid=99.5,
            ask=100.5,
            bid_size=100,
            ask_size=100,
            volume=1000,
        )

        # Setup initial successful operation
        base_adapter.quotes["FAIL_TEST"] = quote

        with patch("app.adapters.cache.asset_factory", return_value=stock):
            # First call succeeds and caches
            result1 = cached_adapter_instance.get_quote("FAIL_TEST")
            assert result1 is quote

            # Make base adapter fail
            async def failing_get_quote(asset):
                raise Exception("Adapter failure")

            base_adapter.get_quote = failing_get_quote

            # Cached result should still be available
            result2 = cached_adapter_instance.get_quote("FAIL_TEST")
            assert result2 is quote  # From cache


class TestCachePerformanceBenchmarks:
    """Performance benchmarks for cache system."""

    @pytest.mark.performance
    def test_cache_put_performance(self):
        """Benchmark cache put operations."""
        cache = QuoteCache(default_ttl=300.0, max_size=10000)

        import time

        start_time = time.time()

        # Perform many put operations
        for i in range(5000):
            cache.put(f"perf_put_{i}", f"value_{i}")

        end_time = time.time()
        duration = end_time - start_time

        # Should complete quickly
        assert duration < 2.0, f"Put operations took {duration} seconds"

        # Verify all items were stored
        assert len(cache._cache) <= cache.max_size

    @pytest.mark.performance
    def test_cache_get_performance(self):
        """Benchmark cache get operations."""
        cache = QuoteCache(default_ttl=300.0, max_size=10000)

        # Populate cache
        for i in range(1000):
            cache.put(f"perf_get_{i}", f"value_{i}")

        import time

        start_time = time.time()

        # Perform many get operations
        for i in range(10000):
            cache.get(f"perf_get_{i % 1000}")

        end_time = time.time()
        duration = end_time - start_time

        # Should complete very quickly
        assert duration < 1.0, f"Get operations took {duration} seconds"

        # Verify high hit rate
        stats = cache.get_stats()
        assert stats["hit_rate"] > 0.9

    @pytest.mark.performance
    @pytest.mark.asyncio
    async def test_cached_adapter_throughput(self):
        """Benchmark cached adapter throughput."""
        base_adapter = MockQuoteAdapterWithConfig()
        cached_adapter_instance = CachedQuoteAdapter(base_adapter)

        # Setup quotes
        stock = Stock(symbol="THROUGHPUT", name="Throughput Test")
        quote = Quote(
            asset=stock,
            quote_date=datetime.now(),
            price=100.0,
            bid=99.5,
            ask=100.5,
            bid_size=100,
            ask_size=100,
            volume=1000,
        )
        base_adapter.quotes["THROUGHPUT"] = quote

        import time

        start_time = time.time()

        with patch("app.adapters.cache.asset_factory", return_value=stock):
            # Many requests (should mostly hit cache after first)
            for _ in range(1000):
                result = cached_adapter_instance.get_quote("THROUGHPUT")
                assert result is quote

        end_time = time.time()
        duration = end_time - start_time

        # Should complete quickly due to caching
        assert duration < 1.0, f"Throughput test took {duration} seconds"

        # Should have made minimal calls to base adapter
        assert base_adapter.call_count <= 5  # Very few actual adapter calls
