"""
Portfolio analytics tools for advanced portfolio analysis and risk management.

These tools provide sophisticated portfolio metrics, risk analysis, and
performance attribution capabilities.
"""

import math
from datetime import datetime
from typing import Any

from app.mcp.base import get_trading_service
from app.mcp.response_utils import handle_tool_exception, success_response


async def calculate_portfolio_beta() -> dict[str, Any]:
    """
    Calculate portfolio beta relative to market benchmark (S&P 500).
    """
    try:
        # Get portfolio from trading service
        service = get_trading_service()
        portfolio = await service.get_portfolio()

        # Simulate beta calculation
        # In a real implementation, this would calculate actual beta using:
        # - Historical price data for each position
        # - Correlation with market benchmark
        # - Weighted average based on position sizes

        position_betas = []
        total_value = 0
        weighted_beta = 0

        for position in portfolio.positions:
            # Simulate individual stock betas
            if position.symbol == "AAPL":
                beta = 1.20
            elif position.symbol == "GOOGL":
                beta = 1.05
            elif position.symbol == "MSFT":
                beta = 0.90
            elif position.symbol == "JNJ":
                beta = 0.65
            else:
                beta = 1.0  # Default market beta

            position_value = position.quantity * position.current_price
            total_value += position_value
            weighted_beta += beta * position_value

            position_betas.append(
                {
                    "symbol": position.symbol,
                    "beta": beta,
                    "position_value": position_value,
                    "weight": 0,  # Will be calculated below
                }
            )

        # Calculate position weights and final portfolio beta
        portfolio_beta = weighted_beta / total_value if total_value > 0 else 1.0

        for pos_beta in position_betas:
            pos_beta["weight"] = (
                pos_beta["position_value"] / total_value if total_value > 0 else 0
            )

        data = {
            "portfolio_beta": round(portfolio_beta, 3),
            "benchmark": "S&P 500",
            "interpretation": {
                "risk_level": "high"
                if portfolio_beta > 1.2
                else "medium"
                if portfolio_beta > 0.8
                else "low",
                "market_sensitivity": f"{portfolio_beta:.1f}x market movement",
                "description": f"Portfolio moves {portfolio_beta:.1f}% for every 1% market move",
            },
            "position_betas": position_betas,
            "total_portfolio_value": total_value,
            "calculation_date": datetime.now().isoformat(),
        }

        return success_response(data)
    except Exception as e:
        return handle_tool_exception("calculate_portfolio_beta", e)


async def calculate_sharpe_ratio(period_days: int = 252) -> dict[str, Any]:
    """
    Calculate portfolio Sharpe ratio for risk-adjusted returns.

    Args:
        period_days: Number of days for calculation (default 252 = 1 year)
    """
    try:
        # Get portfolio from trading service
        service = get_trading_service()
        await service.get_portfolio()  # Portfolio fetched but not used in simulation

        # Simulate Sharpe ratio calculation
        # In reality, this would use:
        # - Historical portfolio returns
        # - Risk-free rate (Treasury rate)
        # - Portfolio volatility (standard deviation)

        # Simulate portfolio performance
        annual_return = 0.12  # 12% annual return
        annual_volatility = 0.18  # 18% annual volatility
        risk_free_rate = 0.04  # 4% risk-free rate

        # Calculate Sharpe ratio
        excess_return = annual_return - risk_free_rate
        sharpe_ratio = excess_return / annual_volatility

        # Risk-adjusted metrics
        treynor_ratio = excess_return / 1.1  # Assuming portfolio beta of 1.1
        information_ratio = 0.25  # Simulated

        data = {
            "sharpe_ratio": round(sharpe_ratio, 3),
            "annual_return": annual_return,
            "annual_volatility": annual_volatility,
            "risk_free_rate": risk_free_rate,
            "excess_return": excess_return,
            "interpretation": {
                "rating": "excellent"
                if sharpe_ratio > 2.0
                else "good"
                if sharpe_ratio > 1.0
                else "fair"
                if sharpe_ratio > 0.5
                else "poor",
                "description": f"Earning {sharpe_ratio:.2f} units of return per unit of risk",
            },
            "additional_metrics": {
                "treynor_ratio": round(treynor_ratio, 3),
                "information_ratio": information_ratio,
                "calmar_ratio": round(
                    annual_return / 0.08, 3
                ),  # Assuming 8% max drawdown
            },
            "period_days": period_days,
            "calculation_date": datetime.now().isoformat(),
        }

        return success_response(data)
    except Exception as e:
        return handle_tool_exception("calculate_sharpe_ratio", e)


