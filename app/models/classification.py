from datetime import datetime
from ..extensions import db


class Classification(db.Model):
    """Donor classification tags (ZTorm: Sivug)."""
    __tablename__ = 'classifications'

    id = db.Column(db.Integer, primary_key=True)
    donor_id = db.Column(db.Integer, db.ForeignKey('donors.id', ondelete='CASCADE'), nullable=False)
    tag = db.Column(db.String(100), nullable=False)  # sivug value
    category = db.Column(db.String(50), nullable=True)  # grouping category

    created_at = db.Column(db.DateTime, default=datetime.utcnow)
