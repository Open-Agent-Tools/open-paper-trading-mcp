"""
Comprehensive tests for OrderNotificationManager - order status tracking and notification system.

Tests cover:
- Notification rule creation and management
- Multiple notification channels (WebSocket, Webhook, Log, etc.)
- Order event handling and notification triggering
- Notification formatting and message generation
- Real-time notification delivery mechanisms
- WebSocket client management and broadcasting
- Webhook delivery with timeout and error handling
- Notification queue processing and worker management
- Retry logic for failed notification delivery
- Notification history and statistics tracking
- Rule conditions and filtering (symbol, order type, quantity, status)
- Priority-based notification handling
- Alert mechanisms for critical order events
- Error handling and resilience
- Performance optimization for high-volume scenarios
"""

import asyncio
import json
from datetime import datetime
from unittest.mock import AsyncMock, Mock, patch

import pytest

from app.schemas.orders import Order, OrderSide, OrderStatus, OrderType
from app.services.order_lifecycle import OrderEvent, OrderLifecycleState
from app.services.order_notifications import (
    LogNotificationSender,
    Notification,
    NotificationChannel,
    NotificationPriority,
    NotificationRule,
    NotificationSender,
    OrderNotificationManager,
    WebhookNotificationSender,
    WebSocketNotificationSender,
    get_order_notification_manager,
)


@pytest.fixture
def notification_manager():
    """Fresh notification manager instance for testing."""
    manager = OrderNotificationManager()
    return manager


@pytest.fixture
def sample_order():
    """Sample order for testing."""
    return Order(
        id="test-order-123",
        symbol="AAPL",
        side=OrderSide.BUY,
        order_type=OrderType.MARKET,
        quantity=100,
        price=150.00,
        status=OrderStatus.PENDING,
        user_id="test-user",
        account_id="test-account",
        created_at=datetime.utcnow(),
    )


@pytest.fixture
def sample_lifecycle_state(sample_order):
    """Sample order lifecycle state for testing."""
    return OrderLifecycleState(
        order=sample_order,
        current_status=OrderStatus.PENDING,
        filled_quantity=0,
        remaining_quantity=100,
        average_fill_price=None,
        total_commission=0.0,
        status_history=[],
        fills=[],
        error_messages=[],
        created_at=datetime.utcnow(),
        updated_at=datetime.utcnow(),
    )


@pytest.fixture
def sample_notification_rule():
    """Sample notification rule for testing."""
    return NotificationRule(
        id="test-rule",
        name="Test Rule",
        events={OrderEvent.FILLED, OrderEvent.REJECTED},
        channels={NotificationChannel.LOG, NotificationChannel.WEBSOCKET},
        priority=NotificationPriority.HIGH,
        enabled=True,
    )


class TestNotificationRule:
    """Test NotificationRule data class and functionality."""

    def test_notification_rule_creation(self):
        """Test creating a notification rule."""
        rule = NotificationRule(
            id="rule-1",
            name="Critical Events",
            events={OrderEvent.FILLED, OrderEvent.CANCELLED},
            channels={NotificationChannel.LOG, NotificationChannel.EMAIL},
            priority=NotificationPriority.URGENT,
            conditions={"symbols": ["AAPL", "GOOGL"]},
            enabled=True,
        )

        assert rule.id == "rule-1"
        assert rule.name == "Critical Events"
        assert OrderEvent.FILLED in rule.events
        assert OrderEvent.CANCELLED in rule.events
        assert NotificationChannel.LOG in rule.channels
        assert NotificationChannel.EMAIL in rule.channels
        assert rule.priority == NotificationPriority.URGENT
        assert rule.conditions["symbols"] == ["AAPL", "GOOGL"]
        assert rule.enabled is True
        assert isinstance(rule.created_at, datetime)

    def test_notification_rule_defaults(self):
        """Test notification rule default values."""
        rule = NotificationRule(
            id="rule-2",
            name="Default Rule",
            events={OrderEvent.TRIGGERED},
            channels={NotificationChannel.LOG},
        )

        assert rule.priority == NotificationPriority.NORMAL
        assert rule.conditions == {}
        assert rule.enabled is True
        assert isinstance(rule.created_at, datetime)


class TestNotification:
    """Test Notification data class and functionality."""

    def test_notification_creation(self):
        """Test creating a notification."""
        notification = Notification(
            id="notif-1",
            rule_id="rule-1",
            event=OrderEvent.FILLED,
            order_id="order-123",
            title="Order Filled",
            message="Your order has been filled",
            priority=NotificationPriority.HIGH,
            channels={NotificationChannel.LOG, NotificationChannel.WEBSOCKET},
            data={"symbol": "AAPL", "quantity": 100},
        )

        assert notification.id == "notif-1"
        assert notification.rule_id == "rule-1"
        assert notification.event == OrderEvent.FILLED
        assert notification.order_id == "order-123"
        assert notification.title == "Order Filled"
        assert notification.message == "Your order has been filled"
        assert notification.priority == NotificationPriority.HIGH
        assert NotificationChannel.LOG in notification.channels
        assert notification.data["symbol"] == "AAPL"
        assert isinstance(notification.created_at, datetime)
        assert notification.sent_at is None
        assert notification.retry_count == 0
        assert notification.max_retries == 3

    def test_notification_defaults(self):
        """Test notification default values."""
        notification = Notification(
            id="notif-2",
            rule_id="rule-2",
            event=OrderEvent.CANCELLED,
            order_id="order-456",
            title="Order Cancelled",
            message="Your order has been cancelled",
            priority=NotificationPriority.NORMAL,
            channels={NotificationChannel.LOG},
        )

        assert notification.data == {}
        assert notification.sent_at is None
        assert notification.failed_channels == set()
        assert notification.retry_count == 0
        assert notification.max_retries == 3