async def calculate_var(
    confidence_level: float = 0.95, period_days: int = 1
) -> dict[str, Any]:
    """
    Calculate Value at Risk (VaR) for the portfolio.

    Args:
        confidence_level: Confidence level for VaR (default 0.95 = 95%)
        period_days: Period for VaR calculation (default 1 day)
    """
    try:
        # Get portfolio from trading service
        service = get_trading_service()
        portfolio = await service.get_portfolio()

        # Calculate portfolio value
        total_value = sum(
            pos.quantity * pos.current_price for pos in portfolio.positions
        )

        # Simulate VaR calculation
        # In reality, this would use:
        # - Historical portfolio returns
        # - Monte Carlo simulation or historical simulation
        # - Parametric approach with normal distribution

        # Simulate daily volatility
        daily_volatility = 0.018  # 1.8% daily volatility

        # Calculate VaR using parametric approach
        # Z-score for confidence level (95% = 1.645, 99% = 2.326)
        z_scores = {0.90: 1.282, 0.95: 1.645, 0.99: 2.326}
        z_score = z_scores.get(confidence_level, 1.645)

        var_percentage = z_score * daily_volatility * math.sqrt(period_days)
        var_amount = total_value * var_percentage

        # Expected Shortfall (Conditional VaR)
        expected_shortfall_percentage = var_percentage * 1.3  # Approximation
        expected_shortfall_amount = total_value * expected_shortfall_percentage

        data = {
            "var_amount": round(var_amount, 2),
            "var_percentage": round(var_percentage * 100, 2),
            "confidence_level": confidence_level,
            "period_days": period_days,
            "portfolio_value": total_value,
            "interpretation": {
                "description": f"With {confidence_level * 100}% confidence, portfolio will not lose more than ${var_amount:,.2f} in {period_days} day(s)",
                "risk_level": "high"
                if var_percentage > 0.05
                else "medium"
                if var_percentage > 0.02
                else "low",
            },
            "expected_shortfall": {
                "amount": round(expected_shortfall_amount, 2),
                "percentage": round(expected_shortfall_percentage * 100, 2),
                "description": "Expected loss if VaR threshold is exceeded",
            },
            "methodology": "Parametric VaR (normal distribution)",
            "calculation_date": datetime.now().isoformat(),
        }

        return success_response(data)
    except Exception as e:
        return handle_tool_exception("calculate_var", e)


