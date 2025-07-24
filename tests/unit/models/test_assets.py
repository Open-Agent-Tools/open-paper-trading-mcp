"""
Comprehensive test suite for app.models.assets module.

Tests cover:
- Asset base class validation and methods
- Stock class creation and validation
- Option class parsing and validation
- Call and Put classes
- Factory methods and edge cases
- Symbol normalization and validation
- Option symbol parsing and creation
- Intrinsic/extrinsic value calculations
- Date parsing and handling
"""

from datetime import date, datetime

import pytest
from pydantic import ValidationError

from app.models.assets import (
    Asset,
    Call,
    Option,
    OptionType,
    Put,
    Stock,
    asset_factory,
)


class TestAssetBaseClass:
    """Test the Asset base class functionality."""

    def test_asset_creation_basic(self):
        """Test basic asset creation with required fields."""
        asset = Asset(symbol="AAPL")
        assert asset.symbol == "AAPL"
        assert asset.asset_type == "stock"
        assert asset.underlying is None
        assert asset.option_type is None
        assert asset.strike is None
        assert asset.expiration_date is None

    def test_asset_symbol_normalization(self):
        """Test that symbols are normalized to uppercase."""
        asset = Asset(symbol="  aapl  ")
        assert asset.symbol == "AAPL"

    def test_asset_frozen_model(self):
        """Test that Asset is immutable (frozen)."""
        asset = Asset(symbol="AAPL")
        with pytest.raises(ValidationError):
            asset.symbol = "GOOGL"

    def test_asset_equality_by_symbol(self):
        """Test asset equality is based on symbol."""
        asset1 = Asset(symbol="AAPL")
        asset2 = Asset(symbol="AAPL")
        asset3 = Asset(symbol="GOOGL")

        assert asset1 == asset2
        assert asset1 != asset3
        assert asset1 == "AAPL"
        assert asset1 == "aapl"  # Case insensitive
        assert asset1 != "GOOGL"
        assert asset1 != 123  # Different type

    def test_asset_hash_by_symbol(self):
        """Test asset hashing is based on symbol."""
        asset1 = Asset(symbol="AAPL")
        asset2 = Asset(symbol="AAPL")

        assert hash(asset1) == hash(asset2)
        assert {asset1, asset2} == {asset1}  # Same in set

    def test_asset_with_all_fields(self):
        """Test asset creation with all optional fields."""
        underlying = Asset(symbol="AAPL")
        exp_date = date(2024, 12, 20)

        asset = Asset(
            symbol="AAPL241220C00195000",
            asset_type="call",
            underlying=underlying,
            option_type="call",
            strike=195.0,
            expiration_date=exp_date,
        )

        assert asset.symbol == "AAPL241220C00195000"
        assert asset.asset_type == "call"
        assert asset.underlying == underlying
        assert asset.option_type == "call"
        assert asset.strike == 195.0
        assert asset.expiration_date == exp_date


class TestStockClass:
    """Test the Stock class functionality."""

    def test_stock_creation(self):
        """Test stock creation sets correct asset type."""
        stock = Stock(symbol="AAPL")
        assert stock.symbol == "AAPL"
        assert stock.asset_type == "stock"
        assert stock.underlying is None

    def test_stock_symbol_normalization(self):
        """Test stock symbol normalization."""
        stock = Stock(symbol="  aapl  ")
        assert stock.symbol == "AAPL"

    def test_stock_with_extra_data(self):
        """Test stock creation with additional data."""
        stock = Stock(symbol="AAPL", extra_field="test")
        assert stock.symbol == "AAPL"
        assert stock.asset_type == "stock"


class TestOptionType:
    """Test the OptionType enum."""

    def test_option_type_values(self):
        """Test OptionType enum values."""
        assert OptionType.CALL == "call"
        assert OptionType.PUT == "put"

    def test_option_type_membership(self):
        """Test membership in OptionType enum."""
        assert "call" in [ot.value for ot in OptionType]
        assert "put" in [ot.value for ot in OptionType]
        assert "invalid" not in [ot.value for ot in OptionType]


