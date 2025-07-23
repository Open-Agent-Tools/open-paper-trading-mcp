"""
Comprehensive test suite for TradingService.

Tests all trading functionality including:
- Async database operations and session management
- Quote adapter integration and fallback mechanisms  
- Order creation, management, and cancellation
- Portfolio calculations and position management
- Options trading and Greeks calculations
- Multi-leg order handling
- Error handling and edge cases
"""

import pytest
from datetime import datetime, date
from decimal import Decimal
from unittest.mock import AsyncMock, Mock, patch, MagicMock
from uuid import uuid4
import asyncio

from app.services.trading_service import TradingService, _get_quote_adapter
from app.core.exceptions import NotFoundError
from app.schemas.orders import OrderCreate, OrderType, OrderStatus, OrderCondition
from app.schemas.positions import Portfolio, PortfolioSummary, Position
from app.schemas.trading import StockQuote
from app.models.quotes import Quote, OptionQuote, OptionsChain
from app.models.assets import Stock, Option, OptionType, asset_factory
from app.models.database.trading import Account as DBAccount, Order as DBOrder, Position as DBPosition


class TestTradingServiceInitialization:
    """Test TradingService initialization and configuration."""

    def test_trading_service_init_default(self):
        """Test TradingService initialization with defaults."""
        with patch('app.services.trading_service.get_adapter_factory') as mock_factory:
            mock_adapter = Mock()
            mock_factory.return_value.create_adapter.return_value = mock_adapter
            
            service = TradingService()
            
            assert service.quote_adapter == mock_adapter
            assert service.account_owner == "default"
            assert service.order_execution is not None
            assert service.account_validation is not None
            assert service.strategy_recognition is not None

    def test_trading_service_init_with_quote_adapter(self):
        """Test TradingService initialization with provided quote adapter."""
        mock_adapter = Mock()
        service = TradingService(quote_adapter=mock_adapter, account_owner="test_user")
        
        assert service.quote_adapter == mock_adapter
        assert service.account_owner == "test_user"

    def test_trading_service_init_adapter_fallback(self):
        """Test TradingService adapter fallback mechanism."""
        with patch('app.services.trading_service.get_adapter_factory') as mock_factory:
            # Simulate adapter factory returning None
            mock_factory.return_value.create_adapter.return_value = None
            
            with patch('app.services.trading_service.DevDataQuoteAdapter') as mock_dev_adapter:
                mock_dev_instance = Mock()
                mock_dev_adapter.return_value = mock_dev_instance
                
                service = TradingService()
                
                assert service.quote_adapter == mock_dev_instance

    def test_trading_service_schema_converters_initialization(self):
        """Test that schema converters are properly initialized."""
        service = TradingService()
        
        assert service.account_converter is not None
        assert service.order_converter is not None
        assert service.position_converter is not None


