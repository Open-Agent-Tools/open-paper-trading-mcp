"""
Comprehensive tests for asset models - Phase 5.1 implementation.
Tests option symbol parsing, asset factory, intrinsic/extrinsic calculations, and edge cases.
"""

import pytest
from datetime import datetime, date, timedelta

from app.models.assets import Asset, Option, Call, Put, asset_factory


class TestAssetBase:
    """Test the base Asset class functionality."""

    def test_asset_creation(self) -> None:
        """Test basic asset creation and symbol normalization."""
        asset = Asset(symbol="AAPL")
        assert asset.symbol == "AAPL"
        assert str(asset) == "AAPL"

    def test_asset_symbol_normalization(self) -> None:
        """Test symbol normalization (uppercase, whitespace removal)."""
        asset = Asset(symbol="  aapl  ")
        assert asset.symbol == "AAPL"

    def test_asset_equality(self) -> None:
        """Test asset equality comparison."""
        asset1 = Asset(symbol="AAPL")
        asset2 = Asset(symbol="AAPL")
        asset3 = Asset(symbol="GOOGL")

        assert asset1 == asset2
        assert asset1 != asset3
        assert hash(asset1) == hash(asset2)
        assert hash(asset1) != hash(asset3)


class TestAssetFactory:
    """Test the asset_factory function for polymorphic asset creation."""

    def test_stock_creation(self) -> None:
        """Test creating stock assets via factory."""
        asset = asset_factory("AAPL")
        assert isinstance(asset, Asset)
        assert not isinstance(asset, Option)
        assert asset.symbol == "AAPL"

    def test_option_creation_call(self) -> None:
        """Test creating call option via factory."""
        option = asset_factory("AAPL240119C00195000")
        assert isinstance(option, Call)
        assert isinstance(option, Option)
        assert option.symbol == "AAPL240119C00195000"

    def test_option_creation_put(self) -> None:
        """Test creating put option via factory."""
        option = asset_factory("AAPL240119P00195000")
        assert isinstance(option, Put)
        assert isinstance(option, Option)
        assert option.symbol == "AAPL240119P00195000"

    def test_invalid_symbol(self) -> None:
        """Test factory with invalid symbol."""
        with pytest.raises(ValueError, match="Invalid option symbol format"):
            asset_factory("INVALID_SYMBOL")


class TestOptionSymbolParsing:
    """Test option symbol parsing with various formats and edge cases."""

    def test_standard_option_parsing(self) -> None:
        """Test parsing standard option symbols (AAPL240119C00195000)."""
        option = Option(symbol="AAPL240119C00195000")

        assert option.underlying.symbol == "AAPL"
        assert option.expiration_date == date(2024, 1, 19)
        assert option.option_type == "call"
        assert option.strike == 195.0

    def test_different_strikes(self) -> None:
        """Test parsing options with different strike prices."""
        # Low strike
        option1 = Option(symbol="AAPL240119C00050000")
        assert option1.strike == 50.0

        # High strike
        option2 = Option(symbol="AAPL240119C00500000")
        assert option2.strike == 500.0

        # Fractional strike
        option3 = Option(symbol="AAPL240119C00195500")
        assert option3.strike == 195.5

    def test_different_expirations(self) -> None:
        """Test parsing options with different expiration dates."""
        # Near-term expiration
        option1 = Option(symbol="AAPL241220C00195000")
        assert option1.expiration_date == date(2024, 12, 20)

        # Far-term expiration
        option2 = Option(symbol="AAPL260116C00195000")
        assert option2.expiration_date == date(2026, 1, 16)

    def test_different_underlyings(self) -> None:
        """Test parsing options with different underlying symbols."""
        # Single letter
        option1 = Option(symbol="F240119C00195000")
        assert option1.underlying.symbol == "F"

        # Multiple letters
        option2 = Option(symbol="GOOGL240119C00195000")
        assert option2.underlying.symbol == "GOOGL"

        # With numbers
        option3 = Option(symbol="BRK240119C00195000")
        assert option3.underlying.symbol == "BRK"

    def test_invalid_option_symbols(self) -> None:
        """Test parsing invalid option symbols."""
        invalid_symbols = [
            "AAPL",  # Too short
            "AAPL240119",  # Missing option type and strike
            "AAPL240119X00195000",  # Invalid option type
            "AAPL240230C00195000",  # Invalid date
            "AAPL24C00195000",  # Too short date
            "",  # Empty string
        ]

        for symbol in invalid_symbols:
            with pytest.raises(ValueError, match="Invalid option symbol format"):
                Option(symbol=symbol)


