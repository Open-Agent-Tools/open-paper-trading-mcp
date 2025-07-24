"""
Priority 1 Core Functionality Tests

This module tests the core Priority 1 functionality:
- Advanced Order Types & Execution
- TradingService core operations
- Order execution engine basics
- Database connectivity
"""

import pytest
import pytest_asyncio
from datetime import datetime
from sqlalchemy.ext.asyncio import AsyncSession

from app.services.trading_service import TradingService
from app.services.order_execution_engine import OrderExecutionEngine
from app.schemas.orders import OrderCreate, OrderType, OrderCondition, OrderStatus
from app.models.database.trading import Account as DBAccount


@pytest.mark.db_crud
class TestPriority1Core:
    """Test Priority 1 core functionality."""

    @pytest_asyncio.fixture
    async def trading_service(self, async_db_session: AsyncSession) -> TradingService:
        """Create a TradingService instance for testing."""
        from unittest.mock import AsyncMock, MagicMock
        from app.models.quotes import Quote
        from app.models.assets import Stock
        from datetime import datetime
        
        # Create a mock quote adapter that doesn't use database
        mock_adapter = MagicMock()
        mock_adapter.get_quote = AsyncMock()
        mock_adapter.get_quote.return_value = Quote(
            asset=Stock(symbol="AAPL"),
            quote_date=datetime.now(),
            price=150.0,
            bid=149.95,
            ask=150.05,
            volume=1000000,
        )
        
        return TradingService(
            account_owner="test_user",
            db_session=async_db_session,
            quote_adapter=mock_adapter
        )

    @pytest.mark.asyncio
    async def test_trading_service_initialization(
        self, trading_service: TradingService
    ):
        """Test that TradingService initializes correctly."""
        assert trading_service is not None
        assert trading_service.account_owner == "test_user"

    @pytest.mark.asyncio
    async def test_account_creation(
        self, trading_service: TradingService, async_db_session: AsyncSession
    ):
        """Test that accounts can be created."""
        # This tests the core account creation functionality
        await trading_service._ensure_account_exists()
        account = await trading_service._get_account()
        assert account is not None
        assert account.owner == "test_user"
        assert account.cash_balance > 0

    @pytest.mark.asyncio
    async def test_order_creation_basic(
        self, trading_service: TradingService, async_db_session: AsyncSession
    ):
        """Test basic order creation functionality."""
        order_data = OrderCreate(
            symbol="AAPL",
            order_type=OrderType.BUY,
            quantity=100,
            price=150.0,
            condition=OrderCondition.LIMIT
        )
        
        # Ensure account exists first
        await trading_service._ensure_account_exists()
        
        # Test order creation
        order = await trading_service.create_order(order_data)
        assert order is not None
        assert order.symbol == "AAPL"
        assert order.order_type == OrderType.BUY
        assert order.quantity == 100

    @pytest.mark.asyncio
    async def test_order_execution_engine_exists(self, trading_service: TradingService):
        """Test that OrderExecutionEngine can be instantiated."""
        engine = OrderExecutionEngine(trading_service)
        assert engine is not None

    @pytest.mark.asyncio
    async def test_database_connectivity(self, async_db_session: AsyncSession):
        """Test database connectivity and basic operations."""
        # Test that we can create and query an account
        account = DBAccount(
            owner="test_user_db",
            cash_balance=10000.0
        )
        
        async_db_session.add(account)
        await async_db_session.commit()
        await async_db_session.refresh(account)
        
        assert account.owner == "test_user_db"
        assert account.cash_balance == 10000.0

    @pytest.mark.asyncio
    async def test_portfolio_retrieval(
        self, trading_service: TradingService, async_db_session: AsyncSession
    ):
        """Test portfolio retrieval functionality."""
        # Ensure account exists
        await trading_service._ensure_account_exists()
        
        # Get portfolio
        portfolio = await trading_service.get_portfolio()
        assert portfolio is not None
        assert portfolio.cash_balance > 0  # Should have starting balance
        assert isinstance(portfolio.positions, list)  # Should have initial positions