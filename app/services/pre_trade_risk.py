"""
Pre-trade risk analysis service for comprehensive order evaluation.

Integrates advanced validation, strategy analysis, Greeks calculation,
and scenario modeling to provide complete pre-trade risk assessment.
"""

from datetime import datetime, date
from typing import List, Dict, Any, Optional, Union, Tuple
from enum import Enum
from pydantic import BaseModel, Field
import numpy as np

from app.models.assets import Option, asset_factory
from app.models.trading import Order, MultiLegOrder, OrderType, Position
from app.models.quotes import Quote, OptionQuote
from app.services.advanced_validation import (
    AdvancedOrderValidator,
    ValidationResult,
    AccountLimits,
)
from app.services.strategies import (
    AdvancedStrategyAnalyzer,
    StrategyGreeks,
)
from app.services.order_impact import OrderImpactService, OrderImpactAnalysis


class RiskLevel(str, Enum):
    """Risk level classifications."""

    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    EXTREME = "extreme"


class ScenarioType(str, Enum):
    """Price scenario types for stress testing."""

    BASE_CASE = "base_case"
    BULL_CASE = "bull_case"
    BEAR_CASE = "bear_case"
    VOLATILITY_CRUSH = "volatility_crush"
    VOLATILITY_SPIKE = "volatility_spike"
    TIME_DECAY = "time_decay"


class PriceScenario(BaseModel):
    """Price scenario for stress testing."""

    scenario_type: ScenarioType = Field(..., description="Scenario type")
    description: str = Field(..., description="Scenario description")
    underlying_price_change: float = Field(
        ..., description="Underlying price change percentage"
    )
    volatility_change: float = Field(
        0.0, description="Implied volatility change percentage"
    )
    time_decay_days: int = Field(0, description="Days of time decay to apply")
    probability: float = Field(0.0, description="Estimated probability of scenario")


class ScenarioResult(BaseModel):
    """Result of scenario analysis."""

    scenario: PriceScenario = Field(..., description="Price scenario")
    portfolio_pnl: float = Field(..., description="Total portfolio P&L in scenario")
    order_pnl: float = Field(..., description="Order P&L in scenario")
    combined_pnl: float = Field(..., description="Combined portfolio + order P&L")
    max_loss: float = Field(..., description="Maximum potential loss")
    margin_call_risk: bool = Field(False, description="Risk of margin call in scenario")
    greeks_impact: StrategyGreeks = Field(..., description="Greeks changes in scenario")


class RiskMetrics(BaseModel):
    """Comprehensive risk metrics for pre-trade analysis."""

    overall_risk_level: RiskLevel = Field(..., description="Overall risk assessment")
    risk_score: float = Field(..., description="Numerical risk score (0-100)")

    # Portfolio metrics
    portfolio_var_1day: float = Field(0.0, description="1-day Value at Risk")
    portfolio_var_10day: float = Field(0.0, description="10-day Value at Risk")
    max_drawdown_potential: float = Field(0.0, description="Maximum potential drawdown")

    # Order-specific metrics
    order_risk_reward_ratio: float = Field(0.0, description="Risk/reward ratio")
    order_probability_profit: float = Field(0.0, description="Probability of profit")
    order_max_loss: float = Field(0.0, description="Maximum order loss")
    order_breakeven_moves: List[float] = Field(
        default_factory=list, description="Required moves to breakeven"
    )

    # Greeks risk
    delta_risk: float = Field(0.0, description="Delta exposure risk")
    gamma_risk: float = Field(0.0, description="Gamma risk (convexity)")
    theta_risk: float = Field(0.0, description="Time decay risk")
    vega_risk: float = Field(0.0, description="Volatility risk")

    # Time-based risks
    days_to_next_expiration: Optional[int] = Field(
        None, description="Days to nearest expiration"
    )
    theta_decay_impact: float = Field(
        0.0, description="Expected theta decay to expiration"
    )

    # Concentration and liquidity risks
    concentration_risk: float = Field(0.0, description="Concentration risk percentage")
    liquidity_risk: float = Field(0.0, description="Liquidity risk score")


