from datetime import datetime
from ..extensions import db


class Account(db.Model):
    """Ledger accounts (ZTorm: Heshbonot)."""
    __tablename__ = 'accounts'

    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(200), nullable=False)
    account_type = db.Column(db.String(50), nullable=True)  # sug
    donor_id = db.Column(db.Integer, db.ForeignKey('donors.id'), nullable=True)
    fixed_percentage = db.Column(db.Numeric(5, 2), nullable=True)  # ahuz_kavua
    notes = db.Column(db.Text, nullable=True)
    is_active = db.Column(db.Boolean, default=True)

    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    allocations = db.relationship('AccountAllocation', backref='account', lazy='dynamic')
    credits = db.relationship('AccountingCredit', backref='account', lazy='dynamic')


class AccountAllocation(db.Model):
    """Per-donation allocation rules (ZTorm: Zacaim)."""
    __tablename__ = 'account_allocations'

    id = db.Column(db.Integer, primary_key=True)
    donation_id = db.Column(db.Integer, db.ForeignKey('donations.id', ondelete='CASCADE'), nullable=False)
    account_id = db.Column(db.Integer, db.ForeignKey('accounts.id'), nullable=False)

    percentage = db.Column(db.Numeric(5, 2), nullable=True)  # ahuz
    is_active = db.Column(db.Boolean, default=True)  # pail
    base_amount = db.Column(db.Numeric(12, 2), nullable=True)  # schum_basis
    base_date = db.Column(db.Date, nullable=True)  # date_basis

    entry_date = db.Column(db.Date, nullable=True)  # date_klita
    created_at = db.Column(db.DateTime, default=datetime.utcnow)


class AccountingCredit(db.Model):
    """Accounting credit/debit entries (ZTorm: Zicuim)."""
    __tablename__ = 'accounting_credits'

    id = db.Column(db.Integer, primary_key=True)
    account_id = db.Column(db.Integer, db.ForeignKey('accounts.id'), nullable=False)
    payment_id = db.Column(db.Integer, db.ForeignKey('payments.id'), nullable=True)
    donation_id = db.Column(db.Integer, db.ForeignKey('donations.id'), nullable=True)

    entry_date = db.Column(db.Date, nullable=True)
    value_date = db.Column(db.Date, nullable=True)
    amount = db.Column(db.Numeric(12, 2), nullable=False)
    currency = db.Column(db.String(10), default='ILS')
    entry_type = db.Column(db.String(20), nullable=True)  # sug: zicui/amala/fix
    sub_type = db.Column(db.String(20), nullable=True)
    details = db.Column(db.Text, nullable=True)
    user = db.Column(db.String(50), nullable=True)

    created_at = db.Column(db.DateTime, default=datetime.utcnow)
