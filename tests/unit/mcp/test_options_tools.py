"""
Comprehensive unit tests for MCP options tools.

Tests async options tools, parameter validation, TradingService integration,
error handling, and response formatting for options data operations.
"""

from unittest.mock import AsyncMock, Mock, patch
from typing import Any

import pytest
import pytest_asyncio
from pydantic import ValidationError

from app.mcp.options_tools import (
    FindTradableOptionsArgs,
    GetOptionMarketDataArgs,
    GetOptionsChainsArgs,
    find_tradable_options,
    get_option_market_data,
    get_options_chains,
    trading_service,
)


class TestOptionsToolsParameterValidation:
    """Test parameter validation for options tool arguments."""
    
    def test_get_options_chains_args_validation(self):
        """Test GetOptionsChainsArgs parameter validation."""
        # Valid args
        args = GetOptionsChainsArgs(symbol="AAPL")
        assert args.symbol == "AAPL"
        
        # Test required field
        with pytest.raises(ValidationError):
            GetOptionsChainsArgs()
        
        # Test empty symbol should be allowed (handled in tool)
        args = GetOptionsChainsArgs(symbol="")
        assert args.symbol == ""
    
    def test_find_tradable_options_args_validation(self):
        """Test FindTradableOptionsArgs parameter validation."""
        # Valid args with only symbol
        args = FindTradableOptionsArgs(symbol="AAPL")
        assert args.symbol == "AAPL"
        assert args.expiration_date is None
        assert args.option_type is None
        
        # Valid args with expiration date
        args = FindTradableOptionsArgs(symbol="GOOGL", expiration_date="2024-12-20")
        assert args.symbol == "GOOGL"
        assert args.expiration_date == "2024-12-20"
        
        # Valid args with option type
        args = FindTradableOptionsArgs(symbol="MSFT", option_type="call")
        assert args.symbol == "MSFT"
        assert args.option_type == "call"
        
        # Valid args with all fields
        args = FindTradableOptionsArgs(
            symbol="TSLA", 
            expiration_date="2024-12-20", 
            option_type="put"
        )
        assert args.symbol == "TSLA"
        assert args.expiration_date == "2024-12-20"
        assert args.option_type == "put"
        
        # Test required field
        with pytest.raises(ValidationError):
            FindTradableOptionsArgs()
    
    def test_get_option_market_data_args_validation(self):
        """Test GetOptionMarketDataArgs parameter validation."""
        # Valid args
        args = GetOptionMarketDataArgs(option_id="AAPL240119C00195000")
        assert args.option_id == "AAPL240119C00195000"
        
        # Test with numeric ID
        args = GetOptionMarketDataArgs(option_id="12345")
        assert args.option_id == "12345"
        
        # Test required field
        with pytest.raises(ValidationError):
            GetOptionMarketDataArgs()


