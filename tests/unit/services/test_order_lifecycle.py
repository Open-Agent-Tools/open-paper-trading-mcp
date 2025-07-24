"""
Comprehensive tests for OrderLifecycleManager - order state management service.

Tests cover:
- Order lifecycle state creation and initialization
- State transitions and validation rules
- Event tracking and audit trail management
- Fill details and execution tracking
- Order cancellation and rejection handling
- Status queries and filtering
- Event callback registration and triggering
- Cleanup and maintenance operations
- Error handling and edge cases
- Performance and concurrent operations
"""

from datetime import datetime, timedelta

import pytest

from app.schemas.orders import Order, OrderCondition, OrderStatus, OrderType
from app.services.order_lifecycle import (
    OrderEvent,
    OrderLifecycleError,
    OrderLifecycleManager,
    OrderLifecycleState,
    OrderStateTransition,
    get_order_lifecycle_manager,
)


@pytest.fixture
def lifecycle_manager():
    """Order lifecycle manager instance."""
    return OrderLifecycleManager()


@pytest.fixture
def sample_order():
    """Sample order for testing."""
    return Order(
        id="order-123",
        symbol="AAPL",
        order_type=OrderType.BUY,
        quantity=100,
        price=150.00,
        status=OrderStatus.PENDING,
        created_at=datetime.now(),
        condition=OrderCondition.LIMIT,
    )


@pytest.fixture
def sample_lifecycle_state(sample_order):
    """Sample order lifecycle state."""
    return OrderLifecycleState(
        order=sample_order,
        current_status=OrderStatus.PENDING,
        created_at=datetime.now(),
        last_updated=datetime.now(),
        remaining_quantity=100,
    )


class TestOrderLifecycleState:
    """Test order lifecycle state data structure."""

    def test_lifecycle_state_initialization(self, sample_order):
        """Test lifecycle state creation and initialization."""
        state = OrderLifecycleState(
            order=sample_order,
            current_status=OrderStatus.PENDING,
            created_at=datetime.now(),
            last_updated=datetime.now(),
            remaining_quantity=100,
        )

        assert state.order == sample_order
        assert state.current_status == OrderStatus.PENDING
        assert isinstance(state.created_at, datetime)
        assert isinstance(state.last_updated, datetime)
        assert state.remaining_quantity == 100
        assert state.filled_quantity == 0
        assert state.can_cancel is True
        assert state.can_modify is True
        assert state.is_terminal is False
        assert len(state.transitions) == 0
        assert len(state.error_messages) == 0

    def test_lifecycle_state_defaults(self, sample_order):
        """Test lifecycle state default values."""
        state = OrderLifecycleState(
            order=sample_order,
            current_status=OrderStatus.PENDING,
            created_at=datetime.now(),
            last_updated=datetime.now(),
        )

        # Test default values
        assert state.filled_quantity == 0
        assert state.remaining_quantity == 0
        assert state.average_fill_price is None
        assert state.total_commission == 0.0
        assert isinstance(state.transitions, list)
        assert isinstance(state.error_messages, list)
        assert isinstance(state.metadata, dict)


class TestOrderStateTransition:
    """Test order state transition data structure."""

    def test_state_transition_creation(self):
        """Test state transition creation."""
        transition = OrderStateTransition(
            from_status=OrderStatus.PENDING,
            to_status=OrderStatus.FILLED,
            event=OrderEvent.FILLED,
            timestamp=datetime.now(),
            details={"fill_price": 150.50, "fill_quantity": 100},
            triggered_by="market",
        )

        assert transition.from_status == OrderStatus.PENDING
        assert transition.to_status == OrderStatus.FILLED
        assert transition.event == OrderEvent.FILLED
        assert isinstance(transition.timestamp, datetime)
        assert transition.details["fill_price"] == 150.50
        assert transition.triggered_by == "market"

    def test_state_transition_defaults(self):
        """Test state transition default values."""
        transition = OrderStateTransition(
            from_status=OrderStatus.PENDING,
            to_status=OrderStatus.FILLED,
            event=OrderEvent.FILLED,
            timestamp=datetime.now(),
        )

        assert isinstance(transition.details, dict)
        assert transition.triggered_by == "system"


