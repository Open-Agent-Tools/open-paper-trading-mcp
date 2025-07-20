"""
Options Greeks calculation service using Black-Scholes model.

Pure Python implementation adapted from reference implementation, with improvements for numerical stability.
"""

import math
from typing import TYPE_CHECKING

from app.models.assets import Option

if TYPE_CHECKING:
    from app.models.assets import Option
    from app.models.quotes import OptionQuote


def calculate_option_greeks(
    option_type: str,
    strike: float,
    underlying_price: float,
    days_to_expiration: int,
    option_price: float,
    volatility: float = 0.2,
    dividend_yield: float = 0.0,
) -> dict[str, float | None]:
    """
    Calculate option Greeks using Black-Scholes model.

    Args:
        option_type: 'call' or 'put'
        strike: Strike price
        underlying_price: Current price of underlying
        days_to_expiration: Days until expiration
        option_price: Current option price (for IV calculation)
        dividend_yield: Annual dividend yield (default 0%)

    Returns:
        Dictionary containing all Greeks and implied volatility
    """

    # Initialize output with None values
    greeks: dict[str, float | None] = {
        "iv": None,
        "delta": None,
        "gamma": None,
        "theta": None,
        "vega": None,
        "rho": None,
        "vanna": None,
        "charm": None,
        "speed": None,
        "zomma": None,
        "color": None,
        "veta": None,
        "vomma": None,
        "ultima": None,
        "dual_delta": None,
    }

    # Validate inputs
    if not _validate_inputs(
        option_type, strike, underlying_price, days_to_expiration, option_price
    ):
        return greeks

    # Convert parameters to Black-Scholes format
    S = underlying_price
    K = strike
    T = days_to_expiration / 365.0  # Time to expiration in years
    r = 0.02
    q = dividend_yield

    # Calculate implied volatility first
    try:
        if option_type.lower() == "call":
            iv = _implied_volatility_call(S, K, r, q, T, option_price)
        else:
            iv = _implied_volatility_put(S, K, r, q, T, option_price)

        if iv is None or math.isnan(iv) or iv <= 0:
            return greeks

        greeks["iv"] = iv

        # Calculate all Greeks using the implied volatility
        greeks.update(_calculate_all_greeks(option_type.lower(), S, K, r, q, T, iv))

    except (ValueError, ZeroDivisionError, OverflowError):
        # Return empty greeks if calculation fails
        pass

    return greeks


def _validate_inputs(
    option_type: str,
    strike: float,
    underlying_price: float,
    days_to_expiration: int,
    option_price: float,
) -> bool:
    """Validate input parameters."""
    if option_type.lower() not in ["call", "put"]:
        return False
    if strike <= 0 or underlying_price <= 0:
        return False
    if days_to_expiration <= 0:
        return False
    if option_price <= 0:
        return False
    return True


def _normal_cdf(x: float) -> float:
    """Standard normal cumulative distribution function."""
    # Approximation using error function
    return 0.5 * (1 + math.erf(x / math.sqrt(2)))


def _normal_pdf(x: float) -> float:
    """Standard normal probability density function."""
    return math.exp(-0.5 * x * x) / math.sqrt(2 * math.pi)


def _d1(S: float, K: float, r: float, q: float, T: float, sigma: float) -> float:
    """Calculate d1 parameter for Black-Scholes."""
    return (math.log(S / K) + (r - q + 0.5 * sigma * sigma) * T) / (
        sigma * math.sqrt(T)
    )


def _d2(S: float, K: float, r: float, q: float, T: float, sigma: float) -> float:
    """Calculate d2 parameter for Black-Scholes."""
    return _d1(S, K, r, q, T, sigma) - sigma * math.sqrt(T)


def _black_scholes_call(
    S: float, K: float, r: float, q: float, T: float, sigma: float
) -> float:
    """Black-Scholes call option price."""
    d1 = _d1(S, K, r, q, T, sigma)
    d2 = _d2(S, K, r, q, T, sigma)

    call_price = S * math.exp(-q * T) * _normal_cdf(d1) - K * math.exp(
        -r * T
    ) * _normal_cdf(d2)
    return call_price


