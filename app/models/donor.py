from datetime import datetime
from ..extensions import db


class Donor(db.Model):
    """Donor information."""
    __tablename__ = 'donors'
    
    id = db.Column(db.Integer, primary_key=True)
    stripe_customer_id = db.Column(db.String(255), unique=True, nullable=True)
    first_name = db.Column(db.String(100), nullable=False)
    last_name = db.Column(db.String(100), nullable=False)
    email = db.Column(db.String(255), nullable=False)
    phone = db.Column(db.String(50), nullable=True)
    phone_country_code = db.Column(db.String(10), nullable=True)
    address_line1 = db.Column(db.String(255), nullable=True)
    address_line2 = db.Column(db.String(255), nullable=True)
    city = db.Column(db.String(100), nullable=True)
    state = db.Column(db.String(100), nullable=True)
    zip = db.Column(db.String(20), nullable=True)
    country = db.Column(db.String(100), default='US')
    comm_pref_email = db.Column(db.Boolean, default=True)
    comm_pref_sms = db.Column(db.Boolean, default=False)
    comm_pref_whatsapp = db.Column(db.Boolean, default=False)
    language_pref = db.Column(db.String(5), default='en')  # en/he
    test = db.Column(db.Boolean, default=False)  # True for test donations, False for real
    deleted_at = db.Column(db.DateTime, nullable=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    # Relationships
    donations = db.relationship('Donation', backref='donor', lazy='dynamic')
    receipts = db.relationship('Receipt', backref='donor', lazy='dynamic')
    
    @property
    def is_deleted(self):
        return self.deleted_at is not None
    
    @property
    def full_name(self):
        return f"{self.first_name} {self.last_name}"
    
    @property
    def full_address(self):
        parts = [self.address_line1]
        if self.address_line2:
            parts.append(self.address_line2)
        if self.city and self.state and self.zip:
            parts.append(f"{self.city}, {self.state} {self.zip}")
        elif self.city:
            parts.append(self.city)
        return '\n'.join(filter(None, parts))
    
    @classmethod
    def query_active(cls):
        return cls.query.filter(cls.deleted_at.is_(None))
    
    def __repr__(self):
        return f'<Donor {self.email}>'
