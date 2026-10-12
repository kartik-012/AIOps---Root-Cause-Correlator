"""add_last_seen_at_to_service_dependencies

Revision ID: c4d91a23f802
Revises: b8e12f45c901
Create Date: 2026-10-12 16:08:00.000000

"""
from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa

revision: str = "c4d91a23f802"
down_revision: Union[str, None] = "b8e12f45c901"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Add last_seen_at column to service_dependencies for OTel trace topology discovery."""
    op.add_column(
        "service_dependencies",
        sa.Column("last_seen_at", sa.DateTime(timezone=True), nullable=True),
    )


def downgrade() -> None:
    """Remove last_seen_at column from service_dependencies."""
    op.drop_column("service_dependencies", "last_seen_at")
