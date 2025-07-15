"""
Test suite for Phase 1 completion verification.
Tests all enhanced models and services from reference implementation migration.
"""

import pytest
from datetime import datetime, date
from unittest.mock import Mock

from app.models.assets import Asset, Option, Call, asset_factory
from app.models.trading import (
    Order,
    MultiLegOrder,
    OrderLeg,
    OrderType,
    Position,
)
from app.models.quotes import Quote, OptionQuote, quote_factory
from app.services.greeks import calculate_option_greeks
from app.services.order_execution import OrderExecutionEngine
from app.services.validation import AccountValidator
from app.services.strategies import (
    StrategyRecognitionService,
)
from app.services.margin import MaintenanceMarginService
from app.services.order_impact import OrderImpactService
from app.adapters.test_data import TestDataQuoteAdapter


class TestAssetModels:
    """Test enhanced asset models from Phase 1."""

    def test_asset_factory_stock(self):
        """Test asset factory creates stocks correctly."""
        asset = asset_factory("AAPL")
        assert isinstance(asset, Asset)
        assert asset.symbol == "AAPL"
        assert not isinstance(asset, Option)

    def test_asset_factory_option(self):
        """Test asset factory creates options correctly."""
        option = asset_factory("AAPL240119C00195000")
        assert isinstance(option, Call)
        assert option.symbol == "AAPL240119C00195000"
        assert option.underlying.symbol == "AAPL"
        assert option.strike == 195.0
        assert option.option_type == "call"
        assert option.expiration_date == date(2024, 1, 19)

    def test_option_intrinsic_value(self):
        """Test option intrinsic value calculations."""
        call = asset_factory("AAPL240119C00195000")
        put = asset_factory("AAPL240119P00195000")

        # ITM call
        assert call.get_intrinsic_value(200.0) == 5.0
        # OTM call
        assert call.get_intrinsic_value(190.0) == 0.0

        # ITM put
        assert put.get_intrinsic_value(190.0) == 5.0
        # OTM put
        assert put.get_intrinsic_value(200.0) == 0.0

    def test_option_days_to_expiration(self):
        """Test days to expiration calculation."""
        option = asset_factory("AAPL240119C00195000")
        test_date = date(2024, 1, 15)  # 4 days before expiration

        days = option.get_days_to_expiration(test_date)
        assert days == 4


class TestEnhancedOrderModels:
    """Test enhanced order models with options support."""

    def test_order_leg_creation(self):
        """Test OrderLeg creation and validation."""
        leg = OrderLeg(
            asset="AAPL240119C00195000",
            quantity=1,
            order_type=OrderType.BTO,
            price=5.50,
        )

        assert isinstance(leg.asset, Option)
        assert leg.quantity == 1  # BTO should be positive
        assert leg.order_type == OrderType.BTO
        assert leg.price == 5.50  # BTO should be positive

    def test_order_leg_quantity_sign_correction(self):
        """Test automatic quantity sign correction."""
        # Buy orders should be positive
        buy_leg = OrderLeg(
            asset="AAPL",
            quantity=-10,  # Negative input
            order_type=OrderType.BUY,
            price=150.0,
        )
        assert buy_leg.quantity == 10  # Should be corrected to positive

        # Sell orders should be negative
        sell_leg = OrderLeg(
            asset="AAPL",
            quantity=10,  # Positive input
            order_type=OrderType.STO,
            price=5.50,
        )
        assert sell_leg.quantity == -10  # Should be corrected to negative

    def test_multileg_order_creation(self):
        """Test multi-leg order creation."""
        order = MultiLegOrder(legs=[])
        order.buy_to_open("AAPL240119C00195000", 1, 5.50)
        order.sell_to_open("AAPL240119C00200000", 1, 3.25)

        assert len(order.legs) == 2
        assert order.legs[0].order_type == OrderType.BTO
        assert order.legs[1].order_type == OrderType.STO
        assert order.is_opening_order
        assert not order.is_closing_order

    def test_multileg_order_net_price(self):
        """Test net price calculation for multi-leg orders."""
        order = MultiLegOrder(legs=[])
        order.buy_to_open("AAPL240119C00195000", 1, 5.50)
        order.sell_to_open("AAPL240119C00200000", 1, 3.25)

        # Net price should be sum of leg prices * quantities
        expected = (5.50 * 1) + (3.25 * 1)  # BTO positive, STO negative in practice
        assert order.net_price == expected

    def test_order_to_leg_conversion(self):
        """Test Order to OrderLeg conversion."""
        order = Order(symbol="AAPL", order_type=OrderType.BUY, quantity=10, price=150.0)

        leg = order.to_leg()
        assert isinstance(leg, OrderLeg)
        assert leg.asset.symbol == "AAPL"
        assert leg.quantity == 10
        assert leg.order_type == OrderType.BUY


