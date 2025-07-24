# Key Entity Properties Definition

## Account Entity
**Purpose**: Core user account for paper trading with cash balance management

### Required Properties
- `id` (String, PK): UUID identifier for global uniqueness
- `owner` (String, UK): Unique identifier for account owner (email, username, etc.)
- `cash_balance` (Float): Available cash for trading (default: $100,000)
- `created_at` (DateTime): Account creation timestamp (auto-generated)
- `updated_at` (DateTime): Last modification timestamp (auto-updated)

### Key Constraints
- Primary key: `id`
- Unique constraint: `owner` (one account per owner)
- Not null: `id`, `owner`, `cash_balance`
- Index: `owner` for fast lookups

### Business Rules
- Starting cash balance: $100,000 (configurable)
- Cash balance can go negative (margin trading simulation)
- Owner must be unique across system
- Timestamps automatically managed by database

---

## Order Entity
**Purpose**: Individual trading orders with comprehensive order management features

### Required Properties
- `id` (String, PK): Prefixed format "order_[8-char-uuid]" for easy identification
- `account_id` (String, FK): References Account.id
- `symbol` (String): Stock/asset symbol (e.g., "AAPL", "GOOGL")
- `order_type` (OrderType Enum): BUY or SELL
- `quantity` (Integer): Number of shares/contracts
- `status` (OrderStatus Enum): PENDING, FILLED, CANCELLED, FAILED, REJECTED

### Optional Properties
- `price` (Float): Limit price (null for market orders)
- `condition` (OrderCondition Enum): MARKET, LIMIT, STOP, STOP_LIMIT, TRAILING_STOP
- `stop_price` (Float): Stop loss trigger price
- `trail_percent` (Float): Trailing stop percentage
- `trail_amount` (Float): Trailing stop dollar amount
- `net_price` (Float): Net execution price after fees
- `created_at` (DateTime): Order creation time (auto-generated)
- `filled_at` (DateTime): Order execution time
- `triggered_at` (DateTime): Stop/trail trigger activation time

### Key Constraints
- Primary key: `id`
- Foreign key: `account_id` → `accounts.id`
- Not null: `id`, `account_id`, `symbol`, `order_type`, `quantity`, `status`
- Indexes: `account_id`, `symbol`, `status`, `created_at`

### Business Rules
- Market orders: `price` is null
- Limit orders: `price` is required
- Stop orders: `stop_price` is required
- Trailing stops: `trail_percent` OR `trail_amount` (not both)
- Order lifecycle: PENDING → FILLED/CANCELLED/FAILED/REJECTED
- Partial fills not supported (simplification)

---

## Position Entity
**Purpose**: Current holdings in accounts with average cost tracking

### Required Properties
- `id` (String, PK): UUID identifier
- `account_id` (String, FK): References Account.id
- `symbol` (String): Stock/asset symbol
- `quantity` (Integer): Current position size (positive/negative for long/short)
- `avg_price` (Float): Average cost basis per share

### Key Constraints
- Primary key: `id`
- Foreign key: `account_id` → `accounts.id`
- Not null: all fields
- Composite index: `(account_id, symbol)` for fast position lookups

### Business Rules
- Position quantity can be positive (long) or negative (short)
- Average price recalculated on each buy transaction
- Position is closed when quantity reaches zero
- Cost basis tracking for P&L calculations

---

## Transaction Entity
**Purpose**: Immutable record of all executed trades

### Required Properties
- `id` (String, PK): UUID identifier
- `account_id` (String, FK): References Account.id
- `symbol` (String): Stock/asset symbol traded
- `quantity` (Integer): Number of shares traded (always positive)
- `price` (Float): Execution price per share
- `transaction_type` (OrderType Enum): BUY or SELL
- `timestamp` (DateTime): Trade execution time (auto-generated)

### Optional Properties
- `order_id` (String, FK): References Order.id (null for manual transactions)

### Key Constraints
- Primary key: `id`
- Foreign key: `account_id` → `accounts.id`
- Foreign key: `order_id` → `orders.id` (nullable)
- Not null: `id`, `account_id`, `symbol`, `quantity`, `price`, `transaction_type`
- Indexes: `account_id`, `symbol`, `timestamp`

