"""
Comprehensive unit tests for MCP options tools.

Tests async options tools, parameter validation, TradingService integration,
error handling, and response formatting for options data operations.
"""

from unittest.mock import AsyncMock, Mock, patch

import pytest

from app.mcp.options_tools import (
    aggregate_option_positions,
    all_option_positions,
    find_options,
    get_mcp_trading_service,
    open_option_positions,
    option_historicals,
    option_market_data,
    options_chains,
    set_mcp_trading_service,
)


@pytest.fixture
def mock_trading_service():
    """Create a mock trading service for tests."""
    mock_service = Mock()
    # Set up common async methods
    mock_service.get_formatted_options_chain = AsyncMock()
    mock_service.find_tradable_options = AsyncMock()
    mock_service.get_option_market_data = AsyncMock()
    mock_service.get_positions = AsyncMock()
    mock_service.get_enhanced_quote = AsyncMock()
    mock_service.get_quote = AsyncMock()

    # Set the mock service for MCP tools
    set_mcp_trading_service(mock_service)

    yield mock_service

    # Clean up - set to None after test
    from app.mcp import options_tools

    options_tools._trading_service = None


class TestOptionsToolsParameterValidation:
    """Test parameter validation for options tool functions."""

    @pytest.mark.asyncio
    async def test_options_chains_parameter_validation(self, mock_trading_service):
        """Test options_chains parameter validation."""
        # Test with valid symbol
        mock_trading_service.get_formatted_options_chain.return_value = {"test": "data"}
        result = await options_chains("AAPL")
        assert result["result"]["status"] == "success"

        # Test with empty symbol (should still call service, error handling at service level)
        result = await options_chains("")
        assert "result" in result

    @pytest.mark.asyncio
    async def test_find_options_parameter_validation(self, mock_trading_service):
        """Test find_options parameter validation."""
        mock_trading_service.find_tradable_options.return_value = {"test": "data"}

        # Test with all parameters
        result = await find_options("AAPL", "2024-12-20", "call")
        assert result["result"]["status"] == "success"

        # Test with optional None parameters
        result = await find_options("AAPL", None, None)
        assert result["result"]["status"] == "success"

    @pytest.mark.asyncio
    async def test_option_market_data_parameter_validation(self, mock_trading_service):
        """Test option_market_data parameter validation."""
        mock_trading_service.get_option_market_data.return_value = {"test": "data"}

        # Test with valid option ID
        result = await option_market_data("AAPL240119C00195000")
        assert result["result"]["status"] == "success"


