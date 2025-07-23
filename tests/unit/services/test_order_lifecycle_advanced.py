"""
Comprehensive test suite for OrderLifecycleManager.

Tests all order lifecycle functionality including:
- Order state transitions and validation
- Lifecycle event management and callbacks
- Order creation and tracking
- Error handling and edge cases
- Performance and concurrent operations
"""

import pytest
from datetime import datetime, timedelta
from unittest.mock import Mock, patch, MagicMock
from collections.abc import Callable

from app.services.order_lifecycle import (
    OrderLifecycleManager,
    OrderStateTransition,
    OrderLifecycleState,
    OrderEvent,
    OrderLifecycleError,
    get_order_lifecycle_manager,
    order_lifecycle_manager
)
from app.schemas.orders import Order, OrderStatus, OrderType, OrderCondition


class TestOrderEvent:
    """Test OrderEvent enum values."""
    
    def test_order_event_values(self):
        """Test that all expected order events exist."""
        expected_events = [
            "created", "submitted", "acknowledged", "triggered", 
            "partially_filled", "filled", "cancelled", "rejected", 
            "expired", "modified", "error"
        ]
        
        for event_name in expected_events:
            assert hasattr(OrderEvent, event_name.upper())
            assert OrderEvent[event_name.upper()].value == event_name


class TestOrderStateTransition:
    """Test OrderStateTransition data class."""
    
    def test_state_transition_initialization(self):
        """Test OrderStateTransition initialization."""
        timestamp = datetime.utcnow()
        
        transition = OrderStateTransition(
            from_status=OrderStatus.PENDING,
            to_status=OrderStatus.FILLED,
            event=OrderEvent.FILLED,
            timestamp=timestamp,
            details={"fill_price": 150.0},
            triggered_by="market"
        )
        
        assert transition.from_status == OrderStatus.PENDING
        assert transition.to_status == OrderStatus.FILLED
        assert transition.event == OrderEvent.FILLED
        assert transition.timestamp == timestamp
        assert transition.details == {"fill_price": 150.0}
        assert transition.triggered_by == "market"

    def test_state_transition_default_values(self):
        """Test OrderStateTransition with default values."""
        transition = OrderStateTransition(
            from_status=OrderStatus.PENDING,
            to_status=OrderStatus.FILLED,
            event=OrderEvent.FILLED,
            timestamp=datetime.utcnow()
        )
        
        assert transition.details == {}
        assert transition.triggered_by == "system"


class TestOrderLifecycleState:
    """Test OrderLifecycleState data class."""
    
    def setup_method(self):
        """Set up test fixtures."""
        self.mock_order = Mock(spec=Order)
        self.mock_order.id = "test_order_123"
        self.mock_order.symbol = "AAPL"
        self.mock_order.quantity = 100

    def test_lifecycle_state_initialization(self):
        """Test OrderLifecycleState initialization."""
        created_at = datetime.utcnow()
        last_updated = datetime.utcnow()
        
        state = OrderLifecycleState(
            order=self.mock_order,
            current_status=OrderStatus.PENDING,
            created_at=created_at,
            last_updated=last_updated
        )
        
        assert state.order == self.mock_order
        assert state.current_status == OrderStatus.PENDING
        assert state.created_at == created_at
        assert state.last_updated == last_updated
        assert state.transitions == []
        assert state.error_messages == []
        assert state.metadata == {}

    def test_lifecycle_state_default_values(self):
        """Test OrderLifecycleState with default values."""
        state = OrderLifecycleState(
            order=self.mock_order,
            current_status=OrderStatus.PENDING,
            created_at=datetime.utcnow(),
            last_updated=datetime.utcnow()
        )
        
        assert state.filled_quantity == 0
        assert state.remaining_quantity == 0
        assert state.average_fill_price is None
        assert state.total_commission == 0.0
        assert state.can_cancel is True
        assert state.can_modify is True
        assert state.is_terminal is False


