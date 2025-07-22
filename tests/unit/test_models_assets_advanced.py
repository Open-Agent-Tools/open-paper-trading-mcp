"""
Advanced tests for asset models.

Comprehensive test coverage for asset classes including Stock, Option, Call, Put,
asset factory patterns, validation, equality, serialization, and option pricing logic.
"""

from datetime import date, datetime, timedelta

import pytest

from app.models.assets import Asset, Call, Option, Put, Stock, asset_factory


class TestAssetFactory:
    """Test the asset factory function."""

    def test_asset_factory_none_input(self):
        """Test asset factory with None input."""
        result = asset_factory(None)
        assert result is None

    def test_asset_factory_existing_asset(self):
        """Test asset factory with existing Asset object."""
        stock = Stock("AAPL")
        result = asset_factory(stock)
        assert result is stock  # Should return the same object
        assert isinstance(result, Stock)

    def test_asset_factory_stock_symbol(self):
        """Test asset factory with stock symbol."""
        result = asset_factory("AAPL")
        assert isinstance(result, Stock)
        assert result.symbol == "AAPL"

    def test_asset_factory_stock_symbol_lowercase(self):
        """Test asset factory normalizes case."""
        result = asset_factory("aapl")
        assert isinstance(result, Stock)
        assert result.symbol == "AAPL"

    def test_asset_factory_stock_symbol_with_spaces(self):
        """Test asset factory strips whitespace."""
        result = asset_factory("  MSFT  ")
        assert isinstance(result, Stock)
        assert result.symbol == "MSFT"

    def test_asset_factory_put_option_symbol(self):
        """Test asset factory with put option symbol."""
        result = asset_factory("AAPL240119P00195000")
        assert isinstance(result, Put)
        assert result.symbol == "AAPL240119P00195000"

    def test_asset_factory_call_option_symbol(self):
        """Test asset factory with call option symbol."""
        result = asset_factory("GOOGL240315C02800000")
        assert isinstance(result, Call)
        assert result.symbol == "GOOGL240315C02800000"

    def test_asset_factory_generic_option_symbol(self):
        """Test asset factory with generic option symbol (no C/P indicator)."""
        result = asset_factory("LONGOPTIONSYMBOL123456")
        assert isinstance(result, Option)
        assert result.symbol == "LONGOPTIONSYMBOL123456"

    def test_asset_factory_edge_case_long_stock_symbol(self):
        """Test asset factory with borderline long stock symbol."""
        # 8 characters should still be treated as stock
        result = asset_factory("BERKSHIR")
        assert isinstance(result, Stock)
        assert result.symbol == "BERKSHIR"

    def test_asset_factory_edge_case_short_option_symbol(self):
        """Test asset factory with 9 character symbol (minimum for option)."""
        result = asset_factory("SHORTOPT1")
        assert isinstance(result, Option)
        assert result.symbol == "SHORTOPT1"


