"""
Advanced test coverage for Validation service.

This module provides comprehensive testing of the validation service,
focusing on business validation rules, account validation, order validation,
multi-leg order validation, and risk-based validation logic.
"""

import asyncio
from datetime import date, datetime, timedelta
from decimal import Decimal
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
import pytest_asyncio

from app.models.assets import Stock, Option, asset_factory
from app.schemas.orders import (
    Order, OrderCreate, OrderType, OrderLeg, MultiLegOrder,
    OrderCondition, OrderStatus, OrderTimeInForce
)
from app.schemas.positions import Position, Portfolio
from app.services.validation import (
    AccountValidator,
    OrderValidator,
    MultiLegOrderValidator,
    PositionValidator,
    ValidationError,
    ValidationResult,
    ValidationRule,
    BusinessRuleValidator
)


@pytest.fixture
def account_validator():
    """Create AccountValidator instance for testing."""
    return AccountValidator()


@pytest.fixture
def order_validator():
    """Create OrderValidator instance for testing."""
    return OrderValidator()


@pytest.fixture
def multileg_validator():
    """Create MultiLegOrderValidator instance for testing."""
    return MultiLegOrderValidator()


@pytest.fixture
def position_validator():
    """Create PositionValidator instance for testing."""
    return PositionValidator()


@pytest.fixture
def business_rule_validator():
    """Create BusinessRuleValidator instance for testing."""
    return BusinessRuleValidator()


@pytest.fixture
def sample_portfolio():
    """Create sample portfolio for testing."""
    positions = [
        Position(
            symbol="AAPL",
            quantity=100,
            average_cost=150.0,
            current_price=155.0,
            market_value=15500.0,
            unrealized_pnl=500.0,
            unrealized_pnl_percent=3.33
        ),
        Position(
            symbol="GOOGL",
            quantity=50,
            average_cost=2500.0,
            current_price=2600.0,
            market_value=130000.0,
            unrealized_pnl=5000.0,
            unrealized_pnl_percent=4.0
        )
    ]
    
    return Portfolio(
        cash_balance=25000.0,
        total_value=170500.0,
        positions=positions,
        unrealized_pnl=5500.0,
        unrealized_pnl_percent=3.33
    )


class TestAccountValidator:
    """Test AccountValidator functionality."""
    
    def test_validate_account_state_positive_cash(self, account_validator, sample_portfolio):
        """Test account validation with positive cash balance."""
        result = account_validator.validate_account_state(
            cash_balance=25000.0,
            positions=sample_portfolio.positions
        )
        
        assert result is True  # Should pass validation
    
    def test_validate_account_state_negative_cash(self, account_validator, sample_portfolio):
        """Test account validation with negative cash balance."""
        with pytest.raises(ValidationError, match="Insufficient cash"):
            account_validator.validate_account_state(
                cash_balance=-1000.0,
                positions=sample_portfolio.positions
            )
    
    def test_validate_account_state_zero_cash(self, account_validator, sample_portfolio):
        """Test account validation with zero cash balance."""
        result = account_validator.validate_account_state(
            cash_balance=0.0,
            positions=sample_portfolio.positions
        )
        
        assert result is True  # Zero cash is valid
    
    def test_validate_account_leverage(self, account_validator, sample_portfolio):
        """Test account leverage validation."""
        # High leverage scenario
        high_leverage_positions = [
            Position(
                symbol="TSLA",
                quantity=1000,  # Large position
                average_cost=800.0,
                current_price=750.0,
                market_value=750000.0,  # $750k position
                unrealized_pnl=-50000.0,
                unrealized_pnl_percent=-6.25
            )
        ]
        
        with pytest.raises(ValidationError, match="leverage|margin"):
            account_validator.validate_account_leverage(
                cash_balance=50000.0,  # Only $50k cash
                positions=high_leverage_positions,
                max_leverage_ratio=4.0
            )
    
    def test_validate_buying_power(self, account_validator):
        """Test buying power validation."""
        # Test insufficient buying power
        with pytest.raises(ValidationError, match="Insufficient buying power"):
            account_validator.validate_buying_power(
                required_amount=50000.0,
                available_buying_power=30000.0
            )
        
        # Test sufficient buying power
        result = account_validator.validate_buying_power(
            required_amount=20000.0,
            available_buying_power=30000.0
        )
        assert result is True
    
    def test_validate_day_trading_limits(self, account_validator):
        """Test day trading limit validation."""
        # Test PDT rule violation
        with pytest.raises(ValidationError, match="Pattern Day Trader"):
            account_validator.validate_day_trading_limits(
                account_value=20000.0,  # Under $25k PDT limit
                day_trades_count=4,  # Over 3 day trades
                trading_period_days=5
            )
        
        # Test valid day trading
        result = account_validator.validate_day_trading_limits(
            account_value=30000.0,  # Above PDT limit
            day_trades_count=10,
            trading_period_days=5
        )
        assert result is True
    
    def test_validate_account_restrictions(self, account_validator):
        """Test account restriction validation."""
        # Test restricted account
        with pytest.raises(ValidationError, match="Account is restricted"):
            account_validator.validate_account_restrictions(
                is_restricted=True,
                restriction_reason="Good faith violation"
            )
        
        # Test unrestricted account
        result = account_validator.validate_account_restrictions(
            is_restricted=False,
            restriction_reason=None
        )
        assert result is True