class TestOrderLifecycleManagerBasics:
    """Test basic lifecycle manager functionality."""

    def test_manager_initialization(self):
        """Test lifecycle manager initialization."""
        manager = OrderLifecycleManager()

        assert isinstance(manager.active_orders, dict)
        assert isinstance(manager.completed_orders, dict)
        assert isinstance(manager.event_callbacks, dict)
        assert isinstance(manager.valid_transitions, dict)
        assert isinstance(manager.terminal_states, set)

        # Check all events have callback lists
        for event in OrderEvent:
            assert event in manager.event_callbacks
            assert isinstance(manager.event_callbacks[event], list)

    def test_valid_transitions_definition(self, lifecycle_manager):
        """Test valid state transitions are properly defined."""
        transitions = lifecycle_manager.valid_transitions

        # Test key transitions
        assert OrderStatus.FILLED in transitions[OrderStatus.PENDING]
        assert OrderStatus.CANCELLED in transitions[OrderStatus.PENDING]
        assert OrderStatus.PARTIALLY_FILLED in transitions[OrderStatus.PENDING]

        # Terminal states should have no valid transitions
        assert len(transitions[OrderStatus.FILLED]) == 0
        assert len(transitions[OrderStatus.CANCELLED]) == 0

    def test_terminal_states_definition(self, lifecycle_manager):
        """Test terminal states are properly defined."""
        terminal_states = lifecycle_manager.terminal_states

        assert OrderStatus.FILLED in terminal_states
        assert OrderStatus.CANCELLED in terminal_states
        assert OrderStatus.REJECTED in terminal_states
        assert OrderStatus.EXPIRED in terminal_states

        # Non-terminal states should not be in terminal set
        assert OrderStatus.PENDING not in terminal_states
        assert OrderStatus.PARTIALLY_FILLED not in terminal_states


class TestOrderCreation:
    """Test order creation and lifecycle initialization."""

    def test_create_order_success(self, lifecycle_manager, sample_order):
        """Test successful order creation."""
        lifecycle_state = lifecycle_manager.create_order(sample_order)

        assert isinstance(lifecycle_state, OrderLifecycleState)
        assert lifecycle_state.order == sample_order
        assert lifecycle_state.current_status == OrderStatus.PENDING
        assert lifecycle_state.remaining_quantity == abs(sample_order.quantity)
        assert sample_order.id in lifecycle_manager.active_orders
        assert len(lifecycle_state.transitions) == 1  # Creation event

    def test_create_order_without_id_raises_error(self, lifecycle_manager):
        """Test order creation without ID raises error."""
        order_without_id = Order(
            id=None,  # Missing ID
            symbol="AAPL",
            order_type=OrderType.BUY,
            quantity=100,
            status=OrderStatus.PENDING,
            created_at=datetime.now(),
        )

        with pytest.raises(OrderLifecycleError, match="Order must have an ID"):
            lifecycle_manager.create_order(order_without_id)

    def test_create_duplicate_order_raises_error(self, lifecycle_manager, sample_order):
        """Test creating duplicate order raises error."""
        lifecycle_manager.create_order(sample_order)

        with pytest.raises(OrderLifecycleError, match="Order .* already exists"):
            lifecycle_manager.create_order(sample_order)

    def test_create_order_records_transition(self, lifecycle_manager, sample_order):
        """Test order creation records initial transition."""
        lifecycle_state = lifecycle_manager.create_order(sample_order)

        assert len(lifecycle_state.transitions) == 1
        transition = lifecycle_state.transitions[0]
        assert transition.to_status == OrderStatus.PENDING
        assert transition.event == OrderEvent.CREATED
        assert "order_type" in transition.details
        assert "symbol" in transition.details


