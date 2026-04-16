"""Gemach general Transaction (תנועה / Tnua) — non-loan transaction.

Covers deposits, donations, fees, expenses — anything not tied to a specific loan.
Legacy table: Tnuot in C:\\Gmach\\MttData.mdb (97,969 rows).
"""
from datetime import datetime
from ..extensions import db


class GemachTransaction(db.Model):
    __tablename__ = 'gemach_transactions'

    id = db.Column(db.Integer, primary_key=True)
    gmach_counter = db.Column(db.Integer, index=True)  # Legacy counter

    member_id = db.Column(db.Integer, db.ForeignKey('gemach_members.id', ondelete='RESTRICT'),
                          nullable=False, index=True)
    beneficiary_member_id = db.Column(db.Integer, db.ForeignKey('gemach_members.id'),
                                      nullable=True)  # num_zacai

    # Dates
    transaction_date = db.Column(db.Date, nullable=False, index=True)
    posting_date = db.Column(db.Date)   # date_peraon
    value_date = db.Column(db.Date)     # erech
    receipt_date = db.Column(db.Date)   # kabala_date

    # Classification
    deposit_or_withdraw = db.Column(db.String(1))  # tash
    category = db.Column(db.String(3), index=True)  # sug: הלו/פקד/תרו/תמי/הוצ

    # Amounts (dual currency tracking)
    amount_ils = db.Column(db.Numeric(12, 2))   # schum_sh
    amount_usd = db.Column(db.Numeric(12, 2))   # schum_$
    primary_currency = db.Column(db.String(3), default='ILS')  # matbea
    prior_amount_ils = db.Column(db.Numeric(12, 2))  # old_schum_nis

    # Description / payment method
    description = db.Column(db.String(50))   # pratim
    payment_method = db.Column(db.String(50))  # ofen

    # Bank details (if check or transfer)
    bank_code = db.Column(db.SmallInteger)
    branch_code = db.Column(db.Integer)
    account_number = db.Column(db.Integer)
    check_number = db.Column(db.Integer)

    # Receipt
    receipt_issued = db.Column(db.Boolean, default=False)  # kabala
    receipt_notes = db.Column(db.Text)  # heara_kabala

    # Flags
    organization_flag = db.Column(db.Boolean, default=False)  # amuta
    private_flag = db.Column(db.Boolean, default=False)       # private

    # References
    closure_ref = db.Column(db.Integer)   # num_sgira
    transfer_ref = db.Column(db.Integer)  # num_transfer

    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    # Relationships
    member = db.relationship('GemachMember', foreign_keys=[member_id],
                             backref=db.backref('transactions', lazy='dynamic'))
    beneficiary = db.relationship('GemachMember', foreign_keys=[beneficiary_member_id])

    def __repr__(self):
        return f'<GemachTransaction member={self.member_id} {self.category} {self.transaction_date}>'
