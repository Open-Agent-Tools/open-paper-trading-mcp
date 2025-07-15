"""Market adapter implementations."""

from typing import Dict, List, Optional, Any
from datetime import datetime
import uuid

from app.adapters.base import MarketAdapter, QuoteAdapter
from app.models.orders import Order, OrderStatus, OrderAction, OrderType
from app.services.estimators import MidpointEstimator, WorstCaseEstimator


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
    ) -> Dict[str, float]:
        """Calculate the full impact of the order."""
        # Calculate executed price based on order type
        if self.order.order_type == OrderType.MARKET:
            # Market orders get slight slippage
            slippage_mult = 1 + (slippage_bps / 10000)
            if self.order.action in [
                OrderAction.BUY,
                OrderAction.BUY_TO_OPEN,
                OrderAction.BUY_TO_CLOSE,
            ]:
                self.executed_price = self.current_price * slippage_mult
            else:
                self.executed_price = self.current_price / slippage_mult
        else:
            # Limit orders execute at limit price or better
            self.executed_price = self.order.limit_price or self.current_price

        # Calculate costs
        self.slippage = (
            abs(self.executed_price - self.current_price) * self.order.quantity
        )
        self.commission = commission_per_share * self.order.quantity

        # Total cost/proceeds
        if self.order.action in [
            OrderAction.BUY,
            OrderAction.BUY_TO_OPEN,
            OrderAction.BUY_TO_CLOSE,
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
        self.filled_orders: List[Order] = []
        self.midpoint_estimator = MidpointEstimator()
        self.worst_case_estimator = WorstCaseEstimator()

    def submit_order(self, order: Order) -> Order:
        """Submit an order to the market."""
        # Generate order ID if not present
        if not order.id:
            order.id = str(uuid.uuid4())[:8]

        # Set submission time
        order.submitted_at = datetime.utcnow()
        order.status = OrderStatus.PENDING

        # Add to pending orders
        self.pending_orders.append(order)

        # Try to fill immediately if market order
        if order.order_type == OrderType.MARKET:
            self._try_fill_order(order)

        return order

    def cancel_order(self, order_id: str) -> bool:
        """Cancel a pending order."""
        for i, order in enumerate(self.pending_orders):
            if order.id == order_id:
                order.status = OrderStatus.CANCELLED
                self.pending_orders.pop(i)
                return True
        return False

    def get_pending_orders(self, account_id: Optional[str] = None) -> List[Order]:
        """Get pending orders, optionally filtered by account."""
        if account_id:
            return [o for o in self.pending_orders if o.account_id == account_id]
        return self.pending_orders.copy()

    def simulate_order(self, order: Order) -> Dict[str, Any]:
        """Simulate order execution without actually executing."""
        # Get current quote
        quote = self.quote_adapter.get_quote(order.asset)
        if not quote:
            return {"success": False, "reason": "No quote available", "impact": None}

        # Use appropriate estimator
        if order.order_type == OrderType.MARKET:
            current_price = self.worst_case_estimator.estimate(quote, order.quantity)
        else:
            current_price = self.midpoint_estimator.estimate(quote, order.quantity)

        # Calculate impact
        impact = OrderImpact(order, current_price)
        impact_data = impact.calculate_impact()

        # Check if limit order would fill
        would_fill = True
        if order.order_type == OrderType.LIMIT and order.limit_price:
            if order.action in [
                OrderAction.BUY,
                OrderAction.BUY_TO_OPEN,
                OrderAction.BUY_TO_CLOSE,
            ]:
                would_fill = quote.ask is not None and order.limit_price >= quote.ask
            else:
                would_fill = quote.bid is not None and order.limit_price <= quote.bid

        return {
            "success": True,
            "would_fill": would_fill,
            "current_price": current_price,
            "impact": impact_data,
            "quote": quote,
        }

    def process_pending_orders(self) -> List[Order]:
        """Process all pending orders and return filled orders."""
        filled = []
        remaining = []

        for order in self.pending_orders:
            if self._try_fill_order(order):
                filled.append(order)
            else:
                remaining.append(order)

        self.pending_orders = remaining
        return filled

    def _try_fill_order(self, order: Order) -> bool:
        """Try to fill an order based on current market conditions."""
        # Get current quote
        quote = self.quote_adapter.get_quote(order.asset)
        if not quote:
            return False

        # Check if order can be filled
        can_fill = False
        fill_price = 0.0

        if order.order_type == OrderType.MARKET:
            # Market orders always fill if quote available
            can_fill = True
            if order.action in [
                OrderAction.BUY,
                OrderAction.BUY_TO_OPEN,
                OrderAction.BUY_TO_CLOSE,
            ]:
                fill_price = quote.ask or quote.last or 0.0
            else:
                fill_price = quote.bid or quote.last or 0.0

        elif order.order_type == OrderType.LIMIT and order.limit_price:
            # Limit orders fill if price is favorable
            if order.action in [
                OrderAction.BUY,
                OrderAction.BUY_TO_OPEN,
                OrderAction.BUY_TO_CLOSE,
            ]:
                if quote.ask and order.limit_price >= quote.ask:
                    can_fill = True
                    fill_price = quote.ask
            else:
                if quote.bid and order.limit_price <= quote.bid:
                    can_fill = True
                    fill_price = quote.bid

        elif order.order_type == OrderType.STOP and order.stop_price:
            # Stop orders convert to market when stop price is hit
            if order.action in [
                OrderAction.BUY,
                OrderAction.BUY_TO_OPEN,
                OrderAction.BUY_TO_CLOSE,
            ]:
                if quote.last and quote.last >= order.stop_price:
                    can_fill = True
                    fill_price = quote.ask or quote.last or 0.0
            else:
                if quote.last and quote.last <= order.stop_price:
                    can_fill = True
                    fill_price = quote.bid or quote.last or 0.0

        # Fill the order if possible
        if can_fill and fill_price > 0:
            order.status = OrderStatus.FILLED
            order.filled_at = datetime.utcnow()
            order.fill_price = fill_price
            self.filled_orders.append(order)
            return True

        return False
