"""
Quote classes for market data and options pricing.

Quote models with Pydantic validation and FastAPI integration.
"""

from datetime import datetime, date
from typing import Optional, Union, List, Dict, Any
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
    underlying_price: Optional[float] = None,
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

    if asset_obj is None:
        raise ValueError("Could not create asset from provided symbol")

    # Normalize quote_date to datetime
    if isinstance(quote_date, str):
        quote_date = datetime.fromisoformat(quote_date.replace("Z", "+00:00"))
    elif isinstance(quote_date, date) and not isinstance(quote_date, datetime):
        quote_date = datetime.combine(quote_date, datetime.min.time())

    if isinstance(asset_obj, Option):
        return OptionQuote(
            quote_date=quote_date,
            asset=asset_obj,
            price=price,
            bid=bid,
            ask=ask,
            bid_size=bid_size,
            ask_size=ask_size,
            volume=None,
            underlying_price=underlying_price,
        )
    else:
        return Quote(
            quote_date=quote_date,
            asset=asset_obj,
            price=price,
            bid=bid,
            ask=ask,
            bid_size=bid_size,
            ask_size=ask_size,
            volume=None,
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

    @validator("asset", pre=True)
    def normalize_asset(cls, v: Union[str, Asset]) -> Asset:
        if isinstance(v, str):
            asset = asset_factory(v)
            if asset is None:
                raise ValueError(f"Could not create asset for symbol: {v}")
            return asset
        return v

    @validator("quote_date", pre=True)
    def normalize_date(cls, v: Union[str, date, datetime]) -> datetime:
        if isinstance(v, str):
            return datetime.fromisoformat(v.replace("Z", "+00:00"))
        elif isinstance(v, date) and not isinstance(v, datetime):
            return datetime.combine(v, datetime.min.time())
        return v if isinstance(v, datetime) else datetime.now()

    @validator("price")
    def calculate_midpoint(
        cls, v: Optional[float], values: Dict[str, Any]
    ) -> Optional[float]:
        """Calculate midpoint if price not provided."""
        if v is None:
            bid = values.get("bid", 0.0)
            ask = values.get("ask", 0.0)
            if bid > 0 and ask > 0:
                return float((bid + ask) / 2)
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

    underlying_price: Optional[float] = Field(
        None, description="Underlying asset price"
    )

    # Greeks (will be calculated if underlying_price is available)
    delta: Optional[float] = Field(None, description="Delta (price sensitivity)")
    gamma: Optional[float] = Field(None, description="Gamma (delta sensitivity)")
    theta: Optional[float] = Field(None, description="Theta (time decay)")
    vega: Optional[float] = Field(None, description="Vega (volatility sensitivity)")
    rho: Optional[float] = Field(None, description="Rho (interest rate sensitivity)")
    iv: Optional[float] = Field(None, description="Implied volatility")

    # Additional Greeks
    vanna: Optional[float] = Field(
        None, description="Vanna (delta sensitivity to volatility)"
    )
    charm: Optional[float] = Field(None, description="Charm (delta decay)")
    speed: Optional[float] = Field(None, description="Speed (gamma sensitivity)")
    zomma: Optional[float] = Field(
        None, description="Zomma (gamma sensitivity to volatility)"
    )
    color: Optional[float] = Field(None, description="Color (gamma decay)")
    veta: Optional[float] = Field(None, description="Veta (vega decay)")
    vomma: Optional[float] = Field(
        None, description="Vomma (vega sensitivity to volatility)"
    )
    ultima: Optional[float] = Field(None, description="Ultima (vomma sensitivity)")
    dual_delta: Optional[float] = Field(None, description="Dual delta")

    # Market data
    open_interest: Optional[int] = Field(None, description="Open interest")

    @validator("asset")
    def validate_option_asset(cls, v: Asset) -> Asset:
        if not isinstance(v, Option):
            raise ValueError("OptionQuote requires an Option asset")
        return v

    def __init__(self, **data: Any) -> None:
        super().__init__(**data)

        # Calculate Greeks if we have sufficient data
        if (
            self.is_priceable()
            and self.underlying_price is not None
            and self.underlying_price > 0
            and self.delta is None
        ):  # Only calculate if not already provided
            self._calculate_greeks()

    def _calculate_greeks(self) -> None:
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
        if (
            price is None
            or not isinstance(self.asset, Option)
            or not self.is_priceable()
        ):
            return 0.0
        if self.price is None:
            return 0.0
        return self.asset.get_extrinsic_value(price, self.price)


class QuoteResponse(BaseModel):
    """API response wrapper for quotes."""

    quote: Union[Quote, OptionQuote] = Field(..., description="Quote data")
    data_source: str = Field(..., description="Data source identifier")
    cached: bool = Field(False, description="Whether data was served from cache")
    cache_age_seconds: Optional[int] = Field(
        None, description="Age of cached data in seconds"
    )


class OptionsChain(BaseModel):
    """Options chain for a given underlying and expiration."""

    underlying_symbol: str = Field(..., description="Underlying asset symbol")
    expiration_date: date = Field(..., description="Options expiration date")
    underlying_price: Optional[float] = Field(
        None, description="Current underlying price"
    )
    calls: List[OptionQuote] = Field(default_factory=list, description="Call options")
    puts: List[OptionQuote] = Field(default_factory=list, description="Put options")
    quote_time: datetime = Field(
        default_factory=datetime.now, description="Quote timestamp"
    )

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

    def filter_by_strike_range(
        self, min_strike: Optional[float] = None, max_strike: Optional[float] = None
    ) -> "OptionsChain":
        """
        Filter options by strike price range.

        Args:
            min_strike: Minimum strike price (inclusive)
            max_strike: Maximum strike price (inclusive)

        Returns:
            New OptionsChain with filtered options
        """
        filtered_calls = self.calls.copy()
        filtered_puts = self.puts.copy()

        if min_strike is not None:
            filtered_calls = [
                opt
                for opt in filtered_calls
                if opt.strike is not None and opt.strike >= min_strike
            ]
            filtered_puts = [
                opt
                for opt in filtered_puts
                if opt.strike is not None and opt.strike >= min_strike
            ]

        if max_strike is not None:
            filtered_calls = [
                opt
                for opt in filtered_calls
                if opt.strike is not None and opt.strike <= max_strike
            ]
            filtered_puts = [
                opt
                for opt in filtered_puts
                if opt.strike is not None and opt.strike <= max_strike
            ]

        return OptionsChain(
            underlying_symbol=self.underlying_symbol,
            expiration_date=self.expiration_date,
            underlying_price=self.underlying_price,
            calls=filtered_calls,
            puts=filtered_puts,
            quote_time=self.quote_time,
        )

    def filter_by_moneyness(self, moneyness_range: float = 0.2) -> "OptionsChain":
        """
        Filter options by moneyness (how close strikes are to underlying price).

        Args:
            moneyness_range: Range around ATM as a percentage (0.2 = 20%)

        Returns:
            New OptionsChain with filtered options around the money
        """
        if self.underlying_price is None:
            return self

        min_strike = self.underlying_price * (1 - moneyness_range)
        max_strike = self.underlying_price * (1 + moneyness_range)

        return self.filter_by_strike_range(min_strike, max_strike)

    def get_atm_options(self, tolerance: float = 0.05) -> Dict[str, List[OptionQuote]]:
        """
        Get at-the-money options.

        Args:
            tolerance: Tolerance for ATM as percentage of underlying price

        Returns:
            Dictionary with 'calls' and 'puts' lists of ATM options
        """
        if self.underlying_price is None:
            return {"calls": [], "puts": []}

        tolerance_amount = self.underlying_price * tolerance
        min_strike = self.underlying_price - tolerance_amount
        max_strike = self.underlying_price + tolerance_amount

        atm_calls = [
            opt
            for opt in self.calls
            if opt.strike is not None and min_strike <= opt.strike <= max_strike
        ]
        atm_puts = [
            opt
            for opt in self.puts
            if opt.strike is not None and min_strike <= opt.strike <= max_strike
        ]

        return {"calls": atm_calls, "puts": atm_puts}

    def get_itm_options(self) -> Dict[str, List[OptionQuote]]:
        """
        Get in-the-money options.

        Returns:
            Dictionary with 'calls' and 'puts' lists of ITM options
        """
        if self.underlying_price is None:
            return {"calls": [], "puts": []}

        itm_calls = [
            opt
            for opt in self.calls
            if opt.strike is not None and opt.strike < self.underlying_price
        ]
        itm_puts = [
            opt
            for opt in self.puts
            if opt.strike is not None and opt.strike > self.underlying_price
        ]

        return {"calls": itm_calls, "puts": itm_puts}

    def get_otm_options(self) -> Dict[str, List[OptionQuote]]:
        """
        Get out-of-the-money options.

        Returns:
            Dictionary with 'calls' and 'puts' lists of OTM options
        """
        if self.underlying_price is None:
            return {"calls": [], "puts": []}

        otm_calls = [
            opt
            for opt in self.calls
            if opt.strike is not None and opt.strike > self.underlying_price
        ]
        otm_puts = [
            opt
            for opt in self.puts
            if opt.strike is not None and opt.strike < self.underlying_price
        ]

        return {"calls": otm_calls, "puts": otm_puts}

    def get_option_by_delta(
        self, target_delta: float, option_type: str = "call"
    ) -> Optional[OptionQuote]:
        """
        Find option closest to target delta.

        Args:
            target_delta: Target delta value
            option_type: 'call' or 'put'

        Returns:
            Option closest to target delta, or None if no options have delta
        """
        options = self.calls if option_type.lower() == "call" else self.puts

        # Filter options that have delta values
        options_with_delta = [opt for opt in options if opt.delta is not None]
        if not options_with_delta:
            return None

        # Find closest delta
        closest_option = min(
            options_with_delta, key=lambda opt: abs((opt.delta or 0) - target_delta)
        )

        return closest_option

    def get_liquid_options(
        self, min_volume: int = 10, min_bid: float = 0.05
    ) -> "OptionsChain":
        """
        Filter options by liquidity criteria.

        Args:
            min_volume: Minimum daily volume
            min_bid: Minimum bid price

        Returns:
            New OptionsChain with liquid options only
        """
        liquid_calls = [
            opt
            for opt in self.calls
            if (opt.volume or 0) >= min_volume and opt.bid >= min_bid
        ]
        liquid_puts = [
            opt
            for opt in self.puts
            if (opt.volume or 0) >= min_volume and opt.bid >= min_bid
        ]

        return OptionsChain(
            underlying_symbol=self.underlying_symbol,
            expiration_date=self.expiration_date,
            underlying_price=self.underlying_price,
            calls=liquid_calls,
            puts=liquid_puts,
            quote_time=self.quote_time,
        )

    def get_summary_stats(self) -> Dict[str, Any]:
        """
        Get summary statistics for the options chain.

        Returns:
            Dictionary with chain statistics
        """
        all_options = self.all_options
        if not all_options:
            return {}

        # Strike statistics
        strikes = self.get_strikes()

        # Volume statistics
        volumes = [opt.volume or 0 for opt in all_options]
        total_volume = sum(volumes)

        # Open interest statistics
        open_interests = [opt.open_interest or 0 for opt in all_options]
        total_oi = sum(open_interests)

        # Greeks statistics (if available)
        deltas = [opt.delta for opt in all_options if opt.delta is not None]

        return {
            "total_options": len(all_options),
            "call_count": len(self.calls),
            "put_count": len(self.puts),
            "strike_range": {
                "min": min(strikes) if strikes else None,
                "max": max(strikes) if strikes else None,
                "count": len(strikes),
            },
            "volume": {
                "total": total_volume,
                "average": total_volume / len(all_options) if all_options else 0,
            },
            "open_interest": {
                "total": total_oi,
                "average": total_oi / len(all_options) if all_options else 0,
            },
            "greeks": {
                "delta_available": len(deltas),
                "avg_delta": sum(deltas) / len(deltas) if deltas else None,
            },
        }


class OptionsChainResponse(BaseModel):
    """API response for options chain data."""
    
    underlying_symbol: str = Field(..., description="Underlying asset symbol")
    underlying_price: Optional[float] = Field(None, description="Current underlying price")
    expiration_date: Optional[str] = Field(None, description="Expiration date (ISO format)")
    quote_time: str = Field(..., description="Quote timestamp (ISO format)")
    calls: List[Dict[str, Any]] = Field(default_factory=list, description="Call options data")
    puts: List[Dict[str, Any]] = Field(default_factory=list, description="Put options data")
    data_source: str = Field(..., description="Data source identifier")
    cached: bool = Field(False, description="Whether data was served from cache")


class GreeksResponse(BaseModel):
    """API response for option Greeks data."""
    
    option_symbol: str = Field(..., description="Option symbol")
    underlying_symbol: str = Field(..., description="Underlying asset symbol")
    strike: float = Field(..., description="Strike price")
    expiration_date: str = Field(..., description="Expiration date (ISO format)")
    option_type: str = Field(..., description="Option type (call/put)")
    days_to_expiration: Optional[int] = Field(None, description="Days to expiration")
    
    # Greeks
    delta: Optional[float] = Field(None, description="Delta")
    gamma: Optional[float] = Field(None, description="Gamma")
    theta: Optional[float] = Field(None, description="Theta")
    vega: Optional[float] = Field(None, description="Vega")
    rho: Optional[float] = Field(None, description="Rho")
    charm: Optional[float] = Field(None, description="Charm")
    vanna: Optional[float] = Field(None, description="Vanna")
    speed: Optional[float] = Field(None, description="Speed")
    zomma: Optional[float] = Field(None, description="Zomma")
    color: Optional[float] = Field(None, description="Color")
    
    # Additional data
    implied_volatility: Optional[float] = Field(None, description="Implied volatility")
    underlying_price: Optional[float] = Field(None, description="Underlying price")
    option_price: Optional[float] = Field(None, description="Option price")
    data_source: str = Field(..., description="Data source identifier")
    cached: bool = Field(False, description="Whether data was served from cache")
