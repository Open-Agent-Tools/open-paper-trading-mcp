import os
from collections.abc import AsyncGenerator
from typing import Any
from unittest.mock import MagicMock

import pytest
import pytest_asyncio
from fastapi.testclient import TestClient
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine


def pytest_configure(config):
    """Configure pytest with custom markers."""
    config.addinivalue_line("markers", "unit: Unit tests")
    config.addinivalue_line("markers", "integration: Integration tests")
    config.addinivalue_line("markers", "performance: Performance tests")
    config.addinivalue_line("markers", "slow: Slow running tests")
    config.addinivalue_line("markers", "database: Tests that require database")
    config.addinivalue_line("markers", "live_data: Tests that require live market data")
    config.addinivalue_line(
        "markers", "robinhood: Tests that use live Robinhood API calls"
    )
    config.addinivalue_line("markers", "asyncio: Async test marker")


# Set testing environment variables BEFORE importing the app
os.environ["TESTING"] = "True"
# Use Docker PostgreSQL database for all tests
os.environ["DATABASE_URL"] = (
    "postgresql+asyncpg://trading_user:trading_password@localhost:5432/trading_db"
)
os.environ["TEST_DATABASE_URL"] = (
    "postgresql+asyncpg://trading_user:trading_password@localhost:5432/trading_db"
)
os.environ["QUOTE_ADAPTER_TYPE"] = "test"  # Use test data adapter

# Import statements after environment setup (required by ruff E402)
from datetime import UTC  # noqa: E402

from app.main import app  # noqa: E402
from app.models.database import trading  # noqa: E402, F401
from app.models.database.base import Base  # noqa: E402
from app.storage.database import get_async_session  # noqa: E402


# Configure pytest-asyncio explicitly
@pytest.fixture(scope="session")
def event_loop_policy():
    """Set event loop policy for the session."""
    import asyncio

    return asyncio.DefaultEventLoopPolicy()


@pytest_asyncio.fixture(scope="session", autouse=True)
async def setup_test_database():
    """Set up test database once per test session."""
    # Create engine in the current event loop
    database_url = os.environ.get(
        "TEST_DATABASE_URL",
        "postgresql+asyncpg://trading_user:trading_password@localhost:5432/trading_db",
    )

    session_engine = create_async_engine(database_url, echo=False, future=True)

    # Create tables using session engine
    async with session_engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    yield

    # Cleanup after all tests
    await session_engine.dispose()


@pytest_asyncio.fixture(scope="function")
async def db_session() -> AsyncGenerator[AsyncSession, None]:
    """Standard database session fixture - all tests should use this."""

    # Create engine in current event loop (critical for AsyncIO compatibility)
    database_url = os.environ.get(
        "TEST_DATABASE_URL",
        "postgresql+asyncpg://trading_user:trading_password@localhost:5432/trading_db",
    )

    # Create fresh engine for each test to ensure correct event loop binding
    test_engine = create_async_engine(
        database_url,
        echo=False,
        future=True,
        pool_pre_ping=True,  # Verify connections before use
        pool_recycle=300,  # Recycle connections every 5 minutes
    )

    # Create session factory bound to current event loop
    test_session_factory = async_sessionmaker(
        bind=test_engine, class_=AsyncSession, expire_on_commit=False
    )

    try:
        # Clean up any existing test data BEFORE test runs
        async with test_engine.begin() as conn:
            await conn.execute(text("TRUNCATE TABLE transactions CASCADE"))
            await conn.execute(text("TRUNCATE TABLE orders CASCADE"))
            await conn.execute(text("TRUNCATE TABLE positions CASCADE"))
            await conn.execute(text("TRUNCATE TABLE accounts CASCADE"))
            await conn.commit()

        # Create session using test session factory
        async with test_session_factory() as session:
            try:
                yield session
                # Commit any pending transactions
                await session.commit()
            except Exception:
                # Rollback on error
                await session.rollback()
                raise

        # Clean up data (not tables) for test isolation AFTER test runs
        try:
            async with test_engine.begin() as conn:
                # Truncate all tables to clean up test data
                await conn.execute(text("TRUNCATE TABLE transactions CASCADE"))
                await conn.execute(text("TRUNCATE TABLE orders CASCADE"))
                await conn.execute(text("TRUNCATE TABLE positions CASCADE"))
                await conn.execute(text("TRUNCATE TABLE accounts CASCADE"))
                await conn.commit()
        except Exception as e:
            print(f"Test cleanup warning: {e}")
    except Exception as e:
        print(f"Database session setup error: {e}")
        raise
    finally:
        # Always dispose engine to prevent connection leaks
        await test_engine.dispose()


