# API Endpoints Test Suite

This directory contains comprehensive pytest test coverage for all FastAPI endpoints in the open-paper-trading-mcp project.

## Test Organization

### Test Files

- **`test_auth_endpoints.py`** - Authentication endpoints (`/auth/token`, `/auth/me`)
- **`test_health_endpoints.py`** - Health check endpoints (`/health/*`)
- **`test_portfolio_endpoints.py`** - Portfolio management endpoints (`/portfolio/*`)
- **`test_trading_endpoints.py`** - Trading operations endpoints (`/trading/*`)
- **`test_market_data_endpoints.py`** - Market data endpoints (`/market-data/*`)
- **`test_options_endpoints.py`** - Options trading endpoints (`/options/*`)
- **`conftest.py`** - Shared fixtures and mocking utilities

### Test Coverage Statistics

| Module | Endpoints | Test Methods | Coverage |
|--------|-----------|-------------|----------|
| Authentication | 2 | 17+ | 100% |
| Health Checks | 6 | 25+ | 100% |
| Portfolio | 7 | 30+ | 100% |
| Trading | 7 | 35+ | 100% |
| Market Data | 6 | 25+ | 100% |
| Options | 7 | 35+ | 100% |
| **TOTAL** | **35** | **167+** | **100%** |

## Test Patterns

### Async Test Structure
All tests use proper async patterns with `pytest-asyncio`:

```python
@pytest.mark.asyncio
async def test_endpoint_success(self, client):
    """Test successful endpoint operation."""
    mock_service = AsyncMock(spec=TradingService)
    mock_service.method.return_value = expected_data
    
    with patch('app.core.dependencies.get_trading_service', return_value=mock_service):
        async with AsyncClient(app=client.app, base_url="http://test") as ac:
            response = await ac.get("/api/v1/endpoint")
    
    assert response.status_code == status.HTTP_200_OK
    data = response.json()
    assert data["field"] == expected_value
```

### Comprehensive Mocking
Tests mock external dependencies at the service layer:

- **TradingService** - Core business logic
- **AuthService** - Authentication operations
- **Database connections** - Async database sessions
- **External APIs** - Market data providers

### Test Scenarios Covered

#### Success Cases
- ✅ Valid requests with expected responses
- ✅ Different parameter combinations
- ✅ Edge cases (empty data, large datasets)
- ✅ Various HTTP methods (GET, POST, DELETE)

#### Error Cases
- ✅ Invalid input validation (422 Unprocessable Entity)
- ✅ Resource not found (404 Not Found)
- ✅ Authentication failures (401 Unauthorized)
- ✅ Business logic errors (400 Bad Request)
- ✅ Server errors (500 Internal Server Error)

#### Edge Cases
- ✅ Special characters in symbols (BRK.A, BRK.B)
- ✅ Unicode characters in search queries
- ✅ Large datasets and pagination
- ✅ Timeout and network errors
- ✅ Rate limiting scenarios

## Running Tests

### Run All API Tests
```bash
# Run all API endpoint tests
pytest tests/unit/api/ -v

# Run with coverage
pytest tests/unit/api/ --cov=app/api --cov-report=html

# Run specific endpoint tests
pytest tests/unit/api/test_trading_endpoints.py -v
```

### Run by Test Markers
```bash
# Run only authentication tests
pytest tests/unit/api/ -m auth

# Run only slow tests
pytest tests/unit/api/ -m slow

# Skip integration tests
pytest tests/unit/api/ -m "not integration"
```

### Parallel Execution
```bash
# Run tests in parallel (requires pytest-xdist)
pytest tests/unit/api/ -n auto
```

## Mock Data Factories

The test suite includes comprehensive mock data factories in `conftest.py`:

### MockDataFactory
Creates mock objects for testing:
- `create_stock_quote()` - Stock price quotes
- `create_option_quote()` - Options quotes with Greeks
- `create_order()` - Trading orders
- `create_position()` - Portfolio positions
- `create_portfolio()` - Complete portfolios
- `create_options_chain_response()` - Options chains
- `create_market_data_response()` - Market data responses

### MockServiceFactory
Creates mock service instances:
- `create_mock_trading_service()` - TradingService mock
- `create_mock_auth_service()` - AuthService mock

## Test Fixtures

### Core Fixtures
- `mock_trading_service` - Pre-configured TradingService mock
- `mock_auth_service` - Pre-configured AuthService mock
- `async_test_client` - AsyncClient for async endpoint testing
- `auth_headers` - Authentication headers for protected endpoints

### Data Fixtures
- `sample_stock_symbols` - Common stock symbols for testing
- `sample_option_symbols` - Option contract symbols
- `sample_order_data` - Various order types and structures
- `sample_portfolio_data` - Portfolio configurations
- `sample_market_data` - Market data responses
- `sample_options_data` - Options data structures

### Utility Fixtures
- `api_test_utils` - Helper methods for common assertions
- `health_check_responses` - Health check response templates
- `error_responses` - Error response templates

## Best Practices

### 1. Isolation
Each test is completely isolated:
- Fresh mock objects for each test
- No shared state between tests
- Database cleanup between tests

### 2. Comprehensive Coverage
Tests cover all scenarios:
- Happy path (successful operations)
- Error paths (validation, not found, server errors)
- Edge cases (boundary conditions, special inputs)
- Security scenarios (authentication, authorization)

### 3. Realistic Mocking
Mocks behave like real services:
- Proper return types and structures
- Realistic data relationships
- Appropriate error conditions

### 4. Maintainable Tests
Tests are easy to maintain:
- Clear test names describing scenarios
- Well-organized with helper methods
- Consistent patterns across all test files
- Comprehensive documentation

## Integration with CI/CD

### GitHub Actions
```yaml
- name: Run API Tests
  run: |
    pytest tests/unit/api/ \
      --cov=app/api \
      --cov-report=xml \
      --junitxml=test-results.xml
```

### Coverage Requirements
- **Minimum coverage**: 95% for API endpoints
- **Line coverage**: All endpoint functions covered
- **Branch coverage**: All error paths tested
- **Integration coverage**: Service layer interactions validated

## Debugging Tests

### Verbose Output
```bash
# Run with verbose output and no capture
pytest tests/unit/api/test_trading_endpoints.py::TestTradingEndpoints::test_create_order_success_buy -v -s
```

### Debug Mode
```bash
# Run with Python debugger
pytest tests/unit/api/ --pdb
```

### Test Coverage Analysis
```bash
# Generate detailed coverage report
pytest tests/unit/api/ --cov=app/api --cov-report=html
# Open htmlcov/index.html to view detailed coverage
```

## Contributing

When adding new API endpoints or modifying existing ones:

1. **Add comprehensive tests** covering all scenarios
2. **Update mock factories** if new data structures are introduced
3. **Follow existing patterns** for consistency
4. **Update this README** if new test categories are added
5. **Ensure tests pass** before submitting pull requests

### Test Naming Convention
```python
def test_[endpoint]_[scenario]_[expected_outcome]():
    """Test [endpoint] [when scenario] [then expected outcome]."""
```

Examples:
- `test_create_order_success_buy()` - Test order creation succeeds for buy orders
- `test_get_portfolio_not_found()` - Test portfolio retrieval when portfolio not found
- `test_get_quote_invalid_symbol()` - Test quote retrieval with invalid symbol

This comprehensive test suite ensures robust, reliable API endpoints with 100% coverage of all critical functionality and error conditions.