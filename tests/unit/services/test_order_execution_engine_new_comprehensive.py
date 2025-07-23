"""Comprehensive tests for order_execution_engine.py - Advanced order execution engine."""

import pytest
import asyncio
from datetime import datetime, date
from unittest.mock import AsyncMock, Mock, patch, MagicMock
from collections import defaultdict

from app.services.order_execution_engine import (
    OrderExecutionEngine,
    TriggerCondition,
    OrderExecutionError,
    get_execution_engine,
    initialize_execution_engine,
)
from app.schemas.orders import Order, OrderStatus, OrderType, OrderCondition
from app.services.trading_service import TradingService
from app.models.assets import Stock, Call, Put
from app.models.quotes import Quote


class MockTradingService:
    """Mock trading service for testing."""
    
    def __init__(self):
        self.executed_orders = []
        
    async def execute_order(self, order: Order):
        """Mock order execution."""
        self.executed_orders.append(order)


class MockQuoteAdapter:
    """Mock quote adapter for testing."""
    
    def __init__(self, prices: dict[str, float] = None):
        self.prices = prices or {}
        
    async def get_quote(self, asset):
        """Return mock quote."""
        symbol = asset.symbol if hasattr(asset, 'symbol') else str(asset)
        price = self.prices.get(symbol, 100.0)
        
        return Quote(
            asset=asset,
            quote_date=datetime.now(),
            price=price,
            bid=price - 0.5,
            ask=price + 0.5,
            bid_size=100,
            ask_size=100,
            volume=1000
        )


@pytest.fixture
def mock_trading_service():
    """Create mock trading service."""
    return MockTradingService()


@pytest.fixture
def execution_engine(mock_trading_service):
    """Create execution engine for testing."""
    return OrderExecutionEngine(mock_trading_service)


@pytest.fixture
def sample_stop_loss_order():
    """Create sample stop loss order."""
    return Order(
        id="stop_loss_123",
        symbol="AAPL",
        order_type=OrderType.STOP_LOSS,
        quantity=-100,  # Sell order
        price=None,
        stop_price=145.0,
        condition=OrderCondition.MARKET,
        status=OrderStatus.PENDING
    )


@pytest.fixture
def sample_stop_limit_order():
    """Create sample stop limit order."""
    return Order(
        id="stop_limit_123",
        symbol="AAPL",
        order_type=OrderType.STOP_LIMIT,
        quantity=-100,
        price=145.0,  # Limit price
        stop_price=147.0,  # Stop price
        condition=OrderCondition.LIMIT,
        status=OrderStatus.PENDING
    )


@pytest.fixture
def sample_trailing_stop_order():
    """Create sample trailing stop order."""
    return Order(
        id="trailing_stop_123",
        symbol="AAPL",
        order_type=OrderType.TRAILING_STOP,
        quantity=-100,
        price=None,
        trail_percent=5.0,  # 5% trailing stop
        condition=OrderCondition.MARKET,
        status=OrderStatus.PENDING
    )


