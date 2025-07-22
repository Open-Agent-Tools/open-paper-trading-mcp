"""
Advanced test coverage for trading schemas.

Tests stock quote schemas, market data validation, serialization,
and trading-related data transfer objects.
"""

from datetime import UTC, datetime

import pytest
from pydantic import ValidationError

from app.schemas.trading import StockQuote


class TestStockQuoteSchema:
    """Test StockQuote schema validation and functionality."""

    def test_stock_quote_creation_basic(self):
        """Test creating basic stock quote."""
        timestamp = datetime.now(UTC)

        quote = StockQuote(
            symbol="AAPL",
            price=155.50,
            change=2.75,
            change_percent=1.80,
            volume=45_000_000,
            last_updated=timestamp,
        )

        assert quote.symbol == "AAPL"
        assert quote.price == 155.50
        assert quote.change == 2.75
        assert quote.change_percent == 1.80
        assert quote.volume == 45_000_000
        assert quote.last_updated == timestamp

    def test_stock_quote_creation_all_fields(self):
        """Test creating stock quote with all field variations."""
        timestamp = datetime(2024, 1, 15, 14, 30, 0, tzinfo=UTC)

        quote = StockQuote(
            symbol="GOOGL",
            price=2850.25,
            change=-15.75,
            change_percent=-0.55,
            volume=1_250_000,
            last_updated=timestamp,
        )

        assert quote.symbol == "GOOGL"
        assert quote.price == 2850.25
        assert quote.change == -15.75
        assert quote.change_percent == -0.55
        assert quote.volume == 1_250_000
        assert quote.last_updated == timestamp

    def test_stock_quote_required_fields(self):
        """Test that all StockQuote fields are required."""
        # Test missing symbol
        with pytest.raises(ValidationError) as exc_info:
            StockQuote(
                price=155.50,
                change=2.75,
                change_percent=1.80,
                volume=45_000_000,
                last_updated=datetime.now(UTC),
            )

        error = exc_info.value.errors()[0]
        assert error["type"] == "missing"
        assert error["loc"] == ("symbol",)

    def test_stock_quote_missing_price(self):
        """Test StockQuote creation with missing price."""
        with pytest.raises(ValidationError) as exc_info:
            StockQuote(
                symbol="AAPL",
                change=2.75,
                change_percent=1.80,
                volume=45_000_000,
                last_updated=datetime.now(UTC),
            )

        error = exc_info.value.errors()[0]
        assert error["type"] == "missing"
        assert error["loc"] == ("price",)

    def test_stock_quote_missing_change(self):
        """Test StockQuote creation with missing change."""
        with pytest.raises(ValidationError) as exc_info:
            StockQuote(
                symbol="AAPL",
                price=155.50,
                change_percent=1.80,
                volume=45_000_000,
                last_updated=datetime.now(UTC),
            )

        error = exc_info.value.errors()[0]
        assert error["type"] == "missing"
        assert error["loc"] == ("change",)

    def test_stock_quote_missing_change_percent(self):
        """Test StockQuote creation with missing change_percent."""
        with pytest.raises(ValidationError) as exc_info:
            StockQuote(
                symbol="AAPL",
                price=155.50,
                change=2.75,
                volume=45_000_000,
                last_updated=datetime.now(UTC),
            )

        error = exc_info.value.errors()[0]
        assert error["type"] == "missing"
        assert error["loc"] == ("change_percent",)

    def test_stock_quote_missing_volume(self):
        """Test StockQuote creation with missing volume."""
        with pytest.raises(ValidationError) as exc_info:
            StockQuote(
                symbol="AAPL",
                price=155.50,
                change=2.75,
                change_percent=1.80,
                last_updated=datetime.now(UTC),
            )

        error = exc_info.value.errors()[0]
        assert error["type"] == "missing"
        assert error["loc"] == ("volume",)

    def test_stock_quote_missing_timestamp(self):
        """Test StockQuote creation with missing last_updated."""
        with pytest.raises(ValidationError) as exc_info:
            StockQuote(
                symbol="AAPL",
                price=155.50,
                change=2.75,
                change_percent=1.80,
                volume=45_000_000,
            )

        error = exc_info.value.errors()[0]
        assert error["type"] == "missing"
        assert error["loc"] == ("last_updated",)


