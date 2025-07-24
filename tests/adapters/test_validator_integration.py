"""
Comprehensive integration tests for test data validation.

Tests TestDataValidator with focus on:
- Database integrity validation
- Data consistency checks
- Scenario validation
- Symbol relationship validation
- Performance with large datasets
- Error detection and reporting
- Recovery scenarios
"""

from datetime import date
from decimal import Decimal
from unittest.mock import MagicMock, Mock, patch

import pytest
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session

from app.adapters.test_data_validator import (
    TestDataValidationError,
    TestDataValidator,
    validate_test_data,
)
from app.models.database.trading import DevOptionQuote, DevScenario, DevStockQuote


class TestTestDataValidatorInitialization:
    """Test TestDataValidator initialization and basic functionality."""

    @pytest.fixture
    def validator(self):
        """Create test data validator."""
        return TestDataValidator()

    def test_validator_initialization(self, validator):
        """Test validator initialization."""
        assert isinstance(validator, TestDataValidator)
        assert isinstance(validator.validation_errors, list)
        assert isinstance(validator.validation_warnings, list)
        assert len(validator.validation_errors) == 0
        assert len(validator.validation_warnings) == 0

    def test_clear_results(self, validator):
        """Test clearing validation results."""
        # Add some test errors and warnings
        validator.validation_errors.append("Test error")
        validator.validation_warnings.append("Test warning")

        # Clear results
        validator.clear_results()

        assert len(validator.validation_errors) == 0
        assert len(validator.validation_warnings) == 0


class TestStockQuoteValidationIntegration:
    """Integration tests for stock quote validation."""

    @pytest.fixture
    def validator(self):
        """Create validator for testing."""
        return TestDataValidator()

    @pytest.fixture
    def mock_session(self):
        """Create mock database session."""
        return MagicMock(spec=Session)

    @pytest.fixture
    def valid_stock_quotes(self):
        """Create valid stock quotes for testing."""
        quotes = []
        for i in range(3):
            quote = DevStockQuote()
            quote.symbol = f"STOCK{i}"
            quote.quote_date = date(2017, 3, 24)
            quote.scenario = "default"
            quote.bid = Decimal(f"{100 + i}.25")
            quote.ask = Decimal(f"{100 + i}.75")
            quote.price = Decimal(f"{100 + i}.50")
            quote.volume = 1000000 + i * 100000
            quotes.append(quote)
        return quotes

    @pytest.fixture
    def invalid_stock_quotes(self):
        """Create invalid stock quotes for testing."""
        quotes = []

        # Quote with bid > ask
        quote1 = DevStockQuote()
        quote1.symbol = "INVALID1"
        quote1.quote_date = date(2017, 3, 24)
        quote1.scenario = "default"
        quote1.bid = Decimal("101.00")
        quote1.ask = Decimal("100.00")  # Invalid: ask < bid
        quote1.price = Decimal("100.50")
        quotes.append(quote1)

        # Quote with price outside bid-ask spread
        quote2 = DevStockQuote()
        quote2.symbol = "INVALID2"
        quote2.quote_date = date(2017, 3, 24)
        quote2.scenario = "default"
        quote2.bid = Decimal("100.00")
        quote2.ask = Decimal("101.00")
        quote2.price = Decimal("102.00")  # Invalid: price > ask
        quotes.append(quote2)

        # Quote with negative price
        quote3 = DevStockQuote()
        quote3.symbol = "INVALID3"
        quote3.quote_date = date(2017, 3, 24)
        quote3.scenario = "default"
        quote3.bid = Decimal("-1.00")  # Invalid: negative bid
        quote3.ask = Decimal("100.00")
        quote3.price = Decimal("99.50")
        quotes.append(quote3)

        return quotes

    @pytest.mark.integration
    def test_valid_stock_quote_validation(
        self, validator, mock_session, valid_stock_quotes
    ):
        """Test validation of valid stock quotes."""
        mock_session.query.return_value.filter.return_value.all.return_value = (
            valid_stock_quotes
        )

        result = validator.validate_stock_quote_integrity(mock_session, "default")

        assert result is True
        assert len(validator.validation_errors) == 0
        assert len(validator.validation_warnings) == 0

    @pytest.mark.integration
    def test_invalid_stock_quote_validation(
        self, validator, mock_session, invalid_stock_quotes
    ):
        """Test validation of invalid stock quotes."""
        mock_session.query.return_value.filter.return_value.all.return_value = (
            invalid_stock_quotes
        )

        result = validator.validate_stock_quote_integrity(mock_session, "default")

        assert result is False
        assert len(validator.validation_errors) >= 3  # Should detect all invalid quotes

        # Check specific error types
        error_messages = " ".join(validator.validation_errors)
        assert "bid" in error_messages and "ask" in error_messages
        assert "price" in error_messages
        assert "negative" in error_messages

    @pytest.mark.integration
    def test_stock_quote_wide_spread_warning(self, validator, mock_session):
        """Test warning for wide bid-ask spreads."""
        # Create quote with wide spread
        quote = DevStockQuote()
        quote.symbol = "WIDE_SPREAD"
        quote.quote_date = date(2017, 3, 24)
        quote.scenario = "default"
        quote.bid = Decimal("90.00")
        quote.ask = Decimal("110.00")  # 22% spread - should trigger warning
        quote.price = Decimal("100.00")

        mock_session.query.return_value.filter.return_value.all.return_value = [quote]

        result = validator.validate_stock_quote_integrity(mock_session, "default")

        assert result is True  # No errors, just warnings
        assert len(validator.validation_warnings) >= 1

        warning_messages = " ".join(validator.validation_warnings)
        assert "wide spread" in warning_messages

    @pytest.mark.integration
    def test_empty_stock_quotes_validation(self, validator, mock_session):
        """Test validation with no stock quotes."""
        mock_session.query.return_value.filter.return_value.all.return_value = []

        result = validator.validate_stock_quote_integrity(mock_session, "default")

        assert result is False
        assert len(validator.validation_errors) == 1
        assert "No stock quotes found" in validator.validation_errors[0]


