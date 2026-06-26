"""One-shot — ingest every Stripe transaction from the dashboard CSV
that isn't already in our donations table. Records ALL outcomes
(paid / failed / canceled / abandoned) so the operator can look up
any Stripe attempt without leaving the system.

Reads /var/www/matat/unified_payments.csv (the Stripe Dashboard
export). Skips rows whose PaymentIntent ID already exists in our
donations table. For each remaining row:

  1) Find or create the donor by email; otherwise create a placeholder
     donor with whatever Stripe provided (name on card / address).
  2) Insert a Donation row with the right status, amount, and
     Stripe IDs.
  3) Fetch the full PaymentIntent / Charge / Customer / Checkout
     Session from Stripe and dump into a DonationContactSnapshot row.

Does NOT generate or send receipts — per the project rule on
migrations, the operator reviews first.
"""
import csv, json, os, stripe, time
from datetime import datetime
from app import create_app
from app.extensions import db
from app.models.donation import Donation
from app.models.donor import Donor
from app.models.config_settings import ConfigSettings
from app.models.donation_contact_snapshot import DonationContactSnapshot


# Stripe Dashboard status → our Donation.status convention
STATUS_MAP = {
    'paid':                     'succeeded',
    'failed':                   'failed',
    'canceled':                 'canceled',
    'requires_payment_method':  'pending',  # abandoned mid-flow
}


def _stripe_to_plain(obj):
    return json.loads(json.dumps(obj, default=str))


def _find_or_create_donor(row, default_test=False):
    """Match an existing donor by Stripe customer id → email →
    create a placeholder donor with whatever Stripe gave us."""
    email = (row.get('Customer Email') or '').strip().lower() or None
    stripe_cust_id = (row.get('Customer ID') or '').strip() or None

    donor = None
    if stripe_cust_id:
        donor = Donor.query.filter_by(stripe_customer_id=stripe_cust_id).first()
    if not donor and email:
        donor = Donor.query.filter_by(email=email).first()
    if donor:
        return donor

    name = (row.get('Card Name') or '').strip()
    parts = name.split(None, 1) if name else []
    first = parts[0] if parts else 'Unknown'
    last  = parts[1] if len(parts) > 1 else 'Donor'

    donor = Donor(
        first_name=first,
        last_name=last,
        email=email or 'unknown@example.com',
        address_line1=(row.get('Card Address Line1') or '').strip() or None,
        city=(row.get('Card Address City') or '').strip() or None,
        state=(row.get('Card Address State') or '').strip() or None,
        zip=(row.get('Card Address Zip') or '').strip() or None,
        country=(row.get('Card Address Country') or '').strip() or None,
        stripe_customer_id=stripe_cust_id,
        test=default_test,
    )
    db.session.add(donor)
    db.session.flush()
    return donor


def _import_row(row, live_key, test_key):
    pi_id = (row.get('PaymentIntent ID') or '').strip()
    if not pi_id:
        return 'no_pi', None

    if Donation.query.filter_by(stripe_payment_intent_id=pi_id).first():
        return 'exists', None

    csv_status = (row.get('Status') or '').strip().lower()
    our_status = STATUS_MAP.get(csv_status, csv_status)

    amount_dollars = float(row.get('Amount') or 0)
    amount_cents = int(round(amount_dollars * 100))
    currency = (row.get('Currency') or 'usd').lower()

    created_str = row.get('Created date (UTC)') or ''
    try:
        created_at = datetime.strptime(created_str, '%Y-%m-%d %H:%M:%S')
    except Exception:
        created_at = datetime.utcnow()

    donor = _find_or_create_donor(row)

    # Try to pull the full Stripe payload — try live first, then test
    pi = charge = customer = session = None
    used_mode = None
    for key, mode in [(live_key, 'live'), (test_key, 'test')]:
        if not key:
            continue
        stripe.api_key = key
        try:
            pi = stripe.PaymentIntent.retrieve(
                pi_id,
                expand=['latest_charge.balance_transaction', 'customer'],
            )
            used_mode = mode
            charge   = getattr(pi, 'latest_charge', None)
            if isinstance(charge, str):
                charge = None
            customer = getattr(pi, 'customer', None)
            if isinstance(customer, str):
                customer = None
            try:
                lst = stripe.checkout.Session.list(payment_intent=pi.id, limit=1)
                if lst.data:
                    session = lst.data[0]
            except stripe.error.StripeError:
                pass
            break
        except stripe.error.InvalidRequestError as e:
            if 'similar object exists in test mode' not in str(e):
                pi = None
                break

    donation = Donation(
        donor_id=donor.id,
        amount=amount_cents,
        currency=currency,
        status=our_status,
        donation_type='one_time',
        source='backfilled_from_csv',
        payment_processor='stripe',
        stripe_payment_intent_id=pi_id,
        stripe_charge_id=row.get('id') or None,
        created_at=created_at,
        salesperson_id=None,
    )
    db.session.add(donation)
    db.session.flush()

    snap = DonationContactSnapshot(
        donation_id=donation.id,
        donor_id=donor.id,
        source='csv_backfill',
        first_name=(row.get('Card Name') or '').split(None, 1)[0] if row.get('Card Name') else None,
        last_name=(row.get('Card Name') or '').split(None, 1)[1] if len((row.get('Card Name') or '').split(None, 1)) > 1 else None,
        email=(row.get('Customer Email') or '').strip().lower() or None,
        phone=(row.get('Customer Phone') or '').strip() or None,
        address_line1=(row.get('Card Address Line1') or '').strip() or None,
        address_line2=(row.get('Card Address Line2') or '').strip() or None,
        city=(row.get('Card Address City') or '').strip() or None,
        state=(row.get('Card Address State') or '').strip() or None,
        zip=(row.get('Card Address Zip') or '').strip() or None,
        country=(row.get('Card Address Country') or '').strip() or None,
        raw_data={
            'csv_row':          {k: v for k, v in row.items() if v},
            'payment_intent':   _stripe_to_plain(pi)       if pi       else None,
            'charge':           _stripe_to_plain(charge)   if charge   else None,
            'customer':         _stripe_to_plain(customer) if customer else None,
            'checkout_session': _stripe_to_plain(session)  if session  else None,
            'stripe_mode':      used_mode,
            'imported_at':      datetime.utcnow().isoformat(),
        },
    )
    db.session.add(snap)
    return 'ok', (donation.id, our_status)


def main():
    app = create_app()
    with app.app_context():
        c = ConfigSettings.query.first()
        live_key = c.stripe_live_secret_key or os.environ.get('STRIPE_LIVE_SECRET_KEY')
        test_key = c.stripe_test_secret_key or os.environ.get('STRIPE_TEST_SECRET_KEY')

        results = {'ok': 0, 'exists': 0, 'no_pi': 0, 'by_status': {}}
        created_ids = []

        with open('/var/www/matat/unified_payments.csv', encoding='utf-8') as fp:
            rows = list(csv.DictReader(fp))

        for i, row in enumerate(rows, 1):
            outcome, info = _import_row(row, live_key, test_key)
            results[outcome] = results.get(outcome, 0) + 1
            if outcome == 'ok':
                results['by_status'][info[1]] = results['by_status'].get(info[1], 0) + 1
                created_ids.append(info[0])
                db.session.commit()
            if i % 10 == 0:
                print(f'[{i}/{len(rows)}] {results}')
            time.sleep(0.05)

        db.session.commit()
        print(f'\nDONE: {results}')
        if created_ids:
            print(f'Created donation ids: {created_ids}')


if __name__ == '__main__':
    main()
