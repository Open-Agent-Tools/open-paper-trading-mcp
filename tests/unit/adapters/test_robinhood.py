"""
Comprehensive tests for Robinhood adapter with mocked API calls.
"""

import asyncio
import time
from datetime import date, datetime
from unittest.mock import AsyncMock, Mock, patch

import pytest

from app.adapters.robinhood import RobinhoodAdapter, RobinhoodConfig, retry_with_backoff
from app.auth.session_manager import SessionManager
from app.models.assets import Option, Stock
from app.models.quotes import OptionQuote, Quote


class TestRobinhoodConfig:
    """Test suite for RobinhoodConfig."""

    def test_robinhood_config_defaults(self):
        """Test RobinhoodConfig default values."""
        config = RobinhoodConfig()

        assert config.name == "robinhood"
        assert config.priority == 1
        assert config.cache_ttl == 300.0
        assert config.enabled is True

    def test_robinhood_config_custom_values(self):
        """Test RobinhoodConfig with custom values."""
        config = RobinhoodConfig(
            name="custom_robinhood", priority=5, cache_ttl=600.0, enabled=False
        )

        assert config.name == "custom_robinhood"
        assert config.priority == 5
        assert config.cache_ttl == 600.0
        assert config.enabled is False


class TestRetryDecorator:
    """Test suite for retry_with_backoff decorator."""

    @pytest.mark.asyncio
    async def test_retry_success_first_attempt(self):
        """Test retry decorator with successful first attempt."""
        call_count = 0

        @retry_with_backoff(max_retries=3, base_delay=0.1)
        async def successful_function():
            nonlocal call_count
            call_count += 1
            return "success"

        result = await successful_function()
        assert result == "success"
        assert call_count == 1

    @pytest.mark.asyncio
    async def test_retry_success_after_failures(self):
        """Test retry decorator with success after failures."""
        call_count = 0

        @retry_with_backoff(max_retries=3, base_delay=0.1)
        async def eventually_successful_function():
            nonlocal call_count
            call_count += 1
            if call_count < 3:
                raise Exception("Temporary failure")
            return "success"

        result = await eventually_successful_function()
        assert result == "success"
        assert call_count == 3

    @pytest.mark.asyncio
    async def test_retry_max_retries_exceeded(self):
        """Test retry decorator when max retries exceeded."""
        call_count = 0

        @retry_with_backoff(max_retries=2, base_delay=0.1)
        async def always_failing_function():
            nonlocal call_count
            call_count += 1
            raise Exception("Always fails")

        with pytest.raises(Exception, match="Always fails"):
            await always_failing_function()

        assert call_count == 2

    @pytest.mark.asyncio
    async def test_retry_delay_calculation(self):
        """Test retry delay calculation."""
        call_times = []

        @retry_with_backoff(max_retries=3, base_delay=0.1, max_delay=1.0)
        async def delayed_function():
            call_times.append(time.time())
            if len(call_times) < 3:
                raise Exception("Retry needed")
            return "success"

        start_time = time.time()
        result = await delayed_function()
        total_time = time.time() - start_time

        assert result == "success"
        assert len(call_times) == 3
        # Should have some delay between calls
        assert total_time > 0.2  # At least 2 * 0.1 seconds


