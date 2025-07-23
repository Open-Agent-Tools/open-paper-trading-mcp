"""Comprehensive tests for order_execution.py - Order execution engine."""

import pytest
from datetime import datetime
from unittest.mock import AsyncMock, Mock, patch
from decimal import Decimal

from app.services.order_execution import (
    OrderExecutionEngine,
    OrderExecutionResult,
    OrderExecutionError,
    QuoteServiceProtocol,
)
from app.schemas.orders import (
    Order, 
    OrderLeg, 
    MultiLegOrder, 
    OrderType, 
    OrderCondition,
)
from app.schemas.positions import Position
from app.models.assets import Stock, Call, Put, Option
from app.models.quotes import Quote
from app.services.estimators import MidpointEstimator, PriceEstimator
from app.services.validation import AccountValidator


class MockQuoteService:
    """Mock quote service for testing."""
    
    def __init__(self, quotes: dict[str, Quote] = None):
        self.quotes = quotes or {}
        
    async def get_quote(self, asset) -> Quote:
        """Return mock quote for asset."""
        symbol = asset.symbol if hasattr(asset, 'symbol') else str(asset)
        if symbol in self.quotes:
            return self.quotes[symbol]
            
        # Default quote
        return Quote(
            asset=asset,
            quote_date=datetime.now(),
            price=100.0,
            bid=99.5,
            ask=100.5,
            bid_size=100,
            ask_size=100,
            volume=1000
        )


class MockPriceEstimator(PriceEstimator):
    """Mock price estimator for testing."""
    
    def __init__(self, price_multiplier: float = 1.0):
        self.price_multiplier = price_multiplier
        
    def estimate(self, quote: Quote, quantity: int) -> float:
        """Return estimated price."""
        if quote.price is None:
            return 100.0 * self.price_multiplier
        return quote.price * self.price_multiplier


@pytest.fixture
def execution_engine():
    """Create order execution engine for testing."""
    return OrderExecutionEngine()


@pytest.fixture
def mock_quote_service():
    """Create mock quote service."""
    return MockQuoteService()


@pytest.fixture
def sample_positions():
    """Create sample positions for testing."""
    return [
        Position(symbol="AAPL", quantity=100, avg_price=145.0, current_price=150.0),
        Position(symbol="AAPL__230120C00140000", quantity=2, avg_price=12.0, current_price=10.0),
        Position(symbol="GOOGL", quantity=-50, avg_price=2800.0, current_price=2750.0),
    ]


@pytest.fixture
def sample_stock():
    """Create sample stock asset."""
    return Stock("AAPL")


@pytest.fixture
def sample_call_option():
    """Create sample call option asset."""
    return Call(
        underlying=Stock("AAPL"),
        strike=150.0,
        expiration_date=datetime(2023, 6, 16).date()
    )


@pytest.fixture
def sample_put_option():
    """Create sample put option asset."""
    return Put(
        underlying=Stock("AAPL"),
        strike=140.0,
        expiration_date=datetime(2023, 6, 16).date()
    )


class TestOrderExecutionResult:
    """Test OrderExecutionResult class."""
    
    def test_execution_result_initialization(self):
        """Test OrderExecutionResult initialization."""
        result = OrderExecutionResult(success=True, message="Order executed")
        
        assert result.success is True
        assert result.message == "Order executed"
        assert result.order_id is None
        assert result.cash_change == 0.0
        assert result.positions_created == []
        assert result.positions_modified == []
        assert isinstance(result.executed_at, datetime)
    
    def test_execution_result_with_data(self):
        """Test OrderExecutionResult with detailed data."""
        position = Position(symbol="AAPL", quantity=100, avg_price=150.0, current_price=152.0)
        
        result = OrderExecutionResult(
            success=True,
            message="Order filled",
            order_id="order123",
            cash_change=-15000.0,
            positions_created=[position],
            positions_modified=[]
        )
        
        assert result.success is True
        assert result.order_id == "order123"
        assert result.cash_change == -15000.0
        assert len(result.positions_created) == 1
        assert result.positions_created[0].symbol == "AAPL"
    
    def test_execution_result_failure(self):
        """Test OrderExecutionResult for failed execution."""
        result = OrderExecutionResult(
            success=False,
            message="Insufficient funds",
            order_id="order123"
        )
        
        assert result.success is False
        assert result.message == "Insufficient funds"
        assert result.cash_change == 0.0
        assert result.positions_created == []


