"""
Comprehensive tests for AccountValidator - business rule validation service.

Tests cover:
- Account state validation and balance checks
- Order pre-execution validation
- Position limit enforcement
- Order structure validation
- Multi-leg order validation
- Options-specific trading rules
- Closing position validation
- Error handling and edge cases
"""

from datetime import date, timedelta
from unittest.mock import patch

import pytest

from app.models.assets import Call, Put, Stock
from app.schemas.orders import MultiLegOrder, OrderLeg, OrderType
from app.schemas.positions import Position
from app.services.validation import AccountValidator, ValidationError


@pytest.fixture
def account_validator():
    """Account validator instance."""
    return AccountValidator()


@pytest.fixture
def sample_positions():
    """Sample positions for testing."""
    return [
        Position(
            symbol="AAPL",
            quantity=100,
            avg_price=145.00,
            current_price=150.00,
            market_value=15000.00,
        ),
        Position(
            symbol="GOOGL",
            quantity=50,
            avg_price=2800.00,
            current_price=2850.00,
            market_value=142500.00,
        ),
        Position(
            symbol="AAPL240119C150",  # Call option
            quantity=10,
            avg_price=5.50,
            current_price=6.25,
            market_value=6250.00,
        ),
    ]


@pytest.fixture
def sample_order_legs():
    """Sample order legs for testing."""
    return [
        OrderLeg(
            asset=Stock(symbol="AAPL"),
            order_type=OrderType.BUY,
            quantity=100,
            price=150.00,
        ),
        OrderLeg(
            asset=Call(
                underlying=Stock(symbol="AAPL"),
                strike=155.0,
                expiration_date=date.today() + timedelta(days=30),
            ),
            order_type=OrderType.STO,
            quantity=-1,
            price=5.50,
        ),
    ]


@pytest.fixture
def sample_multi_leg_order(sample_order_legs):
    """Sample multi-leg order for testing."""
    return MultiLegOrder(
        legs=sample_order_legs, net_price=2.50, order_condition="limit"
    )


class TestAccountStateValidation:
    """Test account state validation functionality."""

    def test_validate_account_state_positive_balance(
        self, account_validator, sample_positions
    ):
        """Test account state validation with positive cash balance."""
        result = account_validator.validate_account_state(
            cash_balance=10000.00, positions=sample_positions
        )

        assert result is True

    def test_validate_account_state_zero_balance(
        self, account_validator, sample_positions
    ):
        """Test account state validation with zero cash balance."""
        result = account_validator.validate_account_state(
            cash_balance=0.00, positions=sample_positions
        )

        assert result is True

    def test_validate_account_state_negative_balance_raises_error(
        self, account_validator, sample_positions
    ):
        """Test account state validation with negative balance raises error."""
        with pytest.raises(ValidationError, match="Insufficient cash"):
            account_validator.validate_account_state(
                cash_balance=-1000.00, positions=sample_positions
            )

    def test_validate_account_state_empty_positions(self, account_validator):
        """Test account state validation with no positions."""
        result = account_validator.validate_account_state(
            cash_balance=5000.00, positions=[]
        )

        assert result is True

    def test_validate_account_state_decimal_balance(
        self, account_validator, sample_positions
    ):
        """Test account state validation with decimal balance."""
        result = account_validator.validate_account_state(
            cash_balance=9999.99, positions=sample_positions
        )

        assert result is True

    def test_validate_account_state_large_negative_balance(self, account_validator):
        """Test account state validation with large negative balance."""
        with pytest.raises(ValidationError) as exc_info:
            account_validator.validate_account_state(
                cash_balance=-50000.00, positions=[]
            )

        assert "Insufficient cash" in str(exc_info.value)
        assert "-50,000.00" in str(exc_info.value)


