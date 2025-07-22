#!/usr/bin/env python3
"""
Setup test database for running tests against Docker PostgreSQL.

This script creates a separate test database and ensures proper cleanup.
"""

import asyncio
import os
import sys
from pathlib import Path

# Add the app directory to Python path
app_dir = Path(__file__).parent.parent / "app"
sys.path.insert(0, str(app_dir.parent))

from sqlalchemy import text
from sqlalchemy.ext.asyncio import create_async_engine

from app.models.database.base import Base


async def setup_test_database():
    """Create test database and tables."""
    # Connect to postgres database to create test database
    admin_db_url = (
        "postgresql+asyncpg://trading_user:trading_password@localhost:5432/postgres"
    )
    test_db_url = "postgresql+asyncpg://trading_user:trading_password@localhost:5432/trading_db_test"

    try:
        # Create test database if it doesn't exist
        admin_engine = create_async_engine(admin_db_url)

        async with admin_engine.begin() as conn:
            # Check if test database exists
            result = await conn.execute(
                text("SELECT 1 FROM pg_database WHERE datname = 'trading_db_test'")
            )

            if not result.fetchone():
                # Create test database
                await conn.execute(text("COMMIT"))  # End current transaction
                await conn.execute(text("CREATE DATABASE trading_db_test"))
                print("✅ Created test database: trading_db_test")
            else:
                print("✅ Test database already exists: trading_db_test")

        await admin_engine.dispose()

        # Connect to test database and create tables
        test_engine = create_async_engine(test_db_url)

        async with test_engine.begin() as conn:
            await conn.run_sync(Base.metadata.create_all)
            print("✅ Created all tables in test database")

        await test_engine.dispose()

        # Update environment for tests
        os.environ["TEST_DATABASE_URL"] = test_db_url
        print(f"✅ Test database ready: {test_db_url}")

    except Exception as e:
        print(f"❌ Error setting up test database: {e}")
        sys.exit(1)


async def cleanup_test_database():
    """Clean up test database."""
    admin_db_url = (
        "postgresql+asyncpg://trading_user:trading_password@localhost:5432/postgres"
    )

    try:
        admin_engine = create_async_engine(admin_db_url)

        async with admin_engine.begin() as conn:
            # Disconnect all connections to test database
            await conn.execute(text("COMMIT"))
            await conn.execute(
                text("""
                SELECT pg_terminate_backend(pid)
                FROM pg_stat_activity
                WHERE datname = 'trading_db_test' AND pid <> pg_backend_pid()
            """)
            )

            # Drop test database
            await conn.execute(text("DROP DATABASE IF EXISTS trading_db_test"))
            print("✅ Cleaned up test database")

        await admin_engine.dispose()

    except Exception as e:
        print(f"⚠️  Warning: Could not clean up test database: {e}")


if __name__ == "__main__":
    if len(sys.argv) > 1 and sys.argv[1] == "cleanup":
        asyncio.run(cleanup_test_database())
    else:
        asyncio.run(setup_test_database())
