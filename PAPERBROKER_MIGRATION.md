# Paperbroker Migration Plan

This document outlines the systematic migration of capabilities from the paperbroker reference implementation into our Open Paper Trading MCP application.

## 📋 Migration Roadmap

### Phase 1A: Core Data Models ✅ COMPLETE

#### 1.1 Asset Models - `app/models/assets.py` ✅ COMPLETE
- [x] `Asset` base class with symbol normalization and equality
- [x] `asset_factory()` function for polymorphic asset creation
- [x] `Option` class with symbol parsing and validation
- [x] `Call` and `Put` specialized option classes
- [x] Option symbol parsing (AAPL240119C00195000 format)
- [x] Intrinsic/extrinsic value calculations
- [x] Days to expiration calculation
- [x] ITM/OTM checking methods

#### 1.2 Enhanced Order Models - `app/models/trading.py` ✅ COMPLETE
- [x] Add options-specific order types (BTO, STO, BTC, STC)
- [x] Create `OrderLeg` class for multi-leg orders
- [x] Create `MultiLegOrder` class extending current Order
- [x] Add automatic quantity/price sign correction by order type
- [x] Add order condition support (market, limit, stop)
- [x] Add order validation for options-specific rules
- [x] Builder pattern methods for common option strategies

#### 1.3 Enhanced Position Models - `app/models/trading.py` ✅ COMPLETE
- [x] Add options multiplier handling (100x for options)
- [x] Add Greeks properties (delta, gamma, theta, vega, rho, iv)
- [x] Add profit/loss calculation methods with P&L percentage
- [x] Add total vs per-share amount calculations
- [x] Add option-specific position properties (strike, expiration, etc.)
- [x] Add position closing simulation and cost analysis
- [x] Add market data update methods with Greeks integration

### Phase 1B: Quote and Pricing System ✅ COMPLETE

#### 1.4 Quote System - `app/models/quotes.py` ✅ COMPLETE
- [x] Create `Quote` base class with bid/ask/price
- [x] Create `OptionQuote` class with Greeks integration
- [x] Add `quote_factory()` for polymorphic quote creation
- [x] Add price validation and midpoint calculation
- [x] Add quote timestamp and data source tracking
- [x] Integration with asset models
- [x] Add OptionsChain class for complete option chains
- [x] Add 15+ Greeks support (including advanced Greeks)

#### 1.5 Greeks Calculation Service - `app/services/greeks.py` ✅ COMPLETE
- [x] Pure Python Black-Scholes implementation (no external deps)
- [x] Newton-Raphson implied volatility calculation
- [x] First-order Greeks (delta, gamma, theta, vega, rho)
- [x] Second-order Greeks (charm, vanna, speed, zomma, color, etc.)
- [x] Advanced Greeks (veta, vomma, ultima, dual_delta)
- [x] Risk-free rate and dividend handling
- [x] Comprehensive validation and error handling
- [x] Integration with OptionQuote automatic calculation

### Phase 1C: Trading Engine Enhancements ✅ COMPLETE

#### 1.6 Order Execution Engine - `app/services/order_execution.py` ✅ COMPLETE
- [x] **Migrated `fill_order()` logic from paperbroker** (core functionality)
- [x] Add multi-leg order execution with proper leg processing
- [x] Implement position opening vs closing logic (BTO/STO vs BTC/STC)
- [x] Add automatic quantity/price sign correction by order type
- [x] Add cash balance validation with options multiplier (100x)
- [x] Add position quantity validation for closing orders
- [x] Implement FIFO position closing with partial quantities
- [x] Add automatic position creation and updates with cost basis
- [x] Add maintenance margin calculation after fills
- [x] Integration with quote system for realistic fill prices
- [x] Comprehensive order validation and error handling

#### 1.7 Account Validation Service - `app/services/validation.py` ✅ COMPLETE
- [x] **Migrated `validate_account()` logic from paperbroker**
- [x] Add sufficient cash validation for orders
- [x] Add maintenance margin requirement checking
- [x] Add position availability validation for closing orders
- [x] Add overleveraging prevention
- [x] Add order size and quantity limits
- [x] Multi-leg order validation with options-specific rules

#### 1.8 Test Data System - `app/adapters/test_data.py` ✅ COMPLETE
- [x] **Migrated TestDataQuoteAdapter from paperbroker**
- [x] Port historical options and stock data (AAL, GOOG 2017)
- [x] Add compressed test data storage system (gzip CSV)
- [x] Implement time-based testing scenarios
- [x] Add pre-calculated Greeks for test data
- [x] Create test data management utilities
- [x] Integration with quote system for testing
- [x] Sample test scenarios for common use cases

#### 1.9 Order Impact Analysis - `app/services/order_impact.py` ✅ COMPLETE
- [x] **Migrated OrderImpact analysis from paperbroker**
- [x] Add comprehensive before/after order simulation
- [x] Implement cash impact calculation with options multiplier
- [x] Add margin requirement change analysis
- [x] Add sophisticated risk assessment capabilities
- [x] Create order preview functionality for UIs
- [x] Portfolio Greeks impact analysis
- [x] Position change tracking and concentration warnings