class TestOrderPreExecutionValidation:
    """Test order pre-execution validation."""

    def test_validate_order_pre_execution_success(
        self, account_validator, sample_multi_leg_order, sample_positions
    ):
        """Test successful order pre-execution validation."""
        result = account_validator.validate_order_pre_execution(
            order=sample_multi_leg_order,
            cash_balance=20000.00,
            positions=sample_positions,
            estimated_cost=-5000.00,  # Cash outflow
        )

        assert result is True

    def test_validate_order_pre_execution_insufficient_cash_raises_error(
        self, account_validator, sample_multi_leg_order, sample_positions
    ):
        """Test order validation with insufficient cash raises error."""
        with pytest.raises(ValidationError, match="Insufficient cash for order"):
            account_validator.validate_order_pre_execution(
                order=sample_multi_leg_order,
                cash_balance=1000.00,
                positions=sample_positions,
                estimated_cost=-5000.00,  # Need $5000 but only have $1000
            )

    def test_validate_order_pre_execution_cash_inflow(
        self, account_validator, sample_multi_leg_order, sample_positions
    ):
        """Test order validation with cash inflow (positive estimated cost)."""
        result = account_validator.validate_order_pre_execution(
            order=sample_multi_leg_order,
            cash_balance=1000.00,
            positions=sample_positions,
            estimated_cost=5000.00,  # Cash inflow
        )

        assert result is True

    def test_validate_order_pre_execution_zero_estimated_cost(
        self, account_validator, sample_multi_leg_order, sample_positions
    ):
        """Test order validation with zero estimated cost."""
        result = account_validator.validate_order_pre_execution(
            order=sample_multi_leg_order,
            cash_balance=1000.00,
            positions=sample_positions,
            estimated_cost=0.00,
        )

        assert result is True

    def test_validate_order_pre_execution_exact_balance_match(
        self, account_validator, sample_multi_leg_order, sample_positions
    ):
        """Test order validation where cash exactly matches requirement."""
        result = account_validator.validate_order_pre_execution(
            order=sample_multi_leg_order,
            cash_balance=5000.00,
            positions=sample_positions,
            estimated_cost=-5000.00,  # Exactly matches available cash
        )

        assert result is True

    def test_validate_order_pre_execution_calls_other_validations(
        self, account_validator, sample_multi_leg_order, sample_positions
    ):
        """Test that pre-execution validation calls other validation methods."""
        with (
            patch.object(
                account_validator, "_validate_order_structure"
            ) as mock_structure,
            patch.object(
                account_validator, "_validate_closing_positions"
            ) as mock_closing,
            patch.object(account_validator, "_validate_options_rules") as mock_options,
        ):
            account_validator.validate_order_pre_execution(
                order=sample_multi_leg_order,
                cash_balance=20000.00,
                positions=sample_positions,
                estimated_cost=-1000.00,
            )

            mock_structure.assert_called_once_with(sample_multi_leg_order)
            mock_closing.assert_called_once_with(
                sample_multi_leg_order.legs, sample_positions
            )
            mock_options.assert_called_once_with(sample_multi_leg_order.legs)


class TestOrderStructureValidation:
    """Test order structure validation."""

    def test_validate_order_structure_success(
        self, account_validator, sample_multi_leg_order
    ):
        """Test successful order structure validation."""
        # Should not raise any exceptions
        account_validator._validate_order_structure(sample_multi_leg_order)

    def test_validate_order_structure_empty_legs_raises_error(self, account_validator):
        """Test order structure validation with empty legs raises error."""
        empty_order = MultiLegOrder(legs=[], net_price=0.00, order_condition="limit")

        with pytest.raises(ValidationError, match="Order must have at least one leg"):
            account_validator._validate_order_structure(empty_order)

    def test_validate_order_structure_duplicate_assets_raises_error(
        self, account_validator
    ):
        """Test order structure validation with duplicate assets raises error."""
        duplicate_legs = [
            OrderLeg(
                asset=Stock(symbol="AAPL"),
                order_type=OrderType.BUY,
                quantity=100,
                price=150.00,
            ),
            OrderLeg(
                asset=Stock(symbol="AAPL"),  # Duplicate asset
                order_type=OrderType.SELL,
                quantity=-50,
                price=151.00,
            ),
        ]

        duplicate_order = MultiLegOrder(
            legs=duplicate_legs, net_price=1.00, order_condition="limit"
        )

        with pytest.raises(ValidationError, match="Duplicate assets not allowed"):
            account_validator._validate_order_structure(duplicate_order)

    def test_validate_order_structure_calls_leg_validation(
        self, account_validator, sample_multi_leg_order
    ):
        """Test that order structure validation calls leg validation."""
        with patch.object(account_validator, "_validate_leg") as mock_validate_leg:
            account_validator._validate_order_structure(sample_multi_leg_order)

            # Should call _validate_leg for each leg
            assert mock_validate_leg.call_count == len(sample_multi_leg_order.legs)


