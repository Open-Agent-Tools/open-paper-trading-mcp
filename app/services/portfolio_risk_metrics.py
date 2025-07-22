"""
Portfolio risk metrics calculation including VaR and exposure limits.

This module provides comprehensive portfolio risk analysis including
Value at Risk (VaR), exposure measurements, correlation analysis,
and risk limit monitoring.
"""

import logging
import math
from dataclasses import dataclass, field
from datetime import datetime

import numpy as np
from scipy import stats

from ..models.assets import Option, Stock, asset_factory
from ..schemas.positions import Portfolio, Position

logger = logging.getLogger(__name__)


@dataclass
class VaRResult:
    """Value at Risk calculation result."""

    confidence_level: float
    time_horizon: int  # days
    var_amount: float
    var_percent: float
    expected_shortfall: float  # CVaR
    method: str  # historical, parametric, monte_carlo
    calculation_date: datetime = field(default_factory=datetime.utcnow)


@dataclass
class ExposureMetrics:
    """Portfolio exposure metrics."""

    gross_exposure: float
    net_exposure: float
    long_exposure: float
    short_exposure: float
    sector_exposures: dict[str, float]
    concentration_metrics: dict[str, float]
    leverage_ratio: float
    beta_weighted_exposure: float


@dataclass
class RiskBudgetAllocation:
    """Risk budget allocation across positions."""

    position_risk_contributions: dict[str, float]
    marginal_risk_contributions: dict[str, float]
    component_var: dict[str, float]
    diversification_ratio: float


@dataclass
class StressTestResult:
    """Stress test scenario result."""

    scenario_name: str
    portfolio_return: float
    position_impacts: dict[str, float]
    sector_impacts: dict[str, float]
    largest_losses: list[tuple[str, float]]


@dataclass
class PortfolioRiskSummary:
    """Comprehensive portfolio risk summary."""

    var_results: dict[float, VaRResult]  # confidence level -> VaR
    exposure_metrics: ExposureMetrics
    risk_budget: RiskBudgetAllocation
    stress_tests: list[StressTestResult]
    correlation_matrix: np.ndarray | None = None
    risk_alerts: list[str] = field(default_factory=list)
    calculation_timestamp: datetime = field(default_factory=datetime.utcnow)