class TestRobinhoodAdapter:
    """Test suite for RobinhoodAdapter."""

    @pytest.fixture
    def config(self):
        """Create test configuration."""
        return RobinhoodConfig()

    @pytest.fixture
    def mock_session_manager(self):
        """Create mock session manager."""
        manager = Mock(spec=SessionManager)
        manager.ensure_authenticated = AsyncMock(return_value=True)
        manager.get_auth_metrics = Mock(
            return_value={
                "login_attempts": 1,
                "last_login": "2023-01-01T00:00:00",
                "session_duration": 3600,
            }
        )
        return manager

    @pytest.fixture
    def adapter(self, config, mock_session_manager):
        """Create RobinhoodAdapter with mocked dependencies."""
        with patch(
            "app.adapters.robinhood.get_session_manager",
            return_value=mock_session_manager,
        ):
            return RobinhoodAdapter(config)

    def test_adapter_initialization(self, adapter, config, mock_session_manager):
        """Test adapter initialization."""
        assert adapter.config is config
        assert adapter.session_manager is mock_session_manager
        assert adapter._request_count == 0
        assert adapter._error_count == 0
        assert adapter._total_request_time == 0.0

    @pytest.mark.asyncio
    async def test_ensure_authenticated_success(self, adapter, mock_session_manager):
        """Test successful authentication."""
        mock_session_manager.ensure_authenticated.return_value = True

        result = await adapter._ensure_authenticated()
        assert result is True
        mock_session_manager.ensure_authenticated.assert_called_once()

    @pytest.mark.asyncio
    async def test_ensure_authenticated_failure(self, adapter, mock_session_manager):
        """Test authentication failure."""
        mock_session_manager.ensure_authenticated.return_value = False

        result = await adapter._ensure_authenticated()
        assert result is False

    @pytest.mark.asyncio
    async def test_get_stock_quote_success(self, adapter):
        """Test successful stock quote retrieval."""
        stock = Stock(symbol="AAPL", name="Apple Inc.")

        # Mock Robinhood API responses
        with patch("app.adapters.robinhood.rh.stocks.get_latest_price") as mock_price:
            with patch(
                "app.adapters.robinhood.rh.stocks.get_fundamentals"
            ) as mock_fundamentals:
                mock_price.return_value = ["150.25"]
                mock_fundamentals.return_value = [{"volume": "1000000"}]

                quote = await adapter.get_quote(stock)

                assert quote is not None
                assert quote.asset is stock
                assert quote.price == 150.25
                assert quote.bid == 149.24  # price - 0.01
                assert quote.ask == 151.26  # price + 0.01
                assert quote.volume == 1000000

    @pytest.mark.asyncio
    async def test_get_stock_quote_no_data(self, adapter):
        """Test stock quote retrieval with no data."""
        stock = Stock(symbol="INVALID", name="Invalid Stock")

        with patch("app.adapters.robinhood.rh.stocks.get_latest_price") as mock_price:
            mock_price.return_value = [None]

            quote = await adapter.get_quote(stock)
            assert quote is None

    @pytest.mark.asyncio
    async def test_get_stock_quote_auth_failure(self, adapter, mock_session_manager):
        """Test stock quote retrieval with authentication failure."""
        stock = Stock(symbol="AAPL", name="Apple Inc.")
        mock_session_manager.ensure_authenticated.return_value = False

        quote = await adapter.get_quote(stock)
        assert quote is None
        assert adapter._error_count == 1

    @pytest.mark.asyncio
    async def test_get_stock_quote_api_error(self, adapter):
        """Test stock quote retrieval with API error."""
        stock = Stock(symbol="AAPL", name="Apple Inc.")

        with patch("app.adapters.robinhood.rh.stocks.get_latest_price") as mock_price:
            mock_price.side_effect = Exception("API Error")

            with pytest.raises(Exception, match="API Error"):
                await adapter.get_quote(stock)

            assert adapter._error_count == 1

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

        with (
            patch(
                "app.adapters.robinhood.rh.options.find_options_by_expiration_and_strike"
            ) as mock_find,
            patch(
                "app.adapters.robinhood.rh.options.get_option_market_data_by_id"
            ) as mock_market,
            patch.object(adapter, "_get_stock_quote") as mock_stock_quote,
        ):
            mock_find.return_value = [{"id": "option_id_123"}]
            mock_market.return_value = {
                "bid_price": "5.25",
                "ask_price": "5.75",
                "volume": "500",
                "open_interest": "1000",
            }

            stock_quote = Quote(
                asset=underlying,
                quote_date=datetime.now(),
                price=150.0,
                bid=149.50,
                ask=150.50,
                bid_size=100,
                ask_size=100,
                volume=1000000,
            )
            mock_stock_quote.return_value = stock_quote

            quote = await adapter.get_quote(option)

            assert quote is not None
            assert isinstance(quote, OptionQuote)
            assert quote.asset is option
            assert quote.bid == 5.25
            assert quote.ask == 5.75
            assert quote.price == 5.5  # (bid + ask) / 2
            assert quote.underlying_price == 150.0
            assert quote.volume == 500

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
            "app.adapters.robinhood.rh.options.find_options_by_expiration_and_strike"
        ) as mock_find:
            mock_find.return_value = []

            quote = await adapter.get_quote(option)
            assert quote is None

    @pytest.mark.asyncio
    async def test_get_quotes_multiple_assets(self, adapter):
        """Test getting quotes for multiple assets."""
        stock1 = Stock(symbol="AAPL", name="Apple Inc.")
        stock2 = Stock(symbol="GOOGL", name="Alphabet Inc.")
        assets = [stock1, stock2]

        with patch.object(adapter, "get_quote") as mock_get_quote:
            quote1 = Quote(
                asset=stock1,
                quote_date=datetime.now(),
                price=150.0,
                bid=149.50,
                ask=150.50,
                bid_size=100,
                ask_size=100,
                volume=1000000,
            )
            quote2 = Quote(
                asset=stock2,
                quote_date=datetime.now(),
                price=2500.0,
                bid=2495.0,
                ask=2505.0,
                bid_size=100,
                ask_size=100,
                volume=500000,
            )

            mock_get_quote.side_effect = [quote1, quote2]

            quotes = await adapter.get_quotes(assets)

            assert len(quotes) == 2
            assert quotes[stock1] is quote1
            assert quotes[stock2] is quote2

    @pytest.mark.asyncio
    async def test_get_chain_success(self, adapter):
        """Test successful option chain retrieval."""
        with patch("app.adapters.robinhood.rh.options.get_chains") as mock_chains:
            with patch(
                "app.adapters.robinhood.rh.options.get_option_instruments"
            ) as mock_instruments:
                with patch("app.models.assets.asset_factory") as mock_factory:
                    mock_chains.return_value = [{"expiration_date": "2024-01-19"}]
                    mock_instruments.return_value = [
                        {"url": "option_url_1"},
                        {"url": "option_url_2"},
                    ]

                    option1 = Option(
                        symbol="AAPL240119C00150000",
                        underlying=Stock(symbol="AAPL", name="Apple Inc."),
                        option_type="CALL",
                        strike=150.0,
                        expiration_date=date(2024, 1, 19),
                    )
                    option2 = Option(
                        symbol="AAPL240119P00150000",
                        underlying=Stock(symbol="AAPL", name="Apple Inc."),
                        option_type="PUT",
                        strike=150.0,
                        expiration_date=date(2024, 1, 19),
                    )

                    mock_factory.side_effect = [option1, option2]

                    assets = await adapter.get_chain("AAPL")

                    assert len(assets) == 2
                    assert option1 in assets
                    assert option2 in assets

    @pytest.mark.asyncio
    async def test_get_options_chain_success(self, adapter):
        """Test successful options chain with quotes."""
        expiration_date = datetime(2024, 1, 19)

        with patch("app.models.assets.asset_factory") as mock_factory:
            with patch.object(adapter, "_get_stock_quote") as mock_stock_quote:
                with patch(
                    "app.adapters.robinhood.rh.options.get_chains"
                ) as mock_chains:
                    with patch(
                        "app.adapters.robinhood.rh.options.get_option_instruments"
                    ) as mock_instruments:
                        with patch.object(
                            adapter, "_create_option_asset"
                        ) as mock_create_option:
                            with patch.object(
                                adapter, "_get_option_quote"
                            ) as mock_option_quote:
                                # Setup mocks
                                underlying = Stock(symbol="AAPL", name="Apple Inc.")
                                mock_factory.return_value = underlying

                                stock_quote = Quote(
                                    asset=underlying,
                                    quote_date=datetime.now(),
                                    price=150.0,
                                    bid=149.50,
                                    ask=150.50,
                                    bid_size=100,
                                    ask_size=100,
                                    volume=1000000,
                                )
                                mock_stock_quote.return_value = stock_quote

                                mock_chains.return_value = [
                                    {"expiration_date": "2024-01-19"}
                                ]
                                mock_instruments.side_effect = [
                                    [
                                        {
                                            "strike_price": "150.0",
                                            "expiration_date": "2024-01-19",
                                        }
                                    ],  # calls
                                    [
                                        {
                                            "strike_price": "150.0",
                                            "expiration_date": "2024-01-19",
                                        }
                                    ],  # puts
                                ]

                                call_option = Option(
                                    symbol="AAPL240119C00150000",
                                    underlying=underlying,
                                    option_type="CALL",
                                    strike=150.0,
                                    expiration_date=date(2024, 1, 19),
                                )
                                put_option = Option(
                                    symbol="AAPL240119P00150000",
                                    underlying=underlying,
                                    option_type="PUT",
                                    strike=150.0,
                                    expiration_date=date(2024, 1, 19),
                                )

                                mock_create_option.side_effect = [
                                    call_option,
                                    put_option,
                                ]

                                call_quote = OptionQuote(
                                    asset=call_option,
                                    quote_date=datetime.now(),
                                    price=5.5,
                                    bid=5.25,
                                    ask=5.75,
                                    underlying_price=150.0,
                                    volume=500,
                                )
                                put_quote = OptionQuote(
                                    asset=put_option,
                                    quote_date=datetime.now(),
                                    price=4.5,
                                    bid=4.25,
                                    ask=4.75,
                                    underlying_price=150.0,
                                    volume=300,
                                )

                                mock_option_quote.side_effect = [call_quote, put_quote]

                                chain = await adapter.get_options_chain(
                                    "AAPL", expiration_date
                                )

                                assert chain is not None
                                assert chain.underlying_symbol == "AAPL"
                                assert chain.underlying_price == 150.0
                                assert len(chain.calls) == 1
                                assert len(chain.puts) == 1
                                assert chain.calls[0] is call_quote
                                assert chain.puts[0] is put_quote

    @pytest.mark.asyncio
    async def test_is_market_open_success(self, adapter):
        """Test successful market open check."""
        with patch("app.adapters.robinhood.rh.markets.get_market_hours") as mock_hours:
            mock_hours.return_value = {"is_open": True}

            is_open = await adapter.is_market_open()
            assert is_open is True

    @pytest.mark.asyncio
    async def test_is_market_open_closed(self, adapter):
        """Test market closed check."""
        with patch("app.adapters.robinhood.rh.markets.get_market_hours") as mock_hours:
            mock_hours.return_value = {"is_open": False}

            is_open = await adapter.is_market_open()
            assert is_open is False

    @pytest.mark.asyncio
    async def test_is_market_open_error(self, adapter):
        """Test market open check with error."""
        with patch("app.adapters.robinhood.rh.markets.get_market_hours") as mock_hours:
            mock_hours.side_effect = Exception("API Error")

            is_open = await adapter.is_market_open()
            assert is_open is False

    @pytest.mark.asyncio
    async def test_get_market_hours_success(self, adapter):
        """Test successful market hours retrieval."""
        expected_hours = {
            "opens_at": "2024-01-01T14:30:00Z",
            "closes_at": "2024-01-01T21:00:00Z",
            "is_open": True,
        }

        with patch("app.adapters.robinhood.rh.markets.get_market_hours") as mock_hours:
            mock_hours.return_value = expected_hours

            hours = await adapter.get_market_hours()
            assert hours == expected_hours

    @pytest.mark.asyncio
    async def test_get_market_hours_error(self, adapter):
        """Test market hours retrieval with error."""
        with patch("app.adapters.robinhood.rh.markets.get_market_hours") as mock_hours:
            mock_hours.side_effect = Exception("API Error")

            hours = await adapter.get_market_hours()
            assert hours == {}

    @pytest.mark.asyncio
    async def test_get_stock_info_success(self, adapter):
        """Test successful stock info retrieval."""
        with (
            patch(
                "app.adapters.robinhood.rh.stocks.get_fundamentals"
            ) as mock_fundamentals,
            patch(
                "app.adapters.robinhood.rh.stocks.get_instruments_by_symbols"
            ) as mock_instruments,
            patch("app.adapters.robinhood.rh.stocks.get_name_by_symbol") as mock_name,
        ):
            mock_fundamentals.return_value = [
                {
                    "sector": "Technology",
                    "industry": "Consumer Electronics",
                    "market_cap": "3000000000000",
                    "pe_ratio": "25.5",
                    "dividend_yield": "0.5",
                }
            ]
            mock_instruments.return_value = [
                {"simple_name": "Apple", "tradeable": True}
            ]
            mock_name.return_value = "Apple Inc."

            info = await adapter.get_stock_info("AAPL")

            assert info["symbol"] == "AAPL"
            assert info["company_name"] == "Apple Inc."
            assert info["sector"] == "Technology"
            assert info["industry"] == "Consumer Electronics"
            assert info["tradeable"] is True

    @pytest.mark.asyncio
    async def test_get_price_history_success(self, adapter):
        """Test successful price history retrieval."""
        with patch(
            "app.adapters.robinhood.rh.stocks.get_stock_historicals"
        ) as mock_historicals:
            mock_historicals.return_value = [
                {
                    "begins_at": "2024-01-01T00:00:00Z",
                    "open_price": "150.0",
                    "high_price": "155.0",
                    "low_price": "148.0",
                    "close_price": "152.0",
                    "volume": "1000000",
                }
            ]

            history = await adapter.get_price_history("AAPL", "day")

            assert history["symbol"] == "AAPL"
            assert history["period"] == "day"
            assert len(history["data_points"]) == 1
            assert history["data_points"][0]["close"] == 152.0

    def test_create_option_asset_success(self, adapter):
        """Test successful option asset creation."""
        underlying = Stock(symbol="AAPL", name="Apple Inc.")
        instrument = {"strike_price": "150.0", "expiration_date": "2024-01-19"}

        option = adapter._create_option_asset(instrument, underlying, "call")

        assert option is not None
        assert option.underlying is underlying
        assert option.option_type == "CALL"
        assert option.strike == 150.0
        assert option.expiration_date == date(2024, 1, 19)
        assert "AAPL" in option.symbol
        assert "240119" in option.symbol  # Expiration date
        assert "C" in option.symbol  # Call option
        assert "00150000" in option.symbol  # Strike price

    def test_create_option_asset_invalid_data(self, adapter):
        """Test option asset creation with invalid data."""
        underlying = Stock(symbol="AAPL", name="Apple Inc.")
        instrument = {"strike_price": None, "expiration_date": None}

        option = adapter._create_option_asset(instrument, underlying, "call")
        assert option is None

    def test_get_performance_metrics(self, adapter):
        """Test performance metrics retrieval."""
        # Simulate some activity
        adapter._request_count = 10
        adapter._error_count = 2
        adapter._total_request_time = 5.0
        adapter._cache_hits = 8
        adapter._cache_misses = 2

        metrics = adapter.get_performance_metrics()

        assert metrics["adapter_name"] == "robinhood"
        assert metrics["request_count"] == 10
        assert metrics["error_count"] == 2
        assert metrics["error_rate"] == 0.2
        assert metrics["avg_response_time"] == 0.5
        assert metrics["cache_hit_rate"] == 0.8

    def test_reset_metrics(self, adapter):
        """Test metrics reset."""
        # Set some metrics
        adapter._request_count = 10
        adapter._error_count = 2
        adapter._total_request_time = 5.0

        adapter.reset_metrics()

        assert adapter._request_count == 0
        assert adapter._error_count == 0
        assert adapter._total_request_time == 0.0

    def test_get_sample_data_info(self, adapter):
        """Test sample data info for live adapter."""
        info = adapter.get_sample_data_info()

        assert "RobinhoodAdapter uses live data" in info["message"]

    def test_get_test_scenarios(self, adapter):
        """Test test scenarios for live adapter."""
        scenarios = adapter.get_test_scenarios()

        assert "RobinhoodAdapter uses live data" in scenarios["message"]

    def test_set_date_noop(self, adapter):
        """Test set_date does nothing for live adapter."""
        # Should not raise any exception
        adapter.set_date("2024-01-01")

    def test_get_available_symbols_empty(self, adapter):
        """Test get_available_symbols returns empty list."""
        symbols = adapter.get_available_symbols()
        assert symbols == []


