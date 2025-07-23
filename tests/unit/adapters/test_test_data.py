"""
Comprehensive tests for test data adapter functionality.
"""

import pytest
from unittest.mock import Mock, patch, MagicMock
from datetime import datetime, date, timedelta
from decimal import Decimal

from app.adapters.test_data import DevDataQuoteAdapter, TestDataError, get_test_adapter
from app.adapters.base import AdapterConfig
from app.models.assets import Stock, Option, asset_factory
from app.models.quotes import Quote, OptionQuote, OptionsChain
from app.models.database.trading import DevStockQuote, DevOptionQuote, DevScenario


class TestDevDataQuoteAdapter:
    """Test suite for DevDataQuoteAdapter."""

    @pytest.fixture
    def adapter(self):
        """Create test data adapter with default settings."""
        return DevDataQuoteAdapter(current_date="2017-03-24", scenario="default")

    @pytest.fixture
    def custom_adapter(self):
        """Create test data adapter with custom settings."""
        config = AdapterConfig(
            name="test_adapter", cache_ttl=3600.0, config={"test_param": "value"}
        )
        return DevDataQuoteAdapter(
            current_date="2017-01-27", scenario="earnings_volatility", config=config
        )

    @pytest.fixture
    def mock_db_session(self):
        """Create mock database session."""
        session = MagicMock()
        return session

    @pytest.fixture
    def sample_stock_quote(self):
        """Create sample stock quote from database."""
        quote = DevStockQuote()
        quote.symbol = "AAPL"
        quote.quote_date = date(2017, 3, 24)
        quote.scenario = "default"
        quote.bid = Decimal("150.25")
        quote.ask = Decimal("150.75")
        quote.price = Decimal("150.50")
        quote.volume = 1000000
        return quote

    @pytest.fixture
    def sample_option_quote(self):
        """Create sample option quote from database."""
        quote = DevOptionQuote()
        quote.symbol = "AAPL170324C00150000"
        quote.underlying = "AAPL"
        quote.quote_date = date(2017, 3, 24)
        quote.scenario = "default"
        quote.expiration = date(2017, 3, 24)
        quote.strike = Decimal("150.0")
        quote.option_type = "call"
        quote.bid = Decimal("2.25")
        quote.ask = Decimal("2.75")
        quote.price = Decimal("2.50")
        quote.volume = 500
        return quote

    def test_adapter_initialization_defaults(self):
        """Test adapter initialization with default values."""
        adapter = DevDataQuoteAdapter()

        assert adapter.current_date == date(2017, 3, 24)
        assert adapter.scenario == "default"
        assert adapter.name == "DevDataQuoteAdapter"
        assert adapter.enabled is True
        assert isinstance(adapter.config, AdapterConfig)

    def test_adapter_initialization_custom(self, custom_adapter):
        """Test adapter initialization with custom values."""
        assert custom_adapter.current_date == date(2017, 1, 27)
        assert custom_adapter.scenario == "earnings_volatility"
        assert custom_adapter.config.name == "test_adapter"

    def test_set_date(self, adapter):
        """Test setting current date."""
        adapter.set_date("2017-01-28")

        assert adapter.current_date == date(2017, 1, 28)
        assert len(adapter._quote_cache) == 0  # Cache should be cleared

    def test_set_date_invalid_format(self, adapter):
        """Test setting date with invalid format."""
        with pytest.raises(ValueError):
            adapter.set_date("invalid-date")

    @pytest.mark.asyncio
    async def test_switch_scenario(self, adapter):
        """Test switching scenarios."""
        mock_scenario = DevScenario()
        mock_scenario.name = "new_scenario"
        mock_scenario.start_date = date(2017, 1, 27)

        with patch("app.adapters.test_data.get_sync_session") as mock_session:
            mock_db = MagicMock()
            mock_session.return_value.__enter__.return_value = mock_db
            mock_db.query.return_value.filter.return_value.first.return_value = (
                mock_scenario
            )

            await adapter.switch_scenario("new_scenario")

            assert adapter.scenario == "new_scenario"
            assert adapter.current_date == date(2017, 1, 27)

    @pytest.mark.asyncio
    async def test_switch_scenario_not_found(self, adapter):
        """Test switching to non-existent scenario."""
        with patch("app.adapters.test_data.get_sync_session") as mock_session:
            mock_db = MagicMock()
            mock_session.return_value.__enter__.return_value = mock_db
            mock_db.query.return_value.filter.return_value.first.return_value = None

            # Should not raise error, just not change anything
            await adapter.switch_scenario("nonexistent")

            assert adapter.scenario == "default"  # Should remain unchanged

    def test_get_available_dates(self, adapter):
        """Test getting available dates."""
        mock_dates = [(date(2017, 3, 24),), (date(2017, 3, 25),), (date(2017, 1, 27),)]

        with patch("app.adapters.test_data.get_sync_session") as mock_session:
            mock_db = MagicMock()
            mock_session.return_value.__enter__.return_value = mock_db
            mock_db.query.return_value.filter.return_value.distinct.return_value.all.return_value = (
                mock_dates
            )

            dates = adapter.get_available_dates()

            assert len(dates) == 3
            assert "2017-01-27" in dates
            assert "2017-03-24" in dates
            assert "2017-03-25" in dates

    @pytest.mark.asyncio
    async def test_advance_date(self, adapter):
        """Test advancing date."""
        original_date = adapter.current_date

        await adapter.advance_date(days=2)

        assert adapter.current_date == original_date + timedelta(days=2)
        assert len(adapter._quote_cache) == 0  # Cache should be cleared

    @pytest.mark.asyncio
    async def test_advance_date_negative(self, adapter):
        """Test advancing date with negative days."""
        original_date = adapter.current_date

        await adapter.advance_date(days=-1)

        assert adapter.current_date == original_date - timedelta(days=1)

    def test_get_stock_quote_from_db(self, adapter, sample_stock_quote):
        """Test getting stock quote from database."""
        with patch("app.adapters.test_data.get_sync_session") as mock_session:
            mock_db = MagicMock()
            mock_session.return_value.__enter__.return_value = mock_db
            mock_db.query.return_value.filter.return_value.first.return_value = (
                sample_stock_quote
            )

            quote = adapter._get_stock_quote_from_db(
                "AAPL", date(2017, 3, 24), "default"
            )

            assert quote is sample_stock_quote

    def test_get_stock_quote_from_db_not_found(self, adapter):
        """Test getting non-existent stock quote from database."""
        with patch("app.adapters.test_data.get_sync_session") as mock_session:
            mock_db = MagicMock()
            mock_session.return_value.__enter__.return_value = mock_db
            mock_db.query.return_value.filter.return_value.first.return_value = None

            quote = adapter._get_stock_quote_from_db(
                "INVALID", date(2017, 3, 24), "default"
            )

            assert quote is None

    def test_get_option_quote_from_db(self, adapter, sample_option_quote):
        """Test getting option quote from database."""
        with patch("app.adapters.test_data.get_sync_session") as mock_session:
            mock_db = MagicMock()
            mock_session.return_value.__enter__.return_value = mock_db
            mock_db.query.return_value.filter.return_value.first.return_value = (
                sample_option_quote
            )

            quote = adapter._get_option_quote_from_db(
                "AAPL170324C00150000", date(2017, 3, 24), "default"
            )

            assert quote is sample_option_quote

    def test_cached_stock_quote(self, adapter, sample_stock_quote):
        """Test cached stock quote conversion."""
        with patch("app.adapters.test_data.asset_factory") as mock_factory:
            stock = Stock(symbol="AAPL", name="Apple Inc.")
            mock_factory.return_value = stock

            with patch.object(
                adapter, "_get_stock_quote_from_db", return_value=sample_stock_quote
            ):
                quote = adapter._cached_stock_quote(
                    "AAPL", date(2017, 3, 24), "default"
                )

                assert quote is not None
                assert isinstance(quote, Quote)
                assert quote.asset is stock
                assert quote.bid == 150.25
                assert quote.ask == 150.75
                assert quote.price == 150.50
                assert quote.volume == 1000000

    def test_cached_stock_quote_no_data(self, adapter):
        """Test cached stock quote with no database data."""
        with patch.object(adapter, "_get_stock_quote_from_db", return_value=None):
            quote = adapter._cached_stock_quote("INVALID", date(2017, 3, 24), "default")
            assert quote is None

    def test_cached_option_quote(self, adapter, sample_option_quote):
        """Test cached option quote conversion."""
        underlying = Stock(symbol="AAPL", name="Apple Inc.")
        option = Option(
            symbol="AAPL170324C00150000",
            underlying=underlying,
            option_type="CALL",
            strike=150.0,
            expiration_date=date(2017, 3, 24),
        )

        with patch("app.adapters.test_data.asset_factory") as mock_factory:
            mock_factory.return_value = option

            with patch.object(
                adapter, "_get_option_quote_from_db", return_value=sample_option_quote
            ):
                with patch.object(adapter, "_cached_stock_quote") as mock_stock_quote:
                    # Mock underlying stock quote
                    underlying_quote = Quote(
                        asset=underlying,
                        quote_date=datetime.now(),
                        price=150.0,
                        bid=149.50,
                        ask=150.50,
                        bid_size=100,
                        ask_size=100,
                        volume=1000000,
                    )
                    mock_stock_quote.return_value = underlying_quote

                    quote = adapter._cached_option_quote(
                        "AAPL170324C00150000", date(2017, 3, 24), "default"
                    )

                    assert quote is not None
                    assert isinstance(quote, OptionQuote)
                    assert quote.asset is option
                    assert quote.bid == 2.25
                    assert quote.ask == 2.75
                    assert quote.price == 2.50
                    assert quote.volume == 500

    def test_cached_option_quote_with_greeks(self, adapter, sample_option_quote):
        """Test option quote with Greeks calculation."""
        underlying = Stock(symbol="AAPL", name="Apple Inc.")
        option = Option(
            symbol="AAPL170324C00150000",
            underlying=underlying,
            option_type="CALL",
            strike=150.0,
            expiration_date=date(2017, 3, 24),
        )

        with patch("app.adapters.test_data.asset_factory") as mock_factory:
            with patch("app.services.greeks.calculate_option_greeks") as mock_greeks:
                mock_factory.return_value = option
                mock_greeks.return_value = {
                    "delta": 0.5,
                    "gamma": 0.02,
                    "theta": -0.05,
                    "vega": 0.15,
                    "rho": 0.08,
                }

                with patch.object(
                    adapter,
                    "_get_option_quote_from_db",
                    return_value=sample_option_quote,
                ):
                    with patch.object(
                        adapter, "_cached_stock_quote"
                    ) as mock_stock_quote:
                        # Mock underlying stock quote
                        underlying_quote = Quote(
                            asset=underlying,
                            quote_date=datetime.now(),
                            price=150.0,
                            bid=149.50,
                            ask=150.50,
                            bid_size=100,
                            ask_size=100,
                            volume=1000000,
                        )
                        mock_stock_quote.return_value = underlying_quote

                        quote = adapter._cached_option_quote(
                            "AAPL170324C00150000", date(2017, 3, 24), "default"
                        )

                        assert quote is not None
                        assert quote.delta == 0.5
                        assert quote.gamma == 0.02
                        assert quote.theta == -0.05
                        assert quote.vega == 0.15
                        assert quote.rho == 0.08

    @pytest.mark.asyncio
    async def test_get_quote_stock(self, adapter):
        """Test getting quote for stock asset."""
        stock = Stock(symbol="AAPL", name="Apple Inc.")

        mock_quote = Quote(
            asset=stock,
            quote_date=datetime.now(),
            price=150.0,
            bid=149.50,
            ask=150.50,
            bid_size=100,
            ask_size=100,
            volume=1000000,
        )

        with patch.object(adapter, "_cached_stock_quote", return_value=mock_quote):
            quote = await adapter.get_quote(stock)

            assert quote is mock_quote

    @pytest.mark.asyncio
    async def test_get_quote_option(self, adapter):
        """Test getting quote for option asset."""
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
            price=2.50,
            bid=2.25,
            ask=2.75,
            underlying_price=150.0,
            volume=500,
        )

        with patch.object(adapter, "_cached_option_quote", return_value=mock_quote):
            quote = await adapter.get_quote(option)

            assert quote is mock_quote

    @pytest.mark.asyncio
    async def test_get_quotes_multiple_assets(self, adapter):
        """Test getting quotes for multiple assets."""
        stock = Stock(symbol="AAPL", name="Apple Inc.")
        option = Option(
            symbol="AAPL170324C00150000",
            underlying=stock,
            option_type="CALL",
            strike=150.0,
            expiration_date=date(2017, 3, 24),
        )

        stock_quote = Quote(
            asset=stock,
            quote_date=datetime.now(),
            price=150.0,
            bid=149.50,
            ask=150.50,
            bid_size=100,
            ask_size=100,
            volume=1000000,
        )

        option_quote = OptionQuote(
            asset=option,
            quote_date=datetime.now(),
            price=2.50,
            bid=2.25,
            ask=2.75,
            underlying_price=150.0,
            volume=500,
        )

        async def mock_get_quote(asset):
            if isinstance(asset, Stock):
                return stock_quote
            elif isinstance(asset, Option):
                return option_quote
            return None

        with patch.object(adapter, "get_quote", side_effect=mock_get_quote):
            quotes = await adapter.get_quotes([stock, option])

            assert len(quotes) == 2
            assert quotes[stock] is stock_quote
            assert quotes[option] is option_quote

    @pytest.mark.asyncio
    async def test_batch_get_quotes(
        self, adapter, sample_stock_quote, sample_option_quote
    ):
        """Test batch quote retrieval."""
        symbols = ["AAPL", "AAPL170324C00150000"]

        with patch("app.adapters.test_data.get_sync_session") as mock_session:
            with patch("app.adapters.test_data.asset_factory") as mock_factory:
                mock_db = MagicMock()
                mock_session.return_value.__enter__.return_value = mock_db

                # Mock database queries
                stock_query = MagicMock()
                stock_query.all.return_value = [sample_stock_quote]
                option_query = MagicMock()
                option_query.all.return_value = [sample_option_quote]

                mock_db.query.side_effect = [stock_query, option_query]

                # Mock asset factory
                stock = Stock(symbol="AAPL", name="Apple Inc.")
                option = Option(
                    symbol="AAPL170324C00150000",
                    underlying=stock,
                    option_type="CALL",
                    strike=150.0,
                    expiration_date=date(2017, 3, 24),
                )
                mock_factory.side_effect = [stock, option]

                with patch.object(adapter, "_cached_stock_quote") as mock_stock_cached:
                    with patch.object(
                        adapter, "_cached_option_quote"
                    ) as mock_option_cached:
                        stock_quote = Quote(
                            asset=stock,
                            quote_date=datetime.now(),
                            price=150.0,
                            bid=149.50,
                            ask=150.50,
                            bid_size=100,
                            ask_size=100,
                            volume=1000000,
                        )
                        option_quote = OptionQuote(
                            asset=option,
                            quote_date=datetime.now(),
                            price=2.50,
                            bid=2.25,
                            ask=2.75,
                            underlying_price=150.0,
                            volume=500,
                        )

                        mock_stock_cached.return_value = stock_quote
                        mock_option_cached.return_value = option_quote

                        quotes = await adapter.batch_get_quotes(symbols)

                        assert len(quotes) == 2
                        assert quotes["AAPL"] is stock_quote
                        assert quotes["AAPL170324C00150000"] is option_quote

    @pytest.mark.asyncio
    async def test_get_quotes_for_date_range(self, adapter):
        """Test getting quotes for a date range."""
        start_date = date(2017, 3, 24)
        end_date = date(2017, 3, 25)

        mock_records = [sample_stock_quote for _ in range(2)]  # Two days of data

        with patch("app.adapters.test_data.get_sync_session") as mock_session:
            with patch("app.adapters.test_data.asset_factory") as mock_factory:
                mock_db = MagicMock()
                mock_session.return_value.__enter__.return_value = mock_db

                query_mock = MagicMock()
                query_mock.all.return_value = mock_records
                mock_db.query.return_value.filter.return_value.order_by.return_value = (
                    query_mock
                )

                stock = Stock(symbol="AAPL", name="Apple Inc.")
                mock_factory.return_value = stock

                with patch.object(adapter, "_cached_stock_quote") as mock_cached:
                    mock_quote = Quote(
                        asset=stock,
                        quote_date=datetime.now(),
                        price=150.0,
                        bid=149.50,
                        ask=150.50,
                        bid_size=100,
                        ask_size=100,
                        volume=1000000,
                    )
                    mock_cached.return_value = mock_quote

                    quotes = await adapter.get_quotes_for_date_range(
                        "AAPL", start_date, end_date
                    )

                    assert len(quotes) == 2
                    assert all(isinstance(quote, Quote) for quote in quotes)

    @pytest.mark.asyncio
    async def test_get_chain(self, adapter):
        """Test getting option chain assets."""
        # This method returns empty list in current implementation
        assets = await adapter.get_chain("AAPL")
        assert assets == []

    @pytest.mark.asyncio
    async def test_get_options_chain(self, adapter, sample_option_quote):
        """Test getting complete options chain."""
        underlying = Stock(symbol="AAPL", name="Apple Inc.")
        option = Option(
            symbol="AAPL170324C00150000",
            underlying=underlying,
            option_type="CALL",
            strike=150.0,
            expiration_date=date(2017, 3, 24),
        )

        with patch("app.adapters.test_data.asset_factory") as mock_factory:
            with patch("app.adapters.test_data.get_sync_session") as mock_session:
                mock_factory.return_value = underlying

                mock_db = MagicMock()
                mock_session.return_value.__enter__.return_value = mock_db

                query_mock = MagicMock()
                query_mock.all.return_value = [sample_option_quote]
                mock_db.query.return_value.filter.return_value = query_mock

                with patch.object(adapter, "get_quote") as mock_get_quote:
                    with patch.object(
                        adapter, "_cached_option_quote"
                    ) as mock_option_cached:
                        underlying_quote = Quote(
                            asset=underlying,
                            quote_date=datetime.now(),
                            price=150.0,
                            bid=149.50,
                            ask=150.50,
                            bid_size=100,
                            ask_size=100,
                            volume=1000000,
                        )
                        mock_get_quote.return_value = underlying_quote

                        option_quote = OptionQuote(
                            asset=option,
                            quote_date=datetime.now(),
                            price=2.50,
                            bid=2.25,
                            ask=2.75,
                            underlying_price=150.0,
                            volume=500,
                        )
                        mock_option_cached.return_value = option_quote

                        chain = await adapter.get_options_chain("AAPL")

                        assert chain is not None
                        assert isinstance(chain, OptionsChain)
                        assert chain.underlying_symbol == "AAPL"
                        assert chain.underlying_price == 150.0

    def test_get_expiration_dates(self, adapter):
        """Test getting expiration dates for underlying."""
        mock_dates = [(date(2017, 3, 24),), (date(2017, 4, 21),)]

        with patch("app.adapters.test_data.get_sync_session") as mock_session:
            mock_db = MagicMock()
            mock_session.return_value.__enter__.return_value = mock_db

            query_mock = MagicMock()
            query_mock.all.return_value = mock_dates
            mock_db.query.return_value.filter.return_value.distinct.return_value = (
                query_mock
            )

            dates = adapter.get_expiration_dates("AAPL")

            assert len(dates) == 2
            assert date(2017, 3, 24) in dates
            assert date(2017, 4, 21) in dates

    @pytest.mark.asyncio
    async def test_is_market_open(self, adapter):
        """Test market open status (always True for test data)."""
        is_open = await adapter.is_market_open()
        assert is_open is True

    @pytest.mark.asyncio
    async def test_get_market_hours(self, adapter):
        """Test getting market hours."""
        hours = await adapter.get_market_hours()

        assert isinstance(hours, dict)
        assert "open" in hours
        assert "close" in hours

    def test_supports_symbol(self, adapter):
        """Test symbol support check."""
        with patch("app.adapters.test_data.asset_factory") as mock_factory:
            with patch("app.adapters.test_data.get_sync_session") as mock_session:
                mock_factory.return_value = Stock(symbol="AAPL", name="Apple Inc.")

                mock_db = MagicMock()
                mock_session.return_value.__enter__.return_value = mock_db

                query_mock = MagicMock()
                query_mock.first.return_value = Mock()  # Found
                mock_db.query.return_value.filter.return_value = query_mock

                result = adapter.supports_symbol("AAPL")
                assert result is True

    def test_supports_symbol_not_found(self, adapter):
        """Test symbol support check for non-existent symbol."""
        with patch("app.adapters.test_data.asset_factory") as mock_factory:
            with patch("app.adapters.test_data.get_sync_session") as mock_session:
                mock_factory.return_value = Stock(symbol="INVALID", name="Invalid")

                mock_db = MagicMock()
                mock_session.return_value.__enter__.return_value = mock_db

                query_mock = MagicMock()
                query_mock.first.return_value = None  # Not found
                mock_db.query.return_value.filter.return_value = query_mock

                result = adapter.supports_symbol("INVALID")
                assert result is False

    def test_get_last_updated(self, adapter):
        """Test getting last updated timestamp."""
        timestamp = adapter.get_last_updated("AAPL")

        assert timestamp is not None
        assert isinstance(timestamp, datetime)
        assert timestamp.date() == adapter.current_date

    def test_health_check(self, adapter):
        """Test health check functionality."""
        with patch("app.adapters.test_data.get_sync_session") as mock_session:
            mock_db = MagicMock()
            mock_session.return_value.__enter__.return_value = mock_db

            # Mock count queries
            stock_query = MagicMock()
            stock_query.count.return_value = 5
            option_query = MagicMock()
            option_query.count.return_value = 50
            total_stock_query = MagicMock()
            total_stock_query.count.return_value = 100
            total_option_query = MagicMock()
            total_option_query.count.return_value = 1000

            mock_db.query.side_effect = [
                stock_query,
                option_query,
                total_stock_query,
                total_option_query,
            ]

            health = adapter.health_check()

            assert health["name"] == adapter.name
            assert health["enabled"] is True
            assert health["status"] == "healthy"
            assert health["current_date"] == "2017-03-24"
            assert health["available_stocks"] == 5
            assert health["available_options"] == 50

    def test_health_check_error(self, adapter):
        """Test health check with database error."""
        with patch("app.adapters.test_data.get_sync_session") as mock_session:
            mock_session.side_effect = Exception("Database error")

            health = adapter.health_check()

            assert health["status"] == "error"
            assert "Database error" in health["error"]

    def test_get_available_symbols(self, adapter):
        """Test getting available symbols."""
        stock_symbols = [("AAPL",), ("GOOGL",)]
        option_symbols = [("AAPL170324C00150000",), ("GOOGL170324C02500000",)]

        with patch("app.adapters.test_data.get_sync_session") as mock_session:
            mock_db = MagicMock()
            mock_session.return_value.__enter__.return_value = mock_db

            stock_query = MagicMock()
            stock_query.all.return_value = stock_symbols
            option_query = MagicMock()
            option_query.all.return_value = option_symbols

            mock_db.query.side_effect = [stock_query, option_query]

            symbols = adapter.get_available_symbols()

            assert len(symbols) == 4
            assert "AAPL" in symbols
            assert "GOOGL" in symbols
            assert "AAPL170324C00150000" in symbols
            assert "GOOGL170324C02500000" in symbols

    def test_get_underlying_symbols(self, adapter):
        """Test getting underlying symbols."""
        underlying_symbols = [("AAPL",), ("GOOGL",)]

        with patch("app.adapters.test_data.get_sync_session") as mock_session:
            mock_db = MagicMock()
            mock_session.return_value.__enter__.return_value = mock_db

            query_mock = MagicMock()
            query_mock.all.return_value = underlying_symbols
            mock_db.query.return_value.filter.return_value.distinct.return_value = (
                query_mock
            )

            symbols = adapter.get_underlying_symbols()

            assert len(symbols) == 2
            assert "AAPL" in symbols
            assert "GOOGL" in symbols

    def test_get_test_scenarios(self, adapter):
        """Test getting test scenarios."""
        scenarios = adapter.get_test_scenarios()

        assert isinstance(scenarios, dict)
        assert "aal_earnings" in scenarios
        assert "goog_january" in scenarios
        assert scenarios["aal_earnings"]["symbol"] == "AAL"

    def test_get_sample_data_info(self, adapter):
        """Test getting sample data info."""
        info = adapter.get_sample_data_info()

        assert isinstance(info, dict)
        assert "description" in info
        assert "symbols" in info
        assert "dates" in info
        assert "features" in info
        assert "AAL" in info["symbols"]
        assert "GOOG" in info["symbols"]


