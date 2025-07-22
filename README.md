# Open Paper Trading MCP 📈

A comprehensive paper trading simulator with dual interfaces: REST API (FastAPI) and AI agent tools (MCP). Designed for algorithmic trading development, strategy backtesting, options trading simulation, and training AI agents in realistic market environments without financial risk.

## 🎯 Core Capabilities

- **Multi-Asset Trading**: Stocks, options, ETFs, and bonds with specialized implementations
- **Options Trading**: Full options chain support with Greeks calculations (delta, gamma, theta, vega, rho)
- **Strategy Development**: Build and test algorithmic trading strategies with backtesting framework  
- **AI Agent Training**: Native MCP interface for training trading agents and LLMs
- **Educational Platform**: Risk-free environment for learning market mechanics and trading concepts
- **Production-Ready**: Type-safe, async architecture with comprehensive testing and monitoring

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
#    - REST API: http://localhost:2080/api/v1/
#    - API Docs: http://localhost:2080/docs
#    - MCP Server: http://localhost:2081
```

## 🏗️ Architecture Overview

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

**Key Design Decisions:**
- **Monolithic Architecture**: Both servers run in one process, sharing the TradingService
- **Database-First**: All state persisted in PostgreSQL, no in-memory storage
- **Async Throughout**: Uses asyncio for high performance
- **Type Safety**: Full Pydantic validation on all inputs/outputs

## 🛠️ Technology Stack

- **Backend**: Python, FastAPI, FastMCP
- **Database**: PostgreSQL, Redis
- **ORM**: SQLAlchemy
- **Task Queue**: Celery
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

## 📋 Feature Roadmap

See [TODO.md](TODO.md) for the detailed, up-to-date development roadmap. 

### 🎯 Current Status: Phase 0 Near Completion
- **Phase 0: Foundation & QA** - ✅ **Major Progress** (In completion process)
  - ✅ Test environment functional (5/9 E2E tests passing)  
  - ✅ Dependencies resolved, AsyncClient fixed
  - ✅ Global service refactoring completed
  - 🔄 Async/await migration in progress (76 MyPy errors remaining)

### 🚀 Next Development Phases:
-   **Phase 1: Advanced Order Management**: Stop-loss, stop-limit, and other advanced order types.
-   **Phase 2: Caching & Performance Infrastructure**: Redis caching and async task processing for scalability.
-   **Phase 3: User Authentication & Multi-Tenancy**: A production-grade, secure user management system.
-   **Phase 4: Advanced Features & User Experience**: Frontend dashboard, advanced MCP tools, and educational features.
-   **Phase 5: Backtesting & Strategy Framework**: Historical backtesting and strategy development tools.

## 🤖 MCP Tools Reference

### Available Tools

| Tool | Description | Parameters |
|------|-------------|------------|
| `create_buy_order` | Place a buy order | symbol, quantity, price |
| `create_sell_order` | Place a sell order | symbol, quantity, price |
| `get_all_orders` | List all orders | - |
| `get_order` | Get specific order | order_id |
| `cancel_order` | Cancel an order | order_id |
| `get_portfolio` | Full portfolio details | - |
| `get_portfolio_summary` | Portfolio metrics | - |
| `get_all_positions` | List all positions | - |
| `get_position` | Get specific position | symbol |

## 🧪 Testing

### Test Architecture

**🚨 Important**: All tests run against Docker PostgreSQL database for consistency with production.

- **Database**: Uses Docker PostgreSQL with separate test database (`trading_db_test`)
- **Isolation**: Each test gets clean database state
- **Performance**: Comprehensive test suite covering unit, integration, performance, and edge cases
- **Coverage**: Advanced order management, market conditions, high-volume processing

### Running Tests

```bash
# 1. Start Docker containers (required for tests)
docker-compose up -d

# 2. Set up test database (run once)
python3 scripts/setup_test_db.py

# 3. Run tests
pytest tests/                    # All tests
pytest tests/unit/               # Unit tests only
pytest tests/integration/        # Integration tests only
pytest tests/performance/        # Performance tests only

# 4. Run tests with markers
pytest -m "not slow"             # Skip slow tests
pytest -m "database"             # Database tests only
pytest -v                        # Verbose output

# 5. Clean up (optional)
python3 scripts/setup_test_db.py cleanup
```

### Test Categories

- **Unit Tests**: Fast, isolated component testing
- **Integration Tests**: Full workflow testing with database
- **Performance Tests**: High-volume order processing (1000-5000 orders)
- **Edge Case Tests**: Market hours, holidays, circuit breakers, data failures

### Run ADK Evaluations

```bash
# Set your Google API key
export GOOGLE_API_KEY="your-google-api-key"

# Run evaluation (app must be running)
adk eval examples/google_adk_agent tests/evals/list_available_tools_test.json \
  --config_file_path tests/evals/test_config.json
```

See [ADK Testing Guide](tests/evals/ADK-testing-evals.md) for details.

## 📚 Documentation

- **API Documentation**: http://localhost:2080/docs (when running)
- **Development Plan**: See [TODO.md](TODO.md)
- **Claude Integration**: See [CLAUDE.md](CLAUDE.md)

## 🤝 Contributing

We welcome contributions from the community! Please read our [CONTRIBUTING.md](CONTRIBUTING.md) file for details on our code of conduct, development process, and pull request submission guidelines.

## 📄 License

MIT License - see LICENSE file for details.