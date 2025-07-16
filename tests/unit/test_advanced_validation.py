"""
Tests for the advanced validation service in app/services/advanced_validation.py.
"""

import pytest
from app.services.advanced_validation import AdvancedOrderValidator, AccountLimits
from app.schemas.orders import Order, OrderType
from app.models.trading import Position
from app.models.assets import Stock, asset_factory
from app.models.quotes import Quote, OptionQuote
from datetime import datetime, date, timedelta


@pytest.fixture
def advanced_validator():
    """Provides an AdvancedOrderValidator instance."""
    return AdvancedOrderValidator()


@pytest.fixture
def sample_account_data():
    """Provides sample account data."""
    return {
        "cash_balance": 50000.0,
        "positions": [
            Position(symbol="AAPL", quantity=100, avg_price=150.0, current_price=155.0)
        ],
    }


@pytest.fixture
def sample_quotes():
    """Provides sample quotes."""
    return {
        "AAPL": Quote(
            asset=Stock(symbol="AAPL"), quote_date=datetime.now(), price=155.0
        ),
        "SPY251219C00500000": OptionQuote(
            asset=asset_factory("SPY251219C00500000"),
            quote_date=datetime.now(),
            price=10.0,
            underlying_price=500.0,
            iv=0.20,
        ),
    }


def test_validate_order_success(advanced_validator, sample_account_data, sample_quotes):
    """Tests a successful advanced order validation."""
    order = Order(
        symbol="SPY251219C00500000", quantity=1, order_type=OrderType.BTO, price=10.0
    )
    result = advanced_validator.validate_order(
        sample_account_data, order, sample_quotes
    )
    assert result.is_valid
    assert result.can_execute


def test_validate_expiration_date_too_close(
    advanced_validator, sample_account_data, sample_quotes
):
    """Tests validation for an option that expires too soon."""
    today = date.today()
    yesterday_str = (today - timedelta(days=1)).strftime("%y%m%d")
    expired_option_symbol = f"SPY{yesterday_str}C00500000"
    expired_option = asset_factory(expired_option_symbol)

    order = Order(
        symbol=expired_option_symbol, quantity=1, order_type=OrderType.BTO, price=0.01
    )

    quotes = sample_quotes.copy()
    quotes[expired_option_symbol] = OptionQuote(
        asset=expired_option,
        quote_date=datetime.now(),
        price=0.01,
        underlying_price=500.0,
    )

    result = advanced_validator.validate_order(sample_account_data, order, quotes)
    assert not result.is_valid
    error_codes = [msg.code for msg in result.errors]
    assert "OPTION_EXPIRED" in error_codes


def test_position_size_exceeded(advanced_validator, sample_account_data, sample_quotes):
    """Tests validation for an order that exceeds the maximum position size."""
    order = Order(symbol="AAPL", quantity=1000, order_type=OrderType.BUY, price=155.0)
    limits = AccountLimits(max_position_size=100000.0)
    result = advanced_validator.validate_order(
        sample_account_data, order, sample_quotes, limits
    )
    assert not result.is_valid
    error_codes = [msg.code for msg in result.errors]
    assert "POSITION_SIZE_EXCEEDED" in error_codes