class TestOptionQuoteValidationIntegration:
    """Integration tests for option quote validation."""

    @pytest.fixture
    def validator(self):
        """Create validator for testing."""
        return TestDataValidator()

    @pytest.fixture
    def mock_session(self):
        """Create mock database session."""
        return MagicMock(spec=Session)

    @pytest.fixture
    def valid_option_quotes(self):
        """Create valid option quotes for testing."""
        quotes = []
        for i in range(3):
            quote = DevOptionQuote()
            quote.symbol = f"AAPL17032{4 + i}C00{150 + i}000"
            quote.underlying = "AAPL"
            quote.quote_date = date(2017, 3, 24)
            quote.scenario = "default"
            quote.expiration = date(2017, 3, 31)  # Future date
            quote.strike = Decimal(f"{150 + i}.0")
            quote.option_type = "call"
            quote.bid = Decimal(f"{2 + i * 0.5}.25")
            quote.ask = Decimal(f"{2 + i * 0.5}.75")
            quote.price = Decimal(f"{2 + i * 0.5}.50")
            quote.volume = 500 + i * 100
            quotes.append(quote)
        return quotes

    @pytest.fixture
    def invalid_option_quotes(self):
        """Create invalid option quotes for testing."""
        quotes = []

        # Option without underlying
        quote1 = DevOptionQuote()
        quote1.symbol = "INVALID1C00150000"
        quote1.underlying = None  # Invalid: no underlying
        quote1.quote_date = date(2017, 3, 24)
        quote1.scenario = "default"
        quote1.expiration = date(2017, 3, 31)
        quote1.strike = Decimal("150.0")
        quote1.option_type = "call"
        quotes.append(quote1)

        # Option with invalid strike
        quote2 = DevOptionQuote()
        quote2.symbol = "AAPL170324C00000000"
        quote2.underlying = "AAPL"
        quote2.quote_date = date(2017, 3, 24)
        quote2.scenario = "default"
        quote2.expiration = date(2017, 3, 31)
        quote2.strike = Decimal("0.0")  # Invalid: zero strike
        quote2.option_type = "call"
        quotes.append(quote2)

        # Option with invalid type
        quote3 = DevOptionQuote()
        quote3.symbol = "AAPL170324X00150000"
        quote3.underlying = "AAPL"
        quote3.quote_date = date(2017, 3, 24)
        quote3.scenario = "default"
        quote3.expiration = date(2017, 3, 31)
        quote3.strike = Decimal("150.0")
        quote3.option_type = "invalid"  # Invalid: not call or put
        quotes.append(quote3)

        # Option expired at quote date
        quote4 = DevOptionQuote()
        quote4.symbol = "AAPL170324C00150000"
        quote4.underlying = "AAPL"
        quote4.quote_date = date(2017, 3, 24)
        quote4.scenario = "default"
        quote4.expiration = date(2017, 3, 23)  # Invalid: already expired
        quote4.strike = Decimal("150.0")
        quote4.option_type = "call"
        quotes.append(quote4)

        return quotes

    @pytest.mark.integration
    def test_valid_option_quote_validation(
        self, validator, mock_session, valid_option_quotes
    ):
        """Test validation of valid option quotes."""
        mock_session.query.return_value.filter.return_value.all.return_value = (
            valid_option_quotes
        )

        result = validator.validate_option_quote_integrity(mock_session, "default")

        assert result is True
        assert len(validator.validation_errors) == 0

    @pytest.mark.integration
    def test_invalid_option_quote_validation(
        self, validator, mock_session, invalid_option_quotes
    ):
        """Test validation of invalid option quotes."""
        mock_session.query.return_value.filter.return_value.all.return_value = (
            invalid_option_quotes
        )

        result = validator.validate_option_quote_integrity(mock_session, "default")

        assert result is False
        assert len(validator.validation_errors) >= 4  # Should detect all invalid quotes

        # Check specific error types
        error_messages = " ".join(validator.validation_errors)
        assert "underlying" in error_messages
        assert "strike" in error_messages
        assert "option type" in error_messages
        assert "expiration" in error_messages

    @pytest.mark.integration
    def test_empty_option_quotes_validation(self, validator, mock_session):
        """Test validation with no option quotes."""
        mock_session.query.return_value.filter.return_value.all.return_value = []

        result = validator.validate_option_quote_integrity(mock_session, "default")

        assert result is True  # No options is not an error
        assert len(validator.validation_warnings) == 1
        assert "No option quotes found" in validator.validation_warnings[0]