class TestOptionsToolFunctions:
    """Test individual options tool functions."""
    
    @pytest_asyncio.async
    async def test_get_options_chains_success(self):
        """Test successful options chain retrieval."""
        mock_result = {
            "underlying_symbol": "AAPL",
            "expiration_dates": ["2024-12-20", "2025-01-17"],
            "chains": {
                "2024-12-20": {
                    "calls": [
                        {"strike": 150.0, "symbol": "AAPL241220C00150000", "bid": 5.25, "ask": 5.50}
                    ],
                    "puts": [
                        {"strike": 150.0, "symbol": "AAPL241220P00150000", "bid": 2.10, "ask": 2.25}
                    ]
                }
            }
        }
        
        with patch.object(trading_service, 'get_formatted_options_chain', new_callable=AsyncMock) as mock_service:
            mock_service.return_value = mock_result
            
            args = GetOptionsChainsArgs(symbol="AAPL")
            result = await get_options_chains(args)
            
            assert result == mock_result
            mock_service.assert_called_once_with("AAPL")
    
    @pytest_asyncio.async
    async def test_get_options_chains_with_whitespace_symbol(self):
        """Test options chain retrieval with whitespace in symbol."""
        mock_result = {"underlying_symbol": "TSLA", "chains": {}}
        
        with patch.object(trading_service, 'get_formatted_options_chain', new_callable=AsyncMock) as mock_service:
            mock_service.return_value = mock_result
            
            args = GetOptionsChainsArgs(symbol="  tsla  ")
            result = await get_options_chains(args)
            
            # Should strip and uppercase
            mock_service.assert_called_once_with("TSLA")
            assert result == mock_result
    
    @pytest_asyncio.async
    async def test_get_options_chains_error_handling(self):
        """Test error handling in get_options_chains."""
        with patch.object(trading_service, 'get_formatted_options_chain', new_callable=AsyncMock) as mock_service:
            mock_service.side_effect = Exception("Options data unavailable")
            
            args = GetOptionsChainsArgs(symbol="INVALID")
            result = await get_options_chains(args)
            
            assert "error" in result
            assert "Options data unavailable" in result["error"]
    
    @pytest_asyncio.async
    async def test_find_tradable_options_success(self):
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
                    "ask": 5.50
                }
            ],
            "count": 1
        }
        
        with patch.object(trading_service, 'find_tradable_options', new_callable=AsyncMock) as mock_service:
            mock_service.return_value = mock_result
            
            args = FindTradableOptionsArgs(symbol="aapl", expiration_date="2024-12-20", option_type="call")
            result = await find_tradable_options(args)
            
            assert result == mock_result
            mock_service.assert_called_once_with("AAPL", "2024-12-20", "call")
    
    @pytest_asyncio.async
    async def test_find_tradable_options_minimal_args(self):
        """Test find_tradable_options with minimal arguments."""
        mock_result = {"symbol": "GOOGL", "options": [], "count": 0}
        
        with patch.object(trading_service, 'find_tradable_options', new_callable=AsyncMock) as mock_service:
            mock_service.return_value = mock_result
            
            args = FindTradableOptionsArgs(symbol="googl")
            result = await find_tradable_options(args)
            
            assert result == mock_result
            mock_service.assert_called_once_with("GOOGL", None, None)
    
    @pytest_asyncio.async
    async def test_find_tradable_options_error_handling(self):
        """Test error handling in find_tradable_options."""
        with patch.object(trading_service, 'find_tradable_options', new_callable=AsyncMock) as mock_service:
            mock_service.side_effect = ValueError("Invalid expiration date")
            
            args = FindTradableOptionsArgs(symbol="AAPL", expiration_date="invalid-date")
            result = await find_tradable_options(args)
            
            assert "error" in result
            assert "Invalid expiration date" in result["error"]
    
    @pytest_asyncio.async
    async def test_get_option_market_data_success(self):
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
                "rho": 0.08
            }
        }
        
        with patch.object(trading_service, 'get_option_market_data', new_callable=AsyncMock) as mock_service:
            mock_service.return_value = mock_result
            
            args = GetOptionMarketDataArgs(option_id="AAPL241220C00150000")
            result = await get_option_market_data(args)
            
            assert result == mock_result
            mock_service.assert_called_once_with("AAPL241220C00150000")
    
    @pytest_asyncio.async
    async def test_get_option_market_data_error_handling(self):
        """Test error handling in get_option_market_data."""
        with patch.object(trading_service, 'get_option_market_data', new_callable=AsyncMock) as mock_service:
            mock_service.side_effect = Exception("Option contract not found")
            
            args = GetOptionMarketDataArgs(option_id="INVALID_OPTION")
            result = await get_option_market_data(args)
            
            assert "error" in result
            assert "Option contract not found" in result["error"]


