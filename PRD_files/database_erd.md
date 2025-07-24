# Database Entity-Relationship Diagram (ERD)

## Core Trading Entities

```mermaid
erDiagram
    Account ||--o{ Position : has
    Account ||--o{ Order : places
    Account ||--o{ Transaction : creates
    Account ||--o{ MultiLegOrder : places
    Account ||--o{ RecognizedStrategy : has
    Account ||--o{ PortfolioGreeksSnapshot : tracks
    
    Order ||--o{ Transaction : generates
    
    MultiLegOrder ||--o{ OrderLeg : contains
    
    RecognizedStrategy ||--o{ StrategyPerformance : tracks
    
    Account {
        string id PK "UUID"
        string owner UK "Unique owner identifier"
        float cash_balance "Available cash"
        datetime created_at "Account creation time"
        datetime updated_at "Last update time"
    }
    
    Position {
        string id PK "UUID"
        string account_id FK "References Account.id"
        string symbol "Stock/asset symbol"
        int quantity "Number of shares/contracts"
        float avg_price "Average purchase price"
    }
    
    Order {
        string id PK "order_[8-char-uuid]"
        string account_id FK "References Account.id"
        string symbol "Stock/asset symbol"
        OrderType order_type "BUY/SELL"
        int quantity "Number of shares"
        float price "Limit price (null for market)"
        OrderStatus status "PENDING/FILLED/CANCELLED/FAILED"
        datetime created_at "Order creation time"
        datetime filled_at "Order fill time"
        float stop_price "Stop loss price"
        float trail_percent "Trailing stop percentage"
        float trail_amount "Trailing stop amount"
        datetime triggered_at "Trigger activation time"
        OrderCondition condition "MARKET/LIMIT/STOP/etc"
        float net_price "Net execution price"
    }
    
    Transaction {
        string id PK "UUID"
        string account_id FK "References Account.id"
        string order_id FK "References Order.id (nullable)"
        string symbol "Stock/asset symbol"
        int quantity "Number of shares traded"
        float price "Execution price"
        OrderType transaction_type "BUY/SELL"
        datetime timestamp "Transaction time"
    }
```

## Options Trading Entities

```mermaid
erDiagram
    OptionQuoteHistory {
        string id PK "UUID"
        string symbol "Option symbol"
        string underlying_symbol "Stock symbol"
        float strike "Strike price"
        date expiration_date "Expiration date"
        string option_type "call/put"
        float bid "Bid price"
        float ask "Ask price"
        float price "Market price"
        int volume "Trading volume"
        int open_interest "Open interest"
        float delta "Delta Greek"
        float gamma "Gamma Greek"
        float theta "Theta Greek"
        float vega "Vega Greek"
        float rho "Rho Greek"
        float charm "Charm (advanced Greek)"
        float vanna "Vanna (advanced Greek)"
        float speed "Speed (advanced Greek)"
        float zomma "Zomma (advanced Greek)"
        float color "Color (advanced Greek)"
        float implied_volatility "IV"
        float underlying_price "Stock price"
        datetime quote_time "Quote timestamp"
        string test_scenario "Test scenario name"
        datetime created_at "Record creation time"
    }
    
    MultiLegOrder {
        string id PK "mlo_[8-char-uuid]"
        string account_id FK "References Account.id"
        string order_type "limit/market"
        float net_price "Net order price"
        OrderStatus status "Order status"
        string strategy_type "spread/straddle/etc"
        string underlying_symbol "Stock symbol"
        datetime created_at "Order creation time"
        datetime filled_at "Order fill time"
    }
    
    OrderLeg {
        string id PK "UUID"
        string multi_leg_order_id FK "References MultiLegOrder.id"
        string symbol "Asset symbol"
        string asset_type "stock/option"
        int quantity "Number of shares/contracts"
        OrderType order_type "BUY/SELL"
        float price "Leg price"
        float strike "Option strike price"
        date expiration_date "Option expiration"
        string option_type "call/put"
        string underlying_symbol "Stock symbol"
        int filled_quantity "Executed quantity"
        float filled_price "Execution price"
    }
```

## Strategy and Performance Tracking

