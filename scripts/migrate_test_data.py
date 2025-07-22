#!/usr/bin/env python3
"""
Data migration script to populate test data tables from existing CSV files.

This script reads the existing test data CSV files and populates the
DevStockQuote and DevOptionQuote database tables for Phase 3.
"""

import asyncio
import csv
import gzip
import random
import sys
from datetime import date, datetime, timedelta
from pathlib import Path
from typing import Any

# Add the app directory to the path
sys.path.insert(0, str(Path(__file__).parent.parent))

from sqlalchemy import delete, select
from sqlalchemy.exc import IntegrityError

from app.models.assets import Option, Stock, asset_factory
from app.models.database.trading import DevOptionQuote, DevScenario, DevStockQuote
from app.storage.database import get_async_session, init_db

# Expanded symbols for comprehensive test data
EXPANDED_SYMBOLS = [
    "AAPL",
    "GOOGL",
    "MSFT",
    "TSLA",
    "AMZN",
    "NVDA",
    "META",
    "NFLX",
    "SPY",
    "QQQ",
    "IWM",
    "GLD",
    "AAL",
    "AMD",
    "F",
    "GE",
]

# Test date ranges for different market conditions
TEST_DATE_RANGES = [
    ("2017-01-27", "2017-01-28"),  # Existing calm period
    ("2017-03-24", "2017-03-25"),  # Existing volatile period
    ("2023-01-03", "2023-01-31"),  # Recent calm period
    ("2023-03-01", "2023-03-31"),  # Recent volatile period
]

# Predefined test scenarios
PREDEFINED_SCENARIOS = {
    "calm_market": {
        "name": "Calm Market Conditions",
        "description": "Low volatility, steady price movements",
        "start_date": date(2017, 1, 27),
        "end_date": date(2017, 1, 28),
        "market_condition": "calm",
        "symbols": ["AAPL", "GOOGL", "MSFT", "SPY"],
    },
    "volatile_market": {
        "name": "Volatile Market Conditions",
        "description": "High volatility, rapid price changes",
        "start_date": date(2017, 3, 24),
        "end_date": date(2017, 3, 25),
        "market_condition": "volatile",
        "symbols": ["TSLA", "NVDA", "AMD", "NFLX"],
    },
    "trending_up": {
        "name": "Bull Market Trend",
        "description": "Consistent upward price movement",
        "start_date": date(2023, 1, 3),
        "end_date": date(2023, 1, 31),
        "market_condition": "trending",
        "symbols": ["AAPL", "MSFT", "GOOGL", "AMZN"],
    },
}


