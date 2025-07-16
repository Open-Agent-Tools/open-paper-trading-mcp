# Architectural and MyPy Refactoring Plan

## Overview
Address 537 mypy errors and improve the core architecture through a multi-phase approach. This plan targets foundational architectural issues first, then resolves type system problems, and finally cleans up remaining edge cases.

## 🚧 CURRENT PRIORITY

### Phase 0: Foundational Architecture & Models
**Goal**: Unify the project structure, separate schemas from models, establish database best practices, and set up a robust testing foundation before tackling detailed type errors.

**Implementation Priority**: Tasks must be completed in this order to minimize cascading failures and maximize MyPy error reduction.

#### ✅ PRIORITY 1: Schema/Model Separation (0.1) - COMPLETE
**Why First**: Foundation for everything else, will immediately resolve many MyPy errors

- [x] **Create Schema Directory Structure**: ✅ Created `app/schemas/` with proper `__init__.py`
- [x] **Move and Reorganize Schemas**: ✅ All schemas moved successfully:
  - Created `app/schemas/orders.py` → Moved `Order`, `OrderLeg`, `MultiLegOrder`, enums
  - Created `app/schemas/positions.py` → Moved `Position`, `Portfolio`, `PortfolioSummary`  
  - Created `app/schemas/accounts.py` → Moved `Account` schema
  - Created `app/schemas/trading.py` → Moved `StockQuote` and general trading schemas
- [x] **Backwards Compatibility**: ✅ `app/models/trading.py` now re-exports all schemas
- [x] **Standardize Constructors**: ✅ All schemas have proper Field definitions with defaults

#### ✅ PRIORITY 2: Fix Imports & Dependencies (0.5) - COMPLETE
**Why Second**: Must be done immediately after schema move to prevent breakage

- [x] **Schema Exports**: ✅ `app/schemas/__init__.py` exports all schemas for easy access
- [x] **Backwards Compatibility**: ✅ All existing imports continue to work via `app.models.trading`
- [x] **Verify Module Loading**: ✅ All critical modules (main, services, API) load correctly
- [x] **Application Startup**: ✅ FastAPI app imports and initializes successfully

#### 🥉 PRIORITY 3: Database Configuration (0.2)
**Why Third**: Critical for production, independent of other tasks

- [ ] **Update SQLAlchemy Models**: Use `Mapped[Type]` annotations in `app/models/database/trading.py`
- [ ] **Set Up Alembic**: Integrate database migrations
- [ ] **Create Initial Migration**: From current schema
- [ ] **Test Migration**: Verify up/down operations work

#### 🏅 PRIORITY 4: Service Architecture Review (0.3)
**Why Fourth**: May require schema changes, so do after schema separation

- [ ] **Analyze TradingService Complexity**: Identify decomposition opportunities
- [ ] **Standardize Dependency Injection**: Use FastAPI `Depends` consistently across endpoints
- [ ] **Refactor Services**: Break down large services if needed (may defer to Phase 1)
- [x] **Enhanced Configuration**: `app/core/config.py` already uses `BaseSettings` ✅
- [x] **Break Circular Dependencies**: Recent import review found none ✅

#### 🎖️ PRIORITY 5: Testing Foundation (0.4)
**Why Fifth**: Needs stable schemas and services to be effective

- [ ] **Verify Test Database Isolation**: Ensure separate, ephemeral test database
- [ ] **Centralize Test Fixtures**: Expand `tests/conftest.py` with new schema structure
- [ ] **Create Base Test Classes**: For common testing patterns

#### 🏆 PRIORITY 6: Code Quality Pass (0.6)
**Why Last**: Only after all structural changes are complete

- [ ] **Run Full Format Pass**: `ruff format .`
- [ ] **Run Full Lint Pass**: `ruff check .`
- [ ] **Verify MyPy Improvement**: Compare error count to baseline

#### Success Gates
Each priority must pass these gates before moving to the next:
- [ ] All imports resolve correctly
- [ ] All tests pass
- [ ] MyPy error count decreases
- [ ] Application starts successfully

---

## 🚀 PLANNED PHASES (Renumbered)

### Phase 1: Type System Cleanup
**Goal**: Resolve type annotation and Union handling issues within the new architecture.

- [ ] **Fix Union Type Handling**: Add type guards for `str | Asset` unions to resolve attribute access errors.
- [ ] **Complete Type Annotations**: Add return type annotations to all untyped functions and use modern generic types (`list[T]`, `dict[K, V]`).
- [ ] **Fix Adapter Architecture**: Align concrete adapter implementations with base classes and resolve any method signature compatibility issues.
- [ ] **Fix Quote and Asset Type Issues**: Ensure `Asset` and `Quote` types have all required attributes across the service and adapter layers.

### Phase 2: Service Layer Consistency
**Goal**: Standardize types and models across the service layer.

- [ ] **Strategy System Fixes**: Ensure all `BasicStrategy` subclasses have consistent interfaces and attributes.
- [ ] **Trading Service Updates**: Ensure all services correctly construct and handle the new Pydantic schemas and SQLAlchemy models.
- [ ] **Fix Service Dependencies**: Resolve any remaining `None` checks for adapters and ensure all services are initialized with their required dependencies.

### Phase 3: Edge Case Cleanup
**Goal**: Handle remaining operator, indexing, and compatibility issues to achieve near-zero errors.

- [ ] **Operator Safety**: Add null checks before performing operations on `Optional` types.
- [ ] **Method Override Issues**: Fix any remaining Liskov substitution principle violations in subclasses.
- [ ] **Final Compatibility**: Address any final `Dict`/`List` generic parameter issues and `no-any-return` errors.
- [ ] **Testing Integration**: Fix any abstract class instantiation issues in tests and update fixtures to use the correct types.

### Phase 4: Final Verification and Documentation
**Goal**: Ensure the refactoring is complete, correct, and well-documented.

- [ ] **Verify Public API Contract**: Run or create contract tests to ensure that the JSON structure of API requests and responses has not been unintentionally altered.
- [ ] **Update Documentation**: Review and update all project documentation (`GEMINI.md`, `README.md`) to reflect the new architecture.

## Implementation Strategy

1.  **One Phase at a Time**: Complete each phase before starting the next.
2.  **Test After Each Phase**: Run `uv run mypy app/` to verify progress.
3.  **Track Progress**: Use the mypy error count to measure success.
4.  **Focus on High-Impact Files**: Start with the files that have the most errors.

## Expected Outcome
This systematic approach addresses architectural foundations first, ensuring type safety improvements build on a solid and maintainable structure. The end result should be a fully type-safe codebase with comprehensive mypy compliance and a more robust, scalable design.