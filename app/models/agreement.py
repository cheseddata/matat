from datetime import datetime
from ..extensions import db


class Agreement(db.Model):
    """Fundraising agreements (ZTorm: Hescemim)."""
    __tablename__ = 'agreements'

    id = db.Column(db.Integer, primary_key=True)
    ztorm_hescem_id = db.Column(db.Integer, nullable=True, index=True)  # Original num_hescem

    donor_id = db.Column(db.Integer, db.ForeignKey('donors.id'), nullable=True)  # Contact donor
    department_id = db.Column(db.Integer, nullable=True)  # num_mahlaka

    agreement_type = db.Column(db.String(50), nullable=True)  # sug: clali, matbeot, nziv, etc.
    sub_type = db.Column(db.String(50), nullable=True)  # tat_sug
    currency = db.Column(db.String(10), default='ILS')  # matbea
    total_amount = db.Column(db.Numeric(12, 2), nullable=True)  # sach_ltashlum
    paid_amount = db.Column(db.Numeric(12, 2), default=0)  # SumOfShulam
    expected_amount = db.Column(db.Numeric(12, 2), default=0)  # SumOfTzafui
    expected_unlimited = db.Column(db.Numeric(12, 2), default=0)  # SumOfTzafui_Unlimited

    is_cancelled = db.Column(db.Boolean, default=False)  # mvutal
    is_hidden = db.Column(db.Boolean, default=False)  # hitalem
    notes = db.Column(db.Text, nullable=True)  # hearot
    certificate_name = db.Column(db.String(200), nullable=True)  # shem_teuda

    # Self-referencing for agreement chains
    target_agreement_id = db.Column(db.Integer, db.ForeignKey('agreements.id'), nullable=True)
    continuation_agreement_id = db.Column(db.Integer, nullable=True)

    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    # Relationships
    # donations relationship defined via Donation.agreement_id (no FK constraint yet)
    # donor relationship via donor_id

    def recalculate(self):
        """Recalculate paid/expected amounts from linked donations."""
        from .donation import Donation
        donations = Donation.query.filter_by(agreement_id=self.id).filter(Donation.deleted_at.is_(None)).all()
        paid = sum(float(d.paid_nis or 0) for d in donations)
        expected = sum(float(d.expected_nis or 0) for d in donations)
        self.paid_amount = paid
        self.expected_amount = expected

    def __repr__(self):
        return f'<Agreement {self.id} type={self.agreement_type}>'