@pytest_asyncio.fixture(scope="function")
async def async_db_session() -> AsyncGenerator[AsyncSession, None]:
    """Alias for db_session to maintain backward compatibility."""
    # Use the same pattern as db_session but as separate fixture

    database_url = os.environ.get(
        "TEST_DATABASE_URL",
        "postgresql+asyncpg://trading_user:trading_password@localhost:5432/trading_db",
    )

    # Create fresh engine for each test to ensure correct event loop binding
    test_engine = create_async_engine(
        database_url, echo=False, future=True, pool_pre_ping=True, pool_recycle=300
    )

    test_session_factory = async_sessionmaker(
        bind=test_engine, class_=AsyncSession, expire_on_commit=False
    )

    try:
        # Clean up any existing test data BEFORE test runs
        async with test_engine.begin() as conn:
            await conn.execute(text("TRUNCATE TABLE transactions CASCADE"))
            await conn.execute(text("TRUNCATE TABLE orders CASCADE"))
            await conn.execute(text("TRUNCATE TABLE positions CASCADE"))
            await conn.execute(text("TRUNCATE TABLE accounts CASCADE"))
            await conn.commit()

        # Create session using test session factory
        async with test_session_factory() as session:
            try:
                yield session
                # Commit any pending transactions
                await session.commit()
            except Exception:
                # Rollback on error
                await session.rollback()
                raise

        # Clean up data for test isolation AFTER test runs
        try:
            async with test_engine.begin() as conn:
                await conn.execute(text("TRUNCATE TABLE transactions CASCADE"))
                await conn.execute(text("TRUNCATE TABLE orders CASCADE"))
                await conn.execute(text("TRUNCATE TABLE positions CASCADE"))
                await conn.execute(text("TRUNCATE TABLE accounts CASCADE"))
                await conn.commit()
        except Exception as e:
            print(f"Test cleanup warning: {e}")
    except Exception as e:
        print(f"Database session setup error: {e}")
        raise
    finally:
        # Always dispose engine to prevent connection leaks
        await test_engine.dispose()


@pytest.fixture
def client(async_db_session: AsyncSession) -> TestClient:
    """Create a test client that uses the test database session."""

    async def override_get_async_session() -> AsyncGenerator[AsyncSession, None]:
        yield async_db_session

    app.dependency_overrides[get_async_session] = override_get_async_session

    # Initialize TradingService for testing and store in app state
    from app.services.trading_service import TradingService, _get_quote_adapter

    trading_service = TradingService(_get_quote_adapter())
    app.state.trading_service = trading_service

    return TestClient(app)


@pytest_asyncio.fixture
async def test_async_session(
    async_db_session: AsyncSession,
) -> AsyncGenerator[AsyncSession, None]:
    """Create a new async database session for a test - alias for async_db_session."""
    # Use the same session as async_db_session to avoid conflicts
    yield async_db_session


@pytest.fixture
def auth_headers() -> dict[str, str]:
    """Create authentication headers for testing."""
    return {"Authorization": "Bearer testuser"}


@pytest.fixture
def mock_trading_service(mocker: Any) -> MagicMock:
    """Mock the trading service."""
    mock_service = mocker.patch("app.services.trading_service.trading_service")
    return mock_service


# Enhanced Test Fixtures for Integration Testing


