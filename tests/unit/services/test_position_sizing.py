"""
Comprehensive tests for app/services/position_sizing.py - Position sizing calculators.

Tests cover:
- Sizing strategy implementations and calculations
- Kelly Criterion with win rate and ratio parameters
- Volatility-based sizing with historical data
- Risk parity allocation and risk budgeting
- Fixed dollar and percentage strategies
- Maximum loss sizing with stop loss integration
- ATR-based sizing with range calculations
- Portfolio allocation across multiple symbols
- Constraint application and validation
- Edge cases and error handling
- Performance and optimization scenarios
"""

from unittest.mock import patch

import numpy as np
import pytest

from app.schemas.positions import Portfolio, Position
from app.services.position_sizing import (
    PositionSizeResult,
    PositionSizingCalculator,
    SizingParameters,
    SizingStrategy,
    configure_sizing_parameters,
    get_position_calculator,
    position_calculator,
)


class TestSizingStrategy:
    """Test suite for SizingStrategy enum."""

    def test_sizing_strategy_values(self):
        """Test all sizing strategy values."""
        assert SizingStrategy.FIXED_DOLLAR == "fixed_dollar"
        assert SizingStrategy.FIXED_PERCENTAGE == "fixed_percentage"
        assert SizingStrategy.KELLY_CRITERION == "kelly_criterion"
        assert SizingStrategy.VOLATILITY_BASED == "volatility_based"
        assert SizingStrategy.RISK_PARITY == "risk_parity"
        assert SizingStrategy.MAX_LOSS == "max_loss"
        assert SizingStrategy.ATR_BASED == "atr_based"


class TestPositionSizeResult:
    """Test suite for PositionSizeResult data class."""

    def test_position_size_result_creation(self):
        """Test PositionSizeResult creation with defaults."""
        result = PositionSizeResult(
            strategy=SizingStrategy.FIXED_DOLLAR,
            recommended_shares=100,
            position_value=15000.0,
            percent_of_portfolio=0.15,
            risk_amount=300.0,
        )

        assert result.strategy == SizingStrategy.FIXED_DOLLAR
        assert result.recommended_shares == 100
        assert result.position_value == 15000.0
        assert result.percent_of_portfolio == 0.15
        assert result.risk_amount == 300.0
        assert result.stop_loss_price is None
        assert result.confidence_level == 0.95
        assert result.notes == []

    def test_position_size_result_with_all_fields(self):
        """Test PositionSizeResult with all fields."""
        result = PositionSizeResult(
            strategy=SizingStrategy.MAX_LOSS,
            recommended_shares=50,
            position_value=7500.0,
            percent_of_portfolio=0.075,
            risk_amount=150.0,
            stop_loss_price=145.0,
            confidence_level=0.90,
            notes=["Stop loss based", "2% risk"],
        )

        assert result.stop_loss_price == 145.0
        assert result.confidence_level == 0.90
        assert len(result.notes) == 2

    def test_position_size_result_post_init(self):
        """Test PositionSizeResult post_init method."""
        result = PositionSizeResult(
            strategy=SizingStrategy.FIXED_DOLLAR,
            recommended_shares=100,
            position_value=15000.0,
            percent_of_portfolio=0.15,
            risk_amount=300.0,
            notes=None,
        )

        assert result.notes == []


class TestSizingParameters:
    """Test suite for SizingParameters data class."""

    def test_sizing_parameters_defaults(self):
        """Test SizingParameters default values."""
        params = SizingParameters()

        assert params.max_risk_per_trade == 0.02
        assert params.max_position_size == 0.20
        assert params.min_position_size == 0.01
        assert params.win_rate == 0.55
        assert params.average_win == 1.5
        assert params.average_loss == 1.0
        assert params.kelly_fraction == 0.25
        assert params.target_volatility == 0.16
        assert params.lookback_period == 20
        assert params.risk_budget == 0.10

    def test_sizing_parameters_custom_values(self):
        """Test SizingParameters with custom values."""
        params = SizingParameters(
            max_risk_per_trade=0.03,
            max_position_size=0.25,
            min_position_size=0.005,
            win_rate=0.60,
            average_win=2.0,
            average_loss=0.8,
            kelly_fraction=0.50,
            target_volatility=0.20,
            lookback_period=30,
            risk_budget=0.15,
        )

        assert params.max_risk_per_trade == 0.03
        assert params.win_rate == 0.60
        assert params.kelly_fraction == 0.50