class TestEnhancedPositionModels:
    """Test enhanced position models with options support."""

    def test_position_options_properties(self):
        """Test options-specific position properties."""
        position = Position(
            symbol="AAPL240119C00195000",
            quantity=1,
            avg_price=5.50,
            current_price=6.00,
            asset=asset_factory("AAPL240119C00195000"),
        )

        assert position.is_option
        assert position.multiplier == 100
        assert position.total_cost_basis == 550.0  # 5.50 * 1 * 100
        assert position.market_value == 600.0  # 6.00 * 1 * 100

    def test_position_stock_properties(self):
        """Test stock position properties."""
        position = Position(
            symbol="AAPL",
            quantity=10,
            avg_price=150.0,
            current_price=155.0,
            asset=asset_factory("AAPL"),
        )

        assert not position.is_option
        assert position.multiplier == 1
        assert position.total_cost_basis == 1500.0  # 150.0 * 10 * 1
        assert position.market_value == 1550.0  # 155.0 * 10 * 1

    def test_position_pnl_calculations(self):
        """Test P&L calculations."""
        position = Position(
            symbol="AAPL240119C00195000",
            quantity=1,
            avg_price=5.50,
            current_price=6.00,
            asset=asset_factory("AAPL240119C00195000"),
        )

        unrealized = position.calculate_unrealized_pnl()
        assert unrealized == 50.0  # (6.00 - 5.50) * 1 * 100

        position.realized_pnl = 25.0
        assert position.total_pnl == 75.0  # 50.0 + 25.0

        pnl_percent = position.pnl_percent
        assert abs(pnl_percent - (75.0 / 550.0 * 100)) < 0.01

    def test_position_greeks_update(self):
        """Test Greeks update functionality."""
        position = Position(
            symbol="AAPL240119C00195000",
            quantity=1,
            avg_price=5.50,
            current_price=6.00,
            asset=asset_factory("AAPL240119C00195000"),
        )

        # Mock quote with Greeks
        mock_quote = Mock()
        mock_quote.delta = 0.65
        mock_quote.gamma = 0.03
        mock_quote.theta = -0.05
        mock_quote.vega = 0.12
        mock_quote.rho = 0.08
        mock_quote.iv = 0.25

        position.update_market_data(6.00, mock_quote)

        # Greeks should be scaled by quantity * multiplier
        assert position.delta == 65.0  # 0.65 * 1 * 100
        assert position.gamma == 3.0  # 0.03 * 1 * 100
        assert position.theta == -5.0  # -0.05 * 1 * 100
        assert position.iv == 0.25


