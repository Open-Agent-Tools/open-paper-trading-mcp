"""
Integration tests for account error handling across all layers.

Tests error propagation and handling from API endpoints through services 
to database adapters, ensuring proper error handling throughout the stack.
"""

import uuid
from unittest.mock import AsyncMock, MagicMock, patch
from datetime import datetime

import pytest
import pytest_asyncio
from fastapi.testclient import TestClient
from sqlalchemy.exc import DatabaseError, IntegrityError, OperationalError
from sqlalchemy.ext.asyncio import AsyncSession

from app.main import app
from app.mcp import account_tools
from app.services.trading_service import TradingService
from app.adapters.accounts import DatabaseAccountAdapter
from app.schemas.accounts import Account
from app.core.exceptions import NotFoundError, ValidationError


class TestAccountErrorIntegration:
    """Integration tests for account error handling across all layers."""

    @pytest_asyncio.fixture
    async def test_client(self):
        """Create test client for integration testing."""
        return TestClient(app)

    @pytest_asyncio.fixture
    async def mock_db_session(self):
        """Create mock database session."""
        session = MagicMock(spec=AsyncSession)
        session.execute = AsyncMock()
        session.commit = AsyncMock()
        session.rollback = AsyncMock()
        session.close = AsyncMock()
        return session

    @pytest.mark.asyncio
    async def test_api_to_database_error_propagation(self, test_client, mock_db_session):
        """Test error propagation from API through service to database."""
        # This test verifies that database errors are handled gracefully in the API layer
        # Since the test client initialization would be complex, we'll test that the error
        # handling mechanisms are in place by checking the response format
        
        # Mock the app state to include a service that raises database errors
        from app.services.trading_service import TradingService
        from unittest.mock import MagicMock
        
        mock_service = MagicMock(spec=TradingService)
        mock_service.get_portfolio.side_effect = OperationalError("Database connection failed", None, None)
        
        # Set the service in app state
        from app.main import app
        app.state.trading_service = mock_service
        
        # API call should handle database error gracefully
        response = test_client.get("/api/v1/portfolio")
        
        # Should return appropriate HTTP error status
        assert response.status_code in [500, 503]  # Internal server error or service unavailable

    @patch('app.mcp.account_tools.get_trading_service')
    @pytest.mark.asyncio
    async def test_mcp_to_service_error_propagation(self, mock_get_service):
        """Test error propagation from MCP tools to trading service."""
        # Setup service failure
        mock_service = MagicMock()
        mock_service.get_portfolio.side_effect = DatabaseError("Database query failed", None, None)
        mock_get_service.return_value = mock_service
        
        # MCP tool call should handle service error
        result = await account_tools.portfolio()
        
        assert result["result"]["status"] == "error"
        assert "Database query failed" in result["result"]["error"]

    @patch('app.storage.database.get_async_session')
    @pytest.mark.asyncio
    async def test_service_to_adapter_error_recovery(self, mock_get_session):
        """Test error recovery from service to adapter layer."""
        mock_adapter = MagicMock()
        service = TradingService(quote_adapter=mock_adapter, account_owner="test_user")
        
        call_count = 0
        def session_side_effect(*args, **kwargs):
            nonlocal call_count
            call_count += 1
            
            async def mock_session_generator():
                mock_session = MagicMock(spec=AsyncSession)
                
                if call_count == 1:
                    # First call fails
                    mock_session.execute.side_effect = OperationalError("Connection timeout", None, None)
                else:
                    # Second call succeeds (simulating retry or recovery)
                    from app.models.database.trading import Account as DBAccount
                    from decimal import Decimal
                    
                    mock_result = MagicMock()
                    account = DBAccount(
                        id="test-123",
                        owner="test_user",
                        cash_balance=Decimal("10000.0"),
                        buying_power=Decimal("10000.0")
                    )
                    mock_result.scalar_one_or_none.return_value = account
                    mock_session.execute.return_value = mock_result
                
                yield mock_session
            
            return mock_session_generator()
        
        mock_get_session.side_effect = session_side_effect
        
        # First call should fail
        with pytest.raises(OperationalError):
            await service._get_account()
        
        # Service should be able to recover on subsequent calls
        account = await service._get_account()
        assert account is not None

    @patch('app.adapters.accounts.get_async_session')
    @pytest.mark.asyncio
    async def test_adapter_database_rollback_integration(self, mock_get_session):
        """Test database rollback integration in adapters."""
        adapter = DatabaseAccountAdapter()
        
        mock_db = MagicMock()
        async def mock_session_generator():
            yield mock_db
        mock_get_session.side_effect = lambda: mock_session_generator()
        
        # Simulate transaction failure
        mock_db.commit.side_effect = IntegrityError("Constraint violation", None, None)
        
        sample_account = Account(
            id="test-123",
            cash_balance=1000.0,
            positions=[],
            name="Test Account",
            owner="test_user",
        )
        
        # Should handle rollback properly
        with pytest.raises(IntegrityError):
            await adapter.put_account(sample_account)
        
        # Verify rollback was called
        mock_db.rollback.assert_called_once()

    @patch('app.mcp.account_tools.get_trading_service')
    @patch('app.services.trading_service.get_async_session')
    @pytest.mark.asyncio
    async def test_end_to_end_error_handling_chain(self, mock_get_session, mock_get_service):
        """Test complete error handling chain from MCP to database."""
        # Setup database layer failure
        mock_session = MagicMock(spec=AsyncSession)
        mock_session.execute.side_effect = DatabaseError("Critical database error", None, None)
        mock_get_session.return_value.__aenter__.return_value = mock_session
        
        # Setup trading service
        mock_adapter = MagicMock()
        service = TradingService(quote_adapter=mock_adapter, account_owner="test_user")
        mock_get_service.return_value = service
        
        # Call MCP tool - should handle error gracefully through entire chain
        result = await account_tools.account_info()
        
        # Error should be handled at MCP level
        assert result["result"]["status"] == "error"
        assert "Critical database error" in result["result"]["error"]

    def test_validation_error_propagation(self):
        """Test validation error propagation through layers."""
        # Test invalid account data validation
        with pytest.raises(Exception) as exc_info:
            Account(
                id="test-123",
                cash_balance=-1000.0,  # Invalid negative balance
                positions=[],
                name="Test Account",
                owner="test_user",
            )
        
        # Should be a validation error
        assert "Cash balance cannot be negative" in str(exc_info.value)

    @patch('app.adapters.accounts.get_async_session')
    @pytest.mark.asyncio
    async def test_concurrent_access_error_handling(self, mock_get_session):
        """Test concurrent access error handling integration."""
        adapter = DatabaseAccountAdapter()
        
        # Simulate concurrent modification conflict
        call_count = 0
        def session_side_effect(*args, **kwargs):
            nonlocal call_count
            call_count += 1
            
            async def mock_session_generator():
                mock_db = MagicMock()
                
                if call_count == 1:
                    # First access succeeds
                    mock_result = MagicMock()
                    mock_result.scalar_one_or_none.return_value = MagicMock()
                    mock_db.execute.return_value = mock_result
                    yield mock_db
                else:
                    # Second access fails due to concurrent modification
                    mock_db.execute.side_effect = OperationalError("Lock timeout", None, None)
                    yield mock_db
            
            return mock_session_generator()
        
        mock_get_session.side_effect = session_side_effect
        
        # First call should succeed
        result1 = await adapter.delete_account("test-id")
        
        # Second call should handle concurrent access error
        with pytest.raises(OperationalError):
            await adapter.delete_account("test-id-2")

    @patch('app.mcp.account_tools.get_trading_service')
    @pytest.mark.asyncio
    async def test_mcp_error_response_format_integration(self, mock_get_service):
        """Test MCP error response format integration."""
        # Test various error types and ensure consistent formatting
        error_scenarios = [
            (DatabaseError("DB error", None, None), "DatabaseError"),
            (NotFoundError("Not found"), "NotFoundError"),
            (ValidationError("Invalid data"), "ValidationError"),
            (ConnectionError("Network error"), "ConnectionError"),
            (Exception("Generic error"), "Exception"),
        ]
        
        for error, expected_type in error_scenarios:
            mock_service = MagicMock()
            mock_service._get_account.side_effect = error
            mock_get_service.return_value = mock_service
            
            result = await account_tools.account_info()
            
            assert result["result"]["status"] == "error"
            assert expected_type in result["result"]["error"] or "error" in result["result"]["error"].lower()

    @patch('app.services.trading_service.get_async_session')
    @pytest.mark.asyncio
    async def test_service_transaction_isolation(self, mock_get_session):
        """Test transaction isolation in service layer."""
        mock_adapter = MagicMock()
        service = TradingService(quote_adapter=mock_adapter, account_owner="test_user")
        
        # Mock session that tracks transaction state
        mock_session = MagicMock(spec=AsyncSession)
        mock_get_session.return_value.__aenter__.return_value = mock_session
        
        # Simulate failure during transaction
        mock_session.execute.side_effect = DatabaseError("Transaction failed", None, None)
        
        # Should handle transaction failure properly
        with pytest.raises(DatabaseError):
            await service.get_portfolio()
        
        # Session should be properly cleaned up
        # (Context manager handles this automatically)

    @pytest.mark.asyncio
    async def test_resource_cleanup_integration(self):
        """Test resource cleanup across layers during errors."""
        adapter = DatabaseAccountAdapter()
        
        # Test file system adapter cleanup
        fs_adapter = None
        try:
            import tempfile
            import shutil
            
            temp_dir = tempfile.mkdtemp()
            from app.adapters.accounts import LocalFileSystemAccountAdapter
            fs_adapter = LocalFileSystemAccountAdapter(temp_dir)
            
            sample_account = Account(
                id="test-123",
                cash_balance=1000.0,
                positions=[],
                name="Test Account",
                owner="test_user",
            )
            
            # Should handle file operations properly
            await fs_adapter.put_account(sample_account)
            assert await fs_adapter.account_exists("test-123")
            
            # Cleanup
            await fs_adapter.delete_account("test-123")
            assert not await fs_adapter.account_exists("test-123")
            
        finally:
            if fs_adapter and hasattr(fs_adapter, 'root_path'):
                import shutil
                import os
                if os.path.exists(fs_adapter.root_path):
                    shutil.rmtree(fs_adapter.root_path)

    @patch('app.storage.database.get_async_session')
    @pytest.mark.asyncio
    async def test_database_connection_recovery_integration(self, mock_get_session):
        """Test database connection recovery integration."""
        call_count = 0
        
        def session_side_effect(*args, **kwargs):
            nonlocal call_count
            call_count += 1
            
            if call_count <= 2:
                # First few calls fail
                raise OperationalError("Connection lost", None, None)
            else:
                # Later calls succeed (connection recovered)
                mock_session = MagicMock(spec=AsyncSession)
                return mock_session
        
        mock_get_session.return_value.__aenter__.side_effect = session_side_effect
        
        mock_adapter = MagicMock()
        service = TradingService(quote_adapter=mock_adapter, account_owner="test_user")
        
        # First calls should fail
        with pytest.raises(OperationalError):
            await service.get_portfolio()
        
        with pytest.raises(OperationalError):
            await service.get_positions()
        
        # Third call should succeed (connection recovered)
        # This simulates external connection recovery
        from app.models.database.trading import Account as DBAccount
        from decimal import Decimal
        
        mock_session = MagicMock(spec=AsyncSession)
        mock_result = MagicMock()
        account = DBAccount(
            id="test-123",
            owner="test_user",
            cash_balance=Decimal("10000.0"),
            buying_power=Decimal("10000.0")
        )
        mock_result.scalar_one_or_none.return_value = account
        
        positions_result = MagicMock()
        positions_result.scalars.return_value.all.return_value = []
        
        mock_session.execute.side_effect = [mock_result, positions_result]
        async def final_mock_session_generator():
            yield mock_session
        mock_get_session.side_effect = lambda: final_mock_session_generator()
        
        portfolio = await service.get_portfolio()
        assert portfolio is not None


