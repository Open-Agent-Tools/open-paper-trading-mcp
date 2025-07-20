"""
Asset classes for different financial instruments.

Asset models with improvements for FastAPI/MCP architecture.
"""

from datetime import date, datetime
from typing import Any, Optional, Union

from pydantic import BaseModel, ConfigDict, Field, field_validator


def asset_factory(symbol: Union[str, "Asset", None] = None) -> Optional["Asset"]:
    """
    Create the appropriate asset based on the symbol.

    Args:
        symbol: Case-insensitive symbol for the asset being created

    Returns:
        An Asset, Option, Call, or Put object, or None if symbol is None
    """
    if symbol is None:
        return None

    if isinstance(symbol, Asset):
        return symbol

    symbol = symbol.upper().strip()

    # Options have longer symbols with specific patterns
    if len(symbol) > 8:
        if "P0" in symbol:
            return Put(symbol=symbol)
        elif "C0" in symbol:
            return Call(symbol=symbol)
        else:
            return Option(symbol=symbol)
    else:
        return Stock(symbol=symbol)


class Asset(BaseModel):
    """Base class for all tradeable assets."""

    model_config = ConfigDict(frozen=True)

    symbol: str = Field(..., description="Asset symbol (e.g., AAPL, GOOGL)")
    asset_type: str = Field(default="stock", description="Type of asset")

    # Option-specific attributes (None for stocks)
    underlying: Optional["Asset"] = Field(
        default=None, description="Underlying asset for options"
    )
    option_type: str | None = Field(default=None, description="Option type (call/put)")
    strike: float | None = Field(default=None, description="Strike price for options")
    expiration_date: date | None = Field(
        default=None, description="Expiration date for options"
    )

    @field_validator("symbol", mode="before")
    def normalize_symbol(self, v: str) -> str:
        if isinstance(v, str):
            return v.upper().strip()
        return v

    def __eq__(self, other: object) -> bool:
        """Override equality to compare symbols."""
        if isinstance(other, Asset):
            return self.symbol == other.symbol
        if isinstance(other, str):
            return self.symbol == other.upper().strip()
        return False

    def __hash__(self) -> int:
        return hash(self.symbol)


class Stock(Asset):
    """Stock asset class for specific stock instruments."""

    def __init__(self, symbol: str, **data: Any) -> None:
        super().__init__(symbol=symbol, asset_type="stock", **data)  # type: ignore