class TestOrderExecutionEngineInitialization:
    """Test OrderExecutionEngine initialization."""
    
    def test_engine_initialization_default(self):
        """Test engine initialization with defaults."""
        engine = OrderExecutionEngine()
        
        assert isinstance(engine.validator, AccountValidator)
        assert isinstance(engine.default_estimator, MidpointEstimator)
        assert engine.quote_service is None
    
    def test_engine_initialization_with_validator(self):
        """Test engine initialization with custom validator."""
        custom_validator = AccountValidator()
        engine = OrderExecutionEngine(validator=custom_validator)
        
        assert engine.validator is custom_validator
    
    def test_engine_with_quote_service(self, execution_engine, mock_quote_service):
        """Test engine with quote service."""
        execution_engine.quote_service = mock_quote_service
        
        assert execution_engine.quote_service is mock_quote_service


class TestOrderValidation:
    """Test order validation functionality."""
    
    def test_validate_order_success(self, execution_engine, sample_stock):
        """Test successful order validation."""
        order = MultiLegOrder(
            id="order123",
            legs=[
                OrderLeg(
                    asset=sample_stock,
                    quantity=100,
                    order_type=OrderType.BTO,
                    price=150.0
                )
            ],
            condition=OrderCondition.MARKET
        )
        
        # Should not raise exception
        execution_engine._validate_order(order)
    
    def test_validate_order_no_legs(self, execution_engine):
        """Test order validation with no legs."""
        order = MultiLegOrder(
            id="order123",
            legs=[],
            condition=OrderCondition.MARKET
        )
        
        with pytest.raises(OrderExecutionError, match="Order must have at least one leg"):
            execution_engine._validate_order(order)
    
    def test_validate_order_duplicate_assets(self, execution_engine, sample_stock):
        """Test order validation with duplicate assets."""
        order = MultiLegOrder(
            id="order123",
            legs=[
                OrderLeg(asset=sample_stock, quantity=100, order_type=OrderType.BTO, price=150.0),
                OrderLeg(asset=sample_stock, quantity=-50, order_type=OrderType.STO, price=150.0),
            ],
            condition=OrderCondition.MARKET
        )
        
        with pytest.raises(OrderExecutionError, match="Duplicate assets not allowed"):
            execution_engine._validate_order(order)


class TestLegPriceCalculation:
    """Test leg price calculation functionality."""
    
    @pytest.mark.asyncio
    async def test_calculate_leg_prices_with_quote_service(self, execution_engine, sample_stock):
        """Test calculating leg prices with quote service."""
        # Setup quote service
        quote = Quote(
            asset=sample_stock,
            quote_date=datetime.now(),
            price=150.0,
            bid=149.5,
            ask=150.5,
            bid_size=100,
            ask_size=100,
            volume=1000
        )
        execution_engine.quote_service = MockQuoteService({"AAPL": quote})
        
        leg = OrderLeg(
            asset=sample_stock,
            quantity=100,
            order_type=OrderType.BTO,
            price=150.0
        )
        
        estimator = MidpointEstimator()
        prices = await execution_engine._calculate_leg_prices([leg], estimator)
        
        assert leg in prices
        # MidpointEstimator should return midpoint of bid/ask for positive quantity
        expected_price = (149.5 + 150.5) / 2  # 150.0
        assert prices[leg] == expected_price
    
    @pytest.mark.asyncio
    async def test_calculate_leg_prices_without_quote_service(self, execution_engine, sample_stock):
        """Test calculating leg prices without quote service (fallback mode)."""
        leg = OrderLeg(
            asset=sample_stock,
            quantity=100,
            order_type=OrderType.BTO,
            price=145.0
        )
        
        estimator = MockPriceEstimator()
        prices = await execution_engine._calculate_leg_prices([leg], estimator)
        
        assert leg in prices
        # Should use fallback quote with price 100.0
        assert prices[leg] == 100.0
    
    @pytest.mark.asyncio
    async def test_calculate_leg_prices_negative_quantity(self, execution_engine, sample_stock):
        """Test calculating leg prices with negative quantity."""
        quote = Quote(
            asset=sample_stock,
            quote_date=datetime.now(),
            price=150.0,
            bid=149.5,
            ask=150.5,
            bid_size=100,
            ask_size=100,
            volume=1000
        )
        execution_engine.quote_service = MockQuoteService({"AAPL": quote})
        
        leg = OrderLeg(
            asset=sample_stock,
            quantity=-100,  # Sell order
            order_type=OrderType.STO,
            price=150.0
        )
        
        estimator = MidpointEstimator()
        prices = await execution_engine._calculate_leg_prices([leg], estimator)
        
        # For negative quantity, price should be negative
        expected_price = -((149.5 + 150.5) / 2)  # -150.0
        assert prices[leg] == expected_price


