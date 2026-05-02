"""Inbox sync orchestrator — provider-agnostic.

Walks every enabled EmailInboxProvider, asks its handler for new
messages, and persists them as EmailMessage / EmailAttachment rows.
The handler does the backend-specific work; this module only knows
about our DB schema.
"""
import logging
from datetime import datetime

from sqlalchemy.exc import IntegrityError

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


def _apply_message_fields(em, msg):
    """Copy every syncable field from the normalized message dict onto em.

    Donor link and portal-side state (is_archived) are deliberately not
    touched — those are owned by the create path / operator UI.
    """
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
    em.parent_folder_id = msg.get('parent_folder_id')
    em.folder_name = msg.get('folder_name')


def _persist_message(provider, msg, handler):
    """Insert or update one message + attachment metadata. Returns (created, message).

    Optimistic insert: try INSERT first inside a SAVEPOINT, fall back
    to fetch+UPDATE on IntegrityError. The cron at `* * * * *` and
    operator-triggered manual syncs both fetch the same Graph delta
    page, and only one INSERT can win the unique constraint
    (provider_id, remote_id) — the loser's IntegrityError lands inside
    the savepoint, gets caught, and turns into an update without
    poisoning the outer session.
    """
    em = EmailMessage(provider_id=provider.id, remote_id=msg['remote_id'])
    _apply_message_fields(em, msg)

    # Donor auto-link runs as part of the optimistic INSERT — on lost
    # race the winner already set donor_id (or not), and the UPDATE
    # path leaves the existing value alone so an operator override
    # later in the lifecycle isn't clobbered.
    donor = _match_donor(em.from_address)
    if donor:
        em.donor_id = donor.id

    is_create = False
    try:
        with db.session.begin_nested():
            db.session.add(em)
            db.session.flush()  # forces INSERT now so IntegrityError surfaces here
        is_create = True
    except IntegrityError:
        # Either pre-existing or we lost the race. Fetch and update.
        em = EmailMessage.query.filter_by(
            provider_id=provider.id, remote_id=msg['remote_id']
        ).first()
        if em is None:
            # Genuinely shouldn't happen — IntegrityError says it exists.
            raise
        _apply_message_fields(em, msg)

    # Attachment metadata — only on first ingest. The race winner does
    # this; losers don't double-fetch. We also don't re-fetch on
    # subsequent updates (read flags change a lot, attachments don't).
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
    """Sync one provider. Commits after each message so row locks are
    released immediately — this keeps a parallel cron run from blocking
    on rows we've already inserted but not yet committed."""
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
            db.session.commit()
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