class TestPositionSizingCalculator:
    """Test suite for PositionSizingCalculator functionality."""

    @pytest.fixture
    def calculator(self):
        """Create PositionSizingCalculator instance."""
        return PositionSizingCalculator()

    @pytest.fixture
    def custom_calculator(self):
        """Create calculator with custom parameters."""
        params = SizingParameters(
            max_risk_per_trade=0.015,
            max_position_size=0.15,
            win_rate=0.60,
            kelly_fraction=0.30,
        )
        return PositionSizingCalculator(params)

    @pytest.fixture
    def sample_portfolio(self):
        """Create sample portfolio for testing."""
        positions = [
            Position(symbol="AAPL", quantity=100, avg_price=145.0, current_price=150.0),
            Position(symbol="MSFT", quantity=50, avg_price=290.0, current_price=300.0),
        ]
        return Portfolio(
            cash_balance=50000.0,
            positions=positions,
            total_value=80000.0,  # 15000 + 15000 + 50000
            daily_pnl=1000.0,
            total_pnl=5000.0,
        )

    @pytest.fixture
    def historical_prices(self):
        """Create sample historical prices."""
        # Generate realistic price series with some volatility
        base_price = 150.0
        prices = [base_price]
        np.random.seed(42)  # For reproducible tests

        for _ in range(29):  # 30 days total
            change = np.random.normal(0, 0.02)  # 2% daily volatility
            new_price = prices[-1] * (1 + change)
            prices.append(new_price)

        return prices

    def test_calculator_initialization(self, calculator):
        """Test calculator initialization."""
        assert isinstance(calculator.parameters, SizingParameters)
        assert calculator.price_history == {}

    def test_calculator_initialization_with_custom_params(self, custom_calculator):
        """Test calculator with custom parameters."""
        assert custom_calculator.parameters.max_risk_per_trade == 0.015
        assert custom_calculator.parameters.win_rate == 0.60

    def test_fixed_dollar_sizing(self, calculator, sample_portfolio):
        """Test fixed dollar position sizing."""
        result = calculator._fixed_dollar_sizing("GOOGL", 2500.0, sample_portfolio)

        assert result.strategy == SizingStrategy.FIXED_DOLLAR
        assert result.recommended_shares > 0
        assert result.position_value > 0
        assert result.percent_of_portfolio > 0
        assert len(result.notes) > 0
        assert "Fixed amount" in result.notes[0]

        # Should use 5% of portfolio (4000)
        expected_shares = int(4000.0 / 2500.0)  # 1 share
        assert result.recommended_shares == expected_shares

    def test_fixed_percentage_sizing(self, calculator, sample_portfolio):
        """Test fixed percentage position sizing."""
        result = calculator._fixed_percentage_sizing("TSLA", 800.0, sample_portfolio)

        assert result.strategy == SizingStrategy.FIXED_PERCENTAGE
        assert result.recommended_shares > 0
        assert result.percent_of_portfolio > 0
        assert "Target:" in result.notes[0]

        # Should use 10% of portfolio (8000)
        expected_shares = int(8000.0 / 800.0)  # 10 shares
        assert result.recommended_shares == expected_shares

    def test_kelly_criterion_sizing(self, calculator, sample_portfolio):
        """Test Kelly Criterion position sizing."""
        result = calculator._kelly_criterion_sizing("NVDA", 500.0, sample_portfolio)

        assert result.strategy == SizingStrategy.KELLY_CRITERION
        assert result.recommended_shares > 0
        assert result.confidence_level == calculator.parameters.win_rate
        assert len(result.notes) >= 3
        assert "Kelly %" in result.notes[0]
        assert "Win rate:" in result.notes[1]
        assert "Win/Loss ratio:" in result.notes[2]

    def test_kelly_criterion_calculation(self, calculator):
        """Test Kelly Criterion mathematical calculation."""
        # Test Kelly formula: f* = (p * b - q) / b
        p = 0.60  # 60% win rate

        calculator.parameters.win_rate = p
        calculator.parameters.average_win = 2.0
        calculator.parameters.average_loss = 1.0
        calculator.parameters.kelly_fraction = 1.0  # Full Kelly

        portfolio = Portfolio(
            cash_balance=10000.0,
            positions=[],
            total_value=10000.0,
            daily_pnl=0.0,
            total_pnl=0.0,
        )

        result = calculator._kelly_criterion_sizing("TEST", 100.0, portfolio)

        # Kelly % = (0.60 * 2.0 - 0.40) / 2.0 = 0.40
        expected_kelly = 0.40
        expected_position_value = 10000.0 * expected_kelly
        expected_shares = int(expected_position_value / 100.0)

        assert result.recommended_shares == expected_shares

    def test_volatility_based_sizing(
        self, calculator, sample_portfolio, historical_prices
    ):
        """Test volatility-based position sizing."""
        result = calculator._volatility_based_sizing(
            "AMZN", 3000.0, sample_portfolio, historical_prices
        )

        assert result.strategy == SizingStrategy.VOLATILITY_BASED
        assert result.recommended_shares > 0
        assert len(result.notes) >= 3
        assert "Annual volatility:" in result.notes[0]
        assert "Volatility scalar:" in result.notes[1]
        assert "Target vol:" in result.notes[2]

    def test_volatility_based_sizing_insufficient_data(
        self, calculator, sample_portfolio
    ):
        """Test volatility-based sizing with insufficient data."""
        with pytest.raises(ValueError, match="Insufficient price history"):
            calculator._volatility_based_sizing(
                "AMZN", 3000.0, sample_portfolio, [150.0]
            )

    def test_risk_parity_sizing(self, calculator, sample_portfolio, historical_prices):
        """Test risk parity position sizing."""
        result = calculator._risk_parity_sizing(
            "META", 200.0, sample_portfolio, historical_prices
        )

        assert result.strategy == SizingStrategy.RISK_PARITY
        assert result.recommended_shares > 0
        assert len(result.notes) >= 3
        assert "Asset volatility:" in result.notes[0]
        assert "Risk budget:" in result.notes[1]
        assert "Risk allocation:" in result.notes[2]

    def test_risk_parity_sizing_insufficient_data(self, calculator, sample_portfolio):
        """Test risk parity sizing with insufficient data."""
        with pytest.raises(ValueError, match="Insufficient price history"):
            calculator._risk_parity_sizing("META", 200.0, sample_portfolio, [200.0])

    def test_max_loss_sizing(self, calculator, sample_portfolio):
        """Test maximum loss position sizing."""
        current_price = 150.0
        stop_loss = 140.0  # $10 risk per share

        result = calculator._max_loss_sizing(
            "AAPL", current_price, sample_portfolio, stop_loss
        )

        assert result.strategy == SizingStrategy.MAX_LOSS
        assert result.stop_loss_price == stop_loss
        assert result.recommended_shares > 0
        assert len(result.notes) >= 3
        assert "Risk per share:" in result.notes[0]
        assert "Max risk:" in result.notes[1]
        assert "Stop loss:" in result.notes[2]

        # Risk per share = 150 - 140 = $10
        # Max risk = 80000 * 0.02 = $1600
        # Shares = 1600 / 10 = 160
        expected_shares = 160
        # But will be constrained by other factors
        assert result.recommended_shares <= expected_shares

    def test_max_loss_sizing_no_stop_loss(self, calculator, sample_portfolio):
        """Test max loss sizing without stop loss."""
        with pytest.raises(ValueError, match="Stop loss price required"):
            calculator._max_loss_sizing("AAPL", 150.0, sample_portfolio, None)

    def test_max_loss_sizing_invalid_stop_loss(self, calculator, sample_portfolio):
        """Test max loss sizing with invalid stop loss."""
        with pytest.raises(ValueError, match="Stop loss must be below current price"):
            calculator._max_loss_sizing("AAPL", 150.0, sample_portfolio, 160.0)

    def test_atr_based_sizing(self, calculator, sample_portfolio, historical_prices):
        """Test ATR-based position sizing."""
        result = calculator._atr_based_sizing(
            "NFLX", 400.0, sample_portfolio, historical_prices
        )

        assert result.strategy == SizingStrategy.ATR_BASED
        assert result.recommended_shares > 0
        assert result.stop_loss_price is not None
        assert result.stop_loss_price < 400.0
        assert len(result.notes) >= 3
        assert "ATR:" in result.notes[0]
        assert "Risk in ATRs:" in result.notes[1]
        assert "ATR-based stop:" in result.notes[2]

    def test_atr_based_sizing_insufficient_data(self, calculator, sample_portfolio):
        """Test ATR-based sizing with insufficient data."""
        short_prices = [400.0, 405.0, 398.0]  # Less than lookback period

        with pytest.raises(ValueError, match="Insufficient price history"):
            calculator._atr_based_sizing("NFLX", 400.0, sample_portfolio, short_prices)

    def test_calculate_position_size_all_strategies(
        self, calculator, sample_portfolio, historical_prices
    ):
        """Test calculate_position_size with all strategies."""
        strategies = [
            SizingStrategy.FIXED_DOLLAR,
            SizingStrategy.FIXED_PERCENTAGE,
            SizingStrategy.KELLY_CRITERION,
            SizingStrategy.VOLATILITY_BASED,
            SizingStrategy.RISK_PARITY,
            SizingStrategy.MAX_LOSS,
            SizingStrategy.ATR_BASED,
        ]

        for strategy in strategies:
            if strategy == SizingStrategy.MAX_LOSS:
                result = calculator.calculate_position_size(
                    "AAPL", 150.0, sample_portfolio, strategy, stop_loss=140.0
                )
            elif strategy in [
                SizingStrategy.VOLATILITY_BASED,
                SizingStrategy.RISK_PARITY,
                SizingStrategy.ATR_BASED,
            ]:
                result = calculator.calculate_position_size(
                    "AAPL",
                    150.0,
                    sample_portfolio,
                    strategy,
                    historical_prices=historical_prices,
                )
            else:
                result = calculator.calculate_position_size(
                    "AAPL", 150.0, sample_portfolio, strategy
                )

            assert isinstance(result, PositionSizeResult)
            assert result.strategy == strategy
            assert result.recommended_shares >= 0

    def test_calculate_position_size_unknown_strategy(
        self, calculator, sample_portfolio
    ):
        """Test calculate_position_size with unknown strategy."""
        with pytest.raises(ValueError, match="Unknown sizing strategy"):
            calculator.calculate_position_size(
                "AAPL", 150.0, sample_portfolio, "unknown_strategy"
            )

    def test_calculate_multiple_strategies(
        self, calculator, sample_portfolio, historical_prices
    ):
        """Test calculate_multiple_strategies method."""
        results = calculator.calculate_multiple_strategies(
            "AAPL",
            150.0,
            sample_portfolio,
            stop_loss=140.0,
            historical_prices=historical_prices,
        )

        # Should include all applicable strategies
        assert SizingStrategy.FIXED_DOLLAR in results
        assert SizingStrategy.FIXED_PERCENTAGE in results
        assert SizingStrategy.KELLY_CRITERION in results
        assert SizingStrategy.MAX_LOSS in results
        assert SizingStrategy.VOLATILITY_BASED in results
        assert SizingStrategy.RISK_PARITY in results
        assert SizingStrategy.ATR_BASED in results

    def test_calculate_multiple_strategies_no_stop_loss(
        self, calculator, sample_portfolio, historical_prices
    ):
        """Test calculate_multiple_strategies without stop loss."""
        results = calculator.calculate_multiple_strategies(
            "AAPL", 150.0, sample_portfolio, historical_prices=historical_prices
        )

        # Should not include MAX_LOSS strategy
        assert SizingStrategy.MAX_LOSS not in results
        assert SizingStrategy.FIXED_DOLLAR in results
        assert SizingStrategy.VOLATILITY_BASED in results

    def test_calculate_multiple_strategies_no_historical_data(
        self, calculator, sample_portfolio
    ):
        """Test calculate_multiple_strategies without historical data."""
        results = calculator.calculate_multiple_strategies(
            "AAPL", 150.0, sample_portfolio, stop_loss=140.0
        )

        # Should not include strategies requiring historical data
        assert SizingStrategy.VOLATILITY_BASED not in results
        assert SizingStrategy.RISK_PARITY not in results
        assert SizingStrategy.ATR_BASED not in results
        assert SizingStrategy.FIXED_DOLLAR in results
        assert SizingStrategy.MAX_LOSS in results

    def test_apply_constraints_min_position(self, calculator):
        """Test constraint application for minimum position size."""
        portfolio = Portfolio(
            cash_balance=10000.0,
            positions=[],
            total_value=10000.0,
            daily_pnl=0.0,
            total_pnl=0.0,
        )

        # Very small position that would be below minimum
        constrained_shares = calculator._apply_constraints(0, 1000.0, portfolio)

        # Should be adjusted to minimum
        min_value = portfolio.total_value * calculator.parameters.min_position_size
        min_shares = max(1, int(min_value / 1000.0))
        assert constrained_shares == min_shares

    def test_apply_constraints_max_position(self, calculator):
        """Test constraint application for maximum position size."""
        portfolio = Portfolio(
            cash_balance=100000.0,
            positions=[],
            total_value=100000.0,
            daily_pnl=0.0,
            total_pnl=0.0,
        )

        # Very large position that would exceed maximum
        large_shares = 10000  # Would be way over 20% max
        constrained_shares = calculator._apply_constraints(
            large_shares, 100.0, portfolio
        )

        # Should be capped at maximum
        max_value = portfolio.total_value * calculator.parameters.max_position_size
        max_shares = int(max_value / 100.0)
        assert constrained_shares <= max_shares

    def test_apply_constraints_cash_limit(self, calculator):
        """Test constraint application for available cash."""
        portfolio = Portfolio(
            cash_balance=5000.0,  # Limited cash
            positions=[],
            total_value=100000.0,  # High total value
            daily_pnl=0.0,
            total_pnl=0.0,
        )

        # Try to buy more than cash allows
        large_shares = 100  # Would cost $10,000 at $100/share
        constrained_shares = calculator._apply_constraints(
            large_shares, 100.0, portfolio
        )

        # Should be limited by available cash (with 5% buffer)
        available_cash = portfolio.cash_balance * 0.95
        max_affordable = int(available_cash / 100.0)
        assert constrained_shares <= max_affordable

    def test_calculate_portfolio_allocation(self, calculator, sample_portfolio):
        """Test portfolio allocation across multiple symbols."""
        symbols = ["AAPL", "GOOGL", "TSLA"]
        current_prices = {"AAPL": 150.0, "GOOGL": 2500.0, "TSLA": 800.0}

        results = calculator.calculate_portfolio_allocation(
            symbols, current_prices, sample_portfolio, SizingStrategy.FIXED_PERCENTAGE
        )

        assert len(results) == 3
        assert "AAPL" in results
        assert "GOOGL" in results
        assert "TSLA" in results

        # Each result should be valid
        for _symbol, result in results.items():
            assert isinstance(result, PositionSizeResult)
            assert result.recommended_shares >= 0
            assert result.position_value >= 0

    def test_calculate_portfolio_allocation_insufficient_cash(self, calculator):
        """Test portfolio allocation with insufficient cash."""
        portfolio = Portfolio(
            cash_balance=1000.0,  # Very limited cash
            positions=[],
            total_value=1000.0,
            daily_pnl=0.0,
            total_pnl=0.0,
        )

        symbols = ["GOOGL", "TSLA", "AMZN"]  # Expensive stocks
        current_prices = {"GOOGL": 2500.0, "TSLA": 800.0, "AMZN": 3000.0}

        results = calculator.calculate_portfolio_allocation(
            symbols, current_prices, portfolio, SizingStrategy.FIXED_PERCENTAGE
        )

        # Should stop when cash runs out
        total_allocated = sum(result.position_value for result in results.values())
        assert total_allocated <= portfolio.cash_balance

    def test_suggest_position_size_risk_tolerance_mapping(
        self, calculator, sample_portfolio
    ):
        """Test suggest_position_size with different risk tolerances."""
        risk_tolerances = ["low", "moderate", "high"]
        expected_strategies = [
            SizingStrategy.FIXED_PERCENTAGE,
            SizingStrategy.VOLATILITY_BASED,
            SizingStrategy.KELLY_CRITERION,
        ]

        for risk_tolerance, expected_strategy in zip(
            risk_tolerances, expected_strategies, strict=False
        ):
            with patch.object(calculator, "calculate_position_size") as mock_calc:
                mock_calc.return_value = PositionSizeResult(
                    strategy=expected_strategy,
                    recommended_shares=100,
                    position_value=15000.0,
                    percent_of_portfolio=0.15,
                    risk_amount=300.0,
                )

                calculator.suggest_position_size(
                    "AAPL", 150.0, sample_portfolio, risk_tolerance
                )

                # Should call with expected strategy
                mock_calc.assert_called_once()
                args = mock_calc.call_args[0]
                assert args[3] == expected_strategy

    def test_suggest_position_size_with_stop_loss(self, calculator, sample_portfolio):
        """Test suggest_position_size with stop loss overrides strategy."""
        with patch.object(calculator, "calculate_position_size") as mock_calc:
            mock_calc.return_value = PositionSizeResult(
                strategy=SizingStrategy.MAX_LOSS,
                recommended_shares=100,
                position_value=15000.0,
                percent_of_portfolio=0.15,
                risk_amount=300.0,
            )

            calculator.suggest_position_size(
                "AAPL", 150.0, sample_portfolio, "moderate", stop_loss=140.0
            )

            # Should use MAX_LOSS strategy when stop loss provided
            mock_calc.assert_called_once()
            args = mock_calc.call_args[0]
            assert args[3] == SizingStrategy.MAX_LOSS

    def test_suggest_position_size_unknown_risk_tolerance(
        self, calculator, sample_portfolio
    ):
        """Test suggest_position_size with unknown risk tolerance."""
        with patch.object(calculator, "calculate_position_size") as mock_calc:
            mock_calc.return_value = PositionSizeResult(
                strategy=SizingStrategy.FIXED_PERCENTAGE,
                recommended_shares=100,
                position_value=15000.0,
                percent_of_portfolio=0.15,
                risk_amount=300.0,
            )

            calculator.suggest_position_size("AAPL", 150.0, sample_portfolio, "unknown")

            # Should default to FIXED_PERCENTAGE
            mock_calc.assert_called_once()
            args = mock_calc.call_args[0]
            assert args[3] == SizingStrategy.FIXED_PERCENTAGE

    def test_portfolio_with_no_positions(self, calculator):
        """Test calculations with empty portfolio."""
        empty_portfolio = Portfolio(
            cash_balance=10000.0,
            positions=[],
            total_value=10000.0,
            daily_pnl=0.0,
            total_pnl=0.0,
        )

        result = calculator.calculate_position_size(
            "AAPL", 150.0, empty_portfolio, SizingStrategy.FIXED_PERCENTAGE
        )

        assert result.recommended_shares > 0
        assert result.position_value > 0

    def test_portfolio_with_current_price_none(self, calculator):
        """Test calculations with positions having None current_price."""
        portfolio = Portfolio(
            cash_balance=10000.0,
            positions=[
                Position(
                    symbol="AAPL", quantity=100, avg_price=145.0, current_price=None
                ),
            ],
            total_value=10000.0,
            daily_pnl=0.0,
            total_pnl=0.0,
        )

        # Risk parity should handle None current_price gracefully
        with pytest.raises(ValueError):  # Should fail with insufficient data
            calculator._risk_parity_sizing("MSFT", 300.0, portfolio, [])

    def test_volatility_calculation_edge_cases(self, calculator, sample_portfolio):
        """Test volatility calculations with edge cases."""
        # All same prices (zero volatility)
        flat_prices = [100.0] * 30

        result = calculator._volatility_based_sizing(
            "TEST", 100.0, sample_portfolio, flat_prices
        )

        # Should handle zero volatility gracefully
        assert result.recommended_shares > 0

    def test_atr_calculation_edge_cases(self, calculator, sample_portfolio):
        """Test ATR calculations with edge cases."""
        # All same prices (zero ATR)
        flat_prices = [100.0] * 30

        result = calculator._atr_based_sizing(
            "TEST", 100.0, sample_portfolio, flat_prices
        )

        # Should use default ATR when calculated ATR is zero
        assert result.recommended_shares > 0
        assert result.stop_loss_price is not None

    def test_kelly_criterion_edge_cases(self, calculator, sample_portfolio):
        """Test Kelly Criterion with edge cases."""
        # Test with losing strategy (negative Kelly)
        calculator.parameters.win_rate = 0.30  # 30% win rate
        calculator.parameters.average_win = 1.0
        calculator.parameters.average_loss = 2.0  # Losses bigger than wins

        result = calculator._kelly_criterion_sizing("TEST", 100.0, sample_portfolio)

        # Should constrain to minimum position even with negative Kelly
        assert result.recommended_shares > 0

    def test_risk_parity_with_existing_positions(
        self, calculator, sample_portfolio, historical_prices
    ):
        """Test risk parity calculation with existing positions."""
        # Sample portfolio already has positions with current prices
        result = calculator._risk_parity_sizing(
            "NEW", 500.0, sample_portfolio, historical_prices
        )

        assert result.recommended_shares >= 0
        assert "Risk allocation:" in result.notes[2]


