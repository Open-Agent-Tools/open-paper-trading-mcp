"""
Comprehensive unit tests for MCP options tools - complete implementation.

Tests all options tools with new signatures, parameter validation, TradingService integration,
error handling, response formatting, and the new position management functions.
"""

from datetime import datetime
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from pydantic import ValidationError

from app.mcp.options_tools import (
    FindOptionsArgs,
    OptionHistoricalsArgs,
    OptionMarketDataArgs,
    # Argument classes
    OptionsChainsArgs,
    aggregate_option_positions,
    all_option_positions,
    find_options,
    find_tradable_options,
    # Service functions
    get_mcp_trading_service,
    get_option_market_data,
    # Backward compatibility functions
    get_options_chains,
    open_option_positions,
    option_historicals,
    option_market_data,
    # New direct parameter functions
    options_chains,
    set_mcp_trading_service,
)


class TestOptionsToolsParameterValidation:
    """Test parameter validation for options tool arguments."""

    def test_options_chains_args_validation(self):
        """Test OptionsChainsArgs parameter validation."""
        # Valid args
        args = OptionsChainsArgs(symbol="AAPL")
        assert args.symbol == "AAPL"

        # Test required field
        with pytest.raises(ValidationError):
            OptionsChainsArgs()

        # Test empty symbol should be allowed (handled in tool)
        args = OptionsChainsArgs(symbol="")
        assert args.symbol == ""

    def test_find_options_args_validation(self):
        """Test FindOptionsArgs parameter validation."""
        # Valid args with only symbol
        args = FindOptionsArgs(symbol="AAPL")
        assert args.symbol == "AAPL"
        assert args.expiration_date is None
        assert args.option_type is None

        # Valid args with expiration date
        args = FindOptionsArgs(symbol="GOOGL", expiration_date="2024-12-20")
        assert args.symbol == "GOOGL"
        assert args.expiration_date == "2024-12-20"

        # Valid args with option type
        args = FindOptionsArgs(symbol="MSFT", option_type="call")
        assert args.symbol == "MSFT"
        assert args.option_type == "call"

        # Valid args with all fields
        args = FindOptionsArgs(
            symbol="TSLA", expiration_date="2024-12-20", option_type="put"
        )
        assert args.symbol == "TSLA"
        assert args.expiration_date == "2024-12-20"
        assert args.option_type == "put"

        # Test required field
        with pytest.raises(ValidationError):
            FindOptionsArgs()

    def test_option_market_data_args_validation(self):
        """Test OptionMarketDataArgs parameter validation."""
        # Valid args
        args = OptionMarketDataArgs(option_id="AAPL240119C00195000")
        assert args.option_id == "AAPL240119C00195000"

        # Test with numeric ID
        args = OptionMarketDataArgs(option_id="12345")
        assert args.option_id == "12345"

        # Test required field
        with pytest.raises(ValidationError):
            OptionMarketDataArgs()

    def test_option_historicals_args_validation(self):
        """Test OptionHistoricalsArgs parameter validation."""
        # Valid args with all required fields
        args = OptionHistoricalsArgs(
            symbol="AAPL",
            expiration_date="2024-12-20",
            strike_price=150.0,
            option_type="call",
        )
        assert args.symbol == "AAPL"
        assert args.expiration_date == "2024-12-20"
        assert args.strike_price == 150.0
        assert args.option_type == "call"
        assert args.interval == "day"  # Default
        assert args.span == "week"  # Default

        # Valid args with custom interval and span
        args = OptionHistoricalsArgs(
            symbol="GOOGL",
            expiration_date="2025-01-17",
            strike_price=2800.0,
            option_type="put",
            interval="hour",
            span="month",
        )
        assert args.interval == "hour"
        assert args.span == "month"

        # Test required fields
        with pytest.raises(ValidationError):
            OptionHistoricalsArgs()


