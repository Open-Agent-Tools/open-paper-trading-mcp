"""
Advanced test coverage for position schemas.

Tests position calculations, Greeks, options support, validation mixins,
portfolio calculations, and complex position scenarios.
"""

import pytest
from datetime import date, datetime
from unittest.mock import MagicMock
from pydantic import ValidationError

from app.models.assets import Stock, Option, Call, Put, asset_factory
from app.schemas.positions import Position, Portfolio, PortfolioSummary


class TestPositionSchema:
    """Test Position schema validation and functionality."""

    def test_position_creation_basic_stock(self):
        """Test creating basic stock position."""
        position = Position(
            symbol="AAPL",
            quantity=100,
            avg_price=150.0,
            current_price=155.0,
            unrealized_pnl=500.0
        )
        
        assert position.symbol == "AAPL"
        assert position.quantity == 100
        assert position.avg_price == 150.0
        assert position.current_price == 155.0
        assert position.unrealized_pnl == 500.0
        assert position.realized_pnl == 0.0

    def test_position_creation_with_defaults(self):
        """Test position creation with default values."""
        position = Position(
            symbol="GOOGL",
            quantity=50,
            avg_price=2800.0
        )
        
        assert position.symbol == "GOOGL"
        assert position.quantity == 50
        assert position.avg_price == 2800.0
        assert position.current_price is None
        assert position.unrealized_pnl is None
        assert position.realized_pnl == 0.0
        assert position.asset is None

    def test_position_symbol_validation_and_normalization(self):
        """Test symbol validation and normalization."""
        position = Position(
            symbol="aapl",
            quantity=100,
            avg_price=150.0
        )
        
        assert position.symbol == "AAPL"

    def test_position_symbol_validation_empty(self):
        """Test empty symbol validation."""
        with pytest.raises(ValidationError) as exc_info:
            Position(
                symbol="",
                quantity=100,
                avg_price=150.0
            )
        
        error = exc_info.value.errors()[0]
        assert "Symbol cannot be empty" in error["msg"]

    def test_position_with_option_fields(self):
        """Test position with options-specific fields."""
        position = Position(
            symbol="AAPL240119C00195000",
            quantity=10,
            avg_price=5.50,
            current_price=6.00,
            option_type="call",
            strike=195.0,
            expiration_date=date(2024, 1, 19),
            underlying_symbol="AAPL",
            delta=0.65,
            gamma=0.05,
            theta=-0.025,
            vega=0.12,
            rho=0.08,
            iv=0.25
        )
        
        assert position.option_type == "call"
        assert position.strike == 195.0
        assert position.expiration_date == date(2024, 1, 19)
        assert position.underlying_symbol == "AAPL"
        assert position.delta == 0.65
        assert position.gamma == 0.05
        assert position.theta == -0.025
        assert position.vega == 0.12
        assert position.rho == 0.08
        assert position.iv == 0.25

    def test_position_asset_normalization_from_string(self):
        """Test asset normalization from string."""
        position = Position(
            symbol="AAPL",
            quantity=100,
            avg_price=150.0,
            asset="AAPL"
        )
        
        assert position.asset is not None
        assert position.asset.symbol == "AAPL"
        assert isinstance(position.asset, Stock)

    def test_position_asset_normalization_option_string(self):
        """Test asset normalization from option string."""
        option_symbol = "AAPL240119C00195000"
        position = Position(
            symbol=option_symbol,
            quantity=10,
            avg_price=5.50,
            asset=option_symbol
        )
        
        assert position.asset is not None
        assert position.asset.symbol == option_symbol
        assert isinstance(position.asset, Option)


