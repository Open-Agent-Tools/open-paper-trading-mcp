"""Account adapter implementations."""

import json
import os
import uuid
from datetime import datetime

from sqlalchemy.ext.asyncio import AsyncSession

from app.adapters.base import AccountAdapter
from app.models.database.trading import Account as DBAccount
from app.schemas.accounts import Account
from app.storage.database import AsyncSessionLocal


class DatabaseAccountAdapter(AccountAdapter):
    """Database-backed account adapter."""

    def __init__(self, db_session: AsyncSession | None = None):
        self._db = db_session

    @property
    def db(self) -> AsyncSession:
        """Get database session."""
        if self._db is None:
            self._db = AsyncSessionLocal()
        return self._db

    def get_account(self, account_id: str) -> Account | None:
        """Retrieve an account by ID."""
        db_account = self.db.query(DBAccount).filter(DBAccount.id == account_id).first()
        if not db_account:
            return None

        return Account(
            id=db_account.id,
            cash_balance=float(db_account.cash_balance),
            positions=[],  # Positions loaded separately
            name=f"Account-{db_account.id}",
            owner=db_account.owner,
        )

    def put_account(self, account: Account) -> None:
        """Store or update an account."""
        db_account = self.db.query(DBAccount).filter(DBAccount.id == account.id).first()

        if db_account:
            # Update existing
            if account.owner:
                db_account.owner = account.owner
            db_account.cash_balance = account.cash_balance
            db_account.updated_at = datetime.utcnow()
        else:
            # Create new
            db_account = DBAccount(
                id=account.id,
                owner=account.owner or "default",
                cash_balance=account.cash_balance,
                created_at=datetime.utcnow(),
                updated_at=datetime.utcnow(),
            )
            self.db.add(db_account)

        self.db.commit()

    def get_account_ids(self) -> list[str]:
        """Get all account IDs."""
        return [acc.id for acc in self.db.query(DBAccount.id).all()]

    def account_exists(self, account_id: str) -> bool:
        """Check if an account exists."""
        return self.db.query(DBAccount).filter(DBAccount.id == account_id).count() > 0

    def delete_account(self, account_id: str) -> bool:
        """Delete an account."""
        db_account = self.db.query(DBAccount).filter(DBAccount.id == account_id).first()
        if db_account:
            self.db.delete(db_account)
            self.db.commit()
            return True
        return False


class LocalFileSystemAccountAdapter(AccountAdapter):
    """File system-backed account adapter (for compatibility)."""

    def __init__(self, root_path: str = "./data/accounts"):
        self.root_path = root_path
        os.makedirs(root_path, exist_ok=True)

    def _get_account_path(self, account_id: str) -> str:
        """Get file path for an account."""
        return os.path.join(self.root_path, f"{account_id}.json")

    def get_account(self, account_id: str) -> Account | None:
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

    def put_account(self, account: Account) -> None:
        """Store or update an account."""
        path = self._get_account_path(account.id)
        with open(path, "w") as f:
            json.dump(account.model_dump(), f, indent=2, default=str)

    def get_account_ids(self) -> list[str]:
        """Get all account IDs."""
        account_ids = []
        for filename in os.listdir(self.root_path):
            if filename.endswith(".json"):
                account_ids.append(filename[:-5])  # Remove .json extension
        return account_ids

    def account_exists(self, account_id: str) -> bool:
        """Check if an account exists."""
        return os.path.exists(self._get_account_path(account_id))

    def delete_account(self, account_id: str) -> bool:
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
    account_id = str(uuid.uuid4())[:8]  # Short ID like reference implementation

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
