"""
Tests for the options expiration engine in app/services/expiration.py.
"""
import pytest
from app.services.expiration import OptionsExpirationEngine, ExpirationResult
from app.models.trading import Position
from app.models.assets import Option
from app.adapters.test_data import TestDataQuoteAdapter
from datetime import date, timedelta

@pytest.fixture
def expiration_engine():
    """Provides an OptionsExpirationEngine instance."""
    return OptionsExpirationEngine()

@pytest.fixture
def sample_account_data():
    """Provides sample account data with an expired option."""
    today = date.today()
    yesterday = today - timedelta(days=1)
    yesterday_str = yesterday.strftime("%y%m%d")
    
    return {
        "cash_balance": 10000.0,
        "positions": [
            Position(symbol=f"SPY{yesterday_str}C00500000", quantity=1, avg_price=1.0, asset=Option.from_symbol(f"SPY{yesterday_str}C00500000"))
        ]
    }

@pytest.fixture
def quote_adapter():
    """Provides a TestDataQuoteAdapter."""
    return TestDataQuoteAdapter()

def test_process_account_expirations(expiration_engine, sample_account_data, quote_adapter):
    """Tests the processing of expired options in an account."""
    result = expiration_engine.process_account_expirations(sample_account_data, quote_adapter)
    assert len(result.expired_positions) == 1
    assert result.expired_positions[0].symbol == sample_account_data["positions"][0].symbol
