"""Account adapter implementations."""

import json
import os
from typing import List, Optional
from datetime import datetime
import uuid

from sqlalchemy.orm import Session

from app.adapters.base import AccountAdapter
from app.schemas.accounts import Account
from app.models.database.trading import Account as DBAccount
from app.storage.database import SessionLocal


class DatabaseAccountAdapter(AccountAdapter):
    """Database-backed account adapter."""

    def __init__(self, db_session: Optional[Session] = None):
        self._db = db_session

    @property
    def db(self) -> Session:
        """Get database session."""
        if self._db is None:
            self._db = SessionLocal()
        return self._db

    def get_account(self, account_id: str) -> Optional[Account]:
        """Retrieve an account by ID."""
        db_account = self.db.query(DBAccount).filter(DBAccount.id == account_id).first()
        if not db_account:
            return None

        return Account(
            id=db_account.id,
            name=db_account.name,
            owner=db_account.owner,
            cash=float(db_account.cash),
            positions=[],  # Positions loaded separately
            orders=[],  # Orders loaded separately
            transactions=[],  # Transactions loaded separately
        )

    def put_account(self, account: Account) -> None:
        """Store or update an account."""
        db_account = self.db.query(DBAccount).filter(DBAccount.id == account.id).first()

        if db_account:
            # Update existing
            db_account.name = account.name
            db_account.owner = account.owner
            db_account.cash = account.cash
            db_account.updated_at = datetime.utcnow()
        else:
            # Create new
            db_account = DBAccount(
                id=account.id,
                name=account.name,
                owner=account.owner,
                cash=account.cash,
                created_at=datetime.utcnow(),
                updated_at=datetime.utcnow(),
            )
            self.db.add(db_account)

        self.db.commit()

    def get_account_ids(self) -> List[str]:
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

    def get_account(self, account_id: str) -> Optional[Account]:
        """Retrieve an account by ID."""
        path = self._get_account_path(account_id)
        if not os.path.exists(path):
            return None

        try:
            with open(path, "r") as f:
                data = json.load(f)
                return Account(**data)
        except Exception:
            return None

    def put_account(self, account: Account) -> None:
        """Store or update an account."""
        path = self._get_account_path(account.id)
        with open(path, "w") as f:
            json.dump(account.model_dump(), f, indent=2, default=str)

    def get_account_ids(self) -> List[str]:
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
    name: Optional[str] = None, owner: Optional[str] = None, cash: float = 100000.0
) -> Account:
    """Factory function to create new accounts."""
    account_id = str(uuid.uuid4())[:8]  # Short ID like reference implementation

    if name is None:
        name = f"Account-{account_id}"

    if owner is None:
        owner = "default"

    return Account(
        id=account_id,
        name=name,
        owner=owner,
        cash=cash,
        positions=[],
        orders=[],
        transactions=[],
    )
