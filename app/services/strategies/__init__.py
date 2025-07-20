"""
Strategy analysis and recognition module.

This module provides comprehensive strategy analysis capabilities including:
- Basic strategy recognition and grouping
- Advanced P&L calculation and analysis
- Greeks aggregation
- Complex strategy detection
- Portfolio optimization recommendations

The module is organized into focused components:
- models: Core strategy models and data structures
- recognition: Basic strategy recognition and grouping
- analyzer: Advanced analysis and complex strategy detection
"""

# Core models and enums
# Advanced analyzer
from .analyzer import (
    AdvancedStrategyAnalyzer,
    aggregate_portfolio_greeks,
    analyze_advanced_strategy_pnl,
    detect_complex_strategies,
    get_portfolio_optimization_recommendations,
)
from .models import (
    AssetStrategy,
    # Base strategy models
    BasicStrategy,
    ComplexStrategy,
    ComplexStrategyType,
    CoveredStrategy,
    OffsetStrategy,
    SpreadStrategy,
    SpreadType,
    StrategyGreeks,
    # Analysis models
    StrategyPnL,
    # Enums
    StrategyType,
)

# Recognition service
from .recognition import (
    StrategyRecognitionService,
    analyze_strategy_portfolio,
    group_into_basic_strategies,
)

# Public API - exposed at package level
__all__ = [
    # Enums
    "StrategyType",
    "SpreadType",
    "ComplexStrategyType",
    # Strategy models
    "BasicStrategy",
    "AssetStrategy",
    "OffsetStrategy",
    "SpreadStrategy",
    "CoveredStrategy",
    "ComplexStrategy",
    # Analysis models
    "StrategyPnL",
    "StrategyGreeks",
    # Services
    "StrategyRecognitionService",
    "AdvancedStrategyAnalyzer",
    # Convenience functions
    "group_into_basic_strategies",
    "analyze_strategy_portfolio",
    "analyze_advanced_strategy_pnl",
    "aggregate_portfolio_greeks",
    "detect_complex_strategies",
    "get_portfolio_optimization_recommendations",
]
