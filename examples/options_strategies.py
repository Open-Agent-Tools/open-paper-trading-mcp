"""
Educational examples for common options strategies - Phase 5.3 implementation.
Demonstrates how to construct and analyze popular options trading strategies.
"""

from datetime import date, timedelta
from decimal import Decimal
from typing import Any

from app.models.trading import (
    MultiLegOrder,
    OrderCondition,
    OrderLeg,
    OrderSide,
    OrderType,
)
from app.services.greeks import calculate_option_greeks
from app.services.order_execution import OrderExecutionService
from app.services.order_impact import OrderImpactService
from app.services.strategies.recognition import StrategyRecognitionService


class OptionsStrategyExamples:
    """Educational examples for common options strategies."""

    def __init__(self):
        self.execution_service = OrderExecutionService()
        self.strategy_service = StrategyRecognitionService()
        self.impact_service = OrderImpactService()

    def covered_call_example(self) -> dict[str, Any]:
        """
        Covered Call Strategy Example

        Strategy: Own 100 shares of stock + Sell 1 call option
        Outlook: Neutral to slightly bullish
        Max Profit: Premium received + (Strike - Stock Purchase Price)
        Max Loss: Stock Purchase Price - Premium received
        """

        print("=== COVERED CALL STRATEGY EXAMPLE ===")

        # Scenario: Own 100 AAPL shares at $150, sell $155 call for $3.50
        underlying_symbol = "AAPL"
        stock_price = Decimal("150.00")
        strike_price = Decimal("155.00")
        premium = Decimal("3.50")
        expiration = date.today() + timedelta(days=30)

        # Create the covered call order (sell call when owning stock)
        call_symbol = (
            f"AAPL{expiration.strftime('%y%m%d')}C{int(strike_price * 1000):08d}"
        )

        order = MultiLegOrder.create_covered_call(
            underlying_symbol=underlying_symbol,
            call_symbol=call_symbol,
            call_premium=premium,
            shares_owned=100,
        )

        print(f"Underlying: {underlying_symbol} @ ${stock_price}")
        print(f"Call Option: {call_symbol}")
        print(f"Premium Received: ${premium}")
        print("Strategy: Covered Call")

        # Calculate potential outcomes
        breakeven = stock_price - premium
        max_profit = (strike_price - stock_price) + premium

        print("\nStrategy Analysis:")
        print(f"Breakeven Price: ${breakeven}")
        print(f"Maximum Profit: ${max_profit} (if stock >= ${strike_price})")
        print(f"Maximum Loss: Unlimited downside (minus ${premium} premium)")

        return {
            "strategy": "Covered Call",
            "order": order,
            "breakeven": breakeven,
            "max_profit": max_profit,
            "analysis": "Conservative income strategy - collects premium while capping upside",
        }

    def cash_secured_put_example(self) -> dict[str, Any]:
        """
        Cash-Secured Put Strategy Example

        Strategy: Sell put option while holding cash to buy shares if assigned
        Outlook: Neutral to bullish
        Max Profit: Premium received
        Max Loss: Strike Price - Premium received
        """

        print("\n=== CASH-SECURED PUT STRATEGY EXAMPLE ===")

        # Scenario: Sell $145 put on AAPL for $2.80, willing to buy at $145
        underlying_symbol = "AAPL"
        current_price = Decimal("150.00")
        strike_price = Decimal("145.00")
        premium = Decimal("2.80")
        expiration = date.today() + timedelta(days=45)

        put_symbol = (
            f"AAPL{expiration.strftime('%y%m%d')}P{int(strike_price * 1000):08d}"
        )

        order = MultiLegOrder(
            symbol="AAPL_CSP",
            order_type=OrderType.MULTI_LEG,
            legs=[
                OrderLeg(
                    symbol=put_symbol,
                    side=OrderSide.SELL,  # STO - Sell to Open
                    quantity=Decimal("1"),
                    price=premium,
                )
            ],
            total_price=premium,
            condition=OrderCondition.LIMIT,
        )

        print(f"Underlying: {underlying_symbol} @ ${current_price}")
        print(f"Put Option: {put_symbol}")
        print(f"Premium Received: ${premium}")
        print(f"Cash Required: ${strike_price * 100}")  # $14,500 cash to secure the put

        # Calculate potential outcomes
        breakeven = strike_price - premium
        max_profit = premium
        max_loss = strike_price - premium

        print("\nStrategy Analysis:")
        print(f"Breakeven Price: ${breakeven}")
        print(f"Maximum Profit: ${max_profit} (if stock >= ${strike_price})")
        print(f"Maximum Loss: ${max_loss} (if stock goes to $0)")
        print(f"Assignment Risk: If stock < ${strike_price} at expiration")

        return {
            "strategy": "Cash-Secured Put",
            "order": order,
            "breakeven": breakeven,
            "max_profit": max_profit,
            "max_loss": max_loss,
            "analysis": "Income strategy - get paid to potentially buy stock at discount",
        }

    def bull_call_spread_example(self) -> dict[str, Any]:
        """
        Bull Call Spread Strategy Example

        Strategy: Buy lower strike call + Sell higher strike call (same expiration)
        Outlook: Moderately bullish
        Max Profit: Spread width - Net debit paid
        Max Loss: Net debit paid
        """

        print("\n=== BULL CALL SPREAD STRATEGY EXAMPLE ===")

        # Scenario: AAPL at $150, buy $150 call, sell $155 call
        underlying_symbol = "AAPL"
        current_price = Decimal("150.00")
        long_strike = Decimal("150.00")
        short_strike = Decimal("155.00")
        long_premium = Decimal("5.50")  # Cost to buy $150 call
        short_premium = Decimal("3.00")  # Premium received for $155 call
        expiration = date.today() + timedelta(days=30)

        long_call_symbol = (
            f"AAPL{expiration.strftime('%y%m%d')}C{int(long_strike * 1000):08d}"
        )
        short_call_symbol = (
            f"AAPL{expiration.strftime('%y%m%d')}C{int(short_strike * 1000):08d}"
        )

        net_debit = long_premium - short_premium

        order = MultiLegOrder(
            symbol="AAPL_BULL_CALL_SPREAD",
            order_type=OrderType.MULTI_LEG,
            legs=[
                OrderLeg(
                    symbol=long_call_symbol,
                    side=OrderSide.BUY,  # BTO
                    quantity=Decimal("1"),
                    price=long_premium,
                ),
                OrderLeg(
                    symbol=short_call_symbol,
                    side=OrderSide.SELL,  # STO
                    quantity=Decimal("1"),
                    price=short_premium,
                ),
            ],
            total_price=net_debit,
            condition=OrderCondition.LIMIT,
        )

        print(f"Underlying: {underlying_symbol} @ ${current_price}")
        print(f"Long Call: {long_call_symbol} @ ${long_premium}")
        print(f"Short Call: {short_call_symbol} @ ${short_premium}")
        print(f"Net Debit: ${net_debit}")

        # Calculate potential outcomes
        spread_width = short_strike - long_strike
        max_profit = spread_width - net_debit
        max_loss = net_debit
        breakeven = long_strike + net_debit

        print("\nStrategy Analysis:")
        print(f"Spread Width: ${spread_width}")
        print(f"Breakeven Price: ${breakeven}")
        print(f"Maximum Profit: ${max_profit} (if stock >= ${short_strike})")
        print(f"Maximum Loss: ${max_loss} (if stock <= ${long_strike})")

        return {
            "strategy": "Bull Call Spread",
            "order": order,
            "net_debit": net_debit,
            "breakeven": breakeven,
            "max_profit": max_profit,
            "max_loss": max_loss,
            "analysis": "Limited risk, limited reward bullish strategy",
        }

    def iron_condor_example(self) -> dict[str, Any]:
        """
        Iron Condor Strategy Example

        Strategy: Sell call spread + Sell put spread (same expiration)
        Outlook: Neutral (expect low volatility)
        Max Profit: Net credit received
        Max Loss: Spread width - Net credit
        """

        print("\n=== IRON CONDOR STRATEGY EXAMPLE ===")

        # Scenario: AAPL at $150, create iron condor with $10 wings
        underlying_symbol = "AAPL"
        current_price = Decimal("150.00")

        # Put spread: Sell $140 put, Buy $135 put
        short_put_strike = Decimal("140.00")
        long_put_strike = Decimal("135.00")
        short_put_premium = Decimal("1.50")
        long_put_premium = Decimal("0.80")

        # Call spread: Sell $160 call, Buy $165 call
        short_call_strike = Decimal("160.00")
        long_call_strike = Decimal("165.00")
        short_call_premium = Decimal("1.20")
        long_call_premium = Decimal("0.60")

        expiration = date.today() + timedelta(days=45)

        # Create option symbols
        symbols = {
            "short_put": f"AAPL{expiration.strftime('%y%m%d')}P{int(short_put_strike * 1000):08d}",
            "long_put": f"AAPL{expiration.strftime('%y%m%d')}P{int(long_put_strike * 1000):08d}",
            "short_call": f"AAPL{expiration.strftime('%y%m%d')}C{int(short_call_strike * 1000):08d}",
            "long_call": f"AAPL{expiration.strftime('%y%m%d')}C{int(long_call_strike * 1000):08d}",
        }

        net_credit = (short_put_premium - long_put_premium) + (
            short_call_premium - long_call_premium
        )

        order = MultiLegOrder(
            symbol="AAPL_IRON_CONDOR",
            order_type=OrderType.MULTI_LEG,
            legs=[
                # Put spread legs
                OrderLeg(
                    symbol=symbols["short_put"],
                    side=OrderSide.SELL,
                    quantity=Decimal("1"),
                    price=short_put_premium,
                ),
                OrderLeg(
                    symbol=symbols["long_put"],
                    side=OrderSide.BUY,
                    quantity=Decimal("1"),
                    price=long_put_premium,
                ),
                # Call spread legs
                OrderLeg(
                    symbol=symbols["short_call"],
                    side=OrderSide.SELL,
                    quantity=Decimal("1"),
                    price=short_call_premium,
                ),
                OrderLeg(
                    symbol=symbols["long_call"],
                    side=OrderSide.BUY,
                    quantity=Decimal("1"),
                    price=long_call_premium,
                ),
            ],
            total_price=net_credit,
            condition=OrderCondition.LIMIT,
        )

        print(f"Underlying: {underlying_symbol} @ ${current_price}")
        print(
            f"Put Spread: Sell ${short_put_strike} put @ ${short_put_premium}, Buy ${long_put_strike} put @ ${long_put_premium}"
        )
        print(
            f"Call Spread: Sell ${short_call_strike} call @ ${short_call_premium}, Buy ${long_call_strike} call @ ${long_call_premium}"
        )
        print(f"Net Credit: ${net_credit}")

        # Calculate potential outcomes
        spread_width = (
            short_put_strike - long_put_strike
        )  # Both spreads have same width
        max_profit = net_credit
        max_loss = spread_width - net_credit
        upper_breakeven = short_call_strike + net_credit
        lower_breakeven = short_put_strike - net_credit

        print("\nStrategy Analysis:")
        print(f"Spread Width: ${spread_width}")
        print(f"Profit Zone: ${lower_breakeven} to ${upper_breakeven}")
        print(
            f"Maximum Profit: ${max_profit} (if ${short_put_strike} < stock < ${short_call_strike})"
        )
        print(
            f"Maximum Loss: ${max_loss} (if stock <= ${long_put_strike} or >= ${long_call_strike})"
        )

        return {
            "strategy": "Iron Condor",
            "order": order,
            "net_credit": net_credit,
            "profit_zone": (lower_breakeven, upper_breakeven),
            "max_profit": max_profit,
            "max_loss": max_loss,
            "analysis": "Neutral strategy that profits from low volatility",
        }

    def protective_put_example(self) -> dict[str, Any]:
        """
        Protective Put Strategy Example

        Strategy: Own stock + Buy put option for protection
        Outlook: Bullish but want downside protection
        Max Profit: Unlimited upside - Put premium
        Max Loss: Current stock price - Put strike + Put premium
        """

        print("\n=== PROTECTIVE PUT STRATEGY EXAMPLE ===")

        # Scenario: Own 100 AAPL shares at $150, buy $145 put for $2.50
        underlying_symbol = "AAPL"
        stock_price = Decimal("150.00")
        put_strike = Decimal("145.00")
        put_premium = Decimal("2.50")
        expiration = date.today() + timedelta(days=60)

        put_symbol = f"AAPL{expiration.strftime('%y%m%d')}P{int(put_strike * 1000):08d}"

        order = MultiLegOrder(
            symbol="AAPL_PROTECTIVE_PUT",
            order_type=OrderType.MULTI_LEG,
            legs=[
                OrderLeg(
                    symbol=put_symbol,
                    side=OrderSide.BUY,  # BTO
                    quantity=Decimal("1"),
                    price=put_premium,
                )
            ],
            total_price=put_premium,
            condition=OrderCondition.LIMIT,
        )

        print(f"Underlying: {underlying_symbol} @ ${stock_price} (own 100 shares)")
        print(f"Protective Put: {put_symbol} @ ${put_premium}")
        print(f"Cost of Protection: ${put_premium}")

        # Calculate potential outcomes
        max_loss = (stock_price - put_strike) + put_premium
        breakeven = stock_price + put_premium

        print("\nStrategy Analysis:")
        print(f"Breakeven Price: ${breakeven}")
        print(f"Maximum Loss: ${max_loss} (downside protected below ${put_strike})")
        print(f"Maximum Profit: Unlimited (minus ${put_premium} premium cost)")
        print(
            f"Insurance Cost: {(put_premium / stock_price * 100):.1f}% of stock value"
        )

        return {
            "strategy": "Protective Put",
            "order": order,
            "breakeven": breakeven,
            "max_loss": max_loss,
            "insurance_cost_pct": put_premium / stock_price * 100,
            "analysis": "Portfolio insurance - limits downside while preserving upside",
        }