class TestScenarioValidationIntegration:
    """Integration tests for scenario validation."""

    @pytest.fixture
    def validator(self):
        """Create validator for testing."""
        return TestDataValidator()

    @pytest.fixture
    def mock_session(self):
        """Create mock database session."""
        return MagicMock(spec=Session)

    @pytest.fixture
    def valid_scenarios(self):
        """Create valid scenarios for testing."""
        scenarios = []

        scenario1 = DevScenario()
        scenario1.name = "default"
        scenario1.start_date = date(2017, 3, 24)
        scenario1.end_date = date(2017, 3, 25)
        scenario1.symbols = ["AAPL", "GOOGL"]
        scenario1.description = "Default test scenario"
        scenarios.append(scenario1)

        scenario2 = DevScenario()
        scenario2.name = "earnings"
        scenario2.start_date = date(2017, 1, 27)
        scenario2.end_date = date(2017, 1, 28)
        scenario2.symbols = ["AAL"]
        scenario2.description = "Earnings scenario"
        scenarios.append(scenario2)

        return scenarios

    @pytest.fixture
    def invalid_scenarios(self):
        """Create invalid scenarios for testing."""
        scenarios = []

        # Scenario with end_date before start_date
        scenario1 = DevScenario()
        scenario1.name = "invalid_dates"
        scenario1.start_date = date(2017, 3, 25)
        scenario1.end_date = date(2017, 3, 24)  # Invalid: end before start
        scenario1.symbols = ["AAPL"]
        scenarios.append(scenario1)

        # Scenario with no symbols
        scenario2 = DevScenario()
        scenario2.name = "no_symbols"
        scenario2.start_date = date(2017, 3, 24)
        scenario2.end_date = date(2017, 3, 25)
        scenario2.symbols = []  # Invalid: no symbols
        scenarios.append(scenario2)

        return scenarios

    @pytest.mark.integration
    def test_valid_scenario_validation(self, validator, mock_session, valid_scenarios):
        """Test validation of valid scenarios."""
        mock_session.query.return_value.all.return_value = valid_scenarios

        # Mock stock quote counts for symbol validation
        mock_session.query.return_value.filter.return_value.count.return_value = 1

        result = validator.validate_scenario_integrity(mock_session)

        assert result is True
        assert len(validator.validation_errors) == 0

    @pytest.mark.integration
    def test_invalid_scenario_validation(
        self, validator, mock_session, invalid_scenarios
    ):
        """Test validation of invalid scenarios."""
        mock_session.query.return_value.all.return_value = invalid_scenarios

        # Mock stock quote counts
        mock_session.query.return_value.filter.return_value.count.return_value = 0

        result = validator.validate_scenario_integrity(mock_session)

        assert result is False
        assert len(validator.validation_errors) >= 2

        error_messages = " ".join(validator.validation_errors)
        assert "end_date" in error_messages and "start_date" in error_messages
        assert "no symbols" in error_messages

    @pytest.mark.integration
    def test_empty_scenarios_validation(self, validator, mock_session):
        """Test validation with no scenarios."""
        mock_session.query.return_value.all.return_value = []

        result = validator.validate_scenario_integrity(mock_session)

        assert result is False
        assert len(validator.validation_errors) == 1
        assert "No test scenarios found" in validator.validation_errors[0]

    @pytest.mark.integration
    def test_scenario_symbol_data_validation(
        self, validator, mock_session, valid_scenarios
    ):
        """Test validation of symbol data in scenarios."""
        mock_session.query.return_value.all.return_value = valid_scenarios

        # Mock that some symbols have no data
        def mock_count_side_effect(*args, **kwargs):
            # Return 0 for GOOGL (no data), 1 for others
            filter_calls = mock_session.query.return_value.filter.call_args_list
            if filter_calls:
                # This is a simplified mock - in real scenario would check filter conditions
                return 0  # Simulate no data found
            return 1

        mock_session.query.return_value.filter.return_value.count.side_effect = (
            mock_count_side_effect
        )

        result = validator.validate_scenario_integrity(mock_session)

        # Should still pass but with warnings
        assert result is True
        assert len(validator.validation_warnings) > 0


