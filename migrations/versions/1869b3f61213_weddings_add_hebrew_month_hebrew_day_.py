"""weddings: add hebrew_month + hebrew_day sort keys

Revision ID: 1869b3f61213
Revises: 67125b0d743f
Create Date: 2026-05-13 17:45:00.000000

"""
from alembic import op
import sqlalchemy as sa


revision = '1869b3f61213'
down_revision = '67125b0d743f'
branch_labels = None
depends_on = None


def upgrade():
    with op.batch_alter_table('weddings', schema=None) as batch_op:
        batch_op.add_column(sa.Column('hebrew_month', sa.Integer(), nullable=True))
        batch_op.add_column(sa.Column('hebrew_day',   sa.Integer(), nullable=True))
        batch_op.create_index(batch_op.f('ix_weddings_hebrew_month'),
                              ['hebrew_month'], unique=False)


def downgrade():
    with op.batch_alter_table('weddings', schema=None) as batch_op:
        batch_op.drop_index(batch_op.f('ix_weddings_hebrew_month'))
        batch_op.drop_column('hebrew_day')
        batch_op.drop_column('hebrew_month')