def demonstrate_strategy_analysis():
    """Demonstrate strategy analysis and Greeks calculation."""

    print("\n" + "=" * 60)
    print("STRATEGY ANALYSIS AND GREEKS DEMONSTRATION")
    print("=" * 60)

    examples = OptionsStrategyExamples()

    # Run through all examples
    strategies = [
        examples.covered_call_example(),
        examples.cash_secured_put_example(),
        examples.bull_call_spread_example(),
        examples.iron_condor_example(),
        examples.protective_put_example(),
    ]

    print("\n" + "=" * 60)
    print("STRATEGY COMPARISON SUMMARY")
    print("=" * 60)

    for strategy_result in strategies:
        print(f"\n{strategy_result['strategy']}:")
        print(f"  Analysis: {strategy_result['analysis']}")

        if "max_profit" in strategy_result:
            print(f"  Max Profit: ${strategy_result['max_profit']}")
        if "max_loss" in strategy_result:
            print(f"  Max Loss: ${strategy_result['max_loss']}")
        if "breakeven" in strategy_result:
            print(f"  Breakeven: ${strategy_result['breakeven']}")


def demonstrate_greeks_analysis():
    """Demonstrate Greeks analysis for different option positions."""

    print("\n" + "=" * 60)
    print("OPTIONS GREEKS ANALYSIS DEMONSTRATION")
    print("=" * 60)

    # Example: Analyze Greeks for different moneyness and time to expiration
    scenarios = [
        {"name": "Deep ITM Call", "strike": 140, "spot": 160, "days": 30},
        {"name": "ATM Call", "strike": 150, "spot": 150, "days": 30},
        {"name": "OTM Call", "strike": 160, "spot": 150, "days": 30},
        {"name": "ATM Call - Near Expiry", "strike": 150, "spot": 150, "days": 7},
        {"name": "ATM Call - Long Term", "strike": 150, "spot": 150, "days": 90},
    ]

    print(
        f"{'Scenario':<25} {'Delta':<8} {'Gamma':<8} {'Theta':<8} {'Vega':<8} {'IV':<8}"
    )
    print("-" * 65)

    for scenario in scenarios:
        # Estimate option price (simplified)
        intrinsic = max(0, scenario["spot"] - scenario["strike"])
        time_value = 2.0 + (scenario["days"] / 365) * 3.0  # Simplified time value
        option_price = intrinsic + time_value

        try:
            greeks = calculate_option_greeks(
                option_type="call",
                strike=float(scenario["strike"]),
                underlying_price=float(scenario["spot"]),
                days_to_expiration=scenario["days"],
                option_price=option_price,
                risk_free_rate=0.05,
                dividend_yield=0.0,
            )

            print(
                f"{scenario['name']:<25} "
                f"{greeks['delta']:<8.3f} "
                f"{greeks['gamma']:<8.3f} "
                f"{greeks['theta']:<8.3f} "
                f"{greeks['vega']:<8.3f} "
                f"{greeks['iv']:<8.3f}"
            )

        except Exception as e:
            print(f"{scenario['name']:<25} Error: {str(e)[:30]}")


