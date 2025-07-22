"""
Advanced tests for quote models.

Comprehensive test coverage for quote classes including Quote, OptionQuote, 
OptionsChain, quote factory patterns, validation, Greeks calculation,
and market data analysis functionality.
"""

from datetime import date, datetime, timedelta
from typing import Any

import pytest

from app.models.assets import Call, Option, Put, Stock, asset_factory
from app.models.quotes import (
    GreeksResponse,
    OptionQuote,
    OptionsChain,
    OptionsChainResponse,
    Quote,
    QuoteResponse,
    quote_factory,
)


class TestQuoteFactory:
    """Test the quote factory function."""

    def test_quote_factory_stock_quote(self):
        """Test quote factory creates Stock quote."""
        quote_date = datetime.now()
        result = quote_factory(
            quote_date=quote_date,
            asset="AAPL",
            price=150.0,
            bid=149.5,
            ask=150.5
        )
        
        assert isinstance(result, Quote)
        assert not isinstance(result, OptionQuote)
        assert result.asset.symbol == "AAPL"
        assert result.price == 150.0

    def test_quote_factory_option_quote(self):
        """Test quote factory creates OptionQuote."""
        quote_date = datetime.now()
        result = quote_factory(
            quote_date=quote_date,
            asset="AAPL240119C00195000",
            price=5.25,
            bid=5.0,
            ask=5.5,
            underlying_price=200.0
        )
        
        assert isinstance(result, OptionQuote)
        assert result.asset.symbol == "AAPL240119C00195000"
        assert result.underlying_price == 200.0

    def test_quote_factory_with_asset_object(self):
        """Test quote factory with Asset object."""
        stock = Stock("GOOGL")
        quote_date = datetime.now()
        
        result = quote_factory(
            quote_date=quote_date,
            asset=stock,
            price=2800.0
        )
        
        assert isinstance(result, Quote)
        assert result.asset is stock

    def test_quote_factory_date_normalization(self):
        """Test quote factory normalizes different date types."""
        # String date
        result1 = quote_factory(
            quote_date="2024-03-15T10:30:00Z",
            asset="AAPL",
            price=150.0
        )
        assert isinstance(result1.quote_date, datetime)
        
        # Date object
        date_obj = date(2024, 3, 15)
        result2 = quote_factory(
            quote_date=date_obj,
            asset="AAPL",
            price=150.0
        )
        assert isinstance(result2.quote_date, datetime)
        assert result2.quote_date.date() == date_obj

    def test_quote_factory_invalid_asset(self):
        """Test quote factory with invalid asset."""
        with pytest.raises(ValueError, match="Could not create asset"):
            quote_factory(
                quote_date=datetime.now(),
                asset=None,
                price=100.0
            )


