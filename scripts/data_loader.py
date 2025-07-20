"""
Data loading utilities for test data migration.

Separates data loading logic from migration script for better code organization.
"""

import csv
import logging
from datetime import datetime
from decimal import Decimal
from pathlib import Path
from typing import Any

from sqlalchemy import delete

from app.models.assets import Option, asset_factory
from app.models.database.trading import TestOptionQuote, TestScenario, TestStockQuote
from app.storage.database import get_async_session, init_db

logger = logging.getLogger(__name__)


class DataLoader:
    """Handles loading and parsing of test data from various sources."""

    def __init__(self, data_dir: Path | None = None):
        """
        Initialize data loader.

        Args:
            data_dir: Directory containing test data files
        """
        if data_dir is None:
            data_dir = Path(__file__).parent.parent / "reference_code" / "test_data"

        self.data_dir = Path(data_dir)
        self.stats = {
            "files_processed": 0,
            "stocks_loaded": 0,
            "options_loaded": 0,
            "errors": [],
        }

    def reset_stats(self) -> None:
        """Reset loading statistics."""
        self.stats = {
            "files_processed": 0,
            "stocks_loaded": 0,
            "options_loaded": 0,
            "errors": [],
        }

    def load_csv_file(self, file_path: Path) -> list[dict[str, Any]]:
        """
        Load and parse CSV file.

        Args:
            file_path: Path to CSV file

        Returns:
            List of parsed records
        """
        records = []

        try:
            with open(file_path) as f:
                reader = csv.DictReader(f)
                for row in reader:
                    # Clean up the row data
                    cleaned_row = {}
                    for key, value in row.items():
                        # Remove any extra whitespace
                        cleaned_key = key.strip() if key else key
                        cleaned_value = value.strip() if value else value
                        cleaned_row[cleaned_key] = cleaned_value

                    records.append(cleaned_row)

            self.stats["files_processed"] += 1
            logger.info(f"Loaded {len(records)} records from {file_path}")

        except Exception as e:
            error_msg = f"Error loading {file_path}: {e}"
            self.stats["errors"].append(error_msg)
            logger.error(error_msg)

        return records

    def parse_stock_record(
        self, record: dict[str, Any], scenario: str
    ) -> TestStockQuote | None:
        """
        Parse CSV record into TestStockQuote object.

        Args:
            record: CSV record dictionary
            scenario: Scenario name

        Returns:
            TestStockQuote object or None if parsing fails
        """
        try:
            # Parse date from different possible formats
            quote_date_str = record.get("current_date", record.get("date", ""))
            if not quote_date_str:
                return None

            # Handle different date formats
            try:
                if "/" in quote_date_str:
                    # MM/DD/YYYY format
                    quote_date = datetime.strptime(quote_date_str, "%m/%d/%Y").date()
                else:
                    # YYYY-MM-DD format
                    quote_date = datetime.strptime(quote_date_str, "%Y-%m-%d").date()
            except ValueError:
                logger.warning(f"Could not parse date: {quote_date_str}")
                return None

            symbol = record.get("symbol", "").strip().upper()
            if not symbol:
                return None

            # Parse prices
            bid = self._parse_decimal(record.get("bid"))
            ask = self._parse_decimal(record.get("ask"))
            price = self._parse_decimal(record.get("price", record.get("close")))

            # If price is missing, use midpoint of bid/ask
            if price is None and bid is not None and ask is not None:
                price = (bid + ask) / 2

            volume = self._parse_int(record.get("volume", "1000"))

            stock_quote = TestStockQuote(
                symbol=symbol,
                quote_date=quote_date,
                scenario=scenario,
                bid=bid,
                ask=ask,
                price=price,
                volume=volume,
            )

            self.stats["stocks_loaded"] += 1
            return stock_quote

        except Exception as e:
            error_msg = f"Error parsing stock record {record}: {e}"
            self.stats["errors"].append(error_msg)
            logger.error(error_msg)
            return None

    def parse_option_record(
        self, record: dict[str, Any], scenario: str
    ) -> TestOptionQuote | None:
        """
        Parse CSV record into TestOptionQuote object.

        Args:
            record: CSV record dictionary
            scenario: Scenario name

        Returns:
            TestOptionQuote object or None if parsing fails
        """
        try:
            # Parse date
            quote_date_str = record.get("current_date", record.get("date", ""))
            if not quote_date_str:
                return None

            try:
                if "/" in quote_date_str:
                    quote_date = datetime.strptime(quote_date_str, "%m/%d/%Y").date()
                else:
                    quote_date = datetime.strptime(quote_date_str, "%Y-%m-%d").date()
            except ValueError:
                logger.warning(f"Could not parse date: {quote_date_str}")
                return None

            symbol = record.get("symbol", "").strip().upper()
            if not symbol:
                return None

            # Try to parse option symbol to get details
            asset = asset_factory(symbol)
            if not asset or not isinstance(asset, Option):
                return None

            # Parse prices
            bid = self._parse_decimal(record.get("bid"))
            ask = self._parse_decimal(record.get("ask"))
            price = self._parse_decimal(record.get("price", record.get("close")))

            if price is None and bid is not None and ask is not None:
                price = (bid + ask) / 2

            volume = self._parse_int(record.get("volume", "100"))

            option_quote = TestOptionQuote(
                symbol=symbol,
                underlying=asset.underlying.symbol,
                quote_date=quote_date,
                scenario=scenario,
                bid=bid,
                ask=ask,
                price=price,
                strike=asset.strike,
                expiration=asset.expiration,
                option_type=asset.option_type,
                volume=volume,
            )

            self.stats["options_loaded"] += 1
            return option_quote

        except Exception as e:
            error_msg = f"Error parsing option record {record}: {e}"
            self.stats["errors"].append(error_msg)
            logger.error(error_msg)
            return None

    def _parse_decimal(self, value: Any) -> Decimal | None:
        """Parse value as Decimal."""
        if value is None or value == "":
            return None

        try:
            return Decimal(str(value))
        except (ValueError, TypeError):
            return None

    def _parse_int(self, value: Any) -> int | None:
        """Parse value as integer."""
        if value is None or value == "":
            return None

        try:
            return int(float(str(value)))
        except (ValueError, TypeError):
            return None

    def discover_csv_files(self) -> list[Path]:
        """
        Discover CSV files in the data directory.

        Returns:
            List of CSV file paths
        """
        csv_files = []

        if self.data_dir.exists():
            csv_files = list(self.data_dir.glob("*.csv"))
            csv_files.extend(list(self.data_dir.glob("**/*.csv")))

        logger.info(f"Discovered {len(csv_files)} CSV files in {self.data_dir}")
        return csv_files

    async def load_csv_data_to_database(
        self, scenario: str = "default"
    ) -> dict[str, Any]:
        """
        Load all CSV data into database.

        Args:
            scenario: Scenario name to load data for

        Returns:
            Statistics about the loading process
        """
        self.reset_stats()

        # Initialize database
        await init_db()

        # Clear existing data for scenario
        async for db in get_async_session():
            await db.execute(
                delete(TestStockQuote).where(TestStockQuote.scenario == scenario)
            )
            await db.execute(
                delete(TestOptionQuote).where(TestOptionQuote.scenario == scenario)
            )
            await db.commit()
            break

        # Discover and load CSV files
        csv_files = self.discover_csv_files()

        for csv_file in csv_files:
            await self._load_single_csv_file(csv_file, scenario)

        return {
            "scenario": scenario,
            "files_processed": self.stats["files_processed"],
            "stocks_loaded": self.stats["stocks_loaded"],
            "options_loaded": self.stats["options_loaded"],
            "total_loaded": self.stats["stocks_loaded"] + self.stats["options_loaded"],
            "errors": self.stats["errors"],
        }

    async def _load_single_csv_file(self, csv_file: Path, scenario: str) -> None:
        """
        Load a single CSV file into the database.

        Args:
            csv_file: Path to CSV file
            scenario: Scenario name
        """
        records = self.load_csv_file(csv_file)
        if not records:
            return

        stock_quotes = []
        option_quotes = []

        # Parse records
        for record in records:
            symbol = record.get("symbol", "").strip().upper()
            if not symbol:
                continue

            # Determine if it's a stock or option based on symbol
            asset = asset_factory(symbol)

            if asset and isinstance(asset, Option):
                option_quote = self.parse_option_record(record, scenario)
                if option_quote:
                    option_quotes.append(option_quote)
            else:
                stock_quote = self.parse_stock_record(record, scenario)
                if stock_quote:
                    stock_quotes.append(stock_quote)

        # Batch insert into database
        if stock_quotes or option_quotes:
            async for db in get_async_session():
                if stock_quotes:
                    db.add_all(stock_quotes)

                if option_quotes:
                    db.add_all(option_quotes)

                try:
                    await db.commit()
                    logger.info(
                        f"Loaded {len(stock_quotes)} stocks and {len(option_quotes)} options from {csv_file.name}"
                    )
                except Exception as e:
                    await db.rollback()
                    error_msg = f"Error inserting data from {csv_file}: {e}"
                    self.stats["errors"].append(error_msg)
                    logger.error(error_msg)

                break

    async def load_predefined_scenarios(self) -> int:
        """
        Load predefined test scenarios into database.

        Returns:
            Number of scenarios created
        """
        from scripts.create_scenarios import PREDEFINED_SCENARIOS

        await init_db()

        created_count = 0

        async for db in get_async_session():
            for _scenario_key, scenario_data in PREDEFINED_SCENARIOS.items():
                # Check if scenario already exists
                existing = await db.execute(
                    db.query(TestScenario).where(
                        TestScenario.name == scenario_data["name"]
                    )
                )

                if not existing.fetchone():
                    scenario = TestScenario(
                        name=scenario_data["name"],
                        description=scenario_data["description"],
                        start_date=scenario_data["start_date"],
                        end_date=scenario_data["end_date"],
                        symbols=scenario_data["symbols"],
                        market_condition=scenario_data["market_condition"],
                    )
                    db.add(scenario)
                    created_count += 1

            try:
                await db.commit()
            except Exception as e:
                await db.rollback()
                logger.error(f"Error creating scenarios: {e}")
                return 0

            break

        return created_count

    def get_loading_summary(self, results: dict[str, Any]) -> str:
        """
        Generate summary of loading results.

        Args:
            results: Results from load_csv_data_to_database()

        Returns:
            Formatted summary string
        """
        lines = [
            f"Data Loading Summary for Scenario: {results['scenario']}",
            "=" * 50,
            f"Files Processed: {results['files_processed']}",
            f"Stock Quotes Loaded: {results['stocks_loaded']:,}",
            f"Option Quotes Loaded: {results['options_loaded']:,}",
            f"Total Records Loaded: {results['total_loaded']:,}",
        ]

        if results["errors"]:
            lines.extend(
                [
                    "",
                    f"Errors ({len(results['errors'])}):",
                    *[f"  • {error}" for error in results["errors"]],
                ]
            )
        else:
            lines.append("\n✓ No errors encountered")

        return "\n".join(lines)


# Convenience functions
async def load_test_data_from_csv(
    scenario: str = "default", data_dir: Path | None = None
) -> dict[str, Any]:
    """
    Load test data from CSV files.

    Args:
        scenario: Scenario name
        data_dir: Directory containing CSV files

    Returns:
        Loading results
    """
    loader = DataLoader(data_dir)
    return await loader.load_csv_data_to_database(scenario)


async def load_scenarios() -> int:
    """
    Load predefined scenarios.

    Returns:
        Number of scenarios created
    """
    loader = DataLoader()
    return await loader.load_predefined_scenarios()
