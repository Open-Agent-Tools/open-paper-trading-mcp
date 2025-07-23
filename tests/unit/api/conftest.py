"""
Comprehensive fixtures and mocking utilities for API endpoint tests.

This module provides:
- Common fixtures for API testing
- Mock data factories
- Testing utilities for async endpoints
- Authentication helpers
- Database session mocking
- Service layer mocking utilities
"""

from datetime import date, datetime
from typing import Any
from unittest.mock import MagicMock

import pytest
from httpx import AsyncClient

from app.models.quotes import OptionQuote
from app.schemas.orders import Order, OrderCondition, OrderStatus, OrderType
from app.schemas.positions import Portfolio, PortfolioSummary, Position
from app.schemas.trading import StockQuote
from app.services.auth_service import AuthService
from app.services.trading_service import TradingService


class MockDataFactory:
    """Factory class for creating mock data objects."""

    @staticmethod
    def create_stock_quote(
        symbol: str = "AAPL", price: float = 155.0, **kwargs
    ) -> StockQuote:
        """Create a mock StockQuote object."""
        defaults = {
            "bid": price - 0.05,
            "ask": price + 0.05,
            "volume": 1000000,
            "quote_date": datetime(2023, 6, 15, 15, 30),
        }
        defaults.update(kwargs)

        return StockQuote(symbol=symbol, price=price, **defaults)

    @staticmethod
    def create_option_quote(
        symbol: str = "AAPL_230616C00150000", price: float = 5.25, **kwargs
    ) -> OptionQuote:
        """Create a mock OptionQuote object."""
        defaults = {
            "bid": price - 0.05,
            "ask": price + 0.05,
            "volume": 1000,
            "quote_date": datetime(2023, 6, 15, 15, 30),
            "delta": 0.65,
            "gamma": 0.03,
            "theta": -0.02,
            "vega": 0.15,
            "rho": 0.08,
            "iv": 0.25,
            "underlying_price": 155.0,
        }
        defaults.update(kwargs)

        return OptionQuote(symbol=symbol, price=price, **defaults)

    @staticmethod
    def create_order(
        order_id: str = "order_123",
        symbol: str = "AAPL",
        order_type: OrderType = OrderType.BUY,
        quantity: int = 100,
        **kwargs,
    ) -> Order:
        """Create a mock Order object."""
        defaults = {
            "price": 155.0,
            "condition": OrderCondition.LIMIT,
            "status": OrderStatus.PENDING,
            "created_at": datetime.utcnow(),
        }
        defaults.update(kwargs)

        return Order(
            id=order_id,
            symbol=symbol,
            order_type=order_type,
            quantity=quantity,
            **defaults,
        )

    @staticmethod
    def create_position(
        symbol: str = "AAPL", quantity: int = 100, **kwargs
    ) -> Position:
        """Create a mock Position object."""
        defaults = {
            "average_price": 150.0,
            "current_price": 155.0,
            "market_value": 15500.0,
            "unrealized_pnl": 500.0,
            "realized_pnl": 0.0,
        }
        defaults.update(kwargs)

        return Position(symbol=symbol, quantity=quantity, **defaults)

    @staticmethod
    def create_portfolio(
        cash_balance: float = 10000.0, positions: list[Position] | None = None, **kwargs
    ) -> Portfolio:
        """Create a mock Portfolio object."""
        if positions is None:
            positions = [MockDataFactory.create_position()]

        market_value = sum(pos.market_value for pos in positions)
        total_value = cash_balance + market_value

        defaults = {"market_value": market_value, "total_value": total_value}
        defaults.update(kwargs)

        return Portfolio(cash_balance=cash_balance, positions=positions, **defaults)

    @staticmethod
    def create_portfolio_summary(**kwargs) -> PortfolioSummary:
        """Create a mock PortfolioSummary object."""
        defaults = {
            "cash_balance": 10000.0,
            "market_value": 15500.0,
            "total_value": 25500.0,
            "day_change": 250.0,
            "day_change_percent": 1.0,
            "total_gain_loss": 500.0,
            "total_gain_loss_percent": 2.0,
            "position_count": 1,
        }
        defaults.update(kwargs)

        return PortfolioSummary(**defaults)

    @staticmethod
    def create_options_chain_response(
        underlying_symbol: str = "AAPL", **kwargs
    ) -> dict[str, Any]:
        """Create mock options chain data."""
        defaults = {
            "underlying_price": 155.0,
            "chains": {
                "2023-06-16": {
                    "calls": [
                        {
                            "symbol": "AAPL_230616C00150000",
                            "strike": 150.0,
                            "bid": 5.20,
                            "ask": 5.30,
                            "delta": 0.65,
                        }
                    ],
                    "puts": [
                        {
                            "symbol": "AAPL_230616P00150000",
                            "strike": 150.0,
                            "bid": 2.10,
                            "ask": 2.20,
                            "delta": -0.35,
                        }
                    ],
                }
            },
            "expiration_dates": ["2023-06-16"],
            "data_source": "test",
            "cached": False,
        }
        defaults.update(kwargs)

        return {"underlying_symbol": underlying_symbol, **defaults}

    @staticmethod
    def create_market_data_response(
        symbol: str = "AAPL", data_type: str = "price", **kwargs
    ) -> dict[str, Any]:
        """Create mock market data response."""
        if data_type == "price":
            defaults: dict[str, Any] = {
                "price": 155.0,
                "change": 2.5,
                "change_percent": 1.64,
                "volume": 50000000,
                "market_cap": 2500000000000,
            }
        elif data_type == "info":
            defaults = {
                "name": f"{symbol} Inc.",
                "sector": "Technology", 
                "industry": "Consumer Electronics",
                "pe_ratio": 28.5,
                "dividend_yield": 0.0055,
            }
        elif data_type == "history":
            defaults = {
                "period": "week",
                "data": [
                    {"date": "2023-06-12", "close": 150.0},
                    {"date": "2023-06-13", "close": 153.0},
                    {"date": "2023-06-14", "close": 155.5},
                ],
            }
        elif data_type == "news":
            defaults = {
                "articles": [
                    {
                        "title": f"{symbol} Reports Strong Earnings",
                        "url": "https://example.com/news/1", 
                        "published_at": "2023-06-15T14:30:00Z",
                        "source": "MarketWatch",
                    }
                ],
                "count": 1,
            }
        else:
            defaults = {}

        defaults.update(kwargs)

        return {"symbol": symbol, **defaults}

    @staticmethod
    def create_greeks_response(
        symbol: str = "AAPL_230616C00150000", **kwargs
    ) -> dict[str, Any]:
        """Create mock Greeks response."""
        defaults = {
            "underlying_symbol": "AAPL",
            "strike": 150.0,
            "expiration": "2023-06-16",
            "delta": 0.65,
            "gamma": 0.03,
            "theta": -0.02,
            "vega": 0.15,
            "rho": 0.08,
            "implied_volatility": 0.25,
        }
        defaults.update(kwargs)

        return {"symbol": symbol, **defaults}