class TestRobinhoodAdapterErrorHandling:
    """Test error handling and edge cases."""

    @pytest.fixture
    def adapter(self):
        """Create adapter with default config."""
        config = RobinhoodConfig()
        with patch("app.adapters.robinhood.get_session_manager"):
            return RobinhoodAdapter(config)

    @pytest.mark.asyncio
    async def test_unsupported_asset_type(self, adapter):
        """Test unsupported asset type."""
        # Create a mock asset that's neither Stock nor Option
        unsupported_asset = Mock()
        unsupported_asset.symbol = "UNSUPPORTED"

        quote = await adapter.get_quote(unsupported_asset)
        assert quote is None

    @pytest.mark.asyncio
    async def test_network_timeout_handling(self, adapter):
        """Test network timeout handling."""
        stock = Stock(symbol="AAPL", name="Apple Inc.")

        with patch("app.adapters.robinhood.rh.stocks.get_latest_price") as mock_price:
            mock_price.side_effect = TimeoutError("Network timeout")

            with pytest.raises(TimeoutError):
                await adapter.get_quote(stock)

    @pytest.mark.asyncio
    async def test_api_rate_limiting(self, adapter):
        """Test API rate limiting error."""
        stock = Stock(symbol="AAPL", name="Apple Inc.")

        with patch("app.adapters.robinhood.rh.stocks.get_latest_price") as mock_price:
            mock_price.side_effect = Exception("Rate limit exceeded")

            with pytest.raises(Exception, match="Rate limit exceeded"):
                await adapter.get_quote(stock)

    @pytest.mark.asyncio
    async def test_malformed_api_response(self, adapter):
        """Test handling of malformed API responses."""
        stock = Stock(symbol="AAPL", name="Apple Inc.")

        with patch("app.adapters.robinhood.rh.stocks.get_latest_price") as mock_price:
            # Return malformed data
            mock_price.return_value = ["not_a_number"]

            with pytest.raises(ValueError):
                await adapter.get_quote(stock)

    def test_invalid_option_symbol_format(self, adapter):
        """Test invalid option symbol format handling."""
        underlying = Stock(symbol="AAPL", name="Apple Inc.")
        instrument = {"strike_price": "invalid", "expiration_date": "invalid_date"}

        option = adapter._create_option_asset(instrument, underlying, "call")
        assert option is None


