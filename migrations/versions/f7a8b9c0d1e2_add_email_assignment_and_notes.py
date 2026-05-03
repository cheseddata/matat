"""Add operator assignment + internal notes to email_messages.

Lets operators delegate inbox follow-ups: each message can be assigned
to a User (assigned_to_user_id), and operators can leave private notes
on a message via internal_notes.

Revision ID: f7a8b9c0d1e2
Revises: e5f6a7b8c9d0
Create Date: 2026-05-03 02:50:00.000000

"""
from alembic import op
import sqlalchemy as sa


revision = 'f7a8b9c0d1e2'
down_revision = 'e5f6a7b8c9d0'
branch_labels = None
depends_on = None


def upgrade():
    with op.batch_alter_table('email_messages', schema=None) as batch_op:
        batch_op.add_column(sa.Column('assigned_to_user_id', sa.Integer(), nullable=True))
        batch_op.add_column(sa.Column('internal_notes', sa.Text(), nullable=True))
        batch_op.create_index('ix_email_messages_assigned_to_user_id',
                              ['assigned_to_user_id'], unique=False)
        batch_op.create_foreign_key(
            'fk_email_messages_assigned_to_user',
            'users', ['assigned_to_user_id'], ['id'],
            ondelete='SET NULL',
        )


def downgrade():
    with op.batch_alter_table('email_messages', schema=None) as batch_op:
        batch_op.drop_constraint('fk_email_messages_assigned_to_user', type_='foreignkey')
        batch_op.drop_index('ix_email_messages_assigned_to_user_id')
        batch_op.drop_column('internal_notes')
        batch_op.drop_column('assigned_to_user_id')
