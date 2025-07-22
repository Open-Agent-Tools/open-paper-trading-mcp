# Open Stocks MCP Tools Documentation

This document provides a comprehensive list of all 84 MCP tools available in the Open Stocks MCP server v0.5.0, including their signatures and descriptions.

## Core System Tools

### `list_tools() -> dict[str, Any]`
Provides a list of available tools and their descriptions.

### `health_check() -> dict[str, Any]`
Gets health status of the MCP server.

## Account & Portfolio Tools

### `account_info() -> dict[str, Any]`
Gets basic Robinhood account information.

### `portfolio() -> dict[str, Any]`
Provides a high-level overview of the portfolio.

### `account_details() -> dict[str, Any]`
Gets comprehensive account details including buying power and cash balances.

### `positions() -> dict[str, Any]`
Gets current stock positions with quantities and values.

## Market Data Tools

### `stock_price(symbol: str) -> dict[str, Any]`
Gets current stock price and basic metrics.
- **symbol**: Stock ticker symbol (e.g., "AAPL")

### `stock_info(symbol: str) -> dict[str, Any]`
Gets detailed company information and fundamentals.
- **symbol**: Stock ticker symbol (e.g., "AAPL")

### `search_stocks_tool(query: str) -> dict[str, Any]`
Searches for stocks by symbol or company name.
- **query**: Search query (symbol or company name)

### `market_hours() -> dict[str, Any]`
Gets current market hours and status.

### `price_history(symbol: str, period: str = "week") -> dict[str, Any]`
Gets historical price data for a stock.
- **symbol**: Stock ticker symbol (e.g., "AAPL")
- **period**: Time period ("day", "week", "month", "3month", "year", "5year")

### `stock_ratings(symbol: str) -> dict[str, Any]`
Gets analyst ratings for a stock.
- **symbol**: Stock ticker symbol (e.g., "AAPL")

### `stock_events(symbol: str) -> dict[str, Any]`
Gets corporate events for a stock (for owned positions).
- **symbol**: Stock ticker symbol (e.g., "AAPL")

### `stock_level2_data(symbol: str) -> dict[str, Any]`
Gets Level II market data for a stock (Gold subscription required).
- **symbol**: Stock ticker symbol (e.g., "AAPL")


## Order Management Tools

### `stock_orders() -> dict[str, Any]`
Retrieves a list of recent stock order history and their statuses.

### `options_orders() -> dict[str, Any]`
Retrieves a list of recent options order history and their statuses.

### `open_stock_orders() -> dict[str, Any]`
Retrieves all open stock orders.

### `open_option_orders() -> dict[str, Any]`
Retrieves all open option orders.

## Options Trading Tools

### `options_chains(symbol: str) -> dict[str, Any]`
Gets complete option chains for a stock symbol.
- **symbol**: Stock ticker symbol (e.g., "AAPL")

### `find_options(symbol: str, expiration_date: str | None = None, option_type: str | None = None) -> dict[str, Any]`
Finds tradable options with optional filtering.
- **symbol**: Stock ticker symbol (e.g., "AAPL")
- **expiration_date**: Optional expiration date in YYYY-MM-DD format
- **option_type**: Optional option type ("call" or "put")

### `option_market_data(option_id: str) -> dict[str, Any]`
Gets market data for a specific option contract.
- **option_id**: Unique option contract ID

### `option_historicals(symbol: str, expiration_date: str, strike_price: str, option_type: str, interval: str = "hour", span: str = "week") -> dict[str, Any]`
Gets historical price data for an option contract.
- **symbol**: Stock ticker symbol (e.g., "AAPL")
- **expiration_date**: Expiration date in YYYY-MM-DD format
- **strike_price**: Strike price as string
- **option_type**: Option type ("call" or "put")
- **interval**: Time interval (default: "hour")
- **span**: Time span (default: "week")

### `aggregate_option_positions() -> dict[str, Any]`
Gets aggregated option positions collapsed by underlying stock.

### `all_option_positions() -> dict[str, Any]`
Gets all option positions ever held.

### `open_option_positions() -> dict[str, Any]`
Gets currently open option positions.

## Stock Trading Tools

### `buy_stock_market(symbol: str, quantity: int) -> dict[str, Any]`
Places a market buy order for a stock.
- **symbol**: The stock symbol to buy (e.g., "AAPL")
- **quantity**: The number of shares to buy

