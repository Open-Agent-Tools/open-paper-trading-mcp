# Data Migration and Persistence Plan

## Overview
This document outlines the phased approach to migrate all paper trading tracking from in-memory storage to PostgreSQL database, integrate with Robinhood for live quotes, and reconcile the model/schema architecture.

## Current Issues Identified

### 1. In-Memory Storage (Critical)
- **TradingService** (`app/services/trading_service.py`):
  - `self.orders: List[Order] = []` (line 51)
  - `self.portfolio_positions: List[Position] = []` (line 54)
  - `self.cash_balance: float = 100000.0` (line 55)
  - `self.mock_quotes` dictionary (lines 60-93)
  - Direct list operations: `self.orders.append(order)` (line 715)

### 2. Quote System Issues
- Mock quotes hardcoded in TradingService
- Robinhood adapter exists but not fully integrated
- Test data stored in cache instead of database

### 3. Model/Schema Confusion
- Duplicate definitions in `app/models/trading.py` (backwards compatibility)
- Inconsistent imports across codebase
- Schema objects used where database models should be used

## Phase 1: Remove In-Memory Storage ✅ COMPLETED [2025-07-16]

**Status:** This phase has been completed as part of the comprehensive codebase refactoring and type safety improvements. All in-memory storage has been removed and replaced with proper database persistence. The MyPy-driven refactoring successfully addressed the architectural issues identified in this section.

### Key Accomplishments:

1. **Removed All In-Memory Storage**:
   - Eliminated `self.orders: List[Order] = []`
   - Eliminated `self.portfolio_positions: List[Position] = []`
   - Eliminated `self.cash_balance: float = 100000.0`
   - Eliminated `self.mock_quotes` dictionary

2. **Complete Async Migration**:
   - Unified production and test database logic
   - Implemented correct asynchronous service patterns
   - All database operations now use async/await patterns
   - Removed synchronous fallback logic

3. **Database-First Architecture**:
   - All persistent state stored in PostgreSQL
   - Service layer reads/writes to database, never holds state in memory
   - Account queries replace cash balance references
   - Position queries replace in-memory lists

4. **Testing Infrastructure**:
   - Updated test suite for async operations
   - Removed database session mocks
   - Added proper integration tests
   - Verified data persistence across service restarts

5. **Type Safety Improvements**:
   - MyPy errors reduced from 567 → 0 (100% resolution)
   - Modern SQLAlchemy 2.0 implementation
   - Complete schema/model separation
   - Full ruff integration for formatting and linting

6. **Documentation Updates**:
   - Updated CLAUDE.md to remove in-memory storage references
   - Added migration notes for future reference
   - Documented architectural decisions

## Phase 2: Integrate Robinhood for Live Quotes ✅ COMPLETED [2025-07-17]

**Status:** Phase 2 has been successfully completed with all mandatory QA requirements addressed. The RobinhoodAdapter now includes comprehensive testing, robust error handling, performance monitoring, and cache warming capabilities.

### Key Accomplishments:

1. **RobinhoodAdapter Implementation**:
   - Fully integrated with `robin_stocks` library for live market data
   - Proper async/await patterns throughout all methods
   - Support for stock quotes, options chains, and market hours
   - Comprehensive error handling and retry mechanisms

2. **Robust Authentication System**:
   - Enhanced `SessionManager` with exponential backoff and circuit breaker
   - Automatic authentication recovery with token management
   - Specific exception handling for 4xx/5xx responses
   - Comprehensive authentication metrics and monitoring

3. **Cache Warming Implementation**:
   - Automatic cache warming on application startup
   - Configurable popular symbols (AAPL, GOOGL, MSFT, TSLA, etc.)
   - Concurrent request limiting and retry logic
   - Performance monitoring and statistics

4. **Comprehensive Testing Suite**:
   - Unit tests for `RobinhoodAdapter` covering all functionality
   - Integration tests for `TradingService`-`RobinhoodAdapter` integration
   - Tests for authentication logic, retry mechanisms, and error handling
   - Performance benchmarks and concurrent request testing

5. **Performance and Monitoring**:
   - Structured logging with contextual information
   - Performance metrics collection (request duration, cache hit/miss ratios)
   - Rate limit monitoring and enforcement
   - Comprehensive error classification and handling

6. **Adapter Factory System**:
   - Dynamic adapter creation and configuration
   - Runtime adapter switching capabilities
   - Proper failover support between adapters
   - Environment variable configuration

7. **Production Features**:
   - Proper session lifecycle management
   - Connection pooling and resource management
   - Graceful degradation and error recovery
   - Docker configuration with persistent token storage

### Final QA Requirements Addressed:
- ✅ **Cache Warming Activation**: Implemented in `app/main.py` lifespan function
- ✅ **Integration Test Corrections**: Fixed tests to verify actual component integration
- ✅ **Comprehensive Unit Tests**: Created for all adapter functionality
- ✅ **Robust Error Handling**: Exponential backoff, circuit breaker, and recovery mechanisms
- ✅ **Performance Monitoring**: Structured logging and metrics collection throughout

## Phase 3: Migrate Test Data to Database

### 3.1 Create Database Models for Test Data

#### 3.1.1 Create Stock Quote Test Model (`app/models/database/trading.py`)
- [ ] **Add TestStockQuote model** after existing models:
  ```python
  class TestStockQuote(Base):
      __tablename__ = "test_stock_quotes"
      
      id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
      symbol = Column(String(10), nullable=False, index=True)
      quote_date = Column(Date, nullable=False, index=True)
      bid = Column(Numeric(10, 4), nullable=True)
      ask = Column(Numeric(10, 4), nullable=True)
      price = Column(Numeric(10, 4), nullable=True)
      volume = Column(BigInteger, nullable=True)
      scenario = Column(String(50), nullable=True, index=True)
      created_at = Column(DateTime, default=datetime.utcnow)
      
      # Add composite indexes for efficient queries
      __table_args__ = (
          Index('idx_test_stock_symbol_date', 'symbol', 'quote_date'),
          Index('idx_test_stock_scenario', 'scenario', 'quote_date'),
      )
  ```

#### 3.1.2 Create Option Quote Test Model (extend existing)
- [ ] **Add test scenario field** to existing `OptionQuoteHistory`:
  ```python
  # Add to existing OptionQuoteHistory model (line 115):
  test_scenario = Column(String(50), nullable=True, index=True)
  ```

- [ ] **Create TestOptionQuote model** for simplified test data:
  ```python
  class TestOptionQuote(Base):
      __tablename__ = "test_option_quotes"
      
      id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
      symbol = Column(String(20), nullable=False, index=True)
      underlying = Column(String(10), nullable=False, index=True)
      expiration = Column(Date, nullable=False)
      strike = Column(Numeric(10, 2), nullable=False)
      option_type = Column(String(4), nullable=False)  # 'call' or 'put'
      quote_date = Column(Date, nullable=False, index=True)
      bid = Column(Numeric(10, 4), nullable=True)
      ask = Column(Numeric(10, 4), nullable=True)
      price = Column(Numeric(10, 4), nullable=True)
      volume = Column(BigInteger, nullable=True)
      scenario = Column(String(50), nullable=True, index=True)
      created_at = Column(DateTime, default=datetime.utcnow)
      
      __table_args__ = (
          Index('idx_test_option_underlying_date', 'underlying', 'quote_date'),
          Index('idx_test_option_scenario', 'scenario', 'quote_date'),
      )
  ```

#### 3.1.3 Create Test Scenarios Model
- [ ] **Add TestScenario model** for scenario management:
  ```python
  class TestScenario(Base):
      __tablename__ = "test_scenarios"
      
      id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
      name = Column(String(100), nullable=False, unique=True)
      description = Column(Text, nullable=True)
      start_date = Column(Date, nullable=False)
      end_date = Column(Date, nullable=False)
      symbols = Column(ARRAY(String), nullable=False)  # Array of symbols
      market_condition = Column(String(20), nullable=True)  # 'volatile', 'calm', 'trending'
      created_at = Column(DateTime, default=datetime.utcnow)
      
      # Add index for efficient scenario queries
      __table_args__ = (
          Index('idx_test_scenario_dates', 'start_date', 'end_date'),
      )
  ```

### 3.2 Create Data Migration Script

#### 3.2.1 Create Migration Script (`scripts/migrate_test_data.py`)
- [ ] **Create script structure**:
  ```python
  import asyncio
  import gzip
  import csv
  from datetime import datetime, date
  from typing import List, Dict, Any
  from app.models.database.trading import TestStockQuote, TestOptionQuote, TestScenario
  from app.storage.database import SessionLocal
  
  class TestDataMigrator:
      def __init__(self):
          self.db = SessionLocal()
          
      async def migrate_existing_data(self):
          """Migrate existing CSV data to database."""
          pass
          
      async def generate_expanded_dataset(self):
          """Generate expanded test dataset."""
          pass
          
      async def create_test_scenarios(self):
          """Create predefined test scenarios."""
          pass
  ```

#### 3.2.2 Parse Existing CSV Data
- [ ] **Implement CSV parsing** from `app/adapters/test_data/data.csv.gz`:
  ```python
  async def parse_csv_data(self) -> List[Dict[str, Any]]:
      """Parse existing compressed CSV data."""
      data_file = "app/adapters/test_data/data.csv.gz"
      records = []
      
      with gzip.open(data_file, 'rt') as f:
          reader = csv.DictReader(f, delimiter='\t')
          for row in reader:
              records.append({
                  'symbol': row['symbol'],
                  'date': datetime.strptime(row['date'], '%Y-%m-%d').date(),
                  'bid': float(row['bid']),
                  'ask': float(row['ask']),
                  'price': (float(row['bid']) + float(row['ask'])) / 2
              })
      return records
  ```

#### 3.2.3 Generate Expanded Test Dataset
- [ ] **Create data generator** for multiple symbols and dates:
  ```python
  EXPANDED_SYMBOLS = [
      'AAPL', 'GOOGL', 'MSFT', 'TSLA', 'AMZN', 'NVDA', 'META', 'NFLX',
      'SPY', 'QQQ', 'IWM', 'GLD', 'AAL', 'AMD', 'F', 'GE'
  ]
  
  TEST_DATE_RANGES = [
      ('2017-01-27', '2017-01-28'),  # Existing calm period
      ('2017-03-24', '2017-03-25'),  # Existing volatile period
      ('2023-01-01', '2023-01-31'),  # Recent calm period
      ('2023-03-01', '2023-03-31'),  # Recent volatile period
  ]
  
  async def generate_stock_quotes(self, scenario: str, symbols: List[str], date_range: tuple):
      """Generate realistic stock quotes for test scenarios."""
      pass
  ```

