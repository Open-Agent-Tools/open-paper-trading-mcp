"""
Tests for the order execution engine in app/services/order_execution.py.
"""
import pytest
from app.services.order_execution import OrderExecutionEngine, OrderExecutionError
from app.models.trading import Order, OrderType, Position, MultiLegOrder
from app.models.assets import Stock
from datetime import datetime

@pytest.fixture
def execution_engine():
    """Provides an OrderExecutionEngine instance."""
    return OrderExecutionEngine()

@pytest.fixture
def sample_order():
    """Provides a sample order for testing."""
    return MultiLegOrder(legs=[
        Order(symbol="AAPL", quantity=10, order_type=OrderType.BUY, price=150.0).to_leg()
    ])

@pytest.fixture
def sample_positions():
    """Provides sample positions."""
    return [
        Position(symbol="GOOGL", quantity=-10, avg_price=2800.0, current_price=2750.0, asset=Stock(symbol="GOOGL")),
    ]

@pytest.mark.asyncio
async def test_execute_order_success(execution_engine, sample_order, sample_positions):
    """Tests successful order execution."""
    result = await execution_engine.execute_order("test_account", sample_order, 10000.0, sample_positions)
    assert result.success
    assert result.cash_change < 0
    assert len(result.positions_created) == 1

@pytest.mark.asyncio
async def test_execute_order_insufficient_cash(execution_engine, sample_order, sample_positions):
    """Tests order execution with insufficient cash."""
    result = await execution_engine.execute_order("test_account", sample_order, 1000.0, sample_positions)
    assert not result.success
    assert "Insufficient cash" in result.message
