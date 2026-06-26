"""Scan the Exchange inbox for delivery-failure notifications and
recover bounced receipt emails.

When an outbound receipt bounces, the receiving mail server returns a
DSN (Delivery Status Notification) / NDR (Non-Delivery Report) to the
sender — `support@matatmordechai.org`. Because the inbox is synced into
`email_messages`, the bounces are queryable from our DB.

Each pass of the sweep:
  1. Finds recent inbox rows that look like bounces.
  2. Parses the failed recipient address from the body / Final-Recipient.
  3. Looks up DonationContactSnapshot rows whose
     `receipt_sent_to_email` matches the failed address and that
     haven't already been marked bounced.
  4. Flips `receipt_bounced=true`, records the reason.
  5. If `donor.email` differs from the bounced address, regenerates
     the PDF and resends the receipt to the donor's main email, then
     marks `receipt_fallback_used=true`.

Invoke via `flask sweep-bounces` (registered in app/cli.py) — manual
for now, easy to wire into cron later.
"""
import re
import logging
from datetime import datetime, timedelta

from ..extensions import db
from ..models.email_message import EmailMessage
from ..models.donation_contact_snapshot import DonationContactSnapshot
from ..models.receipt import Receipt
from ..models.donation import Donation
from ..models.donor import Donor

logger = logging.getLogger(__name__)

# Subject + From patterns that identify bounce messages across providers.
_BOUNCE_SUBJECT_RE = re.compile(
    r'\b(undeliverable|delivery (status|notification|failure)|'
    r'mail delivery (failed|subsystem)|returned mail|'
    r'message not delivered|address rejected)\b',
    re.IGNORECASE,
)
_BOUNCE_FROM_RE = re.compile(
    r'(mailer-?daemon|postmaster|delivery[-_]?failure|'
    r'no-?reply.*(bounce|delivery))',
    re.IGNORECASE,
)
_EMAIL_RE = re.compile(r'[\w.+-]+@[\w-]+\.[\w.-]+')
_FINAL_RECIP_RE = re.compile(
    r'Final-Recipient:\s*[^;]*;\s*([^\s<>]+)', re.IGNORECASE,
)
_ORIG_RECIP_RE = re.compile(
    r'Original-Recipient:\s*[^;]*;\s*([^\s<>]+)', re.IGNORECASE,
)


def _is_bounce(msg):
    subj = (msg.subject or '')
    frm  = (msg.from_address or '') + ' ' + (msg.from_name or '')
    return bool(_BOUNCE_SUBJECT_RE.search(subj) or _BOUNCE_FROM_RE.search(frm))


def _extract_failed_recipient(msg):
    """Return the email address that bounced, or None."""
    body = (msg.body_text or '') + '\n' + (msg.body_html or '')

    m = _FINAL_RECIP_RE.search(body) or _ORIG_RECIP_RE.search(body)
    if m:
        return m.group(1).strip().lower()

    # Heuristic fallback: the first @-address that isn't our own
    for cand in _EMAIL_RE.findall(body):
        c = cand.lower()
        if 'matatmordechai.org' in c or 'mailer-daemon' in c or 'postmaster' in c:
            continue
        return c
    return None


def sweep_bounces(window_hours=72, dry_run=False):
    """Scan the last `window_hours` of inbox messages for DSN/NDR
    bounces and reconcile against snapshot rows.

    Returns a dict summary. Logs every action.
    """
    cutoff = datetime.utcnow() - timedelta(hours=window_hours)
    candidates = (EmailMessage.query
                  .filter(EmailMessage.received_at >= cutoff)
                  .order_by(EmailMessage.received_at.asc())
                  .all())
    logger.info(f'[bounce-sweep] {len(candidates)} inbox messages in last {window_hours}h')

    stats = {
        'inspected': len(candidates),
        'bounces_seen': 0,
        'snapshots_flipped': 0,
        'resends_succeeded': 0,
        'resends_failed': 0,
        'no_match': 0,
    }

    for msg in candidates:
        if not _is_bounce(msg):
            continue
        stats['bounces_seen'] += 1

        failed = _extract_failed_recipient(msg)
        if not failed:
            logger.warning(f'[bounce-sweep] msg #{msg.id} looks like a bounce but no recipient extracted')
            continue

        # Find every un-flipped snapshot whose receipt went to that address
        snaps = (DonationContactSnapshot.query
                 .filter(DonationContactSnapshot.receipt_sent_to_email.ilike(failed),
                         DonationContactSnapshot.receipt_bounced.is_(False))
                 .all())
        if not snaps:
            stats['no_match'] += 1
            continue

        for snap in snaps:
            reason = (msg.subject or '')[:500]
            logger.info(f'[bounce-sweep] snapshot #{snap.id} → bounced (was {failed!r}) — {reason!r}')
            if dry_run:
                continue
            snap.receipt_bounced = True
            snap.receipt_bounce_reason = reason
            stats['snapshots_flipped'] += 1

            # Try the fallback: resend to the donor's canonical email
            # if it actually differs from the address that bounced.
            donation = Donation.query.get(snap.donation_id)
            if not donation:
                continue
            donor = donation.donor
            main_email = (donor.email or '').strip()
            if not main_email or main_email.lower() == failed.lower():
                logger.info(f'[bounce-sweep] no usable fallback for donation #{donation.id} '
                            f'(donor.email={main_email!r})')
                continue

            receipt = Receipt.query.filter_by(donation_id=donation.id).first()
            if not receipt:
                logger.warning(f'[bounce-sweep] donation #{donation.id} has no receipt to resend')
                continue

            # Direct send to donor.email, bypassing the snapshot logic
            # in send_receipt_email so we actually go to the fallback.
            ok = _resend_receipt_to(donor, donation, receipt, main_email)
            if ok:
                snap.receipt_fallback_used = True
                snap.receipt_sent_to_email = main_email
                receipt.email_sent_to = main_email
                stats['resends_succeeded'] += 1
            else:
                stats['resends_failed'] += 1

        if not dry_run:
            db.session.commit()

    logger.info(f'[bounce-sweep] done: {stats}')
    return stats


def _resend_receipt_to(donor, donation, receipt, override_email):
    """Resend a receipt PDF to a specific address, bypassing
    send_receipt_email's snapshot-routing (which would otherwise pull
    us right back to the bounced address)."""
    import os
    from .email_service import send_email
    from flask import render_template

    if not (receipt.pdf_path and os.path.exists(receipt.pdf_path)):
        logger.warning(f'[bounce-sweep] receipt {receipt.receipt_number} PDF missing')
        return False

    html_body = render_template(
        'emails/receipt_en.html',
        donor=donor, donation=donation, receipt=receipt,
        amount=donation.amount / 100.0,
    )
    subject = (f'Your Tax-Deductible Receipt - Matat Mordechai '
               f'(#{receipt.receipt_number})')
    return send_email(
        to=override_email,
        subject=subject,
        html_body=html_body,
        attachments=[receipt.pdf_path],
        message_type='receipt',
        related_donation_id=donation.id,
    )