class TestStockQuoteDataTypes:
    """Test StockQuote field data type validation."""

    def test_stock_quote_symbol_string(self):
        """Test symbol field accepts string."""
        quote = StockQuote(
            symbol="TSLA",
            price=250.00,
            change=5.50,
            change_percent=2.25,
            volume=35_000_000,
            last_updated=datetime.now(UTC),
        )
        assert isinstance(quote.symbol, str)
        assert quote.symbol == "TSLA"

    def test_stock_quote_price_float(self):
        """Test price field accepts float."""
        quote = StockQuote(
            symbol="MSFT",
            price=300.75,
            change=1.25,
            change_percent=0.42,
            volume=25_000_000,
            last_updated=datetime.now(UTC),
        )
        assert isinstance(quote.price, float)
        assert quote.price == 300.75

    def test_stock_quote_price_int_conversion(self):
        """Test price field converts int to float."""
        quote = StockQuote(
            symbol="MSFT",
            price=300,  # Integer input
            change=1.25,
            change_percent=0.42,
            volume=25_000_000,
            last_updated=datetime.now(UTC),
        )
        assert isinstance(quote.price, float)
        assert quote.price == 300.0

    def test_stock_quote_change_positive(self):
        """Test change field with positive value."""
        quote = StockQuote(
            symbol="NVDA",
            price=875.50,
            change=25.75,  # Positive change
            change_percent=3.03,
            volume=40_000_000,
            last_updated=datetime.now(UTC),
        )
        assert quote.change == 25.75

    def test_stock_quote_change_negative(self):
        """Test change field with negative value."""
        quote = StockQuote(
            symbol="META",
            price=325.00,
            change=-12.50,  # Negative change
            change_percent=-3.70,
            volume=30_000_000,
            last_updated=datetime.now(UTC),
        )
        assert quote.change == -12.50

    def test_stock_quote_change_zero(self):
        """Test change field with zero value."""
        quote = StockQuote(
            symbol="AMZN",
            price=150.00,
            change=0.0,  # No change
            change_percent=0.0,
            volume=20_000_000,
            last_updated=datetime.now(UTC),
        )
        assert quote.change == 0.0

    def test_stock_quote_change_percent_positive(self):
        """Test change_percent field with positive value."""
        quote = StockQuote(
            symbol="AAPL",
            price=175.00,
            change=8.50,
            change_percent=5.10,  # Positive percentage
            volume=50_000_000,
            last_updated=datetime.now(UTC),
        )
        assert quote.change_percent == 5.10

    def test_stock_quote_change_percent_negative(self):
        """Test change_percent field with negative value."""
        quote = StockQuote(
            symbol="GOOGL",
            price=2800.00,
            change=-75.00,
            change_percent=-2.61,  # Negative percentage
            volume=1_500_000,
            last_updated=datetime.now(UTC),
        )
        assert quote.change_percent == -2.61

    def test_stock_quote_volume_integer(self):
        """Test volume field accepts integer."""
        quote = StockQuote(
            symbol="SPY",
            price=450.00,
            change=2.25,
            change_percent=0.50,
            volume=75_000_000,  # Large integer
            last_updated=datetime.now(UTC),
        )
        assert isinstance(quote.volume, int)
        assert quote.volume == 75_000_000

    def test_stock_quote_volume_zero(self):
        """Test volume field accepts zero."""
        quote = StockQuote(
            symbol="LOWVOL",
            price=10.00,
            change=0.05,
            change_percent=0.50,
            volume=0,  # Zero volume (e.g., after hours)
            last_updated=datetime.now(UTC),
        )
        assert quote.volume == 0

    def test_stock_quote_datetime_with_timezone(self):
        """Test last_updated field with timezone-aware datetime."""
        utc_time = datetime(2024, 1, 15, 16, 0, 0, tzinfo=UTC)

        quote = StockQuote(
            symbol="AAPL",
            price=155.50,
            change=2.75,
            change_percent=1.80,
            volume=45_000_000,
            last_updated=utc_time,
        )

        assert quote.last_updated == utc_time
        assert quote.last_updated.tzinfo is not None

    def test_stock_quote_datetime_naive(self):
        """Test last_updated field with naive datetime."""
        naive_time = datetime(2024, 1, 15, 16, 0, 0)

        quote = StockQuote(
            symbol="AAPL",
            price=155.50,
            change=2.75,
            change_percent=1.80,
            volume=45_000_000,
            last_updated=naive_time,
        )

        assert quote.last_updated == naive_time


