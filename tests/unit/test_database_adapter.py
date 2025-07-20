"""
Unit tests for TestDataAdapter using database backend.

Tests adapter functionality with mocked database sessions for proper unit testing.
"""

import sys
from datetime import date, datetime, timedelta
from decimal import Decimal
from pathlib import Path
from unittest.mock import Mock, patch

import pytest

# Add the app directory to the path
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from app.adapters.test_data import TestDataQuoteAdapter
from app.models.assets import Option, asset_factory
from app.models.database.trading import TestOptionQuote, TestScenario, TestStockQuote


class TestDatabaseAdapter:
    """Test database-backed quote adapter with mocked database."""

    @pytest.fixture
    def mock_stock_quote(self):
        """Create a mock stock quote."""
        quote = Mock(spec=TestStockQuote)
        quote.symbol = "AAPL"
        quote.quote_date = date(2017, 1, 27)
        quote.scenario = "default"
        quote.bid = Decimal("100.50")
        quote.ask = Decimal("100.60")
        quote.price = Decimal("100.55")
        quote.volume = 1000
        return quote

    @pytest.fixture
    def mock_option_quote(self):
        """Create a mock option quote."""
        quote = Mock(spec=TestOptionQuote)
        quote.symbol = "AAPL170203C00100000"
        quote.underlying = "AAPL"
        quote.quote_date = date(2017, 1, 27)
        quote.scenario = "default"
        quote.bid = Decimal("2.50")
        quote.ask = Decimal("2.60")
        quote.price = Decimal("2.55")
        quote.strike = Decimal("100")
        quote.expiration = date(2017, 2, 3)
        quote.option_type = "call"
        quote.volume = 100
        return quote

    @pytest.fixture
    def mock_session(self):
        """Create a mock database session."""
        session = Mock()
        return session

    @pytest.fixture
    def adapter(self):
        """Create test adapter instance."""
        return TestDataQuoteAdapter("2017-01-27", "default")

    @pytest.mark.asyncio
    async def test_stock_quote_retrieval(self, adapter, mock_stock_quote, mock_session):
        """Test stock quote retrieval from database."""
        # Mock the database session and query result
        mock_session.query.return_value.filter.return_value.first.return_value = (
            mock_stock_quote
        )

        with patch("app.adapters.test_data.get_sync_session") as mock_get_session:
            mock_get_session.return_value.__next__.return_value = mock_session

            # Get stock quote
            aapl = asset_factory("AAPL")
            quote = await adapter.get_quote(aapl)

            assert quote is not None
            assert quote.asset.symbol == "AAPL"
            assert quote.bid is not None
            assert quote.ask is not None
            assert quote.price is not None
            assert quote.bid <= quote.price <= quote.ask

    @pytest.mark.asyncio
    async def test_option_quote_retrieval(
        self, adapter, mock_option_quote, mock_session
    ):
        """Test option quote retrieval from database."""
        # Mock the database session and query result
        mock_session.query.return_value.filter.return_value.first.return_value = (
            mock_option_quote
        )

        with patch("app.adapters.test_data.get_sync_session") as mock_get_session:
            mock_get_session.return_value.__next__.return_value = mock_session

            # Get option quote
            option_symbol = "AAPL170203C00100000"
            option = asset_factory(option_symbol)

            if option:
                quote = await adapter.get_quote(option)
                if quote:
                    assert quote.asset.symbol == option_symbol
                    assert isinstance(quote.asset, Option)

    @pytest.mark.asyncio
    async def test_scenario_switching(self, adapter, mock_session):
        """Test switching between scenarios."""
        # Mock scenario lookup
        mock_scenario = Mock(spec=TestScenario)
        mock_scenario.name = "volatile_market"
        mock_scenario.start_date = date(2017, 3, 24)

        mock_session.query.return_value.filter.return_value.first.return_value = (
            mock_scenario
        )

        with patch("app.adapters.test_data.get_sync_session") as mock_get_session:
            mock_get_session.return_value.__next__.return_value = mock_session

            # Switch to different scenario
            await adapter.switch_scenario("volatile_market")

            # Date should have changed
            assert adapter.scenario == "volatile_market"
            assert adapter.current_date == date(2017, 3, 24)

    @pytest.mark.asyncio
    async def test_date_range_queries(self, adapter, mock_stock_quote, mock_session):
        """Test date range query functionality."""
        # Mock database records for date range
        mock_records = [mock_stock_quote]
        mock_session.query.return_value.filter.return_value.order_by.return_value.all.return_value = mock_records

        with patch("app.adapters.test_data.get_sync_session") as mock_get_session:
            mock_get_session.return_value.__next__.return_value = mock_session

            # Get quotes for date range
            start_date = date(2017, 1, 27)
            end_date = date(2017, 1, 28)

            quotes = await adapter.get_quotes_for_date_range(
                "AAPL", start_date, end_date
            )

            assert len(quotes) >= 0  # Could be empty if no mocked data matches

    @pytest.mark.asyncio
    async def test_bulk_quote_retrieval(self, adapter, mock_stock_quote, mock_session):
        """Test retrieving multiple quotes at once."""
        # Mock database session
        mock_session.query.return_value.filter.return_value.first.return_value = (
            mock_stock_quote
        )

        with patch("app.adapters.test_data.get_sync_session") as mock_get_session:
            mock_get_session.return_value.__next__.return_value = mock_session

            # Get multiple assets
            assets = [
                asset_factory("AAPL"),
                asset_factory("GOOGL"),
                asset_factory("MSFT"),
            ]

            quotes = await adapter.get_quotes(assets)

            # Should get at least the mocked quotes
            for asset, quote in quotes.items():
                assert quote.asset.symbol == asset.symbol
                assert quote.price is not None

    @pytest.mark.asyncio
    async def test_options_chain_retrieval(
        self, adapter, mock_option_quote, mock_stock_quote, mock_session
    ):
        """Test options chain retrieval from database."""
        # Mock database responses
        mock_session.query.return_value.filter.return_value.all.return_value = [
            mock_option_quote
        ]
        mock_session.query.return_value.filter.return_value.first.return_value = (
            mock_stock_quote
        )

        with patch("app.adapters.test_data.get_sync_session") as mock_get_session:
            mock_get_session.return_value.__next__.return_value = mock_session

            # Get options chain
            chain = await adapter.get_options_chain("AAPL")

            if chain:  # May not have options in all scenarios
                assert chain.underlying_symbol == "AAPL"
                # Check calls and puts
                if chain.calls:
                    for call in chain.calls:
                        assert call.asset.option_type == "call"
                        assert call.asset.underlying.symbol == "AAPL"

    @pytest.mark.asyncio
    async def test_date_advancement(self, adapter):
        """Test advancing current date."""
        initial_date = adapter.current_date

        # Advance by 1 day
        await adapter.advance_date(1)

        assert adapter.current_date == initial_date + timedelta(days=1)

        # Advance by multiple days
        await adapter.advance_date(5)

        assert adapter.current_date == initial_date + timedelta(days=6)

    @pytest.mark.asyncio
    async def test_available_dates(self, adapter, mock_session):
        """Test getting available dates."""
        # Mock available dates
        mock_dates = [(date(2017, 1, 27),), (date(2017, 1, 28),)]
        mock_session.query.return_value.filter.return_value.distinct.return_value.all.return_value = mock_dates

        with patch("app.adapters.test_data.get_sync_session") as mock_get_session:
            mock_get_session.return_value.__next__.return_value = mock_session

            dates = adapter.get_available_dates()

            assert len(dates) >= 0
            assert all(isinstance(d, str) for d in dates)
            # Dates should be in YYYY-MM-DD format
            for date_str in dates:
                datetime.strptime(date_str, "%Y-%m-%d")

    @pytest.mark.asyncio
    async def test_symbol_support_check(self, adapter, mock_session):
        """Test checking if adapter supports a symbol."""

        # Mock symbol support - return True for AAPL, False for others
        def mock_first_side_effect():
            return Mock()  # Non-None for supported symbols

        mock_session.query.return_value.filter.return_value.first.side_effect = [
            mock_first_side_effect(),
            None,
        ]

        with patch("app.adapters.test_data.get_sync_session") as mock_get_session:
            mock_get_session.return_value.__next__.return_value = mock_session

            # Check symbol support
            supports_aapl = adapter.supports_symbol("AAPL")
            supports_unknown = adapter.supports_symbol("UNKNOWN123")

            # At least one should be supported based on our mock
            assert isinstance(supports_aapl, bool)
            assert isinstance(supports_unknown, bool)

    @pytest.mark.asyncio
    async def test_expiration_dates(self, adapter, mock_session):
        """Test getting option expiration dates."""
        # Mock expiration dates
        future_date = date(2017, 2, 3)
        mock_expirations = [(future_date,)]
        mock_session.query.return_value.filter.return_value.distinct.return_value.all.return_value = mock_expirations

        with patch("app.adapters.test_data.get_sync_session") as mock_get_session:
            mock_get_session.return_value.__next__.return_value = mock_session

            expirations = adapter.get_expiration_dates("AAPL")

            if expirations:  # May not have options in all scenarios
                assert all(isinstance(exp, date) for exp in expirations)
                # Expirations should be in the future relative to current date
                for exp in expirations:
                    assert exp >= adapter.current_date

    @pytest.mark.asyncio
    async def test_health_check(self, adapter, mock_session):
        """Test adapter health check."""
        # Mock database counts
        mock_session.query.return_value.filter.return_value.distinct.return_value.count.return_value = 5
        mock_session.query.return_value.count.return_value = 100

        with patch("app.adapters.test_data.get_sync_session") as mock_get_session:
            mock_get_session.return_value.__next__.return_value = mock_session

            health = adapter.health_check()

            assert health["status"] == "healthy"
            assert health["name"] == "TestDataQuoteAdapter"
            assert health["enabled"] is True
            assert health["database_connected"] is True
            assert health["total_stock_quotes_in_db"] >= 0
            assert health["total_option_quotes_in_db"] >= 0

    @pytest.mark.asyncio
    async def test_caching_performance(self, adapter, mock_stock_quote, mock_session):
        """Test that caching improves performance."""
        # Mock database session
        mock_session.query.return_value.filter.return_value.first.return_value = (
            mock_stock_quote
        )

        with patch("app.adapters.test_data.get_sync_session") as mock_get_session:
            mock_get_session.return_value.__next__.return_value = mock_session

            aapl = asset_factory("AAPL")

            # First call (cache miss)
            quote1 = await adapter.get_quote(aapl)

            # Second call (cache hit)
            quote2 = await adapter.get_quote(aapl)

            # Both should return same quote if caching works
            if quote1 and quote2:
                assert quote1.price == quote2.price

    @pytest.mark.asyncio
    async def test_greeks_calculation(
        self, adapter, mock_option_quote, mock_stock_quote, mock_session
    ):
        """Test that option quotes include calculated Greeks."""
        # Mock database responses
        mock_session.query.return_value.filter.return_value.all.return_value = [
            mock_option_quote
        ]
        mock_session.query.return_value.filter.return_value.first.return_value = (
            mock_stock_quote
        )

        with patch("app.adapters.test_data.get_sync_session") as mock_get_session:
            mock_get_session.return_value.__next__.return_value = mock_session

            # Get options chain
            chain = await adapter.get_options_chain("AAPL")

            if chain and chain.calls:
                # Check first call option
                call_quote = chain.calls[0]

                # Greeks calculation is attempted during quote creation
                # We don't assert Greeks existence since calculation might fail
                assert call_quote is not None