class TestGetTestAdapter:
    """Test the convenience function for getting test adapter."""

    def test_get_test_adapter_defaults(self):
        """Test getting test adapter with defaults."""
        adapter = get_test_adapter()

        assert isinstance(adapter, DevDataQuoteAdapter)
        assert adapter.current_date == date(2017, 3, 24)
        assert adapter.scenario == "default"

    def test_get_test_adapter_custom(self):
        """Test getting test adapter with custom parameters."""
        adapter = get_test_adapter(date="2017-01-27", scenario="earnings_volatility")

        assert adapter.current_date == date(2017, 1, 27)
        assert adapter.scenario == "earnings_volatility"


class TestTestDataError:
    """Test TestDataError exception."""

    def test_test_data_error(self):
        """Test TestDataError can be raised and caught."""
        with pytest.raises(TestDataError):
            raise TestDataError("Test error message")

    def test_test_data_error_with_message(self):
        """Test TestDataError with custom message."""
        try:
            raise TestDataError("Custom error message")
        except TestDataError as e:
            assert str(e) == "Custom error message"


class TestDevDataQuoteAdapterEdgeCases:
    """Test edge cases and error handling."""

    @pytest.fixture
    def adapter(self):
        """Create adapter for edge case testing."""
        return DevDataQuoteAdapter()

    def test_cached_stock_quote_invalid_asset(self, adapter):
        """Test cached stock quote with invalid asset factory result."""
        with patch("app.adapters.test_data.asset_factory", return_value=None):
            with patch.object(adapter, "_get_stock_quote_from_db", return_value=Mock()):
                quote = adapter._cached_stock_quote(
                    "INVALID", date(2017, 3, 24), "default"
                )
                assert quote is None

    def test_cached_option_quote_invalid_asset(self, adapter):
        """Test cached option quote with invalid asset factory result."""
        with patch("app.adapters.test_data.asset_factory", return_value=None):
            with patch.object(
                adapter, "_get_option_quote_from_db", return_value=Mock()
            ):
                quote = adapter._cached_option_quote(
                    "INVALID", date(2017, 3, 24), "default"
                )
                assert quote is None

    def test_cached_option_quote_greeks_calculation_error(
        self, adapter, sample_option_quote
    ):
        """Test option quote when Greeks calculation fails."""
        underlying = Stock(symbol="AAPL", name="Apple Inc.")
        option = Option(
            symbol="AAPL170324C00150000",
            underlying=underlying,
            option_type="CALL",
            strike=150.0,
            expiration_date=date(2017, 3, 24),
        )

        with patch("app.adapters.test_data.asset_factory", return_value=option):
            with patch(
                "app.services.greeks.calculate_option_greeks",
                side_effect=Exception("Calculation error"),
            ):
                with patch.object(
                    adapter,
                    "_get_option_quote_from_db",
                    return_value=sample_option_quote,
                ):
                    with patch.object(
                        adapter, "_cached_stock_quote"
                    ) as mock_stock_quote:
                        underlying_quote = Quote(
                            asset=underlying,
                            quote_date=datetime.now(),
                            price=150.0,
                            bid=149.50,
                            ask=150.50,
                            bid_size=100,
                            ask_size=100,
                            volume=1000000,
                        )
                        mock_stock_quote.return_value = underlying_quote

                        # Should not raise exception, just continue without Greeks
                        quote = adapter._cached_option_quote(
                            "AAPL170324C00150000", date(2017, 3, 24), "default"
                        )

                        assert quote is not None
                        # Greeks should be None since calculation failed
                        assert quote.delta is None

    @pytest.mark.asyncio
    async def test_get_quotes_for_date_range_invalid_asset(self, adapter):
        """Test getting quotes for date range with invalid asset."""
        with patch("app.adapters.test_data.asset_factory", return_value=None):
            quotes = await adapter.get_quotes_for_date_range(
                "INVALID", date(2017, 3, 24), date(2017, 3, 25)
            )
            assert quotes == []

    def test_supports_symbol_asset_factory_error(self, adapter):
        """Test supports_symbol when asset_factory fails."""
        with patch(
            "app.adapters.test_data.asset_factory",
            side_effect=Exception("Asset creation error"),
        ):
            result = adapter.supports_symbol("AAPL")
            assert result is False

    def test_get_last_updated_error(self, adapter):
        """Test get_last_updated with error."""
        # Force an error by setting invalid current_date
        adapter.current_date = None

        result = adapter.get_last_updated("AAPL")
        assert result is None