class TestOptionsToolsIntegration:
    """Test integration with TradingService."""
    
    def test_trading_service_instance(self):
        """Test that trading_service is properly instantiated."""
        assert trading_service is not None
        # Should be a TradingService instance
        from app.services.trading_service import TradingService
        assert isinstance(trading_service, TradingService)
    
    @pytest_asyncio.async
    async def test_all_tools_use_trading_service(self):
        """Test that all tools properly integrate with TradingService."""
        # Mock all TradingService methods used by options tools
        with patch.object(trading_service, 'get_formatted_options_chain', new_callable=AsyncMock) as mock_chains, \
             patch.object(trading_service, 'find_tradable_options', new_callable=AsyncMock) as mock_find, \
             patch.object(trading_service, 'get_option_market_data', new_callable=AsyncMock) as mock_data:
            
            # Set up return values
            mock_chains.return_value = {"underlying_symbol": "AAPL"}
            mock_find.return_value = {"symbol": "AAPL", "options": []}
            mock_data.return_value = {"option_id": "test"}
            
            # Call all tools
            await get_options_chains(GetOptionsChainsArgs(symbol="AAPL"))
            await find_tradable_options(FindTradableOptionsArgs(symbol="AAPL"))
            await get_option_market_data(GetOptionMarketDataArgs(option_id="test"))
            
            # Verify all service methods were called
            mock_chains.assert_called_once()
            mock_find.assert_called_once()
            mock_data.assert_called_once()


class TestOptionsToolsErrorHandling:
    """Test comprehensive error handling scenarios."""
    
    @pytest_asyncio.async
    async def test_network_error_handling(self):
        """Test handling of network-related errors."""
        import asyncio
        
        with patch.object(trading_service, 'get_formatted_options_chain', new_callable=AsyncMock) as mock_service:
            mock_service.side_effect = asyncio.TimeoutError("Request timeout")
            
            args = GetOptionsChainsArgs(symbol="AAPL")
            result = await get_options_chains(args)
            
            assert "error" in result
            assert "Request timeout" in result["error"]
    
    @pytest_asyncio.async
    async def test_service_exception_handling(self):
        """Test handling of service-specific exceptions."""
        with patch.object(trading_service, 'find_tradable_options', new_callable=AsyncMock) as mock_service:
            mock_service.side_effect = ValueError("Invalid option type")
            
            args = FindTradableOptionsArgs(symbol="AAPL", option_type="invalid")
            result = await find_tradable_options(args)
            
            assert "error" in result
            assert "Invalid option type" in result["error"]
    
    @pytest_asyncio.async
    async def test_unexpected_exception_handling(self):
        """Test handling of unexpected exceptions."""
        with patch.object(trading_service, 'get_option_market_data', new_callable=AsyncMock) as mock_service:
            mock_service.side_effect = RuntimeError("Database connection failed")
            
            args = GetOptionMarketDataArgs(option_id="test")
            result = await get_option_market_data(args)
            
            assert "error" in result
            assert "Database connection failed" in result["error"]