class TestDirectParameterFunctions:
    """Test the new direct parameter functions (main API)."""

    @pytest.mark.asyncio
    async def test_options_chains_success(self):
        """Test successful options chain retrieval with direct parameters."""
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

        # Mock the trading service
        mock_service = AsyncMock()
        mock_service.get_formatted_options_chain.return_value = mock_result

        with patch(
            "app.mcp.options_tools.get_mcp_trading_service", return_value=mock_service
        ):
            result = await options_chains("AAPL")
            assert result == mock_result
            mock_service.get_formatted_options_chain.assert_called_once_with("AAPL")

    @pytest.mark.asyncio
    async def test_find_options_success(self):
        """Test successful tradable options search with direct parameters."""
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

        mock_service = AsyncMock()
        mock_service.find_tradable_options.return_value = mock_result

        with patch(
            "app.mcp.options_tools.get_mcp_trading_service", return_value=mock_service
        ):
            result = await find_options("AAPL", "2024-12-20", "call")
            assert result == mock_result
            mock_service.find_tradable_options.assert_called_once_with(
                "AAPL", "2024-12-20", "call"
            )

    @pytest.mark.asyncio
    async def test_option_market_data_success(self):
        """Test successful option market data retrieval with direct parameters."""
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

        mock_service = AsyncMock()
        mock_service.get_option_market_data.return_value = mock_result

        with patch(
            "app.mcp.options_tools.get_mcp_trading_service", return_value=mock_service
        ):
            result = await option_market_data("AAPL241220C00150000")
            assert result == mock_result
            mock_service.get_option_market_data.assert_called_once_with(
                "AAPL241220C00150000"
            )

    @pytest.mark.asyncio
    async def test_option_historicals_success(self):
        """Test successful option historical data retrieval."""
        # Mock the dependencies
        with (
            patch("app.mcp.options_tools.get_mcp_trading_service") as mock_get_service,
            patch("app.models.assets.Stock") as mock_stock,
            patch("app.models.assets.Option") as mock_option,
        ):
            # Setup mocks
            mock_service = AsyncMock()
            mock_get_service.return_value = mock_service
            mock_service.get_quote.return_value = MagicMock(price=150.0)

            mock_stock.return_value = MagicMock()
            mock_option_instance = MagicMock()
            mock_option_instance.symbol = "AAPL241220C00150000"
            mock_option.return_value = mock_option_instance

            # Test the function
            result = await option_historicals(
                "AAPL", "2024-12-20", 150.0, "call", "day", "week"
            )

            # Verify the result structure
            assert "option_symbol" in result
            assert "underlying_symbol" in result
            assert "strike_price" in result
            assert "expiration_date" in result
            assert "option_type" in result
            assert "interval" in result
            assert "span" in result
            assert "data" in result
            assert "data_source" in result

    @pytest.mark.asyncio
    async def test_option_historicals_validation_errors(self):
        """Test option_historicals input validation errors."""
        # Invalid option type
        result = await option_historicals(
            "AAPL", "2024-12-20", 150.0, "invalid", "day", "week"
        )
        assert "error" in result
        assert "Invalid option type" in result["error"]

        # Invalid interval
        result = await option_historicals(
            "AAPL", "2024-12-20", 150.0, "call", "invalid", "week"
        )
        assert "error" in result
        assert "Invalid interval" in result["error"]

        # Invalid span
        result = await option_historicals(
            "AAPL", "2024-12-20", 150.0, "call", "day", "invalid"
        )
        assert "error" in result
        assert "Invalid span" in result["error"]

        # Invalid date format
        result = await option_historicals(
            "AAPL", "invalid-date", 150.0, "call", "day", "week"
        )
        assert "error" in result
        assert "Invalid expiration date format" in result["error"]

    @pytest.mark.asyncio
    async def test_aggregate_option_positions_success(self):
        """Test successful aggregate option positions retrieval."""
        # Mock position data
        mock_positions = [
            MagicMock(
                symbol="AAPL241220C00150000",
                quantity=2,
                current_price=5.50,
                unrealized_pnl=100.0,
            ),
            MagicMock(
                symbol="GOOGL250117P02800000",
                quantity=1,
                current_price=25.00,
                unrealized_pnl=-50.0,
            ),
        ]

        # Mock the assets and the isinstance check within the function
        with (
            patch("app.mcp.options_tools.get_mcp_trading_service") as mock_get_service,
            patch("app.models.assets.asset_factory") as mock_asset_factory,
        ):
            mock_service = AsyncMock()
            mock_service.get_positions.return_value = mock_positions
            mock_get_service.return_value = mock_service

            # Create mock option assets
            mock_option1 = MagicMock()
            mock_option1.underlying.symbol = "AAPL"
            mock_option1.strike = 150.0
            mock_option1.expiration_date = datetime(2024, 12, 20).date()
            mock_option1.option_type = "CALL"
            mock_option1.get_days_to_expiration.return_value = 30

            mock_option2 = MagicMock()
            mock_option2.underlying.symbol = "GOOGL"
            mock_option2.strike = 2800.0
            mock_option2.expiration_date = datetime(2025, 1, 17).date()
            mock_option2.option_type = "PUT"
            mock_option2.get_days_to_expiration.return_value = 45

            def asset_factory_side_effect(symbol):
                if symbol == "AAPL241220C00150000":
                    return mock_option1
                elif symbol == "GOOGL250117P02800000":
                    return mock_option2
                return None

            mock_asset_factory.side_effect = asset_factory_side_effect

            # Mock the Option class check by patching isinstance locally in the function
            with patch("app.mcp.options_tools.isinstance") as mock_isinstance:

                def isinstance_side_effect(obj, class_type):
                    # Return True for our mock options when checking against Option class
                    return obj in [mock_option1, mock_option2]

                mock_isinstance.side_effect = isinstance_side_effect

                # Mock option quotes with Greeks
                mock_quote1 = MagicMock()
                mock_quote1.delta = 0.65
                mock_quote1.gamma = 0.02
                mock_quote1.theta = -0.15
                mock_quote1.vega = 0.12
                mock_quote1.rho = 0.08

                mock_quote2 = MagicMock()
                mock_quote2.delta = -0.35
                mock_quote2.gamma = 0.01
                mock_quote2.theta = -0.10
                mock_quote2.vega = 0.08
                mock_quote2.rho = -0.05

                async def get_enhanced_quote_side_effect(symbol):
                    if symbol == "AAPL241220C00150000":
                        return mock_quote1
                    elif symbol == "GOOGL250117P02800000":
                        return mock_quote2
                    return None

                mock_service.get_enhanced_quote.side_effect = (
                    get_enhanced_quote_side_effect
                )

                # Call the function
                result = await aggregate_option_positions()

                # Verify the result
                assert "timestamp" in result
                assert "total_option_positions" in result
                assert "total_market_value" in result
                assert "total_unrealized_pnl" in result
                assert "portfolio_greeks" in result
                assert "positions" in result
                assert "summary" in result

                assert result["total_option_positions"] == 2
                assert len(result["positions"]) == 2

    @pytest.mark.asyncio
    async def test_all_option_positions_success(self):
        """Test successful all option positions retrieval."""
        # Similar setup to aggregate test but with more detailed position data
        mock_positions = [
            MagicMock(
                symbol="AAPL241220C00150000",
                quantity=2,
                current_price=5.50,
                avg_price=5.00,
                unrealized_pnl=100.0,
            )
        ]

        with (
            patch("app.mcp.options_tools.get_mcp_trading_service") as mock_get_service,
            patch("app.models.assets.asset_factory") as mock_asset_factory,
        ):
            mock_service = AsyncMock()
            mock_service.get_positions.return_value = mock_positions
            mock_get_service.return_value = mock_service

            # Mock option asset
            mock_option = MagicMock()
            mock_option.underlying.symbol = "AAPL"
            mock_option.strike = 150.0
            mock_option.expiration_date = datetime(2024, 12, 20).date()
            mock_option.option_type = "CALL"
            mock_option.get_days_to_expiration.return_value = 30

            mock_asset_factory.return_value = mock_option

            # Mock the isinstance check
            with patch("app.mcp.options_tools.isinstance") as mock_isinstance:
                mock_isinstance.return_value = (
                    True  # Always return True for Option checks
                )

                # Mock quotes
                mock_option_quote = MagicMock()
                mock_option_quote.price = 5.50
                mock_option_quote.bid = 5.25
                mock_option_quote.ask = 5.75
                mock_option_quote.volume = 1000
                mock_option_quote.open_interest = 5000
                mock_option_quote.iv = 0.25
                mock_option_quote.delta = 0.65
                mock_option_quote.gamma = 0.02
                mock_option_quote.theta = -0.15
                mock_option_quote.vega = 0.12
                mock_option_quote.rho = 0.08
                mock_option_quote.quote_date = datetime.now()

                mock_underlying_quote = MagicMock()
                mock_underlying_quote.price = 155.0

                async def get_enhanced_quote_side_effect(symbol):
                    if symbol == "AAPL241220C00150000":
                        return mock_option_quote
                    elif symbol == "AAPL":
                        return mock_underlying_quote
                    return None

                mock_service.get_enhanced_quote.side_effect = (
                    get_enhanced_quote_side_effect
                )

                # Call the function
                result = await all_option_positions()

                # Verify the result
                assert "timestamp" in result
                assert "total_positions" in result
                assert "open_positions" in result
                assert "closed_positions" in result
                assert "total_market_value" in result
                assert "total_unrealized_pnl" in result
                assert "positions" in result

                assert len(result["positions"]) == 1
                position = result["positions"][0]
                assert "symbol" in position
                assert "underlying_symbol" in position
                assert "strike_price" in position
                assert "expiration_date" in position
                assert "option_type" in position
                assert "intrinsic_value" in position
                assert "time_value" in position
                assert "greeks" in position

    @pytest.mark.asyncio
    async def test_open_option_positions_success(self):
        """Test successful open option positions retrieval."""
        # Mock all_option_positions result
        mock_all_positions_result = {
            "positions": [
                {
                    "symbol": "AAPL241220C00150000",
                    "status": "open",
                    "quantity": 2,
                    "market_value": 1100.0,
                    "unrealized_pnl": 100.0,
                    "underlying_symbol": "AAPL",
                    "option_type": "call",
                    "days_to_expiration": 30,
                    "current_price": 5.50,
                    "unrealized_pnl_percent": 9.09,
                },
                {
                    "symbol": "GOOGL250117P02800000",
                    "status": "closed",
                    "quantity": 0,
                    "market_value": 0.0,
                    "unrealized_pnl": 0.0,
                    "underlying_symbol": "GOOGL",
                    "option_type": "put",
                    "days_to_expiration": 45,
                },
            ]
        }

        with patch(
            "app.mcp.options_tools.all_option_positions",
            return_value=mock_all_positions_result,
        ):
            result = await open_option_positions()

            # Verify the result
            assert "timestamp" in result
            assert "total_open_positions" in result
            assert "total_market_value" in result
            assert "total_unrealized_pnl" in result
            assert "positions" in result
            assert "positions_by_underlying" in result
            assert "summary" in result
            assert "risk_alerts" in result

            # Should only have open positions
            assert result["total_open_positions"] == 1
            assert len(result["positions"]) == 1
            assert result["positions"][0]["status"] == "open"

            # Check risk alerts
            assert "near_expiration" in result["risk_alerts"]
            assert "high_unrealized_loss" in result["risk_alerts"]