#### 3.2.4 Create Option Chain Data
- [ ] **Generate option chains** for each underlying:
  ```python
  async def generate_option_chains(self, underlying: str, quote_date: date, underlying_price: float):
      """Generate complete option chains for testing."""
      expirations = [
          quote_date + timedelta(days=7),   # Weekly
          quote_date + timedelta(days=30),  # Monthly
          quote_date + timedelta(days=90),  # Quarterly
      ]
      
      for expiration in expirations:
          for strike in self._generate_strikes(underlying_price):
              for option_type in ['call', 'put']:
                  # Generate option quote with realistic pricing
                  pass
  ```

### 3.3 Update TestDataAdapter to Use Database

#### 3.3.1 Refactor TestDataAdapter (`app/adapters/test_data.py`)
- [ ] **Remove file-based cache** (lines 62, 81):
  - Delete `self._cache: Optional[Dict[str, Any]] = None`
  - Remove file parsing logic from `_load_data()` method

- [ ] **Add database query methods**:
  ```python
  async def _get_stock_quote(self, symbol: str, quote_date: date, scenario: str = None) -> Optional[StockQuote]:
      """Get stock quote from database."""
      db = SessionLocal()
      try:
          query = db.query(TestStockQuote).filter(
              TestStockQuote.symbol == symbol,
              TestStockQuote.quote_date == quote_date
          )
          if scenario:
              query = query.filter(TestStockQuote.scenario == scenario)
          
          record = query.first()
          if record:
              return StockQuote(
                  symbol=record.symbol,
                  price=float(record.price),
                  bid=float(record.bid),
                  ask=float(record.ask),
                  volume=record.volume or 0,
                  last_updated=datetime.combine(record.quote_date, datetime.min.time())
              )
      finally:
          db.close()
      return None
  ```

#### 3.3.2 Add Scenario Support
- [ ] **Add scenario selection** to adapter constructor:
  ```python
  def __init__(self, scenario: str = "default"):
      self.scenario = scenario
      self.current_date = date(2017, 3, 24)  # Default test date
      self._cache = {}  # Keep small cache for performance
  ```

- [ ] **Implement scenario switching**:
  ```python
  async def switch_scenario(self, scenario_name: str) -> None:
      """Switch to different test scenario."""
      db = SessionLocal()
      try:
          scenario = db.query(TestScenario).filter(
              TestScenario.name == scenario_name
          ).first()
          if scenario:
              self.scenario = scenario_name
              self.current_date = scenario.start_date
              self._cache.clear()  # Clear cache when switching
      finally:
          db.close()
  ```

#### 3.3.3 Implement Efficient Caching
- [ ] **Add database result caching**:
  ```python
  from functools import lru_cache
  from datetime import timedelta
  
  @lru_cache(maxsize=1000)
  async def _cached_stock_quote(self, symbol: str, quote_date: date, scenario: str) -> Optional[StockQuote]:
      """Cached version of stock quote lookup."""
      return await self._get_stock_quote(symbol, quote_date, scenario)
  ```

### 3.4 Create Bulk Data Management

#### 3.4.1 Create Data Loader Utilities (`scripts/data_loader.py`)
- [ ] **Create bulk loader class**:
  ```python
  class TestDataLoader:
      def __init__(self):
          self.batch_size = 1000
          
      async def bulk_load_stock_quotes(self, quotes: List[Dict]) -> None:
          """Efficiently load stock quotes in batches."""
          db = SessionLocal()
          try:
              for i in range(0, len(quotes), self.batch_size):
                  batch = quotes[i:i + self.batch_size]
                  objects = [TestStockQuote(**quote) for quote in batch]
                  db.bulk_save_objects(objects)
                  db.commit()
          finally:
              db.close()
  ```

#### 3.4.2 Add Data Validation
- [ ] **Create validation utilities**:
  ```python
  class TestDataValidator:
      def validate_stock_quote(self, quote: Dict) -> bool:
          """Validate stock quote data."""
          required_fields = ['symbol', 'quote_date', 'bid', 'ask']
          return all(field in quote for field in required_fields)
          
      def validate_price_consistency(self, quote: Dict) -> bool:
          """Ensure bid <= price <= ask."""
          return quote['bid'] <= quote['price'] <= quote['ask']
  ```

### 3.5 Implement Time-Based Data Selection

#### 3.5.1 Add Date Range Queries
- [ ] **Add date range support** to TestDataAdapter:
  ```python
  async def get_quotes_for_date_range(self, symbol: str, start_date: date, end_date: date) -> List[StockQuote]:
      """Get quotes for a date range (backtesting support)."""
      db = SessionLocal()
      try:
          records = db.query(TestStockQuote).filter(
              TestStockQuote.symbol == symbol,
              TestStockQuote.quote_date >= start_date,
              TestStockQuote.quote_date <= end_date,
              TestStockQuote.scenario == self.scenario
          ).order_by(TestStockQuote.quote_date).all()
          
          return [self._convert_to_stock_quote(record) for record in records]
      finally:
          db.close()
  ```

#### 3.5.2 Add Backtesting Support
- [ ] **Implement time travel functionality**:
  ```python
  async def set_current_date(self, current_date: date) -> None:
      """Set current date for backtesting."""
      self.current_date = current_date
      self._cache.clear()  # Clear cache when date changes
      
  async def advance_date(self, days: int = 1) -> None:
      """Advance current date by specified days."""
      self.current_date += timedelta(days=days)
      self._cache.clear()
  ```

### 3.6 Create Predefined Test Scenarios

#### 3.6.1 Define Test Scenarios (`scripts/create_scenarios.py`)
- [ ] **Create scenario definitions**:
  ```python
  PREDEFINED_SCENARIOS = {
      "calm_market": {
          "name": "Calm Market Conditions",
          "description": "Low volatility, steady price movements",
          "start_date": date(2017, 1, 27),
          "end_date": date(2017, 1, 28),
          "market_condition": "calm",
          "symbols": ["AAPL", "GOOGL", "MSFT", "SPY"]
      },
      "volatile_market": {
          "name": "Volatile Market Conditions",
          "description": "High volatility, rapid price changes",
          "start_date": date(2017, 3, 24),
          "end_date": date(2017, 3, 25),
          "market_condition": "volatile",
          "symbols": ["TSLA", "NVDA", "AMD", "NFLX"]
      },
      "trending_up": {
          "name": "Bull Market Trend",
          "description": "Consistent upward price movement",
          "start_date": date(2023, 1, 1),
          "end_date": date(2023, 1, 31),
          "market_condition": "trending",
          "symbols": ["AAPL", "MSFT", "GOOGL", "AMZN"]
      }
  }
  ```

#### 3.6.2 Create Scenario Loader
- [ ] **Implement scenario creation**:
  ```python
  async def create_predefined_scenarios():
      """Create predefined test scenarios in database."""
      db = SessionLocal()
      try:
          for scenario_key, scenario_data in PREDEFINED_SCENARIOS.items():
              scenario = TestScenario(**scenario_data)
              db.add(scenario)
              db.commit()
      finally:
          db.close()
  ```

### 3.7 Testing and Validation

#### 3.7.1 Create Migration Tests (`tests/integration/test_data_migration.py`)
- [ ] **Test data migration**:
  ```python
  class TestDataMigration:
      async def test_csv_to_database_migration(self):
          """Test migration from CSV to database."""
          # Load original CSV data
          # Run migration script
          # Verify data integrity
          pass
          
      async def test_expanded_dataset_generation(self):
          """Test generation of expanded test dataset."""
          # Generate expanded data
          # Verify completeness and consistency
          pass
  ```

#### 3.7.2 Create Adapter Tests (`tests/unit/test_database_adapter.py`)
- [ ] **Test database adapter**:
  ```python
  class TestDatabaseAdapter:
      async def test_stock_quote_retrieval(self):
          """Test stock quote retrieval from database."""
          pass
          
      async def test_scenario_switching(self):
          """Test switching between scenarios."""
          pass
          
      async def test_date_range_queries(self):
          """Test date range query functionality."""
          pass
  ```

### 3.8 Performance Optimization

#### 3.8.1 Add Database Indexes
- [ ] **Create additional indexes** for common queries:
  ```sql
  CREATE INDEX CONCURRENTLY idx_test_stock_symbol_scenario_date 
  ON test_stock_quotes(symbol, scenario, quote_date);
  
  CREATE INDEX CONCURRENTLY idx_test_option_underlying_scenario_date 
  ON test_option_quotes(underlying, scenario, quote_date);
  ```

#### 3.8.2 Implement Query Optimization
- [ ] **Add query optimization** to adapter:
  ```python
  async def batch_get_quotes(self, symbols: List[str], quote_date: date) -> Dict[str, StockQuote]:
      """Efficiently retrieve multiple quotes in single query."""
      db = SessionLocal()
      try:
          records = db.query(TestStockQuote).filter(
              TestStockQuote.symbol.in_(symbols),
              TestStockQuote.quote_date == quote_date,
              TestStockQuote.scenario == self.scenario
          ).all()
          
          return {record.symbol: self._convert_to_stock_quote(record) for record in records}
      finally:
          db.close()
  ```

### 3.9 Documentation and Configuration

#### 3.9.1 Update Configuration (`app/core/config.py`)
- [ ] **Add test scenario configuration**:
  ```python
  TEST_SCENARIO: str = Field(
      default="default",
      description="Default test scenario to use"
  )
  
  TEST_DATE: str = Field(
      default="2017-03-24",
      description="Default test date for backtesting"
  )
  ```

#### 3.9.2 Update Documentation
- [ ] **Update CLAUDE.md** with test data information:
  - Document available test scenarios
  - Explain how to switch scenarios
  - Document backtesting capabilities
  - Add troubleshooting section

### 3.10 Validation Steps

#### 3.10.1 Migration Validation
- [ ] **Run migration script**: Execute `python scripts/migrate_test_data.py`
- [ ] **Verify data integrity**: Check that all CSV data was migrated correctly
- [ ] **Test expanded dataset**: Verify generated data looks realistic
- [ ] **Validate scenarios**: Ensure all predefined scenarios work

#### 3.10.2 Performance Validation
- [ ] **Test query performance**: Ensure queries complete in < 50ms
- [ ] **Test memory usage**: Monitor memory usage with large datasets
- [ ] **Test concurrent access**: Verify multiple users can access test data
- [ ] **Validate caching**: Ensure cache improves performance

## Phase 4: Complete Model/Schema Separation

### 4.1 Analyze Current Architecture Status

#### 4.1.1 Verify Current Separation Quality
- [ ] **Review backwards compatibility layer** (`app/models/trading.py`):
  - Verify all schema re-exports are working correctly
  - Check that no duplicate definitions exist
  - Ensure clean import structure

