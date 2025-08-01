"""
Quote caching system with TTL (Time To Live) for performance optimization.
"""

import time
from dataclasses import dataclass
from threading import RLock
from typing import Any

from app.adapters.base import QuoteAdapter
from app.models.quotes import OptionQuote, OptionsChain, Quote


@dataclass
class CacheEntry:
    """
    Cache entry with TTL support.
    """

    value: Quote | OptionQuote | OptionsChain | dict[str, Any] | list[Any]
    timestamp: float
    ttl: float

    @property
    def is_expired(self) -> bool:
        """Check if this cache entry has expired."""
        return time.time() - self.timestamp > self.ttl

    @property
    def age_seconds(self) -> float:
        """Get the age of this cache entry in seconds."""
        return time.time() - self.timestamp

    @property
    def remaining_ttl(self) -> float:
        """Get remaining TTL in seconds."""
        return max(0, self.ttl - self.age_seconds)


class QuoteCache:
    """
    Thread-safe quote cache with TTL support and automatic cleanup.
    """

    def __init__(self, default_ttl: float = 60.0, max_size: int = 10000):
        """
        Initialize quote cache.

        Args:
            default_ttl: Default time-to-live in seconds
            max_size: Maximum number of entries before cleanup
        """
        self.default_ttl = default_ttl
        self.max_size = max_size
        self._cache: dict[str, CacheEntry] = {}
        self._lock = RLock()
        self._stats = {
            "hits": 0,
            "misses": 0,
            "evictions": 0,
            "cleanups": 0,
        }

    def get(
        self, key: str
    ) -> Quote | OptionQuote | OptionsChain | dict[str, Any] | list[Any] | None:
        """
        Get value from cache if it exists and hasn't expired.

        Args:
            key: Cache key

        Returns:
            Cached value or None if not found/expired
        """
        with self._lock:
            entry = self._cache.get(key)

            if entry is None:
                self._stats["misses"] += 1
                return None

            if entry.is_expired:
                del self._cache[key]
                self._stats["misses"] += 1
                self._stats["evictions"] += 1
                return None

            self._stats["hits"] += 1
            return entry.value

    def put(
        self,
        key: str,
        value: Quote | OptionQuote | OptionsChain | dict[str, Any] | list[Any],
        ttl: float | None = None,
    ) -> None:
        """
        Store value in cache with TTL.

        Args:
            key: Cache key
            value: Value to cache
            ttl: Time-to-live in seconds, uses default if None
        """
        if ttl is None:
            ttl = self.default_ttl

        with self._lock:
            # Check if we need to cleanup
            if len(self._cache) >= self.max_size:
                self._cleanup_expired()

                # If still at max size, remove oldest entries
                if len(self._cache) >= self.max_size:
                    self._evict_oldest(self.max_size // 2)

            self._cache[key] = CacheEntry(value=value, timestamp=time.time(), ttl=ttl)

    def delete(self, key: str) -> bool:
        """
        Delete a specific key from cache.

        Args:
            key: Cache key to delete

        Returns:
            True if key was found and deleted
        """
        with self._lock:
            if key in self._cache:
                del self._cache[key]
                return True
            return False

    def clear(self) -> None:
        """Clear all entries from cache."""
        with self._lock:
            self._cache.clear()
            # Reset stats except for cumulative counters
            self._stats["hits"] = 0
            self._stats["misses"] = 0

    def _cleanup_expired(self) -> int:
        """
        Remove expired entries from cache.

        Returns:
            Number of entries removed
        """
        expired_keys = []
        current_time = time.time()

        for key, entry in self._cache.items():
            if current_time - entry.timestamp > entry.ttl:
                expired_keys.append(key)

        for key in expired_keys:
            del self._cache[key]

        self._stats["evictions"] += len(expired_keys)
        self._stats["cleanups"] += 1

        return len(expired_keys)

    def _evict_oldest(self, count: int) -> int:
        """
        Evict oldest entries from cache.

        Args:
            count: Number of entries to evict

        Returns:
            Number of entries actually evicted
        """
        if not self._cache:
            return 0

        # Sort by timestamp (oldest first)
        sorted_items = sorted(self._cache.items(), key=lambda x: x[1].timestamp)

        evicted = 0
        for key, _ in sorted_items[:count]:
            if key in self._cache:
                del self._cache[key]
                evicted += 1

        self._stats["evictions"] += evicted
        return evicted

    def get_stats(self) -> dict[str, Any]:
        """
        Get cache statistics.

        Returns:
            Dictionary with cache statistics
        """
        with self._lock:
            total_requests = self._stats["hits"] + self._stats["misses"]
            hit_rate = (
                (self._stats["hits"] / total_requests) if total_requests > 0 else 0.0
            )

            return {
                "size": len(self._cache),
                "max_size": self.max_size,
                "hits": self._stats["hits"],
                "misses": self._stats["misses"],
                "hit_rate": hit_rate,
                "evictions": self._stats["evictions"],
                "cleanups": self._stats["cleanups"],
                "default_ttl": self.default_ttl,
            }

    def get_entries_info(self) -> list[dict[str, Any]]:
        """
        Get information about current cache entries.

        Returns:
            List of entry information dictionaries
        """
        with self._lock:
            entries = []
            current_time = time.time()

            for key, entry in self._cache.items():
                entries.append(
                    {
                        "key": key,
                        "age_seconds": current_time - entry.timestamp,
                        "ttl": entry.ttl,
                        "remaining_ttl": max(
                            0, entry.ttl - (current_time - entry.timestamp)
                        ),
                        "is_expired": entry.is_expired,
                        "value_type": type(entry.value).__name__,
                    }
                )

            # Sort by age (newest first)
            entries.sort(
                key=lambda x: (
                    float(x["age_seconds"])
                    if isinstance(x["age_seconds"], int | float | str)
                    else 0.0
                )
            )
            return entries


class CachedQuoteAdapter:
    """
    Wrapper that adds caching to any QuoteAdapter.
    """

    def __init__(self, adapter: QuoteAdapter, cache: QuoteCache | None = None) -> None:
        """
        Initialize cached adapter.

        Args:
            adapter: Base adapter to wrap
            cache: Cache instance, creates new one if None
        """
        self.adapter = adapter
        config = getattr(adapter, "config", None)
        cache_ttl = (
            config.cache_ttl if config and hasattr(config, "cache_ttl") else 300.0
        )
        self.cache = cache or QuoteCache(default_ttl=cache_ttl)

    def get_quote(self, symbol: str) -> Quote | OptionQuote | None:
        """Get quote with caching."""
        cache_key = f"quote:{symbol}:{getattr(self.adapter, 'name', 'unknown')}"

        # Try cache first
        cached_quote = self.cache.get(cache_key)
        if cached_quote is not None and isinstance(cached_quote, Quote | OptionQuote):
            return cached_quote

        # Fetch from adapter
        from ..models.assets import asset_factory

        asset = asset_factory(symbol)
        if asset is None:
            return None
        quote = self.adapter.get_quote(asset)
        if quote is not None and isinstance(quote, Quote | OptionQuote):
            self.cache.put(cache_key, quote)
            return quote

        return None

    async def get_quotes(self, symbols: list[str]) -> dict[str, Quote | OptionQuote]:
        """Get multiple quotes with caching."""
        results = {}
        uncached_symbols = []

        # Check cache for each symbol
        for symbol in symbols:
            cache_key = f"quote:{symbol}:{getattr(self.adapter, 'name', 'unknown')}"
            cached_quote = self.cache.get(cache_key)
            if cached_quote is not None and isinstance(
                cached_quote, Quote | OptionQuote
            ):
                results[symbol] = cached_quote
            else:
                uncached_symbols.append(symbol)

        # Fetch uncached symbols
        if uncached_symbols:
            from ..models.assets import asset_factory

            uncached_assets = [asset_factory(symbol) for symbol in uncached_symbols]
            valid_assets = [asset for asset in uncached_assets if asset is not None]
            fresh_quotes = await self.adapter.get_quotes(valid_assets)
            for asset, quote in fresh_quotes.items():
                symbol = asset.symbol if hasattr(asset, "symbol") else str(asset)
                cache_key = f"quote:{symbol}:{getattr(self.adapter, 'name', 'unknown')}"
                self.cache.put(cache_key, quote)
                results[symbol] = quote

        return results

    async def get_options_chain(
        self, underlying: str, expiration: Any | None = None
    ) -> OptionsChain | None:
        """Get options chain with caching."""
        exp_str = expiration.isoformat() if expiration else "all"
        cache_key = (
            f"chain:{underlying}:{exp_str}:{getattr(self.adapter, 'name', 'unknown')}"
        )

        # Try cache first
        cached_chain = self.cache.get(cache_key)
        if cached_chain is not None and isinstance(cached_chain, OptionsChain):
            return cached_chain

        # Fetch from adapter
        if hasattr(self.adapter, "get_options_chain"):
            chain = await self.adapter.get_options_chain(underlying, expiration)
        else:
            return None
        if chain is not None and isinstance(chain, OptionsChain):
            # Use shorter TTL for options chains as they change more frequently
            ttl = min(self.cache.default_ttl, 30.0)  # Max 30 seconds for chains
            self.cache.put(cache_key, chain, ttl)
            return chain

        return None

    def get_expiration_dates(self, underlying: str) -> list[Any]:
        """Get expiration dates with caching."""
        cache_key = (
            f"expirations:{underlying}:{getattr(self.adapter, 'name', 'unknown')}"
        )

        # Try cache first
        cached_dates = self.cache.get(cache_key)
        if cached_dates is not None and isinstance(cached_dates, list):
            return cached_dates

        # Fetch from adapter
        if hasattr(self.adapter, "get_expiration_dates"):
            dates = self.adapter.get_expiration_dates(underlying)
        else:
            return []
        if dates and isinstance(dates, list):
            # Cache for longer as expiration dates don't change often
            ttl = max(self.cache.default_ttl, 300.0)  # Min 5 minutes
            self.cache.put(cache_key, dates, ttl)
            return dates

        return []

    def clear_cache(self) -> None:
        """Clear all cached data."""
        self.cache.clear()

    def get_cache_stats(self) -> dict[str, Any]:
        """Get cache statistics."""
        return self.cache.get_stats()

    # Delegate other methods to the underlying adapter
    def __getattr__(self, name: str) -> Any:
        """Delegate unknown methods to the underlying adapter."""
        return getattr(self.adapter, name)


# Global cache instance for shared use
_global_cache = QuoteCache(default_ttl=60.0, max_size=10000)


def get_global_cache() -> QuoteCache:
    """Get the global quote cache instance."""
    return _global_cache


def cached_adapter(adapter: Any, cache: QuoteCache | None = None) -> CachedQuoteAdapter:
    """
    Wrap an adapter with caching.

    Args:
        adapter: Adapter to wrap
        cache: Cache instance, uses global cache if None

    Returns:
        Cached adapter wrapper
    """
    if cache is None:
        cache = get_global_cache()
    return CachedQuoteAdapter(adapter, cache)