@pytest_asyncio.fixture
async def test_account_data(async_db_session: AsyncSession) -> dict[str, Any]:
    """Create test account with sample data."""
    import uuid

    from app.models.database.trading import Account as DBAccount
    from app.models.database.trading import Position as DBPosition

    # Create test account
    account = DBAccount(
        id="TEST123456",
        owner="test_user",
        cash_balance=100000.0,
    )
    async_db_session.add(account)
    await async_db_session.commit()
    await async_db_session.refresh(account)

    # Create test positions
    positions = [
        DBPosition(
            id="POS_001",
            account_id=account.id,
            symbol="AAPL",
            quantity=100,
            avg_price=150.0,
        ),
        DBPosition(
            id="POS_002",
            account_id=account.id,
            symbol="GOOGL",
            quantity=50,
            avg_price=2800.0,
        ),
    ]

    for position in positions:
        async_db_session.add(position)

    await async_db_session.commit()

    return {
        "account": account,
        "positions": positions,
        "account_id": account.id,
        "owner": account.owner,
    }


@pytest.fixture
def sample_stock_quotes() -> dict[str, Any]:
    """Create sample stock quotes for testing."""
    from datetime import datetime

    from app.schemas.trading import StockQuote

    return {
        "AAPL": StockQuote(
            symbol="AAPL",
            price=155.0,
            change=5.0,
            change_percent=3.33,
            volume=1000000,
            last_updated=datetime.now(),
        ),
        "GOOGL": StockQuote(
            symbol="GOOGL",
            price=2750.0,
            change=-50.0,
            change_percent=-1.79,
            volume=500000,
            last_updated=datetime.now(),
        ),
        "MSFT": StockQuote(
            symbol="MSFT",
            price=380.0,
            change=2.5,
            change_percent=0.66,
            volume=800000,
            last_updated=datetime.now(),
        ),
    }


@pytest.fixture
def sample_order_data() -> dict[str, Any]:
    """Create sample order data for testing."""
    from app.schemas.orders import OrderCondition, OrderCreate, OrderType

    return {
        "buy_market": OrderCreate(
            symbol="AAPL",
            order_type=OrderType.BUY,
            quantity=100,
            price=None,  # Market order
            condition=OrderCondition.MARKET,
            stop_price=None,
            trail_percent=None,
            trail_amount=None,
        ),
        "sell_limit": OrderCreate(
            symbol="AAPL",
            order_type=OrderType.SELL,
            quantity=50,
            price=160.0,
            condition=OrderCondition.LIMIT,
            stop_price=None,
            trail_percent=None,
            trail_amount=None,
        ),
        "buy_limit": OrderCreate(
            symbol="GOOGL",
            order_type=OrderType.BUY,
            quantity=10,
            price=2700.0,
            condition=OrderCondition.LIMIT,
            stop_price=None,
            trail_percent=None,
            trail_amount=None,
        ),
    }


@pytest_asyncio.fixture
async def trading_service_with_data(
    async_db_session: AsyncSession, test_account_data: dict[str, Any]
) -> Any:
    """Create a TradingService instance with test data and mocked quote adapter."""
    from datetime import datetime
    from unittest.mock import AsyncMock, MagicMock

    from app.schemas.trading import StockQuote
    from app.services.trading_service import TradingService

    # Create trading service
    service = TradingService(account_owner=test_account_data["owner"])

    # Override the database session via dependency injection
    from unittest.mock import patch

    with patch.object(service, "_get_async_db_session", return_value=async_db_session):
        pass  # Service will use the mocked session

    # Mock quote adapter with realistic data
    mock_adapter = MagicMock()
    mock_adapter.get_quote = AsyncMock()
    mock_adapter.get_quote.side_effect = lambda symbol: StockQuote(
        symbol=symbol,
        price={"AAPL": 155.0, "GOOGL": 2750.0, "MSFT": 380.0}.get(symbol, 100.0),
        change=0.0,
        change_percent=0.0,
        volume=1000000,
        last_updated=datetime.now(),
    )

    service.quote_adapter = mock_adapter

    return service