class PreTradeAnalysis(BaseModel):
    """Comprehensive pre-trade risk analysis result."""

    # Core analysis
    validation_result: ValidationResult = Field(
        ..., description="Order validation results"
    )
    risk_metrics: RiskMetrics = Field(..., description="Risk assessment metrics")
    order_impact: OrderImpactAnalysis = Field(..., description="Order impact analysis")

    # Strategy analysis
    strategy_analysis: Dict[str, Any] = Field(
        default_factory=dict, description="Strategy-specific analysis"
    )
    portfolio_greeks: StrategyGreeks = Field(
        ..., description="Current portfolio Greeks"
    )
    projected_greeks: StrategyGreeks = Field(
        ..., description="Projected Greeks after order"
    )

    # Scenario analysis
    scenario_results: List[ScenarioResult] = Field(
        default_factory=list, description="Stress test results"
    )
    worst_case_loss: float = Field(0.0, description="Worst case scenario loss")
    best_case_gain: float = Field(0.0, description="Best case scenario gain")

    # Recommendations
    recommendations: List[Dict[str, Any]] = Field(
        default_factory=list, description="Risk management recommendations"
    )
    alternative_strategies: List[Dict[str, Any]] = Field(
        default_factory=list, description="Alternative strategy suggestions"
    )

    # Summary
    execution_recommendation: str = Field(
        ..., description="Execute/modify/reject recommendation"
    )
    confidence_level: float = Field(
        ..., description="Analysis confidence level (0-100)"
    )

    @property
    def should_execute(self) -> bool:
        """Whether order should be executed based on analysis."""
        return (
            self.validation_result.can_execute
            and self.risk_metrics.overall_risk_level != RiskLevel.EXTREME
            and self.execution_recommendation in ["execute", "execute_with_caution"]
        )


