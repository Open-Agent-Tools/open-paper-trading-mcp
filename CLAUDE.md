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
┌─────────────────┐     ┌─────────────────┐
│   REST Client   │     │    AI Agent     │
└────────┬────────┘     └────────┬────────┘
         │                       │
         ▼                       ▼
┌─────────────────┐     ┌─────────────────┐
│  FastAPI :2080  │     │ FastMCP :2081   │
└────────┬────────┘     └────────┬────────┘
         │                       │
         └───────────┬───────────┘
                     ▼
           ┌─────────────────┐
           │ TradingService  │
           │   (Shared)      │
           └────────┬────────┘
                    │
        ┌───────────┴───────────┐
        ▼                       ▼
┌─────────────────┐     ┌─────────────────┐
│   PostgreSQL    │     │   Robinhood     │
│   Database      │     │      API        │
│ (Trading State) │     │ (Market Data)   │
└─────────────────┘     └─────────────────┘
```

### Core Components

1. **TradingService** (`app/services/trading_service.py`):
   - Central business logic shared by both interfaces
   - Currently mocked - primary target for Phase 1 implementation
   - Manages orders, positions, portfolio calculations

2. **Database Layer**:
   - PostgreSQL in dedicated container
   - SQLAlchemy models in `app/models/database/trading.py`
   - Tables created on startup via `Base.metadata.create_all()`
   - Connection managed by `app/storage/database.py`

3. **API Structure**:
   - REST endpoints in `app/api/v1/endpoints/` (auth, trading, portfolio)
   - MCP tools in `app/mcp/tools.py`
   - Shared Pydantic models in `app/models/trading.py`

4. **Configuration**:
   - Settings in `app/core/config.py` loaded from environment variables
   - Database URL: `postgresql+asyncpg://trading_user:trading_password@db:5432/trading_db`

### Implementation Status

**Phase 0 (Complete)**: Infrastructure with Docker, PostgreSQL integration, test runner

**Phase 1 (Complete) [2025-07-16]**: Comprehensive codebase refactoring and type safety improvements:
- MyPy errors reduced from 567 → 0 (100% resolution achieved)
- Complete schema/model separation with backward compatibility
- Modern SQLAlchemy 2.0 implementation throughout
- Systematic type safety improvements across all services
- Full ruff integration for code formatting and linting

**Phase 2 (Current)**: Live Market Data Integration via Robinhood/open-stocks-mcp
- Account management with persistent storage
- Real-time market data via Polygon.io API
- Order execution logic with database updates
- Portfolio calculations from database state

### Key Architectural Decisions

1. **Shared Service Pattern**: Both FastAPI and FastMCP access the same in-memory `TradingService` instance, avoiding duplication and ensuring consistency.

2. **Database First**: All persistent state (accounts, orders, positions, transactions) stored in PostgreSQL. The service layer reads/writes to DB, never holds state in memory.

3. **Deprecation Strategy**:
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
- `POLYGON_API_KEY`: For market data (Phase 1)
- `GOOGLE_API_KEY`: For ADK testing