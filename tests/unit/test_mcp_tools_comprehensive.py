"""
Comprehensive tests for the MCP tools module.

This test suite aims to provide high coverage of the mcp/tools.py module
by testing all functions with appropriate mocks.
"""

from datetime import date, datetime
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.mcp.tools import (
    calculate_option_greeks,
    cancel_stock_order_by_id,
    create_buy_order,
    create_multi_leg_order,
    create_sell_order,
    find_tradable_options,
    get_all_orders,
    get_all_positions,
    get_expiration_dates,
    get_mcp_trading_service,
    get_option_market_data,
    get_options_chain,
    get_order,
    get_portfolio,
    get_portfolio_summary,
    get_position,
    get_stock_quote,
    get_strategy_analysis,
    set_mcp_trading_service,
    simulate_option_expiration,
)
from app.models.assets import Option
from app.schemas.orders import OrderStatus, OrderType
from app.schemas.positions import Portfolio, Position
from app.services.trading_service import TradingService


@pytest.fixture
def mock_trading_service():
    """Create a mock trading service."""
    mock_service = AsyncMock(spec=TradingService)
    # Set up the mock service with default return values
    mock_service.get_quote.return_value = MagicMock(
        symbol="AAPL",
        price=150.0,
        change=5.0,
        change_percent=3.33,
        volume=1000,
        last_updated=datetime.now(),
    )
    return mock_service


@pytest.fixture
def setup_trading_service(mock_trading_service):
    """Set up the trading service for MCP tools."""
    set_mcp_trading_service(mock_trading_service)
    yield
    # Reset the global trading service after the test
    set_mcp_trading_service(None)


class TestMCPToolsSetup:
    """Test MCP tools setup and initialization."""

    def test_set_get_trading_service(self):
        """Test setting and getting the trading service."""
        # Arrange
        mock_service = MagicMock(spec=TradingService)

        # Act
        set_mcp_trading_service(mock_service)
        result = get_mcp_trading_service()

        # Assert
        assert result == mock_service

        # Clean up
        set_mcp_trading_service(None)

    def test_get_trading_service_not_initialized(self):
        """Test getting the trading service when not initialized."""
        # Arrange
        set_mcp_trading_service(None)

        # Act & Assert
        with pytest.raises(RuntimeError):
            get_mcp_trading_service()


class TestMCPStockTools:
    """Test MCP stock trading tools."""

    @pytest.mark.asyncio
    async def test_get_stock_quote_success(
        self, setup_trading_service, mock_trading_service
    ):
        """Test successful stock quote retrieval."""
        # Act
        result = await get_stock_quote(symbol="AAPL")

        # Assert
        result_dict = result["result"]["data"]
        assert result_dict["symbol"] == "AAPL"
        assert result_dict["price"] == 150.0
        mock_trading_service.get_quote.assert_called_once_with("AAPL")

    @pytest.mark.asyncio
    async def test_get_stock_quote_error(
        self, setup_trading_service, mock_trading_service
    ):
        """Test stock quote retrieval with error."""
        # Arrange
        mock_trading_service.get_quote.side_effect = Exception("API error")

        # Act
        result = await get_stock_quote(symbol="AAPL")

        # Assert
        assert result["result"]["status"] == "error"
        assert "API error" in result["result"]["error"]
        mock_trading_service.get_quote.assert_called_once_with("AAPL")

    @pytest.mark.asyncio
    async def test_create_buy_order_success(
        self, setup_trading_service, mock_trading_service
    ):
        """Test successful buy order creation."""
        # Arrange
        mock_order = MagicMock(
            id="order123",
            symbol="AAPL",
            order_type=OrderType.BUY,
            quantity=10,
            price=150.0,
            status=OrderStatus.PENDING,
            created_at=datetime.now(),
        )
        mock_trading_service.create_order.return_value = mock_order

        # Act
        result = await create_buy_order(symbol="AAPL", quantity=10, price=150.0)

        # Assert
        result_dict = result["result"]["data"]
        assert result_dict["id"] == "order123"
        assert result_dict["symbol"] == "AAPL"
        assert result_dict["order_type"] == "buy"
        mock_trading_service.create_order.assert_called_once()

    @pytest.mark.asyncio
    async def test_create_sell_order_success(
        self, setup_trading_service, mock_trading_service
    ):
        """Test successful sell order creation."""
        # Arrange
        mock_order = MagicMock(
            id="order123",
            symbol="AAPL",
            order_type=OrderType.SELL,
            quantity=10,
            price=150.0,
            status=OrderStatus.PENDING,
            created_at=datetime.now(),
        )
        mock_trading_service.create_order.return_value = mock_order

        # Act
        result = await create_sell_order(symbol="AAPL", quantity=10, price=150.0)

        # Assert
        result_dict = result["result"]["data"]
        assert result_dict["id"] == "order123"
        assert result_dict["symbol"] == "AAPL"
        assert result_dict["order_type"] == "sell"
        mock_trading_service.create_order.assert_called_once()