### `sell_stock_market(symbol: str, quantity: int) -> dict[str, Any]`
Places a market sell order for a stock.
- **symbol**: The stock symbol to sell (e.g., "AAPL")
- **quantity**: The number of shares to sell

### `buy_stock_limit(symbol: str, quantity: int, limit_price: float) -> dict[str, Any]`
Places a limit buy order for a stock.
- **symbol**: The stock symbol to buy (e.g., "AAPL")
- **quantity**: The number of shares to buy
- **limit_price**: The maximum price per share

### `sell_stock_limit(symbol: str, quantity: int, limit_price: float) -> dict[str, Any]`
Places a limit sell order for a stock.
- **symbol**: The stock symbol to sell (e.g., "AAPL")
- **quantity**: The number of shares to sell
- **limit_price**: The minimum price per share

### `buy_stock_stop_loss(symbol: str, quantity: int, stop_price: float) -> dict[str, Any]`
Places a stop loss buy order for a stock.
- **symbol**: The stock symbol to buy (e.g., "AAPL")
- **quantity**: The number of shares to buy
- **stop_price**: The stop price that triggers the order

### `sell_stock_stop_loss(symbol: str, quantity: int, stop_price: float) -> dict[str, Any]`
Places a stop loss sell order for a stock.
- **symbol**: The stock symbol to sell (e.g., "AAPL")
- **quantity**: The number of shares to sell
- **stop_price**: The stop price that triggers the order

### `buy_stock_trailing_stop(symbol: str, quantity: int, trail_amount: float) -> dict[str, Any]`
Places a trailing stop buy order for a stock.
- **symbol**: The stock symbol to buy (e.g., "AAPL")
- **quantity**: The number of shares to buy
- **trail_amount**: The trailing amount (percentage or dollar amount)

### `sell_stock_trailing_stop(symbol: str, quantity: int, trail_amount: float) -> dict[str, Any]`
Places a trailing stop sell order for a stock.
- **symbol**: The stock symbol to sell (e.g., "AAPL")
- **quantity**: The number of shares to sell
- **trail_amount**: The trailing amount (percentage or dollar amount)


## Options Trading Tools

### `buy_option_limit(instrument_id: str, quantity: int, limit_price: float) -> dict[str, Any]`
Places a limit buy order for an option.
- **instrument_id**: The option instrument ID
- **quantity**: The number of option contracts to buy
- **limit_price**: The maximum price per contract

### `sell_option_limit(instrument_id: str, quantity: int, limit_price: float) -> dict[str, Any]`
Places a limit sell order for an option.
- **instrument_id**: The option instrument ID
- **quantity**: The number of option contracts to sell
- **limit_price**: The minimum price per contract

### `option_credit_spread(short_instrument_id: str, long_instrument_id: str, quantity: int, credit_price: float) -> dict[str, Any]`
Places a credit spread order (sell short option, buy long option).
- **short_instrument_id**: The option instrument ID to sell (short leg)
- **long_instrument_id**: The option instrument ID to buy (long leg)
- **quantity**: The number of spread contracts
- **credit_price**: The net credit received per spread

### `option_debit_spread(short_instrument_id: str, long_instrument_id: str, quantity: int, debit_price: float) -> dict[str, Any]`
Places a debit spread order (buy long option, sell short option).
- **short_instrument_id**: The option instrument ID to sell (short leg)
- **long_instrument_id**: The option instrument ID to buy (long leg)
- **quantity**: The number of spread contracts
- **debit_price**: The net debit paid per spread

## Order Cancellation Tools

### `cancel_stock_order_by_id(order_id: str) -> dict[str, Any]`
Cancels a specific stock order.
- **order_id**: The ID of the order to cancel

### `cancel_option_order_by_id(order_id: str) -> dict[str, Any]`
Cancels a specific option order.
- **order_id**: The ID of the order to cancel

### `cancel_all_stock_orders_tool() -> dict[str, Any]`
Cancels all open stock orders.

### `cancel_all_option_orders_tool() -> dict[str, Any]`
Cancels all open option orders.

---

## Tool Response Format

All tools return JSON responses with a standardized `result` field containing the data or error information:

```json
{
  "result": {
    "status": "success",
    "data": { ... }
  }
}
```

Error responses follow the same format:

```json
{
  "result": {
    "error": "Error description",
    "status": "error"
  }
}
```