- [ ] **Audit schema organization** (`app/schemas/`):
  - Verify all schemas are properly organized by domain
  - Check for any missing schema definitions
  - Ensure consistent naming conventions

- [ ] **Review database model separation** (`app/models/database/`):
  - Verify clean separation from API schemas
  - Check for proper relationship definitions
  - Ensure no schema mixing in database operations

#### 4.1.2 Identify Field Mapping Issues
- [ ] **Account schema vs database fields**:
  - Schema: `['id', 'cash_balance', 'positions', 'name', 'owner']`
  - Database: `['id', 'owner', 'cash_balance', 'created_at']`
  - **Issues to resolve**: Schema has `positions` (relationship) and `name` (not in DB)

- [ ] **Order schema vs database fields**:
  - Schema: `['id', 'symbol', 'order_type', 'quantity', 'price', 'condition', 'status', 'created_at', 'filled_at', 'legs', 'net_price']`
  - Database: `['id', 'account_id', 'symbol', 'order_type', 'quantity', 'price', 'status', 'created_at', 'filled_at']`
  - **Issues to resolve**: Schema missing `account_id`, has extra `condition`, `legs`, `net_price`

- [ ] **Position schema vs database fields**:
  - Schema: `['symbol', 'quantity', 'avg_price', 'current_price', 'unrealized_pnl', 'realized_pnl', 'asset', 'option_type', 'strike', 'expiration_date', 'underlying_symbol', 'delta', 'gamma', 'theta', 'vega', 'rho', 'iv']`
  - Database: `['id', 'account_id', 'symbol', 'quantity', 'avg_price']`
  - **Issues to resolve**: Schema missing `id`, `account_id`; has many calculated/derived fields

### 4.2 Create Schema-Database Conversion Utilities

#### 4.2.1 Create Converter Classes (`app/utils/schema_converters.py`)
- [ ] **Create base converter class**:
  ```python
  from abc import ABC, abstractmethod
  from typing import TypeVar, Generic, Any
  
  T = TypeVar('T')
  U = TypeVar('U')
  
  class SchemaConverter(Generic[T, U], ABC):
      @abstractmethod
      def to_schema(self, db_model: T) -> U:
          """Convert database model to schema."""
          pass
      
      @abstractmethod
      def to_database(self, schema: U) -> T:
          """Convert schema to database model."""
          pass
  ```

#### 4.2.2 Create Account Converter
- [ ] **Implement AccountConverter**:
  ```python
  from app.models.database.trading import DBAccount
  from app.schemas.accounts import Account
  
  class AccountConverter(SchemaConverter[DBAccount, Account]):
      def to_schema(self, db_account: DBAccount) -> Account:
          """Convert DBAccount to Account schema."""
          return Account(
              id=db_account.id,
              owner=db_account.owner,
              cash_balance=db_account.cash_balance,
              name=db_account.owner,  # Use owner as name for now
              positions=[]  # Will be populated separately
          )
      
      def to_database(self, account: Account) -> DBAccount:
          """Convert Account schema to DBAccount."""
          return DBAccount(
              id=account.id,
              owner=account.owner,
              cash_balance=account.cash_balance
          )
  ```

#### 4.2.3 Create Order Converter
- [ ] **Implement OrderConverter**:
  ```python
  from app.models.database.trading import DBOrder
  from app.schemas.orders import Order
  
  class OrderConverter(SchemaConverter[DBOrder, Order]):
      def to_schema(self, db_order: DBOrder) -> Order:
          """Convert DBOrder to Order schema."""
          return Order(
              id=db_order.id,
              symbol=db_order.symbol,
              order_type=db_order.order_type,
              quantity=db_order.quantity,
              price=db_order.price,
              status=db_order.status,
              created_at=db_order.created_at,
              filled_at=db_order.filled_at,
              # These fields are calculated/derived:
              condition=None,  # Not stored in DB
              legs=[],  # Will be populated for multi-leg orders
              net_price=db_order.price  # Same as price for simple orders
          )
      
      def to_database(self, order: Order, account_id: str) -> DBOrder:
          """Convert Order schema to DBOrder."""
          return DBOrder(
              id=order.id,
              account_id=account_id,  # Required field not in schema
              symbol=order.symbol,
              order_type=order.order_type,
              quantity=order.quantity,
              price=order.price,
              status=order.status,
              created_at=order.created_at,
              filled_at=order.filled_at
          )
  ```

#### 4.2.4 Create Position Converter
- [ ] **Implement PositionConverter**:
  ```python
  from app.models.database.trading import DBPosition
  from app.schemas.positions import Position
  
  class PositionConverter(SchemaConverter[DBPosition, Position]):
      def to_schema(self, db_position: DBPosition, current_price: float = None) -> Position:
          """Convert DBPosition to Position schema with calculated fields."""
          current_price = current_price or db_position.current_price or db_position.avg_price
          unrealized_pnl = (current_price - db_position.avg_price) * db_position.quantity
          
          return Position(
              symbol=db_position.symbol,
              quantity=db_position.quantity,
              avg_price=db_position.avg_price,
              current_price=current_price,
              unrealized_pnl=unrealized_pnl,
              realized_pnl=0.0,  # Would need to calculate from trades
              # Options fields (if applicable):
              asset=None,  # Would need to determine from symbol
              option_type=None,
              strike=None,
              expiration_date=None,
              underlying_symbol=None,
              # Greeks would be calculated separately
              delta=None, gamma=None, theta=None, vega=None, rho=None, iv=None
          )
      
      def to_database(self, position: Position, account_id: str) -> DBPosition:
          """Convert Position schema to DBPosition."""
          return DBPosition(
              account_id=account_id,
              symbol=position.symbol,
              quantity=position.quantity,
              avg_price=position.avg_price,
              current_price=position.current_price,
              unrealized_pnl=position.unrealized_pnl
          )
  ```

### 4.3 Enhance Schema Validation and Consistency

#### 4.3.1 Add Schema Validation Rules (`app/schemas/validation.py`)
- [ ] **Create validation utilities**:
  ```python
  from pydantic import validator
  from typing import Optional
  
  class SchemaValidationMixin:
      @validator('quantity')
      def validate_quantity(cls, v):
          if v == 0:
              raise ValueError('Quantity cannot be zero')
          return v
      
      @validator('price')
      def validate_price(cls, v):
          if v is not None and v <= 0:
              raise ValueError('Price must be positive')
          return v
  ```

#### 4.3.2 Update Existing Schemas with Validation
- [ ] **Add validation to Order schema** (`app/schemas/orders.py`):
  ```python
  class Order(BaseModel, SchemaValidationMixin):
      # ... existing fields ...
      
      @validator('order_type')
      def validate_order_type(cls, v):
          valid_types = ['market', 'limit', 'stop', 'stop_limit']
          if v not in valid_types:
              raise ValueError(f'Invalid order type: {v}')
          return v
      
      @validator('status')
      def validate_status(cls, v):
          valid_statuses = ['pending', 'filled', 'cancelled', 'rejected']
          if v not in valid_statuses:
              raise ValueError(f'Invalid status: {v}')
          return v
  ```

#### 4.3.3 Add Cross-Schema Validation
- [ ] **Create cross-schema validators** (`app/schemas/validation.py`):
  ```python
  def validate_order_against_account(order: Order, account: Account) -> bool:
      """Validate order is compatible with account."""
      # Check account has sufficient balance
      if order.order_type == 'market' and order.quantity * order.price > account.cash_balance:
          return False
      return True
  
  def validate_position_consistency(position: Position) -> bool:
      """Validate position data consistency."""
      # Check unrealized P&L calculation
      expected_pnl = (position.current_price - position.avg_price) * position.quantity
      return abs(position.unrealized_pnl - expected_pnl) < 0.01
  ```

### 4.4 Migrate from Backwards Compatibility Imports

#### 4.4.1 Create Migration Script (`scripts/migrate_imports.py`)
- [ ] **Create import migration script**:
  ```python
  import os
  import re
  from typing import Dict, List
  
  class ImportMigrator:
      def __init__(self):
          self.migration_map = {
              'from app.models.trading import Order': 'from app.schemas.orders import Order',
              'from app.models.trading import Position': 'from app.schemas.positions import Position',
              'from app.models.trading import Portfolio': 'from app.schemas.positions import Portfolio',
              'from app.models.trading import StockQuote': 'from app.schemas.trading import StockQuote',
              'from app.models.trading import OrderLeg': 'from app.schemas.orders import OrderLeg',
              'from app.models.trading import MultiLegOrder': 'from app.schemas.orders import MultiLegOrder',
          }
      
      def migrate_file(self, file_path: str) -> bool:
          """Migrate imports in a single file."""
          with open(file_path, 'r') as f:
              content = f.read()
          
          original_content = content
          for old_import, new_import in self.migration_map.items():
              content = content.replace(old_import, new_import)
          
          if content != original_content:
              with open(file_path, 'w') as f:
                  f.write(content)
              return True
          return False
  ```

#### 4.4.2 Update Specific Files
- [ ] **Update TradingService** (`app/services/trading_service.py` line 13):
  ```python
  # Replace:
  from app.models.trading import Order, Position, Portfolio, StockQuote
  
  # With:
  from app.schemas.orders import Order
  from app.schemas.positions import Position, Portfolio
  from app.schemas.trading import StockQuote
  ```

- [ ] **Update API endpoints** (`app/api/v1/endpoints/trading.py` line 5):
  ```python
  # Replace:
  from app.models.trading import Order, Position, Portfolio
  
  # With:
  from app.schemas.orders import Order
  from app.schemas.positions import Position, Portfolio
  ```

- [ ] **Update test files** (`tests/unit/test_trading_service.py` line 4):
  ```python
  # Replace:
  from app.models.trading import Order, Position, StockQuote
  
  # With:
  from app.schemas.orders import Order
  from app.schemas.positions import Position
  from app.schemas.trading import StockQuote
  ```

### 4.5 Add Advanced Type Safety Features

#### 4.5.1 Create Type Checking Utilities (`app/utils/type_checking.py`)
- [ ] **Add runtime type checking**:
  ```python
  from typing import TypeVar, Type, get_type_hints
  from pydantic import BaseModel
  
  T = TypeVar('T', bound=BaseModel)
  
  def validate_schema_type(obj: any, expected_type: Type[T]) -> T:
      """Validate object matches expected schema type."""
      if not isinstance(obj, expected_type):
          raise TypeError(f"Expected {expected_type.__name__}, got {type(obj).__name__}")
      return obj
  
  def get_schema_fields(schema_class: Type[BaseModel]) -> List[str]:
      """Get list of fields in a schema."""
      return list(get_type_hints(schema_class).keys())
  ```

