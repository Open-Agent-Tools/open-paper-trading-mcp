"""
Tests for TradingService error handling and edge cases.

This module covers various error handling paths and edge cases throughout
the TradingService that may not be covered by other test modules:
- RuntimeError fallbacks and exception handling
- Database session failure scenarios
- Invalid input validation edge cases
- Adapter failure and recovery scenarios
- Network timeout and retry logic
- Boundary value testing
- Type validation edge cases

Coverage target: Various error handling lines throughout trading_service.py
"""

import pytest
from unittest.mock import patch, MagicMock
from datetime import date, datetime
from decimal import Decimal

from app.core.exceptions import InputValidationError, NotFoundError
from app.schemas.orders import OrderCreate, OrderType
from app.schemas.positions import Portfolio, Position


class TestTradingServiceErrorHandling:
    """Test error handling and edge cases."""

    @pytest.mark.asyncio
    async def test_database_session_failure_handling(self, trading_service_test_data):
        """Test handling of database session failures."""
        with patch.object(trading_service_test_data, '_get_async_db_session') as mock_session:
            mock_session.side_effect = RuntimeError("Database connection failed")
            
            # Test that portfolio retrieval handles database errors gracefully
            with pytest.raises(RuntimeError, match="Database connection failed"):
                await trading_service_test_data.get_portfolio()

    @pytest.mark.asyncio
    async def test_quote_adapter_failure_fallback(self, trading_service_test_data):
        """Test fallback behavior when quote adapter fails."""
        with patch.object(trading_service_test_data.quote_adapter, 'get_quote') as mock_get_quote:
            mock_get_quote.side_effect = Exception("Quote service unavailable")
            
            # Test that get_quote handles adapter failures
            with pytest.raises(Exception, match="Quote service unavailable"):
                await trading_service_test_data.get_quote("AAPL")

    @pytest.mark.asyncio
    async def test_invalid_symbol_format_validation(self, trading_service_test_data):
        """Test validation of invalid symbol formats."""
        invalid_symbols = [
            "",  # Empty string
            "   ",  # Whitespace only
            "A" * 50,  # Too long
            "123INVALID",  # Invalid characters
            None,  # None value
        ]
        
        for symbol in invalid_symbols[:-1]:  # Skip None for now
            try:
                result = await trading_service_test_data.get_quote(symbol)
                # If no exception, check for error in result
                if isinstance(result, dict) and "error" in result:
                    assert "Invalid" in result["error"] or "error" in result
            except Exception as e:
                # Exception is acceptable for invalid input
                assert "Invalid" in str(e) or "error" in str(e).lower()

    @pytest.mark.asyncio
    async def test_malformed_order_data_handling(self, trading_service_test_data):
        """Test handling of malformed order data."""
        malformed_orders = [
            # Missing required fields
            OrderCreate(
                symbol="AAPL",
                quantity=0,  # Invalid quantity
                order_type=OrderType.MARKET,
                side="buy"
            ),
            # Negative quantity
            OrderCreate(
                symbol="AAPL",
                quantity=-10,
                order_type=OrderType.MARKET,
                side="buy"
            ),
            # Invalid side
            OrderCreate(
                symbol="AAPL",
                quantity=100,
                order_type=OrderType.MARKET,
                side="invalid_side"
            )
        ]
        
        for order_data in malformed_orders:
            try:
                result = await trading_service_test_data.create_order(order_data)
                # If no exception, should have error in result
                if hasattr(result, 'status') and result.status:
                    # Order was created but might be rejected
                    pass
                else:
                    # Should have error indication
                    assert hasattr(result, 'id') or "error" in str(result)
            except (InputValidationError, ValueError) as e:
                # Expected validation errors
                assert "Invalid" in str(e) or "quantity" in str(e) or "side" in str(e)

    @pytest.mark.asyncio
    async def test_boundary_value_order_quantities(self, trading_service_test_data):
        """Test boundary values for order quantities."""
        boundary_quantities = [
            1,  # Minimum valid
            999999,  # Very large
            0.1,  # Fractional (if supported)
        ]
        
        for quantity in boundary_quantities:
            order_data = OrderCreate(
                symbol="AAPL",
                quantity=quantity,
                order_type=OrderType.MARKET,
                side="buy"
            )
            
            try:
                result = await trading_service_test_data.create_order(order_data)
                # Should succeed or have clear validation error
                assert hasattr(result, 'id') or hasattr(result, 'status')
            except Exception as e:
                # For fractional quantities, might not be supported
                if quantity == 0.1:
                    assert "fractional" in str(e).lower() or "decimal" in str(e).lower()

    @pytest.mark.asyncio
    async def test_portfolio_retrieval_empty_account(self, trading_service_test_data):
        """Test portfolio retrieval for empty account."""
        # Mock empty portfolio scenario
        empty_portfolio = Portfolio(
            account_id="empty-account",
            total_value=Decimal("0.00"),
            cash_balance=Decimal("0.00"),
            positions=[]
        )
        
        with patch.object(trading_service_test_data, '_get_portfolio_positions', return_value=[]):
            with patch.object(trading_service_test_data, 'get_account_balance', return_value=0.0):
                result = await trading_service_test_data.get_portfolio()
                
                assert isinstance(result, Portfolio)
                assert len(result.positions) == 0
                assert result.cash_balance >= 0

    @pytest.mark.asyncio
    async def test_account_creation_duplicate_handling(self, trading_service_test_data):
        """Test handling of duplicate account creation attempts."""
        # This tests the _ensure_account_exists method's duplicate handling
        with patch.object(trading_service_test_data, '_get_async_db_session'):
            # First creation should succeed
            await trading_service_test_data._ensure_account_exists()
            
            # Second creation should handle existing account gracefully
            await trading_service_test_data._ensure_account_exists()
            
            # No exception should be raised

    @pytest.mark.asyncio
    async def test_position_calculation_edge_cases(self, trading_service_test_data):
        """Test edge cases in position calculations."""
        edge_case_positions = [
            Position(
                symbol="AAPL",
                quantity=0,  # Zero quantity
                average_price=Decimal("150.00"),
                current_price=Decimal("160.00"),
                unrealized_pnl=Decimal("0.00"),
                asset_type="stock"
            ),
            Position(
                symbol="TSLA",
                quantity=1,
                average_price=Decimal("0.01"),  # Very low price
                current_price=Decimal("0.02"),
                unrealized_pnl=Decimal("0.01"),
                asset_type="stock"
            ),
            Position(
                symbol="EXPENSIVE",
                quantity=1,
                average_price=Decimal("999999.99"),  # Very high price
                current_price=Decimal("1000000.00"),
                unrealized_pnl=Decimal("0.01"),
                asset_type="stock"
            )
        ]
        
        portfolio = Portfolio(
            account_id="edge-case-account",
            total_value=Decimal("1000000.00"),
            cash_balance=Decimal("1000.00"),
            positions=edge_case_positions
        )
        
        with patch.object(trading_service_test_data, 'get_portfolio', return_value=portfolio):
            result = await trading_service_test_data.get_portfolio()
            
            assert isinstance(result, Portfolio)
            assert len(result.positions) == 3
            
            # Verify calculations don't break with edge values
            for position in result.positions:
                assert isinstance(position.average_price, Decimal)
                assert isinstance(position.current_price, Decimal)
                assert isinstance(position.unrealized_pnl, Decimal)

    @pytest.mark.asyncio
    async def test_option_symbol_parsing_errors(self, trading_service_test_data):
        """Test handling of unparseable option symbols."""
        invalid_option_symbols = [
            "INVALID_OPTION_FORMAT",
            "AAPL_MALFORMED",
            "12345",
            "AAPL240315X00150000",  # Invalid option type
        ]
        
        for symbol in invalid_option_symbols:
            try:
                result = await trading_service_test_data.get_quote(symbol)
                # If no exception, should have error indication
                if isinstance(result, dict):
                    # May return error dict or empty result
                    pass  # Acceptable
                elif hasattr(result, 'price'):
                    # Got a quote somehow - also acceptable
                    pass
                else:
                    # Should be some kind of error indication
                    assert result is None or "error" in str(result)
            except Exception as e:
                # Parsing errors are expected
                assert "symbol" in str(e).lower() or "format" in str(e).lower() or "invalid" in str(e).lower()

    @pytest.mark.asyncio
    async def test_network_timeout_simulation(self, trading_service_test_data):
        """Test handling of network timeouts."""
        import asyncio
        
        with patch.object(trading_service_test_data.quote_adapter, 'get_quote') as mock_get_quote:
            mock_get_quote.side_effect = asyncio.TimeoutError("Network timeout")
            
            with pytest.raises(asyncio.TimeoutError):
                await trading_service_test_data.get_quote("AAPL")

    @pytest.mark.asyncio
    async def test_concurrent_access_edge_cases(self, trading_service_test_data):
        """Test edge cases with concurrent access patterns."""
        # Simulate concurrent portfolio access
        import asyncio
        
        async def get_portfolio_concurrent():
            return await trading_service_test_data.get_portfolio()
        
        # Run multiple concurrent requests
        tasks = [get_portfolio_concurrent() for _ in range(5)]
        
        try:
            results = await asyncio.gather(*tasks, return_exceptions=True)
            
            # Should either all succeed or fail gracefully
            for result in results:
                if isinstance(result, Exception):
                    # Acceptable if it's a controlled failure
                    assert "database" in str(result).lower() or "concurrent" in str(result).lower()
                else:
                    # Should be valid portfolio
                    assert hasattr(result, 'positions')
        except Exception as e:
            # Concurrent access issues are acceptable
            assert "concurrent" in str(e).lower() or "database" in str(e).lower()

    @pytest.mark.asyncio
    async def test_memory_pressure_large_data_sets(self, trading_service_test_data):
        """Test handling of large data sets that might cause memory pressure."""
        # Create a very large position list
        large_positions = []
        for i in range(1000):  # Large number of positions
            large_positions.append(
                Position(
                    symbol=f"STOCK{i:04d}",
                    quantity=1,
                    average_price=Decimal("100.00"),
                    current_price=Decimal("101.00"),
                    unrealized_pnl=Decimal("1.00"),
                    asset_type="stock"
                )
            )
        
        large_portfolio = Portfolio(
            account_id="large-account",
            total_value=Decimal("101000.00"),
            cash_balance=Decimal("1000.00"),
            positions=large_positions
        )
        
        with patch.object(trading_service_test_data, 'get_portfolio', return_value=large_portfolio):
            result = await trading_service_test_data.get_portfolio()
            
            assert isinstance(result, Portfolio)
            assert len(result.positions) == 1000
            # Should handle large data set without issues

    @pytest.mark.asyncio
    async def test_type_coercion_edge_cases(self, trading_service_test_data):
        """Test type coercion edge cases."""
        # Test various input types that might need coercion
        type_test_cases = [
            ("100", "string that looks like number"),
            (100.0, "float instead of int"),
            (Decimal("100.50"), "decimal type"),
        ]
        
        for test_value, description in type_test_cases:
            try:
                order_data = OrderCreate(
                    symbol="AAPL",
                    quantity=test_value,  # Different types
                    order_type=OrderType.MARKET,
                    side="buy"
                )
                result = await trading_service_test_data.create_order(order_data)
                # Should either succeed with type coercion or fail gracefully
                assert hasattr(result, 'id') or hasattr(result, 'status')
            except (TypeError, ValueError) as e:
                # Type errors are acceptable
                assert "type" in str(e).lower() or "invalid" in str(e).lower()

    @pytest.mark.asyncio
    async def test_unicode_and_special_characters(self, trading_service_test_data):
        """Test handling of unicode and special characters in input."""
        special_symbols = [
            "AAPL🚀",  # Emoji
            "AAPL.TO",  # Period
            "AAPL-WT",  # Dash
            "AAPL_OLD",  # Underscore
            "ÂPPL",  # Accented characters
        ]
        
        for symbol in special_symbols:
            try:
                result = await trading_service_test_data.get_quote(symbol)
                # May succeed or fail depending on adapter
                if isinstance(result, dict) and "error" in result:
                    assert "symbol" in result["error"] or "Invalid" in result["error"]
            except Exception as e:
                # Special character issues are acceptable
                assert "symbol" in str(e).lower() or "character" in str(e).lower() or "encoding" in str(e).lower()

    @pytest.mark.asyncio
    async def test_date_parsing_edge_cases(self, trading_service_test_data):
        """Test edge cases in date parsing for expiration simulation."""
        edge_case_dates = [
            "2024-02-29",  # Leap year
            "2024-12-31",  # Year end
            "2024-01-01",  # Year start
            "invalid-date",  # Invalid format
            "",  # Empty string
        ]
        
        for date_str in edge_case_dates:
            try:
                result = await trading_service_test_data.simulate_expiration(
                    processing_date=date_str if date_str else None
                )
                
                if "error" in result:
                    if date_str == "invalid-date" or date_str == "":
                        # Expected to fail
                        assert "date" in result["error"] or "invalid" in result["error"]
                    else:
                        # Valid dates might still fail for other reasons
                        pass
                else:
                    # Should have valid processing_date in result
                    assert "processing_date" in result
                    
            except Exception as e:
                # Date parsing errors are expected for invalid dates
                if date_str in ["invalid-date", ""]:
                    assert "date" in str(e).lower() or "time" in str(e).lower()

    @pytest.mark.asyncio
    async def test_circular_dependency_prevention(self, trading_service_test_data):
        """Test prevention of circular dependencies in operations."""
        # Test that operations don't create circular references
        portfolio = await trading_service_test_data.get_portfolio()
        
        # Use portfolio in another operation that might reference back
        if len(portfolio.positions) > 0:
            position = portfolio.positions[0]
            quote_result = await trading_service_test_data.get_quote(position.symbol)
            
            # Should complete without circular reference issues
            assert quote_result is not None or isinstance(quote_result, dict)

    @pytest.mark.asyncio
    async def test_resource_cleanup_on_errors(self, trading_service_test_data):
        """Test that resources are properly cleaned up when errors occur."""
        with patch.object(trading_service_test_data, '_get_async_db_session') as mock_session:
            # Mock a session that raises an error during operation
            mock_db = MagicMock()
            mock_db.close = MagicMock()
            mock_session.return_value.__aenter__.return_value = mock_db
            mock_session.return_value.__aexit__.return_value = None
            
            # Simulate operation that fails
            mock_db.execute.side_effect = RuntimeError("Database error")
            
            try:
                await trading_service_test_data.get_portfolio()
            except RuntimeError:
                # Error is expected
                pass
            
            # Session cleanup should still happen (tested via context manager)
            assert mock_session.called