# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

Open Paper Trading MCP is a dual-interface paper trading simulation platform that runs both a REST API (FastAPI) and an AI agent interface (FastMCP) in a single monolithic Python application. The application is containerized with Docker Compose, managing both the app container and a PostgreSQL database container.

## Development Commands

### Primary Development Workflow

```bash
# Start the full stack (recommended)
docker-compose up --build

# Stop the application
docker-compose down

# Run ADK evaluations (in another terminal)
docker-compose run --rm test-runner
```

### Local Development (without Docker)

```bash
# Install dependencies with uv
uv venv
source .venv/bin/activate
uv pip sync pyproject.toml

# Run development server
uv run python app/main.py

# Development utilities
python scripts/dev.py server     # Start both FastAPI and MCP servers
python scripts/dev.py test       # Run all tests
python3 -m ruff format .         # Format with ruff
python3 -m ruff check . --fix    # Lint with ruff
python3 -m mypy app/             # Type check with mypy
python scripts/dev.py check      # Run all checks (format, lint, typecheck, test)

# Run specific tests
uv run pytest tests/unit/test_specific.py::TestClass::test_method -v
```

### Testing Setup

**Important**: Tests run against Docker PostgreSQL database for consistency.

```bash
# Setup test database (run once)
python scripts/setup_test_db.py

# Run tests (Docker must be running)
pytest tests/

# Run specific test categories
pytest tests/unit/         # Unit tests only
pytest tests/integration/  # Integration tests only  
pytest tests/performance/  # Performance tests only

# Run tests with markers
pytest -m "not slow"       # Skip slow tests
pytest -m "database"       # Database tests only

# Clean up test database
python scripts/setup_test_db.py cleanup
```

### Service Access Points

- **FastAPI REST API**: http://localhost:2080/api/v1/
- **Interactive API docs**: http://localhost:2080/docs
- **Health check**: http://localhost:2080/health
- **MCP Server**: http://localhost:2081 (SSE transport)

## High-Level Architecture

### Monolithic Design

The application runs both servers in a single Python process (`app/main.py`):
- FastAPI server runs on the main thread (port 2080)
- MCP server runs in a background thread (port 2081)
- Both share the same `TradingService` instance in memory

### Architecture Diagram

```
                  +-------------------+      +-------------------+
                  |    REST Client    |      |     AI Agent      |
                  +--------+----------+      +---------+---------+
                           |                           |
                           +-----------+---------------+
                                       |
                                       V
                             +-------------------+
                             |  FastAPI / FastMCP|
                             |  (Main Process)   |
                             +---------+---------+
                                       |
                                       V
                             +-----------------+
                             |  TradingService |
                             +--------+--------+
                                      |
         +----------------------------+----------------------------+
         |                            |                            |
 (Dispatch Task)                      | (Direct Read/Write)        | (Cache Check)
         V                            V                            V
+------------------+        +-----------------+        +-----------------+
| Redis (Broker)   |        | PostgreSQL DB   |        |  Redis (Cache)  |
+--------+---------+        | (Trading State) |        +--------+--------+
         |                  +--------+--------+                 |
         | (Task Queue)              ^                         | (Cache R/W)
         V                           |                         |
+----------------+                   | (DB R/W)                |
| Celery Worker  |-------------------+                         |
| (Async Tasks)  |                                             |
+----------------+                                             |
         |                                                     |
         +-----------------------------------------------------+
                                      |
                                      V
                              +-----------------+
                              |  Robinhood API  |
                              |  (Market Data)  |
                              +-----------------+
```

### Core Components

1. **TradingService** (`app/services/trading_service.py`):
   - Central business logic shared by both interfaces
   - **Fully async**: All I/O operations use async/await patterns
   - **Database-first**: All state persisted in PostgreSQL, no in-memory storage
   - Manages orders, positions, portfolio calculations with proper async methods

2. **Database Layer**:
   - PostgreSQL in dedicated container
   - SQLAlchemy models in `app/models/database/trading.py`
   - Tables created on startup via `Base.metadata.create_all()`
   - Connection managed by `app/storage/database.py`

3. **API Structure**:
   - **Async REST endpoints** in `app/api/v1/endpoints/` (auth, trading, portfolio)
   - **Async MCP tools** in `app/mcp/tools.py` - all tools use async/await
   - Shared Pydantic models in `app/models/trading.py`

4. **Quote Adapter System**:
   - **AdapterFactory**: Dynamic adapter creation and configuration
   - **RobinhoodAdapter**: Live market data via robin_stocks library
   - **TestDataAdapter**: Historical test data for development and testing
   - **Cache Warming**: Automatic pre-loading of popular symbols on startup
   - **Failover Support**: Automatic fallback between adapters