class TestGlobalPositionCalculator:
    """Test suite for global position calculator functions."""

    def test_get_position_calculator(self):
        """Test getting global position calculator."""
        calc = get_position_calculator()

        assert isinstance(calc, PositionSizingCalculator)
        assert calc is position_calculator

    def test_configure_sizing_parameters(self):
        """Test configuring global sizing parameters."""
        custom_params = SizingParameters(
            max_risk_per_trade=0.025, win_rate=0.65, kelly_fraction=0.40
        )

        configure_sizing_parameters(custom_params)
        calc = get_position_calculator()

        assert calc.parameters.max_risk_per_trade == 0.025
        assert calc.parameters.win_rate == 0.65
        assert calc.parameters.kelly_fraction == 0.40


class TestPositionSizingEdgeCases:
    """Test suite for edge cases and error conditions."""

    @pytest.fixture
    def calculator(self):
        return PositionSizingCalculator()

    def test_zero_price_handling(self, calculator):
        """Test handling of zero or negative prices."""
        portfolio = Portfolio(
            cash_balance=10000.0,
            positions=[],
            total_value=10000.0,
            daily_pnl=0.0,
            total_pnl=0.0,
        )

        # Should handle gracefully without crashing
        result = calculator._fixed_dollar_sizing(
            "TEST", 0.01, portfolio
        )  # Very small price
        assert result.recommended_shares >= 0

    def test_zero_portfolio_value(self, calculator):
        """Test handling of zero portfolio value."""
        zero_portfolio = Portfolio(
            cash_balance=0.0,
            positions=[],
            total_value=0.0,
            daily_pnl=0.0,
            total_pnl=0.0,
        )

        result = calculator._fixed_percentage_sizing("TEST", 100.0, zero_portfolio)

        # Should return zero shares for zero portfolio
        assert result.recommended_shares == 0

    def test_extreme_volatility(self, calculator):
        """Test handling of extreme volatility."""
        portfolio = Portfolio(
            cash_balance=10000.0,
            positions=[],
            total_value=10000.0,
            daily_pnl=0.0,
            total_pnl=0.0,
        )

        # Create extremely volatile price series
        extreme_prices = [100.0, 200.0, 50.0, 300.0, 25.0] * 6  # 30 prices

        result = calculator._volatility_based_sizing(
            "VOLATILE", 100.0, portfolio, extreme_prices
        )

        # Should constrain position due to high volatility
        assert result.recommended_shares >= 0
        assert result.percent_of_portfolio <= calculator.parameters.max_position_size

    def test_insufficient_cash_constraints(self, calculator):
        """Test constraints with insufficient cash."""
        poor_portfolio = Portfolio(
            cash_balance=100.0,  # Very little cash
            positions=[],
            total_value=100000.0,  # High total value from other assets
            daily_pnl=0.0,
            total_pnl=0.0,
        )

        # Try to buy expensive stock
        constrained_shares = calculator._apply_constraints(100, 1000.0, poor_portfolio)

        # Should be severely limited by cash
        available_cash = poor_portfolio.cash_balance * 0.95
        max_affordable = int(available_cash / 1000.0)
        assert constrained_shares <= max_affordable

    def test_mathematical_edge_cases(self, calculator):
        """Test mathematical edge cases in calculations."""
        portfolio = Portfolio(
            cash_balance=10000.0,
            positions=[],
            total_value=10000.0,
            daily_pnl=0.0,
            total_pnl=0.0,
        )

        # Test Kelly with extreme parameters
        calculator.parameters.win_rate = 0.99  # 99% win rate
        calculator.parameters.average_win = 0.01  # Tiny wins
        calculator.parameters.average_loss = 100.0  # Huge losses

        result = calculator._kelly_criterion_sizing("EXTREME", 100.0, portfolio)

        # Should produce reasonable result despite extreme parameters
        assert result.recommended_shares >= 0
        assert result.percent_of_portfolio <= 1.0


