"""
Comprehensive tests for TradingService account creation and initialization functions.

This module focuses specifically on testing the core account creation logic:
- _ensure_account_exists() function
- _get_account() function
- __init__() method
- Default balance assignment ($10,000)
- Initial position setup (AAPL, GOOGL seed data)
- Edge cases and error handling
"""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest
import pytest_asyncio
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.adapters.synthetic_data import DevDataQuoteAdapter
from app.models.database.trading import Account as DBAccount
from app.models.database.trading import Position as DBPosition
from app.services.trading_service import TradingService

pytestmark = pytest.mark.journey_account_management


@pytest.mark.journey_account_management
@pytest.mark.database
class TestTradingServiceAccountCreation:
    """Test suite for TradingService account creation and initialization."""

    @pytest_asyncio.fixture
    async def clean_db_session(self, db_session: AsyncSession) -> AsyncSession:
        """Provide a clean database session for each test."""
        # Ensure database is clean before each test
        from sqlalchemy import delete

        await db_session.execute(delete(DBPosition))
        await db_session.execute(delete(DBAccount))
        await db_session.commit()
        return db_session

    @pytest_asyncio.fixture
    async def mock_quote_adapter(self) -> MagicMock:
        """Create a mock quote adapter for testing."""
        adapter = MagicMock()
        adapter.get_quote = AsyncMock()
        adapter.get_available_symbols = MagicMock(
            return_value=["AAPL", "GOOGL", "MSFT"]
        )
        adapter.is_market_open = AsyncMock(return_value=True)
        return adapter

    @pytest_asyncio.fixture
    async def trading_service_factory(
        self, clean_db_session: AsyncSession, mock_quote_adapter: MagicMock
    ):
        """Factory to create TradingService instances for testing."""

        def _create_service(account_owner: str = "test_user", quote_adapter=None):
            if quote_adapter is None:
                quote_adapter = mock_quote_adapter

            # Inject the database session into the service
            service = TradingService(
                quote_adapter=quote_adapter,
                account_owner=account_owner,
                db_session=clean_db_session,
            )

            return service

        return _create_service

    # ========================================================================
    # Tests for _ensure_account_exists() function
    # ========================================================================

    @pytest.mark.asyncio
    async def test_ensure_account_exists_new_account_creation(
        self, clean_db_session: AsyncSession, trading_service_factory
    ):
        """Test _ensure_account_exists() creates new account with correct defaults."""
        # Arrange
        account_owner = "new_test_user"
        service = trading_service_factory(account_owner=account_owner)

        # Verify account doesn't exist initially
        stmt = select(DBAccount).where(DBAccount.owner == account_owner)
        result = await clean_db_session.execute(stmt)
        assert result.scalar_one_or_none() is None

        # Act
        await service._ensure_account_exists()

        # Assert - Account was created
        stmt = select(DBAccount).where(DBAccount.owner == account_owner)
        result = await clean_db_session.execute(stmt)
        account = result.scalar_one_or_none()

        assert account is not None
        assert account.owner == account_owner
        assert account.cash_balance == 10000.0  # Default balance
        assert account.created_at is not None
        # Note: updated_at column may not exist in current database schema

    @pytest.mark.asyncio
    async def test_ensure_account_exists_with_initial_positions(
        self, clean_db_session: AsyncSession, trading_service_factory
    ):
        """Test _ensure_account_exists() creates initial AAPL and GOOGL positions."""
        # Arrange
        account_owner = "new_position_user"
        service = trading_service_factory(account_owner=account_owner)

        # Act
        await service._ensure_account_exists()

        # Assert - Initial positions were created
        stmt = select(DBAccount).where(DBAccount.owner == account_owner)
        result = await clean_db_session.execute(stmt)
        account = result.scalar_one()

        # Check AAPL position
        aapl_stmt = select(DBPosition).where(
            DBPosition.account_id == account.id, DBPosition.symbol == "AAPL"
        )
        aapl_result = await clean_db_session.execute(aapl_stmt)
        aapl_position = aapl_result.scalar_one_or_none()

        assert aapl_position is not None
        assert aapl_position.symbol == "AAPL"
        assert aapl_position.quantity == 10
        assert aapl_position.avg_price == 145.00

        # Check GOOGL position
        googl_stmt = select(DBPosition).where(
            DBPosition.account_id == account.id, DBPosition.symbol == "GOOGL"
        )
        googl_result = await clean_db_session.execute(googl_stmt)
        googl_position = googl_result.scalar_one_or_none()

        assert googl_position is not None
        assert googl_position.symbol == "GOOGL"
        assert googl_position.quantity == 2
        assert googl_position.avg_price == 2850.00

    @pytest.mark.asyncio
    async def test_ensure_account_exists_existing_account_no_duplicate(
        self, clean_db_session: AsyncSession, trading_service_factory
    ):
        """Test _ensure_account_exists() doesn't create duplicate accounts."""
        # Arrange
        account_owner = "existing_user"
        service = trading_service_factory(account_owner=account_owner)

        # Create initial account
        await service._ensure_account_exists()

        # Get initial account data
        stmt = select(DBAccount).where(DBAccount.owner == account_owner)
        result = await clean_db_session.execute(stmt)
        initial_account = result.scalar_one()
        initial_id = initial_account.id
        initial_created_at = initial_account.created_at

        # Act - Call again
        await service._ensure_account_exists()

        # Assert - No duplicate account was created
        stmt = select(DBAccount).where(DBAccount.owner == account_owner)
        result = await clean_db_session.execute(stmt)
        accounts = result.scalars().all()

        assert len(accounts) == 1
        assert accounts[0].id == initial_id
        assert accounts[0].created_at == initial_created_at

    @pytest.mark.asyncio
    async def test_ensure_account_exists_multiple_different_owners(
        self, clean_db_session: AsyncSession, trading_service_factory
    ):
        """Test _ensure_account_exists() handles multiple different account owners."""
        # Arrange
        owners = ["user1", "user2", "user3"]
        services = [trading_service_factory(account_owner=owner) for owner in owners]

        # Act
        for service in services:
            await service._ensure_account_exists()

        # Assert - Each owner has their own account
        for owner in owners:
            stmt = select(DBAccount).where(DBAccount.owner == owner)
            result = await clean_db_session.execute(stmt)
            account = result.scalar_one_or_none()

            assert account is not None
            assert account.owner == owner
            assert account.cash_balance == 10000.0

        # Verify total account count
        all_accounts_stmt = select(DBAccount)
        all_result = await clean_db_session.execute(all_accounts_stmt)
        all_accounts = all_result.scalars().all()
        assert len(all_accounts) == 3

    # ========================================================================
    # Tests for _get_account() function
    # ========================================================================

    @pytest.mark.asyncio
    async def test_get_account_creates_new_account_when_none_exists(
        self, clean_db_session: AsyncSession, trading_service_factory
    ):
        """Test _get_account() creates account if none exists."""
        # Arrange
        account_owner = "new_account_user"
        service = trading_service_factory(account_owner=account_owner)

        # Verify no account exists
        stmt = select(DBAccount).where(DBAccount.owner == account_owner)
        result = await clean_db_session.execute(stmt)
        assert result.scalar_one_or_none() is None

        # Act
        account = await service._get_account()

        # Assert
        assert account is not None
        assert account.owner == account_owner
        assert account.cash_balance == 10000.0

    @pytest.mark.asyncio
    async def test_get_account_returns_existing_account(
        self, clean_db_session: AsyncSession, trading_service_factory
    ):
        """Test _get_account() returns existing account without modification."""
        # Arrange
        account_owner = "existing_account_user"
        service = trading_service_factory(account_owner=account_owner)

        # Create account first
        await service._ensure_account_exists()

        # Modify the balance to test we get the same account
        stmt = select(DBAccount).where(DBAccount.owner == account_owner)
        result = await clean_db_session.execute(stmt)
        existing_account = result.scalar_one()
        original_balance = 15000.0
        existing_account.cash_balance = original_balance
        await clean_db_session.commit()

        # Act
        retrieved_account = await service._get_account()

        # Assert
        assert retrieved_account.id == existing_account.id
        assert retrieved_account.owner == account_owner
        assert retrieved_account.cash_balance == original_balance

    @pytest.mark.asyncio
    async def test_get_account_with_different_account_owners(
        self, clean_db_session: AsyncSession, trading_service_factory
    ):
        """Test _get_account() works correctly with different account owners."""
        # Arrange
        service1 = trading_service_factory(account_owner="user1")
        service2 = trading_service_factory(account_owner="user2")

        # Act
        account1 = await service1._get_account()
        account2 = await service2._get_account()

        # Assert
        assert account1.owner == "user1"
        assert account2.owner == "user2"
        assert account1.id != account2.id
        assert account1.cash_balance == 10000.0
        assert account2.cash_balance == 10000.0

    # ========================================================================
    # Tests for __init__() method
    # ========================================================================

    def test_init_with_no_adapter_uses_factory_fallback(self):
        """Test __init__() uses adapter factory when no adapter provided."""
        # Act
        service = TradingService(account_owner="test_user")

        # Assert
        assert service.quote_adapter is not None
        assert service.account_owner == "test_user"
        assert service.order_execution is not None
        assert service.account_validation is not None
        assert service.strategy_recognition is not None

    def test_init_with_custom_adapter(self, mock_quote_adapter):
        """Test __init__() uses provided custom adapter."""
        # Act
        service = TradingService(
            quote_adapter=mock_quote_adapter, account_owner="custom_user"
        )

        # Assert
        assert service.quote_adapter is mock_quote_adapter
        assert service.account_owner == "custom_user"

    def test_init_with_dev_data_adapter_fallback(self):
        """Test __init__() falls back to DevDataQuoteAdapter when factory fails."""
        with patch("app.adapters.config.get_adapter_factory") as mock_factory:
            # Mock factory to return None for all adapters
            mock_adapter_factory = MagicMock()
            mock_adapter_factory.create_adapter.return_value = None
            mock_factory.return_value = mock_adapter_factory

            # Act
            service = TradingService(account_owner="fallback_user")

            # Assert
            assert isinstance(service.quote_adapter, DevDataQuoteAdapter)
            assert service.account_owner == "fallback_user"

    def test_init_default_account_owner(self):
        """Test __init__() uses 'default' as default account owner."""
        # Act
        service = TradingService()

        # Assert
        assert service.account_owner == "default"

    def test_init_components_initialization(self, mock_quote_adapter):
        """Test __init__() properly initializes all service components."""
        # Act
        service = TradingService(
            quote_adapter=mock_quote_adapter, account_owner="component_test_user"
        )

        # Assert - All required components are initialized
        assert service.quote_adapter is not None
        assert service.order_execution is not None
        assert service.account_validation is not None
        assert service.strategy_recognition is not None
        assert service.account_converter is not None
        assert service.order_converter is not None
        assert service.position_converter is not None

    # ========================================================================
    # Tests for default balance validation
    # ========================================================================

    @pytest.mark.asyncio
    async def test_default_balance_assignment(
        self, clean_db_session: AsyncSession, trading_service_factory
    ):
        """Test account creation assigns exactly $10,000 default balance."""
        # Arrange
        service = trading_service_factory(account_owner="balance_test_user")

        # Act
        await service._ensure_account_exists()

        # Assert
        account = await service._get_account()
        assert account.cash_balance == 10000.0
        assert isinstance(account.cash_balance, float)

    @pytest.mark.asyncio
    async def test_get_account_balance_method(
        self, clean_db_session: AsyncSession, trading_service_factory
    ):
        """Test get_account_balance() returns correct default balance."""
        # Arrange
        service = trading_service_factory(account_owner="balance_method_user")

        # Act
        balance = await service.get_account_balance()

        # Assert
        assert balance == 10000.0
        assert isinstance(balance, float)

    # ========================================================================
    # Tests for initial position setup validation
    # ========================================================================

    @pytest.mark.asyncio
    async def test_initial_positions_exact_values(
        self, clean_db_session: AsyncSession, trading_service_factory
    ):
        """Test initial positions have exact expected values."""
        # Arrange
        service = trading_service_factory(account_owner="position_values_user")

        # Act
        await service._ensure_account_exists()
        account = await service._get_account()

        # Assert AAPL position
        aapl_stmt = select(DBPosition).where(
            DBPosition.account_id == account.id, DBPosition.symbol == "AAPL"
        )
        aapl_result = await clean_db_session.execute(aapl_stmt)
        aapl_position = aapl_result.scalar_one()

        assert aapl_position.symbol == "AAPL"
        assert aapl_position.quantity == 10
        assert aapl_position.avg_price == 145.00
        assert aapl_position.account_id == account.id

        # Assert GOOGL position
        googl_stmt = select(DBPosition).where(
            DBPosition.account_id == account.id, DBPosition.symbol == "GOOGL"
        )
        googl_result = await clean_db_session.execute(googl_stmt)
        googl_position = googl_result.scalar_one()

        assert googl_position.symbol == "GOOGL"
        assert googl_position.quantity == 2
        assert googl_position.avg_price == 2850.00
        assert googl_position.account_id == account.id

    @pytest.mark.asyncio
    async def test_initial_positions_total_count(
        self, clean_db_session: AsyncSession, trading_service_factory
    ):
        """Test exactly 2 initial positions are created."""
        # Arrange
        service = trading_service_factory(account_owner="position_count_user")

        # Act
        await service._ensure_account_exists()
        account = await service._get_account()

        # Assert
        positions_stmt = select(DBPosition).where(DBPosition.account_id == account.id)
        positions_result = await clean_db_session.execute(positions_stmt)
        positions = positions_result.scalars().all()

        assert len(positions) == 2
        symbols = [pos.symbol for pos in positions]
        assert "AAPL" in symbols
        assert "GOOGL" in symbols

    @pytest.mark.asyncio
    async def test_initial_positions_not_duplicated_on_multiple_calls(
        self, clean_db_session: AsyncSession, trading_service_factory
    ):
        """Test initial positions are not duplicated on multiple _ensure_account_exists() calls."""
        # Arrange
        service = trading_service_factory(account_owner="no_duplicate_positions_user")

        # Act
        await service._ensure_account_exists()
        await service._ensure_account_exists()  # Call again
        await service._ensure_account_exists()  # And again

        # Assert
        account = await service._get_account()
        positions_stmt = select(DBPosition).where(DBPosition.account_id == account.id)
        positions_result = await clean_db_session.execute(positions_stmt)
        positions = positions_result.scalars().all()

        # Should still only have 2 positions total
        assert len(positions) == 2

        # Verify exact counts for each symbol
        aapl_positions = [pos for pos in positions if pos.symbol == "AAPL"]
        googl_positions = [pos for pos in positions if pos.symbol == "GOOGL"]

        assert len(aapl_positions) == 1
        assert len(googl_positions) == 1

    # ========================================================================
    # Tests for edge cases and error handling
    # ========================================================================

    def test_init_with_empty_account_owner(self):
        """Test __init__() raises InputValidationError for empty account owner string."""
        from app.core.exceptions import InputValidationError

        # Act & Assert
        with pytest.raises(
            InputValidationError,
            match="account_owner cannot be empty or whitespace-only",
        ):
            TradingService(account_owner="")

    def test_init_with_whitespace_only_account_owner(self):
        """Test __init__() raises InputValidationError for whitespace-only account owner."""
        from app.core.exceptions import InputValidationError

        # Act & Assert
        with pytest.raises(
            InputValidationError,
            match="account_owner cannot be empty or whitespace-only",
        ):
            TradingService(account_owner="   ")

    def test_init_with_none_account_owner(self):
        """Test __init__() handles None account owner."""
        # Act & Assert
        with pytest.raises(TypeError, match="account_owner cannot be None"):
            TradingService(account_owner=None)

    def test_init_with_non_string_account_owner(self):
        """Test __init__() raises TypeError for non-string account owner."""
        # Act & Assert
        with pytest.raises(TypeError, match="account_owner must be a string"):
            TradingService(account_owner=123)

    def test_init_with_very_long_account_owner(self):
        """Test __init__() raises InputValidationError for account owner longer than 255 chars."""
        from app.core.exceptions import InputValidationError

        long_owner = "a" * 256  # 256 characters (over the limit)

        # Act & Assert
        with pytest.raises(
            InputValidationError, match="account_owner must be 255 characters or less"
        ):
            TradingService(account_owner=long_owner)

    def test_init_with_account_owner_exactly_255_chars(self):
        """Test __init__() accepts account owner with exactly 255 characters."""
        # Arrange
        owner_255_chars = "a" * 255  # Exactly 255 characters

        # Act
        service = TradingService(account_owner=owner_255_chars)

        # Assert
        assert service.account_owner == owner_255_chars

    def test_init_strips_whitespace_from_account_owner(self):
        """Test __init__() strips leading and trailing whitespace from account owner."""
        # Act
        service = TradingService(account_owner="  test_user  ")

        # Assert
        assert service.account_owner == "test_user"

    def test_init_with_invalid_db_session(self):
        """Test __init__() raises TypeError for invalid db_session."""
        # Act & Assert
        with pytest.raises(
            TypeError, match="db_session must be a valid AsyncSession instance or None"
        ):
            TradingService(account_owner="test", db_session="invalid_session")

    @pytest.mark.asyncio
    async def test_ensure_account_exists_with_special_characters_in_owner(
        self, clean_db_session: AsyncSession, trading_service_factory
    ):
        """Test _ensure_account_exists() handles special characters in account owner."""
        # Arrange
        special_owners = [
            "user@example.com",
            "user-with-dashes",
            "user_with_underscores",
            "user with spaces",
            "用户",  # Unicode characters
            "user123",
        ]

        # Act & Assert
        for owner in special_owners:
            service = trading_service_factory(account_owner=owner)
            await service._ensure_account_exists()

            account = await service._get_account()
            assert account.owner == owner
            assert account.cash_balance == 10000.0

    @pytest.mark.asyncio
    async def test_ensure_account_exists_with_long_owner_name_within_limit(
        self, clean_db_session: AsyncSession, trading_service_factory
    ):
        """Test _ensure_account_exists() handles long account owner names within limit."""
        # Arrange
        long_owner = "a" * 200  # Long string but within 255 char limit
        service = trading_service_factory(account_owner=long_owner)

        # Act
        await service._ensure_account_exists()

        # Assert
        account = await service._get_account()
        assert account.owner == long_owner
        assert account.cash_balance == 10000.0

    @pytest.mark.asyncio
    async def test_get_account_database_session_handling(
        self, clean_db_session: AsyncSession, trading_service_factory
    ):
        """Test _get_account() properly handles database operations."""
        # Arrange
        service = trading_service_factory(account_owner="session_test_user")

        # Act
        account = await service._get_account()

        # Assert
        assert account is not None
        assert account.owner == "session_test_user"
        assert account.cash_balance == 10000.0

    # ========================================================================
    # Tests for integration with different adapter types
    # ========================================================================

    def test_init_with_synthetic_data_adapter(self):
        """Test __init__() with DevDataQuoteAdapter."""
        # Arrange
        adapter = DevDataQuoteAdapter()

        # Act
        service = TradingService(
            quote_adapter=adapter, account_owner="test_adapter_user"
        )

        # Assert
        assert service.quote_adapter is adapter
        assert isinstance(service.quote_adapter, DevDataQuoteAdapter)

    @pytest.mark.asyncio
    async def test_account_creation_with_different_adapters(
        self, clean_db_session: AsyncSession
    ):
        """Test account creation works with different adapter types."""
        # Arrange
        adapters = [
            DevDataQuoteAdapter(),
            MagicMock(),  # Mock adapter
        ]

        # Act & Assert
        for i, adapter in enumerate(adapters):
            account_owner = f"adapter_test_user_{i}"
            service = TradingService(
                quote_adapter=adapter,
                account_owner=account_owner,
                db_session=clean_db_session,  # Properly inject the session
            )

            # Test account creation
            await service._ensure_account_exists()
            account = await service._get_account()

            assert account.owner == account_owner
            assert account.cash_balance == 10000.0

    # ========================================================================
    # Tests for performance validation
    # ========================================================================

    @pytest.mark.asyncio
    async def test_account_creation_performance(
        self, clean_db_session: AsyncSession, trading_service_factory
    ):
        """Test account creation completes within reasonable time."""
        import time

        # Arrange
        service = trading_service_factory(account_owner="performance_test_user")

        # Act
        start_time = time.time()
        await service._ensure_account_exists()
        end_time = time.time()

        # Assert
        execution_time = end_time - start_time
        assert execution_time < 2.0  # Should complete within 2 seconds

        # Verify account was created correctly
        account = await service._get_account()
        assert account.owner == "performance_test_user"

    @pytest.mark.asyncio
    async def test_multiple_account_operations_performance(
        self, clean_db_session: AsyncSession, trading_service_factory
    ):
        """Test multiple account operations complete within reasonable time."""
        import time

        # Arrange
        service = trading_service_factory(account_owner="multi_ops_user")

        # Act
        start_time = time.time()

        # Multiple operations
        await service._ensure_account_exists()
        await service._get_account()
        await service.get_account_balance()
        await service._get_account()  # Multiple calls
        await service.get_account_balance()

        end_time = time.time()

        # Assert
        execution_time = end_time - start_time
        assert execution_time < 3.0  # Should complete within 3 seconds

    # ========================================================================
    # Tests for database connection error handling
    # ========================================================================

    @pytest.mark.asyncio
    async def test_ensure_account_exists_database_error_handling(
        self, trading_service_factory
    ):
        """Test _ensure_account_exists() handles database connection errors."""
        # Arrange
        service = trading_service_factory(account_owner="db_error_user")

        # Mock database session to raise an error
        async def mock_failing_db_session():
            raise Exception("Database connection failed")

        service._get_async_db_session = mock_failing_db_session

        # Act & Assert
        with pytest.raises(Exception, match="Database connection failed"):
            await service._ensure_account_exists()

    @pytest.mark.asyncio
    async def test_get_account_database_error_handling(self, trading_service_factory):
        """Test _get_account() handles database connection errors."""
        # Arrange
        service = trading_service_factory(account_owner="db_error_get_user")

        # Mock database session to raise an error
        async def mock_failing_db_session():
            raise Exception("Database connection failed")

        service._get_async_db_session = mock_failing_db_session

        # Act & Assert
        with pytest.raises(Exception, match="Database connection failed"):
            await service._get_account()

    # ========================================================================
    # Integration tests
    # ========================================================================

    @pytest.mark.asyncio
    async def test_full_account_initialization_workflow(
        self, clean_db_session: AsyncSession, trading_service_factory
    ):
        """Test complete account initialization workflow from start to finish."""
        # Arrange
        account_owner = "full_workflow_user"
        service = trading_service_factory(account_owner=account_owner)

        # Act - Complete workflow
        # 1. Initialize service (already done by factory)
        # 2. Ensure account exists
        await service._ensure_account_exists()
        # 3. Get account
        account = await service._get_account()
        # 4. Get balance
        balance = await service.get_account_balance()

        # Assert - All components work together
        assert account.owner == account_owner
        assert account.cash_balance == 10000.0
        assert balance == 10000.0

        # Verify initial positions exist
        positions_stmt = select(DBPosition).where(DBPosition.account_id == account.id)
        positions_result = await clean_db_session.execute(positions_stmt)
        positions = positions_result.scalars().all()

        assert len(positions) == 2
        symbols = [pos.symbol for pos in positions]
        assert "AAPL" in symbols
        assert "GOOGL" in symbols

    @pytest.mark.asyncio
    async def test_concurrent_account_creation_safety(
        self, clean_db_session: AsyncSession, trading_service_factory
    ):
        """Test account creation is safe under concurrent access."""
        # Arrange
        account_owner = "concurrent_test_user"

        # Create first service and account
        service1 = trading_service_factory(account_owner=account_owner)
        await service1._ensure_account_exists()

        # Create a second service that tries to create the same account
        service2 = trading_service_factory(account_owner=account_owner)

        # Act - Second service tries to ensure account exists (should not create duplicate)
        await (
            service2._ensure_account_exists()
        )  # Should gracefully handle existing account

        # Assert - Only one account was created
        stmt = select(DBAccount).where(DBAccount.owner == account_owner)
        result = await clean_db_session.execute(stmt)
        accounts = result.scalars().all()

        assert len(accounts) == 1
        assert accounts[0].owner == account_owner
        assert accounts[0].cash_balance == 10000.0

        # Verify positions are not duplicated
        positions_stmt = select(DBPosition).where(
            DBPosition.account_id == accounts[0].id
        )
        positions_result = await clean_db_session.execute(positions_stmt)
        positions = positions_result.scalars().all()

        assert len(positions) == 2  # Should still only have 2 positions

    @pytest.mark.asyncio
    async def test_duplicate_account_creation_handling(
        self, clean_db_session: AsyncSession, trading_service_factory
    ):
        """Test proper handling of duplicate account creation attempts."""
        # Arrange
        account_owner = "duplicate_test_user"

        # Create first account manually in database
        account = DBAccount(
            owner=account_owner,
            cash_balance=5000.0,  # Different balance to verify we don't overwrite
        )
        clean_db_session.add(account)
        await clean_db_session.commit()

        # Create service that will try to ensure the same account exists
        service = trading_service_factory(account_owner=account_owner)

        # Act - Service should handle the existing account gracefully
        await service._ensure_account_exists()

        # Assert - Original account should be unchanged
        stmt = select(DBAccount).where(DBAccount.owner == account_owner)
        result = await clean_db_session.execute(stmt)
        accounts = result.scalars().all()

        assert len(accounts) == 1
        assert accounts[0].owner == account_owner
        assert accounts[0].cash_balance == 5000.0  # Original balance preserved
        assert accounts[0].id == account.id  # Same account ID
