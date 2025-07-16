# Open Paper Trading MCP 📈

A comprehensive paper trading simulator with dual interfaces: REST API (FastAPI) and AI agent tools (MCP). Designed for algorithmic trading development, strategy backtesting, options trading simulation, and training AI agents in realistic market environments without financial risk.

## 🎯 Core Capabilities

- **Multi-Asset Trading**: Stocks, options, ETFs, and bonds with specialized implementations
- **Options Trading**: Full options chain support with Greeks calculations (delta, gamma, theta, vega, rho)
- **Strategy Development**: Build and test algorithmic trading strategies with backtesting framework  
- **AI Agent Training**: Native MCP interface for training trading agents and LLMs
- **Educational Platform**: Risk-free environment for learning market mechanics and trading concepts
- **Production-Ready**: Type-safe, async architecture with comprehensive testing and monitoring

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

**Key Design Decisions:**
- **Monolithic Architecture**: Both servers run in one process, sharing the TradingService
- **Database-First**: All state persisted in PostgreSQL, no in-memory storage
- **Async Throughout**: Uses asyncio for high performance
- **Type Safety**: Full Pydantic validation on all inputs/outputs

## 🛠️ Development

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

### Phase 0: Infrastructure ✅ COMPLETE
- **Dual Interface**: REST API + MCP tools in one application
- **Mock Trading**: Simulated orders with hardcoded market data  
- **Portfolio Tracking**: Basic position and P&L calculations
- **Docker Setup**: Full containerization with PostgreSQL
- **Type Safety**: 100% typed with Pydantic validation

### Phase 1: Core Trading Engine 🚧 IN PROGRESS
- **Database Integration**: Persistent storage for all trading data
- **Account Management**: Multi-account support with ownership tracking
- **Real Market Data**: Polygon.io integration for live prices
- **Order Execution**: Realistic fill simulation with balance checks
- **Portfolio History**: Track performance over time

### Phase 2: Options Trading & Greeks 📊 PLANNED
- **Options Chain Support**: Real-time options quotes and Greeks calculations
- **Complex Orders**: Multi-leg strategies (covered calls, spreads, straddles)
- **Automatic Expiration**: Handle option expirations and assignments
- **Risk Management**: Position sizing and margin requirements
- **Options Education**: Interactive learning tools for options mechanics

### Phase 3: Backtesting Framework 📈 PLANNED
- **Historical Data**: Integrated data feeds for strategy testing
- **Strategy Engine**: Plugin architecture for custom trading algorithms
- **Performance Analytics**: Sharpe ratio, drawdown, win rate analysis
- **Simulation Quality**: Realistic slippage, commissions, and market impact
- **Comparative Analysis**: A/B testing multiple strategies

### Phase 4: Advanced Features 🚀 PLANNED
- **Machine Learning**: Integrate ML models for predictive analytics
- **Paper Trading Competitions**: Multi-user contests and leaderboards
- **Advanced Charts**: Technical analysis tools and indicators
- **News Integration**: Sentiment analysis and event-driven trading
- **International Markets**: Multi-currency and global exchange support

### Phase 5: Educational & Community 🎓 PLANNED
- **Interactive Tutorials**: Guided lessons for beginners to advanced
- **Strategy Library**: Community-contributed trading algorithms
- **Mentorship Tools**: Pair experienced traders with learners
- **Certification System**: Skills validation and achievement tracking
- **Research Tools**: Academic features for finance education

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

### Example Usage

```python
# Place a market order
response = create_buy_order(
    symbol="AAPL",
    quantity=100,
    price=195.20
)

# Check portfolio performance
summary = get_portfolio_summary()
print(f"Total Value: ${summary['total_value']:,.2f}")
print(f"Daily P&L: ${summary['daily_pnl']:,.2f}")
```

### Future MCP Tools (Roadmap)

| Phase | Tool | Description |
|-------|------|-------------|
| **Phase 2** | `get_options_chain` | Retrieve options quotes with Greeks for a symbol |
| | `create_multi_leg_order` | Execute complex strategies (spreads, straddles) |
| | `calculate_option_greeks` | Compute delta, gamma, theta, vega, rho |
| | `get_expiration_dates` | List available option expiration dates |
| **Phase 3** | `backtest_strategy` | Run historical simulation of trading strategy |
| | `get_historical_data` | Retrieve price history for backtesting |
| | `analyze_performance` | Calculate Sharpe ratio, drawdown metrics |
| | `simulate_order_impact` | Preview order effects without execution |
| **Phase 4** | `get_technical_indicators` | Calculate SMA, EMA, RSI, MACD |
| | `search_symbols` | Find stocks by company name or sector |
| | `get_news_sentiment` | Analyze news impact on stock prices |
| | `set_price_alerts` | Create notifications for price movements |

## 📊 REST API Examples

### Create an Order
```bash
curl -X POST http://localhost:2080/api/v1/trading/order \
  -H "Content-Type: application/json" \
  -d '{
    "symbol": "AAPL",
    "order_type": "BUY",
    "quantity": 100,
    "price": 195.20
  }'
```

### Get Portfolio Summary
```bash
curl http://localhost:2080/api/v1/portfolio/summary
```

### View All Positions
```bash
curl http://localhost:2080/api/v1/portfolio/positions
```

## 🧪 Testing

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
- **MCP Protocol**: [Anthropic MCP Docs](https://modelcontextprotocol.io/)
- **Development Plan**: See [TODO.md](TODO.md)
- **Claude Integration**: See [CLAUDE.md](CLAUDE.md)

## 🤝 Contributing

1. Fork the repository
2. Create a feature branch (`git checkout -b feature/amazing-feature`)
3. Run tests and linting (`python scripts/dev.py check`)
4. Commit your changes
5. Push to the branch
6. Open a Pull Request

## 📄 License

MIT License - see LICENSE file for details.

