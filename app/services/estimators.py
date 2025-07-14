"""
Price estimation tools for determining likely transaction prices.

Adapted from paperbroker with Pydantic integration.
"""

from abc import ABC, abstractmethod
from math import copysign
from typing import Optional

from ..models.quotes import Quote


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
        if (quote.bid is not None and quote.ask is not None and 
            quote.bid > 0.0 and quote.ask > 0.0):
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
        
        if (quote.bid is None or quote.ask is None or 
            quote.bid <= 0.0 or quote.ask <= 0.0):
            raise ValueError(
                "SlippageEstimator requires valid bid and ask prices"
            )
        
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
        
        if (quote.bid is None or quote.ask is None or 
            quote.bid <= 0.0 or quote.ask <= 0.0):
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
        
        if (quote.bid is None or quote.ask is None or 
            quote.bid <= 0.0 or quote.ask <= 0.0):
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
def create_estimator(estimator_type: str, **kwargs) -> PriceEstimator:
    """
    Create an estimator by type name.
    
    Args:
        estimator_type: Type of estimator ('midpoint', 'slippage', 'fixed', 'market', 'volume')
        **kwargs: Arguments specific to the estimator type
        
    Returns:
        Configured estimator instance
    """
    estimator_type = estimator_type.lower()
    
    if estimator_type == 'midpoint':
        return MidpointEstimator()
    elif estimator_type == 'slippage':
        return SlippageEstimator(kwargs.get('slippage', 0.0))
    elif estimator_type == 'fixed':
        return FixedPriceEstimator(kwargs.get('price', 0.0))
    elif estimator_type == 'market':
        return MarketEstimator()
    elif estimator_type == 'volume':
        return VolumeWeightedEstimator(kwargs.get('size_impact_factor', 0.1))
    else:
        raise ValueError(f"Unknown estimator type: {estimator_type}")