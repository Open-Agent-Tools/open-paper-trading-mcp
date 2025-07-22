"""
Integration tests for test data migration from CSV to database.

Tests the migration process, data integrity, and expanded dataset generation.
"""

import sys
from datetime import date
from pathlib import Path

import pytest

# Add the app directory to the path
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from sqlalchemy import and_, delete, select

from app.models.database.trading import DevOptionQuote, DevScenario, DevStockQuote
from app.storage.database import get_async_session, init_db
from scripts.migrate_test_data import EXPANDED_SYMBOLS, TEST_DATE_RANGES, DataMigrator


class TestDataMigration:
    """Test data migration from CSV to database."""

    @pytest.fixture(autouse=True)
    async def setup_and_teardown(self):
        """Set up test database and clean up after tests."""
        # Initialize database
        await init_db()

        # Clean up any existing test data before tests
        async for db in get_async_session():
            await db.execute(delete(DevStockQuote))
            await db.execute(delete(DevOptionQuote))
            await db.execute(delete(DevScenario))
            await db.commit()
            break

        yield

        # Clean up after tests
        async for db in get_async_session():
            await db.execute(delete(DevStockQuote))
            await db.execute(delete(DevOptionQuote))
            await db.execute(delete(DevScenario))
            await db.commit()
            break

    @pytest.mark.asyncio
    async def test_csv_to_database_migration(self):
        """Test migration from CSV to database."""
        migrator = DataMigrator()

        # Run migration
        stats = await migrator.migrate_data("default")

        # Verify stats
        assert stats["stocks_migrated"] > 0
        assert stats["options_migrated"] > 0
        assert (
            stats["total_migrated"]
            == stats["stocks_migrated"] + stats["options_migrated"]
        )
        assert len(stats["available_dates"]) > 0

        # Verify data in database
        async for db in get_async_session():
            # Check stock quotes
            stock_count = await db.execute(
                select(DevStockQuote).where(DevStockQuote.scenario == "default")
            )
            stock_records = stock_count.fetchall()
            assert len(stock_records) == stats["stocks_migrated"]

            # Check option quotes
            option_count = await db.execute(
                select(DevOptionQuote).where(DevOptionQuote.scenario == "default")
            )
            option_records = option_count.fetchall()
            assert len(option_records) == stats["options_migrated"]

            # Verify sample data
            aal_quote = await db.execute(
                select(DevStockQuote).where(
                    and_(
                        DevStockQuote.symbol == "AAL",
                        DevStockQuote.quote_date == date(2017, 1, 27),
                        DevStockQuote.scenario == "default",
                    )
                )
            )
            aal_record = aal_quote.fetchone()
            assert aal_record is not None
            assert aal_record[0].bid is not None
            assert aal_record[0].ask is not None
            assert aal_record[0].price is not None

            break

    @pytest.mark.asyncio
    async def test_expanded_dataset_generation(self):
        """Test generation of expanded test dataset."""
        migrator = DataMigrator()

        # Generate expanded dataset
        stats = await migrator.generate_expanded_dataset()

        # Verify stats
        assert stats["stocks_generated"] > 0
        assert stats["options_generated"] > 0
        assert (
            stats["total_generated"]
            == stats["stocks_generated"] + stats["options_generated"]
        )
        assert len(stats["scenarios"]) > 0

        # Verify all symbols were generated
        async for db in get_async_session():
            for symbol in EXPANDED_SYMBOLS:
                # Check stock quotes exist
                stock_exists = await db.execute(
                    select(DevStockQuote).where(DevStockQuote.symbol == symbol).limit(1)
                )
                assert stock_exists.fetchone() is not None, (
                    f"Stock quotes missing for {symbol}"
                )

                # Check option quotes exist
                option_exists = await db.execute(
                    select(DevOptionQuote)
                    .where(DevOptionQuote.underlying == symbol)
                    .limit(1)
                )
                assert option_exists.fetchone() is not None, (
                    f"Option quotes missing for {symbol}"
                )

            break

    @pytest.mark.asyncio
    async def test_scenario_creation(self):
        """Test creation of predefined test scenarios."""
        migrator = DataMigrator()

        # Create scenarios
        count = await migrator.create_test_scenarios()
        assert count > 0

        # Verify scenarios in database
        async for db in get_async_session():
            # Check all scenarios exist
            scenarios = await db.execute(select(DevScenario))
            scenario_records = scenarios.fetchall()
            assert len(scenario_records) == count

            # Verify specific scenario
            calm_scenario = await db.execute(
                select(DevScenario).where(DevScenario.name == "Calm Market Conditions")
            )
            calm_record = calm_scenario.fetchone()
            assert calm_record is not None
            assert calm_record[0].market_condition == "calm"
            assert len(calm_record[0].symbols) > 0
            assert calm_record[0].start_date == date(2017, 1, 27)

            break

    @pytest.mark.asyncio
    async def test_data_integrity_after_migration(self):
        """Test data integrity and consistency after migration."""
        migrator = DataMigrator()

        # Run full migration
        await migrator.create_test_scenarios()
        await migrator.migrate_data("default")
        await migrator.generate_expanded_dataset()

        async for db in get_async_session():
            # Test bid/ask/price consistency
            stock_quotes = await db.execute(select(DevStockQuote).limit(100))
            for quote_row in stock_quotes:
                quote = quote_row[0]
                if quote.bid and quote.ask and quote.price:
                    # Price should be between bid and ask
                    assert quote.bid <= quote.price <= quote.ask, (
                        f"Price inconsistency for {quote.symbol}: bid={quote.bid}, price={quote.price}, ask={quote.ask}"
                    )

                    # Spread should be reasonable
                    spread = float(quote.ask - quote.bid)
                    spread_pct = spread / float(quote.price)
                    assert spread_pct < 0.05, (
                        f"Spread too wide for {quote.symbol}: {spread_pct:.2%}"
                    )

            # Test option data integrity
            option_quotes = await db.execute(select(DevOptionQuote).limit(100))
            for quote_row in option_quotes:
                quote = quote_row[0]
                # Verify option fields
                assert quote.underlying is not None
                assert quote.strike > 0
                assert quote.option_type in ["call", "put"]
                assert quote.expiration > quote.quote_date

            break

    @pytest.mark.asyncio
    async def test_date_range_coverage(self):
        """Test that all date ranges are properly covered."""
        migrator = DataMigrator()

        # Generate data
        await migrator.generate_expanded_dataset()

        async for db in get_async_session():
            # Check each date range
            for start_str, end_str in TEST_DATE_RANGES:
                start_date = date.fromisoformat(start_str)
                end_date = date.fromisoformat(end_str)

                # Query quotes in date range
                quotes_in_range = await db.execute(
                    select(DevStockQuote).where(
                        and_(
                            DevStockQuote.quote_date >= start_date,
                            DevStockQuote.quote_date <= end_date,
                        )
                    )
                )
                records = quotes_in_range.fetchall()
                assert len(records) > 0, (
                    f"No quotes found for date range {start_str} to {end_str}"
                )

            break

    @pytest.mark.asyncio
    async def test_migration_idempotency(self):
        """Test that migration can be run multiple times safely."""
        migrator = DataMigrator()

        # First migration
        stats1 = await migrator.migrate_data("default")

        # Second migration (should clear and re-migrate)
        stats2 = await migrator.migrate_data("default")

        # Stats should be the same
        assert stats1["stocks_migrated"] == stats2["stocks_migrated"]
        assert stats1["options_migrated"] == stats2["options_migrated"]

        # Verify no duplicates in database
        async for db in get_async_session():
            # Count total records
            stock_count = await db.execute(
                select(DevStockQuote).where(DevStockQuote.scenario == "default")
            )
            assert len(stock_count.fetchall()) == stats2["stocks_migrated"]

            break
