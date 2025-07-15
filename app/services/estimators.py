"""
Price estimation tools for determining likely transaction prices.

Adapted from reference implementation with enhanced features for realistic fill simulation.
Includes slippage modeling, volume impact, and options-specific estimation.
"""

import random
from abc import ABC, abstractmethod
from math import copysign, sqrt
from typing import Optional, Dict, Union, Any, Tuple
from datetime import datetime

from ..models.quotes import Quote, OptionQuote
from ..models.assets import Option, asset_factory


class PriceEstimator(ABC):
    """Base class for price estimators."""

    @abstractmethod
    def estimate(self, quote: Quote, quantity: Optional[int] = None) -> float:
        """
        Estimate the price an asset would transact at.

        Args:
            quote: Quote object with pricing data
            quantity: Signed quantity (positive=buy, negative=sell)

        Returns:
            Estimated transaction price
        """
        pass


class MidpointEstimator(PriceEstimator):
    """
    Default estimator that uses the midpoint between bid and ask.
    Falls back to last price if bid/ask not available.
    """

    def estimate(self, quote: Quote, quantity: Optional[int] = None) -> float:
        """Estimate price as bid-ask midpoint or last price."""

        # If we have valid bid and ask, use midpoint
        if (
            quote.bid is not None
            and quote.ask is not None
            and quote.bid > 0.0
            and quote.ask > 0.0
        ):
            return round((quote.bid + quote.ask) / 2, 2)

        # Fall back to last price
        if quote.price is not None and quote.price > 0.0:
            return round(quote.price, 2)

        raise ValueError(
            "Cannot estimate price: bid/ask are invalid and no last price available"
        )


class SlippageEstimator(PriceEstimator):
    """
    Price estimator that accounts for slippage within the bid-ask spread.

    Slippage parameter:
    - 1.0: Most favorable price (buy@bid, sell@ask)
    - 0.0: Midpoint price
    - -1.0: Least favorable price (buy@ask, sell@bid)
    """

    def __init__(self, slippage: float = 0.0):
        """
        Initialize with slippage factor.

        Args:
            slippage: Float between -1.0 and 1.0
                     Positive is better execution, negative is worse
        """
        if not -1.0 <= slippage <= 1.0:
            raise ValueError("Slippage must be between -1.0 and 1.0")
        self.slippage = slippage

    def estimate(self, quote: Quote, quantity: Optional[int] = None) -> float:
        """Estimate price accounting for slippage within spread."""

        if (
            quote.bid is None
            or quote.ask is None
            or quote.bid <= 0.0
            or quote.ask <= 0.0
        ):
            raise ValueError("SlippageEstimator requires valid bid and ask prices")

        if quantity is None or quantity == 0:
            raise ValueError(
                "SlippageEstimator requires a signed quantity for direction"
            )

        # Calculate spread and midpoint
        spread = (quote.ask - quote.bid) / 2
        midpoint = quote.bid + spread

        # Apply slippage based on direction
        direction = copysign(1, quantity)

        if direction > 0:  # Buying
            # Positive slippage means better execution (closer to bid)
            # Negative slippage means worse execution (closer to ask)
            return round(midpoint - spread * self.slippage, 2)
        else:  # Selling
            # Positive slippage means better execution (closer to ask)
            # Negative slippage means worse execution (closer to bid)
            return round(midpoint + spread * self.slippage, 2)


class FixedPriceEstimator(PriceEstimator):
    """
    Estimator that always returns a fixed price.
    Useful for testing, forced fills, or option expiration scenarios.
    """

    def __init__(self, price: float = 0.0):
        """
        Initialize with fixed price.

        Args:
            price: Fixed price to return for all estimates
        """
        self.price = price

    def estimate(self, quote: Quote, quantity: Optional[int] = None) -> float:
        """Return the fixed price regardless of quote or quantity."""
        return self.price


class MarketEstimator(PriceEstimator):
    """
    Estimator that simulates market order execution.
    Uses ask price for buys, bid price for sells.
    """

    def estimate(self, quote: Quote, quantity: Optional[int] = None) -> float:
        """Estimate market order execution price."""

        if (
            quote.bid is None
            or quote.ask is None
            or quote.bid <= 0.0
            or quote.ask <= 0.0
        ):
            # Fall back to midpoint if bid/ask not available
            return MidpointEstimator().estimate(quote, quantity)

        if quantity is None or quantity == 0:
            # No direction specified, use midpoint
            return round((quote.bid + quote.ask) / 2, 2)

        # Market orders: buy at ask, sell at bid
        if quantity > 0:  # Buying
            return round(quote.ask, 2)
        else:  # Selling
            return round(quote.bid, 2)


