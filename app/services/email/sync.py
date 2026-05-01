"""Inbox sync orchestrator — provider-agnostic.

Walks every enabled EmailInboxProvider, asks its handler for new
messages, and persists them as EmailMessage / EmailAttachment rows.
The handler does the backend-specific work; this module only knows
about our DB schema.
"""
import logging
from datetime import datetime

from ...extensions import db
from ...models.email_inbox_provider import EmailInboxProvider
from ...models.email_message import EmailMessage
from ...models.email_attachment import EmailAttachment
from ...models.donor import Donor

logger = logging.getLogger(__name__)


def _match_donor(from_address):
    """Find a donor whose email matches `from_address`. Case-insensitive."""
    if not from_address:
        return None
    return Donor.query.filter(db.func.lower(Donor.email) == from_address.lower()).first()


def _persist_message(provider, msg, handler):
    """Insert or update one message + attachment metadata. Returns (created, message)."""
    existing = EmailMessage.query.filter_by(
        provider_id=provider.id, remote_id=msg['remote_id']
    ).first()

    is_create = existing is None
    em = existing or EmailMessage(provider_id=provider.id, remote_id=msg['remote_id'])

    em.internet_message_id = msg.get('internet_message_id')
    em.conversation_id = msg.get('conversation_id')
    em.from_address = msg.get('from_address')
    em.from_name = msg.get('from_name')
    em.to_addresses = msg.get('to_addresses') or []
    em.cc_addresses = msg.get('cc_addresses') or []
    em.bcc_addresses = msg.get('bcc_addresses') or []
    em.subject = msg.get('subject')
    em.body_text = msg.get('body_text')
    em.body_html = msg.get('body_html')
    em.body_preview = msg.get('body_preview')
    em.received_at = msg.get('received_at')
    em.importance = msg.get('importance')
    em.has_attachments = bool(msg.get('has_attachments'))
    em.is_read = bool(msg.get('is_read'))

    # Auto-link donor by from_address — only on create so a donor
    # match learned later doesn't clobber an operator's manual override.
    if is_create:
        donor = _match_donor(em.from_address)
        if donor:
            em.donor_id = donor.id

    if is_create:
        db.session.add(em)
        db.session.flush()  # need em.id for attachments

    # Attachment metadata — only on first ingest. We don't re-fetch
    # binaries on subsequent updates (read flags change a lot, attachments
    # don't).
    if is_create and em.has_attachments:
        try:
            att_resp = handler.list_attachments(msg['remote_id'])
            if att_resp.get('success'):
                for a in att_resp.get('attachments') or []:
                    if not a.get('remote_id'):
                        continue
                    db.session.add(EmailAttachment(
                        email_id=em.id,
                        remote_id=a['remote_id'],
                        filename=a.get('filename'),
                        content_type=a.get('content_type'),
                        size=a.get('size'),
                        is_inline=bool(a.get('is_inline')),
                        content_id=a.get('content_id'),
                    ))
            else:
                logger.warning(f'list_attachments failed for msg {em.id}: {att_resp.get("error")}')
        except Exception as e:
            logger.warning(f'attachment metadata fetch failed for msg {em.id}: {e}')

    return is_create, em


def sync_provider(provider, limit=500):
    """Sync one provider. Commits after each batch."""
    handler = provider.get_handler()
    result = handler.fetch_new_messages(limit=limit)

    if not result.get('success'):
        provider.last_sync_status = 'error'
        provider.last_sync_error = result.get('error')
        provider.last_sync_at = datetime.utcnow()
        db.session.commit()
        return {
            'provider': provider.code,
            'success': False,
            'error': result.get('error'),
            'created': 0,
            'updated': 0,
        }

    created = 0
    updated = 0
    for msg in result.get('messages') or []:
        try:
            is_create, _ = _persist_message(provider, msg, handler)
            if is_create:
                created += 1
            else:
                updated += 1
        except Exception as e:
            logger.error(f'Failed to persist message {msg.get("remote_id")}: {e}', exc_info=True)
            db.session.rollback()
            continue

    new_delta = result.get('new_delta')
    if new_delta:
        provider.last_delta_token = new_delta
    provider.last_sync_status = 'ok'
    provider.last_sync_error = None
    provider.last_sync_at = datetime.utcnow()
    db.session.commit()

    return {
        'provider': provider.code,
        'success':  True,
        'created':  created,
        'updated':  updated,
        'has_more': result.get('has_more'),
    }


def sync_all(limit=500):
    """Sync every enabled inbox provider."""
    results = []
    for provider in EmailInboxProvider.get_enabled():
        try:
            results.append(sync_provider(provider, limit=limit))
        except Exception as e:
            logger.error(f'Provider {provider.code} sync raised: {e}', exc_info=True)
            results.append({
                'provider': provider.code,
                'success':  False,
                'error':    str(e),
                'created':  0,
                'updated':  0,
            })
    return results
