# Open Paper Trading MCP 📈

A comprehensive paper trading simulator with dual interfaces: REST API (FastAPI) and AI agent tools (MCP). Designed for algorithmic trading development, strategy backtesting, options trading simulation, and training AI agents in realistic market environments without financial risk.

## 🎯 Core Capabilities

- **Multi-Asset Trading**: Stocks, options, ETFs, and bonds with specialized implementations
- **Advanced Options Trading**: Full options chain support with Greeks calculations and 15+ spread strategies
- **Professional Spread Builder**: Iron Condors, Butterflies, Straddles, Strangles, and advanced multi-leg strategies
- **Real-time Risk Analysis**: P&L diagrams, breakeven calculations, and win probability analysis
- **AI Agent Training**: Native MCP interface for training trading agents and LLMs
- **Production-Ready**: Type-safe, async architecture with comprehensive testing and monitoring
- **Dual Interface Access**: Both REST API (web clients) and MCP tools (AI agents) access identical functionality

## ✅ Current Status (2025-08-03)

🎉 **PRODUCTION READY QUALITY** - Successfully implemented and deployed dual-server architecture:

- **FastAPI Server** (port 2080): Frontend integration + 49 REST API endpoints operational
- **MCP Server** (port 2081): Independent MCP server with 43 tools + auto-generated list_tools function
- **Test Success Rate**: 99.8% (580/581 tests passing, comprehensive journey-based testing)
- **Code Quality**: 100% ruff compliance, 100% mypy clean, all style violations resolved
- **Database Integration**: PostgreSQL async operations with proper session management
- **Service Layer**: TradingService fully integrated via dependency injection
- **API Documentation**: Auto-generated docs available at `/docs`
- **Multi-Account Support**: Complete backend implementation with account_id parameter support
- **Options Spread Trading**: Advanced spread builder with 15+ strategies and real-time P&L analysis
- **Global Loading System**: Comprehensive loading state management across all components

## ✅ Prerequisites

Before you begin, ensure you have the following installed:
- **Docker and Docker Compose**: For running the application in a containerized environment.
- **Python**: Version 3.11 or higher.
- **uv**: The project's package manager.

## 🚀 Quick Start

```bash
# 1. Clone the repository
git clone https://github.com/yourusername/open-paper-trading-mcp.git
cd open-paper-trading-mcp

# 2. Start everything with Docker
docker-compose up --build

# 3. Services are now available at:
#    - Frontend & API: http://localhost:2080/
#    - MCP Server: http://localhost:2081/
#    - API Docs: http://localhost:2080/docs
```

## 🏗️ Architecture Overview

```
REST Client          AI Agent
     |                  |
     v                  v
FastAPI Server    MCP Server
(Port 2080)      (Port 2081)
     |                  |
     +------------------+
              |
              v
       TradingService
              |
    +---------+---------+
    |                   |
    v                   v
PostgreSQL DB    Robinhood API
(Trading State)  (Market Data)
```

**Split Architecture Benefits:**
- **Independent Servers**: FastAPI (2080) and MCP (2081) run separately, eliminating mounting conflicts
- **Dual Interface Access**: Web clients use REST API, AI agents use MCP tools - same underlying functionality
- **Service Layer Unity**: Both interfaces use identical TradingService for consistency
- **Database-First**: All trading state persisted in PostgreSQL with async operations
- **Real-time Market Data**: Direct API calls to Robinhood for current market information
- **Type Safety**: Full Pydantic validation on all inputs/outputs across both interfaces

## 🏆 Key Achievements & Lessons Learned

### Major Technical Achievements
1. **AsyncIO Infrastructure Mastery**: Resolved 164 AsyncIO event loop conflicts that were causing 49% test failure rate
2. **Split Architecture Success**: Overcame FastMCP mounting conflicts by implementing independent server architecture  
3. **Database Session Consistency**: Established unified `get_async_session()` pattern across entire codebase
4. **Test Infrastructure Stability**: Achieved 99.7% test success rate (596/598 tests passing)
5. **Dual Interface Implementation**: Successfully created mirror functionality between REST API and MCP tools

### Critical Lessons Learned
1. **Event Loop Management**: Create fresh database engines per test in current event loop to prevent AsyncIO conflicts
2. **Service Architecture**: Independent servers solve mounting conflicts better than complex integration
3. **Database Patterns**: Always use `get_async_session()` dependency injection, never `AsyncSessionLocal()` directly
4. **Testing Patterns**: Standardized mocking with `side_effect` for async generators ensures reliable tests
5. **Code Quality**: Comprehensive linting (ruff), type checking (mypy), and formatting standards prevent technical debt

### Development Workflow Optimizations
- **Split Development**: FastAPI server (frontend/API) and MCP server (AI tools) can be developed independently
- **Service Layer Unity**: Changes to TradingService automatically benefit both interfaces
- **Test-Driven Stability**: Comprehensive test coverage (70%+) with AsyncIO-safe patterns
- **Live API Integration**: Robinhood API tests with `@pytest.mark.robinhood` for real-world validation

