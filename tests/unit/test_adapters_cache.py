"""Tests for caching system (QuoteCache and CachedQuoteAdapter)."""

import pytest
import time
import threading
from unittest.mock import Mock, MagicMock, patch, AsyncMock
from datetime import datetime, date
from typing import Any, Dict, List

from app.adapters.cache import (
    CacheEntry,
    QuoteCache,
    CachedQuoteAdapter,
    get_global_cache,
    cached_adapter,
)
from app.adapters.base import QuoteAdapter, AdapterConfig
from app.models.assets import Stock, Option, Asset
from app.models.quotes import Quote, OptionQuote, OptionsChain


class TestCacheEntry:
    """Test CacheEntry functionality."""

    def test_cache_entry_creation(self):
        """Test creating a cache entry."""
        value = {"test": "data"}
        entry = CacheEntry(value=value, timestamp=time.time(), ttl=60.0)
        
        assert entry.value == value
        assert isinstance(entry.timestamp, float)
        assert entry.ttl == 60.0

    def test_cache_entry_not_expired(self):
        """Test that fresh cache entry is not expired."""
        entry = CacheEntry(value="test", timestamp=time.time(), ttl=60.0)
        
        assert not entry.is_expired
        assert entry.remaining_ttl > 0
        assert entry.age_seconds < 1.0

    def test_cache_entry_expired(self):
        """Test that old cache entry is expired."""
        old_timestamp = time.time() - 120.0  # 2 minutes ago
        entry = CacheEntry(value="test", timestamp=old_timestamp, ttl=60.0)
        
        assert entry.is_expired
        assert entry.remaining_ttl == 0.0
        assert entry.age_seconds >= 120.0

    def test_cache_entry_almost_expired(self):
        """Test cache entry that's almost expired."""
        almost_old_timestamp = time.time() - 59.0  # Almost expired
        entry = CacheEntry(value="test", timestamp=almost_old_timestamp, ttl=60.0)
        
        assert not entry.is_expired
        assert 0 < entry.remaining_ttl < 2.0
        assert 59.0 <= entry.age_seconds < 60.0

    def test_cache_entry_exactly_expired(self):
        """Test cache entry that's exactly at TTL boundary."""
        exact_timestamp = time.time() - 60.0  # Exactly TTL ago
        entry = CacheEntry(value="test", timestamp=exact_timestamp, ttl=60.0)
        
        # Should be expired (>= TTL)
        assert entry.is_expired
        assert entry.remaining_ttl == 0.0

    def test_cache_entry_properties_consistency(self):
        """Test that cache entry properties are consistent."""
        timestamp = time.time() - 30.0  # 30 seconds ago
        entry = CacheEntry(value="test", timestamp=timestamp, ttl=60.0)
        
        # Age + remaining should equal TTL (approximately)
        total_time = entry.age_seconds + entry.remaining_ttl
        assert abs(total_time - entry.ttl) < 0.1  # Allow small floating point errors