class TestOptionClass:
    """Test the Option class functionality."""

    def test_option_from_symbol_parsing(self):
        """Test option creation from option symbol."""
        option = Option(symbol="AAPL241220C00195000")

        assert option.symbol == "AAPL241220C00195000"
        assert option.asset_type == "call"
        assert option.underlying.symbol == "AAPL"
        assert option.option_type == "call"
        assert option.strike == 195.0
        assert option.expiration_date == date(2024, 12, 20)

    def test_option_from_symbol_parsing_put(self):
        """Test option creation from put option symbol."""
        option = Option(symbol="AAPL241220P00195000")

        assert option.symbol == "AAPL241220P00195000"
        assert option.asset_type == "put"
        assert option.underlying.symbol == "AAPL"
        assert option.option_type == "put"
        assert option.strike == 195.0
        assert option.expiration_date == date(2024, 12, 20)

    def test_option_from_components(self):
        """Test option creation from individual components."""
        option = Option(
            underlying="AAPL",
            option_type="call",
            strike=195.0,
            expiration_date="2024-12-20",
        )

        assert option.symbol == "AAPL241220C00195000"
        assert option.asset_type == "call"
        assert option.underlying.symbol == "AAPL"
        assert option.option_type == "call"
        assert option.strike == 195.0
        assert option.expiration_date == date(2024, 12, 20)

    def test_option_from_components_with_asset(self):
        """Test option creation with Asset object as underlying."""
        underlying_asset = Stock(symbol="AAPL")
        option = Option(
            underlying=underlying_asset,
            option_type="put",
            strike=180.0,
            expiration_date=date(2024, 12, 20),
        )

        assert option.underlying == underlying_asset
        assert option.option_type == "put"
        assert option.strike == 180.0

    def test_option_validation_errors(self):
        """Test option validation errors."""
        # Missing underlying
        with pytest.raises(ValueError, match="underlying asset is required"):
            Option(option_type="call", strike=195.0, expiration_date="2024-12-20")

        # Invalid option type
        with pytest.raises(ValueError, match="option_type must be 'call' or 'put'"):
            Option(
                underlying="AAPL",
                option_type="invalid",
                strike=195.0,
                expiration_date="2024-12-20",
            )

        # Invalid strike
        with pytest.raises(ValueError, match="strike must be positive"):
            Option(
                underlying="AAPL",
                option_type="call",
                strike=-195.0,
                expiration_date="2024-12-20",
            )

        # Missing strike
        with pytest.raises(ValueError, match="strike must be positive"):
            Option(
                underlying="AAPL",
                option_type="call",
                strike=0,
                expiration_date="2024-12-20",
            )

        # Missing expiration
        with pytest.raises(ValueError, match="expiration_date is required"):
            Option(underlying="AAPL", option_type="call", strike=195.0)

    def test_option_symbol_parsing_invalid(self):
        """Test invalid option symbol parsing."""
        with pytest.raises(ValueError, match="Invalid option symbol format"):
            Option(symbol="INVALID")

        with pytest.raises(ValueError, match="Invalid option symbol format"):
            Option(symbol="AAPL")  # Too short

        with pytest.raises(ValueError, match="Invalid option symbol format"):
            Option(symbol="AAPL24122X00195000")  # Invalid option type

    def test_option_date_parsing(self):
        """Test various date parsing formats."""
        test_cases = [
            ("2024-12-20", date(2024, 12, 20)),
            ("241220", date(2024, 12, 20)),
            ("20241220", date(2024, 12, 20)),
            (date(2024, 12, 20), date(2024, 12, 20)),
            (datetime(2024, 12, 20, 15, 30), date(2024, 12, 20)),
        ]

        for date_input, expected in test_cases:
            option = Option(
                underlying="AAPL",
                option_type="call",
                strike=195.0,
                expiration_date=date_input,
            )
            assert option.expiration_date == expected

    def test_option_date_parsing_invalid(self):
        """Test invalid date parsing."""
        with pytest.raises(ValueError, match="Could not parse date"):
            Option(
                underlying="AAPL",
                option_type="call",
                strike=195.0,
                expiration_date="invalid-date",
            )

        with pytest.raises(ValueError, match="Invalid date type"):
            Option(
                underlying="AAPL",
                option_type="call",
                strike=195.0,
                expiration_date=123,  # Invalid type
            )

    def test_option_intrinsic_value(self):
        """Test intrinsic value calculation."""
        call_option = Option(
            underlying="AAPL",
            option_type="call",
            strike=195.0,
            expiration_date="2024-12-20",
        )

        put_option = Option(
            underlying="AAPL",
            option_type="put",
            strike=195.0,
            expiration_date="2024-12-20",
        )

        # Call option intrinsic value
        assert call_option.get_intrinsic_value(200.0) == 5.0  # ITM
        assert call_option.get_intrinsic_value(195.0) == 0.0  # ATM
        assert call_option.get_intrinsic_value(190.0) == 0.0  # OTM

        # Put option intrinsic value
        assert put_option.get_intrinsic_value(190.0) == 5.0  # ITM
        assert put_option.get_intrinsic_value(195.0) == 0.0  # ATM
        assert put_option.get_intrinsic_value(200.0) == 0.0  # OTM

    def test_option_extrinsic_value(self):
        """Test extrinsic value calculation."""
        option = Option(
            underlying="AAPL",
            option_type="call",
            strike=195.0,
            expiration_date="2024-12-20",
        )

        # Option price $10, underlying $200, intrinsic $5, extrinsic $5
        assert option.get_extrinsic_value(200.0, 10.0) == 5.0

        # Option price $3, underlying $190, intrinsic $0, extrinsic $3
        assert option.get_extrinsic_value(190.0, 3.0) == 3.0

    def test_option_days_to_expiration(self):
        """Test days to expiration calculation."""
        option = Option(
            underlying="AAPL",
            option_type="call",
            strike=195.0,
            expiration_date=date(2024, 12, 20),
        )

        # Test with specific date
        test_date = date(2024, 12, 10)
        assert option.get_days_to_expiration(test_date) == 10

        # Test with datetime
        test_datetime = datetime(2024, 12, 10, 15, 30)
        assert option.get_days_to_expiration(test_datetime) == 10

    def test_option_moneyness_checks(self):
        """Test ITM/OTM checks."""
        call_option = Option(
            underlying="AAPL",
            option_type="call",
            strike=195.0,
            expiration_date="2024-12-20",
        )

        put_option = Option(
            underlying="AAPL",
            option_type="put",
            strike=195.0,
            expiration_date="2024-12-20",
        )

        # Call option moneyness
        assert call_option.is_itm(200.0) is True
        assert call_option.is_otm(200.0) is False
        assert call_option.is_itm(190.0) is False
        assert call_option.is_otm(190.0) is True

        # Put option moneyness
        assert put_option.is_itm(190.0) is True
        assert put_option.is_otm(190.0) is False
        assert put_option.is_itm(200.0) is False
        assert put_option.is_otm(200.0) is True


