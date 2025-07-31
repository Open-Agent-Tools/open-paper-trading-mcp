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
- Options Positions: 6 diverse options (calls, puts, spreads)
  * AAPL 180 calls (2 contracts)
  * MSFT 300 puts (1 contract)
  * TSLA iron condor (4-leg spread)
  * SPY covered call (protective position)
- Historical Orders: 15+ orders across stocks and options
- Multi-leg Strategies: 3 complex options strategies
- Transaction History: 25+ transaction records
- Portfolio Greeks: Daily snapshots with risk metrics
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

        # Options holdings configuration
        self.options_holdings = [
            {
                "symbol": "AAPL250221C00180000",  # AAPL Feb 21 2025 180 Call
                "underlying": "AAPL",
                "strike": 180.00,
                "expiration": "2025-02-21",
                "option_type": "call",
                "quantity": 2,  # 2 contracts = 200 shares
                "avg_cost": 5.50,  # $5.50 per share, $1100 total
            },
            {
                "symbol": "MSFT250117P00300000",  # MSFT Jan 17 2025 300 Put
                "underlying": "MSFT",
                "strike": 300.00,
                "expiration": "2025-01-17",
                "option_type": "put",
                "quantity": 1,  # 1 contract = 100 shares
                "avg_cost": 12.75,  # $12.75 per share, $1275 total
            },
            {
                "symbol": "SPY250321C00420000",  # SPY Mar 21 2025 420 Call (covered call)
                "underlying": "SPY",
                "strike": 420.00,
                "expiration": "2025-03-21",
                "option_type": "call",
                "quantity": -1,  # Short 1 contract (covered call)
                "avg_cost": -8.25,  # Received $8.25 per share, $825 total credit
            },
            {
                "symbol": "GOOGL250214C00130000",  # GOOGL Feb 14 2025 130 Call
                "underlying": "GOOGL",
                "strike": 130.00,
                "expiration": "2025-02-14",
                "option_type": "call",
                "quantity": 3,  # 3 contracts = 300 shares
                "avg_cost": 4.20,  # $4.20 per share, $1260 total
            },
        ]

        # Multi-leg strategies configuration
        self.multi_leg_strategies = [
            {
                "strategy_type": "iron_condor",
                "strategy_name": "TSLA Iron Condor Feb 2025",
                "underlying": "TSLA",
                "legs": [
                    {"symbol": "TSLA250221P00180000", "strike": 180, "option_type": "put", "quantity": -1, "price": 3.50},
                    {"symbol": "TSLA250221P00190000", "strike": 190, "option_type": "put", "quantity": 1, "price": 5.25},
                    {"symbol": "TSLA250221C00220000", "strike": 220, "option_type": "call", "quantity": 1, "price": 6.75},
                    {"symbol": "TSLA250221C00230000", "strike": 230, "option_type": "call", "quantity": -1, "price": 4.50},
                ],
                "net_credit": 1.50,  # $150 credit received
                "date": "2024-12-20",
            },
            {
                "strategy_type": "call_spread",
                "strategy_name": "MSFT Bull Call Spread",
                "underlying": "MSFT",
                "legs": [
                    {"symbol": "MSFT250117C00290000", "strike": 290, "option_type": "call", "quantity": 2, "price": 8.50},
                    {"symbol": "MSFT250117C00310000", "strike": 310, "option_type": "call", "quantity": -2, "price": 3.25},
                ],
                "net_debit": 5.25,  # $1050 debit paid
                "date": "2024-12-10",
            },
        ]

        # Historical orders configuration (expanded)
        self.historical_orders = [
            # Stock orders (original XOM orders plus current holdings)
            {"symbol": "XOM", "action": "BUY", "quantity": 100, "price": 58.50, "date": "2024-12-01"},
            {"symbol": "XOM", "action": "SELL", "quantity": 50, "price": 61.25, "date": "2024-12-15"},
            {"symbol": "XOM", "action": "BUY", "quantity": 75, "price": 59.75, "date": "2025-01-05"},
            {"symbol": "XOM", "action": "SELL", "quantity": 25, "price": 62.00, "date": "2025-01-20"},
            {"symbol": "XOM", "action": "BUY", "quantity": 200, "price": 57.80, "date": "2025-02-10"},
            # Current stock holdings orders
            {"symbol": "AAPL", "action": "BUY", "quantity": 50, "price": 150.00, "date": "2024-11-15"},
            {"symbol": "MSFT", "action": "BUY", "quantity": 25, "price": 280.00, "date": "2024-11-20"},
            {"symbol": "GOOGL", "action": "BUY", "quantity": 15, "price": 120.00, "date": "2024-11-25"},
            {"symbol": "TSLA", "action": "BUY", "quantity": 30, "price": 200.00, "date": "2024-12-01"},
            {"symbol": "SPY", "action": "BUY", "quantity": 100, "price": 400.00, "date": "2024-12-05"},
            # Options orders
            {"symbol": "AAPL250221C00180000", "action": "BUY", "quantity": 2, "price": 5.50, "date": "2024-12-10"},
            {"symbol": "MSFT250117P00300000", "action": "BUY", "quantity": 1, "price": 12.75, "date": "2024-12-12"},
            {"symbol": "SPY250321C00420000", "action": "SELL", "quantity": 1, "price": 8.25, "date": "2024-12-15"},
            {"symbol": "GOOGL250214C00130000", "action": "BUY", "quantity": 3, "price": 4.20, "date": "2024-12-18"},
        ]

    async def load_profile(self) -> dict:
        """Load complete UITESTER01 profile with all test data."""
        print("🚀 Loading UITESTER01 test profile...")

        results = {
            "account_created": False,
            "user_created": False,
            "stock_positions_created": 0,
            "options_positions_created": 0,
            "orders_created": 0,
            "multi_leg_orders_created": 0,
            "transactions_created": 0,
            "portfolio_snapshots_created": 0,
            "market_data_created": 0,
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
                stock_positions_count = await self._create_stock_positions(db)
                results["stock_positions_created"] = stock_positions_count

                # Create options positions
                options_positions_count = await self._create_options_positions(db)
                results["options_positions_created"] = options_positions_count

                # Create historical orders
                orders_count = await self._create_historical_orders(db)
                results["orders_created"] = orders_count

                # Create multi-leg strategies
                multi_leg_count = await self._create_multi_leg_strategies(db)
                results["multi_leg_orders_created"] = multi_leg_count

                # Create supporting transactions
                transactions_count = await self._create_transactions(db)
                results["transactions_created"] = transactions_count

                # Create portfolio Greeks snapshots
                snapshots_count = await self._create_portfolio_snapshots(db)
                results["portfolio_snapshots_created"] = snapshots_count

                # Create market data snapshots
                market_data_count = await self._create_market_data(db)
                results["market_data_created"] = market_data_count

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
        # First handle tables with direct account_id relationships
        direct_account_tables = [
            "portfolio_greeks_snapshots",
            "recognized_strategies",
            "multi_leg_orders",
            "transactions",
            "orders",
            "positions",
        ]
        
        for table in direct_account_tables:
            await db.execute(
                text(f"DELETE FROM {table} WHERE account_id = :account_id"),
                {"account_id": self.account_id},
            )
        
        # Handle tables with indirect relationships or different column names
        # Delete order_legs via multi_leg_order_id (handled by cascade)
        # Delete strategy_performance via strategy_id (handled by cascade)
        
        # Clean up test data tables with scenario filter
        test_data_tables = [
            "test_stock_quotes",
            "test_option_quotes",
        ]
        
        for table in test_data_tables:
            await db.execute(
                text(f"DELETE FROM {table} WHERE scenario = :scenario"),
                {"scenario": "ui_testing"},
            )
        
        # Finally delete the account
        await db.execute(
            text("DELETE FROM accounts WHERE id = :account_id"),
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

    async def _create_options_positions(self, db) -> int:
        """Create options positions for various underlyings."""
        print("📊 Creating options positions...")

        positions_created = 0

        for holding in self.options_holdings:
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
                    "avg_price": abs(holding["avg_cost"]),  # Store absolute value
                },
            )

            positions_created += 1
            option_desc = f"{holding['underlying']} {holding['expiration']} {holding['strike']} {holding['option_type'].upper()}"
            action = "SHORT" if holding["quantity"] < 0 else "LONG"
            print(
                f"  ✅ {action} {abs(holding['quantity'])} {option_desc} @ ${abs(holding['avg_cost']):.2f}"
            )

        return positions_created

    async def _create_historical_orders(self, db) -> int:
        """Create comprehensive historical orders for stocks and options."""
        print("📋 Creating historical orders...")

        orders_created = 0

        for order_data in self.historical_orders:
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
                    "symbol": order_data["symbol"],
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
                f"  ✅ {order_data['action']} {order_data['quantity']} {order_data['symbol']} @ ${order_data['price']:.2f} on {order_data['date']}"
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

        # Create transactions for all historical orders
        for order_data in self.historical_orders:
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
                    "symbol": order_data["symbol"],
                    "quantity": order_data["quantity"],
                    "price": order_data["price"],
                    "transaction_type": transaction_type,
                    "timestamp": transaction_date,
                },
            )

            transactions_created += 1

        # Create transactions for multi-leg strategies
        for strategy in self.multi_leg_strategies:
            for leg in strategy["legs"]:
                transaction_id = str(uuid.uuid4())
                transaction_date = datetime.strptime(
                    strategy["date"], "%Y-%m-%d"
                ).replace(hour=10, minute=15)

                transaction_type = "BUY" if leg["quantity"] > 0 else "SELL"

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
                        "symbol": leg["symbol"],
                        "quantity": abs(leg["quantity"]),
                        "price": leg["price"],
                        "transaction_type": transaction_type,
                        "timestamp": transaction_date,
                    },
                )

                transactions_created += 1

        return transactions_created

    async def _create_multi_leg_strategies(self, db) -> int:
        """Create multi-leg options strategies."""
        print("🔗 Creating multi-leg options strategies...")

        strategies_created = 0

        for strategy in self.multi_leg_strategies:
            # Create multi-leg order
            mlo_id = f"mlo_{uuid.uuid4().hex[:8]}"
            strategy_date = datetime.strptime(strategy["date"], "%Y-%m-%d").replace(
                hour=10, minute=0
            )
            filled_date = strategy_date + timedelta(minutes=15)

            net_price = strategy.get("net_credit", 0) - strategy.get("net_debit", 0)

            await db.execute(
                text("""
                INSERT INTO multi_leg_orders (
                    id, account_id, order_type, net_price, status, strategy_type,
                    underlying_symbol, created_at, filled_at
                ) VALUES (
                    :id, :account_id, :order_type, :net_price, :status, :strategy_type,
                    :underlying_symbol, :created_at, :filled_at
                )
            """),
                {
                    "id": mlo_id,
                    "account_id": self.account_id,
                    "order_type": "limit",
                    "net_price": net_price,
                    "status": "FILLED",
                    "strategy_type": strategy["strategy_type"],
                    "underlying_symbol": strategy["underlying"],
                    "created_at": strategy_date,
                    "filled_at": filled_date,
                },
            )

            # Create order legs
            for leg in strategy["legs"]:
                leg_id = str(uuid.uuid4())
                
                await db.execute(
                    text("""
                    INSERT INTO order_legs (
                        id, multi_leg_order_id, symbol, asset_type, quantity,
                        order_type, price, strike, expiration_date, option_type,
                        underlying_symbol, filled_quantity, filled_price
                    ) VALUES (
                        :id, :multi_leg_order_id, :symbol, :asset_type, :quantity,
                        :order_type, :price, :strike, :expiration_date, :option_type,
                        :underlying_symbol, :filled_quantity, :filled_price
                    )
                """),
                    {
                        "id": leg_id,
                        "multi_leg_order_id": mlo_id,
                        "symbol": leg["symbol"],
                        "asset_type": "option",
                        "quantity": leg["quantity"],
                        "order_type": "BUY" if leg["quantity"] > 0 else "SELL",
                        "price": leg["price"],
                        "strike": leg["strike"],
                        "expiration_date": datetime.strptime(f"20{leg['symbol'][4:10]}", "%Y%m%d").date(),
                        "option_type": leg["option_type"],
                        "underlying_symbol": strategy["underlying"],
                        "filled_quantity": abs(leg["quantity"]),
                        "filled_price": leg["price"],
                    },
                )

            # Create recognized strategy record
            strategy_id = str(uuid.uuid4())
            await db.execute(
                text("""
                INSERT INTO recognized_strategies (
                    id, account_id, strategy_type, strategy_name, underlying_symbol,
                    cost_basis, position_ids, is_active, detected_at
                ) VALUES (
                    :id, :account_id, :strategy_type, :strategy_name, :underlying_symbol,
                    :cost_basis, :position_ids, :is_active, :detected_at
                )
            """),
                {
                    "id": strategy_id,
                    "account_id": self.account_id,
                    "strategy_type": strategy["strategy_type"],
                    "strategy_name": strategy["strategy_name"],
                    "underlying_symbol": strategy["underlying"],
                    "cost_basis": abs(net_price) * 100,  # Convert to dollar amount
                    "position_ids": f'["{mlo_id}"]',  # JSON array as string
                    "is_active": True,
                    "detected_at": strategy_date,
                },
            )

            strategies_created += 1
            print(
                f"  ✅ {strategy['strategy_name']} - Net: ${net_price:.2f} on {strategy['date']}"
            )

        return strategies_created

    async def _create_portfolio_snapshots(self, db) -> int:
        """Create portfolio Greeks snapshots for risk analysis."""
        print("📸 Creating portfolio Greeks snapshots...")

        snapshots_created = 0

        # Create snapshots for the last 30 days
        for days_back in range(0, 30, 7):  # Weekly snapshots
            snapshot_date = (datetime.now() - timedelta(days=days_back)).date()
            snapshot_time = datetime.combine(snapshot_date, datetime.min.time()).replace(hour=16, minute=0)

            snapshot_id = str(uuid.uuid4())

            # Calculate sample Greeks (in real implementation, these would be calculated from positions)
            base_delta = 125.50 + (days_back * 2.3)  # Slight variation over time
            base_gamma = 8.75 - (days_back * 0.2)
            base_theta = -45.20 - (days_back * 1.1)
            base_vega = 89.30 + (days_back * 0.8)

            portfolio_value = 65000 + (days_back * 100)  # Slight variation

            await db.execute(
                text("""
                INSERT INTO portfolio_greeks_snapshots (
                    id, account_id, snapshot_date, snapshot_time,
                    total_delta, total_gamma, total_theta, total_vega, total_rho,
                    delta_normalized, gamma_normalized, theta_normalized, vega_normalized,
                    delta_dollars, gamma_dollars, theta_dollars,
                    total_portfolio_value, options_value, stocks_value
                ) VALUES (
                    :id, :account_id, :snapshot_date, :snapshot_time,
                    :total_delta, :total_gamma, :total_theta, :total_vega, :total_rho,
                    :delta_normalized, :gamma_normalized, :theta_normalized, :vega_normalized,
                    :delta_dollars, :gamma_dollars, :theta_dollars,
                    :total_portfolio_value, :options_value, :stocks_value
                )
            """),
                {
                    "id": snapshot_id,
                    "account_id": self.account_id,
                    "snapshot_date": snapshot_date,
                    "snapshot_time": snapshot_time,
                    "total_delta": base_delta,
                    "total_gamma": base_gamma,
                    "total_theta": base_theta,
                    "total_vega": base_vega,
                    "total_rho": 12.45,  # Static for simplicity
                    "delta_normalized": base_delta / (portfolio_value / 1000),
                    "gamma_normalized": base_gamma / (portfolio_value / 1000),
                    "theta_normalized": base_theta / (portfolio_value / 1000),
                    "vega_normalized": base_vega / (portfolio_value / 1000),
                    "delta_dollars": base_delta * 100,
                    "gamma_dollars": base_gamma * 100,
                    "theta_dollars": base_theta * 100,
                    "total_portfolio_value": portfolio_value,
                    "options_value": portfolio_value * 0.15,  # ~15% options
                    "stocks_value": portfolio_value * 0.85,   # ~85% stocks
                },
            )

            snapshots_created += 1
            print(
                f"  ✅ Portfolio snapshot for {snapshot_date} - Value: ${portfolio_value:,.2f}, Delta: {base_delta:.1f}"
            )

        return snapshots_created

    async def _create_market_data(self, db) -> int:
        """Create realistic market data for testing."""
        print("💹 Creating market data snapshots...")

        market_data_created = 0

        # Create stock quotes
        stock_prices = {
            "AAPL": 175.50,
            "MSFT": 295.75,
            "GOOGL": 125.30,
            "TSLA": 205.80,
            "SPY": 415.25,
            "XOM": 60.45,
        }

        for symbol, base_price in stock_prices.items():
            for days_back in range(0, 10):  # Last 10 days
                quote_date = (datetime.now() - timedelta(days=days_back)).date()
                
                # Add some realistic price variation
                price_variation = base_price * (0.98 + (days_back * 0.004))  # Slight trend
                bid = price_variation - 0.02
                ask = price_variation + 0.02

                quote_id = str(uuid.uuid4())

                await db.execute(
                    text("""
                    INSERT INTO test_stock_quotes (
                        id, symbol, quote_date, bid, ask, price, volume, scenario
                    ) VALUES (
                        :id, :symbol, :quote_date, :bid, :ask, :price, :volume, :scenario
                    )
                """),
                    {
                        "id": quote_id,
                        "symbol": symbol,
                        "quote_date": quote_date,
                        "bid": round(bid, 2),
                        "ask": round(ask, 2),
                        "price": round(price_variation, 2),
                        "volume": 1000000 + (days_back * 50000),
                        "scenario": "ui_testing",
                    },
                )

                market_data_created += 1

        # Create options quotes for key options
        options_data = [
            {"symbol": "AAPL250221C00180000", "underlying": "AAPL", "price": 6.25},
            {"symbol": "MSFT250117P00300000", "underlying": "MSFT", "price": 14.50},
            {"symbol": "SPY250321C00420000", "underlying": "SPY", "price": 7.75},
            {"symbol": "GOOGL250214C00130000", "underlying": "GOOGL", "price": 4.80},
        ]

        for option in options_data:
            for days_back in range(0, 5):  # Last 5 days for options
                quote_date = (datetime.now() - timedelta(days=days_back)).date()
                
                base_price = option["price"]
                price_variation = base_price * (0.95 + (days_back * 0.02))
                bid = price_variation - 0.10
                ask = price_variation + 0.10

                quote_id = str(uuid.uuid4())

                # Parse option details from symbol 
                # Format: AAPL250221C00180000 -> AAPL 25/02/21 C 00180000
                symbol = option["symbol"]
                expiry_str = symbol[4:10]  # 250221
                expiry_date = datetime.strptime(f"20{expiry_str}", "%Y%m%d").date()
                strike = float(symbol[11:19]) / 1000  # 00180000 -> 180.000
                option_type = "call" if symbol[10] == "C" else "put"

                await db.execute(
                    text("""
                    INSERT INTO test_option_quotes (
                        id, symbol, underlying, expiration, strike, option_type,
                        quote_date, bid, ask, price, volume, scenario
                    ) VALUES (
                        :id, :symbol, :underlying, :expiration, :strike, :option_type,
                        :quote_date, :bid, :ask, :price, :volume, :scenario
                    )
                """),
                    {
                        "id": quote_id,
                        "symbol": option["symbol"],
                        "underlying": option["underlying"],
                        "expiration": expiry_date,
                        "strike": strike,
                        "option_type": option_type,
                        "quote_date": quote_date,
                        "bid": round(bid, 2),
                        "ask": round(ask, 2),
                        "price": round(price_variation, 2),
                        "volume": 500 + (days_back * 25),
                        "scenario": "ui_testing",
                    },
                )

                market_data_created += 1

        print(f"  ✅ Created {market_data_created} market data records")
        return market_data_created

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

        if results["account_created"] and (results["stock_positions_created"] > 0 or results["options_positions_created"] > 0):
            print("\n🎉 Profile loading complete!")
            print(f"   Account: {loader.account_id}")
            print(f"   Owner: {loader.owner_name}")
            print(f"   Stock Positions: {results['stock_positions_created']}")
            print(f"   Options Positions: {results['options_positions_created']}")
            print(f"   Orders: {results['orders_created']}")
            print(f"   Multi-leg Orders: {results['multi_leg_orders_created']}")
            print(f"   Transactions: {results['transactions_created']}")
            print(f"   Portfolio Snapshots: {results['portfolio_snapshots_created']}")
            print(f"   Market Data Records: {results['market_data_created']}")
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