class TestAsset:
    """Test the base Asset class."""

    def test_asset_creation(self):
        """Test basic asset creation."""
        asset = Asset(symbol="TEST")
        assert asset.symbol == "TEST"
        assert asset.asset_type == "stock"  # Default
        assert asset.underlying is None
        assert asset.option_type is None
        assert asset.strike is None
        assert asset.expiration_date is None

    def test_asset_symbol_normalization(self):
        """Test symbol normalization on creation."""
        asset = Asset(symbol="  test  ")
        assert asset.symbol == "TEST"

    def test_asset_custom_asset_type(self):
        """Test asset with custom asset type."""
        asset = Asset(symbol="BOND1", asset_type="bond")
        assert asset.asset_type == "bond"

    def test_asset_equality_with_asset(self):
        """Test asset equality with another Asset."""
        asset1 = Asset(symbol="AAPL")
        asset2 = Asset(symbol="AAPL")
        asset3 = Asset(symbol="GOOGL")

        assert asset1 == asset2
        assert asset1 != asset3

    def test_asset_equality_with_string(self):
        """Test asset equality with string."""
        asset = Asset(symbol="AAPL")

        assert asset == "AAPL"
        assert asset == "aapl"  # Case insensitive
        assert asset == "  AAPL  "  # Strips whitespace
        assert asset != "GOOGL"

    def test_asset_equality_with_other_types(self):
        """Test asset equality with non-Asset, non-string types."""
        asset = Asset(symbol="AAPL")

        assert asset != 123
        assert asset is not None
        assert asset != ["AAPL"]
        assert asset != {"symbol": "AAPL"}

    def test_asset_hash(self):
        """Test asset hashing for use in sets/dicts."""
        asset1 = Asset(symbol="AAPL")
        asset2 = Asset(symbol="AAPL")
        asset3 = Asset(symbol="GOOGL")

        # Same symbols should have same hash
        assert hash(asset1) == hash(asset2)
        # Different symbols should (likely) have different hash
        assert hash(asset1) != hash(asset3)

        # Should work in set
        asset_set = {asset1, asset2, asset3}
        assert len(asset_set) == 2  # asset1 and asset2 are equivalent

    def test_asset_frozen(self):
        """Test that Asset is immutable (frozen)."""
        asset = Asset(symbol="AAPL")

        with pytest.raises(AttributeError):
            asset.symbol = "GOOGL"  # Should not be able to modify

    def test_asset_with_option_fields(self):
        """Test Asset with option-specific fields set."""
        underlying_asset = Asset(symbol="AAPL")
        exp_date = date.today() + timedelta(days=30)

        asset = Asset(
            symbol="AAPL240315C00180000",
            asset_type="call",
            underlying=underlying_asset,
            option_type="call",
            strike=180.0,
            expiration_date=exp_date,
        )

        assert asset.underlying == underlying_asset
        assert asset.option_type == "call"
        assert asset.strike == 180.0
        assert asset.expiration_date == exp_date


class TestStock:
    """Test the Stock class."""

    def test_stock_creation(self):
        """Test basic stock creation."""
        stock = Stock("AAPL")
        assert stock.symbol == "AAPL"
        assert stock.asset_type == "stock"

    def test_stock_creation_with_extra_data(self):
        """Test stock creation with additional data."""
        stock = Stock("GOOGL", custom_field="value")
        assert stock.symbol == "GOOGL"
        assert stock.asset_type == "stock"

    def test_stock_symbol_normalization(self):
        """Test symbol normalization in stock."""
        stock = Stock("  msft  ")
        assert stock.symbol == "MSFT"

    def test_stock_inheritance(self):
        """Test that Stock inherits from Asset."""
        stock = Stock("TSLA")
        assert isinstance(stock, Asset)
        assert isinstance(stock, Stock)

    def test_stock_equality(self):
        """Test stock equality."""
        stock1 = Stock("NVDA")
        stock2 = Stock("NVDA")
        stock3 = Stock("AMD")

        assert stock1 == stock2
        assert stock1 != stock3
        assert stock1 == "NVDA"

    def test_stock_with_special_symbols(self):
        """Test stocks with special characters in symbols."""
        stock1 = Stock("BRK.A")
        stock2 = Stock("BRK.B")

        assert stock1.symbol == "BRK.A"
        assert stock2.symbol == "BRK.B"
        assert stock1 != stock2


