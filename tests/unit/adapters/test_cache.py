"""
Comprehensive tests for caching system with TTL support.
"""

import pytest
import time
import asyncio
from unittest.mock import Mock, patch, AsyncMock
from datetime import datetime

from app.adapters.cache import (
    CacheEntry,
    QuoteCache,
    CachedQuoteAdapter,
    get_global_cache,
    cached_adapter
)
from app.adapters.base import QuoteAdapter
from app.models.assets import Stock, Option
from app.models.quotes import Quote, OptionQuote, OptionsChain


class TestCacheEntry:
    """Test suite for CacheEntry class."""

    @pytest.fixture
    def sample_quote(self):
        """Create sample quote for testing."""
        stock = Stock(symbol="AAPL", name="Apple Inc.")
        return Quote(
            asset=stock,
            quote_date=datetime.now(),
            price=150.0,
            bid=149.50,
            ask=150.50,
            bid_size=100,
            ask_size=100,
            volume=1000000
        )

    def test_cache_entry_creation(self, sample_quote):
        """Test CacheEntry creation."""
        entry = CacheEntry(
            value=sample_quote,
            timestamp=time.time(),
            ttl=60.0
        )
        
        assert entry.value is sample_quote
        assert isinstance(entry.timestamp, float)
        assert entry.ttl == 60.0

    def test_cache_entry_is_expired_false(self, sample_quote):
        """Test CacheEntry is not expired when fresh."""
        entry = CacheEntry(
            value=sample_quote,
            timestamp=time.time(),
            ttl=60.0
        )
        
        assert not entry.is_expired

    def test_cache_entry_is_expired_true(self, sample_quote):
        """Test CacheEntry is expired when TTL exceeded."""
        entry = CacheEntry(
            value=sample_quote,
            timestamp=time.time() - 120.0,  # 2 minutes ago
            ttl=60.0  # 1 minute TTL
        )
        
        assert entry.is_expired

    def test_cache_entry_age_seconds(self, sample_quote):
        """Test CacheEntry age calculation."""
        start_time = time.time()
        entry = CacheEntry(
            value=sample_quote,
            timestamp=start_time,
            ttl=60.0
        )
        
        # Allow some time to pass
        time.sleep(0.01)
        
        age = entry.age_seconds
        assert age > 0
        assert age < 1.0  # Should be very small

    def test_cache_entry_remaining_ttl(self, sample_quote):
        """Test CacheEntry remaining TTL calculation."""
        entry = CacheEntry(
            value=sample_quote,
            timestamp=time.time(),
            ttl=60.0
        )
        
        remaining = entry.remaining_ttl
        assert remaining > 59.0  # Should be close to 60
        assert remaining <= 60.0

    def test_cache_entry_remaining_ttl_expired(self, sample_quote):
        """Test CacheEntry remaining TTL when expired."""
        entry = CacheEntry(
            value=sample_quote,
            timestamp=time.time() - 120.0,  # 2 minutes ago
            ttl=60.0  # 1 minute TTL
        )
        
        remaining = entry.remaining_ttl
        assert remaining == 0.0