class TestRobinhoodAdapterIntegration:
    """Integration tests for RobinhoodAdapter."""

    @pytest.fixture
    def adapter(self):
        """Create adapter for integration tests."""
        config = RobinhoodConfig()
        with patch("app.adapters.robinhood.get_session_manager"):
            return RobinhoodAdapter(config)

    @pytest.mark.asyncio
    async def test_full_quote_workflow(self, adapter):
        """Test complete quote retrieval workflow."""
        stock = Stock(symbol="AAPL", name="Apple Inc.")

        # Mock all required API calls
        with patch("app.adapters.robinhood.rh.stocks.get_latest_price") as mock_price:
            with patch(
                "app.adapters.robinhood.rh.stocks.get_fundamentals"
            ) as mock_fundamentals:
                mock_price.return_value = ["150.25"]
                mock_fundamentals.return_value = [{"volume": "1000000"}]

                # Test the full workflow
                quote = await adapter.get_quote(stock)

                # Verify metrics were updated
                assert adapter._request_count == 1
                assert adapter._total_request_time > 0
                assert adapter._last_api_response_time is not None

                # Verify quote data
                assert quote is not None
                assert quote.price == 150.25
                assert quote.volume == 1000000

    @pytest.mark.asyncio
    async def test_multiple_concurrent_requests(self, adapter):
        """Test handling multiple concurrent requests."""
        stocks = [
            Stock(symbol="AAPL", name="Apple Inc."),
            Stock(symbol="GOOGL", name="Alphabet Inc."),
            Stock(symbol="MSFT", name="Microsoft Corp."),
        ]

        with patch("app.adapters.robinhood.rh.stocks.get_latest_price") as mock_price:
            with patch(
                "app.adapters.robinhood.rh.stocks.get_fundamentals"
            ) as mock_fundamentals:
                mock_price.side_effect = [["150.0"], ["2500.0"], ["300.0"]]
                mock_fundamentals.side_effect = [
                    [{"volume": "1000000"}],
                    [{"volume": "500000"}],
                    [{"volume": "2000000"}],
                ]

                # Execute concurrent requests
                tasks = [adapter.get_quote(stock) for stock in stocks]
                quotes = await asyncio.gather(*tasks)

                # Verify all quotes retrieved
                assert len(quotes) == 3
                assert all(quote is not None for quote in quotes)
                assert adapter._request_count == 3

    @pytest.mark.asyncio
    async def test_retry_mechanism_integration(self, adapter):
        """Test retry mechanism with actual failures."""
        stock = Stock(symbol="AAPL", name="Apple Inc.")

        call_count = 0

        def side_effect(*args, **kwargs):
            nonlocal call_count
            call_count += 1
            if call_count < 3:
                raise Exception("Temporary failure")
            return ["150.0"]

        with patch("app.adapters.robinhood.rh.stocks.get_latest_price") as mock_price:
            with patch(
                "app.adapters.robinhood.rh.stocks.get_fundamentals"
            ) as mock_fundamentals:
                mock_price.side_effect = side_effect
                mock_fundamentals.return_value = [{"volume": "1000000"}]

                quote = await adapter.get_quote(stock)

                # Should succeed after retries
                assert quote is not None
                assert call_count == 3
                # Should have recorded errors from failed attempts
                assert adapter._error_count > 0