class TestOrderFillConditions:
    """Test order fill condition checking."""
    
    def test_should_fill_order_market(self, execution_engine):
        """Test market order should always fill."""
        order = MultiLegOrder(
            id="order123",
            legs=[],
            condition=OrderCondition.MARKET
        )
        
        assert execution_engine._should_fill_order(order, 150.0) is True
        assert execution_engine._should_fill_order(order, 200.0) is True
    
    def test_should_fill_order_limit_fill(self, execution_engine):
        """Test limit order that should fill."""
        order = MultiLegOrder(
            id="order123",
            legs=[],
            condition=OrderCondition.LIMIT,
            limit_price=155.0
        )
        
        # Market price 150.0 <= limit price 155.0, should fill
        assert execution_engine._should_fill_order(order, 150.0) is True
    
    def test_should_fill_order_limit_no_fill(self, execution_engine):
        """Test limit order that should not fill."""
        order = MultiLegOrder(
            id="order123",
            legs=[],
            condition=OrderCondition.LIMIT,
            limit_price=145.0
        )
        
        # Market price 150.0 > limit price 145.0, should not fill
        assert execution_engine._should_fill_order(order, 150.0) is False
    
    def test_should_fill_order_limit_no_price(self, execution_engine):
        """Test limit order without limit price."""
        order = MultiLegOrder(
            id="order123",
            legs=[],
            condition=OrderCondition.LIMIT,
            limit_price=None
        )
        
        # Should default to fill when no limit price specified
        assert execution_engine._should_fill_order(order, 150.0) is True


class TestClosingPositionValidation:
    """Test validation of closing positions."""
    
    def test_validate_closing_positions_success(self, execution_engine, sample_stock, sample_positions):
        """Test successful closing position validation."""
        # Trying to close 50 shares of 100 share position
        leg = OrderLeg(
            asset=sample_stock,
            quantity=-50,  # Selling 50 shares
            order_type=OrderType.STC,
            price=150.0
        )
        
        # Should not raise exception
        execution_engine._validate_closing_positions([leg], sample_positions)
    
    def test_validate_closing_positions_no_position(self, execution_engine, sample_positions):
        """Test closing position validation when no position exists."""
        # Trying to close position that doesn't exist
        non_existent_stock = Stock("TSLA")
        leg = OrderLeg(
            asset=non_existent_stock,
            quantity=-50,
            order_type=OrderType.STC,
            price=800.0
        )
        
        with pytest.raises(OrderExecutionError, match="No available positions to close"):
            execution_engine._validate_closing_positions([leg], sample_positions)
    
    def test_validate_closing_positions_insufficient_quantity(self, execution_engine, sample_stock, sample_positions):
        """Test closing position validation with insufficient quantity."""
        # Trying to close more shares than available
        leg = OrderLeg(
            asset=sample_stock,
            quantity=-200,  # Trying to sell 200 shares, only have 100
            order_type=OrderType.STC,
            price=150.0
        )
        
        with pytest.raises(OrderExecutionError, match="Insufficient position quantity"):
            execution_engine._validate_closing_positions([leg], sample_positions)
    
    def test_validate_closing_positions_wrong_direction(self, execution_engine, sample_stock, sample_positions):
        """Test closing position validation with wrong direction."""
        # Trying to cover short position with positive quantity
        leg = OrderLeg(
            asset=Stock("GOOGL"),  # GOOGL has -50 shares (short)
            quantity=25,  # Should be positive to cover short
            order_type=OrderType.BTC,
            price=2750.0
        )
        
        # Should not raise exception as signs are correct for covering short
        execution_engine._validate_closing_positions([leg], sample_positions)


