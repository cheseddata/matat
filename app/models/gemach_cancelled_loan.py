"""Gemach Cancelled Loan archive (בטול הוראת קבע / Btlhork)."""
from datetime import datetime
from ..extensions import db


class GemachCancelledLoan(db.Model):
    """Archive of cancelled loans. Populated when a Hork is cancelled (status='b').

    Legacy table: Btlhork (8,027 rows).
    Kept as a separate audit table so the live gemach_loans stays clean.
    """
    __tablename__ = 'gemach_cancelled_loans'

    id = db.Column(db.Integer, primary_key=True)
    gmach_num_hork = db.Column(db.Integer, nullable=False, index=True)

    loan_id = db.Column(db.Integer, db.ForeignKey('gemach_loans.id', ondelete='SET NULL'),
                        nullable=True)

    start_date = db.Column(db.Date)
    currency = db.Column(db.String(3))
    amount = db.Column(db.Numeric(12, 2))
    committed_payments = db.Column(db.SmallInteger)
    payments_made = db.Column(db.SmallInteger)
    bounces = db.Column(db.SmallInteger)
    last_charge_date = db.Column(db.Date)
    asmachta = db.Column(db.Integer)

    cancellation_reason_code = db.Column(db.String(2))  # siba
    details = db.Column(db.String(50))  # pratim
    loan_type = db.Column(db.String(3))
    period_months = db.Column(db.SmallInteger)

    archived_at = db.Column(db.DateTime, default=datetime.utcnow)
