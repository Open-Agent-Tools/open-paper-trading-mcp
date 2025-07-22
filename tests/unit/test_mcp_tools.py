"""
Unit tests for app.mcp.tools module.

These tests verify that the MCP tools functions correctly interact with the trading service
and properly handle responses and errors.
"""

import json
from datetime import datetime
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from pydantic import ValidationError

from app.mcp.tools import (
    CreateOrderArgs,
    GetOrderArgs,
    CancelOrderArgs,
    GetPositionArgs,
    GetOptionsChainArgs,
    GetExpirationDatesArgs,
    CreateMultiLegOrderArgs,
    CalculateGreeksArgs,
    GetStrategyAnalysisArgs,
    SimulateExpirationArgs,
    FindTradableOptionsArgs,
    GetOptionMarketDataArgs,
    set_mcp_trading_service,
    get_mcp_trading_service,
    get_stock_quote,
    create_buy_order,
    create_sell_order,
    get_all_orders,
    get_order,
    cancel_order,
    get_portfolio,
    get_portfolio_summary,
    get_all_positions,
    get_position,
    get_options_chain,
    get_expiration_dates,
    create_multi_leg_order,
    calculate_option_greeks,
    get_strategy_analysis,
    simulate_option_expiration,
    find_tradable_options,
    get_option_market_data,
)
from app.schemas.orders import OrderCondition, OrderCreate, OrderType, Order
from app.schemas.positions import Portfolio, Position, PortfolioSummary


@pytest.fixture
def mock_mcp_trading_service():
    """Create a mock trading service for MCP tools."""
    mock_service = MagicMock()
    # Set up async methods as AsyncMock
    mock_service.get_quote = AsyncMock()
    mock_service.create_order = AsyncMock()
    mock_service.get_orders = AsyncMock()
    mock_service.get_order = AsyncMock()
    mock_service.cancel_order = AsyncMock()
    mock_service.get_portfolio = AsyncMock()
    mock_service.get_portfolio_summary = AsyncMock()
    mock_service.get_positions = AsyncMock()
    mock_service.get_position = AsyncMock()
    mock_service.get_formatted_options_chain = AsyncMock()
    mock_service.get_expiration_dates = AsyncMock()
    mock_service.create_multi_leg_order_from_request = AsyncMock()
    mock_service.calculate_greeks = AsyncMock()
    mock_service.analyze_portfolio_strategies = AsyncMock()
    mock_service.simulate_expiration = AsyncMock()
    mock_service.find_tradable_options = AsyncMock()
    mock_service.get_option_market_data = AsyncMock()
    
    # Set the mock service for MCP tools
    set_mcp_trading_service(mock_service)
    
    return mock_service


class TestMCPToolsSetup:
    """Tests for MCP tools setup functions."""
    
    def test_set_get_trading_service(self):
        """Test setting and getting the trading service."""
        # Create a mock service
        mock_service = MagicMock()
        
        # Set the mock service
        set_mcp_trading_service(mock_service)
        
        # Get the service
        service = get_mcp_trading_service()
        
        # Verify it's the same service
        assert service is mock_service
    
    def test_get_trading_service_not_initialized(self):
        """Test getting the trading service when not initialized."""
        # Set the trading service to None
        set_mcp_trading_service(None)
        
        # Verify that getting the service raises an error
        with pytest.raises(RuntimeError):
            get_mcp_trading_service()


class TestMCPStockQuote:
    """Tests for stock quote functions."""
    
    @pytest.mark.asyncio
    async def test_get_stock_quote_success(self, mock_mcp_trading_service):
        """Test successful stock quote retrieval."""
        # Arrange
        symbol = "AAPL"
        mock_quote = MagicMock()
        mock_quote.symbol = symbol
        mock_quote.price = 150.0
        mock_quote.change = 5.0
        mock_quote.change_percent = 3.33
        mock_quote.volume = 1000
        mock_quote.last_updated = datetime.now()
        
        mock_mcp_trading_service.get_quote.return_value = mock_quote
        
        # Act
        result = await get_stock_quote(GetQuoteArgs(symbol=symbol))
        result_dict = json.loads(result)
        
        # Assert
        mock_mcp_trading_service.get_quote.assert_called_once_with(symbol)
        assert result_dict["symbol"] == symbol
        assert result_dict["price"] == 150.0
        assert result_dict["change"] == 5.0
        assert result_dict["change_percent"] == 3.33
        assert result_dict["volume"] == 1000
        assert "last_updated" in result_dict
    
    @pytest.mark.asyncio
    async def test_get_stock_quote_error(self, mock_mcp_trading_service):
        """Test error handling in stock quote retrieval."""
        # Arrange
        symbol = "INVALID"
        mock_mcp_trading_service.get_quote.side_effect = Exception("Symbol not found")
        
        # Act
        result = await get_stock_quote(GetQuoteArgs(symbol=symbol))
        
        # Assert
        mock_mcp_trading_service.get_quote.assert_called_once_with(symbol)
        assert "Error getting quote" in result


