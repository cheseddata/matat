from datetime import datetime
from ..extensions import db


class Payment(db.Model):
    """Individual payments within a donation (ZTorm: Tashlumim)."""
    __tablename__ = 'payments'

    id = db.Column(db.Integer, primary_key=True)
    ztorm_tashlum_id = db.Column(db.Integer, nullable=True, index=True)

    donation_id = db.Column(db.Integer, db.ForeignKey('donations.id', ondelete='CASCADE'), nullable=False)
    receipt_id = db.Column(db.Integer, db.ForeignKey('receipts.id'), nullable=True)
    batch_id = db.Column(db.Integer, db.ForeignKey('collection_batches.id'), nullable=True)

    # Financial
    amount = db.Column(db.Numeric(12, 2), nullable=False)  # schum (full currency, not cents)
    currency = db.Column(db.String(10), default='ILS')  # matbea
    amount_nis = db.Column(db.Numeric(12, 2), nullable=True)  # schum_nis
    usd_equivalent = db.Column(db.Numeric(12, 2), nullable=True)  # shovi

    # Dates
    payment_date = db.Column(db.Date, nullable=True)  # date
    value_date = db.Column(db.Date, nullable=True)  # erech
    authorization_date = db.Column(db.Date, nullable=True)  # date_ishur

    # Status and method
    status = db.Column(db.String(20), default='ready')  # ok/ready/returned/paid (hazar/shulam)
    method = db.Column(db.String(20), nullable=True)  # credit/hork/cash/check/hafkada
    reference = db.Column(db.String(100), nullable=True)  # asmachta
    reason = db.Column(db.String(255), nullable=True)  # siba

    # Check details
    check_bank = db.Column(db.Integer, nullable=True)  # bank
    check_branch = db.Column(db.Integer, nullable=True)  # snif
    check_account = db.Column(db.String(20), nullable=True)  # heshbon
    check_number = db.Column(db.String(20), nullable=True)  # mispar

    # Authorization
    authorization_number = db.Column(db.String(50), nullable=True)  # num_ishur
    error_code = db.Column(db.String(50), nullable=True)  # err_code

    # Credit status for accounting
    credit_status = db.Column(db.String(20), nullable=True)  # status_zicui

    # Classification
    classification_1 = db.Column(db.String(100), nullable=True)
    classification_2 = db.Column(db.String(100), nullable=True)

    notes = db.Column(db.Text, nullable=True)  # pratim

    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    @property
    def currency_symbol(self):
        symbols = {'ILS': '₪', 'USD': '$', 'EUR': '€'}
        return symbols.get(self.currency.upper() if self.currency else 'ILS', '')

    @property
    def status_display(self):
        status_map = {
            'ok': 'Paid ✓', 'ready': 'Pending', 'returned': 'Returned ✗',
            'paid': 'Paid ✓', 'hazar': 'Returned ✗'
        }
        return status_map.get(self.status, self.status)

    def __repr__(self):
        return f'<Payment {self.id} {self.currency_symbol}{self.amount}>'
