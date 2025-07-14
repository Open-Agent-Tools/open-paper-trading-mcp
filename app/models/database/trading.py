import uuid
from sqlalchemy import Column, String, Float, DateTime, ForeignKey, Integer, Enum
from sqlalchemy.orm import relationship, Mapped
from sqlalchemy.sql import func
from app.models.database.base import Base
from app.models.trading import OrderStatus, OrderType


class Account(Base):
    __tablename__ = "accounts"
    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    owner = Column(String, index=True, unique=True, nullable=False)
    cash_balance = Column(Float, nullable=False, default=100000.0)
    created_at = Column(DateTime, server_default=func.now())

    positions = relationship("Position", back_populates="account")
    orders = relationship("Order", back_populates="account")
    transactions = relationship("Transaction", back_populates="account")


class Position(Base):
    __tablename__ = "positions"
    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    account_id = Column(String, ForeignKey("accounts.id"), nullable=False)
    symbol = Column(String, index=True, nullable=False)
    quantity = Column(Integer, nullable=False)
    avg_price = Column(Float, nullable=False)

    account = relationship("Account", back_populates="positions")


class Order(Base):
    __tablename__ = "orders"
    id = Column(
        String, primary_key=True, default=lambda: f"order_{uuid.uuid4().hex[:8]}"
    )
    account_id = Column(String, ForeignKey("accounts.id"), nullable=False)
    symbol = Column(String, index=True, nullable=False)
    order_type: Mapped[OrderType] = Column(Enum(OrderType), nullable=False)
    quantity = Column(Integer, nullable=False)
    price = Column(Float, nullable=True)  # Null for market orders
    status: Mapped[OrderStatus] = Column(Enum(OrderStatus), nullable=False, default=OrderStatus.PENDING)
    created_at = Column(DateTime, server_default=func.now())
    filled_at = Column(DateTime, nullable=True)

    account = relationship("Account", back_populates="orders")


class Transaction(Base):
    __tablename__ = "transactions"
    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    account_id = Column(String, ForeignKey("accounts.id"), nullable=False)
    order_id = Column(String, ForeignKey("orders.id"), nullable=True)
    symbol = Column(String, index=True, nullable=False)
    quantity = Column(Integer, nullable=False)
    price = Column(Float, nullable=False)
    transaction_type: Mapped[OrderType] = Column(Enum(OrderType), nullable=False)
    timestamp = Column(DateTime, server_default=func.now())

    account = relationship("Account", back_populates="transactions")