class TestBackwardCompatibilityFunctions:
    """Test backward compatibility wrapper functions."""

    @pytest.mark.asyncio
    async def test_get_options_chains_compatibility(self):
        """Test get_options_chains backward compatibility."""
        mock_result = {"underlying_symbol": "AAPL"}

        with patch(
            "app.mcp.options_tools.options_chains", return_value=mock_result
        ) as mock_func:
            args = OptionsChainsArgs(symbol="AAPL")
            result = await get_options_chains(args)

            assert result == mock_result
            mock_func.assert_called_once_with("AAPL")

    @pytest.mark.asyncio
    async def test_find_tradable_options_compatibility(self):
        """Test find_tradable_options backward compatibility."""
        mock_result = {"symbol": "AAPL", "options": []}

        with patch(
            "app.mcp.options_tools.find_options", return_value=mock_result
        ) as mock_func:
            args = FindOptionsArgs(
                symbol="AAPL", expiration_date="2024-12-20", option_type="call"
            )
            result = await find_tradable_options(args)

            assert result == mock_result
            mock_func.assert_called_once_with("AAPL", "2024-12-20", "call")

    @pytest.mark.asyncio
    async def test_get_option_market_data_compatibility(self):
        """Test get_option_market_data backward compatibility."""
        mock_result = {"option_id": "test"}

        with patch(
            "app.mcp.options_tools.option_market_data", return_value=mock_result
        ) as mock_func:
            args = OptionMarketDataArgs(option_id="AAPL241220C00150000")
            result = await get_option_market_data(args)

            assert result == mock_result
            mock_func.assert_called_once_with("AAPL241220C00150000")