class TestQuote:
    """Test the base Quote class."""

    def test_quote_creation_basic(self):
        """Test basic quote creation."""
        asset = Stock("AAPL")
        quote_date = datetime.now()
        
        quote = Quote(
            asset=asset,
            quote_date=quote_date,
            price=150.0,
            bid=149.5,
            ask=150.5,
            volume=1000000
        )
        
        assert quote.asset == asset
        assert quote.quote_date == quote_date
        assert quote.price == 150.0
        assert quote.bid == 149.5
        assert quote.ask == 150.5
        assert quote.volume == 1000000

    def test_quote_asset_normalization(self):
        """Test quote asset normalization from string."""
        quote = Quote(
            asset="GOOGL",
            quote_date=datetime.now(),
            price=2800.0
        )
        
        assert isinstance(quote.asset, Stock)
        assert quote.asset.symbol == "GOOGL"

    def test_quote_asset_normalization_invalid(self):
        """Test quote asset normalization with invalid string."""
        with pytest.raises(ValueError, match="Could not create asset"):
            Quote(
                asset="",
                quote_date=datetime.now(),
                price=100.0
            )

    def test_quote_date_normalization(self):
        """Test quote date normalization."""
        # String date
        quote1 = Quote(
            asset="AAPL",
            quote_date="2024-03-15T10:30:00Z",
            price=150.0
        )
        assert isinstance(quote1.quote_date, datetime)
        
        # Date object
        date_obj = date(2024, 3, 15)
        quote2 = Quote(
            asset="AAPL",
            quote_date=date_obj,
            price=150.0
        )
        assert isinstance(quote2.quote_date, datetime)
        assert quote2.quote_date.date() == date_obj

    def test_quote_price_calculation_from_bid_ask(self):
        """Test price calculation when not provided."""
        quote = Quote(
            asset="AAPL",
            quote_date=datetime.now(),
            bid=149.5,
            ask=150.5
            # price not provided
        )
        
        # Should calculate midpoint
        assert quote.price == 150.0

    def test_quote_price_provided_overrides_calculation(self):
        """Test that provided price overrides calculation."""
        quote = Quote(
            asset="AAPL",
            quote_date=datetime.now(),
            price=151.0,  # Explicitly provided
            bid=149.5,
            ask=150.5
        )
        
        # Should use provided price, not calculated midpoint
        assert quote.price == 151.0

    def test_quote_properties(self):
        """Test quote properties."""
        asset = Stock("TSLA")
        quote = Quote(
            asset=asset,
            quote_date=datetime.now(),
            bid=800.0,
            ask=801.0,
            price=800.5
        )
        
        assert quote.symbol == "TSLA"
        assert quote.spread == 1.0  # 801.0 - 800.0
        assert quote.midpoint == 800.5  # (800.0 + 801.0) / 2

    def test_quote_is_priceable(self):
        """Test is_priceable method."""
        # Valid price
        quote1 = Quote(
            asset="AAPL",
            quote_date=datetime.now(),
            price=150.0
        )
        assert quote1.is_priceable() is True
        
        # Zero price
        quote2 = Quote(
            asset="AAPL",
            quote_date=datetime.now(),
            price=0.0
        )
        assert quote2.is_priceable() is False
        
        # None price
        quote3 = Quote(
            asset="AAPL",
            quote_date=datetime.now(),
            price=None
        )
        assert quote3.is_priceable() is False

    def test_quote_validation_constraints(self):
        """Test quote validation constraints."""
        # Negative bid should fail
        with pytest.raises(ValueError):
            Quote(
                asset="AAPL",
                quote_date=datetime.now(),
                bid=-1.0
            )
        
        # Negative ask should fail
        with pytest.raises(ValueError):
            Quote(
                asset="AAPL",
                quote_date=datetime.now(),
                ask=-1.0
            )
        
        # Negative volume should fail
        with pytest.raises(ValueError):
            Quote(
                asset="AAPL",
                quote_date=datetime.now(),
                volume=-100
            )

    def test_quote_optional_greeks(self):
        """Test quote with optional Greeks fields."""
        quote = Quote(
            asset="AAPL",
            quote_date=datetime.now(),
            price=150.0,
            delta=0.5,
            gamma=0.02,
            theta=-0.05,
            vega=0.3,
            rho=0.1
        )
        
        assert quote.delta == 0.5
        assert quote.gamma == 0.02
        assert quote.theta == -0.05
        assert quote.vega == 0.3
        assert quote.rho == 0.1

    def test_quote_edge_cases(self):
        """Test quote edge cases."""
        # Zero bid/ask but no error (edge case for some markets)
        quote = Quote(
            asset="PENNY",
            quote_date=datetime.now(),
            bid=0.0,
            ask=0.0
        )
        assert quote.spread == 0.0
        assert quote.midpoint == 0.0


