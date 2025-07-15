"""
Tests for the validation service in app/services/validation.py.
"""
import pytest
from app.services.validation import AccountValidator, ValidationError
from app.models.trading import Order, OrderType, Position, MultiLegOrder
from app.models.assets import Stock
from datetime import date

@pytest.fixture
def validator():
    """Provides an AccountValidator instance."""
    return AccountValidator()

@pytest.fixture
def sample_positions():
    """Provides sample positions."""
    return [
        Position(symbol="AAPL", quantity=100, avg_price=150.0, current_price=155.0),
        Position(symbol="GOOGL", quantity=-10, avg_price=2800.0, current_price=2750.0),
    ]

def test_validate_account_state_success(validator):
    """Tests successful account state validation."""
    assert validator.validate_account_state(cash_balance=10000.0, positions=[], maintenance_margin=5000.0)

def test_validate_account_state_negative_cash(validator):
    """Tests for negative cash balance."""
    with pytest.raises(ValidationError, match="Insufficient cash"):
        validator.validate_account_state(cash_balance=-100.0, positions=[], maintenance_margin=0)

def test_validate_account_state_insufficient_margin(validator):
    """Tests for insufficient margin."""
    with pytest.raises(ValidationError, match="Insufficient cash for margin"):
        validator.validate_account_state(cash_balance=4000.0, positions=[], maintenance_margin=5000.0)

def test_validate_order_pre_execution_success(validator, sample_positions):
    """Tests successful pre-execution order validation."""
    order = MultiLegOrder(legs=[
        Order(symbol="TSLA", quantity=10, order_type=OrderType.BUY, price=200.0).to_leg()
    ])
    assert validator.validate_order_pre_execution(order, 10000.0, sample_positions, -2000.0)

def test_validate_closing_positions_insufficient(validator, sample_positions):
    """Tests validation for closing a position with insufficient quantity."""
    order = MultiLegOrder(legs=[
        Order(symbol="AAPL", quantity=-150, order_type=OrderType.SELL, price=155.0).to_leg()
    ])
    with pytest.raises(ValidationError, match="Insufficient position quantity to close"):
        validator._validate_closing_positions(order.legs, sample_positions)