class VolumeWeightedEstimator(PriceEstimator):
    """
    Estimator that considers bid/ask sizes for more realistic execution.
    Larger orders may get worse execution due to limited liquidity.
    """

    def __init__(self, size_impact_factor: float = 0.1):
        """
        Initialize with size impact factor.

        Args:
            size_impact_factor: How much large orders impact execution (0.0 - 1.0)
        """
        self.size_impact_factor = max(0.0, min(1.0, size_impact_factor))

    def estimate(self, quote: Quote, quantity: Optional[int] = None) -> float:
        """Estimate price considering order size vs available liquidity."""

        if (
            quote.bid is None
            or quote.ask is None
            or quote.bid <= 0.0
            or quote.ask <= 0.0
        ):
            return MidpointEstimator().estimate(quote, quantity)

        if quantity is None or quantity == 0:
            return round((quote.bid + quote.ask) / 2, 2)

        # Calculate base execution price
        direction = copysign(1, quantity)
        base_price = quote.ask if direction > 0 else quote.bid
        available_size = quote.ask_size if direction > 0 else quote.bid_size

        # If no size information, fall back to market estimator
        if available_size <= 0:
            return MarketEstimator().estimate(quote, quantity)

        # Calculate size impact
        order_size = abs(quantity)
        size_ratio = min(order_size / available_size, 1.0)

        # Apply impact: larger orders get worse execution
        spread = quote.ask - quote.bid
        impact = spread * size_ratio * self.size_impact_factor

        if direction > 0:  # Buying - price gets worse (higher)
            return round(base_price + impact, 2)
        else:  # Selling - price gets worse (lower)
            return round(base_price - impact, 2)


# Convenience function for getting default estimator
def get_default_estimator() -> PriceEstimator:
    """Get the default price estimator (midpoint)."""
    return MidpointEstimator()


# Factory function for creating estimators by name
def create_estimator(estimator_type: str, **kwargs: Any) -> PriceEstimator:
    """
    Create an estimator by type name.

    Args:
        estimator_type: Type of estimator ('midpoint', 'slippage', 'fixed', 'market', 'volume')
        **kwargs: Arguments specific to the estimator type

    Returns:
        Configured estimator instance
    """
    estimator_type = estimator_type.lower()

    if estimator_type == "midpoint":
        return MidpointEstimator()
    elif estimator_type == "slippage":
        return SlippageEstimator(kwargs.get("slippage", 0.0))
    elif estimator_type == "fixed":
        return FixedPriceEstimator(kwargs.get("price", 0.0))
    elif estimator_type == "market":
        return MarketEstimator()
    elif estimator_type == "volume":
        return VolumeWeightedEstimator(kwargs.get("size_impact_factor", 0.1))
    elif estimator_type == "realistic":
        return RealisticEstimator(
            kwargs.get("base_slippage", 0.1),
            kwargs.get("size_impact", 0.05),
            kwargs.get("volatility_impact", 0.02),
        )
    elif estimator_type == "options":
        return OptionsEstimator(kwargs.get("spread_factor", 0.3))
    elif estimator_type == "random":
        return RandomWalkEstimator(
            kwargs.get("volatility", 0.01), kwargs.get("seed", None)
        )
    else:
        raise ValueError(f"Unknown estimator type: {estimator_type}")