class TestOptionQuote:
    """Test the OptionQuote class."""

    def test_option_quote_creation(self):
        """Test option quote creation."""
        option = Call(underlying="AAPL", strike=150.0, expiration_date=date.today() + timedelta(days=30))
        
        quote = OptionQuote(
            asset=option,
            quote_date=datetime.now(),
            price=5.25,
            bid=5.0,
            ask=5.5,
            underlying_price=155.0,
            delta=0.6,
            gamma=0.02,
            theta=-0.05,
            vega=0.3,
            iv=0.25
        )
        
        assert isinstance(quote, OptionQuote)
        assert isinstance(quote, Quote)
        assert quote.underlying_price == 155.0
        assert quote.delta == 0.6
        assert quote.iv == 0.25

    def test_option_quote_validation_non_option_asset(self):
        """Test OptionQuote validation with non-option asset."""
        stock = Stock("AAPL")
        
        with pytest.raises(ValueError, match="OptionQuote requires an Option asset"):
            OptionQuote(
                asset=stock,
                quote_date=datetime.now(),
                price=150.0
            )

    def test_option_quote_advanced_greeks(self):
        """Test option quote with advanced Greeks."""
        option = Put(underlying="SPY", strike=450.0, expiration_date=date.today() + timedelta(days=15))
        
        quote = OptionQuote(
            asset=option,
            quote_date=datetime.now(),
            price=2.5,
            underlying_price=455.0,
            vanna=0.15,
            charm=0.01,
            speed=0.005,
            zomma=0.02,
            color=0.001,
            veta=0.1,
            vomma=0.05,
            ultima=0.02,
            dual_delta=0.4
        )
        
        assert quote.vanna == 0.15
        assert quote.charm == 0.01
        assert quote.speed == 0.005
        assert quote.zomma == 0.02
        assert quote.color == 0.001
        assert quote.veta == 0.1
        assert quote.vomma == 0.05
        assert quote.ultima == 0.02
        assert quote.dual_delta == 0.4

    def test_option_quote_market_data(self):
        """Test option quote with market data fields."""
        option = Option(symbol="QQQ240315C00400000")
        
        quote = OptionQuote(
            asset=option,
            quote_date=datetime.now(),
            price=3.0,
            volume=500,
            open_interest=1200,
            bid_size=10,
            ask_size=15
        )
        
        assert quote.volume == 500
        assert quote.open_interest == 1200
        assert quote.bid_size == 10
        assert quote.ask_size == 15

    def test_option_quote_properties(self):
        """Test option quote derived properties."""
        exp_date = date.today() + timedelta(days=21)
        option = Call(underlying="NVDA", strike=900.0, expiration_date=exp_date)
        quote_date = datetime.now()
        
        quote = OptionQuote(
            asset=option,
            quote_date=quote_date,
            price=25.0,
            underlying_price=950.0
        )
        
        assert quote.days_to_expiration == 21
        assert quote.strike == 900.0
        assert quote.expiration_date == exp_date
        assert quote.option_type == "call"

    def test_option_quote_has_greeks(self):
        """Test has_greeks method."""
        option = Option(symbol="AAPL240119C00150000")
        
        # Without IV
        quote1 = OptionQuote(
            asset=option,
            quote_date=datetime.now(),
            price=5.0
        )
        assert quote1.has_greeks() is False
        
        # With IV
        quote2 = OptionQuote(
            asset=option,
            quote_date=datetime.now(),
            price=5.0,
            iv=0.3
        )
        assert quote2.has_greeks() is True

    def test_option_quote_intrinsic_value(self):
        """Test intrinsic value calculation."""
        call_option = Call(underlying="AAPL", strike=150.0, expiration_date=date.today())
        
        quote = OptionQuote(
            asset=call_option,
            quote_date=datetime.now(),
            price=8.0,
            underlying_price=155.0
        )
        
        # Using stored underlying price
        assert quote.get_intrinsic_value() == 5.0
        
        # Using provided underlying price
        assert quote.get_intrinsic_value(160.0) == 10.0

    def test_option_quote_extrinsic_value(self):
        """Test extrinsic value calculation."""
        put_option = Put(underlying="SPY", strike=450.0, expiration_date=date.today())
        
        quote = OptionQuote(
            asset=put_option,
            quote_date=datetime.now(),
            price=8.0,
            underlying_price=445.0  # Put is ITM by $5
        )
        
        # Intrinsic = 5.0, Extrinsic = 8.0 - 5.0 = 3.0
        assert quote.get_extrinsic_value() == 3.0

    def test_option_quote_edge_cases(self):
        """Test option quote edge cases."""
        option = Option(symbol="TEST240119C00100000")
        
        # No underlying price - should return 0 for intrinsic/extrinsic
        quote = OptionQuote(
            asset=option,
            quote_date=datetime.now(),
            price=5.0
        )
        
        assert quote.get_intrinsic_value() == 0.0
        assert quote.get_extrinsic_value() == 0.0

    def test_option_quote_greeks_calculation_attempt(self):
        """Test that OptionQuote attempts Greeks calculation if conditions are met."""
        option = Call(underlying="AAPL", strike=150.0, expiration_date=date.today() + timedelta(days=30))
        
        # This should attempt to calculate Greeks (but will gracefully fail without service)
        quote = OptionQuote(
            asset=option,
            quote_date=datetime.now(),
            price=5.0,
            underlying_price=155.0
        )
        
        # Should not raise error even if Greeks calculation fails
        assert quote.price == 5.0
        assert quote.underlying_price == 155.0


