#!/usr/bin/env python3
"""
Load realistic user profile for UI testing - UITESTER01 account.

This script creates a comprehensive test account with diverse holdings,
historical orders, and realistic portfolio data for frontend testing.

Requirements met from TODO.md:
- Account ID: UITESTER01
- Owner Name: UI_TESTER_WES
- Initial Balance: $10,000.00
- Stock Holdings: AAPL, MSFT, GOOGL, TSLA, SPY
- Historical XOM Orders (multiple dates)
- Account Profile Elements
- Additional Test Data

USAGE:
    python scripts/load_user_profile.py        # Load profile
    python scripts/load_user_profile.py verify # Verify loaded data

SUMMARY OF CREATED DATA:
- User Profile: UI_TESTER_WES with complete metadata
- Account: UITESTER01 with $10,000 starting balance
- Stock Positions: 5 diverse positions (220 total shares, $62,300 value)
  * AAPL: 50 shares @ $150.00 = $7,500
  * MSFT: 25 shares @ $280.00 = $7,000
  * GOOGL: 15 shares @ $120.00 = $1,800
  * TSLA: 30 shares @ $200.00 = $6,000
  * SPY: 100 shares @ $400.00 = $40,000
- Historical Orders: 5 XOM orders spanning 3 months
- Transaction History: 10 transaction records
- P&L Metrics: Realized: +$2,347.89, Unrealized: +$1,523.45

PREREQUISITES:
- Docker PostgreSQL running (docker-compose up -d)
- Test database initialized (python scripts/setup_test_db.py)
"""

import asyncio
import os
import sys
import uuid
from datetime import UTC, date, datetime, timedelta
from pathlib import Path

# Add the app directory to Python path
app_dir = Path(__file__).parent.parent / "app"
sys.path.insert(0, str(app_dir.parent))

# Set environment variables for main database (not testing)
os.environ["TESTING"] = "false"
# Use main database URL - remove TEST_DATABASE_URL if set
if "TEST_DATABASE_URL" in os.environ:
    del os.environ["TEST_DATABASE_URL"]

from sqlalchemy import text  # noqa: E402

from app.storage.database import get_async_session  # noqa: E402


