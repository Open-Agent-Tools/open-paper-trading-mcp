"""
Tests for the strategy recognition service in app/services/strategies/recognition.py.
"""
import pytest
from app.services.strategies.recognition import StrategyRecognitionService
from app.models.trading import Position
from app.models.assets import Stock, Option

@pytest.fixture
def recognition_service():
    """Provides a StrategyRecognitionService instance."""
    return StrategyRecognitionService()

@pytest.fixture
def sample_positions():
    """Provides a sample set of positions for testing."""
    return [
        Position(symbol="AAPL", quantity=100, avg_price=150.0, asset=Stock(symbol="AAPL")),
        Position(symbol="SPY251219C00500000", quantity=-1, avg_price=10.0, asset=Option.from_symbol("SPY251219C00500000")),
        Position(symbol="SPY251219C00510000", quantity=1, avg_price=8.0, asset=Option.from_symbol("SPY251219C00510000")),
    ]

def test_group_positions_by_strategy(recognition_service, sample_positions):
    """Tests the group_positions_by_strategy method."""
    strategies = recognition_service.group_positions_by_strategy(sample_positions)
    assert len(strategies) > 0
    # Example assertion: check if a covered call is identified
    assert any(s.strategy_type == 'covered' for s in strategies)