class TestQuoteResponse:
    """Test QuoteResponse wrapper."""

    def test_quote_response_creation(self):
        """Test quote response creation."""
        quote = Quote(
            asset="AAPL",
            quote_date=datetime.now(),
            price=150.0
        )
        
        response = QuoteResponse(
            quote=quote,
            data_source="test_adapter",
            cached=True,
            cache_age_seconds=300
        )
        
        assert response.quote == quote
        assert response.data_source == "test_adapter"
        assert response.cached is True
        assert response.cache_age_seconds == 300

    def test_quote_response_with_option_quote(self):
        """Test quote response with option quote."""
        option_quote = OptionQuote(
            asset=Option(symbol="AAPL240119C00150000"),
            quote_date=datetime.now(),
            price=5.0
        )
        
        response = QuoteResponse(
            quote=option_quote,
            data_source="robinhood",
            cached=False
        )
        
        assert isinstance(response.quote, OptionQuote)
        assert response.data_source == "robinhood"
        assert response.cached is False


class TestOptionsChain:
    """Test OptionsChain class."""

    def test_options_chain_creation(self):
        """Test options chain creation."""
        exp_date = date.today() + timedelta(days=30)
        quote_time = datetime.now()
        
        # Create sample option quotes
        call1 = OptionQuote(
            asset=Call(underlying="AAPL", strike=145.0, expiration_date=exp_date),
            quote_date=quote_time,
            price=7.5,
            underlying_price=150.0
        )
        call2 = OptionQuote(
            asset=Call(underlying="AAPL", strike=150.0, expiration_date=exp_date),
            quote_date=quote_time,
            price=5.0,
            underlying_price=150.0
        )
        put1 = OptionQuote(
            asset=Put(underlying="AAPL", strike=145.0, expiration_date=exp_date),
            quote_date=quote_time,
            price=2.0,
            underlying_price=150.0
        )
        
        chain = OptionsChain(
            underlying_symbol="AAPL",
            expiration_date=exp_date,
            underlying_price=150.0,
            calls=[call1, call2],
            puts=[put1],
            quote_time=quote_time
        )
        
        assert chain.underlying_symbol == "AAPL"
        assert chain.underlying_price == 150.0
        assert len(chain.calls) == 2
        assert len(chain.puts) == 1
        assert len(chain.all_options) == 3

    def test_options_chain_get_strikes(self):
        """Test get_strikes method."""
        exp_date = date.today() + timedelta(days=30)
        
        calls = [
            OptionQuote(
                asset=Call(underlying="SPY", strike=440.0, expiration_date=exp_date),
                quote_date=datetime.now(),
                price=10.0
            ),
            OptionQuote(
                asset=Call(underlying="SPY", strike=450.0, expiration_date=exp_date),
                quote_date=datetime.now(),
                price=5.0
            ),
        ]
        
        puts = [
            OptionQuote(
                asset=Put(underlying="SPY", strike=445.0, expiration_date=exp_date),
                quote_date=datetime.now(),
                price=3.0
            ),
        ]
        
        chain = OptionsChain(
            underlying_symbol="SPY",
            expiration_date=exp_date,
            calls=calls,
            puts=puts
        )
        
        strikes = chain.get_strikes()
        assert strikes == [440.0, 445.0, 450.0]  # Sorted

    def test_options_chain_get_options_by_strike(self):
        """Test get options by strike methods."""
        exp_date = date.today() + timedelta(days=15)
        
        call = OptionQuote(
            asset=Call(underlying="QQQ", strike=380.0, expiration_date=exp_date),
            quote_date=datetime.now(),
            price=8.0
        )
        put = OptionQuote(
            asset=Put(underlying="QQQ", strike=380.0, expiration_date=exp_date),
            quote_date=datetime.now(),
            price=5.0
        )
        
        chain = OptionsChain(
            underlying_symbol="QQQ",
            expiration_date=exp_date,
            calls=[call],
            puts=[put]
        )
        
        calls_380 = chain.get_calls_by_strike(380.0)
        puts_380 = chain.get_puts_by_strike(380.0)
        
        assert len(calls_380) == 1
        assert calls_380[0] == call
        assert len(puts_380) == 1
        assert puts_380[0] == put

    def test_options_chain_filter_by_strike_range(self):
        """Test filter by strike range."""
        exp_date = date.today() + timedelta(days=30)
        
        # Create options at different strikes
        options_data = [
            (Call, 140.0, 12.0),
            (Call, 145.0, 8.0),
            (Call, 150.0, 5.0),
            (Call, 155.0, 3.0),
            (Put, 145.0, 3.0),
            (Put, 150.0, 5.0),
        ]
        
        calls = []
        puts = []
        
        for option_class, strike, price in options_data:
            quote = OptionQuote(
                asset=option_class(underlying="AAPL", strike=strike, expiration_date=exp_date),
                quote_date=datetime.now(),
                price=price
            )
            if option_class == Call:
                calls.append(quote)
            else:
                puts.append(quote)
        
        chain = OptionsChain(
            underlying_symbol="AAPL",
            expiration_date=exp_date,
            calls=calls,
            puts=puts
        )
        
        # Filter to strikes 145-150
        filtered = chain.filter_by_strike_range(145.0, 150.0)
        
        assert len(filtered.calls) == 2  # 145, 150
        assert len(filtered.puts) == 2   # 145, 150
        
        filtered_strikes = filtered.get_strikes()
        assert 140.0 not in filtered_strikes
        assert 155.0 not in filtered_strikes
        assert 145.0 in filtered_strikes
        assert 150.0 in filtered_strikes

    def test_options_chain_filter_by_moneyness(self):
        """Test filter by moneyness."""
        exp_date = date.today() + timedelta(days=20)
        underlying_price = 150.0
        
        # Create wide range of strikes
        strikes = [130.0, 140.0, 145.0, 150.0, 155.0, 160.0, 170.0]
        calls = []
        
        for strike in strikes:
            call = OptionQuote(
                asset=Call(underlying="AAPL", strike=strike, expiration_date=exp_date),
                quote_date=datetime.now(),
                price=max(underlying_price - strike + 5, 1.0)  # Rough pricing
            )
            calls.append(call)
        
        chain = OptionsChain(
            underlying_symbol="AAPL",
            expiration_date=exp_date,
            underlying_price=underlying_price,
            calls=calls
        )
        
        # Filter to 20% moneyness around 150
        # Should include strikes from 120 to 180, but we only have 130-170
        filtered = chain.filter_by_moneyness(0.2)
        
        # All our strikes should be included since they're within 20%
        assert len(filtered.calls) == len(calls)

    def test_options_chain_get_atm_options(self):
        """Test get at-the-money options."""
        exp_date = date.today() + timedelta(days=30)
        underlying_price = 150.0
        
        # Create options around ATM
        strikes = [148.0, 149.0, 150.0, 151.0, 152.0]
        calls = []
        puts = []
        
        for strike in strikes:
            call = OptionQuote(
                asset=Call(underlying="AAPL", strike=strike, expiration_date=exp_date),
                quote_date=datetime.now(),
                price=5.0
            )
            put = OptionQuote(
                asset=Put(underlying="AAPL", strike=strike, expiration_date=exp_date),
                quote_date=datetime.now(),
                price=5.0
            )
            calls.append(call)
            puts.append(put)
        
        chain = OptionsChain(
            underlying_symbol="AAPL",
            expiration_date=exp_date,
            underlying_price=underlying_price,
            calls=calls,
            puts=puts
        )
        
        # Get ATM with 2% tolerance (148-152)
        atm_options = chain.get_atm_options(tolerance=0.02)
        
        # All options should be ATM within tolerance
        assert len(atm_options["calls"]) == 5
        assert len(atm_options["puts"]) == 5

    def test_options_chain_get_itm_otm_options(self):
        """Test get ITM/OTM options."""
        exp_date = date.today() + timedelta(days=30)
        underlying_price = 150.0
        
        call_strikes = [140.0, 145.0, 150.0, 155.0, 160.0]  # ITM: <150, OTM: >150
        put_strikes = [140.0, 145.0, 150.0, 155.0, 160.0]   # ITM: >150, OTM: <150
        
        calls = [
            OptionQuote(
                asset=Call(underlying="AAPL", strike=strike, expiration_date=exp_date),
                quote_date=datetime.now(),
                price=5.0
            ) for strike in call_strikes
        ]
        
        puts = [
            OptionQuote(
                asset=Put(underlying="AAPL", strike=strike, expiration_date=exp_date),
                quote_date=datetime.now(),
                price=5.0
            ) for strike in put_strikes
        ]
        
        chain = OptionsChain(
            underlying_symbol="AAPL",
            expiration_date=exp_date,
            underlying_price=underlying_price,
            calls=calls,
            puts=puts
        )
        
        itm_options = chain.get_itm_options()
        otm_options = chain.get_otm_options()
        
        # ITM calls: strikes < 150 (140, 145)
        assert len(itm_options["calls"]) == 2
        # ITM puts: strikes > 150 (155, 160)
        assert len(itm_options["puts"]) == 2
        
        # OTM calls: strikes > 150 (155, 160)
        assert len(otm_options["calls"]) == 2
        # OTM puts: strikes < 150 (140, 145)
        assert len(otm_options["puts"]) == 2

    def test_options_chain_get_option_by_delta(self):
        """Test get option by target delta."""
        exp_date = date.today() + timedelta(days=30)
        
        calls = [
            OptionQuote(
                asset=Call(underlying="AAPL", strike=145.0, expiration_date=exp_date),
                quote_date=datetime.now(),
                price=8.0,
                delta=0.7
            ),
            OptionQuote(
                asset=Call(underlying="AAPL", strike=150.0, expiration_date=exp_date),
                quote_date=datetime.now(),
                price=5.0,
                delta=0.5
            ),
            OptionQuote(
                asset=Call(underlying="AAPL", strike=155.0, expiration_date=exp_date),
                quote_date=datetime.now(),
                price=3.0,
                delta=0.3
            ),
        ]
        
        chain = OptionsChain(
            underlying_symbol="AAPL",
            expiration_date=exp_date,
            calls=calls
        )
        
        # Find call closest to 0.6 delta
        closest = chain.get_option_by_delta(0.6, "call")
        assert closest is not None
        assert closest.delta == 0.7  # Closest to 0.6
        
        # Find call closest to 0.4 delta
        closest = chain.get_option_by_delta(0.4, "call")
        assert closest is not None
        assert closest.delta == 0.3  # Closest to 0.4

    def test_options_chain_get_liquid_options(self):
        """Test get liquid options filter."""
        exp_date = date.today() + timedelta(days=30)
        
        calls = [
            OptionQuote(
                asset=Call(underlying="AAPL", strike=150.0, expiration_date=exp_date),
                quote_date=datetime.now(),
                price=5.0,
                bid=4.8,
                volume=1000  # High volume
            ),
            OptionQuote(
                asset=Call(underlying="AAPL", strike=155.0, expiration_date=exp_date),
                quote_date=datetime.now(),
                price=3.0,
                bid=0.01,   # Low bid
                volume=50   # Low volume
            ),
        ]
        
        chain = OptionsChain(
            underlying_symbol="AAPL",
            expiration_date=exp_date,
            calls=calls
        )
        
        # Filter for liquid options (min_volume=100, min_bid=0.1)
        liquid = chain.get_liquid_options(min_volume=100, min_bid=0.1)
        
        assert len(liquid.calls) == 1  # Only first call meets criteria
        assert liquid.calls[0].volume == 1000

    def test_options_chain_get_summary_stats(self):
        """Test get summary statistics."""
        exp_date = date.today() + timedelta(days=30)
        
        calls = [
            OptionQuote(
                asset=Call(underlying="AAPL", strike=145.0, expiration_date=exp_date),
                quote_date=datetime.now(),
                price=8.0,
                volume=500,
                open_interest=1000,
                delta=0.7
            ),
            OptionQuote(
                asset=Call(underlying="AAPL", strike=150.0, expiration_date=exp_date),
                quote_date=datetime.now(),
                price=5.0,
                volume=800,
                open_interest=1500,
                delta=0.5
            ),
        ]
        
        puts = [
            OptionQuote(
                asset=Put(underlying="AAPL", strike=150.0, expiration_date=exp_date),
                quote_date=datetime.now(),
                price=3.0,
                volume=300,
                open_interest=800
            ),
        ]
        
        chain = OptionsChain(
            underlying_symbol="AAPL",
            expiration_date=exp_date,
            calls=calls,
            puts=puts
        )
        
        stats = chain.get_summary_stats()
        
        assert stats["total_options"] == 3
        assert stats["call_count"] == 2
        assert stats["put_count"] == 1
        assert stats["strike_range"]["min"] == 145.0
        assert stats["strike_range"]["max"] == 150.0
        assert stats["strike_range"]["count"] == 2
        assert stats["volume"]["total"] == 1600  # 500 + 800 + 300
        assert stats["open_interest"]["total"] == 3300  # 1000 + 1500 + 800
        assert stats["greeks"]["delta_available"] == 2  # Only calls have delta

    def test_options_chain_empty(self):
        """Test options chain with no options."""
        chain = OptionsChain(
            underlying_symbol="TEST",
            expiration_date=date.today()
        )
        
        assert len(chain.all_options) == 0
        assert chain.get_strikes() == []
        
        stats = chain.get_summary_stats()
        assert stats == {}  # Empty stats for empty chain