class TestStockQuoteFieldValidation:
    """Test field validation edge cases."""

    def test_stock_quote_empty_symbol(self):
        """Test validation of empty symbol."""
        with pytest.raises(ValidationError):
            StockQuote(
                symbol="",  # Empty string
                price=155.50,
                change=2.75,
                change_percent=1.80,
                volume=45_000_000,
                last_updated=datetime.now(UTC),
            )

    def test_stock_quote_very_long_symbol(self):
        """Test symbol with many characters."""
        long_symbol = "VERYLONGSYMBOL123456789"
        quote = StockQuote(
            symbol=long_symbol,
            price=155.50,
            change=2.75,
            change_percent=1.80,
            volume=45_000_000,
            last_updated=datetime.now(UTC),
        )
        assert quote.symbol == long_symbol

    def test_stock_quote_zero_price(self):
        """Test quote with zero price."""
        quote = StockQuote(
            symbol="WORTHLESS",
            price=0.0,
            change=0.0,
            change_percent=0.0,
            volume=1000,
            last_updated=datetime.now(UTC),
        )
        assert quote.price == 0.0

    def test_stock_quote_very_high_price(self):
        """Test quote with very high price."""
        high_price = 999999.99
        quote = StockQuote(
            symbol="BRK.A",  # Berkshire Hathaway A shares style
            price=high_price,
            change=1000.00,
            change_percent=0.10,
            volume=100,
            last_updated=datetime.now(UTC),
        )
        assert quote.price == high_price

    def test_stock_quote_very_small_price(self):
        """Test quote with very small price (penny stock)."""
        small_price = 0.0001
        quote = StockQuote(
            symbol="PENNY",
            price=small_price,
            change=0.00001,
            change_percent=10.0,
            volume=1_000_000,
            last_updated=datetime.now(UTC),
        )
        assert quote.price == small_price

    def test_stock_quote_very_high_volume(self):
        """Test quote with very high volume."""
        high_volume = 1_000_000_000
        quote = StockQuote(
            symbol="POPULAR",
            price=50.00,
            change=2.50,
            change_percent=5.26,
            volume=high_volume,
            last_updated=datetime.now(UTC),
        )
        assert quote.volume == high_volume

    def test_stock_quote_extreme_change_percent(self):
        """Test quote with extreme percentage changes."""
        # Very high gain (meme stock behavior)
        quote_gain = StockQuote(
            symbol="MEME",
            price=100.00,
            change=900.00,
            change_percent=900.0,  # 900% gain
            volume=500_000_000,
            last_updated=datetime.now(UTC),
        )
        assert quote_gain.change_percent == 900.0

        # Large loss
        quote_loss = StockQuote(
            symbol="CRASH",
            price=1.00,
            change=-99.00,
            change_percent=-99.0,  # 99% loss
            volume=100_000_000,
            last_updated=datetime.now(UTC),
        )
        assert quote_loss.change_percent == -99.0


