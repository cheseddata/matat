"""Add yeshinvoice_allocation_number column to donations

Revision ID: a1b2c3d4e5f6
Revises: df3585d3ad94
Create Date: 2026-05-01 05:18:00.000000

"""
from alembic import op
import sqlalchemy as sa


revision = 'a1b2c3d4e5f6'
down_revision = 'df3585d3ad94'
branch_labels = None
depends_on = None


def upgrade():
    with op.batch_alter_table('donations', schema=None) as batch_op:
        batch_op.add_column(sa.Column('yeshinvoice_allocation_number', sa.String(length=50), nullable=True))
        batch_op.create_index(
            'ix_donations_yeshinvoice_allocation_number',
            ['yeshinvoice_allocation_number'],
            unique=False,
        )


def downgrade():
    with op.batch_alter_table('donations', schema=None) as batch_op:
        batch_op.drop_index('ix_donations_yeshinvoice_allocation_number')
        batch_op.drop_column('yeshinvoice_allocation_number')
