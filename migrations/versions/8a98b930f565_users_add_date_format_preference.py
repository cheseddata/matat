"""users: add date_format preference

Revision ID: 8a98b930f565
Revises: cb4834271d0e
Create Date: 2026-05-01 08:10:42.786936

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = '8a98b930f565'
down_revision = 'cb4834271d0e'
branch_labels = None
depends_on = None


def upgrade():
    with op.batch_alter_table('users', schema=None) as batch_op:
        batch_op.add_column(sa.Column('date_format', sa.String(length=20), server_default='auto', nullable=False))


def downgrade():
    with op.batch_alter_table('users', schema=None) as batch_op:
        batch_op.drop_column('date_format')
