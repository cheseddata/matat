"""Add email_messages + email_attachments tables.

Stores ingested mail from any email_inbox_providers row. Attachment
binaries are stored inline (Text column) but only fetched lazily on
first download click — see email_inbox phase 2 in the changelog.

Revision ID: d4e5f6a7b8c9
Revises: aa480c874101
Create Date: 2026-05-01 06:30:00.000000

"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import mysql


revision = 'd4e5f6a7b8c9'
down_revision = 'aa480c874101'
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        'email_messages',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('provider_id', sa.Integer(), nullable=False),
        sa.Column('remote_id', sa.String(length=500), nullable=False),
        sa.Column('internet_message_id', sa.String(length=500), nullable=True),
        sa.Column('conversation_id', sa.String(length=500), nullable=True),
        sa.Column('from_address', sa.String(length=255), nullable=True),
        sa.Column('from_name', sa.String(length=255), nullable=True),
        sa.Column('to_addresses', sa.JSON().with_variant(mysql.LONGTEXT(), 'mysql'), nullable=True),
        sa.Column('cc_addresses', sa.JSON().with_variant(mysql.LONGTEXT(), 'mysql'), nullable=True),
        sa.Column('bcc_addresses', sa.JSON().with_variant(mysql.LONGTEXT(), 'mysql'), nullable=True),
        sa.Column('subject', sa.String(length=1000), nullable=True),
        sa.Column('body_text', sa.Text().with_variant(mysql.LONGTEXT(), 'mysql'), nullable=True),
        sa.Column('body_html', sa.Text().with_variant(mysql.LONGTEXT(), 'mysql'), nullable=True),
        sa.Column('body_preview', sa.String(length=500), nullable=True),
        sa.Column('received_at', sa.DateTime(), nullable=True),
        sa.Column('importance', sa.String(length=20), nullable=True),
        sa.Column('has_attachments', sa.Boolean(), nullable=True),
        sa.Column('is_read', sa.Boolean(), nullable=True),
        sa.Column('is_archived', sa.Boolean(), nullable=True),
        sa.Column('donor_id', sa.Integer(), nullable=True),
        sa.Column('created_at', sa.DateTime(), nullable=True),
        sa.Column('updated_at', sa.DateTime(), nullable=True),
        sa.ForeignKeyConstraint(['provider_id'], ['email_inbox_providers.id']),
        sa.ForeignKeyConstraint(['donor_id'], ['donors.id']),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('provider_id', 'remote_id', name='uq_email_provider_remote'),
    )
    op.create_index('ix_email_messages_provider_id', 'email_messages', ['provider_id'])
    op.create_index('ix_email_messages_remote_id', 'email_messages', ['remote_id'])
    op.create_index('ix_email_messages_internet_message_id', 'email_messages', ['internet_message_id'])
    op.create_index('ix_email_messages_conversation_id', 'email_messages', ['conversation_id'])
    op.create_index('ix_email_messages_from_address', 'email_messages', ['from_address'])
    op.create_index('ix_email_messages_received_at', 'email_messages', ['received_at'])
    op.create_index('ix_email_messages_is_read', 'email_messages', ['is_read'])
    op.create_index('ix_email_messages_is_archived', 'email_messages', ['is_archived'])
    op.create_index('ix_email_messages_donor_id', 'email_messages', ['donor_id'])

    op.create_table(
        'email_attachments',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('email_id', sa.Integer(), nullable=False),
        sa.Column('remote_id', sa.String(length=500), nullable=False),
        sa.Column('filename', sa.String(length=500), nullable=True),
        sa.Column('content_type', sa.String(length=255), nullable=True),
        sa.Column('size', sa.Integer(), nullable=True),
        sa.Column('is_inline', sa.Boolean(), nullable=True),
        sa.Column('content_id', sa.String(length=255), nullable=True),
        sa.Column('content_b64', sa.Text().with_variant(mysql.LONGTEXT(), 'mysql'), nullable=True),
        sa.Column('created_at', sa.DateTime(), nullable=True),
        sa.Column('fetched_at', sa.DateTime(), nullable=True),
        sa.ForeignKeyConstraint(['email_id'], ['email_messages.id']),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_index('ix_email_attachments_email_id', 'email_attachments', ['email_id'])


def downgrade():
    op.drop_index('ix_email_attachments_email_id', table_name='email_attachments')
    op.drop_table('email_attachments')

    for ix in ('ix_email_messages_donor_id', 'ix_email_messages_is_archived',
               'ix_email_messages_is_read', 'ix_email_messages_received_at',
               'ix_email_messages_from_address', 'ix_email_messages_conversation_id',
               'ix_email_messages_internet_message_id', 'ix_email_messages_remote_id',
               'ix_email_messages_provider_id'):
        op.drop_index(ix, table_name='email_messages')
    op.drop_table('email_messages')
