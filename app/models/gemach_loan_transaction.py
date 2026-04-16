"""Gemach Loan Transaction (פעולה / Peula) — one payment attempt on a loan."""
from datetime import datetime
from ..extensions import db


class GemachLoanTransaction(db.Model):
    """Individual payment record against a Gemach loan.

    Legacy table: Peulot in C:\\Gmach\\MttData.mdb (133,847 rows as of April 2026).
    """
    __tablename__ = 'gemach_loan_transactions'

    id = db.Column(db.Integer, primary_key=True)
    gmach_counter = db.Column(db.Integer, index=True)  # Legacy auto-increment key

    loan_id = db.Column(db.Integer, db.ForeignKey('gemach_loans.id', ondelete='CASCADE'),
                        nullable=False, index=True)

    # Optional: beneficiary override (num_zacai in Access)
    beneficiary_member_id = db.Column(db.Integer, db.ForeignKey('gemach_members.id'),
                                      nullable=True)

    transaction_date = db.Column(db.Date, nullable=False, index=True)
    asmachta = db.Column(db.Integer)  # Bank reference

    amount_ils = db.Column(db.Numeric(12, 2))   # schum (primary)
    amount_usd = db.Column(db.Numeric(12, 2))   # schum_d

    bounced = db.Column(db.Boolean, default=False, index=True)  # hazar
    bounce_reason = db.Column(db.String(2))  # siba (FK to reason lookup)

    loan_type = db.Column(db.String(3))  # sug
    receipt_issued = db.Column(db.Boolean, default=False)  # kabala
    transfer_ref = db.Column(db.Integer)  # num_transfer

    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    def __repr__(self):
        return f'<GemachLoanTransaction loan={self.loan_id} date={self.transaction_date} hazar={self.bounced}>'
