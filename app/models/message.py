from datetime import datetime
from ..extensions import db


class MessageQueue(db.Model):
    """Unified outbound message log."""
    __tablename__ = 'message_queue'
    
    id = db.Column(db.Integer, primary_key=True)
    channel = db.Column(db.String(20), nullable=False)  # email/sms/whatsapp
    recipient_type = db.Column(db.String(20), nullable=True)  # donor/salesperson/admin
    recipient_id = db.Column(db.Integer, nullable=True)
    recipient_address = db.Column(db.String(255), nullable=False)  # Email or phone
    
    message_type = db.Column(db.String(50), nullable=False)  # receipt/donation_link/welcome/etc.
    subject = db.Column(db.String(500), nullable=True)  # Email only
    body_text = db.Column(db.Text, nullable=True)
    body_html = db.Column(db.Text, nullable=True)
    attachment_path = db.Column(db.String(500), nullable=True)
    
    template_id = db.Column(db.Integer, db.ForeignKey('message_templates.id'), nullable=True)
    related_donation_id = db.Column(db.Integer, db.ForeignKey('donations.id'), nullable=True)
    related_link_id = db.Column(db.Integer, db.ForeignKey('donation_links.id'), nullable=True)
    
    status = db.Column(db.String(20), default='queued')  # queued/sending/sent/delivered/failed/bounced
    provider = db.Column(db.String(50), nullable=True)  # sendgrid/twilio/etc.
    provider_message_id = db.Column(db.String(255), nullable=True)
    error_message = db.Column(db.Text, nullable=True)
    
    retry_count = db.Column(db.Integer, default=0)
    max_retries = db.Column(db.Integer, default=3)
    
    scheduled_at = db.Column(db.DateTime, nullable=True)
    sent_at = db.Column(db.DateTime, nullable=True)
    delivered_at = db.Column(db.DateTime, nullable=True)
    opened_at = db.Column(db.DateTime, nullable=True)
    clicked_at = db.Column(db.DateTime, nullable=True)
    
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    
    def __repr__(self):
        return f'<MessageQueue {self.id} {self.channel}>'


class MessageTemplate(db.Model):
    """Reusable templates per channel."""
    __tablename__ = 'message_templates'
    
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=False)
    channel = db.Column(db.String(20), nullable=False)  # email/sms/whatsapp
    message_type = db.Column(db.String(50), nullable=False)
    
    subject_template = db.Column(db.String(500), nullable=True)  # Email only
    body_template_text = db.Column(db.Text, nullable=True)
    body_template_html = db.Column(db.Text, nullable=True)
    
    language = db.Column(db.String(5), default='en')  # en/he
    variables = db.Column(db.JSON, nullable=True)  # List of merge fields
    whatsapp_template_name = db.Column(db.String(100), nullable=True)
    
    active = db.Column(db.Boolean, default=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    def __repr__(self):
        return f'<MessageTemplate {self.name}>'


class CommProvider(db.Model):
    """Channel provider configuration."""
    __tablename__ = 'comm_providers'
    
    id = db.Column(db.Integer, primary_key=True)
    channel = db.Column(db.String(20), nullable=False)  # email/sms/whatsapp
    provider_name = db.Column(db.String(50), nullable=False)
    
    api_key = db.Column(db.String(500), nullable=True)
    api_secret = db.Column(db.String(500), nullable=True)
    from_address = db.Column(db.String(255), nullable=True)  # Email sender or phone number
    webhook_secret = db.Column(db.String(255), nullable=True)
    
    is_active = db.Column(db.Boolean, default=True)
    is_default = db.Column(db.Boolean, default=False)
    config_json = db.Column(db.JSON, nullable=True)  # Provider-specific settings
    
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    def __repr__(self):
        return f'<CommProvider {self.channel} {self.provider_name}>'