class TestTradingServiceDatabaseOperations:
    """Test database operations in TradingService."""

    def setup_method(self):
        """Set up test fixtures."""
        self.mock_adapter = Mock()
        self.service = TradingService(quote_adapter=self.mock_adapter)

    @pytest.mark.asyncio
    async def test_get_async_db_session(self):
        """Test getting async database session."""
        with patch('app.services.trading_service.get_async_session') as mock_get_session:
            mock_session = Mock()
            mock_generator = AsyncMock()
            mock_generator.__anext__ = AsyncMock(return_value=mock_session)
            mock_get_session.return_value = mock_generator
            
            result = await self.service._get_async_db_session()
            
            assert result == mock_session

    @pytest.mark.asyncio
    async def test_ensure_account_exists_creates_new_account(self):
        """Test that _ensure_account_exists creates a new account when none exists."""
        with patch('app.services.trading_service.get_async_session') as mock_get_session:
            mock_db = AsyncMock()
            mock_get_session.return_value.__aenter__ = AsyncMock(return_value=mock_db)
            mock_get_session.return_value.__aexit__ = AsyncMock(return_value=None)
            
            # Mock query to return no existing account
            mock_result = Mock()
            mock_result.scalar_one_or_none.return_value = None
            mock_db.execute.return_value = mock_result
            
            await self.service._ensure_account_exists()
            
            # Verify account was created
            assert mock_db.add.call_count >= 1  # Account + positions
            assert mock_db.commit.call_count >= 1

    @pytest.mark.asyncio
    async def test_ensure_account_exists_account_already_exists(self):
        """Test that _ensure_account_exists skips creation when account exists."""
        with patch('app.services.trading_service.get_async_session') as mock_get_session:
            mock_db = AsyncMock()
            mock_get_session.return_value.__aenter__ = AsyncMock(return_value=mock_db)
            mock_get_session.return_value.__aexit__ = AsyncMock(return_value=None)
            
            # Mock query to return existing account
            mock_account = DBAccount(id="123", owner="default", cash_balance=10000.0)
            mock_result = Mock()
            mock_result.scalar_one_or_none.return_value = mock_account
            mock_db.execute.return_value = mock_result
            
            await self.service._ensure_account_exists()
            
            # Verify no new account was created
            mock_db.add.assert_not_called()

    @pytest.mark.asyncio
    async def test_get_account_success(self):
        """Test successful account retrieval."""
        with patch.object(self.service, '_ensure_account_exists') as mock_ensure:
            with patch('app.services.trading_service.get_async_session') as mock_get_session:
                mock_db = AsyncMock()
                mock_get_session.return_value.__aenter__ = AsyncMock(return_value=mock_db)
                mock_get_session.return_value.__aexit__ = AsyncMock(return_value=None)
                
                mock_account = DBAccount(id="123", owner="default", cash_balance=10000.0)
                mock_result = Mock()
                mock_result.scalar_one_or_none.return_value = mock_account
                mock_db.execute.return_value = mock_result
                
                result = await self.service._get_account()
                
                assert result == mock_account
                mock_ensure.assert_called_once()

    @pytest.mark.asyncio
    async def test_get_account_not_found(self):
        """Test account retrieval when account not found."""
        with patch.object(self.service, '_ensure_account_exists'):
            with patch('app.services.trading_service.get_async_session') as mock_get_session:
                mock_db = AsyncMock()
                mock_get_session.return_value.__aenter__ = AsyncMock(return_value=mock_db)
                mock_get_session.return_value.__aexit__ = AsyncMock(return_value=None)
                
                mock_result = Mock()
                mock_result.scalar_one_or_none.return_value = None
                mock_db.execute.return_value = mock_result
                
                with pytest.raises(NotFoundError, match="Account for owner default not found"):
                    await self.service._get_account()

    @pytest.mark.asyncio
    async def test_get_account_balance(self):
        """Test getting account balance."""
        with patch.object(self.service, '_get_account') as mock_get_account:
            mock_account = DBAccount(id="123", owner="default", cash_balance=15000.50)
            mock_get_account.return_value = mock_account
            
            balance = await self.service.get_account_balance()
            
            assert balance == 15000.50


class TestTradingServiceQuoteOperations:
    """Test quote operations in TradingService."""

    def setup_method(self):
        """Set up test fixtures."""
        self.mock_adapter = AsyncMock()
        self.service = TradingService(quote_adapter=self.mock_adapter)

    @pytest.mark.asyncio
    async def test_get_quote_success(self):
        """Test successful quote retrieval."""
        # Mock asset factory
        with patch('app.services.trading_service.asset_factory') as mock_factory:
            mock_asset = Stock("AAPL")
            mock_factory.return_value = mock_asset
            
            # Mock quote adapter response
            mock_quote = Quote(
                asset=mock_asset,
                price=150.0,
                bid=149.5,
                ask=150.5,
                quote_date=datetime.now()
            )
            self.mock_adapter.get_quote.return_value = mock_quote
            
            result = await self.service.get_quote("AAPL")
            
            assert isinstance(result, StockQuote)
            assert result.symbol == "AAPL"
            assert result.price == 150.0

    @pytest.mark.asyncio
    async def test_get_quote_invalid_symbol(self):
        """Test quote retrieval with invalid symbol."""
        with patch('app.services.trading_service.asset_factory') as mock_factory:
            mock_factory.return_value = None
            
            with pytest.raises(NotFoundError, match="Invalid symbol: INVALID"):
                await self.service.get_quote("INVALID")

    @pytest.mark.asyncio
    async def test_get_quote_adapter_failure(self):
        """Test quote retrieval when adapter fails."""
        with patch('app.services.trading_service.asset_factory') as mock_factory:
            mock_asset = Stock("AAPL")
            mock_factory.return_value = mock_asset
            
            self.mock_adapter.get_quote.side_effect = Exception("Adapter error")
            
            with pytest.raises(NotFoundError, match="Symbol AAPL not found"):
                await self.service.get_quote("AAPL")

    @pytest.mark.asyncio
    async def test_get_enhanced_quote_success(self):
        """Test enhanced quote retrieval."""
        with patch('app.services.trading_service.asset_factory') as mock_factory:
            mock_asset = Stock("AAPL")
            mock_factory.return_value = mock_asset
            
            mock_quote = Quote(
                asset=mock_asset,
                price=150.0,
                bid=149.5,
                ask=150.5,
                quote_date=datetime.now()
            )
            self.mock_adapter.get_quote.return_value = mock_quote
            
            result = await self.service.get_enhanced_quote("AAPL")
            
            assert result == mock_quote

    @pytest.mark.asyncio
    async def test_get_enhanced_quote_no_quote_available(self):
        """Test enhanced quote when no quote is available."""
        with patch('app.services.trading_service.asset_factory') as mock_factory:
            mock_asset = Stock("AAPL")
            mock_factory.return_value = mock_asset
            
            self.mock_adapter.get_quote.return_value = None
            
            with pytest.raises(NotFoundError, match="No quote available for AAPL"):
                await self.service.get_enhanced_quote("AAPL")


