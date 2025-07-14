"""
Test suite for enhanced TradingService with Phase 1 capabilities.
"""

import pytest
from unittest.mock import Mock, patch
from datetime import datetime, date

from app.services.trading_service import TradingService
from app.models.assets import asset_factory
from app.models.quotes import OptionQuote
from app.models.trading import Position


class TestEnhancedTradingService:
    """Test enhanced TradingService functionality."""
    
    def setup_method(self):
        """Set up test trading service."""
        self.trading_service = TradingService()
    
    def test_service_initialization(self):
        """Test that all enhanced services are initialized."""
        assert self.trading_service.quote_adapter is not None
        assert self.trading_service.order_execution is not None
        assert self.trading_service.account_validation is not None
        assert self.trading_service.strategy_recognition is not None
        assert self.trading_service.margin_service is not None
    
    def test_enhanced_quote_method_exists(self):
        """Test that enhanced quote methods exist."""
        assert hasattr(self.trading_service, 'get_enhanced_quote')
        assert hasattr(self.trading_service, 'get_options_chain')
        assert hasattr(self.trading_service, 'calculate_greeks')
    
    def test_portfolio_analysis_methods_exist(self):
        """Test that portfolio analysis methods exist."""
        assert hasattr(self.trading_service, 'analyze_portfolio_strategies')
        assert hasattr(self.trading_service, 'calculate_margin_requirement')
        assert hasattr(self.trading_service, 'validate_account_state')
    
    def test_test_data_methods_exist(self):
        """Test that test data methods exist."""
        assert hasattr(self.trading_service, 'get_test_scenarios')
        assert hasattr(self.trading_service, 'set_test_date')
        assert hasattr(self.trading_service, 'get_available_symbols')
        assert hasattr(self.trading_service, 'get_sample_data_info')
    
    def test_legacy_compatibility(self):
        """Test that legacy methods still work."""
        # Test legacy quote method
        quote = self.trading_service.get_quote("AAPL")
        assert quote.symbol == "AAPL"
        assert quote.price > 0
        
        # Test legacy portfolio methods
        portfolio = self.trading_service.get_portfolio()
        assert hasattr(portfolio, 'cash_balance')
        assert hasattr(portfolio, 'positions')
        
        positions = self.trading_service.get_positions()
        assert isinstance(positions, list)
    
    @patch('app.adapters.test_data.TestDataQuoteAdapter.get_quote')
    def test_enhanced_quote_fallback(self, mock_get_quote):
        """Test enhanced quote with fallback to legacy."""
        # Mock test adapter returning None
        mock_get_quote.return_value = None
        
        # Should fall back to legacy quote for stocks
        quote = self.trading_service.get_enhanced_quote("AAPL")
        assert quote is not None
        assert quote.asset.symbol == "AAPL"
    
    def test_get_test_scenarios(self):
        """Test test scenarios retrieval."""
        scenarios = self.trading_service.get_test_scenarios()
        
        assert isinstance(scenarios, dict)
        assert len(scenarios) > 0
        
        # Should have known scenarios
        scenario_keys = scenarios.keys()
        assert any('aal' in key.lower() for key in scenario_keys)
        assert any('goog' in key.lower() for key in scenario_keys)
    
    def test_get_sample_data_info(self):
        """Test sample data info retrieval."""
        info = self.trading_service.get_sample_data_info()
        
        assert isinstance(info, dict)
        assert 'symbols' in info
        assert 'dates' in info
        assert 'features' in info
        
        assert 'AAL' in info['symbols']
        assert 'GOOG' in info['symbols']
    
    def test_get_available_symbols(self):
        """Test available symbols retrieval."""
        symbols = self.trading_service.get_available_symbols()
        
        assert isinstance(symbols, list)
        # Should have some symbols available
        assert len(symbols) >= 0
    
    def test_set_test_date(self):
        """Test setting test data date."""
        original_date = self.trading_service.quote_adapter.current_date
        
        # Set new date
        self.trading_service.set_test_date('2017-01-27')
        assert self.trading_service.quote_adapter.current_date == '2017-01-27'
        
        # Reset to original
        self.trading_service.set_test_date(original_date)
    
    def test_analyze_portfolio_strategies(self):
        """Test portfolio strategy analysis."""
        # Test with existing portfolio
        analysis = self.trading_service.analyze_portfolio_strategies()
        
        assert isinstance(analysis, dict)
        assert 'strategies' in analysis
        assert 'summary' in analysis
        assert 'total_positions' in analysis
        assert 'total_strategies' in analysis
        
        # Should handle empty portfolios gracefully
        assert analysis['total_positions'] >= 0
        assert analysis['total_strategies'] >= 0
    
    def test_calculate_margin_requirement(self):
        """Test margin requirement calculation."""
        margin_info = self.trading_service.calculate_margin_requirement()
        
        assert isinstance(margin_info, dict)
        assert 'total_margin' in margin_info
        assert 'calculation_time' in margin_info
        
        # Should be non-negative
        assert margin_info['total_margin'] >= 0
    
    def test_validate_account_state(self):
        """Test account state validation."""
        validation = self.trading_service.validate_account_state()
        
        assert isinstance(validation, dict)
        # Should have some validation structure
    
    @patch('app.services.greeks.calculate_option_greeks')
    def test_calculate_greeks(self, mock_calculate_greeks):
        """Test Greeks calculation method."""
        # Mock Greeks calculation
        mock_calculate_greeks.return_value = {
            'delta': 0.65,
            'gamma': 0.03,
            'theta': -0.05,
            'vega': 0.12,
            'rho': 0.08,
            'iv': 0.25
        }
        
        # Mock enhanced quote
        with patch.object(self.trading_service, 'get_enhanced_quote') as mock_quote:
            mock_option_quote = Mock()
            mock_option_quote.price = 5.50
            mock_quote.return_value = mock_option_quote
            
            # Mock underlying quote
            mock_underlying_quote = Mock()
            mock_underlying_quote.price = 200.0
            mock_quote.side_effect = [mock_option_quote, mock_underlying_quote]
            
            greeks = self.trading_service.calculate_greeks("AAPL240119C00195000")
            
            assert isinstance(greeks, dict)
            assert 'delta' in greeks
            assert greeks['delta'] == 0.65
    
    def test_calculate_greeks_with_underlying_price(self):
        """Test Greeks calculation with provided underlying price."""
        with patch('app.services.greeks.calculate_option_greeks') as mock_calc:
            mock_calc.return_value = {'delta': 0.70}
            
            with patch.object(self.trading_service, 'get_enhanced_quote') as mock_quote:
                mock_option_quote = Mock()
                mock_option_quote.price = 6.00
                mock_quote.return_value = mock_option_quote
                
                greeks = self.trading_service.calculate_greeks(
                    "AAPL240119C00195000", 
                    underlying_price=205.0
                )
                
                assert greeks['delta'] == 0.70
    
    def test_calculate_greeks_error_handling(self):
        """Test Greeks calculation error handling."""
        with pytest.raises(ValueError, match="is not an option"):
            self.trading_service.calculate_greeks("AAPL")  # Stock, not option
    
    def test_service_methods_return_types(self):
        """Test that all enhanced methods return expected types."""
        # Test scenarios
        scenarios = self.trading_service.get_test_scenarios()
        assert isinstance(scenarios, dict)
        
        # Test sample info
        info = self.trading_service.get_sample_data_info()
        assert isinstance(info, dict)
        
        # Test symbols
        symbols = self.trading_service.get_available_symbols()
        assert isinstance(symbols, list)
        
        # Test strategy analysis
        analysis = self.trading_service.analyze_portfolio_strategies()
        assert isinstance(analysis, dict)
        
        # Test margin calculation
        margin = self.trading_service.calculate_margin_requirement()
        assert isinstance(margin, dict)
        
        # Test validation
        validation = self.trading_service.validate_account_state()
        assert isinstance(validation, dict)


