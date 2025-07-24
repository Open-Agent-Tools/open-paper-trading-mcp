"""
Comprehensive test suite for app.models.quotes module.

Tests cover:
- Quote class validation and methods
- OptionQuote class with Greeks calculations
- QuoteResponse and OptionsChain classes
- Quote factory method functionality
- Market data validation and processing
- Options chain filtering and analysis
- Greeks calculations and validation
- Edge cases and error handling
"""

from datetime import date, datetime
from unittest.mock import patch

import pytest
from pydantic import ValidationError

from app.models.assets import Call, Option, Put, Stock
from app.models.quotes import (
    GreeksResponse,
    OptionQuote,
    OptionsChain,
    OptionsChainResponse,
    Quote,
    QuoteResponse,
    quote_factory,
)


class TestQuoteClass:
    """Test the Quote class functionality."""

    def test_quote_creation_basic(self):
        """Test basic quote creation."""
        quote = Quote(
            asset=Stock(symbol="AAPL"),
            quote_date=datetime.now(),
            price=150.0,
            bid=149.5,
            ask=150.5,
        )

        assert quote.asset.symbol == "AAPL"
        assert quote.price == 150.0
        assert quote.bid == 149.5
        assert quote.ask == 150.5
        assert quote.spread == 1.0
        assert quote.midpoint == 150.0

    def test_quote_asset_normalization(self):
        """Test asset normalization from string."""
        quote = Quote(asset="AAPL", quote_date=datetime.now(), price=150.0)

        assert isinstance(quote.asset, Stock)
        assert quote.asset.symbol == "AAPL"

    def test_quote_asset_normalization_invalid(self):
        """Test invalid asset normalization."""
        with pytest.raises(ValueError, match="Could not create asset for symbol"):
            Quote(asset="", quote_date=datetime.now(), price=150.0)

    def test_quote_date_normalization(self):
        """Test various date format normalizations."""
        test_cases = [
            ("2024-01-15T10:30:00Z", datetime(2024, 1, 15, 10, 30)),
            ("2024-01-15T10:30:00+00:00", datetime(2024, 1, 15, 10, 30)),
            (date(2024, 1, 15), datetime(2024, 1, 15)),
            (datetime(2024, 1, 15, 10, 30), datetime(2024, 1, 15, 10, 30)),
        ]

        for date_input, expected in test_cases:
            quote = Quote(asset="AAPL", quote_date=date_input, price=150.0)
            # Compare just the date and time components, ignoring timezone
            assert quote.quote_date.replace(tzinfo=None) == expected

    def test_quote_price_calculation_from_bid_ask(self):
        """Test price calculation from bid/ask when price is None."""
        quote = Quote(asset="AAPL", quote_date=datetime.now(), bid=149.5, ask=150.5)

        assert quote.price == 150.0  # Midpoint

    def test_quote_price_calculation_no_bid_ask(self):
        """Test price remains None when no bid/ask provided."""
        quote = Quote(asset="AAPL", quote_date=datetime.now())

        assert quote.price is None

    def test_quote_field_validation(self):
        """Test field validation constraints."""
        # Negative bid should fail
        with pytest.raises(ValidationError):
            Quote(asset="AAPL", quote_date=datetime.now(), bid=-1.0)

        # Negative ask should fail
        with pytest.raises(ValidationError):
            Quote(asset="AAPL", quote_date=datetime.now(), ask=-1.0)

        # Negative volume should fail
        with pytest.raises(ValidationError):
            Quote(asset="AAPL", quote_date=datetime.now(), volume=-1)

    def test_quote_properties(self):
        """Test quote computed properties."""
        quote = Quote(
            asset="AAPL",
            quote_date=datetime.now(),
            price=150.0,
            bid=149.0,
            ask=151.0,
            volume=1000,
        )

        assert quote.symbol == "AAPL"
        assert quote.spread == 2.0
        assert quote.midpoint == 150.0
        assert quote.is_priceable() is True

    def test_quote_not_priceable(self):
        """Test quote without valid pricing."""
        quote = Quote(asset="AAPL", quote_date=datetime.now(), bid=149.0, ask=151.0)

        assert quote.is_priceable() is False

    def test_quote_with_greeks(self):
        """Test quote with Greeks (should be None for stock quotes)."""
        quote = Quote(
            asset="AAPL",
            quote_date=datetime.now(),
            price=150.0,
            delta=0.5,
            gamma=0.1,
            theta=-0.05,
            vega=0.2,
            rho=0.1,
        )

        assert quote.delta == 0.5
        assert quote.gamma == 0.1
        assert quote.theta == -0.05
        assert quote.vega == 0.2
        assert quote.rho == 0.1


