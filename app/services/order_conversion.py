"""
Order conversion logic for advanced order types.

This module handles the conversion of triggered orders (stop loss, stop limit,
trailing stop) into executable market or limit orders.
"""

import logging
from datetime import datetime, UTC
from typing import Any

from ..schemas.orders import Order, OrderCondition, OrderStatus, OrderType

logger = logging.getLogger(__name__)


class OrderConversionError(Exception):
    """Error during order conversion."""

    pass


class OrderConverter:
    """
    Handles conversion of complex order types into executable orders.

    This class manages the logic for converting triggered orders (stop loss,
    stop limit, trailing stop) into standard market or limit orders that can
    be executed by the trading system.
    """

    def __init__(self) -> None:
        self.conversion_history: dict[str, dict[str, Any]] = {}

    def convert_stop_loss_to_market(
        self,
        order: Order,
        current_price: float,
        triggered_at: datetime | None = None,
    ) -> Order:
        """
        Convert a stop loss order to a market order when triggered.

        Args:
            order: The stop loss order to convert
            current_price: Current market price that triggered the order
            triggered_at: Timestamp when the order was triggered

        Returns:
            New market order ready for execution

        Raises:
            OrderConversionError: If conversion fails
        """
        if order.order_type != OrderType.STOP_LOSS:
            raise OrderConversionError(
                f"Cannot convert {order.order_type} to market order"
            )

        if order.stop_price is None:
            raise OrderConversionError("Stop loss order missing stop_price")

        # Stop loss logic:
        # - Positive quantity = protective stop (sell when price drops)
        # - Negative quantity = buy stop (buy when price rises)
        is_protective_stop = order.quantity > 0
        trigger_condition_met = (
            is_protective_stop and current_price <= order.stop_price
        ) or (not is_protective_stop and current_price >= order.stop_price)

        if not trigger_condition_met:
            raise OrderConversionError(
                f"Stop loss trigger condition not met: "
                f"price={current_price}, stop_price={order.stop_price}, "
                f"is_protective_stop={is_protective_stop}"
            )

        # Create market order
        converted_order = Order(
            id=f"{order.id}_converted" if order.id else None,
            symbol=order.symbol,
            order_type=OrderType.SELL if is_protective_stop else OrderType.BUY,
            quantity=abs(order.quantity),
            price=None,  # Market order has no price
            status=OrderStatus.PENDING,
            created_at=triggered_at or datetime.now(UTC),
            condition=OrderCondition.MARKET,
            stop_price=None,
            trail_percent=None,
            trail_amount=None,
            net_price=None,
        )

        # Log conversion
        self._log_conversion(
            order, converted_order, current_price, "stop_loss_to_market"
        )

        return converted_order

    def convert_stop_limit_to_limit(
        self,
        order: Order,
        current_price: float,
        triggered_at: datetime | None = None,
    ) -> Order:
        """
        Convert a stop limit order to a limit order when triggered.

        Args:
            order: The stop limit order to convert
            current_price: Current market price that triggered the order
            triggered_at: Timestamp when the order was triggered

        Returns:
            New limit order ready for execution

        Raises:
            OrderConversionError: If conversion fails
        """
        if order.order_type != OrderType.STOP_LIMIT:
            raise OrderConversionError(
                f"Cannot convert {order.order_type} to limit order"
            )

        if order.stop_price is None:
            raise OrderConversionError("Stop limit order missing stop_price")

        if order.price is None:
            raise OrderConversionError("Stop limit order missing limit price")

        # Stop limit logic: same as stop loss
        is_protective_stop = order.quantity > 0
        trigger_condition_met = (
            is_protective_stop and current_price <= order.stop_price
        ) or (not is_protective_stop and current_price >= order.stop_price)

        if not trigger_condition_met:
            raise OrderConversionError(
                f"Stop limit trigger condition not met: "
                f"price={current_price}, stop_price={order.stop_price}, "
                f"is_protective_stop={is_protective_stop}"
            )

        # Create limit order
        converted_order = Order(
            id=f"{order.id}_converted" if order.id else None,
            symbol=order.symbol,
            order_type=OrderType.SELL if is_protective_stop else OrderType.BUY,
            quantity=abs(order.quantity),  # Convert to positive
            price=order.price,  # Use the limit price
            status=OrderStatus.PENDING,
            created_at=triggered_at or datetime.now(UTC),
            condition=OrderCondition.LIMIT,
            stop_price=None,
            trail_percent=None,
            trail_amount=None,
            net_price=None,
        )

        # Log conversion
        self._log_conversion(
            order, converted_order, current_price, "stop_limit_to_limit"
        )

        return converted_order

    def update_trailing_stop(
        self,
        order: Order,
        current_price: float,
        high_water_mark: float | None = None,
    ) -> Order:
        """
        Update trailing stop order based on current price movement.

        Args:
            order: The trailing stop order to update
            current_price: Current market price
            high_water_mark: Highest price seen since order creation

        Returns:
            Updated order with new stop price

        Raises:
            OrderConversionError: If update fails
        """
        if order.order_type != OrderType.TRAILING_STOP:
            raise OrderConversionError(
                f"Cannot update {order.order_type} as trailing stop"
            )

        if order.trail_percent is None and order.trail_amount is None:
            raise OrderConversionError("Trailing stop order missing trail parameters")

        # For trailing stops, positive quantity = protective sell stop
        is_protective_stop = order.quantity > 0

        # Calculate new stop price based on trail parameters
        if order.trail_percent is not None:
            # Percentage-based trailing
            if is_protective_stop:
                # For protective stops, trail below the current price as it rises
                new_stop_price = current_price * (1 - order.trail_percent / 100)
            else:
                # For buy stops, trail above the current price as it falls
                new_stop_price = current_price * (1 + order.trail_percent / 100)
        elif order.trail_amount is not None:
            # Dollar amount-based trailing
            if is_protective_stop:
                new_stop_price = current_price - order.trail_amount
            else:
                new_stop_price = current_price + order.trail_amount
        else:
            raise OrderConversionError("Invalid trailing stop order")

        # Update stop price if it's more favorable
        updated_order = order.model_copy()

        if order.stop_price is None:
            # First time setting stop price
            updated_order.stop_price = new_stop_price
        else:
            if is_protective_stop:
                # For protective stops, only raise the stop price (follow price up)
                updated_order.stop_price = max(order.stop_price, new_stop_price)
            else:
                # For buy stops, only lower the stop price (follow price down)
                updated_order.stop_price = min(order.stop_price, new_stop_price)

        # Check if should trigger
        if updated_order.stop_price:
            if is_protective_stop:
                pass
            else:
                pass

        return updated_order

    def convert_trailing_stop_to_market(
        self,
        order: Order,
        current_price: float,
        triggered_at: datetime | None = None,
    ) -> Order:
        """
        Convert a trailing stop order to a market order when triggered.

        Args:
            order: The trailing stop order to convert
            current_price: Current market price that triggered the order
            triggered_at: Timestamp when the order was triggered

        Returns:
            New market order ready for execution

        Raises:
            OrderConversionError: If conversion fails
        """
        if order.order_type != OrderType.TRAILING_STOP:
            raise OrderConversionError(
                f"Cannot convert {order.order_type} to market order"
            )

        # Create market order
        converted_order = Order(
            id=f"{order.id}_converted" if order.id else None,
            symbol=order.symbol,
            order_type=OrderType.SELL if order.quantity < 0 else OrderType.BUY,
            quantity=abs(order.quantity),  # Convert to positive
            price=None,  # Market order has no price
            condition=OrderCondition.MARKET,
            status=OrderStatus.PENDING,
            created_at=triggered_at or datetime.now(UTC),
            stop_price=None,
            trail_percent=None,
            trail_amount=None,
            net_price=None,
        )

        # Log conversion
        self._log_conversion(
            order, converted_order, current_price, "trailing_stop_to_market"
        )

        return converted_order

    def can_convert_order(self, order: Order) -> bool:
        """
        Check if an order can be converted.

        Args:
            order: Order to check

        Returns:
            True if order can be converted
        """
        convertible_types = [
            OrderType.STOP_LOSS,
            OrderType.STOP_LIMIT,
            OrderType.TRAILING_STOP,
        ]

        return order.order_type in convertible_types

    def get_conversion_requirements(self, order_type: OrderType) -> dict[str, bool]:
        """
        Get the field requirements for converting an order type.

        Args:
            order_type: The order type to check

        Returns:
            Dictionary of field requirements
        """
        requirements = {
            OrderType.STOP_LOSS: {
                "stop_price": True,
                "price": False,
                "trail_percent": False,
                "trail_amount": False,
            },
            OrderType.STOP_LIMIT: {
                "stop_price": True,
                "price": True,
                "trail_percent": False,
                "trail_amount": False,
            },
            OrderType.TRAILING_STOP: {
                "stop_price": False,
                "price": False,
                "trail_percent": False,  # Either this OR trail_amount
                "trail_amount": False,  # Either this OR trail_percent
            },
        }

        return requirements.get(order_type, {})

    def validate_order_for_conversion(self, order: Order) -> bool:
        """
        Validate that an order has all required fields for conversion.

        Args:
            order: Order to validate

        Returns:
            True if order is valid for conversion

        Raises:
            OrderConversionError: If validation fails
        """
        if not self.can_convert_order(order):
            raise OrderConversionError(
                f"Order type {order.order_type} is not convertible"
            )

        requirements = self.get_conversion_requirements(order.order_type)

        # Check required fields
        if order.order_type in [OrderType.STOP_LOSS, OrderType.STOP_LIMIT]:
            if requirements.get("stop_price") and order.stop_price is None:
                raise OrderConversionError(f"{order.order_type} requires stop_price")

        if order.order_type == OrderType.STOP_LIMIT:
            if requirements.get("price") and order.price is None:
                raise OrderConversionError(f"{order.order_type} requires price")

        if order.order_type == OrderType.TRAILING_STOP:
            if order.trail_percent is None and order.trail_amount is None:
                raise OrderConversionError(
                    "Trailing stop requires either trail_percent or trail_amount"
                )
            if order.trail_percent is not None and order.trail_amount is not None:
                raise OrderConversionError(
                    "Trailing stop cannot have both trail_percent and trail_amount"
                )

        return True

    def _log_conversion(
        self,
        original_order: Order,
        converted_order: Order,
        trigger_price: float,
        conversion_type: str,
    ) -> None:
        """Log order conversion for audit trail."""
        conversion_record = {
            "original_order_id": original_order.id,
            "converted_order_id": converted_order.id,
            "conversion_type": conversion_type,
            "trigger_price": trigger_price,
            "original_type": original_order.order_type,
            "converted_type": converted_order.order_type,
            "timestamp": datetime.now(UTC),
        }

        if original_order.id:
            self.conversion_history[original_order.id] = conversion_record

        logger.info(
            f"Order conversion: {conversion_type} - "
            f"Original: {original_order.order_type} {original_order.symbol} "
            f"-> Converted: {converted_order.order_type} at price {trigger_price}"
        )

    def get_conversion_history(self, order_id: str) -> dict[str, Any] | None:
        """Get conversion history for an order."""
        return self.conversion_history.get(order_id)


# Global converter instance
order_converter = OrderConverter()
