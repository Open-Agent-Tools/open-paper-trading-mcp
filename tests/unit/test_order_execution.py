"""
Tests for the order execution engine in app/services/order_execution.py.
"""

import pytest
from unittest.mock import Mock
from app.services.order_execution import OrderExecutionEngine, OrderExecutionError
from app.schemas.orders import OrderType, MultiLegOrder, OrderLeg, OrderCondition
from app.models.trading import Position
from app.models.assets import Asset, Stock


@pytest.mark.asyncio
class TestOrderExecutionEngine:
    @pytest.fixture
    def execution_engine(self) -> OrderExecutionEngine:
        """Provides an OrderExecutionEngine instance with a mock quote service."""
        engine = OrderExecutionEngine()
        engine.quote_service = Mock()

        # Make the mock awaitable
        async def get_quote_mock(asset: Asset) -> Mock:
            quote = Mock()
            quote.price = 150.0
            quote.bid = 149.9
            quote.ask = 150.1
            return quote

        engine.quote_service.get_quote = get_quote_mock
        return engine

    @pytest.fixture
    def sample_bto_order(self) -> MultiLegOrder:
        """Provides a sample Buy-To-Open order."""
        return MultiLegOrder(
            legs=[
                OrderLeg(
                    asset=Asset(symbol="AAPL"),
                    quantity=10,
                    order_type=OrderType.BTO,
                    price=150.0,
                )
            ],
            condition=OrderCondition.MARKET,
            limit_price=None,
        )

    @pytest.fixture
    def sample_stc_order(self) -> MultiLegOrder:
        """Provides a sample Sell-To-Close order."""
        return MultiLegOrder(
            legs=[
                OrderLeg(
                    asset=Asset(symbol="GOOGL"),
                    quantity=10,
                    order_type=OrderType.STC,
                    price=None,
                )
            ],
            condition=OrderCondition.MARKET,
            limit_price=None,
        )

    @pytest.fixture
    def sample_positions(self) -> list[Position]:
        """Provides sample positions."""
        return [
            Position(
                symbol="GOOGL",
                quantity=10,
                avg_price=2800.0,
                asset=Stock(symbol="GOOGL"),
            ),
        ]

    async def test_execute_order_success(
        self,
        execution_engine: OrderExecutionEngine,
        sample_bto_order: MultiLegOrder,
        sample_positions: list[Position],
    ) -> None:
        """Tests successful order execution for an opening order."""
        result = await execution_engine.execute_order(
            "test_account", sample_bto_order, 2000.0, sample_positions
        )
        assert result.success
        assert result.cash_change < 0
        assert len(result.positions_created) == 1
        assert result.positions_created[0].symbol == "AAPL"

    async def test_execute_simple_order(
        self, execution_engine: OrderExecutionEngine
    ) -> None:
        """Test stub for execute_simple_order."""
        pytest.fail("Test not implemented")

    async def test_execute_order_insufficient_cash(
        self,
        execution_engine: OrderExecutionEngine,
        sample_bto_order: MultiLegOrder,
        sample_positions: list[Position],
    ) -> None:
        """Tests order execution with insufficient cash."""
        result = await execution_engine.execute_order(
            "test_account", sample_bto_order, 1000.0, sample_positions
        )
        assert not result.success
        assert "Insufficient cash" in result.message

    async def test_execute_order_insufficient_position_to_close(
        self, execution_engine: OrderExecutionEngine, sample_stc_order: MultiLegOrder
    ) -> None:
        """Tests order execution with insufficient position to close."""
        # No initial positions
        result = await execution_engine.execute_order(
            "test_account", sample_stc_order, 50000.0, []
        )
        assert not result.success
        assert "No available positions to close" in result.message

    async def test_validate_order_no_legs(
        self, execution_engine: OrderExecutionEngine
    ) -> None:
        """Tests validation for an order with no legs."""
        order = MultiLegOrder(
            legs=[], condition=OrderCondition.MARKET, limit_price=None
        )
        with pytest.raises(
            OrderExecutionError, match="Order must have at least one leg"
        ):
            execution_engine._validate_order(order)

    async def test_calculate_leg_prices(
        self, execution_engine: OrderExecutionEngine
    ) -> None:
        """Test stub for _calculate_leg_prices."""
        pytest.fail("Test not implemented")

    async def test_should_fill_order_limit_not_met(
        self, execution_engine: OrderExecutionEngine
    ) -> None:
        """Test stub for _should_fill_order with a limit order that shouldn't fill."""
        pytest.fail("Test not implemented")

    async def test_calculate_cash_requirement(
        self, execution_engine: OrderExecutionEngine
    ) -> None:
        """Test stub for _calculate_cash_requirement."""
        pytest.fail("Test not implemented")

    async def test_open_position(self, execution_engine: OrderExecutionEngine) -> None:
        """Test stub for _open_position."""
        pytest.fail("Test not implemented")

    async def test_close_position_fifo(
        self, execution_engine: OrderExecutionEngine
    ) -> None:
        """Tests the FIFO logic for closing positions."""
        pytest.fail("Test not implemented")

    async def test_close_position_partial(
        self, execution_engine: OrderExecutionEngine
    ) -> None:
        """Tests partially closing a position."""
        pytest.fail("Test not implemented")