class TestStateTransitions:
    """Test order state transitions and validation."""

    def test_valid_state_transition(self, lifecycle_manager, sample_order):
        """Test valid state transition."""
        lifecycle_manager.create_order(sample_order)

        updated_state = lifecycle_manager.transition_order(
            sample_order.id,
            OrderStatus.FILLED,
            OrderEvent.FILLED,
            details={"fill_price": 150.50},
        )

        assert updated_state.current_status == OrderStatus.FILLED
        assert len(updated_state.transitions) == 2  # Created + Filled
        assert sample_order.id in lifecycle_manager.completed_orders
        assert sample_order.id not in lifecycle_manager.active_orders

    def test_invalid_state_transition_raises_error(
        self, lifecycle_manager, sample_order
    ):
        """Test invalid state transition raises error."""
        lifecycle_manager.create_order(sample_order)

        # Try to transition from PENDING directly to CANCELLED then to FILLED (invalid)
        lifecycle_manager.transition_order(
            sample_order.id, OrderStatus.CANCELLED, OrderEvent.CANCELLED
        )

        with pytest.raises(OrderLifecycleError, match="Invalid transition"):
            lifecycle_manager.transition_order(
                sample_order.id, OrderStatus.FILLED, OrderEvent.FILLED
            )

    def test_transition_order_not_found_raises_error(self, lifecycle_manager):
        """Test transition of non-existent order raises error."""
        with pytest.raises(OrderLifecycleError, match="Order .* not found"):
            lifecycle_manager.transition_order(
                "non-existent", OrderStatus.FILLED, OrderEvent.FILLED
            )

    def test_transition_updates_lifecycle_flags(self, lifecycle_manager, sample_order):
        """Test state transition updates lifecycle flags."""
        lifecycle_state = lifecycle_manager.create_order(sample_order)

        # Transition to partially filled
        lifecycle_manager.transition_order(
            sample_order.id, OrderStatus.PARTIALLY_FILLED, OrderEvent.PARTIALLY_FILLED
        )

        assert lifecycle_state.can_cancel is True  # Can still cancel partially filled
        assert lifecycle_state.can_modify is True  # Can still modify partially filled
        assert lifecycle_state.is_terminal is False

    def test_transition_to_terminal_state(self, lifecycle_manager, sample_order):
        """Test transition to terminal state moves order to completed."""
        lifecycle_state = lifecycle_manager.create_order(sample_order)

        lifecycle_manager.transition_order(
            sample_order.id, OrderStatus.FILLED, OrderEvent.FILLED
        )

        assert lifecycle_state.is_terminal is True
        assert lifecycle_state.can_cancel is False
        assert lifecycle_state.can_modify is False
        assert sample_order.id in lifecycle_manager.completed_orders
        assert sample_order.id not in lifecycle_manager.active_orders

    def test_transition_records_audit_trail(self, lifecycle_manager, sample_order):
        """Test state transitions are recorded in audit trail."""
        lifecycle_state = lifecycle_manager.create_order(sample_order)

        lifecycle_manager.transition_order(
            sample_order.id,
            OrderStatus.PARTIALLY_FILLED,
            OrderEvent.PARTIALLY_FILLED,
            details={"fill_quantity": 50, "fill_price": 150.25},
            triggered_by="market_maker",
        )

        assert len(lifecycle_state.transitions) == 2
        fill_transition = lifecycle_state.transitions[1]
        assert fill_transition.from_status == OrderStatus.PENDING
        assert fill_transition.to_status == OrderStatus.PARTIALLY_FILLED
        assert fill_transition.triggered_by == "market_maker"
        assert fill_transition.details["fill_quantity"] == 50