class TestPositionSizingPerformance:
    """Test suite for performance and optimization scenarios."""

    @pytest.fixture
    def calculator(self):
        return PositionSizingCalculator()

    @pytest.fixture
    def large_portfolio(self):
        """Create large portfolio for performance testing."""
        positions = []
        for i in range(100):  # 100 positions
            positions.append(
                Position(
                    symbol=f"STOCK{i:03d}",
                    quantity=100 + i,
                    avg_price=50.0 + i,
                    current_price=55.0 + i,
                )
            )

        total_value = sum(pos.quantity * pos.current_price for pos in positions)

        return Portfolio(
            cash_balance=50000.0,
            positions=positions,
            total_value=total_value + 50000.0,
            daily_pnl=1000.0,
            total_pnl=5000.0,
        )

    def test_large_portfolio_risk_parity(self, calculator, large_portfolio):
        """Test risk parity performance with large portfolio."""
        historical_prices = list(range(100, 130))  # 30 day price series

        result = calculator._risk_parity_sizing(
            "NEWSTOCK", 100.0, large_portfolio, historical_prices
        )

        # Should complete in reasonable time and produce valid result
        assert result.recommended_shares >= 0
        assert result.strategy == SizingStrategy.RISK_PARITY

    def test_multiple_strategy_performance(self, calculator, large_portfolio):
        """Test performance of calculating multiple strategies."""
        historical_prices = list(range(100, 130))

        results = calculator.calculate_multiple_strategies(
            "PERF",
            150.0,
            large_portfolio,
            stop_loss=140.0,
            historical_prices=historical_prices,
        )

        # Should calculate all strategies efficiently
        assert len(results) >= 5  # Should have multiple strategies

        for _strategy, result in results.items():
            assert isinstance(result, PositionSizeResult)
            assert result.recommended_shares >= 0

    def test_portfolio_allocation_performance(self, calculator, large_portfolio):
        """Test performance of portfolio allocation across many symbols."""
        symbols = [f"ALLOC{i:03d}" for i in range(20)]
        prices = {symbol: 100.0 + i for i, symbol in enumerate(symbols)}

        results = calculator.calculate_portfolio_allocation(
            symbols, prices, large_portfolio, SizingStrategy.FIXED_PERCENTAGE
        )

        # Should handle many symbols efficiently
        assert len(results) <= len(symbols)

        total_value = sum(result.position_value for result in results.values())
        assert total_value <= large_portfolio.cash_balance