class TestLegValidation:
    """Test individual order leg validation."""

    def test_validate_leg_buy_order_success(self, account_validator):
        """Test successful buy order leg validation."""
        buy_leg = OrderLeg(
            asset=Stock(symbol="AAPL"),
            order_type=OrderType.BUY,
            quantity=100,  # Positive quantity for buy
            price=150.00,  # Positive price for buy
        )

        # Should not raise any exceptions
        account_validator._validate_leg(buy_leg, "Test Leg")

    def test_validate_leg_sell_order_success(self, account_validator):
        """Test successful sell order leg validation."""
        sell_leg = OrderLeg(
            asset=Stock(symbol="AAPL"),
            order_type=OrderType.SELL,
            quantity=-100,  # Negative quantity for sell
            price=-150.00,  # Negative price for sell
        )

        # Should not raise any exceptions
        account_validator._validate_leg(sell_leg, "Test Leg")

    def test_validate_leg_zero_quantity_raises_error(self, account_validator):
        """Test leg validation with zero quantity raises error."""
        zero_leg = OrderLeg(
            asset=Stock(symbol="AAPL"),
            order_type=OrderType.BUY,
            quantity=0,  # Invalid zero quantity
            price=150.00,
        )

        with pytest.raises(ValidationError, match="Quantity cannot be zero"):
            account_validator._validate_leg(zero_leg, "Test Leg")

    def test_validate_leg_buy_negative_quantity_raises_error(self, account_validator):
        """Test buy leg with negative quantity raises error."""
        invalid_buy_leg = OrderLeg(
            asset=Stock(symbol="AAPL"),
            order_type=OrderType.BUY,
            quantity=-100,  # Invalid negative quantity for buy
            price=150.00,
        )

        with pytest.raises(
            ValidationError, match="Buy orders must have positive quantity"
        ):
            account_validator._validate_leg(invalid_buy_leg, "Test Leg")

    def test_validate_leg_buy_negative_price_raises_error(self, account_validator):
        """Test buy leg with negative price raises error."""
        invalid_buy_leg = OrderLeg(
            asset=Stock(symbol="AAPL"),
            order_type=OrderType.BUY,
            quantity=100,
            price=-150.00,  # Invalid negative price for buy
        )

        with pytest.raises(
            ValidationError, match="Buy orders must have positive price"
        ):
            account_validator._validate_leg(invalid_buy_leg, "Test Leg")

    def test_validate_leg_sell_positive_quantity_raises_error(self, account_validator):
        """Test sell leg with positive quantity raises error."""
        invalid_sell_leg = OrderLeg(
            asset=Stock(symbol="AAPL"),
            order_type=OrderType.SELL,
            quantity=100,  # Invalid positive quantity for sell
            price=-150.00,
        )

        with pytest.raises(
            ValidationError, match="Sell orders must have negative quantity"
        ):
            account_validator._validate_leg(invalid_sell_leg, "Test Leg")

    def test_validate_leg_sell_positive_price_raises_error(self, account_validator):
        """Test sell leg with positive price raises error."""
        invalid_sell_leg = OrderLeg(
            asset=Stock(symbol="AAPL"),
            order_type=OrderType.SELL,
            quantity=-100,
            price=150.00,  # Invalid positive price for sell
        )

        with pytest.raises(
            ValidationError, match="Sell orders must have negative price"
        ):
            account_validator._validate_leg(invalid_sell_leg, "Test Leg")

    def test_validate_leg_options_order_types(self, account_validator):
        """Test validation of options-specific order types."""
        # Buy to Open (BTO)
        bto_leg = OrderLeg(
            asset=Call(
                underlying=Stock(symbol="AAPL"),
                strike=150.0,
                expiration_date=date.today() + timedelta(days=30),
            ),
            order_type=OrderType.BTO,
            quantity=1,
            price=5.50,
        )
        account_validator._validate_leg(bto_leg, "BTO Leg")

        # Sell to Close (STC)
        stc_leg = OrderLeg(
            asset=Call(
                underlying=Stock(symbol="AAPL"),
                strike=150.0,
                expiration_date=date.today() + timedelta(days=30),
            ),
            order_type=OrderType.STC,
            quantity=-1,
            price=-5.50,
        )
        account_validator._validate_leg(stc_leg, "STC Leg")

    def test_validate_leg_none_price_allowed(self, account_validator):
        """Test that None price is allowed (market orders)."""
        market_leg = OrderLeg(
            asset=Stock(symbol="AAPL"),
            order_type=OrderType.BUY,
            quantity=100,
            price=None,  # Market order
        )

        # Should not raise any exceptions
        account_validator._validate_leg(market_leg, "Market Leg")