class TestCashRequirementCalculation:
    """Test cash requirement calculation."""
    
    def test_calculate_cash_requirement_buy_stock(self, execution_engine, sample_stock):
        """Test cash requirement for buying stock."""
        leg = OrderLeg(
            asset=sample_stock,
            quantity=100,
            order_type=OrderType.BTO,
            price=150.0
        )
        
        leg_prices = {leg: 150.0}
        cash_requirement = execution_engine._calculate_cash_requirement([leg], leg_prices)
        
        # Buying 100 shares at $150 = -$15,000 (negative = cash out)
        assert cash_requirement == -15000.0
    
    def test_calculate_cash_requirement_sell_stock(self, execution_engine, sample_stock):
        """Test cash requirement for selling stock."""
        leg = OrderLeg(
            asset=sample_stock,
            quantity=-100,
            order_type=OrderType.STO,
            price=150.0
        )
        
        leg_prices = {leg: -150.0}  # Negative price for sell
        cash_requirement = execution_engine._calculate_cash_requirement([leg], leg_prices)
        
        # Selling 100 shares at $150 = +$15,000 (positive = cash in)
        assert cash_requirement == 15000.0
    
    def test_calculate_cash_requirement_buy_option(self, execution_engine, sample_call_option):
        """Test cash requirement for buying option."""
        leg = OrderLeg(
            asset=sample_call_option,
            quantity=2,
            order_type=OrderType.BTO,
            price=10.0
        )
        
        leg_prices = {leg: 10.0}
        cash_requirement = execution_engine._calculate_cash_requirement([leg], leg_prices)
        
        # Buying 2 contracts at $10 = -$2,000 (negative = cash out)
        # Options have 100 multiplier
        assert cash_requirement == -2000.0
    
    def test_calculate_cash_requirement_sell_option(self, execution_engine, sample_put_option):
        """Test cash requirement for selling option."""
        leg = OrderLeg(
            asset=sample_put_option,
            quantity=-1,
            order_type=OrderType.STO,
            price=8.0
        )
        
        leg_prices = {leg: -8.0}  # Negative price for sell
        cash_requirement = execution_engine._calculate_cash_requirement([leg], leg_prices)
        
        # Selling 1 contract at $8 = +$800 (positive = cash in)
        assert cash_requirement == 800.0
    
    def test_calculate_cash_requirement_invalid_buy_signs(self, execution_engine, sample_stock):
        """Test cash requirement calculation with invalid buy order signs."""
        leg = OrderLeg(
            asset=sample_stock,
            quantity=-100,  # Negative quantity for buy order (invalid)
            order_type=OrderType.BTO,
            price=150.0
        )
        
        leg_prices = {leg: 150.0}
        
        with pytest.raises(OrderExecutionError, match="Buy orders must have positive quantity"):
            execution_engine._calculate_cash_requirement([leg], leg_prices)
    
    def test_calculate_cash_requirement_invalid_sell_signs(self, execution_engine, sample_stock):
        """Test cash requirement calculation with invalid sell order signs."""
        leg = OrderLeg(
            asset=sample_stock,
            quantity=100,  # Positive quantity for sell order (invalid)
            order_type=OrderType.STO,
            price=150.0
        )
        
        leg_prices = {leg: 150.0}
        
        with pytest.raises(OrderExecutionError, match="Sell orders must have negative quantity"):
            execution_engine._calculate_cash_requirement([leg], leg_prices)


