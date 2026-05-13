from datetime import datetime
from ..extensions import db


class FaxRecipient(db.Model):
    """Bank-transfer recipient for the Bank Hadoar fax (Matat → vendors).

    Each row is a payee Gittle keeps in the database so she can pick them
    when building the fax. The transferred amount is per-fax and is not
    stored here.
    """
    __tablename__ = 'fax_recipients'

    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(255), nullable=False)
    bank_number = db.Column(db.String(10), nullable=False)
    branch_number = db.Column(db.String(10), nullable=False)
    account_number = db.Column(db.String(30), nullable=False)

    created_by = db.Column(db.Integer, db.ForeignKey('users.id', ondelete='SET NULL'), nullable=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    deleted_at = db.Column(db.DateTime, nullable=True)

    @property
    def is_deleted(self):
        return self.deleted_at is not None

    @classmethod
    def query_active(cls):
        return cls.query.filter(cls.deleted_at.is_(None))

    def __repr__(self):
        return f'<FaxRecipient {self.id} {self.name}>'
