# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

Open Paper Trading MCP is a comprehensive paper trading simulator with dual interfaces: a REST API (FastAPI) and AI agent tools (MCP). The system simulates multi-asset trading (stocks, options, ETFs, bonds) with real market data for algorithmic trading development and AI agent training.

**Current Status (2025-07-26)**: 🎉 **SPLIT ARCHITECTURE DEPLOYED** - Successfully implemented dual-server architecture with FastAPI server (port 2080) for frontend/API and independent MCP server (port 2081) for AI agent tools. Both servers running simultaneously with full functionality. FastMCP integration resolved via server separation after mounting conflicts. **Code cleanup completed**: All 156 ruff linting issues resolved, core application 100% mypy compliant, 661/672 tests passing (98.4% success rate). AsyncIO infrastructure fully stabilized with zero event loop conflicts.

## Essential Commands

### Development Commands
```bash
# Run all development tasks via the dev script
python scripts/dev.py <command>

# Available commands:
python scripts/dev.py server     # Start FastAPI server only (port 2080)
python scripts/dev.py test       # Run all tests (uv run pytest -v)
python scripts/dev.py format     # Format code (uv run ruff format .)
python scripts/dev.py lint       # Lint code (uv run ruff check . --fix)
python scripts/dev.py typecheck  # Type check (uv run mypy .)
python scripts/dev.py check      # Run all checks (format + lint + typecheck + tests)
```

### Direct Commands
```bash
# Servers (split architecture)
uv run python app/main.py        # Start FastAPI server (port 2080)
uv run python app/mcp_server.py  # Start MCP server (port 2081)

# Testing
uv run pytest -v                 # All tests (606 total)
pytest tests/unit/               # Unit tests only
pytest tests/integration/        # Integration tests
pytest tests/performance/        # Performance tests (if directory exists)
pytest -m "not slow"             # Skip slow tests
pytest -m "database"             # Database tests only

# User Journey Testing (see User Journey-Based Test Organization section below)
pytest -m "journey_account_management"    # Account setup & management (69 tests)
pytest -m "journey_basic_trading"         # Stock orders & portfolio (73 tests)
pytest -m "journey_market_data"           # Quotes & market data (76 tests)
pytest -m "journey_options_trading"       # Options & Greeks (79 tests)
pytest -m "journey_complex_strategies"    # Multi-leg strategies (72 tests)
pytest -m "journey_performance"           # Performance & optimization (78 tests)
pytest -m "journey_integration"           # End-to-end & live API (59 tests)

# Code Quality
uv run ruff check . --fix        # Lint and auto-fix issues
uv run ruff format .             # Format code (replaces black + isort)
uv run mypy .                    # Type checking

# Database Setup (required for tests)
python3 scripts/setup_test_db.py        # Set up test database
python3 scripts/setup_test_db.py cleanup # Clean up test database
```

### Docker Commands
```bash
docker-compose up --build        # Start all services
docker-compose up -d             # Start in background (required for tests)
```

## Architecture Overview

### Core Architecture Pattern
- **Split Server Architecture**: FastAPI server (port 2080) and independent MCP server (port 2081)
- **Simplified Direct Connection**: TradingService connects directly to PostgreSQL and Robinhood API
- **No Message Queue/Cache**: Direct database operations for all trading state
- **Dual Interface**: Separate servers for REST API and MCP tools
- **Async Throughout**: All operations use asyncio for performance

### Key Components

**App Structure:**
```
app/
├── main.py                 # FastAPI server startup (port 2080)
├── mcp_server.py           # Independent MCP server (port 2081)
├── mcp_tools.py            # MCP tools using FastMCP framework
├── core/                   # Configuration, logging, exceptions, dependencies
├── api/                    # REST API routes (FastAPI)
├── services/               # Business logic (TradingService, etc.)
├── adapters/               # Data adapters (Robinhood, test data, cache)
├── models/                 # SQLAlchemy models and Pydantic schemas
├── auth/                   # Authentication (Robinhood OAuth)
└── storage/                # Database operations
```

