"""add can_view_all_donations to users

Revision ID: 0fc24eb63f94
Revises: c7e2d4a9f1b3
Create Date: 2026-04-28 13:01:47.256848

"""
from alembic import op
import sqlalchemy as sa


revision = '0fc24eb63f94'
down_revision = 'c7e2d4a9f1b3'
branch_labels = None
depends_on = None


def upgrade():
    with op.batch_alter_table('users', schema=None) as batch_op:
        batch_op.add_column(sa.Column(
            'can_view_all_donations', sa.Boolean(),
            server_default='0', nullable=False,
        ))


def downgrade():
    with op.batch_alter_table('users', schema=None) as batch_op:
        batch_op.drop_column('can_view_all_donations')
