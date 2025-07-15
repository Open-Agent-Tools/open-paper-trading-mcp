"""
Tests for the margin calculation service in app/services/margin.py.
"""
import pytest
from unittest.mock import Mock
from app.services.margin import MaintenanceMarginService, MarginCalculationResult
from app.services.strategies.models import AssetStrategy, SpreadStrategy, CoveredStrategy, SpreadType
from app.models.assets import Asset, Option, asset_factory
from app.models.trading import Position

class TestMaintenanceMarginService:

    @pytest.fixture
    def mock_quote_adapter(self):
        """Provides a mock quote adapter that returns predictable prices."""
        adapter = Mock()
        def get_quote(asset):
            quote = Mock()
            if isinstance(asset, Stock):
                quote.price = 150.0
            elif isinstance(asset, Option):
                quote.price = 5.0 # Premium
            return quote
        adapter.get_quote.side_effect = get_quote
        return adapter

    @pytest.fixture
    def margin_service(self, mock_quote_adapter):
        """Provides a MaintenanceMarginService instance with a mock adapter."""
        return MaintenanceMarginService(quote_adapter=mock_quote_adapter)

    def test_calculate_maintenance_margin_empty(self, margin_service):
        """Test calculating margin for an empty list of positions."""
        result = margin_service.calculate_maintenance_margin(positions=[])
        assert isinstance(result, MarginCalculationResult)
        assert result.total_margin_requirement == 0

    def test_calculate_long_stock_margin(self, margin_service):
        """Tests that a long stock position requires no margin."""
        strategy = AssetStrategy(asset=Asset(symbol="AAPL"), quantity=100)
        margin_req = margin_service._calculate_asset_margin(strategy, margin_service.quote_adapter)
        assert margin_req.margin_requirement == 0

    def test_calculate_short_stock_margin(self, margin_service):
        """Tests margin calculation for a short stock position."""
        strategy = AssetStrategy(asset=Asset(symbol="AAPL"), quantity=-100)
        margin_req = margin_service._calculate_asset_margin(strategy, margin_service.quote_adapter)
        # Margin = 100 * 150.0 * 1.0 = 15000
        assert margin_req.margin_requirement == 15000.0

    def test_calculate_naked_call_margin(self, margin_service):
        """Tests margin calculation for a naked call."""
        strategy = AssetStrategy(asset=asset_factory("AAPL241220C00160000"), quantity=-1)
        margin_req = margin_service._calculate_asset_margin(strategy, margin_service.quote_adapter)
        assert margin_req.margin_requirement > 0

    def test_calculate_naked_put_margin(self, margin_service):
        """Tests margin calculation for a naked put."""
        pytest.fail("Test not implemented")

    def test_calculate_credit_spread_margin(self, margin_service):
        """Tests margin calculation for a credit spread."""
        sell_option = asset_factory("SPY251219P00490000")
        buy_option = asset_factory("SPY251219P00480000")
        strategy = SpreadStrategy(sell_option=sell_option, buy_option=buy_option, quantity=1)
        
        margin_req = margin_service._calculate_spread_margin(strategy, margin_service.quote_adapter)
        expected_margin = (490.0 - 480.0) * 100
        assert margin_req.margin_requirement == expected_margin

    def test_calculate_debit_spread_margin(self, margin_service):
        """Tests margin calculation for a debit spread."""
        sell_option = asset_factory("SPY251219C00500000")
        buy_option = asset_factory("SPY251219C00510000")
        strategy = SpreadStrategy(sell_option=sell_option, buy_option=buy_option, quantity=1)
        strategy.spread_type = SpreadType.DEBIT
        
        margin_req = margin_service._calculate_spread_margin(strategy, margin_service.quote_adapter)
        assert margin_req.margin_requirement == 0

    def test_calculate_covered_call_margin(self, margin_service):
        """Tests that a covered call requires no additional margin."""
        strategy = CoveredStrategy(asset=Stock(symbol="AAPL"), sell_option=asset_factory("AAPL241220C00160000"), quantity=1)
        margin_req = margin_service._calculate_covered_margin(strategy, margin_service.quote_adapter)
        assert margin_req.margin_requirement == 0

    def test_get_portfolio_margin_breakdown(self, margin_service):
        """Tests the detailed margin breakdown function."""
        pytest.fail("Test not implemented")

    def test_calculation_with_missing_quote(self, margin_service):
        """Tests that the service handles missing quotes gracefully."""
        margin_service.quote_adapter.get_quote.return_value = None
        positions = [Position(symbol="FAIL", quantity=-100)]
        result = margin_service.calculate_maintenance_margin(positions=positions)
        assert result.total_margin_requirement == 0
        assert len(result.warnings) == 1
        assert "Failed to calculate margin" in result.warnings[0]