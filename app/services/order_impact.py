"""
Order Impact Analysis Service.

Adapted from reference implementation OrderImpact with enhanced analysis capabilities.
Provides before/after simulation of orders to assess their impact on accounts.
"""

from copy import deepcopy
from datetime import datetime
from typing import Any

from pydantic import BaseModel, Field

from app.core.exceptions import ValidationError
from app.models.assets import Asset, Option
from app.schemas.orders import MultiLegOrder, Order, OrderLeg
from app.schemas.positions import Position
from app.services.validation import AccountValidator


class AccountSnapshot(BaseModel):
    """Snapshot of account state for impact analysis."""

    cash_balance: float = Field(..., description="Available cash")
    positions: list[Position] = Field(
        default_factory=list, description="Current positions"
    )
    total_value: float = Field(..., description="Total account value")
    buying_power: float = Field(..., description="Available buying power")
    timestamp: datetime = Field(
        default_factory=datetime.now, description="Snapshot timestamp"
    )


class OrderImpactAnalysis(BaseModel):
    """Complete analysis of order impact on account."""

    # Order information
    order_id: str | None = Field(None, description="Order identifier")
    order_type: str = Field(..., description="Type of order analyzed")
    estimated_fill_price: float | None = Field(None, description="Estimated fill price")
    commission: float = Field(default=0.0, description="Estimated commission")

    # Before/after snapshots
    before: AccountSnapshot = Field(..., description="Account state before order")
    after: AccountSnapshot = Field(..., description="Account state after order")

    # Impact calculations
    cash_impact: float = Field(..., description="Change in cash balance")
    buying_power_impact: float = Field(..., description="Change in buying power")
    position_impact: dict[str, Any] = Field(
        default_factory=dict, description="Changes to positions"
    )

    # Risk assessments
    validation_errors: list[str] = Field(
        default_factory=list, description="Validation errors"
    )
    approval_status: str = Field(..., description="Order approval status")


