from datetime import datetime
from ..extensions import db


class CollectionBatch(db.Model):
    """Batch collection runs (ZTorm: Gvia)."""
    __tablename__ = 'collection_batches'

    id = db.Column(db.Integer, primary_key=True)
    batch_type = db.Column(db.String(20), nullable=True)  # sug: credit/hork
    batch_date = db.Column(db.DateTime, default=datetime.utcnow)
    charge_date = db.Column(db.Date, nullable=True)  # date_hiuv
    exchange_rate = db.Column(db.Numeric(10, 4), nullable=True)  # shaar
    total_amount = db.Column(db.Numeric(12, 2), default=0)
    item_count = db.Column(db.Integer, default=0)
    terminal_id = db.Column(db.Integer, nullable=True)  # num_masof
    returns_processed = db.Column(db.Boolean, default=False)  # hazarot_done
    notes = db.Column(db.Text, nullable=True)

    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    payments = db.relationship('Payment', backref='batch', lazy='dynamic')
    charges = db.relationship('CreditCardCharge', backref='batch', lazy='dynamic')