class Option(Asset):
    """Base class for option derivatives."""

    underlying: Asset
    option_type: str
    strike: float
    expiration_date: date

    def __init__(
        self,
        symbol: str | None = None,
        underlying: str | Asset | None = None,
        option_type: str | None = None,
        strike: float | None = None,
        expiration_date: str | date | datetime | None = None,
        **data: Any,
    ) -> None:
        if symbol is not None:
            # Parse from option symbol (e.g., "AAPL240119C00195000")
            parsed = self._parse_option_symbol(symbol)
            data.update(
                {
                    "symbol": symbol,
                    "asset_type": parsed["option_type"],
                    "underlying": Stock(symbol=str(parsed["underlying"])),
                    "option_type": parsed["option_type"],
                    "strike": parsed["strike"],
                    "expiration_date": parsed["expiration_date"],
                }
            )
            super().__init__(**data)
        else:
            # Build from components
            if not underlying:
                raise ValueError("Option: underlying asset is required")
            if option_type not in ["call", "put"]:
                raise ValueError("Option: option_type must be 'call' or 'put'")
            if not strike or strike <= 0:
                raise ValueError("Option: strike must be positive")
            if not expiration_date:
                raise ValueError("Option: expiration_date is required")

            underlying_asset = (
                asset_factory(underlying)
                if not isinstance(underlying, Asset)
                else underlying
            )
            exp_date = self._parse_date(expiration_date)

            # Build option symbol from components
            exp_str = exp_date.strftime("%y%m%d")
            option_char = "C" if option_type == "call" else "P"
            strike_str = f"{int(strike * 1000):08d}"
            if underlying_asset is None:
                raise ValueError("Option: underlying asset could not be created")
            built_symbol = (
                f"{underlying_asset.symbol}{exp_str}{option_char}{strike_str}"
            )

            data.update(
                {
                    "symbol": built_symbol,
                    "asset_type": option_type,
                    "underlying": underlying_asset,
                    "option_type": option_type,
                    "strike": float(strike),
                    "expiration_date": exp_date,
                }
            )
            super().__init__(**data)

    @staticmethod
    def _parse_option_symbol(symbol: str) -> dict[str, str | float | date]:
        """
        Parse option symbol like AAPL240119C00195000.

        Format: [UNDERLYING][YYMMDD][C/P][STRIKE*1000]
        """
        symbol = symbol.upper().strip()

        # Reverse the symbol for easier parsing
        reversed_symbol = symbol[::-1]

        try:
            # Extract strike (last 8 digits)
            strike = float(reversed_symbol[0:8][::-1]) / 1000

            # Extract option type (9th character from end)
            option_type = "call" if reversed_symbol[8] == "C" else "put"

            # Extract expiration date (6 digits before option type)
            exp_str = reversed_symbol[9:15][::-1]
            exp_date = datetime.strptime(exp_str, "%y%m%d").date()

            # Extract underlying symbol (remaining characters)
            underlying = reversed_symbol[15:][::-1]

            return {
                "underlying": underlying,
                "option_type": option_type,
                "strike": strike,
                "expiration_date": exp_date,
            }
        except (ValueError, IndexError) as e:
            raise ValueError(f"Invalid option symbol format: {symbol}") from e

    @staticmethod
    def _parse_date(date_input: str | date | datetime) -> date:
        """Parse various date formats into a date object."""
        if isinstance(date_input, date):
            return date_input
        if isinstance(date_input, datetime):
            return date_input.date()
        if isinstance(date_input, str):
            # Try common date formats
            for fmt in ["%Y-%m-%d", "%y%m%d", "%Y%m%d"]:
                try:
                    return datetime.strptime(date_input, fmt).date()
                except ValueError:
                    continue
            raise ValueError(f"Could not parse date: {date_input}")
        raise ValueError(f"Invalid date type: {type(date_input)}")

    def get_intrinsic_value(self, underlying_price: float) -> float:
        """Calculate intrinsic value of the option."""
        if self.option_type == "call":
            return max(underlying_price - self.strike, 0)
        elif self.option_type == "put":
            return max(self.strike - underlying_price, 0)
        return 0.0

    def get_extrinsic_value(
        self, underlying_price: float, option_price: float
    ) -> float:
        """Calculate extrinsic (time) value of the option."""
        return option_price - self.get_intrinsic_value(underlying_price)

    def get_days_to_expiration(self, as_of_date: date | datetime | None = None) -> int:
        """Calculate days until expiration."""
        if as_of_date is None:
            as_of_date = date.today()
        elif isinstance(as_of_date, datetime):
            as_of_date = as_of_date.date()

        return (self.expiration_date - as_of_date).days

    def is_itm(self, underlying_price: float) -> bool:
        """Check if option is in-the-money."""
        return self.get_intrinsic_value(underlying_price) > 0

    def is_otm(self, underlying_price: float) -> bool:
        """Check if option is out-of-the-money."""
        return not self.is_itm(underlying_price)


class Call(Option):
    """Call option class."""

    def __init__(
        self,
        symbol: str | None = None,
        underlying: str | Asset | None = None,
        strike: float | None = None,
        expiration_date: str | date | None = None,
        **data: Any,
    ) -> None:
        super().__init__(
            symbol=symbol,
            underlying=underlying,
            option_type="call",
            strike=strike,
            expiration_date=expiration_date,
            **data,
        )


class Put(Option):
    """Put option class."""

    def __init__(
        self,
        symbol: str | None = None,
        underlying: str | Asset | None = None,
        strike: float | None = None,
        expiration_date: str | date | None = None,
        **data: Any,
    ) -> None:
        super().__init__(
            symbol=symbol,
            underlying=underlying,
            option_type="put",
            strike=strike,
            expiration_date=expiration_date,
            **data,
        )
