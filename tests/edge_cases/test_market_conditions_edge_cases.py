"""
Edge case testing for market conditions and special scenarios.

This module tests system behavior during:
- Market hours validation
- Holiday and weekend handling
- Stock halts and circuit breakers
- Data feed failures
- Extreme market conditions
"""

import asyncio
from contextlib import contextmanager
from datetime import date, datetime, time, timedelta
from unittest.mock import AsyncMock, Mock, patch

import pytest
import pytz

from app.schemas.orders import Order, OrderStatus, OrderType
from app.services.market_impact import MarketImpactSimulator
from app.services.order_execution_engine import OrderExecutionEngine
from app.services.order_state_tracker import (
    MemoryEfficientOrderTracker,
    StateChangeEvent,
)


class MarketHours:
    """Market hours configuration."""

    MARKET_OPEN = time(9, 30)  # 9:30 AM EST
    MARKET_CLOSE = time(16, 0)  # 4:00 PM EST
    PRE_MARKET_START = time(4, 0)  # 4:00 AM EST
    AFTER_HOURS_END = time(20, 0)  # 8:00 PM EST


class TestMarketHoursValidation:
    """Test market hours and trading session validation."""

    @pytest.fixture
    def mock_trading_service(self):
        service = AsyncMock()
        service.get_current_quote = AsyncMock(return_value=Mock(price=150.00))
        service.execute_order = AsyncMock()
        service.is_market_open = AsyncMock(return_value=True)
        return service

    @pytest.fixture
    async def execution_engine(self, mock_trading_service):
        engine = OrderExecutionEngine(mock_trading_service)
        await engine.start()
        yield engine
        await engine.stop()

    def test_market_hours_detection(self):
        """Test detection of market hours."""
        est = pytz.timezone("US/Eastern")

        # Market open time (Wednesday 10:00 AM EST)
        market_open_time = est.localize(datetime(2024, 3, 13, 10, 0, 0))
        assert self._is_market_hours(market_open_time)

        # Market closed time (Wednesday 5:00 PM EST)
        market_closed_time = est.localize(datetime(2024, 3, 13, 17, 0, 0))
        assert not self._is_market_hours(market_closed_time)

        # Weekend (Saturday 10:00 AM EST)
        weekend_time = est.localize(datetime(2024, 3, 16, 10, 0, 0))
        assert not self._is_market_hours(weekend_time)

    @pytest.mark.asyncio
    async def test_order_rejection_outside_hours(
        self, execution_engine, mock_trading_service
    ):
        """Test order rejection when market is closed."""
        # Mock market as closed
        mock_trading_service.is_market_open = AsyncMock(return_value=False)

        closed_market_order = Order(
            id="closed_market_1",
            symbol="AAPL",
            order_type=OrderType.BUY,
            quantity=100,
            status=OrderStatus.PENDING,
            created_at=datetime.utcnow(),
        )

        # Attempt to process order when market is closed
        with patch.object(execution_engine, "_is_market_open", return_value=False):
            result = await execution_engine._should_process_order(closed_market_order)
            assert not result, "Order should be rejected when market is closed"

    @pytest.mark.asyncio
    async def test_extended_hours_trading(self, execution_engine):
        """Test extended hours trading validation."""
        pre_market_order = Order(
            id="pre_market_1",
            symbol="AAPL",
            order_type=OrderType.LIMIT,
            quantity=100,
            price=150.00,
            status=OrderStatus.PENDING,
            created_at=datetime.utcnow(),
            metadata={"extended_hours": True},
        )

        # Mock pre-market time (7:00 AM EST)
        with patch("datetime.datetime") as mock_datetime:
            est = pytz.timezone("US/Eastern")
            mock_time = est.localize(datetime(2024, 3, 13, 7, 0, 0))
            mock_datetime.now.return_value = mock_time
            mock_datetime.utcnow.return_value = mock_time

            # Should allow extended hours order
            can_process = self._can_process_extended_hours(pre_market_order, mock_time)
            assert can_process, "Extended hours order should be allowed in pre-market"

    def test_holiday_detection(self):
        """Test detection of market holidays."""
        # Common market holidays (2024)
        holidays = [
            date(2024, 1, 1),  # New Year's Day
            date(2024, 1, 15),  # Martin Luther King Jr. Day
            date(2024, 2, 19),  # Presidents' Day
            date(2024, 7, 4),  # Independence Day
            date(2024, 12, 25),  # Christmas Day
        ]

        for holiday in holidays:
            assert self._is_market_holiday(
                holiday
            ), f"{holiday} should be recognized as market holiday"

        # Regular trading day
        regular_day = date(2024, 3, 13)  # Wednesday
        assert not self._is_market_holiday(
            regular_day
        ), "Regular day should not be holiday"

    def _is_market_hours(self, dt: datetime) -> bool:
        """Check if datetime is during market hours."""
        if dt.weekday() >= 5:  # Weekend
            return False

        if self._is_market_holiday(dt.date()):
            return False

        market_time = dt.time()
        return MarketHours.MARKET_OPEN <= market_time <= MarketHours.MARKET_CLOSE

    def _can_process_extended_hours(self, order: Order, dt: datetime) -> bool:
        """Check if order can be processed in extended hours."""
        if not order.metadata.get("extended_hours", False):
            return False

        market_time = dt.time()
        return (
            MarketHours.PRE_MARKET_START <= market_time < MarketHours.MARKET_OPEN
            or MarketHours.MARKET_CLOSE < market_time <= MarketHours.AFTER_HOURS_END
        )

    def _is_market_holiday(self, check_date: date) -> bool:
        """Check if date is a market holiday."""
        # Simplified holiday check - real implementation would use trading calendar
        holidays_2024 = [
            date(2024, 1, 1),
            date(2024, 1, 15),
            date(2024, 2, 19),
            date(2024, 3, 29),
            date(2024, 5, 27),
            date(2024, 6, 19),
            date(2024, 7, 4),
            date(2024, 9, 2),
            date(2024, 11, 28),
            date(2024, 12, 25),
        ]
        return check_date in holidays_2024


