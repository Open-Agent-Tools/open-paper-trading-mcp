import uuid
from datetime import datetime
from typing import TYPE_CHECKING

from sqlalchemy import (
    JSON,
    BigInteger,
    Boolean,
    Column,
    Date,
    DateTime,
    Enum,
    Float,
    ForeignKey,
    Index,
    Integer,
    Numeric,
    String,
    Text,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy.sql import func

from app.core.id_utils import generate_account_id
from app.models.database.base import Base
from app.schemas.orders import OrderCondition, OrderStatus, OrderType

if TYPE_CHECKING:
    # Import type annotations to avoid circular imports during runtime
    pass


class User(Base):
    __tablename__ = "users"

    id: Mapped[str] = mapped_column(
        String(36), primary_key=True, default=lambda: str(uuid.uuid4())
    )
    username: Mapped[str] = mapped_column(String(100), unique=True, index=True)
    email: Mapped[str] = mapped_column(String(255), unique=True, index=True)
    first_name: Mapped[str] = mapped_column(String(100))
    last_name: Mapped[str] = mapped_column(String(100))
    phone: Mapped[str | None] = mapped_column(String(20), nullable=True)
    date_of_birth: Mapped[Date | None] = mapped_column(Date, nullable=True)

    # Account metadata
    is_verified: Mapped[bool] = mapped_column(Boolean, default=False)
    verification_status: Mapped[str] = mapped_column(
        String(50), default="pending"
    )  # pending, verified, rejected
    account_tier: Mapped[str] = mapped_column(
        String(50), default="basic"
    )  # basic, premium, professional

    # Profile settings (JSON for flexibility)
    profile_settings: Mapped[dict] = mapped_column(JSON, default=dict)
    preferences: Mapped[dict] = mapped_column(JSON, default=dict)

    # Timestamps
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, server_default=func.now(), onupdate=func.now()
    )
    last_login_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)

    # Relationships
    accounts: Mapped[list["Account"]] = relationship("Account", back_populates="user")


class Account(Base):
    __tablename__ = "accounts"

    id: Mapped[str] = mapped_column(
        String(10), primary_key=True, default=generate_account_id
    )
    user_id: Mapped[str | None] = mapped_column(
        String(36), ForeignKey("users.id"), index=True, nullable=True
    )
    owner: Mapped[str] = mapped_column(
        String, index=True
    )  # Keep for backward compatibility
    cash_balance: Mapped[float] = mapped_column(Float, default=10000.0)
    starting_balance: Mapped[float] = mapped_column(Float, default=10000.0)
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, server_default=func.now(), onupdate=func.now()
    )

    # Relationships
    user: Mapped["User | None"] = relationship("User", back_populates="accounts")
    positions: Mapped[list["Position"]] = relationship(
        "Position", back_populates="account"
    )
    orders: Mapped[list["Order"]] = relationship("Order", back_populates="account")
    transactions: Mapped[list["Transaction"]] = relationship(
        "Transaction", back_populates="account"
    )
    multi_leg_orders: Mapped[list["MultiLegOrder"]] = relationship(
        "MultiLegOrder", back_populates="account"
    )
    recognized_strategies: Mapped[list["RecognizedStrategy"]] = relationship(
        "RecognizedStrategy", back_populates="account"
    )
    greeks_snapshots: Mapped[list["PortfolioGreeksSnapshot"]] = relationship(
        "PortfolioGreeksSnapshot", back_populates="account"
    )


class Position(Base):
    __tablename__ = "positions"

    id: Mapped[str] = mapped_column(
        String, primary_key=True, default=lambda: str(uuid.uuid4())
    )
    account_id: Mapped[str] = mapped_column(String(10), ForeignKey("accounts.id"))
    symbol: Mapped[str] = mapped_column(String, index=True)
    quantity: Mapped[int] = mapped_column(Integer)
    avg_price: Mapped[float] = mapped_column(Float)

    # Relationships
    account: Mapped["Account"] = relationship("Account", back_populates="positions")


