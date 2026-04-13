from datetime import datetime
from sqlalchemy.ext.mutable import MutableDict, MutableList
from ..extensions import db


class PaymentProcessor(db.Model):
    """Payment processor configuration (Stripe, Nedarim Plus, etc.)"""
    __tablename__ = 'payment_processors'

    id = db.Column(db.Integer, primary_key=True)
    code = db.Column(db.String(50), unique=True, nullable=False)  # 'stripe', 'nedarim', 'stripe_il'
    name = db.Column(db.String(100), nullable=False)               # Display name
    enabled = db.Column(db.Boolean, default=False)
    priority = db.Column(db.Integer, default=100)                  # Lower = higher priority
    processor_type = db.Column(db.String(50), default='credit_card')  # 'credit_card', 'daf', 'daf_aggregator'

    # Credentials (stored in DB, consider encryption for production)
    config_json = db.Column(MutableDict.as_mutable(db.JSON), nullable=True)  # API keys, mosad_id, etc.

    # Capabilities
    supported_currencies = db.Column(MutableList.as_mutable(db.JSON), nullable=True)   # ['USD', 'ILS']
    supported_countries = db.Column(MutableList.as_mutable(db.JSON), nullable=True)    # ['US', 'IL', '*'] (* = all)
    supports_recurring = db.Column(db.Boolean, default=True)
    supports_refunds = db.Column(db.Boolean, default=True)

    # Fees (for smart routing / cost optimization)
    fee_percentage = db.Column(db.Numeric(5, 3), nullable=True)    # e.g., 2.9%
    fee_fixed_cents = db.Column(db.Integer, nullable=True)          # e.g., 30 cents
    fee_currency = db.Column(db.String(10), default='USD')          # Currency of fixed fee

    # Display settings
    display_order = db.Column(db.Integer, default=100)              # Order in donor UI
    display_name = db.Column(db.String(100), nullable=True)         # Name shown to donors
    icon_url = db.Column(db.String(255), nullable=True)

    # Organization mapping (for international orgs with multiple IDs)
    organization_id = db.Column(db.String(100), nullable=True)      # External org ID
    organization_country = db.Column(db.String(5), nullable=True)   # Primary country for this processor account

    # Timestamps
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    deleted_at = db.Column(db.DateTime, nullable=True)

    # Relationships
    routing_rules = db.relationship('PaymentRoutingRule', backref='processor', lazy='dynamic')

    @property
    def is_deleted(self):
        return self.deleted_at is not None

    @classmethod
    def query_active(cls):
        return cls.query.filter(cls.deleted_at.is_(None))

    @classmethod
    def get_enabled(cls):
        """Get all enabled processors ordered by priority."""
        return cls.query_active().filter(cls.enabled == True).order_by(cls.priority).all()

    @classmethod
    def get_by_code(cls, code):
        """Get processor by code."""
        return cls.query_active().filter(cls.code == code).first()

    def supports_currency(self, currency):
        """Check if processor supports a currency."""
        if not self.supported_currencies:
            return True  # No restriction = supports all
        return currency.upper() in [c.upper() for c in self.supported_currencies]

    def supports_country(self, country_code):
        """Check if processor supports a country."""
        if not self.supported_countries:
            return True  # No restriction = supports all
        if '*' in self.supported_countries:
            return True
        return country_code.upper() in [c.upper() for c in self.supported_countries]

    def get_config(self, key, default=None):
        """Get a config value."""
        if not self.config_json:
            return default
        return self.config_json.get(key, default)

    def __repr__(self):
        return f'<PaymentProcessor {self.code}>'