class TestClosingPositionValidation:
    """Test closing position validation."""

    def test_validate_closing_positions_success(
        self, account_validator, sample_positions
    ):
        """Test successful closing position validation."""
        closing_legs = [
            OrderLeg(
                asset=Stock(symbol="AAPL"),
                order_type=OrderType.STC,  # Sell to close
                quantity=-50,  # Closing 50 out of 100 shares
                price=-150.00,
            )
        ]

        # Should not raise any exceptions
        account_validator._validate_closing_positions(closing_legs, sample_positions)

    def test_validate_closing_positions_insufficient_quantity_raises_error(
        self, account_validator, sample_positions
    ):
        """Test closing position validation with insufficient quantity raises error."""
        closing_legs = [
            OrderLeg(
                asset=Stock(symbol="AAPL"),
                order_type=OrderType.STC,
                quantity=-200,  # Trying to close 200 but only have 100
                price=-150.00,
            )
        ]

        with pytest.raises(ValidationError, match="Insufficient position quantity"):
            account_validator._validate_closing_positions(
                closing_legs, sample_positions
            )

    def test_validate_closing_positions_no_existing_position_raises_error(
        self, account_validator, sample_positions
    ):
        """Test closing position validation with no existing position raises error."""
        closing_legs = [
            OrderLeg(
                asset=Stock(symbol="TSLA"),  # No TSLA position exists
                order_type=OrderType.STC,
                quantity=-100,
                price=-800.00,
            )
        ]

        with pytest.raises(ValidationError, match="No available positions to close"):
            account_validator._validate_closing_positions(
                closing_legs, sample_positions
            )

    def test_validate_closing_positions_non_closing_orders_ignored(
        self, account_validator, sample_positions
    ):
        """Test that non-closing order types are ignored."""
        opening_legs = [
            OrderLeg(
                asset=Stock(symbol="MSFT"),
                order_type=OrderType.BUY,  # Opening order, not closing
                quantity=100,
                price=300.00,
            )
        ]

        # Should not raise any exceptions
        account_validator._validate_closing_positions(opening_legs, sample_positions)

    def test_validate_closing_positions_btc_options(
        self, account_validator, sample_positions
    ):
        """Test closing options positions with Buy to Close (BTC)."""
        closing_legs = [
            OrderLeg(
                asset=Call(
                    underlying=Stock(symbol="AAPL"),
                    strike=150.0,
                    expiration_date=date.today() + timedelta(days=30),
                ),
                order_type=OrderType.BTC,
                quantity=-5,  # Closing 5 out of 10 options
                price=-6.25,
            )
        ]

        # Should not raise any exceptions (assuming the option position exists)
        # Note: This test assumes the sample_positions includes the AAPL240119C150 option
        account_validator._validate_closing_positions(closing_legs, sample_positions)

    def test_validate_closing_positions_exact_quantity_match(
        self, account_validator, sample_positions
    ):
        """Test closing position with exact quantity match."""
        closing_legs = [
            OrderLeg(
                asset=Stock(symbol="GOOGL"),
                order_type=OrderType.STC,
                quantity=-50,  # Exactly matches the 50 GOOGL shares
                price=-2850.00,
            )
        ]

        # Should not raise any exceptions
        account_validator._validate_closing_positions(closing_legs, sample_positions)


