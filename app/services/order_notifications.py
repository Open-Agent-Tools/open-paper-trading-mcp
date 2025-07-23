"""
Order status tracking and notification system.

This module provides real-time notifications and tracking for order status changes,
execution updates, and important trading events.
"""

import asyncio
import contextlib
import json
import logging
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Any

from .order_lifecycle import OrderEvent, OrderLifecycleState

logger = logging.getLogger(__name__)


class NotificationChannel(str, Enum):
    """Available notification channels."""

    WEBSOCKET = "websocket"
    EMAIL = "email"
    SMS = "sms"
    WEBHOOK = "webhook"
    LOG = "log"
    DATABASE = "database"


class NotificationPriority(str, Enum):
    """Notification priority levels."""

    LOW = "low"
    NORMAL = "normal"
    HIGH = "high"
    URGENT = "urgent"


@dataclass
class NotificationRule:
    """Defines when and how to send notifications."""

    id: str
    name: str
    events: set[OrderEvent]
    channels: set[NotificationChannel]
    priority: NotificationPriority = NotificationPriority.NORMAL
    conditions: dict[str, Any] = field(default_factory=dict)  # Additional conditions
    enabled: bool = True
    created_at: datetime = field(default_factory=datetime.utcnow)


@dataclass
class Notification:
    """A notification message."""

    id: str
    rule_id: str
    event: OrderEvent
    order_id: str
    title: str
    message: str
    priority: NotificationPriority
    channels: set[NotificationChannel]
    data: dict[str, Any] = field(default_factory=dict)
    created_at: datetime = field(default_factory=datetime.utcnow)
    sent_at: datetime | None = None
    failed_channels: set[NotificationChannel] = field(default_factory=set)
    retry_count: int = 0
    max_retries: int = 3


class NotificationSender(ABC):
    """Abstract base class for notification senders."""

    @abstractmethod
    async def send(self, notification: Notification) -> bool:
        """Send a notification. Returns True if successful."""
        pass

    @abstractmethod
    def get_channel(self) -> NotificationChannel:
        """Get the notification channel this sender handles."""
        pass


class LogNotificationSender(NotificationSender):
    """Sends notifications to the application log."""

    async def send(self, notification: Notification) -> bool:
        """Send notification to log."""
        try:
            log_level = {
                NotificationPriority.LOW: logging.DEBUG,
                NotificationPriority.NORMAL: logging.INFO,
                NotificationPriority.HIGH: logging.WARNING,
                NotificationPriority.URGENT: logging.ERROR,
            }.get(notification.priority, logging.INFO)

            logger.log(
                log_level,
                f"Order Notification [{notification.priority.upper()}]: {notification.title} - {notification.message}",
            )
            return True

        except Exception as e:
            logger.error(f"Failed to send log notification: {e}")
            return False

    def get_channel(self) -> NotificationChannel:
        return NotificationChannel.LOG


class WebSocketNotificationSender(NotificationSender):
    """Sends notifications via WebSocket."""

    def __init__(self) -> None:
        self.connected_clients: set[Any] = set()  # WebSocket connections

    async def send(self, notification: Notification) -> bool:
        """Send notification to all connected WebSocket clients."""
        if not self.connected_clients:
            return True  # No clients to notify

        message = {
            "type": "order_notification",
            "notification_id": notification.id,
            "event": notification.event.value,
            "order_id": notification.order_id,
            "title": notification.title,
            "message": notification.message,
            "priority": notification.priority.value,
            "timestamp": notification.created_at.isoformat(),
            "data": notification.data,
        }

        failed_clients = []
        success_count = 0

        for client in self.connected_clients:
            try:
                await client.send_text(json.dumps(message))
                success_count += 1
            except Exception as e:
                logger.error(f"Failed to send WebSocket notification to client: {e}")
                failed_clients.append(client)

        # Remove failed clients
        for client in failed_clients:
            self.connected_clients.discard(client)

        return success_count > 0

    def add_client(self, client: Any) -> None:
        """Add a WebSocket client."""
        self.connected_clients.add(client)

    def remove_client(self, client: Any) -> None:
        """Remove a WebSocket client."""
        self.connected_clients.discard(client)

    def get_channel(self) -> NotificationChannel:
        return NotificationChannel.WEBSOCKET