class TestOptionsToolFunctions:
    """Test individual options tool functions."""

    @pytest.mark.asyncio
    async def test_options_chains_success(self, mock_trading_service):
        """Test successful options chain retrieval."""
        mock_result = {
            "underlying_symbol": "AAPL",
            "expiration_dates": ["2024-12-20", "2025-01-17"],
            "chains": {
                "2024-12-20": {
                    "calls": [
                        {
                            "strike": 150.0,
                            "symbol": "AAPL241220C00150000",
                            "bid": 5.25,
                            "ask": 5.50,
                        }
                    ],
                    "puts": [
                        {
                            "strike": 150.0,
                            "symbol": "AAPL241220P00150000",
                            "bid": 2.10,
                            "ask": 2.25,
                        }
                    ],
                }
            },
        }

        mock_trading_service.get_formatted_options_chain.return_value = mock_result

        result = await options_chains("AAPL")

        # Expect standardized response format
        assert result["result"]["status"] == "success"
        assert result["result"]["data"] == mock_result
        mock_trading_service.get_formatted_options_chain.assert_called_once_with("AAPL")

    @pytest.mark.asyncio
    async def test_find_options_success(self, mock_trading_service):
        """Test successful tradable options search."""
        mock_result = {
            "symbol": "AAPL",
            "options": [
                {
                    "symbol": "AAPL241220C00150000",
                    "strike": 150.0,
                    "expiration_date": "2024-12-20",
                    "option_type": "call",
                    "bid": 5.25,
                    "ask": 5.50,
                }
            ],
            "count": 1,
        }

        mock_trading_service.find_tradable_options.return_value = mock_result

        result = await find_options("aapl", "2024-12-20", "call")

        assert result["result"]["status"] == "success"
        assert result["result"]["data"] == mock_result
        mock_trading_service.find_tradable_options.assert_called_once_with(
            "AAPL", "2024-12-20", "call"
        )

    @pytest.mark.asyncio
    async def test_option_market_data_success(self, mock_trading_service):
        """Test successful option market data retrieval."""
        mock_result = {
            "option_id": "AAPL241220C00150000",
            "underlying_symbol": "AAPL",
            "strike": 150.0,
            "expiration_date": "2024-12-20",
            "option_type": "call",
            "bid": 5.25,
            "ask": 5.50,
            "last_price": 5.40,
            "volume": 1000,
            "open_interest": 5000,
            "implied_volatility": 0.25,
            "greeks": {
                "delta": 0.65,
                "gamma": 0.02,
                "theta": -0.15,
                "vega": 0.12,
                "rho": 0.08,
            },
        }

        mock_trading_service.get_option_market_data.return_value = mock_result

        result = await option_market_data("AAPL241220C00150000")

        assert result["result"]["status"] == "success"
        assert result["result"]["data"] == mock_result
        mock_trading_service.get_option_market_data.assert_called_once_with(
            "AAPL241220C00150000"
        )

    @pytest.mark.asyncio
    async def test_option_historicals_success(self, mock_trading_service):
        """Test successful option historical data retrieval."""
        # Mock the get_quote method to return a price
        mock_quote = Mock()
        mock_quote.price = 150.0
        mock_trading_service.get_quote.return_value = mock_quote

        result = await option_historicals(
            "AAPL", "2024-12-20", 150.0, "call", "day", "week"
        )

        assert result["result"]["status"] == "success"
        data = result["result"]["data"]
        assert "option_symbol" in data
        assert "underlying_symbol" in data
        assert data["underlying_symbol"] == "AAPL"
        assert data["strike_price"] == 150.0
        assert data["option_type"] == "call"
        assert "data" in data
        assert len(data["data"]) > 0
        assert data["interval"] == "day"
        assert data["span"] == "week"

    @pytest.mark.asyncio
    async def test_option_historicals_with_adapter_data(self, mock_trading_service):
        """Test option historicals with live adapter data."""
        # Mock adapter with historical data capability
        mock_adapter = Mock()
        mock_adapter.get_option_historicals = AsyncMock(
            return_value=[
                {"timestamp": "2024-01-01T10:00:00", "price": 5.25, "volume": 100}
            ]
        )
        mock_trading_service.quote_adapter = mock_adapter

        result = await option_historicals(
            "AAPL", "2024-12-20", 150.0, "call", "hour", "day"
        )

        assert result["result"]["status"] == "success"
        data = result["result"]["data"]
        assert data["data_source"] == "live_adapter"
        assert len(data["data"]) == 1

    @pytest.mark.asyncio
    async def test_aggregate_option_positions_success(self, mock_trading_service):
        """Test successful aggregate option positions retrieval."""
        # Mock positions data with option position
        mock_position = Mock()
        mock_position.symbol = "AAPL241220C00150000"
        mock_position.quantity = 2
        mock_position.current_price = 5.50
        mock_position.unrealized_pnl = 100.0

        mock_positions = [mock_position]
        mock_trading_service.get_positions.return_value = mock_positions

        # Mock asset factory and enhanced quote
        with patch("app.mcp.options_tools.asset_factory") as mock_factory:
            mock_option = Mock()
            mock_option.underlying.symbol = "AAPL"
            mock_option.strike = 150.0
            mock_option.expiration_date.isoformat.return_value = "2024-12-20"
            mock_option.option_type = "CALL"
            mock_option.get_days_to_expiration.return_value = 30
            mock_factory.return_value = mock_option

            # Mock isinstance to return True for Option
            with patch("builtins.isinstance", return_value=True):
                mock_enhanced_quote = Mock()
                mock_enhanced_quote.delta = 0.65
                mock_enhanced_quote.gamma = 0.02
                mock_enhanced_quote.theta = -0.15
                mock_enhanced_quote.vega = 0.12
                mock_enhanced_quote.rho = 0.08
                mock_trading_service.get_enhanced_quote.return_value = (
                    mock_enhanced_quote
                )

                result = await aggregate_option_positions()

                assert result["result"]["status"] == "success"
                data = result["result"]["data"]
                assert "total_option_positions" in data
                assert "portfolio_greeks" in data
                assert "positions" in data
                assert data["total_option_positions"] == 1

    @pytest.mark.asyncio
    async def test_aggregate_option_positions_with_no_options(
        self, mock_trading_service
    ):
        """Test aggregate positions with no option positions."""
        mock_positions = []
        mock_trading_service.get_positions.return_value = mock_positions

        result = await aggregate_option_positions()

        assert result["result"]["status"] == "success"
        data = result["result"]["data"]
        assert data["total_option_positions"] == 0
        assert data["total_market_value"] == 0.0

    @pytest.mark.asyncio
    async def test_all_option_positions_success(self, mock_trading_service):
        """Test successful all option positions retrieval."""
        mock_positions = []

        mock_trading_service.get_positions.return_value = mock_positions

        result = await all_option_positions()

        assert result["result"]["status"] == "success"
        data = result["result"]["data"]
        assert "total_positions" in data
        assert "positions" in data

    @pytest.mark.asyncio
    async def test_open_option_positions_success(self, mock_trading_service):
        """Test successful open option positions retrieval."""
        # Mock the all_option_positions call
        mock_all_result = {
            "positions": [
                {"symbol": "AAPL241220C00150000", "status": "open", "quantity": 1},
                {"symbol": "AAPL241220P00150000", "status": "closed", "quantity": 0},
            ]
        }

        with patch(
            "app.mcp.options_tools.all_option_positions", new_callable=AsyncMock
        ) as mock_all:
            mock_all.return_value = {
                "result": {"status": "success", "data": mock_all_result}
            }

            result = await open_option_positions()

            assert result["result"]["status"] == "success"
            data = result["result"]["data"]
            assert "total_open_positions" in data
            assert "positions" in data
            # Should only contain open positions
            open_positions = [p for p in data["positions"] if p.get("status") == "open"]
            assert len(open_positions) == 1