class TestDevDataQuoteAdapterPerformance:
    """Performance tests for DevDataQuoteAdapter."""

    @pytest.fixture
    def adapter(self):
        """Create adapter for performance testing."""
        return DevDataQuoteAdapter()

    def test_cache_performance(self, adapter):
        """Test caching improves performance."""
        # Simulate cache population
        for i in range(100):
            key = f"test_key_{i}"
            value = f"test_value_{i}"
            adapter._quote_cache[key] = value

        # Access should be fast
        import time

        start_time = time.time()

        for i in range(100):
            key = f"test_key_{i}"
            value = adapter._quote_cache.get(key)
            assert value == f"test_value_{i}"

        end_time = time.time()

        # Should complete very quickly
        assert (end_time - start_time) < 0.1

    @pytest.mark.asyncio
    async def test_batch_quote_performance(self, adapter):
        """Test batch quote retrieval performance."""
        symbols = [f"STOCK{i}" for i in range(50)]

        with patch("app.adapters.test_data.get_sync_session") as mock_session:
            mock_db = MagicMock()
            mock_session.return_value.__enter__.return_value = mock_db

            # Mock database to return empty results (fast)
            query_mock = MagicMock()
            query_mock.all.return_value = []
            mock_db.query.return_value.filter.return_value = query_mock

            import time

            start_time = time.time()

            quotes = await adapter.batch_get_quotes(symbols)

            end_time = time.time()

            # Should complete quickly even with many symbols
            assert (end_time - start_time) < 1.0
            assert isinstance(quotes, dict)