class TestPositionProperties:
    """Test Position computed properties."""

    def test_is_option_property_with_asset(self):
        """Test is_option property with Option asset."""
        option_asset = Option(
            symbol="AAPL240119C00195000",
            underlying=Stock(symbol="AAPL"),
            option_type="call",
            strike=195.0,
            expiration_date=date(2024, 1, 19)
        )
        
        position = Position(
            symbol="AAPL240119C00195000",
            quantity=10,
            avg_price=5.50,
            asset=option_asset
        )
        
        assert position.is_option is True

    def test_is_option_property_with_option_type(self):
        """Test is_option property with option_type field."""
        position = Position(
            symbol="AAPL240119C00195000",
            quantity=10,
            avg_price=5.50,
            option_type="call"
        )
        
        assert position.is_option is True

    def test_is_option_property_stock(self):
        """Test is_option property for stock position."""
        position = Position(
            symbol="AAPL",
            quantity=100,
            avg_price=150.0
        )
        
        assert position.is_option is False

    def test_multiplier_property_stock(self):
        """Test multiplier property for stock (1x)."""
        position = Position(
            symbol="AAPL",
            quantity=100,
            avg_price=150.0
        )
        
        assert position.multiplier == 1

    def test_multiplier_property_option(self):
        """Test multiplier property for option (100x)."""
        position = Position(
            symbol="AAPL240119C00195000",
            quantity=10,
            avg_price=5.50,
            option_type="call"
        )
        
        assert position.multiplier == 100

    def test_total_cost_basis_property_stock(self):
        """Test total_cost_basis property for stock."""
        position = Position(
            symbol="AAPL",
            quantity=100,
            avg_price=150.0
        )
        
        # |150.0 * 100| * 1 = 15,000
        assert position.total_cost_basis == 15000.0

    def test_total_cost_basis_property_option(self):
        """Test total_cost_basis property for option."""
        position = Position(
            symbol="AAPL240119C00195000",
            quantity=10,
            avg_price=5.50,
            option_type="call"
        )
        
        # |5.50 * 10| * 100 = 5,500
        assert position.total_cost_basis == 5500.0

    def test_total_cost_basis_property_negative_quantity(self):
        """Test total_cost_basis with negative quantity (short position)."""
        position = Position(
            symbol="AAPL",
            quantity=-100,
            avg_price=150.0
        )
        
        # |150.0 * -100| * 1 = 15,000 (absolute value)
        assert position.total_cost_basis == 15000.0

    def test_market_value_property_with_current_price(self):
        """Test market_value property with current price."""
        position = Position(
            symbol="AAPL",
            quantity=100,
            avg_price=150.0,
            current_price=155.0
        )
        
        # 155.0 * 100 * 1 = 15,500
        assert position.market_value == 15500.0

    def test_market_value_property_without_current_price(self):
        """Test market_value property without current price."""
        position = Position(
            symbol="AAPL",
            quantity=100,
            avg_price=150.0,
            current_price=None
        )
        
        assert position.market_value is None

    def test_market_value_property_option(self):
        """Test market_value property for option."""
        position = Position(
            symbol="AAPL240119C00195000",
            quantity=10,
            avg_price=5.50,
            current_price=6.00,
            option_type="call"
        )
        
        # 6.00 * 10 * 100 = 6,000
        assert position.market_value == 6000.0

    def test_total_pnl_property_with_unrealized(self):
        """Test total_pnl property with unrealized P&L."""
        position = Position(
            symbol="AAPL",
            quantity=100,
            avg_price=150.0,
            unrealized_pnl=500.0,
            realized_pnl=200.0
        )
        
        assert position.total_pnl == 700.0

    def test_total_pnl_property_without_unrealized(self):
        """Test total_pnl property without unrealized P&L."""
        position = Position(
            symbol="AAPL",
            quantity=100,
            avg_price=150.0,
            unrealized_pnl=None,
            realized_pnl=200.0
        )
        
        assert position.total_pnl == 200.0

    def test_pnl_percent_property_positive(self):
        """Test pnl_percent property with positive P&L."""
        position = Position(
            symbol="AAPL",
            quantity=100,
            avg_price=150.0,
            unrealized_pnl=1500.0,  # 10% gain
            realized_pnl=0.0
        )
        
        # Total P&L: 1500.0, Cost basis: 15,000, Percentage: 10%
        assert position.pnl_percent == 10.0

    def test_pnl_percent_property_negative(self):
        """Test pnl_percent property with negative P&L."""
        position = Position(
            symbol="AAPL",
            quantity=100,
            avg_price=150.0,
            unrealized_pnl=-750.0,  # 5% loss
            realized_pnl=0.0
        )
        
        # Total P&L: -750.0, Cost basis: 15,000, Percentage: -5%
        assert position.pnl_percent == -5.0

    def test_pnl_percent_property_no_pnl(self):
        """Test pnl_percent property with no P&L data."""
        position = Position(
            symbol="AAPL",
            quantity=100,
            avg_price=150.0,
            unrealized_pnl=None,
            realized_pnl=0.0
        )
        
        assert position.pnl_percent is None

    def test_pnl_percent_property_zero_cost_basis(self):
        """Test pnl_percent property with zero cost basis."""
        position = Position(
            symbol="AAPL",
            quantity=0,
            avg_price=150.0,
            unrealized_pnl=500.0
        )
        
        assert position.pnl_percent is None


