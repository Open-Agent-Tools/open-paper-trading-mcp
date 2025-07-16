"""
API Schemas Package

This package contains all Pydantic models used for API request/response validation.
These are separate from database models to maintain clear separation of concerns:

- Schemas: API request/response validation and serialization (this package)
- Models: Database entities and business logic (app/models/)

Organization:
- orders.py: Order-related schemas (Order, OrderLeg, MultiLegOrder, etc.)
- positions.py: Position and portfolio schemas
- accounts.py: Account management schemas
- trading.py: General trading schemas (quotes, assets, etc.)
"""

# Export all schemas for easy access
from .orders import (
    OrderType,
    OrderStatus,
    OrderCondition,
    OrderSide,
    OrderLeg,
    Order,
    MultiLegOrder,
    OrderCreate,
    OrderLegCreate,
    MultiLegOrderCreate,
)

from .positions import (
    Position,
    Portfolio,
    PortfolioSummary,
)

from .accounts import (
    Account,
)

from .trading import (
    StockQuote,
)

__all__ = [
    # Order schemas
    "OrderType",
    "OrderStatus",
    "OrderCondition",
    "OrderSide",
    "OrderLeg",
    "Order",
    "MultiLegOrder",
    "OrderCreate",
    "OrderLegCreate",
    "MultiLegOrderCreate",
    # Position schemas
    "Position",
    "Portfolio",
    "PortfolioSummary",
    # Account schemas
    "Account",
    # Trading schemas
    "StockQuote",
]
