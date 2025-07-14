"""
Quote classes for market data and options pricing.

Adapted from paperbroker with Pydantic models and FastAPI integration.
"""

from datetime import datetime, date
from typing import Optional, Union, List
from pydantic import BaseModel, Field, validator
from .assets import Asset, Option, asset_factory


def quote_factory(
    quote_date: Union[datetime, date, str], 
    asset: Union[str, Asset], 
    price: Optional[float] = None,
    bid: float = 0.0, 
    ask: float = 0.0, 
    bid_size: int = 0,
    ask_size: int = 0, 
    underlying_price: Optional[float] = None
) -> Union["Quote", "OptionQuote"]:
    """
    Create the appropriate quote type based on the asset.
    
    Args:
        quote_date: Date/time of the quote
        asset: Asset symbol or Asset object
        price: Last trade price
        bid: Bid price
        ask: Ask price
        bid_size: Bid size
        ask_size: Ask size
        underlying_price: Price of underlying (for options)
        
    Returns:
        Quote or OptionQuote object
    """
    asset_obj = asset_factory(asset)
    
    if isinstance(asset_obj, Option):
        return OptionQuote(
            quote_date=quote_date,
            asset=asset_obj,
            price=price,
            bid=bid,
            ask=ask,
            bid_size=bid_size,
            ask_size=ask_size,
            underlying_price=underlying_price
        )
    else:
        return Quote(
            quote_date=quote_date,
            asset=asset_obj,
            price=price,
            bid=bid,
            ask=ask,
            bid_size=bid_size,
            ask_size=ask_size
        )


class Quote(BaseModel):
    """Base quote class for all assets."""
    
    asset: Asset = Field(..., description="Asset being quoted")
    quote_date: datetime = Field(..., description="Quote timestamp")
    price: Optional[float] = Field(None, description="Last trade price")
    bid: float = Field(0.0, ge=0, description="Bid price")
    ask: float = Field(0.0, ge=0, description="Ask price")
    bid_size: int = Field(0, ge=0, description="Bid size")
    ask_size: int = Field(0, ge=0, description="Ask size")
    volume: Optional[int] = Field(None, ge=0, description="Trading volume")
    
    @validator('asset', pre=True)
    def normalize_asset(cls, v):
        return asset_factory(v) if isinstance(v, str) else v
    
    @validator('quote_date', pre=True)
    def normalize_date(cls, v):
        if isinstance(v, str):
            return datetime.fromisoformat(v.replace('Z', '+00:00'))
        elif isinstance(v, date) and not isinstance(v, datetime):
            return datetime.combine(v, datetime.min.time())
        return v
    
    @validator('price')
    def calculate_midpoint(cls, v, values):
        """Calculate midpoint if price not provided."""
        if v is None:
            bid = values.get('bid', 0.0)
            ask = values.get('ask', 0.0)
            if bid > 0 and ask > 0:
                return (bid + ask) / 2
        return v
    
    @property
    def symbol(self) -> str:
        """Asset symbol."""
        return self.asset.symbol
    
    @property
    def spread(self) -> float:
        """Bid-ask spread."""
        return self.ask - self.bid
    
    @property
    def midpoint(self) -> float:
        """Bid-ask midpoint."""
        return (self.bid + self.ask) / 2
    
    def is_priceable(self) -> bool:
        """Check if quote has valid pricing data."""
        return self.price is not None and self.price > 0


