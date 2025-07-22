"""
Unit tests for app.mcp.options_tools module.

These tests verify that the MCP options tools functions correctly interact with the trading service
and properly handle responses and errors.
"""

from unittest.mock import MagicMock, patch

import pytest

from app.mcp.options_tools import (
    GetOptionsChainsArgs,
    FindTradableOptionsArgs,
    GetOptionMarketDataArgs,
    get_options_chains,
    find_tradable_options,
    get_option_market_data,
)


class TestMCPOptionsTools:
    """Tests for MCP options tools."""

    @pytest.mark.asyncio
    async def test_get_options_chains_success(self, mock_trading_service):
        """Test successful options chains retrieval."""
        # Arrange
        symbol = "AAPL"
        mock_result = {
            "underlying_symbol": symbol,
            "expiration_dates": ["2024-01-19", "2024-02-16", "2024-03-15"],
            "underlying_price": 150.0,
            "calls": [
                {"strike": 145.0, "bid": 6.0, "ask": 6.2, "volume": 1000},
                {"strike": 150.0, "bid": 3.0, "ask": 3.2, "volume": 2000},
                {"strike": 155.0, "bid": 1.0, "ask": 1.2, "volume": 1500},
            ],
            "puts": [
                {"strike": 145.0, "bid": 1.0, "ask": 1.2, "volume": 800},
                {"strike": 150.0, "bid": 3.0, "ask": 3.2, "volume": 1800},
                {"strike": 155.0, "bid": 6.0, "ask": 6.2, "volume": 1200},
            ],
        }
        mock_trading_service.get_formatted_options_chain.return_value = mock_result

        # Act
        result = await get_options_chains(GetOptionsChainsArgs(symbol=symbol))

        # Assert
        mock_trading_service.get_formatted_options_chain.assert_called_once_with(symbol.strip().upper())
        assert result == mock_result
        assert result["underlying_symbol"] == symbol
        assert len(result["calls"]) == 3
        assert len(result["puts"]) == 3

    @pytest.mark.asyncio
    async def test_get_options_chains_error(self, mock_trading_service):
        """Test error handling in options chains retrieval."""
        # Arrange
        symbol = "INVALID"
        mock_trading_service.get_formatted_options_chain.side_effect = Exception("Symbol not found")

        # Act
        result = await get_options_chains(GetOptionsChainsArgs(symbol=symbol))

        # Assert
        mock_trading_service.get_formatted_options_chain.assert_called_once_with(symbol.strip().upper())
        assert "error" in result
        assert "Symbol not found" in result["error"]

    @pytest.mark.asyncio
    async def test_find_tradable_options_success(self, mock_trading_service):
        """Test successful tradable options search."""
        # Arrange
        symbol = "AAPL"
        expiration_date = "2024-01-19"
        option_type = "call"
        
        mock_result = {
            "symbol": symbol,
            "total_found": 10,
            "options": [
                {"symbol": "AAPL240119C00145000", "strike": 145.0, "bid": 10.0, "ask": 10.2},
                {"symbol": "AAPL240119C00150000", "strike": 150.0, "bid": 5.0, "ask": 5.2},
            ],
            "expiration_date": expiration_date,
            "option_type": option_type,
        }
        
        mock_trading_service.find_tradable_options.return_value = mock_result
        
        # Act
        result = await find_tradable_options(FindTradableOptionsArgs(
            symbol=symbol,
            expiration_date=expiration_date,
            option_type=option_type
        ))
        
        # Assert
        mock_trading_service.find_tradable_options.assert_called_once_with(
            symbol.strip().upper(), expiration_date, option_type
        )
        assert result == mock_result
        assert result["symbol"] == symbol
        assert result["total_found"] == 10
        assert len(result["options"]) == 2
        assert result["expiration_date"] == expiration_date
        assert result["option_type"] == option_type

    @pytest.mark.asyncio
    async def test_find_tradable_options_error(self, mock_trading_service):
        """Test error handling in tradable options search."""
        # Arrange
        symbol = "INVALID"
        expiration_date = "2024-01-19"
        option_type = "call"
        
        mock_trading_service.find_tradable_options.side_effect = Exception("Symbol not found")
        
        # Act
        result = await find_tradable_options(FindTradableOptionsArgs(
            symbol=symbol,
            expiration_date=expiration_date,
            option_type=option_type
        ))
        
        # Assert
        mock_trading_service.find_tradable_options.assert_called_once_with(
            symbol.strip().upper(), expiration_date, option_type
        )
        assert "error" in result
        assert "Symbol not found" in result["error"]

    @pytest.mark.asyncio
    async def test_get_option_market_data_success(self, mock_trading_service):
        """Test successful option market data retrieval."""
        # Arrange
        option_id = "AAPL240119C00150000"
        
        mock_result = {
            "option_id": option_id,
            "underlying_symbol": "AAPL",
            "strike": 150.0,
            "expiration_date": "2024-01-19",
            "option_type": "call",
            "bid_price": 5.0,
            "ask_price": 5.2,
            "last_price": 5.1,
            "volume": 1000,
            "open_interest": 5000,
            "implied_volatility": 0.3,
            "delta": 0.65,
            "gamma": 0.05,
            "theta": -0.1,
            "vega": 0.2,
            "rho": 0.05,
        }
        
        mock_trading_service.get_option_market_data.return_value = mock_result
        
        # Act
        result = await get_option_market_data(GetOptionMarketDataArgs(option_id=option_id))
        
        # Assert
        mock_trading_service.get_option_market_data.assert_called_once_with(option_id)
        assert result == mock_result
        assert result["option_id"] == option_id
        assert result["underlying_symbol"] == "AAPL"
        assert result["strike"] == 150.0
        assert result["expiration_date"] == "2024-01-19"
        assert result["option_type"] == "call"
        assert result["bid_price"] == 5.0
        assert result["ask_price"] == 5.2
        assert "delta" in result
        assert "gamma" in result
        assert "theta" in result
        assert "vega" in result
        assert "rho" in result

    @pytest.mark.asyncio
    async def test_get_option_market_data_error(self, mock_trading_service):
        """Test error handling in option market data retrieval."""
        # Arrange
        option_id = "INVALID"
        
        mock_trading_service.get_option_market_data.side_effect = Exception("Option not found")
        
        # Act
        result = await get_option_market_data(GetOptionMarketDataArgs(option_id=option_id))
        
        # Assert
        mock_trading_service.get_option_market_data.assert_called_once_with(option_id)
        assert "error" in result
        assert "Option not found" in result["error"]
