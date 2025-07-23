"""
Advanced unit tests for MCP options tools implementation.

Tests options-specific MCP tools, async patterns, service integration,
parameter validation, and response formatting for options operations.
"""

import asyncio
from unittest.mock import Mock, patch

import pytest
import pytest_asyncio

from app.mcp.options_tools import (
    FindTradableOptionsArgs,
    GetOptionMarketDataArgs,
    GetOptionsChainsArgs,
    find_tradable_options,
    get_option_market_data,
    get_options_chains,
)


class TestMCPOptionsToolsModule:
    """Test MCP options tools module structure."""

    def test_options_tools_module_imports(self):
        """Test that options tools module imports correctly."""
        import app.mcp.options_tools

        assert app.mcp.options_tools is not None

    def test_options_tools_module_docstring(self):
        """Test module has proper docstring."""
        import app.mcp.options_tools

        doc = app.mcp.options_tools.__doc__
        assert doc is not None
        assert "options data" in doc.lower()

    def test_all_options_functions_imported(self):
        """Test all expected options functions are available."""
        import app.mcp.options_tools as tools

        expected_functions = [
            "get_options_chains",
            "find_tradable_options",
            "get_option_market_data",
        ]

        for func_name in expected_functions:
            assert hasattr(tools, func_name), f"Should have {func_name} function"
            func = getattr(tools, func_name)
            assert callable(func), f"{func_name} should be callable"

    def test_trading_service_import(self):
        """Test that trading service is imported correctly."""
        import inspect

        import app.mcp.options_tools

        source = inspect.getsource(app.mcp.options_tools)
        assert "from app.services.trading_service import trading_service" in source


class TestMCPOptionsParameterValidation:
    """Test parameter validation for options tools."""

    def test_get_options_chains_args_validation(self):
        """Test GetOptionsChainsArgs parameter validation."""
        # Valid args
        args = GetOptionsChainsArgs(symbol="AAPL")
        assert args.symbol == "AAPL"

        # Test required field
        from pydantic import ValidationError

        with pytest.raises(ValidationError):
            GetOptionsChainsArgs()  # Missing required symbol

    def test_find_tradable_options_args_validation(self):
        """Test FindTradableOptionsArgs parameter validation."""
        # Valid args with just symbol
        args = FindTradableOptionsArgs(symbol="GOOGL")
        assert args.symbol == "GOOGL"
        assert args.expiration_date is None
        assert args.option_type is None

        # Valid args with all fields
        args = FindTradableOptionsArgs(
            symbol="TSLA", expiration_date="2024-03-15", option_type="call"
        )
        assert args.symbol == "TSLA"
        assert args.expiration_date == "2024-03-15"
        assert args.option_type == "call"

        # Test required field
        from pydantic import ValidationError

        with pytest.raises(ValidationError):
            FindTradableOptionsArgs()  # Missing required symbol

    def test_get_option_market_data_args_validation(self):
        """Test GetOptionMarketDataArgs parameter validation."""
        # Valid args
        args = GetOptionMarketDataArgs(option_id="AAPL240315C00180000")
        assert args.option_id == "AAPL240315C00180000"

        # Test required field
        from pydantic import ValidationError

        with pytest.raises(ValidationError):
            GetOptionMarketDataArgs()  # Missing required option_id

    def test_option_type_validation(self):
        """Test option type parameter validation."""
        # Valid option types
        valid_types = ["call", "put", None]

        for option_type in valid_types:
            args = FindTradableOptionsArgs(symbol="TEST", option_type=option_type)
            assert args.option_type == option_type

    def test_expiration_date_format_validation(self):
        """Test expiration date format validation."""
        # Valid date formats should be accepted
        valid_dates = ["2024-03-15", "2024-12-31", None]

        for exp_date in valid_dates:
            args = FindTradableOptionsArgs(symbol="TEST", expiration_date=exp_date)
            assert args.expiration_date == exp_date


