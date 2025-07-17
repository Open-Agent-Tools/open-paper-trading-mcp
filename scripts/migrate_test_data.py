#!/usr/bin/env python3
"""
Data migration script to populate test data tables from existing CSV files.

This script reads the existing test data CSV files and populates the 
TestStockQuote and TestOptionQuote database tables for Phase 3.
"""

import asyncio
import gzip
import csv
import sys
from pathlib import Path
from datetime import datetime
from typing import Dict, List, Optional, Any

# Add the app directory to the path
sys.path.insert(0, str(Path(__file__).parent.parent))

from app.storage.database import get_async_session, init_db
from app.models.database.trading import TestStockQuote, TestOptionQuote
from app.models.assets import asset_factory, Stock, Option
from sqlalchemy import select, delete
from sqlalchemy.exc import IntegrityError


class TestDataMigrator:
    """Migrates test data from CSV files to database tables."""
    
    def __init__(self):
        self.data_file = Path(__file__).parent.parent / "app" / "adapters" / "test_data" / "data.csv.gz"
        self.batch_size = 1000
        
    async def migrate_data(self, scenario: str = "default") -> Dict[str, Any]:
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
                stock_quotes.append({
                    'symbol': asset.symbol,
                    'quote_date': datetime.strptime(quote_date, "%Y-%m-%d").date(),
                    'bid': float(bid),
                    'ask': float(ask),
                    'price': (float(bid) + float(ask)) / 2,
                    'volume': None,  # Not in test data
                    'scenario': scenario
                })
            elif isinstance(asset, Option):
                option_quotes.append({
                    'symbol': asset.symbol,
                    'underlying': asset.underlying.symbol,
                    'expiration': asset.expiration_date,
                    'strike': float(asset.strike),
                    'option_type': asset.option_type.lower(),
                    'quote_date': datetime.strptime(quote_date, "%Y-%m-%d").date(),
                    'bid': float(bid),
                    'ask': float(ask),
                    'price': (float(bid) + float(ask)) / 2,
                    'volume': None,  # Not in test data
                    'scenario': scenario
                })
        
        # Insert data in batches
        stock_count = await self._insert_stock_quotes(stock_quotes)
        option_count = await self._insert_option_quotes(option_quotes)
        
        stats = {
            'scenario': scenario,
            'stocks_migrated': stock_count,
            'options_migrated': option_count,
            'total_migrated': stock_count + option_count,
            'available_dates': self._get_available_dates(data)
        }
        
        print(f"Migration completed: {stats}")
        return stats
    
    def _load_csv_data(self) -> List[tuple]:
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
    
    def _get_available_dates(self, data: List[tuple]) -> List[str]:
        """Get list of available dates from the data."""
        dates = set()
        for symbol, quote_date, bid, ask in data:
            dates.add(quote_date)
        return sorted(list(dates))
    
    async def _clear_existing_data(self) -> None:
        """Clear existing test data from database."""
        print("Clearing existing test data...")
        
        async for db in get_async_session():
            # Clear test stock quotes
            await db.execute(delete(TestStockQuote))
            
            # Clear test option quotes
            await db.execute(delete(TestOptionQuote))
            
            await db.commit()
            break
    
    async def _insert_stock_quotes(self, stock_quotes: List[Dict[str, Any]]) -> int:
        """Insert stock quotes in batches."""
        if not stock_quotes:
            return 0
        
        print(f"Inserting {len(stock_quotes)} stock quotes...")
        
        async for db in get_async_session():
            count = 0
            
            for i in range(0, len(stock_quotes), self.batch_size):
                batch = stock_quotes[i:i + self.batch_size]
                
                # Create TestStockQuote objects
                db_quotes = []
                for quote_data in batch:
                    db_quote = TestStockQuote(**quote_data)
                    db_quotes.append(db_quote)
                
                # Insert batch
                db.add_all(db_quotes)
                
                try:
                    await db.commit()
                    count += len(batch)
                    print(f"Inserted batch of {len(batch)} stock quotes (total: {count})")
                except IntegrityError as e:
                    print(f"Error inserting stock quote batch: {e}")
                    await db.rollback()
            
            break
        
        return count
    
    async def _insert_option_quotes(self, option_quotes: List[Dict[str, Any]]) -> int:
        """Insert option quotes in batches."""
        if not option_quotes:
            return 0
        
        print(f"Inserting {len(option_quotes)} option quotes...")
        
        async for db in get_async_session():
            count = 0
            
            for i in range(0, len(option_quotes), self.batch_size):
                batch = option_quotes[i:i + self.batch_size]
                
                # Create TestOptionQuote objects
                db_quotes = []
                for quote_data in batch:
                    db_quote = TestOptionQuote(**quote_data)
                    db_quotes.append(db_quote)
                
                # Insert batch
                db.add_all(db_quotes)
                
                try:
                    await db.commit()
                    count += len(batch)
                    print(f"Inserted batch of {len(batch)} option quotes (total: {count})")
                except IntegrityError as e:
                    print(f"Error inserting option quote batch: {e}")
                    await db.rollback()
            
            break
        
        return count
    
    async def verify_migration(self, scenario: str = "default") -> Dict[str, Any]:
        """Verify the migration was successful."""
        print(f"Verifying migration for scenario: {scenario}")
        
        verification = {}
        
        async for db in get_async_session():
            try:
                # Count stock quotes
                stock_result = await db.execute(
                    select(TestStockQuote).where(TestStockQuote.scenario == scenario)
                )
                stock_count = len(stock_result.fetchall())
                
                # Count option quotes
                option_result = await db.execute(
                    select(TestOptionQuote).where(TestOptionQuote.scenario == scenario)
                )
                option_count = len(option_result.fetchall())
                
                verification = {
                    'scenario': scenario,
                    'stock_quotes_count': stock_count,
                    'option_quotes_count': option_count,
                    'stock_samples': [],
                    'option_samples': []
                }
                
                print(f"Verification results: {verification}")
                break  # Exit the async for loop
                
            except Exception as e:
                print(f"Error during verification: {e}")
                verification = {
                    'scenario': scenario,
                    'stock_quotes_count': 0,
                    'option_quotes_count': 0,
                    'stock_samples': [],
                    'option_samples': [],
                    'error': str(e)
                }
                break
            
        return verification


async def main():
    """Main migration entry point."""
    migrator = TestDataMigrator()
    
    try:
        # Run migration
        stats = await migrator.migrate_data("default")
        print(f"\nMigration completed successfully!")
        print(f"Stock quotes migrated: {stats['stocks_migrated']}")
        print(f"Option quotes migrated: {stats['options_migrated']}")
        print(f"Total quotes migrated: {stats['total_migrated']}")
        print(f"Available dates: {stats['available_dates']}")
        
        # Verify migration
        verification = await migrator.verify_migration("default")
        print(f"\nVerification completed!")
        print(f"Stock quotes in database: {verification['stock_quotes_count']}")
        print(f"Option quotes in database: {verification['option_quotes_count']}")
        
        if verification['stock_samples']:
            print("\nSample stock quotes:")
            for sample in verification['stock_samples']:
                print(f"  {sample['symbol']} on {sample['date']}: ${sample['price']}")
        
        if verification['option_samples']:
            print("\nSample option quotes:")
            for sample in verification['option_samples']:
                print(f"  {sample['symbol']} ({sample['underlying']} ${sample['strike']} {sample['type']}) on {sample['date']}: ${sample['price']}")
        
    except Exception as e:
        print(f"Migration failed: {e}")
        sys.exit(1)


if __name__ == "__main__":
    asyncio.run(main())