class MockServiceFactory:
    """Factory class for creating mock service objects."""

    @staticmethod
    def create_mock_trading_service() -> MagicMock:
        """Create a mock TradingService with common methods."""
        mock_service = MagicMock(spec=TradingService)

        # Configure common return values
        mock_service.get_portfolio.return_value = MockDataFactory.create_portfolio()
        mock_service.get_portfolio_summary.return_value = (
            MockDataFactory.create_portfolio_summary()
        )
        mock_service.get_positions.return_value = [MockDataFactory.create_position()]
        mock_service.get_orders.return_value = [MockDataFactory.create_order()]
        mock_service.get_quote.return_value = MockDataFactory.create_stock_quote()

        # Configure market data methods
        mock_service.get_stock_price.return_value = (
            MockDataFactory.create_market_data_response(data_type="price")
        )
        mock_service.get_stock_info.return_value = (
            MockDataFactory.create_market_data_response(data_type="info")
        )
        mock_service.get_price_history.return_value = (
            MockDataFactory.create_market_data_response(data_type="history")
        )
        mock_service.get_stock_news.return_value = (
            MockDataFactory.create_market_data_response(data_type="news")
        )

        # Configure options methods
        mock_service.get_formatted_options_chain.return_value = (
            MockDataFactory.create_options_chain_response()
        )
        mock_service.get_expiration_dates.return_value = [
            date(2023, 6, 16),
            date(2023, 6, 23),
        ]
        mock_service.get_option_greeks_response.return_value = (
            MockDataFactory.create_greeks_response()
        )

        return mock_service

    @staticmethod
    def create_mock_auth_service() -> MagicMock:
        """Create a mock AuthService with common methods."""
        mock_service = MagicMock(spec=AuthService)

        # Configure common return values
        mock_service.authenticate_user.return_value = {"username": "testuser"}
        mock_service.access_token_expire_minutes = 30
        mock_service.create_access_token.return_value = "fake-jwt-token"
        mock_service.get_current_user.return_value = {
            "username": "testuser",
            "email": "test@example.com",
            "full_name": "Test User",
        }

        return mock_service


