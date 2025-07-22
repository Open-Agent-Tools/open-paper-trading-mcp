"""
Position sizing calculators for optimal trade sizing.

This module provides various position sizing strategies including
Kelly Criterion, fixed fractional, volatility-based, and risk parity approaches.
"""

import logging
import math
from dataclasses import dataclass, field
from enum import Enum

import numpy as np

from ..schemas.positions import Portfolio

logger = logging.getLogger(__name__)


class SizingStrategy(str, Enum):
    """Position sizing strategies."""

    FIXED_DOLLAR = "fixed_dollar"
    FIXED_PERCENTAGE = "fixed_percentage"
    KELLY_CRITERION = "kelly_criterion"
    VOLATILITY_BASED = "volatility_based"
    RISK_PARITY = "risk_parity"
    MAX_LOSS = "max_loss"
    ATR_BASED = "atr_based"


@dataclass
class PositionSizeResult:
    """Result from position sizing calculation."""

    strategy: SizingStrategy
    recommended_shares: int
    position_value: float
    percent_of_portfolio: float
    risk_amount: float
    stop_loss_price: float | None = None
    confidence_level: float = 0.95
    notes: list[str] = field(default_factory=list)

    def __post_init__(self):
        if self.notes is None:
            self.notes = []


@dataclass
class SizingParameters:
    """Parameters for position sizing calculations."""

    # Risk parameters
    max_risk_per_trade: float = 0.02  # 2% risk per trade
    max_position_size: float = 0.20  # 20% max position
    min_position_size: float = 0.01  # 1% min position

    # Kelly parameters
    win_rate: float = 0.55  # Historical win rate
    average_win: float = 1.5  # Average win size
    average_loss: float = 1.0  # Average loss size
    kelly_fraction: float = 0.25  # Fractional Kelly (25%)

    # Volatility parameters
    target_volatility: float = 0.16  # 16% annual volatility
    lookback_period: int = 20  # Days for volatility calc

    # Risk parity parameters
    risk_budget: float = 0.10  # 10% risk budget


