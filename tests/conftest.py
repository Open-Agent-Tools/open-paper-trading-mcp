import os
import pytest
from fastapi.testclient import TestClient

# Set the TESTING environment variable BEFORE importing the app
os.environ["TESTING"] = "True"

from app.main import app
from app.storage.database import get_db, SessionLocal, engine
from app.models.database.base import Base

@pytest.fixture(scope="function")
def db_session():
    """Create a new database session for a test and handle setup/teardown."""
    Base.metadata.create_all(bind=engine)
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
        Base.metadata.drop_all(bind=engine)

@pytest.fixture
def client(db_session) -> TestClient:
    """Create a test client that uses the test database session."""
    
    def override_get_db():
        try:
            yield db_session
        finally:
            db_session.close()

    app.dependency_overrides[get_db] = override_get_db
    return TestClient(app)

@pytest.fixture
def auth_headers() -> dict[str, str]:
    """Create authentication headers for testing."""
    return {"Authorization": "Bearer testuser"}

@pytest.fixture
def mock_trading_service(mocker):
    """Mock the trading service."""
    mock_service = mocker.patch("app.services.trading_service.trading_service")
    return mock_service