### Phase 1D: Risk Management Foundation ✅ COMPLETE

#### 1.10 Strategy Recognition Service - `app/services/strategies.py` ✅ COMPLETE
- [x] **Migrated `group_into_basic_strategies()` from paperbroker**
- [x] Add covered call/put detection with automatic pairing
- [x] Add spread recognition (credit/debit, call/put)
- [x] Add naked position identification
- [x] Add strategy risk analysis and summary statistics
- [x] Integration with margin calculation system
- [x] Pydantic models for all strategy types

#### 1.11 Maintenance Margin Service - `app/services/margin.py` ✅ COMPLETE
- [x] **Migrated margin calculation logic from paperbroker**
- [x] Add margin requirements by strategy type:
  - [x] Long positions (no margin)
  - [x] Short stock positions (full margin)
  - [x] Covered strategies (no margin)
  - [x] Credit/debit spreads (width-based)
  - [x] Naked options (enhanced standard formulas)
- [x] Add real-time margin monitoring
- [x] Add margin call detection and portfolio breakdown
- [x] Enhanced naked option margin calculations beyond paperbroker

## 🎉 Phase 1 Complete! 

**Phase 1 Status: ✅ 100% COMPLETE**

All core paperbroker functionality has been successfully migrated and enhanced:

### ✅ **Completed Components (11/11)**
1. ✅ **Asset Models** - Complete options support with symbol parsing
2. ✅ **Enhanced Order Models** - BTO/STO/BTC/STC, multi-leg orders
3. ✅ **Enhanced Position Models** - Options multiplier, Greeks, P&L
4. ✅ **Quote System** - Complete quote framework with 15+ Greeks
5. ✅ **Greeks Calculation** - Pure Python Black-Scholes implementation
6. ✅ **Order Execution Engine** - Full paperbroker fill_order logic
7. ✅ **Account Validation** - Comprehensive order and account validation
8. ✅ **Test Data System** - Historical options data with pre-calculated Greeks
9. ✅ **Order Impact Analysis** - Before/after simulation with risk assessment
10. ✅ **Strategy Recognition** - Automated strategy detection and analysis
11. ✅ **Maintenance Margin** - Enhanced margin calculations for all strategies

### 🚀 **Enhanced Beyond Paperbroker**
- **Pydantic v2 Models** - Type safety and validation throughout
- **Async/Modern Python** - Contemporary patterns and best practices
- **Docker Integration** - Fully containerized with PostgreSQL
- **Dual Interface** - Both REST API and MCP server support
- **Enhanced Greeks** - 15+ Greeks vs paperbroker's basic set
- **Sophisticated Risk Management** - Portfolio analysis and warnings
- **Builder Patterns** - Easy multi-leg order construction

### 📊 **Phase 1 Impact**
- **🔧 Core Services**: 11 sophisticated trading services
- **📋 Data Models**: Complete options trading model support
- **🧮 Greeks Calculation**: Production-ready Black-Scholes implementation
- **⚖️ Risk Management**: Strategy recognition and margin calculations
- **🏗️ Architecture**: Modern, scalable, containerized platform

**Ready for Phase 2: API Exposure and Market Data Integration**

### Phase 2: Market Data Integration - **MOVED TO FINAL PHASE**

*Note: All live data retrieval capabilities have been moved to Phase 6 (final phase) to focus on core functionality first.*

### Phase 2B: Options Trading Specialized Features ✅ COMPLETE

#### 2.5 Options Expiration Engine - `app/services/expiration.py` ✅ COMPLETE
- [x] **Migrate `close_expired_options()` logic from paperbroker**
- [x] Add automatic ITM/OTM option processing
- [x] Implement assignment and exercise simulation
- [x] Add cash and position adjustments for expired options
- [x] Handle covered calls/puts with insufficient underlying shares
- [x] Add `drain_asset` utility for reducing position quantities
- [x] Add expiration notification system
- [x] Integration with position management and cash updates

#### 2.6 Price Estimators - `app/services/estimators.py` ✅ COMPLETE
- [x] **Migrate estimator classes from paperbroker**
- [x] Add `MidpointEstimator` for bid-ask midpoint fills
- [x] Add `SlippageEstimator` for realistic execution within spread
- [x] Add `FixedPriceEstimator` for testing and forced fills
- [x] Add configurable slippage parameters
- [x] Integration with order execution system

### Phase 3: Advanced Features ✅ COMPLETE

#### 3.1 Advanced Strategy Analysis ✅ COMPLETE
- [x] Add advanced strategy P&L calculation
- [x] Add strategy risk analysis and Greeks aggregation
- [x] Add performance attribution by strategy
- [x] Add strategy optimization recommendations
- [x] Add complex strategy detection (iron condors, butterflies, etc.)

#### 3.2 Advanced Order Validation ✅ COMPLETE
- [x] Add comprehensive order validation beyond basic checks:
  - [x] Options expiration validation
  - [x] Strike price reasonableness validation
  - [x] Strategy-specific quantity limits
  - [x] Risk-based position size limits