class TestStockHaltsAndCircuitBreakers:
    """Test handling of stock halts and market circuit breakers."""

    @pytest.fixture
    def mock_halted_service(self):
        service = AsyncMock()

        # Simulate halted stock
        def get_quote_with_halt(symbol):
            if symbol == "HALTED":
                quote = Mock(
                    price=100.00, is_halted=True, halt_reason="T1"
                )  # Trading halt
                return quote
            else:
                return Mock(price=150.00, is_halted=False, halt_reason=None)

        service.get_current_quote = AsyncMock(side_effect=get_quote_with_halt)
        service.execute_order = AsyncMock()
        service.is_stock_halted = AsyncMock(return_value=False)
        return service

    @pytest.mark.asyncio
    async def test_stock_halt_detection(self, mock_halted_service):
        """Test detection of halted stocks."""
        execution_engine = OrderExecutionEngine(mock_halted_service)
        await execution_engine.start()

        try:
            halted_order = Order(
                id="halt_test_1",
                symbol="HALTED",
                order_type=OrderType.STOP_LOSS,
                quantity=100,
                stop_price=95.00,
                status=OrderStatus.PENDING,
                created_at=datetime.utcnow(),
            )

            execution_engine.add_trigger_order(halted_order)

            # Try to trigger order on halted stock
            await execution_engine._check_trigger_conditions("HALTED", 90.00)

            # Order should not execute due to halt
            mock_halted_service.execute_order.assert_not_called()

        finally:
            await execution_engine.stop()

    @pytest.mark.asyncio
    async def test_circuit_breaker_handling(self):
        """Test market-wide circuit breaker handling."""
        mock_service = AsyncMock()
        mock_service.get_current_quote = AsyncMock(return_value=Mock(price=150.00))
        mock_service.execute_order = AsyncMock()
        mock_service.is_circuit_breaker_active = AsyncMock(return_value=True)

        execution_engine = OrderExecutionEngine(mock_service)
        await execution_engine.start()

        try:
            circuit_breaker_order = Order(
                id="cb_test_1",
                symbol="SPY",
                order_type=OrderType.SELL,
                quantity=1000,
                status=OrderStatus.PENDING,
                created_at=datetime.utcnow(),
            )

            # Simulate circuit breaker active
            with patch.object(
                execution_engine, "_is_circuit_breaker_active", return_value=True
            ):
                should_process = await execution_engine._should_process_order(
                    circuit_breaker_order
                )
                assert (
                    not should_process
                ), "Orders should be paused during circuit breaker"

        finally:
            await execution_engine.stop()

    @pytest.mark.asyncio
    async def test_halt_recovery_processing(self, mock_halted_service):
        """Test order processing when halt is lifted."""
        execution_engine = OrderExecutionEngine(mock_halted_service)
        state_tracker = MemoryEfficientOrderTracker()

        await execution_engine.start()
        await state_tracker.start()

        try:
            recovery_order = Order(
                id="recovery_test_1",
                symbol="RECOVER",
                order_type=OrderType.STOP_LOSS,
                quantity=200,
                stop_price=98.00,
                status=OrderStatus.PENDING,
                created_at=datetime.utcnow(),
            )

            execution_engine.add_trigger_order(recovery_order)
            state_tracker.track_state_change(
                recovery_order.id, OrderStatus.PENDING, StateChangeEvent.CREATED
            )

            # Initially halted
            mock_halted_service.is_stock_halted = AsyncMock(return_value=True)

            # Try to trigger (should be blocked)
            await execution_engine._check_trigger_conditions("RECOVER", 95.00)
            mock_halted_service.execute_order.assert_not_called()

            # Halt lifted
            mock_halted_service.is_stock_halted = AsyncMock(return_value=False)

            # Should now execute
            await execution_engine._check_trigger_conditions("RECOVER", 95.00)
            mock_halted_service.execute_order.assert_called_once()

            # Track execution
            state_tracker.track_state_change(
                recovery_order.id, OrderStatus.FILLED, StateChangeEvent.FILLED
            )

            # Verify state progression
            history = state_tracker.get_order_history(recovery_order.id)
            events = [s.event for s in history]
            assert StateChangeEvent.CREATED in events
            assert StateChangeEvent.FILLED in events

        finally:
            await execution_engine.stop()
            await state_tracker.stop()