class TestQuoteCache:
    """Test suite for QuoteCache class."""

    @pytest.fixture
    def cache(self):
        """Create fresh cache for each test."""
        return QuoteCache(default_ttl=60.0, max_size=100)

    @pytest.fixture
    def sample_quote(self):
        """Create sample quote for testing."""
        stock = Stock(symbol="AAPL", name="Apple Inc.")
        return Quote(
            asset=stock,
            quote_date=datetime.now(),
            price=150.0,
            bid=149.50,
            ask=150.50,
            bid_size=100,
            ask_size=100,
            volume=1000000
        )

    def test_cache_initialization(self, cache):
        """Test cache initialization."""
        assert cache.default_ttl == 60.0
        assert cache.max_size == 100
        assert len(cache._cache) == 0
        assert cache._stats["hits"] == 0
        assert cache._stats["misses"] == 0

    def test_cache_put_and_get(self, cache, sample_quote):
        """Test basic put and get operations."""
        cache.put("test_key", sample_quote)
        
        retrieved = cache.get("test_key")
        assert retrieved is sample_quote

    def test_cache_get_nonexistent(self, cache):
        """Test getting non-existent key."""
        retrieved = cache.get("nonexistent")
        assert retrieved is None

    def test_cache_get_expired(self, cache, sample_quote):
        """Test getting expired entry."""
        cache.put("test_key", sample_quote, ttl=0.01)  # Very short TTL
        
        # Wait for expiration
        time.sleep(0.02)
        
        retrieved = cache.get("test_key")
        assert retrieved is None
        assert cache._stats["evictions"] == 1

    def test_cache_put_custom_ttl(self, cache, sample_quote):
        """Test putting entry with custom TTL."""
        cache.put("test_key", sample_quote, ttl=120.0)
        
        # Verify entry has custom TTL
        entry = cache._cache["test_key"]
        assert entry.ttl == 120.0

    def test_cache_delete(self, cache, sample_quote):
        """Test deleting cache entry."""
        cache.put("test_key", sample_quote)
        assert cache.get("test_key") is not None
        
        result = cache.delete("test_key")
        assert result is True
        assert cache.get("test_key") is None

    def test_cache_delete_nonexistent(self, cache):
        """Test deleting non-existent entry."""
        result = cache.delete("nonexistent")
        assert result is False

    def test_cache_clear(self, cache, sample_quote):
        """Test clearing cache."""
        cache.put("key1", sample_quote)
        cache.put("key2", sample_quote)
        assert len(cache._cache) == 2
        
        cache.clear()
        assert len(cache._cache) == 0
        assert cache._stats["hits"] == 0
        assert cache._stats["misses"] == 0

    def test_cache_stats_tracking(self, cache, sample_quote):
        """Test cache statistics tracking."""
        # Test miss
        cache.get("nonexistent")
        assert cache._stats["misses"] == 1
        
        # Test put and hit
        cache.put("test_key", sample_quote)
        retrieved = cache.get("test_key")
        assert retrieved is sample_quote
        assert cache._stats["hits"] == 1

    def test_cache_cleanup_expired(self, cache, sample_quote):
        """Test cleanup of expired entries."""
        # Add entries with different TTLs
        cache.put("short_ttl", sample_quote, ttl=0.01)
        cache.put("long_ttl", sample_quote, ttl=60.0)
        
        # Wait for first entry to expire
        time.sleep(0.02)
        
        # Cleanup should remove expired entry
        removed_count = cache._cleanup_expired()
        assert removed_count == 1
        assert "short_ttl" not in cache._cache
        assert "long_ttl" in cache._cache

    def test_cache_evict_oldest(self, cache, sample_quote):
        """Test evicting oldest entries."""
        # Add multiple entries
        for i in range(5):
            cache.put(f"key_{i}", sample_quote)
            time.sleep(0.01)  # Ensure different timestamps
        
        # Evict 2 oldest
        evicted_count = cache._evict_oldest(2)
        assert evicted_count == 2
        assert len(cache._cache) == 3
        
        # Oldest entries should be gone
        assert "key_0" not in cache._cache
        assert "key_1" not in cache._cache
        assert "key_4" in cache._cache  # Newest should remain

    def test_cache_max_size_cleanup(self, cache, sample_quote):
        """Test automatic cleanup when max size reached."""
        # Set small max size for testing
        cache.max_size = 3
        
        # Add entries to exceed max size
        for i in range(5):
            cache.put(f"key_{i}", sample_quote)
        
        # Should not exceed max size
        assert len(cache._cache) <= cache.max_size

    def test_cache_get_stats(self, cache, sample_quote):
        """Test getting cache statistics."""
        # Generate some activity
        cache.put("key1", sample_quote)
        cache.get("key1")  # Hit
        cache.get("nonexistent")  # Miss
        
        stats = cache.get_stats()
        
        assert stats["size"] == 1
        assert stats["max_size"] == 100
        assert stats["hits"] == 1
        assert stats["misses"] == 1
        assert stats["hit_rate"] == 0.5
        assert stats["default_ttl"] == 60.0

    def test_cache_get_entries_info(self, cache, sample_quote):
        """Test getting cache entries information."""
        cache.put("key1", sample_quote, ttl=60.0)
        cache.put("key2", sample_quote, ttl=120.0)
        
        entries = cache.get_entries_info()
        
        assert len(entries) == 2
        assert all("key" in entry for entry in entries)
        assert all("age_seconds" in entry for entry in entries)
        assert all("ttl" in entry for entry in entries)
        assert all("remaining_ttl" in entry for entry in entries)
        assert all("value_type" in entry for entry in entries)

    def test_cache_thread_safety(self, cache, sample_quote):
        """Test cache thread safety with concurrent operations."""
        import threading
        
        def worker(thread_id):
            for i in range(10):
                key = f"thread_{thread_id}_key_{i}"
                cache.put(key, sample_quote)
                retrieved = cache.get(key)
                assert retrieved is sample_quote
        
        threads = []
        for i in range(5):
            thread = threading.Thread(target=worker, args=(i,))
            threads.append(thread)
            thread.start()
        
        for thread in threads:
            thread.join()
        
        # Should have entries from all threads
        assert len(cache._cache) > 0