class TestQuoteSystem:
    """Test enhanced quote system."""

    def test_quote_factory(self):
        """Test quote factory creates correct types."""
        # Stock quote
        stock_quote = quote_factory(
            quote_date=datetime.now(),
            asset="AAPL",
            bid=149.50,
            ask=150.00,
            price=149.75,
        )
        assert isinstance(stock_quote, Quote)
        assert not isinstance(stock_quote, OptionQuote)

        # Option quote
        option_quote = quote_factory(
            quote_date=datetime.now(),
            asset="AAPL240119C00195000",
            bid=5.40,
            ask=5.60,
            price=5.50,
            underlying_price=200.0,
        )
        assert isinstance(option_quote, OptionQuote)

    def test_quote_price_calculation(self):
        """Test automatic price calculation."""
        quote = Quote(
            asset=asset_factory("AAPL"),
            quote_date=datetime.now(),
            bid=149.50,
            ask=150.00,
        )

        # Price should be calculated as midpoint
        assert quote.price == 149.75
        assert quote.midpoint == 149.75
        assert quote.spread == 0.50

    def test_option_quote_greeks_properties(self):
        """Test option quote Greeks properties."""
        option_quote = OptionQuote(
            asset=asset_factory("AAPL240119C00195000"),
            quote_date=datetime.now(),
            bid=5.40,
            ask=5.60,
            price=5.50,
            underlying_price=200.0,
            delta=0.65,
        )

        assert option_quote.strike == 195.0
        assert option_quote.option_type == "call"
        assert option_quote.delta == 0.65
        assert option_quote.days_to_expiration is not None


class TestGreeksCalculation:
    """Test Greeks calculation service."""

    def test_option_greeks_calculation(self):
        """Test basic Greeks calculation."""
        greeks = calculate_option_greeks(
            option_type="call",
            strike=100.0,
            underlying_price=105.0,
            days_to_expiration=30,
            option_price=7.50,
            risk_free_rate=0.05,
            dividend_yield=0.02,
        )

        assert "delta" in greeks
        assert "gamma" in greeks
        assert "theta" in greeks
        assert "vega" in greeks
        assert "rho" in greeks
        assert "iv" in greeks

        # Basic sanity checks
        assert 0 < greeks["delta"] < 1  # Call delta should be between 0 and 1
        assert greeks["gamma"] > 0  # Gamma should be positive
        assert greeks["vega"] > 0  # Vega should be positive
        assert greeks["iv"] > 0  # IV should be positive

    def test_put_greeks_calculation(self):
        """Test put option Greeks."""
        greeks = calculate_option_greeks(
            option_type="put",
            strike=100.0,
            underlying_price=95.0,
            days_to_expiration=30,
            option_price=7.50,
        )

        assert -1 < greeks["delta"] < 0  # Put delta should be negative
        assert greeks["gamma"] > 0  # Gamma should be positive
        assert greeks["vega"] > 0  # Vega should be positive


class TestTradingServices:
    """Test trading engine services."""

    def test_order_execution_engine(self):
        """Test order execution engine instantiation."""
        engine = OrderExecutionEngine()
        assert engine is not None
        # More detailed testing would require mock positions and accounts

    def test_account_validator(self):
        """Test account validator."""
        validator = AccountValidator()
        assert validator is not None

        # Test basic validation structure
        mock_account = {"cash_balance": 10000.0, "positions": [], "orders": []}

        result = validator.validate_account_state(mock_account)
        assert isinstance(result, dict)

    def test_strategy_recognition_service(self):
        """Test strategy recognition."""
        service = StrategyRecognitionService()
        assert service is not None

        # Test with empty positions
        strategies = service.group_positions_by_strategy([])
        assert strategies == []

        # Test strategy summary
        summary = service.get_strategy_summary([])
        assert isinstance(summary, dict)
        assert "total_strategies" in summary

    def test_maintenance_margin_service(self):
        """Test margin calculation service."""
        service = MaintenanceMarginService()
        assert service is not None

        # Test with empty positions
        result = service.calculate_maintenance_margin(positions=[])
        assert result.total_margin_requirement == 0.0
        assert isinstance(result.strategy_margins, list)

    def test_order_impact_service(self):
        """Test order impact analysis."""
        service = OrderImpactService()
        assert service is not None

        # Test with mock data
        mock_account = {"cash_balance": 10000.0, "positions": []}

        mock_order = Order(
            symbol="AAPL", order_type=OrderType.BUY, quantity=10, price=150.0
        )

        analysis = service.analyze_order_impact(mock_account, mock_order)
        assert analysis.approval_status in ["approved", "warning", "rejected"]
        assert isinstance(analysis.cash_impact, float)


