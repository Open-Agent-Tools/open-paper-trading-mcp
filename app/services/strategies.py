"""
Advanced strategy recognition and analysis service.

Enhanced from paperbroker with sophisticated P&L calculation, Greeks aggregation,
performance attribution, and complex strategy detection.

Strategy Types:
- AssetStrategy: Long/short positions in underlying assets
- OffsetStrategy: Simultaneous long/short positions in same asset
- SpreadStrategy: Options spreads with inverse risk profiles
- CoveredStrategy: Underlying asset covering short option risk
- ComplexStrategy: Multi-leg strategies (iron condors, butterflies, etc.)
"""

from typing import List, Dict, Any, Optional, Union, Literal
from enum import Enum
from datetime import date
from pydantic import BaseModel, Field

from ..models.assets import Asset, Option, Call, Put, asset_factory
from ..models.trading import Position
from ..models.quotes import Quote, OptionQuote


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

    strategy_type: StrategyType = Field(
        default=StrategyType.BASIC, description="Strategy classification"
    )
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
        direction = "short" if quantity < 0 else "long"

        super().__init__(
            asset=asset_obj, quantity=quantity, direction=direction, **data
        )


class OffsetStrategy(BasicStrategy):
    """Strategy with simultaneous long and short positions in same asset."""

    strategy_type: Literal[StrategyType.OFFSET] = Field(default=StrategyType.OFFSET)
    asset: Asset = Field(..., description="Asset being offset")

    def __init__(self, asset: Union[str, Asset], quantity: int = 1, **data):
        asset_obj = asset_factory(asset) if isinstance(asset, str) else asset

        super().__init__(asset=asset_obj, quantity=quantity, **data)


class SpreadStrategy(BasicStrategy):
    """Options spread strategy with defined risk profile."""

    strategy_type: Literal[StrategyType.SPREAD] = Field(default=StrategyType.SPREAD)
    sell_option: Option = Field(..., description="Option being sold")
    buy_option: Option = Field(..., description="Option being bought")
    option_type: str = Field(..., description="Option type (call/put)")
    spread_type: SpreadType = Field(
        ..., description="Spread classification (credit/debit)"
    )

    def __init__(
        self, sell_option: Option, buy_option: Option, quantity: int = 1, **data
    ):
        # Validation
        if sell_option.option_type != buy_option.option_type:
            raise ValueError("SpreadStrategy: option types must match")

        if sell_option.underlying.symbol != buy_option.underlying.symbol:
            raise ValueError("SpreadStrategy: underlying assets must match")

        if sell_option.strike == buy_option.strike:
            raise ValueError("SpreadStrategy: strikes must be different")

        # Determine spread type based on option type and strikes
        option_type = sell_option.option_type

        if option_type == "put":
            spread_type = (
                SpreadType.CREDIT
                if sell_option.strike > buy_option.strike
                else SpreadType.DEBIT
            )
        else:  # call
            spread_type = (
                SpreadType.CREDIT
                if sell_option.strike < buy_option.strike
                else SpreadType.DEBIT
            )

        super().__init__(
            sell_option=sell_option,
            buy_option=buy_option,
            option_type=option_type,
            spread_type=spread_type,
            quantity=abs(quantity),
            **data,
        )


class CoveredStrategy(BasicStrategy):
    """Strategy where underlying asset covers short option risk."""

    strategy_type: Literal[StrategyType.COVERED] = Field(default=StrategyType.COVERED)
    asset: Asset = Field(..., description="Underlying asset providing cover")
    sell_option: Option = Field(..., description="Option being sold")

    def __init__(
        self, asset: Union[str, Asset], sell_option: Option, quantity: int = 1, **data
    ):
        # Normalize asset
        asset_obj = asset_factory(asset) if isinstance(asset, str) else asset

        # Validation
        if asset_obj.symbol != sell_option.underlying.symbol:
            raise ValueError("CoveredStrategy: option underlying must match asset")

        super().__init__(
            asset=asset_obj, sell_option=sell_option, quantity=abs(quantity), **data
        )