## 🛠️ Technology Stack

- **Backend**: Python, FastAPI, FastMCP
- **Database**: PostgreSQL
- **ORM**: SQLAlchemy
- **Market Data**: Robinhood API
- **Package Management**: uv
- **Containerization**: Docker, Docker Compose

## ⚙️ Development

### Local Setup (without Docker)

```bash
# Install uv package manager
curl -LsSf https://astral.sh/uv/install.sh | sh

# Create virtual environment and install dependencies
uv venv
source .venv/bin/activate  # On Windows: .venv\Scripts\activate
uv pip sync pyproject.toml

# Set up PostgreSQL and update .env
cp .env.example .env
# Edit DATABASE_URL in .env

# Run the application
uv run python app/main.py
```

### Configuration

The application is configured using environment variables. Copy the `.env.example` file to `.env` and update the following variables:

-   `DATABASE_URL`: The connection string for your PostgreSQL database.
-   `ROBINHOOD_USERNAME`: Your Robinhood username (for live market data).
-   `ROBINHOOD_PASSWORD`: Your Robinhood password.
-   `QUOTE_ADAPTER_TYPE`: The quote adapter to use (`test` or `robinhood`).

### Development Commands

```bash
# Format code
python scripts/dev.py format

# Run linting
python scripts/dev.py lint

# Type checking
python scripts/dev.py typecheck

# Run all tests
python scripts/dev.py test

# Run all checks
python scripts/dev.py check
```

### Database Development Patterns

**Always use consistent database session patterns:**

```python
# ✅ CORRECT - Use get_async_session()
from app.storage.database import get_async_session

async def database_operation():
    async for db in get_async_session():
        result = await db.execute(select(Model))
        return result.scalars().all()

# ❌ INCORRECT - Never use AsyncSessionLocal() directly
from app.storage.database import AsyncSessionLocal
async with AsyncSessionLocal() as db:  # Breaks testing!
    pass
```

**Testing database code:**

```python
from unittest.mock import patch

@patch('app.storage.database.get_async_session')
async def test_function(mock_get_session, test_session):
    async def mock_generator():
        yield test_session
    mock_get_session.return_value = mock_generator()
    
    # Your test code here
    result = await database_operation()
    assert result is not None
```

This ensures consistent behavior between production and testing environments.

## 🧪 Testing Best Practices

### AsyncIO Event Loop Management
**Critical for async test stability:**

```python
# tests/conftest.py - Create fresh engines per test
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
        async with test_session_factory() as session:
            yield session
    finally:
        await test_engine.dispose()  # Critical for preventing leaks
```

### Common Test Issues & Solutions

**1. Missing Await Keywords**
```python
# ❌ WRONG - Async method without await
result = adapter.get_account_ids()  # Returns coroutine!
assert len(result) == 3  # TypeError: object of type 'coroutine' has no len()

# ✅ CORRECT - Always await async methods
result = await adapter.get_account_ids()
assert len(result) == 3
```

**2. DateTime Timezone Issues**
```python
# ❌ WRONG - Mixed timezone awareness
from datetime import datetime
created_at = datetime.now(timezone.utc)  # timezone-aware
updated_at = datetime.now()              # timezone-naive

# ✅ CORRECT - Consistent timezone handling
from datetime import datetime, timezone
created_at = datetime.now(timezone.utc)
updated_at = datetime.now(timezone.utc)
```

**3. Database Session Mocking Pattern**
```python
# ✅ CORRECT - Proper async session mocking
async def test_database_operation(self, db_session: AsyncSession):
    adapter = DatabaseAccountAdapter()
    with patch('app.adapters.accounts.get_async_session') as mock_get_session:
        async def mock_session_generator():
            yield db_session
        mock_get_session.side_effect = lambda: mock_session_generator()
        
        # Test database operations with real session
        result = await adapter.get_account("test-id")
        assert result is not None
```

### Test Infrastructure Achievements
- **AsyncIO Event Loop Issues**: ✅ **RESOLVED** - 164 AsyncIO errors eliminated
- **Success Rate Improvement**: 29% → 70% (130% improvement)
- **Database Session Consistency**: ✅ Implemented across all core functions
- **Test Pattern Standardization**: ✅ Unified mocking patterns established
- **Live API Testing**: ✅ Robinhood tests integrated with `@pytest.mark.robinhood` marker

### Live API Testing with Robinhood
The test suite includes integration tests that make live, read-only calls to the Robinhood API:

```bash
# Run all tests including live Robinhood calls
uv run pytest

# Exclude live Robinhood API tests (faster, no external dependencies)
uv run pytest -m "not robinhood"

# Run only Robinhood integration tests
uv run pytest -m "robinhood"
```

**Robinhood Test Features:**
- **Read-only operations**: Stock quotes, market data, company information, search
- **Rate limiting protection**: All marked as `@pytest.mark.slow`
- **Real data validation**: Verifies actual API responses and data formats
- **Shared fixtures**: Consistent setup via `trading_service_robinhood` fixture

