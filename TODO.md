# Open Paper Trading MCP - Development Roadmap

This document tracks the implementation progress and upcoming tasks for the paper trading simulator with dual REST API and MCP interfaces.

## 🧭 Architectural Strategy
The core principle of this platform is the separation of concerns between the **internal state** and **external data**.

- **Paper Trading System (Internal):** Manages all stateful information, including user accounts, portfolios, positions, orders, and trading history. This is the single source of truth for the user's paper trading activity.
- **Live Data Integration (External):** Provides real-time and historical market data for stocks and options. This data is used to enrich the user's portfolio with live pricing and to provide broad market context. It is read-only and does not affect the internal state.

---

## ✅ COMPLETED

### Phase 0: Initial Setup & Core Engine
- [x] **Infrastructure:** Docker containerization with PostgreSQL and ADK test runner.
- [x] **Core Trading Engine:** All fundamental options trading logic, including asset modeling, order execution, account validation, margin calculations, strategy recognition, Greeks, and expiration processing.
- [x] **Dual-Interface:** Both FastAPI (REST) and FastMCP (AI Agent) servers are operational.

---

## 🚧 CURRENT PRIORITY

### Phase 1: Codebase Refactoring & Stabilization
**Goal:** Address significant architectural debt and type-safety issues to create a robust, maintainable foundation before adding new features. This involves a full MyPy-driven refactoring to improve data consistency and reduce runtime errors.

**A comprehensive, multi-phase plan for this effort is documented in `REFACTORING_TODO.md`. This is the next priority and must be completed before work on other phases continues.**

---

## 🚀 PLANNED PHASES

### Phase 2: Live Market Data Integration
**Goal:** Integrate a live, read-only data source (e.g., Robinhood via `open-stocks-mcp`) to provide real-time market context and historical data.

#### 2.1 Foundational Integration
- [ ] **MCP Transport Layer:** Implement the MCP server with an HTTP/SSE (Server-Sent Events) transport to support asynchronous, long-running data lookups for market data tools.
- [ ] **Session Management:** Implement a robust session manager for the live data connection, including authentication and token persistence.
- [ ] **Data Source Abstraction:** Create a clear abstraction layer to cleanly separate live market data queries from internal paper trading data.
- [ ] **Resilience:** Implement consistent error handling, API retries, and rate limiting for the external data source.

#### 2.2 MCP & API Tool Implementation
- [ ] **Market Data Tools (Live Source):**
  - [x] `get_stock_info`
  - [x] `get_price_history`
  - [x] `get_stock_news`
  - [x] `get_top_movers`
  - [x] `search_stocks`
  - [ ] `get_top_100`, `get_stocks_by_tag`
  - [ ] `get_stock_earnings`, `get_stock_ratings`
- [ ] **Options Data Tools (Live Source):**
  - [x] `get_options_chains`
  - [x] `find_tradable_options`
  - [x] `get_option_market_data`
  - [ ] `get_option_historicals`
- [ ] **API Endpoints:**
  - [x] `GET /api/v1/market/info/{symbol}`
  - [x] `GET /api/v1/market/history/{symbol}`
  - [x] `GET /api/v1/market/news/{symbol}`
  - [x] `GET /api/v1/market/movers`
  - [x] `GET /api/v1/market/search`
  - [x] `GET /api/v1/options/{symbol}/live-chain`
  - [x] `GET /api/v1/options/{symbol}/live-chain/search`
  - [x] `GET /api/v1/options/market-data/{option_id}`
  - [ ] Create corresponding REST endpoints for all new market and options data tools.
  - [ ] Update existing portfolio and position endpoints to enrich them with live market prices.

### Phase 3: Comprehensive Testing & Validation
**Goal:** Ensure all existing and newly integrated functionality is robust, correct, and performant through comprehensive testing.

- [ ] **Unit & Integration Testing:**
  - [ ] Write tests for all new live data tools and API endpoints.
  - [ ] Enhance existing tests for the core trading engine (Greeks, order execution, risk management).
  - [ ] Validate all calculations against known financial formulas and reference values.
- [ ] **Test Data & Scenarios:**
  - [ ] Expand test data to include more diverse scenarios (e.g., earnings, dividends, market volatility).
  - [ ] Create examples and documentation for all major API and MCP workflows.
- [ ] **Performance Testing:**
  - [ ] Benchmark API response times and database query performance under load.
  - [ ] Profile critical components like the Greeks calculator for performance bottlenecks.

### Phase 4: Backtesting Framework
**Goal:** Build a robust framework for strategy development and historical performance analysis.

- [ ] **Historical Data Engine:** Utilize the live data integration to fetch and store historical time-series data efficiently.
- [ ] **Strategy Runner:** Design a plugin architecture to allow for the development and execution of custom trading strategies against historical data.
- [ ] **Performance Analytics:** Implement a suite of backtesting metrics (Sharpe Ratio, Sortino Ratio, max drawdown, etc.) and reporting tools.
- [ ] **Simulation Realism:** Model realistic market conditions, including bid-ask spreads, slippage, and commissions.

### Phase 5: Advanced Features & User Interface
**Goal:** Enhance the platform with a user-facing dashboard and more sophisticated trading tools. This phase will likely be split into sub-projects.

- [ ] **Frontend Dashboard:** Develop a web-based UI (React/Vue) for portfolio visualization, interactive charting, and real-time updates.
- [ ] **Advanced MCP Tools:** Implement tools for more complex analysis, such as `get_market_status`, `get_technical_indicators`, and `scan_market`.
- [ ] **Advanced Risk Management:**
  - [ ] Implement pre-trade risk analysis (order impact simulation).
  - [ ] Add compliance rules like Pattern Day Trader (PDT) tracking.
  - [ ] Introduce position sizing calculators and advanced order types (stop-loss, etc.).

---

## 🔭 FUTURE VISION

### Phase 6: Educational & Community Features
- [ ] **Interactive Learning:** Create guided trading tutorials, paper trading competitions, and leaderboards.
- [ ] **Collaboration:** Build a strategy-sharing marketplace for users to exchange ideas.

### Phase 7: Production & Enterprise Readiness
- [ ] **Scalability & Observability:** Implement horizontal scaling, database read replicas, and a full observability stack (Prometheus, Grafana, OpenTelemetry).
- [ ] **Enterprise Features:** Add multi-tenancy, Role-Based Access Control (RBAC), and audit logging.

---

## 🎯 QUICK WINS
*Small, high-impact tasks that can be implemented at any time.*

- [ ] **Developer Experience:** Set up pre-commit hooks, add OpenAPI client generation, and create Docker health checks.
- [ ] **Administration:** Create a CLI for simplified account management and system administration.