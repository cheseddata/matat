from datetime import datetime
from ..extensions import db


class ChatArchive(db.Model):
    """Archived chat conversations."""
    __tablename__ = 'chat_archives'

    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    messages_json = db.Column(db.Text, nullable=False)  # JSON array of messages
    message_count = db.Column(db.Integer, default=0)
    resolution_notes = db.Column(db.Text, nullable=True)  # What was done
    archived_at = db.Column(db.DateTime, default=datetime.utcnow)
    archived_by = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=True)  # Who cleared it

    # Relationships
    user = db.relationship('User', foreign_keys=[user_id], backref=db.backref('chat_archives', lazy='dynamic'))
    archiver = db.relationship('User', foreign_keys=[archived_by])

    def __repr__(self):
        return f'<ChatArchive {self.id} for user {self.user_id}>'