class TestOptionsToolsInputProcessing:
    """Test input processing and normalization."""
    
    @pytest_asyncio.async
    async def test_symbol_normalization(self):
        """Test that symbols are properly normalized."""
        test_cases = [
            ("aapl", "AAPL"),
            ("  GOOGL  ", "GOOGL"),
            ("\tTSLA\n", "TSLA"),
            ("msft", "MSFT")
        ]
        
        with patch.object(trading_service, 'get_formatted_options_chain', new_callable=AsyncMock) as mock_service:
            mock_service.return_value = {"underlying_symbol": "TEST"}
            
            for input_symbol, expected_symbol in test_cases:
                args = GetOptionsChainsArgs(symbol=input_symbol)
                await get_options_chains(args)
                
                # Get the last call and verify the symbol was normalized
                last_call_args = mock_service.call_args[0]
                assert last_call_args[0] == expected_symbol
    
    @pytest_asyncio.async
    async def test_option_type_validation(self):
        """Test option type parameter handling."""
        test_cases = ["call", "put", None, "CALL", "PUT"]
        
        with patch.object(trading_service, 'find_tradable_options', new_callable=AsyncMock) as mock_service:
            mock_service.return_value = {"symbol": "AAPL", "options": []}
            
            for option_type in test_cases:
                args = FindTradableOptionsArgs(symbol="AAPL", option_type=option_type)
                await find_tradable_options(args)
                
                # Verify the option_type is passed through
                last_call_args = mock_service.call_args[0]
                assert last_call_args[2] == option_type
    
    @pytest_asyncio.async
    async def test_expiration_date_validation(self):
        """Test expiration date parameter handling."""
        test_cases = [
            "2024-12-20",
            "2025-01-17", 
            None,
            "2024-03-15"
        ]
        
        with patch.object(trading_service, 'find_tradable_options', new_callable=AsyncMock) as mock_service:
            mock_service.return_value = {"symbol": "AAPL", "options": []}
            
            for expiration_date in test_cases:
                args = FindTradableOptionsArgs(symbol="AAPL", expiration_date=expiration_date)
                await find_tradable_options(args)
                
                # Verify the expiration_date is passed through
                last_call_args = mock_service.call_args[0]
                assert last_call_args[1] == expiration_date


class TestOptionsToolsResponseFormatting:
    """Test response formatting and structure."""
    
    @pytest_asyncio.async
    async def test_successful_response_passthrough(self):
        """Test that successful responses are passed through correctly."""
        mock_response = {
            "underlying_symbol": "AAPL",
            "chains": {"2024-12-20": {"calls": [], "puts": []}},
            "metadata": {"source": "test", "timestamp": "2024-01-01T10:00:00Z"}
        }
        
        with patch.object(trading_service, 'get_formatted_options_chain', new_callable=AsyncMock) as mock_service:
            mock_service.return_value = mock_response
            
            args = GetOptionsChainsArgs(symbol="AAPL")
            result = await get_options_chains(args)
            
            # Should return the exact response from service
            assert result == mock_response
    
    @pytest_asyncio.async
    async def test_error_response_formatting(self):
        """Test that error responses are properly formatted."""
        with patch.object(trading_service, 'get_formatted_options_chain', new_callable=AsyncMock) as mock_service:
            mock_service.side_effect = Exception("Test error")
            
            args = GetOptionsChainsArgs(symbol="AAPL")
            result = await get_options_chains(args)
            
            # Should return error dict
            assert isinstance(result, dict)
            assert "error" in result
            assert "Test error" in result["error"]
    
    @pytest_asyncio.async
    async def test_empty_response_handling(self):
        """Test handling of empty or None responses."""
        with patch.object(trading_service, 'find_tradable_options', new_callable=AsyncMock) as mock_service:
            mock_service.return_value = None
            
            args = FindTradableOptionsArgs(symbol="AAPL")
            result = await find_tradable_options(args)
            
            # Should return None directly (service handles this case)
            assert result is None


class TestOptionsToolsAsyncBehavior:
    """Test async behavior and concurrency."""
    
    @pytest_asyncio.async
    async def test_concurrent_tool_calls(self):
        """Test that tools can be called concurrently."""
        import asyncio
        
        with patch.object(trading_service, 'get_formatted_options_chain', new_callable=AsyncMock) as mock_chains, \
             patch.object(trading_service, 'find_tradable_options', new_callable=AsyncMock) as mock_find, \
             patch.object(trading_service, 'get_option_market_data', new_callable=AsyncMock) as mock_data:
            
            mock_chains.return_value = {"underlying_symbol": "TEST"}
            mock_find.return_value = {"symbol": "TEST", "options": []}
            mock_data.return_value = {"option_id": "TEST"}
            
            # Create multiple concurrent calls
            tasks = [
                get_options_chains(GetOptionsChainsArgs(symbol="AAPL")),
                find_tradable_options(FindTradableOptionsArgs(symbol="GOOGL")),
                get_option_market_data(GetOptionMarketDataArgs(option_id="TEST123"))
            ]
            
            results = await asyncio.gather(*tasks)
            
            # All calls should succeed
            assert len(results) == 3
            assert "underlying_symbol" in results[0] or "error" in results[0]
            assert "symbol" in results[1] or "error" in results[1]
            assert "option_id" in results[2] or "error" in results[2]
    
    @pytest_asyncio.async
    async def test_async_context_preservation(self):
        """Test that async context is preserved across tool calls."""
        import contextvars
        
        # Create a context variable
        test_var = contextvars.ContextVar('test_var')
        test_var.set('options_test_value')
        
        with patch.object(trading_service, 'get_formatted_options_chain', new_callable=AsyncMock) as mock_service:
            async def check_context(*args, **kwargs):
                # Verify context is preserved
                assert test_var.get() == 'options_test_value'
                return {"underlying_symbol": "AAPL"}
            
            mock_service.side_effect = check_context
            
            args = GetOptionsChainsArgs(symbol="AAPL")
            result = await get_options_chains(args)
            
            assert result["underlying_symbol"] == "AAPL"