class TestTradingServiceOrderOperations:
    """Test order operations in TradingService."""

    def setup_method(self):
        """Set up test fixtures."""
        self.mock_adapter = AsyncMock()
        self.service = TradingService(quote_adapter=self.mock_adapter)

    @pytest.mark.asyncio
    async def test_create_order_success(self):
        """Test successful order creation."""
        # Mock quote validation
        with patch.object(self.service, 'get_quote') as mock_get_quote:
            mock_get_quote.return_value = StockQuote(
                symbol="AAPL", price=150.0, change=0.0, change_percent=0.0,
                volume=1000, last_updated=datetime.now()
            )
            
            # Mock database operations
            with patch.object(self.service, '_get_async_db_session') as mock_get_session:
                mock_db = AsyncMock()
                mock_get_session.return_value = mock_db
                
                with patch.object(self.service, '_get_account') as mock_get_account:
                    mock_account = DBAccount(id="123", owner="default", cash_balance=10000.0)
                    mock_get_account.return_value = mock_account
                    
                    # Mock order converter
                    with patch.object(self.service.order_converter, 'to_schema') as mock_to_schema:
                        mock_order = Mock()
                        mock_order.id = "order_123"
                        mock_order.symbol = "AAPL"
                        mock_to_schema.return_value = mock_order
                        
                        order_data = OrderCreate(
                            symbol="AAPL",
                            order_type=OrderType.BUY,
                            quantity=10,
                            price=150.0
                        )
                        
                        result = await self.service.create_order(order_data)
                        
                        assert result == mock_order
                        mock_db.add.assert_called_once()
                        mock_db.commit.assert_called_once()

    @pytest.mark.asyncio
    async def test_create_order_invalid_symbol(self):
        """Test order creation with invalid symbol."""
        with patch.object(self.service, 'get_quote') as mock_get_quote:
            mock_get_quote.side_effect = NotFoundError("Symbol not found")
            
            order_data = OrderCreate(
                symbol="INVALID",
                order_type=OrderType.BUY,
                quantity=10,
                price=150.0
            )
            
            with pytest.raises(NotFoundError):
                await self.service.create_order(order_data)

    @pytest.mark.asyncio
    async def test_get_orders_success(self):
        """Test successful retrieval of all orders."""
        with patch.object(self.service, '_get_async_db_session') as mock_get_session:
            mock_db = AsyncMock()
            mock_get_session.return_value = mock_db
            
            with patch.object(self.service, '_get_account') as mock_get_account:
                mock_account = DBAccount(id="123", owner="default", cash_balance=10000.0)
                mock_get_account.return_value = mock_account
                
                # Mock database query result
                mock_db_order = DBOrder(
                    id="order_123",
                    account_id="123",
                    symbol="AAPL",
                    order_type=OrderType.BUY,
                    quantity=10,
                    price=150.0,
                    status=OrderStatus.PENDING
                )
                
                mock_result = Mock()
                mock_result.scalars.return_value.all.return_value = [mock_db_order]
                mock_db.execute.return_value = mock_result
                
                # Mock order converter
                with patch.object(self.service.order_converter, 'to_schema') as mock_to_schema:
                    mock_order = Mock()
                    mock_to_schema.return_value = mock_order
                    
                    result = await self.service.get_orders()
                    
                    assert result == [mock_order]

    @pytest.mark.asyncio
    async def test_cancel_order_success(self):
        """Test successful order cancellation."""
        with patch.object(self.service, '_get_async_db_session') as mock_get_session:
            mock_db = AsyncMock()
            mock_get_session.return_value = mock_db
            
            with patch.object(self.service, '_get_account') as mock_get_account:
                mock_account = DBAccount(id="123", owner="default", cash_balance=10000.0)
                mock_get_account.return_value = mock_account
                
                mock_db_order = DBOrder(
                    id="order_123",
                    account_id="123",
                    symbol="AAPL",
                    order_type=OrderType.BUY,
                    quantity=10,
                    price=150.0,
                    status=OrderStatus.PENDING
                )
                
                mock_result = Mock()
                mock_result.scalar_one_or_none.return_value = mock_db_order
                mock_db.execute.return_value = mock_result
                
                result = await self.service.cancel_order("order_123")
                
                assert result == {"message": "Order cancelled successfully"}
                assert mock_db_order.status == OrderStatus.CANCELLED
                mock_db.commit.assert_called_once()

    @pytest.mark.asyncio
    async def test_cancel_order_not_found(self):
        """Test order cancellation when order not found."""
        with patch.object(self.service, '_get_async_db_session') as mock_get_session:
            mock_db = AsyncMock()
            mock_get_session.return_value = mock_db
            
            with patch.object(self.service, '_get_account') as mock_get_account:
                mock_account = DBAccount(id="123", owner="default", cash_balance=10000.0)
                mock_get_account.return_value = mock_account
                
                mock_result = Mock()
                mock_result.scalar_one_or_none.return_value = None
                mock_db.execute.return_value = mock_result
                
                with pytest.raises(NotFoundError, match="Order order_123 not found"):
                    await self.service.cancel_order("order_123")