async def get_portfolio_correlation() -> dict[str, Any]:
    """
    Calculate correlation matrix for portfolio positions.
    """
    try:
        # Get portfolio from trading service
        service = get_trading_service()
        portfolio = await service.get_portfolio()

        # Simulate correlation matrix
        # In reality, this would calculate actual correlations using historical price data

        symbols = [pos.symbol for pos in portfolio.positions]
        correlations = []

        # Simulate correlation coefficients
        correlation_data = {
            ("AAPL", "MSFT"): 0.72,
            ("AAPL", "GOOGL"): 0.68,
            ("AAPL", "TSLA"): 0.45,
            ("MSFT", "GOOGL"): 0.75,
            ("MSFT", "TSLA"): 0.38,
            ("GOOGL", "TSLA"): 0.42,
        }

        for i, symbol1 in enumerate(symbols):
            correlation_row = []
            for j, symbol2 in enumerate(symbols):
                if i == j:
                    corr = 1.0  # Perfect correlation with itself
                else:
                    # Look up correlation or use symmetric value
                    key = (
                        (symbol1, symbol2)
                        if (symbol1, symbol2) in correlation_data
                        else (symbol2, symbol1)
                    )
                    corr = correlation_data.get(key, 0.3)  # Default correlation

                correlation_row.append(
                    {
                        "symbol_pair": f"{symbol1}-{symbol2}",
                        "correlation": round(corr, 3),
                    }
                )
            correlations.append({"symbol": symbol1, "correlations": correlation_row})

        # Calculate average correlation
        total_correlations = 0
        correlation_count = 0
        for row in correlations:
            for corr in row["correlations"]:
                if corr["correlation"] != 1.0:  # Exclude self-correlation
                    total_correlations += corr["correlation"]
                    correlation_count += 1

        avg_correlation = (
            total_correlations / correlation_count if correlation_count > 0 else 0
        )

        data = {
            "correlation_matrix": correlations,
            "average_correlation": round(avg_correlation, 3),
            "interpretation": {
                "diversification_level": "low"
                if avg_correlation > 0.7
                else "medium"
                if avg_correlation > 0.4
                else "high",
                "description": f"Average correlation of {avg_correlation:.2f} indicates {'poor' if avg_correlation > 0.7 else 'moderate' if avg_correlation > 0.4 else 'good'} diversification",
            },
            "highest_correlation": max(
                [
                    corr
                    for row in correlations
                    for corr in row["correlations"]
                    if corr["correlation"] != 1.0
                ],
                key=lambda x: x["correlation"],
            ),
            "lowest_correlation": min(
                [
                    corr
                    for row in correlations
                    for corr in row["correlations"]
                    if corr["correlation"] != 1.0
                ],
                key=lambda x: x["correlation"],
            ),
            "calculation_date": datetime.now().isoformat(),
        }

        return success_response(data)
    except Exception as e:
        return handle_tool_exception("get_portfolio_correlation", e)


async def analyze_sector_allocation() -> dict[str, Any]:
    """
    Analyze portfolio allocation by market sector.
    """
    try:
        # Get portfolio from trading service
        service = get_trading_service()
        portfolio = await service.get_portfolio()

        # Map symbols to sectors (simulated)
        sector_mapping = {
            "AAPL": "Technology",
            "MSFT": "Technology",
            "GOOGL": "Technology",
            "TSLA": "Consumer Cyclical",
            "JNJ": "Healthcare",
            "JPM": "Financial Services",
            "XOM": "Energy",
            "PG": "Consumer Staples",
        }

        # Calculate sector allocations
        sector_values = {}
        total_value = 0

        for position in portfolio.positions:
            sector = sector_mapping.get(position.symbol, "Unknown")
            position_value = position.quantity * position.current_price
            total_value += position_value

            if sector not in sector_values:
                sector_values[sector] = {"value": 0, "positions": []}

            sector_values[sector]["value"] += position_value
            sector_values[sector]["positions"].append(
                {
                    "symbol": position.symbol,
                    "value": position_value,
                    "percentage": 0,  # Will be calculated below
                }
            )

        # Calculate percentages
        sector_allocations = []
        for sector, data in sector_values.items():
            sector_percentage = (
                (data["value"] / total_value * 100) if total_value > 0 else 0
            )

            # Update position percentages within sector
            for pos in data["positions"]:
                pos["percentage"] = (
                    (pos["value"] / total_value * 100) if total_value > 0 else 0
                )

            sector_allocations.append(
                {
                    "sector": sector,
                    "value": data["value"],
                    "percentage": round(sector_percentage, 2),
                    "positions": data["positions"],
                }
            )

        # Sort by allocation percentage
        sector_allocations.sort(key=lambda x: x["percentage"], reverse=True)

        # Benchmark comparison (simulated ideal allocation)
        benchmark_allocation = {
            "Technology": 25.0,
            "Healthcare": 15.0,
            "Financial Services": 12.0,
            "Consumer Cyclical": 12.0,
            "Consumer Staples": 8.0,
            "Energy": 5.0,
            "Utilities": 3.0,
            "Other": 20.0,
        }

        data = {
            "sector_allocations": sector_allocations,
            "total_portfolio_value": total_value,
            "largest_sector": sector_allocations[0] if sector_allocations else None,
            "concentration_risk": {
                "top_sector_percentage": sector_allocations[0]["percentage"]
                if sector_allocations
                else 0,
                "risk_level": "high"
                if (sector_allocations[0]["percentage"] if sector_allocations else 0)
                > 40
                else "medium"
                if (sector_allocations[0]["percentage"] if sector_allocations else 0)
                > 25
                else "low",
            },
            "benchmark_comparison": benchmark_allocation,
            "diversification_score": min(
                100,
                max(
                    0,
                    100
                    - (
                        sector_allocations[0]["percentage"] if sector_allocations else 0
                    ),
                ),
            ),
            "calculation_date": datetime.now().isoformat(),
        }

        return success_response(data)
    except Exception as e:
        return handle_tool_exception("analyze_sector_allocation", e)


