"""
Robinhood adapter for live market data integration.
"""

import asyncio
import random
import time
from collections.abc import Callable
from datetime import UTC, date, datetime
from functools import wraps
from typing import Any, TypeVar

import robin_stocks.robinhood as rh  # type: ignore

from app.adapters.base import AdapterConfig, QuoteAdapter
from app.auth.session_manager import get_session_manager
from app.core.logging import logger
from app.models.assets import Asset, Option, Stock, asset_factory
from app.models.quotes import OptionQuote, OptionsChain, Quote

F = TypeVar("F", bound=Callable[..., Any])


def retry_with_backoff(
    max_retries: int = 3, base_delay: float = 1.0, max_delay: float = 60.0
) -> Callable[[F], F]:
    """Decorator for adding exponential backoff retry logic to async methods."""

    def decorator(func: F) -> F:
        @wraps(func)
        async def wrapper(*args: Any, **kwargs: Any) -> Any:
            for attempt in range(max_retries):
                try:
                    return await func(*args, **kwargs)
                except Exception as e:
                    if attempt == max_retries - 1:
                        logger.error(f"Final attempt failed for {func.__name__}: {e}")
                        raise
                    delay = min(
                        base_delay * (2**attempt) + random.uniform(0, 1), max_delay
                    )
                    logger.warning(
                        f"Attempt {attempt + 1} failed for {func.__name__}, retrying in {delay:.2f}s: {e}"
                    )
                    await asyncio.sleep(delay)
            return None

        return wrapper  # type: ignore

    return decorator


class RobinhoodConfig(AdapterConfig):
    """Configuration for Robinhood adapter."""

    name: str = "robinhood"
    priority: int = 1
    cache_ttl: float = 300.0  # 5 minutes