#### 4.5.2 Add Generic Repository Pattern
- [ ] **Create generic repository** (`app/repositories/base.py`):
  ```python
  from typing import TypeVar, Generic, List, Optional
  from abc import ABC, abstractmethod
  from pydantic import BaseModel
  
  T = TypeVar('T', bound=BaseModel)
  U = TypeVar('U')  # Database model type
  
  class Repository(Generic[T, U], ABC):
      @abstractmethod
      async def get_by_id(self, id: str) -> Optional[T]:
          pass
      
      @abstractmethod
      async def get_all(self) -> List[T]:
          pass
      
      @abstractmethod
      async def create(self, item: T) -> T:
          pass
      
      @abstractmethod
      async def update(self, item: T) -> T:
          pass
      
      @abstractmethod
      async def delete(self, id: str) -> bool:
          pass
  ```

### 4.6 Create Documentation and Style Guide

#### 4.6.1 Create Schema Documentation (`docs/schemas.md`)
- [ ] **Document schema organization**:
  ```markdown
  # Schema Organization Guide
  
  ## Directory Structure
  - `/app/schemas/orders.py` - Order-related schemas
  - `/app/schemas/positions.py` - Position and portfolio schemas
  - `/app/schemas/accounts.py` - Account schemas
  - `/app/schemas/trading.py` - Trading data schemas (quotes, etc.)
  
  ## Usage Guidelines
  - Use schemas for API input/output
  - Use database models for persistence
  - Use converters for transformation
  
  ## Field Mapping
  - Schema fields may be calculated/derived
  - Database fields are stored values only
  - Use converters to bridge the gap
  ```

#### 4.6.2 Create Import Style Guide
- [ ] **Document import conventions**:
  ```python
  # Good - Direct schema imports
  from app.schemas.orders import Order, OrderLeg
  from app.schemas.positions import Position, Portfolio
  
  # Avoid - Backwards compatibility imports (deprecated)
  from app.models.trading import Order, Position
  
  # Good - Database model imports
  from app.models.database.trading import DBOrder, DBPosition
  
  # Good - Converter imports
  from app.utils.schema_converters import OrderConverter, PositionConverter
  ```

### 4.7 Testing and Validation

#### 4.7.1 Create Converter Tests (`tests/unit/test_schema_converters.py`)
- [ ] **Test schema-database conversion**:
  ```python
  class TestSchemaConverters:
      def test_account_converter_to_schema(self):
          """Test DBAccount to Account schema conversion."""
          db_account = DBAccount(id="123", owner="test", cash_balance=1000.0)
          converter = AccountConverter()
          schema = converter.to_schema(db_account)
          
          assert schema.id == "123"
          assert schema.owner == "test"
          assert schema.cash_balance == 1000.0
          assert schema.name == "test"
      
      def test_order_converter_roundtrip(self):
          """Test Order schema to DB and back."""
          # Test bidirectional conversion
          pass
  ```

#### 4.7.2 Create Validation Tests (`tests/unit/test_schema_validation.py`)
- [ ] **Test schema validation rules**:
  ```python
  class TestSchemaValidation:
      def test_order_validation(self):
          """Test Order schema validation."""
          # Test valid order
          order = Order(
              symbol="AAPL",
              order_type="market",
              quantity=100,
              price=150.0,
              status="pending"
          )
          assert order.quantity == 100
          
          # Test invalid order type
          with pytest.raises(ValueError):
              Order(
                  symbol="AAPL",
                  order_type="invalid_type",
                  quantity=100
              )
  ```

### 4.8 Performance Optimization

#### 4.8.1 Add Caching for Converters
- [ ] **Add converter caching** (`app/utils/schema_converters.py`):
  ```python
  from functools import lru_cache
  
  class CachedConverter:
      @lru_cache(maxsize=1000)
      def cached_to_schema(self, db_model_id: str, db_model_data: tuple) -> Any:
          """Cached version of to_schema conversion."""
          # Reconstruct model from tuple and convert
          pass
  ```

#### 4.8.2 Optimize Bulk Conversions
- [ ] **Add bulk conversion methods**:
  ```python
  class BulkConverter:
      def bulk_to_schema(self, db_models: List[Any]) -> List[Any]:
          """Convert multiple DB models to schemas efficiently."""
          return [self.to_schema(model) for model in db_models]
      
      def bulk_to_database(self, schemas: List[Any]) -> List[Any]:
          """Convert multiple schemas to DB models efficiently."""
          return [self.to_database(schema) for schema in schemas]
  ```

### 4.9 Final Integration and Cleanup

#### 4.9.1 Remove Backwards Compatibility Layer
- [ ] **Update app/models/trading.py**:
  ```python
  # Replace entire file with:
  """
  DEPRECATED: This module is deprecated.
  
  Use direct imports from app.schemas.* instead:
  - from app.schemas.orders import Order, OrderLeg, MultiLegOrder
  - from app.schemas.positions import Position, Portfolio
  - from app.schemas.accounts import Account
  - from app.schemas.trading import StockQuote
  """
  
  import warnings
  warnings.warn(
      "app.models.trading is deprecated. Use app.schemas.* instead.",
      DeprecationWarning,
      stacklevel=2
  )
  ```

#### 4.9.2 Update Service Layer to Use Converters
- [ ] **Update TradingService** to use converters:
  ```python
  from app.utils.schema_converters import OrderConverter, PositionConverter, AccountConverter
  
  class TradingService:
      def __init__(self):
          self.order_converter = OrderConverter()
          self.position_converter = PositionConverter()
          self.account_converter = AccountConverter()
      
      async def get_order(self, order_id: str) -> Optional[Order]:
          db_order = await self._get_db_order(order_id)
          if db_order:
              return self.order_converter.to_schema(db_order)
          return None
  ```

### 4.10 Validation and Documentation Updates

#### 4.10.1 Final Validation Steps
- [ ] **Run comprehensive type checking**: `python -m mypy app/`
- [ ] **Test all conversions**: Run converter test suite
- [ ] **Validate API responses**: Ensure all API endpoints return correct schemas
- [ ] **Test backwards compatibility**: Verify deprecated imports still work with warnings

#### 4.10.2 Documentation Updates
- [ ] **Update CLAUDE.md**:
  - Document new converter utilities
  - Explain schema vs database model usage
  - Add migration guide for developers
  - Document validation rules

- [ ] **Update API documentation**:
  - Ensure all endpoints document correct schema types
  - Add examples of schema usage
  - Document validation error responses

## Phase 5: Comprehensive Testing and Monitoring

### 5.1 End-to-End Testing Framework

#### 5.1.1 Create E2E Test Infrastructure (`tests/e2e/conftest.py`)
- [ ] **Set up test database isolation**:
  ```python
  import pytest
  import asyncio
  from sqlalchemy import create_engine
  from sqlalchemy.orm import sessionmaker
  from app.models.database.trading import Base
  from app.storage.database import get_db
  
  @pytest.fixture(scope="session")
  def event_loop():
      """Create an instance of the default event loop for the test session."""
      loop = asyncio.get_event_loop_policy().new_event_loop()
      yield loop
      loop.close()
  
  @pytest.fixture(scope="function")
  async def test_db():
      """Create a test database for each test."""
      engine = create_engine("sqlite:///test.db")
      Base.metadata.create_all(bind=engine)
      TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
      
      def override_get_db():
          db = TestingSessionLocal()
          try:
              yield db
          finally:
              db.close()
      
      # Override the database dependency
      app.dependency_overrides[get_db] = override_get_db
      yield
      Base.metadata.drop_all(bind=engine)
  ```

#### 5.1.2 Create Complete Order Flow Tests (`tests/e2e/test_order_flow.py`)
- [ ] **Test complete market order flow**:
  ```python
  class TestOrderFlow:
      async def test_market_order_complete_flow(self, test_db, test_client):
          """Test complete market order from creation to execution."""
          # 1. Create account with initial balance
          account_data = {
              "owner": "test_user",
              "cash_balance": 10000.0
          }
          account_response = await test_client.post("/api/v1/accounts", json=account_data)
          account_id = account_response.json()["id"]
          
          # 2. Create market order
          order_data = {
              "symbol": "AAPL",
              "order_type": "market",
              "quantity": 100,
              "price": 150.0
          }
          order_response = await test_client.post(f"/api/v1/accounts/{account_id}/orders", json=order_data)
          order_id = order_response.json()["id"]
          
          # 3. Verify order in database
          order_check = await test_client.get(f"/api/v1/orders/{order_id}")
          assert order_check.json()["status"] == "pending"
          
          # 4. Simulate order execution
          execution_data = {"status": "filled", "filled_price": 149.50}
          await test_client.patch(f"/api/v1/orders/{order_id}", json=execution_data)
          
          # 5. Verify position created
          positions = await test_client.get(f"/api/v1/accounts/{account_id}/positions")
          assert len(positions.json()) == 1
          assert positions.json()[0]["symbol"] == "AAPL"
          assert positions.json()[0]["quantity"] == 100
          
          # 6. Verify account balance updated
          account_check = await test_client.get(f"/api/v1/accounts/{account_id}")
          expected_balance = 10000.0 - (100 * 149.50)
          assert abs(account_check.json()["cash_balance"] - expected_balance) < 0.01
  ```

#### 5.1.3 Test Options Order Flow
- [ ] **Test multi-leg options order**:
  ```python
  async def test_options_spread_order_flow(self, test_db, test_client):
      """Test complete options spread order flow."""
      # 1. Create account
      account_data = {"owner": "options_trader", "cash_balance": 50000.0}
      account_response = await test_client.post("/api/v1/accounts", json=account_data)
      account_id = account_response.json()["id"]
      
      # 2. Create bull call spread
      spread_data = {
          "strategy_type": "bull_call_spread",
          "underlying": "AAPL",
          "legs": [
              {
                  "symbol": "AAPL240119C00150000",
                  "action": "buy",
                  "quantity": 1,
                  "price": 5.50
              },
              {
                  "symbol": "AAPL240119C00160000",
                  "action": "sell",
                  "quantity": 1,
                  "price": 2.75
              }
          ]
      }
      
      spread_response = await test_client.post(f"/api/v1/accounts/{account_id}/orders/multi-leg", json=spread_data)
      order_id = spread_response.json()["id"]
      
      # 3. Verify both legs created
      order_check = await test_client.get(f"/api/v1/orders/{order_id}")
      assert len(order_check.json()["legs"]) == 2
      
      # 4. Execute spread
      execution_data = {"status": "filled"}
      await test_client.patch(f"/api/v1/orders/{order_id}", json=execution_data)
      
      # 5. Verify positions
      positions = await test_client.get(f"/api/v1/accounts/{account_id}/positions")
      assert len(positions.json()) == 2
      
      # 6. Verify net debit applied to account
      account_check = await test_client.get(f"/api/v1/accounts/{account_id}")
      net_debit = (5.50 - 2.75) * 100  # $275 per spread
      expected_balance = 50000.0 - net_debit
      assert abs(account_check.json()["cash_balance"] - expected_balance) < 0.01
  ```

