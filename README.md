# Open Paper Trading MCP

A FastAPI-based paper trading simulation platform with MCP (Model Context Protocol) integration.

## 🚀 Quick Start

1. **Start both servers (FastAPI + MCP):**
   ```bash
   uv run python app/main.py
   ```
   This starts:
   - FastAPI server on http://localhost:8000
   - MCP server on http://localhost:8001

2. **Access the services:**
   - **FastAPI REST API**: http://localhost:8000/api/v1/
   - **Interactive docs**: http://localhost:8000/docs
   - **Health check**: http://localhost:8000/health
   - **MCP Server**: http://localhost:8001 (SSE transport)

3. **Run development commands:**
   ```bash
   # Format code
   python scripts/dev.py format
   
   # Run tests
   python scripts/dev.py test
   
   # Run all checks
   python scripts/dev.py check
   ```

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
- `get_stock_quote` - Get current stock quotes
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

The system is a monolithic, event-driven architecture running in a single Docker container for simplicity, given the low scale. It uses FastMCP for the MCP server, FastAPI for HTTP JSON endpoints and the lightweight frontend (serving HTML templates with embedded JS charts). The services run on separate ports (e.g., 8000 for FastAPI HTTP/JSON + Frontend, 8001 for FastMCP).

Key components:
- **HTTP API Server (FastAPI)**: Handles RESTful endpoints for traditional access, plus routes for serving the frontend dashboard.
- **MCP Server (FastMCP)**: Exposes tools for AI agents, mirroring the HTTP functionality.
- **Frontend (FastAPI Templates)**: Simple Jinja2-rendered HTML pages with Chart.js for visualizations, fetching data from the internal API.
- **Backend Logic**: Shared Python modules for simulation: order execution (virtual matching), position tracking, account management, and balance history computation.
- **Storage**: SQLite database for persistence of accounts (with owner field), virtual funds, positions, and timestamped trade history.
- **Docker Container**: Encapsulates the app, with a volume for DB persistence and multiple ports exposed.

Interactions:
- Clients connect via HTTP to FastAPI endpoints (e.g., JSON POST for order placement) or browse to /dashboard for the frontend.
- AI agents connect via MCP protocol to FastMCP tools (e.g., WebSocket or HTTP for tool calls).
- Frontend fetches data dynamically via JS calls to API endpoints or renders server-side with template data.
- Both interfaces and frontend interact with the shared logic and storage layer to read/write data.
- No external services; all simulation is internal. Balance over time computed from timestamped trades.

Architectural patterns:
- Monolithic for ease of development and deployment.
- Event-driven within shared logic (e.g., order placement triggers position updates and timestamp logging).
- Layered: presentation (HTTP/MCP/Frontend), business logic (simulation), data (SQLite).

## Architectural Decisions and Trade-Offs

1. **Monolith vs. Microservices**
   - Alternatives considered: Microservices for separate HTTP, MCP, and frontend services.
   - Decision rationale: With low user count (1-5 concurrent), a monolith with shared logic simplifies development, reduces overhead, and fits local Docker deployment.
   - Trade-offs: Easier to maintain now, but harder to scale if users grow; potential for service splitting if needed later.

2. **SQLite vs. NoSQL (e.g., MongoDB) for Storage**
   - Alternatives considered: MongoDB for flexible schemas or in-memory for speed.
   - Decision rationale: SQLite is lightweight, file-based, perfect for local persistence in Docker volumes, and sufficient for structured data like accounts/positions/trades (including timestamps for history). No need for distributed DB at this scale.
   - Trade-offs: Slower for very large datasets (not an issue here); lacks advanced querying, but relational model fits trading data well.

3. **Dual FastAPI/FastMCP on Separate Ports vs. Single Unified Endpoint**
   - Alternatives considered: Unified server with MCP over FastAPI or single port multiplexing.
   - Decision rationale: Separate ports allow independent operation and scaling if needed, while sharing code. FastAPI for familiar HTTP/JSON access and frontend serving; FastMCP for AI-specific MCP tools. Fits the dual-support requirement without complexity.
   - Trade-offs: Adds minor config overhead (e.g., port mapping in Docker); but enables flexibility for clients preferring one interface over the other.

