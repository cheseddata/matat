"""add hebrew_name to donors

Revision ID: 806e4467aac0
Revises: a8d501f9c5b3
Create Date: 2026-04-30 09:16:42.893790

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = '806e4467aac0'
down_revision = 'a8d501f9c5b3'
branch_labels = None
depends_on = None


def upgrade():
    with op.batch_alter_table('donors', schema=None) as batch_op:
        batch_op.add_column(sa.Column('hebrew_name', sa.String(length=200), nullable=True))
        batch_op.create_index(batch_op.f('ix_donors_hebrew_name'), ['hebrew_name'], unique=False)


def downgrade():
    with op.batch_alter_table('donors', schema=None) as batch_op:
        batch_op.drop_index(batch_op.f('ix_donors_hebrew_name'))
        batch_op.drop_column('hebrew_name')
