"""
Options expiration engine for automatic expiration processing.

Migrated from reference implementation with modern Python patterns and enhanced functionality.
Handles automatic ITM/OTM option processing, assignment, and exercise simulation.
"""

import copy
from datetime import date
from math import copysign
from typing import Any

from pydantic import BaseModel, Field

from app.adapters.base import QuoteAdapter
from app.models.assets import Call, Option, Put, asset_factory
from app.schemas.positions import Position


class ExpirationResult(BaseModel):
    """Result of options expiration processing."""

    expired_positions: list[Position] = Field(
        default_factory=list, description="Positions that expired"
    )
    new_positions: list[Position] = Field(
        default_factory=list, description="New positions created from expiration"
    )
    cash_impact: float = Field(0.0, description="Net cash impact from expiration")
    assignments: list[dict[str, Any]] = Field(
        default_factory=list, description="Assignment details"
    )
    exercises: list[dict[str, Any]] = Field(
        default_factory=list, description="Exercise details"
    )
    worthless_expirations: list[dict[str, Any]] = Field(
        default_factory=list, description="Options expired worthless"
    )
    warnings: list[str] = Field(
        default_factory=list, description="Warnings during processing"
    )
    errors: list[str] = Field(
        default_factory=list, description="Errors during processing"
    )


