"""add stripe_payment_link_url to config_settings

Revision ID: c9fb6b81cbfd
Revises: 1869b3f61213
Create Date: 2026-06-26 17:23:17.873346

"""
from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision = 'c9fb6b81cbfd'
down_revision = '1869b3f61213'
branch_labels = None
depends_on = None


def upgrade():
    op.add_column(
        'config',
        sa.Column('stripe_payment_link_url', sa.String(length=500), nullable=True),
    )
    # Seed with the current PaymentLink URL so the column has a value
    # immediately — admins can edit in the settings UI without us having
    # to ship a follow-up data migration.
    op.execute(
        "UPDATE config "
        "SET stripe_payment_link_url = 'https://donate.stripe.com/dRm5kE2IRb2AdC16I22cg02' "
        "WHERE stripe_payment_link_url IS NULL"
    )


def downgrade():
    op.drop_column('config', 'stripe_payment_link_url')
