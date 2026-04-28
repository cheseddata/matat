"""Add weddings table

Revision ID: b1c4a8e2d9f7
Revises: 3561cad40c40
Create Date: 2026-04-28 11:30:00.000000

"""
from alembic import op
import sqlalchemy as sa


revision = 'b1c4a8e2d9f7'
down_revision = '3561cad40c40'
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        'weddings',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('hebrew_date', sa.String(length=80), nullable=False),
        sa.Column('gregorian_date', sa.Date(), nullable=True),
        sa.Column('groom_name', sa.String(length=120), nullable=False),
        sa.Column('bride_name', sa.String(length=120), nullable=False),
        sa.Column('hall_name', sa.String(length=160), nullable=True),
        sa.Column('phone', sa.String(length=40), nullable=True),
        sa.Column('contact_name', sa.String(length=120), nullable=True),
        sa.Column('notes', sa.Text(), nullable=True),
        sa.Column('created_at', sa.DateTime(), nullable=True),
        sa.Column('updated_at', sa.DateTime(), nullable=True),
        sa.Column('deleted_at', sa.DateTime(), nullable=True),
        sa.Column('created_by_id', sa.Integer(), nullable=True),
        sa.ForeignKeyConstraint(['created_by_id'], ['users.id'], ondelete='SET NULL'),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_index('ix_weddings_gregorian_date', 'weddings', ['gregorian_date'], unique=False)


def downgrade():
    op.drop_index('ix_weddings_gregorian_date', table_name='weddings')
    op.drop_table('weddings')