class TestOptionQuoteClass:
    """Test the OptionQuote class functionality."""

    def test_option_quote_creation(self):
        """Test option quote creation."""
        option = Call(underlying="AAPL", strike=150.0, expiration_date="2024-12-20")

        quote = OptionQuote(
            asset=option,
            quote_date=datetime.now(),
            price=5.0,
            bid=4.9,
            ask=5.1,
            underlying_price=155.0,
        )

        assert isinstance(quote.asset, Option)
        assert quote.underlying_price == 155.0
        assert quote.strike == 150.0
        assert quote.option_type == "call"

    def test_option_quote_validation_requires_option(self):
        """Test that OptionQuote requires an Option asset."""
        with pytest.raises(ValueError, match="OptionQuote requires an Option asset"):
            OptionQuote(
                asset=Stock(symbol="AAPL"), quote_date=datetime.now(), price=5.0
            )

    def test_option_quote_properties(self):
        """Test option quote specific properties."""
        option = Call(underlying="AAPL", strike=150.0, expiration_date="2024-12-20")
        quote_date = datetime(2024, 12, 10, 10, 0)

        quote = OptionQuote(
            asset=option, quote_date=quote_date, price=5.0, underlying_price=155.0
        )

        assert quote.days_to_expiration == 10
        assert quote.strike == 150.0
        assert quote.expiration_date == date(2024, 12, 20)
        assert quote.option_type == "call"

    @patch("app.models.quotes.OptionQuote._calculate_greeks")
    def test_option_quote_greeks_calculation(self, mock_calc_greeks):
        """Test Greeks calculation is called when appropriate."""
        option = Call(underlying="AAPL", strike=150.0, expiration_date="2024-12-20")

        OptionQuote(
            asset=option, quote_date=datetime.now(), price=5.0, underlying_price=155.0
        )

        # Greeks calculation should be called
        mock_calc_greeks.assert_called_once()

    def test_option_quote_greeks_not_calculated_when_provided(self):
        """Test Greeks are not calculated when already provided."""
        option = Call(underlying="AAPL", strike=150.0, expiration_date="2024-12-20")

        with patch("app.models.quotes.OptionQuote._calculate_greeks") as mock_calc:
            OptionQuote(
                asset=option,
                quote_date=datetime.now(),
                price=5.0,
                underlying_price=155.0,
                delta=0.6,  # Already provided
            )

            # Greeks calculation should not be called
            mock_calc.assert_not_called()

    def test_option_quote_greeks_not_calculated_insufficient_data(self):
        """Test Greeks are not calculated without sufficient data."""
        option = Call(underlying="AAPL", strike=150.0, expiration_date="2024-12-20")

        with patch("app.models.quotes.OptionQuote._calculate_greeks") as mock_calc:
            OptionQuote(
                asset=option,
                quote_date=datetime.now(),
                # No price or underlying_price
            )

            # Greeks calculation should not be called
            mock_calc.assert_not_called()

    @patch("app.services.greeks.update_option_quote_with_greeks")
    def test_option_quote_greeks_service_integration(self, mock_update_greeks):
        """Test integration with Greeks calculation service."""
        option = Call(underlying="AAPL", strike=150.0, expiration_date="2024-12-20")

        quote = OptionQuote(
            asset=option, quote_date=datetime.now(), price=5.0, underlying_price=155.0
        )

        # Service should be called
        mock_update_greeks.assert_called_once_with(quote)

    def test_option_quote_greeks_service_not_available(self):
        """Test graceful handling when Greeks service not available."""
        option = Call(underlying="AAPL", strike=150.0, expiration_date="2024-12-20")

        with patch("app.models.quotes.OptionQuote._calculate_greeks") as mock_calc:

            def side_effect():
                raise ImportError("Service not available")

            mock_calc.side_effect = side_effect

            # Should not raise error
            OptionQuote(
                asset=option,
                quote_date=datetime.now(),
                price=5.0,
                underlying_price=155.0,
            )

    def test_option_quote_has_greeks(self):
        """Test has_greeks method."""
        option = Call(underlying="AAPL", strike=150.0, expiration_date="2024-12-20")

        quote_without_iv = OptionQuote(
            asset=option, quote_date=datetime.now(), price=5.0
        )
        assert quote_without_iv.has_greeks() is False

        quote_with_iv = OptionQuote(
            asset=option, quote_date=datetime.now(), price=5.0, iv=0.25
        )
        assert quote_with_iv.has_greeks() is True

    def test_option_quote_intrinsic_value(self):
        """Test intrinsic value calculation."""
        call_option = Call(
            underlying="AAPL", strike=150.0, expiration_date="2024-12-20"
        )

        quote = OptionQuote(
            asset=call_option,
            quote_date=datetime.now(),
            price=8.0,
            underlying_price=155.0,
        )

        assert quote.get_intrinsic_value() == 5.0
        assert quote.get_intrinsic_value(160.0) == 10.0  # Override price

    def test_option_quote_extrinsic_value(self):
        """Test extrinsic value calculation."""
        call_option = Call(
            underlying="AAPL", strike=150.0, expiration_date="2024-12-20"
        )

        quote = OptionQuote(
            asset=call_option,
            quote_date=datetime.now(),
            price=8.0,
            underlying_price=155.0,
        )

        assert quote.get_extrinsic_value() == 3.0  # 8.0 - 5.0 intrinsic

    def test_option_quote_all_greeks_fields(self):
        """Test all Greeks fields are available."""
        option = Call(underlying="AAPL", strike=150.0, expiration_date="2024-12-20")

        quote = OptionQuote(
            asset=option,
            quote_date=datetime.now(),
            price=5.0,
            delta=0.6,
            gamma=0.05,
            theta=-0.02,
            vega=0.15,
            rho=0.08,
            iv=0.25,
            vanna=0.01,
            charm=-0.001,
            speed=0.002,
            zomma=0.003,
            color=-0.0001,
            veta=0.05,
            vomma=0.1,
            ultima=0.01,
            dual_delta=0.4,
            open_interest=100,
        )

        assert quote.delta == 0.6
        assert quote.gamma == 0.05
        assert quote.theta == -0.02
        assert quote.vega == 0.15
        assert quote.rho == 0.08
        assert quote.iv == 0.25
        assert quote.vanna == 0.01
        assert quote.charm == -0.001
        assert quote.speed == 0.002
        assert quote.zomma == 0.003
        assert quote.color == -0.0001
        assert quote.veta == 0.05
        assert quote.vomma == 0.1
        assert quote.ultima == 0.01
        assert quote.dual_delta == 0.4
        assert quote.open_interest == 100


