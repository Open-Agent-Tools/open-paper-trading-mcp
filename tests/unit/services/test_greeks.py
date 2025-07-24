"""
Comprehensive tests for Options Greeks calculation service using Black-Scholes model.

Tests cover:
- Black-Scholes option pricing model validation
- Implied volatility calculation using Newton-Raphson method
- First-order Greeks: Delta, Gamma, Theta, Vega, Rho
- Second-order Greeks: Vanna, Charm, Speed, Zomma, Color, Veta, Vomma, Ultima
- Dual Delta calculations for risk management
- Greeks calculation for both call and put options
- Input validation and error handling
- Edge cases: deep ITM/OTM options, near-expiration scenarios
- Mathematical accuracy and numerical stability
- Integration with OptionQuote system
- Performance optimization for large portfolios
"""

import math
from unittest.mock import Mock, patch

import pytest

from app.models.assets import Call, Stock
from app.models.quotes import OptionQuote
from app.services.greeks import (
    _black_scholes_call,
    _black_scholes_put,
    _calculate_all_greeks,
    _d1,
    _d2,
    _implied_volatility_call,
    _implied_volatility_newton_raphson,
    _implied_volatility_put,
    _normal_cdf,
    _normal_pdf,
    _validate_inputs,
    calculate_option_greeks,
    update_option_quote_with_greeks,
)


class TestInputValidation:
    """Test input validation for Greeks calculations."""

    def test_validate_inputs_valid_call(self):
        """Test input validation with valid call option parameters."""
        result = _validate_inputs("call", 100.0, 105.0, 30, 2.50)
        assert result is True

    def test_validate_inputs_valid_put(self):
        """Test input validation with valid put option parameters."""
        result = _validate_inputs("put", 100.0, 95.0, 45, 3.75)
        assert result is True

    def test_validate_inputs_invalid_option_type(self):
        """Test input validation with invalid option type."""
        result = _validate_inputs("invalid", 100.0, 105.0, 30, 2.50)
        assert result is False

    def test_validate_inputs_zero_strike(self):
        """Test input validation with zero strike price."""
        result = _validate_inputs("call", 0.0, 105.0, 30, 2.50)
        assert result is False

    def test_validate_inputs_negative_strike(self):
        """Test input validation with negative strike price."""
        result = _validate_inputs("call", -50.0, 105.0, 30, 2.50)
        assert result is False

    def test_validate_inputs_zero_underlying_price(self):
        """Test input validation with zero underlying price."""
        result = _validate_inputs("call", 100.0, 0.0, 30, 2.50)
        assert result is False

    def test_validate_inputs_negative_underlying_price(self):
        """Test input validation with negative underlying price."""
        result = _validate_inputs("call", 100.0, -105.0, 30, 2.50)
        assert result is False

    def test_validate_inputs_zero_days_to_expiration(self):
        """Test input validation with zero days to expiration."""
        result = _validate_inputs("call", 100.0, 105.0, 0, 2.50)
        assert result is False

    def test_validate_inputs_negative_days_to_expiration(self):
        """Test input validation with negative days to expiration."""
        result = _validate_inputs("call", 100.0, 105.0, -30, 2.50)
        assert result is False

    def test_validate_inputs_zero_option_price(self):
        """Test input validation with zero option price."""
        result = _validate_inputs("call", 100.0, 105.0, 30, 0.0)
        assert result is False

    def test_validate_inputs_negative_option_price(self):
        """Test input validation with negative option price."""
        result = _validate_inputs("call", 100.0, 105.0, 30, -2.50)
        assert result is False

    def test_validate_inputs_case_insensitive_option_type(self):
        """Test input validation is case insensitive for option type."""
        assert _validate_inputs("CALL", 100.0, 105.0, 30, 2.50) is True
        assert _validate_inputs("PUT", 100.0, 95.0, 30, 2.50) is True
        assert _validate_inputs("Call", 100.0, 105.0, 30, 2.50) is True
        assert _validate_inputs("Put", 100.0, 95.0, 30, 2.50) is True

    def test_validate_inputs_edge_case_small_values(self):
        """Test input validation with very small but valid values."""
        result = _validate_inputs("call", 0.01, 0.01, 1, 0.01)
        assert result is True


class TestNormalDistributionFunctions:
    """Test normal distribution helper functions."""

    def test_normal_cdf_standard_values(self):
        """Test normal CDF with standard statistical values."""
        # Test known values
        assert abs(_normal_cdf(0.0) - 0.5) < 1e-10
        assert abs(_normal_cdf(1.645) - 0.95) < 1e-3  # 95th percentile
        assert abs(_normal_cdf(2.326) - 0.99) < 1e-3  # 99th percentile
        assert abs(_normal_cdf(-1.645) - 0.05) < 1e-3  # 5th percentile

    def test_normal_cdf_extreme_values(self):
        """Test normal CDF with extreme values."""
        assert _normal_cdf(-10.0) < 1e-10  # Very close to 0
        assert _normal_cdf(10.0) > 0.9999999  # Very close to 1

    def test_normal_cdf_symmetry(self):
        """Test normal CDF symmetry property."""
        for x in [-3, -1, -0.5, 0.5, 1, 3]:
            assert abs(_normal_cdf(x) + _normal_cdf(-x) - 1.0) < 1e-10

    def test_normal_pdf_standard_values(self):
        """Test normal PDF with standard values."""
        # Maximum at x=0
        assert abs(_normal_pdf(0.0) - (1 / math.sqrt(2 * math.pi))) < 1e-10

        # Symmetry
        for x in [-2, -1, 0.5, 1, 2]:
            assert abs(_normal_pdf(x) - _normal_pdf(-x)) < 1e-10

    def test_normal_pdf_positive_values(self):
        """Test that normal PDF always returns positive values."""
        for x in [-5, -2, -1, 0, 1, 2, 5]:
            assert _normal_pdf(x) > 0

    def test_normal_pdf_extreme_values(self):
        """Test normal PDF with extreme values."""
        assert _normal_pdf(-10.0) < 1e-10  # Very close to 0
        assert _normal_pdf(10.0) < 1e-10  # Very close to 0