class TestOrderLifecycleManager:
    """Test OrderLifecycleManager functionality."""

    def setup_method(self):
        """Set up test fixtures."""
        self.manager = OrderLifecycleManager()
        self.mock_order = Mock(spec=Order)
        self.mock_order.id = "test_order_123"
        self.mock_order.symbol = "AAPL"
        self.mock_order.quantity = 100

    def test_manager_initialization(self):
        """Test OrderLifecycleManager initialization."""
        assert len(self.manager.active_orders) == 0
        assert len(self.manager.completed_orders) == 0
        assert len(self.manager.event_callbacks) == len(OrderEvent)
        assert self.manager.valid_transitions is not None
        assert self.manager.terminal_states == {
            OrderStatus.FILLED,
            OrderStatus.CANCELLED,
            OrderStatus.REJECTED,
            OrderStatus.EXPIRED,
        }

    def test_create_order_success(self):
        """Test successful order creation."""
        result = self.manager.create_order(self.mock_order)
        
        assert isinstance(result, OrderLifecycleState)
        assert result.order == self.mock_order
        assert result.current_status == OrderStatus.PENDING
        assert result.remaining_quantity == 100
        assert self.mock_order.id in self.manager.active_orders
        assert len(result.transitions) == 1
        assert result.transitions[0].event == OrderEvent.CREATED

    def test_create_order_missing_id(self):
        """Test order creation with missing ID."""
        self.mock_order.id = None
        
        with pytest.raises(OrderLifecycleError, match="Order must have an ID"):
            self.manager.create_order(self.mock_order)

    def test_create_order_duplicate_id(self):
        """Test order creation with duplicate ID."""
        # Create first order
        self.manager.create_order(self.mock_order)
        
        # Try to create order with same ID
        duplicate_order = Mock(spec=Order)
        duplicate_order.id = "test_order_123"
        duplicate_order.quantity = 50
        
        with pytest.raises(OrderLifecycleError, match="Order test_order_123 already exists"):
            self.manager.create_order(duplicate_order)

    def test_transition_order_success(self):
        """Test successful order transition."""
        # Create order first
        lifecycle_state = self.manager.create_order(self.mock_order)
        
        # Transition to filled
        result = self.manager.transition_order(
            "test_order_123",
            OrderStatus.FILLED,
            OrderEvent.FILLED,
            details={"fill_price": 150.0}
        )
        
        assert result.current_status == OrderStatus.FILLED
        assert result.is_terminal is True
        assert len(result.transitions) == 2  # Created + Filled
        assert result.transitions[1].event == OrderEvent.FILLED
        assert result.transitions[1].details == {"fill_price": 150.0}
        
        # Should be moved to completed orders
        assert "test_order_123" not in self.manager.active_orders
        assert "test_order_123" in self.manager.completed_orders

    def test_transition_order_not_found(self):
        """Test transition when order not found."""
        with pytest.raises(OrderLifecycleError, match="Order nonexistent not found"):
            self.manager.transition_order(
                "nonexistent",
                OrderStatus.FILLED,
                OrderEvent.FILLED
            )

    def test_transition_order_invalid_transition(self):
        """Test invalid state transition."""
        # Create and fill order
        self.manager.create_order(self.mock_order)
        self.manager.transition_order(
            "test_order_123",
            OrderStatus.FILLED,
            OrderEvent.FILLED
        )
        
        # Try to transition from filled to pending (invalid)
        with pytest.raises(OrderLifecycleError, match="Invalid transition"):
            self.manager.transition_order(
                "test_order_123",
                OrderStatus.PENDING,
                OrderEvent.MODIFIED
            )

    def test_update_fill_details_success(self):
        """Test updating order fill details."""
        # Create order
        lifecycle_state = self.manager.create_order(self.mock_order)
        
        # Update fill details
        result = self.manager.update_fill_details(
            "test_order_123",
            filled_quantity=50,
            fill_price=150.0,
            commission=1.0
        )
        
        assert result.filled_quantity == 50
        assert result.remaining_quantity == 50  # 100 - 50
        assert result.average_fill_price == 150.0
        assert result.total_commission == 1.0
        assert result.current_status == OrderStatus.PARTIALLY_FILLED

    def test_update_fill_details_complete_fill(self):
        """Test updating fill details with complete fill."""
        # Create order
        self.manager.create_order(self.mock_order)
        
        # Fill completely
        result = self.manager.update_fill_details(
            "test_order_123",
            filled_quantity=100,
            fill_price=150.0,
            commission=2.0
        )
        
        assert result.filled_quantity == 100
        assert result.remaining_quantity == 0
        assert result.current_status == OrderStatus.FILLED
        assert result.is_terminal is True

    def test_update_fill_details_multiple_fills(self):
        """Test multiple partial fills and average price calculation."""
        # Create order
        self.manager.create_order(self.mock_order)
        
        # First partial fill
        self.manager.update_fill_details(
            "test_order_123",
            filled_quantity=30,
            fill_price=150.0,
            commission=1.0
        )
        
        # Second partial fill
        result = self.manager.update_fill_details(
            "test_order_123",
            filled_quantity=20,
            fill_price=155.0,
            commission=1.0
        )
        
        # Check weighted average price: (30*150 + 20*155) / 50 = 152.0
        assert result.filled_quantity == 50
        assert result.remaining_quantity == 50
        assert abs(result.average_fill_price - 152.0) < 0.01
        assert result.total_commission == 2.0

    def test_update_fill_details_order_not_found(self):
        """Test updating fill details when order not found."""
        with pytest.raises(OrderLifecycleError, match="Order nonexistent not found"):
            self.manager.update_fill_details(
                "nonexistent",
                filled_quantity=50,
                fill_price=150.0
            )

    def test_cancel_order_success(self):
        """Test successful order cancellation."""
        # Create order
        self.manager.create_order(self.mock_order)
        
        # Cancel order
        result = self.manager.cancel_order(
            "test_order_123",
            reason="User requested",
            triggered_by="user"
        )
        
        assert result.current_status == OrderStatus.CANCELLED
        assert result.is_terminal is True
        assert result.transitions[-1].event == OrderEvent.CANCELLED
        assert result.transitions[-1].details == {"reason": "User requested"}
        assert result.transitions[-1].triggered_by == "user"

    def test_cancel_order_not_found(self):
        """Test cancelling order that doesn't exist."""
        with pytest.raises(OrderLifecycleError, match="Order nonexistent not found"):
            self.manager.cancel_order("nonexistent")

    def test_cancel_order_cannot_cancel(self):
        """Test cancelling order that cannot be cancelled."""
        # Create and fill order
        self.manager.create_order(self.mock_order)
        lifecycle_state = self.manager.transition_order(
            "test_order_123",
            OrderStatus.FILLED,
            OrderEvent.FILLED
        )
        
        # Try to cancel filled order
        with pytest.raises(OrderLifecycleError, match="Order test_order_123 cannot be cancelled"):
            self.manager.cancel_order("test_order_123")

    def test_reject_order_success(self):
        """Test successful order rejection."""
        # Create order
        self.manager.create_order(self.mock_order)
        
        # Reject order
        result = self.manager.reject_order(
            "test_order_123",
            reason="Insufficient funds",
            triggered_by="risk_engine"
        )
        
        assert result.current_status == OrderStatus.REJECTED
        assert result.is_terminal is True
        assert "Insufficient funds" in result.error_messages
        assert result.transitions[-1].event == OrderEvent.REJECTED

    def test_expire_order_success(self):
        """Test successful order expiration."""
        # Create order
        self.manager.create_order(self.mock_order)
        
        # Expire order
        result = self.manager.expire_order(
            "test_order_123",
            reason="End of day",
            triggered_by="time_engine"
        )
        
        assert result.current_status == OrderStatus.EXPIRED
        assert result.is_terminal is True
        assert result.transitions[-1].event == OrderEvent.EXPIRED
        assert result.transitions[-1].details == {"reason": "End of day"}

    def test_trigger_order_success(self):
        """Test successful order triggering."""
        # Create order
        self.manager.create_order(self.mock_order)
        
        # Trigger order
        result = self.manager.trigger_order(
            "test_order_123",
            trigger_price=145.0,
            triggered_by="market"
        )
        
        assert result.current_status == OrderStatus.TRIGGERED
        assert result.transitions[-1].event == OrderEvent.TRIGGERED
        assert result.transitions[-1].details == {"trigger_price": 145.0}

    def test_get_order_state_active(self):
        """Test getting order state for active order."""
        # Create order
        lifecycle_state = self.manager.create_order(self.mock_order)
        
        result = self.manager.get_order_state("test_order_123")
        
        assert result == lifecycle_state

    def test_get_order_state_completed(self):
        """Test getting order state for completed order."""
        # Create and complete order
        self.manager.create_order(self.mock_order)
        self.manager.transition_order(
            "test_order_123",
            OrderStatus.FILLED,
            OrderEvent.FILLED
        )
        
        result = self.manager.get_order_state("test_order_123")
        
        assert result is not None
        assert result.current_status == OrderStatus.FILLED

    def test_get_order_state_not_found(self):
        """Test getting order state when order not found."""
        result = self.manager.get_order_state("nonexistent")
        
        assert result is None

    def test_get_active_orders(self):
        """Test getting all active orders."""
        # Create multiple orders
        order1 = Mock(spec=Order)
        order1.id = "order_1"
        order1.quantity = 100
        
        order2 = Mock(spec=Order)
        order2.id = "order_2"  
        order2.quantity = 200
        
        self.manager.create_order(order1)
        self.manager.create_order(order2)
        
        # Complete one order
        self.manager.transition_order("order_1", OrderStatus.FILLED, OrderEvent.FILLED)
        
        active_orders = self.manager.get_active_orders()
        
        assert len(active_orders) == 1
        assert "order_2" in active_orders
        assert "order_1" not in active_orders

    def test_get_orders_by_status(self):
        """Test getting orders by specific status."""
        # Create multiple orders
        orders = []
        for i in range(3):
            order = Mock(spec=Order)
            order.id = f"order_{i}"
            order.quantity = 100
            orders.append(order)
            self.manager.create_order(order)
        
        # Transition orders to different states
        self.manager.transition_order("order_0", OrderStatus.FILLED, OrderEvent.FILLED)
        self.manager.transition_order("order_1", OrderStatus.CANCELLED, OrderEvent.CANCELLED)
        # order_2 remains PENDING
        
        pending_orders = self.manager.get_orders_by_status(OrderStatus.PENDING)
        filled_orders = self.manager.get_orders_by_status(OrderStatus.FILLED)
        cancelled_orders = self.manager.get_orders_by_status(OrderStatus.CANCELLED)
        
        assert len(pending_orders) == 1
        assert pending_orders[0].order.id == "order_2"
        assert len(filled_orders) == 0  # Filled orders are in completed_orders
        assert len(cancelled_orders) == 0  # Cancelled orders are in completed_orders

    def test_get_orders_by_symbol(self):
        """Test getting orders by symbol."""
        # Create orders for different symbols
        order1 = Mock(spec=Order)
        order1.id = "order_1"
        order1.symbol = "AAPL"
        order1.quantity = 100
        
        order2 = Mock(spec=Order)
        order2.id = "order_2"
        order2.symbol = "MSFT"
        order2.quantity = 200
        
        order3 = Mock(spec=Order)
        order3.id = "order_3"
        order3.symbol = "AAPL"
        order3.quantity = 150
        
        self.manager.create_order(order1)
        self.manager.create_order(order2)
        self.manager.create_order(order3)
        
        aapl_orders = self.manager.get_orders_by_symbol("AAPL")
        msft_orders = self.manager.get_orders_by_symbol("MSFT")
        
        assert len(aapl_orders) == 2
        assert len(msft_orders) == 1
        assert all(order.order.symbol == "AAPL" for order in aapl_orders)

    def test_register_event_callback(self):
        """Test registering event callbacks."""
        callback_calls = []
        
        def test_callback(lifecycle_state, event):
            callback_calls.append((lifecycle_state.order.id, event))
        
        self.manager.register_event_callback(OrderEvent.FILLED, test_callback)
        
        # Create and fill order
        self.manager.create_order(self.mock_order)
        self.manager.transition_order(
            "test_order_123",
            OrderStatus.FILLED,
            OrderEvent.FILLED
        )
        
        # Callback should have been called
        assert len(callback_calls) == 1
        assert callback_calls[0][0] == "test_order_123"
        assert callback_calls[0][1] == OrderEvent.FILLED

    def test_event_callback_error_handling(self):
        """Test error handling in event callbacks."""
        def failing_callback(lifecycle_state, event):
            raise Exception("Callback error")
        
        self.manager.register_event_callback(OrderEvent.FILLED, failing_callback)
        
        # Create and fill order - should not raise exception
        self.manager.create_order(self.mock_order)
        self.manager.transition_order(
            "test_order_123",
            OrderStatus.FILLED,
            OrderEvent.FILLED
        )
        
        # Order should still be properly transitioned
        state = self.manager.get_order_state("test_order_123")
        assert state.current_status == OrderStatus.FILLED

    def test_cleanup_completed_orders(self):
        """Test cleanup of old completed orders."""
        # Create and complete multiple orders
        for i in range(5):
            order = Mock(spec=Order)
            order.id = f"order_{i}"
            order.quantity = 100
            self.manager.create_order(order)
            self.manager.transition_order(f"order_{i}", OrderStatus.FILLED, OrderEvent.FILLED)
        
        # Manually set some orders as old
        old_time = datetime.utcnow() - timedelta(hours=25)
        for i in range(3):
            order_id = f"order_{i}"
            if order_id in self.manager.completed_orders:
                self.manager.completed_orders[order_id].last_updated = old_time
        
        # Cleanup orders older than 24 hours
        cleaned = self.manager.cleanup_completed_orders(older_than_hours=24)
        
        assert cleaned == 3
        assert len(self.manager.completed_orders) == 2

    def test_get_statistics(self):
        """Test getting lifecycle statistics."""
        # Create orders in various states
        orders = []
        for i in range(5):
            order = Mock(spec=Order)
            order.id = f"order_{i}"
            order.quantity = 100
            orders.append(order)
            self.manager.create_order(order)
        
        # Transition some orders
        self.manager.transition_order("order_0", OrderStatus.FILLED, OrderEvent.FILLED)
        self.manager.transition_order("order_1", OrderStatus.CANCELLED, OrderEvent.CANCELLED)
        self.manager.transition_order("order_2", OrderStatus.PARTIALLY_FILLED, OrderEvent.PARTIALLY_FILLED)
        # order_3 and order_4 remain PENDING
        
        stats = self.manager.get_statistics()
        
        assert stats["total_orders"] == 5
        assert stats["active_orders"] == 3  # PENDING and PARTIALLY_FILLED
        assert stats["completed_orders"] == 2  # FILLED and CANCELLED
        assert stats["status_breakdown"][OrderStatus.PENDING.value] == 2
        assert stats["status_breakdown"][OrderStatus.PARTIALLY_FILLED.value] == 1

    def test_valid_transitions_definition(self):
        """Test that valid transitions are properly defined."""
        transitions = self.manager._define_valid_transitions()
        
        # Test some key transitions
        assert OrderStatus.FILLED in transitions[OrderStatus.PENDING]
        assert OrderStatus.CANCELLED in transitions[OrderStatus.PENDING]
        assert OrderStatus.PARTIALLY_FILLED in transitions[OrderStatus.PENDING]
        assert OrderStatus.FILLED in transitions[OrderStatus.PARTIALLY_FILLED]
        
        # Terminal states should have no valid transitions
        assert len(transitions[OrderStatus.FILLED]) == 0
        assert len(transitions[OrderStatus.CANCELLED]) == 0
        assert len(transitions[OrderStatus.REJECTED]) == 0
        assert len(transitions[OrderStatus.EXPIRED]) == 0

    def test_is_valid_transition(self):
        """Test transition validation logic."""
        # Valid transitions
        assert self.manager._is_valid_transition(OrderStatus.PENDING, OrderStatus.FILLED)
        assert self.manager._is_valid_transition(OrderStatus.PENDING, OrderStatus.CANCELLED)
        assert self.manager._is_valid_transition(OrderStatus.PARTIALLY_FILLED, OrderStatus.FILLED)
        
        # Invalid transitions
        assert not self.manager._is_valid_transition(OrderStatus.FILLED, OrderStatus.PENDING)
        assert not self.manager._is_valid_transition(OrderStatus.CANCELLED, OrderStatus.FILLED)
        assert not self.manager._is_valid_transition(OrderStatus.REJECTED, OrderStatus.PENDING)

    def test_update_lifecycle_flags(self):
        """Test updating lifecycle flags based on status."""
        # Create order
        lifecycle_state = self.manager.create_order(self.mock_order)
        
        # Test PENDING status flags
        assert lifecycle_state.can_cancel is True
        assert lifecycle_state.can_modify is True
        assert lifecycle_state.is_terminal is False
        
        # Transition to PARTIALLY_FILLED
        self.manager.transition_order(
            "test_order_123",
            OrderStatus.PARTIALLY_FILLED,
            OrderEvent.PARTIALLY_FILLED
        )
        
        state = self.manager.get_order_state("test_order_123")
        assert state.can_cancel is True
        assert state.can_modify is True
        assert state.is_terminal is False
        
        # Transition to FILLED
        self.manager.transition_order(
            "test_order_123",
            OrderStatus.FILLED,
            OrderEvent.FILLED
        )
        
        state = self.manager.get_order_state("test_order_123")
        assert state.can_cancel is False
        assert state.can_modify is False
        assert state.is_terminal is True

    def test_record_transition(self):
        """Test transition recording."""
        # Create order
        lifecycle_state = self.manager.create_order(self.mock_order)
        
        # Record a custom transition
        self.manager._record_transition(
            "test_order_123",
            OrderStatus.PENDING,
            OrderStatus.ACKNOWLEDGED,
            OrderEvent.ACKNOWLEDGED,
            {"broker_id": "12345"},
            "broker"
        )
        
        state = self.manager.get_order_state("test_order_123")
        
        # Should have 2 transitions: CREATED and ACKNOWLEDGED
        assert len(state.transitions) == 2
        ack_transition = state.transitions[1]
        assert ack_transition.from_status == OrderStatus.PENDING
        assert ack_transition.to_status == OrderStatus.ACKNOWLEDGED
        assert ack_transition.event == OrderEvent.ACKNOWLEDGED
        assert ack_transition.details == {"broker_id": "12345"}
        assert ack_transition.triggered_by == "broker"

    def test_trigger_event_callbacks(self):
        """Test triggering event callbacks."""
        callback_calls = []
        
        def callback1(lifecycle_state, event):
            callback_calls.append(("callback1", lifecycle_state.order.id, event))
        
        def callback2(lifecycle_state, event):
            callback_calls.append(("callback2", lifecycle_state.order.id, event))
        
        # Register multiple callbacks for same event
        self.manager.register_event_callback(OrderEvent.FILLED, callback1)
        self.manager.register_event_callback(OrderEvent.FILLED, callback2)
        
        # Create order and trigger event
        lifecycle_state = self.manager.create_order(self.mock_order)
        self.manager._trigger_event_callbacks(OrderEvent.FILLED, lifecycle_state)
        
        # Both callbacks should be called
        assert len(callback_calls) == 2
        assert ("callback1", "test_order_123", OrderEvent.FILLED) in callback_calls
        assert ("callback2", "test_order_123", OrderEvent.FILLED) in callback_calls


