"""add_deployment_events_table

Revision ID: d7e82b41a903
Revises: c4d91a23f802
Create Date: 2026-10-12 17:43:30.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'd7e82b41a903'
down_revision: Union[str, None] = 'c4d91a23f802'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        'deployment_events',
        sa.Column('id', sa.Uuid(), nullable=False),
        sa.Column('service_id', sa.Uuid(), nullable=False),
        sa.Column('git_sha', sa.String(length=64), nullable=False),
        sa.Column('config_version', sa.String(length=100), nullable=True),
        sa.Column('deployed_by', sa.String(length=100), nullable=True),
        sa.Column('environment', sa.String(length=50), nullable=False, server_default='production'),
        sa.Column('deployed_at', sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(['service_id'], ['services.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_index(
        'idx_deployment_service_time',
        'deployment_events',
        ['service_id', sa.text('deployed_at DESC')],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index('idx_deployment_service_time', table_name='deployment_events')
    op.drop_table('deployment_events')