class TestBlackScholesParameters:
    """Test Black-Scholes parameter calculations."""

    def test_d1_calculation(self):
        """Test d1 parameter calculation."""
        S, K, r, q, T, sigma = 100.0, 100.0, 0.05, 0.02, 0.25, 0.2

        d1 = _d1(S, K, r, q, T, sigma)

        # Expected calculation
        expected = (math.log(S / K) + (r - q + 0.5 * sigma * sigma) * T) / (
            sigma * math.sqrt(T)
        )
        assert abs(d1 - expected) < 1e-10

    def test_d1_itm_call(self):
        """Test d1 for in-the-money call option."""
        d1 = _d1(110.0, 100.0, 0.05, 0.0, 0.25, 0.2)  # ITM call
        assert d1 > 0  # Should be positive for ITM call

    def test_d1_otm_call(self):
        """Test d1 for out-of-the-money call option."""
        d1 = _d1(90.0, 100.0, 0.05, 0.0, 0.25, 0.2)  # OTM call
        assert d1 < 0  # Should be negative for OTM call

    def test_d2_calculation(self):
        """Test d2 parameter calculation."""
        S, K, r, q, T, sigma = 100.0, 105.0, 0.05, 0.0, 0.25, 0.2

        d1_val = _d1(S, K, r, q, T, sigma)
        d2 = _d2(S, K, r, q, T, sigma)

        # d2 = d1 - sigma * sqrt(T)
        expected = d1_val - sigma * math.sqrt(T)
        assert abs(d2 - expected) < 1e-10

    def test_d1_d2_relationship(self):
        """Test relationship between d1 and d2."""
        S, K, r, q, T, sigma = 100.0, 100.0, 0.05, 0.0, 0.25, 0.2

        d1_val = _d1(S, K, r, q, T, sigma)
        d2_val = _d2(S, K, r, q, T, sigma)

        # d1 should always be greater than d2 for positive volatility
        assert d1_val > d2_val
        assert abs((d1_val - d2_val) - sigma * math.sqrt(T)) < 1e-10

    def test_parameters_with_dividends(self):
        """Test parameter calculations with dividend yield."""
        S, K, r, q, T, sigma = 100.0, 100.0, 0.05, 0.03, 0.25, 0.2

        d1_with_div = _d1(S, K, r, q, T, sigma)
        d1_no_div = _d1(S, K, r, 0.0, T, sigma)

        # Higher dividend yield should reduce d1 for calls
        assert d1_with_div < d1_no_div

    def test_parameters_time_to_expiration_effect(self):
        """Test effect of time to expiration on parameters."""
        S, K, r, q, sigma = 100.0, 100.0, 0.05, 0.0, 0.2

        d1_short = _d1(S, K, r, q, 0.08, sigma)  # ~1 month
        d1_long = _d1(S, K, r, q, 1.0, sigma)  # 1 year

        # For ATM options, longer time should increase d1 due to time value
        assert abs(d1_long) < abs(d1_short) or d1_long > d1_short


