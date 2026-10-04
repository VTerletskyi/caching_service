"""create transformations and payloads tables

Revision ID: 001
Revises:
Create Date: 2026-10-04 15:32:38.754425

"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op


# revision identifiers, used by Alembic.
revision: str = "001"
down_revision: str | Sequence[str] | None = None
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Upgrade schema."""
    op.create_table(
        "payloads",
        sa.Column("payload_hash", sa.String(length=64), nullable=False),
        sa.Column("output", sa.Text(), nullable=False),
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("payload_hash"),
    )
    op.create_table(
        "transformations",
        sa.Column("input_hash", sa.String(length=64), nullable=False),
        sa.Column("input", sa.Text(), nullable=False),
        sa.Column("output", sa.Text(), nullable=False),
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("input_hash"),
    )


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_table("transformations")
    op.drop_table("payloads")
