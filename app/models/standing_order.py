from datetime import datetime
from ..extensions import db


class StandingOrder(db.Model):
    """Bank standing orders / direct debit (ZTorm: Hork)."""
    __tablename__ = 'standing_orders'

    id = db.Column(db.Integer, primary_key=True)
    donation_id = db.Column(db.Integer, db.ForeignKey('donations.id', ondelete='CASCADE'), nullable=False, unique=True)

    # Bank details
    bank_code = db.Column(db.Integer, nullable=True)  # bank
    branch_code = db.Column(db.Integer, nullable=True)  # snif
    account_number = db.Column(db.String(20), nullable=True)  # heshbon
    account_name = db.Column(db.String(200), nullable=True)  # shem_heshbon

    # Payment setup
    amount = db.Column(db.Numeric(12, 2), nullable=True)  # schum
    currency = db.Column(db.String(10), default='ILS')  # matbea
    total_payments = db.Column(db.Integer, nullable=True)  # peimot (null=unlimited)
    current_count = db.Column(db.Integer, default=0)  # buza
    collection_day = db.Column(db.Integer, nullable=True)  # yom (day of month)
    period_months = db.Column(db.Integer, default=1)  # tkufa

    # Institution
    institution_id = db.Column(db.Integer, nullable=True)  # num_mosad
    reference = db.Column(db.String(100), nullable=True)  # asmachta

    # Status
    end_date = db.Column(db.Date, nullable=True)  # date_limit
    is_manual_split = db.Column(db.Boolean, default=False)  # prisa_yadanit
    authorization_cancelled = db.Column(db.Boolean, default=False)  # butal_harshaa
    received_confirmation = db.Column(db.Boolean, default=False)  # nitkabel_sefah
    confirmation_date = db.Column(db.Date, nullable=True)  # date_sefah

    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    def __repr__(self):
        return f'<StandingOrder {self.id} bank={self.bank_code}/{self.branch_code}>'
