from datetime import datetime, date
from typing import List, Dict, Optional, Union, Any
from uuid import uuid4

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

# Import new services
from .order_execution import OrderExecutionEngine
from .validation import AccountValidator
from .strategies import StrategyRecognitionService
from .margin import MaintenanceMarginService
from .greeks import calculate_option_greeks
from ..adapters.test_data import TestDataQuoteAdapter
from ..adapters.base import QuoteAdapter


class TradingService:
    def __init__(self, quote_adapter: Optional[QuoteAdapter] = None) -> None:
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
        self.quote_adapter = quote_adapter or TestDataQuoteAdapter()
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
            condition=order_data.condition
            if hasattr(order_data, "condition")
            else OrderCondition.MARKET,
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
            pos.quantity * (pos.current_price or 0) for pos in self.portfolio_positions
        )
        total_value = self.cash_balance + total_invested
        total_pnl = sum(pos.unrealized_pnl or 0 for pos in self.portfolio_positions)

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
            pos.quantity * (pos.current_price or 0) for pos in self.portfolio_positions
        )
        total_value = self.cash_balance + invested_value
        total_pnl = sum(pos.unrealized_pnl or 0 for pos in self.portfolio_positions)

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
        chain = self.quote_adapter.get_options_chain(underlying, expiration_date)
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
        )
        self.orders.append(order)
        return order

    def find_tradable_options(
        self, 
        symbol: str, 
        expiration_date: Optional[str] = None,
        option_type: Optional[str] = None
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
                
            chain = self.get_options_chain(symbol, exp_date.date() if exp_date else None)
            
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
                "underlying_symbol": quote.asset.underlying.symbol,
                "strike_price": quote.asset.strike,
                "expiration_date": quote.asset.expiration_date.isoformat(),
                "option_type": quote.asset.option_type.lower(),
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
            
            if previous_close and previous_close > 0:
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
                    return {"error": f"No company information found for symbol: {symbol}"}
                    
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
                    return {"error": f"No historical data found for {symbol} over {period}"}
                    
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
                            movers.append({
                                "symbol": symbol,
                                "price": price_data["price"],
                                "change_percent": price_data.get("change_percent", 0),
                            })
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
                        results.append({
                            "symbol": symbol,
                            "name": f"{symbol} Company",
                            "tradeable": True,
                        })
                        
                return {
                    "query": query,
                    "results": results[:10],  # Limit to 10 results
                    "message": "Limited search from test adapter" if not results else None,
                }
                
        except Exception as e:
            return {"error": str(e)}


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
