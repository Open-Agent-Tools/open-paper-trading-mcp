"""
Memory-efficient order state tracking system.

This module provides a lightweight, memory-efficient system for tracking
order states and transitions without holding excessive data in memory.
"""

import asyncio
import contextlib
import logging
import threading
import weakref
from collections import defaultdict, deque
from collections.abc import Callable
from dataclasses import dataclass
from datetime import datetime, timedelta
from enum import Enum
from typing import Any, cast

from ..schemas.orders import OrderStatus

logger = logging.getLogger(__name__)


class StateChangeEvent(str, Enum):
    """Order state change events."""

    CREATED = "created"
    SUBMITTED = "submitted"
    TRIGGERED = "triggered"
    PARTIALLY_FILLED = "partially_filled"
    FILLED = "filled"
    CANCELLED = "cancelled"
    REJECTED = "rejected"
    EXPIRED = "expired"


@dataclass
class OrderStateSnapshot:
    """Lightweight order state snapshot."""

    order_id: str
    status: OrderStatus
    timestamp: datetime
    event: StateChangeEvent

    # Optional context data (kept minimal)
    symbol: str | None = None
    quantity: int | None = None
    filled_quantity: int | None = None
    metadata: dict[str, Any] | None = None

    def __post_init__(self) -> None:
        if self.metadata is None:
            self.metadata = {}


@dataclass
class OrderStateTrackingConfig:
    """Configuration for order state tracking."""

    max_snapshots_per_order: int = 50
    max_total_snapshots: int = 10000
    max_history_days: int = 7
    cleanup_interval_minutes: int = 30
    enable_metrics: bool = True
    enable_callbacks: bool = True


