from datetime import datetime
from typing import List, Optional, Dict, Any
from uuid import uuid4

from app.models.trading import (
    Order, OrderCreate, OrderStatus, OrderType,
    StockQuote, Position, Portfolio, PortfolioSummary
)
from app.core.exceptions import NotFoundError, ValidationError


class TradingService:
    def __init__(self):
        self.orders: List[Order] = []
        self.mock_quotes: Dict[str, StockQuote] = {
            "AAPL": StockQuote(
                symbol="AAPL",
                price=150.00,
                change=2.50,
                change_percent=1.69,
                volume=1000000,
                last_updated=datetime.now()
            ),
            "GOOGL": StockQuote(
                symbol="GOOGL",
                price=2800.00,
                change=-15.00,
                change_percent=-0.53,
                volume=500000,
                last_updated=datetime.now()
            ),
            "MSFT": StockQuote(
                symbol="MSFT",
                price=420.00,
                change=5.25,
                change_percent=1.27,
                volume=750000,
                last_updated=datetime.now()
            ),
            "TSLA": StockQuote(
                symbol="TSLA",
                price=245.00,
                change=-8.50,
                change_percent=-3.36,
                volume=2000000,
                last_updated=datetime.now()
            )
        }
        self.portfolio_positions: List[Position] = [
            Position(
                symbol="AAPL",
                quantity=10,
                avg_price=145.00,
                current_price=150.00,
                unrealized_pnl=50.0
            ),
            Position(
                symbol="GOOGL",
                quantity=2,
                avg_price=2850.00,
                current_price=2800.00,
                unrealized_pnl=-100.0
            ),
        ]
        self.cash_balance = 10000.0

    def get_quote(self, symbol: str) -> StockQuote:
        """Get current stock quote for a symbol."""
        if symbol.upper() not in self.mock_quotes:
            raise NotFoundError(f"Symbol {symbol} not found")
        return self.mock_quotes[symbol.upper()]

    def create_order(self, order_data: OrderCreate) -> Order:
        """Create a new trading order."""
        # Validate symbol exists
        self.get_quote(order_data.symbol)
        
        new_order = Order(
            id=f"order_{uuid4().hex[:8]}",
            symbol=order_data.symbol.upper(),
            order_type=order_data.order_type,
            quantity=order_data.quantity,
            price=order_data.price,
            created_at=datetime.now()
        )
        
        self.orders.append(new_order)
        return new_order

    def get_orders(self) -> List[Order]:
        """Get all orders."""
        return self.orders

    def get_order(self, order_id: str) -> Order:
        """Get a specific order by ID."""
        for order in self.orders:
            if order.id == order_id:
                return order
        raise NotFoundError(f"Order {order_id} not found")

    def cancel_order(self, order_id: str) -> Dict[str, str]:
        """Cancel a specific order."""
        order = self.get_order(order_id)
        order.status = OrderStatus.CANCELLED
        return {"message": "Order cancelled successfully"}

    def get_portfolio(self) -> Portfolio:
        """Get complete portfolio information."""
        total_invested = sum(pos.quantity * pos.current_price for pos in self.portfolio_positions)
        total_value = self.cash_balance + total_invested
        total_pnl = sum(pos.unrealized_pnl for pos in self.portfolio_positions)
        
        return Portfolio(
            cash_balance=self.cash_balance,
            total_value=total_value,
            positions=self.portfolio_positions,
            daily_pnl=total_pnl,
            total_pnl=total_pnl
        )

    def get_portfolio_summary(self) -> PortfolioSummary:
        """Get portfolio summary."""
        invested_value = sum(pos.quantity * pos.current_price for pos in self.portfolio_positions)
        total_value = self.cash_balance + invested_value
        total_pnl = sum(pos.unrealized_pnl for pos in self.portfolio_positions)
        
        return PortfolioSummary(
            total_value=total_value,
            cash_balance=self.cash_balance,
            invested_value=invested_value,
            daily_pnl=total_pnl,
            daily_pnl_percent=(total_pnl / total_value) * 100 if total_value > 0 else 0,
            total_pnl=total_pnl,
            total_pnl_percent=(total_pnl / total_value) * 100 if total_value > 0 else 0
        )

    def get_positions(self) -> List[Position]:
        """Get all portfolio positions."""
        return self.portfolio_positions

    def get_position(self, symbol: str) -> Position:
        """Get a specific position by symbol."""
        for position in self.portfolio_positions:
            if position.symbol.upper() == symbol.upper():
                return position
        raise NotFoundError(f"Position for symbol {symbol} not found")


# Global service instance
trading_service = TradingService()