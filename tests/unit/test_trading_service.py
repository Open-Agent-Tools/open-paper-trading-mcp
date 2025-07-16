import pytest
from unittest.mock import MagicMock, patch
from app.services.trading_service import TradingService
from app.models.trading import Portfolio
from app.models.trading import Position
from app.models.quotes import OptionsChain, OptionQuote
from app.models.assets import Option
from datetime import date, datetime
from app.schemas.orders import OrderType, OrderCondition, Order


@pytest.fixture
def trading_service():
    """Provides a TradingService instance with mocked dependencies."""
    service = TradingService()
    service.quote_adapter = MagicMock()
    return service


@patch("app.services.trading_service.aggregate_portfolio_greeks")
@patch("app.services.trading_service.analyze_advanced_strategy_pnl")
@patch("app.services.trading_service.detect_complex_strategies")
@patch("app.services.trading_service.get_portfolio_optimization_recommendations")
def test_analyze_portfolio_strategies(
    mock_get_recs,
    mock_detect_complex,
    mock_analyze_pnl,
    mock_agg_greeks,
    trading_service,
):
    """Test the comprehensive strategy analysis method."""
    # Arrange
    mock_positions = [Position(symbol="AAPL", quantity=10, avg_price=150.0)]
    mock_portfolio = Portfolio(
        cash_balance=100000.0,
        positions=mock_positions,
        total_value=101500.0,
        daily_pnl=500.0,
        total_pnl=500.0,
    )
    trading_service.get_portfolio = MagicMock(return_value=mock_portfolio)
    trading_service.get_enhanced_quote = MagicMock(return_value=MagicMock())

    mock_agg_greeks.return_value = MagicMock(
        delta=1,
        gamma=2,
        theta=3,
        vega=4,
        rho=5,
        delta_normalized=0.1,
        delta_dollars=100,
        theta_dollars=300,
    )
    mock_analyze_pnl.return_value = [
        MagicMock(
            strategy_type="test",
            strategy_name="Test Strategy",
            unrealized_pnl=100,
            realized_pnl=0,
            total_pnl=100,
            pnl_percent=10,
            cost_basis=1000,
            market_value=1100,
            days_held=10,
            annualized_return=365,
        )
    ]
    mock_detect_complex.return_value = [
        MagicMock(
            complex_type="iron_condor",
            underlying_symbol="AAPL",
            legs=[],
            net_credit=1.0,
            max_profit=100,
            max_loss=-100,
            breakeven_points=[1, 2],
        )
    ]
    mock_get_recs.return_value = ["recommendation1"]

    # Act
    result = trading_service.analyze_portfolio_strategies(
        include_greeks=True,
        include_pnl=True,
        include_complex_strategies=True,
        include_recommendations=True,
    )

    # Assert
    assert result is not None
    assert "portfolio_greeks" in result
    assert result["portfolio_greeks"]["delta"] == 1
    assert "strategy_pnl" in result
    assert result["strategy_pnl"][0]["total_pnl"] == 100
    assert "complex_strategies" in result
    assert result["complex_strategies"][0]["complex_type"] == "iron_condor"
    assert "recommendations" in result
    assert result["recommendations"][0] == "recommendation1"

    trading_service.get_portfolio.assert_called_once()
    trading_service.get_enhanced_quote.assert_called_with("AAPL")
    mock_agg_greeks.assert_called_once()
    mock_analyze_pnl.assert_called_once()
    mock_detect_complex.assert_called_once()
    mock_get_recs.assert_called_once()


def test_get_formatted_options_chain(trading_service):
    """Test the options chain formatting and filtering method."""
    # Arrange
    mock_option_asset_1 = Option(symbol="AAPL240119C00150000")
    mock_option_asset_2 = Option(symbol="AAPL240119P00150000")
    mock_chain = OptionsChain(
        underlying_symbol="AAPL",
        expiration_date=date(2024, 1, 19),
        underlying_price=150.0,
        calls=[
            OptionQuote(
                asset=mock_option_asset_1,
                quote_date=datetime.now(),
                price=1.0,
                strike=150.0,
            ),
        ],
        puts=[
            OptionQuote(
                asset=mock_option_asset_2,
                quote_date=datetime.now(),
                price=2.0,
                strike=150.0,
            ),
        ],
    )
    trading_service.get_options_chain = MagicMock(return_value=mock_chain)

    # Act
    result = trading_service.get_formatted_options_chain(
        "AAPL",
        expiration_date=date(2024, 1, 19),
        min_strike=140,
        max_strike=160,
        include_greeks=True,
    )

    # Assert
    assert result is not None
    assert result["underlying_symbol"] == "AAPL"
    assert len(result["calls"]) == 1
    assert len(result["puts"]) == 1
    assert result["calls"][0]["strike"] == 150.0
    assert "delta" in result["calls"][0]
    trading_service.get_options_chain.assert_called_once_with("AAPL", date(2024, 1, 19))


def test_create_multi_leg_order_from_request(trading_service):
    """Test creating a multi-leg order from a raw request."""
    # Arrange
    raw_legs = [
        {"symbol": "AAPL240119C00150000", "quantity": 1, "side": "buy"},
        {"symbol": "AAPL240119C00155000", "quantity": 1, "side": "sell"},
    ]
    trading_service.create_multi_leg_order = MagicMock(
        return_value=Order(
            id="123",
            symbol="AAPL_SPREAD",
            order_type=OrderType.BUY,
            quantity=1,
            price=1.0,
            condition=OrderCondition.LIMIT,
            status="pending",
        )
    )

    # Act
    order = trading_service.create_multi_leg_order_from_request(raw_legs, "limit", 2.50)

    # Assert
    assert order is not None
    assert order.id == "123"
    trading_service.create_multi_leg_order.assert_called_once()