class TestCallOption:
    """Test Call option specific functionality."""

    def test_call_creation(self) -> None:
        """Test creating call options."""
        call = Call(symbol="AAPL240119C00195000")
        assert call.option_type == "call"
        assert isinstance(call, Option)
        assert isinstance(call, Call)

    def test_call_intrinsic_value(self) -> None:
        """Test intrinsic value calculations for calls."""
        call = Call(symbol="AAPL240119C00195000")  # Strike 195

        # ITM: underlying > strike
        assert call.get_intrinsic_value(200.0) == 5.0
        assert call.get_intrinsic_value(210.0) == 15.0

        # ATM: underlying = strike
        assert call.get_intrinsic_value(195.0) == 0.0

        # OTM: underlying < strike
        assert call.get_intrinsic_value(190.0) == 0.0
        assert call.get_intrinsic_value(180.0) == 0.0

    def test_call_itm_otm_status(self) -> None:
        """Test ITM/OTM status for calls."""
        call = Call(symbol="AAPL240119C00195000")

        # ITM
        assert call.is_itm(200.0) is True
        assert call.is_otm(200.0) is False

        # ATM
        assert call.is_itm(195.0) is False
        assert call.is_otm(195.0) is True

        # OTM
        assert call.is_itm(190.0) is False
        assert call.is_otm(190.0) is True


class TestPutOption:
    """Test Put option specific functionality."""

    def test_put_creation(self) -> None:
        """Test creating put options."""
        put = Put(symbol="AAPL240119P00195000")
        assert put.option_type == "put"
        assert isinstance(put, Option)
        assert isinstance(put, Put)

    def test_put_intrinsic_value(self) -> None:
        """Test intrinsic value calculations for puts."""
        put = Put(symbol="AAPL240119P00195000")  # Strike 195

        # ITM: underlying < strike
        assert put.get_intrinsic_value(190.0) == 5.0
        assert put.get_intrinsic_value(180.0) == 15.0

        # ATM: underlying = strike
        assert put.get_intrinsic_value(195.0) == 0.0

        # OTM: underlying > strike
        assert put.get_intrinsic_value(200.0) == 0.0
        assert put.get_intrinsic_value(210.0) == 0.0

    def test_put_itm_otm_status(self) -> None:
        """Test ITM/OTM status for puts."""
        put = Put(symbol="AAPL240119P00195000")

        # ITM
        assert put.is_itm(190.0) is True
        assert put.is_otm(190.0) is False

        # ATM
        assert put.is_itm(195.0) is False
        assert put.is_otm(195.0) is True

        # OTM
        assert put.is_itm(200.0) is False
        assert put.is_otm(200.0) is True


class TestExtrinsicValue:
    """Test extrinsic value calculations."""

    def test_call_extrinsic_value(self) -> None:
        """Test extrinsic value for calls."""
        call = Call(symbol="AAPL240119C00195000")

        # ITM call with premium
        market_price = 7.50
        underlying_price = 200.0  # $5 intrinsic
        extrinsic = call.get_extrinsic_value(underlying_price, market_price)
        assert extrinsic == 2.50  # 7.50 - 5.00

        # OTM call (all extrinsic)
        market_price = 3.00
        underlying_price = 190.0  # $0 intrinsic
        extrinsic = call.get_extrinsic_value(underlying_price, market_price)
        assert extrinsic == 3.00

    def test_put_extrinsic_value(self) -> None:
        """Test extrinsic value for puts."""
        put = Put(symbol="AAPL240119P00195000")

        # ITM put with premium
        market_price = 8.00
        underlying_price = 190.0  # $5 intrinsic
        extrinsic = put.get_extrinsic_value(underlying_price, market_price)
        assert extrinsic == 3.00  # 8.00 - 5.00

        # OTM put (all extrinsic)
        market_price = 2.50
        underlying_price = 200.0  # $0 intrinsic
        extrinsic = put.get_extrinsic_value(underlying_price, market_price)
        assert extrinsic == 2.50


