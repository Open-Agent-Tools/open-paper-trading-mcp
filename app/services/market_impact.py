"""
Market impact simulation for realistic order execution.

This module simulates real market conditions including slippage, partial fills,
and market impact based on order size and market conditions.
"""

import logging
import random
from dataclasses import dataclass
from datetime import datetime
from enum import Enum

from ..models.quotes import Quote
from ..schemas.orders import Order, OrderCondition, OrderType

logger = logging.getLogger(__name__)


class MarketCondition(Enum):
    """Market volatility conditions."""

    CALM = "calm"
    NORMAL = "normal"
    VOLATILE = "volatile"
    HIGHLY_VOLATILE = "highly_volatile"


@dataclass
class FillResult:
    """Result of an order fill simulation."""

    filled_quantity: int
    fill_price: float
    remaining_quantity: int
    slippage: float  # Absolute slippage amount
    slippage_percent: float  # Slippage as percentage
    commission: float
    total_cost: float
    partial_fill: bool
    execution_time: datetime


@dataclass
class MarketImpactConfig:
    """Configuration for market impact simulation."""

    base_slippage_bps: float = 2.0  # Base slippage in basis points
    volume_impact_factor: float = 0.1  # Impact factor for large volumes
    volatility_multiplier: dict[MarketCondition, float] = None
    partial_fill_probability: float = 0.05  # 5% chance of partial fill
    min_fill_ratio: float = 0.7  # Minimum fill ratio for partial fills
    commission_per_share: float = 0.005  # $0.005 per share commission
    max_commission: float = 10.0  # Maximum commission per order

    def __post_init__(self):
        if self.volatility_multiplier is None:
            self.volatility_multiplier = {
                MarketCondition.CALM: 0.5,
                MarketCondition.NORMAL: 1.0,
                MarketCondition.VOLATILE: 2.0,
                MarketCondition.HIGHLY_VOLATILE: 3.5,
            }


