from datetime import datetime
from ..extensions import db


class HelpRequest(db.Model):
    """Help requests from users to Claude."""
    __tablename__ = 'help_requests'

    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    page_url = db.Column(db.String(500), nullable=True)
    issue = db.Column(db.Text, nullable=False)
    screenshot_id = db.Column(db.Integer, db.ForeignKey('claude_screenshots.id'), nullable=True)
    status = db.Column(db.String(20), default='pending')  # pending, in_progress, resolved, referred
    resolution = db.Column(db.Text, nullable=True)  # What was done to resolve
    referred_to = db.Column(db.String(100), nullable=True)  # e.g., "Menachem Kantor" for new dev
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    resolved_at = db.Column(db.DateTime, nullable=True)

    # Relationships
    user = db.relationship('User', backref=db.backref('help_requests', lazy='dynamic'))
    screenshot = db.relationship('ClaudeScreenshot', backref='help_request')

    def __repr__(self):
        return f'<HelpRequest {self.id} from user {self.user_id}>'