class TestOrderValidator:
    """Test OrderValidator functionality."""
    
    def test_validate_basic_order_valid(self, order_validator):
        """Test validation of valid basic order."""
        order = OrderCreate(
            symbol="AAPL",
            quantity=100,
            order_type=OrderType.MARKET,
            side="buy",
            time_in_force=OrderTimeInForce.DAY
        )
        
        result = order_validator.validate_order(order)
        assert isinstance(result, ValidationResult)
        assert result.is_valid is True
        assert len(result.errors) == 0
    
    def test_validate_order_invalid_symbol(self, order_validator):
        """Test validation with invalid symbol."""
        order = OrderCreate(
            symbol="",  # Empty symbol
            quantity=100,
            order_type=OrderType.MARKET,
            side="buy"
        )
        
        result = order_validator.validate_order(order)
        assert result.is_valid is False
        assert any("symbol" in error.lower() for error in result.errors)
    
    def test_validate_order_invalid_quantity(self, order_validator):
        """Test validation with invalid quantity."""
        # Zero quantity
        order_zero = OrderCreate(
            symbol="AAPL",
            quantity=0,
            order_type=OrderType.MARKET,
            side="buy"
        )
        
        result = order_validator.validate_order(order_zero)
        assert result.is_valid is False
        assert any("quantity" in error.lower() for error in result.errors)
        
        # Negative quantity
        order_negative = OrderCreate(
            symbol="AAPL",
            quantity=-10,
            order_type=OrderType.MARKET,
            side="buy"
        )
        
        result = order_validator.validate_order(order_negative)
        assert result.is_valid is False
        assert any("quantity" in error.lower() for error in result.errors)
    
    def test_validate_limit_order_missing_price(self, order_validator):
        """Test limit order validation without limit price."""
        order = OrderCreate(
            symbol="AAPL",
            quantity=100,
            order_type=OrderType.LIMIT,
            side="buy"
            # Missing limit_price
        )
        
        result = order_validator.validate_order(order)
        assert result.is_valid is False
        assert any("limit price" in error.lower() for error in result.errors)
    
    def test_validate_stop_order_missing_price(self, order_validator):
        """Test stop order validation without stop price."""
        order = OrderCreate(
            symbol="AAPL",
            quantity=100,
            order_type=OrderType.STOP,
            side="sell"
            # Missing stop_price
        )
        
        result = order_validator.validate_order(order)
        assert result.is_valid is False
        assert any("stop price" in error.lower() for error in result.errors)
    
    def test_validate_order_price_ranges(self, order_validator):
        """Test order price range validation."""
        # Limit price too far from market (collar validation)
        with patch.object(order_validator, '_get_current_price') as mock_price:
            mock_price.return_value = 100.0
            
            # Limit buy order with price too high
            order_high = OrderCreate(
                symbol="AAPL",
                quantity=10,
                order_type=OrderType.LIMIT,
                side="buy",
                limit_price=150.0  # 50% above market
            )
            
            result = order_validator.validate_order(order_high, enable_price_collar=True)
            assert result.is_valid is False
            assert any("price collar" in error.lower() or "far from market" in error.lower() 
                      for error in result.errors)
    
    def test_validate_order_market_hours(self, order_validator):
        """Test market hours validation."""
        order = OrderCreate(
            symbol="AAPL",
            quantity=100,
            order_type=OrderType.MARKET,
            side="buy",
            time_in_force=OrderTimeInForce.DAY
        )
        
        # Mock market closed
        with patch.object(order_validator, '_is_market_open') as mock_market_open:
            mock_market_open.return_value = False
            
            result = order_validator.validate_order(order, check_market_hours=True)
            
            # Market orders during closed hours should be invalid
            if order.order_type == OrderType.MARKET:
                assert result.is_valid is False
                assert any("market hours" in error.lower() for error in result.errors)
    
    def test_validate_fractional_shares(self, order_validator):
        """Test fractional share validation."""
        # Fractional quantity for stock that doesn't support it
        order_fractional = OrderCreate(
            symbol="AAPL",
            quantity=10.5,  # Fractional shares
            order_type=OrderType.MARKET,
            side="buy"
        )
        
        with patch.object(order_validator, '_supports_fractional_shares') as mock_fractional:
            mock_fractional.return_value = False
            
            result = order_validator.validate_order(order_fractional)
            assert result.is_valid is False
            assert any("fractional" in error.lower() for error in result.errors)


