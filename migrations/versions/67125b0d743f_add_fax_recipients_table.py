"""add_fax_recipients_table

Revision ID: 67125b0d743f
Revises: 385d0baebd36
Create Date: 2026-05-13 14:22:16.782785

"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import mysql

# revision identifiers, used by Alembic.
revision = '67125b0d743f'
down_revision = '385d0baebd36'
branch_labels = None
depends_on = None


def upgrade():
    op.create_table('fax_recipients',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('name', sa.String(length=255), nullable=False),
        sa.Column('bank_number', sa.String(length=10), nullable=False),
        sa.Column('branch_number', sa.String(length=10), nullable=False),
        sa.Column('account_number', sa.String(length=30), nullable=False),
        sa.Column('created_by', sa.Integer(), nullable=True),
        sa.Column('created_at', sa.DateTime(), nullable=True),
        sa.Column('updated_at', sa.DateTime(), nullable=True),
        sa.Column('deleted_at', sa.DateTime(), nullable=True),
        sa.ForeignKeyConstraint(['created_by'], ['users.id'], ondelete='SET NULL'),
        sa.PrimaryKeyConstraint('id'),
    )


def downgrade():
    op.drop_table('fax_recipients')
