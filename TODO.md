# Project TODO List: Open Paper Trading MCP

This document outlines the phased development plan to build out the key features of the Open Paper Trading MCP application. The focus is on moving from the current mocked implementation to a fully functional, persistent paper trading simulator.

---

## Phase 0: Scaffolding & Infrastructure (✓ Complete)

**Goal:** Establish a robust, containerized foundation for the application with a persistent database.

-   [x] **1. Containerize the Application:**
    -   [x] Create a `Dockerfile` for the main application.
    -   [x] Create a `docker-compose.yml` to manage services.
    -   [x] Configure the application to run within Docker.

-   [x] **2. Implement Database Persistence:**
    -   [x] Integrate `PostgreSQL` as the database service in Docker Compose.
    -   [x] Create database models for `Account`, `Position`, `Order`, and `Transaction`.
    -   [x] Configure the application to connect to the database.
    -   [x] Implement logic to create database tables on startup.

-   [x] **3. Containerize the Test Runner:**
    -   [x] Create a `Dockerfile.test` for the ADK evaluation runner.
    -   [x] Add a `test-runner` service to Docker Compose.
    -   [x] Create a helper script (`run_adk_eval.sh`) as the entrypoint.

---

## Phase 1: Core Engine Implementation

**Goal:** Replace the in-memory mock service with a functional trading engine that uses the persistent database.

-   [ ] **1. Implement Account Management:**
    -   [ ] Create a default trading account on the first run.
    -   [ ] Update the `auth` endpoints to link users to a trading account.
    -   [ ] Create an API endpoint to view account details and balance.

-   [ ] **2. Implement Real-time Market Data:**
    -   [ ] Integrate the Polygon.io API client to fetch real-time stock quotes.
    -   [ ] Replace the hard-coded `mock_quotes` in `TradingService` with live API calls.
    -   [ ] Add proper error handling for API failures (e.g., invalid symbol, rate limits).

-   [ ] **3. Implement Order Execution Logic:**
    -   [ ] **Crucial Step:** Rewrite `TradingService` methods (`create_order`, `cancel_order`, etc.) to interact with the database.
    -   [ ] When an order is created, check if the account has sufficient funds (for buys) or shares (for sells).
    -   [ ] Simulate order fills based on the current market price.
    -   [ ] Update order status from `PENDING` to `FILLED` or `FAILED` in the database.
    -   [ ] Record a transaction in the `transactions` table for every filled order.

-   [ ] **4. Implement Portfolio Management:**
    -   [ ] When an order is filled, create or update the user's `Position` in the database.
    -   [ ] Update the user's cash balance in the `accounts` table.
    -   [ ] Rewrite portfolio endpoints (`get_portfolio`, `get_positions`, etc.) to calculate results from database tables and live market data.

---

## Phase 2: Enhancing Agent Capabilities & User Experience

**Goal:** Make the MCP agent more intelligent and provide a simple UI for visualization.

-   [ ] **1. Develop Advanced MCP Tools:**
    -   [ ] Create a tool for basic technical analysis (e.g., `get_moving_average`).

-   [ ] **2. Implement a Basic Web UI:**
    -   [ ] Create a simple dashboard page using FastAPI templates (Jinja2).
    -   [ ] Display the current portfolio summary (total value, P&L).
    -   [ ] Show a table of current positions.
    -   [ ] List recent orders and their status.

---

## Phase 3: Advanced Features & Polish

**Goal:** Add more sophisticated trading features and improve the overall robustness of the application.

-   [ ] **1. Support for Advanced Order Types:**
    -   [ ] Implement logic for `LIMIT` and `STOP` orders.
    -   [ ] Add a background task that periodically checks market prices to trigger these orders.

-   [ ] **2. Expand Test Coverage:**
    -   [ ] Write integration tests that cover the full order-to-portfolio update lifecycle.
    -   [ ] Create more complex ADK evaluation sets for the new agent tools.