class TestDataFeedFailures:
    """Test handling of data feed failures and connectivity issues."""

    @pytest.mark.asyncio
    async def test_quote_service_timeout(self):
        """Test handling of quote service timeouts."""
        mock_service = AsyncMock()

        # Simulate timeout
        async def timeout_quote(symbol):
            await asyncio.sleep(10)  # Simulate long delay
            return Mock(price=150.00)

        mock_service.get_current_quote = timeout_quote
        mock_service.execute_order = AsyncMock()

        execution_engine = OrderExecutionEngine(mock_service)
        await execution_engine.start()

        try:
            timeout_order = Order(
                id="timeout_test_1",
                symbol="TIMEOUT",
                order_type=OrderType.STOP_LOSS,
                quantity=100,
                stop_price=145.00,
                status=OrderStatus.PENDING,
                created_at=datetime.utcnow(),
            )

            execution_engine.add_trigger_order(timeout_order)

            # This should timeout and handle gracefully
            start_time = asyncio.get_event_loop().time()

            with pytest.raises(asyncio.TimeoutError):
                await asyncio.wait_for(
                    execution_engine._check_trigger_conditions("TIMEOUT", 140.00),
                    timeout=2.0,  # 2-second timeout
                )

            elapsed = asyncio.get_event_loop().time() - start_time
            assert elapsed < 3.0, "Timeout should be enforced"

        finally:
            await execution_engine.stop()

    @pytest.mark.asyncio
    async def test_stale_data_handling(self):
        """Test handling of stale market data."""
        mock_service = AsyncMock()

        # Return stale quote (old timestamp)
        stale_quote = Mock(
            price=150.00,
            timestamp=datetime.utcnow() - timedelta(minutes=10),  # 10 minutes old
            is_stale=True,
        )

        mock_service.get_current_quote = AsyncMock(return_value=stale_quote)
        mock_service.execute_order = AsyncMock()

        execution_engine = OrderExecutionEngine(mock_service)
        await execution_engine.start()

        try:
            stale_order = Order(
                id="stale_test_1",
                symbol="STALE",
                order_type=OrderType.TRAILING_STOP,
                quantity=150,
                trail_percent=3.0,
                stop_price=145.00,
                status=OrderStatus.PENDING,
                created_at=datetime.utcnow(),
            )

            execution_engine.add_trigger_order(stale_order)

            # Should reject stale data
            with patch.object(execution_engine, "_is_quote_stale", return_value=True):
                await execution_engine._check_trigger_conditions("STALE", 140.00)

                # Should not execute with stale data
                mock_service.execute_order.assert_not_called()

        finally:
            await execution_engine.stop()

    @pytest.mark.asyncio
    async def test_data_feed_recovery(self):
        """Test recovery from data feed failures."""
        mock_service = AsyncMock()

        # Simulate intermittent failures
        call_count = 0

        async def unreliable_quote(symbol):
            nonlocal call_count
            call_count += 1

            if call_count <= 3:
                raise ConnectionError("Data feed unavailable")
            else:
                return Mock(price=150.00, timestamp=datetime.utcnow())

        mock_service.get_current_quote = unreliable_quote
        mock_service.execute_order = AsyncMock()

        execution_engine = OrderExecutionEngine(mock_service)
        await execution_engine.start()

        try:
            recovery_order = Order(
                id="recovery_feed_1",
                symbol="RECOVER",
                order_type=OrderType.STOP_LOSS,
                quantity=100,
                stop_price=145.00,
                status=OrderStatus.PENDING,
                created_at=datetime.utcnow(),
            )

            execution_engine.add_trigger_order(recovery_order)

            # Multiple attempts should eventually succeed
            for _attempt in range(5):
                try:
                    await execution_engine._check_trigger_conditions("RECOVER", 140.00)
                    break
                except ConnectionError:
                    await asyncio.sleep(0.1)
                    continue

            # Should have recovered and executed
            assert call_count > 3, "Should have retried after failures"

        finally:
            await execution_engine.stop()