class TestMultiLegOrderValidator:
    """Test MultiLegOrderValidator functionality."""
    
    def test_validate_spread_order_valid(self, multileg_validator):
        """Test validation of valid spread order."""
        legs = [
            OrderLeg(
                symbol="AAPL240119C00155000",  # Long call
                quantity=1,
                side="buy",
                order_type=OrderType.LIMIT,
                limit_price=5.0
            ),
            OrderLeg(
                symbol="AAPL240119C00160000",  # Short call  
                quantity=1,
                side="sell",
                order_type=OrderType.LIMIT,
                limit_price=3.0
            )
        ]
        
        multileg_order = MultiLegOrder(
            strategy_type="call_spread",
            legs=legs,
            net_debit=2.0
        )
        
        result = multileg_validator.validate_multileg_order(multileg_order)
        assert result.is_valid is True
        assert len(result.errors) == 0
    
    def test_validate_spread_legs_mismatch(self, multileg_validator):
        """Test validation with mismatched spread legs."""
        legs = [
            OrderLeg(
                symbol="AAPL240119C00155000",
                quantity=1,
                side="buy",
                order_type=OrderType.LIMIT,
                limit_price=5.0
            ),
            OrderLeg(
                symbol="GOOGL240119C00160000",  # Different underlying
                quantity=1,
                side="sell",
                order_type=OrderType.LIMIT,
                limit_price=3.0
            )
        ]
        
        multileg_order = MultiLegOrder(
            strategy_type="call_spread",
            legs=legs
        )
        
        result = multileg_validator.validate_multileg_order(multileg_order)
        assert result.is_valid is False
        assert any("underlying" in error.lower() or "mismatch" in error.lower() 
                  for error in result.errors)
    
    def test_validate_iron_condor(self, multileg_validator):
        """Test iron condor validation."""
        legs = [
            OrderLeg(symbol="AAPL240119P00145000", quantity=1, side="buy", limit_price=1.0),   # Long put
            OrderLeg(symbol="AAPL240119P00150000", quantity=1, side="sell", limit_price=2.0),  # Short put
            OrderLeg(symbol="AAPL240119C00160000", quantity=1, side="sell", limit_price=3.0),  # Short call
            OrderLeg(symbol="AAPL240119C00165000", quantity=1, side="buy", limit_price=1.5)   # Long call
        ]
        
        iron_condor = MultiLegOrder(
            strategy_type="iron_condor",
            legs=legs,
            net_credit=0.5
        )
        
        result = multileg_validator.validate_multileg_order(iron_condor)
        assert result.is_valid is True
    
    def test_validate_unbalanced_strategy(self, multileg_validator):
        """Test validation of unbalanced multi-leg strategy."""
        legs = [
            OrderLeg(
                symbol="AAPL240119C00155000",
                quantity=2,  # Unbalanced quantity
                side="buy",
                limit_price=5.0
            ),
            OrderLeg(
                symbol="AAPL240119C00160000",
                quantity=1,  # Different quantity
                side="sell",
                limit_price=3.0
            )
        ]
        
        multileg_order = MultiLegOrder(
            strategy_type="call_spread",
            legs=legs
        )
        
        result = multileg_validator.validate_multileg_order(multileg_order)
        assert result.is_valid is False
        assert any("balanced" in error.lower() or "ratio" in error.lower() 
                  for error in result.errors)
    
    def test_validate_strategy_profit_loss(self, multileg_validator):
        """Test strategy profit/loss validation."""
        legs = [
            OrderLeg(symbol="AAPL240119C00155000", quantity=1, side="buy", limit_price=10.0),  # Expensive
            OrderLeg(symbol="AAPL240119C00160000", quantity=1, side="sell", limit_price=2.0)   # Cheap
        ]
        
        # This would result in guaranteed loss (paying 8.0 net debit for 5.0 max profit)
        multileg_order = MultiLegOrder(
            strategy_type="call_spread",
            legs=legs,
            net_debit=8.0
        )
        
        result = multileg_validator.validate_multileg_order(
            multileg_order, 
            check_economics=True
        )
        assert result.is_valid is False
        assert any("profit" in error.lower() or "loss" in error.lower() or "economic" in error.lower()
                  for error in result.errors)