@pytest.fixture
def mock_data_factory():
    """Provide MockDataFactory instance."""
    return MockDataFactory


@pytest.fixture
def mock_service_factory():
    """Provide MockServiceFactory instance."""
    return MockServiceFactory


@pytest.fixture
def mock_trading_service():
    """Create a mock TradingService instance."""
    return MockServiceFactory.create_mock_trading_service()


@pytest.fixture
def mock_auth_service():
    """Create a mock AuthService instance."""
    return MockServiceFactory.create_mock_auth_service()


@pytest.fixture
async def async_test_client(client):
    """Create an async test client for testing async endpoints."""
    async with AsyncClient(app=client.app, base_url="http://test") as ac:
        yield ac


@pytest.fixture
def auth_headers():
    """Create authentication headers for testing."""
    return {"Authorization": "Bearer fake-jwt-token"}


@pytest.fixture
def sample_stock_symbols():
    """Provide sample stock symbols for testing."""
    return [
        "AAPL",
        "GOOGL",
        "MSFT",
        "TSLA",
        "AMZN",
        "NVDA",
        "META",
        "BRK.A",
        "SPY",
        "QQQ",
    ]


@pytest.fixture
def sample_option_symbols():
    """Provide sample option symbols for testing."""
    return [
        "AAPL_230616C00150000",  # AAPL call
        "AAPL_230616P00150000",  # AAPL put
        "SPY_230616C00400000",  # SPY call
        "QQQ_230616P00350000",  # QQQ put
        "TSLA_230616C00250000",  # TSLA call
    ]


@pytest.fixture
def sample_order_data():
    """Provide sample order data for testing."""
    return {
        "buy_order": {
            "symbol": "AAPL",
            "order_type": "buy",
            "quantity": 100,
            "price": 155.0,
            "condition": "limit",
        },
        "sell_order": {
            "symbol": "AAPL",
            "order_type": "sell",
            "quantity": 50,
            "price": 160.0,
            "condition": "limit",
        },
        "market_order": {
            "symbol": "MSFT",
            "order_type": "buy",
            "quantity": 200,
            "condition": "market",
        },
        "multi_leg_order": {
            "legs": [
                {
                    "asset": "AAPL_230616C00150000",
                    "order_type": "buy_to_open",
                    "quantity": 1,
                    "price": 5.25,
                },
                {
                    "asset": "AAPL_230616C00160000",
                    "order_type": "sell_to_open",
                    "quantity": 1,
                    "price": 2.50,
                },
            ],
            "condition": "limit",
            "limit_price": -2.75,
        },
    }


@pytest.fixture
def sample_portfolio_data(mock_data_factory):
    """Provide sample portfolio data for testing."""
    return {
        "simple_portfolio": mock_data_factory.create_portfolio(
            cash_balance=10000.0,
            positions=[
                mock_data_factory.create_position("AAPL", 100, current_price=155.0),
                mock_data_factory.create_position("GOOGL", 50, current_price=2500.0),
            ],
        ),
        "empty_portfolio": mock_data_factory.create_portfolio(
            cash_balance=10000.0, positions=[]
        ),
        "large_portfolio": mock_data_factory.create_portfolio(
            cash_balance=100000.0,
            positions=[
                mock_data_factory.create_position(
                    symbol, 100 + i * 10, current_price=150.0 + i * 5
                )
                for i, symbol in enumerate(["AAPL", "GOOGL", "MSFT", "TSLA", "AMZN"])
            ],
        ),
    }


