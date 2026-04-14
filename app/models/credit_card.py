from datetime import datetime
from ..extensions import db


class CreditCardRecurring(db.Model):
    """Recurring credit card setup (ZTorm: CreditP)."""
    __tablename__ = 'credit_card_recurring'

    id = db.Column(db.Integer, primary_key=True)
    donation_id = db.Column(db.Integer, db.ForeignKey('donations.id', ondelete='CASCADE'), nullable=False, unique=True)

    card_last4 = db.Column(db.String(4), nullable=True)  # mispar_cartis
    card_expiry = db.Column(db.String(4), nullable=True)  # tokef (YYMM)
    card_brand = db.Column(db.String(50), nullable=True)  # shem_cartis
    card_company_code = db.Column(db.Integer, nullable=True)  # code_hevra
    clearing_house = db.Column(db.Integer, nullable=True)  # solek

    amount = db.Column(db.Numeric(12, 2), nullable=True)  # schum
    currency = db.Column(db.String(10), default='ILS')
    total_charges = db.Column(db.Integer, nullable=True)  # peimot
    current_count = db.Column(db.Integer, default=0)  # buza
    collection_day = db.Column(db.Integer, nullable=True)  # yom

    holder_tz = db.Column(db.String(9), nullable=True)  # t_z
    is_donor_card = db.Column(db.Boolean, default=True)  # shel_torem
    has_signature = db.Column(db.Boolean, default=False)  # chatima
    terminal_id = db.Column(db.Integer, nullable=True)  # num_masof
    end_date = db.Column(db.Date, nullable=True)  # date_limit
    limit_to_month = db.Column(db.Boolean, default=True)

    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)


class CreditCardCharge(db.Model):
    """Individual credit card charges (ZTorm: CreditCards)."""
    __tablename__ = 'credit_card_charges'

    id = db.Column(db.Integer, primary_key=True)
    donation_id = db.Column(db.Integer, db.ForeignKey('donations.id', ondelete='CASCADE'), nullable=False)
    batch_id = db.Column(db.Integer, db.ForeignKey('collection_batches.id'), nullable=True)

    execution_date = db.Column(db.Date, nullable=True)  # date_bitzua
    amount = db.Column(db.Numeric(12, 2), nullable=True)  # schum
    currency = db.Column(db.String(10), default='ILS')
    card_last4 = db.Column(db.String(4), nullable=True)
    card_expiry = db.Column(db.String(4), nullable=True)
    card_brand = db.Column(db.String(50), nullable=True)

    transaction_type = db.Column(db.String(20), nullable=True)  # sug_iska
    company_code = db.Column(db.Integer, nullable=True)  # code_hevra
    authorization_number = db.Column(db.String(50), nullable=True)  # num_ishur
    collection_method = db.Column(db.String(20), nullable=True)  # ofen_gvia: online/offline
    error_code = db.Column(db.String(50), nullable=True)

    status = db.Column(db.String(20), default='pending')
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