class TestOpenPosition:
    """Test opening new positions."""
    
    @pytest.mark.asyncio
    async def test_open_position_stock(self, execution_engine, sample_stock):
        """Test opening stock position."""
        leg = OrderLeg(
            asset=sample_stock,
            quantity=100,
            order_type=OrderType.BTO,
            price=150.0
        )
        
        position = await execution_engine._open_position(leg, 150.0)
        
        assert position.symbol == "AAPL"
        assert position.quantity == 100
        assert position.avg_price == 150.0
        assert position.asset == sample_stock
        assert position.current_price == 150.0  # No quote service, uses cost basis
    
    @pytest.mark.asyncio
    async def test_open_position_option(self, execution_engine, sample_call_option):
        """Test opening option position."""
        leg = OrderLeg(
            asset=sample_call_option,
            quantity=2,
            order_type=OrderType.BTO,
            price=12.0
        )
        
        position = await execution_engine._open_position(leg, 12.0)
        
        assert position.symbol == sample_call_option.symbol
        assert position.quantity == 2
        assert position.avg_price == 12.0
        assert position.option_type == "call"
        assert position.strike == 150.0
        assert position.expiration_date == sample_call_option.expiration_date
        assert position.underlying_symbol == "AAPL"
    
    @pytest.mark.asyncio
    async def test_open_position_with_quote_service(self, execution_engine, sample_stock):
        """Test opening position with quote service."""
        quote = Quote(
            asset=sample_stock,
            quote_date=datetime.now(),
            price=152.0,
            bid=151.5,
            ask=152.5,
            bid_size=100,
            ask_size=100,
            volume=1000
        )
        execution_engine.quote_service = MockQuoteService({"AAPL": quote})
        
        leg = OrderLeg(
            asset=sample_stock,
            quantity=100,
            order_type=OrderType.BTO,
            price=150.0
        )
        
        position = await execution_engine._open_position(leg, 150.0)
        
        assert position.current_price == 152.0  # From quote service
        assert position.avg_price == 150.0  # Cost basis
    
    @pytest.mark.asyncio
    async def test_open_position_short(self, execution_engine, sample_stock):
        """Test opening short position."""
        leg = OrderLeg(
            asset=sample_stock,
            quantity=-100,
            order_type=OrderType.STO,
            price=150.0
        )
        
        position = await execution_engine._open_position(leg, -150.0)
        
        assert position.quantity == -100
        assert position.avg_price == 150.0  # Always positive for cost basis


class TestClosePosition:
    """Test closing existing positions."""
    
    def test_close_position_partial(self, execution_engine, sample_stock, sample_positions):
        """Test partially closing position."""
        leg = OrderLeg(
            asset=sample_stock,
            quantity=-50,  # Selling 50 of 100 shares
            order_type=OrderType.STC,
            price=155.0
        )
        
        modified_positions = execution_engine._close_position(leg, sample_positions, -155.0)
        
        assert len(modified_positions) == 1
        modified_position = modified_positions[0]
        
        # Should have 50 shares remaining
        assert modified_position.quantity == 50
        assert modified_position.symbol == "AAPL"
        
        # Should calculate realized P&L
        # (155.0 - 145.0) * 50 * 1 = $500 profit
        assert modified_position.realized_pnl == 500.0
    
    def test_close_position_complete(self, execution_engine, sample_stock, sample_positions):
        """Test completely closing position."""
        leg = OrderLeg(
            asset=sample_stock,
            quantity=-100,  # Selling all 100 shares
            order_type=OrderType.STC,
            price=155.0
        )
        
        modified_positions = execution_engine._close_position(leg, sample_positions, -155.0)
        
        assert len(modified_positions) == 1
        modified_position = modified_positions[0]
        
        # Should have 0 shares remaining
        assert modified_position.quantity == 0
        
        # Should calculate realized P&L for full position
        # (155.0 - 145.0) * 100 * 1 = $1000 profit
        assert modified_position.realized_pnl == 1000.0
    
    def test_close_position_short_cover(self, execution_engine, sample_positions):
        """Test covering short position."""
        googl_stock = Stock("GOOGL")
        leg = OrderLeg(
            asset=googl_stock,
            quantity=25,  # Covering 25 of -50 short shares
            order_type=OrderType.BTC,
            price=2750.0
        )
        
        modified_positions = execution_engine._close_position(leg, sample_positions, 2750.0)
        
        assert len(modified_positions) == 1
        modified_position = modified_positions[0]
        
        # Should have -25 shares remaining
        assert modified_position.quantity == -25
        assert modified_position.symbol == "GOOGL"
        
        # Should calculate realized P&L for short position
        # Short position: profit when cover price < avg price
        # (2800.0 - 2750.0) * 25 * 1 = $1250 profit
        assert modified_position.realized_pnl == 1250.0
    
    def test_close_position_option(self, execution_engine, sample_positions):
        """Test closing option position."""
        call_option = Call(
            underlying=Stock("AAPL"),
            strike=140.0,
            expiration_date=datetime(2023, 1, 20).date()
        )
        
        leg = OrderLeg(
            asset=call_option,
            quantity=-1,  # Selling 1 of 2 long contracts
            order_type=OrderType.STC,
            price=15.0
        )
        
        modified_positions = execution_engine._close_position(leg, sample_positions, -15.0)
        
        assert len(modified_positions) == 1
        modified_position = modified_positions[0]
        
        # Should have 1 contract remaining
        assert modified_position.quantity == 1
        
        # Should calculate realized P&L with option multiplier
        # (15.0 - 12.0) * 1 * 100 = $300 profit
        assert modified_position.realized_pnl == 300.0


