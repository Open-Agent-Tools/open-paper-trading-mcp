import logging
import os

from pydantic_settings import BaseSettings, SettingsConfigDict

# Configure logger
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env", case_sensitive=True, extra="ignore"
    )

    PROJECT_NAME: str = "Open Paper Trading MCP"
    API_V1_STR: str = "/api/v1"

    # CORS - simplified for Docker
    BACKEND_CORS_ORIGINS: str = "http://localhost:3000,http://localhost:2080"

    # Database
    DATABASE_URL: str = os.getenv(
        "DATABASE_URL",
        "postgresql+asyncpg://trading_user:trading_password@db:5432/trading_db",
    )

    # Redis
    REDIS_URL: str = "redis://localhost:6379"

    # Security
    SECRET_KEY: str = os.getenv(
        "SECRET_KEY", "your-secret-key-change-this-in-production"
    )
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 30

    # Environment
    ENVIRONMENT: str = os.getenv("ENVIRONMENT", "development")
    DEBUG: bool = os.getenv("DEBUG", "True").lower() == "true"
    LOG_LEVEL: str = os.getenv("LOG_LEVEL", "INFO")

    # MCP Server Configuration
    MCP_SERVER_PORT: int = int(os.getenv("MCP_SERVER_PORT", "2081"))
    MCP_SERVER_HOST: str = os.getenv("MCP_SERVER_HOST", "localhost")
    MCP_SERVER_NAME: str = "Open Paper Trading MCP"
    MCP_HTTP_PORT: int = int(os.getenv("MCP_HTTP_PORT", "2081"))
    MCP_HTTP_URL: str = os.getenv("MCP_HTTP_URL", "http://localhost:2081")

    # Quote Adapter Configuration
    QUOTE_ADAPTER_TYPE: str = os.getenv("QUOTE_ADAPTER_TYPE", "test")

    # Test Data Configuration
    TEST_SCENARIO: str = os.getenv("TEST_SCENARIO", "ui_testing")
    TEST_DATE: str = os.getenv("TEST_DATE", "2025-07-30")

    # Robinhood Configuration
    ROBINHOOD_USERNAME: str = os.getenv("ROBINHOOD_USERNAME", "")
    ROBINHOOD_PASSWORD: str = os.getenv("ROBINHOOD_PASSWORD", "")
    ROBINHOOD_TOKEN_PATH: str = os.getenv("ROBINHOOD_TOKEN_PATH", "/app/.tokens")

    def get_cors_origins(self) -> list[str]:
        """Convert CORS origins string to list."""
        if isinstance(self.BACKEND_CORS_ORIGINS, str):
            return [origin.strip() for origin in self.BACKEND_CORS_ORIGINS.split(",")]
        return self.BACKEND_CORS_ORIGINS


settings = Settings()
