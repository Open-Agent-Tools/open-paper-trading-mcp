"""Tests for RobinhoodAdapter with comprehensive mocking."""

import asyncio
from datetime import date, datetime
from unittest.mock import AsyncMock, MagicMock, Mock, patch

import pytest

from app.adapters.robinhood import (
    RobinhoodAdapter,
    RobinhoodConfig,
    retry_with_backoff,
)
from app.models.assets import Option, Stock
from app.models.quotes import OptionQuote, OptionsChain, Quote


class TestRobinhoodConfig:
    """Test RobinhoodAdapter configuration."""

    def test_default_config(self):
        """Test default configuration values."""
        config = RobinhoodConfig()

        assert config.name == "robinhood"
        assert config.priority == 1
        assert config.cache_ttl == 300.0
        assert config.enabled is True

    def test_custom_config(self):
        """Test custom configuration values."""
        config = RobinhoodConfig(
            name="custom-robinhood", priority=5, cache_ttl=600.0, enabled=False
        )

        assert config.name == "custom-robinhood"
        assert config.priority == 5
        assert config.cache_ttl == 600.0
        assert config.enabled is False


class TestRetryDecorator:
    """Test retry with backoff decorator."""

    @pytest.mark.asyncio
    async def test_successful_execution(self):
        """Test that successful execution works without retries."""

        @retry_with_backoff(max_retries=3)
        async def success_func():
            return "success"

        result = await success_func()
        assert result == "success"

    @pytest.mark.asyncio
    async def test_retry_on_failure_then_success(self):
        """Test retry mechanism with eventual success."""
        call_count = 0

        @retry_with_backoff(max_retries=3, base_delay=0.1)
        async def retry_func():
            nonlocal call_count
            call_count += 1
            if call_count < 3:
                raise ValueError("Temporary error")
            return "success"

        result = await retry_func()
        assert result == "success"
        assert call_count == 3

    @pytest.mark.asyncio
    async def test_retry_exhaustion(self):
        """Test that exceptions are re-raised after max retries."""

        @retry_with_backoff(max_retries=2, base_delay=0.1)
        async def fail_func():
            raise ValueError("Persistent error")

        with pytest.raises(ValueError, match="Persistent error"):
            await fail_func()

    @pytest.mark.asyncio
    async def test_exponential_backoff(self):
        """Test exponential backoff timing (mocked sleep)."""
        call_count = 0
        sleep_calls = []

        async def mock_sleep(delay):
            sleep_calls.append(delay)

        @retry_with_backoff(max_retries=3, base_delay=1.0)
        async def retry_func():
            nonlocal call_count
            call_count += 1
            if call_count < 3:
                raise ValueError("Retry me")
            return "success"

        with patch("asyncio.sleep", side_effect=mock_sleep):
            result = await retry_func()

        assert result == "success"
        assert len(sleep_calls) == 2  # 2 retries
        # Verify exponential backoff (base * 2^attempt + jitter)
        assert sleep_calls[0] >= 1.0  # First retry delay
        assert sleep_calls[1] >= 2.0  # Second retry delay