4. **FastAPI with Jinja2/Chart.js for Frontend vs. Separate Framework (e.g., Streamlit)**
   - Alternatives considered: Streamlit for Python-based UI or full JS framework like React.
   - Decision rationale: Integrating with FastAPI keeps the stack minimal and Python-centric; Jinja2 for templates and Chart.js for lightweight charts provide a "cheap and cheerful" solution without additional servers or heavy deps. Suits simple displays like account lists and balance charts.
   - Trade-offs: Less interactive than a full SPA, but faster to build and maintain; requires basic JS for dynamic fetches if needed.

## Recommended Technology Stack

- **Backend Language and Framework**: Python 3.12, with FastAPI for HTTP JSON APIs and frontend serving (chosen for its speed, async support, auto-generated docs, and template integration) and FastMCP for MCP server and tool exposure (chosen for its simplicity in defining AI-agent tools and integration with MCP protocol).
- **Frontend Technology**: Jinja2 templates served by FastAPI for HTML rendering, with Chart.js for interactive balance-over-time charts (lightweight, no-build-step JS library; rationale: enables simple, effective visualizations without a full frontend framework).
- **Database**: SQLite (lightweight, persistent, file-based; rationale: suits low-scale, local use with easy Docker volume mounting for data durability; supports timestamped data for history).
- **Message Brokers or Queues**: Not needed; all operations synchronous due to low load.
- **Infrastructure**: Docker for containerization (local runs); expose multiple ports (e.g., -p 8000:8000 -p 8001:8001).
- **Observability**: Basic logging with Python's `logging` module; optional integration with `structlog` for structured logs. No advanced metrics/tracing needed at this scale.

## Codebase Directory Structure

```
/app
  /api            # HTTP API routes and controllers (FastAPI routers for JSON endpoints)
  /ui             # Frontend routes and templates (FastAPI routers for dashboard, Jinja2 files)
  /static         # Static assets (e.g., chart.js, custom CSS/JS)
  /tools          # MCP tools definitions (e.g., create_account.py, place_buy_order.py with @mcp.tool)
  /models         # Shared data models (Pydantic for API/tool inputs/outputs, SQLAlchemy for DB)
  /simulation     # Shared business logic for paper trading simulation (e.g., order matching, balance history computation)
  /storage        # DB setup and queries (SQLite connection, schemas with timestamps)
  /config         # Configuration files (e.g., env vars, ports)
Dockerfile        # Docker build instructions
requirements.txt  # Python dependencies (add jinja2)
main.py           # Entry point: initializes both FastAPI (with UI routes) and FastMCP servers, registers tools/routes
/tests            # Unit and integration tests for both interfaces and frontend logic
/docs             # Additional documentation beyond README
```

- `/app`: Core application code; keeps everything organized under one namespace.
- `/api`: FastAPI-specific routes mirroring trading functions (e.g., /accounts, /orders).
- `/ui`: Routes for frontend (e.g., GET /dashboard renders template with account data).
- `/static`: JS libraries like chart.js and any custom scripts for client-side charting.
- `/tools`: Contains @mcp.tool decorated functions for MCP exposure.
- `/models`: Schemas for data validation shared between API, tools, and UI.
- `/simulation`: Logic to simulate trades and compute histories, shared by all.
- `/storage`: Handles persistence for accounts (add owner field) and timestamped trades.
- `/config`: Settings like port numbers (e.g., API_PORT=8000, MCP_PORT=8001).
- `/tests`: Tests for API endpoints, tools, UI rendering, and simulation logic.
- `/docs`: For diagrams or extended guides, including API docs from FastAPI.

## Packaging and Publishing Process