class TestMCPOrderManagement:
    """Tests for order management functions."""
    
    @pytest.mark.asyncio
    async def test_create_buy_order_success(self, mock_mcp_trading_service):
        """Test successful buy order creation."""
        # Arrange
        args = CreateOrderArgs(
            symbol="AAPL",
            order_type=OrderType.BUY,
            quantity=10,
            price=150.0
        )
        
        mock_order = MagicMock()
        mock_order.id = "order123"
        mock_order.symbol = "AAPL"
        mock_order.order_type = OrderType.BUY
        mock_order.quantity = 10
        mock_order.price = 150.0
        mock_order.status = "pending"
        mock_order.created_at = datetime.now()
        
        mock_mcp_trading_service.create_order.return_value = mock_order
        
        # Act
        result = await create_buy_order(args)
        result_dict = json.loads(result)
        
        # Assert
        assert mock_mcp_trading_service.create_order.call_count == 1
        assert result_dict["id"] == "order123"
        assert result_dict["symbol"] == "AAPL"
        assert result_dict["order_type"] == "buy"
        assert result_dict["quantity"] == 10
        assert result_dict["price"] == 150.0
        assert result_dict["status"] == "pending"
        assert "created_at" in result_dict
    
    @pytest.mark.asyncio
    async def test_create_sell_order_success(self, mock_mcp_trading_service):
        """Test successful sell order creation."""
        # Arrange
        args = CreateOrderArgs(
            symbol="AAPL",
            order_type=OrderType.SELL,
            quantity=10,
            price=150.0
        )
        
        mock_order = MagicMock()
        mock_order.id = "order123"
        mock_order.symbol = "AAPL"
        mock_order.order_type = OrderType.SELL
        mock_order.quantity = 10
        mock_order.price = 150.0
        mock_order.status = "pending"
        mock_order.created_at = datetime.now()
        
        mock_mcp_trading_service.create_order.return_value = mock_order
        
        # Act
        result = await create_sell_order(args)
        result_dict = json.loads(result)
        
        # Assert
        assert mock_mcp_trading_service.create_order.call_count == 1
        assert result_dict["id"] == "order123"
        assert result_dict["symbol"] == "AAPL"
        assert result_dict["order_type"] == "sell"
        assert result_dict["quantity"] == 10
        assert result_dict["price"] == 150.0
        assert result_dict["status"] == "pending"
        assert "created_at" in result_dict
    
    @pytest.mark.asyncio
    async def test_create_order_error(self, mock_mcp_trading_service):
        """Test error handling in order creation."""
        # Arrange
        args = CreateOrderArgs(
            symbol="AAPL",
            order_type=OrderType.BUY,
            quantity=10,
            price=150.0
        )
        
        mock_mcp_trading_service.create_order.side_effect = Exception("Insufficient funds")
        
        # Act
        result = await create_buy_order(args)
        
        # Assert
        assert mock_mcp_trading_service.create_order.call_count == 1
        assert "Error creating buy order" in result
        assert "Insufficient funds" in result
    
    @pytest.mark.asyncio
    async def test_get_all_orders_success(self, mock_mcp_trading_service):
        """Test successful retrieval of all orders."""
        # Arrange
        mock_order1 = MagicMock()
        mock_order1.id = "order1"
        mock_order1.symbol = "AAPL"
        mock_order1.order_type = OrderType.BUY
        mock_order1.quantity = 10
        mock_order1.price = 150.0
        mock_order1.status = "filled"
        mock_order1.created_at = datetime.now()
        mock_order1.filled_at = datetime.now()
        
        mock_order2 = MagicMock()
        mock_order2.id = "order2"
        mock_order2.symbol = "GOOGL"
        mock_order2.order_type = OrderType.SELL
        mock_order2.quantity = 5
        mock_order2.price = 2800.0
        mock_order2.status = "pending"
        mock_order2.created_at = datetime.now()
        mock_order2.filled_at = None
        
        mock_mcp_trading_service.get_orders.return_value = [mock_order1, mock_order2]
        
        # Act
        result = await get_all_orders()
        result_list = json.loads(result)
        
        # Assert
        mock_mcp_trading_service.get_orders.assert_called_once()
        assert len(result_list) == 2
        assert result_list[0]["id"] == "order1"
        assert result_list[0]["symbol"] == "AAPL"
        assert result_list[1]["id"] == "order2"
        assert result_list[1]["symbol"] == "GOOGL"
    
    @pytest.mark.asyncio
    async def test_get_order_success(self, mock_mcp_trading_service):
        """Test successful retrieval of a specific order."""
        # Arrange
        order_id = "order123"
        
        mock_order = MagicMock()
        mock_order.id = order_id
        mock_order.symbol = "AAPL"
        mock_order.order_type = OrderType.BUY
        mock_order.quantity = 10
        mock_order.price = 150.0
        mock_order.status = "filled"
        mock_order.created_at = datetime.now()
        mock_order.filled_at = datetime.now()
        
        mock_mcp_trading_service.get_order.return_value = mock_order
        
        # Act
        result = await get_order(GetOrderArgs(order_id=order_id))
        result_dict = json.loads(result)
        
        # Assert
        mock_mcp_trading_service.get_order.assert_called_once_with(order_id)
        assert result_dict["id"] == order_id
        assert result_dict["symbol"] == "AAPL"
        assert result_dict["order_type"] == "buy"
        assert result_dict["quantity"] == 10
        assert result_dict["price"] == 150.0
        assert result_dict["status"] == "filled"
        assert "created_at" in result_dict
        assert "filled_at" in result_dict
    
    @pytest.mark.asyncio
    async def test_cancel_order_success(self, mock_mcp_trading_service):
        """Test successful order cancellation."""
        # Arrange
        order_id = "order123"
        
        mock_mcp_trading_service.cancel_order.return_value = {
            "message": "Order cancelled successfully"
        }
        
        # Act
        result = await cancel_order(CancelOrderArgs(order_id=order_id))
        result_dict = json.loads(result)
        
        # Assert
        mock_mcp_trading_service.cancel_order.assert_called_once_with(order_id)
        assert result_dict["message"] == "Order cancelled successfully"