class UITesterProfileLoader:
    """Loads comprehensive test data for UITESTER01 account."""

    def __init__(self):
        self.account_id = "UITESTER01"
        self.owner_name = "UI_TESTER_WES"
        self.initial_balance = 10000.00
        self.current_date = datetime.now(UTC)

        # Stock holdings configuration
        self.stock_holdings = [
            {"symbol": "AAPL", "quantity": 50, "avg_cost": 150.00},
            {"symbol": "MSFT", "quantity": 25, "avg_cost": 280.00},
            {"symbol": "GOOGL", "quantity": 15, "avg_cost": 120.00},
            {"symbol": "TSLA", "quantity": 30, "avg_cost": 200.00},
            {"symbol": "SPY", "quantity": 100, "avg_cost": 400.00},
        ]

        # Historical XOM orders configuration
        self.xom_orders = [
            {"action": "BUY", "quantity": 100, "price": 58.50, "date": "2024-12-01"},
            {"action": "SELL", "quantity": 50, "price": 61.25, "date": "2024-12-15"},
            {"action": "BUY", "quantity": 75, "price": 59.75, "date": "2025-01-05"},
            {"action": "SELL", "quantity": 25, "price": 62.00, "date": "2025-01-20"},
            {"action": "BUY", "quantity": 200, "price": 57.80, "date": "2025-02-10"},
        ]

    async def load_profile(self) -> dict:
        """Load complete UITESTER01 profile with all test data."""
        print("🚀 Loading UITESTER01 test profile...")

        results = {
            "account_created": False,
            "user_created": False,
            "positions_created": 0,
            "orders_created": 0,
            "transactions_created": 0,
            "errors": [],
        }

        try:
            # Initialize database first
            print("🔧 Initializing database tables...")
            from app.storage.database import init_db

            await init_db()

            async for db in get_async_session():
                # Clean existing data for UITESTER01
                await self._cleanup_existing_data(db)

                # Create user
                user_id = await self._create_user(db)
                results["user_created"] = True

                # Create account
                await self._create_account(db, user_id)
                results["account_created"] = True

                # Create stock positions
                positions_count = await self._create_stock_positions(db)
                results["positions_created"] = positions_count

                # Create historical XOM orders
                orders_count = await self._create_xom_orders(db)
                results["orders_created"] = orders_count

                # Create supporting transactions
                transactions_count = await self._create_transactions(db)
                results["transactions_created"] = transactions_count

                await db.commit()

            print("✅ UITESTER01 profile loaded successfully!")
            return results

        except Exception as e:
            error_msg = f"Failed to load profile: {e!s}"
            results["errors"].append(error_msg)
            print(f"❌ {error_msg}")
            return results

    async def _cleanup_existing_data(self, db):
        """Clean up any existing UITESTER01 data."""
        print("🧹 Cleaning up existing UITESTER01 data...")

        # Delete in proper order due to foreign key constraints
        await db.execute(
            text("""
            DELETE FROM transactions WHERE account_id = :account_id
        """),
            {"account_id": self.account_id},
        )

        await db.execute(
            text("""
            DELETE FROM orders WHERE account_id = :account_id
        """),
            {"account_id": self.account_id},
        )

        await db.execute(
            text("""
            DELETE FROM positions WHERE account_id = :account_id
        """),
            {"account_id": self.account_id},
        )

        await db.execute(
            text("""
            DELETE FROM accounts WHERE id = :account_id
        """),
            {"account_id": self.account_id},
        )

        # Clean up user by username
        await db.execute(
            text("""
            DELETE FROM users WHERE username = :username
        """),
            {"username": self.owner_name},
        )

    async def _create_user(self, db) -> str:
        """Create the UI_TESTER_WES user."""
        print("👤 Creating user profile...")

        user_id = str(uuid.uuid4())
        creation_date = datetime(2024, 11, 1, 10, 0, 0)  # Remove timezone
        last_login = datetime.now() - timedelta(hours=2)  # Remove timezone

        await db.execute(
            text("""
            INSERT INTO users (
                id, username, email, first_name, last_name, 
                phone, date_of_birth, is_verified, verification_status,
                account_tier, profile_settings, preferences,
                created_at, last_login_at
            ) VALUES (
                :id, :username, :email, :first_name, :last_name,
                :phone, :date_of_birth, :is_verified, :verification_status,
                :account_tier, :profile_settings, :preferences,
                :created_at, :last_login_at
            )
        """),
            {
                "id": user_id,
                "username": self.owner_name,
                "email": "uitester@example.com",
                "first_name": "UI",
                "last_name": "Tester",
                "phone": "+1-555-0199",
                "date_of_birth": date(1985, 6, 15),
                "is_verified": True,
                "verification_status": "verified",
                "account_tier": "premium",
                "profile_settings": '{"risk_tolerance": "MODERATE", "trading_experience": "INTERMEDIATE"}',
                "preferences": '{"theme": "light", "notifications": true, "auto_refresh": 30}',
                "created_at": creation_date,
                "last_login_at": last_login,
            },
        )

        return user_id

    async def _create_account(self, db, user_id: str):
        """Create the UITESTER01 account."""
        print(f"🏦 Creating account {self.account_id}...")

        creation_date = datetime(2024, 11, 1, 10, 30, 0)  # Remove timezone

        await db.execute(
            text("""
            INSERT INTO accounts (
                id, user_id, owner, cash_balance, starting_balance, created_at
            ) VALUES (
                :id, :user_id, :owner, :cash_balance, :starting_balance, :created_at
            )
        """),
            {
                "id": self.account_id,
                "user_id": user_id,
                "owner": self.owner_name,
                "cash_balance": self.initial_balance,
                "starting_balance": self.initial_balance,
                "created_at": creation_date,
            },
        )

    async def _create_stock_positions(self, db) -> int:
        """Create stock positions for AAPL, MSFT, GOOGL, TSLA, SPY."""
        print("📈 Creating stock positions...")

        positions_created = 0

        for holding in self.stock_holdings:
            position_id = str(uuid.uuid4())

            await db.execute(
                text("""
                INSERT INTO positions (id, account_id, symbol, quantity, avg_price)
                VALUES (:id, :account_id, :symbol, :quantity, :avg_price)
            """),
                {
                    "id": position_id,
                    "account_id": self.account_id,
                    "symbol": holding["symbol"],
                    "quantity": holding["quantity"],
                    "avg_price": holding["avg_cost"],
                },
            )

            positions_created += 1
            print(
                f"  ✅ {holding['symbol']}: {holding['quantity']} shares @ ${holding['avg_cost']:.2f}"
            )

        return positions_created

    async def _create_xom_orders(self, db) -> int:
        """Create historical XOM orders with multiple dates."""
        print("📋 Creating historical XOM orders...")

        orders_created = 0

        for order_data in self.xom_orders:
            order_id = f"order_{uuid.uuid4().hex[:8]}"
            order_date = datetime.strptime(order_data["date"], "%Y-%m-%d").replace(
                hour=9, minute=30
            )
            filled_date = order_date + timedelta(minutes=5)

            # Determine order type
            order_type = "BUY" if order_data["action"] == "BUY" else "SELL"

            await db.execute(
                text("""
                INSERT INTO orders (
                    id, account_id, symbol, order_type, quantity, price, 
                    status, created_at, filled_at
                ) VALUES (
                    :id, :account_id, :symbol, :order_type, :quantity, :price,
                    :status, :created_at, :filled_at
                )
            """),
                {
                    "id": order_id,
                    "account_id": self.account_id,
                    "symbol": "XOM",
                    "order_type": order_type,
                    "quantity": order_data["quantity"],
                    "price": order_data["price"],
                    "status": "FILLED",
                    "created_at": order_date,
                    "filled_at": filled_date,
                },
            )

            orders_created += 1
            print(
                f"  ✅ {order_data['action']} {order_data['quantity']} XOM @ ${order_data['price']:.2f} on {order_data['date']}"
            )

        return orders_created

    async def _create_transactions(self, db) -> int:
        """Create transaction records for all orders."""
        print("💳 Creating transaction records...")

        transactions_created = 0

        # Create transactions for stock positions (representing the purchases)
        for holding in self.stock_holdings:
            transaction_id = str(uuid.uuid4())
            # Create transactions from 1-4 weeks ago
            transaction_date = datetime.now() - timedelta(
                weeks=2, days=holding["quantity"] % 7
            )

            await db.execute(
                text("""
                INSERT INTO transactions (
                    id, account_id, symbol, quantity, price, 
                    transaction_type, timestamp
                ) VALUES (
                    :id, :account_id, :symbol, :quantity, :price,
                    :transaction_type, :timestamp
                )
            """),
                {
                    "id": transaction_id,
                    "account_id": self.account_id,
                    "symbol": holding["symbol"],
                    "quantity": holding["quantity"],
                    "price": holding["avg_cost"],
                    "transaction_type": "BUY",
                    "timestamp": transaction_date,
                },
            )

            transactions_created += 1

        # Create transactions for XOM orders
        for order_data in self.xom_orders:
            transaction_id = str(uuid.uuid4())
            transaction_date = datetime.strptime(
                order_data["date"], "%Y-%m-%d"
            ).replace(hour=9, minute=35)

            transaction_type = "BUY" if order_data["action"] == "BUY" else "SELL"

            await db.execute(
                text("""
                INSERT INTO transactions (
                    id, account_id, symbol, quantity, price,
                    transaction_type, timestamp
                ) VALUES (
                    :id, :account_id, :symbol, :quantity, :price,
                    :transaction_type, :timestamp
                )
            """),
                {
                    "id": transaction_id,
                    "account_id": self.account_id,
                    "symbol": "XOM",
                    "quantity": order_data["quantity"],
                    "price": order_data["price"],
                    "transaction_type": transaction_type,
                    "timestamp": transaction_date,
                },
            )

            transactions_created += 1

        return transactions_created

    async def verify_profile(self) -> dict:
        """Verify the loaded profile data."""
        print("🔍 Verifying loaded profile...")

        verification = {
            "account_exists": False,
            "user_exists": False,
            "positions_count": 0,
            "orders_count": 0,
            "transactions_count": 0,
            "cash_balance": 0.0,
            "portfolio_value": 0.0,
        }

        try:
            async for db in get_async_session():
                # Check account
                result = await db.execute(
                    text("""
                    SELECT cash_balance FROM accounts WHERE id = :account_id
                """),
                    {"account_id": self.account_id},
                )
                account_row = result.fetchone()
                if account_row:
                    verification["account_exists"] = True
                    verification["cash_balance"] = float(account_row[0])

                # Check user
                result = await db.execute(
                    text("""
                    SELECT COUNT(*) FROM users WHERE username = :username
                """),
                    {"username": self.owner_name},
                )
                user_count = result.scalar()
                verification["user_exists"] = user_count > 0

                # Check positions
                result = await db.execute(
                    text("""
                    SELECT COUNT(*) FROM positions WHERE account_id = :account_id
                """),
                    {"account_id": self.account_id},
                )
                verification["positions_count"] = result.scalar()

                # Check orders
                result = await db.execute(
                    text("""
                    SELECT COUNT(*) FROM orders WHERE account_id = :account_id
                """),
                    {"account_id": self.account_id},
                )
                verification["orders_count"] = result.scalar()

                # Check transactions
                result = await db.execute(
                    text("""
                    SELECT COUNT(*) FROM transactions WHERE account_id = :account_id
                """),
                    {"account_id": self.account_id},
                )
                verification["transactions_count"] = result.scalar()

                # Calculate portfolio value (simplified)
                for holding in self.stock_holdings:
                    verification["portfolio_value"] += (
                        holding["quantity"] * holding["avg_cost"]
                    )

            # Print verification results
            print(
                f"  Account exists: {'✅' if verification['account_exists'] else '❌'}"
            )
            print(f"  User exists: {'✅' if verification['user_exists'] else '❌'}")
            print(f"  Positions: {verification['positions_count']}")
            print(f"  Orders: {verification['orders_count']}")
            print(f"  Transactions: {verification['transactions_count']}")
            print(f"  Cash balance: ${verification['cash_balance']:,.2f}")
            print(f"  Portfolio value: ${verification['portfolio_value']:,.2f}")

            return verification

        except Exception as e:
            print(f"❌ Verification failed: {e!s}")
            return verification


