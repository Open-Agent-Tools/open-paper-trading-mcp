"""
Comprehensive integration tests for test data adapters.

Tests DevDataQuoteAdapter with focus on:
- Database integration and query patterns
- Test scenario management
- Date handling and time series data
- Options chain and Greeks calculations
- Performance with large datasets
- Concurrent access scenarios
- Cache integration
- Error handling and recovery
"""

import asyncio
from datetime import date, datetime
from decimal import Decimal
from unittest.mock import MagicMock, Mock, patch

import pytest
from sqlalchemy.exc import SQLAlchemyError

from app.adapters.base import AdapterConfig
from app.adapters.test_data import (
    DevDataQuoteAdapter,
    get_test_adapter,
)
from app.models.assets import Option, Stock
from app.models.database.trading import DevOptionQuote, DevStockQuote
from app.models.quotes import OptionQuote, OptionsChain, Quote


class TestDevDataQuoteAdapterDatabaseIntegration:
    """Integration tests for DevDataQuoteAdapter with database operations."""

    @pytest.fixture
    def adapter(self):
        """Create test data adapter."""
        return DevDataQuoteAdapter(current_date="2017-03-24", scenario="default")

    @pytest.fixture
    def custom_adapter(self):
        """Create adapter with custom settings."""
        config = AdapterConfig(
            name="custom_test_adapter",
            cache_ttl=1800.0,
            config={"custom_param": "custom_value"},
        )
        return DevDataQuoteAdapter(
            current_date="2017-01-27", scenario="earnings_volatility", config=config
        )

    @pytest.fixture
    def mock_stock_quote_data(self):
        """Create mock stock quote data."""
        return {
            "symbol": "AAPL",
            "quote_date": date(2017, 3, 24),
            "scenario": "default",
            "bid": Decimal("150.25"),
            "ask": Decimal("150.75"),
            "price": Decimal("150.50"),
            "volume": 1000000,
        }

    @pytest.fixture
    def mock_option_quote_data(self):
        """Create mock option quote data."""
        return {
            "symbol": "AAPL170324C00150000",
            "underlying": "AAPL",
            "quote_date": date(2017, 3, 24),
            "scenario": "default",
            "expiration": date(2017, 3, 24),
            "strike": Decimal("150.0"),
            "option_type": "call",
            "bid": Decimal("2.25"),
            "ask": Decimal("2.75"),
            "price": Decimal("2.50"),
            "volume": 500,
        }

    @pytest.mark.integration
    def test_adapter_initialization_integration(self, adapter, custom_adapter):
        """Test adapter initialization with different configurations."""
        # Default adapter
        assert adapter.current_date == date(2017, 3, 24)
        assert adapter.scenario == "default"
        assert adapter.name == "DevDataQuoteAdapter"
        assert adapter.enabled is True

        # Custom adapter
        assert custom_adapter.current_date == date(2017, 1, 27)
        assert custom_adapter.scenario == "earnings_volatility"
        assert custom_adapter.config.name == "custom_test_adapter"

    @pytest.mark.integration
    def test_database_stock_quote_retrieval_integration(
        self, adapter, mock_stock_quote_data
    ):
        """Test stock quote retrieval from database."""
        with patch("app.adapters.test_data.get_sync_session") as mock_session:
            # Setup mock database session
            mock_db = MagicMock()
            mock_session.return_value.__enter__.return_value = mock_db

            # Create mock database quote
            mock_db_quote = DevStockQuote()
            for key, value in mock_stock_quote_data.items():
                setattr(mock_db_quote, key, value)

            mock_db.query.return_value.filter.return_value.first.return_value = (
                mock_db_quote
            )

            # Test retrieval
            db_quote = adapter._get_stock_quote_from_db(
                "AAPL", date(2017, 3, 24), "default"
            )

            assert db_quote is mock_db_quote
            assert db_quote.symbol == "AAPL"
            assert db_quote.price == Decimal("150.50")

    @pytest.mark.integration
    def test_database_option_quote_retrieval_integration(
        self, adapter, mock_option_quote_data
    ):
        """Test option quote retrieval from database."""
        with patch("app.adapters.test_data.get_sync_session") as mock_session:
            mock_db = MagicMock()
            mock_session.return_value.__enter__.return_value = mock_db

            # Create mock database quote
            mock_db_quote = DevOptionQuote()
            for key, value in mock_option_quote_data.items():
                setattr(mock_db_quote, key, value)

            mock_db.query.return_value.filter.return_value.first.return_value = (
                mock_db_quote
            )

            # Test retrieval
            db_quote = adapter._get_option_quote_from_db(
                "AAPL170324C00150000", date(2017, 3, 24), "default"
            )

            assert db_quote is mock_db_quote
            assert db_quote.symbol == "AAPL170324C00150000"
            assert db_quote.option_type == "call"

    @pytest.mark.integration
    def test_cached_stock_quote_conversion_integration(
        self, adapter, mock_stock_quote_data
    ):
        """Test conversion of database stock quote to Quote object."""
        with patch("app.adapters.test_data.asset_factory") as mock_factory:
            with patch.object(adapter, "_get_stock_quote_from_db") as mock_db_get:
                # Setup mocks
                stock = Stock(symbol="AAPL", name="Apple Inc.")
                mock_factory.return_value = stock

                mock_db_quote = DevStockQuote()
                for key, value in mock_stock_quote_data.items():
                    setattr(mock_db_quote, key, value)
                mock_db_get.return_value = mock_db_quote

                # Test conversion
                quote = adapter._cached_stock_quote(
                    "AAPL", date(2017, 3, 24), "default"
                )

                assert quote is not None
                assert isinstance(quote, Quote)
                assert quote.asset is stock
                assert quote.price == 150.50
                assert quote.bid == 150.25
                assert quote.ask == 150.75
                assert quote.volume == 1000000

    @pytest.mark.integration
    def test_cached_option_quote_conversion_integration(
        self, adapter, mock_option_quote_data
    ):
        """Test conversion of database option quote to OptionQuote object."""
        with patch("app.adapters.test_data.asset_factory") as mock_factory:
            with patch.object(adapter, "_get_option_quote_from_db") as mock_db_get:
                with patch.object(adapter, "_cached_stock_quote") as mock_stock_quote:
                    # Setup mocks
                    underlying = Stock(symbol="AAPL", name="Apple Inc.")
                    option = Option(
                        symbol="AAPL170324C00150000",
                        underlying=underlying,
                        option_type="CALL",
                        strike=150.0,
                        expiration_date=date(2017, 3, 24),
                    )
                    mock_factory.return_value = option

                    mock_db_quote = DevOptionQuote()
                    for key, value in mock_option_quote_data.items():
                        setattr(mock_db_quote, key, value)
                    mock_db_get.return_value = mock_db_quote

                    # Mock underlying stock quote for Greeks calculation
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

                    # Test conversion
                    quote = adapter._cached_option_quote(
                        "AAPL170324C00150000", date(2017, 3, 24), "default"
                    )

                    assert quote is not None
                    assert isinstance(quote, OptionQuote)
                    assert quote.asset is option
                    assert quote.price == 2.50
                    assert quote.bid == 2.25
                    assert quote.ask == 2.75

    @pytest.mark.integration
    @pytest.mark.asyncio
    async def test_get_quote_integration_workflow(self, adapter):
        """Test complete get_quote workflow integration."""
        with patch("app.adapters.test_data.asset_factory") as mock_factory:
            with patch.object(adapter, "_cached_stock_quote") as mock_cached_stock:
                with patch.object(
                    adapter, "_cached_option_quote"
                ) as mock_cached_option:
                    # Test stock quote
                    stock = Stock(symbol="AAPL", name="Apple Inc.")
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

                    mock_factory.return_value = stock
                    mock_cached_stock.return_value = stock_quote

                    result = await adapter.get_quote(stock)
                    assert result is stock_quote

                    # Test option quote
                    option = Option(
                        symbol="AAPL170324C00150000",
                        underlying=stock,
                        option_type="CALL",
                        strike=150.0,
                        expiration_date=date(2017, 3, 24),
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

                    mock_factory.return_value = option
                    mock_cached_option.return_value = option_quote

                    result = await adapter.get_quote(option)
                    assert result is option_quote

    @pytest.mark.integration
    @pytest.mark.asyncio
    async def test_batch_get_quotes_integration(self, adapter):
        """Test batch quote retrieval integration."""
        symbols = ["AAPL", "AAPL170324C00150000", "GOOGL"]

        with patch("app.adapters.test_data.get_sync_session") as mock_session:
            with patch("app.adapters.test_data.asset_factory") as mock_factory:
                mock_db = MagicMock()
                mock_session.return_value.__enter__.return_value = mock_db

                # Mock database queries
                stock_records = [Mock(symbol="AAPL"), Mock(symbol="GOOGL")]
                option_records = [Mock(symbol="AAPL170324C00150000")]

                mock_db.query.side_effect = [
                    Mock(all=Mock(return_value=stock_records)),
                    Mock(all=Mock(return_value=option_records)),
                ]

                # Mock asset factory
                assets = [
                    Stock(symbol="AAPL", name="Apple Inc."),
                    Option(
                        symbol="AAPL170324C00150000",
                        underlying=Stock(symbol="AAPL", name="Apple Inc."),
                        option_type="CALL",
                        strike=150.0,
                        expiration_date=date(2017, 3, 24),
                    ),
                    Stock(symbol="GOOGL", name="Alphabet Inc."),
                ]
                mock_factory.side_effect = assets[:2]  # First two calls

                with patch.object(adapter, "_cached_stock_quote") as mock_stock_cached:
                    with patch.object(
                        adapter, "_cached_option_quote"
                    ) as mock_option_cached:
                        # Mock cached quote methods
                        stock_quote = Quote(
                            asset=assets[0],
                            quote_date=datetime.now(),
                            price=150.0,
                            bid=149.50,
                            ask=150.50,
                            bid_size=100,
                            ask_size=100,
                            volume=1000000,
                        )
                        option_quote = OptionQuote(
                            asset=assets[1],
                            quote_date=datetime.now(),
                            price=2.50,
                            bid=2.25,
                            ask=2.75,
                            underlying_price=150.0,
                            volume=500,
                        )

                        mock_stock_cached.return_value = stock_quote
                        mock_option_cached.return_value = option_quote

                        results = await adapter.batch_get_quotes(symbols)

                        assert len(results) >= 2  # At least the mocked ones
                        assert "AAPL" in results or "AAPL170324C00150000" in results

    @pytest.mark.integration
    @pytest.mark.asyncio
    async def test_options_chain_integration(self, adapter):
        """Test options chain retrieval integration."""
        underlying = "AAPL"

        with patch("app.adapters.test_data.asset_factory") as mock_factory:
            with patch("app.adapters.test_data.get_sync_session") as mock_session:
                with patch.object(adapter, "get_quote") as mock_get_quote:
                    # Setup mocks
                    underlying_asset = Stock(symbol="AAPL", name="Apple Inc.")
                    mock_factory.return_value = underlying_asset

                    mock_db = MagicMock()
                    mock_session.return_value.__enter__.return_value = mock_db

                    # Mock database option records
                    option_records = [
                        Mock(
                            symbol="AAPL170324C00150000",
                            underlying="AAPL",
                            expiration=date(2017, 3, 24),
                            quote_date=date(2017, 3, 24),
                        )
                    ]
                    mock_db.query.return_value.filter.return_value.all.return_value = (
                        option_records
                    )

                    # Mock underlying quote
                    underlying_quote = Quote(
                        asset=underlying_asset,
                        quote_date=datetime.now(),
                        price=150.0,
                        bid=149.50,
                        ask=150.50,
                        bid_size=100,
                        ask_size=100,
                        volume=1000000,
                    )
                    mock_get_quote.return_value = underlying_quote

                    with patch.object(
                        adapter, "_cached_option_quote"
                    ) as mock_option_cached:
                        option = Option(
                            symbol="AAPL170324C00150000",
                            underlying=underlying_asset,
                            option_type="CALL",
                            strike=150.0,
                            expiration_date=date(2017, 3, 24),
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
                        mock_option_cached.return_value = option_quote

                        chain = await adapter.get_options_chain(underlying)

                        assert chain is not None
                        assert isinstance(chain, OptionsChain)
                        assert chain.underlying_symbol == underlying
                        assert chain.underlying_price == 150.0

    @pytest.mark.integration
    def test_scenario_management_integration(self, adapter):
        """Test scenario switching and management."""
        with patch("app.adapters.test_data.get_sync_session") as mock_session:
            mock_db = MagicMock()
            mock_session.return_value.__enter__.return_value = mock_db

            # Test getting available dates
            mock_dates = [(date(2017, 3, 24),), (date(2017, 3, 25),)]
            mock_db.query.return_value.filter.return_value.distinct.return_value.all.return_value = mock_dates

            dates = adapter.get_available_dates()

            assert len(dates) == 2
            assert "2017-03-24" in dates
            assert "2017-03-25" in dates

    @pytest.mark.integration
    @pytest.mark.asyncio
    async def test_date_range_quote_retrieval_integration(self, adapter):
        """Test retrieving quotes for date range."""
        symbol = "AAPL"
        start_date = date(2017, 3, 24)
        end_date = date(2017, 3, 25)

        with patch("app.adapters.test_data.get_sync_session") as mock_session:
            with patch("app.adapters.test_data.asset_factory") as mock_factory:
                mock_db = MagicMock()
                mock_session.return_value.__enter__.return_value = mock_db

                # Mock asset
                stock = Stock(symbol="AAPL", name="Apple Inc.")
                mock_factory.return_value = stock

                # Mock database records
                records = [
                    Mock(symbol="AAPL", quote_date=date(2017, 3, 24)),
                    Mock(symbol="AAPL", quote_date=date(2017, 3, 25)),
                ]
                mock_db.query.return_value.filter.return_value.order_by.return_value.all.return_value = records

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
                        symbol, start_date, end_date
                    )

                    assert len(quotes) == 2
                    assert all(isinstance(quote, Quote) for quote in quotes)

    @pytest.mark.integration
    def test_expiration_dates_retrieval_integration(self, adapter):
        """Test getting expiration dates for underlying."""
        underlying = "AAPL"

        with patch("app.adapters.test_data.get_sync_session") as mock_session:
            mock_db = MagicMock()
            mock_session.return_value.__enter__.return_value = mock_db

            # Mock expiration dates
            exp_dates = [(date(2017, 3, 24),), (date(2017, 4, 21),)]
            mock_db.query.return_value.filter.return_value.distinct.return_value.all.return_value = exp_dates

            dates = adapter.get_expiration_dates(underlying)

            assert len(dates) == 2
            assert date(2017, 3, 24) in dates
            assert date(2017, 4, 21) in dates

    @pytest.mark.integration
    def test_health_check_integration(self, adapter):
        """Test health check functionality."""
        with patch("app.adapters.test_data.get_sync_session") as mock_session:
            mock_db = MagicMock()
            mock_session.return_value.__enter__.return_value = mock_db

            # Mock count queries
            mock_db.query.side_effect = [
                Mock(
                    distinct=Mock(return_value=Mock(count=Mock(return_value=5)))
                ),  # stock symbols
                Mock(
                    distinct=Mock(return_value=Mock(count=Mock(return_value=50)))
                ),  # option symbols
                Mock(count=Mock(return_value=100)),  # total stock quotes
                Mock(count=Mock(return_value=1000)),  # total option quotes
            ]

            health = adapter.health_check()

            assert health["name"] == adapter.name
            assert health["enabled"] is True
            assert health["status"] == "healthy"
            assert health["current_date"] == "2017-03-24"
            assert health["available_stocks"] == 5
            assert health["available_options"] == 50
            assert health["database_connected"] is True

    @pytest.mark.integration
    def test_symbols_retrieval_integration(self, adapter):
        """Test getting available symbols."""
        with patch("app.adapters.test_data.get_sync_session") as mock_session:
            mock_db = MagicMock()
            mock_session.return_value.__enter__.return_value = mock_db

            # Mock symbol queries
            stock_symbols = [("AAPL",), ("GOOGL",)]
            option_symbols = [("AAPL170324C00150000",), ("GOOGL170324C02500000",)]

            mock_db.query.side_effect = [
                Mock(all=Mock(return_value=stock_symbols)),
                Mock(all=Mock(return_value=option_symbols)),
            ]

            symbols = adapter.get_available_symbols()

            assert len(symbols) == 4
            assert "AAPL" in symbols
            assert "GOOGL" in symbols
            assert "AAPL170324C00150000" in symbols
            assert "GOOGL170324C02500000" in symbols

    @pytest.mark.integration
    @pytest.mark.asyncio
    async def test_market_status_integration(self, adapter):
        """Test market status methods."""
        # Market should always be open for test data
        is_open = await adapter.is_market_open()
        assert is_open is True

        # Get market hours
        hours = await adapter.get_market_hours()
        assert isinstance(hours, dict)
        assert "open" in hours
        assert "close" in hours

    @pytest.mark.integration
    def test_sample_data_info_integration(self, adapter):
        """Test getting sample data information."""
        info = adapter.get_sample_data_info()

        assert isinstance(info, dict)
        assert "description" in info
        assert "symbols" in info
        assert "dates" in info
        assert "features" in info
        assert "use_cases" in info

        # Verify sample data structure
        assert "AAL" in info["symbols"]
        assert "GOOG" in info["symbols"]
        assert len(info["dates"]) > 0


class TestDevDataQuoteAdapterConcurrency:
    """Test concurrent access to DevDataQuoteAdapter."""

    @pytest.fixture
    def adapter(self):
        """Create adapter for concurrency testing."""
        return DevDataQuoteAdapter()

    @pytest.mark.integration
    @pytest.mark.asyncio
    async def test_concurrent_quote_requests(self, adapter):
        """Test concurrent quote requests."""
        symbols = ["AAPL", "GOOGL", "MSFT", "AMZN", "TSLA"]

        with patch.object(adapter, "_cached_stock_quote") as mock_cached:
            # Mock quote response
            def mock_quote_response(symbol, quote_date, scenario):
                if symbol in symbols:
                    stock = Stock(symbol=symbol, name=f"{symbol} Inc.")
                    return Quote(
                        asset=stock,
                        quote_date=datetime.now(),
                        price=100.0,
                        bid=99.5,
                        ask=100.5,
                        bid_size=100,
                        ask_size=100,
                        volume=1000,
                    )
                return None

            mock_cached.side_effect = mock_quote_response

            # Create concurrent tasks
            async def get_quote_task(symbol):
                asset = Stock(symbol=symbol, name=f"{symbol} Inc.")
                return await adapter.get_quote(asset)

            tasks = [get_quote_task(symbol) for symbol in symbols]
            results = await asyncio.gather(*tasks)

            # Verify all requests completed successfully
            assert len(results) == len(symbols)
            assert all(result is not None for result in results)

    @pytest.mark.integration
    def test_concurrent_cache_access(self, adapter):
        """Test concurrent access to adapter cache."""
        import threading

        results = []
        errors = []

        def cache_worker(worker_id: int):
            """Worker function for concurrent cache operations."""
            try:
                for i in range(10):
                    key = f"worker_{worker_id}_item_{i}"
                    value = f"value_{worker_id}_{i}"

                    # Cache operations
                    adapter._quote_cache[key] = value
                    retrieved = adapter._quote_cache.get(key)

                    if retrieved == value:
                        results.append(f"{worker_id}_{i}")

            except Exception as e:
                errors.append(f"Worker {worker_id}: {e!s}")

        # Create worker threads
        threads = []
        for worker_id in range(5):
            thread = threading.Thread(target=cache_worker, args=(worker_id,))
            threads.append(thread)

        # Start all threads
        for thread in threads:
            thread.start()

        # Wait for completion
        for thread in threads:
            thread.join()

        # Verify no errors
        assert len(errors) == 0, f"Concurrent errors: {errors}"
        assert len(results) > 0

    @pytest.mark.integration
    @pytest.mark.asyncio
    async def test_concurrent_scenario_switching(self, adapter):
        """Test concurrent scenario switching operations."""
        scenarios = ["default", "earnings_volatility", "high_price_stock"]

        with patch("app.adapters.test_data.get_sync_session") as mock_session:
            mock_db = MagicMock()
            mock_session.return_value.__enter__.return_value = mock_db

            # Mock scenario objects
            mock_scenarios = []
            for scenario in scenarios:
                mock_scenario = Mock()
                mock_scenario.name = scenario
                mock_scenario.start_date = date(2017, 1, 27)
                mock_scenarios.append(mock_scenario)

            mock_db.query.return_value.filter.return_value.first.side_effect = (
                mock_scenarios
            )

            # Create concurrent scenario switch tasks
            async def switch_scenario_task(scenario):
                await adapter.switch_scenario(scenario)
                return adapter.scenario

            tasks = [switch_scenario_task(scenario) for scenario in scenarios]
            await asyncio.gather(*tasks)

            # Final scenario should be one of the tested scenarios
            assert adapter.scenario in scenarios


class TestDevDataQuoteAdapterErrorHandling:
    """Test error handling in DevDataQuoteAdapter."""

    @pytest.fixture
    def adapter(self):
        """Create adapter for error testing."""
        return DevDataQuoteAdapter()

    @pytest.mark.integration
    def test_database_connection_error_handling(self, adapter):
        """Test handling of database connection errors."""
        with patch("app.adapters.test_data.get_sync_session") as mock_session:
            mock_session.side_effect = SQLAlchemyError("Database connection failed")

            # Health check should handle error gracefully
            health = adapter.health_check()

            assert health["status"] == "error"
            assert "Database connection failed" in health["error"]

    @pytest.mark.integration
    def test_invalid_asset_handling(self, adapter):
        """Test handling of invalid assets."""
        with patch("app.adapters.test_data.asset_factory", return_value=None):
            # Should handle gracefully
            quote = adapter._cached_stock_quote("INVALID", date(2017, 3, 24), "default")
            assert quote is None

    @pytest.mark.integration
    @pytest.mark.asyncio
    async def test_empty_database_handling(self, adapter):
        """Test handling of empty database responses."""
        with patch("app.adapters.test_data.get_sync_session") as mock_session:
            mock_db = MagicMock()
            mock_session.return_value.__enter__.return_value = mock_db

            # Mock empty responses
            mock_db.query.return_value.filter.return_value.first.return_value = None
            mock_db.query.return_value.filter.return_value.all.return_value = []

            # Should handle gracefully
            stock = Stock(symbol="EMPTY", name="Empty Stock")
            quote = await adapter.get_quote(stock)
            assert quote is None

    @pytest.mark.integration
    def test_date_conversion_error_handling(self, adapter):
        """Test handling of date conversion errors."""
        # Test invalid date format
        with pytest.raises(ValueError):
            adapter.set_date("invalid-date-format")

        # Test with None date (edge case)
        adapter.current_date = None
        timestamp = adapter.get_last_updated("AAPL")
        assert timestamp is None

    @pytest.mark.integration
    def test_greeks_calculation_error_handling(self, adapter):
        """Test handling of Greeks calculation errors."""
        with patch("app.adapters.test_data.asset_factory") as mock_factory:
            with patch("app.services.greeks.calculate_option_greeks") as mock_greeks:
                # Setup option
                underlying = Stock(symbol="AAPL", name="Apple Inc.")
                option = Option(
                    symbol="AAPL170324C00150000",
                    underlying=underlying,
                    option_type="CALL",
                    strike=150.0,
                    expiration_date=date(2017, 3, 24),
                )
                mock_factory.return_value = option

                # Mock Greeks calculation to fail
                mock_greeks.side_effect = Exception("Greeks calculation failed")

                with patch.object(adapter, "_get_option_quote_from_db") as mock_db_get:
                    mock_db_quote = Mock()
                    mock_db_quote.bid = Decimal("2.25")
                    mock_db_quote.ask = Decimal("2.75")
                    mock_db_quote.price = Decimal("2.50")
                    mock_db_quote.volume = 500
                    mock_db_quote.quote_date = date(2017, 3, 24)
                    mock_db_get.return_value = mock_db_quote

                    with patch.object(adapter, "_cached_stock_quote") as mock_stock:
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
                        mock_stock.return_value = underlying_quote

                        # Should not raise exception, continue without Greeks
                        quote = adapter._cached_option_quote(
                            "AAPL170324C00150000", date(2017, 3, 24), "default"
                        )

                        assert quote is not None
                        # Greeks should be None since calculation failed
                        assert quote.delta is None


class TestDevDataQuoteAdapterPerformance:
    """Performance tests for DevDataQuoteAdapter."""

    @pytest.fixture
    def adapter(self):
        """Create adapter for performance testing."""
        return DevDataQuoteAdapter()

    @pytest.mark.performance
    @pytest.mark.asyncio
    async def test_batch_quote_performance(self, adapter):
        """Test performance of batch quote operations."""
        symbols = [f"STOCK{i}" for i in range(100)]

        with patch("app.adapters.test_data.get_sync_session") as mock_session:
            mock_db = MagicMock()
            mock_session.return_value.__enter__.return_value = mock_db

            # Mock fast database responses
            mock_db.query.return_value.filter.return_value.all.return_value = []

            import time

            start_time = time.time()

            results = await adapter.batch_get_quotes(symbols)

            end_time = time.time()
            duration = end_time - start_time

            # Should complete quickly even with many symbols
            assert duration < 2.0, f"Batch quotes took {duration} seconds"
            assert isinstance(results, dict)

    @pytest.mark.performance
    def test_cache_performance(self, adapter):
        """Test adapter cache performance."""
        # Populate cache
        import time

        start_time = time.time()

        for i in range(1000):
            key = f"perf_test_key_{i}"
            value = f"perf_test_value_{i}"
            adapter._quote_cache[key] = value

        populate_time = time.time() - start_time

        # Access cache entries
        start_time = time.time()

        for i in range(1000):
            key = f"perf_test_key_{i}"
            value = adapter._quote_cache.get(key)
            assert value is not None

        access_time = time.time() - start_time

        # Should be very fast
        assert populate_time < 1.0, f"Cache population took {populate_time} seconds"
        assert access_time < 0.5, f"Cache access took {access_time} seconds"

    @pytest.mark.performance
    def test_date_switching_performance(self, adapter):
        """Test performance of date switching operations."""
        dates = ["2017-01-27", "2017-01-28", "2017-03-24", "2017-03-25"]

        import time

        start_time = time.time()

        for date_str in dates * 10:  # Repeat for more operations
            adapter.set_date(date_str)

        end_time = time.time()
        duration = end_time - start_time

        # Should complete quickly
        assert duration < 1.0, f"Date switching took {duration} seconds"


class TestGetTestAdapterIntegration:
    """Integration tests for get_test_adapter convenience function."""

    def test_get_test_adapter_default_integration(self):
        """Test get_test_adapter with default parameters."""
        adapter = get_test_adapter()

        assert isinstance(adapter, DevDataQuoteAdapter)
        assert adapter.current_date == date(2017, 3, 24)
        assert adapter.scenario == "default"

    def test_get_test_adapter_custom_integration(self):
        """Test get_test_adapter with custom parameters."""
        adapter = get_test_adapter(date="2017-01-27", scenario="earnings_volatility")

        assert adapter.current_date == date(2017, 1, 27)
        assert adapter.scenario == "earnings_volatility"

    def test_get_test_adapter_multiple_instances(self):
        """Test that get_test_adapter creates independent instances."""
        adapter1 = get_test_adapter(date="2017-01-27")
        adapter2 = get_test_adapter(date="2017-03-24")

        assert adapter1 is not adapter2
        assert adapter1.current_date != adapter2.current_date

    @pytest.mark.integration
    def test_get_test_adapter_functional_integration(self):
        """Test that get_test_adapter returns functional adapter."""
        adapter = get_test_adapter()

        # Test that basic functionality works
        scenarios = adapter.get_test_scenarios()
        assert isinstance(scenarios, dict)

        info = adapter.get_sample_data_info()
        assert isinstance(info, dict)
        assert "description" in info