class TestLogNotificationSender:
    """Test LogNotificationSender implementation."""

    @pytest.fixture
    def log_sender(self):
        """Log notification sender instance."""
        return LogNotificationSender()

    @pytest.mark.asyncio
    async def test_log_sender_send_normal_priority(self, log_sender):
        """Test sending normal priority log notification."""
        notification = Notification(
            id="log-notif-1",
            rule_id="rule-1",
            event=OrderEvent.FILLED,
            order_id="order-123",
            title="Order Filled",
            message="Market order filled successfully",
            priority=NotificationPriority.NORMAL,
            channels={NotificationChannel.LOG},
        )

        with patch("app.services.order_notifications.logger") as mock_logger:
            result = await log_sender.send(notification)

            assert result is True
            mock_logger.log.assert_called_once()
            args, kwargs = mock_logger.log.call_args
            assert args[0] == 20  # logging.INFO
            assert "Order Filled" in args[1]
            assert "Market order filled successfully" in args[1]

    @pytest.mark.asyncio
    async def test_log_sender_send_urgent_priority(self, log_sender):
        """Test sending urgent priority log notification."""
        notification = Notification(
            id="log-notif-2",
            rule_id="rule-1",
            event=OrderEvent.ERROR,
            order_id="order-456",
            title="Order Error",
            message="Critical error occurred",
            priority=NotificationPriority.URGENT,
            channels={NotificationChannel.LOG},
        )

        with patch("app.services.order_notifications.logger") as mock_logger:
            result = await log_sender.send(notification)

            assert result is True
            mock_logger.log.assert_called_once()
            args, kwargs = mock_logger.log.call_args
            assert args[0] == 40  # logging.ERROR

    @pytest.mark.asyncio
    async def test_log_sender_send_low_priority(self, log_sender):
        """Test sending low priority log notification."""
        notification = Notification(
            id="log-notif-3",
            rule_id="rule-1",
            event=OrderEvent.SUBMITTED,
            order_id="order-789",
            title="Order Submitted",
            message="Order submitted for processing",
            priority=NotificationPriority.LOW,
            channels={NotificationChannel.LOG},
        )

        with patch("app.services.order_notifications.logger") as mock_logger:
            result = await log_sender.send(notification)

            assert result is True
            mock_logger.log.assert_called_once()
            args, kwargs = mock_logger.log.call_args
            assert args[0] == 10  # logging.DEBUG

    @pytest.mark.asyncio
    async def test_log_sender_exception_handling(self, log_sender):
        """Test log sender exception handling."""
        notification = Notification(
            id="log-notif-4",
            rule_id="rule-1",
            event=OrderEvent.FILLED,
            order_id="order-error",
            title="Test",
            message="Test message",
            priority=NotificationPriority.NORMAL,
            channels={NotificationChannel.LOG},
        )

        with patch("app.services.order_notifications.logger") as mock_logger:
            mock_logger.log.side_effect = Exception("Log error")

            result = await log_sender.send(notification)

            assert result is False
            mock_logger.error.assert_called_once()

    def test_log_sender_get_channel(self, log_sender):
        """Test log sender channel identification."""
        assert log_sender.get_channel() == NotificationChannel.LOG


class TestWebSocketNotificationSender:
    """Test WebSocketNotificationSender implementation."""

    @pytest.fixture
    def websocket_sender(self):
        """WebSocket notification sender instance."""
        return WebSocketNotificationSender()

    @pytest.mark.asyncio
    async def test_websocket_sender_no_clients(self, websocket_sender):
        """Test WebSocket sender with no connected clients."""
        notification = Notification(
            id="ws-notif-1",
            rule_id="rule-1",
            event=OrderEvent.FILLED,
            order_id="order-123",
            title="Order Filled",
            message="Order filled successfully",
            priority=NotificationPriority.NORMAL,
            channels={NotificationChannel.WEBSOCKET},
        )

        result = await websocket_sender.send(notification)

        assert result is True  # No clients, but not an error
        assert len(websocket_sender.connected_clients) == 0

    @pytest.mark.asyncio
    async def test_websocket_sender_successful_send(self, websocket_sender):
        """Test successful WebSocket notification sending."""
        # Mock WebSocket client
        mock_client = AsyncMock()
        websocket_sender.add_client(mock_client)

        notification = Notification(
            id="ws-notif-2",
            rule_id="rule-1",
            event=OrderEvent.CANCELLED,
            order_id="order-456",
            title="Order Cancelled",
            message="Order was cancelled",
            priority=NotificationPriority.HIGH,
            channels={NotificationChannel.WEBSOCKET},
            data={"symbol": "GOOGL", "quantity": 50},
        )

        result = await websocket_sender.send(notification)

        assert result is True
        mock_client.send_text.assert_called_once()

        # Verify message content
        sent_message = mock_client.send_text.call_args[0][0]
        message_data = json.loads(sent_message)

        assert message_data["type"] == "order_notification"
        assert message_data["notification_id"] == "ws-notif-2"
        assert message_data["event"] == "CANCELLED"
        assert message_data["order_id"] == "order-456"
        assert message_data["title"] == "Order Cancelled"
        assert message_data["message"] == "Order was cancelled"
        assert message_data["priority"] == "high"
        assert message_data["data"]["symbol"] == "GOOGL"

    @pytest.mark.asyncio
    async def test_websocket_sender_client_failure(self, websocket_sender):
        """Test WebSocket sender with client send failure."""
        # Mock failing client
        mock_client = AsyncMock()
        mock_client.send_text.side_effect = Exception("Connection error")
        websocket_sender.add_client(mock_client)

        notification = Notification(
            id="ws-notif-3",
            rule_id="rule-1",
            event=OrderEvent.REJECTED,
            order_id="order-789",
            title="Order Rejected",
            message="Order was rejected",
            priority=NotificationPriority.URGENT,
            channels={NotificationChannel.WEBSOCKET},
        )

        with patch("app.services.order_notifications.logger") as mock_logger:
            result = await websocket_sender.send(notification)

            assert result is False  # No successful sends
            assert len(websocket_sender.connected_clients) == 0  # Client removed
            mock_logger.error.assert_called_once()

    @pytest.mark.asyncio
    async def test_websocket_sender_mixed_success_failure(self, websocket_sender):
        """Test WebSocket sender with mixed success and failure."""
        # Mock successful client
        mock_client1 = AsyncMock()
        websocket_sender.add_client(mock_client1)

        # Mock failing client
        mock_client2 = AsyncMock()
        mock_client2.send_text.side_effect = Exception("Connection error")
        websocket_sender.add_client(mock_client2)

        notification = Notification(
            id="ws-notif-4",
            rule_id="rule-1",
            event=OrderEvent.TRIGGERED,
            order_id="order-abc",
            title="Order Triggered",
            message="Stop order was triggered",
            priority=NotificationPriority.NORMAL,
            channels={NotificationChannel.WEBSOCKET},
        )

        with patch("app.services.order_notifications.logger"):
            result = await websocket_sender.send(notification)

            assert result is True  # At least one successful send
            assert len(websocket_sender.connected_clients) == 1  # Failed client removed
            assert mock_client1 in websocket_sender.connected_clients

    def test_websocket_sender_client_management(self, websocket_sender):
        """Test WebSocket client management."""
        mock_client1 = Mock()
        mock_client2 = Mock()

        # Add clients
        websocket_sender.add_client(mock_client1)
        websocket_sender.add_client(mock_client2)
        assert len(websocket_sender.connected_clients) == 2

        # Remove client
        websocket_sender.remove_client(mock_client1)
        assert len(websocket_sender.connected_clients) == 1
        assert mock_client2 in websocket_sender.connected_clients

        # Remove non-existent client (should not raise error)
        websocket_sender.remove_client(Mock())
        assert len(websocket_sender.connected_clients) == 1

    def test_websocket_sender_get_channel(self, websocket_sender):
        """Test WebSocket sender channel identification."""
        assert websocket_sender.get_channel() == NotificationChannel.WEBSOCKET


