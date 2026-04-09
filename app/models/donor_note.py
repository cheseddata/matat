from datetime import datetime
from ..extensions import db


class DonorNote(db.Model):
    """Notes added to donor records by admin or salesperson users."""
    __tablename__ = 'donor_notes'

    id = db.Column(db.Integer, primary_key=True)
    donor_id = db.Column(db.Integer, db.ForeignKey('donors.id', ondelete='CASCADE'), nullable=False)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id', ondelete='SET NULL'), nullable=True)

    content = db.Column(db.Text, nullable=False)
    is_pinned = db.Column(db.Boolean, default=False)

    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    deleted_at = db.Column(db.DateTime, nullable=True)  # Soft delete

    # Relationships
    donor = db.relationship('Donor', backref=db.backref('notes', lazy='dynamic'))
    user = db.relationship('User', backref=db.backref('donor_notes', lazy='dynamic'))

    @property
    def is_deleted(self):
        return self.deleted_at is not None

    @classmethod
    def query_active(cls):
        return cls.query.filter(cls.deleted_at.is_(None))

    def __repr__(self):
        return f'<DonorNote {self.id} for Donor {self.donor_id}>'