class TestOptionsToolsErrorHandling:
    """Test comprehensive error handling scenarios."""

    @pytest.mark.asyncio
    async def test_options_chains_error_handling(self, mock_trading_service):
        """Test error handling in options_chains."""
        mock_trading_service.get_formatted_options_chain.side_effect = Exception(
            "Options data unavailable"
        )

        result = await options_chains("INVALID")

        assert "error" in result
        assert "Options data unavailable" in result["error"]

    @pytest.mark.asyncio
    async def test_find_options_error_handling(self, mock_trading_service):
        """Test error handling in find_options."""
        mock_trading_service.find_tradable_options.side_effect = ValueError(
            "Invalid expiration date"
        )

        result = await find_options("AAPL", "invalid-date", "call")

        assert "error" in result
        assert "Invalid expiration date" in result["error"]

    @pytest.mark.asyncio
    async def test_option_market_data_error_handling(self, mock_trading_service):
        """Test error handling in option_market_data."""
        mock_trading_service.get_option_market_data.side_effect = Exception(
            "Option contract not found"
        )

        result = await option_market_data("INVALID_OPTION")

        assert "error" in result
        assert "Option contract not found" in result["error"]

    @pytest.mark.asyncio
    async def test_option_historicals_error_handling(self, mock_trading_service):
        """Test error handling in option_historicals."""
        # Test invalid option type
        result = await option_historicals(
            "AAPL", "2024-12-20", 150.0, "invalid", "day", "week"
        )
        assert "error" in result
        assert "Invalid option type" in result["error"]

        # Test invalid interval
        result = await option_historicals(
            "AAPL", "2024-12-20", 150.0, "call", "invalid", "week"
        )
        assert "error" in result
        assert "Invalid interval" in result["error"]

        # Test invalid span
        result = await option_historicals(
            "AAPL", "2024-12-20", 150.0, "call", "day", "invalid"
        )
        assert "error" in result
        assert "Invalid span" in result["error"]

        # Test invalid expiration date
        result = await option_historicals(
            "AAPL", "invalid-date", 150.0, "call", "day", "week"
        )
        assert "error" in result
        assert "Invalid expiration date format" in result["error"]