class TestOptionsRulesValidation:
    """Test options-specific trading rules validation."""

    def test_validate_options_rules_success(self, account_validator):
        """Test successful options rules validation."""
        valid_option_legs = [
            OrderLeg(
                asset=Call(
                    underlying=Stock(symbol="AAPL"),
                    strike=150.0,
                    expiration_date=date.today()
                    + timedelta(days=30),  # Valid future date
                ),
                order_type=OrderType.BTO,
                quantity=1,
                price=5.50,
            )
        ]

        # Should not raise any exceptions
        account_validator._validate_options_rules(valid_option_legs)

    def test_validate_options_rules_expired_option_raises_error(
        self, account_validator
    ):
        """Test options rules validation with expired option raises error."""
        expired_option_legs = [
            OrderLeg(
                asset=Call(
                    underlying=Stock(symbol="AAPL"),
                    strike=150.0,
                    expiration_date=date.today()
                    - timedelta(days=1),  # Expired yesterday
                ),
                order_type=OrderType.BTO,
                quantity=1,
                price=5.50,
            )
        ]

        with pytest.raises(ValidationError, match="Cannot trade expired option"):
            account_validator._validate_options_rules(expired_option_legs)

    def test_validate_options_rules_zero_strike_raises_error(self, account_validator):
        """Test options rules validation with zero strike raises error."""
        zero_strike_legs = [
            OrderLeg(
                asset=Call(
                    underlying=Stock(symbol="AAPL"),
                    strike=0.0,  # Invalid zero strike
                    expiration_date=date.today() + timedelta(days=30),
                ),
                order_type=OrderType.BTO,
                quantity=1,
                price=5.50,
            )
        ]

        with pytest.raises(ValidationError, match="Invalid strike price"):
            account_validator._validate_options_rules(zero_strike_legs)

    def test_validate_options_rules_negative_strike_raises_error(
        self, account_validator
    ):
        """Test options rules validation with negative strike raises error."""
        negative_strike_legs = [
            OrderLeg(
                asset=Put(
                    underlying=Stock(symbol="AAPL"),
                    strike=-50.0,  # Invalid negative strike
                    expiration_date=date.today() + timedelta(days=30),
                ),
                order_type=OrderType.BTO,
                quantity=1,
                price=2.50,
            )
        ]

        with pytest.raises(ValidationError, match="Invalid strike price"):
            account_validator._validate_options_rules(negative_strike_legs)

    def test_validate_options_rules_invalid_symbol_format_raises_error(
        self, account_validator
    ):
        """Test options rules validation with invalid symbol format raises error."""
        # Mock an option with invalid symbol format
        invalid_option = Call(
            underlying=Stock(symbol="AAPL"),
            strike=150.0,
            expiration_date=date.today() + timedelta(days=30),
        )
        # Manually set invalid symbol
        invalid_option._symbol = "INVALID"  # Too short, doesn't contain C0 or P0

        invalid_symbol_legs = [
            OrderLeg(
                asset=invalid_option, order_type=OrderType.BTO, quantity=1, price=5.50
            )
        ]

        with pytest.raises(ValidationError, match="Invalid option symbol format"):
            account_validator._validate_options_rules(invalid_symbol_legs)

    def test_validate_options_rules_non_option_assets_ignored(self, account_validator):
        """Test that non-option assets are ignored in options rules validation."""
        mixed_legs = [
            OrderLeg(
                asset=Stock(symbol="AAPL"),  # Stock, not option
                order_type=OrderType.BUY,
                quantity=100,
                price=150.00,
            ),
            OrderLeg(
                asset=Call(
                    underlying=Stock(symbol="AAPL"),
                    strike=155.0,
                    expiration_date=date.today() + timedelta(days=30),
                ),
                order_type=OrderType.BTO,
                quantity=1,
                price=4.50,
            ),
        ]

        # Should not raise any exceptions
        account_validator._validate_options_rules(mixed_legs)

    def test_validate_options_rules_expiration_today_allowed(self, account_validator):
        """Test that options expiring today are allowed."""
        expiring_today_legs = [
            OrderLeg(
                asset=Call(
                    underlying=Stock(symbol="AAPL"),
                    strike=150.0,
                    expiration_date=date.today(),  # Expires today
                ),
                order_type=OrderType.BTO,
                quantity=1,
                price=1.00,
            )
        ]

        # Should not raise any exceptions
        account_validator._validate_options_rules(expiring_today_legs)