class TestTriggerCondition:
    """Test TriggerCondition class."""
    
    def test_trigger_condition_initialization(self):
        """Test trigger condition initialization."""
        condition = TriggerCondition(
            order_id="order123",
            symbol="AAPL",
            trigger_type="stop_loss",
            trigger_price=145.0,
            order_type=OrderType.SELL
        )
        
        assert condition.order_id == "order123"
        assert condition.symbol == "AAPL"
        assert condition.trigger_type == "stop_loss"
        assert condition.trigger_price == 145.0
        assert condition.order_type == OrderType.SELL
        assert isinstance(condition.created_at, datetime)
        assert condition.high_water_mark is None
        assert condition.low_water_mark is None
    
    def test_should_trigger_stop_loss_sell(self):
        """Test stop loss sell trigger condition."""
        condition = TriggerCondition(
            order_id="order123",
            symbol="AAPL",
            trigger_type="stop_loss",
            trigger_price=145.0,
            order_type=OrderType.SELL
        )
        
        # Should trigger when price drops to or below trigger
        assert condition.should_trigger(145.0) is True
        assert condition.should_trigger(144.0) is True
        assert condition.should_trigger(146.0) is False
    
    def test_should_trigger_stop_loss_buy(self):
        """Test stop loss buy trigger condition."""
        condition = TriggerCondition(
            order_id="order123",
            symbol="AAPL",
            trigger_type="stop_loss",
            trigger_price=155.0,
            order_type=OrderType.BUY
        )
        
        # Should trigger when price rises to or above trigger
        assert condition.should_trigger(155.0) is True
        assert condition.should_trigger(156.0) is True
        assert condition.should_trigger(154.0) is False
    
    def test_should_trigger_trailing_stop(self):
        """Test trailing stop trigger condition."""
        condition = TriggerCondition(
            order_id="order123",
            symbol="AAPL",
            trigger_type="trailing_stop",
            trigger_price=145.0,
            order_type=OrderType.SELL
        )
        
        # Same logic as stop loss for basic triggering
        assert condition.should_trigger(145.0) is True
        assert condition.should_trigger(144.0) is True
        assert condition.should_trigger(146.0) is False
    
    def test_update_trailing_stop_percentage_sell(self):
        """Test updating trailing stop with percentage for sell order."""
        condition = TriggerCondition(
            order_id="order123",
            symbol="AAPL",
            trigger_type="trailing_stop",
            trigger_price=145.0,
            order_type=OrderType.SELL
        )
        
        # Mock order with trail percentage
        order = Mock()
        order.quantity = -100  # Sell order
        order.trail_percent = 5.0
        order.trail_amount = None
        
        # Price goes up, should update trigger price
        updated = condition.update_trailing_stop(155.0, order)
        
        assert updated is True
        assert condition.high_water_mark == 155.0
        # New trigger = 155.0 * (1 - 0.05) = 147.25
        assert condition.trigger_price == 147.25
    
    def test_update_trailing_stop_percentage_buy(self):
        """Test updating trailing stop with percentage for buy order."""
        condition = TriggerCondition(
            order_id="order123",
            symbol="AAPL",
            trigger_type="trailing_stop",
            trigger_price=155.0,
            order_type=OrderType.BUY
        )
        
        # Mock order with trail percentage
        order = Mock()
        order.quantity = 100  # Buy order
        order.trail_percent = 5.0
        order.trail_amount = None
        
        # Price goes down, should update trigger price
        updated = condition.update_trailing_stop(145.0, order)
        
        assert updated is True
        assert condition.low_water_mark == 145.0
        # New trigger = 145.0 * (1 + 0.05) = 152.25
        assert condition.trigger_price == 152.25
    
    def test_update_trailing_stop_amount_sell(self):
        """Test updating trailing stop with dollar amount for sell order."""
        condition = TriggerCondition(
            order_id="order123",
            symbol="AAPL",
            trigger_type="trailing_stop",
            trigger_price=145.0,
            order_type=OrderType.SELL
        )
        
        # Mock order with trail amount
        order = Mock()
        order.quantity = -100  # Sell order
        order.trail_percent = None
        order.trail_amount = 5.0
        
        # Price goes up, should update trigger price
        updated = condition.update_trailing_stop(155.0, order)
        
        assert updated is True
        assert condition.high_water_mark == 155.0
        # New trigger = 155.0 - 5.0 = 150.0
        assert condition.trigger_price == 150.0
    
    def test_update_trailing_stop_no_update(self):
        """Test trailing stop when price doesn't warrant update."""
        condition = TriggerCondition(
            order_id="order123",
            symbol="AAPL",
            trigger_type="trailing_stop",
            trigger_price=145.0,
            order_type=OrderType.SELL
        )
        
        # Set initial high water mark
        condition.high_water_mark = 155.0
        
        # Mock order
        order = Mock()
        order.quantity = -100
        order.trail_percent = 5.0
        order.trail_amount = None
        
        # Price goes down, should not update
        updated = condition.update_trailing_stop(150.0, order)
        
        assert updated is False
        assert condition.high_water_mark == 155.0  # Unchanged
    
    def test_update_trailing_stop_non_trailing_type(self):
        """Test updating non-trailing stop condition."""
        condition = TriggerCondition(
            order_id="order123",
            symbol="AAPL",
            trigger_type="stop_loss",  # Not trailing
            trigger_price=145.0,
            order_type=OrderType.SELL
        )
        
        order = Mock()
        updated = condition.update_trailing_stop(155.0, order)
        
        assert updated is False


class TestOrderExecutionEngineInitialization:
    """Test OrderExecutionEngine initialization."""
    
    def test_engine_initialization(self, mock_trading_service):
        """Test engine initialization."""
        engine = OrderExecutionEngine(mock_trading_service)
        
        assert engine.trading_service is mock_trading_service
        assert engine.is_running is False
        assert engine.monitoring_task is None
        assert isinstance(engine.trigger_conditions, dict)
        assert isinstance(engine.monitored_symbols, set)
        assert engine.orders_processed == 0
        assert engine.orders_triggered == 0
        assert isinstance(engine.last_market_data_update, datetime)
    
    def test_engine_attributes(self, execution_engine):
        """Test engine has required attributes."""
        assert hasattr(execution_engine, 'trading_service')
        assert hasattr(execution_engine, 'is_running')
        assert hasattr(execution_engine, 'trigger_conditions')
        assert hasattr(execution_engine, 'monitored_symbols')
        assert hasattr(execution_engine, 'orders_processed')
        assert hasattr(execution_engine, 'orders_triggered')


