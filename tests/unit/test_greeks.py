"""
Comprehensive tests for Greeks calculations - Phase 5.1 implementation.
Tests Black-Scholes accuracy, implied volatility convergence, edge cases, and performance.
"""

import pytest
from decimal import Decimal
import math
from app.services.greeks import (
    calculate_option_greeks, 
    black_scholes_call, 
    black_scholes_put,
    calculate_implied_volatility,
    norm_cdf,
    norm_pdf
)


class TestBlackScholesAccuracy:
    """Test Black-Scholes calculations against known reference values."""
    
    def test_black_scholes_call_reference_values(self):
        """Test call option pricing against known accurate values."""
        # Reference case: S=100, K=100, T=0.25, r=0.05, σ=0.20
        S = 100.0
        K = 100.0
        T = 0.25  # 3 months
        r = 0.05
        sigma = 0.20
        q = 0.0
        
        call_price = black_scholes_call(S, K, T, r, sigma, q)
        
        # Expected value from standard Black-Scholes references
        expected = 2.533  # Approximate value
        assert abs(call_price - expected) < 0.01, f"Expected ~{expected}, got {call_price}"
        
    def test_black_scholes_put_reference_values(self):
        """Test put option pricing against known accurate values."""
        # Same parameters as call test
        S = 100.0
        K = 100.0
        T = 0.25
        r = 0.05
        sigma = 0.20
        q = 0.0
        
        put_price = black_scholes_put(S, K, T, r, sigma, q)
        
        # Expected value using put-call parity verification
        call_price = black_scholes_call(S, K, T, r, sigma, q)
        expected_put = call_price - S + K * math.exp(-r * T)
        
        assert abs(put_price - expected_put) < 0.001, "Put-call parity violation"
        
    def test_atm_option_symmetry(self):
        """Test that ATM options have expected symmetry properties."""
        S = K = 100.0
        T = 0.25
        r = 0.05
        sigma = 0.20
        q = 0.0
        
        greeks_call = calculate_option_greeks("call", K, S, int(T * 365), None, r, q, sigma)
        greeks_put = calculate_option_greeks("put", K, S, int(T * 365), None, r, q, sigma)
        
        # For ATM options: call_delta ≈ 0.5, put_delta ≈ -0.5
        assert abs(greeks_call["delta"] - 0.5) < 0.05
        assert abs(greeks_put["delta"] + 0.5) < 0.05
        
        # Gamma should be the same for calls and puts
        assert abs(greeks_call["gamma"] - greeks_put["gamma"]) < 0.001
        
        # Theta should have expected relationship (puts more negative for same strike)
        assert greeks_put["theta"] < greeks_call["theta"]


class TestImpliedVolatilityConvergence:
    """Test implied volatility Newton-Raphson convergence."""
    
    def test_iv_convergence_standard_case(self):
        """Test IV convergence for standard market conditions."""
        S = 100.0
        K = 105.0  # Slightly OTM call
        T = 0.5  # 6 months
        r = 0.03
        q = 0.0
        option_type = "call"
        
        # Generate a theoretical price with known IV
        known_iv = 0.25
        theoretical_price = black_scholes_call(S, K, T, r, known_iv, q)
        
        # Calculate IV from the price
        calculated_iv = calculate_implied_volatility(
            option_type, theoretical_price, S, K, T, r, q
        )
        
        assert abs(calculated_iv - known_iv) < 0.001, f"IV convergence failed: expected {known_iv}, got {calculated_iv}"
        
    def test_iv_convergence_deep_itm(self):
        """Test IV convergence for deep ITM options."""
        S = 120.0
        K = 100.0  # Deep ITM call
        T = 0.25
        r = 0.02
        q = 0.0
        
        known_iv = 0.30
        theoretical_price = black_scholes_call(S, K, T, r, known_iv, q)
        
        calculated_iv = calculate_implied_volatility("call", theoretical_price, S, K, T, r, q)
        assert abs(calculated_iv - known_iv) < 0.005
        
    def test_iv_convergence_deep_otm(self):
        """Test IV convergence for deep OTM options."""
        S = 100.0
        K = 130.0  # Deep OTM call
        T = 0.1  # Short time to expiration
        r = 0.02
        q = 0.0
        
        known_iv = 0.40  # High volatility needed for OTM options to have value
        theoretical_price = black_scholes_call(S, K, T, r, known_iv, q)
        
        # OTM options with short time may have convergence challenges
        if theoretical_price > 0.01:  # Only test if option has meaningful value
            calculated_iv = calculate_implied_volatility("call", theoretical_price, S, K, T, r, q)
            assert abs(calculated_iv - known_iv) < 0.01
            
    def test_iv_non_convergence_handling(self):
        """Test handling of cases where IV cannot converge."""
        # Price too low for the given parameters
        very_low_price = 0.001
        calculated_iv = calculate_implied_volatility("call", very_low_price, 100, 120, 0.01, 0.02, 0.0)
        
        # Should return a reasonable minimum value rather than failing
        assert calculated_iv is not None
        assert calculated_iv > 0


