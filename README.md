# Open Paper Trading MCP

A FastAPI-based paper trading simulation platform with MCP (Model Context Protocol) integration.

## 🚀 Quick Start (with Docker)

The recommended way to run this project is with Docker Compose.

1. **Start the application:**
   ```bash
   docker-compose up --build
   ```
   This command will:
   - Build the Docker image for the application.
   - Start the application container and a dedicated PostgreSQL database container.
   - Create a persistent volume for the database to store data.

2. **Access the services:**
   - **FastAPI REST API**: http://localhost:2080/api/v1/
   - **Interactive docs**: http://localhost:2080/docs
   - **Health check**: http://localhost:2080/health
   - **MCP Server**: http://localhost:2081 (SSE transport)

3. **Shut down the application:**
   ```bash
   docker-compose down
   ```

## 💻 Local Development Setup (without Docker)

If you prefer to run the application locally without Docker, you can use `uv` to manage the virtual environment and dependencies.

1.  **Create and activate a virtual environment:**
    ```bash
    uv venv
    source .venv/bin/activate  # On Windows, use `.venv\Scripts\activate`
    ```

2.  **Install dependencies:**
    ```bash
    uv pip sync pyproject.toml
    ```

3.  **Set up the environment:**
    - You will need a running PostgreSQL instance.
    - Copy the `.env.example` file to `.env`.
    - Update the `DATABASE_URL` in your `.env` file to point to your local PostgreSQL instance (e.g., `postgresql+asyncpg://user:pass@localhost:5432/db_name`).

4.  **Run the application:**
    ```bash
    uv run python app/main.py
    ```

## Project Structure Overview

This section provides a detailed look at the key files and directories in the project.

### 🐳 Docker Configuration

-   `Dockerfile`: Defines the instructions to build the main application image. It installs dependencies, copies the application code, and sets the default command to run the server.
-   `Dockerfile.test`: Defines the image for the containerized test runner. It builds on the main application image and installs the ADK and other testing-specific dependencies.
-   `docker-compose.yml`: Orchestrates the multi-container environment. It defines three services:
    -   `db`: A PostgreSQL database for persistent data storage.
    -   `app`: The main Python application running both FastAPI and FastMCP servers.
    -   `test-runner`: A dedicated container for running ADK evaluations in a controlled environment.

### 🐍 Application Code (`/app`)

-   `main.py`: The main entry point for the application. It initializes the FastAPI app, sets up the MCP server to run in a background thread, and contains the `lifespan` event handler that creates the database tables on startup.
-   `/api`: Contains all FastAPI-related code.
    -   `routes.py`: The main API router that includes all versioned endpoint routers.
    -   `/v1/endpoints`: Each file (`auth.py`, `trading.py`, `portfolio.py`) defines the routes for a specific domain of the REST API.
-   `/core`: Core application logic and configuration.
    -   `config.py`: Defines all application settings using Pydantic, loading values from environment variables.
    -   `exceptions.py`: Defines custom exception classes for the application.
-   `/mcp`: Contains the MCP tool definitions.
    -   `tools.py`: Defines all the functions exposed as tools to the AI agent via the FastMCP server.
-   `/models`: Defines the data structures for the application.
    -   `trading.py`: Contains Pydantic models used for API request/response validation.
    -   `/database/trading.py`: Contains the SQLAlchemy models that define the database schema.
-   `/services`: Contains the shared business logic.
    -   `trading_service.py`: The heart of the application logic. **Currently mocked**, this service will be updated to interact with the database and external APIs.
-   `/storage`: Handles the database connection.
    -   `database.py`: Sets up the SQLAlchemy engine and provides a `get_db` dependency for use in API endpoints.

### 🧪 Testing (`/tests` and `/examples`)

-   `/tests`: Contains all automated tests.
    -   `/unit`: Unit tests for individual components.
    -   `/evals`: ADK evaluation files (`.json`) and configuration.
-   `/examples/google_adk_agent`: A sample ADK agent that can interact with the MCP server.

### 📜 Scripts and Configuration

-   `/scripts`: Contains helper scripts for development.
    -   `dev.py`: A simple CLI for running common development tasks like formatting and testing.
    -   `run_adk_eval.sh`: The entrypoint script for the `test-runner` container, used to execute ADK evaluations.
-   `pyproject.toml`: The project's main configuration file, defining dependencies, project metadata, and tool settings.
-   `TODO.md`: The development plan outlining the next steps for implementation.

## 📋 Features

### 🔌 Dual Interface Support
- **FastAPI REST API**: Traditional HTTP JSON endpoints
- **MCP Server**: AI agent integration via Model Context Protocol
- **Shared Business Logic**: Both interfaces use the same trading service

### 💼 Trading Functionality
- **Stock Quotes**: Real-time market data simulation
- **Order Management**: Buy/sell orders with status tracking
- **Portfolio Tracking**: Position management and P&L calculations
- **Authentication**: OAuth2 bearer token authentication (FastAPI)

### 🛠️ Development Features
- **Type Safety**: Full type hints with Pydantic models
- **Testing**: Comprehensive test suite with pytest (95%+ coverage)
- **Auto-Documentation**: OpenAPI docs for REST API
- **Development Tools**: Black, isort, flake8, mypy integration
- **CI/CD**: GitHub Actions pipeline