class TestOption:
    """Test the base Option class."""

    def test_option_from_symbol(self):
        """Test option creation from symbol."""
        option = Option(symbol="AAPL240119C00195000")

        assert option.symbol == "AAPL240119C00195000"
        assert option.option_type == "call"
        assert option.strike == 195.0
        assert isinstance(option.underlying, Stock)
        assert option.underlying.symbol == "AAPL"
        assert option.expiration_date == date(2024, 1, 19)

    def test_option_from_symbol_put(self):
        """Test put option creation from symbol."""
        option = Option(symbol="GOOGL240315P02800000")

        assert option.symbol == "GOOGL240315P02800000"
        assert option.option_type == "put"
        assert option.strike == 2800.0
        assert option.underlying.symbol == "GOOGL"

    def test_option_from_components(self):
        """Test option creation from components."""
        exp_date = date(2024, 3, 15)
        option = Option(
            underlying="SPY", option_type="call", strike=450.0, expiration_date=exp_date
        )

        assert option.option_type == "call"
        assert option.strike == 450.0
        assert option.underlying.symbol == "SPY"
        assert option.expiration_date == exp_date
        # Should build symbol from components
        assert "SPY" in option.symbol
        assert "C" in option.symbol

    def test_option_from_components_with_asset_underlying(self):
        """Test option creation with Asset as underlying."""
        underlying_stock = Stock("QQQ")
        exp_date = date(2024, 6, 21)

        option = Option(
            underlying=underlying_stock,
            option_type="put",
            strike=380.0,
            expiration_date=exp_date,
        )

        assert option.underlying is underlying_stock
        assert option.option_type == "put"
        assert option.strike == 380.0

    def test_option_validation_errors(self):
        """Test option validation errors."""
        # Missing underlying
        with pytest.raises(ValueError, match="underlying asset is required"):
            Option(option_type="call", strike=100.0, expiration_date=date.today())

        # Invalid option type
        with pytest.raises(ValueError, match="option_type must be 'call' or 'put'"):
            Option(
                underlying="AAPL",
                option_type="invalid",
                strike=100.0,
                expiration_date=date.today(),
            )

        # Invalid strike
        with pytest.raises(ValueError, match="strike must be positive"):
            Option(
                underlying="AAPL",
                option_type="call",
                strike=-10.0,
                expiration_date=date.today(),
            )

        with pytest.raises(ValueError, match="strike must be positive"):
            Option(
                underlying="AAPL",
                option_type="call",
                strike=0.0,
                expiration_date=date.today(),
            )

        # Missing expiration
        with pytest.raises(ValueError, match="expiration_date is required"):
            Option(underlying="AAPL", option_type="call", strike=100.0)

    def test_option_symbol_parsing_edge_cases(self):
        """Test option symbol parsing edge cases."""
        # Test with different underlying lengths
        option1 = Option(symbol="A240119C00100000")  # Single letter
        assert option1.underlying.symbol == "A"
        assert option1.strike == 100.0

        option2 = Option(symbol="VERYLONGSTOCK240119P00050000")  # Long underlying
        assert option2.underlying.symbol == "VERYLONGSTOCK"
        assert option2.strike == 50.0

    def test_option_symbol_parsing_invalid(self):
        """Test invalid option symbol parsing."""
        with pytest.raises(ValueError, match="Invalid option symbol format"):
            Option(symbol="INVALID")

        with pytest.raises(ValueError, match="Invalid option symbol format"):
            Option(symbol="TOO_SHORT")

    def test_option_date_parsing(self):
        """Test different date format parsing."""
        # String date formats
        option1 = Option(
            underlying="AAPL",
            option_type="call",
            strike=150.0,
            expiration_date="2024-03-15",
        )
        assert option1.expiration_date == date(2024, 3, 15)

        option2 = Option(
            underlying="AAPL",
            option_type="call",
            strike=150.0,
            expiration_date="240315",
        )
        assert option2.expiration_date == date(2024, 3, 15)

        # Date object
        exp_date = date(2024, 6, 21)
        option3 = Option(
            underlying="AAPL",
            option_type="call",
            strike=150.0,
            expiration_date=exp_date,
        )
        assert option3.expiration_date == exp_date

        # DateTime object
        exp_datetime = datetime(2024, 9, 20, 16, 0, 0)
        option4 = Option(
            underlying="AAPL",
            option_type="call",
            strike=150.0,
            expiration_date=exp_datetime,
        )
        assert option4.expiration_date == exp_datetime.date()

    def test_option_date_parsing_invalid(self):
        """Test invalid date parsing."""
        with pytest.raises(ValueError, match="Could not parse date"):
            Option(
                underlying="AAPL",
                option_type="call",
                strike=150.0,
                expiration_date="invalid-date",
            )

        with pytest.raises(ValueError, match="Invalid date type"):
            Option(
                underlying="AAPL", option_type="call", strike=150.0, expiration_date=123
            )

    def test_option_intrinsic_value_call(self):
        """Test intrinsic value calculation for calls."""
        call_option = Option(
            underlying="AAPL",
            option_type="call",
            strike=150.0,
            expiration_date=date.today(),
        )

        # ITM call
        assert call_option.get_intrinsic_value(160.0) == 10.0
        # ATM call
        assert call_option.get_intrinsic_value(150.0) == 0.0
        # OTM call
        assert call_option.get_intrinsic_value(140.0) == 0.0

    def test_option_intrinsic_value_put(self):
        """Test intrinsic value calculation for puts."""
        put_option = Option(
            underlying="AAPL",
            option_type="put",
            strike=150.0,
            expiration_date=date.today(),
        )

        # ITM put
        assert put_option.get_intrinsic_value(140.0) == 10.0
        # ATM put
        assert put_option.get_intrinsic_value(150.0) == 0.0
        # OTM put
        assert put_option.get_intrinsic_value(160.0) == 0.0

    def test_option_extrinsic_value(self):
        """Test extrinsic value calculation."""
        option = Option(
            underlying="AAPL",
            option_type="call",
            strike=150.0,
            expiration_date=date.today(),
        )

        underlying_price = 155.0
        option_price = 8.0
        option.get_intrinsic_value(underlying_price)  # 5.0
        extrinsic_value = option.get_extrinsic_value(underlying_price, option_price)

        assert extrinsic_value == 3.0  # 8.0 - 5.0

    def test_option_days_to_expiration(self):
        """Test days to expiration calculation."""
        exp_date = date.today() + timedelta(days=30)
        option = Option(
            underlying="AAPL",
            option_type="call",
            strike=150.0,
            expiration_date=exp_date,
        )

        # Current date
        days = option.get_days_to_expiration()
        assert days == 30

        # Specific date
        as_of_date = date.today() + timedelta(days=10)
        days = option.get_days_to_expiration(as_of_date)
        assert days == 20

        # DateTime input
        as_of_datetime = datetime.now() + timedelta(days=5)
        days = option.get_days_to_expiration(as_of_datetime)
        assert days == 25

    def test_option_moneyness_call(self):
        """Test moneyness methods for calls."""
        call_option = Option(
            underlying="AAPL",
            option_type="call",
            strike=150.0,
            expiration_date=date.today(),
        )

        # ITM call
        assert call_option.is_itm(160.0) is True
        assert call_option.is_otm(160.0) is False

        # OTM call
        assert call_option.is_itm(140.0) is False
        assert call_option.is_otm(140.0) is True

        # ATM call
        assert call_option.is_itm(150.0) is False
        assert call_option.is_otm(150.0) is True

    def test_option_moneyness_put(self):
        """Test moneyness methods for puts."""
        put_option = Option(
            underlying="AAPL",
            option_type="put",
            strike=150.0,
            expiration_date=date.today(),
        )

        # ITM put
        assert put_option.is_itm(140.0) is True
        assert put_option.is_otm(140.0) is False

        # OTM put
        assert put_option.is_itm(160.0) is False
        assert put_option.is_otm(160.0) is True

    def test_option_symbol_building(self):
        """Test option symbol building from components."""
        exp_date = date(2024, 1, 19)
        option = Option(
            underlying="AAPL",
            option_type="call",
            strike=195.5,  # Test decimal strike
            expiration_date=exp_date,
        )

        # Should build proper option symbol
        expected_symbol = "AAPL240119C00195500"  # 195.5 * 1000 = 195500
        assert option.symbol == expected_symbol

    def test_option_with_underlying_asset_failure(self):
        """Test option creation with invalid underlying."""
        with pytest.raises(ValueError, match="underlying asset could not be created"):
            Option(
                underlying=None,
                option_type="call",
                strike=100.0,
                expiration_date=date.today(),
            )


