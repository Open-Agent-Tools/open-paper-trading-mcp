"""Tests for DevDataQuoteAdapter (test data adapter)."""

from datetime import date, datetime, timedelta
from unittest.mock import MagicMock, Mock, patch

import pytest

from app.adapters.base import AdapterConfig
from app.adapters.test_data import (
    DevDataQuoteAdapter,
    TestDataError,
    get_test_adapter,
)
from app.models.assets import Option, Stock
from app.models.database.trading import DevOptionQuote, DevStockQuote
from app.models.quotes import OptionQuote, OptionsChain, Quote


class TestTestDataError:
    """Test TestDataError exception."""

    def test_test_data_error(self):
        """Test TestDataError exception creation."""
        error = TestDataError("Test error message")
        assert str(error) == "Test error message"
        assert isinstance(error, Exception)


class TestDevDataQuoteAdapter:
    """Test DevDataQuoteAdapter functionality."""

    @pytest.fixture
    def mock_db_session(self):
        """Mock database session."""
        mock_session = MagicMock()
        return mock_session

    @pytest.fixture
    def adapter(self, mock_db_session):
        """Create adapter with mocked database."""
        with patch("app.adapters.test_data.get_sync_session") as mock_get_session:
            mock_get_session.return_value.__enter__.return_value = mock_db_session
            mock_get_session.return_value.__exit__.return_value = None

            adapter = DevDataQuoteAdapter(current_date="2017-03-24", scenario="default")
        return adapter

    def test_adapter_initialization_default(self):
        """Test adapter initialization with defaults."""
        with patch("app.adapters.test_data.get_sync_session"):
            adapter = DevDataQuoteAdapter()

        assert adapter.name == "DevDataQuoteAdapter"
        assert adapter.enabled is True
        assert adapter.scenario == "default"
        assert adapter.current_date == date(2017, 3, 24)
        assert isinstance(adapter._quote_cache, dict)

    def test_adapter_initialization_custom(self):
        """Test adapter initialization with custom values."""
        config = AdapterConfig(name="custom-test", enabled=False, priority=50)

        with patch("app.adapters.test_data.get_sync_session"):
            adapter = DevDataQuoteAdapter(
                current_date="2017-01-27", scenario="earnings_volatility", config=config
            )

        assert adapter.name == "DevDataQuoteAdapter"
        assert adapter.scenario == "earnings_volatility"
        assert adapter.current_date == date(2017, 1, 27)
        assert adapter.config.name == "custom-test"
        assert adapter.config.enabled is False

    def test_set_date(self, adapter):
        """Test setting current date."""
        adapter.set_date("2017-01-27")

        assert adapter.current_date == date(2017, 1, 27)
        # Cache should be cleared
        adapter._quote_cache["test"] = "value"
        adapter.set_date("2017-01-28")
        assert "test" not in adapter._quote_cache

    def test_set_date_invalid_format(self, adapter):
        """Test setting invalid date format."""
        with pytest.raises(ValueError):
            adapter.set_date("invalid-date")

    @pytest.mark.asyncio
    async def test_switch_scenario(self, adapter, mock_db_session):
        """Test switching scenarios."""
        # Mock scenario query
        mock_scenario = Mock()
        mock_scenario.name = "earnings_volatility"
        mock_scenario.start_date = date(2017, 1, 27)

        mock_query = Mock()
        mock_query.filter.return_value.first.return_value = mock_scenario
        mock_db_session.query.return_value = mock_query

        await adapter.switch_scenario("earnings_volatility")

        assert adapter.scenario == "earnings_volatility"
        assert adapter.current_date == date(2017, 1, 27)

    @pytest.mark.asyncio
    async def test_switch_scenario_not_found(self, adapter, mock_db_session):
        """Test switching to non-existent scenario."""
        mock_query = Mock()
        mock_query.filter.return_value.first.return_value = None
        mock_db_session.query.return_value = mock_query

        # Should not change current scenario
        original_scenario = adapter.scenario
        await adapter.switch_scenario("nonexistent")

        assert adapter.scenario == original_scenario

    def test_get_available_dates(self, adapter, mock_db_session):
        """Test getting available dates."""
        # Mock date query results
        mock_dates = [
            (datetime(2017, 3, 24).date(),),
            (datetime(2017, 3, 25).date(),),
        ]

        mock_query = Mock()
        mock_query.filter.return_value.distinct.return_value.all.return_value = (
            mock_dates
        )
        mock_db_session.query.return_value = mock_query

        dates = adapter.get_available_dates()

        assert dates == ["2017-03-24", "2017-03-25"]
        mock_db_session.query.assert_called_with(DevStockQuote.quote_date)

    @pytest.mark.asyncio
    async def test_advance_date(self, adapter):
        """Test advancing current date."""
        original_date = adapter.current_date

        await adapter.advance_date(1)

        assert adapter.current_date == original_date + timedelta(days=1)

        # Test advancing multiple days
        await adapter.advance_date(5)
        assert adapter.current_date == original_date + timedelta(days=6)

    def test_get_stock_quote_from_db(self, adapter, mock_db_session):
        """Test getting stock quote from database."""
        # Mock database quote
        mock_quote = Mock(spec=DevStockQuote)
        mock_quote.symbol = "AAPL"
        mock_quote.bid = 150.25
        mock_quote.ask = 150.75
        mock_quote.price = 150.50
        mock_quote.volume = 1000000
        mock_quote.quote_date = date(2017, 3, 24)

        mock_query = Mock()
        mock_query.filter.return_value.first.return_value = mock_quote
        mock_db_session.query.return_value = mock_query

        result = adapter._get_stock_quote_from_db("AAPL", date(2017, 3, 24), "default")

        assert result == mock_quote
        mock_db_session.query.assert_called_with(DevStockQuote)

    def test_get_stock_quote_from_db_not_found(self, adapter, mock_db_session):
        """Test getting non-existent stock quote from database."""
        mock_query = Mock()
        mock_query.filter.return_value.first.return_value = None
        mock_db_session.query.return_value = mock_query

        result = adapter._get_stock_quote_from_db(
            "NONEXISTENT", date(2017, 3, 24), "default"
        )

        assert result is None

    def test_get_option_quote_from_db(self, adapter, mock_db_session):
        """Test getting option quote from database."""
        # Mock database option quote
        mock_quote = Mock(spec=DevOptionQuote)
        mock_quote.symbol = "AAPL170324C00150000"
        mock_quote.bid = 5.25
        mock_quote.ask = 5.75
        mock_quote.price = 5.50
        mock_quote.volume = 1000
        mock_quote.quote_date = date(2017, 3, 24)

        mock_query = Mock()
        mock_query.filter.return_value.first.return_value = mock_quote
        mock_db_session.query.return_value = mock_query

        result = adapter._get_option_quote_from_db(
            "AAPL170324C00150000", date(2017, 3, 24), "default"
        )

        assert result == mock_quote
        mock_db_session.query.assert_called_with(DevOptionQuote)

    def test_cached_stock_quote_success(self, adapter, mock_db_session):
        """Test cached stock quote creation."""
        # Mock database quote
        mock_db_quote = Mock(spec=DevStockQuote)
        mock_db_quote.symbol = "AAPL"
        mock_db_quote.bid = 150.25
        mock_db_quote.ask = 150.75
        mock_db_quote.price = 150.50
        mock_db_quote.volume = 1000000
        mock_db_quote.quote_date = date(2017, 3, 24)

        # Mock asset factory
        mock_stock = Stock(symbol="AAPL", name="Apple Inc.")

        with (
            patch.object(
                adapter, "_get_stock_quote_from_db", return_value=mock_db_quote
            ),
            patch("app.models.assets.asset_factory", return_value=mock_stock),
        ):
            quote = adapter._cached_stock_quote("AAPL", date(2017, 3, 24), "default")

        assert quote is not None
        assert isinstance(quote, Quote)
        assert quote.asset.symbol == "AAPL"
        assert quote.price == 150.50
        assert quote.bid == 150.25
        assert quote.ask == 150.75
        assert quote.volume == 1000000

    def test_cached_stock_quote_no_data(self, adapter):
        """Test cached stock quote with no database data."""
        with patch.object(adapter, "_get_stock_quote_from_db", return_value=None):
            quote = adapter._cached_stock_quote(
                "NONEXISTENT", date(2017, 3, 24), "default"
            )

        assert quote is None

    def test_cached_stock_quote_no_asset(self, adapter, mock_db_session):
        """Test cached stock quote with invalid asset."""
        mock_db_quote = Mock(spec=DevStockQuote)

        with (
            patch.object(
                adapter, "_get_stock_quote_from_db", return_value=mock_db_quote
            ),
            patch("app.models.assets.asset_factory", return_value=None),
        ):
            quote = adapter._cached_stock_quote("INVALID", date(2017, 3, 24), "default")

        assert quote is None

    def test_cached_option_quote_success(self, adapter, mock_db_session):
        """Test cached option quote creation."""
        # Mock database option quote
        mock_db_quote = Mock(spec=DevOptionQuote)
        mock_db_quote.symbol = "AAPL170324C00150000"
        mock_db_quote.bid = 5.25
        mock_db_quote.ask = 5.75
        mock_db_quote.price = 5.50
        mock_db_quote.volume = 1000
        mock_db_quote.quote_date = date(2017, 3, 24)

        # Mock option asset
        underlying = Stock(symbol="AAPL", name="Apple Inc.")
        mock_option = Option(
            symbol="AAPL170324C00150000",
            underlying=underlying,
            option_type="CALL",
            strike=150.0,
            expiration_date=date(2017, 3, 24),
        )

        # Mock underlying quote for Greeks calculation
        mock_underlying_quote = Quote(
            asset=underlying,
            quote_date=datetime.now(),
            price=150.50,
            bid=150.25,
            ask=150.75,
            bid_size=100,
            ask_size=100,
            volume=1000000,
        )

        with (
            patch.object(
                adapter, "_get_option_quote_from_db", return_value=mock_db_quote
            ),
            patch("app.models.assets.asset_factory", return_value=mock_option),
            patch.object(
                adapter, "_cached_stock_quote", return_value=mock_underlying_quote
            ),
            patch(
                "app.services.greeks.calculate_option_greeks",
                return_value={
                    "delta": 0.65,
                    "gamma": 0.02,
                    "theta": -0.05,
                    "vega": 0.15,
                },
            ),
        ):
            quote = adapter._cached_option_quote(
                "AAPL170324C00150000", date(2017, 3, 24), "default"
            )

        assert quote is not None
        assert isinstance(quote, OptionQuote)
        assert quote.asset.symbol == "AAPL170324C00150000"
        assert quote.price == 5.50
        assert quote.bid == 5.25
        assert quote.ask == 5.75
        assert quote.volume == 1000
        # Greeks should be calculated and set
        assert hasattr(quote, "delta")

    def test_cached_option_quote_greeks_calculation_error(
        self, adapter, mock_db_session
    ):
        """Test cached option quote with Greeks calculation error."""
        # Mock database option quote
        mock_db_quote = Mock(spec=DevOptionQuote)
        mock_db_quote.symbol = "AAPL170324C00150000"
        mock_db_quote.bid = 5.25
        mock_db_quote.ask = 5.75
        mock_db_quote.price = 5.50
        mock_db_quote.volume = 1000
        mock_db_quote.quote_date = date(2017, 3, 24)

        # Mock option asset
        underlying = Stock(symbol="AAPL", name="Apple Inc.")
        mock_option = Option(
            symbol="AAPL170324C00150000",
            underlying=underlying,
            option_type="CALL",
            strike=150.0,
            expiration_date=date(2017, 3, 24),
        )

        # Mock underlying quote
        mock_underlying_quote = Quote(
            asset=underlying,
            quote_date=datetime.now(),
            price=150.50,
            bid=150.25,
            ask=150.75,
            bid_size=100,
            ask_size=100,
            volume=1000000,
        )

        with (
            patch.object(
                adapter, "_get_option_quote_from_db", return_value=mock_db_quote
            ),
            patch("app.models.assets.asset_factory", return_value=mock_option),
            patch.object(
                adapter, "_cached_stock_quote", return_value=mock_underlying_quote
            ),
            patch(
                "app.services.greeks.calculate_option_greeks",
                side_effect=Exception("Greeks error"),
            ),
        ):
            # Should still return quote even if Greeks calculation fails
            quote = adapter._cached_option_quote(
                "AAPL170324C00150000", date(2017, 3, 24), "default"
            )

        assert quote is not None
        assert isinstance(quote, OptionQuote)
        assert quote.price == 5.50

    @pytest.mark.asyncio
    async def test_get_quote_stock(self, adapter):
        """Test getting stock quote."""
        stock = Stock(symbol="AAPL", name="Apple Inc.")
        mock_quote = Quote(
            asset=stock,
            quote_date=datetime.now(),
            price=150.50,
            bid=150.25,
            ask=150.75,
            bid_size=100,
            ask_size=100,
            volume=1000000,
        )

        with patch.object(adapter, "_cached_stock_quote", return_value=mock_quote):
            quote = await adapter.get_quote(stock)

        assert quote == mock_quote

    @pytest.mark.asyncio
    async def test_get_quote_option(self, adapter):
        """Test getting option quote."""
        underlying = Stock(symbol="AAPL", name="Apple Inc.")
        option = Option(
            symbol="AAPL170324C00150000",
            underlying=underlying,
            option_type="CALL",
            strike=150.0,
            expiration_date=date(2017, 3, 24),
        )
        mock_quote = OptionQuote(
            asset=option,
            quote_date=datetime.now(),
            price=5.50,
            bid=5.25,
            ask=5.75,
            volume=1000,
        )

        with patch.object(adapter, "_cached_option_quote", return_value=mock_quote):
            quote = await adapter.get_quote(option)

        assert quote == mock_quote

    @pytest.mark.asyncio
    async def test_get_quote_not_found(self, adapter):
        """Test getting quote that doesn't exist."""
        stock = Stock(symbol="NONEXISTENT", name="Non-existent")

        with patch.object(adapter, "_cached_stock_quote", return_value=None):
            quote = await adapter.get_quote(stock)

        assert quote is None

    @pytest.mark.asyncio
    async def test_get_quotes_multiple(self, adapter):
        """Test getting multiple quotes."""
        stock1 = Stock(symbol="AAPL", name="Apple Inc.")
        stock2 = Stock(symbol="GOOGL", name="Alphabet Inc.")
        stock3 = Stock(symbol="NONEXISTENT", name="Non-existent")

        quote1 = Quote(
            asset=stock1,
            quote_date=datetime.now(),
            price=150.50,
            bid=150.25,
            ask=150.75,
            bid_size=100,
            ask_size=100,
            volume=1000000,
        )
        quote2 = Quote(
            asset=stock2,
            quote_date=datetime.now(),
            price=2500.00,
            bid=2499.50,
            ask=2500.50,
            bid_size=100,
            ask_size=100,
            volume=500000,
        )

        async def mock_get_quote(asset):
            if asset.symbol == "AAPL":
                return quote1
            elif asset.symbol == "GOOGL":
                return quote2
            return None

        with patch.object(adapter, "get_quote", side_effect=mock_get_quote):
            quotes = await adapter.get_quotes([stock1, stock2, stock3])

        assert len(quotes) == 2
        assert stock1 in quotes
        assert stock2 in quotes
        assert stock3 not in quotes

    @pytest.mark.asyncio
    async def test_batch_get_quotes(self, adapter, mock_db_session):
        """Test batch getting quotes efficiently."""
        # Mock stock records
        mock_stock_records = [
            Mock(symbol="AAPL", quote_date=date(2017, 3, 24)),
            Mock(symbol="GOOGL", quote_date=date(2017, 3, 24)),
        ]

        # Mock option records
        mock_option_records = [
            Mock(symbol="AAPL170324C00150000", quote_date=date(2017, 3, 24))
        ]

        # Mock quotes
        mock_stock_quote = Quote(
            asset=Stock(symbol="AAPL", name="Apple Inc."),
            quote_date=datetime.now(),
            price=150.50,
            bid=150.25,
            ask=150.75,
            bid_size=100,
            ask_size=100,
            volume=1000000,
        )

        mock_option_quote = OptionQuote(
            asset=Option(
                symbol="AAPL170324C00150000",
                underlying=Stock(symbol="AAPL", name="Apple Inc."),
                option_type="CALL",
                strike=150.0,
                expiration_date=date(2017, 3, 24),
            ),
            quote_date=datetime.now(),
            price=5.50,
            bid=5.25,
            ask=5.75,
            volume=1000,
        )

        # Mock database queries
        def mock_query_side_effect(model_class):
            mock_query = Mock()
            if model_class == DevStockQuote:
                mock_query.filter.return_value.all.return_value = mock_stock_records
            elif model_class == DevOptionQuote:
                mock_query.filter.return_value.all.return_value = mock_option_records
            return mock_query

        mock_db_session.query.side_effect = mock_query_side_effect

        # Mock asset factory
        def mock_asset_factory(symbol):
            if symbol == "AAPL":
                return Stock(symbol="AAPL", name="Apple Inc.")
            elif symbol == "GOOGL":
                return Stock(symbol="GOOGL", name="Alphabet Inc.")
            elif symbol == "AAPL170324C00150000":
                return Option(
                    symbol="AAPL170324C00150000",
                    underlying=Stock(symbol="AAPL", name="Apple Inc."),
                    option_type="CALL",
                    strike=150.0,
                    expiration_date=date(2017, 3, 24),
                )
            return None

        with (
            patch("app.models.assets.asset_factory", side_effect=mock_asset_factory),
            patch.object(adapter, "_cached_stock_quote", return_value=mock_stock_quote),
            patch.object(
                adapter, "_cached_option_quote", return_value=mock_option_quote
            ),
        ):
            results = await adapter.batch_get_quotes(
                ["AAPL", "GOOGL", "AAPL170324C00150000", "NONEXISTENT"]
            )

        assert len(results) == 4
        assert results["AAPL"] == mock_stock_quote
        assert results["GOOGL"] == mock_stock_quote  # Same mock returned
        assert results["AAPL170324C00150000"] == mock_option_quote
        assert results["NONEXISTENT"] is None

    @pytest.mark.asyncio
    async def test_get_quotes_for_date_range(self, adapter, mock_db_session):
        """Test getting quotes for a date range."""
        # Mock database records
        mock_records = [
            Mock(quote_date=date(2017, 3, 24)),
            Mock(quote_date=date(2017, 3, 25)),
        ]

        mock_quote = Quote(
            asset=Stock(symbol="AAPL", name="Apple Inc."),
            quote_date=datetime.now(),
            price=150.50,
            bid=150.25,
            ask=150.75,
            bid_size=100,
            ask_size=100,
            volume=1000000,
        )

        # Mock database query
        mock_query = Mock()
        mock_query.filter.return_value.order_by.return_value.all.return_value = (
            mock_records
        )
        mock_db_session.query.return_value = mock_query

        with (
            patch(
                "app.models.assets.asset_factory",
                return_value=Stock(symbol="AAPL", name="Apple Inc."),
            ),
            patch.object(adapter, "_cached_stock_quote", return_value=mock_quote),
        ):
            quotes = await adapter.get_quotes_for_date_range(
                "AAPL", date(2017, 3, 24), date(2017, 3, 25)
            )

        assert len(quotes) == 2
        assert all(isinstance(q, Quote) for q in quotes)

    @pytest.mark.asyncio
    async def test_get_chain(self, adapter):
        """Test getting option chain (basic implementation)."""
        assets = await adapter.get_chain("AAPL")
        assert assets == []

    @pytest.mark.asyncio
    async def test_get_options_chain(self, adapter, mock_db_session):
        """Test getting complete options chain."""
        # Mock underlying quote
        underlying_stock = Stock(symbol="AAPL", name="Apple Inc.")
        underlying_quote = Quote(
            asset=underlying_stock,
            quote_date=datetime.now(),
            price=150.50,
            bid=150.25,
            ask=150.75,
            bid_size=100,
            ask_size=100,
            volume=1000000,
        )

        # Mock option records
        mock_option_records = [
            Mock(
                symbol="AAPL170324C00150000",
                quote_date=date(2017, 3, 24),
                expiration=date(2017, 3, 24),
            ),
            Mock(
                symbol="AAPL170324P00150000",
                quote_date=date(2017, 3, 24),
                expiration=date(2017, 3, 24),
            ),
        ]

        # Mock option quotes
        call_option = Option(
            symbol="AAPL170324C00150000",
            underlying=underlying_stock,
            option_type="call",
            strike=150.0,
            expiration_date=date(2017, 3, 24),
        )
        put_option = Option(
            symbol="AAPL170324P00150000",
            underlying=underlying_stock,
            option_type="put",
            strike=150.0,
            expiration_date=date(2017, 3, 24),
        )

        call_quote = OptionQuote(
            asset=call_option, quote_date=datetime.now(), price=5.50, bid=5.25, ask=5.75
        )
        put_quote = OptionQuote(
            asset=put_option, quote_date=datetime.now(), price=3.25, bid=3.15, ask=3.35
        )

        # Mock database query
        mock_query = Mock()
        mock_query.all.return_value = mock_option_records
        mock_db_session.query.return_value.filter.return_value = mock_query

        def mock_cached_option_quote(symbol, quote_date, scenario):
            if "C00150000" in symbol:
                return call_quote
            elif "P00150000" in symbol:
                return put_quote
            return None

        with (
            patch("app.models.assets.asset_factory", return_value=underlying_stock),
            patch.object(adapter, "get_quote", return_value=underlying_quote),
            patch.object(
                adapter, "_cached_option_quote", side_effect=mock_cached_option_quote
            ),
        ):
            chain = await adapter.get_options_chain("AAPL")

        assert chain is not None
        assert isinstance(chain, OptionsChain)
        assert chain.underlying_symbol == "AAPL"
        assert chain.underlying_price == 150.50
        assert len(chain.calls) == 1
        assert len(chain.puts) == 1
        assert chain.calls[0].price == 5.50
        assert chain.puts[0].price == 3.25

    @pytest.mark.asyncio
    async def test_get_options_chain_no_data(self, adapter, mock_db_session):
        """Test getting options chain with no data."""
        mock_query = Mock()
        mock_query.all.return_value = []
        mock_db_session.query.return_value.filter.return_value = mock_query

        with patch(
            "app.models.assets.asset_factory",
            return_value=Stock(symbol="AAPL", name="Apple Inc."),
        ):
            chain = await adapter.get_options_chain("AAPL")

        assert chain is None

    def test_get_expiration_dates(self, adapter, mock_db_session):
        """Test getting expiration dates."""
        mock_expiration_dates = [
            (date(2017, 3, 24),),
            (date(2017, 4, 21),),
            (date(2017, 5, 19),),
        ]

        mock_query = Mock()
        mock_query.filter.return_value.distinct.return_value.all.return_value = (
            mock_expiration_dates
        )
        mock_db_session.query.return_value = mock_query

        dates = adapter.get_expiration_dates("AAPL")

        assert len(dates) == 3
        assert date(2017, 3, 24) in dates
        assert date(2017, 4, 21) in dates
        assert date(2017, 5, 19) in dates

    @pytest.mark.asyncio
    async def test_is_market_open(self, adapter):
        """Test market open check (always True for test data)."""
        is_open = await adapter.is_market_open()
        assert is_open is True

    @pytest.mark.asyncio
    async def test_get_market_hours(self, adapter):
        """Test getting market hours."""
        hours = await adapter.get_market_hours()

        assert "open" in hours
        assert "close" in hours
        assert hours["open"].hour == 9
        assert hours["open"].minute == 30
        assert hours["close"].hour == 16
        assert hours["close"].minute == 0

    def test_supports_symbol(self, adapter, mock_db_session):
        """Test checking if symbol is supported."""

        # Mock database queries
        def mock_query_side_effect(model_class):
            mock_query = Mock()
            if model_class == DevStockQuote:
                mock_first = Mock()
                mock_first.first.return_value = Mock()  # Symbol exists
                mock_query.filter.return_value = mock_first
            elif model_class == DevOptionQuote:
                mock_first = Mock()
                mock_first.first.return_value = None  # Option doesn't exist
                mock_query.filter.return_value = mock_first
            return mock_query

        mock_db_session.query.side_effect = mock_query_side_effect

        with patch(
            "app.models.assets.asset_factory",
            return_value=Stock(symbol="AAPL", name="Apple Inc."),
        ):
            supports = adapter.supports_symbol("AAPL")

        assert supports is True

    def test_supports_symbol_not_found(self, adapter, mock_db_session):
        """Test checking unsupported symbol."""
        # Mock database queries - no data found
        mock_query = Mock()
        mock_query.filter.return_value.first.return_value = None
        mock_db_session.query.return_value = mock_query

        with patch(
            "app.models.assets.asset_factory",
            return_value=Stock(symbol="NONEXISTENT", name="Non-existent"),
        ):
            supports = adapter.supports_symbol("NONEXISTENT")

        assert supports is False

    def test_supports_symbol_invalid_asset(self, adapter):
        """Test checking symbol with invalid asset."""
        with patch("app.models.assets.asset_factory", return_value=None):
            supports = adapter.supports_symbol("INVALID")

        assert supports is False

    def test_get_last_updated(self, adapter):
        """Test getting last updated time."""
        last_updated = adapter.get_last_updated("AAPL")

        assert last_updated is not None
        assert isinstance(last_updated, datetime)
        assert last_updated.date() == adapter.current_date

    def test_get_last_updated_error(self, adapter):
        """Test getting last updated time with error."""
        # Mock datetime.combine to raise exception
        with patch("datetime.datetime.combine", side_effect=Exception("Error")):
            last_updated = adapter.get_last_updated("AAPL")

        assert last_updated is None

    def test_health_check_success(self, adapter, mock_db_session):
        """Test health check success."""

        # Mock database queries
        def mock_query_side_effect(model_class):
            mock_query = Mock()
            if model_class == DevStockQuote.symbol:
                mock_query.filter.return_value.distinct.return_value.count.return_value = (
                    2
                )
            elif model_class == DevOptionQuote.symbol:
                mock_query.filter.return_value.distinct.return_value.count.return_value = (
                    10
                )
            elif model_class == DevStockQuote:
                mock_query.count.return_value = 100
            elif model_class == DevOptionQuote:
                mock_query.count.return_value = 1000
            return mock_query

        mock_db_session.query.side_effect = mock_query_side_effect

        health = adapter.health_check()

        assert health["name"] == "DevDataQuoteAdapter"
        assert health["enabled"] is True
        assert health["status"] == "healthy"
        assert health["current_date"] == "2017-03-24"
        assert health["current_scenario"] == "default"
        assert health["available_stocks"] == 2
        assert health["available_options"] == 10
        assert health["total_stock_quotes_in_db"] == 100
        assert health["total_option_quotes_in_db"] == 1000
        assert health["database_connected"] is True

    def test_health_check_error(self, adapter, mock_db_session):
        """Test health check with error."""
        mock_db_session.query.side_effect = Exception("Database error")

        health = adapter.health_check()

        assert health["status"] == "error"
        assert "Database error" in health["error"]

    def test_get_available_symbols(self, adapter, mock_db_session):
        """Test getting available symbols."""
        mock_stock_symbols = [("AAPL",), ("GOOGL",)]
        mock_option_symbols = [("AAPL170324C00150000",), ("AAPL170324P00150000",)]

        def mock_query_side_effect(model_class):
            mock_query = Mock()
            if model_class == DevStockQuote.symbol:
                mock_query.filter.return_value.distinct.return_value.all.return_value = (
                    mock_stock_symbols
                )
            elif model_class == DevOptionQuote.symbol:
                mock_query.filter.return_value.distinct.return_value.all.return_value = (
                    mock_option_symbols
                )
            return mock_query

        mock_db_session.query.side_effect = mock_query_side_effect

        symbols = adapter.get_available_symbols()

        assert len(symbols) == 4
        assert "AAPL" in symbols
        assert "GOOGL" in symbols
        assert "AAPL170324C00150000" in symbols
        assert "AAPL170324P00150000" in symbols

    def test_get_underlying_symbols(self, adapter, mock_db_session):
        """Test getting underlying symbols."""
        mock_symbols = [("AAPL",), ("GOOGL",)]

        mock_query = Mock()
        mock_query.filter.return_value.distinct.return_value.all.return_value = (
            mock_symbols
        )
        mock_db_session.query.return_value = mock_query

        symbols = adapter.get_underlying_symbols()

        assert symbols == ["AAPL", "GOOGL"]

    def test_get_test_scenarios(self, adapter):
        """Test getting test scenarios."""
        scenarios = adapter.get_test_scenarios()

        assert "aal_earnings" in scenarios
        assert "aal_march_expiration" in scenarios
        assert "goog_january" in scenarios
        assert "goog_march" in scenarios

        # Check scenario structure
        aal_earnings = scenarios["aal_earnings"]
        assert aal_earnings["symbol"] == "AAL"
        assert "2017-01-27" in aal_earnings["dates"]
        assert aal_earnings["scenario"] == "earnings_volatility"

    def test_get_sample_data_info(self, adapter):
        """Test getting sample data info."""
        info = adapter.get_sample_data_info()

        assert "description" in info
        assert "symbols" in info
        assert "dates" in info
        assert "features" in info
        assert "use_cases" in info

        assert "AAL" in info["symbols"]
        assert "GOOG" in info["symbols"]
        assert "2017-01-27" in info["dates"]
        assert "Real market bid/ask spreads" in info["features"]


class TestGetTestAdapter:
    """Test get_test_adapter convenience function."""

    def test_get_test_adapter_default(self):
        """Test getting test adapter with defaults."""
        with patch("app.adapters.test_data.get_sync_session"):
            adapter = get_test_adapter()

        assert isinstance(adapter, DevDataQuoteAdapter)
        assert adapter.current_date == date(2017, 3, 24)
        assert adapter.scenario == "default"

    def test_get_test_adapter_custom(self):
        """Test getting test adapter with custom parameters."""
        with patch("app.adapters.test_data.get_sync_session"):
            adapter = get_test_adapter(
                date="2017-01-27", scenario="earnings_volatility"
            )

        assert isinstance(adapter, DevDataQuoteAdapter)
        assert adapter.current_date == date(2017, 1, 27)
        assert adapter.scenario == "earnings_volatility"
