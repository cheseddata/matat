"""donors: add IL + foreign phones (home/cell/fax)

Revision ID: dec3fe3c91d7
Revises: 88459d423e98
Create Date: 2026-04-30 10:27:34.657658

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = 'dec3fe3c91d7'
down_revision = '88459d423e98'
branch_labels = None
depends_on = None


def upgrade():
    # Add 5 new columns (il_phone_cell already exists from earlier work).
    with op.batch_alter_table('donors', schema=None) as batch_op:
        batch_op.add_column(sa.Column('il_phone_home', sa.String(length=50), nullable=True))
        batch_op.add_column(sa.Column('il_phone_fax', sa.String(length=50), nullable=True))
        batch_op.add_column(sa.Column('foreign_phone_home', sa.String(length=50), nullable=True))
        batch_op.add_column(sa.Column('foreign_phone_cell', sa.String(length=50), nullable=True))
        batch_op.add_column(sa.Column('foreign_phone_fax', sa.String(length=50), nullable=True))

    # Backfill: route the legacy single `phone` value to the right cell
    # column based on the donor's country. IL donors → il_phone_cell.
    # Everyone else → foreign_phone_cell. Skip rows where the target is
    # already populated (don't overwrite earlier manual data).
    op.execute("""
        UPDATE donors
        SET il_phone_cell = phone
        WHERE country IN ('IL', 'ISRAEL', 'ISR', 'ISRA')
          AND phone IS NOT NULL AND phone <> ''
          AND (il_phone_cell IS NULL OR il_phone_cell = '')
    """)
    op.execute("""
        UPDATE donors
        SET foreign_phone_cell = phone
        WHERE (country NOT IN ('IL', 'ISRAEL', 'ISR', 'ISRA') OR country IS NULL)
          AND phone IS NOT NULL AND phone <> ''
          AND (foreign_phone_cell IS NULL OR foreign_phone_cell = '')
    """)


def downgrade():
    with op.batch_alter_table('donors', schema=None) as batch_op:
        batch_op.drop_column('foreign_phone_fax')
        batch_op.drop_column('foreign_phone_cell')
        batch_op.drop_column('foreign_phone_home')
        batch_op.drop_column('il_phone_fax')
        batch_op.drop_column('il_phone_home')