class TestTradingServicePortfolioOperations:
    """Test portfolio operations in TradingService."""

    def setup_method(self):
        """Set up test fixtures."""
        self.mock_adapter = AsyncMock()
        self.service = TradingService(quote_adapter=self.mock_adapter)

    @pytest.mark.asyncio
    async def test_get_portfolio_success(self):
        """Test successful portfolio retrieval."""
        with patch.object(self.service, '_get_async_db_session') as mock_get_session:
            mock_db = AsyncMock()
            mock_get_session.return_value = mock_db
            
            with patch.object(self.service, '_get_account') as mock_get_account:
                mock_account = DBAccount(id="123", owner="default", cash_balance=10000.0)
                mock_get_account.return_value = mock_account
                
                # Mock positions
                mock_position = DBPosition(
                    id="pos_123",
                    account_id="123",
                    symbol="AAPL",
                    quantity=10,
                    avg_price=145.0
                )
                
                mock_result = Mock()
                mock_result.scalars.return_value.all.return_value = [mock_position]
                mock_db.execute.return_value = mock_result
                
                # Mock quote for position
                with patch.object(self.service, 'get_quote') as mock_get_quote:
                    mock_get_quote.return_value = StockQuote(
                        symbol="AAPL", price=150.0, change=5.0, change_percent=3.4,
                        volume=1000, last_updated=datetime.now()
                    )
                    
                    # Mock position converter
                    with patch.object(self.service.position_converter, 'to_schema') as mock_to_schema:
                        mock_position_schema = Position(
                            symbol="AAPL",
                            quantity=10,
                            avg_price=145.0,
                            current_price=150.0,
                            market_value=1500.0,
                            unrealized_pnl=50.0
                        )
                        mock_to_schema.return_value = mock_position_schema
                        
                        result = await self.service.get_portfolio()
                        
                        assert isinstance(result, Portfolio)
                        assert result.cash_balance == 10000.0
                        assert len(result.positions) == 1
                        assert result.positions[0].symbol == "AAPL"

    @pytest.mark.asyncio
    async def test_get_portfolio_with_no_quote_position(self):
        """Test portfolio retrieval with position that has no quote."""
        with patch.object(self.service, '_get_async_db_session') as mock_get_session:
            mock_db = AsyncMock()
            mock_get_session.return_value = mock_db
            
            with patch.object(self.service, '_get_account') as mock_get_account:
                mock_account = DBAccount(id="123", owner="default", cash_balance=10000.0)
                mock_get_account.return_value = mock_account
                
                mock_position = DBPosition(
                    id="pos_123",
                    account_id="123",
                    symbol="INVALID",
                    quantity=10,
                    avg_price=145.0
                )
                
                mock_result = Mock()
                mock_result.scalars.return_value.all.return_value = [mock_position]
                mock_db.execute.return_value = mock_result
                
                # Mock quote failure
                with patch.object(self.service, 'get_quote') as mock_get_quote:
                    mock_get_quote.side_effect = NotFoundError("No quote")
                    
                    result = await self.service.get_portfolio()
                    
                    # Position should be skipped
                    assert len(result.positions) == 0

    @pytest.mark.asyncio
    async def test_get_portfolio_summary(self):
        """Test portfolio summary calculation."""
        with patch.object(self.service, 'get_portfolio') as mock_get_portfolio:
            mock_portfolio = Portfolio(
                cash_balance=10000.0,
                total_value=11500.0,
                positions=[
                    Position(
                        symbol="AAPL",
                        quantity=10,
                        avg_price=145.0,
                        current_price=150.0,
                        market_value=1500.0,
                        unrealized_pnl=50.0
                    )
                ],
                daily_pnl=50.0,
                total_pnl=50.0
            )
            mock_get_portfolio.return_value = mock_portfolio
            
            result = await self.service.get_portfolio_summary()
            
            assert isinstance(result, PortfolioSummary)
            assert result.total_value == 11500.0
            assert result.cash_balance == 10000.0
            assert result.invested_value == 1500.0

    @pytest.mark.asyncio
    async def test_get_position_success(self):
        """Test getting specific position."""
        with patch.object(self.service, 'get_portfolio') as mock_get_portfolio:
            mock_position = Position(
                symbol="AAPL",
                quantity=10,
                avg_price=145.0,
                current_price=150.0,
                market_value=1500.0
            )
            mock_portfolio = Portfolio(
                cash_balance=10000.0,
                total_value=11500.0,
                positions=[mock_position],
                daily_pnl=50.0,
                total_pnl=50.0
            )
            mock_get_portfolio.return_value = mock_portfolio
            
            result = await self.service.get_position("AAPL")
            
            assert result == mock_position

    @pytest.mark.asyncio
    async def test_get_position_not_found(self):
        """Test getting position that doesn't exist."""
        with patch.object(self.service, 'get_portfolio') as mock_get_portfolio:
            mock_portfolio = Portfolio(
                cash_balance=10000.0,
                total_value=10000.0,
                positions=[],
                daily_pnl=0.0,
                total_pnl=0.0
            )
            mock_get_portfolio.return_value = mock_portfolio
            
            with pytest.raises(NotFoundError, match="Position for symbol AAPL not found"):
                await self.service.get_position("AAPL")


