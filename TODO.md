# Open Paper Trading MCP - Development Roadmap

This document tracks the implementation progress and upcoming tasks for the paper trading simulator with dual REST API and MCP interfaces.

## Phase 0: Infrastructure & Setup ✅ COMPLETE

All infrastructure components are in place:
- Docker containerization with PostgreSQL
- Database models and schema
- ADK test runner integration
- Both FastAPI and FastMCP servers running

## Phase 1: Core Trading Engine 🚧 IN PROGRESS

**Goal:** Replace mocked `TradingService` with real database-backed operations.

### 1.1 Database Integration
- [ ] Convert `TradingService` to use async SQLAlchemy operations
- [ ] Implement database session management and connection pooling
- [ ] Add database migration support with Alembic
- [ ] Create indexes for performance on frequently queried fields

### 1.2 Account Management
- [ ] Implement account creation with initial balance ($100,000 default)
- [ ] Add account ownership tracking (human vs agent identifier)
- [ ] Create account funding operations (deposit/withdraw)
- [ ] Link authentication to accounts (JWT token contains account_id)

### 1.3 Market Data Integration
- [ ] Set up Polygon.io client with API key management
- [ ] Implement quote caching with Redis (already in dependencies)
- [ ] Add fallback to IEX Cloud or Alpha Vantage for redundancy
- [ ] Create market hours checking and pre/post market handling

### 1.4 Order Execution Engine
- [ ] Implement order validation (funds check, position check for sells)
- [ ] Add instant fill simulation for market orders
- [ ] Create order state machine (PENDING → FILLED/REJECTED/CANCELLED)
- [ ] Record all fills as transactions with timestamp and fees
- [ ] Update positions and cash balance atomically on fills

### 1.5 Portfolio Calculations
- [ ] Calculate real-time P&L using live market prices
- [ ] Implement cost basis tracking (FIFO method)
- [ ] Add portfolio history snapshots for charting
- [ ] Create portfolio performance metrics (Sharpe ratio, etc.)

## Phase 2: Enhanced Features & UI 📊 PLANNED

### 2.1 Frontend Dashboard
- [ ] Create React/Vue.js SPA for portfolio visualization
- [ ] Implement WebSocket for real-time updates
- [ ] Add interactive charts with Chart.js or D3.js
- [ ] Display account list with owner identification
- [ ] Show portfolio performance over time

### 2.2 Advanced MCP Tools
- [ ] `get_market_status` - Check if markets are open
- [ ] `get_technical_indicators` - SMA, EMA, RSI, MACD
- [ ] `search_symbols` - Find stocks by name or ticker
- [ ] `get_news_sentiment` - Basic news analysis for symbols
- [ ] `set_price_alert` - Notifications for price movements

### 2.3 Risk Management
- [ ] Add position sizing calculator
- [ ] Implement stop-loss and take-profit orders
- [ ] Create daily loss limits per account
- [ ] Add margin trading simulation

## Phase 3: Production Readiness 🚀 FUTURE

### 3.1 Performance & Scaling
- [ ] Implement caching layer for frequently accessed data
- [ ] Add database read replicas for scaling
- [ ] Optimize queries with explain analyze
- [ ] Load test with 100+ concurrent users

### 3.2 Observability
- [ ] Set up Prometheus metrics (already in dependencies)
- [ ] Add distributed tracing with OpenTelemetry
- [ ] Create Grafana dashboards
- [ ] Implement structured logging with correlation IDs

### 3.3 Advanced Trading Features
- [ ] Options trading simulation
- [ ] Crypto trading support
- [ ] International markets (multiple currencies)
- [ ] Backtesting framework
- [ ] Paper trading competitions

## Quick Wins 🎯

These can be done anytime to improve the project:

- [ ] Add comprehensive API documentation with examples
- [ ] Create a CLI tool for account management
- [ ] Implement rate limiting on endpoints
- [ ] Add Swagger/OpenAPI client generation
- [ ] Create Docker health checks
- [ ] Set up pre-commit hooks for code quality
- [ ] Add performance benchmarks