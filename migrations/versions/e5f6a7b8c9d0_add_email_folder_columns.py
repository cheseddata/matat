"""Add parent_folder_id + folder_name to email_messages.

Lets the inbox portal track which folder each message lives in upstream
and filter by folder. parent_folder_id is the backend's stable id;
folder_name is the human-readable display name resolved from a folder
listing at sync time.

Revision ID: e5f6a7b8c9d0
Revises: d4e5f6a7b8c9
Create Date: 2026-05-01 09:30:00.000000

"""
from alembic import op
import sqlalchemy as sa


revision = 'e5f6a7b8c9d0'
down_revision = 'd4e5f6a7b8c9'
branch_labels = None
depends_on = None


def upgrade():
    with op.batch_alter_table('email_messages', schema=None) as batch_op:
        batch_op.add_column(sa.Column('parent_folder_id', sa.String(length=500), nullable=True))
        batch_op.add_column(sa.Column('folder_name', sa.String(length=255), nullable=True))
        batch_op.create_index('ix_email_messages_parent_folder_id',
                              ['parent_folder_id'], unique=False)
        batch_op.create_index('ix_email_messages_folder_name',
                              ['folder_name'], unique=False)


def downgrade():
    with op.batch_alter_table('email_messages', schema=None) as batch_op:
        batch_op.drop_index('ix_email_messages_folder_name')
        batch_op.drop_index('ix_email_messages_parent_folder_id')
        batch_op.drop_column('folder_name')
        batch_op.drop_column('parent_folder_id')