### 5.2 Database State Testing

#### 5.2.1 Create Database Consistency Tests (`tests/integration/test_database_state.py`)
- [ ] **Test portfolio calculations from database only**:
  ```python
  class TestDatabaseState:
      async def test_portfolio_calculation_from_db(self, test_db):
          """Test portfolio calculations using only database state."""
          # Create test data directly in database
          db = TestingSessionLocal()
          
          # Create account
          account = DBAccount(owner="test", cash_balance=10000.0)
          db.add(account)
          db.commit()
          
          # Create positions
          positions = [
              DBPosition(
                  account_id=account.id,
                  symbol="AAPL",
                  quantity=100,
                  avg_price=150.0,
                  current_price=155.0,
                  unrealized_pnl=500.0
              ),
              DBPosition(
                  account_id=account.id,
                  symbol="GOOGL",
                  quantity=10,
                  avg_price=2800.0,
                  current_price=2750.0,
                  unrealized_pnl=-500.0
              )
          ]
          for pos in positions:
              db.add(pos)
          db.commit()
          
          # Test portfolio calculation
          trading_service = TradingService()
          portfolio = await trading_service.get_portfolio(account.id)
          
          # Verify calculations
          assert portfolio.cash_balance == 10000.0
          assert len(portfolio.positions) == 2
          assert portfolio.total_value == 10000.0 + 155.0*100 + 2750.0*10
          assert portfolio.unrealized_pnl == 0.0  # Net zero
          
          db.close()
  ```

#### 5.2.2 Test Data Persistence Between Requests
- [ ] **Test data survives service restarts**:
  ```python
  async def test_data_persistence_across_restarts(self, test_db):
      """Test that data persists between service restarts."""
      # Create initial data
      service1 = TradingService()
      order = await service1.create_order(
          account_id="test_account",
          symbol="AAPL",
          order_type="market",
          quantity=100,
          price=150.0
      )
      order_id = order.id
      
      # Simulate service restart (new instance)
      service2 = TradingService()
      retrieved_order = await service2.get_order(order_id)
      
      # Verify data persisted
      assert retrieved_order is not None
      assert retrieved_order.id == order_id
      assert retrieved_order.symbol == "AAPL"
      assert retrieved_order.quantity == 100
  ```

### 5.3 Quote Adapter Testing

#### 5.3.1 Create Adapter Switching Tests (`tests/integration/test_quote_adapters.py`)
- [ ] **Test seamless adapter switching**:
  ```python
  class TestQuoteAdapterSwitching:
      async def test_switch_between_test_and_live_data(self):
          """Test switching between test and live quote adapters."""
          # Start with test adapter
          trading_service = TradingService()
          await trading_service.switch_quote_adapter("test")
          
          # Get test quote
          test_quote = await trading_service.get_quote("AAPL")
          assert test_quote is not None
          assert test_quote.symbol == "AAPL"
          
          # Switch to Robinhood adapter
          await trading_service.switch_quote_adapter("robinhood")
          
          # Get live quote (mocked in tests)
          live_quote = await trading_service.get_quote("AAPL")
          assert live_quote is not None
          assert live_quote.symbol == "AAPL"
          
          # Verify different data sources
          assert test_quote.price != live_quote.price  # Different data sources
  ```

#### 5.3.2 Test Adapter Failover
- [ ] **Test adapter failover scenarios**:
  ```python
  async def test_adapter_failover_on_failure(self):
      """Test failover to backup adapter when primary fails."""
      # Mock Robinhood adapter failure
      with patch('app.adapters.robinhood.RobinhoodAdapter.get_quote') as mock_robinhood:
          mock_robinhood.side_effect = Exception("API Error")
          
          # Configure fallback chain
          trading_service = TradingService()
          await trading_service.configure_adapter_fallback(["robinhood", "test"])
          
          # Should fallback to test adapter
          quote = await trading_service.get_quote("AAPL")
          assert quote is not None
          assert quote.symbol == "AAPL"
  ```

### 5.4 Performance Testing and Benchmarking

#### 5.4.1 Create Performance Benchmarks (`tests/performance/test_benchmarks.py`)
- [ ] **Database query performance benchmarks**:
  ```python
  import time
  import pytest
  from statistics import mean, median
  
  class TestPerformanceBenchmarks:
      async def test_order_creation_performance(self, test_db):
          """Benchmark order creation performance."""
          trading_service = TradingService()
          
          # Create test account
          account = await trading_service.create_account("perf_test", 100000.0)
          
          # Benchmark order creation
          times = []
          for i in range(100):
              start_time = time.time()
              await trading_service.create_order(
                  account_id=account.id,
                  symbol=f"TEST{i:03d}",
                  order_type="market",
                  quantity=100,
                  price=100.0
              )
              end_time = time.time()
              times.append(end_time - start_time)
          
          # Performance assertions
          avg_time = mean(times)
          median_time = median(times)
          max_time = max(times)
          
          assert avg_time < 0.1, f"Average order creation time {avg_time:.3f}s exceeds 100ms"
          assert median_time < 0.05, f"Median order creation time {median_time:.3f}s exceeds 50ms"
          assert max_time < 0.5, f"Max order creation time {max_time:.3f}s exceeds 500ms"
  ```

#### 5.4.2 Portfolio Calculation Performance
- [ ] **Benchmark portfolio calculations**:
  ```python
  async def test_portfolio_calculation_performance(self, test_db):
      """Benchmark portfolio calculation with many positions."""
      trading_service = TradingService()
      
      # Create account with many positions
      account = await trading_service.create_account("portfolio_test", 1000000.0)
      
      # Create 1000 positions
      for i in range(1000):
          await trading_service.create_position(
              account_id=account.id,
              symbol=f"STOCK{i:04d}",
              quantity=100,
              avg_price=100.0 + i * 0.1,
              current_price=100.0 + i * 0.1 + 5.0
          )
      
      # Benchmark portfolio calculation
      times = []
      for _ in range(10):
          start_time = time.time()
          portfolio = await trading_service.get_portfolio(account.id)
          end_time = time.time()
          times.append(end_time - start_time)
      
      avg_time = mean(times)
      assert avg_time < 0.5, f"Portfolio calculation time {avg_time:.3f}s exceeds 500ms"
      assert len(portfolio.positions) == 1000
  ```

### 5.5 Database Query Monitoring

#### 5.5.1 Create Query Logging System (`app/monitoring/query_logger.py`)
- [ ] **Implement query performance monitoring**:
  ```python
  import time
  import logging
  from sqlalchemy import event
  from sqlalchemy.engine import Engine
  
  # Set up query logging
  logging.basicConfig()
  query_logger = logging.getLogger("sqlalchemy.engine")
  query_logger.setLevel(logging.INFO)
  
  @event.listens_for(Engine, "before_cursor_execute")
  def before_cursor_execute(conn, cursor, statement, parameters, context, executemany):
      conn.info.setdefault('query_start_time', []).append(time.time())
      query_logger.debug("Start Query: %s", statement)
  
  @event.listens_for(Engine, "after_cursor_execute")
  def after_cursor_execute(conn, cursor, statement, parameters, context, executemany):
      total = time.time() - conn.info['query_start_time'].pop(-1)
      if total > 0.1:  # Log slow queries (> 100ms)
          query_logger.warning(
              "Slow Query: %s\nDuration: %.3fs\nParameters: %s",
              statement, total, parameters
          )
      else:
          query_logger.debug("Query completed in %.3fs", total)
  ```

#### 5.5.2 Add Query Performance Metrics
- [ ] **Create query metrics collection**:
  ```python
  from dataclasses import dataclass
  from typing import Dict, List
  from collections import defaultdict
  
  @dataclass
  class QueryMetrics:
      statement: str
      execution_count: int
      total_time: float
      avg_time: float
      max_time: float
      min_time: float
  
  class QueryMonitor:
      def __init__(self):
          self.metrics: Dict[str, List[float]] = defaultdict(list)
      
      def record_query(self, statement: str, execution_time: float):
          """Record query execution time."""
          self.metrics[statement].append(execution_time)
      
      def get_metrics(self) -> List[QueryMetrics]:
          """Get aggregated query metrics."""
          results = []
          for statement, times in self.metrics.items():
              results.append(QueryMetrics(
                  statement=statement,
                  execution_count=len(times),
                  total_time=sum(times),
                  avg_time=sum(times) / len(times),
                  max_time=max(times),
                  min_time=min(times)
              ))
          return sorted(results, key=lambda x: x.total_time, reverse=True)
  ```

### 5.6 API Rate Limit Monitoring

#### 5.6.1 Create Robinhood Rate Limit Tracker (`app/monitoring/rate_limits.py`)
- [ ] **Implement rate limit monitoring**:
  ```python
  import time
  from typing import Dict, Optional
  from dataclasses import dataclass
  
  @dataclass
  class RateLimitStatus:
      requests_made: int
      requests_limit: int
      reset_time: float
      remaining_requests: int
      
      @property
      def utilization_percent(self) -> float:
          return (self.requests_made / self.requests_limit) * 100
  
  class RateLimitMonitor:
      def __init__(self):
          self.rate_limits: Dict[str, RateLimitStatus] = {}
      
      def update_rate_limit(self, api_name: str, headers: Dict[str, str]):
          """Update rate limit status from API response headers."""
          if 'X-RateLimit-Limit' in headers:
              self.rate_limits[api_name] = RateLimitStatus(
                  requests_made=int(headers.get('X-RateLimit-Used', 0)),
                  requests_limit=int(headers['X-RateLimit-Limit']),
                  reset_time=float(headers.get('X-RateLimit-Reset', 0)),
                  remaining_requests=int(headers.get('X-RateLimit-Remaining', 0))
              )
      
      def get_rate_limit_status(self, api_name: str) -> Optional[RateLimitStatus]:
          """Get current rate limit status for an API."""
          return self.rate_limits.get(api_name)
      
      def is_rate_limited(self, api_name: str) -> bool:
          """Check if API is currently rate limited."""
          status = self.get_rate_limit_status(api_name)
          if not status:
              return False
          return status.remaining_requests <= 0 and time.time() < status.reset_time
  ```

