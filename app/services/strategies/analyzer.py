"""
Advanced strategy analyzer.

This module provides sophisticated strategy analysis including P&L calculation,
Greeks aggregation, complex strategy detection, and optimization recommendations.
"""

from datetime import date
from typing import Any

from ...models.assets import Call, Option, Put
from ...models.quotes import OptionQuote, Quote
from ...schemas.positions import Position
from .models import (AssetStrategy, BasicStrategy, ComplexStrategy,
                     CoveredStrategy, SpreadStrategy, StrategyGreeks,
                     StrategyPnL)
from .recognition import StrategyRecognitionService


class AdvancedStrategyAnalyzer:
    """Advanced strategy analysis with P&L calculation and Greeks aggregation."""

    def __init__(self) -> None:
        self.basic_analyzer = StrategyRecognitionService()

    def analyze_strategy_pnl(
        self,
        positions: list[Position],
        current_quotes: dict[str, Quote | OptionQuote],
        entry_date: date | None = None,
    ) -> list[StrategyPnL]:
        """
        Calculate comprehensive P&L analysis for all strategies.

        Args:
            positions: Portfolio positions
            current_quotes: Current market quotes
            entry_date: Strategy entry date for time-based metrics

        Returns:
            List of StrategyPnL objects with detailed analysis
        """
        strategies = self.basic_analyzer.group_positions_by_strategy(positions)
        strategy_pnls = []

        for strategy in strategies:
            pnl = self._calculate_strategy_pnl(
                strategy, positions, current_quotes, entry_date
            )
            strategy_pnls.append(pnl)

        return strategy_pnls

    def aggregate_strategy_greeks(
        self,
        positions: list[Position],
        current_quotes: dict[str, Quote | OptionQuote],
    ) -> StrategyGreeks:
        """
        Aggregate Greeks across all strategy positions.

        Args:
            positions: Portfolio positions with options
            current_quotes: Current market quotes with Greeks

        Returns:
            StrategyGreeks with aggregated exposure
        """
        total_greeks = StrategyGreeks(
            delta=0.0,
            gamma=0.0,
            theta=0.0,
            vega=0.0,
            rho=0.0,
            delta_normalized=0.0,
            gamma_normalized=0.0,
            theta_normalized=0.0,
            vega_normalized=0.0,
            delta_dollars=0.0,
            gamma_dollars=0.0,
            theta_dollars=0.0,
        )
        total_investment = 0.0
        underlying_price = 0.0

        for position in positions:
            if isinstance(position.asset, Option) and position.quantity != 0:
                symbol = position.symbol
                quote = current_quotes.get(symbol)

                if isinstance(quote, OptionQuote) and quote.delta is not None:
                    # Get position multiplier (100 for options)
                    multiplier = getattr(position, "multiplier", 100)
                    position_size = position.quantity * multiplier

                    # Aggregate Greeks
                    total_greeks.delta += (quote.delta or 0.0) * position_size
                    total_greeks.gamma += (quote.gamma or 0.0) * position_size
                    total_greeks.theta += (quote.theta or 0.0) * position_size
                    total_greeks.vega += (quote.vega or 0.0) * position_size
                    total_greeks.rho += (quote.rho or 0.0) * position_size

                    # Track investment for normalization
                    position_value = abs(
                        position.quantity * (quote.price or 0.0) * multiplier
                    )
                    total_investment += position_value

                    # Get underlying price for dollar Greeks
                    if hasattr(quote, "underlying_price") and quote.underlying_price:
                        underlying_price = quote.underlying_price

        # Calculate normalized Greeks (per $1000 invested)
        if total_investment > 0:
            normalization_factor = 1000.0 / total_investment
            total_greeks.delta_normalized = total_greeks.delta * normalization_factor
            total_greeks.gamma_normalized = total_greeks.gamma * normalization_factor
            total_greeks.theta_normalized = total_greeks.theta * normalization_factor
            total_greeks.vega_normalized = total_greeks.vega * normalization_factor

        # Calculate dollar Greeks
        if underlying_price > 0:
            total_greeks.delta_dollars = total_greeks.delta * underlying_price
            total_greeks.gamma_dollars = total_greeks.gamma * underlying_price
            total_greeks.theta_dollars = total_greeks.theta

        return total_greeks

    def detect_complex_strategies(
        self, positions: list[Position]
    ) -> list[ComplexStrategy]:
        """
        Detect complex multi-leg strategies.

        Args:
            positions: Portfolio positions

        Returns:
            List of detected complex strategies
        """
        complex_strategies = []

        # Group positions by underlying
        by_underlying: dict[str, list[Position]] = {}
        for position in positions:
            if isinstance(position.asset, Option):
                underlying = position.asset.underlying.symbol
                if underlying not in by_underlying:
                    by_underlying[underlying] = []
                by_underlying[underlying].append(position)

        # Analyze each underlying for complex strategies
        for underlying_symbol, underlying_positions in by_underlying.items():
            strategies = self._detect_complex_for_underlying(
                underlying_symbol, underlying_positions
            )
            complex_strategies.extend(strategies)

        return complex_strategies

    def generate_optimization_recommendations(
        self,
        positions: list[Position],
        current_quotes: dict[str, Quote | OptionQuote],
    ) -> list[dict[str, Any]]:
        """
        Generate strategy optimization recommendations.

        Args:
            positions: Current portfolio positions
            current_quotes: Current market quotes

        Returns:
            List of optimization recommendations
        """
        recommendations = []

        # Analyze current Greeks exposure
        greeks = self.aggregate_strategy_greeks(positions, current_quotes)

        # Check for excessive exposures
        if abs(greeks.delta) > 1000:  # High delta exposure
            recommendations.append(
                {
                    "type": "hedge_delta",
                    "priority": "high",
                    "description": f"High delta exposure ({greeks.delta:.0f}). Consider delta hedging.",
                    "suggested_action": "hedge_delta_exposure",
                    "target_delta": 0,
                    "current_delta": greeks.delta,
                }
            )

        if greeks.theta < -100:  # High theta decay
            recommendations.append(
                {
                    "type": "manage_theta",
                    "priority": "medium",
                    "description": f"High theta decay ({greeks.theta:.2f}/day). Consider rolling positions.",
                    "suggested_action": "roll_short_options",
                    "daily_decay": greeks.theta,
                }
            )

        if abs(greeks.vega) > 500:  # High vega exposure
            recommendations.append(
                {
                    "type": "hedge_vega",
                    "priority": "medium",
                    "description": f"High vega exposure ({greeks.vega:.0f}).",
                    "suggested_action": "hedge_volatility",
                    "current_vega": greeks.vega,
                }
            )

        # Strategy-specific recommendations
        strategy_recommendations = self._generate_strategy_specific_recommendations(
            positions, current_quotes
        )
        recommendations.extend(strategy_recommendations)

        return recommendations

    def _calculate_strategy_pnl(
        self,
        strategy: BasicStrategy,
        all_positions: list[Position],
        current_quotes: dict[str, Quote | OptionQuote],
        entry_date: date | None,
    ) -> StrategyPnL:
        """Calculate P&L for a specific strategy."""

        # Find positions that belong to this strategy
        strategy_positions = self._get_strategy_positions(strategy, all_positions)

        total_cost_basis = 0.0
        total_market_value = 0.0
        total_realized_pnl = 0.0

        for position in strategy_positions:
            quote = current_quotes.get(position.symbol)
            if quote is None:
                continue

            # Calculate position values
            multiplier = getattr(position, "multiplier", 1)
            cost_basis = position.avg_price * abs(position.quantity) * multiplier
            market_value = (quote.price or 0.0) * abs(position.quantity) * multiplier

            total_cost_basis += cost_basis
            total_market_value += market_value
            total_realized_pnl += getattr(position, "realized_pnl", 0.0)

        unrealized_pnl = total_market_value - total_cost_basis
        total_pnl = unrealized_pnl + total_realized_pnl
        pnl_percent = (
            (total_pnl / total_cost_basis * 100) if total_cost_basis > 0 else 0.0
        )

        # Calculate days held
        days_held = 0
        if entry_date:
            days_held = (date.today() - entry_date).days

        # Calculate annualized return
        annualized_return = None
        if days_held > 0 and total_cost_basis > 0:
            daily_return = total_pnl / total_cost_basis / days_held
            annualized_return = daily_return * 365 * 100

        return StrategyPnL(
            strategy_type=strategy.strategy_type,
            strategy_name=self._get_strategy_name(strategy),
            unrealized_pnl=unrealized_pnl,
            realized_pnl=total_realized_pnl,
            total_pnl=total_pnl,
            pnl_percent=pnl_percent,
            cost_basis=total_cost_basis,
            market_value=total_market_value,
            max_profit=None,
            max_loss=None,
            breakeven_points=[],
            days_held=days_held,
            annualized_return=annualized_return,
        )

    def _get_strategy_positions(
        self, strategy: BasicStrategy, all_positions: list[Position]
    ) -> list[Position]:
        """Get positions that belong to a specific strategy."""
        # Simplified matching - in a real implementation, this would be more sophisticated
        strategy_positions = []

        if isinstance(strategy, AssetStrategy):
            for position in all_positions:
                if (
                    position.asset is not None
                    and position.asset.symbol == strategy.asset.symbol
                ):
                    strategy_positions.append(position)

        return strategy_positions

    def _get_strategy_name(self, strategy: BasicStrategy) -> str:
        """Get human-readable strategy name."""
        if isinstance(strategy, AssetStrategy):
            direction = "Long" if strategy.quantity > 0 else "Short"
            asset_type = "Option" if isinstance(strategy.asset, Option) else "Stock"
            return f"{direction} {asset_type}"
        elif isinstance(strategy, SpreadStrategy):
            return (
                f"{strategy.option_type.title()} {strategy.spread_type.title()} Spread"
            )
        elif isinstance(strategy, CoveredStrategy):
            option_type = strategy.sell_option.option_type
            return f"Covered {option_type.title()}"
        else:
            return strategy.strategy_type.title()

    def _detect_complex_for_underlying(
        self, underlying_symbol: str, positions: list[Position]
    ) -> list[ComplexStrategy]:
        """Detect complex strategies for a specific underlying."""
        complex_strategies = []

        # Group options by type and expiration
        calls = [p for p in positions if isinstance(p.asset, Call)]
        puts = [p for p in positions if isinstance(p.asset, Put)]

        # Detect iron condors (short call spread + short put spread)
        iron_condors = self._detect_iron_condors(calls, puts, underlying_symbol)
        complex_strategies.extend(iron_condors)

        # Detect straddles and strangles
        straddles_strangles = self._detect_straddles_strangles(
            calls, puts, underlying_symbol
        )
        complex_strategies.extend(straddles_strangles)

        # Detect butterflies
        butterflies = self._detect_butterflies(calls, puts, underlying_symbol)
        complex_strategies.extend(butterflies)

        # Detect condors
        condors = self._detect_condors(calls, puts, underlying_symbol)
        complex_strategies.extend(condors)

        return complex_strategies

    def _detect_iron_condors(
        self, calls: list[Position], puts: list[Position], underlying_symbol: str
    ) -> list[ComplexStrategy]:
        """Detect iron condor strategies."""
        # Simplified detection - in a real implementation this would be more sophisticated
        return []

    def _detect_straddles_strangles(
        self, calls: list[Position], puts: list[Position], underlying_symbol: str
    ) -> list[ComplexStrategy]:
        """Detect straddle and strangle strategies."""
        # Simplified detection - in a real implementation this would be more sophisticated
        return []

    def _detect_butterflies(
        self, calls: list[Position], puts: list[Position], underlying_symbol: str
    ) -> list[ComplexStrategy]:
        """Detect butterfly strategies."""
        # Simplified detection - in a real implementation this would be more sophisticated
        return []

    def _detect_condors(
        self, calls: list[Position], puts: list[Position], underlying_symbol: str
    ) -> list[ComplexStrategy]:
        """Detect condor strategies."""
        # Simplified detection - in a real implementation this would be more sophisticated
        return []

    def _generate_strategy_specific_recommendations(
        self,
        positions: list[Position],
        current_quotes: dict[str, Quote | OptionQuote],
    ) -> list[dict[str, Any]]:
        """Generate strategy-specific optimization recommendations."""
        recommendations = []

        # Find short options close to expiration
        for position in positions:
            if isinstance(position.asset, Option) and position.quantity < 0:
                days_to_expiry = (position.asset.expiration_date - date.today()).days

                if days_to_expiry <= 7:  # One week to expiration
                    recommendations.append(
                        {
                            "type": "expiration_management",
                            "priority": "high",
                            "description": f"Short {position.asset.option_type} expires in {days_to_expiry} days",
                            "suggested_action": "consider_rolling_or_closing",
                            "symbol": position.symbol,
                            "days_to_expiry": days_to_expiry,
                        }
                    )

        return recommendations


