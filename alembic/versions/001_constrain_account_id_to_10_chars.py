"""Constrain account_id to 10 character alphanumeric format

Revision ID: 001
Revises:
Create Date: 2025-07-27 00:00:00.000000

"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "001"
down_revision: str | None = None
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Upgrade to constrain account_id to 10 characters."""

    # First, add a check constraint to validate existing data
    # This will fail if any existing account IDs don't meet the new format
    op.execute("""
        ALTER TABLE accounts 
        ADD CONSTRAINT check_account_id_format 
        CHECK (LENGTH(id) = 10 AND id ~ '^[A-Z0-9]{10}$')
    """)

    # Modify the account ID column to have length constraint
    op.alter_column(
        "accounts",
        "id",
        existing_type=sa.String(),
        type_=sa.String(length=10),
        existing_nullable=False,
    )

    # Update foreign key columns to also have the length constraint
    # Positions table
    op.alter_column(
        "positions",
        "account_id",
        existing_type=sa.String(),
        type_=sa.String(length=10),
        existing_nullable=False,
    )

    # Orders table
    op.alter_column(
        "orders",
        "account_id",
        existing_type=sa.String(),
        type_=sa.String(length=10),
        existing_nullable=False,
    )

    # Transactions table
    op.alter_column(
        "transactions",
        "account_id",
        existing_type=sa.String(),
        type_=sa.String(length=10),
        existing_nullable=False,
    )

    # Multi-leg orders table
    op.alter_column(
        "multi_leg_orders",
        "account_id",
        existing_type=sa.String(),
        type_=sa.String(length=10),
        existing_nullable=False,
    )

    # Recognized strategies table
    op.alter_column(
        "recognized_strategies",
        "account_id",
        existing_type=sa.String(),
        type_=sa.String(length=10),
        existing_nullable=False,
    )

    # Portfolio Greeks snapshots table
    op.alter_column(
        "portfolio_greeks_snapshots",
        "account_id",
        existing_type=sa.String(),
        type_=sa.String(length=10),
        existing_nullable=False,
    )


def downgrade() -> None:
    """Downgrade to remove account_id constraints."""

    # Remove the check constraint
    op.drop_constraint("check_account_id_format", "accounts", type_="check")

    # Revert column types back to unlimited String
    # Portfolio Greeks snapshots table
    op.alter_column(
        "portfolio_greeks_snapshots",
        "account_id",
        existing_type=sa.String(length=10),
        type_=sa.String(),
        existing_nullable=False,
    )

    # Recognized strategies table
    op.alter_column(
        "recognized_strategies",
        "account_id",
        existing_type=sa.String(length=10),
        type_=sa.String(),
        existing_nullable=False,
    )

    # Multi-leg orders table
    op.alter_column(
        "multi_leg_orders",
        "account_id",
        existing_type=sa.String(length=10),
        type_=sa.String(),
        existing_nullable=False,
    )

    # Transactions table
    op.alter_column(
        "transactions",
        "account_id",
        existing_type=sa.String(length=10),
        type_=sa.String(),
        existing_nullable=False,
    )

    # Orders table
    op.alter_column(
        "orders",
        "account_id",
        existing_type=sa.String(length=10),
        type_=sa.String(),
        existing_nullable=False,
    )

    # Positions table
    op.alter_column(
        "positions",
        "account_id",
        existing_type=sa.String(length=10),
        type_=sa.String(),
        existing_nullable=False,
    )

    # Accounts table
    op.alter_column(
        "accounts",
        "id",
        existing_type=sa.String(length=10),
        type_=sa.String(),
        existing_nullable=False,
    )