class TestOrderAdditionAndRemoval:
    """Test adding and removing orders from monitoring."""
    
    @pytest.mark.asyncio
    async def test_add_order_stop_loss(self, execution_engine, sample_stop_loss_order):
        """Test adding stop loss order."""
        with patch('app.services.order_execution_engine.order_converter') as mock_converter:
            mock_converter.can_convert_order.return_value = True
            mock_converter.validate_order_for_conversion.return_value = True
            
            await execution_engine.add_order(sample_stop_loss_order)
            
            assert "AAPL" in execution_engine.monitored_symbols
            assert len(execution_engine.trigger_conditions["AAPL"]) == 1
            
            condition = execution_engine.trigger_conditions["AAPL"][0]
            assert condition.order_id == "stop_loss_123"
            assert condition.symbol == "AAPL"
            assert condition.trigger_price == 145.0
    
    @pytest.mark.asyncio
    async def test_add_order_non_convertible(self, execution_engine):
        """Test adding non-convertible order."""
        regular_order = Order(
            id="regular_order",
            symbol="AAPL",
            order_type=OrderType.BUY,
            quantity=100,
            price=150.0,
            condition=OrderCondition.MARKET,
            status=OrderStatus.PENDING
        )
        
        with patch('app.services.order_execution_engine.order_converter') as mock_converter:
            mock_converter.can_convert_order.return_value = False
            
            # Should not add to monitoring
            await execution_engine.add_order(regular_order)
            
            assert len(execution_engine.monitored_symbols) == 0
            assert len(execution_engine.trigger_conditions) == 0
    
    @pytest.mark.asyncio
    async def test_add_order_invalid(self, execution_engine, sample_stop_loss_order):
        """Test adding invalid order."""
        with patch('app.services.order_execution_engine.order_converter') as mock_converter:
            mock_converter.can_convert_order.return_value = True
            mock_converter.validate_order_for_conversion.side_effect = Exception("Invalid order")
            
            with pytest.raises(OrderExecutionError, match="Invalid order for monitoring"):
                await execution_engine.add_order(sample_stop_loss_order)
    
    @pytest.mark.asyncio
    async def test_remove_order(self, execution_engine, sample_stop_loss_order):
        """Test removing order from monitoring."""
        with patch('app.services.order_execution_engine.order_converter') as mock_converter:
            mock_converter.can_convert_order.return_value = True
            mock_converter.validate_order_for_conversion.return_value = True
            
            # Add order first
            await execution_engine.add_order(sample_stop_loss_order)
            assert len(execution_engine.trigger_conditions["AAPL"]) == 1
            
            # Remove order
            await execution_engine.remove_order("stop_loss_123")
            
            assert len(execution_engine.trigger_conditions.get("AAPL", [])) == 0
            assert "AAPL" not in execution_engine.monitored_symbols
    
    @pytest.mark.asyncio
    async def test_remove_nonexistent_order(self, execution_engine):
        """Test removing non-existent order."""
        # Should not raise exception
        await execution_engine.remove_order("nonexistent_order")
        
        assert len(execution_engine.monitored_symbols) == 0


class TestEngineStartStop:
    """Test engine start/stop functionality."""
    
    @pytest.mark.asyncio
    async def test_start_engine(self, execution_engine):
        """Test starting the engine."""
        with patch.object(execution_engine, '_load_pending_orders', new_callable=AsyncMock):
            await execution_engine.start()
            
            assert execution_engine.is_running is True
            assert execution_engine.monitoring_task is not None
    
    @pytest.mark.asyncio
    async def test_start_engine_already_running(self, execution_engine):
        """Test starting engine when already running."""
        execution_engine.is_running = True
        
        with patch.object(execution_engine, '_load_pending_orders', new_callable=AsyncMock):
            await execution_engine.start()
            
            # Should still be running, but shouldn't create new task
            assert execution_engine.is_running is True
    
    @pytest.mark.asyncio
    async def test_stop_engine(self, execution_engine):
        """Test stopping the engine."""
        # Start engine first
        with patch.object(execution_engine, '_load_pending_orders', new_callable=AsyncMock):
            await execution_engine.start()
            assert execution_engine.is_running is True
            
            # Stop engine
            await execution_engine.stop()
            
            assert execution_engine.is_running is False
    
    @pytest.mark.asyncio
    async def test_stop_engine_not_running(self, execution_engine):
        """Test stopping engine when not running."""
        # Should not raise exception
        await execution_engine.stop()
        
        assert execution_engine.is_running is False