class MarketImpactSimulator:
    """
    Simulates realistic market impact for order execution.

    This simulator adds realism to paper trading by modeling:
    - Price slippage based on order size and market conditions
    - Partial fills for large orders
    - Commission costs
    - Market impact based on trading volume
    """

    def __init__(self, config: MarketImpactConfig | None = None):
        self.config = config or MarketImpactConfig()
        self.execution_history: list[FillResult] = []

    def simulate_execution(
        self,
        order: Order,
        quote: Quote,
        market_condition: MarketCondition = MarketCondition.NORMAL,
        average_volume: int | None = None,
    ) -> FillResult:
        """
        Simulate the execution of an order with market impact.

        Args:
            order: Order to execute
            quote: Current market quote
            market_condition: Current market volatility condition
            average_volume: Average daily volume for the symbol

        Returns:
            FillResult with execution details
        """
        logger.debug(
            f"Simulating execution for {order.order_type} {order.quantity} {order.symbol}"
        )

        # Determine execution price and slippage
        execution_price, slippage = self._calculate_execution_price(
            order, quote, market_condition, average_volume
        )

        # Determine fill quantity (partial vs full)
        filled_quantity = self._calculate_fill_quantity(
            order, market_condition, average_volume
        )

        # Calculate commission
        commission = self._calculate_commission(filled_quantity)

        # Calculate total cost
        total_cost = abs(filled_quantity * execution_price) + commission

        # Create result
        slippage_percent = (slippage / quote.price) * 100 if quote.price else 0

        result = FillResult(
            filled_quantity=filled_quantity,
            fill_price=execution_price,
            remaining_quantity=abs(order.quantity) - filled_quantity,
            slippage=slippage,
            slippage_percent=slippage_percent,
            commission=commission,
            total_cost=total_cost,
            partial_fill=filled_quantity < abs(order.quantity),
            execution_time=datetime.utcnow(),
        )

        # Store in history
        self.execution_history.append(result)

        logger.info(
            f"Simulated execution: {filled_quantity}/{abs(order.quantity)} filled "
            f"at ${execution_price:.4f} (slippage: {slippage_percent:.2f}%)"
        )

        return result

    def _calculate_execution_price(
        self,
        order: Order,
        quote: Quote,
        market_condition: MarketCondition,
        average_volume: int | None,
    ) -> tuple[float, float]:
        """Calculate execution price with slippage."""

        # Determine base price based on order condition
        if order.condition == OrderCondition.MARKET:
            # Market orders use bid/ask
            if order.order_type in [OrderType.BUY, OrderType.BTO]:
                base_price = quote.ask or quote.price
            else:
                base_price = quote.bid or quote.price
        else:
            # Limit orders use the limit price, but may have slippage for realism
            base_price = order.price or quote.price

        if not base_price:
            base_price = quote.price or 100.0  # Fallback

        # Calculate slippage factors
        slippage_bps = self._calculate_slippage_bps(
            order, quote, market_condition, average_volume
        )

        # Apply slippage
        slippage_factor = slippage_bps / 10000.0  # Convert basis points to decimal

        if order.order_type in [OrderType.BUY, OrderType.BTO]:
            # Buying - slippage increases price
            execution_price = base_price * (1 + slippage_factor)
            slippage = execution_price - base_price
        else:
            # Selling - slippage decreases price
            execution_price = base_price * (1 - slippage_factor)
            slippage = base_price - execution_price

        return execution_price, slippage

    def _calculate_slippage_bps(
        self,
        order: Order,
        quote: Quote,
        market_condition: MarketCondition,
        average_volume: int | None,
    ) -> float:
        """Calculate slippage in basis points."""

        # Start with base slippage
        slippage_bps = self.config.base_slippage_bps

        # Apply volatility multiplier
        volatility_mult = self.config.volatility_multiplier[market_condition]
        slippage_bps *= volatility_mult

        # Volume impact - larger orders relative to average volume have more impact
        if average_volume:
            volume_ratio = abs(order.quantity) / average_volume
            volume_impact = (
                volume_ratio * self.config.volume_impact_factor * 100
            )  # Convert to bps
            slippage_bps += volume_impact

        # Spread impact - wider spreads mean more slippage
        if quote.bid and quote.ask:
            spread = quote.ask - quote.bid
            spread_percent = (spread / quote.price) * 100 if quote.price else 0
            spread_impact = spread_percent * 10  # Convert spread % to additional bps
            slippage_bps += spread_impact

        # Add some randomness
        random_factor = random.uniform(0.8, 1.2)  # ±20% randomness
        slippage_bps *= random_factor

        return max(0.1, slippage_bps)  # Minimum 0.1 bps slippage

    def _calculate_fill_quantity(
        self,
        order: Order,
        market_condition: MarketCondition,
        average_volume: int | None,
    ) -> int:
        """Calculate how much of the order gets filled."""

        order_quantity = abs(order.quantity)

        # Check for partial fill conditions
        should_partial_fill = self._should_partially_fill(
            order, market_condition, average_volume
        )

        if should_partial_fill:
            # Determine partial fill ratio
            min_ratio = self.config.min_fill_ratio
            fill_ratio = random.uniform(min_ratio, 0.95)  # 70-95% fill
            filled_quantity = int(order_quantity * fill_ratio)

            # Ensure at least 1 share is filled
            filled_quantity = max(1, filled_quantity)

            logger.debug(
                f"Partial fill: {filled_quantity}/{order_quantity} ({fill_ratio:.1%})"
            )

            return filled_quantity
        else:
            return order_quantity

    def _should_partially_fill(
        self,
        order: Order,
        market_condition: MarketCondition,
        average_volume: int | None,
    ) -> bool:
        """Determine if order should be partially filled."""

        # Base probability
        partial_prob = self.config.partial_fill_probability

        # Increase probability for large orders
        if average_volume:
            volume_ratio = abs(order.quantity) / average_volume
            if volume_ratio > 0.01:  # Order is >1% of daily volume
                partial_prob += volume_ratio * 0.1

        # Increase probability during volatile markets
        if market_condition in [
            MarketCondition.VOLATILE,
            MarketCondition.HIGHLY_VOLATILE,
        ]:
            partial_prob *= 2.0

        # Market orders are less likely to be partial
        if order.condition == OrderCondition.MARKET:
            partial_prob *= 0.5

        # Limit orders far from market are more likely to be partial
        # (This would require current market price comparison)

        return random.random() < partial_prob

    def _calculate_commission(self, quantity: int) -> float:
        """Calculate commission for the trade."""
        commission = quantity * self.config.commission_per_share
        return min(commission, self.config.max_commission)

    def get_market_condition(self, quote: Quote) -> MarketCondition:
        """
        Determine market condition based on quote characteristics.

        This is a simple heuristic - in production, you might use:
        - Historical volatility
        - VIX levels
        - Recent price movements
        - Volume patterns
        """

        if not quote.bid or not quote.ask or not quote.price:
            return MarketCondition.NORMAL

        # Use bid-ask spread as volatility proxy
        spread = quote.ask - quote.bid
        spread_percent = (spread / quote.price) * 100

        if spread_percent < 0.05:  # Very tight spread
            return MarketCondition.CALM
        elif spread_percent < 0.2:  # Normal spread
            return MarketCondition.NORMAL
        elif spread_percent < 0.5:  # Wide spread
            return MarketCondition.VOLATILE
        else:  # Very wide spread
            return MarketCondition.HIGHLY_VOLATILE

    def get_execution_statistics(self) -> dict:
        """Get statistics from recent executions."""
        if not self.execution_history:
            return {}

        recent_executions = self.execution_history[-100:]  # Last 100 executions

        total_slippage = sum(result.slippage for result in recent_executions)
        total_fills = len(recent_executions)
        partial_fills = sum(1 for result in recent_executions if result.partial_fill)

        avg_slippage = total_slippage / total_fills if total_fills else 0
        avg_slippage_pct = (
            sum(result.slippage_percent for result in recent_executions) / total_fills
            if total_fills
            else 0
        )

        return {
            "total_executions": total_fills,
            "partial_fill_rate": partial_fills / total_fills if total_fills else 0,
            "average_slippage": avg_slippage,
            "average_slippage_percent": avg_slippage_pct,
            "total_commission": sum(result.commission for result in recent_executions),
        }

    def simulate_market_hours_impact(self, current_time: datetime) -> MarketCondition:
        """
        Simulate different market conditions based on time of day.

        Returns more volatile conditions during:
        - Market open (9:30-10:30 AM ET)
        - Market close (3:30-4:00 PM ET)
        - Lunch time (12:00-1:00 PM ET) - less volume, more volatile
        """

        hour = current_time.hour

        # Market open volatility
        if 9 <= hour <= 10 or 12 <= hour <= 13 or 15 <= hour <= 16:
            return MarketCondition.VOLATILE

        # Normal trading hours
        else:
            return MarketCondition.NORMAL

    def simulate_market_impact(
        self, order: Order, current_price: float, average_volume: int
    ) -> FillResult:
        """
        Simulate market impact with simple parameters (compatibility method for tests).

        Args:
            order: Order to execute
            current_price: Current market price
            average_volume: Average daily trading volume

        Returns:
            FillResult with execution details
        """
        # Create a simple Quote object from the current price
        from ..models.assets import asset_factory

        asset = asset_factory(order.symbol)
        if not asset:
            raise ValueError(f"Could not create asset for symbol: {order.symbol}")

        quote = Quote(
            asset=asset,
            quote_date=datetime.utcnow(),
            price=current_price,
            bid=current_price * 0.999,  # Slightly below market
            ask=current_price * 1.001,  # Slightly above market
            volume=0,  # Not used in simulation
        )

        # Call the main simulation method
        return self.simulate_execution(
            order=order,
            quote=quote,
            market_condition=MarketCondition.NORMAL,
            average_volume=average_volume,
        )

    def reset_statistics(self) -> None:
        """Reset execution history and statistics."""
        self.execution_history.clear()
        logger.info("Reset market impact statistics")


# Global simulator instance
market_impact_simulator = MarketImpactSimulator()


def get_market_impact_simulator() -> MarketImpactSimulator:
    """Get the global market impact simulator instance."""
    return market_impact_simulator


def configure_market_impact(config: MarketImpactConfig) -> None:
    """Configure the global market impact simulator."""
    global market_impact_simulator
    market_impact_simulator = MarketImpactSimulator(config)