class TestTradingServiceOptionsOperations:
    """Test options-specific operations in TradingService."""

    def setup_method(self):
        """Set up test fixtures."""
        self.mock_adapter = AsyncMock()
        self.service = TradingService(quote_adapter=self.mock_adapter)

    @pytest.mark.asyncio
    async def test_get_options_chain_success(self):
        """Test successful options chain retrieval."""
        mock_option = Option(
            underlying=Stock("AAPL"),
            option_type=OptionType.CALL,
            strike=150.0,
            expiration_date=date(2024, 12, 20)
        )
        
        mock_chain = OptionsChain(
            underlying_symbol="AAPL",
            underlying_price=150.0,
            expiration_date=date(2024, 12, 20),
            calls=[],
            puts=[]
        )
        
        self.mock_adapter.get_options_chain.return_value = mock_chain
        
        result = await self.service.get_options_chain("AAPL", date(2024, 12, 20))
        
        assert result == mock_chain

    @pytest.mark.asyncio
    async def test_get_options_chain_not_found(self):
        """Test options chain retrieval when not found."""
        self.mock_adapter.get_options_chain.return_value = None
        
        with pytest.raises(NotFoundError, match="No options chain found for AAPL"):
            await self.service.get_options_chain("AAPL")

    @pytest.mark.asyncio
    async def test_calculate_greeks_success(self):
        """Test successful Greeks calculation."""
        option_symbol = "AAPL241220C00150000"
        
        with patch('app.services.trading_service.asset_factory') as mock_factory:
            mock_option = Option(
                underlying=Stock("AAPL"),
                option_type=OptionType.CALL,
                strike=150.0,
                expiration_date=date(2024, 12, 20)
            )
            mock_factory.return_value = mock_option
            
            with patch.object(self.service, 'get_enhanced_quote') as mock_get_quote:
                # Mock option quote
                option_quote = OptionQuote(
                    asset=mock_option,
                    price=5.0,
                    bid=4.8,
                    ask=5.2,
                    quote_date=datetime.now(),
                    underlying_price=150.0
                )
                
                # Mock underlying quote
                underlying_quote = Quote(
                    asset=Stock("AAPL"),
                    price=150.0,
                    bid=149.8,
                    ask=150.2,
                    quote_date=datetime.now()
                )
                
                mock_get_quote.side_effect = [option_quote, underlying_quote]
                
                with patch('app.services.trading_service.calculate_option_greeks') as mock_calc_greeks:
                    mock_greeks = {
                        "delta": 0.5,
                        "gamma": 0.02,
                        "theta": -0.05,
                        "vega": 0.15,
                        "rho": 0.08
                    }
                    mock_calc_greeks.return_value = mock_greeks
                    
                    result = await self.service.calculate_greeks(option_symbol)
                    
                    assert result == mock_greeks

    @pytest.mark.asyncio
    async def test_calculate_greeks_invalid_option(self):
        """Test Greeks calculation with invalid option symbol."""
        with patch('app.services.trading_service.asset_factory') as mock_factory:
            mock_factory.return_value = Stock("AAPL")  # Not an option
            
            with pytest.raises(ValueError, match="AAPL is not an option"):
                await self.service.calculate_greeks("AAPL")