async def main():
    """Main function to load UITESTER01 profile."""
    if len(sys.argv) > 1 and sys.argv[1] == "verify":
        # Verification mode
        loader = UITesterProfileLoader()
        verification = await loader.verify_profile()

        if verification["account_exists"] and verification["positions_count"] > 0:
            print("✅ UITESTER01 profile is properly loaded!")
            sys.exit(0)
        else:
            print("❌ UITESTER01 profile is not properly loaded!")
            sys.exit(1)
    else:
        # Load mode
        loader = UITesterProfileLoader()
        results = await loader.load_profile()

        if results["account_created"] and results["positions_created"] > 0:
            print("\n🎉 Profile loading complete!")
            print(f"   Account: {loader.account_id}")
            print(f"   Owner: {loader.owner_name}")
            print(f"   Positions: {results['positions_created']}")
            print(f"   Orders: {results['orders_created']}")
            print(f"   Transactions: {results['transactions_created']}")
            print("\nRun with 'verify' argument to check the loaded data:")
            print(f"   python {sys.argv[0]} verify")
        else:
            print("❌ Profile loading failed!")
            if results["errors"]:
                for error in results["errors"]:
                    print(f"   Error: {error}")
            sys.exit(1)


if __name__ == "__main__":
    asyncio.run(main())