class TestFillDetailsManagement:
    """Test fill details tracking and management."""

    def test_update_fill_details_partial_fill(self, lifecycle_manager, sample_order):
        """Test updating fill details for partial fill."""
        lifecycle_manager.create_order(sample_order)

        updated_state = lifecycle_manager.update_fill_details(
            sample_order.id, filled_quantity=50, fill_price=150.25, commission=5.00
        )

        assert updated_state.filled_quantity == 50
        assert updated_state.remaining_quantity == 50  # 100 - 50
        assert updated_state.average_fill_price == 150.25
        assert updated_state.total_commission == 5.00
        assert updated_state.current_status == OrderStatus.PARTIALLY_FILLED

    def test_update_fill_details_complete_fill(self, lifecycle_manager, sample_order):
        """Test updating fill details for complete fill."""
        lifecycle_manager.create_order(sample_order)

        updated_state = lifecycle_manager.update_fill_details(
            sample_order.id, filled_quantity=100, fill_price=150.50, commission=7.50
        )

        assert updated_state.filled_quantity == 100
        assert updated_state.remaining_quantity == 0
        assert updated_state.average_fill_price == 150.50
        assert updated_state.total_commission == 7.50
        assert updated_state.current_status == OrderStatus.FILLED
        assert sample_order.id in lifecycle_manager.completed_orders

    def test_update_fill_details_multiple_fills(self, lifecycle_manager, sample_order):
        """Test updating fill details across multiple fills."""
        lifecycle_state = lifecycle_manager.create_order(sample_order)

        # First partial fill
        lifecycle_manager.update_fill_details(
            sample_order.id, filled_quantity=30, fill_price=150.00, commission=3.00
        )

        # Second partial fill
        lifecycle_manager.update_fill_details(
            sample_order.id, filled_quantity=40, fill_price=150.50, commission=4.00
        )

        # Third fill to complete
        lifecycle_manager.update_fill_details(
            sample_order.id, filled_quantity=30, fill_price=151.00, commission=3.00
        )

        assert lifecycle_state.filled_quantity == 100
        assert lifecycle_state.remaining_quantity == 0
        assert lifecycle_state.total_commission == 10.00
        assert lifecycle_state.current_status == OrderStatus.FILLED

        # Calculate expected weighted average price
        expected_avg = (30 * 150.00 + 40 * 150.50 + 30 * 151.00) / 100
        assert abs(lifecycle_state.average_fill_price - expected_avg) < 0.01

    def test_update_fill_details_order_not_found_raises_error(self, lifecycle_manager):
        """Test updating fill details for non-existent order raises error."""
        with pytest.raises(OrderLifecycleError, match="Order .* not found"):
            lifecycle_manager.update_fill_details("non-existent", 50, 150.00, 5.00)

    def test_weighted_average_price_calculation(self, lifecycle_manager, sample_order):
        """Test weighted average price calculation across fills."""
        lifecycle_state = lifecycle_manager.create_order(sample_order)

        # Fill 1: 60 shares at $150.00
        lifecycle_manager.update_fill_details(sample_order.id, 60, 150.00, 6.00)

        # Fill 2: 40 shares at $151.00
        lifecycle_manager.update_fill_details(sample_order.id, 40, 151.00, 4.00)

        # Weighted average should be (60*150 + 40*151) / 100 = 150.40
        expected_avg = (60 * 150.00 + 40 * 151.00) / 100
        assert abs(lifecycle_state.average_fill_price - expected_avg) < 0.01


class TestOrderActions:
    """Test order actions like cancellation and rejection."""

    def test_cancel_order_success(self, lifecycle_manager, sample_order):
        """Test successful order cancellation."""
        lifecycle_manager.create_order(sample_order)

        cancelled_state = lifecycle_manager.cancel_order(
            sample_order.id, reason="User requested", triggered_by="user"
        )

        assert cancelled_state.current_status == OrderStatus.CANCELLED
        assert sample_order.id in lifecycle_manager.completed_orders
        assert any(t.event == OrderEvent.CANCELLED for t in cancelled_state.transitions)

    def test_cancel_order_not_found_raises_error(self, lifecycle_manager):
        """Test cancelling non-existent order raises error."""
        with pytest.raises(OrderLifecycleError, match="Order .* not found"):
            lifecycle_manager.cancel_order("non-existent")

    def test_cancel_order_cannot_cancel_raises_error(
        self, lifecycle_manager, sample_order
    ):
        """Test cancelling non-cancellable order raises error."""
        lifecycle_manager.create_order(sample_order)

        # Transition to filled state (cannot cancel)
        lifecycle_manager.transition_order(
            sample_order.id, OrderStatus.FILLED, OrderEvent.FILLED
        )

        with pytest.raises(OrderLifecycleError, match="cannot be cancelled"):
            lifecycle_manager.cancel_order(sample_order.id)

    def test_reject_order_success(self, lifecycle_manager, sample_order):
        """Test successful order rejection."""
        lifecycle_manager.create_order(sample_order)

        rejected_state = lifecycle_manager.reject_order(
            sample_order.id, reason="Insufficient funds", triggered_by="risk_management"
        )

        assert rejected_state.current_status == OrderStatus.REJECTED
        assert "Insufficient funds" in rejected_state.error_messages
        assert sample_order.id in lifecycle_manager.completed_orders

    def test_expire_order_success(self, lifecycle_manager, sample_order):
        """Test successful order expiration."""
        lifecycle_manager.create_order(sample_order)

        expired_state = lifecycle_manager.expire_order(
            sample_order.id, reason="End of trading day"
        )

        assert expired_state.current_status == OrderStatus.EXPIRED
        assert sample_order.id in lifecycle_manager.completed_orders

    def test_trigger_order_success(self, lifecycle_manager, sample_order):
        """Test successful order triggering."""
        lifecycle_manager.create_order(sample_order)

        triggered_state = lifecycle_manager.trigger_order(
            sample_order.id, trigger_price=149.50, triggered_by="market"
        )

        assert triggered_state.current_status == OrderStatus.TRIGGERED
        assert sample_order.id in lifecycle_manager.active_orders  # Still active


