# Open Paper Trading MCP - Development Roadmap

This document tracks the implementation progress and upcoming tasks for the paper trading simulator with dual REST API and MCP interfaces.

## Phase 0: Validated QA Findings & Action Plan
**Status:** Validated

This section provides an updated assessment of the project's status, incorporating feedback from the development team and a fresh code review. It supersedes previous QA reports.

### 1. Summary of Findings
The project is more advanced than initially assessed, particularly regarding its stateless architecture. However, critical gaps remain in testing and documentation that block further development and validation.

-   **Architecture:** The `TradingService` is **stateless** and uses a database-first approach, which significantly mitigates risks related to thread safety. This is a major positive.
-   **Testing:** The test environment is **non-functional**. The test suite fails to run due to missing dependencies (`aiosqlite`), making it impossible to verify the "Completed" status of Phases 3, 4, and 5. This is the most critical blocker.
-   **Documentation:** The `README.md` is **outdated** and conflicts with the project's current state regarding dependencies (Robinhood, not Polygon.io) and the development roadmap.

### 2. Priority Action Plan
The following issues must be addressed before proceeding with the feature development phases.

#### P0.1: CRITICAL - Fix the Test Environment
-   [x] **Resolve Dependencies:** Add `aiosqlite` and any other missing packages to the `[dev]` dependencies in `pyproject.toml`. ✅ **COMPLETED 2025-01-20**: Dependencies resolved, test suite now runs successfully.
-   [x] **Add Synchronous Database Support:** Added `get_sync_session()` function for legacy compatibility. ✅ **COMPLETED 2025-01-20**: Tests can now access database properly.
-   [ ] **Fix Database Incompatibility:** The test suite is failing because the SQLAlchemy models use a PostgreSQL-specific `ARRAY` type that is not compatible with the SQLite dialect used for testing. This must be resolved. **Suggestion:** Use a generic type like `JSON` or implement dialect-specific type compilation.
-   [x] **Enable Test Suite:** Ensure `pytest` runs without errors and all existing tests pass. ✅ **PARTIALLY COMPLETED**: Test infrastructure works (206 tests run), but many tests fail due to code issues, not infrastructure.
-   [ ] **Fix Dockerized Runner:** Repair the `test-runner` service in `docker-compose.yml` to provide a reliable, containerized testing environment.
-   **Justification:** Without a functional test suite, no code changes can be safely validated, and the "Key Achievements" related to testing and production-readiness are not verifiable. **No feature development should proceed until this is complete.**

#### P0.2: HIGH - Refactor Global Service Instance
-   [ ] **Remove Global Variable:** Eliminate the global `trading_service` instance in `app/services/trading_service.py`.
-   [ ] **Use Lifespan Injection:** Instantiate `TradingService` within the FastAPI `lifespan` context manager in `app/main.py` and manage it within the application state.
-   [ ] **Update Dependency:** Modify the `get_service` dependency to retrieve the service instance from the application state.
-   **Justification:** Aligns with FastAPI best practices, improves testability by allowing mock services to be injected, and makes the application more robust and maintainable.

#### P0.3: HIGH - Synchronize All Documentation
-   [ ] **Update README.md:** Align the "Feature Roadmap" and dependency information in `README.md` with the details in `TODO.md`. **Clarification:** The roadmap in `TODO.md` should be considered the single source of truth.
-   [ ] **Consolidate Project Status:** Ensure `README.md`, `TODO.md`, and `CLAUDE.md` provide a consistent view of the project's goals and completed work.
-   **Justification:** Provides a single, reliable source of truth for all developers and contributors.

---

## 🧭 Architectural Strategy
The core principle of this platform is the separation of concerns between the **internal state** and **external data**.

- **Paper Trading System (Internal):** Manages all stateful information, including user accounts, portfolios, positions, orders, and trading history. This is the single source of truth for the user's paper trading activity.
- **Live Data Integration (External):** Provides real-time and historical market data for stocks and options. This data is used to enrich the user's portfolio with live pricing and to provide broad market context. It is read-only and does not affect the internal state.

---

##  foundational codebase PENDING VALIDATION

**Code Complete, Awaiting Test Verification**: The codebase for the foundational phases is largely complete, but the features are **not fully validated** due to the non-functional test environment. The "Key Achievements" are goals that must be verified once the test suite is operational. Completion of P0.1 is required to validate these phases.

- **Phase 0**: Infrastructure with Docker, PostgreSQL, and dual-interface (FastAPI + MCP)
- **Phase 1**: Complete codebase refactoring with 100% MyPy compliance (567→0 errors)
- **Phase 2**: Live market data integration with Robinhood API and comprehensive tooling
- **Phase 3**: Complete testing suite with E2E, integration, and performance validation
- **Phase 4**: Schema-database separation with converter patterns and validation
- **Phase 5**: Production monitoring with health checks, performance benchmarks, and Kubernetes probes

