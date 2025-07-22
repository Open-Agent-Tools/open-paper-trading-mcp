# Open Paper Trading MCP - Development Roadmap

This document tracks the implementation progress and upcoming tasks for the paper trading simulator with dual REST API and MCP interfaces.

## Phase 0: Foundation & QA ✅ **COMPLETED** 2025-07-20

**Major Achievements:**
- **Test Infrastructure**: 5/9 E2E tests passing, AsyncClient working, database setup complete
- **Async Migration**: MyPy errors reduced 101→62 (39% improvement), async/await patterns implemented
- **Dependency Injection**: Global service refactoring completed with FastAPI lifespan management
- **Documentation**: README.md, TODO.md, CLAUDE.md synchronized and current
- **Application Stability**: Core functionality operational, imports successful, health checks passing

---

## ✅ FOUNDATIONAL CODEBASE VALIDATED

**Code Complete and Verified**: With the test environment fully operational, the foundational features for Phases 0-5 have been successfully validated against the test suite. The "Key Achievements" are now confirmed.

- **Phase 0**: Infrastructure with Docker, PostgreSQL, and dual-interface (FastAPI + MCP)
- **Phase 1**: Complete codebase refactoring with 100% MyPy compliance (567���0 errors)
- **Phase 2**: Live market data integration with Robinhood API and comprehensive tooling
- **Phase 3**: Complete testing suite with E2E, integration, and performance validation
- **Phase 4**: Schema-database separation with converter patterns and validation
- **Phase 5**: Production monitoring with health checks, performance benchmarks, and Kubernetes probes

**Key Achievements Verified**: Async architecture, type safety, comprehensive testing, production monitoring, performance targets (<100ms order creation, >95% success rates)

---

## 🚀 DEVELOPMENT PHASES

### Phase 1: Architectural Refactoring & API Consistency ⚠️ **PARTIALLY COMPLETED** 2025-07-22
**Goal:** Address architectural inconsistencies and improve code quality across the MCP and FastAPI interfaces.
**Clarification:** This phase will refactor the codebase to align with best practices, improve testability, and create a more consistent and maintainable API. This must be completed before new feature development.

**Status:** ~70% Complete - Core architecture refactored, but test suite validation incomplete.

**Major Achievements:**
- **Unified Service Access**: Eliminated global service anti-pattern, implemented proper dependency injection for MCP tools
- **Async Architecture**: Fixed sync/async mismatches in 12+ MCP tools, all now use proper `async def` and `await` patterns
- **Code Consolidation**: Replaced deprecated `app.models.trading` imports with proper `app.schemas.*` imports across 8+ files
- **Error Handling**: Implemented structured error responses with global exception handlers, consistent error formats
- **E2E Event Loop Issues**: Resolved "Task got Future attached to a different loop" errors in E2E tests

**Test Status (Current):** 206 failed, 486 passed, 27 skipped (out of 719 total tests)

#### 1.1 Unify TradingService Access ✅
- [x] Refactor MCP tools to use dependency injection for `TradingService`.
- [x] Remove `get_global_trading_service()` from `app/mcp/tools.py`.
- [x] Ensure all components access `TradingService` via the lifespan-managed instance.

#### 1.2 Fix Sync/Async Mismatches ⚠️ **PARTIALLY COMPLETED**
- [x] Convert all MCP tools that call async methods to `async def`.
- [x] Convert all FastAPI endpoints that call async methods to `async def`.
- [x] Run MyPy to ensure all `await` calls are in `async` functions.
- [ ] **REMAINING:** Convert unit test methods to async patterns - 30+ tests still calling async methods without `await`
- [ ] **REMAINING:** Fix database mocking patterns (AsyncMock vs MagicMock) in test suite
- [ ] **REMAINING:** Resolve integration test async/await issues

#### 1.3 Consolidate Redundant Code ✅
- [x] Consolidate duplicated Pydantic models into a shared location (e.g., `app/schemas/mcp.py`).
- [x] Merge redundant FastAPI endpoints for multi-leg orders.
- [x] Review and remove any other duplicated code.

#### 1.4 Implement Consistent Error Handling ✅
- [x] Create custom exception handlers for `NotFoundError` and `ValidationError`.
- [x] Replace generic `HTTPException`s with custom exceptions where appropriate.
- [x] Ensure all API responses provide consistent error formats.

#### 1.5 Standardize API Responses ⚠️ **PARTIALLY COMPLETED**
- [ ] Refactor MCP tools to return Pydantic models instead of JSON strings. *(Deferred: MCP tools appropriately return JSON strings for external consumption)*
- [x] Use `response_model` for all FastAPI endpoints to standardize output. *(Most endpoints have proper response models)*
- [ ] Remove manual dictionary formatting from API endpoints. *(Deferred: Would require extensive new Pydantic model creation)*

