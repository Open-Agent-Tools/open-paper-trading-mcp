import asyncio
import os
from datetime import date, datetime, timedelta
from typing import Any
from uuid import uuid4

from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import InputValidationError, NotFoundError
from app.models.assets import Option, asset_factory
from app.models.database.trading import Account as DBAccount
from app.models.database.trading import Order as DBOrder
from app.models.database.trading import Position as DBPosition
from app.models.database.trading import User as DBUser
from app.models.quotes import OptionQuote, OptionsChain, Quote
from app.schemas.accounts import AccountSummaryList
from app.schemas.orders import (
    Order,
    OrderCondition,
    OrderCreate,
    OrderStatus,
    OrderType,
)
from app.schemas.positions import Portfolio, PortfolioSummary, Position
from app.schemas.trading import StockQuote
from app.schemas.users import UserCreate, UserProfile, UserProfileSummary, UserUpdate

# Import schema converters
from app.utils.schema_converters import (
    AccountConverter,
    OrderConverter,
    PositionConverter,
)

# Database imports removed - using async patterns only
from ..adapters.base import QuoteAdapter
from ..adapters.synthetic_data import DevDataQuoteAdapter
from .greeks import calculate_option_greeks

# Import new services
from .order_execution import OrderExecutionEngine
from .strategies import StrategyRecognitionService
from .validation import AccountValidator


