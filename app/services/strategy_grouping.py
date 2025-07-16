"""
Advanced strategy grouping algorithm from reference implementation.

Groups positions into basic strategies for margin calculation and risk analysis.
Special thanks to /u/EdKaim for the outline of this process.
"""

from typing import List, Dict, Any, Optional, Tuple

from ..models.assets import Option, asset_factory
from ..models.trading import Position
from .strategies import (
    BasicStrategy,
    AssetStrategy,
    SpreadStrategy,
    CoveredStrategy,
    StrategyType,
)


def group_into_basic_strategies(positions: List[Position]) -> List[BasicStrategy]:
    """
    Group positions into basic strategies for margin calculation.

    Args:
        positions: List of positions to group

    Returns:
        List of BasicStrategy objects
    """
    if not positions:
        return []

    # Get unique underlyings
    underlyings = set()
    for position in positions:
        asset = asset_factory(position.symbol)
        if asset is None:
            continue
        if isinstance(asset, Option):
            underlyings.add(asset.underlying.symbol)
        else:
            underlyings.add(asset.symbol)

    # Group strategies by underlying
    all_strategies = []
    for underlying in underlyings:
        strategies = _group_into_basic_strategies_in_underlying(underlying, positions)
        all_strategies.extend(strategies)

    # Filter out zero-quantity strategies
    return [s for s in all_strategies if s.quantity != 0]


def _group_into_basic_strategies_in_underlying(
    underlying: str, positions: List[Position]
) -> List[BasicStrategy]:
    """Group positions for a specific underlying into basic strategies."""

    # Filter positions for this underlying
    underlying_positions = []
    for position in positions:
        asset = asset_factory(position.symbol)
        if asset is None:
            continue
        if isinstance(asset, Option):
            if asset.underlying.symbol == underlying:
                underlying_positions.append(position)
        elif asset.symbol == underlying:
            underlying_positions.append(position)

    if not underlying_positions:
        return []

    strategies = []

    # Calculate equity positions
    long_equity_quantity = sum(
        pos.quantity
        for pos in underlying_positions
        if not isinstance(asset_factory(pos.symbol), Option) and pos.quantity > 0
    )

    short_equity_quantity = sum(
        pos.quantity
        for pos in underlying_positions
        if not isinstance(asset_factory(pos.symbol), Option) and pos.quantity < 0
    )

    # Create asset strategies for equity
    long_equity = AssetStrategy(asset=underlying, quantity=long_equity_quantity)

    short_equity = AssetStrategy(asset=underlying, quantity=short_equity_quantity)

    # Separate options by type and direction
    short_calls = []
    long_calls = []
    short_puts = []
    long_puts = []

    for position in underlying_positions:
        asset = asset_factory(position.symbol)
        if isinstance(asset, Option):
            if asset.option_type == "call":
                if position.quantity < 0:
                    # Create individual strategies for each contract
                    for _ in range(abs(int(position.quantity))):
                        short_calls.append(AssetStrategy(asset=asset, quantity=-1))
                else:
                    for _ in range(abs(int(position.quantity))):
                        long_calls.append(AssetStrategy(asset=asset, quantity=1))
            elif asset.option_type == "put":
                if position.quantity < 0:
                    for _ in range(abs(int(position.quantity))):
                        short_puts.append(AssetStrategy(asset=asset, quantity=-1))
                else:
                    for _ in range(abs(int(position.quantity))):
                        long_puts.append(AssetStrategy(asset=asset, quantity=1))

    # Sort by strike for optimal pairing
    short_calls.sort(key=lambda x: getattr(x.asset, 'strike', 0))
    long_calls.sort(key=lambda x: getattr(x.asset, 'strike', 0))
    short_puts.sort(key=lambda x: getattr(x.asset, 'strike', 0), reverse=True)
    long_puts.sort(key=lambda x: getattr(x.asset, 'strike', 0), reverse=True)

    # Process short calls
    for short_call in short_calls:
        if long_equity.quantity >= 100:
            # Covered call strategy
            strategies.append(
                CoveredStrategy(
                    asset=underlying, sell_option=short_call.asset, quantity=1
                )
            )
            long_equity.quantity -= 100
        elif long_calls:
            # Call spread strategy
            long_call = long_calls.pop(0)
            strategies.append(
                SpreadStrategy(
                    buy_option=long_call.asset, sell_option=short_call.asset, quantity=1
                )
            )
        else:
            # Naked short call
            strategies.append(short_call)

    # Process short puts
    for short_put in short_puts:
        if abs(short_equity.quantity) >= 100:
            # Covered put strategy (short stock covers short put)
            strategies.append(
                CoveredStrategy(
                    asset=underlying, sell_option=short_put.asset, quantity=1
                )
            )
            short_equity.quantity += 100  # Reduce short position
        elif long_puts:
            # Put spread strategy
            long_put = long_puts.pop(0)
            strategies.append(
                SpreadStrategy(
                    buy_option=long_put.asset, sell_option=short_put.asset, quantity=1
                )
            )
        else:
            # Naked short put
            strategies.append(short_put)

    # Add remaining long options and equity positions
    strategies.extend(long_calls)
    strategies.extend(long_puts)
    strategies.append(long_equity)
    strategies.append(short_equity)

    return strategies


