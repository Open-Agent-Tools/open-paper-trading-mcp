# Architectural and MyPy Refactoring Plan

## Overview
Address 537 mypy errors and improve the core architecture through a multi-phase approach. This plan targets foundational architectural issues first, then resolves type system problems, and finally cleans up remaining edge cases.

## 🚧 CURRENT PRIORITY

### Phase 0: Foundational Architecture & Models
**Goal**: Unify the project structure, separate schemas from models, establish database best practices, and set up a robust testing foundation before tackling detailed type errors.

#### 0.1 Standardize Models and Schemas
- [ ] **Separate Concerns**: Move all Pydantic models from `app/models/` to a new `app/schemas/` directory to distinguish API schemas from database models.
- [ ] **Organize Files**:
  - Create `app/schemas/orders.py` and move `Order`, `OrderLeg`, and `MultiLegOrder`.
  - Create `app/schemas/positions.py` for all position-related schemas.
  - Create `app/schemas/accounts.py` for the `Account` schema.
- [ ] **Standardize Constructors**: Add any missing required arguments to all Pydantic model constructors (e.g., `Position`, `Quote`) and provide sensible defaults for optional fields. This will fix a large category of `mypy` errors upfront.

#### 0.2 Configure Database and Migrations
- [ ] **Fix SQLAlchemy Mappings**: In `app/models/database/trading.py`, update column definitions to use modern SQLAlchemy 2.0 type annotations (e.g., `Mapped[OrderType]`).
- [ ] **Implement Database Migrations**: Integrate `Alembic` to manage and version the database schema, preventing manual schema changes.

#### 0.3 Refactor Core Application Logic
- [ ] **Enhance Configuration**: Refactor `app/core/config.py` to use Pydantic's `BaseSettings` for validated, type-safe loading of environment variables.
- [ ] **Break Circular Dependencies**: Use a tool like `pylint` or `deptry` to identify and refactor any module import cycles.
- [ ] **Refactor Services**: Review `app/services/trading_service.py` to decompose it into smaller, more cohesive services if needed.
- [ ] **Standardize Dependency Injection**: Refactor all API endpoints to consistently use FastAPI's `Depends` system for providing services and database sessions.

#### 0.4 Establish Testing Foundation
- [ ] **Ensure Isolated Test Database**: Configure the test environment to use a separate, ephemeral database for every test run.
- [ ] **Centralize Test Fixtures**: Move common test setup logic (e.g., creating an API client, a database session) into `tests/conftest.py` for reusability.

#### 0.5 Finalize and Clean Up
- [ ] **Fix Imports**: After all files have been moved and reorganized, update all import statements across the application to reflect the new structure.

#### 0.6 Code Quality and Consistency
- [ ] **Format and Lint**: Run a full formatting (`ruff format .`) and linting (`ruff check .`) pass across the entire codebase to ensure a consistent style after major structural changes.

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