class TestRobinhoodAdapterPerformance:
    """Performance tests for RobinhoodAdapter."""

    @pytest.fixture
    def adapter(self):
        """Create adapter for performance tests."""
        config = RobinhoodConfig()
        with patch("app.adapters.robinhood.get_session_manager"):
            return RobinhoodAdapter(config)

    @pytest.mark.asyncio
    async def test_quote_retrieval_performance(self, adapter):
        """Test quote retrieval performance."""
        stock = Stock(symbol="AAPL", name="Apple Inc.")

        with patch("app.adapters.robinhood.rh.stocks.get_latest_price") as mock_price:
            with patch(
                "app.adapters.robinhood.rh.stocks.get_fundamentals"
            ) as mock_fundamentals:
                mock_price.return_value = ["150.0"]
                mock_fundamentals.return_value = [{"volume": "1000000"}]

                # Measure performance
                start_time = time.time()

                # Make multiple requests
                for _ in range(10):
                    await adapter.get_quote(stock)

                end_time = time.time()
                total_time = end_time - start_time

                # Should complete in reasonable time (less than 1 second for mocked calls)
                assert total_time < 1.0

                # Verify metrics
                assert adapter._request_count == 10
                assert adapter._total_request_time > 0

    def test_memory_usage_with_many_quotes(self, adapter):
        """Test memory usage doesn't grow excessively."""
        import sys

        initial_size = sys.getsizeof(adapter)

        # Simulate processing many quotes
        for _i in range(1000):
            adapter._request_count += 1
            adapter._total_request_time += 0.1

        final_size = sys.getsizeof(adapter)

        # Memory usage should not grow significantly
        assert final_size - initial_size < 1000  # Less than 1KB growth
