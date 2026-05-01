"""Inbox-side email provider — table-driven like payment processors.

Each row in `email_inbox_providers` represents one mailbox we pull from
(e.g. support@matatmordechai.org via Microsoft Graph,
donations@... via Gmail, info@... via IMAP). The `code` column picks
the handler class in `app/services/email/` that knows how to talk to
that backend; `config_json` (encrypted) holds the per-backend
credentials (tenant id, client id, secret, OAuth refresh token, etc.).

This matches the PaymentProcessor pattern — operators add or disable
providers from admin without code changes; new backend types just need
a new handler class registered in the router.
"""
import json
from datetime import datetime
from ..extensions import db


class EmailInboxProvider(db.Model):
    __tablename__ = 'email_inbox_providers'

    id = db.Column(db.Integer, primary_key=True)
    code = db.Column(db.String(50), unique=True, nullable=False)   # 'msgraph', 'gmail', 'imap'
    name = db.Column(db.String(100), nullable=False)               # display name
    enabled = db.Column(db.Boolean, default=False)
    priority = db.Column(db.Integer, default=100)                  # lower = synced first

    # Mailbox the operator wants pulled into the portal
    mailbox_address = db.Column(db.String(255), nullable=True)     # e.g. support@matatmordechai.org

    # Encrypted JSON blob of provider-specific config (tenant id, client id,
    # secret, OAuth refresh token, IMAP host, etc.). Each handler class
    # knows the keys it expects.
    _config_json_enc = db.Column('config_json', db.Text, nullable=True)

    # Sync state for resumable / delta-driven syncs
    last_sync_at = db.Column(db.DateTime, nullable=True)
    last_delta_token = db.Column(db.Text, nullable=True)           # opaque pagination/delta cursor
    last_sync_status = db.Column(db.String(20), nullable=True)     # 'ok' | 'error'
    last_sync_error = db.Column(db.Text, nullable=True)            # last error message if any

    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    deleted_at = db.Column(db.DateTime, nullable=True)

    @property
    def is_deleted(self):
        return self.deleted_at is not None

    @property
    def config(self):
        """Decrypted config dict. Empty dict if not set."""
        if not self._config_json_enc:
            return {}
        from ..utils.crypto import decrypt_value
        decrypted = decrypt_value(self._config_json_enc)
        if decrypted is None:
            decrypted = self._config_json_enc  # legacy unencrypted fallback
        try:
            return json.loads(decrypted) if decrypted else {}
        except (ValueError, TypeError):
            return {}

    @config.setter
    def config(self, value):
        """Encrypt and store the config dict."""
        if not value:
            self._config_json_enc = None
            return
        from ..utils.crypto import encrypt_value
        plain = json.dumps(value)
        encrypted = encrypt_value(plain)
        self._config_json_enc = encrypted if encrypted else plain

    @classmethod
    def query_active(cls):
        return cls.query.filter(cls.deleted_at.is_(None))

    @classmethod
    def get_enabled(cls):
        return cls.query_active().filter(cls.enabled == True).order_by(cls.priority).all()

    @classmethod
    def get_by_code(cls, code):
        return cls.query_active().filter(cls.code == code).first()

    def get_handler(self):
        """Return an instance of the matching handler class."""
        from ..services.email.router import get_handler_for_provider
        return get_handler_for_provider(self)

    def __repr__(self):
        return f'<EmailInboxProvider {self.code}:{self.mailbox_address}>'