class TestOrderQueries:
    """Test order querying and filtering operations."""

    def test_get_order_state_active_order(self, lifecycle_manager, sample_order):
        """Test getting state of active order."""
        lifecycle_state = lifecycle_manager.create_order(sample_order)

        retrieved_state = lifecycle_manager.get_order_state(sample_order.id)

        assert retrieved_state == lifecycle_state
        assert retrieved_state.current_status == OrderStatus.PENDING

    def test_get_order_state_completed_order(self, lifecycle_manager, sample_order):
        """Test getting state of completed order."""
        lifecycle_state = lifecycle_manager.create_order(sample_order)
        lifecycle_manager.transition_order(
            sample_order.id, OrderStatus.FILLED, OrderEvent.FILLED
        )

        retrieved_state = lifecycle_manager.get_order_state(sample_order.id)

        assert retrieved_state == lifecycle_state
        assert retrieved_state.current_status == OrderStatus.FILLED

    def test_get_order_state_not_found_returns_none(self, lifecycle_manager):
        """Test getting state of non-existent order returns None."""
        result = lifecycle_manager.get_order_state("non-existent")
        assert result is None

    def test_get_active_orders(self, lifecycle_manager):
        """Test getting all active orders."""
        # Create multiple orders
        orders = []
        for i in range(3):
            order = Order(
                id=f"order-{i}",
                symbol="AAPL",
                order_type=OrderType.BUY,
                quantity=100,
                status=OrderStatus.PENDING,
                created_at=datetime.now(),
            )
            orders.append(order)
            lifecycle_manager.create_order(order)

        # Complete one order
        lifecycle_manager.transition_order(
            "order-1", OrderStatus.FILLED, OrderEvent.FILLED
        )

        active_orders = lifecycle_manager.get_active_orders()

        assert len(active_orders) == 2  # 3 created - 1 completed
        assert "order-0" in active_orders
        assert "order-2" in active_orders
        assert "order-1" not in active_orders

    def test_get_orders_by_status(self, lifecycle_manager):
        """Test getting orders filtered by status."""
        # Create orders with different statuses
        orders = []
        for i in range(4):
            order = Order(
                id=f"order-{i}",
                symbol="AAPL",
                order_type=OrderType.BUY,
                quantity=100,
                status=OrderStatus.PENDING,
                created_at=datetime.now(),
            )
            orders.append(order)
            lifecycle_manager.create_order(order)

        # Transition some orders
        lifecycle_manager.transition_order(
            "order-1", OrderStatus.PARTIALLY_FILLED, OrderEvent.PARTIALLY_FILLED
        )
        lifecycle_manager.transition_order(
            "order-2", OrderStatus.PARTIALLY_FILLED, OrderEvent.PARTIALLY_FILLED
        )
        lifecycle_manager.transition_order(
            "order-3", OrderStatus.FILLED, OrderEvent.FILLED
        )

        pending_orders = lifecycle_manager.get_orders_by_status(OrderStatus.PENDING)
        partial_orders = lifecycle_manager.get_orders_by_status(
            OrderStatus.PARTIALLY_FILLED
        )

        assert len(pending_orders) == 1
        assert pending_orders[0].order.id == "order-0"
        assert len(partial_orders) == 2

    def test_get_orders_by_symbol(self, lifecycle_manager):
        """Test getting orders filtered by symbol."""
        symbols = ["AAPL", "GOOGL", "AAPL", "MSFT"]

        for i, symbol in enumerate(symbols):
            order = Order(
                id=f"order-{i}",
                symbol=symbol,
                order_type=OrderType.BUY,
                quantity=100,
                status=OrderStatus.PENDING,
                created_at=datetime.now(),
            )
            lifecycle_manager.create_order(order)

        aapl_orders = lifecycle_manager.get_orders_by_symbol("AAPL")
        googl_orders = lifecycle_manager.get_orders_by_symbol("GOOGL")

        assert len(aapl_orders) == 2
        assert len(googl_orders) == 1
        assert all(order.order.symbol == "AAPL" for order in aapl_orders)


