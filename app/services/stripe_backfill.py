"""Pull the full Stripe payload (PaymentIntent + Charge + Customer +
Checkout Session) for every historical donation and persist it into
`DonationContactSnapshot.raw_data`. Lets us answer any future question
about a transaction without round-tripping Stripe — even if Stripe is
unreachable or our account access changes.

Run via:
    flask backfill-stripe-snapshots
    flask backfill-stripe-snapshots --limit 50 --start-id 6000
    flask backfill-stripe-snapshots --dry-run

Idempotent: skips any donation whose snapshot already has the full
`raw_data.payment_intent` set, so re-running is safe.
"""
import os
import json
import logging
import time
import stripe

from ..extensions import db
from ..models.donation import Donation
from ..models.donation_contact_snapshot import DonationContactSnapshot
from ..models.config_settings import ConfigSettings

logger = logging.getLogger(__name__)


def _to_plain(obj):
    """Stripe objects subclass dict but may carry nested Stripe types.
    json-roundtrip with default=str makes the whole tree storable as
    JSON without losing values to repr."""
    return json.loads(json.dumps(obj, default=str))


def _pick(*candidates):
    for c in candidates:
        v = c
        if hasattr(v, 'strip'):
            v = v.strip()
        if v:
            return v
    return None


def _populate_typed_fields(snap, pi, charge, customer, session):
    """Choose best-available source for each typed snapshot field.
    Priority: Checkout Session.customer_details → Charge.billing_details
    → Customer. Never blank-out an existing value if Stripe has none."""
    cd      = getattr(session, 'customer_details', None) if session else None
    cd_addr = getattr(cd, 'address', None) if cd else None
    bd      = getattr(charge, 'billing_details', None) if charge else None
    bd_addr = getattr(bd, 'address', None) if bd else None

    # Phone may live inside session.custom_fields too (we use that for
    # the Stripe Payment Link's optional-phone field).
    custom_phone = None
    for cf in (getattr(session, 'custom_fields', None) or []):
        if (getattr(cf, 'key', None) or '') == 'phone':
            txt = getattr(cf, 'text', None)
            custom_phone = (getattr(txt, 'value', None) or '').strip() or None
            break

    email = _pick(
        getattr(cd, 'email', None) if cd else None,
        getattr(bd, 'email', None) if bd else None,
        getattr(customer, 'email', None) if customer else None,
    )
    name = _pick(
        getattr(cd, 'name', None) if cd else None,
        getattr(bd, 'name', None) if bd else None,
        getattr(customer, 'name', None) if customer else None,
    )
    phone = _pick(
        custom_phone,
        getattr(cd, 'phone', None) if cd else None,
        getattr(bd, 'phone', None) if bd else None,
        getattr(customer, 'phone', None) if customer else None,
    )
    addr = cd_addr or bd_addr  # session preferred over charge billing
    if addr is None and customer is not None:
        addr = getattr(customer, 'address', None) or getattr(
            getattr(customer, 'shipping', None), 'address', None
        )

    if name:
        parts = name.split(None, 1)
        snap.first_name = snap.first_name or (parts[0] if parts else None)
        snap.last_name  = snap.last_name  or (parts[1] if len(parts) > 1 else None)
    if email:
        snap.email = snap.email or email.strip().lower()
    if phone:
        snap.phone = snap.phone or phone.strip()
    if addr is not None:
        snap.address_line1 = snap.address_line1 or getattr(addr, 'line1', None) or None
        snap.address_line2 = snap.address_line2 or getattr(addr, 'line2', None) or None
        snap.city          = snap.city          or getattr(addr, 'city', None) or None
        snap.state         = snap.state         or getattr(addr, 'state', None) or None
        snap.zip           = snap.zip           or getattr(addr, 'postal_code', None) or None
        snap.country       = snap.country       or getattr(addr, 'country', None) or None