class TestMultiLegOrderExecution:
    """Test multi-leg order execution."""
    
    @pytest.mark.asyncio
    async def test_execute_order_success(self, execution_engine, sample_stock):
        """Test successful multi-leg order execution."""
        order = MultiLegOrder(
            id="order123",
            legs=[
                OrderLeg(
                    asset=sample_stock,
                    quantity=100,
                    order_type=OrderType.BTO,
                    price=150.0
                )
            ],
            condition=OrderCondition.MARKET
        )
        
        result = await execution_engine.execute_order(
            account_id="account123",
            order=order,
            current_cash=20000.0,
            current_positions=[],
            estimator=MockPriceEstimator()
        )
        
        assert result.success is True
        assert result.order_id == "order123"
        assert result.cash_change == -15000.0  # Buying $15k worth of stock
        assert len(result.positions_created) == 1
        assert result.positions_created[0].symbol == "AAPL"
    
    @pytest.mark.asyncio
    async def test_execute_order_insufficient_cash(self, execution_engine, sample_stock):
        """Test order execution with insufficient cash."""
        order = MultiLegOrder(
            id="order123",
            legs=[
                OrderLeg(
                    asset=sample_stock,
                    quantity=1000,  # Expensive order
                    order_type=OrderType.BTO,
                    price=150.0
                )
            ],
            condition=OrderCondition.MARKET
        )
        
        result = await execution_engine.execute_order(
            account_id="account123",
            order=order,
            current_cash=10000.0,  # Not enough cash
            current_positions=[],
            estimator=MockPriceEstimator()
        )
        
        assert result.success is False
        assert "Insufficient cash" in result.message
        assert result.cash_change == 0.0
    
    @pytest.mark.asyncio
    async def test_execute_order_limit_not_met(self, execution_engine, sample_stock):
        """Test order execution with limit price not met."""
        order = MultiLegOrder(
            id="order123",
            legs=[
                OrderLeg(
                    asset=sample_stock,
                    quantity=100,
                    order_type=OrderType.BTO,
                    price=145.0
                )
            ],
            condition=OrderCondition.LIMIT,
            limit_price=145.0  # Market price will be 100.0, limit is 145.0
        )
        
        # Market price from MockPriceEstimator will be 100.0
        # Total order price = 100.0 * 100 = 10000.0
        # Limit price = 145.0, so 145.0 < 10000.0, order shouldn't fill
        result = await execution_engine.execute_order(
            account_id="account123",
            order=order,
            current_cash=20000.0,
            current_positions=[],
            estimator=MockPriceEstimator()
        )
        
        assert result.success is False
        assert "Order condition not met" in result.message
    
    @pytest.mark.asyncio
    async def test_execute_order_closing_position(self, execution_engine, sample_stock, sample_positions):
        """Test executing order that closes existing position."""
        order = MultiLegOrder(
            id="order123",
            legs=[
                OrderLeg(
                    asset=sample_stock,
                    quantity=-50,  # Selling 50 shares
                    order_type=OrderType.STC,
                    price=155.0
                )
            ],
            condition=OrderCondition.MARKET
        )
        
        result = await execution_engine.execute_order(
            account_id="account123",
            order=order,
            current_cash=10000.0,
            current_positions=sample_positions,
            estimator=MockPriceEstimator()
        )
        
        assert result.success is True
        assert result.cash_change == 5000.0  # Selling for $5k
        assert len(result.positions_modified) == 1
        assert result.positions_modified[0].quantity == 50  # 50 shares remaining
    
    @pytest.mark.asyncio
    async def test_execute_order_exception_handling(self, execution_engine, sample_stock):
        """Test order execution exception handling."""
        # Create order with invalid data that will cause exception
        order = MultiLegOrder(
            id="order123",
            legs=[
                OrderLeg(
                    asset=sample_stock,
                    quantity=100,
                    order_type=OrderType.BTO,
                    price=150.0
                )
            ],
            condition=OrderCondition.MARKET
        )
        
        # Mock the estimator to raise an exception
        error_estimator = Mock()
        error_estimator.estimate.side_effect = Exception("Estimator error")
        
        with patch.object(execution_engine, '_calculate_leg_prices', side_effect=Exception("Test error")):
            result = await execution_engine.execute_order(
                account_id="account123",
                order=order,
                current_cash=20000.0,
                current_positions=[],
                estimator=error_estimator
            )
        
        assert result.success is False
        assert "Order execution failed" in result.message