class TestBlackScholesPricing:
    """Test Black-Scholes option pricing formulas."""

    def test_black_scholes_call_atm(self):
        """Test Black-Scholes call pricing for at-the-money option."""
        S, K, r, q, T, sigma = 100.0, 100.0, 0.05, 0.0, 0.25, 0.2

        call_price = _black_scholes_call(S, K, r, q, T, sigma)

        # ATM call should have positive value
        assert call_price > 0
        # Should be roughly equal to time value for ATM option
        assert call_price > 2.0  # Minimum time value

    def test_black_scholes_put_atm(self):
        """Test Black-Scholes put pricing for at-the-money option."""
        S, K, r, q, T, sigma = 100.0, 100.0, 0.05, 0.0, 0.25, 0.2

        put_price = _black_scholes_put(S, K, r, q, T, sigma)

        # ATM put should have positive value
        assert put_price > 0
        assert put_price > 2.0  # Minimum time value

    def test_put_call_parity(self):
        """Test put-call parity relationship."""
        S, K, r, q, T, sigma = 100.0, 100.0, 0.05, 0.0, 0.25, 0.2

        call_price = _black_scholes_call(S, K, r, q, T, sigma)
        put_price = _black_scholes_put(S, K, r, q, T, sigma)

        # Put-call parity: C - P = S*e^(-q*T) - K*e^(-r*T)
        parity_rhs = S * math.exp(-q * T) - K * math.exp(-r * T)
        parity_lhs = call_price - put_price

        assert abs(parity_lhs - parity_rhs) < 1e-6

    def test_deep_itm_call(self):
        """Test deep in-the-money call option pricing."""
        call_price = _black_scholes_call(150.0, 100.0, 0.05, 0.0, 0.25, 0.2)

        # Deep ITM call should be approximately intrinsic value + time value
        intrinsic = 150.0 - 100.0
        assert call_price > intrinsic  # Should exceed intrinsic value
        assert call_price < intrinsic + 10.0  # But not by too much

    def test_deep_otm_call(self):
        """Test deep out-of-the-money call option pricing."""
        call_price = _black_scholes_call(50.0, 100.0, 0.05, 0.0, 0.25, 0.2)

        # Deep OTM call should have small positive value
        assert 0 < call_price < 1.0

    def test_deep_itm_put(self):
        """Test deep in-the-money put option pricing."""
        put_price = _black_scholes_put(50.0, 100.0, 0.05, 0.0, 0.25, 0.2)

        # Deep ITM put should be close to intrinsic value (but may be slightly less due to time value and discounting)
        intrinsic = 100.0 - 50.0
        assert put_price > intrinsic * 0.95  # Should be close to intrinsic value

    def test_deep_otm_put(self):
        """Test deep out-of-the-money put option pricing."""
        put_price = _black_scholes_put(150.0, 100.0, 0.05, 0.0, 0.25, 0.2)

        # Deep OTM put should have small positive value
        assert 0 < put_price < 1.0

    def test_price_monotonicity_underlying(self):
        """Test that call prices increase and put prices decrease with underlying price."""
        K, r, q, T, sigma = 100.0, 0.05, 0.0, 0.25, 0.2

        underlyings = [80.0, 90.0, 100.0, 110.0, 120.0]
        call_prices = [_black_scholes_call(S, K, r, q, T, sigma) for S in underlyings]
        put_prices = [_black_scholes_put(S, K, r, q, T, sigma) for S in underlyings]

        # Call prices should increase with underlying price
        for i in range(1, len(call_prices)):
            assert call_prices[i] > call_prices[i - 1]

        # Put prices should decrease with underlying price
        for i in range(1, len(put_prices)):
            assert put_prices[i] < put_prices[i - 1]

    def test_price_monotonicity_strike(self):
        """Test that call prices decrease and put prices increase with strike price."""
        S, r, q, T, sigma = 100.0, 0.05, 0.0, 0.25, 0.2

        strikes = [80.0, 90.0, 100.0, 110.0, 120.0]
        call_prices = [_black_scholes_call(S, K, r, q, T, sigma) for K in strikes]
        put_prices = [_black_scholes_put(S, K, r, q, T, sigma) for K in strikes]

        # Call prices should decrease with strike price
        for i in range(1, len(call_prices)):
            assert call_prices[i] < call_prices[i - 1]

        # Put prices should increase with strike price
        for i in range(1, len(put_prices)):
            assert put_prices[i] > put_prices[i - 1]

    def test_time_decay_effect(self):
        """Test that option prices decrease as time to expiration decreases."""
        S, K, r, q, sigma = 100.0, 100.0, 0.05, 0.0, 0.2

        times = [1.0, 0.5, 0.25, 0.08]  # 1 year to 1 month
        call_prices = [_black_scholes_call(S, K, r, q, T, sigma) for T in times]
        put_prices = [_black_scholes_put(S, K, r, q, T, sigma) for T in times]

        # Both call and put prices should decrease with time (time decay)
        for i in range(1, len(call_prices)):
            assert call_prices[i] < call_prices[i - 1]
            assert put_prices[i] < put_prices[i - 1]


