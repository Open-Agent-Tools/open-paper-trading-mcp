"""Add starting_balance to accounts table

Revision ID: 002_add_starting_balance
Revises: 001_constrain_account_id_to_10_chars
Create Date: 2025-07-27 12:00:00.000000

"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "002"
down_revision: str | None = "001"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Add starting_balance column to accounts table."""
    # Add starting_balance column with default value
    op.add_column(
        "accounts",
        sa.Column(
            "starting_balance", sa.Float(), nullable=False, server_default="10000.0"
        ),
    )

    # Update existing accounts to set starting_balance equal to current cash_balance
    # This assumes existing accounts started with their current balance
    op.execute(
        "UPDATE accounts SET starting_balance = cash_balance WHERE starting_balance IS NULL"
    )


def downgrade() -> None:
    """Remove starting_balance column from accounts table."""
    op.drop_column("accounts", "starting_balance")