class RobinhoodAdapter(QuoteAdapter):
    """Live market data adapter using Robinhood API."""

    def __init__(self, config: RobinhoodConfig | None = None):
        self.config = config or RobinhoodConfig()
        self.session_manager = get_session_manager()

        # Load credentials from environment variables
        import os

        username = os.getenv("ROBINHOOD_USERNAME")
        password = os.getenv("ROBINHOOD_PASSWORD")

        if username and password:
            self.session_manager.set_credentials(username, password)
            logger.info(f"✅ Robinhood credentials loaded for user: {username}")
        else:
            logger.warning("⚠️ Robinhood credentials not found in environment variables")

        # Performance metrics
        self._request_count = 0
        self._error_count = 0
        self._total_request_time = 0.0
        self._cache_hits = 0
        self._cache_misses = 0

        # Last known API status
        self._last_api_response_time: float | None = None
        self._last_error_time: datetime | None = None
        self._last_error_message: str | None = None

    async def _ensure_authenticated(self) -> bool:
        """Ensure we have valid authentication."""
        return await self.session_manager.ensure_authenticated()

    @retry_with_backoff(max_retries=3, base_delay=1.0)
    async def get_quote(self, asset: Asset) -> Quote | None:
        """Get a single quote for an asset."""
        start_time = time.time()
        symbol = asset.symbol

        logger.info(
            "quote_request_started",
            extra={
                "symbol": symbol,
                "asset_type": type(asset).__name__,
                "adapter": "robinhood",
            },
        )

        try:
            self._request_count += 1

            # Authentication is now handled by session manager in each API call

            if isinstance(asset, Stock):
                result = await self._get_stock_quote(asset)
            elif isinstance(asset, Option):
                result = await self._get_option_quote(asset)
            else:
                logger.warning(
                    "quote_request_unsupported_asset",
                    extra={
                        "symbol": symbol,
                        "asset_type": type(asset).__name__,
                        "adapter": "robinhood",
                    },
                )
                return None

            duration = time.time() - start_time
            self._total_request_time += duration
            self._last_api_response_time = duration

            if result:
                logger.info(
                    "quote_request_completed",
                    extra={
                        "symbol": symbol,
                        "price": result.price,
                        "volume": result.volume,
                        "duration": duration,
                        "adapter": "robinhood",
                    },
                )
            else:
                logger.warning(
                    "quote_request_no_data",
                    extra={
                        "symbol": symbol,
                        "duration": duration,
                        "adapter": "robinhood",
                    },
                )

            return result

        except Exception as e:
            duration = time.time() - start_time
            self._error_count += 1
            self._last_error_time = datetime.now(UTC)
            self._last_error_message = str(e)

            logger.error(
                "quote_request_failed",
                extra={
                    "symbol": symbol,
                    "error": str(e),
                    "duration": duration,
                    "adapter": "robinhood",
                },
            )
            raise

    async def _get_stock_quote(self, asset: Stock) -> Quote | None:
        """Get stock quote from Robinhood using persistent session."""
        try:
            # Use session manager for persistent authentication
            quote_data = await self.session_manager.with_session(
                rh.stocks.get_latest_price, asset.symbol
            )

            if not quote_data or not quote_data[0]:
                return None

            price = float(quote_data[0])

            # Get fundamentals for more data using persistent session
            fundamentals = await self.session_manager.with_session(
                rh.stocks.get_fundamentals, asset.symbol
            )

            if fundamentals and fundamentals[0]:
                fund_data = fundamentals[0]
                volume = (
                    int(float(fund_data.get("volume", 0)))
                    if fund_data.get("volume")
                    else None
                )
            else:
                volume = None

            return Quote(
                asset=asset,
                quote_date=datetime.now(UTC),
                price=price,
                bid=price - 0.01,  # Approximation
                ask=price + 0.01,  # Approximation
                bid_size=100,  # Default approximation
                ask_size=100,  # Default approximation
                volume=volume,
            )

        except Exception as e:
            logger.error(f"Error getting stock quote for {asset.symbol}: {e}")
            return None

    async def _get_option_quote(self, asset: Option) -> OptionQuote | None:
        """Get option quote from Robinhood using persistent session."""
        try:
            # Find the option instrument using persistent session
            option_data = await self.session_manager.with_session(
                rh.options.find_options_by_expiration_and_strike,
                asset.underlying.symbol,
                asset.expiration_date.isoformat(),
                asset.strike,
                asset.option_type.lower(),
            )

            if not option_data:
                return None

            instrument = option_data[0]
            market_data = await self.session_manager.with_session(
                rh.options.get_option_market_data_by_id, instrument["id"]
            )

            if not market_data:
                return None

            # Get underlying price
            if isinstance(asset.underlying, Stock):
                underlying_quote = await self._get_stock_quote(asset.underlying)
                underlying_price = underlying_quote.price if underlying_quote else None
            else:
                underlying_price = None

            bid = (
                float(market_data.get("bid_price", 0))
                if market_data.get("bid_price")
                else 0
            )
            ask = (
                float(market_data.get("ask_price", 0))
                if market_data.get("ask_price")
                else 0
            )
            price = (bid + ask) / 2 if bid > 0 and ask > 0 else None

            return OptionQuote(
                asset=asset,
                quote_date=datetime.now(UTC),
                price=price,
                bid=bid,
                ask=ask,
                underlying_price=underlying_price,
                volume=(
                    int(float(market_data.get("volume", 0)))
                    if market_data.get("volume")
                    else None
                ),
                open_interest=(
                    int(float(market_data.get("open_interest", 0)))
                    if market_data.get("open_interest")
                    else None
                ),
            )

        except Exception as e:
            logger.error(f"Error getting option quote for {asset.symbol}: {e}")
            return None

    async def get_quotes(self, assets: list[Asset]) -> dict[Asset, Quote]:
        """Get quotes for multiple assets."""
        results = {}
        for asset in assets:
            quote = await self.get_quote(asset)
            if quote:
                results[asset] = quote
        return results

    @retry_with_backoff(max_retries=3, base_delay=1.0)
    async def get_chain(
        self, underlying: str, expiration_date: datetime | None = None
    ) -> list[Asset]:
        """Get option chain for an underlying (returns list of assets)."""
        # This method returns just the assets, not full quotes
        if not await self._ensure_authenticated():
            return []

        try:
            chains_data = rh.options.get_chains(underlying)
            logger.info(
                f"get_chain returned: type={type(chains_data)}, value={chains_data}"
            )
        except Exception as e:
            logger.error(f"Error calling rh.options.get_chains({underlying}): {e}")
            return []

        if not chains_data:
            return []

        assets = []

        # Handle different return types from get_chains
        if isinstance(chains_data, list):
            chain_list = chains_data
        elif isinstance(chains_data, dict):
            chain_list = [chains_data]
        else:
            logger.error(
                f"Unexpected chains_data type in get_chain: {type(chains_data)}, content: {chains_data}"
            )
            return []

        for chain in chain_list:
            if not isinstance(chain, dict):
                logger.warning(
                    f"Expected dict in get_chain, got {type(chain)}: {chain}"
                )
                continue

            expiration = chain.get("expiration_date")
            if expiration_date and expiration != expiration_date.strftime("%Y-%m-%d"):
                continue

            # Get instruments for this expiration
            instruments = rh.options.get_option_instruments(
                underlying, expiration, option_type="both"
            )

            for instrument in instruments:
                asset = asset_factory(instrument.get("url", ""))
                if asset:
                    assets.append(asset)

        return assets

    @retry_with_backoff(max_retries=3, base_delay=1.0)
    async def get_options_chain(
        self, underlying: str, expiration_date: datetime | None = None
    ) -> OptionsChain | None:
        """Get complete options chain with quotes."""
        if not await self._ensure_authenticated():
            return None

        # Get underlying asset and price
        underlying_asset = asset_factory(underlying)
        if not underlying_asset:
            return None

        if isinstance(underlying_asset, Stock):
            underlying_quote = await self._get_stock_quote(underlying_asset)
            underlying_price = underlying_quote.price if underlying_quote else None
        else:
            underlying_price = None

        # Get chains data
        try:
            chains_data = rh.options.get_chains(underlying)
            logger.info(f"Successfully retrieved chains data for {underlying}")

        except Exception as e:
            logger.error(f"Error calling rh.options.get_chains({underlying}): {e}")
            return None

        if not chains_data:
            logger.warning(f"No chains data returned for {underlying}")
            return None

        # If no expiration date specified, return empty chain (UI should select expiration first)
        if expiration_date is None:
            logger.info(
                f"No expiration date specified for {underlying}, returning empty chain"
            )
            return OptionsChain(
                underlying_symbol=underlying,
                expiration_date=datetime.now(UTC).date(),
                underlying_price=underlying_price,
                calls=[],
                puts=[],
                quote_time=datetime.now(UTC),
            )

        calls = []
        puts = []
        target_expiration = None

        # Handle robinhood chains_data structure - it's a dict with expiration_dates list
        try:
            if not isinstance(chains_data, dict):
                logger.error(f"Expected dict from get_chains, got {type(chains_data)}")
                return None

            # Get list of expiration dates from the chain data
            expiration_dates_list = chains_data.get("expiration_dates", [])
            if not expiration_dates_list:
                logger.warning(
                    f"No expiration_dates found in chains_data for {underlying}"
                )
                return None

            logger.info(
                f"Found {len(expiration_dates_list)} expiration dates for {underlying}"
            )

            # Process each expiration date
            for expiration_str in expiration_dates_list:
                chain_exp_date = datetime.strptime(expiration_str, "%Y-%m-%d").date()

                # Filter by expiration if specified
                if expiration_date:
                    exp_date = (
                        expiration_date.date()
                        if isinstance(expiration_date, datetime)
                        else expiration_date
                    )
                    if chain_exp_date != exp_date:
                        continue

                target_expiration = chain_exp_date
                logger.debug(f"Processing expiration {expiration_str}")

                # Get option instruments for this expiration
                all_instruments = rh.options.find_options_by_expiration(
                    underlying, expiration_str
                )

                if not all_instruments:
                    continue

                # Separate calls and puts
                all_calls = [
                    opt for opt in all_instruments if opt.get("type") == "call"
                ]
                all_puts = [opt for opt in all_instruments if opt.get("type") == "put"]

                # Sort by strike price
                all_calls.sort(key=lambda x: float(x.get("strike_price", 0)))
                all_puts.sort(key=lambda x: float(x.get("strike_price", 0)))

                # Select strikes around current underlying price (10 below, 10 above)
                if underlying_price:
                    # Find strikes closest to underlying price
                    call_instruments = self._select_strikes_around_price(
                        all_calls, underlying_price, 10
                    )
                    put_instruments = self._select_strikes_around_price(
                        all_puts, underlying_price, 10
                    )
                else:
                    # Fallback to first 10 strikes if no underlying price
                    call_instruments = all_calls[:10]
                    put_instruments = all_puts[:10]

                logger.debug(
                    f"Found {len(call_instruments) if call_instruments else 0} calls, {len(put_instruments) if put_instruments else 0} puts for {expiration_str}"
                )

                # Process calls
                if call_instruments:
                    for instrument in call_instruments:
                        option_quote = self._create_option_quote_from_instrument(
                            instrument, underlying_asset, underlying_price
                        )
                        if option_quote:
                            calls.append(option_quote)

                # Process puts
                if put_instruments:
                    for instrument in put_instruments:
                        option_quote = self._create_option_quote_from_instrument(
                            instrument, underlying_asset, underlying_price
                        )
                        if option_quote:
                            puts.append(option_quote)

                # Only process the requested expiration date
                if expiration_date:
                    break  # Got the requested expiration

        except Exception as e:
            logger.error(f"Error processing chains_data: {e}")
            return None

        if not target_expiration:
            return None

        return OptionsChain(
            underlying_symbol=underlying,
            expiration_date=target_expiration,
            underlying_price=underlying_price,
            calls=calls,
            puts=puts,
            quote_time=datetime.now(UTC),
        )

    def _create_option_asset(
        self, instrument: dict[str, Any], underlying_asset: Asset, option_type: str
    ) -> Option | None:
        """Create an Option asset from Robinhood instrument data."""
        try:
            strike = float(instrument.get("strike_price", 0))
            expiration_str = instrument.get("expiration_date")
            if not expiration_str:
                return None

            expiration = datetime.strptime(expiration_str, "%Y-%m-%d").date()

            # Create option symbol in standard format
            exp_str = expiration.strftime("%y%m%d")
            strike_str = f"{int(strike * 1000):08d}"
            type_char = "C" if option_type.lower() == "call" else "P"
            symbol = f"{underlying_asset.symbol}{exp_str}{type_char}{strike_str}"

            return Option(
                symbol=symbol,
                underlying=underlying_asset,
                option_type=option_type.upper(),
                strike=strike,
                expiration_date=expiration,
            )

        except Exception as e:
            logger.error(f"Error creating option asset: {e}")
            return None

    def _create_option_quote_from_instrument(
        self,
        instrument: dict[str, Any],
        underlying_asset: Asset,
        underlying_price: float | None,
    ) -> OptionQuote | None:
        """Create an OptionQuote directly from Robinhood instrument data."""
        try:
            # Create the option asset first
            option_type = instrument.get("type", "").lower()
            option_asset = self._create_option_asset(
                instrument, underlying_asset, option_type
            )
            if not option_asset:
                return None

            # Extract pricing data from instrument
            bid = (
                float(instrument.get("bid_price", 0))
                if instrument.get("bid_price")
                else 0.0
            )
            ask = (
                float(instrument.get("ask_price", 0))
                if instrument.get("ask_price")
                else 0.0
            )

            # Use mark_price as the primary price, fallback to midpoint of bid/ask
            price = None
            mark_price = instrument.get("mark_price")
            if mark_price is not None:
                price = float(mark_price)
            elif bid and ask:
                price = (bid + ask) / 2

            volume = (
                int(float(instrument.get("volume", 0)))
                if instrument.get("volume")
                else None
            )
            open_interest = (
                int(float(instrument.get("open_interest", 0)))
                if instrument.get("open_interest")
                else None
            )

            # Extract Greeks if available
            delta = (
                float(instrument.get("delta", 0)) if instrument.get("delta") else None
            )
            gamma = (
                float(instrument.get("gamma", 0)) if instrument.get("gamma") else None
            )
            theta = (
                float(instrument.get("theta", 0)) if instrument.get("theta") else None
            )
            vega = float(instrument.get("vega", 0)) if instrument.get("vega") else None
            rho = float(instrument.get("rho", 0)) if instrument.get("rho") else None
            implied_volatility = (
                float(instrument.get("implied_volatility", 0))
                if instrument.get("implied_volatility")
                else None
            )

            return OptionQuote(
                asset=option_asset,
                quote_date=datetime.now(UTC),
                price=price,
                bid=bid,
                ask=ask,
                underlying_price=underlying_price,
                volume=volume,
                open_interest=open_interest,
                # Greeks
                delta=delta,
                gamma=gamma,
                theta=theta,
                vega=vega,
                rho=rho,
                # Additional fields
                iv=implied_volatility,
            )

        except Exception as e:
            logger.error(f"Error creating option quote from instrument: {e}")
            return None

    def _select_strikes_around_price(
        self, options: list[dict], underlying_price: float, count: int
    ) -> list[dict]:
        """Select strikes centered around the underlying price."""
        if not options or underlying_price <= 0:
            return options[:count]

        # Find the option with strike closest to underlying price
        closest_idx = 0
        min_diff = float("inf")

        for i, option in enumerate(options):
            strike = float(option.get("strike_price", 0))
            diff = abs(strike - underlying_price)
            if diff < min_diff:
                min_diff = diff
                closest_idx = i

        # Select strikes around the closest one
        half_count = count // 2
        start_idx = max(0, closest_idx - half_count)
        end_idx = min(len(options), start_idx + count)

        # Adjust start if we're near the end
        if end_idx - start_idx < count:
            start_idx = max(0, end_idx - count)

        return options[start_idx:end_idx]

    async def is_market_open(self) -> bool:
        """Check if the market is currently open."""
        try:
            if not await self._ensure_authenticated():
                return False

            market_hours = rh.markets.get_market_hours("XNYS", datetime.now(UTC).date())
            if not market_hours:
                return False

            is_open = market_hours.get("is_open", False)
            return bool(is_open)

        except Exception as e:
            logger.error(f"Error checking market status: {e}")
            return False

    async def get_market_hours(self) -> dict[str, Any]:
        """Get market hours information."""
        try:
            if not await self._ensure_authenticated():
                return {}

            market_hours = rh.markets.get_market_hours("XNYS", datetime.now(UTC).date())
            return market_hours or {}

        except Exception as e:
            logger.error(f"Error getting market hours: {e}")
            return {}

    # ============================================================================
    # EXTENDED STOCK DATA METHODS
    # ============================================================================

    async def get_stock_info(self, symbol: str) -> dict[str, Any]:
        """Get detailed company information and fundamentals for a stock."""
        try:
            if not await self._ensure_authenticated():
                return {"error": "Authentication failed"}

            fundamentals_list = rh.stocks.get_fundamentals(symbol)
            instruments_list = rh.stocks.get_instruments_by_symbols(symbol)

            if not fundamentals_list or not instruments_list:
                return {"error": f"No company information found for symbol: {symbol}"}

            fundamental = fundamentals_list[0]
            instrument = instruments_list[0]
            company_name = rh.stocks.get_name_by_symbol(symbol)

            return {
                "symbol": symbol.upper(),
                "company_name": company_name or instrument.get("simple_name", "N/A"),
                "sector": fundamental.get("sector", "N/A"),
                "industry": fundamental.get("industry", "N/A"),
                "description": fundamental.get("description", "N/A"),
                "market_cap": fundamental.get("market_cap", "N/A"),
                "pe_ratio": fundamental.get("pe_ratio", "N/A"),
                "dividend_yield": fundamental.get("dividend_yield", "N/A"),
                "high_52_weeks": fundamental.get("high_52_weeks", "N/A"),
                "low_52_weeks": fundamental.get("low_52_weeks", "N/A"),
                "average_volume": fundamental.get("average_volume", "N/A"),
                "tradeable": instrument.get("tradeable", False),
            }

        except Exception as e:
            logger.error(f"Error getting stock info for {symbol}: {e}")
            return {"error": str(e)}

    async def get_price_history(self, symbol: str, period: str) -> dict[str, Any]:
        """Get historical price data for a stock."""
        try:
            if not await self._ensure_authenticated():
                return {"error": "Authentication failed"}

            interval_map = {
                "day": "5minute",
                "week": "hour",
                "month": "day",
                "3month": "day",
                "year": "week",
                "5year": "week",
            }
            interval = interval_map.get(period, "day")

            historical_data = rh.stocks.get_stock_historicals(
                symbol, interval, period, "regular"
            )

            if not historical_data:
                return {"error": f"No historical data found for {symbol} over {period}"}

            price_points = [
                {
                    "date": data_point.get("begins_at", "N/A"),
                    "open": float(data_point.get("open_price", 0)),
                    "high": float(data_point.get("high_price", 0)),
                    "low": float(data_point.get("low_price", 0)),
                    "close": float(data_point.get("close_price", 0)),
                    "volume": int(float(data_point.get("volume", 0))),
                }
                for data_point in historical_data
                if data_point and data_point.get("close_price")
            ]

            return {
                "symbol": symbol.upper(),
                "period": period,
                "interval": interval,
                "data_points": price_points,
            }

        except Exception as e:
            logger.error(f"Error getting price history for {symbol}: {e}")
            return {"error": str(e)}

    async def search_stocks(self, query: str) -> dict[str, Any]:
        """Search for stocks by symbol or company name."""
        try:
            if not await self._ensure_authenticated():
                return {"error": "Authentication failed"}

            search_results = rh.stocks.find_instrument_data(query)

            if not search_results:
                return {
                    "query": query,
                    "results": [],
                    "message": f"No stocks found matching query: {query}",
                }

            results = [
                {
                    "symbol": item.get("symbol", "").upper(),
                    "name": item.get("simple_name", "N/A"),
                    "tradeable": item.get("tradeable", False),
                }
                for item in search_results
                if item and item.get("symbol")
            ]

            return {
                "query": query,
                "results": results,
            }

        except Exception as e:
            logger.error(f"Error searching for stocks with query {query}: {e}")
            return {"query": query, "error": str(e), "results": []}

    def get_sample_data_info(self) -> dict[str, Any]:
        """Get information about sample data."""
        return {"message": "RobinhoodAdapter uses live data, not sample data"}

    def get_expiration_dates(self, underlying: str) -> list[date]:
        """Get available expiration dates for an underlying symbol."""
        # Note: This is a synchronous method to match base class interface
        # Authentication is handled by the robin_stocks library internally

        try:
            chains_data = rh.options.get_chains(underlying)
            if not chains_data or not isinstance(chains_data, dict):
                return []

            expiration_dates_list = chains_data.get("expiration_dates", [])
            if not expiration_dates_list:
                return []

            # Convert string dates to date objects
            dates = []
            for date_str in expiration_dates_list:
                try:
                    date_obj = datetime.strptime(date_str, "%Y-%m-%d").date()
                    dates.append(date_obj)
                except ValueError:
                    continue

            return sorted(dates)

        except Exception as e:
            logger.error(f"Error getting expiration dates for {underlying}: {e}")
            return []

    def get_test_scenarios(self) -> dict[str, Any]:
        """Get available test scenarios."""
        return {"message": "RobinhoodAdapter uses live data, no test scenarios"}

    def set_date(self, date: str) -> None:
        """Set the current date for test data."""
        # No-op for live data adapter
        pass

    def get_available_symbols(self) -> list[str]:
        """Get list of available symbols."""
        # This would need to be implemented with actual Robinhood API calls
        return []

    def get_performance_metrics(self) -> dict[str, Any]:
        """Get performance metrics for the adapter."""
        avg_response_time = (
            self._total_request_time / self._request_count
            if self._request_count > 0
            else 0
        )

        error_rate = (
            self._error_count / self._request_count if self._request_count > 0 else 0
        )

        return {
            "adapter_name": "robinhood",
            "request_count": self._request_count,
            "error_count": self._error_count,
            "error_rate": error_rate,
            "total_request_time": self._total_request_time,
            "avg_response_time": avg_response_time,
            "last_api_response_time": self._last_api_response_time,
            "last_error_time": (
                self._last_error_time.isoformat() if self._last_error_time else None
            ),
            "last_error_message": self._last_error_message,
            "cache_hits": self._cache_hits,
            "cache_misses": self._cache_misses,
            "cache_hit_rate": (
                self._cache_hits / (self._cache_hits + self._cache_misses)
                if (self._cache_hits + self._cache_misses) > 0
                else 0
            ),
            "auth_metrics": self.session_manager.get_auth_metrics(),
        }

    def reset_metrics(self) -> None:
        """Reset performance metrics."""
        self._request_count = 0
        self._error_count = 0
        self._total_request_time = 0.0
        self._cache_hits = 0
        self._cache_misses = 0
        self._last_api_response_time = None
        self._last_error_time = None
        self._last_error_message = None