class DataMigrator:
    """Migrates test data from CSV files to database tables."""

    def __init__(self):
        self.data_file = (
            Path(__file__).parent.parent
            / "app"
            / "adapters"
            / "test_data"
            / "data.csv.gz"
        )
        self.batch_size = 1000

    async def migrate_data(self, scenario: str = "default") -> dict[str, Any]:
        """
        Migrate test data from CSV to database tables.

        Args:
            scenario: Test scenario name for data categorization

        Returns:
            Migration statistics
        """
        print(f"Starting test data migration for scenario: {scenario}")

        # Initialize database
        await init_db()

        # Clear existing test data
        await self._clear_existing_data()

        # Load and process data
        data = self._load_csv_data()

        # Separate stocks and options
        stock_quotes = []
        option_quotes = []

        for symbol, quote_date, bid, ask in data:
            asset = asset_factory(symbol)

            if isinstance(asset, Stock):
                stock_quotes.append(
                    {
                        "symbol": asset.symbol,
                        "quote_date": datetime.strptime(quote_date, "%Y-%m-%d").date(),
                        "bid": float(bid),
                        "ask": float(ask),
                        "price": (float(bid) + float(ask)) / 2,
                        "volume": None,  # Not in test data
                        "scenario": scenario,
                    }
                )
            elif isinstance(asset, Option):
                option_quotes.append(
                    {
                        "symbol": asset.symbol,
                        "underlying": asset.underlying.symbol,
                        "expiration": asset.expiration_date,
                        "strike": float(asset.strike),
                        "option_type": asset.option_type.lower(),
                        "quote_date": datetime.strptime(quote_date, "%Y-%m-%d").date(),
                        "bid": float(bid),
                        "ask": float(ask),
                        "price": (float(bid) + float(ask)) / 2,
                        "volume": None,  # Not in test data
                        "scenario": scenario,
                    }
                )

        # Insert data in batches
        stock_count = await self._insert_stock_quotes(stock_quotes)
        option_count = await self._insert_option_quotes(option_quotes)

        stats = {
            "scenario": scenario,
            "stocks_migrated": stock_count,
            "options_migrated": option_count,
            "total_migrated": stock_count + option_count,
            "available_dates": self._get_available_dates(data),
        }

        print(f"Migration completed: {stats}")
        return stats

    def _load_csv_data(self) -> list[tuple]:
        """Load test data from compressed CSV file."""
        print(f"Loading test data from: {self.data_file}")

        if not self.data_file.exists():
            raise FileNotFoundError(f"Test data file not found: {self.data_file}")

        data = []

        with gzip.open(self.data_file, "rt") as f:
            reader = csv.reader(f, delimiter="\t")

            for row in reader:
                if len(row) < 4:
                    continue

                symbol, quote_date, bid, ask = row[0], row[1], row[2], row[3]

                # Skip invalid data
                try:
                    float(bid)
                    float(ask)
                    datetime.strptime(quote_date, "%Y-%m-%d")
                except ValueError:
                    continue

                data.append((symbol, quote_date, bid, ask))

        print(f"Loaded {len(data)} quotes from CSV")
        return data

    def _get_available_dates(self, data: list[tuple]) -> list[str]:
        """Get list of available dates from the data."""
        dates = set()
        for _symbol, quote_date, _bid, _ask in data:
            dates.add(quote_date)
        return sorted(dates)

    async def _clear_existing_data(self) -> None:
        """Clear existing test data from database."""
        print("Clearing existing test data...")

        async for db in get_async_session():
            # Clear test stock quotes
            await db.execute(delete(DevStockQuote))

            # Clear test option quotes
            await db.execute(delete(DevOptionQuote))

            # Clear test scenarios
            await db.execute(delete(DevScenario))

            await db.commit()
            break

    async def _insert_stock_quotes(self, stock_quotes: list[dict[str, Any]]) -> int:
        """Insert stock quotes in batches."""
        if not stock_quotes:
            return 0

        print(f"Inserting {len(stock_quotes)} stock quotes...")

        async for db in get_async_session():
            count = 0

            for i in range(0, len(stock_quotes), self.batch_size):
                batch = stock_quotes[i : i + self.batch_size]

                # Create DevStockQuote objects
                db_quotes = []
                for quote_data in batch:
                    db_quote = DevStockQuote(**quote_data)
                    db_quotes.append(db_quote)

                # Insert batch
                db.add_all(db_quotes)

                try:
                    await db.commit()
                    count += len(batch)
                    print(
                        f"Inserted batch of {len(batch)} stock quotes (total: {count})"
                    )
                except IntegrityError as e:
                    print(f"Error inserting stock quote batch: {e}")
                    await db.rollback()

            break

        return count

    async def _insert_option_quotes(self, option_quotes: list[dict[str, Any]]) -> int:
        """Insert option quotes in batches."""
        if not option_quotes:
            return 0

        print(f"Inserting {len(option_quotes)} option quotes...")

        async for db in get_async_session():
            count = 0

            for i in range(0, len(option_quotes), self.batch_size):
                batch = option_quotes[i : i + self.batch_size]

                # Create DevOptionQuote objects
                db_quotes = []
                for quote_data in batch:
                    db_quote = DevOptionQuote(**quote_data)
                    db_quotes.append(db_quote)

                # Insert batch
                db.add_all(db_quotes)

                try:
                    await db.commit()
                    count += len(batch)
                    print(
                        f"Inserted batch of {len(batch)} option quotes (total: {count})"
                    )
                except IntegrityError as e:
                    print(f"Error inserting option quote batch: {e}")
                    await db.rollback()

            break

        return count

    async def verify_migration(self, scenario: str = "default") -> dict[str, Any]:
        """Verify the migration was successful."""
        print(f"Verifying migration for scenario: {scenario}")

        verification = {}

        async for db in get_async_session():
            try:
                # Count stock quotes
                stock_result = await db.execute(
                    select(DevStockQuote).where(DevStockQuote.scenario == scenario)
                )
                stock_count = len(stock_result.fetchall())

                # Count option quotes
                option_result = await db.execute(
                    select(DevOptionQuote).where(DevOptionQuote.scenario == scenario)
                )
                option_count = len(option_result.fetchall())

                verification = {
                    "scenario": scenario,
                    "stock_quotes_count": stock_count,
                    "option_quotes_count": option_count,
                    "stock_samples": [],
                    "option_samples": [],
                }

                print(f"Verification results: {verification}")
                break  # Exit the async for loop

            except Exception as e:
                print(f"Error during verification: {e}")
                verification = {
                    "scenario": scenario,
                    "stock_quotes_count": 0,
                    "option_quotes_count": 0,
                    "stock_samples": [],
                    "option_samples": [],
                    "error": str(e),
                }
                break

        return verification

    async def generate_expanded_dataset(self) -> dict[str, Any]:
        """Generate expanded test dataset with multiple symbols and dates."""
        print("Generating expanded test dataset...")

        stock_quotes = []
        option_quotes = []

        # Generate data for each date range
        for start_date_str, end_date_str in TEST_DATE_RANGES:
            start_date = datetime.strptime(start_date_str, "%Y-%m-%d").date()
            end_date = datetime.strptime(end_date_str, "%Y-%m-%d").date()

            # Determine scenario based on date range
            if start_date_str == "2017-01-27":
                scenario = "calm_market"
                base_volatility = 0.15
            elif start_date_str == "2017-03-24":
                scenario = "volatile_market"
                base_volatility = 0.35
            elif start_date_str == "2023-01-03":
                scenario = "trending_up"
                base_volatility = 0.20
            else:
                scenario = "default"
                base_volatility = 0.25

            current_date = start_date
            while current_date <= end_date:
                # Generate stock quotes for all symbols
                for symbol in EXPANDED_SYMBOLS:
                    stock_data = self._generate_stock_quote(
                        symbol, current_date, scenario, base_volatility
                    )
                    stock_quotes.append(stock_data)

                    # Generate option chains for each stock
                    option_chain = self._generate_option_chain(
                        symbol,
                        current_date,
                        stock_data["price"],
                        scenario,
                        base_volatility,
                    )
                    option_quotes.extend(option_chain)

                current_date += timedelta(days=1)

        # Insert generated data
        stock_count = await self._insert_stock_quotes(stock_quotes)
        option_count = await self._insert_option_quotes(option_quotes)

        return {
            "stocks_generated": stock_count,
            "options_generated": option_count,
            "total_generated": stock_count + option_count,
            "scenarios": list({q["scenario"] for q in stock_quotes}),
        }

    def _generate_stock_quote(
        self, symbol: str, quote_date: date, scenario: str, volatility: float
    ) -> dict[str, Any]:
        """Generate realistic stock quote data."""
        # Base prices for different symbols
        base_prices = {
            "AAPL": 175.0,
            "GOOGL": 140.0,
            "MSFT": 370.0,
            "TSLA": 200.0,
            "AMZN": 170.0,
            "NVDA": 480.0,
            "META": 350.0,
            "NFLX": 450.0,
            "SPY": 450.0,
            "QQQ": 370.0,
            "IWM": 190.0,
            "GLD": 180.0,
            "AAL": 15.0,
            "AMD": 120.0,
            "F": 12.0,
            "GE": 100.0,
        }

        base_price = base_prices.get(symbol, 100.0)

        # Add some randomness based on volatility
        price_change = random.uniform(-volatility, volatility) * base_price
        price = base_price + price_change

        # Calculate bid/ask spread (tighter for liquid stocks)
        if symbol in ["AAPL", "MSFT", "SPY", "QQQ"]:
            spread = 0.01  # 1 cent spread for very liquid stocks
        else:
            spread = price * 0.001  # 0.1% spread for others

        bid = round(price - spread / 2, 2)
        ask = round(price + spread / 2, 2)

        return {
            "symbol": symbol,
            "quote_date": quote_date,
            "bid": bid,
            "ask": ask,
            "price": round((bid + ask) / 2, 2),
            "volume": random.randint(1000000, 50000000),
            "scenario": scenario,
        }

    def _generate_option_chain(
        self,
        underlying: str,
        quote_date: date,
        underlying_price: float,
        scenario: str,
        volatility: float,
    ) -> list[dict[str, Any]]:
        """Generate option chain for a given underlying."""
        options = []

        # Generate expirations (weekly, monthly, quarterly)
        expirations = [
            quote_date + timedelta(days=7),  # Weekly
            quote_date + timedelta(days=30),  # Monthly
            quote_date + timedelta(days=90),  # Quarterly
        ]

        for expiration in expirations:
            # Skip if expiration is in the past
            if expiration <= quote_date:
                continue

            # Generate strikes around the current price
            strikes = self._generate_strikes(underlying_price)

            for strike in strikes:
                for option_type in ["call", "put"]:
                    # Calculate option price using simplified Black-Scholes approximation
                    days_to_expiry = (expiration - quote_date).days
                    option_price = self._calculate_option_price(
                        underlying_price,
                        strike,
                        days_to_expiry,
                        volatility,
                        option_type,
                    )

                    # Create option symbol
                    exp_str = expiration.strftime("%y%m%d")
                    strike_str = f"{int(strike * 1000):08d}"
                    option_symbol = (
                        f"{underlying}{exp_str}{option_type[0].upper()}{strike_str}"
                    )

                    # Calculate bid/ask spread (wider for options)
                    spread = max(0.05, option_price * 0.02)  # Min 5 cents or 2%
                    bid = round(max(0, option_price - spread / 2), 2)
                    ask = round(option_price + spread / 2, 2)

                    options.append(
                        {
                            "symbol": option_symbol,
                            "underlying": underlying,
                            "expiration": expiration,
                            "strike": strike,
                            "option_type": option_type,
                            "quote_date": quote_date,
                            "bid": bid,
                            "ask": ask,
                            "price": round((bid + ask) / 2, 2),
                            "volume": random.randint(0, 10000),
                            "scenario": scenario,
                        }
                    )

        return options

    def _generate_strikes(self, underlying_price: float) -> list[float]:
        """Generate strike prices around the underlying price."""
        strikes = []

        # Determine strike interval based on price
        if underlying_price < 50:
            interval = 1.0
        elif underlying_price < 200:
            interval = 5.0
        else:
            interval = 10.0

        # Generate strikes from 80% to 120% of underlying price
        start = int(underlying_price * 0.8 / interval) * interval
        end = int(underlying_price * 1.2 / interval) * interval

        current = start
        while current <= end:
            strikes.append(current)
            current += interval

        return strikes

    def _calculate_option_price(
        self,
        underlying_price: float,
        strike: float,
        days_to_expiry: int,
        volatility: float,
        option_type: str,
    ) -> float:
        """Simple option pricing model for test data."""
        # Intrinsic value
        if option_type == "call":
            intrinsic = max(0, underlying_price - strike)
        else:
            intrinsic = max(0, strike - underlying_price)

        # Time value (simplified)
        time_value = (
            volatility * underlying_price * (days_to_expiry / 365) ** 0.5
        ) * 0.4

        # Adjust time value based on moneyness
        moneyness = underlying_price / strike
        if 0.95 <= moneyness <= 1.05:  # ATM
            time_value *= 1.0
        elif 0.90 <= moneyness <= 1.10:  # Near the money
            time_value *= 0.7
        else:  # Far from money
            time_value *= 0.3

        return max(0.01, intrinsic + time_value)

    async def create_test_scenarios(self) -> int:
        """Create predefined test scenarios in the database."""
        print("Creating test scenarios...")

        count = 0
        async for db in get_async_session():
            for _scenario_key, scenario_data in PREDEFINED_SCENARIOS.items():
                scenario = DevScenario(
                    name=scenario_data["name"],
                    description=scenario_data["description"],
                    start_date=scenario_data["start_date"],
                    end_date=scenario_data["end_date"],
                    symbols=scenario_data["symbols"],
                    market_condition=scenario_data["market_condition"],
                )
                db.add(scenario)
                count += 1

            try:
                await db.commit()
                print(f"Created {count} test scenarios")
            except IntegrityError as e:
                print(f"Error creating scenarios: {e}")
                await db.rollback()
                count = 0

            break

        return count


