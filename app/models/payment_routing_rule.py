from datetime import datetime
from ..extensions import db


class PaymentRoutingRule(db.Model):
    """Rules for routing payments to specific processors."""
    __tablename__ = 'payment_routing_rules'

    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=False)
    description = db.Column(db.Text, nullable=True)
    priority = db.Column(db.Integer, default=100)       # Lower = check first
    enabled = db.Column(db.Boolean, default=True)

    # Conditions (all nullable - null means "match any")
    # When multiple conditions are set, ALL must match (AND logic)

    # Currency condition
    currency = db.Column(db.String(10), nullable=True)  # 'USD', 'ILS', etc.

    # Geographic conditions
    country_code = db.Column(db.String(5), nullable=True)   # Donor's country: 'US', 'IL'
    region = db.Column(db.String(50), nullable=True)        # Region grouping: 'israel', 'us', 'europe'

    # Amount conditions (in cents)
    min_amount_cents = db.Column(db.Integer, nullable=True)
    max_amount_cents = db.Column(db.Integer, nullable=True)

    # Donation type
    donation_type = db.Column(db.String(20), nullable=True)  # 'one_time', 'recurring'

    # Source conditions
    source = db.Column(db.String(50), nullable=True)         # 'phone', 'web', 'campaign'
    campaign_id = db.Column(db.Integer, db.ForeignKey('campaigns.id'), nullable=True)

    # Action: which processor to use
    processor_id = db.Column(db.Integer, db.ForeignKey('payment_processors.id'), nullable=False)

    # Timestamps
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    deleted_at = db.Column(db.DateTime, nullable=True)

    @property
    def is_deleted(self):
        return self.deleted_at is not None

    @classmethod
    def query_active(cls):
        return cls.query.filter(cls.deleted_at.is_(None))

    @classmethod
    def get_enabled_ordered(cls):
        """Get all enabled rules ordered by priority (lowest first)."""
        return cls.query_active().filter(cls.enabled == True).order_by(cls.priority).all()

    def matches(self, currency=None, country_code=None, amount_cents=None,
                donation_type=None, source=None, campaign_id=None):
        """
        Check if this rule matches the given conditions.
        Returns True if all non-null rule conditions match.
        """
        # Currency check
        if self.currency and currency:
            if self.currency.upper() != currency.upper():
                return False

        # Country check
        if self.country_code and country_code:
            if self.country_code.upper() != country_code.upper():
                return False

        # Region check (maps countries to regions)
        if self.region and country_code:
            region_map = {
                'israel': ['IL'],
                'us': ['US'],
                'europe': ['GB', 'DE', 'FR', 'IT', 'ES', 'NL', 'BE', 'AT', 'CH'],
            }
            countries_in_region = region_map.get(self.region.lower(), [])
            if country_code.upper() not in countries_in_region:
                return False

        # Amount range check
        if amount_cents is not None:
            if self.min_amount_cents and amount_cents < self.min_amount_cents:
                return False
            if self.max_amount_cents and amount_cents > self.max_amount_cents:
                return False

        # Donation type check
        if self.donation_type and donation_type:
            if self.donation_type.lower() != donation_type.lower():
                return False

        # Source check
        if self.source and source:
            if self.source.lower() != source.lower():
                return False

        # Campaign check
        if self.campaign_id and campaign_id:
            if self.campaign_id != campaign_id:
                return False

        return True

    def __repr__(self):
        return f'<PaymentRoutingRule {self.id}: {self.name}>'
