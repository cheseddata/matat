from datetime import datetime
from ..extensions import db


class Receipt(db.Model):
    """Receipt log."""
    __tablename__ = 'receipts'
    
    id = db.Column(db.Integer, primary_key=True)
    donation_id = db.Column(db.Integer, db.ForeignKey('donations.id', ondelete='RESTRICT'), nullable=False)
    receipt_number = db.Column(db.String(50), unique=True, nullable=False)  # e.g., MM-2026-00147
    donor_id = db.Column(db.Integer, db.ForeignKey('donors.id', ondelete='RESTRICT'), nullable=False)
    
    amount = db.Column(db.Integer, nullable=False)  # In cents
    tax_id_used = db.Column(db.String(50), nullable=True)
    pdf_path = db.Column(db.String(500), nullable=True)
    
    email_sent_to = db.Column(db.String(255), nullable=True)
    sent_at = db.Column(db.DateTime, nullable=True)
    reissued_at = db.Column(db.DateTime, nullable=True)
    
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    
    @property
    def amount_dollars(self):
        return self.amount / 100 if self.amount else 0
    
    def __repr__(self):
        return f'<Receipt {self.receipt_number}>'


class ReceiptCounter(db.Model):
    """Atomic sequential receipt numbering."""
    __tablename__ = 'receipt_counter'
    
    id = db.Column(db.Integer, primary_key=True)
    org_prefix = db.Column(db.String(10), nullable=False)  # e.g., MM
    fiscal_year = db.Column(db.Integer, nullable=False)
    last_sequence = db.Column(db.Integer, default=0)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    __table_args__ = (
        db.UniqueConstraint('org_prefix', 'fiscal_year', name='uq_org_year'),
    )
    
    def __repr__(self):
        return f'<ReceiptCounter {self.org_prefix}-{self.fiscal_year}>'