class TestPositionValidator:
    """Test PositionValidator functionality."""
    
    def test_validate_position_size_limits(self, position_validator, sample_portfolio):
        """Test position size limit validation."""
        # Test position within limits
        new_position = Position(
            symbol="MSFT",
            quantity=50,
            average_cost=300.0,
            current_price=310.0,
            market_value=15500.0
        )
        
        result = position_validator.validate_position_size(
            new_position,
            sample_portfolio,
            max_position_percent=0.20  # 20% max
        )
        assert result.is_valid is True
        
        # Test position exceeding limits
        large_position = Position(
            symbol="NVDA",
            quantity=200,
            average_cost=800.0,
            current_price=850.0,
            market_value=170000.0  # Would be 50% of portfolio
        )
        
        result = position_validator.validate_position_size(
            large_position,
            sample_portfolio,
            max_position_percent=0.20
        )
        assert result.is_valid is False
        assert any("concentration" in error.lower() or "limit" in error.lower() 
                  for error in result.errors)
    
    def test_validate_sector_concentration(self, position_validator, sample_portfolio):
        """Test sector concentration validation."""
        with patch.object(position_validator, '_get_sector_info') as mock_sector:
            # Mock all positions as tech sector
            mock_sector.return_value = "Technology"
            
            # Add another tech position
            tech_position = Position(
                symbol="MSFT",
                quantity=100,
                average_cost=300.0,
                current_price=320.0,
                market_value=32000.0
            )
            
            result = position_validator.validate_sector_concentration(
                tech_position,
                sample_portfolio,
                max_sector_percent=0.60  # 60% sector limit
            )
            
            # Should fail as tech would be over 60%
            assert result.is_valid is False
            assert any("sector" in error.lower() for error in result.errors)
    
    def test_validate_correlation_risk(self, position_validator, sample_portfolio):
        """Test correlation risk validation."""
        with patch.object(position_validator, '_get_correlation') as mock_correlation:
            mock_correlation.return_value = 0.85  # High correlation
            
            correlated_position = Position(
                symbol="MSFT",  # Highly correlated with AAPL
                quantity=50,
                average_cost=300.0,
                current_price=320.0,
                market_value=16000.0
            )
            
            result = position_validator.validate_correlation_risk(
                correlated_position,
                sample_portfolio,
                max_correlation=0.80
            )
            
            assert result.is_valid is False
            assert any("correlation" in error.lower() for error in result.errors)
    
    def test_validate_options_position_risk(self, position_validator):
        """Test options position risk validation."""
        # High-risk naked option position
        naked_put_position = Position(
            symbol="TSLA240119P00700000",  # Naked put
            quantity=-10,  # Short position
            average_cost=-5.0,  # Credit received
            current_price=8.0,  # Now more expensive
            market_value=-8000.0,
            unrealized_pnl=-3000.0
        )
        
        portfolio_with_options = Portfolio(
            cash_balance=50000.0,
            total_value=42000.0,  # Lost money on options
            positions=[naked_put_position],
            unrealized_pnl=-3000.0
        )
        
        result = position_validator.validate_options_risk(
            naked_put_position,
            portfolio_with_options,
            max_naked_exposure=0.20  # 20% max naked exposure
        )
        
        # Should fail due to high naked option exposure
        assert result.is_valid is False
        assert any("naked" in error.lower() or "option" in error.lower() 
                  for error in result.errors)


