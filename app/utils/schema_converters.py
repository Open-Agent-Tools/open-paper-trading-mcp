"""
Schema-Database conversion utilities.

Provides converters between API schemas and database models to handle
field mapping differences and maintain clean separation of concerns.
"""

from abc import ABC, abstractmethod
from typing import TYPE_CHECKING, Generic, Optional, TypeVar

from app.models.assets import asset_factory
from app.models.database.trading import Account as DBAccount
from app.models.database.trading import Order as DBOrder
from app.models.database.trading import Position as DBPosition
from app.schemas.accounts import Account
from app.schemas.orders import Order, OrderCondition
from app.schemas.positions import Position

if TYPE_CHECKING:
    from app.services.trading_service import TradingService

T = TypeVar("T")
U = TypeVar("U")


class SchemaConverter(Generic[T, U], ABC):
    """Base class for schema-database converters."""

    @abstractmethod
    async def to_schema(self, db_model: T) -> U:
        """Convert database model to schema."""
        pass

    @abstractmethod
    def to_database(self, schema: U, **kwargs) -> T:
        """Convert schema to database model."""
        pass


class AccountConverter(SchemaConverter[DBAccount, Account]):
    """Converter between database Account and API Account schema."""

    def __init__(self, trading_service: Optional["TradingService"] = None):
        """
        Initialize converter.

        Args:
            trading_service: Optional trading service for loading positions
        """
        self.trading_service = trading_service

    async def to_schema(self, db_account: DBAccount) -> Account:
        """
        Convert DBAccount to Account schema.

        Args:
            db_account: Database account model

        Returns:
            Account API schema
        """
        # Load positions if trading service is available
        positions = []
        if self.trading_service and hasattr(db_account, "positions"):
            position_converter = PositionConverter(self.trading_service)
            positions = [
                await position_converter.to_schema(db_pos)
                for db_pos in db_account.positions
            ]

        return Account(
            id=db_account.id,
            owner=db_account.owner,
            cash_balance=db_account.cash_balance,
            name=db_account.owner,  # Use owner as name for now
            positions=positions,
        )

    def to_database(self, account: Account, **kwargs) -> DBAccount:
        """
        Convert Account schema to DBAccount.

        Args:
            account: Account API schema

        Returns:
            Database account model
        """
        return DBAccount(
            id=account.id,
            owner=account.owner or account.name or "unknown",
            cash_balance=account.cash_balance,
        )


class OrderConverter(SchemaConverter[DBOrder, Order]):
    """Converter between database Order and API Order schema."""

    async def to_schema(self, db_order: DBOrder) -> Order:
        """
        Convert DBOrder to Order schema.

        Args:
            db_order: Database order model

        Returns:
            Order API schema
        """
        return Order(
            id=db_order.id,
            symbol=db_order.symbol,
            order_type=db_order.order_type,
            quantity=db_order.quantity,
            price=db_order.price,
            status=db_order.status,
            created_at=db_order.created_at,
            filled_at=db_order.filled_at,
            # Schema-only fields with defaults:
            condition=OrderCondition.MARKET,  # Default condition
            legs=[],  # Will be populated for multi-leg orders
            net_price=db_order.price,  # Same as price for simple orders
        )

    def to_database(self, order: Order, **kwargs) -> DBOrder:
        """
        Convert Order schema to DBOrder.

        Args:
            order: Order API schema
            account_id: Required account ID not in schema

        Returns:
            Database order model
        """
        account_id = kwargs.get("account_id")
        if not account_id:
            raise ConversionError("account_id is required for order conversion")

        return DBOrder(
            id=order.id,
            account_id=account_id,  # Required field not in schema
            symbol=order.symbol,
            order_type=order.order_type,
            quantity=order.quantity,
            price=order.price,
            status=order.status,
            created_at=order.created_at,
            filled_at=order.filled_at,
        )