async def main():
    """Main migration entry point."""
    migrator = DataMigrator()

    try:
        # Step 1: Create test scenarios
        scenario_count = await migrator.create_test_scenarios()
        print(f"\nCreated {scenario_count} test scenarios")

        # Step 2: Run migration of existing CSV data
        stats = await migrator.migrate_data("default")
        print("\nCSV Migration completed!")
        print(f"Stock quotes migrated: {stats['stocks_migrated']}")
        print(f"Option quotes migrated: {stats['options_migrated']}")
        print(f"Total quotes migrated: {stats['total_migrated']}")
        print(f"Available dates: {stats['available_dates']}")

        # Step 3: Generate expanded dataset
        expanded_stats = await migrator.generate_expanded_dataset()
        print("\nExpanded dataset generation completed!")
        print(f"Stock quotes generated: {expanded_stats['stocks_generated']}")
        print(f"Option quotes generated: {expanded_stats['options_generated']}")
        print(f"Total quotes generated: {expanded_stats['total_generated']}")
        print(f"Scenarios: {expanded_stats['scenarios']}")

        # Step 4: Verify all data
        total_stats = {
            "total_stocks": stats["stocks_migrated"]
            + expanded_stats["stocks_generated"],
            "total_options": stats["options_migrated"]
            + expanded_stats["options_generated"],
            "total_quotes": stats["total_migrated"] + expanded_stats["total_generated"],
        }

        print("\n========== FINAL STATISTICS ==========")
        print(f"Total stock quotes: {total_stats['total_stocks']}")
        print(f"Total option quotes: {total_stats['total_options']}")
        print(f"Total quotes in database: {total_stats['total_quotes']}")
        print(f"Symbols: {len(EXPANDED_SYMBOLS)}")
        print(f"Date ranges: {len(TEST_DATE_RANGES)}")
        print(f"Scenarios: {scenario_count}")

        # Verify migration
        for scenario in ["default", "calm_market", "volatile_market", "trending_up"]:
            verification = await migrator.verify_migration(scenario)
            print(f"\nScenario '{scenario}':")
            print(f"  Stock quotes: {verification['stock_quotes_count']}")
            print(f"  Option quotes: {verification['option_quotes_count']}")

    except Exception as e:
        print(f"Migration failed: {e}")
        sys.exit(1)


if __name__ == "__main__":
    asyncio.run(main())