class TestImpliedVolatilityCalculation:
    """Test implied volatility calculation methods."""

    def test_implied_volatility_call_exact_match(self):
        """Test implied volatility calculation when theoretical equals market price."""
        S, K, r, q, T, sigma_true = 100.0, 100.0, 0.05, 0.0, 0.25, 0.25

        # Calculate theoretical price
        theoretical_price = _black_scholes_call(S, K, r, q, T, sigma_true)

        # Calculate implied volatility
        implied_vol = _implied_volatility_call(S, K, r, q, T, theoretical_price)

        assert implied_vol is not None
        assert abs(implied_vol - sigma_true) < 1e-4

    def test_implied_volatility_put_exact_match(self):
        """Test implied volatility calculation for put option."""
        S, K, r, q, T, sigma_true = 100.0, 100.0, 0.05, 0.0, 0.25, 0.3

        # Calculate theoretical price
        theoretical_price = _black_scholes_put(S, K, r, q, T, sigma_true)

        # Calculate implied volatility
        implied_vol = _implied_volatility_put(S, K, r, q, T, theoretical_price)

        assert implied_vol is not None
        assert abs(implied_vol - sigma_true) < 1e-4

    def test_implied_volatility_newton_raphson_convergence(self):
        """Test Newton-Raphson method convergence."""
        S, K, r, q, T = 100.0, 105.0, 0.05, 0.0, 0.25
        market_price = 3.5

        implied_vol = _implied_volatility_newton_raphson(
            "call", S, K, r, q, T, market_price, max_iterations=100, tolerance=1e-6
        )

        assert implied_vol is not None
        assert 0.1 < implied_vol < 1.0  # Reasonable volatility range

        # Verify the implied volatility produces the correct price
        calculated_price = _black_scholes_call(S, K, r, q, T, implied_vol)
        assert abs(calculated_price - market_price) < 1e-4

    def test_implied_volatility_extreme_itm(self):
        """Test implied volatility for extremely in-the-money options."""
        S, K, r, q, T = 150.0, 100.0, 0.05, 0.0, 0.25
        market_price = 52.0  # Close to intrinsic value (50)

        implied_vol = _implied_volatility_call(S, K, r, q, T, market_price)

        assert implied_vol is not None
        assert implied_vol > 0

    def test_implied_volatility_extreme_otm(self):
        """Test implied volatility for extremely out-of-the-money options."""
        S, K, r, q, T = 50.0, 100.0, 0.05, 0.0, 0.25
        market_price = 0.10  # Very small price

        implied_vol = _implied_volatility_call(S, K, r, q, T, market_price)

        # May not converge for extreme OTM options
        if implied_vol is not None:
            assert implied_vol > 0

    def test_implied_volatility_bounds_checking(self):
        """Test implied volatility bounds checking."""
        S, K, r, q, T = 100.0, 100.0, 0.05, 0.0, 0.25
        market_price = 5.0

        implied_vol = _implied_volatility_newton_raphson(
            "call", S, K, r, q, T, market_price
        )

        assert implied_vol is not None
        assert 0 < implied_vol <= 5.0  # Should be capped at 500%

    def test_implied_volatility_near_expiration(self):
        """Test implied volatility calculation near expiration."""
        S, K, r, q, T = 100.0, 100.0, 0.05, 0.0, 1 / 365  # 1 day to expiration
        market_price = 1.0

        implied_vol = _implied_volatility_call(S, K, r, q, T, market_price)

        # Near expiration, IV can be very high
        if implied_vol is not None:
            assert implied_vol > 0

    def test_implied_volatility_no_convergence(self):
        """Test implied volatility when Newton-Raphson doesn't converge."""
        S, K, r, q, T = 100.0, 100.0, 0.05, 0.0, 0.25
        market_price = 100.0  # Unrealistically high price

        implied_vol = _implied_volatility_newton_raphson(
            "call", S, K, r, q, T, market_price, max_iterations=5, tolerance=1e-6
        )

        # Should return last iteration value or None
        if implied_vol is not None:
            assert implied_vol > 0


class TestFirstOrderGreeks:
    """Test first-order Greeks calculations."""

    def test_delta_call_atm(self):
        """Test delta calculation for at-the-money call."""
        greeks = _calculate_all_greeks("call", 100.0, 100.0, 0.05, 0.0, 0.25, 0.2)

        # ATM call delta should be around 0.5
        assert 0.4 < greeks["delta"] < 0.6

    def test_delta_call_itm(self):
        """Test delta calculation for in-the-money call."""
        greeks = _calculate_all_greeks("call", 120.0, 100.0, 0.05, 0.0, 0.25, 0.2)

        # ITM call delta should be high (close to 1)
        assert 0.7 < greeks["delta"] < 1.0

    def test_delta_call_otm(self):
        """Test delta calculation for out-of-the-money call."""
        greeks = _calculate_all_greeks("call", 80.0, 100.0, 0.05, 0.0, 0.25, 0.2)

        # OTM call delta should be low (close to 0)
        assert 0.0 < greeks["delta"] < 0.3

    def test_delta_put_atm(self):
        """Test delta calculation for at-the-money put."""
        greeks = _calculate_all_greeks("put", 100.0, 100.0, 0.05, 0.0, 0.25, 0.2)

        # ATM put delta should be around -0.5
        assert -0.6 < greeks["delta"] < -0.4

    def test_delta_put_itm(self):
        """Test delta calculation for in-the-money put."""
        greeks = _calculate_all_greeks("put", 80.0, 100.0, 0.05, 0.0, 0.25, 0.2)

        # ITM put delta should be high negative (close to -1)
        assert -1.0 < greeks["delta"] < -0.7

    def test_delta_put_otm(self):
        """Test delta calculation for out-of-the-money put."""
        greeks = _calculate_all_greeks("put", 120.0, 100.0, 0.05, 0.0, 0.25, 0.2)

        # OTM put delta should be low negative (close to 0)
        assert -0.3 < greeks["delta"] < 0.0

    def test_gamma_symmetric(self):
        """Test that gamma is the same for calls and puts."""
        call_greeks = _calculate_all_greeks("call", 100.0, 100.0, 0.05, 0.0, 0.25, 0.2)
        put_greeks = _calculate_all_greeks("put", 100.0, 100.0, 0.05, 0.0, 0.25, 0.2)

        # Gamma should be identical for calls and puts
        assert abs(call_greeks["gamma"] - put_greeks["gamma"]) < 1e-10

    def test_gamma_positive(self):
        """Test that gamma is always positive."""
        test_cases = [
            (80.0, 100.0),  # OTM call
            (100.0, 100.0),  # ATM call
            (120.0, 100.0),  # ITM call
        ]

        for S, K in test_cases:
            greeks = _calculate_all_greeks("call", S, K, 0.05, 0.0, 0.25, 0.2)
            assert greeks["gamma"] > 0

    def test_gamma_maximum_atm(self):
        """Test that gamma is maximum at-the-money."""
        strikes = [95.0, 100.0, 105.0]
        gammas = []

        for K in strikes:
            greeks = _calculate_all_greeks("call", 100.0, K, 0.05, 0.0, 0.25, 0.2)
            gammas.append(greeks["gamma"])

        # ATM gamma should be highest
        assert gammas[1] > gammas[0]  # ATM > OTM
        assert gammas[1] > gammas[2]  # ATM > ITM

    def test_theta_call_negative(self):
        """Test that theta is negative for call options (time decay)."""
        greeks = _calculate_all_greeks("call", 100.0, 100.0, 0.05, 0.0, 0.25, 0.2)

        # Theta should be negative (time decay)
        assert greeks["theta"] < 0

    def test_theta_put_negative(self):
        """Test that theta is negative for put options (time decay)."""
        greeks = _calculate_all_greeks("put", 100.0, 100.0, 0.05, 0.0, 0.25, 0.2)

        # Theta should be negative (time decay)
        assert greeks["theta"] < 0

    def test_vega_symmetric(self):
        """Test that vega is the same for calls and puts."""
        call_greeks = _calculate_all_greeks("call", 100.0, 100.0, 0.05, 0.0, 0.25, 0.2)
        put_greeks = _calculate_all_greeks("put", 100.0, 100.0, 0.05, 0.0, 0.25, 0.2)

        # Vega should be identical for calls and puts
        assert abs(call_greeks["vega"] - put_greeks["vega"]) < 1e-10

    def test_vega_positive(self):
        """Test that vega is always positive."""
        test_cases = [
            (80.0, 100.0),  # OTM call
            (100.0, 100.0),  # ATM call
            (120.0, 100.0),  # ITM call
        ]

        for S, K in test_cases:
            greeks = _calculate_all_greeks("call", S, K, 0.05, 0.0, 0.25, 0.2)
            assert greeks["vega"] > 0

    def test_rho_call_positive(self):
        """Test that rho is positive for call options."""
        greeks = _calculate_all_greeks("call", 100.0, 100.0, 0.05, 0.0, 0.25, 0.2)

        # Call rho should be positive (benefit from higher rates)
        assert greeks["rho"] > 0

    def test_rho_put_negative(self):
        """Test that rho is negative for put options."""
        greeks = _calculate_all_greeks("put", 100.0, 100.0, 0.05, 0.0, 0.25, 0.2)

        # Put rho should be negative (hurt by higher rates)
        assert greeks["rho"] < 0

    def test_rho_itm_magnitude(self):
        """Test that rho magnitude is higher for ITM options."""
        itm_call_greeks = _calculate_all_greeks(
            "call", 120.0, 100.0, 0.05, 0.0, 0.25, 0.2
        )
        otm_call_greeks = _calculate_all_greeks(
            "call", 80.0, 100.0, 0.05, 0.0, 0.25, 0.2
        )

        # ITM call should have higher rho magnitude
        assert abs(itm_call_greeks["rho"]) > abs(otm_call_greeks["rho"])