class TestStockQuoteSerialization:
    """Test StockQuote serialization and deserialization."""

    def test_stock_quote_model_dump(self):
        """Test StockQuote model_dump serialization."""
        timestamp = datetime(2024, 1, 15, 16, 0, 0, tzinfo=UTC)

        quote = StockQuote(
            symbol="AAPL",
            price=155.50,
            change=2.75,
            change_percent=1.80,
            volume=45_000_000,
            last_updated=timestamp,
        )

        data = quote.model_dump()

        assert data["symbol"] == "AAPL"
        assert data["price"] == 155.50
        assert data["change"] == 2.75
        assert data["change_percent"] == 1.80
        assert data["volume"] == 45_000_000
        assert data["last_updated"] == timestamp

    def test_stock_quote_json_roundtrip(self):
        """Test StockQuote JSON serialization roundtrip."""
        timestamp = datetime.now(UTC)

        original_quote = StockQuote(
            symbol="GOOGL",
            price=2850.25,
            change=-15.75,
            change_percent=-0.55,
            volume=1_250_000,
            last_updated=timestamp,
        )

        # Serialize to dict
        data = original_quote.model_dump()

        # Deserialize back to model
        restored_quote = StockQuote(**data)

        assert restored_quote.symbol == original_quote.symbol
        assert restored_quote.price == original_quote.price
        assert restored_quote.change == original_quote.change
        assert restored_quote.change_percent == original_quote.change_percent
        assert restored_quote.volume == original_quote.volume
        assert restored_quote.last_updated == original_quote.last_updated

    def test_stock_quote_from_dict(self):
        """Test creating StockQuote from dictionary."""
        data = {
            "symbol": "TSLA",
            "price": 250.00,
            "change": 12.50,
            "change_percent": 5.26,
            "volume": 85_000_000,
            "last_updated": datetime(2024, 1, 15, 15, 30, 0, tzinfo=UTC),
        }

        quote = StockQuote(**data)

        assert quote.symbol == "TSLA"
        assert quote.price == 250.00
        assert quote.change == 12.50
        assert quote.change_percent == 5.26
        assert quote.volume == 85_000_000


class TestStockQuoteEdgeCases:
    """Test edge cases and complex scenarios."""

    def test_stock_quote_special_symbols(self):
        """Test quotes with special symbol formats."""
        # ETF symbol
        etf_quote = StockQuote(
            symbol="SPY",
            price=450.00,
            change=2.25,
            change_percent=0.50,
            volume=75_000_000,
            last_updated=datetime.now(UTC),
        )
        assert etf_quote.symbol == "SPY"

        # Class A/B shares
        class_quote = StockQuote(
            symbol="BRK.A",
            price=500000.00,
            change=1000.00,
            change_percent=0.20,
            volume=50,
            last_updated=datetime.now(UTC),
        )
        assert class_quote.symbol == "BRK.A"

        # Foreign stock
        foreign_quote = StockQuote(
            symbol="TSM",
            price=100.00,
            change=-2.50,
            change_percent=-2.44,
            volume=25_000_000,
            last_updated=datetime.now(UTC),
        )
        assert foreign_quote.symbol == "TSM"

    def test_stock_quote_market_hours_vs_after_hours(self):
        """Test quotes during different market periods."""
        # Market hours quote
        market_hours_quote = StockQuote(
            symbol="AAPL",
            price=155.50,
            change=2.75,
            change_percent=1.80,
            volume=45_000_000,
            last_updated=datetime(2024, 1, 15, 15, 30, 0, tzinfo=UTC),  # 3:30 PM UTC
        )
        assert market_hours_quote.volume > 0

        # After hours quote (typically lower volume)
        after_hours_quote = StockQuote(
            symbol="AAPL",
            price=156.00,
            change=3.25,
            change_percent=2.13,
            volume=500_000,  # Much lower volume
            last_updated=datetime(2024, 1, 15, 22, 0, 0, tzinfo=UTC),  # 10 PM UTC
        )
        assert after_hours_quote.volume < market_hours_quote.volume

    def test_stock_quote_halted_stock(self):
        """Test quote for halted stock."""
        quote = StockQuote(
            symbol="HALTED",
            price=25.00,
            change=0.0,  # No change during halt
            change_percent=0.0,
            volume=0,  # No volume during halt
            last_updated=datetime.now(UTC),
        )
        assert quote.change == 0.0
        assert quote.volume == 0

    def test_stock_quote_ipo_first_day(self):
        """Test quote for IPO stock on first trading day."""
        quote = StockQuote(
            symbol="NEWIPO",
            price=45.00,
            change=20.00,  # Big gain from IPO price
            change_percent=80.0,  # 80% gain
            volume=100_000_000,  # High volume for IPO
            last_updated=datetime.now(UTC),
        )
        assert quote.change_percent == 80.0
        assert quote.volume == 100_000_000

    def test_stock_quote_cryptocurrency_style(self):
        """Test quote with cryptocurrency-like precision."""
        quote = StockQuote(
            symbol="CRYPTO",
            price=0.000123456,  # Very precise price
            change=0.000001234,
            change_percent=1.01,
            volume=1_000_000_000,  # High volume
            last_updated=datetime.now(UTC),
        )
        assert quote.price == 0.000123456

    def test_stock_quote_negative_price_invalid(self):
        """Test that negative prices are technically allowed by schema."""
        # Note: In real markets, prices can't be negative, but the schema doesn't enforce this
        # This test documents current behavior - in production, business logic should validate
        quote = StockQuote(
            symbol="WEIRD",
            price=-10.00,  # Negative price (unusual but schema allows it)
            change=-15.00,
            change_percent=-60.0,
            volume=1000,
            last_updated=datetime.now(UTC),
        )
        assert quote.price == -10.00  # Schema currently allows this

    def test_stock_quote_future_timestamp(self):
        """Test quote with future timestamp."""
        future_time = datetime(2030, 1, 1, 12, 0, 0, tzinfo=UTC)

        quote = StockQuote(
            symbol="FUTURE",
            price=100.00,
            change=5.00,
            change_percent=5.26,
            volume=1_000_000,
            last_updated=future_time,
        )
        assert quote.last_updated == future_time


