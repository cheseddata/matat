"""split hebrew_name into hebrew_first_name + hebrew_last_name

Revision ID: 88459d423e98
Revises: 806e4467aac0
Create Date: 2026-04-30 09:19:58.046422

"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import mysql

# revision identifiers, used by Alembic.
revision = '88459d423e98'
down_revision = '806e4467aac0'
branch_labels = None
depends_on = None


def upgrade():
    # 1. Add the two new columns + their indexes.
    with op.batch_alter_table('donors', schema=None) as batch_op:
        batch_op.add_column(sa.Column('hebrew_first_name', sa.String(length=100), nullable=True))
        batch_op.add_column(sa.Column('hebrew_last_name', sa.String(length=100), nullable=True))
        batch_op.create_index(batch_op.f('ix_donors_hebrew_first_name'), ['hebrew_first_name'], unique=False)
        batch_op.create_index(batch_op.f('ix_donors_hebrew_last_name'), ['hebrew_last_name'], unique=False)

    # 2. Migrate existing hebrew_name values: split on first space.
    #    "מנחם קנטור" -> first="מנחם", last="קנטור"
    #    Single-word names -> first="X", last=NULL
    op.execute("""
        UPDATE donors
        SET
            hebrew_first_name = CASE
                WHEN LOCATE(' ', hebrew_name) = 0 THEN hebrew_name
                ELSE SUBSTRING(hebrew_name, 1, LOCATE(' ', hebrew_name) - 1)
            END,
            hebrew_last_name = CASE
                WHEN LOCATE(' ', hebrew_name) = 0 THEN NULL
                ELSE SUBSTRING(hebrew_name, LOCATE(' ', hebrew_name) + 1)
            END
        WHERE hebrew_name IS NOT NULL AND hebrew_name <> ''
    """)

    # 3. Drop the old single-field column + its index.
    with op.batch_alter_table('donors', schema=None) as batch_op:
        batch_op.drop_index(batch_op.f('ix_donors_hebrew_name'))
        batch_op.drop_column('hebrew_name')


def downgrade():
    with op.batch_alter_table('donors', schema=None) as batch_op:
        batch_op.add_column(sa.Column('hebrew_name',
                                      mysql.VARCHAR(collation='utf8mb4_unicode_ci', length=200),
                                      nullable=True))
        batch_op.create_index(batch_op.f('ix_donors_hebrew_name'), ['hebrew_name'], unique=False)

    op.execute("""
        UPDATE donors
        SET hebrew_name = TRIM(CONCAT(COALESCE(hebrew_first_name, ''), ' ',
                                       COALESCE(hebrew_last_name, '')))
        WHERE hebrew_first_name IS NOT NULL OR hebrew_last_name IS NOT NULL
    """)

    with op.batch_alter_table('donors', schema=None) as batch_op:
        batch_op.drop_index(batch_op.f('ix_donors_hebrew_last_name'))
        batch_op.drop_index(batch_op.f('ix_donors_hebrew_first_name'))
        batch_op.drop_column('hebrew_last_name')
        batch_op.drop_column('hebrew_first_name')
