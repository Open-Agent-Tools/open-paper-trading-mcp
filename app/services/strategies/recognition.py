"""
Strategy recognition service.

This module handles grouping positions into basic trading strategies
and provides analysis of strategy composition.
"""

from typing import List, Dict, Any

from ...models.assets import Asset, Option, asset_factory
from ...models.trading import Position

from .models import (
    BasicStrategy,
    AssetStrategy,
    SpreadStrategy,
    CoveredStrategy,
    SpreadType,
)


class StrategyRecognitionService:
    """Service for grouping positions into trading strategies."""

    def __init__(self) -> None:
        pass

    def group_positions_by_strategy(
        self, positions: List[Position]
    ) -> List[BasicStrategy]:
        """
        Group positions into basic trading strategies.

        Args:
            positions: List of Position objects

        Returns:
            List of strategy objects grouped by underlying
        """
        if not positions:
            return []

        # Get unique underlying symbols
        underlyings = self._get_underlying_symbols(positions)

        # Group strategies for each underlying
        all_strategies = []
        for underlying_symbol in underlyings:
            underlying_strategies = self._group_strategies_for_underlying(
                underlying_symbol, positions
            )
            all_strategies.extend(underlying_strategies)

        return all_strategies

    def _get_underlying_symbols(self, positions: List[Position]) -> List[str]:
        """Extract unique underlying symbols from positions."""
        underlyings = set()

        for position in positions:
            if position.asset is None:
                continue
            if isinstance(position.asset, Option):
                underlyings.add(position.asset.underlying.symbol)
            else:
                # Stock position - add its own symbol
                underlyings.add(position.asset.symbol)

        return list(underlyings)

    def _group_strategies_for_underlying(
        self, underlying_symbol: str, all_positions: List[Position]
    ) -> List[BasicStrategy]:
        """Group strategies for a specific underlying asset."""

        # Filter positions for this underlying
        positions = self._filter_positions_for_underlying(
            underlying_symbol, all_positions
        )

        if not positions:
            return []

        strategies: List[BasicStrategy] = []

        # Calculate equity positions
        long_equity_qty = sum(
            p.quantity
            for p in positions
            if not isinstance(p.asset, Option) and p.quantity > 0
        )
        short_equity_qty = sum(
            p.quantity
            for p in positions
            if not isinstance(p.asset, Option) and p.quantity < 0
        )

        # Get individual option strategies
        short_calls = self._create_individual_option_strategies(
            positions, "call", negative=True
        )
        short_puts = self._create_individual_option_strategies(
            positions, "put", negative=True
        )
        long_calls = self._create_individual_option_strategies(
            positions, "call", negative=False
        )
        long_puts = self._create_individual_option_strategies(
            positions, "put", negative=False
        )

        # Sort options by strike for optimal pairing
        short_calls.sort(key=lambda s: s.asset.strike if isinstance(s.asset, Option) else 0, reverse=False)
        long_calls.sort(key=lambda s: s.asset.strike if isinstance(s.asset, Option) else 0, reverse=False)
        short_puts.sort(key=lambda s: s.asset.strike if isinstance(s.asset, Option) else 0, reverse=True)
        long_puts.sort(key=lambda s: s.asset.strike if isinstance(s.asset, Option) else 0, reverse=True)

        # Create underlying asset for covered strategies
        underlying_asset = asset_factory(underlying_symbol)

        # Process short calls (priority: covered > spreads > naked)
        for short_call in short_calls:
            if not isinstance(short_call.asset, Option):
                continue
            if long_equity_qty >= 100 and underlying_asset:
                # Covered call
                strategies.append(
                    CoveredStrategy(
                        asset=underlying_asset, sell_option=short_call.asset, quantity=1
                    )
                )
                long_equity_qty -= 100
            elif long_calls:
                # Call spread
                long_call = long_calls.pop(0)
                if isinstance(long_call.asset, Option):
                    strategies.append(
                        SpreadStrategy(
                            sell_option=short_call.asset,
                            buy_option=long_call.asset,
                            quantity=1,
                        )
                    )
            else:
                # Naked short call
                strategies.append(short_call)

        # Process short puts (priority: covered > spreads > naked)
        for short_put in short_puts:
            if not isinstance(short_put.asset, Option):
                continue
            if abs(short_equity_qty) >= 100 and underlying_asset:
                # Covered put (short equity covers short put)
                strategies.append(
                    CoveredStrategy(
                        asset=underlying_asset, sell_option=short_put.asset, quantity=1
                    )
                )
                short_equity_qty += 100  # Reduce short position
            elif long_puts:
                # Put spread
                long_put = long_puts.pop(0)
                if isinstance(long_put.asset, Option):
                    strategies.append(
                        SpreadStrategy(
                            sell_option=short_put.asset,
                            buy_option=long_put.asset,
                            quantity=1,
                        )
                    )
            else:
                # Naked short put
                strategies.append(short_put)

        # Add remaining long options and equity positions
        for long_call in long_calls:
            strategies.append(long_call)
        for long_put in long_puts:
            strategies.append(long_put)

        # Add equity positions
        if long_equity_qty > 0 and underlying_asset:
            strategies.append(
                AssetStrategy(asset=underlying_asset, quantity=long_equity_qty)
            )

        if short_equity_qty < 0 and underlying_asset:
            strategies.append(
                AssetStrategy(asset=underlying_asset, quantity=short_equity_qty)
            )

        return strategies

    def _filter_positions_for_underlying(
        self, underlying_symbol: str, positions: List[Position]
    ) -> List[Position]:
        """Filter positions that relate to a specific underlying."""
        filtered = []

        for position in positions:
            if position.asset is None:
                continue
            if isinstance(position.asset, Option):
                if position.asset.underlying.symbol == underlying_symbol:
                    filtered.append(position)
            else:
                if position.asset.symbol == underlying_symbol:
                    filtered.append(position)

        return filtered

    def _create_individual_option_strategies(
        self, positions: List[Position], option_type: str, negative: bool
    ) -> List[AssetStrategy]:
        """Create individual AssetStrategy objects for options of a given type and direction."""
        strategies = []

        for position in positions:
            if (
                isinstance(position.asset, Option)
                and position.asset.option_type == option_type
                and (position.quantity < 0) == negative
            ):
                # Create individual strategies for each contract
                quantity_per_strategy = -1 if negative else 1
                num_strategies = abs(int(position.quantity))

                for _ in range(num_strategies):
                    strategies.append(
                        AssetStrategy(
                            asset=position.asset, quantity=quantity_per_strategy
                        )
                    )

        return strategies

    def get_strategy_summary(self, strategies: List[BasicStrategy]) -> Dict[str, Any]:
        """Generate summary statistics for a list of strategies."""
        summary: Dict[str, Any] = {
            "total_strategies": len(strategies),
            "strategy_counts": {"asset": 0, "offset": 0, "spread": 0, "covered": 0},
            "spread_details": {
                "credit_spreads": 0,
                "debit_spreads": 0,
                "call_spreads": 0,
                "put_spreads": 0,
            },
            "covered_details": {"covered_calls": 0, "covered_puts": 0},
            "naked_positions": {
                "naked_calls": 0,
                "naked_puts": 0,
                "long_equity": 0,
                "short_equity": 0,
            },
        }

        for strategy in strategies:
            strategy_type = strategy.strategy_type
            summary["strategy_counts"][strategy_type.value] += 1

            if isinstance(strategy, SpreadStrategy):
                # Spread details
                if strategy.spread_type == SpreadType.CREDIT:
                    summary["spread_details"]["credit_spreads"] += 1
                else:
                    summary["spread_details"]["debit_spreads"] += 1

                if strategy.option_type == "call":
                    summary["spread_details"]["call_spreads"] += 1
                else:
                    summary["spread_details"]["put_spreads"] += 1

            elif isinstance(strategy, CoveredStrategy):
                # Covered position details
                if strategy.sell_option.option_type == "call":
                    summary["covered_details"]["covered_calls"] += 1
                else:
                    summary["covered_details"]["covered_puts"] += 1

            elif isinstance(strategy, AssetStrategy):
                # Naked position details
                if isinstance(strategy.asset, Option):
                    if strategy.asset.option_type == "call":
                        summary["naked_positions"]["naked_calls"] += 1
                    else:
                        summary["naked_positions"]["naked_puts"] += 1
                else:
                    if strategy.direction == "long":
                        summary["naked_positions"]["long_equity"] += 1
                    else:
                        summary["naked_positions"]["short_equity"] += 1

        return summary


# Convenience functions
def group_into_basic_strategies(positions: List[Position]) -> List[BasicStrategy]:
    """Group positions into basic trading strategies."""
    service = StrategyRecognitionService()
    return service.group_positions_by_strategy(positions)


def analyze_strategy_portfolio(positions: List[Position]) -> Dict[str, Any]:
    """Analyze a portfolio's strategy composition."""
    service = StrategyRecognitionService()
    strategies = service.group_positions_by_strategy(positions)
    summary = service.get_strategy_summary(strategies)

    return {
        "strategies": strategies,
        "summary": summary,
        "total_positions": len(positions),
        "total_strategies": len(strategies),
    }