class TestBusinessRuleValidator:
    """Test BusinessRuleValidator functionality."""
    
    def test_validate_margin_requirements(self, business_rule_validator):
        """Test margin requirement validation."""
        order = OrderCreate(
            symbol="AAPL",
            quantity=1000,  # Large order
            order_type=OrderType.MARKET,
            side="buy"
        )
        
        # Mock insufficient margin
        result = business_rule_validator.validate_margin_requirements(
            order,
            available_margin=50000.0,
            margin_rate=0.25  # 25% margin requirement
        )
        
        # Order value would be ~$155k, requiring ~$39k margin
        # Should pass with $50k available margin
        assert result.is_valid is True
        
        # Test insufficient margin
        result = business_rule_validator.validate_margin_requirements(
            order,
            available_margin=20000.0,  # Insufficient
            margin_rate=0.25
        )
        
        assert result.is_valid is False
        assert any("margin" in error.lower() for error in result.errors)
    
    def test_validate_options_approval_level(self, business_rule_validator):
        """Test options approval level validation."""
        # Level 1 account trying level 3 strategy
        spread_order = MultiLegOrder(
            strategy_type="iron_condor",
            legs=[
                OrderLeg(symbol="AAPL240119P00145000", quantity=1, side="buy"),
                OrderLeg(symbol="AAPL240119P00150000", quantity=1, side="sell"),
                OrderLeg(symbol="AAPL240119C00160000", quantity=1, side="sell"),
                OrderLeg(symbol="AAPL240119C00165000", quantity=1, side="buy")
            ]
        )
        
        result = business_rule_validator.validate_options_level(
            spread_order,
            account_options_level=1,  # Basic level
            required_level=3  # Advanced spreads require level 3
        )
        
        assert result.is_valid is False
        assert any("options level" in error.lower() or "approval" in error.lower() 
                  for error in result.errors)
    
    def test_validate_wash_sale_rules(self, business_rule_validator):
        """Test wash sale rule validation."""
        # Mock recent sale of AAPL at loss
        with patch.object(business_rule_validator, '_get_recent_transactions') as mock_transactions:
            mock_transactions.return_value = [
                {
                    "symbol": "AAPL",
                    "quantity": -100,  # Sold 100 shares
                    "price": 140.0,
                    "cost_basis": 160.0,  # $20 loss per share
                    "date": datetime.now() - timedelta(days=15)  # 15 days ago
                }
            ]
            
            # New buy order for AAPL within 30 days
            buy_order = OrderCreate(
                symbol="AAPL",
                quantity=50,
                order_type=OrderType.MARKET,
                side="buy"
            )
            
            result = business_rule_validator.validate_wash_sale_rules(buy_order)
            
            assert result.is_valid is False
            assert any("wash sale" in error.lower() for error in result.errors)
    
    def test_validate_good_faith_violations(self, business_rule_validator):
        """Test good faith violation validation."""
        # Mock unsettled funds scenario
        buy_order = OrderCreate(
            symbol="AAPL",
            quantity=100,
            order_type=OrderType.MARKET,
            side="buy"
        )
        
        result = business_rule_validator.validate_good_faith_violation(
            buy_order,
            settled_cash=10000.0,
            unsettled_funds=15000.0,  # Recent sale proceeds not settled
            order_value=15500.0  # Order exceeds settled cash
        )
        
        # Should warn about potential good faith violation
        assert result.is_valid is False
        assert any("good faith" in error.lower() or "unsettled" in error.lower() 
                  for error in result.errors)
    
    def test_validate_free_riding_rules(self, business_rule_validator):
        """Test free riding rule validation."""
        # Mock scenario: buying then selling before settlement
        with patch.object(business_rule_validator, '_get_pending_settlements') as mock_settlements:
            mock_settlements.return_value = [
                {
                    "symbol": "GOOGL",
                    "quantity": 10,
                    "settlement_date": datetime.now() + timedelta(days=2),
                    "proceeds": 26000.0
                }
            ]
            
            # Sell order that would use unsettled funds
            sell_order = OrderCreate(
                symbol="GOOGL",
                quantity=10,
                order_type=OrderType.MARKET,
                side="sell"
            )
            
            result = business_rule_validator.validate_free_riding_rules(
                sell_order,
                cash_balance=5000.0  # Low cash, would rely on unsettled funds
            )
            
            assert result.is_valid is False
            assert any("free riding" in error.lower() or "settlement" in error.lower() 
                      for error in result.errors)