class TestQuoteFactory:
    """Test the quote_factory function."""

    def test_factory_creates_stock_quote(self):
        """Test factory creates Quote for stock."""
        quote = quote_factory(quote_date=datetime.now(), asset="AAPL", price=150.0)

        assert isinstance(quote, Quote)
        assert not isinstance(quote, OptionQuote)
        assert quote.asset.symbol == "AAPL"

    def test_factory_creates_option_quote(self):
        """Test factory creates OptionQuote for option."""
        option = Call(underlying="AAPL", strike=150.0, expiration_date="2024-12-20")

        quote = quote_factory(
            quote_date=datetime.now(), asset=option, price=5.0, underlying_price=155.0
        )

        assert isinstance(quote, OptionQuote)
        assert quote.underlying_price == 155.0

    def test_factory_with_string_date(self):
        """Test factory with string date input."""
        quote = quote_factory(
            quote_date="2024-01-15T10:30:00Z", asset="AAPL", price=150.0
        )

        assert quote.quote_date.year == 2024
        assert quote.quote_date.month == 1
        assert quote.quote_date.day == 15

    def test_factory_with_date_object(self):
        """Test factory with date object input."""
        test_date = date(2024, 1, 15)

        quote = quote_factory(quote_date=test_date, asset="AAPL", price=150.0)

        assert quote.quote_date.date() == test_date

    def test_factory_invalid_asset(self):
        """Test factory with invalid asset."""
        with pytest.raises(
            ValueError, match="Could not create asset from provided symbol"
        ):
            quote_factory(quote_date=datetime.now(), asset=None, price=150.0)