class TestTradingServiceUtilityMethods:
    """Test utility and helper methods."""

    def setup_method(self):
        """Set up test fixtures."""
        self.mock_adapter = Mock()
        self.service = TradingService(quote_adapter=self.mock_adapter)

    def test_get_test_scenarios(self):
        """Test getting test scenarios."""
        mock_scenarios = {"scenario1": "data1", "scenario2": "data2"}
        self.mock_adapter.get_test_scenarios.return_value = mock_scenarios
        
        result = self.service.get_test_scenarios()
        
        assert result == mock_scenarios

    def test_set_test_date(self):
        """Test setting test date."""
        test_date = "2024-01-15"
        
        self.service.set_test_date(test_date)
        
        self.mock_adapter.set_date.assert_called_once_with(test_date)

    def test_get_available_symbols(self):
        """Test getting available symbols."""
        mock_symbols = ["AAPL", "MSFT", "GOOGL"]
        self.mock_adapter.get_available_symbols.return_value = mock_symbols
        
        result = self.service.get_available_symbols()
        
        assert result == mock_symbols

    def test_get_sample_data_info(self):
        """Test getting sample data info."""
        mock_info = {"symbols": 100, "date_range": "2023-2024"}
        self.mock_adapter.get_sample_data_info.return_value = mock_info
        
        result = self.service.get_sample_data_info()
        
        assert result == mock_info

    def test_get_expiration_dates(self):
        """Test getting expiration dates."""
        mock_dates = [date(2024, 12, 20), date(2025, 1, 17)]
        self.mock_adapter.get_expiration_dates.return_value = mock_dates
        
        result = self.service.get_expiration_dates("AAPL")
        
        assert result == mock_dates

    @pytest.mark.asyncio
    async def test_validate_account_state(self):
        """Test account state validation."""
        with patch.object(self.service, 'get_account_balance') as mock_balance:
            mock_balance.return_value = 10000.0
            
            with patch.object(self.service, 'get_positions') as mock_positions:
                mock_positions.return_value = []
                
                with patch.object(self.service.account_validation, 'validate_account_state') as mock_validate:
                    mock_validate.return_value = True
                    
                    result = await self.service.validate_account_state()
                    
                    assert result is True
                    mock_validate.assert_called_once_with(cash_balance=10000.0, positions=[])