# Convenience functions for Phase 3 features
def analyze_advanced_strategy_pnl(
    positions: list[Position],
    current_quotes: dict[str, Quote | OptionQuote],
    entry_date: date | None = None,
) -> list[StrategyPnL]:
    """Analyze comprehensive P&L for all strategies."""
    analyzer = AdvancedStrategyAnalyzer()
    return analyzer.analyze_strategy_pnl(positions, current_quotes, entry_date)


def aggregate_portfolio_greeks(
    positions: list[Position], current_quotes: dict[str, Quote | OptionQuote]
) -> StrategyGreeks:
    """Aggregate Greeks across entire portfolio."""
    analyzer = AdvancedStrategyAnalyzer()
    return analyzer.aggregate_strategy_greeks(positions, current_quotes)


def detect_complex_strategies(positions: list[Position]) -> list[ComplexStrategy]:
    """Detect complex multi-leg strategies in portfolio."""
    analyzer = AdvancedStrategyAnalyzer()
    return analyzer.detect_complex_strategies(positions)


def get_portfolio_optimization_recommendations(
    positions: list[Position], current_quotes: dict[str, Quote | OptionQuote]
) -> list[dict[str, Any]]:
    """Get optimization recommendations for portfolio."""
    analyzer = AdvancedStrategyAnalyzer()
    return analyzer.generate_optimization_recommendations(positions, current_quotes)
