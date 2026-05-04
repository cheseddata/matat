"""email_templates: add attachments JSON list

Revision ID: 4b608e4b46cd
Revises: f7a8b9c0d1e2
Create Date: 2026-05-04 16:49:07.761479

"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import mysql

# revision identifiers, used by Alembic.
revision = '4b608e4b46cd'
down_revision = 'f7a8b9c0d1e2'
branch_labels = None
depends_on = None


def upgrade():
    with op.batch_alter_table('email_templates', schema=None) as batch_op:
        batch_op.add_column(sa.Column('attachments', sa.JSON(), nullable=True))

    # Backfill: every template that already had a single attachment
    # gets it copied into the new list as the first entry. Legacy
    # columns kept populated for safety; the model property
    # `all_attachments` merges both.
    op.execute("""
        UPDATE email_templates
        SET attachments = JSON_ARRAY(JSON_OBJECT(
            'path', attachment_path,
            'name', COALESCE(attachment_name, attachment_path)
        ))
        WHERE attachment_path IS NOT NULL
          AND attachment_path <> ''
          AND attachments IS NULL
    """)


def downgrade():
    with op.batch_alter_table('email_templates', schema=None) as batch_op:
        batch_op.drop_column('attachments')