class TestPositionCalculations:
    """Test Position calculation methods."""

    def test_calculate_unrealized_pnl_long_position_gain(self):
        """Test unrealized P&L calculation for long position gain."""
        position = Position(
            symbol="AAPL",
            quantity=100,
            avg_price=150.0
        )
        
        # Current price higher than avg price
        pnl = position.calculate_unrealized_pnl(155.0)
        
        # (155.0 - 150.0) * 100 * 1 = 500.0
        assert pnl == 500.0

    def test_calculate_unrealized_pnl_long_position_loss(self):
        """Test unrealized P&L calculation for long position loss."""
        position = Position(
            symbol="AAPL",
            quantity=100,
            avg_price=150.0
        )
        
        # Current price lower than avg price
        pnl = position.calculate_unrealized_pnl(145.0)
        
        # (145.0 - 150.0) * 100 * 1 = -500.0
        assert pnl == -500.0

    def test_calculate_unrealized_pnl_short_position_gain(self):
        """Test unrealized P&L calculation for short position gain."""
        position = Position(
            symbol="AAPL",
            quantity=-100,
            avg_price=150.0
        )
        
        # Current price lower than avg price (good for short)
        pnl = position.calculate_unrealized_pnl(145.0)
        
        # (145.0 - 150.0) * -100 * 1 = 500.0
        assert pnl == 500.0

    def test_calculate_unrealized_pnl_option_position(self):
        """Test unrealized P&L calculation for option position."""
        position = Position(
            symbol="AAPL240119C00195000",
            quantity=10,
            avg_price=5.50,
            option_type="call"
        )
        
        pnl = position.calculate_unrealized_pnl(6.00)
        
        # (6.00 - 5.50) * 10 * 100 = 500.0
        assert pnl == 500.0

    def test_calculate_unrealized_pnl_no_price(self):
        """Test unrealized P&L calculation with no price."""
        position = Position(
            symbol="AAPL",
            quantity=100,
            avg_price=150.0
        )
        
        pnl = position.calculate_unrealized_pnl(None)
        assert pnl is None

    def test_calculate_unrealized_pnl_use_current_price(self):
        """Test unrealized P&L calculation using position's current price."""
        position = Position(
            symbol="AAPL",
            quantity=100,
            avg_price=150.0,
            current_price=155.0
        )
        
        pnl = position.calculate_unrealized_pnl()
        assert pnl == 500.0

    def test_update_market_data_basic(self):
        """Test updating position with market data."""
        position = Position(
            symbol="AAPL",
            quantity=100,
            avg_price=150.0
        )
        
        position.update_market_data(155.0)
        
        assert position.current_price == 155.0
        assert position.unrealized_pnl == 500.0

    def test_update_market_data_with_greeks(self):
        """Test updating position with market data and Greeks."""
        position = Position(
            symbol="AAPL240119C00195000",
            quantity=10,
            avg_price=5.50,
            option_type="call"
        )
        
        # Mock quote with Greeks
        mock_quote = MagicMock()
        mock_quote.delta = 0.65
        mock_quote.gamma = 0.05
        mock_quote.theta = -0.025
        mock_quote.vega = 0.12
        mock_quote.rho = 0.08
        mock_quote.iv = 0.25
        
        position.update_market_data(6.00, mock_quote)
        
        assert position.current_price == 6.00
        assert position.unrealized_pnl == 500.0
        # Greeks should be scaled by quantity * multiplier
        assert position.delta == 0.65 * 10 * 100  # 650
        assert position.gamma == 0.05 * 10 * 100  # 50
        assert position.theta == -0.025 * 10 * 100  # -25
        assert position.vega == 0.12 * 10 * 100  # 120
        assert position.rho == 0.08 * 10 * 100  # 80
        assert position.iv == 0.25

    def test_update_market_data_stock_no_greeks(self):
        """Test updating stock position doesn't calculate Greeks."""
        position = Position(
            symbol="AAPL",
            quantity=100,
            avg_price=150.0
        )
        
        # Mock quote with Greeks (should be ignored for stocks)
        mock_quote = MagicMock()
        mock_quote.delta = 0.65
        
        position.update_market_data(155.0, mock_quote)
        
        assert position.current_price == 155.0
        assert position.unrealized_pnl == 500.0
        assert position.delta is None  # Should remain None for stocks

    def test_get_close_cost_long_position(self):
        """Test get_close_cost for long position."""
        position = Position(
            symbol="AAPL",
            quantity=100,
            avg_price=150.0,
            current_price=155.0
        )
        
        close_cost = position.get_close_cost()
        
        # To close long position, we sell: -155.0 * 100 * 1 = -15,500
        # Negative means we receive money
        assert close_cost == -15500.0

    def test_get_close_cost_short_position(self):
        """Test get_close_cost for short position."""
        position = Position(
            symbol="AAPL",
            quantity=-100,
            avg_price=150.0,
            current_price=155.0
        )
        
        close_cost = position.get_close_cost()
        
        # To close short position, we buy: -155.0 * -100 * 1 = 15,500
        # Positive means we pay money
        assert close_cost == 15500.0

    def test_get_close_cost_option_position(self):
        """Test get_close_cost for option position."""
        position = Position(
            symbol="AAPL240119C00195000",
            quantity=10,
            avg_price=5.50,
            current_price=6.00,
            option_type="call"
        )
        
        close_cost = position.get_close_cost()
        
        # To close long option position: -6.00 * 10 * 100 = -6,000
        assert close_cost == -6000.0

    def test_get_close_cost_no_current_price(self):
        """Test get_close_cost with no current price."""
        position = Position(
            symbol="AAPL",
            quantity=100,
            avg_price=150.0,
            current_price=None
        )
        
        close_cost = position.get_close_cost()
        assert close_cost is None

    def test_get_close_cost_with_override_price(self):
        """Test get_close_cost with price override."""
        position = Position(
            symbol="AAPL",
            quantity=100,
            avg_price=150.0,
            current_price=155.0
        )
        
        close_cost = position.get_close_cost(160.0)
        
        # Using override price: -160.0 * 100 * 1 = -16,000
        assert close_cost == -16000.0

    def test_simulate_close_long_position(self):
        """Test simulate_close for long position."""
        position = Position(
            symbol="AAPL",
            quantity=100,
            avg_price=150.0,
            current_price=155.0,
            realized_pnl=100.0
        )
        
        result = position.simulate_close()
        
        assert result["close_cost"] == -15500.0  # Receive money
        assert result["realized_pnl"] == 500.0   # Unrealized becomes realized
        assert result["total_realized_pnl"] == 600.0  # 100 + 500
        assert result["cash_impact"] == -15500.0

    def test_simulate_close_short_position(self):
        """Test simulate_close for short position."""
        position = Position(
            symbol="AAPL",
            quantity=-100,
            avg_price=150.0,
            current_price=145.0,  # Price dropped, good for short
            realized_pnl=0.0
        )
        
        result = position.simulate_close()
        
        assert result["close_cost"] == 14500.0   # Pay to buy back
        assert result["realized_pnl"] == 500.0   # Profit from price drop
        assert result["total_realized_pnl"] == 500.0
        assert result["cash_impact"] == 14500.0

    def test_simulate_close_no_price(self):
        """Test simulate_close with no price available."""
        position = Position(
            symbol="AAPL",
            quantity=100,
            avg_price=150.0,
            current_price=None
        )
        
        result = position.simulate_close()
        
        assert "error" in result
        assert result["error"] == "No price available"

    def test_simulate_close_with_override_price(self):
        """Test simulate_close with price override."""
        position = Position(
            symbol="AAPL",
            quantity=100,
            avg_price=150.0,
            current_price=155.0,
            realized_pnl=0.0
        )
        
        result = position.simulate_close(160.0)
        
        assert result["close_cost"] == -16000.0
        assert result["realized_pnl"] == 1000.0  # (160-150) * 100
        assert result["total_realized_pnl"] == 1000.0