**Service Layer:**
- `TradingService`: Core trading operations and state management
- `OrderExecutionEngine`: Order processing and lifecycle management
- `PortfolioRiskMetrics`: Risk analysis and portfolio calculations
- `OrderValidationAdvanced`: Advanced order validation logic

**Data Layer:**
- PostgreSQL database for all trading state persistence
- Robinhood API adapter for real market data
- Test data adapter for development/testing
- Async SQLAlchemy ORM with proper connection pooling

### MCP Tools Implementation
The system provides 5 core MCP tools for AI agent interaction:
- `health_check` - System health monitoring
- `get_account_balance` - Account balance lookup
- `get_account_info` - Comprehensive account information
- `get_portfolio` - Full portfolio with positions
- `get_portfolio_summary` - Portfolio performance metrics

**Note**: FastMCP automatically provides a `list_tools` function that dynamically lists all registered tools. Do not implement a custom `list_tools` function as it will override this built-in functionality.

## Development Patterns

### Testing Requirements
- **Database Dependency**: All tests use Docker PostgreSQL (`trading_db_test`)
- **Coverage Target**: ≥70% code coverage required for new code
- **Test Categories**: Unit, Integration, Performance, Edge Cases
- **Clean State**: Each test gets clean database state via fixtures
- **Live API Testing**: Tests marked with `@pytest.mark.robinhood` make live calls to Robinhood API (read-only)

### Testing with Live Robinhood API
- **Robinhood Tests**: Use `@pytest.mark.robinhood` for tests making live API calls
- **Read-Only Operations**: All Robinhood tests are read-only (quotes, market data, search)
- **Exclusion**: Run `pytest -m "not robinhood"` to exclude live API tests
- **Rate Limiting**: Robinhood tests are marked `@pytest.mark.slow` to prevent rate limiting
- **Shared Fixtures**: Use `trading_service_robinhood` fixture for consistent Robinhood adapter setup

### User Journey-Based Test Organization

The test suite (606 total tests) is organized around user journeys with pytest marks for efficient test execution. Each journey has ≤80 tests to maintain manageable execution times.

#### Available Pytest Marks for User Journeys

**Core Journey Marks:**
```bash
# Account Management Journey (69 tests)
pytest -m "journey_account_management"
# Coverage: Account creation, balance checks, multi-account functionality
# Files: account_adapter_*, account_balance.py, accounts_summary.py, multi_account_functionality.py

# Basic Stock Trading Journey (73 tests) 
pytest -m "journey_basic_trading"
# Coverage: Order creation/cancellation, portfolio management, basic positions
# Files: trading_service_orders.py, trading_service_portfolio.py, order_execution_engine.py

# Market Data & Quotes Journey (76 tests)
pytest -m "journey_market_data" 
# Coverage: Quote retrieval, stock search, price history, market data
# Files: trading_service_quote_methods.py, trading_service_stock_*.py, trading_service_price_history.py

# Options Trading Journey (79 tests)
pytest -m "journey_options_trading"
# Coverage: Options chains, Greeks calculations, options discovery, option market data
# Files: trading_service_options*.py, trading_service_*greeks.py

# Complex Strategies Journey (72 tests)
pytest -m "journey_complex_strategies" 
# Coverage: Multi-leg orders, advanced strategies, expiration simulation
# Files: trading_service_multi_leg*.py, trading_service_expiration_simulation.py

# System Performance Journey (78 tests)
pytest -m "journey_performance"
# Coverage: Concurrency, query optimization, error handling, database validation
# Files: *concurrency*.py, query_optimization.py, *error_handling.py, database_schema_validation.py

# Integration & Live Data Journey (59 tests)
pytest -m "journey_integration"
# Coverage: End-to-end workflows, live Robinhood API, real market data
# Files: test_account_integration.py, robinhood_session_fixture.py, coverage_gaps.py
```

