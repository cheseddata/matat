from datetime import datetime
from ..extensions import db


class ConfigSettings(db.Model):
    """System settings."""
    __tablename__ = 'config'
    
    id = db.Column(db.Integer, primary_key=True)
    org_name = db.Column(db.String(255), nullable=False, default='Matat Mordechai')
    org_prefix = db.Column(db.String(10), nullable=False, default='MM')  # For receipt numbering
    org_address = db.Column(db.String(500), nullable=True)  # Street address
    org_city = db.Column(db.String(100), nullable=True)
    org_state = db.Column(db.String(50), nullable=True)
    org_zip = db.Column(db.String(20), nullable=True)
    org_phone = db.Column(db.String(50), nullable=True)
    tax_id = db.Column(db.String(50), nullable=True)
    logo_url = db.Column(db.String(500), nullable=True)
    
    # Stripe configuration
    stripe_test_secret_key = db.Column(db.String(255), nullable=True)
    stripe_test_publishable_key = db.Column(db.String(255), nullable=True)
    stripe_live_secret_key = db.Column(db.String(255), nullable=True)
    stripe_live_publishable_key = db.Column(db.String(255), nullable=True)
    stripe_webhook_secret = db.Column(db.String(255), nullable=True)
    stripe_mode = db.Column(db.String(10), default='test')  # test/live

    @property
    def stripe_secret_key(self):
        """Return active secret key based on mode."""
        if self.stripe_mode == 'live':
            return self.stripe_live_secret_key
        return self.stripe_test_secret_key

    @property
    def stripe_publishable_key(self):
        """Return active publishable key based on mode."""
        if self.stripe_mode == 'live':
            return self.stripe_live_publishable_key
        return self.stripe_test_publishable_key
    
    # Default commission settings (system-wide fallback)
    default_commission_type = db.Column(db.String(20), nullable=True)  # flat/percentage
    default_commission_rate = db.Column(db.Numeric(10, 2), nullable=True)
    
    # Language
    default_language = db.Column(db.String(5), default='en')  # en/he

    # Site URL for generating links
    site_url = db.Column(db.String(255), default='https://matatmordechai.org')

    # Email/SMTP configuration
    smtp_host = db.Column(db.String(255), nullable=True)
    smtp_port = db.Column(db.Integer, default=587)
    smtp_username = db.Column(db.String(255), nullable=True)
    smtp_password = db.Column(db.String(255), nullable=True)
    smtp_use_tls = db.Column(db.Boolean, default=True)
    email_from_name = db.Column(db.String(255), default='Matat Mordechai')
    email_from_address = db.Column(db.String(255), nullable=True)
    mailtrap_token = db.Column(db.String(255), nullable=True)

    # ActiveTrail configuration
    activetrail_api_key = db.Column(db.String(255), nullable=True)
    activetrail_profile_id = db.Column(db.Integer, nullable=True)  # Sending profile ID
    activetrail_group_id = db.Column(db.Integer, nullable=True)  # Group to add contacts to
    activetrail_classification = db.Column(db.String(100), nullable=True)  # Company branding name
    activetrail_from_email = db.Column(db.String(255), nullable=True)
    activetrail_from_name = db.Column(db.String(255), nullable=True)

    # Email provider selection: 'mailtrap', 'activetrail', 'smtp'
    email_provider = db.Column(db.String(50), default='mailtrap')

    # YeshInvoice configuration
    yeshinvoice_user_key = db.Column(db.String(255), nullable=True)
    yeshinvoice_secret_key = db.Column(db.String(255), nullable=True)
    yeshinvoice_account_id = db.Column(db.String(100), nullable=True)
    yeshinvoice_enabled = db.Column(db.Boolean, default=False)
    yeshinvoice_default_doc_type = db.Column(db.String(50), default='receipt')

    # Claude AI API key
    anthropic_api_key = db.Column(db.String(255), nullable=True)

    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    def __repr__(self):
        return f'<ConfigSettings {self.org_name}>'