class TestPositionLimitsValidation:
    """Test position size and exposure limits validation."""

    def test_validate_position_limits_success(
        self, account_validator, sample_positions
    ):
        """Test successful position limits validation."""
        result = account_validator.validate_position_limits(
            positions=sample_positions,
            max_position_size=200000.00,  # Higher than largest position
            max_total_exposure=500000.00,  # Higher than total exposure
        )

        assert result is True

    def test_validate_position_limits_no_limits_specified(
        self, account_validator, sample_positions
    ):
        """Test position limits validation with no limits specified."""
        result = account_validator.validate_position_limits(
            positions=sample_positions, max_position_size=None, max_total_exposure=None
        )

        assert result is True

    def test_validate_position_limits_max_position_size_exceeded_raises_error(
        self, account_validator, sample_positions
    ):
        """Test position limits validation with max position size exceeded."""
        with pytest.raises(ValidationError, match="Position size limit exceeded"):
            account_validator.validate_position_limits(
                positions=sample_positions,
                max_position_size=100000.00,  # Lower than GOOGL position (142,500)
                max_total_exposure=None,
            )

    def test_validate_position_limits_max_total_exposure_exceeded_raises_error(
        self, account_validator, sample_positions
    ):
        """Test position limits validation with max total exposure exceeded."""
        with pytest.raises(ValidationError, match="Total exposure limit exceeded"):
            account_validator.validate_position_limits(
                positions=sample_positions,
                max_position_size=None,
                max_total_exposure=100000.00,  # Lower than total exposure
            )

    def test_validate_position_limits_zero_market_value_positions(
        self, account_validator
    ):
        """Test position limits validation with zero market value positions."""
        zero_value_positions = [
            Position(
                symbol="ZERO",
                quantity=100,
                avg_price=0.00,
                current_price=0.00,
                market_value=0.00,
            )
        ]

        result = account_validator.validate_position_limits(
            positions=zero_value_positions,
            max_position_size=1000.00,
            max_total_exposure=5000.00,
        )

        assert result is True

    def test_validate_position_limits_none_market_value_positions(
        self, account_validator
    ):
        """Test position limits validation with None market value positions."""
        none_value_positions = [
            Position(
                symbol="NONE",
                quantity=100,
                avg_price=150.00,
                current_price=None,
                market_value=None,
            )
        ]

        result = account_validator.validate_position_limits(
            positions=none_value_positions,
            max_position_size=1000.00,
            max_total_exposure=5000.00,
        )

        assert result is True

    def test_validate_position_limits_negative_market_values(self, account_validator):
        """Test position limits validation with negative market values (short positions)."""
        short_positions = [
            Position(
                symbol="SHORT",
                quantity=-100,
                avg_price=150.00,
                current_price=155.00,
                market_value=-15500.00,  # Negative market value
            )
        ]

        result = account_validator.validate_position_limits(
            positions=short_positions,
            max_position_size=20000.00,
            max_total_exposure=30000.00,
        )

        assert result is True


class TestUtilityMethods:
    """Test utility and helper methods."""

    def test_get_symbol_from_asset(self, account_validator):
        """Test getting symbol from asset."""
        stock = Stock(symbol="AAPL")
        symbol = account_validator._get_symbol(stock)
        assert symbol == "AAPL"

    def test_positions_are_closable_success(self, account_validator):
        """Test positions are closable check."""
        # Can close 50 shares from 100 share position
        assert account_validator._positions_are_closable(100, 50) is True

        # Can close exact amount
        assert account_validator._positions_are_closable(100, 100) is True

        # Can close from short position
        assert account_validator._positions_are_closable(-100, -50) is True

    def test_positions_are_closable_failure(self, account_validator):
        """Test positions are closable check failure."""
        # Cannot close more than available
        assert account_validator._positions_are_closable(100, 150) is False

        # Cannot close more short than available
        assert account_validator._positions_are_closable(-50, -100) is False

    def test_is_valid_option_symbol_success(self, account_validator):
        """Test valid option symbol format checking."""
        # Valid option symbols
        assert account_validator._is_valid_option_symbol("AAPL240119C150000") is True
        assert account_validator._is_valid_option_symbol("GOOGL240315P2800000") is True
        assert account_validator._is_valid_option_symbol("SPY240101C0400000") is True

    def test_is_valid_option_symbol_failure(self, account_validator):
        """Test invalid option symbol format checking."""
        # Too short
        assert account_validator._is_valid_option_symbol("AAPL") is False

        # Doesn't contain C0 or P0
        assert account_validator._is_valid_option_symbol("AAPL240119X150000") is False

        # Empty string
        assert account_validator._is_valid_option_symbol("") is False


