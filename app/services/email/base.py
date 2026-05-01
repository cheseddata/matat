"""Base interface every inbox provider implements."""
from abc import ABC, abstractmethod


class BaseInboxProvider(ABC):
    """Abstract base class for inbox-side email providers.

    Each subclass talks to a different backend (Microsoft Graph,
    Gmail, IMAP, etc.) but exposes the same interface so the rest
    of the application doesn't have to care which backend a given
    mailbox actually uses.
    """

    def __init__(self, provider_row):
        self.provider = provider_row
        self.config = provider_row.config or {}

    @property
    @abstractmethod
    def code(self):
        """Unique provider code, e.g. 'msgraph', 'gmail', 'imap'."""

    @property
    @abstractmethod
    def name(self):
        """Human-readable provider name."""

    @abstractmethod
    def test_connection(self):
        """Verify credentials + mailbox access.

        Returns dict: {'success': bool, 'error': str|None, ...details}
        """

    @abstractmethod
    def fetch_new_messages(self, limit=100):
        """Pull messages we haven't seen yet for this mailbox.

        Implementations should use whatever change-tracking the backend
        offers (Graph delta queries, Gmail historyId, IMAP UIDs) and
        update `provider.last_delta_token` so the next call resumes.

        Returns list of dicts shaped like:
          {
            'remote_id':           backend's stable message id,
            'internet_message_id': RFC-822 Message-ID header,
            'conversation_id':     thread/conversation grouping id,
            'from_address':        ...,
            'from_name':           ...,
            'to_addresses':        [...],
            'cc_addresses':        [...],
            'subject':             ...,
            'body_text':           ...,
            'body_html':           ...,
            'received_at':         datetime,
            'has_attachments':     bool,
            'is_read':             bool,
            'attachments':         [{'filename', 'content_type', 'size', 'content_b64'}, ...],
          }
        Caller (sync command) is responsible for inserting / updating
        EmailMessage + EmailAttachment rows.
        """

    def supports_send(self):
        """Whether this provider can send replies. Override if it can."""
        return False

    def send_reply(self, to_addresses, subject, body_html, in_reply_to=None):
        """Send a reply through this provider. Override if supported."""
        raise NotImplementedError(f'{self.code} does not support sending')