class TestGlobalOrderLifecycleManager:
    """Test global order lifecycle manager functions."""

    def test_get_order_lifecycle_manager(self):
        """Test getting the global order lifecycle manager."""
        manager = get_order_lifecycle_manager()
        
        assert isinstance(manager, OrderLifecycleManager)
        assert manager == order_lifecycle_manager

    def test_global_manager_functionality(self):
        """Test that global manager works correctly."""
        # Create order using global manager
        mock_order = Mock(spec=Order)
        mock_order.id = "global_test_order"
        mock_order.quantity = 100
        
        lifecycle_state = order_lifecycle_manager.create_order(mock_order)
        
        assert lifecycle_state.order == mock_order
        assert "global_test_order" in order_lifecycle_manager.active_orders
        
        # Clean up
        order_lifecycle_manager.active_orders.clear()
        order_lifecycle_manager.completed_orders.clear()


class TestOrderLifecycleManagerPerformance:
    """Test performance aspects of OrderLifecycleManager."""

    def setup_method(self):
        """Set up test fixtures."""
        self.manager = OrderLifecycleManager()

    def test_concurrent_order_operations(self):
        """Test concurrent order operations."""
        import threading
        import time
        
        orders_created = []
        errors = []
        
        def create_orders(start_index, count):
            try:
                for i in range(start_index, start_index + count):
                    order = Mock(spec=Order)
                    order.id = f"concurrent_order_{i}"
                    order.quantity = 100
                    
                    lifecycle_state = self.manager.create_order(order)
                    orders_created.append(lifecycle_state.order.id)
                    
                    # Small delay to increase chance of race conditions
                    time.sleep(0.001)
            except Exception as e:
                errors.append(str(e))
        
        # Create multiple threads
        threads = []
        for i in range(5):
            thread = threading.Thread(target=create_orders, args=[i * 10, 10])
            threads.append(thread)
            thread.start()
        
        # Wait for all threads to complete
        for thread in threads:
            thread.join()
        
        # Verify results
        assert len(errors) == 0, f"Errors occurred: {errors}"
        assert len(orders_created) == 50
        assert len(set(orders_created)) == 50  # All IDs should be unique
        assert len(self.manager.active_orders) == 50

    def test_large_number_of_orders(self):
        """Test handling a large number of orders."""
        import time
        
        start_time = time.time()
        
        # Create many orders
        for i in range(1000):
            order = Mock(spec=Order)
            order.id = f"bulk_order_{i}"
            order.quantity = 100
            order.symbol = f"SYM{i % 100}"  # 100 different symbols
            
            self.manager.create_order(order)
            
            # Randomly transition some orders
            if i % 10 == 0:
                self.manager.transition_order(
                    f"bulk_order_{i}",
                    OrderStatus.FILLED,
                    OrderEvent.FILLED
                )
        
        end_time = time.time()
        duration = end_time - start_time
        
        # Should complete in reasonable time
        assert duration < 5.0, f"Processing took too long: {duration}s"
        
        # Verify state
        assert len(self.manager.active_orders) == 900  # 1000 - 100 filled
        assert len(self.manager.completed_orders) == 100

    def test_memory_usage_with_many_transitions(self):
        """Test memory usage with many transitions."""
        import sys
        
        # Create order
        order = Mock(spec=Order)
        order.id = "memory_test_order"
        order.quantity = 1000
        
        lifecycle_state = self.manager.create_order(order)
        initial_size = sys.getsizeof(lifecycle_state.transitions)
        
        # Create many partial fill transitions
        for i in range(100):
            self.manager.update_fill_details(
                "memory_test_order",
                filled_quantity=1,
                fill_price=150.0 + i * 0.01,
                commission=0.01
            )
        
        final_size = sys.getsizeof(lifecycle_state.transitions)
        memory_increase = final_size - initial_size
        
        # Memory usage should be reasonable
        assert memory_increase < 1024 * 100  # Less than 100KB for 100 transitions