class TestQuoteResponse:
    """Test the QuoteResponse class."""

    def test_quote_response_creation(self):
        """Test quote response creation."""
        quote = Quote(asset="AAPL", quote_date=datetime.now(), price=150.0)

        response = QuoteResponse(
            quote=quote, data_source="test_source", cached=True, cache_age_seconds=60
        )

        assert response.quote == quote
        assert response.data_source == "test_source"
        assert response.cached is True
        assert response.cache_age_seconds == 60

    def test_quote_response_with_option_quote(self):
        """Test quote response with option quote."""
        option = Call(underlying="AAPL", strike=150.0, expiration_date="2024-12-20")
        quote = OptionQuote(asset=option, quote_date=datetime.now(), price=5.0)

        response = QuoteResponse(quote=quote, data_source="test_source")

        assert isinstance(response.quote, OptionQuote)


class TestOptionsChain:
    """Test the OptionsChain class."""

    def setup_method(self):
        """Set up test data for options chain tests."""
        self.underlying_symbol = "AAPL"
        self.expiration_date = date(2024, 12, 20)
        self.underlying_price = 150.0

        # Create sample calls
        self.call_145 = OptionQuote(
            asset=Call(underlying="AAPL", strike=145.0, expiration_date="2024-12-20"),
            quote_date=datetime.now(),
            price=8.0,
            volume=100,
            delta=0.7,
        )

        self.call_150 = OptionQuote(
            asset=Call(underlying="AAPL", strike=150.0, expiration_date="2024-12-20"),
            quote_date=datetime.now(),
            price=5.0,
            volume=200,
            delta=0.5,
        )

        self.call_155 = OptionQuote(
            asset=Call(underlying="AAPL", strike=155.0, expiration_date="2024-12-20"),
            quote_date=datetime.now(),
            price=3.0,
            volume=50,
            delta=0.3,
        )

        # Create sample puts
        self.put_145 = OptionQuote(
            asset=Put(underlying="AAPL", strike=145.0, expiration_date="2024-12-20"),
            quote_date=datetime.now(),
            price=2.0,
            volume=75,
            delta=-0.3,
        )

        self.put_150 = OptionQuote(
            asset=Put(underlying="AAPL", strike=150.0, expiration_date="2024-12-20"),
            quote_date=datetime.now(),
            price=4.0,
            volume=150,
            delta=-0.5,
        )

        self.put_155 = OptionQuote(
            asset=Put(underlying="AAPL", strike=155.0, expiration_date="2024-12-20"),
            quote_date=datetime.now(),
            price=7.0,
            volume=80,
            delta=-0.7,
        )

    def test_options_chain_creation(self):
        """Test options chain creation."""
        chain = OptionsChain(
            underlying_symbol=self.underlying_symbol,
            expiration_date=self.expiration_date,
            underlying_price=self.underlying_price,
            calls=[self.call_150],
            puts=[self.put_150],
        )

        assert chain.underlying_symbol == "AAPL"
        assert chain.expiration_date == self.expiration_date
        assert chain.underlying_price == 150.0
        assert len(chain.calls) == 1
        assert len(chain.puts) == 1

    def test_options_chain_all_options_property(self):
        """Test all_options property."""
        chain = OptionsChain(
            underlying_symbol=self.underlying_symbol,
            expiration_date=self.expiration_date,
            calls=[self.call_150, self.call_155],
            puts=[self.put_150],
        )

        all_options = chain.all_options
        assert len(all_options) == 3
        assert self.call_150 in all_options
        assert self.call_155 in all_options
        assert self.put_150 in all_options

    def test_options_chain_get_strikes(self):
        """Test get_strikes method."""
        chain = OptionsChain(
            underlying_symbol=self.underlying_symbol,
            expiration_date=self.expiration_date,
            calls=[self.call_145, self.call_155],
            puts=[self.put_150],
        )

        strikes = chain.get_strikes()
        assert strikes == [145.0, 150.0, 155.0]  # Sorted

    def test_options_chain_get_by_strike(self):
        """Test get calls/puts by strike methods."""
        chain = OptionsChain(
            underlying_symbol=self.underlying_symbol,
            expiration_date=self.expiration_date,
            calls=[self.call_150, self.call_155],
            puts=[self.put_150, self.put_155],
        )

        calls_150 = chain.get_calls_by_strike(150.0)
        assert len(calls_150) == 1
        assert calls_150[0] == self.call_150

        puts_155 = chain.get_puts_by_strike(155.0)
        assert len(puts_155) == 1
        assert puts_155[0] == self.put_155

    def test_options_chain_filter_by_strike_range(self):
        """Test strike range filtering."""
        chain = OptionsChain(
            underlying_symbol=self.underlying_symbol,
            expiration_date=self.expiration_date,
            calls=[self.call_145, self.call_150, self.call_155],
            puts=[self.put_145, self.put_150, self.put_155],
        )

        # Filter to 148-152 range
        filtered = chain.filter_by_strike_range(148.0, 152.0)

        assert len(filtered.calls) == 1  # Only 150 call
        assert len(filtered.puts) == 1  # Only 150 put
        assert filtered.calls[0].strike == 150.0
        assert filtered.puts[0].strike == 150.0

    def test_options_chain_filter_by_moneyness(self):
        """Test moneyness filtering."""
        chain = OptionsChain(
            underlying_symbol=self.underlying_symbol,
            expiration_date=self.expiration_date,
            underlying_price=150.0,
            calls=[self.call_145, self.call_150, self.call_155],
            puts=[self.put_145, self.put_150, self.put_155],
        )

        # Filter to 10% around ATM (135-165 range)
        filtered = chain.filter_by_moneyness(0.1)

        # All strikes should be included (145, 150, 155 all within 10% of 150)
        assert len(filtered.calls) == 3
        assert len(filtered.puts) == 3

    def test_options_chain_get_atm_options(self):
        """Test ATM options identification."""
        chain = OptionsChain(
            underlying_symbol=self.underlying_symbol,
            expiration_date=self.expiration_date,
            underlying_price=150.0,
            calls=[self.call_145, self.call_150, self.call_155],
            puts=[self.put_145, self.put_150, self.put_155],
        )

        atm_options = chain.get_atm_options(tolerance=0.05)  # 5% tolerance

        # Only 150 strike should be ATM
        assert len(atm_options["calls"]) == 1
        assert len(atm_options["puts"]) == 1
        assert atm_options["calls"][0].strike == 150.0
        assert atm_options["puts"][0].strike == 150.0

    def test_options_chain_get_itm_options(self):
        """Test ITM options identification."""
        chain = OptionsChain(
            underlying_symbol=self.underlying_symbol,
            expiration_date=self.expiration_date,
            underlying_price=150.0,
            calls=[self.call_145, self.call_150, self.call_155],
            puts=[self.put_145, self.put_150, self.put_155],
        )

        itm_options = chain.get_itm_options()

        # ITM calls: strike < underlying (145)
        # ITM puts: strike > underlying (155)
        assert len(itm_options["calls"]) == 1
        assert len(itm_options["puts"]) == 1
        assert itm_options["calls"][0].strike == 145.0
        assert itm_options["puts"][0].strike == 155.0

    def test_options_chain_get_otm_options(self):
        """Test OTM options identification."""
        chain = OptionsChain(
            underlying_symbol=self.underlying_symbol,
            expiration_date=self.expiration_date,
            underlying_price=150.0,
            calls=[self.call_145, self.call_150, self.call_155],
            puts=[self.put_145, self.put_150, self.put_155],
        )

        otm_options = chain.get_otm_options()

        # OTM calls: strike > underlying (155)
        # OTM puts: strike < underlying (145)
        assert len(otm_options["calls"]) == 1
        assert len(otm_options["puts"]) == 1
        assert otm_options["calls"][0].strike == 155.0
        assert otm_options["puts"][0].strike == 145.0

    def test_options_chain_get_option_by_delta(self):
        """Test finding option by delta."""
        chain = OptionsChain(
            underlying_symbol=self.underlying_symbol,
            expiration_date=self.expiration_date,
            calls=[self.call_145, self.call_150, self.call_155],
            puts=[self.put_145, self.put_150, self.put_155],
        )

        # Find call closest to 0.4 delta (should be call_155 with 0.3)
        closest_call = chain.get_option_by_delta(0.4, "call")
        assert closest_call == self.call_155

        # Find put closest to -0.4 delta (should be put_145 with -0.3)
        closest_put = chain.get_option_by_delta(-0.4, "put")
        assert closest_put == self.put_145

    def test_options_chain_get_liquid_options(self):
        """Test liquidity filtering."""
        chain = OptionsChain(
            underlying_symbol=self.underlying_symbol,
            expiration_date=self.expiration_date,
            calls=[self.call_150, self.call_155],  # 200 and 50 volume
            puts=[self.put_150, self.put_155],  # 150 and 80 volume
        )

        # Filter for min 100 volume, min 0.05 bid
        liquid_chain = chain.get_liquid_options(min_volume=100, min_bid=0.05)

        # Should only include options with volume >= 100
        assert len(liquid_chain.calls) == 1  # Only call_150 (200 volume)
        assert len(liquid_chain.puts) == 1  # Only put_150 (150 volume)

    def test_options_chain_get_summary_stats(self):
        """Test chain summary statistics."""
        chain = OptionsChain(
            underlying_symbol=self.underlying_symbol,
            expiration_date=self.expiration_date,
            calls=[self.call_145, self.call_150, self.call_155],
            puts=[self.put_145, self.put_150, self.put_155],
        )

        stats = chain.get_summary_stats()

        assert stats["total_options"] == 6
        assert stats["call_count"] == 3
        assert stats["put_count"] == 3
        assert stats["strike_range"]["min"] == 145.0
        assert stats["strike_range"]["max"] == 155.0
        assert stats["strike_range"]["count"] == 3
        assert stats["volume"]["total"] == 605  # Sum of all volumes
        assert stats["greeks"]["delta_available"] == 6  # All have delta

    def test_options_chain_empty(self):
        """Test empty options chain."""
        chain = OptionsChain(
            underlying_symbol=self.underlying_symbol,
            expiration_date=self.expiration_date,
        )

        assert len(chain.all_options) == 0
        assert chain.get_strikes() == []
        assert chain.get_summary_stats() == {}

    def test_options_chain_no_underlying_price(self):
        """Test chain operations without underlying price."""
        chain = OptionsChain(
            underlying_symbol=self.underlying_symbol,
            expiration_date=self.expiration_date,
            underlying_price=None,
            calls=[self.call_150],
            puts=[self.put_150],
        )

        # Should return empty for moneyness-based methods
        assert chain.get_atm_options() == {"calls": [], "puts": []}
        assert chain.get_itm_options() == {"calls": [], "puts": []}
        assert chain.get_otm_options() == {"calls": [], "puts": []}

        # Moneyness filtering should return self
        filtered = chain.filter_by_moneyness(0.1)
        assert filtered is chain