class TestErrorHandling:
    """Test comprehensive error handling scenarios."""

    @pytest.mark.asyncio
    async def test_options_chains_service_error(self):
        """Test error handling in options_chains."""
        mock_service = AsyncMock()
        mock_service.get_formatted_options_chain.side_effect = Exception(
            "Service error"
        )

        with patch(
            "app.mcp.options_tools.get_mcp_trading_service", return_value=mock_service
        ):
            result = await options_chains("AAPL")
            assert "error" in result
            assert "Service error" in result["error"]

    @pytest.mark.asyncio
    async def test_find_options_service_error(self):
        """Test error handling in find_options."""
        mock_service = AsyncMock()
        mock_service.find_tradable_options.side_effect = ValueError(
            "Invalid parameters"
        )

        with patch(
            "app.mcp.options_tools.get_mcp_trading_service", return_value=mock_service
        ):
            result = await find_options("AAPL", "2024-12-20", "call")
            assert "error" in result
            assert "Invalid parameters" in result["error"]

    @pytest.mark.asyncio
    async def test_option_market_data_service_error(self):
        """Test error handling in option_market_data."""
        mock_service = AsyncMock()
        mock_service.get_option_market_data.side_effect = RuntimeError(
            "Data unavailable"
        )

        with patch(
            "app.mcp.options_tools.get_mcp_trading_service", return_value=mock_service
        ):
            result = await option_market_data("INVALID")
            assert "error" in result
            assert "Data unavailable" in result["error"]

    @pytest.mark.asyncio
    async def test_aggregate_option_positions_service_error(self):
        """Test error handling in aggregate_option_positions."""
        mock_service = AsyncMock()
        mock_service.get_positions.side_effect = Exception("Database error")

        with patch(
            "app.mcp.options_tools.get_mcp_trading_service", return_value=mock_service
        ):
            result = await aggregate_option_positions()
            assert "error" in result
            assert "Database error" in result["error"]

    @pytest.mark.asyncio
    async def test_open_option_positions_error_propagation(self):
        """Test error propagation in open_option_positions."""
        with patch(
            "app.mcp.options_tools.all_option_positions",
            return_value={"error": "Test error"},
        ):
            result = await open_option_positions()
            assert "error" in result
            assert "Test error" in result["error"]


