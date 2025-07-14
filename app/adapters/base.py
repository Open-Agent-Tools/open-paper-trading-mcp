"""
Base adapter interfaces for pluggable market data sources.
"""

from abc import ABC, abstractmethod
from datetime import datetime, date
from typing import List, Dict, Optional, Union, Any
from dataclasses import dataclass

from app.models.assets import Asset, Option, asset_factory
from app.models.quotes import Quote, OptionQuote, OptionsChain


@dataclass
class AdapterConfig:
    """Configuration for quote adapters."""
    name: str
    enabled: bool = True
    priority: int = 100
    timeout: float = 5.0
    cache_ttl: float = 60.0
    config: Dict[str, Any] = None
    
    def __post_init__(self):
        if self.config is None:
            self.config = {}


class QuoteAdapter(ABC):
    """
    Abstract base class for market data adapters.
    
    All quote adapters must implement these methods to provide
    market data for stocks and options.
    """
    
    def __init__(self, config: AdapterConfig):
        self.config = config
        self.name = config.name
        self.enabled = config.enabled
        self.timeout = config.timeout
        
    @abstractmethod
    def get_quote(self, symbol: str) -> Optional[Union[Quote, OptionQuote]]:
        """
        Get current quote for a symbol.
        
        Args:
            symbol: Stock symbol (AAPL) or option symbol (AAPL240119C00195000)
            
        Returns:
            Quote for stocks or OptionQuote for options, None if not found
        """
        pass
    
    @abstractmethod
    def get_quotes(self, symbols: List[str]) -> Dict[str, Union[Quote, OptionQuote]]:
        """
        Get quotes for multiple symbols.
        
        Args:
            symbols: List of symbols to quote
            
        Returns:
            Dictionary mapping symbols to their quotes
        """
        pass
    
    @abstractmethod
    def get_options_chain(self, underlying: str, expiration: Optional[date] = None) -> Optional[OptionsChain]:
        """
        Get options chain for an underlying symbol.
        
        Args:
            underlying: Underlying stock symbol (e.g., 'AAPL')
            expiration: Optional specific expiration date
            
        Returns:
            OptionsChain containing calls and puts, None if not available
        """
        pass
    
    @abstractmethod
    def get_expiration_dates(self, underlying: str) -> List[date]:
        """
        Get available expiration dates for an underlying.
        
        Args:
            underlying: Underlying stock symbol
            
        Returns:
            List of available expiration dates
        """
        pass
    
    @abstractmethod
    def is_market_open(self) -> bool:
        """
        Check if the market is currently open.
        
        Returns:
            True if market is open, False otherwise
        """
        pass
    
    @abstractmethod
    def get_market_hours(self) -> Dict[str, datetime]:
        """
        Get current market hours.
        
        Returns:
            Dictionary with 'open' and 'close' times for today
        """
        pass
    
    def supports_symbol(self, symbol: str) -> bool:
        """
        Check if this adapter supports the given symbol.
        
        Args:
            symbol: Symbol to check
            
        Returns:
            True if supported, False otherwise
        """
        # Default implementation - override for specific logic
        return True
    
    def get_last_updated(self, symbol: str) -> Optional[datetime]:
        """
        Get the last update time for a symbol's quote.
        
        Args:
            symbol: Symbol to check
            
        Returns:
            Last update timestamp, None if unknown
        """
        # Default implementation - override for tracking
        return None
    
    def health_check(self) -> Dict[str, Any]:
        """
        Perform health check on the adapter.
        
        Returns:
            Dictionary with health status and metrics
        """
        return {
            'name': self.name,
            'enabled': self.enabled,
            'status': 'healthy' if self.enabled else 'disabled',
            'last_check': datetime.now()
        }


