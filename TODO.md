# Open Paper Trading MCP - Development Roadmap

## 🧪 Test Coverage Requirements
**All new function implementations must include unit tests with ≥70% code coverage.**
- Coverage measured using `pytest-cov` with branch coverage enabled
- Test files should follow naming convention: `test_<module_name>.py` 
- Integration tests required for multi-component interactions
- Performance tests required for high-volume operations

### Priority 1: MCP Tools Implementation (Target: 84 tools per MCP_TOOLS.md)
**Current Status: 17/84 tools implemented (~20% complete)**
**Goal:** Complete the MCP tools interface to match the target specification, providing full AI agent functionality.

**Core System Tools (Missing: 2/2)**
- [ ] Implement `list_tools() -> dict[str, Any]`
- [ ] Implement `health_check() -> dict[str, Any]`
- [ ] Write unit tests for core system tools (target: ≥70% coverage)

**Account & Portfolio Tools (Missing: 3/4, 1 signature fix)**
- [ ] Implement `account_info() -> dict[str, Any]`
- [ ] Fix `get_portfolio()` → `portfolio() -> dict[str, Any]` (signature correction)
- [ ] Fix `get_portfolio_summary()` → `account_details() -> dict[str, Any]` (rename/signature)
- [ ] Fix `get_all_positions()` → `positions() -> dict[str, Any]` (rename/signature)
- [ ] Write unit tests for account & portfolio tools (target: ≥70% coverage)

**Market Data Tools (Missing: 8/8)**
- [ ] Implement `stock_price(symbol: str) -> dict[str, Any]`
- [ ] Implement `stock_info(symbol: str) -> dict[str, Any]`
- [ ] Implement `search_stocks_tool(query: str) -> dict[str, Any]`
- [ ] Implement `market_hours() -> dict[str, Any]`
- [ ] Implement `price_history(symbol: str, period: str = "week") -> dict[str, Any]`
- [ ] Implement `stock_ratings(symbol: str) -> dict[str, Any]`
- [ ] Implement `stock_events(symbol: str) -> dict[str, Any]`
- [ ] Implement `stock_level2_data(symbol: str) -> dict[str, Any]`
- [ ] Write unit tests for market data tools (target: ≥70% coverage)

**Order Management Tools (Missing: 3/4, 1 signature fix)**
- [ ] Fix `get_all_orders()` → `stock_orders() -> dict[str, Any]` (rename/signature)
- [ ] Implement `options_orders() -> dict[str, Any]`
- [ ] Implement `open_stock_orders() -> dict[str, Any]`
- [ ] Implement `open_option_orders() -> dict[str, Any]`
- [ ] Write unit tests for order management tools (target: ≥70% coverage)

**Options Trading Tools (Missing: 8/11, 3 signature fixes)**
- [ ] Fix `get_options_chain()` → `options_chains(symbol: str) -> dict[str, Any]` (signature)
- [ ] Fix `find_tradable_options()` → `find_options(symbol, expiration_date, option_type) -> dict[str, Any]`
- [ ] Fix `get_option_market_data()` → `option_market_data(option_id: str) -> dict[str, Any]`
- [ ] Implement `option_historicals(symbol, expiration_date, strike_price, option_type, interval, span) -> dict[str, Any]`
- [ ] Implement `aggregate_option_positions() -> dict[str, Any]`
- [ ] Implement `all_option_positions() -> dict[str, Any]`
- [ ] Implement `open_option_positions() -> dict[str, Any]`
- [ ] Write unit tests for options trading tools (target: ≥70% coverage)

**Order Cancellation Tools (Missing: 3/4, 1 signature fix)**
- [ ] Fix `cancel_order()` → `cancel_stock_order_by_id(order_id: str) -> dict[str, Any]`
- [ ] Implement `cancel_option_order_by_id(order_id: str) -> dict[str, Any]`
- [ ] Implement `cancel_all_stock_orders_tool() -> dict[str, Any]`
- [ ] Implement `cancel_all_option_orders_tool() -> dict[str, Any]`
- [ ] Write unit tests for order cancellation tools (target: ≥70% coverage)

**Basic Stock Trading Tools (Missing: 2/2, replace existing create_buy_order/create_sell_order)**
- [ ] `buy_stock_market(symbol: str, quantity: int) -> dict[str, Any]`
- [ ] `sell_stock_market(symbol: str, quantity: int) -> dict[str, Any]`
- [ ] Write unit tests for basic stock trading tools (target: ≥70% coverage)

**Architecture Updates for MCP Tools:**
- [ ] Update all existing tools to return `dict[str, Any]` instead of JSON strings
- [ ] Replace Pydantic model parameters with direct function parameters per MCP_TOOLS.md spec
- [ ] Implement standardized response format with `result` field containing `status` and `data`/`error`

### Priority 2: Advanced Order Management & Execution
**Goal:** Implement sophisticated order types and execution capabilities for realistic trading simulation.
**Clarification:** This Priority introduces stateful, long-running processes. The `OrderExecutionEngine` will be a persistent, background service that operates independently of the API request/response cycle.

