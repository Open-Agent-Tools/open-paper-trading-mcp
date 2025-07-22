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
from .accounts import Account
from .orders import (MultiLegOrder, MultiLegOrderCreate, Order, OrderCondition,
                     OrderCreate, OrderLeg, OrderLegCreate, OrderSide,
                     OrderStatus, OrderType)
from .positions import Portfolio, PortfolioSummary, Position
from .trading import StockQuote

__all__ = [
    # Account schemas
    "Account",
    "MultiLegOrder",
    "MultiLegOrderCreate",
    "Order",
    "OrderCondition",
    "OrderCreate",
    "OrderLeg",
    "OrderLegCreate",
    "OrderSide",
    "OrderStatus",
    # Order schemas
    "OrderType",
    "Portfolio",
    "PortfolioSummary",
    # Position schemas
    "Position",
    # Trading schemas
    "StockQuote",
]
