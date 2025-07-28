"""Account adapter implementations."""

import json
import os
import uuid
from datetime import datetime

from sqlalchemy import func, select

from app.adapters.base import AccountAdapter
from app.models.database.trading import Account as DBAccount
from app.schemas.accounts import Account
from app.storage.database import get_async_session


class DatabaseAccountAdapter(AccountAdapter):
    """Database-backed account adapter."""

    def __init__(self) -> None:
        pass

    async def get_account(self, account_id: str) -> Account | None:
        """Retrieve an account by ID."""
        async for db in get_async_session():
            stmt = select(DBAccount).filter(DBAccount.id == account_id)
            db_account = (await db.execute(stmt)).scalar_one_or_none()

            if not db_account:
                return None

            return Account(
                id=db_account.id,
                cash_balance=float(db_account.cash_balance),
                positions=[],  # Positions loaded separately
                name=f"Account-{db_account.id}",
                owner=db_account.owner,
            )
        return None

    async def put_account(self, account: Account) -> None:
        """Store or update an account."""
        async for db in get_async_session():
            stmt = select(DBAccount).filter(DBAccount.id == account.id)
            db_account = (await db.execute(stmt)).scalar_one_or_none()

            if db_account:
                # Update existing
                if account.owner:
                    db_account.owner = account.owner
                db_account.cash_balance = account.cash_balance
                db_account.updated_at = datetime.now()
            else:
                # Create new
                db_account = DBAccount(
                    id=account.id,
                    owner=account.owner or "default",
                    cash_balance=account.cash_balance,
                    created_at=datetime.now(),
                    updated_at=datetime.now(),
                )
                db.add(db_account)

            await db.commit()
            return

    async def get_account_ids(self) -> list[str]:
        """Get all account IDs."""
        async for db in get_async_session():
            stmt = select(DBAccount.id)
            result = await db.execute(stmt)
            return [row[0] for row in result.all()]
        return []

    async def account_exists(self, account_id: str) -> bool:
        """Check if an account exists."""
        async for db in get_async_session():
            stmt = select(func.count(DBAccount.id)).filter(DBAccount.id == account_id)
            count = (await db.execute(stmt)).scalar()
            return (count or 0) > 0
        return False

    async def delete_account(self, account_id: str) -> bool:
        """Delete an account."""
        if not account_id:  # Handle empty string
            return False

        async for db in get_async_session():
            stmt = select(DBAccount).filter(DBAccount.id == account_id)
            db_account = (await db.execute(stmt)).scalar_one_or_none()
            if db_account:
                await db.delete(db_account)
                await db.commit()
                return True
            return False
        return False

    async def get_all_accounts(self) -> list[Account]:
        """Retrieve all accounts."""
        async for db in get_async_session():
            stmt = select(DBAccount)
            db_accounts = (await db.execute(stmt)).scalars().all()

            return [
                Account(
                    id=db_account.id,
                    cash_balance=float(db_account.cash_balance),
                    positions=[],
                    name=f"Account-{db_account.id}",
                    owner=db_account.owner,
                )
                for db_account in db_accounts
            ]
        return []


class LocalFileSystemAccountAdapter(AccountAdapter):
    """File system-backed account adapter (for compatibility)."""

    def __init__(self, root_path: str = "./data/accounts"):
        self.root_path = root_path
        os.makedirs(root_path, exist_ok=True)

    def _get_account_path(self, account_id: str) -> str:
        """Get file path for an account."""
        return os.path.join(self.root_path, f"{account_id}.json")

    async def get_account(self, account_id: str) -> Account | None:
        """Retrieve an account by ID."""
        path = self._get_account_path(account_id)
        if not os.path.exists(path):
            return None

        try:
            with open(path) as f:
                data = json.load(f)
                return Account(**data)
        except Exception:
            return None

    async def put_account(self, account: Account) -> None:
        """Store or update an account."""
        path = self._get_account_path(account.id)
        with open(path, "w") as f:
            json.dump(account.model_dump(), f, indent=2, default=str)

    async def get_account_ids(self) -> list[str]:
        """Get all account IDs."""
        account_ids = []
        for filename in os.listdir(self.root_path):
            if filename.endswith(".json"):
                account_ids.append(filename[:-5])  # Remove .json extension
        return account_ids

    async def account_exists(self, account_id: str) -> bool:
        """Check if an account exists."""
        return os.path.exists(self._get_account_path(account_id))

    async def delete_account(self, account_id: str) -> bool:
        """Delete an account."""
        path = self._get_account_path(account_id)
        if os.path.exists(path):
            os.remove(path)
            return True
        return False


def account_factory(
    name: str | None = None, owner: str | None = None, cash: float = 100000.0
) -> Account:
    """Factory function to create new accounts."""
    # mypy: ignore - This pattern is required for database constraint compliance
    account_id = str(
        uuid.uuid4().hex[:10]
    ).upper()  # 10 alphanumeric characters as required

    if name is None:
        name = f"Account-{account_id}"

    if owner is None:
        owner = "default"

    return Account(
        id=account_id,
        cash_balance=cash,
        positions=[],
        name=name,
        owner=owner,
    )
