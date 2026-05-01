"""Maps EmailInboxProvider rows to their handler classes.

Adding a new backend = adding a row to PROVIDERS plus the handler module.
Nothing else in the app needs to change.
"""
from .microsoft_graph_inbox import MicrosoftGraphInbox


PROVIDERS = {
    'msgraph': MicrosoftGraphInbox,
    # 'gmail': GmailInbox,        # to add: app/services/email/gmail_inbox.py
    # 'imap':  ImapInbox,         # to add: app/services/email/imap_inbox.py
}


def get_handler_for_provider(provider_row):
    """Return an instance of the handler class matching provider_row.code."""
    cls = PROVIDERS.get(provider_row.code)
    if not cls:
        raise ValueError(f'No handler registered for inbox provider code: {provider_row.code!r}')
    return cls(provider_row)


def supported_codes():
    """List of provider codes the system knows how to talk to."""
    return list(PROVIDERS.keys())
