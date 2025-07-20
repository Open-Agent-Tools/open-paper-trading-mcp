"""
Unit tests for RobinhoodAdapter.

Tests cover quote retrieval, error handling, authentication logic,
and retry mechanisms as required by QA feedback.
"""

from datetime import date, datetime
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.adapters.robinhood import RobinhoodAdapter, RobinhoodConfig
from app.models.assets import Option, Stock
from app.models.quotes import OptionQuote, OptionsChain, Quote


class TestRobinhoodAdapter:
    """Test suite for RobinhoodAdapter."""

    @pytest.fixture
    def mock_session_manager(self):
        """Mock session manager for testing."""
        mock_manager = AsyncMock()
        mock_manager.ensure_authenticated.return_value = True
        mock_manager.get_auth_token.return_value = "test_token"
        return mock_manager

    @pytest.fixture
    def adapter(self, mock_session_manager):
        """Create RobinhoodAdapter instance for testing."""
        with patch(
            "app.adapters.robinhood.get_session_manager",
            return_value=mock_session_manager,
        ):
            return RobinhoodAdapter()

    @pytest.fixture
    def sample_stock_asset(self):
        """Create sample stock asset for testing."""
        return Stock(symbol="AAPL", name="Apple Inc.")

    @pytest.fixture
    def sample_option_asset(self):
        """Create sample option asset for testing."""
        underlying = Stock(symbol="AAPL", name="Apple Inc.")
        return Option(
            symbol="AAPL240119C00150000",
            underlying=underlying,
            option_type="CALL",
            strike=150.0,
            expiration_date=date(2024, 1, 19),
        )

    @pytest.mark.asyncio
    async def test_get_quote_success_stock(self, adapter, sample_stock_asset):
        """Test successful stock quote retrieval."""
        # Mock robin_stocks responses
        with (
            patch("app.adapters.robinhood.rh.stocks.get_latest_price") as mock_price,
            patch(
                "app.adapters.robinhood.rh.stocks.get_fundamentals"
            ) as mock_fundamentals,
        ):
            mock_price.return_value = ["150.25"]
            mock_fundamentals.return_value = [{"volume": "1000000"}]

            quote = await adapter.get_quote(sample_stock_asset)

            assert quote is not None
            assert isinstance(quote, Quote)
            assert quote.asset == sample_stock_asset
            assert quote.price == 150.25
            assert quote.bid == 149.24  # price - 0.01
            assert quote.ask == 151.26  # price + 0.01
            assert quote.volume == 1000000
            assert isinstance(quote.quote_date, datetime)

    @pytest.mark.asyncio
    async def test_get_quote_success_option(self, adapter, sample_option_asset):
        """Test successful option quote retrieval."""
        # Mock robin_stocks responses
        with (
            patch(
                "app.adapters.robinhood.rh.options.find_options_by_expiration_and_strike"
            ) as mock_find,
            patch(
                "app.adapters.robinhood.rh.options.get_option_market_data_by_id"
            ) as mock_market_data,
            patch.object(adapter, "_get_stock_quote") as mock_stock_quote,
        ):
            mock_find.return_value = [{"id": "test_option_id"}]
            mock_market_data.return_value = {
                "bid_price": "5.50",
                "ask_price": "5.75",
                "volume": "100",
                "open_interest": "1000",
            }

            # Mock underlying stock quote
            underlying_quote = Quote(
                asset=sample_option_asset.underlying,
                quote_date=datetime.now(),
                price=150.0,
                bid=149.50,
                ask=150.50,
                volume=1000000,
            )
            mock_stock_quote.return_value = underlying_quote

            quote = await adapter.get_quote(sample_option_asset)

            assert quote is not None
            assert isinstance(quote, OptionQuote)
            assert quote.asset == sample_option_asset
            assert quote.bid == 5.50
            assert quote.ask == 5.75
            assert quote.price == 5.625  # (bid + ask) / 2
            assert quote.underlying_price == 150.0
            assert quote.volume == 100
            assert quote.open_interest == 1000

    @pytest.mark.asyncio
    async def test_get_quote_authentication_failure(self, adapter, sample_stock_asset):
        """Test quote retrieval with authentication failure."""
        # Mock authentication failure
        adapter.session_manager.ensure_authenticated.return_value = False

        quote = await adapter.get_quote(sample_stock_asset)

        assert quote is None

    @pytest.mark.asyncio
    async def test_get_quote_no_data_returned(self, adapter, sample_stock_asset):
        """Test quote retrieval when no data is returned from API."""
        with patch("app.adapters.robinhood.rh.stocks.get_latest_price") as mock_price:
            mock_price.return_value = []

            quote = await adapter.get_quote(sample_stock_asset)

            assert quote is None

    @pytest.mark.asyncio
    async def test_get_quote_invalid_price_data(self, adapter, sample_stock_asset):
        """Test quote retrieval with invalid price data."""
        with patch("app.adapters.robinhood.rh.stocks.get_latest_price") as mock_price:
            mock_price.return_value = [None]

            quote = await adapter.get_quote(sample_stock_asset)

            assert quote is None

    @pytest.mark.asyncio
    async def test_get_quote_fundamentals_failure(self, adapter, sample_stock_asset):
        """Test quote retrieval when fundamentals call fails."""
        with (
            patch("app.adapters.robinhood.rh.stocks.get_latest_price") as mock_price,
            patch(
                "app.adapters.robinhood.rh.stocks.get_fundamentals"
            ) as mock_fundamentals,
        ):
            mock_price.return_value = ["150.25"]
            mock_fundamentals.return_value = []  # No fundamentals data

            quote = await adapter.get_quote(sample_stock_asset)

            assert quote is not None
            assert quote.price == 150.25
            assert quote.volume is None  # Volume should be None when fundamentals fail

    @pytest.mark.asyncio
    async def test_get_quote_retry_on_exception(self, adapter, sample_stock_asset):
        """Test retry logic when API call raises exception."""
        with patch("app.adapters.robinhood.rh.stocks.get_latest_price") as mock_price:
            # First two calls fail, third succeeds
            mock_price.side_effect = [
                Exception("API Error"),
                Exception("Another API Error"),
                ["150.25"],
            ]

            with patch(
                "app.adapters.robinhood.rh.stocks.get_fundamentals"
            ) as mock_fundamentals:
                mock_fundamentals.return_value = [{"volume": "1000000"}]

                quote = await adapter.get_quote(sample_stock_asset)

                assert quote is not None
                assert quote.price == 150.25
                assert mock_price.call_count == 3  # Should retry 3 times total

    @pytest.mark.asyncio
    async def test_get_quote_retry_exhausted(self, adapter, sample_stock_asset):
        """Test retry logic when all retries are exhausted."""
        with patch("app.adapters.robinhood.rh.stocks.get_latest_price") as mock_price:
            # All calls fail
            mock_price.side_effect = Exception("Persistent API Error")

            with pytest.raises(Exception, match="Persistent API Error"):
                await adapter.get_quote(sample_stock_asset)

            assert mock_price.call_count == 3  # Should retry 3 times total

    @pytest.mark.asyncio
    async def test_get_quotes_multiple_assets(self, adapter):
        """Test retrieving quotes for multiple assets."""
        assets = [
            Stock(symbol="AAPL", name="Apple Inc."),
            Stock(symbol="GOOGL", name="Google Inc."),
        ]

        with patch.object(adapter, "get_quote") as mock_get_quote:
            # Mock successful quotes for both assets
            mock_get_quote.side_effect = [
                Quote(
                    asset=assets[0],
                    quote_date=datetime.now(),
                    price=150.25,
                    bid=149.24,
                    ask=151.26,
                    volume=1000000,
                ),
                Quote(
                    asset=assets[1],
                    quote_date=datetime.now(),
                    price=2800.50,
                    bid=2799.50,
                    ask=2801.50,
                    volume=500000,
                ),
            ]

            quotes = await adapter.get_quotes(assets)

            assert len(quotes) == 2
            assert assets[0] in quotes
            assert assets[1] in quotes
            assert quotes[assets[0]].price == 150.25
            assert quotes[assets[1]].price == 2800.50

    @pytest.mark.asyncio
    async def test_get_quotes_partial_failure(self, adapter):
        """Test retrieving quotes when some assets fail."""
        assets = [
            Stock(symbol="AAPL", name="Apple Inc."),
            Stock(symbol="INVALID", name="Invalid Stock"),
        ]

        with patch.object(adapter, "get_quote") as mock_get_quote:
            # First succeeds, second fails
            mock_get_quote.side_effect = [
                Quote(
                    asset=assets[0],
                    quote_date=datetime.now(),
                    price=150.25,
                    bid=149.24,
                    ask=151.26,
                    volume=1000000,
                ),
                None,  # Failed quote
            ]

            quotes = await adapter.get_quotes(assets)

            assert len(quotes) == 1
            assert assets[0] in quotes
            assert assets[1] not in quotes

    @pytest.mark.asyncio
    async def test_get_chain_success(self, adapter):
        """Test successful option chain retrieval."""
        with (
            patch("app.adapters.robinhood.rh.options.get_chains") as mock_chains,
            patch(
                "app.adapters.robinhood.rh.options.get_option_instruments"
            ) as mock_instruments,
            patch("app.adapters.robinhood.asset_factory") as mock_factory,
        ):
            mock_chains.return_value = [{"expiration_date": "2024-01-19"}]
            mock_instruments.return_value = [
                {"url": "https://robinhood.com/instruments/abc123/"}
            ]
            mock_factory.return_value = Stock(symbol="AAPL", name="Apple Inc.")

            assets = await adapter.get_chain("AAPL")

            assert len(assets) == 1
            assert isinstance(assets[0], Stock)

    @pytest.mark.asyncio
    async def test_get_chain_authentication_failure(self, adapter):
        """Test option chain retrieval with authentication failure."""
        adapter.session_manager.ensure_authenticated.return_value = False

        assets = await adapter.get_chain("AAPL")

        assert assets == []

    @pytest.mark.asyncio
    async def test_get_chain_no_data(self, adapter):
        """Test option chain retrieval when no data is returned."""
        with patch("app.adapters.robinhood.rh.options.get_chains") as mock_chains:
            mock_chains.return_value = []

            assets = await adapter.get_chain("AAPL")

            assert assets == []

    @pytest.mark.asyncio
    async def test_get_options_chain_success(self, adapter):
        """Test successful options chain with quotes retrieval."""
        with (
            patch("app.adapters.robinhood.rh.options.get_chains") as mock_chains,
            patch(
                "app.adapters.robinhood.rh.options.get_option_instruments"
            ) as mock_instruments,
            patch("app.adapters.robinhood.asset_factory") as mock_factory,
            patch.object(adapter, "_get_stock_quote") as mock_stock_quote,
            patch.object(adapter, "_get_option_quote") as mock_option_quote,
            patch.object(adapter, "_create_option_asset") as mock_create_option,
        ):
            mock_chains.return_value = [{"expiration_date": "2024-01-19"}]
            mock_instruments.side_effect = [
                [{"id": "call_1"}],  # Calls
                [{"id": "put_1"}],  # Puts
            ]

            underlying_stock = Stock(symbol="AAPL", name="Apple Inc.")
            mock_factory.return_value = underlying_stock

            mock_stock_quote.return_value = Quote(
                asset=underlying_stock,
                quote_date=datetime.now(),
                price=150.0,
                bid=149.50,
                ask=150.50,
                volume=1000000,
            )

            call_option = Option(
                symbol="AAPL240119C00150000",
                underlying=underlying_stock,
                option_type="CALL",
                strike=150.0,
                expiration_date=date(2024, 1, 19),
            )
            put_option = Option(
                symbol="AAPL240119P00150000",
                underlying=underlying_stock,
                option_type="PUT",
                strike=150.0,
                expiration_date=date(2024, 1, 19),
            )

            mock_create_option.side_effect = [call_option, put_option]

            mock_option_quote.side_effect = [
                OptionQuote(
                    asset=call_option,
                    quote_date=datetime.now(),
                    price=5.625,
                    bid=5.50,
                    ask=5.75,
                    underlying_price=150.0,
                    volume=100,
                ),
                OptionQuote(
                    asset=put_option,
                    quote_date=datetime.now(),
                    price=3.125,
                    bid=3.00,
                    ask=3.25,
                    underlying_price=150.0,
                    volume=50,
                ),
            ]

            options_chain = await adapter.get_options_chain("AAPL")

            assert options_chain is not None
            assert isinstance(options_chain, OptionsChain)
            assert options_chain.underlying_symbol == "AAPL"
            assert options_chain.underlying_price == 150.0
            assert len(options_chain.calls) == 1
            assert len(options_chain.puts) == 1
            assert options_chain.calls[0].price == 5.625
            assert options_chain.puts[0].price == 3.125

    @pytest.mark.asyncio
    async def test_get_options_chain_authentication_failure(self, adapter):
        """Test options chain retrieval with authentication failure."""
        adapter.session_manager.ensure_authenticated.return_value = False

        options_chain = await adapter.get_options_chain("AAPL")

        assert options_chain is None

    @pytest.mark.asyncio
    async def test_is_market_open_success(self, adapter):
        """Test market open status check."""
        with patch("app.adapters.robinhood.rh.markets.get_market_hours") as mock_hours:
            mock_hours.return_value = {"is_open": True}

            is_open = await adapter.is_market_open()

            assert is_open is True

    @pytest.mark.asyncio
    async def test_is_market_open_closed(self, adapter):
        """Test market open status when market is closed."""
        with patch("app.adapters.robinhood.rh.markets.get_market_hours") as mock_hours:
            mock_hours.return_value = {"is_open": False}

            is_open = await adapter.is_market_open()

            assert is_open is False

    @pytest.mark.asyncio
    async def test_is_market_open_authentication_failure(self, adapter):
        """Test market open status with authentication failure."""
        adapter.session_manager.ensure_authenticated.return_value = False

        is_open = await adapter.is_market_open()

        assert is_open is False

    @pytest.mark.asyncio
    async def test_get_market_hours_success(self, adapter):
        """Test market hours retrieval."""
        expected_hours = {
            "is_open": True,
            "opens_at": "2024-01-19T14:30:00Z",
            "closes_at": "2024-01-19T21:00:00Z",
        }

        with patch("app.adapters.robinhood.rh.markets.get_market_hours") as mock_hours:
            mock_hours.return_value = expected_hours

            hours = await adapter.get_market_hours()

            assert hours == expected_hours

    @pytest.mark.asyncio
    async def test_get_market_hours_authentication_failure(self, adapter):
        """Test market hours retrieval with authentication failure."""
        adapter.session_manager.ensure_authenticated.return_value = False

        hours = await adapter.get_market_hours()

        assert hours == {}

    def test_robinhood_config_defaults(self):
        """Test RobinhoodConfig default values."""
        config = RobinhoodConfig()

        assert config.name == "robinhood"
        assert config.priority == 1
        assert config.cache_ttl == 300.0

    def test_robinhood_config_custom_values(self):
        """Test RobinhoodConfig with custom values."""
        config = RobinhoodConfig(name="custom_robinhood", priority=5, cache_ttl=600.0)

        assert config.name == "custom_robinhood"
        assert config.priority == 5
        assert config.cache_ttl == 600.0

    @pytest.mark.asyncio
    async def test_unsupported_asset_type(self, adapter):
        """Test quote retrieval with unsupported asset type."""
        # Create a mock asset that's neither Stock nor Option
        unsupported_asset = MagicMock()
        unsupported_asset.__class__ = type("UnsupportedAsset", (), {})

        quote = await adapter.get_quote(unsupported_asset)

        assert quote is None

    @pytest.mark.asyncio
    async def test_error_logging_on_failure(self, adapter, sample_stock_asset):
        """Test that errors are properly logged."""
        with (
            patch("app.adapters.robinhood.rh.stocks.get_latest_price") as mock_price,
            patch("app.adapters.robinhood.logger") as mock_logger,
        ):
            mock_price.side_effect = Exception("Test error")

            with pytest.raises(Exception):
                await adapter.get_quote(sample_stock_asset)

            # Verify error was logged
            mock_logger.error.assert_called()
            assert "Test error" in str(mock_logger.error.call_args)
