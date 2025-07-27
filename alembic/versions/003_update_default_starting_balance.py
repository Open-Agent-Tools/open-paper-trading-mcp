"""Update default starting balance to 10,000

Revision ID: 003
Revises: 002
Create Date: 2025-07-27 12:30:00.000000

"""

from collections.abc import Sequence

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "003"
down_revision: str | None = "002"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Update default values for cash_balance and starting_balance to 10,000."""
    # Update column defaults
    op.alter_column("accounts", "cash_balance", server_default="10000.0")
    op.alter_column("accounts", "starting_balance", server_default="10000.0")


def downgrade() -> None:
    """Revert default values for cash_balance and starting_balance to 100,000."""
    # Revert column defaults
    op.alter_column("accounts", "cash_balance", server_default="100000.0")
    op.alter_column("accounts", "starting_balance", server_default="100000.0")