- **Packaging**: Use Docker to build the image (`docker build -t paper-trading-server .`). Dependencies managed via `requirements.txt` (e.g., `pip install -r requirements.txt`; add jinja2 via CDN or local). Include static files in build.
- **Versioning and Deployment**: Semantic versioning (e.g., v1.0.0) tagged in Git. Deploy locally with `docker run -p 8000:8000 -p 8001:8001 -v ./data:/app/data paper-trading-server` (mounts volume for SQLite persistence). Frontend accessible at http://localhost:8000/dashboard.
- **Target Registries or Environments**: Local only; no publishing to registries like Docker Hub unless extended. For dev, run directly with `python main.py` (starts both servers).
- **Dev-to-Prod Workflow**: Use Git branches (main for prod-like, dev for features). CI via GitHub Actions: lint/test on push, build Docker image on merge. No staging; direct local runs. Gates: All tests pass before merge.

## Future Evolution Plan

The architecture is simple and monolithic, allowing easy iteration for small-scale use. To scale or adapt:
- **If user/agent count grows to 10+**: Introduce async processing in shared logic and consider splitting HTTP/MCP/frontend into separate containers.
- **For real market integration**: Add optional external API calls in simulation logic; ensure both interfaces handle it; update charts for live data.
- **Enhanced security**: Implement full JWT/OAuth for HTTP/MCP and add frontend login if exposing beyond local.
- **UI expansion**: Evolve to a more interactive SPA (e.g., React) if complex interactions needed; add more dashboards like trade history tables.
- **When to split**: If interfaces diverge (e.g., frontend needs dedicated caching), extract to separate services. Monitor via added metrics; evolve when response times exceed 100ms or data volume hits 1GB.

## 📊 API Reference

### FastAPI REST Endpoints
```
GET  /                                    - Welcome message with server info
GET  /health                             - Health check for both servers
GET  /docs                               - Interactive API documentation

# Authentication
POST /api/v1/auth/token                  - Get access token
GET  /api/v1/auth/me                     - Get current user info

# Trading
GET  /api/v1/trading/quote/{symbol}      - Get stock quote
POST /api/v1/trading/order               - Create new order
GET  /api/v1/trading/orders              - Get all orders
GET  /api/v1/trading/order/{order_id}    - Get specific order
DEL  /api/v1/trading/order/{order_id}    - Cancel order

# Portfolio
GET  /api/v1/portfolio/                  - Get complete portfolio
GET  /api/v1/portfolio/summary           - Get portfolio summary
GET  /api/v1/portfolio/positions         - Get all positions
GET  /api/v1/portfolio/position/{symbol} - Get specific position
```

### MCP Tools
Available at `http://localhost:8001` via SSE transport:
```
get_stock_quote(symbol: str)                    - Get current stock quotes
create_buy_order(symbol, quantity, price)      - Place buy order
create_sell_order(symbol, quantity, price)     - Place sell order
get_all_orders()                                - Get all orders
get_order(order_id: str)                        - Get specific order
cancel_order(order_id: str)                     - Cancel order
get_portfolio()                                 - Get complete portfolio
get_portfolio_summary()                         - Get portfolio summary
get_all_positions()                             - Get all positions
get_position(symbol: str)                       - Get specific position
```

### Configuration
Environment variables (see `.env.example`):
```bash
# Server Configuration
MCP_SERVER_PORT=8001
MCP_SERVER_HOST=localhost

# Database & Redis (for future use)
DATABASE_URL=postgresql://user:pass@localhost/db
REDIS_URL=redis://localhost:6379

# Security
SECRET_KEY=your-secret-key
ACCESS_TOKEN_EXPIRE_MINUTES=30

# ADK Evaluations (optional)
GOOGLE_API_KEY=your-google-api-key
GOOGLE_MODEL=gemini-2.0-flash
MCP_HTTP_URL=http://localhost:8001/mcp
```

## 🧪 ADK Evaluations

Test your MCP server with Google ADK agent evaluations:

```bash
# 1. Set up environment
export GOOGLE_API_KEY="your-google-api-key"

# 2. Start MCP server
uv run python app/main.py

# 3. Run evaluation (in another terminal)
adk eval examples/google_adk_agent tests/evals/list_available_tools_test.json --config_file_path tests/evals/test_config.json

# 4. Verify setup
uv run python test_adk_setup.py
```

See [ADK Testing Guide](tests/evals/ADK-testing-evals.md) for detailed instructions.