**Key Achievements**: Async architecture, type safety, comprehensive testing, production monitoring, performance targets (<100ms order creation, >95% success rates)

---

## 🚀 DEVELOPMENT PHASES

### Phase 1: Advanced Order Management
**Goal:** Implement sophisticated order types and execution capabilities for realistic trading simulation.
**Clarification:** This phase introduces stateful, long-running processes. The `OrderExecutionEngine` should be designed as a persistent, background service that operates independently of the API request/response cycle. It will monitor market data and execute orders when trigger conditions are met. All database modifications must be performed within atomic transactions to ensure data integrity.

#### 1.1 Advanced Order Types
- [ ] Update OrderType enum in `app/schemas/orders.py` (stop_loss, stop_limit, trailing_stop)
- [ ] Add trigger fields to DBOrder model (stop_price, trail_percent, trail_amount)
- [ ] Implement order validation for complex order types
- [ ] Create order conversion logic for triggered orders

#### 1.2 Order Execution Engine
- [ ] Build OrderExecutionEngine with trigger condition monitoring
- [ ] Implement market impact simulation (slippage, partial fills)
- [ ] Add order lifecycle management (pending → triggered → executed)
- [ ] Create order status tracking and notifications

#### 1.3 Risk Management
- [ ] Pre-trade risk analysis with position impact simulation
- [ ] Position sizing calculators for optimal trade sizing
- [ ] Advanced validation for complex order combinations
- [ ] Portfolio risk metrics calculation (VaR, exposure limits)

#### 1.4 Performance Optimization
- [ ] Order processing performance benchmarks
- [ ] Async order queue management
- [ ] Database indexing for order queries
- [ ] Memory-efficient order state tracking

#### 1.5 Testing & Validation
- [ ] Unit tests for all order types and execution logic
- [ ] Integration tests for order lifecycle
- [ ] Performance tests for high-volume order processing
- [ ] Edge case testing (market hours, holidays, halted stocks)

### Phase 2: Caching & Performance Infrastructure
**Goal:** Implement Redis caching and async task processing for scalability and performance.
**Clarification:** The primary goal is to reduce latency for read-heavy operations and offload non-critical tasks from the main application thread. This is critical for scaling the application.

#### 2.1 Redis Caching Layer
- [ ] Set up Redis container in docker-compose.yml
- [ ] Implement CacheService using redis-py with async support
- [ ] Integrate cache into TradingService for quotes and portfolio data
- [ ] Cache warming strategies for frequently accessed symbols

#### 2.2 Quote Caching Strategy
- [ ] Cache popular symbols with TTL-based expiration
- [ ] Implement cache invalidation patterns
- [ ] Quote cache hit/miss monitoring and metrics
- [ ] Fallback mechanisms when cache is unavailable

#### 2.3 Portfolio Data Caching
- [ ] Cache portfolio calculations and position data
- [ ] Smart cache invalidation on order execution
- [ ] Cache warming for user portfolios on login
- [ ] Performance monitoring for cache effectiveness

#### 2.4 Asynchronous Task Queue
- [ ] Set up Celery with Redis message broker
- [ ] Create async tasks for end-of-day processing
- [ ] Implement background portfolio rebalancing tasks
- [ ] Add task monitoring and failure handling
**Clarification:** Use the task queue for operations that are not time-sensitive, such as generating reports or sending email notifications. This will improve API responsiveness.

#### 2.5 Performance Monitoring
- [ ] Cache hit ratio dashboards
- [ ] Task queue performance metrics
- [ ] Memory usage optimization
- [ ] Response time improvements validation

### Phase 3: User Authentication & Multi-Tenancy
**Goal:** Implement secure user management and production-grade authentication system.
**Clarification:** This is a security-critical phase. The implementation of multi-tenancy must ensure strict data isolation between users at the database level.

#### 3.1 User Management System
- [ ] Create User model and schemas with password hashing (passlib)
- [ ] Implement user registration and profile management
- [ ] Add user preferences and settings storage
- [ ] User account lifecycle management (activation, deactivation)

#### 3.2 JWT Authentication
- [ ] JWT token system with access/refresh token patterns
- [ ] Secure token storage and rotation mechanisms
- [ ] Token blacklisting for logout and security
- [ ] Rate limiting for authentication endpoints

#### 3.3 API Security Integration
- [ ] Secure existing FastAPI endpoints with authentication
- [ ] FastAPI dependencies for current user injection
- [ ] Permission-based access control for trading operations
- [ ] API key management for MCP server access

