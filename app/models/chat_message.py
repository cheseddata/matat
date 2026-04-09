from datetime import datetime
from ..extensions import db


class ChatMessage(db.Model):
    """Chat messages between users and Claude."""
    __tablename__ = 'chat_messages'

    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    role = db.Column(db.String(20), nullable=False)  # 'user' or 'assistant'
    content = db.Column(db.Text, nullable=False)
    page_url = db.Column(db.String(500), nullable=True)  # Where user was when they sent message
    screenshot_id = db.Column(db.Integer, db.ForeignKey('claude_screenshots.id'), nullable=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    # Relationships
    user = db.relationship('User', backref=db.backref('chat_messages', lazy='dynamic'))
    screenshot = db.relationship('ClaudeScreenshot')

    def to_dict(self):
        return {
            'id': self.id,
            'role': self.role,
            'content': self.content,
            'created_at': self.created_at.isoformat(),
            'screenshot_url': self.screenshot.url if self.screenshot else None
        }

    def __repr__(self):
        return f'<ChatMessage {self.id} from user {self.user_id}>'