class TestQuoteCache:
    """Test QuoteCache functionality."""

    @pytest.fixture
    def cache(self):
        """Create a fresh cache instance."""
        return QuoteCache(default_ttl=60.0, max_size=100)

    def test_cache_initialization(self):
        """Test cache initialization with defaults."""
        cache = QuoteCache()
        
        assert cache.default_ttl == 60.0
        assert cache.max_size == 10000
        assert len(cache._cache) == 0
        assert cache._stats["hits"] == 0
        assert cache._stats["misses"] == 0

    def test_cache_initialization_custom(self):
        """Test cache initialization with custom values."""
        cache = QuoteCache(default_ttl=120.0, max_size=500)
        
        assert cache.default_ttl == 120.0
        assert cache.max_size == 500

    def test_cache_put_and_get(self, cache):
        """Test basic put and get operations."""
        test_value = {"symbol": "AAPL", "price": 150.0}
        
        # Put value
        cache.put("test_key", test_value, ttl=30.0)
        
        # Get value
        retrieved = cache.get("test_key")
        
        assert retrieved == test_value
        assert cache._stats["hits"] == 1
        assert cache._stats["misses"] == 0

    def test_cache_get_miss(self, cache):
        """Test cache miss."""
        retrieved = cache.get("nonexistent_key")
        
        assert retrieved is None
        assert cache._stats["hits"] == 0
        assert cache._stats["misses"] == 1

    def test_cache_get_expired(self, cache):
        """Test getting expired cache entry."""
        # Put with very short TTL
        cache.put("test_key", "test_value", ttl=0.1)
        
        # Wait for expiration
        time.sleep(0.2)
        
        # Get should return None and increment evictions
        retrieved = cache.get("test_key")
        
        assert retrieved is None
        assert cache._stats["misses"] == 1
        assert cache._stats["evictions"] == 1
        assert "test_key" not in cache._cache

    def test_cache_put_default_ttl(self, cache):
        """Test putting value with default TTL."""
        cache.put("test_key", "test_value")
        
        entry = cache._cache["test_key"]
        assert entry.ttl == cache.default_ttl

    def test_cache_put_custom_ttl(self, cache):
        """Test putting value with custom TTL."""
        custom_ttl = 120.0
        cache.put("test_key", "test_value", ttl=custom_ttl)
        
        entry = cache._cache["test_key"]
        assert entry.ttl == custom_ttl

    def test_cache_overwrite(self, cache):
        """Test overwriting existing cache entry."""
        # Put initial value
        cache.put("test_key", "initial_value")
        
        # Overwrite with new value
        cache.put("test_key", "new_value")
        
        retrieved = cache.get("test_key")
        assert retrieved == "new_value"

    def test_cache_delete(self, cache):
        """Test deleting cache entry."""
        # Put value
        cache.put("test_key", "test_value")
        assert cache.get("test_key") == "test_value"
        
        # Delete
        result = cache.delete("test_key")
        
        assert result is True
        assert cache.get("test_key") is None

    def test_cache_delete_nonexistent(self, cache):
        """Test deleting non-existent entry."""
        result = cache.delete("nonexistent_key")
        assert result is False

    def test_cache_clear(self, cache):
        """Test clearing cache."""
        # Put multiple values
        for i in range(5):
            cache.put(f"key_{i}", f"value_{i}")
        
        # Record some hits
        for i in range(3):
            cache.get(f"key_{i}")
        
        assert len(cache._cache) == 5
        assert cache._stats["hits"] == 3
        
        # Clear cache
        cache.clear()
        
        assert len(cache._cache) == 0
        assert cache._stats["hits"] == 0  # Stats reset
        assert cache._stats["misses"] == 0

    def test_cache_max_size_cleanup(self, cache):
        """Test automatic cleanup when max size is reached."""
        cache.max_size = 3  # Small cache for testing
        
        # Fill cache to max size
        for i in range(3):
            cache.put(f"key_{i}", f"value_{i}")
        
        assert len(cache._cache) == 3
        
        # Add one more - should trigger cleanup
        cache.put("key_3", "value_3")
        
        # Cache should still be at or below max size
        assert len(cache._cache) <= cache.max_size

    def test_cache_cleanup_expired(self, cache):
        """Test manual cleanup of expired entries."""
        # Add mix of fresh and expired entries
        current_time = time.time()
        
        # Add fresh entry
        cache.put("fresh", "fresh_value", ttl=60.0)
        
        # Add expired entry manually
        expired_entry = CacheEntry(value="expired_value", timestamp=current_time - 120.0, ttl=60.0)
        cache._cache["expired"] = expired_entry
        
        # Add another fresh entry
        cache.put("fresh2", "fresh_value2", ttl=60.0)
        
        assert len(cache._cache) == 3
        
        # Cleanup expired entries
        removed = cache._cleanup_expired()
        
        assert removed == 1
        assert len(cache._cache) == 2
        assert "expired" not in cache._cache
        assert "fresh" in cache._cache
        assert "fresh2" in cache._cache
        assert cache._stats["cleanups"] == 1

    def test_cache_evict_oldest(self, cache):
        """Test evicting oldest entries."""
        # Add entries with different timestamps
        base_time = time.time()
        
        entries = [
            CacheEntry(value="old_value", timestamp=base_time - 100, ttl=300),
            CacheEntry(value="medium_value", timestamp=base_time - 50, ttl=300),
            CacheEntry(value="new_value", timestamp=base_time, ttl=300)
        ]
        
        cache._cache["old_key"] = entries[0]
        cache._cache["medium_key"] = entries[1]
        cache._cache["new_key"] = entries[2]
        
        # Evict oldest 2 entries
        evicted = cache._evict_oldest(2)
        
        assert evicted == 2
        assert len(cache._cache) == 1
        assert "new_key" in cache._cache  # Newest should remain
        assert "old_key" not in cache._cache
        assert "medium_key" not in cache._cache
        assert cache._stats["evictions"] == 2

    def test_cache_evict_oldest_empty_cache(self, cache):
        """Test evicting from empty cache."""
        evicted = cache._evict_oldest(5)
        assert evicted == 0

    def test_cache_get_stats(self, cache):
        """Test getting cache statistics."""
        # Perform various operations
        cache.put("key1", "value1")
        cache.put("key2", "value2")
        cache.get("key1")  # Hit
        cache.get("key1")  # Hit
        cache.get("nonexistent")  # Miss
        
        stats = cache.get_stats()
        
        assert stats["size"] == 2
        assert stats["max_size"] == cache.max_size
        assert stats["hits"] == 2
        assert stats["misses"] == 1
        assert stats["hit_rate"] == 2/3  # 2 hits out of 3 total requests
        assert stats["default_ttl"] == cache.default_ttl

    def test_cache_get_stats_no_requests(self, cache):
        """Test getting stats with no requests."""
        stats = cache.get_stats()
        
        assert stats["hit_rate"] == 0.0  # Avoid division by zero

    def test_cache_get_entries_info(self, cache):
        """Test getting entries information."""
        # Add some entries
        cache.put("key1", "value1", ttl=60.0)
        time.sleep(0.1)  # Small delay
        cache.put("key2", "value2", ttl=120.0)
        
        entries_info = cache.get_entries_info()
        
        assert len(entries_info) == 2
        
        # Entries should be sorted by age (newest first)
        assert entries_info[0]["key"] == "key2"  # Newer
        assert entries_info[1]["key"] == "key1"  # Older
        
        # Check entry info structure
        for entry_info in entries_info:
            assert "key" in entry_info
            assert "age_seconds" in entry_info
            assert "ttl" in entry_info
            assert "remaining_ttl" in entry_info
            assert "is_expired" in entry_info
            assert "value_type" in entry_info
            
            assert entry_info["age_seconds"] >= 0
            assert entry_info["remaining_ttl"] >= 0
            assert isinstance(entry_info["is_expired"], bool)

    def test_cache_thread_safety(self, cache):
        """Test cache thread safety with concurrent operations."""
        num_threads = 10
        operations_per_thread = 100
        results = []
        
        def worker(thread_id):
            thread_results = []
            for i in range(operations_per_thread):
                key = f"thread_{thread_id}_key_{i}"
                value = f"thread_{thread_id}_value_{i}"
                
                # Put value
                cache.put(key, value)
                
                # Get value
                retrieved = cache.get(key)
                thread_results.append(retrieved == value)
                
                # Sometimes delete
                if i % 10 == 0:
                    cache.delete(key)
            
            results.append(all(thread_results))
        
        # Start threads
        threads = []
        for thread_id in range(num_threads):
            thread = threading.Thread(target=worker, args=(thread_id,))
            threads.append(thread)
            thread.start()
        
        # Wait for all threads
        for thread in threads:
            thread.join()
        
        # All threads should have succeeded
        assert all(results)
        
        # Cache should be in consistent state
        stats = cache.get_stats()
        assert stats["size"] >= 0  # Some entries may remain

    def test_cache_different_value_types(self, cache):
        """Test caching different types of values."""
        # Test different value types
        test_values = {
            "string": "test_string",
            "int": 42,
            "float": 3.14,
            "list": [1, 2, 3],
            "dict": {"nested": "value"},
            "none": None,
            "bool": True
        }
        
        # Put all values
        for key, value in test_values.items():
            cache.put(key, value)
        
        # Get and verify all values
        for key, expected_value in test_values.items():
            retrieved = cache.get(key)
            assert retrieved == expected_value
            assert type(retrieved) == type(expected_value)