class TestMCPPortfolio:
    """Tests for portfolio management functions."""
    
    @pytest.mark.asyncio
    async def test_get_portfolio_success(self, mock_mcp_trading_service):
        """Test successful portfolio retrieval."""
        # Arrange
        mock_position1 = Position(
            symbol="AAPL",
            quantity=10,
            avg_price=150.0,
            current_price=155.0,
            unrealized_pnl=50.0,
            realized_pnl=0.0
        )
        
        mock_position2 = Position(
            symbol="GOOGL",
            quantity=5,
            avg_price=2800.0,
            current_price=2850.0,
            unrealized_pnl=250.0,
            realized_pnl=0.0
        )
        
        mock_portfolio = Portfolio(
            cash_balance=10000.0,
            positions=[mock_position1, mock_position2],
            total_value=25000.0,
            daily_pnl=300.0,
            total_pnl=300.0
        )
        
        mock_mcp_trading_service.get_portfolio.return_value = mock_portfolio
        
        # Act
        result = await get_portfolio()
        result_dict = json.loads(result)
        
        # Assert
        mock_mcp_trading_service.get_portfolio.assert_called_once()
        assert result_dict["cash_balance"] == 10000.0
        assert result_dict["total_value"] == 25000.0
        assert result_dict["daily_pnl"] == 300.0
        assert result_dict["total_pnl"] == 300.0
        assert len(result_dict["positions"]) == 2
        assert result_dict["positions"][0]["symbol"] == "AAPL"
        assert result_dict["positions"][1]["symbol"] == "GOOGL"
    
    @pytest.mark.asyncio
    async def test_get_portfolio_summary_success(self, mock_mcp_trading_service):
        """Test successful portfolio summary retrieval."""
        # Arrange
        mock_summary = PortfolioSummary(
            total_value=25000.0,
            cash_balance=10000.0,
            invested_value=15000.0,
            daily_pnl=300.0,
            daily_pnl_percent=2.0,
            total_pnl=1000.0,
            total_pnl_percent=4.0
        )
        
        mock_mcp_trading_service.get_portfolio_summary.return_value = mock_summary
        
        # Act
        result = await get_portfolio_summary()
        result_dict = json.loads(result)
        
        # Assert
        mock_mcp_trading_service.get_portfolio_summary.assert_called_once()
        assert result_dict["total_value"] == 25000.0
        assert result_dict["cash_balance"] == 10000.0
        assert result_dict["invested_value"] == 15000.0
        assert result_dict["daily_pnl"] == 300.0
        assert result_dict["daily_pnl_percent"] == 2.0
        assert result_dict["total_pnl"] == 1000.0
        assert result_dict["total_pnl_percent"] == 4.0
    
    @pytest.mark.asyncio
    async def test_get_all_positions_success(self, mock_mcp_trading_service):
        """Test successful retrieval of all positions."""
        # Arrange
        mock_position1 = Position(
            symbol="AAPL",
            quantity=10,
            avg_price=150.0,
            current_price=155.0,
            unrealized_pnl=50.0,
            realized_pnl=0.0
        )
        
        mock_position2 = Position(
            symbol="GOOGL",
            quantity=5,
            avg_price=2800.0,
            current_price=2850.0,
            unrealized_pnl=250.0,
            realized_pnl=0.0
        )
        
        mock_mcp_trading_service.get_positions.return_value = [mock_position1, mock_position2]
        
        # Act
        result = await get_all_positions()
        result_list = json.loads(result)
        
        # Assert
        mock_mcp_trading_service.get_positions.assert_called_once()
        assert len(result_list) == 2
        assert result_list[0]["symbol"] == "AAPL"
        assert result_list[0]["quantity"] == 10
        assert result_list[0]["avg_price"] == 150.0
        assert result_list[0]["current_price"] == 155.0
        assert result_list[0]["unrealized_pnl"] == 50.0
        assert result_list[1]["symbol"] == "GOOGL"
    
    @pytest.mark.asyncio
    async def test_get_position_success(self, mock_mcp_trading_service):
        """Test successful retrieval of a specific position."""
        # Arrange
        symbol = "AAPL"
        
        mock_position = Position(
            symbol=symbol,
            quantity=10,
            avg_price=150.0,
            current_price=155.0,
            unrealized_pnl=50.0,
            realized_pnl=0.0
        )
        
        mock_mcp_trading_service.get_position.return_value = mock_position
        
        # Act
        result = await get_position(GetPositionArgs(symbol=symbol))
        result_dict = json.loads(result)
        
        # Assert
        mock_mcp_trading_service.get_position.assert_called_once_with(symbol)
        assert result_dict["symbol"] == symbol
        assert result_dict["quantity"] == 10
        assert result_dict["avg_price"] == 150.0
        assert result_dict["current_price"] == 155.0
        assert result_dict["unrealized_pnl"] == 50.0


