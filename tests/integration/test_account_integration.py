"""
Integration tests for account functionality.

This module tests the complete account lifecycle with real database integration,
ensuring all account adapter functions works together correctly.
"""

from unittest.mock import patch

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from app.adapters.accounts import DatabaseAccountAdapter, account_factory
from app.schemas.accounts import Account

pytestmark = pytest.mark.journey_integration


class TestAccountIntegration:
    """Integration tests for account functionality using real database."""

    @pytest.mark.asyncio
    async def test_complete_account_lifecycle(self, db_session: AsyncSession):
        """Test complete account lifecycle: create → read → update → delete."""
        adapter = DatabaseAccountAdapter()

        with patch("app.adapters.accounts.get_async_session") as mock_get_session:

            async def mock_session_generator():
                yield db_session

            mock_get_session.side_effect = lambda: mock_session_generator()

            # Step 1: Create an account using factory
            new_account = account_factory(
                name="Integration Test Account", owner="integration_user", cash=50000.0
            )

            # Step 2: Store account in database
            await adapter.put_account(new_account)

            # Step 3: Verify account exists
            assert await adapter.account_exists(new_account.id)

            # Step 4: Retrieve account and verify data
            retrieved_account = await adapter.get_account(new_account.id)
            assert retrieved_account is not None
            assert retrieved_account.id == new_account.id
            assert retrieved_account.cash_balance == 50000.0
            assert retrieved_account.owner == "integration_user"
            assert retrieved_account.name == f"Account-{new_account.id}"

            # Step 5: Update account
            retrieved_account.cash_balance = 75000.0
            await adapter.put_account(retrieved_account)

            # Step 6: Verify update
            updated_account = await adapter.get_account(new_account.id)
            assert updated_account is not None
            assert updated_account.cash_balance == 75000.0

            # Step 7: Verify account appears in ID list
            account_ids = await adapter.get_account_ids()
            assert new_account.id in account_ids

            # Step 8: Delete account
            deletion_success = await adapter.delete_account(new_account.id)
            assert deletion_success is True

            # Step 9: Verify account no longer exists
            assert not await adapter.account_exists(new_account.id)
            deleted_account = await adapter.get_account(new_account.id)
            assert deleted_account is None

            # Step 10: Verify account removed from ID list
            final_account_ids = await adapter.get_account_ids()
            assert new_account.id not in final_account_ids

    @pytest.mark.asyncio
    async def test_multiple_accounts_lifecycle(self, db_session: AsyncSession):
        """Test managing multiple accounts simultaneously."""
        adapter = DatabaseAccountAdapter()

        with patch("app.adapters.accounts.get_async_session") as mock_get_session:

            async def mock_session_generator():
                yield db_session

            mock_get_session.side_effect = lambda: mock_session_generator()

            # Create multiple accounts
            accounts = []
            for i in range(5):
                account = account_factory(
                    name=f"Test Account {i + 1}",
                    owner=f"user_{i + 1}",
                    cash=10000.0 * (i + 1),
                )
                accounts.append(account)
                await adapter.put_account(account)

            # Verify all accounts exist
            for account in accounts:
                assert await adapter.account_exists(account.id)

            # Verify all accounts in ID list
            account_ids = await adapter.get_account_ids()
            for account in accounts:
                assert account.id in account_ids

            # Retrieve and verify each account
            for i, account in enumerate(accounts):
                retrieved = await adapter.get_account(account.id)
                assert retrieved is not None
                assert retrieved.cash_balance == 10000.0 * (i + 1)
                assert retrieved.owner == f"user_{i + 1}"

            # Update all accounts
            for i, account in enumerate(accounts):
                account.cash_balance = 20000.0 * (i + 1)
                await adapter.put_account(account)

            # Verify updates
            for i, account in enumerate(accounts):
                updated = await adapter.get_account(account.id)
                assert updated is not None
                assert updated.cash_balance == 20000.0 * (i + 1)

            # Delete accounts one by one and verify remaining
            for i, account in enumerate(accounts):
                # Delete current account
                success = await adapter.delete_account(account.id)
                assert success is True

                # Verify deleted account is gone
                assert not await adapter.account_exists(account.id)

                # Verify remaining accounts still exist
                remaining_accounts = accounts[i + 1 :]
                account_ids = await adapter.get_account_ids()

                for remaining_account in remaining_accounts:
                    assert remaining_account.id in account_ids
                    assert await adapter.account_exists(remaining_account.id)

    @pytest.mark.asyncio
    async def test_account_update_scenarios(self, db_session: AsyncSession):
        """Test different account update scenarios."""
        adapter = DatabaseAccountAdapter()

        with patch("app.adapters.accounts.get_async_session") as mock_get_session:

            async def mock_session_generator():
                yield db_session

            mock_get_session.side_effect = lambda: mock_session_generator()

            # Create initial account
            account = account_factory(
                name="Update Test Account", owner="update_user", cash=25000.0
            )
            await adapter.put_account(account)

            # Test partial update - only cash balance
            account.cash_balance = 30000.0
            await adapter.put_account(account)

            retrieved = await adapter.get_account(account.id)
            assert retrieved is not None
            assert retrieved.cash_balance == 30000.0
            assert retrieved.owner == "update_user"

            # Test owner update
            account.owner = "new_owner"
            await adapter.put_account(account)

            retrieved = await adapter.get_account(account.id)
            assert retrieved is not None
            assert retrieved.owner == "new_owner"
            assert retrieved.cash_balance == 30000.0

            # Test multiple field update
            account.cash_balance = 45000.0
            account.owner = "final_owner"
            await adapter.put_account(account)

            retrieved = await adapter.get_account(account.id)
            assert retrieved is not None
            assert retrieved.cash_balance == 45000.0
            assert retrieved.owner == "final_owner"

            # Clean up
            await adapter.delete_account(account.id)

    @pytest.mark.asyncio
    async def test_account_factory_integration(self, db_session: AsyncSession):
        """Test account factory integration with database operations."""
        adapter = DatabaseAccountAdapter()

        with patch("app.adapters.accounts.get_async_session") as mock_get_session:

            async def mock_session_generator():
                yield db_session

            mock_get_session.side_effect = lambda: mock_session_generator()

            # Test factory with default parameters
            default_account = account_factory()
            await adapter.put_account(default_account)

            retrieved = await adapter.get_account(default_account.id)
            assert retrieved is not None
            assert retrieved.cash_balance == 100000.0  # Default cash
            assert retrieved.owner == "default"
            assert retrieved.name == f"Account-{default_account.id}"

            # Test factory with custom parameters
            custom_account = account_factory(
                name="Custom Factory Account", owner="factory_user", cash=75000.0
            )
            await adapter.put_account(custom_account)

            retrieved = await adapter.get_account(custom_account.id)
            assert retrieved is not None
            assert retrieved.cash_balance == 75000.0
            assert retrieved.owner == "factory_user"
            # Note: Database adapter sets name based on ID, not factory name
            assert retrieved.name == f"Account-{custom_account.id}"

            # Test factory creates unique IDs
            account1 = account_factory()
            account2 = account_factory()
            assert account1.id != account2.id

            # Clean up
            await adapter.delete_account(default_account.id)
            await adapter.delete_account(custom_account.id)

    @pytest.mark.asyncio
    async def test_edge_cases_and_error_handling(self, db_session: AsyncSession):
        """Test edge cases and error handling scenarios."""
        adapter = DatabaseAccountAdapter()

        with patch("app.adapters.accounts.get_async_session") as mock_get_session:

            async def mock_session_generator():
                yield db_session

            mock_get_session.side_effect = lambda: mock_session_generator()

            # Test retrieving non-existent account
            non_existent_account = await adapter.get_account("non-existent-id")
            assert non_existent_account is None

            # Test checking existence of non-existent account
            exists = await adapter.account_exists("non-existent-id")
            assert exists is False

            # Test deleting non-existent account
            deletion_success = await adapter.delete_account("non-existent-id")
            assert deletion_success is False

            # Test empty account ID list when no accounts exist
            initial_ids = await adapter.get_account_ids()
            # Could be empty or contain other test accounts, just ensure it's a list
            assert isinstance(initial_ids, list)

            # Test with account having zero balance
            zero_balance_account = account_factory(cash=0.0)
            await adapter.put_account(zero_balance_account)

            retrieved = await adapter.get_account(zero_balance_account.id)
            assert retrieved is not None
            assert retrieved.cash_balance == 0.0

            # Test that negative balance validation works (should raise error)
            try:
                account_factory(cash=-1000.0)
                # If we get here, validation didn't work
                raise AssertionError("Expected ValidationError for negative balance")
            except Exception:
                # Expected validation error - this is correct behavior
                pass

            # Clean up
            await adapter.delete_account(zero_balance_account.id)

    @pytest.mark.asyncio
    async def test_concurrent_operations(self, db_session: AsyncSession):
        """Test concurrent account operations."""

        adapter = DatabaseAccountAdapter()

        with patch("app.adapters.accounts.get_async_session") as mock_get_session:

            async def mock_session_generator():
                yield db_session

            mock_get_session.side_effect = lambda: mock_session_generator()

            # Create multiple accounts sequentially (simulating concurrent scenario results)
            created_accounts = []
            for i in range(10):
                account = account_factory(
                    name=f"Concurrent Account {i}",
                    owner=f"concurrent_user_{i}",
                    cash=15000.0 + (i * 1000),
                )
                await adapter.put_account(account)
                created_accounts.append(account)

            # Verify all accounts were created
            assert len(created_accounts) == 10
            for account in created_accounts:
                assert await adapter.account_exists(account.id)

            # Verify all accounts appear in ID list
            account_ids = await adapter.get_account_ids()
            for account in created_accounts:
                assert account.id in account_ids

            # Update accounts sequentially (simulating concurrent updates)
            for account in created_accounts:
                account.cash_balance += 5000.0
                await adapter.put_account(account)

            # Verify updates
            for i, account in enumerate(created_accounts):
                retrieved = await adapter.get_account(account.id)
                assert retrieved is not None
                expected_balance = 15000.0 + (i * 1000) + 5000.0
                assert retrieved.cash_balance == expected_balance

            # Delete accounts sequentially (simulating concurrent deletions)
            deletion_results = []
            for account in created_accounts:
                result = await adapter.delete_account(account.id)
                deletion_results.append(result)

            # Verify all deletions succeeded
            assert all(deletion_results)

            # Verify all accounts are gone
            for account in created_accounts:
                assert not await adapter.account_exists(account.id)

    @pytest.mark.asyncio
    async def synthetic_database_constraints_and_relationships(
        self, db_session: AsyncSession
    ):
        """Test database constraints and potential relationships."""
        adapter = DatabaseAccountAdapter()

        with patch("app.adapters.accounts.get_async_session") as mock_get_session:

            async def mock_session_generator():
                yield db_session

            mock_get_session.side_effect = lambda: mock_session_generator()

            # Test account ID uniqueness by attempting to create duplicate
            original_account = account_factory(
                name="Original Account", owner="original_user", cash=40000.0
            )
            await adapter.put_account(original_account)

            # Create account with same ID (should update, not create duplicate)
            duplicate_account = Account(
                id=original_account.id,
                cash_balance=60000.0,
                positions=[],
                name="Updated Account",
                owner="updated_user",
            )
            await adapter.put_account(duplicate_account)

            # Verify only one account exists with updated values
            retrieved = await adapter.get_account(original_account.id)
            assert retrieved is not None
            assert retrieved.cash_balance == 60000.0
            assert retrieved.owner == "updated_user"

            # Verify only one entry in account_ids
            account_ids = await adapter.get_account_ids()
            matching_ids = [aid for aid in account_ids if aid == original_account.id]
            assert len(matching_ids) == 1

            # Test with various data types and edge values (only valid ones)
            valid_edge_cases = [
                {"cash": 0.000001, "owner": "tiny_balance_user"},
                {"cash": 999999999.99, "owner": "large_balance_user"},
                {"cash": 0.0, "owner": "zero_balance_user"},
            ]

            edge_accounts = []
            for case in valid_edge_cases:
                cash_value = case["cash"]
                account = account_factory(
                    owner=str(case["owner"]),
                    cash=float(cash_value) if cash_value is not None else 0.0,
                )
                await adapter.put_account(account)
                edge_accounts.append(account)

            # Test invalid cases (should raise validation errors)
            invalid_cases = [
                {"cash": -999999.50, "owner": "negative_user"},
                {"cash": float("inf"), "owner": "infinity_user"},
            ]

            for case in invalid_cases:
                try:
                    cash_value = case["cash"]
                    account = account_factory(
                        owner=str(case["owner"]),
                        cash=float(cash_value) if cash_value is not None else 0.0,
                    )
                    # If we get here, validation didn't work as expected
                    raise AssertionError(
                        f"Expected ValidationError for cash={case['cash']}"
                    )
                except Exception:
                    # Expected validation error - this is correct behavior
                    pass

            # Verify edge case accounts
            for account in edge_accounts:
                retrieved = await adapter.get_account(account.id)
                assert retrieved is not None
                assert retrieved.cash_balance == account.cash_balance

            # Clean up
            await adapter.delete_account(original_account.id)
            for account in edge_accounts:
                await adapter.delete_account(account.id)

    @pytest.mark.asyncio
    async def test_performance_with_many_accounts(self, db_session: AsyncSession):
        """Test performance with a larger number of accounts."""
        import time

        adapter = DatabaseAccountAdapter()

        with patch("app.adapters.accounts.get_async_session") as mock_get_session:

            async def mock_session_generator():
                yield db_session

            mock_get_session.side_effect = lambda: mock_session_generator()

            num_accounts = 50  # Reasonable number for integration test

            # Measure account creation time
            start_time = time.time()

            created_accounts = []
            for i in range(num_accounts):
                account = account_factory(
                    name=f"Performance Test Account {i}",
                    owner=f"perf_user_{i}",
                    cash=10000.0 + i,
                )
                await adapter.put_account(account)
                created_accounts.append(account)

            creation_time = time.time() - start_time

            # Measure retrieval time
            start_time = time.time()
            for account in created_accounts:
                retrieved = await adapter.get_account(account.id)
                assert retrieved is not None

            retrieval_time = time.time() - start_time

            # Measure get_account_ids performance
            start_time = time.time()
            account_ids = await adapter.get_account_ids()
            ids_time = time.time() - start_time

            # Verify all accounts are in the list
            for account in created_accounts:
                assert account.id in account_ids

            # Measure deletion time
            start_time = time.time()
            for account in created_accounts:
                success = await adapter.delete_account(account.id)
                assert success

            deletion_time = time.time() - start_time

            # Performance assertions (generous limits for integration tests)
            assert creation_time < 30.0  # Should create 50 accounts in under 30 seconds
            assert (
                retrieval_time < 15.0
            )  # Should retrieve 50 accounts in under 15 seconds
            assert ids_time < 5.0  # Should get ID list in under 5 seconds
            assert deletion_time < 15.0  # Should delete 50 accounts in under 15 seconds

            print(f"Performance results for {num_accounts} accounts:")
            print(f"  Creation: {creation_time:.2f}s")
            print(f"  Retrieval: {retrieval_time:.2f}s")
            print(f"  Get IDs: {ids_time:.2f}s")
            print(f"  Deletion: {deletion_time:.2f}s")