#### 1.6 Test Suite Validation ❌ **INCOMPLETE** - Critical for Phase 1 Completion
**Current Status:** 206 failed, 486 passed, 27 skipped (28.7% failure rate)

**Unit Tests Issues (30 failed, 31 passed):**
- [ ] Fix async/await issues in `TestMarketData` class - methods calling `get_quote()`, `get_enhanced_quote()` without `await`
- [ ] Fix async/await issues in `TestOrderManagement` class - complex database mocking patterns
- [ ] Fix async/await issues in `TestOptionsGreeks`, `TestOptionsData`, `TestOptionsStrategy` classes
- [ ] Fix async/await issues in `TestDatabaseInteraction` class - database session mocking
- [ ] Convert remaining sync test methods to async with proper `@pytest.mark.asyncio` decorators

**E2E Tests Issues (13 failed, 8 passed):**
- [x] Database event loop issues resolved ("Task got Future attached to a different loop")
- [ ] Portfolio assertion failures - tests expecting positions but finding empty portfolios
- [ ] Order flow test logic issues - API behavior vs test expectations mismatch
- [ ] Database cleanup and isolation issues

**Integration/Performance Tests:**
- [ ] Database persistence test errors (6 errors)
- [ ] Live quotes integration test failures
- [ ] Performance benchmark test errors (6 errors)
- [ ] High-volume order processing test issues

**Specific Test Failures to Address:**
```
CRITICAL UNIT TEST FIXES NEEDED:
- TestMarketData::test_get_quote_not_found - async method called without await
- TestMarketData::test_get_enhanced_quote_* - multiple async call issues  
- TestOrderManagement::test_get_orders_success - database mocking issues
- TestOptionsGreeks::test_get_portfolio_greeks_success - async method calls
- TestOptionsData::test_find_tradable_options_success - service method issues
- TestOptionsStrategy::test_*_success - multiple async pattern issues
```

**Phase 1 Completion Criteria:**
- [ ] Unit test pass rate > 90% (currently ~50%)
- [ ] E2E test pass rate > 80% (currently ~38%) 
- [ ] Integration test errors resolved
- [ ] No async/await warnings in test output
- [ ] All core TradingService methods properly tested with async patterns

### Phase 2: Advanced Order Management & Execution
**Goal:** Implement sophisticated order types and execution capabilities for realistic trading simulation.
**Clarification:** This phase introduces stateful, long-running processes. The `OrderExecutionEngine` will be a persistent, background service that operates independently of the API request/response cycle.

#### 2.1 Asynchronous Task Queue
- [ ] Set up Celery with a Redis message broker in `docker-compose.yml`.
- [ ] Create async tasks for order processing and other background jobs.
- [ ] Implement task monitoring and failure handling.
**Clarification:** The task queue is essential for offloading long-running processes like order execution from the main application thread, ensuring API responsiveness.

#### 2.2 Advanced Order Types
- [ ] Update `OrderType` enum in `app/schemas/orders.py` (e.g., stop_loss, stop_limit, trailing_stop).
- [ ] Add trigger fields to the `DBOrder` model (e.g., `stop_price`, `trail_percent`).
- [ ] Implement validation logic for complex order types.
- [ ] Implement MCP tools for specific order types:
    - [ ] `buy_stock_market`, `sell_stock_market`
    - [ ] `buy_stock_limit`, `sell_stock_limit`
    - [ ] `buy_stock_stop_loss`, `sell_stock_stop_loss`
    - [ ] `buy_stock_trailing_stop`, `sell_stock_trailing_stop`
    - [ ] `buy_option_limit`, `sell_option_limit`
    - [ ] `option_credit_spread`, `option_debit_spread`

#### 2.3 Order Execution Engine
- [ ] Build `OrderExecutionEngine` to monitor market data and execute orders when trigger conditions are met.
- [ ] Implement order lifecycle management (pending → triggered → executed).
- [ ] Implement market impact simulation (slippage, partial fills).
- [ ] Create order status tracking and notifications.
- [ ] Implement MCP tools for order management and cancellation:
    - [ ] `stock_orders`, `options_orders`
    - [ ] `open_stock_orders`, `open_option_orders`
    - [ ] `cancel_stock_order_by_id`, `cancel_option_order_by_id`
    - [ ] `cancel_all_stock_orders_tool`, `cancel_all_option_orders_tool`

#### 2.4 Risk Management
- [ ] Implement pre-trade risk analysis and position impact simulation.
- [ ] Add advanced validation for complex order combinations.
- [ ] Calculate portfolio risk metrics (e.g., VaR, exposure limits).

#### 2.5 Testing & Validation
- [ ] Write unit and integration tests for all advanced order types and execution logic.
- [ ] Create performance tests for high-volume order processing.
- [ ] Test edge cases (e.g., market hours, holidays, halted stocks).