class WebhookNotificationSender(NotificationSender):
    """Sends notifications via HTTP webhook."""

    def __init__(self, webhook_url: str):
        self.webhook_url = webhook_url

    async def send(self, notification: Notification) -> bool:
        """Send notification to webhook URL."""
        try:
            import aiohttp

            payload = {
                "notification_id": notification.id,
                "event": notification.event.value,
                "order_id": notification.order_id,
                "title": notification.title,
                "message": notification.message,
                "priority": notification.priority.value,
                "timestamp": notification.created_at.isoformat(),
                "data": notification.data,
            }

            async with (
                aiohttp.ClientSession() as session,
                session.post(
                    self.webhook_url,
                    json=payload,
                    timeout=aiohttp.ClientTimeout(total=10),
                ) as response,
            ):
                if response.status < 400:
                    return True
                else:
                    logger.error(f"Webhook returned status {response.status}")
                    return False

        except Exception as e:
            logger.error(f"Failed to send webhook notification: {e}")
            return False

    def get_channel(self) -> NotificationChannel:
        return NotificationChannel.WEBHOOK


class OrderNotificationManager:
    """
    Manages order notifications and status tracking.

    This class handles:
    - Notification rules and conditions
    - Multiple notification channels
    - Retry logic for failed notifications
    - Real-time order status updates
    """

    def __init__(self) -> None:
        self.notification_rules: dict[str, NotificationRule] = {}
        self.senders: dict[NotificationChannel, NotificationSender] = {}
        self.notification_queue: asyncio.Queue[Notification] = asyncio.Queue()
        self.notification_history: list[Notification] = []

        # Worker task for processing notifications
        self.worker_task: asyncio.Task[None] | None = None
        self.is_running = False

        # Initialize default senders
        self._initialize_default_senders()
        self._create_default_rules()

    def _initialize_default_senders(self) -> None:
        """Initialize default notification senders."""
        self.senders[NotificationChannel.LOG] = LogNotificationSender()
        self.senders[NotificationChannel.WEBSOCKET] = WebSocketNotificationSender()

    def _create_default_rules(self) -> None:
        """Create default notification rules."""

        # High priority events that should always be logged
        self.add_rule(
            NotificationRule(
                id="critical_events",
                name="Critical Order Events",
                events={OrderEvent.FILLED, OrderEvent.REJECTED, OrderEvent.CANCELLED},
                channels={NotificationChannel.LOG, NotificationChannel.WEBSOCKET},
                priority=NotificationPriority.HIGH,
            )
        )

        # Trigger events for advanced orders
        self.add_rule(
            NotificationRule(
                id="trigger_events",
                name="Order Trigger Events",
                events={OrderEvent.TRIGGERED},
                channels={NotificationChannel.LOG, NotificationChannel.WEBSOCKET},
                priority=NotificationPriority.NORMAL,
            )
        )

        # Partial fill notifications
        self.add_rule(
            NotificationRule(
                id="partial_fills",
                name="Partial Fill Notifications",
                events={OrderEvent.PARTIALLY_FILLED},
                channels={NotificationChannel.LOG, NotificationChannel.WEBSOCKET},
                priority=NotificationPriority.NORMAL,
            )
        )

        # Error notifications
        self.add_rule(
            NotificationRule(
                id="error_events",
                name="Order Error Events",
                events={OrderEvent.ERROR},
                channels={NotificationChannel.LOG, NotificationChannel.WEBSOCKET},
                priority=NotificationPriority.URGENT,
            )
        )

    async def start(self) -> None:
        """Start the notification manager."""
        if self.is_running:
            logger.warning("Notification manager is already running")
            return

        self.is_running = True
        self.worker_task = asyncio.create_task(self._notification_worker())
        logger.info("Order notification manager started")

    async def stop(self) -> None:
        """Stop the notification manager."""
        if not self.is_running:
            return

        self.is_running = False

        if self.worker_task:
            self.worker_task.cancel()
            with contextlib.suppress(asyncio.CancelledError):
                await self.worker_task

        logger.info("Order notification manager stopped")

    def add_rule(self, rule: NotificationRule) -> None:
        """Add a notification rule."""
        self.notification_rules[rule.id] = rule
        logger.info(f"Added notification rule: {rule.name}")

    def remove_rule(self, rule_id: str) -> bool:
        """Remove a notification rule."""
        if rule_id in self.notification_rules:
            del self.notification_rules[rule_id]
            logger.info(f"Removed notification rule: {rule_id}")
            return True
        return False

    def add_sender(self, sender: NotificationSender) -> None:
        """Add a notification sender."""
        channel = sender.get_channel()
        self.senders[channel] = sender
        logger.info(f"Added notification sender for channel: {channel}")

    async def handle_order_event(
        self, lifecycle_state: OrderLifecycleState, event: OrderEvent
    ) -> None:
        """Handle an order event and create notifications if rules match."""
        try:
            matching_rules = self._find_matching_rules(lifecycle_state, event)

            for rule in matching_rules:
                notification = self._create_notification(rule, lifecycle_state, event)
                await self.notification_queue.put(notification)

        except Exception as e:
            logger.error(
                f"Error handling order event {event} for order {lifecycle_state.order.id}: {e}"
            )

    def _find_matching_rules(
        self, lifecycle_state: OrderLifecycleState, event: OrderEvent
    ) -> list[NotificationRule]:
        """Find notification rules that match the event and conditions."""
        matching_rules = []

        for rule in self.notification_rules.values():
            if not rule.enabled:
                continue

            if event not in rule.events:
                continue

            # Check additional conditions
            if not self._check_conditions(rule, lifecycle_state, event):
                continue

            matching_rules.append(rule)

        return matching_rules

    def _check_conditions(
        self,
        rule: NotificationRule,
        lifecycle_state: OrderLifecycleState,
        event: OrderEvent,
    ) -> bool:
        """Check if rule conditions are met."""
        conditions = rule.conditions

        # Symbol filter
        if "symbols" in conditions:
            if lifecycle_state.order.symbol not in conditions["symbols"]:
                return False

        # Order type filter
        if "order_types" in conditions:
            if lifecycle_state.order.order_type not in conditions["order_types"]:
                return False

        # Minimum quantity filter
        if "min_quantity" in conditions:
            if abs(lifecycle_state.order.quantity) < conditions["min_quantity"]:
                return False

        # Status filter
        if "statuses" in conditions:
            if lifecycle_state.current_status not in conditions["statuses"]:
                return False

        return True

    def _create_notification(
        self,
        rule: NotificationRule,
        lifecycle_state: OrderLifecycleState,
        event: OrderEvent,
    ) -> Notification:
        """Create a notification from a rule and order event."""
        import uuid

        order = lifecycle_state.order

        # Create title and message based on event
        title, message = self._format_notification_content(lifecycle_state, event)

        # Additional data to include
        data = {
            "symbol": order.symbol,
            "order_type": order.order_type.value,
            "quantity": order.quantity,
            "price": order.price,
            "current_status": lifecycle_state.current_status.value,
            "filled_quantity": lifecycle_state.filled_quantity,
            "remaining_quantity": lifecycle_state.remaining_quantity,
            "average_fill_price": lifecycle_state.average_fill_price,
            "total_commission": lifecycle_state.total_commission,
        }

        return Notification(
            id=str(uuid.uuid4()),
            rule_id=rule.id,
            event=event,
            order_id=order.id or "unknown",
            title=title,
            message=message,
            priority=rule.priority,
            channels=rule.channels.copy(),
            data=data,
        )

    def _format_notification_content(
        self, lifecycle_state: OrderLifecycleState, event: OrderEvent
    ) -> tuple[str, str]:
        """Format notification title and message."""
        order = lifecycle_state.order
        symbol = order.symbol
        quantity = abs(order.quantity)
        order_type = order.order_type.value.replace("_", " ").title()

        if event == OrderEvent.FILLED:
            title = f"Order Filled: {symbol}"
            message = f"{order_type} order for {quantity} shares of {symbol} has been completely filled"
            if lifecycle_state.average_fill_price:
                message += (
                    f" at average price ${lifecycle_state.average_fill_price:.4f}"
                )

        elif event == OrderEvent.PARTIALLY_FILLED:
            title = f"Partial Fill: {symbol}"
            filled = lifecycle_state.filled_quantity
            remaining = lifecycle_state.remaining_quantity
            message = f"{order_type} order for {symbol}: {filled} shares filled, {remaining} remaining"

        elif event == OrderEvent.CANCELLED:
            title = f"Order Cancelled: {symbol}"
            message = f"{order_type} order for {quantity} shares of {symbol} has been cancelled"

        elif event == OrderEvent.REJECTED:
            title = f"Order Rejected: {symbol}"
            message = f"{order_type} order for {quantity} shares of {symbol} has been rejected"
            if lifecycle_state.error_messages:
                message += f": {lifecycle_state.error_messages[-1]}"

        elif event == OrderEvent.TRIGGERED:
            title = f"Order Triggered: {symbol}"
            message = f"{order_type} order for {quantity} shares of {symbol} has been triggered"

        elif event == OrderEvent.EXPIRED:
            title = f"Order Expired: {symbol}"
            message = (
                f"{order_type} order for {quantity} shares of {symbol} has expired"
            )

        elif event == OrderEvent.ERROR:
            title = f"Order Error: {symbol}"
            message = f"Error occurred with {order_type} order for {quantity} shares of {symbol}"
            if lifecycle_state.error_messages:
                message += f": {lifecycle_state.error_messages[-1]}"
        else:
            title = f"Order Update: {symbol}"
            message = (
                f"{order_type} order for {quantity} shares of {symbol} - {event.value}"
            )

        return title, message

    async def _notification_worker(self) -> None:
        """Worker task that processes notifications from the queue."""
        logger.info("Notification worker started")

        while self.is_running:
            try:
                # Wait for notification with timeout
                try:
                    notification = await asyncio.wait_for(
                        self.notification_queue.get(), timeout=1.0
                    )
                except TimeoutError:
                    continue

                # Send notification to all channels
                await self._send_notification(notification)

                # Mark task as done
                self.notification_queue.task_done()

            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"Error in notification worker: {e}", exc_info=True)

        logger.info("Notification worker stopped")

    async def _send_notification(self, notification: Notification) -> None:
        """Send a notification to all specified channels."""
        success = False

        for channel in notification.channels:
            sender = self.senders.get(channel)
            if not sender:
                logger.warning(f"No sender configured for channel: {channel}")
                notification.failed_channels.add(channel)
                continue

            try:
                if await sender.send(notification):
                    success = True
                else:
                    notification.failed_channels.add(channel)

            except Exception as e:
                logger.error(f"Error sending notification via {channel}: {e}")
                notification.failed_channels.add(channel)

        if success:
            notification.sent_at = datetime.utcnow()

        # Store in history
        self.notification_history.append(notification)

        # Limit history size
        if len(self.notification_history) > 1000:
            self.notification_history = self.notification_history[-500:]

    def get_statistics(self) -> dict[str, Any]:
        """Get notification statistics."""
        total_notifications = len(self.notification_history)
        successful_notifications = sum(
            1 for n in self.notification_history if n.sent_at
        )

        return {
            "total_notifications": total_notifications,
            "successful_notifications": successful_notifications,
            "success_rate": (
                successful_notifications / total_notifications
                if total_notifications
                else 0
            ),
            "active_rules": len(
                [r for r in self.notification_rules.values() if r.enabled]
            ),
            "total_rules": len(self.notification_rules),
            "connected_channels": list(self.senders.keys()),
            "queue_size": self.notification_queue.qsize(),
        }

    def get_recent_notifications(self, limit: int = 50) -> list[Notification]:
        """Get recent notifications."""
        return self.notification_history[-limit:] if self.notification_history else []


# Global notification manager instance
order_notification_manager = OrderNotificationManager()


def get_order_notification_manager() -> OrderNotificationManager:
    """Get the global order notification manager instance."""
    return order_notification_manager