class TestServiceManagement:
    """Test trading service management functions."""

    def test_set_and_get_mcp_trading_service(self):
        """Test setting and getting the trading service."""
        from app.services.trading_service import TradingService

        # Create mock service
        mock_service = MagicMock(spec=TradingService)

        # Set the service
        set_mcp_trading_service(mock_service)

        # Get the service
        retrieved_service = get_mcp_trading_service()
        assert retrieved_service is mock_service

    def test_get_mcp_trading_service_not_initialized(self):
        """Test getting trading service when not initialized."""
        # Reset the service to None
        set_mcp_trading_service(None)

        with pytest.raises(RuntimeError, match="TradingService not initialized"):
            get_mcp_trading_service()


class TestInputProcessing:
    """Test input processing and normalization."""

    @pytest.mark.asyncio
    async def test_symbol_normalization(self):
        """Test that symbols are properly normalized."""
        test_cases = [
            ("aapl", "AAPL"),
            ("  GOOGL  ", "GOOGL"),
            ("\tTSLA\n", "TSLA"),
            ("msft", "MSFT"),
        ]

        mock_service = AsyncMock()
        mock_service.get_formatted_options_chain.return_value = {
            "underlying_symbol": "TEST"
        }

        with patch(
            "app.mcp.options_tools.get_mcp_trading_service", return_value=mock_service
        ):
            for input_symbol, expected_symbol in test_cases:
                await options_chains(input_symbol)

                # Get the last call and verify the symbol was normalized
                last_call_args = mock_service.get_formatted_options_chain.call_args[0]
                assert last_call_args[0] == expected_symbol

    @pytest.mark.asyncio
    async def test_option_type_handling(self):
        """Test option type parameter handling."""
        test_cases = ["call", "put", None, "CALL", "PUT"]

        mock_service = AsyncMock()
        mock_service.find_tradable_options.return_value = {
            "symbol": "AAPL",
            "options": [],
        }

        with patch(
            "app.mcp.options_tools.get_mcp_trading_service", return_value=mock_service
        ):
            for option_type in test_cases:
                await find_options("AAPL", None, option_type)

                # Verify the option_type is passed through
                last_call_args = mock_service.find_tradable_options.call_args[0]
                assert last_call_args[2] == option_type


