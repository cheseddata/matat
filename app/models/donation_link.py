from datetime import datetime
from ..extensions import db


class DonationLink(db.Model):
    """Salesperson/campaign-generated donation links."""
    __tablename__ = 'donation_links'
    
    id = db.Column(db.Integer, primary_key=True)
    short_code = db.Column(db.String(20), unique=True, nullable=False)
    salesperson_id = db.Column(db.Integer, db.ForeignKey('users.id', ondelete='RESTRICT'), nullable=True)
    campaign_id = db.Column(db.Integer, db.ForeignKey('campaigns.id', ondelete='RESTRICT'), nullable=True)
    
    # Donor pre-fill data
    donor_email = db.Column(db.String(255), nullable=True)
    donor_name = db.Column(db.String(255), nullable=True)
    donor_address = db.Column(db.String(500), nullable=True)
    
    # Preset options
    preset_amount = db.Column(db.Integer, nullable=True)  # In cents
    preset_type = db.Column(db.String(20), nullable=True)  # onetime/recurring
    
    # Full URL for reference
    full_url = db.Column(db.String(1000), nullable=True)
    
    # Usage tracking
    times_used = db.Column(db.Integer, default=0)
    last_used_at = db.Column(db.DateTime, nullable=True)
    
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    
    # Relationship
    donations = db.relationship('Donation', backref='link', lazy='dynamic')
    
    @property
    def preset_amount_dollars(self):
        return self.preset_amount / 100 if self.preset_amount else None
    
    def __repr__(self):
        return f'<DonationLink {self.short_code}>'