async def get_risk_metrics() -> dict[str, Any]:
    """
    Get comprehensive portfolio risk metrics.
    """
    try:
        # Get portfolio from trading service
        service = get_trading_service()
        portfolio = await service.get_portfolio()

        # Calculate total portfolio value
        total_value = sum(
            pos.quantity * pos.current_price for pos in portfolio.positions
        )

        # Simulate comprehensive risk metrics
        metrics = {
            "volatility": {
                "daily": 0.018,
                "weekly": 0.040,
                "monthly": 0.082,
                "annual": 0.186,
            },
            "downside_metrics": {
                "downside_deviation": 0.125,
                "maximum_drawdown": 0.084,
                "pain_index": 0.032,
                "ulcer_index": 0.045,
            },
            "risk_ratios": {
                "sharpe_ratio": 1.25,
                "sortino_ratio": 1.68,
                "calmar_ratio": 1.43,
                "omega_ratio": 1.89,
            },
            "tail_risk": {
                "var_95": total_value * 0.032,
                "var_99": total_value * 0.048,
                "expected_shortfall_95": total_value * 0.042,
                "expected_shortfall_99": total_value * 0.062,
            },
            "concentration_risk": {
                "herfindahl_index": 0.28,
                "effective_number_of_positions": len(portfolio.positions) * 0.65,
                "largest_position_weight": 0.35,
            },
        }

        # Overall risk assessment
        risk_score = 0
        if metrics["volatility"]["annual"] > 0.25:
            risk_score += 3
        elif metrics["volatility"]["annual"] > 0.15:
            risk_score += 2
        else:
            risk_score += 1

        if metrics["downside_metrics"]["maximum_drawdown"] > 0.15:
            risk_score += 3
        elif metrics["downside_metrics"]["maximum_drawdown"] > 0.08:
            risk_score += 2
        else:
            risk_score += 1

        risk_levels = {
            1: "very_low",
            2: "low",
            3: "medium",
            4: "high",
            5: "very_high",
            6: "extreme",
        }

        data = {
            "portfolio_value": total_value,
            "risk_metrics": metrics,
            "overall_risk_assessment": {
                "risk_score": risk_score,
                "risk_level": risk_levels.get(risk_score, "medium"),
                "description": f"Portfolio exhibits {risk_levels.get(risk_score, 'medium').replace('_', ' ')} risk characteristics",
            },
            "recommendations": [
                "Consider diversifying across more sectors"
                if metrics["concentration_risk"]["largest_position_weight"] > 0.3
                else "Sector diversification appears adequate",
                "Monitor volatility levels"
                if metrics["volatility"]["annual"] > 0.2
                else "Volatility within acceptable range",
                "Review drawdown management"
                if metrics["downside_metrics"]["maximum_drawdown"] > 0.1
                else "Drawdown control effective",
            ],
            "calculation_date": datetime.now().isoformat(),
        }

        return success_response(data)
    except Exception as e:
        return handle_tool_exception("get_risk_metrics", e)
