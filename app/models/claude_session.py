from datetime import datetime
from ..extensions import db


class ClaudeSession(db.Model):
    """Track Claude chat sessions for audit and rollback purposes."""
    __tablename__ = 'claude_sessions'

    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=True)

    # Session timing
    started_at = db.Column(db.DateTime, default=datetime.utcnow)
    ended_at = db.Column(db.DateTime, nullable=True)

    # tmux session info
    tmux_session = db.Column(db.String(50), default='4')

    # Session metadata
    purpose = db.Column(db.String(255), nullable=True)  # What they're working on
    notes = db.Column(db.Text, nullable=True)  # Any notes about the session

    # Relationships
    user = db.relationship('User', backref='claude_sessions')
    screenshots = db.relationship('ClaudeScreenshot', backref='session', lazy='dynamic')

    @property
    def duration(self):
        """Get session duration in minutes."""
        if self.ended_at:
            delta = self.ended_at - self.started_at
            return int(delta.total_seconds() / 60)
        else:
            delta = datetime.utcnow() - self.started_at
            return int(delta.total_seconds() / 60)

    @property
    def is_active(self):
        return self.ended_at is None

    def __repr__(self):
        return f'<ClaudeSession {self.id} by user {self.user_id}>'


class ClaudeScreenshot(db.Model):
    """Screenshots uploaded during Claude sessions."""
    __tablename__ = 'claude_screenshots'

    id = db.Column(db.Integer, primary_key=True)
    session_id = db.Column(db.Integer, db.ForeignKey('claude_sessions.id'), nullable=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=True)

    filename = db.Column(db.String(255), nullable=False)
    original_filename = db.Column(db.String(255), nullable=True)
    file_path = db.Column(db.String(500), nullable=False)
    file_size = db.Column(db.Integer, nullable=True)

    description = db.Column(db.Text, nullable=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    # Relationship
    user = db.relationship('User', backref='claude_screenshots')

    @property
    def url(self):
        return f'/claude/screenshot/{self.filename}'

    def __repr__(self):
        return f'<ClaudeScreenshot {self.filename}>'


class ClaudeConfig(db.Model):
    """Configuration for Claude integration."""
    __tablename__ = 'claude_config'

    id = db.Column(db.Integer, primary_key=True)
    key = db.Column(db.String(50), unique=True, nullable=False)
    value = db.Column(db.String(255), nullable=True)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    @classmethod
    def get(cls, key, default=None):
        config = cls.query.filter_by(key=key).first()
        return config.value if config else default

    @classmethod
    def set(cls, key, value):
        config = cls.query.filter_by(key=key).first()
        if config:
            config.value = value
        else:
            config = cls(key=key, value=value)
            db.session.add(config)
        db.session.commit()
        return config

    def __repr__(self):
        return f'<ClaudeConfig {self.key}={self.value}>'