class TestTriggerConditionChecking:
    """Test trigger condition checking logic."""
    
    @pytest.mark.asyncio
    async def test_check_trigger_conditions_no_symbols(self, execution_engine):
        """Test checking conditions when no symbols monitored."""
        await execution_engine._check_trigger_conditions()
        
        # Should complete without error
        assert execution_engine.orders_triggered == 0
    
    @pytest.mark.asyncio
    async def test_check_trigger_conditions_with_symbol_and_price(self, execution_engine):
        """Test checking conditions with specific symbol and price."""
        # Add a condition manually
        condition = TriggerCondition(
            order_id="test_order",
            symbol="AAPL",
            trigger_type="stop_loss",
            trigger_price=145.0,
            order_type=OrderType.SELL
        )
        execution_engine.trigger_conditions["AAPL"].append(condition)
        execution_engine.monitored_symbols.add("AAPL")
        
        with patch.object(execution_engine, '_process_triggered_order', new_callable=AsyncMock) as mock_process:
            # Check with triggering price
            await execution_engine._check_trigger_conditions("AAPL", 144.0)
            
            # Should trigger and process
            mock_process.assert_called_once()
            assert len(execution_engine.trigger_conditions["AAPL"]) == 0  # Removed after triggering
    
    @pytest.mark.asyncio
    async def test_check_trigger_conditions_no_trigger(self, execution_engine):
        """Test checking conditions when no trigger occurs."""
        # Add a condition manually
        condition = TriggerCondition(
            order_id="test_order",
            symbol="AAPL",
            trigger_type="stop_loss",
            trigger_price=145.0,
            order_type=OrderType.SELL
        )
        execution_engine.trigger_conditions["AAPL"].append(condition)
        execution_engine.monitored_symbols.add("AAPL")
        
        with patch.object(execution_engine, '_process_triggered_order', new_callable=AsyncMock) as mock_process:
            # Check with non-triggering price
            await execution_engine._check_trigger_conditions("AAPL", 150.0)
            
            # Should not trigger
            mock_process.assert_not_called()
            assert len(execution_engine.trigger_conditions["AAPL"]) == 1  # Still there
    
    @pytest.mark.asyncio
    async def test_check_trigger_conditions_market_data(self, execution_engine):
        """Test checking conditions using market data."""
        # Add a condition manually
        condition = TriggerCondition(
            order_id="test_order",
            symbol="AAPL",
            trigger_type="stop_loss",
            trigger_price=145.0,
            order_type=OrderType.SELL
        )
        execution_engine.trigger_conditions["AAPL"].append(condition)
        execution_engine.monitored_symbols.add("AAPL")
        
        # Mock the quote adapter
        mock_adapter = MockQuoteAdapter({"AAPL": 140.0})  # Triggering price
        
        with patch('app.services.order_execution_engine._get_quote_adapter', return_value=mock_adapter):
            with patch.object(execution_engine, '_process_triggered_order', new_callable=AsyncMock) as mock_process:
                await execution_engine._check_trigger_conditions()
                
                # Should trigger
                mock_process.assert_called_once()


class TestOrderProcessing:
    """Test order processing functionality."""
    
    @pytest.mark.asyncio
    async def test_process_triggered_order_stop_loss(self, execution_engine):
        """Test processing triggered stop loss order."""
        condition = TriggerCondition(
            order_id="stop_loss_123",
            symbol="AAPL",
            trigger_type="stop_loss",
            trigger_price=145.0,
            order_type=OrderType.SELL
        )
        
        # Mock order loading and conversion
        mock_order = Order(
            id="stop_loss_123",
            symbol="AAPL",
            order_type=OrderType.STOP_LOSS,
            quantity=-100,
            stop_price=145.0,
            condition=OrderCondition.MARKET,
            status=OrderStatus.PENDING
        )
        
        converted_order = Order(
            id="converted_123",
            symbol="AAPL",
            order_type=OrderType.SELL,
            quantity=-100,
            price=144.0,
            condition=OrderCondition.MARKET,
            status=OrderStatus.PENDING
        )
        
        with patch.object(execution_engine, '_load_order_by_id', return_value=mock_order):
            with patch('app.services.order_execution_engine.order_converter') as mock_converter:
                mock_converter.convert_stop_loss_to_market.return_value = converted_order
                
                with patch.object(execution_engine, '_update_order_triggered_status', new_callable=AsyncMock):
                    with patch.object(execution_engine, '_execute_converted_order', new_callable=AsyncMock):
                        await execution_engine._process_triggered_order(condition, 144.0)
                        
                        # Should increment triggered counter
                        assert execution_engine.orders_triggered == 1
    
    @pytest.mark.asyncio
    async def test_process_triggered_order_no_original(self, execution_engine):
        """Test processing triggered order when original order not found."""
        condition = TriggerCondition(
            order_id="missing_order",
            symbol="AAPL",
            trigger_type="stop_loss",
            trigger_price=145.0,
            order_type=OrderType.SELL
        )
        
        with patch.object(execution_engine, '_load_order_by_id', return_value=None):
            # Should handle gracefully
            await execution_engine._process_triggered_order(condition, 144.0)
            
            assert execution_engine.orders_triggered == 0
    
    @pytest.mark.asyncio
    async def test_process_triggered_order_exception(self, execution_engine):
        """Test processing triggered order with exception."""
        condition = TriggerCondition(
            order_id="error_order",
            symbol="AAPL",
            trigger_type="stop_loss",
            trigger_price=145.0,
            order_type=OrderType.SELL
        )
        
        with patch.object(execution_engine, '_load_order_by_id', side_effect=Exception("DB error")):
            # Should handle exception gracefully
            await execution_engine._process_triggered_order(condition, 144.0)
            
            assert execution_engine.orders_triggered == 0