class Order(Base):
    __tablename__ = "orders"

    id: Mapped[str] = mapped_column(
        String, primary_key=True, default=lambda: f"order_{uuid.uuid4().hex[:8]}"
    )
    account_id: Mapped[str] = mapped_column(String(10), ForeignKey("accounts.id"))
    symbol: Mapped[str] = mapped_column(String, index=True)
    order_type: Mapped[OrderType] = mapped_column(Enum(OrderType))
    quantity: Mapped[int] = mapped_column(Integer)
    price: Mapped[float | None] = mapped_column(
        Float, nullable=True
    )  # Null for market orders
    status: Mapped[OrderStatus] = mapped_column(
        Enum(OrderStatus), default=OrderStatus.PENDING
    )
    created_at: Mapped[DateTime] = mapped_column(DateTime, server_default=func.now())
    filled_at: Mapped[DateTime | None] = mapped_column(DateTime, nullable=True)

    # Advanced order trigger fields
    stop_price: Mapped[float | None] = mapped_column(Float, nullable=True)
    trail_percent: Mapped[float | None] = mapped_column(Float, nullable=True)
    trail_amount: Mapped[float | None] = mapped_column(Float, nullable=True)
    triggered_at: Mapped[DateTime | None] = mapped_column(DateTime, nullable=True)

    # Additional order fields
    condition: Mapped[OrderCondition | None] = mapped_column(
        Enum(OrderCondition), nullable=True
    )
    net_price: Mapped[float | None] = mapped_column(Float, nullable=True)

    # Relationships
    account: Mapped["Account"] = relationship("Account", back_populates="orders")


class Transaction(Base):
    __tablename__ = "transactions"

    id: Mapped[str] = mapped_column(
        String, primary_key=True, default=lambda: str(uuid.uuid4())
    )
    account_id: Mapped[str] = mapped_column(String(10), ForeignKey("accounts.id"))
    order_id: Mapped[str | None] = mapped_column(
        String, ForeignKey("orders.id"), nullable=True
    )
    symbol: Mapped[str] = mapped_column(String, index=True)
    quantity: Mapped[int] = mapped_column(Integer)
    price: Mapped[float] = mapped_column(Float)
    transaction_type: Mapped[OrderType] = mapped_column(Enum(OrderType))
    timestamp: Mapped[DateTime] = mapped_column(DateTime, server_default=func.now())

    # Relationships
    account: Mapped["Account"] = relationship("Account", back_populates="transactions")


# ============================================================================
# OPTIONS-SPECIFIC TABLES (Phase 4)
# ============================================================================


class OptionQuoteHistory(Base):
    """Historical option quotes with Greeks data."""

    __tablename__ = "option_quotes"

    id: Mapped[str] = mapped_column(
        String, primary_key=True, default=lambda: str(uuid.uuid4())
    )
    symbol: Mapped[str] = mapped_column(String, index=True)
    underlying_symbol: Mapped[str] = mapped_column(String, index=True)

    # Option details
    strike: Mapped[float] = mapped_column(Float)
    expiration_date: Mapped[Date] = mapped_column(Date, index=True)
    option_type: Mapped[str] = mapped_column(String)  # 'call' or 'put'

    # Quote data
    bid: Mapped[float | None] = mapped_column(Float, nullable=True)
    ask: Mapped[float | None] = mapped_column(Float, nullable=True)
    price: Mapped[float] = mapped_column(Float)
    volume: Mapped[int | None] = mapped_column(Integer, nullable=True)
    open_interest: Mapped[int | None] = mapped_column(Integer, nullable=True)

    # Greeks
    delta: Mapped[float | None] = mapped_column(Float, nullable=True)
    gamma: Mapped[float | None] = mapped_column(Float, nullable=True)
    theta: Mapped[float | None] = mapped_column(Float, nullable=True)
    vega: Mapped[float | None] = mapped_column(Float, nullable=True)
    rho: Mapped[float | None] = mapped_column(Float, nullable=True)

    # Advanced Greeks
    charm: Mapped[float | None] = mapped_column(Float, nullable=True)
    vanna: Mapped[float | None] = mapped_column(Float, nullable=True)
    speed: Mapped[float | None] = mapped_column(Float, nullable=True)
    zomma: Mapped[float | None] = mapped_column(Float, nullable=True)
    color: Mapped[float | None] = mapped_column(Float, nullable=True)

    # Market data
    implied_volatility: Mapped[float | None] = mapped_column(Float, nullable=True)
    underlying_price: Mapped[float | None] = mapped_column(Float, nullable=True)
    quote_time: Mapped[DateTime] = mapped_column(DateTime, index=True)

    # Test scenario field for Phase 3
    test_scenario: Mapped[str | None] = mapped_column(
        String(50), nullable=True, index=True
    )

    created_at: Mapped[DateTime] = mapped_column(DateTime, server_default=func.now())