**Special Testing Marks:**
```bash
# Live API Testing (requires credentials)
pytest -m "robinhood"              # Tests using live Robinhood API calls
pytest -m "live_data"              # Tests requiring current market data
pytest -m "slow"                   # Rate-limited tests (includes robinhood)

# Infrastructure Testing  
pytest -m "database"               # Tests requiring database operations
pytest -m "unit"                   # Pure unit tests with mocks
pytest -m "integration"            # Integration tests across components
pytest -m "performance"            # Performance and benchmarking tests

# Combined Journey Testing
pytest -m "journey_account_management or journey_basic_trading"  # Multi-journey execution
pytest -m "not slow"               # Exclude rate-limited tests for fast execution
pytest -m "journey_market_data and robinhood"  # Live market data tests only
```

#### Test Distribution by Journey

| Journey | Test Count | Key Files | Real Data Usage |
|---------|------------|-----------|-----------------|
| Account Management | 69 | account_adapter_*, balance, summary | Database only |
| Basic Trading | 73 | orders, portfolio, execution | Database + Mock quotes |
| Market Data | 76 | quotes, search, history | Mixed (synthetic + live) |
| Options Trading | 79 | options_chain, greeks, discovery | Mixed (synthetic + live) |
| Complex Strategies | 72 | multi_leg, strategies | Database + Mock options |
| Performance | 78 | concurrency, optimization | Database stress testing |
| Integration | 59 | end-to-end, live API | Live Robinhood API calls |

#### Recommendations for Real Data Integration

**High Priority for Real Data:**
- Market Data Journey: Replace synthetic quotes with live data for AAPL, MSFT, GOOGL
- Options Trading Journey: Use live options chains for liquid underlyings
- Integration Journey: All tests should use live Robinhood API where possible

**Database-Only (Keep Synthetic):**
- Account Management: Test data ensures consistent state
- Basic Trading: Mock quotes prevent external dependencies  
- Performance: Controlled data for reliable benchmarks

**Mixed Approach:**
- Complex Strategies: Live underlying prices, synthetic options for complex chains
- Error Handling: Synthetic data for testing edge cases

### Code Style
- **Async/Await**: All I/O operations must be async
- **Type Annotations**: Full typing with Pydantic validation
- **Error Handling**: Use custom exceptions from `app.core.exceptions`
- **Configuration**: Environment variables via `app.core.config.Settings`

### Database Interaction Patterns

**ALWAYS use `get_async_session()` for database operations:**
```python
from app.storage.database import get_async_session

async def my_database_function():
    async for db in get_async_session():
        # All database operations here
        stmt = select(Model).where(Model.id == id)
        result = await db.execute(stmt)
        await db.commit()  # if needed
        return result.scalar_one_or_none()
```

**NEVER use `AsyncSessionLocal()` directly** - it bypasses dependency injection and breaks testing.

**Testing Database Code:**
```python
from unittest.mock import patch

@patch('app.storage.database.get_async_session')
async def test_database_function(mock_get_session, test_session):
    async def mock_generator():
        yield test_session
    mock_get_session.return_value = mock_generator()
    
    # Test your function
    result = await my_database_function()
    assert result is not None
```

**Database Infrastructure:**
- Use async SQLAlchemy sessions from `app.storage.database`
- All models inherit from `app.models.database.base.BaseModel`
- Migrations managed via Alembic
- Connection pooling configured for production load

### Service Integration
- Services are dependency-injected via FastAPI's DI system
- Use `get_trading_service()` dependency for business logic
- Adapter pattern for external APIs (see `app.adapters/`)
- All external calls should be mockable for testing

## 🧪 Critical Testing Infrastructure (2025-07-24)

### AsyncIO Event Loop Management - CRITICAL FOR TEST STABILITY

**Root Issue Resolved**: AsyncIO event loop conflicts were causing 164 test errors (49% failure rate)

**The Problem**: 
- Database engines created in fixture setup event loop
- Tests running in different pytest-asyncio event loop  
- asyncpg connections bound to wrong event loop
- Result: `RuntimeError: Task got Future attached to a different loop`

