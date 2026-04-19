"""add allowed_processors to users

Revision ID: 03fc01b4e58c
Revises: 7b2c24b2be46
Create Date: 2026-04-19 05:39:41.950769

"""
from alembic import op
import sqlalchemy as sa


revision = '03fc01b4e58c'
down_revision = '7b2c24b2be46'
branch_labels = None
depends_on = None


def upgrade():
    with op.batch_alter_table('users', schema=None) as batch_op:
        batch_op.add_column(sa.Column('allowed_processors', sa.JSON(), nullable=True))


def downgrade():
    with op.batch_alter_table('users', schema=None) as batch_op:
        batch_op.drop_column('allowed_processors')