```mermaid
erDiagram
    RecognizedStrategy {
        string id PK "UUID"
        string account_id FK "References Account.id"
        string strategy_type "spread/covered_call/etc"
        string strategy_name "Strategy display name"
        string underlying_symbol "Stock symbol"
        float cost_basis "Initial investment"
        float max_profit "Maximum profit potential"
        float max_loss "Maximum loss potential"
        json breakeven_points "List of breakeven prices"
        json position_ids "List of position IDs"
        bool is_active "Strategy active status"
        datetime detected_at "Strategy detection time"
        datetime last_updated "Last update time"
    }
    
    StrategyPerformance {
        string id PK "UUID"
        string strategy_id FK "References RecognizedStrategy.id"
        float unrealized_pnl "Unrealized P&L"
        float realized_pnl "Realized P&L"
        float total_pnl "Total P&L"
        float pnl_percent "P&L percentage"
        float current_market_value "Current market value"
        float cost_basis "Cost basis"
        int days_held "Days held"
        float annualized_return "Annualized return"
        float delta_exposure "Delta exposure"
        float theta_decay "Theta decay"
        float vega_exposure "Vega exposure"
        datetime measured_at "Measurement time"
        float underlying_price "Stock price at measurement"
    }
    
    PortfolioGreeksSnapshot {
        string id PK "UUID"
        string account_id FK "References Account.id"
        date snapshot_date "Snapshot date"
        datetime snapshot_time "Snapshot time"
        float total_delta "Portfolio delta"
        float total_gamma "Portfolio gamma"
        float total_theta "Portfolio theta"
        float total_vega "Portfolio vega"
        float total_rho "Portfolio rho"
        float delta_normalized "Delta per $1000"
        float gamma_normalized "Gamma per $1000"
        float theta_normalized "Theta per $1000"
        float vega_normalized "Vega per $1000"
        float delta_dollars "Delta in dollars"
        float gamma_dollars "Gamma in dollars"
        float theta_dollars "Theta in dollars"
        float total_portfolio_value "Total portfolio value"
        float options_value "Options value"
        float stocks_value "Stocks value"
    }
```

## Test and Development Data

```mermaid
erDiagram
    DevStockQuote {
        string id PK "UUID"
        string symbol "Stock symbol (max 10 chars)"
        date quote_date "Quote date"
        decimal bid "Bid price (10,4)"
        decimal ask "Ask price (10,4)"
        decimal price "Market price (10,4)"
        bigint volume "Trading volume"
        string scenario "Test scenario (max 50 chars)"
        datetime created_at "Record creation time"
    }
    
    DevOptionQuote {
        string id PK "UUID"
        string symbol "Option symbol (max 20 chars)"
        string underlying "Stock symbol (max 10 chars)"
        date expiration "Expiration date"
        decimal strike "Strike price (10,2)"
        string option_type "call/put (max 4 chars)"
        date quote_date "Quote date"
        decimal bid "Bid price (10,4)"
        decimal ask "Ask price (10,4)"
        decimal price "Market price (10,4)"
        bigint volume "Trading volume"
        string scenario "Test scenario (max 50 chars)"
        datetime created_at "Record creation time"
    }
    
    DevScenario {
        string id PK "UUID"
        string name UK "Scenario name (max 100 chars)"
        text description "Scenario description"
        date start_date "Scenario start date"
        date end_date "Scenario end date"
        json symbols "List of symbols"
        string market_condition "volatile/calm/trending (max 20 chars)"
        datetime created_at "Record creation time"
    }
    
    OptionExpiration {
        string id PK "UUID"
        string underlying_symbol "Stock symbol"
        date expiration_date "Expiration date"
        bool is_processed "Processing status"
        datetime processed_at "Processing time"
        string processing_mode "automatic/manual"
        int expired_positions_count "Number of expired positions"
        int assignments_count "Number of assignments"
        int exercises_count "Number of exercises"
        int worthless_count "Number of worthless options"
        float total_cash_impact "Total cash impact"
        float fees_charged "Fees charged"
        datetime created_at "Record creation time"
        text notes "Processing notes"
    }
```

## Key Database Design Principles

### Primary Keys
- **Accounts**: String UUID for global uniqueness
- **Orders**: Prefixed format `order_[8-char-uuid]` for easy identification
- **Multi-leg Orders**: Prefixed format `mlo_[8-char-uuid]` for easy identification
- **All Others**: Standard UUID strings

### Foreign Key Relationships
- **No CASCADE DELETE**: Referential integrity prevents orphaned records
- **Account-centric**: All trading entities reference Account.id
- **Order tracking**: Transactions optionally reference Order.id

### Unique Constraints
- **Account.owner**: One account per owner
- **DevScenario.name**: Unique test scenario names

### Indexes for Performance
- **Composite indexes** on frequently queried combinations
- **Symbol-based indexes** for market data queries
- **Time-based indexes** for historical analysis
- **Status-based indexes** for order processing

### Data Types
- **Timestamps**: DateTime with automatic server defaults
- **Money**: Float for simplicity (consider Decimal for production)
- **Enums**: SQLAlchemy Enums for order types, statuses, conditions
- **JSON**: For flexible data like breakeven points, position lists