class TestMCPPortfolioTools:
    """Test MCP portfolio management tools."""

    @pytest.mark.asyncio
    async def test_get_portfolio_success(
        self, setup_trading_service, mock_trading_service
    ):
        """Test successful portfolio retrieval."""
        # Arrange
        mock_portfolio = Portfolio(
            cash_balance=10000.0,
            total_value=25000.0,
            positions=[
                Position(
                    symbol="AAPL",
                    quantity=100,
                    avg_price=150.0,
                    current_price=155.0,
                    unrealized_pnl=500.0,
                    realized_pnl=0.0,
                )
            ],
            daily_pnl=500.0,
            total_pnl=500.0,
        )
        mock_trading_service.get_portfolio.return_value = mock_portfolio

        # Act
        result = await get_portfolio()

        # Assert
        result_dict = result["result"]["data"]
        assert result_dict["cash_balance"] == 10000.0
        assert result_dict["total_value"] == 25000.0
        assert len(result_dict["positions"]) == 1
        assert result_dict["positions"][0]["symbol"] == "AAPL"
        mock_trading_service.get_portfolio.assert_called_once()

    @pytest.mark.asyncio
    async def test_get_portfolio_error(
        self, setup_trading_service, mock_trading_service
    ):
        """Test portfolio retrieval with error."""
        # Arrange
        mock_trading_service.get_portfolio.side_effect = Exception("Database error")

        # Act
        result = await get_portfolio()

        # Assert
        assert result["result"]["status"] == "error"
        assert "Database error" in result["result"]["error"]
        mock_trading_service.get_portfolio.assert_called_once()

    @pytest.mark.asyncio
    async def test_get_portfolio_summary_success(
        self, setup_trading_service, mock_trading_service
    ):
        """Test successful portfolio summary retrieval."""
        # Arrange
        mock_summary = MagicMock(
            total_value=25000.0,
            cash_balance=10000.0,
            invested_value=15000.0,
            daily_pnl=500.0,
            daily_pnl_percent=0.02,
            total_pnl=1000.0,
            total_pnl_percent=0.04,
        )
        mock_trading_service.get_portfolio_summary.return_value = mock_summary

        # Act
        result = await get_portfolio_summary()

        # Assert
        result_dict = result["result"]["data"]
        assert result_dict["total_value"] == 25000.0
        assert result_dict["cash_balance"] == 10000.0
        assert result_dict["invested_value"] == 15000.0
        assert result_dict["daily_pnl"] == 500.0
        mock_trading_service.get_portfolio_summary.assert_called_once()

    @pytest.mark.asyncio
    async def test_get_portfolio_summary_error(
        self, setup_trading_service, mock_trading_service
    ):
        """Test portfolio summary retrieval with error."""
        # Arrange
        mock_trading_service.get_portfolio_summary.side_effect = Exception(
            "Database error"
        )

        # Act
        result = await get_portfolio_summary()

        # Assert
        assert result["result"]["status"] == "error"
        assert "Database error" in result["result"]["error"]
        mock_trading_service.get_portfolio_summary.assert_called_once()

    @pytest.mark.asyncio
    async def test_get_all_positions_success(
        self, setup_trading_service, mock_trading_service
    ):
        """Test successful positions retrieval."""
        # Arrange
        mock_positions = [
            Position(
                symbol="AAPL",
                quantity=100,
                avg_price=150.0,
                current_price=155.0,
                unrealized_pnl=500.0,
                realized_pnl=0.0,
            ),
            Position(
                symbol="GOOGL",
                quantity=10,
                avg_price=2800.0,
                current_price=2850.0,
                unrealized_pnl=500.0,
                realized_pnl=0.0,
            ),
        ]
        mock_trading_service.get_positions.return_value = mock_positions

        # Act
        result = await get_all_positions()

        # Assert
        result_list = result["result"]["data"]
        assert len(result_list) == 2
        assert result_list[0]["symbol"] == "AAPL"
        assert result_list[1]["symbol"] == "GOOGL"
        mock_trading_service.get_positions.assert_called_once()

    @pytest.mark.asyncio
    async def test_get_position_success(
        self, setup_trading_service, mock_trading_service
    ):
        """Test successful position retrieval."""
        # Arrange
        mock_position = Position(
            symbol="AAPL",
            quantity=100,
            avg_price=150.0,
            current_price=155.0,
            unrealized_pnl=500.0,
            realized_pnl=0.0,
        )
        mock_trading_service.get_position.return_value = mock_position

        # Act
        result = await get_position(symbol="AAPL")

        # Assert
        result_dict = result["result"]["data"]
        assert result_dict["symbol"] == "AAPL"
        assert result_dict["quantity"] == 100
        assert result_dict["avg_price"] == 150.0
        assert result_dict["current_price"] == 155.0
        mock_trading_service.get_position.assert_called_once_with("AAPL")

    @pytest.mark.asyncio
    async def test_get_position_error(
        self, setup_trading_service, mock_trading_service
    ):
        """Test position retrieval with error."""
        # Arrange
        mock_trading_service.get_position.side_effect = Exception("Position not found")

        # Act
        result = await get_position(symbol="UNKNOWN")

        # Assert
        assert result["result"]["status"] == "error"
        assert "Position not found" in result["result"]["error"]
        mock_trading_service.get_position.assert_called_once_with("UNKNOWN")