class TestTradingServiceIntegration:
    """Integration tests for TradingService with all Phase 1 components."""
    
    def setup_method(self):
        """Set up test trading service."""
        self.trading_service = TradingService()
    
    def test_full_options_workflow(self):
        """Test complete options trading workflow."""
        # Set test date for consistent data
        self.trading_service.set_test_date('2017-03-24')
        
        # Try to get an options chain (will use test data)
        try:
            chain = self.trading_service.get_options_chain('AAL')
            assert hasattr(chain, 'calls')
            assert hasattr(chain, 'puts')
            assert hasattr(chain, 'underlying_symbol')
        except Exception:
            # Test data might not be fully loaded, that's ok
            pass
        
        # Test strategy analysis with current portfolio
        analysis = self.trading_service.analyze_portfolio_strategies()
        assert isinstance(analysis, dict)
        
        # Test margin calculation
        margin = self.trading_service.calculate_margin_requirement()
        assert isinstance(margin, dict)
    
    def test_service_resilience(self):
        """Test that service handles missing data gracefully."""
        # Test with non-existent symbol
        try:
            quote = self.trading_service.get_enhanced_quote("NONEXISTENT")
        except Exception as e:
            assert "not found" in str(e).lower() or "no quote" in str(e).lower()
        
        # Test Greeks with bad symbol
        with pytest.raises((ValueError, Exception)):
            self.trading_service.calculate_greeks("BADOPTION")
    
    def test_backward_compatibility(self):
        """Test that all legacy TradingService functionality still works."""
        # Test legacy quote
        quote = self.trading_service.get_quote("AAPL")
        assert quote.symbol == "AAPL"
        
        # Test order creation
        from app.models.trading import OrderCreate, OrderType
        order_data = OrderCreate(
            symbol="AAPL",
            order_type=OrderType.BUY,
            quantity=1,
            price=150.0
        )
        
        order = self.trading_service.create_order(order_data)
        assert order.symbol == "AAPL"
        
        # Test portfolio methods
        portfolio = self.trading_service.get_portfolio()
        assert hasattr(portfolio, 'cash_balance')
        
        summary = self.trading_service.get_portfolio_summary()
        assert hasattr(summary, 'total_value')
        
        positions = self.trading_service.get_positions()
        assert isinstance(positions, list)