class TestOptionsToolsSpecialCases:
    """Test options-specific edge cases and scenarios."""
    
    @pytest_asyncio.async
    async def test_complex_option_symbols(self):
        """Test handling of complex option symbols."""
        complex_symbols = [
            "AAPL241220C00150000",  # Standard format
            "SPY250117P00400000",   # ETF option
            "QQQ241115C00350000",   # Another ETF
            "TSLA241220C00200000"   # High strike
        ]
        
        with patch.object(trading_service, 'get_option_market_data', new_callable=AsyncMock) as mock_service:
            mock_service.return_value = {"option_id": "test", "valid": True}
            
            for symbol in complex_symbols:
                args = GetOptionMarketDataArgs(option_id=symbol)
                result = await get_option_market_data(args)
                
                # Should handle all complex symbols
                assert "option_id" in result or "error" in result
                mock_service.assert_called_with(symbol)
    
    @pytest_asyncio.async
    async def test_multiple_expiration_dates(self):
        """Test handling of multiple expiration dates in chain data."""
        mock_chain_data = {
            "underlying_symbol": "AAPL",
            "expiration_dates": ["2024-12-20", "2025-01-17", "2025-03-21"],
            "chains": {
                "2024-12-20": {"calls": [{"strike": 150}], "puts": [{"strike": 150}]},
                "2025-01-17": {"calls": [{"strike": 155}], "puts": [{"strike": 155}]},
                "2025-03-21": {"calls": [{"strike": 160}], "puts": [{"strike": 160}]}
            }
        }
        
        with patch.object(trading_service, 'get_formatted_options_chain', new_callable=AsyncMock) as mock_service:
            mock_service.return_value = mock_chain_data
            
            args = GetOptionsChainsArgs(symbol="AAPL")
            result = await get_options_chains(args)
            
            assert result == mock_chain_data
            assert len(result["expiration_dates"]) == 3
            assert len(result["chains"]) == 3
    
    @pytest_asyncio.async
    async def test_options_filtering_scenarios(self):
        """Test various filtering scenarios for tradable options."""
        filtering_scenarios = [
            {"symbol": "AAPL", "expiration_date": "2024-12-20", "option_type": "call"},
            {"symbol": "AAPL", "expiration_date": "2024-12-20", "option_type": "put"},
            {"symbol": "AAPL", "expiration_date": None, "option_type": "call"},
            {"symbol": "AAPL", "expiration_date": "2024-12-20", "option_type": None},
            {"symbol": "AAPL", "expiration_date": None, "option_type": None}
        ]
        
        with patch.object(trading_service, 'find_tradable_options', new_callable=AsyncMock) as mock_service:
            mock_service.return_value = {"symbol": "AAPL", "options": []}
            
            for scenario in filtering_scenarios:
                args = FindTradableOptionsArgs(**scenario)
                result = await find_tradable_options(args)
                
                # Should handle all filtering combinations
                expected_calls = (scenario["symbol"], scenario["expiration_date"], scenario["option_type"])
                mock_service.assert_called_with(*expected_calls)