### Business Rules
- Immutable records (no updates after creation)
- Quantity always positive (direction indicated by transaction_type)
- One transaction per order execution (no partial fills)
- Automatic timestamp on creation

---

## MultiLegOrder Entity
**Purpose**: Complex options orders with multiple legs (spreads, combinations)

### Required Properties
- `id` (String, PK): Prefixed format "mlo_[8-char-uuid]"
- `account_id` (String, FK): References Account.id
- `status` (OrderStatus Enum): Order status

### Optional Properties
- `order_type` (String): "limit" or "market"
- `net_price` (Float): Net order price across all legs
- `strategy_type` (String): "spread", "straddle", "iron_condor", etc.
- `underlying_symbol` (String): Stock symbol for options strategy
- `created_at` (DateTime): Order creation time
- `filled_at` (DateTime): Order execution time

### Key Constraints
- Primary key: `id`
- Foreign key: `account_id` → `accounts.id`
- Not null: `id`, `account_id`, `status`

### Business Rules
- Must have at least 2 order legs
- All legs execute atomically (all or nothing)
- Net price is sum of all leg prices
- Strategy type auto-detected from leg configuration

---

## OrderLeg Entity
**Purpose**: Individual components of multi-leg orders

### Required Properties
- `id` (String, PK): UUID identifier
- `multi_leg_order_id` (String, FK): References MultiLegOrder.id
- `symbol` (String): Asset symbol
- `asset_type` (String): "stock" or "option"
- `quantity` (Integer): Number of shares/contracts
- `order_type` (OrderType Enum): BUY or SELL

### Optional Properties
- `price` (Float): Leg-specific price
- `strike` (Float): Option strike price (null for stocks)
- `expiration_date` (Date): Option expiration (null for stocks)
- `option_type` (String): "call" or "put" (null for stocks)
- `underlying_symbol` (String): Stock symbol (for options)
- `filled_quantity` (Integer): Executed quantity
- `filled_price` (Float): Execution price

### Key Constraints
- Primary key: `id`
- Foreign key: `multi_leg_order_id` → `multi_leg_orders.id`
- Not null: `id`, `multi_leg_order_id`, `symbol`, `asset_type`, `quantity`, `order_type`

### Business Rules
- Options legs require: `strike`, `expiration_date`, `option_type`, `underlying_symbol`
- Stock legs: option fields must be null
- Filled quantities track execution progress
- All legs in order must fill together

---

## Key Design Decisions

### 1. UUID vs Integer IDs
- **Choice**: String UUIDs for global uniqueness
- **Rationale**: Enables distributed systems, prevents ID guessing, easier debugging
- **Trade-off**: Slightly larger storage, but better for microservices architecture

### 2. Prefixed Order IDs
- **Choice**: "order_[uuid]" and "mlo_[uuid]" formats
- **Rationale**: Easy identification in logs, customer support, debugging
- **Implementation**: Generated in SQLAlchemy default functions

### 3. Float vs Decimal for Money
- **Choice**: Float for prices and balances
- **Rationale**: Simplicity for paper trading, performance
- **Production Note**: Consider Decimal(10,4) for real money systems

### 4. Enum Usage
- **Choice**: SQLAlchemy Enums for order types, statuses, conditions
- **Rationale**: Type safety, database constraints, clear API contracts
- **Benefits**: Prevents invalid data, clear documentation

### 5. Soft vs Hard Deletes
- **Choice**: No soft deletes implemented
- **Rationale**: Immutable transaction history, referential integrity
- **Trade-off**: Cannot "undo" operations, but maintains audit trail

### 6. Timestamp Strategy
- **Choice**: Automatic server-side timestamps
- **Rationale**: Consistent timezone handling, prevents client clock issues
- **Implementation**: `server_default=func.now()` with `onupdate` for updates

### 7. Index Strategy
- **Choice**: Comprehensive composite indexes
- **Rationale**: Optimized for common query patterns
- **Coverage**: Account-based queries, symbol lookups, time-based analysis, status filtering