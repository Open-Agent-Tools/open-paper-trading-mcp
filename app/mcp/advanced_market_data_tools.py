"""
Advanced market data tools for comprehensive market analysis.

These tools provide extended market data functionality beyond basic quotes,
including earnings, dividends, market movers, and economic data.
"""

from datetime import datetime, timedelta
from typing import Any

from app.mcp.base import get_trading_service
from app.mcp.response_utils import handle_tool_exception, success_response


async def get_earnings_calendar(days_ahead: int = 7) -> dict[str, Any]:
    """
    Get upcoming earnings calendar for specified number of days.
    
    Args:
        days_ahead: Number of days to look ahead (default 7)
    """
    try:
        # Simulate earnings calendar data
        today = datetime.now()
        earnings_data = []
        
        for i in range(days_ahead):
            date = today + timedelta(days=i)
            # Simulate some earnings for demo
            if i % 2 == 0:
                earnings_data.append({
                    "date": date.strftime("%Y-%m-%d"),
                    "symbol": "AAPL" if i % 4 == 0 else "GOOGL",
                    "company_name": "Apple Inc." if i % 4 == 0 else "Alphabet Inc.",
                    "time": "after_market_close",
                    "estimate_eps": 1.25 if i % 4 == 0 else 1.15,
                    "previous_eps": 1.20 if i % 4 == 0 else 1.10
                })
        
        data = {
            "earnings_calendar": earnings_data,
            "date_range": {
                "start": today.strftime("%Y-%m-%d"),
                "end": (today + timedelta(days=days_ahead-1)).strftime("%Y-%m-%d")
            },
            "total_companies": len(earnings_data)
        }
        
        return success_response(data)
    except Exception as e:
        return handle_tool_exception("get_earnings_calendar", e)


async def get_dividend_calendar(days_ahead: int = 30) -> dict[str, Any]:
    """
    Get upcoming dividend calendar for specified number of days.
    
    Args:
        days_ahead: Number of days to look ahead (default 30)
    """
    try:
        # Simulate dividend calendar data
        today = datetime.now()
        dividend_data = []
        
        # Simulate some dividends
        for i in range(0, days_ahead, 7):
            date = today + timedelta(days=i)
            dividend_data.append({
                "ex_dividend_date": date.strftime("%Y-%m-%d"),
                "symbol": "MSFT" if i % 14 == 0 else "JNJ",
                "company_name": "Microsoft Corp." if i % 14 == 0 else "Johnson & Johnson",
                "dividend_amount": 0.68 if i % 14 == 0 else 1.13,
                "dividend_yield": 0.72 if i % 14 == 0 else 2.85,
                "payment_date": (date + timedelta(days=14)).strftime("%Y-%m-%d")
            })
        
        data = {
            "dividend_calendar": dividend_data,
            "date_range": {
                "start": today.strftime("%Y-%m-%d"),
                "end": (today + timedelta(days=days_ahead-1)).strftime("%Y-%m-%d")
            },
            "total_dividends": len(dividend_data)
        }
        
        return success_response(data)
    except Exception as e:
        return handle_tool_exception("get_dividend_calendar", e)