class MockQuoteAdapter(QuoteAdapter):
    """Mock quote adapter for testing cached adapter."""

    def __init__(self):
        self.call_count = 0
        self.quotes = {}

    async def get_quote(self, asset):
        self.call_count += 1
        return self.quotes.get(asset.symbol)

    async def get_quotes(self, assets):
        self.call_count += 1
        results = {}
        for asset in assets:
            quote = self.quotes.get(asset.symbol)
            if quote:
                results[asset] = quote
        return results

    async def get_chain(self, underlying, expiration_date=None):
        self.call_count += 1
        return []

    async def get_options_chain(self, underlying, expiration_date=None):
        self.call_count += 1
        return None

    async def is_market_open(self):
        return True

    async def get_market_hours(self):
        return {"open": "09:30", "close": "16:00"}

    def get_sample_data_info(self):
        return {"type": "mock"}

    def get_expiration_dates(self, underlying):
        self.call_count += 1
        return []

    def get_test_scenarios(self):
        return {"scenarios": ["default"]}

    def set_date(self, date):
        pass

    def get_available_symbols(self):
        return list(self.quotes.keys())


class TestCachedQuoteAdapter:
    """Test suite for CachedQuoteAdapter."""

    @pytest.fixture
    def base_adapter(self):
        """Create mock base adapter."""
        return MockQuoteAdapter()

    @pytest.fixture
    def cache(self):
        """Create cache for testing."""
        return QuoteCache(default_ttl=60.0, max_size=100)

    @pytest.fixture
    def cached_adapter(self, base_adapter, cache):
        """Create cached adapter."""
        return CachedQuoteAdapter(base_adapter, cache)

    @pytest.fixture
    def sample_stock(self):
        """Create sample stock."""
        return Stock(symbol="AAPL", name="Apple Inc.")

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
            volume=1000000
        )

    def test_cached_adapter_initialization(self, cached_adapter, base_adapter, cache):
        """Test cached adapter initialization."""
        assert cached_adapter.adapter is base_adapter
        assert cached_adapter.cache is cache

    def test_cached_adapter_initialization_with_config(self, base_adapter):
        """Test cached adapter initialization with adapter config."""
        # Mock adapter with config
        base_adapter.config = Mock()
        base_adapter.config.cache_ttl = 300.0
        
        cached_adapter = CachedQuoteAdapter(base_adapter)
        
        assert cached_adapter.cache.default_ttl == 300.0

    def test_get_quote_cache_miss(self, cached_adapter, base_adapter, sample_stock, sample_quote):
        """Test get_quote with cache miss."""
        base_adapter.quotes["AAPL"] = sample_quote
        
        # Patch asset_factory to return the stock
        with patch('app.adapters.cache.asset_factory', return_value=sample_stock):
            quote = cached_adapter.get_quote("AAPL")
            
            assert quote is sample_quote
            assert base_adapter.call_count == 1

    def test_get_quote_cache_hit(self, cached_adapter, base_adapter, sample_stock, sample_quote):
        """Test get_quote with cache hit."""
        base_adapter.quotes["AAPL"] = sample_quote
        
        with patch('app.adapters.cache.asset_factory', return_value=sample_stock):
            # First call - cache miss
            quote1 = cached_adapter.get_quote("AAPL")
            
            # Second call - cache hit
            quote2 = cached_adapter.get_quote("AAPL")
            
            assert quote1 is sample_quote
            assert quote2 is sample_quote
            assert base_adapter.call_count == 1  # Should only call adapter once

    def test_get_quote_invalid_asset(self, cached_adapter):
        """Test get_quote with invalid asset."""
        with patch('app.adapters.cache.asset_factory', return_value=None):
            quote = cached_adapter.get_quote("INVALID")
            assert quote is None

    @pytest.mark.asyncio
    async def test_get_quotes_cache_performance(self, cached_adapter, base_adapter, sample_stock, sample_quote):
        """Test get_quotes with caching performance."""
        base_adapter.quotes["AAPL"] = sample_quote
        
        with patch('app.adapters.cache.asset_factory', return_value=sample_stock):
            # First call
            quotes1 = await cached_adapter.get_quotes(["AAPL"])
            
            # Second call - should use cache
            quotes2 = await cached_adapter.get_quotes(["AAPL"])
            
            assert quotes1["AAPL"] is sample_quote
            assert quotes2["AAPL"] is sample_quote
            # First call to get_quote (cache miss), second call to get_quotes
            assert base_adapter.call_count == 2

    @pytest.mark.asyncio
    async def test_get_quotes_mixed_cache_state(self, cached_adapter, base_adapter, sample_quote):
        """Test get_quotes with mixed cache state."""
        # Setup quotes in adapter
        stock1 = Stock(symbol="AAPL", name="Apple Inc.")
        stock2 = Stock(symbol="GOOGL", name="Alphabet Inc.")
        quote1 = sample_quote
        quote2 = Quote(
            asset=stock2,
            quote_date=datetime.now(),
            price=2500.0,
            bid=2495.0,
            ask=2505.0,
            bid_size=100,
            ask_size=100,
            volume=500000
        )
        
        base_adapter.quotes["AAPL"] = quote1
        base_adapter.quotes["GOOGL"] = quote2
        
        # Pre-cache one quote
        with patch('app.adapters.cache.asset_factory', side_effect=[stock1, stock1, stock2]):
            cached_adapter.get_quote("AAPL")  # Cache AAPL
            
            # Get quotes for both - AAPL from cache, GOOGL from adapter
            quotes = await cached_adapter.get_quotes(["AAPL", "GOOGL"])
            
            assert len(quotes) == 2
            assert quotes["AAPL"] is quote1
            assert quotes["GOOGL"] is quote2

    @pytest.mark.asyncio
    async def test_get_options_chain_caching(self, cached_adapter, base_adapter):
        """Test options chain caching."""
        mock_chain = OptionsChain(
            underlying_symbol="AAPL",
            expiration_date=datetime.now().date(),
            underlying_price=150.0,
            calls=[],
            puts=[],
            quote_time=datetime.now()
        )
        
        # Mock the adapter method
        base_adapter.get_options_chain = AsyncMock(return_value=mock_chain)
        
        # First call
        chain1 = await cached_adapter.get_options_chain("AAPL")
        
        # Second call - should use cache
        chain2 = await cached_adapter.get_options_chain("AAPL")
        
        assert chain1 is mock_chain
        assert chain2 is mock_chain
        # Should only call adapter once
        base_adapter.get_options_chain.assert_called_once()

    def test_get_expiration_dates_caching(self, cached_adapter, base_adapter):
        """Test expiration dates caching."""
        mock_dates = [datetime.now().date()]
        
        # Mock base adapter to return dates and track calls
        base_adapter.get_expiration_dates = Mock(return_value=mock_dates)
        
        # First call
        dates1 = cached_adapter.get_expiration_dates("AAPL")
        
        # Second call - should use cache
        dates2 = cached_adapter.get_expiration_dates("AAPL")
        
        assert dates1 is mock_dates
        assert dates2 is mock_dates
        # Should only call adapter once
        base_adapter.get_expiration_dates.assert_called_once()

    def test_clear_cache(self, cached_adapter, cache):
        """Test clearing cache."""
        # Add some entries to cache
        cache.put("test_key", "test_value")
        assert len(cache._cache) == 1
        
        cached_adapter.clear_cache()
        assert len(cache._cache) == 0

    def test_get_cache_stats(self, cached_adapter, cache):
        """Test getting cache statistics."""
        stats = cached_adapter.get_cache_stats()
        assert isinstance(stats, dict)
        assert "size" in stats
        assert "hits" in stats
        assert "misses" in stats

    def test_attribute_delegation(self, cached_adapter, base_adapter):
        """Test delegation of unknown attributes to base adapter."""
        # Access an attribute that should be delegated
        adapter_name = getattr(cached_adapter, 'name', None)
        base_name = getattr(base_adapter, 'name', None)
        
        # Should delegate to base adapter
        assert adapter_name == base_name

    def test_method_delegation(self, cached_adapter, base_adapter):
        """Test delegation of unknown methods to base adapter."""
        # Call a method that should be delegated
        scenarios = cached_adapter.get_test_scenarios()
        
        # Should return result from base adapter
        assert scenarios == {"scenarios": ["default"]}