#### 5.6.2 Integrate Rate Limit Monitoring
- [ ] **Add rate limit monitoring to RobinhoodAdapter**:
  ```python
  class RobinhoodAdapter:
      def __init__(self):
          self.rate_monitor = RateLimitMonitor()
          
      async def get_quote(self, symbol: str) -> Optional[StockQuote]:
          # Check rate limit before request
          if self.rate_monitor.is_rate_limited("robinhood"):
              raise RateLimitExceededException("Robinhood API rate limit exceeded")
          
          # Make API request
          response = await self._make_request(f"/quotes/{symbol}")
          
          # Update rate limit tracking
          self.rate_monitor.update_rate_limit("robinhood", response.headers)
          
          return self._parse_quote_response(response)
  ```

### 5.7 Health Check Endpoints

#### 5.7.1 Create Health Check System (`app/api/v1/endpoints/health.py`)
- [ ] **Create comprehensive health checks**:
  ```python
  from fastapi import APIRouter, HTTPException
  from typing import Dict, Any
  import time
  
  router = APIRouter()
  
  @router.get("/health")
  async def health_check() -> Dict[str, Any]:
      """Comprehensive health check endpoint."""
      health_status = {
          "status": "healthy",
          "timestamp": time.time(),
          "checks": {}
      }
      
      # Database health check
      try:
          db_start = time.time()
          db = get_db()
          db.execute("SELECT 1")
          db_time = time.time() - db_start
          health_status["checks"]["database"] = {
              "status": "healthy",
              "response_time": db_time
          }
      except Exception as e:
          health_status["checks"]["database"] = {
              "status": "unhealthy",
              "error": str(e)
          }
          health_status["status"] = "unhealthy"
      
      # Quote adapter health check
      try:
          quote_start = time.time()
          trading_service = TradingService()
          quote = await trading_service.get_quote("AAPL")
          quote_time = time.time() - quote_start
          health_status["checks"]["quote_adapter"] = {
              "status": "healthy" if quote else "degraded",
              "response_time": quote_time
          }
      except Exception as e:
          health_status["checks"]["quote_adapter"] = {
              "status": "unhealthy",
              "error": str(e)
          }
      
      # Set overall status
      if any(check["status"] == "unhealthy" for check in health_status["checks"].values()):
          health_status["status"] = "unhealthy"
      elif any(check["status"] == "degraded" for check in health_status["checks"].values()):
          health_status["status"] = "degraded"
      
      return health_status
  ```

#### 5.7.2 Create Detailed Service Health Checks
- [ ] **Add service-specific health endpoints**:
  ```python
  @router.get("/health/database")
  async def database_health():
      """Detailed database health check."""
      try:
          db = get_db()
          
          # Test basic connectivity
          db.execute("SELECT 1")
          
          # Test table access
          account_count = db.query(DBAccount).count()
          order_count = db.query(DBOrder).count()
          
          return {
              "status": "healthy",
              "details": {
                  "accounts": account_count,
                  "orders": order_count,
                  "connection_pool": {
                      "size": db.get_bind().pool.size(),
                      "checked_in": db.get_bind().pool.checkedin(),
                      "checked_out": db.get_bind().pool.checkedout()
                  }
              }
          }
      except Exception as e:
          return {
              "status": "unhealthy",
              "error": str(e)
          }
  
  @router.get("/health/quotes")
  async def quotes_health():
      """Detailed quote service health check."""
      try:
          trading_service = TradingService()
          
          # Test quote retrieval
          test_symbols = ["AAPL", "GOOGL", "MSFT"]
          quote_results = {}
          
          for symbol in test_symbols:
              start_time = time.time()
              quote = await trading_service.get_quote(symbol)
              response_time = time.time() - start_time
              
              quote_results[symbol] = {
                  "available": quote is not None,
                  "response_time": response_time,
                  "price": quote.price if quote else None
              }
          
          return {
              "status": "healthy",
              "adapter_type": trading_service.quote_adapter.__class__.__name__,
              "quotes": quote_results
          }
      except Exception as e:
          return {
              "status": "unhealthy",
              "error": str(e)
          }
  ```

### 5.8 Concurrent Trading Operation Tests

#### 5.8.1 Create Concurrency Tests (`tests/stress/test_concurrency.py`)
- [ ] **Test concurrent order creation**:
  ```python
  import asyncio
  import pytest
  from concurrent.futures import ThreadPoolExecutor
  
  class TestConcurrency:
      async def test_concurrent_order_creation(self, test_db):
          """Test multiple users creating orders simultaneously."""
          trading_service = TradingService()
          
          # Create multiple accounts
          accounts = []
          for i in range(10):
              account = await trading_service.create_account(f"user_{i}", 10000.0)
              accounts.append(account)
          
          # Create orders concurrently
          async def create_orders_for_account(account):
              orders = []
              for j in range(10):
                  order = await trading_service.create_order(
                      account_id=account.id,
                      symbol="AAPL",
                      order_type="market",
                      quantity=10,
                      price=150.0
                  )
                  orders.append(order)
              return orders
          
          # Execute concurrently
          tasks = [create_orders_for_account(account) for account in accounts]
          results = await asyncio.gather(*tasks)
          
          # Verify all orders created
          total_orders = sum(len(orders) for orders in results)
          assert total_orders == 100  # 10 accounts × 10 orders each
          
          # Verify database consistency
          all_orders = await trading_service.get_all_orders()
          assert len(all_orders) == 100
  ```

#### 5.8.2 Test Portfolio Calculation Concurrency
- [ ] **Test concurrent portfolio calculations**:
  ```python
  async def test_concurrent_portfolio_calculations(self, test_db):
      """Test multiple portfolio calculations running simultaneously."""
      trading_service = TradingService()
      
      # Create account with positions
      account = await trading_service.create_account("concurrent_test", 100000.0)
      
      # Create positions
      for i in range(100):
          await trading_service.create_position(
              account_id=account.id,
              symbol=f"STOCK{i:03d}",
              quantity=100,
              avg_price=100.0,
              current_price=105.0
          )
      
      # Run concurrent portfolio calculations
      async def calculate_portfolio():
          return await trading_service.get_portfolio(account.id)
      
      tasks = [calculate_portfolio() for _ in range(20)]
      portfolios = await asyncio.gather(*tasks)
      
      # Verify all calculations return consistent results
      for portfolio in portfolios:
          assert len(portfolio.positions) == 100
          assert portfolio.total_value == portfolios[0].total_value
          assert portfolio.unrealized_pnl == portfolios[0].unrealized_pnl
  ```

### 5.9 Stress Testing

#### 5.9.1 Create High-Volume Trading Tests (`tests/stress/test_volume.py`)
- [ ] **Test high-volume order processing**:
  ```python
  class TestHighVolumeTrading:
      async def test_high_volume_order_processing(self, test_db):
          """Test system under high order volume."""
          trading_service = TradingService()
          
          # Create account with large balance
          account = await trading_service.create_account("high_volume", 1000000.0)
          
          # Create 10,000 orders
          start_time = time.time()
          orders = []
          
          for i in range(10000):
              order = await trading_service.create_order(
                  account_id=account.id,
                  symbol="AAPL",
                  order_type="market",
                  quantity=1,
                  price=150.0 + (i % 100) * 0.01
              )
              orders.append(order)
              
              # Progress tracking
              if i % 1000 == 0:
                  elapsed = time.time() - start_time
                  rate = (i + 1) / elapsed
                  print(f"Created {i+1} orders in {elapsed:.1f}s (rate: {rate:.1f}/s)")
          
          total_time = time.time() - start_time
          rate = 10000 / total_time
          
          # Performance assertions
          assert rate > 100, f"Order creation rate {rate:.1f}/s is too low"
          assert len(orders) == 10000
          
          # Verify database consistency
          db_orders = await trading_service.get_orders(account.id)
          assert len(db_orders) == 10000
  ```

#### 5.9.2 Test Memory Usage Under Load
- [ ] **Test memory usage under sustained load**:
  ```python
  import psutil
  import os
  
  async def test_memory_usage_under_load(self, test_db):
      """Test memory usage during sustained operation."""
      process = psutil.Process(os.getpid())
      initial_memory = process.memory_info().rss / 1024 / 1024  # MB
      
      trading_service = TradingService()
      account = await trading_service.create_account("memory_test", 1000000.0)
      
      # Sustained operation
      for cycle in range(100):
          # Create orders
          orders = []
          for i in range(100):
              order = await trading_service.create_order(
                  account_id=account.id,
                  symbol="AAPL",
                  order_type="market",
                  quantity=10,
                  price=150.0
              )
              orders.append(order)
          
          # Execute orders
          for order in orders:
              await trading_service.execute_order(order.id, 149.50)
          
          # Check memory usage
          current_memory = process.memory_info().rss / 1024 / 1024  # MB
          memory_increase = current_memory - initial_memory
          
          # Memory should not grow indefinitely
          assert memory_increase < 500, f"Memory usage increased by {memory_increase:.1f}MB"
          
          if cycle % 10 == 0:
              print(f"Cycle {cycle}: Memory usage {current_memory:.1f}MB (+{memory_increase:.1f}MB)")
  ```

### 5.10 Test Documentation and Reporting

#### 5.10.1 Create Test Documentation (`tests/README.md`)
- [ ] **Document all test scenarios**:
  ```markdown
  # Test Suite Documentation
  
  ## Test Categories
  
  ### Unit Tests (`tests/unit/`)
  - Individual component testing
  - Schema validation
  - Business logic validation
  - Database model testing
  
  ### Integration Tests (`tests/integration/`)
  - Service integration testing
  - Database integration
  - Quote adapter integration
  - Multi-service workflows
  
  ### End-to-End Tests (`tests/e2e/`)
  - Complete user workflows
  - API endpoint testing
  - Cross-service communication
  - Real-world scenarios
  
  ### Performance Tests (`tests/performance/`)
  - Response time benchmarks
  - Throughput testing
  - Resource utilization
  - Scalability testing
  
  ### Stress Tests (`tests/stress/`)
  - High-volume scenarios
  - Concurrent operations
  - Memory usage validation
  - Error handling under load
  
  ## Running Tests
  
  ### All Tests
  ```bash
  pytest tests/
  ```
  
  ### By Category
  ```bash
  pytest tests/unit/          # Unit tests
  pytest tests/integration/   # Integration tests
  pytest tests/e2e/          # End-to-end tests
  pytest tests/performance/  # Performance tests
  pytest tests/stress/       # Stress tests
  ```
  
  ### With Coverage
  ```bash
  pytest --cov=app tests/
  ```
  
  ## Expected Test Outcomes
  
  ### Performance Targets
  - Order creation: < 100ms average
  - Portfolio calculation: < 500ms for 1000 positions
  - Quote retrieval: < 50ms average
  - Database queries: < 100ms for complex queries
  
  ### Stress Test Targets
  - Handle 10,000 orders without performance degradation
  - Support 100 concurrent users
  - Memory usage growth < 500MB during sustained operation
  - No data corruption under high load
  ```