class TestAsyncValidation:
    """Test async validation operations."""
    
    @pytest_asyncio.async_test
    async def test_async_order_validation(self, order_validator):
        """Test async order validation with external data."""
        order = OrderCreate(
            symbol="AAPL",
            quantity=100,
            order_type=OrderType.LIMIT,
            side="buy",
            limit_price=150.0
        )
        
        # Mock async market data lookup
        with patch.object(order_validator, '_get_market_data_async') as mock_market_data:
            mock_market_data.return_value = {
                "current_price": 155.0,
                "bid": 154.5,
                "ask": 155.5,
                "volume": 1000000,
                "market_open": True
            }
            
            result = await order_validator.validate_order_async(
                order, 
                check_market_data=True
            )
            
            assert result.is_valid is True
            mock_market_data.assert_called_once_with("AAPL")
    
    @pytest_asyncio.async_test
    async def test_async_portfolio_validation(self, account_validator, sample_portfolio):
        """Test async portfolio validation."""
        # Mock async risk calculations
        with patch.object(account_validator, '_calculate_risk_metrics_async') as mock_risk:
            mock_risk.return_value = {
                "portfolio_beta": 1.2,
                "var_95": 15000.0,
                "max_drawdown": 0.08,
                "sharpe_ratio": 1.5
            }
            
            result = await account_validator.validate_portfolio_async(
                sample_portfolio,
                include_risk_analysis=True
            )
            
            assert result.is_valid is True
            mock_risk.assert_called_once()
    
    @pytest_asyncio.async_test
    async def test_concurrent_validation(self, order_validator):
        """Test concurrent validation of multiple orders."""
        orders = [
            OrderCreate(symbol=f"STOCK{i}", quantity=10, order_type=OrderType.MARKET, side="buy")
            for i in range(5)
        ]
        
        # Validate all orders concurrently
        validation_tasks = [
            order_validator.validate_order_async(order)
            for order in orders
        ]
        
        results = await asyncio.gather(*validation_tasks)
        
        assert len(results) == 5
        assert all(isinstance(result, ValidationResult) for result in results)
    
    @pytest_asyncio.async_test
    async def test_validation_timeout_handling(self, order_validator):
        """Test validation timeout handling."""
        order = OrderCreate(
            symbol="AAPL",
            quantity=100,
            order_type=OrderType.MARKET,
            side="buy"
        )
        
        # Mock slow external service
        with patch.object(order_validator, '_get_market_data_async') as mock_market_data:
            mock_market_data.side_effect = asyncio.TimeoutError("Market data timeout")
            
            result = await order_validator.validate_order_async(
                order, 
                check_market_data=True,
                timeout_seconds=1.0
            )
            
            # Should fallback to basic validation
            assert result.is_valid is True
            assert any("timeout" in warning.lower() for warning in result.warnings)