class RealisticEstimator(PriceEstimator):
    """
    Advanced estimator that models realistic market conditions.

    Combines multiple factors:
    - Base slippage (market microstructure)
    - Size impact (liquidity constraints)
    - Volatility impact (bid-ask spreads widen with volatility)
    - Time-of-day effects
    """

    def __init__(
        self,
        base_slippage: float = 0.1,
        size_impact: float = 0.05,
        volatility_impact: float = 0.02,
    ):
        """
        Initialize realistic estimator.

        Args:
            base_slippage: Base slippage factor (0.0 - 1.0)
            size_impact: Impact factor for order size (0.0 - 1.0)
            volatility_impact: Impact factor for volatility (0.0 - 1.0)
        """
        self.base_slippage = max(0.0, min(1.0, base_slippage))
        self.size_impact = max(0.0, min(1.0, size_impact))
        self.volatility_impact = max(0.0, min(1.0, volatility_impact))

    def estimate(
        self, quote: Union[Quote, OptionQuote], quantity: Optional[int] = None
    ) -> float:
        """Estimate price using realistic market modeling."""

        if (
            quote.bid is None
            or quote.ask is None
            or quote.bid <= 0.0
            or quote.ask <= 0.0
        ):
            return MidpointEstimator().estimate(quote, quantity)

        if quantity is None or quantity == 0:
            return round((quote.bid + quote.ask) / 2, 2)

        # Base calculation
        direction = copysign(1, quantity)
        spread = quote.ask - quote.bid
        midpoint = quote.bid + spread / 2

        # Base slippage (market microstructure)
        base_impact = spread * self.base_slippage * 0.5

        # Size impact
        order_size = abs(quantity)
        typical_size = 100  # Assume 100 shares is typical
        if hasattr(quote, "ask_size") and quote.ask_size > 0:
            available_size = quote.ask_size if direction > 0 else quote.bid_size
            size_ratio = min(order_size / max(available_size, typical_size), 2.0)
        else:
            size_ratio = order_size / typical_size

        size_impact = spread * self.size_impact * sqrt(size_ratio)

        # Volatility impact (wider spreads in volatile conditions)
        volatility_factor = 1.0
        if hasattr(quote, "iv") and quote.iv is not None:
            # Use implied volatility for options
            volatility_factor = 1.0 + quote.iv * self.volatility_impact
        elif spread / midpoint > 0.05:  # Wide spread indicates volatility
            volatility_factor = 1.2

        # Time of day impact (wider spreads at open/close)
        time_factor = self._get_time_factor()

        # Combine all impacts
        total_impact = (base_impact + size_impact) * volatility_factor * time_factor

        # Apply based on direction
        if direction > 0:  # Buying - price gets worse (higher)
            return round(midpoint + total_impact, 2)
        else:  # Selling - price gets worse (lower)
            return round(midpoint - total_impact, 2)

    def _get_time_factor(self) -> float:
        """Get time-of-day impact factor."""
        now = datetime.now()
        hour = now.hour
        minute = now.minute

        # Market opens at 9:30 AM, closes at 4:00 PM
        if hour < 9 or (hour == 9 and minute < 30) or hour >= 16:
            return 1.0  # After hours - no additional impact

        # First 30 minutes (9:30-10:00) and last 30 minutes (3:30-4:00)
        if (hour == 9 and minute >= 30) or hour == 15 and minute >= 30:
            return 1.3  # Higher volatility at open/close

        # Normal trading hours
        return 1.0


class OptionsEstimator(PriceEstimator):
    """
    Specialized estimator for options with wider bid-ask spreads.

    Options typically have wider spreads and different liquidity characteristics
    than stocks. This estimator accounts for these differences.
    """

    def __init__(self, spread_factor: float = 0.3):
        """
        Initialize options estimator.

        Args:
            spread_factor: Factor for options spread execution (0.0 - 1.0)
                          0.0 = always get worst price, 1.0 = always get best price
        """
        self.spread_factor = max(0.0, min(1.0, spread_factor))

    def estimate(
        self, quote: Union[Quote, OptionQuote], quantity: Optional[int] = None
    ) -> float:
        """Estimate option execution price."""

        if (
            quote.bid is None
            or quote.ask is None
            or quote.bid <= 0.0
            or quote.ask <= 0.0
        ):
            if quote.price is not None and quote.price > 0.0:
                return round(quote.price, 2)
            raise ValueError("OptionsEstimator requires valid bid/ask or last price")

        if quantity is None or quantity == 0:
            # For options, bias slightly toward the spread to account for illiquidity
            return round(quote.bid + (quote.ask - quote.bid) * 0.6, 2)

        direction = copysign(1, quantity)
        spread = quote.ask - quote.bid

        # For options, we rarely get the best price due to wide spreads
        # Use spread_factor to determine how much of the spread we capture
        if direction > 0:  # Buying
            # 0 = pay ask, 1 = pay bid (impossible), spread_factor = somewhere in between
            price = quote.ask - spread * self.spread_factor
        else:  # Selling
            # 0 = receive bid, 1 = receive ask (impossible), spread_factor = somewhere in between
            price = quote.bid + spread * self.spread_factor

        # Options are priced in increments (usually $0.05 or $0.10)
        # Round to nearest nickel for options under $3, dime for options over $3
        if price < 3.0:
            price = round(price * 20) / 20  # Round to nearest $0.05
        else:
            price = round(price * 10) / 10  # Round to nearest $0.10

        return price


