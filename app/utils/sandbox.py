"""SANDBOX_MODE — kill-switch for all outbound live transactions.

When `SANDBOX_MODE=1` is set in the environment (or via config), every
service that would otherwise hit a live external API (payment processors,
email, SMS, accounting systems) short-circuits and returns a fake-success
response. This lets an operator run their full workflow against real data
without any real money moving, emails going out, or third-party side effects.

Use:
    from app.utils.sandbox import is_sandbox, sandbox_email, sandbox_charge

    if is_sandbox():
        return sandbox_charge(amount=..., reason='pre-deploy operator sign-off')

The sandbox is a process-wide, read-only flag — never toggled at runtime
from user actions. It's set once at startup from the SANDBOX_MODE env var.
"""
from __future__ import annotations

import os
import uuid
import logging
from datetime import datetime

logger = logging.getLogger(__name__)


# Read once at module import. Any truthy string other than "" or "0"/"false"/
# "no"/"off" enables sandbox.
_RAW = (os.environ.get('SANDBOX_MODE') or os.environ.get('MATAT_SANDBOX') or '').strip().lower()
_SANDBOX = _RAW not in ('', '0', 'false', 'no', 'off')

if _SANDBOX:
    logger.warning('*' * 60)
    logger.warning('* SANDBOX_MODE ACTIVE — no live transactions will fire *')
    logger.warning('*' * 60)


def is_sandbox() -> bool:
    """Process-wide read of the SANDBOX_MODE env flag."""
    return _SANDBOX


# ------------------------------------------------------------------
# Fake-success stubs. Each mimics the shape of a real provider reply.
# ------------------------------------------------------------------

def sandbox_email_success(to: str, subject: str, **_):
    """Pretend an email provider accepted a message."""
    mid = f'sandbox-{uuid.uuid4().hex[:16]}'
    logger.info(f'[SANDBOX] would send email to={to} subject={subject[:60]!r} msg_id={mid}')
    return {
        'success': True,
        'sandbox': True,
        'message_id': mid,
        'message_ids': [mid],
        'provider': 'sandbox',
    }


def sandbox_charge_success(amount=0, currency='ILS', **kwargs):
    """Pretend a payment processor authorized and captured a charge."""
    txn_id = f'sbx_{uuid.uuid4().hex[:20]}'
    logger.info(f'[SANDBOX] would charge {amount} {currency} — txn_id={txn_id}')
    return {
        'success': True,
        'status': 'succeeded',
        'sandbox': True,
        'transaction_id': txn_id,
        'authorization_code': 'SANDBOX-AUTH',
        'reference_number': txn_id,
        'charged_amount': amount,
        'currency': currency,
        'approval_code': 'SANDBOX',
        'raw_response': {'sandbox': True, **kwargs},
    }


def sandbox_receipt_success(donation_id=None, **kwargs):
    """Pretend an accounting provider (EZCount, Yeshinvoice) issued a receipt."""
    doc_no = f'SBX-{uuid.uuid4().hex[:8].upper()}'
    logger.info(f'[SANDBOX] would issue receipt donation={donation_id} doc_no={doc_no}')
    return {
        'success': True,
        'sandbox': True,
        'doc_id': doc_no,
        'doc_number': doc_no,
        'pdf_url': 'about:blank',  # safe placeholder
        'raw_response': {'sandbox': True, **kwargs},
    }


def sandbox_sms_success(to: str, body: str, **_):
    """Pretend Twilio accepted an SMS."""
    sid = f'SM{uuid.uuid4().hex[:30]}'
    logger.info(f'[SANDBOX] would send SMS to={to} body={body[:60]!r} sid={sid}')
    return {
        'success': True,
        'sandbox': True,
        'sid': sid,
        'status': 'queued',
    }


def sandbox_masav_success(file_name=None, **_):
    """Pretend a Masav batch was accepted by the bank."""
    batch_id = f'MSV-{datetime.utcnow():%Y%m%d%H%M%S}'
    logger.info(f'[SANDBOX] would submit Masav batch file={file_name} batch_id={batch_id}')
    return {'success': True, 'sandbox': True, 'batch_id': batch_id}


# Generic marker for use in webhook/processor branches
SANDBOX_BANNER_HTML = (
    '<div style="background:#FFECB3;color:#6D4C41;padding:6px 14px;'
    'border-bottom:2px solid #FB8C00;font-size:12px;font-weight:bold;'
    'text-align:center;font-family:\'Segoe UI\',Tahoma,Arial,sans-serif;">'
    '⚠️ SANDBOX MODE — תצוגת הדגמה / No live transactions will be sent ⚠️'
    '</div>'
)
