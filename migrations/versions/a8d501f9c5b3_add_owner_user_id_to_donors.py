"""add owner_user_id to donors (multi-office segregation)

Revision ID: a8d501f9c5b3
Revises: 0fc24eb63f94
Create Date: 2026-04-29 07:40:00.000000

Adds donors.owner_user_id (FK to users.id, NULL allowed). Each donor is
"owned" by one user account. Going forward we segregate offices by which
user owns each donor. Existing donors are backfilled to user_id=4
(Gittle Goldblum) in a separate step (`flask backfill-donor-owner ...`).
"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = 'a8d501f9c5b3'
down_revision = '0fc24eb63f94'
branch_labels = None
depends_on = None


def upgrade():
    with op.batch_alter_table('donors', schema=None) as batch:
        batch.add_column(sa.Column('owner_user_id', sa.Integer(), nullable=True))
        batch.create_index('ix_donors_owner_user_id', ['owner_user_id'], unique=False)
        batch.create_foreign_key(
            'fk_donors_owner_user_id_users',
            'users',
            ['owner_user_id'],
            ['id'],
            ondelete='SET NULL',
        )


def downgrade():
    with op.batch_alter_table('donors', schema=None) as batch:
        batch.drop_constraint('fk_donors_owner_user_id_users', type_='foreignkey')
        batch.drop_index('ix_donors_owner_user_id')
        batch.drop_column('owner_user_id')
