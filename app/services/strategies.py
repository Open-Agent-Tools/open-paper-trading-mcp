"""
Strategy recognition service for grouping positions into basic trading strategies.

Adapted from paperbroker's strategy grouping logic with modern Python patterns.
Used primarily for margin calculations and portfolio analysis.

Strategy Types:
- AssetStrategy: Long/short positions in underlying assets
- OffsetStrategy: Simultaneous long/short positions in same asset  
- SpreadStrategy: Options spreads with inverse risk profiles
- CoveredStrategy: Underlying asset covering short option risk
"""

from typing import List, Dict, Any, Optional, Union, Literal
from enum import Enum
from pydantic import BaseModel, Field

from ..models.assets import Asset, Option, Call, Put, asset_factory
from ..models.trading import Position


class StrategyType(str, Enum):
    """Strategy classification types."""
    BASIC = "basic"
    ASSET = "asset"  
    OFFSET = "offset"
    SPREAD = "spread"
    COVERED = "covered"


class SpreadType(str, Enum):
    """Spread strategy subtypes."""
    CREDIT = "credit"
    DEBIT = "debit"


class BasicStrategy(BaseModel):
    """Base class for all trading strategies."""
    
    strategy_type: StrategyType = Field(default=StrategyType.BASIC, description="Strategy classification")
    quantity: int = Field(default=1, description="Strategy quantity (contracts/shares)")
    
    class Config:
        use_enum_values = True


class AssetStrategy(BasicStrategy):
    """Strategy involving long or short positions in an asset."""
    
    strategy_type: Literal[StrategyType.ASSET] = Field(default=StrategyType.ASSET)
    asset: Asset = Field(..., description="Asset being held")
    direction: str = Field(..., description="Position direction (long/short)")
    
    def __init__(self, asset: Union[str, Asset], quantity: int = 1, **data):
        # Normalize asset
        asset_obj = asset_factory(asset) if isinstance(asset, str) else asset
        
        # Determine direction
        direction = 'short' if quantity < 0 else 'long'
        
        super().__init__(
            asset=asset_obj,
            quantity=quantity,
            direction=direction,
            **data
        )


class OffsetStrategy(BasicStrategy):
    """Strategy with simultaneous long and short positions in same asset."""
    
    strategy_type: Literal[StrategyType.OFFSET] = Field(default=StrategyType.OFFSET)
    asset: Asset = Field(..., description="Asset being offset")
    
    def __init__(self, asset: Union[str, Asset], quantity: int = 1, **data):
        asset_obj = asset_factory(asset) if isinstance(asset, str) else asset
        
        super().__init__(
            asset=asset_obj,
            quantity=quantity,
            **data
        )


class SpreadStrategy(BasicStrategy):
    """Options spread strategy with defined risk profile."""
    
    strategy_type: Literal[StrategyType.SPREAD] = Field(default=StrategyType.SPREAD)
    sell_option: Option = Field(..., description="Option being sold")
    buy_option: Option = Field(..., description="Option being bought")
    option_type: str = Field(..., description="Option type (call/put)")
    spread_type: SpreadType = Field(..., description="Spread classification (credit/debit)")
    
    def __init__(self, sell_option: Option, buy_option: Option, quantity: int = 1, **data):
        # Validation
        if sell_option.option_type != buy_option.option_type:
            raise ValueError("SpreadStrategy: option types must match")
        
        if sell_option.underlying.symbol != buy_option.underlying.symbol:
            raise ValueError("SpreadStrategy: underlying assets must match")
        
        if sell_option.strike == buy_option.strike:
            raise ValueError("SpreadStrategy: strikes must be different")
        
        # Determine spread type based on option type and strikes
        option_type = sell_option.option_type
        
        if option_type == 'put':
            spread_type = SpreadType.CREDIT if sell_option.strike > buy_option.strike else SpreadType.DEBIT
        else:  # call
            spread_type = SpreadType.CREDIT if sell_option.strike < buy_option.strike else SpreadType.DEBIT
        
        super().__init__(
            sell_option=sell_option,
            buy_option=buy_option,
            option_type=option_type,
            spread_type=spread_type,
            quantity=abs(quantity),
            **data
        )