class TestCall:
    """Test the Call class."""

    def test_call_creation_from_symbol(self):
        """Test call creation from symbol."""
        call = Call(symbol="AAPL240119C00195000")

        assert call.symbol == "AAPL240119C00195000"
        assert call.option_type == "call"
        assert call.strike == 195.0
        assert isinstance(call, Option)
        assert isinstance(call, Call)

    def test_call_creation_from_components(self):
        """Test call creation from components."""
        call = Call(
            underlying="GOOGL", strike=2800.0, expiration_date=date(2024, 3, 15)
        )

        assert call.option_type == "call"
        assert call.strike == 2800.0
        assert call.underlying.symbol == "GOOGL"

    def test_call_forces_call_type(self):
        """Test that Call class forces option_type to be 'call'."""
        # Even if we don't specify option_type, it should be 'call'
        call = Call(underlying="TSLA", strike=800.0, expiration_date=date.today())
        assert call.option_type == "call"

    def test_call_inheritance(self):
        """Test call inheritance hierarchy."""
        call = Call(underlying="NVDA", strike=900.0, expiration_date=date.today())

        assert isinstance(call, Call)
        assert isinstance(call, Option)
        assert isinstance(call, Asset)

    def test_call_pricing_methods(self):
        """Test call-specific pricing methods."""
        call = Call(underlying="SPY", strike=450.0, expiration_date=date.today())

        # ITM call
        assert call.get_intrinsic_value(460.0) == 10.0
        assert call.is_itm(460.0) is True

        # OTM call
        assert call.get_intrinsic_value(440.0) == 0.0
        assert call.is_otm(440.0) is True


