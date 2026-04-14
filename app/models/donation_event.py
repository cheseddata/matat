from datetime import datetime
from ..extensions import db


class DonationEvent(db.Model):
    """Audit trail for donation changes (ZTorm: TrumotEruim)."""
    __tablename__ = 'donation_events'

    id = db.Column(db.Integer, primary_key=True)
    donation_id = db.Column(db.Integer, db.ForeignKey('donations.id', ondelete='CASCADE'), nullable=False)
    payment_id = db.Column(db.Integer, db.ForeignKey('payments.id'), nullable=True)

    event_type = db.Column(db.String(50), nullable=False)  # erua: bitul/status_change/amount_change/etc.
    event_date = db.Column(db.Date, nullable=True)
    description = db.Column(db.Text, nullable=True)

    old_value = db.Column(db.String(255), nullable=True)
    new_value = db.Column(db.String(255), nullable=True)

    user = db.Column(db.String(50), nullable=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    def __repr__(self):
        return f'<DonationEvent {self.event_type} on donation {self.donation_id}>'
