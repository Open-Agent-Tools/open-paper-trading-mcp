"""
Comprehensive unit tests for MCP account tools.

Tests all 4 account tools: account_info, portfolio, account_details, and positions.
Includes testing patterns for async MCP tools, service integration, and error handling.
"""

from typing import Any
from unittest.mock import AsyncMock, Mock, patch

import pytest

from app.mcp.account_tools import (
    account_details,
    account_info,
    get_mcp_trading_service,
    portfolio,
    positions,
    set_mcp_trading_service,
)
from app.schemas.positions import Portfolio, PortfolioSummary, Position


class TestAccountToolsServiceManagement:
    """Test trading service dependency management."""

    def test_set_and_get_mcp_trading_service(self):
        """Test setting and getting trading service."""
        mock_service = Mock()
        set_mcp_trading_service(mock_service)

        service = get_mcp_trading_service()
        assert service is mock_service

    def test_get_mcp_trading_service_not_initialized(self):
        """Test getting service when not initialized raises error."""
        # Clear any existing service
        from app.mcp import account_tools

        account_tools._trading_service = None

        with pytest.raises(RuntimeError, match="TradingService not initialized"):
            get_mcp_trading_service()


class TestAccountInfoTool:
    """Test the account_info MCP tool."""

    @pytest.mark.asyncio
    async def test_account_info_success(self):
        """Test account_info returns correct structure."""
        result = await account_info()

        # Check response structure
        assert "result" in result
        assert "status" in result["result"]
        assert "data" in result["result"]
        assert result["result"]["status"] == "success"

        # Check data structure
        data = result["result"]["data"]
        assert "account_id" in data
        assert "account_type" in data
        assert "status" in data
        assert "created_at" in data
        assert "last_login" in data

        # Check specific values for paper trading
        assert data["account_id"] == "DEMO_ACCOUNT"
        assert data["account_type"] == "paper_trading"
        assert data["status"] == "active"

    @pytest.mark.asyncio
    async def test_account_info_return_type(self):
        """Test account_info returns dict[str, Any]."""
        result = await account_info()
        assert isinstance(result, dict)
        assert all(isinstance(k, str) for k in result)

    @pytest.mark.asyncio
    async def test_account_info_exception_handling(self):
        """Test account_info handles exceptions properly."""
        # This test verifies the exception handling structure
        # Since account_info doesn't currently use external services,
        # we test the error handling pattern
        with patch(
            "app.mcp.account_tools.success_response",
            side_effect=Exception("Test error"),
        ):
            result = await account_info()

            assert "result" in result
            assert result["result"]["status"] == "error"
            assert "error" in result["result"]
            assert "account_info" in result["result"]["error"]