class TestMCPOptionsAsyncBehavior:
    """Test async behavior of options tools."""

    @pytest_asyncio.fixture
    async def mock_trading_service(self):
        """Create mock trading service for options testing."""
        with patch("app.mcp.options_tools.trading_service") as mock_service:
            # Configure mock methods
            mock_service.get_formatted_options_chain = Mock(
                return_value={
                    "symbol": "AAPL",
                    "chains": {
                        "2024-03-15": {
                            "calls": [
                                {
                                    "strike": 180.0,
                                    "symbol": "AAPL240315C00180000",
                                    "bid": 2.50,
                                    "ask": 2.60,
                                    "last": 2.55,
                                    "volume": 1500,
                                    "open_interest": 5000,
                                    "implied_volatility": 0.25,
                                }
                            ],
                            "puts": [
                                {
                                    "strike": 180.0,
                                    "symbol": "AAPL240315P00180000",
                                    "bid": 1.80,
                                    "ask": 1.90,
                                    "last": 1.85,
                                    "volume": 800,
                                    "open_interest": 3000,
                                    "implied_volatility": 0.22,
                                }
                            ],
                        }
                    },
                }
            )

            mock_service.find_tradable_options = Mock(
                return_value={
                    "symbol": "AAPL",
                    "options": [
                        {
                            "symbol": "AAPL240315C00180000",
                            "strike": 180.0,
                            "expiration_date": "2024-03-15",
                            "option_type": "call",
                            "bid": 2.50,
                            "ask": 2.60,
                            "last": 2.55,
                        }
                    ],
                    "count": 1,
                }
            )

            mock_service.get_option_market_data = Mock(
                return_value={
                    "option_id": "AAPL240315C00180000",
                    "underlying_symbol": "AAPL",
                    "strike": 180.0,
                    "expiration_date": "2024-03-15",
                    "option_type": "call",
                    "bid": 2.50,
                    "ask": 2.60,
                    "last": 2.55,
                    "volume": 1500,
                    "open_interest": 5000,
                    "implied_volatility": 0.25,
                    "delta": 0.65,
                    "gamma": 0.02,
                    "theta": -0.05,
                    "vega": 0.15,
                    "rho": 0.08,
                }
            )

            yield mock_service

    @pytest.mark.asyncio
    async def test_get_options_chains_async(self, mock_trading_service):
        """Test get_options_chains async execution."""
        args = GetOptionsChainsArgs(symbol="AAPL")
        result = await get_options_chains(args)

        # Verify service call
        mock_trading_service.get_formatted_options_chain.assert_called_once_with("AAPL")

        # Verify response structure
        assert isinstance(result, dict)
        assert result["symbol"] == "AAPL"
        assert "chains" in result
        assert isinstance(result["chains"], dict)

        # Check structure of options data
        chains = result["chains"]
        if "2024-03-15" in chains:
            exp_data = chains["2024-03-15"]
            assert "calls" in exp_data
            assert "puts" in exp_data
            assert isinstance(exp_data["calls"], list)
            assert isinstance(exp_data["puts"], list)

    @pytest.mark.asyncio
    async def test_find_tradable_options_async(self, mock_trading_service):
        """Test find_tradable_options async execution."""
        args = FindTradableOptionsArgs(
            symbol="AAPL", expiration_date="2024-03-15", option_type="call"
        )
        result = await find_tradable_options(args)

        # Verify service call
        mock_trading_service.find_tradable_options.assert_called_once_with(
            "AAPL", "2024-03-15", "call"
        )

        # Verify response structure
        assert isinstance(result, dict)
        assert result["symbol"] == "AAPL"
        assert "options" in result
        assert "count" in result
        assert isinstance(result["options"], list)

        # Check options data structure
        if result["options"]:
            option = result["options"][0]
            assert "symbol" in option
            assert "strike" in option
            assert "expiration_date" in option
            assert "option_type" in option

    @pytest.mark.asyncio
    async def test_get_option_market_data_async(self, mock_trading_service):
        """Test get_option_market_data async execution."""
        args = GetOptionMarketDataArgs(option_id="AAPL240315C00180000")
        result = await get_option_market_data(args)

        # Verify service call
        mock_trading_service.get_option_market_data.assert_called_once_with(
            "AAPL240315C00180000"
        )

        # Verify response structure
        assert isinstance(result, dict)
        assert result["option_id"] == "AAPL240315C00180000"
        assert result["underlying_symbol"] == "AAPL"
        assert result["strike"] == 180.0
        assert result["option_type"] == "call"

        # Check market data fields
        market_fields = [
            "bid",
            "ask",
            "last",
            "volume",
            "open_interest",
            "implied_volatility",
        ]
        for field in market_fields:
            assert field in result

        # Check Greeks
        greeks_fields = ["delta", "gamma", "theta", "vega", "rho"]
        for greek in greeks_fields:
            assert greek in result