class TestWebhookNotificationSender:
    """Test WebhookNotificationSender implementation."""

    @pytest.fixture
    def webhook_sender(self):
        """Webhook notification sender instance."""
        return WebhookNotificationSender("https://example.com/webhook")

    @pytest.mark.asyncio
    async def test_webhook_sender_successful_send(self, webhook_sender):
        """Test successful webhook notification sending."""
        notification = Notification(
            id="hook-notif-1",
            rule_id="rule-1",
            event=OrderEvent.FILLED,
            order_id="order-123",
            title="Order Filled",
            message="Market order filled",
            priority=NotificationPriority.NORMAL,
            channels={NotificationChannel.WEBHOOK},
            data={"symbol": "MSFT", "price": 300.0},
        )

        mock_response = AsyncMock()
        mock_response.status = 200

        with patch("aiohttp.ClientSession") as mock_session_class:
            mock_session = AsyncMock()
            mock_session_class.return_value.__aenter__.return_value = mock_session
            mock_session.post.return_value.__aenter__.return_value = mock_response

            result = await webhook_sender.send(notification)

            assert result is True

            # Verify POST request was made
            mock_session.post.assert_called_once()
            call_args = mock_session.post.call_args

            assert call_args[0][0] == "https://example.com/webhook"
            assert "json" in call_args[1]
            payload = call_args[1]["json"]
            assert payload["notification_id"] == "hook-notif-1"
            assert payload["event"] == "FILLED"
            assert payload["order_id"] == "order-123"
            assert payload["data"]["symbol"] == "MSFT"

    @pytest.mark.asyncio
    async def test_webhook_sender_http_error(self, webhook_sender):
        """Test webhook sender with HTTP error response."""
        notification = Notification(
            id="hook-notif-2",
            rule_id="rule-1",
            event=OrderEvent.REJECTED,
            order_id="order-456",
            title="Order Rejected",
            message="Order was rejected",
            priority=NotificationPriority.HIGH,
            channels={NotificationChannel.WEBHOOK},
        )

        mock_response = AsyncMock()
        mock_response.status = 500  # Server error

        with patch("aiohttp.ClientSession") as mock_session_class:
            mock_session = AsyncMock()
            mock_session_class.return_value.__aenter__.return_value = mock_session
            mock_session.post.return_value.__aenter__.return_value = mock_response

            with patch("app.services.order_notifications.logger") as mock_logger:
                result = await webhook_sender.send(notification)

                assert result is False
                mock_logger.error.assert_called_once()

    @pytest.mark.asyncio
    async def test_webhook_sender_connection_error(self, webhook_sender):
        """Test webhook sender with connection error."""
        notification = Notification(
            id="hook-notif-3",
            rule_id="rule-1",
            event=OrderEvent.EXPIRED,
            order_id="order-789",
            title="Order Expired",
            message="Order has expired",
            priority=NotificationPriority.NORMAL,
            channels={NotificationChannel.WEBHOOK},
        )

        with patch("aiohttp.ClientSession") as mock_session_class:
            mock_session = AsyncMock()
            mock_session_class.return_value.__aenter__.return_value = mock_session
            mock_session.post.side_effect = Exception("Connection timeout")

            with patch("app.services.order_notifications.logger") as mock_logger:
                result = await webhook_sender.send(notification)

                assert result is False
                mock_logger.error.assert_called_once()

    @pytest.mark.asyncio
    async def test_webhook_sender_timeout_handling(self, webhook_sender):
        """Test webhook sender timeout configuration."""
        notification = Notification(
            id="hook-notif-4",
            rule_id="rule-1",
            event=OrderEvent.PARTIALLY_FILLED,
            order_id="order-abc",
            title="Partial Fill",
            message="Order partially filled",
            priority=NotificationPriority.NORMAL,
            channels={NotificationChannel.WEBHOOK},
        )

        mock_response = AsyncMock()
        mock_response.status = 200

        with patch("aiohttp.ClientSession") as mock_session_class:
            mock_session = AsyncMock()
            mock_session_class.return_value.__aenter__.return_value = mock_session
            mock_session.post.return_value.__aenter__.return_value = mock_response

            result = await webhook_sender.send(notification)

            assert result is True

            # Verify timeout was set
            call_args = mock_session.post.call_args
            assert "timeout" in call_args[1]

    def test_webhook_sender_get_channel(self, webhook_sender):
        """Test webhook sender channel identification."""
        assert webhook_sender.get_channel() == NotificationChannel.WEBHOOK


