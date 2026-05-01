"""Add yeshinvoice_webhook_data column to donations

Stores the full payload received from YeshInvoice's webhook callback
(both /doc and /tax events). Lets us build our own invoice template
later from every field YeshInvoice has about a receipt — customer
contact info, line items, payments breakdown, fields[] custom rows,
etc. — without further API calls.

Revision ID: b2c3d4e5f6a7
Revises: a1b2c3d4e5f6
Create Date: 2026-05-01 05:30:00.000000

"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import mysql


revision = 'b2c3d4e5f6a7'
down_revision = 'a1b2c3d4e5f6'
branch_labels = None
depends_on = None


def upgrade():
    with op.batch_alter_table('donations', schema=None) as batch_op:
        batch_op.add_column(sa.Column(
            'yeshinvoice_webhook_data',
            sa.JSON().with_variant(mysql.LONGTEXT(), 'mysql'),
            nullable=True,
        ))


def downgrade():
    with op.batch_alter_table('donations', schema=None) as batch_op:
        batch_op.drop_column('yeshinvoice_webhook_data')