class OptionQuote(Quote):
    """Quote for options with Greeks."""
    
    underlying_price: Optional[float] = Field(None, description="Underlying asset price")
    
    # Greeks (will be calculated if underlying_price is available)
    delta: Optional[float] = Field(None, description="Delta (price sensitivity)")
    gamma: Optional[float] = Field(None, description="Gamma (delta sensitivity)")
    theta: Optional[float] = Field(None, description="Theta (time decay)")
    vega: Optional[float] = Field(None, description="Vega (volatility sensitivity)")
    rho: Optional[float] = Field(None, description="Rho (interest rate sensitivity)")
    iv: Optional[float] = Field(None, description="Implied volatility")
    
    # Additional Greeks
    vanna: Optional[float] = Field(None, description="Vanna (delta sensitivity to volatility)")
    charm: Optional[float] = Field(None, description="Charm (delta decay)")
    speed: Optional[float] = Field(None, description="Speed (gamma sensitivity)")
    zomma: Optional[float] = Field(None, description="Zomma (gamma sensitivity to volatility)")
    color: Optional[float] = Field(None, description="Color (gamma decay)")
    veta: Optional[float] = Field(None, description="Veta (vega decay)")
    vomma: Optional[float] = Field(None, description="Vomma (vega sensitivity to volatility)")
    ultima: Optional[float] = Field(None, description="Ultima (vomma sensitivity)")
    dual_delta: Optional[float] = Field(None, description="Dual delta")
    
    @validator('asset')
    def validate_option_asset(cls, v):
        if not isinstance(v, Option):
            raise ValueError("OptionQuote requires an Option asset")
        return v
    
    def __init__(self, **data):
        super().__init__(**data)
        
        # Calculate Greeks if we have sufficient data
        if (self.is_priceable() and 
            self.underlying_price is not None and 
            self.underlying_price > 0 and
            self.delta is None):  # Only calculate if not already provided
            
            self._calculate_greeks()
    
    def _calculate_greeks(self):
        """Calculate Greeks using Black-Scholes."""
        try:
            from ..services.greeks import update_option_quote_with_greeks
            update_option_quote_with_greeks(self)
        except ImportError:
            # Graceful fallback if service not available
            pass
    
    @property
    def days_to_expiration(self) -> Optional[int]:
        """Days until expiration."""
        if isinstance(self.asset, Option):
            return self.asset.get_days_to_expiration(self.quote_date.date())
        return None
    
    @property
    def strike(self) -> Optional[float]:
        """Strike price."""
        return self.asset.strike if isinstance(self.asset, Option) else None
    
    @property
    def expiration_date(self) -> Optional[date]:
        """Expiration date."""
        return self.asset.expiration_date if isinstance(self.asset, Option) else None
    
    @property
    def option_type(self) -> Optional[str]:
        """Option type (call/put)."""
        return self.asset.option_type if isinstance(self.asset, Option) else None
    
    def has_greeks(self) -> bool:
        """Check if Greeks are available."""
        return self.iv is not None
    
    def get_intrinsic_value(self, underlying_price: Optional[float] = None) -> float:
        """Calculate intrinsic value."""
        price = underlying_price or self.underlying_price
        if price is None or not isinstance(self.asset, Option):
            return 0.0
        return self.asset.get_intrinsic_value(price)
    
    def get_extrinsic_value(self, underlying_price: Optional[float] = None) -> float:
        """Calculate extrinsic (time) value."""
        price = underlying_price or self.underlying_price
        if price is None or not isinstance(self.asset, Option) or not self.is_priceable():
            return 0.0
        return self.asset.get_extrinsic_value(price, self.price)


class QuoteResponse(BaseModel):
    """API response wrapper for quotes."""
    
    quote: Union[Quote, OptionQuote] = Field(..., description="Quote data")
    data_source: str = Field(..., description="Data source identifier")
    cached: bool = Field(False, description="Whether data was served from cache")
    cache_age_seconds: Optional[int] = Field(None, description="Age of cached data in seconds")


class OptionsChain(BaseModel):
    """Options chain for a given underlying and expiration."""
    
    underlying_symbol: str = Field(..., description="Underlying asset symbol")
    expiration_date: date = Field(..., description="Options expiration date")
    underlying_price: Optional[float] = Field(None, description="Current underlying price")
    calls: List[OptionQuote] = Field(default_factory=list, description="Call options")
    puts: List[OptionQuote] = Field(default_factory=list, description="Put options")
    quote_time: datetime = Field(default_factory=datetime.now, description="Quote timestamp")
    
    @property
    def all_options(self) -> List[OptionQuote]:
        """All options (calls + puts)."""
        return self.calls + self.puts
    
    def get_strikes(self) -> List[float]:
        """Get all available strike prices."""
        strikes = set()
        for option in self.all_options:
            if option.strike:
                strikes.add(option.strike)
        return sorted(list(strikes))
    
    def get_calls_by_strike(self, strike: float) -> List[OptionQuote]:
        """Get call options for a specific strike."""
        return [opt for opt in self.calls if opt.strike == strike]
    
    def get_puts_by_strike(self, strike: float) -> List[OptionQuote]:
        """Get put options for a specific strike."""
        return [opt for opt in self.puts if opt.strike == strike]