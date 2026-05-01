"""Email messages pulled into the inbox portal.

One row per message we've ingested from any inbox provider. The
`provider_id + remote_id` pair is unique — `remote_id` is the
backend's stable message id (Graph message.id, Gmail messageId, IMAP
UIDVALIDITY+UID, etc.). `internet_message_id` is the RFC-822
Message-ID header which lets us match the same message across
providers if a mailbox ever switches backends.

Bodies are stored inline. Attachment binaries live on
EmailAttachment and are downloaded lazily on click.
"""
from datetime import datetime
from sqlalchemy.ext.mutable import MutableList
from ..extensions import db


class EmailMessage(db.Model):
    __tablename__ = 'email_messages'

    id = db.Column(db.Integer, primary_key=True)
    provider_id = db.Column(db.Integer, db.ForeignKey('email_inbox_providers.id'),
                            nullable=False, index=True)

    # Backend-stable IDs
    remote_id = db.Column(db.String(500), nullable=False, index=True)
    internet_message_id = db.Column(db.String(500), nullable=True, index=True)
    conversation_id = db.Column(db.String(500), nullable=True, index=True)

    # Headers
    from_address = db.Column(db.String(255), nullable=True, index=True)
    from_name = db.Column(db.String(255), nullable=True)
    to_addresses = db.Column(MutableList.as_mutable(db.JSON), nullable=True)   # ['a@b.com', ...]
    cc_addresses = db.Column(MutableList.as_mutable(db.JSON), nullable=True)
    bcc_addresses = db.Column(MutableList.as_mutable(db.JSON), nullable=True)
    subject = db.Column(db.String(1000), nullable=True)

    # Body
    body_text = db.Column(db.Text, nullable=True)
    body_html = db.Column(db.Text, nullable=True)
    body_preview = db.Column(db.String(500), nullable=True)        # short snippet for list view

    # Metadata
    received_at = db.Column(db.DateTime, nullable=True, index=True)
    importance = db.Column(db.String(20), nullable=True)           # 'low'|'normal'|'high'
    has_attachments = db.Column(db.Boolean, default=False)

    # Per-mailbox state
    is_read = db.Column(db.Boolean, default=False, index=True)
    is_archived = db.Column(db.Boolean, default=False, index=True) # portal-side archive

    # Auto-linked to a donor by matching from_address — recomputed on
    # ingest. Operator can override later via the UI if we ever surface
    # that, but the auto-match handles 95% of inbound mail.
    donor_id = db.Column(db.Integer, db.ForeignKey('donors.id'), nullable=True, index=True)

    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    # Relationships
    provider = db.relationship('EmailInboxProvider', backref='messages')
    donor = db.relationship('Donor', backref='emails', foreign_keys=[donor_id])
    attachments = db.relationship('EmailAttachment', backref='message',
                                  cascade='all, delete-orphan', lazy='dynamic')

    __table_args__ = (
        db.UniqueConstraint('provider_id', 'remote_id', name='uq_email_provider_remote'),
    )

    def __repr__(self):
        return f'<EmailMessage {self.id} from={self.from_address!r} subject={self.subject!r}>'
