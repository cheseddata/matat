"""Gemach Loan (הוראת קבע / Hork) — standing-order loan from the fund."""
from datetime import datetime
from ..extensions import db


class GemachLoan(db.Model):
    """A loan disbursed to a member with a standing order for repayment.

    Legacy table: Hork in C:\\Gmach\\MttData.mdb.
    One row per loan. Once cancelled, a copy lives in gemach_cancelled_loans.
    """
    __tablename__ = 'gemach_loans'

    id = db.Column(db.Integer, primary_key=True)
    gmach_num_hork = db.Column(db.Integer, unique=True, nullable=False, index=True)

    member_id = db.Column(db.Integer, db.ForeignKey('gemach_members.id', ondelete='RESTRICT'),
                          nullable=False, index=True)
    beneficiary_member_id = db.Column(db.Integer, db.ForeignKey('gemach_members.id'),
                                      nullable=True)  # num_zacai (0 = same as borrower)

    institution_id = db.Column(db.Integer, db.ForeignKey('gemach_institutions.id'),
                               nullable=True)

    # Status: p=pending/active, s=satisfied, b=bitul (cancelled)
    status = db.Column(db.String(1), default='p', nullable=False, index=True)

    # Money
    currency = db.Column(db.String(3), default='ILS')  # ILS or USD
    amount = db.Column(db.Numeric(12, 2), nullable=False)

    # Schedule
    start_date = db.Column(db.Date)              # date_hathala
    last_charge_date = db.Column(db.Date)         # date_hiuv_aharon
    global_start_date = db.Column(db.Date)        # date_hathala_clali

    charge_day = db.Column(db.SmallInteger)       # yom (day of month)
    period_months = db.Column(db.SmallInteger, default=1)  # tkufa

    # Payment tracking
    committed_payments = db.Column(db.SmallInteger)  # hithayev (999 = unlimited)
    payments_made = db.Column(db.SmallInteger, default=0)  # buza
    total_expected = db.Column(db.SmallInteger)   # sach_buza
    bounces = db.Column(db.SmallInteger, default=0)  # hazar
    amount_paid = db.Column(db.Numeric(12, 2), default=0)  # shulam (cumulative)

    # Loan type: הלו=loan, תרו=donation, פקד=deposit, תמי=support, הוצ=expense
    loan_type = db.Column(db.String(3))           # sug

    # Bank details for direct debit
    bank_code = db.Column(db.SmallInteger)
    branch_code = db.Column(db.SmallInteger)
    account_number = db.Column(db.String(20))
    asmachta = db.Column(db.Integer, index=True)

    # Collection flags
    separate_collection = db.Column(db.Boolean, default=False)   # gvia_nifredet
    sent_to_collection = db.Column(db.Boolean, default=False)    # nishlach_harsha
    limited_collection = db.Column(db.Boolean, default=False)    # harsha_mugbelet

    # Cancellation
    cancellation_reason_code = db.Column(db.String(2))  # sibat_bitul (FK to reasons lookup)

    # Notes
    notes = db.Column(db.Text)                    # heara

    # Audit
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    # Relationships
    member = db.relationship('GemachMember', foreign_keys=[member_id],
                             backref=db.backref('loans', lazy='dynamic'))
    beneficiary = db.relationship('GemachMember', foreign_keys=[beneficiary_member_id])
    institution = db.relationship('GemachInstitution', backref='loans')
    transactions = db.relationship('GemachLoanTransaction', backref='loan',
                                   lazy='dynamic', cascade='all, delete-orphan')

    @property
    def is_active(self):
        return self.status == 'p'

    @property
    def is_cancelled(self):
        return self.status == 'b'

    @property
    def is_satisfied(self):
        return self.status == 's'

    @property
    def remaining_payments(self):
        if self.committed_payments is None or self.committed_payments == 999:
            return None  # unlimited
        return max(0, self.committed_payments - (self.payments_made or 0))

    def __repr__(self):
        return f'<GemachLoan #{self.gmach_num_hork} member={self.member_id} status={self.status}>'
