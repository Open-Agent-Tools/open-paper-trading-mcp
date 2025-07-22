"""
Test data adapter using historical options and stock data.

Adapted from reference implementation DevDataQuoteAdapter with modern Python patterns.

Data includes quotes for AAL and GOOG from 2017:
- AAL: 2017-01-27 to 2017-01-28 (Jan expiration + earnings)
- AAL: 2017-03-24 to 2017-03-25 (March expiration)
- GOOG: 2017-01-27 to 2017-01-28 (Jan expiration)
- GOOG: 2017-03-24 to 2017-03-25 (March expiration)

Data format: [symbol],[current_date],[bid],[ask]
"""

from datetime import date, datetime, timedelta
from typing import Any

from sqlalchemy import and_

from ..models.assets import Asset, Option, asset_factory
from ..models.database.trading import DevOptionQuote, DevScenario, DevStockQuote
from ..models.quotes import OptionQuote, OptionsChain, Quote
from ..services.greeks import calculate_option_greeks
from ..storage.database import get_sync_session
from .base import AdapterConfig, QuoteAdapter


class TestDataError(Exception):
    """Error loading or accessing test data."""

    pass


class DevDataQuoteAdapter(QuoteAdapter):
    """
    Quote adapter that provides historical test data for development and testing.

    Includes real market data with pre-calculated Greeks for comprehensive testing
    of options trading strategies and edge cases.
    """

    def __init__(
        self,
        current_date: str = "2017-03-24",
        scenario: str = "default",
        config: AdapterConfig | None = None,
    ):
        """
        Initialize with a specific date and scenario.

        Args:
            current_date: Date to retrieve quotes for (YYYY-MM-DD format)
            scenario: Test scenario to use (default, calm_market, volatile_market, trending_up)
            config: Adapter configuration, will create default if None
        """
        if config is None:
            config = AdapterConfig()

        self.config = config
        self.name = "DevDataQuoteAdapter"
        self.enabled = True
        self.scenario = scenario
        self.current_date = datetime.strptime(current_date, "%Y-%m-%d").date()
        self._quote_cache: dict[str, Any] = {}  # Small cache for performance

    def set_date(self, date_str: str) -> None:
        """Set the current date for quote retrieval."""
        self.current_date = datetime.strptime(date_str, "%Y-%m-%d").date()
        self._quote_cache.clear()  # Clear cache when date changes

    async def switch_scenario(self, scenario_name: str) -> None:
        """Switch to different test scenario."""
        with get_sync_session() as db:
            scenario = (
                db.query(DevScenario).filter(DevScenario.name == scenario_name).first()
            )
            if scenario:
                self.scenario = scenario_name
                start_date = scenario.start_date
                if hasattr(start_date, "date"):
                    start_date = start_date.date()
                else:
                    # Ensure it's a date object
                    from datetime import date as date_type

                    if not isinstance(start_date, date_type):
                        start_date = date_type.today()
                self.current_date = start_date
                self._quote_cache.clear()  # Clear cache when switching

    def get_available_dates(self) -> list[str]:
        """Get list of available test dates."""
        with get_sync_session() as db:
            # Get unique dates from stock quotes for current scenario
            dates = (
                db.query(DevStockQuote.quote_date)
                .filter(DevStockQuote.scenario == self.scenario)
                .distinct()
                .all()
            )
            return sorted([d[0].strftime("%Y-%m-%d") for d in dates])

    async def advance_date(self, days: int = 1) -> None:
        """Advance current date by specified days."""
        self.current_date += timedelta(days=days)
        self._quote_cache.clear()

    def _get_stock_quote_from_db(
        self, symbol: str, quote_date: date, scenario: str
    ) -> DevStockQuote | None:
        """Get stock quote from database."""
        with get_sync_session() as db:
            return (
                db.query(DevStockQuote)
                .filter(
                    and_(
                        DevStockQuote.symbol == symbol,
                        DevStockQuote.quote_date == quote_date,
                        DevStockQuote.scenario == scenario,
                    )
                )
                .first()
            )

    def _get_option_quote_from_db(
        self, symbol: str, quote_date: date, scenario: str
    ) -> DevOptionQuote | None:
        """Get option quote from database."""
        with get_sync_session() as db:
            return (
                db.query(DevOptionQuote)
                .filter(
                    and_(
                        DevOptionQuote.symbol == symbol,
                        DevOptionQuote.quote_date == quote_date,
                        DevOptionQuote.scenario == scenario,
                    )
                )
                .first()
            )

    def _cached_stock_quote(
        self, symbol: str, quote_date: date, scenario: str
    ) -> Quote | None:
        """Cached version of stock quote lookup."""
        db_quote = self._get_stock_quote_from_db(symbol, quote_date, scenario)
        if db_quote:
            asset = asset_factory(symbol)
            if asset:
                # Convert date properly
                quote_date_val = db_quote.quote_date
                if hasattr(quote_date_val, "date"):
                    quote_date_val = quote_date_val.date()
                else:
                    from datetime import date as date_type

                    if not isinstance(quote_date_val, date_type):
                        quote_date_val = date_type.today()

                return Quote(
                    quote_date=datetime.combine(quote_date_val, datetime.min.time()),
                    asset=asset,
                    bid=float(db_quote.bid) if db_quote.bid else 0.0,
                    ask=float(db_quote.ask) if db_quote.ask else 0.0,
                    price=float(db_quote.price) if db_quote.price else None,
                    bid_size=100,
                    ask_size=100,
                    volume=db_quote.volume or 1000,
                )
        return None

    def _cached_option_quote(
        self, symbol: str, quote_date: date, scenario: str
    ) -> OptionQuote | None:
        """Cached version of option quote lookup."""
        db_quote = self._get_option_quote_from_db(symbol, quote_date, scenario)
        if db_quote:
            asset = asset_factory(symbol)
            if asset and isinstance(asset, Option):
                # Convert date properly
                quote_date_val = db_quote.quote_date
                if hasattr(quote_date_val, "date"):
                    quote_date_val = quote_date_val.date()
                else:
                    from datetime import date as date_type

                    if not isinstance(quote_date_val, date_type):
                        quote_date_val = date_type.today()

                option_quote = OptionQuote(
                    quote_date=datetime.combine(quote_date_val, datetime.min.time()),
                    asset=asset,
                    bid=float(db_quote.bid) if db_quote.bid else None,
                    ask=float(db_quote.ask) if db_quote.ask else None,
                    price=float(db_quote.price) if db_quote.price else None,
                    volume=db_quote.volume,
                )

                # Calculate Greeks if we have price and underlying data
                if option_quote.price and option_quote.price > 0:
                    underlying_quote = self._cached_stock_quote(
                        asset.underlying.symbol, quote_date, scenario
                    )

                    if underlying_quote and underlying_quote.price:
                        try:
                            greeks = calculate_option_greeks(
                                option_type=asset.option_type,
                                strike=asset.strike,
                                underlying_price=underlying_quote.price,
                                days_to_expiration=asset.get_days_to_expiration(
                                    quote_date
                                ),
                                option_price=option_quote.price,
                            )

                            # Update option quote with Greeks
                            for greek_name, value in greeks.items():
                                if value is not None:
                                    setattr(option_quote, greek_name, value)
                        except Exception:
                            # Greeks calculation failed - continue without Greeks
                            pass

                return option_quote
        return None

    async def get_quote(self, asset: Asset) -> Quote | None:
        """
        Get quote for a symbol on the current date.

        Args:
            asset: Asset object

        Returns:
            Quote object or None if not found
        """
        # Check if it's an option or stock
        if isinstance(asset, Option):
            return self._cached_option_quote(
                asset.symbol, self.current_date, self.scenario
            )
        else:
            return self._cached_stock_quote(
                asset.symbol, self.current_date, self.scenario
            )

    async def get_quotes(self, assets: list[Asset]) -> dict[Asset, Quote]:
        """
        Get quotes for multiple symbols.

        Args:
            assets: List of assets to quote

        Returns:
            Dictionary mapping assets to their quotes
        """
        results: dict[Asset, Quote] = {}

        for asset in assets:
            quote = await self.get_quote(asset)
            if quote is not None:
                results[asset] = quote

        return results

    async def batch_get_quotes(self, symbols: list[str]) -> dict[str, Quote | None]:
        """
        Get quotes for multiple symbols efficiently.

        Args:
            symbols: List of symbol strings

        Returns:
            Dictionary mapping symbols to their quotes
        """
        results: dict[str, Quote | None] = {}

        # Group symbols by type (stock vs option)
        stock_symbols = []
        option_symbols = []

        for symbol in symbols:
            asset = asset_factory(symbol)
            if asset:
                if isinstance(asset, Option):
                    option_symbols.append(symbol)
                else:
                    stock_symbols.append(symbol)

        # Batch query stocks
        if stock_symbols:
            with get_sync_session() as db:
                stock_records = (
                    db.query(DevStockQuote)
                    .filter(
                        and_(
                            DevStockQuote.symbol.in_(stock_symbols),
                            DevStockQuote.quote_date == self.current_date,
                            DevStockQuote.scenario == self.scenario,
                        )
                    )
                    .all()
                )

                for record in stock_records:
                    quote = self._cached_stock_quote(
                        record.symbol, record.quote_date, self.scenario
                    )
                    if quote:
                        results[record.symbol] = quote

        # Batch query options
        if option_symbols:
            with get_sync_session() as db:
                option_records = (
                    db.query(DevOptionQuote)
                    .filter(
                        and_(
                            DevOptionQuote.symbol.in_(option_symbols),
                            DevOptionQuote.quote_date == self.current_date,
                            DevOptionQuote.scenario == self.scenario,
                        )
                    )
                    .all()
                )

                for record in option_records:
                    quote = self._cached_option_quote(
                        record.symbol, record.quote_date, self.scenario
                    )
                    if quote:
                        results[record.symbol] = quote

        # Add None for symbols that weren't found
        for symbol in symbols:
            if symbol not in results:
                results[symbol] = None

        return results

    async def get_quotes_for_date_range(
        self, symbol: str, start_date: date, end_date: date
    ) -> list[Quote]:
        """Get quotes for a date range (backtesting support)."""
        quotes: list[Quote] = []

        with get_sync_session() as db:
            # Check if it's a stock or option
            asset = asset_factory(symbol)
            if not asset:
                return quotes

            if isinstance(asset, Option):
                records = (
                    db.query(DevOptionQuote)
                    .filter(
                        and_(
                            DevOptionQuote.symbol == symbol,
                            DevOptionQuote.quote_date >= start_date,
                            DevOptionQuote.quote_date <= end_date,
                            DevOptionQuote.scenario == self.scenario,
                        )
                    )
                    .order_by(DevOptionQuote.quote_date)
                    .all()
                )

                for record in records:
                    quote = self._cached_option_quote(
                        symbol, record.quote_date, self.scenario
                    )
                    if quote:
                        quotes.append(quote)
            else:
                records = (
                    db.query(DevStockQuote)
                    .filter(
                        and_(
                            DevStockQuote.symbol == symbol,
                            DevStockQuote.quote_date >= start_date,
                            DevStockQuote.quote_date <= end_date,
                            DevStockQuote.scenario == self.scenario,
                        )
                    )
                    .order_by(DevStockQuote.quote_date)
                    .all()
                )

                for record in records:
                    quote = self._cached_stock_quote(
                        symbol, record.quote_date, self.scenario
                    )
                    if quote:
                        quotes.append(quote)

        return quotes

    async def get_chain(
        self, underlying: str, expiration_date: datetime | None = None
    ) -> list[Asset]:
        """Get option chain for an underlying."""
        # This is a basic implementation to satisfy the abstract method.
        # A full implementation would be similar to get_options_chain.
        return []

    async def get_options_chain(
        self, underlying: str, expiration: date | None = None
    ) -> OptionsChain | None:
        """
        Get options chain for an underlying asset.

        Args:
            underlying: Underlying asset symbol
            expiration: Specific expiration date, or None for all

        Returns:
            OptionsChain object with calls and puts, or None if not available
        """
        underlying_asset = asset_factory(underlying)
        if underlying_asset is None:
            return None

        # Get underlying quote
        underlying_quote = await self.get_quote(underlying_asset)
        underlying_price = underlying_quote.price if underlying_quote else None

        # Query options from database
        with get_sync_session() as db:
            query = db.query(DevOptionQuote).filter(
                and_(
                    DevOptionQuote.underlying == underlying,
                    DevOptionQuote.quote_date == self.current_date,
                    DevOptionQuote.scenario == self.scenario,
                )
            )

            if expiration:
                query = query.filter(DevOptionQuote.expiration == expiration)

            option_records = query.all()

        if not option_records:
            return None

        # Convert database records to OptionQuote objects
        calls = []
        puts = []

        for record in option_records:
            option_quote = self._cached_option_quote(
                record.symbol, record.quote_date, self.scenario
            )
            if option_quote and isinstance(option_quote.asset, Option):
                if option_quote.asset.option_type == "call":
                    calls.append(option_quote)
                else:
                    puts.append(option_quote)

        # Sort by strike price
        calls.sort(key=lambda x: x.asset.strike if isinstance(x.asset, Option) else 0)
        puts.sort(key=lambda x: x.asset.strike if isinstance(x.asset, Option) else 0)

        # Determine expiration date
        exp_date = expiration
        if exp_date is None and option_records:
            exp_date_val = option_records[0].expiration
            if hasattr(exp_date_val, "date"):
                exp_date_val = exp_date_val.date()
            else:
                from datetime import date as date_type

                if not isinstance(exp_date_val, date_type):
                    exp_date_val = date_type.today()
            exp_date = exp_date_val

        return OptionsChain(
            underlying_symbol=underlying_asset.symbol,
            expiration_date=exp_date or date.today(),
            underlying_price=underlying_price,
            calls=calls,
            puts=puts,
            quote_time=datetime.combine(self.current_date, datetime.min.time()),
        )

    def get_expiration_dates(self, underlying: str) -> list[date]:
        """
        Get available expiration dates for an underlying asset.

        Args:
            underlying: Underlying asset symbol

        Returns:
            List of expiration dates
        """
        with get_sync_session() as db:
            expiration_dates = (
                db.query(DevOptionQuote.expiration)
                .filter(
                    and_(
                        DevOptionQuote.underlying == underlying,
                        DevOptionQuote.quote_date == self.current_date,
                        DevOptionQuote.scenario == self.scenario,
                    )
                )
                .distinct()
                .all()
            )

            return sorted([exp[0] for exp in expiration_dates])

    async def is_market_open(self) -> bool:
        """
        Check if the market is currently open.
        For test data, always return True.

        Returns:
            True (test data is always available)
        """
        return True

    async def get_market_hours(self) -> dict[str, datetime]:
        """
        Get current market hours.
        For test data, return standard market hours.

        Returns:
            Dictionary with 'open' and 'close' times
        """
        today = datetime.now().replace(hour=9, minute=30, second=0, microsecond=0)
        return {"open": today, "close": today.replace(hour=16, minute=0)}

    def supports_symbol(self, symbol: str) -> bool:
        """
        Check if this adapter supports the given symbol.

        Args:
            symbol: Symbol to check

        Returns:
            True if symbol exists in test data
        """
        try:
            asset_obj = asset_factory(symbol)
            if asset_obj is None:
                return False

            with get_sync_session() as db:
                # Check stock quotes
                stock_exists = (
                    db.query(DevStockQuote)
                    .filter(
                        and_(
                            DevStockQuote.symbol == symbol,
                            DevStockQuote.quote_date == self.current_date,
                            DevStockQuote.scenario == self.scenario,
                        )
                    )
                    .first()
                    is not None
                )

                if stock_exists:
                    return True

                # Check option quotes
                option_exists = (
                    db.query(DevOptionQuote)
                    .filter(
                        and_(
                            DevOptionQuote.symbol == symbol,
                            DevOptionQuote.quote_date == self.current_date,
                            DevOptionQuote.scenario == self.scenario,
                        )
                    )
                    .first()
                    is not None
                )

                return option_exists
        except Exception:
            return False

    def get_last_updated(self, symbol: str) -> datetime | None:
        """
        Get the last update time for a symbol's quote.

        Args:
            symbol: Symbol to check

        Returns:
            Last update timestamp (the test data date)
        """
        try:
            return datetime.combine(self.current_date, datetime.min.time())
        except Exception:
            return None

    def health_check(self) -> dict[str, Any]:
        """
        Perform health check on the adapter.

        Returns:
            Dictionary with health status and metrics
        """
        try:
            with get_sync_session() as db:
                # Count unique symbols for current date and scenario
                stock_count = (
                    db.query(DevStockQuote.symbol)
                    .filter(
                        and_(
                            DevStockQuote.quote_date == self.current_date,
                            DevStockQuote.scenario == self.scenario,
                        )
                    )
                    .distinct()
                    .count()
                )

                option_count = (
                    db.query(DevOptionQuote.symbol)
                    .filter(
                        and_(
                            DevOptionQuote.quote_date == self.current_date,
                            DevOptionQuote.scenario == self.scenario,
                        )
                    )
                    .distinct()
                    .count()
                )

                # Check if database has data
                total_stock_quotes = db.query(DevStockQuote).count()
                total_option_quotes = db.query(DevOptionQuote).count()

            return {
                "name": self.name,
                "enabled": self.enabled,
                "status": "healthy",
                "current_date": self.current_date.strftime("%Y-%m-%d"),
                "current_scenario": self.scenario,
                "available_stocks": stock_count,
                "available_options": option_count,
                "total_stock_quotes_in_db": total_stock_quotes,
                "total_option_quotes_in_db": total_option_quotes,
                "database_connected": True,
                "last_check": datetime.now(),
            }
        except Exception as e:
            return {
                "name": self.name,
                "enabled": self.enabled,
                "status": "error",
                "error": str(e),
                "last_check": datetime.now(),
            }

    def get_available_symbols(self) -> list[str]:
        """Get all available symbols in test data."""
        with get_sync_session() as db:
            # Get stock symbols
            stock_symbols = (
                db.query(DevStockQuote.symbol)
                .filter(
                    and_(
                        DevStockQuote.quote_date == self.current_date,
                        DevStockQuote.scenario == self.scenario,
                    )
                )
                .distinct()
                .all()
            )

            # Get option symbols
            option_symbols = (
                db.query(DevOptionQuote.symbol)
                .filter(
                    and_(
                        DevOptionQuote.quote_date == self.current_date,
                        DevOptionQuote.scenario == self.scenario,
                    )
                )
                .distinct()
                .all()
            )

            # Combine and return sorted list
            all_symbols = set(
                [s[0] for s in stock_symbols] + [s[0] for s in option_symbols]
            )
            return sorted(all_symbols)

    def get_underlying_symbols(self) -> list[str]:
        """Get underlying asset symbols (stocks)."""
        with get_sync_session() as db:
            underlyings = (
                db.query(DevStockQuote.symbol)
                .filter(
                    and_(
                        DevStockQuote.quote_date == self.current_date,
                        DevStockQuote.scenario == self.scenario,
                    )
                )
                .distinct()
                .all()
            )

            return sorted([u[0] for u in underlyings])

    def get_test_scenarios(self) -> dict[str, Any]:
        """
        Get predefined test scenarios for common testing patterns.

        Returns:
            Dictionary of test scenarios with descriptions and data
        """
        return {
            "aal_earnings": {
                "description": "AAL around earnings (2017-01-27 to 2017-01-28)",
                "symbol": "AAL",
                "dates": ["2017-01-27", "2017-01-28"],
                "scenario": "earnings_volatility",
            },
            "aal_march_expiration": {
                "description": "AAL March expiration (2017-03-24 to 2017-03-25)",
                "symbol": "AAL",
                "dates": ["2017-03-24", "2017-03-25"],
                "scenario": "expiration_week",
            },
            "goog_january": {
                "description": "GOOG January expiration (2017-01-27 to 2017-01-28)",
                "symbol": "GOOG",
                "dates": ["2017-01-27", "2017-01-28"],
                "scenario": "high_price_stock",
            },
            "goog_march": {
                "description": "GOOG March expiration (2017-03-24 to 2017-03-25)",
                "symbol": "GOOG",
                "dates": ["2017-03-24", "2017-03-25"],
                "scenario": "high_price_expiration",
            },
        }

    def get_sample_data_info(self) -> dict[str, Any]:
        """
        Get information about the sample data included.

        Returns:
            Dictionary with sample data details
        """
        return {
            "description": "Historical options and stock data from 2017",
            "symbols": ["AAL", "GOOG"],
            "dates": ["2017-01-27", "2017-01-28", "2017-03-24", "2017-03-25"],
            "features": [
                "Real market bid/ask spreads",
                "Pre-calculated option Greeks",
                "Multiple expiration cycles",
                "Earnings event data (AAL)",
                "High-priced stock data (GOOG)",
            ],
            "sample_quotes": {
                "AAL": {
                    "2017-01-27": {"bid": 47.35, "ask": 47.37},
                    "2017-01-28": {"bid": 46.90, "ask": 47.00},
                },
                "AAL170203P00047000": {  # AAL Put, Feb 3, Strike 47
                    "2017-01-27": {"bid": 0.68, "ask": 0.72},
                    "2017-01-28": {"bid": 0.79, "ask": 0.86},
                },
            },
            "use_cases": [
                "Testing options strategies",
                "Validating Greeks calculations",
                "Backtesting algorithms",
                "Edge case testing",
                "Performance benchmarking",
            ],
        }


# Convenience function for getting test adapter
def get_test_adapter(
    date: str = "2017-03-24", scenario: str = "default"
) -> DevDataQuoteAdapter:
    """Get a configured test data adapter."""
    return DevDataQuoteAdapter(date, scenario)