class DevStockQuote(Base):
    """Test stock quote data for development and testing."""

    __tablename__ = "test_stock_quotes"

    id: Mapped[str] = mapped_column(
        String, primary_key=True, default=lambda: str(uuid.uuid4())
    )
    symbol: Mapped[str] = mapped_column(String(10), nullable=False, index=True)
    quote_date: Mapped[Date] = mapped_column(Date, nullable=False, index=True)
    bid: Mapped[float | None] = mapped_column(Numeric(10, 4), nullable=True)
    ask: Mapped[float | None] = mapped_column(Numeric(10, 4), nullable=True)
    price: Mapped[float | None] = mapped_column(Numeric(10, 4), nullable=True)
    volume: Mapped[int | None] = mapped_column(BigInteger, nullable=True)
    scenario: Mapped[str | None] = mapped_column(String(50), nullable=True, index=True)
    created_at: Mapped[DateTime] = mapped_column(DateTime, server_default=func.now())

    # Composite indexes for efficient queries
    __table_args__ = (
        Index("idx_test_stock_symbol_date", "symbol", "quote_date"),
        Index("idx_test_stock_scenario", "scenario", "quote_date"),
    )


class DevOptionQuote(Base):
    """Test option quote data for development and testing."""

    __tablename__ = "test_option_quotes"

    id: Mapped[str] = mapped_column(
        String, primary_key=True, default=lambda: str(uuid.uuid4())
    )
    symbol: Mapped[str] = mapped_column(String(20), nullable=False, index=True)
    underlying: Mapped[str] = mapped_column(String(10), nullable=False, index=True)
    expiration: Mapped[Date] = mapped_column(Date, nullable=False)
    strike: Mapped[float] = mapped_column(Numeric(10, 2), nullable=False)
    option_type: Mapped[str] = mapped_column(
        String(4), nullable=False
    )  # 'call' or 'put'
    quote_date: Mapped[Date] = mapped_column(Date, nullable=False, index=True)
    bid: Mapped[float | None] = mapped_column(Numeric(10, 4), nullable=True)
    ask: Mapped[float | None] = mapped_column(Numeric(10, 4), nullable=True)
    price: Mapped[float | None] = mapped_column(Numeric(10, 4), nullable=True)
    volume: Mapped[int | None] = mapped_column(BigInteger, nullable=True)
    scenario: Mapped[str | None] = mapped_column(String(50), nullable=True, index=True)
    created_at: Mapped[DateTime] = mapped_column(DateTime, server_default=func.now())

    # Composite indexes for efficient queries
    __table_args__ = (
        Index("idx_test_option_symbol_date", "symbol", "quote_date"),
        Index("idx_test_option_underlying_date", "underlying", "quote_date"),
        Index("idx_test_option_scenario", "scenario", "quote_date"),
        Index("idx_test_option_expiry_strike", "expiration", "strike"),
    )


class DevScenario(Base):
    """Test scenarios for managing different test datasets."""

    __tablename__ = "test_scenarios"

    id: Mapped[str] = mapped_column(
        String, primary_key=True, default=lambda: str(uuid.uuid4())
    )
    name: Mapped[str] = mapped_column(String(100), nullable=False, unique=True)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    start_date: Mapped[Date] = mapped_column(Date, nullable=False)
    end_date: Mapped[Date] = mapped_column(Date, nullable=False)
    symbols: Mapped[list[str]] = mapped_column(JSON, nullable=False)
    market_condition: Mapped[str | None] = mapped_column(
        String(20), nullable=True
    )  # 'volatile', 'calm', 'trending'
    created_at: Mapped[DateTime] = mapped_column(DateTime, server_default=func.now())

    # Add index for efficient scenario queries
    __table_args__ = (Index("idx_test_scenario_dates", "start_date", "end_date"),)