class TestOptionsToolsInputProcessing:
    """Test input processing and normalization."""

    @pytest.mark.asyncio
    async def test_symbol_normalization(self, mock_trading_service):
        """Test that symbols are properly normalized."""
        test_cases = [
            ("aapl", "AAPL"),
            ("  GOOGL  ", "GOOGL"),
            ("\tTSLA\n", "TSLA"),
            ("msft", "MSFT"),
        ]

        mock_trading_service.get_formatted_options_chain.return_value = {
            "underlying_symbol": "TEST"
        }

        for input_symbol, expected_symbol in test_cases:
            await options_chains(input_symbol)

            # Get the last call and verify the symbol was normalized
            last_call_args = mock_trading_service.get_formatted_options_chain.call_args[
                0
            ]
            assert last_call_args[0] == expected_symbol


class TestOptionsToolsCoverage:
    """Additional tests to achieve 70% coverage target."""

    def test_module_imports(self):
        """Test module imports and structure."""
        # Test that all expected functions are importable
        import app.mcp.options_tools as module

        # Verify all required functions exist
        assert hasattr(module, "options_chains")
        assert hasattr(module, "find_options")
        assert hasattr(module, "option_market_data")
        assert hasattr(module, "option_historicals")
        assert hasattr(module, "aggregate_option_positions")
        assert hasattr(module, "all_option_positions")
        assert hasattr(module, "open_option_positions")

    def test_module_documentation(self):
        """Test module and function documentation."""
        import app.mcp.options_tools as module

        # Module should have docstring
        assert module.__doc__ is not None
        assert "options" in module.__doc__.lower()

        # Functions should have docstrings
        assert options_chains.__doc__ is not None
        assert find_options.__doc__ is not None
        assert option_market_data.__doc__ is not None

    @pytest.mark.asyncio
    async def test_concurrent_tool_calls(self, mock_trading_service):
        """Test that tools can be called concurrently."""
        import asyncio

        mock_trading_service.get_formatted_options_chain.return_value = {
            "underlying_symbol": "TEST"
        }
        mock_trading_service.find_tradable_options.return_value = {
            "symbol": "TEST",
            "options": [],
        }
        mock_trading_service.get_option_market_data.return_value = {"option_id": "TEST"}

        # Create multiple concurrent calls
        tasks = [
            options_chains("AAPL"),
            find_options("GOOGL", None, None),
            option_market_data("TEST123"),
        ]

        results = await asyncio.gather(*tasks)

        # All calls should succeed
        assert len(results) == 3
        # Check for standardized response format
        assert results[0]["result"]["status"] == "success"
        assert results[1]["result"]["status"] == "success"
        assert results[2]["result"]["status"] == "success"
        assert (
            "underlying_symbol" in results[0]["result"]["data"] or "error" in results[0]
        )
        assert "symbol" in results[1]["result"]["data"] or "error" in results[1]
        assert "option_id" in results[2]["result"]["data"] or "error" in results[2]

    def test_service_management(self, mock_trading_service):
        """Test trading service management functions."""
        # Test that we can get the service
        service = get_mcp_trading_service()
        assert service is mock_trading_service

    def test_service_not_initialized(self):
        """Test error when service not initialized."""
        # Clear the service
        from app.mcp import options_tools

        options_tools._trading_service = None

        with pytest.raises(RuntimeError, match="TradingService not initialized"):
            get_mcp_trading_service()