class AdapterRegistry:
    """
    Registry for managing multiple quote adapters with fallback support.
    """
    
    def __init__(self):
        self.adapters: List[QuoteAdapter] = []
        self.adapter_map: Dict[str, QuoteAdapter] = {}
        
    def register(self, adapter: QuoteAdapter) -> None:
        """
        Register a quote adapter.
        
        Args:
            adapter: Adapter to register
        """
        if adapter.name in self.adapter_map:
            # Replace existing adapter
            self.remove(adapter.name)
            
        self.adapters.append(adapter)
        self.adapter_map[adapter.name] = adapter
        
        # Sort by priority (lower numbers = higher priority)
        self.adapters.sort(key=lambda a: a.config.priority)
        
    def remove(self, name: str) -> None:
        """
        Remove an adapter by name.
        
        Args:
            name: Name of adapter to remove
        """
        if name in self.adapter_map:
            adapter = self.adapter_map[name]
            self.adapters.remove(adapter)
            del self.adapter_map[name]
            
    def get_adapter(self, name: str) -> Optional[QuoteAdapter]:
        """
        Get a specific adapter by name.
        
        Args:
            name: Adapter name
            
        Returns:
            Adapter instance or None if not found
        """
        return self.adapter_map.get(name)
    
    def get_enabled_adapters(self) -> List[QuoteAdapter]:
        """
        Get all enabled adapters in priority order.
        
        Returns:
            List of enabled adapters
        """
        return [a for a in self.adapters if a.enabled]
    
    def get_quote(self, symbol: str) -> Optional[Union[Quote, OptionQuote]]:
        """
        Get quote using adapter fallback chain.
        
        Args:
            symbol: Symbol to quote
            
        Returns:
            Quote from first adapter that provides it
        """
        for adapter in self.get_enabled_adapters():
            if adapter.supports_symbol(symbol):
                try:
                    quote = adapter.get_quote(symbol)
                    if quote is not None:
                        return quote
                except Exception as e:
                    # Log error and try next adapter
                    print(f"Adapter {adapter.name} failed for {symbol}: {e}")
                    continue
        
        return None
    
    def get_quotes(self, symbols: List[str]) -> Dict[str, Union[Quote, OptionQuote]]:
        """
        Get quotes for multiple symbols using fallback chain.
        
        Args:
            symbols: List of symbols
            
        Returns:
            Dictionary of symbol -> quote mappings
        """
        results = {}
        remaining_symbols = symbols.copy()
        
        for adapter in self.get_enabled_adapters():
            if not remaining_symbols:
                break
                
            # Filter symbols this adapter supports
            supported_symbols = [s for s in remaining_symbols if adapter.supports_symbol(s)]
            if not supported_symbols:
                continue
                
            try:
                quotes = adapter.get_quotes(supported_symbols)
                for symbol, quote in quotes.items():
                    if quote is not None:
                        results[symbol] = quote
                        if symbol in remaining_symbols:
                            remaining_symbols.remove(symbol)
            except Exception as e:
                print(f"Adapter {adapter.name} failed for batch quotes: {e}")
                continue
        
        return results
    
    def get_options_chain(self, underlying: str, expiration: Optional[date] = None) -> Optional[OptionsChain]:
        """
        Get options chain using adapter fallback.
        
        Args:
            underlying: Underlying symbol
            expiration: Optional expiration date
            
        Returns:
            OptionsChain from first adapter that provides it
        """
        for adapter in self.get_enabled_adapters():
            try:
                chain = adapter.get_options_chain(underlying, expiration)
                if chain is not None:
                    return chain
            except Exception as e:
                print(f"Adapter {adapter.name} failed for options chain {underlying}: {e}")
                continue
                
        return None
    
    def get_expiration_dates(self, underlying: str) -> List[date]:
        """
        Get expiration dates using adapter fallback.
        
        Args:
            underlying: Underlying symbol
            
        Returns:
            List of expiration dates from first successful adapter
        """
        for adapter in self.get_enabled_adapters():
            try:
                dates = adapter.get_expiration_dates(underlying)
                if dates:
                    return dates
            except Exception as e:
                print(f"Adapter {adapter.name} failed for expiration dates {underlying}: {e}")
                continue
                
        return []
    
    def health_check(self) -> Dict[str, Any]:
        """
        Perform health check on all adapters.
        
        Returns:
            Health status for all adapters
        """
        return {
            'total_adapters': len(self.adapters),
            'enabled_adapters': len(self.get_enabled_adapters()),
            'adapters': [adapter.health_check() for adapter in self.adapters]
        }


# Global adapter registry instance
adapter_registry = AdapterRegistry()


def get_adapter_registry() -> AdapterRegistry:
    """Get the global adapter registry."""
    return adapter_registry