class PositionSizingCalculator:
    """
    Calculate optimal position sizes using various strategies.

    Provides multiple position sizing methods to help traders
    determine appropriate trade sizes based on risk tolerance,
    market conditions, and portfolio constraints.
    """

    def __init__(self, parameters: SizingParameters | None = None):
        self.parameters = parameters or SizingParameters()
        self.price_history: dict[str, list[float]] = {}  # Simplified price history

    def calculate_position_size(
        self,
        symbol: str,
        current_price: float,
        portfolio: Portfolio,
        strategy: SizingStrategy,
        stop_loss: float | None = None,
        historical_prices: list[float] | None = None,
    ) -> PositionSizeResult:
        """
        Calculate position size using specified strategy.

        Args:
            symbol: Symbol to size position for
            current_price: Current market price
            portfolio: Current portfolio state
            strategy: Sizing strategy to use
            stop_loss: Stop loss price if applicable
            historical_prices: Historical prices for volatility calculations

        Returns:
            Position sizing result with recommendations
        """
        logger.info(f"Calculating position size for {symbol} using {strategy} strategy")

        if strategy == SizingStrategy.FIXED_DOLLAR:
            return self._fixed_dollar_sizing(symbol, current_price, portfolio)

        elif strategy == SizingStrategy.FIXED_PERCENTAGE:
            return self._fixed_percentage_sizing(symbol, current_price, portfolio)

        elif strategy == SizingStrategy.KELLY_CRITERION:
            return self._kelly_criterion_sizing(symbol, current_price, portfolio)

        elif strategy == SizingStrategy.VOLATILITY_BASED:
            return self._volatility_based_sizing(
                symbol, current_price, portfolio, historical_prices
            )

        elif strategy == SizingStrategy.RISK_PARITY:
            return self._risk_parity_sizing(
                symbol, current_price, portfolio, historical_prices
            )

        elif strategy == SizingStrategy.MAX_LOSS:
            return self._max_loss_sizing(symbol, current_price, portfolio, stop_loss)

        elif strategy == SizingStrategy.ATR_BASED:
            return self._atr_based_sizing(
                symbol, current_price, portfolio, historical_prices
            )
        else:
            raise ValueError(f"Unknown sizing strategy: {strategy}")

    def calculate_multiple_strategies(
        self,
        symbol: str,
        current_price: float,
        portfolio: Portfolio,
        stop_loss: float | None = None,
        historical_prices: list[float] | None = None,
    ) -> dict[SizingStrategy, PositionSizeResult]:
        """Calculate position sizes using all applicable strategies."""
        results = {}

        # Always available strategies
        for strategy in [
            SizingStrategy.FIXED_DOLLAR,
            SizingStrategy.FIXED_PERCENTAGE,
            SizingStrategy.KELLY_CRITERION,
        ]:
            try:
                results[strategy] = self.calculate_position_size(
                    symbol,
                    current_price,
                    portfolio,
                    strategy,
                    stop_loss,
                    historical_prices,
                )
            except Exception as e:
                logger.error(f"Error calculating {strategy}: {e}")

        # Strategies requiring stop loss
        if stop_loss:
            try:
                results[SizingStrategy.MAX_LOSS] = self.calculate_position_size(
                    symbol,
                    current_price,
                    portfolio,
                    SizingStrategy.MAX_LOSS,
                    stop_loss,
                    historical_prices,
                )
            except Exception as e:
                logger.error(f"Error calculating MAX_LOSS: {e}")

        # Strategies requiring historical data
        if (
            historical_prices
            and len(historical_prices) >= self.parameters.lookback_period
        ):
            for strategy in [
                SizingStrategy.VOLATILITY_BASED,
                SizingStrategy.RISK_PARITY,
                SizingStrategy.ATR_BASED,
            ]:
                try:
                    results[strategy] = self.calculate_position_size(
                        symbol,
                        current_price,
                        portfolio,
                        strategy,
                        stop_loss,
                        historical_prices,
                    )
                except Exception as e:
                    logger.error(f"Error calculating {strategy}: {e}")

        return results

    def _fixed_dollar_sizing(
        self, symbol: str, current_price: float, portfolio: Portfolio
    ) -> PositionSizeResult:
        """Fixed dollar amount per position."""
        # Use 5% of portfolio value as fixed amount
        fixed_amount = portfolio.total_value * 0.05
        shares = int(fixed_amount / current_price)

        # Apply constraints
        shares = self._apply_constraints(shares, current_price, portfolio)

        position_value = shares * current_price
        percent_of_portfolio = position_value / portfolio.total_value

        return PositionSizeResult(
            strategy=SizingStrategy.FIXED_DOLLAR,
            recommended_shares=shares,
            position_value=position_value,
            percent_of_portfolio=percent_of_portfolio,
            risk_amount=position_value * self.parameters.max_risk_per_trade,
            notes=[f"Fixed amount: ${fixed_amount:.2f}"],
        )

    def _fixed_percentage_sizing(
        self, symbol: str, current_price: float, portfolio: Portfolio
    ) -> PositionSizeResult:
        """Fixed percentage of portfolio per position."""
        # Use 10% of portfolio as default
        target_percent = 0.10
        position_value = portfolio.total_value * target_percent
        shares = int(position_value / current_price)

        # Apply constraints
        shares = self._apply_constraints(shares, current_price, portfolio)

        actual_value = shares * current_price
        actual_percent = actual_value / portfolio.total_value

        return PositionSizeResult(
            strategy=SizingStrategy.FIXED_PERCENTAGE,
            recommended_shares=shares,
            position_value=actual_value,
            percent_of_portfolio=actual_percent,
            risk_amount=actual_value * self.parameters.max_risk_per_trade,
            notes=[f"Target: {target_percent:.1%} of portfolio"],
        )

    def _kelly_criterion_sizing(
        self, symbol: str, current_price: float, portfolio: Portfolio
    ) -> PositionSizeResult:
        """Kelly Criterion position sizing."""
        # Calculate Kelly percentage
        # f* = (p * b - q) / b
        # where p = win rate, q = loss rate, b = win/loss ratio

        p = self.parameters.win_rate
        q = 1 - p
        b = self.parameters.average_win / self.parameters.average_loss

        kelly_percent = (p * b - q) / b

        # Apply fractional Kelly
        kelly_percent *= self.parameters.kelly_fraction

        # Ensure within bounds
        kelly_percent = max(0, min(kelly_percent, self.parameters.max_position_size))

        position_value = portfolio.total_value * kelly_percent
        shares = int(position_value / current_price)

        # Apply constraints
        shares = self._apply_constraints(shares, current_price, portfolio)

        actual_value = shares * current_price
        actual_percent = actual_value / portfolio.total_value

        return PositionSizeResult(
            strategy=SizingStrategy.KELLY_CRITERION,
            recommended_shares=shares,
            position_value=actual_value,
            percent_of_portfolio=actual_percent,
            risk_amount=actual_value * self.parameters.max_risk_per_trade,
            confidence_level=p,
            notes=[
                f"Kelly %: {kelly_percent:.1%}",
                f"Win rate: {p:.1%}",
                f"Win/Loss ratio: {b:.2f}",
            ],
        )

    def _volatility_based_sizing(
        self,
        symbol: str,
        current_price: float,
        portfolio: Portfolio,
        historical_prices: list[float] | None,
    ) -> PositionSizeResult:
        """Size position based on volatility targeting."""
        if not historical_prices or len(historical_prices) < 2:
            raise ValueError("Insufficient price history for volatility calculation")

        # Calculate historical volatility
        returns = [
            (historical_prices[i] - historical_prices[i - 1]) / historical_prices[i - 1]
            for i in range(1, len(historical_prices))
        ]

        daily_vol = np.std(returns) if returns else 0.01
        annual_vol = daily_vol * math.sqrt(252)  # Annualize

        # Target position size to achieve target portfolio volatility
        if annual_vol > 0:
            volatility_scalar = self.parameters.target_volatility / annual_vol
        else:
            volatility_scalar = 1.0

        # Base position size (e.g., 10% of portfolio)
        base_position = 0.10
        adjusted_position = base_position * volatility_scalar

        # Apply constraints
        adjusted_position = max(
            self.parameters.min_position_size,
            min(adjusted_position, self.parameters.max_position_size),
        )

        position_value = portfolio.total_value * adjusted_position
        shares = int(position_value / current_price)

        # Apply share constraints
        shares = self._apply_constraints(shares, current_price, portfolio)

        actual_value = shares * current_price
        actual_percent = actual_value / portfolio.total_value

        return PositionSizeResult(
            strategy=SizingStrategy.VOLATILITY_BASED,
            recommended_shares=shares,
            position_value=actual_value,
            percent_of_portfolio=actual_percent,
            risk_amount=float(actual_value * daily_vol * 2),  # 2 std dev risk
            notes=[
                f"Annual volatility: {annual_vol:.1%}",
                f"Volatility scalar: {volatility_scalar:.2f}",
                f"Target vol: {self.parameters.target_volatility:.1%}",
            ],
        )

    def _risk_parity_sizing(
        self,
        symbol: str,
        current_price: float,
        portfolio: Portfolio,
        historical_prices: list[float] | None,
    ) -> PositionSizeResult:
        """Risk parity position sizing."""
        if not historical_prices or len(historical_prices) < 2:
            raise ValueError("Insufficient price history for risk parity calculation")

        # Calculate asset volatility
        returns = [
            (historical_prices[i] - historical_prices[i - 1]) / historical_prices[i - 1]
            for i in range(1, len(historical_prices))
        ]

        asset_vol = np.std(returns) if returns else 0.01

        # Calculate position volatilities for existing positions
        position_risks = []
        total_risk = 0.0

        for position in portfolio.positions:
            # Skip positions with no current price
            if position.current_price is None:
                continue

            # Simplified - assume equal volatility for existing positions
            pos_risk = (
                abs(position.quantity) * position.current_price * 0.02
            )  # 2% daily vol
            position_risks.append(pos_risk)
            total_risk += pos_risk

        # Allocate risk budget to new position
        if total_risk > 0:
            available_risk = (
                portfolio.total_value * self.parameters.risk_budget - total_risk
            )
            available_risk = max(0, available_risk)
        else:
            available_risk = portfolio.total_value * self.parameters.risk_budget

        # Calculate position size to use available risk
        if asset_vol > 0:
            position_value = available_risk / asset_vol
        else:
            position_value = available_risk / 0.02  # Default 2% vol

        shares = int(position_value / current_price)

        # Apply constraints
        shares = self._apply_constraints(shares, current_price, portfolio)

        actual_value = shares * current_price
        actual_percent = actual_value / portfolio.total_value
        actual_risk = actual_value * asset_vol

        return PositionSizeResult(
            strategy=SizingStrategy.RISK_PARITY,
            recommended_shares=shares,
            position_value=actual_value,
            percent_of_portfolio=actual_percent,
            risk_amount=float(actual_risk),
            notes=[
                f"Asset volatility: {asset_vol:.1%}",
                f"Risk budget: {self.parameters.risk_budget:.1%}",
                f"Risk allocation: {actual_risk / portfolio.total_value:.1%}",
            ],
        )

    def _max_loss_sizing(
        self,
        symbol: str,
        current_price: float,
        portfolio: Portfolio,
        stop_loss: float | None,
    ) -> PositionSizeResult:
        """Size position based on maximum acceptable loss."""
        if not stop_loss:
            raise ValueError("Stop loss price required for max loss sizing")

        if stop_loss >= current_price:
            raise ValueError("Stop loss must be below current price for long positions")

        # Calculate risk per share
        risk_per_share = current_price - stop_loss

        # Maximum risk amount
        max_risk_amount = portfolio.total_value * self.parameters.max_risk_per_trade

        # Calculate shares based on max risk
        shares = int(max_risk_amount / risk_per_share)

        # Apply constraints
        shares = self._apply_constraints(shares, current_price, portfolio)

        actual_value = shares * current_price
        actual_percent = actual_value / portfolio.total_value
        actual_risk = shares * risk_per_share

        return PositionSizeResult(
            strategy=SizingStrategy.MAX_LOSS,
            recommended_shares=shares,
            position_value=actual_value,
            percent_of_portfolio=actual_percent,
            risk_amount=actual_risk,
            stop_loss_price=stop_loss,
            notes=[
                f"Risk per share: ${risk_per_share:.2f}",
                f"Max risk: ${max_risk_amount:.2f}",
                f"Stop loss: ${stop_loss:.2f}",
            ],
        )

    def _atr_based_sizing(
        self,
        symbol: str,
        current_price: float,
        portfolio: Portfolio,
        historical_prices: list[float] | None,
    ) -> PositionSizeResult:
        """Size position based on Average True Range (ATR)."""
        if (
            not historical_prices
            or len(historical_prices) < self.parameters.lookback_period
        ):
            raise ValueError("Insufficient price history for ATR calculation")

        # Calculate ATR (simplified - using daily ranges)
        atr_values = []
        for i in range(1, len(historical_prices)):
            # Simplified ATR using price changes
            daily_range = abs(historical_prices[i] - historical_prices[i - 1])
            atr_values.append(daily_range)

        if atr_values:
            atr = float(np.mean(atr_values[-self.parameters.lookback_period :]))
        else:
            atr = current_price * 0.02  # Default 2% ATR

        # Risk 2 ATRs
        risk_amount = portfolio.total_value * self.parameters.max_risk_per_trade
        risk_in_atrs = 2.0  # Risk 2 ATRs

        shares = int(risk_amount / (atr * risk_in_atrs))

        # Apply constraints
        shares = self._apply_constraints(shares, current_price, portfolio)

        actual_value = shares * current_price
        actual_percent = actual_value / portfolio.total_value
        actual_risk = shares * atr * risk_in_atrs

        # Calculate stop loss based on ATR
        stop_loss = current_price - (atr * risk_in_atrs)

        return PositionSizeResult(
            strategy=SizingStrategy.ATR_BASED,
            recommended_shares=shares,
            position_value=actual_value,
            percent_of_portfolio=actual_percent,
            risk_amount=float(actual_risk),
            stop_loss_price=float(stop_loss),
            notes=[
                f"ATR: ${atr:.2f}",
                f"Risk in ATRs: {risk_in_atrs}",
                f"ATR-based stop: ${stop_loss:.2f}",
            ],
        )

    def _apply_constraints(
        self, shares: int, price: float, portfolio: Portfolio
    ) -> int:
        """Apply position sizing constraints."""
        # Minimum position size
        min_value = portfolio.total_value * self.parameters.min_position_size
        min_shares = max(1, int(min_value / price))

        # Maximum position size
        max_value = portfolio.total_value * self.parameters.max_position_size
        max_shares = int(max_value / price)

        # Cash constraint
        available_cash = portfolio.cash_balance * 0.95  # Keep 5% buffer
        max_affordable = int(available_cash / price)

        # Apply all constraints
        shares = int(
            max(
                float(min_shares),
                min(float(shares), float(max_shares), float(max_affordable)),
            )
        )

        return shares

    def calculate_portfolio_allocation(
        self,
        symbols: list[str],
        current_prices: dict[str, float],
        portfolio: Portfolio,
        strategy: SizingStrategy,
    ) -> dict[str, PositionSizeResult]:
        """
        Calculate position sizes for multiple symbols.

        Useful for portfolio construction and rebalancing.
        """
        results = {}
        remaining_capital = portfolio.cash_balance

        for symbol in symbols:
            if symbol not in current_prices:
                continue

            # Create temporary portfolio with remaining capital
            temp_portfolio = Portfolio(
                cash_balance=remaining_capital,
                positions=portfolio.positions,
                total_value=portfolio.total_value,
                daily_pnl=portfolio.daily_pnl,
                total_pnl=portfolio.total_pnl,
            )

            result = self.calculate_position_size(
                symbol, current_prices[symbol], temp_portfolio, strategy
            )

            results[symbol] = result

            # Deduct allocated capital
            remaining_capital -= result.position_value

            if remaining_capital <= 0:
                break

        return results

    def suggest_position_size(
        self,
        symbol: str,
        current_price: float,
        portfolio: Portfolio,
        risk_tolerance: str = "moderate",
        stop_loss: float | None = None,
    ) -> PositionSizeResult:
        """
        Suggest position size based on risk tolerance.

        Args:
            symbol: Symbol to size
            current_price: Current price
            portfolio: Portfolio state
            risk_tolerance: low, moderate, high
            stop_loss: Optional stop loss price

        Returns:
            Recommended position size
        """
        # Map risk tolerance to strategy
        strategy_map = {
            "low": SizingStrategy.FIXED_PERCENTAGE,
            "moderate": SizingStrategy.VOLATILITY_BASED,
            "high": SizingStrategy.KELLY_CRITERION,
        }

        strategy = strategy_map.get(risk_tolerance, SizingStrategy.FIXED_PERCENTAGE)

        # Use max loss if stop loss provided
        if stop_loss:
            strategy = SizingStrategy.MAX_LOSS

        return self.calculate_position_size(
            symbol, current_price, portfolio, strategy, stop_loss
        )


# Global position sizing calculator
position_calculator = PositionSizingCalculator()


def get_position_calculator() -> PositionSizingCalculator:
    """Get the global position sizing calculator."""
    return position_calculator


def configure_sizing_parameters(parameters: SizingParameters) -> None:
    """Configure position sizing parameters."""
    global position_calculator
    position_calculator = PositionSizingCalculator(parameters)