@pytest.fixture
def mock_quote_adapter() -> MagicMock:
    """Create a mock quote adapter for testing."""
    from datetime import datetime
    from unittest.mock import AsyncMock, MagicMock

    from app.schemas.trading import StockQuote

    adapter = MagicMock()
    adapter.get_quote = AsyncMock()

    # Default quote response
    adapter.get_quote.return_value = StockQuote(
        symbol="TEST",
        price=100.0,
        change=0.0,
        change_percent=0.0,
        volume=1000000,
        last_updated=datetime.now(),
    )

    return adapter


@pytest_asyncio.fixture
async def integration_test_client(
    async_db_session: AsyncSession, test_account_data: dict[str, Any]
) -> TestClient:
    """Create a test client configured for integration testing."""

    from app.services.trading_service import TradingService

    # Override database session dependency
    async def override_get_async_session() -> AsyncGenerator[AsyncSession, None]:
        yield async_db_session

    app.dependency_overrides[get_async_session] = override_get_async_session

    # Create and configure trading service for integration testing
    trading_service = TradingService(account_owner=test_account_data["owner"])
    # Note: Database session will be overridden by FastAPI dependency injection

    # Store in app state
    app.state.trading_service = trading_service

    return TestClient(app)


@pytest.fixture
def test_scenarios() -> dict[str, Any]:
    """Create common test scenarios for integration testing."""
    return {
        "happy_path_order": {
            "symbol": "AAPL",
            "quantity": 100,
            "order_type": "buy",
            "expected_cost": 15500.0,  # 100 * 155.0
        },
        "insufficient_funds": {
            "symbol": "BERKB",  # Expensive stock
            "quantity": 1000,
            "order_type": "buy",
            "price": 500000.0,  # Would exceed account balance
        },
        "partial_sell": {
            "symbol": "AAPL",
            "quantity": 50,  # Sell half of existing position
            "order_type": "sell",
        },
    }


@pytest.fixture
def performance_monitor():
    """Create a performance monitor for testing."""
    from app.services.performance_benchmarks import PerformanceMonitor

    monitor = PerformanceMonitor()
    return monitor


# Shared Trading Service Fixtures for Stock Market Data Tests