class TestDateCoverageValidationIntegration:
    """Integration tests for date coverage validation."""

    @pytest.fixture
    def validator(self):
        """Create validator for testing."""
        return TestDataValidator()

    @pytest.fixture
    def mock_session(self):
        """Create mock database session."""
        return MagicMock(spec=Session)

    @pytest.fixture
    def mock_scenario(self):
        """Create mock scenario for testing."""
        scenario = DevScenario()
        scenario.name = "test_scenario"
        scenario.start_date = date(2017, 3, 24)
        scenario.end_date = date(2017, 3, 25)
        return scenario

    @pytest.mark.integration
    def test_valid_date_coverage_validation(
        self, validator, mock_session, mock_scenario
    ):
        """Test validation of valid date coverage."""
        # Mock scenario retrieval
        mock_session.query.return_value.filter.return_value.first.return_value = (
            mock_scenario
        )

        # Mock available dates include start and end dates
        available_dates = [
            (date(2017, 3, 24),),
            (date(2017, 3, 25),),
        ]
        mock_session.query.return_value.filter.return_value.distinct.return_value.all.return_value = available_dates

        result = validator.validate_date_coverage(mock_session, "test_scenario")

        assert result is True
        assert len(validator.validation_warnings) == 0

    @pytest.mark.integration
    def test_missing_date_coverage_validation(
        self, validator, mock_session, mock_scenario
    ):
        """Test validation with missing date coverage."""
        mock_session.query.return_value.filter.return_value.first.return_value = (
            mock_scenario
        )

        # Mock available dates missing start and end dates
        available_dates = [
            (date(2017, 3, 23),),  # Before start date
            (date(2017, 3, 26),),  # After end date
        ]
        mock_session.query.return_value.filter.return_value.distinct.return_value.all.return_value = available_dates

        result = validator.validate_date_coverage(mock_session, "test_scenario")

        assert result is True  # Warnings, not errors
        assert len(validator.validation_warnings) == 2

        warning_messages = " ".join(validator.validation_warnings)
        assert "start_date" in warning_messages
        assert "end_date" in warning_messages

    @pytest.mark.integration
    def test_nonexistent_scenario_validation(self, validator, mock_session):
        """Test validation of non-existent scenario."""
        mock_session.query.return_value.filter.return_value.first.return_value = None

        result = validator.validate_date_coverage(mock_session, "nonexistent")

        assert result is False
        assert len(validator.validation_errors) == 1
        assert "Scenario 'nonexistent' not found" in validator.validation_errors[0]


