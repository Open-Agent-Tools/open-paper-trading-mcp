# Gemini Project Configuration: Open Paper Trading MCP

This document provides project-specific context and conventions to guide Gemini's interactions with this codebase.

## 1. Project Overview

-   **Purpose**: A production-ready paper trading simulation platform with a dual interface: a traditional REST API (FastAPI) and an AI agent interface (FastMCP).
-   **Architecture**: A monolithic Python application that runs both the FastAPI and FastMCP servers in the same process. This allows them to share the core business logic from the `TradingService`. The application is orchestrated with Docker Compose, which manages the app container and a dedicated PostgreSQL database container.
-   **Current Status**: Phase 1 complete with modern async architecture, database-first design, comprehensive testing foundation, live market data integration, and production monitoring. Ready for advanced feature development.

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





## 2. Development Environment

-   **Primary Workflow**: The project is designed to be run with Docker Compose. The primary command to start the development environment is:
    ```bash
    docker-compose up --build
    ```
-   **Database**: The application uses a PostgreSQL database running in a dedicated Docker container (`db` service). The data is persisted in a Docker volume (`postgres_data`).
-   **Testing**: ADK evaluations are run inside a dedicated `test-runner` container, which is also managed by Docker Compose. The command to run the default evaluation is:
    ```bash
    docker-compose run --rm test-runner
    ```

### Local Development (Non-Docker)

For direct development workflow that bypasses Docker:

1.  **Create and activate a virtual environment:**
    ```bash
    uv venv
    source .venv/bin/activate
    uv pip sync pyproject.toml
    ```

2.  **Development utilities:**
    ```bash
    python scripts/dev.py server     # Start both FastAPI and MCP servers
    python scripts/dev.py test       # Run all tests
    python3 -m ruff format .         # Format with ruff
    python3 -m ruff check . --fix    # Lint with ruff
    python3 -m mypy app/             # Type check with mypy
    python scripts/dev.py check      # Run all checks (format, lint, typecheck, test)
    ```

3.  **Run tests:**
    Execute the comprehensive test suite using `pytest`.
    ```bash
    uv run pytest tests/unit/test_specific.py::TestClass::test_method -v
    ```
    *Note: The test suite now has comprehensive coverage with E2E, integration, and performance validation.*


## 3. Core Technologies

-   **Backend**: FastAPI (for the REST API), FastMCP (for the AI agent tools).
-   **Database**: PostgreSQL with SQLAlchemy for the ORM.
-   **Package Management**: `uv` is used for package management. Dependencies are defined in `pyproject.toml`.
-   **Containerization**: Docker and Docker Compose.

## 4. Code Conventions & Structure

-   **API Endpoints**: Located in `app/api/v1/endpoints/`. Each file corresponds to a different domain (e.g., `trading.py`, `portfolio.py`).
-   **MCP Tools**: All AI agent tools are defined in `app/mcp/tools.py`.
-   **Shared Business Logic**: The core application logic is located in `app/services/trading_service.py`. This service is fully implemented with async/await patterns, database-first architecture, and comprehensive trading functionality.
-   **Database Models**: SQLAlchemy models are defined in `app/models/database/trading.py`.
-   **Configuration**: Application settings are managed in `app/core/config.py` and loaded from environment variables.



## 6. Implementation Status

**COMPLETED FOUNDATION [2025-07-16 to 2025-01-22]**

- **Phase 0**: Infrastructure with Docker, PostgreSQL, and dual-interface (FastAPI + MCP)
- **Phase 1**: Complete codebase refactoring and architectural modernization:
  - MyPy compliance: 567→0 errors (100% resolution for core application)
  - Full async/await migration with database-first architecture
  - E2E test resolution with portfolio calculation validation
  - Code quality improvements with ruff integration and clean exception handling
  - Test foundation: 66.4% pass rate (487/733 tests) with core functionality validated
- **Phase 2**: Live market data integration with Robinhood API and comprehensive tooling
- **Phase 3**: Complete testing suite with E2E, integration, and performance validation
- **Phase 4**: Schema-database separation with converter patterns and validation
- **Phase 5**: Production monitoring with health checks, performance benchmarks, and Kubernetes probes

**Key Achievements**: Modern async architecture, type safety, comprehensive database persistence, production monitoring, and validated core trading functionality

**NEXT PHASE ROADMAP (2025-07-20+)**

See TODO.md for the complete 5-phase roadmap:
1. **Advanced Order Management** - Sophisticated order types and execution
2. **Caching & Performance Infrastructure** - Redis caching and async task processing
3. **User Authentication & Multi-Tenancy** - Secure user management
4. **Backtesting & Strategy Framework** - Historical analysis capabilities
5. **Advanced Features & User Experience** - UI/UX and market analysis tools

## 7. Deprecation Strategy

-   **FastAPI Endpoints**: Deprecated by adding the `deprecated=True` flag to the endpoint decorator.
-   **MCP Tools**: Deprecated by adding a `[DEPRECATED]` prefix to the tool's docstring.
-   In both cases, the deprecated feature should also be removed from the `README.md` documentation.

## 8. Architecture Highlights

**Key Architectural Decisions:**
1. **Shared Service Pattern**: Both FastAPI and FastMCP access the same `TradingService` instance
2. **Database First**: All persistent state stored in PostgreSQL, no in-memory storage
3. **Async Throughout**: All I/O operations use async/await patterns
4. **Quote Adapter System**: Dynamic adapter creation with failover support
5. **Production Ready**: Comprehensive monitoring, health checks, and performance benchmarks