#### 5.10.2 Create Test Reporting System (`tests/reporting/test_reporter.py`)
- [ ] **Create automated test reporting**:
  ```python
  import json
  import time
  from typing import Dict, Any, List
  from dataclasses import dataclass
  
  @dataclass
  class TestResult:
      test_name: str
      status: str  # "passed", "failed", "skipped"
      duration: float
      error_message: str = None
      
  class TestReporter:
      def __init__(self):
          self.results: List[TestResult] = []
          self.start_time = time.time()
      
      def add_result(self, result: TestResult):
          """Add a test result."""
          self.results.append(result)
      
      def generate_report(self) -> Dict[str, Any]:
          """Generate comprehensive test report."""
          end_time = time.time()
          total_duration = end_time - self.start_time
          
          passed = len([r for r in self.results if r.status == "passed"])
          failed = len([r for r in self.results if r.status == "failed"])
          skipped = len([r for r in self.results if r.status == "skipped"])
          
          return {
              "summary": {
                  "total_tests": len(self.results),
                  "passed": passed,
                  "failed": failed,
                  "skipped": skipped,
                  "success_rate": (passed / len(self.results)) * 100 if self.results else 0,
                  "total_duration": total_duration
              },
              "performance": {
                  "avg_test_duration": sum(r.duration for r in self.results) / len(self.results) if self.results else 0,
                  "slowest_tests": sorted(self.results, key=lambda r: r.duration, reverse=True)[:10]
              },
              "failures": [r for r in self.results if r.status == "failed"],
              "detailed_results": [
                  {
                      "name": r.test_name,
                      "status": r.status,
                      "duration": r.duration,
                      "error": r.error_message
                  }
                  for r in self.results
              ]
          }
      
      def save_report(self, filename: str):
          """Save report to file."""
          report = self.generate_report()
          with open(filename, 'w') as f:
              json.dump(report, f, indent=2)
  ```

### 5.11 Final Validation and Acceptance Testing

#### 5.11.1 Create Acceptance Test Suite (`tests/acceptance/test_acceptance.py`)
- [ ] **Create user acceptance tests**:
  ```python
  class TestUserAcceptance:
      async def test_paper_trading_workflow(self, test_db, test_client):
          """Test complete paper trading workflow from user perspective."""
          # 1. User creates account
          account_response = await test_client.post("/api/v1/accounts", json={
              "owner": "paper_trader",
              "cash_balance": 100000.0
          })
          assert account_response.status_code == 201
          account_id = account_response.json()["id"]
          
          # 2. User checks available quotes
          quote_response = await test_client.get("/api/v1/quotes/AAPL")
          assert quote_response.status_code == 200
          quote_data = quote_response.json()
          
          # 3. User places buy order
          order_response = await test_client.post(f"/api/v1/accounts/{account_id}/orders", json={
              "symbol": "AAPL",
              "order_type": "market",
              "quantity": 100,
              "price": quote_data["price"]
          })
          assert order_response.status_code == 201
          order_id = order_response.json()["id"]
          
          # 4. Order gets executed
          execution_response = await test_client.patch(f"/api/v1/orders/{order_id}", json={
              "status": "filled"
          })
          assert execution_response.status_code == 200
          
          # 5. User checks portfolio
          portfolio_response = await test_client.get(f"/api/v1/accounts/{account_id}/portfolio")
          assert portfolio_response.status_code == 200
          portfolio = portfolio_response.json()
          
          # 6. Verify position created
          assert len(portfolio["positions"]) == 1
          assert portfolio["positions"][0]["symbol"] == "AAPL"
          assert portfolio["positions"][0]["quantity"] == 100
          
          # 7. User places sell order
          sell_response = await test_client.post(f"/api/v1/accounts/{account_id}/orders", json={
              "symbol": "AAPL",
              "order_type": "market",
              "quantity": -100,  # Sell
              "price": quote_data["price"] + 5.0
          })
          assert sell_response.status_code == 201
          
          # 8. Verify complete workflow
          final_portfolio = await test_client.get(f"/api/v1/accounts/{account_id}/portfolio")
          # Should have realized profit
          assert final_portfolio.json()["realized_pnl"] > 0
  ```

#### 5.11.2 Final System Validation
- [ ] **Run comprehensive system validation**:
  ```bash
  # Run all test suites
  pytest tests/ --cov=app --cov-report=html --cov-report=term-missing
  
  # Run performance benchmarks
  pytest tests/performance/ -v --benchmark-only
  
  # Run stress tests
  pytest tests/stress/ -v --timeout=300
  
  # Run acceptance tests
  pytest tests/acceptance/ -v
  ```

- [ ] **Validate success criteria**:
  - All unit tests pass (100% pass rate)
  - Integration tests pass (100% pass rate)
  - Performance targets met (< 100ms order creation)
  - Stress tests pass (10,000 orders handled)
  - Memory usage stable (< 500MB growth)
  - No data corruption detected
  - Rate limiting works correctly
  - Health checks all green

## Phase 6: Remove All Deprecated Components

### 6.1 Identify Deprecated Components

#### 6.1.1 Audit Deprecated Modules (`scripts/audit_deprecated.py`)
- [ ] **Create deprecation audit script**:
  ```python
  import os
  import re
  from typing import List, Dict, Any
  
  class DeprecationAuditor:
      def __init__(self):
          self.deprecated_items = []
          self.deprecated_patterns = [
              r'# DEPRECATED',
              r'@deprecated',
              r'warnings\.warn.*deprecated',
              r'DEPRECATED.*This.*deprecated',
              r'# TODO.*remove.*deprecated'
          ]
      
      def scan_file(self, file_path: str) -> List[Dict[str, Any]]:
          """Scan file for deprecated items."""
          deprecated_items = []
          
          with open(file_path, 'r') as f:
              lines = f.readlines()
              
          for line_num, line in enumerate(lines, 1):
              for pattern in self.deprecated_patterns:
                  if re.search(pattern, line, re.IGNORECASE):
                      deprecated_items.append({
                          'file': file_path,
                          'line': line_num,
                          'content': line.strip(),
                          'type': 'deprecated_marker'
                      })
          
          return deprecated_items
  ```

#### 6.1.2 Find Backwards Compatibility Imports
- [ ] **Search for backwards compatibility imports**:
  ```bash
  # Find all imports from deprecated modules
  grep -r "from app.models.trading import" app/ --include="*.py"
  
  # Find deprecated API endpoints
  grep -r "deprecated=True" app/api/ --include="*.py"
  
  # Find deprecated MCP tools
  grep -r "DEPRECATED" app/mcp/ --include="*.py"
  ```

#### 6.1.3 Catalog Deprecated Items
- [ ] **Create comprehensive deprecation catalog**:
  - `app/models/trading.py` - Backwards compatibility layer
  - Any API endpoints marked with `deprecated=True`
  - MCP tools with `[DEPRECATED]` prefix
  - Old test data loading mechanisms
  - Legacy configuration options
  - Unused utility functions

### 6.2 Remove Deprecated API Endpoints

#### 6.2.1 Identify Deprecated Endpoints (`app/api/v1/endpoints/`)
- [ ] **Search for deprecated endpoints**:
  ```python
  # Find endpoints with deprecated=True
  grep -r "deprecated=True" app/api/v1/endpoints/
  
  # Common patterns for deprecated endpoints:
  # - Old quote endpoints that use mock data
  # - Legacy position calculation endpoints
  # - Deprecated account management endpoints
  ```

#### 6.2.2 Remove Deprecated Trading Endpoints
- [ ] **Remove deprecated endpoints** in `app/api/v1/endpoints/trading.py`:
  ```python
  # Remove any endpoints marked like:
  @router.get("/legacy/quotes/{symbol}", deprecated=True)
  async def get_legacy_quote(symbol: str):
      # Remove entire function
  
  @router.post("/legacy/orders", deprecated=True)
  async def create_legacy_order():
      # Remove entire function
  ```

#### 6.2.3 Remove Deprecated Portfolio Endpoints
- [ ] **Remove deprecated endpoints** in `app/api/v1/endpoints/portfolio.py`:
  ```python
  # Remove any endpoints marked like:
  @router.get("/legacy/portfolio/{account_id}", deprecated=True)
  async def get_legacy_portfolio():
      # Remove entire function
  ```

#### 6.2.4 Update API Router
- [ ] **Remove deprecated route inclusions** in `app/api/v1/api.py`:
  ```python
  # Remove any deprecated route inclusions
  # api_router.include_router(legacy_router, prefix="/legacy", deprecated=True)
  ```

### 6.3 Remove Deprecated MCP Tools

#### 6.3.1 Identify Deprecated MCP Tools (`app/mcp/tools.py`)
- [ ] **Search for deprecated MCP tools**:
  ```python
  # Find tools with [DEPRECATED] prefix in docstrings
  grep -A 10 -B 2 "DEPRECATED" app/mcp/tools.py
  
  # Find tools that use deprecated imports
  grep -n "from app.models.trading import" app/mcp/tools.py
  ```

#### 6.3.2 Remove Deprecated Trading Tools
- [ ] **Remove deprecated tools** from `app/mcp/tools.py`:
  ```python
  # Remove tools like:
  @server.tool()
  async def legacy_get_quote(symbol: str) -> str:
      """[DEPRECATED] Get stock quote - use get_stock_quote instead."""
      # Remove entire function
  
  @server.tool()
  async def legacy_create_order(symbol: str, quantity: int) -> str:
      """[DEPRECATED] Create order - use create_stock_order instead."""
      # Remove entire function
  ```

#### 6.3.3 Remove Deprecated Portfolio Tools
- [ ] **Remove deprecated portfolio tools**:
  ```python
  # Remove tools like:
  @server.tool()
  async def legacy_get_portfolio() -> str:
      """[DEPRECATED] Get portfolio - use get_trading_portfolio instead."""
      # Remove entire function
  ```

### 6.4 Remove Backwards Compatibility Layer

#### 6.4.1 Remove Models Trading Module
- [ ] **Delete backwards compatibility file** (`app/models/trading.py`):
  ```bash
  # Remove the entire file
  rm app/models/trading.py
  ```

#### 6.4.2 Update All Remaining Imports
- [ ] **Update any remaining imports** throughout codebase:
  ```python
  # Replace any remaining imports:
  # from app.models.trading import Order
  # With:
  # from app.schemas.orders import Order
  
  # Create script to do bulk replacement:
  find app/ -name "*.py" -exec sed -i 's/from app\.models\.trading import/from app.schemas.orders import Order; from app.schemas.positions import Position, Portfolio; from app.schemas.trading import StockQuote; # UPDATED_IMPORT/g' {} \;
  ```

