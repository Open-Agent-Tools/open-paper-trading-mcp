"""
Order lifecycle management system.

This module manages the complete lifecycle of orders from creation to completion,
including state transitions, validation, and event tracking.
"""

import logging
from collections.abc import Callable
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from enum import Enum

from ..schemas.orders import Order, OrderStatus

logger = logging.getLogger(__name__)


class OrderEvent(str, Enum):
    """Order lifecycle events."""

    CREATED = "created"
    SUBMITTED = "submitted"
    ACKNOWLEDGED = "acknowledged"
    TRIGGERED = "triggered"
    PARTIALLY_FILLED = "partially_filled"
    FILLED = "filled"
    CANCELLED = "cancelled"
    REJECTED = "rejected"
    EXPIRED = "expired"
    MODIFIED = "modified"
    ERROR = "error"


@dataclass
class OrderStateTransition:
    """Represents a state transition in the order lifecycle."""

    from_status: OrderStatus
    to_status: OrderStatus
    event: OrderEvent
    timestamp: datetime
    details: dict = field(default_factory=dict)
    triggered_by: str = "system"  # user, system, market, etc.


@dataclass
class OrderLifecycleState:
    """Complete lifecycle state of an order."""

    order: Order
    current_status: OrderStatus
    created_at: datetime
    last_updated: datetime
    transitions: list[OrderStateTransition] = field(default_factory=list)
    error_messages: list[str] = field(default_factory=list)
    metadata: dict = field(default_factory=dict)

    # Execution details
    filled_quantity: int = 0
    remaining_quantity: int = 0
    average_fill_price: float | None = None
    total_commission: float = 0.0

    # Lifecycle flags
    can_cancel: bool = True
    can_modify: bool = True
    is_terminal: bool = False


class OrderLifecycleError(Exception):
    """Error in order lifecycle management."""

    pass


