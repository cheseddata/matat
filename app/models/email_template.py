from datetime import datetime
from sqlalchemy.ext.mutable import MutableList
from ..extensions import db


class EmailTemplate(db.Model):
    """Custom email templates for donation link emails."""
    __tablename__ = 'email_templates'

    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=False)
    language = db.Column(db.String(5), nullable=False, default='en')  # 'en' or 'he'
    subject = db.Column(db.String(255), nullable=False)
    body = db.Column(db.Text, nullable=False)

    # Legacy single-attachment fields — kept for back-compat reading.
    # New attachments go into `attachments` (list) below.
    attachment_path = db.Column(db.String(500), nullable=True)
    attachment_name = db.Column(db.String(255), nullable=True)
    # Multi-attachment list: [{"path": "/var/www/matat/uploads/...",
    #                         "name": "donor-letter.pdf"}, ...]
    # Mrs. Rosen needs to attach >1 file per template (PDF + DOCX +
    # an image are typical). The `MutableList.as_mutable` makes
    # SQLAlchemy notice in-place mutations so we don't have to
    # reassign the whole list on every edit.
    attachments = db.Column(MutableList.as_mutable(db.JSON), nullable=True)

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

    @property
    def all_attachments(self):
        """Unified list of {path, name} for every attachment on this
        template — pulls in the legacy single-attachment fields too so
        callers don't need to special-case old vs new templates.
        """
        items = []
        for a in (self.attachments or []):
            if isinstance(a, dict) and a.get('path'):
                items.append({'path': a['path'], 'name': a.get('name') or a['path'].rsplit('/', 1)[-1]})
        if self.attachment_path and self.attachment_path not in {a['path'] for a in items}:
            items.append({'path': self.attachment_path,
                          'name': self.attachment_name or self.attachment_path.rsplit('/', 1)[-1]})
        return items

    @property
    def attachment_paths(self):
        """Just the filesystem paths — convenient for the email-sender."""
        return [a['path'] for a in self.all_attachments if a.get('path')]