class MockQuoteAdapter(QuoteAdapter):
    """Mock quote adapter for testing cached adapter."""

    def __init__(self):
        self.name = "MockAdapter"
        self.config = AdapterConfig(cache_ttl=300.0)
        self.call_counts = {
            "get_quote": 0,
            "get_quotes": 0,
            "get_options_chain": 0,
            "get_expiration_dates": 0
        }
        self.quotes = {}
        self.options_chains = {}
        self.expiration_dates = {}

    async def get_quote(self, asset):
        self.call_counts["get_quote"] += 1
        return self.quotes.get(asset.symbol)

    async def get_quotes(self, assets):
        self.call_counts["get_quotes"] += 1
        results = {}
        for asset in assets:
            quote = self.quotes.get(asset.symbol)
            if quote:
                results[asset] = quote
        return results

    async def get_chain(self, underlying, expiration_date=None):
        return []

    async def get_options_chain(self, underlying, expiration_date=None):
        self.call_counts["get_options_chain"] += 1
        key = f"{underlying}_{expiration_date.isoformat() if expiration_date else 'all'}"
        return self.options_chains.get(key)

    async def is_market_open(self):
        return True

    async def get_market_hours(self):
        return {"open": "09:30", "close": "16:00"}

    def get_sample_data_info(self):
        return {"test": "data"}

    def get_expiration_dates(self, underlying):
        self.call_counts["get_expiration_dates"] += 1
        return self.expiration_dates.get(underlying, [])

    def get_test_scenarios(self):
        return {}

    def set_date(self, date):
        pass

    def get_available_symbols(self):
        return []