class PositionConverter(SchemaConverter[DBPosition, Position]):
    """Converter between database Position and API Position schema."""

    def __init__(self, trading_service: Optional["TradingService"] = None):
        """
        Initialize converter.

        Args:
            trading_service: Optional trading service for current prices and Greeks
        """
        self.trading_service = trading_service

    async def to_schema(
        self, db_position: DBPosition, current_price: float | None = None
    ) -> Position:
        """
        Convert DBPosition to Position schema with calculated fields.

        Args:
            db_position: Database position model
            current_price: Optional current market price

        Returns:
            Position API schema with calculated fields
        """
        # Get current price if not provided
        if current_price is None and self.trading_service:
            try:
                asset = asset_factory(db_position.symbol)
                if asset:
                    quote = await self.trading_service.get_quote(db_position.symbol)
                    current_price = quote.price if quote else db_position.avg_price
            except Exception:
                current_price = db_position.avg_price

        current_price = current_price or db_position.avg_price

        # Calculate unrealized P&L
        unrealized_pnl = (current_price - db_position.avg_price) * db_position.quantity

        # Create asset object
        asset = asset_factory(db_position.symbol)

        # Determine if it's an option and extract option fields safely
        option_type = None
        strike = None
        expiration_date = None
        underlying_symbol = None

        if asset and hasattr(asset, "option_type"):
            option_type = getattr(asset, "option_type", None)
            strike = getattr(asset, "strike", None)
            expiration_date = getattr(asset, "expiration", None)
            if hasattr(asset, "underlying") and asset.underlying:
                underlying_symbol = getattr(asset.underlying, "symbol", None)

        return Position(
            symbol=db_position.symbol,
            quantity=db_position.quantity,
            avg_price=db_position.avg_price,
            current_price=current_price,
            unrealized_pnl=unrealized_pnl,
            realized_pnl=0.0,  # Would need to calculate from trades
            asset=asset,
            # Options fields (if applicable)
            option_type=option_type,
            strike=strike,
            expiration_date=expiration_date,
            underlying_symbol=underlying_symbol,
            # Greeks would be calculated separately by trading service
            delta=None,
            gamma=None,
            theta=None,
            vega=None,
            rho=None,
            iv=None,
        )

    def to_schema_sync(
        self, db_position: DBPosition, current_price: float | None = None
    ) -> Position:
        """
        Synchronous version of to_schema for testing.

        Args:
            db_position: Database position model
            current_price: Optional current market price

        Returns:
            Position API schema with calculated fields
        """
        current_price = current_price or db_position.avg_price

        # Calculate unrealized P&L
        unrealized_pnl = (current_price - db_position.avg_price) * db_position.quantity

        # Create asset object
        asset = asset_factory(db_position.symbol)

        # Determine if it's an option and extract option fields safely
        option_type = None
        strike = None
        expiration_date = None
        underlying_symbol = None

        if asset and hasattr(asset, "option_type"):
            option_type = getattr(asset, "option_type", None)
            strike = getattr(asset, "strike", None)
            expiration_date = getattr(asset, "expiration", None)
            if hasattr(asset, "underlying") and asset.underlying:
                underlying_symbol = getattr(asset.underlying, "symbol", None)

        return Position(
            symbol=db_position.symbol,
            quantity=db_position.quantity,
            avg_price=db_position.avg_price,
            current_price=current_price,
            unrealized_pnl=unrealized_pnl,
            realized_pnl=0.0,  # Would need to calculate from trades
            asset=asset,
            # Options fields (if applicable)
            option_type=option_type,
            strike=strike,
            expiration_date=expiration_date,
            underlying_symbol=underlying_symbol,
            # Greeks would be calculated separately by trading service
            delta=None,
            gamma=None,
            theta=None,
            vega=None,
            rho=None,
            iv=None,
        )

    def to_database(self, position: Position, **kwargs) -> DBPosition:
        """
        Convert Position schema to DBPosition.

        Args:
            position: Position API schema
            account_id: Required account ID not in schema

        Returns:
            Database position model
        """
        account_id = kwargs.get("account_id")
        if not account_id:
            raise ConversionError("account_id is required for position conversion")

        return DBPosition(
            account_id=account_id,
            symbol=position.symbol,
            quantity=position.quantity,
            avg_price=position.avg_price,
        )


class ConversionError(Exception):
    """Error during schema-database conversion."""

    pass


# Convenience functions for direct usage
async def db_account_to_schema(
    db_account: DBAccount, trading_service: Optional["TradingService"] = None
) -> Account:
    """Convert database account to schema."""
    converter = AccountConverter(trading_service)
    return await converter.to_schema(db_account)


def schema_account_to_db(account: Account) -> DBAccount:
    """Convert schema account to database model."""
    converter = AccountConverter()
    return converter.to_database(account)


async def db_order_to_schema(db_order: DBOrder) -> Order:
    """Convert database order to schema."""
    converter = OrderConverter()
    return await converter.to_schema(db_order)


def schema_order_to_db(order: Order, account_id: str) -> DBOrder:
    """Convert schema order to database model."""
    converter = OrderConverter()
    return converter.to_database(order, account_id=account_id)


async def db_position_to_schema(
    db_position: DBPosition,
    trading_service: Optional["TradingService"] = None,
    current_price: float | None = None,
) -> Position:
    """Convert database position to schema."""
    converter = PositionConverter(trading_service)
    return await converter.to_schema(db_position, current_price)


def schema_position_to_db(position: Position, account_id: str) -> DBPosition:
    """Convert schema position to database model."""
    converter = PositionConverter()
    return converter.to_database(position, account_id=account_id)
