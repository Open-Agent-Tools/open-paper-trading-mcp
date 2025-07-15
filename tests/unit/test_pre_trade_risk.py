"""
Tests for the pre-trade risk analyzer in app/services/pre_trade_risk.py.
"""
import pytest
from app.services.pre_trade_risk import PreTradeRiskAnalyzer, RiskLevel
from app.models.trading import Order, OrderType
from app.models.assets import Stock, Option
from app.models.quotes import Quote, OptionQuote
from datetime import datetime

@pytest.fixture
def risk_analyzer():
    """Provides a PreTradeRiskAnalyzer instance."""
    return PreTradeRiskAnalyzer()

@pytest.fixture
def sample_account_data():
    """Provides sample account data."""
    return {"cash_balance": 100000.0, "positions": []}

@pytest.fixture
def sample_quotes():
    """Provides sample quotes."""
    return {
        "AAPL": Quote(asset=Stock(symbol="AAPL"), quote_date=datetime.now(), price=155.0),
        "SPY251219C00500000": OptionQuote(
            asset=Option.from_symbol("SPY251219C00500000"),
            quote_date=datetime.now(),
            price=10.0,
            underlying_price=500.0,
            iv=0.20
        )
    }

def test_analyze_order_low_risk(risk_analyzer, sample_account_data, sample_quotes):
    """Tests the analysis of a low-risk order."""
    order = Order(symbol="AAPL", quantity=1, order_type=OrderType.BUY, price=155.0)
    analysis = risk_analyzer.analyze_order(sample_account_data, order, sample_quotes)
    assert analysis.risk_metrics.overall_risk_level == RiskLevel.LOW
    assert analysis.should_execute

def test_analyze_order_high_risk(risk_analyzer, sample_account_data, sample_quotes):
    """Tests the analysis of a high-risk order."""
    # A large naked option order should be high risk
    order = Order(symbol="SPY251219C00500000", quantity=-100, order_type=OrderType.STO, price=10.0)
    analysis = risk_analyzer.analyze_order(sample_account_data, order, sample_quotes)
    assert analysis.risk_metrics.overall_risk_level in [RiskLevel.HIGH, RiskLevel.EXTREME]
    assert not analysis.should_execute
