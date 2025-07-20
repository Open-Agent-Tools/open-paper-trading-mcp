#!/usr/bin/env python3
"""
Script to create predefined test scenarios in the database.

This can be run independently to set up test scenarios without running
the full data migration.
"""

import asyncio
import sys
from datetime import date
from pathlib import Path

# Add the app directory to the path
sys.path.insert(0, str(Path(__file__).parent.parent))

from sqlalchemy import select
from sqlalchemy.exc import IntegrityError

from app.models.database.trading import TestScenario
from app.storage.database import get_async_session, init_db

# Predefined test scenarios
PREDEFINED_SCENARIOS = {
    "default": {
        "name": "Default Test Data",
        "description": "Original test data from CSV files",
        "start_date": date(2017, 1, 27),
        "end_date": date(2017, 3, 25),
        "market_condition": "mixed",
        "symbols": ["AAL", "GOOG"],
    },
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
    "bear_market": {
        "name": "Bear Market Conditions",
        "description": "Declining prices and negative sentiment",
        "start_date": date(2023, 3, 1),
        "end_date": date(2023, 3, 31),
        "market_condition": "bearish",
        "symbols": ["META", "NFLX", "TSLA", "IWM"],
    },
    "earnings_season": {
        "name": "Earnings Season",
        "description": "High volatility around earnings announcements",
        "start_date": date(2017, 1, 27),
        "end_date": date(2017, 1, 28),
        "market_condition": "earnings",
        "symbols": ["AAL", "AAPL", "GOOGL", "AMZN"],
    },
}


async def create_test_scenarios() -> int:
    """Create predefined test scenarios in the database."""
    print("Creating test scenarios...")

    # Initialize database
    await init_db()

    created_count = 0
    updated_count = 0

    async for db in get_async_session():
        for scenario_key, scenario_data in PREDEFINED_SCENARIOS.items():
            # Check if scenario already exists
            existing = await db.execute(
                select(TestScenario).where(TestScenario.name == scenario_data["name"])
            )
            existing_scenario = existing.fetchone()

            if existing_scenario:
                # Update existing scenario
                scenario = existing_scenario[0]
                scenario.description = scenario_data["description"]
                scenario.start_date = scenario_data["start_date"]
                scenario.end_date = scenario_data["end_date"]
                scenario.symbols = scenario_data["symbols"]
                scenario.market_condition = scenario_data["market_condition"]
                updated_count += 1
                print(f"Updated scenario: {scenario_data['name']}")
            else:
                # Create new scenario
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
                print(f"Created scenario: {scenario_data['name']}")

        try:
            await db.commit()
            print(
                f"\nSuccessfully created {created_count} and updated {updated_count} scenarios"
            )
        except IntegrityError as e:
            print(f"Error saving scenarios: {e}")
            await db.rollback()
            return 0

        break

    return created_count + updated_count


async def list_scenarios():
    """List all test scenarios in the database."""
    print("\nAvailable test scenarios:")
    print("-" * 80)

    async for db in get_async_session():
        scenarios = await db.execute(
            select(TestScenario).order_by(TestScenario.start_date)
        )

        for scenario_row in scenarios:
            scenario = scenario_row[0]
            print(f"\nName: {scenario.name}")
            print(f"Description: {scenario.description}")
            print(f"Date Range: {scenario.start_date} to {scenario.end_date}")
            print(f"Market Condition: {scenario.market_condition}")
            print(f"Symbols: {', '.join(scenario.symbols)}")

        break


async def main():
    """Main entry point."""
    import argparse

    parser = argparse.ArgumentParser(description="Manage test scenarios")
    parser.add_argument("action", choices=["create", "list"], help="Action to perform")

    args = parser.parse_args()

    if args.action == "create":
        count = await create_test_scenarios()
        if count > 0:
            await list_scenarios()
    elif args.action == "list":
        await list_scenarios()


if __name__ == "__main__":
    asyncio.run(main())
