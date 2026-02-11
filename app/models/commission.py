from datetime import datetime
from ..extensions import db


class Commission(db.Model):
    """Commission tracking."""
    __tablename__ = 'commissions'
    
    id = db.Column(db.Integer, primary_key=True)
    donation_id = db.Column(db.Integer, db.ForeignKey('donations.id', ondelete='CASCADE'), nullable=False)
    salesperson_id = db.Column(db.Integer, db.ForeignKey('users.id', ondelete='RESTRICT'), nullable=False)
    
    # Amount fields (in cents)
    donation_amount = db.Column(db.Integer, nullable=False)  # Gross donation amount in cents
    commission_type = db.Column(db.String(20), nullable=False)  # flat/percentage
    commission_rate = db.Column(db.Numeric(10, 2), nullable=False)  # Rate used
    commission_amount = db.Column(db.Integer, nullable=False)  # Commission in cents
    
    # Status and payment
    status = db.Column(db.String(20), default='pending')  # pending/paid/voided
    paid_date = db.Column(db.DateTime, nullable=True)
    paid_method = db.Column(db.String(100), nullable=True)  # check/bank/cash
    paid_reference = db.Column(db.String(255), nullable=True)  # Check number, etc.
    
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    
    @property
    def commission_amount_dollars(self):
        return self.commission_amount / 100 if self.commission_amount else 0
    
    @property
    def donation_amount_dollars(self):
        return self.donation_amount / 100 if self.donation_amount else 0
    
    def __repr__(self):
        return f'<Commission {self.id} ${self.commission_amount_dollars}>'
