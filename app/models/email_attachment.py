"""Per-message email attachments.

For phase 2 we store binaries inline in the DB (LONGTEXT/MEDIUMBLOB)
since we expect modest volume and most support@ attachments are
small (PDFs, screenshots, vCards). If volume grows we can move to
filesystem / S3 with a content_path column without breaking callers
— they only see the .read_content() method.

The binary is fetched lazily on first download click, not at sync
time, so a 50 MB attachment doesn't slow down the every-minute sync.
"""
from datetime import datetime
from ..extensions import db


class EmailAttachment(db.Model):
    __tablename__ = 'email_attachments'

    id = db.Column(db.Integer, primary_key=True)
    email_id = db.Column(db.Integer, db.ForeignKey('email_messages.id'),
                         nullable=False, index=True)

    remote_id = db.Column(db.String(500), nullable=False)          # Graph attachment id
    filename = db.Column(db.String(500), nullable=True)
    content_type = db.Column(db.String(255), nullable=True)
    size = db.Column(db.Integer, nullable=True)                    # bytes (per Graph)

    # Inline images referenced from the HTML body — content_id matches
    # `cid:<content_id>` in the html.
    is_inline = db.Column(db.Boolean, default=False)
    content_id = db.Column(db.String(255), nullable=True)

    # Lazy-fetched content. NULL until the first download / view request,
    # then populated and reused.
    content_b64 = db.Column(db.Text, nullable=True)

    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    fetched_at = db.Column(db.DateTime, nullable=True)

    def __repr__(self):
        return f'<EmailAttachment {self.id} {self.filename!r} {self.size}b>'
