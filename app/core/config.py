import logging
import os

from pydantic import field_validator
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

    # CORS
    BACKEND_CORS_ORIGINS: list[str] = ["http://localhost:3000", "http://localhost:2080"]

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

    # Quote Adapter Configuration
    QUOTE_ADAPTER_TYPE: str = os.getenv("QUOTE_ADAPTER_TYPE", "test")

    # Test Data Configuration
    TEST_SCENARIO: str = os.getenv("TEST_SCENARIO", "default")
    TEST_DATE: str = os.getenv("TEST_DATE", "2017-03-24")

    # Robinhood Configuration
    ROBINHOOD_USERNAME: str = os.getenv("ROBINHOOD_USERNAME", "")
    ROBINHOOD_PASSWORD: str = os.getenv("ROBINHOOD_PASSWORD", "")
    ROBINHOOD_TOKEN_PATH: str = os.getenv("ROBINHOOD_TOKEN_PATH", "/app/.tokens")

    @field_validator("BACKEND_CORS_ORIGINS", mode="before")
    @classmethod
    def assemble_cors_origins(cls, v: str | list[str]) -> list[str] | str:
        if isinstance(v, str) and not v.startswith("["):
            return [i.strip() for i in v.split(",")]
        elif isinstance(v, list | str):
            return v
        raise ValueError(v)


settings = Settings()
