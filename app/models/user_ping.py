from datetime import datetime
from ..extensions import db


class UserPing(db.Model):
    """In-app real-time popup notification (admin → user).

    The recipient's browser polls `/api/pings/check` every ~8 seconds;
    any un-dismissed row addressed to them surfaces as a centered modal
    that requires acknowledgement to dismiss. Lightweight by design —
    no rich content, no threading, no read-receipts beyond delivered_at
    and dismissed_at timestamps. For anything heavier, use email.
    """
    __tablename__ = 'user_pings'

    id = db.Column(db.Integer, primary_key=True)
    sender_id    = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    recipient_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False, index=True)

    title   = db.Column(db.String(200), nullable=True)
    message = db.Column(db.Text, nullable=False)
    # Optional URL the modal can link to (e.g., a specific donation
    # row the admin wants the user to look at). NULL = info-only ping.
    link    = db.Column(db.String(500), nullable=True)

    created_at   = db.Column(db.DateTime, default=datetime.utcnow, index=True)
    delivered_at = db.Column(db.DateTime, nullable=True)  # first time recipient's poller saw it
    dismissed_at = db.Column(db.DateTime, nullable=True, index=True)  # recipient clicked OK

    sender    = db.relationship('User', foreign_keys=[sender_id])
    recipient = db.relationship('User', foreign_keys=[recipient_id])

    def __repr__(self):
        return f'<UserPing #{self.id} {self.sender_id}→{self.recipient_id} dismissed={self.dismissed_at is not None}>'