class TestOptionsChainResponse:
    """Test the OptionsChainResponse class."""

    def test_options_chain_response_creation(self):
        """Test options chain response creation."""
        response = OptionsChainResponse(
            underlying_symbol="AAPL",
            underlying_price=150.0,
            expiration_date="2024-12-20",
            quote_time="2024-01-15T10:30:00Z",
            data_source="test_source",
            cached=True,
        )

        assert response.underlying_symbol == "AAPL"
        assert response.underlying_price == 150.0
        assert response.expiration_date == "2024-12-20"
        assert response.data_source == "test_source"
        assert response.cached is True


class TestGreeksResponse:
    """Test the GreeksResponse class."""

    def test_greeks_response_creation(self):
        """Test Greeks response creation."""
        response = GreeksResponse(
            option_symbol="AAPL241220C00150000",
            underlying_symbol="AAPL",
            strike=150.0,
            expiration_date="2024-12-20",
            option_type="call",
            days_to_expiration=30,
            delta=0.6,
            gamma=0.05,
            theta=-0.02,
            vega=0.15,
            rho=0.08,
            implied_volatility=0.25,
            underlying_price=155.0,
            option_price=8.0,
            data_source="test_source",
        )

        assert response.option_symbol == "AAPL241220C00150000"
        assert response.underlying_symbol == "AAPL"
        assert response.strike == 150.0
        assert response.delta == 0.6
        assert response.gamma == 0.05
        assert response.implied_volatility == 0.25


