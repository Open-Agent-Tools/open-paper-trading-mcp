"""
Tests for the margin calculation service in app/services/margin.py.
"""
import pytest
from app.services.margin import MaintenanceMarginService
from app.services.strategies.models import SpreadStrategy, SpreadType
from app.models.assets import Option
from app.models.trading import Position

@pytest.fixture
def margin_service():
    """Provides a MaintenanceMarginService instance."""
    return MaintenanceMarginService()

@pytest.fixture
def credit_spread_strategy():
    """Provides a sample credit spread strategy."""
    sell_option = Option.from_symbol("SPY251219P00490000")
    buy_option = Option.from_symbol("SPY251219P00480000")
    return SpreadStrategy(sell_option=sell_option, buy_option=buy_option, quantity=1)

def test_calculate_credit_spread_margin(margin_service, credit_spread_strategy):
    """Tests margin calculation for a credit spread."""
    margin_req = margin_service._calculate_spread_margin(credit_spread_strategy, None)
    # Margin should be the difference in strikes * 100
    expected_margin = (490.0 - 480.0) * 100
    assert margin_req.margin_requirement == expected_margin
