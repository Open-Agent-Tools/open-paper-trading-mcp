"""
Tests for the advanced strategy analyzer in app/services/strategies/analyzer.py.
"""
import pytest
from app.services.strategies.analyzer import AdvancedStrategyAnalyzer
from app.models.trading import Position
from app.models.assets import Asset, Option
from app.models.quotes import Quote, OptionQuote
from datetime import datetime

@pytest.fixture
def analyzer():
    """Provides an AdvancedStrategyAnalyzer instance."""
    return AdvancedStrategyAnalyzer()

@pytest.fixture
def sample_positions():
    """Provides a sample set of positions for testing."""
    return [
        Position(symbol="SPY251219C00500000", quantity=-1, avg_price=10.0, asset=Option.from_symbol("SPY251219C00500000")),
        Position(symbol="SPY251219C00510000", quantity=1, avg_price=8.0, asset=Option.from_symbol("SPY251219C00510000")),
    ]

@pytest.fixture
def sample_quotes():
    """Provides sample quotes with Greeks."""
    return {
        "SPY251219C00500000": OptionQuote(asset=Option.from_symbol("SPY251219C00500000"), quote_date=datetime.now(), price=11.0, delta=0.5, gamma=0.05, theta=-0.1, vega=0.2),
        "SPY251219C00510000": OptionQuote(asset=Option.from_symbol("SPY251219C00510000"), quote_date=datetime.now(), price=9.0, delta=0.4, gamma=0.04, theta=-0.08, vega=0.18),
    }

def test_aggregate_strategy_greeks(analyzer, sample_positions, sample_quotes):
    """Tests the aggregation of Greeks for a portfolio."""
    greeks = analyzer.aggregate_strategy_greeks(sample_positions, sample_quotes)
    assert greeks.delta != 0
    assert greeks.gamma != 0
    assert greeks.theta != 0
    assert greeks.vega != 0
