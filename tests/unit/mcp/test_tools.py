"""
Comprehensive unit tests for MCP trading tools.

Tests async tool functions, parameter validation, TradingService integration,
error handling, response formatting, and options trading functionality.
"""

from datetime import date, datetime
from unittest.mock import AsyncMock, Mock, patch

import pytest

from app.mcp.tools import (
    calculate_option_greeks,
    create_buy_order,
    create_multi_leg_order,
    create_sell_order,
    find_tradable_options,
    get_all_positions,
    get_expiration_dates,
    get_mcp_trading_service,
    get_option_market_data,
    get_options_chain,
    get_order,
    get_portfolio,
    get_portfolio_summary,
    get_position,
    set_mcp_trading_service,
    simulate_option_expiration,
    stock_orders,
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


class TestBasicTradingTools:
    """Test basic trading tool functions."""

    def setup_method(self):
        """Set up mock trading service for each test."""
        self.mock_service = AsyncMock(spec=TradingService)
        set_mcp_trading_service(self.mock_service)

    @pytest.mark.asyncio
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

        result = await create_buy_order(symbol="AAPL", quantity=100, price=150.50)

        assert result["result"]["status"] == "success"
        data = result["result"]["data"]
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
        assert call_args.condition == OrderCondition.LIMIT

    @pytest.mark.asyncio
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

        result = await create_sell_order(symbol="GOOGL", quantity=50, price=2800.00)

        data = result["result"]["data"]
        assert data["order_type"] == OrderType.SELL
        assert data["symbol"] == "GOOGL"

        # Verify service call has correct order type
        call_args = self.mock_service.create_order.call_args[0][0]
        assert call_args.order_type == OrderType.SELL

    @pytest.mark.asyncio
    async def test_stock_orders_success(self):
        """Test successful retrieval of stock orders."""
        mock_orders = [
            Mock(
                id="order_1",
                symbol="AAPL",
                order_type=OrderType.BUY,
                quantity=100,
                price=150.0,
                status=OrderStatus.FILLED,
                created_at=datetime(2024, 1, 1, 10, 0, 0),
                filled_at=datetime(2024, 1, 1, 10, 5, 0),
            ),
            Mock(
                id="order_2",
                symbol="GOOGL",
                order_type=OrderType.SELL,
                quantity=50,
                price=2800.0,
                status=OrderStatus.PENDING,
                created_at=datetime(2024, 1, 1, 11, 0, 0),
                filled_at=None,
            ),
        ]

        self.mock_service.get_orders.return_value = mock_orders

        # Mock asset_factory to return stock assets
        with patch("app.mcp.tools.asset_factory") as mock_asset_factory:
            mock_stock = Mock()
            mock_stock.asset_type = "stock"
            mock_asset_factory.return_value = mock_stock

            result = await stock_orders()

            data = result["result"]["data"]
            assert data["count"] == 2
            assert len(data["stock_orders"]) == 2
            assert data["stock_orders"][0]["id"] == "order_1"
            assert data["stock_orders"][0]["status"] == OrderStatus.FILLED
            assert data["stock_orders"][1]["id"] == "order_2"
            assert data["stock_orders"][1]["status"] == OrderStatus.PENDING

    @pytest.mark.asyncio
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

        result = await get_order(order_id="order_123")

        data = result["result"]["data"]
        assert data["id"] == "order_123"
        assert data["status"] == OrderStatus.FILLED

        self.mock_service.get_order.assert_called_once_with("order_123")

    @pytest.mark.asyncio
    async def test_cancel_order_success(self):
        """Test successful order cancellation."""
        mock_result = {"status": "cancelled", "order_id": "order_123"}
        self.mock_service.cancel_order.return_value = mock_result

        result = await cancel_order(order_id="order_123")

        data = result["result"]["data"]
        assert data["status"] == "cancelled"
        assert data["order_id"] == "order_123"

        self.mock_service.cancel_order.assert_called_once_with("order_123")


class TestPortfolioTools:
    """Test portfolio-related tool functions."""

    def setup_method(self):
        """Set up mock trading service for each test."""
        self.mock_service = AsyncMock(spec=TradingService)
        set_mcp_trading_service(self.mock_service)

    @pytest.mark.asyncio
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

        data = result["result"]["data"]
        assert data["cash_balance"] == 50000.0
        assert data["total_value"] == 200000.0
        assert len(data["positions"]) == 2
        assert data["positions"][0]["symbol"] == "AAPL"
        assert data["positions"][1]["symbol"] == "GOOGL"
        assert data["daily_pnl"] == 3000.0
        assert data["total_pnl"] == 10000.0

    @pytest.mark.asyncio
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

        data = result["result"]["data"]
        assert data["total_value"] == 200000.0
        assert data["cash_balance"] == 50000.0
        assert data["invested_value"] == 150000.0
        assert data["daily_pnl_percent"] == 1.5
        assert data["total_pnl_percent"] == 5.0

    @pytest.mark.asyncio
    async def test_get_all_positions_success(self):
        """Test successful retrieval of all positions."""
        mock_positions = [
            Mock(
                symbol="AAPL",
                quantity=100,
                avg_price=145.0,
                current_price=150.0,
                unrealized_pnl=500.0,
                realized_pnl=0.0,
            ),
            Mock(
                symbol="GOOGL",
                quantity=50,
                avg_price=2750.0,
                current_price=2800.0,
                unrealized_pnl=2500.0,
                realized_pnl=1000.0,
            ),
        ]

        self.mock_service.get_positions.return_value = mock_positions

        result = await get_all_positions()

        data = result["result"]["data"]
        assert len(data) == 2
        assert data[0]["symbol"] == "AAPL"
        assert data[1]["symbol"] == "GOOGL"

    @pytest.mark.asyncio
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

        result = await get_position(symbol="AAPL")

        data = result["result"]["data"]
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
                    "puts": [{"strike": 150.0, "bid": 2.10, "ask": 2.25}],
                }
            },
        }

        self.mock_service.get_formatted_options_chain.return_value = mock_chain_data

        # Test without filters
        result = get_options_chain(symbol="AAPL")

        data = result["result"]["data"]
        assert data["underlying_symbol"] == "AAPL"
        assert len(data["expiration_dates"]) == 1

        self.mock_service.get_formatted_options_chain.assert_called_with(
            "AAPL", expiration_date=None, min_strike=None, max_strike=None
        )

    def test_get_options_chain_with_filters(self):
        """Test options chain retrieval with filters."""
        mock_chain_data = {"underlying_symbol": "AAPL", "chains": {}}
        self.mock_service.get_formatted_options_chain.return_value = mock_chain_data

        get_options_chain(
            symbol="AAPL",
            expiration_date="2024-12-20",
            min_strike=140.0,
            max_strike=160.0,
        )

        # Verify filters are converted properly
        call_args = self.mock_service.get_formatted_options_chain.call_args
        assert call_args[1]["expiration_date"] == date(2024, 12, 20)
        assert call_args[1]["min_strike"] == 140.0
        assert call_args[1]["max_strike"] == 160.0

    def test_get_expiration_dates_success(self):
        """Test successful expiration dates retrieval."""
        mock_dates = [date(2024, 12, 20), date(2025, 1, 17)]
        self.mock_service.get_expiration_dates.return_value = mock_dates

        result = get_expiration_dates(symbol="AAPL")

        data = result["result"]["data"]
        assert data["underlying_symbol"] == "AAPL"
        assert len(data["expiration_dates"]) == 2
        assert data["expiration_dates"][0] == "2024-12-20"
        assert data["expiration_dates"][1] == "2025-01-17"
        assert data["count"] == 2

    @pytest.mark.asyncio
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
                "price": 5.25,
            }
        ]

        result = await create_multi_leg_order(legs=legs_data, order_type="limit")

        data = result["result"]["data"]
        assert data["id"] == "multi_order_123"
        assert data["net_price"] == 5.25
        assert len(data["legs"]) == 1
        assert data["legs"][0]["symbol"] == "AAPL240119C00195000"

    @pytest.mark.asyncio
    async def test_calculate_option_greeks_success(self):
        """Test successful option Greeks calculation."""
        mock_greeks = {
            "delta": 0.65,
            "gamma": 0.02,
            "theta": -0.15,
            "vega": 0.12,
            "rho": 0.08,
        }

        # Mock the asset_factory
        with patch("app.mcp.tools.asset_factory") as mock_factory:
            mock_option = Mock()
            mock_option.underlying.symbol = "AAPL"
            mock_option.strike = 195.0
            mock_option.expiration_date = date(2024, 1, 19)
            mock_option.option_type = "CALL"
            mock_option.get_days_to_expiration.return_value = 30

            mock_factory.return_value = mock_option

            self.mock_service.calculate_greeks = AsyncMock(return_value=mock_greeks)

            result = await calculate_option_greeks(option_symbol="AAPL240119C00195000")

            data = result["result"]["data"]
            assert data["delta"] == 0.65
            assert data["option_symbol"] == "AAPL240119C00195000"
            assert data["underlying_symbol"] == "AAPL"
            assert data["strike"] == 195.0
            assert data["option_type"] == "call"

    # NOTE: get_strategy_analysis function is not implemented yet, skipping test

    @pytest.mark.asyncio
    async def test_simulate_option_expiration_success(self):
        """Test successful option expiration simulation."""
        mock_result = {
            "simulated_date": "2024-01-19",
            "expired_positions": 5,
            "cash_impact": 2500.0,
            "assignments": [],
        }

        self.mock_service.simulate_expiration = AsyncMock(return_value=mock_result)

        result = await simulate_option_expiration(
            processing_date="2024-01-19", dry_run=True
        )

        data = result["result"]["data"]
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
                    "option_type": "call",
                }
            ],
        }

        self.mock_service.find_tradable_options.return_value = mock_result

        result = find_tradable_options(
            symbol="AAPL", expiration_date="2024-01-19", option_type="call"
        )

        data = result["result"]["data"]
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
            "implied_volatility": 0.25,
        }

        self.mock_service.get_option_market_data.return_value = mock_result

        result = get_option_market_data(option_id="AAPL240119C00195000")

        data = result["result"]["data"]
        assert data["option_id"] == "AAPL240119C00195000"
        assert data["bid"] == 5.25

        self.mock_service.get_option_market_data.assert_called_with(
            "AAPL240119C00195000"
        )
