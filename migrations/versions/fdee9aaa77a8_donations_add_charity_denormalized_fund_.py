"""donations: add charity (denormalized fund/campaign label)

Revision ID: fdee9aaa77a8
Revises: dec3fe3c91d7
Create Date: 2026-04-30 12:16:14.667592

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = 'fdee9aaa77a8'
down_revision = 'dec3fe3c91d7'
branch_labels = None
depends_on = None


def upgrade():
    with op.batch_alter_table('donations', schema=None) as batch_op:
        batch_op.add_column(sa.Column('charity', sa.String(length=200), nullable=True))
        batch_op.create_index(batch_op.f('ix_donations_charity'), ['charity'], unique=False)

    # Backfill: pull the Nedarim `Groupe` value out of processor_metadata
    # JSON and into the new top-level column. Only touches Nedarim rows
    # (Stripe / Shva / etc. don't write Groupe).
    op.execute("""
        UPDATE donations
        SET charity = TRIM(JSON_UNQUOTE(JSON_EXTRACT(processor_metadata, '$.Groupe')))
        WHERE payment_processor = 'nedarim'
          AND processor_metadata IS NOT NULL
          AND JSON_EXTRACT(processor_metadata, '$.Groupe') IS NOT NULL
          AND JSON_UNQUOTE(JSON_EXTRACT(processor_metadata, '$.Groupe')) <> ''
    """)


def downgrade():
    with op.batch_alter_table('donations', schema=None) as batch_op:
        batch_op.drop_index(batch_op.f('ix_donations_charity'))
        batch_op.drop_column('charity')
