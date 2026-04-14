from datetime import datetime
from ..extensions import db


class Address(db.Model):
    """Multiple addresses per donor (ZTorm: Ctovot)."""
    __tablename__ = 'addresses'

    id = db.Column(db.Integer, primary_key=True)
    donor_id = db.Column(db.Integer, db.ForeignKey('donors.id', ondelete='CASCADE'), nullable=False)

    sequence = db.Column(db.Integer, default=1)  # num_siduri
    is_primary_mail = db.Column(db.Boolean, default=False)  # doar
    is_invalid = db.Column(db.Boolean, default=False)  # shagui
    invalid_reason = db.Column(db.String(255), nullable=True)  # shagui_reason

    location_type = db.Column(db.String(50), nullable=True)  # mikum: home/work/etc.
    name = db.Column(db.String(200), nullable=True)  # name on address
    subtitle = db.Column(db.String(200), nullable=True)

    street = db.Column(db.String(255), nullable=True)
    house_number = db.Column(db.String(20), nullable=True)
    apartment = db.Column(db.String(20), nullable=True)
    area = db.Column(db.String(100), nullable=True)
    city = db.Column(db.String(100), nullable=True)
    state = db.Column(db.String(100), nullable=True)
    zip_code = db.Column(db.String(20), nullable=True)  # mikud
    country = db.Column(db.String(100), default='Israel')
    notes = db.Column(db.Text, nullable=True)

    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    def __repr__(self):
        return f'<Address {self.id} {self.city}>'