class TestCallClass:
    """Test the Call class functionality."""

    def test_call_from_symbol(self):
        """Test call creation from symbol."""
        call = Call(symbol="AAPL241220C00195000")

        assert call.option_type == "call"
        assert call.asset_type == "call"
        assert call.strike == 195.0

    def test_call_from_components(self):
        """Test call creation from components."""
        call = Call(underlying="AAPL", strike=195.0, expiration_date="2024-12-20")

        assert call.option_type == "call"
        assert call.asset_type == "call"
        assert call.strike == 195.0
        assert call.underlying.symbol == "AAPL"


class TestPutClass:
    """Test the Put class functionality."""

    def test_put_from_symbol(self):
        """Test put creation from symbol."""
        put = Put(symbol="AAPL241220P00195000")

        assert put.option_type == "put"
        assert put.asset_type == "put"
        assert put.strike == 195.0

    def test_put_from_components(self):
        """Test put creation from components."""
        put = Put(underlying="AAPL", strike=195.0, expiration_date="2024-12-20")

        assert put.option_type == "put"
        assert put.asset_type == "put"
        assert put.strike == 195.0
        assert put.underlying.symbol == "AAPL"


class TestAssetFactory:
    """Test the asset_factory function."""

    def test_factory_with_none(self):
        """Test factory returns None for None input."""
        assert asset_factory(None) is None

    def test_factory_with_asset_passthrough(self):
        """Test factory passes through Asset objects."""
        asset = Stock(symbol="AAPL")
        result = asset_factory(asset)
        assert result is asset

    def test_factory_stock_creation(self):
        """Test factory creates Stock for short symbols."""
        stock = asset_factory("AAPL")
        assert isinstance(stock, Stock)
        assert stock.symbol == "AAPL"

    def test_factory_option_creation_call(self):
        """Test factory creates Call for call option symbols."""
        call = asset_factory("AAPL241220C00195000")
        assert isinstance(call, Call)
        assert call.option_type == "call"

    def test_factory_option_creation_put(self):
        """Test factory creates Put for put option symbols."""
        put = asset_factory("AAPL241220P00195000")
        assert isinstance(put, Put)
        assert put.option_type == "put"

    def test_factory_generic_option(self):
        """Test factory creates generic Option for ambiguous symbols."""
        # Long symbol without clear call/put indicator
        option = asset_factory("AAPL241220X00195000")
        assert isinstance(option, Option)
        assert not isinstance(option, Call | Put)

    def test_factory_symbol_normalization(self):
        """Test factory normalizes symbols."""
        stock = asset_factory("  aapl  ")
        assert stock.symbol == "AAPL"


