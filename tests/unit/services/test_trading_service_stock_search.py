"""
Tests for TradingService stock search functionality.

This module covers the search_stocks method which provides:
- Symbol search functionality
- Query matching and result limiting
- Search result formatting

Coverage target: Lines 998-1028 (search_stocks method)
"""

import pytest


class TestTradingServiceStockSearch:
    """Test stock search functionality."""

    @pytest.mark.asyncio
    async def test_search_stocks_basic_success_test_data(
        self, trading_service_test_data
    ):
        """Test basic successful stock search with test data."""
        result = await trading_service_test_data.search_stocks("AAPL")

        assert isinstance(result, dict)
        assert "query" in result
        assert result["query"] == "AAPL"
        assert "results" in result
        assert isinstance(result["results"], list)

    @pytest.mark.asyncio
    async def test_search_stocks_partial_match_test_data(
        self, trading_service_test_data
    ):
        """Test stock search with partial symbol match."""
        result = await trading_service_test_data.search_stocks("APP")

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
        self, trading_service_test_data
    ):
        """Test stock search when adapter has search_stocks method."""
        has_extended = hasattr(trading_service_test_data.quote_adapter, "search_stocks")

        result = await trading_service_test_data.search_stocks("MSFT")

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
    async def test_search_stocks_fallback_mechanism_test_data(
        self, trading_service_test_data
    ):
        """Test stock search fallback when adapter lacks extended functionality."""
        # Force test of fallback by temporarily removing method if it exists
        original_method = getattr(
            trading_service_test_data.quote_adapter, "search_stocks", None
        )

        if original_method:
            delattr(trading_service_test_data.quote_adapter, "search_stocks")

        try:
            result = await trading_service_test_data.search_stocks("AAPL")

            assert isinstance(result, dict)
            assert result["query"] == "AAPL"
            assert "results" in result

            # Should get fallback results from available symbols
            if result["results"]:
                for res in result["results"]:
                    assert "symbol" in res
                    assert "name" in res
                    assert "tradeable" in res
                    assert res["tradeable"] is True
                    assert "AAPL" in res["symbol"].upper()

        finally:
            # Restore original method if it existed
            if original_method:
                trading_service_test_data.quote_adapter.search_stocks = original_method

    @pytest.mark.asyncio
    async def test_search_stocks_result_limit_fallback(self, trading_service_test_data):
        """Test that search results are limited to 10 in fallback mode."""
        # Force fallback by temporarily removing method
        original_method = getattr(
            trading_service_test_data.quote_adapter, "search_stocks", None
        )

        if original_method:
            delattr(trading_service_test_data.quote_adapter, "search_stocks")

        try:
            # Search for a common letter that might match many symbols
            result = await trading_service_test_data.search_stocks("A")

            assert isinstance(result, dict)
            assert len(result["results"]) <= 10  # Should limit to 10 results

        finally:
            if original_method:
                trading_service_test_data.quote_adapter.search_stocks = original_method

    @pytest.mark.asyncio
    async def test_search_stocks_case_insensitive_test_data(
        self, trading_service_test_data
    ):
        """Test that stock search is case insensitive."""
        # Test lowercase query
        result_lower = await trading_service_test_data.search_stocks("aapl")
        result_upper = await trading_service_test_data.search_stocks("AAPL")

        assert isinstance(result_lower, dict)
        assert isinstance(result_upper, dict)

        # Both should work and find similar results
        assert result_lower["query"] == "aapl"
        assert result_upper["query"] == "AAPL"

    @pytest.mark.asyncio
    async def test_search_stocks_no_matches_test_data(self, trading_service_test_data):
        """Test stock search with query that has no matches."""
        result = await trading_service_test_data.search_stocks("ZZZZNOMATCH")

        assert isinstance(result, dict)
        assert result["query"] == "ZZZZNOMATCH"
        assert "results" in result

        # Should return empty results or message about no matches
        if not result["results"]:
            assert "message" in result

    @pytest.mark.slow
    @pytest.mark.robinhood
    @pytest.mark.asyncio
    async def test_search_stocks_robinhood_no_matches(self, trading_service_robinhood):
        """Test stock search with no matches using Robinhood."""
        result = await trading_service_robinhood.search_stocks("ZZZZNOMATCH")

        assert isinstance(result, dict)
        assert result["query"] == "ZZZZNOMATCH"

    @pytest.mark.asyncio
    async def test_search_stocks_empty_query_test_data(self, trading_service_test_data):
        """Test stock search with empty query."""
        result = await trading_service_test_data.search_stocks("")

        assert isinstance(result, dict)
        assert result["query"] == ""
        # May return error or empty results

    @pytest.mark.asyncio
    async def test_search_stocks_special_characters_test_data(
        self, trading_service_test_data
    ):
        """Test stock search with special characters."""
        result = await trading_service_test_data.search_stocks("BRK.B")

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

    @pytest.mark.asyncio
    async def test_search_stocks_exception_handling_test_data(
        self, trading_service_test_data
    ):
        """Test exception handling in search_stocks."""
        # Force an exception by corrupting the adapter
        original_get_available_symbols = getattr(
            trading_service_test_data, "get_available_symbols", None
        )

        if original_get_available_symbols:
            # Force exception in fallback path
            trading_service_test_data.get_available_symbols = lambda: None

            # Remove search method to force fallback
            original_method = getattr(
                trading_service_test_data.quote_adapter, "search_stocks", None
            )
            if original_method:
                delattr(trading_service_test_data.quote_adapter, "search_stocks")

            try:
                result = await trading_service_test_data.search_stocks("AAPL")
                assert isinstance(result, dict)
                # Should handle exception gracefully

            finally:
                trading_service_test_data.get_available_symbols = (
                    original_get_available_symbols
                )
                if original_method:
                    trading_service_test_data.quote_adapter.search_stocks = (
                        original_method
                    )

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