@pytest.fixture
def sample_market_data():
    """Provide sample market data responses."""
    return {
        "stock_price": MockDataFactory.create_market_data_response("AAPL", "price"),
        "stock_info": MockDataFactory.create_market_data_response("AAPL", "info"),
        "price_history": MockDataFactory.create_market_data_response("AAPL", "history"),
        "stock_news": MockDataFactory.create_market_data_response("AAPL", "news"),
        "top_movers": {
            "gainers": [
                {
                    "symbol": "TSLA",
                    "price": 250.0,
                    "change": 25.0,
                    "change_percent": 11.11,
                },
                {
                    "symbol": "NVDA",
                    "price": 400.0,
                    "change": 35.0,
                    "change_percent": 9.59,
                },
            ],
            "losers": [
                {
                    "symbol": "META",
                    "price": 200.0,
                    "change": -20.0,
                    "change_percent": -9.09,
                }
            ],
            "most_active": [{"symbol": "AAPL", "price": 155.0, "volume": 100000000}],
        },
        "search_results": {
            "query": "AAPL",
            "results": [
                {
                    "symbol": "AAPL",
                    "name": "Apple Inc.",
                    "type": "equity",
                    "match_score": 1.0,
                }
            ],
            "count": 1,
        },
    }


@pytest.fixture
def sample_options_data():
    """Provide sample options data."""
    return {
        "options_chain": MockDataFactory.create_options_chain_response("AAPL"),
        "greeks": MockDataFactory.create_greeks_response("AAPL_230616C00150000"),
        "expiration_dates": [date(2023, 6, 16), date(2023, 6, 23), date(2023, 6, 30)],
        "strategy_analysis": {
            "recognized_strategies": [
                {
                    "strategy_type": "covered_call",
                    "max_profit": 500.0,
                    "max_loss": -15000.0,
                    "recommendation": "Hold to expiration",
                }
            ],
            "portfolio_greeks": {"total_delta": 150.0, "total_theta": -25.5},
            "recommendations": ["Consider closing before expiration"],
        },
    }


@pytest.fixture
def health_check_responses():
    """Provide sample health check responses."""
    return {
        "healthy": {
            "status": "healthy",
            "response_time_ms": 5.0,
            "message": "Service is operational",
        },
        "degraded": {
            "status": "degraded",
            "response_time_ms": 500.0,
            "message": "Service is slow but functional",
        },
        "unhealthy": {
            "status": "unhealthy",
            "response_time_ms": 2000.0,
            "message": "Service is not responding",
        },
    }


@pytest.fixture
def error_responses():
    """Provide sample error responses for testing."""
    return {
        "not_found": {"error": "Resource not found"},
        "validation_error": {"error": "Invalid input data"},
        "server_error": {"error": "Internal server error"},
        "timeout_error": {"error": "Request timeout"},
        "rate_limit_error": {"error": "Rate limit exceeded"},
    }


class APITestUtils:
    """Utility class for API testing helpers."""

    @staticmethod
    def assert_error_response(
        response, expected_status: int, expected_message: str | None = None
    ):
        """Assert that response is an error with expected status and message."""
        assert response.status_code == expected_status

        if expected_message:
            data = response.json()
            assert "detail" in data
            assert expected_message in data["detail"]

    @staticmethod
    def assert_success_response(response, expected_fields: list[str] | None = None):
        """Assert that response is successful and contains expected fields."""
        assert response.status_code == 200

        if expected_fields:
            data = response.json()
            for field in expected_fields:
                assert field in data

    @staticmethod
    def assert_pagination_response(response, min_count: int = 0):
        """Assert that response contains pagination information."""
        assert response.status_code == 200
        data = response.json()

        if isinstance(data, list):
            assert len(data) >= min_count
        elif isinstance(data, dict):
            if "count" in data:
                assert data["count"] >= min_count
            if "results" in data:
                assert len(data["results"]) >= min_count


@pytest.fixture
def api_test_utils():
    """Provide APITestUtils instance."""
    return APITestUtils


# Custom pytest markers for API tests - these would be defined in pytest.ini or pyproject.toml
# pytest.mark.auth = pytest.mark.auth
# pytest.mark.health = pytest.mark.health 
# pytest.mark.portfolio = pytest.mark.portfolio
# pytest.mark.trading = pytest.mark.trading
# pytest.mark.market_data = pytest.mark.market_data
# pytest.mark.options = pytest.mark.options
# pytest.mark.slow = pytest.mark.slow
# pytest.mark.integration = pytest.mark.integration