class StrategyRecognitionService:
    """Service for grouping positions into trading strategies."""

    def __init__(self):
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

        strategies = []

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
                strategies.append(
                    CoveredStrategy(
                        asset=underlying_asset, sell_option=short_call.asset, quantity=1
                    )
                )
                long_equity_qty -= 100
            elif long_calls:
                # Call spread
                long_call = long_calls.pop(0)
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
            if abs(short_equity_qty) >= 100:
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
        strategies.extend(long_calls)
        strategies.extend(long_puts)

        # Add equity positions
        if long_equity_qty > 0:
            strategies.append(
                AssetStrategy(asset=underlying_asset, quantity=long_equity_qty)
            )

        if short_equity_qty < 0:
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
        summary = {
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
            summary["strategy_counts"][strategy_type] += 1

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


# ============================================================================
# PHASE 3: ADVANCED STRATEGY ANALYSIS
# ============================================================================


class StrategyPnL(BaseModel):
    """Advanced P&L calculation for strategy positions."""

    strategy_type: str = Field(..., description="Strategy type identifier")
    strategy_name: str = Field(..., description="Human-readable strategy name")
    unrealized_pnl: float = Field(0.0, description="Current unrealized P&L")
    realized_pnl: float = Field(0.0, description="Realized P&L from closed positions")
    total_pnl: float = Field(0.0, description="Total P&L (realized + unrealized)")
    pnl_percent: float = Field(0.0, description="P&L as percentage of cost basis")
    cost_basis: float = Field(0.0, description="Total cost basis of strategy")
    market_value: float = Field(0.0, description="Current market value")
    max_profit: Optional[float] = Field(None, description="Maximum theoretical profit")
    max_loss: Optional[float] = Field(None, description="Maximum theoretical loss")
    breakeven_points: List[float] = Field(
        default_factory=list, description="Breakeven prices"
    )
    days_held: int = Field(0, description="Days strategy has been held")
    annualized_return: Optional[float] = Field(
        None, description="Annualized return percentage"
    )


class StrategyGreeks(BaseModel):
    """Aggregated Greeks for strategy positions."""

    delta: float = Field(0.0, description="Total delta exposure")
    gamma: float = Field(0.0, description="Total gamma exposure")
    theta: float = Field(0.0, description="Total theta decay per day")
    vega: float = Field(0.0, description="Total vega sensitivity")
    rho: float = Field(0.0, description="Total rho sensitivity")

    # Normalized Greeks (per $1000 invested)
    delta_normalized: float = Field(0.0, description="Delta per $1000 invested")
    gamma_normalized: float = Field(0.0, description="Gamma per $1000 invested")
    theta_normalized: float = Field(0.0, description="Theta per $1000 invested")
    vega_normalized: float = Field(0.0, description="Vega per $1000 invested")

    # Risk metrics
    delta_dollars: float = Field(
        0.0, description="Dollar delta (delta * underlying price)"
    )
    gamma_dollars: float = Field(0.0, description="Dollar gamma")
    theta_dollars: float = Field(0.0, description="Dollar theta per day")


class StrategyRiskMetrics(BaseModel):
    """Risk analysis metrics for strategies."""

    max_drawdown: float = Field(0.0, description="Maximum historical drawdown")
    volatility: float = Field(0.0, description="Strategy volatility")
    sharpe_ratio: Optional[float] = Field(
        None, description="Risk-adjusted return ratio"
    )
    var_95: Optional[float] = Field(None, description="Value at Risk (95% confidence)")
    expected_shortfall: Optional[float] = Field(
        None, description="Expected loss beyond VaR"
    )

    # Time decay risk
    theta_risk_score: float = Field(0.0, description="Time decay risk (0-100 scale)")
    days_to_max_theta: Optional[int] = Field(
        None, description="Days to maximum theta decay"
    )

    # Assignment risk (for short options)
    assignment_probability: float = Field(0.0, description="Probability of assignment")
    itm_probability: float = Field(0.0, description="Probability of finishing ITM")


class ComplexStrategyType(str, Enum):
    """Complex multi-leg strategy types."""

    IRON_CONDOR = "iron_condor"
    IRON_BUTTERFLY = "iron_butterfly"
    BUTTERFLY = "butterfly"
    CONDOR = "condor"
    STRANGLE = "strangle"
    STRADDLE = "straddle"
    COLLAR = "collar"
    RATIO_SPREAD = "ratio_spread"
    CALENDAR_SPREAD = "calendar_spread"
    DIAGONAL_SPREAD = "diagonal_spread"


class ComplexStrategy(BasicStrategy):
    """Multi-leg complex strategy."""

    strategy_type: Literal[StrategyType.SPREAD] = Field(default=StrategyType.SPREAD)
    complex_type: ComplexStrategyType = Field(
        ..., description="Complex strategy subtype"
    )
    legs: List[Position] = Field(..., description="Strategy legs")
    underlying_symbol: str = Field(..., description="Underlying asset symbol")
    net_credit: float = Field(0.0, description="Net credit/debit (positive = credit)")
    max_profit: Optional[float] = Field(None, description="Maximum profit potential")
    max_loss: Optional[float] = Field(None, description="Maximum loss potential")
    breakeven_points: List[float] = Field(
        default_factory=list, description="Breakeven prices"
    )


class AdvancedStrategyAnalyzer:
    """Advanced strategy analysis with P&L calculation and Greeks aggregation."""

    def __init__(self):
        self.basic_analyzer = StrategyRecognitionService()

    def analyze_strategy_pnl(
        self,
        positions: List[Position],
        current_quotes: Dict[str, Union[Quote, OptionQuote]],
        entry_date: Optional[date] = None,
    ) -> List[StrategyPnL]:
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
        positions: List[Position],
        current_quotes: Dict[str, Union[Quote, OptionQuote]],
    ) -> StrategyGreeks:
        """
        Aggregate Greeks across all strategy positions.

        Args:
            positions: Portfolio positions with options
            current_quotes: Current market quotes with Greeks

        Returns:
            StrategyGreeks with aggregated exposure
        """
        total_greeks = StrategyGreeks()
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
                    position_value = abs(position.quantity * quote.price * multiplier)
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
        self, positions: List[Position]
    ) -> List[ComplexStrategy]:
        """
        Detect complex multi-leg strategies.

        Args:
            positions: Portfolio positions

        Returns:
            List of detected complex strategies
        """
        complex_strategies = []

        # Group positions by underlying
        by_underlying = {}
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

    def calculate_risk_metrics(
        self,
        positions: List[Position],
        historical_prices: Optional[List[Dict[str, float]]] = None,
    ) -> StrategyRiskMetrics:
        """
        Calculate comprehensive risk metrics for strategy portfolio.

        Args:
            positions: Portfolio positions
            historical_prices: Historical price data for volatility calculation

        Returns:
            StrategyRiskMetrics with risk analysis
        """
        metrics = StrategyRiskMetrics()

        # Calculate basic risk metrics
        if historical_prices:
            metrics = self._calculate_historical_risk_metrics(
                positions, historical_prices
            )

        # Calculate options-specific risk metrics
        options_positions = [p for p in positions if isinstance(p.asset, Option)]
        if options_positions:
            theta_risk = self._calculate_theta_risk(options_positions)
            assignment_risk = self._calculate_assignment_risk(options_positions)

            metrics.theta_risk_score = theta_risk["risk_score"]
            metrics.days_to_max_theta = theta_risk["days_to_max"]
            metrics.assignment_probability = assignment_risk["assignment_prob"]
            metrics.itm_probability = assignment_risk["itm_prob"]

        return metrics

    def generate_optimization_recommendations(
        self,
        positions: List[Position],
        current_quotes: Dict[str, Union[Quote, OptionQuote]],
    ) -> List[Dict[str, Any]]:
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
                    "description": f"High vega exposure ({greeks.vega:.0f}). Monitor volatility risk.",
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
        all_positions: List[Position],
        current_quotes: Dict[str, Union[Quote, OptionQuote]],
        entry_date: Optional[date],
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
            market_value = quote.price * abs(position.quantity) * multiplier

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
            days_held=days_held,
            annualized_return=annualized_return,
        )

    def _get_strategy_positions(
        self, strategy: BasicStrategy, all_positions: List[Position]
    ) -> List[Position]:
        """Get positions that belong to a specific strategy."""
        # Simplified matching - in a real implementation, this would be more sophisticated
        strategy_positions = []

        if isinstance(strategy, AssetStrategy):
            for position in all_positions:
                if position.asset.symbol == strategy.asset.symbol:
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
        self, underlying_symbol: str, positions: List[Position]
    ) -> List[ComplexStrategy]:
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
        self, calls: List[Position], puts: List[Position], underlying_symbol: str
    ) -> List[ComplexStrategy]:
        """Detect iron condor strategies."""
        iron_condors = []

        # Iron condor requires 4 legs with same expiration and quantities
        # Pattern: Short call (higher strike), Long call (even higher), Short put (lower strike), Long put (even lower)

        # Group by expiration
        call_expirations = {}
        put_expirations = {}

        for call_pos in calls:
            if isinstance(call_pos.asset, Call):
                exp_date = call_pos.asset.expiration_date
                if exp_date not in call_expirations:
                    call_expirations[exp_date] = []
                call_expirations[exp_date].append(call_pos)

        for put_pos in puts:
            if isinstance(put_pos.asset, Put):
                exp_date = put_pos.asset.expiration_date
                if exp_date not in put_expirations:
                    put_expirations[exp_date] = []
                put_expirations[exp_date].append(put_pos)

        # Check each expiration for iron condor patterns
        for exp_date in call_expirations:
            if exp_date not in put_expirations:
                continue

            calls_exp = call_expirations[exp_date]
            puts_exp = put_expirations[exp_date]

            # Sort by strike
            calls_exp.sort(key=lambda x: x.asset.strike)
            puts_exp.sort(key=lambda x: x.asset.strike)

            # Look for iron condor pattern
            for i in range(len(calls_exp) - 1):
                for j in range(i + 1, len(calls_exp)):
                    call_short = calls_exp[i]  # Lower strike call
                    call_long = calls_exp[j]  # Higher strike call

                    # Check if we have short/long pattern
                    if call_short.quantity >= 0 or call_long.quantity <= 0:
                        continue

                    # Check if quantities match
                    if abs(call_short.quantity) != abs(call_long.quantity):
                        continue

                    # Look for matching put spread
                    for k in range(len(puts_exp) - 1):
                        for m in range(k + 1, len(puts_exp)):
                            put_long = puts_exp[k]  # Lower strike put
                            put_short = puts_exp[m]  # Higher strike put

                            # Check pattern and quantities
                            if (
                                put_long.quantity <= 0
                                or put_short.quantity >= 0
                                or abs(put_long.quantity) != abs(call_short.quantity)
                                or abs(put_short.quantity) != abs(call_short.quantity)
                            ):
                                continue

                            # Calculate iron condor metrics
                            call_spread_width = (
                                call_long.asset.strike - call_short.asset.strike
                            )
                            put_spread_width = (
                                put_short.asset.strike - put_long.asset.strike
                            )

                            # Typical iron condor has equal width spreads
                            if abs(call_spread_width - put_spread_width) > 1.0:
                                continue

                            # Calculate net credit (should be positive for iron condor)
                            net_credit = (
                                call_short.avg_price * abs(call_short.quantity)
                                + put_short.avg_price * abs(put_short.quantity)
                                - call_long.avg_price * abs(call_long.quantity)
                                - put_long.avg_price * abs(put_long.quantity)
                            )

                            # Calculate max profit/loss
                            max_profit = net_credit * abs(call_short.quantity) * 100
                            max_loss = (
                                (call_spread_width - net_credit)
                                * abs(call_short.quantity)
                                * 100
                            )

                            # Calculate breakeven points
                            lower_breakeven = put_short.asset.strike - net_credit
                            upper_breakeven = call_short.asset.strike + net_credit

                            iron_condor = ComplexStrategy(
                                complex_type=ComplexStrategyType.IRON_CONDOR,
                                legs=[call_short, call_long, put_short, put_long],
                                underlying_symbol=underlying_symbol,
                                net_credit=net_credit,
                                max_profit=max_profit,
                                max_loss=max_loss,
                                breakeven_points=[lower_breakeven, upper_breakeven],
                                quantity=abs(call_short.quantity),
                            )
                            iron_condors.append(iron_condor)

        return iron_condors

    def _detect_straddles_strangles(
        self, calls: List[Position], puts: List[Position], underlying_symbol: str
    ) -> List[ComplexStrategy]:
        """Detect straddle and strangle strategies."""
        strategies = []

        # Group by expiration
        call_expirations = {}
        put_expirations = {}

        for call_pos in calls:
            if isinstance(call_pos.asset, Call):
                exp_date = call_pos.asset.expiration_date
                if exp_date not in call_expirations:
                    call_expirations[exp_date] = []
                call_expirations[exp_date].append(call_pos)

        for put_pos in puts:
            if isinstance(put_pos.asset, Put):
                exp_date = put_pos.asset.expiration_date
                if exp_date not in put_expirations:
                    put_expirations[exp_date] = []
                put_expirations[exp_date].append(put_pos)

        # Check each expiration for straddle/strangle patterns
        for exp_date in call_expirations:
            if exp_date not in put_expirations:
                continue

            calls_exp = call_expirations[exp_date]
            puts_exp = put_expirations[exp_date]

            # Check all call-put combinations
            for call_pos in calls_exp:
                for put_pos in puts_exp:
                    # Must have same direction (both long or both short) and quantity
                    if call_pos.quantity * put_pos.quantity <= 0 or abs(
                        call_pos.quantity
                    ) != abs(put_pos.quantity):
                        continue

                    call_strike = call_pos.asset.strike
                    put_strike = put_pos.asset.strike

                    # Determine if it's a straddle or strangle
                    if call_strike == put_strike:
                        # Straddle: same strike
                        strategy_type = ComplexStrategyType.STRADDLE
                    else:
                        # Strangle: different strikes
                        strategy_type = ComplexStrategyType.STRANGLE

                    # Calculate net debit/credit
                    net_cost = (call_pos.avg_price + put_pos.avg_price) * abs(
                        call_pos.quantity
                    )
                    if call_pos.quantity > 0:
                        net_credit = -net_cost  # Long positions are debits
                    else:
                        net_credit = net_cost  # Short positions are credits

                    # Calculate breakeven points
                    if strategy_type == ComplexStrategyType.STRADDLE:
                        # Straddle breakevens: strike ± net_premium
                        net_premium = abs(net_cost / abs(call_pos.quantity))
                        breakevens = [
                            call_strike - net_premium,
                            call_strike + net_premium,
                        ]
                    else:
                        # Strangle breakevens
                        net_premium = abs(net_cost / abs(call_pos.quantity))
                        lower_strike = min(call_strike, put_strike)
                        upper_strike = max(call_strike, put_strike)
                        breakevens = [
                            lower_strike - net_premium,
                            upper_strike + net_premium,
                        ]

                    # Calculate max profit/loss
                    if call_pos.quantity > 0:  # Long straddle/strangle
                        max_loss = net_cost * 100  # Premium paid
                        max_profit = None  # Unlimited upside
                    else:  # Short straddle/strangle
                        max_profit = net_cost * 100  # Premium received
                        max_loss = None  # Unlimited risk

                    strategy = ComplexStrategy(
                        complex_type=strategy_type,
                        legs=[call_pos, put_pos],
                        underlying_symbol=underlying_symbol,
                        net_credit=net_credit,
                        max_profit=max_profit,
                        max_loss=max_loss,
                        breakeven_points=breakevens,
                        quantity=abs(call_pos.quantity),
                    )
                    strategies.append(strategy)

        return strategies

    def _detect_butterflies(
        self, calls: List[Position], puts: List[Position], underlying_symbol: str
    ) -> List[ComplexStrategy]:
        """Detect butterfly strategies (call butterflies and put butterflies)."""
        butterflies = []

        # Call butterflies
        call_butterflies = self._detect_single_type_butterflies(
            calls, underlying_symbol, "call"
        )
        butterflies.extend(call_butterflies)

        # Put butterflies
        put_butterflies = self._detect_single_type_butterflies(
            puts, underlying_symbol, "put"
        )
        butterflies.extend(put_butterflies)

        # Iron butterflies (combination of call and put spreads)
        iron_butterflies = self._detect_iron_butterflies(calls, puts, underlying_symbol)
        butterflies.extend(iron_butterflies)

        return butterflies

    def _detect_single_type_butterflies(
        self, positions: List[Position], underlying_symbol: str, option_type: str
    ) -> List[ComplexStrategy]:
        """Detect single-type butterfly spreads (all calls or all puts)."""
        butterflies = []

        # Group by expiration
        expirations = {}
        for pos in positions:
            if isinstance(pos.asset, Option):
                exp_date = pos.asset.expiration_date
                if exp_date not in expirations:
                    expirations[exp_date] = []
                expirations[exp_date].append(pos)

        # Check each expiration for butterfly patterns
        for exp_date, positions_exp in expirations.items():
            # Sort by strike
            positions_exp.sort(key=lambda x: x.asset.strike)

            # Butterfly pattern: Long 1 low strike, Short 2 middle strike, Long 1 high strike
            # Or reverse: Short 1 low, Long 2 middle, Short 1 high

            for i in range(len(positions_exp) - 2):
                for j in range(i + 1, len(positions_exp) - 1):
                    for k in range(j + 1, len(positions_exp)):
                        low_pos = positions_exp[i]
                        mid_pos = positions_exp[j]
                        high_pos = positions_exp[k]

                        # Check if strikes are evenly spaced
                        strike_diff_1 = mid_pos.asset.strike - low_pos.asset.strike
                        strike_diff_2 = high_pos.asset.strike - mid_pos.asset.strike

                        if abs(strike_diff_1 - strike_diff_2) > 1.0:
                            continue

                        # Check butterfly pattern: +1, -2, +1 or -1, +2, -1
                        if (
                            low_pos.quantity == 1
                            and mid_pos.quantity == -2
                            and high_pos.quantity == 1
                        ):
                            # Long butterfly
                            strategy_type = ComplexStrategyType.BUTTERFLY
                            net_cost = (
                                low_pos.avg_price
                                + high_pos.avg_price
                                - 2 * mid_pos.avg_price
                            )
                            net_credit = -net_cost

                        elif (
                            low_pos.quantity == -1
                            and mid_pos.quantity == 2
                            and high_pos.quantity == -1
                        ):
                            # Short butterfly
                            strategy_type = ComplexStrategyType.BUTTERFLY
                            net_cost = (
                                2 * mid_pos.avg_price
                                - low_pos.avg_price
                                - high_pos.avg_price
                            )
                            net_credit = net_cost

                        else:
                            continue

                        # Calculate max profit/loss
                        width = strike_diff_1
                        if net_credit > 0:  # Short butterfly
                            max_profit = net_credit * 100
                            max_loss = (width - net_credit) * 100
                        else:  # Long butterfly
                            max_profit = (width + net_credit) * 100
                            max_loss = -net_credit * 100

                        # Calculate breakeven points
                        lower_breakeven = low_pos.asset.strike + abs(net_credit)
                        upper_breakeven = high_pos.asset.strike - abs(net_credit)

                        butterfly = ComplexStrategy(
                            complex_type=strategy_type,
                            legs=[low_pos, mid_pos, high_pos],
                            underlying_symbol=underlying_symbol,
                            net_credit=net_credit,
                            max_profit=max_profit,
                            max_loss=max_loss,
                            breakeven_points=[lower_breakeven, upper_breakeven],
                            quantity=1,
                        )
                        butterflies.append(butterfly)

        return butterflies

    def _detect_iron_butterflies(
        self, calls: List[Position], puts: List[Position], underlying_symbol: str
    ) -> List[ComplexStrategy]:
        """Detect iron butterfly strategies."""
        iron_butterflies = []

        # Iron butterfly: Short call + Short put (same strike) + Long call (higher) + Long put (lower)
        # Group by expiration
        call_expirations = {}
        put_expirations = {}

        for call_pos in calls:
            if isinstance(call_pos.asset, Call):
                exp_date = call_pos.asset.expiration_date
                if exp_date not in call_expirations:
                    call_expirations[exp_date] = []
                call_expirations[exp_date].append(call_pos)

        for put_pos in puts:
            if isinstance(put_pos.asset, Put):
                exp_date = put_pos.asset.expiration_date
                if exp_date not in put_expirations:
                    put_expirations[exp_date] = []
                put_expirations[exp_date].append(put_pos)

        # Check each expiration for iron butterfly patterns
        for exp_date in call_expirations:
            if exp_date not in put_expirations:
                continue

            calls_exp = call_expirations[exp_date]
            puts_exp = put_expirations[exp_date]

            # Look for short call and short put at same strike
            for call_pos in calls_exp:
                for put_pos in puts_exp:
                    if (
                        call_pos.quantity >= 0
                        or put_pos.quantity >= 0
                        or call_pos.asset.strike != put_pos.asset.strike
                    ):
                        continue

                    center_strike = call_pos.asset.strike

                    # Find long call (higher strike)
                    long_call = None
                    for c in calls_exp:
                        if c.quantity > 0 and c.asset.strike > center_strike:
                            long_call = c
                            break

                    # Find long put (lower strike)
                    long_put = None
                    for p in puts_exp:
                        if p.quantity > 0 and p.asset.strike < center_strike:
                            long_put = p
                            break

                    if long_call is None or long_put is None:
                        continue

                    # Check if wings are equidistant
                    call_width = long_call.asset.strike - center_strike
                    put_width = center_strike - long_put.asset.strike

                    if abs(call_width - put_width) > 1.0:
                        continue

                    # Calculate net credit
                    net_credit = (
                        call_pos.avg_price
                        + put_pos.avg_price
                        - long_call.avg_price
                        - long_put.avg_price
                    )

                    # Calculate max profit/loss
                    max_profit = net_credit * 100
                    max_loss = (call_width - net_credit) * 100

                    # Calculate breakeven points
                    lower_breakeven = long_put.asset.strike + net_credit
                    upper_breakeven = long_call.asset.strike - net_credit

                    iron_butterfly = ComplexStrategy(
                        complex_type=ComplexStrategyType.IRON_BUTTERFLY,
                        legs=[call_pos, put_pos, long_call, long_put],
                        underlying_symbol=underlying_symbol,
                        net_credit=net_credit,
                        max_profit=max_profit,
                        max_loss=max_loss,
                        breakeven_points=[lower_breakeven, upper_breakeven],
                        quantity=1,
                    )
                    iron_butterflies.append(iron_butterfly)

        return iron_butterflies

    def _detect_condors(
        self, calls: List[Position], puts: List[Position], underlying_symbol: str
    ) -> List[ComplexStrategy]:
        """Detect condor strategies (call condors and put condors)."""
        condors = []

        # Call condors
        call_condors = self._detect_single_type_condors(
            calls, underlying_symbol, "call"
        )
        condors.extend(call_condors)

        # Put condors
        put_condors = self._detect_single_type_condors(puts, underlying_symbol, "put")
        condors.extend(put_condors)

        return condors

    def _detect_single_type_condors(
        self, positions: List[Position], underlying_symbol: str, option_type: str
    ) -> List[ComplexStrategy]:
        """Detect single-type condor spreads (all calls or all puts)."""
        condors = []

        # Group by expiration
        expirations = {}
        for pos in positions:
            if isinstance(pos.asset, Option):
                exp_date = pos.asset.expiration_date
                if exp_date not in expirations:
                    expirations[exp_date] = []
                expirations[exp_date].append(pos)

        # Check each expiration for condor patterns
        for exp_date, positions_exp in expirations.items():
            # Sort by strike
            positions_exp.sort(key=lambda x: x.asset.strike)

            # Condor pattern: Long 1 low, Short 1 lower-mid, Short 1 upper-mid, Long 1 high
            # Or reverse for short condor

            for i in range(len(positions_exp) - 3):
                for j in range(i + 1, len(positions_exp) - 2):
                    for k in range(j + 1, len(positions_exp) - 1):
                        for m in range(k + 1, len(positions_exp)):
                            low_pos = positions_exp[i]
                            lower_mid_pos = positions_exp[j]
                            upper_mid_pos = positions_exp[k]
                            high_pos = positions_exp[m]

                            # Check condor pattern: +1, -1, -1, +1 or -1, +1, +1, -1
                            if (
                                low_pos.quantity == 1
                                and lower_mid_pos.quantity == -1
                                and upper_mid_pos.quantity == -1
                                and high_pos.quantity == 1
                            ):
                                # Long condor
                                net_cost = (
                                    low_pos.avg_price
                                    + high_pos.avg_price
                                    - lower_mid_pos.avg_price
                                    - upper_mid_pos.avg_price
                                )
                                net_credit = -net_cost

                            elif (
                                low_pos.quantity == -1
                                and lower_mid_pos.quantity == 1
                                and upper_mid_pos.quantity == 1
                                and high_pos.quantity == -1
                            ):
                                # Short condor
                                net_cost = (
                                    lower_mid_pos.avg_price
                                    + upper_mid_pos.avg_price
                                    - low_pos.avg_price
                                    - high_pos.avg_price
                                )
                                net_credit = net_cost

                            else:
                                continue

                            # Calculate max profit/loss
                            body_width = (
                                upper_mid_pos.asset.strike - lower_mid_pos.asset.strike
                            )
                            if net_credit > 0:  # Short condor
                                max_profit = net_credit * 100
                                max_loss = (body_width - net_credit) * 100
                            else:  # Long condor
                                max_profit = (body_width + net_credit) * 100
                                max_loss = -net_credit * 100

                            # Calculate breakeven points
                            lower_breakeven = lower_mid_pos.asset.strike + abs(
                                net_credit
                            )
                            upper_breakeven = upper_mid_pos.asset.strike - abs(
                                net_credit
                            )

                            condor = ComplexStrategy(
                                complex_type=ComplexStrategyType.CONDOR,
                                legs=[low_pos, lower_mid_pos, upper_mid_pos, high_pos],
                                underlying_symbol=underlying_symbol,
                                net_credit=net_credit,
                                max_profit=max_profit,
                                max_loss=max_loss,
                                breakeven_points=[lower_breakeven, upper_breakeven],
                                quantity=1,
                            )
                            condors.append(condor)

        return condors

    def _calculate_historical_risk_metrics(
        self, positions: List[Position], historical_prices: List[Dict[str, float]]
    ) -> StrategyRiskMetrics:
        """Calculate risk metrics from historical price data."""
        # Implementation would calculate volatility, VaR, etc. from historical data
        return StrategyRiskMetrics()

    def _calculate_theta_risk(
        self, options_positions: List[Position]
    ) -> Dict[str, Any]:
        """Calculate theta decay risk metrics."""
        total_theta = sum(getattr(p, "theta", 0.0) for p in options_positions)

        # Find position closest to expiration
        min_days_to_expiry = float("inf")
        for position in options_positions:
            if isinstance(position.asset, Option):
                days_to_expiry = (position.asset.expiration_date - date.today()).days
                min_days_to_expiry = min(min_days_to_expiry, days_to_expiry)

        # Calculate risk score (0-100)
        risk_score = min(100, abs(total_theta) / 10)  # Simplified scoring

        return {
            "risk_score": risk_score,
            "days_to_max": (
                int(min_days_to_expiry) if min_days_to_expiry != float("inf") else None
            ),
            "total_theta": total_theta,
        }

    def _calculate_assignment_risk(
        self, options_positions: List[Position]
    ) -> Dict[str, Any]:
        """Calculate assignment risk for short options."""
        # Simplified assignment risk calculation
        short_options = [p for p in options_positions if p.quantity < 0]

        assignment_prob = 0.0
        itm_prob = 0.0

        if short_options:
            # In a real implementation, this would use current prices and Greeks
            # to estimate probabilities
            assignment_prob = len(short_options) * 0.1  # Simplified
            itm_prob = len(short_options) * 0.15  # Simplified

        return {
            "assignment_prob": min(1.0, assignment_prob),
            "itm_prob": min(1.0, itm_prob),
        }

    def _generate_strategy_specific_recommendations(
        self,
        positions: List[Position],
        current_quotes: Dict[str, Union[Quote, OptionQuote]],
    ) -> List[Dict[str, Any]]:
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
    positions: List[Position],
    current_quotes: Dict[str, Union[Quote, OptionQuote]],
    entry_date: Optional[date] = None,
) -> List[StrategyPnL]:
    """Analyze comprehensive P&L for all strategies."""
    analyzer = AdvancedStrategyAnalyzer()
    return analyzer.analyze_strategy_pnl(positions, current_quotes, entry_date)


def aggregate_portfolio_greeks(
    positions: List[Position], current_quotes: Dict[str, Union[Quote, OptionQuote]]
) -> StrategyGreeks:
    """Aggregate Greeks across entire portfolio."""
    analyzer = AdvancedStrategyAnalyzer()
    return analyzer.aggregate_strategy_greeks(positions, current_quotes)


def detect_complex_strategies(positions: List[Position]) -> List[ComplexStrategy]:
    """Detect complex multi-leg strategies in portfolio."""
    analyzer = AdvancedStrategyAnalyzer()
    return analyzer.detect_complex_strategies(positions)


def get_portfolio_optimization_recommendations(
    positions: List[Position], current_quotes: Dict[str, Union[Quote, OptionQuote]]
) -> List[Dict[str, Any]]:
    """Get optimization recommendations for portfolio."""
    analyzer = AdvancedStrategyAnalyzer()
    return analyzer.generate_optimization_recommendations(positions, current_quotes)
