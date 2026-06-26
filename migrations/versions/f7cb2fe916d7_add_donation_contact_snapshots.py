"""add donation_contact_snapshots

Revision ID: f7cb2fe916d7
Revises: c9fb6b81cbfd
Create Date: 2026-06-26 18:15:49.404656

"""
from alembic import op
import sqlalchemy as sa

revision = 'f7cb2fe916d7'
down_revision = 'c9fb6b81cbfd'
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        'donation_contact_snapshots',
        sa.Column('id', sa.Integer(), primary_key=True),
        sa.Column('donation_id', sa.Integer(), nullable=False),
        sa.Column('donor_id', sa.Integer(), nullable=True),
        sa.Column('first_name', sa.String(length=100), nullable=True),
        sa.Column('last_name', sa.String(length=100), nullable=True),
        sa.Column('company_name', sa.String(length=200), nullable=True),
        sa.Column('email', sa.String(length=255), nullable=True),
        sa.Column('phone', sa.String(length=50), nullable=True),
        sa.Column('address_line1', sa.String(length=255), nullable=True),
        sa.Column('address_line2', sa.String(length=255), nullable=True),
        sa.Column('city', sa.String(length=100), nullable=True),
        sa.Column('state', sa.String(length=100), nullable=True),
        sa.Column('zip', sa.String(length=20), nullable=True),
        sa.Column('country', sa.String(length=50), nullable=True),
        sa.Column('receipt_sent_to_email', sa.String(length=255), nullable=True),
        sa.Column('receipt_bounced', sa.Boolean(), nullable=False, server_default=sa.text('0')),
        sa.Column('receipt_fallback_used', sa.Boolean(), nullable=False, server_default=sa.text('0')),
        sa.Column('receipt_bounce_reason', sa.String(length=500), nullable=True),
        sa.Column('source', sa.String(length=50), nullable=True),
        sa.Column('raw_data', sa.JSON(), nullable=True),
        sa.Column('created_at', sa.DateTime(), nullable=False,
                  server_default=sa.text('CURRENT_TIMESTAMP')),
        sa.ForeignKeyConstraint(['donation_id'], ['donations.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['donor_id'], ['donors.id'], ondelete='SET NULL'),
        sa.UniqueConstraint('donation_id'),
    )
    op.create_index('ix_donation_contact_snapshots_donation_id',
                    'donation_contact_snapshots', ['donation_id'])
    op.create_index('ix_donation_contact_snapshots_donor_id',
                    'donation_contact_snapshots', ['donor_id'])
    op.create_index('ix_donation_contact_snapshots_email',
                    'donation_contact_snapshots', ['email'])


def downgrade():
    op.drop_index('ix_donation_contact_snapshots_email',
                  table_name='donation_contact_snapshots')
    op.drop_index('ix_donation_contact_snapshots_donor_id',
                  table_name='donation_contact_snapshots')
    op.drop_index('ix_donation_contact_snapshots_donation_id',
                  table_name='donation_contact_snapshots')
    op.drop_table('donation_contact_snapshots')