class TestSimpleOrderExecution:
    """Test simple order execution."""
    
    @pytest.mark.asyncio
    async def test_execute_simple_order(self, execution_engine, sample_stock):
        """Test executing simple single-leg order."""
        order = Order(
            id="order123",
            symbol="AAPL",
            order_type=OrderType.BUY,
            quantity=100,
            price=150.0,
            condition=OrderCondition.MARKET
        )
        
        result = await execution_engine.execute_simple_order(
            account_id="account123",
            order=order,
            current_cash=20000.0,
            current_positions=[],
            estimator=MockPriceEstimator()
        )
        
        assert result.success is True
        assert result.order_id == "order123"
        assert result.cash_change == -15000.0


class TestErrorHandling:
    """Test error handling scenarios."""
    
    @pytest.mark.asyncio
    async def test_execution_with_invalid_asset(self, execution_engine):
        """Test execution with invalid asset."""
        # Create invalid asset that might cause issues
        invalid_asset = Mock()
        invalid_asset.symbol = "INVALID"
        
        order = MultiLegOrder(
            id="order123",
            legs=[
                OrderLeg(
                    asset=invalid_asset,
                    quantity=100,
                    order_type=OrderType.BTO,
                    price=150.0
                )
            ],
            condition=OrderCondition.MARKET
        )
        
        # Should handle gracefully
        result = await execution_engine.execute_order(
            account_id="account123",
            order=order,
            current_cash=20000.0,
            current_positions=[],
            estimator=MockPriceEstimator()
        )
        
        # Exact result depends on implementation, but should not crash
        assert isinstance(result, OrderExecutionResult)
    
    def test_cash_requirement_zero_quantity(self, execution_engine, sample_stock):
        """Test cash requirement calculation with zero quantity."""
        leg = OrderLeg(
            asset=sample_stock,
            quantity=0,
            order_type=OrderType.BTO,
            price=150.0
        )
        
        leg_prices = {leg: 150.0}
        cash_requirement = execution_engine._calculate_cash_requirement([leg], leg_prices)
        
        assert cash_requirement == 0.0
    
    def test_close_position_no_matching_positions(self, execution_engine, sample_positions):
        """Test closing position when no matching positions exist."""
        tsla_stock = Stock("TSLA")
        leg = OrderLeg(
            asset=tsla_stock,
            quantity=-100,
            order_type=OrderType.STC,
            price=800.0
        )
        
        # Should return empty list when no matching positions
        modified_positions = execution_engine._close_position(leg, sample_positions, -800.0)
        
        assert len(modified_positions) == 0