class TestMCPOptionsSymbolHandling:
    """Test symbol handling in options tools."""

    @pytest_asyncio.fixture
    async def mock_trading_service(self):
        """Create mock trading service for symbol testing."""
        with patch("app.mcp.options_tools.trading_service") as mock_service:
            mock_service.get_formatted_options_chain = Mock(
                return_value={"symbol": "TEST"}
            )
            mock_service.find_tradable_options = Mock(
                return_value={"symbol": "TEST", "options": []}
            )
            mock_service.get_option_market_data = Mock(
                return_value={"option_id": "test"}
            )
            yield mock_service

    @pytest.mark.asyncio
    async def test_underlying_symbol_uppercase_conversion(self, mock_trading_service):
        """Test that underlying symbols are converted to uppercase."""
        args = GetOptionsChainsArgs(symbol="aapl")  # lowercase
        await get_options_chains(args)

        # Should call service with uppercase symbol
        mock_trading_service.get_formatted_options_chain.assert_called_once_with("AAPL")

    @pytest.mark.asyncio
    async def test_find_options_symbol_cleaning(self, mock_trading_service):
        """Test symbol cleaning in find_tradable_options."""
        args = FindTradableOptionsArgs(symbol="  msft  ")  # with spaces
        await find_tradable_options(args)

        # Should call service with clean, uppercase symbol
        mock_trading_service.find_tradable_options.assert_called_once_with(
            "MSFT", None, None
        )

    @pytest.mark.asyncio
    async def test_option_id_passthrough(self, mock_trading_service):
        """Test that option IDs are passed through without modification."""
        option_id = "AAPL240315C00180000"
        args = GetOptionMarketDataArgs(option_id=option_id)
        await get_option_market_data(args)

        # Option ID should be passed through exactly
        mock_trading_service.get_option_market_data.assert_called_once_with(option_id)


class TestMCPOptionsErrorHandling:
    """Test error handling in options tools."""

    @pytest.mark.asyncio
    async def test_get_options_chains_error_handling(self):
        """Test error handling in get_options_chains."""
        with patch("app.mcp.options_tools.trading_service") as mock_service:
            mock_service.get_formatted_options_chain.side_effect = Exception(
                "Options data unavailable"
            )

            args = GetOptionsChainsArgs(symbol="INVALID")
            result = await get_options_chains(args)

            # Should return error dict, not raise
            assert isinstance(result, dict)
            assert "error" in result
            assert "Options data unavailable" in result["error"]

    @pytest.mark.asyncio
    async def test_find_tradable_options_error_handling(self):
        """Test error handling in find_tradable_options."""
        with patch("app.mcp.options_tools.trading_service") as mock_service:
            mock_service.find_tradable_options.side_effect = ValueError(
                "Invalid expiration date"
            )

            args = FindTradableOptionsArgs(
                symbol="AAPL", expiration_date="invalid-date", option_type="call"
            )
            result = await find_tradable_options(args)

            # Should return error dict
            assert isinstance(result, dict)
            assert "error" in result
            assert "Invalid expiration date" in result["error"]

    @pytest.mark.asyncio
    async def test_get_option_market_data_error_handling(self):
        """Test error handling in get_option_market_data."""
        with patch("app.mcp.options_tools.trading_service") as mock_service:
            mock_service.get_option_market_data.side_effect = KeyError(
                "Option not found"
            )

            args = GetOptionMarketDataArgs(option_id="INVALID_OPTION_ID")
            result = await get_option_market_data(args)

            # Should return error dict
            assert isinstance(result, dict)
            assert "error" in result
            assert "Option not found" in result["error"]

    @pytest.mark.asyncio
    async def test_network_timeout_error_handling(self):
        """Test handling of network timeout errors."""
        with patch("app.mcp.options_tools.trading_service") as mock_service:
            mock_service.get_formatted_options_chain.side_effect = TimeoutError(
                "Request timeout"
            )

            args = GetOptionsChainsArgs(symbol="AAPL")
            result = await get_options_chains(args)

            # Should return error dict
            assert isinstance(result, dict)
            assert "error" in result
            assert "Request timeout" in result["error"]