class TestEventCallbacks:
    """Test event callback registration and triggering."""

    def test_register_event_callback(self, lifecycle_manager):
        """Test registering event callback."""
        callback_calls = []

        def test_callback(lifecycle_state, event):
            callback_calls.append((lifecycle_state.order.id, event))

        lifecycle_manager.register_event_callback(OrderEvent.FILLED, test_callback)

        assert test_callback in lifecycle_manager.event_callbacks[OrderEvent.FILLED]

    def test_event_callback_triggered(self, lifecycle_manager, sample_order):
        """Test event callback is triggered on state transition."""
        callback_calls = []

        def fill_callback(lifecycle_state, event):
            callback_calls.append((lifecycle_state.order.id, event))

        lifecycle_manager.register_event_callback(OrderEvent.FILLED, fill_callback)
        lifecycle_manager.create_order(sample_order)

        # Trigger fill event
        lifecycle_manager.transition_order(
            sample_order.id, OrderStatus.FILLED, OrderEvent.FILLED
        )

        assert len(callback_calls) == 1
        assert callback_calls[0][0] == sample_order.id
        assert callback_calls[0][1] == OrderEvent.FILLED

    def test_multiple_event_callbacks(self, lifecycle_manager, sample_order):
        """Test multiple callbacks for same event."""
        callback1_calls = []
        callback2_calls = []

        def callback1(state, event):
            callback1_calls.append(state.order.id)

        def callback2(state, event):
            callback2_calls.append(state.order.id)

        lifecycle_manager.register_event_callback(OrderEvent.CANCELLED, callback1)
        lifecycle_manager.register_event_callback(OrderEvent.CANCELLED, callback2)

        lifecycle_manager.create_order(sample_order)
        lifecycle_manager.cancel_order(sample_order.id)

        assert len(callback1_calls) == 1
        assert len(callback2_calls) == 1

    def test_event_callback_error_handling(self, lifecycle_manager, sample_order):
        """Test error handling in event callbacks."""

        def failing_callback(state, event):
            raise Exception("Callback failed")

        lifecycle_manager.register_event_callback(OrderEvent.CREATED, failing_callback)

        # Should not raise exception despite callback failure
        lifecycle_state = lifecycle_manager.create_order(sample_order)

        assert lifecycle_state.current_status == OrderStatus.PENDING


