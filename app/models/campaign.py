from datetime import datetime
from ..extensions import db


class Campaign(db.Model):
    """Campaign / Affiliate tracking."""
    __tablename__ = 'campaigns'
    
    id = db.Column(db.Integer, primary_key=True)
    aff_code = db.Column(db.String(50), unique=True, nullable=False)  # e.g., PURIM2026
    name = db.Column(db.String(255), nullable=False)
    description = db.Column(db.Text, nullable=True)
    start_date = db.Column(db.Date, nullable=True)
    end_date = db.Column(db.Date, nullable=True)  # Nullable for ongoing campaigns
    
    # Commission override (overrides salesperson default if set)
    commission_override_type = db.Column(db.String(20), nullable=True)  # flat/percentage
    commission_override_rate = db.Column(db.Numeric(10, 2), nullable=True)
    
    # Goal tracking
    goal_amount = db.Column(db.Integer, nullable=True)  # In cents
    total_raised = db.Column(db.Integer, default=0)  # Cached total in cents
    
    is_active = db.Column(db.Boolean, default=True)
    created_by = db.Column(db.Integer, db.ForeignKey('users.id', ondelete='RESTRICT'), nullable=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    # Relationships
    donations = db.relationship('Donation', backref='campaign', lazy='dynamic')
    donation_links = db.relationship('DonationLink', backref='campaign', lazy='dynamic')
    
    @property
    def goal_amount_dollars(self):
        return self.goal_amount / 100 if self.goal_amount else 0
    
    @property
    def total_raised_dollars(self):
        return self.total_raised / 100 if self.total_raised else 0
    
    @property
    def progress_percent(self):
        if not self.goal_amount or self.goal_amount == 0:
            return 0
        return min(100, (self.total_raised / self.goal_amount) * 100)
    
    def __repr__(self):
        return f'<Campaign {self.aff_code}>'