class TestDaysToExpiration:
    """Test days to expiration calculations with edge cases."""

    def test_days_to_expiration_future(self) -> None:
        """Test days to expiration for future dates."""
        option = Option(symbol="AAPL240119C00195000")  # Jan 19, 2024

        # Test from Jan 1, 2024 (18 days before)
        current_date = date(2024, 1, 1)
        days = option.get_days_to_expiration(current_date)
        assert days == 18

        # Test from Jan 10, 2024 (9 days before)
        current_date = date(2024, 1, 10)
        days = option.get_days_to_expiration(current_date)
        assert days == 9

    def test_days_to_expiration_same_day(self) -> None:
        """Test days to expiration on expiration day."""
        option = Option(symbol="AAPL240119C00195000")
        current_date = date(2024, 1, 19)
        days = option.get_days_to_expiration(current_date)
        assert days == 0

    def test_days_to_expiration_past(self) -> None:
        """Test days to expiration for expired options."""
        option = Option(symbol="AAPL240119C00195000")
        current_date = date(2024, 1, 25)  # 6 days after expiration
        days = option.get_days_to_expiration(current_date)
        assert days == -6

    def test_days_to_expiration_default_current_date(self) -> None:
        """Test days to expiration using current date when not specified."""
        # Create an option that expires far in the future
        future_date = datetime.now().date() + timedelta(days=365)
        year = future_date.year % 100  # Last 2 digits
        month = f"{future_date.month:02d}"
        day = f"{future_date.day:02d}"
        symbol = f"AAPL{year}{month}{day}C00195000"

        option = Option(symbol=symbol)
        days = option.get_days_to_expiration()
        assert days >= 364  # Should be around 365 days


class TestOptionEdgeCases:
    """Test edge cases and error conditions."""

    def test_zero_strike_option(self) -> None:
        """Test option with zero strike (should be invalid)."""
        with pytest.raises(ValueError, match="strike must be positive"):
            Option(symbol="AAPL240119C00000000")

    def test_very_high_strike(self) -> None:
        """Test option with very high strike."""
        option = Option(symbol="AAPL240119C09999900")
        assert option.strike == 9999.9

    def test_leap_year_expiration(self) -> None:
        """Test option expiring on leap year date."""
        option = Option(symbol="AAPL240229C00195000")  # Feb 29, 2024 (leap year)
        assert option.expiration_date == date(2024, 2, 29)

    def test_option_repr(self) -> None:
        """Test string representation of options."""
        call = Call(symbol="AAPL240119C00195000")
        put = Put(symbol="AAPL240119P00195000")

        assert "AAPL" in str(call)
        assert "Call" in repr(call)
        assert "Put" in repr(put)

    def test_negative_underlying_price(self) -> None:
        """Test intrinsic value with negative underlying price (edge case)."""
        call = Call(symbol="AAPL240119C00195000")
        put = Put(symbol="AAPL240119P00195000")

        # Negative prices should still work mathematically
        assert call.get_intrinsic_value(-10.0) == 0.0
        assert put.get_intrinsic_value(-10.0) == 205.0


class TestOptionPerformance:
    """Test performance characteristics of option operations."""

    def test_symbol_parsing_performance(self) -> None:
        """Test that symbol parsing is fast enough for bulk operations."""
        import time

        symbols = [
            f"AAPL240119C00{strike:05d}00"
            for strike in range(100, 300, 5)  # 40 different strikes
        ]

        start_time = time.time()
        options = [Option(symbol=symbol) for symbol in symbols]
        end_time = time.time()

        # Should parse 40 option symbols in well under a second
        assert end_time - start_time < 1.0
        assert len(options) == 40

    def test_intrinsic_value_calculation_performance(self) -> None:
        """Test intrinsic value calculation performance."""
        import time

        option = Call(symbol="AAPL240119C00195000")
        prices = [float(price) for price in range(150, 250)]  # 100 prices

        start_time = time.time()
        intrinsic_values = [option.get_intrinsic_value(price) for price in prices]
        end_time = time.time()

        # Should calculate 100 intrinsic values very quickly
        assert end_time - start_time < 0.1
        assert len(intrinsic_values) == 100