class TestExtremeMarketConditions:
    """Test system behavior under extreme market conditions."""

    @pytest.mark.asyncio
    async def test_flash_crash_scenario(self):
        """Test handling of flash crash conditions."""
        market_simulator = MarketImpactSimulator()

        # Simulate flash crash order in illiquid market
        flash_crash_order = Order(
            id="flash_crash_1",
            symbol="FLASHCRASH",
            order_type=OrderType.SELL,
            quantity=10000,  # Large order
            status=OrderStatus.PENDING,
            created_at=datetime.utcnow(),
        )

        # Very low liquidity during flash crash
        low_volume = 50000  # Low daily volume
        crash_price = 50.00  # Significantly below normal

        result = market_simulator.simulate_market_impact(
            flash_crash_order, crash_price, low_volume
        )

        # Should have significant slippage and partial fills
        assert result.average_price < crash_price  # Adverse slippage
        assert result.filled_quantity < flash_crash_order.quantity  # Partial fill
        assert not result.is_complete, "Large order should not fill completely in crash"

    @pytest.mark.asyncio
    async def test_high_volatility_conditions(self):
        """Test system behavior during high volatility."""
        AsyncMock()
        state_tracker = MemoryEfficientOrderTracker()

        await state_tracker.start()

        try:
            # Rapid price movements
            volatile_prices = [100.0, 105.0, 95.0, 110.0, 85.0, 102.0]

            volatility_order = Order(
                id="volatility_1",
                symbol="VOLATILE",
                order_type=OrderType.TRAILING_STOP,
                quantity=500,
                trail_percent=8.0,  # Wide trail for volatility
                stop_price=92.00,
                status=OrderStatus.PENDING,
                created_at=datetime.utcnow(),
            )

            state_tracker.track_state_change(
                volatility_order.id, OrderStatus.PENDING, StateChangeEvent.CREATED
            )

            # Simulate multiple rapid price updates
            for i, price in enumerate(volatile_prices):
                state_tracker.track_state_change(
                    volatility_order.id,
                    OrderStatus.PENDING,
                    StateChangeEvent.CREATED,  # Price update event
                    metadata={"price_update": price, "sequence": i},
                )

                await asyncio.sleep(0.01)  # Rapid updates

            # Verify all price updates were tracked
            history = state_tracker.get_order_history(volatility_order.id)
            price_updates = [
                h.metadata.get("price_update")
                for h in history
                if h.metadata and "price_update" in h.metadata
            ]

            assert len(price_updates) == len(volatile_prices)
            assert max(price_updates) == 110.0
            assert min(price_updates) == 85.0

        finally:
            await state_tracker.stop()

    @pytest.mark.asyncio
    async def test_market_maker_absence(self):
        """Test handling when market makers are absent."""
        market_simulator = MarketImpactSimulator()

        # Order in stock with no market makers (very wide spread)
        no_mm_order = Order(
            id="no_mm_1",
            symbol="NOMM",
            order_type=OrderType.LIMIT,
            quantity=100,
            price=100.00,
            status=OrderStatus.PENDING,
            created_at=datetime.utcnow(),
        )

        # Simulate very wide spread (no market makers)
        market_price = 100.00
        very_low_volume = 1000  # Minimal volume

        result = market_simulator.simulate_market_impact(
            no_mm_order, market_price, very_low_volume
        )

        # Should have difficulty filling
        assert result.filled_quantity <= no_mm_order.quantity

        # May not fill at all due to wide spreads
        if result.filled_quantity > 0:
            # If it fills, should be at a poor price
            assert abs(result.average_price - no_mm_order.price) >= 0.5