class TestPositionValidationMixin:
    """Test PositionValidationMixin validation rules."""

    def test_avg_price_validation_positive(self):
        """Test average price must be positive."""
        position = Position(
            symbol="AAPL",
            quantity=100,
            avg_price=150.0
        )
        assert position.avg_price == 150.0

    def test_avg_price_validation_zero(self):
        """Test average price cannot be zero."""
        with pytest.raises(ValidationError) as exc_info:
            Position(
                symbol="AAPL",
                quantity=100,
                avg_price=0.0
            )
        
        error = exc_info.value.errors()[0]
        assert "Average price must be positive" in error["msg"]

    def test_avg_price_validation_negative(self):
        """Test average price cannot be negative."""
        with pytest.raises(ValidationError) as exc_info:
            Position(
                symbol="AAPL",
                quantity=100,
                avg_price=-150.0
            )
        
        error = exc_info.value.errors()[0]
        assert "Average price must be positive" in error["msg"]

    def test_strike_validation_positive(self):
        """Test strike price must be positive when provided."""
        position = Position(
            symbol="AAPL240119C00195000",
            quantity=10,
            avg_price=5.50,
            strike=195.0
        )
        assert position.strike == 195.0

    def test_strike_validation_zero(self):
        """Test strike price cannot be zero."""
        with pytest.raises(ValidationError) as exc_info:
            Position(
                symbol="AAPL240119C00195000",
                quantity=10,
                avg_price=5.50,
                strike=0.0
            )
        
        error = exc_info.value.errors()[0]
        assert "Strike price must be positive" in error["msg"]

    def test_strike_validation_negative(self):
        """Test strike price cannot be negative."""
        with pytest.raises(ValidationError) as exc_info:
            Position(
                symbol="AAPL240119C00195000",
                quantity=10,
                avg_price=5.50,
                strike=-195.0
            )
        
        error = exc_info.value.errors()[0]
        assert "Strike price must be positive" in error["msg"]

    def test_expiration_date_validation_future(self):
        """Test expiration date must be in future."""
        future_date = date(2025, 12, 31)
        position = Position(
            symbol="AAPL251231C00200000",
            quantity=10,
            avg_price=5.50,
            expiration_date=future_date
        )
        assert position.expiration_date == future_date

    def test_expiration_date_validation_past(self):
        """Test expiration date cannot be in past."""
        past_date = date(2020, 1, 1)
        with pytest.raises(ValidationError) as exc_info:
            Position(
                symbol="AAPL200101C00200000",
                quantity=10,
                avg_price=5.50,
                expiration_date=past_date
            )
        
        error = exc_info.value.errors()[0]
        assert "Expiration date must be in the future" in error["msg"]

    def test_option_type_validation_valid(self):
        """Test valid option type validation."""
        call_position = Position(
            symbol="AAPL240119C00195000",
            quantity=10,
            avg_price=5.50,
            option_type="call"
        )
        assert call_position.option_type == "call"
        
        put_position = Position(
            symbol="AAPL240119P00190000",
            quantity=10,
            avg_price=4.25,
            option_type="put"
        )
        assert put_position.option_type == "put"

    def test_option_type_validation_invalid(self):
        """Test invalid option type validation."""
        with pytest.raises(ValidationError) as exc_info:
            Position(
                symbol="AAPL240119C00195000",
                quantity=10,
                avg_price=5.50,
                option_type="invalid"
            )
        
        error = exc_info.value.errors()[0]
        assert 'Option type must be "call" or "put"' in error["msg"]


