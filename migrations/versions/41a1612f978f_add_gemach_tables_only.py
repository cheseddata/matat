"""Add Gemach tables only

Revision ID: 41a1612f978f
Revises: 7b2c24b2be46
Create Date: 2026-04-16 21:41:18.798611

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = '41a1612f978f'
down_revision = '7b2c24b2be46'
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        'gemach_cancellation_reasons',
        sa.Column('code', sa.String(length=2), nullable=False),
        sa.Column('name', sa.String(length=255), nullable=False),
        sa.Column('triggers_cancellation', sa.Boolean(), nullable=True),
        sa.PrimaryKeyConstraint('code'),
    )
    op.create_table(
        'gemach_hash_accounts',
        sa.Column('account_no', sa.Integer(), nullable=False),
        sa.Column('name', sa.String(length=50), nullable=False),
        sa.Column('description', sa.String(length=50), nullable=True),
        sa.PrimaryKeyConstraint('account_no'),
    )
    op.create_table(
        'gemach_institutions',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('gmach_num_mosad', sa.SmallInteger(), nullable=False),
        sa.Column('name', sa.String(length=50), nullable=False),
        sa.Column('code', sa.String(length=20), nullable=True),
        sa.Column('active', sa.Boolean(), nullable=True),
        sa.Column('created_at', sa.DateTime(), nullable=True),
        sa.PrimaryKeyConstraint('id'),
    )
    with op.batch_alter_table('gemach_institutions', schema=None) as batch_op:
        batch_op.create_index(
            batch_op.f('ix_gemach_institutions_gmach_num_mosad'),
            ['gmach_num_mosad'],
            unique=True,
        )

    op.create_table(
        'gemach_setup',
        sa.Column('key', sa.String(length=50), nullable=False),
        sa.Column('value', sa.String(length=255), nullable=True),
        sa.Column('description', sa.String(length=50), nullable=True),
        sa.PrimaryKeyConstraint('key'),
    )
    op.create_table(
        'gemach_transaction_types',
        sa.Column('code', sa.String(length=3), nullable=False),
        sa.Column('description', sa.String(length=50), nullable=False),
        sa.PrimaryKeyConstraint('code'),
    )
    op.create_table(
        'gemach_members',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('gmach_card_no', sa.Integer(), nullable=False),
        sa.Column('donor_id', sa.Integer(), nullable=True),
        sa.Column('ztorm_donor_id', sa.Integer(), nullable=True),
        sa.Column('last_name', sa.String(length=255), nullable=True),
        sa.Column('first_name', sa.String(length=255), nullable=True),
        sa.Column('title', sa.String(length=12), nullable=True),
        sa.Column('suffix', sa.String(length=20), nullable=True),
        sa.Column('teudat_zehut', sa.String(length=9), nullable=True),
        sa.Column('member_type', sa.String(length=5), nullable=True),
        sa.Column('address', sa.String(length=70), nullable=True),
        sa.Column('city', sa.String(length=25), nullable=True),
        sa.Column('zip_code', sa.String(length=10), nullable=True),
        sa.Column('phone', sa.String(length=15), nullable=True),
        sa.Column('phone_area', sa.String(length=3), nullable=True),
        sa.Column('phone2', sa.String(length=15), nullable=True),
        sa.Column('phone2_area', sa.String(length=3), nullable=True),
        sa.Column('fax', sa.String(length=15), nullable=True),
        sa.Column('fax_area', sa.String(length=3), nullable=True),
        sa.Column('address2_type', sa.String(length=7), nullable=True),
        sa.Column('address2_name', sa.String(length=30), nullable=True),
        sa.Column('address2', sa.String(length=70), nullable=True),
        sa.Column('city2', sa.String(length=25), nullable=True),
        sa.Column('zip_code2', sa.String(length=10), nullable=True),
        sa.Column('phone2_secondary', sa.String(length=15), nullable=True),
        sa.Column('phone2_secondary_area', sa.String(length=3), nullable=True),
        sa.Column('fax2', sa.String(length=15), nullable=True),
        sa.Column('fax2_area', sa.String(length=3), nullable=True),
        sa.Column('mail_address', sa.SmallInteger(), nullable=True),
        sa.Column('tag1', sa.String(length=5), nullable=True),
        sa.Column('tag2', sa.String(length=5), nullable=True),
        sa.Column('tag3', sa.String(length=5), nullable=True),
        sa.Column('tag4', sa.String(length=5), nullable=True),
        sa.Column('tag5', sa.String(length=5), nullable=True),
        sa.Column('bookmark', sa.Boolean(), nullable=True),
        sa.Column('english_receipt', sa.Boolean(), nullable=True),
        sa.Column('registration_date', sa.Date(), nullable=True),
        sa.Column('last_reconciliation', sa.Date(), nullable=True),
        sa.Column('notes', sa.Text(), nullable=True),
        sa.Column('created_at', sa.DateTime(), nullable=True),
        sa.Column('updated_at', sa.DateTime(), nullable=True),
        sa.ForeignKeyConstraint(['donor_id'], ['donors.id'], ondelete='SET NULL'),
        sa.PrimaryKeyConstraint('id'),
    )
    with op.batch_alter_table('gemach_members', schema=None) as batch_op:
        batch_op.create_index(
            batch_op.f('ix_gemach_members_donor_id'), ['donor_id'], unique=False
        )
        batch_op.create_index(
            batch_op.f('ix_gemach_members_gmach_card_no'), ['gmach_card_no'], unique=True
        )
        batch_op.create_index(
            batch_op.f('ix_gemach_members_ztorm_donor_id'),
            ['ztorm_donor_id'],
            unique=False,
        )

    op.create_table(
        'gemach_loans',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('gmach_num_hork', sa.Integer(), nullable=False),
        sa.Column('member_id', sa.Integer(), nullable=False),
        sa.Column('beneficiary_member_id', sa.Integer(), nullable=True),
        sa.Column('institution_id', sa.Integer(), nullable=True),
        sa.Column('status', sa.String(length=1), nullable=False),
        sa.Column('currency', sa.String(length=3), nullable=True),
        sa.Column('amount', sa.Numeric(precision=12, scale=2), nullable=False),
        sa.Column('start_date', sa.Date(), nullable=True),
        sa.Column('last_charge_date', sa.Date(), nullable=True),
        sa.Column('global_start_date', sa.Date(), nullable=True),
        sa.Column('charge_day', sa.SmallInteger(), nullable=True),
        sa.Column('period_months', sa.SmallInteger(), nullable=True),
        sa.Column('committed_payments', sa.SmallInteger(), nullable=True),
        sa.Column('payments_made', sa.SmallInteger(), nullable=True),
        sa.Column('total_expected', sa.SmallInteger(), nullable=True),
        sa.Column('bounces', sa.SmallInteger(), nullable=True),
        sa.Column('amount_paid', sa.Numeric(precision=12, scale=2), nullable=True),
        sa.Column('loan_type', sa.String(length=3), nullable=True),
        sa.Column('bank_code', sa.SmallInteger(), nullable=True),
        sa.Column('branch_code', sa.SmallInteger(), nullable=True),
        sa.Column('account_number', sa.String(length=20), nullable=True),
        sa.Column('asmachta', sa.Integer(), nullable=True),
        sa.Column('separate_collection', sa.Boolean(), nullable=True),
        sa.Column('sent_to_collection', sa.Boolean(), nullable=True),
        sa.Column('limited_collection', sa.Boolean(), nullable=True),
        sa.Column('cancellation_reason_code', sa.String(length=2), nullable=True),
        sa.Column('notes', sa.Text(), nullable=True),
        sa.Column('created_at', sa.DateTime(), nullable=True),
        sa.Column('updated_at', sa.DateTime(), nullable=True),
        sa.ForeignKeyConstraint(['beneficiary_member_id'], ['gemach_members.id']),
        sa.ForeignKeyConstraint(['institution_id'], ['gemach_institutions.id']),
        sa.ForeignKeyConstraint(['member_id'], ['gemach_members.id'], ondelete='RESTRICT'),
        sa.PrimaryKeyConstraint('id'),
    )
    with op.batch_alter_table('gemach_loans', schema=None) as batch_op:
        batch_op.create_index(
            batch_op.f('ix_gemach_loans_asmachta'), ['asmachta'], unique=False
        )
        batch_op.create_index(
            batch_op.f('ix_gemach_loans_gmach_num_hork'), ['gmach_num_hork'], unique=True
        )
        batch_op.create_index(
            batch_op.f('ix_gemach_loans_member_id'), ['member_id'], unique=False
        )
        batch_op.create_index(
            batch_op.f('ix_gemach_loans_status'), ['status'], unique=False
        )

    op.create_table(
        'gemach_memorials',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('gmach_id', sa.Integer(), nullable=True),
        sa.Column('sponsor_member_id', sa.Integer(), nullable=False),
        sa.Column('deceased_name', sa.String(length=100), nullable=True),
        sa.Column('hebrew_day', sa.SmallInteger(), nullable=True),
        sa.Column('hebrew_month', sa.String(length=10), nullable=True),
        sa.Column('hebrew_year', sa.SmallInteger(), nullable=True),
        sa.Column('active', sa.Boolean(), nullable=True),
        sa.Column('kaddish_end_date', sa.Date(), nullable=True),
        sa.Column('registration_date', sa.Date(), nullable=True),
        sa.Column('yahrzeit_printed', sa.Boolean(), nullable=True),
        sa.Column('kaddish_printed', sa.Boolean(), nullable=True),
        sa.Column('notes', sa.Text(), nullable=True),
        sa.Column('created_at', sa.DateTime(), nullable=True),
        sa.ForeignKeyConstraint(
            ['sponsor_member_id'], ['gemach_members.id'], ondelete='CASCADE'
        ),
        sa.PrimaryKeyConstraint('id'),
    )
    with op.batch_alter_table('gemach_memorials', schema=None) as batch_op:
        batch_op.create_index(
            batch_op.f('ix_gemach_memorials_gmach_id'), ['gmach_id'], unique=False
        )
        batch_op.create_index(
            batch_op.f('ix_gemach_memorials_sponsor_member_id'),
            ['sponsor_member_id'],
            unique=False,
        )

    op.create_table(
        'gemach_transactions',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('gmach_counter', sa.Integer(), nullable=True),
        sa.Column('member_id', sa.Integer(), nullable=False),
        sa.Column('beneficiary_member_id', sa.Integer(), nullable=True),
        sa.Column('transaction_date', sa.Date(), nullable=False),
        sa.Column('posting_date', sa.Date(), nullable=True),
        sa.Column('value_date', sa.Date(), nullable=True),
        sa.Column('receipt_date', sa.Date(), nullable=True),
        sa.Column('deposit_or_withdraw', sa.String(length=1), nullable=True),
        sa.Column('category', sa.String(length=3), nullable=True),
        sa.Column('amount_ils', sa.Numeric(precision=12, scale=2), nullable=True),
        sa.Column('amount_usd', sa.Numeric(precision=12, scale=2), nullable=True),
        sa.Column('primary_currency', sa.String(length=3), nullable=True),
        sa.Column('prior_amount_ils', sa.Numeric(precision=12, scale=2), nullable=True),
        sa.Column('description', sa.String(length=50), nullable=True),
        sa.Column('payment_method', sa.String(length=50), nullable=True),
        sa.Column('bank_code', sa.SmallInteger(), nullable=True),
        sa.Column('branch_code', sa.Integer(), nullable=True),
        sa.Column('account_number', sa.Integer(), nullable=True),
        sa.Column('check_number', sa.Integer(), nullable=True),
        sa.Column('receipt_issued', sa.Boolean(), nullable=True),
        sa.Column('receipt_notes', sa.Text(), nullable=True),
        sa.Column('organization_flag', sa.Boolean(), nullable=True),
        sa.Column('private_flag', sa.Boolean(), nullable=True),
        sa.Column('closure_ref', sa.Integer(), nullable=True),
        sa.Column('transfer_ref', sa.Integer(), nullable=True),
        sa.Column('created_at', sa.DateTime(), nullable=True),
        sa.Column('updated_at', sa.DateTime(), nullable=True),
        sa.ForeignKeyConstraint(['beneficiary_member_id'], ['gemach_members.id']),
        sa.ForeignKeyConstraint(['member_id'], ['gemach_members.id'], ondelete='RESTRICT'),
        sa.PrimaryKeyConstraint('id'),
    )
    with op.batch_alter_table('gemach_transactions', schema=None) as batch_op:
        batch_op.create_index(
            batch_op.f('ix_gemach_transactions_category'), ['category'], unique=False
        )
        batch_op.create_index(
            batch_op.f('ix_gemach_transactions_gmach_counter'),
            ['gmach_counter'],
            unique=False,
        )
        batch_op.create_index(
            batch_op.f('ix_gemach_transactions_member_id'), ['member_id'], unique=False
        )
        batch_op.create_index(
            batch_op.f('ix_gemach_transactions_transaction_date'),
            ['transaction_date'],
            unique=False,
        )

    op.create_table(
        'gemach_cancelled_loans',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('gmach_num_hork', sa.Integer(), nullable=False),
        sa.Column('loan_id', sa.Integer(), nullable=True),
        sa.Column('start_date', sa.Date(), nullable=True),
        sa.Column('currency', sa.String(length=3), nullable=True),
        sa.Column('amount', sa.Numeric(precision=12, scale=2), nullable=True),
        sa.Column('committed_payments', sa.SmallInteger(), nullable=True),
        sa.Column('payments_made', sa.SmallInteger(), nullable=True),
        sa.Column('bounces', sa.SmallInteger(), nullable=True),
        sa.Column('last_charge_date', sa.Date(), nullable=True),
        sa.Column('asmachta', sa.Integer(), nullable=True),
        sa.Column('cancellation_reason_code', sa.String(length=2), nullable=True),
        sa.Column('details', sa.String(length=50), nullable=True),
        sa.Column('loan_type', sa.String(length=3), nullable=True),
        sa.Column('period_months', sa.SmallInteger(), nullable=True),
        sa.Column('archived_at', sa.DateTime(), nullable=True),
        sa.ForeignKeyConstraint(['loan_id'], ['gemach_loans.id'], ondelete='SET NULL'),
        sa.PrimaryKeyConstraint('id'),
    )
    with op.batch_alter_table('gemach_cancelled_loans', schema=None) as batch_op:
        batch_op.create_index(
            batch_op.f('ix_gemach_cancelled_loans_gmach_num_hork'),
            ['gmach_num_hork'],
            unique=False,
        )

    op.create_table(
        'gemach_loan_transactions',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('gmach_counter', sa.Integer(), nullable=True),
        sa.Column('loan_id', sa.Integer(), nullable=False),
        sa.Column('beneficiary_member_id', sa.Integer(), nullable=True),
        sa.Column('transaction_date', sa.Date(), nullable=False),
        sa.Column('asmachta', sa.Integer(), nullable=True),
        sa.Column('amount_ils', sa.Numeric(precision=12, scale=2), nullable=True),
        sa.Column('amount_usd', sa.Numeric(precision=12, scale=2), nullable=True),
        sa.Column('bounced', sa.Boolean(), nullable=True),
        sa.Column('bounce_reason', sa.String(length=2), nullable=True),
        sa.Column('loan_type', sa.String(length=3), nullable=True),
        sa.Column('receipt_issued', sa.Boolean(), nullable=True),
        sa.Column('transfer_ref', sa.Integer(), nullable=True),
        sa.Column('created_at', sa.DateTime(), nullable=True),
        sa.ForeignKeyConstraint(['beneficiary_member_id'], ['gemach_members.id']),
        sa.ForeignKeyConstraint(['loan_id'], ['gemach_loans.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id'),
    )
    with op.batch_alter_table('gemach_loan_transactions', schema=None) as batch_op:
        batch_op.create_index(
            batch_op.f('ix_gemach_loan_transactions_bounced'), ['bounced'], unique=False
        )
        batch_op.create_index(
            batch_op.f('ix_gemach_loan_transactions_gmach_counter'),
            ['gmach_counter'],
            unique=False,
        )
        batch_op.create_index(
            batch_op.f('ix_gemach_loan_transactions_loan_id'), ['loan_id'], unique=False
        )
        batch_op.create_index(
            batch_op.f('ix_gemach_loan_transactions_transaction_date'),
            ['transaction_date'],
            unique=False,
        )


def downgrade():
    with op.batch_alter_table('gemach_loan_transactions', schema=None) as batch_op:
        batch_op.drop_index(batch_op.f('ix_gemach_loan_transactions_transaction_date'))
        batch_op.drop_index(batch_op.f('ix_gemach_loan_transactions_loan_id'))
        batch_op.drop_index(batch_op.f('ix_gemach_loan_transactions_gmach_counter'))
        batch_op.drop_index(batch_op.f('ix_gemach_loan_transactions_bounced'))

    op.drop_table('gemach_loan_transactions')

    with op.batch_alter_table('gemach_cancelled_loans', schema=None) as batch_op:
        batch_op.drop_index(batch_op.f('ix_gemach_cancelled_loans_gmach_num_hork'))

    op.drop_table('gemach_cancelled_loans')

    with op.batch_alter_table('gemach_transactions', schema=None) as batch_op:
        batch_op.drop_index(batch_op.f('ix_gemach_transactions_transaction_date'))
        batch_op.drop_index(batch_op.f('ix_gemach_transactions_member_id'))
        batch_op.drop_index(batch_op.f('ix_gemach_transactions_gmach_counter'))
        batch_op.drop_index(batch_op.f('ix_gemach_transactions_category'))

    op.drop_table('gemach_transactions')

    with op.batch_alter_table('gemach_memorials', schema=None) as batch_op:
        batch_op.drop_index(batch_op.f('ix_gemach_memorials_sponsor_member_id'))
        batch_op.drop_index(batch_op.f('ix_gemach_memorials_gmach_id'))

    op.drop_table('gemach_memorials')

    with op.batch_alter_table('gemach_loans', schema=None) as batch_op:
        batch_op.drop_index(batch_op.f('ix_gemach_loans_status'))
        batch_op.drop_index(batch_op.f('ix_gemach_loans_member_id'))
        batch_op.drop_index(batch_op.f('ix_gemach_loans_gmach_num_hork'))
        batch_op.drop_index(batch_op.f('ix_gemach_loans_asmachta'))

    op.drop_table('gemach_loans')

    with op.batch_alter_table('gemach_members', schema=None) as batch_op:
        batch_op.drop_index(batch_op.f('ix_gemach_members_ztorm_donor_id'))
        batch_op.drop_index(batch_op.f('ix_gemach_members_gmach_card_no'))
        batch_op.drop_index(batch_op.f('ix_gemach_members_donor_id'))

    op.drop_table('gemach_members')

    op.drop_table('gemach_transaction_types')
    op.drop_table('gemach_setup')

    with op.batch_alter_table('gemach_institutions', schema=None) as batch_op:
        batch_op.drop_index(batch_op.f('ix_gemach_institutions_gmach_num_mosad'))

    op.drop_table('gemach_institutions')
    op.drop_table('gemach_hash_accounts')
    op.drop_table('gemach_cancellation_reasons')