class TestSpecialCases:
    """Test options-specific edge cases and scenarios."""

    @pytest.mark.asyncio
    async def test_complex_option_symbols(self):
        """Test handling of complex option symbols."""
        complex_symbols = [
            "AAPL241220C00150000",  # Standard format
            "SPY250117P00400000",  # ETF option
            "QQQ241115C00350000",  # Another ETF
            "TSLA241220C00200000",  # High strike
        ]

        mock_service = AsyncMock()
        mock_service.get_option_market_data.return_value = {
            "option_id": "test",
            "valid": True,
        }

        with patch(
            "app.mcp.options_tools.get_mcp_trading_service", return_value=mock_service
        ):
            for symbol in complex_symbols:
                result = await option_market_data(symbol)

                # Should handle all complex symbols
                assert "option_id" in result or "error" in result
                mock_service.get_option_market_data.assert_called_with(symbol)

    @pytest.mark.asyncio
    async def test_near_expiration_detection(self):
        """Test detection of positions near expiration."""
        # Mock positions with various expiration dates
        mock_positions = [
            {
                "symbol": "AAPL_NEAR",
                "status": "open",
                "quantity": 1,
                "days_to_expiration": 3,  # Near expiration
                "market_value": 100.0,
                "unrealized_pnl": 10.0,
                "option_type": "call",
            },
            {
                "symbol": "AAPL_FAR",
                "status": "open",
                "quantity": 1,
                "days_to_expiration": 30,  # Not near expiration
                "market_value": 200.0,
                "unrealized_pnl": 20.0,
                "option_type": "put",
            },
        ]

        mock_all_positions_result = {"positions": mock_positions}

        with patch(
            "app.mcp.options_tools.all_option_positions",
            return_value=mock_all_positions_result,
        ):
            result = await open_option_positions()

            # Check that near expiration positions are detected
            near_exp_positions = result["risk_alerts"]["near_expiration"]
            assert len(near_exp_positions) == 1
            assert near_exp_positions[0]["symbol"] == "AAPL_NEAR"

    @pytest.mark.asyncio
    async def test_high_loss_detection(self):
        """Test detection of positions with high unrealized losses."""
        mock_positions = [
            {
                "symbol": "AAPL_LOSS",
                "status": "open",
                "quantity": 1,
                "unrealized_pnl_percent": -25.0,  # High loss
                "market_value": 100.0,
                "unrealized_pnl": -25.0,
                "option_type": "call",
            },
            {
                "symbol": "AAPL_GAIN",
                "status": "open",
                "quantity": 1,
                "unrealized_pnl_percent": 15.0,  # Gain
                "market_value": 200.0,
                "unrealized_pnl": 30.0,
                "option_type": "put",
            },
        ]

        mock_all_positions_result = {"positions": mock_positions}

        with patch(
            "app.mcp.options_tools.all_option_positions",
            return_value=mock_all_positions_result,
        ):
            result = await open_option_positions()

            # Check that high loss positions are detected
            high_loss_positions = result["risk_alerts"]["high_unrealized_loss"]
            assert len(high_loss_positions) == 1
            assert high_loss_positions[0]["symbol"] == "AAPL_LOSS"