class OrderImpactService:
    """Service for analyzing the impact of orders on accounts."""

    def __init__(
        self,
        validator: AccountValidator | None = None,
    ) -> None:
        """Initialize with validation services."""
        self.validator = validator or AccountValidator()

    def analyze_order_impact(
        self,
        account_data: dict[str, Any],
        order: Order | MultiLegOrder | list[OrderLeg],
        quote_adapter: Any = None,
        estimated_fill_prices: dict[str, float] | None = None,
    ) -> OrderImpactAnalysis:
        """
        Analyze the complete impact of an order on an account.

        Args:
            account_data: Current account state
            order: Order to analyze
            quote_adapter: Quote adapter for price data
            estimated_fill_prices: Override prices for simulation

        Returns:
            Complete impact analysis
        """
        # Create before snapshot
        before_snapshot = self._create_account_snapshot(account_data, quote_adapter)

        # Initialize validation errors
        validation_errors: list[str] = []

        # Simulate order execution
        after_account_data = self._simulate_order_execution(
            account_data, order, quote_adapter, estimated_fill_prices
        )
        after_snapshot = self._create_account_snapshot(
            after_account_data, quote_adapter
        )

        # Calculate impacts
        cash_impact = after_snapshot.cash_balance - before_snapshot.cash_balance
        buying_power_impact = after_snapshot.buying_power - before_snapshot.buying_power

        # Analyze position changes
        position_impact = self._analyze_position_changes(
            before_snapshot.positions, after_snapshot.positions
        )

        # Determine approval status
        approval_status = "approved" if not validation_errors else "rejected"

        return OrderImpactAnalysis(
            order_id=getattr(order, "id", None),
            order_type=self._get_order_type_description(order),
            estimated_fill_price=self._get_estimated_fill_price(
                order, estimated_fill_prices
            ),
            before=before_snapshot,
            after=after_snapshot,
            cash_impact=cash_impact,
            buying_power_impact=buying_power_impact,
            position_impact=position_impact,
            validation_errors=validation_errors,
            approval_status=approval_status,
        )

    def preview_order(
        self,
        account_data: dict[str, Any],
        order: Order | MultiLegOrder,
        quote_adapter: Any = None,
    ) -> dict[str, Any]:
        """
        Quick preview of order impact for UI display.

        Returns:
            Simplified impact summary
        """
        analysis = self.analyze_order_impact(account_data, order, quote_adapter)

        return {
            "estimated_cost": abs(analysis.cash_impact),
            "approval_status": analysis.approval_status,
            "buying_power_after": analysis.after.buying_power,
            "errors": analysis.validation_errors[:3],  # Top 3 errors
            "estimated_fill": analysis.estimated_fill_price,
        }

    def _create_account_snapshot(
        self, account_data: dict[str, Any], quote_adapter: Any = None
    ) -> AccountSnapshot:
        """Create a snapshot of current account state."""

        # Extract basic account info
        cash_balance = account_data.get("cash_balance", 0.0)
        positions = account_data.get("positions", [])

        # Convert to Position objects if needed
        position_objects: list[Position] = []
        for pos in positions:
            if isinstance(pos, Position):
                position_objects.append(pos)
            else:
                # Convert dict to Position object
                position_objects.append(Position(**pos))

        # Calculate total value
        total_invested = sum(
            pos.market_value for pos in position_objects if pos.market_value is not None
        )
        total_value = cash_balance + total_invested

        # Calculate buying power (simplified)
        buying_power = cash_balance

        return AccountSnapshot(
            cash_balance=cash_balance,
            positions=position_objects,
            total_value=total_value,
            buying_power=buying_power,
        )

    def _simulate_order_execution(
        self,
        account_data: dict[str, Any],
        order: Order | MultiLegOrder | list[OrderLeg],
        quote_adapter: Any = None,
        estimated_fill_prices: dict[str, float] | None = None,
    ) -> dict[str, Any]:
        """Simulate order execution and return modified account data."""

        # Deep copy account data to avoid modifying original
        simulated_account = deepcopy(account_data)

        # Convert order to legs for uniform processing
        if isinstance(order, Order):
            legs = [order.to_leg()]
        elif isinstance(order, MultiLegOrder):
            legs = order.legs
        else:
            legs = order  # Already a list of legs

        # Simulate each leg
        for leg in legs:
            self._simulate_leg_execution(
                simulated_account, leg, quote_adapter, estimated_fill_prices
            )

        return simulated_account

    def _simulate_leg_execution(
        self,
        account_data: dict[str, Any],
        leg: OrderLeg,
        quote_adapter: Any = None,
        estimated_fill_prices: dict[str, float] | None = None,
    ) -> None:
        """Simulate execution of a single order leg."""

        asset = leg.asset
        symbol = asset.symbol if hasattr(asset, "symbol") else str(asset)
        quantity = leg.quantity

        # Determine fill price
        if estimated_fill_prices and symbol in estimated_fill_prices:
            fill_price = estimated_fill_prices[symbol]
        elif leg.price is not None:
            fill_price = abs(leg.price)  # Use order price
        elif quote_adapter:
            quote = quote_adapter.get_quote(asset)
            fill_price = quote.price if quote and quote.price else 0.0
        else:
            fill_price = 0.0  # No price available

        # Calculate multiplier
        multiplier = 100 if isinstance(asset, Option) else 1

        # Calculate cash impact
        cash_impact = -fill_price * quantity * multiplier
        account_data["cash_balance"] += cash_impact

        # Update or create position
        self._update_position_in_simulation(
            account_data, symbol, quantity, fill_price, asset
        )

    def _update_position_in_simulation(
        self,
        account_data: dict[str, Any],
        symbol: str,
        quantity: int,
        fill_price: float,
        asset: Asset,
    ) -> None:
        """Update position in simulated account."""

        positions = account_data.setdefault("positions", [])

        # Find existing position
        existing_position = None
        for i, pos in enumerate(positions):
            pos_symbol = pos.get("symbol") if isinstance(pos, dict) else pos.symbol
            if pos_symbol == symbol:
                existing_position = i
                break

        if existing_position is not None:
            # Update existing position
            pos = positions[existing_position]
            if isinstance(pos, dict):
                old_quantity = pos.get("quantity", 0)
                old_avg_price = pos.get("avg_price", 0)
            else:
                old_quantity = pos.quantity
                old_avg_price = pos.avg_price

            new_quantity = old_quantity + quantity

            if new_quantity == 0:
                # Position closed - remove it
                positions.pop(existing_position)
            else:
                # Update average price
                if (old_quantity > 0 and quantity > 0) or (
                    old_quantity < 0 and quantity < 0
                ):
                    # Same direction - weighted average
                    total_cost = (old_quantity * old_avg_price) + (
                        quantity * fill_price
                    )
                    new_avg_price = total_cost / new_quantity
                else:
                    # Opposite direction - keep old average price
                    new_avg_price = old_avg_price

                # Update position
                if isinstance(pos, dict):
                    pos["quantity"] = new_quantity
                    pos["avg_price"] = new_avg_price
                else:
                    pos.quantity = new_quantity
                    pos.avg_price = new_avg_price
        else:
            # Create new position
            new_position: dict[str, Any] = {
                "symbol": symbol,
                "quantity": quantity,
                "avg_price": fill_price,
                "current_price": fill_price,
                "unrealized_pnl": 0.0,
                "realized_pnl": 0.0,
                "asset": asset,
            }

            # Add options-specific fields
            if isinstance(asset, Option):
                new_position.update(
                    {
                        "option_type": asset.option_type,
                        "strike": asset.strike,
                        "expiration_date": asset.expiration_date,
                        "underlying_symbol": asset.underlying.symbol,
                    }
                )

            positions.append(new_position)

    def _analyze_position_changes(
        self, before_positions: list[Position], after_positions: list[Position]
    ) -> dict[str, Any]:
        """Analyze changes in positions."""

        changes: dict[str, Any] = {
            "new_positions": [],
            "closed_positions": [],
            "modified_positions": [],
            "summary": {},
        }

        before_symbols = {pos.symbol for pos in before_positions}
        after_symbols = {pos.symbol for pos in after_positions}

        # Find new positions
        new_symbols = after_symbols - before_symbols
        changes["new_positions"] = [
            pos.symbol for pos in after_positions if pos.symbol in new_symbols
        ]

        # Find closed positions
        closed_symbols = before_symbols - after_symbols
        changes["closed_positions"] = [
            pos.symbol for pos in before_positions if pos.symbol in closed_symbols
        ]

        # Find modified positions
        for before_pos in before_positions:
            for after_pos in after_positions:
                if (
                    before_pos.symbol == after_pos.symbol
                    and before_pos.quantity != after_pos.quantity
                ):
                    changes["modified_positions"].append(
                        {
                            "symbol": before_pos.symbol,
                            "quantity_change": after_pos.quantity - before_pos.quantity,
                            "before_quantity": before_pos.quantity,
                            "after_quantity": after_pos.quantity,
                        }
                    )

        changes["summary"] = {
            "positions_opened": len(changes["new_positions"]),
            "positions_closed": len(changes["closed_positions"]),
            "positions_modified": len(changes["modified_positions"]),
        }

        return changes

    def _calculate_greeks_impact(
        self, before_positions: list[Position], after_positions: list[Position]
    ) -> dict[str, float | None]:
        """Calculate impact on portfolio Greeks."""

        def sum_position_greeks(positions: list[Position], greek: str) -> float:
            return sum(
                getattr(pos, greek, 0) or 0 for pos in positions if pos.is_option
            )

        before_delta = sum_position_greeks(before_positions, "delta")
        after_delta = sum_position_greeks(after_positions, "delta")

        before_gamma = sum_position_greeks(before_positions, "gamma")
        after_gamma = sum_position_greeks(after_positions, "gamma")

        before_theta = sum_position_greeks(before_positions, "theta")
        after_theta = sum_position_greeks(after_positions, "theta")

        before_vega = sum_position_greeks(before_positions, "vega")
        after_vega = sum_position_greeks(after_positions, "vega")

        return {
            "delta": after_delta - before_delta,
            "gamma": after_gamma - before_gamma,
            "theta": after_theta - before_theta,
            "vega": after_vega - before_vega,
        }

    def _validate_order(
        self,
        account_data: dict[str, Any],
        order: Order | MultiLegOrder | list[OrderLeg],
        quote_adapter: Any = None,
    ) -> list[str]:
        """Validate order using account validation service."""

        try:
            # Use existing validator if available
            self.validator.validate_account_state(
                cash_balance=account_data.get("cash_balance", 0.0),
                positions=account_data.get("positions", []),
            )
        except ValidationError as e:
            return [f"Validation error: {e!s}"]

        return []

    def _has_covering_position(self, option: Option, positions: list[Position]) -> bool:
        """Check if there's a position that covers the naked option."""

        for pos in positions:
            # Check for underlying stock position
            if (
                not pos.is_option
                and pos.symbol == option.underlying.symbol
                and pos.quantity >= 100
            ):  # Sufficient shares to cover
                return True

            # Check for covering option position
            if (
                pos.is_option
                and pos.asset is not None
                and hasattr(pos.asset, "underlying")
                and pos.asset.underlying is not None
                and pos.asset.underlying.symbol == option.underlying.symbol
            ):
                # Add specific logic for different spread types
                return True

        return False

    def _get_order_type_description(
        self, order: Order | MultiLegOrder | list[OrderLeg]
    ) -> str:
        """Get human-readable description of order type."""

        if isinstance(order, Order):
            return f"Single leg {order.order_type.value}"
        elif isinstance(order, MultiLegOrder):
            return f"Multi-leg order with {len(order.legs)} legs"
        elif isinstance(order, list):
            return f"Order with {len(order)} legs"
        else:
            return "Unknown order type"

    def _get_estimated_fill_price(
        self,
        order: Order | MultiLegOrder | list[OrderLeg],
        estimated_fill_prices: dict[str, float] | None = None,
    ) -> float | None:
        """Get estimated fill price for the order."""

        if isinstance(order, Order):
            symbol = order.symbol
            if estimated_fill_prices and symbol in estimated_fill_prices:
                return estimated_fill_prices[symbol]
            return order.price
        elif isinstance(order, MultiLegOrder):
            return order.net_price

        return None


# Convenience functions
def analyze_order_impact(
    account_data: dict[str, Any],
    order: Order | MultiLegOrder,
    quote_adapter: Any = None,
    estimated_fill_prices: dict[str, float] | None = None,
) -> OrderImpactAnalysis:
    """Quick order impact analysis."""
    service = OrderImpactService()
    return service.analyze_order_impact(
        account_data, order, quote_adapter, estimated_fill_prices
    )


def preview_order_impact(
    account_data: dict[str, Any],
    order: Order | MultiLegOrder,
    quote_adapter: Any = None,
) -> dict[str, Any]:
    """Quick order preview for UI."""
    service = OrderImpactService()
    return service.preview_order(account_data, order, quote_adapter)