class PortfolioRiskCalculator:
    """
    Calculate comprehensive portfolio risk metrics.

    Provides various risk measures including:
    - Value at Risk (VaR) using multiple methods
    - Expected Shortfall (CVaR)
    - Exposure analysis
    - Risk budget allocation
    - Stress testing
    - Correlation analysis
    """

    def __init__(self):
        self.price_history: dict[str, list[float]] = {}
        self.return_history: dict[str, list[float]] = {}
        self.sector_mappings = self._load_sector_mappings()
        self.correlation_cache: dict[str, np.ndarray] = {}

    def calculate_portfolio_risk(
        self,
        portfolio: Portfolio,
        historical_data: dict[str, list[float]] | None = None,
        confidence_levels: list[float] = None,
    ) -> PortfolioRiskSummary:
        """
        Calculate comprehensive portfolio risk metrics.

        Args:
            portfolio: Portfolio to analyze
            historical_data: Historical price data for positions
            confidence_levels: VaR confidence levels to calculate

        Returns:
            Complete portfolio risk summary
        """
        if confidence_levels is None:
            confidence_levels = [0.95, 0.99]

        logger.info(
            f"Calculating portfolio risk for {len(portfolio.positions)} positions"
        )

        # Calculate historical returns if data provided
        if historical_data:
            self._update_return_history(historical_data)

        # Calculate VaR for different confidence levels
        var_results = {}
        for confidence in confidence_levels:
            try:
                var_results[confidence] = self._calculate_var(
                    portfolio, confidence, historical_data
                )
            except Exception as e:
                logger.error(f"Error calculating VaR at {confidence}: {e}")

        # Calculate exposure metrics
        exposure_metrics = self._calculate_exposure_metrics(portfolio)

        # Calculate risk budget allocation
        risk_budget = self._calculate_risk_budget(portfolio, historical_data)

        # Run stress tests
        stress_tests = self._run_stress_tests(portfolio)

        # Generate risk alerts
        risk_alerts = self._generate_risk_alerts(
            portfolio, exposure_metrics, var_results
        )

        return PortfolioRiskSummary(
            var_results=var_results,
            exposure_metrics=exposure_metrics,
            risk_budget=risk_budget,
            stress_tests=stress_tests,
            risk_alerts=risk_alerts,
        )

    def _calculate_var(
        self,
        portfolio: Portfolio,
        confidence_level: float,
        historical_data: dict[str, list[float]] | None = None,
        time_horizon: int = 1,
    ) -> VaRResult:
        """Calculate Value at Risk using historical simulation."""
        if not historical_data:
            # Use simplified parametric VaR if no historical data
            return self._calculate_parametric_var(
                portfolio, confidence_level, time_horizon
            )

        # Calculate portfolio returns from historical data
        portfolio_returns = self._calculate_portfolio_returns(
            portfolio, historical_data
        )

        if len(portfolio_returns) < 30:
            logger.warning("Insufficient historical data for reliable VaR calculation")
            return self._calculate_parametric_var(
                portfolio, confidence_level, time_horizon
            )

        # Historical VaR
        sorted_returns = sorted(portfolio_returns)
        var_index = int((1 - confidence_level) * len(sorted_returns))
        var_return = sorted_returns[var_index]

        # Convert to dollar amount
        var_amount = abs(var_return * portfolio.total_value)
        var_percent = abs(var_return)

        # Expected Shortfall (average of losses beyond VaR)
        tail_losses = [r for r in sorted_returns if r <= var_return]
        expected_shortfall = (
            abs(np.mean(tail_losses) * portfolio.total_value)
            if tail_losses
            else var_amount
        )

        return VaRResult(
            confidence_level=confidence_level,
            time_horizon=time_horizon,
            var_amount=var_amount,
            var_percent=var_percent,
            expected_shortfall=expected_shortfall,
            method="historical",
        )

    def _calculate_parametric_var(
        self, portfolio: Portfolio, confidence_level: float, time_horizon: int = 1
    ) -> VaRResult:
        """Calculate parametric VaR using normal distribution assumption."""
        # Estimate portfolio volatility (simplified)
        estimated_daily_vol = 0.02  # 2% daily volatility assumption

        # Scale for time horizon
        vol_scaled = estimated_daily_vol * math.sqrt(time_horizon)

        # Calculate VaR using normal distribution
        z_score = stats.norm.ppf(1 - confidence_level)
        var_return = z_score * vol_scaled

        var_amount = abs(var_return * portfolio.total_value)
        var_percent = abs(var_return)

        # Expected shortfall for normal distribution
        expected_shortfall = (
            (stats.norm.pdf(z_score) / (1 - confidence_level))
            * vol_scaled
            * portfolio.total_value
        )

        return VaRResult(
            confidence_level=confidence_level,
            time_horizon=time_horizon,
            var_amount=var_amount,
            var_percent=var_percent,
            expected_shortfall=expected_shortfall,
            method="parametric",
        )

    def _calculate_portfolio_returns(
        self, portfolio: Portfolio, historical_data: dict[str, list[float]]
    ) -> list[float]:
        """Calculate historical portfolio returns."""
        # Get the minimum data length across all positions
        min_length = min(len(prices) for prices in historical_data.values())

        if min_length < 2:
            return []

        portfolio_returns = []

        for i in range(1, min_length):
            daily_return = 0.0
            total_weight = 0.0

            for position in portfolio.positions:
                symbol = position.symbol
                if symbol in historical_data:
                    prices = historical_data[symbol]
                    if i < len(prices):
                        # Calculate return
                        asset_return = (prices[i] - prices[i - 1]) / prices[i - 1]

                        # Weight by position value
                        position_weight = (
                            abs(position.quantity) * position.current_price
                        ) / portfolio.total_value

                        # Account for long/short
                        if position.quantity > 0:
                            daily_return += asset_return * position_weight
                        else:
                            daily_return -= asset_return * position_weight

                        total_weight += position_weight

            if total_weight > 0:
                portfolio_returns.append(daily_return)

        return portfolio_returns

    def _calculate_exposure_metrics(self, portfolio: Portfolio) -> ExposureMetrics:
        """Calculate various exposure metrics."""
        gross_exposure = 0.0
        long_exposure = 0.0
        short_exposure = 0.0
        sector_exposures: dict[str, float] = {}

        for position in portfolio.positions:
            position_value = abs(position.quantity) * position.current_price
            gross_exposure += position_value

            if position.quantity > 0:
                long_exposure += position_value
            else:
                short_exposure += position_value

            # Sector exposure
            sector = self.sector_mappings.get(position.symbol, "Unknown")
            sector_exposures[sector] = sector_exposures.get(sector, 0) + position_value

        net_exposure = long_exposure - short_exposure

        # Concentration metrics
        concentration_metrics = self._calculate_concentration_metrics(portfolio)

        # Leverage ratio
        if portfolio.cash_balance > 0:
            leverage_ratio = gross_exposure / portfolio.cash_balance
        else:
            leverage_ratio = float("inf")

        # Beta-weighted exposure (simplified - assume beta = 1)
        beta_weighted_exposure = net_exposure

        return ExposureMetrics(
            gross_exposure=gross_exposure,
            net_exposure=net_exposure,
            long_exposure=long_exposure,
            short_exposure=short_exposure,
            sector_exposures=sector_exposures,
            concentration_metrics=concentration_metrics,
            leverage_ratio=leverage_ratio,
            beta_weighted_exposure=beta_weighted_exposure,
        )

    def _calculate_concentration_metrics(
        self, portfolio: Portfolio
    ) -> dict[str, float]:
        """Calculate position concentration metrics."""
        position_weights = []

        for position in portfolio.positions:
            weight = (
                abs(position.quantity) * position.current_price
            ) / portfolio.total_value
            position_weights.append(weight)

        if not position_weights:
            return {}

        # Herfindahl-Hirschman Index
        hhi = sum(w**2 for w in position_weights)

        # Effective number of positions
        effective_positions = 1 / hhi if hhi > 0 else 0

        # Largest position concentration
        max_concentration = max(position_weights) if position_weights else 0

        # Top 3 concentration
        sorted_weights = sorted(position_weights, reverse=True)
        top3_concentration = (
            sum(sorted_weights[:3]) if len(sorted_weights) >= 3 else sum(sorted_weights)
        )

        return {
            "herfindahl_index": hhi,
            "effective_positions": effective_positions,
            "max_concentration": max_concentration,
            "top3_concentration": top3_concentration,
        }

    def _calculate_risk_budget(
        self,
        portfolio: Portfolio,
        historical_data: dict[str, list[float]] | None = None,
    ) -> RiskBudgetAllocation:
        """Calculate risk budget allocation across positions."""
        position_risk_contributions: dict[str, float] = {}
        marginal_risk_contributions: dict[str, float] = {}
        component_var: dict[str, float] = {}

        total_portfolio_var = (
            portfolio.total_value * 0.02
        )  # Simplified 2% portfolio VaR

        for position in portfolio.positions:
            symbol = position.symbol
            position_value = abs(position.quantity) * position.current_price
            position_weight = position_value / portfolio.total_value

            # Simplified risk contribution (proportional to weight)
            risk_contribution = position_weight * total_portfolio_var
            position_risk_contributions[symbol] = risk_contribution

            # Marginal risk contribution (derivative of portfolio VaR w.r.t. position weight)
            marginal_risk = (
                risk_contribution / position_weight if position_weight > 0 else 0
            )
            marginal_risk_contributions[symbol] = marginal_risk

            # Component VaR
            component_var[symbol] = risk_contribution

        # Diversification ratio
        sum_individual_risks = sum(position_risk_contributions.values())
        diversification_ratio = (
            total_portfolio_var / sum_individual_risks
            if sum_individual_risks > 0
            else 0
        )

        return RiskBudgetAllocation(
            position_risk_contributions=position_risk_contributions,
            marginal_risk_contributions=marginal_risk_contributions,
            component_var=component_var,
            diversification_ratio=diversification_ratio,
        )

    def _run_stress_tests(self, portfolio: Portfolio) -> list[StressTestResult]:
        """Run various stress test scenarios."""
        stress_tests = []

        # Market crash scenario (-20% across all positions)
        market_crash = self._stress_test_scenario(
            portfolio, "Market Crash", {"all": -0.20}
        )
        stress_tests.append(market_crash)

        # Sector rotation (Technology -15%, Financials +10%)
        sector_rotation = self._stress_test_scenario(
            portfolio, "Sector Rotation", {"Technology": -0.15, "Financials": 0.10}
        )
        stress_tests.append(sector_rotation)

        # Interest rate shock (affects options differently)
        interest_shock = self._stress_test_scenario(
            portfolio, "Interest Rate Shock", {"all": -0.05}
        )
        stress_tests.append(interest_shock)

        # Volatility spike
        vol_spike = self._stress_test_scenario(
            portfolio, "Volatility Spike", {"options": 0.30, "stocks": -0.10}
        )
        stress_tests.append(vol_spike)

        return stress_tests

    def _stress_test_scenario(
        self, portfolio: Portfolio, scenario_name: str, shocks: dict[str, float]
    ) -> StressTestResult:
        """Apply stress test scenario to portfolio."""
        portfolio_return = 0.0
        position_impacts: dict[str, float] = {}
        sector_impacts: dict[str, float] = {}

        for position in portfolio.positions:
            symbol = position.symbol
            asset = asset_factory(symbol)
            sector = self.sector_mappings.get(symbol, "Unknown")

            # Determine shock to apply
            shock = 0.0

            # Check for specific sector shocks
            if sector in shocks:
                shock = shocks[sector]
            elif "options" in shocks and isinstance(asset, Option):
                shock = shocks["options"]
            elif "stocks" in shocks and isinstance(asset, Stock):
                shock = shocks["stocks"]
            elif "all" in shocks:
                shock = shocks["all"]

            # Calculate position impact
            position_value = abs(position.quantity) * position.current_price
            position_impact = position_value * shock

            # Account for long/short
            if position.quantity < 0:
                position_impact = -position_impact

            position_impacts[symbol] = position_impact
            portfolio_return += position_impact

            # Aggregate sector impacts
            sector_impacts[sector] = sector_impacts.get(sector, 0) + position_impact

        # Find largest losses
        largest_losses = sorted(
            [
                (symbol, impact)
                for symbol, impact in position_impacts.items()
                if impact < 0
            ],
            key=lambda x: x[1],
        )[:5]

        return StressTestResult(
            scenario_name=scenario_name,
            portfolio_return=portfolio_return,
            position_impacts=position_impacts,
            sector_impacts=sector_impacts,
            largest_losses=largest_losses,
        )

    def _generate_risk_alerts(
        self,
        portfolio: Portfolio,
        exposure_metrics: ExposureMetrics,
        var_results: dict[float, VaRResult],
    ) -> list[str]:
        """Generate risk alerts based on metrics."""
        alerts = []

        # High concentration alert
        max_concentration = exposure_metrics.concentration_metrics.get(
            "max_concentration", 0
        )
        if max_concentration > 0.20:  # 20% threshold
            alerts.append(
                f"High position concentration: {max_concentration:.1%} in single position"
            )

        # High leverage alert
        if exposure_metrics.leverage_ratio > 2.0:
            alerts.append(f"High leverage: {exposure_metrics.leverage_ratio:.1f}x")

        # Large short exposure
        if exposure_metrics.short_exposure > exposure_metrics.long_exposure * 0.5:
            alerts.append("Significant short exposure relative to long positions")

        # High VaR alert
        if 0.95 in var_results:
            var_95 = var_results[0.95]
            var_percent_of_portfolio = var_95.var_amount / portfolio.total_value
            if var_percent_of_portfolio > 0.05:  # 5% of portfolio
                alerts.append(
                    f"High VaR: {var_percent_of_portfolio:.1%} of portfolio at risk"
                )

        # Sector concentration
        for sector, exposure in exposure_metrics.sector_exposures.items():
            sector_percent = exposure / portfolio.total_value
            if sector_percent > 0.40:  # 40% threshold
                alerts.append(f"High {sector} sector exposure: {sector_percent:.1%}")

        # Low diversification
        effective_positions = exposure_metrics.concentration_metrics.get(
            "effective_positions", 0
        )
        if effective_positions < 5:
            alerts.append(
                f"Low diversification: effective positions = {effective_positions:.1f}"
            )

        return alerts

    def calculate_position_var(
        self,
        position: Position,
        confidence_level: float = 0.95,
        time_horizon: int = 1,
        historical_prices: list[float] | None = None,
    ) -> VaRResult:
        """Calculate VaR for a single position."""
        position_value = abs(position.quantity) * position.current_price

        if historical_prices and len(historical_prices) > 1:
            # Historical VaR
            returns = [
                (historical_prices[i] - historical_prices[i - 1])
                / historical_prices[i - 1]
                for i in range(1, len(historical_prices))
            ]

            sorted_returns = sorted(returns)
            var_index = int((1 - confidence_level) * len(sorted_returns))
            var_return = sorted_returns[var_index]

            var_amount = abs(var_return * position_value)
            var_percent = abs(var_return)

            # Expected shortfall
            tail_losses = [r for r in sorted_returns if r <= var_return]
            expected_shortfall = (
                abs(np.mean(tail_losses) * position_value)
                if tail_losses
                else var_amount
            )

            method = "historical"
        else:
            # Parametric VaR
            estimated_vol = 0.025  # 2.5% daily volatility
            z_score = stats.norm.ppf(1 - confidence_level)
            var_return = z_score * estimated_vol

            var_amount = abs(var_return * position_value)
            var_percent = abs(var_return)
            expected_shortfall = (
                (stats.norm.pdf(z_score) / (1 - confidence_level))
                * estimated_vol
                * position_value
            )

            method = "parametric"

        return VaRResult(
            confidence_level=confidence_level,
            time_horizon=time_horizon,
            var_amount=var_amount,
            var_percent=var_percent,
            expected_shortfall=expected_shortfall,
            method=method,
        )

    def calculate_correlation_matrix(
        self, symbols: list[str], historical_data: dict[str, list[float]]
    ) -> np.ndarray:
        """Calculate correlation matrix for given symbols."""
        # Calculate returns for each symbol
        returns_data = {}

        for symbol in symbols:
            if symbol in historical_data:
                prices = historical_data[symbol]
                returns = [
                    (prices[i] - prices[i - 1]) / prices[i - 1]
                    for i in range(1, len(prices))
                ]
                returns_data[symbol] = returns

        if not returns_data:
            return np.eye(len(symbols))

        # Create correlation matrix
        min_length = min(len(returns) for returns in returns_data.values())

        returns_matrix = []
        for symbol in symbols:
            if symbol in returns_data:
                returns_matrix.append(returns_data[symbol][:min_length])
            else:
                # Use zeros if no data
                returns_matrix.append([0.0] * min_length)

        return np.corrcoef(returns_matrix)

    def _update_return_history(self, historical_data: dict[str, list[float]]) -> None:
        """Update internal return history cache."""
        for symbol, prices in historical_data.items():
            if len(prices) > 1:
                returns = [
                    (prices[i] - prices[i - 1]) / prices[i - 1]
                    for i in range(1, len(prices))
                ]
                self.return_history[symbol] = returns

    def _load_sector_mappings(self) -> dict[str, str]:
        """Load sector mappings for symbols."""
        # Simplified - in production would load from database
        return {
            "AAPL": "Technology",
            "MSFT": "Technology",
            "GOOGL": "Technology",
            "AMZN": "Consumer Discretionary",
            "TSLA": "Consumer Discretionary",
            "JPM": "Financials",
            "BAC": "Financials",
            "GS": "Financials",
            "XOM": "Energy",
            "CVX": "Energy",
            "JNJ": "Healthcare",
            "PFE": "Healthcare",
            "PG": "Consumer Staples",
            "KO": "Consumer Staples",
            # Add more mappings as needed
        }


# Global portfolio risk calculator
portfolio_risk_calculator = PortfolioRiskCalculator()


def get_portfolio_risk_calculator() -> PortfolioRiskCalculator:
    """Get the global portfolio risk calculator."""
    return portfolio_risk_calculator
