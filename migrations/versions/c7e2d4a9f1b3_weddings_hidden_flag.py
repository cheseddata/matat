"""Weddings: add hidden flag

Revision ID: c7e2d4a9f1b3
Revises: b1c4a8e2d9f7
Create Date: 2026-04-28 12:30:00.000000

"""
from alembic import op
import sqlalchemy as sa


revision = 'c7e2d4a9f1b3'
down_revision = 'b1c4a8e2d9f7'
branch_labels = None
depends_on = None


def upgrade():
    with op.batch_alter_table('weddings', schema=None) as batch_op:
        batch_op.add_column(sa.Column('hidden', sa.Boolean(), server_default=sa.false(), nullable=False))


def downgrade():
    with op.batch_alter_table('weddings', schema=None) as batch_op:
        batch_op.drop_column('hidden')