@pytest_asyncio.fixture
async def trading_service_test_data():
    """Create TradingService with mock test data adapter (read-only)."""
    from datetime import datetime

    from app.adapters.base import QuoteAdapter
    from app.services.trading_service import TradingService

    class MockTestQuoteAdapter(QuoteAdapter):
        """Mock quote adapter with hardcoded test data - no database access."""

        def __init__(self):
            from app.models.assets import asset_factory

            # Create simple mock quote objects with required attributes
            class MockQuote:
                def __init__(self, symbol, price, bid, ask, volume, previous_close):
                    self.asset = asset_factory(symbol)
                    self.symbol = symbol
                    self.price = price
                    self.bid = bid
                    self.ask = ask
                    self.volume = volume
                    self.previous_close = previous_close
                    self.quote_date = datetime.now(UTC)

            self.test_quotes = {
                "AAPL": MockQuote("AAPL", 150.25, 150.20, 150.30, 1000000, 148.50),
                "MSFT": MockQuote("MSFT", 380.00, 379.95, 380.05, 800000, 378.25),
                "GOOGL": MockQuote("GOOGL", 2750.00, 2749.00, 2751.00, 500000, 2720.00),
                "TSLA": MockQuote("TSLA", 250.00, 249.95, 250.05, 2000000, 245.00),
            }

        async def get_quote(self, asset):
            """Return mock quote data."""
            # Extract symbol from Asset object
            if hasattr(asset, "symbol"):
                symbol = asset.symbol
            elif hasattr(asset, "__str__"):
                symbol = str(asset)
            else:
                symbol = str(asset)

            return self.test_quotes.get(symbol.upper())

        async def get_quotes(self, assets):
            """Return multiple mock quotes."""
            return {asset: await self.get_quote(asset) for asset in assets}

        async def get_chain(self, underlying, expiration_date=None):
            return []

        async def get_options_chain(self, underlying, expiration_date=None):
            return None

        async def is_market_open(self):
            return True

        async def get_market_hours(self):
            return {"market_open": True}

        def get_sample_data_info(self):
            return {"provider": "mock", "symbols": list(self.test_quotes.keys())}

        def get_expiration_dates(self, underlying):
            return []

        def get_test_scenarios(self):
            return {"default": "Mock test data"}

        def set_date(self, date):
            pass

        def get_available_symbols(self):
            return list(self.test_quotes.keys())

        async def search_stocks(self, query):
            """Mock search_stocks method."""
            # Simple mock implementation that matches symbols containing query
            query_upper = query.upper()
            results = []
            for symbol in self.test_quotes.keys():
                if query_upper in symbol:
                    results.append(
                        {
                            "symbol": symbol,
                            "name": f"{symbol} Company",
                            "tradeable": True,
                        }
                    )
            return {"query": query, "results": results, "total_count": len(results)}

        async def get_price_history(self, symbol, period="1year", interval="1day"):
            """Mock price history method."""
            return {
                "symbol": symbol.upper(),
                "prices": [
                    {
                        "date": "2024-01-01",
                        "open": 100.0,
                        "high": 105.0,
                        "low": 98.0,
                        "close": 102.0,
                        "volume": 1000000,
                    },
                    {
                        "date": "2024-01-02",
                        "open": 102.0,
                        "high": 108.0,
                        "low": 101.0,
                        "close": 106.0,
                        "volume": 1200000,
                    },
                ],
                "period": period,
                "interval": interval,
            }

        async def get_stock_info(self, symbol):
            """Mock stock info method."""
            return {
                "symbol": symbol.upper(),
                "name": f"Mock Company {symbol}",
                "market_cap": 1000000000,
                "pe_ratio": 20.5,
                "dividend_yield": 2.1,
                "sector": "Technology",
            }

        async def search_stocks(self, query, limit=10):
            """Mock stock search method."""
            # Return symbols that contain the query
            matches = [
                symbol for symbol in self.test_quotes.keys() if query.upper() in symbol
            ]
            results = [
                {"symbol": symbol, "name": f"Mock Company {symbol}"}
                for symbol in matches[:limit]
            ]

            response = {"query": query, "results": results, "total_count": len(results)}

            if not results:
                response["message"] = f"No stocks found matching query: {query}"

            return response

    adapter = MockTestQuoteAdapter()
    return TradingService(quote_adapter=adapter)


@pytest_asyncio.fixture(scope="session")
async def robinhood_session():
    """Create authenticated Robinhood session for live tests (session-scoped)."""
    import asyncio
    import os

    from dotenv import load_dotenv

    from app.auth.session_manager import get_session_manager
    from app.core.logging import logger

    # Load environment variables from .env file
    load_dotenv()

    # Load credentials from .env
    username = os.getenv("ROBINHOOD_USERNAME")
    password = os.getenv("ROBINHOOD_PASSWORD")

    if not username or not password:
        pytest.skip("Robinhood credentials not available in .env")

    # Get the session manager and set credentials
    session_manager = get_session_manager()
    session_manager.set_credentials(username, password)

    try:
        # Authenticate once for the entire test session
        authenticated = await session_manager.ensure_authenticated()
        if not authenticated:
            pytest.skip("Failed to authenticate with Robinhood")

        logger.info("Robinhood session authenticated successfully")
        yield session_manager

    finally:
        # Cleanup: logout to avoid leaving sessions open
        try:
            import robin_stocks.robinhood as rh

            await asyncio.get_event_loop().run_in_executor(None, rh.logout)
            logger.info("Robinhood session logged out")
        except Exception as e:
            logger.warning(f"Error during logout: {e}")


@pytest_asyncio.fixture
async def trading_service_robinhood(robinhood_session):
    """Create TradingService with authenticated Robinhood adapter for live tests."""
    from app.adapters.robinhood import RobinhoodAdapter
    from app.services.trading_service import TradingService

    # Create adapter that will use the already authenticated session
    adapter = RobinhoodAdapter()
    return TradingService(quote_adapter=adapter)
