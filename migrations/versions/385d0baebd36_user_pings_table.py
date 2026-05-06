"""user_pings table

Revision ID: 385d0baebd36
Revises: 4b608e4b46cd
Create Date: 2026-05-06 16:26:52.647740

"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import mysql

# revision identifiers, used by Alembic.
revision = '385d0baebd36'
down_revision = '4b608e4b46cd'
branch_labels = None
depends_on = None


def upgrade():
    op.create_table('user_pings',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('sender_id', sa.Integer(), nullable=False),
        sa.Column('recipient_id', sa.Integer(), nullable=False),
        sa.Column('title', sa.String(length=200), nullable=True),
        sa.Column('message', sa.Text(), nullable=False),
        sa.Column('link', sa.String(length=500), nullable=True),
        sa.Column('created_at', sa.DateTime(), nullable=True),
        sa.Column('delivered_at', sa.DateTime(), nullable=True),
        sa.Column('dismissed_at', sa.DateTime(), nullable=True),
        sa.ForeignKeyConstraint(['recipient_id'], ['users.id'], ),
        sa.ForeignKeyConstraint(['sender_id'], ['users.id'], ),
        sa.PrimaryKeyConstraint('id'),
    )
    with op.batch_alter_table('user_pings', schema=None) as batch_op:
        batch_op.create_index(batch_op.f('ix_user_pings_created_at'), ['created_at'], unique=False)
        batch_op.create_index(batch_op.f('ix_user_pings_dismissed_at'), ['dismissed_at'], unique=False)
        batch_op.create_index(batch_op.f('ix_user_pings_recipient_id'), ['recipient_id'], unique=False)


def downgrade():
    with op.batch_alter_table('user_pings', schema=None) as batch_op:
        batch_op.drop_index(batch_op.f('ix_user_pings_recipient_id'))
        batch_op.drop_index(batch_op.f('ix_user_pings_dismissed_at'))
        batch_op.drop_index(batch_op.f('ix_user_pings_created_at'))
    op.drop_table('user_pings')
