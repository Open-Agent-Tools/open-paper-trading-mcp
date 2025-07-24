# Open Paper Trading MCP 📈

A comprehensive paper trading simulator with dual interfaces: REST API (FastAPI) and AI agent tools (MCP). Designed for algorithmic trading development, strategy backtesting, options trading simulation, and training AI agents in realistic market environments without financial risk.

## 🎯 Core Capabilities

- **Multi-Asset Trading**: Stocks, options, ETFs, and bonds with specialized implementations
- **Options Trading**: Full options chain support with Greeks calculations (delta, gamma, theta, vega, rho)
- **AI Agent Training**: Native MCP interface for training trading agents and LLMs
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
                   +------------------+------------------+
                   |                                     |
        (Direct Read/Write)                   (Market Data Queries)
                   V                                     V
         +-----------------+                   +-----------------+
         | PostgreSQL DB   |                   |  Robinhood API  |
         | (Trading State) |                   |  (Market Data)  |
         +-----------------+                   +-----------------+
```

**Key Design Decisions:**
- **Simplified Architecture**: Direct connection between TradingService and data sources
- **Database-First**: All trading state persisted in PostgreSQL
- **Real-time Market Data**: Direct API calls to Robinhood for current market information
- **Async Throughout**: Uses asyncio for high performance
- **Type Safety**: Full Pydantic validation on all inputs/outputs

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