class TestOptionsChainResponse:
    """Test OptionsChainResponse API model."""

    def test_options_chain_response_creation(self):
        """Test options chain response creation."""
        response = OptionsChainResponse(
            underlying_symbol="AAPL",
            underlying_price=150.0,
            expiration_date="2024-03-15",
            quote_time="2024-01-15T10:30:00Z",
            calls=[
                {
                    "symbol": "AAPL240315C00150000",
                    "strike": 150.0,
                    "price": 5.0,
                    "bid": 4.8,
                    "ask": 5.2
                }
            ],
            puts=[],
            data_source="test_adapter",
            cached=False
        )
        
        assert response.underlying_symbol == "AAPL"
        assert response.underlying_price == 150.0
        assert len(response.calls) == 1
        assert len(response.puts) == 0
        assert response.data_source == "test_adapter"


class TestGreeksResponse:
    """Test GreeksResponse API model."""

    def test_greeks_response_creation(self):
        """Test Greeks response creation."""
        response = GreeksResponse(
            option_symbol="AAPL240315C00150000",
            underlying_symbol="AAPL",
            strike=150.0,
            expiration_date="2024-03-15",
            option_type="call",
            days_to_expiration=60,
            delta=0.6,
            gamma=0.02,
            theta=-0.05,
            vega=0.3,
            rho=0.15,
            charm=0.01,
            vanna=0.12,
            implied_volatility=0.25,
            underlying_price=155.0,
            option_price=8.0,
            data_source="live_data",
            cached=True
        )
        
        assert response.option_symbol == "AAPL240315C00150000"
        assert response.delta == 0.6
        assert response.implied_volatility == 0.25
        assert response.cached is True

    def test_greeks_response_minimal(self):
        """Test Greeks response with minimal fields."""
        response = GreeksResponse(
            option_symbol="SPY240119P00450000",
            underlying_symbol="SPY",
            strike=450.0,
            expiration_date="2024-01-19",
            option_type="put",
            data_source="test"
        )
        
        assert response.option_symbol == "SPY240119P00450000"
        assert response.option_type == "put"
        assert response.delta is None  # Optional field
        assert response.days_to_expiration is None


