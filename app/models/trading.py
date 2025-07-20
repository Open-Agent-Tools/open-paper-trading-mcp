"""
Trading models and business logic.

DEPRECATED: This module is deprecated as of Phase 4 implementation.

This module now serves as a compatibility layer and re-exports schemas
from the dedicated schema modules. This maintains backwards compatibility
while establishing proper separation between API schemas and business logic.

For new code, import directly from app.schemas.* modules:
- from app.schemas.orders import Order, OrderLeg, MultiLegOrder
- from app.schemas.positions import Position, Portfolio
- from app.schemas.accounts import Account
- from app.schemas.trading import StockQuote
"""

import warnings

# Issue deprecation warning when this module is imported
warnings.warn(
    "app.models.trading is deprecated. Use direct imports from app.schemas.* instead. "
    "For example: 'from app.schemas.orders import Order' instead of 'from app.models.trading import Order'",
    DeprecationWarning,
    stacklevel=2,
)

# Re-export schemas for backwards compatibility
from app.schemas.orders import (
    MultiLegOrder,
    MultiLegOrderCreate,
    Order,
    OrderCondition,
    OrderCreate,
    OrderLeg,
    OrderLegCreate,
    OrderSide,
    OrderStatus,
    OrderType,
)
from app.schemas.positions import (
    Portfolio,
    PortfolioSummary,
    Position,
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