class TestErrorHandlingAndEdgeCases:
    """Test error handling and edge cases."""

    def test_validation_error_creation(self):
        """Test ValidationError exception creation."""
        error = ValidationError("Test error message")
        assert str(error) == "Test error message"
        assert isinstance(error, Exception)

    def test_validate_order_structure_with_asset_objects(self, account_validator):
        """Test order structure validation with actual asset objects."""
        legs_with_assets = [
            OrderLeg(
                asset=Stock(symbol="AAPL"),
                order_type=OrderType.BUY,
                quantity=100,
                price=150.00,
            ),
            OrderLeg(
                asset=Call(
                    underlying=Stock(symbol="GOOGL"),
                    strike=2900.0,
                    expiration_date=date.today() + timedelta(days=45),
                ),
                order_type=OrderType.STO,
                quantity=-1,
                price=-25.00,
            ),
        ]

        order = MultiLegOrder(
            legs=legs_with_assets, net_price=125.00, order_condition="limit"
        )

        # Should not raise any exceptions
        account_validator._validate_order_structure(order)

    def test_validate_closing_positions_with_string_assets(
        self, account_validator, sample_positions
    ):
        """Test closing position validation when assets are strings instead of objects."""
        # This tests the fallback logic when asset is not an Asset object
        string_asset_legs = [
            OrderLeg(
                asset="AAPL",  # String instead of Asset object
                order_type=OrderType.STC,
                quantity=-25,
                price=-150.00,
            )
        ]

        # Should handle gracefully and still perform validation
        account_validator._validate_closing_positions(
            string_asset_legs, sample_positions
        )

    def test_options_rules_validation_with_edge_case_dates(self, account_validator):
        """Test options rules validation with edge case expiration dates."""
        # Option expiring in exactly one year
        far_future_legs = [
            OrderLeg(
                asset=Call(
                    underlying=Stock(symbol="AAPL"),
                    strike=200.0,
                    expiration_date=date.today() + timedelta(days=365),
                ),
                order_type=OrderType.BTO,
                quantity=1,
                price=10.00,
            )
        ]

        # Should not raise any exceptions
        account_validator._validate_options_rules(far_future_legs)

    def test_validate_order_pre_execution_with_edge_case_costs(
        self, account_validator, sample_multi_leg_order, sample_positions
    ):
        """Test order validation with edge case estimated costs."""
        # Very large cost
        result = account_validator.validate_order_pre_execution(
            order=sample_multi_leg_order,
            cash_balance=1000000.00,
            positions=sample_positions,
            estimated_cost=-999999.00,
        )
        assert result is True

        # Very small cost
        result = account_validator.validate_order_pre_execution(
            order=sample_multi_leg_order,
            cash_balance=1.00,
            positions=sample_positions,
            estimated_cost=-0.01,
        )
        assert result is True

    def test_position_limits_with_extreme_values(self, account_validator):
        """Test position limits validation with extreme values."""
        extreme_positions = [
            Position(
                symbol="EXTREME",
                quantity=1,
                avg_price=1e6,  # Very high price
                current_price=1e6,
                market_value=1e6,
            )
        ]

        # Should handle extreme values gracefully
        result = account_validator.validate_position_limits(
            positions=extreme_positions, max_position_size=2e6, max_total_exposure=5e6
        )
        assert result is True

    def test_validation_with_empty_inputs(self, account_validator):
        """Test validation methods with empty inputs."""
        empty_order = MultiLegOrder(legs=[], net_price=0.00, order_condition="market")

        # Empty order should raise error
        with pytest.raises(ValidationError):
            account_validator._validate_order_structure(empty_order)

        # Empty positions list should be fine for most validations
        result = account_validator.validate_position_limits(
            positions=[], max_position_size=10000.00, max_total_exposure=50000.00
        )
        assert result is True

    def test_concurrent_validation_calls(
        self, account_validator, sample_multi_leg_order, sample_positions
    ):
        """Test that validation methods can handle concurrent calls."""
        import threading

        results = []
        errors = []

        def validate_worker():
            try:
                result = account_validator.validate_order_pre_execution(
                    order=sample_multi_leg_order,
                    cash_balance=20000.00,
                    positions=sample_positions,
                    estimated_cost=-1000.00,
                )
                results.append(result)
            except Exception as e:
                errors.append(e)

        # Run multiple validation calls concurrently
        threads = []
        for _ in range(5):
            thread = threading.Thread(target=validate_worker)
            threads.append(thread)
            thread.start()

        # Wait for all threads to complete
        for thread in threads:
            thread.join()

        # All should succeed
        assert len(results) == 5
        assert len(errors) == 0
        assert all(result is True for result in results)
