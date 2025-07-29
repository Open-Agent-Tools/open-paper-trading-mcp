"""Add users table and update accounts with nullable user relationship

Revision ID: 85471114549d
Revises: 003
Create Date: 2025-07-28 18:58:00.000000

"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "85471114549d"
down_revision: str | Sequence[str] | None = "003"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Upgrade schema."""
    # Step 1: Create users table
    op.create_table(
        "users",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("username", sa.String(length=100), nullable=False),
        sa.Column("email", sa.String(length=255), nullable=False),
        sa.Column("first_name", sa.String(length=100), nullable=False),
        sa.Column("last_name", sa.String(length=100), nullable=False),
        sa.Column("phone", sa.String(length=20), nullable=True),
        sa.Column("date_of_birth", sa.Date(), nullable=True),
        sa.Column("is_verified", sa.Boolean(), nullable=False, server_default="false"),
        sa.Column(
            "verification_status",
            sa.String(length=50),
            nullable=False,
            server_default="'pending'",
        ),
        sa.Column(
            "account_tier",
            sa.String(length=50),
            nullable=False,
            server_default="'basic'",
        ),
        sa.Column("profile_settings", sa.JSON(), nullable=False, server_default="{}"),
        sa.Column("preferences", sa.JSON(), nullable=False, server_default="{}"),
        sa.Column(
            "created_at", sa.DateTime(), server_default=sa.text("now()"), nullable=False
        ),
        sa.Column(
            "updated_at", sa.DateTime(), server_default=sa.text("now()"), nullable=False
        ),
        sa.Column("last_login_at", sa.DateTime(), nullable=True),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_users_email", "users", ["email"], unique=True)
    op.create_index("ix_users_username", "users", ["username"], unique=True)

    # Step 2: Add nullable user_id column to accounts
    op.add_column("accounts", sa.Column("user_id", sa.String(length=36), nullable=True))
    op.create_index("ix_accounts_user_id", "accounts", ["user_id"])

    # Step 3: Add foreign key constraint
    op.create_foreign_key(
        "fk_accounts_user_id", "accounts", "users", ["user_id"], ["id"]
    )


def downgrade() -> None:
    """Downgrade schema."""
    # Remove foreign key constraint
    op.drop_constraint("fk_accounts_user_id", "accounts", type_="foreignkey")

    # Remove user_id column from accounts
    op.drop_index("ix_accounts_user_id", table_name="accounts")
    op.drop_column("accounts", "user_id")

    # Drop users table
    op.drop_index("ix_users_username", table_name="users")
    op.drop_index("ix_users_email", table_name="users")
    op.drop_table("users")