class TestOrderLifecycleManagerErrorScenarios:
    """Test various error scenarios in OrderLifecycleManager."""

    def setup_method(self):
        """Set up test fixtures."""
        self.manager = OrderLifecycleManager()

    def test_corrupted_order_data(self):
        """Test handling of corrupted order data."""
        # Order with invalid attributes
        corrupted_order = Mock()
        corrupted_order.id = "corrupted_order"
        # Missing quantity attribute
        
        with pytest.raises(AttributeError):
            self.manager.create_order(corrupted_order)

    def test_invalid_fill_quantities(self):
        """Test handling of invalid fill quantities."""
        # Create order
        order = Mock(spec=Order)
        order.id = "test_order"
        order.quantity = 100
        
        self.manager.create_order(order)
        
        # Try to fill more than order quantity
        result = self.manager.update_fill_details(
            "test_order",
            filled_quantity=150,  # More than order quantity
            fill_price=150.0
        )
        
        # Should handle gracefully
        assert result.filled_quantity == 150
        assert result.remaining_quantity == -50  # Negative remaining

    def test_negative_fill_prices(self):
        """Test handling of negative fill prices."""
        # Create order
        order = Mock(spec=Order)
        order.id = "test_order"
        order.quantity = 100
        
        self.manager.create_order(order)
        
        # Fill with negative price
        result = self.manager.update_fill_details(
            "test_order",
            filled_quantity=50,
            fill_price=-10.0  # Negative price
        )
        
        # Should accept negative price (could be valid in some cases)
        assert result.average_fill_price == -10.0

    def test_zero_quantity_fills(self):
        """Test handling of zero quantity fills."""
        # Create order
        order = Mock(spec=Order)
        order.id = "test_order"
        order.quantity = 100
        
        self.manager.create_order(order)
        
        # Fill with zero quantity
        result = self.manager.update_fill_details(
            "test_order",
            filled_quantity=0,
            fill_price=150.0
        )
        
        # Should handle gracefully
        assert result.filled_quantity == 0
        assert result.remaining_quantity == 100
        assert result.current_status == OrderStatus.PENDING  # No transition for zero fill

    def test_concurrent_state_modifications(self):
        """Test handling concurrent state modifications."""
        import threading
        import time
        
        # Create order
        order = Mock(spec=Order)
        order.id = "concurrent_test"
        order.quantity = 1000
        
        self.manager.create_order(order)
        
        results = []
        errors = []
        
        def fill_order(fill_size):
            try:
                result = self.manager.update_fill_details(
                    "concurrent_test",
                    filled_quantity=fill_size,
                    fill_price=150.0
                )
                results.append(result.filled_quantity)
            except Exception as e:
                errors.append(str(e))
        
        # Create multiple threads doing fills concurrently
        threads = []
        for i in range(10):
            thread = threading.Thread(target=fill_order, args=[10])
            threads.append(thread)
            thread.start()
        
        # Wait for all threads to complete
        for thread in threads:
            thread.join()
        
        # Check final state
        final_state = self.manager.get_order_state("concurrent_test")
        
        # Some operations should succeed
        assert len(errors) == 0, f"Unexpected errors: {errors}"
        assert final_state.filled_quantity == 100  # 10 threads * 10 shares each