def create_asset_strategies(
    positions: List[Position], underlying: str
) -> List[AssetStrategy]:
    """
    Create asset strategies for positions in a specific underlying.

    Args:
        positions: List of positions
        underlying: Underlying symbol to filter by

    Returns:
        List of AssetStrategy objects
    """
    filtered_positions = []
    for position in positions:
        asset = asset_factory(position.symbol)
        if asset is None:
            continue
        if isinstance(asset, Option):
            if asset.underlying.symbol == underlying:
                filtered_positions.append(position)
        elif asset.symbol == underlying:
            filtered_positions.append(position)

    if not filtered_positions:
        return []

    strategies = []

    # Equity positions
    long_equity_qty = sum(
        pos.quantity
        for pos in filtered_positions
        if not isinstance(asset_factory(pos.symbol), Option) and pos.quantity > 0
    )

    short_equity_qty = sum(
        pos.quantity
        for pos in filtered_positions
        if not isinstance(asset_factory(pos.symbol), Option) and pos.quantity < 0
    )

    if long_equity_qty > 0:
        strategies.append(AssetStrategy(asset=underlying, quantity=long_equity_qty))

    if short_equity_qty < 0:
        strategies.append(AssetStrategy(asset=underlying, quantity=short_equity_qty))

    # Option positions
    for position in filtered_positions:
        asset = asset_factory(position.symbol)
        if isinstance(asset, Option):
            if position.quantity != 0:
                strategies.append(
                    AssetStrategy(asset=asset, quantity=position.quantity)
                )

    return strategies


def normalize_strategy_quantities(
    strategies: List[BasicStrategy],
) -> List[BasicStrategy]:
    """
    Normalize strategy quantities to minimize margin requirements.

    Args:
        strategies: List of strategies to normalize

    Returns:
        List of normalized strategies
    """
    if not strategies:
        return []

    # Group strategies by type and asset
    grouped = {}

    for strategy in strategies:
        if strategy.strategy_type == StrategyType.ASSET and hasattr(strategy, 'asset'):
            key = (strategy.strategy_type, strategy.asset.symbol)
        elif strategy.strategy_type == StrategyType.SPREAD:
            key = (
                strategy.strategy_type,
                strategy.sell_option.symbol,
                strategy.buy_option.symbol,
            )
        elif strategy.strategy_type == StrategyType.COVERED:
            key = (
                strategy.strategy_type,
                strategy.asset.symbol,
                strategy.sell_option.symbol,
            )
        else:
            key = (strategy.strategy_type, str(strategy))

        if key not in grouped:
            grouped[key] = []
        grouped[key].append(strategy)

    # Combine quantities for same strategy types
    normalized = []
    for key, strategy_group in grouped.items():
        if not strategy_group:
            continue

        # Use the first strategy as template
        template = strategy_group[0]
        total_quantity = sum(s.quantity for s in strategy_group)

        if total_quantity != 0:
            # Create new strategy with combined quantity
            template.quantity = total_quantity
            normalized.append(template)

    return normalized