class TestEdgeCasesAndValidation:
    """Test edge cases and comprehensive validation."""

    def test_empty_symbol_validation(self):
        """Test empty symbol validation."""
        with pytest.raises(ValidationError):
            Asset(symbol="")

        with pytest.raises(ValidationError):
            Asset(symbol="  ")

    def test_option_symbol_parsing_edge_cases(self):
        """Test option symbol parsing edge cases."""
        # Very short underlying symbol
        option = Option(symbol="A241220C00195000")
        assert option.underlying.symbol == "A"

        # Longer underlying symbol
        option = Option(symbol="BERKB241220C00195000")
        assert option.underlying.symbol == "BERKB"

        # Different strike prices
        test_cases = [
            ("AAPL241220C00010000", 10.0),
            ("AAPL241220C00000500", 0.5),
            ("AAPL241220C01000000", 1000.0),
        ]

        for symbol, expected_strike in test_cases:
            option = Option(symbol=symbol)
            assert option.strike == expected_strike

    def test_option_symbol_generation(self):
        """Test option symbol generation from components."""
        test_cases = [
            ("AAPL", "call", 195.0, "2024-12-20", "AAPL241220C00195000"),
            ("AAPL", "put", 180.5, "2024-01-19", "AAPL240119P00180500"),
            ("GOOGL", "call", 2500.0, "2024-06-21", "GOOGL240621C02500000"),
        ]

        for underlying, option_type, strike, exp_date, expected_symbol in test_cases:
            option = Option(
                underlying=underlying,
                option_type=option_type,
                strike=strike,
                expiration_date=exp_date,
            )
            assert option.symbol == expected_symbol

    def test_underlying_asset_creation_failure(self):
        """Test handling when underlying asset creation fails."""
        # This should raise an error when underlying is None after factory
        with pytest.raises(ValueError, match="underlying asset could not be created"):
            Option(
                underlying=None,
                option_type="call",
                strike=195.0,
                expiration_date="2024-12-20",
            )

    def test_complex_option_scenarios(self):
        """Test complex option scenarios."""
        # Weekly options
        weekly_option = Option(symbol="AAPL241206C00195000")
        assert weekly_option.expiration_date == date(2024, 12, 6)

        # LEAPS (long-term options)
        leaps_option = Option(symbol="AAPL260115C00195000")
        assert leaps_option.expiration_date == date(2026, 1, 15)

        # High strike prices
        high_strike = Option(symbol="AAPL241220C09999900")
        assert high_strike.strike == 99999.0

    def test_asset_type_consistency(self):
        """Test asset type consistency across classes."""
        stock = Stock(symbol="AAPL")
        assert stock.asset_type == "stock"

        call = Call(underlying="AAPL", strike=195.0, expiration_date="2024-12-20")
        assert call.asset_type == "call"

        put = Put(underlying="AAPL", strike=195.0, expiration_date="2024-12-20")
        assert put.asset_type == "put"

        # Generic option should use option_type for asset_type
        option = Option(
            underlying="AAPL",
            option_type="call",
            strike=195.0,
            expiration_date="2024-12-20",
        )
        assert option.asset_type == "call"

    @pytest.mark.parametrize(
        "underlying_price,call_strike,put_strike,expected_call,expected_put",
        [
            (100.0, 95.0, 105.0, 5.0, 5.0),  # Both ITM
            (100.0, 105.0, 95.0, 0.0, 0.0),  # Both OTM
            (100.0, 100.0, 100.0, 0.0, 0.0),  # Both ATM
            (150.0, 100.0, 200.0, 50.0, 50.0),  # Deep ITM
        ],
    )
    def test_parametrized_intrinsic_values(
        self, underlying_price, call_strike, put_strike, expected_call, expected_put
    ):
        """Test intrinsic value calculations with various scenarios."""
        call = Call(underlying="AAPL", strike=call_strike, expiration_date="2024-12-20")
        put = Put(underlying="AAPL", strike=put_strike, expiration_date="2024-12-20")

        assert call.get_intrinsic_value(underlying_price) == expected_call
        assert put.get_intrinsic_value(underlying_price) == expected_put