class TestCachedQuoteAdapter:
    """Test CachedQuoteAdapter functionality."""

    @pytest.fixture
    def mock_adapter(self):
        """Create mock quote adapter."""
        return MockQuoteAdapter()

    @pytest.fixture
    def cache(self):
        """Create cache instance."""
        return QuoteCache(default_ttl=60.0, max_size=100)

    @pytest.fixture
    def cached_adapter(self, mock_adapter, cache):
        """Create cached quote adapter."""
        return CachedQuoteAdapter(mock_adapter, cache)

    def test_cached_adapter_initialization(self, mock_adapter):
        """Test cached adapter initialization."""
        cached = CachedQuoteAdapter(mock_adapter)
        
        assert cached.adapter is mock_adapter
        assert isinstance(cached.cache, QuoteCache)
        assert cached.cache.default_ttl == 300.0  # From mock adapter config

    def test_cached_adapter_initialization_custom_cache(self, mock_adapter, cache):
        """Test cached adapter with custom cache."""
        cached = CachedQuoteAdapter(mock_adapter, cache)
        
        assert cached.adapter is mock_adapter
        assert cached.cache is cache

    def test_cached_adapter_initialization_no_config(self):
        """Test cached adapter with adapter that has no config."""
        adapter = Mock()
        adapter.name = "TestAdapter"
        # No config attribute
        
        cached = CachedQuoteAdapter(adapter)
        
        assert cached.cache.default_ttl == 300.0  # Default fallback

    def test_get_quote_cache_miss(self, cached_adapter, mock_adapter):
        """Test getting quote with cache miss."""
        # Setup mock adapter to return quote
        stock = Stock(symbol="AAPL", name="Apple Inc.")
        quote = Quote(
            asset=stock,
            quote_date=datetime.now(),
            price=150.0,
            bid=149.95,
            ask=150.05,
            bid_size=100,
            ask_size=100,
            volume=1000000
        )
        mock_adapter.quotes["AAPL"] = quote
        
        with patch('app.models.assets.asset_factory', return_value=stock):
            result = cached_adapter.get_quote("AAPL")
        
        assert result is quote
        assert mock_adapter.call_counts["get_quote"] == 1  # Called underlying adapter
        
        # Should be cached now
        cache_key = "quote:AAPL:MockAdapter"
        assert cached_adapter.cache.get(cache_key) is quote

    def test_get_quote_cache_hit(self, cached_adapter, mock_adapter):
        """Test getting quote with cache hit."""
        stock = Stock(symbol="AAPL", name="Apple Inc.")
        quote = Quote(
            asset=stock,
            quote_date=datetime.now(),
            price=150.0,
            bid=149.95,
            ask=150.05,
            bid_size=100,
            ask_size=100,
            volume=1000000
        )
        
        # Pre-populate cache
        cache_key = "quote:AAPL:MockAdapter"
        cached_adapter.cache.put(cache_key, quote)
        
        with patch('app.models.assets.asset_factory', return_value=stock):
            result = cached_adapter.get_quote("AAPL")
        
        assert result is quote
        assert mock_adapter.call_counts["get_quote"] == 0  # Should not call underlying adapter

    def test_get_quote_invalid_symbol(self, cached_adapter):
        """Test getting quote for invalid symbol."""
        with patch('app.models.assets.asset_factory', return_value=None):
            result = cached_adapter.get_quote("INVALID")
        
        assert result is None

    def test_get_quote_no_quote_available(self, cached_adapter, mock_adapter):
        """Test getting quote when adapter returns None."""
        stock = Stock(symbol="AAPL", name="Apple Inc.")
        # mock_adapter.quotes is empty, so will return None
        
        with patch('app.models.assets.asset_factory', return_value=stock):
            result = cached_adapter.get_quote("AAPL")
        
        assert result is None
        assert mock_adapter.call_counts["get_quote"] == 1

    @pytest.mark.asyncio
    async def test_get_quotes_mixed_cache_hits_misses(self, cached_adapter, mock_adapter):
        """Test getting multiple quotes with mixed cache hits and misses."""
        # Setup quotes in mock adapter
        stock1 = Stock(symbol="AAPL", name="Apple Inc.")
        stock2 = Stock(symbol="GOOGL", name="Alphabet Inc.")
        stock3 = Stock(symbol="MSFT", name="Microsoft Corp.")
        
        quote1 = Quote(asset=stock1, quote_date=datetime.now(), price=150.0, bid=149.95, ask=150.05, bid_size=100, ask_size=100, volume=1000000)
        quote2 = Quote(asset=stock2, quote_date=datetime.now(), price=2500.0, bid=2499.50, ask=2500.50, bid_size=100, ask_size=100, volume=500000)
        quote3 = Quote(asset=stock3, quote_date=datetime.now(), price=300.0, bid=299.95, ask=300.05, bid_size=100, ask_size=100, volume=800000)
        
        mock_adapter.quotes["AAPL"] = quote1
        mock_adapter.quotes["GOOGL"] = quote2
        mock_adapter.quotes["MSFT"] = quote3
        
        # Pre-populate cache with one quote
        cached_adapter.cache.put("quote:AAPL:MockAdapter", quote1)
        
        def asset_factory_side_effect(symbol):
            if symbol == "AAPL":
                return stock1
            elif symbol == "GOOGL":
                return stock2
            elif symbol == "MSFT":
                return stock3
            return None
        
        with patch('app.models.assets.asset_factory', side_effect=asset_factory_side_effect):
            results = await cached_adapter.get_quotes(["AAPL", "GOOGL", "MSFT"])
        
        assert len(results) == 3
        assert results["AAPL"] is quote1  # Cache hit
        assert results["GOOGL"] is quote2  # Cache miss, fetched and cached
        assert results["MSFT"] is quote3   # Cache miss, fetched and cached
        
        # Should have called underlying adapter only for cache misses
        assert mock_adapter.call_counts["get_quotes"] == 1
        
        # All should be cached now
        assert cached_adapter.cache.get("quote:AAPL:MockAdapter") is quote1
        assert cached_adapter.cache.get("quote:GOOGL:MockAdapter") is quote2
        assert cached_adapter.cache.get("quote:MSFT:MockAdapter") is quote3

    @pytest.mark.asyncio
    async def test_get_options_chain_cache_miss(self, cached_adapter, mock_adapter):
        """Test getting options chain with cache miss."""
        expiration = date(2024, 1, 19)
        chain = OptionsChain(
            underlying_symbol="AAPL",
            expiration_date=expiration,
            underlying_price=150.0,
            calls=[],
            puts=[],
            quote_time=datetime.now()
        )
        
        # Setup mock adapter
        chain_key = f"AAPL_{expiration.isoformat()}"
        mock_adapter.options_chains[chain_key] = chain
        
        result = await cached_adapter.get_options_chain("AAPL", expiration)
        
        assert result is chain
        assert mock_adapter.call_counts["get_options_chain"] == 1
        
        # Should be cached with shorter TTL
        cache_key = f"chain:AAPL:{expiration.isoformat()}:MockAdapter"
        cached_chain = cached_adapter.cache.get(cache_key)
        assert cached_chain is chain

    @pytest.mark.asyncio
    async def test_get_options_chain_cache_hit(self, cached_adapter, mock_adapter):
        """Test getting options chain with cache hit."""
        expiration = date(2024, 1, 19)
        chain = OptionsChain(
            underlying_symbol="AAPL",
            expiration_date=expiration,
            underlying_price=150.0,
            calls=[],
            puts=[],
            quote_time=datetime.now()
        )
        
        # Pre-populate cache
        cache_key = f"chain:AAPL:{expiration.isoformat()}:MockAdapter"
        cached_adapter.cache.put(cache_key, chain)
        
        result = await cached_adapter.get_options_chain("AAPL", expiration)
        
        assert result is chain
        assert mock_adapter.call_counts["get_options_chain"] == 0  # Should not call underlying

    @pytest.mark.asyncio
    async def test_get_options_chain_no_adapter_method(self, cache):
        """Test getting options chain when adapter doesn't have the method."""
        # Create adapter without get_options_chain method
        adapter = Mock()
        adapter.name = "TestAdapter"
        # No get_options_chain method
        
        cached = CachedQuoteAdapter(adapter, cache)
        
        result = await cached.get_options_chain("AAPL", date(2024, 1, 19))
        
        assert result is None

    def test_get_expiration_dates_cache_miss(self, cached_adapter, mock_adapter):
        """Test getting expiration dates with cache miss."""
        dates = [date(2024, 1, 19), date(2024, 2, 16)]
        mock_adapter.expiration_dates["AAPL"] = dates
        
        result = cached_adapter.get_expiration_dates("AAPL")
        
        assert result == dates
        assert mock_adapter.call_counts["get_expiration_dates"] == 1
        
        # Should be cached with longer TTL
        cache_key = "expirations:AAPL:MockAdapter"
        cached_dates = cached_adapter.cache.get(cache_key)
        assert cached_dates == dates

    def test_get_expiration_dates_cache_hit(self, cached_adapter, mock_adapter):
        """Test getting expiration dates with cache hit."""
        dates = [date(2024, 1, 19), date(2024, 2, 16)]
        
        # Pre-populate cache
        cache_key = "expirations:AAPL:MockAdapter"
        cached_adapter.cache.put(cache_key, dates)
        
        result = cached_adapter.get_expiration_dates("AAPL")
        
        assert result == dates
        assert mock_adapter.call_counts["get_expiration_dates"] == 0

    def test_get_expiration_dates_no_adapter_method(self, cache):
        """Test getting expiration dates when adapter doesn't have the method."""
        adapter = Mock()
        adapter.name = "TestAdapter"
        # No get_expiration_dates method
        
        cached = CachedQuoteAdapter(adapter, cache)
        
        result = cached.get_expiration_dates("AAPL")
        
        assert result == []

    def test_clear_cache(self, cached_adapter):
        """Test clearing the cache."""
        # Add some data to cache
        cached_adapter.cache.put("test_key", "test_value")
        assert cached_adapter.cache.get("test_key") == "test_value"
        
        # Clear cache
        cached_adapter.clear_cache()
        
        assert cached_adapter.cache.get("test_key") is None

    def test_get_cache_stats(self, cached_adapter):
        """Test getting cache statistics."""
        # Perform some operations to generate stats
        with patch('app.models.assets.asset_factory', return_value=Stock(symbol="AAPL", name="Apple Inc.")):
            cached_adapter.get_quote("AAPL")  # Miss
            cached_adapter.get_quote("AAPL")  # Hit
        
        stats = cached_adapter.get_cache_stats()
        
        assert isinstance(stats, dict)
        assert "hits" in stats
        assert "misses" in stats
        assert "hit_rate" in stats

    def test_attribute_delegation(self, cached_adapter, mock_adapter):
        """Test that unknown attributes are delegated to underlying adapter."""
        # Mock adapter has name attribute
        assert cached_adapter.name == "MockAdapter"
        
        # Mock adapter has config attribute
        assert cached_adapter.config is mock_adapter.config
        
        # Should also work for methods
        assert cached_adapter.get_sample_data_info() == {"test": "data"}

    def test_attribute_delegation_missing_attribute(self, cached_adapter):
        """Test delegation of missing attributes raises appropriate error."""
        with pytest.raises(AttributeError):
            _ = cached_adapter.nonexistent_attribute