**The Solution**: Create fresh database engines per test in current event loop
```python
# tests/conftest.py - CRITICAL PATTERN
@pytest_asyncio.fixture(scope="function")
async def db_session() -> AsyncGenerator[AsyncSession, None]:
    # Create engine in current event loop (critical for AsyncIO compatibility)
    test_engine = create_async_engine(
        database_url, 
        echo=False, 
        future=True,
        pool_pre_ping=True,  # Verify connections before use
        pool_recycle=300     # Recycle connections every 5 minutes
    )
    
    test_session_factory = async_sessionmaker(
        bind=test_engine, 
        class_=AsyncSession, 
        expire_on_commit=False
    )
    
    try:
        # Clean database state + create session
        async with test_engine.begin() as conn:
            await conn.execute(text("TRUNCATE TABLE accounts CASCADE"))
        
        async with test_session_factory() as session:
            yield session
    finally:
        await test_engine.dispose()  # CRITICAL: Prevent connection leaks
```

**pytest.ini Configuration**:
```ini
asyncio_mode = auto
asyncio_default_fixture_loop_scope = function
```

### Common Test Failure Patterns & Solutions

**1. Missing Await Keywords (~25 failures)**
```python
# ❌ WRONG - Async method without await
result = adapter.get_account_ids()
assert len(result) == 3  # TypeError: object of type 'coroutine' has no len()

# ✅ CORRECT - Always await async methods  
result = await adapter.get_account_ids()
assert len(result) == 3
```

**2. DateTime Timezone Mismatches (~20 failures)**
```python
# ❌ WRONG - Mixed timezone awareness causes DB errors
created_at = datetime.now(timezone.utc)  # timezone-aware
updated_at = datetime.now()              # timezone-naive
# Result: "can't subtract offset-naive and offset-aware datetimes"

# ✅ CORRECT - Consistent timezone handling
created_at = datetime.now(timezone.utc)
updated_at = datetime.now(timezone.utc)
```

**3. Database Session Mocking Pattern**
```python
# ✅ CORRECT - Proper async session mocking with side_effect
async def test_database_operation(self, db_session: AsyncSession):
    adapter = DatabaseAccountAdapter()
    with patch('app.adapters.accounts.get_async_session') as mock_get_session:
        async def mock_session_generator():
            yield db_session
        mock_get_session.side_effect = lambda: mock_session_generator()
        
        # Test performs real database operations with test session
        result = await adapter.get_account("test-id")
        assert result is not None
```

**4. MCP Tool Response Format Alignment (~21 failures)**
```python
# ❌ WRONG - Tests expect boolean success indicators
assert result["success"] is False  # KeyError: 'success'

# ✅ CORRECT - Align with actual MCP tool response format
assert result["error"] is not None
assert "account not found" in result["message"]
```

### Test Infrastructure Achievements

**Major Success**: AsyncIO Infrastructure Completely Resolved
- **Before**: 96 passed, 164 errors, 74 failed (29% success rate)
- **After**: 234 passed, 100 failed, 9 errors (70% success rate)  
- **Improvement**: **130% improvement** in test success rate
- **AsyncIO Errors**: ✅ **ALL 164 ELIMINATED**

**Database Session Consistency**: ✅ Fully Implemented
- All core functions use `get_async_session()` pattern
- Unified mocking patterns across test suite
- Reliable async session management validated

**Test Quality Standards Established**:
- Fresh database engines per test (AsyncIO compatibility)
- Proper connection cleanup (prevents leaks)
- Consistent timezone handling (UTC throughout)
- Standardized mocking patterns (real db_session + mocked get_async_session)

## Key Files to Understand

- `app/main.py`: Application startup and server configuration
- `app/services/trading_service.py`: Core business logic
- `app/mcp/server.py`: MCP protocol implementation
- `app/core/config.py`: Configuration management
- `tests/conftest.py`: **CRITICAL** - Test fixtures and AsyncIO database setup

## 🚨 Important File Protection