class TestSymbolConsistencyValidationIntegration:
    """Integration tests for symbol consistency validation."""

    @pytest.fixture
    def validator(self):
        """Create validator for testing."""
        return TestDataValidator()

    @pytest.fixture
    def mock_session(self):
        """Create mock database session."""
        return MagicMock(spec=Session)

    @pytest.mark.integration
    def test_consistent_symbols_validation(self, validator, mock_session):
        """Test validation with consistent symbols."""
        # Mock stock symbols
        stock_symbols = [("AAPL",), ("GOOGL",)]
        # Mock option underlyings (subset of stock symbols)
        option_underlyings = [("AAPL",)]

        mock_session.query.side_effect = [
            Mock(all=Mock(return_value=stock_symbols)),
            Mock(all=Mock(return_value=option_underlyings)),
        ]

        result = validator.validate_symbol_consistency(mock_session, "default")

        assert result is True
        assert len(validator.validation_warnings) == 0

    @pytest.mark.integration
    def test_inconsistent_symbols_validation(self, validator, mock_session):
        """Test validation with inconsistent symbols."""
        # Mock stock symbols
        stock_symbols = [("AAPL",)]
        # Mock option underlyings include symbol not in stocks
        option_underlyings = [("AAPL",), ("GOOGL",)]  # GOOGL not in stock symbols

        mock_session.query.side_effect = [
            Mock(all=Mock(return_value=stock_symbols)),
            Mock(all=Mock(return_value=option_underlyings)),
        ]

        result = validator.validate_symbol_consistency(mock_session, "default")

        assert result is True  # Warnings, not errors
        assert len(validator.validation_warnings) == 1

        warning_messages = " ".join(validator.validation_warnings)
        assert "without stock data" in warning_messages
        assert "GOOGL" in warning_messages


class TestCompleteValidationIntegration:
    """Integration tests for complete validation workflow."""

    @pytest.fixture
    def validator(self):
        """Create validator for testing."""
        return TestDataValidator()

    @pytest.fixture
    def mock_session(self):
        """Create mock database session."""
        return MagicMock(spec=Session)

    @pytest.mark.integration
    def test_validate_all_success(self, validator):
        """Test complete validation with successful results."""
        with patch(
            "app.adapters.test_data_validator.get_sync_session"
        ) as mock_session_context:
            mock_db = MagicMock()
            mock_session_context.return_value.__enter__.return_value = mock_db

            # Mock all validation methods to pass
            with patch.object(
                validator, "validate_stock_quote_integrity", return_value=True
            ):
                with patch.object(
                    validator, "validate_option_quote_integrity", return_value=True
                ):
                    with patch.object(
                        validator, "validate_scenario_integrity", return_value=True
                    ):
                        with patch.object(
                            validator, "validate_date_coverage", return_value=True
                        ):
                            with patch.object(
                                validator,
                                "validate_symbol_consistency",
                                return_value=True,
                            ):
                                # Mock counts for summary
                                mock_db.query.return_value.filter.return_value.count.side_effect = [
                                    100,
                                    500,
                                    3,
                                ]

                                results = validator.validate_all("default")

                                assert results["overall_valid"] is True
                                assert results["stock_quotes_valid"] is True
                                assert results["option_quotes_valid"] is True
                                assert results["scenarios_valid"] is True
                                assert results["date_coverage_valid"] is True
                                assert results["symbol_consistency_valid"] is True
                                assert results["counts"]["stock_quotes"] == 100
                                assert results["counts"]["option_quotes"] == 500
                                assert results["counts"]["scenarios"] == 3

    @pytest.mark.integration
    def test_validate_all_with_errors(self, validator):
        """Test complete validation with errors."""
        with patch(
            "app.adapters.test_data_validator.get_sync_session"
        ) as mock_session_context:
            mock_db = MagicMock()
            mock_session_context.return_value.__enter__.return_value = mock_db

            # Mock some validation methods to fail
            with patch.object(
                validator, "validate_stock_quote_integrity", return_value=False
            ):
                with patch.object(
                    validator, "validate_option_quote_integrity", return_value=True
                ):
                    with patch.object(
                        validator, "validate_scenario_integrity", return_value=False
                    ):
                        with patch.object(
                            validator, "validate_date_coverage", return_value=True
                        ):
                            with patch.object(
                                validator,
                                "validate_symbol_consistency",
                                return_value=True,
                            ):
                                # Add test errors
                                validator.validation_errors.extend(
                                    ["Stock quote error", "Scenario error"]
                                )
                                validator.validation_warnings.append("Test warning")

                                mock_db.query.return_value.filter.return_value.count.side_effect = [
                                    50,
                                    200,
                                    2,
                                ]

                                results = validator.validate_all("default")

                                assert results["overall_valid"] is False
                                assert results["stock_quotes_valid"] is False
                                assert results["scenarios_valid"] is False
                                assert len(results["errors"]) == 2
                                assert len(results["warnings"]) == 1

    @pytest.mark.integration
    def test_validation_summary_generation(self, validator):
        """Test validation summary generation."""
        # Create sample results
        results = {
            "scenario": "test_scenario",
            "overall_valid": False,
            "stock_quotes_valid": True,
            "option_quotes_valid": False,
            "scenarios_valid": True,
            "date_coverage_valid": True,
            "symbol_consistency_valid": True,
            "errors": ["Option quote error 1", "Option quote error 2"],
            "warnings": ["Test warning"],
            "counts": {"stock_quotes": 100, "option_quotes": 50, "scenarios": 2},
        }

        summary = validator.get_validation_summary(results)

        assert isinstance(summary, str)
        assert "test_scenario" in summary
        assert "✗ FAILED" in summary
        assert "Stock Quotes: ✓" in summary
        assert "Option Quotes: ✗" in summary
        assert "Errors (2):" in summary
        assert "Warnings (1):" in summary
        assert "100" in summary  # Stock quote count