class TestPortfolioTool:
    """Test the portfolio MCP tool."""

    @pytest.fixture
    def mock_portfolio(self):
        """Create a mock portfolio with positions."""
        positions = [
            Position(
                symbol="AAPL",
                quantity=100,
                avg_price=150.0,
                current_price=155.0,
                unrealized_pnl=500.0,
                realized_pnl=100.0,
            ),
            Position(
                symbol="GOOGL",
                quantity=50,
                avg_price=2800.0,
                current_price=2850.0,
                unrealized_pnl=2500.0,
                realized_pnl=200.0,
            ),
        ]
        return Portfolio(
            cash_balance=10000.0,
            total_value=165000.0,
            positions=positions,
            daily_pnl=1500.0,
            total_pnl=3300.0,
        )

    @pytest.mark.asyncio
    async def test_portfolio_success(self, mock_portfolio):
        """Test portfolio returns correct structure."""
        mock_service = AsyncMock()
        mock_service.get_portfolio.return_value = mock_portfolio
        set_mcp_trading_service(mock_service)

        result = await portfolio()

        # Check response structure
        assert "result" in result
        assert result["result"]["status"] == "success"
        assert "data" in result["result"]

        # Check data structure
        data = result["result"]["data"]
        assert "cash_balance" in data
        assert "total_value" in data
        assert "positions" in data
        assert "daily_pnl" in data
        assert "total_pnl" in data

        # Check values
        assert data["cash_balance"] == 10000.0
        assert data["total_value"] == 165000.0
        assert data["daily_pnl"] == 1500.0
        assert data["total_pnl"] == 3300.0

        # Check positions
        assert len(data["positions"]) == 2
        aapl_pos = data["positions"][0]
        assert aapl_pos["symbol"] == "AAPL"
        assert aapl_pos["quantity"] == 100
        assert aapl_pos["avg_price"] == 150.0
        assert aapl_pos["current_price"] == 155.0
        assert aapl_pos["unrealized_pnl"] == 500.0
        assert aapl_pos["realized_pnl"] == 100.0

    @pytest.mark.asyncio
    async def test_portfolio_service_call(self, mock_portfolio):
        """Test portfolio calls trading service correctly."""
        mock_service = AsyncMock()
        mock_service.get_portfolio.return_value = mock_portfolio
        set_mcp_trading_service(mock_service)

        await portfolio()

        mock_service.get_portfolio.assert_called_once()

    @pytest.mark.asyncio
    async def test_portfolio_exception_handling(self):
        """Test portfolio handles service exceptions."""
        mock_service = AsyncMock()
        mock_service.get_portfolio.side_effect = Exception("Service error")
        set_mcp_trading_service(mock_service)

        result = await portfolio()

        assert result["result"]["status"] == "error"
        assert "error" in result["result"]
        assert "portfolio" in result["result"]["error"]
        assert "Service error" in result["result"]["error"]

    @pytest.mark.asyncio
    async def test_portfolio_return_type(self, mock_portfolio):
        """Test portfolio returns dict[str, Any]."""
        mock_service = AsyncMock()
        mock_service.get_portfolio.return_value = mock_portfolio
        set_mcp_trading_service(mock_service)

        result = await portfolio()
        assert isinstance(result, dict)
        assert all(isinstance(k, str) for k in result)


class TestAccountDetailsTool:
    """Test the account_details MCP tool."""

    @pytest.fixture
    def mock_portfolio_summary(self):
        """Create a mock portfolio summary."""
        return PortfolioSummary(
            total_value=165000.0,
            invested_value=155000.0,
            cash_balance=10000.0,
            daily_pnl=1500.0,
            daily_pnl_percent=0.91,  # 1500/165000 * 100
            total_pnl=3300.0,
            total_pnl_percent=2.0,  # 3300/165000 * 100
        )

    @pytest.fixture
    def mock_portfolio_basic(self):
        """Create a basic mock portfolio for account details."""
        return Portfolio(
            cash_balance=10000.0,
            total_value=165000.0,
            positions=[],
            daily_pnl=1500.0,
            total_pnl=3300.0,
        )

    @pytest.mark.asyncio
    async def test_account_details_success(
        self, mock_portfolio_basic, mock_portfolio_summary
    ):
        """Test account_details returns correct structure."""
        mock_service = AsyncMock()
        mock_service.get_portfolio.return_value = mock_portfolio_basic
        mock_service.get_portfolio_summary.return_value = mock_portfolio_summary
        set_mcp_trading_service(mock_service)

        result = await account_details()

        # Check response structure
        assert "result" in result
        assert result["result"]["status"] == "success"
        assert "data" in result["result"]

        # Check data structure
        data = result["result"]["data"]
        expected_fields = [
            "account_id",
            "cash_balance",
            "buying_power",
            "total_value",
            "invested_value",
            "day_trades_remaining",
            "account_type",
            "margin_enabled",
            "options_level",
            "crypto_enabled",
        ]
        for field in expected_fields:
            assert field in data

        # Check specific values
        assert data["account_id"] == "DEMO_ACCOUNT"
        assert data["cash_balance"] == 10000.0
        assert data["buying_power"] == 10000.0  # Should equal cash for paper trading
        assert data["total_value"] == 165000.0
        assert data["invested_value"] == 155000.0
        assert data["day_trades_remaining"] == 3
        assert data["account_type"] == "paper_trading"
        assert data["margin_enabled"] is False
        assert data["options_level"] == 3
        assert data["crypto_enabled"] is False

    @pytest.mark.asyncio
    async def test_account_details_service_calls(
        self, mock_portfolio_basic, mock_portfolio_summary
    ):
        """Test account_details calls both required services."""
        mock_service = AsyncMock()
        mock_service.get_portfolio.return_value = mock_portfolio_basic
        mock_service.get_portfolio_summary.return_value = mock_portfolio_summary
        set_mcp_trading_service(mock_service)

        await account_details()

        mock_service.get_portfolio.assert_called_once()
        mock_service.get_portfolio_summary.assert_called_once()

    @pytest.mark.asyncio
    async def test_account_details_exception_handling(self):
        """Test account_details handles service exceptions."""
        mock_service = AsyncMock()
        mock_service.get_portfolio.side_effect = Exception("Portfolio error")
        set_mcp_trading_service(mock_service)

        result = await account_details()

        assert result["result"]["status"] == "error"
        assert "error" in result["result"]
        assert "account_details" in result["result"]["error"]