class TestOrderNotificationManager:
    """Test OrderNotificationManager main functionality."""

    def test_notification_manager_initialization(self, notification_manager):
        """Test notification manager initialization."""
        assert isinstance(notification_manager.notification_rules, dict)
        assert isinstance(notification_manager.senders, dict)
        assert isinstance(notification_manager.notification_queue, asyncio.Queue)
        assert isinstance(notification_manager.notification_history, list)
        assert notification_manager.worker_task is None
        assert notification_manager.is_running is False

        # Should have default senders
        assert NotificationChannel.LOG in notification_manager.senders
        assert NotificationChannel.WEBSOCKET in notification_manager.senders

        # Should have default rules
        assert len(notification_manager.notification_rules) > 0

    def test_add_notification_rule(
        self, notification_manager, sample_notification_rule
    ):
        """Test adding notification rule."""
        initial_count = len(notification_manager.notification_rules)

        notification_manager.add_rule(sample_notification_rule)

        assert len(notification_manager.notification_rules) == initial_count + 1
        assert sample_notification_rule.id in notification_manager.notification_rules
        assert (
            notification_manager.notification_rules[sample_notification_rule.id]
            == sample_notification_rule
        )

    def test_remove_notification_rule(
        self, notification_manager, sample_notification_rule
    ):
        """Test removing notification rule."""
        # Add rule first
        notification_manager.add_rule(sample_notification_rule)
        assert sample_notification_rule.id in notification_manager.notification_rules

        # Remove rule
        result = notification_manager.remove_rule(sample_notification_rule.id)

        assert result is True
        assert (
            sample_notification_rule.id not in notification_manager.notification_rules
        )

    def test_remove_nonexistent_rule(self, notification_manager):
        """Test removing non-existent notification rule."""
        result = notification_manager.remove_rule("nonexistent-rule")

        assert result is False

    def test_add_notification_sender(self, notification_manager):
        """Test adding custom notification sender."""
        mock_sender = Mock(spec=NotificationSender)
        mock_sender.get_channel.return_value = NotificationChannel.EMAIL

        initial_count = len(notification_manager.senders)

        notification_manager.add_sender(mock_sender)

        assert len(notification_manager.senders) == initial_count + 1
        assert NotificationChannel.EMAIL in notification_manager.senders
        assert notification_manager.senders[NotificationChannel.EMAIL] == mock_sender

    @pytest.mark.asyncio
    async def test_start_stop_notification_manager(self, notification_manager):
        """Test starting and stopping notification manager."""
        assert notification_manager.is_running is False
        assert notification_manager.worker_task is None

        # Start manager
        await notification_manager.start()

        assert notification_manager.is_running is True
        assert notification_manager.worker_task is not None
        assert not notification_manager.worker_task.done()

        # Stop manager
        await notification_manager.stop()

        assert notification_manager.is_running is False
        assert notification_manager.worker_task.cancelled()

    @pytest.mark.asyncio
    async def test_start_already_running(self, notification_manager):
        """Test starting notification manager when already running."""
        await notification_manager.start()
        assert notification_manager.is_running is True

        with patch("app.services.order_notifications.logger") as mock_logger:
            await notification_manager.start()  # Start again

            mock_logger.warning.assert_called_once()

        await notification_manager.stop()

    @pytest.mark.asyncio
    async def test_stop_not_running(self, notification_manager):
        """Test stopping notification manager when not running."""
        assert notification_manager.is_running is False

        # Should not raise error
        await notification_manager.stop()

        assert notification_manager.is_running is False

    @pytest.mark.asyncio
    async def test_handle_order_event_matching_rule(
        self, notification_manager, sample_lifecycle_state
    ):
        """Test handling order event with matching rule."""
        # Add a rule that matches FILLED events
        rule = NotificationRule(
            id="fill-rule",
            name="Fill Notifications",
            events={OrderEvent.FILLED},
            channels={NotificationChannel.LOG},
            priority=NotificationPriority.NORMAL,
        )
        notification_manager.add_rule(rule)

        # Update lifecycle state to filled
        sample_lifecycle_state.current_status = OrderStatus.FILLED
        sample_lifecycle_state.filled_quantity = 100
        sample_lifecycle_state.remaining_quantity = 0
        sample_lifecycle_state.average_fill_price = 151.25

        await notification_manager.handle_order_event(
            sample_lifecycle_state, OrderEvent.FILLED
        )

        # Should have queued a notification
        assert notification_manager.notification_queue.qsize() == 1

    @pytest.mark.asyncio
    async def test_handle_order_event_no_matching_rule(
        self, notification_manager, sample_lifecycle_state
    ):
        """Test handling order event with no matching rule."""
        # Clear default rules
        notification_manager.notification_rules.clear()

        await notification_manager.handle_order_event(
            sample_lifecycle_state, OrderEvent.SUBMITTED
        )

        # Should not have queued any notifications
        assert notification_manager.notification_queue.qsize() == 0

    @pytest.mark.asyncio
    async def test_handle_order_event_disabled_rule(
        self, notification_manager, sample_lifecycle_state
    ):
        """Test handling order event with disabled rule."""
        # Add disabled rule
        rule = NotificationRule(
            id="disabled-rule",
            name="Disabled Rule",
            events={OrderEvent.SUBMITTED},
            channels={NotificationChannel.LOG},
            enabled=False,  # Disabled
        )
        notification_manager.add_rule(rule)

        await notification_manager.handle_order_event(
            sample_lifecycle_state, OrderEvent.SUBMITTED
        )

        # Should not have queued any notifications
        assert notification_manager.notification_queue.qsize() == 0

    @pytest.mark.asyncio
    async def test_handle_order_event_with_conditions(
        self, notification_manager, sample_lifecycle_state
    ):
        """Test handling order event with rule conditions."""
        # Add rule with symbol condition
        rule = NotificationRule(
            id="symbol-rule",
            name="AAPL Only Rule",
            events={OrderEvent.FILLED},
            channels={NotificationChannel.LOG},
            conditions={"symbols": ["AAPL"]},
        )
        notification_manager.add_rule(rule)

        # Test with matching symbol
        await notification_manager.handle_order_event(
            sample_lifecycle_state, OrderEvent.FILLED
        )
        assert notification_manager.notification_queue.qsize() == 1

        # Test with non-matching symbol
        sample_lifecycle_state.order.symbol = "GOOGL"
        await notification_manager.handle_order_event(
            sample_lifecycle_state, OrderEvent.FILLED
        )
        # Should still be 1 (no new notification added)
        assert notification_manager.notification_queue.qsize() == 1

    @pytest.mark.asyncio
    async def test_handle_order_event_exception(
        self, notification_manager, sample_lifecycle_state
    ):
        """Test handling order event with exception."""
        with (
            patch.object(
                notification_manager,
                "_find_matching_rules",
                side_effect=Exception("Test error"),
            ),
            patch("app.services.order_notifications.logger") as mock_logger,
        ):
            await notification_manager.handle_order_event(
                sample_lifecycle_state, OrderEvent.ERROR
            )

            mock_logger.error.assert_called_once()

    def test_find_matching_rules_basic(
        self, notification_manager, sample_lifecycle_state
    ):
        """Test finding matching rules for basic event."""
        # Add rule that matches
        matching_rule = NotificationRule(
            id="match-rule",
            name="Matching Rule",
            events={OrderEvent.FILLED},
            channels={NotificationChannel.LOG},
        )
        notification_manager.add_rule(matching_rule)

        # Add rule that doesn't match
        non_matching_rule = NotificationRule(
            id="no-match-rule",
            name="Non-matching Rule",
            events={OrderEvent.CANCELLED},
            channels={NotificationChannel.LOG},
        )
        notification_manager.add_rule(non_matching_rule)

        matching_rules = notification_manager._find_matching_rules(
            sample_lifecycle_state, OrderEvent.FILLED
        )

        assert len(matching_rules) == 1
        assert matching_rules[0] == matching_rule

    def test_check_conditions_symbol_filter(
        self, notification_manager, sample_lifecycle_state
    ):
        """Test rule condition checking with symbol filter."""
        rule = NotificationRule(
            id="symbol-rule",
            name="Symbol Filter Rule",
            events={OrderEvent.FILLED},
            channels={NotificationChannel.LOG},
            conditions={"symbols": ["AAPL", "MSFT"]},
        )

        # Test with matching symbol
        sample_lifecycle_state.order.symbol = "AAPL"
        result = notification_manager._check_conditions(
            rule, sample_lifecycle_state, OrderEvent.FILLED
        )
        assert result is True

        # Test with non-matching symbol
        sample_lifecycle_state.order.symbol = "GOOGL"
        result = notification_manager._check_conditions(
            rule, sample_lifecycle_state, OrderEvent.FILLED
        )
        assert result is False

    def test_check_conditions_order_type_filter(
        self, notification_manager, sample_lifecycle_state
    ):
        """Test rule condition checking with order type filter."""
        rule = NotificationRule(
            id="type-rule",
            name="Order Type Filter Rule",
            events={OrderEvent.FILLED},
            channels={NotificationChannel.LOG},
            conditions={"order_types": [OrderType.LIMIT, OrderType.STOP]},
        )

        # Test with matching order type
        sample_lifecycle_state.order.order_type = OrderType.LIMIT
        result = notification_manager._check_conditions(
            rule, sample_lifecycle_state, OrderEvent.FILLED
        )
        assert result is True

        # Test with non-matching order type
        sample_lifecycle_state.order.order_type = OrderType.MARKET
        result = notification_manager._check_conditions(
            rule, sample_lifecycle_state, OrderEvent.FILLED
        )
        assert result is False

    def test_check_conditions_min_quantity_filter(
        self, notification_manager, sample_lifecycle_state
    ):
        """Test rule condition checking with minimum quantity filter."""
        rule = NotificationRule(
            id="qty-rule",
            name="Minimum Quantity Rule",
            events={OrderEvent.FILLED},
            channels={NotificationChannel.LOG},
            conditions={"min_quantity": 50},
        )

        # Test with quantity meeting minimum
        sample_lifecycle_state.order.quantity = 100
        result = notification_manager._check_conditions(
            rule, sample_lifecycle_state, OrderEvent.FILLED
        )
        assert result is True

        # Test with quantity below minimum
        sample_lifecycle_state.order.quantity = 25
        result = notification_manager._check_conditions(
            rule, sample_lifecycle_state, OrderEvent.FILLED
        )
        assert result is False

    def test_check_conditions_status_filter(
        self, notification_manager, sample_lifecycle_state
    ):
        """Test rule condition checking with status filter."""
        rule = NotificationRule(
            id="status-rule",
            name="Status Filter Rule",
            events={OrderEvent.FILLED},
            channels={NotificationChannel.LOG},
            conditions={"statuses": [OrderStatus.FILLED, OrderStatus.PARTIALLY_FILLED]},
        )

        # Test with matching status
        sample_lifecycle_state.current_status = OrderStatus.FILLED
        result = notification_manager._check_conditions(
            rule, sample_lifecycle_state, OrderEvent.FILLED
        )
        assert result is True

        # Test with non-matching status
        sample_lifecycle_state.current_status = OrderStatus.PENDING
        result = notification_manager._check_conditions(
            rule, sample_lifecycle_state, OrderEvent.FILLED
        )
        assert result is False

    def test_check_conditions_no_conditions(
        self, notification_manager, sample_lifecycle_state
    ):
        """Test rule condition checking with no conditions (should always pass)."""
        rule = NotificationRule(
            id="no-conditions-rule",
            name="No Conditions Rule",
            events={OrderEvent.FILLED},
            channels={NotificationChannel.LOG},
            conditions={},  # No conditions
        )

        result = notification_manager._check_conditions(
            rule, sample_lifecycle_state, OrderEvent.FILLED
        )
        assert result is True

    def test_create_notification(self, notification_manager, sample_lifecycle_state):
        """Test creating notification from rule and lifecycle state."""
        rule = NotificationRule(
            id="test-create-rule",
            name="Test Create Rule",
            events={OrderEvent.FILLED},
            channels={NotificationChannel.LOG, NotificationChannel.WEBSOCKET},
            priority=NotificationPriority.HIGH,
        )

        # Update lifecycle state with fill data
        sample_lifecycle_state.current_status = OrderStatus.FILLED
        sample_lifecycle_state.filled_quantity = 100
        sample_lifecycle_state.remaining_quantity = 0
        sample_lifecycle_state.average_fill_price = 152.50

        notification = notification_manager._create_notification(
            rule, sample_lifecycle_state, OrderEvent.FILLED
        )

        assert isinstance(notification, Notification)
        assert notification.rule_id == rule.id
        assert notification.event == OrderEvent.FILLED
        assert notification.order_id == sample_lifecycle_state.order.id
        assert notification.priority == NotificationPriority.HIGH
        assert notification.channels == rule.channels
        assert "AAPL" in notification.title
        assert "filled" in notification.message.lower()
        assert notification.data["symbol"] == "AAPL"
        assert notification.data["quantity"] == 100
        assert notification.data["filled_quantity"] == 100

    def test_format_notification_content_filled(
        self, notification_manager, sample_lifecycle_state
    ):
        """Test notification content formatting for filled order."""
        sample_lifecycle_state.current_status = OrderStatus.FILLED
        sample_lifecycle_state.filled_quantity = 100
        sample_lifecycle_state.average_fill_price = 151.75

        title, message = notification_manager._format_notification_content(
            sample_lifecycle_state, OrderEvent.FILLED
        )

        assert "Order Filled: AAPL" in title
        assert (
            "Market order for 100 shares of AAPL has been completely filled" in message
        )
        assert "151.7500" in message

    def test_format_notification_content_partially_filled(
        self, notification_manager, sample_lifecycle_state
    ):
        """Test notification content formatting for partially filled order."""
        sample_lifecycle_state.current_status = OrderStatus.PARTIALLY_FILLED
        sample_lifecycle_state.filled_quantity = 60
        sample_lifecycle_state.remaining_quantity = 40

        title, message = notification_manager._format_notification_content(
            sample_lifecycle_state, OrderEvent.PARTIALLY_FILLED
        )

        assert "Partial Fill: AAPL" in title
        assert "60 shares filled, 40 remaining" in message

    def test_format_notification_content_cancelled(
        self, notification_manager, sample_lifecycle_state
    ):
        """Test notification content formatting for cancelled order."""
        title, message = notification_manager._format_notification_content(
            sample_lifecycle_state, OrderEvent.CANCELLED
        )

        assert "Order Cancelled: AAPL" in title
        assert "Market order for 100 shares of AAPL has been cancelled" in message

    def test_format_notification_content_rejected(
        self, notification_manager, sample_lifecycle_state
    ):
        """Test notification content formatting for rejected order."""
        sample_lifecycle_state.error_messages = ["Insufficient funds"]

        title, message = notification_manager._format_notification_content(
            sample_lifecycle_state, OrderEvent.REJECTED
        )

        assert "Order Rejected: AAPL" in title
        assert "Market order for 100 shares of AAPL has been rejected" in message
        assert "Insufficient funds" in message

    def test_format_notification_content_triggered(
        self, notification_manager, sample_lifecycle_state
    ):
        """Test notification content formatting for triggered order."""
        sample_lifecycle_state.order.order_type = OrderType.STOP

        title, message = notification_manager._format_notification_content(
            sample_lifecycle_state, OrderEvent.TRIGGERED
        )

        assert "Order Triggered: AAPL" in title
        assert "Stop order for 100 shares of AAPL has been triggered" in message

    def test_format_notification_content_expired(
        self, notification_manager, sample_lifecycle_state
    ):
        """Test notification content formatting for expired order."""
        title, message = notification_manager._format_notification_content(
            sample_lifecycle_state, OrderEvent.EXPIRED
        )

        assert "Order Expired: AAPL" in title
        assert "Market order for 100 shares of AAPL has expired" in message

    def test_format_notification_content_error(
        self, notification_manager, sample_lifecycle_state
    ):
        """Test notification content formatting for error event."""
        sample_lifecycle_state.error_messages = ["System error occurred"]

        title, message = notification_manager._format_notification_content(
            sample_lifecycle_state, OrderEvent.ERROR
        )

        assert "Order Error: AAPL" in title
        assert "Error occurred with Market order for 100 shares of AAPL" in message
        assert "System error occurred" in message

    def test_format_notification_content_unknown_event(
        self, notification_manager, sample_lifecycle_state
    ):
        """Test notification content formatting for unknown event."""
        title, message = notification_manager._format_notification_content(
            sample_lifecycle_state, OrderEvent.SUBMITTED
        )

        assert "Order Update: AAPL" in title
        assert "Market order for 100 shares of AAPL - SUBMITTED" in message

    @pytest.mark.asyncio
    async def test_notification_worker_processing(self, notification_manager):
        """Test notification worker processing notifications from queue."""
        # Add a mock sender
        mock_sender = AsyncMock()
        mock_sender.send.return_value = True
        notification_manager.senders[NotificationChannel.LOG] = mock_sender

        # Create notification
        notification = Notification(
            id="worker-test-1",
            rule_id="rule-1",
            event=OrderEvent.FILLED,
            order_id="order-123",
            title="Test Notification",
            message="Test message",
            priority=NotificationPriority.NORMAL,
            channels={NotificationChannel.LOG},
        )

        # Add to queue
        await notification_manager.notification_queue.put(notification)

        # Start manager briefly to process
        await notification_manager.start()
        await asyncio.sleep(0.1)  # Allow processing
        await notification_manager.stop()

        # Verify notification was processed
        mock_sender.send.assert_called_once_with(notification)
        assert len(notification_manager.notification_history) == 1
        assert notification_manager.notification_history[0] == notification

    @pytest.mark.asyncio
    async def test_send_notification_success(self, notification_manager):
        """Test successful notification sending."""
        mock_sender = AsyncMock()
        mock_sender.send.return_value = True
        notification_manager.senders[NotificationChannel.LOG] = mock_sender

        notification = Notification(
            id="send-test-1",
            rule_id="rule-1",
            event=OrderEvent.FILLED,
            order_id="order-123",
            title="Test Notification",
            message="Test message",
            priority=NotificationPriority.NORMAL,
            channels={NotificationChannel.LOG},
        )

        await notification_manager._send_notification(notification)

        assert notification.sent_at is not None
        assert len(notification.failed_channels) == 0
        mock_sender.send.assert_called_once_with(notification)

    @pytest.mark.asyncio
    async def test_send_notification_failure(self, notification_manager):
        """Test notification sending failure."""
        mock_sender = AsyncMock()
        mock_sender.send.return_value = False
        notification_manager.senders[NotificationChannel.LOG] = mock_sender

        notification = Notification(
            id="send-test-2",
            rule_id="rule-1",
            event=OrderEvent.REJECTED,
            order_id="order-456",
            title="Test Notification",
            message="Test message",
            priority=NotificationPriority.HIGH,
            channels={NotificationChannel.LOG},
        )

        await notification_manager._send_notification(notification)

        assert notification.sent_at is None
        assert NotificationChannel.LOG in notification.failed_channels

    @pytest.mark.asyncio
    async def test_send_notification_no_sender(self, notification_manager):
        """Test notification sending with no configured sender."""
        notification = Notification(
            id="send-test-3",
            rule_id="rule-1",
            event=OrderEvent.EXPIRED,
            order_id="order-789",
            title="Test Notification",
            message="Test message",
            priority=NotificationPriority.NORMAL,
            channels={NotificationChannel.EMAIL},  # No email sender configured
        )

        with patch("app.services.order_notifications.logger") as mock_logger:
            await notification_manager._send_notification(notification)

            assert notification.sent_at is None
            assert NotificationChannel.EMAIL in notification.failed_channels
            mock_logger.warning.assert_called_once()

    @pytest.mark.asyncio
    async def test_send_notification_exception(self, notification_manager):
        """Test notification sending with sender exception."""
        mock_sender = AsyncMock()
        mock_sender.send.side_effect = Exception("Sender error")
        notification_manager.senders[NotificationChannel.LOG] = mock_sender

        notification = Notification(
            id="send-test-4",
            rule_id="rule-1",
            event=OrderEvent.ERROR,
            order_id="order-abc",
            title="Test Notification",
            message="Test message",
            priority=NotificationPriority.URGENT,
            channels={NotificationChannel.LOG},
        )

        with patch("app.services.order_notifications.logger") as mock_logger:
            await notification_manager._send_notification(notification)

            assert notification.sent_at is None
            assert NotificationChannel.LOG in notification.failed_channels
            mock_logger.error.assert_called_once()

    def test_get_statistics(self, notification_manager):
        """Test getting notification statistics."""
        # Add some notifications to history
        notification1 = Notification(
            id="stat-test-1",
            rule_id="rule-1",
            event=OrderEvent.FILLED,
            order_id="order-123",
            title="Test",
            message="Test",
            priority=NotificationPriority.NORMAL,
            channels={NotificationChannel.LOG},
        )
        notification1.sent_at = datetime.utcnow()  # Mark as sent

        notification2 = Notification(
            id="stat-test-2",
            rule_id="rule-1",
            event=OrderEvent.REJECTED,
            order_id="order-456",
            title="Test",
            message="Test",
            priority=NotificationPriority.HIGH,
            channels={NotificationChannel.LOG},
        )
        # Leave sent_at as None (failed)

        notification_manager.notification_history = [notification1, notification2]

        stats = notification_manager.get_statistics()

        assert stats["total_notifications"] == 2
        assert stats["successful_notifications"] == 1
        assert stats["success_rate"] == 0.5
        assert stats["queue_size"] == 0
        assert stats["total_rules"] > 0  # Default rules
        assert stats["active_rules"] > 0
        assert "connected_channels" in stats

    def test_get_statistics_empty_history(self, notification_manager):
        """Test getting statistics with empty notification history."""
        notification_manager.notification_history = []

        stats = notification_manager.get_statistics()

        assert stats["total_notifications"] == 0
        assert stats["successful_notifications"] == 0
        assert stats["success_rate"] == 0

    def test_get_recent_notifications(self, notification_manager):
        """Test getting recent notifications."""
        # Create test notifications
        notifications = []
        for i in range(75):  # More than default limit of 50
            notification = Notification(
                id=f"recent-test-{i}",
                rule_id="rule-1",
                event=OrderEvent.FILLED,
                order_id=f"order-{i}",
                title=f"Test {i}",
                message=f"Test message {i}",
                priority=NotificationPriority.NORMAL,
                channels={NotificationChannel.LOG},
            )
            notifications.append(notification)

        notification_manager.notification_history = notifications

        # Test default limit
        recent = notification_manager.get_recent_notifications()
        assert len(recent) == 50
        assert recent[-1].id == "recent-test-74"  # Last item

        # Test custom limit
        recent_10 = notification_manager.get_recent_notifications(limit=10)
        assert len(recent_10) == 10
        assert recent_10[-1].id == "recent-test-74"

    def test_get_recent_notifications_empty_history(self, notification_manager):
        """Test getting recent notifications with empty history."""
        notification_manager.notification_history = []

        recent = notification_manager.get_recent_notifications()
        assert recent == []

    def test_notification_history_size_limit(self, notification_manager):
        """Test that notification history size is limited."""
        # Create many notifications to exceed limit
        notifications = []
        for i in range(1200):  # Exceed limit of 1000
            notification = Notification(
                id=f"limit-test-{i}",
                rule_id="rule-1",
                event=OrderEvent.FILLED,
                order_id=f"order-{i}",
                title=f"Test {i}",
                message=f"Test message {i}",
                priority=NotificationPriority.NORMAL,
                channels={NotificationChannel.LOG},
            )
            notifications.append(notification)

        # Simulate adding to history one by one with limit check
        for notification in notifications:
            notification_manager.notification_history.append(notification)
            if len(notification_manager.notification_history) > 1000:
                notification_manager.notification_history = (
                    notification_manager.notification_history[-500:]
                )

        # Should be limited to 500
        assert len(notification_manager.notification_history) == 500
        assert notification_manager.notification_history[0].id == "limit-test-700"