class PreTradeRiskAnalyzer:
    """
    Comprehensive pre-trade risk analysis engine.

    Integrates all risk analysis components to provide complete
    pre-trade assessment with scenario modeling and recommendations.
    """

    def __init__(self):
        self.validator = AdvancedOrderValidator()
        self.strategy_analyzer = AdvancedStrategyAnalyzer()
        self.impact_service = OrderImpactService()

    def analyze_order(
        self,
        account_data: Dict[str, Any],
        order: Union[Order, MultiLegOrder],
        current_quotes: Dict[str, Union[Quote, OptionQuote]],
        account_limits: Optional[AccountLimits] = None,
        include_scenarios: bool = True,
    ) -> PreTradeAnalysis:
        """
        Perform comprehensive pre-trade risk analysis.

        Args:
            account_data: Account state with positions and cash
            order: Order to analyze
            current_quotes: Current market quotes
            account_limits: Account limits and restrictions
            include_scenarios: Whether to run scenario analysis

        Returns:
            PreTradeAnalysis with comprehensive assessment
        """
        # Core validation
        validation_result = self.validator.validate_order(
            account_data, order, current_quotes, account_limits
        )

        # Order impact analysis
        order_impact = self.impact_service.analyze_order_impact(
            account_data, order, current_quotes
        )

        # Current portfolio Greeks
        positions = account_data.get("positions", [])
        portfolio_greeks = self.strategy_analyzer.aggregate_strategy_greeks(
            positions, current_quotes
        )

        # Projected Greeks after order
        projected_greeks = self._calculate_projected_greeks(
            positions, order, current_quotes
        )

        # Risk metrics calculation
        risk_metrics = self._calculate_risk_metrics(
            account_data,
            order,
            current_quotes,
            validation_result,
            portfolio_greeks,
            projected_greeks,
        )

        # Strategy analysis
        strategy_analysis = self._analyze_order_strategy(
            order, current_quotes, portfolio_greeks
        )

        # Scenario analysis
        scenario_results = []
        if include_scenarios:
            scenario_results = self._run_scenario_analysis(
                account_data, order, current_quotes
            )

        # Generate recommendations
        recommendations = self._generate_recommendations(
            validation_result, risk_metrics, order_impact, scenario_results
        )

        # Alternative strategies
        alternatives = self._suggest_alternatives(order, current_quotes, risk_metrics)

        # Execution recommendation
        execution_rec, confidence = self._make_execution_recommendation(
            validation_result, risk_metrics, scenario_results
        )

        # Calculate worst/best case from scenarios
        worst_case = min([s.combined_pnl for s in scenario_results], default=0.0)
        best_case = max([s.combined_pnl for s in scenario_results], default=0.0)

        return PreTradeAnalysis(
            validation_result=validation_result,
            risk_metrics=risk_metrics,
            order_impact=order_impact,
            strategy_analysis=strategy_analysis,
            portfolio_greeks=portfolio_greeks,
            projected_greeks=projected_greeks,
            scenario_results=scenario_results,
            worst_case_loss=worst_case,
            best_case_gain=best_case,
            recommendations=recommendations,
            alternative_strategies=alternatives,
            execution_recommendation=execution_rec,
            confidence_level=confidence,
        )

    def _calculate_projected_greeks(
        self,
        positions: List[Position],
        order: Union[Order, MultiLegOrder],
        current_quotes: Dict[str, Union[Quote, OptionQuote]],
    ) -> StrategyGreeks:
        """Calculate projected Greeks after order execution."""

        # Simulate order execution
        simulated_positions = positions.copy()

        # Add order positions (simplified simulation)
        if isinstance(order, Order):
            # Create simulated position
            asset = asset_factory(order.symbol)
            simulated_position = Position(
                symbol=order.symbol,
                quantity=order.quantity,
                avg_price=order.price
                or current_quotes.get(
                    order.symbol, Quote(asset=asset, quote_date=datetime.now(), price=0)
                ).price,
                current_price=current_quotes.get(
                    order.symbol, Quote(asset=asset, quote_date=datetime.now(), price=0)
                ).price,
                asset=asset,
            )
            simulated_positions.append(simulated_position)

        elif isinstance(order, MultiLegOrder):
            for leg in order.legs:
                simulated_position = Position(
                    symbol=leg.asset.symbol,
                    quantity=leg.quantity,
                    avg_price=leg.price
                    or current_quotes.get(
                        leg.asset.symbol,
                        Quote(asset=leg.asset, quote_date=datetime.now(), price=0),
                    ).price,
                    current_price=current_quotes.get(
                        leg.asset.symbol,
                        Quote(asset=leg.asset, quote_date=datetime.now(), price=0),
                    ).price,
                    asset=leg.asset,
                )
                simulated_positions.append(simulated_position)

        return self.strategy_analyzer.aggregate_strategy_greeks(
            simulated_positions, current_quotes
        )

    def _calculate_risk_metrics(
        self,
        account_data: Dict[str, Any],
        order: Union[Order, MultiLegOrder],
        current_quotes: Dict[str, Union[Quote, OptionQuote]],
        validation_result: ValidationResult,
        current_greeks: StrategyGreeks,
        projected_greeks: StrategyGreeks,
    ) -> RiskMetrics:
        """Calculate comprehensive risk metrics."""

        # Base risk level from validation
        risk_score = validation_result.risk_score

        if risk_score < 20:
            risk_level = RiskLevel.LOW
        elif risk_score < 50:
            risk_level = RiskLevel.MEDIUM
        elif risk_score < 80:
            risk_level = RiskLevel.HIGH
        else:
            risk_level = RiskLevel.EXTREME

        # Calculate Greeks risks
        delta_risk = abs(projected_greeks.delta - current_greeks.delta)
        theta_risk = abs(projected_greeks.theta - current_greeks.theta)
        vega_risk = abs(projected_greeks.vega - current_greeks.vega)

        # Estimate order max loss
        order_max_loss = self._estimate_order_max_loss(order, current_quotes)

        # Calculate concentration risk
        portfolio_value = self._calculate_portfolio_value(account_data, current_quotes)
        order_value = validation_result.estimated_cost
        concentration_risk = (
            (order_value / portfolio_value * 100) if portfolio_value > 0 else 0
        )

        # Estimate VaR (simplified)
        var_1day = portfolio_value * 0.02  # Simplified 2% VaR
        var_10day = var_1day * np.sqrt(10)

        # Find nearest expiration
        days_to_expiration = self._find_nearest_expiration(order)

        return RiskMetrics(
            overall_risk_level=risk_level,
            risk_score=risk_score,
            portfolio_var_1day=var_1day,
            portfolio_var_10day=var_10day,
            order_max_loss=order_max_loss,
            delta_risk=delta_risk,
            theta_risk=theta_risk,
            vega_risk=vega_risk,
            days_to_next_expiration=days_to_expiration,
            concentration_risk=concentration_risk,
            liquidity_risk=self._calculate_liquidity_risk(order, current_quotes),
        )

    def _analyze_order_strategy(
        self,
        order: Union[Order, MultiLegOrder],
        current_quotes: Dict[str, Union[Quote, OptionQuote]],
        portfolio_greeks: StrategyGreeks,
    ) -> Dict[str, Any]:
        """Analyze order from strategy perspective."""

        analysis = {
            "order_type": "single_leg" if isinstance(order, Order) else "multi_leg",
            "involves_options": self._involves_options(order),
            "strategy_classification": self._classify_strategy(order),
        }

        if isinstance(order, MultiLegOrder):
            analysis.update(
                {
                    "leg_count": len(order.legs),
                    "net_debit_credit": self._calculate_net_debit_credit(
                        order, current_quotes
                    ),
                    "expiration_consistency": self._check_expiration_consistency(order),
                    "underlying_consistency": self._check_underlying_consistency(order),
                }
            )

        return analysis

    def _run_scenario_analysis(
        self,
        account_data: Dict[str, Any],
        order: Union[Order, MultiLegOrder],
        current_quotes: Dict[str, Union[Quote, OptionQuote]],
    ) -> List[ScenarioResult]:
        """Run comprehensive scenario analysis."""

        scenarios = self._generate_price_scenarios(order, current_quotes)
        results = []

        for scenario in scenarios:
            result = self._analyze_scenario(
                account_data, order, current_quotes, scenario
            )
            results.append(result)

        return results

    def _generate_price_scenarios(
        self,
        order: Union[Order, MultiLegOrder],
        current_quotes: Dict[str, Union[Quote, OptionQuote]],
    ) -> List[PriceScenario]:
        """Generate price scenarios for stress testing."""

        scenarios = [
            PriceScenario(
                scenario_type=ScenarioType.BASE_CASE,
                description="Current market conditions",
                underlying_price_change=0.0,
                probability=0.4,
            ),
            PriceScenario(
                scenario_type=ScenarioType.BULL_CASE,
                description="Strong upward move (+10%)",
                underlying_price_change=0.10,
                probability=0.15,
            ),
            PriceScenario(
                scenario_type=ScenarioType.BEAR_CASE,
                description="Strong downward move (-10%)",
                underlying_price_change=-0.10,
                probability=0.15,
            ),
            PriceScenario(
                scenario_type=ScenarioType.VOLATILITY_CRUSH,
                description="Volatility crush (-50% IV)",
                underlying_price_change=0.0,
                volatility_change=-0.50,
                probability=0.1,
            ),
            PriceScenario(
                scenario_type=ScenarioType.TIME_DECAY,
                description="One week time decay",
                underlying_price_change=0.0,
                time_decay_days=7,
                probability=0.2,
            ),
        ]

        return scenarios

    def _analyze_scenario(
        self,
        account_data: Dict[str, Any],
        order: Union[Order, MultiLegOrder],
        current_quotes: Dict[str, Union[Quote, OptionQuote]],
        scenario: PriceScenario,
    ) -> ScenarioResult:
        """Analyze single price scenario."""

        # Simulate price changes
        scenario_quotes = self._apply_scenario_to_quotes(current_quotes, scenario)

        # Calculate portfolio P&L in scenario
        portfolio_pnl = self._calculate_portfolio_scenario_pnl(
            account_data.get("positions", []), current_quotes, scenario_quotes
        )

        # Calculate order P&L in scenario
        order_pnl = self._calculate_order_scenario_pnl(
            order, current_quotes, scenario_quotes
        )

        combined_pnl = portfolio_pnl + order_pnl

        # Calculate Greeks impact
        greeks_impact = self._calculate_scenario_greeks_impact(
            order, current_quotes, scenario_quotes
        )

        # Check margin call risk
        margin_call_risk = combined_pnl < -account_data.get("cash_balance", 0) * 0.5

        return ScenarioResult(
            scenario=scenario,
            portfolio_pnl=portfolio_pnl,
            order_pnl=order_pnl,
            combined_pnl=combined_pnl,
            max_loss=min(combined_pnl, 0),
            margin_call_risk=margin_call_risk,
            greeks_impact=greeks_impact,
        )

    def _generate_recommendations(
        self,
        validation_result: ValidationResult,
        risk_metrics: RiskMetrics,
        order_impact: OrderImpactAnalysis,
        scenario_results: List[ScenarioResult],
    ) -> List[Dict[str, Any]]:
        """Generate risk management recommendations."""

        recommendations = []

        # High-risk recommendations
        if risk_metrics.overall_risk_level == RiskLevel.EXTREME:
            recommendations.append(
                {
                    "type": "risk_warning",
                    "priority": "critical",
                    "message": "Extreme risk detected - consider avoiding this trade",
                    "details": {"risk_score": risk_metrics.risk_score},
                }
            )

        # Concentration risk
        if risk_metrics.concentration_risk > 20:
            recommendations.append(
                {
                    "type": "concentration_risk",
                    "priority": "high",
                    "message": f"High concentration risk ({risk_metrics.concentration_risk:.1f}% of portfolio)",
                    "suggestion": "Consider reducing position size",
                }
            )

        # Greeks exposure
        if risk_metrics.delta_risk > 1000:
            recommendations.append(
                {
                    "type": "delta_hedge",
                    "priority": "medium",
                    "message": f"High delta impact ({risk_metrics.delta_risk:.0f})",
                    "suggestion": "Consider delta hedging",
                }
            )

        # Time decay risk
        if risk_metrics.theta_risk > 50:
            recommendations.append(
                {
                    "type": "theta_risk",
                    "priority": "medium",
                    "message": f"High theta decay risk ({risk_metrics.theta_risk:.0f}/day)",
                    "suggestion": "Monitor time decay closely",
                }
            )

        # Scenario-based recommendations
        worst_scenario = min(
            scenario_results, key=lambda x: x.combined_pnl, default=None
        )
        if (
            worst_scenario
            and worst_scenario.combined_pnl < -risk_metrics.portfolio_var_10day
        ):
            recommendations.append(
                {
                    "type": "scenario_risk",
                    "priority": "high",
                    "message": f"Worst case scenario shows significant loss: ${worst_scenario.combined_pnl:,.2f}",
                    "suggestion": "Consider protective strategies",
                }
            )

        return recommendations

    def _suggest_alternatives(
        self,
        order: Union[Order, MultiLegOrder],
        current_quotes: Dict[str, Union[Quote, OptionQuote]],
        risk_metrics: RiskMetrics,
    ) -> List[Dict[str, Any]]:
        """Suggest alternative strategies."""

        alternatives = []

        # For high-risk single options, suggest spreads
        if (
            isinstance(order, Order)
            and isinstance(asset_factory(order.symbol), Option)
            and risk_metrics.overall_risk_level in [RiskLevel.HIGH, RiskLevel.EXTREME]
        ):
            alternatives.append(
                {
                    "strategy": "spread_alternative",
                    "description": "Consider a spread to reduce risk",
                    "risk_reduction": "Lower maximum loss and theta decay",
                    "trade_off": "Limited profit potential",
                }
            )

        # For high delta exposure, suggest hedging
        if risk_metrics.delta_risk > 500:
            alternatives.append(
                {
                    "strategy": "delta_hedge",
                    "description": "Add underlying stock position to hedge delta",
                    "risk_reduction": "Reduced directional risk",
                    "trade_off": "Additional capital required",
                }
            )

        return alternatives

    def _make_execution_recommendation(
        self,
        validation_result: ValidationResult,
        risk_metrics: RiskMetrics,
        scenario_results: List[ScenarioResult],
    ) -> Tuple[str, float]:
        """Make final execution recommendation."""

        confidence = 80.0  # Base confidence

        # Cannot execute if validation failed
        if not validation_result.can_execute:
            return "reject", confidence

        # Extreme risk - reject
        if risk_metrics.overall_risk_level == RiskLevel.EXTREME:
            return "reject", confidence

        # High risk - modify
        if risk_metrics.overall_risk_level == RiskLevel.HIGH:
            confidence -= 20
            return "modify", confidence

        # Check scenario outcomes
        negative_scenarios = sum(1 for s in scenario_results if s.combined_pnl < 0)
        total_scenarios = len(scenario_results)

        if total_scenarios > 0 and negative_scenarios / total_scenarios > 0.7:
            confidence -= 15
            return "execute_with_caution", confidence

        # Medium risk - execute with caution
        if risk_metrics.overall_risk_level == RiskLevel.MEDIUM:
            confidence -= 10
            return "execute_with_caution", confidence

        # Low risk - execute
        return "execute", confidence

    # Helper methods
    def _involves_options(self, order: Union[Order, MultiLegOrder]) -> bool:
        """Check if order involves options."""
        if isinstance(order, Order):
            return isinstance(asset_factory(order.symbol), Option)
        return any(isinstance(leg.asset, Option) for leg in order.legs)

    def _classify_strategy(self, order: Union[Order, MultiLegOrder]) -> str:
        """Classify the order strategy."""
        if isinstance(order, Order):
            asset = asset_factory(order.symbol)
            if isinstance(asset, Option):
                direction = "long" if order.quantity > 0 else "short"
                return f"{direction}_{asset.option_type}"
            else:
                return "stock_trade"
        else:
            return "multi_leg_strategy"

    def _calculate_net_debit_credit(
        self, order: MultiLegOrder, quotes: Dict[str, Union[Quote, OptionQuote]]
    ) -> float:
        """Calculate net debit/credit for multi-leg order."""
        net = 0.0
        for leg in order.legs:
            quote = quotes.get(leg.asset.symbol)
            if quote:
                price = leg.price or quote.price
                # Positive for credit (selling), negative for debit (buying)
                if leg.order_type in [OrderType.SELL, OrderType.STO]:
                    net += price * abs(leg.quantity)
                else:
                    net -= price * abs(leg.quantity)
        return net

    def _check_expiration_consistency(self, order: MultiLegOrder) -> bool:
        """Check if all legs have same expiration."""
        expirations = set()
        for leg in order.legs:
            if isinstance(leg.asset, Option):
                expirations.add(leg.asset.expiration_date)
        return len(expirations) <= 1

    def _check_underlying_consistency(self, order: MultiLegOrder) -> bool:
        """Check if all legs have same underlying."""
        underlyings = set()
        for leg in order.legs:
            if isinstance(leg.asset, Option):
                underlyings.add(leg.asset.underlying.symbol)
            else:
                underlyings.add(leg.asset.symbol)
        return len(underlyings) <= 1

    def _estimate_order_max_loss(
        self,
        order: Union[Order, MultiLegOrder],
        quotes: Dict[str, Union[Quote, OptionQuote]],
    ) -> float:
        """Estimate maximum possible loss from order."""
        # Simplified estimation
        if isinstance(order, Order):
            quote = quotes.get(order.symbol)
            if quote:
                return (
                    abs(order.quantity)
                    * quote.price
                    * (100 if isinstance(asset_factory(order.symbol), Option) else 1)
                )
        return 0.0

    def _calculate_portfolio_value(
        self, account_data: Dict[str, Any], quotes: Dict[str, Union[Quote, OptionQuote]]
    ) -> float:
        """Calculate total portfolio value."""
        total = account_data.get("cash_balance", 0.0)
        for position in account_data.get("positions", []):
            symbol = getattr(position, "symbol", position.get("symbol"))
            quantity = getattr(position, "quantity", position.get("quantity", 0))
            quote = quotes.get(symbol)
            if quote:
                total += abs(quantity) * quote.price
        return total

    def _find_nearest_expiration(
        self, order: Union[Order, MultiLegOrder]
    ) -> Optional[int]:
        """Find nearest expiration in order."""
        min_days = None

        symbols = []
        if isinstance(order, Order):
            symbols = [order.symbol]
        else:
            symbols = [leg.asset.symbol for leg in order.legs]

        for symbol in symbols:
            asset = asset_factory(symbol)
            if isinstance(asset, Option):
                days = (asset.expiration_date - date.today()).days
                if min_days is None or days < min_days:
                    min_days = days

        return min_days

    def _calculate_liquidity_risk(
        self,
        order: Union[Order, MultiLegOrder],
        quotes: Dict[str, Union[Quote, OptionQuote]],
    ) -> float:
        """Calculate liquidity risk score."""
        # Simplified liquidity risk calculation
        return 0.0

    def _apply_scenario_to_quotes(
        self, quotes: Dict[str, Union[Quote, OptionQuote]], scenario: PriceScenario
    ) -> Dict[str, Union[Quote, OptionQuote]]:
        """Apply scenario changes to quotes."""
        # Simplified scenario application
        return quotes.copy()

    def _calculate_portfolio_scenario_pnl(
        self,
        positions: List[Position],
        current_quotes: Dict[str, Union[Quote, OptionQuote]],
        scenario_quotes: Dict[str, Union[Quote, OptionQuote]],
    ) -> float:
        """Calculate portfolio P&L in scenario."""
        # Simplified P&L calculation
        return 0.0

    def _calculate_order_scenario_pnl(
        self,
        order: Union[Order, MultiLegOrder],
        current_quotes: Dict[str, Union[Quote, OptionQuote]],
        scenario_quotes: Dict[str, Union[Quote, OptionQuote]],
    ) -> float:
        """Calculate order P&L in scenario."""
        # Simplified P&L calculation
        return 0.0

    def _calculate_scenario_greeks_impact(
        self,
        order: Union[Order, MultiLegOrder],
        current_quotes: Dict[str, Union[Quote, OptionQuote]],
        scenario_quotes: Dict[str, Union[Quote, OptionQuote]],
    ) -> StrategyGreeks:
        """Calculate Greeks impact in scenario."""
        # Simplified Greeks calculation
        return StrategyGreeks()


# Convenience functions
def analyze_pre_trade_risk(
    account_data: Dict[str, Any],
    order: Union[Order, MultiLegOrder],
    current_quotes: Dict[str, Union[Quote, OptionQuote]],
    account_limits: Optional[AccountLimits] = None,
) -> PreTradeAnalysis:
    """Perform comprehensive pre-trade risk analysis."""
    analyzer = PreTradeRiskAnalyzer()
    return analyzer.analyze_order(account_data, order, current_quotes, account_limits)


def quick_risk_check(
    order: Union[Order, MultiLegOrder],
    current_quotes: Dict[str, Union[Quote, OptionQuote]],
) -> Dict[str, Any]:
    """Quick risk assessment for order."""
    analyzer = PreTradeRiskAnalyzer()

    # Simplified account data for quick check
    quick_account = {"cash_balance": 100000.0, "positions": []}

    analysis = analyzer.analyze_order(
        quick_account, order, current_quotes, include_scenarios=False
    )

    return {
        "risk_level": analysis.risk_metrics.overall_risk_level,
        "risk_score": analysis.risk_metrics.risk_score,
        "can_execute": analysis.should_execute,
        "key_warnings": [
            msg.message for msg in analysis.validation_result.warnings[:3]
        ],
    }