class TestGlobalCache:
    """Test global cache functionality."""

    def test_get_global_cache(self):
        """Test getting global cache instance."""
        cache1 = get_global_cache()
        cache2 = get_global_cache()
        
        # Should return same instance
        assert cache1 is cache2
        assert isinstance(cache1, QuoteCache)

    def test_cached_adapter_function(self):
        """Test cached_adapter convenience function."""
        base_adapter = MockQuoteAdapter()
        
        cached = cached_adapter(base_adapter)
        
        assert isinstance(cached, CachedQuoteAdapter)
        assert cached.adapter is base_adapter

    def test_cached_adapter_function_with_custom_cache(self):
        """Test cached_adapter with custom cache."""
        base_adapter = MockQuoteAdapter()
        custom_cache = QuoteCache(default_ttl=120.0)
        
        cached = cached_adapter(base_adapter, custom_cache)
        
        assert cached.cache is custom_cache
        assert cached.cache.default_ttl == 120.0


class TestCacheErrorHandling:
    """Test error handling in cache system."""

    @pytest.fixture
    def cache(self):
        """Create cache for error testing."""
        return QuoteCache()

    def test_cache_with_none_values(self, cache):
        """Test cache handling of None values."""
        cache.put("test_key", None)
        
        retrieved = cache.get("test_key")
        assert retrieved is None

    def test_cache_with_invalid_ttl(self, cache):
        """Test cache with invalid TTL values."""
        # Negative TTL should work (immediate expiration)
        cache.put("test_key", "test_value", ttl=-1.0)
        
        retrieved = cache.get("test_key")
        assert retrieved is None  # Should be expired immediately

    def test_cache_cleanup_with_empty_cache(self, cache):
        """Test cleanup with empty cache."""
        removed = cache._cleanup_expired()
        assert removed == 0

    def test_cache_evict_with_empty_cache(self, cache):
        """Test eviction with empty cache."""
        evicted = cache._evict_oldest(5)
        assert evicted == 0

    def test_cached_adapter_with_adapter_error(self):
        """Test cached adapter when base adapter raises errors."""
        base_adapter = MockQuoteAdapter()
        cached = CachedQuoteAdapter(base_adapter)
        
        # Mock adapter to raise exception
        async def failing_get_quote(asset):
            raise Exception("Adapter error")
        
        base_adapter.get_quote = failing_get_quote
        
        with patch('app.adapters.cache.asset_factory', return_value=Stock(symbol="AAPL", name="Apple")):
            # Should propagate the exception
            with pytest.raises(Exception, match="Adapter error"):
                cached.get_quote("AAPL")

    def test_cached_adapter_without_optional_methods(self):
        """Test cached adapter when base adapter lacks optional methods."""
        base_adapter = MockQuoteAdapter()
        # Remove optional method
        delattr(base_adapter, 'get_expiration_dates')
        
        cached = CachedQuoteAdapter(base_adapter)
        
        # Should handle gracefully
        dates = cached.get_expiration_dates("AAPL")
        assert dates == []