### 🤖 MCP Tools Available
- `create_buy_order` / `create_sell_order` - Place trading orders
- `get_all_orders` / `get_order` - Order management
- `cancel_order` - Cancel pending orders
- `get_portfolio` / `get_portfolio_summary` - Portfolio overview
- `get_all_positions` / `get_position` - Position tracking

## Key Functional Features

- **Account Instantiation**: Create new paper trading accounts with initial virtual funds and optional owner (e.g., agent name), allowing separate accounts for different agents or users.
- **Order Placement**: Simulate buying and selling stocks/options at market or limit prices, updating virtual positions within a specific account.
- **Portfolio Management**: View all positions, historical trades, open positions, and virtual account balances for a given account.
- **Fund Management**: Deposit or withdraw virtual funds to/from a specific paper trading account.
- **Persistence**: Store account data (including owner, timestamps for trades to compute balance history), trade history, and balances in a local storage backend for session continuity.
- **Dual Access**: All features exposed via HTTP JSON APIs (e.g., POST /accounts, GET /positions/{account_id}) and as MCP tools (e.g., create_account, place_buy_order) for AI agent integration.
- **Frontend Dashboard**: Lightweight web interface to list all accounts (with owners), display current balances, and show balance over time as interactive line charts.

## Key Non-Functional Requirements

- **Performance**: <50ms average response time for API/MCP calls and <200ms for frontend page loads, as user load is minimal (1 human + <5 agents concurrent).
- **Reliability**: 99% availability during local runs; stateless operations where possible, with automatic recovery from DB on restart.
- **Scalability**: Designed for low scale; handles up to 100 requests/min without optimization; easy to run on a standard laptop.
- **Security**: Basic API key or token for HTTP/MCP access to prevent unauthorized access; no real funds involved, so focus on data integrity rather than encryption. All operations local, no external exposure unless configured.
- **Availability**: Persistent storage ensures data survives container restarts; target 100% local uptime with Docker volumes.

## Architecture Overview

The system is a monolithic, event-driven architecture. It is orchestrated with Docker Compose, running the application and a PostgreSQL database in separate containers.

Key components:
- **HTTP API Server (FastAPI)**: Handles RESTful endpoints for traditional access.
- **MCP Server (FastMCP)**: Exposes tools for AI agents, running in the same process as the FastAPI server to share logic.
- **Backend Logic**: Shared Python modules for simulation: order execution, position tracking, and account management.
- **Storage**: PostgreSQL database for persistent storage of all trading data.
- **Docker Compose**: Manages the `app` and `db` services, including networking and persistent volumes.

## Architectural Decisions and Trade-Offs

1. **Monolith vs. Microservices**
   - Decision rationale: A monolith with shared logic simplifies development and is sufficient for the current scale. The application runs in a single container, but the database is separated for better data management.
   - Trade-offs: This approach is easy to maintain now, but may require splitting the application into separate services if it needs to scale significantly.

2. **PostgreSQL vs. SQLite**
   - Decision rationale: PostgreSQL provides a robust, scalable, and production-ready database, managed in its own container. This is superior to a file-based SQLite database for all but the simplest of use cases.
   - Trade-offs: Requires Docker Compose for orchestration, which adds a small amount of complexity compared to a single file.

3. **Dual FastAPI/FastMCP in a Single Container**
   - Decision rationale: Running both servers in the same container allows them to share the core `TradingService` in memory, which is simple and efficient.
   - Trade-offs: The two services cannot be scaled independently. If one required significantly more resources, the application would need to be re-architected.

## Recommended Technology Stack

- **Backend Language and Framework**: Python 3.12, with FastAPI and FastMCP.
- **Database**: PostgreSQL, running in a dedicated Docker container.
- **Infrastructure**: Docker Compose to orchestrate the application and database services.
- **Observability**: Basic logging with Python's `logging` module.

## Packaging and Publishing Process

- **Packaging**: The application is packaged as a Docker image using the provided `Dockerfile`.
- **Versioning and Deployment**: Use Git for versioning. For local deployment, use `docker-compose up`. This is the recommended way to run the application.
- **Dev-to-Prod Workflow**: Use Git branches (main for prod-like, dev for features). CI via GitHub Actions can be used to lint, test, and build the Docker image on every push.

## Future Evolution Plan

The architecture is designed to be easily extensible.
- **To Scale**: If the application grows, the `app` container can be split into separate `api` and `mcp` services. This would require introducing a shared communication layer (like a message queue or internal API calls) to replace the in-memory service sharing.
- **For Real Market Data**: The `TradingService` can be updated to call external market data APIs.
- **Enhanced Security**: Full JWT/OAuth can be implemented for both the API and MCP interfaces.

## 📊 API Reference

(API and MCP tool references remain the same)

## 🧪 ADK Evaluations

Test your MCP server with Google ADK agent evaluations.

1. **Start the application:**
   ```bash
   docker-compose up --build
   ```

2. **Run evaluation (in another terminal):**
   ```bash
   # Set your Google API key
   export GOOGLE_API_KEY="your-google-api-key"
   
   # Run the evaluation
   adk eval examples/google_adk_agent tests/evals/list_available_tools_test.json --config_file_path tests/evals/test_config.json
   ```

See [ADK Testing Guide](tests/evals/ADK-testing-evals.md) for detailed instructions.