class TestGreeksEdgeCases:
    """Test Greeks calculations in edge cases and extreme market conditions."""
    
    def test_zero_dte_options(self):
        """Test Greeks for zero days to expiration."""
        greeks = calculate_option_greeks(
            option_type="call",
            strike=100.0,
            underlying_price=105.0,  # ITM
            days_to_expiration=0,
            option_price=5.0,  # Intrinsic value
            risk_free_rate=0.05,
            dividend_yield=0.0
        )
        
        # Zero DTE ITM call should have delta ≈ 1, gamma ≈ 0, theta ≈ 0
        assert greeks["delta"] > 0.95
        assert abs(greeks["gamma"]) < 0.1
        assert abs(greeks["theta"]) < 0.1
        
    def test_deep_itm_call_greeks(self):
        """Test Greeks for deep ITM call options."""
        greeks = calculate_option_greeks(
            option_type="call",
            strike=80.0,
            underlying_price=120.0,  # Deep ITM
            days_to_expiration=30,
            option_price=40.5,
            risk_free_rate=0.05,
            dividend_yield=0.0
        )
        
        # Deep ITM call should have high delta, low gamma
        assert greeks["delta"] > 0.9
        assert greeks["gamma"] < 0.05
        
    def test_deep_otm_put_greeks(self):
        """Test Greeks for deep OTM put options."""
        greeks = calculate_option_greeks(
            option_type="put",
            strike=80.0,
            underlying_price=120.0,  # Deep OTM put
            days_to_expiration=30,
            option_price=0.1,
            risk_free_rate=0.05,
            dividend_yield=0.0
        )
        
        # Deep OTM put should have delta ≈ 0, low gamma
        assert abs(greeks["delta"]) < 0.1
        assert greeks["gamma"] < 0.05
        
    def test_negative_rates_environment(self):
        """Test Greeks in negative interest rate environment."""
        greeks = calculate_option_greeks(
            option_type="call",
            strike=100.0,
            underlying_price=100.0,
            days_to_expiration=90,
            option_price=3.0,
            risk_free_rate=-0.01,  # Negative rates
            dividend_yield=0.0
        )
        
        # Should still produce reasonable Greeks
        assert 0 < greeks["delta"] < 1
        assert greeks["gamma"] > 0
        assert greeks["rho"] is not None
        
    def test_high_dividend_yield(self):
        """Test Greeks with high dividend yield."""
        greeks = calculate_option_greeks(
            option_type="call",
            strike=100.0,
            underlying_price=100.0,
            days_to_expiration=180,
            option_price=2.0,
            risk_free_rate=0.03,
            dividend_yield=0.06  # High dividend yield
        )
        
        # High dividend yield should reduce call delta, increase put delta
        assert greeks["delta"] < 0.5  # Lower than typical ATM delta


class TestAdvancedGreeks:
    """Test second-order and advanced Greeks calculations."""
    
    def test_second_order_greeks_presence(self):
        """Test that all advanced Greeks are calculated."""
        greeks = calculate_option_greeks(
            option_type="call",
            strike=100.0,
            underlying_price=100.0,
            days_to_expiration=60,
            option_price=4.0,
            risk_free_rate=0.04,
            dividend_yield=0.02
        )
        
        # Verify advanced Greeks are present
        advanced_greeks = [
            "charm", "vanna", "speed", "zomma", "color", 
            "veta", "vomma", "ultima", "dual_delta"
        ]
        
        for greek in advanced_greeks:
            assert greek in greeks, f"Missing advanced Greek: {greek}"
            assert greeks[greek] is not None, f"Null value for Greek: {greek}"
            
    def test_greeks_mathematical_relationships(self):
        """Test mathematical relationships between Greeks."""
        greeks = calculate_option_greeks(
            option_type="call",
            strike=100.0,
            underlying_price=100.0,
            days_to_expiration=45,
            option_price=3.5,
            risk_free_rate=0.05,
            dividend_yield=0.0
        )
        
        # Gamma should be positive for both calls and puts
        assert greeks["gamma"] > 0
        
        # Vega should be positive for both calls and puts
        assert greeks["vega"] > 0
        
        # For ATM options, charm should be approximately -delta * theta / underlying
        # (This is an approximation, not exact)
        expected_charm_magnitude = abs(greeks["delta"] * greeks["theta"] / 100)
        assert abs(greeks["charm"]) < expected_charm_magnitude * 10  # Loose bounds check