def demonstrate_risk_scenarios():
    """Demonstrate risk analysis for different market scenarios."""

    print("\n" + "=" * 60)
    print("RISK SCENARIO ANALYSIS")
    print("=" * 60)

    # Example: Bull call spread P&L at different stock prices
    print("\nBull Call Spread P&L Analysis (150/155 call spread for $2.50 debit)")
    print("Stock Price at Expiration vs Profit/Loss:")
    print(f"{'Stock Price':<12} {'P&L':<10} {'P&L %':<10} {'Notes'}")
    print("-" * 50)

    long_strike = 150
    short_strike = 155
    net_debit = 2.50

    stock_prices = [140, 145, 150, 152.5, 155, 160, 165]

    for stock_price in stock_prices:
        if stock_price <= long_strike:
            pnl = -net_debit  # Max loss
            notes = "Max Loss"
        elif stock_price >= short_strike:
            pnl = (short_strike - long_strike) - net_debit  # Max profit
            notes = "Max Profit"
        else:
            pnl = (stock_price - long_strike) - net_debit  # Between strikes
            notes = "Partial Profit"

        pnl_pct = (pnl / net_debit) * 100

        print(f"${stock_price:<11} ${pnl:<9.2f} {pnl_pct:<9.1f}% {notes}")


if __name__ == "__main__":
    """Run all educational examples."""

    print("OPTIONS TRADING EDUCATIONAL EXAMPLES")
    print("====================================")
    print("\nThis module demonstrates common options trading strategies")
    print("and shows how to construct them using our trading platform.")

    # Run demonstrations
    demonstrate_strategy_analysis()
    demonstrate_greeks_analysis()
    demonstrate_risk_scenarios()

    print("\n" + "=" * 60)
    print("EDUCATIONAL SUMMARY")
    print("=" * 60)
    print("""
Key Learning Points:

1. COVERED CALL: Conservative income strategy, caps upside
2. CASH-SECURED PUT: Get paid to potentially buy stock at discount
3. BULL CALL SPREAD: Limited risk/reward bullish strategy
4. IRON CONDOR: Neutral strategy that profits from low volatility
5. PROTECTIVE PUT: Portfolio insurance for long stock positions

Risk Management:
- Always understand maximum profit and loss before entering
- Consider breakeven points and probability of profit
- Monitor Greeks, especially delta and theta for time decay
- Use position sizing appropriate for your risk tolerance

Options Greeks:
- DELTA: Price sensitivity to underlying movement
- GAMMA: Rate of delta change (acceleration)
- THETA: Time decay (enemy of option buyers)
- VEGA: Volatility sensitivity
- RHO: Interest rate sensitivity (usually minor)

Remember: Options can expire worthless. Never risk more than you can afford to lose.
    """)