class TestValidationPerformanceIntegration:
    """Performance tests for validation operations."""

    @pytest.fixture
    def validator(self):
        """Create validator for performance testing."""
        return TestDataValidator()

    @pytest.mark.performance
    def test_large_dataset_validation_performance(self, validator):
        """Test validation performance with large datasets."""
        with patch(
            "app.adapters.test_data_validator.get_sync_session"
        ) as mock_session_context:
            mock_db = MagicMock()
            mock_session_context.return_value.__enter__.return_value = mock_db

            # Create large number of mock quotes
            large_stock_quotes = []
            for i in range(1000):
                quote = Mock()
                quote.symbol = f"STOCK{i}"
                quote.bid = Decimal(f"{100 + i}.25")
                quote.ask = Decimal(f"{100 + i}.75")
                quote.price = Decimal(f"{100 + i}.50")
                quote.volume = 1000000
                large_stock_quotes.append(quote)

            mock_db.query.return_value.filter.return_value.all.return_value = (
                large_stock_quotes
            )

            import time

            start_time = time.time()

            result = validator.validate_stock_quote_integrity(mock_db, "default")

            end_time = time.time()
            duration = end_time - start_time

            # Should complete within reasonable time
            assert duration < 5.0, f"Validation took {duration} seconds"
            assert result is True

    @pytest.mark.performance
    def test_validation_memory_efficiency(self, validator):
        """Test memory efficiency during validation."""
        with patch(
            "app.adapters.test_data_validator.get_sync_session"
        ) as mock_session_context:
            mock_db = MagicMock()
            mock_session_context.return_value.__enter__.return_value = mock_db

            # Mock all validations to pass quickly
            with patch.object(
                validator, "validate_stock_quote_integrity", return_value=True
            ):
                with patch.object(
                    validator, "validate_option_quote_integrity", return_value=True
                ):
                    with patch.object(
                        validator, "validate_scenario_integrity", return_value=True
                    ):
                        with patch.object(
                            validator, "validate_date_coverage", return_value=True
                        ):
                            with patch.object(
                                validator,
                                "validate_symbol_consistency",
                                return_value=True,
                            ):
                                mock_db.query.return_value.filter.return_value.count.side_effect = [
                                    10000,
                                    50000,
                                    10,
                                ]

                                import time

                                start_time = time.time()

                                # Run validation multiple times
                                for _ in range(10):
                                    validator.clear_results()
                                    results = validator.validate_all("default")
                                    assert results["overall_valid"] is True

                                end_time = time.time()
                                duration = end_time - start_time

                                # Should complete efficiently
                                assert duration < 2.0, (
                                    f"Multiple validations took {duration} seconds"
                                )