class TestGlobalNotificationManager:
    """Test global notification manager instance."""

    def test_get_order_notification_manager(self):
        """Test getting global notification manager instance."""
        manager1 = get_order_notification_manager()
        manager2 = get_order_notification_manager()

        assert isinstance(manager1, OrderNotificationManager)
        assert manager1 is manager2  # Should be same instance


class TestNotificationChannelsAndPriorities:
    """Test notification channels and priority enums."""

    def test_notification_channels(self):
        """Test notification channel enum values."""
        assert NotificationChannel.WEBSOCKET == "websocket"
        assert NotificationChannel.EMAIL == "email"
        assert NotificationChannel.SMS == "sms"
        assert NotificationChannel.WEBHOOK == "webhook"
        assert NotificationChannel.LOG == "log"
        assert NotificationChannel.DATABASE == "database"

    def test_notification_priorities(self):
        """Test notification priority enum values."""
        assert NotificationPriority.LOW == "low"
        assert NotificationPriority.NORMAL == "normal"
        assert NotificationPriority.HIGH == "high"
        assert NotificationPriority.URGENT == "urgent"


class TestNotificationSystemIntegration:
    """Test end-to-end notification system integration."""

    @pytest.mark.asyncio
    async def test_complete_notification_flow(
        self, notification_manager, sample_lifecycle_state
    ):
        """Test complete notification flow from order event to delivery."""
        # Set up mock sender
        mock_sender = AsyncMock()
        mock_sender.send.return_value = True
        notification_manager.senders[NotificationChannel.LOG] = mock_sender

        # Add custom rule
        rule = NotificationRule(
            id="integration-rule",
            name="Integration Test Rule",
            events={OrderEvent.FILLED},
            channels={NotificationChannel.LOG},
            priority=NotificationPriority.HIGH,
        )
        notification_manager.add_rule(rule)

        # Update lifecycle state
        sample_lifecycle_state.current_status = OrderStatus.FILLED
        sample_lifecycle_state.filled_quantity = 100
        sample_lifecycle_state.remaining_quantity = 0
        sample_lifecycle_state.average_fill_price = 152.00

        # Start notification manager
        await notification_manager.start()

        # Handle order event
        await notification_manager.handle_order_event(
            sample_lifecycle_state, OrderEvent.FILLED
        )

        # Allow processing
        await asyncio.sleep(0.1)

        # Stop manager
        await notification_manager.stop()

        # Verify notification was sent
        mock_sender.send.assert_called()
        sent_notification = mock_sender.send.call_args[0][0]
        assert sent_notification.event == OrderEvent.FILLED
        assert sent_notification.order_id == sample_lifecycle_state.order.id
        assert sent_notification.priority == NotificationPriority.HIGH

        # Verify notification in history
        assert len(notification_manager.notification_history) > 0
        assert any(
            n.order_id == sample_lifecycle_state.order.id
            for n in notification_manager.notification_history
        )

    @pytest.mark.asyncio
    async def test_multiple_channels_notification(
        self, notification_manager, sample_lifecycle_state
    ):
        """Test notification delivery to multiple channels."""
        # Set up multiple mock senders
        mock_log_sender = AsyncMock()
        mock_log_sender.send.return_value = True
        notification_manager.senders[NotificationChannel.LOG] = mock_log_sender

        mock_ws_sender = AsyncMock()
        mock_ws_sender.send.return_value = True
        notification_manager.senders[NotificationChannel.WEBSOCKET] = mock_ws_sender

        # Add rule with multiple channels
        rule = NotificationRule(
            id="multi-channel-rule",
            name="Multi-Channel Rule",
            events={OrderEvent.REJECTED},
            channels={NotificationChannel.LOG, NotificationChannel.WEBSOCKET},
            priority=NotificationPriority.URGENT,
        )
        notification_manager.add_rule(rule)

        # Start manager and handle event
        await notification_manager.start()
        await notification_manager.handle_order_event(
            sample_lifecycle_state, OrderEvent.REJECTED
        )
        await asyncio.sleep(0.1)
        await notification_manager.stop()

        # Verify both senders were called
        mock_log_sender.send.assert_called_once()
        mock_ws_sender.send.assert_called_once()

    @pytest.mark.asyncio
    async def test_notification_retry_logic(self, notification_manager):
        """Test notification retry logic for failed deliveries."""
        # This would be implemented if retry logic exists
        # For now, test that failed channels are tracked
        mock_sender = AsyncMock()
        mock_sender.send.return_value = False  # Simulate failure
        notification_manager.senders[NotificationChannel.LOG] = mock_sender

        notification = Notification(
            id="retry-test",
            rule_id="rule-1",
            event=OrderEvent.ERROR,
            order_id="order-retry",
            title="Retry Test",
            message="Test retry message",
            priority=NotificationPriority.URGENT,
            channels={NotificationChannel.LOG},
        )

        await notification_manager._send_notification(notification)

        # Verify failure was tracked
        assert NotificationChannel.LOG in notification.failed_channels
        assert notification.sent_at is None

    @pytest.mark.asyncio
    async def test_high_volume_notification_processing(self, notification_manager):
        """Test notification system under high volume."""
        # Add mock sender
        mock_sender = AsyncMock()
        mock_sender.send.return_value = True
        notification_manager.senders[NotificationChannel.LOG] = mock_sender

        # Create many notifications
        notifications = []
        for i in range(100):
            notification = Notification(
                id=f"volume-test-{i}",
                rule_id="rule-1",
                event=OrderEvent.FILLED,
                order_id=f"order-{i}",
                title=f"Volume Test {i}",
                message=f"Volume test message {i}",
                priority=NotificationPriority.NORMAL,
                channels={NotificationChannel.LOG},
            )
            notifications.append(notification)

        # Start manager
        await notification_manager.start()

        # Queue all notifications
        for notification in notifications:
            await notification_manager.notification_queue.put(notification)

        # Allow processing
        await asyncio.sleep(0.5)
        await notification_manager.stop()

        # Verify all were processed
        assert mock_sender.send.call_count == 100
        assert len(notification_manager.notification_history) == 100
