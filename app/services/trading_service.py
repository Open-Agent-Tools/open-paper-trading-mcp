from datetime import datetime, date
from typing import List, Dict, Optional, Union, Any
from uuid import uuid4

from app.schemas.orders import Order, OrderCreate, OrderStatus
from app.models.trading import StockQuote, Position, Portfolio, PortfolioSummary
from app.models.assets import Option, asset_factory
from app.models.quotes import Quote, OptionQuote, OptionsChain
from app.core.exceptions import NotFoundError

# Import new services
from .order_execution import OrderExecutionEngine
from .validation import AccountValidator
from .strategies import StrategyRecognitionService
from .margin import MaintenanceMarginService
from .greeks import calculate_option_greeks
from ..adapters.test_data import TestDataQuoteAdapter


class TradingService:
    def __init__(self) -> None:
        # Legacy data (maintain compatibility)
        self.orders: List[Order] = []
        self.mock_quotes: Dict[str, StockQuote] = {
            "AAPL": StockQuote(
                symbol="AAPL",
                price=150.00,
                change=2.50,
                change_percent=1.69,
                volume=1000000,
                last_updated=datetime.now(),
            ),
            "GOOGL": StockQuote(
                symbol="GOOGL",
                price=2800.00,
                change=-15.00,
                change_percent=-0.53,
                volume=500000,
                last_updated=datetime.now(),
            ),
            "MSFT": StockQuote(
                symbol="MSFT",
                price=420.00,
                change=5.25,
                change_percent=1.27,
                volume=750000,
                last_updated=datetime.now(),
            ),
            "TSLA": StockQuote(
                symbol="TSLA",
                price=245.00,
                change=-8.50,
                change_percent=-3.36,
                volume=2000000,
                last_updated=datetime.now(),
            ),
        }
        self.portfolio_positions: List[Position] = [
            Position(
                symbol="AAPL",
                quantity=10,
                avg_price=145.00,
                current_price=150.00,
                unrealized_pnl=50.0,
            ),
            Position(
                symbol="GOOGL",
                quantity=2,
                avg_price=2850.00,
                current_price=2800.00,
                unrealized_pnl=-100.0,
            ),
        ]
        self.cash_balance = 10000.0

        # Enhanced services
        self.quote_adapter = TestDataQuoteAdapter()
        self.order_execution = OrderExecutionEngine()
        self.account_validation = AccountValidator()
        self.strategy_recognition = StrategyRecognitionService()
        self.margin_service = MaintenanceMarginService(self.quote_adapter)

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
            created_at=datetime.now(),
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
        total_invested = sum(
            pos.quantity * pos.current_price for pos in self.portfolio_positions
        )
        total_value = self.cash_balance + total_invested
        total_pnl = sum(pos.unrealized_pnl for pos in self.portfolio_positions)

        return Portfolio(
            cash_balance=self.cash_balance,
            total_value=total_value,
            positions=self.portfolio_positions,
            daily_pnl=total_pnl,
            total_pnl=total_pnl,
        )

    def get_portfolio_summary(self) -> PortfolioSummary:
        """Get portfolio summary."""
        invested_value = sum(
            pos.quantity * pos.current_price for pos in self.portfolio_positions
        )
        total_value = self.cash_balance + invested_value
        total_pnl = sum(pos.unrealized_pnl for pos in self.portfolio_positions)

        return PortfolioSummary(
            total_value=total_value,
            cash_balance=self.cash_balance,
            invested_value=invested_value,
            daily_pnl=total_pnl,
            daily_pnl_percent=(total_pnl / total_value) * 100 if total_value > 0 else 0,
            total_pnl=total_pnl,
            total_pnl_percent=(total_pnl / total_value) * 100 if total_value > 0 else 0,
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

    # Enhanced Options Trading Methods

    def get_enhanced_quote(
        self, symbol: str, underlying_price: Optional[float] = None
    ) -> Union[Quote, OptionQuote]:
        """Get enhanced quote with Greeks for options."""
        asset = asset_factory(symbol)

        # Try test data adapter first
        quote = self.quote_adapter.get_quote(asset)
        if quote:
            return quote

        # Fallback to legacy data for stocks
        if not isinstance(asset, Option) and symbol.upper() in self.mock_quotes:
            legacy_quote = self.mock_quotes[symbol.upper()]
            return Quote(
                asset=asset,
                quote_date=datetime.now(),
                price=legacy_quote.price,
                bid=legacy_quote.price - 0.01,
                ask=legacy_quote.price + 0.01,
                bid_size=100,
                ask_size=100,
                volume=legacy_quote.volume,
            )

        raise NotFoundError(f"No quote available for {symbol}")

    def get_options_chain(
        self, underlying: str, expiration_date: Optional[date] = None
    ) -> OptionsChain:
        """Get complete options chain for an underlying."""
        return self.quote_adapter.get_options_chain(underlying, expiration_date)

    def calculate_greeks(
        self, option_symbol: str, underlying_price: Optional[float] = None
    ) -> Dict[str, float]:
        """Calculate option Greeks."""
        option = asset_factory(option_symbol)
        if not isinstance(option, Option):
            raise ValueError(f"{option_symbol} is not an option")

        # Get quotes
        option_quote = self.get_enhanced_quote(option_symbol)
        if underlying_price is None:
            underlying_quote = self.get_enhanced_quote(option.underlying.symbol)
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

    def analyze_portfolio_strategies(self) -> Dict[str, Any]:
        """Analyze portfolio for trading strategies."""
        # Convert legacy positions to enhanced Position objects
        enhanced_positions = []
        for pos in self.portfolio_positions:
            # This is a simplified conversion - in real implementation would need proper Position model
            enhanced_positions.append(pos)

        strategies = self.strategy_recognition.group_positions_by_strategy(
            enhanced_positions
        )
        summary = self.strategy_recognition.get_strategy_summary(strategies)

        return {
            "strategies": [strategy.dict() for strategy in strategies],
            "summary": summary,
            "total_positions": len(enhanced_positions),
            "total_strategies": len(strategies),
        }

    def calculate_margin_requirement(self) -> Dict[str, Any]:
        """Calculate current portfolio margin requirement."""
        # Convert legacy positions to enhanced Position objects
        enhanced_positions = []
        for pos in self.portfolio_positions:
            enhanced_positions.append(pos)

        return self.margin_service.get_portfolio_margin_breakdown(
            enhanced_positions, self.quote_adapter
        )

    def validate_account_state(self) -> Dict[str, Any]:
        """Validate current account state."""
        # Mock account data for validation
        account_data = {
            "cash_balance": self.cash_balance,
            "positions": self.portfolio_positions,
            "orders": self.orders,
        }

        return self.account_validation.validate_account_state(account_data)

    def get_test_scenarios(self) -> Dict[str, Any]:
        """Get available test scenarios for development."""
        return self.quote_adapter.get_test_scenarios()

    def set_test_date(self, date_str: str):
        """Set test data date for historical scenarios."""
        self.quote_adapter.set_date(date_str)

    def get_available_symbols(self) -> List[str]:
        """Get all available symbols in test data."""
        return self.quote_adapter.get_available_symbols()

    def get_sample_data_info(self) -> Dict[str, Any]:
        """Get information about sample data."""
        return self.quote_adapter.get_sample_data_info()

    def get_expiration_dates(self, underlying: str) -> List[date]:
        """Get available expiration dates for an underlying symbol."""
        return self.quote_adapter.get_expiration_dates(underlying)

    def create_multi_leg_order(self, order_data) -> Order:
        """Create a multi-leg order."""
        # For now, create a simple order representation
        # In a real implementation, this would handle complex multi-leg orders
        order = Order(
            id=str(uuid4()),
            symbol=f"MULTI_LEG_{len(order_data.legs)}_LEGS",
            order_type=order_data.legs[0].order_type if order_data.legs else "buy",
            quantity=sum(leg.quantity for leg in order_data.legs),
            price=sum(leg.price or 0 for leg in order_data.legs if leg.price),
            status=OrderStatus.FILLED,
            created_at=datetime.now(),
            filled_at=datetime.now(),
        )
        self.orders.append(order)
        return order


# Global service instance
trading_service = TradingService()