class OrderLifecycleManager:
    """
    Manages the complete lifecycle of orders.

    This class handles:
    - Order state transitions
    - Validation of state changes
    - Event tracking and audit trail
    - Notification triggers
    - Cleanup of completed orders
    """

    def __init__(self):
        self.active_orders: dict[str, OrderLifecycleState] = {}
        self.completed_orders: dict[str, OrderLifecycleState] = {}

        # Event callbacks
        self.event_callbacks: dict[OrderEvent, list[Callable]] = {
            event: [] for event in OrderEvent
        }

        # Valid state transitions
        self.valid_transitions = self._define_valid_transitions()

        # Terminal states
        self.terminal_states = {
            OrderStatus.FILLED,
            OrderStatus.CANCELLED,
            OrderStatus.REJECTED,
            OrderStatus.EXPIRED,
        }

    def create_order(self, order: Order) -> OrderLifecycleState:
        """Create a new order and initialize its lifecycle."""
        if not order.id:
            raise OrderLifecycleError("Order must have an ID")

        if order.id in self.active_orders:
            raise OrderLifecycleError(f"Order {order.id} already exists")

        # Initialize lifecycle state
        lifecycle_state = OrderLifecycleState(
            order=order,
            current_status=OrderStatus.PENDING,
            created_at=datetime.utcnow(),
            last_updated=datetime.utcnow(),
            remaining_quantity=abs(order.quantity),
        )

        self.active_orders[order.id] = lifecycle_state

        # Record creation event
        self._record_transition(
            order.id,
            None,
            OrderStatus.PENDING,
            OrderEvent.CREATED,
            details={"order_type": order.order_type, "symbol": order.symbol},
        )

        logger.info(f"Created order lifecycle for {order.id}")
        return lifecycle_state

    def transition_order(
        self,
        order_id: str,
        new_status: OrderStatus,
        event: OrderEvent,
        details: dict | None = None,
        triggered_by: str = "system",
    ) -> OrderLifecycleState:
        """Transition an order to a new status."""
        lifecycle_state = self.get_order_state(order_id)
        if not lifecycle_state:
            raise OrderLifecycleError(f"Order {order_id} not found")

        current_status = lifecycle_state.current_status

        # Validate transition
        if not self._is_valid_transition(current_status, new_status):
            raise OrderLifecycleError(
                f"Invalid transition from {current_status} to {new_status}"
            )

        # Update state
        lifecycle_state.current_status = new_status
        lifecycle_state.last_updated = datetime.utcnow()

        # Update lifecycle flags
        self._update_lifecycle_flags(lifecycle_state)

        # Record transition
        self._record_transition(
            order_id, current_status, new_status, event, details or {}, triggered_by
        )

        # Move to completed if terminal
        if new_status in self.terminal_states:
            lifecycle_state.is_terminal = True
            self.completed_orders[order_id] = lifecycle_state
            del self.active_orders[order_id]

        # Trigger event callbacks
        self._trigger_event_callbacks(event, lifecycle_state)

        logger.info(
            f"Order {order_id} transitioned from {current_status} to {new_status}"
        )
        return lifecycle_state

    def update_fill_details(
        self,
        order_id: str,
        filled_quantity: int,
        fill_price: float,
        commission: float = 0.0,
    ) -> OrderLifecycleState:
        """Update order with fill details."""
        lifecycle_state = self.get_order_state(order_id)
        if not lifecycle_state:
            raise OrderLifecycleError(f"Order {order_id} not found")

        # Update quantities
        lifecycle_state.filled_quantity += filled_quantity
        lifecycle_state.remaining_quantity = (
            abs(lifecycle_state.order.quantity) - lifecycle_state.filled_quantity
        )
        lifecycle_state.total_commission += commission

        # Update average fill price
        if lifecycle_state.average_fill_price is None:
            lifecycle_state.average_fill_price = fill_price
        else:
            # Weighted average
            total_filled_value = (
                lifecycle_state.filled_quantity - filled_quantity
            ) * lifecycle_state.average_fill_price
            total_filled_value += filled_quantity * fill_price
            lifecycle_state.average_fill_price = (
                total_filled_value / lifecycle_state.filled_quantity
            )

        lifecycle_state.last_updated = datetime.utcnow()

        # Determine new status
        if lifecycle_state.remaining_quantity <= 0:
            new_status = OrderStatus.FILLED
            event = OrderEvent.FILLED
        else:
            new_status = OrderStatus.PARTIALLY_FILLED
            event = OrderEvent.PARTIALLY_FILLED

        # Transition to new status
        self.transition_order(
            order_id,
            new_status,
            event,
            details={
                "filled_quantity": filled_quantity,
                "fill_price": fill_price,
                "commission": commission,
                "total_filled": lifecycle_state.filled_quantity,
                "remaining": lifecycle_state.remaining_quantity,
            },
        )

        return lifecycle_state

    def cancel_order(
        self, order_id: str, reason: str = "User requested", triggered_by: str = "user"
    ) -> OrderLifecycleState:
        """Cancel an order."""
        lifecycle_state = self.get_order_state(order_id)
        if not lifecycle_state:
            raise OrderLifecycleError(f"Order {order_id} not found")

        if not lifecycle_state.can_cancel:
            raise OrderLifecycleError(f"Order {order_id} cannot be cancelled")

        return self.transition_order(
            order_id,
            OrderStatus.CANCELLED,
            OrderEvent.CANCELLED,
            details={"reason": reason},
            triggered_by=triggered_by,
        )

    def reject_order(
        self, order_id: str, reason: str, triggered_by: str = "system"
    ) -> OrderLifecycleState:
        """Reject an order."""
        lifecycle_state = self.get_order_state(order_id)
        if not lifecycle_state:
            raise OrderLifecycleError(f"Order {order_id} not found")

        lifecycle_state.error_messages.append(reason)

        return self.transition_order(
            order_id,
            OrderStatus.REJECTED,
            OrderEvent.REJECTED,
            details={"reason": reason},
            triggered_by=triggered_by,
        )

    def expire_order(
        self, order_id: str, reason: str = "Order expired", triggered_by: str = "system"
    ) -> OrderLifecycleState:
        """Expire an order."""
        return self.transition_order(
            order_id,
            OrderStatus.EXPIRED,
            OrderEvent.EXPIRED,
            details={"reason": reason},
            triggered_by=triggered_by,
        )

    def trigger_order(
        self, order_id: str, trigger_price: float, triggered_by: str = "market"
    ) -> OrderLifecycleState:
        """Mark an order as triggered."""
        return self.transition_order(
            order_id,
            OrderStatus.TRIGGERED,
            OrderEvent.TRIGGERED,
            details={"trigger_price": trigger_price},
            triggered_by=triggered_by,
        )

    def get_order_state(self, order_id: str) -> OrderLifecycleState | None:
        """Get the current lifecycle state of an order."""
        if order_id in self.active_orders:
            return self.active_orders[order_id]
        elif order_id in self.completed_orders:
            return self.completed_orders[order_id]
        else:
            return None

    def get_active_orders(self) -> dict[str, OrderLifecycleState]:
        """Get all active (non-terminal) orders."""
        return self.active_orders.copy()

    def get_orders_by_status(self, status: OrderStatus) -> list[OrderLifecycleState]:
        """Get all orders with a specific status."""
        result = []
        for lifecycle_state in self.active_orders.values():
            if lifecycle_state.current_status == status:
                result.append(lifecycle_state)
        return result

    def get_orders_by_symbol(self, symbol: str) -> list[OrderLifecycleState]:
        """Get all orders for a specific symbol."""
        result = []
        for lifecycle_state in self.active_orders.values():
            if lifecycle_state.order.symbol == symbol:
                result.append(lifecycle_state)
        return result

    def register_event_callback(self, event: OrderEvent, callback: Callable) -> None:
        """Register a callback for order events."""
        self.event_callbacks[event].append(callback)

    def cleanup_completed_orders(self, older_than_hours: int = 24) -> int:
        """Clean up completed orders older than specified hours."""
        cutoff_time = datetime.utcnow() - timedelta(hours=older_than_hours)

        orders_to_remove = []
        for order_id, lifecycle_state in self.completed_orders.items():
            if lifecycle_state.last_updated < cutoff_time:
                orders_to_remove.append(order_id)

        for order_id in orders_to_remove:
            del self.completed_orders[order_id]

        logger.info(f"Cleaned up {len(orders_to_remove)} completed orders")
        return len(orders_to_remove)

    def get_statistics(self) -> dict:
        """Get statistics about order lifecycle."""
        total_orders = len(self.active_orders) + len(self.completed_orders)

        status_counts = {}
        for status in OrderStatus:
            status_counts[status.value] = len(self.get_orders_by_status(status))

        return {
            "total_orders": total_orders,
            "active_orders": len(self.active_orders),
            "completed_orders": len(self.completed_orders),
            "status_breakdown": status_counts,
        }

    def _define_valid_transitions(self) -> dict[OrderStatus, set[OrderStatus]]:
        """Define valid state transitions."""
        return {
            OrderStatus.PENDING: {
                OrderStatus.TRIGGERED,
                OrderStatus.FILLED,
                OrderStatus.PARTIALLY_FILLED,
                OrderStatus.CANCELLED,
                OrderStatus.REJECTED,
                OrderStatus.EXPIRED,
            },
            OrderStatus.TRIGGERED: {
                OrderStatus.FILLED,
                OrderStatus.PARTIALLY_FILLED,
                OrderStatus.CANCELLED,
                OrderStatus.REJECTED,
                OrderStatus.EXPIRED,
            },
            OrderStatus.PARTIALLY_FILLED: {
                OrderStatus.FILLED,
                OrderStatus.CANCELLED,
                OrderStatus.EXPIRED,
            },
            OrderStatus.FILLED: set(),  # Terminal state
            OrderStatus.CANCELLED: set(),  # Terminal state
            OrderStatus.REJECTED: set(),  # Terminal state
            OrderStatus.EXPIRED: set(),  # Terminal state
        }

    def _is_valid_transition(
        self, from_status: OrderStatus, to_status: OrderStatus
    ) -> bool:
        """Check if a state transition is valid."""
        return to_status in self.valid_transitions.get(from_status, set())

    def _update_lifecycle_flags(self, lifecycle_state: OrderLifecycleState) -> None:
        """Update lifecycle flags based on current status."""
        status = lifecycle_state.current_status

        # Can cancel?
        lifecycle_state.can_cancel = status in {
            OrderStatus.PENDING,
            OrderStatus.TRIGGERED,
            OrderStatus.PARTIALLY_FILLED,
        }

        # Can modify?
        lifecycle_state.can_modify = status in {
            OrderStatus.PENDING,
            OrderStatus.PARTIALLY_FILLED,
        }

        # Is terminal?
        lifecycle_state.is_terminal = status in self.terminal_states

    def _record_transition(
        self,
        order_id: str,
        from_status: OrderStatus | None,
        to_status: OrderStatus,
        event: OrderEvent,
        details: dict,
        triggered_by: str = "system",
    ) -> None:
        """Record a state transition."""
        lifecycle_state = self.active_orders.get(order_id) or self.completed_orders.get(
            order_id
        )
        if not lifecycle_state:
            return

        transition = OrderStateTransition(
            from_status=from_status or OrderStatus.PENDING,
            to_status=to_status,
            event=event,
            timestamp=datetime.utcnow(),
            details=details,
            triggered_by=triggered_by,
        )

        lifecycle_state.transitions.append(transition)

    def _trigger_event_callbacks(
        self, event: OrderEvent, lifecycle_state: OrderLifecycleState
    ) -> None:
        """Trigger registered callbacks for an event."""
        callbacks = self.event_callbacks.get(event, [])
        for callback in callbacks:
            try:
                callback(lifecycle_state, event)
            except Exception as e:
                logger.error(f"Error in event callback for {event}: {e}", exc_info=True)


# Global lifecycle manager instance
order_lifecycle_manager = OrderLifecycleManager()


def get_order_lifecycle_manager() -> OrderLifecycleManager:
    """Get the global order lifecycle manager instance."""
    return order_lifecycle_manager


class OrderStateMachine:
    """
    A stub for the OrderStateMachine.
    """
    pass