class TestPut:
    """Test the Put class."""

    def test_put_creation_from_symbol(self):
        """Test put creation from symbol."""
        put = Put(symbol="AAPL240119P00195000")

        assert put.symbol == "AAPL240119P00195000"
        assert put.option_type == "put"
        assert put.strike == 195.0
        assert isinstance(put, Option)
        assert isinstance(put, Put)

    def test_put_creation_from_components(self):
        """Test put creation from components."""
        put = Put(underlying="QQQ", strike=380.0, expiration_date=date(2024, 6, 21))

        assert put.option_type == "put"
        assert put.strike == 380.0
        assert put.underlying.symbol == "QQQ"

    def test_put_forces_put_type(self):
        """Test that Put class forces option_type to be 'put'."""
        put = Put(underlying="IWM", strike=200.0, expiration_date=date.today())
        assert put.option_type == "put"

    def test_put_inheritance(self):
        """Test put inheritance hierarchy."""
        put = Put(underlying="VTI", strike=220.0, expiration_date=date.today())

        assert isinstance(put, Put)
        assert isinstance(put, Option)
        assert isinstance(put, Asset)

    def test_put_pricing_methods(self):
        """Test put-specific pricing methods."""
        put = Put(underlying="SPY", strike=450.0, expiration_date=date.today())

        # ITM put
        assert put.get_intrinsic_value(440.0) == 10.0
        assert put.is_itm(440.0) is True

        # OTM put
        assert put.get_intrinsic_value(460.0) == 0.0
        assert put.is_otm(460.0) is True