class TestPortfolioSchema:
    """Test Portfolio schema."""

    def test_portfolio_creation_basic(self):
        """Test creating basic portfolio."""
        position = Position(
            symbol="AAPL",
            quantity=100,
            avg_price=150.0,
            current_price=155.0,
            unrealized_pnl=500.0
        )
        
        portfolio = Portfolio(
            cash_balance=10000.0,
            total_value=25500.0,
            positions=[position],
            daily_pnl=250.0,
            total_pnl=1500.0
        )
        
        assert portfolio.cash_balance == 10000.0
        assert portfolio.total_value == 25500.0
        assert len(portfolio.positions) == 1
        assert portfolio.positions[0].symbol == "AAPL"
        assert portfolio.daily_pnl == 250.0
        assert portfolio.total_pnl == 1500.0

    def test_portfolio_empty_positions(self):
        """Test portfolio with no positions."""
        portfolio = Portfolio(
            cash_balance=50000.0,
            total_value=50000.0,
            positions=[],
            daily_pnl=0.0,
            total_pnl=0.0
        )
        
        assert portfolio.positions == []
        assert portfolio.cash_balance == portfolio.total_value


class TestPortfolioSummary:
    """Test PortfolioSummary schema."""

    def test_portfolio_summary_creation(self):
        """Test creating portfolio summary."""
        summary = PortfolioSummary(
            total_value=75000.0,
            cash_balance=25000.0,
            invested_value=50000.0,
            daily_pnl=1250.0,
            daily_pnl_percent=1.67,
            total_pnl=5000.0,
            total_pnl_percent=7.14
        )
        
        assert summary.total_value == 75000.0
        assert summary.cash_balance == 25000.0
        assert summary.invested_value == 50000.0
        assert summary.daily_pnl == 1250.0
        assert summary.daily_pnl_percent == 1.67
        assert summary.total_pnl == 5000.0
        assert summary.total_pnl_percent == 7.14