#### 6.4.3 Fix Import Statements
- [ ] **Clean up import statements** after bulk replacement:
  ```python
  # Create script to fix multiple imports on one line
  # Split combined imports back into separate lines
  # Remove unused imports
  # Sort imports alphabetically
  ```

### 6.5 Remove Deprecated Test Data Systems

#### 6.5.1 Remove Old Test Data Loading
- [ ] **Remove deprecated test data mechanisms**:
  ```python
  # In app/adapters/test_data.py, remove:
  # - Old CSV file loading methods
  # - In-memory cache systems that are no longer used
  # - Legacy date selection mechanisms
  ```

#### 6.5.2 Remove Old Test Data Files
- [ ] **Remove deprecated test data files**:
  ```bash
  # Remove old CSV files if they're no longer used
  find app/adapters/test_data/ -name "*.csv" -type f
  find app/adapters/test_data/ -name "*.csv.gz" -type f
  
  # Only remove if data has been migrated to database
  # rm app/adapters/test_data/old_data.csv.gz
  ```

#### 6.5.3 Clean Up Test Data Adapter
- [ ] **Remove deprecated methods** from `TestDataAdapter`:
  ```python
  # Remove methods like:
  def _load_from_csv(self):
      # Remove if no longer used
      pass
  
  def _parse_legacy_format(self):
      # Remove if no longer used
      pass
  ```

### 6.6 Remove Deprecated Configuration Options

#### 6.6.1 Clean Up Configuration (`app/core/config.py`)
- [ ] **Remove deprecated configuration options**:
  ```python
  # Remove settings like:
  # LEGACY_QUOTE_ENABLED: bool = Field(default=False, deprecated=True)
  # USE_MOCK_DATA: bool = Field(default=False, deprecated=True)
  # ENABLE_LEGACY_ENDPOINTS: bool = Field(default=False, deprecated=True)
  ```

#### 6.6.2 Clean Up Environment Variables
- [ ] **Remove deprecated environment variables**:
  ```bash
  # Update .env.example to remove:
  # LEGACY_QUOTE_ENABLED=false
  # USE_MOCK_DATA=false
  # ENABLE_LEGACY_ENDPOINTS=false
  ```

#### 6.6.3 Update Docker Configuration
- [ ] **Remove deprecated environment variables** from `docker-compose.yml`:
  ```yaml
  # Remove from environment section:
  # - LEGACY_QUOTE_ENABLED=false
  # - USE_MOCK_DATA=false
  # - ENABLE_LEGACY_ENDPOINTS=false
  ```

### 6.7 Remove Deprecated Utility Functions

#### 6.7.1 Clean Up Utility Modules
- [ ] **Remove deprecated utility functions**:
  ```python
  # In app/utils/ directory, remove:
  # - Legacy data conversion functions
  # - Old validation functions
  # - Deprecated helper functions
  ```

#### 6.7.2 Remove Unused Imports
- [ ] **Clean up unused imports** throughout codebase:
  ```python
  # Use tools like autoflake to remove unused imports
  autoflake --remove-all-unused-imports --recursive app/
  
  # Or use isort to organize imports
  isort app/
  ```

### 6.8 Remove Deprecated Tests

#### 6.8.1 Remove Tests for Deprecated Features
- [ ] **Remove test files** for deprecated components:
  ```bash
  # Remove tests for deprecated endpoints
  rm tests/unit/test_legacy_endpoints.py
  
  # Remove tests for deprecated tools
  rm tests/unit/test_legacy_tools.py
  
  # Remove tests for backwards compatibility
  rm tests/unit/test_backwards_compatibility.py
  ```

#### 6.8.2 Clean Up Test Imports
- [ ] **Update test imports** to remove deprecated references:
  ```python
  # In test files, replace:
  # from app.models.trading import Order
  # With:
  # from app.schemas.orders import Order
  ```

#### 6.8.3 Remove Mock Data Tests
- [ ] **Remove tests** that rely on deprecated mock data:
  ```python
  # Remove tests that use:
  # - Old mock quote systems
  # - Legacy test data loading
  # - Deprecated test fixtures
  ```

### 6.9 Update Documentation

#### 6.9.1 Remove Deprecated API Documentation
- [ ] **Clean up API documentation**:
  ```python
  # Remove from FastAPI docs:
  # - Deprecated endpoint documentation
  # - Legacy parameter descriptions
  # - Deprecated response schemas
  ```

#### 6.9.2 Update CLAUDE.md
- [ ] **Remove deprecated references** from `CLAUDE.md`:
  ```markdown
  # Remove sections about:
  # - Legacy quote systems
  # - Deprecated endpoints
  # - Old configuration options
  # - Backwards compatibility notes
  ```

#### 6.9.3 Update README and Examples
- [ ] **Clean up example code**:
  ```python
  # In examples/ directory, remove:
  # - Examples using deprecated APIs
  # - Legacy usage patterns
  # - Deprecated configuration examples
  ```

### 6.10 Database Cleanup

#### 6.10.1 Remove Deprecated Database Tables
- [ ] **Create migration to remove deprecated tables**:
  ```sql
  -- Remove deprecated tables if they exist
  DROP TABLE IF EXISTS legacy_quotes;
  DROP TABLE IF EXISTS deprecated_positions;
  DROP TABLE IF EXISTS old_test_data;
  ```

#### 6.10.2 Clean Up Database Models
- [ ] **Remove deprecated model fields**:
  ```python
  # In app/models/database/trading.py, remove:
  # - Deprecated columns
  # - Legacy indexes
  # - Old relationships
  ```

### 6.11 Final Cleanup and Validation

#### 6.11.1 Run Code Quality Checks
- [ ] **Run comprehensive code quality checks**:
  ```bash
  # Check for unused imports
  autoflake --check --remove-all-unused-imports --recursive app/
  
  # Check for code style issues
  flake8 app/
  
  # Run type checking
  mypy app/
  
  # Check for security issues
  bandit -r app/
  ```

#### 6.11.2 Search for Remaining Deprecated Items
- [ ] **Search for any remaining deprecated items**:
  ```bash
  # Search for deprecated markers
  grep -r "deprecated\|DEPRECATED" app/ --include="*.py"
  
  # Search for old imports
  grep -r "from app.models.trading import" app/ --include="*.py"
  
  # Search for legacy patterns
  grep -r "legacy\|Legacy\|LEGACY" app/ --include="*.py"
  ```

#### 6.11.3 Update Version Numbers
- [ ] **Update version numbers** after cleanup:
  ```python
  # In pyproject.toml, update version to indicate major cleanup
  version = "2.0.0"  # Major version bump for breaking changes
  ```

### 6.12 Testing After Cleanup

#### 6.12.1 Run Full Test Suite
- [ ] **Ensure all tests pass** after cleanup:
  ```bash
  # Run all tests
  pytest tests/ -v
  
  # Run with coverage
  pytest --cov=app tests/
  
  # Run specific test categories
  pytest tests/unit/ tests/integration/ tests/e2e/
  ```

#### 6.12.2 Test API Endpoints
- [ ] **Verify all remaining endpoints work**:
  ```bash
  # Test FastAPI endpoints
  curl http://localhost:2080/health
  curl http://localhost:2080/api/v1/quotes/AAPL
  curl http://localhost:2080/docs  # Check API docs
  ```

#### 6.12.3 Test MCP Tools
- [ ] **Verify all remaining MCP tools work**:
  ```bash
  # Test MCP server
  curl http://localhost:2081/health
  
  # Test tool listing
  # Use MCP client to list available tools
  ```

### 6.13 Documentation Updates

#### 6.13.1 Create Migration Guide
- [ ] **Create migration guide** for users (`docs/MIGRATION_V2.md`):
  ```markdown
  # Migration Guide to v2.0
  
  ## Breaking Changes
  
  ### Removed Components
  - `app.models.trading` module (use `app.schemas.*` instead)
  - Legacy API endpoints under `/legacy/`
  - Deprecated MCP tools with `[DEPRECATED]` prefix
  - Old test data loading system
  
  ### Updated Import Patterns
  ```python
  # Old (removed):
  from app.models.trading import Order, Position
  
  # New (required):
  from app.schemas.orders import Order
  from app.schemas.positions import Position
  ```
  
  ### Configuration Changes
  - Removed `LEGACY_QUOTE_ENABLED` environment variable
  - Removed `USE_MOCK_DATA` environment variable
  - Removed `ENABLE_LEGACY_ENDPOINTS` environment variable
  ```

#### 6.13.2 Update API Documentation
- [ ] **Update API documentation** to reflect cleanup:
  ```markdown
  # Update OpenAPI documentation
  # Remove deprecated endpoint descriptions
  # Update example requests/responses
  # Remove legacy parameter documentation
  ```

### 6.14 Final Validation

#### 6.14.1 Validate System Functionality
- [ ] **Comprehensive system validation**:
  ```bash
  # Start system
  docker-compose up --build
  
  # Test core functionality
  # 1. Create account
  # 2. Get quotes
  # 3. Create orders
  # 4. View portfolio
  # 5. Test MCP tools
  ```

#### 6.14.2 Performance Validation
- [ ] **Ensure performance not degraded** after cleanup:
  ```bash
  # Run performance tests
  pytest tests/performance/ -v
  
  # Check memory usage
  # Monitor response times
  # Verify no performance regression
  ```

#### 6.14.3 Create Cleanup Report
- [ ] **Document cleanup results**:
  ```markdown
  # Cleanup Report
  
  ## Removed Components
  - X deprecated API endpoints
  - X deprecated MCP tools
  - X deprecated utility functions
  - X deprecated test files
  - X deprecated configuration options
  
  ## Code Quality Improvements
  - Reduced codebase size by X%
  - Removed X unused imports
  - Eliminated X deprecated warnings
  - Improved type safety score
  
  ## Performance Impact
  - Startup time: X% improvement
  - Memory usage: X% reduction
  - Test execution time: X% improvement
  ```

## Success Criteria

1. **No in-memory state**: All trading data persisted in PostgreSQL
2. **Live quotes**: Robinhood integration working for real-time data
3. **Test isolation**: Test data in separate database tables
4. **Clean architecture**: Clear separation between models and schemas
5. **Performance**: Response times under 100ms for common operations
6. **Reliability**: Graceful handling of API failures and rate limits
7. **Clean codebase**: All deprecated components removed

## Notes

- Each phase should be completed with full testing before moving to the next
- Database migrations should be versioned and reversible
- All changes should maintain backwards compatibility for API clients until Phase 6
- Monitor application logs during rollout for any issues
- Phase 6 introduces breaking changes - increment major version number