"""
Unit tests for the OrderLifecycleManager class.

These tests verify that the order lifecycle manager correctly tracks order states,
enforces valid state transitions, and provides accurate order information.
"""

from datetime import datetime, timedelta
from unittest.mock import MagicMock

import pytest

from app.schemas.orders import Order, OrderStatus, OrderType
from app.services.order_lifecycle import (
    OrderEvent,
    OrderLifecycleError,
    OrderLifecycleManager,
)


@pytest.fixture
def sample_order():
    """Create a sample order for testing."""
    return Order(
        id="test-order-1",
        symbol="AAPL",
        order_type=OrderType.BUY,
        quantity=100,
        price=150.0,
        status=OrderStatus.PENDING,
        created_at=datetime.utcnow(),
    )


@pytest.fixture
def lifecycle_manager():
    """Create an OrderLifecycleManager instance for testing."""
    return OrderLifecycleManager()


class TestOrderLifecycleManager:
    """Tests for the OrderLifecycleManager class."""

    def test_init(self):
        """Test OrderLifecycleManager initialization."""
        manager = OrderLifecycleManager()

        assert isinstance(manager.active_orders, dict)
        assert isinstance(manager.completed_orders, dict)
        assert len(manager.active_orders) == 0
        assert len(manager.completed_orders) == 0
        assert isinstance(manager.event_callbacks, dict)
        assert isinstance(manager.valid_transitions, dict)
        assert isinstance(manager.terminal_states, set)

    def test_create_order(self, lifecycle_manager, sample_order):
        """Test creating an order."""
        # Create the order
        lifecycle_state = lifecycle_manager.create_order(sample_order)

        # Verify the order was created
        assert sample_order.id in lifecycle_manager.active_orders
        assert lifecycle_state.order == sample_order
        assert lifecycle_state.current_status == OrderStatus.PENDING
        assert lifecycle_state.created_at is not None
        assert lifecycle_state.last_updated is not None
        assert lifecycle_state.remaining_quantity == sample_order.quantity
        assert len(lifecycle_state.transitions) == 1
        assert lifecycle_state.transitions[0].event == OrderEvent.CREATED

    def test_create_order_duplicate(self, lifecycle_manager, sample_order):
        """Test creating a duplicate order."""
        # Create the order
        lifecycle_manager.create_order(sample_order)

        # Try to create it again - should raise an error
        with pytest.raises(OrderLifecycleError):
            lifecycle_manager.create_order(sample_order)

    def test_create_order_no_id(self, lifecycle_manager):
        """Test creating an order without an ID."""
        # Create an order without an ID
        order = Order(
            id="",  # Empty ID
            symbol="AAPL",
            order_type=OrderType.BUY,
            quantity=100,
            price=150.0,
            status=OrderStatus.PENDING,
            created_at=datetime.utcnow(),
        )

        # Try to create it - should raise an error
        with pytest.raises(OrderLifecycleError):
            lifecycle_manager.create_order(order)

    def test_transition_order(self, lifecycle_manager, sample_order):
        """Test transitioning an order to a new status."""
        # Create the order
        lifecycle_manager.create_order(sample_order)

        # Transition to FILLED
        lifecycle_state = lifecycle_manager.transition_order(
            sample_order.id,
            OrderStatus.FILLED,
            OrderEvent.FILLED,
            details={"fill_price": 150.0},
        )

        # Verify the transition
        assert lifecycle_state.current_status == OrderStatus.FILLED
        assert len(lifecycle_state.transitions) == 2
        assert lifecycle_state.transitions[1].from_status == OrderStatus.PENDING
        assert lifecycle_state.transitions[1].to_status == OrderStatus.FILLED
        assert lifecycle_state.transitions[1].event == OrderEvent.FILLED
        assert lifecycle_state.transitions[1].details == {"fill_price": 150.0}
        assert lifecycle_state.is_terminal is True

        # Verify the order was moved to completed_orders
        assert sample_order.id not in lifecycle_manager.active_orders
        assert sample_order.id in lifecycle_manager.completed_orders

    def test_transition_order_invalid(self, lifecycle_manager, sample_order):
        """Test transitioning an order with an invalid transition."""
        # Create the order
        lifecycle_manager.create_order(sample_order)

        # Transition to FILLED
        lifecycle_manager.transition_order(
            sample_order.id,
            OrderStatus.FILLED,
            OrderEvent.FILLED,
        )

        # Try to transition from FILLED to CANCELLED - should raise an error
        with pytest.raises(OrderLifecycleError):
            lifecycle_manager.transition_order(
                sample_order.id,
                OrderStatus.CANCELLED,
                OrderEvent.CANCELLED,
            )

    def test_transition_order_not_found(self, lifecycle_manager):
        """Test transitioning a non-existent order."""
        # Try to transition a non-existent order - should raise an error
        with pytest.raises(OrderLifecycleError):
            lifecycle_manager.transition_order(
                "non-existent-order",
                OrderStatus.FILLED,
                OrderEvent.FILLED,
            )

    def test_update_fill_details(self, lifecycle_manager, sample_order):
        """Test updating fill details."""
        # Create the order
        lifecycle_manager.create_order(sample_order)

        # Update fill details - partial fill
        lifecycle_state = lifecycle_manager.update_fill_details(
            sample_order.id,
            filled_quantity=50,
            fill_price=150.0,
            commission=5.0,
        )

        # Verify the update
        assert lifecycle_state.filled_quantity == 50
        assert lifecycle_state.remaining_quantity == 50
        assert lifecycle_state.average_fill_price == 150.0
        assert lifecycle_state.total_commission == 5.0
        assert lifecycle_state.current_status == OrderStatus.PARTIALLY_FILLED

        # Update fill details - complete fill
        lifecycle_state = lifecycle_manager.update_fill_details(
            sample_order.id,
            filled_quantity=50,
            fill_price=152.0,
            commission=5.0,
        )

        # Verify the update
        assert lifecycle_state.filled_quantity == 100
        assert lifecycle_state.remaining_quantity == 0
        assert lifecycle_state.average_fill_price == 151.0  # (50*150 + 50*152)/100
        assert lifecycle_state.total_commission == 10.0
        assert lifecycle_state.current_status == OrderStatus.FILLED
        assert lifecycle_state.is_terminal is True

        # Verify the order was moved to completed_orders
        assert sample_order.id not in lifecycle_manager.active_orders
        assert sample_order.id in lifecycle_manager.completed_orders

    def test_cancel_order(self, lifecycle_manager, sample_order):
        """Test cancelling an order."""
        # Create the order
        lifecycle_manager.create_order(sample_order)

        # Cancel the order
        lifecycle_state = lifecycle_manager.cancel_order(
            sample_order.id, reason="Testing cancellation"
        )

        # Verify the cancellation
        assert lifecycle_state.current_status == OrderStatus.CANCELLED
        assert len(lifecycle_state.transitions) == 2
        assert lifecycle_state.transitions[1].event == OrderEvent.CANCELLED
        assert lifecycle_state.transitions[1].details == {
            "reason": "Testing cancellation"
        }
        assert lifecycle_state.is_terminal is True

        # Verify the order was moved to completed_orders
        assert sample_order.id not in lifecycle_manager.active_orders
        assert sample_order.id in lifecycle_manager.completed_orders

    def test_cancel_order_not_found(self, lifecycle_manager):
        """Test cancelling a non-existent order."""
        # Try to cancel a non-existent order - should raise an error
        with pytest.raises(OrderLifecycleError):
            lifecycle_manager.cancel_order("non-existent-order")

    def test_cancel_order_not_cancellable(self, lifecycle_manager, sample_order):
        """Test cancelling an order that cannot be cancelled."""
        # Create the order
        lifecycle_manager.create_order(sample_order)

        # Fill the order
        lifecycle_manager.transition_order(
            sample_order.id,
            OrderStatus.FILLED,
            OrderEvent.FILLED,
        )

        # Try to cancel the filled order - should raise an error
        with pytest.raises(OrderLifecycleError):
            lifecycle_manager.cancel_order(sample_order.id)

    def test_reject_order(self, lifecycle_manager, sample_order):
        """Test rejecting an order."""
        # Create the order
        lifecycle_manager.create_order(sample_order)

        # Reject the order
        lifecycle_state = lifecycle_manager.reject_order(
            sample_order.id, reason="Invalid order"
        )

        # Verify the rejection
        assert lifecycle_state.current_status == OrderStatus.REJECTED
        assert len(lifecycle_state.transitions) == 2
        assert lifecycle_state.transitions[1].event == OrderEvent.REJECTED
        assert lifecycle_state.transitions[1].details == {"reason": "Invalid order"}
        assert lifecycle_state.is_terminal is True
        assert len(lifecycle_state.error_messages) == 1
        assert lifecycle_state.error_messages[0] == "Invalid order"

        # Verify the order was moved to completed_orders
        assert sample_order.id not in lifecycle_manager.active_orders
        assert sample_order.id in lifecycle_manager.completed_orders

    def test_reject_order_not_found(self, lifecycle_manager):
        """Test rejecting a non-existent order."""
        # Try to reject a non-existent order - should raise an error
        with pytest.raises(OrderLifecycleError):
            lifecycle_manager.reject_order("non-existent-order", "Invalid order")

    def test_expire_order(self, lifecycle_manager, sample_order):
        """Test expiring an order."""
        # Create the order
        lifecycle_manager.create_order(sample_order)

        # Expire the order
        lifecycle_state = lifecycle_manager.expire_order(
            sample_order.id, reason="Order timed out"
        )

        # Verify the expiration
        assert lifecycle_state.current_status == OrderStatus.EXPIRED
        assert len(lifecycle_state.transitions) == 2
        assert lifecycle_state.transitions[1].event == OrderEvent.EXPIRED
        assert lifecycle_state.transitions[1].details == {"reason": "Order timed out"}
        assert lifecycle_state.is_terminal is True

        # Verify the order was moved to completed_orders
        assert sample_order.id not in lifecycle_manager.active_orders
        assert sample_order.id in lifecycle_manager.completed_orders

    def test_trigger_order(self, lifecycle_manager, sample_order):
        """Test triggering an order."""
        # Create the order
        lifecycle_manager.create_order(sample_order)

        # Trigger the order
        lifecycle_state = lifecycle_manager.trigger_order(
            sample_order.id, trigger_price=155.0
        )

        # Verify the trigger
        assert lifecycle_state.current_status == OrderStatus.TRIGGERED
        assert len(lifecycle_state.transitions) == 2
        assert lifecycle_state.transitions[1].event == OrderEvent.TRIGGERED
        assert lifecycle_state.transitions[1].details == {"trigger_price": 155.0}
        assert lifecycle_state.is_terminal is False

        # Verify the order is still in active_orders
        assert sample_order.id in lifecycle_manager.active_orders
        assert sample_order.id not in lifecycle_manager.completed_orders

    def test_get_order_state(self, lifecycle_manager, sample_order):
        """Test getting the state of an order."""
        # Create the order
        lifecycle_manager.create_order(sample_order)

        # Get the state
        lifecycle_state = lifecycle_manager.get_order_state(sample_order.id)

        # Verify the state
        assert lifecycle_state is not None
        assert lifecycle_state.order == sample_order
        assert lifecycle_state.current_status == OrderStatus.PENDING

        # Move to completed
        lifecycle_manager.transition_order(
            sample_order.id,
            OrderStatus.FILLED,
            OrderEvent.FILLED,
        )

        # Get the state again
        lifecycle_state = lifecycle_manager.get_order_state(sample_order.id)

        # Verify the state
        assert lifecycle_state is not None
        assert lifecycle_state.order == sample_order
        assert lifecycle_state.current_status == OrderStatus.FILLED

    def test_get_order_state_not_found(self, lifecycle_manager):
        """Test getting the state of a non-existent order."""
        # Get the state of a non-existent order
        lifecycle_state = lifecycle_manager.get_order_state("non-existent-order")

        # Verify the state is None
        assert lifecycle_state is None

    def test_get_active_orders(self, lifecycle_manager, sample_order):
        """Test getting all active orders."""
        # Create the order
        lifecycle_manager.create_order(sample_order)

        # Create another order
        order2 = Order(
            id="test-order-2",
            symbol="GOOGL",
            order_type=OrderType.SELL,
            quantity=50,
            price=2800.0,
            status=OrderStatus.PENDING,
            created_at=datetime.utcnow(),
        )
        lifecycle_manager.create_order(order2)

        # Get active orders
        active_orders = lifecycle_manager.get_active_orders()

        # Verify active orders
        assert len(active_orders) == 2
        assert sample_order.id in active_orders
        assert order2.id in active_orders

        # Move one to completed
        lifecycle_manager.transition_order(
            sample_order.id,
            OrderStatus.FILLED,
            OrderEvent.FILLED,
        )

        # Get active orders again
        active_orders = lifecycle_manager.get_active_orders()

        # Verify active orders
        assert len(active_orders) == 1
        assert sample_order.id not in active_orders
        assert order2.id in active_orders

    def test_get_orders_by_status(self, lifecycle_manager, sample_order):
        """Test getting orders by status."""
        # Create the order
        lifecycle_manager.create_order(sample_order)

        # Create another order
        order2 = Order(
            id="test-order-2",
            symbol="GOOGL",
            order_type=OrderType.SELL,
            quantity=50,
            price=2800.0,
            status=OrderStatus.PENDING,
            created_at=datetime.utcnow(),
        )
        lifecycle_manager.create_order(order2)

        # Get orders by status
        pending_orders = lifecycle_manager.get_orders_by_status(OrderStatus.PENDING)

        # Verify orders
        assert len(pending_orders) == 2
        assert any(o.order.id == sample_order.id for o in pending_orders)
        assert any(o.order.id == order2.id for o in pending_orders)

        # Transition one order
        lifecycle_manager.transition_order(
            sample_order.id,
            OrderStatus.PARTIALLY_FILLED,
            OrderEvent.PARTIALLY_FILLED,
        )

        # Get orders by status again
        pending_orders = lifecycle_manager.get_orders_by_status(OrderStatus.PENDING)
        partially_filled_orders = lifecycle_manager.get_orders_by_status(
            OrderStatus.PARTIALLY_FILLED
        )

        # Verify orders
        assert len(pending_orders) == 1
        assert len(partially_filled_orders) == 1
        assert pending_orders[0].order.id == order2.id
        assert partially_filled_orders[0].order.id == sample_order.id

    def test_get_orders_by_symbol(self, lifecycle_manager, sample_order):
        """Test getting orders by symbol."""
        # Create the order
        lifecycle_manager.create_order(sample_order)

        # Create another order for the same symbol
        order2 = Order(
            id="test-order-2",
            symbol="AAPL",
            order_type=OrderType.SELL,
            quantity=50,
            price=150.0,
            status=OrderStatus.PENDING,
            created_at=datetime.utcnow(),
        )
        lifecycle_manager.create_order(order2)

        # Create an order for a different symbol
        order3 = Order(
            id="test-order-3",
            symbol="GOOGL",
            order_type=OrderType.BUY,
            quantity=10,
            price=2800.0,
            status=OrderStatus.PENDING,
            created_at=datetime.utcnow(),
        )
        lifecycle_manager.create_order(order3)

        # Get orders by symbol
        aapl_orders = lifecycle_manager.get_orders_by_symbol("AAPL")
        googl_orders = lifecycle_manager.get_orders_by_symbol("GOOGL")

        # Verify orders
        assert len(aapl_orders) == 2
        assert len(googl_orders) == 1
        assert any(o.order.id == sample_order.id for o in aapl_orders)
        assert any(o.order.id == order2.id for o in aapl_orders)
        assert googl_orders[0].order.id == order3.id

    def test_register_event_callback(self, lifecycle_manager, sample_order):
        """Test registering an event callback."""
        # Create a mock callback
        callback = MagicMock()

        # Register the callback
        lifecycle_manager.register_event_callback(OrderEvent.FILLED, callback)

        # Create the order
        lifecycle_manager.create_order(sample_order)

        # Transition to FILLED - should trigger the callback
        lifecycle_manager.transition_order(
            sample_order.id,
            OrderStatus.FILLED,
            OrderEvent.FILLED,
        )

        # Verify the callback was called
        callback.assert_called_once()
        args = callback.call_args[0]
        assert args[0].order.id == sample_order.id
        assert args[1] == OrderEvent.FILLED

    def test_cleanup_completed_orders(self, lifecycle_manager, sample_order):
        """Test cleaning up completed orders."""
        # Create the order
        lifecycle_manager.create_order(sample_order)

        # Fill the order
        lifecycle_manager.transition_order(
            sample_order.id,
            OrderStatus.FILLED,
            OrderEvent.FILLED,
        )

        # Verify the order is in completed_orders
        assert sample_order.id in lifecycle_manager.completed_orders

        # Modify the last_updated time to be older
        lifecycle_manager.completed_orders[sample_order.id].last_updated = (
            datetime.utcnow() - timedelta(hours=25)
        )

        # Clean up completed orders
        cleaned_count = lifecycle_manager.cleanup_completed_orders(older_than_hours=24)

        # Verify the order was cleaned up
        assert cleaned_count == 1
        assert sample_order.id not in lifecycle_manager.completed_orders

    def test_get_statistics(self, lifecycle_manager, sample_order):
        """Test getting statistics."""
        # Create the order
        lifecycle_manager.create_order(sample_order)

        # Create another order
        order2 = Order(
            id="test-order-2",
            symbol="GOOGL",
            order_type=OrderType.SELL,
            quantity=50,
            price=2800.0,
            status=OrderStatus.PENDING,
            created_at=datetime.utcnow(),
        )
        lifecycle_manager.create_order(order2)

        # Fill one order
        lifecycle_manager.transition_order(
            sample_order.id,
            OrderStatus.FILLED,
            OrderEvent.FILLED,
        )

        # Get statistics
        stats = lifecycle_manager.get_statistics()

        # Verify statistics
        assert stats["total_orders"] == 2
        assert stats["active_orders"] == 1
        assert stats["completed_orders"] == 1
        assert stats["status_breakdown"]["pending"] == 1
        assert (
            stats["status_breakdown"]["filled"] == 0
        )  # Filled order is in completed_orders

    def test_is_valid_transition(self, lifecycle_manager):
        """Test checking if a transition is valid."""
        # Valid transitions
        assert lifecycle_manager._is_valid_transition(
            OrderStatus.PENDING, OrderStatus.FILLED
        )
        assert lifecycle_manager._is_valid_transition(
            OrderStatus.PENDING, OrderStatus.CANCELLED
        )
        assert lifecycle_manager._is_valid_transition(
            OrderStatus.PARTIALLY_FILLED, OrderStatus.FILLED
        )

        # Invalid transitions
        assert not lifecycle_manager._is_valid_transition(
            OrderStatus.FILLED, OrderStatus.PENDING
        )
        assert not lifecycle_manager._is_valid_transition(
            OrderStatus.CANCELLED, OrderStatus.FILLED
        )
        assert not lifecycle_manager._is_valid_transition(
            OrderStatus.FILLED, OrderStatus.CANCELLED
        )

    def test_update_lifecycle_flags(self, lifecycle_manager, sample_order):
        """Test updating lifecycle flags."""
        # Create the order
        lifecycle_state = lifecycle_manager.create_order(sample_order)

        # Verify initial flags
        assert lifecycle_state.can_cancel is True
        assert lifecycle_state.can_modify is True
        assert lifecycle_state.is_terminal is False

        # Transition to PARTIALLY_FILLED
        lifecycle_manager.transition_order(
            sample_order.id,
            OrderStatus.PARTIALLY_FILLED,
            OrderEvent.PARTIALLY_FILLED,
        )

        # Verify flags
        assert lifecycle_state.can_cancel is True
        assert lifecycle_state.can_modify is True
        assert lifecycle_state.is_terminal is False

        # Transition to FILLED
        lifecycle_manager.transition_order(
            sample_order.id,
            OrderStatus.FILLED,
            OrderEvent.FILLED,
        )

        # Verify flags
        assert lifecycle_state.can_cancel is False
        assert lifecycle_state.can_modify is False
        assert lifecycle_state.is_terminal is True

    def test_record_transition(self, lifecycle_manager, sample_order):
        """Test recording a transition."""
        # Create the order
        lifecycle_state = lifecycle_manager.create_order(sample_order)

        # Record a transition
        lifecycle_manager._record_transition(
            sample_order.id,
            OrderStatus.PENDING,
            OrderStatus.FILLED,
            OrderEvent.FILLED,
            {"fill_price": 150.0},
            "market",
        )

        # Verify the transition was recorded
        assert len(lifecycle_state.transitions) == 2
        transition = lifecycle_state.transitions[1]
        assert transition.from_status == OrderStatus.PENDING
        assert transition.to_status == OrderStatus.FILLED
        assert transition.event == OrderEvent.FILLED
        assert transition.details == {"fill_price": 150.0}
        assert transition.triggered_by == "market"

    def test_trigger_event_callbacks(self, lifecycle_manager, sample_order):
        """Test triggering event callbacks."""
        # Create mock callbacks
        callback1 = MagicMock()
        callback2 = MagicMock()

        # Register callbacks
        lifecycle_manager.register_event_callback(OrderEvent.FILLED, callback1)
        lifecycle_manager.register_event_callback(OrderEvent.FILLED, callback2)

        # Create the order
        lifecycle_state = lifecycle_manager.create_order(sample_order)

        # Trigger callbacks
        lifecycle_manager._trigger_event_callbacks(OrderEvent.FILLED, lifecycle_state)

        # Verify callbacks were called
        callback1.assert_called_once_with(lifecycle_state, OrderEvent.FILLED)
        callback2.assert_called_once_with(lifecycle_state, OrderEvent.FILLED)

    def test_trigger_event_callbacks_error(self, lifecycle_manager, sample_order):
        """Test error handling in event callbacks."""
        # Create a callback that raises an exception
        callback = MagicMock(side_effect=Exception("Test error"))

        # Register the callback
        lifecycle_manager.register_event_callback(OrderEvent.FILLED, callback)

        # Create the order
        lifecycle_state = lifecycle_manager.create_order(sample_order)

        # Trigger callbacks - should not raise an exception
        lifecycle_manager._trigger_event_callbacks(OrderEvent.FILLED, lifecycle_state)

        # Verify the callback was called
        callback.assert_called_once_with(lifecycle_state, OrderEvent.FILLED)