class TestRobinhoodAdapter:
    """Test RobinhoodAdapter functionality."""

    @pytest.fixture
    def mock_session_manager(self):
        """Mock session manager."""
        mock_manager = MagicMock()
        mock_manager.ensure_authenticated = AsyncMock(return_value=True)
        mock_manager.get_auth_metrics = MagicMock(
            return_value={
                "total_login_attempts": 1,
                "successful_logins": 1,
                "last_login_time": datetime.now().isoformat(),
            }
        )
        return mock_manager

    @pytest.fixture
    def adapter(self, mock_session_manager):
        """Create adapter with mocked dependencies."""
        with patch(
            "app.adapters.robinhood.get_session_manager",
            return_value=mock_session_manager,
        ):
            adapter = RobinhoodAdapter()
        return adapter

    def test_adapter_initialization(self, adapter):
        """Test adapter initialization."""
        assert adapter.config.name == "robinhood"
        assert adapter._request_count == 0
        assert adapter._error_count == 0
        assert adapter._total_request_time == 0.0
        assert adapter._cache_hits == 0
        assert adapter._cache_misses == 0
        assert adapter._last_api_response_time is None
        assert adapter._last_error_time is None
        assert adapter._last_error_message is None

    def test_adapter_initialization_with_custom_config(self, mock_session_manager):
        """Test adapter initialization with custom config."""
        config = RobinhoodConfig(name="custom", priority=10, cache_ttl=120.0)

        with patch(
            "app.adapters.robinhood.get_session_manager",
            return_value=mock_session_manager,
        ):
            adapter = RobinhoodAdapter(config)

        assert adapter.config.name == "custom"
        assert adapter.config.priority == 10
        assert adapter.config.cache_ttl == 120.0

    @pytest.mark.asyncio
    async def test_ensure_authenticated_success(self, adapter, mock_session_manager):
        """Test successful authentication check."""
        mock_session_manager.ensure_authenticated.return_value = True

        result = await adapter._ensure_authenticated()
        assert result is True
        mock_session_manager.ensure_authenticated.assert_called_once()

    @pytest.mark.asyncio
    async def test_ensure_authenticated_failure(self, adapter, mock_session_manager):
        """Test failed authentication check."""
        mock_session_manager.ensure_authenticated.return_value = False

        result = await adapter._ensure_authenticated()
        assert result is False

    @pytest.mark.asyncio
    async def test_get_stock_quote_success(self, adapter):
        """Test successful stock quote retrieval."""
        stock = Stock(symbol="AAPL", name="Apple Inc.")

        # Mock robin_stocks responses
        mock_price_data = ["150.00"]
        mock_fundamentals_data = [{"volume": "1000000", "market_cap": "2500000000000"}]

        with (
            patch(
                "robin_stocks.robinhood.stocks.get_latest_price",
                return_value=mock_price_data,
            ),
            patch(
                "robin_stocks.robinhood.stocks.get_fundamentals",
                return_value=mock_fundamentals_data,
            ),
        ):
            quote = await adapter.get_quote(stock)

        assert quote is not None
        assert isinstance(quote, Quote)
        assert quote.asset.symbol == "AAPL"
        assert quote.price == 150.00
        assert quote.bid == 149.99  # price - 0.01
        assert quote.ask == 150.01  # price + 0.01
        assert quote.volume == 1000000
        assert adapter._request_count == 1
        assert adapter._error_count == 0

    @pytest.mark.asyncio
    async def test_get_stock_quote_no_data(self, adapter):
        """Test stock quote retrieval with no data."""
        stock = Stock(symbol="INVALID", name="Invalid Stock")

        # Mock empty responses
        with (
            patch("robin_stocks.robinhood.stocks.get_latest_price", return_value=[]),
            patch("robin_stocks.robinhood.stocks.get_fundamentals", return_value=[]),
        ):
            quote = await adapter.get_quote(stock)

        assert quote is None
        assert adapter._request_count == 1
        assert adapter._error_count == 0

    @pytest.mark.asyncio
    async def test_get_stock_quote_auth_failure(self, adapter, mock_session_manager):
        """Test stock quote retrieval with authentication failure."""
        stock = Stock(symbol="AAPL", name="Apple Inc.")
        mock_session_manager.ensure_authenticated.return_value = False

        quote = await adapter.get_quote(stock)

        assert quote is None
        assert adapter._request_count == 1
        assert adapter._error_count == 1

    @pytest.mark.asyncio
    async def test_get_stock_quote_api_error(self, adapter):
        """Test stock quote retrieval with API error."""
        stock = Stock(symbol="AAPL", name="Apple Inc.")

        with patch(
            "robin_stocks.robinhood.stocks.get_latest_price",
            side_effect=Exception("API Error"),
        ), pytest.raises(Exception, match="API Error"):
            await adapter.get_quote(stock)

        assert adapter._request_count == 1
        assert adapter._error_count == 1
        assert adapter._last_error_message == "API Error"

    @pytest.mark.asyncio
    async def test_get_option_quote_success(self, adapter):
        """Test successful option quote retrieval."""
        underlying = Stock(symbol="AAPL", name="Apple Inc.")
        option = Option(
            symbol="AAPL240119C00150000",
            underlying=underlying,
            option_type="CALL",
            strike=150.0,
            expiration_date=date(2024, 1, 19),
        )

        # Mock robin_stocks responses
        mock_option_data = [{"id": "option-123"}]
        mock_market_data = {
            "bid_price": "5.25",
            "ask_price": "5.75",
            "volume": "1000",
            "open_interest": "5000",
        }
        mock_stock_price = ["150.00"]
        mock_stock_fundamentals = [{}]

        with (
            patch(
                "robin_stocks.robinhood.options.find_options_by_expiration_and_strike",
                return_value=mock_option_data,
            ),
            patch(
                "robin_stocks.robinhood.options.get_option_market_data_by_id",
                return_value=mock_market_data,
            ),
            patch(
                "robin_stocks.robinhood.stocks.get_latest_price",
                return_value=mock_stock_price,
            ),
            patch(
                "robin_stocks.robinhood.stocks.get_fundamentals",
                return_value=mock_stock_fundamentals,
            ),
        ):
            quote = await adapter.get_quote(option)

        assert quote is not None
        assert isinstance(quote, OptionQuote)
        assert quote.asset.symbol == "AAPL240119C00150000"
        assert quote.bid == 5.25
        assert quote.ask == 5.75
        assert quote.price == 5.5  # (bid + ask) / 2
        assert quote.volume == 1000
        assert quote.open_interest == 5000
        assert quote.underlying_price == 150.0

    @pytest.mark.asyncio
    async def test_get_option_quote_no_data(self, adapter):
        """Test option quote retrieval with no data."""
        underlying = Stock(symbol="AAPL", name="Apple Inc.")
        option = Option(
            symbol="AAPL240119C00150000",
            underlying=underlying,
            option_type="CALL",
            strike=150.0,
            expiration_date=date(2024, 1, 19),
        )

        with patch(
            "robin_stocks.robinhood.options.find_options_by_expiration_and_strike",
            return_value=[],
        ):
            quote = await adapter.get_quote(option)

        assert quote is None

    @pytest.mark.asyncio
    async def test_get_quotes_multiple(self, adapter):
        """Test getting multiple quotes."""
        stock1 = Stock(symbol="AAPL", name="Apple Inc.")
        stock2 = Stock(symbol="GOOGL", name="Alphabet Inc.")

        # Mock responses for both stocks
        def mock_get_latest_price(symbol):
            if symbol == "AAPL":
                return ["150.00"]
            elif symbol == "GOOGL":
                return ["2500.00"]
            return []

        def mock_get_fundamentals(symbol):
            return [{"volume": "1000000"}]

        with (
            patch(
                "robin_stocks.robinhood.stocks.get_latest_price",
                side_effect=mock_get_latest_price,
            ),
            patch(
                "robin_stocks.robinhood.stocks.get_fundamentals",
                side_effect=mock_get_fundamentals,
            ),
        ):
            quotes = await adapter.get_quotes([stock1, stock2])

        assert len(quotes) == 2
        assert stock1 in quotes
        assert stock2 in quotes
        assert quotes[stock1].price == 150.00
        assert quotes[stock2].price == 2500.00

    @pytest.mark.asyncio
    async def test_get_chain_success(self, adapter):
        """Test getting option chain assets."""
        mock_chains_data = [{"expiration_date": "2024-01-19"}]
        mock_instruments = [{"url": "https://robinhood.com/instruments/option-123/"}]

        with (
            patch(
                "robin_stocks.robinhood.options.get_chains",
                return_value=mock_chains_data,
            ),
            patch(
                "robin_stocks.robinhood.options.get_option_instruments",
                return_value=mock_instruments,
            ),
            patch("app.models.assets.asset_factory") as mock_factory,
        ):
            mock_option = Option(
                symbol="AAPL240119C00150000",
                underlying=Stock(symbol="AAPL", name="Apple Inc."),
                option_type="CALL",
                strike=150.0,
                expiration_date=date(2024, 1, 19),
            )
            mock_factory.return_value = mock_option

            assets = await adapter.get_chain("AAPL")

        assert len(assets) == 1
        assert assets[0] == mock_option

    @pytest.mark.asyncio
    async def test_get_chain_auth_failure(self, adapter, mock_session_manager):
        """Test getting option chain with auth failure."""
        mock_session_manager.ensure_authenticated.return_value = False

        assets = await adapter.get_chain("AAPL")

        assert assets == []

    @pytest.mark.asyncio
    async def test_get_options_chain_success(self, adapter):
        """Test getting complete options chain with quotes."""
        mock_chains_data = [{"expiration_date": "2024-01-19"}]
        mock_stock_price = ["150.00"]
        mock_stock_fundamentals = [{}]
        mock_call_instruments = [
            {"strike_price": "150.00", "expiration_date": "2024-01-19"}
        ]
        mock_put_instruments = [
            {"strike_price": "150.00", "expiration_date": "2024-01-19"}
        ]
        mock_option_data_call = [{"id": "call-123"}]
        mock_option_data_put = [{"id": "put-123"}]
        mock_call_market_data = {"bid_price": "5.25", "ask_price": "5.75"}
        mock_put_market_data = {"bid_price": "3.15", "ask_price": "3.65"}

        with (
            patch(
                "robin_stocks.robinhood.options.get_chains",
                return_value=mock_chains_data,
            ),
            patch(
                "robin_stocks.robinhood.stocks.get_latest_price",
                return_value=mock_stock_price,
            ),
            patch(
                "robin_stocks.robinhood.stocks.get_fundamentals",
                return_value=mock_stock_fundamentals,
            ),
            patch(
                "robin_stocks.robinhood.options.get_option_instruments"
            ) as mock_get_instruments,
            patch(
                "robin_stocks.robinhood.options.find_options_by_expiration_and_strike"
            ) as mock_find_options,
            patch(
                "robin_stocks.robinhood.options.get_option_market_data_by_id"
            ) as mock_get_market_data,
            patch("app.models.assets.asset_factory") as mock_factory,
        ):
            # Setup mock returns for different calls
            def get_instruments_side_effect(underlying, expiration, option_type):
                if option_type == "call":
                    return mock_call_instruments
                elif option_type == "put":
                    return mock_put_instruments
                return []

            def find_options_side_effect(underlying, expiration, strike, option_type):
                if option_type.lower() == "call":
                    return mock_option_data_call
                elif option_type.lower() == "put":
                    return mock_option_data_put
                return []

            def get_market_data_side_effect(option_id):
                if option_id == "call-123":
                    return mock_call_market_data
                elif option_id == "put-123":
                    return mock_put_market_data
                return {}

            mock_get_instruments.side_effect = get_instruments_side_effect
            mock_find_options.side_effect = find_options_side_effect
            mock_get_market_data.side_effect = get_market_data_side_effect

            # Mock asset factory to return different options for calls/puts
            call_option = Option(
                symbol="AAPL240119C00150000",
                underlying=Stock(symbol="AAPL", name="Apple Inc."),
                option_type="CALL",
                strike=150.0,
                expiration_date=date(2024, 1, 19),
            )
            put_option = Option(
                symbol="AAPL240119P00150000",
                underlying=Stock(symbol="AAPL", name="Apple Inc."),
                option_type="PUT",
                strike=150.0,
                expiration_date=date(2024, 1, 19),
            )

            def factory_side_effect(symbol):
                if symbol == "AAPL":
                    return Stock(symbol="AAPL", name="Apple Inc.")
                return None

            mock_factory.side_effect = factory_side_effect

            # Mock _create_option_asset to return appropriate options
            def create_option_asset_side_effect(instrument, underlying, option_type):
                if option_type == "call":
                    return call_option
                elif option_type == "put":
                    return put_option
                return None

            adapter._create_option_asset = Mock(
                side_effect=create_option_asset_side_effect
            )

            # Mock _get_option_quote to return quotes
            async def get_option_quote_side_effect(option_asset):
                if option_asset.option_type == "CALL":
                    return OptionQuote(
                        asset=option_asset,
                        quote_date=datetime.now(),
                        price=5.5,
                        bid=5.25,
                        ask=5.75,
                    )
                elif option_asset.option_type == "PUT":
                    return OptionQuote(
                        asset=option_asset,
                        quote_date=datetime.now(),
                        price=3.4,
                        bid=3.15,
                        ask=3.65,
                    )
                return None

            adapter._get_option_quote = AsyncMock(
                side_effect=get_option_quote_side_effect
            )

            chain = await adapter.get_options_chain("AAPL")

        assert chain is not None
        assert isinstance(chain, OptionsChain)
        assert chain.underlying_symbol == "AAPL"
        assert chain.underlying_price == 150.0
        assert len(chain.calls) == 1
        assert len(chain.puts) == 1
        assert chain.calls[0].price == 5.5
        assert chain.puts[0].price == 3.4

    @pytest.mark.asyncio
    async def test_is_market_open(self, adapter):
        """Test market open check."""
        mock_market_hours = {"is_open": True}

        with patch(
            "robin_stocks.robinhood.markets.get_market_hours",
            return_value=mock_market_hours,
        ):
            is_open = await adapter.is_market_open()

        assert is_open is True

    @pytest.mark.asyncio
    async def test_is_market_open_closed(self, adapter):
        """Test market open check when closed."""
        mock_market_hours = {"is_open": False}

        with patch(
            "robin_stocks.robinhood.markets.get_market_hours",
            return_value=mock_market_hours,
        ):
            is_open = await adapter.is_market_open()

        assert is_open is False

    @pytest.mark.asyncio
    async def test_is_market_open_error(self, adapter):
        """Test market open check with error."""
        with patch(
            "robin_stocks.robinhood.markets.get_market_hours",
            side_effect=Exception("API Error"),
        ):
            is_open = await adapter.is_market_open()

        assert is_open is False

    @pytest.mark.asyncio
    async def test_get_market_hours(self, adapter):
        """Test getting market hours."""
        mock_hours = {
            "is_open": True,
            "next_open_hours": "09:30:00",
            "next_close_hours": "16:00:00",
        }

        with patch(
            "robin_stocks.robinhood.markets.get_market_hours", return_value=mock_hours
        ):
            hours = await adapter.get_market_hours()

        assert hours == mock_hours

    @pytest.mark.asyncio
    async def test_get_stock_info(self, adapter):
        """Test getting detailed stock information."""
        mock_fundamentals = [
            {
                "sector": "Technology",
                "industry": "Consumer Electronics",
                "description": "Apple Inc. designs and manufactures consumer electronics",
                "market_cap": "2500000000000",
                "pe_ratio": "28.5",
                "dividend_yield": "0.5",
            }
        ]
        mock_instruments = [{"simple_name": "Apple", "tradeable": True}]
        mock_name = "Apple Inc."

        with (
            patch(
                "robin_stocks.robinhood.stocks.get_fundamentals",
                return_value=mock_fundamentals,
            ),
            patch(
                "robin_stocks.robinhood.stocks.get_instruments_by_symbols",
                return_value=mock_instruments,
            ),
            patch(
                "robin_stocks.robinhood.stocks.get_name_by_symbol",
                return_value=mock_name,
            ),
        ):
            info = await adapter.get_stock_info("AAPL")

        assert info["symbol"] == "AAPL"
        assert info["company_name"] == "Apple Inc."
        assert info["sector"] == "Technology"
        assert info["industry"] == "Consumer Electronics"
        assert info["market_cap"] == "2500000000000"

    @pytest.mark.asyncio
    async def test_get_price_history(self, adapter):
        """Test getting price history."""
        mock_history = [
            {
                "begins_at": "2023-01-01T09:30:00Z",
                "open_price": "148.00",
                "high_price": "152.00",
                "low_price": "147.50",
                "close_price": "150.00",
                "volume": "1000000",
            },
            {
                "begins_at": "2023-01-01T10:30:00Z",
                "open_price": "150.00",
                "high_price": "155.00",
                "low_price": "149.50",
                "close_price": "153.00",
                "volume": "1500000",
            },
        ]

        with patch(
            "robin_stocks.robinhood.stocks.get_stock_historicals",
            return_value=mock_history,
        ):
            history = await adapter.get_price_history("AAPL", "day")

        assert history["symbol"] == "AAPL"
        assert history["period"] == "day"
        assert len(history["data_points"]) == 2
        assert history["data_points"][0]["open"] == 148.0
        assert history["data_points"][0]["close"] == 150.0
        assert history["data_points"][1]["close"] == 153.0

    def test_get_performance_metrics(self, adapter):
        """Test getting performance metrics."""
        # Simulate some activity
        adapter._request_count = 100
        adapter._error_count = 5
        adapter._total_request_time = 50.0
        adapter._cache_hits = 80
        adapter._cache_misses = 20
        adapter._last_api_response_time = 0.5
        adapter._last_error_time = datetime.now()
        adapter._last_error_message = "Test error"

        metrics = adapter.get_performance_metrics()

        assert metrics["adapter_name"] == "robinhood"
        assert metrics["request_count"] == 100
        assert metrics["error_count"] == 5
        assert metrics["error_rate"] == 0.05  # 5/100
        assert metrics["avg_response_time"] == 0.5  # 50/100
        assert metrics["cache_hit_rate"] == 0.8  # 80/(80+20)
        assert metrics["last_error_message"] == "Test error"

    def test_reset_metrics(self, adapter):
        """Test resetting performance metrics."""
        # Set some values
        adapter._request_count = 100
        adapter._error_count = 5
        adapter._total_request_time = 50.0
        adapter._cache_hits = 80
        adapter._cache_misses = 20
        adapter._last_api_response_time = 0.5
        adapter._last_error_time = datetime.now()
        adapter._last_error_message = "Test error"

        # Reset
        adapter.reset_metrics()

        # Verify reset
        assert adapter._request_count == 0
        assert adapter._error_count == 0
        assert adapter._total_request_time == 0.0
        assert adapter._cache_hits == 0
        assert adapter._cache_misses == 0
        assert adapter._last_api_response_time is None
        assert adapter._last_error_time is None
        assert adapter._last_error_message is None

    def test_unsupported_asset_type(self, adapter):
        """Test handling of unsupported asset types."""
        # Create a mock unsupported asset
        unsupported_asset = MagicMock()
        unsupported_asset.symbol = "UNKNOWN"
        type(unsupported_asset).__name__ = "UnsupportedAsset"

        # Should return None for unsupported types
        result = asyncio.run(adapter.get_quote(unsupported_asset))
        assert result is None

    def test_create_option_asset_success(self, adapter):
        """Test creating option asset from instrument data."""
        underlying = Stock(symbol="AAPL", name="Apple Inc.")
        instrument_data = {"strike_price": "150.00", "expiration_date": "2024-01-19"}

        option = adapter._create_option_asset(instrument_data, underlying, "call")

        assert option is not None
        assert isinstance(option, Option)
        assert option.underlying.symbol == "AAPL"
        assert option.strike == 150.0
        assert option.option_type == "CALL"
        assert option.expiration_date == date(2024, 1, 19)

    def test_create_option_asset_invalid_data(self, adapter):
        """Test creating option asset with invalid data."""
        underlying = Stock(symbol="AAPL", name="Apple Inc.")

        # Missing required fields
        invalid_data = {}

        option = adapter._create_option_asset(invalid_data, underlying, "call")
        assert option is None

    # Mock method implementations for no-op methods
    def test_get_sample_data_info(self, adapter):
        """Test sample data info (should return live data message)."""
        info = adapter.get_sample_data_info()
        assert "live data" in info["message"].lower()

    def test_get_expiration_dates(self, adapter):
        """Test getting expiration dates (not implemented)."""
        dates = adapter.get_expiration_dates("AAPL")
        assert dates == []

    def test_get_test_scenarios(self, adapter):
        """Test getting test scenarios (not applicable for live data)."""
        scenarios = adapter.get_test_scenarios()
        assert "live data" in scenarios["message"].lower()

    def test_set_date(self, adapter):
        """Test setting date (no-op for live data)."""
        # Should not raise exception
        adapter.set_date("2023-01-01")

    def test_get_available_symbols(self, adapter):
        """Test getting available symbols (not implemented)."""
        symbols = adapter.get_available_symbols()
        assert symbols == []