class TradingService:
    def __init__(
        self,
        quote_adapter: QuoteAdapter | None = None,
        account_owner: str = "default",
        db_session: AsyncSession | None = None,
    ) -> None:
        # Validate account_owner input
        if account_owner is None:
            raise TypeError("account_owner cannot be None")
        if not isinstance(account_owner, str):
            raise TypeError("account_owner must be a string")
        if not account_owner.strip():
            raise InputValidationError(
                "account_owner cannot be empty or whitespace-only"
            )
        if len(account_owner) > 255:
            raise InputValidationError("account_owner must be 255 characters or less")

        # Validate db_session input
        if db_session is not None and not hasattr(db_session, "execute"):
            raise TypeError("db_session must be a valid AsyncSession instance or None")

        # Initialize services
        if quote_adapter is None:
            # Use adapter factory to create quote adapter based on configuration
            from app.adapters.config import get_adapter_factory
            from app.core.config import settings

            factory = get_adapter_factory()
            quote_adapter = factory.create_adapter(settings.QUOTE_ADAPTER_TYPE)

            if quote_adapter is None:
                # Fall back to database test data adapter
                quote_adapter = factory.create_adapter("synthetic_data_db")

                if quote_adapter is None:
                    # Final fallback to CSV test data adapter
                    quote_adapter = DevDataQuoteAdapter()

        self.quote_adapter = quote_adapter
        self.order_execution = OrderExecutionEngine()
        self.account_validation = AccountValidator()
        self.strategy_recognition = StrategyRecognitionService()

        # Initialize schema converters
        self.account_converter = AccountConverter(self)
        self.order_converter = OrderConverter()
        self.position_converter = PositionConverter(self)

        # Account configuration (store the trimmed value)
        self.account_owner = account_owner.strip()
        self._db_session = db_session  # Optional injected session

        # Service components

        # Initialize database account
        # Note: This will be called lazily on first async method call

    async def _get_async_db_session(self) -> AsyncSession:
        """Get an async database session."""
        if self._db_session is not None:
            return self._db_session

        # For production, sessions should be managed by dependency injection
        # This should not happen in normal operation
        raise RuntimeError(
            "No database session available - ensure proper dependency injection"
        )

    async def _execute_with_session(self, operation):
        """Execute a database operation with proper session management."""
        if self._db_session is not None:
            # Use injected session (testing)
            return await operation(self._db_session)
        else:
            # Use dependency injection pattern (production)
            from app.storage.database import get_async_session

            async for db in get_async_session():
                return await operation(db)

    async def _ensure_account_exists(self) -> None:
        """Ensure the account exists in the database."""
        from sqlalchemy import select

        async def _operation(db: AsyncSession):
            stmt = select(DBAccount).where(DBAccount.owner == self.account_owner)
            result = await db.execute(stmt)
            account = result.scalar_one_or_none()

            if not account:
                account = DBAccount(
                    owner=self.account_owner,
                    cash_balance=10000.0,  # Starting balance
                )
                db.add(account)
                await db.commit()
                await db.refresh(account)

                # Add some initial positions for compatibility
                initial_positions = [
                    DBPosition(
                        account_id=account.id,
                        symbol="AAPL",
                        quantity=10,
                        avg_price=145.00,
                    ),
                    DBPosition(
                        account_id=account.id,
                        symbol="GOOGL",
                        quantity=2,
                        avg_price=2850.00,
                    ),
                ]
                for pos in initial_positions:
                    db.add(pos)
                await db.commit()

        await self._execute_with_session(_operation)

    async def _get_account(self, account_id: str | None = None) -> DBAccount:
        """Get account from database by ID or by owner."""
        from sqlalchemy import select

        from app.core.id_utils import validate_optional_account_id

        # Validate account_id format if provided
        account_id = validate_optional_account_id(account_id)

        if account_id is None:
            # Ensure account exists first
            await self._ensure_account_exists()

        async def _operation(db: AsyncSession):
            if account_id is not None:
                # Get account by ID
                stmt = select(DBAccount).where(DBAccount.id == account_id)
                result = await db.execute(stmt)
                account = result.scalar_one_or_none()
                if not account:
                    raise NotFoundError(f"Account with ID {account_id} not found")
            else:
                # Get account by owner (legacy behavior)
                stmt = select(DBAccount).where(DBAccount.owner == self.account_owner)
                result = await db.execute(stmt)
                account = result.scalar_one_or_none()
                if not account:
                    raise NotFoundError(
                        f"Account for owner {self.account_owner} not found"
                    )
            return account

        return await self._execute_with_session(_operation)

    async def get_account_balance(self, account_id: str | None = None) -> float:
        """Get current account balance from database."""
        account = await self._get_account(account_id)
        return float(account.cash_balance)

    async def get_account_info(self, account_id: str | None = None) -> dict[str, Any]:
        """Get comprehensive account information."""
        account = await self._get_account(account_id)
        portfolio = await self.get_portfolio(account_id)

        return {
            "account_id": account.id,
            "owner": account.owner,
            "cash_balance": float(account.cash_balance),
            "starting_balance": float(account.starting_balance),
            "created_at": account.created_at.isoformat(),
            "updated_at": account.updated_at.isoformat(),
            "total_value": portfolio.cash_balance
            + sum(
                pos.quantity * (pos.current_price or 0) for pos in portfolio.positions
            ),
            "positions_count": len(portfolio.positions),
            "invested_value": sum(
                pos.quantity * (pos.current_price or 0) for pos in portfolio.positions
            ),
        }

    async def get_all_accounts_summary(self) -> AccountSummaryList:
        """Get summary of all accounts with ID, created date, starting balance, and current balance."""
        from sqlalchemy import select

        from app.schemas.accounts import AccountSummary

        async def _operation(db: AsyncSession):
            # Query all accounts
            stmt = select(DBAccount).order_by(DBAccount.created_at.desc())
            result = await db.execute(stmt)
            accounts = result.scalars().all()

            # Convert to AccountSummary objects
            account_summaries = []
            total_starting_balance = 0.0
            total_current_balance = 0.0

            for account in accounts:
                summary = AccountSummary(
                    id=account.id,
                    created_at=account.created_at,
                    starting_balance=account.starting_balance,
                    current_balance=account.cash_balance,
                    owner=account.owner,
                )
                account_summaries.append(summary)
                total_starting_balance += account.starting_balance
                total_current_balance += account.cash_balance

            return AccountSummaryList(
                accounts=account_summaries,
                total_count=len(account_summaries),
                total_starting_balance=total_starting_balance,
                total_current_balance=total_current_balance,
            )

        return await self._execute_with_session(_operation)

    # ============================================================================
    # USER PROFILE METHODS
    # ============================================================================

    async def create_user_profile(self, user_data: UserCreate) -> UserProfile:
        """Create a new user profile."""

        async def _operation(db: AsyncSession):
            # Create new user
            db_user = DBUser(
                username=user_data.username,
                email="",  # Not captured in simplified schema
                first_name=user_data.first_name,
                last_name=user_data.last_name,
                phone=None,
                date_of_birth=None,
                profile_settings={},
                preferences={},
            )
            db.add(db_user)
            await db.commit()
            await db.refresh(db_user)

            # Convert to UserProfile - simplified schema
            return UserProfile(
                id=db_user.id,
                username=db_user.username,
                first_name=db_user.first_name,
                last_name=db_user.last_name,
                created_at=db_user.created_at,
                updated_at=db_user.updated_at,
                full_name=f"{db_user.first_name} {db_user.last_name}",
                account_age_days=(datetime.utcnow() - db_user.created_at).days,
            )

        return await self._execute_with_session(_operation)

    async def get_user_profile(self, user_id: str) -> UserProfile | None:
        """Get user profile by ID."""

        async def _operation(db: AsyncSession):
            stmt = select(DBUser).where(DBUser.id == user_id)
            result = await db.execute(stmt)
            db_user = result.scalar_one_or_none()

            if not db_user:
                return None

            return UserProfile(
                id=db_user.id,
                username=db_user.username,
                first_name=db_user.first_name,
                last_name=db_user.last_name,
                created_at=db_user.created_at,
                updated_at=db_user.updated_at,
                full_name=f"{db_user.first_name} {db_user.last_name}",
                account_age_days=(datetime.utcnow() - db_user.created_at).days,
            )

        return await self._execute_with_session(_operation)

    async def update_user_profile(
        self, user_id: str, user_data: UserUpdate
    ) -> UserProfile | None:
        """Update user profile."""

        async def _operation(db: AsyncSession):
            # Check if user exists
            stmt = select(DBUser).where(DBUser.id == user_id)
            result = await db.execute(stmt)
            db_user = result.scalar_one_or_none()

            if not db_user:
                return None

            # Update fields that are provided (simplified schema)
            updated = False
            if user_data.first_name is not None:
                db_user.first_name = user_data.first_name
                updated = True
            if user_data.last_name is not None:
                db_user.last_name = user_data.last_name
                updated = True

            if updated:
                db_user.updated_at = datetime.utcnow()
                await db.commit()
                await db.refresh(db_user)

            return UserProfile(
                id=db_user.id,
                username=db_user.username,
                first_name=db_user.first_name,
                last_name=db_user.last_name,
                created_at=db_user.created_at,
                updated_at=db_user.updated_at,
                full_name=f"{db_user.first_name} {db_user.last_name}",
                account_age_days=(datetime.utcnow() - db_user.created_at).days,
            )

        return await self._execute_with_session(_operation)

    async def delete_user_profile(self, user_id: str) -> bool:
        """Delete user profile."""

        async def _operation(db: AsyncSession):
            stmt = delete(DBUser).where(DBUser.id == user_id)
            result = await db.execute(stmt)
            await db.commit()
            return result.rowcount > 0

        return await self._execute_with_session(_operation)

    async def list_users(
        self, limit: int = 50, offset: int = 0, verified_only: bool = False
    ) -> list[UserProfileSummary]:
        """List user profiles with pagination."""

        async def _operation(db: AsyncSession):
            stmt = select(DBUser).order_by(DBUser.created_at.desc())

            if verified_only:
                stmt = stmt.where(DBUser.is_verified)

            stmt = stmt.offset(offset).limit(limit)
            result = await db.execute(stmt)
            db_users = result.scalars().all()

            return [
                UserProfileSummary(
                    id=user.id,
                    username=user.username,
                    full_name=f"{user.first_name} {user.last_name}",
                    created_at=user.created_at,
                )
                for user in db_users
            ]

        return await self._execute_with_session(_operation)

    async def get_user_accounts(self, user_id: str) -> list[dict[str, Any]]:
        """Get all accounts for a user."""

        async def _operation(db: AsyncSession):
            stmt = select(DBAccount).where(DBAccount.user_id == user_id)
            result = await db.execute(stmt)
            accounts = result.scalars().all()

            return [
                {
                    "id": account.id,
                    "owner": account.owner,
                    "cash_balance": account.cash_balance,
                    "starting_balance": account.starting_balance,
                    "created_at": account.created_at,
                    "updated_at": account.updated_at,
                }
                for account in accounts
            ]

        return await self._execute_with_session(_operation)

    async def get_quote(self, symbol: str) -> StockQuote:
        """Get current stock quote for a symbol."""
        try:
            # Create asset from symbol
            asset = asset_factory(symbol)
            if asset is None:
                raise NotFoundError(f"Invalid symbol: {symbol}")

            # Use the quote adapter to get real market data
            quote = await self.quote_adapter.get_quote(asset)
            if quote is None:
                raise NotFoundError(f"Symbol {symbol} not found")

            # Convert to StockQuote format for backward compatibility
            return StockQuote(
                symbol=symbol.upper(),
                price=quote.price or 0.0,
                change=0.0,  # Not available in Quote format
                change_percent=0.0,  # Not available in Quote format
                volume=getattr(quote, "volume", 0),
                last_updated=quote.quote_date,
            )
        except Exception as e:
            # If adapter fails, raise a not found error
            raise NotFoundError(f"Symbol {symbol} not found: {e!s}") from e

    async def create_order(self, order_data: OrderCreate) -> Order:
        """Create a new trading order."""
        # Validate symbol exists
        await self.get_quote(order_data.symbol)

        async def _operation(db: AsyncSession):
            account = await self._get_account()

            # Create database order
            db_order = DBOrder(
                account_id=account.id,
                symbol=order_data.symbol.upper(),
                order_type=order_data.order_type,
                quantity=order_data.quantity,
                price=order_data.price,
                condition=order_data.condition,
                stop_price=order_data.stop_price,
                trail_percent=order_data.trail_percent,
                trail_amount=order_data.trail_amount,
                status=OrderStatus.PENDING,
                created_at=datetime.now(),
            )

            db.add(db_order)
            await db.commit()
            await db.refresh(db_order)

            # Use converter to convert to schema
            return await self.order_converter.to_schema(db_order)

        return await self._execute_with_session(_operation)

    async def get_orders(self) -> list[Order]:
        """Get all orders."""
        from sqlalchemy import select

        async def _operation(db: AsyncSession):
            account = await self._get_account()

            stmt = select(DBOrder).where(DBOrder.account_id == account.id)
            result = await db.execute(stmt)
            db_orders = result.scalars().all()

            # Use converter for all orders
            orders = []
            for db_order in db_orders:
                order = await self.order_converter.to_schema(db_order)
                orders.append(order)
            return orders

        return await self._execute_with_session(_operation)

    async def get_order(self, order_id: str) -> Order:
        """Get a specific order by ID."""
        from sqlalchemy import select

        async def _operation(db: AsyncSession):
            account = await self._get_account()

            stmt = select(DBOrder).where(
                DBOrder.id == order_id, DBOrder.account_id == account.id
            )
            result = await db.execute(stmt)
            db_order = result.scalar_one_or_none()

            if not db_order:
                raise NotFoundError(f"Order {order_id} not found")

            # Use converter to convert to schema
            return await self.order_converter.to_schema(db_order)

        return await self._execute_with_session(_operation)

    async def cancel_order(self, order_id: str) -> dict[str, str]:
        """Cancel a specific order."""
        from sqlalchemy import select

        async def _operation(db: AsyncSession):
            account = await self._get_account()

            stmt = select(DBOrder).where(
                DBOrder.id == order_id, DBOrder.account_id == account.id
            )
            result = await db.execute(stmt)
            db_order = result.scalar_one_or_none()

            if not db_order:
                raise NotFoundError(f"Order {order_id} not found")

            db_order.status = OrderStatus.CANCELLED
            await db.commit()

            return {"message": "Order cancelled successfully"}

        return await self._execute_with_session(_operation)

    async def cancel_all_stock_orders(self) -> dict[str, Any]:
        """Cancel all open stock orders."""
        from sqlalchemy import select

        async def _operation(db: AsyncSession):
            account = await self._get_account()

            # Get all open stock orders (orders without options-specific indicators)
            stmt = select(DBOrder).where(
                DBOrder.account_id == account.id,
                DBOrder.status.in_([OrderStatus.PENDING]),
                # Assume stock orders have simple symbols (no option-style identifiers)
                ~DBOrder.symbol.like("%C%"),  # Basic heuristic for non-option symbols
                ~DBOrder.symbol.like("%P%"),
            )
            result = await db.execute(stmt)
            open_stock_orders = result.scalars().all()

            cancelled_orders = []
            for order in open_stock_orders:
                order.status = OrderStatus.CANCELLED
                cancelled_orders.append(
                    {
                        "id": order.id,
                        "symbol": order.symbol,
                        "order_type": order.order_type,
                        "quantity": order.quantity,
                        "price": order.price,
                    }
                )

            await db.commit()

            return {
                "message": f"Cancelled {len(cancelled_orders)} stock orders",
                "cancelled_orders": cancelled_orders,
                "total_cancelled": len(cancelled_orders),
            }

        return await self._execute_with_session(_operation)

    async def cancel_all_option_orders(self) -> dict[str, Any]:
        """Cancel all open option orders."""
        from sqlalchemy import select

        async def _operation(db: AsyncSession):
            account = await self._get_account()

            # Get all open option orders (orders with options-specific indicators)
            stmt = select(DBOrder).where(
                DBOrder.account_id == account.id,
                DBOrder.status.in_([OrderStatus.PENDING]),
                # Assume option orders have option-style symbols or specific order types
                (
                    DBOrder.symbol.like("%C%")
                    | DBOrder.symbol.like("%P%")
                    | DBOrder.order_type.in_(
                        [OrderType.BTO, OrderType.STO, OrderType.BTC, OrderType.STC]
                    )
                ),
            )
            result = await db.execute(stmt)
            open_option_orders = result.scalars().all()

            cancelled_orders = []
            for order in open_option_orders:
                order.status = OrderStatus.CANCELLED
                cancelled_orders.append(
                    {
                        "id": order.id,
                        "symbol": order.symbol,
                        "order_type": order.order_type,
                        "quantity": order.quantity,
                        "price": order.price,
                    }
                )

            await db.commit()

            return {
                "message": f"Cancelled {len(cancelled_orders)} option orders",
                "cancelled_orders": cancelled_orders,
                "total_cancelled": len(cancelled_orders),
            }

        return await self._execute_with_session(_operation)

    async def get_portfolio(self, account_id: str | None = None) -> Portfolio:
        """Get complete portfolio information."""
        from sqlalchemy import select

        async def _operation(db: AsyncSession):
            account = await self._get_account(account_id)

            stmt = select(DBPosition).where(DBPosition.account_id == account.id)
            result = await db.execute(stmt)
            db_positions = result.scalars().all()

            # Convert database positions to schema positions using converter
            positions = []
            for db_pos in db_positions:
                # Update current price from quote adapter
                try:
                    quote = await self.get_quote(db_pos.symbol)
                    current_price = quote.price

                    # Use position converter with current price
                    position = await self.position_converter.to_schema(
                        db_pos, current_price
                    )
                    positions.append(position)
                except NotFoundError:
                    # Skip positions with no quote data
                    continue

            total_invested = sum(
                pos.quantity * (pos.current_price or 0) for pos in positions
            )
            total_value = account.cash_balance + total_invested
            total_pnl = sum(pos.unrealized_pnl or 0 for pos in positions)

            return Portfolio(
                cash_balance=account.cash_balance,
                total_value=total_value,
                positions=positions,
                daily_pnl=total_pnl,
                total_pnl=total_pnl,
            )

        return await self._execute_with_session(_operation)

    async def get_portfolio_summary(
        self, account_id: str | None = None
    ) -> PortfolioSummary:
        """Get portfolio summary."""
        # Use get_portfolio to get updated positions from database
        portfolio = await self.get_portfolio(account_id)

        invested_value = sum(
            pos.quantity * (pos.current_price or 0) for pos in portfolio.positions
        )
        total_value = portfolio.cash_balance + invested_value
        total_pnl = sum(pos.unrealized_pnl or 0 for pos in portfolio.positions)

        return PortfolioSummary(
            total_value=total_value,
            cash_balance=portfolio.cash_balance,
            invested_value=invested_value,
            daily_pnl=total_pnl,
            daily_pnl_percent=(total_pnl / total_value) * 100 if total_value > 0 else 0,
            total_pnl=total_pnl,
            total_pnl_percent=(total_pnl / total_value) * 100 if total_value > 0 else 0,
        )

    async def get_positions(self) -> list[Position]:
        """Get all portfolio positions."""
        # Use get_portfolio to get updated positions from database
        portfolio = await self.get_portfolio()
        return portfolio.positions

    async def get_position(self, symbol: str) -> Position:
        """Get a specific position by symbol."""
        portfolio = await self.get_portfolio()
        for position in portfolio.positions:
            if position.symbol.upper() == symbol.upper():
                return position
        raise NotFoundError(f"Position for symbol {symbol} not found")

    # Enhanced Options Trading Methods

    async def get_portfolio_greeks(self) -> dict[str, Any]:
        """Get aggregated Greeks for entire portfolio."""
        from .strategies import aggregate_portfolio_greeks

        positions = await self.get_positions()

        # Get quotes for all positions
        current_quotes = {}
        for position in positions:
            try:
                quote = await self.get_enhanced_quote(position.symbol)
                current_quotes[position.symbol] = quote
            except Exception:
                continue

        # Aggregate Greeks
        portfolio_greeks = aggregate_portfolio_greeks(positions, current_quotes)

        return {
            "timestamp": datetime.now().isoformat(),
            "total_positions": len(positions),
            "options_positions": len(
                [
                    p
                    for p in positions
                    if p.symbol in current_quotes
                    and hasattr(current_quotes[p.symbol], "delta")
                ]
            ),
            "portfolio_greeks": {
                "delta": portfolio_greeks.delta,
                "gamma": portfolio_greeks.gamma,
                "theta": portfolio_greeks.theta,
                "vega": portfolio_greeks.vega,
                "rho": portfolio_greeks.rho,
                "delta_normalized": portfolio_greeks.delta_normalized,
                "gamma_normalized": portfolio_greeks.gamma_normalized,
                "theta_normalized": portfolio_greeks.theta_normalized,
                "vega_normalized": portfolio_greeks.vega_normalized,
                "delta_dollars": portfolio_greeks.delta_dollars,
                "gamma_dollars": portfolio_greeks.gamma_dollars,
                "theta_dollars": portfolio_greeks.theta_dollars,
            },
        }

    async def get_position_greeks(self, symbol: str) -> dict[str, Any]:
        """Get Greeks for a specific position."""
        position = await self.get_position(symbol)

        # Get current quote for Greeks
        quote = await self.get_enhanced_quote(symbol)

        if not hasattr(quote, "delta"):
            raise ValueError("Position is not an options position")

        return {
            "symbol": symbol,
            "position_quantity": position.quantity,
            "multiplier": getattr(position, "multiplier", 100),
            "greeks": {
                "delta": quote.delta,
                "gamma": quote.gamma,
                "theta": quote.theta,
                "vega": quote.vega,
                "rho": quote.rho,
                "iv": getattr(quote, "iv", None),
            },
            "position_greeks": {
                "delta": (quote.delta or 0.0)
                * position.quantity
                * getattr(position, "multiplier", 100),
                "gamma": (quote.gamma or 0.0)
                * position.quantity
                * getattr(position, "multiplier", 100),
                "theta": (quote.theta or 0.0)
                * position.quantity
                * getattr(position, "multiplier", 100),
                "vega": (quote.vega or 0.0)
                * position.quantity
                * getattr(position, "multiplier", 100),
                "rho": (quote.rho or 0.0)
                * position.quantity
                * getattr(position, "multiplier", 100),
            },
            "underlying_price": getattr(quote, "underlying_price", None),
            "quote_time": quote.quote_date.isoformat(),
        }

    async def get_option_greeks_response(
        self, option_symbol: str, underlying_price: float | None = None
    ) -> dict[str, Any]:
        """Get comprehensive Greeks response for an option symbol."""
        # Calculate Greeks
        greeks = await self.calculate_greeks(
            option_symbol, underlying_price=underlying_price
        )

        # Get option details and quote
        asset = asset_factory(option_symbol)
        if not isinstance(asset, Option):
            raise ValueError("Symbol is not an option")

        option_quote = await self.get_enhanced_quote(option_symbol)

        return {
            "option_symbol": option_symbol,
            "underlying_symbol": asset.underlying.symbol,
            "strike": asset.strike,
            "expiration_date": asset.expiration_date.isoformat(),
            "option_type": asset.option_type.lower(),
            "days_to_expiration": asset.get_days_to_expiration(),
            "delta": greeks.get("delta"),
            "gamma": greeks.get("gamma"),
            "theta": greeks.get("theta"),
            "vega": greeks.get("vega"),
            "rho": greeks.get("rho"),
            "charm": greeks.get("charm"),
            "vanna": greeks.get("vanna"),
            "speed": greeks.get("speed"),
            "zomma": greeks.get("zomma"),
            "color": greeks.get("color"),
            "implied_volatility": greeks.get("iv"),
            "underlying_price": underlying_price,
            "option_price": option_quote.price,
            "data_source": "trading_service",
            "cached": False,
        }

    async def get_enhanced_quote(
        self, symbol: str, underlying_price: float | None = None
    ) -> Quote | OptionQuote:
        """Get enhanced quote with Greeks for options."""
        asset = asset_factory(symbol)
        if asset is None:
            raise NotFoundError(f"Invalid symbol: {symbol}")

        # Use the quote adapter to get real market data
        quote = await self.quote_adapter.get_quote(asset)
        if quote:
            return quote

        # No fallback - raise error if adapter cannot provide quote
        raise NotFoundError(f"No quote available for {symbol}")

    async def get_options_chain(
        self, underlying: str, expiration_date: date | None = None
    ) -> OptionsChain:
        """Get complete options chain for an underlying."""
        exp_datetime = (
            datetime.combine(expiration_date, datetime.min.time())
            if expiration_date
            else None
        )
        chain = await self.quote_adapter.get_options_chain(underlying, exp_datetime)
        if chain is None:
            raise NotFoundError(f"No options chain found for {underlying}")
        return chain

    async def calculate_greeks(
        self, option_symbol: str, underlying_price: float | None = None
    ) -> dict[str, float | None]:
        """Calculate option Greeks."""
        option = asset_factory(option_symbol)
        if not isinstance(option, Option):
            raise ValueError(f"{option_symbol} is not an option")

        # Get quotes
        option_quote = await self.get_enhanced_quote(option_symbol)
        if underlying_price is None:
            underlying_quote = await self.get_enhanced_quote(option.underlying.symbol)
            underlying_price = underlying_quote.price

        if not option_quote.price or not underlying_price:
            raise ValueError("Insufficient pricing data for Greeks calculation")

        return calculate_option_greeks(
            option_type=option.option_type,
            strike=option.strike,
            underlying_price=underlying_price,
            days_to_expiration=option.get_days_to_expiration(datetime.now().date()),
            option_price=option_quote.price,
        )

    async def validate_account_state(self) -> bool:
        """Validate current account state."""
        cash_balance = await self.get_account_balance()
        positions = await self.get_positions()
        return self.account_validation.validate_account_state(
            cash_balance=cash_balance, positions=positions
        )

    async def get_expiration_dates(self, underlying: str) -> list[date]:
        """Get available expiration dates for an underlying symbol."""
        if hasattr(self.quote_adapter, "get_expiration_dates"):
            if asyncio.iscoroutinefunction(self.quote_adapter.get_expiration_dates):
                return await self.quote_adapter.get_expiration_dates(underlying)
            else:
                return self.quote_adapter.get_expiration_dates(underlying)
        else:
            # Fallback to empty list if adapter doesn't support expiration dates
            return []

    async def create_multi_leg_order(self, order_data: Any) -> Order:
        """Create a multi-leg order."""
        # For now, create a simple order representation
        # In a real implementation, this would handle complex multi-leg orders
        order = Order(
            id=str(uuid4()),
            symbol=f"MULTI_LEG_{len(order_data.legs)}_LEGS",
            order_type=(
                order_data.legs[0].order_type if order_data.legs else OrderType.BUY
            ),
            quantity=sum(leg.quantity for leg in order_data.legs),
            price=sum(leg.price or 0 for leg in order_data.legs if leg.price),
            condition=getattr(order_data, "condition", OrderCondition.MARKET),
            status=OrderStatus.FILLED,
            created_at=datetime.now(),
            filled_at=datetime.now(),
            net_price=sum(leg.price or 0 for leg in order_data.legs if leg.price),
            stop_price=None,
            trail_percent=None,
            trail_amount=None,
        )

        # Persist to database using the same pattern as create_order
        async def _operation(db: AsyncSession):
            # Query for the account ID instead of using account_owner directly
            account = await self._get_account()

            db_order = DBOrder(
                id=order.id,
                symbol=order.symbol,
                order_type=order.order_type.value,
                quantity=order.quantity,
                price=order.price,
                condition=order.condition.value,
                status=order.status.value,
                created_at=order.created_at,
                filled_at=order.filled_at,
                account_id=account.id,
            )
            db.add(db_order)
            await db.commit()
            await db.refresh(db_order)

        await self._execute_with_session(_operation)

        return order

    async def find_tradable_options(
        self,
        symbol: str,
        expiration_date: str | None = None,
        option_type: str | None = None,
    ) -> dict[str, Any]:
        """
        Find tradable options for a symbol with optional filtering.

        This method provides a unified interface that works with both
        test data and live market data adapters.
        """
        try:
            # Get the full options chain
            exp_date = None
            if expiration_date:
                exp_date = datetime.strptime(expiration_date, "%Y-%m-%d")

            chain = await self.get_options_chain(
                symbol, exp_date.date() if exp_date else None
            )

            if not chain:
                return {
                    "symbol": symbol,
                    "filters": {
                        "expiration_date": expiration_date,
                        "option_type": option_type,
                    },
                    "options": [],
                    "total_found": 0,
                    "message": "No tradable options found",
                }

            # Filter options based on criteria
            options = []
            target_options = []

            if option_type is None or option_type.lower() == "call":
                target_options.extend(chain.calls)
            if option_type is None or option_type.lower() == "put":
                target_options.extend(chain.puts)

            # Convert to API format
            for option_quote in target_options:
                if not isinstance(option_quote.asset, Option):
                    continue

                option_data = {
                    "symbol": option_quote.asset.symbol,
                    "underlying_symbol": option_quote.asset.underlying.symbol,
                    "strike_price": option_quote.asset.strike,
                    "expiration_date": option_quote.asset.expiration_date.isoformat(),
                    "option_type": option_quote.asset.option_type.lower(),
                    "bid_price": option_quote.bid,
                    "ask_price": option_quote.ask,
                    "mark_price": option_quote.price,
                    "volume": getattr(option_quote, "volume", None),
                    "open_interest": getattr(option_quote, "open_interest", None),
                    "delta": getattr(option_quote, "delta", None),
                    "gamma": getattr(option_quote, "gamma", None),
                    "theta": getattr(option_quote, "theta", None),
                    "vega": getattr(option_quote, "vega", None),
                }
                options.append(option_data)

            return {
                "symbol": symbol,
                "filters": {
                    "expiration_date": expiration_date,
                    "option_type": option_type,
                },
                "options": options,
                "total_found": len(options),
            }

        except Exception as e:
            return {"error": str(e)}

    async def get_option_market_data(self, option_id: str) -> dict[str, Any]:
        """
        Get market data for a specific option contract.

        Args:
            option_id: Option symbol or identifier

        Returns:
            Dict containing market data or error
        """
        try:
            # Try to get quote using the option symbol
            asset = asset_factory(option_id)
            if not isinstance(asset, Option):
                return {"error": f"Invalid option symbol: {option_id}"}

            quote = await self.get_enhanced_quote(option_id)
            if not isinstance(quote, OptionQuote):
                return {"error": f"No market data available for {option_id}"}

            return {
                "option_id": option_id,
                "symbol": quote.asset.symbol,
                "underlying_symbol": (
                    quote.asset.underlying.symbol if quote.asset.underlying else "N/A"
                ),
                "strike_price": quote.asset.strike,
                "expiration_date": (
                    quote.asset.expiration_date.isoformat()
                    if quote.asset.expiration_date
                    else "N/A"
                ),
                "option_type": (
                    quote.asset.option_type.lower()
                    if quote.asset.option_type
                    else "N/A"
                ),
                "bid_price": quote.bid,
                "ask_price": quote.ask,
                "mark_price": quote.price,
                "volume": getattr(quote, "volume", None),
                "open_interest": getattr(quote, "open_interest", None),
                "underlying_price": quote.underlying_price,
                "greeks": {
                    "delta": getattr(quote, "delta", None),
                    "gamma": getattr(quote, "gamma", None),
                    "theta": getattr(quote, "theta", None),
                    "vega": getattr(quote, "vega", None),
                    "rho": getattr(quote, "rho", None),
                },
                "implied_volatility": getattr(quote, "iv", None),
                "last_updated": quote.quote_date.isoformat(),
            }

        except Exception as e:
            return {"error": str(e)}

    # ============================================================================
    # STOCK MARKET DATA METHODS
    # ============================================================================

    async def get_stock_price(self, symbol: str) -> dict[str, Any]:
        """
        Get current stock price and basic metrics.

        This method provides a unified interface that works with both
        test data and live market data adapters.
        """
        try:
            asset = asset_factory(symbol)
            if not asset:
                return {"error": f"Invalid symbol: {symbol}"}

            quote = await self.get_enhanced_quote(symbol)
            if not quote:
                return {"error": f"No price data found for symbol: {symbol}"}

            # Calculate basic metrics
            previous_close = getattr(quote, "previous_close", None)
            if previous_close is None:
                # Fallback calculation based on bid/ask
                previous_close = quote.price

            change = 0.0
            change_percent = 0.0

            if previous_close and previous_close > 0 and quote.price is not None:
                change = quote.price - previous_close
                change_percent = (change / previous_close) * 100

            return {
                "symbol": symbol.upper(),
                "price": quote.price,
                "change": round(change, 2),
                "change_percent": round(change_percent, 2),
                "previous_close": previous_close,
                "volume": getattr(quote, "volume", None),
                "ask_price": quote.ask,
                "bid_price": quote.bid,
                "last_trade_price": quote.price,
                "last_updated": quote.quote_date.isoformat(),
            }

        except Exception as e:
            return {"error": str(e)}

    async def get_stock_info(self, symbol: str) -> dict[str, Any]:
        """
        Get detailed company information and fundamentals for a stock.

        This method provides a unified interface that works with both
        test data and live market data adapters.
        """
        try:
            asset = asset_factory(symbol)
            if not asset:
                return {"error": f"Invalid symbol: {symbol}"}

            # For now, use the adapter's extended functionality if available
            if hasattr(self.quote_adapter, "get_stock_info"):
                result = await self.quote_adapter.get_stock_info(symbol)
                return dict(result) if result else {}
            else:
                # Fallback to basic quote data
                quote = await self.get_enhanced_quote(symbol)
                if not quote:
                    return {
                        "error": f"No company information found for symbol: {symbol}"
                    }

                return {
                    "symbol": symbol.upper(),
                    "company_name": f"{symbol.upper()} Company",
                    "sector": "N/A",
                    "industry": "N/A",
                    "description": "Company information not available",
                    "market_cap": "N/A",
                    "pe_ratio": "N/A",
                    "dividend_yield": "N/A",
                    "high_52_weeks": "N/A",
                    "low_52_weeks": "N/A",
                    "average_volume": "N/A",
                    "tradeable": True,
                    "last_updated": quote.quote_date.isoformat(),
                }

        except Exception as e:
            return {"error": str(e)}

    async def get_price_history(
        self, symbol: str, period: str = "week"
    ) -> dict[str, Any]:
        """
        Get historical price data for a stock.

        This method provides a unified interface that works with both
        test data and live market data adapters.
        """
        try:
            asset = asset_factory(symbol)
            if not asset:
                return {"error": f"Invalid symbol: {symbol}"}

            # For now, use the adapter's extended functionality if available
            if hasattr(self.quote_adapter, "get_price_history"):
                result = await self.quote_adapter.get_price_history(symbol, period)
                return dict(result) if result else {}
            else:
                # Fallback to current quote only
                quote = await self.get_enhanced_quote(symbol)
                if not quote:
                    return {
                        "error": f"No historical data found for {symbol} over {period}"
                    }

                # Create a single data point from current quote
                data_point = {
                    "date": quote.quote_date.isoformat(),
                    "open": quote.price,
                    "high": quote.price,
                    "low": quote.price,
                    "close": quote.price,
                    "volume": getattr(quote, "volume", 0),
                }

                return {
                    "symbol": symbol.upper(),
                    "period": period,
                    "interval": "current",
                    "data_points": [data_point],
                    "message": "Historical data not available, showing current quote only",
                }

        except Exception as e:
            return {"error": str(e)}

    async def search_stocks(self, query: str) -> dict[str, Any]:
        """
        Search for stocks by symbol or company name.

        This method provides a unified interface that works with both
        test data and live market data adapters.
        """
        try:
            # For now, use the adapter's extended functionality if available
            if hasattr(self.quote_adapter, "search_stocks"):
                result = await self.quote_adapter.search_stocks(query)
                # If adapter already returns proper format, return as-is
                if (
                    isinstance(result, dict)
                    and "query" in result
                    and "results" in result
                ):
                    return result
                # Otherwise, wrap in proper format
                return {
                    "query": query,
                    "results": result if result else [],
                    "total_count": len(result) if result else 0,
                }
            else:
                # Fallback to symbol matching from available symbols
                query_upper = query.upper()
                available_symbols = self.get_available_symbols()

                results = []
                for symbol in available_symbols:
                    if query_upper in symbol.upper():
                        results.append(
                            {
                                "symbol": symbol,
                                "name": f"{symbol} Company",
                                "tradeable": True,
                            }
                        )

                return {
                    "query": query,
                    "results": results[:10],  # Limit to 10 results
                    "message": (
                        "Limited search from test adapter" if not results else None
                    ),
                }

        except Exception as e:
            return {"error": str(e)}

    async def get_formatted_options_chain(
        self,
        symbol: str,
        expiration_date: date | None = None,
        min_strike: float | None = None,
        max_strike: float | None = None,
        include_greeks: bool = True,
    ) -> dict[str, Any]:
        """
        Get formatted options chain with filtering and optional Greeks.

        Args:
            symbol: Underlying symbol
            expiration_date: Filter by expiration date
            min_strike: Minimum strike price filter
            max_strike: Maximum strike price filter
            include_greeks: Whether to include Greeks in response

        Returns:
            Dict containing formatted options chain data
        """
        try:
            # Get the raw options chain
            chain = await self.get_options_chain(symbol, expiration_date)

            # Format the response
            formatted_calls = []
            formatted_puts = []

            # Process calls
            for call_quote in chain.calls:
                if not isinstance(call_quote.asset, Option):
                    continue

                strike = call_quote.asset.strike

                # Apply strike filters
                if min_strike is not None and strike < min_strike:
                    continue
                if max_strike is not None and strike > max_strike:
                    continue

                call_data = {
                    "symbol": call_quote.asset.symbol,
                    "strike": strike,
                    "bid": call_quote.bid,
                    "ask": call_quote.ask,
                    "mark": call_quote.price,
                    "volume": getattr(call_quote, "volume", None),
                    "open_interest": getattr(call_quote, "open_interest", None),
                }

                # Add Greeks if requested
                if include_greeks:
                    call_data.update(
                        {
                            "delta": getattr(call_quote, "delta", None),
                            "gamma": getattr(call_quote, "gamma", None),
                            "theta": getattr(call_quote, "theta", None),
                            "vega": getattr(call_quote, "vega", None),
                            "rho": getattr(call_quote, "rho", None),
                            "iv": getattr(call_quote, "iv", None),
                        }
                    )

                formatted_calls.append(call_data)

            # Process puts
            for put_quote in chain.puts:
                if not isinstance(put_quote.asset, Option):
                    continue

                strike = put_quote.asset.strike

                # Apply strike filters
                if min_strike is not None and strike < min_strike:
                    continue
                if max_strike is not None and strike > max_strike:
                    continue

                put_data = {
                    "symbol": put_quote.asset.symbol,
                    "strike": strike,
                    "bid": put_quote.bid,
                    "ask": put_quote.ask,
                    "mark": put_quote.price,
                    "volume": getattr(put_quote, "volume", None),
                    "open_interest": getattr(put_quote, "open_interest", None),
                }

                # Add Greeks if requested
                if include_greeks:
                    put_data.update(
                        {
                            "delta": getattr(put_quote, "delta", None),
                            "gamma": getattr(put_quote, "gamma", None),
                            "theta": getattr(put_quote, "theta", None),
                            "vega": getattr(put_quote, "vega", None),
                            "rho": getattr(put_quote, "rho", None),
                            "iv": getattr(put_quote, "iv", None),
                        }
                    )

                formatted_puts.append(put_data)

            return {
                "underlying_symbol": symbol,
                "underlying_price": chain.underlying_price,
                "expiration_date": (
                    chain.expiration_date.isoformat() if chain.expiration_date else None
                ),
                "quote_time": datetime.now().isoformat(),
                "calls": formatted_calls,
                "puts": formatted_puts,
            }

        except Exception as e:
            return {"error": str(e)}

    async def create_multi_leg_order_from_request(
        self,
        legs: list[dict[str, Any]],
        order_type: str,
        net_price: float | None = None,
    ) -> Order:
        """
        Create a multi-leg order from raw request data.

        Args:
            legs: List of order legs with symbol, quantity, and side
            order_type: Type of order (limit, market, etc.)
            net_price: Net price for the order

        Returns:
            Order object representing the multi-leg order
        """
        try:
            # Convert raw leg data to structured format
            structured_legs = []
            for leg in legs:
                structured_legs.append(
                    {
                        "symbol": leg["symbol"],
                        "quantity": leg["quantity"],
                        "side": leg["side"],
                        "order_type": order_type,
                        "price": net_price,
                    }
                )

            # Create a mock order data structure for the existing create_multi_leg_order method
            class MockOrderData:
                class MockLeg:
                    def __init__(self, data: dict[str, Any]) -> None:
                        self.symbol = data["symbol"]
                        self.quantity = data["quantity"]
                        self.side = data["side"]
                        self.order_type = (
                            OrderType.BUY if data["side"] == "buy" else OrderType.SELL
                        )
                        self.price = data.get("price")

                def __init__(self, legs: list[dict[str, Any]]) -> None:
                    self.legs = [MockOrderData.MockLeg(leg) for leg in legs]
                    self.condition = (
                        OrderCondition.LIMIT
                        if order_type == "limit"
                        else OrderCondition.MARKET
                    )

            mock_order_data = MockOrderData(structured_legs)

            # Use the existing create_multi_leg_order method
            return await self.create_multi_leg_order(mock_order_data)

        except Exception as e:
            raise ValueError(f"Failed to create multi-leg order: {e!s}") from e

    async def simulate_expiration(
        self, processing_date: str | None = None, dry_run: bool = True
    ) -> dict[str, Any]:
        """
        Simulate option expiration processing for current portfolio.

        Args:
            processing_date: Date to process expirations (YYYY-MM-DD format)
            dry_run: Whether to perform a dry run without modifying account

        Returns:
            Dict containing simulation results
        """
        try:
            # Parse processing date
            if processing_date:
                process_date = datetime.strptime(processing_date, "%Y-%m-%d").date()
            else:
                process_date = datetime.now().date()

            # Get current portfolio positions
            portfolio = await self.get_portfolio()

            expiring_positions = []
            non_expiring_positions = []
            total_impact = 0.0

            for position in portfolio.positions:
                try:
                    # Check if position is an option
                    asset = asset_factory(position.symbol)
                    if isinstance(asset, Option):
                        # Check if option expires on or before processing date
                        if asset.expiration_date <= process_date:
                            # Get current quote to determine intrinsic value
                            try:
                                option_quote = await self.get_enhanced_quote(
                                    position.symbol
                                )
                                underlying_quote = await self.get_enhanced_quote(
                                    asset.underlying.symbol
                                )

                                # Calculate intrinsic value
                                intrinsic_value = 0.0
                                if (
                                    asset.option_type
                                    and asset.option_type.upper() == "CALL"
                                ):
                                    if (
                                        underlying_quote.price is not None
                                        and asset.strike is not None
                                    ):
                                        intrinsic_value = max(
                                            0, underlying_quote.price - asset.strike
                                        )
                                elif (
                                    asset.option_type
                                    and asset.option_type.upper() == "PUT"
                                ) and (
                                    underlying_quote.price is not None
                                    and asset.strike is not None
                                ):
                                    intrinsic_value = max(
                                        0, asset.strike - underlying_quote.price
                                    )

                                # Calculate impact
                                multiplier = 100  # Standard option multiplier
                                position_impact = (
                                    intrinsic_value * position.quantity * multiplier
                                )
                                total_impact += position_impact

                                expiring_positions.append(
                                    {
                                        "symbol": position.symbol,
                                        "underlying_symbol": asset.underlying.symbol,
                                        "strike": asset.strike,
                                        "option_type": asset.option_type,
                                        "expiration_date": asset.expiration_date.isoformat(),
                                        "quantity": position.quantity,
                                        "current_price": option_quote.price,
                                        "underlying_price": underlying_quote.price,
                                        "intrinsic_value": intrinsic_value,
                                        "position_impact": position_impact,
                                        "action": (
                                            "expire_worthless"
                                            if intrinsic_value == 0
                                            else "exercise_or_assign"
                                        ),
                                    }
                                )

                            except Exception as quote_error:
                                # Handle positions where we can't get quotes
                                expiring_positions.append(
                                    {
                                        "symbol": position.symbol,
                                        "expiration_date": asset.expiration_date.isoformat(),
                                        "quantity": position.quantity,
                                        "error": f"Could not get quote: {quote_error!s}",
                                        "action": "manual_review_required",
                                    }
                                )
                        else:
                            non_expiring_positions.append(
                                {
                                    "symbol": position.symbol,
                                    "expiration_date": asset.expiration_date.isoformat(),
                                    "quantity": position.quantity,
                                    "days_to_expiration": (
                                        asset.expiration_date - process_date
                                    ).days,
                                }
                            )
                    else:
                        # Non-option position
                        non_expiring_positions.append(
                            {
                                "symbol": position.symbol,
                                "quantity": position.quantity,
                                "position_type": "stock",
                            }
                        )

                except Exception as position_error:
                    # Handle positions we can't parse
                    expiring_positions.append(
                        {
                            "symbol": position.symbol,
                            "error": f"Could not parse position: {position_error!s}",
                            "action": "manual_review_required",
                        }
                    )

            # Prepare simulation results
            results = {
                "processing_date": process_date.isoformat(),
                "dry_run": dry_run,
                "total_positions": len(portfolio.positions),
                "expiring_positions": len(expiring_positions),
                "non_expiring_positions": len(non_expiring_positions),
                "total_impact": total_impact,
                "expiring_options": expiring_positions,
                "non_expiring_positions_details": non_expiring_positions,
                "summary": {
                    "positions_expiring": len(expiring_positions),
                    "estimated_cash_impact": total_impact,
                    "positions_requiring_review": len(
                        [pos for pos in expiring_positions if "error" in pos]
                    ),
                },
            }

            if not dry_run:
                # In a real implementation, this would actually process the expirations
                # For now, we just add a note that processing would happen
                results["processing_note"] = (
                    "Actual expiration processing not implemented in this simulation"
                )

            return results

        except Exception as e:
            return {"error": f"Simulation failed: {e!s}"}

    def get_available_symbols(self) -> list[str]:
        """Get list of available symbols."""
        return self.quote_adapter.get_available_symbols()

    async def get_market_hours(self) -> dict[str, Any]:
        """
        Get market hours and status information.

        This method provides a unified interface that works with both
        test data and live market data adapters.
        """
        try:
            # Use the adapter's extended functionality if available
            if hasattr(self.quote_adapter, "get_market_hours"):
                result = await self.quote_adapter.get_market_hours()
                return dict(result) if result else {}
            else:
                # Fallback to basic market status check
                is_open = await self.quote_adapter.is_market_open()

                # Return basic market hours info
                return {
                    "is_market_open": is_open,
                    "market_status": "open" if is_open else "closed",
                    "timezone": "US/Eastern",
                    "regular_hours": {"start": "09:30", "end": "16:00"},
                    "extended_hours": {
                        "premarket_start": "04:00",
                        "premarket_end": "09:30",
                        "aftermarket_start": "16:00",
                        "aftermarket_end": "20:00",
                    },
                    "message": "Market hours data from fallback implementation",
                }

        except Exception as e:
            return {"error": str(e)}

    async def get_stock_ratings(self, symbol: str) -> dict[str, Any]:
        """
        Get analyst ratings and recommendations for a stock.

        This method provides a unified interface that works with both
        test data and live market data adapters.
        """
        try:
            asset = asset_factory(symbol)
            if not asset:
                return {"error": f"Invalid symbol: {symbol}"}

            # Use the adapter's extended functionality if available
            if hasattr(self.quote_adapter, "get_stock_ratings"):
                result = await self.quote_adapter.get_stock_ratings(symbol)
                return dict(result) if result else {}
            else:
                # Fallback to simulated ratings data
                return {
                    "symbol": symbol.upper(),
                    "overall_rating": "Hold",
                    "rating_score": 3.2,
                    "analyst_count": 12,
                    "ratings_breakdown": {
                        "strong_buy": 2,
                        "buy": 3,
                        "hold": 5,
                        "sell": 2,
                        "strong_sell": 0,
                    },
                    "price_targets": {
                        "average_target": 155.50,
                        "high_target": 175.00,
                        "low_target": 140.00,
                        "median_target": 152.00,
                    },
                    "last_updated": datetime.now().isoformat(),
                    "message": "Simulated ratings data from fallback implementation",
                }

        except Exception as e:
            return {"error": str(e)}

    async def get_stock_events(self, symbol: str) -> dict[str, Any]:
        """
        Get corporate events and calendar items for a stock.

        This method provides a unified interface that works with both
        test data and live market data adapters.
        """
        try:
            asset = asset_factory(symbol)
            if not asset:
                return {"error": f"Invalid symbol: {symbol}"}

            # Use the adapter's extended functionality if available
            if hasattr(self.quote_adapter, "get_stock_events"):
                result = await self.quote_adapter.get_stock_events(symbol)
                return dict(result) if result else {}
            else:
                # Fallback to simulated events data
                next_earnings = datetime.now() + timedelta(days=30)
                next_dividend = datetime.now() + timedelta(days=45)

                return {
                    "symbol": symbol.upper(),
                    "upcoming_events": [
                        {
                            "event_type": "earnings",
                            "event_date": next_earnings.isoformat(),
                            "description": f"Q{(next_earnings.month - 1) // 3 + 1} Earnings Report",
                            "confirmed": False,
                        },
                        {
                            "event_type": "dividend",
                            "event_date": next_dividend.isoformat(),
                            "description": "Quarterly Dividend Payment",
                            "estimated_amount": 0.50,
                            "confirmed": False,
                        },
                    ],
                    "recent_events": [
                        {
                            "event_type": "earnings",
                            "event_date": (
                                datetime.now() - timedelta(days=90)
                            ).isoformat(),
                            "description": "Previous Quarter Earnings",
                            "confirmed": True,
                        }
                    ],
                    "last_updated": datetime.now().isoformat(),
                    "message": "Simulated events data from fallback implementation",
                }

        except Exception as e:
            return {"error": str(e)}

    async def get_stock_level2_data(self, symbol: str) -> dict[str, Any]:
        """
        Get Level 2 market data (order book) for a stock.

        This method provides a unified interface that works with both
        test data and live market data adapters.
        """
        try:
            asset = asset_factory(symbol)
            if not asset:
                return {"error": f"Invalid symbol: {symbol}"}

            # Use the adapter's extended functionality if available
            if hasattr(self.quote_adapter, "get_stock_level2_data"):
                result = await self.quote_adapter.get_stock_level2_data(symbol)
                return dict(result) if result else {}
            else:
                # Get current quote for base price
                quote = await self.get_enhanced_quote(symbol)
                if not quote or not quote.price:
                    return {"error": f"No market data available for {symbol}"}

                base_price = quote.price
                bid_price = quote.bid or (base_price - 0.01)
                ask_price = quote.ask or (base_price + 0.01)

                # Simulate Level 2 order book data
                return {
                    "symbol": symbol.upper(),
                    "bid_levels": [
                        {"price": round(bid_price, 2), "size": 1000, "orders": 5},
                        {
                            "price": round(bid_price - 0.01, 2),
                            "size": 2500,
                            "orders": 8,
                        },
                        {
                            "price": round(bid_price - 0.02, 2),
                            "size": 1800,
                            "orders": 6,
                        },
                        {
                            "price": round(bid_price - 0.03, 2),
                            "size": 3200,
                            "orders": 12,
                        },
                        {"price": round(bid_price - 0.04, 2), "size": 800, "orders": 3},
                    ],
                    "ask_levels": [
                        {"price": round(ask_price, 2), "size": 1200, "orders": 4},
                        {
                            "price": round(ask_price + 0.01, 2),
                            "size": 1900,
                            "orders": 7,
                        },
                        {
                            "price": round(ask_price + 0.02, 2),
                            "size": 2200,
                            "orders": 9,
                        },
                        {
                            "price": round(ask_price + 0.03, 2),
                            "size": 1500,
                            "orders": 6,
                        },
                        {
                            "price": round(ask_price + 0.04, 2),
                            "size": 2800,
                            "orders": 11,
                        },
                    ],
                    "market_maker_moves": {
                        "total_bid_size": 10300,
                        "total_ask_size": 9600,
                        "spread": round(ask_price - bid_price, 2),
                        "spread_percentage": round(
                            ((ask_price - bid_price) / base_price) * 100, 4
                        ),
                    },
                    "last_updated": datetime.now().isoformat(),
                    "message": "Simulated Level 2 data from fallback implementation",
                }

        except Exception as e:
            return {"error": str(e)}


# Initialize adapter based on configuration
def _get_quote_adapter() -> QuoteAdapter:
    """Get the appropriate quote adapter based on environment."""

    # Use Robinhood adapter if configured for live data
    use_live_data = os.getenv("USE_LIVE_DATA", "False").lower() == "true"

    if use_live_data:
        try:
            from ..adapters.robinhood import RobinhoodAdapter

            return RobinhoodAdapter()
        except ImportError as e:
            print(f"Warning: Could not load Robinhood adapter: {e}")
            print("Falling back to test data adapter")

    # Default to test data adapter
    return DevDataQuoteAdapter()


# Global service instance removed - now managed by FastAPI lifespan
# Use app.core.dependencies.get_trading_service() for dependency injection
# MCP tools use their own service management via app.mcp.tools
