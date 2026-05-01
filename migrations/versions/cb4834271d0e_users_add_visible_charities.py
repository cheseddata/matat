"""users: add visible_charities

Revision ID: cb4834271d0e
Revises: b2c3d4e5f6a7
Create Date: 2026-05-01 07:42:50.301679

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = 'cb4834271d0e'
down_revision = 'b2c3d4e5f6a7'
branch_labels = None
depends_on = None


def upgrade():
    with op.batch_alter_table('users', schema=None) as batch_op:
        batch_op.add_column(sa.Column('visible_charities', sa.JSON(), nullable=True))


def downgrade():
    with op.batch_alter_table('users', schema=None) as batch_op:
        batch_op.drop_column('visible_charities')