class TestGreeksPerformance:
    """Test performance characteristics of Greeks calculations."""
    
    def test_single_calculation_performance(self):
        """Test that single Greeks calculation is fast enough."""
        import time
        
        start_time = time.time()
        
        greeks = calculate_option_greeks(
            option_type="call",
            strike=100.0,
            underlying_price=100.0,
            days_to_expiration=30,
            option_price=3.0,
            risk_free_rate=0.05,
            dividend_yield=0.0
        )
        
        end_time = time.time()
        calculation_time = end_time - start_time
        
        # Single calculation should be very fast
        assert calculation_time < 0.01, f"Greeks calculation too slow: {calculation_time:.4f}s"
        assert len(greeks) >= 10  # Should have all major Greeks
        
    def test_bulk_calculation_performance(self):
        """Test performance for bulk Greeks calculations."""
        import time
        
        # Parameters for 100 different options
        test_cases = [
            {
                "option_type": "call" if i % 2 == 0 else "put",
                "strike": 95.0 + i,
                "underlying_price": 100.0,
                "days_to_expiration": 30 + i,
                "option_price": 2.0 + i * 0.1,
                "risk_free_rate": 0.05,
                "dividend_yield": 0.0
            }
            for i in range(100)
        ]
        
        start_time = time.time()
        
        results = []
        for params in test_cases:
            greeks = calculate_option_greeks(**params)
            results.append(greeks)
            
        end_time = time.time()
        total_time = end_time - start_time
        
        # 100 calculations should complete reasonably quickly
        assert total_time < 1.0, f"Bulk calculations too slow: {total_time:.2f}s for 100 calculations"
        assert len(results) == 100


class TestGreeksValidation:
    """Test validation and error handling in Greeks calculations."""
    
    def test_invalid_option_type(self):
        """Test handling of invalid option type."""
        with pytest.raises(ValueError, match="option_type must be 'call' or 'put'"):
            calculate_option_greeks(
                option_type="invalid",
                strike=100.0,
                underlying_price=100.0,
                days_to_expiration=30,
                option_price=3.0,
                risk_free_rate=0.05,
                dividend_yield=0.0
            )
            
    def test_negative_underlying_price(self):
        """Test handling of negative underlying price."""
        with pytest.raises(ValueError, match="Underlying price must be positive"):
            calculate_option_greeks(
                option_type="call",
                strike=100.0,
                underlying_price=-10.0,
                days_to_expiration=30,
                option_price=3.0,
                risk_free_rate=0.05,
                dividend_yield=0.0
            )
            
    def test_negative_strike_price(self):
        """Test handling of negative strike price."""
        with pytest.raises(ValueError, match="Strike price must be positive"):
            calculate_option_greeks(
                option_type="call",
                strike=-100.0,
                underlying_price=100.0,
                days_to_expiration=30,
                option_price=3.0,
                risk_free_rate=0.05,
                dividend_yield=0.0
            )
            
    def test_negative_option_price(self):
        """Test handling of negative option price."""
        with pytest.raises(ValueError, match="Option price must be non-negative"):
            calculate_option_greeks(
                option_type="call",
                strike=100.0,
                underlying_price=100.0,
                days_to_expiration=30,
                option_price=-1.0,
                risk_free_rate=0.05,
                dividend_yield=0.0
            )


# Backward compatibility tests for existing functionality
def test_calculate_option_greeks_call():
    """Tests the calculate_option_greeks function for a call option."""
    greeks = calculate_option_greeks(
        option_type="call",
        strike=150.0,
        underlying_price=150.0,
        days_to_expiration=30,
        option_price=2.18,
        risk_free_rate=0.01,
        dividend_yield=0.0,
    )
    assert greeks["iv"] is not None
    assert greeks["delta"] is not None
    assert abs(greeks["delta"] - 0.5) < 0.1

def test_calculate_option_greeks_put():
    """Tests the calculate_option_greeks function for a put option."""
    greeks = calculate_option_greeks(
        option_type="put",
        strike=150.0,
        underlying_price=150.0,
        days_to_expiration=30,
        option_price=2.18,
        risk_free_rate=0.01,
        dividend_yield=0.0,
    )
    assert greeks["iv"] is not None
    assert greeks["delta"] is not None
    assert abs(greeks["delta"] + 0.5) < 0.1