- [x] Add account status and compliance validation
- [x] Add pre-trade risk analysis

### Phase 4: API and MCP Integration ✅ COMPLETE

#### 4.1 Enhanced MCP Tools ✅ COMPLETE
- [x] Add options-specific MCP tools:
  - [x] `get_options_chain(symbol, expiration_date)`
  - [x] `get_expiration_dates(symbol)`
  - [x] `create_multi_leg_order(legs)`
  - [x] `calculate_option_greeks(option_symbol, underlying_price)`
  - [x] `get_strategy_analysis(positions)`
  - [x] `simulate_option_expiration(account_id)`

#### 4.2 Enhanced REST API Endpoints ✅ COMPLETE
- [x] Add options endpoints to FastAPI:
  - [x] `/api/v1/options/{symbol}/chain`
  - [x] `/api/v1/options/{symbol}/expirations`
  - [x] `/api/v1/orders/multi-leg`
  - [x] `/api/v1/positions/{id}/greeks`
  - [x] `/api/v1/strategies/analyze`

#### 4.3 Database Schema Updates ✅ COMPLETE
- [x] Add options-specific database tables:
  - [x] `option_quotes` table with Greeks
  - [x] `order_legs` table for multi-leg orders
  - [x] `strategies` table for recognized strategies
  - [x] `option_expirations` table for tracking
- [x] Add foreign key relationships
- [x] Add database indexes for performance

### Phase 5: Testing and Validation 🚧 PLANNED **[NEXT PRIORITY]**

#### 5.1 Unit Tests 🚧 PLANNED
- [ ] Port relevant tests from paperbroker
- [ ] Add tests for new asset models
- [ ] Add tests for Greeks calculations
- [ ] Add tests for order execution logic
- [ ] Add tests for risk management
- [ ] Add integration tests with database

#### 5.2 Sample Data and Examples 🚧 PLANNED
- [ ] Port sample options data from paperbroker
- [ ] Create example multi-leg order scenarios
- [ ] Create example strategy scenarios
- [ ] Add educational examples for documentation

### Phase 6: Live Market Data Integration 🚧 PLANNED **[FINAL PHASE]**

#### 6.1 Quote Adapter Framework - `app/adapters/`
- [ ] Create `QuoteAdapter` base class interface
- [ ] Create adapter registry and factory
- [ ] Add quote caching mechanism with TTL
- [ ] Create test data adapter for development
- [ ] Plan integration with Polygon.io for options data
- [ ] Add adapter configuration management

#### 6.2 Options Data Support
- [ ] Add options chain retrieval
- [ ] Add expiration date queries
- [ ] Add strike range filtering
- [ ] Add Greeks data caching
- [ ] Add options market hours handling
- [ ] Add underlying price correlation

## 🎯 Updated Implementation Priority

### ✅ **COMPLETED PHASES** (Phases 1-4)
All core paperbroker functionality has been successfully migrated and enhanced:

1. ✅ **Phase 1A-1D: Core Models & Trading Engine** - Complete foundation
2. ✅ **Phase 2B: Options Trading Features** - Expiration engine, price estimators
3. ✅ **Phase 3: Advanced Features** - Strategy analysis, advanced validation
4. ✅ **Phase 4: API/MCP Integration** - Complete dual-interface support

### 🚧 **REMAINING PHASES** (Phases 5-6)

#### **Phase 5: Testing and Validation** (NEXT PRIORITY)
5. **Unit Tests** - Port tests from paperbroker, add comprehensive coverage
6. **Sample Data** - Create educational examples and test scenarios

#### **Phase 6: Live Market Data Integration** (FINAL PHASE)
7. **Quote Adapter Framework** - Pluggable market data integration
8. **Options Data Support** - Real-time options chains and Greeks

## 📦 Dependencies to Add

```toml
# Option 1: Pure Python (recommended for start)
scipy = "^1.11.0"     # For statistical functions
numpy = "^1.24.0"     # For numerical computations

# Option 2: Exact paperbroker compatibility (later)
ivolat3 = "^1.0.0"    # For advanced Greeks calculations

# Option 3: Alternative options pricing libraries
py_vollib = "^1.0.1"  # Another options library option
```

## 🧪 Testing Strategy

1. **Unit Tests**: Each migrated component gets comprehensive tests
2. **Integration Tests**: End-to-end options trading scenarios  
3. **Validation Tests**: Compare results with paperbroker reference
4. **Performance Tests**: Ensure Greeks calculations are fast enough
5. **Edge Case Tests**: Expiration, deep ITM/OTM, zero DTE options

## 📚 Documentation Plan

1. **API Documentation**: Update OpenAPI specs with options endpoints
2. **Usage Examples**: Multi-leg order creation and management
3. **Strategy Guides**: How to implement common options strategies
4. **Migration Guide**: How features map from paperbroker to our app
5. **Educational Content**: Options trading concepts and Greeks

This migration plan ensures we systematically adopt paperbroker's proven patterns while maintaining our FastAPI/MCP architecture and adding our own improvements.