class TestDatabaseOperations:
    """Test database operations."""
    
    @pytest.mark.asyncio
    async def test_load_order_by_id_success(self, execution_engine):
        """Test loading order by ID successfully."""
        mock_db_order = Mock()
        mock_db_order.id = "order123"
        mock_db_order.symbol = "AAPL"
        mock_db_order.order_type = OrderType.STOP_LOSS
        mock_db_order.quantity = -100
        mock_db_order.price = None
        mock_db_order.status = OrderStatus.PENDING
        mock_db_order.created_at = datetime.now()
        mock_db_order.stop_price = 145.0
        mock_db_order.trail_percent = None
        mock_db_order.trail_amount = None
        mock_db_order.condition = OrderCondition.MARKET
        mock_db_order.net_price = None
        mock_db_order.filled_at = None
        
        with patch('app.services.order_execution_engine.get_async_session') as mock_session:
            mock_db = AsyncMock()
            mock_result = Mock()
            mock_result.scalar_one_or_none.return_value = mock_db_order
            mock_db.execute.return_value = mock_result
            mock_session.return_value.__aenter__.return_value = mock_db
            
            order = await execution_engine._load_order_by_id("order123")
            
            assert order is not None
            assert order.id == "order123"
            assert order.symbol == "AAPL"
            assert order.order_type == OrderType.STOP_LOSS
    
    @pytest.mark.asyncio
    async def test_load_order_by_id_not_found(self, execution_engine):
        """Test loading order by ID when not found."""
        with patch('app.services.order_execution_engine.get_async_session') as mock_session:
            mock_db = AsyncMock()
            mock_result = Mock()
            mock_result.scalar_one_or_none.return_value = None
            mock_db.execute.return_value = mock_result
            mock_session.return_value.__aenter__.return_value = mock_db
            
            order = await execution_engine._load_order_by_id("nonexistent")
            
            assert order is None
    
    @pytest.mark.asyncio
    async def test_load_order_by_id_exception(self, execution_engine):
        """Test loading order by ID with exception."""
        with patch('app.services.order_execution_engine.get_async_session', side_effect=Exception("DB error")):
            order = await execution_engine._load_order_by_id("order123")
            
            assert order is None
    
    @pytest.mark.asyncio
    async def test_update_order_triggered_status(self, execution_engine):
        """Test updating order triggered status."""
        mock_db_order = Mock()
        mock_db_order.status = OrderStatus.PENDING
        
        with patch('app.services.order_execution_engine.get_async_session') as mock_session:
            mock_db = AsyncMock()
            mock_result = Mock()
            mock_result.scalar_one_or_none.return_value = mock_db_order
            mock_db.execute.return_value = mock_result
            mock_session.return_value.__aenter__.return_value = mock_db
            
            await execution_engine._update_order_triggered_status("order123", 144.0)
            
            assert mock_db_order.status == OrderStatus.FILLED
            assert mock_db_order.triggered_at is not None
            assert mock_db_order.filled_at is not None
            mock_db.commit.assert_called_once()
    
    @pytest.mark.asyncio
    async def test_load_pending_orders(self, execution_engine):
        """Test loading pending orders from database."""
        mock_db_order = Mock()
        mock_db_order.id = "order123"
        mock_db_order.symbol = "AAPL"
        mock_db_order.order_type = OrderType.STOP_LOSS
        mock_db_order.quantity = -100
        mock_db_order.price = None
        mock_db_order.status = OrderStatus.PENDING
        mock_db_order.created_at = datetime.now()
        mock_db_order.stop_price = 145.0
        mock_db_order.trail_percent = None
        mock_db_order.trail_amount = None
        mock_db_order.condition = OrderCondition.MARKET
        mock_db_order.net_price = None
        
        with patch('app.services.order_execution_engine.get_async_session') as mock_session:
            mock_db = AsyncMock()
            mock_result = Mock()
            mock_result.scalars.return_value.all.return_value = [mock_db_order]
            mock_db.execute.return_value = mock_result
            mock_session.return_value.__aenter__.return_value = mock_db
            
            with patch.object(execution_engine, 'add_order', new_callable=AsyncMock) as mock_add:
                await execution_engine._load_pending_orders()
                
                mock_add.assert_called_once()