class TestSecondOrderGreeks:
    """Test second-order Greeks calculations."""

    def test_vanna_calculation(self):
        """Test vanna (sensitivity of delta to volatility) calculation."""
        greeks = _calculate_all_greeks("call", 100.0, 100.0, 0.05, 0.0, 0.25, 0.2)

        # Vanna can be positive or negative
        assert "vanna" in greeks
        assert isinstance(greeks["vanna"], float)
        assert not math.isnan(greeks["vanna"])

    def test_charm_calculation(self):
        """Test charm (sensitivity of delta to time) calculation."""
        call_greeks = _calculate_all_greeks("call", 100.0, 100.0, 0.05, 0.0, 0.25, 0.2)
        put_greeks = _calculate_all_greeks("put", 100.0, 100.0, 0.05, 0.0, 0.25, 0.2)

        # Charm exists for both calls and puts
        assert "charm" in call_greeks
        assert "charm" in put_greeks
        assert isinstance(call_greeks["charm"], float)
        assert isinstance(put_greeks["charm"], float)

    def test_speed_calculation(self):
        """Test speed (sensitivity of gamma to underlying price) calculation."""
        greeks = _calculate_all_greeks("call", 100.0, 100.0, 0.05, 0.0, 0.25, 0.2)

        # Speed can be positive or negative
        assert "speed" in greeks
        assert isinstance(greeks["speed"], float)
        assert not math.isnan(greeks["speed"])

    def test_zomma_calculation(self):
        """Test zomma (sensitivity of gamma to volatility) calculation."""
        greeks = _calculate_all_greeks("call", 100.0, 100.0, 0.05, 0.0, 0.25, 0.2)

        # Zomma can be positive or negative
        assert "zomma" in greeks
        assert isinstance(greeks["zomma"], float)
        assert not math.isnan(greeks["zomma"])

    def test_color_calculation(self):
        """Test color (sensitivity of gamma to time) calculation."""
        greeks = _calculate_all_greeks("call", 100.0, 100.0, 0.05, 0.0, 0.25, 0.2)

        # Color is typically negative (gamma decreases with time)
        assert "color" in greeks
        assert isinstance(greeks["color"], float)
        assert not math.isnan(greeks["color"])

    def test_veta_calculation(self):
        """Test veta (sensitivity of vega to time) calculation."""
        greeks = _calculate_all_greeks("call", 100.0, 100.0, 0.05, 0.0, 0.25, 0.2)

        # Veta is typically negative (vega decreases with time)
        assert "veta" in greeks
        assert isinstance(greeks["veta"], float)
        assert not math.isnan(greeks["veta"])

    def test_vomma_calculation(self):
        """Test vomma (sensitivity of vega to volatility) calculation."""
        greeks = _calculate_all_greeks("call", 100.0, 100.0, 0.05, 0.0, 0.25, 0.2)

        # Vomma can be positive or negative
        assert "vomma" in greeks
        assert isinstance(greeks["vomma"], float)
        assert not math.isnan(greeks["vomma"])

    def test_ultima_calculation(self):
        """Test ultima (sensitivity of vomma to volatility) calculation."""
        greeks = _calculate_all_greeks("call", 100.0, 100.0, 0.05, 0.0, 0.25, 0.2)

        # Ultima is a third-order Greek
        assert "ultima" in greeks
        assert isinstance(greeks["ultima"], float)
        assert not math.isnan(greeks["ultima"])

    def test_dual_delta_call(self):
        """Test dual delta calculation for call options."""
        greeks = _calculate_all_greeks("call", 100.0, 100.0, 0.05, 0.0, 0.25, 0.2)

        # Dual delta for calls should be negative
        assert "dual_delta" in greeks
        assert greeks["dual_delta"] < 0

    def test_dual_delta_put(self):
        """Test dual delta calculation for put options."""
        greeks = _calculate_all_greeks("put", 100.0, 100.0, 0.05, 0.0, 0.25, 0.2)

        # Dual delta for puts should be positive
        assert "dual_delta" in greeks
        assert greeks["dual_delta"] > 0


