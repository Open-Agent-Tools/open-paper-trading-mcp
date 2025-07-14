"""
Test data adapter using historical options and stock data.

Adapted from paperbroker TestDataQuoteAdapter with modern Python patterns.

Data includes quotes for AAL and GOOG from 2017:
- AAL: 2017-01-27 to 2017-01-28 (Jan expiration + earnings)
- AAL: 2017-03-24 to 2017-03-25 (March expiration)  
- GOOG: 2017-01-27 to 2017-01-28 (Jan expiration)
- GOOG: 2017-03-24 to 2017-03-25 (March expiration)

Data format: [symbol],[current_date],[bid],[ask]
"""

import gzip
import csv
import os
from datetime import datetime, date
from typing import Dict, List, Optional, Any
from pathlib import Path

from ..models.assets import Asset, Option, asset_factory
from ..models.quotes import Quote, OptionQuote, OptionsChain
from ..services.greeks import calculate_option_greeks


class TestDataError(Exception):
    """Error loading or accessing test data."""
    pass


class TestDataQuoteAdapter:
    """
    Quote adapter that provides historical test data for development and testing.
    
    Includes real market data with pre-calculated Greeks for comprehensive testing
    of options trading strategies and edge cases.
    """
    
    def __init__(self, current_date: str = '2017-03-24'):
        """
        Initialize with a specific date.
        
        Args:
            current_date: Date to retrieve quotes for (YYYY-MM-DD format)
                         Available dates: 2017-01-27, 2017-01-28, 2017-03-24, 2017-03-25
        """
        self.current_date = datetime.strptime(current_date, '%Y-%m-%d').strftime('%Y-%m-%d')
        self._cache: Optional[Dict[str, Any]] = None
        self._data_file = Path(__file__).parent / 'test_data' / 'data.csv.gz'
        
        if not self._data_file.exists():
            raise TestDataError(f"Test data file not found: {self._data_file}")
    
    def set_date(self, date_str: str):
        """Set the current date for quote retrieval."""
        self.current_date = datetime.strptime(date_str, '%Y-%m-%d').strftime('%Y-%m-%d')
    
    def get_available_dates(self) -> List[str]:
        """Get list of available test dates."""
        return ['2017-01-27', '2017-01-28', '2017-03-24', '2017-03-25']
    
    def load_test_data(self) -> Dict[str, Any]:
        """Load and cache test data from compressed CSV file."""
        if self._cache is not None:
            return self._cache
        
        self._cache = {}
        
        try:
            with gzip.open(self._data_file, 'rt') as f:
                reader = csv.reader(f, delimiter='\t')
                
                for row in reader:
                    if len(row) < 4:
                        continue
                    
                    symbol, quote_date, bid, ask = row[0], row[1], float(row[2]), float(row[3])
                    cache_key = symbol + quote_date
                    
                    # Create asset and quote
                    asset = asset_factory(symbol)
                    
                    if isinstance(asset, Option):
                        # Create option quote with calculated price
                        price = (bid + ask) / 2 if bid > 0 and ask > 0 else None
                        option_quote = OptionQuote(
                            quote_date=datetime.strptime(quote_date, '%Y-%m-%d'),
                            asset=asset,
                            bid=bid,
                            ask=ask,
                            price=price
                        )
                        
                        # Calculate Greeks if we have price and underlying data
                        if option_quote.price and option_quote.price > 0:
                            underlying_key = asset.underlying.symbol + quote_date
                            underlying_quote = self._cache.get(underlying_key)
                            
                            if underlying_quote and hasattr(underlying_quote, 'price'):
                                try:
                                    greeks = calculate_option_greeks(
                                        option_type=asset.option_type,
                                        strike=asset.strike,
                                        underlying_price=underlying_quote.price,
                                        days_to_expiration=asset.get_days_to_expiration(
                                            datetime.strptime(quote_date, '%Y-%m-%d').date()
                                        ),
                                        option_price=option_quote.price
                                    )
                                    
                                    # Update option quote with Greeks
                                    for greek_name, value in greeks.items():
                                        if value is not None:
                                            setattr(option_quote, greek_name, value)
                                            
                                except Exception:
                                    # Greeks calculation failed - continue without Greeks
                                    pass
                        
                        self._cache[cache_key] = option_quote
                    
                    else:
                        # Create stock quote with calculated price
                        price = (bid + ask) / 2 if bid > 0 and ask > 0 else None
                        stock_quote = Quote(
                            quote_date=datetime.strptime(quote_date, '%Y-%m-%d'),
                            asset=asset,
                            bid=bid,
                            ask=ask,
                            price=price
                        )
                        self._cache[cache_key] = stock_quote
                        
        except Exception as e:
            raise TestDataError(f"Failed to load test data: {e}")
        
        return self._cache
    
    def get_quote(self, asset: Any) -> Optional[Quote]:
        """
        Get quote for an asset on the current date.
        
        Args:
            asset: Asset symbol string or Asset object
            
        Returns:
            Quote object or None if not found
        """
        asset_obj = asset_factory(asset)
        cache_key = asset_obj.symbol + self.current_date
        
        cache = self.load_test_data()
        return cache.get(cache_key)
    
    def get_options_chain(self, 
                         underlying: Any, 
                         expiration_date: Optional[date] = None) -> OptionsChain:
        """
        Get options chain for an underlying asset.
        
        Args:
            underlying: Underlying asset symbol or object
            expiration_date: Specific expiration date, or None for all
            
        Returns:
            OptionsChain object with calls and puts
        """
        underlying_asset = asset_factory(underlying)
        cache = self.load_test_data()
        
        # Get underlying quote
        underlying_quote = self.get_quote(underlying_asset)
        underlying_price = underlying_quote.price if underlying_quote else None
        
        # Filter options for this underlying and date
        all_options = []
        for quote in cache.values():
            if (isinstance(quote, OptionQuote) and 
                quote.quote_date.strftime('%Y-%m-%d') == self.current_date and
                hasattr(quote.asset, 'underlying') and
                quote.asset.underlying.symbol == underlying_asset.symbol):
                
                if expiration_date is None or quote.asset.expiration_date == expiration_date:
                    all_options.append(quote)
        
        # Separate calls and puts
        calls = [opt for opt in all_options if opt.asset.option_type == 'call']
        puts = [opt for opt in all_options if opt.asset.option_type == 'put']
        
        # Sort by strike price
        calls.sort(key=lambda x: x.asset.strike)
        puts.sort(key=lambda x: x.asset.strike)
        
        # Determine expiration date
        exp_date = expiration_date
        if exp_date is None and all_options:
            exp_date = all_options[0].asset.expiration_date
        
        return OptionsChain(
            underlying_symbol=underlying_asset.symbol,
            expiration_date=exp_date or date.today(),
            underlying_price=underlying_price,
            calls=calls,
            puts=puts,
            quote_time=datetime.strptime(self.current_date, '%Y-%m-%d')
        )
    
    def get_expiration_dates(self, underlying: Any) -> List[date]:
        """
        Get available expiration dates for an underlying asset.
        
        Args:
            underlying: Underlying asset symbol or object
            
        Returns:
            List of expiration dates
        """
        underlying_asset = asset_factory(underlying)
        cache = self.load_test_data()
        
        expiration_dates = set()
        for quote in cache.values():
            if (isinstance(quote, OptionQuote) and 
                quote.quote_date.strftime('%Y-%m-%d') == self.current_date and
                hasattr(quote.asset, 'underlying') and
                quote.asset.underlying.symbol == underlying_asset.symbol):
                
                expiration_dates.add(quote.asset.expiration_date)
        
        return sorted(list(expiration_dates))
    
    def get_available_symbols(self) -> List[str]:
        """Get all available symbols in test data."""
        cache = self.load_test_data()
        symbols = set()
        
        for quote in cache.values():
            if quote.quote_date.strftime('%Y-%m-%d') == self.current_date:
                symbols.add(quote.asset.symbol)
        
        return sorted(list(symbols))
    
    def get_underlying_symbols(self) -> List[str]:
        """Get underlying asset symbols (stocks)."""
        cache = self.load_test_data()
        underlyings = set()
        
        for quote in cache.values():
            if (quote.quote_date.strftime('%Y-%m-%d') == self.current_date and
                not isinstance(quote.asset, Option)):
                underlyings.add(quote.asset.symbol)
        
        return sorted(list(underlyings))
    
    def get_test_scenarios(self) -> Dict[str, Any]:
        """
        Get predefined test scenarios for common testing patterns.
        
        Returns:
            Dictionary of test scenarios with descriptions and data
        """
        return {
            'aal_earnings': {
                'description': 'AAL around earnings (2017-01-27 to 2017-01-28)',
                'symbol': 'AAL',
                'dates': ['2017-01-27', '2017-01-28'],
                'scenario': 'earnings_volatility'
            },
            'aal_march_expiration': {
                'description': 'AAL March expiration (2017-03-24 to 2017-03-25)',
                'symbol': 'AAL', 
                'dates': ['2017-03-24', '2017-03-25'],
                'scenario': 'expiration_week'
            },
            'goog_january': {
                'description': 'GOOG January expiration (2017-01-27 to 2017-01-28)',
                'symbol': 'GOOG',
                'dates': ['2017-01-27', '2017-01-28'],
                'scenario': 'high_price_stock'
            },
            'goog_march': {
                'description': 'GOOG March expiration (2017-03-24 to 2017-03-25)',
                'symbol': 'GOOG',
                'dates': ['2017-03-24', '2017-03-25'],
                'scenario': 'high_price_expiration'
            }
        }
    
    def get_sample_data_info(self) -> Dict[str, Any]:
        """
        Get information about the sample data included.
        
        Returns:
            Dictionary with sample data details
        """
        return {
            'description': 'Historical options and stock data from 2017',
            'symbols': ['AAL', 'GOOG'],
            'dates': ['2017-01-27', '2017-01-28', '2017-03-24', '2017-03-25'],
            'features': [
                'Real market bid/ask spreads',
                'Pre-calculated option Greeks',
                'Multiple expiration cycles',
                'Earnings event data (AAL)',
                'High-priced stock data (GOOG)'
            ],
            'sample_quotes': {
                'AAL': {
                    '2017-01-27': {'bid': 47.35, 'ask': 47.37},
                    '2017-01-28': {'bid': 46.90, 'ask': 47.00}
                },
                'AAL170203P00047000': {  # AAL Put, Feb 3, Strike 47
                    '2017-01-27': {'bid': 0.68, 'ask': 0.72},
                    '2017-01-28': {'bid': 0.79, 'ask': 0.86}
                }
            },
            'use_cases': [
                'Testing options strategies',
                'Validating Greeks calculations', 
                'Backtesting algorithms',
                'Edge case testing',
                'Performance benchmarking'
            ]
        }


# Convenience function for getting test adapter
def get_test_adapter(date: str = '2017-03-24') -> TestDataQuoteAdapter:
    """Get a configured test data adapter."""
    return TestDataQuoteAdapter(date)