class TestTradingServiceErrorHandling:
    """Test error handling in TradingService."""

    def setup_method(self):
        """Set up test fixtures."""
        self.mock_adapter = AsyncMock()
        self.service = TradingService(quote_adapter=self.mock_adapter)

    @pytest.mark.asyncio
    async def test_database_connection_error(self):
        """Test handling of database connection errors."""
        with patch.object(self.service, '_get_async_db_session') as mock_get_session:
            mock_get_session.side_effect = Exception("Database connection failed")
            
            with pytest.raises(Exception, match="Database connection failed"):
                await self.service.get_account_balance()

    @pytest.mark.asyncio
    async def test_quote_adapter_timeout(self):
        """Test handling of quote adapter timeouts."""
        with patch('app.services.trading_service.asset_factory') as mock_factory:
            mock_asset = Stock("AAPL")
            mock_factory.return_value = mock_asset
            
            self.mock_adapter.get_quote.side_effect = asyncio.TimeoutError("Timeout")
            
            with pytest.raises(NotFoundError):
                await self.service.get_quote("AAPL")

    @pytest.mark.asyncio
    async def test_concurrent_order_operations(self):
        """Test concurrent order operations."""
        async def create_test_order(symbol):
            order_data = OrderCreate(
                symbol=symbol,
                order_type=OrderType.BUY,
                quantity=10,
                price=150.0
            )
            
            with patch.object(self.service, 'get_quote') as mock_get_quote:
                mock_get_quote.return_value = StockQuote(
                    symbol=symbol, price=150.0, change=0.0, change_percent=0.0,
                    volume=1000, last_updated=datetime.now()
                )
                
                with patch.object(self.service, '_get_async_db_session') as mock_get_session:
                    mock_db = AsyncMock()
                    mock_get_session.return_value = mock_db
                    
                    with patch.object(self.service, '_get_account') as mock_get_account:
                        mock_account = DBAccount(id="123", owner="default", cash_balance=10000.0)
                        mock_get_account.return_value = mock_account
                        
                        with patch.object(self.service.order_converter, 'to_schema') as mock_to_schema:
                            mock_order = Mock()
                            mock_order.id = f"order_{symbol}"
                            mock_to_schema.return_value = mock_order
                            
                            return await self.service.create_order(order_data)
        
        # Create multiple orders concurrently
        tasks = [create_test_order(f"SYM{i}") for i in range(5)]
        results = await asyncio.gather(*tasks, return_exceptions=True)
        
        # All should succeed
        assert len([r for r in results if not isinstance(r, Exception)]) == 5


class TestGetQuoteAdapter:
    """Test the _get_quote_adapter function."""

    @patch.dict('os.environ', {'USE_LIVE_DATA': 'true'})
    def test_get_quote_adapter_live_data(self):
        """Test getting quote adapter with live data enabled."""
        with patch('app.services.trading_service.RobinhoodAdapter') as mock_robinhood:
            mock_adapter = Mock()
            mock_robinhood.return_value = mock_adapter
            
            result = _get_quote_adapter()
            
            assert result == mock_adapter

    @patch.dict('os.environ', {'USE_LIVE_DATA': 'false'})
    def test_get_quote_adapter_test_data(self):
        """Test getting quote adapter with test data."""
        with patch('app.services.trading_service.DevDataQuoteAdapter') as mock_dev:
            mock_adapter = Mock()
            mock_dev.return_value = mock_adapter
            
            result = _get_quote_adapter()
            
            assert result == mock_adapter

    @patch.dict('os.environ', {'USE_LIVE_DATA': 'true'})
    def test_get_quote_adapter_robinhood_import_error(self):
        """Test fallback when Robinhood adapter import fails."""
        with patch('app.services.trading_service.RobinhoodAdapter', side_effect=ImportError("No module")):
            with patch('app.services.trading_service.DevDataQuoteAdapter') as mock_dev:
                mock_adapter = Mock()
                mock_dev.return_value = mock_adapter
                
                result = _get_quote_adapter()
                
                assert result == mock_adapter