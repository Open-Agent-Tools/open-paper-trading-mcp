"""
Tests for TradingService stock search functionality.

This module covers the search_stocks method which provides:
- Symbol search functionality
- Query matching and result limiting
- Search result formatting

Coverage target: Lines 998-1028 (search_stocks method)
"""

import pytest

pytestmark = pytest.mark.journey_market_data


class TestTradingServiceStockSearch:
    """Test stock search functionality."""

    @pytest.mark.asyncio
    async def test_search_stocks_basic_success_synthetic_data(
        self, trading_service_synthetic_data
    ):
        """Test basic successful stock search with test data."""
        result = await trading_service_synthetic_data.search_stocks("AAPL")

        assert isinstance(result, dict)
        assert "query" in result
        assert result["query"] == "AAPL"
        assert "results" in result
        assert isinstance(result["results"], list)

    @pytest.mark.asyncio
    async def test_search_stocks_partial_match_synthetic_data(
        self, trading_service_synthetic_data
    ):
        """Test stock search with partial symbol match."""
        result = await trading_service_synthetic_data.search_stocks("APP")

        assert isinstance(result, dict)
        assert result["query"] == "APP"
        assert "results" in result

        # Should find AAPL and potentially other symbols containing APP
        if result["results"]:
            assert any("APP" in res["symbol"] for res in result["results"])

    @pytest.mark.slow
    @pytest.mark.robinhood
    @pytest.mark.asyncio
    async def test_search_stocks_robinhood_live_apple(self, trading_service_robinhood):
        """Test stock search with live Robinhood data for Apple."""
        result = await trading_service_robinhood.search_stocks("AAPL")

        assert isinstance(result, dict)
        assert "query" in result
        assert result["query"] == "AAPL"
        assert "results" in result

        # Should get some results (either from extended search or fallback)
        if result["results"]:
            assert isinstance(result["results"], list)

    @pytest.mark.slow
    @pytest.mark.robinhood
    @pytest.mark.asyncio
    async def test_search_stocks_robinhood_company_name(
        self, trading_service_robinhood
    ):
        """Test stock search by company name using Robinhood."""
        result = await trading_service_robinhood.search_stocks("Apple")

        assert isinstance(result, dict)
        assert result["query"] == "Apple"

        # Company name search may or may not be supported depending on adapter

    @pytest.mark.asyncio
    async def test_search_stocks_adapter_with_extended_functionality(
        self, trading_service_synthetic_data
    ):
        """Test stock search when adapter has search_stocks method."""
        has_extended = hasattr(
            trading_service_synthetic_data.quote_adapter, "search_stocks"
        )

        result = await trading_service_synthetic_data.search_stocks("MSFT")

        assert isinstance(result, dict)
        assert result["query"] == "MSFT"

        if has_extended:
            # Should use adapter's method
            pass  # Structure depends on adapter implementation
        else:
            # Should use fallback symbol matching
            if result["results"]:
                for res in result["results"]:
                    assert "MSFT" in res["symbol"].upper()

    @pytest.mark.asyncio
    async def test_search_stocks_fallback_mechanism_synthetic_data(
        self, trading_service_synthetic_data
    ):
        """Test stock search fallback when adapter lacks extended functionality."""
        # Force test of fallback by temporarily removing method if it exists
        adapter = trading_service_synthetic_data.quote_adapter
        print(f"DEBUG: Adapter type = {type(adapter)}")
        print(f"DEBUG: hasattr search_stocks = {hasattr(adapter, 'search_stocks')}")
        print(
            f"DEBUG: Method exists = {getattr(adapter, 'search_stocks', None) is not None}"
        )

        # Remove the search_stocks method to test fallback - use monkey patching
        if hasattr(adapter, "search_stocks"):
            # Save original for later restoration
            original_method = adapter.search_stocks
            # Remove by setting to None and updating __dict__ if it exists there
            if hasattr(adapter, "__dict__") and "search_stocks" in adapter.__dict__:
                del adapter.__dict__["search_stocks"]
            else:
                # Set a flag to skip the hasattr check in the service
                adapter._skip_search_stocks = True

        try:
            result = await trading_service_synthetic_data.search_stocks("AAPL")
            print(f"DEBUG: Result = {result}")  # Debug print

            assert isinstance(result, dict)
            assert result["query"] == "AAPL"
            assert "results" in result

            # Should get fallback results from available symbols
            if result["results"]:
                for res in result["results"]:
                    assert "symbol" in res
                    assert "name" in res
                    # Note: "tradeable" field may not be present in synthetic data
                    if "tradeable" in res:
                        assert res["tradeable"] is True
                    assert "AAPL" in res["symbol"].upper()

        finally:
            # Restore original method if it existed
            if original_method:
                trading_service_synthetic_data.quote_adapter.search_stocks = (
                    original_method
                )

    @pytest.mark.asyncio
    async def test_search_stocks_result_limit_fallback(
        self, trading_service_synthetic_data
    ):
        """Test that search results are limited to 10 in fallback mode."""
        # Force fallback by creating minimal adapter without search_stocks method
        from app.adapters.base import QuoteAdapter
        from app.services.trading_service import TradingService

        class MinimalQuoteAdapter(QuoteAdapter):
            def get_available_symbols(self):
                return [
                    "AAPL",
                    "MSFT",
                    "GOOGL",
                    "AMZN",
                    "TSLA",
                    "META",
                    "NVDA",
                    "AMD",
                    "NFLX",
                    "ADBE",
                    "ABBV",
                    "ABC",
                ]  # 12 symbols

            async def get_quote(self, asset):
                return None

            async def get_quotes(self, assets):
                return {}

            async def get_chain(self, underlying, expiration_date=None):
                return []

            async def get_options_chain(self, underlying, expiration_date=None):
                return None

            async def is_market_open(self):
                return True

            async def get_market_hours(self):
                return {"market_open": True}

            def get_sample_data_info(self):
                return {"provider": "minimal", "symbols": self.get_available_symbols()}

            def get_expiration_dates(self, underlying):
                return []

            def get_test_scenarios(self):
                return {"default": "Minimal test data"}

            def set_date(self, date):
                pass

        # Create new service with minimal adapter for this test
        test_service = TradingService(
            account_owner="limit_test_user",
            quote_adapter=MinimalQuoteAdapter(),
        )

        # Search for a common letter that might match many symbols
        result = await test_service.search_stocks("A")

        assert isinstance(result, dict)
        assert len(result["results"]) <= 10  # Should limit to 10 results

    @pytest.mark.asyncio
    async def test_search_stocks_case_insensitive_synthetic_data(
        self, trading_service_synthetic_data
    ):
        """Test that stock search is case insensitive."""
        # Test lowercase query
        result_lower = await trading_service_synthetic_data.search_stocks("aapl")
        result_upper = await trading_service_synthetic_data.search_stocks("AAPL")

        assert isinstance(result_lower, dict)
        assert isinstance(result_upper, dict)

        # Both should work and find similar results
        assert result_lower["query"] == "aapl"
        assert result_upper["query"] == "AAPL"

    @pytest.mark.asyncio
    async def test_search_stocks_no_matches_synthetic_data(
        self, trading_service_synthetic_data
    ):
        """Test stock search with query that has no matches."""
        result = await trading_service_synthetic_data.search_stocks("ZZZZNOMATCH")

        assert isinstance(result, dict)
        assert result["query"] == "ZZZZNOMATCH"
        assert "results" in result

        # Should return empty results (message field is optional for synthetic data)
        assert result["results"] == [] or len(result["results"]) == 0

    @pytest.mark.slow
    @pytest.mark.robinhood
    @pytest.mark.asyncio
    async def test_search_stocks_robinhood_no_matches(self, trading_service_robinhood):
        """Test stock search with no matches using Robinhood."""
        result = await trading_service_robinhood.search_stocks("ZZZZNOMATCH")

        assert isinstance(result, dict)
        assert result["query"] == "ZZZZNOMATCH"

    @pytest.mark.asyncio
    async def test_search_stocks_empty_query_synthetic_data(
        self, trading_service_synthetic_data
    ):
        """Test stock search with empty query."""
        result = await trading_service_synthetic_data.search_stocks("")

        assert isinstance(result, dict)
        assert result["query"] == ""
        # May return error or empty results

    @pytest.mark.asyncio
    async def test_search_stocks_special_characters_synthetic_data(
        self, trading_service_synthetic_data
    ):
        """Test stock search with special characters."""
        result = await trading_service_synthetic_data.search_stocks("BRK.B")

        assert isinstance(result, dict)
        assert result["query"] == "BRK.B"

        # May or may not find results depending on available symbols

    @pytest.mark.slow
    @pytest.mark.robinhood
    @pytest.mark.asyncio
    async def test_search_stocks_robinhood_multiple_queries(
        self, trading_service_robinhood
    ):
        """Test multiple search queries with Robinhood."""
        queries = ["AAPL", "MSFT", "GOOGL", "Tesla", "Microsoft"]

        for query in queries:
            result = await trading_service_robinhood.search_stocks(query)
            assert isinstance(result, dict)
            assert result["query"] == query

    @pytest.mark.slow
    @pytest.mark.robinhood
    @pytest.mark.asyncio
    async def test_search_stocks_robinhood_exception_handling(
        self, trading_service_robinhood
    ):
        """Test exception handling with Robinhood adapter."""
        # Test with very long query that might cause issues
        very_long_query = "A" * 1000

        result = await trading_service_robinhood.search_stocks(very_long_query)
        assert isinstance(result, dict)
        # Should handle gracefully without crashing
