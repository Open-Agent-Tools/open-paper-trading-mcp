"""
Trading models and business logic.

This module now serves as a compatibility layer and re-exports schemas
from the dedicated schema modules. This maintains backwards compatibility
while establishing proper separation between API schemas and business logic.

For new code, import directly from app.schemas.* modules.
"""

# Re-export schemas for backwards compatibility
from app.schemas.orders import (
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

from app.schemas.positions import (
    Position,
    Portfolio,
    PortfolioSummary,
)

from app.schemas.trading import (
    StockQuote,
)

# Keep imports available for backwards compatibility
__all__ = [
    # Order types and enums
    "OrderType",
    "OrderStatus",
    "OrderCondition",
    "OrderSide",
    # Order models
    "OrderLeg",
    "Order",
    "MultiLegOrder",
    "OrderCreate",
    "OrderLegCreate",
    "MultiLegOrderCreate",
    # Position models
    "Position",
    "Portfolio",
    "PortfolioSummary",
    # Trading models
    "StockQuote",
]