class MultiLegOrder(Base):
    """Multi-leg options orders (spreads, combinations)."""

    __tablename__ = "multi_leg_orders"

    id: Mapped[str] = mapped_column(
        String, primary_key=True, default=lambda: f"mlo_{uuid.uuid4().hex[:8]}"
    )
    account_id: Mapped[str] = mapped_column(String(10), ForeignKey("accounts.id"))

    # Order details
    order_type: Mapped[str] = mapped_column(String, default="limit")  # limit, market
    net_price: Mapped[float | None] = mapped_column(Float, nullable=True)
    status: Mapped[OrderStatus] = mapped_column(
        Enum(OrderStatus), default=OrderStatus.PENDING
    )

    # Strategy identification
    strategy_type: Mapped[str | None] = mapped_column(
        String, nullable=True
    )  # spread, straddle, etc.
    underlying_symbol: Mapped[str | None] = mapped_column(
        String, nullable=True, index=True
    )

    # Metadata
    created_at: Mapped[DateTime] = mapped_column(DateTime, server_default=func.now())
    filled_at: Mapped[DateTime | None] = mapped_column(DateTime, nullable=True)

    # Relationships
    account: Mapped["Account"] = relationship(
        "Account", back_populates="multi_leg_orders"
    )
    legs: Mapped[list["OrderLeg"]] = relationship(
        "OrderLeg", back_populates="multi_leg_order", cascade="all, delete-orphan"
    )


class OrderLeg(Base):
    """Individual legs of multi-leg orders."""

    __tablename__ = "order_legs"

    id: Mapped[str] = mapped_column(
        String, primary_key=True, default=lambda: str(uuid.uuid4())
    )
    multi_leg_order_id: Mapped[str] = mapped_column(
        String, ForeignKey("multi_leg_orders.id")
    )

    # Asset details
    symbol: Mapped[str] = mapped_column(String, index=True)
    asset_type: Mapped[str] = mapped_column(String)  # 'stock' or 'option'

    # Order details
    quantity: Mapped[int] = mapped_column(Integer)
    order_type: Mapped[OrderType] = mapped_column(Enum(OrderType))
    price: Mapped[float | None] = mapped_column(Float, nullable=True)

    # Option-specific fields (null for stocks)
    strike: Mapped[float | None] = mapped_column(Float, nullable=True)
    expiration_date: Mapped[Date | None] = mapped_column(Date, nullable=True)
    option_type: Mapped[str | None] = mapped_column(
        String, nullable=True
    )  # 'call' or 'put'
    underlying_symbol: Mapped[str | None] = mapped_column(String, nullable=True)

    # Execution details
    filled_quantity: Mapped[int] = mapped_column(Integer, default=0)
    filled_price: Mapped[float | None] = mapped_column(Float, nullable=True)

    # Relationships
    multi_leg_order: Mapped["MultiLegOrder"] = relationship(
        "MultiLegOrder", back_populates="legs"
    )


class RecognizedStrategy(Base):
    """Detected trading strategies in portfolios."""

    __tablename__ = "recognized_strategies"

    id: Mapped[str] = mapped_column(
        String, primary_key=True, default=lambda: str(uuid.uuid4())
    )
    account_id: Mapped[str] = mapped_column(String(10), ForeignKey("accounts.id"))

    # Strategy details
    strategy_type: Mapped[str] = mapped_column(String)  # spread, covered_call, etc.
    strategy_name: Mapped[str] = mapped_column(String)
    underlying_symbol: Mapped[str] = mapped_column(String, index=True)

    # Financial metrics
    cost_basis: Mapped[float] = mapped_column(Float, default=0.0)
    max_profit: Mapped[float | None] = mapped_column(Float, nullable=True)
    max_loss: Mapped[float | None] = mapped_column(Float, nullable=True)
    breakeven_points: Mapped[str | None] = mapped_column(
        JSON, nullable=True
    )  # List of breakeven prices

    # Risk metrics
    # net_delta: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    # net_gamma: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    # net_theta: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    # net_vega: Mapped[Optional[float]] = mapped_column(Float, nullable=True)

    # Position tracking
    position_ids: Mapped[str] = mapped_column(JSON)  # List of position IDs in strategy
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)

    # Metadata
    detected_at: Mapped[DateTime] = mapped_column(DateTime, server_default=func.now())
    last_updated: Mapped[DateTime] = mapped_column(
        DateTime, server_default=func.now(), onupdate=func.now()
    )

    # Relationships
    account = relationship("Account", back_populates="recognized_strategies")
    performance_records = relationship(
        "StrategyPerformance", back_populates="strategy", cascade="all, delete-orphan"
    )


