"""
Test data validation utilities for ensuring data integrity and consistency.

Provides validation methods for test data migration and database integrity checks.
"""

import logging
from typing import Any

from sqlalchemy import and_
from sqlalchemy.orm import Session

from ..models.database.trading import DevOptionQuote, DevScenario, DevStockQuote
from ..storage.database import get_sync_session

logger = logging.getLogger(__name__)


class TestDataValidationError(Exception):
    """Error during test data validation."""

    pass


class TestDataValidator:
    """Validates test data integrity and consistency."""

    def __init__(self):
        self.validation_errors: list[str] = []
        self.validation_warnings: list[str] = []

    def clear_results(self) -> None:
        """Clear previous validation results."""
        self.validation_errors.clear()
        self.validation_warnings.clear()

    def validate_stock_quote_integrity(
        self, db: Session, scenario: str = "default"
    ) -> bool:
        """
        Validate stock quote data integrity.

        Args:
            db: Database session
            scenario: Scenario to validate

        Returns:
            True if validation passes, False otherwise
        """
        stock_quotes = (
            db.query(DevStockQuote).filter(DevStockQuote.scenario == scenario).all()
        )

        if not stock_quotes:
            self.validation_errors.append(
                f"No stock quotes found for scenario '{scenario}'"
            )
            return False

        for quote in stock_quotes:
            # Check bid/ask/price consistency
            if quote.bid and quote.ask and quote.price:
                if quote.bid > quote.ask:
                    self.validation_errors.append(
                        f"Stock {quote.symbol} on {quote.quote_date}: bid ({quote.bid}) > ask ({quote.ask})"
                    )

                if not (quote.bid <= quote.price <= quote.ask):
                    self.validation_errors.append(
                        f"Stock {quote.symbol} on {quote.quote_date}: price ({quote.price}) not between bid ({quote.bid}) and ask ({quote.ask})"
                    )

                # Check for reasonable spreads
                spread_pct = float(quote.ask - quote.bid) / float(quote.price)
                if spread_pct > 0.05:  # 5% spread warning
                    self.validation_warnings.append(
                        f"Stock {quote.symbol} on {quote.quote_date}: wide spread ({spread_pct:.2%})"
                    )

            # Check for negative prices
            if quote.bid and quote.bid < 0:
                self.validation_errors.append(
                    f"Stock {quote.symbol} on {quote.quote_date}: negative bid ({quote.bid})"
                )

            if quote.ask and quote.ask < 0:
                self.validation_errors.append(
                    f"Stock {quote.symbol} on {quote.quote_date}: negative ask ({quote.ask})"
                )

            if quote.price and quote.price < 0:
                self.validation_errors.append(
                    f"Stock {quote.symbol} on {quote.quote_date}: negative price ({quote.price})"
                )

        return len(self.validation_errors) == 0

    def validate_option_quote_integrity(
        self, db: Session, scenario: str = "default"
    ) -> bool:
        """
        Validate option quote data integrity.

        Args:
            db: Database session
            scenario: Scenario to validate

        Returns:
            True if validation passes, False otherwise
        """
        option_quotes = (
            db.query(DevOptionQuote).filter(DevOptionQuote.scenario == scenario).all()
        )

        if not option_quotes:
            self.validation_warnings.append(
                f"No option quotes found for scenario '{scenario}'"
            )
            return True  # Not an error if no options

        for quote in option_quotes:
            # Check basic option fields
            if not quote.underlying:
                self.validation_errors.append(
                    f"Option {quote.symbol} on {quote.quote_date}: missing underlying"
                )

            if not quote.strike or quote.strike <= 0:
                self.validation_errors.append(
                    f"Option {quote.symbol} on {quote.quote_date}: invalid strike ({quote.strike})"
                )

            if quote.option_type not in ["call", "put"]:
                self.validation_errors.append(
                    f"Option {quote.symbol} on {quote.quote_date}: invalid option type ({quote.option_type})"
                )

            expiration_date = quote.expiration
            if hasattr(expiration_date, "date"):
                expiration_date = expiration_date.date()
            quote_date = quote.quote_date
            if hasattr(quote_date, "date"):
                quote_date = quote_date.date()
            if expiration_date and quote_date and expiration_date <= quote_date:
                self.validation_errors.append(
                    f"Option {quote.symbol} on {quote.quote_date}: expiration ({quote.expiration}) not in future"
                )

            # Check bid/ask/price consistency
            if quote.bid and quote.ask and quote.price:
                if quote.bid > quote.ask:
                    self.validation_errors.append(
                        f"Option {quote.symbol} on {quote.quote_date}: bid ({quote.bid}) > ask ({quote.ask})"
                    )

                if not (quote.bid <= quote.price <= quote.ask):
                    self.validation_errors.append(
                        f"Option {quote.symbol} on {quote.quote_date}: price ({quote.price}) not between bid ({quote.bid}) and ask ({quote.ask})"
                    )

            # Check for negative prices
            if quote.bid and quote.bid < 0:
                self.validation_errors.append(
                    f"Option {quote.symbol} on {quote.quote_date}: negative bid ({quote.bid})"
                )

            if quote.ask and quote.ask < 0:
                self.validation_errors.append(
                    f"Option {quote.symbol} on {quote.quote_date}: negative ask ({quote.ask})"
                )

            if quote.price and quote.price < 0:
                self.validation_errors.append(
                    f"Option {quote.symbol} on {quote.quote_date}: negative price ({quote.price})"
                )

        return len(self.validation_errors) == 0

    def validate_scenario_integrity(self, db: Session) -> bool:
        """
        Validate test scenario data integrity.

        Args:
            db: Database session

        Returns:
            True if validation passes, False otherwise
        """
        scenarios = db.query(DevScenario).all()

        if not scenarios:
            self.validation_errors.append("No test scenarios found")
            return False

        for scenario in scenarios:
            # Check date range
            end_date = scenario.end_date
            if hasattr(end_date, "date"):
                end_date = end_date.date()
            start_date = scenario.start_date
            if hasattr(start_date, "date"):
                start_date = start_date.date()
            if end_date and start_date and end_date <= start_date:
                self.validation_errors.append(
                    f"Scenario '{scenario.name}': end_date ({scenario.end_date}) not after start_date ({scenario.start_date})"
                )

            # Check symbols list
            if not scenario.symbols or len(scenario.symbols) == 0:
                self.validation_errors.append(
                    f"Scenario '{scenario.name}': no symbols defined"
                )

            # Check that symbols have data
            for symbol in scenario.symbols:
                stock_count = (
                    db.query(DevStockQuote)
                    .filter(
                        and_(
                            DevStockQuote.symbol == symbol,
                            DevStockQuote.scenario == scenario.name,
                            DevStockQuote.quote_date >= scenario.start_date,
                            DevStockQuote.quote_date <= scenario.end_date,
                        )
                    )
                    .count()
                )

                if stock_count == 0:
                    self.validation_warnings.append(
                        f"Scenario '{scenario.name}': no data for symbol '{symbol}'"
                    )

        return len(self.validation_errors) == 0

    def validate_date_coverage(self, db: Session, scenario: str = "default") -> bool:
        """
        Validate that date coverage is complete for scenario.

        Args:
            db: Database session
            scenario: Scenario to validate

        Returns:
            True if validation passes, False otherwise
        """
        # Get scenario info
        scenario_obj = (
            db.query(DevScenario).filter(DevScenario.name == scenario).first()
        )

        if not scenario_obj:
            self.validation_errors.append(f"Scenario '{scenario}' not found")
            return False

        # Get available dates for scenario
        available_dates = (
            db.query(DevStockQuote.quote_date)
            .filter(DevStockQuote.scenario == scenario)
            .distinct()
            .all()
        )

        available_date_set = {d[0] for d in available_dates}

        # Check if we have data for start and end dates
        if scenario_obj.start_date not in available_date_set:
            self.validation_warnings.append(
                f"Scenario '{scenario}': no data for start_date ({scenario_obj.start_date})"
            )

        if scenario_obj.end_date not in available_date_set:
            self.validation_warnings.append(
                f"Scenario '{scenario}': no data for end_date ({scenario_obj.end_date})"
            )

        return True

    def validate_symbol_consistency(
        self, db: Session, scenario: str = "default"
    ) -> bool:
        """
        Validate symbol consistency across stock and option data.

        Args:
            db: Database session
            scenario: Scenario to validate

        Returns:
            True if validation passes, False otherwise
        """
        # Get stock symbols
        stock_symbols = {
            s[0]
            for s in db.query(DevStockQuote.symbol)
            .filter(DevStockQuote.scenario == scenario)
            .distinct()
            .all()
        }

        # Get option underlying symbols
        option_underlyings = {
            u[0]
            for u in db.query(DevOptionQuote.underlying)
            .filter(DevOptionQuote.scenario == scenario)
            .distinct()
            .all()
        }

        # Check that all option underlyings have stock data
        missing_underlyings = option_underlyings - stock_symbols
        if missing_underlyings:
            self.validation_warnings.append(
                f"Options exist for underlyings without stock data: {missing_underlyings}"
            )

        return True

    def validate_all(self, scenario: str = "default") -> dict[str, Any]:
        """
        Run all validation checks for a scenario.

        Args:
            scenario: Scenario to validate

        Returns:
            Dictionary with validation results
        """
        self.clear_results()

        with get_sync_session() as db:
            # Run all validations
            stock_valid = self.validate_stock_quote_integrity(db, scenario)
            option_valid = self.validate_option_quote_integrity(db, scenario)
            scenario_valid = self.validate_scenario_integrity(db)
            coverage_valid = self.validate_date_coverage(db, scenario)
            consistency_valid = self.validate_symbol_consistency(db, scenario)

            # Get counts for summary
            stock_count = (
                db.query(DevStockQuote)
                .filter(DevStockQuote.scenario == scenario)
                .count()
            )

            option_count = (
                db.query(DevOptionQuote)
                .filter(DevOptionQuote.scenario == scenario)
                .count()
            )

            scenario_count = db.query(DevScenario).count()

        overall_valid = all(
            [
                stock_valid,
                option_valid,
                scenario_valid,
                coverage_valid,
                consistency_valid,
            ]
        )

        return {
            "scenario": scenario,
            "overall_valid": overall_valid,
            "stock_quotes_valid": stock_valid,
            "option_quotes_valid": option_valid,
            "scenarios_valid": scenario_valid,
            "date_coverage_valid": coverage_valid,
            "symbol_consistency_valid": consistency_valid,
            "errors": self.validation_errors.copy(),
            "warnings": self.validation_warnings.copy(),
            "counts": {
                "stock_quotes": stock_count,
                "option_quotes": option_count,
                "scenarios": scenario_count,
            },
        }

    def get_validation_summary(self, results: dict[str, Any]) -> str:
        """
        Generate a human-readable validation summary.

        Args:
            results: Results from validate_all()

        Returns:
            Formatted summary string
        """
        lines = [
            f"Validation Summary for Scenario: {results['scenario']}",
            "=" * 50,
            f"Overall Status: {'✓ PASSED' if results['overall_valid'] else '✗ FAILED'}",
            "",
            "Component Status:",
            f"  Stock Quotes: {'✓' if results['stock_quotes_valid'] else '✗'}",
            f"  Option Quotes: {'✓' if results['option_quotes_valid'] else '✗'}",
            f"  Scenarios: {'✓' if results['scenarios_valid'] else '✗'}",
            f"  Date Coverage: {'✓' if results['date_coverage_valid'] else '✗'}",
            f"  Symbol Consistency: {'✓' if results['symbol_consistency_valid'] else '✗'}",
            "",
            "Data Counts:",
            f"  Stock Quotes: {results['counts']['stock_quotes']:,}",
            f"  Option Quotes: {results['counts']['option_quotes']:,}",
            f"  Scenarios: {results['counts']['scenarios']}",
        ]

        if results["errors"]:
            lines.extend(
                [
                    "",
                    f"Errors ({len(results['errors'])}):",
                    *[f"  • {error}" for error in results["errors"]],
                ]
            )

        if results["warnings"]:
            lines.extend(
                [
                    "",
                    f"Warnings ({len(results['warnings'])}):",
                    *["  • warning" for warning in results["warnings"]],
                ]
            )

        return "\n".join(lines)


# Convenience function for quick validation
def validate_test_data(scenario: str = "default") -> dict[str, Any]:
    """
    Quick validation of test data for a scenario.

    Args:
        scenario: Scenario to validate

    Returns:
        Validation results dictionary
    """
    validator = TestDataValidator()
    return validator.validate_all(scenario)