class TestCalculateOptionGreeks:
    """Test the main calculate_option_greeks function."""

    def test_calculate_greeks_valid_call(self):
        """Test Greeks calculation for valid call option."""
        greeks = calculate_option_greeks(
            option_type="call",
            strike=100.0,
            underlying_price=105.0,
            days_to_expiration=30,
            option_price=7.5,
            volatility=0.25,
            dividend_yield=0.0,
        )

        # Should have all Greeks
        expected_greeks = [
            "iv",
            "delta",
            "gamma",
            "theta",
            "vega",
            "rho",
            "vanna",
            "charm",
            "speed",
            "zomma",
            "color",
            "veta",
            "vomma",
            "ultima",
            "dual_delta",
        ]

        for greek in expected_greeks:
            assert greek in greeks
            assert greeks[greek] is not None
            assert isinstance(greeks[greek], float)
            assert not math.isnan(greeks[greek])

    def test_calculate_greeks_valid_put(self):
        """Test Greeks calculation for valid put option."""
        greeks = calculate_option_greeks(
            option_type="put",
            strike=100.0,
            underlying_price=95.0,
            days_to_expiration=45,
            option_price=6.25,
            volatility=0.3,
            dividend_yield=0.02,
        )

        # Should have all Greeks with valid values
        assert greeks["iv"] is not None
        assert greeks["delta"] < 0  # Put delta is negative
        assert greeks["gamma"] > 0  # Gamma is always positive
        assert greeks["vega"] > 0  # Vega is always positive
        assert greeks["rho"] < 0  # Put rho is negative

    def test_calculate_greeks_invalid_inputs(self):
        """Test Greeks calculation with invalid inputs."""
        greeks = calculate_option_greeks(
            option_type="invalid",
            strike=100.0,
            underlying_price=105.0,
            days_to_expiration=30,
            option_price=7.5,
        )

        # Should return all None values
        for value in greeks.values():
            assert value is None

    def test_calculate_greeks_zero_days_to_expiration(self):
        """Test Greeks calculation with zero days to expiration."""
        greeks = calculate_option_greeks(
            option_type="call",
            strike=100.0,
            underlying_price=105.0,
            days_to_expiration=0,
            option_price=5.0,
        )

        # Should return all None values
        for value in greeks.values():
            assert value is None

    def test_calculate_greeks_extreme_parameters(self):
        """Test Greeks calculation with extreme but valid parameters."""
        greeks = calculate_option_greeks(
            option_type="call",
            strike=100.0,
            underlying_price=200.0,  # Deep ITM
            days_to_expiration=365,  # 1 year
            option_price=105.0,
            volatility=0.8,  # High volatility
            dividend_yield=0.05,
        )

        # Should still calculate Greeks
        assert greeks["iv"] is not None
        assert greeks["delta"] is not None
        assert 0.8 < greeks["delta"] < 1.0  # Deep ITM call delta

    def test_calculate_greeks_implied_volatility_failure(self):
        """Test Greeks calculation when implied volatility calculation fails."""
        # Use unrealistic option price that won't converge
        greeks = calculate_option_greeks(
            option_type="call",
            strike=100.0,
            underlying_price=100.0,
            days_to_expiration=30,
            option_price=0.001,  # Unrealistically low price
            volatility=0.2,
        )

        # May return None values if IV calculation fails
        if greeks["iv"] is None:
            for value in greeks.values():
                assert value is None

    def test_calculate_greeks_with_dividends(self):
        """Test Greeks calculation with dividend yield."""
        greeks_no_div = calculate_option_greeks(
            option_type="call",
            strike=100.0,
            underlying_price=100.0,
            days_to_expiration=90,
            option_price=5.0,
            dividend_yield=0.0,
        )

        greeks_with_div = calculate_option_greeks(
            option_type="call",
            strike=100.0,
            underlying_price=100.0,
            days_to_expiration=90,
            option_price=4.5,  # Lower price due to dividends
            dividend_yield=0.03,
        )

        # Dividends should affect Greeks
        if greeks_no_div["delta"] is not None and greeks_with_div["delta"] is not None:
            assert greeks_with_div["delta"] < greeks_no_div["delta"]

    def test_calculate_greeks_case_insensitive(self):
        """Test that option type is case insensitive."""
        greeks_lower = calculate_option_greeks(
            option_type="call",
            strike=100.0,
            underlying_price=105.0,
            days_to_expiration=30,
            option_price=7.5,
        )

        greeks_upper = calculate_option_greeks(
            option_type="CALL",
            strike=100.0,
            underlying_price=105.0,
            days_to_expiration=30,
            option_price=7.5,
        )

        # Should produce identical results
        for key in greeks_lower:
            assert abs(greeks_lower[key] - greeks_upper[key]) < 1e-10


