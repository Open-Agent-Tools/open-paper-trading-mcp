"""
Robinhood adapter for live market data integration.
"""

import asyncio
from typing import Dict, List, Optional, Any
from datetime import datetime, date
import robin_stocks.robinhood as rh
from pydantic import BaseModel

from app.adapters.base import QuoteAdapter, AdapterConfig
from app.models.quotes import Quote, OptionQuote, OptionsChain
from app.models.assets import Asset, Option, Stock, asset_factory
from app.auth.session_manager import get_session_manager
from app.core.logging import logger


class RobinhoodConfig(AdapterConfig):
    """Configuration for Robinhood adapter."""
    
    name: str = "robinhood"
    priority: int = 1
    cache_ttl: float = 300.0  # 5 minutes
    
    
class RobinhoodAdapter(QuoteAdapter):
    """Live market data adapter using Robinhood API."""
    
    def __init__(self, config: Optional[RobinhoodConfig] = None):
        self.config = config or RobinhoodConfig()
        self.session_manager = get_session_manager()
        
    async def _ensure_authenticated(self) -> bool:
        """Ensure we have valid authentication."""
        return await self.session_manager.ensure_authenticated()
        
    def get_quote(self, asset: Asset) -> Optional[Quote]:
        """Get a single quote for an asset."""
        try:
            # Run async method in sync context
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
            try:
                if not loop.run_until_complete(self._ensure_authenticated()):
                    logger.error("Robinhood authentication failed")
                    return None
                    
                if isinstance(asset, Stock):
                    return self._get_stock_quote(asset)
                elif isinstance(asset, Option):
                    return self._get_option_quote(asset)
                    
            finally:
                loop.close()
                
        except Exception as e:
            logger.error(f"Error getting quote for {asset.symbol}: {e}")
            return None
            
    def _get_stock_quote(self, asset: Stock) -> Optional[Quote]:
        """Get stock quote from Robinhood."""
        try:
            quote_data = rh.stocks.get_latest_price(asset.symbol)
            if not quote_data or not quote_data[0]:
                return None
                
            price = float(quote_data[0])
            
            # Get fundamentals for more data
            fundamentals = rh.stocks.get_fundamentals(asset.symbol)
            if fundamentals and fundamentals[0]:
                fund_data = fundamentals[0]
                volume = int(fund_data.get('volume', 0)) if fund_data.get('volume') else None
            else:
                volume = None
                
            return Quote(
                asset=asset,
                quote_date=datetime.now(),
                price=price,
                bid=price - 0.01,  # Approximation
                ask=price + 0.01,  # Approximation
                volume=volume
            )
            
        except Exception as e:
            logger.error(f"Error getting stock quote for {asset.symbol}: {e}")
            return None
            
    def _get_option_quote(self, asset: Option) -> Optional[OptionQuote]:
        """Get option quote from Robinhood."""
        try:
            # Find the option instrument
            option_data = rh.options.find_options_by_expiration_and_strike(
                asset.underlying.symbol,
                asset.expiration_date.isoformat(),
                asset.strike,
                asset.option_type.lower()
            )
            
            if not option_data:
                return None
                
            instrument = option_data[0]
            market_data = rh.options.get_option_market_data_by_id(instrument['id'])
            
            if not market_data:
                return None
                
            # Get underlying price
            underlying_quote = self._get_stock_quote(asset.underlying)
            underlying_price = underlying_quote.price if underlying_quote else None
            
            bid = float(market_data.get('bid_price', 0)) if market_data.get('bid_price') else 0
            ask = float(market_data.get('ask_price', 0)) if market_data.get('ask_price') else 0
            price = (bid + ask) / 2 if bid > 0 and ask > 0 else None
            
            return OptionQuote(
                asset=asset,
                quote_date=datetime.now(),
                price=price,
                bid=bid,
                ask=ask,
                underlying_price=underlying_price,
                volume=int(market_data.get('volume', 0)) if market_data.get('volume') else None,
                open_interest=int(market_data.get('open_interest', 0)) if market_data.get('open_interest') else None
            )
            
        except Exception as e:
            logger.error(f"Error getting option quote for {asset.symbol}: {e}")
            return None
            
    def get_quotes(self, assets: List[Asset]) -> Dict[Asset, Quote]:
        """Get quotes for multiple assets."""
        results = {}
        for asset in assets:
            quote = self.get_quote(asset)
            if quote:
                results[asset] = quote
        return results
        
    def get_chain(
        self, underlying: str, expiration_date: Optional[datetime] = None
    ) -> List[Asset]:
        """Get option chain for an underlying (returns list of assets)."""
        # This method returns just the assets, not full quotes
        try:
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
            try:
                if not loop.run_until_complete(self._ensure_authenticated()):
                    return []
                    
                chains_data = rh.options.get_chains(underlying)
                if not chains_data:
                    return []
                    
                assets = []
                for chain in chains_data:
                    expiration = chain.get('expiration_date')
                    if expiration_date and expiration != expiration_date.strftime('%Y-%m-%d'):
                        continue
                        
                    # Get instruments for this expiration
                    instruments = rh.options.get_option_instruments(
                        underlying,
                        expiration,
                        option_type='both'
                    )
                    
                    for instrument in instruments:
                        asset = asset_factory(instrument.get('url', ''))
                        if asset:
                            assets.append(asset)
                            
                return assets
                
            finally:
                loop.close()
                
        except Exception as e:
            logger.error(f"Error getting option chain for {underlying}: {e}")
            return []
            
    def get_options_chain(
        self, underlying: str, expiration_date: Optional[datetime] = None
    ) -> Optional[OptionsChain]:
        """Get complete options chain with quotes."""
        try:
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
            try:
                if not loop.run_until_complete(self._ensure_authenticated()):
                    return None
                    
                # Get underlying asset and price
                underlying_asset = asset_factory(underlying)
                if not underlying_asset:
                    return None
                    
                underlying_quote = self._get_stock_quote(underlying_asset)
                underlying_price = underlying_quote.price if underlying_quote else None
                
                # Get chains data
                chains_data = rh.options.get_chains(underlying)
                if not chains_data:
                    return None
                    
                calls = []
                puts = []
                target_expiration = None
                
                for chain in chains_data:
                    expiration_str = chain.get('expiration_date')
                    if not expiration_str:
                        continue
                        
                    chain_exp_date = datetime.strptime(expiration_str, '%Y-%m-%d').date()
                    
                    # Filter by expiration if specified
                    if expiration_date:
                        exp_date = expiration_date.date() if isinstance(expiration_date, datetime) else expiration_date
                        if chain_exp_date != exp_date:
                            continue
                    
                    target_expiration = chain_exp_date
                    
                    # Get option instruments for this expiration
                    call_instruments = rh.options.get_option_instruments(
                        underlying, expiration_str, option_type='call'
                    )
                    put_instruments = rh.options.get_option_instruments(
                        underlying, expiration_str, option_type='put'
                    )
                    
                    # Process calls
                    for instrument in call_instruments:
                        option_asset = self._create_option_asset(instrument, underlying_asset, 'call')
                        if option_asset:
                            option_quote = self._get_option_quote(option_asset)
                            if option_quote:
                                calls.append(option_quote)
                                
                    # Process puts  
                    for instrument in put_instruments:
                        option_asset = self._create_option_asset(instrument, underlying_asset, 'put')
                        if option_asset:
                            option_quote = self._get_option_quote(option_asset)
                            if option_quote:
                                puts.append(option_quote)
                                
                    # If we have a specific expiration, we only want one
                    if expiration_date:
                        break
                        
                if not target_expiration:
                    return None
                    
                return OptionsChain(
                    underlying_symbol=underlying,
                    expiration_date=target_expiration,
                    underlying_price=underlying_price,
                    calls=calls,
                    puts=puts,
                    quote_time=datetime.now()
                )
                
            finally:
                loop.close()
                
        except Exception as e:
            logger.error(f"Error getting options chain for {underlying}: {e}")
            return None
            
    def _create_option_asset(self, instrument: Dict, underlying_asset: Asset, option_type: str) -> Optional[Option]:
        """Create an Option asset from Robinhood instrument data."""
        try:
            strike = float(instrument.get('strike_price', 0))
            expiration_str = instrument.get('expiration_date')
            if not expiration_str:
                return None
                
            expiration = datetime.strptime(expiration_str, '%Y-%m-%d').date()
            
            # Create option symbol in standard format
            exp_str = expiration.strftime('%y%m%d')
            strike_str = f"{int(strike * 1000):08d}"
            type_char = 'C' if option_type.lower() == 'call' else 'P'
            symbol = f"{underlying_asset.symbol}{exp_str}{type_char}{strike_str}"
            
            return Option(
                symbol=symbol,
                underlying=underlying_asset,
                option_type=option_type.upper(),
                strike=strike,
                expiration_date=expiration
            )
            
        except Exception as e:
            logger.error(f"Error creating option asset: {e}")
            return None
            
    def is_market_open(self) -> bool:
        """Check if the market is currently open."""
        try:
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
            try:
                if not loop.run_until_complete(self._ensure_authenticated()):
                    return False
                    
                market_hours = rh.markets.get_market_hours('XNYS', datetime.now().date())
                if not market_hours:
                    return False
                    
                return market_hours.get('is_open', False)
                
            finally:
                loop.close()
                
        except Exception as e:
            logger.error(f"Error checking market status: {e}")
            return False
            
    def get_market_hours(self) -> Dict[str, Any]:
        """Get market hours information."""
        try:
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
            try:
                if not loop.run_until_complete(self._ensure_authenticated()):
                    return {}
                    
                market_hours = rh.markets.get_market_hours('XNYS', datetime.now().date())
                return market_hours or {}
                
            finally:
                loop.close()
                
        except Exception as e:
            logger.error(f"Error getting market hours: {e}")
            return {}

    # ============================================================================
    # EXTENDED STOCK DATA METHODS
    # ============================================================================

    def get_stock_info(self, symbol: str) -> Dict[str, Any]:
        """Get detailed company information and fundamentals for a stock."""
        try:
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
            try:
                if not loop.run_until_complete(self._ensure_authenticated()):
                    return {"error": "Authentication failed"}

                fundamentals_list = rh.stocks.get_fundamentals(symbol)
                instruments_list = rh.stocks.get_instruments_by_symbols(symbol)

                if not fundamentals_list or not instruments_list:
                    return {"error": f"No company information found for symbol: {symbol}"}

                fundamental = fundamentals_list[0]
                instrument = instruments_list[0]
                company_name = rh.stocks.get_name_by_symbol(symbol)

                return {
                    "symbol": symbol.upper(),
                    "company_name": company_name or instrument.get("simple_name", "N/A"),
                    "sector": fundamental.get("sector", "N/A"),
                    "industry": fundamental.get("industry", "N/A"),
                    "description": fundamental.get("description", "N/A"),
                    "market_cap": fundamental.get("market_cap", "N/A"),
                    "pe_ratio": fundamental.get("pe_ratio", "N/A"),
                    "dividend_yield": fundamental.get("dividend_yield", "N/A"),
                    "high_52_weeks": fundamental.get("high_52_weeks", "N/A"),
                    "low_52_weeks": fundamental.get("low_52_weeks", "N/A"),
                    "average_volume": fundamental.get("average_volume", "N/A"),
                    "tradeable": instrument.get("tradeable", False),
                }
                
            finally:
                loop.close()
                
        except Exception as e:
            logger.error(f"Error getting stock info for {symbol}: {e}")
            return {"error": str(e)}

    def get_price_history(self, symbol: str, period: str) -> Dict[str, Any]:
        """Get historical price data for a stock."""
        try:
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
            try:
                if not loop.run_until_complete(self._ensure_authenticated()):
                    return {"error": "Authentication failed"}

                interval_map = {
                    "day": "5minute",
                    "week": "hour", 
                    "month": "day",
                    "3month": "day",
                    "year": "week",
                    "5year": "week",
                }
                interval = interval_map.get(period, "day")

                historical_data = rh.stocks.get_stock_historicals(
                    symbol, interval, period, "regular"
                )

                if not historical_data:
                    return {"error": f"No historical data found for {symbol} over {period}"}

                price_points = [
                    {
                        "date": data_point.get("begins_at", "N/A"),
                        "open": float(data_point.get("open_price", 0)),
                        "high": float(data_point.get("high_price", 0)),
                        "low": float(data_point.get("low_price", 0)),
                        "close": float(data_point.get("close_price", 0)),
                        "volume": int(data_point.get("volume", 0)),
                    }
                    for data_point in historical_data
                    if data_point and data_point.get("close_price")
                ]

                return {
                    "symbol": symbol.upper(),
                    "period": period,
                    "interval": interval,
                    "data_points": price_points,
                }
                
            finally:
                loop.close()
                
        except Exception as e:
            logger.error(f"Error getting price history for {symbol}: {e}")
            return {"error": str(e)}

    def get_stock_news(self, symbol: str) -> Dict[str, Any]:
        """Get news stories for a stock."""
        try:
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
            try:
                if not loop.run_until_complete(self._ensure_authenticated()):
                    return {"error": "Authentication failed"}

                news_data = rh.stocks.get_news(symbol)

                if not news_data:
                    return {"error": f"No news data found for symbol: {symbol}"}

                return {
                    "symbol": symbol.upper(),
                    "news": news_data,
                }
                
            finally:
                loop.close()
                
        except Exception as e:
            logger.error(f"Error getting news for {symbol}: {e}")
            return {"error": str(e)}

    def get_top_movers(self) -> Dict[str, Any]:
        """Get top movers in the market."""
        try:
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
            try:
                if not loop.run_until_complete(self._ensure_authenticated()):
                    return {"error": "Authentication failed"}

                movers_data = rh.stocks.get_top_movers()

                if not movers_data:
                    return {"error": "No top movers data found"}

                return {"movers": movers_data}
                
            finally:
                loop.close()
                
        except Exception as e:
            logger.error(f"Error getting top movers: {e}")
            return {"error": str(e)}

    def search_stocks(self, query: str) -> Dict[str, Any]:
        """Search for stocks by symbol or company name."""
        try:
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
            try:
                if not loop.run_until_complete(self._ensure_authenticated()):
                    return {"error": "Authentication failed"}

                search_results = rh.stocks.find_instrument_data(query)

                if not search_results:
                    return {
                        "query": query,
                        "results": [],
                        "message": f"No stocks found matching query: {query}",
                    }

                results = [
                    {
                        "symbol": item.get("symbol", "").upper(),
                        "name": item.get("simple_name", "N/A"),
                        "tradeable": item.get("tradeable", False),
                    }
                    for item in search_results
                    if item.get("symbol")
                ]

                return {
                    "query": query,
                    "results": results,
                }
                
            finally:
                loop.close()
                
        except Exception as e:
            logger.error(f"Error searching for stocks with query {query}: {e}")
            return {"error": str(e)}