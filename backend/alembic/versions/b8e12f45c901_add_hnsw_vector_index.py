"""add_hnsw_vector_index

Revision ID: b8e12f45c901
Revises: 9a7e62c2bcc0
Create Date: 2026-09-30 22:15:00.000000

"""
from typing import Sequence, Union
from alembic import op

# revision identifiers, used by Alembic.
revision: str = 'b8e12f45c901'
down_revision: Union[str, None] = '9a7e62c2bcc0'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Create HNSW vector index on incident signatures using vector_cosine_ops."""
    op.execute("""
        CREATE INDEX IF NOT EXISTS idx_incidents_signature_hnsw 
        ON incidents USING hnsw (anomaly_signature vector_cosine_ops)
        WITH (m = 16, ef_construction = 64);
    """)


def downgrade() -> None:
    """Drop HNSW vector index."""
    op.execute("DROP INDEX IF EXISTS idx_incidents_signature_hnsw;")
