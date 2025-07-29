"""
Test suite for multi-account functionality.
Tests the account_id parameter support across TradingService methods.
"""

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from app.adapters.synthetic_data import DevDataQuoteAdapter
from app.core.exceptions import NotFoundError
from app.models.database.trading import Account as DBAccount
from app.services.trading_service import TradingService

pytestmark = pytest.mark.journey_basic_trading


@pytest.mark.journey_account_management
@pytest.mark.database
@pytest.mark.asyncio
class TestMultiAccountFunctionality:
    """Test cases for multi-account functionality."""

    async def test_get_account_balance_with_account_id(self, db_session: AsyncSession):
        """Test getting account balance with specific account_id."""
        # Create two test accounts
        account1 = DBAccount(
            id="ACC0000001",
            owner="user1",
            cash_balance=15000.0,
            starting_balance=10000.0,
        )
        account2 = DBAccount(
            id="ACC0000002",
            owner="user2",
            cash_balance=25000.0,
            starting_balance=20000.0,
        )
        db_session.add(account1)
        db_session.add(account2)
        await db_session.commit()

        trading_service = TradingService(
            quote_adapter=DevDataQuoteAdapter(),
            account_owner="user1",
            db_session=db_session,
        )

        # Test getting balance for specific account
        balance1 = await trading_service.get_account_balance("ACC0000001")
        balance2 = await trading_service.get_account_balance("ACC0000002")

        assert balance1 == 15000.0
        assert balance2 == 25000.0

    async def test_get_account_info_with_account_id(self, db_session: AsyncSession):
        """Test getting account info with specific account_id."""
        # Create test account
        account = DBAccount(
            id="INFO000001",
            owner="info_user",
            cash_balance=12000.0,
            starting_balance=10000.0,
        )
        db_session.add(account)
        await db_session.commit()

        trading_service = TradingService(
            quote_adapter=DevDataQuoteAdapter(),
            account_owner="info_user",
            db_session=db_session,
        )

        # Test getting account info for specific account
        account_info = await trading_service.get_account_info("INFO000001")

        assert account_info["account_id"] == "INFO000001"
        assert account_info["owner"] == "info_user"
        assert account_info["cash_balance"] == 12000.0
        assert account_info["starting_balance"] == 10000.0

    async def test_account_id_validation(self, db_session: AsyncSession):
        """Test that invalid account_id formats are rejected."""
        trading_service = TradingService(
            quote_adapter=DevDataQuoteAdapter(),
            account_owner="test_user",
            db_session=db_session,
        )

        # Test various invalid account_id formats
        invalid_ids = [
            "short",  # Too short
            "toolongaccountid",  # Too long
            "lower12345",  # Contains lowercase
            "SPECIAL@#$",  # Contains special characters
            "123456789a",  # Contains lowercase letter
            "",  # Empty string
        ]

        for invalid_id in invalid_ids:
            with pytest.raises(ValueError, match="Invalid account ID format"):
                await trading_service.get_account_balance(invalid_id)

    async def test_account_not_found_error(self, db_session: AsyncSession):
        """Test that accessing non-existent account raises NotFoundError."""
        trading_service = TradingService(
            quote_adapter=DevDataQuoteAdapter(),
            account_owner="test_user",
            db_session=db_session,
        )

        # Test accessing non-existent account
        with pytest.raises(NotFoundError, match="Account with ID NONEXIST01 not found"):
            await trading_service.get_account_balance("NONEXIST01")

    async def test_portfolio_with_account_id(self, db_session: AsyncSession):
        """Test getting portfolio with specific account_id."""
        # Create test account
        account = DBAccount(
            id="PORT000001",
            owner="portfolio_user",
            cash_balance=50000.0,
            starting_balance=50000.0,
        )
        db_session.add(account)
        await db_session.commit()

        trading_service = TradingService(
            quote_adapter=DevDataQuoteAdapter(),
            account_owner="portfolio_user",
            db_session=db_session,
        )

        # Test getting portfolio for specific account
        portfolio = await trading_service.get_portfolio("PORT000001")

        assert portfolio.cash_balance == 50000.0
        assert isinstance(portfolio.positions, list)

    async def test_portfolio_summary_with_account_id(self, db_session: AsyncSession):
        """Test getting portfolio summary with specific account_id."""
        # Create test account
        account = DBAccount(
            id="SUMM000001",
            owner="summary_user",
            cash_balance=30000.0,
            starting_balance=25000.0,
        )
        db_session.add(account)
        await db_session.commit()

        trading_service = TradingService(
            quote_adapter=DevDataQuoteAdapter(),
            account_owner="summary_user",
            db_session=db_session,
        )

        # Test getting portfolio summary for specific account
        summary = await trading_service.get_portfolio_summary("SUMM000001")

        assert summary.cash_balance == 30000.0
        assert summary.total_value >= 30000.0  # Should be at least cash balance

    async def test_legacy_behavior_without_account_id(self, db_session: AsyncSession):
        """Test that legacy behavior (no account_id) still works."""
        # Create account for specific owner
        account = DBAccount(
            id="LEGACY0001",
            owner="legacy_user",
            cash_balance=40000.0,
            starting_balance=35000.0,
        )
        db_session.add(account)
        await db_session.commit()

        trading_service = TradingService(
            quote_adapter=DevDataQuoteAdapter(),
            account_owner="legacy_user",
            db_session=db_session,
        )

        # Test legacy behavior (no account_id parameter)
        balance = await trading_service.get_account_balance()
        account_info = await trading_service.get_account_info()
        portfolio = await trading_service.get_portfolio()
        summary = await trading_service.get_portfolio_summary()

        assert balance == 40000.0
        assert account_info["account_id"] == "LEGACY0001"
        assert portfolio.cash_balance == 40000.0
        assert summary.cash_balance == 40000.0