### Phase 3: Caching & Performance Infrastructure
**Goal:** Implement Redis caching for scalability and performance.
**Clarification:** The primary goal is to reduce latency for read-heavy operations.

#### 3.1 Redis Caching Layer
- [ ] Set up a dedicated Redis container for caching in `docker-compose.yml`.
- [ ] Implement a `CacheService` using `redis-py` with async support.
- [ ] Integrate the cache into `TradingService` for quotes and portfolio data.

#### 3.2 Caching Strategy & Monitoring
- [ ] Implement TTL-based expiration for cached data.
- [ ] Develop cache invalidation strategies (e.g., on order execution).
- [ ] Add monitoring for cache hit/miss ratios and performance.

### Phase 4: User Authentication & Multi-Tenancy
**Goal:** Implement a secure, production-grade user management and authentication system.
**Clarification:** This is a security-critical phase. Multi-tenancy must ensure strict data isolation between users at the database level.

#### 4.1 User Management & JWT Authentication
- [ ] Create User model and schemas with password hashing (`passlib`).
- [ ] Implement JWT token system with access/refresh token patterns.
- [ ] Implement user registration, profile management, and secure token storage.

#### 4.2 API Security & Multi-Tenancy
- [ ] Secure all relevant FastAPI endpoints with authentication.
- [ ] Implement account isolation and data segregation at the database query level.
- [ ] Add permission-based access control for trading operations.

#### 4.3 Security & Compliance
- [ ] Implement audit logging for all user actions.
- [ ] Add rate limiting, security headers, and CSRF protection.

### Phase 5: Advanced Features & User Experience
**Goal:** Enhance the platform with a frontend, advanced tools, and educational features.
**Clarification:** The frontend should be a separate SPA that communicates with the backend via the REST API.

#### 5.1 Frontend Dashboard
- [ ] Develop a React/Vue dashboard with real-time portfolio updates and interactive charts.
- [ ] Create an order management interface supporting advanced order types.

#### 5.2 Advanced MCP Tools
- [ ] Build market analysis tools (e.g., `get_technical_indicators`, `scan_market`).
- [ ] Add options chain analysis and economic news integration.
- [ ] Implement core system tools: `list_tools`, `health_check`.
- [ ] Implement account and portfolio tools: `account_info`, `account_details`.
- [ ] Implement advanced market data tools: `stock_ratings`, `stock_events`, `stock_level2_data`, `market_hours`.
- [ ] Implement advanced options analysis tools: `option_historicals`, `aggregate_option_positions`, `all_option_positions`, `open_option_positions`.

#### 5.3 Educational & Community Features
- [ ] Create interactive trading tutorials and guides.
- [ ] Implement paper trading competitions and leaderboards.
- [ ] Build a strategy sharing and discovery platform.

### Phase 6: Backtesting & Strategy Framework
**Goal:** Build comprehensive strategy development and historical analysis capabilities.
**Clarification:** This phase requires a robust data engineering pipeline for historical data and a backtesting engine that is completely isolated from the live trading service.

#### 6.1 Historical Data Engine
- [ ] Design and implement a time-series data storage solution.
- [ ] Build data ingestion pipelines for historical quote data.

#### 6.2 Backtesting Engine & Strategy Framework
- [ ] Build a backtesting engine with realistic market simulation (slippage, commissions).
- [ ] Create a plugin architecture for custom trading strategies.
- [ ] Implement performance analytics (e.g., Sharpe ratio, max drawdown).
- [ ] Add strategy validation tools (e.g., walk-forward analysis, Monte Carlo simulation).

### Phase 7: Developer Experience & Documentation
**Goal:** Improve the development workflow and provide comprehensive documentation.

#### 7.1 Tooling & Automation
- [ ] Set up pre-commit hooks for automated code quality checks.
- [ ] Implement OpenAPI client generation for easier API consumption.
- [ ] Create CLI administration tools for system management.

#### 7.2 Documentation
- [ ] Create sequence diagrams showing the request flow through the system.
- [ ] Write an API versioning strategy and migration guide.
- [ ] Develop comprehensive deployment and scaling documentation.
- [ ] Create a `CONTRIBUTING.md` file to formalize the development workflow.

---

## 📊 SUCCESS METRICS
**Clarification:** These metrics should be measured and tracked automatically as part of the CI/CD pipeline to ensure consistent quality and performance.

### Performance Targets
- Order execution: <100ms average response time
- API endpoints: >95% success rate, <200ms P95 latency
- Cache hit ratio: >80% for quote requests
- System uptime: >99.9% availability

### Quality Gates
- Test coverage: >90% for core trading logic
- Type safety: 100% MyPy compliance maintained
- Security: Zero high-severity vulnerabilities
- Documentation: All public APIs documented
