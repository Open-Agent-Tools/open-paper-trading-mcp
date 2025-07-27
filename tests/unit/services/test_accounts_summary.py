"""
Test suite for TradingService.get_all_accounts_summary() function.
"""

import pytest
from datetime import datetime, timezone
from sqlalchemy.ext.asyncio import AsyncSession

from app.services.trading_service import TradingService
from app.adapters.test_data import DevDataQuoteAdapter
from app.models.database.trading import Account as DBAccount
from app.schemas.accounts import AccountSummary, AccountSummaryList


@pytest.mark.asyncio
class TestGetAllAccountsSummary:
    """Test cases for get_all_accounts_summary function."""

    async def test_get_all_accounts_summary_empty_database(self, db_session: AsyncSession):
        """Test getting accounts summary when no accounts exist."""
        trading_service = TradingService(
            quote_adapter=DevDataQuoteAdapter(),
            account_owner="test_user",
            db_session=db_session
        )
        
        result = await trading_service.get_all_accounts_summary()
        
        assert isinstance(result, AccountSummaryList)
        assert result.total_count == 0
        assert result.total_starting_balance == 0.0
        assert result.total_current_balance == 0.0
        assert len(result.accounts) == 0

    async def test_get_all_accounts_summary_single_account(self, db_session: AsyncSession):
        """Test getting accounts summary with single account."""
        # Create test account
        account = DBAccount(
            id="TEST123456",
            owner="test_owner",
            cash_balance=15000.0,
            starting_balance=10000.0
        )
        db_session.add(account)
        await db_session.commit()
        
        trading_service = TradingService(
            quote_adapter=DevDataQuoteAdapter(),
            account_owner="test_owner",
            db_session=db_session
        )
        
        result = await trading_service.get_all_accounts_summary()
        
        assert isinstance(result, AccountSummaryList)
        assert result.total_count == 1
        assert result.total_starting_balance == 10000.0
        assert result.total_current_balance == 15000.0
        assert len(result.accounts) == 1
        
        account_summary = result.accounts[0]
        assert account_summary.id == "TEST123456"
        assert account_summary.owner == "test_owner"
        assert account_summary.starting_balance == 10000.0
        assert account_summary.current_balance == 15000.0

    async def test_get_all_accounts_summary_multiple_accounts(self, db_session: AsyncSession):
        """Test getting accounts summary with multiple accounts."""
        # Create multiple test accounts
        accounts_data = [
            {"id": "ACC0000001", "owner": "user1", "starting": 10000.0, "current": 12000.0},
            {"id": "ACC0000002", "owner": "user2", "starting": 20000.0, "current": 18000.0},
            {"id": "ACC0000003", "owner": "user3", "starting": 5000.0, "current": 7500.0},
        ]
        
        for data in accounts_data:
            account = DBAccount(
                id=data["id"],
                owner=data["owner"],
                cash_balance=data["current"],
                starting_balance=data["starting"]
            )
            db_session.add(account)
        
        await db_session.commit()
        
        trading_service = TradingService(
            quote_adapter=DevDataQuoteAdapter(),
            account_owner="user1",  # Can be any owner since we're getting all accounts
            db_session=db_session
        )
        
        result = await trading_service.get_all_accounts_summary()
        
        assert isinstance(result, AccountSummaryList)
        assert result.total_count == 3
        assert result.total_starting_balance == 35000.0  # 10k + 20k + 5k
        assert result.total_current_balance == 37500.0   # 12k + 18k + 7.5k
        assert len(result.accounts) == 3
        
        # Check accounts are sorted by created_at desc (newest first)
        account_ids = [acc.id for acc in result.accounts]
        assert set(account_ids) == {"ACC0000001", "ACC0000002", "ACC0000003"}
        
        # Verify individual account data
        for account_summary in result.accounts:
            assert isinstance(account_summary, AccountSummary)
            assert isinstance(account_summary.created_at, datetime)
            assert account_summary.starting_balance > 0
            assert account_summary.current_balance > 0

    async def test_get_all_accounts_summary_return_types(self, db_session: AsyncSession):
        """Test that return types are correct."""
        # Create test account
        account = DBAccount(
            id="TYPE123456",
            owner="type_test",
            cash_balance=10000.0,
            starting_balance=10000.0
        )
        db_session.add(account)
        await db_session.commit()
        
        trading_service = TradingService(
            quote_adapter=DevDataQuoteAdapter(),
            account_owner="type_test",
            db_session=db_session
        )
        
        result = await trading_service.get_all_accounts_summary()
        
        # Check main result type
        assert isinstance(result, AccountSummaryList)
        assert isinstance(result.total_count, int)
        assert isinstance(result.total_starting_balance, float)
        assert isinstance(result.total_current_balance, float)
        assert isinstance(result.accounts, list)
        
        # Check individual account type
        account_summary = result.accounts[0]
        assert isinstance(account_summary, AccountSummary)
        assert isinstance(account_summary.id, str)
        assert isinstance(account_summary.owner, str)
        assert isinstance(account_summary.starting_balance, float)
        assert isinstance(account_summary.current_balance, float)
        assert isinstance(account_summary.created_at, datetime)