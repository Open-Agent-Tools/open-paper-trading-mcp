from datetime import date, datetime
from typing import Any
from uuid import uuid4

from sqlalchemy.orm import Session
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import NotFoundError
from app.models.assets import Option, asset_factory
from app.models.database.trading import (
    Account as DBAccount,
)
from app.models.database.trading import (
    Order as DBOrder,
)
from app.models.database.trading import (
    Position as DBPosition,
)
from app.models.quotes import OptionQuote, OptionsChain, Quote
from app.models.trading import Portfolio, PortfolioSummary, Position, StockQuote
from app.schemas.orders import (
    Order,
    OrderCondition,
    OrderCreate,
    OrderStatus,
    OrderType,
)

# Database imports removed - using async patterns only

from ..adapters.base import QuoteAdapter
from ..adapters.test_data import TestDataQuoteAdapter
from .greeks import calculate_option_greeks

# Import new services
from .order_execution import OrderExecutionEngine
from .strategies import StrategyRecognitionService
from .validation import AccountValidator


class TradingService:
    def __init__(
        self,
        quote_adapter: QuoteAdapter | None = None,
        account_owner: str = "default",
    ) -> None:
        # Initialize services
        self.quote_adapter = quote_adapter or TestDataQuoteAdapter()
        self.order_execution = OrderExecutionEngine()
        self.account_validation = AccountValidator()
        self.strategy_recognition = StrategyRecognitionService()

        # Account configuration
        self.account_owner = account_owner

        # Service components
        self.margin_service = None  # Placeholder for margin service
        self.legs: list[Any] = []  # Placeholder for legs

        # Initialize database account
        # Note: This will be called lazily on first async method call

    async def _get_async_db_session(self) -> AsyncSession:
        """Get an async database session."""
        from app.storage.database import get_async_session
        async_generator = get_async_session()
        session = await async_generator.__anext__()
        return session

    async def _ensure_account_exists(self) -> None:
        """Ensure the account exists in the database."""
        from sqlalchemy import select
        db = await self._get_async_db_session()
        try:
            stmt = select(DBAccount).where(DBAccount.owner == self.account_owner)
            result = await db.execute(stmt)
            account = result.scalar_one_or_none()
            
            if not account:
                account = DBAccount(
                    owner=self.account_owner,
                    cash_balance=10000.0,  # Starting balance
                )
                db.add(account)
                await db.commit()
                await db.refresh(account)

                # Add some initial positions for compatibility
                initial_positions = [
                    DBPosition(
                        account_id=account.id,
                        symbol="AAPL",
                        quantity=10,
                        avg_price=145.00,
                    ),
                    DBPosition(
                        account_id=account.id,
                        symbol="GOOGL",
                        quantity=2,
                        avg_price=2850.00,
                    ),
                ]
                for pos in initial_positions:
                    db.add(pos)
                await db.commit()
        finally:
            await db.close()

    async def _get_account(self) -> DBAccount:
        """Get the current account from database."""
        from sqlalchemy import select
        
        # Ensure account exists first
        await self._ensure_account_exists()
        
        db = await self._get_async_db_session()
        try:
            stmt = select(DBAccount).where(DBAccount.owner == self.account_owner)
            result = await db.execute(stmt)
            account = result.scalar_one_or_none()
            if not account:
                raise NotFoundError(f"Account for owner {self.account_owner} not found")
            return account
        finally:
            await db.close()

    async def get_account_balance(self) -> float:
        """Get current account balance from database."""
        account = await self._get_account()
        return float(account.cash_balance)

    def get_quote(self, symbol: str) -> StockQuote:
        """Get current stock quote for a symbol."""
        try:
            # Create asset from symbol
            asset = asset_factory(symbol)
            if asset is None:
                raise NotFoundError(f"Invalid symbol: {symbol}")
            
            # Use the quote adapter to get real market data
            quote = self.quote_adapter.get_quote(asset)
            if quote is None:
                raise NotFoundError(f"Symbol {symbol} not found")
            
            # Convert to StockQuote format for backward compatibility
            return StockQuote(
                symbol=symbol.upper(),
                price=quote.price or 0.0,
                change=0.0,  # Not available in Quote format
                change_percent=0.0,  # Not available in Quote format
                volume=getattr(quote, 'volume', 0),
                last_updated=quote.quote_date
            )
        except Exception as e:
            # If adapter fails, raise a not found error
            raise NotFoundError(f"Symbol {symbol} not found: {e!s}") from e

    async def create_order(self, order_data: OrderCreate) -> Order:
        """Create a new trading order."""
        # Validate symbol exists
        self.get_quote(order_data.symbol)

        db = await self._get_async_db_session()
        try:
            account = await self._get_account()

            # Create database order
            db_order = DBOrder(
                account_id=account.id,
                symbol=order_data.symbol.upper(),
                order_type=order_data.order_type,
                quantity=order_data.quantity,
                price=order_data.price,
                status=OrderStatus.PENDING,
                created_at=datetime.now(),
            )

            db.add(db_order)
            await db.commit()
            await db.refresh(db_order)
            
            # Return schema model
            return Order(
                id=db_order.id,
                symbol=db_order.symbol,
                order_type=db_order.order_type,
                quantity=db_order.quantity,
                price=db_order.price,
                condition=OrderCondition.MARKET,  # Default condition since not stored in DB
                status=db_order.status,
                created_at=db_order.created_at if db_order.created_at else None,  # type: ignore
                filled_at=db_order.filled_at if db_order.filled_at else None,  # type: ignore
                net_price=db_order.price,
            )
        finally:
            await db.close()

    async def get_orders(self) -> list[Order]:
        """Get all orders."""
        from sqlalchemy import select
        db = await self._get_async_db_session()
        try:
            account = await self._get_account()
            
            stmt = select(DBOrder).where(DBOrder.account_id == account.id)
            result = await db.execute(stmt)
            db_orders = result.scalars().all()

            return [
                Order(
                    id=db_order.id,
                    symbol=db_order.symbol,
                    order_type=db_order.order_type,
                    quantity=db_order.quantity,
                    price=db_order.price,
                    condition=OrderCondition.MARKET,  # Default condition since not stored in DB
                    status=db_order.status,
                    created_at=db_order.created_at,  # type: ignore
                    filled_at=db_order.filled_at,  # type: ignore
                    net_price=db_order.price,
                )
                for db_order in db_orders
            ]
        finally:
            await db.close()

    async def get_order(self, order_id: str) -> Order:
        """Get a specific order by ID."""
        from sqlalchemy import select
        db = await self._get_async_db_session()
        try:
            account = await self._get_account()

            stmt = select(DBOrder).where(
                DBOrder.id == order_id,
                DBOrder.account_id == account.id
            )
            result = await db.execute(stmt)
            db_order = result.scalar_one_or_none()

            if not db_order:
                raise NotFoundError(f"Order {order_id} not found")

            return Order(
                id=db_order.id,
                symbol=db_order.symbol,
                order_type=db_order.order_type,
                quantity=db_order.quantity,
                price=db_order.price,
                condition=OrderCondition.MARKET,  # Default condition since not stored in DB
                status=db_order.status,
                created_at=db_order.created_at if db_order.created_at else None,  # type: ignore
                filled_at=db_order.filled_at if db_order.filled_at else None,  # type: ignore
                net_price=db_order.price,
            )
        finally:
            await db.close()

    async def cancel_order(self, order_id: str) -> dict[str, str]:
        """Cancel a specific order."""
        from sqlalchemy import select
        db = await self._get_async_db_session()
        try:
            account = await self._get_account()

            stmt = select(DBOrder).where(
                DBOrder.id == order_id,
                DBOrder.account_id == account.id
            )
            result = await db.execute(stmt)
            db_order = result.scalar_one_or_none()

            if not db_order:
                raise NotFoundError(f"Order {order_id} not found")

            db_order.status = OrderStatus.CANCELLED
            await db.commit()

            return {"message": "Order cancelled successfully"}
        finally:
            await db.close()

    async def get_portfolio(self) -> Portfolio:
        """Get complete portfolio information."""
        from sqlalchemy import select
        db = await self._get_async_db_session()
        try:
            account = await self._get_account()

            stmt = select(DBPosition).where(DBPosition.account_id == account.id)
            result = await db.execute(stmt)
            db_positions = result.scalars().all()

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

                    # Don't update database - calculate on the fly
                    positions.append(
                        Position(
                            symbol=db_pos.symbol,
                            quantity=db_pos.quantity,
                            avg_price=db_pos.avg_price,
                            current_price=current_price,
                            unrealized_pnl=unrealized_pnl,
                            realized_pnl=0.0,  # Not stored in database currently
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
            await db.close()

    async def get_portfolio_summary(self) -> PortfolioSummary:
        """Get portfolio summary."""
        # Use get_portfolio to get updated positions from database
        portfolio = await self.get_portfolio()

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

    async def get_positions(self) -> list[Position]:
        """Get all portfolio positions."""
        # Use get_portfolio to get updated positions from database
        portfolio = await self.get_portfolio()
        return portfolio.positions

    async def get_position(self, symbol: str) -> Position:
        """Get a specific position by symbol."""
        portfolio = await self.get_portfolio()
        for position in portfolio.positions:
            if position.symbol.upper() == symbol.upper():
                return position
        raise NotFoundError(f"Position for symbol {symbol} not found")

    # Enhanced Options Trading Methods

    async def get_portfolio_greeks(self) -> dict[str, Any]:
        """Get aggregated Greeks for entire portfolio."""
        from .strategies import aggregate_portfolio_greeks

        positions = await self.get_positions()

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

    async def get_position_greeks(self, symbol: str) -> dict[str, Any]:
        """Get Greeks for a specific position."""
        position = await self.get_position(symbol)

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

    async def get_portfolio_strategies(self) -> dict[str, Any]:
        """Get strategy analysis for portfolio."""
        from .strategies import analyze_strategy_portfolio

        positions = await self.get_positions()

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
        self, option_symbol: str, underlying_price: float | None = None
    ) -> dict[str, Any]:
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
        self, symbol: str, underlying_price: float | None = None
    ) -> Quote | OptionQuote:
        """Get enhanced quote with Greeks for options."""
        asset = asset_factory(symbol)
        if asset is None:
            raise NotFoundError(f"Invalid symbol: {symbol}")

        # Use the quote adapter to get real market data
        quote = self.quote_adapter.get_quote(asset)
        if quote:
            return quote

        # No fallback - raise error if adapter cannot provide quote
        raise NotFoundError(f"No quote available for {symbol}")

    def get_options_chain(
        self, underlying: str, expiration_date: date | None = None
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
        self, option_symbol: str, underlying_price: float | None = None
    ) -> dict[str, float | None]:
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

    async def analyze_portfolio_strategies(
        self,
        include_greeks: bool = False,
        include_pnl: bool = False,
        include_complex_strategies: bool = False,
        include_recommendations: bool = False,
    ) -> dict[str, Any]:
        """Analyze portfolio for trading strategies."""
        # Get current positions from database
        positions = await self.get_positions()
        
        # Convert to enhanced Position objects
        enhanced_positions = []
        for pos in positions:
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

    async def calculate_margin_requirement(self) -> dict[str, Any]:
        """Calculate current portfolio margin requirement."""
        # Get current positions from database
        positions = await self.get_positions()
        
        # Convert to enhanced Position objects
        enhanced_positions = []
        for pos in positions:
            enhanced_positions.append(pos)

        if self.margin_service:
            return self.margin_service.get_portfolio_margin_breakdown(
                enhanced_positions, self.quote_adapter
            )
        else:
            return {"error": "Margin service not available"}

    async def validate_account_state(self) -> bool:
        """Validate current account state."""
        cash_balance = await self.get_account_balance()
        positions = await self.get_positions()
        return self.account_validation.validate_account_state(
            cash_balance=cash_balance, positions=positions
        )

    def get_test_scenarios(self) -> dict[str, Any]:
        """Get available test scenarios for development."""
        return self.quote_adapter.get_test_scenarios()

    def set_test_date(self, date_str: str) -> None:
        """Set test data date for historical scenarios."""
        self.quote_adapter.set_date(date_str)

    def get_available_symbols(self) -> list[str]:
        """Get all available symbols in test data."""
        return self.quote_adapter.get_available_symbols()

    def get_sample_data_info(self) -> dict[str, Any]:
        """Get information about sample data."""
        return self.quote_adapter.get_sample_data_info()

    def get_expiration_dates(self, underlying: str) -> list[date]:
        """Get available expiration dates for an underlying symbol."""
        return self.quote_adapter.get_expiration_dates(underlying)

    async def create_multi_leg_order(self, order_data: Any) -> Order:
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
        
        # Persist to database using the same pattern as create_order
        db = await self._get_async_db_session()
        try:
            # Query for the account ID instead of using account_owner directly
            account = await self._get_account()
            
            db_order = DBOrder(
                id=order.id,
                symbol=order.symbol,
                order_type=order.order_type.value,
                quantity=order.quantity,
                price=order.price,
                condition=order.condition.value,
                status=order.status.value,
                created_at=order.created_at,
                filled_at=order.filled_at,
                account_id=account.id,
            )
            db.add(db_order)
            await db.commit()
            await db.refresh(db_order)
        finally:
            await db.close()
        
        return order

    def find_tradable_options(
        self,
        symbol: str,
        expiration_date: str | None = None,
        option_type: str | None = None,
    ) -> dict[str, Any]:
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

    def get_option_market_data(self, option_id: str) -> dict[str, Any]:
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

    def get_stock_price(self, symbol: str) -> dict[str, Any]:
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

    def get_stock_info(self, symbol: str) -> dict[str, Any]:
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

    def get_price_history(self, symbol: str, period: str = "week") -> dict[str, Any]:
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

    def get_stock_news(self, symbol: str) -> dict[str, Any]:
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

    def get_top_movers(self) -> dict[str, Any]:
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

    def search_stocks(self, query: str) -> dict[str, Any]:
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
        expiration_date: date | None = None,
        min_strike: float | None = None,
        max_strike: float | None = None,
        include_greeks: bool = True,
    ) -> dict[str, Any]:
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
        legs: list[dict[str, Any]],
        order_type: str,
        net_price: float | None = None,
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
            raise ValueError(f"Failed to create multi-leg order: {e!s}") from e

    async def simulate_expiration(
        self, processing_date: str | None = None, dry_run: bool = True
    ) -> dict[str, Any]:
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
            portfolio = await self.get_portfolio()

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
                                        "error": f"Could not get quote: {quote_error!s}",
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
                            "error": f"Could not parse position: {position_error!s}",
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
            return {"error": f"Simulation failed: {e!s}"}


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


# Global service instance - will be created lazily to avoid sync database calls during import
import os
trading_service = None

def get_trading_service() -> TradingService:
    """Get or create the global trading service instance."""
    global trading_service
    if trading_service is None:
        trading_service = TradingService(_get_quote_adapter())
    return trading_service