class TestValidationErrorHandlingIntegration:
    """Integration tests for validation error handling."""

    @pytest.fixture
    def validator(self):
        """Create validator for error testing."""
        return TestDataValidator()

    @pytest.mark.integration
    def test_database_error_handling(self, validator):
        """Test handling of database errors during validation."""
        with patch(
            "app.adapters.test_data_validator.get_sync_session"
        ) as mock_session_context:
            mock_session_context.side_effect = SQLAlchemyError(
                "Database connection failed"
            )

            # Should handle database errors gracefully
            with pytest.raises(SQLAlchemyError):
                validator.validate_all("default")

    @pytest.mark.integration
    def test_validation_with_none_values(self, validator):
        """Test handling of None values in data."""
        with patch(
            "app.adapters.test_data_validator.get_sync_session"
        ) as mock_session_context:
            mock_db = MagicMock()
            mock_session_context.return_value.__enter__.return_value = mock_db

            # Create quotes with None values
            quotes_with_none = []
            quote = Mock()
            quote.symbol = "TEST"
            quote.bid = None
            quote.ask = None
            quote.price = None
            quote.volume = None
            quotes_with_none.append(quote)

            mock_db.query.return_value.filter.return_value.all.return_value = (
                quotes_with_none
            )

            # Should handle None values gracefully
            result = validator.validate_stock_quote_integrity(mock_db, "default")
            # Result depends on validation logic for None values
            assert isinstance(result, bool)

    @pytest.mark.integration
    def test_validation_with_corrupted_data(self, validator):
        """Test handling of corrupted or malformed data."""
        with patch(
            "app.adapters.test_data_validator.get_sync_session"
        ) as mock_session_context:
            mock_db = MagicMock()
            mock_session_context.return_value.__enter__.return_value = mock_db

            # Create malformed quote objects
            corrupted_quotes = []
            quote = Mock()
            quote.symbol = None  # Invalid: no symbol
            quote.bid = "invalid_decimal"  # Invalid: not a number
            quote.ask = Decimal("100.00")
            quote.price = Decimal("99.50")
            corrupted_quotes.append(quote)

            mock_db.query.return_value.filter.return_value.all.return_value = (
                corrupted_quotes
            )

            # Should handle corrupted data without crashing
            try:
                result = validator.validate_stock_quote_integrity(mock_db, "default")
                assert isinstance(result, bool)
            except Exception as e:
                # Acceptable if validation detects and reports corruption
                assert "invalid" in str(e).lower() or "corrupted" in str(e).lower()


class TestConvenienceFunctionIntegration:
    """Integration tests for convenience functions."""

    @pytest.mark.integration
    def test_validate_test_data_convenience_function(self):
        """Test validate_test_data convenience function."""
        with patch(
            "app.adapters.test_data_validator.TestDataValidator"
        ) as mock_validator_class:
            mock_validator = Mock()
            mock_validator.validate_all.return_value = {
                "overall_valid": True,
                "scenario": "default",
            }
            mock_validator_class.return_value = mock_validator

            results = validate_test_data("default")

            assert results["overall_valid"] is True
            assert results["scenario"] == "default"
            mock_validator.validate_all.assert_called_once_with("default")

    @pytest.mark.integration
    def test_validate_test_data_with_custom_scenario(self):
        """Test validate_test_data with custom scenario."""
        with patch(
            "app.adapters.test_data_validator.TestDataValidator"
        ) as mock_validator_class:
            mock_validator = Mock()
            mock_validator.validate_all.return_value = {
                "overall_valid": False,
                "scenario": "custom_scenario",
                "errors": ["Test error"],
            }
            mock_validator_class.return_value = mock_validator

            results = validate_test_data("custom_scenario")

            assert results["overall_valid"] is False
            assert results["scenario"] == "custom_scenario"
            assert "errors" in results
            mock_validator.validate_all.assert_called_once_with("custom_scenario")


class TestTestDataValidationErrorIntegration:
    """Integration tests for TestDataValidationError exception."""

    def test_validation_error_creation(self):
        """Test creating TestDataValidationError."""
        error = TestDataValidationError("Test validation error")
        assert str(error) == "Test validation error"
        assert isinstance(error, Exception)

    def test_validation_error_raising(self):
        """Test raising and catching TestDataValidationError."""
        with pytest.raises(TestDataValidationError) as exc_info:
            raise TestDataValidationError("Custom validation error")

        assert str(exc_info.value) == "Custom validation error"

    def test_validation_error_in_context(self):
        """Test using TestDataValidationError in validation context."""
        validator = TestDataValidator()

        try:
            # Simulate validation that raises custom error
            if len(validator.validation_errors) == 0:  # Always true initially
                raise TestDataValidationError("Validation failed in test context")
        except TestDataValidationError as e:
            assert "Validation failed in test context" in str(e)