class TestIntegrationScenarios:
    """Test complex integration scenarios."""
    
    @pytest.mark.asyncio
    async def test_covered_call_strategy(self, execution_engine):
        """Test executing covered call strategy."""
        # Own stock, sell call
        stock = Stock("AAPL")
        call = Call(
            underlying=stock,
            strike=155.0,
            expiration_date=datetime(2023, 6, 16).date()
        )
        
        # Start with long stock position
        existing_positions = [
            Position(symbol="AAPL", quantity=100, avg_price=145.0, current_price=150.0)
        ]
        
        # Sell covered call
        order = MultiLegOrder(
            id="order123",
            legs=[
                OrderLeg(
                    asset=call,
                    quantity=-1,  # Sell 1 call
                    order_type=OrderType.STO,
                    price=5.0
                )
            ],
            condition=OrderCondition.MARKET
        )
        
        result = await execution_engine.execute_order(
            account_id="account123",
            order=order,
            current_cash=5000.0,
            current_positions=existing_positions,
            estimator=MockPriceEstimator()
        )
        
        assert result.success is True
        assert result.cash_change == 500.0  # Received premium from selling call
        assert len(result.positions_created) == 1
        assert result.positions_created[0].quantity == -1  # Short call position
    
    @pytest.mark.asyncio
    async def test_protective_put_strategy(self, execution_engine):
        """Test executing protective put strategy."""
        # Own stock, buy put
        stock = Stock("AAPL")
        put = Put(
            underlying=stock,
            strike=140.0,
            expiration_date=datetime(2023, 6, 16).date()
        )
        
        # Start with long stock position
        existing_positions = [
            Position(symbol="AAPL", quantity=100, avg_price=145.0, current_price=150.0)
        ]
        
        # Buy protective put
        order = MultiLegOrder(
            id="order123",
            legs=[
                OrderLeg(
                    asset=put,
                    quantity=1,  # Buy 1 put
                    order_type=OrderType.BTO,
                    price=3.0
                )
            ],
            condition=OrderCondition.MARKET
        )
        
        result = await execution_engine.execute_order(
            account_id="account123",
            order=order,
            current_cash=5000.0,
            current_positions=existing_positions,
            estimator=MockPriceEstimator()
        )
        
        assert result.success is True
        assert result.cash_change == -300.0  # Paid premium for put
        assert len(result.positions_created) == 1
        assert result.positions_created[0].quantity == 1  # Long put position
    
    @pytest.mark.asyncio
    async def test_spread_strategy(self, execution_engine):
        """Test executing spread strategy."""
        # Bull call spread: buy lower strike, sell higher strike
        stock = Stock("AAPL")
        call_lower = Call(
            underlying=stock,
            strike=145.0,
            expiration_date=datetime(2023, 6, 16).date()
        )
        call_higher = Call(
            underlying=stock,
            strike=155.0,
            expiration_date=datetime(2023, 6, 16).date()
        )
        
        order = MultiLegOrder(
            id="order123",
            legs=[
                OrderLeg(
                    asset=call_lower,
                    quantity=1,  # Buy lower strike call
                    order_type=OrderType.BTO,
                    price=8.0
                ),
                OrderLeg(
                    asset=call_higher,
                    quantity=-1,  # Sell higher strike call
                    order_type=OrderType.STO,
                    price=3.0
                )
            ],
            condition=OrderCondition.MARKET
        )
        
        result = await execution_engine.execute_order(
            account_id="account123",
            order=order,
            current_cash=10000.0,
            current_positions=[],
            estimator=MockPriceEstimator()
        )
        
        assert result.success is True
        # Net debit: paid $800 for long call, received $300 for short call = -$500
        assert result.cash_change == -500.0
        assert len(result.positions_created) == 2


class TestPerformanceScenarios:
    """Test performance with large orders."""
    
    @pytest.mark.asyncio
    async def test_large_multi_leg_order(self, execution_engine):
        """Test execution of large multi-leg order."""
        # Create order with many legs
        legs = []
        for i in range(10):
            stock = Stock(f"STOCK{i}")
            leg = OrderLeg(
                asset=stock,
                quantity=100,
                order_type=OrderType.BTO,
                price=100.0 + i
            )
            legs.append(leg)
        
        order = MultiLegOrder(
            id="order123",
            legs=legs,
            condition=OrderCondition.MARKET
        )
        
        result = await execution_engine.execute_order(
            account_id="account123",
            order=order,
            current_cash=1000000.0,  # Lots of cash
            current_positions=[],
            estimator=MockPriceEstimator()
        )
        
        assert result.success is True
        assert len(result.positions_created) == 10
        # Each stock costs $100 * 100 = $10,000, total = $100,000
        assert result.cash_change == -100000.0
    
    @pytest.mark.asyncio
    async def test_execution_with_many_existing_positions(self, execution_engine, sample_stock):
        """Test execution with many existing positions."""
        # Create many existing positions
        existing_positions = []
        for i in range(100):
            position = Position(
                symbol=f"STOCK{i}",
                quantity=100,
                avg_price=100.0 + i,
                current_price=105.0 + i
            )
            existing_positions.append(position)
        
        # Add AAPL position to close
        existing_positions.append(
            Position(symbol="AAPL", quantity=100, avg_price=145.0, current_price=150.0)
        )
        
        order = MultiLegOrder(
            id="order123",
            legs=[
                OrderLeg(
                    asset=sample_stock,
                    quantity=-100,
                    order_type=OrderType.STC,
                    price=155.0
                )
            ],
            condition=OrderCondition.MARKET
        )
        
        result = await execution_engine.execute_order(
            account_id="account123",
            order=order,
            current_cash=10000.0,
            current_positions=existing_positions,
            estimator=MockPriceEstimator()
        )
        
        assert result.success is True
        assert len(result.positions_modified) == 1
        assert result.positions_modified[0].symbol == "AAPL"