def _retrieve_pi(pi_id, live_key, test_key):
    """Retrieve a PaymentIntent, trying live first then test. Old test-
    mode donations have PI IDs that only resolve under the test key.
    Returns (pi, mode) or raises."""
    last_err = None
    for key, mode in [(live_key, 'live'), (test_key, 'test')]:
        if not key:
            continue
        stripe.api_key = key
        try:
            pi = stripe.PaymentIntent.retrieve(
                pi_id, expand=['latest_charge.balance_transaction', 'customer'],
            )
            return pi, mode
        except stripe.error.InvalidRequestError as e:
            last_err = e
            # Only fall through to test if Stripe specifically tells us
            # the object exists in the other mode
            if 'similar object exists in test mode' not in str(e):
                raise
    raise last_err


def backfill_all(limit=None, start_id=0, dry_run=False, sleep_s=0.05):
    cfg = ConfigSettings.query.first()
    live_key = (cfg.stripe_live_secret_key
                or os.environ.get('STRIPE_LIVE_SECRET_KEY'))
    test_key = (cfg.stripe_test_secret_key
                or os.environ.get('STRIPE_TEST_SECRET_KEY'))
    if not (live_key or test_key):
        raise RuntimeError('No Stripe secret keys configured.')
    stripe.api_key = live_key or test_key

    q = (Donation.query
         .filter(Donation.stripe_payment_intent_id.isnot(None))
         .filter(Donation.id > start_id)
         .order_by(Donation.id.asc()))
    if limit:
        q = q.limit(limit)
    donations = q.all()
    total = len(donations)
    logger.info(f'[stripe-backfill] working {total} donations')

    stats = {'ok': 0, 'skip': 0, 'fail': 0}

    for i, d in enumerate(donations, 1):
        # Idempotency — skip if the snapshot already has the full PI.
        snap = (DonationContactSnapshot.query
                .filter_by(donation_id=d.id).first())
        if snap and (snap.raw_data or {}).get('payment_intent'):
            stats['skip'] += 1
            continue

        try:
            pi, pi_mode = _retrieve_pi(
                d.stripe_payment_intent_id, live_key, test_key,
            )
            charge   = getattr(pi, 'latest_charge', None)
            if isinstance(charge, str):
                charge = None
            customer = getattr(pi, 'customer', None)
            if isinstance(customer, str):
                customer = None

            # Checkout Session — only exists if PI came through Payment
            # Link / Checkout. Cheap to ask either way.
            session = None
            try:
                lst = stripe.checkout.Session.list(payment_intent=pi.id, limit=1)
                if lst.data:
                    session = lst.data[0]
            except stripe.error.StripeError:
                pass

            if snap is None:
                snap = DonationContactSnapshot(
                    donation_id=d.id,
                    donor_id=d.donor_id,
                )
                db.session.add(snap)

            # Tag the source so we can tell backfilled rows apart from
            # live-written ones during future audits. Keep the original
            # source if there already was one.
            if not snap.source:
                snap.source = 'stripe_backfill'
            elif snap.source != 'stripe_backfill' and 'backfill' not in snap.source:
                snap.source = f'{snap.source}+backfill'

            _populate_typed_fields(snap, pi, charge, customer, session)

            snap.raw_data = {
                'payment_intent':   _to_plain(pi),
                'charge':           _to_plain(charge)   if charge   else None,
                'customer':         _to_plain(customer) if customer else None,
                'checkout_session': _to_plain(session)  if session  else None,
                'stripe_mode':      pi_mode,
                'backfilled_at':    __import__('datetime').datetime.utcnow().isoformat(),
            }
            stats['ok'] += 1

            # Commit per row so a mid-run failure doesn't lose progress
            if not dry_run:
                db.session.commit()

            if i % 10 == 0 or i == total:
                logger.info(f'[stripe-backfill] {i}/{total} ok={stats["ok"]} '
                            f'skip={stats["skip"]} fail={stats["fail"]}')

        except stripe.error.StripeError as e:
            stats['fail'] += 1
            logger.warning(f'[stripe-backfill] donation #{d.id} pi={d.stripe_payment_intent_id} '
                           f'→ {e}')
            db.session.rollback()

        time.sleep(sleep_s)

    logger.info(f'[stripe-backfill] done: {stats}')
    return stats