class TestCoverageCompleteness:
    """Additional tests to ensure comprehensive coverage."""

    def test_module_imports(self):
        """Test module imports and structure."""
        from pydantic import BaseModel

        # Verify classes are Pydantic models
        assert issubclass(OptionsChainsArgs, BaseModel)
        assert issubclass(FindOptionsArgs, BaseModel)
        assert issubclass(OptionMarketDataArgs, BaseModel)
        assert issubclass(OptionHistoricalsArgs, BaseModel)

    def test_argument_model_fields(self):
        """Test argument model field definitions."""
        # Test field descriptions exist
        assert OptionsChainsArgs.model_fields["symbol"].description is not None
        assert FindOptionsArgs.model_fields["symbol"].description is not None
        assert FindOptionsArgs.model_fields["expiration_date"].description is not None
        assert FindOptionsArgs.model_fields["option_type"].description is not None
        assert OptionMarketDataArgs.model_fields["option_id"].description is not None
        assert OptionHistoricalsArgs.model_fields["symbol"].description is not None
        assert (
            OptionHistoricalsArgs.model_fields["expiration_date"].description
            is not None
        )
        assert (
            OptionHistoricalsArgs.model_fields["strike_price"].description is not None
        )
        assert OptionHistoricalsArgs.model_fields["option_type"].description is not None
        assert OptionHistoricalsArgs.model_fields["interval"].description is not None
        assert OptionHistoricalsArgs.model_fields["span"].description is not None

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
        assert option_historicals.__doc__ is not None
        assert aggregate_option_positions.__doc__ is not None
        assert all_option_positions.__doc__ is not None
        assert open_option_positions.__doc__ is not None

    @pytest.mark.asyncio
    async def test_edge_case_inputs(self):
        """Test edge case inputs."""
        mock_service = AsyncMock()
        mock_service.get_formatted_options_chain.return_value = {
            "underlying_symbol": "A"
        }

        with patch(
            "app.mcp.options_tools.get_mcp_trading_service", return_value=mock_service
        ):
            # Test single character symbol
            await options_chains("A")
            mock_service.get_formatted_options_chain.assert_called_with("A")

            # Test symbol with dots
            await options_chains("BRK.A")
            mock_service.get_formatted_options_chain.assert_called_with("BRK.A")

    def test_field_types_and_defaults(self):
        """Test field types and default values."""
        # Test FindOptionsArgs defaults
        args = FindOptionsArgs(symbol="AAPL")
        assert args.expiration_date is None
        assert args.option_type is None

        # Test OptionHistoricalsArgs defaults
        args = OptionHistoricalsArgs(
            symbol="AAPL",
            expiration_date="2024-12-20",
            strike_price=150.0,
            option_type="call",
        )
        assert args.interval == "day"
        assert args.span == "week"

        # Test field types
        assert isinstance(args.symbol, str)
        assert isinstance(args.expiration_date, str)
        assert isinstance(args.strike_price, float)
        assert isinstance(args.option_type, str)
        assert isinstance(args.interval, str)
        assert isinstance(args.span, str)

    @pytest.mark.asyncio
    async def test_concurrent_tool_calls(self):
        """Test that tools can be called concurrently."""
        import asyncio

        mock_service = AsyncMock()
        mock_service.get_formatted_options_chain.return_value = {
            "underlying_symbol": "TEST"
        }
        mock_service.find_tradable_options.return_value = {
            "symbol": "TEST",
            "options": [],
        }
        mock_service.get_option_market_data.return_value = {"option_id": "TEST"}

        with patch(
            "app.mcp.options_tools.get_mcp_trading_service", return_value=mock_service
        ):
            # Create multiple concurrent calls
            tasks = [
                options_chains("AAPL"),
                find_options("GOOGL", None, None),
                option_market_data("TEST123"),
            ]

            results = await asyncio.gather(*tasks)

            # All calls should succeed
            assert len(results) == 3
            assert "underlying_symbol" in results[0] or "error" in results[0]
            assert "symbol" in results[1] or "error" in results[1]
            assert "option_id" in results[2] or "error" in results[2]

    @pytest.mark.asyncio
    async def test_position_grouping_by_underlying(self):
        """Test position grouping by underlying symbol."""
        mock_positions = [
            {
                "symbol": "AAPL_1",
                "status": "open",
                "quantity": 1,
                "underlying_symbol": "AAPL",
                "market_value": 100.0,
                "option_type": "call",
            },
            {
                "symbol": "AAPL_2",
                "status": "open",
                "quantity": 1,
                "underlying_symbol": "AAPL",
                "market_value": 200.0,
                "option_type": "put",
            },
            {
                "symbol": "GOOGL_1",
                "status": "open",
                "quantity": 1,
                "underlying_symbol": "GOOGL",
                "market_value": 300.0,
                "option_type": "call",
            },
        ]

        mock_all_positions_result = {"positions": mock_positions}

        with patch(
            "app.mcp.options_tools.all_option_positions",
            return_value=mock_all_positions_result,
        ):
            result = await open_option_positions()

            # Check grouping by underlying
            grouped = result["positions_by_underlying"]
            assert "AAPL" in grouped
            assert "GOOGL" in grouped
            assert len(grouped["AAPL"]) == 2
            assert len(grouped["GOOGL"]) == 1

            # Check summary counts
            assert result["summary"]["underlyings_count"] == 2