class OptionExpiration(Base):
    """Option expiration tracking and processing."""

    __tablename__ = "option_expirations"

    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))

    # Expiration details
    underlying_symbol = Column(String, nullable=False, index=True)
    expiration_date = Column(Date, nullable=False, index=True)

    # Processing status
    is_processed = Column(Boolean, nullable=False, default=False)
    processed_at = Column(DateTime, nullable=True)
    processing_mode = Column(String, nullable=True)  # 'automatic', 'manual'

    # Results
    expired_positions_count = Column(Integer, nullable=False, default=0)
    assignments_count = Column(Integer, nullable=False, default=0)
    exercises_count = Column(Integer, nullable=False, default=0)
    worthless_count = Column(Integer, nullable=False, default=0)

    # Financial impact
    total_cash_impact = Column(Float, nullable=False, default=0.0)
    fees_charged = Column(Float, nullable=False, default=0.0)

    # Metadata
    created_at = Column(DateTime, server_default=func.now())
    notes = Column(Text, nullable=True)


class PortfolioGreeksSnapshot(Base):
    """Daily snapshots of portfolio Greeks exposure."""

    __tablename__ = "portfolio_greeks_snapshots"

    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    account_id = Column(String, ForeignKey("accounts.id"), nullable=False)

    # Snapshot details
    snapshot_date = Column(Date, nullable=False, index=True)
    snapshot_time = Column(DateTime, nullable=False)

    # Portfolio Greeks
    total_delta = Column(Float, nullable=False, default=0.0)
    total_gamma = Column(Float, nullable=False, default=0.0)
    total_theta = Column(Float, nullable=False, default=0.0)
    total_vega = Column(Float, nullable=False, default=0.0)
    total_rho = Column(Float, nullable=False, default=0.0)

    # Normalized Greeks (per $1000 invested)
    delta_normalized = Column(Float, nullable=False, default=0.0)
    gamma_normalized = Column(Float, nullable=False, default=0.0)
    theta_normalized = Column(Float, nullable=False, default=0.0)
    vega_normalized = Column(Float, nullable=False, default=0.0)

    # Dollar Greeks
    delta_dollars = Column(Float, nullable=False, default=0.0)
    gamma_dollars = Column(Float, nullable=False, default=0.0)
    theta_dollars = Column(Float, nullable=False, default=0.0)

    # Portfolio metrics
    total_portfolio_value = Column(Float, nullable=False, default=0.0)
    options_value = Column(Float, nullable=False, default=0.0)
    stocks_value = Column(Float, nullable=False, default=0.0)

    # Relationships
    account = relationship("Account", back_populates="greeks_snapshots")


class StrategyPerformance(Base):
    """Performance tracking for recognized strategies."""

    __tablename__ = "strategy_performance"

    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    strategy_id = Column(String, ForeignKey("recognized_strategies.id"), nullable=False)

    # Performance metrics
    unrealized_pnl = Column(Float, nullable=False, default=0.0)
    realized_pnl = Column(Float, nullable=False, default=0.0)
    total_pnl = Column(Float, nullable=False, default=0.0)
    pnl_percent = Column(Float, nullable=False, default=0.0)

    # Market value tracking
    current_market_value = Column(Float, nullable=False, default=0.0)
    cost_basis = Column(Float, nullable=False, default=0.0)

    # Time-based metrics
    days_held = Column(Integer, nullable=False, default=0)
    annualized_return = Column(Float, nullable=True)

    # Risk metrics
    # max_drawdown: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    # sharpe_ratio: Mapped[Optional[float]] = mapped_column(Float, nullable=True)

    # Greeks at measurement time
    delta_exposure = Column(Float, nullable=True)
    theta_decay = Column(Float, nullable=True)
    vega_exposure = Column(Float, nullable=True)

    # Measurement details
    measured_at = Column(DateTime, nullable=False, index=True)
    underlying_price = Column(Float, nullable=True)

    # Relationships
    strategy = relationship("RecognizedStrategy", back_populates="performance_records")


# ============================================================================
# DATABASE INDEXES FOR PERFORMANCE OPTIMIZATION
# ============================================================================

# Composite indexes for common query patterns
Index("idx_positions_account_symbol", Position.account_id, Position.symbol)
Index("idx_orders_account_status", Order.account_id, Order.status)
Index("idx_orders_account_created", Order.account_id, Order.created_at)
Index(
    "idx_transactions_account_timestamp", Transaction.account_id, Transaction.timestamp
)

