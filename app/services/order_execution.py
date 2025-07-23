"""
Order Execution Engine.

Handles the execution of orders, including cash balance updates.
"""

from datetime import datetime
from math import copysign
from typing import Protocol

from ..models.assets import Option
from ..models.quotes import Quote
from ..schemas.orders import MultiLegOrder, Order, OrderLeg, OrderType
from ..schemas.positions import Position
from .estimators import MidpointEstimator, PriceEstimator
from .validation import AccountValidator


class QuoteServiceProtocol(Protocol):
    """Protocol for quote service."""

    async def get_quote(self, asset: object) -> Quote: ...


class OrderExecutionError(Exception):
    """Custom exception for order execution errors."""

    pass


class OrderExecutionResult:
    """Result of order execution with details."""

    def __init__(
        self,
        success: bool,
        message: str = "",
        order_id: str | None = None,
        cash_change: float = 0.0,
        positions_created: list[Position] | None = None,
        positions_modified: list[Position] | None = None,
    ):
        self.success = success
        self.message = message
        self.order_id = order_id
        self.cash_change = cash_change
        self.positions_created = positions_created or []
        self.positions_modified = positions_modified or []
        self.executed_at = datetime.now()


class OrderExecutionEngine:
    """Service for executing trading orders."""

    def __init__(
        self,
        validator: AccountValidator | None = None,
    ) -> None:
        """Initialize with validation services."""
        self.validator = validator or AccountValidator()
        self.default_estimator = MidpointEstimator()
        self.quote_service: QuoteServiceProtocol | None = None

    async def execute_order(
        self,
        account_id: str,
        order: MultiLegOrder,
        current_cash: float,
        current_positions: list[Position],
        estimator: PriceEstimator | None = None,
    ) -> OrderExecutionResult:
        """
        Execute a multi-leg order with full validation and position management.

        Args:
            account_id: Account executing the order
            order: MultiLegOrder to execute
            current_cash: Current cash balance
            current_positions: Current positions in account
            estimator: Price estimator for fills (defaults to midpoint)

        Returns:
            OrderExecutionResult with execution details
        """

        if estimator is None:
            estimator = self.default_estimator

        try:
            # Validate order structure
            self._validate_order(order)

            # Get quotes and calculate fill prices for each leg
            leg_prices = await self._calculate_leg_prices(order.legs, estimator)
            total_order_price = sum(
                price * abs(leg.quantity) for leg, price in leg_prices.items()
            )

            # Check if order should fill based on condition
            if not self._should_fill_order(order, total_order_price):
                return OrderExecutionResult(
                    success=False,
                    message=f"Order condition not met. Limit price: {order.limit_price}, Market price: {total_order_price}",
                    order_id=order.id,
                )

            # Validate sufficient positions for closing orders
            self._validate_closing_positions(order.legs, current_positions)

            # Calculate cash requirement
            cash_requirement = self._calculate_cash_requirement(order.legs, leg_prices)

            # Validate sufficient cash
            if (
                current_cash + cash_requirement < 0
            ):  # Negative cash_requirement means cash out
                return OrderExecutionResult(
                    success=False,
                    message=f"Insufficient cash. Required: ${-cash_requirement:,.2f}, Available: ${current_cash:,.2f}",
                    order_id=order.id,
                )

            # Execute each leg
            new_positions = []
            modified_positions = []

            for leg in order.legs:
                cost_basis = leg_prices[leg]

                if leg.order_type in [OrderType.BTO, OrderType.STO]:
                    # Opening position
                    position = await self._open_position(leg, cost_basis)
                    new_positions.append(position)

                elif leg.order_type in [OrderType.BTC, OrderType.STC]:
                    # Closing position
                    affected_positions = self._close_position(
                        leg, current_positions, cost_basis
                    )
                    modified_positions.extend(affected_positions)

            # Calculate maintenance margin if service available
            # if self.margin_service:
            #     # This will be implemented when we migrate the margin service
            #     pass

            return OrderExecutionResult(
                success=True,
                message="Order executed successfully",
                order_id=order.id,
                cash_change=cash_requirement,
                positions_created=new_positions,
                positions_modified=modified_positions,
            )

        except Exception as e:
            return OrderExecutionResult(
                success=False,
                message=f"Order execution failed: {e!s}",
                order_id=order.id,
            )

    async def execute_simple_order(
        self,
        account_id: str,
        order: Order,
        current_cash: float,
        current_positions: list[Position],
        estimator: PriceEstimator | None = None,
    ) -> OrderExecutionResult:
        """Execute a simple single-leg order."""

        # Convert to multi-leg order for unified processing
        multi_leg = MultiLegOrder(
            id=order.id,
            legs=[order.to_leg()],
            condition=order.condition,
            limit_price=order.price,
        )

        return await self.execute_order(
            account_id, multi_leg, current_cash, current_positions, estimator
        )

    def _validate_order(self, order: MultiLegOrder) -> None:
        """Validate order structure and leg consistency."""
        if not order.legs:
            raise OrderExecutionError("Order must have at least one leg")

        # Check for duplicate assets
        symbols = [
            leg.asset.symbol if hasattr(leg.asset, "symbol") else str(leg.asset)
            for leg in order.legs
        ]
        if len(symbols) != len(set(symbols)):
            raise OrderExecutionError(
                "Duplicate assets not allowed in multi-leg orders"
            )

    async def _calculate_leg_prices(
        self, legs: list[OrderLeg], estimator: PriceEstimator
    ) -> dict[OrderLeg, float]:
        """Calculate fill price for each leg using the estimator."""
        leg_prices = {}

        for leg in legs:
            # Get quote for the asset
            if self.quote_service:
                quote = await self.quote_service.get_quote(leg.asset)
            else:
                # Fallback for testing - create mock quote
                quote = Quote(
                    asset=leg.asset,
                    quote_date=datetime.now(),
                    price=leg.price if leg.price else 100.0,  # Mock price
                    bid=95.0,
                    ask=105.0,
                    bid_size=100,
                    ask_size=100,
                    volume=1000,
                )

            # Calculate fill price using estimator
            estimated_price = estimator.estimate(quote, leg.quantity)

            # Apply proper sign based on order direction
            fill_price = estimated_price * copysign(1, leg.quantity)
            leg_prices[leg] = fill_price

        return leg_prices

    def _should_fill_order(self, order: MultiLegOrder, market_price: float) -> bool:
        """Determine if order should fill based on condition and limit price."""
        if order.condition.value == "market":
            return True
        elif order.condition.value == "limit" and order.limit_price is not None:
            return order.limit_price >= market_price
        return True  # Default to fill

    def _validate_closing_positions(
        self, legs: list[OrderLeg], current_positions: list[Position]
    ) -> None:
        """Validate that sufficient positions exist for closing orders."""
        for leg in legs:
            if leg.order_type in [OrderType.BTC, OrderType.STC]:
                # Find closable positions for this asset
                closable_positions = [
                    pos
                    for pos in current_positions
                    if pos.symbol == leg.asset.symbol
                    and copysign(1, pos.quantity)
                    == (copysign(1, leg.quantity) * -1)  # Opposite sign
                ]

                if not closable_positions:
                    raise OrderExecutionError(
                        f"No available positions to close for {leg.asset.symbol}"
                    )

                # Check sufficient quantity
                available_quantity = sum(
                    abs(pos.quantity) for pos in closable_positions
                )
                if available_quantity < abs(leg.quantity):
                    raise OrderExecutionError(
                        f"Insufficient position quantity to close. "
                        f"Requested: {abs(leg.quantity)}, Available: {available_quantity}"
                    )

    def _calculate_cash_requirement(
        self, legs: list[OrderLeg], leg_prices: dict[OrderLeg, float]
    ) -> float:
        """Calculate total cash requirement (negative means cash received)."""
        total_cash_impact = 0.0

        for leg in legs:
            cost_basis = leg_prices[leg]

            # Validate quantity/price signs
            if leg.order_type.value.startswith("b") and (
                leg.quantity < 0 or cost_basis < 0
            ):
                raise OrderExecutionError(
                    "Buy orders must have positive quantity and positive price"
                )

            if leg.order_type.value.startswith("s") and (
                leg.quantity > 0 or cost_basis > 0
            ):
                raise OrderExecutionError(
                    "Sell orders must have negative quantity and negative price"
                )

            # Calculate cash impact with multiplier
            multiplier = 100 if isinstance(leg.asset, Option) else 1
            cash_impact = (
                abs(cost_basis * leg.quantity) * copysign(1, leg.quantity) * multiplier
            )
            total_cash_impact -= cash_impact  # Negative because we're paying cash

        return total_cash_impact

    async def _open_position(self, leg: OrderLeg, cost_basis: float) -> Position:
        """Create a new position from an opening leg."""

        # Get current quote for position tracking
        quote = None
        if self.quote_service:
            quote = await self.quote_service.get_quote(leg.asset)

        position = Position(
            symbol=leg.asset.symbol,
            quantity=leg.quantity,
            avg_price=abs(cost_basis),  # Always positive for cost basis
            asset=leg.asset,
            current_price=quote.price if quote else abs(cost_basis),
        )

        # Set options-specific fields if applicable
        if isinstance(leg.asset, Option):
            position.option_type = leg.asset.option_type
            position.strike = leg.asset.strike
            position.expiration_date = leg.asset.expiration_date
            position.underlying_symbol = leg.asset.underlying.symbol

        # Update with market data and Greeks if available
        if quote and quote.price is not None:
            position.update_market_data(quote.price, quote)

        return position

    def _close_position(
        self, leg: OrderLeg, current_positions: list[Position], fill_price: float
    ) -> list[Position]:
        """Close positions using FIFO method, return modified positions."""

        # Find closable positions
        closable_positions = [
            pos
            for pos in current_positions
            if pos.symbol == leg.asset.symbol
            and copysign(1, pos.quantity) == (copysign(1, leg.quantity) * -1)
        ]

        # Sort by creation date for FIFO (if available) or by current order
        # For now, use current order as proxy for FIFO

        quantity_to_close_remaining = abs(leg.quantity)
        modified_positions = []

        for position in closable_positions:
            if quantity_to_close_remaining <= 0:
                break

            quantity_can_close = abs(position.quantity)
            quantity_to_close = int(
                min(quantity_to_close_remaining, quantity_can_close)
            )

            # Reduce position quantity
            position.quantity += int(
                copysign(1, position.quantity) * -1 * quantity_to_close
            )
            quantity_to_close_remaining -= quantity_to_close

            # Calculate realized P&L for the closed portion
            realized_pnl = (
                (abs(fill_price) - position.avg_price)
                * quantity_to_close
                * position.multiplier
            )
            if (
                copysign(1, position.quantity + quantity_to_close) < 0
            ):  # Was short position
                realized_pnl *= -1
            position.realized_pnl += realized_pnl

            modified_positions.append(position)

        return modified_positions


class OrderFillSimulator:
    """
    A stub for the OrderFillSimulator.
    """

    pass


# Alias for backwards compatibility
OrderExecutionService = OrderExecutionEngine