class TestEdgeCasesAndValidation:
    """Test edge cases and comprehensive validation."""

    def test_quote_with_zero_spread(self):
        """Test quote with zero bid-ask spread."""
        quote = Quote(
            asset="AAPL", quote_date=datetime.now(), bid=150.0, ask=150.0, price=150.0
        )

        assert quote.spread == 0.0
        assert quote.midpoint == 150.0

    def test_quote_with_inverted_spread(self):
        """Test quote with inverted spread (bid > ask)."""
        quote = Quote(asset="AAPL", quote_date=datetime.now(), bid=151.0, ask=150.0)

        assert quote.spread == -1.0  # Negative spread
        assert quote.midpoint == 150.5

    def test_option_quote_without_underlying_price(self):
        """Test option quote calculations without underlying price."""
        option = Call(underlying="AAPL", strike=150.0, expiration_date="2024-12-20")

        quote = OptionQuote(asset=option, quote_date=datetime.now(), price=5.0)

        assert quote.get_intrinsic_value() == 0.0
        assert quote.get_extrinsic_value() == 0.0

    def test_options_chain_duplicate_strikes(self):
        """Test options chain with duplicate strikes."""
        call1 = OptionQuote(
            asset=Call(underlying="AAPL", strike=150.0, expiration_date="2024-12-20"),
            quote_date=datetime.now(),
            price=5.0,
        )

        call2 = OptionQuote(
            asset=Call(underlying="AAPL", strike=150.0, expiration_date="2024-12-20"),
            quote_date=datetime.now(),
            price=5.1,
        )

        chain = OptionsChain(
            underlying_symbol="AAPL",
            expiration_date=date(2024, 12, 20),
            calls=[call1, call2],
        )

        # Should handle duplicates correctly
        strikes = chain.get_strikes()
        assert strikes == [150.0]  # Only one unique strike

        calls_at_150 = chain.get_calls_by_strike(150.0)
        assert len(calls_at_150) == 2  # Both calls returned

    def test_options_chain_missing_greeks(self):
        """Test options chain with missing Greeks."""
        call_no_delta = OptionQuote(
            asset=Call(underlying="AAPL", strike=150.0, expiration_date="2024-12-20"),
            quote_date=datetime.now(),
            price=5.0,
            # No delta provided
        )

        chain = OptionsChain(
            underlying_symbol="AAPL",
            expiration_date=date(2024, 12, 20),
            calls=[call_no_delta],
        )

        # get_option_by_delta should return None when no deltas available
        result = chain.get_option_by_delta(0.5, "call")
        assert result is None