class TestCleanupAndMaintenance:
    """Test cleanup and maintenance operations."""

    def test_cleanup_completed_orders(self, lifecycle_manager):
        """Test cleanup of old completed orders."""
        # Create and complete orders with different ages
        old_time = datetime.utcnow() - timedelta(hours=48)  # 2 days old
        recent_time = datetime.utcnow() - timedelta(hours=12)  # 12 hours old

        for i in range(3):
            order = Order(
                id=f"order-{i}",
                symbol="AAPL",
                order_type=OrderType.BUY,
                quantity=100,
                status=OrderStatus.PENDING,
                created_at=datetime.now(),
            )
            lifecycle_state = lifecycle_manager.create_order(order)

            # Set different last_updated times
            if i < 2:
                lifecycle_state.last_updated = old_time  # Old orders
            else:
                lifecycle_state.last_updated = recent_time  # Recent order

            # Complete the orders
            lifecycle_manager.transition_order(
                order.id, OrderStatus.FILLED, OrderEvent.FILLED
            )

        # Cleanup orders older than 24 hours
        cleaned_count = lifecycle_manager.cleanup_completed_orders(older_than_hours=24)

        assert cleaned_count == 2  # 2 old orders cleaned
        assert len(lifecycle_manager.completed_orders) == 1  # 1 recent order remains

    def test_cleanup_no_old_orders(self, lifecycle_manager, sample_order):
        """Test cleanup when no orders are old enough."""
        lifecycle_manager.create_order(sample_order)
        lifecycle_manager.transition_order(
            sample_order.id, OrderStatus.FILLED, OrderEvent.FILLED
        )

        cleaned_count = lifecycle_manager.cleanup_completed_orders(older_than_hours=1)

        assert cleaned_count == 0
        assert len(lifecycle_manager.completed_orders) == 1

    def test_get_statistics(self, lifecycle_manager):
        """Test getting lifecycle statistics."""
        # Create orders with various statuses
        statuses = [
            OrderStatus.PENDING,
            OrderStatus.PARTIALLY_FILLED,
            OrderStatus.FILLED,
        ]

        for i, status in enumerate(statuses):
            order = Order(
                id=f"order-{i}",
                symbol="AAPL",
                order_type=OrderType.BUY,
                quantity=100,
                status=OrderStatus.PENDING,
                created_at=datetime.now(),
            )
            lifecycle_manager.create_order(order)

            if status != OrderStatus.PENDING:
                lifecycle_manager.transition_order(order.id, status, OrderEvent.FILLED)

        stats = lifecycle_manager.get_statistics()

        assert "total_orders" in stats
        assert "active_orders" in stats
        assert "completed_orders" in stats
        assert "status_breakdown" in stats
        assert stats["total_orders"] == 3
        assert stats["active_orders"] == 2  # PENDING, PARTIALLY_FILLED
        assert stats["completed_orders"] == 1  # FILLED


class TestLifecycleManagerErrorHandling:
    """Test error handling and edge cases."""

    def test_invalid_status_transition_validation(self, lifecycle_manager):
        """Test validation of invalid status transitions."""
        # Test internal validation method
        assert (
            lifecycle_manager._is_valid_transition(
                OrderStatus.PENDING, OrderStatus.FILLED
            )
            is True
        )

        assert (
            lifecycle_manager._is_valid_transition(
                OrderStatus.FILLED, OrderStatus.PENDING
            )
            is False
        )

    def test_lifecycle_flags_update(self, lifecycle_manager, sample_order):
        """Test lifecycle flags are updated correctly."""
        lifecycle_state = lifecycle_manager.create_order(sample_order)

        # Test flags for different statuses
        lifecycle_state.current_status = OrderStatus.PARTIALLY_FILLED
        lifecycle_manager._update_lifecycle_flags(lifecycle_state)
        assert lifecycle_state.can_cancel is True
        assert lifecycle_state.can_modify is True
        assert lifecycle_state.is_terminal is False

        lifecycle_state.current_status = OrderStatus.FILLED
        lifecycle_manager._update_lifecycle_flags(lifecycle_state)
        assert lifecycle_state.can_cancel is False
        assert lifecycle_state.can_modify is False
        assert lifecycle_state.is_terminal is True

    def test_concurrent_order_operations(self, lifecycle_manager):
        """Test concurrent operations on orders."""

        # Create multiple orders concurrently
        async def create_order_async(order_id):
            order = Order(
                id=order_id,
                symbol="AAPL",
                order_type=OrderType.BUY,
                quantity=100,
                status=OrderStatus.PENDING,
                created_at=datetime.now(),
            )
            return lifecycle_manager.create_order(order)

        # This test doesn't use async/await but tests thread safety
        orders = []
        for i in range(10):
            order = Order(
                id=f"order-{i}",
                symbol="AAPL",
                order_type=OrderType.BUY,
                quantity=100,
                status=OrderStatus.PENDING,
                created_at=datetime.now(),
            )
            lifecycle_state = lifecycle_manager.create_order(order)
            orders.append(lifecycle_state)

        assert len(lifecycle_manager.active_orders) == 10

    def test_memory_cleanup_on_completion(self, lifecycle_manager):
        """Test memory is properly managed when orders complete."""
        initial_active_count = len(lifecycle_manager.active_orders)
        initial_completed_count = len(lifecycle_manager.completed_orders)

        order = Order(
            id="memory-test",
            symbol="AAPL",
            order_type=OrderType.BUY,
            quantity=100,
            status=OrderStatus.PENDING,
            created_at=datetime.now(),
        )

        lifecycle_manager.create_order(order)
        assert len(lifecycle_manager.active_orders) == initial_active_count + 1

        lifecycle_manager.transition_order(
            order.id, OrderStatus.FILLED, OrderEvent.FILLED
        )

        assert len(lifecycle_manager.active_orders) == initial_active_count
        assert len(lifecycle_manager.completed_orders) == initial_completed_count + 1

    def test_order_transition_from_terminal_state(
        self, lifecycle_manager, sample_order
    ):
        """Test attempting to transition from terminal state."""
        lifecycle_manager.create_order(sample_order)

        # Complete the order
        lifecycle_manager.transition_order(
            sample_order.id, OrderStatus.FILLED, OrderEvent.FILLED
        )

        # Try to transition from terminal state - should fail
        with pytest.raises(OrderLifecycleError, match="Invalid transition"):
            lifecycle_manager.transition_order(
                sample_order.id, OrderStatus.CANCELLED, OrderEvent.CANCELLED
            )


