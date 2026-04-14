from datetime import datetime
from ..extensions import db


class Phone(db.Model):
    """Multiple phones per donor (ZTorm: Tel)."""
    __tablename__ = 'phones'

    id = db.Column(db.Integer, primary_key=True)
    donor_id = db.Column(db.Integer, db.ForeignKey('donors.id', ondelete='CASCADE'), nullable=False)

    sequence = db.Column(db.Integer, default=1)
    number = db.Column(db.String(20), nullable=True)
    area_code = db.Column(db.String(10), nullable=True)  # kidomet
    extension = db.Column(db.String(10), nullable=True)
    is_phone = db.Column(db.Boolean, default=True)  # tel
    is_fax = db.Column(db.Boolean, default=False)  # fax
    location = db.Column(db.String(50), nullable=True)  # mikum: home/work/cell
    notes = db.Column(db.String(255), nullable=True)

    created_at = db.Column(db.DateTime, default=datetime.utcnow)