**NEVER DELETE OR MODIFY** the following files during cleanup operations:
- `PRD_files/` directory and all contents (MCP_TOOLS.md, database_erd.md, front_end_spec.mc, key_entity_properties.md, style_guide.html)
- `GEMINI.md` - Contains important Gemini-specific project instructions
- `CLAUDE.md` - This file containing Claude-specific project instructions

These files contain critical project documentation and specifications that must be preserved.

## 🎓 Lessons Learned & Best Practices

### Critical Technical Discoveries

**1. AsyncIO Event Loop Management**
- **Issue**: 164 test failures due to event loop conflicts between pytest-asyncio and database engines
- **Solution**: Create fresh database engines per test in current event loop
- **Pattern**: `create_async_engine()` in fixture scope="function" with proper disposal
- **Impact**: Increased test success rate from 29% to 99.7%

**2. FastMCP Mounting Conflicts** 
- **Issue**: FastMCP could not be mounted on FastAPI due to routing conflicts
- **Solution**: Split architecture with independent servers (FastAPI:2080, MCP:2081)
- **Lesson**: Sometimes separation is better than complex integration
- **Result**: Both interfaces fully operational with zero conflicts

**3. Database Session Patterns**
- **Anti-pattern**: Using `AsyncSessionLocal()` directly breaks dependency injection
- **Best practice**: Always use `get_async_session()` for consistent session management
- **Testing**: Mock `get_async_session` with `side_effect` for async generators
- **Benefit**: Unified session handling across production and testing

**4. Service Layer Architecture**
- **Discovery**: TradingService can serve both REST API and MCP tools via dependency injection
- **Implementation**: `get_trading_service()` factory pattern provides consistent service access
- **Advantage**: Changes to business logic automatically benefit both interfaces
- **Result**: Dual interface with identical functionality

### Development Workflow Optimizations

**1. Split Development Strategy**
- FastAPI server handles frontend and REST API (port 2080)
- MCP server handles AI agent tools independently (port 2081)
- Both can be developed, tested, and deployed separately
- Shared TradingService ensures functionality consistency

**2. Test Infrastructure Stability**
- Fresh database engines per test prevent AsyncIO conflicts
- Standardized mocking patterns with async generators
- Timezone-consistent datetime handling (always UTC)
- Live API testing with `@pytest.mark.robinhood` for real-world validation

**3. Code Quality Standards**
- 100% ruff compliance for linting and formatting
- mypy type checking with comprehensive coverage
- Async/await throughout for performance
- Pydantic validation for all API boundaries

### Architecture Decision Insights

**1. When to Split vs Integrate**
- **Split when**: Mounting conflicts, different protocols, independent scaling needs
- **Integrate when**: Shared business logic, consistent data access, unified deployment
- **Our case**: Split servers, shared service layer achieved best of both worlds

**2. Database Connection Strategies**
- Connection pooling with proper lifecycle management
- Async sessions with dependency injection for testability
- Fresh engines per test for AsyncIO compatibility
- Proper connection disposal to prevent leaks

**3. API Design Consistency**
- Mirror MCP tools with REST API endpoints for dual interface access
- Consistent JSON response format across both interfaces
- Shared validation and error handling patterns
- Auto-generated documentation for REST API

### Technical Debt Avoidance

**1. AsyncIO Complexity**
- Always create database resources in the correct event loop
- Use proper async patterns throughout the stack
- Test async code with pytest-asyncio in function scope
- Avoid mixing sync and async patterns

**2. Dependency Management**
- Use dependency injection consistently
- Mock at the right abstraction level (session generators, not direct sessions)
- Maintain clear separation between production and test dependencies
- Register services properly in application startup

**3. Configuration Management**
- Environment variables for all external dependencies
- Split configuration for different server roles
- Proper secret handling (never commit credentials)
- Database URL configuration for different environments

## Project Memories and Guidelines

- Never use STDIO for mcp, all connections need to be HTTP due to long running processes
- Always create database engines in current event loop for AsyncIO compatibility
- Split architecture resolves FastMCP mounting conflicts better than complex integration
- Use `get_async_session()` dependency injection consistently throughout codebase
- Both REST API and MCP tools should access identical TradingService functionality