class TestQuoteEdgeCases:
    """Test edge cases and error conditions for quote models."""

    def test_quote_with_zero_bid_ask(self):
        """Test quote behavior with zero bid/ask."""
        quote = Quote(
            asset="PENNY",
            quote_date=datetime.now(),
            bid=0.0,
            ask=0.0
        )
        
        assert quote.spread == 0.0
        assert quote.midpoint == 0.0
        assert quote.price is None  # No price calculated from zero bid/ask

    def test_quote_with_inverted_spread(self):
        """Test quote with bid > ask (unusual but possible)."""
        quote = Quote(
            asset="WEIRD",
            quote_date=datetime.now(),
            bid=101.0,
            ask=100.0
        )
        
        assert quote.spread == -1.0  # Negative spread
        assert quote.midpoint == 100.5

    def test_option_quote_without_underlying_price(self):
        """Test option quote behavior without underlying price."""
        option = Call(underlying="AAPL", strike=150.0, expiration_date=date.today())
        
        quote = OptionQuote(
            asset=option,
            quote_date=datetime.now(),
            price=5.0
        )
        
        assert quote.get_intrinsic_value() == 0.0
        assert quote.get_extrinsic_value() == 0.0

    def test_options_chain_no_underlying_price(self):
        """Test options chain behavior without underlying price."""
        chain = OptionsChain(
            underlying_symbol="TEST",
            expiration_date=date.today()
        )
        
        # Methods that depend on underlying price should handle None gracefully
        itm_options = chain.get_itm_options()
        otm_options = chain.get_otm_options()
        atm_options = chain.get_atm_options()
        
        assert itm_options == {"calls": [], "puts": []}
        assert otm_options == {"calls": [], "puts": []}
        assert atm_options == {"calls": [], "puts": []}

    def test_options_chain_filter_moneyness_no_underlying(self):
        """Test moneyness filter without underlying price."""
        chain = OptionsChain(
            underlying_symbol="TEST",
            expiration_date=date.today()
        )
        
        # Should return self when no underlying price
        filtered = chain.filter_by_moneyness(0.2)
        assert filtered is chain

    def test_quote_date_edge_cases(self):
        """Test quote date handling edge cases."""
        # ISO string with timezone
        quote1 = Quote(
            asset="AAPL",
            quote_date="2024-03-15T10:30:00+05:00",
            price=150.0
        )
        assert isinstance(quote1.quote_date, datetime)
        
        # Minimal date object
        minimal_date = date(2024, 1, 1)
        quote2 = Quote(
            asset="AAPL",
            quote_date=minimal_date,
            price=150.0
        )
        assert quote2.quote_date.date() == minimal_date
        assert quote2.quote_date.time() == datetime.min.time()

    def test_options_chain_delta_search_no_deltas(self):
        """Test delta search when no options have delta."""
        exp_date = date.today() + timedelta(days=30)
        calls = [
            OptionQuote(
                asset=Call(underlying="AAPL", strike=150.0, expiration_date=exp_date),
                quote_date=datetime.now(),
                price=5.0
                # No delta provided
            )
        ]
        
        chain = OptionsChain(
            underlying_symbol="AAPL",
            expiration_date=exp_date,
            calls=calls
        )
        
        result = chain.get_option_by_delta(0.5, "call")
        assert result is None