class TestSystemRecoveryScenarios:
    """Test system recovery from various failure modes."""

    @pytest.mark.asyncio
    async def test_graceful_degradation(self):
        """Test graceful degradation when services fail."""
        # Mock service that fails gradually
        mock_service = AsyncMock()
        failure_count = 0

        async def degrading_service(symbol):
            nonlocal failure_count
            failure_count += 1

            if failure_count <= 2:
                return Mock(price=150.00)  # Normal
            elif failure_count <= 4:
                await asyncio.sleep(1.0)  # Slow response
                return Mock(price=150.00)
            else:
                raise TimeoutError("Service unavailable")

        mock_service.get_current_quote = degrading_service
        mock_service.execute_order = AsyncMock()

        execution_engine = OrderExecutionEngine(mock_service)
        await execution_engine.start()

        try:
            degradation_order = Order(
                id="degradation_1",
                symbol="DEGRADE",
                order_type=OrderType.STOP_LOSS,
                quantity=100,
                stop_price=145.00,
                status=OrderStatus.PENDING,
                created_at=datetime.utcnow(),
            )

            execution_engine.add_trigger_order(degradation_order)

            # Multiple checks should show degrading performance
            response_times = []

            for _ in range(6):
                start_time = asyncio.get_event_loop().time()
                try:
                    await execution_engine._check_trigger_conditions("DEGRADE", 140.00)
                except Exception:
                    pass  # Expected failures

                response_time = asyncio.get_event_loop().time() - start_time
                response_times.append(response_time)
                await asyncio.sleep(0.1)

            # Should show increasing response times, then failures
            assert len(response_times) == 6
            # Early responses should be faster than later ones
            assert response_times[0] < response_times[2]

        finally:
            await execution_engine.stop()

    @pytest.mark.asyncio
    async def test_memory_pressure_recovery(self):
        """Test system behavior under memory pressure."""
        config = OrderStateTrackingConfig(
            max_snapshots_per_order=5,  # Very low limit
            max_total_snapshots=50,  # Force frequent cleanup
            max_history_days=1,
            cleanup_interval_minutes=1,
        )

        state_tracker = MemoryEfficientOrderTracker(config)
        await state_tracker.start()

        try:
            # Create memory pressure by adding many orders
            order_count = 100

            for i in range(order_count):
                order_id = f"memory_pressure_{i}"

                # Add multiple state changes per order
                for j in range(10):  # Exceeds max_snapshots_per_order
                    state_tracker.track_state_change(
                        order_id,
                        OrderStatus.PENDING,
                        StateChangeEvent.CREATED,
                        metadata={"iteration": j},
                    )

            # Force cleanup under pressure
            cleanup_results = state_tracker.cleanup_old_data(force=True)

            # Verify cleanup occurred
            assert cleanup_results["snapshots_removed"] > 0

            # System should still be responsive
            metrics = state_tracker.get_performance_metrics()
            assert metrics["total_snapshots"] <= config.max_total_snapshots

            # Add new order to verify system still works
            state_tracker.track_state_change(
                "post_cleanup_test", OrderStatus.FILLED, StateChangeEvent.FILLED
            )

            final_state = state_tracker.get_current_state("post_cleanup_test")
            assert final_state is not None
            assert final_state.status == OrderStatus.FILLED

        finally:
            await state_tracker.stop()


@contextmanager
def simulate_market_conditions(condition: str):
    """Context manager to simulate various market conditions."""
    if condition == "closed":
        with patch("datetime.datetime") as mock_dt:
            # Saturday
            mock_dt.now.return_value = datetime(2024, 3, 16, 10, 0, 0)
            yield
    elif condition == "holiday":
        with patch("datetime.date") as mock_date:
            # Christmas Day
            mock_date.today.return_value = date(2024, 12, 25)
            yield
    elif condition == "halt":
        with patch(
            "app.services.order_execution_engine.OrderExecutionEngine._is_stock_halted"
        ) as mock_halt:
            mock_halt.return_value = True
            yield
    else:
        yield


if __name__ == "__main__":
    pytest.main([__file__, "-v", "-s"])