class TestCacheUtilities:
    """Test cache utility functions."""

    def test_get_global_cache(self):
        """Test getting global cache instance."""
        cache1 = get_global_cache()
        cache2 = get_global_cache()
        
        # Should return the same instance
        assert cache1 is cache2
        assert isinstance(cache1, QuoteCache)

    def test_cached_adapter_function(self):
        """Test cached_adapter convenience function."""
        mock_adapter = MockQuoteAdapter()
        
        # Without custom cache
        cached = cached_adapter(mock_adapter)
        
        assert isinstance(cached, CachedQuoteAdapter)
        assert cached.adapter is mock_adapter
        assert cached.cache is get_global_cache()

    def test_cached_adapter_function_custom_cache(self):
        """Test cached_adapter function with custom cache."""
        mock_adapter = MockQuoteAdapter()
        custom_cache = QuoteCache(default_ttl=120.0, max_size=50)
        
        cached = cached_adapter(mock_adapter, custom_cache)
        
        assert isinstance(cached, CachedQuoteAdapter)
        assert cached.adapter is mock_adapter
        assert cached.cache is custom_cache
        assert cached.cache.default_ttl == 120.0

    def test_cache_performance_under_load(self):
        """Test cache performance with high load."""
        cache = QuoteCache(default_ttl=60.0, max_size=1000)
        
        # Simulate high load
        num_operations = 10000
        keys = [f"key_{i}" for i in range(num_operations)]
        
        start_time = time.time()
        
        # Put operations
        for key in keys:
            cache.put(key, f"value_for_{key}")
        
        # Get operations (mix of hits and misses)
        for i in range(num_operations):
            key = f"key_{i % (num_operations // 2)}"  # 50% hit rate
            cache.get(key)
        
        end_time = time.time()
        duration = end_time - start_time
        
        # Should complete reasonably quickly
        assert duration < 5.0  # Less than 5 seconds for 20k operations
        
        # Verify cache integrity
        stats = cache.get_stats()
        assert stats["hits"] > 0
        assert stats["misses"] > 0
        assert stats["size"] <= cache.max_size

    def test_cache_memory_usage_control(self):
        """Test that cache controls memory usage properly."""
        cache = QuoteCache(default_ttl=60.0, max_size=100)
        
        # Add more entries than max_size
        for i in range(200):
            cache.put(f"key_{i}", f"value_{i}")
        
        # Cache should not exceed max_size significantly
        assert len(cache._cache) <= cache.max_size * 1.1  # Allow 10% overage for cleanup timing
        
        # Should have performed cleanup/evictions
        stats = cache.get_stats()
        assert stats["evictions"] > 0 or stats["cleanups"] > 0
