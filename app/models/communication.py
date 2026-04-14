from datetime import datetime
from ..extensions import db


class Communication(db.Model):
    """Correspondence log (ZTorm: Tikshoret)."""
    __tablename__ = 'communications'

    id = db.Column(db.Integer, primary_key=True)
    donor_id = db.Column(db.Integer, db.ForeignKey('donors.id'), nullable=False)
    donation_id = db.Column(db.Integer, db.ForeignKey('donations.id'), nullable=True)
    agreement_id = db.Column(db.Integer, db.ForeignKey('agreements.id'), nullable=True)
    receipt_id = db.Column(db.Integer, db.ForeignKey('receipts.id'), nullable=True)

    comm_type = db.Column(db.String(30), nullable=True)  # ofen: kabala/doar/sms/email
    status = db.Column(db.String(30), nullable=True)  # NoAddress/sent/returned/etc.

    registration_date = db.Column(db.Date, nullable=True)  # date_rishum
    execution_date = db.Column(db.Date, nullable=True)  # date_bitzua
    target_date = db.Column(db.Date, nullable=True)  # date_yaad
    return_date = db.Column(db.Date, nullable=True)  # date_hazar

    executor = db.Column(db.String(100), nullable=True)  # mvatzea
    link = db.Column(db.String(500), nullable=True)
    notes = db.Column(db.Text, nullable=True)  # hearot
    document = db.Column(db.String(500), nullable=True)  # doc path

    created_at = db.Column(db.DateTime, default=datetime.utcnow)
