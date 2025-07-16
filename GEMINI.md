# Gemini Project Configuration: Open Paper Trading MCP

This document provides project-specific context and conventions to guide Gemini's interactions with this codebase.

## 1. Project Overview

-   **Purpose**: A paper trading simulation platform with a dual interface: a traditional REST API (FastAPI) and an AI agent interface (FastMCP).
-   **Architecture**: A monolithic Python application that runs both the FastAPI and FastMCP servers in the same process. This allows them to share the core business logic from the `TradingService`. The application is orchestrated with Docker Compose, which manages the app container and a dedicated PostgreSQL database container.

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

## 3. Core Technologies

-   **Backend**: FastAPI (for the REST API), FastMCP (for the AI agent tools).
-   **Database**: PostgreSQL with SQLAlchemy for the ORM.
-   **Package Management**: `uv` is used for package management. Dependencies are defined in `pyproject.toml`.
-   **Containerization**: Docker and Docker Compose.

## 4. Code Conventions & Structure

-   **API Endpoints**: Located in `app/api/v1/endpoints/`. Each file corresponds to a different domain (e.g., `trading.py`, `portfolio.py`).
-   **MCP Tools**: All AI agent tools are defined in `app/mcp/tools.py`.
-   **Shared Business Logic**: The core application logic is located in `app/services/trading_service.py`. This service is currently mocked and is the primary target for future implementation work.
-   **Database Models**: SQLAlchemy models are defined in `app/models/database/trading.py`.
-   **Configuration**: Application settings are managed in `app/core/config.py` and loaded from environment variables.

## 5. API Keys

-   **Polygon.io API Key**: This will be required to implement real-time market data features. The key should be stored as an environment variable.
    -   `POLYGON_API_KEY`: (Not yet implemented)

## 6. Deprecation Strategy

-   **FastAPI Endpoints**: Deprecated by adding the `deprecated=True` flag to the endpoint decorator.
-   **MCP Tools**: Deprecated by adding a `[DEPRECATED]` prefix to the tool's docstring.
-   In both cases, the deprecated feature should also be removed from the `README.md` documentation.