class TestMCPOrderTools:
    """Test MCP order management tools."""

    @pytest.mark.asyncio
    async def test_get_all_orders_success(
        self, setup_trading_service, mock_trading_service
    ):
        """Test successful orders retrieval."""
        # Arrange
        mock_orders = [
            MagicMock(
                id="order1",
                symbol="AAPL",
                order_type=OrderType.BUY,
                quantity=10,
                price=150.0,
                status=OrderStatus.FILLED,
                created_at=datetime.now(),
                filled_at=datetime.now(),
            ),
            MagicMock(
                id="order2",
                symbol="GOOGL",
                order_type=OrderType.SELL,
                quantity=5,
                price=2800.0,
                status=OrderStatus.PENDING,
                created_at=datetime.now(),
                filled_at=None,
            ),
        ]
        mock_trading_service.get_orders.return_value = mock_orders

        # Act
        result = await get_all_orders()

        # Assert
        result_list = result["result"]["data"]
        assert len(result_list) == 2
        assert result_list[0]["id"] == "order1"
        assert result_list[0]["symbol"] == "AAPL"
        assert result_list[1]["id"] == "order2"
        assert result_list[1]["symbol"] == "GOOGL"
        mock_trading_service.get_orders.assert_called_once()

    @pytest.mark.asyncio
    async def test_get_all_orders_error(
        self, setup_trading_service, mock_trading_service
    ):
        """Test orders retrieval with error."""
        # Arrange
        mock_trading_service.get_orders.side_effect = Exception("Database error")

        # Act
        result = await get_all_orders()

        # Assert
        assert result["result"]["status"] == "error"
        assert "Database error" in result["result"]["error"]
        mock_trading_service.get_orders.assert_called_once()

    @pytest.mark.asyncio
    async def test_get_order_success(self, setup_trading_service, mock_trading_service):
        """Test successful order retrieval."""
        # Arrange
        mock_order = MagicMock(
            id="order123",
            symbol="AAPL",
            order_type=OrderType.BUY,
            quantity=10,
            price=150.0,
            status=OrderStatus.FILLED,
            created_at=datetime.now(),
            filled_at=datetime.now(),
        )
        mock_trading_service.get_order.return_value = mock_order

        # Act
        result = await get_order(order_id="order123")

        # Assert
        result_dict = result["result"]["data"]
        assert result_dict["id"] == "order123"
        assert result_dict["symbol"] == "AAPL"
        assert result_dict["order_type"] == "buy"
        assert result_dict["status"] == "FILLED"
        mock_trading_service.get_order.assert_called_once_with("order123")

    @pytest.mark.asyncio
    async def test_get_order_error(self, setup_trading_service, mock_trading_service):
        """Test order retrieval with error."""
        # Arrange
        mock_trading_service.get_order.side_effect = Exception("Order not found")

        # Act
        result = await get_order(order_id="unknown")

        # Assert
        assert result["result"]["status"] == "error"
        assert "Order not found" in result["result"]["error"]
        mock_trading_service.get_order.assert_called_once_with("unknown")

    @pytest.mark.asyncio
    async def test_cancel_order_success(
        self, setup_trading_service, mock_trading_service
    ):
        """Test successful order cancellation."""
        # Arrange
        mock_result = {"message": "Order cancelled successfully"}
        mock_trading_service.cancel_order.return_value = mock_result

        # Act
        result = await cancel_stock_order_by_id(order_id="order123")

        # Assert
        result_dict = result["result"]["data"]
        assert result_dict["message"] == "Order cancelled successfully"
        mock_trading_service.cancel_order.assert_called_once_with("order123")

    @pytest.mark.asyncio
    async def test_cancel_order_error(
        self, setup_trading_service, mock_trading_service
    ):
        """Test order cancellation with error."""
        # Arrange
        mock_trading_service.cancel_order.side_effect = Exception("Order not found")

        # Act
        result = await cancel_stock_order_by_id(order_id="unknown")

        # Assert
        assert result["result"]["status"] == "error"
        assert "Order not found" in result["result"]["error"]
        mock_trading_service.cancel_order.assert_called_once_with("unknown")


