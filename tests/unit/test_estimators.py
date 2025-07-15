"""
Tests for the price estimators in app/services/estimators.py.
"""
import pytest
from app.services.estimators import (
    MidpointEstimator,
    SlippageEstimator,
    create_estimator,
)
from app.models.quotes import Quote
from app.models.assets import Stock
from datetime import datetime

@pytest.fixture
def sample_quote():
    """Provides a sample quote for testing."""
    return Quote(
        asset=Stock(symbol="AAPL"),
        quote_date=datetime.now(),
        price=150.0,
        bid=149.9,
        ask=150.1,
        volume=1000000,
    )

def test_midpoint_estimator(sample_quote):
    """Tests the MidpointEstimator."""
    estimator = MidpointEstimator()
    estimated_price = estimator.estimate(sample_quote)
    assert estimated_price == 150.0

def test_slippage_estimator(sample_quote):
    """Tests the SlippageEstimator."""
    estimator = SlippageEstimator(slippage=0.5)
    # Buying
    estimated_price_buy = estimator.estimate(sample_quote, quantity=100)
    assert estimated_price_buy < 150.0
    # Selling
    estimated_price_sell = estimator.estimate(sample_quote, quantity=-100)
    assert estimated_price_sell > 150.0

def test_create_estimator():
    """Tests the create_estimator factory function."""
    estimator = create_estimator("midpoint")
    assert isinstance(estimator, MidpointEstimator)
    estimator = create_estimator("slippage", slippage=0.5)
    assert isinstance(estimator, SlippageEstimator)
    assert estimator.slippage == 0.5