class MemoryEfficientOrderTracker:
    """
    Memory-efficient order state tracking system.

    Features:
    - Bounded memory usage with automatic cleanup
    - Lightweight state snapshots
    - Event-based state change notifications
    - Efficient querying and filtering
    - Weak references to prevent memory leaks
    """

    def __init__(self, config: OrderStateTrackingConfig | None = None):
        self.config = config or OrderStateTrackingConfig()

        # Core state storage - bounded for memory efficiency
        self.order_snapshots: dict[str, deque[OrderStateSnapshot]] = defaultdict(
            lambda: deque(maxlen=self.config.max_snapshots_per_order)
        )

        # Current state cache for fast lookups
        self.current_states: dict[str, OrderStateSnapshot] = {}

        # Event callbacks using weak references
        self.state_change_callbacks: list[
            weakref.ReferenceType[Callable[..., Any]]
        ] = []

        # Metrics tracking
        self.metrics = {
            "total_events": 0,
            "events_by_type": defaultdict(int),
            "active_orders": 0,
            "memory_usage_kb": 0,
            "last_cleanup": datetime.utcnow(),
        }

        # Thread safety
        self._lock = threading.RLock()

        # Background cleanup task
        self._cleanup_task: asyncio.Task[None] | None = None
        self._is_running = False

    async def start(self) -> None:
        """Start the order state tracker."""
        if self._is_running:
            logger.warning("Order state tracker is already running")
            return

        self._is_running = True

        # Start cleanup task
        self._cleanup_task = asyncio.create_task(self._cleanup_loop())

        logger.info("Memory-efficient order state tracker started")

    async def stop(self) -> None:
        """Stop the order state tracker."""
        if not self._is_running:
            return

        self._is_running = False

        # Cancel cleanup task
        if self._cleanup_task:
            self._cleanup_task.cancel()
            with contextlib.suppress(asyncio.CancelledError):
                await self._cleanup_task

        logger.info("Order state tracker stopped")

    def track_state_change(
        self,
        order_id: str,
        new_status: OrderStatus,
        event: StateChangeEvent,
        symbol: str | None = None,
        quantity: int | None = None,
        filled_quantity: int | None = None,
        metadata: dict[str, Any] | None = None,
    ) -> None:
        """Track an order state change efficiently."""
        with self._lock:
            # Create snapshot
            snapshot = OrderStateSnapshot(
                order_id=order_id,
                status=new_status,
                timestamp=datetime.utcnow(),
                event=event,
                symbol=symbol,
                quantity=quantity,
                filled_quantity=filled_quantity,
                metadata=metadata or {},
            )

            # Add to order history (bounded deque automatically manages memory)
            self.order_snapshots[order_id].append(snapshot)

            # Update current state cache
            self.current_states[order_id] = snapshot

            # Update metrics
            if self.config.enable_metrics:
                self.metrics["total_events"] = (
                    cast(int, self.metrics.get("total_events", 0)) + 1
                )
                events_by_type = self.metrics["events_by_type"]
                if isinstance(events_by_type, defaultdict):
                    events_by_type[event.value] += 1
                self.metrics["active_orders"] = len(self.current_states)

        # Trigger callbacks asynchronously (only if event loop is running)
        if self.config.enable_callbacks:
            try:
                loop = asyncio.get_running_loop()
                loop.create_task(self._notify_callbacks(snapshot))
            except RuntimeError:
                # No event loop running, skip async notifications
                # This can happen during testing or synchronous usage
                pass

    def get_current_state(self, order_id: str) -> OrderStateSnapshot | None:
        """Get current state of an order."""
        with self._lock:
            return self.current_states.get(order_id)

    def get_order_history(
        self, order_id: str, limit: int | None = None
    ) -> list[OrderStateSnapshot]:
        """Get state history for an order."""
        with self._lock:
            snapshots = list(self.order_snapshots.get(order_id, []))

            if limit:
                snapshots = snapshots[-limit:]

            return snapshots

    def get_orders_by_status(self, status: OrderStatus) -> list[str]:
        """Get order IDs with specific status."""
        with self._lock:
            return [
                order_id
                for order_id, snapshot in self.current_states.items()
                if snapshot.status == status
            ]

    def get_orders_by_symbol(self, symbol: str) -> list[str]:
        """Get order IDs for specific symbol."""
        with self._lock:
            return [
                order_id
                for order_id, snapshot in self.current_states.items()
                if snapshot.symbol == symbol
            ]

    def get_recent_events(
        self,
        event_type: StateChangeEvent | None = None,
        symbol: str | None = None,
        minutes: int = 60,
        limit: int = 100,
    ) -> list[OrderStateSnapshot]:
        """Get recent state change events with filtering."""
        cutoff = datetime.utcnow() - timedelta(minutes=minutes)
        events: list[OrderStateSnapshot] = []

        with self._lock:
            for order_snapshots in self.order_snapshots.values():
                for snapshot in order_snapshots:
                    # Time filter
                    if snapshot.timestamp < cutoff:
                        continue

                    # Event type filter
                    if event_type and snapshot.event != event_type:
                        continue

                    # Symbol filter
                    if symbol and snapshot.symbol != symbol:
                        continue

                    events.append(snapshot)

                    if len(events) >= limit:
                        break

                if len(events) >= limit:
                    break

        # Sort by timestamp descending
        return sorted(events, key=lambda x: x.timestamp, reverse=True)

    def get_order_transitions(
        self, order_id: str
    ) -> list[tuple[OrderStatus, OrderStatus]]:
        """Get status transitions for an order."""
        history = self.get_order_history(order_id)

        transitions: list[tuple[OrderStatus, OrderStatus]] = []
        for i in range(1, len(history)):
            prev_status = history[i - 1].status
            curr_status = history[i].status

            if prev_status != curr_status:
                transitions.append((prev_status, curr_status))

        return transitions

    def calculate_order_duration(self, order_id: str) -> timedelta | None:
        """Calculate time from creation to completion."""
        history = self.get_order_history(order_id)

        if len(history) < 2:
            return None

        start_time = history[0].timestamp

        # Find completion event
        for snapshot in reversed(history):
            if snapshot.status in [
                OrderStatus.FILLED,
                OrderStatus.CANCELLED,
                OrderStatus.REJECTED,
            ]:
                return snapshot.timestamp - start_time

        # Order still active
        return datetime.utcnow() - start_time

    def get_fill_rate_by_symbol(self, hours: int = 24) -> dict[str, dict[str, Any]]:
        """Calculate fill rates by symbol for recent orders."""
        cutoff = datetime.utcnow() - timedelta(hours=hours)
        symbol_stats: dict[str, dict[str, int]] = defaultdict(
            lambda: {"total": 0, "filled": 0}
        )

        with self._lock:
            for snapshot in self.current_states.values():
                if snapshot.timestamp < cutoff or not snapshot.symbol:
                    continue

                symbol_stats[snapshot.symbol]["total"] += 1

                if snapshot.status == OrderStatus.FILLED:
                    symbol_stats[snapshot.symbol]["filled"] += 1

        # Calculate rates
        result: dict[str, dict[str, Any]] = {}
        for symbol, stats in symbol_stats.items():
            result[symbol] = {
                "total_orders": stats["total"],
                "filled_orders": stats["filled"],
                "fill_rate": (
                    stats["filled"] / stats["total"] if stats["total"] > 0 else 0
                ),
            }

        return result

    def get_performance_metrics(self) -> dict[str, Any]:
        """Get tracker performance metrics."""
        with self._lock:
            # Calculate memory usage estimate
            total_snapshots = sum(
                len(deque_) for deque_ in self.order_snapshots.values()
            )
            estimated_memory_kb = (
                total_snapshots * 0.5  # Rough estimate per snapshot
                + len(self.current_states) * 0.3  # Current state cache
            )

            self.metrics["memory_usage_kb"] = estimated_memory_kb

            return {
                **self.metrics,
                "total_snapshots": total_snapshots,
                "tracked_orders": len(self.order_snapshots),
                "active_orders": len(self.current_states),
                "avg_snapshots_per_order": total_snapshots
                / max(len(self.order_snapshots), 1),
            }

    def register_callback(self, callback: Callable[[OrderStateSnapshot], None]) -> None:
        """Register state change callback using weak reference."""
        if not self.config.enable_callbacks:
            return

        # Use weak reference to prevent memory leaks
        weak_callback = weakref.ref(callback)
        self.state_change_callbacks.append(weak_callback)

    def cleanup_old_data(self, force: bool = False) -> dict[str, int]:
        """Clean up old state data to manage memory."""
        with self._lock:
            if not force:
                # Check if cleanup is needed
                total_snapshots = sum(
                    len(deque_) for deque_ in self.order_snapshots.values()
                )
                if total_snapshots < self.config.max_total_snapshots:
                    return {"orders_cleaned": 0, "snapshots_removed": 0}

            cutoff = datetime.utcnow() - timedelta(days=self.config.max_history_days)

            orders_cleaned = 0
            snapshots_removed = 0
            orders_to_remove: list[str] = []

            for order_id, snapshots in self.order_snapshots.items():
                # Remove old snapshots
                original_length = len(snapshots)

                # Keep snapshots that are recent or represent final states
                filtered_snapshots: deque[OrderStateSnapshot] = deque(
                    maxlen=self.config.max_snapshots_per_order
                )

                for snapshot in snapshots:
                    # Keep recent snapshots
                    if snapshot.timestamp >= cutoff or snapshot.status in [
                        OrderStatus.FILLED,
                        OrderStatus.CANCELLED,
                        OrderStatus.REJECTED,
                    ]:
                        filtered_snapshots.append(snapshot)

                # Update snapshots
                if filtered_snapshots:
                    self.order_snapshots[order_id] = filtered_snapshots
                    snapshots_removed += original_length - len(filtered_snapshots)
                else:
                    # Mark for removal
                    orders_to_remove.append(order_id)
                    snapshots_removed += original_length
                    orders_cleaned += 1

            # Remove empty order tracking
            for order_id in orders_to_remove:
                del self.order_snapshots[order_id]
                if order_id in self.current_states:
                    del self.current_states[order_id]

            # Update metrics
            self.metrics["last_cleanup"] = datetime.utcnow()
            self.metrics["active_orders"] = len(self.current_states)

            logger.info(
                f"Cleanup completed: {orders_cleaned} orders, {snapshots_removed} snapshots removed"
            )

            return {
                "orders_cleaned": orders_cleaned,
                "snapshots_removed": snapshots_removed,
            }

    async def _cleanup_loop(self) -> None:
        """Background cleanup loop."""
        logger.info("Order state tracker cleanup loop started")

        while self._is_running:
            try:
                await asyncio.sleep(self.config.cleanup_interval_minutes * 60)

                if self._is_running:
                    self.cleanup_old_data()

            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"Error in cleanup loop: {e}", exc_info=True)
                await asyncio.sleep(60)  # Wait before retrying

        logger.info("Order state tracker cleanup loop stopped")

    async def _notify_callbacks(self, snapshot: OrderStateSnapshot) -> None:
        """Notify registered callbacks of state changes."""
        # Clean up dead weak references
        self.state_change_callbacks = [
            ref for ref in self.state_change_callbacks if ref() is not None
        ]

        # Call active callbacks
        for weak_callback in self.state_change_callbacks[
            :
        ]:  # Copy to avoid modification during iteration
            callback = weak_callback()
            if callback:
                try:
                    if asyncio.iscoroutinefunction(callback):
                        await callback(snapshot)
                    else:
                        callback(snapshot)
                except Exception as e:
                    logger.error(f"Error in state change callback: {e}")
                    # Remove failing callback
                    with contextlib.suppress(ValueError):
                        self.state_change_callbacks.remove(weak_callback)

    def reset(self) -> None:
        """Reset all tracking data (useful for testing)."""
        with self._lock:
            self.order_snapshots.clear()
            self.current_states.clear()
            self.metrics = {
                "total_events": 0,
                "events_by_type": defaultdict(int),
                "active_orders": 0,
                "memory_usage_kb": 0,
                "last_cleanup": datetime.utcnow(),
            }

        logger.info("Order state tracker reset")


# Global order state tracker
order_state_tracker: MemoryEfficientOrderTracker | None = None


def get_order_state_tracker() -> MemoryEfficientOrderTracker:
    """Get the global order state tracker."""
    global order_state_tracker
    if order_state_tracker is None:
        order_state_tracker = MemoryEfficientOrderTracker()
    return order_state_tracker


def initialize_order_state_tracker(
    config: OrderStateTrackingConfig | None = None,
) -> MemoryEfficientOrderTracker:
    """Initialize the global order state tracker."""
    global order_state_tracker
    order_state_tracker = MemoryEfficientOrderTracker(config)
    return order_state_tracker