class TestMCPOptionsTools:
    """Tests for options trading functions."""
    
    @pytest.mark.asyncio
    async def test_get_options_chain_success(self, mock_mcp_trading_service):
        """Test successful options chain retrieval."""
        # Arrange
        symbol = "AAPL"
        expiration_date = "2024-01-19"
        min_strike = 140.0
        max_strike = 160.0
        
        mock_chain = {
            "underlying_symbol": symbol,
            "expiration_date": expiration_date,
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
            ]
        }
        
        mock_mcp_trading_service.get_formatted_options_chain.return_value = mock_chain
        
        # Act
        result = await get_options_chain(GetOptionsChainArgs(
            symbol=symbol,
            expiration_date=expiration_date,
            min_strike=min_strike,
            max_strike=max_strike
        ))
        result_dict = json.loads(result)
        
        # Assert
        mock_mcp_trading_service.get_formatted_options_chain.assert_called_once()
        assert result_dict["underlying_symbol"] == symbol
        assert result_dict["expiration_date"] == expiration_date
        assert result_dict["underlying_price"] == 150.0
        assert len(result_dict["calls"]) == 3
        assert len(result_dict["puts"]) == 3
    
    @pytest.mark.asyncio
    async def test_get_expiration_dates_success(self, mock_mcp_trading_service):
        """Test successful expiration dates retrieval."""
        # Arrange
        symbol = "AAPL"
        
        mock_dates = [
            datetime(2024, 1, 19).date(),
            datetime(2024, 2, 16).date(),
            datetime(2024, 3, 15).date(),
        ]
        
        mock_mcp_trading_service.get_expiration_dates.return_value = mock_dates
        
        # Act
        result = await get_expiration_dates(GetExpirationDatesArgs(symbol=symbol))
        result_dict = json.loads(result)
        
        # Assert
        mock_mcp_trading_service.get_expiration_dates.assert_called_once_with(symbol)
        assert result_dict["underlying_symbol"] == symbol
        assert len(result_dict["expiration_dates"]) == 3
        assert result_dict["count"] == 3
        assert "2024-01-19" in result_dict["expiration_dates"]
        assert "2024-02-16" in result_dict["expiration_dates"]
        assert "2024-03-15" in result_dict["expiration_dates"]
    
    @pytest.mark.asyncio
    async def test_create_multi_leg_order_success(self, mock_mcp_trading_service):
        """Test successful multi-leg order creation."""
        # Arrange
        legs = [
            {"symbol": "AAPL240119C00150000", "quantity": 1, "side": "buy"},
            {"symbol": "AAPL240119C00155000", "quantity": 1, "side": "sell"},
        ]
        order_type = "limit"
        
        mock_order = MagicMock()
        mock_order.id = "spread123"
        mock_order.net_price = 2.5
        mock_order.status = "filled"
        mock_order.created_at = datetime.now()
        
        mock_leg1 = MagicMock()
        mock_leg1.asset.symbol = "AAPL240119C00150000"
        mock_leg1.quantity = 1
        mock_leg1.order_type = "buy"
        mock_leg1.price = 5.0
        
        mock_leg2 = MagicMock()
        mock_leg2.asset.symbol = "AAPL240119C00155000"
        mock_leg2.quantity = 1
        mock_leg2.order_type = "sell"
        mock_leg2.price = 2.5
        
        mock_order.legs = [mock_leg1, mock_leg2]
        
        mock_mcp_trading_service.create_multi_leg_order_from_request.return_value = mock_order
        
        # Act
        result = await create_multi_leg_order(CreateMultiLegOrderArgs(
            legs=legs,
            order_type=order_type
        ))
        result_dict = json.loads(result)
        
        # Assert
        mock_mcp_trading_service.create_multi_leg_order_from_request.assert_called_once_with(
            legs, order_type
        )
        assert result_dict["id"] == "spread123"
        assert result_dict["net_price"] == 2.5
        assert result_dict["status"] == "filled"
        assert len(result_dict["legs"]) == 2
        assert result_dict["legs"][0]["symbol"] == "AAPL240119C00150000"
        assert result_dict["legs"][1]["symbol"] == "AAPL240119C00155000"
    
    @pytest.mark.asyncio
    async def test_calculate_option_greeks_success(self, mock_mcp_trading_service):
        """Test successful option Greeks calculation."""
        # Arrange
        option_symbol = "AAPL240119C00150000"
        underlying_price = 155.0
        
        mock_greeks = {
            "delta": 0.65,
            "gamma": 0.05,
            "theta": -0.1,
            "vega": 0.2,
            "rho": 0.05,
        }
        
        mock_mcp_trading_service.calculate_greeks.return_value = mock_greeks
        
        # Mock asset_factory to return a mock Option
        mock_option = MagicMock()
        mock_option.underlying.symbol = "AAPL"
        mock_option.strike = 150.0
        mock_option.expiration_date = datetime(2024, 1, 19).date()
        mock_option.option_type = "CALL"
        mock_option.get_days_to_expiration.return_value = 30
        
        with patch("app.mcp.tools.asset_factory", return_value=mock_option):
            # Act
            result = await calculate_option_greeks(CalculateGreeksArgs(
                option_symbol=option_symbol,
                underlying_price=underlying_price
            ))
            result_dict = json.loads(result)
            
            # Assert
            mock_mcp_trading_service.calculate_greeks.assert_called_once_with(
                option_symbol, underlying_price=underlying_price
            )
            assert result_dict["option_symbol"] == option_symbol
            assert result_dict["underlying_symbol"] == "AAPL"
            assert result_dict["strike"] == 150.0
            assert result_dict["expiration_date"] == "2024-01-19"
            assert result_dict["option_type"] == "call"
            assert result_dict["days_to_expiration"] == 30
            assert result_dict["delta"] == 0.65
            assert result_dict["gamma"] == 0.05
            assert result_dict["theta"] == -0.1
            assert result_dict["vega"] == 0.2
            assert result_dict["rho"] == 0.05
    
    @pytest.mark.asyncio
    async def test_get_strategy_analysis_success(self, mock_mcp_trading_service):
        """Test successful strategy analysis."""
        # Arrange
        include_greeks = True
        include_pnl = True
        include_recommendations = True
        
        mock_analysis = {
            "total_positions": 5,
            "total_strategies": 2,
            "strategies": [
                {"strategy_type": "long_call", "quantity": 1},
                {"strategy_type": "bull_spread", "quantity": 1},
            ],
            "summary": {"long_call": 1, "bull_spread": 1},
            "greeks": {"delta": 0.75, "gamma": 0.1, "theta": -0.2},
            "pnl": {"unrealized": 500.0, "realized": 0.0},
            "recommendations": ["Consider taking profits on long call"],
        }
        
        mock_mcp_trading_service.analyze_portfolio_strategies.return_value = mock_analysis
        
        # Act
        result = await get_strategy_analysis(GetStrategyAnalysisArgs(
            include_greeks=include_greeks,
            include_pnl=include_pnl,
            include_recommendations=include_recommendations
        ))
        result_dict = json.loads(result)
        
        # Assert
        mock_mcp_trading_service.analyze_portfolio_strategies.assert_called_once_with(
            include_greeks=include_greeks,
            include_pnl=include_pnl,
            include_complex_strategies=True,
            include_recommendations=include_recommendations
        )
        assert result_dict["total_positions"] == 5
        assert result_dict["total_strategies"] == 2
        assert len(result_dict["strategies"]) == 2
        assert "greeks" in result_dict
        assert "pnl" in result_dict
        assert "recommendations" in result_dict
    
    @pytest.mark.asyncio
    async def test_simulate_option_expiration_success(self, mock_mcp_trading_service):
        """Test successful option expiration simulation."""
        # Arrange
        processing_date = "2024-01-19"
        dry_run = True
        
        mock_result = {
            "processing_date": processing_date,
            "expiring_positions": 2,
            "total_impact": 500.0,
            "positions_processed": [
                {"symbol": "AAPL240119C00150000", "result": "exercised", "pnl": 300.0},
                {"symbol": "AAPL240119P00145000", "result": "expired", "pnl": 200.0},
            ],
            "dry_run": dry_run,
        }
        
        mock_mcp_trading_service.simulate_expiration.return_value = mock_result
        
        # Act
        result = await simulate_option_expiration(SimulateExpirationArgs(
            processing_date=processing_date,
            dry_run=dry_run
        ))
        result_dict = json.loads(result)
        
        # Assert
        mock_mcp_trading_service.simulate_expiration.assert_called_once_with(
            processing_date=processing_date,
            dry_run=dry_run
        )
        assert result_dict["processing_date"] == processing_date
        assert result_dict["expiring_positions"] == 2
        assert result_dict["total_impact"] == 500.0
        assert len(result_dict["positions_processed"]) == 2
        assert result_dict["dry_run"] == dry_run
    
    @pytest.mark.asyncio
    async def test_find_tradable_options_success(self, mock_mcp_trading_service):
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
        
        mock_mcp_trading_service.find_tradable_options.return_value = mock_result
        
        # Act
        result = await find_tradable_options(FindTradableOptionsArgs(
            symbol=symbol,
            expiration_date=expiration_date,
            option_type=option_type
        ))
        result_dict = json.loads(result)
        
        # Assert
        mock_mcp_trading_service.find_tradable_options.assert_called_once_with(
            symbol, expiration_date, option_type
        )
        assert result_dict["symbol"] == symbol
        assert result_dict["total_found"] == 10
        assert len(result_dict["options"]) == 2
        assert result_dict["expiration_date"] == expiration_date
        assert result_dict["option_type"] == option_type
    
    @pytest.mark.asyncio
    async def test_get_option_market_data_success(self, mock_mcp_trading_service):
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
        
        mock_mcp_trading_service.get_option_market_data.return_value = mock_result
        
        # Act
        result = await get_option_market_data(GetOptionMarketDataArgs(option_id=option_id))
        result_dict = json.loads(result)
        
        # Assert
        mock_mcp_trading_service.get_option_market_data.assert_called_once_with(option_id)
        assert result_dict["option_id"] == option_id
        assert result_dict["underlying_symbol"] == "AAPL"
        assert result_dict["strike"] == 150.0
        assert result_dict["expiration_date"] == "2024-01-19"
        assert result_dict["option_type"] == "call"
        assert result_dict["bid_price"] == 5.0
        assert result_dict["ask_price"] == 5.2
        assert "delta" in result_dict
        assert "gamma" in result_dict
        assert "theta" in result_dict
        assert "vega" in result_dict
        assert "rho" in result_dict