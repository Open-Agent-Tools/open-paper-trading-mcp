from datetime import datetime, date
from typing import List, Dict, Optional, Union, Any
from uuid import uuid4
from sqlalchemy.orm import Session

from app.schemas.orders import (
    Order,
    OrderCreate,
    OrderStatus,
    OrderCondition,
    OrderType,
)
from app.models.trading import StockQuote, Position, Portfolio, PortfolioSummary
from app.models.assets import Option, asset_factory
from app.models.quotes import Quote, OptionQuote, OptionsChain
from app.core.exceptions import NotFoundError

# Database imports
from app.storage.database import SessionLocal
from app.models.database.trading import (
    Account as DBAccount,
    Position as DBPosition,
    Order as DBOrder,
)

# Import new services
from .order_execution import OrderExecutionEngine
from .validation import AccountValidator
from .strategies import StrategyRecognitionService
from .greeks import calculate_option_greeks
from ..adapters.test_data import TestDataQuoteAdapter
from ..adapters.base import QuoteAdapter


class TradingService:
    def __init__(
        self,
        quote_adapter: Optional[QuoteAdapter] = None,
        account_owner: str = "default",
    ) -> None:
        # Initialize services
        self.quote_adapter = quote_adapter or TestDataQuoteAdapter()
        self.order_execution = OrderExecutionEngine()
        self.account_validation = AccountValidator()
        self.strategy_recognition = StrategyRecognitionService()

        # Account configuration
        self.account_owner = account_owner

        # Initialize orders list
        self.orders: List[Order] = []

        # Portfolio and account state
        self.portfolio_positions: List[Position] = []
        self.cash_balance: float = 100000.0  # Default starting balance
        self.margin_service = None  # Placeholder for margin service
        self.legs: List[Any] = []  # Placeholder for legs

        # Legacy data (maintain compatibility for test data)
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

        # Initialize database account
        self._ensure_account_exists()

    def _get_db_session(self) -> Session:
        """Get a database session."""
        return SessionLocal()

    def _ensure_account_exists(self) -> None:
        """Ensure the account exists in the database."""
        db = self._get_db_session()
        try:
            account = (
                db.query(DBAccount)
                .filter(DBAccount.owner == self.account_owner)
                .first()
            )
            if not account:
                account = DBAccount(
                    owner=self.account_owner,
                    cash_balance=10000.0,  # Starting balance
                )
                db.add(account)
                db.commit()

                # Add some initial positions for compatibility
                initial_positions = [
                    DBPosition(
                        account_id=account.id,
                        symbol="AAPL",
                        quantity=10,
                        avg_price=145.00,
                        current_price=150.00,
                        unrealized_pnl=50.0,
                    ),
                    DBPosition(
                        account_id=account.id,
                        symbol="GOOGL",
                        quantity=2,
                        avg_price=2850.00,
                        current_price=2800.00,
                        unrealized_pnl=-100.0,
                    ),
                ]
                for pos in initial_positions:
                    db.add(pos)
                db.commit()
        finally:
            db.close()

    def _get_account(self) -> DBAccount:
        """Get the current account from database."""
        db = self._get_db_session()
        try:
            account = (
                db.query(DBAccount)
                .filter(DBAccount.owner == self.account_owner)
                .first()
            )
            if not account:
                raise NotFoundError(f"Account for owner {self.account_owner} not found")
            return account
        finally:
            db.close()

    def get_quote(self, symbol: str) -> StockQuote:
        """Get current stock quote for a symbol."""
        if symbol.upper() not in self.mock_quotes:
            raise NotFoundError(f"Symbol {symbol} not found")
        return self.mock_quotes[symbol.upper()]

    def create_order(self, order_data: OrderCreate) -> Order:
        """Create a new trading order."""
        # Validate symbol exists
        self.get_quote(order_data.symbol)

        db = self._get_db_session()
        try:
            account = (
                db.query(DBAccount)
                .filter(DBAccount.owner == self.account_owner)
                .first()
            )
            if not account:
                raise NotFoundError(f"Account for owner {self.account_owner} not found")

            # Create database order
            db_order = DBOrder(
                account_id=account.id,
                symbol=order_data.symbol.upper(),
                order_type=order_data.order_type,
                quantity=order_data.quantity,
                price=order_data.price,
                condition=order_data.condition
                if hasattr(order_data, "condition")
                else OrderCondition.MARKET,
                status=OrderStatus.PENDING,
                created_at=datetime.now(),
            )

            db.add(db_order)
            db.commit()
            db.refresh(db_order)

            # Return schema model
            return Order(
                id=db_order.id,
                symbol=db_order.symbol,
                order_type=db_order.order_type,
                quantity=db_order.quantity,
                price=db_order.price,
                condition=db_order.condition,
                status=db_order.status,
                created_at=db_order.created_at if db_order.created_at else None,  # type: ignore
                filled_at=db_order.filled_at if db_order.filled_at else None,  # type: ignore
                net_price=db_order.price,
            )
        finally:
            db.close()

    def get_orders(self) -> List[Order]:
        """Get all orders."""
        db = self._get_db_session()
        try:
            account = (
                db.query(DBAccount)
                .filter(DBAccount.owner == self.account_owner)
                .first()
            )
            if not account:
                return []

            db_orders = db.query(DBOrder).filter(DBOrder.account_id == account.id).all()

            return [
                Order(
                    id=db_order.id,
                    symbol=db_order.symbol,
                    order_type=db_order.order_type,
                    quantity=db_order.quantity,
                    price=db_order.price,
                    condition=db_order.condition,
                    status=db_order.status,
                    created_at=db_order.created_at,  # type: ignore
                    filled_at=db_order.filled_at,  # type: ignore
                    net_price=db_order.price,
                )
                for db_order in db_orders
            ]
        finally:
            db.close()

    def get_order(self, order_id: str) -> Order:
        """Get a specific order by ID."""
        db = self._get_db_session()
        try:
            account = (
                db.query(DBAccount)
                .filter(DBAccount.owner == self.account_owner)
                .first()
            )
            if not account:
                raise NotFoundError(f"Order {order_id} not found")

            db_order = (
                db.query(DBOrder)
                .filter(DBOrder.id == order_id, DBOrder.account_id == account.id)
                .first()
            )

            if not db_order:
                raise NotFoundError(f"Order {order_id} not found")

            return Order(
                id=db_order.id,
                symbol=db_order.symbol,
                order_type=db_order.order_type,
                quantity=db_order.quantity,
                price=db_order.price,
                condition=db_order.condition,
                status=db_order.status,
                created_at=db_order.created_at if db_order.created_at else None,  # type: ignore
                filled_at=db_order.filled_at if db_order.filled_at else None,  # type: ignore
                net_price=db_order.price,
            )
        finally:
            db.close()

    def cancel_order(self, order_id: str) -> Dict[str, str]:
        """Cancel a specific order."""
        db = self._get_db_session()
        try:
            account = (
                db.query(DBAccount)
                .filter(DBAccount.owner == self.account_owner)
                .first()
            )
            if not account:
                raise NotFoundError(f"Order {order_id} not found")

            db_order = (
                db.query(DBOrder)
                .filter(DBOrder.id == order_id, DBOrder.account_id == account.id)
                .first()
            )

            if not db_order:
                raise NotFoundError(f"Order {order_id} not found")

            db_order.status = OrderStatus.CANCELLED
            db.commit()

            return {"message": "Order cancelled successfully"}
        finally:
            db.close()

    def get_portfolio(self) -> Portfolio:
        """Get complete portfolio information."""
        db = self._get_db_session()
        try:
            account = (
                db.query(DBAccount)
                .filter(DBAccount.owner == self.account_owner)
                .first()
            )
            if not account:
                raise NotFoundError(f"Account for owner {self.account_owner} not found")

            db_positions = (
                db.query(DBPosition).filter(DBPosition.account_id == account.id).all()
            )

            # Convert database positions to schema positions
            positions = []
            for db_pos in db_positions:
                # Update current price from quote adapter
                try:
                    quote = self.get_quote(db_pos.symbol)
                    current_price = quote.price
                    unrealized_pnl = (
                        current_price - db_pos.avg_price
                    ) * db_pos.quantity

                    # Update database with current price
                    db_pos.current_price = current_price
                    db_pos.unrealized_pnl = unrealized_pnl
                    db.commit()

                    positions.append(
                        Position(
                            symbol=db_pos.symbol,
                            quantity=db_pos.quantity,
                            avg_price=db_pos.avg_price,
                            current_price=current_price,
                            unrealized_pnl=unrealized_pnl,
                            realized_pnl=db_pos.realized_pnl,
                        )
                    )
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
        finally:
            db.close()

    def get_portfolio_summary(self) -> PortfolioSummary:
        """Get portfolio summary."""
        # Use get_portfolio to get updated positions from database
        portfolio = self.get_portfolio()

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

    def get_positions(self) -> List[Position]:
        """Get all portfolio positions."""
        # Use get_portfolio to get updated positions from database
        portfolio = self.get_portfolio()
        return portfolio.positions

    def get_position(self, symbol: str) -> Position:
        """Get a specific position by symbol."""
        portfolio = self.get_portfolio()
        for position in portfolio.positions:
            if position.symbol.upper() == symbol.upper():
                return position
        raise NotFoundError(f"Position for symbol {symbol} not found")

    # Enhanced Options Trading Methods

    def get_portfolio_greeks(self) -> Dict[str, Any]:
        """Get aggregated Greeks for entire portfolio."""
        from .strategies import aggregate_portfolio_greeks

        positions = self.get_positions()

        # Get quotes for all positions
        current_quotes = {}
        for position in positions:
            try:
                quote = self.get_enhanced_quote(position.symbol)
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

    def get_position_greeks(self, symbol: str) -> Dict[str, Any]:
        """Get Greeks for a specific position."""
        position = self.get_position(symbol)

        # Get current quote for Greeks
        quote = self.get_enhanced_quote(symbol)

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

    def get_portfolio_strategies(self) -> Dict[str, Any]:
        """Get strategy analysis for portfolio."""
        from .strategies import analyze_strategy_portfolio

        positions = self.get_positions()

        # Analyze strategies
        analysis = analyze_strategy_portfolio(positions)

        return {
            "timestamp": datetime.now().isoformat(),
            "total_positions": analysis["total_positions"],
            "total_strategies": analysis["total_strategies"],
            "strategies": [
                {
                    "strategy_type": strategy.strategy_type,
                    "quantity": strategy.quantity,
                    "asset_symbol": (
                        getattr(strategy, "asset", {}).get("symbol", "unknown")
                        if hasattr(strategy, "asset")
                        else "unknown"
                    ),
                }
                for strategy in analysis["strategies"]
            ],
            "summary": analysis["summary"],
        }

    def get_option_greeks_response(
        self, option_symbol: str, underlying_price: Optional[float] = None
    ) -> Dict[str, Any]:
        """Get comprehensive Greeks response for an option symbol."""
        # Calculate Greeks
        greeks = self.calculate_greeks(option_symbol, underlying_price=underlying_price)

        # Get option details and quote
        asset = asset_factory(option_symbol)
        if not isinstance(asset, Option):
            raise ValueError("Symbol is not an option")

        option_quote = self.get_enhanced_quote(option_symbol)

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

    def get_enhanced_quote(
        self, symbol: str, underlying_price: Optional[float] = None
    ) -> Union[Quote, OptionQuote]:
        """Get enhanced quote with Greeks for options."""
        asset = asset_factory(symbol)
        if asset is None:
            raise NotFoundError(f"Invalid symbol: {symbol}")

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
        exp_datetime = (
            datetime.combine(expiration_date, datetime.min.time())
            if expiration_date
            else None
        )
        chain = self.quote_adapter.get_options_chain(underlying, exp_datetime)
        if chain is None:
            raise NotFoundError(f"No options chain found for {underlying}")
        return chain

    def calculate_greeks(
        self, option_symbol: str, underlying_price: Optional[float] = None
    ) -> Dict[str, Optional[float]]:
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

    def analyze_portfolio_strategies(
        self,
        include_greeks: bool = False,
        include_pnl: bool = False,
        include_complex_strategies: bool = False,
        include_recommendations: bool = False,
    ) -> Dict[str, Any]:
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

        if self.margin_service:
            return self.margin_service.get_portfolio_margin_breakdown(
                enhanced_positions, self.quote_adapter
            )
        else:
            return {"error": "Margin service not available"}

    def validate_account_state(self) -> bool:
        """Validate current account state."""
        return self.account_validation.validate_account_state(
            cash_balance=self.cash_balance, positions=self.portfolio_positions
        )

    def get_test_scenarios(self) -> Dict[str, Any]:
        """Get available test scenarios for development."""
        return self.quote_adapter.get_test_scenarios()

    def set_test_date(self, date_str: str) -> None:
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

    def create_multi_leg_order(self, order_data: Any) -> Order:
        """Create a multi-leg order."""
        # For now, create a simple order representation
        # In a real implementation, this would handle complex multi-leg orders
        order = Order(
            id=str(uuid4()),
            symbol=f"MULTI_LEG_{len(order_data.legs)}_LEGS",
            order_type=order_data.legs[0].order_type
            if order_data.legs
            else OrderType.BUY,
            quantity=sum(leg.quantity for leg in order_data.legs),
            price=sum(leg.price or 0 for leg in order_data.legs if leg.price),
            condition=getattr(order_data, "condition", OrderCondition.MARKET),
            status=OrderStatus.FILLED,
            created_at=datetime.now(),
            filled_at=datetime.now(),
            net_price=sum(leg.price or 0 for leg in order_data.legs if leg.price),
        )
        self.orders.append(order)
        return order

    def find_tradable_options(
        self,
        symbol: str,
        expiration_date: Optional[str] = None,
        option_type: Optional[str] = None,
    ) -> Dict[str, Any]:
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

            chain = self.get_options_chain(
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

    def get_option_market_data(self, option_id: str) -> Dict[str, Any]:
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

            quote = self.get_enhanced_quote(option_id)
            if not isinstance(quote, OptionQuote):
                return {"error": f"No market data available for {option_id}"}

            return {
                "option_id": option_id,
                "symbol": quote.asset.symbol,
                "underlying_symbol": quote.asset.underlying.symbol
                if quote.asset.underlying
                else "N/A",
                "strike_price": quote.asset.strike,
                "expiration_date": quote.asset.expiration_date.isoformat()
                if quote.asset.expiration_date
                else "N/A",
                "option_type": quote.asset.option_type.lower()
                if quote.asset.option_type
                else "N/A",
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

    def get_stock_price(self, symbol: str) -> Dict[str, Any]:
        """
        Get current stock price and basic metrics.

        This method provides a unified interface that works with both
        test data and live market data adapters.
        """
        try:
            asset = asset_factory(symbol)
            if not asset:
                return {"error": f"Invalid symbol: {symbol}"}

            quote = self.get_enhanced_quote(symbol)
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

    def get_stock_info(self, symbol: str) -> Dict[str, Any]:
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
                return self.quote_adapter.get_stock_info(symbol)
            else:
                # Fallback to basic quote data
                quote = self.get_enhanced_quote(symbol)
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

    def get_price_history(self, symbol: str, period: str = "week") -> Dict[str, Any]:
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
                return self.quote_adapter.get_price_history(symbol, period)
            else:
                # Fallback to current quote only
                quote = self.get_enhanced_quote(symbol)
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

    def get_stock_news(self, symbol: str) -> Dict[str, Any]:
        """
        Get news stories for a stock.

        This method provides a unified interface that works with both
        test data and live market data adapters.
        """
        try:
            asset = asset_factory(symbol)
            if not asset:
                return {"error": f"Invalid symbol: {symbol}"}

            # For now, use the adapter's extended functionality if available
            if hasattr(self.quote_adapter, "get_stock_news"):
                return self.quote_adapter.get_stock_news(symbol)
            else:
                return {
                    "symbol": symbol.upper(),
                    "news": [],
                    "message": "News data not available in current adapter",
                }

        except Exception as e:
            return {"error": str(e)}

    def get_top_movers(self) -> Dict[str, Any]:
        """
        Get top movers in the market.

        This method provides a unified interface that works with both
        test data and live market data adapters.
        """
        try:
            # For now, use the adapter's extended functionality if available
            if hasattr(self.quote_adapter, "get_top_movers"):
                return self.quote_adapter.get_top_movers()
            else:
                # Fallback to available symbols with basic data
                symbols = self.get_available_symbols()[:10]  # Top 10
                movers = []

                for symbol in symbols:
                    try:
                        price_data = self.get_stock_price(symbol)
                        if "error" not in price_data:
                            movers.append(
                                {
                                    "symbol": symbol,
                                    "price": price_data["price"],
                                    "change_percent": price_data.get(
                                        "change_percent", 0
                                    ),
                                }
                            )
                    except Exception:
                        continue

                return {
                    "movers": movers,
                    "message": "Limited movers data from test adapter",
                }

        except Exception as e:
            return {"error": str(e)}

    def search_stocks(self, query: str) -> Dict[str, Any]:
        """
        Search for stocks by symbol or company name.

        This method provides a unified interface that works with both
        test data and live market data adapters.
        """
        try:
            # For now, use the adapter's extended functionality if available
            if hasattr(self.quote_adapter, "search_stocks"):
                return self.quote_adapter.search_stocks(query)
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
                    "message": "Limited search from test adapter"
                    if not results
                    else None,
                }

        except Exception as e:
            return {"error": str(e)}

    def get_formatted_options_chain(
        self,
        symbol: str,
        expiration_date: Optional[date] = None,
        min_strike: Optional[float] = None,
        max_strike: Optional[float] = None,
        include_greeks: bool = True,
    ) -> Dict[str, Any]:
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
            chain = self.get_options_chain(symbol, expiration_date)

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
                "expiration_date": chain.expiration_date.isoformat()
                if chain.expiration_date
                else None,
                "quote_time": datetime.now().isoformat(),
                "calls": formatted_calls,
                "puts": formatted_puts,
            }

        except Exception as e:
            return {"error": str(e)}

    def create_multi_leg_order_from_request(
        self,
        legs: List[Dict[str, Any]],
        order_type: str,
        net_price: Optional[float] = None,
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
                    def __init__(self, data):
                        self.symbol = data["symbol"]
                        self.quantity = data["quantity"]
                        self.side = data["side"]
                        self.order_type = (
                            OrderType.BUY if data["side"] == "buy" else OrderType.SELL
                        )
                        self.price = data.get("price")

                def __init__(self, legs):
                    self.legs = legs

                self.legs = [self.MockLeg(leg) for leg in legs]
                self.condition = (
                    OrderCondition.LIMIT
                    if order_type == "limit"
                    else OrderCondition.MARKET
                )

            mock_order_data = MockOrderData(structured_legs)

            # Use the existing create_multi_leg_order method
            return self.create_multi_leg_order(mock_order_data)

        except Exception as e:
            raise ValueError(f"Failed to create multi-leg order: {str(e)}")

    def simulate_expiration(
        self, processing_date: Optional[str] = None, dry_run: bool = True
    ) -> Dict[str, Any]:
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
            portfolio = self.get_portfolio()

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
                                option_quote = self.get_enhanced_quote(position.symbol)
                                underlying_quote = self.get_enhanced_quote(
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
                                ):
                                    if (
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
                                        "action": "expire_worthless"
                                        if intrinsic_value == 0
                                        else "exercise_or_assign",
                                    }
                                )

                            except Exception as quote_error:
                                # Handle positions where we can't get quotes
                                expiring_positions.append(
                                    {
                                        "symbol": position.symbol,
                                        "expiration_date": asset.expiration_date.isoformat(),
                                        "quantity": position.quantity,
                                        "error": f"Could not get quote: {str(quote_error)}",
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
                            "error": f"Could not parse position: {str(position_error)}",
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
            return {"error": f"Simulation failed: {str(e)}"}


# Initialize adapter based on configuration
def _get_quote_adapter() -> QuoteAdapter:
    """Get the appropriate quote adapter based on environment."""
    import os

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
    return TestDataQuoteAdapter()


# Global service instance
trading_service = TradingService(_get_quote_adapter())
