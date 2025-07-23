"""
Comprehensive unit tests for MCP trading tools.

Tests async tool functions, parameter validation, TradingService integration,
error handling, response formatting, and options trading functionality.
"""

import json
from datetime import datetime, date
from decimal import Decimal
from unittest.mock import AsyncMock, Mock, patch, MagicMock
from typing import Any

import pytest
import pytest_asyncio
from pydantic import ValidationError

from app.mcp.tools import (
    # Service management
    set_mcp_trading_service,
    get_mcp_trading_service,
    
    # Argument models
    GetQuoteArgs,
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
    
    # Tool functions
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
from app.schemas.orders import OrderCondition, OrderStatus, OrderType
from app.services.trading_service import TradingService


class TestMCPServiceManagement:
    """Test MCP trading service management."""
    
    def test_set_and_get_trading_service(self):
        """Test setting and getting the trading service."""
        mock_service = Mock(spec=TradingService)
        
        # Set the service
        set_mcp_trading_service(mock_service)
        
        # Get the service
        service = get_mcp_trading_service()
        assert service is mock_service
    
    def test_get_trading_service_not_initialized(self):
        """Test getting trading service when not initialized."""
        # Reset the global service
        import app.mcp.tools as tools_module
        tools_module._trading_service = None
        
        with pytest.raises(RuntimeError) as exc_info:
            get_mcp_trading_service()
        
        assert "TradingService not initialized" in str(exc_info.value)
        
        # Clean up - set a mock service for other tests
        mock_service = Mock(spec=TradingService)
        set_mcp_trading_service(mock_service)


class TestMCPToolParameterValidation:
    """Test parameter validation for MCP tool arguments."""
    
    def test_get_quote_args_validation(self):
        """Test GetQuoteArgs parameter validation."""
        # Valid args
        args = GetQuoteArgs(symbol="AAPL")
        assert args.symbol == "AAPL"
        
        # Test required field
        with pytest.raises(ValidationError):
            GetQuoteArgs()
    
    def test_create_order_args_validation(self):
        """Test CreateOrderArgs parameter validation."""
        # Valid args
        args = CreateOrderArgs(
            symbol="AAPL",
            order_type=OrderType.BUY,
            quantity=100,
            price=150.50
        )
        assert args.symbol == "AAPL"
        assert args.order_type == OrderType.BUY
        assert args.quantity == 100
        assert args.price == 150.50
        
        # Test required fields
        with pytest.raises(ValidationError):
            CreateOrderArgs()
        
        # Test positive quantity validation
        with pytest.raises(ValidationError):
            CreateOrderArgs(symbol="AAPL", order_type=OrderType.BUY, quantity=0, price=100)
        
        # Test positive price validation
        with pytest.raises(ValidationError):
            CreateOrderArgs(symbol="AAPL", order_type=OrderType.BUY, quantity=100, price=0)
    
    def test_get_order_args_validation(self):
        """Test GetOrderArgs parameter validation."""
        args = GetOrderArgs(order_id="order_123")
        assert args.order_id == "order_123"
        
        with pytest.raises(ValidationError):
            GetOrderArgs()
    
    def test_cancel_order_args_validation(self):
        """Test CancelOrderArgs parameter validation."""
        args = CancelOrderArgs(order_id="order_123")
        assert args.order_id == "order_123"
        
        with pytest.raises(ValidationError):
            CancelOrderArgs()
    
    def test_get_position_args_validation(self):
        """Test GetPositionArgs parameter validation."""
        args = GetPositionArgs(symbol="AAPL")
        assert args.symbol == "AAPL"
        
        with pytest.raises(ValidationError):
            GetPositionArgs()
    
    def test_options_chain_args_validation(self):
        """Test GetOptionsChainArgs parameter validation."""
        # Valid args with minimal fields
        args = GetOptionsChainArgs(symbol="AAPL")
        assert args.symbol == "AAPL"
        assert args.expiration_date is None
        assert args.min_strike is None
        assert args.max_strike is None
        
        # Valid args with all fields
        args = GetOptionsChainArgs(
            symbol="AAPL",
            expiration_date="2024-12-20",
            min_strike=140.0,
            max_strike=160.0
        )
        assert args.expiration_date == "2024-12-20"
        assert args.min_strike == 140.0
        assert args.max_strike == 160.0
        
        with pytest.raises(ValidationError):
            GetOptionsChainArgs()
    
    def test_calculate_greeks_args_validation(self):
        """Test CalculateGreeksArgs parameter validation."""
        # Valid args
        args = CalculateGreeksArgs(option_symbol="AAPL240119C00195000")
        assert args.option_symbol == "AAPL240119C00195000"
        assert args.underlying_price is None
        
        # With underlying price
        args = CalculateGreeksArgs(
            option_symbol="AAPL240119C00195000",
            underlying_price=150.0
        )
        assert args.underlying_price == 150.0
        
        with pytest.raises(ValidationError):
            CalculateGreeksArgs()


class TestBasicTradingTools:
    """Test basic trading tool functions."""
    
    def setup_method(self):
        """Set up mock trading service for each test."""
        self.mock_service = AsyncMock(spec=TradingService)
        set_mcp_trading_service(self.mock_service)
    
    @pytest_asyncio.async
    async def test_get_stock_quote_success(self):
        """Test successful stock quote retrieval."""
        mock_quote = Mock()
        mock_quote.symbol = "AAPL"
        mock_quote.price = 150.25
        mock_quote.change = 2.50
        mock_quote.change_percent = 1.69
        mock_quote.volume = 1000000
        mock_quote.last_updated = datetime(2024, 1, 1, 10, 0, 0)
        
        self.mock_service.get_quote.return_value = mock_quote
        
        args = GetQuoteArgs(symbol="AAPL")
        result = await get_stock_quote(args)
        
        # Parse JSON result
        data = json.loads(result)
        assert data["symbol"] == "AAPL"
        assert data["price"] == 150.25
        assert data["change"] == 2.50
        assert data["change_percent"] == 1.69
        assert data["volume"] == 1000000
        assert "last_updated" in data
        
        self.mock_service.get_quote.assert_called_once_with("AAPL")
    
    @pytest_asyncio.async
    async def test_get_stock_quote_error(self):
        """Test stock quote error handling."""
        self.mock_service.get_quote.side_effect = Exception("Quote not found")
        
        args = GetQuoteArgs(symbol="INVALID")
        result = await get_stock_quote(args)
        
        assert "Error getting quote" in result
        assert "Quote not found" in result
    
    @pytest_asyncio.async
    async def test_create_buy_order_success(self):
        """Test successful buy order creation."""
        mock_order = Mock()
        mock_order.id = "order_123"
        mock_order.symbol = "AAPL"
        mock_order.order_type = OrderType.BUY
        mock_order.quantity = 100
        mock_order.price = 150.50
        mock_order.status = OrderStatus.PENDING
        mock_order.created_at = datetime(2024, 1, 1, 10, 0, 0)
        
        self.mock_service.create_order.return_value = mock_order
        
        args = CreateOrderArgs(
            symbol="AAPL",
            order_type=OrderType.BUY,
            quantity=100,
            price=150.50
        )
        result = await create_buy_order(args)
        
        # Parse JSON result
        data = json.loads(result)
        assert data["id"] == "order_123"
        assert data["symbol"] == "AAPL"
        assert data["order_type"] == OrderType.BUY
        assert data["quantity"] == 100
        assert data["price"] == 150.50
        assert data["status"] == OrderStatus.PENDING
        
        # Verify service call
        self.mock_service.create_order.assert_called_once()
        call_args = self.mock_service.create_order.call_args[0][0]
        assert call_args.symbol == "AAPL"
        assert call_args.order_type == OrderType.BUY
        assert call_args.quantity == 100
        assert call_args.price == 150.50
        assert call_args.condition == OrderCondition.MARKET
    
    @pytest_asyncio.async
    async def test_create_sell_order_success(self):
        """Test successful sell order creation."""
        mock_order = Mock()
        mock_order.id = "order_456"
        mock_order.symbol = "GOOGL"
        mock_order.order_type = OrderType.SELL
        mock_order.quantity = 50
        mock_order.price = 2800.00
        mock_order.status = OrderStatus.PENDING
        mock_order.created_at = datetime(2024, 1, 1, 11, 0, 0)
        
        self.mock_service.create_order.return_value = mock_order
        
        args = CreateOrderArgs(
            symbol="GOOGL",
            order_type=OrderType.SELL,
            quantity=50,
            price=2800.00
        )
        result = await create_sell_order(args)
        
        data = json.loads(result)
        assert data["order_type"] == OrderType.SELL
        assert data["symbol"] == "GOOGL"
        
        # Verify service call has correct order type
        call_args = self.mock_service.create_order.call_args[0][0]
        assert call_args.order_type == OrderType.SELL
    
    @pytest_asyncio.async
    async def test_get_all_orders_success(self):
        """Test successful retrieval of all orders."""
        mock_orders = [
            Mock(
                id="order_1",
                symbol="AAPL",
                order_type=OrderType.BUY,
                quantity=100,
                price=150.0,
                status=OrderStatus.FILLED,
                created_at=datetime(2024, 1, 1, 10, 0, 0),
                filled_at=datetime(2024, 1, 1, 10, 5, 0)
            ),
            Mock(
                id="order_2",
                symbol="GOOGL",
                order_type=OrderType.SELL,
                quantity=50,
                price=2800.0,
                status=OrderStatus.PENDING,
                created_at=datetime(2024, 1, 1, 11, 0, 0),
                filled_at=None
            )
        ]
        
        self.mock_service.get_orders.return_value = mock_orders
        
        result = await get_all_orders()
        
        data = json.loads(result)
        assert len(data) == 2
        assert data[0]["id"] == "order_1"
        assert data[0]["status"] == OrderStatus.FILLED
        assert data[1]["id"] == "order_2"
        assert data[1]["status"] == OrderStatus.PENDING
        assert data[1]["filled_at"] is None
    
    @pytest_asyncio.async
    async def test_get_order_success(self):
        """Test successful retrieval of specific order."""
        mock_order = Mock()
        mock_order.id = "order_123"
        mock_order.symbol = "AAPL"
        mock_order.order_type = OrderType.BUY
        mock_order.quantity = 100
        mock_order.price = 150.0
        mock_order.status = OrderStatus.FILLED
        mock_order.created_at = datetime(2024, 1, 1, 10, 0, 0)
        mock_order.filled_at = datetime(2024, 1, 1, 10, 5, 0)
        
        self.mock_service.get_order.return_value = mock_order
        
        args = GetOrderArgs(order_id="order_123")
        result = await get_order(args)
        
        data = json.loads(result)
        assert data["id"] == "order_123"
        assert data["status"] == OrderStatus.FILLED
        
        self.mock_service.get_order.assert_called_once_with("order_123")
    
    @pytest_asyncio.async
    async def test_cancel_order_success(self):
        """Test successful order cancellation."""
        mock_result = {"status": "cancelled", "order_id": "order_123"}
        self.mock_service.cancel_order.return_value = mock_result
        
        args = CancelOrderArgs(order_id="order_123")
        result = await cancel_order(args)
        
        data = json.loads(result)
        assert data["status"] == "cancelled"
        assert data["order_id"] == "order_123"
        
        self.mock_service.cancel_order.assert_called_once_with("order_123")


class TestPortfolioTools:
    """Test portfolio-related tool functions."""
    
    def setup_method(self):
        """Set up mock trading service for each test."""
        self.mock_service = AsyncMock(spec=TradingService)
        set_mcp_trading_service(self.mock_service)
    
    @pytest_asyncio.async
    async def test_get_portfolio_success(self):
        """Test successful portfolio retrieval."""
        # Create mock positions
        mock_position1 = Mock()
        mock_position1.symbol = "AAPL"
        mock_position1.quantity = 100
        mock_position1.avg_price = 145.0
        mock_position1.current_price = 150.0
        mock_position1.unrealized_pnl = 500.0
        mock_position1.realized_pnl = 0.0
        
        mock_position2 = Mock()
        mock_position2.symbol = "GOOGL"
        mock_position2.quantity = 50
        mock_position2.avg_price = 2750.0
        mock_position2.current_price = 2800.0
        mock_position2.unrealized_pnl = 2500.0
        mock_position2.realized_pnl = 1000.0
        
        # Create mock portfolio
        mock_portfolio = Mock()
        mock_portfolio.cash_balance = 50000.0
        mock_portfolio.total_value = 200000.0
        mock_portfolio.positions = [mock_position1, mock_position2]
        mock_portfolio.daily_pnl = 3000.0
        mock_portfolio.total_pnl = 10000.0
        
        self.mock_service.get_portfolio.return_value = mock_portfolio
        
        result = await get_portfolio()
        
        data = json.loads(result)
        assert data["cash_balance"] == 50000.0
        assert data["total_value"] == 200000.0
        assert len(data["positions"]) == 2
        assert data["positions"][0]["symbol"] == "AAPL"
        assert data["positions"][1]["symbol"] == "GOOGL"
        assert data["daily_pnl"] == 3000.0
        assert data["total_pnl"] == 10000.0
    
    @pytest_asyncio.async
    async def test_get_portfolio_summary_success(self):
        """Test successful portfolio summary retrieval."""
        mock_summary = Mock()
        mock_summary.total_value = 200000.0
        mock_summary.cash_balance = 50000.0
        mock_summary.invested_value = 150000.0
        mock_summary.daily_pnl = 3000.0
        mock_summary.daily_pnl_percent = 1.5
        mock_summary.total_pnl = 10000.0
        mock_summary.total_pnl_percent = 5.0
        
        self.mock_service.get_portfolio_summary.return_value = mock_summary
        
        result = await get_portfolio_summary()
        
        data = json.loads(result)
        assert data["total_value"] == 200000.0
        assert data["cash_balance"] == 50000.0
        assert data["invested_value"] == 150000.0
        assert data["daily_pnl_percent"] == 1.5
        assert data["total_pnl_percent"] == 5.0
    
    @pytest_asyncio.async
    async def test_get_all_positions_success(self):
        """Test successful retrieval of all positions."""
        mock_positions = [
            Mock(
                symbol="AAPL",
                quantity=100,
                avg_price=145.0,
                current_price=150.0,
                unrealized_pnl=500.0,
                realized_pnl=0.0
            ),
            Mock(
                symbol="GOOGL",
                quantity=50,
                avg_price=2750.0,
                current_price=2800.0,
                unrealized_pnl=2500.0,
                realized_pnl=1000.0
            )
        ]
        
        self.mock_service.get_positions.return_value = mock_positions
        
        result = await get_all_positions()
        
        data = json.loads(result)
        assert len(data) == 2
        assert data[0]["symbol"] == "AAPL"
        assert data[1]["symbol"] == "GOOGL"
    
    @pytest_asyncio.async
    async def test_get_position_success(self):
        """Test successful retrieval of specific position."""
        mock_position = Mock()
        mock_position.symbol = "AAPL"
        mock_position.quantity = 100
        mock_position.avg_price = 145.0
        mock_position.current_price = 150.0
        mock_position.unrealized_pnl = 500.0
        mock_position.realized_pnl = 0.0
        
        self.mock_service.get_position.return_value = mock_position
        
        args = GetPositionArgs(symbol="AAPL")
        result = await get_position(args)
        
        data = json.loads(result)
        assert data["symbol"] == "AAPL"
        assert data["quantity"] == 100
        assert data["unrealized_pnl"] == 500.0
        
        self.mock_service.get_position.assert_called_once_with("AAPL")


class TestOptionsTools:
    """Test options-related tool functions."""
    
    def setup_method(self):
        """Set up mock trading service for each test."""
        self.mock_service = Mock(spec=TradingService)
        set_mcp_trading_service(self.mock_service)
    
    def test_get_options_chain_success(self):
        """Test successful options chain retrieval."""
        mock_chain_data = {
            "underlying_symbol": "AAPL",
            "expiration_dates": ["2024-12-20"],
            "chains": {
                "2024-12-20": {
                    "calls": [{"strike": 150.0, "bid": 5.25, "ask": 5.50}],
                    "puts": [{"strike": 150.0, "bid": 2.10, "ask": 2.25}]
                }
            }
        }
        
        self.mock_service.get_formatted_options_chain.return_value = mock_chain_data
        
        # Test without filters
        args = GetOptionsChainArgs(symbol="AAPL")
        result = get_options_chain(args)
        
        data = json.loads(result)
        assert data["underlying_symbol"] == "AAPL"
        assert len(data["expiration_dates"]) == 1
        
        self.mock_service.get_formatted_options_chain.assert_called_with(
            "AAPL", expiration_date=None, min_strike=None, max_strike=None
        )
    
    def test_get_options_chain_with_filters(self):
        """Test options chain retrieval with filters."""
        mock_chain_data = {"underlying_symbol": "AAPL", "chains": {}}
        self.mock_service.get_formatted_options_chain.return_value = mock_chain_data
        
        args = GetOptionsChainArgs(
            symbol="AAPL",
            expiration_date="2024-12-20",
            min_strike=140.0,
            max_strike=160.0
        )
        result = get_options_chain(args)
        
        # Verify filters are converted properly
        call_args = self.mock_service.get_formatted_options_chain.call_args
        assert call_args[1]["expiration_date"] == date(2024, 12, 20)
        assert call_args[1]["min_strike"] == 140.0
        assert call_args[1]["max_strike"] == 160.0
    
    def test_get_expiration_dates_success(self):
        """Test successful expiration dates retrieval."""
        mock_dates = [date(2024, 12, 20), date(2025, 1, 17)]
        self.mock_service.get_expiration_dates.return_value = mock_dates
        
        args = GetExpirationDatesArgs(symbol="AAPL")
        result = get_expiration_dates(args)
        
        data = json.loads(result)
        assert data["underlying_symbol"] == "AAPL"
        assert len(data["expiration_dates"]) == 2
        assert data["expiration_dates"][0] == "2024-12-20"
        assert data["expiration_dates"][1] == "2025-01-17"
        assert data["count"] == 2
    
    @pytest_asyncio.async
    async def test_create_multi_leg_order_success(self):
        """Test successful multi-leg order creation."""
        # Mock asset for legs
        mock_asset = Mock()
        mock_asset.symbol = "AAPL240119C00195000"
        
        # Mock order leg
        mock_leg = Mock()
        mock_leg.asset = mock_asset
        mock_leg.quantity = 1
        mock_leg.order_type = OrderType.BUY
        mock_leg.price = 5.25
        
        # Mock multi-leg order
        mock_order = Mock()
        mock_order.id = "multi_order_123"
        mock_order.legs = [mock_leg]
        mock_order.net_price = 5.25
        mock_order.status = OrderStatus.PENDING
        mock_order.created_at = datetime(2024, 1, 1, 10, 0, 0)
        
        self.mock_service.create_multi_leg_order_from_request.return_value = mock_order
        
        legs_data = [
            {
                "symbol": "AAPL240119C00195000",
                "quantity": 1,
                "order_type": "buy",
                "price": 5.25
            }
        ]
        
        args = CreateMultiLegOrderArgs(legs=legs_data, order_type="limit")
        result = await create_multi_leg_order(args)
        
        data = json.loads(result)
        assert data["id"] == "multi_order_123"
        assert data["net_price"] == 5.25
        assert len(data["legs"]) == 1
        assert data["legs"][0]["symbol"] == "AAPL240119C00195000"
    
    @pytest_asyncio.async
    async def test_calculate_option_greeks_success(self):
        """Test successful option Greeks calculation."""
        mock_greeks = {
            "delta": 0.65,
            "gamma": 0.02,
            "theta": -0.15,
            "vega": 0.12,
            "rho": 0.08
        }
        
        # Mock the asset_factory
        with patch('app.mcp.tools.asset_factory') as mock_factory:
            mock_option = Mock()
            mock_option.underlying.symbol = "AAPL"
            mock_option.strike = 195.0
            mock_option.expiration_date = date(2024, 1, 19)
            mock_option.option_type = "CALL"
            mock_option.get_days_to_expiration.return_value = 30
            
            mock_factory.return_value = mock_option
            
            self.mock_service.calculate_greeks = AsyncMock(return_value=mock_greeks)
            
            args = CalculateGreeksArgs(option_symbol="AAPL240119C00195000")
            result = await calculate_option_greeks(args)
            
            data = json.loads(result)
            assert data["delta"] == 0.65
            assert data["option_symbol"] == "AAPL240119C00195000"
            assert data["underlying_symbol"] == "AAPL"
            assert data["strike"] == 195.0
            assert data["option_type"] == "call"
    
    @pytest_asyncio.async
    async def test_get_strategy_analysis_success(self):
        """Test successful strategy analysis."""
        mock_analysis = {
            "portfolio_strategies": ["covered_call", "iron_condor"],
            "greeks_summary": {"total_delta": 0.25},
            "pnl_analysis": {"total_pnl": 1500.0},
            "recommendations": ["Consider rolling positions"]
        }
        
        self.mock_service.analyze_portfolio_strategies = AsyncMock(return_value=mock_analysis)
        
        args = GetStrategyAnalysisArgs(
            include_greeks=True,
            include_pnl=True,
            include_recommendations=True
        )
        result = await get_strategy_analysis(args)
        
        data = json.loads(result)
        assert "portfolio_strategies" in data
        assert "greeks_summary" in data
        
        # Verify service call
        call_kwargs = self.mock_service.analyze_portfolio_strategies.call_args[1]
        assert call_kwargs["include_greeks"] is True
        assert call_kwargs["include_pnl"] is True
        assert call_kwargs["include_recommendations"] is True
        assert call_kwargs["include_complex_strategies"] is True
    
    @pytest_asyncio.async
    async def test_simulate_option_expiration_success(self):
        """Test successful option expiration simulation."""
        mock_result = {
            "simulated_date": "2024-01-19",
            "expired_positions": 5,
            "cash_impact": 2500.0,
            "assignments": []
        }
        
        self.mock_service.simulate_expiration = AsyncMock(return_value=mock_result)
        
        args = SimulateExpirationArgs(
            processing_date="2024-01-19",
            dry_run=True
        )
        result = await simulate_option_expiration(args)
        
        data = json.loads(result)
        assert data["simulated_date"] == "2024-01-19"
        assert data["expired_positions"] == 5
        
        # Verify service call
        call_kwargs = self.mock_service.simulate_expiration.call_args[1]
        assert call_kwargs["processing_date"] == "2024-01-19"
        assert call_kwargs["dry_run"] is True
    
    def test_find_tradable_options_success(self):
        """Test successful tradable options search."""
        mock_result = {
            "symbol": "AAPL",
            "options": [
                {
                    "symbol": "AAPL240119C00195000",
                    "strike": 195.0,
                    "expiration_date": "2024-01-19",
                    "option_type": "call"
                }
            ]
        }
        
        self.mock_service.find_tradable_options.return_value = mock_result
        
        args = FindTradableOptionsArgs(
            symbol="AAPL",
            expiration_date="2024-01-19",
            option_type="call"
        )
        result = find_tradable_options(args)
        
        data = json.loads(result)
        assert data["symbol"] == "AAPL"
        assert len(data["options"]) == 1
        
        self.mock_service.find_tradable_options.assert_called_with(
            "AAPL", "2024-01-19", "call"
        )
    
    def test_get_option_market_data_success(self):
        """Test successful option market data retrieval."""
        mock_result = {
            "option_id": "AAPL240119C00195000",
            "bid": 5.25,
            "ask": 5.50,
            "last_price": 5.30,
            "volume": 1000,
            "implied_volatility": 0.25
        }
        
        self.mock_service.get_option_market_data.return_value = mock_result
        
        args = GetOptionMarketDataArgs(option_id="AAPL240119C00195000")
        result = get_option_market_data(args)
        
        data = json.loads(result)
        assert data["option_id"] == "AAPL240119C00195000"
        assert data["bid"] == 5.25
        
        self.mock_service.get_option_market_data.assert_called_with("AAPL240119C00195000")


class TestMCPToolsErrorHandling:
    """Test comprehensive error handling in MCP tools."""
    
    def setup_method(self):
        """Set up mock trading service for each test."""
        self.mock_service = AsyncMock(spec=TradingService)
        set_mcp_trading_service(self.mock_service)
    
    @pytest_asyncio.async
    async def test_order_creation_error_handling(self):
        """Test order creation error handling."""
        self.mock_service.create_order.side_effect = Exception("Insufficient funds")
        
        args = CreateOrderArgs(
            symbol="AAPL",
            order_type=OrderType.BUY,
            quantity=1000000,  # Unrealistic quantity
            price=150.0
        )
        result = await create_buy_order(args)
        
        assert "Error creating buy order" in result
        assert "Insufficient funds" in result
    
    @pytest_asyncio.async
    async def test_portfolio_retrieval_error_handling(self):
        """Test portfolio retrieval error handling."""
        self.mock_service.get_portfolio.side_effect = Exception("Database connection failed")
        
        result = await get_portfolio()
        
        assert "Error getting portfolio" in result
        assert "Database connection failed" in result
    
    def test_options_chain_error_handling(self):
        """Test options chain error handling."""
        self.mock_service.get_formatted_options_chain.side_effect = Exception("Options data unavailable")
        
        args = GetOptionsChainArgs(symbol="INVALID")
        result = get_options_chain(args)
        
        assert "Error getting options chain" in result
        assert "Options data unavailable" in result
    
    @pytest_asyncio.async
    async def test_greeks_calculation_error_handling(self):
        """Test Greeks calculation error handling."""
        self.mock_service.calculate_greeks.side_effect = ValueError("Invalid option symbol")
        
        args = CalculateGreeksArgs(option_symbol="INVALID")
        result = await calculate_option_greeks(args)
        
        assert "Error calculating Greeks" in result
        assert "Invalid option symbol" in result


class TestMCPToolsAsyncBehavior:
    """Test async behavior and patterns in MCP tools."""
    
    def setup_method(self):
        """Set up mock trading service for each test."""
        self.mock_service = AsyncMock(spec=TradingService)
        set_mcp_trading_service(self.mock_service)
    
    @pytest_asyncio.async
    async def test_concurrent_tool_execution(self):
        """Test that tools can execute concurrently."""
        import asyncio
        
        # Set up mock returns
        mock_quote = Mock(
            symbol="AAPL", price=150.0, change=1.0, change_percent=0.67,
            volume=1000000, last_updated=datetime.now()
        )
        mock_portfolio = Mock(
            cash_balance=50000.0, total_value=100000.0, positions=[],
            daily_pnl=0.0, total_pnl=0.0
        )
        mock_orders = []
        
        self.mock_service.get_quote.return_value = mock_quote
        self.mock_service.get_portfolio.return_value = mock_portfolio
        self.mock_service.get_orders.return_value = mock_orders
        
        # Execute tools concurrently
        tasks = [
            get_stock_quote(GetQuoteArgs(symbol="AAPL")),
            get_portfolio(),
            get_all_orders()
        ]
        
        results = await asyncio.gather(*tasks)
        
        # All should complete successfully
        assert len(results) == 3
        for result in results:
            assert isinstance(result, str)  # All tools return JSON strings
            # Should be valid JSON
            try:
                json.loads(result)
            except json.JSONDecodeError:
                # If not JSON, should be error string
                assert "Error" in result
    
    def test_all_tools_are_async(self):
        """Test that all tool functions are async."""
        import inspect
        
        async_tools = [
            get_stock_quote, create_buy_order, create_sell_order, get_all_orders,
            get_order, cancel_order, get_portfolio, get_portfolio_summary,
            get_all_positions, get_position, get_options_chain, get_expiration_dates,
            create_multi_leg_order, calculate_option_greeks, get_strategy_analysis,
            simulate_option_expiration, find_tradable_options, get_option_market_data
        ]
        
        for tool in async_tools:
            assert inspect.iscoroutinefunction(tool), f"Tool {tool.__name__} should be async"


class TestMCPToolsResponseFormatting:
    """Test response formatting and JSON serialization."""
    
    def setup_method(self):
        """Set up mock trading service for each test."""
        self.mock_service = AsyncMock(spec=TradingService)
        set_mcp_trading_service(self.mock_service)
    
    @pytest_asyncio.async
    async def test_datetime_serialization(self):
        """Test that datetime objects are properly serialized."""
        mock_order = Mock()
        mock_order.id = "order_123"
        mock_order.symbol = "AAPL"
        mock_order.order_type = OrderType.BUY
        mock_order.quantity = 100
        mock_order.price = 150.0
        mock_order.status = OrderStatus.FILLED
        mock_order.created_at = datetime(2024, 1, 1, 10, 0, 0)
        mock_order.filled_at = datetime(2024, 1, 1, 10, 5, 0)
        
        self.mock_service.get_order.return_value = mock_order
        
        args = GetOrderArgs(order_id="order_123")
        result = await get_order(args)
        
        data = json.loads(result)
        assert data["created_at"] == "2024-01-01T10:00:00"
        assert data["filled_at"] == "2024-01-01T10:05:00"
    
    @pytest_asyncio.async
    async def test_none_value_handling(self):
        """Test that None values are properly handled in JSON."""
        mock_order = Mock()
        mock_order.id = "order_123"
        mock_order.symbol = "AAPL"
        mock_order.order_type = OrderType.BUY
        mock_order.quantity = 100
        mock_order.price = 150.0
        mock_order.status = OrderStatus.PENDING
        mock_order.created_at = datetime(2024, 1, 1, 10, 0, 0)
        mock_order.filled_at = None  # Not filled yet
        
        self.mock_service.get_order.return_value = mock_order
        
        args = GetOrderArgs(order_id="order_123")
        result = await get_order(args)
        
        data = json.loads(result)
        assert data["filled_at"] is None
    
    def test_json_indentation(self):
        """Test that JSON responses are properly indented."""
        mock_dates = [date(2024, 12, 20)]
        self.mock_service.get_expiration_dates.return_value = mock_dates
        
        args = GetExpirationDatesArgs(symbol="AAPL")
        result = get_expiration_dates(args)
        
        # Should be indented JSON
        assert "\n" in result
        assert "  " in result  # Indentation spaces


class TestMCPToolsCoverage:
    """Additional tests to achieve 70% coverage target."""
    
    def setup_method(self):
        """Set up mock trading service for each test."""
        self.mock_service = AsyncMock(spec=TradingService)
        set_mcp_trading_service(self.mock_service)
    
    def test_module_docstring(self):
        """Test module documentation."""
        import app.mcp.tools as tools_module
        
        assert tools_module.__doc__ is not None
        # Module should be documented
        assert len(tools_module.__doc__.strip()) > 0
    
    def test_all_argument_models_have_descriptions(self):
        """Test that all argument models have field descriptions."""
        argument_models = [
            GetQuoteArgs, CreateOrderArgs, GetOrderArgs, CancelOrderArgs,
            GetPositionArgs, GetOptionsChainArgs, GetExpirationDatesArgs,
            CreateMultiLegOrderArgs, CalculateGreeksArgs, GetStrategyAnalysisArgs,
            SimulateExpirationArgs, FindTradableOptionsArgs, GetOptionMarketDataArgs
        ]
        
        for model_class in argument_models:
            for field_name, field_info in model_class.model_fields.items():
                assert field_info.description is not None, f"{model_class.__name__}.{field_name} missing description"
    
    def test_service_integration_patterns(self):
        """Test service integration patterns."""
        # Test that service management functions work
        mock_service = Mock(spec=TradingService)
        
        # Test setting service
        original_service = get_mcp_trading_service()
        set_mcp_trading_service(mock_service)
        
        # Test getting service
        retrieved_service = get_mcp_trading_service()
        assert retrieved_service is mock_service
        
        # Restore original service
        set_mcp_trading_service(original_service)
    
    @pytest_asyncio.async
    async def test_edge_case_inputs(self):
        """Test edge case inputs for various tools."""
        # Test empty portfolio
        mock_portfolio = Mock()
        mock_portfolio.cash_balance = 0.0
        mock_portfolio.total_value = 0.0
        mock_portfolio.positions = []
        mock_portfolio.daily_pnl = 0.0
        mock_portfolio.total_pnl = 0.0
        
        self.mock_service.get_portfolio.return_value = mock_portfolio
        
        result = await get_portfolio()
        data = json.loads(result)
        assert data["cash_balance"] == 0.0
        assert len(data["positions"]) == 0
    
    def test_deprecated_tool_markers(self):
        """Test that deprecated tools are properly marked."""
        # get_stock_quote should be marked as deprecated
        assert "[DEPRECATED]" in get_stock_quote.__doc__
    
    @pytest_asyncio.async
    async def test_complex_options_scenarios(self):
        """Test complex options trading scenarios."""
        # Test multi-leg order with multiple legs
        legs_data = [
            {"symbol": "AAPL240119C00195000", "quantity": 1, "order_type": "buy", "price": 5.25},
            {"symbol": "AAPL240119C00200000", "quantity": -1, "order_type": "sell", "price": 3.50}
        ]
        
        mock_order = Mock()
        mock_order.id = "spread_order_123"
        mock_order.legs = []
        mock_order.net_price = 1.75
        mock_order.status = OrderStatus.PENDING
        mock_order.created_at = datetime(2024, 1, 1, 10, 0, 0)
        
        # Create mock legs
        for i, leg_data in enumerate(legs_data):
            mock_leg = Mock()
            mock_leg.asset = Mock()
            mock_leg.asset.symbol = leg_data["symbol"]
            mock_leg.quantity = leg_data["quantity"]
            mock_leg.order_type = leg_data["order_type"]
            mock_leg.price = leg_data["price"]
            mock_order.legs.append(mock_leg)
        
        self.mock_service.create_multi_leg_order_from_request.return_value = mock_order
        
        args = CreateMultiLegOrderArgs(legs=legs_data, order_type="limit")
        result = await create_multi_leg_order(args)
        
        data = json.loads(result)
        assert data["id"] == "spread_order_123"
        assert data["net_price"] == 1.75
        assert len(data["legs"]) == 2