async def get_market_movers(market_type: str = "stocks") -> dict[str, Any]:
    """
    Get current market movers (gainers, losers, most active).
    
    Args:
        market_type: Type of market data ("stocks", "options", "etfs")
    """
    try:
        # Simulate market movers data
        gainers = [
            {"symbol": "NVDA", "change_percent": 8.5, "price": 875.30, "volume": 45000000},
            {"symbol": "AMD", "change_percent": 6.2, "price": 165.45, "volume": 38000000},
            {"symbol": "TSLA", "change_percent": 5.8, "price": 245.67, "volume": 42000000}
        ]
        
        losers = [
            {"symbol": "META", "change_percent": -4.2, "price": 485.20, "volume": 25000000},
            {"symbol": "NFLX", "change_percent": -3.8, "price": 425.30, "volume": 18000000},
            {"symbol": "AMZN", "change_percent": -2.9, "price": 178.45, "volume": 32000000}
        ]
        
        most_active = [
            {"symbol": "SPY", "volume": 85000000, "price": 550.25, "change_percent": 1.2},
            {"symbol": "QQQ", "volume": 62000000, "price": 475.80, "change_percent": 2.1},
            {"symbol": "AAPL", "volume": 55000000, "price": 185.50, "change_percent": 0.8}
        ]
        
        data = {
            "market_type": market_type,
            "timestamp": datetime.now().isoformat(),
            "gainers": gainers,
            "losers": losers,
            "most_active": most_active
        }
        
        return success_response(data)
    except Exception as e:
        return handle_tool_exception("get_market_movers", e)


async def get_sector_performance() -> dict[str, Any]:
    """
    Get sector performance data showing gains/losses by industry sector.
    """
    try:
        # Simulate sector performance data
        sectors = [
            {"sector": "Technology", "change_percent": 2.8, "market_cap": 45000000000000},
            {"sector": "Healthcare", "change_percent": 1.5, "market_cap": 25000000000000},
            {"sector": "Financial Services", "change_percent": 0.9, "market_cap": 35000000000000},
            {"sector": "Consumer Cyclical", "change_percent": 0.2, "market_cap": 20000000000000},
            {"sector": "Energy", "change_percent": -0.5, "market_cap": 8000000000000},
            {"sector": "Utilities", "change_percent": -1.2, "market_cap": 12000000000000},
            {"sector": "Real Estate", "change_percent": -1.8, "market_cap": 6000000000000}
        ]
        
        data = {
            "timestamp": datetime.now().isoformat(),
            "sectors": sectors,
            "best_performing": max(sectors, key=lambda x: x["change_percent"]),
            "worst_performing": min(sectors, key=lambda x: x["change_percent"])
        }
        
        return success_response(data)
    except Exception as e:
        return handle_tool_exception("get_sector_performance", e)


async def get_premarket_data(symbol: str) -> dict[str, Any]:
    """
    Get pre-market trading data for a specific symbol.
    
    Args:
        symbol: Stock symbol (e.g., "AAPL")
    """
    try:
        symbol = symbol.strip().upper()
        
        # Simulate pre-market data
        current_time = datetime.now()
        
        data = {
            "symbol": symbol,
            "timestamp": current_time.isoformat(),
            "premarket_price": 185.75,
            "premarket_change": 2.25,
            "premarket_change_percent": 1.23,
            "premarket_volume": 1250000,
            "previous_close": 183.50,
            "premarket_high": 186.20,
            "premarket_low": 183.80,
            "session_start": "04:00:00",
            "session_end": "09:30:00"
        }
        
        return success_response(data)
    except Exception as e:
        return handle_tool_exception("get_premarket_data", e)


async def get_afterhours_data(symbol: str) -> dict[str, Any]:
    """
    Get after-hours trading data for a specific symbol.
    
    Args:
        symbol: Stock symbol (e.g., "AAPL")
    """
    try:
        symbol = symbol.strip().upper()
        
        # Simulate after-hours data
        current_time = datetime.now()
        
        data = {
            "symbol": symbol,
            "timestamp": current_time.isoformat(),
            "afterhours_price": 187.30,
            "afterhours_change": 1.80,
            "afterhours_change_percent": 0.97,
            "afterhours_volume": 850000,
            "regular_close": 185.50,
            "afterhours_high": 187.85,
            "afterhours_low": 185.20,
            "session_start": "16:00:00",
            "session_end": "20:00:00"
        }
        
        return success_response(data)
    except Exception as e:
        return handle_tool_exception("get_afterhours_data", e)