class TestOptionsToolsCoverage:
    """Additional tests to achieve 70% coverage target."""
    
    def test_module_imports(self):
        """Test module imports and structure."""
        # Test that all expected classes and functions are importable
        from app.mcp.options_tools import (
            FindTradableOptionsArgs,
            GetOptionMarketDataArgs,
            GetOptionsChainsArgs,
            find_tradable_options,
            get_option_market_data,
            get_options_chains,
            trading_service,
        )
        
        # Verify classes are Pydantic models
        from pydantic import BaseModel
        assert issubclass(GetOptionsChainsArgs, BaseModel)
        assert issubclass(FindTradableOptionsArgs, BaseModel)
        assert issubclass(GetOptionMarketDataArgs, BaseModel)
    
    def test_argument_model_fields(self):
        """Test argument model field definitions."""
        # Test field descriptions
        assert GetOptionsChainsArgs.model_fields['symbol'].description is not None
        assert FindTradableOptionsArgs.model_fields['symbol'].description is not None
        assert FindTradableOptionsArgs.model_fields['expiration_date'].description is not None
        assert FindTradableOptionsArgs.model_fields['option_type'].description is not None
        assert GetOptionMarketDataArgs.model_fields['option_id'].description is not None
    
    def test_module_documentation(self):
        """Test module and function documentation."""
        import app.mcp.options_tools as module
        
        # Module should have docstring
        assert module.__doc__ is not None
        assert "options" in module.__doc__.lower()
        
        # Functions should have docstrings
        assert get_options_chains.__doc__ is not None
        assert find_tradable_options.__doc__ is not None
        assert get_option_market_data.__doc__ is not None
    
    @pytest_asyncio.async
    async def test_edge_case_inputs(self):
        """Test edge case inputs."""
        with patch.object(trading_service, 'get_formatted_options_chain', new_callable=AsyncMock) as mock_service:
            mock_service.return_value = {"underlying_symbol": "A"}
            
            # Test single character symbol
            args = GetOptionsChainsArgs(symbol="A")
            result = await get_options_chains(args)
            mock_service.assert_called_with("A")
            
            # Test symbol with dots
            args = GetOptionsChainsArgs(symbol="BRK.A")
            await get_options_chains(args)
            mock_service.assert_called_with("BRK.A")
    
    def test_field_types_and_defaults(self):
        """Test field types and default values."""
        # Test FindTradableOptionsArgs defaults
        args = FindTradableOptionsArgs(symbol="AAPL")
        assert args.expiration_date is None
        assert args.option_type is None
        
        # Test field types
        assert isinstance(args.symbol, str)
        assert args.expiration_date is None or isinstance(args.expiration_date, str)
        assert args.option_type is None or isinstance(args.option_type, str)
    
    @pytest_asyncio.async
    async def test_service_method_signatures(self):
        """Test that service methods are called with correct signatures."""
        with patch.object(trading_service, 'get_formatted_options_chain', new_callable=AsyncMock) as mock_chains, \
             patch.object(trading_service, 'find_tradable_options', new_callable=AsyncMock) as mock_find, \
             patch.object(trading_service, 'get_option_market_data', new_callable=AsyncMock) as mock_data:
            
            mock_chains.return_value = {}
            mock_find.return_value = {}
            mock_data.return_value = {}
            
            # Test method signatures
            await get_options_chains(GetOptionsChainsArgs(symbol="AAPL"))
            mock_chains.assert_called_with("AAPL")
            
            await find_tradable_options(FindTradableOptionsArgs(symbol="AAPL"))
            mock_find.assert_called_with("AAPL", None, None)
            
            await get_option_market_data(GetOptionMarketDataArgs(option_id="test"))
            mock_data.assert_called_with("test")