class TestStockQuoteBusinessLogic:
    """Test business logic that might be applied to StockQuote data."""

    def test_stock_quote_consistency_check(self):
        """Test that change and change_percent are mathematically consistent."""
        # Example: Price = 100, Change = 5, should be 5% change
        quote = StockQuote(
            symbol="MATH",
            price=105.00,
            change=5.00,
            change_percent=5.0,  # This should be consistent
            volume=1_000_000,
            last_updated=datetime.now(UTC),
        )

        # Calculate expected change percent
        previous_price = quote.price - quote.change
        expected_change_percent = (quote.change / previous_price) * 100

        # Allow for small floating point differences
        assert abs(quote.change_percent - expected_change_percent) < 0.01

    def test_stock_quote_percentage_calculation_edge_cases(self):
        """Test percentage calculation with edge cases."""
        # Very small previous price
        quote_small = StockQuote(
            symbol="SMALL",
            price=0.002,
            change=0.001,
            change_percent=100.0,  # 100% gain from 0.001 to 0.002
            volume=1_000_000,
            last_updated=datetime.now(UTC),
        )

        previous_price = quote_small.price - quote_small.change
        calculated_percent = (quote_small.change / previous_price) * 100
        assert abs(quote_small.change_percent - calculated_percent) < 0.01

    def test_stock_quote_volume_analysis(self):
        """Test volume-based analysis patterns."""
        # High volume quote
        high_volume_quote = StockQuote(
            symbol="POPULAR",
            price=50.00,
            change=2.50,
            change_percent=5.26,
            volume=100_000_000,  # Very high volume
            last_updated=datetime.now(UTC),
        )

        # Low volume quote
        low_volume_quote = StockQuote(
            symbol="ILLIQUID",
            price=50.00,
            change=2.50,
            change_percent=5.26,
            volume=1_000,  # Very low volume
            last_updated=datetime.now(UTC),
        )

        # Volume ratio analysis
        volume_ratio = high_volume_quote.volume / low_volume_quote.volume
        assert volume_ratio == 100_000  # 100,000x more volume

    def test_stock_quote_timestamp_recency(self):
        """Test timestamp recency for data freshness."""
        now = datetime.now(UTC)
        recent_quote = StockQuote(
            symbol="FRESH",
            price=100.00,
            change=1.00,
            change_percent=1.01,
            volume=1_000_000,
            last_updated=now,
        )

        # Calculate how fresh the data is
        data_age_seconds = (now - recent_quote.last_updated).total_seconds()
        assert data_age_seconds < 1.0  # Very fresh data