class TestCachePerformance:
    """Performance tests for cache system."""

    def test_cache_performance_large_dataset(self):
        """Test cache performance with large dataset."""
        cache = QuoteCache(max_size=10000)
        
        # Add many entries
        start_time = time.time()
        
        for i in range(1000):
            cache.put(f"key_{i}", f"value_{i}")
        
        put_time = time.time() - start_time
        
        # Retrieve entries
        start_time = time.time()
        
        for i in range(1000):
            value = cache.get(f"key_{i}")
            assert value == f"value_{i}"
        
        get_time = time.time() - start_time
        
        # Should be reasonably fast
        assert put_time < 1.0
        assert get_time < 1.0

    def test_cache_memory_efficiency(self):
        """Test cache memory efficiency."""
        import sys
        
        cache = QuoteCache()
        
        # Measure initial size
        initial_size = sys.getsizeof(cache._cache)
        
        # Add entries
        for i in range(100):
            cache.put(f"key_{i}", f"short_value_{i}")
        
        # Measure final size
        final_size = sys.getsizeof(cache._cache)
        
        # Growth should be reasonable
        growth = final_size - initial_size
        assert growth > 0
        assert growth < 50000  # Less than 50KB for 100 small entries

    @pytest.mark.asyncio
    async def test_cached_adapter_concurrent_access(self):
        """Test cached adapter with concurrent access."""
        base_adapter = MockQuoteAdapter()
        cached = CachedQuoteAdapter(base_adapter)
        
        # Setup quotes
        stock = Stock(symbol="AAPL", name="Apple Inc.")
        quote = Quote(
            asset=stock,
            quote_date=datetime.now(),
            price=150.0,
            bid=149.50,
            ask=150.50,
            bid_size=100,
            ask_size=100,
            volume=1000000
        )
        base_adapter.quotes["AAPL"] = quote
        
        async def worker():
            with patch('app.adapters.cache.asset_factory', return_value=stock):
                return cached.get_quote("AAPL")
        
        # Run concurrent requests
        tasks = [worker() for _ in range(10)]
        results = await asyncio.gather(*tasks)
        
        # All should return the same quote
        assert all(result is quote for result in results)
        # Should only call base adapter once (first request)
        assert base_adapter.call_count == 1

    def test_cache_stats_performance(self):
        """Test cache statistics calculation performance."""
        cache = QuoteCache()
        
        # Add many entries and accesses
        for i in range(1000):
            cache.put(f"key_{i}", f"value_{i}")
            cache.get(f"key_{i}")
        
        # Getting stats should be fast
        start_time = time.time()
        stats = cache.get_stats()
        end_time = time.time()
        
        assert (end_time - start_time) < 0.1
        assert stats["hits"] == 1000
        assert stats["size"] == 1000