def _black_scholes_put(
    S: float, K: float, r: float, q: float, T: float, sigma: float
) -> float:
    """Black-Scholes put option price."""
    d1 = _d1(S, K, r, q, T, sigma)
    d2 = _d2(S, K, r, q, T, sigma)

    put_price = K * math.exp(-r * T) * _normal_cdf(-d2) - S * math.exp(
        -q * T
    ) * _normal_cdf(-d1)
    return put_price


def _implied_volatility_call(
    S: float, K: float, r: float, q: float, T: float, market_price: float
) -> float | None:
    """Calculate implied volatility for call option using Newton-Raphson method."""
    return _implied_volatility_newton_raphson("call", S, K, r, q, T, market_price)


def _implied_volatility_put(
    S: float, K: float, r: float, q: float, T: float, market_price: float
) -> float | None:
    """Calculate implied volatility for put option using Newton-Raphson method."""
    return _implied_volatility_newton_raphson("put", S, K, r, q, T, market_price)


def _implied_volatility_newton_raphson(
    option_type: str,
    S: float,
    K: float,
    r: float,
    q: float,
    T: float,
    market_price: float,
    max_iterations: int = 100,
    tolerance: float = 1e-6,
) -> float | None:
    """Calculate implied volatility using Newton-Raphson method."""

    # Initial guess for volatility
    sigma = 0.2

    for _ in range(max_iterations):
        if option_type == "call":
            price = _black_scholes_call(S, K, r, q, T, sigma)
        else:
            price = _black_scholes_put(S, K, r, q, T, sigma)

        # Calculate vega for Newton-Raphson step
        d1 = _d1(S, K, r, q, T, sigma)
        vega = S * math.exp(-q * T) * _normal_pdf(d1) * math.sqrt(T)

        if abs(vega) < 1e-10:  # Avoid division by zero
            break

        # Newton-Raphson step
        diff = price - market_price
        if abs(diff) < tolerance:
            return sigma

        sigma -= diff / vega

        # Keep sigma positive and reasonable
        if sigma <= 0:
            sigma = 0.001
        elif sigma > 5:  # Cap at 500% volatility
            sigma = 5

    return sigma if sigma > 0 else None