class TestUpdateOptionQuoteWithGreeks:
    """Test integration with OptionQuote system."""

    def test_update_option_quote_valid_call(self):
        """Test updating option quote with Greeks for call option."""

        # Create mock option
        mock_call_option = Mock()
        mock_call_option.option_type = "call"
        mock_call_option.strike = 150.0

        option_quote = Mock(spec=OptionQuote)
        option_quote.asset = mock_call_option
        option_quote.price = 5.25
        option_quote.underlying_price = 155.0
        option_quote.days_to_expiration = 30
        option_quote.iv = 0.25
        option_quote.is_priceable.return_value = True

        # Mock isinstance to return True for Option
        with patch("app.services.greeks.isinstance", return_value=True):
            update_option_quote_with_greeks(option_quote, dividend_yield=0.0)

            # Function should complete without error
            # Verify the quote was processed
            assert option_quote.is_priceable.called

    def test_update_option_quote_valid_put(self):
        """Test updating option quote with Greeks for put option."""

        # Create mock option
        mock_put_option = Mock()
        mock_put_option.option_type = "put"
        mock_put_option.strike = 145.0

        option_quote = Mock(spec=OptionQuote)
        option_quote.asset = mock_put_option
        option_quote.price = 3.75
        option_quote.underlying_price = 150.0
        option_quote.days_to_expiration = 45
        option_quote.iv = 0.22
        option_quote.is_priceable.return_value = True

        # Mock isinstance to return True for Option
        with patch("app.services.greeks.isinstance", return_value=True):
            update_option_quote_with_greeks(option_quote, dividend_yield=0.02)

            # Function should complete without error
            assert option_quote.is_priceable.called

    def test_update_option_quote_not_priceable(self):
        """Test updating option quote that is not priceable."""
        option_quote = Mock(spec=OptionQuote)
        option_quote.is_priceable.return_value = False

        # Should return early without error
        update_option_quote_with_greeks(option_quote)

        # No Greeks should be set
        assert not hasattr(option_quote, "delta")

    def test_update_option_quote_no_underlying_price(self):
        """Test updating option quote with no underlying price."""
        option_quote = Mock(spec=OptionQuote)
        option_quote.is_priceable.return_value = True
        option_quote.underlying_price = None

        update_option_quote_with_greeks(option_quote)

        # Should return early without setting Greeks
        assert not hasattr(option_quote, "delta")

    def test_update_option_quote_no_days_to_expiration(self):
        """Test updating option quote with no days to expiration."""
        option_quote = Mock(spec=OptionQuote)
        option_quote.is_priceable.return_value = True
        option_quote.underlying_price = 150.0
        option_quote.days_to_expiration = None
        option_quote.asset = Mock()  # Add asset attribute

        update_option_quote_with_greeks(option_quote)

        # Should return early
        assert not hasattr(option_quote, "delta")

    def test_update_option_quote_zero_days_to_expiration(self):
        """Test updating option quote with zero days to expiration."""
        option_quote = Mock(spec=OptionQuote)
        option_quote.is_priceable.return_value = True
        option_quote.underlying_price = 150.0
        option_quote.days_to_expiration = 0
        option_quote.asset = Mock()  # Add asset attribute

        update_option_quote_with_greeks(option_quote)

        # Should return early
        assert not hasattr(option_quote, "delta")

    def test_update_option_quote_not_option_asset(self):
        """Test updating quote with non-option asset."""
        stock = Stock(symbol="AAPL")

        option_quote = Mock(spec=OptionQuote)
        option_quote.asset = stock  # Not an Option
        option_quote.is_priceable.return_value = True
        option_quote.underlying_price = 150.0
        option_quote.days_to_expiration = 30

        update_option_quote_with_greeks(option_quote)

        # Should return early
        assert not hasattr(option_quote, "delta")

    def test_update_option_quote_filters_nan_values(self):
        """Test that NaN Greek values are not set on the quote."""
        from datetime import date, timedelta

        call_option = Call(
            underlying=Stock(symbol="AAPL"),
            strike=150.0,
            expiration_date=date.today() + timedelta(days=30),
        )

        option_quote = Mock(spec=OptionQuote)
        option_quote.asset = call_option
        option_quote.price = 5.25
        option_quote.underlying_price = 155.0
        option_quote.days_to_expiration = 30
        option_quote.iv = 0.25
        option_quote.is_priceable.return_value = True

        # Mock calculate_option_greeks to return some NaN values
        with patch("app.services.greeks.calculate_option_greeks") as mock_calc:
            mock_calc.return_value = {
                "delta": 0.65,
                "gamma": float("nan"),  # NaN value
                "theta": -0.05,
                "vega": float("nan"),  # NaN value
                "rho": 0.25,
            }

            with patch("builtins.hasattr", return_value=True):
                call_option.option_type = "call"

                update_option_quote_with_greeks(option_quote)

                # Only non-NaN values should be set
                option_quote.__setattr__.assert_any_call("delta", 0.65)
                option_quote.__setattr__.assert_any_call("theta", -0.05)
                option_quote.__setattr__.assert_any_call("rho", 0.25)

                # NaN values should not be set
                with pytest.raises(AssertionError):
                    option_quote.__setattr__.assert_any_call("gamma", float("nan"))
                with pytest.raises(AssertionError):
                    option_quote.__setattr__.assert_any_call("vega", float("nan"))