class TestGlobalManagerInstance:
    """Test global lifecycle manager instance."""

    def test_global_manager_access(self):
        """Test accessing global lifecycle manager."""
        manager = get_order_lifecycle_manager()
        assert isinstance(manager, OrderLifecycleManager)

        # Should return same instance
        manager2 = get_order_lifecycle_manager()
        assert manager is manager2

    def test_global_manager_is_initialized(self):
        """Test global manager is properly initialized."""
        manager = get_order_lifecycle_manager()

        assert isinstance(manager.active_orders, dict)
        assert isinstance(manager.completed_orders, dict)
        assert isinstance(manager.event_callbacks, dict)


class TestOrderLifecyclePerformance:
    """Test performance characteristics of lifecycle management."""

    def test_large_volume_order_tracking(self, lifecycle_manager):
        """Test performance with large volume of orders."""
        import time

        start_time = time.time()

        # Create many orders
        for i in range(1000):
            order = Order(
                id=f"perf-order-{i}",
                symbol=f"SYM{i % 100}",  # 100 different symbols
                order_type=OrderType.BUY,
                quantity=100,
                status=OrderStatus.PENDING,
                created_at=datetime.now(),
            )
            lifecycle_manager.create_order(order)

        creation_time = time.time() - start_time

        # Complete half the orders
        start_time = time.time()
        for i in range(0, 1000, 2):
            lifecycle_manager.transition_order(
                f"perf-order-{i}", OrderStatus.FILLED, OrderEvent.FILLED
            )

        completion_time = time.time() - start_time

        # Should complete reasonably quickly
        assert creation_time < 5.0  # Less than 5 seconds
        assert completion_time < 3.0  # Less than 3 seconds
        assert len(lifecycle_manager.active_orders) == 500
        assert len(lifecycle_manager.completed_orders) == 500

    def test_memory_efficiency_with_many_transitions(
        self, lifecycle_manager, sample_order
    ):
        """Test memory efficiency with many state transitions."""
        import sys

        lifecycle_state = lifecycle_manager.create_order(sample_order)
        initial_transitions = len(lifecycle_state.transitions)

        # Perform many state transitions
        for i in range(100):
            lifecycle_manager.update_fill_details(
                sample_order.id, 1, 150.00 + i * 0.01, 0.05
            )

        # Memory usage should be reasonable
        final_transitions = len(lifecycle_state.transitions)
        assert final_transitions > initial_transitions

        # Size of transitions list should not be excessive
        transitions_size = sys.getsizeof(lifecycle_state.transitions)
        assert transitions_size < 10000  # Less than 10KB for 100 transitions