# Advanced order management indexes for performance optimization
# Query patterns for order execution engine
Index("idx_orders_status_type", Order.status, Order.order_type)
Index("idx_orders_status_created", Order.status, Order.created_at)
Index("idx_orders_symbol_status", Order.symbol, Order.status)
Index("idx_orders_symbol_type", Order.symbol, Order.order_type)

# Trigger-based order indexes for monitoring
Index("idx_orders_stop_price", Order.stop_price)
Index("idx_orders_triggered_at", Order.triggered_at)
Index(
    "idx_orders_trigger_fields",
    Order.stop_price,
    Order.trail_percent,
    Order.trail_amount,
)

# Order queue processing indexes
Index(
    "idx_orders_status_created_type", Order.status, Order.created_at, Order.order_type
)
Index("idx_orders_account_status_symbol", Order.account_id, Order.status, Order.symbol)

# Time-based order queries for lifecycle management
Index("idx_orders_created_status", Order.created_at, Order.status)
Index("idx_orders_filled_at", Order.filled_at)
Index("idx_orders_created_filled", Order.created_at, Order.filled_at)

# Symbol-based order analysis
Index("idx_orders_symbol_created", Order.symbol, Order.created_at)
Index("idx_orders_symbol_filled", Order.symbol, Order.filled_at)

# Performance monitoring indexes
Index(
    "idx_orders_account_created_status",
    Order.account_id,
    Order.created_at,
    Order.status,
)
Index(
    "idx_orders_type_status_created", Order.order_type, Order.status, Order.created_at
)

# Options-specific indexes
Index(
    "idx_option_quotes_symbol_time",
    OptionQuoteHistory.symbol,
    OptionQuoteHistory.quote_time,
)
Index(
    "idx_option_quotes_underlying_expiry",
    OptionQuoteHistory.underlying_symbol,
    OptionQuoteHistory.expiration_date,
)
Index(
    "idx_option_quotes_expiry_type",
    OptionQuoteHistory.expiration_date,
    OptionQuoteHistory.option_type,
)
Index(
    "idx_option_quotes_strike_expiry",
    OptionQuoteHistory.strike,
    OptionQuoteHistory.expiration_date,
)

# Multi-leg order indexes
Index(
    "idx_multi_leg_orders_account_status",
    MultiLegOrder.account_id,
    MultiLegOrder.status,
)
Index(
    "idx_multi_leg_orders_underlying_created",
    MultiLegOrder.underlying_symbol,
    MultiLegOrder.created_at,
)
Index("idx_order_legs_symbol_type", OrderLeg.symbol, OrderLeg.asset_type)
Index(
    "idx_order_legs_underlying_expiry",
    OrderLeg.underlying_symbol,
    OrderLeg.expiration_date,
)

# Strategy tracking indexes
Index(
    "idx_strategies_account_type",
    RecognizedStrategy.account_id,
    RecognizedStrategy.strategy_type,
)
Index(
    "idx_strategies_underlying_active",
    RecognizedStrategy.underlying_symbol,
    RecognizedStrategy.is_active,
)
Index(
    "idx_strategies_account_updated",
    RecognizedStrategy.account_id,
    RecognizedStrategy.last_updated,
)

# Performance tracking indexes
Index(
    "idx_performance_strategy_measured",
    StrategyPerformance.strategy_id,
    StrategyPerformance.measured_at,
)
Index(
    "idx_performance_measured_pnl",
    StrategyPerformance.measured_at,
    StrategyPerformance.total_pnl,
)

# Greeks snapshots indexes
Index(
    "idx_greeks_account_date",
    PortfolioGreeksSnapshot.account_id,
    PortfolioGreeksSnapshot.snapshot_date,
)
Index(
    "idx_greeks_date_time",
    PortfolioGreeksSnapshot.snapshot_date,
    PortfolioGreeksSnapshot.snapshot_time,
)

# Option expiration indexes
Index(
    "idx_expiry_date_processed",
    OptionExpiration.expiration_date,
    OptionExpiration.is_processed,
)
Index(
    "idx_expiry_underlying_date",
    OptionExpiration.underlying_symbol,
    OptionExpiration.expiration_date,
)

# Test data indexes
Index(
    "idx_test_stock_symbol_date_scenario",
    DevStockQuote.symbol,
    DevStockQuote.quote_date,
    DevStockQuote.scenario,
)
Index(
    "idx_test_option_underlying_expiry_scenario",
    DevOptionQuote.underlying,
    DevOptionQuote.expiration,
    DevOptionQuote.scenario,
)
