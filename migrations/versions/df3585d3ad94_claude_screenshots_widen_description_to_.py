"""claude_screenshots: widen description to TEXT

Revision ID: df3585d3ad94
Revises: fdee9aaa77a8
Create Date: 2026-04-30 12:25:10.654863

"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import mysql

# revision identifiers, used by Alembic.
revision = 'df3585d3ad94'
down_revision = 'fdee9aaa77a8'
branch_labels = None
depends_on = None


def upgrade():
    with op.batch_alter_table('claude_screenshots', schema=None) as batch_op:
        batch_op.alter_column('description',
               existing_type=mysql.VARCHAR(charset='utf8mb4', collation='utf8mb4_unicode_ci', length=255),
               type_=sa.Text(),
               existing_nullable=True)


def downgrade():
    with op.batch_alter_table('claude_screenshots', schema=None) as batch_op:
        batch_op.alter_column('description',
               existing_type=sa.Text(),
               type_=mysql.VARCHAR(charset='utf8mb4', collation='utf8mb4_unicode_ci', length=255),
               existing_nullable=True)