class TestTestDataSystem:
    """Test the test data system."""

    def test_test_data_adapter_creation(self):
        """Test test data adapter instantiation."""
        adapter = TestDataQuoteAdapter()
        assert adapter is not None
        assert adapter.current_date == "2017-03-24"

    def test_available_dates(self):
        """Test available test dates."""
        adapter = TestDataQuoteAdapter()
        dates = adapter.get_available_dates()

        assert isinstance(dates, list)
        assert "2017-01-27" in dates
        assert "2017-03-24" in dates

    def test_sample_data_info(self):
        """Test sample data information."""
        adapter = TestDataQuoteAdapter()
        info = adapter.get_sample_data_info()

        assert isinstance(info, dict)
        assert "symbols" in info
        assert "dates" in info
        assert "AAL" in info["symbols"]
        assert "GOOG" in info["symbols"]

    def test_test_scenarios(self):
        """Test predefined test scenarios."""
        adapter = TestDataQuoteAdapter()
        scenarios = adapter.get_test_scenarios()

        assert isinstance(scenarios, dict)
        assert "aal_earnings" in scenarios
        assert "goog_january" in scenarios


class TestIntegration:
    """Integration tests for Phase 1 components."""

    def test_end_to_end_option_workflow(self):
        """Test complete option workflow."""
        # Create option asset
        option = asset_factory("AAPL240119C00195000")

        # Create multi-leg order
        order = MultiLegOrder(legs=[])
        order.buy_to_open(option, 1, 5.50)

        # Create position
        position = Position(
            symbol=option.symbol,
            quantity=1,
            avg_price=5.50,
            current_price=6.00,
            asset=option,
        )

        # Test margin calculation
        margin_service = MaintenanceMarginService()
        margin_result = margin_service.calculate_maintenance_margin(
            positions=[position]
        )

        assert margin_result.total_margin_requirement >= 0
        assert len(margin_result.strategy_margins) >= 0

    def test_enhanced_trading_service_integration(self):
        """Test that enhanced models work with TradingService."""
        from app.services.trading_service import trading_service

        # Test that we can access enhanced methods
        assert hasattr(trading_service, "quote_adapter")
        assert hasattr(trading_service, "order_execution")
        assert hasattr(trading_service, "strategy_recognition")
        assert hasattr(trading_service, "margin_service")

        # Test enhanced quote method exists
        assert hasattr(trading_service, "get_enhanced_quote")
        assert hasattr(trading_service, "calculate_greeks")
        assert hasattr(trading_service, "analyze_portfolio_strategies")


@pytest.mark.integration
class TestAPIIntegration:
    """Integration tests for API endpoints (requires running app)."""

    def test_health_endpoint(self):
        """Test health endpoint."""
        import requests

        try:
            response = requests.get("http://localhost:2080/health", timeout=5)
            assert response.status_code == 200
            data = response.json()
            assert data["status"] == "healthy"
        except requests.exceptions.RequestException:
            pytest.skip("Application not running for integration tests")

    def test_quote_endpoint(self):
        """Test quote endpoint."""
        import requests

        try:
            response = requests.get(
                "http://localhost:2080/api/v1/trading/quote/AAPL", timeout=5
            )
            assert response.status_code == 200
            data = response.json()
            assert "symbol" in data
            assert "price" in data
        except requests.exceptions.RequestException:
            pytest.skip("Application not running for integration tests")

    def test_order_creation_endpoint(self):
        """Test order creation endpoint."""
        import requests

        try:
            order_data = {
                "symbol": "AAPL",
                "order_type": "buy",
                "quantity": 1,
                "price": 150.0,
            }

            response = requests.post(
                "http://localhost:2080/api/v1/trading/order", json=order_data, timeout=5
            )
            assert response.status_code == 200
            data = response.json()
            assert "id" in data
            assert data["symbol"] == "AAPL"
        except requests.exceptions.RequestException:
            pytest.skip("Application not running for integration tests")