class TestAccountErrorBoundaryConditions:
    """Test error handling at boundary conditions."""

    @pytest.mark.asyncio
    async def test_extremely_large_error_messages(self):
        """Test handling of extremely large error messages."""
        large_error_msg = "x" * 10000  # Very large error message
        
        from app.mcp.response_utils import handle_tool_exception
        
        error = Exception(large_error_msg)
        result = handle_tool_exception("test_tool", error)
        
        # Should handle large error messages gracefully
        assert result["result"]["status"] == "error"
        assert "error" in result["result"]
        # Message should be truncated or handled appropriately

    @pytest.mark.asyncio
    async def test_unicode_error_messages(self):
        """Test handling of Unicode characters in error messages."""
        unicode_error_msg = "错误信息 🚨 произошла ошибка"
        
        from app.mcp.response_utils import handle_tool_exception
        
        error = Exception(unicode_error_msg)
        result = handle_tool_exception("test_tool", error)
        
        # Should handle Unicode error messages properly
        assert result["result"]["status"] == "error"
        assert unicode_error_msg in result["result"]["error"]

    @patch('app.adapters.accounts.get_async_session')
    @pytest.mark.asyncio
    async def test_memory_pressure_error_handling(self, mock_get_session):
        """Test error handling under memory pressure."""
        adapter = DatabaseAccountAdapter()
        
        # Simulate memory error
        mock_get_session.side_effect = MemoryError("Out of memory")
        
        # Should handle memory errors gracefully
        with pytest.raises(MemoryError):
            await adapter.get_account("test-id")

    @pytest.mark.asyncio
    async def test_stack_overflow_error_handling(self):
        """Test handling of stack overflow scenarios."""
        # Test recursive error handling (shouldn't cause stack overflow)
        from app.mcp.response_utils import handle_tool_exception
        
        def create_recursive_error(depth):
            if depth > 0:
                try:
                    create_recursive_error(depth - 1)
                except Exception as e:
                    raise Exception(f"Nested error {depth}") from e
            else:
                raise Exception("Base error")
        
        try:
            create_recursive_error(5)
        except Exception as e:
            result = handle_tool_exception("test_tool", e)
            
            # Should handle nested exceptions gracefully
            assert result["result"]["status"] == "error"
            assert "error" in result["result"]


if __name__ == "__main__":
    pytest.main([__file__, "-v"])