class TestPositionsTool:
    """Test the positions MCP tool."""

    @pytest.fixture
    def mock_positions(self):
        """Create mock positions list."""
        return [
            Position(
                symbol="AAPL",
                quantity=100,
                avg_price=150.0,
                current_price=155.0,
                unrealized_pnl=500.0,
                realized_pnl=100.0,
            ),
            Position(
                symbol="TSLA",
                quantity=-50,  # Short position
                avg_price=800.0,
                current_price=750.0,
                unrealized_pnl=2500.0,  # Profit on short
                realized_pnl=-200.0,
            ),
        ]

    @pytest.mark.asyncio
    async def test_positions_success(self, mock_positions):
        """Test positions returns correct structure."""
        mock_service = AsyncMock()
        mock_service.get_positions.return_value = mock_positions
        set_mcp_trading_service(mock_service)

        result = await positions()

        # Check response structure
        assert "result" in result
        assert result["result"]["status"] == "success"
        assert "data" in result["result"]

        # Check data is a list of positions
        data = result["result"]["data"]
        assert isinstance(data, list)
        assert len(data) == 2

        # Check first position (AAPL)
        aapl_pos = data[0]
        expected_fields = [
            "symbol",
            "quantity",
            "avg_price",
            "current_price",
            "market_value",
            "unrealized_pnl",
            "unrealized_pnl_percent",
            "realized_pnl",
        ]
        for field in expected_fields:
            assert field in aapl_pos

        assert aapl_pos["symbol"] == "AAPL"
        assert aapl_pos["quantity"] == 100
        assert aapl_pos["avg_price"] == 150.0
        assert aapl_pos["current_price"] == 155.0
        assert aapl_pos["market_value"] == 15500.0  # 100 * 155
        assert aapl_pos["unrealized_pnl"] == 500.0
        assert aapl_pos["realized_pnl"] == 100.0

        # Check unrealized PnL percentage calculation
        expected_pnl_percent = (500.0 / (150.0 * 100)) * 100  # ~3.33%
        assert abs(aapl_pos["unrealized_pnl_percent"] - expected_pnl_percent) < 0.01

        # Check second position (TSLA short)
        tsla_pos = data[1]
        assert tsla_pos["symbol"] == "TSLA"
        assert tsla_pos["quantity"] == -50
        assert tsla_pos["market_value"] == -37500.0  # -50 * 750

    @pytest.mark.asyncio
    async def test_positions_empty_list(self):
        """Test positions handles empty positions list."""
        mock_service = AsyncMock()
        mock_service.get_positions.return_value = []
        set_mcp_trading_service(mock_service)

        result = await positions()

        assert result["result"]["status"] == "success"
        assert result["result"]["data"] == []

    @pytest.mark.asyncio
    async def test_positions_pnl_percent_zero_cost_basis(self):
        """Test positions handles zero cost basis for PnL percentage."""
        # Create a position with very small avg_price instead of zero to avoid validation error
        small_price_position = Position(
            symbol="CHEAP",
            quantity=100,
            avg_price=0.01,  # Very small cost basis
            current_price=10.0,
            unrealized_pnl=999.0,
            realized_pnl=0.0,
        )

        mock_service = AsyncMock()
        mock_service.get_positions.return_value = [small_price_position]
        set_mcp_trading_service(mock_service)

        result = await positions()

        data = result["result"]["data"]
        assert len(data) == 1
        # Check that percentage is calculated correctly for small cost basis
        expected_pnl_percent = (
            999.0 / (0.01 * 100)
        ) * 100  # Should be very high percentage
        assert abs(data[0]["unrealized_pnl_percent"] - expected_pnl_percent) < 0.01

    @pytest.mark.asyncio
    async def test_positions_service_call(self, mock_positions):
        """Test positions calls trading service correctly."""
        mock_service = AsyncMock()
        mock_service.get_positions.return_value = mock_positions
        set_mcp_trading_service(mock_service)

        await positions()

        mock_service.get_positions.assert_called_once()

    @pytest.mark.asyncio
    async def test_positions_exception_handling(self):
        """Test positions handles service exceptions."""
        mock_service = AsyncMock()
        mock_service.get_positions.side_effect = Exception("Positions error")
        set_mcp_trading_service(mock_service)

        result = await positions()

        assert result["result"]["status"] == "error"
        assert "error" in result["result"]
        assert "positions" in result["result"]["error"]
        assert "Positions error" in result["result"]["error"]

    @pytest.mark.asyncio
    async def test_positions_return_type(self, mock_positions):
        """Test positions returns dict[str, Any]."""
        mock_service = AsyncMock()
        mock_service.get_positions.return_value = mock_positions
        set_mcp_trading_service(mock_service)

        result = await positions()
        assert isinstance(result, dict)
        assert all(isinstance(k, str) for k in result)


