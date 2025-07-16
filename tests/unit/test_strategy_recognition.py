"""
Tests for the strategy recognition service in app/services/strategies/recognition.py.
"""

import pytest
from app.services.strategies.recognition import StrategyRecognitionService
from app.models.trading import Position
from app.models.assets import asset_factory


@pytest.fixture
def recognition_service() -> StrategyRecognitionService:
    """Provides a StrategyRecognitionService instance."""
    return StrategyRecognitionService()


@pytest.fixture
def sample_positions() -> list[Position]:
    """Provides a sample set of positions for testing."""
    return [
        Position(
            symbol="AAPL", quantity=100, avg_price=150.0, asset=asset_factory("AAPL")
        ),
        Position(
            symbol="SPY251219C00500000",
            quantity=-1,
            avg_price=10.0,
            asset=asset_factory("SPY251219C00500000"),
        ),
        Position(
            symbol="SPY251219C00510000",
            quantity=1,
            avg_price=8.0,
            asset=asset_factory("SPY251219C00510000"),
        ),
    ]


def test_group_positions_by_strategy(
    recognition_service: StrategyRecognitionService, sample_positions: list[Position]
) -> None:
    """Tests the group_positions_by_strategy method."""
    strategies = recognition_service.group_positions_by_strategy(sample_positions)
    assert len(strategies) > 0
    # Example assertion: check if a covered call is identified
    assert any(s.strategy_type == "covered" for s in strategies)