#### 2.1 Background Order Processing
- [ ] Implement background order monitoring within TradingService.
- [ ] Create async order execution loops for processing trigger conditions.
- [ ] Implement order state tracking and failure handling.
- [ ] Write unit tests for background order processing (target: ≥70% coverage)
**Clarification:** Background processing will be handled directly within the TradingService using asyncio tasks, maintaining the simplified architecture without external message brokers.

#### 2.2 Advanced Order Types
- [ ] Update `OrderType` enum in `app/schemas/orders.py` (e.g., stop_loss, stop_limit, trailing_stop).
- [ ] Add trigger fields to the `DBOrder` model (e.g., `stop_price`, `trail_percent`).
- [ ] Implement validation logic for complex order types.
- [ ] Implement MCP tools for advanced order types:
    - [ ] `buy_stock_limit(symbol: str, quantity: int, limit_price: float) -> dict[str, Any]`
    - [ ] `sell_stock_limit(symbol: str, quantity: int, limit_price: float) -> dict[str, Any]`
    - [ ] `buy_stock_stop_loss(symbol: str, quantity: int, stop_price: float) -> dict[str, Any]`
    - [ ] `sell_stock_stop_loss(symbol: str, quantity: int, stop_price: float) -> dict[str, Any]`
    - [ ] `buy_stock_trailing_stop(symbol: str, quantity: int, trail_amount: float) -> dict[str, Any]`
    - [ ] `sell_stock_trailing_stop(symbol: str, quantity: int, trail_amount: float) -> dict[str, Any]`
    - [ ] `buy_option_limit(instrument_id: str, quantity: int, limit_price: float) -> dict[str, Any]`
    - [ ] `sell_option_limit(instrument_id: str, quantity: int, limit_price: float) -> dict[str, Any]`
    - [ ] `option_credit_spread(short_instrument_id, long_instrument_id, quantity, credit_price) -> dict[str, Any]`
    - [ ] `option_debit_spread(short_instrument_id, long_instrument_id, quantity, debit_price) -> dict[str, Any]`
- [ ] Write unit tests for advanced order types (target: ≥70% coverage)

#### 2.3 Order Execution Engine
- [ ] Build `OrderExecutionEngine` to monitor market data and execute orders when trigger conditions are met.
- [ ] Implement order execution monitoring and trigger evaluation.
- [ ] Add order state management for pending advanced orders.
- [ ] Write unit tests for order execution engine (target: ≥70% coverage)

#### 2.4 Risk Management
- [ ] Implement pre-trade risk analysis and position impact simulation.
- [ ] Add advanced validation for complex order combinations.
- [ ] Calculate portfolio risk metrics (e.g., VaR, exposure limits).
- [ ] Write unit tests for risk management components (target: ≥70% coverage)

#### 2.5 Testing & Validation
- [ ] Write unit and integration tests for all advanced order types and execution logic.
- [ ] Create performance tests for high-volume order processing.
- [ ] Test edge cases (e.g., market hours, holidays, halted stocks).

### Priority 3: User Authentication & Multi-Tenancy
**Goal:** Implement a secure, production-grade user management and authentication system.
**Clarification:** This is a security-critical phase. Multi-tenancy must ensure strict data isolation between users at the database level.

#### 3.1 User Management & JWT Authentication
- [ ] Create User model and schemas with password hashing (`passlib`).
- [ ] Implement JWT token system with access/refresh token patterns.
- [ ] Implement user registration, profile management, and secure token storage.
- [ ] Write unit tests for user management & JWT authentication (target: ≥70% coverage)

#### 3.2 API Security & Multi-Tenancy
- [ ] Secure all relevant FastAPI endpoints with token based authentication.
- [ ] Implement account isolation and data segregation at the database query level.
- [ ] Add permission-based access control for trading operations.
- [ ] Write unit tests for API security & multi-tenancy (target: ≥70% coverage)

#### 3.3 Security & Compliance
- [ ] Implement audit logging for all user actions.
- [ ] Write unit tests for security & compliance features (target: ≥70% coverage)

### Priority 4: Advanced Features & User Experience
**Goal:** Enhance the platform with a frontend, advanced tools, and educational features.
**Clarification:** The frontend should be a separate SPA that communicates with the backend via the REST API.

#### 4.1 Frontend Dashboard
- [ ] Develop a React/Vue dashboard with portfolio(s) status and interactive charts.
- [ ] Write unit tests for frontend components (target: ≥70% coverage)

#### 4.2 Backtesting & Strategy Framework
- [ ] Implement historical backtesting engine with strategy development tools.
- [ ] Add portfolio performance analysis and metrics visualization.
- [ ] Write unit tests for backtesting & strategy framework (target: ≥70% coverage)

### Priority 5: Developer Experience & Documentation
- [ ] Create sequence diagrams showing the request flow through the system.
- [ ] Enhanced API documentation and developer guides.
- [ ] Performance monitoring and observability tools.

---