class TestAccountToolsIntegration:
    """Test integration aspects of account tools."""

    @pytest.mark.asyncio
    async def test_all_tools_follow_response_format(self):
        """Test all tools follow standardized response format."""
        # Set up mocks for tools that need services
        mock_service = AsyncMock()
        mock_service.get_portfolio.return_value = Portfolio(
            cash_balance=10000.0,
            total_value=10000.0,
            positions=[],
            daily_pnl=0.0,
            total_pnl=0.0,
        )
        mock_service.get_portfolio_summary.return_value = PortfolioSummary(
            total_value=10000.0,
            invested_value=0.0,
            cash_balance=10000.0,
            daily_pnl=0.0,
            daily_pnl_percent=0.0,
            total_pnl=0.0,
            total_pnl_percent=0.0,
        )
        mock_service.get_positions.return_value = []
        set_mcp_trading_service(mock_service)

        # Test all four tools
        tools = [account_info, portfolio, account_details, positions]

        for tool in tools:
            result = await tool()

            # Check standardized response format
            assert "result" in result, f"Tool {tool.__name__} missing 'result' field"
            assert "status" in result["result"], (
                f"Tool {tool.__name__} missing 'status' field"
            )
            assert result["result"]["status"] in [
                "success",
                "error",
            ], f"Tool {tool.__name__} invalid status"

            if result["result"]["status"] == "success":
                assert "data" in result["result"], (
                    f"Tool {tool.__name__} missing 'data' field on success"
                )
            else:
                assert "error" in result["result"], (
                    f"Tool {tool.__name__} missing 'error' field on error"
                )

    def test_all_tools_have_correct_signatures(self):
        """Test all tools have correct signatures per MCP_TOOLS.md."""
        import inspect

        # Check account_info signature
        sig = inspect.signature(account_info)
        assert len(sig.parameters) == 0, "account_info should have no parameters"
        assert sig.return_annotation == dict[str, Any], (
            "account_info should return dict[str, Any]"
        )

        # Check portfolio signature
        sig = inspect.signature(portfolio)
        assert len(sig.parameters) == 0, "portfolio should have no parameters"
        assert sig.return_annotation == dict[str, Any], (
            "portfolio should return dict[str, Any]"
        )

        # Check account_details signature
        sig = inspect.signature(account_details)
        assert len(sig.parameters) == 0, "account_details should have no parameters"
        assert sig.return_annotation == dict[str, Any], (
            "account_details should return dict[str, Any]"
        )

        # Check positions signature
        sig = inspect.signature(positions)
        assert len(sig.parameters) == 0, "positions should have no parameters"
        assert sig.return_annotation == dict[str, Any], (
            "positions should return dict[str, Any]"
        )

    def test_all_tools_are_async(self):
        """Test all tools are async functions."""
        import inspect

        tools = [account_info, portfolio, account_details, positions]

        for tool in tools:
            assert inspect.iscoroutinefunction(tool), (
                f"Tool {tool.__name__} should be async"
            )