class TestAssetEdgeCases:
    """Test edge cases and error conditions for asset models."""

    def test_option_symbol_parsing_precision(self):
        """Test option symbol parsing with different strike precisions."""
        # Test various strike prices and their symbol representation
        test_cases = [
            (100.0, "00100000"),  # Whole number
            (100.5, "00100500"),  # Half dollar
            (100.25, "00100250"),  # Quarter
            (1.0, "00001000"),  # Small strike
            (9999.99, "99999900"),  # Large strike (capped at 8 digits)
        ]

        for strike, expected_strike_part in test_cases:
            option = Option(
                underlying="TEST",
                option_type="call",
                strike=strike,
                expiration_date=date(2024, 1, 19),
            )
            assert expected_strike_part in option.symbol

    def test_option_symbol_parsing_underlyings(self):
        """Test option symbol parsing with various underlying symbols."""
        test_underlyings = [
            "A",  # Single character
            "BRK.B",  # With dot
            "LONGNAME",  # Long name
            "TEST123",  # With numbers
        ]

        for underlying in test_underlyings:
            option = Option(symbol=f"{underlying}240119C00100000")
            assert option.underlying.symbol == underlying

    def test_asset_equality_edge_cases(self):
        """Test asset equality edge cases."""
        asset = Asset(symbol="TEST")

        # Test with empty string
        assert asset != ""

        # Test with None
        assert asset is not None

        # Test with whitespace-only string
        assert asset != "   "

        # Test case sensitivity in string comparison
        assert asset == "test"
        assert asset == "TeSt"

    def test_option_expiration_edge_cases(self):
        """Test option expiration edge cases."""
        # Past expiration date
        past_date = date.today() - timedelta(days=30)
        option = Option(
            underlying="AAPL",
            option_type="call",
            strike=150.0,
            expiration_date=past_date,
        )

        days = option.get_days_to_expiration()
        assert days == -30  # Negative days for expired options

        # Same day expiration
        today = date.today()
        option_today = Option(
            underlying="AAPL", option_type="call", strike=150.0, expiration_date=today
        )
        assert option_today.get_days_to_expiration() == 0

    def test_option_intrinsic_value_edge_cases(self):
        """Test intrinsic value calculation edge cases."""
        call = Option(
            underlying="TEST",
            option_type="call",
            strike=100.0,
            expiration_date=date.today(),
        )
        put = Option(
            underlying="TEST",
            option_type="put",
            strike=100.0,
            expiration_date=date.today(),
        )

        # Exactly at strike
        assert call.get_intrinsic_value(100.0) == 0.0
        assert put.get_intrinsic_value(100.0) == 0.0

        # Very small differences
        assert call.get_intrinsic_value(100.01) == 0.01
        assert put.get_intrinsic_value(99.99) == 0.01

        # Large differences
        assert call.get_intrinsic_value(200.0) == 100.0
        assert put.get_intrinsic_value(0.0) == 100.0

    def test_asset_with_none_fields(self):
        """Test asset behavior with None values in optional fields."""
        asset = Asset(
            symbol="TEST",
            underlying=None,
            option_type=None,
            strike=None,
            expiration_date=None,
        )

        assert asset.underlying is None
        assert asset.option_type is None
        assert asset.strike is None
        assert asset.expiration_date is None

    def test_option_invalid_symbol_formats(self):
        """Test various invalid option symbol formats."""
        invalid_symbols = [
            "AAPL",  # Too short
            "AAPL240119X00100000",  # Invalid option type
            "AAPL240119C",  # Missing strike
            "AAPL240199C00100000",  # Invalid date
            "240119C00100000",  # Missing underlying
            "",  # Empty string
        ]

        for invalid_symbol in invalid_symbols:
            if len(invalid_symbol) <= 8:  # Short symbols go to stock
                continue
            with pytest.raises(ValueError):
                Option(symbol=invalid_symbol)

    def test_complex_asset_inheritance_chain(self):
        """Test complex inheritance and isinstance checks."""
        stock = Stock("AAPL")
        generic_option = Option(
            underlying="AAPL",
            option_type="call",
            strike=150.0,
            expiration_date=date.today(),
        )
        call = Call(underlying="AAPL", strike=150.0, expiration_date=date.today())
        put = Put(underlying="AAPL", strike=150.0, expiration_date=date.today())

        # Test inheritance hierarchy
        assert isinstance(stock, Asset)
        assert not isinstance(stock, Option)

        assert isinstance(generic_option, Asset)
        assert isinstance(generic_option, Option)
        assert not isinstance(generic_option, Call)
        assert not isinstance(generic_option, Put)

        assert isinstance(call, Asset)
        assert isinstance(call, Option)
        assert isinstance(call, Call)
        assert not isinstance(call, Put)

        assert isinstance(put, Asset)
        assert isinstance(put, Option)
        assert not isinstance(put, Call)
        assert isinstance(put, Put)

    def test_asset_factory_with_malformed_inputs(self):
        """Test asset factory with various malformed inputs."""
        # Empty string
        result = asset_factory("")
        assert isinstance(result, Stock)
        assert result.symbol == ""  # Edge case, but should still create

        # String with only whitespace
        result = asset_factory("   ")
        assert isinstance(result, Stock)
        assert result.symbol == ""  # After stripping

        # Very long symbol
        long_symbol = "A" * 50
        result = asset_factory(long_symbol)
        assert isinstance(result, Option)  # Length > 8

    def test_option_date_formats_comprehensive(self):
        """Test comprehensive date format support."""
        date_formats = [
            ("2024-03-15", date(2024, 3, 15)),
            ("240315", date(2024, 3, 15)),
            ("20240315", date(2024, 3, 15)),
        ]

        for date_str, expected_date in date_formats:
            option = Option(
                underlying="AAPL",
                option_type="call",
                strike=150.0,
                expiration_date=date_str,
            )
            assert option.expiration_date == expected_date