class TestEdgeCasesAndNumericalStability:
    """Test edge cases and numerical stability."""

    def test_greeks_very_short_expiration(self):
        """Test Greeks calculation with very short time to expiration."""
        greeks = calculate_option_greeks(
            option_type="call",
            strike=100.0,
            underlying_price=100.0,
            days_to_expiration=1,  # 1 day
            option_price=1.0,
            volatility=0.2,
        )

        # Should handle short expiration without numerical issues
        if greeks["iv"] is not None:
            assert not math.isnan(greeks["delta"])
            assert not math.isnan(greeks["gamma"])
            assert not math.isnan(greeks["theta"])

    def test_greeks_very_long_expiration(self):
        """Test Greeks calculation with very long time to expiration."""
        greeks = calculate_option_greeks(
            option_type="call",
            strike=100.0,
            underlying_price=100.0,
            days_to_expiration=1825,  # 5 years
            option_price=25.0,
            volatility=0.2,
        )

        # Should handle long expiration without numerical issues
        assert greeks["iv"] is not None
        assert not math.isnan(greeks["delta"])
        assert not math.isnan(greeks["gamma"])

    def test_greeks_extreme_volatility(self):
        """Test Greeks calculation with extreme volatility."""
        # High volatility
        greeks_high_vol = calculate_option_greeks(
            option_type="call",
            strike=100.0,
            underlying_price=100.0,
            days_to_expiration=30,
            option_price=15.0,
            volatility=1.5,  # 150% volatility
        )

        if greeks_high_vol["iv"] is not None:
            assert not math.isnan(greeks_high_vol["delta"])
            assert greeks_high_vol["vega"] > 0

    def test_greeks_extreme_moneyness(self):
        """Test Greeks calculation with extreme moneyness."""
        # Deep ITM call
        greeks_deep_itm = calculate_option_greeks(
            option_type="call",
            strike=50.0,
            underlying_price=200.0,
            days_to_expiration=30,
            option_price=152.0,
            volatility=0.2,
        )

        if greeks_deep_itm["iv"] is not None:
            assert greeks_deep_itm["delta"] > 0.95  # Should be close to 1
            assert greeks_deep_itm["gamma"] > 0  # Should be positive but small

    def test_greeks_zero_interest_rate(self):
        """Test Greeks calculation with zero interest rate."""
        greeks = calculate_option_greeks(
            option_type="call",
            strike=100.0,
            underlying_price=100.0,
            days_to_expiration=30,
            option_price=5.0,
            volatility=0.2,
        )

        # Should work with zero interest rate (default in function)
        assert greeks["rho"] is not None

    def test_greeks_precision_consistency(self):
        """Test that Greeks calculations are consistent across multiple calls."""
        params = {
            "option_type": "call",
            "strike": 100.0,
            "underlying_price": 105.0,
            "days_to_expiration": 30,
            "option_price": 7.5,
            "volatility": 0.25,
        }

        greeks1 = calculate_option_greeks(**params)
        greeks2 = calculate_option_greeks(**params)
        greeks3 = calculate_option_greeks(**params)

        # Results should be identical
        for key in greeks1:
            if greeks1[key] is not None:
                assert abs(greeks1[key] - greeks2[key]) < 1e-15
                assert abs(greeks1[key] - greeks3[key]) < 1e-15

    def test_error_handling_overflow(self):
        """Test error handling for potential overflow conditions."""
        # Try to create conditions that might cause overflow
        try:
            greeks = calculate_option_greeks(
                option_type="call",
                strike=1e-10,  # Very small strike
                underlying_price=1e10,  # Very large underlying
                days_to_expiration=365 * 10,  # 10 years
                option_price=1e9,
                volatility=10.0,  # Very high volatility
            )

            # If it succeeds, Greeks should be finite
            for _key, value in greeks.items():
                if value is not None:
                    assert math.isfinite(value)

        except (OverflowError, ValueError, ZeroDivisionError):
            # These errors are acceptable for extreme inputs
            pass

    def test_error_handling_underflow(self):
        """Test error handling for potential underflow conditions."""
        try:
            greeks = calculate_option_greeks(
                option_type="put",
                strike=1e10,  # Very large strike
                underlying_price=1e-10,  # Very small underlying
                days_to_expiration=1,
                option_price=1e10,
                volatility=1e-10,  # Very small volatility
            )

            # If it succeeds, Greeks should be finite
            for _key, value in greeks.items():
                if value is not None:
                    assert math.isfinite(value)

        except (OverflowError, ValueError, ZeroDivisionError):
            # These errors are acceptable for extreme inputs
            pass