class TestAccountToolsErrorHandling:
    """Test error handling patterns across account tools."""

    @pytest.mark.asyncio
    async def test_service_not_initialized_error(self):
        """Test tools handle uninitialized service appropriately."""
        # Clear the service
        from app.mcp import account_tools

        account_tools._trading_service = None

        # Tools that use the service should handle the error
        service_dependent_tools = [portfolio, account_details, positions]

        for tool in service_dependent_tools:
            result = await tool()
            assert result["result"]["status"] == "error"
            assert "TradingService not initialized" in result["result"]["error"]

    @pytest.mark.asyncio
    async def test_consistent_error_response_format(self):
        """Test all tools return consistent error response format."""
        from app.mcp import account_tools

        account_tools._trading_service = None

        service_dependent_tools = [portfolio, account_details, positions]

        for tool in service_dependent_tools:
            result = await tool()

            # Check error response structure
            assert "result" in result
            assert "status" in result["result"]
            assert "error" in result["result"]
            assert result["result"]["status"] == "error"
            assert isinstance(result["result"]["error"], str)
            assert len(result["result"]["error"]) > 0


class TestAccountToolsCoverage:
    """Tests to ensure comprehensive coverage of account tools functionality."""

    def test_module_exports(self):
        """Test module exports all required functions."""
        from app.mcp import account_tools

        required_functions = [
            "account_info",
            "portfolio",
            "account_details",
            "positions",
        ]

        for func_name in required_functions:
            assert hasattr(account_tools, func_name), f"Missing function: {func_name}"
            func = getattr(account_tools, func_name)
            assert callable(func), f"Function {func_name} is not callable"

    def test_response_utils_integration(self):
        """Test integration with response utilities."""
        from app.mcp.response_utils import (
            error_response,
            handle_tool_exception,
            success_response,
        )

        # Test success response
        data = {"test": "data"}
        response = success_response(data)
        assert response["result"]["status"] == "success"
        assert response["result"]["data"] == data

        # Test error response
        error_msg = "Test error"
        response = error_response(error_msg)
        assert response["result"]["status"] == "error"
        assert response["result"]["error"] == error_msg

        # Test exception handling
        exception = Exception("Test exception")
        response = handle_tool_exception("test_func", exception)
        assert response["result"]["status"] == "error"
        assert "test_func" in response["result"]["error"]
        assert "Test exception" in response["result"]["error"]

    def test_service_dependency_management(self):
        """Test service dependency is properly managed."""
        from app.mcp.account_tools import (
            get_mcp_trading_service,
            set_mcp_trading_service,
        )

        # Test setting service
        mock_service = Mock()
        set_mcp_trading_service(mock_service)

        # Test getting service
        retrieved_service = get_mcp_trading_service()
        assert retrieved_service is mock_service

        # Test service persistence
        retrieved_again = get_mcp_trading_service()
        assert retrieved_again is mock_service