class CoveredStrategy(BasicStrategy):
    """Strategy where underlying asset covers short option risk."""
    
    strategy_type: Literal[StrategyType.COVERED] = Field(default=StrategyType.COVERED)
    asset: Asset = Field(..., description="Underlying asset providing cover")
    sell_option: Option = Field(..., description="Option being sold")
    
    def __init__(self, asset: Union[str, Asset], sell_option: Option, quantity: int = 1, **data):
        # Normalize asset
        asset_obj = asset_factory(asset) if isinstance(asset, str) else asset
        
        # Validation
        if asset_obj.symbol != sell_option.underlying.symbol:
            raise ValueError("CoveredStrategy: option underlying must match asset")
        
        super().__init__(
            asset=asset_obj,
            sell_option=sell_option,
            quantity=abs(quantity),
            **data
        )


class StrategyRecognitionService:
    """Service for grouping positions into trading strategies."""
    
    def __init__(self):
        pass
    
    def group_positions_by_strategy(self, positions: List[Position]) -> List[BasicStrategy]:
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
            if isinstance(position.asset, Option):
                underlyings.add(position.asset.underlying.symbol)
            else:
                # Stock position - add its own symbol
                underlyings.add(position.asset.symbol)
        
        return list(underlyings)
    
    def _group_strategies_for_underlying(self, underlying_symbol: str, all_positions: List[Position]) -> List[BasicStrategy]:
        """Group strategies for a specific underlying asset."""
        
        # Filter positions for this underlying
        positions = self._filter_positions_for_underlying(underlying_symbol, all_positions)
        
        if not positions:
            return []
        
        strategies = []
        
        # Calculate equity positions
        long_equity_qty = sum(p.quantity for p in positions 
                             if not isinstance(p.asset, Option) and p.quantity > 0)
        short_equity_qty = sum(p.quantity for p in positions 
                              if not isinstance(p.asset, Option) and p.quantity < 0)
        
        # Get individual option strategies
        short_calls = self._create_individual_option_strategies(positions, 'call', negative=True)
        short_puts = self._create_individual_option_strategies(positions, 'put', negative=True)  
        long_calls = self._create_individual_option_strategies(positions, 'call', negative=False)
        long_puts = self._create_individual_option_strategies(positions, 'put', negative=False)
        
        # Sort options by strike for optimal pairing
        short_calls.sort(key=lambda s: s.asset.strike, reverse=False)
        long_calls.sort(key=lambda s: s.asset.strike, reverse=False)
        short_puts.sort(key=lambda s: s.asset.strike, reverse=True)
        long_puts.sort(key=lambda s: s.asset.strike, reverse=True)
        
        # Create underlying asset for covered strategies
        underlying_asset = asset_factory(underlying_symbol)
        
        # Process short calls (priority: covered > spreads > naked)
        for short_call in short_calls:
            if long_equity_qty >= 100:
                # Covered call
                strategies.append(CoveredStrategy(
                    asset=underlying_asset,
                    sell_option=short_call.asset,
                    quantity=1
                ))
                long_equity_qty -= 100
            elif long_calls:
                # Call spread
                long_call = long_calls.pop(0)
                strategies.append(SpreadStrategy(
                    sell_option=short_call.asset,
                    buy_option=long_call.asset,
                    quantity=1
                ))
            else:
                # Naked short call
                strategies.append(short_call)
        
        # Process short puts (priority: covered > spreads > naked)
        for short_put in short_puts:
            if abs(short_equity_qty) >= 100:
                # Covered put (short equity covers short put)
                strategies.append(CoveredStrategy(
                    asset=underlying_asset,
                    sell_option=short_put.asset,
                    quantity=1
                ))
                short_equity_qty += 100  # Reduce short position
            elif long_puts:
                # Put spread
                long_put = long_puts.pop(0)
                strategies.append(SpreadStrategy(
                    sell_option=short_put.asset,
                    buy_option=long_put.asset,
                    quantity=1
                ))
            else:
                # Naked short put
                strategies.append(short_put)
        
        # Add remaining long options and equity positions
        strategies.extend(long_calls)
        strategies.extend(long_puts)
        
        # Add equity positions
        if long_equity_qty > 0:
            strategies.append(AssetStrategy(
                asset=underlying_asset,
                quantity=long_equity_qty
            ))
        
        if short_equity_qty < 0:
            strategies.append(AssetStrategy(
                asset=underlying_asset,
                quantity=short_equity_qty
            ))
        
        return strategies
    
    def _filter_positions_for_underlying(self, underlying_symbol: str, positions: List[Position]) -> List[Position]:
        """Filter positions that relate to a specific underlying."""
        filtered = []
        
        for position in positions:
            if isinstance(position.asset, Option):
                if position.asset.underlying.symbol == underlying_symbol:
                    filtered.append(position)
            else:
                if position.asset.symbol == underlying_symbol:
                    filtered.append(position)
        
        return filtered
    
    def _create_individual_option_strategies(self, positions: List[Position], option_type: str, negative: bool) -> List[AssetStrategy]:
        """Create individual AssetStrategy objects for options of a given type and direction."""
        strategies = []
        
        for position in positions:
            if (isinstance(position.asset, Option) and 
                position.asset.option_type == option_type and
                (position.quantity < 0) == negative):
                
                # Create individual strategies for each contract
                quantity_per_strategy = -1 if negative else 1
                num_strategies = abs(int(position.quantity))
                
                for _ in range(num_strategies):
                    strategies.append(AssetStrategy(
                        asset=position.asset,
                        quantity=quantity_per_strategy
                    ))
        
        return strategies
    
    def get_strategy_summary(self, strategies: List[BasicStrategy]) -> Dict[str, Any]:
        """Generate summary statistics for a list of strategies."""
        summary = {
            'total_strategies': len(strategies),
            'strategy_counts': {
                'asset': 0,
                'offset': 0, 
                'spread': 0,
                'covered': 0
            },
            'spread_details': {
                'credit_spreads': 0,
                'debit_spreads': 0,
                'call_spreads': 0,
                'put_spreads': 0
            },
            'covered_details': {
                'covered_calls': 0,
                'covered_puts': 0
            },
            'naked_positions': {
                'naked_calls': 0,
                'naked_puts': 0,
                'long_equity': 0,
                'short_equity': 0
            }
        }
        
        for strategy in strategies:
            strategy_type = strategy.strategy_type
            summary['strategy_counts'][strategy_type] += 1
            
            if isinstance(strategy, SpreadStrategy):
                # Spread details
                if strategy.spread_type == SpreadType.CREDIT:
                    summary['spread_details']['credit_spreads'] += 1
                else:
                    summary['spread_details']['debit_spreads'] += 1
                
                if strategy.option_type == 'call':
                    summary['spread_details']['call_spreads'] += 1
                else:
                    summary['spread_details']['put_spreads'] += 1
            
            elif isinstance(strategy, CoveredStrategy):
                # Covered position details
                if strategy.sell_option.option_type == 'call':
                    summary['covered_details']['covered_calls'] += 1
                else:
                    summary['covered_details']['covered_puts'] += 1
            
            elif isinstance(strategy, AssetStrategy):
                # Naked position details
                if isinstance(strategy.asset, Option):
                    if strategy.asset.option_type == 'call':
                        summary['naked_positions']['naked_calls'] += 1
                    else:
                        summary['naked_positions']['naked_puts'] += 1
                else:
                    if strategy.direction == 'long':
                        summary['naked_positions']['long_equity'] += 1
                    else:
                        summary['naked_positions']['short_equity'] += 1
        
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
        'strategies': strategies,
        'summary': summary,
        'total_positions': len(positions),
        'total_strategies': len(strategies)
    }