class TestValidationRuleEngine:
    """Test validation rule engine and custom rules."""
    
    def test_custom_validation_rule(self, business_rule_validator):
        """Test custom validation rule implementation."""
        def custom_large_order_rule(order: OrderCreate) -> ValidationResult:
            """Custom rule: Flag orders over $100k value."""
            estimated_value = order.quantity * 150.0  # Assume $150 per share
            
            if estimated_value > 100000:
                return ValidationResult(
                    is_valid=False,
                    errors=[f"Order value ${estimated_value:,.0f} exceeds $100k limit"],
                    warnings=[]
                )
            return ValidationResult(is_valid=True, errors=[], warnings=[])
        
        # Register custom rule
        business_rule_validator.add_custom_rule("large_order_check", custom_large_order_rule)
        
        # Test with large order
        large_order = OrderCreate(
            symbol="AAPL",
            quantity=1000,  # $150k value
            order_type=OrderType.MARKET,
            side="buy"
        )
        
        result = business_rule_validator.validate_with_custom_rules(large_order)
        assert result.is_valid is False
        assert any("100k limit" in error for error in result.errors)
    
    def test_conditional_validation_rules(self, business_rule_validator):
        """Test conditional validation rules."""
        def vip_account_rule(order: OrderCreate, account_type: str) -> ValidationResult:
            """VIP accounts get different limits."""
            if account_type == "VIP":
                return ValidationResult(is_valid=True, errors=[], warnings=[])
            
            # Regular accounts have stricter limits
            if order.quantity > 500:
                return ValidationResult(
                    is_valid=False,
                    errors=["Regular accounts limited to 500 shares per order"],
                    warnings=[]
                )
            
            return ValidationResult(is_valid=True, errors=[], warnings=[])
        
        large_order = OrderCreate(
            symbol="AAPL",
            quantity=1000,
            order_type=OrderType.MARKET,
            side="buy"
        )
        
        # Test with regular account
        result_regular = vip_account_rule(large_order, "REGULAR")
        assert result_regular.is_valid is False
        
        # Test with VIP account
        result_vip = vip_account_rule(large_order, "VIP")
        assert result_vip.is_valid is True
    
    def test_rule_priority_and_ordering(self, business_rule_validator):
        """Test validation rule priority and execution order."""
        validation_order = []
        
        def high_priority_rule(order: OrderCreate) -> ValidationResult:
            validation_order.append("high_priority")
            return ValidationResult(is_valid=True, errors=[], warnings=[])
        
        def low_priority_rule(order: OrderCreate) -> ValidationResult:
            validation_order.append("low_priority")
            return ValidationResult(is_valid=True, errors=[], warnings=[])
        
        def medium_priority_rule(order: OrderCreate) -> ValidationResult:
            validation_order.append("medium_priority")
            return ValidationResult(is_valid=True, errors=[], warnings=[])
        
        # Add rules with different priorities
        business_rule_validator.add_custom_rule("high", high_priority_rule, priority=1)
        business_rule_validator.add_custom_rule("low", low_priority_rule, priority=3)
        business_rule_validator.add_custom_rule("medium", medium_priority_rule, priority=2)
        
        order = OrderCreate(
            symbol="AAPL",
            quantity=100,
            order_type=OrderType.MARKET,
            side="buy"
        )
        
        business_rule_validator.validate_with_custom_rules(order)
        
        # Should execute in priority order (1, 2, 3)
        assert validation_order == ["high_priority", "medium_priority", "low_priority"]