class TestMCPOptionsServiceIntegration:
    """Test integration patterns with trading service for options."""

    def test_options_service_methods_called(self):
        """Test that appropriate service methods are called for each tool."""
        with patch("app.mcp.options_tools.trading_service") as mock_service:
            mock_service.get_formatted_options_chain = Mock(return_value={})
            mock_service.find_tradable_options = Mock(return_value={})
            mock_service.get_option_market_data = Mock(return_value={})

            # Each tool should call its corresponding service method
            import asyncio

            async def test_calls():
                await get_options_chains(GetOptionsChainsArgs(symbol="TEST"))
                mock_service.get_formatted_options_chain.assert_called()

                await find_tradable_options(FindTradableOptionsArgs(symbol="TEST"))
                mock_service.find_tradable_options.assert_called()

                await get_option_market_data(GetOptionMarketDataArgs(option_id="test"))
                mock_service.get_option_market_data.assert_called()

            asyncio.run(test_calls())

    @pytest.mark.asyncio
    async def test_service_response_passthrough(self):
        """Test that service responses are passed through correctly."""
        expected_response = {
            "symbol": "AAPL",
            "custom_field": "test_value",
            "chains": {"2024-03-15": {"calls": [], "puts": []}},
        }

        with patch("app.mcp.options_tools.trading_service") as mock_service:
            mock_service.get_formatted_options_chain.return_value = expected_response

            args = GetOptionsChainsArgs(symbol="AAPL")
            result = await get_options_chains(args)

            # Should pass through the exact response
            assert result == expected_response
            assert result["custom_field"] == "test_value"

    @pytest.mark.asyncio
    async def test_parameter_mapping_to_service(self):
        """Test that parameters are correctly mapped to service calls."""
        with patch("app.mcp.options_tools.trading_service") as mock_service:
            mock_service.find_tradable_options.return_value = {"options": []}

            # Test parameter mapping
            args = FindTradableOptionsArgs(
                symbol="NVDA", expiration_date="2024-06-21", option_type="put"
            )
            await find_tradable_options(args)

            # Verify all parameters were passed correctly
            mock_service.find_tradable_options.assert_called_once_with(
                "NVDA",  # symbol (cleaned and uppercased)
                "2024-06-21",  # expiration_date
                "put",  # option_type
            )


class TestMCPOptionsConcurrency:
    """Test concurrent execution of options tools."""

    @pytest.mark.asyncio
    async def test_concurrent_options_chains_requests(self):
        """Test concurrent options chain requests for multiple symbols."""
        symbols = ["AAPL", "GOOGL", "MSFT", "TSLA"]

        with patch("app.mcp.options_tools.trading_service") as mock_service:
            call_count = 0

            def mock_get_chains(symbol):
                nonlocal call_count
                call_count += 1
                return {
                    "symbol": symbol,
                    "chains": {f"2024-0{3 + call_count}-15": {"calls": [], "puts": []}},
                }

            mock_service.get_formatted_options_chain.side_effect = mock_get_chains

            # Create concurrent requests
            tasks = []
            for symbol in symbols:
                args = GetOptionsChainsArgs(symbol=symbol)
                task = asyncio.create_task(get_options_chains(args))
                tasks.append(task)

            # Wait for all to complete
            results = await asyncio.gather(*tasks)

            # All should complete successfully
            assert len(results) == len(symbols)
            for i, result in enumerate(results):
                assert "symbol" in result
                assert "chains" in result
                assert result["symbol"] == symbols[i]

    @pytest.mark.asyncio
    async def test_mixed_concurrent_options_requests(self):
        """Test concurrent execution of different options tools."""
        with patch("app.mcp.options_tools.trading_service") as mock_service:
            mock_service.get_formatted_options_chain.return_value = {
                "symbol": "AAPL",
                "chains": {},
            }
            mock_service.find_tradable_options.return_value = {
                "symbol": "GOOGL",
                "options": [],
            }
            mock_service.get_option_market_data.return_value = {
                "option_id": "test",
                "symbol": "MSFT",
            }

            # Create mixed concurrent requests
            tasks = [
                get_options_chains(GetOptionsChainsArgs(symbol="AAPL")),
                find_tradable_options(FindTradableOptionsArgs(symbol="GOOGL")),
                get_option_market_data(
                    GetOptionMarketDataArgs(option_id="MSFT240315C00300000")
                ),
            ]

            results = await asyncio.gather(*tasks)

            # All should complete
            assert len(results) == 3
            assert results[0]["symbol"] == "AAPL"  # chains request
            assert results[1]["symbol"] == "GOOGL"  # find options
            assert results[2]["option_id"] == "test"  # market data