class TestExecuteConvertedOrder:
    """Test executing converted orders."""
    
    @pytest.mark.asyncio
    async def test_execute_converted_order_success(self, execution_engine):
        """Test successful execution of converted order."""
        order = Order(
            id="converted_123",
            symbol="AAPL",
            order_type=OrderType.SELL,
            quantity=-100,
            price=144.0,
            condition=OrderCondition.MARKET,
            status=OrderStatus.PENDING
        )
        
        # Mock trading service with execute_order method
        execution_engine.trading_service.execute_order = AsyncMock()
        
        await execution_engine._execute_converted_order(order)
        
        execution_engine.trading_service.execute_order.assert_called_once_with(order)
    
    @pytest.mark.asyncio
    async def test_execute_converted_order_no_method(self, execution_engine):
        """Test executing converted order when trading service has no execute_order method."""
        order = Order(
            id="converted_123",
            symbol="AAPL",
            order_type=OrderType.SELL,
            quantity=-100,
            price=144.0,
            condition=OrderCondition.MARKET,
            status=OrderStatus.PENDING
        )
        
        # Trading service without execute_order method
        execution_engine.trading_service = Mock()
        
        # Should handle gracefully
        await execution_engine._execute_converted_order(order)
    
    @pytest.mark.asyncio
    async def test_execute_converted_order_exception(self, execution_engine):
        """Test executing converted order with exception."""
        order = Order(
            id="converted_123",
            symbol="AAPL",
            order_type=OrderType.SELL,
            quantity=-100,
            price=144.0,
            condition=OrderCondition.MARKET,
            status=OrderStatus.PENDING
        )
        
        execution_engine.trading_service.execute_order = AsyncMock(side_effect=Exception("Execution error"))
        
        with pytest.raises(Exception, match="Execution error"):
            await execution_engine._execute_converted_order(order)


class TestTriggerPriceCalculation:
    """Test trigger price calculation."""
    
    def test_get_initial_trigger_price_stop_loss(self, execution_engine):
        """Test getting initial trigger price for stop loss order."""
        order = Order(
            id="order123",
            symbol="AAPL",
            order_type=OrderType.STOP_LOSS,
            quantity=-100,
            stop_price=145.0,
            condition=OrderCondition.MARKET,
            status=OrderStatus.PENDING
        )
        
        trigger_price = execution_engine._get_initial_trigger_price(order)
        
        assert trigger_price == 145.0
    
    def test_get_initial_trigger_price_stop_limit(self, execution_engine):
        """Test getting initial trigger price for stop limit order."""
        order = Order(
            id="order123",
            symbol="AAPL",
            order_type=OrderType.STOP_LIMIT,
            quantity=-100,
            stop_price=147.0,
            condition=OrderCondition.LIMIT,
            status=OrderStatus.PENDING
        )
        
        trigger_price = execution_engine._get_initial_trigger_price(order)
        
        assert trigger_price == 147.0
    
    def test_get_initial_trigger_price_trailing_stop(self, execution_engine):
        """Test getting initial trigger price for trailing stop order."""
        order = Order(
            id="order123",
            symbol="AAPL",
            order_type=OrderType.TRAILING_STOP,
            quantity=-100,
            trail_percent=5.0,
            condition=OrderCondition.MARKET,
            status=OrderStatus.PENDING
        )
        
        trigger_price = execution_engine._get_initial_trigger_price(order)
        
        # Should return 0.0 for dynamic update later
        assert trigger_price == 0.0
    
    def test_get_initial_trigger_price_missing_stop_price(self, execution_engine):
        """Test getting initial trigger price when stop price missing."""
        order = Order(
            id="order123",
            symbol="AAPL",
            order_type=OrderType.STOP_LOSS,
            quantity=-100,
            stop_price=None,  # Missing
            condition=OrderCondition.MARKET,
            status=OrderStatus.PENDING
        )
        
        with pytest.raises(OrderExecutionError, match="Missing stop_price"):
            execution_engine._get_initial_trigger_price(order)
    
    def test_get_initial_trigger_price_unsupported_type(self, execution_engine):
        """Test getting initial trigger price for unsupported order type."""
        order = Order(
            id="order123",
            symbol="AAPL",
            order_type=OrderType.BUY,  # Not a trigger order type
            quantity=100,
            price=150.0,
            condition=OrderCondition.MARKET,
            status=OrderStatus.PENDING
        )
        
        with pytest.raises(OrderExecutionError, match="Unsupported order type"):
            execution_engine._get_initial_trigger_price(order)