async def get_economic_calendar(days_ahead: int = 7) -> dict[str, Any]:
    """
    Get upcoming economic events and indicators.
    
    Args:
        days_ahead: Number of days to look ahead (default 7)
    """
    try:
        # Simulate economic calendar data
        today = datetime.now()
        events = []
        
        # Simulate some economic events
        event_types = [
            {"name": "Federal Reserve Interest Rate Decision", "impact": "high"},
            {"name": "Consumer Price Index (CPI)", "impact": "high"},
            {"name": "Non-Farm Payrolls", "impact": "high"},
            {"name": "GDP Growth Rate", "impact": "medium"},
            {"name": "Consumer Confidence Index", "impact": "medium"},
            {"name": "Manufacturing PMI", "impact": "low"}
        ]
        
        for i in range(days_ahead):
            date = today + timedelta(days=i)
            if i % 2 == 0:  # Add events every other day
                event = event_types[i % len(event_types)]
                events.append({
                    "date": date.strftime("%Y-%m-%d"),
                    "time": "08:30:00" if event["impact"] == "high" else "10:00:00",
                    "event_name": event["name"],
                    "impact": event["impact"],
                    "currency": "USD",
                    "previous_value": "5.2%" if "Rate" in event["name"] else "2.1%",
                    "forecast": "5.0%" if "Rate" in event["name"] else "2.0%"
                })
        
        data = {
            "economic_calendar": events,
            "date_range": {
                "start": today.strftime("%Y-%m-%d"),
                "end": (today + timedelta(days=days_ahead-1)).strftime("%Y-%m-%d")
            },
            "total_events": len(events)
        }
        
        return success_response(data)
    except Exception as e:
        return handle_tool_exception("get_economic_calendar", e)


async def get_news_feed(symbol: str = "", limit: int = 20) -> dict[str, Any]:
    """
    Get financial news feed for a specific symbol or general market news.
    
    Args:
        symbol: Stock symbol for company-specific news (optional)
        limit: Maximum number of news items to return (default 20)
    """
    try:
        # Simulate news feed data
        current_time = datetime.now()
        
        base_news = [
            {
                "headline": "Federal Reserve Signals Potential Rate Cut",
                "summary": "Fed officials indicate possible monetary policy easing in upcoming meetings",
                "source": "Reuters",
                "category": "macroeconomic",
                "sentiment": "neutral",
                "relevance_score": 0.85
            },
            {
                "headline": "Tech Sector Shows Strong Earnings Growth",
                "summary": "Major technology companies report better-than-expected quarterly results",
                "source": "Bloomberg",
                "category": "earnings",
                "sentiment": "positive",
                "relevance_score": 0.78
            },
            {
                "headline": "Oil Prices Rise on Supply Concerns",
                "summary": "Crude oil futures gain on geopolitical tensions and supply disruptions",
                "source": "CNBC",
                "category": "commodities",
                "sentiment": "neutral",
                "relevance_score": 0.65
            }
        ]
        
        # Add symbol-specific news if symbol provided
        if symbol:
            symbol = symbol.strip().upper()
            symbol_news = {
                "headline": f"{symbol} Announces Strategic Partnership",
                "summary": f"{symbol} enters into significant business partnership affecting growth prospects",
                "source": "MarketWatch",
                "category": "corporate",
                "sentiment": "positive",
                "relevance_score": 0.92
            }
            base_news.insert(0, symbol_news)
        
        # Add timestamps to news items
        news_items = []
        for i, news in enumerate(base_news[:limit]):
            news_with_time = news.copy()
            news_with_time["timestamp"] = (current_time - timedelta(hours=i)).isoformat()
            news_with_time["article_id"] = f"news_{i+1:04d}"
            news_items.append(news_with_time)
        
        data = {
            "symbol": symbol if symbol else "MARKET",
            "news_items": news_items,
            "total_items": len(news_items),
            "last_updated": current_time.isoformat()
        }
        
        return success_response(data)
    except Exception as e:
        return handle_tool_exception("get_news_feed", e)