#### 3.4 Multi-Tenant Architecture
- [ ] Account isolation and data segregation
- [ ] Tenant-specific trading configurations
- [ ] Resource limits and quotas per user
- [ ] Cross-tenant data access prevention
**Clarification:** Every database query must include a `user_id` or `tenant_id` filter to prevent data leakage. This should be enforced at a low level, possibly through a shared repository pattern or a custom SQLAlchemy Query class to reduce the risk of human error.

#### 3.5 Security & Compliance
- [ ] Audit logging for all user actions
- [ ] GDPR compliance features (data export, deletion)
- [ ] Security headers and CSRF protection
- [ ] Rate limiting and DDoS protection

### Phase 4: Backtesting & Strategy Framework
**Goal:** Build comprehensive strategy development and historical analysis capabilities.
**Clarification:** This phase requires a robust data engineering pipeline to handle large volumes of historical market data. The backtesting engine should operate on a snapshot of the data and be completely isolated from the live trading service.

#### 4.1 Historical Data Engine
- [ ] Time-series data storage optimization
- [ ] Historical quote data ingestion pipelines
- [ ] Data quality validation and cleaning
- [ ] Efficient data retrieval for backtesting
**Clarification:** Consider using a dedicated time-series database (e.g., TimescaleDB) or optimizing PostgreSQL with appropriate partitioning and indexing for large datasets.

#### 4.2 Strategy Development Framework
- [ ] Plugin architecture for custom trading strategies
- [ ] Strategy base classes and interfaces
- [ ] Parameter optimization and grid search
- [ ] Strategy versioning and deployment

#### 4.3 Backtesting Engine
- [ ] Historical simulation with realistic market conditions
- [ ] Bid-ask spread and slippage modeling
- [ ] Commission and fee calculations
- [ ] Market hours and trading calendar integration

#### 4.4 Performance Analytics
- [ ] Standard metrics (Sharpe, Sortino, max drawdown, alpha, beta)
- [ ] Risk-adjusted return calculations
- [ ] Benchmark comparison and attribution analysis
- [ ] Performance visualization and reporting

#### 4.5 Strategy Validation
- [ ] Walk-forward analysis and out-of-sample testing
- [ ] Monte Carlo simulation for robustness testing
- [ ] Strategy correlation and diversification analysis
- [ ] Live trading vs backtest performance tracking

### Phase 5: Advanced Features & User Experience
**Goal:** Enhanced user interface, market analysis tools, and educational features.
**Clarification:** The frontend should be developed as a separate application to maintain a clean separation of concerns between the UI and the backend API. The API should be designed to be ergonomic for a frontend client.

#### 5.1 Frontend Dashboard
- [ ] React/Vue dashboard with real-time portfolio updates
- [ ] Interactive charts for price and portfolio performance
- [ ] Order management interface with advanced order types
- [ ] Responsive design for mobile and desktop
**Clarification:** This should be a Single-Page Application (SPA) that communicates with the FastAPI backend via the REST API.

#### 5.2 Advanced MCP Tools
- [ ] Market analysis tools (get_technical_indicators, scan_market)
- [ ] Sector and industry analysis capabilities
- [ ] Options chain analysis and strategies
- [ ] Economic calendar and news integration

#### 5.3 Educational Features
- [ ] Interactive trading tutorials and guides
- [ ] Paper trading competitions and leaderboards
- [ ] Risk management education modules
- [ ] Strategy explanation and educational content

#### 5.4 Strategy Marketplace
- [ ] Strategy sharing and discovery platform
- [ ] Strategy performance tracking and ratings
- [ ] Community features and discussion forums
- [ ] Strategy monetization and licensing

#### 5.5 Integration & Export
- [ ] Data export capabilities (CSV, Excel, PDF reports)
- [ ] Third-party platform integrations
- [ ] API client generation for external consumption
- [ ] Webhook notifications for trading events

---

## 🎯 QUICK WINS & DEVELOPER EXPERIENCE

### Code Quality & Tooling
- [ ] Pre-commit hooks setup for automated code quality
- [ ] OpenAPI client generation for easier API consumption
- [ ] CLI administration tools for account and system management
- [ ] Performance profiling tools and optimization guides
- [ ] **New:** Create a `CONTRIBUTING.md` file to formalize the development workflow for contributors.

### Documentation & Architecture
- [ ] Sequence diagrams showing request flow through shared service
- [ ] Thread safety documentation for monolithic design
**Clarification:** This is a critical engineering task, not just a documentation task. The best long-term solution is to refactor the `TradingService` to be stateless, removing the risks of a shared global instance and making the application more scalable and robust.
- [ ] API versioning strategy and migration guides
- [ ] Deployment and scaling documentation

---

## 📊 SUCCESS METRICS
**Clarification:** Once the test environment is functional, these metrics should be measured and tracked automatically as part of the CI/CD pipeline to ensure consistent quality and performance.

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