class TestEngineStatus:
    """Test engine status and monitoring."""
    
    def test_get_status(self, execution_engine):
        """Test getting engine status."""
        # Add some conditions
        condition1 = TriggerCondition("order1", "AAPL", "stop_loss", 145.0, OrderType.SELL)
        condition2 = TriggerCondition("order2", "GOOGL", "stop_limit", 2800.0, OrderType.SELL)
        
        execution_engine.trigger_conditions["AAPL"].append(condition1)
        execution_engine.trigger_conditions["GOOGL"].append(condition2)
        execution_engine.monitored_symbols.update(["AAPL", "GOOGL"])
        execution_engine.orders_processed = 5
        execution_engine.orders_triggered = 2
        
        status = execution_engine.get_status()
        
        assert status["is_running"] is False
        assert status["monitored_symbols"] == 2
        assert status["total_trigger_conditions"] == 2
        assert status["orders_processed"] == 5
        assert status["orders_triggered"] == 2
        assert isinstance(status["last_market_data_update"], datetime)
        assert set(status["symbols"]) == {"AAPL", "GOOGL"}
    
    def test_get_monitored_orders(self, execution_engine):
        """Test getting monitored orders."""
        # Add some conditions
        condition1 = TriggerCondition("order1", "AAPL", "stop_loss", 145.0, OrderType.SELL)
        condition2 = TriggerCondition("order2", "AAPL", "trailing_stop", 150.0, OrderType.SELL)
        condition2.high_water_mark = 155.0
        
        execution_engine.trigger_conditions["AAPL"].extend([condition1, condition2])
        
        monitored = execution_engine.get_monitored_orders()
        
        assert "AAPL" in monitored
        assert len(monitored["AAPL"]) == 2
        
        order1_data = monitored["AAPL"][0]
        assert order1_data["order_id"] == "order1"
        assert order1_data["trigger_type"] == "stop_loss"
        assert order1_data["trigger_price"] == 145.0
        
        order2_data = monitored["AAPL"][1]
        assert order2_data["order_id"] == "order2"
        assert order2_data["trigger_type"] == "trailing_stop"
        assert order2_data["high_water_mark"] == 155.0


class TestGlobalFunctions:
    """Test global helper functions."""
    
    def test_initialize_execution_engine(self, mock_trading_service):
        """Test initializing global execution engine."""
        engine = initialize_execution_engine(mock_trading_service)
        
        assert isinstance(engine, OrderExecutionEngine)
        assert engine.trading_service is mock_trading_service
    
    def test_get_execution_engine_success(self, mock_trading_service):
        """Test getting global execution engine when initialized."""
        # Initialize first
        initialize_execution_engine(mock_trading_service)
        
        engine = get_execution_engine()
        
        assert isinstance(engine, OrderExecutionEngine)
        assert engine.trading_service is mock_trading_service
    
    def test_get_execution_engine_not_initialized(self):
        """Test getting global execution engine when not initialized."""
        # Clear global instance
        import app.services.order_execution_engine
        app.services.order_execution_engine.execution_engine = None
        
        with pytest.raises(RuntimeError, match="Order execution engine not initialized"):
            get_execution_engine()


class TestErrorHandling:
    """Test error handling scenarios."""
    
    @pytest.mark.asyncio
    async def test_monitoring_loop_exception(self, execution_engine):
        """Test monitoring loop with exception."""
        execution_engine.is_running = True
        
        # Mock check_trigger_conditions to raise exception
        with patch.object(execution_engine, '_check_trigger_conditions', side_effect=Exception("Monitor error")):
            # Should handle exception and continue (would sleep and retry)
            try:
                # Run one iteration
                await execution_engine._check_trigger_conditions()
            except Exception:
                # Exception should be caught in real monitoring loop
                pass
    
    @pytest.mark.asyncio
    async def test_quote_adapter_error(self, execution_engine):
        """Test handling quote adapter errors."""
        # Add a condition
        condition = TriggerCondition("order1", "AAPL", "stop_loss", 145.0, OrderType.SELL)
        execution_engine.trigger_conditions["AAPL"].append(condition)
        execution_engine.monitored_symbols.add("AAPL")
        
        # Mock quote adapter to raise exception
        mock_adapter = Mock()
        mock_adapter.get_quote = AsyncMock(side_effect=Exception("Quote error"))
        
        with patch('app.services.order_execution_engine._get_quote_adapter', return_value=mock_adapter):
            # Should handle exception gracefully
            await execution_engine._check_trigger_conditions()
            
            # Condition should still be there (not processed due to error)
            assert len(execution_engine.trigger_conditions["AAPL"]) == 1
    
    @pytest.mark.asyncio
    async def test_asset_factory_error(self, execution_engine):
        """Test handling asset factory errors."""
        # Add a condition with invalid symbol
        condition = TriggerCondition("order1", "INVALID_SYMBOL", "stop_loss", 145.0, OrderType.SELL)
        execution_engine.trigger_conditions["INVALID_SYMBOL"].append(condition)
        execution_engine.monitored_symbols.add("INVALID_SYMBOL")
        
        with patch('app.services.order_execution_engine.asset_factory', return_value=None):
            # Should handle gracefully
            await execution_engine._check_trigger_conditions()
            
            assert execution_engine.orders_triggered == 0


