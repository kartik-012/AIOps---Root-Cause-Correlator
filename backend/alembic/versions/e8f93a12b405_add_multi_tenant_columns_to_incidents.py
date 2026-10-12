"""add_multi_tenant_columns_to_incidents

Revision ID: e8f93a12b405
Revises: d7e82b41a903
Create Date: 2026-10-12 20:00:00.000000

"""
from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'e8f93a12b405'
down_revision: Union[str, None] = 'd7e82b41a903'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        'incidents',
        sa.Column('tenant_id', sa.String(length=100), nullable=False, server_default='default-tenant'),
    )
    op.add_column(
        'incidents',
        sa.Column('environment', sa.String(length=50), nullable=False, server_default='production'),
    )
    op.create_index(
        'idx_incidents_tenant_env',
        'incidents',
        ['tenant_id', 'environment'],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index('idx_incidents_tenant_env', table_name='incidents')
    op.drop_column('incidents', 'environment')
    op.drop_column('incidents', 'tenant_id')