class TestValidationPerformance:
    """Test validation performance and optimization."""
    
    @pytest_asyncio.async_test
    async def test_validation_performance_benchmark(self, order_validator):
        """Test validation performance under load."""
        orders = [
            OrderCreate(
                symbol=f"STOCK{i % 10}",
                quantity=10 + (i % 100),
                order_type=OrderType.MARKET,
                side="buy" if i % 2 == 0 else "sell"
            )
            for i in range(1000)
        ]
        
        start_time = asyncio.get_event_loop().time()
        
        # Validate orders in batches
        batch_size = 100
        results = []
        
        for i in range(0, len(orders), batch_size):
            batch = orders[i:i + batch_size]
            batch_results = await asyncio.gather(*[
                order_validator.validate_order_async(order)
                for order in batch
            ])
            results.extend(batch_results)
        
        end_time = asyncio.get_event_loop().time()
        execution_time = end_time - start_time
        
        assert len(results) == 1000
        assert all(isinstance(result, ValidationResult) for result in results)
        
        # Should process 1000 validations within reasonable time
        assert execution_time < 5.0  # 5 seconds max
        
        # Calculate throughput
        throughput = len(orders) / execution_time
        assert throughput > 200  # At least 200 validations per second
    
    @pytest_asyncio.async_test
    async def test_validation_caching(self, order_validator):
        """Test validation result caching for performance."""
        order = OrderCreate(
            symbol="AAPL",
            quantity=100,
            order_type=OrderType.MARKET,
            side="buy"
        )
        
        # First validation
        start_time1 = asyncio.get_event_loop().time()
        result1 = await order_validator.validate_order_async(order, enable_caching=True)
        end_time1 = asyncio.get_event_loop().time()
        
        # Second validation (should use cache)
        start_time2 = asyncio.get_event_loop().time()
        result2 = await order_validator.validate_order_async(order, enable_caching=True)
        end_time2 = asyncio.get_event_loop().time()
        
        time1 = end_time1 - start_time1
        time2 = end_time2 - start_time2
        
        # Results should be identical
        assert result1.is_valid == result2.is_valid
        assert result1.errors == result2.errors
        
        # Second call should be faster (cached)
        assert time2 <= time1  # Allow for some variance
    
    def test_validation_memory_usage(self, business_rule_validator):
        """Test memory usage during intensive validation."""
        import gc
        import sys
        
        # Get baseline memory
        gc.collect()
        baseline_objects = len(gc.get_objects())
        
        # Perform many validations
        orders = [
            OrderCreate(
                symbol=f"STOCK{i}",
                quantity=i + 1,
                order_type=OrderType.MARKET,
                side="buy"
            )
            for i in range(1000)
        ]
        
        results = []
        for order in orders:
            result = business_rule_validator.validate_order_basic(order)
            results.append(result)
        
        # Check memory usage
        gc.collect()
        final_objects = len(gc.get_objects())
        
        # Memory usage should not grow excessively
        object_growth = final_objects - baseline_objects
        assert object_growth < len(orders) * 10  # Allow reasonable object growth