5. **Configuration**:
   - Settings in `app/core/config.py` loaded from environment variables
   - Database URL: `postgresql+asyncpg://trading_user:trading_password@db:5432/trading_db`
   - Quote adapter configuration via `QUOTE_ADAPTER_TYPE` environment variable

6. **Volume Configuration**:
   - `./data/tokens/` - Robinhood authentication tokens (mounted to `/app/.tokens` in container)
   - `./data/logs/` - Application logs (mounted to `/app/.logs` in container)
   - **Environment Variables:**
     - `ROBINHOOD_TOKEN_PATH=/app/.tokens` - Path to token storage inside container
   - **Benefits:**
     - Avoids re-authentication on container restarts
     - Persistent session tokens for Robinhood API
     - Follows the same pattern as open-stocks-mcp reference implementation

### Implementation Status

**COMPLETED FOUNDATION**

**Phase 0 (Complete)**: Infrastructure with Docker, PostgreSQL integration, test runner

**Phase 1 (Complete - 2025-01-22)**: Code Quality & Infrastructure Cleanup:
- **Automated Linting**: 698 issues automatically fixed via ruff, 113 files reformatted
- **Type Safety**: MyPy validation operational, syntax errors resolved
- **Code Consistency**: Parsing errors fixed, escaped characters resolved, file integrity restored
- **Development Infrastructure**: All required tools validated (uv 0.7.5, ruff 0.12.1, mypy 1.16.1)
- **Build System**: All development commands verified functional
- **Project Structure**: pyproject.toml validated and working

**Phase 2 (Complete)**: Live Market Data Integration via Robinhood:
- **RobinhoodAdapter**: Fully integrated with robin_stocks library for live quotes
- **Comprehensive Testing**: Unit tests for RobinhoodAdapter, integration tests for TradingService-RobinhoodAdapter integration
- **Robust Authentication**: SessionManager with exponential backoff, circuit breaker pattern, and automatic recovery
- **Cache Warming**: Automatic cache warming on startup for popular symbols (AAPL, GOOGL, MSFT, etc.)
- **Performance Monitoring**: Structured logging, performance metrics, and comprehensive error handling
- **Async Integration**: All quote operations use async/await patterns throughout the stack

**Phase 3 (Complete)**: Complete testing suite with E2E, integration, and performance validation

**Phase 4 (Complete)**: Schema-database separation with converter patterns and validation

**Phase 5 (Complete)**: Production monitoring with health checks, performance benchmarks, and Kubernetes probes

**NEXT PHASE ROADMAP**

See TODO.md for the complete 5-phase roadmap:
1. **Advanced Order Management** - Sophisticated order types and execution
2. **Caching & Performance Infrastructure** - Redis caching and async task processing
3. **User Authentication & Multi-Tenancy** - Secure user management
4. **Backtesting & Strategy Framework** - Historical analysis capabilities
5. **Advanced Features & User Experience** - UI/UX and market analysis tools

### Key Architectural Decisions

1. **Shared Service Pattern**: Both FastAPI and FastMCP access the same `TradingService` instance, avoiding duplication and ensuring consistency.

2. **Database First**: All persistent state (accounts, orders, positions, transactions) stored in PostgreSQL. The service layer reads/writes to DB, never holds state in memory.

3. **Async Throughout**: All I/O operations use async/await patterns for optimal performance:
   - TradingService methods: `async def get_portfolio()`, `async def create_order()`, etc.
   - API endpoints: All FastAPI endpoints are async
   - MCP tools: All MCP tools are async functions
   - Database operations: Use async SQLAlchemy patterns

4. **Deprecation Strategy**:
   - FastAPI: Add `deprecated=True` to endpoint decorators
   - MCP: Add `[DEPRECATED]` prefix to tool docstrings

### Testing with ADK

```bash
# Set Google API key
export GOOGLE_API_KEY="your-key"

# Run evaluation (app must be running)
adk eval examples/google_adk_agent tests/evals/list_available_tools_test.json --config_file tests/evals/test_config.json
```

### Database Schema

Key tables defined in `app/models/database/trading.py`:
- `accounts`: Trading accounts with balances
- `orders`: Buy/sell orders with status tracking  
- `positions`: Current stock holdings
- `transactions`: Historical trade records

### Environment Variables

Required in `.env` or Docker environment:
- `DATABASE_URL`: PostgreSQL connection string
- `GOOGLE_API_KEY`: For ADK testing

**Quote Adapter Configuration:**
- `QUOTE_ADAPTER_TYPE`: Adapter type (`test` or `robinhood`, defaults to `test`)

**Robinhood Configuration (for live trading):**
- `ROBINHOOD_USERNAME`: Robinhood account username
- `ROBINHOOD_PASSWORD`: Robinhood account password
- `ROBINHOOD_TOKEN_PATH`: Path to store authentication tokens (defaults to `/app/.tokens`)