class RandomWalkEstimator(PriceEstimator):
    """
    Estimator that adds random walk behavior to simulate market randomness.

    Useful for testing and Monte Carlo simulations.
    """

    def __init__(self, volatility: float = 0.01, seed: Optional[int] = None):
        """
        Initialize random walk estimator.

        Args:
            volatility: Daily volatility factor (standard deviation)
            seed: Random seed for reproducible results
        """
        self.volatility = volatility
        if seed is not None:
            random.seed(seed)

    def estimate(
        self, quote: Union[Quote, OptionQuote], quantity: Optional[int] = None
    ) -> float:
        """Estimate price with random walk component."""

        # Get base price from midpoint estimator
        try:
            base_price = MidpointEstimator().estimate(quote, quantity)
        except ValueError:
            if quote.price is not None and quote.price > 0:
                base_price = quote.price
            else:
                raise ValueError("Cannot determine base price for random walk")

        # Add random component
        # Assume trading day is 6.5 hours, so intraday volatility is reduced
        intraday_vol = self.volatility / sqrt(252 * 6.5)  # Scale down from daily
        random_factor = random.gauss(0, intraday_vol)

        # Apply random walk
        adjusted_price = base_price * (1 + random_factor)

        # Ensure price stays positive and reasonable
        adjusted_price = max(adjusted_price, base_price * 0.8)  # No more than 20% down
        adjusted_price = min(adjusted_price, base_price * 1.2)  # No more than 20% up

        return round(adjusted_price, 2)


class MultiEstimator(PriceEstimator):
    """
    Composite estimator that combines multiple estimation methods.

    Useful for sophisticated modeling that considers multiple factors.
    """

    def __init__(self, estimators: Dict[str, Tuple[PriceEstimator, float]]) -> None:
        """
        Initialize multi-estimator.

        Args:
            estimators: Dictionary of {name: (estimator, weight)} pairs
                       Weights should sum to 1.0
        """
        self.estimators = estimators
        total_weight = sum(weight for _, weight in estimators.values())
        if abs(total_weight - 1.0) > 0.01:
            raise ValueError("Estimator weights should sum to 1.0")

    def estimate(
        self, quote: Union[Quote, OptionQuote], quantity: Optional[int] = None
    ) -> float:
        """Estimate price using weighted combination of estimators."""

        weighted_price = 0.0
        total_weight = 0.0

        for name, (estimator, weight) in self.estimators.items():
            try:
                price = estimator.estimate(quote, quantity)
                weighted_price += price * weight
                total_weight += weight
            except Exception as e:
                # Skip estimators that fail
                print(f"Estimator {name} failed: {e}")
                continue

        if total_weight == 0:
            raise ValueError("All estimators failed")

        return round(weighted_price / total_weight, 2)


# Advanced factory function with presets
def create_advanced_estimator(preset: str, **overrides: Any) -> PriceEstimator:
    """
    Create estimator using presets for common scenarios.

    Args:
        preset: Preset name ('conservative', 'aggressive', 'realistic', 'options', 'test')
        **overrides: Parameter overrides for the preset

    Returns:
        Configured estimator
    """
    presets = {
        "conservative": {
            "type": "realistic",
            "base_slippage": 0.2,
            "size_impact": 0.1,
            "volatility_impact": 0.05,
        },
        "aggressive": {
            "type": "realistic",
            "base_slippage": 0.05,
            "size_impact": 0.02,
            "volatility_impact": 0.01,
        },
        "realistic": {
            "type": "realistic",
            "base_slippage": 0.1,
            "size_impact": 0.05,
            "volatility_impact": 0.02,
        },
        "options": {"type": "options", "spread_factor": 0.3},
        "test": {"type": "random", "volatility": 0.005, "seed": 42},
    }

    if preset not in presets:
        raise ValueError(f"Unknown preset: {preset}")

    config = presets[preset].copy()
    config.update(overrides)

    estimator_type = config.pop("type")
    return create_estimator(str(estimator_type), **config)


def get_estimator_for_asset(symbol: str, **kwargs: Any) -> PriceEstimator:
    """
    Get appropriate estimator for an asset type.

    Args:
        symbol: Asset symbol
        **kwargs: Additional parameters for estimator

    Returns:
        Appropriate estimator for the asset
    """
    asset = asset_factory(symbol)

    if isinstance(asset, Option):
        return create_advanced_estimator("options", **kwargs)
    else:
        return create_advanced_estimator("realistic", **kwargs)