class TestPositionEdgeCases:
    """Test edge cases and complex scenarios."""

    def test_zero_quantity_position(self):
        """Test position with zero quantity."""
        position = Position(
            symbol="AAPL",
            quantity=0,
            avg_price=150.0
        )
        
        assert position.quantity == 0
        assert position.total_cost_basis == 0.0
        assert position.market_value == 0.0

    def test_very_large_position(self):
        """Test position with very large quantities."""
        position = Position(
            symbol="AAPL",
            quantity=1000000,
            avg_price=150.0,
            current_price=155.0
        )
        
        assert position.total_cost_basis == 150_000_000.0
        assert position.market_value == 155_000_000.0
        assert position.calculate_unrealized_pnl() == 5_000_000.0

    def test_fractional_shares_position(self):
        """Test position calculations handle fractional quantities correctly."""
        # Note: quantity is int, but this tests the math works for edge cases
        position = Position(
            symbol="AAPL",
            quantity=50,  # Representing 0.5 shares as 50 fractional units
            avg_price=150.0,
            current_price=155.0
        )
        
        pnl = position.calculate_unrealized_pnl()
        assert pnl == 250.0  # (155-150) * 50 * 1

    def test_high_volatility_option_greeks(self):
        """Test option position with extreme Greeks values."""
        position = Position(
            symbol="MEME240119C00100000",
            quantity=100,
            avg_price=50.0,
            current_price=75.0,
            option_type="call",
            delta=0.95,
            gamma=0.001,
            theta=-5.0,
            vega=2.5,
            iv=3.5  # 350% IV
        )
        
        # Verify extreme but valid values are handled
        assert position.delta == 0.95
        assert position.theta == -5.0
        assert position.iv == 3.5

    def test_deep_otm_option_position(self):
        """Test deep out-of-the-money option position."""
        position = Position(
            symbol="AAPL240119C00300000",  # Way OTM call
            quantity=1000,
            avg_price=0.01,  # Penny options
            current_price=0.005,  # Lost half value
            option_type="call",
            strike=300.0,
            underlying_symbol="AAPL"
        )
        
        # Should handle penny options correctly
        assert position.avg_price == 0.01
        assert position.current_price == 0.005
        unrealized_pnl = position.calculate_unrealized_pnl()
        assert unrealized_pnl == -500.0  # (0.005 - 0.01) * 1000 * 100


class TestPositionSerialization:
    """Test position serialization and deserialization."""

    def test_position_json_roundtrip_basic(self):
        """Test position JSON serialization roundtrip."""
        original_position = Position(
            symbol="AAPL",
            quantity=100,
            avg_price=150.0,
            current_price=155.0,
            unrealized_pnl=500.0,
            realized_pnl=100.0
        )
        
        # Serialize to dict
        data = original_position.model_dump()
        
        # Deserialize back
        restored_position = Position(**data)
        
        assert restored_position.symbol == original_position.symbol
        assert restored_position.quantity == original_position.quantity
        assert restored_position.avg_price == original_position.avg_price
        assert restored_position.current_price == original_position.current_price
        assert restored_position.unrealized_pnl == original_position.unrealized_pnl
        assert restored_position.realized_pnl == original_position.realized_pnl

    def test_position_json_roundtrip_with_option_fields(self):
        """Test position JSON serialization with option fields."""
        exp_date = date(2024, 1, 19)
        
        original_position = Position(
            symbol="AAPL240119C00195000",
            quantity=10,
            avg_price=5.50,
            current_price=6.00,
            option_type="call",
            strike=195.0,
            expiration_date=exp_date,
            underlying_symbol="AAPL",
            delta=650.0,
            gamma=50.0,
            theta=-25.0,
            vega=120.0,
            rho=80.0,
            iv=0.25
        )
        
        # Serialize to dict
        data = original_position.model_dump()
        
        # Deserialize back
        restored_position = Position(**data)
        
        assert restored_position.option_type == "call"
        assert restored_position.strike == 195.0
        assert restored_position.expiration_date == exp_date
        assert restored_position.underlying_symbol == "AAPL"
        assert restored_position.delta == 650.0
        assert restored_position.iv == 0.25