def _calculate_all_greeks(
    option_type: str, S: float, K: float, r: float, q: float, T: float, sigma: float
) -> dict[str, float]:
    """Calculate all Greeks given implied volatility."""

    d1 = _d1(S, K, r, q, T, sigma)
    d2 = _d2(S, K, r, q, T, sigma)

    sqrt_T = math.sqrt(T)
    norm_d1 = _normal_cdf(d1)
    norm_d2 = _normal_cdf(d2)
    norm_pdf_d1 = _normal_pdf(d1)

    greeks = {}

    # First-order Greeks
    if option_type == "call":
        greeks["delta"] = math.exp(-q * T) * norm_d1
    else:
        greeks["delta"] = math.exp(-q * T) * (norm_d1 - 1)

    # Gamma (same for calls and puts)
    greeks["gamma"] = (math.exp(-q * T) * norm_pdf_d1) / (S * sigma * sqrt_T)

    # Vega (same for calls and puts)
    greeks["vega"] = S * math.exp(-q * T) * norm_pdf_d1 * sqrt_T

    # Theta
    if option_type == "call":
        theta_part1 = -S * math.exp(-q * T) * norm_pdf_d1 * sigma / (2 * sqrt_T)
        theta_part2 = q * S * math.exp(-q * T) * norm_d1
        theta_part3 = -r * K * math.exp(-r * T) * norm_d2
        greeks["theta"] = (theta_part1 + theta_part2 + theta_part3) / 365
    else:
        theta_part1 = -S * math.exp(-q * T) * norm_pdf_d1 * sigma / (2 * sqrt_T)
        theta_part2 = -q * S * math.exp(-q * T) * _normal_cdf(-d1)
        theta_part3 = r * K * math.exp(-r * T) * _normal_cdf(-d2)
        greeks["theta"] = (theta_part1 + theta_part2 + theta_part3) / 365

    # Rho
    if option_type == "call":
        greeks["rho"] = K * T * math.exp(-r * T) * norm_d2
    else:
        greeks["rho"] = -K * T * math.exp(-r * T) * _normal_cdf(-d2)

    # Second-order Greeks
    greeks["vanna"] = -math.exp(-q * T) * norm_pdf_d1 * d2 / sigma

    if option_type == "call":
        greeks["charm"] = (
            q * math.exp(-q * T) * norm_d1
            - math.exp(-q * T)
            * norm_pdf_d1
            * (2 * (r - q) * T - d2 * sigma * sqrt_T)
            / (2 * T * sigma * sqrt_T)
        ) / 365
    else:
        greeks["charm"] = (
            -q * math.exp(-q * T) * _normal_cdf(-d1)
            - math.exp(-q * T)
            * norm_pdf_d1
            * (2 * (r - q) * T - d2 * sigma * sqrt_T)
            / (2 * T * sigma * sqrt_T)
        ) / 365

    greeks["speed"] = (
        -math.exp(-q * T)
        * norm_pdf_d1
        * (d1 / (sigma * sqrt_T) + 1)
        / (S * S * sigma * sqrt_T)
    )

    greeks["zomma"] = (
        math.exp(-q * T) * norm_pdf_d1 * (d1 * d2 - 1) / (S * sigma * sigma * sqrt_T)
    )

    greeks["color"] = (
        -math.exp(-q * T)
        * norm_pdf_d1
        / (2 * S * T * sigma * sqrt_T)
        * (
            2 * q * T
            + 1
            + (2 * (r - q) * T - d2 * sigma * sqrt_T) * d1 / (sigma * sqrt_T)
        )
    ) / 365

    greeks["veta"] = (
        S
        * math.exp(-q * T)
        * norm_pdf_d1
        * sqrt_T
        * (q + ((r - q) * d1) / (sigma * sqrt_T) - (1 + d1 * d2) / (2 * T))
    ) / (100 * 365)

    greeks["vomma"] = S * math.exp(-q * T) * norm_pdf_d1 * sqrt_T * d1 * d2 / sigma

    greeks["ultima"] = (
        -greeks["vomma"] / sigma * (d1 * d2 - d1 / d2 - d2 / d1 - 1)
    ) / 365

    # Dual delta
    if option_type == "call":
        greeks["dual_delta"] = -math.exp(-r * T) * norm_d2
    else:
        greeks["dual_delta"] = math.exp(-r * T) * _normal_cdf(-d2)

    return greeks


# Helper function to integrate with the quote system
def update_option_quote_with_greeks(
    option_quote: "OptionQuote",
    dividend_yield: float = 0.0,
) -> None:
    """Update an OptionQuote with calculated Greeks."""
    if (
        not option_quote.is_priceable()
        or option_quote.underlying_price is None
        or not hasattr(option_quote.asset, "option_type")
    ):
        return

    days_to_exp = option_quote.days_to_expiration
    if days_to_exp is None or days_to_exp <= 0:
        return

    if not isinstance(option_quote.asset, Option):
        return

    greeks = calculate_option_greeks(
        option_type=option_quote.asset.option_type,
        strike=option_quote.asset.strike,
        underlying_price=option_quote.underlying_price,
        days_to_expiration=days_to_exp,
        option_price=option_quote.price or 0.0,
        volatility=option_quote.iv or 0.2,
        dividend_yield=dividend_yield,
    )

    # Update the quote with calculated Greeks
    for greek_name, value in greeks.items():
        if value is not None and not math.isnan(value):
            setattr(option_quote, greek_name, value)
