# Project TODO List: Open Paper Trading MCP

This document outlines the phased development plan to build out the key features of the Open Paper Trading MCP application. The focus is on moving from the current mocked implementation to a fully functional, persistent paper trading simulator.

---

## Phase 1: Core Engine & Persistence

**Goal:** Replace the in-memory mock service with a functional trading engine and a persistent database. This is the foundation for all other features.

-   [ ] **1. Implement Database Persistence:**
    -   [ ] Integrate `SQLite` for data storage.
    -   [ ] Create database models (using SQLAlchemy or similar) for `Accounts`, `Positions`, `Orders`, and `Transactions`.
    -   [ ] Initialize the database with a default user account and starting cash balance.

-   [ ] **2. Implement Real-time Market Data:**
    -   [ ] Integrate the Polygon.io API client to fetch real-time stock quotes.
    -   [ ] Replace the hard-coded `mock_quotes` in `TradingService` with live API calls.
    -   [ ] Add proper error handling for API failures (e.g., invalid symbol, rate limits).

-   [ ] **3. Implement Order Execution Logic:**
    -   [ ] When an order is created, check if the account has sufficient funds (for buys) or shares (for sells).
    -   [ ] Simulate order fills based on the current market price.
    -   [ ] Update order status from `PENDING` to `FILLED` or `FAILED`.
    -   [ ] Record a transaction in the database for every filled order.

-   [ ] **4. Implement Portfolio & Account Management:**
    -   [ ] When an order is filled, update the user's `Position` (quantity, average price).
    -   [ ] Update the user's cash balance.
    -   [ ] Recalculate portfolio metrics (`total_value`, `unrealized_pnl`, etc.) based on real-time data.

-   [ ] **5. Secure Endpoints:**
    -   [ ] Apply authentication middleware to all trading and portfolio endpoints to ensure they are protected.

---

## Phase 2: Enhancing Agent Capabilities & User Experience

**Goal:** Make the MCP agent more intelligent and provide a simple UI for visualization.

-   [ ] **1. Develop Advanced MCP Tools:**
    -   [ ] Create a tool to get historical price data for a stock (`get_historical_data`).
    -   [ ] Create a tool to fetch market news for a given symbol (`get_market_news`).
    -   [ ] Create a tool for basic technical analysis (e.g., `get_moving_average`).

-   [ ] **2. Implement a Basic Web UI:**
    -   [ ] Create a simple dashboard page using FastAPI templates (Jinja2).
    -   [ ] Display the current portfolio summary (total value, P&L).
    -   [ ] Show a table of current positions.
    -   [ ] List recent orders and their status.

-   [ ] **3. Improve Agent Context & Memory:**
    -   [ ] Implement a mechanism for the agent to remember the context of a conversation (e.g., remember the last stock it was asked about).
    -   [ ] Allow the agent to manage its own paper trading account.

---

## Phase 3: Advanced Features & Polish

**Goal:** Add more sophisticated trading features and improve the overall robustness of the application.

-   [ ] **1. Support for Advanced Order Types:**
    -   [ ] Implement logic for `LIMIT` and `STOP` orders.
    -   [ ] Add a background task that periodically checks market prices to trigger these orders.

-   [ ] **2. Multi-Account Support:**
    -   [ ] Allow the creation of multiple, named paper trading accounts.
    -   [ ] Enable the agent and API to specify which account to use for a transaction.

-   [ ] **3. Expand Test Coverage:**
    -   [ ] Write integration tests that cover the full order-to-portfolio update lifecycle.
    -   [ ] Create more complex ADK evaluation sets for the new agent tools.

-   [ ] **4. Documentation:**
    -   [ ] Update the `README.md` to reflect the new, functional implementation.
    -   [ ] Add detailed documentation for the API endpoints and MCP tools.