class OptionsExpirationEngine:
    """
    Engine for processing options expiration with automatic ITM/OTM handling.

    Handles:
    - Automatic expiration processing
    - Assignment and exercise simulation
    - Cash and position adjustments
    - FIFO position closing logic
    - Warning generation for insufficient underlying positions
    """

    def __init__(self) -> None:
        self.current_date: date | None = None

    def process_account_expirations(
        self,
        account_data: dict[str, Any],
        quote_adapter: QuoteAdapter,
        processing_date: date | None = None,
    ) -> ExpirationResult:
        """
        Process all expired options in an account.

        Args:
            account_data: Account dictionary with positions and cash_balance
            quote_adapter: Quote adapter for current prices
            processing_date: Date to process expirations for, uses today if None

        Returns:
            ExpirationResult with all changes and details
        """
        if processing_date is None:
            processing_date = date.today()

        self.current_date = processing_date

        # Make a copy to avoid modifying original
        account = copy.deepcopy(account_data)
        result = ExpirationResult(cash_impact=0.0)

        if not account.get("positions"):
            return result

        # Find expired option positions
        expired_positions = self._find_expired_positions(
            account["positions"], processing_date
        )

        if not expired_positions:
            return result

        # Group expired positions by underlying
        expired_by_underlying = self._group_by_underlying(expired_positions)

        # Process each underlying separately
        for underlying_symbol, underlying_positions in expired_by_underlying.items():
            try:
                underlying_result = self._process_underlying_expirations(
                    account, underlying_symbol, underlying_positions, quote_adapter
                )

                # Merge results
                result.expired_positions.extend(underlying_result.expired_positions)
                result.new_positions.extend(underlying_result.new_positions)
                result.cash_impact += underlying_result.cash_impact
                result.assignments.extend(underlying_result.assignments)
                result.exercises.extend(underlying_result.exercises)
                result.worthless_expirations.extend(
                    underlying_result.worthless_expirations
                )
                result.warnings.extend(underlying_result.warnings)
                result.errors.extend(underlying_result.errors)

            except Exception as e:
                result.errors.append(
                    f"Error processing {underlying_symbol} expirations: {e!s}"
                )

        # Remove expired positions with zero quantity
        account["positions"] = [
            pos
            for pos in account["positions"]
            if not (isinstance(pos, dict) and pos.get("quantity", 0) == 0)
        ]

        return result

    def _find_expired_positions(
        self, positions: list[dict[str, object]], processing_date: date
    ) -> list[dict[str, object]]:
        """Find all expired option positions."""
        expired = []

        for position in positions:
            # Handle both dict and Position object
            if isinstance(position, dict):
                symbol = str(position.get("symbol", ""))
                quantity_val = position.get("quantity", 0)
                quantity = (
                    int(quantity_val)
                    if isinstance(quantity_val, int | float | str)
                    else 0
                )
            else:
                symbol = position.symbol
                quantity = position.quantity

            if quantity == 0:
                continue

            # Check if it's an option
            asset = asset_factory(symbol)
            if isinstance(asset, Option):
                if asset.expiration_date <= processing_date:
                    expired.append(position)

        return expired

    def _group_by_underlying(
        self, expired_positions: list[dict[str, object]]
    ) -> dict[str, list[dict[str, object]]]:
        """Group expired positions by underlying symbol."""
        groups: dict[str, list[dict[str, object]]] = {}

        for position in expired_positions:
            if isinstance(position, dict):
                symbol = str(position.get("symbol", ""))
            else:
                symbol = position.symbol

            asset = asset_factory(symbol)
            if isinstance(asset, Option):
                underlying_symbol = asset.underlying.symbol
                if underlying_symbol not in groups:
                    groups[underlying_symbol] = []
                groups[underlying_symbol].append(position)

        return groups

    def _process_underlying_expirations(
        self,
        account: dict[str, Any],
        underlying_symbol: str,
        expired_positions: list[dict[str, object]],
        quote_adapter: QuoteAdapter,
    ) -> ExpirationResult:
        """Process expirations for a specific underlying."""
        result = ExpirationResult(cash_impact=0.0)

        # Get current underlying quote
        try:
            underlying_asset = asset_factory(underlying_symbol)
            if underlying_asset is None:
                result.errors.append(f"Could not create asset for {underlying_symbol}")
                return result
            underlying_quote = quote_adapter.get_quote(underlying_asset)
            if underlying_quote is None:
                result.errors.append(f"Could not get quote for {underlying_symbol}")
                return result

            underlying_price = underlying_quote.price
            if underlying_price is None:
                result.errors.append(f"Quote for {underlying_symbol} has no price")
                return result

        except Exception as e:
            result.errors.append(f"Error getting quote for {underlying_symbol}: {e!s}")
            return result

        # Get current equity positions in this underlying
        equity_positions = self._get_equity_positions(
            account["positions"], underlying_symbol
        )
        long_equity = sum(
            int(pos["quantity"])
            for pos in equity_positions
            if isinstance(pos["quantity"], int | float) and int(pos["quantity"]) > 0
        )
        short_equity = sum(
            int(pos["quantity"])
            for pos in equity_positions
            if isinstance(pos["quantity"], int | float) and int(pos["quantity"]) < 0
        )

        # Process each expired position
        for position in expired_positions:
            try:
                position_result = self._process_single_expiration(
                    account, position, underlying_price, long_equity, short_equity
                )

                # Update equity counts for next iteration
                if position_result.new_positions:
                    for new_pos in position_result.new_positions:
                        if not isinstance(asset_factory(new_pos.symbol), Option):
                            if new_pos.quantity > 0:
                                long_equity += new_pos.quantity
                            else:
                                short_equity += new_pos.quantity

                # Merge results
                result.expired_positions.extend(position_result.expired_positions)
                result.new_positions.extend(position_result.new_positions)
                result.cash_impact += position_result.cash_impact
                result.assignments.extend(position_result.assignments)
                result.exercises.extend(position_result.exercises)
                result.worthless_expirations.extend(
                    position_result.worthless_expirations
                )
                result.warnings.extend(position_result.warnings)

            except Exception as e:
                result.errors.append(f"Error processing position {position}: {e!s}")

        return result

    def _process_single_expiration(
        self,
        account: dict[str, Any],
        position: dict[str, Any],
        underlying_price: float,
        long_equity: int,
        short_equity: int,
    ) -> ExpirationResult:
        """Process a single expired option position."""
        result = ExpirationResult(cash_impact=0.0)

        # Extract position data
        symbol = position.get("symbol", "")
        quantity = position.get("quantity", 0)
        cost_basis = position.get("avg_price", 0.0)

        asset = asset_factory(symbol)
        if not isinstance(asset, Option):
            return result

        # Check if option is ITM
        intrinsic_value = asset.get_intrinsic_value(underlying_price)
        is_itm = intrinsic_value > 0

        if not is_itm:
            # Option expired worthless
            result.worthless_expirations.append(
                {
                    "symbol": symbol,
                    "quantity": quantity,
                    "strike": asset.strike,
                    "option_type": asset.option_type,
                    "cost_basis": cost_basis,
                    "intrinsic_value": 0.0,
                }
            )

            # Set position quantity to 0 (will be removed later)
            position["quantity"] = 0
            result.expired_positions.append(
                Position(
                    symbol=symbol, quantity=0, avg_price=cost_basis, current_price=0.0
                )
            )

        else:
            # Option is ITM - process assignment/exercise
            if isinstance(asset, Call):
                if quantity > 0:
                    # Long call exercise
                    exercise_result = self._exercise_long_call(
                        account, asset, quantity, cost_basis, underlying_price
                    )
                    result.exercises.append(exercise_result)
                else:
                    # Short call assignment
                    assignment_result = self._assign_short_call(
                        account, asset, quantity, underlying_price, long_equity
                    )
                    result.assignments.append(assignment_result)
                    if assignment_result.get("warning"):
                        result.warnings.append(assignment_result["warning"])

            elif isinstance(asset, Put):
                if quantity > 0:
                    # Long put exercise
                    exercise_result = self._exercise_long_put(
                        account, asset, quantity, cost_basis, underlying_price
                    )
                    result.exercises.append(exercise_result)
                else:
                    # Short put assignment
                    assignment_result = self._assign_short_put(
                        account, asset, quantity, underlying_price, short_equity
                    )
                    result.assignments.append(assignment_result)
                    if assignment_result.get("warning"):
                        result.warnings.append(assignment_result["warning"])

            # Set expired position to zero
            position["quantity"] = 0
            result.expired_positions.append(
                Position(
                    symbol=symbol,
                    quantity=0,
                    avg_price=cost_basis,
                    current_price=intrinsic_value,
                )
            )

        return result

    def _exercise_long_call(
        self,
        account: dict[str, Any],
        call: Call,
        quantity: int,
        cost_basis: float,
        underlying_price: float,
    ) -> dict[str, Any]:
        """Exercise long call options."""
        # Buy shares at strike price
        cash_cost = call.strike * abs(quantity) * 100
        account["cash_balance"] -= cash_cost

        # Create new stock position
        new_quantity = abs(quantity) * 100
        new_cost_basis = call.strike + abs(cost_basis)  # Strike + option premium

        # Add to existing positions or create new
        self._add_position(
            account, call.underlying.symbol, new_quantity, new_cost_basis
        )

        return {
            "type": "exercise",
            "option_type": "call",
            "option_symbol": call.symbol,
            "quantity": quantity,
            "strike": call.strike,
            "underlying_symbol": call.underlying.symbol,
            "shares_acquired": new_quantity,
            "cash_paid": cash_cost,
            "effective_cost_basis": new_cost_basis,
        }

    def _assign_short_call(
        self,
        account: dict[str, Any],
        call: Call,
        quantity: int,
        underlying_price: float,
        long_equity: int,
    ) -> dict[str, Any]:
        """Assign short call options."""
        shares_needed = abs(quantity) * 100
        cash_received = call.strike * abs(quantity) * 100

        # Check if we have enough shares to deliver
        if long_equity >= shares_needed:
            # Deliver existing shares
            self._drain_asset(
                account["positions"], call.underlying.symbol, -shares_needed
            )
            account["cash_balance"] += cash_received

            return {
                "type": "assignment",
                "option_type": "call",
                "option_symbol": call.symbol,
                "quantity": quantity,
                "strike": call.strike,
                "underlying_symbol": call.underlying.symbol,
                "shares_delivered": shares_needed,
                "cash_received": cash_received,
                "shares_source": "existing_position",
            }
        else:
            # Need to buy shares to deliver (short squeeze)
            cash_to_buy = underlying_price * shares_needed
            account["cash_balance"] -= cash_to_buy  # Buy at market
            account["cash_balance"] += cash_received  # Sell at strike

            net_cash = cash_received - cash_to_buy

            return {
                "type": "assignment",
                "option_type": "call",
                "option_symbol": call.symbol,
                "quantity": quantity,
                "strike": call.strike,
                "underlying_symbol": call.underlying.symbol,
                "shares_delivered": shares_needed,
                "cash_to_buy": cash_to_buy,
                "cash_received": cash_received,
                "net_cash": net_cash,
                "shares_source": "market_purchase",
                "warning": f"Insufficient shares for call assignment - forced to buy {shares_needed} shares at market price",
            }

    def _exercise_long_put(
        self,
        account: dict[str, Any],
        put: Put,
        quantity: int,
        cost_basis: float,
        underlying_price: float,
    ) -> dict[str, Any]:
        """Exercise long put options."""
        # Sell shares at strike price (create short position)
        cash_received = put.strike * abs(quantity) * 100
        account["cash_balance"] += cash_received

        # Create new short stock position
        new_quantity = -abs(quantity) * 100  # Negative for short
        new_cost_basis = put.strike - abs(cost_basis)  # Strike - option premium

        # Add to existing positions or create new
        self._add_position(account, put.underlying.symbol, new_quantity, new_cost_basis)

        return {
            "type": "exercise",
            "option_type": "put",
            "option_symbol": put.symbol,
            "quantity": quantity,
            "strike": put.strike,
            "underlying_symbol": put.underlying.symbol,
            "shares_sold_short": abs(new_quantity),
            "cash_received": cash_received,
            "effective_cost_basis": new_cost_basis,
        }

    def _assign_short_put(
        self,
        account: dict[str, Any],
        put: Put,
        quantity: int,
        underlying_price: float,
        short_equity: int,
    ) -> dict[str, Any]:
        """Assign short put options."""
        shares_to_buy = abs(quantity) * 100
        cash_paid = put.strike * abs(quantity) * 100

        # Check if we have short shares to cover
        if abs(short_equity) >= shares_to_buy:
            # Cover existing short position
            self._drain_asset(
                account["positions"], put.underlying.symbol, shares_to_buy
            )
            account["cash_balance"] -= cash_paid

            return {
                "type": "assignment",
                "option_type": "put",
                "option_symbol": put.symbol,
                "quantity": quantity,
                "strike": put.strike,
                "underlying_symbol": put.underlying.symbol,
                "shares_purchased": shares_to_buy,
                "cash_paid": cash_paid,
                "shares_destination": "cover_short",
            }
        else:
            # Create new long position
            account["cash_balance"] -= cash_paid
            self._add_position(
                account, put.underlying.symbol, shares_to_buy, put.strike
            )

            return {
                "type": "assignment",
                "option_type": "put",
                "option_symbol": put.symbol,
                "quantity": quantity,
                "strike": put.strike,
                "underlying_symbol": put.underlying.symbol,
                "shares_purchased": shares_to_buy,
                "cash_paid": cash_paid,
                "shares_destination": "new_long_position",
            }

    def _get_equity_positions(
        self, positions: list[dict[str, object]], underlying_symbol: str
    ) -> list[dict[str, object]]:
        """Get non-option positions for an underlying."""
        equity_positions = []

        for position in positions:
            if isinstance(position, dict):
                symbol = str(position.get("symbol", ""))
                quantity_val = position.get("quantity", 0)
                quantity = (
                    int(quantity_val)
                    if isinstance(quantity_val, int | float | str)
                    else 0
                )
            else:
                symbol = position.symbol
                quantity = position.quantity

            # Skip zero quantities and options
            if quantity == 0:
                continue

            asset = asset_factory(symbol)
            if (
                asset is not None
                and not isinstance(asset, Option)
                and asset.symbol == underlying_symbol
            ):
                equity_positions.append(position)

        return equity_positions

    def _drain_asset(
        self, positions: list[dict[str, object]], symbol: str, quantity: int
    ) -> int:
        """
        Reduce asset quantities across positions (FIFO).

        Args:
            positions: List of positions to modify
            symbol: Asset symbol to drain
            quantity: Quantity to remove (positive to reduce long, negative to reduce short)

        Returns:
            Remaining quantity that couldn't be drained
        """
        remaining_quantity = quantity

        # Find positions with opposite sign to what we're draining
        target_positions = []
        for pos in positions:
            if isinstance(pos, dict):
                pos_symbol = str(pos.get("symbol", ""))
                pos_quantity_val = pos.get("quantity", 0)
                pos_quantity = (
                    int(pos_quantity_val)
                    if isinstance(pos_quantity_val, int | float | str)
                    else 0
                )
            else:
                pos_symbol = pos.symbol
                pos_quantity = pos.quantity

            if pos_symbol == symbol and copysign(1, pos_quantity) == copysign(
                1, quantity * -1
            ):
                target_positions.append(pos)

        # Drain quantities FIFO
        for position in target_positions:
            if isinstance(position, dict):
                pos_quantity_val = position.get("quantity", 0)
                pos_quantity = (
                    int(pos_quantity_val)
                    if isinstance(pos_quantity_val, int | float | str)
                    else 0
                )
            else:
                pos_quantity = position.quantity

            if abs(remaining_quantity) <= abs(pos_quantity):
                # This position has enough to complete the drain
                if isinstance(position, dict):
                    current_qty = position["quantity"]
                    if isinstance(current_qty, int | float | str):
                        position["quantity"] = int(current_qty) + remaining_quantity
                    else:
                        position["quantity"] = remaining_quantity
                else:
                    position.quantity += remaining_quantity
                remaining_quantity = 0
                break
            else:
                # Drain this position completely and continue
                remaining_quantity += pos_quantity
                if isinstance(position, dict):
                    position["quantity"] = 0
                else:
                    position.quantity = 0

        return remaining_quantity

    def _add_position(
        self, account: dict[str, Any], symbol: str, quantity: int, cost_basis: float
    ) -> None:
        """Add quantity to existing position or create new one."""
        # Find existing position
        for position in account.get("positions", []):
            if isinstance(position, dict):
                pos_symbol = position.get("symbol", "")
                if pos_symbol == symbol:
                    # Update existing position (weighted average cost basis)
                    old_quantity = position.get("quantity", 0)
                    old_cost_basis = position.get("avg_price", 0.0)

                    new_total_quantity = old_quantity + quantity
                    if new_total_quantity != 0:
                        new_avg_cost = (
                            (old_quantity * old_cost_basis) + (quantity * cost_basis)
                        ) / new_total_quantity
                        position["quantity"] = new_total_quantity
                        position["avg_price"] = new_avg_cost
                    return

        # Create new position
        new_position = {
            "symbol": symbol,
            "quantity": quantity,
            "avg_price": cost_basis,
            "current_price": cost_basis,  # Will be updated by market data
        }

        if "positions" not in account:
            account["positions"] = []
        account["positions"].append(new_position)