class TestIntegrationScenarios:
    """Test complex integration scenarios."""
    
    @pytest.mark.asyncio
    async def test_multiple_orders_same_symbol(self, execution_engine):
        """Test multiple orders for the same symbol."""
        # Create multiple orders for AAPL
        order1 = Order(
            id="stop_loss_1",
            symbol="AAPL",
            order_type=OrderType.STOP_LOSS,
            quantity=-100,
            stop_price=145.0,
            condition=OrderCondition.MARKET,
            status=OrderStatus.PENDING
        )
        
        order2 = Order(
            id="stop_loss_2",
            symbol="AAPL",
            order_type=OrderType.STOP_LOSS,
            quantity=-50,
            stop_price=140.0,
            condition=OrderCondition.MARKET,
            status=OrderStatus.PENDING
        )
        
        with patch('app.services.order_execution_engine.order_converter') as mock_converter:
            mock_converter.can_convert_order.return_value = True
            mock_converter.validate_order_for_conversion.return_value = True
            
            await execution_engine.add_order(order1)
            await execution_engine.add_order(order2)
            
            assert len(execution_engine.trigger_conditions["AAPL"]) == 2
            assert "AAPL" in execution_engine.monitored_symbols
    
    @pytest.mark.asyncio
    async def test_mixed_order_types(self, execution_engine):
        """Test different order types together."""
        # Create different types of orders
        stop_loss_order = Order(
            id="stop_loss_1",
            symbol="AAPL",
            order_type=OrderType.STOP_LOSS,
            quantity=-100,
            stop_price=145.0,
            condition=OrderCondition.MARKET,
            status=OrderStatus.PENDING
        )
        
        trailing_stop_order = Order(
            id="trailing_stop_1",
            symbol="GOOGL",
            order_type=OrderType.TRAILING_STOP,
            quantity=-50,
            trail_percent=5.0,
            condition=OrderCondition.MARKET,
            status=OrderStatus.PENDING
        )
        
        with patch('app.services.order_execution_engine.order_converter') as mock_converter:
            mock_converter.can_convert_order.return_value = True
            mock_converter.validate_order_for_conversion.return_value = True
            
            await execution_engine.add_order(stop_loss_order)
            await execution_engine.add_order(trailing_stop_order)
            
            assert len(execution_engine.monitored_symbols) == 2
            assert "AAPL" in execution_engine.monitored_symbols
            assert "GOOGL" in execution_engine.monitored_symbols
    
    @pytest.mark.asyncio
    async def test_high_frequency_price_updates(self, execution_engine):
        """Test handling high frequency price updates."""
        # Add condition
        condition = TriggerCondition("order1", "AAPL", "stop_loss", 145.0, OrderType.SELL)
        execution_engine.trigger_conditions["AAPL"].append(condition)
        execution_engine.monitored_symbols.add("AAPL")
        
        # Simulate rapid price updates
        prices = [150.0, 148.0, 146.0, 144.0]  # Last one triggers
        
        trigger_count = 0
        
        async def mock_process_triggered_order(condition, price):
            nonlocal trigger_count
            trigger_count += 1
        
        with patch.object(execution_engine, '_process_triggered_order', side_effect=mock_process_triggered_order):
            for price in prices:
                await execution_engine._check_trigger_conditions("AAPL", price)
        
        # Should only trigger once when price hits 144.0
        assert trigger_count == 1


class TestPerformanceScenarios:
    """Test performance with large numbers of orders."""
    
    @pytest.mark.asyncio
    async def test_many_monitored_symbols(self, execution_engine):
        """Test monitoring many symbols."""
        # Add conditions for many symbols
        for i in range(100):
            symbol = f"STOCK{i}"
            condition = TriggerCondition(f"order{i}", symbol, "stop_loss", 100.0 + i, OrderType.SELL)
            execution_engine.trigger_conditions[symbol].append(condition)
            execution_engine.monitored_symbols.add(symbol)
        
        # Should handle large number of symbols
        status = execution_engine.get_status()
        assert status["monitored_symbols"] == 100
        assert status["total_trigger_conditions"] == 100
    
    @pytest.mark.asyncio
    async def test_many_conditions_per_symbol(self, execution_engine):
        """Test many conditions for single symbol."""
        # Add many conditions for AAPL
        for i in range(50):
            condition = TriggerCondition(f"order{i}", "AAPL", "stop_loss", 100.0 + i, OrderType.SELL)
            execution_engine.trigger_conditions["AAPL"].append(condition)
        
        execution_engine.monitored_symbols.add("AAPL")
        
        # Check status
        status = execution_engine.get_status()
        assert status["total_trigger_conditions"] == 50
        
        monitored = execution_engine.get_monitored_orders()
        assert len(monitored["AAPL"]) == 50