def identify_complex_strategies(
    strategies: List[BasicStrategy],
) -> Dict[str, List[BasicStrategy]]:
    """
    Identify complex multi-leg strategies from basic strategies.

    Args:
        strategies: List of basic strategies

    Returns:
        Dictionary mapping complex strategy names to their component strategies
    """
    complex_strategies = {}

    # Look for iron condors
    iron_condors = _find_iron_condors(strategies)
    if iron_condors:
        complex_strategies["iron_condors"] = iron_condors

    # Look for butterflies
    butterflies = _find_butterflies(strategies)
    if butterflies:
        complex_strategies["butterflies"] = butterflies

    # Look for straddles/strangles
    straddles = _find_straddles_strangles(strategies)
    if straddles:
        complex_strategies["straddles_strangles"] = straddles

    return complex_strategies


def _find_iron_condors(strategies: List[BasicStrategy]) -> List[Dict[str, Any]]:
    """Find iron condor strategies."""
    iron_condors = []

    # Iron condor = call spread + put spread with same expiration
    call_spreads = [
        s
        for s in strategies
        if (
            s.strategy_type == StrategyType.SPREAD
            and s.sell_option.option_type == "call"
        )
    ]

    put_spreads = [
        s
        for s in strategies
        if (
            s.strategy_type == StrategyType.SPREAD
            and s.sell_option.option_type == "put"
        )
    ]

    for call_spread in call_spreads:
        for put_spread in put_spreads:
            if (
                call_spread.sell_option.expiration_date
                == put_spread.sell_option.expiration_date
                and call_spread.sell_option.underlying.symbol
                == put_spread.sell_option.underlying.symbol
                and call_spread.quantity == put_spread.quantity
            ):
                iron_condors.append(
                    {
                        "type": "iron_condor",
                        "call_spread": call_spread,
                        "put_spread": put_spread,
                        "quantity": call_spread.quantity,
                        "expiration": call_spread.sell_option.expiration_date,
                    }
                )

    return iron_condors


def _find_butterflies(strategies: List[BasicStrategy]) -> List[Dict[str, Any]]:
    """Find butterfly strategies."""
    butterflies = []

    # Butterfly = buy 2 middle strikes, sell 1 lower + 1 higher
    # This is complex to detect from spreads, would need position-level analysis

    return butterflies


def _find_straddles_strangles(strategies: List[BasicStrategy]) -> List[Dict[str, Any]]:
    """Find straddle and strangle strategies."""
    straddles_strangles = []

    # Group option strategies by expiration and underlying
    option_groups = {}

    for strategy in strategies:
        if strategy.strategy_type == StrategyType.ASSET and isinstance(
            strategy.asset, Option
        ):
            key = (strategy.asset.underlying.symbol, strategy.asset.expiration_date)
            if key not in option_groups:
                option_groups[key] = []
            option_groups[key].append(strategy)

    # Look for straddles (same strike) and strangles (different strikes)
    for key, group in option_groups.items():
        calls = [s for s in group if s.asset.option_type == "call"]
        puts = [s for s in group if s.asset.option_type == "put"]

        for call in calls:
            for put in puts:
                if call.quantity == put.quantity and call.quantity > 0:  # Both long
                    if call.asset.strike == put.asset.strike:
                        # Long straddle
                        straddles_strangles.append(
                            {
                                "type": "long_straddle",
                                "call": call,
                                "put": put,
                                "quantity": call.quantity,
                                "strike": call.asset.strike,
                            }
                        )
                    else:
                        # Long strangle
                        straddles_strangles.append(
                            {
                                "type": "long_strangle",
                                "call": call,
                                "put": put,
                                "quantity": call.quantity,
                                "call_strike": call.asset.strike,
                                "put_strike": put.asset.strike,
                            }
                        )

    return straddles_strangles
