"""Market adapter implementations."""

import uuid
from datetime import datetime
from typing import Any

from app.adapters.base import MarketAdapter, QuoteAdapter
from app.models.assets import asset_factory
from app.schemas.orders import Order, OrderCondition, OrderStatus, OrderType
from app.services.estimators import MarketEstimator, MidpointEstimator


class OrderImpact:
    """Analyze the impact of an order on an account."""

    def __init__(self, order: Order, current_price: float):
        self.order = order
        self.current_price = current_price
        self.executed_price = current_price  # Will be updated based on order type
        self.slippage = 0.0
        self.commission = 0.0
        self.total_cost = 0.0
        self.impact_percentage = 0.0

    def calculate_impact(
        self, slippage_bps: float = 10.0, commission_per_share: float = 0.01
    ) -> dict[str, float]:
        """Calculate the full impact of the order."""
        # Calculate executed price based on order type
        if self.order.condition == OrderCondition.MARKET:
            # Market orders get slight slippage
            slippage_mult = 1 + (slippage_bps / 10000)
            if self.order.order_type in [
                OrderType.BUY,
                OrderType.BTO,
                OrderType.BTC,
            ]:
                self.executed_price = self.current_price * slippage_mult
            else:
                self.executed_price = self.current_price / slippage_mult
        else:
            # Limit orders execute at limit price or better
            self.executed_price = self.order.price or self.current_price

        # Calculate costs
        self.slippage = (
            abs(self.executed_price - self.current_price) * self.order.quantity
        )
        self.commission = commission_per_share * self.order.quantity

        # Total cost/proceeds
        if self.order.order_type in [
            OrderType.BUY,
            OrderType.BTO,
            OrderType.BTC,
        ]:
            self.total_cost = (
                self.executed_price * self.order.quantity
            ) + self.commission
        else:
            self.total_cost = (
                self.executed_price * self.order.quantity
            ) - self.commission

        # Impact as percentage of order value
        order_value = self.current_price * self.order.quantity
        if order_value > 0:
            self.impact_percentage = (
                (self.slippage + self.commission) / order_value * 100
            )

        return {
            "executed_price": self.executed_price,
            "slippage": self.slippage,
            "commission": self.commission,
            "total_cost": self.total_cost,
            "impact_percentage": self.impact_percentage,
        }


class PaperMarketAdapter(MarketAdapter):
    """Paper trading market adapter with order simulation."""

    def __init__(self, quote_adapter: QuoteAdapter):
        super().__init__(quote_adapter)
        self.filled_orders: list[Order] = []
        self.midpoint_estimator = MidpointEstimator()
        self.market_estimator = MarketEstimator()

    async def submit_order(self, order: Order) -> Order:
        """Submit an order to the market."""
        # Generate order ID if not present
        if not order.id:
            order.id = str(uuid.uuid4())[:8]

        # Set submission time
        order.created_at = datetime.utcnow()
        order.status = OrderStatus.PENDING

        # Add to pending orders
        self.pending_orders.append(order)

        # Try to fill immediately if market order
        if order.condition == OrderCondition.MARKET:
            await self._try_fill_order(order)

        return order

    def cancel_order(self, order_id: str) -> bool:
        """Cancel a pending order."""
        for i, order in enumerate(self.pending_orders):
            if order.id == order_id:
                order.status = OrderStatus.CANCELLED
                self.pending_orders.pop(i)
                return True
        return False

    def get_pending_orders(self, account_id: str | None = None) -> list[Order]:
        """Get pending orders, optionally filtered by account."""
        if account_id:
            # Note: Order schema doesn't have account_id, so return all for now
            # TODO: Add account_id to Order schema if needed
            return self.pending_orders.copy()
        return self.pending_orders.copy()

    async def simulate_order(self, order: Order) -> dict[str, Any]:
        """Simulate order execution without actually executing."""
        # Get current quote
        asset = asset_factory(order.symbol)
        if not asset:
            return {"success": False, "reason": "Invalid symbol", "impact": None}
        quote = await self.quote_adapter.get_quote(asset)
        if not quote:
            return {"success": False, "reason": "No quote available", "impact": None}

        # Use appropriate estimator
        if order.condition == OrderCondition.MARKET:
            current_price = self.market_estimator.estimate(quote, order.quantity)
        else:
            current_price = self.midpoint_estimator.estimate(quote, order.quantity)

        # Calculate impact
        impact = OrderImpact(order, current_price)
        impact_data = impact.calculate_impact()

        # Check if limit order would fill
        would_fill = True
        if order.condition == OrderCondition.LIMIT and order.price:
            if order.order_type in [
                OrderType.BUY,
                OrderType.BTO,
                OrderType.BTC,
            ]:
                would_fill = quote.ask is not None and order.price >= quote.ask
            else:
                would_fill = quote.bid is not None and order.price <= quote.bid

        return {
            "success": True,
            "would_fill": would_fill,
            "current_price": current_price,
            "impact": impact_data,
            "quote": quote,
        }

    async def process_pending_orders(self) -> list[Order]:
        """Process all pending orders and return filled orders."""
        filled = []
        remaining = []

        for order in self.pending_orders:
            if await self._try_fill_order(order):
                filled.append(order)
            else:
                remaining.append(order)

        self.pending_orders = remaining
        return filled

    async def _try_fill_order(self, order: Order) -> bool:
        """Try to fill an order based on current market conditions."""
        # Get current quote
        asset = asset_factory(order.symbol)
        if not asset:
            return False
        quote = await self.quote_adapter.get_quote(asset)
        if not quote:
            return False

        # Check if order can be filled
        can_fill = False
        fill_price = 0.0

        if order.condition == OrderCondition.MARKET:
            # Market orders always fill if quote available
            can_fill = True
            if order.order_type in [
                OrderType.BUY,
                OrderType.BTO,
                OrderType.BTC,
            ]:
                fill_price = quote.ask or quote.price or 0.0
            else:
                fill_price = quote.bid or quote.price or 0.0

        elif order.condition == OrderCondition.LIMIT and order.price:
            # Limit orders fill if price is favorable
            if order.order_type in [
                OrderType.BUY,
                OrderType.BTO,
                OrderType.BTC,
            ]:
                if quote.ask and order.price >= quote.ask:
                    can_fill = True
                    fill_price = quote.ask
            else:
                if quote.bid and order.price <= quote.bid:
                    can_fill = True
                    fill_price = quote.bid

        elif order.condition == OrderCondition.STOP and order.price:
            # Stop orders convert to market when stop price is hit
            if order.order_type in [
                OrderType.BUY,
                OrderType.BTO,
                OrderType.BTC,
            ]:
                if quote.price and quote.price >= order.price:
                    can_fill = True
                    fill_price = quote.ask or quote.price or 0.0
            else:
                if quote.price and quote.price <= order.price:
                    can_fill = True
                    fill_price = quote.bid or quote.price or 0.0

        # Fill the order if possible
        if can_fill and fill_price > 0:
            order.status = OrderStatus.FILLED
            order.filled_at = datetime.utcnow()
            # Note: fill_price not stored in schema, would need to add if needed
            self.filled_orders.append(order)
            return True

        return False
