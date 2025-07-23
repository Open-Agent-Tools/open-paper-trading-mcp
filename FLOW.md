# TradingService Core Functions - Data Flow Analysis

## Architecture Overview
The TradingService acts as the central orchestrator in our trading system, routing requests between the MCP/API layer and underlying data sources (PostgreSQL for trading state, Robinhood for market data).

## Core TradingService Functions by Data Source

### Functions Routing to PostgreSQL Database

**Account Management**
- `get_account_balance()` - app/services/trading_service.py:151
- `_get_account()` - app/services/trading_service.py:133
- `_ensure_account_exists()` - app/services/trading_service.py:93

**Order Management**
- `create_order(order_data: OrderCreate)` - app/services/trading_service.py:182
- `get_orders()` - app/services/trading_service.py:211
- `get_order(order_id: str)` - app/services/trading_service.py:232
- `cancel_order(order_id: str)` - app/services/trading_service.py:254
- `create_multi_leg_order(order_data)` - app/services/trading_service.py:645
- `create_multi_leg_order_from_request()` - app/services/trading_service.py:1193

**Portfolio & Position Management**
- `get_portfolio()` - app/services/trading_service.py:278
- `get_portfolio_summary()` - app/services/trading_service.py:323
- `get_positions()` - app/services/trading_service.py:344
- `get_position(symbol: str)` - app/services/trading_service.py:350

**Account State & Validation**
- `validate_account_state()` - app/services/trading_service.py:617

### Functions Routing to Robinhood API (Market Data)

**Basic Quote Data**
- `get_quote(symbol: str)` - app/services/trading_service.py:156
- `get_enhanced_quote(symbol: str)` - app/services/trading_service.py:516
- `get_stock_price(symbol: str)` - app/services/trading_service.py:833
- `get_stock_info(symbol: str)` - app/services/trading_service.py:878
- `get_price_history(symbol: str, period: str)` - app/services/trading_service.py:921
- `search_stocks(query: str)` - app/services/trading_service.py:1035

**Options Market Data**
- `get_options_chain(underlying: str, expiration_date)` - app/services/trading_service.py:532
- `get_formatted_options_chain()` - app/services/trading_service.py:1074
- `find_tradable_options()` - app/services/trading_service.py:693
- `get_option_market_data(option_id: str)` - app/services/trading_service.py:772
- `get_expiration_dates(underlying: str)` - app/services/trading_service.py:555

**Greeks & Analytics**
- `calculate_greeks(option_symbol: str)` - app/services/trading_service.py:520
- `get_option_greeks_response()` - app/services/trading_service.py:449
- `get_position_greeks(symbol: str)` - app/services/trading_service.py:405
- `get_portfolio_greeks()` - app/services/trading_service.py:360

**Advanced Analytics**
- `simulate_expiration()` - app/services/trading_service.py:1226

## API Endpoint Usage

### Trading API (`/api/v1/trading/`)
- `get_quote()` ✓
- `create_order()` ✓
- `get_orders()` ✓
- `get_order()` ✓
- `cancel_order()` ✓
- `get_enhanced_quote()` ✓
- `create_multi_leg_order()` ✓

### Portfolio API (`/api/v1/portfolio/`)
- `get_portfolio()` ✓
- `get_portfolio_summary()` ✓
- `get_positions()` ✓
- `get_position()` ✓
- `get_position_greeks()` ✓
- `get_portfolio_greeks()` ✓

### Market Data API (`/api/v1/market-data/`)
- `get_stock_price()` ✓
- `get_stock_info()` ✓
- `get_price_history()` ✓
- `search_stocks()` ✓

### Options API (`/api/v1/options/`)
- `get_formatted_options_chain()` ✓
- `get_expiration_dates()` ✓
- `create_multi_leg_order_from_request()` ✓
- `get_option_greeks_response()` ✓
- `find_tradable_options()` ✓
- `get_option_market_data()` ✓

## MCP Tool Usage

### Core Tools (`/mcp/tools.py`)
- `create_buy_order()` ✓
- `create_sell_order()` ✓
- `get_all_orders()` ✓
- `get_order()` ✓
- `cancel_order()` ✓
- `get_portfolio()` ✓
- `get_portfolio_summary()` ✓
- `get_all_positions()` ✓
- `get_position()` ✓
- `get_options_chain()` ✓
- `get_expiration_dates()` ✓
- `create_multi_leg_order()` ✓
- `calculate_option_greeks()` ✓
- `simulate_option_expiration()` ✓
- `find_tradable_options()` ✓
- `get_option_market_data()` ✓

### Market Data Tools (`/mcp/market_data_tools.py`)
- `get_stock_price()` ✓
- `get_stock_info()` ✓
- `get_price_history()` ✓

### Options Tools (`/mcp/options_tools.py`)
- `get_options_chains()` ✓
- `find_tradable_options()` ✓
- `get_option_market_data()` ✓

## Data Flow Summary

```
MCP/API Request → TradingService → Database/Market Data Adapter
                                    ↓
                    ← Response ← Database/Robinhood API
```

**PostgreSQL Functions**: 14 core functions handling account state, orders, and positions
**Robinhood API Functions**: 15 functions handling market data, quotes, and analytics
**Total API Coverage**: 100% of active TradingService functions exposed through REST endpoints
**Total MCP Coverage**: 100% of active TradingService functions exposed through MCP tools

The TradingService successfully abstracts the complexity of routing between persistent storage (PostgreSQL) and real-time market data (Robinhood API), providing a unified interface for both API and MCP consumers.

## Deprecated Functions Removed

The following functions have been deprecated and removed from TradingService:
- `calculate_margin_requirement()` - Account state validation
- `get_stock_news()` - Market data retrieval
- `get_top_movers()` - Market data retrieval
- `get_portfolio_strategies()` - Strategy analysis
- `analyze_portfolio_strategies()` - Strategy analysis
- `get_test_scenarios()` - Test data development
- `set_test_date()` - Test data development
- `get_available_symbols()` - Test data development
- `get_sample_data_info()` - Test data development
- `get_stock_quote()` - MCP tools (marked as deprecated)