class TestMCPOptionsTools:
    """Test MCP options trading tools."""

    @pytest.mark.asyncio
    async def test_get_options_chain_success(
        self, setup_trading_service, mock_trading_service
    ):
        """Test successful options chain retrieval."""
        # Arrange
        mock_chain = {
            "underlying_symbol": "AAPL",
            "expiration_date": "2024-01-19",
            "underlying_price": 150.0,
            "calls": [{"strike": 150.0, "bid": 5.0, "ask": 5.5}],
            "puts": [{"strike": 150.0, "bid": 4.5, "ask": 5.0}],
        }
        mock_trading_service.get_formatted_options_chain.return_value = mock_chain

        # Act
        result = await get_options_chain(
            symbol="AAPL",
            expiration_date="2024-01-19",
            min_strike=140.0,
            max_strike=160.0,
        )

        # Assert
        result_dict = result["result"]["data"]
        assert result_dict["underlying_symbol"] == "AAPL"
        assert result_dict["expiration_date"] == "2024-01-19"
        assert len(result_dict["calls"]) == 1
        assert len(result_dict["puts"]) == 1
        mock_trading_service.get_formatted_options_chain.assert_called_once()

    @pytest.mark.asyncio
    async def test_get_expiration_dates_success(
        self, setup_trading_service, mock_trading_service
    ):
        """Test successful expiration dates retrieval."""
        # Arrange
        mock_dates = [date(2024, 1, 19), date(2024, 2, 16), date(2024, 3, 15)]
        mock_trading_service.get_expiration_dates.return_value = mock_dates

        # Act
        result = await get_expiration_dates(symbol="AAPL")

        # Assert
        result_dict = result["result"]["data"]
        assert result_dict["underlying_symbol"] == "AAPL"
        assert len(result_dict["expiration_dates"]) == 3
        assert result_dict["count"] == 3
        assert "2024-01-19" in result_dict["expiration_dates"]
        mock_trading_service.get_expiration_dates.assert_called_once_with("AAPL")

    @pytest.mark.asyncio
    async def test_get_expiration_dates_error(
        self, setup_trading_service, mock_trading_service
    ):
        """Test expiration dates retrieval with error."""
        # Arrange
        mock_trading_service.get_expiration_dates.side_effect = Exception(
            "Symbol not found"
        )

        # Act
        result = await get_expiration_dates(symbol="UNKNOWN")

        # Assert
        assert result["result"]["status"] == "error"
        assert "Symbol not found" in result["result"]["error"]
        mock_trading_service.get_expiration_dates.assert_called_once_with("UNKNOWN")

    @pytest.mark.asyncio
    async def test_calculate_option_greeks_success(
        self, setup_trading_service, mock_trading_service
    ):
        """Test successful option Greeks calculation."""
        # Arrange
        mock_greeks = {
            "delta": 0.65,
            "gamma": 0.05,
            "theta": -0.1,
            "vega": 0.2,
            "rho": 0.05,
        }
        mock_trading_service.calculate_greeks.return_value = mock_greeks

        # Mock asset_factory to return an Option
        mock_option = MagicMock(spec=Option)
        mock_option.underlying.symbol = "AAPL"
        mock_option.strike = 150.0
        mock_option.expiration_date = date(2024, 1, 19)
        mock_option.option_type = "CALL"
        mock_option.get_days_to_expiration.return_value = 30

        with patch("app.mcp.tools.asset_factory", return_value=mock_option):
            # Act
            result = await calculate_option_greeks(
                option_symbol="AAPL240119C00150000",
                underlying_price=155.0,
            )

            # Assert
            result_dict = result["result"]["data"]
            assert result_dict["delta"] == 0.65
            assert result_dict["gamma"] == 0.05
            assert result_dict["option_symbol"] == "AAPL240119C00150000"
            assert result_dict["underlying_symbol"] == "AAPL"
            mock_trading_service.calculate_greeks.assert_called_once_with(
                "AAPL240119C00150000", underlying_price=155.0
            )

    @pytest.mark.asyncio
    async def test_create_multi_leg_order_success(
        self, setup_trading_service, mock_trading_service
    ):
        """Test successful multi-leg order creation."""
        # Arrange
        legs = [
            {"symbol": "AAPL240119C00150000", "quantity": 1, "side": "buy"},
            {"symbol": "AAPL240119C00155000", "quantity": 1, "side": "sell"},
        ]
        mock_order = MagicMock(
            id="spread123",
            legs=[
                MagicMock(
                    asset=MagicMock(symbol="AAPL240119C00150000"),
                    quantity=1,
                    order_type="BUY",
                    price=5.0,
                ),
                MagicMock(
                    asset=MagicMock(symbol="AAPL240119C00155000"),
                    quantity=1,
                    order_type="SELL",
                    price=3.0,
                ),
            ],
            net_price=2.0,
            status="FILLED",
            created_at=datetime.now(),
        )
        mock_trading_service.create_multi_leg_order_from_request.return_value = (
            mock_order
        )

        # Act
        result = await create_multi_leg_order(legs=legs, order_type="limit")

        # Assert
        result_dict = result["result"]["data"]
        assert result_dict["id"] == "spread123"
        assert len(result_dict["legs"]) == 2
        assert result_dict["net_price"] == 2.0
        assert result_dict["status"] == "FILLED"
        mock_trading_service.create_multi_leg_order_from_request.assert_called_once()

    @pytest.mark.asyncio
    async def test_create_multi_leg_order_error(
        self, setup_trading_service, mock_trading_service
    ):
        """Test multi-leg order creation with error."""
        # Arrange
        legs = [
            {"symbol": "INVALID", "quantity": 1, "side": "buy"},
            {"symbol": "AAPL240119C00155000", "quantity": 1, "side": "sell"},
        ]
        mock_trading_service.create_multi_leg_order_from_request.side_effect = (
            Exception("Invalid option symbol")
        )

        # Act
        result = await create_multi_leg_order(legs=legs, order_type="limit")

        # Assert
        assert result["result"]["status"] == "error"
        assert "Invalid option symbol" in result["result"]["error"]
        mock_trading_service.create_multi_leg_order_from_request.assert_called_once()

    @pytest.mark.asyncio
    async def test_get_strategy_analysis_success(
        self, setup_trading_service, mock_trading_service
    ):
        """Test successful strategy analysis."""
        # Arrange
        mock_result = {
            "strategies": [
                {"type": "vertical_spread", "underlying": "AAPL", "risk": "moderate"},
                {"type": "covered_call", "underlying": "MSFT", "risk": "low"},
            ],
            "total_strategies": 2,
            "portfolio_greeks": {"delta": 0.75, "gamma": 0.1, "theta": -0.2},
            "recommendations": ["Consider rolling out the MSFT covered call"],
        }
        mock_trading_service.analyze_portfolio_strategies.return_value = mock_result

        # Act
        result = await get_strategy_analysis(
            symbols=["AAPL", "MSFT"], strategy_type="all"
        )

        # Assert
        result_dict = result["result"]["data"]
        assert result_dict["total_strategies"] == 2
        assert len(result_dict["strategies"]) == 2
        assert "portfolio_greeks" in result_dict
        assert "recommendations" in result_dict
        mock_trading_service.analyze_portfolio_strategies.assert_called_once()

    @pytest.mark.asyncio
    async def test_get_strategy_analysis_error(
        self, setup_trading_service, mock_trading_service
    ):
        """Test strategy analysis with error."""
        # Arrange
        mock_trading_service.analyze_portfolio_strategies.side_effect = Exception(
            "No options positions found"
        )

        # Act
        result = await get_strategy_analysis(symbols=["AAPL"], strategy_type="all")

        # Assert
        assert result["result"]["status"] == "error"
        assert "No options positions found" in result["result"]["error"]
        mock_trading_service.analyze_portfolio_strategies.assert_called_once()

    @pytest.mark.asyncio
    async def test_simulate_option_expiration_success(
        self, setup_trading_service, mock_trading_service
    ):
        """Test successful option expiration simulation."""
        # Arrange
        mock_result = {
            "processing_date": "2024-01-19",
            "expiring_positions": 2,
            "total_impact": 500.0,
            "position_impacts": {
                "AAPL240119C00150000": 300.0,
                "MSFT240119P00350000": 200.0,
            },
            "dry_run": True,
        }
        mock_trading_service.simulate_expiration.return_value = mock_result

        # Act
        result = await simulate_option_expiration(
            processing_date="2024-01-19",
            dry_run=True,
        )

        # Assert
        result_dict = result["result"]["data"]
        assert result_dict["processing_date"] == "2024-01-19"
        assert result_dict["expiring_positions"] == 2
        assert result_dict["total_impact"] == 500.0
        assert len(result_dict["position_impacts"]) == 2
        assert result_dict["dry_run"] is True
        mock_trading_service.simulate_expiration.assert_called_once_with(
            processing_date="2024-01-19",
            dry_run=True,
        )

    @pytest.mark.asyncio
    async def test_simulate_option_expiration_error(
        self, setup_trading_service, mock_trading_service
    ):
        """Test option expiration simulation with error."""
        # Arrange
        mock_trading_service.simulate_expiration.side_effect = Exception(
            "Invalid date format"
        )

        # Act
        result = await simulate_option_expiration(
            processing_date="invalid-date",
            dry_run=True,
        )

        # Assert
        assert result["result"]["status"] == "error"
        assert "Invalid date format" in result["result"]["error"]
        mock_trading_service.simulate_expiration.assert_called_once()

    @pytest.mark.asyncio
    async def test_find_tradable_options_success(
        self, setup_trading_service, mock_trading_service
    ):
        """Test successful tradable options search."""
        # Arrange
        mock_result = {
            "symbol": "AAPL",
            "total_found": 10,
            "options": [
                {
                    "symbol": "AAPL240119C00145000",
                    "strike": 145.0,
                    "bid": 10.0,
                    "ask": 10.2,
                },
                {
                    "symbol": "AAPL240119C00150000",
                    "strike": 150.0,
                    "bid": 5.0,
                    "ask": 5.2,
                },
            ],
            "expiration_date": "2024-01-19",
            "option_type": "call",
        }
        mock_trading_service.find_tradable_options.return_value = mock_result

        # Act
        result = await find_tradable_options(
            symbol="AAPL",
            expiration_date="2024-01-19",
            option_type="call",
        )

        # Assert
        result_dict = result["result"]["data"]
        assert result_dict["symbol"] == "AAPL"
        assert result_dict["total_found"] == 10
        assert len(result_dict["options"]) == 2
        assert result_dict["expiration_date"] == "2024-01-19"
        assert result_dict["option_type"] == "call"
        mock_trading_service.find_tradable_options.assert_called_once_with(
            "AAPL", "2024-01-19", "call"
        )

    @pytest.mark.asyncio
    async def test_find_tradable_options_error(
        self, setup_trading_service, mock_trading_service
    ):
        """Test tradable options search with error."""
        # Arrange
        mock_trading_service.find_tradable_options.side_effect = Exception(
            "Symbol not found"
        )

        # Act
        result = await find_tradable_options(
            symbol="UNKNOWN",
            expiration_date="2024-01-19",
            option_type="call",
        )

        # Assert
        assert result["result"]["status"] == "error"
        assert "Symbol not found" in result["result"]["error"]
        mock_trading_service.find_tradable_options.assert_called_once()

    @pytest.mark.asyncio
    async def test_get_option_market_data_success(
        self, setup_trading_service, mock_trading_service
    ):
        """Test successful option market data retrieval."""
        # Arrange
        mock_result = {
            "option_id": "AAPL240119C00150000",
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
        result = await get_option_market_data(
            option_id="AAPL240119C00150000",
        )

        # Assert
        result_dict = result["result"]["data"]
        assert result_dict["option_id"] == "AAPL240119C00150000"
        assert result_dict["underlying_symbol"] == "AAPL"
        assert result_dict["strike"] == 150.0
        assert result_dict["expiration_date"] == "2024-01-19"
        assert result_dict["option_type"] == "call"
        assert result_dict["bid_price"] == 5.0
        assert result_dict["ask_price"] == 5.2
        assert "delta" in result_dict
        assert "gamma" in result_dict
        assert "theta" in result_dict
        mock_trading_service.get_option_market_data.assert_called_once_with(
            "AAPL240119C00150000"
        )

    @pytest.mark.asyncio
    async def test_get_option_market_data_error(
        self, setup_trading_service, mock_trading_service
    ):
        """Test option market data retrieval with error."""
        # Arrange
        mock_trading_service.get_option_market_data.side_effect = Exception(
            "Invalid option symbol"
        )

        # Act
        result = await get_option_market_data(
            option_id="INVALID",
        )

        # Assert
        assert result["result"]["status"] == "error"
        assert "Invalid option symbol" in result["result"]["error"]
        mock_trading_service.get_option_market_data.assert_called_once_with("INVALID")