class TestMCPOptionsToolDocumentation:
    """Test documentation and metadata for options tools."""

    def test_all_options_tools_have_docstrings(self):
        """Test all options tools have proper docstrings."""
        import inspect

        import app.mcp.options_tools as tools

        tool_functions = [
            "get_options_chains",
            "find_tradable_options",
            "get_option_market_data",
        ]

        for func_name in tool_functions:
            func = getattr(tools, func_name)
            doc = inspect.getdoc(func)
            assert doc is not None and doc.strip(), f"{func_name} should have docstring"

    def test_options_parameter_classes_have_descriptions(self):
        """Test options parameter model classes have field descriptions."""
        from app.mcp.options_tools import (
            FindTradableOptionsArgs,
            GetOptionMarketDataArgs,
            GetOptionsChainsArgs,
        )

        parameter_classes = [
            GetOptionsChainsArgs,
            FindTradableOptionsArgs,
            GetOptionMarketDataArgs,
        ]

        for param_class in parameter_classes:
            schema = param_class.model_json_schema()
            properties = schema.get("properties", {})

            for field_name, field_info in properties.items():
                assert (
                    "description" in field_info
                ), f"{param_class.__name__}.{field_name} should have description"
                assert field_info[
                    "description"
                ].strip(), f"{param_class.__name__}.{field_name} description should not be empty"

    def test_options_function_signatures_are_async(self):
        """Test that all options functions are async."""
        import inspect

        import app.mcp.options_tools as tools

        tool_functions = [
            "get_options_chains",
            "find_tradable_options",
            "get_option_market_data",
        ]

        for func_name in tool_functions:
            func = getattr(tools, func_name)
            assert inspect.iscoroutinefunction(
                func
            ), f"{func_name} should be async function"

    def test_options_tools_comprehensive_coverage(self):
        """Test that options tools cover comprehensive use cases."""
        # Test that we have tools for the main options operations
        expected_operations = {
            "get_options_chains": "Get complete options chains for a symbol",
            "find_tradable_options": "Find specific tradable options with filters",
            "get_option_market_data": "Get detailed market data for specific option",
        }

        import app.mcp.options_tools as tools

        for func_name, description in expected_operations.items():
            assert hasattr(
                tools, func_name
            ), f"Should have {func_name} for: {description}"
            func = getattr(tools, func_name)
            assert callable(func), f"{func_name} should be callable"


class TestMCPOptionsDataValidation:
    """Test data validation and formatting in options tools."""

    @pytest.mark.asyncio
    async def test_options_chain_data_structure_validation(self):
        """Test that options chain data follows expected structure."""
        with patch("app.mcp.options_tools.trading_service") as mock_service:
            # Mock complex options chain data
            mock_response = {
                "symbol": "AAPL",
                "chains": {
                    "2024-03-15": {
                        "calls": [
                            {
                                "strike": 180.0,
                                "symbol": "AAPL240315C00180000",
                                "bid": 2.50,
                                "ask": 2.60,
                                "last": 2.55,
                                "volume": 1500,
                                "open_interest": 5000,
                            }
                        ],
                        "puts": [],
                    }
                },
            }
            mock_service.get_formatted_options_chain.return_value = mock_response

            args = GetOptionsChainsArgs(symbol="AAPL")
            result = await get_options_chains(args)

            # Verify structure
            assert "symbol" in result
            assert "chains" in result
            assert isinstance(result["chains"], dict)

            for _exp_date, chain_data in result["chains"].items():
                assert "calls" in chain_data
                assert "puts" in chain_data
                assert isinstance(chain_data["calls"], list)
                assert isinstance(chain_data["puts"], list)

    @pytest.mark.asyncio
    async def test_tradable_options_response_validation(self):
        """Test that tradable options response has expected structure."""
        with patch("app.mcp.options_tools.trading_service") as mock_service:
            mock_response = {
                "symbol": "AAPL",
                "options": [
                    {
                        "symbol": "AAPL240315C00180000",
                        "strike": 180.0,
                        "expiration_date": "2024-03-15",
                        "option_type": "call",
                    }
                ],
                "count": 1,
                "filters_applied": {
                    "expiration_date": "2024-03-15",
                    "option_type": "call",
                },
            }
            mock_service.find_tradable_options.return_value = mock_response

            args = FindTradableOptionsArgs(symbol="AAPL", option_type="call")
            result = await find_tradable_options(args)

            # Verify required fields
            assert "symbol" in result
            assert "options" in result
            assert isinstance(result["options"], list)

            if "count" in result:
                assert isinstance(result["count"], int)
