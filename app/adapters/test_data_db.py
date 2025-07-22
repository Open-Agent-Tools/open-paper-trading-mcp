"""
Database-backed test data adapter for Phase 3.

This adapter retrieves test data from the database instead of CSV files,
providing better performance and consistency.
"""

from datetime import date, datetime
from typing import Any

from sqlalchemy import select

from ..models.assets import Asset, Option, Stock, asset_factory
from ..models.database.trading import DevOptionQuote, DevStockQuote
from ..models.quotes import OptionQuote, OptionsChain, Quote
from ..services.greeks import calculate_option_greeks
from ..storage.database import get_async_session
from .base import AdapterConfig, QuoteAdapter


class TestDataDBError(Exception):
    """Error accessing test data from database."""

    pass


class DevDataQuoteAdapter(QuoteAdapter):
    """
    Database-backed test data adapter for development and testing.

    Provides fast access to test data stored in PostgreSQL database tables
    with support for multiple test scenarios and date ranges.
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
            scenario: Test scenario to use (default: "default")
            config: Adapter configuration, will create default if None
        """
        if config is None:
            config = AdapterConfig()

        self.config = config
        self.name = "DevDataQuoteAdapter"
        self.enabled = True

        self.current_date = datetime.strptime(current_date, "%Y-%m-%d").date()
        self.scenario = scenario

        # Cache for performance
        self._stock_cache: dict[str, DevStockQuote] = {}
        self._option_cache: dict[str, DevOptionQuote] = {}
        self._cache_loaded = False

    async def _load_cache(self) -> None:
        """Load test data into cache for better performance."""
        if self._cache_loaded:
            return

        async for db in get_async_session():
            # Load stock quotes for current date and scenario
            stock_result = await db.execute(
                select(DevStockQuote).where(
                    DevStockQuote.quote_date == self.current_date,
                    DevStockQuote.scenario == self.scenario,
                )
            )
            stock_quotes = stock_result.scalars().all()

            for quote in stock_quotes:
                self._stock_cache[quote.symbol] = quote

            # Load option quotes for current date and scenario
            option_result = await db.execute(
                select(DevOptionQuote).where(
                    DevOptionQuote.quote_date == self.current_date,
                    DevOptionQuote.scenario == self.scenario,
                )
            )
            option_quotes = option_result.scalars().all()

            for quote in option_quotes:
                self._option_cache[quote.symbol] = quote

            self._cache_loaded = True
            break

    def set_date(self, date_str: str) -> None:
        """Set the current date for quote retrieval."""
        self.current_date = datetime.strptime(date_str, "%Y-%m-%d").date()
        self._cache_loaded = False
        self._stock_cache.clear()
        self._option_cache.clear()

    def set_scenario(self, scenario: str) -> None:
        """Set the test scenario."""
        self.scenario = scenario
        self._cache_loaded = False
        self._stock_cache.clear()
        self._option_cache.clear()

    async def get_available_dates(self) -> list[str]:
        """Get list of available test dates."""
        async for db in get_async_session():
            result = await db.execute(
                select(DevStockQuote.quote_date.distinct())
                .where(DevStockQuote.scenario == self.scenario)
                .order_by(DevStockQuote.quote_date)
            )
            dates = result.scalars().all()
            return [
                date.strftime("%Y-%m-%d") if hasattr(date, "strftime") else str(date)
                for date in dates
            ]

        return []

    async def get_available_scenarios(self) -> list[str]:
        """Get list of available test scenarios."""
        async for db in get_async_session():
            result = await db.execute(
                select(DevStockQuote.scenario.distinct())
                .where(DevStockQuote.scenario.is_not(None))
                .order_by(DevStockQuote.scenario)
            )
            scenarios = result.scalars().all()
            return [scenario for scenario in scenarios if scenario]

        return []

    async def get_quote(self, asset: Asset) -> Quote | None:
        """Get a single quote for an asset."""
        await self._load_cache()

        if isinstance(asset, Stock):
            return await self._get_stock_quote(asset)
        elif isinstance(asset, Option):
            return await self._get_option_quote(asset)
        else:
            return None

    async def _get_stock_quote(self, asset: Asset) -> Quote | None:
        """Get stock quote from database cache."""
        stock_quote = self._stock_cache.get(asset.symbol)

        if stock_quote is None:
            return None

        return Quote(
            asset=asset,
            quote_date=(
                datetime.combine(stock_quote.quote_date, datetime.min.time())
                if isinstance(stock_quote.quote_date, date)
                else datetime.fromisoformat(str(stock_quote.quote_date))
            ),
            price=float(stock_quote.price) if stock_quote.price else 0.0,
            bid=float(stock_quote.bid) if stock_quote.bid else 0.0,
            ask=float(stock_quote.ask) if stock_quote.ask else 0.0,
            bid_size=100,  # Default approximation
            ask_size=100,  # Default approximation
            volume=stock_quote.volume if stock_quote.volume is not None else 0,
        )

    async def _get_option_quote(self, asset: Option) -> OptionQuote | None:
        """Get option quote from database cache."""
        option_quote = self._option_cache.get(asset.symbol)

        if option_quote is None:
            return None

        # Get underlying price
        underlying_price = None
        if asset.underlying:
            underlying_quote = await self._get_stock_quote(asset.underlying)
            if underlying_quote:
                underlying_price = underlying_quote.price

        price = float(option_quote.price) if option_quote.price else None
        bid = float(option_quote.bid) if option_quote.bid else None
        ask = float(option_quote.ask) if option_quote.ask else None

        # Calculate Greeks if we have sufficient data
        greeks = None
        if (
            price is not None
            and underlying_price is not None
            and asset.strike
            and asset.expiration_date
        ):
            try:
                greeks = calculate_option_greeks(
                    option_type=asset.option_type.lower(),
                    strike=asset.strike,
                    underlying_price=underlying_price,
                    days_to_expiration=(asset.expiration_date - self.current_date).days,
                    option_price=price,  # Use the option price from the quote
                    volatility=0.25,  # 25% implied volatility
                )
            except Exception:
                # If Greeks calculation fails, continue without them
                pass

        return OptionQuote(
            asset=asset,
            quote_date=(
                datetime.combine(option_quote.quote_date, datetime.min.time())
                if isinstance(option_quote.quote_date, date)
                else datetime.fromisoformat(str(option_quote.quote_date))
            ),
            price=price,
            bid=bid,
            ask=ask,
            underlying_price=underlying_price,
            volume=option_quote.volume if option_quote.volume is not None else 0,
            open_interest=None,  # Not in test data
            # Greeks
            delta=greeks.get("delta") if greeks else None,
            gamma=greeks.get("gamma") if greeks else None,
            theta=greeks.get("theta") if greeks else None,
            vega=greeks.get("vega") if greeks else None,
            rho=greeks.get("rho") if greeks else None,
        )

    async def get_quotes(self, assets: list[Asset]) -> dict[Asset, Quote]:
        """Get quotes for multiple assets."""
        await self._load_cache()

        results = {}
        for asset in assets:
            quote = await self.get_quote(asset)
            if quote:
                results[asset] = quote

        return results

    async def get_chain(
        self, underlying: str, expiration_date: datetime | None = None
    ) -> list[Asset]:
        """Get option chain for an underlying (returns list of assets)."""
        await self._load_cache()

        assets: list[Asset] = []

        # Filter options by underlying
        for symbol, option_quote in self._option_cache.items():
            if option_quote.underlying == underlying:
                # Create option asset
                asset = asset_factory(symbol)
                if isinstance(asset, Option):
                    # Filter by expiration if specified
                    if (
                        expiration_date is None
                        or asset.expiration_date == expiration_date.date()
                    ):
                        assets.append(asset)

        return assets

    async def get_options_chain(
        self, underlying: str, expiration_date: datetime | None = None
    ) -> OptionsChain | None:
        """Get complete options chain with quotes."""
        await self._load_cache()

        # Get underlying asset and price
        underlying_asset = asset_factory(underlying)
        if not isinstance(underlying_asset, Stock):
            return None

        underlying_quote = await self._get_stock_quote(underlying_asset)
        underlying_price = underlying_quote.price if underlying_quote else None

        # Get option assets
        option_assets = await self.get_chain(underlying, expiration_date)

        if not option_assets:
            return None

        # Separate calls and puts
        calls = []
        puts = []
        target_expiration = None

        for asset in option_assets:
            if isinstance(asset, Option):
                option_quote = await self._get_option_quote(asset)
                if option_quote:
                    if asset.option_type.upper() == "CALL":
                        calls.append(option_quote)
                    elif asset.option_type.upper() == "PUT":
                        puts.append(option_quote)

                    # Set target expiration
                    if target_expiration is None:
                        target_expiration = asset.expiration_date

        if target_expiration is None:
            return None

        return OptionsChain(
            underlying_symbol=underlying,
            expiration_date=target_expiration,
            underlying_price=underlying_price,
            calls=calls,
            puts=puts,
            quote_time=datetime.combine(self.current_date, datetime.min.time()),
        )

    async def is_market_open(self) -> bool:
        """Check if the market is currently open (always True for test data)."""
        return True

    async def get_market_hours(self) -> dict[str, Any]:
        """Get market hours information."""
        return {
            "is_open": True,
            "opens_at": f"{self.current_date}T14:30:00Z",
            "closes_at": f"{self.current_date}T21:00:00Z",
        }

    # Extended methods for compatibility

    async def get_stock_info(self, symbol: str) -> dict[str, Any]:
        """Get stock information."""
        return {
            "symbol": symbol.upper(),
            "company_name": f"{symbol.upper()} Inc.",
            "sector": "Technology",
            "industry": "Software",
            "description": f"Test company for {symbol.upper()}",
            "market_cap": "1000000000",
            "pe_ratio": "25.0",
            "dividend_yield": "0.0",
            "high_52_weeks": "200.0",
            "low_52_weeks": "100.0",
            "average_volume": "1000000",
            "tradeable": True,
        }

    async def get_price_history(self, symbol: str, period: str) -> dict[str, Any]:
        """Get historical price data."""
        return {
            "symbol": symbol.upper(),
            "period": period,
            "interval": "day",
            "data_points": [
                {
                    "date": self.current_date.strftime("%Y-%m-%d"),
                    "open": 150.0,
                    "high": 155.0,
                    "low": 148.0,
                    "close": 152.0,
                    "volume": 1000000,
                }
            ],
        }

    async def get_stock_news(self, symbol: str) -> dict[str, Any]:
        """Get stock news."""
        return {
            "symbol": symbol.upper(),
            "news": [
                {
                    "title": f"Test news for {symbol.upper()}",
                    "summary": f"This is test news for {symbol.upper()}",
                    "published_at": self.current_date.strftime("%Y-%m-%d"),
                }
            ],
        }

    async def get_top_movers(self) -> dict[str, Any]:
        """Get top movers."""
        return {
            "movers": [
                {
                    "symbol": "AAPL",
                    "change_percent": "2.5",
                    "price": "150.00",
                }
            ]
        }

    async def search_stocks(self, query: str) -> dict[str, Any]:
        """Search for stocks."""
        return {
            "query": query,
            "results": [
                {
                    "symbol": query.upper(),
                    "name": f"{query.upper()} Inc.",
                    "tradeable": True,
                }
            ],
        }

    def get_sample_data_info(self) -> dict[str, Any]:
        """Get information about sample data."""
        return {
            "adapter": "DevDataQuoteAdapter",
            "current_date": self.current_date.strftime("%Y-%m-%d"),
            "scenario": self.scenario,
            "stock_quotes_cached": len(self._stock_cache),
            "option_quotes_cached": len(self._option_cache),
            "message": "Using database-backed test data from PostgreSQL",
        }

    def get_expiration_dates(self, underlying: str) -> list[date]:
        """Get available expiration dates for an underlying symbol."""
        dates = []
        for _symbol, option_quote in self._option_cache.items():
            if option_quote.underlying == underlying:
                dates.append(option_quote.expiration)
        return sorted({d.date() if hasattr(d, "date") else d for d in dates})

    def get_test_scenarios(self) -> dict[str, Any]:
        """Get available test scenarios."""
        return {
            "current_scenario": self.scenario,
            "available_scenarios": ["default"],  # Will be expanded when we add more
            "message": "Database-backed test scenarios",
        }

    def get_available_symbols(self) -> list[str]:
        """Get list of available symbols."""
        symbols: set[str] = set()
        symbols.update(self._stock_cache.keys())
        symbols.update(self._option_cache.keys())
        return sorted(symbols)

    def get_performance_metrics(self) -> dict[str, Any]:
        """Get performance metrics for the adapter."""
        return {
            "adapter_name": "test_data_db",
            "current_date": self.current_date.strftime("%Y-%m-%d"),
            "scenario": self.scenario,
            "cache_loaded": self._cache_loaded,
            "stock_quotes_cached": len(self._stock_cache),
            "option_quotes_cached": len(self._option_cache),
            "total_quotes_cached": len(self._stock_cache) + len(self._option_cache),
        }

    def reset_metrics(self) -> None:
        """Reset performance metrics."""
        self._cache_loaded = False
        self._stock_cache.clear()
        self._option_cache.clear()


# Alias for backward compatibility
TestDataDBQuoteAdapter = DevDataQuoteAdapter
