from datetime import datetime
from ..extensions import db


class EmailTemplate(db.Model):
    """Custom email templates for donation link emails."""
    __tablename__ = 'email_templates'

    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=False)
    language = db.Column(db.String(5), nullable=False, default='en')  # 'en' or 'he'
    subject = db.Column(db.String(255), nullable=False)
    body = db.Column(db.Text, nullable=False)

    # Who created it - if null, it's a system template
    created_by = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=True)

    # Is this a global template available to all salespersons?
    is_global = db.Column(db.Boolean, default=False)

    # Soft delete
    deleted_at = db.Column(db.DateTime, nullable=True)

    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    # Relationships
    creator = db.relationship('User', backref='email_templates')

    def __repr__(self):
        return f'<EmailTemplate {self.name} ({self.language})>'
